"""Repro #4982 — a resumed merge fails to preserve the already-merged lane commit.

Mechanism (DEBRIEF §4, root R1): the forward ref advance is non-CAS
(``git/ref_advance.py`` 2-arg ``update-ref``) and ``update-ref`` + ``reset --hard``
are two unlinked steps, so after an interrupted merge the checkout can sit behind
its own HEAD; ``--resume`` then re-consolidates and the already-merged lane's
committed identity is lost (the "Commit" remedy reverts it) rather than being
preserved. Backstopped by S-A (real CAS advance) + a behind-HEAD sentinel +
tree-equality integration check (WP06/WP02/WP09).

Contract postcondition 1 demands every approved WP's approved commit SHA be
reachable from the target. A CLEAN ``--strategy merge`` merge achieves that; the
RESUMED path does not — the interrupted lane's commit is no longer reachable by
SHA from the target after resume.

RED-first: driven through the REAL ``spec-kitty merge --resume`` CLI (no
``_run_git`` / subprocess mocking). The interrupted mid-merge git state (coord
already carrying the WP01 lane, target behind) + resume state are built with real
git and ``save_state`` — fixture setup, not a mock. Approved SHAs from lane-branch
tips (RN-Q3). Today the approved SHA is not reachable after resume →
``xfail(strict=True)``.
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
    listing = git_out(mission.repo, "worktree", "list")
    for line in listing.splitlines():
        path = line.split()[0]
        if "coord" in path:
            return Path(path)
    raise AssertionError("coordination worktree not found")


def _interrupt_after_first_lane(mission: CoordMission, first_wp: str, wp_order: list[str]) -> None:
    """Advance coord to carry *first_wp*'s lane, then persist a mid-merge resume state.

    Mirrors a crash AFTER the first lane consolidated but BEFORE the mission
    branch reached the target — the exact behind-HEAD window (#4982)."""
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
    # WP10 integration (FR-012): stamp the post-fix reconciliation marker so the
    # resumed merge is treated as a POST-fix in-flight crash (the fixture models a
    # crash AFTER the terminus reconciliation gate landed), not a pre-fix legacy
    # state the FR-012 guard would refuse. ``canonical_id`` == ``mission_id``.
    write_post_fix_marker(mission.repo, mission.mission_id)
    git(mission.repo, "checkout", "-q", mission.target_branch)


@pytest.mark.xfail(
    strict=True,
    reason="#4982 RESIDUAL GAP (WP10 finding): with the FR-012 post-fix marker now "
    "stamped, the resume no longer refuses and the reconciliation gate PASSES — but "
    "the gate's claim is computed relative to the RESUME-START coord checkpoint "
    "(which already contains the interrupted lane-a merge), so WP01's set is empty "
    "and trivially satisfied. The PRE-resume lane-tip SHA the test captured is NOT "
    "preserved onto the target after the resume re-consolidates (R1 resume SHA-"
    "preservation). The already-integrated lane's exact commit identity is lost. "
    "Follow-up (resume consolidation must preserve pre-interrupt lane-tip SHAs).",
)
def test_4982_resume_preserves_already_merged_lane_commit(tmp_path: Path) -> None:
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8="01M4982A")
    approved = mission.approved_shas_from_lane_tips(["WP01", "WP02"])  # PRE-resume tips
    _interrupt_after_first_lane(mission, "WP01", ["WP01", "WP02"])

    run_terminus(mission, ["merge", "--resume", "--yes"])

    # Contract postcondition 1: every approved WP commit reachable by SHA from target.
    # The already-merged WP01 lane commit must survive the resume, not be reverted.
    for wp_id, shas in approved.items():
        for sha in shas:
            assert sha_reachable(mission.repo, sha, mission.target_branch), (
                f"approved {wp_id} commit {sha[:10]} is NOT reachable from "
                f"{mission.target_branch} after --resume — the already-merged lane was "
                f"reverted / its identity lost (#4982)"
            )
