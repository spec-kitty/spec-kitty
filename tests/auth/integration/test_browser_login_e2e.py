"""E2E test for ``spec-kitty auth login`` via :class:`typer.testing.CliRunner`.

Covers the full browser-mediated Authorization Code + PKCE happy path:

1. :class:`typer.testing.CliRunner` invokes the real
   ``specify_cli.cli.commands.auth.app`` (the installed Typer app).
2. ``_auth_login.login_impl`` runs in the same process and calls
   :class:`specify_cli.auth.flows.authorization_code.AuthorizationCodeFlow`.
3. The loopback :class:`CallbackServer` and :class:`BrowserLauncher` are
   mocked so the test never binds a real port or opens a browser.
4. ``httpx.AsyncClient`` is patched to serve the ``/oauth/token`` and
   ``/api/v1/me`` responses the real flow expects.
5. :class:`SecureStorage.from_environment` is patched to an in-memory
   :class:`.conftest.FakeSecureStorage`, so the test verifies that the
   resulting :class:`StoredSession` is actually written through the
   :class:`TokenManager` pipeline.

FR coverage: FR-001 (browser OAuth is primary), FR-003 (loopback callback),
FR-006 (OS-backed secure storage), FR-016 (TokenManager is sole credential
surface), FR-017 (HTTP callers go through the auth subsystem).

Test isolation: imports :class:`CliRunner` and drives the Typer app —
audited by :mod:`test_audit_clirunner` (T063).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from typer.testing import CliRunner

from specify_cli.auth import get_token_manager
from specify_cli.auth.loopback.state import PKCEState
from specify_cli.cli.commands.auth import app

from .conftest import FakeSecureStorage


pytestmark = [pytest.mark.integration]

runner = CliRunner()


_FIXED_STATE = "integration-test-state-nonce-abcdef12345"
_FIXED_VERIFIER = "integration-test-verifier-xyz0987654321"
_FIXED_CHALLENGE = "integration-test-challenge-fedcba7654321"


def _token_response() -> dict[str, Any]:
    """Return a successful /oauth/token response body.

    Absolute ``refresh_token_expires_at`` is preferred per C-012 to
    exercise the non-None branch of :meth:`_resolve_refresh_expiry`.
    """
    return {
        "access_token": "at_integration_xyz",
        "refresh_token": "rt_integration_xyz",
        "expires_in": 3600,
        "refresh_token_expires_at": "2099-01-01T00:00:00+00:00",
        "scope": "offline_access",
        "session_id": "sess_integration_xyz",
        "token_type": "Bearer",
    }


def _me_response() -> dict[str, Any]:
    """Return a successful GET /api/v1/me response body."""
    return {
        "user_id": "u_alice",
        "email": "alice@example.com",
        "name": "Alice Developer",
        "teams": [
            {"id": "tm_acme", "name": "Acme Corp", "role": "admin"},
            {"id": "tm_beta", "name": "Beta Labs", "role": "member"},
        ],
        "default_team_id": "tm_acme",
        "session_id": "sess_integration_xyz",
    }


def _mock_httpx_response(
    status_code: int, json_body: dict[str, Any]
) -> MagicMock:
    """Build an httpx.Response-compatible MagicMock."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.text = str(json_body)
    response.json = MagicMock(return_value=json_body)
    return response


@pytest.fixture
def patched_state_manager() -> Any:
    """Patch :class:`StateManager.generate` to return a known PKCE state.

    This is how the test coordinates the state value between the real
    flow and the mocked :class:`CallbackServer`: the fake callback server
    knows the nonce and the real :class:`CallbackHandler.validate` passes.
    """
    from kernel.clock import now_utc, timedelta

    fixed_state = PKCEState(
        state=_FIXED_STATE,
        code_verifier=_FIXED_VERIFIER,
        code_challenge=_FIXED_CHALLENGE,
        code_challenge_method="S256",
        created_at=now_utc(),
        expires_at=now_utc() + timedelta(minutes=5),
    )
    with patch(
        "specify_cli.auth.flows.authorization_code.StateManager"
    ) as mock_sm_cls:
        instance = mock_sm_cls.return_value
        instance.generate = MagicMock(return_value=fixed_state)
        instance.validate_not_expired = MagicMock()
        instance.cleanup = MagicMock()
        yield fixed_state


@pytest.fixture
def mocked_loopback() -> Any:
    """Patch :class:`CallbackServer` so start/stop/wait never touch a socket.

    ``wait_for_callback`` returns a dict with the fixed state nonce so the
    real :class:`CallbackHandler.validate` accepts it.
    """
    with patch(
        "specify_cli.auth.flows.authorization_code.CallbackServer"
    ) as mock_cs_cls:
        instance = mock_cs_cls.return_value
        instance.start = MagicMock(
            return_value="http://127.0.0.1:28888/callback"
        )
        instance.stop = MagicMock()
        instance.wait_for_callback = AsyncMock(
            return_value={
                "code": "authz_code_xyz",
                "state": _FIXED_STATE,
            }
        )
        yield instance


