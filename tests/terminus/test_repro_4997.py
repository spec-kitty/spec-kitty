"""Repro #4997 — resume over a behind-own-HEAD primary must recover, not strand the merge.

Primary-site sibling of the closed #4982. The terminus consolidated every lane onto the
mission branch and advanced the target with ``git update-ref``, but the ``reset --hard``
that refreshes the primary checkout failed (index.lock) or was killed (#1826). The primary
(on the target branch) now sits behind its own already-advanced HEAD, so the mission's
integrated files read as STAGED DELETIONS. ``--resume`` must recognise this pure lag and
recover it (``git reset --hard HEAD``), continuing the merge so the approved code lands —
NOT abort (stranding the merge) nor advise a "Commit" that would delete the mission's code
from the target.

Contract postcondition 1: every approved WP's approved commit SHA must be reachable from
the target after resume. Recovery is gated on a phantom-only proof (the primary tree/index
are byte-identical to the persisted ``pre_mutation_target_sha``) so genuine local work is
never reset away — that safety guard lives in ``test_resume_phantom_only.py``.

RED-first: driven through the REAL ``spec-kitty merge --resume`` CLI (no ``_run_git`` /
subprocess mocking). The interrupted mid-merge git state (all lanes on coord, target
advanced via ``update-ref``, primary left behind its HEAD) + resume state are built with
real git and ``save_state`` — fixture setup, not a mock. Approved SHAs from lane-branch
tips (RN-Q3). Before the fix the resume aborted ``rc=1`` (advisory-only "reset --hard HEAD"
guidance), so the approved commits never landed.
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


def _interrupt_behind_own_head(mission: CoordMission, wp_order: list[str]) -> str:
    """Consolidate EVERY lane onto coord, advance the target ref with ``update-ref``, and
    leave the primary checkout BEHIND ITS OWN HEAD — the real #4997 window (#1826).

    The terminus consolidated all lanes onto the mission branch and advanced the target
    with ``git update-ref``, but the ``reset --hard`` that refreshes the primary checkout
    failed / was killed. So the primary (on ``target_branch``) now sits behind its own
    (already-advanced) HEAD: the mission's already-integrated files read as STAGED
    DELETIONS. No ``git rm`` is needed — that IS what an un-refreshed ``update-ref`` leaves.

    Persists the SAME pre-mutation anchors real post-fix attempt-1 durably writes BEFORE it
    consolidates any lane (persist-before-mutate) — crucially ``pre_mutation_target_sha``
    (the pre-advance target tip the phantom-only recovery proof anchors to) plus the
    coord/lane-tip anchors that clear the H4/H3 resume guards. Returns the advanced target
    SHA for assertions.
    """
    from mission_runtime import MissionArtifactKind, resolve_placement_only
    from specify_cli.merge.reconciliation import write_post_fix_marker
    from specify_cli.merge.state import MergeState, save_state

    # --- pre-mutation anchors, captured BEFORE the simulated consolidation/advance -----
    pre_mutation_target_sha = mission.rev(mission.target_branch)  # pre-advance target tip
    pre_mutation_coord_sha = mission.rev(mission.coord_branch)
    pre_mutation_coord_ref = resolve_placement_only(mission.repo, mission.slug, kind=MissionArtifactKind.STATUS_STATE).ref
    # Keyed EXACTLY as _capture_pre_interrupt_lane_tips keys it (lane_branch_name,
    # mid8 form == mission.lane_branch here); H3's lane_tip_cas_ok CAS-checks
    # refs/heads/<key>, so the key resolves to a real branch ref in this fixture.
    pre_interrupt_lane_tips = {mission.lane_branch(wp): mission.rev(mission.lane_branch(wp)) for wp in wp_order}

    # Consolidate EVERY lane onto the coordination (mission) branch, as the interrupted
    # terminus did before it advanced the target.
    coord_wt = _coord_worktree(mission)
    for wp in wp_order:
        git(coord_wt, "merge", "-q", "--no-edit", mission.lane_branch(wp))
    advanced_sha = mission.rev(mission.coord_branch)

    state = MergeState(
        mission_id=mission.mission_id,
        mission_slug=mission.slug,
        target_branch=mission.target_branch,
        wp_order=list(wp_order),
    )
    state.completed_wps = list(wp_order)
    state.current_wp = wp_order[-1]
    state.strategy = "merge"
    state.pre_mutation_target_sha = pre_mutation_target_sha
    state.pre_mutation_coord_sha = pre_mutation_coord_sha
    state.pre_mutation_coord_ref = pre_mutation_coord_ref
    state.pre_interrupt_lane_tips = pre_interrupt_lane_tips
    save_state(state, mission.repo)
    # WP10 integration (FR-012): mark this as a POST-fix in-flight crash so the
    # resumed merge is not refused by the FR-012 legacy guard.
    write_post_fix_marker(mission.repo, mission.mission_id)

    # Advance the target ref (update-ref) but DO NOT reset the primary checkout: it now
    # sits behind its own HEAD, the mission's files reading as staged deletions (#1826 /
    # the killed reset --hard) — the real #4997 window.
    git(mission.repo, "checkout", "-q", mission.target_branch)
    git(mission.repo, "update-ref", f"refs/heads/{mission.target_branch}", advanced_sha)
    return advanced_sha


def test_4997_resume_over_staged_deletions_does_not_revert_merge(tmp_path: Path) -> None:
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8="01M4997A")
    approved = mission.approved_shas_from_lane_tips(["WP01", "WP02"])  # PRE-resume tips
    _interrupt_behind_own_head(mission, ["WP01", "WP02"])

    result = run_terminus(mission, ["merge", "--resume", "--yes"])

    assert result.returncode == 0, (
        f"merge --resume over a pure behind-own-HEAD primary must recover and exit 0, got "
        f"rc={result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    for wp_id, shas in approved.items():
        for sha in shas:
            assert sha_reachable(mission.repo, sha, mission.target_branch), (
                f"approved {wp_id} commit {sha[:10]} is NOT reachable from "
                f"{mission.target_branch} after --resume over staged deletions — the "
                f"already-merged lane was reverted (#4997)"
            )
