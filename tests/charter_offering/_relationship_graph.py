"""Test helper for WP07 relationship-migration fixtures.

Provides an empty built-in :class:`DRGGraph` so fixture org-fragments can be
merged in isolation (the fragment edges are the subject under test).
"""

from __future__ import annotations

from charter.offering.drg.models import DRGGraph


def empty_built_in() -> DRGGraph:
    """Return a minimal, valid empty built-in graph for fixture merges."""
    return DRGGraph(
        schema_version="1.0",
        generated_at="2026-06-01T00:00:00Z",
        generated_by="wp07-relationship-fixtures",
        nodes=[],
        edges=[],
    )
