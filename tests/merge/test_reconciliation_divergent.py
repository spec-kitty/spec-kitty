"""Claim tests over the US1 divergent lane-naming shapes (#5108).

Drives the pre-existing entry point ``build_approved_wp_set`` over each of the
four divergent shapes from :mod:`tests.merge._divergent_shapes`, guarding
against the #5108 defect (the claim reading a name composed from
``mission_id`` instead of the lane's *created* branch).

Every shape is built through the real allocator (:mod:`tests.merge._divergent_shapes`)
— no lane branch is ever hand-composed here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.merge import git_probes
from specify_cli.merge.reconciliation import build_approved_wp_set

from ._divergent_shapes import DIVERGENT_SHAPE_BUILDERS, DivergentMission

pytestmark = [pytest.mark.git_repo]


@pytest.fixture(params=sorted(DIVERGENT_SHAPE_BUILDERS))
def shape_name(request: pytest.FixtureRequest) -> str:
    name: str = request.param
    return name


@pytest.fixture
def divergent_mission(shape_name: str, tmp_path: Path) -> DivergentMission:
    return DIVERGENT_SHAPE_BUILDERS[shape_name](tmp_path)


def test_claim_attributes_each_approved_lane(divergent_mission: DivergentMission) -> None:
    """US1 AS1: the claim attributes commits for the approved lane, regardless
    of how divergent the mission's slug/mission_id combination is."""
    mission = divergent_mission
    claim = build_approved_wp_set(
        mission.repo_root,
        mission.feature_dir,
        mission.manifest,
        coord_base_ref=mission.coord_base_sha,
    )
    assert claim.refusal is None
    approved_wp_ids = {wp for lane in mission.manifest.lanes for wp in lane.wp_ids}
    assert set(claim.approved) == approved_wp_ids
    for lane in mission.manifest.lanes:
        _, branch = mission.lanes[lane.lane_id]
        expected = set(git_probes.commits_in_range(mission.repo_root, mission.coord_base_sha, branch))
        assert expected, f"lane {lane.lane_id} carried no commit to attribute"
        for wp_id in lane.wp_ids:
            assert set(claim.approved[wp_id]) == expected


def test_canceled_lane_excluded_survivor_attributed(shape_name: str, tmp_path: Path) -> None:
    """US1 AS2: a canceled lane's commits are excluded while the survivor lane
    in the same mission is still attributed."""
    mission = DIVERGENT_SHAPE_BUILDERS[shape_name](tmp_path, with_canceled_lane=True)
    canceled_lane = mission.manifest.lane_for_wp("WP02")
    assert canceled_lane is not None
    canceled_wp_ids = frozenset(canceled_lane.wp_ids)
    claim = build_approved_wp_set(
        mission.repo_root,
        mission.feature_dir,
        mission.manifest,
        coord_base_ref=mission.coord_base_sha,
        excluded_canceled_wp_ids=canceled_wp_ids,
    )
    assert claim.refusal is None
    assert "WP01" in claim.approved
    assert set(claim.approved["WP01"])
    assert "WP02" not in claim.approved

    _, canceled_branch = mission.lanes["lane-b"]
    excluded = set(git_probes.commits_in_range(mission.repo_root, mission.coord_base_sha, canceled_branch))
    assert excluded
    assert excluded <= claim.excluded_shas


def test_missing_created_branch_refuses_by_name(shape_name: str, tmp_path: Path) -> None:
    """US1 AS3: an approved lane whose created branch was removed produces a
    NAMED refusal (lane id + the created branch), never an empty commit set."""
    mission = DIVERGENT_SHAPE_BUILDERS[shape_name](tmp_path, delete_created_branch_of="lane-a")
    _, deleted_branch = mission.lanes["lane-a"]

    claim = build_approved_wp_set(
        mission.repo_root,
        mission.feature_dir,
        mission.manifest,
        coord_base_ref=mission.coord_base_sha,
    )
    assert claim.refusal is not None
    assert "lane-a" in claim.refusal
    assert deleted_branch in claim.refusal


def test_provenance_canceled_lane_missing_branch_is_exempt(shape_name: str, tmp_path: Path) -> None:
    """The ``all(wp in excluded_canceled_wp_ids ...)`` guard in
    ``_unresolvable_approved_lane_branches`` is the ONLY thing distinguishing a
    provenance-canceled lane (still ``approved`` in the status snapshot, but
    excluded by the caller) from a genuinely orphaned approved lane. lane-b is
    ``approved`` in the snapshot AND has had its created branch deleted AND is
    passed as provenance-canceled via ``excluded_canceled_wp_ids`` — the claim
    must NOT refuse, and the survivor lane-a must still be attributed (US1 AS2).

    Deleting the guard makes this test fail: ``_lane_is_approved`` alone still
    counts lane-b (it genuinely IS approved), so an unguarded check would treat
    its missing branch as an unattributable refusal."""
    mission = DIVERGENT_SHAPE_BUILDERS[shape_name](
        tmp_path,
        with_canceled_lane=True,
        canceled_lane_status="approved",
        delete_created_branch_of="lane-b",
    )
    canceled_lane = mission.manifest.lane_for_wp("WP02")
    assert canceled_lane is not None
    claim = build_approved_wp_set(
        mission.repo_root,
        mission.feature_dir,
        mission.manifest,
        coord_base_ref=mission.coord_base_sha,
        excluded_canceled_wp_ids=frozenset(canceled_lane.wp_ids),
    )
    assert claim.refusal is None
    assert "WP01" in claim.approved
    assert set(claim.approved["WP01"])


def test_planning_lane_exempt_from_missing_branch_check(shape_name: str, tmp_path: Path) -> None:
    """A ``lane-planning`` lane is never checked for created-branch existence
    (I-3) — it resolves to the planning base branch, not a
    ``kitty/mission-...`` branch, so the strict branch-existence check must skip it
    unconditionally, regardless of how divergent the mission's slug/mission_id
    combination is."""
    mission = DIVERGENT_SHAPE_BUILDERS[shape_name](tmp_path, with_planning_lane=True)
    planning_lane = next(lane for lane in mission.manifest.lanes if lane.lane_id == "lane-planning")
    claim = build_approved_wp_set(
        mission.repo_root,
        mission.feature_dir,
        mission.manifest,
        coord_base_ref=mission.coord_base_sha,
    )
    assert claim.refusal is None
    for wp_id in planning_lane.wp_ids:
        assert wp_id in claim.approved


def test_authored_blobs_present_for_divergent_shape(divergent_mission: DivergentMission) -> None:
    """The authored-blob spine consumer (``_collect_authored``) is exercised
    for every divergent shape, not just the canonical naming case."""
    mission = divergent_mission
    claim = build_approved_wp_set(
        mission.repo_root,
        mission.feature_dir,
        mission.manifest,
        coord_base_ref=mission.coord_base_sha,
    )
    assert claim.refusal is None
    assert claim.authored_blobs
