"""The upgrade runner must not crash for a project outside any git repository (#6437).

``3.2.0rc35_unified_bundle`` resolves the charter bundle through the git
common dir, which raises ``NotInsideRepositoryError`` outside a repository.
The runner treats that as "not applicable here" (skip, no ledger record)
rather than letting the exception abort the whole upgrade.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from charter.resolution import NotInsideRepositoryError
from specify_cli.upgrade.metadata import ProjectMetadata
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.migrations.base import BaseMigration, MigrationResult
from specify_cli.upgrade.runner import MigrationRunner

pytestmark = [pytest.mark.unit, pytest.mark.fast]

MIGRATION_ID = "3.2.0rc35_unified_bundle"


def _make_project(root: Path) -> Path:
    kittify = root / ".kittify"
    kittify.mkdir(parents=True)
    (kittify / "metadata.yaml").write_text("spec_kitty:\n  schema_version: 3\n", encoding="utf-8")
    return root


def _ledger_ids(project: Path) -> list[str]:
    ledger_file = project / ".kittify" / "migration-ledger.jsonl"
    if not ledger_file.exists():
        return []
    return [json.loads(line).get("id", "") for line in ledger_file.read_text("utf-8").splitlines() if line.strip()]


@pytest.mark.parametrize("dry_run", [True, False])
def test_upgrade_outside_git_repository_skips_unified_bundle(tmp_path: Path, dry_run: bool) -> None:
    auto_discover_migrations()
    project = _make_project(tmp_path)

    result = MigrationRunner(project).upgrade("3.2.0rc35", dry_run=dry_run, include_worktrees=False)

    assert MIGRATION_ID in result.migrations_skipped
    assert MIGRATION_ID not in result.migrations_applied
    assert any("not inside a git repository" in w for w in result.warnings)
    assert MIGRATION_ID not in _ledger_ids(project)


class _DetectOutsideRepository(BaseMigration):
    """A stub whose ``detect()`` resolves the repo root and so raises outside a repository."""

    migration_id = "stub_detect_outside_repository"
    description = "stub"
    target_version = "3.1.0"

    def detect(self, project_path: Path) -> bool:
        raise NotInsideRepositoryError(project_path)

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        raise AssertionError("apply() must not run after a skipped detect()")


@pytest.mark.parametrize("dry_run", [True, False])
def test_detect_outside_a_git_repository_is_a_skip_with_no_ledger_record(tmp_path: Path, dry_run: bool) -> None:
    project = _make_project(tmp_path)
    migration = _DetectOutsideRepository()

    result, status = MigrationRunner(project)._apply_migration(migration, ProjectMetadata.load(project / ".kittify"), dry_run=dry_run)

    assert status == "skipped"
    assert result.success
    assert any("not inside a git repository" in w for w in result.warnings)
    assert migration.migration_id not in _ledger_ids(project)


class _CanApplyOutsideRepository(BaseMigration):
    """A stub that detects legacy state but whose ``can_apply()`` resolves the repo root and raises outside a repository."""

    migration_id = "stub_can_apply_outside_repository"
    description = "stub"
    target_version = "3.1.0"

    def detect(self, project_path: Path) -> bool:
        return True

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        raise NotInsideRepositoryError(project_path)

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        raise AssertionError("apply() must not run after a skipped can_apply()")


@pytest.mark.parametrize("dry_run", [True, False])
def test_can_apply_outside_a_git_repository_is_a_skip_with_no_ledger_record(tmp_path: Path, dry_run: bool) -> None:
    project = _make_project(tmp_path)
    migration = _CanApplyOutsideRepository()

    result, status = MigrationRunner(project)._apply_migration(migration, ProjectMetadata.load(project / ".kittify"), dry_run=dry_run)

    assert status == "skipped"
    assert result.success
    assert any("not inside a git repository" in w for w in result.warnings)
    assert migration.migration_id not in _ledger_ids(project)


class _FlaggedMigration(BaseMigration):
    """A stub that declares the repository requirement; ``detect()`` must never run outside a repository."""

    migration_id = "stub_requires_git_repository"
    description = "stub"
    target_version = "3.1.0"
    requires_git_repository = True
    detect_calls = 0

    def detect(self, project_path: Path) -> bool:
        type(self).detect_calls += 1
        raise AssertionError("detect() must not run for a flagged migration outside a repository")

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        return MigrationResult(success=True, changes_made=["applied"])


@pytest.mark.parametrize("dry_run", [True, False])
def test_flagged_migration_is_skipped_before_detect_outside_a_repository(tmp_path: Path, dry_run: bool) -> None:
    project = _make_project(tmp_path)
    migration = _FlaggedMigration()
    _FlaggedMigration.detect_calls = 0

    result, status = MigrationRunner(project)._apply_migration(migration, ProjectMetadata.load(project / ".kittify"), dry_run=dry_run)

    assert status == "skipped"
    assert result.success
    assert _FlaggedMigration.detect_calls == 0
    assert any("not inside a git repository" in w for w in result.warnings)
    assert migration.migration_id not in _ledger_ids(project)


class _WritesThenRaises(BaseMigration):
    """An unflagged stub whose ``apply()`` writes a marker and then raises the repository error."""

    migration_id = "stub_writes_then_raises"
    description = "stub"
    target_version = "3.1.0"

    def detect(self, project_path: Path) -> bool:
        return True

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        (project_path / "marker.txt").write_text("written", encoding="utf-8")
        raise NotInsideRepositoryError(project_path)


class _WritesThenRaisesRunsFirst(_WritesThenRaises):
    migration_id = "stub_writes_then_raises_runs_first"
    runs_first = True


def test_apply_time_repository_error_is_a_recorded_failure(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    migration = _WritesThenRaises()

    result, status = MigrationRunner(project)._apply_migration(migration, ProjectMetadata.load(project / ".kittify"), dry_run=False)

    assert status == "failed"
    assert not result.success
    assert any(migration.migration_id in e and "git repository" in e for e in result.errors)
    assert (project / "marker.txt").exists()
    assert migration.migration_id in _ledger_ids(project)


def test_apply_time_repository_error_on_runs_first_records_nothing(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    migration = _WritesThenRaisesRunsFirst()

    result, status = MigrationRunner(project)._apply_migration(migration, ProjectMetadata.load(project / ".kittify"), dry_run=False)

    assert status == "failed"
    assert not result.success
    assert migration.migration_id not in _ledger_ids(project)


def test_flagged_migration_runs_normally_inside_a_repository(tmp_path: Path) -> None:
    import subprocess

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    project = _make_project(tmp_path)

    class _Inside(_FlaggedMigration):
        migration_id = "stub_requires_git_repository_inside"

        def detect(self, project_path: Path) -> bool:
            return True

    migration = _Inside()
    result, status = MigrationRunner(project)._apply_migration(migration, ProjectMetadata.load(project / ".kittify"), dry_run=False)

    assert status == "applied"
    assert result.success
    assert migration.migration_id in _ledger_ids(project)


def test_unified_bundle_migration_declares_the_repository_requirement() -> None:
    auto_discover_migrations()
    from specify_cli.upgrade.registry import MigrationRegistry

    by_id = {m.migration_id: m for m in MigrationRegistry.get_all()}
    assert by_id[MIGRATION_ID].requires_git_repository is True
