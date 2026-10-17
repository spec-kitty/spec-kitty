"""Clone-local migrations re-apply per-checkout despite a recorded ledger (#6233).

Structural-class regression for the upgrade runner's skip gate
(``runner._apply_migration``). The gate short-circuits on the TRACKED, pushed
ledger ``metadata.yaml`` (``has_migration`` → skip) BEFORE it ever calls
``detect()``. For a migration whose EFFECT lives OUTSIDE version control
(clone-local: ``.git/info/exclude``, ``.git/hooks``, ``git config --local``),
one clone's recorded state propagates to every pulled clone, so a pulled clone
skips the migration forever and never gains the local effect -- even though its
own ``detect()`` correctly reports the effect absent.

The fix routes the skip decision to per-clone ``detect()`` for migrations
tagged ``clone_local_effect = True``. These tests assert on the real on-disk
effect (``.git/info/exclude`` content, ``git config --local`` values), never on
"a file was written".
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from kernel.clock import now_utc
from specify_cli.core.git_ops import git_exclude_file, run_command
from specify_cli.upgrade.metadata import ProjectMetadata
from specify_cli.upgrade.migrations.m_3_2_6_decisions_event_log_merge_driver import (
    DecisionsEventLogMergeDriverMigration,
)
from specify_cli.upgrade.migrations.m_0_13_1_exclude_worktrees import ExcludeWorktreesMigration
from specify_cli.upgrade.migrations.m_4_0_0rc7_exclude_spec_kitty import ExcludeSpecKittyMigration
from specify_cli.upgrade.runner import MigrationRunner

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_SPEC_KITTY_ENTRY = ".spec-kitty/"
_WORKTREES_ENTRY = ".worktrees/"
_DECISIONS_ATTR = "kitty-specs/**/decisions.events.jsonl merge=spec-kitty-event-log"
_DECISIONS_DRIVER = "spec-kitty merge-driver-event-log %O %A %B"


@pytest.fixture(name="_git_identity")
def git_identity_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Spec Kitty")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "spec@example.com")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Spec Kitty")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "spec@example.com")


@pytest.fixture
def git_project(tmp_path: Path, _git_identity: None) -> Path:
    """A git project standing in for a freshly-pulled clone."""
    repo = tmp_path / "project"
    repo.mkdir()
    run_command(["git", "init"], cwd=repo)
    run_command(["git", "commit", "--allow-empty", "-m", "Initial commit"], cwd=repo)
    (repo / ".kittify").mkdir()
    return repo


def _record_as_applied(repo: Path, migration_id: str, version: str) -> ProjectMetadata:
    """Write a ledger that records *migration_id* applied -- the pushed state a clone inherits."""
    metadata = ProjectMetadata(version=version, initialized_at=now_utc())
    metadata.record_migration(migration_id, "success")
    metadata.save(repo / ".kittify")
    assert metadata.has_migration(migration_id) is True
    return metadata


def _exclude_lines(repo: Path) -> set[str]:
    exclude_file = git_exclude_file(repo)
    assert exclude_file is not None
    return {line.strip() for line in exclude_file.read_text(encoding="utf-8").splitlines()}


def _local_config(repo: Path, key: str) -> str | None:
    result = subprocess.run(
        ["git", "config", "--local", "--get", key],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


class TestExcludeSpecKittyReselect:
    def test_recorded_but_locally_absent_entry_is_reapplied(self, git_project: Path) -> None:
        migration = ExcludeSpecKittyMigration()
        metadata = _record_as_applied(git_project, migration.migration_id, migration.target_version)
        assert _SPEC_KITTY_ENTRY not in _exclude_lines(git_project)  # pulled clone lacks the local effect

        _result, status = MigrationRunner(git_project)._apply_migration(migration, metadata, dry_run=False)

        assert status == "applied"
        assert _SPEC_KITTY_ENTRY in _exclude_lines(git_project)

    def test_full_upgrade_path_reapplies_the_local_entry(self, git_project: Path) -> None:
        migration = ExcludeSpecKittyMigration()
        _record_as_applied(git_project, migration.migration_id, migration.target_version)

        result = MigrationRunner(git_project).upgrade(migration.target_version, include_worktrees=False)

        assert result.success, result.errors
        assert migration.migration_id in result.migrations_applied
        assert _SPEC_KITTY_ENTRY in _exclude_lines(git_project)


class TestExcludeWorktreesReselect:
    def test_recorded_but_locally_absent_entry_is_reapplied(self, git_project: Path) -> None:
        migration = ExcludeWorktreesMigration()
        metadata = _record_as_applied(git_project, migration.migration_id, migration.target_version)
        assert _WORKTREES_ENTRY not in _exclude_lines(git_project)

        _result, status = MigrationRunner(git_project)._apply_migration(migration, metadata, dry_run=False)

        assert status == "applied"
        assert _WORKTREES_ENTRY in _exclude_lines(git_project)


class TestMergeDriverReselect:
    def test_tracked_attributes_present_but_local_config_missing_is_reapplied(self, git_project: Path) -> None:
        """A pulled clone carries the tracked ``.gitattributes`` line but not the clone-local git config."""
        migration = DecisionsEventLogMergeDriverMigration()
        # Simulate the tracked half arriving with the clone; the local config half is clone-local.
        (git_project / ".gitattributes").write_text(f"{_DECISIONS_ATTR}\n", encoding="utf-8")
        metadata = _record_as_applied(git_project, migration.migration_id, "4.0.0rc7")
        assert _local_config(git_project, "merge.spec-kitty-event-log.driver") is None
        assert migration.detect(git_project) is True  # local config still missing

        _result, status = MigrationRunner(git_project)._apply_migration(migration, metadata, dry_run=False)

        assert status == "applied"
        assert _local_config(git_project, "merge.spec-kitty-event-log.driver") == _DECISIONS_DRIVER
        assert migration.detect(git_project) is False  # settles per-clone once the local half lands

    def test_both_halves_present_still_skips(self, git_project: Path) -> None:
        """Over-correction guard: a clone-local migration whose effect is fully present stays skipped."""
        migration = DecisionsEventLogMergeDriverMigration()
        migration.apply(git_project, dry_run=False)  # both halves present
        assert migration.detect(git_project) is False
        metadata = _record_as_applied(git_project, migration.migration_id, "4.0.0rc7")

        _result, status = MigrationRunner(git_project)._apply_migration(migration, metadata, dry_run=False)

        assert status == "skipped"


class TestDryRunTruthfulness:
    def test_dry_run_reports_would_apply_and_writes_nothing(self, git_project: Path) -> None:
        migration = ExcludeSpecKittyMigration()
        metadata = _record_as_applied(git_project, migration.migration_id, migration.target_version)
        before = _exclude_lines(git_project)
        assert _SPEC_KITTY_ENTRY not in before

        result, status = MigrationRunner(git_project)._apply_migration(migration, metadata, dry_run=True)

        # It must report what a real run on THIS checkout would do -- never "already applied, skipping".
        assert status == "applied"
        joined = " ".join(result.warnings + result.changes_made)
        assert "already applied, skipping" not in joined
        assert any("Would add .spec-kitty/" in line for line in result.changes_made)
        assert _exclude_lines(git_project) == before  # nothing written
