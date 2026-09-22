"""Migration: remove the 'release' skill from consumer projects.

The 'release' skill was shipped in v2.0.0 through v2.1.1 but is only relevant
to spec-kitty development (cutting PyPI releases). It should never have been
distributed to consumer projects.

This migration removes .claude/skills/release/ if present.
"""

from __future__ import annotations

from pathlib import Path

from specify_cli.asset_preservation import ManifestProver, guard_destructive_removal

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult

_RELEASE_SKILL_PATH = ".claude/skills/release"
#: Archive root for an unprovable collision. It must sit OUTSIDE the doomed
#: ``.claude/skills/release`` tree so the verbatim copy survives its removal.
_BACKUP_PARENT = ".kittify"


@MigrationRegistry.register
class RemoveReleaseSkillMigration(BaseMigration):
    """Remove the 'release' skill that was incorrectly distributed."""

    migration_id = "2.1.2_remove_release_skill"
    description = "Remove 'release' skill (spec-kitty development only, not for consumers)"
    target_version = "2.1.2"

    def detect(self, project_path: Path) -> bool:
        """Return True if the release skill directory exists."""
        return (project_path / _RELEASE_SKILL_PATH).is_dir()

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        """Check if the release skill exists to remove."""
        if (project_path / _RELEASE_SKILL_PATH).is_dir():
            return True, ""
        return False, "No release skill found — nothing to remove"

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        """Remove the release skill directory."""
        skill_dir = project_path / _RELEASE_SKILL_PATH

        if not skill_dir.is_dir():
            return MigrationResult(
                success=True,
                changes_made=["No release skill found — nothing to do"],
            )

        if dry_run:
            return MigrationResult(
                success=True,
                changes_made=[f"Would remove {_RELEASE_SKILL_PATH}/"],
            )

        # Ownership gate (NFR-006): the directory name is not proof — only a
        # managed-/command-skills manifest entry whose recorded hash matches the
        # bytes on disk authorizes the delete. A user-authored ``release`` skill
        # is unprovable, so it is archived verbatim (the guard performs the
        # rmtree only on a proven-owned tree).
        verdict = guard_destructive_removal(
            skill_dir,
            project_path,
            prover=ManifestProver(),
            is_tree=True,
            backup_parent=project_path / _BACKUP_PARENT,
        )
        if verdict.owned:
            return MigrationResult(
                success=True,
                changes_made=[f"Removed {_RELEASE_SKILL_PATH}/"],
            )
        return MigrationResult(
            success=True,
            changes_made=[verdict.diagnostic],
            warnings=[verdict.diagnostic],
            preserved_paths=[str(verdict.preserved_path)] if verdict.preserved_path is not None else [],
        )
