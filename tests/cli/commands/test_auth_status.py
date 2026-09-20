"""Unit + CliRunner tests for ``spec-kitty auth status`` (feature 080, WP07).

Covers:

- ``format_duration`` across all five branches (expired, <1 minute,
  minutes, hours, days) including singular/plural handling.
- ``format_storage_backend`` for the supported backend plus the
  unknown-fallthrough branch.
- ``format_auth_method`` across both known methods plus the unknown
  fallthrough branch.
- ``_print_token_expiry`` with a concrete ``refresh_token_expires_at``
  AND with ``None`` (the defensive legacy-session fallback — per C-012
  the amendment landed 2026-04-09 so new sessions never hit this branch,
  but the CLI must not crash on replayed pre-amendment sessions).
- CliRunner E2E:
    * authenticated path with multi-team session and default marker
    * unauthenticated path
    * refresh-expired path (the early-return branch in ``status_impl``)

Every CliRunner test mocks ``SecureStorage.from_environment`` so we never
touch the real auth store — matches the pattern established by
``tests/auth/test_device_code_flow.py`` and ``tests/cli/commands/test_auth_login.py``.
"""

from __future__ import annotations

from kernel.clock import datetime, timedelta, now_utc
from io import StringIO
from unittest.mock import Mock, patch

import pytest
from rich.console import Console
from typer.testing import CliRunner

from specify_cli.auth import reset_token_manager
from specify_cli.auth.errors import SessionFilePermissionsError
from specify_cli.auth.server_target import (
    OverrideMode,
    ResolvedServerTarget,
)
from specify_cli.auth.session import StoredSession, Team
from specify_cli.cli.commands._auth_saas_target import (
    format_saas_mismatch_warning,
    format_saas_provenance,
    saas_source_name,
)
from specify_cli.cli.commands._auth_status import (
    _print_token_expiry,
    format_auth_method,
    format_duration,
    format_storage_backend,
)
from specify_cli.cli.commands.auth import app


pytestmark = [pytest.mark.integration]

runner = CliRunner()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    """Reset the process-wide TokenManager between tests.

    Also provides ``SPEC_KITTY_SAAS_URL`` so any auth config code paths
    that probe it don't blow up.
    """
    monkeypatch.setenv("SPEC_KITTY_SAAS_URL", "https://saas.test")
    reset_token_manager()
    yield
    reset_token_manager()


def _make_session(
    *,
    email: str = "alice@example.com",
    name: str = "Alice Developer",
    access_remaining_seconds: int = 3600,
    refresh_remaining_days: int | None = 89,
    storage_backend: str = "file",
    auth_method: str = "authorization_code",
    teams: list[Team] | None = None,
    default_team_id: str = "tm_acme",
    issuer_url: str | None = None,
) -> StoredSession:
    """Build a StoredSession with controllable remaining-time offsets.

    ``refresh_remaining_days=None`` produces a legacy session (the
    ``refresh_token_expires_at`` defensive branch).

    Implementation note: we add a 30-second pad on top of each positive
    offset so that the few microseconds that elapse between building the
    session and materializing the status output don't push the integer
    division below the next boundary (e.g. 89 days - 0.001s -> 88 days).
    """
    now = now_utc()
    if teams is None:
        teams = [
            Team(id="tm_acme", name="Acme Corp", role="admin", is_private_teamspace=True),
            Team(id="tm_widgets", name="Widgets Inc", role="member"),
        ]
    refresh_exp: datetime | None
    if refresh_remaining_days is None:
        refresh_exp = None
    elif refresh_remaining_days < 0:
        # Negative offsets intentionally land in the past (expired branch).
        refresh_exp = now + timedelta(days=refresh_remaining_days)
    else:
        refresh_exp = now + timedelta(days=refresh_remaining_days, seconds=30)
    access_exp = now + timedelta(seconds=access_remaining_seconds + 30) if access_remaining_seconds >= 0 else now + timedelta(seconds=access_remaining_seconds)
    return StoredSession(
        user_id="u_alice",
        email=email,
        name=name,
        teams=teams,
        default_team_id=default_team_id,
        access_token="at_xyz_ignore",
        refresh_token="rt_xyz_ignore",
        session_id="sess_01HR6CABCDEF",
        issued_at=now,
        access_token_expires_at=access_exp,
        refresh_token_expires_at=refresh_exp,
        scope="offline_access",
        storage_backend=storage_backend,  # type: ignore[arg-type]
        last_used_at=now,
        auth_method=auth_method,  # type: ignore[arg-type]
        issuer_url=issuer_url,
    )


