"""Migration: Add .worktrees/ to .git/info/exclude.

This prevents worktrees from being accidentally added to git when users
run 'git add .' or similar commands. The .gitignore entry only protects
against untracked files, not explicit adds.
"""

from __future__ import annotations

from pathlib import Path

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult
from specify_cli.core.git_ops import exclude_from_git_index, is_git_repo


@MigrationRegistry.register
class ExcludeWorktreesMigration(BaseMigration):
    """Add .worktrees/ to .git/info/exclude for defensive protection.

    This migration:
    1. Checks if project is a git repository
    2. Adds .worktrees/ to .git/info/exclude (local-only)
    3. Prevents accidental tracking of worktree directories
    """

    migration_id = "0.13.1_exclude_worktrees"
    description = "Exclude .worktrees/ from git index"
    target_version = "0.13.1"
    clone_local_effect = True  # effect is .git/info/exclude (clone-local), not the tracked ledger (#6233)

    def detect(self, project_path: Path) -> bool:
        """Check if .worktrees/ exclusion is needed."""
        if not is_git_repo(project_path):
            return False

        exclude_file = project_path / ".git" / "info" / "exclude"
        if not exclude_file.exists():
            return False

        try:
            content = exclude_file.read_text()
            return ".worktrees/" not in content
        except OSError:
            return False

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        """Check if migration can be applied."""
        if not is_git_repo(project_path):
            return False, "Not a git repository"

        exclude_file = project_path / ".git" / "info" / "exclude"
        if not exclude_file.exists():
            return False, ".git/info/exclude file not found"

        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        """Add .worktrees/ to .git/info/exclude."""
        changes: list[str] = []
        warnings: list[str] = []
        errors: list[str] = []

        if not is_git_repo(project_path):
            changes.append("Skipped: not a git repository")
            return MigrationResult(
                success=True,
                changes_made=changes,
                errors=errors,
                warnings=warnings,
            )

        if dry_run:
            changes.append("Would add .worktrees/ to .git/info/exclude")
            return MigrationResult(
                success=True,
                changes_made=changes,
                errors=errors,
                warnings=warnings,
            )

        try:
            exclude_from_git_index(project_path, [".worktrees/"])
            changes.append("Added .worktrees/ to .git/info/exclude")
        except Exception as exc:
            # Non-critical error - continue silently
            warnings.append(f"Could not update .git/info/exclude: {exc}")

        return MigrationResult(
            success=True,
            changes_made=changes,
            errors=errors,
            warnings=warnings,
        )
