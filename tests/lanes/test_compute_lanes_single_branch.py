"""``compute_lanes(topology=single_branch)`` unit coverage (#5100 IC-03 / WP05 T022).

Contract (``contracts/single-branch-execution.md``, "Finalize"): a
``single_branch`` mission's manifest holds exactly ONE lane --
``lane_id == PLANNING_LANE_ID`` -- containing EVERY work package (code and
planning alike), in dependency order. Every other topology's output is
UNCHANGED (golden-compared against the pre-WP05 default call shape).
"""

from __future__ import annotations

import pytest

from mission_runtime import MissionTopology

from specify_cli.lanes.compute import PLANNING_LANE_ID, compute_lanes
from specify_cli.ownership.models import OwnershipManifest, WorkProductKind

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _code_manifest(*owned: str) -> OwnershipManifest:
    return OwnershipManifest(
        execution_mode=WorkProductKind.CODE_CHANGE,
        owned_files=owned,
        authoritative_surface=owned[0],
    )


def _planning_manifest() -> OwnershipManifest:
    return OwnershipManifest(
        execution_mode=WorkProductKind.PLANNING_ARTIFACT,
        owned_files=(),
        authoritative_surface="kitty-specs/",
    )


class TestSingleBranchManifestShape:
    def test_one_repo_root_lane_holds_every_wp_in_dependency_order(self) -> None:
        manifest = compute_lanes(
            dependency_graph={"WP01": [], "WP02": ["WP01"]},
            ownership_manifests={
                "WP01": _code_manifest("src/wp01.py"),
                "WP02": _code_manifest("src/wp02.py"),
            },
            mission_slug="single-branch-test",
            target_branch="issue-5100-single-branch-topology",
            topology=MissionTopology.SINGLE_BRANCH,
        )

        assert len(manifest.lanes) == 1
        lane = manifest.lanes[0]
        assert lane.lane_id == PLANNING_LANE_ID
        assert lane.wp_ids == ("WP01", "WP02")
        assert lane.depends_on_lanes == ()
        assert lane.parallel_group == 0
        assert manifest.target_branch == "issue-5100-single-branch-topology"

    def test_reverse_declaration_order_still_yields_dependency_order(self) -> None:
        """Non-vacuity: the lane's WP order is DERIVED from the dependency
        graph, not from dict insertion order."""
        manifest = compute_lanes(
            dependency_graph={"WP02": ["WP01"], "WP01": []},
            ownership_manifests={
                "WP02": _code_manifest("src/wp02.py"),
                "WP01": _code_manifest("src/wp01.py"),
            },
            mission_slug="single-branch-test",
            target_branch="main",
            topology=MissionTopology.SINGLE_BRANCH,
        )

        assert manifest.lanes[0].wp_ids == ("WP01", "WP02")

    def test_mixed_planning_and_code_wps_share_the_one_lane(self) -> None:
        manifest = compute_lanes(
            dependency_graph={"WP01": [], "WP02": ["WP01"]},
            ownership_manifests={
                "WP01": _planning_manifest(),
                "WP02": _code_manifest("src/wp02.py"),
            },
            mission_slug="single-branch-test",
            target_branch="main",
            topology=MissionTopology.SINGLE_BRANCH,
        )

        assert len(manifest.lanes) == 1
        assert manifest.lanes[0].wp_ids == ("WP01", "WP02")
        # planning_artifact_wps stays KIND-derived (WP05 note): only WP01,
        # even though BOTH WPs share the one lane.
        assert manifest.planning_artifact_wps == ["WP01"]

    def test_missing_ownership_manifest_raises(self) -> None:
        from specify_cli.lanes.compute import LaneComputationError

        with pytest.raises(LaneComputationError):
            compute_lanes(
                dependency_graph={"WP01": []},
                ownership_manifests={},
                mission_slug="single-branch-test",
                target_branch="main",
                topology=MissionTopology.SINGLE_BRANCH,
            )


class TestSingleBranchMissionBranchFallback:
    def test_mission_branch_falls_back_to_target_branch_when_unset(self) -> None:
        manifest = compute_lanes(
            dependency_graph={"WP01": []},
            ownership_manifests={"WP01": _code_manifest("src/wp01.py")},
            mission_slug="single-branch-test",
            target_branch="issue-5100-single-branch-topology",
            topology=MissionTopology.SINGLE_BRANCH,
            mission_branch=None,
        )

        assert manifest.mission_branch == "issue-5100-single-branch-topology"

    def test_mission_branch_honors_meta_mission_branch_when_set(self) -> None:
        """A protected-target single_branch mission's minted branch (WP08 /
        IC-05) wins over ``target_branch``."""
        manifest = compute_lanes(
            dependency_graph={"WP01": []},
            ownership_manifests={"WP01": _code_manifest("src/wp01.py")},
            mission_slug="single-branch-test",
            target_branch="main",
            topology=MissionTopology.SINGLE_BRANCH,
            mission_branch="kitty/mission-single-branch-test-01abcdef",
        )

        assert manifest.mission_branch == "kitty/mission-single-branch-test-01abcdef"


