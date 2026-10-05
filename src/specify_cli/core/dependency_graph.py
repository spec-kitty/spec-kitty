"""Dependency graph utilities for work package relationships.

This module provides functions for parsing, validating, and analyzing
dependency relationships between work packages in Spec Kitty features.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import re
from pathlib import Path
from typing import Any

from specify_cli.status import Lane
from specify_cli.status import WorkPackageStartRejected
from specify_cli.status import resolve_lane_alias
from specify_cli.status import read_wp_frontmatter
from specify_cli.status_lanes import has_operator_provenance, is_acceptable_ending


@dataclass(frozen=True)
class DependencyReadiness:
    """Dependency completion status for one work package."""

    wp_id: str
    dependencies: tuple[str, ...]
    unsatisfied: tuple[str, ...]

    @property
    def satisfied(self) -> bool:
        return not self.unsatisfied


def dependency_readiness_for_wp(
    wp_id: str,
    dependencies: Iterable[str],
    wp_lanes: Mapping[str, Lane | str],
    provenance: Mapping[str, Mapping[str, Any] | None] | None = None,
) -> DependencyReadiness:
    """Return whether every dependency has reached an acceptable ending.

    A dependency is satisfied once it has reached a mission ending the shared
    acceptable-ending authority (:func:`is_acceptable_ending`, WP02) accepts:

      * ``approved`` — review passed, merge pending. ``done`` is emitted only by
        the whole-mission merge, so gating strictly on ``done`` would deadlock
        every same-mission dependency chain; accepting ``approved`` is what makes
        intra-mission dependency ordering possible (this matches the merge
        dependency gate in ``policy/merge_gates.py`` and the retrospective
        generator).
      * ``done`` — merged/integrated into the mission target branch.
      * ``canceled`` **with operator-authored provenance** — a documented
        cancellation is a valid removal of the dependency (FR-009). A ``canceled``
        dependency *without* provenance (a synthetic, undocumented cancellation)
        stays non-satisfying, consistent with FR-003.

    Every other lane — ``for_review``, ``in_review``, ``blocked``, missing
    status, etc. — is not ready.

    ``provenance`` maps each dependency's WP id to its reduced status snapshot
    (the ``StatusSnapshot.work_packages`` state dict), from which operator
    provenance is read via :func:`has_operator_provenance`. It is **optional**:
    when omitted (the default), no dependency carries provenance, so a
    ``canceled`` dependency is treated as non-satisfying — preserving the legacy
    lane-only behaviour for read-only callers that do not thread provenance.
    """
    deps = tuple(dependencies)
    unsatisfied = tuple(dep for dep in deps if not _dependency_resolved(dep, wp_lanes, provenance))
    return DependencyReadiness(
        wp_id=wp_id,
        dependencies=deps,
        unsatisfied=unsatisfied,
    )


def _dependency_resolved(
    dep: str,
    wp_lanes: Mapping[str, Lane | str],
    provenance: Mapping[str, Mapping[str, Any] | None] | None,
) -> bool:
    """Return whether one dependency has reached an acceptable ending.

    Consults the shared acceptable-ending authority (WP02) rather than a local
    lane set, resolving operator provenance from the optional ``provenance`` map.
    """
    lane = _dependency_lane(wp_lanes.get(dep, Lane.PLANNED))
    if lane is None:
        return False
    snapshot = provenance.get(dep) if provenance is not None else None
    resolved: bool = is_acceptable_ending(str(lane), has_provenance=has_operator_provenance(snapshot))
    return resolved


def _dependency_lane(value: Lane | str) -> Lane | None:
    """Normalize canonical/legacy dependency lanes without laundering invalid data."""
    try:
        return Lane(resolve_lane_alias(str(value)))
    except ValueError:
        return None


def parse_wp_dependencies(wp_file: Path) -> list[str]:
    """Parse dependencies from WP frontmatter.

    Uses :func:`read_wp_frontmatter` for typed, validated access.

    Args:
        wp_file: Path to work package markdown file

    Returns:
        List of WP IDs this WP depends on (e.g., ["WP01", "WP02"])

    Raises:
        FrontmatterError: If the file cannot be read or parsed.
        ValidationError: If the frontmatter fails model validation.
        OSError: If the file does not exist or is unreadable.

    Examples:
        >>> wp_file = Path("tasks/WP02.md")
        >>> deps = parse_wp_dependencies(wp_file)
        >>> print(deps)  # ["WP01"]
    """
    meta, _ = read_wp_frontmatter(wp_file)
    dependencies: list[str] = meta.dependencies
    return dependencies


def build_dependency_graph(feature_dir: Path) -> dict[str, list[str]]:
    """Build dependency graph from all WPs in feature.

    Scans tasks/ directory for WP files and parses their dependencies.
    Validates that filename WP ID matches frontmatter work_package_id.

    Args:
        feature_dir: Path to feature directory (contains tasks/ subdirectory)
                    OR path to tasks directory directly

    Returns:
        Adjacency list mapping WP ID to list of dependencies
        Example: {"WP01": [], "WP02": ["WP01"], "WP03": ["WP01"]}

    Examples:
        >>> feature_dir = Path("kitty-specs/010-feature")
        >>> graph = build_dependency_graph(feature_dir)
        >>> print(graph)  # {"WP01": [], "WP02": ["WP01"]}
    """
    graph: dict[str, list[str]] = {}

    # Support both feature_dir and tasks_dir as input
    tasks_dir = feature_dir if feature_dir.name == "tasks" else feature_dir / "tasks"

    if not tasks_dir.exists():
        return graph

    # Find all WP markdown files
    for wp_file in sorted(tasks_dir.glob("WP*.md")):
        # Extract WP ID from filename (e.g., WP01-title.md → WP01)
        filename_wp_id = extract_wp_id_from_filename(wp_file.name)
        if not filename_wp_id:
            continue

        # Parse frontmatter to get canonical work_package_id
        meta, _ = read_wp_frontmatter(wp_file)
        frontmatter_wp_id = meta.work_package_id

        # Verify filename matches frontmatter (catch misnamed files)
        if frontmatter_wp_id and frontmatter_wp_id != filename_wp_id:
            raise ValueError(f"WP ID mismatch: filename {filename_wp_id} vs frontmatter {frontmatter_wp_id} in {wp_file}")

        wp_id = frontmatter_wp_id or filename_wp_id

        # Parse dependencies from frontmatter
        dependencies = parse_wp_dependencies(wp_file)
        graph[wp_id] = dependencies

    return graph


def extract_wp_id_from_filename(filename: str) -> str | None:
    """Extract WP ID from filename.

    Args:
        filename: WP file name (e.g., "WP01-title.md" or "WP02.md")

    Returns:
        WP ID (e.g., "WP01") or None if invalid format

    Examples:
        >>> extract_wp_id_from_filename("WP01-setup.md")
        'WP01'
        >>> extract_wp_id_from_filename("invalid.md")
        None
    """
    match = re.match(r"^(WP\d{2})", filename)
    return match.group(1) if match else None


def detect_cycles(graph: dict[str, list[str]]) -> list[list[str]] | None:
    """Detect circular dependencies using DFS with coloring.

    Uses depth-first search with three-color marking (white/gray/black)
    to detect back edges, which indicate cycles.

    Args:
        graph: Adjacency list mapping WP ID to dependencies

    Returns:
        List of cycles (each cycle is a list of WP IDs) or None if acyclic

    Complexity:
        O(V + E) where V = vertices (WPs), E = edges (dependencies)

    Examples:
        >>> graph = {"WP01": ["WP02"], "WP02": ["WP01"]}
        >>> cycles = detect_cycles(graph)
        >>> print(cycles)  # [["WP01", "WP02", "WP01"]]

        >>> graph = {"WP01": [], "WP02": ["WP01"]}
        >>> cycles = detect_cycles(graph)
        >>> print(cycles)  # None (acyclic)
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color = dict.fromkeys(graph, WHITE)
    cycles = []

    def dfs(node: str, path: list[str]) -> None:
        """DFS traversal with cycle detection."""
        color[node] = GRAY
        path.append(node)

        for neighbor in graph.get(node, []):
            neighbor_color = color.get(neighbor, WHITE)

            if neighbor_color == GRAY:
                # Back edge found - cycle detected
                if neighbor in path:
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:] + [neighbor])
            elif neighbor_color == WHITE:
                dfs(neighbor, path)

        path.pop()
        color[node] = BLACK

    # Run DFS from each unvisited node
    for wp in graph:
        if color[wp] == WHITE:
            dfs(wp, [])

    return cycles if cycles else None