def _mock_storage_returning(session: StoredSession | None, *, backend: str = "file"):
    """Build a Mock SecureStorage returning ``session`` on ``read()``."""
    mock_storage = Mock()
    mock_storage.read.return_value = session
    mock_storage.write = Mock(return_value=None)
    mock_storage.delete = Mock(return_value=None)
    mock_storage.backend_name = backend
    return mock_storage


# ---------------------------------------------------------------------------
# format_duration — all five branches
# ---------------------------------------------------------------------------


class TestFormatDuration:
    """Exhaustive coverage of the format_duration branch table."""

    def test_expired_branch(self):
        assert "expired" in format_duration(-100)

    def test_expired_branch_zero(self):
        assert "expired" in format_duration(0)

    def test_less_than_one_minute(self):
        # 45 seconds -> "< 1 minute" (we deliberately don't render "45 seconds"
        # in the status layout because sub-minute precision is noise).
        assert format_duration(45) == "< 1 minute"

    def test_less_than_one_minute_just_below(self):
        assert format_duration(59) == "< 1 minute"

    def test_minute_singular(self):
        assert format_duration(60) == "1 minute"

    def test_minutes_plural(self):
        assert format_duration(120) == "2 minutes"

    def test_minutes_plural_42(self):
        assert format_duration(42 * 60) == "42 minutes"

    def test_hour_singular(self):
        assert format_duration(3600) == "1 hour"

    def test_hours_plural(self):
        assert format_duration(7200) == "2 hours"

    def test_day_singular(self):
        assert format_duration(86400) == "1 day"

    def test_days_plural(self):
        assert format_duration(86400 * 87) == "87 days"

    def test_days_plural_large(self):
        assert format_duration(86400 * 365) == "365 days"


# ---------------------------------------------------------------------------
# format_storage_backend
# ---------------------------------------------------------------------------


class TestFormatStorageBackend:
    """The supported backend plus unknown fallthrough."""

    def test_file_label(self):
        assert format_storage_backend("file") == "Encrypted session file"

    def test_unknown_fallthrough(self):
        assert "Unknown" in format_storage_backend("unknown-backend")
        assert "unknown-backend" in format_storage_backend("unknown-backend")


# ---------------------------------------------------------------------------
# format_auth_method
# ---------------------------------------------------------------------------


class TestFormatAuthMethod:
    """All known methods plus unknown fallthrough."""

    def test_authorization_code_label(self):
        label = format_auth_method("authorization_code")
        assert "Browser" in label
        assert "PKCE" in label

    def test_device_code_label(self):
        label = format_auth_method("device_code")
        assert "Headless" in label
        assert "Device" in label

    def test_client_credentials_label(self):
        """#3277: the machine/CI mode has a first-class label."""
        label = format_auth_method("client_credentials")
        assert "Machine" in label
        assert "Client Credentials" in label

    def test_unknown_fallthrough(self):
        assert "Unknown" in format_auth_method("xyz")


# ---------------------------------------------------------------------------
# _print_token_expiry — both branches (datetime + None defensive fallback)
# ---------------------------------------------------------------------------


def _capture_print_token_expiry(session: StoredSession) -> str:
    """Run ``_print_token_expiry`` against a local Console and return output."""
    buf = StringIO()
    test_console = Console(file=buf, force_terminal=False, width=120)
    with patch("specify_cli.cli.commands._auth_status.console", test_console):
        _print_token_expiry(session)
    return buf.getvalue()


class TestPrintTokenExpiry:
    """The defensive None branch exists only to handle pre-amendment sessions."""

    def test_refresh_datetime_branch_shows_duration(self):
        session = _make_session(
            access_remaining_seconds=3600,
            refresh_remaining_days=89,
        )
        out = _capture_print_token_expiry(session)
        assert "Access token:" in out
        assert "Refresh token:" in out
        assert "89 days" in out
        # Must NOT mention the legacy-session fallback when the datetime is present.
        assert "legacy session" not in out
        assert "server-managed" not in out

    def test_refresh_none_branch_shows_legacy_fallback(self):
        session = _make_session(
            access_remaining_seconds=3600,
            refresh_remaining_days=None,  # pre-amendment / replayed session
        )
        out = _capture_print_token_expiry(session)
        assert "Access token:" in out
        assert "Refresh token:" in out
        # Defensive fallback copy per the C-012 amendment contract.
        assert "server-managed" in out
        assert "legacy session" in out
        assert "re-login" in out

    def test_access_token_expired_rendered_as_expired(self):
        session = _make_session(
            access_remaining_seconds=-100,
            refresh_remaining_days=89,
        )
        out = _capture_print_token_expiry(session)
        assert "expired" in out


