"""Tests for SaasClient.check_repo_admission (TEAM-ADMIT-M2-09).

Client-only coverage per ADR-TEAM-REPO-ADMISSION-2026-08-24 §4.3 item 2: the
new ``check_repo_admission`` method against both real response shapes the
endpoint (TEAM-ADMIT-M2-07/08) returns, both under HTTP 200:

- Admitted:     {"admitted": true, "team": {...}, "provider", "repo_slug", "checked_at"}
- Not admitted: {"admitted": false, "reason": "no_match"}

No caching and no gate wiring here — those are TEAM-ADMIT-M2-10/11.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import httpx
import pytest
import respx

from specify_cli.saas_client import SaasAuthError, SaasClient, SaasNotFoundError, SaasTimeoutError
from specify_cli.saas_client.errors import SaasConsentError
from specify_cli.saas_client.endpoints import AdmissionAnswer

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _make_client(response_data: object, status_code: int = 200) -> SaasClient:
    """Build a SaasClient backed by a mock httpx.Client returning fixed data."""
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = status_code
    mock_resp.is_success = 200 <= status_code < 300
    mock_resp.json.return_value = response_data
    mock_resp.text = json.dumps(response_data) if isinstance(response_data, (dict, list)) else str(response_data)

    mock_http = MagicMock(spec=httpx.Client)
    mock_http.get.return_value = mock_resp
    return SaasClient("http://test", "tok", team_slug="my-team", _http=mock_http)


# ---------------------------------------------------------------------------
# Response-shape parsing (mocked httpx.Client)
# ---------------------------------------------------------------------------


def test_admitted_shape_is_parsed() -> None:
    """The admitted:true shape parses into AdmissionAnswer with team/provider/checked_at."""
    client = _make_client(
        {
            "admitted": True,
            "team": {"id": "T1", "slug": "acme", "name": "Acme Corp"},
            "provider": "github",
            "repo_slug": "acme/widget",
            "checked_at": "2026-08-24T12:00:00Z",
        }
    )
    result = client.check_repo_admission("acme/widget", host="github.com")
    assert result["admitted"] is True
    assert result["team"] == {"id": "T1", "slug": "acme", "name": "Acme Corp"}
    assert result["provider"] == "github"
    assert result["repo_slug"] == "acme/widget"
    assert result["checked_at"] == "2026-08-24T12:00:00Z"


def test_not_admitted_shape_is_parsed() -> None:
    """The admitted:false shape parses with reason and no team/provider."""
    client = _make_client({"admitted": False, "reason": "no_match"})
    result: AdmissionAnswer = client.check_repo_admission("acme/widget", host="github.com")
    assert result["admitted"] is False
    assert result["reason"] == "no_match"
    assert result.get("team") is None
    assert result.get("provider") is None


def test_host_is_optional() -> None:
    """host defaults to None and the call still succeeds."""
    client = _make_client({"admitted": False, "reason": "no_match"})
    result = client.check_repo_admission("acme/widget")
    assert result["admitted"] is False


def test_repo_slug_falls_back_to_request_value_when_response_omits_it() -> None:
    """A negative answer may echo the request for display, never as authority."""
    client = _make_client({"admitted": False, "reason": "no_match"})
    result = client.check_repo_admission("acme/widget", host="github.com")
    assert result["repo_slug"] == "acme/widget"


@pytest.mark.parametrize("data", [None, [], "not-an-object", {"admitted": True}, {"admitted": True, "repo_slug": 42}])
def test_malformed_admission_cannot_supply_authority(data) -> None:
    with pytest.raises(SaasConsentError):
        _make_client(data).check_repo_admission("acme/widget", host="github.com")


# ---------------------------------------------------------------------------
# Error mapping — distinguishable from a genuine admitted:false
# ---------------------------------------------------------------------------


def test_timeout_raises_saas_timeout_error_not_admitted_false() -> None:
    """A network timeout raises — it must never be confused with admitted:false."""
    mock_http = MagicMock(spec=httpx.Client)
    mock_http.get.side_effect = httpx.TimeoutException("timed out")
    client = SaasClient("http://test", "tok", team_slug="my-team", _http=mock_http)
    with pytest.raises(SaasTimeoutError):
        client.check_repo_admission("acme/widget", host="github.com")


def test_401_raises_saas_auth_error() -> None:
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 401
    mock_resp.is_success = False
    mock_resp.text = "Unauthorized"
    mock_http = MagicMock(spec=httpx.Client)
    mock_http.get.return_value = mock_resp
    client = SaasClient("http://test", "tok", team_slug="my-team", _http=mock_http)
    with pytest.raises(SaasAuthError) as exc_info:
        client.check_repo_admission("acme/widget", host="github.com")
    assert exc_info.value.status_code == 401


def test_404_raises_saas_not_found_error() -> None:
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 404
    mock_resp.is_success = False
    mock_resp.text = "Not Found"
    mock_http = MagicMock(spec=httpx.Client)
    mock_http.get.return_value = mock_resp
    client = SaasClient("http://test", "tok", team_slug="my-team", _http=mock_http)
    with pytest.raises(SaasNotFoundError):
        client.check_repo_admission("acme/widget", host="github.com")


# ---------------------------------------------------------------------------
# respx integration — real HTTP-level request shape
# ---------------------------------------------------------------------------


class TestRespxIntegration:
    """Full HTTP-level tests using respx to mock the httpx transport."""

    BASE = "http://saas-test"

    def _client(self, http_client: httpx.Client) -> SaasClient:
        return SaasClient(self.BASE, "test-token", team_slug="my-team", _http=http_client)

    def test_sends_repo_slug_and_host_as_query_params(self) -> None:
        """GET is issued against /api/v1/sync/repo-admission/ with both query params."""
        with respx.mock:
            route = respx.get(f"{self.BASE}/api/v1/sync/repo-admission/").respond(
                200,
                json={
                    "admitted": True,
                    "team": {"id": "T1", "slug": "acme", "name": "Acme"},
                    "provider": "github",
                    "repo_slug": "acme/widget",
                    "checked_at": "2026-08-24T12:00:00Z",
                },
            )
            client = self._client(httpx.Client())
            result = client.check_repo_admission("acme/widget", host="github.com")

        assert route.called
        sent_query = dict(httpx.QueryParams(route.calls[0].request.url.query))
        assert sent_query == {"repo_slug": "acme/widget", "host": "github.com"}
        assert result["admitted"] is True
        assert result["team"]["slug"] == "acme"

    def test_omits_host_query_param_when_not_given(self) -> None:
        """host=None means no host param is sent at all (not host=None/empty)."""
        with respx.mock:
            route = respx.get(f"{self.BASE}/api/v1/sync/repo-admission/").respond(200, json={"admitted": False, "reason": "no_match"})
            client = self._client(httpx.Client())
            client.check_repo_admission("acme/widget")

        sent_query = dict(httpx.QueryParams(route.calls[0].request.url.query))
        assert sent_query == {"repo_slug": "acme/widget"}
        assert "host" not in sent_query

    def test_not_admitted_respx(self) -> None:
        """respx: the admitted:false/no_match shape round-trips end to end."""
        with respx.mock:
            respx.get(f"{self.BASE}/api/v1/sync/repo-admission/").respond(200, json={"admitted": False, "reason": "no_match"})
            client = self._client(httpx.Client())
            result = client.check_repo_admission("acme/widget", host="gitlab.com")

        assert result["admitted"] is False
        assert result["reason"] == "no_match"

    def test_timeout_respx(self) -> None:
        """respx: a transport-level timeout raises SaasTimeoutError."""
        with respx.mock:
            respx.get(f"{self.BASE}/api/v1/sync/repo-admission/").mock(side_effect=httpx.TimeoutException("timed out"))
            client = self._client(httpx.Client())
            with pytest.raises(SaasTimeoutError):
                client.check_repo_admission("acme/widget", host="github.com")

    def test_401_respx(self) -> None:
        """respx: a 401 response raises SaasAuthError, never a false admitted:false."""
        with respx.mock:
            respx.get(f"{self.BASE}/api/v1/sync/repo-admission/").respond(401, text="Unauthorized")
            client = self._client(httpx.Client())
            with pytest.raises(SaasAuthError) as exc_info:
                client.check_repo_admission("acme/widget", host="github.com")
        assert exc_info.value.status_code == 401
