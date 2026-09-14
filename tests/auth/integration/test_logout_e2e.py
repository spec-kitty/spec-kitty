"""E2E test for ``spec-kitty auth logout`` via CliRunner.

Covers FR-001/FR-002 (server-side session revocation via ``POST /oauth/revoke``
with RFC 7009 form-encoded body) and FR-004 (local cleanup is unconditional —
server failure must not block local credential deletion).

Test isolation: imports :class:`CliRunner` and drives the real Typer app.
Does not import any flow class directly.
"""

from __future__ import annotations

from kernel.clock import UTC, now_utc, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from typer.testing import CliRunner

from specify_cli.auth import get_token_manager
from specify_cli.auth.session import StoredSession, Team
from specify_cli.cli.commands.auth import app

from .conftest import FakeSecureStorage


pytestmark = [pytest.mark.integration]

runner = CliRunner()


def _authenticated_session() -> StoredSession:
    """Return a well-formed StoredSession for logout fixtures."""
    now = now_utc()
    return StoredSession(
        user_id="u_alice",
        email="alice@example.com",
        name="Alice",
        teams=[Team(id="tm_acme", name="Acme", role="admin")],
        default_team_id="tm_acme",
        access_token="at_logout_fixture",
        refresh_token="rt_logout_fixture",
        session_id="sess_logout_fixture",
        issued_at=now,
        access_token_expires_at=now + timedelta(hours=1),
        refresh_token_expires_at=now + timedelta(days=89),
        scope="offline_access",
        storage_backend="file",
        last_used_at=now,
        auth_method="authorization_code",
    )


def _mock_httpx_response(
    status_code: int, json_body: dict[str, Any] | None = None
) -> MagicMock:
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.text = str(json_body or {})
    response.json = MagicMock(return_value=json_body or {})
    return response


