"""Tests for ``specify_cli.auth.http.transport.OAuthHttpClient`` (feature 080, WP08 T047).

These tests exercise the bearer injection + 401 retry-once contract using
``respx`` to mock the HTTP layer and a fake ``TokenRefreshFlow`` injected into
``sys.modules`` to avoid real network calls.

The four canonical scenarios covered:
  1. Happy-path: a 200 response reaches the caller with the injected bearer.
  2. 401 → refresh → retry → 200: single refresh, single retry, success.
  3. 401 → refresh raises: propagates as ``SessionInvalidError``.
  4. Non-auth errors (500) pass through unchanged without triggering refresh.
"""

from __future__ import annotations

import sys
import types
from kernel.clock import UTC, datetime, now_utc, timedelta

import httpx
import pytest
import respx

from specify_cli.auth import get_token_manager, reset_token_manager
from specify_cli.auth.errors import (
    NetworkError,
    NotAuthenticatedError,
    SessionInvalidError,
)
from specify_cli.auth.http import OAuthHttpClient
from specify_cli.auth.secure_storage import SecureStorage
from specify_cli.auth.session import StoredSession, Team


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.integration]


@pytest.fixture(autouse=True)
def _configured_saas_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """This suite exercises 401-retry/bearer-injection mechanics, not
    endpoint resolution — endpoint opt-in (FR-011) means an unset
    ``SPEC_KITTY_SAAS_URL`` now raises ``HostedEndpointUnconfigured`` instead
    of silently resolving to a packaged default, so every test here needs an
    explicit, configured target."""
    monkeypatch.setenv("SPEC_KITTY_SAAS_URL", "https://saas.test")


def _now() -> datetime:
    return now_utc()


def _make_session(
    *,
    access_token: str = "access-v1",
    refresh_token: str = "refresh-v1",
    access_expires_in: int = 900,
) -> StoredSession:
    now = _now()
    return StoredSession(
        user_id="user-1",
        email="a@b.com",
        name="A B",
        teams=[Team(id="t1", name="T1", role="owner")],
        default_team_id="t1",
        access_token=access_token,
        refresh_token=refresh_token,
        session_id="sess-1",
        issued_at=now,
        access_token_expires_at=now + timedelta(seconds=access_expires_in),
        refresh_token_expires_at=None,
        scope="openid",
        storage_backend="file",
        last_used_at=now,
        auth_method="authorization_code",
    )


class FakeStorage(SecureStorage):
    """Minimal in-memory storage — pre-populated via ``_session``."""

    def __init__(self, session: StoredSession | None = None) -> None:
        self._session = session
        self.writes = 0
        self.deletes = 0

    def read(self) -> StoredSession | None:
        return self._session

    def write(self, session: StoredSession) -> None:
        self._session = session
        self.writes += 1

    def delete(self) -> None:
        self._session = None
        self.deletes += 1

    @property
    def backend_name(self) -> str:
        return "file"


class FakeRefreshFlow:
    """Counts refresh calls and mints fresh sessions (or raises on demand)."""

    call_count = 0
    raise_session_invalid = False

    def __init__(self) -> None:
        pass

    async def refresh(self, session: StoredSession) -> StoredSession:
        FakeRefreshFlow.call_count += 1
        if FakeRefreshFlow.raise_session_invalid:
            raise SessionInvalidError("server says no")
        return StoredSession(
            user_id=session.user_id,
            email=session.email,
            name=session.name,
            teams=list(session.teams),
            default_team_id=session.default_team_id,
            access_token=f"access-v{FakeRefreshFlow.call_count + 1}",
            refresh_token=session.refresh_token,
            session_id=session.session_id,
            issued_at=_now(),
            access_token_expires_at=_now() + timedelta(seconds=900),
            refresh_token_expires_at=session.refresh_token_expires_at,
            scope=session.scope,
            storage_backend=session.storage_backend,
            last_used_at=_now(),
            auth_method=session.auth_method,
        )


@pytest.fixture
def install_fake_refresh_flow(monkeypatch):
    """Inject a fake ``specify_cli.auth.flows.refresh`` module for TokenManager."""
    FakeRefreshFlow.call_count = 0
    FakeRefreshFlow.raise_session_invalid = False

    flows_pkg = types.ModuleType("specify_cli.auth.flows")
    flows_pkg.__path__ = []
    refresh_module = types.ModuleType("specify_cli.auth.flows.refresh")
    refresh_module.TokenRefreshFlow = FakeRefreshFlow

    monkeypatch.setitem(sys.modules, "specify_cli.auth.flows", flows_pkg)
    monkeypatch.setitem(
        sys.modules, "specify_cli.auth.flows.refresh", refresh_module
    )
    yield FakeRefreshFlow


@pytest.fixture
def seeded_token_manager(monkeypatch, install_fake_refresh_flow):
    """Install a TokenManager with a pre-populated session as the process-wide factory target."""
    import specify_cli.auth.manager as auth_manager

    storage = FakeStorage(session=_make_session(access_token="access-v1"))

    # Reset any existing singleton then patch the factory to return our instrumented manager.
    reset_token_manager()

    from specify_cli.auth.token_manager import TokenManager

    tm = TokenManager(storage)
    tm.load_from_storage_sync()

    monkeypatch.setattr(auth_manager, "_tm", tm, raising=True)

    yield tm

    reset_token_manager()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bearer_token_is_injected(seeded_token_manager):
    """Happy-path: the injected Authorization header matches the current access token."""
    with respx.mock(base_url="https://api.example.com") as mock:
        route = mock.get("/v1/resource").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )

        async with OAuthHttpClient() as client:
            resp = await client.get("https://api.example.com/v1/resource")

        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

        assert route.called
        assert route.call_count == 1
        sent_auth = route.calls.last.request.headers.get("Authorization")
        assert sent_auth == "Bearer access-v1"