# ---------------------------------------------------------------------------
# CliRunner E2E — drives `auth status` through the live Typer app
# ---------------------------------------------------------------------------


class TestAuthStatusCommand:
    """Exercise the full dispatch path: ``runner.invoke(app, ['status'])``."""

    def test_not_authenticated_path(self):
        """No session -> friendly unauthenticated message, exit code 0."""
        mock_storage = _mock_storage_returning(None, backend="file")
        with patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment",
            return_value=mock_storage,
        ):
            reset_token_manager()
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0, result.stdout
        assert "Not authenticated" in result.stdout
        assert "spec-kitty auth login" in result.stdout
        # #189: the endpoint line prints even with no session to compare against.
        assert "SaaS:" in result.stdout
        assert "https://saas.test" in result.stdout

    def test_unsafe_permissions_refusal_renders_remedy_not_login(self):
        """#4761: when storage fails closed on unsafe session-file
        permissions, ``auth status`` renders the storage layer's own chmod
        remedy — never the auth-login line, which would silently overwrite
        the loose file storage just refused to read."""
        mock_storage = _mock_storage_returning(None, backend="file")
        mock_storage.read.side_effect = SessionFilePermissionsError(
            "Session file /home/u/.spec-kitty/auth/session.json has unsafe "
            "permissions (mode=0o644); expected 0600. Fix with: chmod 600 "
            "/home/u/.spec-kitty/auth/session.json"
        )
        with patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment",
            return_value=mock_storage,
        ):
            reset_token_manager()
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0, result.stdout
        assert "Not authenticated" in result.stdout
        assert "unsafe permissions" in result.stdout
        assert "chmod 600" in result.stdout
        assert "spec-kitty auth login" not in result.stdout

    def test_authenticated_path_happy(self):
        """Authenticated session prints identity, teams, expiry, backend."""
        session = _make_session(
            access_remaining_seconds=3600,
            refresh_remaining_days=89,
            storage_backend="file",
            auth_method="authorization_code",
        )
        mock_storage = _mock_storage_returning(session, backend="file")
        with patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment",
            return_value=mock_storage,
        ):
            reset_token_manager()
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0, result.stdout
        # Banner
        assert "Authenticated" in result.stdout
        # Identity
        assert "alice@example.com" in result.stdout
        assert "Alice Developer" in result.stdout
        assert "u_alice" in result.stdout
        # Teams with default marker
        assert "Acme Corp" in result.stdout
        assert "Widgets Inc" in result.stdout
        assert "private" in result.stdout
        assert "default" in result.stdout  # default-team marker
        # Expiry — access ~1 hour, refresh 89 days
        assert "1 hour" in result.stdout
        assert "89 days" in result.stdout
        # Storage backend (human label, not raw literal)
        assert "Encrypted session file" in result.stdout
        # Session id
        assert "sess_01HR6CABCDEF" in result.stdout
        # Auth method human label
        assert "Browser" in result.stdout
        assert "PKCE" in result.stdout
        # Secrets must NOT leak.
        assert "at_xyz_ignore" not in result.stdout
        assert "rt_xyz_ignore" not in result.stdout

    def test_authenticated_path_renders_bracket_markup_in_email_name_and_team(self):
        session = _make_session(
            email="alice[/]@example.com",
            name="Alice [/] Developer",
            teams=[
                Team(
                    id="tm_acme",
                    name="Acme [/] Corp",
                    role="admin",
                    is_private_teamspace=True,
                )
            ],
        )
        mock_storage = _mock_storage_returning(session, backend="file")
        with patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment",
            return_value=mock_storage,
        ):
            reset_token_manager()
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0, result.stdout
        assert "User: alice[/]@example.com (Alice [/] Developer)" in _flat(result.stdout)
        assert "- Acme [/] Corp (admin)" in _flat(result.stdout)
        assert "MarkupError" not in result.stdout

    def test_authenticated_path_strips_terminal_controls_from_saas_identity_bytes(self):
        """Hostile SaaS identity fields cannot emit terminal control bytes (#700)."""
        safe_name = "Zoë Ölafsdóttir 日本語 🐱"
        hostile_suffix = "\x1b[2J\x1b]0;x\x07\x1b"
        session = _make_session(
            email=f"{safe_name}{hostile_suffix}",
            name=f"{safe_name}{hostile_suffix}",
            teams=[
                Team(
                    id="tm_hostile",
                    name=f"{safe_name}{hostile_suffix}",
                    role=f"admin{hostile_suffix}",
                )
            ],
            default_team_id="tm_hostile",
        )
        session.session_id = f"session{hostile_suffix}"
        mock_storage = _mock_storage_returning(session, backend="file")

        with patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment",
            return_value=mock_storage,
        ):
            reset_token_manager()
            result = runner.invoke(app, ["status"])

        emitted = result.stdout_bytes
        assert result.exit_code == 0, result.stdout
        assert safe_name.encode("utf-8") in emitted
        assert b"\x1b" not in emitted
        assert b"[2J" not in emitted
        assert b"]0;x" not in emitted

    def test_authenticated_path_renders_bracket_markup_in_email_only_identity(self):
        session = _make_session(email="alice[/]@example.com", name="")
        mock_storage = _mock_storage_returning(session, backend="file")
        with patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment",
            return_value=mock_storage,
        ):
            reset_token_manager()
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0, result.stdout
        assert "User: alice[/]@example.com" in _flat(result.stdout)
        assert "MarkupError" not in result.stdout

    def test_authenticated_path_minutes_branch(self):
        """Access token with 600s remaining must render minutes, not hours."""
        session = _make_session(
            access_remaining_seconds=600,  # 10 minutes
            refresh_remaining_days=89,
            storage_backend="file",
        )
        mock_storage = _mock_storage_returning(session, backend="file")
        with patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment",
            return_value=mock_storage,
        ):
            reset_token_manager()
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0, result.stdout
        assert "10 minutes" in result.stdout
        assert "89 days" in result.stdout
        assert "Encrypted session file" in result.stdout

    def test_refresh_token_expired_is_not_authenticated(self):
        """An expired refresh token yields the honest ``Not authenticated``
        verdict banner (derived from state), not a hand-rolled claim (#3723)."""
        session = _make_session(
            access_remaining_seconds=-100,
            refresh_remaining_days=-1,  # refresh already expired
        )
        mock_storage = _mock_storage_returning(session, backend="file")
        with patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment",
            return_value=mock_storage,
        ):
            reset_token_manager()
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0, result.stdout
        assert "Not authenticated" in result.stdout
        # The banner names its evidence (rule 1) and is never a bare green claim.
        assert "expired" in result.stdout
        assert "+ Authenticated" not in result.stdout
        assert "spec-kitty auth login" in result.stdout
        # #189: the endpoint line — this is the exact diagnostic surface a
        # post-hostname-move expired session needs.
        assert "SaaS:" in result.stdout
        assert "https://saas.test" in result.stdout

    def test_expired_access_valid_refresh_headline_is_not_green(self):
        """#3723-c: valid refresh + EXPIRED access must NOT print ``+ Authenticated``.

        Offline (no server probe) the refresh chain is unproven, so the honest
        headline is ``Cannot verify`` — and it never sits above a contradicting
        ``Access token: expired`` detail as a green claim.
        """
        session = _make_session(
            access_remaining_seconds=-100,  # access expired
            refresh_remaining_days=30,  # refresh still valid
        )
        mock_storage = _mock_storage_returning(session, backend="file")
        with patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment",
            return_value=mock_storage,
        ):
            reset_token_manager()
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0, result.stdout
        assert "+ Authenticated" not in result.stdout
        assert "Cannot verify" in result.stdout
        # The access-token detail still renders expired — headline agrees with it.
        assert "expired" in result.stdout

    def test_authenticated_path_device_code_auth_method(self):
        """Device-code sessions render the Headless label."""
        session = _make_session(
            auth_method="device_code",
            storage_backend="file",
        )
        mock_storage = _mock_storage_returning(session, backend="file")
        with patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment",
            return_value=mock_storage,
        ):
            reset_token_manager()
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0, result.stdout
        assert "Headless" in result.stdout
        assert "Device" in result.stdout
        assert "Encrypted session file" in result.stdout

    def test_authenticated_path_empty_teams(self):
        """A session with no teams should print ``(none)`` instead of crashing."""
        session = _make_session(teams=[], default_team_id="")
        mock_storage = _mock_storage_returning(session, backend="file")
        with patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment",
            return_value=mock_storage,
        ):
            reset_token_manager()
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0, result.stdout
        assert "(none)" in result.stdout

    def test_authenticated_path_legacy_refresh_none_branch(self):
        """Replayed pre-amendment session hits the defensive None branch."""
        session = _make_session(refresh_remaining_days=None)
        mock_storage = _mock_storage_returning(session, backend="file")
        with patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment",
            return_value=mock_storage,
        ):
            reset_token_manager()
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0, result.stdout
        assert "server-managed" in result.stdout
        assert "legacy session" in result.stdout