@pytest.fixture
def mocked_browser() -> Any:
    """Patch :class:`BrowserLauncher.launch` to always return True (no-op)."""
    with patch(
        "specify_cli.auth.flows.authorization_code.BrowserLauncher.launch",
        return_value=True,
    ) as mock_launch:
        yield mock_launch


class TestBrowserLoginE2E:
    """Full end-to-end browser login via CliRunner + mocked SaaS."""

    def test_full_browser_login_happy_path(
        self,
        fake_storage: FakeSecureStorage,
        patched_state_manager: PKCEState,
        mocked_loopback: MagicMock,
        mocked_browser: MagicMock,
    ) -> None:
        """CliRunner → login_impl → AuthorizationCodeFlow → StoredSession.

        Validates FR-001 (browser OAuth is the primary flow), FR-003 (loopback
        callback), FR-006 (secure-storage write path) and FR-016 (TokenManager
        is the sole credential surface).
        """

        async def _post(
            url: str,
            data: dict[str, Any] | None = None,
            headers: dict[str, str] | None = None,
            **kwargs: Any,
        ) -> MagicMock:
            assert url.endswith("/oauth/token"), f"unexpected POST: {url}"
            return _mock_httpx_response(200, _token_response())

        async def _get(
            url: str,
            headers: dict[str, str] | None = None,
            **kwargs: Any,
        ) -> MagicMock:
            assert url.endswith("/api/v1/me"), f"unexpected GET: {url}"
            return _mock_httpx_response(200, _me_response())

        with (
            patch(
                "specify_cli.auth.secure_storage.SecureStorage.from_environment",
                return_value=fake_storage,
            ),
            patch("specify_cli.auth.flows.authorization_code.PublicHttpClient") as mock_client_cls,
        ):
            fake_client = AsyncMock()
            fake_client.post = AsyncMock(side_effect=_post)
            fake_client.get = AsyncMock(side_effect=_get)
            mock_client_cls.return_value.__aenter__.return_value = fake_client

            result = runner.invoke(app, ["login"])

        assert result.exit_code == 0, (
            f"login failed: stdout={result.stdout!r} "
            f"exception={result.exception!r}"
        )
        assert "Authenticated" in result.stdout
        assert "alice@example.com" in result.stdout

        # Exactly one session was written through the TokenManager
        # pipeline. This confirms FR-016: the flow reached secure storage
        # via ``get_token_manager().set_session`` rather than bypassing it.
        assert len(fake_storage.writes) == 1
        stored = fake_storage.writes[0]
        assert stored.user_id == "u_alice"
        assert stored.email == "alice@example.com"
        assert stored.auth_method == "authorization_code"
        assert stored.default_team_id == "tm_acme"
        assert frozenset(team.id for team in stored.teams) == frozenset(
            {"tm_acme", "tm_beta"}
        )
        # Storage backend matches the fake backend we injected.
        assert stored.storage_backend == "file"

        # The browser launcher WAS called — the flow really went through
        # the browser-open code path.
        mocked_browser.assert_called_once()

        # The loopback server lifecycle ran.
        mocked_loopback.start.assert_called_once()
        mocked_loopback.wait_for_callback.assert_awaited_once()
        mocked_loopback.stop.assert_called()

        # Security: the raw access token MUST NOT be echoed to stdout.
        assert "at_integration_xyz" not in result.stdout
        assert "rt_integration_xyz" not in result.stdout

    def test_already_logged_in_short_circuits(
        self,
        fake_storage: FakeSecureStorage,
    ) -> None:
        """When a valid session is already present, ``login`` skips the flow.

        Covers the FR-001 idempotency path and proves the CliRunner-driven
        test reaches the real ``login_impl`` shortcut logic.
        """
        from kernel.clock import now_utc, timedelta

        from specify_cli.auth.session import StoredSession, Team

        now = now_utc()
        fake_storage._session = StoredSession(
            user_id="u_alice",
            email="alice@example.com",
            name="Alice",
            teams=[Team(id="tm_acme", name="Acme", role="admin")],
            default_team_id="tm_acme",
            access_token="at_preexisting",
            refresh_token="rt_preexisting",
            session_id="sess_pre",
            issued_at=now,
            access_token_expires_at=now + timedelta(hours=1),
            refresh_token_expires_at=now + timedelta(days=89),
            scope="offline_access",
            storage_backend="file",
            last_used_at=now,
            auth_method="authorization_code",
        )

        with patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment",
            return_value=fake_storage,
        ):
            result = runner.invoke(app, ["login"])

        assert result.exit_code == 0, result.stdout
        assert "Already logged in" in result.stdout
        assert "alice@example.com" in result.stdout
        # No write occurred — the short-circuit bailed before the flow.
        assert len(fake_storage.writes) == 0
        # Raw tokens must not leak.
        assert "at_preexisting" not in result.stdout

    def test_login_proceeds_to_packaged_default_when_saas_url_missing(
        self,
        tmp_path: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """#3980 (D-5 revised): no SaaS URL in the environment is no longer an
        error — ``auth login`` proceeds against the packaged default target
        (the acceptance criterion for the launch defaults flip)."""

        async def _fake_browser_flow(tm: Any, saas_url: str) -> None:
            recorded["saas_url"] = saas_url

        recorded: dict[str, str] = {}
        home = tmp_path / "empty-home"
        home.mkdir()
        monkeypatch.setenv("SPEC_KITTY_HOME", str(home))
        monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)

        with (
            patch(
                "specify_cli.cli.commands._auth_login._run_browser_flow",
                side_effect=_fake_browser_flow,
            ),
            patch(
                "specify_cli.cli.commands._auth_login.get_token_manager"
            ) as tm_cls,
        ):
            tm_cls.return_value.is_authenticated = False
            result = runner.invoke(app, ["login"])

        assert result.exit_code == 0, result.stdout
        assert recorded["saas_url"] == "https://team.spec-kitty.ai"

    def test_login_force_resets_session(
        self,
        fake_storage: FakeSecureStorage,
        patched_state_manager: PKCEState,
        mocked_loopback: MagicMock,
        mocked_browser: MagicMock,
    ) -> None:
        """``--force`` must clear the existing session and re-run the flow."""
        from kernel.clock import now_utc, timedelta

        from specify_cli.auth.session import StoredSession, Team

        now = now_utc()
        fake_storage._session = StoredSession(
            user_id="u_bob",
            email="bob@example.com",
            name="Bob",
            teams=[Team(id="tm_x", name="X", role="member")],
            default_team_id="tm_x",
            access_token="at_bob_old",
            refresh_token="rt_bob_old",
            session_id="sess_bob",
            issued_at=now,
            access_token_expires_at=now + timedelta(hours=1),
            refresh_token_expires_at=now + timedelta(days=30),
            scope="offline_access",
            storage_backend="file",
            last_used_at=now,
            auth_method="authorization_code",
        )

        async def _post(url: str, **kwargs: Any) -> MagicMock:
            return _mock_httpx_response(200, _token_response())

        async def _get(url: str, **kwargs: Any) -> MagicMock:
            return _mock_httpx_response(200, _me_response())

        with (
            patch(
                "specify_cli.auth.secure_storage.SecureStorage.from_environment",
                return_value=fake_storage,
            ),
            patch("specify_cli.auth.flows.authorization_code.PublicHttpClient") as mock_client_cls,
        ):
            fake_client = AsyncMock()
            fake_client.post = AsyncMock(side_effect=_post)
            fake_client.get = AsyncMock(side_effect=_get)
            mock_client_cls.return_value.__aenter__.return_value = fake_client

            result = runner.invoke(app, ["login", "--force"])

        assert result.exit_code == 0, result.stdout
        # Old session deleted, new session written — hence at least 1 delete
        # and exactly 1 write (new session).
        assert fake_storage.deletes >= 1
        assert len(fake_storage.writes) == 1
        assert fake_storage.writes[0].email == "alice@example.com"
        assert "at_bob_old" not in result.stdout


