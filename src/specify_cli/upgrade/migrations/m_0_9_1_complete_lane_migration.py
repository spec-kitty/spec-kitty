"""Legacy migration: reads and writes frontmatter ``lane`` field.

This migration predates the canonical event-log status model (3.0).
Frontmatter lane is no longer authoritative for active features.

Original purpose: Complete lane migration, clean up worktrees, and
normalize frontmatter.
"""

from __future__ import annotations

import re
from pathlib import Path
from kernel.tree_removal import ToolOwnedPathUnproven, remove_tool_owned_tree

from ..registry import MigrationRegistry
from ..autocommit import record_upgrade_mutation
from .base import BaseMigration, MigrationResult
from specify_cli.frontmatter import normalize_file, FrontmatterError
from specify_cli.agent_utils.directories import (
    AGENT_DIRS as _AGENT_DIRS,
    AGENT_DIR_TO_KEY as _AGENT_DIR_TO_KEY,
    get_agent_dirs_for_project as _get_agent_dirs_for_project,
)


@MigrationRegistry.register
class CompleteLaneMigration(BaseMigration):
    """Complete the lane migration and clean up worktrees for v0.9.0+.

    Part 1: Complete Lane Migration
    The v0.9.0 migration only moved files matching `WP*.md` pattern,
    but some projects have other files in lane subdirectories
    (like phase-*.md, task-*.md, or files without .md extensions).

    Part 2: Worktree Cleanup
    Worktrees should inherit everything from main repo in v0.9.0+:
    - Agent command directories (.codex/prompts/, .gemini/commands/, etc.)
    - Scripts (.kittify/scripts/)
    Having separate copies causes old command templates to reference
    deprecated scripts like tasks-move-to-lane.sh.

    Part 3: Frontmatter Normalization (CRITICAL)
    Normalize all YAML frontmatter to absolute consistency using ruamel.yaml.
    This prevents issues where:
    - Some files have `lane: "for_review"` (quoted)
    - Some files have `lane: for_review` (unquoted)
    Both are valid YAML but inconsistency breaks grep searches and tooling.

    This migration:
    1. Finds ALL remaining files in lane subdirectories (not just WP*.md)
    2. Moves them to the flat tasks/ directory
    3. Ensures lane: field in frontmatter for .md files
    4. Removes any remaining lane subdirectories
    5. Removes ALL agent command directories from worktrees
    6. Removes .kittify/scripts/ from worktrees
    7. Normalizes ALL frontmatter in all .md files for consistency
    """

    migration_id = "0.9.1_complete_migration"
    description = "Complete lane migration + clean up worktrees + normalize frontmatter"
    target_version = "0.9.1"

    # All known agent command directories (imported from agent_utils)
    AGENT_DIRS = _AGENT_DIRS

    LANE_DIRS: tuple[str, ...] = ("planned", "doing", "for_review", "done")

    # System files to ignore when determining if a directory is empty
    # These files are created automatically by operating systems and should not
    # prevent lane directory cleanup
    IGNORE_FILES = frozenset(
        {
            ".gitkeep",  # Git placeholder
            ".DS_Store",  # macOS Finder metadata
            "Thumbs.db",  # Windows thumbnail cache
            "desktop.ini",  # Windows folder settings
            ".directory",  # KDE folder settings
            "._*",  # macOS resource fork prefix (pattern)
        }
    )

    @classmethod
    def _should_ignore_file(cls, filename: str) -> bool:
        """Check if a file should be ignored when determining if directory is empty.

        Args:
            filename: Name of the file to check

        Returns:
            True if file should be ignored (system file), False otherwise
        """
        # Check exact matches
        if filename in cls.IGNORE_FILES:
            return True

        # Check pattern matches (e.g., ._* for macOS resource forks)
        # Check for macOS resource fork files (._filename)
        return bool(filename.startswith("._"))

    @classmethod
    def _get_real_contents(cls, directory: Path) -> list[Path]:
        """Get directory contents, excluding system files.

        Args:
            directory: Path to directory to check

        Returns:
            List of "real" files (excluding system files like .DS_Store)
        """
        if not directory.exists() or not directory.is_dir():
            return []

        return [item for item in directory.iterdir() if not cls._should_ignore_file(item.name)]

    def detect(self, project_path: Path) -> bool:
        """Check if lane subdirectories exist OR worktrees have agent dirs/scripts."""
        # Part 1: Check for remaining lane subdirectories
        main_specs = project_path / "kitty-specs"
        if main_specs.exists():
            for feature_dir in main_specs.iterdir():
                if feature_dir.is_dir() and self._has_remaining_lane_dirs(feature_dir):
                    return True

        worktrees_dir = project_path / ".worktrees"
        if worktrees_dir.exists():
            for worktree in worktrees_dir.iterdir():
                if not worktree.is_dir():
                    continue

                # Check for lane dirs in worktree features
                wt_specs = worktree / "kitty-specs"
                if wt_specs.exists():
                    for feature_dir in wt_specs.iterdir():
                        if feature_dir.is_dir() and self._has_remaining_lane_dirs(feature_dir):
                            return True

                # Part 2: Check for agent command directories in worktree
                for agent_dir, subdir in self.AGENT_DIRS:
                    wt_commands = worktree / agent_dir / subdir
                    if wt_commands.exists():
                        return True

                # Part 2: Check for .kittify/scripts/ in worktree
                wt_scripts = worktree / ".kittify" / "scripts"
                if wt_scripts.exists():
                    return True

        return False

    def _has_remaining_lane_dirs(self, feature_path: Path) -> bool:
        """Check if feature still has lane subdirectories with any content."""
        tasks_dir = feature_path / "tasks"
        if not tasks_dir.exists():
            return False

        for lane in self.LANE_DIRS:
            lane_path = tasks_dir / lane
            if lane_path.is_dir():
                # Check for real contents (ignoring system files)
                real_contents = self._get_real_contents(lane_path)
                if real_contents or any(lane_path.iterdir()):
                    return True

        return False

    def can_apply(self, project_path: Path) -> tuple[bool, str]:  # noqa: ARG002
        """Migration can always be applied if lane directories exist."""
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        """Apply both lane migration and worktree cleanup."""
        changes: list[str] = []
        warnings: list[str] = []
        errors: list[str] = []

        # Part 1: Complete lane migration
        changes.append("=== Part 1: Complete Lane Migration ===")
        features_found = self._find_features_with_lanes(project_path)

        if features_found:
            total_migrated = 0
            total_dirs_removed = 0

            for feature_dir, location_label in features_found:
                feature_changes, feature_warnings, feature_errors, migrated, dirs_removed = self._migrate_remaining_files(feature_dir, location_label, dry_run)
                changes.extend(feature_changes)
                warnings.extend(feature_warnings)
                errors.extend(feature_errors)
                total_migrated += migrated
                total_dirs_removed += dirs_removed

            if dry_run:
                changes.append(f"Would migrate {total_migrated} files and remove {total_dirs_removed} lane directories")
            else:
                changes.append(f"Migrated {total_migrated} files and removed {total_dirs_removed} lane directories")
        else:
            changes.append("No lane subdirectories found")

        # Part 2: Clean up worktrees
        changes.append("")
        changes.append("=== Part 2: Worktree Cleanup ===")
        worktree_changes, worktree_errors = self._cleanup_worktrees(project_path, dry_run)
        changes.extend(worktree_changes)
        errors.extend(worktree_errors)

        # Part 3: Normalize frontmatter
        changes.append("")
        changes.append("=== Part 3: Normalize Frontmatter ===")
        fm_changes, fm_warnings, fm_errors = self._normalize_all_frontmatter(project_path, dry_run)
        changes.extend(fm_changes)
        warnings.extend(fm_warnings)
        errors.extend(fm_errors)

        success = len(errors) == 0
        return MigrationResult(
            success=success,
            changes_made=changes,
            errors=errors,
            warnings=warnings,
        )

    def _find_features_with_lanes(self, project_path: Path) -> list[tuple[Path, str]]:
        """Find all features with remaining lane subdirectories."""
        features: list[tuple[Path, str]] = []

        # Scan main kitty-specs/
        main_specs = project_path / "kitty-specs"
        if main_specs.exists():
            for feature_dir in sorted(main_specs.iterdir()):
                if feature_dir.is_dir() and self._has_remaining_lane_dirs(feature_dir):
                    features.append((feature_dir, "main"))

        # Scan .worktrees/
        worktrees_dir = project_path / ".worktrees"
        if worktrees_dir.exists():
            for worktree in sorted(worktrees_dir.iterdir()):
                if worktree.is_dir():
                    wt_specs = worktree / "kitty-specs"
                    if wt_specs.exists():
                        for feature_dir in sorted(wt_specs.iterdir()):
                            if feature_dir.is_dir() and self._has_remaining_lane_dirs(feature_dir):
                                features.append((feature_dir, f"worktree:{worktree.name}"))

        return features

    def _migrate_remaining_files(  # noqa: C901
        self,
        feature_dir: Path,
        location_label: str,
        dry_run: bool,
    ) -> tuple[list[str], list[str], list[str], int, int]:
        """Migrate all remaining files from a feature's lane subdirectories."""
        changes: list[str] = []
        warnings: list[str] = []
        errors: list[str] = []
        migrated = 0
        dirs_removed = 0

        tasks_dir = feature_dir / "tasks"
        if not tasks_dir.exists():
            return changes, warnings, errors, migrated, dirs_removed

        feature_name = feature_dir.name
        changes.append(f"[{location_label}] {feature_name}:")

        for lane in self.LANE_DIRS:
            lane_dir = tasks_dir / lane
            if not lane_dir.is_dir():
                continue

            # Get ALL items in the lane directory (files and subdirectories)
            for item in sorted(lane_dir.iterdir()):
                if item.name == ".gitkeep":
                    continue  # Skip .gitkeep files

                if item.is_file():
                    # Move file to flat directory
                    target = tasks_dir / item.name

                    # Check if already exists
                    if target.exists():
                        warnings.append(f"  Skip: {item.name} already exists in tasks/")
                        continue

                    try:
                        if dry_run:
                            changes.append(f"  Would move: {lane}/{item.name} → tasks/{item.name}")
                        else:
                            record_upgrade_mutation(item, target, is_move=True)
                            # For .md files, ensure lane in frontmatter
                            if item.suffix == ".md":
                                content = item.read_text(encoding="utf-8-sig")
                                updated_content = self._ensure_lane_in_frontmatter(content, lane)
                                target.write_text(updated_content, encoding="utf-8")
                            else:
                                # For non-.md files, just copy
                                target.write_bytes(item.read_bytes())

                            # Remove original
                            item.unlink()

                            changes.append(f"  Moved: {lane}/{item.name} → tasks/{item.name}")

                        migrated += 1

                    except Exception as e:
                        errors.append(f"  Error migrating {lane}/{item.name}: {e}")

                elif item.is_dir():
                    # Handle nested directories (shouldn't exist but might)
                    warnings.append(f"  Warning: Nested directory {lane}/{item.name}/ found - please check manually")

            # Clean up empty lane directory
            if not dry_run:
                if lane_dir.is_dir():
                    # Check for real contents (ignoring system files)
                    real_contents = self._get_real_contents(lane_dir)
                    if not real_contents:
                        # Directory has no real files (only system files like .DS_Store or .gitkeep)
                        try:
                            # Use shutil.rmtree for more robust removal
                            # This will remove the directory and all system files within it
                            remove_tool_owned_tree(lane_dir, tool_root=lane_dir, reason="empty lane directory (system files only)")
                            changes.append(f"  Removed: {lane}/")
                            dirs_removed += 1
                        except (OSError, ToolOwnedPathUnproven) as e:
                            warnings.append(f"  Could not remove {lane}/: {e}")
            else:
                if lane_dir.is_dir():
                    real_contents = self._get_real_contents(lane_dir)
                    if not real_contents:
                        changes.append(f"  Would remove: {lane}/")
                        dirs_removed += 1

        return changes, warnings, errors, migrated, dirs_removed

    def _ensure_lane_in_frontmatter(self, content: str, expected_lane: str) -> str:
        """Ensure frontmatter has correct lane field."""
        # Find frontmatter boundaries
        if not content.startswith("---"):
            # No frontmatter, add it
            return f'---\nlane: "{expected_lane}"\n---\n{content}'

        # Find closing ---
        lines = content.split("\n")
        closing_idx = -1
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                closing_idx = i
                break

        if closing_idx == -1:
            # Malformed frontmatter, add lane anyway
            return f'---\nlane: "{expected_lane}"\n---\n{content}'

        frontmatter_lines = lines[1:closing_idx]
        body_lines = lines[closing_idx + 1 :]

        # Check if lane field exists
        lane_pattern = re.compile(r"^lane:\s*(.*)$")
        lane_found = False
        updated_lines = []

        for line in frontmatter_lines:
            match = lane_pattern.match(line)
            if match:
                lane_found = True
                current_value = match.group(1).strip().strip("\"'")
                if current_value != expected_lane:
                    # Replace with expected lane from directory
                    updated_lines.append(f'lane: "{expected_lane}"')
                else:
                    updated_lines.append(line)
            else:
                updated_lines.append(line)

        if not lane_found:
            # Insert lane field (before history: if present, otherwise at end)
            insert_idx = len(updated_lines)
            for i, line in enumerate(updated_lines):
                if line.startswith("history:"):
                    insert_idx = i
                    break
            updated_lines.insert(insert_idx, f'lane: "{expected_lane}"')

        # Reconstruct document
        result_lines = ["---"] + updated_lines + ["---"] + body_lines
        return "\n".join(result_lines)

    def _cleanup_worktrees(self, project_path: Path, dry_run: bool) -> tuple[list[str], list[str]]:  # noqa: C901
        """Clean up agent command directories and scripts from all worktrees."""
        changes: list[str] = []
        errors: list[str] = []

        worktrees_dir = project_path / ".worktrees"
        if not worktrees_dir.exists():
            changes.append("No .worktrees/ directory found")
            return changes, errors

        worktrees_cleaned = 0
        for worktree in sorted(worktrees_dir.iterdir()):
            if not worktree.is_dir():
                continue

            worktree_name = worktree.name
            cleaned_this_worktree = False

            # Remove agent command directories
            for agent_dir, subdir in self.AGENT_DIRS:
                commands_dir = worktree / agent_dir / subdir
                # Check is_symlink() FIRST - exists() returns False for broken symlinks!
                if commands_dir.is_symlink() or commands_dir.exists():
                    if dry_run:
                        is_symlink = commands_dir.is_symlink()
                        type_str = "symlink" if is_symlink else "directory"
                        changes.append(f"[{worktree_name}] Would remove {agent_dir}/{subdir}/ ({type_str})")
                    else:
                        try:
                            # Check if it's a symlink - handle differently
                            if commands_dir.is_symlink():
                                commands_dir.unlink()
                                changes.append(f"[{worktree_name}] Removed {agent_dir}/{subdir}/ symlink (inherits from main)")
                            elif commands_dir.is_dir():
                                remove_tool_owned_tree(commands_dir, tool_root=commands_dir, reason="worktree agent commands dir")
                                changes.append(f"[{worktree_name}] Removed {agent_dir}/{subdir}/ (inherits from main)")

                            # Clean up parent directory if now empty
                            parent = commands_dir.parent
                            if parent.exists() and not any(parent.iterdir()):
                                parent.rmdir()

                            cleaned_this_worktree = True

                        except (OSError, ToolOwnedPathUnproven) as e:
                            errors.append(f"[{worktree_name}] Failed to remove {agent_dir}/{subdir}/: {e}")

            # Remove .kittify/scripts/
            scripts_dir = worktree / ".kittify" / "scripts"
            # Check is_symlink() FIRST - exists() returns False for broken symlinks!
            if scripts_dir.is_symlink() or scripts_dir.exists():
                if dry_run:
                    is_symlink = scripts_dir.is_symlink()
                    type_str = "symlink" if is_symlink else "directory"
                    changes.append(f"[{worktree_name}] Would remove .kittify/scripts/ ({type_str})")
                else:
                    try:
                        # Check if it's a symlink - handle differently
                        if scripts_dir.is_symlink():
                            scripts_dir.unlink()
                            changes.append(f"[{worktree_name}] Removed .kittify/scripts/ symlink (inherits from main)")
                        elif scripts_dir.is_dir():
                            remove_tool_owned_tree(scripts_dir, tool_root=scripts_dir, reason="worktree .kittify/scripts")
                            changes.append(f"[{worktree_name}] Removed .kittify/scripts/ (inherits from main)")
                        cleaned_this_worktree = True
                    except (OSError, ToolOwnedPathUnproven) as e:
                        errors.append(f"[{worktree_name}] Failed to remove .kittify/scripts/: {e}")

            if cleaned_this_worktree:
                worktrees_cleaned += 1

        if worktrees_cleaned > 0:
            if dry_run:
                changes.append(f"Would clean up {worktrees_cleaned} worktrees")
            else:
                changes.append(f"Cleaned up {worktrees_cleaned} worktrees")
        else:
            changes.append("No worktrees needed cleanup")

        return changes, errors

    def _normalize_all_frontmatter(self, project_path: Path, dry_run: bool) -> tuple[list[str], list[str], list[str]]:  # noqa: C901
        """Normalize frontmatter in all markdown files for consistency.

        This ensures:
        - Consistent YAML formatting (no manual quotes)
        - Consistent field ordering
        - Proper ruamel.yaml formatting
        """
        changes: list[str] = []
        warnings: list[str] = []
        errors: list[str] = []

        # Find all markdown files in kitty-specs/
        md_files: list[Path] = []

        # Main kitty-specs/
        main_specs = project_path / "kitty-specs"
        if main_specs.exists():
            md_files.extend(main_specs.rglob("*.md"))

        # Worktrees
        worktrees_dir = project_path / ".worktrees"
        if worktrees_dir.exists():
            for worktree in worktrees_dir.iterdir():
                if worktree.is_dir():
                    wt_specs = worktree / "kitty-specs"
                    if wt_specs.exists():
                        md_files.extend(wt_specs.rglob("*.md"))

        if not md_files:
            changes.append("No markdown files found")
            return changes, warnings, errors

        normalized_count = 0
        skipped_count = 0

        for md_file in sorted(md_files):
            # Skip if not a task/WP file (e.g., README.md, spec.md, etc.)
            # Only normalize files in tasks/ directories
            if "tasks" not in md_file.parts:
                continue

            try:
                if dry_run:
                    # Just check if it would change
                    try:
                        from specify_cli.frontmatter import FrontmatterManager

                        manager = FrontmatterManager()
                        original = md_file.read_text(encoding="utf-8-sig")
                        frontmatter, body = manager.read(md_file)

                        # Write to temp buffer
                        import io

                        buffer = io.StringIO()
                        buffer.write("---\n")
                        manager.yaml.dump(manager._normalize_frontmatter(frontmatter), buffer)
                        buffer.write("---\n")
                        buffer.write(body)
                        new_content = buffer.getvalue()

                        if original != new_content:
                            changes.append(f"Would normalize: {md_file.relative_to(project_path)}")
                            normalized_count += 1
                        else:
                            skipped_count += 1
                    except FrontmatterError:
                        warnings.append(f"Skip (no frontmatter): {md_file.relative_to(project_path)}")
                        skipped_count += 1
                else:
                    # Actually normalize
                    if normalize_file(md_file):
                        changes.append(f"Normalized: {md_file.relative_to(project_path)}")
                        normalized_count += 1
                    else:
                        skipped_count += 1

            except FrontmatterError as e:
                warnings.append(f"Skip (error): {md_file.relative_to(project_path)}: {e}")
                skipped_count += 1
            except Exception as e:
                errors.append(f"Failed to normalize {md_file.relative_to(project_path)}: {e}")

        if dry_run:
            changes.append(f"Would normalize {normalized_count} files, skip {skipped_count}")
        else:
            changes.append(f"Normalized {normalized_count} files, skipped {skipped_count}")

        return changes, warnings, errors


# Re-export agent utilities for backward compatibility
# The canonical source is now specify_cli.agent_utils.directories
# All new code should import from there instead
AGENT_DIR_TO_KEY = _AGENT_DIR_TO_KEY
get_agent_dirs_for_project = _get_agent_dirs_for_project


__all__ = [
    "CompleteLaneMigration",
    "AGENT_DIR_TO_KEY",
    "get_agent_dirs_for_project",
]
