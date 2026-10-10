"""Migration: Remove duplicate .claude/commands/ from worktrees."""

from __future__ import annotations

from pathlib import Path
from kernel.tree_removal import ToolOwnedPathUnproven, remove_tool_owned_tree

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult


@MigrationRegistry.register
class WorktreeCommandsDedupMigration(BaseMigration):
    """Remove .claude/commands/ from worktrees - they inherit from main repo.

    Claude Code traverses parent directories looking for .claude/commands/.
    When a worktree is located inside the main repo (at .worktrees/),
    the worktree can find commands by traversing up to the main repo.

    This migration removes .claude/commands/ from worktrees since they
    don't need their own copy - they inherit from the main repo.
    """

    migration_id = "0.7.2_worktree_commands_dedup"
    description = "Remove duplicate .claude/commands/ from worktrees (inherit from main repo)"
    target_version = "0.7.2"

    def detect(self, project_path: Path) -> bool:
        """Check if any worktrees have their own .claude/commands/."""
        worktrees_dir = project_path / ".worktrees"

        if not worktrees_dir.exists():
            return False

        for worktree in worktrees_dir.iterdir():
            if worktree.is_dir():
                wt_commands = worktree / ".claude" / "commands"
                if wt_commands.exists():
                    return True

        return False

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        """Check that main repo has commands before removing from worktrees."""
        main_claude_commands = project_path / ".claude" / "commands"

        if not main_claude_commands.exists():
            return (False, "Main repo .claude/commands/ must exist before removing from worktrees")

        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        """Remove .claude/commands/ from all worktrees."""
        changes: list[str] = []
        warnings: list[str] = []
        errors: list[str] = []

        worktrees_dir = project_path / ".worktrees"

        if worktrees_dir.exists():
            for worktree in worktrees_dir.iterdir():
                if worktree.is_dir():
                    wt_commands = worktree / ".claude" / "commands"
                    if wt_commands.exists():
                        if dry_run:
                            changes.append(f"Would remove .claude/commands/ from worktree {worktree.name}")
                        else:
                            try:
                                remove_tool_owned_tree(wt_commands, owned_root=wt_commands, reason="worktree .claude/commands dedup")
                                changes.append(
                                    f"Removed .claude/commands/ from worktree {worktree.name} (inherits from main repo)"
                                )
                            except (OSError, ToolOwnedPathUnproven) as e:
                                errors.append(f"Failed to remove .claude/commands/ from {worktree.name}: {e}")

        success = len(errors) == 0
        return MigrationResult(
            success=success,
            changes_made=changes,
            errors=errors,
            warnings=warnings,
        )
