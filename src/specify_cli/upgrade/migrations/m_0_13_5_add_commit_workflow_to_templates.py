"""Migration: Add Commit Workflow section to implement.md templates.

This migration updates both software-dev and documentation mission implement
templates to include the commit workflow section that prevents agents from
marking WPs as complete without committing their work.

Fixes GitHub Issue #72 for existing projects.
"""

from __future__ import annotations

from pathlib import Path

try:
    from importlib.resources import files
except ImportError:
    from importlib_resources import files  # type: ignore

from specify_cli.core.paths import load_meta_fail_closed
from specify_cli.runtime.generated_writer import write_generated_file

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult
from .m_0_9_1_complete_lane_migration import get_agent_dirs_for_project


@MigrationRegistry.register
class AddCommitWorkflowToTemplatesMigration(BaseMigration):
    """Add Commit Workflow section to implement slash commands.

    This migration:
    1. Loads canonical implement.md templates from packaged missions
    2. Copies to all agent slash command directories
    3. Updates both software-dev and documentation missions
    4. Only updates configured agents (respects agent config)
    """

    migration_id = "0.13.5_add_commit_workflow_to_templates"
    description = "Add commit workflow section to implement slash commands"
    target_version = "0.13.5"

    TEMPLATE_FILE = "implement.md"
    SLASH_COMMAND_FILE = "spec-kitty.implement.md"

    def detect(self, project_path: Path) -> bool:  # noqa: ARG002
        """Always returns False — command templates removed in WP10 (canonical context architecture).

        Shim generation (spec-kitty agent shim) now replaces template-based agent commands.
        This migration is retained for history but is permanently inert.
        """
        return False

    def can_apply(self, project_path: Path) -> tuple[bool, str]:  # noqa: ARG002
        """Always returns False — command templates removed in WP10."""
        return (
            False,
            "Command templates were removed in WP10 (canonical context architecture). Shim generation replaces template-based commands.",
        )

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:  # noqa: C901
        """Update implement slash commands across all agent directories."""
        changes: list[str] = []
        warnings: list[str] = []
        errors: list[str] = []

        # Detect mission type from meta.json
        meta_file = project_path / ".kittify" / "meta.json"
        if not meta_file.exists():
            warnings.append("No meta.json found - cannot determine mission type")
            # Try both missions as fallback
            missions_to_update = ["software-dev", "documentation"]
        else:
            try:
                # Canonical fail-closed reader (#2478) over the project-level
                # .kittify/ dir; a malformed meta.json raises MissionMetaReadError,
                # caught below as the historical "warn and fall back" arm. (The
                # runner never reaches apply() since WP10 -- detect() is False and
                # can_apply() refuses -- so this only keeps direct calls honest.)
                meta = load_meta_fail_closed(meta_file.parent)
                if meta is None:  # vanished after exists(): same fallback as before
                    raise FileNotFoundError(meta_file)
                current_mission = meta.get("mission_name", "software-dev")
                missions_to_update = [current_mission]
            except Exception as e:
                warnings.append(f"Cannot parse meta.json: {e}")
                missions_to_update = ["software-dev", "documentation"]

        # Load template from packaged missions
        for mission_name in missions_to_update:
            try:
                data_root = files("specify_cli")
                template_path = data_root.joinpath("missions", mission_name, "command-templates", self.TEMPLATE_FILE)

                if not template_path.exists():
                    warnings.append(f"Template not found for mission: {mission_name}")
                    continue

                template_content = template_path.read_text(encoding="utf-8")
            except Exception as e:
                errors.append(f"Failed to read {mission_name} template: {e}")
                continue

            # Update configured agent directories
            agents_updated = 0
            agent_dirs = get_agent_dirs_for_project(project_path)
            for agent_dir, subdir in agent_dirs:
                agent_path = project_path / agent_dir / subdir
                slash_cmd = agent_path / self.SLASH_COMMAND_FILE

                # Skip if agent directory doesn't exist
                if not agent_path.exists():
                    continue

                # Check if this agent has implement template
                if slash_cmd.exists():
                    current_content = slash_cmd.read_text(encoding="utf-8")

                    # Check if already migrated
                    if current_content == template_content:
                        continue  # Already up to date

                    # Check if needs migration (missing commit workflow)
                    if "Commit Workflow" not in current_content:
                        if dry_run:
                            changes.append(f"Would update: {agent_dir}/{subdir}/{self.SLASH_COMMAND_FILE}")
                        else:
                            try:
                                write_generated_file(slash_cmd, template_content)
                                changes.append(f"Updated: {agent_dir}/{subdir}/{self.SLASH_COMMAND_FILE}")
                                agents_updated += 1
                            except Exception as e:
                                errors.append(f"Failed to update {agent_dir}/{subdir}: {e}")

            if agents_updated > 0:
                if dry_run:
                    changes.append(f"Would update {agents_updated} agent implement templates ({mission_name})")
                else:
                    changes.append(f"Updated {agents_updated} agent implement templates ({mission_name})")
            elif not warnings:  # Only log if we tried to update this mission
                changes.append(f"No agent implement templates needed updates ({mission_name})")

        return MigrationResult(
            success=len(errors) == 0,
            changes_made=changes,
            errors=errors,
            warnings=warnings,
        )
