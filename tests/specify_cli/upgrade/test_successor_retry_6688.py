"""The successor retry rule: a repair is retried while its predecessor's outcome leaves it unproven (#6688).

A pre-ledger project's ``.kittify/metadata.yaml`` records what ran before the migration
ledger existed. First adoption (``4.0.0rc8_backfill_migration_ledger``) copies those
records and settles every migration below the recorded version from the version stamp —
including a residue-safe successor whose superseded predecessor recorded ``failed`` or
``skipped``. Before #6688 that stamped ``success`` settled the successor, so a repair the
predecessor never finished was never retried, while the predecessor itself was a recorded
no-op.

Every case here goes through the production entry point, ``MigrationRunner.upgrade``, with
one whole upgrade run per assertion set:

- the successor is selected and applied, and the dirty Mission is repaired, for every
  predecessor/successor pair and both unsettled outcomes (``failed``, ``skipped``), in the
  main checkout and in a ``.worktrees/*`` checkout with its own ledger;
- a repeated upgrade applies nothing, reports no changes and leaves ``kitty-specs/``
  byte-identical (``detect()`` stays the idempotency guard, so a completed repair is never
  re-applied), live and in dry run;
- a predecessor that recorded ``success`` keeps the #6680 gate: the successor stays inert;
- a migration that declares no predecessor keeps its success-only settlement, and every
  declared predecessor is the migration its successor actually supersedes.

The fixtures come from the #6680 suite (``test_residue_safe_successors_6669``) rather than a
second copy: the two files must describe the same project shapes to mean the same thing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.specify_cli.upgrade.test_residue_safe_successors_6669 import (
    NEW_090,
    NEW_091,
    NEW_206,
    NEW_311,
    LEGACY_WP,
    PAIRS,
    PRED_311,
    TARGET,
    WALL_CLOCK_TS,
    _dirty_mission,
    _get,
    _plain_project,
    _pre_ledger,
    _record,
    _snapshot,
    _tracked_project,
    _write,
)

from specify_cli.upgrade.ledger import TRACKED_LEDGER_RELPATH, MigrationLedger, build_record
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.migrations.base import BaseMigration, MigrationResult
from specify_cli.upgrade.registry import MigrationRegistry, predecessor_outcome_settled, settled_in_selection_view
from specify_cli.upgrade.runner import MigrationRunner
from specify_cli.upgrade.supersession import SUPERSEDED_MIGRATIONS


pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

PAIR_IDS = [new for _old, new in PAIRS]
RECORDED_VERSION = "3.2.0"

#: A migration with no declared predecessor: the widened rule must not touch it.
ORDINARY_MIGRATION = "3.1.1_event_log_merge_driver"


@pytest.fixture(autouse=True)
def _real_registry() -> None:
    MigrationRegistry.clear()
    auto_discover_migrations()


@pytest.fixture(autouse=True)
def quiet_runtime_assets(monkeypatch: pytest.MonkeyPatch) -> None:
    """The global runtime-asset step of the 2.0.6 successor is not what these cases are about."""
    monkeypatch.setattr(
        "specify_cli.upgrade.migrations.m_2_0_6_residue_safe_consistency_sweep._migrate_runtime_assets",
        lambda *_args, **_kwargs: ([], []),
    )


def _results(project: Path, migration_id: str) -> list[str]:
    """The read view's record for the migration: its partition collapses to one record per id."""
    return [record.result for record in MigrationLedger(project).applicable_records_for(_get(migration_id)) if record.id == migration_id]


def _selected(project: Path) -> set[str]:
    return {m.migration_id for m in MigrationRegistry.get_applicable(RECORDED_VERSION, RECORDED_VERSION, project_path=project)}


def _assert_repaired(new: str, mission: Path) -> None:
    """The successor's own effect is present, so a passing run cannot be a no-op."""
    if new in (NEW_090, NEW_091):
        assert (mission / "tasks" / "WP01-x.md").is_file(), new
        assert not (mission / "tasks" / "doing").exists(), new
    elif new == NEW_206:
        assert (mission / "meta.json").is_file(), new
    else:
        assert json.loads((mission / "status.json").read_text(encoding="utf-8"))["materialized_at"] == "", new


