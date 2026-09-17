"""The local Team Kitty double (Z1.md §4 preamble).

An in-process ``http.server.ThreadingHTTPServer``-based fixture that speaks
just enough of the F3 ``ControlEnvelope``/``LiveFrame`` transport surface for
Z1's own test suite: it accepts any POST/GET, records every request it
receives (method, path, headers, parsed JSON body), can be configured to
delay or fail its response, and counts connections/requests separately from
whether they were *acted on* by the client under test.

Precedent: ``tests/saas/conftest.py:159-172`` (``local_http_stub`` /
``_HeadOkHandler``) — same ``127.0.0.1:0`` OS-assigned-port pattern, extended
here to record request bodies and support configurable delay/status, per the
cross-repo ``provider_double`` convention (m1-contract-drafts/E1-L.md).

Never a real Docker Zeitgeist container — that is DKR-M1-02-ZEITGEIST/E1-L
territory (Z1.md §4 preamble); this double never leaves ``127.0.0.1``.
"""

from __future__ import annotations

import contextlib
import http.server
import json
import queue
import socket
import threading
import time
import os
from collections.abc import Callable, Generator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from kernel.clock import now_epoch

from specify_cli.zeitgeist_client import moments, repo_identity


@pytest.fixture()
def instead_of_rewrite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """A synthetic global git config that rewrites ``https://github.com/``
    onto a proxy host, inherited by every child ``git`` through
    ``GIT_CONFIG_GLOBAL`` with system-level config disabled, so the real
    machine config is never touched.

    This is the shape every exe.dev VM — and many corporate laptops — carry
    for real, and it is exactly what made identity resolution report the
    proxy instead of the checkout's own origin (#81): Team Kitty admits by
    the forge host the checkout names, so a machine-local transport rewrite
    must never stand in for it. Installing it unconditionally makes the
    host assertions below deterministic on machines with no rewrite of
    their own.

    Returns the proxy host the rewrite installs, to assert against."""
    proxy_host = "github.int.example.invalid"
    config_path = tmp_path / "global-gitconfig"
    config_path.write_text(f'[url "https://{proxy_host}/"]\n\tinsteadOf = https://github.com/\n')
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config_path))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    return proxy_host