def validate_dependencies(wp_id: str, declared_deps: list[str], graph: dict[str, list[str]]) -> tuple[bool, list[str]]:
    """Validate that WP's dependencies are valid.

    Checks:
    - Dependencies exist in graph
    - No self-dependencies
    - No circular dependencies
    - Valid WP ID format

    Args:
        wp_id: Work package ID being validated
        declared_deps: List of dependency WP IDs
        graph: Complete dependency graph

    Returns:
        Tuple of (is_valid, error_messages)
        - is_valid: True if all validations pass
        - error_messages: List of error descriptions (empty if valid)

    Examples:
        >>> graph = {"WP01": [], "WP02": ["WP01"]}
        >>> is_valid, errors = validate_dependencies("WP02", ["WP01"], graph)
        >>> print(is_valid)  # True

        >>> is_valid, errors = validate_dependencies("WP02", ["WP99"], graph)
        >>> print(is_valid)  # False
        >>> print(errors)  # ["Dependency WP99 not found in graph"]
    """
    errors = []
    wp_pattern = re.compile(r"^WP\d{2}$")

    # Validate each dependency
    for dep in declared_deps:
        # Check format
        if not wp_pattern.match(dep):
            errors.append(f"Invalid WP ID format: {dep} (must be WP## like WP01)")
            continue

        # Check self-dependency
        if dep == wp_id:
            errors.append(f"Cannot depend on self: {wp_id} → {wp_id}")
            continue

        # Check dependency exists in graph
        if dep not in graph:
            errors.append(f"Dependency {dep} not found in graph")

    # Check for circular dependencies
    # Build temporary graph with this WP's dependencies to check for cycles
    test_graph = graph.copy()
    test_graph[wp_id] = declared_deps

    cycles = detect_cycles(test_graph)
    if cycles:
        for cycle in cycles:
            if wp_id in cycle:
                errors.append(f"Circular dependency detected: {' → '.join(cycle)}")
                break

    is_valid = len(errors) == 0
    return is_valid, errors


