"""Migration: Ensure all 12 agent directories are in .gitignore."""

from __future__ import annotations

from pathlib import Path

from specify_cli.gitignore_manager import IgnoreFilePathError, read_ignore_file_text

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult


@MigrationRegistry.register
class GitignoreAgentsMigration(BaseMigration):
    """Ensure all 12 agent directories are in .gitignore.

    This migration adds protection for all known AI agent directories
    that should never be committed to git (they contain auth tokens).
    """

    migration_id = "0.4.8_gitignore_agents"
    description = "Add all 12 AI agent directories to .gitignore"
    target_version = "0.4.8"

    EXPECTED_AGENTS = [
        ".claude/",
        ".codex/",
        ".opencode/",
        ".windsurf/",
        ".gemini/",
        ".cursor/",
        ".qwen/",
        ".kilocode/",
        ".augment/",
        ".roo/",
        ".amazonq/",
        ".github/copilot/",
    ]

    def detect(self, project_path: Path) -> bool:
        """Check if .gitignore is missing agent directories."""
        gitignore = project_path / ".gitignore"

        try:
            content = read_ignore_file_text(gitignore, errors="ignore")
        except (OSError, IgnoreFilePathError):
            return True

        missing = [d for d in self.EXPECTED_AGENTS if d not in content]
        return len(missing) > 0

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        """Check if we can modify .gitignore."""
        gitignore = project_path / ".gitignore"

        if gitignore.exists():
            try:
                # Test read access; tolerate BOM and ignore invalid UTF-8 bytes
                gitignore.read_text(encoding="utf-8-sig", errors="ignore")
            except OSError:
                return False, ".gitignore is not readable"

        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        """Apply gitignore updates."""
        changes: list[str] = []
        warnings: list[str] = []
        errors: list[str] = []

        gitignore = project_path / ".gitignore"

        # Determine what needs to be added
        existing_content = ""
        if gitignore.exists():
            try:
                existing_content = gitignore.read_text(encoding="utf-8-sig", errors="ignore")
            except OSError as e:
                errors.append(f"Failed to read .gitignore: {e}")
                return MigrationResult(success=False, errors=errors)

        missing = [d for d in self.EXPECTED_AGENTS if d not in existing_content]

        if not missing:
            changes.append("All agent directories already in .gitignore")
            return MigrationResult(success=True, changes_made=changes)

        if dry_run:
            changes.append(f"Would add {len(missing)} agent directories to .gitignore")
            for d in missing:
                changes.append(f"  - {d}")
            return MigrationResult(success=True, changes_made=changes)

        # Build new content
        new_entries = "\n# AI Agent directories (added by Spec Kitty CLI)\n"
        new_entries += "# These contain auth tokens and should NEVER be committed\n"
        for d in missing:
            new_entries += f"{d}\n"

        # Ensure existing content ends with newline
        if existing_content and not existing_content.endswith("\n"):
            existing_content += "\n"

        new_content = existing_content + new_entries

        try:
            gitignore.write_text(new_content, encoding="utf-8")
            changes.append(f"Added {len(missing)} agent directories to .gitignore")
        except OSError as e:
            errors.append(f"Failed to write .gitignore: {e}")

        success = len(errors) == 0
        return MigrationResult(
            success=success,
            changes_made=changes,
            errors=errors,
            warnings=warnings,
        )
