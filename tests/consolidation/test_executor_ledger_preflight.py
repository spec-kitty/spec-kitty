"""WP17 (T090, FR-009c, #5023): the consolidation preflight refuses to tear
down a coordination branch that holds the only copy of the decisions
ledger, and the post-merge porcelain-invariant refusal names the real
remedy (``accept`` / ``spec-commit``) for uncommitted ``decisions/`` dirt
now that WP12 reclassified the ledger to the PRIMARY partition.

Red at base:

* ``_pre_mutation_safety_preflight`` has no concept of the decisions ledger
  at all, so it proceeds straight into a merge that will tear down a
  coordination branch holding the Mission's only ledger copy.
* ``_phase_porcelain_invariant``'s refusal message names only
  ``sparse-checkout --fix`` / ``git status`` -- never ``accept`` or
  ``spec-commit`` -- so an operator staring at uncommitted ``decisions/``
  dirt after a merge gets no actionable remedy.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import typer

from kernel.git import GitPath, StatusEntry
from mission_runtime import MissionTopology
from specify_cli.consolidation import executor as ex
from specify_cli.consolidation.state import ConsolidationState
from specify_cli.git.destructive_guard import DestructiveOpRefused
from tests._factories.coord_mission import make_fork_fixture

pytestmark = pytest.mark.fast


def _make_run(tmp_path: Path, *, mission_slug: str = "m") -> ex._MergeRunState:
    """Minimal ``_MergeRunState`` builder (mirrors
    ``test_executor_phase_boundary.py::_make_run``) for a direct,
    single-phase ``_phase_porcelain_invariant`` call."""
    from types import SimpleNamespace

    lanes_manifest = SimpleNamespace(
        target_branch="main",
        mission_branch=f"kitty/mission-{mission_slug}",
        lanes=[SimpleNamespace(lane_id="lane-a", wp_ids=["WP01"])],
    )
    state = ConsolidationState(mission_id="01ID", mission_slug=mission_slug, target_branch="main", wp_order=["WP01"])
    run = ex._MergeRunState(
        main_repo=tmp_path,
        mission_slug=mission_slug,
        canonical_id="01ID",
        canonical_mission_id="01JQANARZAP70V8DVJZ8XN0M3T",
        feature_dir=tmp_path / "kitty-specs" / mission_slug,
        target_feature_dir=tmp_path / "kitty-specs" / mission_slug,
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
    )
    run.canonical_events_path = tmp_path / "kitty-specs" / mission_slug / "status.events.jsonl"
    run.canonical_status_path = tmp_path / "kitty-specs" / mission_slug / "status.json"
    run.merge_state_path = tmp_path / "state.json"
    run.target_baseline_sha = "abc123"
    run.baseline_mission_id = "01ID"
    return run


# ---------------------------------------------------------------------------
# Preflight: refuse before any mutation (NFR-001)
# ---------------------------------------------------------------------------


def test_consolidation_preflight_refuses_coord_only_ledger(tmp_path: Path) -> None:
    """``_pre_mutation_safety_preflight`` refuses on fixture (d) -- a ledger
    committed only on the coordination branch -- before any mutation."""
    fixture = make_fork_fixture(tmp_path, "ledger_only_on_coordination", MissionTopology.COORD)

    with pytest.raises(DestructiveOpRefused) as excinfo:
        ex._refuse_if_coordination_ledger_unrepaired(fixture.repo_root, fixture.mission_dir_name)

    assert excinfo.value.error_code == "COORDINATION_LEDGER_UNREPAIRED"
    assert "doctor decisions" in str(excinfo.value)
    assert "--repair" in str(excinfo.value)


def test_consolidation_preflight_control_unforked_mission_is_silent(tmp_path: Path) -> None:
    """Positive control: a Mission with no coordination-only ledger raises nothing."""
    fixture = make_fork_fixture(tmp_path, "both_committed", MissionTopology.COORD)

    # No raise == pass.
    ex._refuse_if_coordination_ledger_unrepaired(fixture.repo_root, fixture.mission_dir_name)


def test_pre_mutation_safety_preflight_refuses_before_coord_worktree_check(tmp_path: Path) -> None:
    """The full preflight wires the new leg in -- a coordination-only ledger
    refuses the merge even though every other precondition (checkout,
    worktree cleanliness) would otherwise pass."""
    fixture = make_fork_fixture(tmp_path, "ledger_only_on_coordination", MissionTopology.COORD)
    from types import SimpleNamespace

    lanes_manifest = SimpleNamespace(lanes=[])

    with (
        patch.object(ex, "assert_checkout_on_target"),
        patch.object(ex, "assert_worktree_clean"),
        patch.object(ex, "worktree_lanes", return_value=[]),
        patch("specify_cli.lanes.single_branch_landing.expected_consolidate_checkout", return_value="main"),
        pytest.raises(DestructiveOpRefused) as excinfo,
    ):
        ex._pre_mutation_safety_preflight(
            fixture.repo_root,
            fixture.mission_dir_name,
            fixture.target_branch,
            lanes_manifest,
            fixture.root_mission_dir,
            remove_worktree=True,
            teardown_coordination=True,
        )

    assert excinfo.value.error_code == "COORDINATION_LEDGER_UNREPAIRED"


# ---------------------------------------------------------------------------
# Porcelain invariant: message names the real remedy (accept / spec-commit)
# ---------------------------------------------------------------------------


def test_porcelain_invariant_names_accept_for_ledger_dirt(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Uncommitted ``decisions/`` content is real now (WP12) -- the refusal
    must name ``accept``/``spec-commit`` as the remedy, not just
    ``sparse-checkout --fix`` / ``git status``."""
    run = _make_run(tmp_path, mission_slug="ledger-mission")
    porcelain_entry = StatusEntry(xy=" M", path=GitPath.parse("kitty-specs/ledger-mission/decisions/index.json"))

    with (
        patch.object(ex, "_raw_porcelain_status", return_value=(0, (porcelain_entry,))),
        patch.object(ex, "_restore_and_guard_coord_coherence"),
        pytest.raises(typer.Exit) as excinfo,
    ):
        ex._phase_porcelain_invariant(run)

    assert excinfo.value.exit_code == 1
    out = capsys.readouterr().out
    assert "accept" in out
    assert "spec-commit" in out
    assert "decisions/" in out


def test_porcelain_invariant_control_no_decisions_dirt_omits_remedy(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Control: an unrelated offending path does NOT print the ledger remedy
    (proving the new branch is scoped to ``decisions/`` dirt, not every
    porcelain-invariant violation)."""
    run = _make_run(tmp_path, mission_slug="ledger-mission")

    with (
        patch.object(ex, "_raw_porcelain_status", return_value=(0, (StatusEntry(xy=" M", path=GitPath.parse("some/random/file.json")),))),
        patch.object(ex, "_restore_and_guard_coord_coherence"),
        pytest.raises(typer.Exit) as excinfo,
    ):
        ex._phase_porcelain_invariant(run)

    assert excinfo.value.exit_code == 1
    out = capsys.readouterr().out
    assert "spec-commit" not in out