def test_login_uses_token_manager_factory(
    fake_storage: FakeSecureStorage,
    patched_state_manager: PKCEState,
    mocked_loopback: MagicMock,
    mocked_browser: MagicMock,
) -> None:
    """Regression: ``login`` must resolve its :class:`TokenManager` via the
    factory :func:`get_token_manager`, never via a direct constructor.

    After a successful CliRunner login, the same factory call must return
    a TokenManager that already holds the fresh session.
    """

    async def _post(url: str, **kwargs: Any) -> MagicMock:
        return _mock_httpx_response(200, _token_response())

    async def _get(url: str, **kwargs: Any) -> MagicMock:
        return _mock_httpx_response(200, _me_response())

    with (
        patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment",
            return_value=fake_storage,
        ),
        patch("specify_cli.auth.flows.authorization_code.PublicHttpClient") as mock_client_cls,
    ):
        fake_client = AsyncMock()
        fake_client.post = AsyncMock(side_effect=_post)
        fake_client.get = AsyncMock(side_effect=_get)
        mock_client_cls.return_value.__aenter__.return_value = fake_client

        result = runner.invoke(app, ["login"])
        assert result.exit_code == 0, result.stdout

        # Use the public factory — never TokenManager() directly.
        tm = get_token_manager()
        session = tm.get_current_session()
        assert session is not None
        assert session.email == "alice@example.com"
        assert tm.is_authenticated is True