class TestAuthStatusHostileSessionEnums:
    """#527: unknown enum fallthroughs must not become Rich markup.

    These values are local session-file fields rather than SaaS payloads, but a
    tampered or replayed file can still put markup-shaped bytes in them.
    """

    def test_hostile_auth_method_does_not_crash_and_renders_literally(self):
        session = _make_session(auth_method="x[/]y")
        mock_storage = _mock_storage_returning(session, backend="file")
        with patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment",
            return_value=mock_storage,
        ):
            reset_token_manager()
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0, result.stdout
        assert "Unknown (x[/]y)" in _flat(result.stdout)

    def test_hostile_storage_backend_does_not_crash_and_renders_literally(self):
        session = _make_session(storage_backend="f[/]x")
        mock_storage = _mock_storage_returning(session, backend="file")
        with patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment",
            return_value=mock_storage,
        ):
            reset_token_manager()
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0, result.stdout
        assert "Unknown (f[/]x)" in _flat(result.stdout)


# ---------------------------------------------------------------------------
# SaaS endpoint line (#176) — pure formatters
# ---------------------------------------------------------------------------


def _target(
    *,
    env_server_url: str | None,
    configured_server_url: str | None,
) -> ResolvedServerTarget:
    # Hand-built target for the pure formatters.
    resolved = env_server_url or configured_server_url or "https://handbuilt.test"
    return ResolvedServerTarget(
        configured_server_url=configured_server_url,
        env_server_url=env_server_url,
        override_mode=OverrideMode.NONE,
        resolved_server_url=resolved,
    )


