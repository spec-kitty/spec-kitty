"""Focused coverage for the merge executor phase helpers (mission #2057, NFR-002).

Post-review note: the executor seam fell below the NFR-002 >=90% line-coverage
bar — its error-recovery / cleanup / banner branches were exercised only through
broad integration tests, not directly. These tests drive each phase helper with
a real ``_MergeRunState`` and mocked git/IO boundaries so every restore-on-error,
skip, and fail-loud branch is hit (each test fails if its target branch is
removed). Behaviour-preserving: no executor source is modified.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import typer

from specify_cli.merge import executor as ex
from specify_cli.merge.state import MergeState
from specify_cli.post_merge.stale_assertions import (
    Confidence,
    StaleAssertionFinding,
    StaleAssertionReport,
)

pytestmark = pytest.mark.fast


def _make_run(
    tmp_path: Path,
    *,
    done_marked_before_target: bool = False,
    planning_artifact_only: bool = False,
    is_resume: bool = False,
    push: bool = False,
    remove_worktree: bool = True,
    delete_branch: bool = True,
    teardown_coordination: bool | None = None,
) -> ex._MergeRunState:
    lanes_manifest = SimpleNamespace(
        target_branch="main",
        mission_branch="kitty/mission-m",
        lanes=[SimpleNamespace(lane_id="lane-a", wp_ids=["WP01"])],
    )
    state = MergeState(
        mission_id="01ID", mission_slug="m", target_branch="main", wp_order=["WP01"]
    )
    # #3131: mirrors resolve_merge_retention's coupling rule (delete_branch AND
    # remove_worktree) so existing call sites that already pass both True keep
    # exercising the coord-teardown gate without every call site needing an
    # explicit teardown_coordination= kwarg.
    resolved_teardown_coordination = (
        (delete_branch and remove_worktree)
        if teardown_coordination is None
        else teardown_coordination
    )
    run = ex._MergeRunState(
        main_repo=tmp_path,
        mission_slug="m",
        canonical_id="01ID",
        canonical_mission_id="01JQANARZAP70V8DVJZ8XN0M3T",
        feature_dir=tmp_path / "kitty-specs" / "m",
        target_feature_dir=tmp_path / "kitty-specs" / "m",
        lanes_manifest=lanes_manifest,
        all_wp_ids=["WP01"],
        push=push,
        delete_branch=delete_branch,
        remove_worktree=remove_worktree,
        teardown_coordination=resolved_teardown_coordination,
        strategy=ex.MergeStrategy.SQUASH,
        assume_yes=True,
        planning_artifact_only=planning_artifact_only,
        state=state,
        is_resume=is_resume,
        done_marked_before_target=done_marked_before_target,
    )
    run.canonical_events_path = tmp_path / "kitty-specs" / "m" / "status.events.jsonl"
    run.canonical_status_path = tmp_path / "kitty-specs" / "m" / "status.json"
    run.merge_state_path = tmp_path / "state.json"
    run.target_baseline_sha = "abc123"
    run.baseline_mission_id = "01ID"
    return run


# --- _phase_gates_and_state -------------------------------------------------


def test_phase_gates_exits_when_gates_fail(tmp_path: Path) -> None:
    run = _make_run(tmp_path)
    gate = SimpleNamespace(verdict="fail", blocking=True, gate_name="g", details="d")
    gate_eval = SimpleNamespace(gates=[gate], overall_pass=False)
    with (
        patch("specify_cli.policy.config.load_policy_config", return_value=SimpleNamespace(merge_gates=[])),
        patch("specify_cli.policy.merge_gates.evaluate_merge_gates", return_value=gate_eval),
        pytest.raises(typer.Exit) as exc,
    ):
        ex._phase_gates_and_state(run)
    assert exc.value.exit_code == 1


def test_phase_gates_passes_and_prints_resume_banner(tmp_path: Path) -> None:
    run = _make_run(tmp_path, is_resume=True)
    run.state.completed_wps = []
    # terminus-safety-invariant-01M2XFT7 FOLD-F3: ``_phase_gates_and_state``
    # now runs the UNCONDITIONAL ``_assert_mission_terminal_ready``
    # precondition first (T007) — a WP absent from the reduced snapshot
    # refuses (FOLD-F3's fail-closed fix), so this fixture must seed a real
    # acceptable-ending event for WP01 to reach the gate-eval/history/hollow
    # wiring this test actually targets.
    run.feature_dir.mkdir(parents=True, exist_ok=True)
    (run.feature_dir / "status.events.jsonl").write_text(
        json.dumps(
            {
                "actor": "reviewer-renata",
                "at": "2026-09-19T00:00:00+00:00",
                "event_id": "01HXYZEXEC0000000000000001",
                "evidence": None,
                "execution_mode": "worktree",
                "feature_slug": "m",
                "force": False,
                "from_lane": "in_review",
                "reason": None,
                "review_ref": "review-WP01",
                "to_lane": "approved",
                "wp_id": "WP01",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    gate = SimpleNamespace(verdict="pass", blocking=False, gate_name="g", details="ok")
    gate_eval = SimpleNamespace(gates=[gate], overall_pass=True)
    with (
        patch("specify_cli.policy.config.load_policy_config", return_value=SimpleNamespace(merge_gates=[])),
        patch("specify_cli.policy.merge_gates.evaluate_merge_gates", return_value=gate_eval),
        patch.object(ex, "_enforce_canonical_status_history") as hist_mock,
        patch.object(ex, "_warn_or_confirm_hollow_reviews") as hollow_mock,
    ):
        ex._phase_gates_and_state(run)
    hist_mock.assert_called_once()
    hollow_mock.assert_called_once()


# --- _phase_merge_lanes -----------------------------------------------------


def test_phase_merge_lanes_skips_already_integrated(tmp_path: Path) -> None:
    run = _make_run(tmp_path)
    with (
        patch("specify_cli.lanes.branch_naming.lane_branch_name", return_value="kitty/lane-a"),
        patch("specify_cli.lanes.compute.is_planning_lane", return_value=False),
        patch.object(ex, "_lane_already_integrated", return_value=True),
        patch("specify_cli.lanes.merge.consolidate_lane_into_mission") as merge_mock,
    ):
        ex._phase_merge_lanes(run)
    merge_mock.assert_not_called()
    assert run.any_lane_had_unintegrated_code is False


def test_phase_merge_lanes_success_marks_unintegrated(tmp_path: Path) -> None:
    run = _make_run(tmp_path)
    result = SimpleNamespace(success=True, errors=[])
    with (
        patch("specify_cli.lanes.branch_naming.lane_branch_name", return_value="kitty/lane-a"),
        patch("specify_cli.lanes.compute.is_planning_lane", return_value=False),
        patch.object(ex, "_lane_already_integrated", return_value=False),
        patch("specify_cli.lanes.merge.consolidate_lane_into_mission", return_value=result),
    ):
        ex._phase_merge_lanes(run)
    assert run.any_lane_had_unintegrated_code is True


def test_phase_merge_lanes_resume_tolerates_already_merged(tmp_path: Path) -> None:
    run = _make_run(tmp_path, is_resume=True)
    result = SimpleNamespace(success=False, errors=["lane already up to date"])
    with (
        patch("specify_cli.lanes.branch_naming.lane_branch_name", return_value="kitty/lane-a"),
        patch("specify_cli.lanes.compute.is_planning_lane", return_value=False),
        patch.object(ex, "_lane_already_integrated", return_value=False),
        patch("specify_cli.lanes.merge.consolidate_lane_into_mission", return_value=result),
    ):
        # No Exit raised because resume + "already" error is tolerated.
        ex._phase_merge_lanes(run)


def test_phase_merge_lanes_hard_failure_exits(tmp_path: Path) -> None:
    run = _make_run(tmp_path, is_resume=False)
    result = SimpleNamespace(success=False, errors=["conflict in foo.py"])
    with (
        patch("specify_cli.lanes.branch_naming.lane_branch_name", return_value="kitty/lane-a"),
        patch("specify_cli.lanes.compute.is_planning_lane", return_value=False),
        patch.object(ex, "_lane_already_integrated", return_value=False),
        patch("specify_cli.lanes.merge.consolidate_lane_into_mission", return_value=result),
        pytest.raises(typer.Exit) as exc,
    ):
        ex._phase_merge_lanes(run)
    assert exc.value.exit_code == 1


def test_phase_merge_lanes_planning_lane_already_on_target(tmp_path: Path) -> None:
    run = _make_run(tmp_path, planning_artifact_only=True)
    with (
        patch("specify_cli.lanes.compute.is_planning_lane", return_value=True),
        patch("specify_cli.lanes.merge.consolidate_lane_into_mission") as merge_mock,
    ):
        ex._phase_merge_lanes(run)
    merge_mock.assert_not_called()


# --- _phase_baseline_and_surface --------------------------------------------


def test_phase_baseline_and_surface_resolves_paths(tmp_path: Path) -> None:
    run = _make_run(tmp_path)
    surface = tmp_path / ".worktrees" / "m-coord" / "kitty-specs" / "m" / "status.events.jsonl"
    with (
        patch.object(ex, "run_command", return_value=(0, "deadbeef\n", "")),
        patch.object(ex, "resolve_mission_identity", return_value=SimpleNamespace(mission_id="01XID")),
        patch.object(ex, "resolve_status_surface", return_value=surface),
        patch.object(ex, "is_under_worktrees_segment", return_value=True),
        patch.object(ex, "get_state_path", return_value=tmp_path / "state.json"),
    ):
        ex._phase_baseline_and_surface(run)
    assert run.target_baseline_sha == "deadbeef"
    assert run.baseline_mission_id == "01XID"
    assert run.done_marked_before_target is True
    assert run.canonical_events_path == surface


def test_phase_baseline_and_surface_handles_missing_identity(tmp_path: Path) -> None:
    run = _make_run(tmp_path)
    surface = tmp_path / "kitty-specs" / "m" / "status.events.jsonl"
    with (
        patch.object(ex, "run_command", return_value=(1, "", "fatal")),
        patch.object(ex, "resolve_mission_identity", side_effect=ValueError("no meta")),
        patch.object(ex, "resolve_status_surface", return_value=surface),
        patch.object(ex, "is_under_worktrees_segment", return_value=False),
        patch.object(ex, "get_state_path", return_value=tmp_path / "state.json"),
    ):
        ex._phase_baseline_and_surface(run)
    # git rev-parse failed -> baseline falls back to HEAD~1.
    assert run.target_baseline_sha == "HEAD~1"
    assert run.baseline_mission_id is None
    assert run.done_marked_before_target is False


# --- _phase_bake_and_pre_target_done ----------------------------------------


def test_phase_bake_planning_only_short_circuits(tmp_path: Path) -> None:
    run = _make_run(tmp_path, planning_artifact_only=True)
    with patch.object(ex, "_bake_mission_number_into_mission_branch") as bake_mock:
        ex._phase_bake_and_pre_target_done(run)
    bake_mock.assert_not_called()
    assert run.mission_already_applied is True


def test_phase_bake_pre_target_done_restores_on_record_failure(tmp_path: Path) -> None:
    run = _make_run(tmp_path, done_marked_before_target=True)
    restored: list[dict[Path, bytes | None]] = []
    with (
        patch.object(ex, "_bake_mission_number_into_mission_branch", return_value=None),
        patch.object(ex, "_capture_merge_snapshots", return_value={tmp_path / "x": b"o"}),
        patch.object(ex, "_record_merged_wps_done_for_merge", side_effect=RuntimeError("boom")),
        patch.object(ex, "restore_generated_artifact_snapshots", side_effect=lambda s: restored.append(s)),
        pytest.raises(RuntimeError, match="boom"),
    ):
        ex._phase_bake_and_pre_target_done(run)
    assert restored == [{tmp_path / "x": b"o"}]


def test_phase_bake_pre_target_done_success_records(tmp_path: Path) -> None:
    run = _make_run(tmp_path, done_marked_before_target=True)
    with (
        patch.object(ex, "_bake_mission_number_into_mission_branch", return_value=None),
        patch.object(ex, "_capture_merge_snapshots", return_value={}),
        patch.object(ex, "_record_merged_wps_done_for_merge") as record_mock,
    ):
        ex._phase_bake_and_pre_target_done(run)
    record_mock.assert_called_once()


# --- _phase_mission_to_target / _handle_mission_merge_result ----------------


def test_phase_mission_to_target_planning_only_returns(tmp_path: Path) -> None:
    run = _make_run(tmp_path, planning_artifact_only=True)
    with patch("specify_cli.lanes.merge.integrate_mission_into_target") as merge_mock:
        ex._phase_mission_to_target(run)
    merge_mock.assert_not_called()


def test_phase_mission_to_target_restores_on_exception(tmp_path: Path) -> None:
    run = _make_run(tmp_path)
    restored: list[object] = []
    with (
        patch.object(ex, "_branch_trees_equal", return_value=False),
        patch("specify_cli.lanes.merge.integrate_mission_into_target", side_effect=RuntimeError("merge died")),
        patch.object(ex, "_restore_pre_target_if_at_baseline", side_effect=lambda r: restored.append(r)),
        pytest.raises(RuntimeError, match="merge died"),
    ):
        ex._phase_mission_to_target(run)
    assert restored == [run]


def test_phase_mission_to_target_success(tmp_path: Path) -> None:
    run = _make_run(tmp_path)
    result = SimpleNamespace(success=True, errors=[], commit="abcdef1234", already_applied=False)
    with (
        patch.object(ex, "_branch_trees_equal", return_value=False),
        patch("specify_cli.lanes.merge.integrate_mission_into_target", return_value=result),
    ):
        ex._phase_mission_to_target(run)
    assert run.mission_already_applied is False


def test_handle_result_rejects_zero_diff_noop_squash(tmp_path: Path) -> None:
    run = _make_run(tmp_path)
    run.any_lane_had_unintegrated_code = True
    result = SimpleNamespace(success=True, errors=[], commit=None, already_applied=True)
    with (
        patch.object(ex, "_restore_pre_target_if_at_baseline") as restore_mock,
        pytest.raises(typer.Exit) as exc,
    ):
        ex._handle_mission_merge_result(
            run, result, mission_integrated_into_target=False
        )
    assert exc.value.exit_code == 1
    restore_mock.assert_called_once_with(run)


def test_handle_result_resume_tolerates_already_merged(tmp_path: Path) -> None:
    run = _make_run(tmp_path, is_resume=True)
    result = SimpleNamespace(success=False, errors=["already up to date"], commit=None, already_applied=False)
    # No Exit because resume tolerates the already-merged error.
    ex._handle_mission_merge_result(run, result, mission_integrated_into_target=True)


def test_handle_result_resume_never_tolerates_content_conflict(tmp_path: Path) -> None:
    """#4892: a real target-content conflict must fail closed even on resume.

    The conflicting path literally contains "already" — the substring the resume
    tolerance keys on. Before the fix, resume read it as "already merged" and
    continued to done-marking/cleanup while the target never moved. Now the
    structured ``conflicting_paths`` field forces a fail-closed exit and the
    shared ``TARGET_BRANCH_CONTENT_CONFLICT`` diagnostic.
    """
    run = _make_run(tmp_path, is_resume=True)
    result = SimpleNamespace(
        success=False,
        errors=["Squash merge failed: unresolved content conflict(s): tests/test_already_applied.py"],
        commit=None,
        already_applied=False,
        conflicting_paths=("tests/test_already_applied.py",),
        diagnostic_code="TARGET_BRANCH_CONTENT_CONFLICT",
    )
    with (
        patch.object(ex, "_restore_pre_target_if_at_baseline") as restore_mock,
        pytest.raises(typer.Exit) as exc,
    ):
        ex._handle_mission_merge_result(run, result, mission_integrated_into_target=False)
    assert exc.value.exit_code == 1
    restore_mock.assert_called_once_with(run)


def test_emit_mission_target_content_conflict_reports_shared_code(tmp_path: Path, capsys) -> None:
    """The real merge prints the SAME diagnostic code the ``--dry-run`` forecast does."""
    run = _make_run(tmp_path)
    result = SimpleNamespace(
        success=False,
        errors=["unresolved content conflict(s): src/shared.py"],
        commit=None,
        already_applied=False,
        conflicting_paths=("src/shared.py",),
        diagnostic_code="TARGET_BRANCH_CONTENT_CONFLICT",
    )
    ex._emit_mission_target_content_conflict(run, result)
    out = capsys.readouterr().out
    assert "TARGET_BRANCH_CONTENT_CONFLICT" in out
    assert "src/shared.py" in out
    assert "remediation:" in out


def test_handle_result_hard_failure_restores_and_exits(tmp_path: Path) -> None:
    run = _make_run(tmp_path, is_resume=False)
    result = SimpleNamespace(success=False, errors=["real conflict"], commit=None, already_applied=False)
    with (
        patch.object(ex, "_restore_pre_target_if_at_baseline") as restore_mock,
        pytest.raises(typer.Exit) as exc,
    ):
        ex._handle_mission_merge_result(run, result, mission_integrated_into_target=False)
    assert exc.value.exit_code == 1
    restore_mock.assert_called_once_with(run)


# --- _restore_pre_target_if_at_baseline -------------------------------------


def test_restore_pre_target_restores_only_when_at_baseline(tmp_path: Path) -> None:
    run = _make_run(tmp_path, done_marked_before_target=True)
    run.pre_target_bookkeeping_snapshots = {tmp_path / "x": b"o"}
    restored: list[object] = []
    with (
        patch.object(ex, "_target_branch_still_at_baseline", return_value=True),
        patch.object(ex, "restore_generated_artifact_snapshots", side_effect=lambda s: restored.append(s)),
    ):
        ex._restore_pre_target_if_at_baseline(run)
    assert restored == [{tmp_path / "x": b"o"}]


def test_restore_pre_target_noop_when_target_advanced(tmp_path: Path) -> None:
    run = _make_run(tmp_path, done_marked_before_target=True)
    with (
        patch.object(ex, "_target_branch_still_at_baseline", return_value=False),
        patch.object(ex, "restore_generated_artifact_snapshots") as restore_mock,
    ):
        ex._restore_pre_target_if_at_baseline(run)
    restore_mock.assert_not_called()


# --- _phase_record_done_and_project -----------------------------------------


def test_phase_record_done_restores_on_record_failure(tmp_path: Path) -> None:
    run = _make_run(tmp_path, done_marked_before_target=False)
    run.final_bookkeeping_snapshots = {tmp_path / "x": b"o"}
    restored: list[object] = []
    with (
        patch.object(ex, "_record_merged_wps_done_for_merge", side_effect=RuntimeError("boom")),
        patch.object(ex, "restore_generated_artifact_snapshots", side_effect=lambda s: restored.append(s)),
        pytest.raises(RuntimeError, match="boom"),
    ):
        ex._phase_record_done_and_project(run)
    assert restored == [{tmp_path / "x": b"o"}]


def test_phase_record_done_restores_on_project_failure(tmp_path: Path) -> None:
    run = _make_run(tmp_path, done_marked_before_target=True)  # skip record path
    run.final_bookkeeping_snapshots = {tmp_path / "x": b"o"}
    restored: list[object] = []
    with (
        patch.object(ex, "_project_status_bookkeeping_to_target", side_effect=RuntimeError("proj")),
        patch.object(ex, "restore_generated_artifact_snapshots", side_effect=lambda s: restored.append(s)),
        pytest.raises(RuntimeError, match="proj"),
    ):
        ex._phase_record_done_and_project(run)
    assert restored == [{tmp_path / "x": b"o"}]


def test_phase_record_done_success_sets_target_paths(tmp_path: Path) -> None:
    run = _make_run(tmp_path, done_marked_before_target=True)
    events_p = tmp_path / "e.jsonl"
    status_p = tmp_path / "s.json"
    with patch.object(ex, "_project_status_bookkeeping_to_target", return_value=(events_p, status_p)):
        ex._phase_record_done_and_project(run)
    assert run.target_events_path == events_p
    assert run.target_status_path == status_p


# --- _phase_porcelain_invariant: git-status-failed skip ----------------------


def test_phase_porcelain_skips_when_git_status_fails(tmp_path: Path) -> None:
    run = _make_run(tmp_path)
    with (
        patch.object(ex, "_raw_porcelain_status", return_value=(1, "")),
        patch.object(ex, "restore_generated_artifact_snapshots") as restore_mock,
    ):
        ex._phase_porcelain_invariant(run)
    restore_mock.assert_not_called()


def test_phase_porcelain_clean_tree_passes(tmp_path: Path) -> None:
    run = _make_run(tmp_path)
    with (
        patch.object(ex, "_raw_porcelain_status", return_value=(0, "")),
        patch.object(ex, "_classify_porcelain_lines", return_value=([], 0)),
        patch.object(ex, "restore_generated_artifact_snapshots") as restore_mock,
    ):
        ex._phase_porcelain_invariant(run)
    restore_mock.assert_not_called()


# --- #2804/FR-009: gate-artifact preservation guard --------------------------
#
# 2026-08-07 (landing fix, verdict-seam-write-unification #3245, Fix 7):
# diff-coverage flagged the divergent-artifact RESTORE branch of
# ``_restore_regressed_gate_artifacts`` and the ``expected_paths`` fold inside
# ``_phase_porcelain_invariant`` as new-code-uncovered. Both tests below drive
# the REAL functions (no mocking of the branch under test) so the fold's
# actual effect on ``_classify_porcelain_lines``' verdict is proven, not
# merely exercised.


def test_restore_regressed_gate_artifacts_restores_divergent_target_copy(
    tmp_path: Path,
) -> None:
    """#2804: an already-accepted target gate artifact that the squash merge's
    ``-X theirs`` resolution clobbered is restored verbatim, and the path is
    recorded on ``run.gate_artifact_restored_paths`` for the caller to fold
    into the final bookkeeping commit + the porcelain-invariant gate."""
    run = _make_run(tmp_path)
    clobbered_path = run.target_feature_dir / "acceptance-matrix.json"
    clobbered_path.parent.mkdir(parents=True, exist_ok=True)
    clobbered_path.write_bytes(b'{"clobbered": true}')
    untouched_path = run.target_feature_dir / "issue-matrix.json"
    run.pre_target_gate_artifact_snapshots = {
        clobbered_path: b'{"accepted": true}',
        # Ordinary, non-divergent leg: target held nothing here pre-merge, so
        # the squash merge's output is authoritative -- no restore.
        untouched_path: None,
    }

    ex._restore_regressed_gate_artifacts(run)

    assert clobbered_path.read_bytes() == b'{"accepted": true}'
    assert run.gate_artifact_restored_paths == [clobbered_path]
    assert not untouched_path.exists()


def test_restore_regressed_gate_artifacts_noop_when_current_matches_original(
    tmp_path: Path,
) -> None:
    """The ordinary, non-divergent case: the squash merge preserved the
    pre-merge bytes verbatim, so no restore/record happens."""
    run = _make_run(tmp_path)
    matching_path = run.target_feature_dir / "acceptance-matrix.json"
    matching_path.parent.mkdir(parents=True, exist_ok=True)
    matching_path.write_bytes(b'{"accepted": true}')
    run.pre_target_gate_artifact_snapshots = {matching_path: b'{"accepted": true}'}

    ex._restore_regressed_gate_artifacts(run)

    assert matching_path.read_bytes() == b'{"accepted": true}'
    assert run.gate_artifact_restored_paths == []


def test_phase_porcelain_folds_restored_gate_artifact_into_expected_paths(
    tmp_path: Path,
) -> None:
    """#2804/FR-009: a path the restore guard rewrote is an EXPECTED
    post-merge delta -- the porcelain-invariant gate must not treat it as a
    violation. Uses the REAL ``_classify_porcelain_lines`` (not mocked) so the
    ``expected_paths`` fold is what actually suppresses the flag; the
    restored path is deliberately NOT a real mission-artifact kind, so
    neither the coord-residue nor the self-bookkeeping legs could
    accidentally absorb it instead -- isolating the fold under test."""
    run = _make_run(tmp_path)
    restored_path = tmp_path / "some" / "random" / "file.json"
    run.gate_artifact_restored_paths = [restored_path]
    with patch.object(
        ex, "_raw_porcelain_status", return_value=(0, " M some/random/file.json")
    ):
        ex._phase_porcelain_invariant(run)  # must not raise typer.Exit


def test_phase_porcelain_flags_unrestored_unexpected_path(tmp_path: Path) -> None:
    """Control for the test above: the SAME porcelain line, with
    ``gate_artifact_restored_paths`` empty, is a genuine violation -- proving
    the fold (not some other leg) is what suppressed it there."""
    run = _make_run(tmp_path)
    with (
        patch.object(
            ex, "_raw_porcelain_status", return_value=(0, " M some/random/file.json")
        ),
        pytest.raises(typer.Exit) as exc,
    ):
        ex._phase_porcelain_invariant(run)
    assert exc.value.exit_code == 1


# --- _phase_commit_and_assert: no-changes + baseline-assert-failure ----------


def test_phase_commit_skips_when_no_bookkeeping_changes(tmp_path: Path) -> None:
    run = _make_run(tmp_path)
    run.target_events_path = tmp_path / "e.jsonl"
    run.target_status_path = tmp_path / "s.json"
    with (
        patch.object(ex, "_paths_have_status_changes", return_value=False),
        patch.object(ex, "commit_merge_bookkeeping") as commit_mock,
        patch.object(ex, "_assert_merged_wps_done_on_target"),
        patch.object(ex, "_assert_baseline_merge_commit_on_target"),
    ):
        ex._phase_commit_and_assert(run)
    commit_mock.assert_not_called()


def test_phase_commit_baseline_assert_failure_exits(tmp_path: Path) -> None:
    run = _make_run(tmp_path)
    run.target_events_path = tmp_path / "e.jsonl"
    run.target_status_path = tmp_path / "s.json"
    with (
        patch.object(ex, "_paths_have_status_changes", return_value=False),
        patch.object(ex, "_assert_merged_wps_done_on_target"),
        patch.object(
            ex,
            "_assert_baseline_merge_commit_on_target",
            side_effect=ex.BaselineMergeCommitError("baseline missing"),
        ),
        pytest.raises(typer.Exit) as exc,
    ):
        ex._phase_commit_and_assert(run)
    assert exc.value.exit_code == 1


def test_phase_commit_recovered_safe_commit_does_not_restore(tmp_path: Path) -> None:
    run = _make_run(tmp_path)
    run.target_events_path = tmp_path / "e.jsonl"
    run.target_status_path = tmp_path / "s.json"
    run.final_bookkeeping_snapshots = {tmp_path / "x": b"o"}
    recovered = ex.SafeCommitRecoveryFailed("recovered")
    recovered.commit_sha = "abc123"
    with (
        patch.object(ex, "_paths_have_status_changes", return_value=True),
        patch.object(ex, "commit_merge_bookkeeping", side_effect=recovered),
        patch.object(ex, "restore_generated_artifact_snapshots") as restore_mock,
        pytest.raises(ex.SafeCommitRecoveryFailed),
    ):
        ex._phase_commit_and_assert(run)
    # A recovered commit (commit_sha set) must NOT restore — the commit landed.
    restore_mock.assert_not_called()


# --- _phase_dossier_and_stale -----------------------------------------------


def test_phase_dossier_and_stale_swallows_stale_failure(tmp_path: Path) -> None:
    run = _make_run(tmp_path)
    with patch.object(ex, "run_check", side_effect=RuntimeError("scan crashed")):
        ex._phase_dossier_and_stale(run)
    assert run.stale_report is None


def test_phase_dossier_and_stale_records_report(tmp_path: Path) -> None:
    run = _make_run(tmp_path)
    report = StaleAssertionReport(
        base_ref="a", head_ref="HEAD", repo_root=tmp_path, findings=[],
        elapsed_seconds=0.1, files_scanned=1, findings_per_100_loc=0.0,
    )
    with patch.object(ex, "run_check", return_value=report):
        ex._phase_dossier_and_stale(run)
    assert run.stale_report is report


# --- _phase_push ------------------------------------------------------------


def test_phase_push_noop_without_push_flag(tmp_path: Path) -> None:
    run = _make_run(tmp_path, push=False)
    with patch.object(ex, "run_command") as cmd_mock:
        ex._phase_push(run)
    cmd_mock.assert_not_called()


def test_phase_push_success(tmp_path: Path) -> None:
    run = _make_run(tmp_path, push=True)
    with (
        patch.object(ex, "has_remote", return_value=True),
        patch.object(ex, "run_command", return_value=(0, "", "")),
    ):
        ex._phase_push(run)


def test_phase_push_failure_with_linear_history_hint_exits(tmp_path: Path) -> None:
    run = _make_run(tmp_path, push=True)
    with (
        patch.object(ex, "has_remote", return_value=True),
        patch.object(ex, "run_command", return_value=(1, "", "non-fast-forward")),
        patch.object(ex, "_is_linear_history_rejection", return_value=True),
        patch.object(ex, "_emit_remediation_hint") as hint_mock,
        pytest.raises(typer.Exit) as exc,
    ):
        ex._phase_push(run)
    assert exc.value.exit_code == 1
    hint_mock.assert_called_once()


# --- _phase_cleanup_worktrees_and_branches ----------------------------------


def test_phase_cleanup_removes_worktrees_and_branches(tmp_path: Path) -> None:
    """WP03/T012 (#4753): lane-worktree removal now routes through the shared
    ``guarded_worktree_remove`` chokepoint (``specify_cli.git.destructive_guard``)
    instead of a raw ``git worktree remove --force`` issued via ``run_command``.
    That chokepoint shells out for real (it is git-plumbing-pure and does not
    accept an injected command runner), so it is spied on directly here rather
    than through the ``run_command`` fake used for the other git calls in this
    phase.
    """
    run = _make_run(tmp_path, remove_worktree=True, delete_branch=True)
    wt = tmp_path / ".worktrees" / "m-lane-a"
    wt.mkdir(parents=True)
    calls: list[list[str]] = []

    def _fake_cmd(args: list[str], **kwargs: object) -> tuple[int, str, str]:
        calls.append(list(args))
        # rev-parse --verify -> branch exists (ret 0); everything else ret 0.
        return (0, "", "")

    with (
        patch("specify_cli.lanes.branch_naming.lane_branch_name", return_value="kitty/lane-a"),
        patch("specify_cli.lanes.branch_naming.worktree_path", return_value=wt),
        patch("specify_cli.lanes.compute.is_planning_lane", return_value=False),
        patch.object(ex, "_worktree_removal_delay", return_value=0),
        patch.object(ex, "run_command", side_effect=_fake_cmd),
        patch.object(ex, "guarded_worktree_remove") as guarded_remove_mock,
        patch("specify_cli.mission_metadata.load_meta", return_value={"mid8": "deadbeef"}),
        # WP04 (#2119): coordination teardown now routes through the shared
        # ``teardown_coordination_topology`` seam. Patch the seam's real destroy
        # target (``coordination.workspace``) and stub the persist leg.
        patch("specify_cli.post_merge.retrospective_terminus.run_retrospective_postcondition"),
        patch("specify_cli.coordination.workspace.CoordinationWorkspace") as cw_mock,
    ):
        ex._phase_cleanup_worktrees_and_branches(run)
    # T012: the guarded chokepoint removed the (known-clean) lane worktree,
    # never a raw ``git worktree remove --force``.
    guarded_remove_mock.assert_called_once()
    guard_call = guarded_remove_mock.call_args
    assert guard_call.args[0] == wt
    assert guard_call.kwargs["retain"] is False
    assert not any(c[:3] == ["git", "worktree", "remove"] for c in calls)
    # A branch deletion ran (branch existed).
    assert any(c[:3] == ["git", "branch", "-D"] for c in calls)
    cw_mock.teardown.assert_called_once()


def test_phase_cleanup_skips_missing_worktree_and_branch(tmp_path: Path) -> None:
    run = _make_run(tmp_path, remove_worktree=True, delete_branch=True)
    missing_wt = tmp_path / ".worktrees" / "absent"  # does not exist
    calls: list[list[str]] = []

    def _fake_cmd(args: list[str], **kwargs: object) -> tuple[int, str, str]:
        calls.append(list(args))
        # rev-parse --verify -> branch missing (ret 1); other cmds ret 0.
        if list(args)[:3] == ["git", "rev-parse", "--verify"]:
            return (1, "", "not found")
        return (0, "", "")

    with (
        patch("specify_cli.lanes.branch_naming.lane_branch_name", return_value="kitty/lane-a"),
        patch("specify_cli.lanes.branch_naming.worktree_path", return_value=missing_wt),
        patch("specify_cli.lanes.compute.is_planning_lane", return_value=False),
        patch.object(ex, "_worktree_removal_delay", return_value=0),
        patch.object(ex, "run_command", side_effect=_fake_cmd),
        patch("specify_cli.mission_metadata.load_meta", return_value={}),
        # WP04 (#2119): the seam runs the persist leg before the (no-op) destroy;
        # stub it so an empty-meta mission does not hit the real generator.
        patch("specify_cli.post_merge.retrospective_terminus.run_retrospective_postcondition"),
    ):
        ex._phase_cleanup_worktrees_and_branches(run)
    # Worktree absent -> never removed; branch missing -> never deleted.
    assert not any(c[:3] == ["git", "worktree", "remove"] for c in calls)
    assert not any(c[:3] == ["git", "branch", "-D"] for c in calls)


def test_phase_cleanup_coord_teardown_failure_is_non_fatal(tmp_path: Path) -> None:
    # WP04 (#2119): the cleanup phase now routes coordination teardown through the
    # shared ``teardown_coordination_topology`` seam, which persists the
    # retrospective BEFORE destroying the worktree. The DESTROY leg stays
    # best-effort: a worktree-removal failure must NOT raise out of the phase.
    # Patch the seam's real destroy target (``coordination.workspace``) so the
    # fault injection genuinely exercises the swallowed destroy, and stub the
    # persist leg (which runs OUTSIDE the swallow) so it does not interfere.
    run = _make_run(tmp_path, remove_worktree=True, delete_branch=False)
    with (
        patch.object(ex, "_worktree_removal_delay", return_value=0),
        patch.object(ex, "run_command", return_value=(0, "", "")),
        patch("specify_cli.lanes.branch_naming.worktree_path", return_value=tmp_path / "absent"),
        patch("specify_cli.mission_metadata.load_meta", return_value={"mid8": "deadbeef"}),
        patch("specify_cli.post_merge.retrospective_terminus.run_retrospective_postcondition"),
        patch("specify_cli.coordination.workspace.CoordinationWorkspace") as cw_mock,
    ):
        cw_mock.teardown.side_effect = RuntimeError("teardown boom")
        # Must not raise — the destroy leg inside the seam is best-effort.
        ex._phase_cleanup_worktrees_and_branches(run)
        # The destroy leg WAS reached (proves the seam routed to teardown).
        cw_mock.teardown.assert_called_once()


# --- _phase_finalize_and_summary --------------------------------------------


def test_phase_finalize_and_summary_runs_all_steps(tmp_path: Path) -> None:
    run = _make_run(tmp_path)
    with (
        patch.object(ex, "cleanup_merge_workspace") as cleanup_mock,
        patch.object(ex, "clear_state") as clear_mock,
    ):
        ex._phase_finalize_and_summary(run)
    cleanup_mock.assert_called_once()
    clear_mock.assert_called_once()


# --- _render_stale_findings -------------------------------------------------


def _finding(confidence: Confidence) -> StaleAssertionFinding:
    return StaleAssertionFinding(
        test_file=Path("tests/test_x.py"),
        test_line=10,
        source_file=Path("src/x.py"),
        source_line=5,
        changed_symbol="foo",
        confidence=confidence,
        hint="symbol foo changed",
    )


def test_render_stale_findings_none_report() -> None:
    ex._render_stale_findings(None)


def test_render_stale_findings_no_findings(tmp_path: Path) -> None:
    report = StaleAssertionReport(
        base_ref="a", head_ref="HEAD", repo_root=tmp_path, findings=[],
        elapsed_seconds=0.1, files_scanned=1, findings_per_100_loc=0.0,
    )
    ex._render_stale_findings(report)


def test_render_stale_findings_all_grades(tmp_path: Path) -> None:
    report = StaleAssertionReport(
        base_ref="a", head_ref="HEAD", repo_root=tmp_path,
        findings=[
            _finding("high"),
            _finding("medium"),
            _finding("low"),
            _finding("info"),
        ],
        elapsed_seconds=0.1, files_scanned=2, findings_per_100_loc=1.0,
    )
    ex._render_stale_findings(report)


def test_render_stale_findings_info_block_is_prominent(tmp_path: Path) -> None:
    """#3957: message-content (info) findings render as a named block with
    per-assertion file:line entries, placed BEFORE the low-grade noise —
    not as a single trailing count note buried behind it."""
    info_finding = StaleAssertionFinding(
        test_file=Path("tests/test_msg.py"),
        test_line=21,
        source_file=Path("src/msg.py"),
        source_line=3,
        changed_symbol="old error message",
        confidence="info",
        hint="message-content hint marker",
        label="message-content-check",
    )
    low_finding = StaleAssertionFinding(
        test_file=Path("tests/test_x.py"),
        test_line=10,
        source_file=Path("src/x.py"),
        source_line=5,
        changed_symbol="foo",
        confidence="low",
        hint="low-grade hint marker",
    )
    report = StaleAssertionReport(
        base_ref="a", head_ref="HEAD", repo_root=tmp_path,
        findings=[_finding("high"), info_finding, low_finding],
        elapsed_seconds=0.1, files_scanned=2, findings_per_100_loc=1.0,
    )

    with ex.console.capture() as captured:
        ex._render_stale_findings(report)
    output = captured.get()

    # A named block header (not a bare count note) ...
    assert "Message-content assertions skipped as info grade" in output
    # ... whose entries carry the assertion's own file:line and hint.
    assert "test_msg.py:21" in output
    assert "message-content hint marker" in output
    # Prominence: the info block appears before the low-grade noise.
    assert output.index("Message-content assertions") < output.index("low-grade hint marker")


# ---------------------------------------------------------------------------
# #3131 T011 — WP02 owned unit assertions for the retention-enforcement gates.
# ---------------------------------------------------------------------------


def _assert_partial_retention_retains_coord_triple(
    tmp_path: Path, *, delete_branch: bool, remove_worktree: bool
) -> None:
    """One (delete_branch, remove_worktree) case of the partial-retention
    coord-coupling gate — extracted so the loop caller stays closure-free
    (each fake-command call list is scoped to its own call, not a loop var)."""
    calls: list[list[str]] = []

    def _fake_cmd(args: list[str], **kwargs: object) -> tuple[int, str, str]:
        calls.append(list(args))
        return (0, "", "")

    run = _make_run(
        tmp_path,
        remove_worktree=remove_worktree,
        delete_branch=delete_branch,
        teardown_coordination=False,
    )
    with (
        patch("specify_cli.lanes.branch_naming.lane_branch_name", return_value="kitty/lane-a"),
        patch("specify_cli.lanes.branch_naming.worktree_path", return_value=tmp_path / "absent"),
        patch("specify_cli.lanes.compute.is_planning_lane", return_value=False),
        patch.object(ex, "_worktree_removal_delay", return_value=0),
        patch.object(ex, "run_command", side_effect=_fake_cmd),
        patch(
            "specify_cli.mission_metadata.load_meta_or_empty",
            return_value={"coordination_branch": "kitty/mission-m", "mid8": "deadbeef"},
        ),
        patch("specify_cli.post_merge.retrospective_terminus.run_retrospective_postcondition"),
        patch("specify_cli.coordination.workspace.CoordinationWorkspace") as cw_mock,
        patch.object(ex, "commit_merge_bookkeeping") as commit_mock,
    ):
        ex._phase_cleanup_worktrees_and_branches(run)

    mission_branch_deletes = [
        c for c in calls if c[:3] == ["git", "branch", "-D"] and c[3:] == ["kitty/mission-m"]
    ]
    assert not mission_branch_deletes, (
        f"delete_branch={delete_branch}, remove_worktree={remove_worktree}: "
        f"mission/coordination branch was deleted despite teardown_coordination"
        f"=False. calls={calls!r}"
    )
    commit_mock.assert_not_called()
    cw_mock.teardown.assert_not_called()


def test_teardown_coordination_gate_retains_coord_triple_on_partial_retention(
    tmp_path: Path,
) -> None:
    """#3131 T008/T011/INV-2: partial retention (delete_branch XOR
    remove_worktree, so ``teardown_coordination=False``) must not delete the
    mission/coordination branch or attempt the coord-worktree teardown —
    both cases (delete_branch=True/remove_worktree=False and the reverse)."""
    _assert_partial_retention_retains_coord_triple(
        tmp_path, delete_branch=True, remove_worktree=False
    )
    _assert_partial_retention_retains_coord_triple(
        tmp_path, delete_branch=False, remove_worktree=True
    )


def test_scratch_workspace_cleanup_stays_ungated_under_full_retention(
    tmp_path: Path,
) -> None:
    """#3131 FR-013/C-006: the merge SCRATCH workspace cleanup runs regardless
    of the branch/worktree retention decision — retention only ever protects
    the mission's OWN branches/worktrees, never the merge's disposable scratch
    workspace."""
    run = _make_run(
        tmp_path, remove_worktree=False, delete_branch=False, teardown_coordination=False
    )
    with (
        patch.object(ex, "cleanup_merge_workspace") as cleanup_mock,
        patch.object(ex, "clear_state"),
        patch.object(ex, "_render_stale_findings"),
    ):
        ex._phase_finalize_and_summary(run)
    cleanup_mock.assert_called_once()


_ABORT_MISSION_ID = "01ABORT0000000000000000001"


def _init_abort_repo(tmp_path: Path, slug: str, *, retain_worktrees: bool) -> Path:
    """Minimal real git repo + primary meta.json for ``--abort`` teardown tests."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "commit.gpgsign", "false"], check=True)
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    fdir = repo / "kitty-specs" / slug
    fdir.mkdir(parents=True)
    meta: dict[str, object] = {
        "mission_slug": slug,
        "mission_id": _ABORT_MISSION_ID,
        "mid8": "01ABORT0",
        "coordination_branch": f"kitty/mission-{slug}",
        "target_branch": "main",
    }
    if retain_worktrees:
        meta["retain_worktrees"] = True
    (fdir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "seed mission"], check=True)
    return repo