def topological_sort(graph: dict[str, list[str]]) -> list[str]:
    """Return nodes in topological order (dependencies before dependents).

    Uses Kahn's algorithm:
    1. Find all nodes with no incoming edges (no dependencies)
    2. Remove them from graph, add to result
    3. Repeat until graph is empty

    Args:
        graph: Adjacency list where graph[node] = [dependencies]
               Note: This is REVERSE of typical adjacency (edges point to deps)

    Returns:
        List of node IDs in topological order

    Raises:
        ValueError: If graph contains a cycle (use detect_cycles() first)

    Example:
        >>> graph = {"WP01": [], "WP02": ["WP01"], "WP03": ["WP01", "WP02"]}
        >>> topological_sort(graph)
        ['WP01', 'WP02', 'WP03']
    """
    # Build in-degree map and reverse adjacency
    in_degree: dict[str, int] = dict.fromkeys(graph, 0)
    reverse_adj: dict[str, list[str]] = {node: [] for node in graph}

    for node, deps in graph.items():
        in_degree[node] = len(deps)
        for dep in deps:
            if dep in reverse_adj:
                reverse_adj[dep].append(node)

    # Start with nodes that have no dependencies
    queue = [node for node, degree in in_degree.items() if degree == 0]
    queue.sort()  # Stable ordering for determinism

    result = []
    while queue:
        node = queue.pop(0)
        result.append(node)

        # "Remove" this node by decrementing in-degree of dependents
        for dependent in sorted(reverse_adj.get(node, [])):
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)
                queue.sort()  # Maintain sorted order

    if len(result) != len(graph):
        raise ValueError("Graph contains a cycle - cannot topologically sort")

    return result


