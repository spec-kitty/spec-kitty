"""CliRunner tests for ``spec-kitty auth login`` (feature 080, WP04 T027).

These tests exercise the real Typer ``app`` exported by
``specify_cli.cli.commands.auth`` via :class:`typer.testing.CliRunner`.
Internal flow orchestration is mocked at the
``specify_cli.cli.commands._auth_login`` seam so we test the command-to-
implementation wiring without starting a loopback server or touching the
real auth store.

Key behaviors under test (per WP04 acceptance criteria):

- ``--help`` does not mention ``password`` or ``username``.
- Browser flow is dispatched by default.
- ``--headless`` dispatches to the device flow branch.
- Missing ``SPEC_KITTY_SAAS_URL`` surfaces a clear configuration error.
- ``--force`` triggers re-authentication even when already logged in.
- Already-authenticated users without ``--force`` see a friendly message.
"""

from __future__ import annotations

from kernel.clock import timedelta, now_utc
import re
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from specify_cli.auth import reset_token_manager
from specify_cli.auth.errors import (
    AuthenticationError,
    BrowserLaunchError,
    CallbackValidationError,
)
from specify_cli.auth.session import StoredSession, Team
from specify_cli.cli.commands.auth import app


pytestmark = [pytest.mark.integration]

runner = CliRunner()


@pytest.fixture(autouse=True)
def _reset_tm(monkeypatch):
    """Reset the process-wide TokenManager between tests.

    Also provides a default ``SPEC_KITTY_SAAS_URL`` so the flow can
    construct the config without erroring. Tests that need to verify the
    missing-config path delete the env var explicitly.
    """
    monkeypatch.setenv("SPEC_KITTY_SAAS_URL", "https://saas.test")
    reset_token_manager()
    yield
    reset_token_manager()


def _make_session(
    email: str = "alice@example.com",
    team_name: str = "Team One",
    is_private_teamspace: bool = False,
    issuer_url: str | None = None,
) -> StoredSession:
    now = now_utc()
    return StoredSession(
        user_id="user-1",
        email=email,
        name="Alice",
        teams=[
            Team(
                id="t1",
                name=team_name,
                role="owner",
                is_private_teamspace=is_private_teamspace,
            )
        ],
        default_team_id="t1",
        access_token="access-xyz",
        refresh_token="refresh-xyz",
        session_id="sess-1",
        issued_at=now,
        access_token_expires_at=now + timedelta(hours=1),
        refresh_token_expires_at=now + timedelta(days=30),
        scope="offline_access",
        storage_backend="file",
        last_used_at=now,
        auth_method="authorization_code",
        issuer_url=issuer_url,
    )


# ---------------------------------------------------------------------------
# Help output
# ---------------------------------------------------------------------------


class TestAuthLoginHelp:
    """Verify the new command's help output does not mention legacy flags."""

    def test_help_does_not_mention_password(self):
        result = runner.invoke(app, ["login", "--help"])
        assert result.exit_code == 0
        stdout_lower = result.stdout.lower()
        assert "password" not in stdout_lower
        assert "username" not in stdout_lower

    def test_help_shows_new_flags(self):
        result = runner.invoke(app, ["login", "--help"])
        assert result.exit_code == 0
        plain = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
        assert "--headless" in plain
        assert "--force" in plain

    def test_help_describes_browser_flow(self):
        result = runner.invoke(app, ["login", "--help"])
        assert result.exit_code == 0
        assert "browser" in result.stdout.lower() or "oauth" in result.stdout.lower()


# ---------------------------------------------------------------------------
# Dispatch (browser vs headless)
# ---------------------------------------------------------------------------


