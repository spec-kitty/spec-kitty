"""HTTP-level contract tests for discovery and binding endpoints.

Tests the four new endpoints (resources, bind-resolve, bind-confirm,
bind-validate), the binding_ref routing variant on existing endpoints,
and stale-binding error codes preserved in SaaSTrackerClientError.

These tests mock at the ``httpx.Client`` level using the ``_make_response()``
helper pattern established in ``test_saas_client.py``.
"""

from __future__ import annotations

import json as _json
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from specify_cli.tracker.saas_client import (
    SaaSTrackerClient,
    SaaSTrackerClientError,
)

pytestmark = pytest.mark.fast


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------


def _make_response(
    status_code: int = 200,
    json_body: dict[str, Any] | None = None,
    *,
    text: str = "",
) -> httpx.Response:
    """Build a fake httpx.Response with the given status and JSON body."""
    resp = httpx.Response(
        status_code=status_code,
        request=httpx.Request("GET", "https://example.com"),
    )
    if json_body is not None:
        resp._content = _json.dumps(json_body).encode()
        resp.headers["content-type"] = "application/json"
    elif text:
        resp._content = text.encode()
    else:
        resp._content = b""
    return resp


@pytest.fixture()
def mock_credential_store() -> MagicMock:
    store = MagicMock()
    store.get_access_token.return_value = "test-access-token"
    store.get_team_slug.return_value = "team-acme"
    store.get_refresh_token.return_value = "test-refresh-token"
    return store


@pytest.fixture()
def mock_sync_config() -> MagicMock:
    config = MagicMock()
    config.get_server_url.return_value = "https://saas.example.com"
    return config


@pytest.fixture()
def client(mock_credential_store: MagicMock, mock_sync_config: MagicMock) -> SaaSTrackerClient:
    return SaaSTrackerClient(
        credential_store=mock_credential_store,
        sync_config=mock_sync_config,
        timeout=5.0,
    )


# Shared project identity dict used across bind tests.
PROJECT_IDENTITY: dict[str, Any] = {
    "uuid": "550e8400-e29b-41d4-a716-446655440000",
    "slug": "my-project",
    "node_id": "a1b2c3d4e5f6",
    "repo_slug": None,
    "build_id": "b0000000-0000-0000-0000-000000000001",
}


# ---------------------------------------------------------------------------
# T024: HTTP Tests for resources()
# ---------------------------------------------------------------------------