@pytest.mark.asyncio
async def test_401_triggers_refresh_and_retry_once(seeded_token_manager, install_fake_refresh_flow):
    """On 401, client refreshes the token and retries exactly once."""
    with respx.mock(base_url="https://api.example.com") as mock:
        # First call returns 401, second call returns 200.
        route = mock.get("/v1/resource").mock(
            side_effect=[
                httpx.Response(401, json={"error": "expired"}),
                httpx.Response(200, json={"ok": True}),
            ]
        )

        async with OAuthHttpClient() as client:
            resp = await client.get("https://api.example.com/v1/resource")

        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

        # Exactly one refresh call.
        assert install_fake_refresh_flow.call_count == 1
        # Exactly two HTTP attempts (original + retry).
        assert route.call_count == 2

        # The second attempt must use the refreshed token.
        first_auth = route.calls[0].request.headers.get("Authorization")
        second_auth = route.calls[1].request.headers.get("Authorization")
        assert first_auth == "Bearer access-v1"
        assert second_auth == "Bearer access-v2"


@pytest.mark.asyncio
async def test_401_with_refresh_failure_propagates(seeded_token_manager, install_fake_refresh_flow):
    """If refresh raises, the caller sees SessionInvalidError — no further retries."""
    install_fake_refresh_flow.raise_session_invalid = True

    with respx.mock(base_url="https://api.example.com") as mock:
        route = mock.get("/v1/resource").mock(
            return_value=httpx.Response(401, json={"error": "expired"})
        )

        async with OAuthHttpClient() as client:
            with pytest.raises(SessionInvalidError):
                await client.get("https://api.example.com/v1/resource")

        # Refresh was attempted exactly once.
        assert install_fake_refresh_flow.call_count == 1
        # Only the original request reached the server (retry never happens
        # because refresh itself raised).
        assert route.call_count == 1


@pytest.mark.asyncio
async def test_500_passes_through_without_retry(seeded_token_manager, install_fake_refresh_flow):
    """Non-auth failures (5xx) must not trigger refresh or retry."""
    with respx.mock(base_url="https://api.example.com") as mock:
        route = mock.get("/v1/resource").mock(
            return_value=httpx.Response(500, json={"error": "boom"})
        )

        async with OAuthHttpClient() as client:
            resp = await client.get("https://api.example.com/v1/resource")

        assert resp.status_code == 500
        # No refresh attempted.
        assert install_fake_refresh_flow.call_count == 0
        # Exactly one HTTP attempt (no retry).
        assert route.call_count == 1


@pytest.mark.asyncio
async def test_not_authenticated_when_no_session(install_fake_refresh_flow, monkeypatch):
    """If TokenManager has no session, a request raises NotAuthenticatedError before any HTTP call."""
    import specify_cli.auth.manager as auth_manager

    reset_token_manager()
    from specify_cli.auth.token_manager import TokenManager

    tm = TokenManager(FakeStorage(session=None))
    tm.load_from_storage_sync()
    monkeypatch.setattr(auth_manager, "_tm", tm, raising=True)

    try:
        with respx.mock(
            base_url="https://api.example.com", assert_all_called=False
        ) as mock:
            route = mock.get("/v1/resource").mock(
                return_value=httpx.Response(200, json={"ok": True})
            )

            async with OAuthHttpClient() as client:
                with pytest.raises(NotAuthenticatedError):
                    await client.get("https://api.example.com/v1/resource")

            # No HTTP request ever reached the wire.
            assert route.call_count == 0
    finally:
        reset_token_manager()


@pytest.mark.asyncio
async def test_second_401_raises_not_authenticated(seeded_token_manager, install_fake_refresh_flow):
    """If BOTH requests return 401 (refresh succeeds but server still rejects), caller sees NotAuthenticatedError."""
    with respx.mock(base_url="https://api.example.com") as mock:
        route = mock.get("/v1/resource").mock(
            return_value=httpx.Response(401, json={"error": "still bad"})
        )

        async with OAuthHttpClient() as client:
            with pytest.raises(NotAuthenticatedError):
                await client.get("https://api.example.com/v1/resource")

        # Refresh happened once.
        assert install_fake_refresh_flow.call_count == 1
        # Exactly two HTTP attempts (original + single retry).
        assert route.call_count == 2


@pytest.mark.asyncio
async def test_transport_error_becomes_network_error(seeded_token_manager):
    """httpx.TransportError (DNS/connect/timeout) is translated to NetworkError."""
    with respx.mock(base_url="https://api.example.com") as mock:
        mock.get("/v1/resource").mock(side_effect=httpx.ConnectError("boom"))

        async with OAuthHttpClient() as client:
            with pytest.raises(NetworkError):
                await client.get("https://api.example.com/v1/resource")


@pytest.mark.asyncio
async def test_caller_headers_are_preserved(seeded_token_manager):
    """Caller-supplied headers are preserved; Authorization is overwritten with the bearer token."""
    with respx.mock(base_url="https://api.example.com") as mock:
        route = mock.post("/v1/resource").mock(
            return_value=httpx.Response(201, json={"ok": True})
        )

        async with OAuthHttpClient() as client:
            resp = await client.post(
                "https://api.example.com/v1/resource",
                headers={
                    "X-Custom": "value",
                    "Authorization": "Bearer stale-stale",  # must be overwritten
                },
                json={"payload": 1},
            )

        assert resp.status_code == 201
        sent = route.calls.last.request
        assert sent.headers.get("X-Custom") == "value"
        assert sent.headers.get("Authorization") == "Bearer access-v1"
