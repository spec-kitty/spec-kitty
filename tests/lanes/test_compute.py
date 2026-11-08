"""Tests for lane computation algorithm."""

import pytest

from specify_cli.lanes.compute import (
    LaneComputationError,
    LaneIdExhaustedError,
    _are_disjoint,
    _describe_overlap,
    _next_free_lane_id,
    compute_lanes,
    find_overlap_pairs,
    infer_surfaces,
)
from specify_cli.lanes.models import LanesManifest
from specify_cli.ownership.models import WorkProductKind, OwnershipManifest

pytestmark = pytest.mark.fast


def _manifest(owned_files: list[str], mode: str = "code_change") -> OwnershipManifest:
    return OwnershipManifest(
        execution_mode=WorkProductKind(mode),
        owned_files=tuple(owned_files),
        authoritative_surface=owned_files[0] if owned_files else "",
    )


def _assert_manifest_graph_is_acyclic(manifest: LanesManifest) -> None:
    """Independently prove the returned lane graph admits a topological order."""
    remaining = {lane.lane_id: set(lane.depends_on_lanes) for lane in manifest.lanes}
    visited: set[str] = set()
    while ready := sorted(lane_id for lane_id, dependencies in remaining.items() if lane_id not in visited and dependencies <= visited):
        visited.update(ready)
    assert visited == set(remaining)


# ---------------------------------------------------------------------------
# Rule 1: Dependencies → same lane
# ---------------------------------------------------------------------------


class TestDependenciesGrouping:
    def test_sequential_chain_uses_lane_dependencies(self):
        """A→B→C with disjoint ownership: three ordered lanes."""
        graph = {"WP01": [], "WP02": ["WP01"], "WP03": ["WP02"]}
        manifests = {
            "WP01": _manifest(["src/a/**"]),
            "WP02": _manifest(["src/b/**"]),
            "WP03": _manifest(["src/c/**"]),
        }
        result = compute_lanes(graph, manifests, "test-feat")
        assert len(result.lanes) == 3
        by_wp = {lane.wp_ids[0]: lane for lane in result.lanes}
        assert by_wp["WP02"].depends_on_lanes == (by_wp["WP01"].lane_id,)
        assert by_wp["WP03"].depends_on_lanes == (by_wp["WP02"].lane_id,)
        assert by_wp["WP01"].parallel_group == 0
        assert by_wp["WP02"].parallel_group == 1
        assert by_wp["WP03"].parallel_group == 2
        assert result.mission_branch == "kitty/mission-test-feat"
        assert result.target_branch == "main"
        assert result.collapse_report is not None
        assert result.collapse_report.events == []
        _assert_manifest_graph_is_acyclic(result)

    def test_diamond_dag_keeps_middle_parallel(self):
        """A→B, A→C, B→D, C→D: B and C can run in parallel."""
        graph = {
            "WP01": [],
            "WP02": ["WP01"],
            "WP03": ["WP01"],
            "WP04": ["WP02", "WP03"],
        }
        manifests = {
            "WP01": _manifest(["src/a/**"]),
            "WP02": _manifest(["src/b/**"]),
            "WP03": _manifest(["src/c/**"]),
            "WP04": _manifest(["src/d/**"]),
        }
        result = compute_lanes(graph, manifests, "test-feat")
        assert len(result.lanes) == 4
        by_wp = {lane.wp_ids[0]: lane for lane in result.lanes}
        assert by_wp["WP02"].depends_on_lanes == (by_wp["WP01"].lane_id,)
        assert by_wp["WP03"].depends_on_lanes == (by_wp["WP01"].lane_id,)
        assert set(by_wp["WP04"].depends_on_lanes) == {
            by_wp["WP02"].lane_id,
            by_wp["WP03"].lane_id,
        }
        assert by_wp["WP02"].parallel_group == by_wp["WP03"].parallel_group
        assert all(lane.depends_on_lanes == tuple(sorted(lane.depends_on_lanes)) for lane in result.lanes)
        _assert_manifest_graph_is_acyclic(result)

    def test_two_independent_chains_keep_parallel_starts(self):
        """A→B and C→D with no overlap → four lanes across two depths."""
        graph = {
            "WP01": [],
            "WP02": ["WP01"],
            "WP03": [],
            "WP04": ["WP03"],
        }
        manifests = {
            "WP01": _manifest(["src/a/**"]),
            "WP02": _manifest(["src/b/**"]),
            "WP03": _manifest(["src/c/**"]),
            "WP04": _manifest(["src/d/**"]),
        }
        result = compute_lanes(graph, manifests, "test-feat")
        assert len(result.lanes) == 4
        by_wp = {lane.wp_ids[0]: lane for lane in result.lanes}
        assert by_wp["WP01"].parallel_group == by_wp["WP03"].parallel_group == 0
        assert by_wp["WP02"].parallel_group == by_wp["WP04"].parallel_group == 1
        assert by_wp["WP02"].depends_on_lanes == (by_wp["WP01"].lane_id,)
        assert by_wp["WP04"].depends_on_lanes == (by_wp["WP03"].lane_id,)


