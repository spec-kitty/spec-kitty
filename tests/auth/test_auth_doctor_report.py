"""Tests for the read-only ``spec-kitty auth doctor`` report (WP06 / T028).

Covers the contract surface in ``contracts/auth-doctor.md``:
section rendering, finding triggers, exit-code policy, the legacy
session string, the NFR-006 wall-clock ceiling, and JSON schema shape.
The daemon/orphan sections were removed together with the sync transport
(issue #5); the surviving report has 5 sections and schema_version 3.

Also covers the ``--server`` flag (WP04 / T019):
- ServerSessionStatus dataclass construction
- _check_server_session() async function (200, 401, network error)
- doctor_impl server=False makes no outbound calls
- doctor_impl server=True renders active/re-authenticate output
- a failed server check is an F-008 critical finding and exits 1 even when
  the local session is healthy (#4607)

And the issuer/server mismatch guard (issue #253): ``--server`` must never
attempt a refresh — and thereby clear the session — when the stored
session's ``issuer_url`` names a server other than the one currently
resolved.

All tests use ``monkeypatch`` to inject deterministic state for
``assemble_report``'s upstream dependencies — no SaaS, no network.
"""

from __future__ import annotations

import io
import json
import time
from dataclasses import replace
from kernel.clock import datetime, now_utc, parse_iso, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import typer
from rich.console import Console

from specify_cli.auth.server_target import OverrideMode, ResolvedServerTarget, SAAS_URL_ENV_VAR
from specify_cli.auth.session import StoredSession, Team
from specify_cli.auth.token_manager import SessionAssessment
from specify_cli.cli.commands import _auth_doctor
from specify_cli.cli.commands import auth as auth_commands
from specify_cli.cli.commands._auth_doctor import (
    DoctorReport,
    ServerSessionStatus,
    _check_server_session,
    _server_issuer_mismatch_error,
    assemble_report,
    compute_exit_code,
    doctor_impl,
    render_report,
    render_report_json,
)
from kernel.locks import LockRecord
from tests._perf_helpers import assert_timing_budget

pytestmark = pytest.mark.fast


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session(
    *,
    refresh_token_expires_at: datetime | None,
    auth_method: str = "authorization_code",
) -> StoredSession:
    now = now_utc()
    return StoredSession(
        user_id="user-abc",
        email="rob@example.com",
        name="Rob",
        teams=[Team(id="t1", name="Personal", role="owner", is_private_teamspace=True)],
        default_team_id="t1",
        access_token="access-xyz",
        refresh_token="refresh-xyz",
        session_id="session-xyz",
        issued_at=now,
        access_token_expires_at=now + timedelta(minutes=15),
        refresh_token_expires_at=refresh_token_expires_at,
        scope="openid",
        storage_backend="file",
        last_used_at=now,
        auth_method=auth_method,
    )


class _FakeStorage:
    def __init__(self, session: StoredSession | None) -> None:
        self._session = session

    def read(self) -> StoredSession | None:
        return self._session

    def write(self, session: StoredSession) -> None:
        self._session = session


class _FakeTokenManager:
    """Test double for :class:`TokenManager` matching the public API used here."""

    def __init__(
        self,
        session: StoredSession | None,
        assessment: SessionAssessment | None = None,
    ) -> None:
        self._session = session
        self._storage = _FakeStorage(session)
        self.session_assessment = assessment

    def get_current_session(self) -> StoredSession | None:
        return self._session


def _patch_state(
    monkeypatch: pytest.MonkeyPatch,
    *,
    session: StoredSession | None,
    lock_record: LockRecord | None = None,
    auth_root: Path | None = None,
    assessment: SessionAssessment | None = None,
) -> None:
    """Wire ``_auth_doctor``'s upstream calls to deterministic fakes."""
    monkeypatch.setattr(
        _auth_doctor,
        "get_token_manager",
        lambda: _FakeTokenManager(session, assessment),
    )
    monkeypatch.setattr(_auth_doctor, "read_lock_record", lambda _path: lock_record)
    if auth_root is None:
        auth_root = Path("/nonexistent/spec-kitty-doctor-test/auth/refresh.lock")
    monkeypatch.setattr(_auth_doctor, "_refresh_lock_path", lambda: auth_root)


def _capture_render(report: DoctorReport) -> str:
    """Render the report to a string by feeding Rich into a StringIO."""
    buf = io.StringIO()
    console = Console(file=buf, width=120, record=False, force_terminal=False)
    render_report(report, console)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_renders_machine_session_auth_method(monkeypatch: pytest.MonkeyPatch) -> None:
    """#3277: a ``client_credentials`` session renders its auth mode, no secrets."""
    session = _make_session(
        refresh_token_expires_at=now_utc() + timedelta(days=30),
        auth_method="client_credentials",
    )
    _patch_state(monkeypatch, session=session)

    report = assemble_report()
    assert report.session is not None
    assert report.session.auth_method == "client_credentials"

    rendered = _capture_render(report)
    assert "Machine / CI (Client Credentials Grant)" in rendered
    # Diagnostics never carry credential material.
    assert "access-xyz" not in rendered
    assert "refresh-xyz" not in rendered


