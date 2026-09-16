"""Tests for :class:`DeviceCodeFlow` (feature 080, WP05).

These tests exercise the device authorization flow orchestrator with mocked
``httpx.AsyncClient`` — no real sockets, no real network. The polling loop
uses ``interval=0`` so tests finish in milliseconds.

The headline assertions per WP05's acceptance criteria:

- Happy path: full login returns a :class:`StoredSession` with
  ``auth_method="device_code"``.
- ``access_denied`` on the token poll raises :class:`DeviceFlowDenied`.
- ``expired_token`` on the token poll raises :class:`DeviceFlowExpired`.
- ``authorization_pending`` responses loop until approval.
- ``/api/v1/me`` failure surfaces :class:`AuthenticationError`.
- ``refresh_token_expires_at`` from the token response is preferred over
  the relative seconds fallback (SaaS amendment landed 2026-04-09).
- CliRunner integration: ``spec-kitty auth login --headless`` drives the
  real Typer ``app`` through the dispatch shell and into this flow class.
"""

from __future__ import annotations

import io

from kernel.clock import UTC, datetime, now_utc, timedelta
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from typer.testing import CliRunner

from specify_cli.auth.errors import (
    AuthenticationError,
    DeviceFlowDenied,
    DeviceFlowExpired,
    NetworkError,
)
from specify_cli.auth.flows.device_code import DeviceCodeFlow
from specify_cli.cli.console import CliConsole


pytestmark = [pytest.mark.integration]

_SAAS = "https://saas.test"
_FUTURE_ISO = "2099-01-01T00:00:00+00:00"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _device_response(
    *,
    device_code: str = "dc_xyz",
    user_code: str = "ABCD1234",
    verification_uri: str = f"{_SAAS}/device",
    verification_uri_complete: str | None = None,
    expires_in: int = 900,
    interval: int = 0,  # 0 = fast tests (no real sleep)
) -> dict:
    body: dict = {
        "device_code": device_code,
        "user_code": user_code,
        "verification_uri": verification_uri,
        "expires_in": expires_in,
        "interval": interval,
    }
    if verification_uri_complete is not None:
        body["verification_uri_complete"] = verification_uri_complete
    return body


def _token_response(
    *,
    access_token: str = "at_xyz",
    refresh_token: str = "rt_xyz",
    expires_in: int = 3600,
    session_id: str = "sess_xyz",
    scope: str = "offline_access",
    refresh_token_expires_at: str | None = _FUTURE_ISO,
    refresh_token_expires_in: int | None = None,
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
    user_id: str = "u_alice",
    email: str = "alice@example.com",
    name: str = "Alice Developer",
    teams: list[dict] | None = None,
    refresh_token_expires_at: str | None = None,
) -> dict:
    body: dict = {
        "user_id": user_id,
        "email": email,
        "name": name,
        "teams": teams
        if teams is not None
        else [{"id": "tm_acme", "name": "Acme", "role": "admin", "is_private_teamspace": False}],
    }
    if refresh_token_expires_at is not None:
        body["refresh_token_expires_at"] = refresh_token_expires_at
    return body


def _mock_httpx_response(
    status_code: int, json_body: object | None = None, text: str = ""
):
    r = Mock(spec=httpx.Response)
    r.status_code = status_code
    r.text = text or (str(json_body) if json_body else "")
    r.json = Mock(return_value=json_body if json_body is not None else {})
    return r


class _RoutedMockClient:
    """An httpx.AsyncClient stand-in that routes calls by URL.

    The real ``_build_session`` uses ``httpx.AsyncClient`` once for each
    HTTP call. To keep tests readable we reuse a single mock instance across
    every ``httpx.AsyncClient()`` construction inside a ``with patch``
    context, routing by URL.

    Route values may be either a pre-built ``Mock(spec=httpx.Response)`` OR
    a plain callable ``fn(data) -> Response`` wrapped in a non-``Mock``
    sentinel. Because ``Mock`` instances are themselves callable, we check
    for the sentinel explicitly rather than using ``callable()``.
    """

    def __init__(self, post_routes: dict, get_routes: dict | None = None):
        self._post_routes = post_routes
        self._get_routes = get_routes or {}

    async def post(self, url: str, data=None, headers=None):
        for suffix, resp in self._post_routes.items():
            if url.endswith(suffix):
                if isinstance(resp, _Dynamic):
                    return resp(data)
                return resp
        raise AssertionError(f"Unexpected POST: {url}")

    async def get(self, url: str, headers=None):
        for suffix, resp in self._get_routes.items():
            if url.endswith(suffix):
                return resp
        raise AssertionError(f"Unexpected GET: {url}")