class TestAuthLoginDispatch:
    def test_login_no_longer_calls_teamspace_mission_state_gate(self):
        """Phase 6 (issue #1288): identity acquisition is decoupled from
        TeamSpace mission-state readiness. The gate symbol must not be
        imported into the auth-login module and the command must not
        consult it. Sync / tracker / connect commands continue to gate
        themselves — that's their job, not auth's."""
        import specify_cli.cli.commands._auth_login as auth_login_module

        # The gate symbol must not be importable from the auth-login
        # module: even an indirect re-export would re-create the wrong
        # coupling.
        assert not hasattr(auth_login_module, "enforce_teamspace_mission_state_ready")

    def test_login_proceeds_even_if_teamspace_mission_state_is_blocked(self):
        """Belt-and-suspenders for the structural guarantee above: even
        if the gate were called somehow, blocking it must not block
        identity acquisition. Patches the gate to raise, then verifies
        the login impl never invokes it."""
        async def _noop_browser_flow(*_args, **_kwargs):
            return None

        with patch(
            "specify_cli.cli.commands._teamspace_mission_state_gate.enforce_teamspace_mission_state_ready",
            side_effect=AssertionError("auth login must not invoke the TeamSpace gate"),
        ), patch(
            "specify_cli.cli.commands._auth_login._run_browser_flow",
            new=AsyncMock(side_effect=_noop_browser_flow),
        ):
            result = runner.invoke(app, ["login"])

        assert result.exit_code == 0, result.stdout

    def test_default_dispatches_to_browser_flow(self):
        async def _noop(*args, **kwargs):
            return None

        with patch(
            "specify_cli.cli.commands._auth_login.get_token_manager"
        ) as mock_factory, patch(
            "specify_cli.cli.commands._auth_login._run_browser_flow",
            new=AsyncMock(side_effect=_noop),
        ) as mock_browser, patch(
            "specify_cli.cli.commands._auth_login._run_device_flow",
            new=AsyncMock(side_effect=_noop),
        ) as mock_device:
            mock_factory.return_value.is_authenticated = False
            result = runner.invoke(app, ["login"])

        assert result.exit_code == 0, result.stdout
        assert mock_browser.called
        assert not mock_device.called

    def test_headless_dispatches_to_device_flow(self):
        async def _noop(*args, **kwargs):
            return None

        with patch(
            "specify_cli.cli.commands._auth_login.get_token_manager"
        ) as mock_factory, patch(
            "specify_cli.cli.commands._auth_login._run_browser_flow",
            new=AsyncMock(side_effect=_noop),
        ) as mock_browser, patch(
            "specify_cli.cli.commands._auth_login._run_device_flow",
            new=AsyncMock(side_effect=_noop),
        ) as mock_device:
            mock_factory.return_value.is_authenticated = False
            result = runner.invoke(app, ["login", "--headless"])

        assert result.exit_code == 0, result.stdout
        assert mock_device.called
        assert not mock_browser.called


# ---------------------------------------------------------------------------
# Configuration errors
# ---------------------------------------------------------------------------


