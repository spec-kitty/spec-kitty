"""Residue-aware successor of the 2.0.6 consistency sweep (#6669).

``2.0.6_consistency_sweep`` is a shipped, byte-frozen migration (DIRECTIVE_044).
It repairs every ``kitty-specs/`` child, including a residue folder that is not a
Mission, which it then gives a baseline ``meta.json`` and a refreshed
``status.json``. It is listed in ``SUPERSEDED_MIGRATIONS``; this successor
re-walks the project over the frozen helpers and leaves residue untouched.

Only module-level helper functions are imported from the shipped module, never
its migration class: ``auto_discover_migrations`` skips reloading a module that
holds a class whose ``migration_id`` is already registered, so importing the
class by name here would make this successor vanish after
``MigrationRegistry.clear()``.
"""

from __future__ import annotations

from pathlib import Path

from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.runtime.doctor import check_stale_legacy_assets

from ..registry import MigrationRegistry
from ._residue_successor import partition_kitty_specs, predecessor_settled, residue_warnings
from .base import BaseMigration, MigrationResult
from .m_2_0_6_consistency_sweep import (
    _cleanup_legacy_worktree_assets,
    _feature_requires_repair,
    _has_legacy_worktree_assets,
    _migrate_runtime_assets,
    _repair_feature,
)

PREDECESSOR_ID = "2.0.6_consistency_sweep"


@MigrationRegistry.register
class ResidueSafeConsistencySweepMigration(BaseMigration):
    """Repair version-stamped projects that still have structural drift, leaving residue folders alone."""

    migration_id = "2.0.6_residue_safe_consistency_sweep"
    description = "Residue-safe 2.0.6 consistency sweep: repair Mission metadata/state drift, never a kitty-specs/ residue folder"
    target_version = "2.0.6"

    def detect(self, project_path: Path) -> bool:
        """Return True when a non-residue folder, or a legacy asset, still needs 2.0.6 repair."""
        if predecessor_settled(project_path, PREDECESSOR_ID):
            return False
        if check_stale_legacy_assets(project_path).passed is False:
            return True
        if _has_legacy_worktree_assets(project_path):
            return True

        kitty_specs = project_path / KITTY_SPECS_DIR
        missions, _residue = partition_kitty_specs(kitty_specs, project_path)
        return any(_feature_requires_repair(mission_dir, project_path) for mission_dir in missions)

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        """Consistency repair only needs a spec project root."""
        if (project_path / ".kittify").exists() or (project_path / KITTY_SPECS_DIR).exists():
            return True, ""
        return False, "No .kittify/ or kitty-specs/ directory found"

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        """Run the 2.0.6 consistency sweep over the Mission folders; report each residue folder once."""
        changes: list[str] = []
        warnings: list[str] = []
        errors: list[str] = []

        # Probe first: a git timeout must fail the run before any write, as the 0.9.x successors do (#6669).
        kitty_specs = project_path / KITTY_SPECS_DIR
        missions, residue = partition_kitty_specs(kitty_specs, project_path)

        runtime_changes, runtime_warnings = _migrate_runtime_assets(project_path, dry_run)
        changes.extend(runtime_changes)
        warnings.extend(runtime_warnings)

        worktree_changes, worktree_errors = _cleanup_legacy_worktree_assets(project_path, dry_run)
        changes.extend(worktree_changes)
        errors.extend(worktree_errors)

        for mission_dir in missions:
            feature_changes, feature_warnings = _repair_feature(mission_dir, project_path, dry_run)
            changes.extend(feature_changes)
            warnings.extend(feature_warnings)

        if not changes and not warnings and not errors:
            changes.append("Project already consistent for 2.0.6")
        warnings.extend(residue_warnings(residue, project_path))

        return MigrationResult(
            success=not errors,
            changes_made=changes,
            warnings=warnings,
            errors=errors,
        )