class TestResourcesContract:
    """Contract tests for GET /api/v1/tracker/resources/."""

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_resources_sends_get_with_provider_param(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        """Verify GET method, path, and provider query param."""
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(
            200,
            {"resources": [], "installation_id": "inst_01", "provider": "linear"},
        )

        client.resources("linear")

        args, kwargs = mock_http.request.call_args
        assert args[0] == "GET"
        assert args[1].endswith("/api/v1/tracker/resources/")
        assert kwargs["params"]["provider"] == "linear"

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_resources_parses_response(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        """Verify full contract response shape is parsed correctly."""
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(
            200,
            {
                "resources": [
                    {
                        "candidate_token": "cand_01HXYZ",
                        "display_label": "My Project (LINEAR-123)",
                        "provider": "linear",
                        "provider_context": {
                            "team_name": "Engineering",
                            "workspace_name": "Acme Corp",
                        },
                        "binding_ref": "srm_01HXYZ",
                        "bound_project_slug": "my-project",
                        "bound_at": "2026-03-01T10:00:00Z",
                    }
                ],
                "installation_id": "inst_01HXYZ",
                "provider": "linear",
            },
        )

        result = client.resources("linear")

        assert result["provider"] == "linear"
        assert result["installation_id"] == "inst_01HXYZ"
        assert len(result["resources"]) == 1
        resource = result["resources"][0]
        assert resource["candidate_token"] == "cand_01HXYZ"
        assert resource["display_label"] == "My Project (LINEAR-123)"
        assert resource["provider_context"]["team_name"] == "Engineering"
        assert resource["binding_ref"] == "srm_01HXYZ"
        assert resource["bound_project_slug"] == "my-project"
        assert resource["bound_at"] == "2026-03-01T10:00:00Z"

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_resources_empty_list(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        """Empty resources list is a valid response, not an error."""
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(
            200,
            {"resources": [], "installation_id": "inst_01", "provider": "linear"},
        )

        result = client.resources("linear")

        assert result["resources"] == []
        assert result["installation_id"] == "inst_01"

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_resources_403_no_installation(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        """403 with no_installation error code raises SaaSTrackerClientError."""
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(
            403,
            {
                "error_code": "no_installation",
                "message": "No installation found for this provider",
                "user_action_required": True,
            },
        )

        with pytest.raises(SaaSTrackerClientError, match="No installation found"):
            client.resources("linear")


# ---------------------------------------------------------------------------
# T025: HTTP Tests for bind_resolve()
# ---------------------------------------------------------------------------


class TestBindResolveContract:
    """Contract tests for POST /api/v1/tracker/bind-resolve/."""

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_bind_resolve_sends_post_with_body(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        """Verify POST method, path, and body shape with provider + project_identity."""
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(
            200,
            {
                "match_type": "none",
                "candidate_token": None,
                "binding_ref": None,
                "candidates": [],
                "display_label": None,
            },
        )

        client.bind_resolve("linear", PROJECT_IDENTITY)

        args, kwargs = mock_http.request.call_args
        assert args[0] == "POST"
        assert args[1].endswith("/api/v1/tracker/bind-resolve/")
        payload = kwargs["json"]
        assert payload["provider"] == "linear"
        assert payload["project_identity"] == PROJECT_IDENTITY

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_bind_resolve_exact_match(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        """Verify exact match response with candidate_token and binding_ref."""
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(
            200,
            {
                "match_type": "exact",
                "candidate_token": "cand_01HXYZ",
                "binding_ref": "srm_01HXYZ",
                "candidates": [],
                "display_label": "My Project (LINEAR-123)",
            },
        )

        result = client.bind_resolve("linear", PROJECT_IDENTITY)

        assert result["match_type"] == "exact"
        assert result["candidate_token"] == "cand_01HXYZ"
        assert result["binding_ref"] == "srm_01HXYZ"
        assert result["display_label"] == "My Project (LINEAR-123)"
        assert result["candidates"] == []

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_bind_resolve_exact_match_no_existing_mapping(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        """Exact match with null binding_ref means CLI must call bind-confirm."""
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(
            200,
            {
                "match_type": "exact",
                "candidate_token": "cand_01HXYZ",
                "binding_ref": None,
                "candidates": [],
                "display_label": "My Project (LINEAR-123)",
            },
        )

        result = client.bind_resolve("linear", PROJECT_IDENTITY)

        assert result["match_type"] == "exact"
        assert result["candidate_token"] == "cand_01HXYZ"
        assert result["binding_ref"] is None

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_bind_resolve_candidates(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        """Verify candidates array parsed with confidence and sort_position."""
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(
            200,
            {
                "match_type": "candidates",
                "candidate_token": None,
                "binding_ref": None,
                "candidates": [
                    {
                        "candidate_token": "cand_01HABC",
                        "display_label": "My Project (LINEAR-123)",
                        "confidence": "high",
                        "match_reason": "project_slug matches existing mapping",
                        "sort_position": 0,
                    },
                    {
                        "candidate_token": "cand_01HDEF",
                        "display_label": "Backend API (LINEAR-456)",
                        "confidence": "medium",
                        "match_reason": "repo_slug partial match",
                        "sort_position": 1,
                    },
                ],
                "display_label": None,
            },
        )

        result = client.bind_resolve("linear", PROJECT_IDENTITY)

        assert result["match_type"] == "candidates"
        assert result["candidate_token"] is None
        assert result["binding_ref"] is None
        assert result["display_label"] is None
        assert len(result["candidates"]) == 2

        first = result["candidates"][0]
        assert first["candidate_token"] == "cand_01HABC"
        assert first["confidence"] == "high"
        assert first["sort_position"] == 0

        second = result["candidates"][1]
        assert second["candidate_token"] == "cand_01HDEF"
        assert second["confidence"] == "medium"
        assert second["sort_position"] == 1

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_bind_resolve_none(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        """Verify none match type: all optional fields are null."""
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(
            200,
            {
                "match_type": "none",
                "candidate_token": None,
                "binding_ref": None,
                "candidates": [],
                "display_label": None,
            },
        )

        result = client.bind_resolve("linear", PROJECT_IDENTITY)

        assert result["match_type"] == "none"
        assert result["candidate_token"] is None
        assert result["binding_ref"] is None
        assert result["candidates"] == []
        assert result["display_label"] is None


# ---------------------------------------------------------------------------
# T026: HTTP Tests for bind_confirm()
# ---------------------------------------------------------------------------


class TestBindConfirmContract:
    """Contract tests for POST /api/v1/tracker/bind-confirm/."""

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_bind_confirm_sends_post_with_body(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        """Verify POST method, path, and body has provider, candidate_token, project_identity."""
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(
            200,
            {
                "binding_ref": "srm_01HXYZ",
                "display_label": "My Project (LINEAR-123)",
                "provider": "linear",
                "provider_context": {
                    "team_name": "Engineering",
                    "workspace_name": "Acme Corp",
                },
                "bound_at": "2026-04-04T08:32:00Z",
            },
        )

        client.bind_confirm("linear", "cand_01HXYZ", PROJECT_IDENTITY)

        args, kwargs = mock_http.request.call_args
        assert args[0] == "POST"
        assert args[1].endswith("/api/v1/tracker/bind-confirm/")
        payload = kwargs["json"]
        assert payload["provider"] == "linear"
        assert payload["candidate_token"] == "cand_01HXYZ"
        assert payload["project_identity"] == PROJECT_IDENTITY

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_bind_confirm_response_shape(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        """Verify full 200 response parsed with all contract fields."""
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(
            200,
            {
                "binding_ref": "srm_01HXYZ",
                "display_label": "My Project (LINEAR-123)",
                "provider": "linear",
                "provider_context": {
                    "team_name": "Engineering",
                    "workspace_name": "Acme Corp",
                },
                "bound_at": "2026-04-04T08:32:00Z",
            },
        )

        result = client.bind_confirm("linear", "cand_01HXYZ", PROJECT_IDENTITY)

        assert result["binding_ref"] == "srm_01HXYZ"
        assert result["display_label"] == "My Project (LINEAR-123)"
        assert result["provider"] == "linear"
        assert result["provider_context"]["team_name"] == "Engineering"
        assert result["provider_context"]["workspace_name"] == "Acme Corp"
        assert result["bound_at"] == "2026-04-04T08:32:00Z"

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_bind_confirm_sends_idempotency_key(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        """Verify Idempotency-Key header is sent (not X-Idempotency-Key)."""
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(200, {"binding_ref": "srm_01HXYZ"})

        client.bind_confirm(
            "linear",
            "cand_01HXYZ",
            PROJECT_IDENTITY,
            idempotency_key="explicit-key-123",
        )

        _, kwargs = mock_http.request.call_args
        assert "Idempotency-Key" in kwargs["headers"]
        assert kwargs["headers"]["Idempotency-Key"] == "explicit-key-123"

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_bind_confirm_auto_generates_key(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        """When omitted, the key is the durable logical-operation identity."""
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(200, {"binding_ref": "srm_01HXYZ"})

        client.bind_confirm("linear", "cand_01HXYZ", PROJECT_IDENTITY)

        _, kwargs = mock_http.request.call_args
        idem_key = kwargs["headers"]["Idempotency-Key"]
        assert idem_key.startswith("logical-operation:write:")
        # Length of a sha256 hexdigest suffix IS the contract (fixed hash format).
        assert len(idem_key.removeprefix("logical-operation:write:")) == 64

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_bind_confirm_400_invalid_token(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        """400 invalid_candidate_token raises SaaSTrackerClientError."""
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(
            400,
            {
                "error_code": "invalid_candidate_token",
                "message": "Token expired, invalid, or already consumed",
                "user_action_required": False,
            },
        )

        with pytest.raises(SaaSTrackerClientError, match="Token expired"):
            client.bind_confirm("linear", "cand_expired", PROJECT_IDENTITY)

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_bind_confirm_409_already_bound(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        """409 already_bound raises SaaSTrackerClientError."""
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(
            409,
            {
                "error_code": "already_bound",
                "message": "Resource already bound to a different project",
                "user_action_required": True,
            },
        )

        with pytest.raises(SaaSTrackerClientError, match="already bound to a different project"):
            client.bind_confirm("linear", "cand_01HXYZ", PROJECT_IDENTITY)


# ---------------------------------------------------------------------------
# T027: HTTP Tests for bind_validate()
# ---------------------------------------------------------------------------


class TestBindValidateContract:
    """Contract tests for POST /api/v1/tracker/bind-validate/."""

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_bind_validate_sends_post_with_body(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        """Verify POST method, path, and body has provider, binding_ref, project_identity."""
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(
            200,
            {"valid": True, "binding_ref": "srm_01HXYZ"},
        )

        client.bind_validate("linear", "srm_01HXYZ", PROJECT_IDENTITY)

        args, kwargs = mock_http.request.call_args
        assert args[0] == "POST"
        assert args[1].endswith("/api/v1/tracker/bind-validate/")
        payload = kwargs["json"]
        assert payload["provider"] == "linear"
        assert payload["binding_ref"] == "srm_01HXYZ"
        assert payload["project_identity"] == PROJECT_IDENTITY

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_bind_validate_valid_response(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        """Verify valid=true response parsed with display metadata."""
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(
            200,
            {
                "valid": True,
                "binding_ref": "srm_01HXYZ",
                "display_label": "My Project (LINEAR-123)",
                "provider": "linear",
                "provider_context": {
                    "team_name": "Engineering",
                    "workspace_name": "Acme Corp",
                },
            },
        )

        result = client.bind_validate("linear", "srm_01HXYZ", PROJECT_IDENTITY)

        assert result["valid"] is True
        assert result["binding_ref"] == "srm_01HXYZ"
        assert result["display_label"] == "My Project (LINEAR-123)"
        assert result["provider"] == "linear"
        assert result["provider_context"]["team_name"] == "Engineering"

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_bind_validate_invalid_response(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        """Verify valid=false response parsed with reason and guidance."""
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(
            200,
            {
                "valid": False,
                "binding_ref": "srm_01HXYZ",
                "reason": "mapping_deleted",
                "guidance": ("The bound tracker resource no longer exists. Run `tracker bind --provider linear` to rebind."),
            },
        )

        result = client.bind_validate("linear", "srm_01HXYZ", PROJECT_IDENTITY)

        assert result["valid"] is False
        assert result["binding_ref"] == "srm_01HXYZ"
        assert result["reason"] == "mapping_deleted"
        assert "no longer exists" in result["guidance"]

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_bind_validate_both_return_200(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        """Both valid and invalid responses return 200 (not 4xx)."""
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        # valid=true case: no exception
        mock_http.request.return_value = _make_response(200, {"valid": True, "binding_ref": "srm_01"})
        result_valid = client.bind_validate("linear", "srm_01", PROJECT_IDENTITY)
        assert result_valid["valid"] is True

        # valid=false case: also no exception (200, not 4xx)
        mock_http.request.return_value = _make_response(
            200,
            {
                "valid": False,
                "binding_ref": "srm_01",
                "reason": "mapping_disabled",
                "guidance": "Mapping has been disabled.",
            },
        )
        result_invalid = client.bind_validate("linear", "srm_01", PROJECT_IDENTITY)
        assert result_invalid["valid"] is False


# ---------------------------------------------------------------------------
# T028: Existing endpoints with binding_ref routing variant
# ---------------------------------------------------------------------------


class TestExistingEndpointsBindingRef:
    """Verify existing endpoints accept binding_ref routing.

    Detailed routing tests live in test_saas_client_routing.py; these
    contract tests verify the HTTP-level wire format for a representative
    GET (status) and POST (push) endpoint.
    """

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_status_with_binding_ref(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        """GET status with binding_ref sends it as query param."""
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(200, {"connected": True, "provider": "linear"})

        result = client.status("linear", binding_ref="srm_01HXYZ")

        assert result["connected"] is True
        _, kwargs = mock_http.request.call_args
        assert kwargs["params"]["binding_ref"] == "srm_01HXYZ"
        assert kwargs["params"]["provider"] == "linear"
        assert "project_slug" not in kwargs["params"]

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_status_with_project_slug(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        """GET status with project_slug sends it as query param (legacy path)."""
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(200, {"connected": True, "provider": "linear"})

        result = client.status("linear", "my-project")

        assert result["connected"] is True
        _, kwargs = mock_http.request.call_args
        assert kwargs["params"]["project_slug"] == "my-project"
        assert "binding_ref" not in kwargs["params"]

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_status_binding_ref_takes_precedence(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        """When both provided, only binding_ref is sent, project_slug excluded."""
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(200, {"connected": True})

        client.status("linear", "my-project", binding_ref="srm_01HXYZ")

        _, kwargs = mock_http.request.call_args
        assert kwargs["params"]["binding_ref"] == "srm_01HXYZ"
        assert "project_slug" not in kwargs["params"]

    def test_status_missing_both_raises(self, client: SaaSTrackerClient) -> None:
        """When neither project_slug nor binding_ref provided, error raised."""
        with pytest.raises(SaaSTrackerClientError) as exc_info:
            client.status("linear")
        assert exc_info.value.error_code == "missing_routing_key"

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_push_with_binding_ref_in_body(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        """POST push with binding_ref includes it in the JSON body (not query)."""
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(200, {"pushed": 0, "errors": []})

        client.push("linear", binding_ref="srm_01HXYZ", items=[])

        args, kwargs = mock_http.request.call_args
        assert args[0] == "POST"
        assert args[1].endswith("/api/v1/tracker/push/")
        assert kwargs["json"]["binding_ref"] == "srm_01HXYZ"
        assert kwargs["json"]["provider"] == "linear"
        assert "project_slug" not in kwargs["json"]

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_run_with_binding_ref_in_body(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        """POST run with binding_ref includes it in the JSON body."""
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(200, {"pulled": 5, "pushed": 3})

        result = client.run("linear", binding_ref="srm_01HXYZ")

        assert result == {"pulled": 5, "pushed": 3}
        _, kwargs = mock_http.request.call_args
        assert kwargs["json"]["binding_ref"] == "srm_01HXYZ"
        assert "project_slug" not in kwargs["json"]

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_mappings_with_binding_ref(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        """GET mappings with binding_ref sends it as query param."""
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(200, {"fields": [{"src": "title", "dst": "summary"}]})

        result = client.mappings("linear", binding_ref="srm_01HXYZ")

        assert result["fields"][0]["src"] == "title"
        _, kwargs = mock_http.request.call_args
        assert kwargs["params"]["binding_ref"] == "srm_01HXYZ"
        assert "project_slug" not in kwargs["params"]

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_pull_with_binding_ref_in_body(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        """POST pull with binding_ref includes it in the JSON body."""
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(200, {"items": [{"id": "1"}], "cursor": "abc"})

        result = client.pull("linear", binding_ref="srm_01HXYZ")

        assert result["items"][0]["id"] == "1"
        _, kwargs = mock_http.request.call_args
        assert kwargs["json"]["binding_ref"] == "srm_01HXYZ"
        assert "project_slug" not in kwargs["json"]


# ---------------------------------------------------------------------------
# T029: Stale-binding error codes preserved in SaaSTrackerClientError
# ---------------------------------------------------------------------------


class TestStaleBindingErrorCodes:
    """Verify enriched error attributes are preserved for stale-binding codes."""

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_binding_not_found_error_code(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        """404 with error_code=binding_not_found preserved on SaaSTrackerClientError."""
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(
            404,
            {
                "error_code": "binding_not_found",
                "message": "The binding reference srm_01HXYZ is no longer valid.",
                "user_action_required": True,
            },
        )

        with pytest.raises(SaaSTrackerClientError) as exc_info:
            client.status("linear", binding_ref="srm_01HXYZ")

        assert exc_info.value.error_code == "binding_not_found"
        assert exc_info.value.status_code == 404
        assert "no longer valid" in str(exc_info.value)

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_mapping_disabled_error_code(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        """403 with error_code=mapping_disabled preserved on SaaSTrackerClientError."""
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(
            403,
            {
                "error_code": "mapping_disabled",
                "message": "Mapping exists but is disabled.",
                "user_action_required": True,
            },
        )

        with pytest.raises(SaaSTrackerClientError) as exc_info:
            client.status("linear", binding_ref="srm_disabled")

        assert exc_info.value.error_code == "mapping_disabled"
        assert exc_info.value.status_code == 403

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_project_mismatch_error_code(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        """403 with error_code=project_mismatch preserved on SaaSTrackerClientError."""
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(
            403,
            {
                "error_code": "project_mismatch",
                "message": "binding_ref doesn't match the authenticated project context.",
                "user_action_required": True,
            },
        )

        with pytest.raises(SaaSTrackerClientError) as exc_info:
            client.mappings("linear", binding_ref="srm_mismatch")

        assert exc_info.value.error_code == "project_mismatch"
        assert exc_info.value.status_code == 403

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_error_code_none_when_missing(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        """500 with no error_code field results in e.error_code is None."""
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(
            500,
            {"message": "Internal server error"},
        )

        with pytest.raises(SaaSTrackerClientError) as exc_info:
            client.status("linear", binding_ref="srm_01")

        assert exc_info.value.error_code is None
        assert exc_info.value.status_code == 500