def test_teardown_coordination_for_abort_retains_worktree_when_meta_retains(
    tmp_path: Path,
) -> None:
    """#3131 FR-012/T009: ``merge --abort`` must NOT destroy a coordination
    worktree the mission's meta.json asks to retain (INV-1: no silent
    deletion)."""
    from specify_cli.cli.commands.merge import _teardown_coordination_for_abort

    slug = "abort-retain-repro"
    repo = _init_abort_repo(tmp_path, slug, retain_worktrees=True)
    # #4863: teardown now requires active merge state to run at all, so a real
    # state_entry is supplied — otherwise the None short-circuit would skip the
    # retention branch this test exists to exercise (a silent false-green).
    state = MergeState(
        mission_id=_ABORT_MISSION_ID,
        mission_slug=slug,
        target_branch="main",
        wp_order=[],
    )

    with patch(
        "specify_cli.coordination.teardown.teardown_coordination_topology"
    ) as mock_teardown:
        _teardown_coordination_for_abort(repo, slug, (_ABORT_MISSION_ID, state))

    mock_teardown.assert_not_called()


def test_teardown_coordination_for_abort_destroys_worktree_when_no_policy(
    tmp_path: Path,
) -> None:
    """FR-010 companion: a mission with NO retention policy keeps the
    pre-#3131 ``--abort`` teardown behavior byte-identical."""
    from specify_cli.cli.commands.merge import _teardown_coordination_for_abort

    slug = "abort-default-repro"
    repo = _init_abort_repo(tmp_path, slug, retain_worktrees=False)
    # #4863: a real abort now requires active merge state before the destroy leg
    # runs; supply it so this test still reaches the no-retention teardown path.
    state = MergeState(
        mission_id=_ABORT_MISSION_ID,
        mission_slug=slug,
        target_branch="main",
        wp_order=[],
    )

    with patch(
        "specify_cli.coordination.teardown.teardown_coordination_topology"
    ) as mock_teardown:
        _teardown_coordination_for_abort(repo, slug, (_ABORT_MISSION_ID, state))

    mock_teardown.assert_called_once()


