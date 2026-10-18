"""Guardrail: the clone-local migration set carries the flag and re-applies safely (#6233).

``clone_local_effect = True`` routes a recorded migration's skip decision to
per-clone ``detect()`` instead of the shared ledger. That reselection is only
safe when ``apply()`` is idempotent (applying twice is a no-op: no error, no
duplicate line/config). This gate:

1. pins the known clone-local members as tagged, and the benign ones as NOT
   tagged (so neither set drifts), and
2. proves a representative apply-twice is an idempotent no-op on a real repo.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from collections.abc import Iterator

from kernel.clock import now_utc
from specify_cli.core.git_ops import git_exclude_file, run_command
from specify_cli.upgrade.ledger import MigrationLedger
from specify_cli.upgrade.metadata import ProjectMetadata
from specify_cli.upgrade.migrations._merge_driver_seeding import MergeDriverSeedingMigration
from specify_cli.upgrade.migrations.base import BaseMigration
from specify_cli.upgrade.migrations.m_0_13_1_exclude_worktrees import ExcludeWorktreesMigration
from specify_cli.upgrade.migrations.m_2_1_2_fix_glossary_context_skill import FixGlossaryContextSkillMigration
from specify_cli.upgrade.registry import MigrationRegistry
from specify_cli.upgrade.runner import MigrationRunner
from specify_cli.upgrade.migrations.m_2_0_0_retire_git_hooks import RetireGitHooksMigration
from specify_cli.upgrade.migrations.m_3_0_3_globalize_skill_pack import GlobalizeSkillPackMigration
from specify_cli.upgrade.migrations.m_3_1_1_event_log_merge_driver import EventLogMergeDriverMigration
from specify_cli.upgrade.migrations.m_3_1_2_globalize_commands import GlobalizeCommandsMigration
from specify_cli.upgrade.migrations.m_3_2_0a4_safe_globalize_commands import SafeGlobalizeCommandsMigration
from specify_cli.upgrade.migrations.m_3_2_6_decisions_event_log_merge_driver import (
    DecisionsEventLogMergeDriverMigration,
)
from specify_cli.upgrade.migrations.m_3_2_6_gate_artifact_merge_drivers import GateArtifactMergeDriverMigration
from specify_cli.upgrade.migrations.m_3_2_6_issue_matrix_driver_repoint import IssueMatrixDriverRepointMigration
from specify_cli.upgrade.migrations.m_3_2_6_meta_traces_merge_drivers import MetaTracesMergeDriverMigration
from specify_cli.upgrade.migrations.m_3_2_7_review_cycle_merge_driver import ReviewCycleMergeDriverMigration
from specify_cli.upgrade.migrations.m_4_0_0rc5_decision_index_merge_driver import DecisionIndexMergeDriverMigration
from specify_cli.upgrade.migrations.m_4_0_0rc5_install_lane_tip_recorder import InstallLaneTipRecorderMigration
from specify_cli.upgrade.migrations.m_4_0_0rc7_exclude_spec_kitty import ExcludeSpecKittyMigration

#: Every migration whose effect lives outside version control (per #6233).
CLONE_LOCAL_MIGRATIONS: tuple[type[BaseMigration], ...] = (
    ExcludeSpecKittyMigration,
    ExcludeWorktreesMigration,
    InstallLaneTipRecorderMigration,
    MergeDriverSeedingMigration,
    DecisionsEventLogMergeDriverMigration,
    GateArtifactMergeDriverMigration,
    MetaTracesMergeDriverMigration,
    IssueMatrixDriverRepointMigration,
    ReviewCycleMergeDriverMigration,
    DecisionIndexMergeDriverMigration,
    EventLogMergeDriverMigration,
)

#: Deliberately NOT clone-local (removals / per-machine, fail-safe-guarded).
TRACKED_OR_EXCLUDED_MIGRATIONS: tuple[type[BaseMigration], ...] = (
    RetireGitHooksMigration,
    GlobalizeSkillPackMigration,
    GlobalizeCommandsMigration,
    SafeGlobalizeCommandsMigration,
)


@pytest.mark.unit
@pytest.mark.fast
@pytest.mark.parametrize("migration_cls", CLONE_LOCAL_MIGRATIONS, ids=lambda c: c.__name__)
def test_clone_local_members_carry_the_flag(migration_cls: type[BaseMigration]) -> None:
    assert migration_cls.clone_local_effect is True


@pytest.mark.unit
@pytest.mark.fast
@pytest.mark.parametrize("migration_cls", TRACKED_OR_EXCLUDED_MIGRATIONS, ids=lambda c: c.__name__)
def test_tracked_or_excluded_members_do_not_carry_the_flag(migration_cls: type[BaseMigration]) -> None:
    assert migration_cls.clone_local_effect is False


@pytest.mark.unit
@pytest.mark.fast
def test_base_default_is_false() -> None:
    assert BaseMigration.clone_local_effect is False


# --------------------------------------------------------------------------------------
# Idempotency: applying a clone-local migration twice is a safe no-op.
# --------------------------------------------------------------------------------------

pytestmark_git = [pytest.mark.integration, pytest.mark.git_repo]


@pytest.fixture
def git_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for var in ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME"):
        monkeypatch.setenv(var, "Spec Kitty")
    for var in ("GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL"):
        monkeypatch.setenv(var, "spec@example.com")
    repo = tmp_path / "project"
    repo.mkdir()
    run_command(["git", "init"], cwd=repo)
    run_command(["git", "commit", "--allow-empty", "-m", "Initial commit"], cwd=repo)
    (repo / ".kittify").mkdir()
    return repo


def _exclude_text(repo: Path) -> str:
    exclude_file = git_exclude_file(repo)
    assert exclude_file is not None
    return exclude_file.read_text(encoding="utf-8")


@pytest.mark.integration
@pytest.mark.git_repo
@pytest.mark.parametrize(
    ("migration", "entry"),
    [
        (ExcludeSpecKittyMigration(), ".spec-kitty/"),
        (ExcludeWorktreesMigration(), ".worktrees/"),
    ],
    ids=["exclude_spec_kitty", "exclude_worktrees"],
)
def test_exclude_apply_twice_is_idempotent(git_project: Path, migration: BaseMigration, entry: str) -> None:
    assert migration.apply(git_project, dry_run=False).success is True
    assert migration.apply(git_project, dry_run=False).success is True
    assert _exclude_text(git_project).count(entry) == 1
    assert migration.detect(git_project) is False


@pytest.mark.integration
@pytest.mark.git_repo
def test_merge_driver_apply_twice_is_idempotent(git_project: Path) -> None:
    migration = DecisionsEventLogMergeDriverMigration()
    assert migration.apply(git_project, dry_run=False).success is True
    assert migration.apply(git_project, dry_run=False).success is True

    attributes = (git_project / ".gitattributes").read_text(encoding="utf-8")
    assert attributes.count("kitty-specs/**/decisions.events.jsonl merge=spec-kitty-event-log") == 1
    driver = subprocess.run(
        ["git", "config", "--local", "--get-all", "merge.spec-kitty-event-log.driver"],
        cwd=git_project,
        capture_output=True,
        text=True,
        check=True,
    )
    assert driver.stdout.strip().splitlines() == ["spec-kitty merge-driver-event-log %O %A %B"]
    assert migration.detect(git_project) is False


# --------------------------------------------------------------------------------------
# WP02 FR-008: SupersededMigration / detect()-guard interplay with ledger-diff
# --------------------------------------------------------------------------------------


@pytest.fixture
def only_registry() -> Iterator[type[MigrationRegistry]]:
    """An empty registry for the test; the real one is restored afterwards."""
    saved = dict(MigrationRegistry._migrations)
    MigrationRegistry.clear()
    try:
        yield MigrationRegistry
    finally:
        MigrationRegistry._migrations.clear()
        MigrationRegistry._migrations.update(saved)


def _bare_project(tmp_path: Path, version: str) -> Path:
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    ProjectMetadata(version=version, initialized_at=now_utc()).save(kittify)
    return tmp_path


@pytest.mark.unit
@pytest.mark.fast
def test_superseded_migration_records_skipped_once_and_never_refires(only_registry: type[MigrationRegistry], tmp_path: Path) -> None:
    """FR-008: a SupersededMigration (``detect()``==False) is selected by ledger-diff, the
    runner's ``detect()`` idempotency guard records it ``skipped``, and that skipped record
    keeps it from re-firing. It never applies and never fails the run."""
    only_registry.register(FixGlossaryContextSkillMigration)
    project = _bare_project(tmp_path, FixGlossaryContextSkillMigration.target_version)
    migration_id = FixGlossaryContextSkillMigration.migration_id

    first = MigrationRunner(project).upgrade("4.0.0rc7", include_worktrees=False)
    assert first.success, first.errors
    assert migration_id in first.migrations_skipped
    assert migration_id not in first.migrations_applied

    ledger = MigrationLedger(project)
    assert [r.result for r in ledger.read_tracked() if r.id == migration_id] == ["skipped"]

    # Second run: a skipped (not success) record does not settle it, so it is re-evaluated
    # and re-skipped -- but never applied, and the skipped row is idempotent (no duplicate).
    second = MigrationRunner(project).upgrade("4.0.0rc7", include_worktrees=False)
    assert second.success, second.errors
    assert migration_id not in second.migrations_applied  # never fires
    assert migration_id in second.migrations_skipped  # re-evaluated, re-skipped
    assert [r.result for r in ledger.read_tracked() if r.id == migration_id] == ["skipped"]


@pytest.mark.integration
@pytest.mark.git_repo
def test_present_clone_local_effect_noops_via_detect_guard(only_registry: type[MigrationRegistry], git_project: Path) -> None:
    """FR-008: when the clone-local effect is already present, the runner's ``detect()``
    idempotency guard records ``skipped`` and never re-applies -- even with an empty ledger."""
    only_registry.register(ExcludeWorktreesMigration)
    ProjectMetadata(version="4.0.0rc7", initialized_at=now_utc()).save(git_project / ".kittify")
    migration = ExcludeWorktreesMigration()
    migration.apply(git_project, dry_run=False)  # effect already present
    assert migration.detect(git_project) is False
    before = _exclude_text(git_project)

    result = MigrationRunner(git_project).upgrade("4.0.0rc7", include_worktrees=False)

    assert result.success, result.errors
    assert ExcludeWorktreesMigration.migration_id in result.migrations_skipped
    assert ExcludeWorktreesMigration.migration_id not in result.migrations_applied
    assert _exclude_text(git_project) == before  # no duplicate entry written
    records = [r for r in MigrationLedger(git_project).read_clone_local() if r.id == ExcludeWorktreesMigration.migration_id]
    assert [r.result for r in records] == ["skipped"]