def _flat(text: str) -> str:
    """Collapse whitespace so assertions survive rich's line wrapping."""
    return " ".join(text.split())


def _saas_line(text: str) -> str:
    """Return the rendered SaaS label line without collapsing alignment."""
    return next(line for line in text.splitlines() if line.startswith("  SaaS:"))


class TestSaasSourceName:
    """Provenance naming mirrors resolve_server_target's precedence."""

    def test_env_wins(self):
        target = _target(env_server_url="https://env.test", configured_server_url="https://config.test")
        assert saas_source_name(target) == "SPEC_KITTY_SAAS_URL"

    def test_config_when_no_env(self):
        target = _target(env_server_url=None, configured_server_url="https://config.test")
        assert saas_source_name(target) == "config.toml [sync].server_url"

    def test_packaged_default_when_neither_set(self):
        # #3980 (D-5 revised): nothing configured resolves to the packaged
        # default, and the mismatch warning names it as the source.
        target = _target(env_server_url=None, configured_server_url=None)
        assert saas_source_name(target) == "the packaged default"


class TestFormatSaasProvenance:
    """The dim suffix shown next to the ``SaaS:`` line."""

    def test_from_env_var(self):
        target = _target(env_server_url="https://saas.test", configured_server_url=None)
        assert format_saas_provenance(target) == "(from SPEC_KITTY_SAAS_URL)"

    def test_from_config_toml(self):
        target = _target(env_server_url=None, configured_server_url="https://config.test")
        assert format_saas_provenance(target) == "(from config.toml [sync].server_url)"

    def test_packaged_default_when_neither_set(self):
        # #3980: a launch build with nothing configured renders the packaged
        # default with its own provenance — never ``None`` (which crashed the
        # renderer before the packaged-default branch existed).
        target = _target(env_server_url=None, configured_server_url=None)
        assert format_saas_provenance(target) == "(packaged default)"


