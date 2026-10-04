"""Merge ordering based on WP dependencies.

Implements FR-008 through FR-011: determining merge order via topological
sort of the dependency graph.

The mission-number bake cluster that mission #2057 had relocated here lives in
:mod:`specify_cli.consolidation.mission_number.bake` since #2600. One-way
import: this module never imports the command shim.
"""

from __future__ import annotations

import logging
from pathlib import Path

from specify_cli.core.dependency_graph import (
    build_dependency_graph,
    detect_cycles,
    topological_sort,
)

__all__ = [
    "get_merge_order",
    "MergeOrderError",
    "has_dependency_info",
]

logger = logging.getLogger(__name__)


class MergeOrderError(Exception):
    """Error determining merge order."""

    pass


def has_dependency_info(graph: dict[str, list[str]]) -> bool:
    """Check if any WP has declared dependencies.

    Args:
        graph: Dependency graph mapping WP ID to list of dependencies

    Returns:
        True if at least one WP has non-empty dependencies
    """
    return any(deps for deps in graph.values())


def get_merge_order(
    wp_workspaces: list[tuple[Path, str, str]],
    feature_dir: Path,
) -> list[tuple[Path, str, str]]:
    """Return WPs in dependency order (topological sort).

    Determines the optimal merge order based on WP dependencies declared
    in frontmatter. WPs with dependencies will be merged after their
    dependencies.

    Args:
        wp_workspaces: List of (worktree_path, wp_id, branch_name) tuples
        feature_dir: Path to feature directory containing tasks/

    Returns:
        Same tuples reordered by dependency (dependencies first)

    Raises:
        MergeOrderError: If circular dependency detected
    """
    if not wp_workspaces:
        return []

    # Build WP ID → workspace mapping
    wp_map = {wp_id: (path, wp_id, branch) for path, wp_id, branch in wp_workspaces}

    # Build dependency graph from task frontmatter
    graph = build_dependency_graph(feature_dir)

    # Check for missing WPs in graph (may have no frontmatter)
    for wp_id in wp_map:
        if wp_id not in graph:
            graph[wp_id] = []  # No dependencies

    # Check if we have any dependency info
    if not has_dependency_info(graph):
        # No dependency info - fall back to numerical order with warning
        logger.warning("No dependency information found in WP frontmatter. Falling back to numerical order (WP01, WP02, ...).")
        return sorted(wp_workspaces, key=lambda x: x[1])  # Sort by wp_id

    # Detect cycles - show full cycle path in error
    cycles = detect_cycles(graph)
    if cycles:
        # Format the cycle path clearly: WP01 → WP02 → WP03 → WP01
        cycle = cycles[0]
        cycle_str = " → ".join(cycle)
        raise MergeOrderError(f"Circular dependency detected: {cycle_str}\nFix the dependencies in the WP frontmatter to remove this cycle.")

    # Topological sort
    try:
        ordered_ids = topological_sort(graph)
    except ValueError as e:
        raise MergeOrderError(str(e)) from e

    # Filter to only WPs we have workspaces for, maintaining order
    result = []
    for wp_id in ordered_ids:
        if wp_id in wp_map:
            result.append(wp_map[wp_id])

    return result
