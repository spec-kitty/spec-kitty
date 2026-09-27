"""Shared fixtures for the WP03 concurrency test surface.

These fixtures back the three test files that exercise the WP01 + WP02
contract under cross-process load:

- ``test_machine_refresh_lock.py`` — same-process concurrent refresh
- ``test_stale_grant_preservation.py`` — deterministic stale-grant scenarios
- ``test_incident_regression.py`` — multiprocess subprocess-based regression

Two essential fixtures are exposed:

* ``auth_store_root`` — a ``tmp_path``-rooted auth directory plus a
  monkeypatch that redirects the ``_refresh_lock_path`` resolver in
  :mod:`specify_cli.auth.token_manager` so the machine-wide lock lands
  inside ``tmp_path`` instead of the user's real home directory.
* ``fake_refresh_server`` — a ``http.server.HTTPServer`` thread bound to
  ``127.0.0.1:0`` that mirrors the real SaaS ``POST /token`` contract
  closely enough for the multiprocess regression test to drive the
  rotate-then-stale-grant scenario without network access (C-003).

Together with ``seed_session`` they let test workers spawn from a clean
``tmp_path`` with a valid initial session and a deterministic refresh
endpoint pointing at a local port.

The fake server is a fixture, not a substitute for the production refresh
path. The in-process tests exercise the real WP01 (``MachineFileLock``)
and WP02 (``run_refresh_transaction``) modules; only the network leg is
faked. The subprocess test exercises the *deployment shape* of the
incident with two real ``subprocess.Popen`` workers sharing one auth root.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from kernel.clock import now_utc, timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

import pytest

from specify_cli.auth import token_manager as tm_module
from specify_cli.auth.secure_storage.file_fallback import FileFallbackStorage
from specify_cli.auth.session import StoredSession, Team


# ---------------------------------------------------------------------------
# Auth store fixture
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _configured_saas_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """This concurrency surface exercises refresh/single-flight/lock
    mechanics, not endpoint resolution — endpoint opt-in (FR-011) means an
    unset ``SPEC_KITTY_SAAS_URL`` now raises ``HostedEndpointUnconfigured``
    from ``resolve_token_endpoint`` (called at the top of
    ``refresh_if_needed``) instead of silently resolving to a packaged
    default. Sets a default configured target; a test using
    ``fake_refresh_server`` overrides it with the real fake-server URL via
    its own ``monkeypatch.setenv`` call, which wins (set after this fixture
    runs)."""
    monkeypatch.setenv("SPEC_KITTY_SAAS_URL", "https://saas.test")


@pytest.fixture
def auth_store_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Return a ``tmp_path``-rooted auth directory with the lock redirected.

    The encrypted file storage backend (:class:`FileFallbackStorage`) accepts
    an explicit ``base_dir``, so we do not need to monkeypatch ``Path.home``
    for the session file. We do, however, need to redirect the
    machine-wide ``_refresh_lock_path`` resolver in
    :mod:`specify_cli.auth.token_manager` so the lock file lands inside
    ``tmp_path``. Tests that override this with a per-test path may do so
    by re-applying ``monkeypatch.setattr`` in the test body.
    """
    auth_root = tmp_path / "auth"
    auth_root.mkdir(parents=True, exist_ok=True)

    lock_path = auth_root / "refresh.lock"
    monkeypatch.setattr(tm_module, "_refresh_lock_path", lambda: lock_path)
    return auth_root


# ---------------------------------------------------------------------------
# Session seeding helpers
# ---------------------------------------------------------------------------


def _build_seed_session(
    *,
    refresh_token: str = "rt_seed_v1",
    access_token: str = "at_seed_v1",
    session_id: str = "sess_seed",
    access_expires_in: int = 1,
    refresh_expires_in: int = 60 * 60 * 24 * 30,
) -> StoredSession:
    """Build a :class:`StoredSession` whose access token is near-expiry.

    Defaults to a 1-second access-token TTL so workers that sleep briefly
    will trigger refresh, and a 30-day refresh-token TTL so the server-side
    expiry check never fires accidentally.
    """
    now = now_utc()
    return StoredSession(
        user_id="user_seed",
        email="seed@example.com",
        name="Seed User",
        teams=[Team(id="t-seed", name="T", role="owner")],
        default_team_id="t-seed",
        access_token=access_token,
        refresh_token=refresh_token,
        session_id=session_id,
        issued_at=now,
        access_token_expires_at=now + timedelta(seconds=access_expires_in),
        refresh_token_expires_at=now + timedelta(seconds=refresh_expires_in),
        scope="openid offline_access",
        storage_backend="file",
        last_used_at=now,
        auth_method="authorization_code",
    )


@pytest.fixture
def seed_session(auth_store_root: Path) -> StoredSession:
    """Persist a starter session under ``auth_store_root`` and return it.

    Uses the real :class:`FileFallbackStorage` so the on-disk artifacts
    (``session.json`` ciphertext + ``session.key``) match what the
    production code writes. Workers that load via ``SecureStorage``
    pointing at the same ``base_dir`` will read this session back.
    """
    session = _build_seed_session()
    storage = FileFallbackStorage(base_dir=auth_store_root)
    storage.write(session)
    return session