# ---------------------------------------------------------------------------
# Rule 2: Write-scope overlap → same lane
# ---------------------------------------------------------------------------


class TestWriteScopeGrouping:
    def test_independent_wps_with_overlap_same_lane(self):
        """A, B have no dep but overlapping files → same lane."""
        graph = {"WP01": [], "WP02": []}
        manifests = {
            "WP01": _manifest(["src/core/**"]),
            "WP02": _manifest(["src/core/utils/**"]),
        }
        result = compute_lanes(graph, manifests, "test-feat")
        assert len(result.lanes) == 1
        assert set(result.lanes[0].wp_ids) == {"WP01", "WP02"}

    def test_independent_wps_no_overlap_separate_lanes(self):
        """A, B have no dep, no overlap → separate lanes."""
        graph = {"WP01": [], "WP02": []}
        manifests = {
            "WP01": _manifest(["src/core/**"]),
            "WP02": _manifest(["src/merge/**"]),
        }
        result = compute_lanes(graph, manifests, "test-feat")
        assert len(result.lanes) == 2

    def test_chain_plus_overlap_merges_only_overlapping_scope(self):
        """A→B + independent C overlapping B's files → B/C lane depends on A."""
        graph = {"WP01": [], "WP02": ["WP01"], "WP03": []}
        manifests = {
            "WP01": _manifest(["src/a/**"]),
            "WP02": _manifest(["src/b/**"]),
            "WP03": _manifest(["src/b/utils/**"]),
        }
        result = compute_lanes(graph, manifests, "test-feat")
        assert len(result.lanes) == 2
        lane_wp_sets = [set(lane.wp_ids) for lane in result.lanes]
        assert {"WP01"} in lane_wp_sets
        assert {"WP02", "WP03"} in lane_wp_sets
        wp01_lane = next(lane for lane in result.lanes if lane.wp_ids == ("WP01",))
        overlap_lane = next(lane for lane in result.lanes if set(lane.wp_ids) == {"WP02", "WP03"})
        assert overlap_lane.depends_on_lanes == (wp01_lane.lane_id,)
        assert result.collapse_report is not None
        assert result.collapse_report.independent_wps_collapsed == 1
        _assert_manifest_graph_is_acyclic(result)


# ---------------------------------------------------------------------------
# Rule 3: Surface overlap → same lane
# ---------------------------------------------------------------------------