def test_renders_authenticated_no_findings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Healthy state renders all sections with a confirmed ``ok`` verdict."""
    session = _make_session(refresh_token_expires_at=now_utc() + timedelta(days=30))
    _patch_state(monkeypatch, session=session)

    report = assemble_report()

    assert report.session is not None
    assert report.session.present is True
    assert report.findings == []
    assert compute_exit_code(report.findings) == 0

    assert report.auth_verdict.state == "ok"
    assert report.auth_verdict.evidence
    assert not any(f.id == "F-008" for f in report.findings)

    rendered = _capture_render(report)
    for section in (
        "Identity",
        "Tokens",
        "Storage",
        "Refresh Lock",
        "Findings",
    ):
        assert section in rendered, f"section {section!r} missing from rendered output"
    assert "No problems detected." in rendered


def test_hostile_session_display_values_render_literally(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Session-file strings must not be interpreted as Rich markup (#737)."""
    session = _make_session(refresh_token_expires_at=now_utc() + timedelta(days=30))
    _patch_state(monkeypatch, session=session)
    report = assemble_report()
    assert report.session is not None
    report = replace(
        report,
        session=replace(
            report.session,
            user_email="user[/]example.test",
            session_id="session[/]id",
            storage_backend="file[/]backend",
        ),
    )

    rendered = _capture_render(report)

    assert "user[/]example.test" in rendered
    assert "session[/]id" in rendered
    assert "Unknown (file[/]backend)" in rendered


