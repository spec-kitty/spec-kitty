"""Migration 3.0.2: Restore prompt-driven command templates.

The 3.0.0 canonical context migration (step 6: ``rewrite_agent_shims``)
deleted prompt-driven command template files (specify, plan, tasks, etc.)
because it only generated CLI-driven thin shims.  This migration detects
the missing files and regenerates all 16 command files (7 CLI shims +
9 prompt-driven templates) for every configured agent.

Detection
---------
Returns ``True`` when any configured agent directory is missing at least
one prompt-driven command file from :data:`PROMPT_DRIVEN_COMMANDS`.

Idempotency
-----------
After the first successful run, every agent directory has all 16 files.
On a second run ``detect()`` finds all files present and returns ``False``,
so the upgrade runner skips this migration.
"""

from __future__ import annotations

from pathlib import Path

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult


def _compute_output_filename(command: str, agent_key: str) -> str:
    """Return the correct on-disk filename for *command* + *agent_key*."""
    from specify_cli.core.config import AGENT_COMMAND_CONFIG

    config = AGENT_COMMAND_CONFIG.get(agent_key)
    if config is None:
        return f"spec-kitty.{command}.md"

    ext: str = config["ext"]
    stem = command
    if agent_key == "codex":
        stem = stem.replace("-", "_")
    if ext:
        return f"spec-kitty.{stem}.{ext}"
    return f"spec-kitty.{stem}"


@MigrationRegistry.register
class RestorePromptCommandsMigration302(BaseMigration):
    """Restore prompt-driven command templates deleted by the 3.0.0 migration.

    Calls :func:`~specify_cli.migration.rewrite_shims.rewrite_agent_shims`
    which now generates all 16 command files (CLI shims + prompt templates).
    """

    migration_id = "3.0.2_restore_prompt_commands"
    description = (
        "Restore prompt-driven command templates (specify, plan, tasks, etc.) "
        "that were deleted by the 3.0.0 canonical context migration"
    )
    target_version = "3.0.2"

    def detect(self, project_path: Path) -> bool:
        """Return True if any prompt-driven command file is missing."""
        from specify_cli.agent_utils.directories import (
            AGENT_DIR_TO_KEY,
            get_agent_dirs_for_project,
        )
        from specify_cli.shims.registry import PROMPT_DRIVEN_COMMANDS

        agent_dirs = get_agent_dirs_for_project(project_path)
        for agent_root, subdir in agent_dirs:
            agent_dir = project_path / agent_root / subdir
            if not agent_dir.is_dir():
                continue

            agent_key = AGENT_DIR_TO_KEY.get(agent_root)
            if agent_key is None:
                continue

            for command in PROMPT_DRIVEN_COMMANDS:
                filename = _compute_output_filename(command, agent_key)
                if not (agent_dir / filename).exists():
                    return True

        return False

    def can_apply(self, project_path: Path) -> tuple[bool, str]:  # noqa: ARG002
        """Check that the rewrite function is available."""
        try:
            from specify_cli.migration.rewrite_shims import rewrite_agent_shims  # noqa: F401

            return True, ""
        except ImportError as exc:
            return False, f"rewrite_shims module not available: {exc}"

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        """Regenerate all 16 command files for every configured agent.

        Delegates to :func:`~specify_cli.migration.rewrite_shims.rewrite_agent_shims`
        which writes CLI shims + prompt-driven templates and cleans up stale files.
        """
        if dry_run:
            return MigrationResult(
                success=True,
                changes_made=["Would regenerate all agent command files (CLI shims + prompt templates)"],
            )

        from specify_cli.migration.rewrite_shims import rewrite_agent_shims

        rewrite_result = rewrite_agent_shims(project_path)

        changes = [
            f"Processed {rewrite_result.agents_processed} agent directories",
            f"Wrote {len(rewrite_result.files_written)} command files",
            f"Deleted {len(rewrite_result.files_deleted)} stale files",
        ]

        return MigrationResult(
            success=True,
            changes_made=changes,
            warnings=rewrite_result.warnings,
        )
