"""Cycle-aware messaging for the "canonical status not initialized" condition.

Upstream #1589 (facet 1): when ``finalize-tasks`` aborts on a circular WP
dependency it never bootstraps canonical status (the event-log file is never
created), so ``move-task``/``next``/lane reads raise a generic "run
finalize-tasks to bootstrap the event log" error. That hint is misleading —
re-running ``finalize-tasks`` keeps aborting on the same cycle, so the operator
loops. These helpers detect the unresolved dependency cycle from WP frontmatter
and surface it as the actionable root cause.

The module lives in the ``status`` layer (it may import ``core`` +
``status.wp_metadata``); the raise sites (``status.lane_reader`` and the agent
CLI) call into it.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from specify_cli.frontmatter import FrontmatterError
from specify_cli.status.wp_metadata import read_wp_frontmatter

__all__ = [
    "find_wp_dependency_cycles",
    "cycle_root_cause",
    "uninitialized_status_error",
    "feature_event_log_missing_error",
]


def _build_wp_dependency_graph(feature_dir: Path) -> dict[str, list[str]]:
    """Read WP frontmatter under ``feature_dir/tasks`` into a dependency graph.

    Malformed WP files are skipped (they cannot contribute a usable edge);
    cycle detection operates on whatever well-formed WPs are present.
    """
    tasks_dir = feature_dir / "tasks"
    graph: dict[str, list[str]] = {}
    if not tasks_dir.is_dir():
        return graph

    for wp_file in sorted(tasks_dir.glob("WP*.md")):
        try:
            meta, _body = read_wp_frontmatter(wp_file)
        except (FrontmatterError, ValidationError, OSError):
            continue
        wp_id = meta.work_package_id
        if not wp_id:
            continue
        graph[wp_id] = list(meta.dependencies or [])
    return graph


def find_wp_dependency_cycles(feature_dir: Path) -> list[list[str]] | None:
    """Return dependency cycles among the feature's WPs, or ``None`` if acyclic.

    Builds the graph from WP frontmatter ``dependencies`` and delegates to
    :func:`specify_cli.core.dependency_graph.detect_cycles`.

    The ``detect_cycles`` import is deferred into the function body to break a
    module-level import cycle: ``core.dependency_graph`` imports ``status`` (for
    ``Lane``), ``status.__init__`` imports this module, and a module-level
    ``detect_cycles`` import here would close the loop during status init.
    """
    # Deferred to break the status <-> core.dependency_graph import cycle.
    from specify_cli.core.dependency_graph import detect_cycles

    graph = _build_wp_dependency_graph(feature_dir)
    if not graph:
        return None
    return detect_cycles(graph)


def _format_cycles(cycles: list[list[str]]) -> str:
    return "; ".join(" -> ".join(cycle) for cycle in cycles)


def cycle_root_cause(feature_dir: Path) -> str | None:
    """Return a sentence naming an unresolved dependency cycle, or ``None``.

    Suitable to append to a "canonical status missing" error so the operator
    sees the actual blocker rather than a finalize-tasks hint that loops.
    """
    cycles = find_wp_dependency_cycles(feature_dir)
    if not cycles:
        return None
    return (
        f"`finalize-tasks` cannot initialize canonical status while a circular "
        f"WP dependency exists: {_format_cycles(cycles)}. Resolve the dependency "
        f"cycle in tasks.md / WP frontmatter, then re-run finalize-tasks."
    )


def feature_event_log_missing_error(feature_dir: Path) -> str:
    """Feature-level error for an absent canonical event log (lane_reader).

    Names an unresolved dependency cycle as the root cause when present; falls
    back to the standard bootstrap guidance otherwise.
    """
    slug = feature_dir.name
    root_cause = cycle_root_cause(feature_dir)
    if root_cause is not None:
        return f"Canonical status not found for mission '{slug}': {root_cause}"
    return (
        f"Canonical status not found for mission '{slug}'. "
        f"Run 'spec-kitty agent mission finalize-tasks --mission {slug}' "
        f"to bootstrap the event log."
    )


def uninitialized_status_error(
    mission_slug: str,
    wp_id: str,
    feature_dir: Path,
) -> str:
    """WP-level error for a WP that has no canonical status (event log present).

    When an unresolved dependency cycle is present, name it as the root cause;
    otherwise fall back to the standard "run finalize-tasks" guidance.
    """
    root_cause = cycle_root_cause(feature_dir)
    if root_cause is not None:
        return (
            f"WP {wp_id} has no canonical status in feature {mission_slug}: "
            f"{root_cause}"
        )
    return (
        f"WP {wp_id} has no canonical status in feature {mission_slug}. "
        f"Run `spec-kitty agent mission finalize-tasks --mission {mission_slug}` to initialize."
    )