@pytest.fixture()
def no_git_ancestry_inside_tmp_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Keep an unrelated ancestor checkout's identity from leaking into
    tests that build a repo-less directory under ``tmp_path`` and expect
    resolution to fail closed with ``UnverifiedRepositoryIdentity``.

    When pytest's base temp directory itself sits under a checkout with an
    ``origin`` remote configured — true of every exe.dev VM in this
    programme, where repos live under ``/work`` — the upward walk both the
    filesystem fallback (``_git_dir_from_filesystem``) and the live-git
    probe (``Deadline.run``) perform can reach past ``tmp_path`` into that
    ancestor and mint ITS identity instead of raising. Bound both to
    ``tmp_path``, the same boundary-pin PR #386 established for one test:
    a lookup that would otherwise resolve to a ``.git`` OUTSIDE
    ``tmp_path`` reports nothing found, exactly as a real repo-less
    directory would, while a ``.git`` genuinely created inside
    ``tmp_path`` by the test itself (e.g. the ``origin``/``_clone``
    fixtures) is unaffected.
    """
    boundary = os.path.abspath(str(tmp_path))
    real_git_dir_from_filesystem: Callable[[str], str] = (
        repo_identity._git_dir_from_filesystem
    )
    real_deadline_run: Callable[[repo_identity.Deadline, list[str], str], str] = (
        repo_identity.Deadline.run
    )

    def _inside_boundary(path: str) -> bool:
        candidate = os.path.abspath(path)
        return candidate == boundary or candidate.startswith(boundary + os.sep)

    def _bounded_git_dir_from_filesystem(cwd: str) -> str:
        git_dir = real_git_dir_from_filesystem(cwd)
        if git_dir and not _inside_boundary(git_dir):
            return ""
        return git_dir

    def _bounded_deadline_run(
        self: repo_identity.Deadline, args: list[str], cwd: str
    ) -> str:
        git_dir = real_git_dir_from_filesystem(os.path.realpath(cwd))
        if git_dir and not _inside_boundary(git_dir):
            return ""
        return real_deadline_run(self, args, cwd)

    monkeypatch.setattr(
        repo_identity, "_git_dir_from_filesystem", _bounded_git_dir_from_filesystem
    )
    monkeypatch.setattr(repo_identity.Deadline, "run", _bounded_deadline_run)


@dataclass
class RecordedRequest:
    method: str
    path: str
    headers: dict[str, str]
    body: Any


@dataclass
class TeamKittyDouble:
    """A minimal, in-process, loopback-only relay double."""

    requests: list[RecordedRequest] = field(default_factory=list)
    connection_count: int = 0
    response_status: int = 200
    response_body: dict[str, Any] = field(default_factory=dict)
    response_delay_s: float = 0.0

    _server: http.server.ThreadingHTTPServer | None = None
    _thread: threading.Thread | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def start(self) -> None:
        handler_cls = self._make_handler()
        self._server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def url(self) -> str:
        assert self._server is not None
        host, port = self._server.server_address[:2]
        return f"http://127.0.0.1:{port}"

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2)

    def configure(
        self,
        *,
        status: int | None = None,
        body: dict[str, Any] | None = None,
        delay_s: float | None = None,
    ) -> None:
        if status is not None:
            self.response_status = status
        if body is not None:
            self.response_body = body
        if delay_s is not None:
            self.response_delay_s = delay_s

    def _make_handler(self) -> type[http.server.BaseHTTPRequestHandler]:
        double = self

        class _Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def _handle(self) -> None:
                with double._lock:
                    double.connection_count += 1
                length = int(self.headers.get("Content-Length", 0) or 0)
                raw = self.rfile.read(length) if length else b""
                parsed: Any = None
                if raw:
                    try:
                        parsed = json.loads(raw)
                    except json.JSONDecodeError:
                        parsed = None
                with double._lock:
                    double.requests.append(RecordedRequest(self.command, self.path, dict(self.headers), parsed))
                if double.response_delay_s:
                    time.sleep(double.response_delay_s)
                payload = json.dumps(double.response_body).encode("utf-8")
                self.send_response(double.response_status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                with contextlib.suppress(BrokenPipeError, ConnectionResetError):
                    self.wfile.write(payload)

            def do_POST(self) -> None:  # noqa: N802
                self._handle()

            def do_GET(self) -> None:  # noqa: N802
                self._handle()

            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                pass

        return _Handler


@pytest.fixture()
def team_kitty_double() -> Generator[TeamKittyDouble, None, None]:
    double = TeamKittyDouble()
    double.start()
    try:
        yield double
    finally:
        double.stop()


# --- #190: pin the moment preferences these suites run under ----------------


@pytest.fixture(autouse=True)
def moments_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The developer-global ``~/.kittify/config.toml`` every test in this
    subsystem reads, redirected to a per-test file and pre-written with the
    widest mode (``team``).

    Two reasons this pin exists. Hermeticity: without it each test silently
    reads whoever runs the suite's real ``config.toml``, so a developer who
    ran ``spec-kitty moments off`` would red every MCP test here. And scope:
    these suites exercise transport/surface *mechanics*, not #190's gating —
    the synthetic event frames they push carry no real mission — so the
    default ``mine`` mode would drop them for reasons no assertion here
    states.

    Tests that DO exercise #190's gating overwrite the yielded file (or pass
    explicit settings) rather than fighting this one; tests that need the
    path to start EMPTY override this fixture by name in their own module."""
    config_path = tmp_path / "kittify-global-config.toml"
    config_path.write_text('[moments]\nagents = "team"\n')
    monkeypatch.setattr(moments, "global_config_path", lambda *, home=None: config_path)
    return config_path


