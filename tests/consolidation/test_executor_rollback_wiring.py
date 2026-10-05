"""Executor wiring of the single rollback authority (WP03 / T013-T015).

* T013: the snapshot is captured once at the end of the claim and every attempt
  begins with ``begin_attempt``; a missing lane branch is warned about.
* T014: post-mutation tips are recorded by every mutating phase (before ANY exit,
  early return or exception) and by the in-phase byte-restore primitive.
* T015: ``_report_rollback`` resets THIS call's own PASS anchor before invoking
  the authority (post-tasks BLOCKER 1) while an EARLIER attempt's anchor still
  keeps a verified landing (FR-011); the resume short-circuit predicate is the
  single ``reconciliation_passed_for_tip``.
* #5385 (single rollback door): the driver wraps the whole post-mutation span; a
  non-zero ``typer.Exit``, any exception and an interrupt each call
  ``_report_rollback`` exactly once and propagate unchanged, ``typer.Exit(0)``
  passes through, and a failing rollback never replaces the original error.

Real temp git repos; nothing about git is mocked (only ``console`` output capture).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
import typer

from specify_cli.consolidation import (
    executor,
    rollback,
)
from specify_cli.consolidation.rollback import record_post_mutation_tips
from specify_cli.git.ref_advance import RefAdvanceError, RefRestoreError
from specify_cli.consolidation.state import get_state_path, load_state, save_state
from tests.consolidation.test_rollback_authority import _MISSION_BRANCH, _TARGET, Env, _advance_run, _commit_on, _git, _rev, make_env
from specify_cli.consolidation import (
    coord_strand,
    phase_claim,
    run_state,
)
from tests.consolidation.executor_family import (
    family_modules_binding,
    setattr_executor_family,
)

pytestmark = [pytest.mark.git_repo, pytest.mark.fast]


def _run_for(env: Env, *, coord_ref: str | None = None, is_resume: bool = False) -> Any:
    ref = coord_ref or _TARGET  # LANES: the coordination checkpoint resolves to the target itself
    checkpoint = run_state._CoordCheckpoint(ref=ref, sha=_rev(env.repo, ref))
    return SimpleNamespace(
        main_repo=env.repo, state=env.state, lanes_manifest=env.manifest, coord_checkpoint=checkpoint, is_resume=is_resume, own_pre_claim_moves={}
    )


# ------------------------------------------------------------------- T013


def test_lanes_snapshot_keys_are_target_mission_and_lanes_without_duplicates(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    run = _run_for(env)  # LANES: the coordination checkpoint resolves to the target itself

    phase_claim._capture_snapshot_and_begin_attempt(run)

    assert sorted(env.state.pre_mutation_refs) == sorted({_TARGET, _MISSION_BRANCH, *env.lane_branches})
    assert env.state.restore_targets == env.state.pre_mutation_refs, "begin_attempt must fix this attempt's restore targets"
    assert env.state.post_mutation_refs == {}


def test_snapshot_is_captured_once_and_reused_by_a_resume(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    phase_claim._capture_snapshot_and_begin_attempt(_run_for(env))
    first = dict(env.state.pre_mutation_refs)
    posts = _advance_run(env)

    phase_claim._capture_snapshot_and_begin_attempt(_run_for(env, is_resume=True))

    assert env.state.pre_mutation_refs == first, "a resume must reuse the persisted snapshot"
    assert env.state.restore_targets[_TARGET] == first[_TARGET], "consolidation's own advance is undone to the snapshot"
    # Re-pinned 2026-09-29 (slice-10 pre-PR verification): a resume carries forward the
    # previous post tip of every branch still sitting at it; resetting them wedged
    # `--abort` after a crashed resume (tests/terminus/test_abort_restores_snapshot.py).
    assert env.state.post_mutation_refs == {b: posts[b] for b in posts}, "tips still at the previous post tip are carried"


def test_missing_lane_branch_is_warned_about(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = make_env(tmp_path)
    _git(env.repo, "branch", "-D", env.lane_branches[0])
    console = MagicMock()
    setattr_executor_family(monkeypatch, "console", console)

    phase_claim._capture_snapshot_and_begin_attempt(_run_for(env))

    printed = " ".join(str(call.args[0]) for call in console.print.call_args_list)
    assert env.lane_branches[0] in printed and "not snapshotted" in printed
    assert env.lane_branches[0] not in env.state.pre_mutation_refs


# ------------------------------------------------------------------- T014


def _live(env: Env) -> dict[str, str]:
    return {b: _rev(env.repo, b) for b in env.state.pre_mutation_refs}


def _begin(env: Env) -> Any:
    run = _run_for(env)
    phase_claim._capture_snapshot_and_begin_attempt(run)
    return run


def test_phase_decorator_records_after_a_normal_return(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    run = _begin(env)

    @run_state._records_post_mutation_tips
    def phase(r: Any) -> None:
        _advance_run_target_only(env)

    phase(run)
    recorded = {_TARGET: _rev(env.repo, _TARGET)}  # slice-10 F2: only the branch THIS phase moved
    assert env.state.post_mutation_refs == recorded
    persisted = load_state(env.repo, "M1")
    assert persisted is not None and persisted.post_mutation_refs == recorded


def test_phase_decorator_records_before_an_early_return(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    run = _begin(env)

    @run_state._records_post_mutation_tips
    def phase(r: Any) -> None:
        _advance_run_target_only(env)
        return

    phase(run)
    assert env.state.post_mutation_refs[_TARGET] == _rev(env.repo, _TARGET)


def test_phase_decorator_records_when_the_phase_raises(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    run = _begin(env)

    @run_state._records_post_mutation_tips
    def phase(r: Any) -> None:
        _advance_run_target_only(env)
        raise RuntimeError("phase failed after moving a ref")

    with pytest.raises(RuntimeError, match="phase failed"):
        phase(run)
    assert env.state.post_mutation_refs[_TARGET] == _rev(env.repo, _TARGET), "a partial advance must be attributed to this attempt"


@pytest.mark.parametrize("error", [RefAdvanceError("cas refused"), RefRestoreError("cas refused")], ids=["advance", "restore"])
def test_cas_refused_advance_is_not_recorded_as_this_runs_post_tip(tmp_path: Path, error: Exception) -> None:
    """FR-007 / #4996: a detected foreign move must never become this run's own post tip."""
    env = make_env(tmp_path)
    run = _begin(env)
    snapshot = _rev(env.repo, _TARGET)

    @run_state._records_post_mutation_tips
    def phase(r: Any) -> None:
        _advance_run_target_only(env)  # ANOTHER actor moved the branch; our CAS advance is refused
        raise error

    with pytest.raises(type(error)):
        phase(run)

    assert _TARGET not in env.state.post_mutation_refs, "the foreign tip must not be attributed to this run"
    foreign_tip = _rev(env.repo, _TARGET)
    assert foreign_tip != snapshot

    report = rollback.rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    assert _rev(env.repo, _TARGET) == foreign_tip, "rollback must never restore over another actor's commit"
    outcome = next(o for o in report.outcomes if o.branch == _TARGET)
    assert outcome.kind in {rollback.BranchOutcomeKind.NOT_RESTORED, rollback.BranchOutcomeKind.UNCHANGED_BY_RUN}


