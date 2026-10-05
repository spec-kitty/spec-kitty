"""Two-lane, fully approved missions for the "content after approval" scenarios (#5668).

A mission has two independent code lanes: ``WP01`` on ``lane-a`` and ``WP02`` on
``lane-b``. Both work packages are implemented, reviewed and approved through the
production transactional status shell
(:func:`tests.terminus.mixed_lane_support.transition`), so every ``lane_head``
stamp comes from ``probe_lane_head`` and never from a hand-written event. The
lane branches are cut and the lane worktrees allocated by the real
``allocate_lane_worktree``.

Two topologies, one builder each:

* ``"coord"`` -- :func:`build_post_approval_mission` delegates to the
  allocator-faithful coordination builder
  (:func:`tests.terminus.canceled_dependency_support.build_canceled_dependency_mission`
  with independent lanes and both work packages approved).
* ``"lanes"`` -- the same scenario with no coordination branch; the mission
  branch is the claim base and the status log lives on the target checkout.

Helpers (all take the :class:`~tests.terminus.conftest.CoordMission` the builder
returned and work on either topology):

* :func:`add_post_approval_commit` -- one more content commit on a lane branch,
  after review approved it (the defect of #5668).
* :func:`strip_approval_stamps` -- turn a work package into a legacy approval that
  carries no ``lane_head`` stamp.
* :func:`rework_and_reapprove` -- move a work package back for review, change its
  lane, and approve it again, so its newest approval stamp names the new tip.

Known gap: no harness drives ``implement`` and the review transitions through the
CLI end to end. The transitions run through the in-process production shell; the
consolidation that follows is a real subprocess (``run_terminus``).

This module is FROZEN once the work package that created it is approved: later work
packages import it and must not edit it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from specify_cli.lanes.branch_naming import mission_branch_name
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import read_lanes_json, write_lanes_json
from specify_cli.lanes.worktree_allocator import allocate_lane_worktree, predict_lane_worktree
from tests.terminus import lanes_fixture
from tests.terminus.canceled_dependency_support import (
    ACTOR,
    LANE_A,
    LANE_B,
    _approve,
    _commit_in,
    build_canceled_dependency_mission,
    strip_lane_head_stamps,
)
from tests.terminus.conftest import CoordMission, _git, _now_iso, _STATUS_EVENTS_FILENAME
from tests.terminus.mixed_lane_support import transition

Topology = Literal["lanes", "coord"]

WP01_PATH = "src/pkg/wp01.py"
WP02_PATH = "src/pkg/wp02.py"
LATE_PATH = "src/alpha/late.py"
LATE_CONTENT = "UNREVIEWED = True\n"
REWORK_PATH = "src/pkg/wp01_rework.py"
REWORK_CONTENT = "REWORKED = True\n"

_LANE_OF_WP = {"WP01": LANE_A, "WP02": LANE_B}
_COORD_MID8 = "01M56680"
_LANES_MID8 = "01M5668L"


def _lane_manifest(slug: str, mission_id: str, mission_branch: str, target_branch: str) -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=slug,
        mission_id=mission_id,
        mission_branch=mission_branch,
        target_branch=target_branch,
        lanes=[
            ExecutionLane(
                lane_id=lane_id,
                wp_ids=(wp,),
                write_scope=("src/pkg",),
                predicted_surfaces=("code",),
                depends_on_lanes=(),
                parallel_group=0,
            )
            for lane_id, wp in ((LANE_A, "WP01"), (LANE_B, "WP02"))
        ],
        computed_at=_now_iso(),
        computed_from="terminus-post-approval-fixture",
    )


def _wp_file(wp: str) -> str:
    return f"---\nwork_package_id: {wp}\ntitle: {wp} work\ndependencies: []\nsubtasks: []\n---\n# {wp}\n"


def build_post_approval_coord_mission(tmp_path: Path, *, mid8: str = _COORD_MID8, target_branch: str = "main") -> CoordMission:
    """Coordination topology: two independent lanes, both work packages approved."""
    built = build_canceled_dependency_mission(tmp_path, wp01_final="approved", depends=False, mid8=mid8, target_branch=target_branch)
    return built.mission


def build_post_approval_lanes_mission(tmp_path: Path, *, mid8: str = _LANES_MID8, target_branch: str = "develop") -> CoordMission:
    """LANES topology (no coordination branch): two independent lanes, both approved."""
    mid8 = mid8.upper()
    mission_id = (mid8 + "0" * 26)[:26]
    slug = f"terminus-{mid8}"
    mission_branch = mission_branch_name(slug, mission_id=mission_id)
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    mission = CoordMission(
        repo=repo,
        home=home,
        feature_dir=repo / "kitty-specs" / slug,
        slug=slug,
        mission_id=mission_id,
        mid8=mid8,
        coord_branch=mission_branch,
        target_branch=target_branch,
    )
    lanes_fixture._init_repo(repo, target_branch)
    (repo / ".gitignore").write_text(".worktrees/\n", encoding="utf-8")
    (mission.feature_dir / "tasks").mkdir(parents=True)
    lanes_fixture._write_meta(mission, target_branch)
    manifest = _lane_manifest(slug, mission_id, mission_branch, target_branch)
    write_lanes_json(mission.feature_dir, manifest)
    for wp in ("WP01", "WP02"):
        (mission.feature_dir / "tasks" / f"{wp}-work.md").write_text(_wp_file(wp), encoding="utf-8")
    (mission.feature_dir / _STATUS_EVENTS_FILENAME).write_text("", encoding="utf-8")
    _git(repo, "add", ".gitignore", f"kitty-specs/{slug}")
    _git(repo, "commit", "-qm", f"chore({slug}): bootstrap post-approval lanes mission")
    _git(repo, "branch", mission_branch)
    manifest = read_lanes_json(mission.feature_dir) or manifest

    trees = {wp: allocate_lane_worktree(repo, slug, wp, manifest) for wp in ("WP01", "WP02")}
    for wp, path in (("WP01", WP01_PATH), ("WP02", WP02_PATH)):
        for lane in ("planned", "claimed", "in_progress"):
            transition(mission, wp, lane, actor=ACTOR)
        tree, branch = trees[wp]
        _commit_in(tree, path, f"def {wp.lower()}() -> int:\n    return 1\n", f"feat({slug}): {wp} work")
        _approve(mission, wp, reference=f"review-{wp}")
        mission.lane_branches[wp] = branch
    return mission


def build_post_approval_mission(tmp_path: Path, topology: Topology) -> CoordMission:
    """The two-lane, fully approved mission of *topology* (``"lanes"`` or ``"coord"``)."""
    if topology == "coord":
        return build_post_approval_coord_mission(tmp_path)
    return build_post_approval_lanes_mission(tmp_path)


def lane_worktree(mission: CoordMission, lane: str) -> Path:
    """The allocator's worktree path for *lane* (``"lane-a"`` / ``"lane-b"``)."""
    path: Path
    path, _branch = predict_lane_worktree(mission.repo, mission.slug, lane)
    return path


