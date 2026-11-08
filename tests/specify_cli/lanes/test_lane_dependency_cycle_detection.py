"""Contract tests for deterministic execution-lane cycle rejection."""

from __future__ import annotations

import sys

import pytest

from specify_cli.lanes import compute as lanes_compute
from specify_cli.ownership.models import OwnershipManifest, WorkProductKind


pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _manifest(path: str) -> OwnershipManifest:
    return OwnershipManifest(
        execution_mode=WorkProductKind.CODE_CHANGE,
        owned_files=(path,),
        authoritative_surface=path.removesuffix("**"),
    )


def _set_in_order(values: list[str]) -> set[str]:
    result: set[str] = set()
    for value in values:
        result.add(value)
    return result


def test_clean_dag_has_no_cycle() -> None:
    lane_deps = {
        "lane-a": set(),
        "lane-b": {"lane-a"},
        "lane-c": {"lane-a", "lane-b"},
    }

    assert lanes_compute._find_lane_dependency_cycle(lane_deps) is None


@pytest.mark.parametrize(
    ("lane_deps", "expected"),
    [
        ({"lane-a": {"lane-a"}}, ("lane-a", "lane-a")),
        (
            {"lane-a": {"lane-b"}, "lane-b": {"lane-a"}},
            ("lane-a", "lane-b", "lane-a"),
        ),
        (
            {
                "lane-a": {"lane-b"},
                "lane-b": {"lane-c"},
                "lane-c": {"lane-a"},
            },
            ("lane-a", "lane-b", "lane-c", "lane-a"),
        ),
    ],
)
def test_returns_closed_directed_cycle(
    lane_deps: dict[str, set[str]],
    expected: tuple[str, ...],
) -> None:
    assert lanes_compute._find_lane_dependency_cycle(lane_deps) == expected


def test_selects_first_cycle_by_sorted_root_and_neighbor_traversal() -> None:
    larger_cycle_first = (
        ("lane-z", {"lane-y"}),
        ("lane-y", {"lane-z"}),
        ("lane-b", {"lane-a"}),
        ("lane-a", {"lane-b"}),
    )

    for items in (larger_cycle_first, tuple(reversed(larger_cycle_first))):
        lane_deps = dict(items)
        assert lanes_compute._find_lane_dependency_cycle(lane_deps) == (
            "lane-a",
            "lane-b",
            "lane-a",
        )


def test_rotates_cycle_to_smallest_member_without_reversing_edges() -> None:
    lane_deps = {
        "lane-a": {"lane-c"},
        "lane-b": {"lane-c"},
        "lane-c": {"lane-d"},
        "lane-d": {"lane-b"},
    }

    cycle = lanes_compute._find_lane_dependency_cycle(lane_deps)

    assert cycle == ("lane-b", "lane-c", "lane-d", "lane-b")
    assert cycle is not None
    assert all(downstream in lane_deps[upstream] for upstream, downstream in zip(cycle, cycle[1:], strict=False))


def test_mapping_and_set_insertion_order_do_not_change_cycle() -> None:
    forward = {
        "lane-a": {"lane-c", "lane-b"},
        "lane-b": {"lane-c"},
        "lane-c": {"lane-a"},
    }
    reverse = {lane_id: _set_in_order(sorted(dependencies, reverse=True)) for lane_id, dependencies in reversed(tuple(forward.items()))}

    expected = ("lane-a", "lane-b", "lane-c", "lane-a")
    assert lanes_compute._find_lane_dependency_cycle(forward) == expected
    assert lanes_compute._find_lane_dependency_cycle(reverse) == expected


def test_compute_lanes_rejects_cycle_created_by_overlap_collapse() -> None:
    dependency_graph = {
        "WP01": ["WP02"],
        "WP02": [],
        "WP03": ["WP04"],
        "WP04": [],
    }
    manifests = {
        "WP01": _manifest("src/a/**"),
        "WP02": _manifest("src/b/**"),
        "WP03": _manifest("src/b/**"),
        "WP04": _manifest("src/a/**"),
    }

    error_type = lanes_compute.LaneDependencyCycleError
    with pytest.raises(error_type) as exc_info:
        lanes_compute.compute_lanes(dependency_graph, manifests, "cycle-after-collapse")

    error = exc_info.value
    assert error.error_code == "LANE_DEPENDENCY_CYCLE"
    assert error.cycle_path == ("lane-a", "lane-b", "lane-a")
    message = str(error)
    assert message.count("lane-a") == 2
    assert message.index("lane-a") < message.index("lane-b") < message.rindex("lane-a")
    assert tuple(lane.lane_id for lane in error.cycle_lanes) == ("lane-a", "lane-b")
    assert error.cycle_lanes[0].wp_ids == ("WP01", "WP04")
    assert error.cycle_lanes[1].wp_ids == ("WP02", "WP03")


def test_cycle_diagnostics_include_planning_lane_membership() -> None:
    dependency_graph = {"WP01": ["WP02"], "WP02": ["WP01"]}
    manifests = {
        "WP01": _manifest("src/code/**"),
        "WP02": OwnershipManifest(
            execution_mode=WorkProductKind.PLANNING_ARTIFACT,
            owned_files=("kitty-specs/demo/**",),
            authoritative_surface="kitty-specs/demo/",
        ),
    }

    error_type = lanes_compute.LaneDependencyCycleError
    with pytest.raises(error_type) as exc_info:
        lanes_compute.compute_lanes(dependency_graph, manifests, "planning-cycle")

    assert exc_info.value.cycle_path == (
        "lane-a",
        "lane-planning",
        "lane-a",
    )
    assert tuple((lane.lane_id, lane.wp_ids) for lane in exc_info.value.cycle_lanes) == (("lane-a", ("WP01",)), ("lane-planning", ("WP02",)))


def test_compute_lanes_rejects_cycle_beyond_recursion_limit() -> None:
    """A WP cycle deeper than the recursion limit is still rejected (#5155 companion).

    Before #5155 the WPs here each got their own lane and the minting walked
    past ``lane-z`` into garbage ids (``lane-{``, …) that the later cycle
    error masked. Positional lane ids are now capped at 26, so the WPs are
    grouped into 26 write-scope blocks: the cycle still spans more WPs than
    the recursion limit, the lane graph stays within the id budget, and the
    rejection stays the typed cycle error.
    """
    wp_count = sys.getrecursionlimit() + 1
    wp_ids = [f"WP{index:05d}" for index in range(wp_count)]
    dependency_graph = {wp_id: [wp_ids[(index + 1) % wp_count]] for index, wp_id in enumerate(wp_ids)}
    # One write-scope block per mintable lane id (lane-a … lane-z): WPs that
    # share a block's scope collapse into one lane, keeping the lane count
    # at exactly 26 while the WP-level cycle wraps through all of them.
    block_count = ord("z") - ord("a") + 1
    manifests = {wp_id: _manifest(f"src/block{index % block_count:02d}/**") for index, wp_id in enumerate(wp_ids)}

    error_type = lanes_compute.LaneDependencyCycleError
    with pytest.raises(error_type):
        lanes_compute.compute_lanes(dependency_graph, manifests, "long-cycle")