def test_merge_resume_threads_raw_retention_flags_unchanged(tmp_path: Path) -> None:
    """#3131 FR-007: a ``--resume``d merge must fall through into the SAME
    retention resolution as a fresh merge — the resume dispatch must not
    special-case the cleanup flags into concrete bools before
    ``_run_real_merge``, which would bypass ``resolve_merge_retention``."""
    from specify_cli.cli.commands import merge as merge_mod

    captured: dict[str, object] = {}

    def _fake_run_real_merge(_repo_root: object, **kwargs: object) -> None:
        captured.update(kwargs)

    with (
        patch.object(merge_mod, "find_repo_root", return_value=tmp_path),
        patch.object(merge_mod, "_enforce_git_preflight"),
        patch.object(merge_mod, "_dispatch_resume", return_value="m"),
        patch.object(merge_mod, "_resolve_slug_or_exit", return_value="m"),
        patch.object(merge_mod, "load_state", return_value=None),
        patch.object(
            merge_mod, "_resolve_target_branch", return_value=("main", "meta.json")
        ),
        patch.object(merge_mod, "_validate_target_branch"),
        patch.object(merge_mod, "_run_real_merge", side_effect=_fake_run_real_merge),
    ):
        merge_mod.merge(
            strategy=None,
            delete_branch=None,
            remove_worktree=None,
            push=False,
            target_branch=None,
            dry_run=False,
            json_output=False,
            mission="m",
            resume=True,
            abort=False,
            context_token=None,
            keep_workspace=False,
            allow_sparse_checkout=False,
            yes=True,
            skip_review_artifact_check=False,
            note=None,
        )

    assert captured.get("delete_branch") is None, (
        "resume must NOT coerce the unset tri-state delete_branch flag into a "
        f"concrete bool before _run_real_merge; got {captured.get('delete_branch')!r}"
    )
    assert captured.get("remove_worktree") is None, (
        "resume must NOT coerce the unset tri-state remove_worktree flag into "
        f"a concrete bool before _run_real_merge; got {captured.get('remove_worktree')!r}"
    )


