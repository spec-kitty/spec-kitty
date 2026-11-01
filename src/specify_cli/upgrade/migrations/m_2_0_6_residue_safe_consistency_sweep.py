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

import json
from pathlib import Path

from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.runtime.doctor import check_stale_legacy_assets
from specify_cli.status import SNAPSHOT_FILENAME, StoreError, materialize_snapshot, materialize_to_json
from specify_cli.upgrade.feature_meta import build_baseline_feature_meta, load_feature_meta

from ..registry import MigrationRegistry, settled_in_selection_view
from ..tracked_meta_notice import MissingTrackedMeta, classify_missing_tracked_meta
from ._residue_successor import partition_kitty_specs, residue_warnings
from .base import BaseMigration, MigrationResult
from .m_2_0_6_consistency_sweep import (
    _cleanup_legacy_worktree_assets,
    _feature_has_status_drift,
    _feature_requires_repair,
    _has_legacy_worktree_assets,
    _has_orphan_status_snapshot,
    _migrate_runtime_assets,
    _normalize_wp_frontmatter,
    _repair_feature,
    _repair_feature_meta,
    _rewrite_tasks_prompt_refs,
    _tasks_md_has_legacy_prompt_refs,
    _wp_frontmatter_needs_normalization,
)

PREDECESSOR_ID = "2.0.6_consistency_sweep"


def _is_derived_projection(mission_dir: Path) -> bool:
    """True when *mission_dir*'s event-less ``status.json`` is the projection the reducer itself writes, not an orphan.

    A later migration (``3.2.0a4_normalize_mission_lifecycle``) and every status read path
    materialize ``status.json`` for a Mission with no event log. The shipped sweep reads that
    shape as an orphan snapshot and archives it. This successor is re-selected on every upgrade
    while its predecessor is unsettled (#6688), so without this check the second upgrade would
    rename the file the first one's later migration wrote (#6843). Byte equality with the reducer's
    own output tells that projection apart from a stale snapshot, and reads nothing it cannot rebuild.
    """
    if not _has_orphan_status_snapshot(mission_dir):
        return False
    try:
        current = (mission_dir / SNAPSHOT_FILENAME).read_text(encoding="utf-8")
        return bool(current == materialize_to_json(materialize_snapshot(mission_dir)))
    except (OSError, ValueError, StoreError):
        return False


def _requires_repair(mission_dir: Path, project_path: Path) -> bool:
    """The shipped repair check, except that the reducer's own projection is not an orphan to archive."""
    if not _is_derived_projection(mission_dir):
        return bool(_feature_requires_repair(mission_dir, project_path))
    try:
        meta = load_feature_meta(mission_dir)
    except json.JSONDecodeError:
        return True
    return bool(
        meta != build_baseline_feature_meta(mission_dir, project_path, existing_meta=meta)
        or _tasks_md_has_legacy_prompt_refs(mission_dir)
        or _wp_frontmatter_needs_normalization(mission_dir)
        or _feature_has_status_drift(mission_dir)
    )


def _repair_mission(mission_dir: Path, project_path: Path, dry_run: bool) -> tuple[list[str], list[str]]:
    """Run the shipped per-folder repair; for the reducer's projection, its steps without the orphan archive.

    A Mission holding that projection has no event log (that is what made it look like an
    orphan), so the shipped steps that read the log (unreadable-log quarantine, status
    regeneration) have nothing to do and are left out with the archive.
    """
    if not _is_derived_projection(mission_dir):
        repaired_changes, repaired_warnings = _repair_feature(mission_dir, project_path, dry_run)
        return repaired_changes, repaired_warnings
    changes, warnings = _repair_feature_meta(mission_dir, project_path, dry_run)
    normalized, normalize_warnings = _normalize_wp_frontmatter(mission_dir, dry_run)
    warnings.extend(f"{mission_dir.name}: {warning}" for warning in normalize_warnings)
    if normalized:
        verb = "would normalize" if dry_run else "normalized"
        changes.append(f"{mission_dir.name}: {verb} {normalized} work package files")
    rewrites = _rewrite_tasks_prompt_refs(mission_dir, dry_run)
    if rewrites:
        verb = "would rewrite" if dry_run else "rewrote"
        changes.append(f"{mission_dir.name}: {verb} {rewrites} legacy prompt reference(s)")
    return changes, warnings


@MigrationRegistry.register
class ResidueSafeConsistencySweepMigration(BaseMigration):
    """Repair version-stamped projects that still have structural drift, leaving residue folders alone."""

    migration_id = "2.0.6_residue_safe_consistency_sweep"
    description = "Residue-safe 2.0.6 consistency sweep: repair Mission metadata/state drift, never a kitty-specs/ residue folder"
    target_version = "2.0.6"
    #: This successor replaces the shipped sweep: its own record settles it only once that
    #: predecessor's outcome proves the repair ran (#6688).
    predecessor_id = PREDECESSOR_ID

    def detect(self, project_path: Path) -> bool:
        """Return True when a non-residue folder, or a legacy asset, still needs 2.0.6 repair."""
        if settled_in_selection_view(project_path, PREDECESSOR_ID):
            return False
        if check_stale_legacy_assets(project_path).passed is False:
            return True
        if _has_legacy_worktree_assets(project_path):
            return True

        kitty_specs = project_path / KITTY_SPECS_DIR
        missions, _residue = partition_kitty_specs(kitty_specs, project_path)
        return any(_requires_repair(mission_dir, project_path) for mission_dir in missions)

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        """Consistency repair only needs a spec project root."""
        if (project_path / ".kittify").exists() or (project_path / KITTY_SPECS_DIR).exists():
            return True, ""
        return False, "No .kittify/ or kitty-specs/ directory found"

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        """Run the 2.0.6 consistency sweep over the Mission folders; report each residue folder once.

        A Mission whose tracked ``meta.json`` is missing from the working tree is rebuilt from
        the copy git holds, or refused with the restore command; either way the folder is
        never given a second identity (#6673).
        """
        changes: list[str] = []
        warnings: list[str] = []
        errors: list[str] = []

        # Probe first: a git timeout must fail the run before any write, as the 0.9.x successors do (#6669).
        kitty_specs = project_path / KITTY_SPECS_DIR
        missions, residue = partition_kitty_specs(kitty_specs, project_path)
        # One classification per Mission, before the first repair write, so a git failure surfaces
        # while nothing has been changed yet (#6673, mission spec C-005).
        missing_meta: dict[Path, MissingTrackedMeta] = {}
        for mission_dir in missions:
            classified = classify_missing_tracked_meta(mission_dir, project_path)
            if classified is not None:
                missing_meta[mission_dir] = classified
                warnings.append(classified.notice)

        runtime_changes, runtime_warnings = _migrate_runtime_assets(project_path, dry_run)
        changes.extend(runtime_changes)
        warnings.extend(runtime_warnings)

        worktree_changes, worktree_errors = _cleanup_legacy_worktree_assets(project_path, dry_run)
        changes.extend(worktree_changes)
        errors.extend(worktree_errors)

        for mission_dir in missions:
            refusal = missing_meta.get(mission_dir)
            if refusal is not None and refusal.refuse:
                # git knows this Mission's meta.json but cannot give it back: repair nothing here, so no
                # later step writes state (or an identity) for a Mission we could not identify (#6673).
                continue
            feature_changes, feature_warnings = _repair_mission(mission_dir, project_path, dry_run)
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
