"""Forward migration tests for the lane work-tip recorder install (#5115)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.upgrade.migrations import m_4_0_0rc5_install_lane_tip_recorder as recorder_migration
from specify_cli.upgrade.migrations.m_4_0_0rc5_install_lane_tip_recorder import (
    MIGRATION_ID,
    TARGET_VERSION,
    InstallLaneTipRecorderMigration,
)
from specify_cli.upgrade.registry import MigrationRegistry

pytestmark = [pytest.mark.unit]

# Loaded for the registration side effect only; keeps ruff from flagging the
# import as unused while documenting WHY it must happen (the decorator runs
# at import time).
_ = recorder_migration


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "t@example.com"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Test"], check=True)


def test_migration_is_registered_at_current_release_version() -> None:
    migration = MigrationRegistry.get_by_id(MIGRATION_ID)

    assert migration is not None
    assert migration.target_version == TARGET_VERSION == "4.0.0rc5"
    assert migration.runs_on_worktrees is False


def test_detect_true_for_a_fresh_git_repo_with_no_hooks(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)

    migration = InstallLaneTipRecorderMigration()

    assert migration.detect(repo) is True
    can_apply, reason = migration.can_apply(repo)
    assert can_apply is True
    assert reason == ""


def test_detect_false_for_a_non_git_directory(tmp_path: Path) -> None:
    plain_dir = tmp_path / "not-a-repo"
    plain_dir.mkdir()

    migration = InstallLaneTipRecorderMigration()

    assert migration.detect(plain_dir) is False
    can_apply, reason = migration.can_apply(plain_dir)
    assert can_apply is False
    assert reason != ""


def test_apply_installs_both_hooks_and_becomes_undetectable(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    migration = InstallLaneTipRecorderMigration()

    result = migration.apply(repo)

    assert result.success is True
    assert len(result.changes_made) == 2
    assert (repo / ".git" / "hooks" / "post-commit").exists()
    assert (repo / ".git" / "hooks" / "post-rewrite").exists()
    # Idempotent completion: nothing left pending, so a re-scan does not
    # keep re-detecting this migration on every upgrade run.
    assert migration.detect(repo) is False


def test_apply_dry_run_makes_no_filesystem_changes(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    migration = InstallLaneTipRecorderMigration()

    result = migration.apply(repo, dry_run=True)

    assert result.success is True
    assert len(result.changes_made) == 2
    assert not (repo / ".git" / "hooks" / "post-commit").exists()
    assert not (repo / ".git" / "hooks" / "post-rewrite").exists()
    # Still pending afterwards -- the dry run wrote nothing.
    assert migration.detect(repo) is True


def test_apply_skips_a_foreign_hook_and_still_reports_success(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    foreign_hook = repo / ".git" / "hooks" / "post-commit"
    foreign_hook.parent.mkdir(parents=True, exist_ok=True)
    foreign_hook.write_text("#!/bin/sh\necho custom\n", encoding="utf-8")
    original = foreign_hook.read_text(encoding="utf-8")
    migration = InstallLaneTipRecorderMigration()

    result = migration.apply(repo)

    assert result.success is True
    # Only post-rewrite was genuinely empty -- post-commit is foreign and was
    # never counted as pending (see pending_hook_names' docstring).
    assert len(result.changes_made) == 1
    assert foreign_hook.read_text(encoding="utf-8") == original
    assert (repo / ".git" / "hooks" / "post-rewrite").exists()