class TestAuthLoginConfigErrors:

    def test_missing_env_and_config_targets_packaged_default(self, monkeypatch, tmp_path):
        # #3406 FR-005, retargeted by #3980 (D-5 revised): with NEITHER
        # SPEC_KITTY_SAAS_URL nor a configured `[sync].server_url`, login no
        # longer refuses — the packaged default `https://team.spec-kitty.ai`
        # is the target (the #3980 acceptance criterion), and the browser flow
        # is handed exactly that URL.
        runtime_root = tmp_path / "runtime-root"
        runtime_root.mkdir()
        monkeypatch.setenv("SPEC_KITTY_HOME", str(runtime_root))
        monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)

        async def _noop(*_args, **_kwargs):
            return None

        with patch(
            "specify_cli.cli.commands._auth_login.get_token_manager"
        ) as mock_factory, patch(
            "specify_cli.cli.commands._auth_login._run_browser_flow",
            new=AsyncMock(side_effect=_noop),
        ) as mock_browser:
            mock_factory.return_value.is_authenticated = False
            result = runner.invoke(app, ["login"])

        assert result.exit_code == 0, result.stdout
        assert mock_browser.called
        # Login resolved the packaged default and handed it to the flow.
        assert mock_browser.call_args.args[1] == "https://team.spec-kitty.ai"

    def test_missing_env_uses_configured_sync_server_url(self, monkeypatch, tmp_path):
        # #3406 FR-005: the actual bug. When the env var is unset but the user
        # already set a server via `[sync].server_url` in the runtime root's
        # config.toml (the former `spec-kitty sync server <url>` writer died
        # with the sync transport, issue #5), login must use that configured
        # server_url (the same target sync used) instead of erroring.
        runtime_root = tmp_path / "runtime-root"
        runtime_root.mkdir(parents=True)
        monkeypatch.setenv("SPEC_KITTY_HOME", str(runtime_root))
        monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
        (runtime_root / "config.toml").write_text(
            '[sync]\nserver_url = "https://configured.example"\n', encoding="utf-8"
        )

        async def _noop(*_args, **_kwargs):
            return None

        with patch(
            "specify_cli.cli.commands._auth_login.get_token_manager"
        ) as mock_factory, patch(
            "specify_cli.cli.commands._auth_login._run_browser_flow",
            new=AsyncMock(side_effect=_noop),
        ) as mock_browser:
            mock_factory.return_value.is_authenticated = False
            result = runner.invoke(app, ["login"])

        assert result.exit_code == 0, result.stdout
        assert mock_browser.called
        # Login resolved the configured server_url and handed it to the flow.
        assert mock_browser.call_args.args[1] == "https://configured.example"

    def test_blank_configured_server_url_targets_packaged_default(self, monkeypatch, tmp_path):
        # #182 squad MAJOR, retargeted by #3980: `server_url = ""` names no
        # endpoint — it is *no opinion* — so login targets the packaged
        # default exactly as it does when `[sync].server_url` is absent,
        # never treating the blank string as a configured (but empty)
        # endpoint.
        runtime_root = tmp_path / "runtime-root"
        runtime_root.mkdir(parents=True)
        monkeypatch.setenv("SPEC_KITTY_HOME", str(runtime_root))
        monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
        (runtime_root / "config.toml").write_text(
            '[sync]\nserver_url = ""\n', encoding="utf-8"
        )

        async def _noop(*_args, **_kwargs):
            return None

        with patch(
            "specify_cli.cli.commands._auth_login.get_token_manager"
        ) as mock_factory, patch(
            "specify_cli.cli.commands._auth_login._run_browser_flow",
            new=AsyncMock(side_effect=_noop),
        ) as mock_browser:
            mock_factory.return_value.is_authenticated = False
            result = runner.invoke(app, ["login"])

        assert result.exit_code == 0, result.stdout
        assert mock_browser.called
        # The blank value is no opinion: the packaged default wins, and the
        # blank string is never handed to the flow as a configured endpoint.
        assert mock_browser.call_args.args[1] == "https://team.spec-kitty.ai"


class TestAuthLoginSaasLineRendering:
    def test_saas_line_renders_server_url_containing_bracket_markup(
        self, monkeypatch, tmp_path
    ):
        """#202: ``_run_browser_flow`` interpolated the configured
        ``server_url`` into a Rich ``[dim]`` line unescaped, so a value
        containing a closing-tag-like substring (``https://x.test[/]``) raised
        ``rich.markup.MarkupError`` out of ``console.print`` and crashed login
        before the OAuth flow could start. The URL must render verbatim."""
        bracketed = "https://x.test[/]"
        runtime_root = tmp_path / "runtime-root"
        runtime_root.mkdir(parents=True)
        monkeypatch.setenv("SPEC_KITTY_HOME", str(runtime_root))
        monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
        (runtime_root / "config.toml").write_text(
            f'[sync]\nserver_url = "{bracketed}"\n', encoding="utf-8"
        )

        async def _noop_login(*_args, **_kwargs):
            return _make_session()

        with patch(
            "specify_cli.cli.commands._auth_login.get_token_manager"
        ) as mock_factory, patch(
            "specify_cli.auth.flows.authorization_code.AuthorizationCodeFlow"
        ) as mock_flow_cls:
            mock_factory.return_value.is_authenticated = False
            mock_flow_cls.return_value.login = AsyncMock(side_effect=_noop_login)
            result = runner.invoke(app, ["login"])

        assert result.exit_code == 0, result.stdout
        # Rendered verbatim — no MarkupError, no swallowed markup tags.
        assert f"SaaS: {bracketed}" in result.stdout


