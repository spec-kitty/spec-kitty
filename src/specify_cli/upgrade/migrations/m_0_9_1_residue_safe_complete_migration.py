"""Residue-aware successor of the 0.9.1 complete lane migration (#6669).

``0.9.1_complete_migration`` is a shipped, byte-frozen migration
(DIRECTIVE_044). It moves the leftover lane files, cleans worktrees and
normalises the frontmatter of every ``kitty-specs/`` child, including a residue
folder that is not a Mission. It is listed in ``SUPERSEDED_MIGRATIONS``; this
successor subclasses it, so every repair is inherited, and only decides which
folders count (the lane predicate and the frontmatter file collection).

The shipped module is imported as an alias, never the class by name (see
``m_0_9_0_residue_safe_frontmatter_only_lanes`` for the rediscovery trap).
"""

from __future__ import annotations

import io
from pathlib import Path

from specify_cli.context.mission_resolver import is_kitty_specs_residue
from specify_cli.frontmatter import FrontmatterError, FrontmatterManager, normalize_file

from ..registry import MigrationRegistry
from . import m_0_9_1_complete_lane_migration as _shipped
from ._residue_successor import ResidueProbes, partition_checkout_specs, predecessor_settled, residue_warnings
from .base import MigrationResult

PREDECESSOR_ID = "0.9.1_complete_migration"


def _would_change(md_file: Path) -> bool:
    """Dry-run comparison: would normalising *md_file* rewrite it?"""
    manager = FrontmatterManager()
    original = md_file.read_text(encoding="utf-8-sig")
    frontmatter, body = manager.read(md_file)
    buffer = io.StringIO()
    buffer.write("---\n")
    manager.yaml.dump(manager._normalize_frontmatter(frontmatter), buffer)
    buffer.write("---\n")
    buffer.write(body)
    return original != buffer.getvalue()


@MigrationRegistry.register
class ResidueSafeCompleteLaneMigration(_shipped.CompleteLaneMigration):
    """Complete the lane migration in every Mission, leaving ``kitty-specs/`` residue folders alone."""

    migration_id = "0.9.1_residue_safe_complete_migration"
    description = "Residue-safe complete lane migration + clean up worktrees + normalize frontmatter, never in a kitty-specs/ residue folder"

    _probes: ResidueProbes | None = None

    def _is_residue(self, feature_path: Path) -> bool:
        """Residue decision through this run's probe cache (one git probe per checkout); uncached outside detect/apply."""
        if self._probes is None:
            return is_kitty_specs_residue(feature_path)
        return self._probes.is_residue(feature_path)

    def _has_remaining_lane_dirs(self, feature_path: Path) -> bool:
        """Lane folders only count in a Mission; the shipped check runs first, so a clean folder costs no git call."""
        return bool(super()._has_remaining_lane_dirs(feature_path)) and not self._is_residue(feature_path)

    def detect(self, project_path: Path) -> bool:
        if predecessor_settled(project_path, PREDECESSOR_ID):
            return False
        self._probes = ResidueProbes()
        try:
            return bool(super().detect(project_path))
        finally:
            self._probes = None

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        # Probe every checkout before the shipped walk moves a file: a git timeout then aborts with nothing moved.
        self._probes = ResidueProbes()
        try:
            _missions, residue = partition_checkout_specs(project_path, self._probes)
            result = super().apply(project_path, dry_run)
        finally:
            self._probes = None
        result.warnings.extend(residue_warnings(residue, project_path))
        return result

    def _normalize_all_frontmatter(self, project_path: Path, dry_run: bool) -> tuple[list[str], list[str], list[str]]:
        """Normalize the frontmatter of the task files of every Mission; a residue folder's files are never collected."""
        changes: list[str] = []
        warnings: list[str] = []
        errors: list[str] = []

        missions, _residue = partition_checkout_specs(project_path, self._probes)
        md_files = [md_file for mission_dir in missions for md_file in mission_dir.rglob("*.md")]
        if not md_files:
            changes.append("No markdown files found")
            return changes, warnings, errors

        normalized_count = 0
        skipped_count = 0
        for md_file in sorted(md_files):
            # Only normalize files in tasks/ directories (README.md, spec.md, ... are skipped).
            if "tasks" not in md_file.parts:
                continue
            rel = md_file.relative_to(project_path)
            try:
                changed = _would_change(md_file) if dry_run else normalize_file(md_file)
            except FrontmatterError as e:
                warnings.append(f"Skip (no frontmatter): {rel}" if dry_run else f"Skip (error): {rel}: {e}")
                skipped_count += 1
                continue
            except Exception as e:
                errors.append(f"Failed to normalize {rel}: {e}")
                continue
            if changed:
                changes.append(f"{'Would normalize' if dry_run else 'Normalized'}: {rel}")
                normalized_count += 1
            else:
                skipped_count += 1

        if dry_run:
            changes.append(f"Would normalize {normalized_count} files, skip {skipped_count}")
        else:
            changes.append(f"Normalized {normalized_count} files, skipped {skipped_count}")
        return changes, warnings, errors
