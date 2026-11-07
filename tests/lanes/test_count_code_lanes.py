"""``count_code_lanes`` (S7 #7282, T077): the size rule's code-lane count excludes ``lane-planning``."""

from __future__ import annotations

import pytest

from specify_cli.lanes.compute import PLANNING_LANE_ID
from specify_cli.lanes.compute_and_persist import count_code_lanes
from specify_cli.lanes.models import ExecutionLane, LanesManifest

pytestmark = [pytest.mark.fast]


def _lane(lane_id: str) -> ExecutionLane:
    return ExecutionLane(lane_id=lane_id, wp_ids=("WP01",), write_scope=(), predicted_surfaces=(), depends_on_lanes=(), parallel_group=0)


def _manifest(*lane_ids: str) -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug="m",
        mission_id=None,
        mission_branch="kitty/mission-m",
        target_branch="main",
        lanes=[_lane(lane_id) for lane_id in lane_ids],
        computed_at="2026-11-06T00:00:00+00:00",
        computed_from="test",
    )


@pytest.mark.parametrize(
    ("lane_ids", "expected"),
    [
        ((), 0),
        ((PLANNING_LANE_ID,), 0),
        (("lane-a",), 1),
        ((PLANNING_LANE_ID, "lane-a", "lane-b"), 2),
        (("lane-a", "lane-b", "lane-c"), 3),
    ],
)
def test_count_code_lanes_on_a_manifest(lane_ids: tuple[str, ...], expected: int) -> None:
    assert count_code_lanes(_manifest(*lane_ids)) == expected


def test_count_code_lanes_on_a_lane_sequence() -> None:
    assert count_code_lanes([_lane(PLANNING_LANE_ID), _lane("lane-a")]) == 1
