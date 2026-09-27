"""Tests for :class:`AuthorizationCodeFlow` (feature 080, WP04 T027).

These tests exercise the flow orchestrator with mocked httpx, mocked
CallbackServer, and mocked BrowserLauncher — no real browser, no real
socket, no real network.

The headline assertions per WP04's acceptance criteria:

- Happy path: full login returns a valid :class:`StoredSession`.
- :class:`BrowserLaunchError` is raised when no browser is available.
- Missing fields in the token response raise :class:`AuthenticationError`.
- Network errors are surfaced as :class:`NetworkError`.
- ``refresh_token_expires_at`` from the SaaS response is honored directly
  (absolute ISO preferred, relative seconds fallback).
"""

from __future__ import annotations

from kernel.clock import UTC, datetime, now_utc, timedelta
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from specify_cli.auth.errors import (
    AuthenticationError,
    BrowserLaunchError,
    NetworkError,
)
from specify_cli.auth.flows.authorization_code import AuthorizationCodeFlow


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.integration]

_FUTURE_ISO = "2099-01-01T00:00:00+00:00"


def _token_response(
    *,
    access_token: str = "access-xyz",
    refresh_token: str = "refresh-xyz",
    expires_in: int = 3600,
    session_id: str = "sess-1",
    refresh_token_expires_at: str | None = _FUTURE_ISO,
    refresh_token_expires_in: int | None = None,
    scope: str = "offline_access",
) -> dict:
    body: dict = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": expires_in,
        "session_id": session_id,
        "scope": scope,
    }
    if refresh_token_expires_at is not None:
        body["refresh_token_expires_at"] = refresh_token_expires_at
    if refresh_token_expires_in is not None:
        body["refresh_token_expires_in"] = refresh_token_expires_in
    return body


def _me_response(
    *,
    user_id: str = "user-1",
    email: str = "alice@example.com",
    name: str = "Alice",
    teams: list[dict] | None = None,
    refresh_token_expires_at: str | None = None,
) -> dict:
    body: dict = {
        "user_id": user_id,
        "email": email,
        "name": name,
        "teams": teams
        if teams is not None
        else [{"id": "t1", "name": "Team One", "role": "owner", "is_private_teamspace": False}],
    }
    if refresh_token_expires_at is not None:
        body["refresh_token_expires_at"] = refresh_token_expires_at
    return body


def _mock_httpx_response(status_code: int, json_body: object | None = None, text: str = ""):
    r = Mock(spec=httpx.Response)
    r.status_code = status_code
    r.text = text or (str(json_body) if json_body else "")
    r.json = Mock(return_value=json_body if json_body is not None else {})
    return r


# ---------------------------------------------------------------------------
# URL construction
# ---------------------------------------------------------------------------


class TestBuildAuthUrl:
    """Pure-function tests for ``_build_auth_url``."""

    def test_includes_all_required_pkce_params(self):
        flow = AuthorizationCodeFlow(saas_base_url="https://saas.test")
        pkce = flow._state_manager.generate()
        url = flow._build_auth_url(pkce, "http://127.0.0.1:28888/callback")

        assert url.startswith("https://saas.test/oauth/authorize?")
        assert "client_id=cli_native" in url
        assert "response_type=code" in url
        assert "code_challenge_method=S256" in url
        assert f"code_challenge={pkce.code_challenge}" in url
        assert f"state={pkce.state}" in url
        assert "scope=offline_access" in url
        assert "redirect_uri=http" in url  # URL-encoded

    def test_rstrips_trailing_slash(self):
        flow = AuthorizationCodeFlow(saas_base_url="https://saas.test/")
        assert flow._saas_base_url == "https://saas.test"


# ---------------------------------------------------------------------------
# Constructor / config fallback
# ---------------------------------------------------------------------------


