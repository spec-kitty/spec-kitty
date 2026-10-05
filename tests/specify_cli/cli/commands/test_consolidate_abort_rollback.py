"""Unit tests for the ``consolidate --abort`` rollback helpers (#5318 / FR-005 / FR-011 / FR-007).

Real git in a tmp repo and the REAL rollback authority; only the rich console is
captured. The end-to-end behaviour over the real CLI lives in
``tests/terminus/test_repro_5318_abort.py``.
"""

from __future__ import annotations

import dataclasses
import json
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
        proceed, _report = consolidate._abort_restore_or_keep_record(repo, state)
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
        git_merge_aborted, cleared, _report = consolidate._abort_lock_restore_clear(repo, "abort-unit", (None, state))

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


def test_abort_success_line_names_the_record_restore_targets_when_a_restore_left_the_snapshot() -> None:
    """F5: a restore to an ADR-A2 restore target is not a restore to the pre-consolidation commits."""
    from specify_cli.consolidation.rollback import BranchOutcome, BranchOutcomeKind, RollbackReport

    off = BranchOutcome("develop", BranchOutcomeKind.RESTORED, "a" * 40, "c" * 40, "c" * 40, restored_to_sha="b" * 40)
    line = consolidate._abort_success_line("m", restored=True, report=RollbackReport(outcomes=(off,)))
    assert "Branches restored to the record's restore targets" in line and "pre-consolidation" not in line
    on = dataclasses.replace(off, restored_to_sha="a" * 40)
    assert "Branches restored to their pre-consolidation commits" in consolidate._abort_success_line("m", restored=True, report=RollbackReport(outcomes=(on,)))


def test_abort_with_a_snapshot_refuses_while_a_live_foreign_merge_holds_the_lock(repo: Path) -> None:
    """Wiring guard: ``_abort_lock_restore_clear`` must take the global lock BEFORE it restores anything.

    A record WITH a snapshot plus a live foreign mission's merge lock refuses (exit 1), performs
    no rollback, keeps the record and leaves the foreign lock untouched.
    """
    state = _state(repo)
    _advance_both(repo)
    record_post_mutation_tips(repo, state)
    advanced = {b: _git(repo, "rev-parse", b) for b in state.pre_mutation_refs}
    _plant_live_other_mission(repo)

    with pytest.raises(typer.Exit) as excinfo:
        consolidate._abort_lock_restore_clear(repo, "abort-unit", (None, state))

    assert excinfo.value.exit_code == 1
    assert {b: _git(repo, "rev-parse", b) for b in advanced} == advanced, "nothing may be restored while another merge is live"
    assert (repo / ".kittify" / "runtime" / "merge" / _MISSION_ID / "state.json").exists(), "the record must be kept"
    assert read_merge_lock_owner(_LOCK, repo) == _OTHER_ID


def test_abort_keeps_the_record_and_releases_the_lock_when_the_restore_is_incomplete(repo: Path) -> None:
    """Composition guard: an incomplete restore verdict must stop ``_abort_lock_restore_clear`` before it clears.

    A run-movable branch moved by another actor since the recorded post tip makes the restore
    incomplete: the abort exits 1, keeps ``state.json`` (not cleared, coordination not torn down)
    and releases the lock it took, leaving the other actor's commit in place.
    """
    state = _state(repo)
    _advance_both(repo)
    record_post_mutation_tips(repo, state)
    moved = _commit(repo, _MISSION_BRANCH, "another actor")

    with consolidate.console.capture(), pytest.raises(typer.Exit) as excinfo:
        consolidate._abort_lock_restore_clear(repo, "abort-unit", (None, state))

    assert excinfo.value.exit_code == 1
    assert (repo / ".kittify" / "runtime" / "merge" / _MISSION_ID / "state.json").exists(), "the record must be kept"
    assert not is_merge_locked(_LOCK, repo), "the lock this abort took must be released"
    assert _git(repo, "rev-parse", _MISSION_BRANCH) == moved


