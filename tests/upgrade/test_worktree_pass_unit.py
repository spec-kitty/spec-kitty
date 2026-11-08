"""Unit tests for the worktree pass's plan and apply steps (#7405).

The plan is exercised on plain directories (no ``.git`` entry, so never a
Mission worktree); the apply step runs with fake runner hooks, so each rule is
checked without git. The end-to-end behaviour through the runner is pinned in
``test_worktree_pass_characterization.py``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from specify_cli.upgrade.metadata import ProjectMetadata
from specify_cli.upgrade.migrations.base import BaseMigration, MigrationResult
from specify_cli.upgrade.worktree_pass import (
    WorktreePass,
    WorktreePassContext,
    WorktreePassHooks,
    WorktreePassReport,
    WorktreeRun,
    has_upgradeable_state,
    plan_worktree_pass,
)
from specify_cli.upgrade.worktree_selection import WorktreeOutcome, WorktreeSelection

pytestmark = [pytest.mark.unit, pytest.mark.fast]

TARGET = "9.9.9"


class _Stub(BaseMigration):
    migration_id = "unit_stub"
    description = "unit stub"
    target_version = TARGET

    def __init__(self, *, needed: bool = True, result: MigrationResult | None = None) -> None:
        self.needed = needed
        self.result = result or MigrationResult(success=True, changes_made=["done"])
        self.applied_with: list[bool] = []

    def detect(self, project_path: Path) -> bool:
        return self.needed

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        self.applied_with.append(dry_run)
        return self.result


class _MainOnly(_Stub):
    migration_id = "unit_main_only_stub"
    runs_on_worktrees = False


def _worktree(root: Path, name: str, *, kittify: bool = True) -> Path:
    path = root / ".worktrees" / name
    path.mkdir(parents=True)
    if kittify:
        (path / ".kittify").mkdir()
    return path


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("dirs", "pending", "expected"),
    [
        ((".kittify",), False, True),
        ((".kittify",), True, True),
        (("kitty-specs",), True, True),
        (("kitty-specs",), False, False),
        ((".specify",), True, True),
        ((), True, False),
    ],
)
def test_has_upgradeable_state(tmp_path: Path, dirs: tuple[str, ...], pending: bool, expected: bool) -> None:
    for name in dirs:
        (tmp_path / name).mkdir()
    assert has_upgradeable_state(tmp_path, worktree_migrations_pending=pending) is expected


def test_plan_targets_selected_worktrees_with_state_in_name_order(tmp_path: Path) -> None:
    b = _worktree(tmp_path, "b")
    a = _worktree(tmp_path, "a")
    _worktree(tmp_path, "c", kittify=False)
    worktree_only = _Stub()

    plan = plan_worktree_pass(tmp_path / ".worktrees", [worktree_only, _MainOnly()], WorktreeSelection.all())

    assert plan.targets == (a, b)
    assert plan.migrations == (worktree_only,)
    assert [path.name for path in plan.results] == ["a", "b", "c"]
    assert {result.outcome for result in plan.results.values()} == {WorktreeOutcome.NOTHING_TO_UPGRADE}


def test_plan_has_no_target_when_nothing_is_selected(tmp_path: Path) -> None:
    _worktree(tmp_path, "a")

    for selection in (None, WorktreeSelection.none()):
        plan = plan_worktree_pass(tmp_path / ".worktrees", [_Stub()], selection)
        assert plan.targets == ()
        assert [result.outcome for result in plan.results.values()] == [WorktreeOutcome.SKIPPED_NOT_SELECTED]


def test_plan_has_no_target_when_only_main_only_migrations_are_pending(tmp_path: Path) -> None:
    _worktree(tmp_path, "a")

    plan = plan_worktree_pass(tmp_path / ".worktrees", [_MainOnly()], WorktreeSelection.all())

    assert plan.targets == ()
    assert plan.migrations == ()


def test_plan_with_no_migrations_targets_worktrees_for_the_version_bump(tmp_path: Path) -> None:
    a = _worktree(tmp_path, "a")
    _worktree(tmp_path, "b", kittify=False)

    plan = plan_worktree_pass(tmp_path / ".worktrees", [], WorktreeSelection.all())

    assert plan.targets == (a,)


def test_plan_without_worktrees_dir_is_empty(tmp_path: Path) -> None:
    plan = plan_worktree_pass(tmp_path / ".worktrees", [_Stub()], WorktreeSelection.all())

    assert plan.targets == ()
    assert dict(plan.results) == {}


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def test_report_fail_writes_both_channels_and_as_dict_keeps_the_shape() -> None:
    report = WorktreePassReport()
    report.warnings.append("w")
    report.fail(["x", "y"])

    assert report.as_dict() == {"warnings": ["w"], "errors": ["x", "y"], "worktree_failures": ["x", "y"], "worktree_results": []}


# ---------------------------------------------------------------------------
# Apply, with fake hooks
# ---------------------------------------------------------------------------


class _FakeRunner:
    def __init__(self, *, record_returns: bool = True) -> None:
        self.record_returns = record_returns
        self.records: list[tuple[str, str, str | None]] = []
        self.settled: list[WorktreeRun] = []

    def record(self, metadata: ProjectMetadata, root: Path, migration: BaseMigration, result: str, notes: str | None = None, /) -> bool:
        self.records.append((root.name, result, notes))
        return self.record_returns

    def synthesize(self, worktree: Path) -> ProjectMetadata:
        return ProjectMetadata(version="0.1.0", initialized_at=datetime(2026, 1, 1, tzinfo=UTC))

    def settle(self, run: WorktreeRun, context: WorktreePassContext, /) -> tuple[list[str], WorktreeOutcome]:
        self.settled.append(run)
        return [f"settled {run.worktree.name}"], WorktreeOutcome.UPGRADED_COMMITTED

    def hooks(self) -> WorktreePassHooks:
        return WorktreePassHooks(record=self.record, synthesize_metadata=self.synthesize, settle=self.settle)


def _context(*, dry_run: bool = False) -> WorktreePassContext:
    return WorktreePassContext(
        target_version=TARGET,
        dry_run=dry_run,
        auto_commit=False,
        main_metadata=None,
        fallback_timestamp=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_apply_records_settles_and_reports_each_target(tmp_path: Path) -> None:
    a = _worktree(tmp_path, "a")
    fake = _FakeRunner()
    migration = _Stub(result=MigrationResult(success=True, changes_made=["one", "two"], warnings=["note"]))
    plan = plan_worktree_pass(tmp_path / ".worktrees", [migration], WorktreeSelection.all())

    report = WorktreePass(_context(), fake.hooks(), seen_residue=set()).run(plan)

    assert fake.records == [("a", "success", "one; two")]
    (run,) = fake.settled
    assert (run.worktree, run.metadata_dirty, run.migrated, run.failed, run.errored) == (a, True, True, False, False)
    assert run.metadata.version == "0.1.0", "a worktree without metadata.yaml gets synthesized metadata"
    assert report.warnings == ["Worktree a: note", "settled a"]
    assert [result.outcome for result in report.worktree_results] == [WorktreeOutcome.UPGRADED_COMMITTED]


def test_dry_run_records_nothing_and_settles_nothing(tmp_path: Path) -> None:
    _worktree(tmp_path, "a")
    fake = _FakeRunner()
    migration = _Stub()
    plan = plan_worktree_pass(tmp_path / ".worktrees", [migration], WorktreeSelection.all())

    report = WorktreePass(_context(dry_run=True), fake.hooks(), seen_residue=set()).run(plan)

    assert migration.applied_with == [True]
    assert fake.records == []
    assert fake.settled == []
    assert [result.outcome for result in report.worktree_results] == [WorktreeOutcome.NOTHING_TO_UPGRADE]


def test_failed_record_never_marks_metadata_dirty(tmp_path: Path) -> None:
    (tmp_path / ".worktrees" / "a" / ".kittify").mkdir(parents=True)
    (tmp_path / ".worktrees" / "a" / ".kittify" / "metadata.yaml").write_text(
        "spec_kitty:\n  version: '0.1.0'\n  initialized_at: '2026-01-01T00:00:00'\n", encoding="utf-8"
    )
    fake = _FakeRunner(record_returns=True)
    plan = plan_worktree_pass(tmp_path / ".worktrees", [_Stub(result=MigrationResult(success=False))], WorktreeSelection.all())

    report = WorktreePass(_context(), fake.hooks(), seen_residue=set()).run(plan)

    (run,) = fake.settled
    assert (run.metadata_dirty, run.failed) == (False, True)
    assert fake.records == [("a", "failed", None)]
    assert report.worktree_failures == ["Worktree a: Migration unit_stub failed"]


def test_unchanged_record_leaves_metadata_clean(tmp_path: Path) -> None:
    (tmp_path / ".worktrees" / "a" / ".kittify").mkdir(parents=True)
    (tmp_path / ".worktrees" / "a" / ".kittify" / "metadata.yaml").write_text(
        "spec_kitty:\n  version: '0.1.0'\n  initialized_at: '2026-01-01T00:00:00'\n", encoding="utf-8"
    )
    fake = _FakeRunner(record_returns=False)
    plan = plan_worktree_pass(tmp_path / ".worktrees", [_Stub(needed=False)], WorktreeSelection.all())

    WorktreePass(_context(), fake.hooks(), seen_residue=set()).run(plan)

    (run,) = fake.settled
    assert fake.records == [("a", "skipped", "Not applicable")]
    assert run.metadata_dirty is False, "an already recorded skip must not bump last_upgraded_at (#1872)"
