"""Migration: Update slash commands to Python CLI and flat structure."""

from __future__ import annotations

from pathlib import Path

from specify_cli.asset_preservation import (
    AnyProver,
    CanonicalContentProver,
    ManifestProver,
    guard_destructive_removal,
)
from specify_cli.runtime.generated_writer import write_generated_file

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult
from .m_0_9_1_complete_lane_migration import get_agent_dirs_for_project


def _sweep_legacy_command_tomls(
    commands_dir: Path,
    project_path: Path,
    *,
    dry_run: bool,
) -> tuple[list[str], list[str]]:
    """Ownership-gate the legacy ``.kittify/commands/*.toml`` sweep.

    Ownership proof (NFR-006): route every removal through the
    asset-preservation guard so a ``.toml``'s name/location can never authorize
    deleting user-authored content (charter L463-479, contract C1/C4 US4). The
    ``AnyProver`` is ordered **manifest-first** — a cheap exact-path lookup in
    the command-skills manifest — then falls back to a whole-file version-marker
    scan. The marker (``<!-- spec-kitty-command-version:``) is the only command
    marker syntax and can sit PAST a 15-line head inside a ``.toml`` prompt
    body, so ``CanonicalContentProver`` scans the whole file (its default). In
    practice the command-skills manifest schema restricts entry paths to
    ``.agents/skills/spec-kitty.<cmd>/SKILL.md``, so a legacy ``.toml`` is only
    ever proven by the marker; the manifest predicate is kept for a uniform,
    guard-owned composition. The guard performs the delete itself when a proof
    is found; an unprovable file is preserved in place with a diagnostic.
    """
    changes: list[str] = []
    warnings: list[str] = []
    prover = AnyProver(
        [
            ManifestProver(check_managed=False, check_command=True),
            CanonicalContentProver(),
        ]
    )

    for toml_file in sorted(commands_dir.glob("*.toml")):
        verdict = guard_destructive_removal(
            toml_file,
            project_path,
            prover=prover,
            dry_run=dry_run,
        )
        if verdict.owned:
            prefix = "Would remove" if dry_run else "Removed"
            changes.append(f"{prefix} legacy {toml_file.name}")
        else:
            warnings.append(verdict.diagnostic)

    if not dry_run:
        try:
            if not any(commands_dir.iterdir()):
                commands_dir.rmdir()
                changes.append("Removed empty .kittify/commands/ directory")
        except OSError as e:
            warnings.append(f"Failed to remove .kittify/commands/: {e}")

    return changes, warnings


@MigrationRegistry.register
class UpdateSlashCommandsMigration(BaseMigration):
    """Update all agent slash commands to use Python CLI and flat tasks/ structure.

    This migration addresses two critical issues from feature 008 and 007:
    1. Slash commands still referenced deleted bash scripts (feature 008 bug)
    2. Slash commands instructed agents to create subdirectories (feature 007 violation)

    This migration:
    1. Detects if slash commands have old bash script references
    2. Detects if slash commands have subdirectory instructions
    3. Re-copies templates from mission to get latest Python CLI + flat structure
    4. Updates ALL 12 supported agent directories
    """

    migration_id = "0.10.2_update_slash_commands"
    description = "Update slash commands to Python CLI and flat structure"
    target_version = "0.10.2"

    def detect(self, project_path: Path) -> bool:
        """Check if slash commands need updating."""
        # Check agent directories respecting user config
        agent_dirs = get_agent_dirs_for_project(project_path)

        for agent_root, subdir in agent_dirs:
            agent_dir = project_path / agent_root / subdir

            if not agent_dir.exists():
                continue

            # Check for bash script references (old) or subdirectory references
            for cmd_file in agent_dir.glob("spec-kitty.*.md"):
                content = cmd_file.read_text(encoding="utf-8")
                # Check for bash/PowerShell scripts
                if ".kittify/scripts/bash/" in content or "scripts/bash/" in content:
                    return True
                if ".kittify/scripts/powershell/" in content or "scripts/powershell/" in content:
                    return True
                # Check for subdirectory violations (feature 007)
                if "tasks/planned/" in content or "tasks/doing/" in content:  # noqa: SIM102
                    # Exclude "WRONG" examples
                    if "WRONG" not in content or content.count("tasks/planned/") > 2:
                        return True

        return False

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        """Check if we have mission templates to copy from."""
        missions_dir = project_path / ".kittify" / "missions"
        if not missions_dir.exists():
            return False, "No missions directory found"

        # Look for software-dev mission
        software_dev_templates = missions_dir / "software-dev" / "command-templates"
        if software_dev_templates.exists():
            return True, ""

        # Look for any mission with command-templates
        for mission_dir in missions_dir.iterdir():
            if mission_dir.is_dir():
                templates = mission_dir / "command-templates"
                if templates.exists():
                    return True, ""

        return False, "No mission command templates found"

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:  # noqa: C901
        """Update slash commands with latest templates."""
        changes: list[str] = []
        warnings: list[str] = []
        errors: list[str] = []

        missions_dir = project_path / ".kittify" / "missions"

        # Find mission templates
        command_templates_dir = None
        software_dev_templates = missions_dir / "software-dev" / "command-templates"

        if software_dev_templates.exists():
            command_templates_dir = software_dev_templates
            mission_name = "software-dev"
        else:
            # Find first mission with templates
            for mission_dir in sorted(missions_dir.iterdir()):
                if mission_dir.is_dir():
                    templates = mission_dir / "command-templates"
                    if templates.exists():
                        command_templates_dir = templates
                        mission_name = mission_dir.name
                        break

        if not command_templates_dir:
            errors.append("No mission command templates found")
            return MigrationResult(
                success=False,
                changes_made=changes,
                errors=errors,
                warnings=warnings,
            )

        # Update slash commands in configured agent directories (overwrite existing)
        total_updated = 0
        agent_dirs = get_agent_dirs_for_project(project_path)

        for agent_root, subdir in agent_dirs:
            agent_dir = project_path / agent_root / subdir

            if not agent_dir.exists():
                continue

            updated_count = 0
            for template_path in sorted(command_templates_dir.glob("*.md")):
                filename = f"spec-kitty.{template_path.stem}.md"
                dest_path = agent_dir / filename

                if dry_run:
                    changes.append(f"Would update {agent_root}: {dest_path.name}")
                else:
                    write_generated_file(dest_path, template_path.read_text(encoding="utf-8"))
                    updated_count += 1

            if updated_count > 0:
                agent_name = agent_root.strip(".")
                changes.append(f"Updated {updated_count} slash commands for {agent_name}")
                total_updated += updated_count

        if total_updated > 0:
            changes.append(f"Total: Updated {total_updated} slash commands from {mission_name} mission")
            changes.append("Slash commands now use Python CLI (no bash scripts)")
            changes.append("Slash commands now enforce flat tasks/ structure (feature 007)")

        commands_dir = project_path / ".kittify" / "commands"
        if commands_dir.exists():
            sweep_changes, sweep_warnings = _sweep_legacy_command_tomls(
                commands_dir,
                project_path,
                dry_run=dry_run,
            )
            changes.extend(sweep_changes)
            warnings.extend(sweep_warnings)

        success = len(errors) == 0
        return MigrationResult(
            success=success,
            changes_made=changes,
            errors=errors,
            warnings=warnings,
        )