# ---------------------------------------------------------------------------
# Fake refresh server fixture
# ---------------------------------------------------------------------------


def _now_iso(seconds_from_now: int) -> str:
    return (now_utc() + timedelta(seconds=seconds_from_now)).isoformat()


def _build_handler_class(
    *,
    counter_path: Path,
    seed_refresh_token: str,
    rotated_refresh_token: str,
    rotated_session_id: str,
) -> type[BaseHTTPRequestHandler]:
    """Build a request handler class with the rotation contract baked in.

    The handler:

    * counts requests by appending one byte to ``counter_path`` per call;
    * on the **first** call (any refresh token), returns a 200 response
      that rotates ``seed_refresh_token`` -> ``rotated_refresh_token``;
    * on subsequent calls with the seed (now-stale) token, returns
      ``400 invalid_grant`` (the canonical SaaS rejection shape);
    * on subsequent calls with the rotated token, returns another 200
      rotation that is idempotent (keeps the same refresh_token).

    The tracked-state primitive is the byte-length of ``counter_path``
    rather than a Python counter, because the subprocess regression
    test (T014) reads this file from the orchestrator process to
    assert the request count without IPC.
    """
    counter_lock = threading.Lock()

    class _Handler(BaseHTTPRequestHandler):
        # Silence the default access log — keeps pytest output clean.
        def log_message(  # noqa: D401 — base-class override
            self, format: str, *args: Any
        ) -> None:
            return

        def _record_call(self) -> int:
            with counter_lock:
                with counter_path.open("ab") as fp:
                    fp.write(b".")
                return counter_path.stat().st_size

        def _read_body(self) -> dict[str, str]:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8") if length else ""
            parsed = parse_qs(raw)
            return {k: v[0] for k, v in parsed.items() if v}

        def _send_json(self, status: int, body: dict[str, Any]) -> None:
            payload = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_POST(self) -> None:  # noqa: N802 — http.server hook name
            if self.path != "/oauth/token":
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return
            body = self._read_body()
            received_refresh_token = body.get("refresh_token", "")
            self._record_call()

            if received_refresh_token == seed_refresh_token:
                # First (or any) call presenting the seed token: if it is
                # still the freshly-rotatable one, rotate. Distinguish by
                # whether the rotated token has been issued already (we
                # use the sentinel sidecar file).
                rotated_marker = counter_path.with_suffix(".rotated")
                if not rotated_marker.exists():
                    rotated_marker.write_text("1")
                    self._send_json(
                        HTTPStatus.OK,
                        {
                            "access_token": "at_rotated_v2",
                            "refresh_token": rotated_refresh_token,
                            "expires_in": 900,
                            "refresh_token_expires_in": 60 * 60 * 24 * 30,
                            "scope": "openid offline_access",
                            "token_type": "Bearer",
                            "session_id": rotated_session_id,
                        },
                    )
                    return
                # Seed token presented after rotation -> stale grant.
                self._send_json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "invalid_grant"},
                )
                return

            if received_refresh_token == rotated_refresh_token:
                # Idempotent re-rotation for retries.
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "access_token": "at_rotated_v3",
                        "refresh_token": rotated_refresh_token,
                        "expires_in": 900,
                        "refresh_token_expires_in": 60 * 60 * 24 * 30,
                        "scope": "openid offline_access",
                        "token_type": "Bearer",
                        "session_id": rotated_session_id,
                    },
                )
                return

            # Anything else is a hard rejection.
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "invalid_grant"},
            )

    return _Handler


@pytest.fixture
def fake_refresh_server(
    tmp_path: Path,
) -> Iterator[tuple[str, Path]]:
    """Spawn a localhost HTTP server modelling the SaaS refresh endpoint.

    Yields ``(server_url, counter_path)`` where:

    - ``server_url`` is the base URL (e.g. ``http://127.0.0.1:54321``).
      Tests can set ``SPEC_KITTY_SAAS_URL`` to this value to point the
      production :class:`TokenRefreshFlow` at the fake server.
    - ``counter_path`` is a file whose byte-length equals the number of
      ``POST /oauth/token`` calls observed. Tests assert against this
      file's size (read directly so subprocess tests can poll it).

    The handler implements the rotation contract documented on
    :func:`_build_handler_class`. The server is bound to port 0 so each
    test gets a unique port and CI can run tests in parallel without
    collisions.
    """
    counter_path = tmp_path / "refresh_counter.bin"
    counter_path.write_bytes(b"")

    handler_cls = _build_handler_class(
        counter_path=counter_path,
        seed_refresh_token="rt_seed_v1",
        rotated_refresh_token="rt_rotated_v2",
        rotated_session_id="sess_seed",
    )

    server = HTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host_raw, port = server.server_address[0], server.server_address[1]
        host = host_raw.decode() if isinstance(host_raw, bytes) else host_raw
        yield f"http://{host}:{port}", counter_path
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2.0)
