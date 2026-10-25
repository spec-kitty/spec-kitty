"""Residue-aware successor of the 0.9.0 frontmatter-only lanes migration (#6669).

``0.9.0_frontmatter_only_lanes`` is a shipped, byte-frozen migration
(DIRECTIVE_044). It flattens the ``tasks/<lane>/`` folders of every
``kitty-specs/`` child, including a residue folder that is not a Mission. It is
listed in ``SUPERSEDED_MIGRATIONS``; this successor subclasses it, so every
repair is inherited, and only decides which folders count as legacy.

The shipped module is imported as an alias, never the class by name:
``auto_discover_migrations`` skips reloading a module whose ``dir()`` holds a
class with an already-registered ``migration_id``, so a name import of the
shipped class would make this successor vanish after
``MigrationRegistry.clear()``.
"""

from __future__ import annotations

from pathlib import Path

from specify_cli.context.mission_resolver import is_kitty_specs_residue

from ..registry import MigrationRegistry
from . import m_0_9_0_frontmatter_only_lanes as _shipped
from ._residue_successor import ResidueProbes, partition_checkout_specs, predecessor_settled, residue_warnings
from .base import MigrationResult

PREDECESSOR_ID = "0.9.0_frontmatter_only_lanes"


@MigrationRegistry.register
class ResidueSafeFrontmatterOnlyLanesMigration(_shipped.FrontmatterOnlyLanesMigration):
    """Flatten directory-based task lanes in every Mission, leaving ``kitty-specs/`` residue folders alone."""

    migration_id = "0.9.0_residue_safe_frontmatter_only_lanes"
    description = "Residue-safe flatten of task lanes to frontmatter-only, never in a kitty-specs/ residue folder"

    _probes: ResidueProbes | None = None

    def _is_residue(self, feature_path: Path) -> bool:
        """Residue decision through this run's probe cache (one git probe per checkout); uncached outside detect/apply."""
        if self._probes is None:
            return is_kitty_specs_residue(feature_path)
        return self._probes.is_residue(feature_path)

    def _is_legacy_format(self, feature_path: Path) -> bool:
        """Legacy lane folders only count in a Mission; the shipped check runs first, so a clean folder costs no git call."""
        return bool(super()._is_legacy_format(feature_path)) and not self._is_residue(feature_path)

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
