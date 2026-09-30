"""Integration tests for ticket-first mission origin binding (WP06).

Unlike the unit tests in ``test_origin.py`` which mock the entire
``SaaSTrackerClient``, these tests mock ONLY at the ``httpx.Client``
boundary.  Real config loading, real metadata writes, real event
emission, and the real ``SaaSTrackerClient`` transport are exercised.

Covers:
- T031: End-to-end confirm -> bind flow (the search step and T032's
  ``start_mission_from_ticket`` were deleted as never-wired; dead-code review
  2026-09-30)
- T033: Error propagation across layers
- T034: SaaS-first write ordering invariant (MOST CRITICAL)
- T035: Offline event queuing
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from specify_cli.tracker.origin import (
    OriginBindingError,
    bind_mission_origin,
)
from specify_cli.tracker.origin_models import OriginCandidate
from specify_cli.tracker.saas_client import SaaSTrackerClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.unit, pytest.mark.fast]


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
        resp._content = json.dumps(json_body).encode()
        resp.headers["content-type"] = "application/json"
    elif text:
        resp._content = text.encode()
    else:
        resp._content = b""
    return resp


def _make_candidate(
    *,
    key: str = "WEB-123",
    issue_id: str = "issue-uuid-1",
    title: str = "Add Clerk auth",
    body: str = (
        "Make authentication consistent across the product so teams can launch a reliable sign-in flow "
        "without patchwork fixes.\n\n"
        "This ticket creates a single, trustworthy auth path so product and engineering can ship account "
        "access confidently and reduce avoidable support friction."
    ),
    status: str = "In Progress",
    url: str = "https://linear.app/acme/issue/WEB-123/add-clerk-auth",
    match_type: str = "text",
) -> OriginCandidate:
    return OriginCandidate(
        external_issue_id=issue_id,
        external_issue_key=key,
        title=title,
        body=body,
        status=status,
        url=url,
        match_type=match_type,
    )


def _setup_mock_http(mock_http_cls: MagicMock) -> MagicMock:
    """Wire up the context-manager protocol on the mock httpx.Client class."""
    mock_http = MagicMock()
    mock_http_cls.return_value.__enter__ = MagicMock(return_value=mock_http)
    mock_http_cls.return_value.__exit__ = MagicMock(return_value=False)
    return mock_http


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def repo_with_tracker(tmp_path: Path) -> Path:
    """Create a repo with tracker binding configured."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    config_yaml = kittify / "config.yaml"
    config_yaml.write_text(
        "tracker:\n  provider: linear\n  project_slug: acme-web\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture()
def feature_dir_with_meta(repo_with_tracker: Path) -> Path:
    """Create a feature dir with valid meta.json."""
    feature_dir = repo_with_tracker / "kitty-specs" / "061-test-feature"
    feature_dir.mkdir(parents=True)
    meta: dict[str, Any] = {
        "mission_number": "061",
        "slug": "test-feature",
        "mission_slug": "061-test-feature",
        "mission_id": "01KTESTMISSIONID00000000002",
        "friendly_name": "Test Feature",
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-04-01T00:00:00+00:00",
    }
    (feature_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return feature_dir


@pytest.fixture()
def mock_client() -> SaaSTrackerClient:
    """SaaSTrackerClient with mocked credential store and config."""
    store = MagicMock()
    store.get_access_token.return_value = "test-token"
    store.get_team_slug.return_value = "team-acme"
    config = MagicMock()
    config.get_server_url.return_value = "https://saas.example.com"
    return SaaSTrackerClient(
        credential_store=store,
        sync_config=config,
        timeout=5.0,
    )


# ===========================================================================
# T031: End-to-end confirm -> bind flow
# ===========================================================================


class TestSearchConfirmBindFlow:
    """Integration test wiring real service functions with httpx mock only."""

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_confirm_bind_full_flow(
        self,
        mock_http_cls: MagicMock,
        repo_with_tracker: Path,
        feature_dir_with_meta: Path,
        mock_client: SaaSTrackerClient,
    ) -> None:
        """Full happy path: confirmed candidate -> bind -> verify meta."""
        mock_http = _setup_mock_http(mock_http_cls)

        # Step 1: the confirmed candidate (ticket fetch happens in
        # ``mission create --from-ticket``, not in this service).
        candidate = OriginCandidate(
            external_issue_id="id-1",
            external_issue_key="WEB-123",
            title="Add Clerk auth",
            status="In Progress",
            url="https://linear.app/acme/WEB-123",
            match_type="text",
        )

        # Bind returns success
        mock_http.request.side_effect = [
            _make_response(
                200,
                {"origin_link_id": "link-1", "bound_at": "2026-04-01T00:00:00Z"},
            )
        ]

        # Step 2: Bind
        meta, emitted = bind_mission_origin(
            feature_dir_with_meta,
            candidate,
            "linear",
            "linear_team",
            "team-uuid",
            client=mock_client,
        )

        # Step 3: Verify meta.json was written with all 7 required keys.
        # MissionOriginBound SaaS emission was removed with the sync transport (#5).
        assert emitted is False
        assert "origin_ticket" in meta
        ot = meta["origin_ticket"]
        assert ot["provider"] == "linear"
        assert ot["resource_type"] == "linear_team"
        assert ot["resource_id"] == "team-uuid"
        assert ot["external_issue_id"] == "id-1"
        assert ot["external_issue_key"] == "WEB-123"
        assert ot["external_issue_url"] == "https://linear.app/acme/WEB-123"
        assert ot["title"] == "Add Clerk auth"

        # Step 4: Verify meta.json on disk matches
        disk_meta = json.loads(
            (feature_dir_with_meta / "meta.json").read_text(encoding="utf-8"),
        )
        assert disk_meta["origin_ticket"] == ot


# ===========================================================================
# T033: Error propagation across layers
# ===========================================================================


class TestErrorPropagation:
    """Verify errors from httpx propagate as OriginBindingError with
    user-actionable messages (not raw HTTP details)."""

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_409_bind_propagates_as_origin_error(
        self,
        mock_http_cls: MagicMock,
        feature_dir_with_meta: Path,
        mock_client: SaaSTrackerClient,
    ) -> None:
        """HTTP 409 -> SaaSTrackerClientError -> OriginBindingError with conflict message."""
        mock_http = _setup_mock_http(mock_http_cls)
        mock_http.request.return_value = _make_response(
            409,
            {
                "message": "Feature already bound to a different issue",
                "code": "origin_conflict",
            },
        )

        candidate = _make_candidate()

        with pytest.raises(
            OriginBindingError,
            match="already bound to a different issue",
        ):
            bind_mission_origin(
                feature_dir_with_meta,
                candidate,
                "linear",
                "linear_team",
                "team-uuid",
                client=mock_client,
            )


# ===========================================================================
# T034: SaaS-first write ordering invariant (MOST CRITICAL)
# ===========================================================================


class TestSaaSFirstWriteOrdering:
    """The most critical integration test: verify that local metadata
    is NEVER written when the SaaS bind call fails."""

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_500_does_not_write_local_meta(
        self,
        mock_http_cls: MagicMock,
        feature_dir_with_meta: Path,
        mock_client: SaaSTrackerClient,
    ) -> None:
        """HTTP 500 from SaaS -> meta.json must NOT have origin_ticket."""
        mock_http = _setup_mock_http(mock_http_cls)
        mock_http.request.return_value = _make_response(
            500,
            {"message": "Internal server error"},
        )

        candidate = _make_candidate()

        with pytest.raises(OriginBindingError):
            bind_mission_origin(
                feature_dir_with_meta,
                candidate,
                "linear",
                "linear_team",
                "team-uuid",
                client=mock_client,
            )

        # THE INVARIANT: meta.json must NOT have origin_ticket
        meta = json.loads(
            (feature_dir_with_meta / "meta.json").read_text(encoding="utf-8"),
        )
        assert "origin_ticket" not in meta

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_409_does_not_write_local_meta(
        self,
        mock_http_cls: MagicMock,
        feature_dir_with_meta: Path,
        mock_client: SaaSTrackerClient,
    ) -> None:
        """HTTP 409 conflict -> meta.json must NOT have origin_ticket."""
        mock_http = _setup_mock_http(mock_http_cls)
        mock_http.request.return_value = _make_response(
            409,
            {"message": "Feature already bound to a different issue"},
        )

        candidate = _make_candidate()

        with pytest.raises(OriginBindingError):
            bind_mission_origin(
                feature_dir_with_meta,
                candidate,
                "linear",
                "linear_team",
                "team-uuid",
                client=mock_client,
            )

        meta = json.loads(
            (feature_dir_with_meta / "meta.json").read_text(encoding="utf-8"),
        )
        assert "origin_ticket" not in meta

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_401_does_not_write_local_meta(
        self,
        mock_http_cls: MagicMock,
        feature_dir_with_meta: Path,
        mock_client: SaaSTrackerClient,
    ) -> None:
        """HTTP 401 expired session -> meta.json must NOT have origin_ticket."""
        mock_http = _setup_mock_http(mock_http_cls)
        # Both attempts return 401 (initial + after refresh)
        mock_http.request.side_effect = [
            _make_response(401, {"message": "Unauthorized"}),
            _make_response(401, {"message": "Unauthorized"}),
        ]

        candidate = _make_candidate()

        with (
            patch("specify_cli.tracker.saas_client._force_refresh_sync"),
            pytest.raises(OriginBindingError),
        ):
            bind_mission_origin(
                feature_dir_with_meta,
                candidate,
                "linear",
                "linear_team",
                "team-uuid",
                client=mock_client,
            )

        meta = json.loads(
            (feature_dir_with_meta / "meta.json").read_text(encoding="utf-8"),
        )
        assert "origin_ticket" not in meta

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_403_does_not_write_local_meta(
        self,
        mock_http_cls: MagicMock,
        feature_dir_with_meta: Path,
        mock_client: SaaSTrackerClient,
    ) -> None:
        """HTTP 403 forbidden -> meta.json must NOT have origin_ticket."""
        mock_http = _setup_mock_http(mock_http_cls)
        mock_http.request.return_value = _make_response(
            403,
            {"message": "Forbidden: insufficient permissions"},
        )

        candidate = _make_candidate()

        with pytest.raises(OriginBindingError):
            bind_mission_origin(
                feature_dir_with_meta,
                candidate,
                "linear",
                "linear_team",
                "team-uuid",
                client=mock_client,
            )

        meta = json.loads(
            (feature_dir_with_meta / "meta.json").read_text(encoding="utf-8"),
        )
        assert "origin_ticket" not in meta

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_422_does_not_write_local_meta(
        self,
        mock_http_cls: MagicMock,
        feature_dir_with_meta: Path,
        mock_client: SaaSTrackerClient,
    ) -> None:
        """HTTP 422 validation error -> meta.json must NOT have origin_ticket."""
        mock_http = _setup_mock_http(mock_http_cls)
        mock_http.request.return_value = _make_response(
            422,
            {"message": "Invalid payload", "code": "validation_error"},
        )

        candidate = _make_candidate()

        with pytest.raises(OriginBindingError):
            bind_mission_origin(
                feature_dir_with_meta,
                candidate,
                "linear",
                "linear_team",
                "team-uuid",
                client=mock_client,
            )

        meta = json.loads(
            (feature_dir_with_meta / "meta.json").read_text(encoding="utf-8"),
        )
        assert "origin_ticket" not in meta

    @patch("specify_cli.tracker.saas_client.httpx.Client")
    def test_meta_unchanged_byte_for_byte(
        self,
        mock_http_cls: MagicMock,
        feature_dir_with_meta: Path,
        mock_client: SaaSTrackerClient,
    ) -> None:
        """On SaaS failure, meta.json content is byte-for-byte identical."""
        meta_path = feature_dir_with_meta / "meta.json"
        original_bytes = meta_path.read_bytes()

        mock_http = _setup_mock_http(mock_http_cls)
        mock_http.request.return_value = _make_response(
            500,
            {"message": "Internal server error"},
        )

        candidate = _make_candidate()

        with pytest.raises(OriginBindingError):
            bind_mission_origin(
                feature_dir_with_meta,
                candidate,
                "linear",
                "linear_team",
                "team-uuid",
                client=mock_client,
            )

        assert meta_path.read_bytes() == original_bytes


# NOTE: TestOfflineEventQueuing (T035) was deliberately not re-homed here. It
# pinned MissionOriginBound reaching the sync transport's offline queue via
# EventEmitter/OfflineQueue/ProjectSyncStore -- all deleted with the sync
# transport (#5). ``bind_mission_origin`` no longer emits any event (it always
# returns ``emitted=False``, see ``origin.py``), so there is nothing left for
# this test to pin; the queuing behaviour it covered no longer exists.
