"""Tests for :class:`TokenRefreshFlow` (feature 080, WP04 T027).

Unit tests for the refresh grant flow with mocked httpx. These tests
verify the four primary paths called out by WP04's acceptance criteria:

1. Happy path: ``200`` with rotated tokens returns an updated session.
2. ``400 invalid_grant`` raises :class:`RefreshTokenExpiredError`.
3. ``400 session_invalid`` raises :class:`SessionInvalidError`.
4. Transport-level failures raise :class:`NetworkError`.

Plus the refresh-TTL amendment behavior per C-012: the absolute
``refresh_token_expires_at`` is preferred, with a fallback to the
relative ``refresh_token_expires_in`` form.
"""

from __future__ import annotations

from kernel.clock import UTC, datetime, now_utc, timedelta
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from specify_cli.auth.errors import (
    NetworkError,
    RefreshReplayError,
    RefreshTokenExpiredError,
    SessionInvalidError,
    TokenRefreshError,
)
from specify_cli.auth.flows.refresh import TokenRefreshFlow
from specify_cli.auth.session import StoredSession, Team


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.integration]

@pytest.fixture(autouse=True)
def _saas_url(monkeypatch):
    monkeypatch.setenv("SPEC_KITTY_SAAS_URL", "https://saas.test")
    yield


def _make_session(
    *,
    refresh_token: str = "refresh-v1",
    refresh_token_expires_at: datetime | None = None,
) -> StoredSession:
    now = now_utc()
    return StoredSession(
        user_id="user-1",
        email="a@b.com",
        name="A B",
        teams=[Team(id="t1", name="T1", role="owner")],
        default_team_id="t1",
        access_token="access-v1",
        refresh_token=refresh_token,
        session_id="sess",
        issued_at=now,
        access_token_expires_at=now - timedelta(seconds=1),  # expired
        refresh_token_expires_at=refresh_token_expires_at,
        scope="offline_access",
        storage_backend="file",
        last_used_at=now,
        auth_method="authorization_code",
    )


def _mock_httpx_response(status_code: int, json_body: dict | None = None, text: str = ""):
    r = Mock(spec=httpx.Response)
    r.status_code = status_code
    r.text = text or (str(json_body) if json_body else "")
    r.json = Mock(return_value=json_body or {})
    return r


def _refresh_body(
    *,
    access_token: str = "access-v2",
    refresh_token: str | None = "refresh-v2",
    expires_in: int = 3600,
    refresh_token_expires_at: str | None = "2099-01-01T00:00:00+00:00",
    refresh_token_expires_in: int | None = None,
    scope: str = "offline_access",
) -> dict:
    body: dict = {
        "access_token": access_token,
        "expires_in": expires_in,
        "scope": scope,
    }
    if refresh_token is not None:
        body["refresh_token"] = refresh_token
    if refresh_token_expires_at is not None:
        body["refresh_token_expires_at"] = refresh_token_expires_at
    if refresh_token_expires_in is not None:
        body["refresh_token_expires_in"] = refresh_token_expires_in
    return body


# ---------------------------------------------------------------------------
# Happy path + updated session
# ---------------------------------------------------------------------------