class TestLogoutE2E:
    """End-to-end logout through the real Typer app."""

    def test_logout_server_success(
        self,
        fake_storage: FakeSecureStorage,
    ) -> None:
        """FR-001/FR-002: normal logout POSTs ``/oauth/revoke`` and clears locally."""
        fake_storage._session = _authenticated_session()
        captured_posts: list[tuple[str, dict[str, Any]]] = []

        async def _post(url: str, **kwargs: Any) -> MagicMock:
            captured_posts.append((url, kwargs))
            return _mock_httpx_response(200, {"revoked": True})

        with (
            patch(
                "specify_cli.auth.secure_storage.SecureStorage.from_environment",
                return_value=fake_storage,
            ),
            patch(
                "specify_cli.auth.flows.revoke.httpx.AsyncClient"
            ) as mock_client_cls,
        ):
            fake_client = AsyncMock()
            fake_client.post = AsyncMock(side_effect=_post)
            mock_client_cls.return_value.__aenter__.return_value = fake_client

            result = runner.invoke(app, ["logout"])

        assert result.exit_code == 0, result.stdout
        assert "Logged out" in result.stdout
        assert "Server revocation confirmed" in result.stdout

        # FR-001/FR-002: the server-side revoke endpoint was called.
        assert len(captured_posts) == 1
        url, kwargs = captured_posts[0]
        assert url.endswith("/oauth/revoke"), f"Expected /oauth/revoke, got {url}"

        # Body must be form-encoded with token and token_type_hint.
        data = kwargs.get("data", {})
        assert data.get("token") == "rt_logout_fixture"
        assert data.get("token_type_hint") == "refresh_token"

        # NO Authorization header on the revoke call.
        headers = kwargs.get("headers", {})
        assert "Authorization" not in headers
        assert "authorization" not in headers

        # FR-004: the local session was deleted.
        assert fake_storage.deletes == 1
        assert fake_storage.read() is None

        # Raw tokens must not leak into stdout.
        assert "at_logout_fixture" not in result.stdout
        assert "rt_logout_fixture" not in result.stdout

    def test_logout_server_failure_still_clears_local(
        self,
        fake_storage: FakeSecureStorage,
    ) -> None:
        """FR-004: server failure must not block local credential deletion.

        Simulates a network error during the ``/oauth/revoke`` call and
        asserts that local cleanup still happened.
        """
        fake_storage._session = _authenticated_session()

        async def _post(url: str, **kwargs: Any) -> MagicMock:
            raise httpx.ConnectError("DNS failure")

        with (
            patch(
                "specify_cli.auth.secure_storage.SecureStorage.from_environment",
                return_value=fake_storage,
            ),
            patch(
                "specify_cli.auth.flows.revoke.httpx.AsyncClient"
            ) as mock_client_cls,
        ):
            fake_client = AsyncMock()
            fake_client.post = AsyncMock(side_effect=_post)
            mock_client_cls.return_value.__aenter__.return_value = fake_client

            result = runner.invoke(app, ["logout"])

        assert result.exit_code == 0, result.stdout
        # The FR-004 path emits a yellow warning about the server failure
        # AND still runs local cleanup. Both must surface.
        assert "Logged out" in result.stdout
        assert "not confirmed" in result.stdout
        assert fake_storage.deletes == 1
        assert fake_storage.read() is None

    def test_logout_server_500_still_clears_local(
        self,
        fake_storage: FakeSecureStorage,
    ) -> None:
        """FR-004: HTTP 5xx must not block local cleanup either."""
        fake_storage._session = _authenticated_session()

        async def _post(url: str, **kwargs: Any) -> MagicMock:
            return _mock_httpx_response(500, {"error": "internal"})

        with (
            patch(
                "specify_cli.auth.secure_storage.SecureStorage.from_environment",
                return_value=fake_storage,
            ),
            patch(
                "specify_cli.auth.flows.revoke.httpx.AsyncClient"
            ) as mock_client_cls,
        ):
            fake_client = AsyncMock()
            fake_client.post = AsyncMock(side_effect=_post)
            mock_client_cls.return_value.__aenter__.return_value = fake_client

            result = runner.invoke(app, ["logout"])

        assert result.exit_code == 0, result.stdout
        assert "Logged out" in result.stdout
        assert "not confirmed" in result.stdout
        assert fake_storage.deletes == 1

    def test_logout_force_skips_server_call(
        self,
        fake_storage: FakeSecureStorage,
    ) -> None:
        """``--force`` must skip the server call entirely.

        Covers the ``force`` branch of :func:`logout_impl`.
        """
        fake_storage._session = _authenticated_session()
        post_calls: list[str] = []

        async def _post(url: str, **kwargs: Any) -> MagicMock:
            post_calls.append(url)
            return _mock_httpx_response(200, {"revoked": True})

        with (
            patch(
                "specify_cli.auth.secure_storage.SecureStorage.from_environment",
                return_value=fake_storage,
            ),
            patch(
                "specify_cli.auth.flows.revoke.httpx.AsyncClient"
            ) as mock_client_cls,
        ):
            fake_client = AsyncMock()
            fake_client.post = AsyncMock(side_effect=_post)
            mock_client_cls.return_value.__aenter__.return_value = fake_client

            result = runner.invoke(app, ["logout", "--force"])

        assert result.exit_code == 0, result.stdout
        assert "Logged out" in result.stdout
        # FR-004 force path: NO server call was made.
        assert post_calls == []
        assert fake_storage.deletes == 1

    def test_logout_when_not_logged_in_is_idempotent(
        self,
        fake_storage: FakeSecureStorage,
    ) -> None:
        """Logout with no active session must exit 0 (idempotent)."""
        # No session in storage.
        fake_storage._session = None

        with patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment",
            return_value=fake_storage,
        ):
            result = runner.invoke(app, ["logout"])

        assert result.exit_code == 0, result.stdout
        assert "Not logged in" in result.stdout
        # No delete attempt because there was nothing to delete.
        assert fake_storage.deletes == 0

    def test_logout_factory_returns_none_after_logout(
        self,
        fake_storage: FakeSecureStorage,
    ) -> None:
        """After logout, :func:`get_token_manager` must report no session."""
        fake_storage._session = _authenticated_session()

        async def _post(url: str, **kwargs: Any) -> MagicMock:
            return _mock_httpx_response(200, {"revoked": True})

        with (
            patch(
                "specify_cli.auth.secure_storage.SecureStorage.from_environment",
                return_value=fake_storage,
            ),
            patch(
                "specify_cli.auth.flows.revoke.httpx.AsyncClient"
            ) as mock_client_cls,
        ):
            fake_client = AsyncMock()
            fake_client.post = AsyncMock(side_effect=_post)
            mock_client_cls.return_value.__aenter__.return_value = fake_client

            result = runner.invoke(app, ["logout"])
            assert result.exit_code == 0, result.stdout

            tm = get_token_manager()
            assert tm.get_current_session() is None
            assert tm.is_authenticated is False
