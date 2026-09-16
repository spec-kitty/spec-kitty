"""Tests for the origin binding service layer (WP05).

Covers:
- search_origin_candidates(): 7 scenarios
- bind_mission_origin(): SaaS-first ordering, happy path, error cases
- start_mission_from_ticket(): full flow, creation failure, slug derivation
- _derive_slug_from_ticket(): slug sanitization
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from specify_cli.tracker.origin import (
    OriginBindingError,
    _derive_slug_from_ticket,
    _resolve_repo_root,
    bind_mission_origin,
    search_origin_candidates,
    start_mission_from_ticket,
)
from specify_cli.tracker.origin_models import (
    MissionFromTicketResult,
    OriginCandidate,
    SearchOriginResult,
)
from specify_cli.tracker.saas_client import SaaSTrackerClientError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.unit, pytest.mark.fast]


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


def _setup_repo(
    tmp_path: Path,
    *,
    provider: str = "linear",
    project_slug: str = "acme-web",
    binding_ref: str | None = None,
    provider_context: dict[str, str] | None = None,
) -> Path:
    """Create a minimal .kittify/config.yaml with tracker config."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    config_yaml = kittify / "config.yaml"
    lines = ["tracker:", f"  provider: {provider}"]
    if project_slug:
        lines.append(f"  project_slug: {project_slug}")
    if binding_ref:
        lines.append(f"  binding_ref: {binding_ref}")
    if provider_context:
        lines.append("  provider_context:")
        for key, value in provider_context.items():
            lines.append(f"    {key}: {value}")
    config_yaml.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return tmp_path


