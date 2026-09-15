"""Regression fixture for disjoint fan-in lane computation."""

from __future__ import annotations

import pytest

from specify_cli.lanes.compute import compute_lanes
from specify_cli.ownership.models import WorkProductKind, OwnershipManifest

pytestmark = pytest.mark.fast


def _manifest(path: str) -> OwnershipManifest:
    return OwnershipManifest(
        execution_mode=WorkProductKind.CODE_CHANGE,
        owned_files=(path,),
        authoritative_surface=path,
    )


def test_disjoint_upstreams_remain_parallel_until_fan_in() -> None:
    upstreams = [f"WP{i:02d}" for i in range(1, 7)]
    graph = {wp_id: [] for wp_id in upstreams}
    graph["WP07"] = list(upstreams)
    manifests = {
        **{
            wp_id: _manifest(f"src/workstream_{index}/**")
            for index, wp_id in enumerate(upstreams, start=1)
        },
        "WP07": _manifest("src/fan_in/**"),
    }

    result = compute_lanes(graph, manifests, "fan-in-demo")

    assert len(result.lanes) == 7
    by_wp = {lane.wp_ids[0]: lane for lane in result.lanes}
    upstream_lane_ids = {by_wp[wp_id].lane_id for wp_id in upstreams}
    assert len(upstream_lane_ids) == 6  # (disjoint-lane assignment, not nameable lane ids)
    assert {by_wp[wp_id].parallel_group for wp_id in upstreams} == {0}
    assert by_wp["WP07"].parallel_group == 1
    assert set(by_wp["WP07"].depends_on_lanes) == upstream_lane_ids
    assert result.collapse_report is not None
    assert result.collapse_report.events == []


def test_overlapping_upstreams_still_collapse() -> None:
    graph = {"WP01": [], "WP02": [], "WP03": ["WP01", "WP02"]}
    manifests = {
        "WP01": _manifest("src/shared/**"),
        "WP02": _manifest("src/shared/api/**"),
        "WP03": _manifest("src/fan_in/**"),
    }

    result = compute_lanes(graph, manifests, "fan-in-demo")

    lane_sets = [set(lane.wp_ids) for lane in result.lanes]
    assert {"WP01", "WP02"} in lane_sets
    assert {"WP03"} in lane_sets
    assert result.collapse_report is not None
    assert result.collapse_report.events[0].rule == "write_scope_overlap"
