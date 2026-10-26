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

from ..registry import MigrationRegistry
from . import m_0_9_0_frontmatter_only_lanes as _shipped
from ._residue_successor import ResidueSafeLaneSuccessorMixin

PREDECESSOR_ID = "0.9.0_frontmatter_only_lanes"


@MigrationRegistry.register
class ResidueSafeFrontmatterOnlyLanesMigration(ResidueSafeLaneSuccessorMixin, _shipped.FrontmatterOnlyLanesMigration):
    """Flatten directory-based task lanes in every Mission, leaving ``kitty-specs/`` residue folders alone."""

    migration_id = "0.9.0_residue_safe_frontmatter_only_lanes"
    description = "Residue-safe flatten of task lanes to frontmatter-only, never in a kitty-specs/ residue folder"

    predecessor_id = PREDECESSOR_ID

    def _is_legacy_format(self, feature_path: Path) -> bool:
        """Legacy lane folders only count in a Mission; the shipped check runs first, so a clean folder costs no git call."""
        return bool(super()._is_legacy_format(feature_path)) and not self._is_residue(feature_path)