class TestRefreshHappyPath:

    @pytest.mark.asyncio
    async def test_refresh_returns_updated_session(self):
        flow = TokenRefreshFlow()
        session = _make_session()
        body = _refresh_body()

        with patch("specify_cli.auth.flows.refresh.PublicHttpClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = _mock_httpx_response(200, body)

            updated = await flow.refresh(session)

        assert updated.access_token == "access-v2"
        assert updated.refresh_token == "refresh-v2"
        assert updated.session_id == "sess"  # preserved
        assert updated.user_id == "user-1"  # preserved
        assert updated.email == "a@b.com"  # preserved
        assert updated.default_team_id == "t1"  # preserved
        assert updated.refresh_token_expires_at == datetime(2099, 1, 1, tzinfo=UTC)

    @pytest.mark.asyncio
    async def test_refresh_preserves_issuer_url(self):
        """A refresh renews tokens with the same issuer (#176); only a
        re-login may move the session to a new endpoint."""
        flow = TokenRefreshFlow()
        session = _make_session()
        session.issuer_url = "https://old.example.com"
        body = _refresh_body()

        with patch("specify_cli.auth.flows.refresh.PublicHttpClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = _mock_httpx_response(200, body)

            updated = await flow.refresh(session)

        assert updated.issuer_url == "https://old.example.com"

    @pytest.mark.asyncio
    async def test_refresh_keeps_old_refresh_token_when_not_rotated(self):
        flow = TokenRefreshFlow()
        session = _make_session(refresh_token="refresh-v1")
        body = _refresh_body(refresh_token=None)

        with patch("specify_cli.auth.flows.refresh.PublicHttpClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = _mock_httpx_response(200, body)

            updated = await flow.refresh(session)

        assert updated.refresh_token == "refresh-v1"
        assert updated.access_token == "access-v2"

    @pytest.mark.asyncio
    async def test_refresh_posts_to_correct_endpoint(self):
        flow = TokenRefreshFlow()
        session = _make_session()
        body = _refresh_body()

        with patch("specify_cli.auth.flows.refresh.PublicHttpClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = _mock_httpx_response(200, body)

            await flow.refresh(session)

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "https://saas.test/oauth/token"
        posted_data = call_args[1]["data"]
        assert posted_data["grant_type"] == "refresh_token"
        assert posted_data["refresh_token"] == "refresh-v1"
        assert posted_data["client_id"] == "cli_native"


# ---------------------------------------------------------------------------
# Refresh-TTL amendment behavior (C-012 / 2026-04-09)
# ---------------------------------------------------------------------------


class TestRefreshTTLAmendment:

    @pytest.mark.asyncio
    async def test_absolute_expires_at_is_preferred(self):
        """When both absolute and relative forms are present, absolute wins."""
        flow = TokenRefreshFlow()
        session = _make_session()
        body = _refresh_body(
            refresh_token_expires_at="2099-06-01T00:00:00+00:00",
            refresh_token_expires_in=86400,
        )

        with patch("specify_cli.auth.flows.refresh.PublicHttpClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = _mock_httpx_response(200, body)

            updated = await flow.refresh(session)

        assert updated.refresh_token_expires_at == datetime(2099, 6, 1, tzinfo=UTC)

    @pytest.mark.asyncio
    async def test_falls_back_to_expires_in(self):
        """When only the relative form is present, compute expires_at from it."""
        flow = TokenRefreshFlow()
        session = _make_session()
        body = _refresh_body(
            refresh_token_expires_at=None,
            refresh_token_expires_in=3600,
        )

        before = now_utc()
        with patch("specify_cli.auth.flows.refresh.PublicHttpClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = _mock_httpx_response(200, body)

            updated = await flow.refresh(session)
        after = now_utc()

        assert updated.refresh_token_expires_at is not None
        delta = updated.refresh_token_expires_at - before
        assert timedelta(seconds=3595) <= delta <= timedelta(seconds=3605)
        assert updated.refresh_token_expires_at <= after + timedelta(seconds=3600)

    @pytest.mark.asyncio
    async def test_z_suffix_accepted(self):
        flow = TokenRefreshFlow()
        session = _make_session()
        body = _refresh_body(refresh_token_expires_at="2099-01-01T00:00:00Z")

        with patch("specify_cli.auth.flows.refresh.PublicHttpClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = _mock_httpx_response(200, body)

            updated = await flow.refresh(session)

        assert updated.refresh_token_expires_at == datetime(2099, 1, 1, tzinfo=UTC)

    @pytest.mark.asyncio
    async def test_offsetless_absolute_expires_at_is_treated_as_utc(self):
        flow = TokenRefreshFlow()
        session = _make_session()
        body = _refresh_body(refresh_token_expires_at="2099-01-01T00:00:00")

        with patch("specify_cli.auth.flows.refresh.PublicHttpClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = _mock_httpx_response(200, body)

            updated = await flow.refresh(session)

        assert updated.refresh_token_expires_at == datetime(2099, 1, 1, tzinfo=UTC)
        assert updated.is_refresh_token_expired() is False

    @pytest.mark.asyncio
    async def test_preserves_prior_expiry_when_response_omits_both_forms(self):
        """Non-compliant server: last-resort fallback preserves prior expiry."""
        flow = TokenRefreshFlow()
        prior = datetime(2099, 1, 1, tzinfo=UTC)
        session = _make_session(refresh_token_expires_at=prior)
        body = _refresh_body(
            refresh_token_expires_at=None,
            refresh_token_expires_in=None,
        )

        with patch("specify_cli.auth.flows.refresh.PublicHttpClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = _mock_httpx_response(200, body)

            updated = await flow.refresh(session)

        assert updated.refresh_token_expires_at == prior


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class TestRefreshErrors:

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status_code", [400, 401])
    async def test_invalid_grant_raises_expired(self, status_code):
        flow = TokenRefreshFlow()
        session = _make_session()

        with patch("specify_cli.auth.flows.refresh.PublicHttpClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = _mock_httpx_response(
                status_code, {"error": "invalid_grant"}
            )

            with pytest.raises(RefreshTokenExpiredError):
                await flow.refresh(session)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status_code", [400, 401])
    async def test_session_invalid_raises_session_invalid(self, status_code):
        flow = TokenRefreshFlow()
        session = _make_session()

        with patch("specify_cli.auth.flows.refresh.PublicHttpClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = _mock_httpx_response(
                status_code, {"error": "session_invalid"}
            )

            with pytest.raises(SessionInvalidError):
                await flow.refresh(session)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status_code", [400, 401])
    async def test_unknown_error_raises_token_refresh_error(self, status_code):
        flow = TokenRefreshFlow()
        session = _make_session()

        with patch("specify_cli.auth.flows.refresh.PublicHttpClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = _mock_httpx_response(
                status_code, {"error": "mystery"}, text="mystery error"
            )

            with pytest.raises(TokenRefreshError):
                await flow.refresh(session)

    @pytest.mark.asyncio
    async def test_500_raises_token_refresh_error(self):
        flow = TokenRefreshFlow()
        session = _make_session()

        with patch("specify_cli.auth.flows.refresh.PublicHttpClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = _mock_httpx_response(
                500, {}, text="internal"
            )

            with pytest.raises(TokenRefreshError, match="HTTP 500"):
                await flow.refresh(session)

    @pytest.mark.asyncio
    async def test_network_error_raises_network_error(self):
        flow = TokenRefreshFlow()
        session = _make_session()

        with patch("specify_cli.auth.flows.refresh.PublicHttpClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_client
            # PublicHttpClient wraps httpx.RequestError as NetworkError internally;
            # the flow now catches NetworkError from the client directly.
            mock_client.post.side_effect = NetworkError("DNS failed")

            with pytest.raises(NetworkError, match="Network error during refresh"):
                await flow.refresh(session)


# ---------------------------------------------------------------------------
# 409 benign-replay and generation capture (WP03 T012)
# ---------------------------------------------------------------------------


class TestRefresh409AndGeneration:

    @pytest.mark.asyncio
    async def test_refresh_409_benign_replay_raises(self):
        """409 + {"error": "refresh_replay_benign_retry", "retry_after": 2} → RefreshReplayError(retry_after=2)."""
        flow = TokenRefreshFlow()
        session = _make_session()

        with patch("specify_cli.auth.flows.refresh.PublicHttpClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = _mock_httpx_response(
                409,
                {"error": "refresh_replay_benign_retry", "retry_after": 2},
            )

            with pytest.raises(RefreshReplayError) as exc_info:
                await flow.refresh(session)

        assert exc_info.value.retry_after == 2

    @pytest.mark.asyncio
    async def test_refresh_409_other_error_raises_token_refresh_error(self):
        """409 + {"error": "some_other_error"} → TokenRefreshError (not RefreshReplayError)."""
        flow = TokenRefreshFlow()
        session = _make_session()

        with patch("specify_cli.auth.flows.refresh.PublicHttpClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = _mock_httpx_response(
                409,
                {"error": "some_other_error"},
                text="some_other_error",
            )

            with pytest.raises(TokenRefreshError) as exc_info:
                await flow.refresh(session)

        # Must NOT be a RefreshReplayError
        assert not isinstance(exc_info.value, RefreshReplayError)

    @pytest.mark.asyncio
    async def test_refresh_200_captures_generation(self):
        """200 response with generation=7 → returned StoredSession.generation == 7."""
        flow = TokenRefreshFlow()
        session = _make_session()
        body = _refresh_body()
        body["generation"] = 7

        with patch("specify_cli.auth.flows.refresh.PublicHttpClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = _mock_httpx_response(200, body)

            updated = await flow.refresh(session)

        assert updated.generation == 7

    @pytest.mark.asyncio
    async def test_refresh_200_missing_generation_is_none(self):
        """200 response without generation key → returned StoredSession.generation is None."""
        flow = TokenRefreshFlow()
        session = _make_session()
        body = _refresh_body()
        # No "generation" key in body

        with patch("specify_cli.auth.flows.refresh.PublicHttpClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = _mock_httpx_response(200, body)

            updated = await flow.refresh(session)

        assert updated.generation is None


# ---------------------------------------------------------------------------
# Refresh-hook integration tests (WP03 T012, T013)
#
# These tests drive through ``await TokenManager.refresh_if_needed()``, which is
# the actual adoption boundary where WP02/T011 installed the post-refresh
# rehydrate hook. ``flow.refresh()`` alone does NOT trigger the hook -- only
# the TokenManager entry point does.
#
# The OAuth POST is mocked with respx (the real ``PublicHttpClient`` flows
# through ``httpx.AsyncClient``); the rehydrate ``/api/v1/me`` GET is the
# sync ``request_with_fallback_sync`` call inside
# ``rehydrate_membership_if_needed`` (also intercepted by respx).
# ---------------------------------------------------------------------------


from collections.abc import Generator  # noqa: E402
from pathlib import Path  # noqa: E402

import respx  # noqa: E402

from specify_cli.auth.secure_storage import SecureStorage  # noqa: E402
from specify_cli.auth.token_manager import TokenManager  # noqa: E402
from specify_cli.auth import token_manager as _tm_module  # noqa: E402


_REFRESH_HOOK_SAAS_BASE_URL = "https://saas.example"


class _RefreshHookFakeStorage(SecureStorage):  # type: ignore[misc]
    """Minimal in-memory ``SecureStorage`` for refresh-hook integration tests."""

    def __init__(self) -> None:
        self._session: StoredSession | None = None

    def read(self) -> StoredSession | None:
        return self._session

    def write(self, session: StoredSession) -> None:
        self._session = session

    def delete(self) -> None:
        self._session = None

    @property
    def backend_name(self) -> str:
        return "file"


def _make_expired_session_with_teams(teams: list[Team]) -> StoredSession:
    """Build a ``StoredSession`` with the supplied teams and an EXPIRED access token.

    The refresh-token expiry is left far in the future so
    ``refresh_if_needed`` actually performs the OAuth dance instead of
    raising :class:`RefreshTokenExpiredError`.
    """
    now = now_utc()
    return StoredSession(
        user_id="user-1",
        email="a@b.com",
        name="A B",
        teams=teams,
        default_team_id=teams[0].id if teams else "",
        access_token="access-v1",
        refresh_token="refresh-v1",
        session_id="sess",
        issued_at=now,
        # Expired so refresh_if_needed will run
        access_token_expires_at=now - timedelta(seconds=60),
        refresh_token_expires_at=now + timedelta(days=30),
        scope="openid",
        storage_backend="file",
        last_used_at=now,
        auth_method="authorization_code",
    )


@pytest.fixture
def _isolate_refresh_hook_lock(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Generator[Path, None, None]:
    """Redirect the machine-wide refresh lock into ``tmp_path``.

    Without this every test in this group would touch the real
    ``~/.spec-kitty/auth/refresh.lock`` file, which is unsafe under parallel
    test execution.
    """
    lock_path = tmp_path / "refresh.lock"
    monkeypatch.setattr(_tm_module, "_refresh_lock_path", lambda: lock_path)
    yield lock_path


@pytest.fixture
def _refresh_hook_saas_url(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None, None, None]:
    """Override the autouse ``_saas_url`` fixture for these tests.

    The integration tests below mock ``https://saas.example`` because that
    matches the URL used by the WP02 refresh-hook contract tests in
    ``tests/auth/test_token_manager.py``.
    """
    monkeypatch.setenv("SPEC_KITTY_SAAS_URL", _REFRESH_HOOK_SAAS_BASE_URL)
    yield


@pytest.fixture
def token_manager_with_expired_shared_only_session(
    _isolate_refresh_hook_lock: Path,
    _refresh_hook_saas_url: None,
) -> TokenManager:
    """A ``TokenManager`` with an expired access token whose session has only shared teams."""
    storage = _RefreshHookFakeStorage()
    session = _make_expired_session_with_teams(
        [
            Team(
                id="t-shared",
                name="Shared",
                role="member",
                is_private_teamspace=False,
            ),
        ]
    )
    storage.write(session)
    tm = TokenManager(storage, saas_base_url=_REFRESH_HOOK_SAAS_BASE_URL)
    tm._session = session
    return tm


@pytest.fixture
def token_manager_with_expired_private_session(
    _isolate_refresh_hook_lock: Path,
    _refresh_hook_saas_url: None,
) -> TokenManager:
    """A ``TokenManager`` with an expired access token whose session already has a Private Teamspace."""
    storage = _RefreshHookFakeStorage()
    session = _make_expired_session_with_teams(
        [
            Team(
                id="t-private",
                name="Private",
                role="owner",
                is_private_teamspace=True,
            ),
        ]
    )
    storage.write(session)
    tm = TokenManager(storage, saas_base_url=_REFRESH_HOOK_SAAS_BASE_URL)
    tm._session = session
    return tm


@pytest.mark.asyncio
@respx.mock
async def test_refresh_force_rehydrates_when_adopted_session_lacks_private_team(
    token_manager_with_expired_shared_only_session: TokenManager,
) -> None:
    """A refresh whose adopted session lacks a Private Teamspace must trigger
    ``rehydrate_membership_if_needed(force=True)`` and end with a private session."""
    # OAuth refresh response (PublicHttpClient → httpx.AsyncClient)
    respx.post(f"{_REFRESH_HOOK_SAAS_BASE_URL}/oauth/token").mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "new-tok",
                "refresh_token": "new-rtok",
                "expires_in": 3600,
                "scope": "openid",
            },
        )
    )
    # /api/v1/me — provides the Private Teamspace
    me_route = respx.get(f"{_REFRESH_HOOK_SAAS_BASE_URL}/api/v1/me").mock(
        return_value=httpx.Response(
            200,
            json={
                "email": "u@example.com",
                "teams": [
                    {
                        "id": "t-private",
                        "name": "Private",
                        "role": "owner",
                        "is_private_teamspace": True,
                    },
                    {
                        "id": "t-shared",
                        "name": "Shared",
                        "role": "member",
                        "is_private_teamspace": False,
                    },
                ],
            },
        )
    )

    refreshed = await token_manager_with_expired_shared_only_session.refresh_if_needed()

    assert refreshed is True
    assert me_route.call_count == 1
    updated = token_manager_with_expired_shared_only_session.get_current_session()
    assert updated is not None
    assert any(t.is_private_teamspace for t in updated.teams)
    # default_team_id is recomputed via pick_default_team_id, NOT preserved
    # from the old shared-only session.
    assert updated.default_team_id == "t-private"


@pytest.mark.asyncio
@respx.mock
async def test_refresh_healthy_session_no_extra_me_call(
    token_manager_with_expired_private_session: TokenManager,
) -> None:
    """Refresh with an already-private session must NOT issue ``/api/v1/me``.

    FR-011 / NFR-004 regression guard: healthy refresh stays a single round trip.
    """
    respx.post(f"{_REFRESH_HOOK_SAAS_BASE_URL}/oauth/token").mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "new-tok",
                "refresh_token": "new-rtok",
                "expires_in": 3600,
                "scope": "openid",
            },
        )
    )
    me_route = respx.get(f"{_REFRESH_HOOK_SAAS_BASE_URL}/api/v1/me").mock(
        return_value=httpx.Response(200, json={})
    )

    refreshed = await token_manager_with_expired_private_session.refresh_if_needed()

    assert refreshed is True
    assert me_route.call_count == 0


class TestRefreshCredentialDiagnostics:
    """Issue #3233: recovery guidance must not expose credentials."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("refresh_token", [None, "", " ", "\t\n"])
    async def test_missing_refresh_credential_never_opens_http_client(self, refresh_token):
        with (
            patch("specify_cli.auth.flows.refresh.PublicHttpClient") as client,
            pytest.raises(TokenRefreshError, match="refresh credential.*auth login"),
        ):
            await TokenRefreshFlow().refresh(_make_session(refresh_token=refresh_token))
        client.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status_code", [400, 401])
    @pytest.mark.parametrize(
        ("error", "diagnostic", "recovery"),
        [
            ("invalid_request", "refresh request", "auth login"),
            ("invalid_client", "client identification", "administrator"),
        ],
    )
    async def test_known_errors_explain_distinct_recovery(self, status_code, error, diagnostic, recovery):
        secret = "sensitive-refresh-credential"
        with patch("specify_cli.auth.flows.refresh.PublicHttpClient") as client:
            http = AsyncMock()
            client.return_value.__aenter__.return_value = http
            http.post.return_value = _mock_httpx_response(
                status_code, {"error": error, "error_description": secret}, text=secret
            )
            with pytest.raises(TokenRefreshError) as caught:
                await TokenRefreshFlow().refresh(_make_session())
        message = str(caught.value)
        assert error in message
        assert diagnostic in message
        assert recovery in message
        assert secret not in message

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status_code", [400, 401, 409, 500])
    async def test_unrecognized_http_error_does_not_echo_body(self, status_code):
        secret = "sensitive-refresh-credential"
        with patch("specify_cli.auth.flows.refresh.PublicHttpClient") as client:
            http = AsyncMock()
            client.return_value.__aenter__.return_value = http
            http.post.return_value = _mock_httpx_response(
                status_code, {"error": secret}, text=secret
            )
            with pytest.raises(TokenRefreshError) as caught:
                await TokenRefreshFlow().refresh(_make_session())
        assert f"HTTP {status_code}" in str(caught.value)
        assert secret not in str(caught.value)


    @pytest.mark.asyncio
    @pytest.mark.parametrize("payload", [None, [], "sensitive-refresh-credential"])
    @pytest.mark.parametrize("status_code", [400, 401, 409])
    async def test_non_object_error_json_uses_safe_http_diagnostic(self, payload, status_code):
        with patch("specify_cli.auth.flows.refresh.PublicHttpClient") as client:
            http = AsyncMock()
            client.return_value.__aenter__.return_value = http
            response = _mock_httpx_response(status_code, text="sensitive-refresh-credential")
            response.json.return_value = payload
            http.post.return_value = response
            with pytest.raises(TokenRefreshError, match=f"HTTP {status_code}") as caught:
                await TokenRefreshFlow().refresh(_make_session())
        assert "sensitive-refresh-credential" not in str(caught.value)
