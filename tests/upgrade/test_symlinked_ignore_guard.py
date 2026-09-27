"""Scope: a symlinked `.gitignore`/`.claudeignore` must not crash the upgrade
pipeline (issue #626, PR #636 squad MAJOR).

`read_ignore_file_text()` (`gitignore_manager.py`) fails closed with
`GitignorePathError` when an ignore file is a symlink rather than following
it. That guard is correct, but nothing in the migration call chain used to
catch it -- so `detect()`/`apply()` raising propagated as an unhandled
crash of `spec-kitty upgrade` for any project whose `.gitignore` happens to
be a symlink (a normal pattern for dotfile managers / monorepos), not only
for a malicious repo checkout. These tests pin the fix at each call site the
squad named: ``MigrationRunner._apply_migration``, the worktree loop, and
``MigrationRegistry.get_applicable`` -- plus one end-to-end reproduction with
the real migration the squad's repro used.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any

import pytest
import typer
from kernel.clock import now_utc
from typer.testing import CliRunner

from specify_cli.cli.commands.upgrade import upgrade
from specify_cli.gitignore_manager import GitignorePathError
from specify_cli.upgrade.metadata import ProjectMetadata
from specify_cli.upgrade.migrations.base import BaseMigration, MigrationResult
from specify_cli.upgrade.registry import MigrationRegistry
from specify_cli.upgrade.runner import MigrationRunner

pytestmark = [pytest.mark.unit, pytest.mark.fast]


class _DetectRaisesMigration(BaseMigration):
    """Simulates a migration whose detect() hits a symlinked ignore file.

    ``can_apply()`` deliberately does NOT assert unreachability: unlike the
    runner call sites (which return/continue as soon as ``detect()`` raises,
    per ``runner.py``'s ``_apply_migration``/worktree loop), the CLI's
    verbose display loop (``upgrade.py``) calls ``can_apply()``
    unconditionally to compute the display status regardless of whether
    ``detect()`` raised -- that is pre-existing, unrelated behavior, not
    part of this fix.
    """

    migration_id = "0.0.1_detect_raises"
    description = "detect() raises GitignorePathError, like a symlinked ignore file"
    target_version = "0.0.1"

    def detect(self, project_path: Path) -> bool:  # noqa: ARG002
        raise GitignorePathError("<project>/.gitignore is a symlink; refusing to read through it")

    def can_apply(self, project_path: Path) -> tuple[bool, str]:  # noqa: ARG002
        return False, "detect() could not run"

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:  # noqa: ARG002
        raise AssertionError("apply() must not run when detect() raises")


class _ApplyRaisesMigration(BaseMigration):
    """Simulates detect() succeeding, then apply() hitting a symlink swapped in."""

    migration_id = "0.0.1_apply_raises"
    description = "apply() raises GitignorePathError after detect() returned True"
    target_version = "0.0.1"

    def detect(self, project_path: Path) -> bool:  # noqa: ARG002
        return True

    def can_apply(self, project_path: Path) -> tuple[bool, str]:  # noqa: ARG002
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:  # noqa: ARG002
        raise GitignorePathError("<project>/.gitignore is a symlink; refusing to read through it")


class _AlwaysSucceedsMigration(BaseMigration):
    """A later migration that must not run past an earlier unsafe detect()."""

    migration_id = "0.0.2_always_succeeds"
    description = "detect() and apply() both succeed"
    target_version = "0.0.2"

    def detect(self, project_path: Path) -> bool:  # noqa: ARG002
        return True

    def can_apply(self, project_path: Path) -> tuple[bool, str]:  # noqa: ARG002
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:  # noqa: ARG002
        return MigrationResult(success=True, changes_made=["Applied"])


@pytest.fixture()
def registry_restore() -> Any:
    original = MigrationRegistry._migrations.copy()
    yield
    MigrationRegistry._migrations = original


def _register(*migrations: type[BaseMigration]) -> None:
    MigrationRegistry.clear()
    for migration in migrations:
        MigrationRegistry.register(migration)


@pytest.fixture()
def migration_project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    kittify_dir = project / ".kittify"
    kittify_dir.mkdir(parents=True)
    metadata = ProjectMetadata(
        version="0.0.0",
        initialized_at=now_utc(),
        python_version="3.11",
        platform="test",
        platform_version="test",
    )
    metadata.save(kittify_dir)
    return project


class TestMainProjectMigrationGuard:
    """`MigrationRunner._apply_migration` (runner.py) -- the direct call site
    the squad's traceback named at ``runner.py:264``."""

    def test_detect_raising_is_a_failure_not_a_crash(self, migration_project: Path, registry_restore: Any) -> None:
        _register(_DetectRaisesMigration)
        runner = MigrationRunner(migration_project)

        result = runner.upgrade("0.0.1", include_worktrees=False, force=True)

        assert not result.success
        assert any("0.0.1_detect_raises" in e for e in result.errors)
        assert "0.0.1_detect_raises" not in result.migrations_skipped
        assert "0.0.1_detect_raises" not in result.migrations_applied

    def test_apply_raising_is_a_failure_not_a_crash(self, migration_project: Path, registry_restore: Any) -> None:
        _register(_ApplyRaisesMigration)
        runner = MigrationRunner(migration_project)

        result = runner.upgrade("0.0.1", include_worktrees=False, force=True)

        assert not result.success
        assert any("0.0.1_apply_raises" in e for e in result.errors)


class TestWorktreeMigrationGuard:
    """`MigrationRunner._upgrade_worktrees` -- the loop the squad's traceback
    named at ``runner.py:376``."""

    def _make_worktree(self, migration_project: Path) -> Path:
        worktrees_dir = migration_project / ".worktrees"
        worktrees_dir.mkdir(parents=True, exist_ok=True)
        worktree = worktrees_dir / "wt1"
        (worktree / ".kittify").mkdir(parents=True)
        return worktree

    def test_worktree_detect_raising_is_recorded_as_failure_not_crashed(self, migration_project: Path, registry_restore: Any) -> None:
        worktree = self._make_worktree(migration_project)
        _register(_DetectRaisesMigration)
        runner = MigrationRunner(migration_project)

        result = runner._upgrade_worktrees("0.0.1", [_DetectRaisesMigration()], dry_run=False)

        assert any("0.0.1_detect_raises" in e for e in result["errors"])
        wt_metadata = ProjectMetadata.load(worktree / ".kittify")
        assert wt_metadata is not None
        assert not wt_metadata.has_migration("0.0.1_detect_raises")
        record = next(m for m in wt_metadata.applied_migrations if m.id == "0.0.1_detect_raises")
        assert record.result == "failed"

    def test_worktree_apply_raising_is_recorded_as_error_not_crashed(self, migration_project: Path, registry_restore: Any) -> None:
        self._make_worktree(migration_project)
        _register(_ApplyRaisesMigration)
        runner = MigrationRunner(migration_project)

        result = runner._upgrade_worktrees("0.0.1", [_ApplyRaisesMigration()], dry_run=False)

        assert any("0.0.1_apply_raises" in e for e in result["errors"])


class TestRegistryGetApplicableGuard:
    """`MigrationRegistry.get_applicable` -- the call site the squad's
    traceback named at ``registry.py:93``."""

    def test_detect_raising_at_current_version_fails_closed_before_later_migration(self, migration_project: Path, registry_restore: Any) -> None:
        _register(_DetectRaisesMigration, _AlwaysSucceedsMigration)

        metadata = ProjectMetadata.load(migration_project / ".kittify")
        assert metadata is not None
        metadata.version = "0.0.1"
        metadata.save(migration_project / ".kittify")

        runner = MigrationRunner(migration_project)
        result = runner.upgrade("0.0.2", include_worktrees=False, force=True)

        assert not result.success
        assert any("0.0.1_detect_raises" in error for error in result.errors)
        assert "0.0.1_detect_raises" not in result.migrations_skipped
        assert "0.0.1_detect_raises" not in result.migrations_applied
        assert "0.0.2_always_succeeds" not in result.migrations_applied

        reloaded = ProjectMetadata.load(migration_project / ".kittify")
        assert reloaded is not None
        assert reloaded.version == "0.0.1"
        record = next(migration for migration in reloaded.applied_migrations if migration.id == "0.0.1_detect_raises")
        assert record.result == "failed"


class TestRealMigrationEndToEnd:
    """Exact reproduction of the squad's repro on PR #636: the real
    ``StateGitignoreMigration`` against a symlinked ``.gitignore``, driven
    through the same ``MigrationRunner.upgrade()`` entry point
    ``spec-kitty upgrade`` uses."""

    def test_symlinked_gitignore_does_not_crash_upgrade(self, tmp_path: Path, registry_restore: Any) -> None:
        from specify_cli.upgrade.migrations.m_2_0_9_state_gitignore import (
            StateGitignoreMigration,
        )

        _register(StateGitignoreMigration)

        project = tmp_path / "project"
        project.mkdir()
        kittify_dir = project / ".kittify"
        kittify_dir.mkdir(parents=True)
        metadata = ProjectMetadata(
            version="2.0.8",
            initialized_at=now_utc(),
            python_version="3.11",
            platform="test",
            platform_version="test",
        )
        metadata.save(kittify_dir)

        outside_target = tmp_path / "outside-target.txt"
        outside_target.write_text("do-not-touch\n")
        (project / ".gitignore").symlink_to(outside_target)

        runner = MigrationRunner(project)
        # A multi-version jump past the migration's own target_version --
        # squad pass 2's exact repro (target == from_v masks the strand on a
        # same-version re-run per MigrationRegistry.get_applicable; a jump
        # past it is the common upgrade case).
        result = runner.upgrade("3.0.0", include_worktrees=False, force=True)

        assert not result.success
        assert any("2.0.9_state_gitignore" in e for e in result.errors)
        # The guard must not have followed the symlink.
        assert outside_target.read_text() == "do-not-touch\n"

        reloaded = ProjectMetadata.load(kittify_dir)
        assert reloaded is not None
        # A migration the runner could not safely evaluate must NOT strand
        # the project at the target version -- metadata.version stays put so
        # the next `spec-kitty upgrade` re-attempts it once the symlink is
        # gone, instead of it becoming permanently unreachable.
        assert reloaded.version == "2.0.8"

        # Replace the symlink with a real file and retry: the migration must
        # still be selected (never permanently stranded) and now applies.
        (project / ".gitignore").unlink()
        (project / ".gitignore").write_text("# real file\n")

        result2 = runner.upgrade("3.0.0", include_worktrees=False, force=True)

        assert result2.success
        assert "2.0.9_state_gitignore" in result2.migrations_applied


_test_app = typer.Typer(add_completion=False)
_test_app.command()(upgrade)
_runner = CliRunner()


def _run_upgrade(args: list[str], cwd: Path) -> object:
    with contextlib.chdir(cwd):
        return _runner.invoke(_test_app, args, catch_exceptions=False)


class TestCliVerboseDisplayGuard:
    """``upgrade.py``'s verbose detection-results loop -- the call site the
    squad's traceback named at ``upgrade.py:951``. This migration's
    ``target_version`` sits strictly between ``from_version`` and
    ``to_version``, so ``MigrationRegistry.get_applicable`` includes it
    unconditionally (the ``from_v < target <= to_v`` branch never calls
    ``detect()``) -- only the CLI's own verbose loop calls ``detect()``
    directly, which is the path this test exercises.

    That display loop is purely informational (it shows what a migration's
    ``detect()`` reports, independent of the runner), so it still labels the
    migration "skipped" in the plan table -- unrelated to and unaffected by
    the runner's success/failure semantics fixed in squad pass 2. But the
    same ``--dry-run`` invocation also calls ``MigrationRunner.upgrade()``,
    whose ``detect()`` call for this same migration now fails closed
    (squad pass 2 MAJOR: a symlinked ignore file must not be silently
    reported as a successful upgrade), so the command now honestly exits
    non-zero instead of claiming success for a plan it could not evaluate.
    """

    def test_verbose_detect_raising_does_not_crash_and_fails_honestly(self, tmp_path: Path) -> None:
        MigrationRegistry.clear()
        try:
            MigrationRegistry.register(_DetectRaisesMigration)

            project = tmp_path / "project"
            project.mkdir()
            kittify_dir = project / ".kittify"
            kittify_dir.mkdir(parents=True)
            metadata = ProjectMetadata(
                version="0.0.0",
                initialized_at=now_utc(),
                python_version="3.11",
                platform="test",
                platform_version="test",
            )
            metadata.save(kittify_dir)
            from specify_cli.migration.schema_version import MAX_SUPPORTED_SCHEMA

            MigrationRunner._stamp_schema_version(kittify_dir, MAX_SUPPORTED_SCHEMA)

            result = _run_upgrade(
                ["--target", "0.0.1", "--verbose", "--dry-run", "--no-worktrees"],
                cwd=project,
            )

            # The CLI must not crash (no unhandled traceback) -- it exits
            # cleanly with a failure code, not exit_code 0.
            assert result.exit_code == 1, result.output
            assert "0.0.1_detect_raises: " in result.output
            assert "skipped" in result.output.lower()
            assert "symlink" in result.output.lower()
            assert "cannot safely detect" in result.output.lower()
        finally:
            MigrationRegistry.clear()
