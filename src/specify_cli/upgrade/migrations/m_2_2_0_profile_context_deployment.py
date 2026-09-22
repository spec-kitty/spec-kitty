"""Migration: retire the legacy profile-context command template.

The old ``/spec-kitty.profile-context`` surface is no longer part of the
consumer command registry or root CLI. Standalone governed work now routes
through ``spec-kitty dispatch`` and ``profiles`` commands.
This migration no longer deploys the legacy command; when it sees stale
generated copies in configured agent command directories, it removes them.
"""

from __future__ import annotations

from pathlib import Path

from specify_cli.asset_preservation import (
    CanonicalContentProver,
    guard_destructive_removal,
)

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult
from .m_0_9_1_complete_lane_migration import get_agent_dirs_for_project

_DEST_FILENAME = "spec-kitty.profile-context.md"


@MigrationRegistry.register
class ProfileContextDeploymentMigration(BaseMigration):
    """Remove stale /spec-kitty.profile-context command templates."""

    migration_id = "2.2.0_profile_context_deployment"
    description = "Retire /spec-kitty.profile-context slash command from configured agents"
    target_version = "2.2.0"

    def detect(self, project_path: Path) -> bool:
        """Return True if any configured agent dir still has the legacy template."""
        for agent_root, subdir in get_agent_dirs_for_project(project_path):
            agent_dir = project_path / agent_root / subdir
            if agent_dir.exists() and (agent_dir / _DEST_FILENAME).exists():
                return True
        return False

    def can_apply(self, project_path: Path) -> tuple[bool, str]:  # noqa: ARG002
        """Always safe to apply; missing dirs are silently skipped."""
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        """Remove profile-context.md from every configured and present agent dir."""
        changes: list[str] = []
        errors: list[str] = []
        warnings: list[str] = []
        preserved: list[str] = []

        for agent_root, subdir in get_agent_dirs_for_project(project_path):
            agent_dir = project_path / agent_root / subdir
            if not agent_dir.exists():
                continue

            dest = agent_dir / _DEST_FILENAME
            if not dest.exists():
                continue

            rel = str(dest.relative_to(project_path))
            if dry_run:
                changes.append(f"Would remove retired {rel}")
                continue

            # Ownership gate (NFR-006): the retired command filename is not
            # proof — only a version marker / shipped canonical authorizes the
            # delete, so a user file that reuses the name is preserved. The
            # guard performs the removal on a proven-owned file.
            try:
                verdict = guard_destructive_removal(dest, project_path, prover=CanonicalContentProver())
            except OSError as exc:
                errors.append(f"Failed to remove {rel}: {exc}")
                continue

            if verdict.owned:
                changes.append(f"Removed retired {rel}")
            else:
                warnings.append(verdict.diagnostic)
                preserved.append(str(dest))

        if not changes and not errors and not preserved:
            changes.append(f"{_DEST_FILENAME} absent from all configured agent dirs")

        return MigrationResult(
            success=len(errors) == 0,
            changes_made=changes,
            errors=errors,
            warnings=warnings,
            preserved_paths=preserved,
        )