class _Dynamic:
    """Sentinel wrapper for a callable route that computes the response."""

    def __init__(self, fn):
        self._fn = fn

    def __call__(self, data):
        return self._fn(data)


class _AsyncCtx:
    """Minimal async context manager wrapping a pre-built mock client."""

    def __init__(self, client):
        self._client = client

    async def __aenter__(self):
        return self._client

    async def __aexit__(self, exc_type, exc, tb):
        return None


def _install_routed_client(post_routes, get_routes=None):
    """Return a ``patch`` on ``httpx.AsyncClient`` that routes by URL.

    Every ``httpx.AsyncClient(timeout=...)`` call inside the ``with`` block
    returns a fresh async context manager that yields the same routed mock
    client. This keeps the per-call state (``post_routes``, ``get_routes``)
    stable across every ``_request_device_code`` / ``_poll_token_request``
    / ``_build_session`` iteration.
    """
    mock_client = _RoutedMockClient(post_routes, get_routes)

    def _factory(*args, **kwargs):
        return _AsyncCtx(mock_client)

    return patch("httpx.AsyncClient", side_effect=_factory)


# ---------------------------------------------------------------------------
# Constructor / config fallback
# ---------------------------------------------------------------------------


class TestConstructor:

    def test_explicit_url_wins(self, monkeypatch):
        monkeypatch.setenv("SPEC_KITTY_SAAS_URL", "https://env.test")
        flow = DeviceCodeFlow(saas_base_url="https://explicit.test")
        assert flow._saas_base_url == "https://explicit.test"

    def test_falls_back_to_env(self, monkeypatch):
        monkeypatch.setenv("SPEC_KITTY_SAAS_URL", "https://env.test")
        flow = DeviceCodeFlow()
        assert flow._saas_base_url == "https://env.test"

    def test_missing_env_uses_packaged_default(self, monkeypatch):
        from specify_cli.auth.config import DEFAULT_HOSTED_SAAS_URL

        monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
        flow = DeviceCodeFlow()
        assert flow._saas_base_url == DEFAULT_HOSTED_SAAS_URL

    def test_rstrips_trailing_slash(self):
        flow = DeviceCodeFlow(saas_base_url="https://saas.test/")
        assert flow._saas_base_url == "https://saas.test"

    def test_storage_backend_defaults_to_file(self):
        flow = DeviceCodeFlow(saas_base_url=_SAAS)
        assert flow._storage_backend == "file"

    def test_storage_backend_override(self):
        flow = DeviceCodeFlow(saas_base_url=_SAAS, storage_backend="file")
        assert flow._storage_backend == "file"


# ---------------------------------------------------------------------------
# _request_device_code
# ---------------------------------------------------------------------------


class TestRequestDeviceCode:

    @pytest.mark.asyncio
    async def test_happy_path(self):
        flow = DeviceCodeFlow(saas_base_url=_SAAS)
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = _mock_httpx_response(
                200, _device_response()
            )

            state = await flow._request_device_code()

        assert state.device_code == "dc_xyz"
        assert state.user_code == "ABCD1234"
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == f"{_SAAS}/oauth/device"
        # Per FR/C-005, scope=offline_access is always included in the request.
        posted = call_args[1]["data"]
        assert posted["client_id"] == "cli_native"
        assert posted["scope"] == "offline_access"

    @pytest.mark.asyncio
    async def test_http_500_raises_authentication_error(self):
        flow = DeviceCodeFlow(saas_base_url=_SAAS)
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = _mock_httpx_response(
                500, {"error": "server_error"}, text="server error"
            )

            with pytest.raises(AuthenticationError, match="HTTP 500"):
                await flow._request_device_code()

    @pytest.mark.asyncio
    async def test_network_error_raises_network_error(self):
        flow = DeviceCodeFlow(saas_base_url=_SAAS)
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = httpx.ConnectError("DNS failed")

            with pytest.raises(
                NetworkError, match="Network error requesting device code"
            ):
                await flow._request_device_code()

    @pytest.mark.asyncio
    async def test_missing_device_code_raises(self):
        flow = DeviceCodeFlow(saas_base_url=_SAAS)
        bad = _device_response()
        del bad["device_code"]
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = _mock_httpx_response(200, bad)

            with pytest.raises(
                AuthenticationError, match="missing required field"
            ):
                await flow._request_device_code()