class TestAuthLoginErrorMessageEscaping:
    """#526: exception text printed on login error paths can carry a raw,
    server-controlled body (e.g. a non-200 token-exchange response). Unescaped,
    a value containing a closing-tag-like substring raises
    ``rich.errors.MarkupError`` out of ``console.print`` instead of a clean
    non-zero exit with a readable diagnostic."""

    @pytest.mark.parametrize(
        ("headless", "flow_class", "error_type", "expected_prefix"),
        [
            (
                False,
                "specify_cli.auth.flows.authorization_code.AuthorizationCodeFlow",
                CallbackValidationError,
                "Callback validation failed",
            ),
            (
                False,
                "specify_cli.auth.flows.authorization_code.AuthorizationCodeFlow",
                BrowserLaunchError,
                "Could not launch browser",
            ),
            (
                False,
                "specify_cli.auth.flows.authorization_code.AuthorizationCodeFlow",
                AuthenticationError,
                "Authentication failed",
            ),
            (
                True,
                "specify_cli.auth.flows.device_code.DeviceCodeFlow",
                AuthenticationError,
                "Device flow failed",
            ),
        ],
        ids=("callback-validation", "browser-launch", "browser-auth", "device-auth"),
    )
    def test_markup_like_exception_text_does_not_crash(
        self,
        monkeypatch,
        tmp_path,
        headless,
        flow_class,
        error_type,
        expected_prefix,
    ):
        runtime_root = tmp_path / "runtime-root"
        runtime_root.mkdir(parents=True)
        monkeypatch.setenv("SPEC_KITTY_HOME", str(runtime_root))
        monkeypatch.setenv("SPEC_KITTY_SAAS_URL", "https://saas.test")

        hostile_body = "Token exchange failed: HTTP 400 - bad [/] token"

        async def _raise_auth_error(*_args, **_kwargs):
            raise error_type(hostile_body)

        with patch(
            "specify_cli.cli.commands._auth_login.get_token_manager"
        ) as mock_factory, patch(flow_class) as mock_flow_cls:
            mock_factory.return_value.is_authenticated = False
            mock_flow_cls.return_value.login = AsyncMock(
                side_effect=_raise_auth_error
            )
            args = ["login", "--headless"] if headless else ["login"]
            result = runner.invoke(app, args)

        # A clean non-zero exit, not an unhandled MarkupError traceback.
        assert result.exit_code == 1, result.stdout
        assert "MarkupError" not in result.stdout
        assert expected_prefix in result.stdout
        assert hostile_body in result.stdout


# ---------------------------------------------------------------------------
# Already-authenticated / --force behavior
# ---------------------------------------------------------------------------


