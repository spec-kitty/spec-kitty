"""E2E test for ``spec-kitty auth login --headless`` via CliRunner.

Covers the RFC 8628 device authorization happy path end-to-end:

1. CliRunner invokes the real Typer ``app`` with ``["login", "--headless"]``.
2. ``_auth_login.login_impl`` dispatches to
   :class:`specify_cli.auth.flows.device_code.DeviceCodeFlow`.
3. ``httpx.AsyncClient`` is patched to serve ``/oauth/device``,
   ``/oauth/token`` (first-call success), and ``/api/v1/me``.
4. :class:`SecureStorage.from_environment` is patched to an in-memory
   storage so the resulting :class:`StoredSession` is captured.

FR coverage: FR-002 (device flow fallback), FR-018 (polling interval cap),
FR-019 (user-code formatting), FR-020 (no browser for ``--headless``),
FR-016 (TokenManager is sole credential surface).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from typer.testing import CliRunner

from specify_cli.auth import get_token_manager
from specify_cli.cli.commands.auth import app

from .conftest import FakeSecureStorage


pytestmark = [pytest.mark.integration]

runner = CliRunner()


def _device_response() -> dict[str, Any]:
    """Return a successful ``/oauth/device`` response body.

    ``interval=0`` keeps the poller hot in tests so we do not wait 5s.
    """
    return {
        "device_code": "device_code_xyz",
        "user_code": "ABCD1234",
        "verification_uri": "https://saas.test/device",
        "verification_uri_complete": "https://saas.test/device?user_code=ABCD1234",
        "expires_in": 900,
        "interval": 0,
    }


def _token_response() -> dict[str, Any]:
    """Return a successful ``/oauth/token`` response after device approval.

    Uses ``refresh_token_expires_at`` (absolute) per C-012 to exercise
    the preferred branch of :meth:`_resolve_refresh_expiry`.
    """
    return {
        "access_token": "at_device_xyz",
        "refresh_token": "rt_device_xyz",
        "expires_in": 3600,
        "refresh_token_expires_at": "2099-01-01T00:00:00+00:00",
        "scope": "offline_access",
        "session_id": "sess_device_xyz",
        "token_type": "Bearer",
    }


def _me_response() -> dict[str, Any]:
    """Return a successful ``/api/v1/me`` response body."""
    return {
        "user_id": "u_alice",
        "email": "alice@example.com",
        "name": "Alice Developer",
        "teams": [{"id": "tm_acme", "name": "Acme Corp", "role": "admin"}],
        "default_team_id": "tm_acme",
        "session_id": "sess_device_xyz",
    }


def _mock_httpx_response(
    status_code: int, json_body: dict[str, Any]
) -> MagicMock:
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.text = str(json_body)
    response.json = MagicMock(return_value=json_body)
    return response


class TestHeadlessLoginE2E:
    """End-to-end device flow via CliRunner."""

    def test_full_device_flow_happy_path(
        self,
        fake_storage: FakeSecureStorage,
    ) -> None:
        """CliRunner → login_impl → DeviceCodeFlow → StoredSession.

        Validates FR-002 (device flow as fallback), FR-020 (no browser),
        and FR-016 (TokenManager is sole credential surface).
        """
        post_call_count = {"value": 0}

        async def _post(
            url: str,
            data: dict[str, Any] | None = None,
            headers: dict[str, str] | None = None,
            **kwargs: Any,
        ) -> MagicMock:
            post_call_count["value"] += 1
            if url.endswith("/oauth/device"):
                return _mock_httpx_response(200, _device_response())
            if url.endswith("/oauth/token"):
                # First token poll succeeds immediately.
                return _mock_httpx_response(200, _token_response())
            raise AssertionError(f"unexpected POST: {url}")

        async def _get(
            url: str,
            headers: dict[str, str] | None = None,
            **kwargs: Any,
        ) -> MagicMock:
            if url.endswith("/api/v1/me"):
                return _mock_httpx_response(200, _me_response())
            raise AssertionError(f"unexpected GET: {url}")

        # Also patch BrowserLauncher so a FR-020 violation (accidental
        # browser launch in --headless mode) would surface as a test
        # failure: the mock would be called and we assert it wasn't.
        with (
            patch(
                "specify_cli.auth.secure_storage.SecureStorage.from_environment",
                return_value=fake_storage,
            ),
            patch("httpx.AsyncClient") as mock_client_cls,
            patch(
                "specify_cli.auth.loopback.browser_launcher.BrowserLauncher.launch"
            ) as mock_launch,
        ):
            fake_client = AsyncMock()
            fake_client.post = AsyncMock(side_effect=_post)
            fake_client.get = AsyncMock(side_effect=_get)
            mock_client_cls.return_value.__aenter__.return_value = fake_client

            result = runner.invoke(app, ["login", "--headless"])

            # FR-020: headless must NEVER call BrowserLauncher.launch.
            mock_launch.assert_not_called()

        assert result.exit_code == 0, (
            f"headless login failed: stdout={result.stdout!r} "
            f"exception={result.exception!r}"
        )

        # FR-019: the user code was formatted with a hyphen for humans.
        assert "ABCD-1234" in result.stdout

        # Verification URI was displayed.
        assert "https://saas.test/device" in result.stdout

        # Final authenticated banner.
        assert "alice@example.com" in result.stdout

        # FR-016: the session was written via TokenManager.
        assert len(fake_storage.writes) == 1
        stored = fake_storage.writes[0]
        assert stored.user_id == "u_alice"
        assert stored.email == "alice@example.com"
        assert stored.auth_method == "device_code"
        assert stored.default_team_id == "tm_acme"

        # Raw tokens must never leak to stdout.
        assert "at_device_xyz" not in result.stdout
        assert "rt_device_xyz" not in result.stdout

    def test_device_flow_respects_pending_poll(
        self,
        fake_storage: FakeSecureStorage,
    ) -> None:
        """``authorization_pending`` loops, then success is returned.

        Covers FR-018 (poller handles the pending state) end-to-end.
        """
        post_calls: list[str] = []
        token_call_count = {"value": 0}

        async def _post(
            url: str,
            data: dict[str, Any] | None = None,
            headers: dict[str, str] | None = None,
            **kwargs: Any,
        ) -> MagicMock:
            post_calls.append(url)
            if url.endswith("/oauth/device"):
                return _mock_httpx_response(200, _device_response())
            if url.endswith("/oauth/token"):
                token_call_count["value"] += 1
                if token_call_count["value"] == 1:
                    # First poll: still pending. RFC 8628 §3.5 says the
                    # SaaS returns HTTP 400 with error=authorization_pending,
                    # but our DeviceCodeFlow._poll_token_request treats both
                    # 200 and 400 as JSON carriers.
                    return _mock_httpx_response(
                        400, {"error": "authorization_pending"}
                    )
                # Second poll: approved.
                return _mock_httpx_response(200, _token_response())
            raise AssertionError(f"unexpected POST: {url}")

        async def _get(
            url: str, headers: dict[str, str] | None = None, **kwargs: Any
        ) -> MagicMock:
            return _mock_httpx_response(200, _me_response())

        with (
            patch(
                "specify_cli.auth.secure_storage.SecureStorage.from_environment",
                return_value=fake_storage,
            ),
            patch("httpx.AsyncClient") as mock_client_cls,
        ):
            fake_client = AsyncMock()
            fake_client.post = AsyncMock(side_effect=_post)
            fake_client.get = AsyncMock(side_effect=_get)
            mock_client_cls.return_value.__aenter__.return_value = fake_client

            result = runner.invoke(app, ["login", "--headless"])

        assert result.exit_code == 0, result.stdout
        # One device request + two token polls = 3 POSTs minimum.
        assert token_call_count["value"] >= 2
        assert len(fake_storage.writes) == 1
        assert fake_storage.writes[0].auth_method == "device_code"


def test_headless_login_uses_token_manager_factory(
    fake_storage: FakeSecureStorage,
) -> None:
    """After a successful ``--headless`` login the factory returns the session.

    FR-016: ``get_token_manager()`` is the sole credential surface.
    """

    async def _post(url: str, **kwargs: Any) -> MagicMock:
        if url.endswith("/oauth/device"):
            return _mock_httpx_response(200, _device_response())
        if url.endswith("/oauth/token"):
            return _mock_httpx_response(200, _token_response())
        raise AssertionError(f"unexpected POST: {url}")

    async def _get(url: str, **kwargs: Any) -> MagicMock:
        return _mock_httpx_response(200, _me_response())

    with (
        patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment",
            return_value=fake_storage,
        ),
        patch("httpx.AsyncClient") as mock_client_cls,
    ):
        fake_client = AsyncMock()
        fake_client.post = AsyncMock(side_effect=_post)
        fake_client.get = AsyncMock(side_effect=_get)
        mock_client_cls.return_value.__aenter__.return_value = fake_client

        result = runner.invoke(app, ["login", "--headless"])
        assert result.exit_code == 0, result.stdout

        tm = get_token_manager()
        session = tm.get_current_session()
        assert session is not None
        assert session.auth_method == "device_code"
        assert session.email == "alice@example.com"