# ---------------------------------------------------------------------------
# _poll_token_request
# ---------------------------------------------------------------------------


class TestPollTokenRequest:

    @pytest.mark.asyncio
    async def test_success_returns_parsed_body(self):
        flow = DeviceCodeFlow(saas_base_url=_SAAS)
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = _mock_httpx_response(
                200, _token_response()
            )

            body = await flow._poll_token_request("dc_xyz")

        assert body["access_token"] == "at_xyz"
        call_args = mock_client.post.call_args
        posted = call_args[1]["data"]
        assert (
            posted["grant_type"]
            == "urn:ietf:params:oauth:grant-type:device_code"
        )
        assert posted["device_code"] == "dc_xyz"

    @pytest.mark.asyncio
    async def test_400_returns_error_dict(self):
        """RFC 8628 pending/denied/expired responses come back as 400 JSON."""
        flow = DeviceCodeFlow(saas_base_url=_SAAS)
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = _mock_httpx_response(
                400, {"error": "authorization_pending"}
            )

            body = await flow._poll_token_request("dc_xyz")

        assert body == {"error": "authorization_pending"}

    @pytest.mark.asyncio
    async def test_429_returns_slow_down_dict(self):
        """A rate-limit HTTP 429 is routed to the poller's slow_down handling.

        Regression for the CLI aborting the device flow on HTTP 429 instead
        of letting the poller's existing RFC 8628 backoff handle it.
        """
        flow = DeviceCodeFlow(saas_base_url=_SAAS)
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            response = _mock_httpx_response(429, text="rate limited")
            response.headers = httpx.Headers({"Retry-After": "7"})
            mock_client.post.return_value = response

            body = await flow._poll_token_request("dc_xyz")

        assert body == {"error": "slow_down", "retry_after": 7}

    @pytest.mark.asyncio
    async def test_429_without_retry_after_header(self):
        flow = DeviceCodeFlow(saas_base_url=_SAAS)
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            response = _mock_httpx_response(429, text="rate limited")
            response.headers = httpx.Headers({})
            mock_client.post.return_value = response

            body = await flow._poll_token_request("dc_xyz")

        assert body == {"error": "slow_down", "retry_after": None}

    @pytest.mark.asyncio
    async def test_429_with_unparseable_retry_after(self):
        flow = DeviceCodeFlow(saas_base_url=_SAAS)
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            response = _mock_httpx_response(429, text="rate limited")
            response.headers = httpx.Headers({"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"})
            mock_client.post.return_value = response

            body = await flow._poll_token_request("dc_xyz")

        assert body == {"error": "slow_down", "retry_after": None}

    @pytest.mark.asyncio
    async def test_429_with_lowercase_retry_after_header(self):
        """A non-canonical-case header still parses via httpx.Headers' fold.

        Regression for #461: earlier fixtures all used the exact key
        ``"Retry-After"``, so they passed identically whether
        ``_parse_retry_after`` did a case-insensitive lookup or a plain
        ``dict.get``. This uses real ``httpx.Headers`` (case-insensitive by
        RFC 7230 §3.2) with a lowercase key to actually exercise that.
        """
        flow = DeviceCodeFlow(saas_base_url=_SAAS)
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            response = _mock_httpx_response(429, text="rate limited")
            response.headers = httpx.Headers({"retry-after": "7"})
            mock_client.post.return_value = response

            body = await flow._poll_token_request("dc_xyz")

        assert body == {"error": "slow_down", "retry_after": 7}

    @pytest.mark.asyncio
    async def test_unexpected_status_raises(self):
        flow = DeviceCodeFlow(saas_base_url=_SAAS)
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = _mock_httpx_response(
                502, {}, text="bad gateway"
            )

            with pytest.raises(AuthenticationError, match="HTTP 502"):
                await flow._poll_token_request("dc_xyz")

    @pytest.mark.asyncio
    async def test_network_error_raises(self):
        flow = DeviceCodeFlow(saas_base_url=_SAAS)
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = httpx.ConnectError("no route")

            with pytest.raises(
                NetworkError, match="Network error polling for token"
            ):
                await flow._poll_token_request("dc_xyz")


