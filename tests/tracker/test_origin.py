"""Tests for the origin binding service layer (WP05).

Covers:
- bind_mission_origin(): SaaS-first ordering, happy path, error cases
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from specify_cli.tracker.origin import (
    OriginBindingError,
    _resolve_repo_root,
    bind_mission_origin,
)
from specify_cli.tracker.origin_models import OriginCandidate
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
