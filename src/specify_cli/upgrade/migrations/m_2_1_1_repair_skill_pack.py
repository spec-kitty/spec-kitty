"""Migration: repair bundled skill installation after the 2.1.0 wheel defect."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult

if TYPE_CHECKING:
    from specify_cli.skills.registry import SkillRegistry


def _discover_registry(project_path: Path, *, stage: bool = True) -> SkillRegistry | None:
    """Resolve the project's skill catalog (built-in plus pack skills) through the one seam.

    ``detect`` passes ``stage=False`` (read-only); only ``apply`` stages.
    """
    from specify_cli.skills.catalog import resolve_project_skill_catalog

    return resolve_project_skill_catalog(project_path, stage=stage)


def _get_installable_agents(agent_keys: list[str]) -> list[str]:
    """Filter configured agents down to those that actually accept skill files."""
    from specify_cli.core.config import AGENT_SKILL_CONFIG, SKILL_CLASS_WRAPPER

    installable: list[str] = []
    for agent_key in agent_keys:
        config = AGENT_SKILL_CONFIG.get(agent_key)
        if config is None:
            continue
        if config["class"] == SKILL_CLASS_WRAPPER:
            continue
        installable.append(agent_key)
    return installable


@MigrationRegistry.register
class RepairSkillPackMigration(BaseMigration):
    """Repair missing canonical skills for projects upgraded with 2.1.0."""

    migration_id = "2.1.1_repair_skill_pack"
    description = "Repair missing canonical skill installations after the 2.1.0 wheel defect"
    target_version = "2.1.1"

    def detect(self, project_path: Path) -> bool:
        """Return True when a project is missing expected managed skill state."""
        from specify_cli.skills.catalog import PackSkillCatalogError
        from specify_cli.core.agent_config import load_agent_config
        from specify_cli.skills.manifest import load_manifest
        from specify_cli.skills.verifier import verify_installed_skills

        if not (project_path / ".kittify").is_dir():
            return False

        try:
            agent_keys = load_agent_config(project_path).available
        except Exception:
            return True

        installable_agents = _get_installable_agents(agent_keys)
        if not installable_agents:
            return False

        try:
            registry = _discover_registry(project_path, stage=False)
        except PackSkillCatalogError:
            return True  # fail closed: apply() reports the broken pack as a migration error
        if registry is None:
            return True

        skills = registry.discover_skills()
        if not skills:
            return True

        manifest = load_manifest(project_path)
        if manifest is None or not manifest.entries:
            return True

        expected_pairs = {
            (agent_key, skill.name)
            for agent_key in installable_agents
            for skill in skills
        }
        actual_pairs = {
            (entry.agent_key, entry.skill_name)
            for entry in manifest.entries
            if entry.source_file == "SKILL.md"
        }
        if not expected_pairs.issubset(actual_pairs):
            return True

        return not verify_installed_skills(project_path).ok

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        """Require an initialized project root."""
        if not (project_path / ".kittify").is_dir():
            return False, ".kittify/ directory does not exist (not initialized)"
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        """Rebuild canonical managed skills from the packaged doctrine registry."""
        from specify_cli.skills.catalog import PackSkillCatalogError
        from specify_cli.core.agent_config import load_agent_config
        from specify_cli.skills.installer import install_all_skills
        from specify_cli.skills.manifest import save_manifest

        changes: list[str] = []
        warnings: list[str] = []
        errors: list[str] = []

        try:
            registry = _discover_registry(project_path, stage=not dry_run)
        except PackSkillCatalogError as exc:
            errors.append(f"Pack skills could not be resolved: {exc}")
            return MigrationResult(success=False, changes_made=changes, errors=errors)
        if registry is None:
            errors.append("No bundled skills found in the installed package")
            return MigrationResult(success=False, changes_made=changes, errors=errors)

        skills = registry.discover_skills()
        if not skills:
            errors.append("No canonical skills discovered for repair")
            return MigrationResult(success=False, changes_made=changes, errors=errors)

        try:
            agent_keys = load_agent_config(project_path).available
        except Exception as exc:
            errors.append(f"Could not load agent config: {exc}")
            return MigrationResult(success=False, changes_made=changes, errors=errors)

        installable_agents = _get_installable_agents(agent_keys)
        if not installable_agents:
            warnings.append("No skill-installing agents configured; skipping repair")
            return MigrationResult(success=True, changes_made=changes, warnings=warnings)

        if dry_run:
            changes.append(
                f"Would repair/install {len(skills)} skill(s) for {len(installable_agents)} agent(s)"
            )
            return MigrationResult(success=True, changes_made=changes)

        try:
            manifest = install_all_skills(project_path, installable_agents, registry)
        except Exception as exc:
            errors.append(f"Skill repair failed: {exc}")
            return MigrationResult(success=False, changes_made=changes, errors=errors)

        if not manifest.entries:
            errors.append("No skill files were installed for any configured agent")
            return MigrationResult(success=False, changes_made=changes, errors=errors)

        manifest.spec_kitty_version = "2.1.1"
        save_manifest(manifest, project_path)

        changes.append(
            f"Installed {len(skills)} skill(s) for {len(installable_agents)} agent(s) "
            f"({len(manifest.entries)} managed files)"
        )
        changes.append("Rebuilt .kittify/skills-manifest.json")

        return MigrationResult(success=True, changes_made=changes, warnings=warnings)