def closed_port_url() -> str:
    """A ``127.0.0.1`` URL with nothing listening — a real connection-refused
    target (N5), without depending on the OS refusing an entirely unused
    high port (which some sandboxes intercept)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return f"http://127.0.0.1:{port}"


# --- Z4-C: a streaming double for GET /managed/stream -----------------------


@dataclass
class ManagedStreamDouble:
    """A minimal, in-process, loopback-only double for F3's
    ``GET /managed/stream`` SSE route (``zeitgeist/managed.py``).

    Unlike :class:`TeamKittyDouble` (one request, one buffered response),
    this double holds the connection open and lets the test push ``data:``
    lines onto it over time via :meth:`push_frame`, using real
    ``Transfer-Encoding: chunked`` framing so ``urllib``'s ``http.client``
    de-chunks it exactly as it would a real server's ``StreamingResponse``.

    It also serves the sibling ``GET /managed/snapshot`` route
    (spec-kitty#4215): ``snapshot_document`` is returned as JSON when set,
    ``snapshot_body`` overrides it with raw bytes for malformed-response
    cases, and otherwise the route answers ``snapshot_status`` (404 by
    default — a relay that does not serve snapshots at all).

    Never a real Docker Zeitgeist container — same discipline as
    ``TeamKittyDouble``'s own docstring; this double never leaves
    ``127.0.0.1`` and models only the wire shape ``filtered_stream`` reads.
    """

    outgoing: queue.Queue[bytes | None] = field(default_factory=queue.Queue)
    received_headers: list[dict[str, str]] = field(default_factory=list)
    response_status: int = 200

    # spec-kitty#4215: `GET /managed/snapshot` (zeitgeist#296) is a SEPARATE
    # route on the same relay, so this double answers it separately too.
    # The default is the honest shape of a relay that does not serve it (an
    # older build, or the `self_hosted` profile): 404, which is exactly what
    # makes every pre-#4215 test here keep exercising the listen path.
    snapshot_document: dict[str, Any] | None = None
    snapshot_status: int = 404
    snapshot_body: bytes | None = None
    requested_paths: list[str] = field(default_factory=list)

    _server: http.server.ThreadingHTTPServer | None = None
    _thread: threading.Thread | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def start(self) -> None:
        handler_cls = self._make_handler()
        self._server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def url(self) -> str:
        assert self._server is not None
        host, port = self._server.server_address[:2]
        return f"http://127.0.0.1:{port}"

    def stop(self) -> None:
        self.close_stream()
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2)

    def push_frame(self, frame: dict[str, Any]) -> None:
        self.outgoing.put(f"data: {json.dumps(frame)}\n\n".encode())

    def push_raw(self, raw: bytes) -> None:
        self.outgoing.put(raw)

    def close_stream(self) -> None:
        """Signal the handler thread to stop writing and let the response
        end — the sentinel is idempotent-safe to send more than once."""
        self.outgoing.put(None)

    def _make_handler(self) -> type[http.server.BaseHTTPRequestHandler]:
        double = self

        class _Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def _write_chunk(self, data: bytes) -> None:
                self.wfile.write(f"{len(data):x}\r\n".encode() + data + b"\r\n")
                self.wfile.flush()

            def _serve_snapshot(self) -> None:
                body = double.snapshot_body
                if body is None and double.snapshot_document is not None:
                    body = json.dumps(double.snapshot_document).encode()
                if body is None:
                    self.send_response(double.snapshot_status)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                # Mirrors the real relay: zeitgeist/managed.py's managed_snapshot
                # attaches the same X-Zeitgeist-Filter-Own ack header
                # (_filter_headers(spec)) to its JSON response, not just to
                # /managed/stream's SSE response.
                self.send_header("X-Zeitgeist-Filter-Own", "true" if "filterOwn=true" in self.path else "false")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:  # noqa: N802
                with double._lock:
                    double.received_headers.append(dict(self.headers))
                    double.requested_paths.append(self.path)
                if self.path.split("?")[0] == "/managed/snapshot":
                    self._serve_snapshot()
                    return
                self.send_response(double.response_status)
                if double.response_status != 200:
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                self.send_header("X-Zeitgeist-Filter-Own", "true" if "filterOwn=true" in self.path else "false")
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                with contextlib.suppress(BrokenPipeError, ConnectionResetError):
                    while True:
                        item = double.outgoing.get()
                        if item is None:
                            break
                        self._write_chunk(item)
                    self.wfile.write(b"0\r\n\r\n")
                    self.wfile.flush()

            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                pass

        return _Handler


@pytest.fixture()
def managed_stream_double() -> Generator[ManagedStreamDouble, None, None]:
    double = ManagedStreamDouble()
    double.start()
    try:
        yield double
    finally:
        double.stop()


# --- FIX-M2-10: a PROTOCOL-FAITHFUL double for POST /managed/control -------
#
# Unlike TeamKittyDouble above (records anything, asserts nothing — the
# double transport.ZeitgeistClient.offer() was silently passing right past
# before this fix), this one actually enforces the two gates a REAL relay
# enforces on this route: `zeitgeist/auth.py`'s outer, unconditional
# `AuthenticationMiddleware` (`Authorization: Bearer <shared_token>`,
# checked first, mirroring `managed.py`'s route order) and `managed.py`'s
# own `X-Zeitgeist-Capability` capability check (`managed_auth.py`'s
# `SharedSecretCapabilityVerifier` wire shape:
# `v1.<b64url(payload_json)>.<hex(hmac_sha256(key, payload))>`, `kind`-scoped
# to presence/focus/operator). It also enforces the same-shape body
# `managed_control.schema.json` requires: `schema_version` ("1.x.y") plus a
# real op dispatch, including "no prior focus.start" rejection.
#
# Deliberately NOT faithful to (out of scope for what offer()'s tests need):
# SSE streaming, presence/focus TTL expiry, the overload ceilings, replay-
# dedup response caching beyond what op-count assertions below check.
#
# Ported from the SAME reasoning as spec-kitty-saas's own
# `apps/live_capability/testing/fake_zeitgeist_server.py` (built for
# FIX-M2-06/07's identical class of gap on the SaaS relay side) — test-only
# code, re-derived rather than imported: zeitgeist and spec-kitty-saas are
# both separate, git-ignored sibling repos with no package dependency to
# spec-kitty in either direction.

import base64 as _base64
import binascii as _binascii
import hashlib as _hashlib
import hmac as _hmac
import re as _re

_SCHEMA_VERSION_RE = _re.compile(r"^1\.[0-9]+\.[0-9]+$")
_FOCUS_OPS = frozenset({"focus.start", "focus.heartbeat", "focus.pause", "focus.end"})
_ALL_MANAGED_OPS = frozenset({"presence.publish", "session.revoke", "event.publish"}) | _FOCUS_OPS
_KIND_CAPS_DOUBLE: dict[str, frozenset[str]] = {
    # `presence` also grants `event.publish` on the real relay
    # (`managed_auth._KIND_CAPS`) — the CLI's fire-and-forget status moment
    # rides the same lease it already holds for presence. Kept in parity
    # here (spec-kitty#30).
    "presence": frozenset({"presence.publish", "event.publish"}),
    "focus": _FOCUS_OPS,
    "operator": frozenset({"session.revoke"}),
}

# FIX-M2-10: field-for-field reproduction of every per-op `args` shape the
# real schemas declare (managed_control.schema.json's FocusArgs/
# FocusEndArgs/SessionRevokeArgs, managed_presence.schema.json's
# PresencePublish) — required keys + the full additionalProperties:false
# allowed set. This is what caught the SECOND wire-shape defect a
# recording-only double structurally cannot (transport.py's
# focus_heartbeat/focus_pause omitted the schema-required `ttl_s`,
# focus_pause sent a `pause_reason` key the schema has no slot for at all,
# and presence() sent `activity` where the wire field is `kind`) — a real
# zeitgeist container 422'd every one of those, silently invisible to a
# double that only checks path/headers/schema_version/op.
_ARGS_SHAPE_DOUBLE: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "presence.publish": (
        frozenset({"session_id"}),
        frozenset({"host", "harness", "session_id", "agent_id", "repo", "branch", "kind", "path", "ts"}),
    ),
    "focus.start": (
        frozenset({"session_id", "repo", "focus_ref", "ttl_s"}),
        frozenset({"session_id", "repo", "branch", "focus_ref", "ttl_s"}),
    ),
    "focus.heartbeat": (
        frozenset({"session_id", "repo", "focus_ref", "ttl_s"}),
        frozenset({"session_id", "repo", "branch", "focus_ref", "ttl_s"}),
    ),
    "focus.pause": (
        frozenset({"session_id", "repo", "focus_ref", "ttl_s"}),
        frozenset({"session_id", "repo", "branch", "focus_ref", "ttl_s"}),
    ),
    "focus.end": (
        frozenset({"session_id", "repo", "focus_ref", "ttl_s", "ended_reason"}),
        frozenset({"session_id", "repo", "branch", "focus_ref", "ttl_s", "ended_reason"}),
    ),
    "session.revoke": (
        frozenset({"session_id", "reason"}),
        frozenset({"session_id", "reason"}),
    ),
    "event.publish": (
        frozenset({"session_id", "kind", "attrs"}),
        frozenset({"session_id", "kind", "ref", "attrs"}),
    ),
}


def _validate_args_shape(op: str, args: dict) -> str | None:
    """``None`` if ``args`` matches ``op``'s real required/allowed key set;
    else a human-readable reason, mirroring the JSON-Schema-validator
    ``err.code at path`` shape ``managed.py``'s own 422 detail uses."""
    required, allowed = _ARGS_SHAPE_DOUBLE.get(op, (frozenset(), frozenset()))
    missing = required - args.keys()
    if missing:
        return f"missing required key(s) {sorted(missing)} at /args"
    extra = args.keys() - allowed
    if extra:
        return f"extra_key {sorted(extra)} at /args (additionalProperties: false)"
    return None


def mint_capability_token(
    key: str,
    *,
    sub: str,
    team: str,
    deployment: str,
    repo: str,
    kind: str,
    iat: float,
    exp: float,
) -> str:
    """The exact wire shape ``managed_auth.SharedSecretCapabilityVerifier``
    verifies — reimplemented here (test-only) so a test can mint a
    protocol-real ``X-Zeitgeist-Capability`` value without importing
    zeitgeist (no dependency exists in either direction)."""
    payload = json.dumps({"sub": sub, "team": team, "deployment": deployment, "repo": repo, "kind": kind, "iat": iat, "exp": exp}).encode("utf-8")
    payload_b64 = _base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")
    # Reproduces the real relay's HMAC capability-token wire shape
    # (managed_auth.SharedSecretCapabilityVerifier) — a body/file-integrity
    # checksum use, not the charter content hash.
    digest = _hashlib.sha256  # noqa: TID251 — non-charter use: reproduces managed_auth's HMAC capability-token wire shape
    sig_hex = _hmac.new(key.encode("utf-8"), payload, digest).hexdigest()
    return f"v1.{payload_b64}.{sig_hex}"


class _FocusNotStartedDouble(Exception):
    pass


@dataclass
class ManagedControlState:
    shared_token: str
    capability_key: str
    lock: threading.Lock = field(default_factory=threading.Lock)
    received_ops: dict[str, int] = field(default_factory=dict)
    applied_ops: dict[str, int] = field(default_factory=dict)
    dedup: dict[tuple, dict] = field(default_factory=dict)
    focus_started: set = field(default_factory=set)
    last_headers: dict[str, str] = field(default_factory=dict)
    last_status: tuple[int, dict[str, Any]] | None = None

    def authorized(self, header_value: str | None) -> bool:
        if not header_value:
            return False
        try:
            scheme, credentials_ = header_value.split(" ", 1)
        except ValueError:
            return False
        return scheme.lower() == "bearer" and _hmac.compare_digest(credentials_, self.shared_token)

    def verify_capability(self, header_value: str | None) -> dict | None:
        if not header_value:
            return None
        parts = header_value.split(".")
        if len(parts) != 3 or parts[0] != "v1":
            return None
        _, payload_b64, sig_hex = parts
        pad = "=" * (-len(payload_b64) % 4)
        try:
            payload_bytes = _base64.urlsafe_b64decode(payload_b64 + pad)
        except (_binascii.Error, ValueError):
            return None
        digest = _hashlib.sha256  # noqa: TID251 — non-charter use: reproduces managed_auth's HMAC capability-token wire shape
        expected = _hmac.new(self.capability_key.encode("utf-8"), payload_bytes, digest).hexdigest()
        if not _hmac.compare_digest(sig_hex, expected):
            return None
        try:
            return json.loads(payload_bytes)
        except json.JSONDecodeError:
            return None


def _apply_managed_op(state: ManagedControlState, op: str, args: dict, scope: tuple) -> None:
    with state.lock:
        if op in _FOCUS_OPS:
            key = (scope, args.get("focus_ref"))
            if op == "focus.start":
                state.focus_started.add(key)
            elif op == "focus.end":
                state.focus_started.discard(key)
            elif key not in state.focus_started:
                raise _FocusNotStartedDouble(op)


def _dispatch_managed_control(state: ManagedControlState, headers: Any, raw: bytes) -> tuple[int, dict]:
    """The whole ``POST /managed/control`` decision tree, isolated from
    ``http.server`` plumbing so it stays one small, directly-testable
    function rather than living inside a handler method."""
    with state.lock:
        state.last_headers = dict(headers.items())

    # FIX-M2-10 / FIX-M2-06 precedent: the OUTER gate, checked first —
    # exactly AuthenticationMiddleware's position ahead of managed.py's own
    # body parsing.
    if not state.authorized(headers.get("Authorization")):
        return 401, {"detail": "authentication required"}

    try:
        body = json.loads(raw)
    except json.JSONDecodeError:
        return 422, {"detail": "malformed json"}

    schema_version = body.get("schema_version")
    if not isinstance(schema_version, str) or not _SCHEMA_VERSION_RE.match(schema_version):
        return 422, {"detail": "schema_version required at /schema_version"}

    op = body.get("op")
    request_id = body.get("request_id")
    args = body.get("args") or {}

    if op not in _ALL_MANAGED_OPS:
        return 422, {"detail": f"unknown op {op!r}"}

    args_shape_error = _validate_args_shape(op, args)
    if args_shape_error is not None:
        return 422, {"detail": args_shape_error}

    identity = state.verify_capability(headers.get("X-Zeitgeist-Capability"))
    if identity is None:
        return 403, {"detail": "capability credential invalid or expired"}
    if op not in _KIND_CAPS_DOUBLE.get(identity.get("kind"), frozenset()):
        return 403, {"detail": f"capability does not grant op {op}"}

    scope = (identity.get("team"), identity.get("deployment"), identity.get("repo"))
    with state.lock:
        state.received_ops[op] = state.received_ops.get(op, 0) + 1
        cached = state.dedup.get((scope, request_id))
        if cached is not None:
            return 202, cached

    try:
        _apply_managed_op(state, op, args, scope)
    except _FocusNotStartedDouble:
        return 404, {"detail": "no focus session started; call focus.start first"}

    response = {"request_id": request_id, "received_at": now_epoch()}
    with state.lock:
        state.applied_ops[op] = state.applied_ops.get(op, 0) + 1
        state.dedup[(scope, request_id)] = response
    return 202, response


@dataclass
class ManagedControlDouble:
    """Public test-support handle: start/stop the double, configure its two
    secrets, and inspect what op counts it actually applied."""

    shared_token: str = "test-shared-token"
    capability_key: str = "test-capability-key"

    _server: http.server.ThreadingHTTPServer | None = None
    _thread: threading.Thread | None = None
    _state: ManagedControlState | None = None

    def start(self) -> None:
        self._state = ManagedControlState(shared_token=self.shared_token, capability_key=self.capability_key)
        handler_cls = self._make_handler()
        self._server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def url(self) -> str:
        assert self._server is not None
        host, port = self._server.server_address[:2]
        return f"http://127.0.0.1:{port}"

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2)

    def applied_op_count(self, op: str) -> int:
        assert self._state is not None
        with self._state.lock:
            return self._state.applied_ops.get(op, 0)

    def received_op_count(self, op: str) -> int:
        assert self._state is not None
        with self._state.lock:
            return self._state.received_ops.get(op, 0)

    def last_request_headers(self) -> dict[str, str]:
        assert self._state is not None
        with self._state.lock:
            return dict(self._state.last_headers)

    def last_response_status(self) -> tuple[int, dict[str, Any]] | None:
        """The raw HTTP status and JSON payload of the most recently answered POST.

        ``offer()``/``OfferResult`` collapse every non-2xx into
        ``OfferOutcome.REJECTED`` (#352), so a test that must distinguish
        *why* a request was rejected (e.g. 422 unknown-op vs. 403
        kind-does-not-grant-op) needs to look past the client's outcome
        enum at what the double actually answered.
        """
        assert self._state is not None
        with self._state.lock:
            response = self._state.last_status
            return None if response is None else (response[0], dict(response[1]))

    def set_shared_token(self, value: str) -> None:
        """Reconfigure the ``Authorization: Bearer`` secret the running
        double checks, after ``start()`` — lets one test build several
        differently-kinded/credentialed clients against the same shared
        secret each expects, without tearing the server down."""
        assert self._state is not None
        with self._state.lock:
            self._state.shared_token = value
        self.shared_token = value

    def _make_handler(self) -> type[http.server.BaseHTTPRequestHandler]:
        double = self

        class _Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                pass

            def _send_json(self, status: int, payload: dict) -> None:
                body = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self) -> None:  # noqa: N802
                state = double._state
                assert state is not None
                if self.path != "/managed/control":
                    status, payload = 404, {"detail": "not found"}
                else:
                    length = int(self.headers.get("Content-Length", "0") or "0")
                    raw = self.rfile.read(length) if length else b"{}"
                    status, payload = _dispatch_managed_control(state, self.headers, raw)
                with state.lock:
                    state.last_status = status, dict(payload)
                self._send_json(status, payload)

        return _Handler