def add_post_approval_commit(mission: CoordMission, lane: str = LANE_A, path: str = LATE_PATH, content: str = LATE_CONTENT) -> str:
    """Commit *content* at *path* on *lane*'s branch, after review approved it; return the new SHA."""
    return _commit_in(lane_worktree(mission, lane), path, content, f"feat({mission.slug}): unreviewed late change on {lane}")


def strip_approval_stamps(mission: CoordMission, wp_id: str) -> None:
    """Make *wp_id* a legacy approval: drop ``policy_metadata.lane_head`` from all of its events."""
    strip_lane_head_stamps(mission, wp_id)


def rework_and_reapprove(mission: CoordMission, wp_id: str = "WP01") -> str:
    """Reject *wp_id*, change its lane, then approve it again; return the re-approved lane tip.

    The lane gains one content commit (:data:`REWORK_PATH`) after the first approval and
    before the second, so the newest approval stamp is the new tip and the first one is
    an ancestor of it.
    """
    lane = _LANE_OF_WP[wp_id]
    transition(mission, wp_id, "in_progress", actor=ACTOR, review_ref=f"review-{wp_id}-rejected")
    tip = _commit_in(lane_worktree(mission, lane), REWORK_PATH, REWORK_CONTENT, f"feat({mission.slug}): {wp_id} rework")
    _approve(mission, wp_id, reference=f"review-{wp_id}-rework")
    return tip
