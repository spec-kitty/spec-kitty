"""Load and merge DRG graph layers from YAML files.

Uses ``ruamel.yaml`` for round-trip safe YAML parsing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import ValidationError
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from charter.offering.drg.models import DRGGraph, DRGNode, load_graph_document
from charter.offering.pack_paths import built_in_root

__all__ = [
    "DRGLoadError",
    "built_in_graph_source",
    "has_graph_files",
    "load_built_in_graph",
    "load_graph",
    "load_graph_or_dir",
    "merge_layers",
]


class DRGLoadError(Exception):
    """Raised when a graph YAML file cannot be loaded or validated."""


def has_graph_files(path: Path) -> bool:
    """Return True iff *path* contains a graph file the DRG loader recognises.

    The DRG loader treats either ``graph.yaml`` (single-file layout) or
    one or more ``*.graph.yaml`` fragments as a valid graph source. A
    directory that exists but contains only sub-trees (eg ``overlays/``)
    is NOT a valid graph source and ``load_graph_or_dir`` would raise
    ``DRGLoadError`` on it. Callers that treat a project overlay as
    optional should guard with this helper.
    """
    if not path.is_dir():
        return False
    if (path / "graph.yaml").is_file():
        return True
    return any(path.glob("*.graph.yaml"))


def load_graph(path: Path) -> DRGGraph:
    """Read *path* as YAML and return a validated ``DRGGraph``.

    Raises :class:`DRGLoadError` on missing file, YAML parse error, or
    Pydantic validation error.
    """
    if not path.exists():
        raise DRGLoadError(f"File not found: {path}")

    yaml = YAML(typ="safe")
    try:
        data: Any = yaml.load(path)
    except YAMLError as exc:
        raise DRGLoadError(f"YAML parse error in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise DRGLoadError(f"Expected a YAML mapping at top level in {path}")

    # Route through the strict document boundary: a stray *top-level* key raises
    # a typed, named ``DRGGraphSchemaError`` that propagates past the many
    # ``except DRGLoadError`` silent-degrade handlers (fail-closed, NFR-006).
    # Any other validation failure re-raises as a raw ``ValidationError`` and is
    # wrapped into ``DRGLoadError`` exactly as before.
    try:
        return load_graph_document(data, source=str(path))
    except ValidationError as exc:
        raise DRGLoadError(
            f"Validation error in {path}: {exc}"
        ) from exc


def load_graph_or_dir(path: Path) -> DRGGraph:
    """Load a ``DRGGraph`` from a file or directory.

    If *path* is a file, delegates to :func:`load_graph`.
    If *path* is a directory, loads ``graph.yaml`` when present for backward
    compatibility; otherwise, loads ``*.graph.yaml`` fragments alphabetically
    and merges them left-to-right with :func:`merge_layers`.

    Raises :class:`DRGLoadError` if the path does not exist, is not a file or
    directory, or if no graph file can be found in a directory.
    """
    if path.is_file():
        return load_graph(path)

    if not path.exists():
        raise DRGLoadError(f"Path not found: {path}")

    if not path.is_dir():
        raise DRGLoadError(f"Path is not a file or directory: {path}")

    single_graph = path / "graph.yaml"
    if single_graph.is_file():
        return load_graph(single_graph)

    fragment_paths = sorted(path.glob("*.graph.yaml"))
    if not fragment_paths:
        raise DRGLoadError(f"No DRG graph files found in directory: {path}")

    graph = load_graph(fragment_paths[0])
    for fragment_path in fragment_paths[1:]:
        graph = merge_layers(graph, load_graph(fragment_path))
    return graph


def built_in_graph_source() -> Path:
    """Return the directory that ships the built-in DRG graph source.

    This is the ``packs/built-in/`` pack root, which holds the per-kind
    ``*.graph.yaml`` fragments (mission #2680 sharded the former single
    ``graph.yaml`` monolith; the relocation mission flattened the fragments out
    of ``src/charter/offering/`` into ``packs/built-in/``). Resolving to the *directory*
    -- rather than a specific ``graph.yaml`` file -- is what let
    :func:`load_built_in_graph` absorb the monolith->fragment migration
    transparently, with no call-site changes, and keeps either layout loadable
    going forward.

    Resolution routes through the single shared seam
    :func:`charter.offering.pack_paths.built_in_root`. This is deliberately
    **fail-closed**: if no ``packs/built-in/`` root can be located,
    :class:`~charter.offering.pack_paths.PackRootNotFound` propagates rather than falling
    back to an emptied ``src/charter/offering/`` tree that would silently yield a partial
    or empty graph (DIR-005). The resolver stays in-layer (doctrine) and never
    imports upward into charter (C-004).
    """
    return built_in_root()


#: The last built-in graph parsed in this process, keyed on the fingerprint of
#: the files it was parsed from (see :func:`_source_fingerprint`). Parsing the
#: shipped fragments costs about half a second, and one command can need the
#: built-in graph dozens of times (#5526). The shipped fragments are read-only
#: package data, so a key over their names, sizes and modification times
#: re-parses whenever any of them changes or a different root is resolved.
_BUILT_IN_GRAPH_MEMO: dict[tuple[object, ...], DRGGraph] = {}


def _source_fingerprint(source: Path) -> tuple[object, ...]:
    """Identify the graph files :func:`load_graph_or_dir` would read from *source*."""
    if source.is_dir():
        single_graph = source / "graph.yaml"
        files = [single_graph] if single_graph.is_file() else sorted(source.glob("*.graph.yaml"))
    else:
        files = [source]
    stats = []
    for path in files:
        stat = path.stat()
        stats.append((path.name, stat.st_size, stat.st_mtime_ns))
    return (str(source.resolve()), tuple(stats))


def load_built_in_graph() -> DRGGraph:
    """Load the shipped built-in DRG as a validated ``DRGGraph``.

    Canonical accessor for the built-in graph. Every source reader of the
    shipped graph routes through this one seam, which is what let the
    monolith->fragment migration (mission #2680) be a single change here instead
    of a scattered edit across ~22 call sites. Delegates to
    :func:`load_graph_or_dir` on :func:`built_in_graph_source`, which prefers a
    single ``graph.yaml`` when present and otherwise merges the shipped
    ``*.graph.yaml`` fragments alphabetically.

    Raises :class:`DRGLoadError` when no graph source can be loaded (the callers
    that must degrade rather than crash catch this themselves).

    The parsed graph is memoized per process against the fingerprint of its
    source files, and every call returns a deep copy, so a caller that mutates
    its graph never affects another caller.
    """
    source = built_in_graph_source()
    try:
        key = _source_fingerprint(source)
    except OSError:
        return load_graph_or_dir(source)
    cached = _BUILT_IN_GRAPH_MEMO.get(key)
    if cached is None:
        cached = load_graph_or_dir(source)
        _BUILT_IN_GRAPH_MEMO.clear()
        _BUILT_IN_GRAPH_MEMO[key] = cached
    return cached.model_copy(deep=True)


def merge_layers(
    built_in: DRGGraph,
    project: DRGGraph | None,
) -> DRGGraph:
    """Merge *built_in* and *project* graph layers.

    Semantics (additive only):

    * All nodes from *built_in* are kept.
    * Nodes in *project* with new URNs are added.
    * Nodes in *project* whose URN already exists in *built_in* override the
      label (but kind is retained from built-in).
    * All edges from both layers are combined (additive, no removal).

    Returns a new ``DRGGraph`` (not yet validated -- the caller should run
    ``validate_graph()`` on the result).
    """
    if project is None:
        return built_in

    # Build node index keyed by URN
    node_index: dict[str, DRGNode] = {n.urn: n for n in built_in.nodes}

    for pn in project.nodes:
        if pn.urn in node_index:
            # Override label only -- keep built-in kind
            existing = node_index[pn.urn]
            node_index[pn.urn] = existing.model_copy(
                update={"label": pn.label} if pn.label is not None else {}
            )
        else:
            node_index[pn.urn] = pn

    # Combine edges (additive)
    merged_edges = list(built_in.edges) + list(project.edges)

    return DRGGraph(
        schema_version=built_in.schema_version,
        generated_at=built_in.generated_at,
        generated_by=built_in.generated_by,
        nodes=list(node_index.values()),
        edges=merged_edges,
    )
