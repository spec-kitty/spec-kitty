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
    HEAD with a STAGED DELETION and a persisted mid-merge resume state (#4997).

    Persists the SAME pre-mutation anchors real post-fix attempt-1 durably writes
    BEFORE it consolidates any lane (persist-before-mutate), so the resume is not
    fail-closed by the H4 baseless-consolidation guard — see the #4982 sibling."""
    from mission_runtime import MissionArtifactKind, resolve_placement_only
    from specify_cli.merge.reconciliation import write_post_fix_marker
    from specify_cli.merge.state import MergeState, save_state

    # --- pre-mutation anchors, captured BEFORE the simulated consolidation -----
    pre_mutation_coord_sha = mission.rev(mission.coord_branch)
    pre_mutation_coord_ref = resolve_placement_only(mission.repo, mission.slug, kind=MissionArtifactKind.STATUS_STATE).ref
    # Keyed EXACTLY as _capture_pre_interrupt_lane_tips keys it (lane_branch_name,
    # mid8 form == mission.lane_branch here); H3's lane_tip_cas_ok CAS-checks
    # refs/heads/<key>, so the key resolves to a real branch ref in this fixture.
    pre_interrupt_lane_tips = {mission.lane_branch(wp): mission.rev(mission.lane_branch(wp)) for wp in wp_order}

    coord_wt = _coord_worktree(mission)
    git(coord_wt, "merge", "-q", "--no-edit", mission.lane_branch(first_wp))

    state = MergeState(
        mission_id=mission.mission_id,
        mission_slug=mission.slug,
        target_branch=mission.target_branch,
        wp_order=list(wp_order),
    )
    state.completed_wps = [first_wp]
    state.current_wp = wp_order[1] if len(wp_order) > 1 else first_wp
    state.strategy = "merge"
    state.pre_mutation_coord_sha = pre_mutation_coord_sha
    state.pre_mutation_coord_ref = pre_mutation_coord_ref
    state.pre_interrupt_lane_tips = pre_interrupt_lane_tips
    save_state(state, mission.repo)
    # WP10 integration (FR-012): mark this as a POST-fix in-flight crash so the
    # resumed merge is not refused by the FR-012 legacy guard.
    write_post_fix_marker(mission.repo, mission.mission_id)

    # Primary checkout behind HEAD with a staged deletion (the #4997 window).
    git(mission.repo, "checkout", "-q", mission.target_branch)
    git(mission.repo, "rm", "-q", "--cached", "README.md")


@pytest.mark.xfail(
    strict=True,
    reason="#4997 RESIDUAL PRODUCT GAP (terminus-integration finding). The fixture "
    "now persists the SAME pre-mutation anchors real attempt-1 writes "
    "(pre_mutation_coord_sha/ref + pre_interrupt_lane_tips, persist-before-mutate), "
    "so this is NOT a fixture artifact: the resume clears H4/H3 and the "
    "reconciliation gate anchors to the pristine coord base — identical setup to "
    "the clean-window sibling #4982, which with these anchors now PASSES (merge "
    "exit 0, both pre-interrupt lane-tip SHAs preserved as ancestors of target). "
    "#4997 stays RED because its window is DIFFERENT: the primary checkout sits "
    "behind its own HEAD with a STAGED DELETION, which the resume classifies as "
    "LOCAL_CHANGES (the lane is not yet in the target HEAD), so the behind-own-HEAD "
    "preservation remedy does not fire and the already-merged lane's pre-interrupt "
    "commit SHA is not carried onto the target (R1 resume SHA-preservation over "
    "staged deletions). Follow-up: the resume-consolidation preservation fix must "
    "also cover the staged-deletion/LOCAL_CHANGES behind-HEAD window, not just the "
    "clean #4982 case. Data-loss-critical; NOT green-washed.",
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