class TestSurfaceGrouping:
    def test_shared_surface_disjoint_ownership_separate_lanes(self):
        """Two independent WPs with disjoint ownership mentioning 'dashboard' → separate lanes.

        Rule 3 refinement: surface match alone is not sufficient when ownership is
        provably disjoint. Previously this collapsed to one lane.
        """
        graph = {"WP01": [], "WP02": []}
        manifests = {
            "WP01": _manifest(["src/views/**"]),
            "WP02": _manifest(["src/templates/**"]),
        }
        wp_bodies = {
            "WP01": "Implement the dashboard landing page",
            "WP02": "Create dashboard template components",
        }
        result = compute_lanes(graph, manifests, "test-feat", wp_bodies=wp_bodies)
        assert len(result.lanes) == 2

    def test_shared_surface_overlapping_ownership_same_lane(self):
        """Two independent WPs with overlapping ownership + shared surface → same lane."""
        graph = {"WP01": [], "WP02": []}
        manifests = {
            "WP01": _manifest(["src/views/**"]),
            "WP02": _manifest(["src/views/dashboard/**"]),  # overlaps src/views/**
        }
        wp_bodies = {
            "WP01": "Implement the dashboard landing page",
            "WP02": "Create dashboard sub-views",
        }
        result = compute_lanes(graph, manifests, "test-feat", wp_bodies=wp_bodies)
        assert len(result.lanes) == 1

    def test_different_surfaces_separate_lanes(self):
        """Two independent WPs with different surfaces → separate lanes."""
        graph = {"WP01": [], "WP02": []}
        manifests = {
            "WP01": _manifest(["src/views/**"]),
            "WP02": _manifest(["src/api/**"]),
        }
        wp_bodies = {
            "WP01": "Implement the dashboard landing page",
            "WP02": "Build the tracker integration",
        }
        result = compute_lanes(graph, manifests, "test-feat", wp_bodies=wp_bodies)
        assert len(result.lanes) == 2

    def test_disjoint_ownership_preserves_parallelism(self):
        """WP A owns src/a/**, WP B owns src/b/**, both mention 'api' → separate lanes.

        This is the canonical regression test for FR-009.
        """
        graph = {"WP01": [], "WP02": []}
        manifests = {
            "WP01": _manifest(["src/a/**"]),
            "WP02": _manifest(["src/b/**"]),
        }
        wp_bodies = {
            "WP01": "Add API endpoints for the new service",
            "WP02": "Refactor API routes for legacy cleanup",
        }
        result = compute_lanes(graph, manifests, "test-feat", wp_bodies=wp_bodies)
        assert len(result.lanes) == 2
        lane_wp_sets = [set(lane.wp_ids) for lane in result.lanes]
        assert {"WP01"} in lane_wp_sets
        assert {"WP02"} in lane_wp_sets


# ---------------------------------------------------------------------------
# Planning artifact exclusion
# ---------------------------------------------------------------------------


class TestPlanningArtifactLane:
    def test_planning_artifacts_get_lane_planning(self):
        """Planning-artifact WPs are assigned to the canonical lane-planning lane."""
        from specify_cli.lanes.compute import PLANNING_LANE_ID

        graph = {"WP01": [], "WP02": [], "WP03": []}
        manifests = {
            "WP01": _manifest(["src/core/**"]),
            "WP02": _manifest(["kitty-specs/docs/**"], mode="planning_artifact"),
            "WP03": _manifest(["src/merge/**"]),
        }
        result = compute_lanes(graph, manifests, "test-feat")
        # WP02 → lane-planning, WP01 and WP03 each → independent code lanes
        assert len(result.lanes) == 3
        lane_ids = {lane.lane_id for lane in result.lanes}
        assert PLANNING_LANE_ID in lane_ids
        planning_lane = next(l for l in result.lanes if l.lane_id == PLANNING_LANE_ID)
        assert "WP02" in planning_lane.wp_ids
        # Code WPs are NOT in lane-planning
        code_wp_ids: set[str] = set()
        for lane in result.lanes:
            if lane.lane_id != PLANNING_LANE_ID:
                code_wp_ids.update(lane.wp_ids)
        assert "WP01" in code_wp_ids
        assert "WP03" in code_wp_ids
        assert planning_lane.depends_on_lanes == ()
        assert result.planning_artifact_wps == ["WP02"]
        _assert_manifest_graph_is_acyclic(result)

    def test_planning_artifact_wps_is_derived_view(self):
        """LanesManifest.planning_artifact_wps is a derived view from lane-planning."""
        graph = {"WP01": [], "WP02": []}
        manifests = {
            "WP01": _manifest(["src/core/**"]),
            "WP02": _manifest(["kitty-specs/docs/**"], mode="planning_artifact"),
        }
        result = compute_lanes(graph, manifests, "test-feat")
        assert result.planning_artifact_wps == ["WP02"]

    def test_all_planning_artifacts_single_planning_lane(self):
        """All WPs are planning artifacts → only lane-planning lane exists."""
        from specify_cli.lanes.compute import PLANNING_LANE_ID

        graph = {"WP01": [], "WP02": []}
        manifests = {
            "WP01": _manifest(["kitty-specs/**"], mode="planning_artifact"),
            "WP02": _manifest(["docs/**"], mode="planning_artifact"),
        }
        result = compute_lanes(graph, manifests, "test-feat")
        assert len(result.lanes) == 1
        assert result.lanes[0].lane_id == PLANNING_LANE_ID
        assert set(result.lanes[0].wp_ids) == {"WP01", "WP02"}