class TestOtherTopologiesUnchanged:
    """Non-vacuity control: every non-SINGLE_BRANCH topology produces a
    manifest BYTE-IDENTICAL (sans ``computed_at``) to a LITERAL expected
    manifest captured from the pre-WP05 base (commit ``cfb75bc4``, before
    ``compute_lanes`` took a ``topology`` kwarg at all) for this exact
    fixture graph -- via ``PYTHONPATH=<cfb75bc4 worktree>/src`` calling
    ``compute_lanes`` with no ``topology`` argument and serializing
    ``manifest.to_dict()`` (``computed_at`` stripped).

    Review cycle 1, Issue 2: the prior version compared the CURRENT code's
    no-``topology`` default call (also ``LANES``) against the CURRENT
    code's explicit ``topology=LANES`` call -- both post-WP05, so nothing
    was ever compared against pre-WP05 behaviour. This literal closes that
    gap: it can only pass if the union-find/lane-id-assignment/mission-
    branch-naming algorithm for every non-SINGLE_BRANCH topology is
    UNCHANGED byte-for-byte from before WP05 touched this file.
    """

    _DEPENDENCY_GRAPH = {"WP01": [], "WP02": ["WP01"], "WP03": []}
    _OWNERSHIP = {
        "WP01": _code_manifest("src/a.py"),
        "WP02": _code_manifest("src/b.py"),
        "WP03": _code_manifest("docs/readme.md"),
    }

    # Captured verbatim from cfb75bc4 (git worktree add + PYTHONPATH=.../src
    # python -c '... compute_lanes(dependency_graph=_DEPENDENCY_GRAPH,
    # ownership_manifests=_OWNERSHIP, mission_slug="golden-fixture",
    # target_branch="main").to_dict()', computed_at stripped).
    _EXPECTED_PRE_WP05_MANIFEST: dict[str, object] = {
        "version": 1,
        "mission_slug": "golden-fixture",
        "mission_id": None,
        "mission_branch": "kitty/mission-golden-fixture",
        "target_branch": "main",
        "lanes": [
            {
                "lane_id": "lane-a",
                "wp_ids": ["WP01"],
                "write_scope": ["src/a.py"],
                "predicted_surfaces": [],
                "depends_on_lanes": [],
                "parallel_group": 0,
            },
            {
                "lane_id": "lane-c",
                "wp_ids": ["WP03"],
                "write_scope": ["docs/readme.md"],
                "predicted_surfaces": [],
                "depends_on_lanes": [],
                "parallel_group": 0,
            },
            {
                "lane_id": "lane-b",
                "wp_ids": ["WP02"],
                "write_scope": ["src/b.py"],
                "predicted_surfaces": [],
                "depends_on_lanes": ["lane-a"],
                "parallel_group": 1,
            },
        ],
        "computed_from": "dependency_graph+ownership",
        "planning_artifact_wps": [],
        "planning_commit_sha": None,
    }

    @staticmethod
    def _sans_timestamp(manifest: object) -> dict[str, object]:
        d = dict(manifest.to_dict())  # type: ignore[attr-defined]
        d.pop("computed_at", None)
        return d

    def test_lanes_topology_matches_the_pinned_pre_wp05_manifest(self) -> None:
        actual = compute_lanes(
            dependency_graph=self._DEPENDENCY_GRAPH,
            ownership_manifests=self._OWNERSHIP,
            mission_slug="golden-fixture",
            target_branch="main",
            topology=MissionTopology.LANES,
        )

        assert self._sans_timestamp(actual) == self._EXPECTED_PRE_WP05_MANIFEST

    @pytest.mark.parametrize("topology", [MissionTopology.COORD, MissionTopology.LANES_WITH_COORD])
    def test_coord_topologies_match_the_pinned_pre_wp05_manifest(self, topology: MissionTopology) -> None:
        actual = compute_lanes(
            dependency_graph=self._DEPENDENCY_GRAPH,
            ownership_manifests=self._OWNERSHIP,
            mission_slug="golden-fixture",
            target_branch="main",
            topology=topology,
        )

        assert self._sans_timestamp(actual) == self._EXPECTED_PRE_WP05_MANIFEST