# ---------------------------------------------------------------------------
# #5687 / FR-008 / FR-009: operator release on ``--abort`` (US3 AS1-AS4).
#
# Driven through ``run_consolidate`` (the command body), with only the repo
# discovery and the banner stubbed; git, the record and the rollback authority
# are real.

_RELEASE_INVALID = "Error code: RELEASE_BRANCH_INVALID."


def _state_file(repo: Path) -> Path:
    return repo / ".kittify" / "runtime" / "merge" / _MISSION_ID / "state.json"


def _tips(repo: Path, branches: list[str]) -> dict[str, str]:
    return {b: _git(repo, "rev-parse", b) for b in branches}


def _cli(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    abort: bool = True,
    release: tuple[str, ...] = (),
    reason: str | None = None,
) -> tuple[int, str]:
    """Run the consolidate command body; return ``(exit_code, flattened output)``."""
    monkeypatch.setattr(consolidate, "find_repo_root", lambda: repo)
    monkeypatch.setattr(consolidate, "show_banner", lambda: None)
    options = consolidate.ConsolidateOptions(abort=abort)
    if release or reason is not None:  # a plain --abort builds the options exactly as before (positive control)
        options = dataclasses.replace(options, release_branch=list(release) or None, release_reason=reason)
    code = 0
    with consolidate.console.capture() as capture:
        try:
            consolidate.run_consolidate(options)
        except typer.Exit as exc:
            code = int(exc.exit_code or 0)
    return code, " ".join(capture.get().split())


def _target_moved_by_teammate(repo: Path) -> tuple[ConsolidationState, str]:
    """The run advanced both branches and recorded its post tips; then a teammate committed on ``main``."""
    state = _state(repo)
    _advance_both(repo)
    record_post_mutation_tips(repo, state)
    return state, _commit(repo, "main", "teammate")


