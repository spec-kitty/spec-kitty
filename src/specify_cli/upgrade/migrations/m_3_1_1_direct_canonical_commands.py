"""Migration 3.1.1: Replace shim-based command files with direct canonical commands.

Projects initialized before this version have command files that route through
``spec-kitty agent shim <command>`` -- an intermediate dispatch layer that has
been removed.  This migration regenerates all CLI-driven command files so they
call canonical ``spec-kitty`` commands directly (e.g.
``spec-kitty agent action implement``, ``spec-kitty merge``, etc.).

Detection heuristic
-------------------
A project needs this migration if any CLI-driven command file contains the
string ``"spec-kitty agent shim"``.

Idempotency
-----------
After the first run all CLI-driven files contain direct commands.  On a second
run the detection heuristic returns ``False`` so ``apply()`` is never called.
Even if called directly, ``rewrite_agent_shims()`` is itself idempotent --
files are overwritten with identical content.
"""

from __future__ import annotations

from pathlib import Path

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult
from .m_0_9_1_complete_lane_migration import get_agent_dirs_for_project


# Old shim marker that should no longer appear in generated command files.
_OLD_SHIM_MARKER = "spec-kitty agent shim"


@MigrationRegistry.register
class DirectCanonicalCommandsMigration(BaseMigration):
    """Replace shim-based command files with direct canonical CLI commands.

    Idempotent: files that already contain direct commands are overwritten
    with identical content; no data is lost.
    """

    migration_id = "3.1.1_direct_canonical_commands"
    description = (
        "Replace agent shim dispatch files with direct canonical CLI commands "
        "(e.g. spec-kitty agent action implement instead of spec-kitty agent shim implement)"
    )
    target_version = "3.1.1"

    def detect(self, project_path: Path) -> bool:
        """Return ``True`` if any CLI-driven command file uses the old shim dispatch."""
        from specify_cli.shims.registry import CLI_DRIVEN_COMMANDS

        agent_dirs = get_agent_dirs_for_project(project_path)
        for agent_root, subdir in agent_dirs:
            agent_dir = project_path / agent_root / subdir
            if not agent_dir.is_dir():
                continue
            for command in CLI_DRIVEN_COMMANDS:
                for candidate in agent_dir.glob(f"spec-kitty.{command}.*"):
                    try:
                        content = candidate.read_text(encoding="utf-8")
                    except OSError:
                        continue
                    if _OLD_SHIM_MARKER in content:
                        return True
        return False

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        """Always applicable -- no external dependencies required."""
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        """Regenerate all agent command files with direct canonical commands.

        Args:
            project_path: Root of the consumer project.
            dry_run:      When ``True``, report what *would* change but write nothing.

        Returns:
            :class:`~specify_cli.upgrade.migrations.base.MigrationResult` with
            details of files written and deleted.
        """
        from specify_cli.migration.rewrite_shims import rewrite_agent_shims

        changes: list[str] = []
        warnings: list[str] = []
        errors: list[str] = []

        if dry_run:
            changes.append(
                "Would regenerate all CLI-driven command files to use direct canonical commands"
            )
            return MigrationResult(
                success=True,
                changes_made=changes,
                errors=errors,
                warnings=warnings,
            )

        try:
            result = rewrite_agent_shims(project_path)
        except Exception as exc:
            errors.append(f"rewrite_agent_shims failed: {exc}")
            return MigrationResult(
                success=False,
                changes_made=changes,
                errors=errors,
                warnings=warnings,
            )

        for path in result.files_written:
            try:
                rel = str(path.relative_to(project_path))
            except ValueError:
                rel = str(path)
            changes.append(f"Regenerated: {rel}")

        for path in result.files_deleted:
            try:
                rel = str(path.relative_to(project_path))
            except ValueError:
                rel = str(path)
            changes.append(f"Deleted stale: {rel}")

        warnings.extend(result.warnings)

        if not changes:
            changes.append("No command files needed updating")

        return MigrationResult(
            success=True,
            changes_made=changes,
            errors=errors,
            warnings=warnings,
        )