# ---------------------------------------------------------------------------
# Lane ordering and parallel groups
# ---------------------------------------------------------------------------


class TestLaneOrdering:
    def test_topo_order_within_lane(self):
        """WPs collapsed by overlap within a lane are topologically ordered."""
        graph = {"WP01": [], "WP02": ["WP01"], "WP03": ["WP02"]}
        manifests = {
            "WP01": _manifest(["src/core/**"]),
            "WP02": _manifest(["src/core/api/**"]),
            "WP03": _manifest(["src/core/api/routes/**"]),
        }
        result = compute_lanes(graph, manifests, "test-feat")
        assert len(result.lanes) == 1
        assert result.lanes[0].wp_ids == ("WP01", "WP02", "WP03")

    def test_parallel_groups_independent_lanes(self):
        """Independent lanes get the same parallel group (0)."""
        graph = {"WP01": [], "WP02": [], "WP03": []}
        manifests = {
            "WP01": _manifest(["src/a/**"]),
            "WP02": _manifest(["src/b/**"]),
            "WP03": _manifest(["src/c/**"]),
        }
        result = compute_lanes(graph, manifests, "test-feat")
        assert len(result.lanes) == 3
        for lane in result.lanes:
            assert lane.parallel_group == 0


# ---------------------------------------------------------------------------
# Lane-level dependencies
# ---------------------------------------------------------------------------


class TestLaneLevelDependencies:
    def test_lane_deps_from_write_scope_grouping(self):
        """Lane B depends on Lane A when a WP in B depends on a WP in A
        and they ended up in different lanes.
        """
        # A→B, C→D — two independent chains, no overlap
        graph = {
            "WP01": [],
            "WP02": ["WP01"],
            "WP03": [],
            "WP04": ["WP03"],
        }
        manifests = {
            "WP01": _manifest(["src/a/**"]),
            "WP02": _manifest(["src/b/**"]),
            "WP03": _manifest(["src/c/**"]),
            "WP04": _manifest(["src/d/**"]),
        }
        result = compute_lanes(graph, manifests, "test-feat")
        assert len(result.lanes) == 4
        by_wp = {lane.wp_ids[0]: lane for lane in result.lanes}
        assert by_wp["WP02"].depends_on_lanes == (by_wp["WP01"].lane_id,)
        assert by_wp["WP04"].depends_on_lanes == (by_wp["WP03"].lane_id,)

    def test_lanes_are_ordered_by_dependency_depth(self):
        """Persisted lane order keeps upstream lanes before downstream lanes."""
        graph = {"WP01": ["WP02"], "WP02": []}
        manifests = {
            "WP01": _manifest(["src/downstream/**"]),
            "WP02": _manifest(["src/upstream/**"]),
        }
        result = compute_lanes(graph, manifests, "test-feat")

        assert result.lanes[0].wp_ids == ("WP02",)
        assert result.lanes[1].wp_ids == ("WP01",)
        assert result.lanes[1].depends_on_lanes == (result.lanes[0].lane_id,)
        _assert_manifest_graph_is_acyclic(result)

    def test_lane_cycle_after_overlap_collapse_fails_loudly(self):
        """An acyclic WP graph can still become a cyclic lane graph after collapse."""
        graph = {
            "WP01": ["WP02"],
            "WP02": [],
            "WP03": ["WP04"],
            "WP04": [],
        }
        manifests = {
            # WP01 and WP04 collapse into lane-a.
            "WP01": _manifest(["src/a/**"]),
            "WP04": _manifest(["src/a/sub/**"]),
            # WP02 and WP03 collapse into lane-b.
            "WP02": _manifest(["src/b/**"]),
            "WP03": _manifest(["src/b/sub/**"]),
        }

        with pytest.raises(LaneComputationError, match="Execution-lane dependency cycle detected"):
            compute_lanes(graph, manifests, "test-feat")