@pytest.fixture()
def managed_control_double() -> Generator[ManagedControlDouble, None, None]:
    double = ManagedControlDouble()
    double.start()
    try:
        yield double
    finally:
        double.stop()


# --- FIX-M2-13: a PROTOCOL-FAITHFUL double for GET /managed/stream --------
#
# Unlike ManagedStreamDouble above (records anything, gates nothing — the
# double filtered_stream.FilteredStream.watch() was silently passing right
# past before this fix), this one enforces the SAME two gates a REAL relay
# enforces on this route, in the SAME order `managed.py`/`auth.py` check
# them: `zeitgeist/auth.py`'s outer, unconditional `AuthenticationMiddleware`
# (`Authorization: Bearer <shared_token>`, checked first — every route but
# `/health`) and `managed.py`'s own `_extract_identity()` capability check
# (`X-Zeitgeist-Capability`, `managed_auth.py`'s HMAC verification; missing
# -> 401, malformed/wrong-signature/expired -> 403, exactly the same
# 401-vs-403 split `_extract_identity` itself codes). A request that reaches
# a real frame here would genuinely reach one against a real relay too, and
# one that is denied here for the wrong reason (401/403) would be genuinely
# denied by one too.
#
# Reuses ManagedControlState's authorized()/verify_capability() — both are
# pure header checks, agnostic to GET vs POST — rather than re-deriving a
# second HMAC-verification implementation for this route (same "cite, don't
# re-derive" discipline mint_capability_token above already established).
# `/managed/stream`'s own `_extract_identity(request)` call passes no
# `needs_op`, so unlike ManagedControlDouble's op-vs-kind check, ANY
# validly-signed capability (presence | focus | operator) admits a stream
# connection here — reproduced by simply never checking `identity["kind"]`
# below.


