"""Migration: Create AGENTS.md symlink in worktrees."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult


@MigrationRegistry.register
class WorktreeAgentsSymlinkMigration(BaseMigration):
    """Create .kittify/AGENTS.md symlink in worktrees.

    Worktrees need access to the main repo's .kittify/AGENTS.md file
    for command templates that reference it. Since .kittify/ is gitignored,
    worktrees don't automatically have it.

    This migration creates a symlink from each worktree's
    .kittify/AGENTS.md to the main repo's .kittify/AGENTS.md.
    """

    migration_id = "0.8.0_worktree_agents_symlink"
    description = "Create .kittify/AGENTS.md symlink in worktrees"
    target_version = "0.8.0"

    def detect(self, project_path: Path) -> bool:
        """Check if any worktrees are missing .kittify/AGENTS.md."""
        worktrees_dir = project_path / ".worktrees"
        main_agents = project_path / ".kittify" / "AGENTS.md"

        # No main AGENTS.md means nothing to symlink
        if not main_agents.exists():
            return False

        if not worktrees_dir.exists():
            return False

        for worktree in worktrees_dir.iterdir():
            if worktree.is_dir() and not worktree.name.startswith("."):
                wt_agents = worktree / ".kittify" / "AGENTS.md"
                # ``exists()`` is false for both a missing path and a broken symlink.
                if not wt_agents.exists():
                    return True

        return False

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        """Check that main repo has AGENTS.md."""
        main_agents = project_path / ".kittify" / "AGENTS.md"

        if not main_agents.exists():
            return (False, "Main repo .kittify/AGENTS.md must exist before creating symlinks")

        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        """Create .kittify/AGENTS.md symlink in all worktrees."""
        changes: list[str] = []
        warnings: list[str] = []
        errors: list[str] = []

        worktrees_dir = project_path / ".worktrees"
        main_agents = project_path / ".kittify" / "AGENTS.md"

        if not main_agents.exists():
            warnings.append("Main repo .kittify/AGENTS.md not found, skipping")
            return MigrationResult(
                success=True,
                changes_made=changes,
                errors=errors,
                warnings=warnings,
            )

        if worktrees_dir.exists():
            for worktree in worktrees_dir.iterdir():
                if worktree.is_dir() and not worktree.name.startswith("."):
                    wt_kittify = worktree / ".kittify"
                    wt_agents = wt_kittify / "AGENTS.md"

                    # Skip if already exists and is valid
                    if wt_agents.exists() and not wt_agents.is_symlink():
                        warnings.append(f"Worktree {worktree.name} has non-symlink AGENTS.md, skipping")
                        continue

                    if wt_agents.is_symlink() and wt_agents.exists():
                        # Valid symlink already exists
                        continue

                    # Calculate relative path: ../../../.kittify/AGENTS.md
                    # From: .worktrees/001-feature/.kittify/AGENTS.md
                    # To:   .kittify/AGENTS.md
                    relative_path = "../../../.kittify/AGENTS.md"

                    if dry_run:
                        changes.append(f"Would create .kittify/AGENTS.md symlink in worktree {worktree.name}")
                    else:
                        try:
                            # Ensure .kittify directory exists
                            wt_kittify.mkdir(parents=True, exist_ok=True)

                            # Remove broken symlink if present
                            if wt_agents.is_symlink():
                                wt_agents.unlink()

                            # Create the symlink
                            # Need to change to the directory to create relative symlink
                            original_cwd = os.getcwd()
                            try:
                                os.chdir(wt_kittify)
                                os.symlink(relative_path, "AGENTS.md")
                            finally:
                                os.chdir(original_cwd)

                            changes.append(f"Created .kittify/AGENTS.md symlink in worktree {worktree.name}")
                        except OSError as e:
                            # Symlink failed (Windows?), try copying instead
                            try:
                                shutil.copy2(main_agents, wt_agents)
                                changes.append(
                                    f"Copied .kittify/AGENTS.md to worktree {worktree.name} (symlink failed)"
                                )
                            except OSError as copy_error:
                                errors.append(
                                    f"Failed to create AGENTS.md in {worktree.name}: {e}, copy also failed: {copy_error}"  # noqa: E501
                                )

        success = len(errors) == 0
        return MigrationResult(
            success=success,
            changes_made=changes,
            errors=errors,
            warnings=warnings,
        )