@pytest.mark.parametrize("recorded", ["failed", "skipped"])
@pytest.mark.parametrize(("old", "new"), PAIRS, ids=PAIR_IDS)
def test_an_unsettled_predecessor_lets_the_successor_repair_a_pre_ledger_project(tmp_path: Path, old: str, new: str, recorded: str) -> None:
    """A pre-ledger project at 3.2.0 whose metadata records the predecessor unsettled still gets the repair."""
    project = _plain_project(tmp_path)
    mission = _dirty_mission(project)
    _pre_ledger(project, RECORDED_VERSION, {old: recorded})

    assert predecessor_outcome_settled(project, _get(new)) is False
    assert settled_in_selection_view(project, new) is False
    assert new in _selected(project)

    result = MigrationRunner(project).upgrade(TARGET, include_worktrees=False)

    assert result.success, result.errors
    assert new in result.migrations_applied
    assert result.migration_results[new].changes_made
    _assert_repaired(new, mission)
    # The predecessor stays the recorded no-op it is: the successor carries the repair.
    records = {record.id: record.result for record in MigrationLedger(project).applicable_records_for(_get(old))}
    assert records[old] != "success"


@pytest.mark.parametrize("recorded", ["failed", "skipped"])
@pytest.mark.parametrize(("old", "new"), PAIRS, ids=PAIR_IDS)
def test_a_completed_repair_is_never_replayed(tmp_path: Path, old: str, new: str, recorded: str) -> None:
    """A repeated upgrade re-evaluates the successor and applies nothing: ``detect()`` is the guard.

    A re-evaluation that finds nothing to do must not downgrade the ``success`` the repair
    recorded to ``skipped``: the read view keeps the last record per id, so that write would
    claim the repair never ran. The whole ledger file stays byte-identical.
    """
    project = _plain_project(tmp_path)
    _dirty_mission(project)
    _pre_ledger(project, RECORDED_VERSION, {old: recorded})
    first = MigrationRunner(project).upgrade(TARGET, include_worktrees=False)
    assert first.success, first.errors
    assert new in first.migrations_applied
    assert _results(project, new) == ["success"]
    before = _snapshot(project / "kitty-specs")
    tracked_ledger = project / TRACKED_LEDGER_RELPATH
    ledger_before = tracked_ledger.read_bytes()

    for attempt in (2, 3):
        results_before = _results(project, new)
        again = MigrationRunner(project).upgrade(TARGET, include_worktrees=False)
        assert again.success, again.errors
        assert new not in again.migrations_applied, attempt
        assert again.migration_results[new].changes_made == [], attempt
        assert _snapshot(project / "kitty-specs") == before, attempt
        assert _results(project, new) == results_before, attempt
        assert tracked_ledger.read_bytes() == ledger_before, f"run {attempt} wrote to the tracked ledger"


@pytest.mark.parametrize(("old", "new"), PAIRS, ids=PAIR_IDS)
def test_a_dry_run_selects_the_retry_and_the_successor_reports_no_work(tmp_path: Path, old: str, new: str) -> None:
    """The preview agrees with the live run: it lists the retry, and after the repair it reports nothing to do."""
    project = _plain_project(tmp_path)
    _dirty_mission(project)
    _pre_ledger(project, RECORDED_VERSION, {old: "failed"})
    assert new in _selected(project)

    repaired = MigrationRunner(project).upgrade(TARGET, include_worktrees=False)
    assert repaired.success, repaired.errors
    before = _snapshot(project / "kitty-specs")

    preview = MigrationRunner(project).upgrade(TARGET, dry_run=True, include_worktrees=False)

    assert preview.success, preview.errors
    assert new not in preview.migrations_applied
    assert preview.migration_results[new].changes_made == []
    assert _snapshot(project / "kitty-specs") == before