@dataclass
class ManagedStreamAuthDouble:
    """Public test-support handle: start/stop the double, configure its two
    secrets, push frames once a connection is admitted, and inspect what
    headers the most recent request carried."""

    shared_token: str = "test-shared-token"
    capability_key: str = "test-capability-key"

    outgoing: queue.Queue[bytes | None] = field(default_factory=queue.Queue)
    received_headers: list[dict[str, str]] = field(default_factory=list)
    denied_statuses: list[int] = field(default_factory=list)

    _server: http.server.ThreadingHTTPServer | None = None
    _thread: threading.Thread | None = None
    _state: ManagedControlState | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def start(self) -> None:
        self._state = ManagedControlState(shared_token=self.shared_token, capability_key=self.capability_key)
        handler_cls = self._make_handler()
        self._server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def url(self) -> str:
        assert self._server is not None
        host, port = self._server.server_address[:2]
        return f"http://127.0.0.1:{port}"

    def stop(self) -> None:
        self.close_stream()
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2)

    def push_frame(self, frame: dict[str, Any]) -> None:
        self.outgoing.put(f"data: {json.dumps(frame)}\n\n".encode())

    def close_stream(self) -> None:
        """Signal the handler thread to stop writing and let the response
        end — the sentinel is idempotent-safe to send more than once."""
        self.outgoing.put(None)

    def set_shared_token(self, value: str) -> None:
        assert self._state is not None
        with self._state.lock:
            self._state.shared_token = value
        self.shared_token = value

    def _make_handler(self) -> type[http.server.BaseHTTPRequestHandler]:
        double = self

        class _Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                pass

            def _deny(self, status: int, detail: str) -> None:
                # Record the denial BEFORE writing any byte of the response.
                # The client thread's urllib call can only observe a
                # response once send_response()/wfile.write() have run, so
                # appending first makes this append happen-before the
                # client-side HTTPError a caller catches immediately after
                # — closing the cross-thread race where a test could read
                # `denied_statuses` while this handler thread had sent the
                # response but not yet appended (see FIX-M2-13 rework).
                with double._lock:
                    double.denied_statuses.append(status)
                body = json.dumps({"detail": detail}).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                with contextlib.suppress(BrokenPipeError, ConnectionResetError):
                    self.wfile.write(body)

            def _write_chunk(self, data: bytes) -> None:
                self.wfile.write(f"{len(data):x}\r\n".encode() + data + b"\r\n")
                self.wfile.flush()

            def do_GET(self) -> None:  # noqa: N802
                state = double._state
                assert state is not None
                with double._lock:
                    double.received_headers.append(dict(self.headers))

                if self.path.split("?", 1)[0] != "/managed/stream":
                    self._deny(404, "not found")
                    return

                # Outer gate first — exactly AuthenticationMiddleware's
                # position ahead of managed.py's own handler.
                if not state.authorized(self.headers.get("Authorization")):
                    self._deny(401, "authentication required")
                    return

                # managed.py's own _extract_identity(): missing capability
                # header -> 401, malformed/wrong-signature/expired -> 403 —
                # the same split _extract_identity itself codes.
                cap_header = self.headers.get("X-Zeitgeist-Capability")
                if not cap_header:
                    self._deny(401, "managed capability credential required")
                    return
                identity = state.verify_capability(cap_header)
                if identity is None:
                    self._deny(403, "capability credential invalid or expired")
                    return

                self.send_response(200)
                self.send_header("X-Zeitgeist-Filter-Own", "true" if "filterOwn=true" in self.path else "false")
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                with contextlib.suppress(BrokenPipeError, ConnectionResetError):
                    while True:
                        item = double.outgoing.get()
                        if item is None:
                            break
                        self._write_chunk(item)
                    self.wfile.write(b"0\r\n\r\n")
                    self.wfile.flush()

        return _Handler


@pytest.fixture()
def managed_stream_auth_double() -> Generator[ManagedStreamAuthDouble, None, None]:
    double = ManagedStreamAuthDouble()
    double.start()
    try:
        yield double
    finally:
        double.stop()
