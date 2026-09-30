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

from specify_cli.consolidation import executor
from specify_cli.consolidation import rollback
from specify_cli.consolidation.rollback import record_post_mutation_tips
from specify_cli.git.ref_advance import RefAdvanceError, RefRestoreError
from specify_cli.consolidation.state import get_state_path, load_state, save_state
from tests.consolidation.test_rollback_authority import _MISSION_BRANCH, _TARGET, Env, _advance_run, _commit_on, _git, _rev, make_env

pytestmark = [pytest.mark.git_repo, pytest.mark.fast]


def _run_for(env: Env, *, coord_ref: str | None = None, is_resume: bool = False) -> Any:
    ref = coord_ref or _TARGET  # LANES: the coordination checkpoint resolves to the target itself
    checkpoint = executor._CoordCheckpoint(ref=ref, sha=_rev(env.repo, ref))
    return SimpleNamespace(main_repo=env.repo, state=env.state, lanes_manifest=env.manifest, coord_checkpoint=checkpoint, is_resume=is_resume)


# ------------------------------------------------------------------- T013


def test_lanes_snapshot_keys_are_target_mission_and_lanes_without_duplicates(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    run = _run_for(env)  # LANES: the coordination checkpoint resolves to the target itself

    executor._capture_snapshot_and_begin_attempt(run)

    assert sorted(env.state.pre_mutation_refs) == sorted({_TARGET, _MISSION_BRANCH, *env.lane_branches})
    assert env.state.restore_targets == env.state.pre_mutation_refs, "begin_attempt must fix this attempt's restore targets"
    assert env.state.post_mutation_refs == {}


def test_snapshot_is_captured_once_and_reused_by_a_resume(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    executor._capture_snapshot_and_begin_attempt(_run_for(env))
    first = dict(env.state.pre_mutation_refs)
    posts = _advance_run(env)

    executor._capture_snapshot_and_begin_attempt(_run_for(env, is_resume=True))

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
    monkeypatch.setattr(executor, "console", console)

    executor._capture_snapshot_and_begin_attempt(_run_for(env))

    printed = " ".join(str(call.args[0]) for call in console.print.call_args_list)
    assert env.lane_branches[0] in printed and "not snapshotted" in printed
    assert env.lane_branches[0] not in env.state.pre_mutation_refs


# ------------------------------------------------------------------- T014


def _live(env: Env) -> dict[str, str]:
    return {b: _rev(env.repo, b) for b in env.state.pre_mutation_refs}


def _begin(env: Env) -> Any:
    run = _run_for(env)
    executor._capture_snapshot_and_begin_attempt(run)
    return run


def test_phase_decorator_records_after_a_normal_return(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    run = _begin(env)

    @executor._records_post_mutation_tips
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

    @executor._records_post_mutation_tips
    def phase(r: Any) -> None:
        _advance_run_target_only(env)
        return

    phase(run)
    assert env.state.post_mutation_refs[_TARGET] == _rev(env.repo, _TARGET)


def test_phase_decorator_records_when_the_phase_raises(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    run = _begin(env)

    @executor._records_post_mutation_tips
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

    @executor._records_post_mutation_tips
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

    @executor._records_post_mutation_tips
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

    @executor._records_post_mutation_tips
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

    @executor._records_post_mutation_tips
    def phase_a(r: Any) -> None:
        _advance_run_target_only(env)

    @executor._records_post_mutation_tips
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

    @executor._records_post_mutation_tips
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

    @executor._records_post_mutation_tips
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
    fn = getattr(executor, name)
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

    executor._restore_pre_target_if_at_baseline(run)

    assert getattr(executor._restore_pre_target_if_at_baseline, "__wrapped__", None) is None, "it moves no ref, so it records none"
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

    executor._restore_and_guard_coord_coherence(run, {state_path: stale_bytes})

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
    monkeypatch.setattr(executor, "console", console)

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
    monkeypatch.setattr(executor, "console", console)

    executor._report_rollback(run, anchor_before=landed)

    assert _rev(env.repo, _TARGET) == landed
    assert run.state.reconciliation_passed_target_sha == landed
    assert "Kept the landing" in str(console.print.call_args_list[-1].args[0])


def test_report_rollback_reports_a_failing_authority_and_lets_the_exit_propagate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = make_env(tmp_path)
    run = _report_run(env)
    console = MagicMock()
    monkeypatch.setattr(executor, "console", console)

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
    monkeypatch.setattr(executor, "console", console)
    authority = MagicMock()
    monkeypatch.setattr(rollback, "rollback_to_snapshot", authority)

    def _unwritable(*_a: Any, **_k: Any) -> None:
        raise OSError("read-only state dir")

    monkeypatch.setattr(executor, "save_state", _unwritable)

    executor._report_rollback(run, anchor_before=None)  # must not raise

    printed = str(console.print.call_args_list[-1].args[0])
    assert "Rollback could not complete" in printed and "read-only state dir" in printed
    authority.assert_not_called()


def test_report_rollback_survives_a_second_interrupt_during_the_rollback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A Ctrl-C while the rollback runs is reported, never raised in place of the original error."""
    env = make_env(tmp_path)
    run = _report_run(env)
    console = MagicMock()
    monkeypatch.setattr(executor, "console", console)

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