def test_doctor_impl_strips_terminal_controls_from_emitted_identity_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The live doctor renderer never writes SaaS control sequences (#700)."""
    safe_identity = "Zoë Ölafsdóttir 日本語 🐱"
    hostile_suffix = "\x1b[2J\x1b]0;x\x07\x1b"
    session = _make_session(refresh_token_expires_at=now_utc() + timedelta(days=30))
    session.email = f"{safe_identity}{hostile_suffix}"
    session.session_id = f"session{hostile_suffix}"
    _patch_state(monkeypatch, session=session)
    buf = io.StringIO()
    monkeypatch.setattr(
        _auth_doctor,
        "console",
        Console(file=buf, width=120, record=False, force_terminal=False),
    )

    exit_code = doctor_impl(json_output=False, unstick_lock=False, stuck_threshold=60.0)

    emitted = buf.getvalue().encode("utf-8")
    assert exit_code == 0
    assert safe_identity.encode("utf-8") in emitted
    assert b"\x1b" not in emitted
    assert b"[2J" not in emitted
    assert b"]0;x" not in emitted


def test_doctor_shell_strips_terminal_controls_from_unexpected_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The auth shell keeps unexpected backend error text terminal-safe (#700)."""
    buf = io.StringIO()
    monkeypatch.setattr(
        auth_commands,
        "console",
        Console(file=buf, width=120, record=False, force_terminal=False),
    )

    def _raise_unexpected_error(**_kwargs: object) -> int:
        raise RuntimeError("Zoë Ölafsdóttir 日本語 🐱\x1b[2J\x1b]0;x\x07\x1b")

    monkeypatch.setattr(_auth_doctor, "doctor_impl", _raise_unexpected_error)

    with pytest.raises(typer.Exit) as raised:
        auth_commands.doctor(
            json_output=False,
            unstick_lock=False,
            stuck_threshold=60.0,
            server=False,
        )

    emitted = buf.getvalue().encode("utf-8")
    assert raised.value.exit_code == 2
    assert "Zoë Ölafsdóttir 日本語 🐱".encode() in emitted
    assert b"\x1b" not in emitted


def test_expired_access_valid_refresh_local_is_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An expired access token with an unproven refresh chain is unknown."""
    session = _make_session(refresh_token_expires_at=now_utc() + timedelta(days=30))
    session = replace(session, access_token_expires_at=now_utc() - timedelta(minutes=1))
    _patch_state(monkeypatch, session=session)

    report = assemble_report()

    assert report.auth_verdict.state == "unknown"
    assert any(f.id == "F-008" for f in report.findings)
    assert any("expired" in f.summary.lower() for f in report.findings)

    rendered = _capture_render(report)
    assert "No problems detected" not in rendered
    assert "F-008" in rendered


def test_expired_access_and_refresh_yields_critical_finding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Expired access and refresh tokens produce a critical F-008 finding."""
    session = _make_session(refresh_token_expires_at=now_utc() - timedelta(days=1))
    session = replace(session, access_token_expires_at=now_utc() - timedelta(minutes=1))
    _patch_state(monkeypatch, session=session)

    report = assemble_report()

    assert report.auth_verdict.state == "fail"
    f008 = next(f for f in report.findings if f.id == "F-008")
    assert f008.severity == "critical"
    assert "expired" in f008.summary.lower()
    assert f008.remediation_command == "spec-kitty auth login"
    assert compute_exit_code(report.findings) == 1

    rendered = _capture_render(report)
    assert "No problems detected" not in rendered


def test_expired_access_valid_refresh_with_live_server_probe_is_ok(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A live server probe resolves an expired access token to ``ok``."""
    session = _make_session(refresh_token_expires_at=now_utc() + timedelta(days=30))
    session = replace(session, access_token_expires_at=now_utc() - timedelta(minutes=1))
    _patch_state(monkeypatch, session=session)

    report = assemble_report(server_probe=ServerSessionStatus(active=True, session_id="s1"))

    assert report.auth_verdict.state == "ok"
    assert not any(f.id == "F-008" for f in report.findings)


def test_renders_unauthenticated(monkeypatch: pytest.MonkeyPatch) -> None:
    """No session ⇒ F-001 critical; exit 1."""
    _patch_state(monkeypatch, session=None)

    report = assemble_report()

    assert report.session is None
    assert any(f.id == "F-001" and f.severity == "critical" for f in report.findings)
    assert compute_exit_code(report.findings) == 1

    rendered = _capture_render(report)
    assert "Not authenticated" in rendered
    assert "F-001" in rendered


_PERMISSIONS_DETAIL = (
    "Session file /home/u/.spec-kitty/auth/session.json has unsafe "
    "permissions (mode=0o644); expected 0600. Fix with: chmod 600 "
    "/home/u/.spec-kitty/auth/session.json"
)


def test_renders_storage_permission_refusal_not_no_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#4761: a storage refusal must not be misdiagnosed as "no session".

    F-001 stays critical (action required) but its summary names the storage
    layer's own chmod remedy, the identity section says storage refused, and
    the auth-login remediation is withheld — a re-login would overwrite the
    very file storage refused to read.
    """
    _patch_state(
        monkeypatch,
        session=None,
        assessment=SessionAssessment(
            completed=False,
            usable_session=None,
            reason="storage_permissions_unsafe",
            detail=_PERMISSIONS_DETAIL,
        ),
    )

    report = assemble_report()

    assert report.session is None
    f001 = next(f for f in report.findings if f.id == "F-001")
    assert f001.severity == "critical"
    assert "unsafe permissions" in f001.summary
    assert "chmod 600" in f001.summary
    assert f001.remediation_command is None
    assert compute_exit_code(report.findings) == 1

    rendered = _capture_render(report)
    assert "session storage refused" in rendered
    assert "chmod 600" in rendered
    assert "(session unreadable — storage refused to load it)" in rendered
    assert "spec-kitty auth login" not in rendered


def test_renders_stuck_lock_finding(monkeypatch: pytest.MonkeyPatch) -> None:
    """Lock record 120 s old ⇒ F-003 critical; exit 1."""
    session = _make_session(refresh_token_expires_at=now_utc() + timedelta(days=30))
    # Force the holder_host to match local socket so F-007 doesn't fire.
    import socket

    lock = LockRecord(
        schema_version=1,
        pid=99999,
        started_at=now_utc() - timedelta(seconds=120),
        host=socket.gethostname(),
        version="3.2.0a5",
    )
    _patch_state(monkeypatch, session=session, lock_record=lock)

    report = assemble_report(stuck_threshold_s=60.0)

    assert any(f.id == "F-003" and f.severity == "critical" for f in report.findings)
    assert compute_exit_code(report.findings) == 1


def test_renders_legacy_session(monkeypatch: pytest.MonkeyPatch) -> None:
    """``refresh_token_expires_at is None`` ⇒ "server-managed (legacy)" line; no extra finding."""
    session = _make_session(refresh_token_expires_at=None)
    _patch_state(monkeypatch, session=session)

    report = assemble_report()
    rendered = _capture_render(report)

    assert "server-managed (legacy)" in rendered
    # No F-001 or other critical finding for a legacy session.
    assert all(f.severity != "critical" for f in report.findings)


def test_runs_under_three_seconds(monkeypatch: pytest.MonkeyPatch) -> None:
    """Healthy state ⇒ ``assemble_report`` reports no findings (NFR-006, functional half).

    Split from the original NFR-006 test (#4015): the wall-clock ceiling now
    lives in ``test_assemble_report_stays_under_the_nfr_006_ceiling``
    (``@pytest.mark.performance``, nightly-only); this test keeps the
    functional assertion on the per-PR path.
    """
    session = _make_session(refresh_token_expires_at=now_utc() + timedelta(days=30))
    _patch_state(monkeypatch, session=session)

    report = assemble_report()

    assert report.findings == []


@pytest.mark.performance
def test_assemble_report_stays_under_the_nfr_006_ceiling(monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-006: ``assemble_report`` wall-clock stays under the 3 s ceiling (nightly).

    Split from ``test_runs_under_three_seconds`` (#4015); budget preserved.
    The default path reads only local files, so the whole pipeline runs
    well inside the ceiling without any simulated scan delay.
    """
    session = _make_session(refresh_token_expires_at=now_utc() + timedelta(days=30))
    _patch_state(monkeypatch, session=session)

    started = time.monotonic()
    assemble_report()
    elapsed = time.monotonic() - started

    assert_timing_budget(elapsed, 3.0, name="assemble_report")


def test_renders_held_fresh_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fresh held lock ⇒ section renders holder PID, age, host; no F-003."""
    import socket

    session = _make_session(refresh_token_expires_at=now_utc() + timedelta(days=30))
    lock = LockRecord(
        schema_version=1,
        pid=42,
        started_at=now_utc() - timedelta(seconds=2),
        host=socket.gethostname(),
        version="3.2.0a5",
    )
    _patch_state(monkeypatch, session=session, lock_record=lock)

    report = assemble_report()
    rendered = _capture_render(report)

    assert "Held by PID:" in rendered
    assert "42" in rendered
    # Fresh lock ⇒ no F-003
    assert all(f.id != "F-003" for f in report.findings)


def test_nfs_holder_finding(monkeypatch: pytest.MonkeyPatch) -> None:
    """F-007 fires when the lock holder host differs from the local hostname."""
    session = _make_session(refresh_token_expires_at=now_utc() + timedelta(days=30))
    lock = LockRecord(
        schema_version=1,
        pid=42,
        started_at=now_utc() - timedelta(seconds=2),
        host="some-other-host.example.com",
        version="3.2.0a5",
    )
    _patch_state(monkeypatch, session=session, lock_record=lock)

    report = assemble_report()

    assert any(f.id == "F-007" and f.severity == "warn" for f in report.findings)


def test_json_output_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    """``--json`` payload validates against ``data-model.md`` §5 schema."""
    session = _make_session(refresh_token_expires_at=now_utc() + timedelta(days=30))
    _patch_state(monkeypatch, session=session)

    report = assemble_report()
    payload = json.loads(render_report_json(report))

    # Top-level keys. v3 dropped the retired `daemon` / `orphans` sections.
    for key in (
        "schema_version",
        "generated_at",
        "auth_root",
        "session",
        "refresh_lock",
        "findings",
    ):
        assert key in payload
    assert "daemon" not in payload
    assert "orphans" not in payload

    # v3: sync-daemon diagnostics removed from the payload (issue #5).
    assert payload["schema_version"] == 3
    # ISO-8601 datetime
    parse_iso(payload["generated_at"])
    # auth_root is a string path
    assert isinstance(payload["auth_root"], str)

    # Session payload shape.
    session_payload = payload["session"]
    for key in (
        "present",
        "session_id",
        "user_email",
        "access_token_remaining_s",
        "refresh_token_remaining_s",
        "storage_backend",
        "in_memory_drift",
        # #3277: the auth mode is part of the diagnostics contract.
        "auth_method",
    ):
        assert key in session_payload
    assert session_payload["auth_method"] == "authorization_code"

    # Refresh-lock payload shape.
    lock_payload = payload["refresh_lock"]
    for key in (
        "held",
        "holder_pid",
        "started_at",
        "age_s",
        "stuck",
        "stuck_threshold_s",
    ):
        assert key in lock_payload

    # Findings list (empty in healthy state).
    assert payload["findings"] == []


# ---------------------------------------------------------------------------
# T019: ServerSessionStatus dataclass
# ---------------------------------------------------------------------------


def test_server_session_status_active() -> None:
    """ServerSessionStatus(active=True, session_id='abc') constructs without error."""
    s = ServerSessionStatus(active=True, session_id="abc")
    assert s.active is True
    assert s.session_id == "abc"
    assert s.error is None


def test_server_session_status_inactive() -> None:
    """ServerSessionStatus(active=False, error='re-authenticate') constructs without error."""
    s = ServerSessionStatus(active=False, error="re-authenticate")
    assert s.active is False
    assert s.session_id is None
    assert s.error == "re-authenticate"


def test_server_session_status_frozen() -> None:
    """ServerSessionStatus is frozen — mutation raises FrozenInstanceError."""
    import dataclasses

    s = ServerSessionStatus(active=True, session_id="abc")
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.active = False  # type: ignore[misc]  # frozen dataclass: deliberate mutation asserts FrozenInstanceError


# ---------------------------------------------------------------------------
# T019: _check_server_session async tests
# ---------------------------------------------------------------------------


async def test_check_server_session_active(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /api/v1/session-status 200 → ServerSessionStatus(active=True, session_id='abc')."""
    mock_tm = AsyncMock()
    mock_tm.get_access_token = AsyncMock(return_value="tok")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"session_id": "abc", "status": "active"}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_response)

    # _check_server_session imports get_token_manager locally from specify_cli.auth
    import specify_cli.auth as _auth_module

    monkeypatch.setattr(_auth_module, "get_token_manager", lambda: mock_tm)

    with (
        patch.object(
            _auth_doctor,
            "resolve_server_target",
            lambda **_kwargs: _fake_target("https://saas.example.com"),
        ),
        patch("httpx.AsyncClient", return_value=mock_client),
    ):
        result = await _check_server_session()

    assert result.active is True
    assert result.session_id == "abc"
    assert result.error is None


async def test_check_server_session_resolves_target_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """Issuer diagnostics and the send share one target resolution (#762)."""
    mock_tm = AsyncMock()
    mock_tm.get_access_token = AsyncMock(return_value="tok")
    session = _make_session(refresh_token_expires_at=now_utc() + timedelta(days=30))
    session.issuer_url = "https://saas.example.com"
    mock_response = MagicMock(status_code=200)
    mock_response.json.return_value = {"active": True, "session_id": "abc"}
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_response)
    import specify_cli.auth as _auth_module

    monkeypatch.setattr(_auth_module, "get_token_manager", lambda: mock_tm)
    mock_tm.get_current_session = MagicMock(return_value=session)
    resolutions = 0

    def resolve_once(**_kwargs: object) -> object:
        nonlocal resolutions
        resolutions += 1
        return _fake_target("https://saas.example.com")

    with patch.object(_auth_doctor, "resolve_server_target", resolve_once), patch("httpx.AsyncClient", return_value=mock_client):
        result = await _check_server_session()

    assert result.active is True
    assert resolutions == 1


async def test_check_server_session_401(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /api/v1/session-status 401 → ServerSessionStatus(active=False, error='re-authenticate')."""
    mock_tm = AsyncMock()
    mock_tm.get_access_token = AsyncMock(return_value="tok")

    mock_response = MagicMock()
    mock_response.status_code = 401

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_response)

    import specify_cli.auth as _auth_module

    monkeypatch.setattr(_auth_module, "get_token_manager", lambda: mock_tm)

    with (
        patch.object(
            _auth_doctor,
            "resolve_server_target",
            lambda **_kwargs: _fake_target("https://saas.example.com"),
        ),
        patch("httpx.AsyncClient", return_value=mock_client),
    ):
        result = await _check_server_session()

    assert result.active is False
    assert result.error == "re-authenticate"
    # The error must not contain any token content.
    assert "tok" not in (result.error or "")


async def test_check_server_session_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Network error → ServerSessionStatus(active=False, error contains type name)."""
    import httpx

    mock_tm = AsyncMock()
    mock_tm.get_access_token = AsyncMock(return_value="tok")

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("connection refused"))

    import specify_cli.auth as _auth_module

    monkeypatch.setattr(_auth_module, "get_token_manager", lambda: mock_tm)

    with (
        patch.object(
            _auth_doctor,
            "resolve_server_target",
            lambda **_kwargs: _fake_target("https://saas.example.com"),
        ),
        patch("httpx.AsyncClient", return_value=mock_client),
    ):
        result = await _check_server_session()

    assert result.active is False
    assert result.error is not None
    assert "ConnectError" in result.error
    # Access token must not appear in the error.
    assert "tok" not in result.error


async def test_check_server_session_split_brain_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An ambiguous env/config target is reported without making the send."""
    home = tmp_path / "split-brain-home"
    home.mkdir()
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home))
    (home / "config.toml").write_text('[sync]\nserver_url = "https://configured.example.com"\n', encoding="utf-8")
    monkeypatch.setenv(SAAS_URL_ENV_VAR, "https://env-override.example.com")

    session = _make_session(refresh_token_expires_at=now_utc() + timedelta(days=30))
    assert session.issuer_url is None

    class _TmWithAccessToken:
        def get_current_session(self) -> StoredSession:
            return session

        async def get_access_token(self) -> str:
            return "tok"

    import specify_cli.auth as _auth_module

    monkeypatch.setattr(_auth_module, "get_token_manager", lambda: _TmWithAccessToken())

    with patch(
        "httpx.AsyncClient",
        side_effect=AssertionError("the bearer-token send must fail closed"),
    ):
        result = await _check_server_session()

    assert result.active is False
    assert result.error is not None
    assert result.error.startswith("SaaS URL mismatch:")
    assert "configured.example.com" in result.error
    assert "env-override.example.com" in result.error
    assert SAAS_URL_ENV_VAR in result.error
    assert "tok" not in result.error


@pytest.mark.asyncio
async def test_check_server_session_refresh_expired(monkeypatch: pytest.MonkeyPatch) -> None:
    """RefreshTokenExpiredError → user-friendly re-authenticate error, not class name."""
    from specify_cli.auth.errors import RefreshTokenExpiredError

    mock_tm = AsyncMock()
    mock_tm.get_access_token = AsyncMock(side_effect=RefreshTokenExpiredError("expired"))

    import specify_cli.auth as _auth_module

    monkeypatch.setattr(_auth_module, "get_token_manager", lambda: mock_tm)
    monkeypatch.setattr(
        _auth_doctor,
        "resolve_server_target",
        lambda **_kwargs: _fake_target("https://saas.example.com"),
    )

    result = await _check_server_session()

    assert result.active is False
    assert result.error is not None
    assert "re-authenticate" in result.error
    # Must NOT expose the class name as raw diagnostic output.
    assert "RefreshTokenExpiredError" not in result.error


@pytest.mark.asyncio
async def test_check_server_session_refresh_lock_timeout_uses_safe_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RefreshLockTimeoutError → safe recovery text, not an implementation class name."""
    from specify_cli.auth.refresh_transaction import RefreshLockTimeoutError

    mock_tm = AsyncMock()
    mock_tm.get_access_token = AsyncMock(
        side_effect=RefreshLockTimeoutError("Refresh token replay detected and no newer local token is available. Run `spec-kitty auth login` if this persists.")
    )

    import specify_cli.auth as _auth_module

    monkeypatch.setattr(_auth_module, "get_token_manager", lambda: mock_tm)
    monkeypatch.setattr(
        _auth_doctor,
        "resolve_server_target",
        lambda **_kwargs: _fake_target("https://saas.example.com"),
    )

    result = await _check_server_session()

    assert result.active is False
    assert result.error is not None
    assert "replay detected" in result.error
    assert "RefreshLockTimeoutError" not in result.error


@pytest.mark.asyncio
async def test_check_server_session_session_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    """SessionInvalidError → user-friendly re-authenticate error, not class name."""
    from specify_cli.auth.errors import SessionInvalidError

    mock_tm = AsyncMock()
    mock_tm.get_access_token = AsyncMock(side_effect=SessionInvalidError("invalidated"))

    import specify_cli.auth as _auth_module

    monkeypatch.setattr(_auth_module, "get_token_manager", lambda: mock_tm)
    monkeypatch.setattr(
        _auth_doctor,
        "resolve_server_target",
        lambda **_kwargs: _fake_target("https://saas.example.com"),
    )

    result = await _check_server_session()

    assert result.active is False
    assert result.error is not None
    assert "re-authenticate" in result.error
    assert "SessionInvalidError" not in result.error


@pytest.mark.asyncio
async def test_check_server_session_generic_access_token_failure_no_class_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unexpected access-token failures should stay non-sensitive and user-safe."""
    mock_tm = AsyncMock()
    mock_tm.get_access_token = AsyncMock(side_effect=RuntimeError("boom"))

    import specify_cli.auth as _auth_module

    monkeypatch.setattr(_auth_module, "get_token_manager", lambda: mock_tm)
    monkeypatch.setattr(
        _auth_doctor,
        "resolve_server_target",
        lambda **_kwargs: _fake_target("https://saas.example.com"),
    )

    result = await _check_server_session()

    assert result.active is False
    assert result.error == "Could not obtain access token."
    assert "RuntimeError" not in result.error


# ---------------------------------------------------------------------------
# Issue #253: --server must not refresh (and thereby clear) a session minted
# by a different server than the one currently resolved.
# ---------------------------------------------------------------------------


class _FakeTokenManagerWithSession:
    """Test double exposing only the two methods ``_check_server_session`` uses."""

    def __init__(self, session: StoredSession | None) -> None:
        self._session = session

    def get_current_session(self) -> StoredSession | None:
        return self._session

    async def get_access_token(self) -> str:  # pragma: no cover - guarded against by tests
        raise AssertionError("get_access_token() must not be called on a known issuer/server mismatch (#253) — that path refreshes and can clear the session.")


def _fake_target(resolved: str) -> ResolvedServerTarget:
    return ResolvedServerTarget(
        configured_server_url=None,
        env_server_url=resolved,
        override_mode=OverrideMode.PROCESS_OVERRIDE,
        resolved_server_url=resolved,
    )


async def test_check_server_session_issuer_mismatch_skips_refresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A known issuer/server mismatch short-circuits before any refresh (#253)."""
    session = _make_session(refresh_token_expires_at=now_utc() + timedelta(days=30))
    session.issuer_url = "https://old.example.com"

    import specify_cli.auth as _auth_module

    monkeypatch.setattr(_auth_module, "get_token_manager", lambda: _FakeTokenManagerWithSession(session))
    monkeypatch.setattr(
        _auth_doctor,
        "resolve_server_target",
        lambda **_kwargs: _fake_target("https://team.spec-kitty.ai"),
    )

    result = await _check_server_session()

    assert result.active is False
    assert result.error is not None
    assert "old.example.com" in result.error
    assert "team.spec-kitty.ai" in result.error
    assert "auth login --force" in result.error


async def test_check_server_session_issuer_matches_proceeds_normally(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A matching issuer_url does not block the refresh + server check."""
    session = _make_session(refresh_token_expires_at=now_utc() + timedelta(days=30))
    session.issuer_url = "https://team.spec-kitty.ai"

    class _TmMatchingIssuer(_FakeTokenManagerWithSession):
        async def get_access_token(self) -> str:
            return "tok"

    import specify_cli.auth as _auth_module

    monkeypatch.setattr(_auth_module, "get_token_manager", lambda: _TmMatchingIssuer(session))
    monkeypatch.setattr(
        _auth_doctor,
        "resolve_server_target",
        lambda **_kwargs: _fake_target("https://team.spec-kitty.ai"),
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"session_id": "abc"}
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_response)

    with (
        patch("specify_cli.auth.config.get_saas_base_url", return_value="https://team.spec-kitty.ai"),
        patch("httpx.AsyncClient", return_value=mock_client),
    ):
        result = await _check_server_session()

    assert result.active is True
    assert result.session_id == "abc"


async def test_check_server_session_no_issuer_proceeds_normally(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A legacy session with no recorded issuer_url is not treated as a mismatch."""
    session = _make_session(refresh_token_expires_at=now_utc() + timedelta(days=30))
    assert session.issuer_url is None

    class _TmNoIssuer(_FakeTokenManagerWithSession):
        async def get_access_token(self) -> str:
            return "tok"

    import specify_cli.auth as _auth_module

    monkeypatch.setattr(_auth_module, "get_token_manager", lambda: _TmNoIssuer(session))
    monkeypatch.setattr(
        _auth_doctor,
        "resolve_server_target",
        lambda **_kwargs: _fake_target("https://team.spec-kitty.ai"),
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"session_id": "abc"}
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_response)

    with (
        patch("specify_cli.auth.config.get_saas_base_url", return_value="https://team.spec-kitty.ai"),
        patch("httpx.AsyncClient", return_value=mock_client),
    ):
        result = await _check_server_session()

    assert result.active is True


def test_server_issuer_mismatch_error_none_when_session_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No session at all ⇒ no mismatch to report (the ordinary NotAuthenticatedError path decides)."""
    tm = _FakeTokenManagerWithSession(None)
    monkeypatch.setattr(_auth_doctor, "resolve_server_target", lambda: _fake_target("https://team.spec-kitty.ai"))
    assert _server_issuer_mismatch_error(tm) is None


def test_server_issuer_mismatch_error_none_on_bare_async_mock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A bare ``AsyncMock`` test double (unconfigured ``get_current_session``) is treated as unknown, not a mismatch."""
    tm = AsyncMock()
    monkeypatch.setattr(
        _auth_doctor,
        "resolve_server_target",
        lambda **_kwargs: _fake_target("https://team.spec-kitty.ai"),
    )
    assert _server_issuer_mismatch_error(tm) is None


def test_server_issuer_mismatch_error_none_when_target_resolution_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A server-target resolution failure (e.g. split-brain) falls through, not blocks."""
    session = _make_session(refresh_token_expires_at=now_utc() + timedelta(days=30))
    session.issuer_url = "https://old.example.com"
    tm = _FakeTokenManagerWithSession(session)

    def _raise() -> ResolvedServerTarget:
        raise RuntimeError("split-brain")

    monkeypatch.setattr(_auth_doctor, "resolve_server_target", _raise)

    assert _server_issuer_mismatch_error(tm) is None


def test_render_server_status_escapes_bracketed_mismatch_reason() -> None:
    """A mismatch reason naming ``config.toml [sync].server_url`` must not corrupt Rich markup (#182)."""
    status = ServerSessionStatus(
        active=False,
        error=(
            "Session is for https://old.example.com; config.toml [sync].server_url now points at https://team.spec-kitty.ai — run spec-kitty auth login --force"
        ),
    )
    buf = io.StringIO()
    con = Console(file=buf, width=200, record=False, force_terminal=False)
    import specify_cli.cli.commands._auth_doctor as doctor_module

    original_console = doctor_module.console
    doctor_module.console = con
    try:
        doctor_module._render_server_status(status)
    finally:
        doctor_module.console = original_console
    output = buf.getvalue()

    assert "[sync].server_url" in output
    assert "run spec-kitty auth login --force" in output


# ---------------------------------------------------------------------------
# T019: doctor_impl server flag tests
# ---------------------------------------------------------------------------


def test_doctor_impl_server_false_no_outbound_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """server=False must not call asyncio.run or _check_server_session."""
    import asyncio

    session = _make_session(refresh_token_expires_at=now_utc() + timedelta(days=30))
    _patch_state(monkeypatch, session=session)

    asyncio_run_called = []

    def _fail_asyncio_run(coro, *args, **kwargs):  # type: ignore[no-untyped-def]
        asyncio_run_called.append(True)
        raise AssertionError("asyncio.run called with server=False — C-007 violation")

    monkeypatch.setattr(asyncio, "run", _fail_asyncio_run)

    exit_code = doctor_impl(
        json_output=True,
        unstick_lock=False,
        stuck_threshold=60.0,
        server=False,
    )

    assert asyncio_run_called == [], "asyncio.run must not be called with server=False"
    assert exit_code == 0


def test_doctor_impl_server_true_renders_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """server=True + active session → output contains 'active' and session id."""
    session = _make_session(refresh_token_expires_at=now_utc() + timedelta(days=30))
    _patch_state(monkeypatch, session=session)

    fake_status = ServerSessionStatus(active=True, session_id="s1")

    import asyncio

    def _fake_run(coro):  # type: ignore[no-untyped-def]
        coro.close()  # Prevent "coroutine never awaited" warning.
        return fake_status

    monkeypatch.setattr(asyncio, "run", _fake_run)

    buf = io.StringIO()
    monkeypatch.setattr(
        _auth_doctor,
        "console",
        Console(file=buf, width=120, record=False, force_terminal=False),
    )

    exit_code = doctor_impl(
        json_output=False,
        unstick_lock=False,
        stuck_threshold=60.0,
        server=True,
    )

    output = buf.getvalue()
    assert "active" in output
    assert "s1" in output
    assert exit_code == 0


def test_doctor_impl_server_true_renders_unknown_session_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _make_session(refresh_token_expires_at=now_utc() + timedelta(days=30))
    _patch_state(monkeypatch, session=session)

    fake_status = ServerSessionStatus(active=True, session_id=None)

    import asyncio

    def _fake_run(coro):  # type: ignore[no-untyped-def]
        coro.close()
        return fake_status

    monkeypatch.setattr(asyncio, "run", _fake_run)

    buf = io.StringIO()
    monkeypatch.setattr(
        _auth_doctor,
        "console",
        Console(file=buf, width=120, record=False, force_terminal=False),
    )

    exit_code = doctor_impl(
        json_output=False,
        unstick_lock=False,
        stuck_threshold=60.0,
        server=True,
    )

    output = buf.getvalue()
    assert "(unknown)" in output
    assert exit_code == 0


def test_doctor_impl_server_true_renders_reauthenticate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """server=True + 401 → re-authenticate guidance, an F-008 finding, exit 1.

    A failed server check is a critical finding even when the local access
    token is still valid (#4607) — the exit code must agree with the detail
    line rendered directly beneath the Findings section.
    """
    session = _make_session(refresh_token_expires_at=now_utc() + timedelta(days=30))
    _patch_state(monkeypatch, session=session)

    fake_status = ServerSessionStatus(active=False, error="re-authenticate")

    import asyncio

    def _fake_run(coro):  # type: ignore[no-untyped-def]
        coro.close()
        return fake_status

    monkeypatch.setattr(asyncio, "run", _fake_run)

    buf = io.StringIO()
    monkeypatch.setattr(
        _auth_doctor,
        "console",
        Console(file=buf, width=120, record=False, force_terminal=False),
    )

    exit_code = doctor_impl(
        json_output=False,
        unstick_lock=False,
        stuck_threshold=60.0,
        server=True,
    )

    output = buf.getvalue()
    assert "re-authenticate" in output or "login" in output.lower()
    assert "F-008" in output
    assert "No problems detected" not in output
    assert exit_code == 1


def test_doctor_impl_server_http_500_is_finding_and_exit_1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#4607: HTTP 500 on the server check → F-008 finding and exit 1.

    The observed bug: a healthy local session plus a failing server check
    printed ``No problems detected.`` and exited 0, so a CI health gate
    passed cleanly through a total backend outage.
    """
    session = _make_session(refresh_token_expires_at=now_utc() + timedelta(days=30))
    _patch_state(monkeypatch, session=session)

    fake_status = ServerSessionStatus(active=False, error="Server returned HTTP 500")

    import asyncio

    def _fake_run(coro):  # type: ignore[no-untyped-def]
        coro.close()  # Prevent "coroutine never awaited" warning.
        return fake_status

    monkeypatch.setattr(asyncio, "run", _fake_run)

    buf = io.StringIO()
    monkeypatch.setattr(
        _auth_doctor,
        "console",
        Console(file=buf, width=120, record=False, force_terminal=False),
    )

    exit_code = doctor_impl(
        json_output=False,
        unstick_lock=False,
        stuck_threshold=60.0,
        server=True,
    )

    output = buf.getvalue()
    assert "F-008" in output
    assert "Server returned HTTP 500" in output
    assert "No problems detected" not in output
    assert exit_code == 1


def test_doctor_impl_server_http_500_json_finding_and_exit_1(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """#4607 in --json mode: the F-008 finding lands in ``findings`` and exit is 1."""
    session = _make_session(refresh_token_expires_at=now_utc() + timedelta(days=30))
    _patch_state(monkeypatch, session=session)

    fake_status = ServerSessionStatus(active=False, error="Server returned HTTP 500")

    import asyncio

    def _fake_run(coro):  # type: ignore[no-untyped-def]
        coro.close()  # Prevent "coroutine never awaited" warning.
        return fake_status

    monkeypatch.setattr(asyncio, "run", _fake_run)

    exit_code = doctor_impl(
        json_output=True,
        unstick_lock=False,
        stuck_threshold=60.0,
        server=True,
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["server_session"]["active"] is False
    assert payload["server_session"]["error"] == "Server returned HTTP 500"
    f008 = [f for f in payload["findings"] if f["id"] == "F-008"]
    assert len(f008) == 1
    assert f008[0]["severity"] == "critical"
    assert "Server returned HTTP 500" in f008[0]["summary"]
    assert exit_code == 1


def test_assemble_report_failed_server_probe_is_critical_finding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#4607 at the assembly seam: an inactive probe flips the verdict off ``ok``."""
    session = _make_session(refresh_token_expires_at=now_utc() + timedelta(days=30))
    _patch_state(monkeypatch, session=session)

    report = assemble_report(
        server_probe=ServerSessionStatus(active=False, error="Server returned HTTP 500"),
    )

    assert report.auth_verdict.state == "fail"
    f008 = next(f for f in report.findings if f.id == "F-008")
    assert f008.severity == "critical"
    assert "Server returned HTTP 500" in f008.summary
    assert compute_exit_code(report.findings) == 1


def test_doctor_impl_server_true_json_includes_server_session(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """server=True + --json → payload includes server_session key."""
    session = _make_session(refresh_token_expires_at=now_utc() + timedelta(days=30))
    _patch_state(monkeypatch, session=session)

    fake_status = ServerSessionStatus(active=True, session_id="s2")

    import asyncio

    def _fake_run(coro):  # type: ignore[no-untyped-def]
        coro.close()
        return fake_status

    monkeypatch.setattr(asyncio, "run", _fake_run)

    exit_code = doctor_impl(
        json_output=True,
        unstick_lock=False,
        stuck_threshold=60.0,
        server=True,
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert "server_session" in payload
    assert payload["server_session"]["active"] is True
    assert payload["server_session"]["session_id"] == "s2"
    assert exit_code == 0


def test_default_doctor_output_has_server_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default auth doctor output ends with the --server hint line."""
    session = _make_session(refresh_token_expires_at=now_utc() + timedelta(days=30))
    _patch_state(monkeypatch, session=session)

    report = assemble_report()
    rendered = _capture_render(report)

    assert "spec-kitty auth doctor --server" in rendered


def test_server_doctor_output_no_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """auth doctor --server output does NOT show the hint."""
    session = _make_session(refresh_token_expires_at=now_utc() + timedelta(days=30))
    _patch_state(monkeypatch, session=session)

    report = assemble_report()
    buf = io.StringIO()
    con = Console(file=buf, width=120, record=False, force_terminal=False)
    render_report(report, con, show_server_hint=False)
    output = buf.getvalue()

    assert "spec-kitty auth doctor --server" not in output