# ---------------------------------------------------------------------------
# _build_session — refresh-TTL amendment
# ---------------------------------------------------------------------------


class TestBuildSession:

    @pytest.mark.asyncio
    async def test_happy_path_uses_absolute_expires_at(self):
        flow = DeviceCodeFlow(saas_base_url=_SAAS)
        tokens = _token_response(refresh_token_expires_at=_FUTURE_ISO)
        me = _me_response()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = _mock_httpx_response(200, me)

            session = await flow._build_session(tokens)

        assert session.user_id == "u_alice"
        assert session.email == "alice@example.com"
        assert session.name == "Alice Developer"
        assert frozenset(team.id for team in session.teams) == frozenset({"tm_acme"})
        assert session.default_team_id == "tm_acme"  # client-picked
        assert session.access_token == "at_xyz"
        assert session.refresh_token == "rt_xyz"
        assert session.session_id == "sess_xyz"
        # WP05 assertion: auth_method is device_code, NOT authorization_code
        assert session.auth_method == "device_code"
        # Refresh expiry comes from the server verbatim (no clock math):
        assert session.refresh_token_expires_at == datetime(
            2099, 1, 1, tzinfo=UTC
        )
        # #176: the session records which endpoint minted it.
        assert session.issuer_url == _SAAS

    @pytest.mark.asyncio
    async def test_prefers_private_teamspace_for_default_team_id(self):
        flow = DeviceCodeFlow(saas_base_url=_SAAS)
        tokens = _token_response(refresh_token_expires_at=_FUTURE_ISO)
        me = _me_response(
            teams=[
                {"id": "tm_shared", "name": "Shared", "role": "member", "is_private_teamspace": False},
                {"id": "tm_private", "name": "Private Teamspace", "role": "admin", "is_private_teamspace": True},
            ]
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = _mock_httpx_response(200, me)

            session = await flow._build_session(tokens)

        assert session.default_team_id == "tm_private"

    @pytest.mark.asyncio
    async def test_falls_back_to_expires_in_when_absolute_absent(self):
        """When SaaS omits the absolute form, use relative seconds."""
        flow = DeviceCodeFlow(saas_base_url=_SAAS)
        tokens = _token_response(
            refresh_token_expires_at=None,
            refresh_token_expires_in=86400,  # 1 day
        )
        me = _me_response()

        before = now_utc()
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = _mock_httpx_response(200, me)

            session = await flow._build_session(tokens)
        after = now_utc()

        assert session.refresh_token_expires_at is not None
        delta = session.refresh_token_expires_at - before
        assert timedelta(seconds=86400 - 5) <= delta <= timedelta(
            seconds=86400 + 5
        )
        assert session.refresh_token_expires_at <= after + timedelta(
            seconds=86400
        )

    @pytest.mark.asyncio
    async def test_prefers_token_response_over_me_response(self):
        """When both responses carry the field, the token response wins."""
        flow = DeviceCodeFlow(saas_base_url=_SAAS)
        token_iso = "2099-06-01T00:00:00+00:00"
        me_iso = "2099-01-01T00:00:00+00:00"
        tokens = _token_response(refresh_token_expires_at=token_iso)
        me = _me_response(refresh_token_expires_at=me_iso)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = _mock_httpx_response(200, me)

            session = await flow._build_session(tokens)

        assert session.refresh_token_expires_at == datetime(
            2099, 6, 1, tzinfo=UTC
        )

    @pytest.mark.asyncio
    async def test_reads_from_me_response_when_token_missing_absolute(self):
        """Token response has no absolute form; fall back to /api/v1/me."""
        flow = DeviceCodeFlow(saas_base_url=_SAAS)
        tokens = _token_response(refresh_token_expires_at=None)
        me = _me_response(refresh_token_expires_at="2099-01-01T00:00:00Z")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = _mock_httpx_response(200, me)

            session = await flow._build_session(tokens)

        assert session.refresh_token_expires_at == datetime(
            2099, 1, 1, tzinfo=UTC
        )

    @pytest.mark.asyncio
    async def test_accepts_z_suffix_on_iso_string(self):
        """Both ``+00:00`` and ``Z`` suffixes must be accepted."""
        flow = DeviceCodeFlow(saas_base_url=_SAAS)
        tokens = _token_response(
            refresh_token_expires_at="2099-01-01T00:00:00Z"
        )
        me = _me_response()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = _mock_httpx_response(200, me)

            session = await flow._build_session(tokens)

        assert session.refresh_token_expires_at == datetime(
            2099, 1, 1, tzinfo=UTC
        )

    @pytest.mark.asyncio
    async def test_invalid_me_refresh_expiry_raises_authentication_error(self):
        flow = DeviceCodeFlow(saas_base_url=_SAAS)
        tokens = _token_response(refresh_token_expires_at=None)
        me = _me_response(refresh_token_expires_at=123)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = _mock_httpx_response(200, me)

            with pytest.raises(AuthenticationError, match="must be an ISO-8601 timestamp"):
                await flow._build_session(tokens)

    @pytest.mark.asyncio
    async def test_no_teams_raises(self):
        flow = DeviceCodeFlow(saas_base_url=_SAAS)
        tokens = _token_response()
        me = _me_response(teams=[])

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = _mock_httpx_response(200, me)

            with pytest.raises(AuthenticationError, match="no team memberships"):
                await flow._build_session(tokens)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("field", ["user_id", "email"])
    async def test_missing_me_identity_field_raises_authentication_error(self, field):
        flow = DeviceCodeFlow(saas_base_url=_SAAS)
        tokens = _token_response()
        me = _me_response()
        del me[field]

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = _mock_httpx_response(200, me)

            with pytest.raises(AuthenticationError, match=f"missing required field '{field}'"):
                await flow._build_session(tokens)

    @pytest.mark.asyncio
    async def test_non_object_me_payload_raises_authentication_error(self):
        flow = DeviceCodeFlow(saas_base_url=_SAAS)
        tokens = _token_response()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = _mock_httpx_response(200, [])

            with pytest.raises(AuthenticationError, match="must be a JSON object"):
                await flow._build_session(tokens)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("field", ["id", "name", "role"])
    async def test_missing_me_team_field_raises_authentication_error(self, field):
        flow = DeviceCodeFlow(saas_base_url=_SAAS)
        tokens = _token_response()
        team = {"id": "tm_acme", "name": "Acme", "role": "admin"}
        del team[field]
        me = _me_response(teams=[team])

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = _mock_httpx_response(200, me)

            with pytest.raises(AuthenticationError, match=f"missing required team field '{field}'"):
                await flow._build_session(tokens)

    @pytest.mark.asyncio
    async def test_401_on_me_raises(self):
        flow = DeviceCodeFlow(saas_base_url=_SAAS)
        tokens = _token_response()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = _mock_httpx_response(401, {})

            with pytest.raises(AuthenticationError, match="HTTP 401"):
                await flow._build_session(tokens)

    @pytest.mark.asyncio
    async def test_network_error_raises(self):
        flow = DeviceCodeFlow(saas_base_url=_SAAS)
        tokens = _token_response()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.side_effect = httpx.ConnectError("DNS failed")

            with pytest.raises(
                NetworkError, match="Network error fetching user info"
            ):
                await flow._build_session(tokens)

    @pytest.mark.asyncio
    async def test_storage_backend_is_preserved(self):
        flow = DeviceCodeFlow(saas_base_url=_SAAS, storage_backend="file")
        tokens = _token_response()
        me = _me_response()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = _mock_httpx_response(200, me)

            session = await flow._build_session(tokens)

        assert session.storage_backend == "file"


# ---------------------------------------------------------------------------
# Full login() with mocked httpx, routed by URL
# ---------------------------------------------------------------------------


class TestLogin:

    @pytest.mark.asyncio
    async def test_full_happy_path(self):
        """End-to-end: device request -> poll -> me -> StoredSession."""
        flow = DeviceCodeFlow(saas_base_url=_SAAS)

        post_routes = {
            "/oauth/device": _mock_httpx_response(200, _device_response()),
            "/oauth/token": _mock_httpx_response(200, _token_response()),
        }
        get_routes = {
            "/api/v1/me": _mock_httpx_response(200, _me_response()),
        }

        progress_lines: list[str] = []

        with _install_routed_client(post_routes, get_routes):
            session = await flow.login(progress_writer=progress_lines.append)

        assert session.user_id == "u_alice"
        assert session.email == "alice@example.com"
        assert session.auth_method == "device_code"
        assert session.access_token == "at_xyz"
        assert session.refresh_token_expires_at == datetime(
            2099, 1, 1, tzinfo=UTC
        )

        # The progress writer receives the verification URI and a formatted code.
        joined = "\n".join(progress_lines)
        assert "Visit:" in joined
        assert f"{_SAAS}/device" in joined
        # format_user_code turns ABCD1234 into ABCD-1234.
        assert "ABCD-1234" in joined
        assert "Authorization granted" in joined

    @pytest.mark.asyncio
    async def test_login_with_verification_uri_complete(self):
        """When SaaS returns verification_uri_complete, it is displayed too."""
        flow = DeviceCodeFlow(saas_base_url=_SAAS)

        dev = _device_response(
            verification_uri_complete=f"{_SAAS}/device?code=ABCD1234"
        )
        post_routes = {
            "/oauth/device": _mock_httpx_response(200, dev),
            "/oauth/token": _mock_httpx_response(200, _token_response()),
        }
        get_routes = {
            "/api/v1/me": _mock_httpx_response(200, _me_response()),
        }

        progress_lines: list[str] = []
        with _install_routed_client(post_routes, get_routes):
            await flow.login(progress_writer=progress_lines.append)

        joined = "\n".join(progress_lines)
        assert f"{_SAAS}/device?code=ABCD1234" in joined

    @pytest.mark.asyncio
    async def test_login_sanitizes_device_response_fields(self):
        """Hostile OAuth device response fields cannot emit terminal controls."""
        safe_text = "Zoë 日本語 🐱"
        hostile_suffix = "\x1b[2J\x1b]0;x\x07\x1b"
        hostile = f"{safe_text}{hostile_suffix}"
        flow = DeviceCodeFlow(saas_base_url=_SAAS)
        buffer = io.StringIO()
        console = CliConsole(
            file=buffer,
            width=160,
            no_color=True,
            highlight=False,
        )

        post_routes = {
            "/oauth/device": _mock_httpx_response(
                200,
                _device_response(
                    device_code=f"dc{hostile_suffix}",
                    user_code=f"ABCD1234{hostile_suffix}",
                    verification_uri=f"{_SAAS}/device{hostile}",
                    verification_uri_complete=f"{_SAAS}/complete{hostile}",
                ),
            ),
            "/oauth/token": _mock_httpx_response(200, _token_response()),
        }
        get_routes = {
            "/api/v1/me": _mock_httpx_response(200, _me_response()),
        }

        with _install_routed_client(post_routes, get_routes):
            await flow.login(progress_writer=console.print)

        emitted = buffer.getvalue().encode("utf-8")
        assert safe_text.encode("utf-8") in emitted
        assert b"ABCD-1234" in emitted
        assert b"\x1b" not in emitted
        assert b"[2J" not in emitted
        assert b"]0;x" not in emitted

    @pytest.mark.asyncio
    async def test_login_with_authorization_pending_then_success(self):
        """Poller handles authorization_pending responses until approval."""
        flow = DeviceCodeFlow(saas_base_url=_SAAS)

        token_calls = {"count": 0}

        def _token_post(_data):
            token_calls["count"] += 1
            if token_calls["count"] <= 2:
                return _mock_httpx_response(
                    400, {"error": "authorization_pending"}
                )
            return _mock_httpx_response(200, _token_response())

        post_routes = {
            "/oauth/device": _mock_httpx_response(200, _device_response()),
            "/oauth/token": _Dynamic(_token_post),
        }
        get_routes = {
            "/api/v1/me": _mock_httpx_response(200, _me_response()),
        }

        with _install_routed_client(post_routes, get_routes):
            session = await flow.login()

        assert token_calls["count"] == 3
        assert session.auth_method == "device_code"

    @pytest.mark.asyncio
    async def test_login_user_denial(self):
        flow = DeviceCodeFlow(saas_base_url=_SAAS)

        post_routes = {
            "/oauth/device": _mock_httpx_response(200, _device_response()),
            "/oauth/token": _mock_httpx_response(
                400, {"error": "access_denied"}
            ),
        }

        with _install_routed_client(post_routes), pytest.raises(DeviceFlowDenied):
            await flow.login()

    @pytest.mark.asyncio
    async def test_login_expired_token(self):
        flow = DeviceCodeFlow(saas_base_url=_SAAS)

        post_routes = {
            "/oauth/device": _mock_httpx_response(200, _device_response()),
            "/oauth/token": _mock_httpx_response(
                400, {"error": "expired_token"}
            ),
        }

        with _install_routed_client(post_routes), pytest.raises(DeviceFlowExpired):
            await flow.login()

    @pytest.mark.asyncio
    async def test_login_device_request_fails(self):
        flow = DeviceCodeFlow(saas_base_url=_SAAS)

        post_routes = {
            "/oauth/device": _mock_httpx_response(
                500, {"error": "server_error"}, text="down"
            ),
        }

        with _install_routed_client(post_routes), pytest.raises(AuthenticationError):
            await flow.login()

    @pytest.mark.asyncio
    async def test_login_me_fetch_fails(self):
        """Approval succeeds but /api/v1/me returns 401 -> AuthenticationError."""
        flow = DeviceCodeFlow(saas_base_url=_SAAS)

        post_routes = {
            "/oauth/device": _mock_httpx_response(200, _device_response()),
            "/oauth/token": _mock_httpx_response(200, _token_response()),
        }
        get_routes = {
            "/api/v1/me": _mock_httpx_response(401, {}),
        }

        with _install_routed_client(post_routes, get_routes), pytest.raises(AuthenticationError, match="HTTP 401"):
            await flow.login()

    @pytest.mark.asyncio
    async def test_login_without_progress_writer(self):
        """Omitting ``progress_writer`` must not crash."""
        flow = DeviceCodeFlow(saas_base_url=_SAAS)

        post_routes = {
            "/oauth/device": _mock_httpx_response(200, _device_response()),
            "/oauth/token": _mock_httpx_response(200, _token_response()),
        }
        get_routes = {
            "/api/v1/me": _mock_httpx_response(200, _me_response()),
        }

        with _install_routed_client(post_routes, get_routes):
            session = await flow.login()  # no progress_writer

        assert session.auth_method == "device_code"


# ---------------------------------------------------------------------------
# CliRunner integration: `spec-kitty auth login --headless`
# ---------------------------------------------------------------------------


class TestAuthLoginHeadlessCliRunner:
    """End-to-end CliRunner test for ``spec-kitty auth login --headless``.

    This exercises the full path: Typer command shell -> ``_auth_login.login_impl``
    -> ``_run_device_flow`` -> ``DeviceCodeFlow.login`` -> mocked HTTP ->
    ``TokenManager.set_session``. It verifies the dispatch wiring from WP04
    connects to WP05's flow class.

    The test imports both :class:`CliRunner` and :class:`DeviceCodeFlow`
    explicitly so WP11's T063 integration-coverage audit recognizes it as a
    valid end-to-end test.
    """

    def test_headless_login_via_clirunner(self, monkeypatch):
        from specify_cli.auth import reset_token_manager
        from specify_cli.cli.commands.auth import app

        reset_token_manager()
        monkeypatch.setenv("SPEC_KITTY_SAAS_URL", _SAAS)
        runner = CliRunner()

        post_routes = {
            "/oauth/device": _mock_httpx_response(200, _device_response()),
            "/oauth/token": _mock_httpx_response(200, _token_response()),
        }
        get_routes = {
            "/api/v1/me": _mock_httpx_response(200, _me_response()),
        }

        # Also mock the storage backend so we don't write to the real auth store.
        with _install_routed_client(post_routes, get_routes), patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment"
        ) as mock_se:
            mock_storage = Mock()
            mock_storage.read.return_value = None
            mock_storage.write = Mock(return_value=None)
            mock_storage.delete = Mock(return_value=None)
            mock_storage.backend_name = "file"
            mock_se.return_value = mock_storage

            # Fresh TokenManager so is_authenticated reads the mocked storage.
            reset_token_manager()

            # Ensure DeviceCodeFlow is the real symbol (not a stale import).
            assert DeviceCodeFlow is not None  # keeps the lint-import alive
            result = runner.invoke(app, ["login", "--headless"])

        assert result.exit_code == 0, f"stdout: {result.stdout}"
        # The success message prints the email.
        assert "alice@example.com" in result.stdout
        # And uses the "Authenticated" banner from _print_success.
        assert "Authenticated" in result.stdout

    def test_headless_denial_surfaces_exit_code(self, monkeypatch):
        """User denial should exit non-zero with a clear message."""
        from specify_cli.auth import reset_token_manager
        from specify_cli.cli.commands.auth import app

        reset_token_manager()
        monkeypatch.setenv("SPEC_KITTY_SAAS_URL", _SAAS)
        runner = CliRunner()

        post_routes = {
            "/oauth/device": _mock_httpx_response(200, _device_response()),
            "/oauth/token": _mock_httpx_response(
                400, {"error": "access_denied"}
            ),
        }

        with _install_routed_client(post_routes), patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment"
        ) as mock_se:
            mock_storage = Mock()
            mock_storage.read.return_value = None
            mock_storage.write = Mock(return_value=None)
            mock_storage.delete = Mock(return_value=None)
            mock_storage.backend_name = "file"
            mock_se.return_value = mock_storage
            reset_token_manager()
            result = runner.invoke(app, ["login", "--headless"])

        assert result.exit_code != 0
        # DeviceFlowDenied is a subclass of AuthenticationError, which
        # _run_device_flow reports as "Device flow failed: ...".
        assert "Device flow failed" in result.stdout or "denied" in result.stdout.lower()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload, expected",
    [
        ({"error": "invalid_grant"}, "invalid_grant"),
        ({"error": "invalid_client"}, "invalid_client"),
        ({"error": "invalid_request"}, "invalid_request"),
        ({"error": "authorization_pending"}, "HTTP 401"),
        ({"error": "slow_down"}, "HTTP 401"),
        ({"error": ["untrusted-secret"]}, "HTTP 401"),
        ({"error": "untrusted-secret"}, "HTTP 401"),
        (["untrusted-secret"], "HTTP 401"),
    ],
)
async def test_login_401_is_terminal_actionable_and_redacted(payload, expected, caplog):
    """A rejected device grant must not become pending or expose server text."""
    if isinstance(payload, dict):
        payload = {**payload, "error_description": "untrusted-secret", "access_token": "untrusted-secret"}
    poll = Mock(return_value=_mock_httpx_response(401, payload))
    with _install_routed_client(
        {
            "/oauth/device": _mock_httpx_response(200, _device_response()),
            "/oauth/token": _Dynamic(poll),
        }
    ), pytest.raises(AuthenticationError) as caught:
        await DeviceCodeFlow(saas_base_url=_SAAS).login()
    assert expected in str(caught.value)
    assert "spec-kitty auth login --headless" in str(caught.value)
    assert "untrusted-secret" not in str(caught.value) + caplog.text
    assert poll.call_count == 1


@pytest.mark.asyncio
async def test_login_non_json_401_is_terminal_and_redacted():
    response = _mock_httpx_response(401, text="untrusted-secret")
    response.json.side_effect = ValueError("untrusted-secret")
    with _install_routed_client(
        {
            "/oauth/device": _mock_httpx_response(200, _device_response()),
            "/oauth/token": response,
        }
    ), pytest.raises(AuthenticationError) as caught:
        await DeviceCodeFlow(saas_base_url=_SAAS).login()
    assert "spec-kitty auth login --headless" in str(caught.value)
    assert "untrusted-secret" not in str(caught.value)
