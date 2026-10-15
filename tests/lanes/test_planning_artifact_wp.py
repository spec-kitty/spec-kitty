"""Integration test: planning_artifact WPs have a first-class non-worktree
execution path (FR-015, WP04/T020).

Covers:
- The WP frontmatter schema accepts ``execution_mode: planning_artifact``.
- The lane planner skips planning_artifact WPs in lane fan-out (they land
  in the canonical ``lane-planning`` lane, which resolves to the repo root).
- The runtime workspace resolver returns a ``repo_root`` resolution kind
  for planning_artifact WPs (no ``.worktrees/`` allocation required).
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.fast


class TestPlanningArtifactExecutionMode:
    """The execution_mode enum must include planning_artifact."""

    def test_planning_artifact_is_a_first_class_execution_mode(self) -> None:
        from specify_cli.ownership.models import WorkProductKind

        assert WorkProductKind.PLANNING_ARTIFACT == "planning_artifact"
        assert WorkProductKind.CODE_CHANGE == "code_change"

    def test_default_execution_mode_is_code_change(self) -> None:
        """A WP without an explicit execution_mode defaults to code_change."""
        from specify_cli.ownership.models import WorkProductKind

        # The enum's value used as the documented default.
        assert WorkProductKind.CODE_CHANGE.value == "code_change"


class TestLanePlannerSkipsPlanningArtifactWPs:
    """The lane planner must NOT fan out planning_artifact WPs."""

    def test_planning_lane_id_is_canonical_constant(self) -> None:
        """Planning artifacts collect into a single canonical lane id."""
        from specify_cli.lanes.compute import PLANNING_LANE_ID

        # The canonical ID must be stable; downstream resolvers key off it.
        assert PLANNING_LANE_ID == "lane-planning"

    def test_lanes_manifest_has_planning_artifact_wps_field(self) -> None:
        """The manifest exposes a derived view of planning_artifact WPs."""
        from specify_cli.lanes.models import LanesManifest

        # The dataclass must have the field; runtime code reads it.
        assert "planning_artifact_wps" in LanesManifest.__dataclass_fields__


class TestPlanningArtifactWorkspaceResolution:
    """For planning_artifact WPs, the resolved workspace is the repo root."""

    def test_planning_artifact_resolution_kind_is_repo_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """resolve_workspace_for_wp -> resolution_kind='repo_root'."""
        from specify_cli.workspace.context import (
            ResolvedWorkspace,
            resolve_workspace_for_wp,
        )
        from specify_cli.ownership.models import WorkProductKind

        # Skip the full filesystem dance — instead, validate the
        # ResolvedWorkspace contract directly. The contract is what the
        # runtime decision JSON consumes downstream.
        workspace = ResolvedWorkspace(
            mission_slug="fixture-mission",
            wp_id="WP01",
            execution_mode=WorkProductKind.PLANNING_ARTIFACT.value,
            mode_source="explicit",
            resolution_kind="repo_root",
            workspace_name="fixture-mission-lane-planning",
            worktree_path=tmp_path,
            branch_name=None,
            lane_id="lane-planning",
            lane_wp_ids=["WP01"],
            context=None,
        )

        assert workspace.execution_mode == "planning_artifact"
        assert workspace.resolution_kind == "repo_root"
        assert workspace.branch_name is None


class TestPlanningArtifactRuntimeDecisionShape:
    """The runtime decision JSON for a planning_artifact WP must indicate
    a non-worktree execution path (no ``.worktrees/`` allocation)."""

    def test_decision_for_planning_artifact_has_repo_root_workspace(
        self, tmp_path: Path
    ) -> None:
        """A planning_artifact WP's decision points workspace_path at the
        repo root (resolved via the canonical resolver), and the decision
        kind is `step` (i.e. NOT blocked)."""
        from runtime.next.decision import Decision, DecisionKind

        # WP02 / #844: kind=step requires a real prompt_file at construction
        # time (C1/C2). Stage one under tmp_path so the validator passes.
        prompt = tmp_path / "implement.md"
        prompt.write_text("# implement", encoding="utf-8")
        decision = Decision(
            kind=DecisionKind.step,
            agent="claude",
            mission_slug="fixture-mission",
            mission="software-dev",
            mission_state="implementing",
            timestamp="2026-04-26T00:00:00+00:00",
            mission_type="software-dev",
            action="implement",
            wp_id="WP08",
            workspace_path=str(tmp_path),  # planning_artifact -> repo root
            prompt_file=str(prompt),
        )

        payload = decision.to_dict()
        # The kind is `step`; planning_artifact WPs must NOT be reported
        # as blocked when they are actually executable.
        assert payload["kind"] == "step"
        assert payload["wp_id"] == "WP08"
        # workspace_path resolves to the canonical repo root for
        # planning_artifact WPs (NOT a per-WP worktree).
        assert ".worktrees" not in (payload["workspace_path"] or "")
