"""Stamp ``merged_at`` on Missions that landed before #4090 (#7433).

The status read door and ``spec-kitty next`` take "has this Mission landed" from one signal,
the reopen-aware ``merged_at`` marker (``mission_runtime.mission_has_landed``, ADR
``2026-11-06-2``, #7335). A Mission that landed before consolidation wrote that marker (#4090)
carries ``mission_number`` but no ``merged_at``, so it reads as not landed; a coordination
topology one then refuses with ``COORDINATION_BRANCH_DELETED`` because consolidation removed its
coordination branch. This migration stamps the marker from git evidence; the selection and date
rules live in :mod:`specify_cli.migration.backfill_merged_at`.

``meta.json`` is tracked, so the effect travels with the commit: the record goes to the tracked
partition (``clone_local_effect`` stays ``False``). The date comes from git, so the migration
declares ``requires_git_repository``. ``apply()`` is idempotent: a stamped Mission is no longer
selected, and a reopened Mission or one without git evidence is reported, never written.
"""

from __future__ import annotations

from pathlib import Path

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult

MIGRATION_ID = "4.0.0rc8_backfill_merged_at"
TARGET_VERSION = "4.0.0rc8"


@MigrationRegistry.register
class BackfillMergedAtMigration(BaseMigration):
    """Stamp the ``merged_at`` landing marker on pre-#4090 landed Missions."""

    migration_id = MIGRATION_ID
    description = "Stamp merged_at on Missions that landed before #4090 (mission_number set, no merged_at, never reopened) so they read as landed (#7433)."
    target_version = TARGET_VERSION
    runs_on_worktrees = False
    requires_git_repository = True

    def detect(self, project_path: Path) -> bool:
        from specify_cli.migration.backfill_merged_at import has_merged_at_to_backfill

        return has_merged_at_to_backfill(project_path)

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        if self.detect(project_path):
            return True, ""
        return False, "no landed Mission without merged_at has git evidence of its landing date"

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        from specify_cli.migration.backfill_merged_at import backfill_merged_at

        results = backfill_merged_at(project_path, dry_run=dry_run)
        verb = "would stamp" if dry_run else "stamped"
        changes = [f"{result.slug}: {verb} merged_at {result.merged_at} (from {result.source})" for result in results if result.action == "stamped"]
        warnings = [f"{result.slug}: merged_at not stamped: {result.reason}" for result in results if result.action in ("reopened", "unresolved", "error")]
        return MigrationResult(success=True, changes_made=changes, warnings=warnings)
