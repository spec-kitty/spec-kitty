"""Migration: remove legacy profile-context command files.

Projects may have already applied the old 2.2.0 migration that deployed
``spec-kitty.profile-context.md``.  The command is no longer part of the
consumer registry, so this forward migration removes stale generated copies.
"""

from __future__ import annotations

from collections.abc import Iterator
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
class RetireProfileContextCommandMigration(BaseMigration):
    """Remove stale /spec-kitty.profile-context command templates."""

    migration_id = "3.2.0rc43_retire_profile_context_command"
    description = "Remove retired /spec-kitty.profile-context command files"
    target_version = "3.2.0rc43"

    def detect(self, project_path: Path) -> bool:
        """Return True if any configured agent dir still has the legacy file."""
        return any(_iter_existing_profile_context_files(project_path))

    def can_apply(self, project_path: Path) -> tuple[bool, str]:  # noqa: ARG002
        """Always safe to apply; missing dirs are silently skipped."""
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        """Remove profile-context.md from every configured and present agent dir."""
        changes: list[str] = []
        errors: list[str] = []
        warnings: list[str] = []
        preserved: list[str] = []

        for dest in _iter_existing_profile_context_files(project_path):
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


def _iter_existing_profile_context_files(project_path: Path) -> Iterator[Path]:
    for agent_root, subdir in get_agent_dirs_for_project(project_path):
        agent_dir = project_path / agent_root / subdir
        if not agent_dir.exists():
            continue
        dest = agent_dir / _DEST_FILENAME
        if dest.exists():
            yield dest
