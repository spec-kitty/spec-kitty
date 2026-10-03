"""Repro #5571 — ``consolidate --resume`` must refresh a coordination worktree that only lags.

Coordination-worktree sibling of the closed #4982 / #4997. The terminus consolidated every
lane onto the mission (coordination) branch and advanced it with ``git update-ref``, but the
refresh of the coordination WORKTREE never ran (killed / ``index.lock``). The coordination
worktree now sits behind its own, already-advanced HEAD: every lane's integrated file reads
as a STAGED DELETION. Before the fix ``--resume`` refused with ``MERGE_UNSAFE_WORKTREE_DIRTY``
and the generic "Commit, stash, or revert" remedy — advice that, followed, records the
deletions and reverts the integrated lanes (the rc5 #4982 fix assumed only the repository root
checkout can lag; ``test_repro_4982.py`` merges INSIDE the coordination worktree, which leaves
it clean).

Expected behaviour:

* a PURE lag (worktree and index byte-identical to the persisted ``pre_mutation_coord_sha``)
  is refreshed in place on ``--resume`` and the consolidation completes with every approved
  lane's content on the target;
* a lag that carries a GENUINE edit is NOT reset: ``--resume`` refuses non-zero, the edit is
  preserved, and the output never advises committing the staged deletions.

Driven through the REAL ``spec-kitty consolidate --resume`` CLI (no ``_run_git`` /
subprocess mocking). The interrupted git state is real git plus ``save_state`` — fixture
setup, not a mock.
"""

from __future__ import annotations

import subprocess
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

_WPS = ["WP01", "WP02", "WP03"]
_COMMIT_ADVICE = "Commit, stash, or revert"
_DO_NOT_RECORD = "Do NOT stage or record"
_GENUINE_EDIT = "genuine operator edit that must survive\n"


def _flat(result: subprocess.CompletedProcess[str]) -> str:
    """stdout+stderr with Rich's terminal line wrapping collapsed to single spaces."""
    return " ".join((result.stdout + result.stderr).split())


def _coord_worktree(mission: CoordMission) -> Path:
    for line in git_out(mission.repo, "worktree", "list").splitlines():
        path = line.split()[0]
        if "coord" in path:
            return Path(path)
    raise AssertionError("coordination worktree not found")


def _advance_coord_branch_without_refreshing_worktree(mission: CoordMission, wp_order: list[str]) -> None:
    """Merge every lane into the coordination branch WITHOUT touching its worktree.

    The merges run in a throwaway detached worktree and the branch ref is then moved with
    ``update-ref`` — exactly the "ref advanced, worktree never refreshed" window. The
    coordination worktree (still on the coordination branch) therefore reads every lane's
    integrated file as a staged deletion.
    """
    old_tip = mission.rev(mission.coord_branch)
    scratch = mission.repo.parent / "coord-merge-scratch"
    git(mission.repo, "worktree", "add", "--detach", "-q", str(scratch), mission.coord_branch)
    try:
        for wp in wp_order:
            git(scratch, "merge", "-q", "--no-edit", mission.lane_branch(wp))
        merged_tip = git_out(scratch, "rev-parse", "HEAD").strip()
    finally:
        git(mission.repo, "worktree", "remove", "--force", str(scratch))
    git(mission.repo, "update-ref", f"refs/heads/{mission.coord_branch}", merged_tip, old_tip)


def _interrupt_coord_worktree_lag(mission: CoordMission, wp_order: list[str]) -> None:
    """Persist the pre-mutation anchors a real attempt-1 writes, then advance only the ref."""
    from mission_runtime import MissionArtifactKind, resolve_placement_only
    from specify_cli.consolidation.reconciliation import write_post_fix_marker
    from specify_cli.consolidation.state import ConsolidationState, save_state

    pre_mutation_target_sha = mission.rev(mission.target_branch)
    pre_mutation_coord_sha = mission.rev(mission.coord_branch)
    pre_mutation_coord_ref = resolve_placement_only(mission.repo, mission.slug, kind=MissionArtifactKind.STATUS_STATE).ref
    pre_interrupt_lane_tips = {mission.lane_branch(wp): mission.rev(mission.lane_branch(wp)) for wp in wp_order}

    _advance_coord_branch_without_refreshing_worktree(mission, wp_order)

    state = ConsolidationState(
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
    write_post_fix_marker(mission.repo, mission.mission_id)
    git(mission.repo, "checkout", "-q", mission.target_branch)


def _assert_lag_shape(mission: CoordMission) -> Path:
    """Guard the fixture: the coordination worktree really shows staged deletions."""
    coord_wt = _coord_worktree(mission)
    status = git_out(coord_wt, "status", "--porcelain")
    assert "D  src/pkg/wp01.py" in status, f"fixture must leave the coord worktree behind its HEAD:\n{status}"
    return coord_wt


def _wp_lanes(mission: CoordMission) -> dict[str, str]:
    """Current lane per WP, reduced from the mission's status log on the primary checkout."""
    from specify_cli.status.reducer import materialize

    snapshot = materialize(mission.feature_dir)
    return {wp_id: str(wp.get("lane", "")) for wp_id, wp in snapshot.work_packages.items()}


def test_5571_resume_refreshes_a_pure_coord_worktree_lag(tmp_path: Path) -> None:
    mission = build_coord_mission(tmp_path, wps=tuple(_WPS), mid8="01M5571A")
    approved = mission.approved_shas_from_lane_tips(_WPS)  # PRE-resume tips
    _interrupt_coord_worktree_lag(mission, _WPS)
    _assert_lag_shape(mission)

    result = run_terminus(mission, ["consolidate", "--resume", "--yes"])

    output = f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert result.returncode == 0, f"--resume over a pure coord-worktree lag must refresh it and exit 0, got rc={result.returncode}\n{output}"
    assert _COMMIT_ADVICE not in _flat(result), f"must never advise committing the staged deletions\n{output}"
    for wp_id, shas in approved.items():
        for sha in shas:
            assert sha_reachable(mission.repo, sha, mission.target_branch), (
                f"approved {wp_id} commit {sha[:10]} is NOT reachable from {mission.target_branch} after --resume over a lagging coordination worktree (#5571)"
            )
    lanes = _wp_lanes(mission)
    assert {wp: lanes.get(wp) for wp in _WPS} == dict.fromkeys(_WPS, "done"), f"every WP must end done, got {lanes}\n{output}"


def test_5571_resume_refuses_without_commit_advice_when_lag_carries_a_genuine_edit(tmp_path: Path) -> None:
    mission = build_coord_mission(tmp_path, wps=tuple(_WPS), mid8="01M5571B")
    _interrupt_coord_worktree_lag(mission, _WPS)
    coord_wt = _assert_lag_shape(mission)
    readme = coord_wt / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8") + _GENUINE_EDIT, encoding="utf-8")
    target_tip_before = mission.rev(mission.target_branch)

    result = run_terminus(mission, ["consolidate", "--resume", "--yes"])

    output = f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    combined = _flat(result)
    assert result.returncode != 0, f"a lag carrying a genuine edit must refuse non-zero\n{output}"
    assert _COMMIT_ADVICE not in combined, f"must never advise committing staged deletions that revert the integrated lanes\n{output}"
    assert _DO_NOT_RECORD in combined, f"must warn not to stage or record the staged deletions\n{output}"
    assert _GENUINE_EDIT in readme.read_text(encoding="utf-8"), "the genuine edit must be preserved, never reset away"
    assert mission.rev(mission.target_branch) == target_tip_before, "a refusal must move no target branch"