@pytest.mark.parametrize("recorded", ["failed", "skipped"])
def test_a_worktree_with_its_own_adopted_successor_still_gets_the_retry(tmp_path: Path, recorded: str) -> None:
    """The worktree pass reads its own ledger, whose stamped ``success`` must not settle the successor either."""
    repo = _tracked_project(tmp_path, worktree=True)
    worktree = repo / ".worktrees" / "wt1"
    _pre_ledger(repo, RECORDED_VERSION, {PRED_311: recorded})
    _pre_ledger(worktree, RECORDED_VERSION, {PRED_311: recorded})
    mission = worktree / "kitty-specs" / "001-wt-legacy"
    _write(mission / "tasks" / "doing" / "WP01-x.md", LEGACY_WP)
    _write(mission / "meta.json", json.dumps({"mission_id": "01ARZ3NDEKTSV4RRFFQ69G5FAX", "mission_slug": "001-wt-legacy"}))
    _write(mission / "status.json", json.dumps({"event_count": 0, "materialized_at": WALL_CLOCK_TS, "work_packages": {}}, indent=2) + "\n")
    # The worktree's own adoption baseline: the successor stamped `success` from the version.
    _record(worktree, PRED_311, "failed")
    _record(worktree, NEW_311, "success")
    assert settled_in_selection_view(worktree, NEW_311) is False

    result = MigrationRunner(repo).upgrade(TARGET, include_worktrees=True)

    assert result.success, result.errors
    assert json.loads((mission / "status.json").read_text(encoding="utf-8"))["materialized_at"] == ""


@pytest.mark.parametrize(("old", "new"), PAIRS, ids=PAIR_IDS)
def test_a_settled_predecessor_keeps_the_successor_inert(tmp_path: Path, old: str, new: str) -> None:
    """The #6680 gate survives the retry rule: ``success`` on the predecessor settles the successor."""
    project = _plain_project(tmp_path)
    _dirty_mission(project)
    _pre_ledger(project, RECORDED_VERSION, {old: "success"})
    assert predecessor_outcome_settled(project, _get(new)) is True
    assert settled_in_selection_view(project, new) is True
    assert new not in _selected(project)
    before = _snapshot(project / "kitty-specs")

    result = MigrationRunner(project).upgrade(TARGET, include_worktrees=False)

    assert result.success, result.errors
    assert new not in result.migrations_applied
    assert _snapshot(project / "kitty-specs") == before


def test_a_migration_without_a_predecessor_keeps_its_success_only_settlement(tmp_path: Path) -> None:
    """The rule is scoped to declared successors: an ordinary recorded migration stays settled."""
    ordinary = _get(ORDINARY_MIGRATION)
    assert ordinary.predecessor_id == ""

    project = _plain_project(tmp_path)
    MigrationLedger(project).append(build_record(ordinary, "success"))

    assert predecessor_outcome_settled(project, ordinary) is True
    assert ordinary.reselect_when_recorded(project) is False
    assert settled_in_selection_view(project, ORDINARY_MIGRATION) is True


def test_every_declared_predecessor_is_the_migration_this_one_supersedes() -> None:
    """A declared ``predecessor_id`` must name the shipped migration the supersession table replaces (#6688).

    A typo would read as "no predecessor", and a wrong-but-registered id would
    reselect the migration forever; both are silent without this audit.
    """
    declared = {migration.predecessor_id: migration.migration_id for migration in MigrationRegistry.get_all() if migration.predecessor_id}

    assert declared, "the four residue-safe successors declare their predecessor"
    for predecessor_id, successor_id in declared.items():
        assert SUPERSEDED_MIGRATIONS.get(predecessor_id) == successor_id, (predecessor_id, successor_id)


def test_a_predecessor_the_registry_no_longer_carries_keeps_the_recorded_word(tmp_path: Path) -> None:
    """An unresolvable predecessor id must not replay forever: the record's ``success`` still settles."""

    class _RetiredPredecessorSuccessor(BaseMigration):
        migration_id = "9.9.9_successor_of_a_retired_migration"
        description = "stub"
        target_version = "9.9.9"
        predecessor_id = "9.9.9_retired_migration"

        def detect(self, project_path: Path) -> bool:  # noqa: ARG002 - never consulted here
            return False

        def can_apply(self, project_path: Path) -> tuple[bool, str]:  # noqa: ARG002 - never consulted here
            return True, ""

        def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:  # noqa: ARG002 - never consulted here
            return MigrationResult(success=True)

    project = _plain_project(tmp_path)
    MigrationLedger(project).append(build_record(_RetiredPredecessorSuccessor(), "success"))

    assert predecessor_outcome_settled(project, _RetiredPredecessorSuccessor()) is True
