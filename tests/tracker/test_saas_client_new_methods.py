"""Smoke tests for the four new discovery/binding client methods.

Covers: resources(), bind_resolve(), bind_confirm(), bind_validate().
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from specify_cli.tracker.saas_client import SaaSTrackerClient

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
        import json as _json

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


def _valid_identity() -> dict[str, Any]:
    """Return a valid project_identity dict that passes contract gate."""
    return {
        "uuid": str(uuid.uuid4()),
        "slug": "my-project",
        "node_id": "a1b2c3d4e5f6",
        "repo_slug": "acme/widgets",
        "build_id": str(uuid.uuid4()),
    }


# ---------------------------------------------------------------------------
# resources()
# ---------------------------------------------------------------------------


class TestResources:
    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_resources_sends_get_with_provider(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(200, {"resources": [{"id": "proj-1", "name": "Project One"}]})

        result = client.resources("jira")

        assert result == {"resources": [{"id": "proj-1", "name": "Project One"}]}
        args, kwargs = mock_http.request.call_args
        assert args[0] == "GET"
        assert "/api/v1/tracker/resources/" in args[1]
        assert kwargs["params"]["provider"] == "jira"

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_resources_parses_empty_list(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(200, {"resources": []})

        result = client.resources("github")

        assert result == {"resources": []}


# ---------------------------------------------------------------------------
# bind_resolve()
# ---------------------------------------------------------------------------


class TestBindResolve:
    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_bind_resolve_sends_post_with_provider_and_identity(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(
            200,
            {
                "candidates": [{"candidate_token": "tok-abc", "display_name": "My Project"}],
            },
        )

        identity = _valid_identity()
        result = client.bind_resolve("github", identity)

        assert len(result["candidates"]) == 1
        assert result["candidates"][0]["candidate_token"] == "tok-abc"

        args, kwargs = mock_http.request.call_args
        assert args[0] == "POST"
        assert "/api/v1/tracker/bind-resolve/" in args[1]
        assert kwargs["json"]["provider"] == "github"
        assert kwargs["json"]["project_identity"] == identity

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_bind_resolve_empty_candidates(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(200, {"candidates": []})

        result = client.bind_resolve("jira", _valid_identity())

        assert result == {"candidates": []}


# ---------------------------------------------------------------------------
# bind_confirm()
# ---------------------------------------------------------------------------


class TestBindConfirm:
    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_bind_confirm_sends_post_with_payload(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(200, {"binding_ref": "bind-123", "status": "confirmed"})

        identity = _valid_identity()
        result = client.bind_confirm("github", "tok-abc", identity)

        assert result["binding_ref"] == "bind-123"
        assert result["status"] == "confirmed"

        args, kwargs = mock_http.request.call_args
        assert args[0] == "POST"
        assert "/api/v1/tracker/bind-confirm/" in args[1]
        assert kwargs["json"]["provider"] == "github"
        assert kwargs["json"]["candidate_token"] == "tok-abc"
        assert kwargs["json"]["project_identity"] == identity

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_bind_confirm_auto_generates_idempotency_key(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(200, {"binding_ref": "bind-123"})

        client.bind_confirm("github", "tok-abc", _valid_identity())

        _, kwargs = mock_http.request.call_args
        idem_key = kwargs["headers"]["Idempotency-Key"]
        # The key is durable across process recovery, unlike a local UUID.
        assert idem_key.startswith("logical-operation:write:")
        # Length of a sha256 hexdigest suffix IS the contract (fixed hash format).
        assert len(idem_key.removeprefix("logical-operation:write:")) == 64

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_bind_confirm_custom_idempotency_key(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(200, {"binding_ref": "bind-123"})

        client.bind_confirm("github", "tok-abc", _valid_identity(), idempotency_key="custom-key-456")

        _, kwargs = mock_http.request.call_args
        assert kwargs["headers"]["Idempotency-Key"] == "custom-key-456"


# ---------------------------------------------------------------------------
# bind_validate()
# ---------------------------------------------------------------------------


class TestBindValidate:
    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_bind_validate_sends_post_with_payload(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(200, {"valid": True, "binding_ref": "bind-123"})

        identity = _valid_identity()
        result = client.bind_validate("github", "bind-123", identity)

        assert result["valid"] is True
        assert result["binding_ref"] == "bind-123"

        args, kwargs = mock_http.request.call_args
        assert args[0] == "POST"
        assert "/api/v1/tracker/bind-validate/" in args[1]
        assert kwargs["json"]["provider"] == "github"
        assert kwargs["json"]["binding_ref"] == "bind-123"
        assert kwargs["json"]["project_identity"] == identity

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_bind_validate_invalid_response(self, mock_cls: MagicMock, client: SaaSTrackerClient) -> None:
        mock_http = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_http.request.return_value = _make_response(
            200,
            {"valid": False, "binding_ref": "bind-bad", "reason": "binding expired"},
        )

        result = client.bind_validate("jira", "bind-bad", _valid_identity())

        assert result["valid"] is False
        assert result["reason"] == "binding expired"
