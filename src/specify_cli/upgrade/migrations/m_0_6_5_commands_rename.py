"""Migration: Rename commands/ to command-templates/ directories."""

from __future__ import annotations

import shutil
from pathlib import Path
from kernel.tree_removal import ToolOwnedPathUnproven, remove_tool_owned_tree

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult


@MigrationRegistry.register
class CommandsRenameMigration(BaseMigration):
    """Rename commands/ to command-templates/ in templates and missions.

    This migration fixes the issue where Claude Code discovers commands
    from .kittify/templates/commands/ and .kittify/missions/*/commands/
    causing duplicate slash commands.

    The directories are renamed to command-templates/ which Claude Code
    does not automatically discover.
    """

    migration_id = "0.6.5_commands_rename"
    description = "Rename commands/ to command-templates/ directories"
    target_version = "0.6.5"

    def detect(self, project_path: Path) -> bool:
        """Check if project uses old commands/ directories."""
        kittify_dir = project_path / ".kittify"

        # Check templates/commands/
        if (kittify_dir / "templates" / "commands").exists():
            return True

        # Check missions/*/commands/
        missions_dir = kittify_dir / "missions"
        if missions_dir.exists():
            for mission in missions_dir.iterdir():
                if mission.is_dir() and (mission / "commands").exists():
                    return True

        # Check worktrees
        worktrees_dir = project_path / ".worktrees"
        if worktrees_dir.exists():
            for worktree in worktrees_dir.iterdir():
                if worktree.is_dir():
                    wt_kittify = worktree / ".kittify"
                    if (wt_kittify / "templates" / "commands").exists():
                        return True
                    wt_missions = wt_kittify / "missions"
                    if wt_missions.exists():
                        for mission in wt_missions.iterdir():
                            if mission.is_dir() and (mission / "commands").exists():
                                return True

        return False

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        """Check for conflicts."""
        kittify_dir = project_path / ".kittify"

        # Check if both old and new exist in templates
        templates_dir = kittify_dir / "templates"
        if templates_dir.exists():
            old_exists = (templates_dir / "commands").exists()
            new_exists = (templates_dir / "command-templates").exists()
            if old_exists and new_exists:
                return (
                    False,
                    "Both commands/ and command-templates/ exist in templates - manual merge required",
                )

        # Check missions
        missions_dir = kittify_dir / "missions"
        if missions_dir.exists():
            for mission in missions_dir.iterdir():
                if mission.is_dir():
                    old_exists = (mission / "commands").exists()
                    new_exists = (mission / "command-templates").exists()
                    if old_exists and new_exists:
                        return (
                            False,
                            f"Both directories exist in mission {mission.name} - manual merge required",
                        )

        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:  # noqa: C901
        """Rename commands/ to command-templates/."""
        changes: list[str] = []
        warnings: list[str] = []
        errors: list[str] = []

        kittify_dir = project_path / ".kittify"

        def rename_dir(old: Path, new: Path, context: str) -> None:
            if old.exists() and not new.exists():
                if dry_run:
                    changes.append(f"Would rename {context}: commands/ -> command-templates/")
                else:
                    try:
                        shutil.move(str(old), str(new))
                        changes.append(f"Renamed {context}: commands/ -> command-templates/")
                    except OSError as e:
                        errors.append(f"Failed to rename {context}: {e}")

        # Rename in templates/
        templates_dir = kittify_dir / "templates"
        if templates_dir.exists():
            rename_dir(
                templates_dir / "commands",
                templates_dir / "command-templates",
                ".kittify/templates",
            )

        # Rename in each mission
        missions_dir = kittify_dir / "missions"
        if missions_dir.exists():
            for mission in missions_dir.iterdir():
                if mission.is_dir():
                    rename_dir(
                        mission / "commands",
                        mission / "command-templates",
                        f".kittify/missions/{mission.name}",
                    )

        # Handle worktrees - remove old commands/ directories
        # (worktrees should use their own .claude/commands/ not templates)
        worktrees_dir = project_path / ".worktrees"
        if worktrees_dir.exists():
            for worktree in worktrees_dir.iterdir():
                if worktree.is_dir():
                    # Remove old templates/commands/
                    wt_templates_commands = worktree / ".kittify" / "templates" / "commands"
                    if wt_templates_commands.exists():
                        if dry_run:
                            changes.append(f"Would remove old commands/ from worktree {worktree.name}")
                        else:
                            try:
                                remove_tool_owned_tree(wt_templates_commands, tool_root=wt_templates_commands, reason="worktree legacy templates/commands")
                                changes.append(f"Removed old commands/ from worktree {worktree.name}")
                            except (OSError, ToolOwnedPathUnproven) as e:
                                warnings.append(f"Could not remove old commands/ from worktree {worktree.name}: {e}")

                    # Rename missions/*/commands/ in worktree
                    wt_missions = worktree / ".kittify" / "missions"
                    if wt_missions.exists():
                        for mission in wt_missions.iterdir():
                            if mission.is_dir():
                                rename_dir(
                                    mission / "commands",
                                    mission / "command-templates",
                                    f".worktrees/{worktree.name}/.kittify/missions/{mission.name}",
                                )

        success = len(errors) == 0
        return MigrationResult(
            success=success,
            changes_made=changes,
            errors=errors,
            warnings=warnings,
        )
