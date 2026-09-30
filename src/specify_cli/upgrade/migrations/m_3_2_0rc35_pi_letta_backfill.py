"""Migration: backfill .pi/ and .letta/ gitignore entries and skill files.

Existing projects initialised before Pi/Letta support was added may be missing
both the gitignore protection entries for the agent runtime directories and the
Agent-Skills files under ``.agents/skills/``.  This migration detects both gaps
and repairs them idempotently.
"""

from __future__ import annotations

from pathlib import Path

from specify_cli.gitignore_manager import GitignoreManager, read_ignore_file_text

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult


# Maps agent key -> gitignore entry that must be present for that agent.
_AGENT_GITIGNORE_ENTRIES: dict[str, str] = {
    "pi": ".pi/",
    "letta": ".letta/",
}

# The skills sub-directory shared by both agents (canonical install location).
_SKILLS_ROOT = ".agents/skills"


def _skills_complete(project_path: Path) -> bool:
    """Return True if every CANONICAL_COMMANDS SKILL.md exists under _SKILLS_ROOT."""
    from specify_cli.skills.command_installer import CANONICAL_COMMANDS

    for cmd in CANONICAL_COMMANDS:
        skill_file = project_path / _SKILLS_ROOT / f"spec-kitty.{cmd}" / "SKILL.md"
        if not skill_file.exists():
            return False
    return True


def _agent_skill_manifest_complete(project_path: Path, agent_key: str) -> bool:
    """Return True if every command-skill manifest entry claims *agent_key*."""
    from specify_cli.skills.command_installer import CANONICAL_COMMANDS
    from specify_cli.skills import manifest_store

    try:
        manifest = manifest_store.load(project_path)
    except Exception:
        return False

    for cmd in CANONICAL_COMMANDS:
        rel_path = f"{_SKILLS_ROOT}/spec-kitty.{cmd}/SKILL.md"
        entry = manifest.find(rel_path)
        if entry is None or agent_key not in entry.agents:
            return False
    return True


def _agent_skills_complete(project_path: Path, agent_key: str) -> bool:
    """Return True when files exist and manifest ownership is complete."""
    return _skills_complete(project_path) and _agent_skill_manifest_complete(
        project_path, agent_key
    )


@MigrationRegistry.register
class PiLettaBackfillMigration(BaseMigration):
    """Backfill .pi/ and .letta/ gitignore entries and skill files for configured agents."""

    migration_id = "3.2.0rc35_pi_letta_agent_backfill"
    description = "Backfill .pi/ and .letta/ gitignore entries and skill files for configured agents"
    target_version = "3.2.0rc35"

    def detect(self, project_path: Path) -> bool:
        """Return True when the project needs pi/letta gitignore or skill backfill."""
        from specify_cli.core.agent_config import get_configured_agents

        if not (project_path / ".kittify").is_dir():
            return False

        try:
            configured = set(get_configured_agents(project_path))
        except Exception:
            return False

        pi_letta_configured = configured & {"pi", "letta"}
        if not pi_letta_configured:
            return False

        # Check for missing gitignore entries.
        gitignore_text = read_ignore_file_text(project_path / ".gitignore")
        for agent_key in pi_letta_configured:
            entry = _AGENT_GITIGNORE_ENTRIES[agent_key]
            if entry not in gitignore_text:
                return True

        # Check for missing skill files or missing per-agent manifest ownership.
        return any(
            not _agent_skills_complete(project_path, agent_key)
            for agent_key in pi_letta_configured
        )

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        if not project_path.exists():
            return False, f"Project path does not exist: {project_path}"
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        """Add missing gitignore entries and trigger skill-pack repair as needed."""
        from specify_cli.core.agent_config import get_configured_agents

        changes: list[str] = []
        warnings: list[str] = []
        errors: list[str] = []

        try:
            configured = set(get_configured_agents(project_path))
        except Exception as exc:
            errors.append(f"Could not load agent config: {exc}")
            return MigrationResult(success=False, changes_made=changes, errors=errors)

        # --- Gitignore backfill ---
        manager = GitignoreManager(project_path)

        for agent_key, entry in _AGENT_GITIGNORE_ENTRIES.items():
            if agent_key not in configured:
                continue

            gitignore_text = read_ignore_file_text(project_path / ".gitignore")
            if entry in gitignore_text:
                continue

            if dry_run:
                changes.append(f"Would add {entry} to .gitignore")
            else:
                manager.ensure_entries([entry])
                changes.append(f"Added {entry} to .gitignore")

        # --- Skill-pack backfill ---
        for agent_key in ("pi", "letta"):
            if agent_key not in configured:
                continue

            if _agent_skills_complete(project_path, agent_key):
                continue

            if dry_run:
                changes.append(f"Would repair skill pack for {agent_key}")
                continue

            try:
                from specify_cli.skills import command_installer as _ci

                _ci.install(project_path, agent_key)
                changes.append(f"Repaired skill pack for {agent_key}")
            except Exception as exc:
                warnings.append(
                    f"Skill repair for {agent_key} skipped: {exc}"
                )

        return MigrationResult(
            success=True,
            changes_made=changes,
            warnings=warnings,
            errors=errors,
        )
