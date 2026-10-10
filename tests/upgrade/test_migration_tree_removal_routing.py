"""WP07 (#5965 / #5966): tool-owned tree deletions in migrations, runner, init, merge and utils.

Per site group: the normal path still deletes, and a planted ``.git`` makes
``remove_tool_owned_tree`` refuse, so the tree is kept and the refusal is reported.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel.tree_removal import ToolOwnedPathUnproven
from specify_cli.cli.commands.init import _discard_failed_project_scaffold
from specify_cli.core.utils import safe_remove
from specify_cli.migration import runner
from specify_cli.runtime.merge import merge_package_assets
from specify_cli.upgrade.migrations.m_0_6_5_commands_rename import CommandsRenameMigration
from specify_cli.upgrade.migrations.m_0_7_2_worktree_commands_dedup import WorktreeCommandsDedupMigration
from specify_cli.upgrade.migrations.m_0_9_0_frontmatter_only_lanes import FrontmatterOnlyLanesMigration
from specify_cli.upgrade.migrations.m_0_9_1_complete_lane_migration import CompleteLaneMigration
from specify_cli.upgrade.migrations.m_2_0_6_consistency_sweep import _cleanup_legacy_worktree_assets

pytestmark = pytest.mark.fast


def _tree(root: Path, plant_git: bool) -> Path:
    root.mkdir(parents=True)
    (root / "a.md").write_text("x")
    if plant_git:
        (root / ".git").mkdir()
    return root


@pytest.mark.parametrize("plant_git", [False, True])
def test_0_7_2_worktree_commands(tmp_path: Path, plant_git: bool) -> None:
    _tree(tmp_path / ".claude" / "commands", False)
    wt_commands = _tree(tmp_path / ".worktrees" / "wt" / ".claude" / "commands", plant_git)
    result = WorktreeCommandsDedupMigration().apply(tmp_path)
    assert wt_commands.exists() is plant_git
    assert bool(result.errors) is plant_git


@pytest.mark.parametrize("plant_git", [False, True])
def test_0_6_5_worktree_templates_commands(tmp_path: Path, plant_git: bool) -> None:
    target = _tree(tmp_path / ".worktrees" / "wt" / ".kittify" / "templates" / "commands", plant_git)
    result = CommandsRenameMigration().apply(tmp_path)
    assert target.exists() is plant_git
    assert any("Could not remove old commands" in w for w in result.warnings) is plant_git


@pytest.mark.parametrize("plant_git", [False, True])
def test_0_9_1_worktree_cleanup(tmp_path: Path, plant_git: bool) -> None:
    migration = CompleteLaneMigration()
    agent_dir, subdir = migration.AGENT_DIRS[0]
    commands = _tree(tmp_path / ".worktrees" / "wt" / agent_dir / subdir, plant_git)
    scripts = _tree(tmp_path / ".worktrees" / "wt" / ".kittify" / "scripts", plant_git)
    _changes, errors = migration._cleanup_worktrees(tmp_path, dry_run=False)
    assert commands.exists() is plant_git
    assert scripts.exists() is plant_git
    assert bool(errors) is plant_git


@pytest.mark.parametrize("plant_git", [False, True])
def test_2_0_6_worktree_cleanup(tmp_path: Path, plant_git: bool) -> None:
    from specify_cli.agent_utils.directories import AGENT_DIRS

    agent_dir, subdir = AGENT_DIRS[0]
    commands = _tree(tmp_path / ".worktrees" / "wt" / agent_dir / subdir, plant_git)
    scripts = _tree(tmp_path / ".worktrees" / "wt" / ".kittify" / "scripts", plant_git)
    _changes, errors = _cleanup_legacy_worktree_assets(tmp_path, dry_run=False)
    assert commands.exists() is plant_git
    assert scripts.exists() is plant_git
    assert bool(errors) is plant_git


@pytest.mark.parametrize("plant_git", [False, True])
def test_lane_dir_cleanup_0_9_0_and_0_9_1(tmp_path: Path, plant_git: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    for migration, method in (
        (FrontmatterOnlyLanesMigration(), "_migrate_feature"),
        (CompleteLaneMigration(), "_migrate_remaining_files"),
    ):
        feature = tmp_path / type(migration).__name__ / "kitty-specs" / "feat"
        lane_dir = _tree(feature / "tasks" / "planned", plant_git)
        (lane_dir / "a.md").unlink()
        # A planted ``.git`` counts as real content; pretend only system files remain to reach the removal.
        monkeypatch.setattr(type(migration), "_get_real_contents", classmethod(lambda cls, d: []))
        changes, warnings, errors, *_ = getattr(migration, method)(feature, "main", False)
        assert lane_dir.exists() is plant_git
        assert any("Could not remove" in w for w in warnings) is plant_git


def test_runner_backup_cleanup_and_stale_removal(tmp_path: Path) -> None:
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify" / "config.yaml").write_text("x")
    (tmp_path / ".kittify" / runner._BACKUP_DIR_NAME).mkdir()
    (tmp_path / ".kittify" / runner._BACKUP_DIR_NAME / "stale").write_text("old")
    backup = runner._create_backup(tmp_path)
    assert backup is not None and not (backup / "stale").exists()
    assert runner._cleanup_backup(tmp_path) is True
    assert not backup.exists()


def test_runner_cleanup_backup_refuses_git_checkout(tmp_path: Path) -> None:
    backup = _tree(tmp_path / ".kittify" / runner._BACKUP_DIR_NAME, True)
    assert runner._cleanup_backup(tmp_path) is False
    assert backup.exists()


def test_runner_restore_replaces_kitty_specs_from_this_runs_backup(tmp_path: Path) -> None:
    (tmp_path / "kitty-specs" / "m").mkdir(parents=True)
    (tmp_path / "kitty-specs" / "m" / "spec.md").write_text("original")
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify" / "keep.txt").write_text("k")
    backup = runner._create_backup(tmp_path)
    assert backup is not None
    (tmp_path / "kitty-specs" / "m" / "spec.md").write_text("mutated")
    (tmp_path / "kitty-specs" / "m" / "new.md").write_text("by migration")
    (tmp_path / ".kittify" / "extra_dir").mkdir()
    assert runner._restore_backup(tmp_path, backup) is True
    assert (tmp_path / "kitty-specs" / "m" / "spec.md").read_text() == "original"
    assert not (tmp_path / "kitty-specs" / "m" / "new.md").exists()
    assert not (tmp_path / ".kittify" / "extra_dir").exists()


def test_runner_restore_refuses_when_kitty_specs_is_a_git_checkout(tmp_path: Path) -> None:
    (tmp_path / "kitty-specs").mkdir()
    (tmp_path / ".kittify").mkdir()
    backup = runner._create_backup(tmp_path)
    assert backup is not None
    (tmp_path / "kitty-specs" / ".git").mkdir()
    (tmp_path / "kitty-specs" / "only-copy.md").write_text("precious")
    assert runner._restore_backup(tmp_path, backup) is False
    assert (tmp_path / "kitty-specs" / "only-copy.md").read_text() == "precious"


def test_runner_restore_refuses_kittify_git_checkout_item(tmp_path: Path) -> None:
    (tmp_path / ".kittify").mkdir()
    backup = runner._create_backup(tmp_path)
    assert backup is not None
    item = _tree(tmp_path / ".kittify" / "nested", True)
    assert runner._restore_backup(tmp_path, backup) is False
    assert item.exists()


def test_init_discards_scaffold_it_created(tmp_path: Path) -> None:
    project = _tree(tmp_path / "proj", False)
    _discard_failed_project_scaffold(project, here=False)
    assert not project.exists()


def test_init_scaffold_discard_refuses_git_checkout(tmp_path: Path) -> None:
    project = _tree(tmp_path / "proj", True)
    with pytest.raises(ToolOwnedPathUnproven):
        _discard_failed_project_scaffold(project, here=False)
    assert project.exists()


def test_init_scaffold_discard_noop_for_here(tmp_path: Path) -> None:
    project = _tree(tmp_path / "proj", False)
    _discard_failed_project_scaffold(project, here=True)
    assert project.exists()


def test_runtime_merge_replaces_managed_dir_and_refuses_checkout(tmp_path: Path) -> None:
    source, dest = tmp_path / "src", tmp_path / "dest"
    (source / "missions" / "software-dev").mkdir(parents=True)
    (source / "missions" / "software-dev" / "new.md").write_text("new")
    old = _tree(dest / "missions" / "software-dev", False)
    merge_package_assets(source, dest)
    assert not (old / "a.md").exists() and (old / "new.md").read_text() == "new"
    (old / ".git").mkdir()
    with pytest.raises(ToolOwnedPathUnproven):
        merge_package_assets(source, dest)
    assert (old / ".git").exists()


def test_safe_remove_defaults_owned_root_and_refuses_checkout(tmp_path: Path) -> None:
    assert safe_remove(_tree(tmp_path / "t", False)) is True
    assert safe_remove(tmp_path / "t") is False
    checkout = _tree(tmp_path / "c", True)
    with pytest.raises(ToolOwnedPathUnproven):
        safe_remove(checkout)
    with pytest.raises(ToolOwnedPathUnproven):
        safe_remove(_tree(tmp_path / "o" / "x", False), owned_root=tmp_path / "other")
    assert checkout.exists()
