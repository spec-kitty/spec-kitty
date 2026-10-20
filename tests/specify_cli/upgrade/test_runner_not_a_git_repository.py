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

from unittest.mock import patch

from charter.resolution import GitCommonDirUnavailableError, NotInsideRepositoryError
from specify_cli.upgrade.metadata import ProjectMetadata
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.migrations.base import BaseMigration, MigrationResult
from specify_cli.upgrade import runner as runner_module
from specify_cli.upgrade.runner import MigrationRunner

pytestmark = [pytest.mark.unit, pytest.mark.fast]

MIGRATION_ID = "3.2.0rc35_unified_bundle"


@pytest.fixture(autouse=True)
def _confine_git_discovery(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Stop git walking above ``tmp_path`` so the tests hold when TMPDIR sits inside a checkout."""
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))


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
    probes: list[Path] = []
    real_probe = runner_module.project_is_inside_git_repository

    def _counting_probe(path: Path) -> bool:
        probes.append(path)
        return real_probe(path)

    with patch.object(runner_module, "project_is_inside_git_repository", _counting_probe):
        result = MigrationRunner(project).upgrade("3.2.0rc35", dry_run=dry_run, include_worktrees=False)
        # The one flagged migration in the registry triggers exactly one git probe.
        assert len(probes) == 1
        # Memoised: a second question to the same probe does not run git again.
        probe = runner_module.RepositoryProbe(project)
        assert probe.inside() is False
        assert probe.inside() is False
        assert len(probes) == 2

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


class _RaisesInPhase(BaseMigration):
    """A stub whose ``detect()`` or ``can_apply()`` hits an unrunnable repository probe."""

    migration_id = "stub_probe_unrunnable_in_phase"
    description = "stub"
    target_version = "3.1.0"
    phase = "detect"

    def detect(self, project_path: Path) -> bool:
        if self.phase == "detect":
            raise GitCommonDirUnavailableError(project_path, "git binary missing")
        return True

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        raise GitCommonDirUnavailableError(project_path, "git binary missing")

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        raise AssertionError("apply() must not run after a failed detect()/can_apply()")


@pytest.mark.parametrize("phase", ["detect", "can_apply"])
def test_an_unrunnable_probe_in_detect_or_can_apply_is_a_recorded_failure(tmp_path: Path, phase: str) -> None:
    project = _make_project(tmp_path)
    migration = _RaisesInPhase()
    migration.phase = phase

    result, status = MigrationRunner(project)._apply_migration(migration, ProjectMetadata.load(project / ".kittify"), dry_run=False)

    assert status == "failed"
    assert not result.success
    assert migration.migration_id in _ledger_ids(project)


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


def _make_error(error_type: type[RuntimeError], path: Path) -> RuntimeError:
    if error_type is GitCommonDirUnavailableError:
        return GitCommonDirUnavailableError(path, "git binary missing")
    return NotInsideRepositoryError(path)


_REPOSITORY_ERRORS = [NotInsideRepositoryError, GitCommonDirUnavailableError]


class _WritesThenRaises(BaseMigration):
    """An unflagged stub whose ``apply()`` writes a marker and then raises the repository error."""

    migration_id = "stub_writes_then_raises"
    description = "stub"
    target_version = "3.1.0"
    error_type: type[RuntimeError] = NotInsideRepositoryError

    def detect(self, project_path: Path) -> bool:
        return True

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        (project_path / "marker.txt").write_text("written", encoding="utf-8")
        raise _make_error(self.error_type, project_path)


class _WritesThenRaisesRunsFirst(_WritesThenRaises):
    migration_id = "stub_writes_then_raises_runs_first"
    runs_first = True


@pytest.mark.parametrize("error_type", _REPOSITORY_ERRORS)
def test_apply_time_repository_error_is_a_recorded_failure(tmp_path: Path, error_type: type[RuntimeError]) -> None:
    project = _make_project(tmp_path)
    migration = _WritesThenRaises()
    migration.error_type = error_type

    result, status = MigrationRunner(project)._apply_migration(migration, ProjectMetadata.load(project / ".kittify"), dry_run=False)

    assert status == "failed"
    assert not result.success
    assert any(migration.migration_id in e and "git repository" in e for e in result.errors)
    assert (project / "marker.txt").exists()
    assert migration.migration_id in _ledger_ids(project)


@pytest.mark.parametrize("error_type", _REPOSITORY_ERRORS)
def test_apply_time_repository_error_on_runs_first_records_nothing(tmp_path: Path, error_type: type[RuntimeError]) -> None:
    project = _make_project(tmp_path)
    migration = _WritesThenRaisesRunsFirst()
    migration.error_type = error_type

    result, status = MigrationRunner(project)._apply_migration(migration, ProjectMetadata.load(project / ".kittify"), dry_run=False)

    assert status == "failed"
    assert not result.success
    assert migration.migration_id not in _ledger_ids(project)


@pytest.mark.parametrize("subdir", ["", "sub/dir"], ids=["repository-root", "subdirectory"])
def test_flagged_migration_runs_normally_inside_a_repository(tmp_path: Path, subdir: str) -> None:
    import subprocess

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    project = _make_project(tmp_path / subdir)

    class _Inside(_FlaggedMigration):
        migration_id = "stub_requires_git_repository_inside"

        def detect(self, project_path: Path) -> bool:
            return True

    migration = _Inside()
    result, status = MigrationRunner(project)._apply_migration(migration, ProjectMetadata.load(project / ".kittify"), dry_run=False)

    assert status == "applied"
    assert result.success
    assert migration.migration_id in _ledger_ids(project)


def _probe_cannot_run(path: Path) -> Path:
    raise GitCommonDirUnavailableError(path, "git binary missing")


@pytest.mark.parametrize("dry_run", [True, False])
def test_a_repository_probe_that_cannot_run_is_a_failure_not_a_skip_or_a_crash(tmp_path: Path, dry_run: bool) -> None:
    project = _make_project(tmp_path)
    metadata = ProjectMetadata.load(project / ".kittify")
    version_before = metadata.version
    migration = _FlaggedMigration()
    _FlaggedMigration.detect_calls = 0

    with patch("specify_cli.upgrade.runner.resolve_canonical_repo_root", _probe_cannot_run):
        result, status = MigrationRunner(project)._apply_migration(migration, metadata, dry_run=dry_run)

    assert status == "failed"
    assert not result.success
    assert any("Cannot determine whether the project is inside a git repository" in e for e in result.errors)
    assert _FlaggedMigration.detect_calls == 0
    assert ProjectMetadata.load(project / ".kittify").version == version_before
    assert (migration.migration_id in _ledger_ids(project)) is (not dry_run)