def _init_orchestrator_retention_repo(
    tmp_path: Path, slug: str, *, retain: bool, is_coord: bool
) -> Path:
    """Minimal real git repo + primary meta.json for the orchestrator resolver."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "commit.gpgsign", "false"], check=True)
    fdir = repo / "kitty-specs" / slug
    fdir.mkdir(parents=True)
    meta: dict[str, object] = {
        "mission_slug": slug,
        "mission_id": "01ORCH000000000000000000001",
        "mid8": "01ORCH00",
        "target_branch": "main",
    }
    if is_coord:
        meta["coordination_branch"] = f"kitty/mission-{slug}"
    if retain:
        meta["retain_branches"] = True
        meta["retain_worktrees"] = True
    (fdir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "seed mission"], check=True)
    return repo


def test_orchestrator_execute_lane_merge_resolves_retention_for_coord_mission(
    tmp_path: Path,
) -> None:
    """#3131 C-007/T010: ``orchestrator_api._execute_lane_merge`` routes
    through ``resolve_merge_retention`` and (topology-aware) does not mark the
    mission/coordination branch deletable for a retaining coord mission —
    the exact NFR-003 gap the hardcoded ``delete_branch=True,
    remove_worktree=True`` caller used to reach."""
    from specify_cli.orchestrator_api.commands import _resolve_lane_merge_retention

    slug = "orch-retain-coord-repro"
    repo = _init_orchestrator_retention_repo(tmp_path, slug, retain=True, is_coord=True)

    retention, mission_branch_deletable = _resolve_lane_merge_retention(
        repo, slug, delete_branch=None, remove_worktree=None
    )

    assert retention.delete_branch is False
    assert retention.remove_worktree is False
    assert mission_branch_deletable is False, (
        "a retaining COORD mission driven through the orchestrator entry must "
        "not mark the mission/coordination branch deletable"
    )


def test_orchestrator_execute_lane_merge_non_coord_stays_on_delete_branch_gate(
    tmp_path: Path,
) -> None:
    """Topology-aware parity with the executor (#3131 T008): a non-coord
    mission's mission-branch deletability tracks ``delete_branch`` alone, not
    the coupled ``teardown_coordination`` -- so an explicit delete with
    worktrees kept still deletes the (non-coordination) mission branch."""
    from specify_cli.orchestrator_api.commands import _resolve_lane_merge_retention

    slug = "orch-non-coord-repro"
    repo = _init_orchestrator_retention_repo(tmp_path, slug, retain=False, is_coord=False)

    retention, mission_branch_deletable = _resolve_lane_merge_retention(
        repo, slug, delete_branch=True, remove_worktree=False
    )

    assert retention.delete_branch is True
    assert retention.remove_worktree is False
    assert retention.teardown_coordination is False
    assert mission_branch_deletable is True, (
        "a non-coord mission's mission-branch deletion must stay keyed to "
        "delete_branch alone, not the coupled teardown_coordination"
    )