def test_as1_plain_abort_deadlocks_on_a_foreign_commit_and_keeps_the_record(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive control on the AS1 fixture: without a release, ``--abort`` refuses (exit 1) and keeps the record."""
    _state_obj, foreign = _target_moved_by_teammate(repo)

    code, output = _cli(repo, monkeypatch)

    assert code == 1, output
    assert "NOT restored main" in output
    assert _state_file(repo).exists()
    assert _git(repo, "rev-parse", "main") == foreign


def test_as1_release_keeps_the_target_and_clears_the_record(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    state, foreign = _target_moved_by_teammate(repo)
    mission_snapshot = state.pre_mutation_refs[_MISSION_BRANCH]

    code, output = _cli(repo, monkeypatch, release=("main",), reason="keep teammate")

    assert code == 0, output
    assert _git(repo, "rev-parse", "main") == foreign, "the released branch stays at its live tip"
    assert _git(repo, "rev-parse", _MISSION_BRANCH) == mission_snapshot, "every other branch is restored"
    assert "kept main" in output and "released by operator: keep teammate" in output
    assert f"except main (kept at {foreign[:7]} by operator release)" in output
    assert "restored main" not in output
    assert not _state_file(repo).exists(), "the record clears once every other branch is restored"


def test_as1_release_after_a_failed_abort_never_claims_a_restore(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The deadlocked record from the positive control clears with a release; the line says nothing was restored."""
    _state_obj, foreign = _target_moved_by_teammate(repo)
    assert _cli(repo, monkeypatch)[0] == 1  # restores the mission branch, keeps the record

    code, output = _cli(repo, monkeypatch, release=("main",), reason="keep teammate")

    assert code == 0, output
    assert _git(repo, "rev-parse", "main") == foreign
    assert "Branches restored" not in output
    assert f"main (kept at {foreign[:7]} by operator release)" in output
    assert not _state_file(repo).exists()


@pytest.mark.parametrize(
    ("abort", "release", "reason"),
    [
        pytest.param(False, ("main",), "why", id="without-abort"),
        pytest.param(True, ("main",), None, id="missing-reason"),
        pytest.param(True, ("main",), "   ", id="blank-reason"),
        pytest.param(True, ("kitty/mission-abort-unit-lane-a",), "why", id="lane-branch"),
        pytest.param(True, ("no-such-branch",), "why", id="unknown-branch"),
    ],
)
def test_as2_invalid_release_refuses_and_changes_nothing(
    repo: Path, monkeypatch: pytest.MonkeyPatch, abort: bool, release: tuple[str, ...], reason: str | None
) -> None:
    lane = "kitty/mission-abort-unit-lane-a"
    _git(repo, "branch", lane, "main")
    state, _foreign = _target_moved_by_teammate(repo)
    state.pre_mutation_refs[lane] = _git(repo, "rev-parse", lane)
    state.snapshot_lane_branches = [lane]
    save_state(state, repo)
    branches = [*state.pre_mutation_refs]
    before_record = _state_file(repo).read_bytes()
    before_tips = _tips(repo, branches)

    code, output = _cli(repo, monkeypatch, abort=abort, release=release, reason=reason)

    assert code == 2, output
    assert output.endswith(_RELEASE_INVALID), output
    assert _state_file(repo).read_bytes() == before_record, "the record must be unchanged"
    assert _tips(repo, branches) == before_tips, "no branch may move"
    assert not is_merge_locked(_LOCK, repo)


def test_as2_a_release_of_a_branch_that_does_not_resolve_refuses(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    state, _foreign = _target_moved_by_teammate(repo)
    _git(repo, "branch", "-D", _MISSION_BRANCH)
    before_record = _state_file(repo).read_bytes()

    code, output = _cli(repo, monkeypatch, release=(_MISSION_BRANCH,), reason="why")

    assert code == 2, output
    assert output.endswith(_RELEASE_INVALID), output
    assert _state_file(repo).read_bytes() == before_record
    assert not is_merge_locked(_LOCK, repo), "the refusal must release the lock the abort took"


def test_as3_releasing_a_restorable_branch_restores_it(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    state = _state(repo)
    snapshot = dict(state.pre_mutation_refs)
    _advance_both(repo)
    record_post_mutation_tips(repo, state)

    code, output = _cli(repo, monkeypatch, release=("main",), reason="not needed")

    assert code == 0, output
    assert _tips(repo, list(snapshot)) == snapshot
    assert "restored main" in output
    assert "kept" not in output and "released by operator" not in output
    assert not _state_file(repo).exists()


def test_as4_a_release_binds_to_the_sha_it_was_given_at(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A release persists before the rollback, bound to the live SHA; a later move voids it."""
    _state_obj, foreign = _target_moved_by_teammate(repo)
    _commit(repo, _MISSION_BRANCH, "another actor")  # keeps this abort from clearing the record

    code, output = _cli(repo, monkeypatch, release=("main",), reason="keep teammate")

    assert code == 1, output
    assert "kept main" in output
    record = json.loads(_state_file(repo).read_text())
    assert record["released_refs"] == {"main": foreign}
    assert record["release_reasons"] == {"main": "keep teammate"}

    moved = _commit(repo, "main", "after the release")
    code, output = _cli(repo, monkeypatch)

    assert code == 1, output
    assert "NOT restored main" in output and "kept main" not in output
    assert _git(repo, "rev-parse", "main") == moved
    assert _state_file(repo).exists()


def test_release_help_explains_what_is_kept_without_a_destructive_recipe() -> None:
    import click

    app = typer.Typer(add_completion=False)
    app.command()(consolidate.consolidate)
    command = typer.main.get_command(app)
    helps = {opt: (param.help or "") for param in command.params if isinstance(param, click.Option) for opt in param.opts}

    release_help = helps["--release-branch"]
    assert "--abort" in release_help and "unverified" in release_help
    for text in (release_help, helps["--release-reason"]):
        assert "reset --hard" not in text and "push --force" not in text and "branch -D" not in text
