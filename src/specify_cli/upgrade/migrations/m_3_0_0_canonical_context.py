"""Upgrade migration: one-shot migration to canonical context architecture.

Wires :func:`~specify_cli.migration.runner.run_migration` into the
existing upgrade framework so ``spec-kitty upgrade`` discovers and runs it
automatically when the project schema version is older than 3.

Migration ID ``3.0.0_canonical_context`` targets schema version 3.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult

logger = logging.getLogger(__name__)


@MigrationRegistry.register
class M300CanonicalContext(BaseMigration):
    """Migrate project to canonical context architecture (schema v3)."""

    migration_id = "3.0.0_canonical_context"
    description = "Migrate to canonical context architecture (identity, ownership, event log, thin shims)"
    target_version = "3.0.0"

    def detect(self, project_path: Path) -> bool:
        """Return True if the project schema version is below 3 or absent."""
        from specify_cli.migration.schema_version import get_project_schema_version

        version = get_project_schema_version(project_path)
        return version is None or version < 3

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        """Verify the project has a .kittify directory and metadata.yaml."""
        kittify = project_path / ".kittify"
        if not kittify.is_dir():
            return False, "No .kittify directory found — is this a spec-kitty project?"

        metadata = kittify / "metadata.yaml"
        if not metadata.exists():
            return False, "No .kittify/metadata.yaml found"

        try:
            from specify_cli.migration.runner import run_migration  # noqa: F401

            return True, ""
        except ImportError as exc:
            return False, f"Migration runner not available: {exc}"

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        """Run the one-shot canonical context migration."""
        from specify_cli.migration.runner import run_migration

        try:
            report = run_migration(project_path, dry_run=dry_run)
        except Exception as exc:
            logger.error("Canonical context migration raised an exception: %s", exc)
            return MigrationResult(
                success=False,
                errors=[f"Migration failed with exception: {exc}"],
            )

        # The runner never commits (the upgrade command owns that), so a failed report is
        # always a real failure: success must mirror it exactly (FR-006/FR-007).
        result = MigrationResult(success=report.success)
        result.errors = report.errors
        result.warnings = report.warnings

        if report.success:
            summary = (
                f"Migrated {report.features_migrated} feature(s), "
                f"{report.wps_backfilled} WPs backfilled, "
                f"{report.events_generated} events generated"
            )
            if dry_run:
                summary = f"[DRY RUN] {summary}"
            result.changes_made.append(summary)
            if report.files_moved:
                result.changes_made.append(f"Moved {len(report.files_moved)} derived file(s)")
        else:
            result.changes_made.append(
                f"Migration failed at step: {report.failed_step or 'unknown'}"
            )

        return result
