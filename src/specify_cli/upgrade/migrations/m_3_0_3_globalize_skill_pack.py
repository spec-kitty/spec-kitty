"""Migration: relink canonical doctrine skills to user-global roots."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult
from kernel.paths import to_posix

if TYPE_CHECKING:
    from specify_cli.skills.registry import SkillRegistry


def _discover_registry(project_path: Path, *, stage: bool = True) -> SkillRegistry | None:
    """Resolve the project's skill catalog (built-in plus pack skills) through the one seam.

    ``detect`` passes ``stage=False`` (read-only); only ``apply`` stages.
    """
    from specify_cli.skills.catalog import resolve_project_skill_catalog

    return resolve_project_skill_catalog(project_path, stage=stage)


def _installable_agents(project_path: Path) -> list[str]:
    from specify_cli.core.agent_config import load_agent_config
    from specify_cli.core.config import AGENT_SKILL_CONFIG, SKILL_CLASS_WRAPPER

    installable: list[str] = []
    for agent_key in load_agent_config(project_path).available:
        config = AGENT_SKILL_CONFIG.get(agent_key)
        if config is None or config["class"] == SKILL_CLASS_WRAPPER:
            continue
        installable.append(agent_key)
    return installable


@MigrationRegistry.register
class GlobalizeSkillPackMigration(BaseMigration):
    """Relink canonical doctrine skills so future CLI upgrades are global-only."""

    migration_id = "3.0.3_globalize_skill_pack"
    description = "Relink canonical doctrine skills to user-global roots"
    target_version = "3.0.3"

    def detect(self, project_path: Path) -> bool:
        from specify_cli.skills.catalog import PackSkillCatalogError
        from specify_cli.skills.manifest import ORIGIN_BUILTIN, load_manifest
        from specify_cli.skills.paths import get_primary_project_skill_root

        if not (project_path / ".kittify").is_dir():
            return False

        try:
            registry = _discover_registry(project_path, stage=False)
        except PackSkillCatalogError:
            return True  # fail closed: apply() reports the broken pack as a migration error
        if registry is None:
            return False

        skills = registry.discover_skills()
        if not skills:
            return False

        agents = _installable_agents(project_path)
        if not agents:
            return False

        manifest = load_manifest(project_path)
        if manifest is not None:
            for entry in manifest.entries:
                if entry.skill_name.startswith("spec-kitty-") and entry.delivery_mode != "symlink":
                    return True

        for agent_key in agents:
            root = get_primary_project_skill_root(agent_key)
            if root is None:
                continue
            for skill in skills:
                if skill.origin != ORIGIN_BUILTIN:
                    continue  # pack skills are copies by design, never user-global links
                skill_file = project_path / root / skill.name / "SKILL.md"
                if not skill_file.exists():
                    return True
                if not skill_file.is_symlink():
                    return True

        return False

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        if not (project_path / ".kittify").is_dir():
            return False, ".kittify/ directory does not exist (not initialized)"
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        from specify_cli.skills.catalog import PackSkillCatalogError
        from specify_cli.skills.installer import install_all_skills
        from specify_cli.skills.manifest import ORIGIN_PACK, load_manifest, save_manifest

        changes: list[str] = []
        warnings: list[str] = []
        errors: list[str] = []
        preserved_paths: list[str] = []

        try:
            registry = _discover_registry(project_path, stage=not dry_run)
        except PackSkillCatalogError as exc:
            errors.append(f"Pack skills could not be resolved: {exc}")
            return MigrationResult(success=False, changes_made=changes, errors=errors)
        if registry is None:
            errors.append("No canonical skills discovered for relinking")
            return MigrationResult(success=False, changes_made=changes, errors=errors)

        skills = registry.discover_skills()
        if not skills:
            errors.append("No canonical skills discovered for relinking")
            return MigrationResult(success=False, changes_made=changes, errors=errors)

        agents = _installable_agents(project_path)
        if not agents:
            warnings.append("No skill-installing agents configured; skipping relink")
            return MigrationResult(success=True, changes_made=changes, warnings=warnings)

        if dry_run:
            changes.append(
                f"Would relink {len(skills)} canonical skill(s) for {len(agents)} agent(s)"
            )
            return MigrationResult(success=True, changes_made=changes)

        archived_paths: list[Path] = []
        manifest = install_all_skills(project_path, agents, registry, archived_paths=archived_paths)
        existing = load_manifest(project_path)
        preserved: list[Any] = []
        if existing is not None:
            canonical_names = {skill.name for skill in skills}
            preserved = [
                entry
                for entry in existing.entries
                # Pack-origin entries are owned by the installer pass above: a
                # retired pack skill must not be resurrected from the old manifest.
                if (entry.skill_name not in canonical_names and entry.origin != ORIGIN_PACK) or entry.agent_key not in agents
            ]
            manifest.entries.extend(preserved)

        if not manifest.entries and not preserved:
            errors.append("No managed skill files were linked for any configured agent")
            return MigrationResult(success=False, changes_made=changes, errors=errors)

        manifest.spec_kitty_version = "3.0.3"
        save_manifest(manifest, project_path)

        preserved_paths = sorted(
            to_posix(path.relative_to(project_path))
            for path in archived_paths
        )

        changes.append(
            f"Relinked {len(skills)} canonical skill(s) for {len(agents)} agent(s) "
            f"({len(manifest.entries)} managed files)"
        )
        changes.append("Updated .kittify/skills-manifest.json for global canonical skill links")
        changes.extend(
            f"Archived customized skill file for manual review: {path}"
            for path in preserved_paths
        )
        return MigrationResult(
            success=True,
            changes_made=changes,
            warnings=warnings,
            manual_review_required=bool(preserved_paths),
            preserved_paths=preserved_paths,
        )