def _setup_feature(
    tmp_path: Path,
    *,
    mission_slug: str = "061-add-clerk-auth",
    provider: str = "linear",
    project_slug: str = "acme-web",
) -> Path:
    """Create a repo with a feature directory containing meta.json."""
    repo_root = _setup_repo(tmp_path, provider=provider, project_slug=project_slug)
    feature_dir = repo_root / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "mission_number": "061",
        "slug": mission_slug,
        "mission_slug": mission_slug,
        "mission_id": "01KTESTMISSIONID00000000001",
        "friendly_name": "add clerk auth",
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-04-01T00:00:00+00:00",
    }
    (feature_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return feature_dir


def _make_search_response(
    candidates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a canned search_issues response."""
    if candidates is None:
        candidates = [
            {
                "external_issue_id": "issue-uuid-1",
                "external_issue_key": "WEB-123",
                "title": "Add Clerk auth",
                "status": "In Progress",
                "url": "https://linear.app/acme/issue/WEB-123/add-clerk-auth",
                "match_type": "text",
            },
            {
                "external_issue_id": "issue-uuid-2",
                "external_issue_key": "WEB-127",
                "title": "Clerk middleware cleanup",
                "status": "Todo",
                "url": "https://linear.app/acme/issue/WEB-127/clerk-middleware-cleanup",
                "match_type": "text",
            },
        ]
    return {
        "candidates": candidates,
        "resource_type": "linear_team",
        "resource_id": "team-uuid-123",
    }


# ===========================================================================
# Tests: _derive_slug_from_ticket
# ===========================================================================


class TestDeriveSlugFromTicket:
    def test_simple_key(self) -> None:
        candidate = _make_candidate(key="WEB-123")
        assert _derive_slug_from_ticket(candidate) == "web-123"

    def test_iam_key(self) -> None:
        candidate = _make_candidate(key="IAM-42")
        assert _derive_slug_from_ticket(candidate) == "iam-42"

    def test_special_chars_cleaned(self) -> None:
        candidate = _make_candidate(key="PROJ_KEY/123")
        assert _derive_slug_from_ticket(candidate) == "proj-key-123"

    def test_empty_key_falls_back_to_title(self) -> None:
        candidate = _make_candidate(key="///", title="Fix the login page bug")
        slug = _derive_slug_from_ticket(candidate)
        assert slug == "fix-the-login-page-bug"

    def test_title_truncated_to_five_words(self) -> None:
        candidate = _make_candidate(key="", title="one two three four five six seven")
        slug = _derive_slug_from_ticket(candidate)
        assert slug == "one-two-three-four-five"

    def test_both_empty_returns_untitled(self) -> None:
        candidate = _make_candidate(key="", title="")
        slug = _derive_slug_from_ticket(candidate)
        assert slug == "untitled"


# ===========================================================================
# Tests: search_origin_candidates
# ===========================================================================


class TestSearchOriginCandidates:
    def test_free_text_returns_candidates(self, tmp_path: Path) -> None:
        """Scenario 1: Free-text search returns multiple candidates."""
        repo_root = _setup_repo(tmp_path)
        client = MagicMock()
        client.search_issues.return_value = _make_search_response()

        result = search_origin_candidates(
            repo_root,
            query_text="Clerk auth",
            client=client,
        )

        assert isinstance(result, SearchOriginResult)
        assert len(result.candidates) == 2
        assert result.candidates[0].external_issue_key == "WEB-123"
        assert result.candidates[1].external_issue_key == "WEB-127"
        assert result.provider == "linear"
        assert result.resource_type == "linear_team"
        assert result.resource_id == "team-uuid-123"
        assert result.query_used == "Clerk auth"

        client.search_issues.assert_called_once_with(
            "linear",
            "acme-web",
            query_text="Clerk auth",
            query_key=None,
            limit=10,
        )

    def test_key_search_returns_exact_match(self, tmp_path: Path) -> None:
        """Scenario 2: Key search returns single candidate with match_type=exact."""
        repo_root = _setup_repo(tmp_path)
        client = MagicMock()
        client.search_issues.return_value = _make_search_response(
            candidates=[
                {
                    "external_issue_id": "issue-uuid-1",
                    "external_issue_key": "IAM-42",
                    "title": "Fix IAM policy",
                    "status": "Open",
                    "url": "https://linear.app/acme/issue/IAM-42",
                    "match_type": "exact",
                },
            ],
        )

        result = search_origin_candidates(
            repo_root,
            query_key="IAM-42",
            client=client,
        )

        assert len(result.candidates) == 1
        assert result.candidates[0].match_type == "exact"
        assert result.query_used == "IAM-42"

    def test_empty_results(self, tmp_path: Path) -> None:
        """Scenario 3: Search returns empty candidates list."""
        repo_root = _setup_repo(tmp_path)
        client = MagicMock()
        client.search_issues.return_value = _make_search_response(candidates=[])

        result = search_origin_candidates(
            repo_root,
            query_text="nonexistent",
            client=client,
        )

        assert result.candidates == []

    def test_missing_user_link_raises(self, tmp_path: Path) -> None:
        """Scenario 4: SaaS returns user_action_required -> OriginBindingError."""
        repo_root = _setup_repo(tmp_path)
        client = MagicMock()
        client.search_issues.side_effect = SaaSTrackerClientError("Missing user link (action required -- check the Spec Kitty dashboard)")

        with pytest.raises(OriginBindingError, match="Missing user link"):
            search_origin_candidates(repo_root, query_text="test", client=client)

    def test_no_tracker_binding_raises(self, tmp_path: Path) -> None:
        """Scenario 6: No tracker binding -> OriginBindingError."""
        # No config.yaml at all
        kittify = tmp_path / ".kittify"
        kittify.mkdir(parents=True, exist_ok=True)

        with pytest.raises(OriginBindingError, match="No tracker bound"):
            search_origin_candidates(tmp_path)

    def test_wrong_provider_raises(self, tmp_path: Path) -> None:
        """Provider is 'github' -> OriginBindingError (C-001)."""
        repo_root = _setup_repo(tmp_path, provider="github")

        with pytest.raises(OriginBindingError, match="Only Jira and Linear"):
            search_origin_candidates(repo_root, query_text="test")

    def test_query_key_precedence(self, tmp_path: Path) -> None:
        """Both query_text and query_key provided: both sent to client."""
        repo_root = _setup_repo(tmp_path)
        client = MagicMock()
        client.search_issues.return_value = _make_search_response(candidates=[])

        search_origin_candidates(
            repo_root,
            query_text="some text",
            query_key="WEB-123",
            client=client,
        )

        client.search_issues.assert_called_once_with(
            "linear",
            "acme-web",
            query_text="some text",
            query_key="WEB-123",
            limit=10,
        )


# ===========================================================================
# Tests: bind_mission_origin
# ===========================================================================


class TestBindMissionOrigin:
    def test_happy_path(self, tmp_path: Path) -> None:
        """SaaS succeeds -> meta.json updated -> returns meta."""
        feature_dir = _setup_feature(tmp_path)
        candidate = _make_candidate()
        client = MagicMock()
        client.bind_mission_origin.return_value = {
            "origin_link_id": "link-uuid",
            "bound_at": "2026-04-01T00:00:00Z",
        }

        result, emitted = bind_mission_origin(
            feature_dir,
            candidate,
            "linear",
            "linear_team",
            "team-uuid",
            client=client,
        )

        # Verify SaaS was called
        client.bind_mission_origin.assert_called_once()

        # Verify meta.json was updated
        assert "origin_ticket" in result
        ot = result["origin_ticket"]
        assert ot["provider"] == "linear"
        assert ot["external_issue_key"] == "WEB-123"

        # MissionOriginBound SaaS emission was removed with the sync transport (#5)
        assert emitted is False

    def test_saas_first_ordering_saas_fails_no_local_write(
        self,
        tmp_path: Path,
    ) -> None:
        """MOST CRITICAL TEST: SaaS fails -> meta.json NOT written."""
        feature_dir = _setup_feature(tmp_path)
        candidate = _make_candidate()
        client = MagicMock()
        client.bind_mission_origin.side_effect = SaaSTrackerClientError("409 Conflict: different origin already bound")

        # Read meta before the call
        meta_before = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
        assert "origin_ticket" not in meta_before

        with pytest.raises(OriginBindingError, match="409 Conflict"):
            bind_mission_origin(
                feature_dir,
                candidate,
                "linear",
                "linear_team",
                "team-uuid",
                client=client,
            )

        # Verify meta.json was NOT modified
        meta_after = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
        assert "origin_ticket" not in meta_after

    def test_saas_first_ordering_set_origin_ticket_not_called(
        self,
        tmp_path: Path,
    ) -> None:
        """Verify set_origin_ticket is NOT called when SaaS fails."""
        feature_dir = _setup_feature(tmp_path)
        candidate = _make_candidate()
        client = MagicMock()
        client.bind_mission_origin.side_effect = SaaSTrackerClientError("fail")

        with (
            patch("specify_cli.tracker.origin.set_origin_ticket") as mock_set_origin,
            pytest.raises(OriginBindingError),
        ):
            bind_mission_origin(
                feature_dir,
                candidate,
                "linear",
                "linear_team",
                "team-uuid",
                client=client,
            )

        mock_set_origin.assert_not_called()

    def test_same_origin_noop(self, tmp_path: Path) -> None:
        """Same-origin re-bind: SaaS returns success, local overwrites."""
        feature_dir = _setup_feature(tmp_path)
        candidate = _make_candidate()
        client = MagicMock()
        client.bind_mission_origin.return_value = {
            "origin_link_id": "link-uuid",
            "bound_at": "2026-04-01T00:00:00Z",
        }

        result1, _ = bind_mission_origin(
            feature_dir,
            candidate,
            "linear",
            "linear_team",
            "team-uuid",
            client=client,
        )
        result2, _ = bind_mission_origin(
            feature_dir,
            candidate,
            "linear",
            "linear_team",
            "team-uuid",
            client=client,
        )

        assert result1["origin_ticket"] == result2["origin_ticket"]
        assert client.bind_mission_origin.call_count == 2

    def test_different_origin_409_raises(self, tmp_path: Path) -> None:
        """Different-origin 409: SaaS raises -> OriginBindingError."""
        feature_dir = _setup_feature(tmp_path)
        candidate = _make_candidate()
        client = MagicMock()
        # First bind succeeds
        client.bind_mission_origin.return_value = {
            "origin_link_id": "link-uuid",
        }

        bind_mission_origin(
            feature_dir,
            candidate,
            "linear",
            "linear_team",
            "team-uuid",
            client=client,
        )

        # Second bind with different origin -> 409
        different_candidate = _make_candidate(key="WEB-999", issue_id="diff-uuid")
        client.bind_mission_origin.side_effect = SaaSTrackerClientError("409: different origin already bound for this mission")

        with pytest.raises(OriginBindingError, match="409"):
            bind_mission_origin(
                feature_dir,
                different_candidate,
                "linear",
                "linear_team",
                "team-uuid",
                client=client,
            )

    def test_origin_ticket_has_all_required_keys(self, tmp_path: Path) -> None:
        """origin_ticket block has all 7 required keys."""
        feature_dir = _setup_feature(tmp_path)
        candidate = _make_candidate()
        client = MagicMock()
        client.bind_mission_origin.return_value = {"origin_link_id": "x"}

        result, _ = bind_mission_origin(
            feature_dir,
            candidate,
            "linear",
            "linear_team",
            "team-uuid",
            client=client,
        )

        ot = result["origin_ticket"]
        required_keys = {
            "provider",
            "resource_type",
            "resource_id",
            "external_issue_id",
            "external_issue_key",
            "external_issue_url",
            "title",
        }
        assert required_keys == set(ot.keys())

    def test_binding_ref_routing_and_derived_resource_context(self, tmp_path: Path) -> None:
        """Bind should route via binding_ref and derive resource context from config."""
        feature_dir = _setup_feature(
            tmp_path,
            project_slug="",
        )
        _setup_repo(
            tmp_path,
            provider="linear",
            project_slug="",
            binding_ref="bind-linear-123",
            provider_context={"workspace_id": "team-derived-uuid"},
        )
        candidate = _make_candidate()
        client = MagicMock()
        client.bind_mission_origin.return_value = {"origin_link_id": "x"}

        result, _ = bind_mission_origin(
            feature_dir,
            candidate,
            "linear",
            client=client,
        )

        client.bind_mission_origin.assert_called_once_with(
            "linear",
            None,
            binding_ref="bind-linear-123",
            mission_id="01KTESTMISSIONID00000000001",
            mission_slug="061-add-clerk-auth",
            external_issue_id="issue-uuid-1",
            external_issue_key="WEB-123",
            external_issue_url="https://linear.app/acme/issue/WEB-123/add-clerk-auth",
            title="Add Clerk auth",
            external_status="In Progress",
        )
        assert result["origin_ticket"]["resource_type"] == "linear_team"
        assert result["origin_ticket"]["resource_id"] == "team-derived-uuid"

    def test_remote_mapping_fallback_without_local_tracker_config(self, tmp_path: Path) -> None:
        """Bind should fall back to the hosted project mapping when local tracker config is absent."""
        repo_root = tmp_path
        (repo_root / ".kittify").mkdir(parents=True, exist_ok=True)
        feature_dir = repo_root / "kitty-specs" / "061-add-clerk-auth"
        feature_dir.mkdir(parents=True, exist_ok=True)
        meta = {
            "mission_number": "061",
            "slug": "061-add-clerk-auth",
            "mission_slug": "061-add-clerk-auth",
            "mission_id": "01KTESTMISSIONID00000000001",
            "friendly_name": "add clerk auth",
            "mission_type": "software-dev",
            "target_branch": "main",
            "created_at": "2026-04-01T00:00:00+00:00",
        }
        (feature_dir / "meta.json").write_text(
            json.dumps(meta, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        candidate = _make_candidate()
        client = MagicMock()
        client.bind_resolve.return_value = {
            "match_type": "exact",
            "binding_ref": "bind-remote-123",
            "project_slug": "spec-kitty",
            "display_label": "Priivacy",
        }
        client.bind_validate.return_value = {
            "valid": True,
            "binding_ref": "bind-remote-123",
            "display_label": "Priivacy",
            "provider_context": {"workspace_id": "team-remote-uuid"},
        }
        client.bind_mission_origin.return_value = {"origin_link_id": "x"}

        identity = SimpleNamespace(
            project_uuid=UUID("8a4a7da6-a97c-4bb4-893a-b31664abfee4"),
            project_slug="spec-kitty",
            node_id="node-123",
            repo_slug="spec-kitty/spec-kitty",
            build_id="build-123",
        )

        with (
            # #2263 WP02: origin bind-resolve now reads identity via the
            # side-effect-free resolve_identity (was ensure_identity).
            patch("specify_cli.identity.project.resolve_identity", return_value=identity),
        ):
            result, _ = bind_mission_origin(
                feature_dir,
                candidate,
                "linear",
                client=client,
            )

        client.bind_resolve.assert_called_once_with(
            "linear",
            {
                "uuid": "8a4a7da6-a97c-4bb4-893a-b31664abfee4",
                "slug": "spec-kitty",
                "node_id": "node-123",
                "repo_slug": "spec-kitty/spec-kitty",
                "build_id": "build-123",
            },
        )
        client.bind_validate.assert_called_once_with(
            "linear",
            "bind-remote-123",
            {
                "uuid": "8a4a7da6-a97c-4bb4-893a-b31664abfee4",
                "slug": "spec-kitty",
                "node_id": "node-123",
                "repo_slug": "spec-kitty/spec-kitty",
                "build_id": "build-123",
            },
        )
        client.bind_mission_origin.assert_called_once_with(
            "linear",
            "spec-kitty",
            binding_ref="bind-remote-123",
            mission_id="01KTESTMISSIONID00000000001",
            mission_slug="061-add-clerk-auth",
            external_issue_id="issue-uuid-1",
            external_issue_key="WEB-123",
            external_issue_url="https://linear.app/acme/issue/WEB-123/add-clerk-auth",
            title="Add Clerk auth",
            external_status="In Progress",
        )
        assert result["origin_ticket"]["resource_type"] == "linear_team"
        assert result["origin_ticket"]["resource_id"] == "team-remote-uuid"

    def test_remote_mapping_requires_complete_readonly_identity(self, tmp_path: Path) -> None:
        """Uninitialized checkouts must not send ``uuid=None`` to hosted bind lookup."""
        repo_root = tmp_path
        (repo_root / ".kittify").mkdir(parents=True, exist_ok=True)
        feature_dir = repo_root / "kitty-specs" / "061-add-clerk-auth"
        feature_dir.mkdir(parents=True, exist_ok=True)
        meta = {
            "mission_number": "061",
            "slug": "061-add-clerk-auth",
            "mission_slug": "061-add-clerk-auth",
            "mission_id": "01KTESTMISSIONID00000000001",
            "friendly_name": "add clerk auth",
            "mission_type": "software-dev",
            "target_branch": "main",
            "created_at": "2026-04-01T00:00:00+00:00",
        }
        (feature_dir / "meta.json").write_text(
            json.dumps(meta, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        candidate = _make_candidate()
        client = MagicMock()
        identity = SimpleNamespace(
            project_uuid=None,
            project_slug="spec-kitty",
            node_id="node-123",
            repo_slug="spec-kitty/spec-kitty",
            build_id=None,
        )

        with (
            patch("specify_cli.identity.project.resolve_identity", return_value=identity),
            pytest.raises(OriginBindingError, match="Run `spec-kitty init` first"),
        ):
            bind_mission_origin(
                feature_dir,
                candidate,
                "linear",
                client=client,
            )

        client.bind_resolve.assert_not_called()
        client.bind_validate.assert_not_called()
        client.bind_mission_origin.assert_not_called()

    def test_resolve_repo_root_ignores_feature_local_kittify(self, tmp_path: Path) -> None:
        """Feature-local .kittify must not mask the actual project root."""
        repo_root = tmp_path
        (repo_root / ".git").mkdir(parents=True, exist_ok=True)
        (repo_root / ".kittify").mkdir(parents=True, exist_ok=True)
        feature_dir = repo_root / "kitty-specs" / "061-add-clerk-auth"
        (feature_dir / ".kittify").mkdir(parents=True, exist_ok=True)

        assert _resolve_repo_root(feature_dir) == repo_root

    def test_missing_meta_json_raises(self, tmp_path: Path) -> None:
        """No meta.json -> OriginBindingError."""
        feature_dir = tmp_path / "kitty-specs" / "061-missing"
        feature_dir.mkdir(parents=True, exist_ok=True)
        candidate = _make_candidate()

        with pytest.raises(OriginBindingError, match="No meta.json"):
            bind_mission_origin(
                feature_dir,
                candidate,
                "linear",
                "linear_team",
                "team-uuid",
            )


# ===========================================================================
# Tests: start_mission_from_ticket
# ===========================================================================


class TestStartMissionFromTicket:
    @patch("specify_cli.core.mission_creation.create_mission_core")
    def test_full_flow(
        self,
        mock_create: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Full flow: creation + bind -> MissionFromTicketResult."""
        feature_dir = _setup_feature(tmp_path)
        candidate = _make_candidate()

        mock_create.return_value = MagicMock(
            feature_dir=feature_dir,
            mission_slug="061-add-clerk-auth",
        )

        # Mock the SaaS client to allow bind to succeed
        client = MagicMock()
        client.bind_mission_origin.return_value = {
            "origin_link_id": "link-uuid",
            "bound_at": "2026-04-01T00:00:00Z",
        }

        result = start_mission_from_ticket(
            tmp_path,
            candidate,
            "linear",
            "linear_team",
            "team-uuid",
            client=client,
        )

        assert isinstance(result, MissionFromTicketResult)
        assert result.feature_dir == feature_dir
        assert result.mission_slug == "061-add-clerk-auth"
        assert result.origin_ticket["provider"] == "linear"

        mock_create.assert_called_once_with(
            tmp_path,
            "web-123",
            mission="software-dev",
            target_branch=None,
            friendly_name="Add Clerk auth",
            purpose_tldr="Add Clerk auth",
            purpose_context="Make authentication consistent across the product so teams can launch a reliable sign-in flow without patchwork fixes.",
        )

    @patch("specify_cli.core.mission_creation.create_mission_core")
    def test_creation_failure_raises(
        self,
        mock_create: MagicMock,
        tmp_path: Path,
    ) -> None:
        """MissionCreationError -> OriginBindingError."""
        from specify_cli.core.mission_creation import MissionCreationError

        mock_create.side_effect = MissionCreationError("Slug already exists")
        candidate = _make_candidate()

        with pytest.raises(OriginBindingError, match="Slug already exists"):
            start_mission_from_ticket(
                tmp_path,
                candidate,
                "linear",
                "linear_team",
                "team-uuid",
            )

    @patch("specify_cli.core.mission_creation.create_mission_core")
    def test_slug_derivation(
        self,
        mock_create: MagicMock,
        tmp_path: Path,
    ) -> None:
        """'WEB-123' -> feature slug contains 'web-123'."""
        feature_dir = _setup_feature(tmp_path)

        mock_create.return_value = MagicMock(
            feature_dir=feature_dir,
            mission_slug="061-add-clerk-auth",
        )

        candidate = _make_candidate(key="WEB-123")
        client = MagicMock()
        client.bind_mission_origin.return_value = {"origin_link_id": "x"}

        start_mission_from_ticket(
            tmp_path,
            candidate,
            "linear",
            "linear_team",
            "team-uuid",
            client=client,
        )

        # Verify create_mission_core was called with the derived slug
        mock_create.assert_called_once()
        call_args = mock_create.call_args
        assert call_args[0][1] == "web-123"

    @patch("specify_cli.core.mission_creation.create_mission_core")
    def test_bind_failure_after_creation_raises(
        self,
        mock_create: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Bind failure after creation: OriginBindingError propagates."""
        feature_dir = _setup_feature(
            tmp_path,
            mission_slug="061-web-123",
        )

        mock_create.return_value = MagicMock(
            feature_dir=feature_dir,
            mission_slug="061-web-123",
        )
        candidate = _make_candidate()
        client = MagicMock()
        client.bind_mission_origin.side_effect = SaaSTrackerClientError("SaaS bind failed")

        with pytest.raises(OriginBindingError, match="SaaS bind failed"):
            start_mission_from_ticket(
                tmp_path,
                candidate,
                "linear",
                "linear_team",
                "team-uuid",
                client=client,
            )

    def test_missing_body_rejected_before_creation(
        self,
        tmp_path: Path,
    ) -> None:
        """Ticket-first mission creation requires a product-level body paragraph."""
        candidate = _make_candidate(body="")

        with pytest.raises(OriginBindingError, match="requires ticket body text"):
            start_mission_from_ticket(
                tmp_path,
                candidate,
                "linear",
                "linear_team",
                "team-uuid",
            )