def get_dependents(wp_id: str, graph: dict[str, list[str]]) -> list[str]:
    """Get list of WPs that depend on this WP (inverse graph query).

    Builds inverse graph and returns direct dependents only (not transitive).

    Args:
        wp_id: Work package ID to query
        graph: Dependency graph (adjacency list)

    Returns:
        List of WP IDs that directly depend on wp_id
        Returns empty list if no dependents or WP not in graph

    Examples:
        >>> graph = {"WP01": [], "WP02": ["WP01"], "WP03": ["WP01"]}
        >>> deps = get_dependents("WP01", graph)
        >>> print(sorted(deps))  # ["WP02", "WP03"]

        >>> deps = get_dependents("WP02", graph)
        >>> print(deps)  # []
    """
    # Build inverse graph: wp -> list of wps that depend on it
    inverse_graph: dict[str, list[str]] = {wp: [] for wp in graph}

    for wp, dependencies in graph.items():
        for dependency in dependencies:
            if dependency not in inverse_graph:
                inverse_graph[dependency] = []
            inverse_graph[dependency].append(wp)

    return inverse_graph.get(wp_id, [])


def ensure_wp_claim_preconditions(
    wp_id: str,
    declared_deps: Iterable[str] | Any,
    work_packages: Mapping[str, Mapping[str, Any]],
) -> None:
    """Raise if *wp_id* is unseeded (T012 / Contract 3) or a declared
    dependency is not yet ``approved``/``done``.

    Pure decision over the reduced status snapshot's ``work_packages`` mapping:
    the caller reads and reduces the event log (``read_events`` + ``reduce``)
    and passes ``snapshot.work_packages`` here, so this seam does no event I/O.

    Raises:
        WorkPackageStartRejected: *wp_id* is absent from, or still ``genesis`` in,
            the snapshot (it has not been through ``finalize-tasks``).
        ValueError: a declared dependency has not reached an acceptable ending
            (``dependencies_not_satisfied: ...``).
    """
    wp_lanes = {_wp_id: _state.get("lane", Lane.GENESIS) for _wp_id, _state in work_packages.items()}
    # T012 / Contract 3: reject unseeded WPs BEFORE any workspace
    # allocation. A genesis WP has not been through finalize-tasks; the
    # user must run it first to seed the genesis→planned bootstrap event.
    current_wp_lane = wp_lanes.get(wp_id, Lane.GENESIS)
    if current_wp_lane == Lane.GENESIS:
        # FR-009: same rejection (and exception type) as the lifecycle layer,
        # so programmatic callers catching WorkPackageStartRejected see this
        # path too (review M5).
        raise WorkPackageStartRejected(f"WP {wp_id} is not finalized; run `spec-kitty agent mission finalize-tasks`")
    # Thread per-dependency provenance so a canceled-with-operator-provenance
    # dependency counts as resolved (FR-009). `spec-kitty implement WP##` is the
    # primary claim command (CLAUDE.md: "the only supported way to prepare a
    # workspace"); collapsing to a lane-only map here would leave the #2945
    # strand trap open on the main claim path (review REJECT), mirroring the
    # workflow_executor gate fix.
    # Pre-flight UX only (FR-014, fsm-write-path-integrity WP04). The authoritative
    # dependency gate is `GuardContext.dependency_ready`, resolved in-lock by the emit shells.
    dependency_readiness = dependency_readiness_for_wp(wp_id, declared_deps, wp_lanes, provenance=work_packages)
    if not dependency_readiness.satisfied:
        blocked = ", ".join(dependency_readiness.unsatisfied)
        raise ValueError(f"dependencies_not_satisfied: {wp_id} depends on {blocked}; all dependencies must be approved or done before implementation can start")


__all__ = [
    "build_dependency_graph",
    "dependency_readiness_for_wp",
    "detect_cycles",
    "ensure_wp_claim_preconditions",
    "get_dependents",
    "parse_wp_dependencies",
    "topological_sort",
    "validate_dependencies",
]
