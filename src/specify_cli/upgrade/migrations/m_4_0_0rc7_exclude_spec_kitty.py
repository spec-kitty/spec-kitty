"""Migration: Add .spec-kitty/ to .git/info/exclude.

#5434: ``spec-kitty review`` drops ``.spec-kitty/review-lock.json`` into a lane
worktree. The next ``implement`` in the same lane re-enters
``allocate_lane_worktree`` through the REUSE route, whose
``_validate_worktree_clean`` refuses on ANY ``git status`` entry -- so the
untracked review lock trips ``DirtyWorktreeError`` and blocks the implementer.

The allocation choke point now writes ``.spec-kitty/`` to the COMMON-dir
``.git/info/exclude`` (the only exclude git honours for every linked worktree).
This migration backfills that entry for projects created before the fix, so an
existing checkout gets the protection on ``spec-kitty upgrade`` without having
to re-allocate a lane worktree. Modeled 1:1 on
:class:`ExcludeWorktreesMigration` (``m_0_13_1_exclude_worktrees``).
"""

from __future__ import annotations

from pathlib import Path

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult
from specify_cli.core.git_ops import exclude_from_git_index, is_git_repo


@MigrationRegistry.register
class ExcludeSpecKittyMigration(BaseMigration):
    """Add .spec-kitty/ to .git/info/exclude for defensive protection.

    This migration:
    1. Checks if project is a git repository
    2. Adds .spec-kitty/ to the common-dir .git/info/exclude (local-only)
    3. Prevents spec-kitty runtime-state residue (e.g. review-lock.json) from
       surfacing as untracked drift in a worktree's ``git status``
    """

    migration_id = "4.0.0rc7_exclude_spec_kitty"
    description = "Exclude .spec-kitty/ from git index"
    target_version = "4.0.0rc7"

    def detect(self, project_path: Path) -> bool:
        """Check if .spec-kitty/ exclusion is needed."""
        if not is_git_repo(project_path):
            return False

        exclude_file = project_path / ".git" / "info" / "exclude"
        if not exclude_file.exists():
            return False

        try:
            content = exclude_file.read_text()
            return ".spec-kitty/" not in content
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
        """Add .spec-kitty/ to .git/info/exclude."""
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
            changes.append("Would add .spec-kitty/ to .git/info/exclude")
            return MigrationResult(
                success=True,
                changes_made=changes,
                errors=errors,
                warnings=warnings,
            )

        try:
            exclude_from_git_index(project_path, [".spec-kitty/"])
            changes.append("Added .spec-kitty/ to .git/info/exclude")
        except Exception as exc:
            # Non-critical error - continue silently
            warnings.append(f"Could not update .git/info/exclude: {exc}")

        return MigrationResult(
            success=True,
            changes_made=changes,
            errors=errors,
            warnings=warnings,
        )
