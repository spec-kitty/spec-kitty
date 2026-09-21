"""Direct-invocation coverage for the WS provisioning issuer/target guard.

WP04 (#4755, T015-T017) closes the dormant WebSocket-token-provisioning leak
(Path 4): ``WebSocketTokenProvisioner.provision`` now resolves the token
endpoint via the shared authority
``specify_cli.auth.server_target.resolve_token_endpoint`` *before* building
the ``/api/v1/ws-token`` URL and *before* fetching the access token, instead
of reading ``get_saas_base_url()`` directly.

This path has no live caller today (the WP08 sync client that would have
opened the WS connection died with the sync transport), so it is verified
by direct invocation of the provisioner rather than an end-to-end
reproduction — defence-in-depth per
``kitty-specs/token-target-issuer-guard-01M319HS/tasks/WP04-ws-provisioning-guard.md``.

Scope discipline (T017): this WP depends on WP01 only. The chained-refusal
test monkeypatches ``tm.refresh_if_needed`` to raise
``IssuerTargetMismatchError`` directly — it does NOT exercise WP02's actual
refresh-boundary guard implementation, so WP04 can land independently of
WP02.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kernel.clock import now_utc, timedelta
from specify_cli.auth.errors import IssuerTargetMismatchError
from specify_cli.auth.session import StoredSession, Team
from specify_cli.auth.websocket import WebSocketProvisioningError, WebSocketTokenProvisioner

pytestmark = [pytest.mark.fast]

ISSUER_URL = "https://issuer.example.com"
TARGET_URL = "https://target.example.com"


def _make_session(*, issuer_url: str | None, access_remaining_seconds: int = 3600) -> StoredSession:
    now = now_utc()
    return StoredSession(
        user_id="u_alice",
        email="alice@example.com",
        name="Alice",
        teams=[Team(id="tm_acme", name="Acme", role="admin")],
        default_team_id="tm_acme",
        access_token="at_xyz",
        refresh_token="rt_xyz",
        session_id="sess_xyz",
        issued_at=now,
        access_token_expires_at=now + timedelta(seconds=access_remaining_seconds),
        refresh_token_expires_at=now + timedelta(days=90),
        scope="offline_access",
        storage_backend="file",
        last_used_at=now,
        auth_method="authorization_code",
        issuer_url=issuer_url,
    )


class _MockResponse:
    """Minimal ``httpx.Response`` stand-in — only ``status_code`` + ``json()``."""

    def __init__(self, status_code: int, json_body: dict | None = None) -> None:
        self.status_code = status_code
        self._json = json_body if json_body is not None else {}

    def json(self) -> dict:
        return self._json


def _fake_token_manager(session: StoredSession) -> MagicMock:
    fake_tm = MagicMock()
    fake_tm.is_authenticated = True
    fake_tm.get_current_session.return_value = session
    fake_tm.get_access_token = AsyncMock(return_value="at_xyz")
    fake_tm.refresh_if_needed = AsyncMock(return_value=False)
    return fake_tm


def _install_mock_post(mock_client_cls, post_fn):
    instance = mock_client_cls.return_value.__aenter__.return_value
    instance.post = post_fn
    return instance


_WS_RESPONSE = {
    "ws_token": "ws_xyz",
    "ws_url": "wss://target.example.com/ws",
    "expires_in": 3600,
    "session_id": "sess_xyz",
}


async def _mock_post_200(url, json=None, headers=None):
    return _MockResponse(200, _WS_RESPONSE)


# ---------------------------------------------------------------------------
# T016 — direct-invocation guard tests
# ---------------------------------------------------------------------------


class TestProvisioningIssuerGuard:
    async def test_mismatch_raises_token_free_provisioning_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Issuer/target mismatch refuses before the POST — no token leaks."""
        monkeypatch.setenv("SPEC_KITTY_SAAS_URL", TARGET_URL)
        session = _make_session(issuer_url=ISSUER_URL)
        fake_tm = _fake_token_manager(session)

        with (
            patch(
                "specify_cli.auth.websocket.token_provisioning.get_token_manager",
                return_value=fake_tm,
            ),
            patch("specify_cli.auth.websocket.token_provisioning.PublicHttpClient") as mock_client,
        ):
            _install_mock_post(mock_client, _mock_post_200)
            with pytest.raises(WebSocketProvisioningError) as exc_info:
                await WebSocketTokenProvisioner().provision("tm_acme")

        message = str(exc_info.value)
        # NFR-006: zero token material in the refusal message.
        assert "at_xyz" not in message
        assert "rt_xyz" not in message
        # Names both hosts and the stable remedy so the operator can act.
        assert ISSUER_URL in message
        assert TARGET_URL in message
        assert "auth login" in message
        # Guarded before the send: no POST was ever attempted.
        fake_tm.get_access_token.assert_not_called()

    async def test_issuer_equals_target_provisions_unchanged(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """issuer == resolved target: existing happy-path behaviour is unchanged."""
        monkeypatch.setenv("SPEC_KITTY_SAAS_URL", TARGET_URL)
        session = _make_session(issuer_url=TARGET_URL)
        fake_tm = _fake_token_manager(session)

        captured_urls: list[str] = []

        async def mock_post(url, json=None, headers=None):
            captured_urls.append(url)
            return _MockResponse(200, _WS_RESPONSE)

        with (
            patch(
                "specify_cli.auth.websocket.token_provisioning.get_token_manager",
                return_value=fake_tm,
            ),
            patch("specify_cli.auth.websocket.token_provisioning.PublicHttpClient") as mock_client,
        ):
            _install_mock_post(mock_client, mock_post)
            result = await WebSocketTokenProvisioner().provision("tm_acme")

        assert result == _WS_RESPONSE
        assert captured_urls == [f"{TARGET_URL}/api/v1/ws-token"]

    async def test_legacy_none_issuer_routes_to_resolved_target(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A legacy session with no recorded issuer routes to the resolved target, no raise."""
        monkeypatch.setenv("SPEC_KITTY_SAAS_URL", TARGET_URL)
        session = _make_session(issuer_url=None)
        fake_tm = _fake_token_manager(session)

        captured_urls: list[str] = []

        async def mock_post(url, json=None, headers=None):
            captured_urls.append(url)
            return _MockResponse(200, _WS_RESPONSE)

        with (
            patch(
                "specify_cli.auth.websocket.token_provisioning.get_token_manager",
                return_value=fake_tm,
            ),
            patch("specify_cli.auth.websocket.token_provisioning.PublicHttpClient") as mock_client,
        ):
            _install_mock_post(mock_client, mock_post)
            result = await WebSocketTokenProvisioner().provision("tm_acme")

        assert result == _WS_RESPONSE
        assert captured_urls == [f"{TARGET_URL}/api/v1/ws-token"]


# ---------------------------------------------------------------------------
# T017 — chained pre-connect-refresh propagation (WP01-only)
# ---------------------------------------------------------------------------


class TestChainedRefreshPropagation:
    async def test_refresh_mismatch_propagates_unswallowed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A mismatch raised by the nested pre-connect refresh is not swallowed.

        This does NOT depend on WP02's refresh-boundary guard: it monkeypatches
        ``tm.refresh_if_needed`` directly to raise ``IssuerTargetMismatchError``,
        verifying only that ``provision`` has no swallowing ``except`` around
        the pre-connect refresh call — the propagation contract, not WP02's
        refresh internals.
        """
        monkeypatch.setenv("SPEC_KITTY_SAAS_URL", TARGET_URL)
        # Access token near expiry (well within the 300s buffer) so the
        # pre-connect refresh branch fires.
        session = _make_session(issuer_url=ISSUER_URL, access_remaining_seconds=1)
        fake_tm = _fake_token_manager(session)
        fake_tm.refresh_if_needed = AsyncMock(
            side_effect=IssuerTargetMismatchError(
                issuer_url=ISSUER_URL,
                resolved_url=TARGET_URL,
                source_name="SPEC_KITTY_SAAS_URL",
            )
        )

        with (
            patch(
                "specify_cli.auth.websocket.token_provisioning.get_token_manager",
                return_value=fake_tm,
            ),
            patch("specify_cli.auth.websocket.token_provisioning.PublicHttpClient") as mock_client,
        ):
            _install_mock_post(mock_client, _mock_post_200)
            with pytest.raises(IssuerTargetMismatchError):
                await WebSocketTokenProvisioner().provision("tm_acme")

        fake_tm.refresh_if_needed.assert_called_once()
        # Propagated straight through — never reached the endpoint resolution
        # or the send.
        fake_tm.get_access_token.assert_not_called()
