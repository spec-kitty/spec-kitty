"""Sub-current clone-local migrations are SELECTED and land via the real upgrade path (#6233).

Regression that the direct-``_apply_migration`` tests could not catch: the bug is in
``MigrationRegistry.get_applicable``. On a pulled clone ``from_version == to_version ==
current``, so the version window selects only migrations whose ``target == current``.
A clone-local migration BELOW the current version (``exclude_worktrees`` at 0.13.1, the
merge-driver seeders at 3.x) was never pulled into the applicable set, so the skip-gate
route added for #6233 was never reached for it -- it stayed stranded on every pulled clone.

These tests drive the REAL ``MigrationRegistry.get_applicable`` and ``MigrationRunner.upgrade``
for sub-current real migrations and assert both that the migration is selected and that its
clone-local effect lands on disk. The global registry is snapshotted/cleared/restored so only
the migration under test is registered -- a real upgrade path, with no unrelated migrations.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from kernel.clock import now_utc
from specify_cli.core.git_ops import git_exclude_file, run_command
from specify_cli.upgrade.metadata import ProjectMetadata
from specify_cli.upgrade.migrations.base import BaseMigration
from specify_cli.upgrade.migrations.m_0_13_1_exclude_worktrees import ExcludeWorktreesMigration
from specify_cli.upgrade.migrations.m_3_2_6_decisions_event_log_merge_driver import (
    DecisionsEventLogMergeDriverMigration,
)
from specify_cli.upgrade.registry import MigrationRegistry
from specify_cli.upgrade.runner import MigrationRunner

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

#: A current version well above every sub-current migration's target.
_CURRENT = "4.0.0rc7"
_DECISIONS_ATTR = "kitty-specs/**/decisions.events.jsonl merge=spec-kitty-event-log"
_DECISIONS_DRIVER = "spec-kitty merge-driver-event-log %O %A %B"


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


def _pulled_clone_ledger(repo: Path, migration_id: str) -> None:
    """Stamp the repo as a pulled clone: version == current, the migration recorded applied."""
    metadata = ProjectMetadata(version=_CURRENT, initialized_at=now_utc())
    metadata.record_migration(migration_id, "success")
    metadata.save(repo / ".kittify")


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


def _registered_ids(migration_cls: type[BaseMigration], repo: Path) -> list[str]:
    return [m.migration_id for m in MigrationRegistry.get_applicable(_CURRENT, _CURRENT, project_path=repo)]


def test_exclude_worktrees_subcurrent_selected_and_lands(only_registry: type[MigrationRegistry], git_project: Path) -> None:
    only_registry.register(ExcludeWorktreesMigration)
    _pulled_clone_ledger(git_project, ExcludeWorktreesMigration.migration_id)
    assert ".worktrees/" not in _exclude_lines(git_project)

    # (a) the version window excludes 0.13.1, yet selection pulls it back in on this clone:
    assert _registered_ids(ExcludeWorktreesMigration, git_project) == [ExcludeWorktreesMigration.migration_id]

    # (b) a REAL upgrade() to the current version lands the clone-local effect on disk:
    result = MigrationRunner(git_project).upgrade(_CURRENT, include_worktrees=False)
    assert result.success, result.errors
    assert ExcludeWorktreesMigration.migration_id in result.migrations_applied
    assert ".worktrees/" in _exclude_lines(git_project)


def test_merge_driver_subcurrent_selected_and_lands(only_registry: type[MigrationRegistry], git_project: Path) -> None:
    only_registry.register(DecisionsEventLogMergeDriverMigration)
    # Pulled clone carries the tracked .gitattributes half but not the clone-local git config.
    (git_project / ".gitattributes").write_text(f"{_DECISIONS_ATTR}\n", encoding="utf-8")
    _pulled_clone_ledger(git_project, DecisionsEventLogMergeDriverMigration.migration_id)
    assert _local_config(git_project, "merge.spec-kitty-event-log.driver") is None

    assert _registered_ids(DecisionsEventLogMergeDriverMigration, git_project) == [DecisionsEventLogMergeDriverMigration.migration_id]

    result = MigrationRunner(git_project).upgrade(_CURRENT, include_worktrees=False)
    assert result.success, result.errors
    assert DecisionsEventLogMergeDriverMigration.migration_id in result.migrations_applied
    assert _local_config(git_project, "merge.spec-kitty-event-log.driver") == _DECISIONS_DRIVER
