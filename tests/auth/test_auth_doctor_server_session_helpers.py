"""Direct tests for the ``_check_server_session`` campsite extraction.

``_check_server_session`` measured at C901=14 (the mccabe ceiling is 15)
before a caller-census edit raised it further. This extracted three
pure/near-pure helpers -- ``_resolve_target_for_server_session``,
``_acquire_access_token_for_server_session``, and
``_classify_session_status_response`` -- with no behaviour change (the
existing ``tests/auth/test_auth_doctor_report.py`` suite pins
``_check_server_session``'s end-to-end behaviour unchanged). These tests
exercise the extracted helpers directly.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from specify_cli.auth.errors import (
    NotAuthenticatedError,
    RefreshTokenExpiredError,
    SessionInvalidError,
    TokenRefreshError,
)
from specify_cli.auth.refresh_transaction import RefreshLockTimeoutError
from specify_cli.auth.server_target import OverrideMode, ResolvedServerTarget, ServerTargetSplitBrainError
from specify_cli.cli.commands._auth_doctor import (
    ServerSessionStatus,
    _acquire_access_token_for_server_session,
    _classify_session_status_response,
    _resolve_target_for_server_session,
)

pytestmark = [pytest.mark.fast]


def _target(url: str = "https://saas.test") -> ResolvedServerTarget:
    return ResolvedServerTarget(
        configured_server_url=None,
        env_server_url=url,
        override_mode=OverrideMode.PROCESS_OVERRIDE,
        resolved_server_url=url,
    )


# ---------------------------------------------------------------------------
# _resolve_target_for_server_session
# ---------------------------------------------------------------------------


class TestResolveTargetForServerSession:
    def test_returns_target_on_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import specify_cli.cli.commands._auth_doctor as mod

        target = _target()
        monkeypatch.setattr(mod, "resolve_server_target", lambda **_: target)
        monkeypatch.setattr(mod, "_server_issuer_mismatch_error", lambda *_a, **_k: None)
        tm = Mock(session_assessment=None)

        resolved, error = _resolve_target_for_server_session(tm)

        assert resolved is target
        assert error is None

    def test_split_brain_becomes_saas_url_mismatch_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import specify_cli.cli.commands._auth_doctor as mod

        def _raise(**_kwargs):
            raise ServerTargetSplitBrainError(configured_server_url="a", env_server_url="b")

        monkeypatch.setattr(mod, "resolve_server_target", _raise)
        tm = Mock(session_assessment=None)

        resolved, error = _resolve_target_for_server_session(tm)

        assert resolved is None
        assert error is not None
        assert "SaaS URL mismatch" in error

    def test_any_other_resolution_failure_is_saas_url_not_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import specify_cli.cli.commands._auth_doctor as mod

        def _raise(**_kwargs):
            raise RuntimeError("boom")

        monkeypatch.setattr(mod, "resolve_server_target", _raise)
        tm = Mock(session_assessment=None)

        resolved, error = _resolve_target_for_server_session(tm)

        assert resolved is None
        assert error == "SaaS URL not configured"

    def test_issuer_mismatch_short_circuits_before_storage_check(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import specify_cli.cli.commands._auth_doctor as mod

        target = _target()
        monkeypatch.setattr(mod, "resolve_server_target", lambda **_: target)
        monkeypatch.setattr(mod, "_server_issuer_mismatch_error", lambda *_a, **_k: "mismatch!")
        tm = Mock(session_assessment=None)

        resolved, error = _resolve_target_for_server_session(tm)

        assert resolved is None
        assert error == "mismatch!"

    def test_storage_permissions_refusal_short_circuits(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import specify_cli.cli.commands._auth_doctor as mod

        target = _target()
        monkeypatch.setattr(mod, "resolve_server_target", lambda **_: target)
        monkeypatch.setattr(mod, "_server_issuer_mismatch_error", lambda *_a, **_k: None)
        assessment = Mock(reason="storage_permissions_unsafe", detail="chmod 600 the file")
        tm = Mock(session_assessment=assessment)

        resolved, error = _resolve_target_for_server_session(tm)

        assert resolved is None
        assert error == "chmod 600 the file"


# ---------------------------------------------------------------------------
# _acquire_access_token_for_server_session
# ---------------------------------------------------------------------------


class TestAcquireAccessTokenForServerSession:
    async def test_returns_token_on_success(self) -> None:
        tm = MagicMock()
        tm.get_access_token = AsyncMock(return_value="at_123")

        token, error = await _acquire_access_token_for_server_session(tm)

        assert token == "at_123"
        assert error is None

    @pytest.mark.parametrize(
        "exc",
        [NotAuthenticatedError("x"), RefreshTokenExpiredError("x"), SessionInvalidError("x")],
    )
    async def test_dead_session_errors_map_to_reauthenticate(self, exc: Exception) -> None:
        tm = MagicMock()
        tm.get_access_token = AsyncMock(side_effect=exc)

        token, error = await _acquire_access_token_for_server_session(tm)

        assert token is None
        assert error == "re-authenticate"

    async def test_lock_timeout_uses_its_own_message(self) -> None:
        tm = MagicMock()
        tm.get_access_token = AsyncMock(side_effect=RefreshLockTimeoutError("busy, try later"))

        token, error = await _acquire_access_token_for_server_session(tm)

        assert token is None
        assert error == "busy, try later"

    async def test_token_refresh_error_gets_generic_remedy(self) -> None:
        tm = MagicMock()
        tm.get_access_token = AsyncMock(side_effect=TokenRefreshError("server said no"))

        token, error = await _acquire_access_token_for_server_session(tm)

        assert token is None
        assert error is not None
        assert "spec-kitty auth login" in error

    async def test_unexpected_error_gets_catch_all_message(self) -> None:
        tm = MagicMock()
        tm.get_access_token = AsyncMock(side_effect=RuntimeError("boom"))

        token, error = await _acquire_access_token_for_server_session(tm)

        assert token is None
        assert error == "Could not obtain access token."


# ---------------------------------------------------------------------------
# _classify_session_status_response
# ---------------------------------------------------------------------------


class TestClassifySessionStatusResponse:
    def test_200_with_session_id_is_active(self) -> None:
        response = Mock(status_code=200)
        response.json.return_value = {"session_id": "s1"}

        result = _classify_session_status_response(response)

        assert result == ServerSessionStatus(active=True, session_id="s1")

    def test_200_with_invalid_json_is_inactive(self) -> None:
        response = Mock(status_code=200)
        response.json.side_effect = ValueError("bad json")

        result = _classify_session_status_response(response)

        assert result == ServerSessionStatus(active=False, error="Invalid response from server")

    def test_401_maps_to_reauthenticate(self) -> None:
        response = Mock(status_code=401)

        result = _classify_session_status_response(response)

        assert result == ServerSessionStatus(active=False, error="re-authenticate")

    def test_other_status_names_the_http_code(self) -> None:
        response = Mock(status_code=503)

        result = _classify_session_status_response(response)

        assert result == ServerSessionStatus(active=False, error="Server returned HTTP 503")
