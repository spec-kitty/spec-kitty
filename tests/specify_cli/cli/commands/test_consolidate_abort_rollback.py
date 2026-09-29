"""Unit tests for the ``consolidate --abort`` rollback helpers (#5318 / FR-005 / FR-011 / FR-007).

Real git in a tmp repo and the REAL rollback authority; only the rich console is
captured. The end-to-end behaviour over the real CLI lives in
``tests/terminus/test_repro_5318_abort.py``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import typer

from specify_cli.cli.commands import consolidate
from specify_cli.consolidation.rollback import begin_attempt, record_post_mutation_tips
from specify_cli.consolidation.state import (
    ConsolidationState,
    acquire_merge_lock,
    is_merge_locked,
    read_merge_lock_owner,
    save_state,
)

pytestmark = [pytest.mark.git_repo, pytest.mark.fast]

_LOCK = "__global_merge__"
_MISSION_ID = "01MABORT" + "0" * 18
_OTHER_ID = "01MOTHER" + "0" * 18
_MISSION_BRANCH = "kitty/mission-abort-unit"


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
    return proc.stdout.strip()


def _commit(repo: Path, branch: str, name: str) -> str:
    """One real commit on *branch* without touching the checked-out tree (plumbing only)."""
    tip = _git(repo, "rev-parse", branch)
    tree = _git(repo, "rev-parse", f"{tip}^{{tree}}")
    new = _git(repo, "commit-tree", tree, "-p", tip, "-m", name)
    _git(repo, "update-ref", f"refs/heads/{branch}", new, tip)
    return new


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-qb", "main", str(root)], check=True)
    for key, value in (("user.email", "t@t.com"), ("user.name", "T"), ("commit.gpgsign", "false")):
        _git(root, "config", key, value)
    (root / "README.md").write_text("init\n")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "init")
    _git(root, "branch", _MISSION_BRANCH)
    # Park the primary checkout on a throwaway branch so the snapshotted branches are free to move.
    _git(root, "checkout", "-q", "-b", "parking")
    return root


def _state(repo: Path, *, snapshot: bool = True) -> ConsolidationState:
    state = ConsolidationState(mission_id=_MISSION_ID, mission_slug="abort-unit", target_branch="main", wp_order=["WP01"])
    if snapshot:
        state.pre_mutation_refs = {"main": _git(repo, "rev-parse", "main"), _MISSION_BRANCH: _git(repo, "rev-parse", _MISSION_BRANCH)}
        save_state(state, repo)
        begin_attempt(repo, state)
    return state


def _advance_both(repo: Path) -> None:
    _commit(repo, "main", "squash")
    _commit(repo, _MISSION_BRANCH, "bake")


def _run_helper(repo: Path, state: ConsolidationState) -> tuple[bool, str]:
    with consolidate.console.capture() as capture:
        proceed = consolidate._abort_restore_or_keep_record(repo, state)
    return proceed, " ".join(capture.get().split())


def test_no_snapshot_proceeds_with_a_notice_and_moves_nothing(repo: Path) -> None:
    state = _state(repo, snapshot=False)
    _commit(repo, "main", "advance")
    tip = _git(repo, "rev-parse", "main")

    proceed, output = _run_helper(repo, state)

    assert proceed is True
    assert "no pre-mutation snapshot was recorded" in output
    assert _git(repo, "rev-parse", "main") == tip


def test_fully_restored_proceeds_and_restores_every_branch(repo: Path) -> None:
    state = _state(repo)
    snapshot = dict(state.pre_mutation_refs)
    _advance_both(repo)
    record_post_mutation_tips(repo, state)

    proceed, output = _run_helper(repo, state)

    assert proceed is True
    assert {b: _git(repo, "rev-parse", b) for b in snapshot} == snapshot
    assert output.count("restored") >= 2


def test_moved_branches_without_a_recorded_post_tip_keep_the_record(repo: Path) -> None:
    """Slice-10 F1: target/mission moved with no recorded post tip (kill window) -> never guessed at, never "untouched".

    Pre-fold these were reported "not moved by this run" and the abort proceeded to
    clear the record over two advanced branches.
    """
    state = _state(repo)
    _advance_both(repo)  # moved, but the run never recorded a post tip for them
    moved = {b: _git(repo, "rev-parse", b) for b in state.pre_mutation_refs}

    proceed, output = _run_helper(repo, state)

    assert proceed is False
    assert "no post-mutation tip was recorded" in output
    assert "not moved by this run" not in output
    assert {b: _git(repo, "rev-parse", b) for b in moved} == moved


def test_a_branch_moved_by_another_actor_keeps_the_record(repo: Path) -> None:
    state = _state(repo)
    _advance_both(repo)
    record_post_mutation_tips(repo, state)
    expected = state.post_mutation_refs[_MISSION_BRANCH]
    moved = _commit(repo, _MISSION_BRANCH, "another actor")

    proceed, output = _run_helper(repo, state)

    assert proceed is False
    assert "NOT restored" in output and "moved by another actor" in output
    assert f"expected {expected[:7]}" in output and f"observed {moved[:7]}" in output
    assert _git(repo, "rev-parse", _MISSION_BRANCH) == moved


def test_a_verified_landing_is_kept(repo: Path) -> None:
    state = _state(repo)
    _advance_both(repo)
    record_post_mutation_tips(repo, state)
    landed = _git(repo, "rev-parse", "main")
    state.reconciliation_passed_target_sha = landed

    proceed, output = _run_helper(repo, state)

    assert proceed is False
    assert "Kept the landing verified by an earlier reconciliation" in output
    assert _git(repo, "rev-parse", "main") == landed


def _plant_live_other_mission(repo: Path) -> None:
    save_state(ConsolidationState(mission_id=_OTHER_ID, mission_slug="other", target_branch="main", wp_order=["WP01"]), repo)
    assert acquire_merge_lock(_LOCK, repo, owner_token=_OTHER_ID)


def test_lock_is_taken_for_the_abort_when_free(repo: Path) -> None:
    state = _state(repo)

    consolidate._abort_hold_global_lock_or_exit(repo, state)

    assert read_merge_lock_owner(_LOCK, repo) == _MISSION_ID


def test_lock_already_owned_by_this_mission_does_not_block(repo: Path) -> None:
    state = _state(repo)
    assert acquire_merge_lock(_LOCK, repo, owner_token=_MISSION_ID)

    consolidate._abort_hold_global_lock_or_exit(repo, state)

    assert read_merge_lock_owner(_LOCK, repo) == _MISSION_ID


def test_lock_held_by_a_live_other_mission_refuses_and_leaves_it_alone(repo: Path) -> None:
    state = _state(repo)
    _plant_live_other_mission(repo)

    with pytest.raises(typer.Exit) as excinfo:
        consolidate._abort_hold_global_lock_or_exit(repo, state)

    assert excinfo.value.exit_code == 1
    assert read_merge_lock_owner(_LOCK, repo) == _OTHER_ID


def test_lock_held_by_a_dead_owner_does_not_block(repo: Path) -> None:
    state = _state(repo)
    assert acquire_merge_lock(_LOCK, repo, owner_token=_OTHER_ID)  # no state for it -> not live

    consolidate._abort_hold_global_lock_or_exit(repo, state)

    assert is_merge_locked(_LOCK, repo)


def test_a_legacy_unowned_lock_does_not_block(repo: Path) -> None:
    state = _state(repo)
    assert acquire_merge_lock(_LOCK, repo)

    consolidate._abort_hold_global_lock_or_exit(repo, state)

    assert read_merge_lock_owner(_LOCK, repo) is None


def test_keeping_the_record_releases_the_lock_this_abort_took(repo: Path) -> None:
    state = _state(repo)
    consolidate._abort_hold_global_lock_or_exit(repo, state)

    with consolidate.console.capture() as capture, pytest.raises(typer.Exit) as excinfo:
        consolidate._abort_exit_keeping_record(repo, state)

    assert excinfo.value.exit_code == 1
    assert "Kept the consolidation record" in " ".join(capture.get().split())
    assert not is_merge_locked(_LOCK, repo)


def test_success_line_is_truthful_about_restoration() -> None:
    assert "Branches restored to their pre-consolidation commits" in consolidate._abort_success_line("m", restored=True)
    assert "restored" not in consolidate._abort_success_line("m", restored=False)


def test_merge_workspace_abort_is_a_noop_without_an_active_record_or_workspace(repo: Path) -> None:
    assert consolidate._abort_merge_workspace(repo, _state(repo, snapshot=False)) is False  # no saved record
    assert consolidate._abort_merge_workspace(repo, _state(repo)) is False  # active record, no workspace dir


def test_no_snapshot_with_a_live_foreign_lock_proceeds_and_leaves_that_lock(repo: Path) -> None:
    """FR-005: a pre-fix record (no snapshot) moves no refs, so it neither needs nor is refused by the lock."""
    state = _state(repo, snapshot=False)
    save_state(state, repo)
    _plant_live_other_mission(repo)

    with consolidate.console.capture() as capture:
        git_merge_aborted, cleared = consolidate._abort_lock_restore_clear(repo, "abort-unit", (None, state))

    assert git_merge_aborted is False
    assert cleared is True
    assert "no pre-mutation snapshot was recorded" in " ".join(capture.get().split())
    assert read_merge_lock_owner(_LOCK, repo) == _OTHER_ID


def test_an_exception_after_the_lock_is_taken_releases_it_and_propagates(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    state = _state(repo)

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("teardown exploded")

    monkeypatch.setattr(consolidate, "_teardown_coordination_for_abort", _boom)

    with pytest.raises(RuntimeError, match="teardown exploded"):
        consolidate._abort_lock_restore_clear(repo, "abort-unit", (None, state))

    assert not is_merge_locked(_LOCK, repo), "a failed abort must not leave the global lock owned by its record"


def test_abort_success_line_does_not_call_a_resume_seeded_snapshot_pre_consolidation() -> None:
    """Slice-10 F8: after resuming an older record the snapshot was taken at that resume."""
    assert "pre-consolidation" in consolidate._abort_success_line("m", restored=True)
    seeded = consolidate._abort_success_line("m", restored=True, resume_seeded=True)
    assert "pre-consolidation" not in seeded and "snapshot taken when this record was resumed" in seeded