class TestAuthLoginAlreadyAuthenticated:

    def test_shows_friendly_message_when_already_logged_in(self):
        existing = _make_session()

        async def _noop(*args, **kwargs):
            return None

        with patch(
            "specify_cli.cli.commands._auth_login.get_token_manager"
        ) as mock_factory, patch(
            "specify_cli.cli.commands._auth_login._run_browser_flow",
            new=AsyncMock(side_effect=_noop),
        ) as mock_browser:
            mock_tm = mock_factory.return_value
            mock_tm.is_authenticated = True
            mock_tm.get_current_session.return_value = existing

            result = runner.invoke(app, ["login"])

        assert result.exit_code == 0, result.stdout
        assert "Already logged in" in result.stdout
        assert existing.email in result.stdout
        assert not mock_browser.called

    def test_renders_bracket_markup_in_existing_session_email(self):
        existing = _make_session(email="alice[/]@example.com")

        with patch(
            "specify_cli.cli.commands._auth_login.get_token_manager"
        ) as mock_factory:
            mock_tm = mock_factory.return_value
            mock_tm.is_authenticated = True
            mock_tm.get_current_session.return_value = existing

            result = runner.invoke(app, ["login"])

        assert result.exit_code == 0, result.stdout
        assert "Already logged in as alice[/]@example.com" in result.stdout
        assert "MarkupError" not in result.stdout

    def test_renders_bracket_markup_in_success_email(self):
        session = _make_session(email="alice[/]@example.com")

        async def _login(*_args, **_kwargs):
            return session

        with patch(
            "specify_cli.cli.commands._auth_login.get_token_manager"
        ) as mock_factory, patch(
            "specify_cli.auth.flows.authorization_code.AuthorizationCodeFlow"
        ) as mock_flow_cls:
            mock_factory.return_value.is_authenticated = False
            mock_flow_cls.return_value.login = AsyncMock(side_effect=_login)
            result = runner.invoke(app, ["login"])

        assert result.exit_code == 0, result.stdout
        assert "Authenticated as alice[/]@example.com" in result.stdout
        assert "MarkupError" not in result.stdout

    def test_renders_bracket_markup_in_private_team_name_with_suffix(self):
        session = _make_session(
            team_name="A[/]C", is_private_teamspace=True
        )

        async def _login(*_args, **_kwargs):
            return session

        with patch(
            "specify_cli.cli.commands._auth_login.get_token_manager"
        ) as mock_factory, patch(
            "specify_cli.auth.flows.authorization_code.AuthorizationCodeFlow"
        ) as mock_flow_cls:
            mock_factory.return_value.is_authenticated = False
            mock_flow_cls.return_value.login = AsyncMock(side_effect=_login)
            result = runner.invoke(app, ["login"])

        assert result.exit_code == 0, result.stdout
        assert "Default team: A[/]C [Private Teamspace]" in result.stdout
        assert "MarkupError" not in result.stdout

    def test_success_output_strips_terminal_controls_from_identity_bytes(self):
        safe_name = "Zoë Ölafsdóttir 日本語 🐱"
        hostile_suffix = "\x1b[2J\x1b]0;x\x07\x1b"
        session = _make_session(
            email=f"{safe_name}{hostile_suffix}",
            team_name=f"{safe_name}{hostile_suffix}",
        )

        async def _login(*_args, **_kwargs):
            return session

        with patch(
            "specify_cli.cli.commands._auth_login.get_token_manager"
        ) as mock_factory, patch(
            "specify_cli.auth.flows.authorization_code.AuthorizationCodeFlow"
        ) as mock_flow_cls:
            mock_factory.return_value.is_authenticated = False
            mock_flow_cls.return_value.login = AsyncMock(side_effect=_login)
            result = runner.invoke(app, ["login"])

        emitted = result.stdout_bytes
        assert result.exit_code == 0, result.stdout
        assert safe_name.encode("utf-8") in emitted
        assert b"\x1b" not in emitted
        assert b"[2J" not in emitted
        assert b"]0;x" not in emitted

    def test_force_reauthenticates_even_when_logged_in(self):
        existing = _make_session()

        async def _noop(*args, **kwargs):
            return None

        with patch(
            "specify_cli.cli.commands._auth_login.get_token_manager"
        ) as mock_factory, patch(
            "specify_cli.cli.commands._auth_login._run_browser_flow",
            new=AsyncMock(side_effect=_noop),
        ) as mock_browser:
            mock_tm = mock_factory.return_value
            mock_tm.is_authenticated = True
            mock_tm.get_current_session.return_value = existing

            result = runner.invoke(app, ["login", "--force"])

        assert result.exit_code == 0, result.stdout
        assert mock_browser.called
        mock_tm.clear_session.assert_called_once()

    def test_fresh_login_proceeds_when_not_authenticated(self):
        async def _noop(*args, **kwargs):
            return None

        with patch(
            "specify_cli.cli.commands._auth_login.get_token_manager"
        ) as mock_factory, patch(
            "specify_cli.cli.commands._auth_login._run_browser_flow",
            new=AsyncMock(side_effect=_noop),
        ) as mock_browser:
            mock_tm = mock_factory.return_value
            mock_tm.is_authenticated = False
            mock_tm.get_current_session.return_value = None

            result = runner.invoke(app, ["login"])

        assert result.exit_code == 0, result.stdout
        assert mock_browser.called


# ---------------------------------------------------------------------------
# Pre-login target diagnostics (#4259)
# ---------------------------------------------------------------------------


def _flat(output: str) -> str:
    """Strip ANSI styling so assertions see the rendered text."""
    return re.sub(r"\x1b\[[0-9;]*m", "", output)


