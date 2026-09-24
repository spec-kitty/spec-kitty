"""Phase-boundary regression test for the executor decomposition (mission #2057, WP10).

Locks the two #1827 invariants that the CC-102 → phase-helper split must keep:

* INV-5 — ORDERING: the baseline RECORD happens (in
  ``_phase_capture_and_baseline``) BEFORE the bookkeeping ``safe_commit``, which
  happens BEFORE the baseline ASSERT (both in ``_phase_commit_and_assert``, in
  that order).
* INV-6 — RESTORE-ON-ERROR: a ``BaselineMergeCommitError`` raised by the baseline
  RECORD restores the final-bookkeeping snapshots, then re-raises (as exit 1).

Also asserts the executor re-exports from the shim and that the phase list in
``_run_lane_based_merge_locked`` invokes the phases in the frozen order.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from unittest.mock import patch

import pytest
import typer

from specify_cli.cli.commands import merge as shim
from specify_cli.merge import executor as ex
from specify_cli.merge.baseline import BaselineMergeCommitError
from specify_cli.merge.state import MergeState

pytestmark = pytest.mark.fast


def _make_run(tmp_path: Path, *, done_marked_before_target: bool = False) -> ex._MergeRunState:
    from types import SimpleNamespace

    lanes_manifest = SimpleNamespace(
        target_branch="main",
        mission_branch="kitty/mission-m",
        lanes=[SimpleNamespace(lane_id="lane-a", wp_ids=["WP01"])],
    )
    state = MergeState(mission_id="01ID", mission_slug="m", target_branch="main", wp_order=["WP01"])
    run = ex._MergeRunState(
        main_repo=tmp_path,
        mission_slug="m",
        canonical_id="01ID",
        canonical_mission_id="01JQANARZAP70V8DVJZ8XN0M3T",
        feature_dir=tmp_path / "kitty-specs" / "m",
        target_feature_dir=tmp_path / "kitty-specs" / "m",
        lanes_manifest=lanes_manifest,
        all_wp_ids=["WP01"],
        push=False,
        delete_branch=True,
        remove_worktree=True,
        strategy=ex.MergeStrategy.SQUASH,
        assume_yes=True,
        planning_artifact_only=False,
        state=state,
        is_resume=False,
        done_marked_before_target=done_marked_before_target,
    )
    run.canonical_events_path = tmp_path / "kitty-specs" / "m" / "status.events.jsonl"
    run.canonical_status_path = tmp_path / "kitty-specs" / "m" / "status.json"
    run.merge_state_path = tmp_path / "state.json"
    run.target_baseline_sha = "abc123"
    run.baseline_mission_id = "01ID"
    return run


# --- Re-export contract -----------------------------------------------------


def test_shim_re_exports_executor_entrypoints() -> None:
    assert shim._run_lane_based_merge is ex._run_lane_based_merge
    assert shim._run_lane_based_merge_locked is ex._run_lane_based_merge_locked


def test_executor_does_not_import_command_shim() -> None:
    tree = __import__("ast").parse(inspect.getsource(ex))
    import ast

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
        elif isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
    assert not any(
        m.startswith("specify_cli.cli.commands.merge") for m in modules
    ), sorted(modules)


# --- INV-5: phase ordering in the linear driver -----------------------------


def test_locked_driver_calls_phases_in_frozen_order() -> None:
    """The decomposition must invoke the phases in the documented sequence."""
    src = inspect.getsource(ex._run_lane_based_merge_locked)
    expected_order = [
        "_phase_gates_and_state(run)",
        "_phase_merge_lanes(run)",
        "_phase_baseline_and_surface(run)",
        "_phase_bake_and_pre_target_done(run)",
        "_phase_mission_to_target(run)",
        "_phase_capture_and_baseline(run)",
        "_phase_record_done_and_project(run)",
        "_phase_porcelain_invariant(run)",
        "_phase_commit_and_assert(run)",
    ]
    positions = [src.index(call) for call in expected_order]
    assert positions == sorted(positions), "phase calls are out of order"
    # The #1827 RECORD (capture_and_baseline) must precede the commit/assert phase.
    assert src.index("_phase_capture_and_baseline(run)") < src.index("_phase_commit_and_assert(run)")


# --- INV-5: record -> commit -> assert ordering -----------------------------


def test_record_then_commit_then_assert_ordering(tmp_path: Path) -> None:
    """RECORD baseline (capture phase) → safe_commit → ASSERT baseline (commit phase)."""
    events: list[str] = []
    run = _make_run(tmp_path)

    def _record_baseline(*_a: object, **_k: object) -> Path:
        events.append("record")
        return tmp_path / "meta.json"

    with (
        patch.object(ex, "_refresh_primary_checkout_after_merge", lambda *_a, **_k: None),
        patch.object(ex, "_capture_merge_snapshots", lambda *_a, **_k: {}),
        patch.object(
            ex, "_target_bookkeeping_status_paths",
            lambda **_k: (tmp_path / "e.jsonl", tmp_path / "s.json"),
        ),
        patch.object(ex, "_record_baseline_merge_commit", side_effect=_record_baseline),
        patch.object(ex, "_paths_have_status_changes", lambda *_a, **_k: True),
        patch.object(ex, "commit_merge_bookkeeping", side_effect=lambda **_k: events.append("commit")),
        patch.object(ex, "_assert_merged_wps_done_on_target", lambda *_a, **_k: None),
        patch.object(
            ex, "_assert_baseline_merge_commit_on_target",
            side_effect=lambda *_a, **_k: events.append("assert"),
        ),
    ):
        # Capture phase records the baseline...
        ex._phase_capture_and_baseline(run)
        # ...commit phase commits then asserts.
        ex._phase_commit_and_assert(run)

    assert events == ["record", "commit", "assert"], events


# --- INV-6: BaselineMergeCommitError -> restore -> reraise -------------------


def test_baseline_record_error_restores_then_exits(tmp_path: Path) -> None:
    """A BaselineMergeCommitError on RECORD restores final snapshots then exits 1."""
    restored: list[dict[Path, bytes | None]] = []
    run = _make_run(tmp_path)
    run.final_bookkeeping_snapshots = {tmp_path / "x": b"orig"}

    with (
        patch.object(ex, "_refresh_primary_checkout_after_merge", lambda *_a, **_k: None),
        patch.object(ex, "_capture_merge_snapshots", lambda *_a, **_k: {}),
        patch.object(
            ex, "_target_bookkeeping_status_paths",
            lambda **_k: (tmp_path / "e.jsonl", tmp_path / "s.json"),
        ),
        patch.object(
            ex, "_record_baseline_merge_commit",
            side_effect=BaselineMergeCommitError("boom"),
        ),
        patch.object(
            ex, "restore_generated_artifact_snapshots",
            side_effect=lambda snaps: restored.append(snaps),
        ),
        pytest.raises(typer.Exit) as exc,
    ):
        ex._phase_capture_and_baseline(run)

    assert exc.value.exit_code == 1
    assert restored == [{tmp_path / "x": b"orig"}], "restore must run before re-raising"


def test_commit_failure_restores_then_reraises(tmp_path: Path) -> None:
    """A non-recovered safe_commit failure restores final snapshots then re-raises."""
    restored: list[dict[Path, bytes | None]] = []
    run = _make_run(tmp_path)
    run.final_bookkeeping_snapshots = {tmp_path / "x": b"orig"}
    run.target_events_path = tmp_path / "e.jsonl"
    run.target_status_path = tmp_path / "s.json"

    boom = RuntimeError("commit failed")
    with (
        patch.object(ex, "_paths_have_status_changes", lambda *_a, **_k: True),
        patch.object(ex, "commit_merge_bookkeeping", side_effect=boom),
        patch.object(
            ex, "restore_generated_artifact_snapshots",
            side_effect=lambda snaps: restored.append(snaps),
        ),
        pytest.raises(RuntimeError, match="commit failed"),
    ):
        ex._phase_commit_and_assert(run)

    assert restored == [{tmp_path / "x": b"orig"}]


def test_porcelain_invariant_violation_restores_then_exits(tmp_path: Path) -> None:
    """A post-merge porcelain divergence restores final snapshots then exits 1."""
    restored: list[dict[Path, bytes | None]] = []
    run = _make_run(tmp_path)
    run.final_bookkeeping_snapshots = {tmp_path / "x": b"orig"}

    with (
        patch.object(ex, "_raw_porcelain_status", lambda *_a, **_k: (0, " M src/unexpected.py\n")),
        patch.object(ex, "_classify_porcelain_lines", lambda *_a, **_k: ([" M src/unexpected.py"], 0)),
        patch.object(
            ex, "restore_generated_artifact_snapshots",
            side_effect=lambda snaps: restored.append(snaps),
        ),
        pytest.raises(typer.Exit) as exc,
    ):
        ex._phase_porcelain_invariant(run)

    assert exc.value.exit_code == 1
    assert restored == [{tmp_path / "x": b"orig"}]


# --- #5001: claim-builder GitProbeError -> clean fail-closed abort ----------


def test_capture_reconciliation_claim_aborts_clean_on_git_probe_error(tmp_path: Path) -> None:
    """A ``GitProbeError`` from ``build_approved_wp_set`` aborts cleanly (exit 1).

    ``_capture_reconciliation_claim`` runs strictly pre-mutation, so a probe
    error there must never surface as an uncaught traceback: it should be
    caught and turned into the same clean, non-zero-exit abort the teardown
    gate's own ``GitProbeError`` REFUSE path uses (#5001).
    """
    from specify_cli.merge.git_probes import GitProbeError

    run = _make_run(tmp_path)
    boom = GitProbeError("git show deadbeef failed (exit 128): fatal: bad object deadbeef")

    with (
        patch.object(ex, "detect_legacy_in_flight_state", lambda *_a, **_k: None),
        patch.object(ex, "write_post_fix_marker", lambda *_a, **_k: None),
        patch.object(ex, "_capture_coord_checkpoint", lambda *_a, **_k: None),
        patch.object(ex, "_resolve_pre_mutation_target_sha", lambda *_a, **_k: "abc123"),
        patch.object(ex, "build_approved_wp_set", side_effect=boom),
        pytest.raises(typer.Exit) as exc,
    ):
        ex._capture_reconciliation_claim(run)

    assert exc.value.exit_code == 1
    # Strictly pre-mutation: the claim is never partially populated.
    assert run.approved_wp_set is None