def test_resync_failure_after_our_own_ref_move_is_recorded_as_this_runs_post_tip(tmp_path: Path) -> None:
    """Slice-10 F1: ``RefResyncError`` means OUR compare-and-swap won and only the checkout resync failed.

    The ref moved by this run, so its tip IS this run's post tip: recording it lets a
    rollback undo the advance. (A plain ``RefAdvanceError`` is a CAS refusal -- see above.)
    """
    from specify_cli.git.ref_advance import RefResyncError

    env = make_env(tmp_path)
    run = _begin(env)

    @run_state._records_post_mutation_tips
    def phase(r: Any) -> None:
        _advance_run_target_only(env)  # this run's own advance
        raise RefResyncError("Advanced develop but failed to resync the checked-out worktree")

    with pytest.raises(RefResyncError):
        phase(run)

    assert env.state.post_mutation_refs.get(_TARGET) == _rev(env.repo, _TARGET), "our own advance must be recorded"


def test_foreign_lane_commit_during_a_phase_is_never_reverted(tmp_path: Path) -> None:
    """Slice-10 F2: another actor's lane commit landing while a phase runs is never recorded nor rolled back."""
    env = make_env(tmp_path)
    run = _begin(env)
    lane = env.lane_branches[0]
    mission_snapshot = _rev(env.repo, _MISSION_BRANCH)

    @run_state._records_post_mutation_tips
    def phase(r: Any) -> None:
        _commit_on(env.repo, _MISSION_BRANCH, "run-merge")  # this run's own advance
        _commit_on(env.repo, lane, "agent-late-commit")  # ANOTHER actor, concurrently

    phase(run)
    foreign = _rev(env.repo, lane)
    assert lane not in env.state.post_mutation_refs

    report = rollback.rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    assert _rev(env.repo, lane) == foreign, "the foreign lane commit must survive the rollback"
    assert _rev(env.repo, _MISSION_BRANCH) == mission_snapshot, "the run's own advance is undone"
    assert report.fully_restored


def test_foreign_commit_on_the_target_between_phases_is_not_recorded(tmp_path: Path) -> None:
    """Slice-10 F2: a phase records only the branches whose tip changed DURING it.

    A foreign commit landing on the target between two phases is not attributed to
    the later phase (which did not move the target), so the rollback reports the
    target NOT_RESTORED instead of overwriting the other actor's commit.
    """
    env = make_env(tmp_path)
    run = _begin(env)

    @run_state._records_post_mutation_tips
    def phase_a(r: Any) -> None:
        _advance_run_target_only(env)

    @run_state._records_post_mutation_tips
    def phase_b(r: Any) -> None:
        _commit_on(env.repo, _MISSION_BRANCH, "phase-b")

    phase_a(run)
    ours = _rev(env.repo, _TARGET)
    foreign = _commit_on(env.repo, _TARGET, "foreign-between-phases")
    phase_b(run)

    assert env.state.post_mutation_refs[_TARGET] == ours, "phase_b did not move the target and must not re-record it"
    report = rollback.rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    target = next(o for o in report.outcomes if o.branch == _TARGET)
    assert target.kind is rollback.BranchOutcomeKind.NOT_RESTORED and "moved by another actor" in (target.reason or "")
    assert _rev(env.repo, _TARGET) == foreign, "another actor's commit is never overwritten"
    assert not report.fully_restored


def test_recorder_failure_never_masks_the_phase_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = make_env(tmp_path)
    run = _begin(env)

    def _boom(*_a: Any, **_k: Any) -> None:
        raise OSError("state.json unwritable")

    monkeypatch.setattr(rollback, "record_post_mutation_tips", _boom)

    @run_state._records_post_mutation_tips
    def phase(r: Any) -> None:
        raise ValueError("the real phase error")

    with pytest.raises(ValueError, match="the real phase error"):
        phase(run)


def test_recorder_failure_on_normal_exit_propagates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = make_env(tmp_path)
    run = _begin(env)

    def _boom(*_a: Any, **_k: Any) -> None:
        raise OSError("state.json unwritable")

    monkeypatch.setattr(rollback, "record_post_mutation_tips", _boom)

    @run_state._records_post_mutation_tips
    def phase(r: Any) -> None:
        return

    with pytest.raises(OSError, match="unwritable"):
        phase(run)


def _advance_run_target_only(env: Env) -> None:
    (env.repo / "phase.txt").write_text("phase\n")
    _git(env.repo, "add", "-A")
    _git(env.repo, "commit", "-qm", "phase advance")


@pytest.mark.parametrize(
    "name",
    [
        "_phase_merge_lanes",
        "_phase_bake_and_pre_target_done",
        "_phase_mission_to_target",
        "_phase_record_done_and_project",
        "_phase_commit_and_assert",
        "_restore_and_guard_coord_coherence",
    ],
)
def test_mutating_phases_and_in_phase_rollbacks_are_recorders(name: str) -> None:
    # #2026: the phases live in the split executor modules; every binding is the same object.
    fn = getattr(family_modules_binding(name)[0], name)
    assert getattr(fn, "__wrapped__", None) is not None, f"{name} must be wrapped by _records_post_mutation_tips"