class TestAuthLoginTargetDiagnostics:
    """#4259: before any flow starts, login prints the resolved target *and*
    its configuration source, and warns — never rejects — on a noncanonical
    first-party endpoint. Custom/self-hosted endpoints are labelled custom
    and never rewritten."""

    def test_prints_config_provenance_before_flow(self, monkeypatch, tmp_path):
        runtime_root = tmp_path / "runtime-root"
        runtime_root.mkdir(parents=True)
        monkeypatch.setenv("SPEC_KITTY_HOME", str(runtime_root))
        monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
        (runtime_root / "config.toml").write_text(
            '[sync]\nserver_url = "https://configured.example"\n', encoding="utf-8"
        )

        async def _noop_login(*_args, **_kwargs):
            return _make_session()

        with patch(
            "specify_cli.cli.commands._auth_login.get_token_manager"
        ) as mock_factory, patch(
            "specify_cli.auth.flows.authorization_code.AuthorizationCodeFlow"
        ) as mock_flow_cls:
            mock_factory.return_value.is_authenticated = False
            mock_flow_cls.return_value.login = AsyncMock(side_effect=_noop_login)
            result = runner.invoke(app, ["login"])

        assert result.exit_code == 0, result.stdout
        flat = _flat(result.stdout)
        assert "SaaS: https://configured.example" in flat
        assert "(from config.toml [sync].server_url)" in flat
        # The diagnostic precedes the flow, giving the operator time to abort.
        assert flat.index("SaaS: https://configured.example") < flat.index(
            "Opening browser"
        )

    def test_prints_env_provenance_for_env_target(self):
        async def _noop(*_args, **_kwargs):
            return None

        with patch(
            "specify_cli.cli.commands._auth_login.get_token_manager"
        ) as mock_factory, patch(
            "specify_cli.cli.commands._auth_login._run_browser_flow",
            new=AsyncMock(side_effect=_noop),
        ):
            mock_factory.return_value.is_authenticated = False
            result = runner.invoke(app, ["login"])

        assert result.exit_code == 0, result.stdout
        flat = _flat(result.stdout)
        assert "SaaS: https://saas.test" in flat
        assert "(from SPEC_KITTY_SAAS_URL)" in flat

    def test_warns_on_retired_first_party_target_without_rejecting(
        self, monkeypatch, tmp_path
    ):
        """The #4259 stale shape: a saved retired first-party target warns
        loudly (naming the canonical endpoint and the upgrade remedy) but the
        flow still proceeds against the configured target."""
        runtime_root = tmp_path / "runtime-root"
        runtime_root.mkdir(parents=True)
        monkeypatch.setenv("SPEC_KITTY_HOME", str(runtime_root))
        monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
        (runtime_root / "config.toml").write_text(
            '[sync]\nserver_url = "https://app.spec-kitty.ai"\n', encoding="utf-8"
        )

        async def _noop(*_args, **_kwargs):
            return None

        with patch(
            "specify_cli.cli.commands._auth_login.get_token_manager"
        ) as mock_factory, patch(
            "specify_cli.cli.commands._auth_login._run_browser_flow",
            new=AsyncMock(side_effect=_noop),
        ) as mock_browser:
            mock_factory.return_value.is_authenticated = False
            result = runner.invoke(app, ["login"])

        assert result.exit_code == 0, result.stdout
        flat = _flat(result.stdout)
        assert "retired first-party endpoint" in flat
        assert "https://team.spec-kitty.ai" in flat
        assert "spec-kitty upgrade" in flat
        # Warned, not rejected: the flow still ran against the configured target.
        assert mock_browser.called
        assert mock_browser.call_args.args[1] == "https://app.spec-kitty.ai"

    def test_labels_custom_endpoint_without_warning(self):
        """A self-hosted endpoint is supported: labelled custom, never warned
        at, never rewritten (#4259 agreed scope)."""
        async def _noop(*_args, **_kwargs):
            return None

        with patch(
            "specify_cli.cli.commands._auth_login.get_token_manager"
        ) as mock_factory, patch(
            "specify_cli.cli.commands._auth_login._run_browser_flow",
            new=AsyncMock(side_effect=_noop),
        ) as mock_browser:
            mock_factory.return_value.is_authenticated = False
            result = runner.invoke(app, ["login"])

        assert result.exit_code == 0, result.stdout
        flat = _flat(result.stdout)
        assert "Custom endpoint" in flat
        assert "https://team.spec-kitty.ai" in flat
        assert "noncanonical" not in flat
        assert "retired" not in flat
        assert mock_browser.called

    def test_canonical_target_prints_no_warning(self, monkeypatch):
        monkeypatch.setenv("SPEC_KITTY_SAAS_URL", "https://team.spec-kitty.ai")

        async def _noop(*_args, **_kwargs):
            return None

        with patch(
            "specify_cli.cli.commands._auth_login.get_token_manager"
        ) as mock_factory, patch(
            "specify_cli.cli.commands._auth_login._run_browser_flow",
            new=AsyncMock(side_effect=_noop),
        ):
            mock_factory.return_value.is_authenticated = False
            result = runner.invoke(app, ["login"])

        assert result.exit_code == 0, result.stdout
        flat = _flat(result.stdout)
        assert "SaaS: https://team.spec-kitty.ai" in flat
        assert "retired" not in flat
        assert "noncanonical" not in flat
        assert "Custom endpoint" not in flat


