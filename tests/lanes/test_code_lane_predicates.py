"""Tests for the code-lane predicates (#5100 IC-02, WP03 T011).

``is_repo_root_lane`` / ``has_code_lanes`` / ``_has_code_wps`` — true/false
cases for each, plus the control test pinning that the ``has_code_lanes``
change leaves an un-stamped planning-only mission's derivation unchanged
(the T010 test 4 negative control lives at the migration-level regression
test; this module covers the predicates themselves in isolation).
"""

from __future__ import annotations

import pytest

from specify_cli.lanes.compute import (
    PLANNING_LANE_ID,
    has_code_lanes,
    _has_code_wps,
    is_planning_lane,
    is_repo_root_lane,
)
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.ownership.models import WorkProductKind

pytestmark = pytest.mark.fast


def _lane(lane_id: str, wp_ids: tuple[str, ...]) -> ExecutionLane:
    return ExecutionLane(
        lane_id=lane_id,
        wp_ids=wp_ids,
        write_scope=(),
        predicted_surfaces=(),
        depends_on_lanes=(),
        parallel_group=0,
    )


def _manifest(lanes: list[ExecutionLane]) -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug="test-mission",
        mission_id=None,
        mission_branch="kitty/mission-test-mission",
        target_branch="main",
        lanes=lanes,
        computed_at="2026-09-28T00:00:00+00:00",
        computed_from="dependency_graph+ownership",
    )


# ---------------------------------------------------------------------------
# is_repo_root_lane
# ---------------------------------------------------------------------------


def test_is_repo_root_lane_true_for_planning_lane() -> None:
    assert is_repo_root_lane(_lane(PLANNING_LANE_ID, ("WP01",))) is True


def test_is_repo_root_lane_false_for_a_code_lane() -> None:
    assert is_repo_root_lane(_lane("lane-a", ("WP01",))) is False


def test_is_repo_root_lane_shares_backing_with_is_planning_lane() -> None:
    """Today the two names test the exact same classification (single source)."""
    for lane in (_lane(PLANNING_LANE_ID, ("WP01",)), _lane("lane-a", ("WP01",)), _lane("lane-b", ())):
        assert is_repo_root_lane(lane) == is_planning_lane(lane)


# ---------------------------------------------------------------------------
# has_code_lanes
# ---------------------------------------------------------------------------


def test_has_code_lanes_true_when_a_code_lane_is_present() -> None:
    manifest = _manifest([_lane(PLANNING_LANE_ID, ("WP01",)), _lane("lane-a", ("WP02",))])
    assert has_code_lanes(manifest) is True


def test_has_code_lanes_false_for_planning_only_manifest() -> None:
    manifest = _manifest([_lane(PLANNING_LANE_ID, ("WP01", "WP02"))])
    assert has_code_lanes(manifest) is False


def test_has_code_lanes_false_for_an_empty_manifest() -> None:
    manifest = _manifest([])
    assert has_code_lanes(manifest) is False


def test_has_code_lanes_true_for_only_code_lanes_no_planning_lane() -> None:
    manifest = _manifest([_lane("lane-a", ("WP01",)), _lane("lane-b", ("WP02",))])
    assert has_code_lanes(manifest) is True


# ---------------------------------------------------------------------------
# _has_code_wps
# ---------------------------------------------------------------------------


def test_has_code_wps_true_when_any_referenced_wp_is_code_change() -> None:
    manifest = _manifest([_lane(PLANNING_LANE_ID, ("WP01",)), _lane("lane-a", ("WP02",))])
    wp_kinds = {"WP01": WorkProductKind.PLANNING_ARTIFACT, "WP02": WorkProductKind.CODE_CHANGE}
    assert _has_code_wps(manifest, wp_kinds) is True


def test_has_code_wps_false_when_every_referenced_wp_is_planning_artifact() -> None:
    manifest = _manifest([_lane(PLANNING_LANE_ID, ("WP01", "WP02"))])
    wp_kinds = {"WP01": WorkProductKind.PLANNING_ARTIFACT, "WP02": WorkProductKind.PLANNING_ARTIFACT}
    assert _has_code_wps(manifest, wp_kinds) is False


def test_has_code_wps_false_for_an_empty_manifest() -> None:
    assert _has_code_wps(_manifest([]), {}) is False


def test_has_code_wps_ignores_wp_ids_not_in_the_index() -> None:
    """A WP referenced by the manifest but missing from the kinds index is not code."""
    manifest = _manifest([_lane(PLANNING_LANE_ID, ("WP99",))])
    assert _has_code_wps(manifest, {}) is False


# ---------------------------------------------------------------------------
# Control: the has_code_lanes change does not reclassify a planning-only,
# un-stamped mission's derived topology (guards the #5100 IC-02 fix itself).
# ---------------------------------------------------------------------------


def test_planning_only_manifest_still_has_no_code_lanes_after_the_change() -> None:
    """Pin: a planning-only lanes.json never counts as 'has code lanes'.

    This is the shape ``migration.backfill_topology._has_lanes`` now
    delegates to (T011); a mission whose ONLY lane is ``lane-planning``
    must derive ``has_code_lanes() is False`` both for a fresh manifest
    (this test) and for the whole-mission derivation regression pinned in
    ``tests/specify_cli/upgrade/migrations/test_single_branch_code_lanes_restamp.py``.
    """
    manifest = _manifest([_lane(PLANNING_LANE_ID, ("WP01", "WP02", "WP03"))])
    assert has_code_lanes(manifest) is False