def test_restore_pre_target_if_at_baseline_moves_no_ref(tmp_path: Path) -> None:
    """#5385: the in-phase restore is working-tree bytes + marker only; the ref undo is the door's job."""
    env = make_env(tmp_path)
    run = _begin(env)
    run.done_marked_before_target = True
    run.target_baseline_sha = _rev(env.repo, _TARGET)
    bookkeeping = env.repo / "bookkeeping.json"
    bookkeeping.write_text("mutated\n")
    run.pre_target_bookkeeping_snapshots = {bookkeeping: b"original\n"}
    run.pre_target_coord_ref = None  # no coordination topology: the strand marker is a no-op
    run.pre_target_coord_sha = None
    tips = _live(env)

    coord_strand._restore_pre_target_if_at_baseline(run)

    assert getattr(coord_strand._restore_pre_target_if_at_baseline, "__wrapped__", None) is None, "it moves no ref, so it records none"
    assert _live(env) == tips, "no branch may move"
    assert bookkeeping.read_bytes() == b"original\n", "the working-tree bytes are restored"
    assert env.state.post_mutation_refs == {}


def test_byte_restore_of_state_json_keeps_the_recorded_post_tips_on_disk(tmp_path: Path) -> None:
    """Post-spec squad H4: a byte restore that rewrites state.json must not erase the recorded post tips."""
    env = make_env(tmp_path)
    run = _begin(env)
    run.done_marked_before_target = False
    save_state(env.state, env.repo)
    state_path = get_state_path(env.repo, env.state.mission_id)
    stale_bytes = state_path.read_bytes()  # captured before this attempt recorded any post tip
    posts = _advance_run(env)
    recorded = load_state(env.repo, env.state.mission_id)
    assert posts and recorded is not None and recorded.post_mutation_refs == posts

    coord_strand._restore_and_guard_coord_coherence(run, {state_path: stale_bytes})

    persisted = load_state(env.repo, env.state.mission_id)
    assert persisted is not None and persisted.post_mutation_refs == posts, "the recorder re-saves the in-memory record after the byte restore"


# ------------------------------------------------------------------- T015


def _report_run(env: Env) -> Any:
    run = _begin(env)
    run.lanes_manifest = env.manifest
    return run