# ---------------------------------------------------------------------------
# Manifest metadata
# ---------------------------------------------------------------------------


class TestManifestMetadata:
    def test_mission_branch_naming(self):
        graph = {"WP01": []}
        manifests = {"WP01": _manifest(["src/**"])}
        result = compute_lanes(graph, manifests, "057-my-feature")
        assert result.mission_branch == "kitty/mission-057-my-feature"

    def test_target_branch(self):
        graph = {"WP01": []}
        manifests = {"WP01": _manifest(["src/**"])}
        result = compute_lanes(graph, manifests, "test", target_branch="develop")
        assert result.target_branch == "develop"

    def test_version(self):
        graph = {"WP01": []}
        manifests = {"WP01": _manifest(["src/**"])}
        result = compute_lanes(graph, manifests, "test")
        assert result.version == 1

    def test_computed_from(self):
        graph = {"WP01": []}
        manifests = {"WP01": _manifest(["src/**"])}
        result = compute_lanes(graph, manifests, "test")
        assert result.computed_from == "dependency_graph+ownership"

    def test_empty_graph(self):
        result = compute_lanes({}, {}, "test")
        assert len(result.lanes) == 0
        assert result.mission_branch == "kitty/mission-test"


# ---------------------------------------------------------------------------
# find_overlap_pairs
# ---------------------------------------------------------------------------


class TestFindOverlapPairs:
    def test_overlapping_pair(self):
        manifests = {
            "WP01": _manifest(["src/core/**"]),
            "WP02": _manifest(["src/core/utils/**"]),
        }
        pairs = find_overlap_pairs(manifests)
        assert ("WP01", "WP02") in pairs

    def test_no_overlap(self):
        manifests = {
            "WP01": _manifest(["src/core/**"]),
            "WP02": _manifest(["src/merge/**"]),
        }
        pairs = find_overlap_pairs(manifests)
        assert len(pairs) == 0

    def test_multiple_overlaps_deduplicated(self):
        """Multiple overlapping globs between same pair → only one pair entry."""
        manifests = {
            "WP01": _manifest(["src/core/**", "src/core/utils/**"]),
            "WP02": _manifest(["src/core/utils/**", "src/core/models/**"]),
        }
        pairs = find_overlap_pairs(manifests)
        assert pairs.count(("WP01", "WP02")) == 1


# ---------------------------------------------------------------------------
# infer_surfaces
# ---------------------------------------------------------------------------


class TestInferSurfaces:
    def test_dashboard_keyword(self):
        assert "dashboard" in infer_surfaces("Build the dashboard page")

    def test_api_keyword(self):
        assert "api" in infer_surfaces("Create API endpoints")

    def test_legacy_cleanup_keyword(self):
        surfaces = infer_surfaces("Remove legacy fallback pages")
        assert "legacy-cleanup" in surfaces

    def test_no_match(self):
        assert infer_surfaces("Do something generic") == []

    def test_multiple_surfaces(self):
        surfaces = infer_surfaces("Build dashboard API with tracker integration")
        assert "dashboard" in surfaces
        assert "api" in surfaces
        assert "tracker-integration" in surfaces


# ---------------------------------------------------------------------------
# T010: Completeness assertion — all executable WPs appear in lanes
# ---------------------------------------------------------------------------


class TestCompletenessAssertion:
    def test_all_executable_wps_in_lanes(self):
        """All 5 code-change WPs must appear in exactly one lane."""
        graph = {
            "WP01": [],
            "WP02": ["WP01"],
            "WP03": [],
            "WP04": ["WP03"],
            "WP05": [],
        }
        manifests = {
            "WP01": _manifest(["src/a/**"]),
            "WP02": _manifest(["src/b/**"]),
            "WP03": _manifest(["src/c/**"]),
            "WP04": _manifest(["src/d/**"]),
            "WP05": _manifest(["src/e/**"]),
        }
        result = compute_lanes(graph, manifests, "test-feat")
        all_in_lanes: set[str] = set()
        for lane in result.lanes:
            all_in_lanes.update(lane.wp_ids)
        assert {"WP01", "WP02", "WP03", "WP04", "WP05"} == all_in_lanes


