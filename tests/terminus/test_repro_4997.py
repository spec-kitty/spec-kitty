"""Repro #4997 — resume over staged deletions reverts an already-merged lane.

Primary-site sibling of #4982 (DEBRIEF §4, root R1): after an interrupted merge the
primary checkout can sit behind its own HEAD with staged deletions; ``--resume``
then advises/enacts a "Commit" that reverts the already-merged lane rather than
recognizing the lane as already integrated. Backstopped by S-A (real CAS advance)
+ a behind-HEAD sentinel + tree-equality integration check (WP06/WP02/WP09).

Contract postcondition 1: every approved WP's approved commit SHA must be reachable
from the target. A resume that reverts the already-merged lane violates it.

RED-first: driven through the REAL ``spec-kitty merge --resume`` CLI (no
``_run_git`` / subprocess mocking). The interrupted mid-merge git state (coord
already carrying the WP01 lane, primary behind with a staged deletion) + resume
state are built with real git and ``save_state`` — fixture setup, not a mock.
Approved SHAs from lane-branch tips (RN-Q3). Today the already-merged lane commit
is not reachable from the target after resume → ``xfail(strict=True)``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.terminus.conftest import (
    CoordMission,
    build_coord_mission,
    run_terminus,
    sha_reachable,
)
from tests.terminus.conftest import _git as git
from tests.terminus.conftest import _git_out as git_out

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _coord_worktree(mission: CoordMission) -> Path:
    for line in git_out(mission.repo, "worktree", "list").splitlines():
        path = line.split()[0]
        if "coord" in path:
            return Path(path)
    raise AssertionError("coordination worktree not found")


def _interrupt_with_staged_deletion(mission: CoordMission, first_wp: str, wp_order: list[str]) -> None:
    """Consolidate the first lane onto coord, then leave the primary checkout behind
    HEAD with a STAGED DELETION and a persisted mid-merge resume state (#4997)."""
    coord_wt = _coord_worktree(mission)
    git(coord_wt, "merge", "-q", "--no-edit", mission.lane_branch(first_wp))

    from specify_cli.merge.reconciliation import write_post_fix_marker
    from specify_cli.merge.state import MergeState, save_state

    state = MergeState(
        mission_id=mission.mission_id,
        mission_slug=mission.slug,
        target_branch=mission.target_branch,
        wp_order=list(wp_order),
    )
    state.completed_wps = [first_wp]
    state.current_wp = wp_order[1] if len(wp_order) > 1 else first_wp
    state.strategy = "merge"
    save_state(state, mission.repo)
    # WP10 integration (FR-012): mark this as a POST-fix in-flight crash so the
    # resumed merge is not refused by the FR-012 legacy guard.
    write_post_fix_marker(mission.repo, mission.mission_id)

    # Primary checkout behind HEAD with a staged deletion (the #4997 window).
    git(mission.repo, "checkout", "-q", mission.target_branch)
    git(mission.repo, "rm", "-q", "--cached", "README.md")


@pytest.mark.xfail(
    strict=True,
    reason="#4997 RESIDUAL GAP (WP10 finding): with the FR-012 post-fix marker now "
    "stamped the resume proceeds past the legacy guard, but the primary-site "
    "sibling of #4982 remains — the resume over the staged-deletion / behind-HEAD "
    "window does not preserve the already-merged lane's pre-interrupt commit SHA "
    "onto the target (R1 resume SHA-preservation). The WP10 behind-own-HEAD remedy "
    "classifier is wired for the advisory path, but the checkout here classifies as "
    "LOCAL_CHANGES (the lane is not yet in the target HEAD), so the deeper resume-"
    "consolidation preservation fix is still needed. Follow-up.",
)
def test_4997_resume_over_staged_deletions_does_not_revert_merge(tmp_path: Path) -> None:
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8="01M4997A")
    approved = mission.approved_shas_from_lane_tips(["WP01", "WP02"])  # PRE-resume tips
    _interrupt_with_staged_deletion(mission, "WP01", ["WP01", "WP02"])

    run_terminus(mission, ["merge", "--resume", "--yes"])

    for wp_id, shas in approved.items():
        for sha in shas:
            assert sha_reachable(mission.repo, sha, mission.target_branch), (
                f"approved {wp_id} commit {sha[:10]} is NOT reachable from "
                f"{mission.target_branch} after --resume over staged deletions — the "
                f"already-merged lane was reverted (#4997)"
            )
