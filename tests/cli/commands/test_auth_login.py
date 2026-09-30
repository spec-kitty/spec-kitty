"""CliRunner tests for ``spec-kitty auth login`` (feature 080, WP04 T027).

These tests exercise the real Typer ``app`` exported by
``specify_cli.cli.commands.auth`` via :class:`typer.testing.CliRunner`.
The keyring edge (``SecureStorage.from_environment``) is replaced by an
in-memory :class:`FakeSecureStorage` for every test, and ``SPEC_KITTY_HOME``
is pinned per test (``canonical_home``). Target-resolution and issuer
contracts run the real ``AuthorizationCodeFlow`` with only randomness, the
loopback socket, the browser and the network faked (``_oauth_boundary``).

Key behaviors under test:

- ``--help`` does not mention ``password`` or ``username``.
- Missing ``SPEC_KITTY_SAAS_URL`` surfaces a clear configuration error.
- The configured server URL is what the network flow talks to and what the
  persisted session is bound to.
- ``--force`` mints fresh credentials for the resolved target.
- Already-authenticated users without ``--force`` see a friendly message.

Browser-vs-headless dispatch and ``--force`` session reset are guarded end to
end by ``tests/auth/integration/test_browser_login_e2e.py`` and
``test_headless_login_e2e.py``.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from kernel.clock import timedelta, now_utc
import re
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from typer.testing import CliRunner

from specify_cli.auth import reset_token_manager
from specify_cli.auth.errors import (
    AuthenticationError,
    BrowserLaunchError,
    CallbackValidationError,
)
from specify_cli.auth.loopback.state import PKCEState
from specify_cli.auth.session import StoredSession, Team
from specify_cli.cli.commands.auth import app

from tests.auth.integration.conftest import FakeSecureStorage


pytestmark = [pytest.mark.integration]

runner = CliRunner()


_FROM_ENVIRONMENT = "specify_cli.auth.secure_storage.SecureStorage.from_environment"
_FLOW_MODULE = "specify_cli.auth.flows.authorization_code"


@pytest.fixture
def storage() -> FakeSecureStorage:
    """The in-memory keyring every test in this module logs in against."""
    return FakeSecureStorage()


@pytest.fixture(autouse=True)
def _reset_tm(monkeypatch, canonical_home, storage):
    """Isolate auth state per test and reset the process-wide TokenManager.

    ``canonical_home`` pins ``SPEC_KITTY_HOME`` under ``tmp_path`` (tests that
    need a specific runtime root re-pin it), and the keyring edge is replaced
    by :func:`storage`, so no test reads a session another test (or the host)
    left behind. Also provides a default ``SPEC_KITTY_SAAS_URL``; tests of the
    missing-config path delete it explicitly.
    """
    monkeypatch.setenv("SPEC_KITTY_SAAS_URL", "https://saas.test")
    reset_token_manager()
    with patch(_FROM_ENVIRONMENT, return_value=storage):
        yield
    reset_token_manager()


@dataclass
class _OAuthEdge:
    """What crossed the faked network/browser edge during one login."""

    launched_urls: list[str] = field(default_factory=list)
    requested_urls: list[str] = field(default_factory=list)


def _http_ok(body: dict[str, Any]) -> MagicMock:
    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.text = str(body)
    response.json = MagicMock(return_value=body)
    return response


_FRESH_TOKEN_BODY = {
    "access_token": "at_fresh_login",
    "refresh_token": "rt_fresh_login",
    "expires_in": 3600,
    "refresh_token_expires_at": "2099-01-01T00:00:00+00:00",
    "scope": "offline_access",
    "session_id": "sess_fresh_login",
    "token_type": "Bearer",
}
_ME_BODY = {
    "user_id": "u_alice",
    "email": "alice@example.com",
    "name": "Alice Developer",
    "teams": [{"id": "tm_acme", "name": "Acme Corp", "role": "admin"}],
    "default_team_id": "tm_acme",
    "session_id": "sess_fresh_login",
}


@contextlib.contextmanager
def _oauth_boundary() -> Iterator[_OAuthEdge]:
    """Run the REAL ``AuthorizationCodeFlow``; fake only its true edges.

    PKCE randomness (``StateManager``), the loopback socket
    (``CallbackServer``), the browser (``BrowserLauncher.launch``) and the
    network (``PublicHttpClient``) are replaced; every URL that reaches the
    browser or the network is recorded on the yielded :class:`_OAuthEdge`.
    """
    now = now_utc()
    pkce = PKCEState(
        state="auth-login-test-state-nonce-0123456789",
        code_verifier="auth-login-test-verifier-0123456789abcdef",
        code_challenge="auth-login-test-challenge-0123456789abcdef",
        code_challenge_method="S256",
        created_at=now,
        expires_at=now + timedelta(minutes=5),
    )
    edge = _OAuthEdge()

    async def _post(url: str, **_kwargs: Any) -> MagicMock:
        edge.requested_urls.append(url)
        return _http_ok(_FRESH_TOKEN_BODY)

    async def _get(url: str, **_kwargs: Any) -> MagicMock:
        edge.requested_urls.append(url)
        return _http_ok(_ME_BODY)

    def _launch(url: str) -> bool:
        edge.launched_urls.append(url)
        return True

    with (
        patch(f"{_FLOW_MODULE}.StateManager") as state_manager_cls,
        patch(f"{_FLOW_MODULE}.CallbackServer") as callback_server_cls,
        patch(f"{_FLOW_MODULE}.BrowserLauncher.launch", side_effect=_launch),
        patch(f"{_FLOW_MODULE}.PublicHttpClient") as client_cls,
    ):
        state_manager_cls.return_value.generate.return_value = pkce
        callback_server_cls.return_value.start.return_value = "http://127.0.0.1:28888/callback"
        callback_server_cls.return_value.wait_for_callback = AsyncMock(return_value={"code": "authz-code", "state": pkce.state})
        client = AsyncMock()
        client.post = AsyncMock(side_effect=_post)
        client.get = AsyncMock(side_effect=_get)
        client_cls.return_value.__aenter__.return_value = client
        yield edge


def _assert_flow_talked_only_to(edge: _OAuthEdge, server_url: str) -> None:
    """The browser and every network call went to *server_url*, and nowhere else."""
    assert [url.split("?", 1)[0] for url in edge.launched_urls] == [f"{server_url}/oauth/authorize"]
    assert edge.requested_urls == [f"{server_url}/oauth/token", f"{server_url}/api/v1/me"]


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

        with (
            patch(
                "specify_cli.cli.commands._teamspace_mission_state_gate.enforce_teamspace_mission_state_ready",
                side_effect=AssertionError("auth login must not invoke the TeamSpace gate"),
            ),
            patch(
                "specify_cli.cli.commands._auth_login._run_browser_flow",
                new=AsyncMock(side_effect=_noop_browser_flow),
            ),
        ):
            result = runner.invoke(app, ["login"])

        assert result.exit_code == 0, result.stdout


# ---------------------------------------------------------------------------
# Configuration errors
# ---------------------------------------------------------------------------


class TestAuthLoginConfigErrors:
    def test_missing_env_and_config_refuses_with_guidance(self, monkeypatch, tmp_path):
        # Endpoint opt-in (FR-011/FR-012, reversing #3980 D-5): with NEITHER
        # SPEC_KITTY_SAAS_URL nor a configured `[sync].server_url`, login
        # once again refuses with setup guidance (US4 AS1) — no browser flow
        # is ever constructed, so no HTTP call is made.
        runtime_root = tmp_path / "runtime-root"
        runtime_root.mkdir()
        monkeypatch.setenv("SPEC_KITTY_HOME", str(runtime_root))
        monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)

        async def _noop(*_args, **_kwargs):
            return None

        with (
            patch("specify_cli.cli.commands._auth_login.get_token_manager") as mock_factory,
            patch(
                "specify_cli.cli.commands._auth_login._run_browser_flow",
                new=AsyncMock(side_effect=_noop),
            ) as mock_browser,
        ):
            mock_factory.return_value.is_authenticated = False
            result = runner.invoke(app, ["login"])

        assert result.exit_code != 0, result.stdout
        assert "No hosted endpoint configured" in result.stdout
        assert not mock_browser.called

    def test_missing_env_uses_configured_sync_server_url(self, monkeypatch, tmp_path, storage):
        # #3406 FR-005: the actual bug. When the env var is unset but the user
        # already set a server via `[sync].server_url` in the runtime root's
        # config.toml (the former `spec-kitty sync server <url>` writer died
        # with the sync transport, issue #5), login must use that configured
        # server_url (the same target sync used) instead of erroring.
        runtime_root = tmp_path / "runtime-root"
        runtime_root.mkdir(parents=True)
        monkeypatch.setenv("SPEC_KITTY_HOME", str(runtime_root))
        monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
        (runtime_root / "config.toml").write_text('[sync]\nserver_url = "https://configured.example"\n', encoding="utf-8")

        with _oauth_boundary() as edge:
            result = runner.invoke(app, ["login"])

        assert result.exit_code == 0, result.stdout
        # The real flow talked to the configured server, and the persisted
        # session is bound to it.
        _assert_flow_talked_only_to(edge, "https://configured.example")
        assert [session.issuer_url for session in storage.writes] == ["https://configured.example"]

    def test_blank_configured_server_url_refuses_with_guidance(self, monkeypatch, tmp_path):
        # #182 squad MAJOR, retargeted by endpoint opt-in (FR-011): `server_url
        # = ""` names no endpoint — it is *no opinion* — so with no env value
        # either, login refuses with the same guidance it gives when
        # `[sync].server_url` is absent entirely, never treating the blank
        # string as a configured (but empty) endpoint.
        runtime_root = tmp_path / "runtime-root"
        runtime_root.mkdir(parents=True)
        monkeypatch.setenv("SPEC_KITTY_HOME", str(runtime_root))
        monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
        (runtime_root / "config.toml").write_text('[sync]\nserver_url = ""\n', encoding="utf-8")

        async def _noop(*_args, **_kwargs):
            return None

        with (
            patch("specify_cli.cli.commands._auth_login.get_token_manager") as mock_factory,
            patch(
                "specify_cli.cli.commands._auth_login._run_browser_flow",
                new=AsyncMock(side_effect=_noop),
            ) as mock_browser,
        ):
            mock_factory.return_value.is_authenticated = False
            result = runner.invoke(app, ["login"])

        assert result.exit_code != 0, result.stdout
        assert "No hosted endpoint configured" in result.stdout
        assert not mock_browser.called


class TestAuthLoginSaasLineRendering:
    def test_saas_line_renders_server_url_containing_bracket_markup(self, monkeypatch, tmp_path):
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
        (runtime_root / "config.toml").write_text(f'[sync]\nserver_url = "{bracketed}"\n', encoding="utf-8")

        async def _noop_login(*_args, **_kwargs):
            return _make_session()

        with (
            patch("specify_cli.cli.commands._auth_login.get_token_manager") as mock_factory,
            patch("specify_cli.auth.flows.authorization_code.AuthorizationCodeFlow") as mock_flow_cls,
        ):
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

        with patch("specify_cli.cli.commands._auth_login.get_token_manager") as mock_factory, patch(flow_class) as mock_flow_cls:
            mock_factory.return_value.is_authenticated = False
            mock_flow_cls.return_value.login = AsyncMock(side_effect=_raise_auth_error)
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

        with (
            patch("specify_cli.cli.commands._auth_login.get_token_manager") as mock_factory,
            patch(
                "specify_cli.cli.commands._auth_login._run_browser_flow",
                new=AsyncMock(side_effect=_noop),
            ) as mock_browser,
        ):
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

        with patch("specify_cli.cli.commands._auth_login.get_token_manager") as mock_factory:
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

        with (
            patch("specify_cli.cli.commands._auth_login.get_token_manager") as mock_factory,
            patch("specify_cli.auth.flows.authorization_code.AuthorizationCodeFlow") as mock_flow_cls,
        ):
            mock_factory.return_value.is_authenticated = False
            mock_flow_cls.return_value.login = AsyncMock(side_effect=_login)
            result = runner.invoke(app, ["login"])

        assert result.exit_code == 0, result.stdout
        assert "Authenticated as alice[/]@example.com" in result.stdout
        assert "MarkupError" not in result.stdout

    def test_renders_bracket_markup_in_private_team_name_with_suffix(self):
        session = _make_session(team_name="A[/]C", is_private_teamspace=True)

        async def _login(*_args, **_kwargs):
            return session

        with (
            patch("specify_cli.cli.commands._auth_login.get_token_manager") as mock_factory,
            patch("specify_cli.auth.flows.authorization_code.AuthorizationCodeFlow") as mock_flow_cls,
        ):
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

        with (
            patch("specify_cli.cli.commands._auth_login.get_token_manager") as mock_factory,
            patch("specify_cli.auth.flows.authorization_code.AuthorizationCodeFlow") as mock_flow_cls,
        ):
            mock_factory.return_value.is_authenticated = False
            mock_flow_cls.return_value.login = AsyncMock(side_effect=_login)
            result = runner.invoke(app, ["login"])

        emitted = result.stdout_bytes
        assert result.exit_code == 0, result.stdout
        assert safe_name.encode("utf-8") in emitted
        assert b"\x1b" not in emitted
        assert b"[2J" not in emitted
        assert b"]0;x" not in emitted

    def test_fresh_login_proceeds_when_not_authenticated(self):
        async def _noop(*args, **kwargs):
            return None

        with (
            patch("specify_cli.cli.commands._auth_login.get_token_manager") as mock_factory,
            patch(
                "specify_cli.cli.commands._auth_login._run_browser_flow",
                new=AsyncMock(side_effect=_noop),
            ) as mock_browser,
        ):
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
        (runtime_root / "config.toml").write_text('[sync]\nserver_url = "https://configured.example"\n', encoding="utf-8")

        async def _noop_login(*_args, **_kwargs):
            return _make_session()

        with (
            patch("specify_cli.cli.commands._auth_login.get_token_manager") as mock_factory,
            patch("specify_cli.auth.flows.authorization_code.AuthorizationCodeFlow") as mock_flow_cls,
        ):
            mock_factory.return_value.is_authenticated = False
            mock_flow_cls.return_value.login = AsyncMock(side_effect=_noop_login)
            result = runner.invoke(app, ["login"])

        assert result.exit_code == 0, result.stdout
        flat = _flat(result.stdout)
        assert "SaaS: https://configured.example" in flat
        assert "(from config.toml [sync].server_url)" in flat
        # The diagnostic precedes the flow, giving the operator time to abort.
        assert flat.index("SaaS: https://configured.example") < flat.index("Opening browser")

    def test_prints_env_provenance_for_env_target(self):
        async def _noop(*_args, **_kwargs):
            return None

        with (
            patch("specify_cli.cli.commands._auth_login.get_token_manager") as mock_factory,
            patch(
                "specify_cli.cli.commands._auth_login._run_browser_flow",
                new=AsyncMock(side_effect=_noop),
            ),
        ):
            mock_factory.return_value.is_authenticated = False
            result = runner.invoke(app, ["login"])

        assert result.exit_code == 0, result.stdout
        flat = _flat(result.stdout)
        assert "SaaS: https://saas.test" in flat
        assert "(from SPEC_KITTY_SAAS_URL)" in flat

    def test_warns_on_retired_first_party_target_without_rejecting(self, monkeypatch, tmp_path, storage):
        """The #4259 stale shape: a saved retired first-party target warns
        loudly (naming the canonical endpoint and the upgrade remedy) but the
        flow still proceeds against the configured target."""
        runtime_root = tmp_path / "runtime-root"
        runtime_root.mkdir(parents=True)
        monkeypatch.setenv("SPEC_KITTY_HOME", str(runtime_root))
        monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
        (runtime_root / "config.toml").write_text('[sync]\nserver_url = "https://app.spec-kitty.ai"\n', encoding="utf-8")

        with _oauth_boundary() as edge:
            result = runner.invoke(app, ["login"])

        assert result.exit_code == 0, result.stdout
        flat = _flat(result.stdout)
        assert "retired first-party endpoint" in flat
        assert "https://team.spec-kitty.ai" in flat
        assert "spec-kitty upgrade" in flat
        # Warned, not rejected and not rewritten: the real flow ran against the
        # configured target and the session is bound to it.
        _assert_flow_talked_only_to(edge, "https://app.spec-kitty.ai")
        assert [session.issuer_url for session in storage.writes] == ["https://app.spec-kitty.ai"]

    def test_labels_custom_endpoint_without_warning(self):
        """A self-hosted endpoint is supported: labelled custom, never warned
        at, never rewritten (#4259 agreed scope)."""

        async def _noop(*_args, **_kwargs):
            return None

        with (
            patch("specify_cli.cli.commands._auth_login.get_token_manager") as mock_factory,
            patch(
                "specify_cli.cli.commands._auth_login._run_browser_flow",
                new=AsyncMock(side_effect=_noop),
            ) as mock_browser,
        ):
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

        with (
            patch("specify_cli.cli.commands._auth_login.get_token_manager") as mock_factory,
            patch(
                "specify_cli.cli.commands._auth_login._run_browser_flow",
                new=AsyncMock(side_effect=_noop),
            ),
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

        with (
            patch("specify_cli.cli.commands._auth_login.get_token_manager") as mock_factory,
            patch(
                "specify_cli.cli.commands._auth_login._run_browser_flow",
                new=AsyncMock(side_effect=_fail),
            ) as mock_browser,
        ):
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

        with (
            patch("specify_cli.cli.commands._auth_login.get_token_manager") as mock_factory,
            patch(
                "specify_cli.cli.commands._auth_login._run_browser_flow",
                new=AsyncMock(side_effect=_noop),
            ) as mock_browser,
        ):
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
        stale = _make_session(issuer_url="https://app.spec-kitty.ai")
        keyring = FakeSecureStorage(initial=stale)

        with patch(_FROM_ENVIRONMENT, return_value=keyring), _oauth_boundary() as edge:
            result = runner.invoke(app, ["login", "--force"])

        assert result.exit_code == 0, result.stdout
        # The old-host session was dropped and exactly one fresh session was
        # persisted, minted by the resolved target (SPEC_KITTY_SAAS_URL).
        assert keyring.deletes >= 1
        _assert_flow_talked_only_to(edge, "https://saas.test")
        assert [(s.issuer_url, s.access_token) for s in keyring.writes] == [("https://saas.test", "at_fresh_login")]
        assert keyring.read() is keyring.writes[0]
        assert stale.access_token not in result.stdout