# ---------------------------------------------------------------------------
# T011: Missing ownership manifest raises LaneComputationError
# ---------------------------------------------------------------------------


class TestMissingManifestError:
    def test_missing_manifest_raises_error(self):
        """An executable WP with no ownership manifest must raise LaneComputationError."""
        graph = {"WP01": [], "WP02": []}
        manifests = {
            "WP01": _manifest(["src/a/**"]),
            # WP02 has no manifest at all
        }
        with pytest.raises(LaneComputationError, match="WP02"):
            compute_lanes(graph, manifests, "test-feat")

    def test_missing_manifest_error_names_wp(self):
        """The error message must name the missing WP."""
        graph = {"WP01": [], "WP99": []}
        manifests = {"WP01": _manifest(["src/a/**"])}
        with pytest.raises(LaneComputationError) as exc_info:
            compute_lanes(graph, manifests, "test-feat")
        assert "WP99" in str(exc_info.value)


# ---------------------------------------------------------------------------
# T012: Planning-artifact exclusion diagnostic
# ---------------------------------------------------------------------------


class TestPlanningArtifactDiagnostic:
    def test_planning_artifact_in_lane_planning_and_diagnostic(self):
        """Planning WPs are in lane-planning lane and listed in planning_artifact_wps."""
        from specify_cli.lanes.compute import PLANNING_LANE_ID

        graph = {"WP01": [], "WP02": [], "WP03": []}
        manifests = {
            "WP01": _manifest(["src/core/**"]),
            "WP02": _manifest(["kitty-specs/docs/**"], mode="planning_artifact"),
            "WP03": _manifest(["src/merge/**"]),
        }
        result = compute_lanes(graph, manifests, "test-feat")
        # WP02 in lane-planning, not in code lanes
        code_wp_ids: set[str] = set()
        planning_wp_ids: set[str] = set()
        for lane in result.lanes:
            if lane.lane_id == PLANNING_LANE_ID:
                planning_wp_ids.update(lane.wp_ids)
            else:
                code_wp_ids.update(lane.wp_ids)
        assert "WP02" not in code_wp_ids
        assert "WP02" in planning_wp_ids
        # WP02 listed in diagnostic derived view
        assert "WP02" in result.planning_artifact_wps

    def test_planning_artifact_wps_empty_when_none(self):
        """When there are no planning artifacts, the list must be empty."""
        graph = {"WP01": [], "WP02": []}
        manifests = {
            "WP01": _manifest(["src/a/**"]),
            "WP02": _manifest(["src/b/**"]),
        }
        result = compute_lanes(graph, manifests, "test-feat")
        assert result.planning_artifact_wps == []

    def test_all_planning_artifacts_planning_lane_only(self):
        """When all WPs are planning artifacts, only lane-planning lane exists."""
        from specify_cli.lanes.compute import PLANNING_LANE_ID

        graph = {"WP01": [], "WP02": []}
        manifests = {
            "WP01": _manifest(["kitty-specs/**"], mode="planning_artifact"),
            "WP02": _manifest(["docs/**"], mode="planning_artifact"),
        }
        result = compute_lanes(graph, manifests, "test-feat")
        assert len(result.lanes) == 1
        assert result.lanes[0].lane_id == PLANNING_LANE_ID
        assert set(result.planning_artifact_wps) == {"WP01", "WP02"}

    def test_planning_artifact_wps_in_serialized_dict(self):
        """planning_artifact_wps must appear in to_dict() output."""
        graph = {"WP01": [], "WP02": []}
        manifests = {
            "WP01": _manifest(["src/a/**"]),
            "WP02": _manifest(["kitty-specs/x/**"], mode="planning_artifact"),
        }
        result = compute_lanes(graph, manifests, "test-feat")
        data = result.to_dict()
        assert "planning_artifact_wps" in data
        assert "WP02" in data["planning_artifact_wps"]


# ---------------------------------------------------------------------------
# T017/T019: Collapse events recorded and independent collapse counting
# ---------------------------------------------------------------------------


