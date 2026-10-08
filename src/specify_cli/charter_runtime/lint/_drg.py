"""Internal DRG loading helper for charter_lint.

Wraps the doctrine DRG package behind a thin, exception-safe façade.
Callers receive a duck-typed DRG object plus a :class:`GraphState` tag that
explains *which* graph was loaded (project / built-in / none). The tag is
the canonical input to the lint engine's tri-state freshness model
(see ADR ``2026-05-24-1-charter-freshness-ux-contract.md``).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from kernel.charter_pack_paths import resolve_project_pack_read_root

from .findings import GraphState

logger = logging.getLogger(__name__)


def _load_graph_file(path: Path) -> Any | None:
    """Load a DRG graph file (``.yaml``/``.yml``/``.json``) into a ``DRGGraph``.

    Returns ``None`` when the doctrine package is not importable, the file
    cannot be parsed, or validation against ``DRGGraph`` fails.
    """
    try:
        from charter.drg import DRGGraph
        from ruamel.yaml import YAML

        text = path.read_text(encoding="utf-8")
        if path.suffix in {".yaml", ".yml"}:
            yaml = YAML()
            raw = yaml.load(text)
        else:
            raw = json.loads(text)
        return DRGGraph.model_validate(raw)
    except Exception:  # noqa: BLE001
        logger.debug("charter_lint._drg: failed to load %s", path, exc_info=True)
        return None


def _load_project_drg(repo_root: Path) -> Any | None:
    """Try to load the project DRG from the project pack root (``.kittify/charter-packs/``).

    Search order matches the one used by ``entity_pages.py``::

        graph.yaml > merged_drg.json > drg.json > compiled_drg.json
    """
    drg_dir = resolve_project_pack_read_root(repo_root, quiet=True)
    candidates = ["graph.yaml", "merged_drg.json", "drg.json", "compiled_drg.json"]
    for name in candidates:
        path = drg_dir / name
        if path.exists():
            graph = _load_graph_file(path)
            if graph is not None:
                return graph
    return None


def _load_built_in_drg() -> Any | None:
    """Try to load the built-in DRG shipped under ``src/charter/offering/``.

    Routes through the canonical :func:`charter.offering.drg.loader.load_built_in_graph`
    seam (WP03, mission #2680) so the built-in graph is read in exactly one
    place and follows the monolith->fragment migration (WP05) transparently.
    The lazy, exception-safe shape is preserved: returns ``None`` when the
    doctrine package is not importable or the graph cannot be loaded, which the
    caller maps to :class:`GraphState.MISSING`.
    """
    try:
        from charter.drg import DRGLoadError, load_built_in_graph
    except Exception:  # noqa: BLE001
        logger.debug("charter_lint._drg: charter.drg loader not importable", exc_info=True)
        return None

    try:
        return load_built_in_graph()
    except DRGLoadError:
        logger.debug("charter_lint._drg: load_built_in_graph() failed", exc_info=True)
        return None


def load_merged_drg(repo_root: Path) -> tuple[Any | None, GraphState]:
    """Load the most-specific DRG available for *repo_root*.

    Resolution order (deterministic — locked by ADR
    ``2026-05-24-1-charter-freshness-ux-contract.md``):

    1. Project DRG under ``.kittify/charter-packs/`` →
       ``(graph, GraphState.MERGED)``. The "merged" label reflects the
       contract that a synthesized project DRG already incorporates the
       built-in and any org-pack layers; callers do not need to merge
       again.
    2. Built-in DRG shipped under ``src/charter/offering/`` via the canonical
       :func:`charter.offering.drg.loader.load_built_in_graph` seam →
       ``(graph, GraphState.BUILT_IN_ONLY)``.
    3. Nothing loadable → ``(None, GraphState.MISSING)``.

    The return shape is always a tuple. Earlier callers that expected a
    single ``Any | None`` value must be updated; the engine and CLI banner
    use the :class:`GraphState` tag to choose user-visible behaviour.
    """
    project_graph = _load_project_drg(repo_root)
    if project_graph is not None:
        return project_graph, GraphState.MERGED

    built_in_graph = _load_built_in_drg()
    if built_in_graph is not None:
        return built_in_graph, GraphState.BUILT_IN_ONLY

    return None, GraphState.MISSING


def get_incoming_edges(drg: Any, node_urn: str, relation_strs: set[str]) -> list[Any]:
    """Return edges that point *to* ``node_urn`` with a relation in ``relation_strs``.

    Uses ``edge.relation`` (not ``edge.type``) to match the doctrine DRGEdge schema.
    Returns ``[]`` when *drg* is ``None`` or has no ``edges`` attribute.
    """
    if drg is None:
        return []
    result: list[Any] = []
    for edge in getattr(drg, "edges", []):
        target = getattr(edge, "target", None)
        if target != node_urn:
            continue
        relation = getattr(edge, "relation", None)
        relation_val = getattr(relation, "value", str(relation) if relation else "")
        if relation_val in relation_strs:
            result.append(edge)
    return result
