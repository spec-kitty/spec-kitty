"""Migration: install canonical skill pack into existing projects.

Discovers canonical skills from the doctrine layer and installs them into
all configured agent skill roots using the managed skill manifest system.
This brings existing 2.0.11+ projects up to parity with fresh ``spec-kitty init``
behavior for skill distribution.

Scope:
- Discovers all canonical skills from src/charter/offering/skills/
- Installs skills for all configured agents per the capability matrix
- Creates .kittify/skills-manifest.json with installed file tracking
- Skips wrapper-only agents (no skill root)
- Deduplicates shared-root installations
"""

from __future__ import annotations

from pathlib import Path

from kernel.clock import now_utc_iso

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult


@MigrationRegistry.register
class InstallSkillsMigration(BaseMigration):
    """Install canonical skill pack into existing projects during upgrade."""

    migration_id = "2.0.11_install_skills"
    description = "Install canonical skill pack for configured agents"
    target_version = "2.0.11"

    def detect(self, project_path: Path) -> bool:
        """Return True if no skills manifest exists (skills not yet installed)."""
        manifest_path = project_path / ".kittify" / "skills-manifest.json"
        return not manifest_path.exists()

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        """Check that .kittify/ exists and skills can be discovered."""
        kittify = project_path / ".kittify"
        if not kittify.is_dir():
            return False, ".kittify/ directory does not exist (not initialized)"

        # Skill discovery is best-effort. If no skills are found, apply()
        # handles it as a no-op warning rather than blocking the upgrade.
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        """Install skills for all configured agents."""
        from specify_cli.core.agent_config import load_agent_config
        from specify_cli.skills.installer import install_skills_for_agent
        from specify_cli.skills.manifest import ManagedSkillManifest, save_manifest
        from specify_cli.skills.catalog import PackSkillCatalogError, resolve_project_skill_catalog

        changes: list[str] = []
        warnings: list[str] = []
        errors: list[str] = []

        # Discover skills through the one catalog seam (built-in plus pack skills).
        try:
            registry = resolve_project_skill_catalog(project_path)
        except PackSkillCatalogError as exc:
            errors.append(f"Pack skills could not be resolved: {exc}")
            return MigrationResult(success=False, changes_made=changes, errors=errors)
        skills = registry.discover_skills() if registry is not None else []

        if not skills:
            warnings.append("No skills found to install")
            return MigrationResult(success=True, changes_made=changes, warnings=warnings)

        # Get configured agents — config parse failure is a real error
        # (returning success=True would stamp the migration as applied,
        # permanently skipping skill installation for this project)
        try:
            agent_config = load_agent_config(project_path)
            agent_keys = agent_config.available
        except Exception as exc:
            errors.append(f"Could not load agent config: {exc}")
            return MigrationResult(success=False, changes_made=changes, errors=errors)

        if not agent_keys:
            warnings.append("No agents configured; skipping skill installation")
            return MigrationResult(success=True, changes_made=changes, warnings=warnings)

        if dry_run:
            changes.append(
                f"Would install {len(skills)} skill(s) for {len(agent_keys)} agent(s)"
            )
            return MigrationResult(success=True, changes_made=changes)

        # Install skills
        manifest = ManagedSkillManifest(
            created_at=now_utc_iso(),
            updated_at=now_utc_iso(),
            spec_kitty_version="2.0.11",
        )
        shared_root_installed: set[str] = set()

        for agent_key in agent_keys:
            try:
                entries = install_skills_for_agent(
                    project_path,
                    agent_key,
                    skills,
                    shared_root_installed=shared_root_installed,
                )
                for entry in entries:
                    manifest.add_entry(entry)
            except Exception as exc:
                errors.append(f"Skill installation failed for {agent_key}: {exc}")

        # Save manifest only if files were actually installed
        if manifest.entries:
            save_manifest(manifest, project_path)
            changes.append(
                f"Installed {len(skills)} skill(s) for {len(agent_keys)} agent(s) "
                f"({len(manifest.entries)} managed files)"
            )
            changes.append("Created .kittify/skills-manifest.json")
        else:
            # No files installed — report failure so the runner does not
            # stamp the migration as applied (allows re-run on next upgrade)
            errors.append("No skill files were installed for any configured agent")

        success = len(errors) == 0
        return MigrationResult(
            success=success, changes_made=changes, errors=errors, warnings=warnings
        )