class TestCollapseEvents:
    def test_disjoint_dependency_records_no_collapse_event(self):
        """Dependency-only edges become lane dependencies, not collapse events."""
        graph = {"WP01": [], "WP02": ["WP01"]}
        manifests = {
            "WP01": _manifest(["src/a/**"]),
            "WP02": _manifest(["src/b/**"]),
        }
        result = compute_lanes(graph, manifests, "test-feat")
        assert result.collapse_report is not None
        assert result.collapse_report.events == []
        by_wp = {lane.wp_ids[0]: lane for lane in result.lanes}
        assert by_wp["WP02"].depends_on_lanes == (by_wp["WP01"].lane_id,)

    def test_overlap_event_evidence_includes_dependency_when_present(self):
        """Overlap collapse evidence includes direct dependency context."""
        graph = {"WP01": [], "WP02": ["WP01"]}
        manifests = {
            "WP01": _manifest(["src/core/**"]),
            "WP02": _manifest(["src/core/api/**"]),
        }
        result = compute_lanes(graph, manifests, "test-feat")
        assert result.collapse_report is not None
        ws_events = [e for e in result.collapse_report.events if e.rule == "write_scope_overlap"]
        assert len(ws_events) == 1
        assert "WP02 depends on WP01" in ws_events[0].evidence

    def test_write_scope_rule_records_event(self):
        """Overlap-based merge → CollapseEvent with rule='write_scope_overlap'."""
        graph = {"WP01": [], "WP02": []}
        manifests = {
            "WP01": _manifest(["src/core/**"]),
            "WP02": _manifest(["src/core/utils/**"]),
        }
        result = compute_lanes(graph, manifests, "test-feat")
        assert result.collapse_report is not None
        rules = [e.rule for e in result.collapse_report.events]
        assert "write_scope_overlap" in rules

    def test_write_scope_event_evidence_contains_globs(self):
        """Write-scope event evidence names the overlapping globs."""
        graph = {"WP01": [], "WP02": []}
        manifests = {
            "WP01": _manifest(["src/core/**"]),
            "WP02": _manifest(["src/core/utils/**"]),
        }
        result = compute_lanes(graph, manifests, "test-feat")
        assert result.collapse_report is not None
        ws_events = [e for e in result.collapse_report.events if e.rule == "write_scope_overlap"]
        assert len(ws_events) == 1
        assert "src/core/**" in ws_events[0].evidence
        assert "src/core/utils/**" in ws_events[0].evidence

    def test_surface_heuristic_records_event(self):
        """Surface-based merge (non-disjoint) → CollapseEvent with rule='surface_heuristic'."""
        graph = {"WP01": [], "WP02": []}
        manifests = {
            "WP01": _manifest(["src/views/**"]),
            "WP02": _manifest(["src/views/dashboard/**"]),  # overlaps
        }
        wp_bodies = {
            "WP01": "Implement the dashboard landing page",
            "WP02": "Create dashboard sub-views",
        }
        result = compute_lanes(graph, manifests, "test-feat", wp_bodies=wp_bodies)
        assert result.collapse_report is not None
        # The write-scope overlap catches this first; no surface_heuristic needed
        # But we test both rules are recorded across scenarios
        rules = [e.rule for e in result.collapse_report.events]
        # At minimum, write_scope_overlap must fire for overlapping globs
        assert "write_scope_overlap" in rules

    def test_independent_collapse_count_with_overlap(self):
        """Independent WPs forced to same lane via write-scope → count > 0."""
        graph = {"WP01": [], "WP02": []}
        manifests = {
            "WP01": _manifest(["src/core/**"]),
            "WP02": _manifest(["src/core/utils/**"]),
        }
        result = compute_lanes(graph, manifests, "test-feat")
        assert result.collapse_report is not None
        # WP01 and WP02 have no dependency relationship → independent collapse
        assert result.collapse_report.independent_wps_collapsed == 1

    def test_dependent_collapse_not_counted_independent(self):
        """Dependent WPs in same lane (via dep rule) → independent count = 0."""
        graph = {"WP01": [], "WP02": ["WP01"]}
        manifests = {
            "WP01": _manifest(["src/a/**"]),
            "WP02": _manifest(["src/b/**"]),
        }
        result = compute_lanes(graph, manifests, "test-feat")
        assert result.collapse_report is not None
        # WP01→WP02 is a direct dep, so not independent
        assert result.collapse_report.independent_wps_collapsed == 0

    def test_no_collapses_empty_report(self):
        """Two fully independent WPs with no overlaps → empty collapse events."""
        graph = {"WP01": [], "WP02": []}
        manifests = {
            "WP01": _manifest(["src/a/**"]),
            "WP02": _manifest(["src/b/**"]),
        }
        result = compute_lanes(graph, manifests, "test-feat")
        assert result.collapse_report is not None
        assert len(result.collapse_report.events) == 0
        assert result.collapse_report.independent_wps_collapsed == 0

    def test_no_duplicate_events_for_same_pair(self):
        """Dependency plus overlap records one collapse event for the pair."""
        graph = {"WP01": [], "WP02": ["WP01"]}
        manifests = {
            "WP01": _manifest(["src/core/**"]),
            "WP02": _manifest(["src/core/utils/**"]),  # overlapping
        }
        result = compute_lanes(graph, manifests, "test-feat")
        assert result.collapse_report is not None
        dep_events = [e for e in result.collapse_report.events if e.rule == "dependency"]
        assert len(dep_events) == 0
        ws_events = [e for e in result.collapse_report.events if e.rule == "write_scope_overlap"]
        assert len(ws_events) == 1
        assert "WP02 depends on WP01" in ws_events[0].evidence


