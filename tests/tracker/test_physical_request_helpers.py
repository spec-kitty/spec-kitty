"""Direct tests for the ``_physical_request_with_retry`` campsite extraction.

``_physical_request_with_retry`` measured at C901=15 (the mccabe ceiling)
before a caller-census edit. This extracted three helpers --
``_retry_on_unauthorized``, ``_retry_on_rate_limit``, and
``_raise_for_terminal_error`` -- with no behaviour change: the existing
``tests/tracker/test_saas_client.py`` suite pins the end-to-end
401/429/error-envelope behaviour unchanged. These tests exercise the
extracted helpers directly.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest
from kernel.clock import now_utc, timedelta

from specify_cli.tracker.saas_client import SaaSTrackerClient, SaaSTrackerClientError

pytestmark = pytest.mark.fast


def _response(status_code: int, json_body: dict | None = None) -> httpx.Response:
    resp = httpx.Response(
        status_code=status_code,
        request=httpx.Request("GET", "https://example.com"),
    )
    if json_body is not None:
        import json as _json

        resp._content = _json.dumps(json_body).encode()
        resp.headers["content-type"] = "application/json"
    else:
        resp._content = b""
    return resp


@pytest.fixture()
def client() -> SaaSTrackerClient:
    return SaaSTrackerClient(timeout=5.0)


def _authority() -> MagicMock:
    authority = MagicMock()
    authority.collaborative_team_slug = "acme"
    authority.account_identity = "acct_1"
    authority.private_teamspace_id = "tm_priv"
    return authority


def _deadline_args(client: SaaSTrackerClient, *, seconds: float = 30.0) -> dict:
    return {
        "deadline": now_utc() + timedelta(seconds=seconds),
        "monotonic_deadline": client._monotonic() + seconds,
    }


# ---------------------------------------------------------------------------
# _retry_on_unauthorized
# ---------------------------------------------------------------------------


class TestRetryOnUnauthorized:
    def test_non_401_response_passes_through_unchanged(self, client: SaaSTrackerClient) -> None:
        response = _response(200)

        result = client._retry_on_unauthorized(
            response,
            method="GET",
            path="/x",
            json=None,
            headers=None,
            params=None,
            authority=_authority(),
            **_deadline_args(client),
        )

        assert result is response

    def test_successful_refresh_and_retry_returns_new_response(self, client: SaaSTrackerClient) -> None:
        retried = _response(200)
        with (
            patch("specify_cli.tracker.saas_client._force_refresh_sync"),
            patch.object(client, "_request", return_value=retried) as mock_request,
        ):
            result = client._retry_on_unauthorized(
                _response(401),
                method="GET",
                path="/x",
                json=None,
                headers=None,
                params=None,
                authority=_authority(),
                **_deadline_args(client),
            )

        assert result is retried
        mock_request.assert_called_once()

    def test_refresh_failure_raises_session_expired(self, client: SaaSTrackerClient) -> None:
        with (
            patch(
                "specify_cli.tracker.saas_client._force_refresh_sync",
                side_effect=RuntimeError("boom"),
            ),
            pytest.raises(SaaSTrackerClientError) as excinfo,
        ):
            client._retry_on_unauthorized(
                _response(401),
                method="GET",
                path="/x",
                json=None,
                headers=None,
                params=None,
                authority=_authority(),
                **_deadline_args(client),
            )
        assert excinfo.value.error_code == "session_expired"

    def test_second_401_after_refresh_raises_session_expired(self, client: SaaSTrackerClient) -> None:
        with (
            patch("specify_cli.tracker.saas_client._force_refresh_sync"),
            patch.object(client, "_request", return_value=_response(401)),
            pytest.raises(SaaSTrackerClientError) as excinfo,
        ):
            client._retry_on_unauthorized(
                _response(401),
                method="GET",
                path="/x",
                json=None,
                headers=None,
                params=None,
                authority=_authority(),
                **_deadline_args(client),
            )
        assert excinfo.value.error_code == "session_expired"

    def test_deadline_exhausted_after_refresh_raises_deadline_exceeded(self, client: SaaSTrackerClient) -> None:
        with (
            patch("specify_cli.tracker.saas_client._force_refresh_sync"),
            pytest.raises(SaaSTrackerClientError) as excinfo,
        ):
            client._retry_on_unauthorized(
                _response(401),
                method="GET",
                path="/x",
                json=None,
                headers=None,
                params=None,
                authority=_authority(),
                deadline=now_utc() - timedelta(seconds=1),
                monotonic_deadline=-1.0,
            )
        assert excinfo.value.error_code == "deadline_exceeded"


# ---------------------------------------------------------------------------
# _retry_on_rate_limit
# ---------------------------------------------------------------------------


class TestRetryOnRateLimit:
    def test_non_429_response_passes_through_unchanged(self, client: SaaSTrackerClient) -> None:
        response = _response(200)

        result = client._retry_on_rate_limit(
            response,
            method="GET",
            path="/x",
            json=None,
            headers=None,
            params=None,
            authority=_authority(),
            **_deadline_args(client),
        )

        assert result is response

    def test_retries_after_sleeping_the_retry_after_window(self, client: SaaSTrackerClient) -> None:
        retried = _response(200)
        client._sleep = MagicMock()
        with patch.object(client, "_request", return_value=retried) as mock_request:
            result = client._retry_on_rate_limit(
                _response(429, {"retry_after_seconds": 1}),
                method="GET",
                path="/x",
                json=None,
                headers=None,
                params=None,
                authority=_authority(),
                **_deadline_args(client),
            )

        assert result is retried
        client._sleep.assert_called_once_with(1.0)
        mock_request.assert_called_once()

    def test_second_429_raises_rate_limited(self, client: SaaSTrackerClient) -> None:
        client._sleep = MagicMock()
        with (
            patch.object(client, "_request", return_value=_response(429, {"message": "still limited"})),
            pytest.raises(SaaSTrackerClientError) as excinfo,
        ):
            client._retry_on_rate_limit(
                _response(429, {"retry_after_seconds": 1}),
                method="GET",
                path="/x",
                json=None,
                headers=None,
                params=None,
                authority=_authority(),
                **_deadline_args(client),
            )
        assert excinfo.value.error_code == "rate_limited"

    def test_retry_that_would_exceed_deadline_raises_deadline_exceeded(self, client: SaaSTrackerClient) -> None:
        with pytest.raises(SaaSTrackerClientError) as excinfo:
            client._retry_on_rate_limit(
                _response(429, {"retry_after_seconds": 999}),
                method="GET",
                path="/x",
                json=None,
                headers=None,
                params=None,
                authority=_authority(),
                **_deadline_args(client),
            )
        assert excinfo.value.error_code == "deadline_exceeded"

    def test_missing_retry_after_defaults_to_five_seconds(self, client: SaaSTrackerClient) -> None:
        client._sleep = MagicMock()
        with patch.object(client, "_request", return_value=_response(200)):
            client._retry_on_rate_limit(
                _response(429, {}),
                method="GET",
                path="/x",
                json=None,
                headers=None,
                params=None,
                authority=_authority(),
                **_deadline_args(client),
            )
        client._sleep.assert_called_once_with(5.0)


# ---------------------------------------------------------------------------
# _raise_for_terminal_error
# ---------------------------------------------------------------------------


class TestRaiseForTerminalError:
    def test_success_response_passes_through(self, client: SaaSTrackerClient) -> None:
        response = _response(200)

        result = client._raise_for_terminal_error(response, allow_error_response=False)

        assert result is response

    def test_error_response_with_allow_error_response_passes_through(self, client: SaaSTrackerClient) -> None:
        response = _response(404, {"message": "not found"})

        result = client._raise_for_terminal_error(response, allow_error_response=True)

        assert result is response

    def test_error_response_raises_with_message_and_code(self, client: SaaSTrackerClient) -> None:
        response = _response(404, {"message": "not found", "error_code": "not_found"})

        with pytest.raises(SaaSTrackerClientError) as excinfo:
            client._raise_for_terminal_error(response, allow_error_response=False)

        assert excinfo.value.error_code == "not_found"
        assert "not found" in str(excinfo.value)

    def test_user_action_required_appends_guidance(self, client: SaaSTrackerClient) -> None:
        response = _response(400, {"message": "bad", "user_action_required": True})

        with pytest.raises(SaaSTrackerClientError) as excinfo:
            client._raise_for_terminal_error(response, allow_error_response=False)

        assert "action required" in str(excinfo.value)

    def test_falls_back_to_error_category_when_no_error_code(self, client: SaaSTrackerClient) -> None:
        response = _response(400, {"message": "bad", "error_category": "validation"})

        with pytest.raises(SaaSTrackerClientError) as excinfo:
            client._raise_for_terminal_error(response, allow_error_response=False)

        assert excinfo.value.error_code == "validation"