class TestFormatSaasMismatchWarning:
    """The stale-session warning fires only when issuer and config disagree."""

    def test_none_for_legacy_session_without_issuer(self):
        warning = format_saas_mismatch_warning(
            None,
            source_name="SPEC_KITTY_SAAS_URL",
            resolved_server_url="https://saas.test",
        )
        assert warning is None

    def test_none_when_issuer_matches(self):
        warning = format_saas_mismatch_warning(
            "https://saas.test",
            source_name="SPEC_KITTY_SAAS_URL",
            resolved_server_url="https://saas.test",
        )
        assert warning is None

    def test_trailing_slash_is_not_a_mismatch(self):
        warning = format_saas_mismatch_warning(
            "https://saas.test/",
            source_name="SPEC_KITTY_SAAS_URL",
            resolved_server_url="https://saas.test",
        )
        assert warning is None

    def test_message_names_both_endpoints_and_the_fix(self):
        warning = format_saas_mismatch_warning(
            "https://sk-teamkitty.exe.xyz",
            source_name="SPEC_KITTY_SAAS_URL",
            resolved_server_url="https://team.spec-kitty.ai",
        )
        assert warning is not None
        assert warning == (
            "Session is for https://sk-teamkitty.exe.xyz; SPEC_KITTY_SAAS_URL now points at https://team.spec-kitty.ai — run spec-kitty auth login --force"
        )


# ---------------------------------------------------------------------------
# SaaS endpoint line (#176) — CliRunner E2E
# ---------------------------------------------------------------------------