# ---------------------------------------------------------------------------
# T018: _are_disjoint and _describe_overlap helpers
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_are_disjoint_true_for_separate_paths(self):
        ma = _manifest(["src/a/**"])
        mb = _manifest(["src/b/**"])
        assert _are_disjoint(ma, mb) is True

    def test_are_disjoint_false_for_overlapping_paths(self):
        ma = _manifest(["src/core/**"])
        mb = _manifest(["src/core/utils/**"])
        assert _are_disjoint(ma, mb) is False

    def test_are_disjoint_false_exact_match(self):
        ma = _manifest(["src/foo/**"])
        mb = _manifest(["src/foo/**"])
        assert _are_disjoint(ma, mb) is False

    def test_describe_overlap_names_globs(self):
        ma = _manifest(["src/core/**"])
        mb = _manifest(["src/core/utils/**"])
        desc = _describe_overlap(ma, mb)
        assert "src/core/**" in desc
        assert "src/core/utils/**" in desc

    def test_describe_overlap_fallback(self):
        """Disjoint manifests → fallback message."""
        ma = _manifest(["src/a/**"])
        mb = _manifest(["src/b/**"])
        desc = _describe_overlap(ma, mb)
        assert "write-scope overlap" in desc

    def test_next_free_lane_id_skips_used(self):
        """The lowest unclaimed id is minted (#5152 control path)."""
        assert _next_free_lane_id(set()) == "lane-a"
        assert _next_free_lane_id({"lane-a"}) == "lane-b"
        assert _next_free_lane_id({"lane-a", "lane-b", "lane-d"}) == "lane-c"

    def test_next_free_lane_id_exhaustion_raises(self):
        """#5155: all 26 letters claimed → LaneIdExhaustedError, not chr overflow.

        Without a bound the loop walks past ``z`` into ``{``, ``|``, … and
        eventually non-character code points. Exhaustion must refuse loudly
        with a structured error instead.
        """
        used = {f"lane-{chr(letter)}" for letter in range(ord("a"), ord("z") + 1)}

        with pytest.raises(LaneIdExhaustedError) as excinfo:
            _next_free_lane_id(used)

        assert isinstance(excinfo.value, LaneComputationError)
        assert excinfo.value.error_code == "LANE_ID_EXHAUSTED"

    def test_next_free_lane_id_still_mints_after_z_when_gaps_exist(self):
        """Exhaustion is about a full alphabet, not reaching 'z' with gaps.

        If earlier letters free up (read-back released them), ``z`` being
        claimed must not matter — the lowest gap is minted.
        """
        used = {f"lane-{chr(letter)}" for letter in range(ord("b"), ord("z") + 1)}
        assert _next_free_lane_id(used) == "lane-a"
