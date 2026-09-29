"""Executor wiring of the single rollback authority (WP03 / T013-T015).

* T013: the snapshot is captured once at the end of the claim and every attempt
  begins with ``begin_attempt``; a missing lane branch is warned about.
* T014: post-mutation tips are recorded by every mutating phase (before ANY exit,
  early return or exception) and by the in-phase rollbacks.
* T015: ``_report_rollback`` resets THIS call's own PASS anchor before invoking
  the authority (post-tasks BLOCKER 1) while an EARLIER attempt's anchor still
  keeps a verified landing (FR-011); the resume short-circuit predicate is the
  single ``reconciliation_passed_for_tip``.

Real temp git repos; nothing about git is mocked (only ``console`` output capture).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from specify_cli.consolidation import executor
from specify_cli.consolidation import rollback
from specify_cli.consolidation.rollback import record_post_mutation_tips
from specify_cli.git.ref_advance import RefAdvanceError, RefRestoreError
from specify_cli.consolidation.state import load_state
from tests.consolidation.test_rollback_authority import _MISSION_BRANCH, _TARGET, Env, _advance_run, _git, _rev, make_env

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
    _advance_run(env)

    executor._capture_snapshot_and_begin_attempt(_run_for(env, is_resume=True))

    assert env.state.pre_mutation_refs == first, "a resume must reuse the persisted snapshot"
    assert env.state.restore_targets[_TARGET] == first[_TARGET], "consolidation's own advance is undone to the snapshot"
    assert env.state.post_mutation_refs == {}, "every attempt resets its post tips"


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
    assert env.state.post_mutation_refs == _live(env)
    assert load_state(env.repo, "M1").post_mutation_refs == _live(env)  # type: ignore[union-attr]


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
        "_rollback_to_pre_mutation_checkpoint",
        "_restore_and_guard_coord_coherence",
    ],
)
def test_mutating_phases_and_in_phase_rollbacks_are_recorders(name: str) -> None:
    fn = getattr(executor, name)
    assert getattr(fn, "__wrapped__", None) is not None, f"{name} must be wrapped by _records_post_mutation_tips"


def test_restore_pre_target_if_at_baseline_records(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = make_env(tmp_path)
    run = _begin(env)
    run.done_marked_before_target = False
    run.target_baseline_sha = _rev(env.repo, _TARGET)
    monkeypatch.setattr(executor, "_revert_orphan_target_bake_commit", lambda r: _advance_run_target_only(env))

    executor._restore_pre_target_if_at_baseline(run)

    assert env.state.post_mutation_refs == _live(env)


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
                checks[name] = state.post_mutation_refs == live

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
