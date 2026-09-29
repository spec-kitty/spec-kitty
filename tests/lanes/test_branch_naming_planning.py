"""Regression tests for lane_branch_name() lane-planning behaviour (T011, FR-103;
target_branch cutover WP02/#5100 FR-001/FR-002).

Verifies that:
- lane_branch_name with lane-planning returns target_branch, not a kitty/ branch.
- target_branch is a REQUIRED keyword -- there is no silent default (the
  pre-WP02 "returns 'main' by default" behaviour was the #5100 defect: a
  planning lane could resolve to a branch that does not exist on a mission
  whose real target branch is something else).
- Existing behaviour for normal lane IDs is unchanged.
"""

from __future__ import annotations

import pytest

from specify_cli.lanes import branch_naming, compute
from specify_cli.lanes.branch_naming import code_lane_branch_name, lane_branch_name
from specify_cli.lanes.compute import PLANNING_LANE_ID

pytestmark = pytest.mark.fast


def test_planning_lane_id_has_a_single_definition() -> None:
    """``compute.PLANNING_LANE_ID`` re-exposes ``branch_naming``'s constant, never a restated literal."""
    assert compute.PLANNING_LANE_ID is branch_naming.PLANNING_LANE_ID
    assert branch_naming.PLANNING_LANE_ID == "lane-planning"


class TestLaneBranchNamePlanningLane:
    """T2.3 — lane_branch_name for lane-planning returns target_branch."""

    def test_lane_branch_name_planning_requires_target_branch(self):
        """target_branch is a required keyword -- no silent default (#5100)."""
        with pytest.raises(TypeError):
            lane_branch_name("079-test", "lane-planning")  # type: ignore[call-arg]

    def test_lane_branch_name_planning_with_explicit_main(self):
        """Explicit target_branch='main' → 'main'."""
        result = lane_branch_name("079-test", "lane-planning", target_branch="main")
        assert result == "main"

    def test_lane_branch_name_planning_with_custom_branch(self):
        """Explicit target_branch is returned verbatim."""
        result = lane_branch_name("079-test", "lane-planning", target_branch="release/3.x")
        assert result == "release/3.x"

    def test_lane_branch_name_planning_constant(self):
        """PLANNING_LANE_ID resolves to the given target_branch."""
        result = lane_branch_name("079-test", PLANNING_LANE_ID, target_branch="main")
        assert result == "main"

    def test_lane_branch_name_planning_does_not_use_kitty_prefix(self):
        """lane-planning must never produce a kitty/mission-… style name."""
        result = lane_branch_name("079-test", "lane-planning", target_branch="main")
        assert not result.startswith("kitty/")


class TestLaneBranchNameNormalLanesUnchanged:
    """Existing behaviour for non-planning lanes must be preserved."""

    def test_lane_branch_name_for_normal_lane_unchanged(self):
        """lane-a style IDs still produce kitty/mission-… names."""
        assert lane_branch_name("079-test", "lane-a", target_branch="main") == "kitty/mission-079-test-lane-a"

    def test_lane_branch_name_for_lane_b_unchanged(self):
        assert lane_branch_name("079-test", "lane-b", target_branch="main") == "kitty/mission-079-test-lane-b"

    def test_lane_branch_name_normal_lane_ignores_target_branch(self):
        """target_branch is ignored for non-planning lane IDs."""
        result = lane_branch_name("079-test", "lane-a", target_branch="main")
        assert result == "kitty/mission-079-test-lane-a"

    def test_lane_branch_name_slug_with_hyphens(self):
        """Mission slugs with hyphens are preserved verbatim."""
        result = lane_branch_name("079-post-555-release-hardening", "lane-a", target_branch="main")
        assert result == "kitty/mission-079-post-555-release-hardening-lane-a"

    def test_code_lane_branch_name_normal_lane_matches(self):
        """code_lane_branch_name (no target_branch needed) agrees with lane_branch_name."""
        assert code_lane_branch_name("079-test", "lane-a") == "kitty/mission-079-test-lane-a"

    def test_code_lane_branch_name_refuses_planning_lane(self):
        with pytest.raises(ValueError, match="planning lane"):
            code_lane_branch_name("079-test", PLANNING_LANE_ID)