# ---------------------------------------------------------------------------
# Issuer boundary for an existing session (#4259)
# ---------------------------------------------------------------------------


class TestAuthLoginIssuerBoundary:
    """A stored session minted for a different endpoint is never relabeled as
    valid for the resolved target and its bearer is never forwarded: plain
    login requires fresh authentication (--force), mirroring the
    non-interactive #234 guard in saas_client.auth."""

    def test_mismatched_issuer_requires_fresh_authentication(self):
        """The exact #4259 shape: a session minted against the retired
        first-party endpoint while the resolved target is another server."""
        existing = _make_session(issuer_url="https://app.spec-kitty.ai")

        async def _fail(*_args, **_kwargs):
            raise AssertionError("login must not forward an old-host session to a new target")

        with patch(
            "specify_cli.cli.commands._auth_login.get_token_manager"
        ) as mock_factory, patch(
            "specify_cli.cli.commands._auth_login._run_browser_flow",
            new=AsyncMock(side_effect=_fail),
        ) as mock_browser:
            mock_tm = mock_factory.return_value
            mock_tm.is_authenticated = True
            mock_tm.get_current_session.return_value = existing

            result = runner.invoke(app, ["login"])

        # #4265 (folded by WP05, #4755): a refusal is not success -- exit 1
        # so `spec-kitty auth login && ...` chains cannot read this as a
        # completed login.
        assert result.exit_code == 1, result.stdout
        flat = _flat(result.stdout)
        assert "Session is for https://app.spec-kitty.ai" in flat
        assert "SPEC_KITTY_SAAS_URL now points at https://saas.test" in flat
        assert "fresh authentication is required" in flat
        # NOT reported as a valid login for the resolved target, and no
        # credentials were forwarded anywhere.
        assert "Already logged in" not in flat
        assert not mock_browser.called

    def test_matching_issuer_still_shows_already_logged_in(self):
        existing = _make_session(issuer_url="https://saas.test")

        async def _noop(*_args, **_kwargs):
            return None

        with patch(
            "specify_cli.cli.commands._auth_login.get_token_manager"
        ) as mock_factory, patch(
            "specify_cli.cli.commands._auth_login._run_browser_flow",
            new=AsyncMock(side_effect=_noop),
        ) as mock_browser:
            mock_tm = mock_factory.return_value
            mock_tm.is_authenticated = True
            mock_tm.get_current_session.return_value = existing

            result = runner.invoke(app, ["login"])

        assert result.exit_code == 0, result.stdout
        assert "Already logged in" in result.stdout
        assert not mock_browser.called

    def test_force_mints_fresh_credentials_on_mismatch(self):
        """--force re-authenticates against the resolved target — the one
        sanctioned way past the boundary, minting NEW credentials rather
        than relabeling the old-host session."""
        existing = _make_session(issuer_url="https://app.spec-kitty.ai")

        async def _noop(*_args, **_kwargs):
            return None

        with patch(
            "specify_cli.cli.commands._auth_login.get_token_manager"
        ) as mock_factory, patch(
            "specify_cli.cli.commands._auth_login._run_browser_flow",
            new=AsyncMock(side_effect=_noop),
        ) as mock_browser:
            mock_tm = mock_factory.return_value
            mock_tm.is_authenticated = True
            mock_tm.get_current_session.return_value = existing

            result = runner.invoke(app, ["login", "--force"])

        assert result.exit_code == 0, result.stdout
        assert mock_browser.called
        mock_tm.clear_session.assert_called_once()