class TestAuthStatusSaasLine:
    """The authenticated block opens with the SaaS endpoint and its origin."""

    def test_status_prints_endpoint_with_env_provenance(self):
        session = _make_session(issuer_url="https://saas.test")
        mock_storage = _mock_storage_returning(session, backend="file")
        with patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment",
            return_value=mock_storage,
        ):
            reset_token_manager()
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0, result.stdout
        flat = _flat(result.stdout)
        # Same value `auth login` prints (the fixture sets it to https://saas.test).
        assert "https://saas.test" in flat
        assert "(from SPEC_KITTY_SAAS_URL)" in flat
        assert _saas_line(result.stdout) == "  SaaS:           https://saas.test (from SPEC_KITTY_SAAS_URL)"

    def test_status_prints_endpoint_before_identity(self):
        """The SaaS line is the first line of the block after the banner."""
        session = _make_session()
        mock_storage = _mock_storage_returning(session, backend="file")
        with patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment",
            return_value=mock_storage,
        ):
            reset_token_manager()
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0, result.stdout
        saas_at = result.stdout.index("SaaS:")
        user_at = result.stdout.index("User:")
        assert saas_at < user_at

    def test_status_reports_packaged_default_when_unconfigured(self, monkeypatch: pytest.MonkeyPatch, tmp_path):
        """No env var and no config.toml -> the packaged default (#3980, D-5
        revised): the status block names ``https://team.spec-kitty.ai`` with
        ``(packaged default)`` provenance instead of the not-configured
        remedy. The stored session issuer remains visible so QA can tell
        which SaaS the authenticated session belongs to (#213), and the
        mismatch warning fires naming the packaged default as the source.
        """
        session = _make_session(issuer_url="https://saas.test")
        mock_storage = _mock_storage_returning(session, backend="file")
        with patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment",
            return_value=mock_storage,
        ):
            monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
            monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path))
            reset_token_manager()
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0, result.stdout
        flat = _flat(result.stdout)
        assert "Session SaaS:" in flat
        assert "https://saas.test" in flat
        assert "(authenticated session)" in flat
        assert "https://team.spec-kitty.ai" in flat
        assert "(packaged default)" in flat
        assert "SaaS:" in flat
        assert _saas_line(result.stdout).startswith("  SaaS:           https://team.spec-kitty.ai ")
        # The issuer disagrees with the packaged default, so the stale-session
        # warning names the packaged default as the thing now pointed at.
        assert "the packaged default now points at https://team.spec-kitty.ai" in flat

    def test_status_prints_session_endpoint_when_env_points_elsewhere(self):
        """The status output must name the server the token belongs to (#213)."""
        session = _make_session(issuer_url="https://team.spec-kitty.ai")
        mock_storage = _mock_storage_returning(session, backend="file")
        with patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment",
            return_value=mock_storage,
        ):
            reset_token_manager()
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0, result.stdout
        flat = _flat(result.stdout)
        assert "SaaS:" in flat
        assert "https://saas.test" in flat
        assert "(from SPEC_KITTY_SAAS_URL)" in flat
        assert "Session SaaS:" in flat
        assert "https://team.spec-kitty.ai" in flat
        assert "Session is for https://team.spec-kitty.ai" in flat

    def test_status_reports_packaged_default_when_config_server_url_is_blank(self, monkeypatch: pytest.MonkeyPatch, tmp_path):
        """#182 squad MAJOR, retargeted by #3980: a blank ``[sync].server_url``
        is *no opinion*, so the resolver answers the packaged default — a
        blank value must never be rendered as a configured (but empty)
        endpoint, nor as config provenance."""
        (tmp_path / "config.toml").write_text('[sync]\nserver_url = "  "\n', encoding="utf-8")
        session = _make_session(issuer_url="https://saas.test")
        mock_storage = _mock_storage_returning(session, backend="file")
        with patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment",
            return_value=mock_storage,
        ):
            monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
            monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path))
            reset_token_manager()
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0, result.stdout
        flat = _flat(result.stdout)
        assert "https://team.spec-kitty.ai" in flat
        assert "(packaged default)" in flat
        # The blank value must never be rendered as a configured provenance.
        assert "(from config.toml [sync].server_url)" not in flat

    def test_status_shows_config_toml_provenance_when_server_url_configured(self, monkeypatch: pytest.MonkeyPatch, tmp_path):
        """#182 squad pass-2 MAJOR: a genuinely-configured ``[sync].server_url``
        must render its URL and provenance literally, not have the Rich
        markup parser eat the ``[sync]``/`` [/]`` bracket text (regressed by
        the pass-1 reset onto ``main``, which dropped the ``escape()`` calls
        the pre-reset head had)."""
        (tmp_path / "config.toml").write_text('[sync]\nserver_url = "https://team.spec-kitty.ai"\n', encoding="utf-8")
        session = _make_session(issuer_url="https://team.spec-kitty.ai")
        mock_storage = _mock_storage_returning(session, backend="file")
        with patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment",
            return_value=mock_storage,
        ):
            monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
            monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path))
            reset_token_manager()
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0, result.stdout
        flat = _flat(result.stdout)
        assert "https://team.spec-kitty.ai" in flat
        assert "(from config.toml [sync].server_url)" in flat

    def test_status_does_not_crash_when_server_url_contains_bracket_syntax(self, monkeypatch: pytest.MonkeyPatch, tmp_path):
        """#182 squad pass-2 MAJOR: a configured ``server_url`` containing a
        closing-tag-like substring (``[/]``) must not raise
        ``rich.markup.MarkupError`` out of ``console.print`` — this module's
        docstring (FR-015) promises ``auth status`` never fails a shell."""
        (tmp_path / "config.toml").write_text('[sync]\nserver_url = "https://x.test[/]"\n', encoding="utf-8")
        session = _make_session(issuer_url="https://x.test[/]")
        mock_storage = _mock_storage_returning(session, backend="file")
        with patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment",
            return_value=mock_storage,
        ):
            monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
            monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path))
            reset_token_manager()
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0, result.stdout
        flat = _flat(result.stdout)
        assert "https://x.test[/]" in flat

    def test_mismatch_warning_fires_when_issuer_differs(self):
        """Hostname moved: stored session is for the old host, env points elsewhere."""
        session = _make_session(issuer_url="https://sk-teamkitty.exe.xyz")
        mock_storage = _mock_storage_returning(session, backend="file")
        with patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment",
            return_value=mock_storage,
        ):
            reset_token_manager()
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0, result.stdout
        flat = _flat(result.stdout)
        assert _saas_line(result.stdout) == "  SaaS:           https://saas.test (from SPEC_KITTY_SAAS_URL)"
        assert "Session is for https://sk-teamkitty.exe.xyz; SPEC_KITTY_SAAS_URL now points at https://saas.test" in flat
        assert "run spec-kitty auth login --force" in flat

    def test_no_mismatch_warning_when_issuer_matches(self):
        # A trailing slash on the stored issuer must not count as a mismatch.
        session = _make_session(issuer_url="https://saas.test/")
        mock_storage = _mock_storage_returning(session, backend="file")
        with patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment",
            return_value=mock_storage,
        ):
            reset_token_manager()
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0, result.stdout
        assert "Session is for" not in _flat(result.stdout)

    def test_status_shows_split_brain_instead_of_silently_picking_env(self, monkeypatch: pytest.MonkeyPatch, tmp_path):
        """#193: config.toml and SPEC_KITTY_SAAS_URL genuinely disagree.

        Previously ``_print_saas_target`` resolved with the default
        ``process_wide_override=True``, under which env silently wins and
        the diagnostic surface never shows the user that config.toml names a
        different endpoint. It must now show both values and the
        disagreement — and never a traceback, per this module's own
        never-fail invariant (FR-015).
        """
        (tmp_path / "config.toml").write_text('[sync]\nserver_url = "https://config.test"\n', encoding="utf-8")
        session = _make_session(issuer_url="https://saas.test")
        mock_storage = _mock_storage_returning(session, backend="file")
        with patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment",
            return_value=mock_storage,
        ):
            monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path))
            # SPEC_KITTY_SAAS_URL=https://saas.test comes from the autouse fixture.
            reset_token_manager()
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0, result.stdout
        assert "Traceback" not in result.stdout
        flat = _flat(result.stdout)
        assert _saas_line(result.stdout) == "  SaaS:           split-brain (env and config.toml disagree)"
        assert "split-brain" in flat
        assert "https://config.test" in flat
        assert "https://saas.test" in flat
        assert "SPEC_KITTY_SAAS_URL" in flat

    def test_status_split_brain_still_shows_session_issuer(self, monkeypatch: pytest.MonkeyPatch, tmp_path):
        """The session-issuer line (#213) survives the split-brain branch too."""
        (tmp_path / "config.toml").write_text('[sync]\nserver_url = "https://config.test"\n', encoding="utf-8")
        session = _make_session(issuer_url="https://old.example.com")
        mock_storage = _mock_storage_returning(session, backend="file")
        with patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment",
            return_value=mock_storage,
        ):
            monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path))
            reset_token_manager()
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0, result.stdout
        flat = _flat(result.stdout)
        assert "Session SaaS:" in flat
        assert "https://old.example.com" in flat

    def test_no_mismatch_warning_for_legacy_session(self):
        """Pre-#176 sessions carry no issuer; nothing can be compared."""
        session = _make_session(issuer_url=None)
        mock_storage = _mock_storage_returning(session, backend="file")
        with patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment",
            return_value=mock_storage,
        ):
            reset_token_manager()
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0, result.stdout
        assert "Session is for" not in _flat(result.stdout)
        assert "https://saas.test" in _flat(result.stdout)  # endpoint still shown

    def test_packaged_default_shown_in_not_authenticated_branch(self, monkeypatch: pytest.MonkeyPatch, tmp_path):
        """#189, retargeted by #3980: the packaged-default endpoint line must
        reach the no-session branch too, not just the authenticated one —
        there is no session to compare against, so this is the whole
        endpoint line."""
        mock_storage = _mock_storage_returning(None, backend="file")
        with patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment",
            return_value=mock_storage,
        ):
            monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
            monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path))
            reset_token_manager()
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0, result.stdout
        flat = _flat(result.stdout)
        assert "Not authenticated" in flat
        assert "https://team.spec-kitty.ai" in flat
        assert "(packaged default)" in flat
        assert "Session SaaS:" not in flat  # no session -> nothing to name

    def test_endpoint_and_mismatch_shown_in_expired_branch(self):
        """#189: the expired-session early return is exactly the
        post-hostname-move symptom #176 exists to diagnose, so it must show
        the endpoint, the session issuer, and the mismatch warning."""
        session = _make_session(
            access_remaining_seconds=-100,
            refresh_remaining_days=-1,  # refresh already expired
            issuer_url="https://sk-teamkitty.exe.xyz",
        )
        mock_storage = _mock_storage_returning(session, backend="file")
        with patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment",
            return_value=mock_storage,
        ):
            reset_token_manager()
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0, result.stdout
        flat = _flat(result.stdout)
        assert "Not authenticated" in flat
        assert "expired" in flat
        assert "SaaS:" in flat
        assert "https://saas.test" in flat
        assert "Session SaaS:" in flat
        assert "https://sk-teamkitty.exe.xyz" in flat
        assert "Session is for https://sk-teamkitty.exe.xyz; SPEC_KITTY_SAAS_URL now points at https://saas.test" in flat