def test_report_rollback_resets_this_runs_own_pass_anchor_then_restores(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """BLOCKER 1: the fresh path persists ITS OWN anchor before the projection proof refuses."""
    env = make_env(tmp_path)
    run = _report_run(env)
    snap_target = _rev(env.repo, _TARGET)
    _advance_run(env)
    anchor_before = run.state.reconciliation_passed_target_sha
    run.state.reconciliation_passed_target_sha = _rev(env.repo, _TARGET)  # written by this run's PASS
    console = MagicMock()
    setattr_executor_family(monkeypatch, "console", console)

    executor._report_rollback(run, anchor_before=anchor_before)

    assert _rev(env.repo, _TARGET) == snap_target, "this run's own anchor must not shield its advance"
    assert run.state.reconciliation_passed_target_sha is None
    printed = str(console.print.call_args_list[-1].args[0])
    assert "restored" in printed and _TARGET in printed


def test_report_rollback_keeps_a_landing_verified_by_an_earlier_attempt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = make_env(tmp_path)
    run = _report_run(env)
    _advance_run(env)
    landed = _rev(env.repo, _TARGET)
    run.state.reconciliation_passed_target_sha = landed  # persisted by an EARLIER attempt
    console = MagicMock()
    setattr_executor_family(monkeypatch, "console", console)

    executor._report_rollback(run, anchor_before=landed)

    assert _rev(env.repo, _TARGET) == landed
    assert run.state.reconciliation_passed_target_sha == landed
    assert "Kept the landing" in str(console.print.call_args_list[-1].args[0])


def test_report_rollback_reports_a_failing_authority_and_lets_the_exit_propagate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = make_env(tmp_path)
    run = _report_run(env)
    console = MagicMock()
    setattr_executor_family(monkeypatch, "console", console)

    def _boom(*_a: Any, **_k: Any) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(rollback, "rollback_to_snapshot", _boom)

    executor._report_rollback(run, anchor_before=None)  # must not raise: the caller re-raises the gate's typer.Exit

    printed = str(console.print.call_args_list[-1].args[0])
    assert "Rollback could not complete" in printed and "disk full" in printed and _TARGET in printed


@pytest.mark.parametrize(("is_resume", "anchored", "expected"), [(False, True, False), (True, False, False), (True, True, True)])
def test_resume_short_circuit_delegates_to_the_single_predicate(tmp_path: Path, is_resume: bool, anchored: bool, expected: bool) -> None:
    env = make_env(tmp_path)
    run = _run_for(env, is_resume=is_resume)
    run.state.reconciliation_passed_target_sha = _rev(env.repo, _TARGET) if anchored else None
    assert executor._resume_reconciliation_already_passed(run) is expected


def test_unresolvable_target_never_short_circuits(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    run = _run_for(env, is_resume=True)
    run.state.reconciliation_passed_target_sha = "a" * 40
    subprocess.run(["git", "-C", str(env.repo), "branch", "-m", _TARGET, "renamed"], check=True)
    assert executor._resume_reconciliation_already_passed(run) is False


# ---------------------------------------------------------- real-phase recording


def test_persisted_post_tips_equal_live_tips_after_every_real_phase(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Drive a REAL coordination consolidation in-process; after each mutating phase the persisted tips are the live tips."""
    from tests.terminus.conftest import build_coord_mission

    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8="01M5318W")
    monkeypatch.setenv("HOME", str(mission.home))
    monkeypatch.chdir(mission.repo)
    checks: dict[str, bool] = {}

    def spy(name: str, real: Any) -> Any:
        def wrapper(run: Any) -> None:
            try:
                real(run)
            finally:
                state = load_state(run.main_repo, run.canonical_id)
                assert state is not None and state.pre_mutation_refs, "the snapshot must exist before the first mutating phase"
                live = {b: _rev(run.main_repo, b) for b in state.pre_mutation_refs if _resolves(run.main_repo, b)}
                movable = set(live) - set(state.snapshot_lane_branches)
                # slice-10 F2: every recorded tip is live, no lane is recorded, and every
                # run-movable branch the run moved off its restore target is recorded.
                moved = {b for b in movable if live[b] != state.restore_targets.get(b, state.pre_mutation_refs[b])}
                checks[name] = all(live.get(b) == sha for b, sha in state.post_mutation_refs.items()) and moved <= set(state.post_mutation_refs) <= movable

        return wrapper

    phases = ["_phase_merge_lanes", "_phase_bake_and_pre_target_done", "_phase_mission_to_target", "_phase_record_done_and_project", "_phase_commit_and_assert"]
    for name in phases:
        monkeypatch.setattr(executor, name, spy(name, getattr(executor, name)))

    executor._run_lane_based_consolidation(mission.repo, mission.slug, push=False, delete_branch=None, remove_worktree=None, assume_yes=True)

    assert checks == dict.fromkeys(phases, True)


def _resolves(repo: Path, branch: str) -> bool:
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", "-q", f"refs/heads/{branch}"], capture_output=True, check=False).returncode == 0


def test_record_post_mutation_tips_import_is_the_authority_function() -> None:
    assert executor.rollback.record_post_mutation_tips is record_post_mutation_tips


# ------------------------------------------------------------ #5385 rollback door


def _door_mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mid8: str) -> Any:
    from tests.terminus.lanes_fixture import build_lanes_mission

    mission = build_lanes_mission(tmp_path, wps=("WP01",), target_branch="develop", mid8=mid8)
    monkeypatch.setenv("HOME", str(mission.home))
    monkeypatch.chdir(mission.repo)
    return mission


def _consolidate(mission: Any) -> None:
    executor._run_lane_based_consolidation(mission.repo, mission.slug, push=False, delete_branch=None, remove_worktree=None, assume_yes=True)


def _raise_after(monkeypatch: pytest.MonkeyPatch, phase: str, error: BaseException) -> None:
    real = getattr(executor, phase)

    def failing(run: Any) -> None:
        real(run)
        raise error

    monkeypatch.setattr(executor, phase, failing)


def _spy_report(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    calls: list[Any] = []
    real = executor._report_rollback

    def spy(run: Any, *, anchor_before: str | None) -> None:
        calls.append(run)
        real(run, anchor_before=anchor_before)

    monkeypatch.setattr(executor, "_report_rollback", spy)
    return calls


def test_door_lets_a_zero_exit_through_without_rolling_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mission = _door_mission(tmp_path, monkeypatch, "01M5385Z")
    target_before = _rev(mission.repo, mission.target_branch)
    calls = _spy_report(monkeypatch)
    zero = typer.Exit(0)
    _raise_after(monkeypatch, "_phase_porcelain_invariant", zero)

    with pytest.raises(typer.Exit) as excinfo:
        _consolidate(mission)

    assert excinfo.value is zero
    assert calls == [], "typer.Exit(0) is not a failure: no rollback"
    assert _rev(mission.repo, mission.target_branch) != target_before, "a zero exit keeps the landing in place"


@pytest.mark.parametrize(
    "make_error",
    [lambda: typer.Exit(1), lambda: RuntimeError("planted"), lambda: KeyboardInterrupt()],
    ids=["exit1", "runtime", "interrupt"],
)
def test_door_rolls_back_once_and_propagates_the_original(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make_error: Any) -> None:
    mission = _door_mission(tmp_path, monkeypatch, "01M5385W")
    target_before = _rev(mission.repo, mission.target_branch)
    calls = _spy_report(monkeypatch)
    error = make_error()
    _raise_after(monkeypatch, "_phase_mission_to_target", error)

    with pytest.raises(type(error)) as excinfo:
        _consolidate(mission)

    assert excinfo.value is error, "the ORIGINAL exception must propagate unchanged"
    assert len(calls) == 1, "exactly one rollback per failed attempt"
    assert _rev(mission.repo, mission.target_branch) == target_before


def test_door_keeps_the_original_error_when_the_authority_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    mission = _door_mission(tmp_path, monkeypatch, "01M5385A")
    _raise_after(monkeypatch, "_phase_mission_to_target", RuntimeError("planted"))

    def _boom(*_a: Any, **_k: Any) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(rollback, "rollback_to_snapshot", _boom)

    with pytest.raises(RuntimeError, match="planted"):
        _consolidate(mission)

    out = " ".join(capsys.readouterr().out.split())
    assert "Rollback could not complete: disk full" in out


def test_report_rollback_survives_a_failing_anchor_reset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A ``save_state`` failure while undoing this run's own anchor never escapes ``_report_rollback``."""
    env = make_env(tmp_path)
    run = _report_run(env)
    run.state.reconciliation_passed_target_sha = "b" * 40  # differs from anchor_before -> save_state runs
    console = MagicMock()
    setattr_executor_family(monkeypatch, "console", console)
    authority = MagicMock()
    monkeypatch.setattr(rollback, "rollback_to_snapshot", authority)

    def _unwritable(*_a: Any, **_k: Any) -> None:
        raise OSError("read-only state dir")

    setattr_executor_family(monkeypatch, "save_state", _unwritable)

    executor._report_rollback(run, anchor_before=None)  # must not raise

    printed = str(console.print.call_args_list[-1].args[0])
    assert "Rollback could not complete" in printed and "read-only state dir" in printed
    authority.assert_not_called()


def test_report_rollback_survives_a_second_interrupt_during_the_rollback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A Ctrl-C while the rollback runs is reported, never raised in place of the original error."""
    env = make_env(tmp_path)
    run = _report_run(env)
    console = MagicMock()
    setattr_executor_family(monkeypatch, "console", console)

    def _interrupted(*_a: Any, **_k: Any) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(rollback, "rollback_to_snapshot", _interrupted)

    try:
        executor._report_rollback(run, anchor_before=None)
    except KeyboardInterrupt:
        pytest.fail("a second interrupt during the rollback escaped _report_rollback and would replace the original error")

    printed = str(console.print.call_args_list[-1].args[0])
    assert "Rollback could not complete" in printed and _TARGET in printed


def test_door_keeps_the_original_error_when_the_rollback_is_interrupted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    mission = _door_mission(tmp_path, monkeypatch, "01M5385I")
    _raise_after(monkeypatch, "_phase_mission_to_target", RuntimeError("planted"))

    def _interrupted(*_a: Any, **_k: Any) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(rollback, "rollback_to_snapshot", _interrupted)

    try:
        with pytest.raises(RuntimeError, match="planted"):
            _consolidate(mission)
    except KeyboardInterrupt:
        pytest.fail("the interrupt during the rollback replaced the original error")

    assert "Rollback could not complete" in " ".join(capsys.readouterr().out.split())


# ------------------------------------------------- rollback-anchor-authority WP03 (#5686)
#
# T012: the phase recorder's taint rule (FR-011) and per-branch intent clearing (FR-006).
# T013: the read-only UNEXPLAINED_BRANCH_MOVE pre-check, the claim's own-move refusal and
#       the advance-intent sink around the door span.
# T014: a reconciliation PASS settles the target once the door span completed; settling
#       spends the branch's intent chain.

_ERROR_CODE_LINE = "Error code: UNEXPLAINED_BRANCH_MOVE."


#: R2: the UNEXPLAINED_BRANCH_MOVE remedies, in order (inspect, move it yourself, release with its warning).
_REMEDY_ORDER = ("git log ", "move the branch yourself", "--release-branch")
_RELEASE_WARNING = "a release keeps every commit listed above on the branch"


def _assert_remedy_order(output: str) -> None:
    positions = [output.find(marker) for marker in _REMEDY_ORDER]
    assert all(p >= 0 for p in positions) and positions == sorted(positions), f"remedies out of order {positions}. output={output}"
    assert _RELEASE_WARNING in output, f"the release remedy must warn that it keeps the commits. output={output}"


_DESTRUCTIVE = ("reset --hard", "branch -f", "update-ref")


@pytest.mark.parametrize(
    ("entry", "expected", "live", "records"),
    [
        ("E", "E", "L", True),  # moved during the phase, entered at the expected tip
        ("E", "E", "E", False),  # did not move
        ("F", "E", "L", False),  # entered at a foreign tip: a foreign interleave (US1 AS2)
        ("E", "E", None, False),  # deleted during the phase
        (None, None, "L", True),  # an absent branch at entry is expected absent and created by the phase
    ],
    ids=["moved", "unmoved", "foreign-entry", "deleted", "created"],
)
def test_phase_records_branch_rule(entry: str | None, expected: str | None, live: str | None, records: bool) -> None:
    assert rollback.phase_records_branch(entry, expected, live) is records


def test_foreign_commit_between_phases_under_this_runs_next_commit_is_not_recorded(tmp_path: Path) -> None:
    """US1 AS2 / FR-011: a later phase that commits ON TOP of a foreign interleave never records that tip."""
    env = make_env(tmp_path)
    run = _begin(env)

    @run_state._records_post_mutation_tips
    def phase_a(r: Any) -> None:
        _advance_run_target_only(env)

    @run_state._records_post_mutation_tips
    def phase_b(r: Any) -> None:
        rollback.note_advance_intent(env.repo, env.state, _TARGET, _rev(env.repo, _TARGET), "f" * 40)
        _commit_on(env.repo, _TARGET, "phase-b-on-top-of-foreign")

    phase_a(run)
    ours = _rev(env.repo, _TARGET)
    foreign = _commit_on(env.repo, _TARGET, "foreign-between-phases")
    phase_b(run)

    assert env.state.post_mutation_refs[_TARGET] == ours, "a phase entered at a foreign tip must not record its exit tip"
    assert _TARGET not in env.state.advance_intents, "a rejected branch's intent chain is cleared too"
    report = rollback.rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)
    target = next(o for o in report.outcomes if o.branch == _TARGET)
    assert target.kind is rollback.BranchOutcomeKind.NOT_RESTORED and "moved by another actor" in (target.reason or "")
    assert _git(env.repo, "merge-base", "--is-ancestor", foreign, _TARGET) == "", "the foreign commit stays reachable"
    assert not report.fully_restored


def test_recorder_clears_the_intent_chain_of_a_recorded_branch(tmp_path: Path) -> None:
    """A recorded branch's chain is spent: a later advance must start a fresh chain on the recorded post tip."""
    env = make_env(tmp_path)
    run = _begin(env)

    @run_state._records_post_mutation_tips
    def phase(r: Any) -> None:
        rollback.note_advance_intent(env.repo, env.state, _TARGET, _rev(env.repo, _TARGET), "e" * 40)
        _advance_run_target_only(env)

    phase(run)

    assert env.state.post_mutation_refs[_TARGET] == _rev(env.repo, _TARGET)
    persisted = load_state(env.repo, "M1")
    assert persisted is not None and _TARGET not in persisted.advance_intents, "the recorder clears the chain and saves"


def test_unmoved_branch_keeps_its_intent_chain(tmp_path: Path) -> None:
    """Only a branch that MOVED during the phase has its chain cleared."""
    env = make_env(tmp_path)
    run = _begin(env)
    rollback.note_advance_intent(env.repo, env.state, _MISSION_BRANCH, _rev(env.repo, _MISSION_BRANCH), "d" * 40)

    @run_state._records_post_mutation_tips
    def phase(r: Any) -> None:
        _advance_run_target_only(env)

    phase(run)

    assert env.state.advance_intents.get(_MISSION_BRANCH) == [_rev(env.repo, _MISSION_BRANCH), "d" * 40]


def test_nested_recorders_never_taint_the_outer_phase(tmp_path: Path) -> None:
    """Expectations are captured per recorder instance at ITS entry, so an inner recorder never taints the outer one."""
    env = make_env(tmp_path)
    run = _begin(env)

    @run_state._records_post_mutation_tips
    def inner(r: Any) -> None:
        _commit_on(env.repo, _TARGET, "inner-advance")

    @run_state._records_post_mutation_tips
    def outer(r: Any) -> None:
        _advance_run_target_only(env)
        inner(r)
        _commit_on(env.repo, _TARGET, "outer-after-inner")

    outer(run)

    assert env.state.post_mutation_refs[_TARGET] == _rev(env.repo, _TARGET), "the outer phase records its own exit tip"
    report = rollback.rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)
    assert report.fully_restored, report.render()


def test_settle_branch_spends_the_intent_chain(tmp_path: Path) -> None:
    """Leeway (WP02 review LOW): settling a branch drops its intent chain, so a stale chain cannot adopt a later move."""
    env = make_env(tmp_path)
    _begin(env)
    rollback.note_advance_intent(env.repo, env.state, _TARGET, _rev(env.repo, _TARGET), "c" * 40)

    rollback.settle_branch(env.repo, env.state, _TARGET)

    persisted = load_state(env.repo, "M1")
    assert persisted is not None
    assert _TARGET not in persisted.unsettled_refs and _TARGET not in persisted.advance_intents


def test_partial_rollback_drops_the_settled_chain_and_keeps_the_not_restored_chain(tmp_path: Path) -> None:
    """WP02 review LOW: a restored branch's chain is spent; a NOT_RESTORED branch keeps its (still unproven) chain."""
    env = make_env(tmp_path)
    _begin(env)
    mission_snapshot = _rev(env.repo, _MISSION_BRANCH)
    target_snapshot = _rev(env.repo, _TARGET)
    _advance_run(env)
    rollback.note_advance_intent(env.repo, env.state, _MISSION_BRANCH, _rev(env.repo, _MISSION_BRANCH), "b" * 40)
    rollback.note_advance_intent(env.repo, env.state, _TARGET, env.state.post_mutation_refs[_TARGET], "a" * 40)
    _commit_on(env.repo, _TARGET, "foreign-on-target")

    report = rollback.rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    kinds = {o.branch: o.kind for o in report.outcomes}
    assert kinds[_MISSION_BRANCH] is rollback.BranchOutcomeKind.RESTORED and _rev(env.repo, _MISSION_BRANCH) == mission_snapshot
    assert kinds[_TARGET] is rollback.BranchOutcomeKind.NOT_RESTORED and _rev(env.repo, _TARGET) != target_snapshot
    persisted = load_state(env.repo, "M1")
    assert persisted is not None
    assert _MISSION_BRANCH not in persisted.advance_intents, "the restored branch's chain is spent"
    assert persisted.advance_intents.get(_TARGET) == [env.state.post_mutation_refs[_TARGET], "a" * 40], "the NOT_RESTORED chain stays"


def _unrecorded_target_move(env: Env) -> str:
    """A claim, then a move of the target the record cannot explain (a kill before the recorder)."""
    _begin(env)
    return _commit_on(env.repo, _TARGET, "unrecorded-landing")


def _state_bytes(env: Env) -> bytes:
    return get_state_path(env.repo, "M1").read_bytes()


def test_precheck_refuses_an_unexplained_move_and_keeps_the_record(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    env = make_env(tmp_path)
    landed = _unrecorded_target_move(env)
    before = _state_bytes(env)

    with pytest.raises(typer.Exit) as excinfo:
        executor._refuse_unexplained_branch_moves(env.repo, "M1")

    output = " ".join(capsys.readouterr().out.split())
    assert excinfo.value.exit_code == 1
    assert output.endswith(_ERROR_CODE_LINE), output
    assert _TARGET in output and landed in output and env.state.pre_mutation_refs[_TARGET] in output, "names branch, target and live SHA"
    assert "Nothing was changed" in output and "record is kept" in output
    assert "--release-branch" in output and f"git log {env.state.pre_mutation_refs[_TARGET]}..{landed}" in output
    _assert_remedy_order(output)
    assert not any(recipe in output for recipe in _DESTRUCTIVE), f"C-002: no destructive recipe. output={output}"
    assert _state_bytes(env) == before, "the pre-check is read-only"


def test_precheck_returns_the_start_tips_when_every_move_is_explained(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    _begin(env)
    _advance_run(env)

    tips = executor._refuse_unexplained_branch_moves(env.repo, "M1")

    assert tips == {b: _rev(env.repo, b) for b in rollback.run_movable_branches(env.state)}


def test_precheck_without_a_record_or_snapshot_is_a_no_op(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    assert executor._refuse_unexplained_branch_moves(env.repo, "M1") == {}, "no record: nothing to check"
    save_state(env.state, env.repo)
    assert executor._refuse_unexplained_branch_moves(env.repo, "M1") == {}, "zero-progress record: no snapshot yet"


def test_precheck_leaves_the_branch_of_a_pending_coord_reconcile_marker_to_the_heal(tmp_path: Path) -> None:
    """Orchestrator ruling: the resume-start heal owns the coordination branch a marker names."""
    env = make_env(tmp_path)
    landed = _unrecorded_target_move(env)
    env.state.pending_coord_reconcile = {"coord_ref": _TARGET, "captured_sha": env.state.pre_mutation_refs[_TARGET]}
    save_state(env.state, env.repo)

    tips = executor._refuse_unexplained_branch_moves(env.repo, "M1")

    assert tips[_TARGET] == landed


def test_claim_refuses_an_unexplained_move_identically(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    env = make_env(tmp_path)
    landed = _unrecorded_target_move(env)
    before = _state_bytes(env)
    run = _run_for(env, is_resume=True)
    run.own_pre_claim_moves = {}

    with pytest.raises(typer.Exit) as excinfo:
        phase_claim._capture_snapshot_and_begin_attempt(run)

    output = " ".join(capsys.readouterr().out.split())
    assert excinfo.value.exit_code == 1 and output.endswith(_ERROR_CODE_LINE), output
    assert _TARGET in output and landed in output
    assert _state_bytes(env) == before, "begin_attempt changes nothing when it refuses"


def test_claim_accepts_this_processs_own_pre_claim_move(tmp_path: Path) -> None:
    """A branch this process moved itself (heal, attestations) from its restore target re-anchors; no refusal."""
    env = make_env(tmp_path)
    _begin(env)
    origin = _rev(env.repo, _TARGET)
    own = _commit_on(env.repo, _TARGET, "attestation-status-commit")
    run = _run_for(env, is_resume=True)
    run.own_pre_claim_moves = {_TARGET: rollback.OwnMove(origin, own)}

    phase_claim._capture_snapshot_and_begin_attempt(run)

    assert env.state.restore_targets[_TARGET] == own


def test_claim_refuses_a_move_on_top_of_this_processs_own_pre_claim_move(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """P1: once another actor committed on top of the own move, the branch is no longer where this process left it."""
    env = make_env(tmp_path)
    _begin(env)
    _advance_run_target_only(env)
    record_post_mutation_tips(env.repo, env.state)
    origin = _rev(env.repo, _TARGET)
    own = _commit_on(env.repo, _TARGET, "attestation-status-commit")
    foreign = _commit_on(env.repo, _TARGET, "teammate-commit")
    before = _state_bytes(env)
    run = _run_for(env, is_resume=True)
    run.own_pre_claim_moves = {_TARGET: rollback.OwnMove(origin, own)}

    with pytest.raises(typer.Exit) as excinfo:
        phase_claim._capture_snapshot_and_begin_attempt(run)

    output = " ".join(capsys.readouterr().out.split())
    assert excinfo.value.exit_code == 1 and output.endswith(_ERROR_CODE_LINE), output
    assert foreign in output and _state_bytes(env) == before


@pytest.mark.parametrize(
    ("own", "before", "after", "expected"),
    [
        pytest.param({}, {"t": "a"}, {"t": "a"}, {}, id="unmoved_is_not_own"),
        pytest.param({}, {"t": "a"}, {"t": "b"}, {"t": ("a", "b")}, id="moved_by_the_step"),
        pytest.param({}, {"t": "a"}, {"t": None}, {}, id="vanished_is_not_own"),
        pytest.param({"t": ("a", "b")}, {"t": "b"}, {"t": "c"}, {"t": ("a", "c")}, id="continues_an_earlier_own_move"),
        pytest.param({"t": ("a", "b")}, {"t": "x"}, {"t": "c"}, {"t": ("x", "c")}, id="a_foreign_move_in_between_restarts"),
        pytest.param({"t": ("a", "b")}, {"t": "b"}, {"t": "b"}, {"t": ("a", "b")}, id="an_unmoving_step_keeps_the_earlier_move"),
        pytest.param({}, {"t": "a", "o": "p"}, {"t": "b", "o": "q"}, {"t": ("a", "b")}, id="a_branch_the_step_cannot_write_is_never_own"),
    ],
)
def test_own_moves_across_counts_only_tips_the_step_changed(
    own: dict[str, tuple[str, str]], before: dict[str, str | None], after: dict[str, str | None], expected: dict[str, tuple[str, str]]
) -> None:
    folded = rollback.own_moves_across({b: rollback.OwnMove(*m) for b, m in own.items()}, before, after, writes=("t",))
    assert {b: (m.before, m.after) for b, m in folded.items()} == expected


def test_a_foreign_move_on_another_branch_in_the_attestation_window_stays_unexplained(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Fold review: the attestations write only the status-surface branch; a foreign commit on another run-movable branch is never their move."""
    env = make_env(tmp_path)
    _begin(env)
    start = {b: tip for b, tip in rollback.movable_branch_tips(env.repo, env.state).items() if tip is not None}
    _commit_on(env.repo, _TARGET, "attestation-status-commit")  # LANES: the status surface is the target
    foreign = _commit_on(env.repo, _MISSION_BRANCH, "teammate-commit")
    before = _state_bytes(env)

    own = executor._own_moves_after_step(env.repo, {}, start, writes=(_TARGET,))

    assert set(own) == {_TARGET}, f"only the status-surface branch is the attestations' own move: {own}"
    run = _run_for(env, is_resume=True)
    run.own_pre_claim_moves = own
    with pytest.raises(typer.Exit) as excinfo:
        phase_claim._capture_snapshot_and_begin_attempt(run)
    output = " ".join(capsys.readouterr().out.split())
    assert excinfo.value.exit_code == 1 and output.endswith(_ERROR_CODE_LINE), output
    assert _MISSION_BRANCH in output and foreign in output and _state_bytes(env) == before


@pytest.mark.parametrize("topology", ["lanes", "coord"])
def test_the_attestation_status_branch_is_the_status_surface(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, topology: str) -> None:
    """LANES: the attestation status commit lands on the target; coordination topology: on the coordination branch."""
    from tests.terminus.conftest import build_coord_mission
    from tests.terminus.lanes_fixture import build_lanes_mission

    if topology == "lanes":
        mission = build_lanes_mission(tmp_path, wps=("WP01",), target_branch="develop", mid8="01M5686B")
        expected = mission.target_branch
    else:
        mission = build_coord_mission(tmp_path, wps=("WP01",), mid8="01M5686D")
        expected = mission.coord_branch
    monkeypatch.setenv("HOME", str(mission.home))

    assert run_state._status_surface_ref(mission.repo, mission.slug) == expected


def test_door_persists_an_advance_intent_for_every_span_advance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-006: the span's advances report through the sink, which persists them via note_advance_intent."""
    mission = _door_mission(tmp_path, monkeypatch, "01M5686S")
    noted: list[tuple[str, str, str]] = []
    real = rollback.note_advance_intent

    def spy(repo: Path, state: Any, branch: str, old: str, new: str) -> None:
        noted.append((branch, old, new))
        real(repo, state, branch, old, new)

    monkeypatch.setattr(rollback, "note_advance_intent", spy)
    target_before = _rev(mission.repo, mission.target_branch)

    _consolidate(mission)

    target_advances = [(old, new) for branch, old, new in noted if branch == mission.target_branch]
    assert target_advances and target_advances[0][0] == target_before, f"the target advance must report an intent: {noted}"


def test_a_failing_intent_sink_fails_the_advance_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mission = _door_mission(tmp_path, monkeypatch, "01M5686F")
    target_before = _rev(mission.repo, mission.target_branch)

    def _unwritable(*_a: Any, **_k: Any) -> None:
        raise OSError("state.json unwritable")

    monkeypatch.setattr(rollback, "note_advance_intent", _unwritable)

    with pytest.raises(OSError, match="unwritable"):
        _consolidate(mission)

    assert _rev(mission.repo, mission.target_branch) == target_before, "no advance without a persisted intent"


def test_pass_settles_the_target_once_the_span_completed_and_a_resume_is_not_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """T014: after a PASS whose push then fails, the target is settled and a --resume runs to completion."""
    mission = _door_mission(tmp_path, monkeypatch, "01M5686P")
    real_push = executor._phase_push

    def _rejected(run: Any) -> None:
        raise RuntimeError("push rejected")

    monkeypatch.setattr(executor, "_phase_push", _rejected)
    with pytest.raises(RuntimeError, match="push rejected"):
        _consolidate(mission)

    state = load_state(mission.repo, mission.mission_id)
    assert state is not None, "a post-span failure keeps the record"
    assert mission.target_branch not in state.unsettled_refs, "the PASS settled the target"
    assert mission.target_branch not in state.advance_intents
    assert set(state.unsettled_refs) == set(rollback.run_movable_branches(state)) - {mission.target_branch}

    monkeypatch.setattr(executor, "_phase_push", real_push)
    capsys.readouterr()
    _consolidate(mission)

    assert "UNEXPLAINED_BRANCH_MOVE" not in capsys.readouterr().out
    assert load_state(mission.repo, mission.mission_id) is None, "the resumed run completes and clears the record"


def test_projection_refusal_after_the_pass_does_not_settle_the_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Post-tasks squad HIGH: the settle happens only once the WHOLE door span completed."""
    mission = _door_mission(tmp_path, monkeypatch, "01M5686R")
    settled: list[str] = []
    real = rollback.settle_branch

    def spy(repo: Path, state: Any, branch: str) -> None:
        settled.append(branch)
        real(repo, state, branch)

    monkeypatch.setattr(rollback, "settle_branch", spy)
    _raise_after(monkeypatch, "_phase_reconcile_before_teardown", typer.Exit(1))

    with pytest.raises(typer.Exit):
        _consolidate(mission)

    assert mission.target_branch not in settled, "a failure at the end of the span must never settle the target"


def test_precheck_never_refuses_a_verified_landing(tmp_path: Path) -> None:
    """#5021 / #5570: a PASS that still holds for the live target is never rolled back, so its resume is not refused."""
    env = make_env(tmp_path)
    landed = _unrecorded_target_move(env)
    env.state.reconciliation_passed_target_sha = landed
    save_state(env.state, env.repo)

    tips = executor._refuse_unexplained_branch_moves(env.repo, "M1")

    assert tips[_TARGET] == landed


def test_claim_never_refuses_a_verified_landing_on_resume(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    landed = _unrecorded_target_move(env)
    env.state.reconciliation_passed_target_sha = landed
    run = _run_for(env, is_resume=True)
    before = _state_bytes(env)

    phase_claim._capture_snapshot_and_begin_attempt(run)

    assert _state_bytes(env) == before, "begin_attempt still changes nothing for the unexplained branch"


def _verified_landing_with_an_unexplained_mission_branch(env: Env) -> str:
    """The target sits at its PASS anchor while the mission branch carries a move the record cannot explain."""
    _begin(env)
    _advance_run(env)
    env.state.reconciliation_passed_target_sha = _rev(env.repo, _TARGET)
    save_state(env.state, env.repo)
    return _commit_on(env.repo, _MISSION_BRANCH, "unexplained-on-mission")


def test_precheck_refuses_an_unexplained_mission_branch_move_even_at_the_pass_anchor(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """F1 (pre-consolidate squad): the PASS anchor exempts only the target and coordination rows.

    Teardown deletes a non-coordination mission branch with a live-tip CAS, so an
    exempted unexplained mission-branch move would be deleted at exit 0.
    """
    env = make_env(tmp_path)
    moved = _verified_landing_with_an_unexplained_mission_branch(env)
    before = _state_bytes(env)

    with pytest.raises(typer.Exit) as excinfo:
        executor._refuse_unexplained_branch_moves(env.repo, "M1")

    output = " ".join(capsys.readouterr().out.split())
    assert excinfo.value.exit_code == 1 and output.endswith(_ERROR_CODE_LINE), output
    assert _MISSION_BRANCH in output and moved in output
    assert _state_bytes(env) == before, "the pre-check writes nothing"


_COORD = "kitty/coord-x"


def _verified_landing_with_an_unexplained_coordination_move(env: Env) -> str:
    """The target sits at its PASS anchor while the coordination branch carries a move the record cannot explain."""
    _git(env.repo, "branch", _COORD)
    env.state.pre_mutation_coord_ref = _COORD
    phase_claim._capture_snapshot_and_begin_attempt(_run_for(env, coord_ref=_COORD))
    _advance_run(env)
    env.state.reconciliation_passed_target_sha = _rev(env.repo, _TARGET)
    save_state(env.state, env.repo)
    return _commit_on(env.repo, _COORD, "late-coordination-commit")


def test_precheck_exempts_an_unexplained_coordination_move_at_the_pass_anchor(tmp_path: Path) -> None:
    """F1: the coordination row stays exempt (the late-commit landing and the teardown gate protect it, #5570)."""
    env = make_env(tmp_path)
    moved = _verified_landing_with_an_unexplained_coordination_move(env)
    before = _state_bytes(env)

    tips = executor._refuse_unexplained_branch_moves(env.repo, "M1")

    assert tips[_COORD] == moved
    assert _state_bytes(env) == before, "the pre-check writes nothing"


def test_precheck_refuses_the_same_move_once_the_target_left_the_pass_anchor(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Negative case: a foreign target commit ends the exemption, so the unexplained mission move refuses again."""
    env = make_env(tmp_path)
    moved = _verified_landing_with_an_unexplained_mission_branch(env)
    _commit_on(env.repo, _TARGET, "foreign-after-pass")

    with pytest.raises(typer.Exit) as excinfo:
        executor._refuse_unexplained_branch_moves(env.repo, "M1")

    output = " ".join(capsys.readouterr().out.split())
    assert excinfo.value.exit_code == 1 and output.endswith(_ERROR_CODE_LINE), output
    assert _MISSION_BRANCH in output and moved in output


def test_claim_refuses_an_unexplained_mission_branch_move_even_at_the_pass_anchor(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """F1: the claim narrows the PASS-anchor exemption exactly like the pre-check."""
    env = make_env(tmp_path)
    moved = _verified_landing_with_an_unexplained_mission_branch(env)
    run = _run_for(env, is_resume=True)
    before = _state_bytes(env)

    with pytest.raises(typer.Exit) as excinfo:
        phase_claim._capture_snapshot_and_begin_attempt(run)

    output = " ".join(capsys.readouterr().out.split())
    assert excinfo.value.exit_code == 1 and output.endswith(_ERROR_CODE_LINE), output
    assert _MISSION_BRANCH in output and moved in output
    assert _state_bytes(env) == before, "begin_attempt changes nothing when it refuses"


def test_claim_exempts_an_unexplained_coordination_move_at_the_pass_anchor(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    _verified_landing_with_an_unexplained_coordination_move(env)
    run = _run_for(env, coord_ref=_COORD, is_resume=True)
    before = _state_bytes(env)

    phase_claim._capture_snapshot_and_begin_attempt(run)

    assert _state_bytes(env) == before, "begin_attempt writes nothing for the unexplained branch"


def test_claim_refuses_the_same_move_once_the_target_left_the_pass_anchor(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    env = make_env(tmp_path)
    moved = _verified_landing_with_an_unexplained_mission_branch(env)
    _commit_on(env.repo, _TARGET, "foreign-after-pass")
    run = _run_for(env, is_resume=True)
    before = _state_bytes(env)

    with pytest.raises(typer.Exit) as excinfo:
        phase_claim._capture_snapshot_and_begin_attempt(run)

    output = " ".join(capsys.readouterr().out.split())
    assert excinfo.value.exit_code == 1 and _MISSION_BRANCH in output and moved in output, output
    assert _state_bytes(env) == before