class TestConstructor:

    def test_explicit_url_wins(self, monkeypatch):
        monkeypatch.setenv("SPEC_KITTY_SAAS_URL", "https://env.test")
        flow = AuthorizationCodeFlow(saas_base_url="https://explicit.test")
        assert flow._saas_base_url == "https://explicit.test"

    def test_falls_back_to_env(self, monkeypatch):
        monkeypatch.setenv("SPEC_KITTY_SAAS_URL", "https://env.test")
        flow = AuthorizationCodeFlow()
        assert flow._saas_base_url == "https://env.test"

    def test_missing_env_raises_hosted_endpoint_unconfigured(self, monkeypatch):
        """Endpoint opt-in (FR-011/FR-012, T028 item 14): direct construction
        with no ``saas_base_url`` and no env override now raises rather than
        silently defaulting — this constructor path is dead in practice via
        ``_auth_login.py``, which always pre-resolves and passes the URL."""
        from specify_cli.auth.server_target import HostedEndpointUnconfigured

        monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
        with pytest.raises(HostedEndpointUnconfigured):
            AuthorizationCodeFlow()


# ---------------------------------------------------------------------------
# _exchange_code (T024)
# ---------------------------------------------------------------------------


class TestExchangeCode:

    @pytest.mark.asyncio
    async def test_happy_path(self):
        flow = AuthorizationCodeFlow(saas_base_url="https://saas.test")
        tokens = _token_response()

        with patch("specify_cli.auth.flows.authorization_code.PublicHttpClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = _mock_httpx_response(200, tokens)

            result = await flow._exchange_code(
                code="auth-code",
                code_verifier="verifier",
                redirect_uri="http://127.0.0.1:28888/callback",
            )

        assert result == tokens
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "https://saas.test/oauth/token"
        posted_data = call_args[1]["data"]
        assert posted_data["grant_type"] == "authorization_code"
        assert posted_data["code"] == "auth-code"
        assert posted_data["code_verifier"] == "verifier"

    @pytest.mark.asyncio
    async def test_missing_access_token_raises(self):
        flow = AuthorizationCodeFlow(saas_base_url="https://saas.test")
        bad = _token_response()
        del bad["access_token"]

        with patch("specify_cli.auth.flows.authorization_code.PublicHttpClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = _mock_httpx_response(200, bad)

            with pytest.raises(AuthenticationError, match="missing required fields"):
                await flow._exchange_code(
                    code="auth-code",
                    code_verifier="verifier",
                    redirect_uri="http://127.0.0.1:28888/callback",
                )

    @pytest.mark.asyncio
    async def test_http_400_raises_authentication_error(self):
        flow = AuthorizationCodeFlow(saas_base_url="https://saas.test")

        with patch("specify_cli.auth.flows.authorization_code.PublicHttpClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = _mock_httpx_response(
                400, {}, text="invalid grant"
            )

            with pytest.raises(AuthenticationError, match="HTTP 400"):
                await flow._exchange_code(
                    code="x",
                    code_verifier="v",
                    redirect_uri="http://127.0.0.1:28888/callback",
                )

    @pytest.mark.asyncio
    async def test_network_error_raises_network_error(self):
        flow = AuthorizationCodeFlow(saas_base_url="https://saas.test")

        with patch("specify_cli.auth.flows.authorization_code.PublicHttpClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            # PublicHttpClient wraps httpx.RequestError as NetworkError internally;
            # the flow now catches NetworkError from the client directly.
            mock_client.post.side_effect = NetworkError("DNS failed")

            with pytest.raises(NetworkError, match="Network error during code exchange"):
                await flow._exchange_code(
                    code="x",
                    code_verifier="v",
                    redirect_uri="http://127.0.0.1:28888/callback",
                )


# ---------------------------------------------------------------------------
# _build_session (T025) — refresh-TTL amendment
# ---------------------------------------------------------------------------


class TestBuildSession:

    @pytest.mark.asyncio
    async def test_happy_path_uses_absolute_expires_at(self):
        flow = AuthorizationCodeFlow(saas_base_url="https://saas.test")
        tokens = _token_response(refresh_token_expires_at=_FUTURE_ISO)
        me = _me_response()

        with patch("specify_cli.auth.flows.authorization_code.PublicHttpClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = _mock_httpx_response(200, me)

            session = await flow._build_session(tokens)

        assert session.user_id == "user-1"
        assert session.email == "alice@example.com"
        assert session.name == "Alice"
        assert frozenset(team.id for team in session.teams) == frozenset({"t1"})
        assert session.default_team_id == "t1"  # client-picked
        assert session.access_token == "access-xyz"
        assert session.refresh_token == "refresh-xyz"
        assert session.session_id == "sess-1"
        assert session.auth_method == "authorization_code"
        # Refresh expiry comes from the server verbatim (no clock math):
        assert session.refresh_token_expires_at == datetime(2099, 1, 1, tzinfo=UTC)
        # #176: the session records which endpoint minted it.
        assert session.issuer_url == "https://saas.test"

    @pytest.mark.asyncio
    async def test_prefers_private_teamspace_for_default_team_id(self):
        flow = AuthorizationCodeFlow(saas_base_url="https://saas.test")
        tokens = _token_response(refresh_token_expires_at=_FUTURE_ISO)
        me = _me_response(
            teams=[
                {"id": "t-shared", "name": "Shared Team", "role": "member", "is_private_teamspace": False},
                {"id": "t-private", "name": "Private Teamspace", "role": "owner", "is_private_teamspace": True},
            ]
        )

        with patch("specify_cli.auth.flows.authorization_code.PublicHttpClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = _mock_httpx_response(200, me)

            session = await flow._build_session(tokens)

        assert session.default_team_id == "t-private"

    @pytest.mark.asyncio
    async def test_falls_back_to_expires_in_when_absolute_absent(self):
        """When SaaS omits the absolute form, use relative seconds."""
        flow = AuthorizationCodeFlow(saas_base_url="https://saas.test")
        tokens = _token_response(
            refresh_token_expires_at=None,
            refresh_token_expires_in=86400,  # 1 day
        )
        me = _me_response()

        before = now_utc()
        with patch("specify_cli.auth.flows.authorization_code.PublicHttpClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = _mock_httpx_response(200, me)

            session = await flow._build_session(tokens)
        after = now_utc()

        assert session.refresh_token_expires_at is not None
        # Should be approximately 1 day from now
        delta = session.refresh_token_expires_at - before
        assert timedelta(seconds=86400 - 5) <= delta <= timedelta(seconds=86400 + 5)
        assert session.refresh_token_expires_at <= after + timedelta(seconds=86400)

    @pytest.mark.asyncio
    async def test_prefers_token_response_over_me_response(self):
        """When both responses carry the field, the token response wins."""
        flow = AuthorizationCodeFlow(saas_base_url="https://saas.test")
        token_iso = "2099-06-01T00:00:00+00:00"
        me_iso = "2099-01-01T00:00:00+00:00"
        tokens = _token_response(refresh_token_expires_at=token_iso)
        me = _me_response(refresh_token_expires_at=me_iso)

        with patch("specify_cli.auth.flows.authorization_code.PublicHttpClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = _mock_httpx_response(200, me)

            session = await flow._build_session(tokens)

        assert session.refresh_token_expires_at == datetime(2099, 6, 1, tzinfo=UTC)

    @pytest.mark.asyncio
    async def test_reads_from_me_response_when_token_missing_absolute(self):
        """Token response has no absolute form; fall back to /api/v1/me."""
        flow = AuthorizationCodeFlow(saas_base_url="https://saas.test")
        tokens = _token_response(refresh_token_expires_at=None)
        # Also no relative form in tokens
        me = _me_response(refresh_token_expires_at="2099-01-01T00:00:00Z")

        with patch("specify_cli.auth.flows.authorization_code.PublicHttpClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = _mock_httpx_response(200, me)

            session = await flow._build_session(tokens)

        assert session.refresh_token_expires_at == datetime(2099, 1, 1, tzinfo=UTC)

    @pytest.mark.asyncio
    async def test_accepts_z_suffix_on_iso_string(self):
        """Both ``+00:00`` and ``Z`` suffixes must be accepted."""
        flow = AuthorizationCodeFlow(saas_base_url="https://saas.test")
        tokens = _token_response(refresh_token_expires_at="2099-01-01T00:00:00Z")
        me = _me_response()

        with patch("specify_cli.auth.flows.authorization_code.PublicHttpClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = _mock_httpx_response(200, me)

            session = await flow._build_session(tokens)

        assert session.refresh_token_expires_at == datetime(2099, 1, 1, tzinfo=UTC)

    @pytest.mark.asyncio
    async def test_invalid_me_refresh_expiry_raises_authentication_error(self):
        flow = AuthorizationCodeFlow(saas_base_url="https://saas.test")
        tokens = _token_response(refresh_token_expires_at=None)
        me = _me_response(refresh_token_expires_at=123)

        with patch("specify_cli.auth.flows.authorization_code.PublicHttpClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = _mock_httpx_response(200, me)

            with pytest.raises(AuthenticationError, match="must be an ISO-8601 timestamp"):
                await flow._build_session(tokens)

    @pytest.mark.asyncio
    async def test_no_teams_raises(self):
        flow = AuthorizationCodeFlow(saas_base_url="https://saas.test")
        tokens = _token_response()
        me = _me_response(teams=[])

        with patch("specify_cli.auth.flows.authorization_code.PublicHttpClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = _mock_httpx_response(200, me)

            with pytest.raises(AuthenticationError, match="no team memberships"):
                await flow._build_session(tokens)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("field", ["user_id", "email"])
    async def test_missing_me_identity_field_raises_authentication_error(self, field):
        flow = AuthorizationCodeFlow(saas_base_url="https://saas.test")
        tokens = _token_response()
        me = _me_response()
        del me[field]

        with patch("specify_cli.auth.flows.authorization_code.PublicHttpClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = _mock_httpx_response(200, me)

            with pytest.raises(AuthenticationError, match=f"missing required field '{field}'"):
                await flow._build_session(tokens)

    @pytest.mark.asyncio
    async def test_non_object_me_payload_raises_authentication_error(self):
        flow = AuthorizationCodeFlow(saas_base_url="https://saas.test")
        tokens = _token_response()

        with patch("specify_cli.auth.flows.authorization_code.PublicHttpClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = _mock_httpx_response(200, [])

            with pytest.raises(AuthenticationError, match="must be a JSON object"):
                await flow._build_session(tokens)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("field", ["id", "name", "role"])
    async def test_missing_me_team_field_raises_authentication_error(self, field):
        flow = AuthorizationCodeFlow(saas_base_url="https://saas.test")
        tokens = _token_response()
        team = {"id": "t1", "name": "Team One", "role": "owner"}
        del team[field]
        me = _me_response(teams=[team])

        with patch("specify_cli.auth.flows.authorization_code.PublicHttpClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = _mock_httpx_response(200, me)

            with pytest.raises(AuthenticationError, match=f"missing required team field '{field}'"):
                await flow._build_session(tokens)

    @pytest.mark.asyncio
    async def test_401_on_me_raises(self):
        flow = AuthorizationCodeFlow(saas_base_url="https://saas.test")
        tokens = _token_response()

        with patch("specify_cli.auth.flows.authorization_code.PublicHttpClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = _mock_httpx_response(401, {})

            with pytest.raises(AuthenticationError, match="HTTP 401"):
                await flow._build_session(tokens)

    @pytest.mark.asyncio
    async def test_network_error_raises(self):
        flow = AuthorizationCodeFlow(saas_base_url="https://saas.test")
        tokens = _token_response()

        with patch("specify_cli.auth.flows.authorization_code.PublicHttpClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            # PublicHttpClient wraps httpx.RequestError as NetworkError internally;
            # the flow now catches NetworkError from the client directly.
            mock_client.get.side_effect = NetworkError("DNS failed")

            with pytest.raises(NetworkError, match="Network error fetching user info"):
                await flow._build_session(tokens)

    @pytest.mark.asyncio
    async def test_storage_backend_is_preserved(self):
        flow = AuthorizationCodeFlow(
            saas_base_url="https://saas.test", storage_backend="file"
        )
        tokens = _token_response()
        me = _me_response()

        with patch("specify_cli.auth.flows.authorization_code.PublicHttpClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = _mock_httpx_response(200, me)

            session = await flow._build_session(tokens)

        assert session.storage_backend == "file"


# ---------------------------------------------------------------------------
# Full login() with mocked loopback + browser
# ---------------------------------------------------------------------------


class TestLogin:

    @pytest.mark.asyncio
    async def test_no_browser_raises_browser_launch_error(self):
        flow = AuthorizationCodeFlow(saas_base_url="https://saas.test")

        with patch(
            "specify_cli.auth.flows.authorization_code.BrowserLauncher.launch",
            return_value=False,
        ), patch(
            "specify_cli.auth.flows.authorization_code.CallbackServer"
        ) as mock_server_cls:
            mock_server = Mock()
            mock_server.start.return_value = "http://127.0.0.1:28888/callback"
            mock_server.stop = Mock()
            mock_server_cls.return_value = mock_server

            with pytest.raises(BrowserLaunchError, match="No browser available"):
                await flow.login()

            # Server must be stopped even on browser failure
            mock_server.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_happy_path_end_to_end(self):
        """Full login with mocked loopback + httpx."""
        flow = AuthorizationCodeFlow(saas_base_url="https://saas.test")
        tokens = _token_response()
        me = _me_response()

        with patch(
            "specify_cli.auth.flows.authorization_code.BrowserLauncher.launch",
            return_value=True,
        ), patch(
            "specify_cli.auth.flows.authorization_code.CallbackServer"
        ) as mock_server_cls:

            mock_server = Mock()
            mock_server.start.return_value = "http://127.0.0.1:28888/callback"

            # Capture the PKCE state so we return it in the callback
            captured_state = {}

            def _capture_state(_self, pkce, _url):
                captured_state["state"] = pkce.state
                return f"https://saas.test/oauth/authorize?state={pkce.state}"

            async def _wait():
                return {"code": "auth-code", "state": captured_state["state"]}

            mock_server.wait_for_callback = _wait
            mock_server.stop = Mock()
            mock_server_cls.return_value = mock_server

            # Patch _build_auth_url so we can capture the PKCE state
            original_build = AuthorizationCodeFlow._build_auth_url

            def _patched_build(self, pkce, callback_url):
                captured_state["state"] = pkce.state
                return original_build(self, pkce, callback_url)

            with patch.object(
                AuthorizationCodeFlow,
                "_build_auth_url",
                _patched_build,
            ), patch("specify_cli.auth.flows.authorization_code.PublicHttpClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value.__aenter__.return_value = mock_client
                mock_client.post.return_value = _mock_httpx_response(200, tokens)
                mock_client.get.return_value = _mock_httpx_response(200, me)

                session = await flow.login()

        assert session.email == "alice@example.com"
        assert session.access_token == "access-xyz"
        assert session.auth_method == "authorization_code"
        mock_server.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_callback_csrf_mismatch_raises(self):
        from specify_cli.auth.errors import CallbackValidationError

        flow = AuthorizationCodeFlow(saas_base_url="https://saas.test")

        with patch(
            "specify_cli.auth.flows.authorization_code.BrowserLauncher.launch",
            return_value=True,
        ), patch(
            "specify_cli.auth.flows.authorization_code.CallbackServer"
        ) as mock_server_cls:

            mock_server = Mock()
            mock_server.start.return_value = "http://127.0.0.1:28888/callback"
            mock_server.stop = Mock()

            async def _wait():
                return {"code": "auth-code", "state": "WRONG-STATE"}

            mock_server.wait_for_callback = _wait
            mock_server_cls.return_value = mock_server

            with pytest.raises(CallbackValidationError, match="State mismatch"):
                await flow.login()
