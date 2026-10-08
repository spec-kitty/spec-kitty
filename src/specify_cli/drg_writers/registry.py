"""The DRG writer registry — a derived, enumerable inventory of every graph writer.

Mission ``doctrine-delivery-reachability`` (WP01). Every site that persists
``DRGNode`` / ``DRGEdge`` / ``DRGGraph`` state is a **registry member**, so a
field added to a model later cannot be silently dropped by a writer nobody
remembered to update. The completeness gate
(``tests/specify_cli/drg_writers/test_registry_completeness.py``) iterates the
registry; it carries no hand-written list of writers.

The registry has **three shapes** because its members are three different
kinds of thing (contract ``writer-registry.md``):

- :class:`MappingWriter` — ``(DRGNode) -> dict`` / ``(DRGEdge) -> dict``.
- :class:`DocumentWriter` — ``(DRGGraph) -> dict`` (the five document-level keys).
- :class:`ModelBridge` — *constructs* a ``DRGEdge`` from a foreign fragment edge;
  its input is not a ``DRGEdge`` and its output is not a mapping, so its defect
  class is model→model field coverage, not serialization.

Mission ``doctrine-delivery-activation`` WP05 (#3075/#2977) grew
``DOCUMENT_WRITERS`` from one member to four: the three sites that used to
hand-restate the five document-level keys (``charter.activation.synthesizer.project_drg``,
``specify_cli.migration.rewrite_opposed_by``,
``charter.offering.packs.pack_assembler``) now delegate to
``graph_document_to_dict`` and join the registry. A companion static-scan
discovery gate (``tests/architectural/test_drg_writer_discovery.py``) scans
``src/`` directly for the two known bypass shapes, so a FUTURE hand-restating
site cannot repeat this blind spot by simply never joining this tuple.

**Hosting (layer constraint).** This module lives in ``src/specify_cli/`` — the
top layer — because a ``Final`` tuple naming ``charter.activation.synthesizer.project_drg``
*and* ``specify_cli.migration.rewrite_opposed_by`` cannot sit in ``doctrine`` or
``charter`` without reversing an import-layer edge. The members are wired here
**explicitly** — there is no import-time self-registration, which would make
membership depend on import order and re-open the exact "a writer that never
joins is invisible" blind spot the registry concedes.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
from typing import Any, Final, Protocol, cast

# Reach doctrine only through the charter facade (runtime→charter→doctrine
# boundary ratchet, ``tests/architectural/test_runtime_charter_doctrine_boundary``).
from charter.drg import (
    DRGEdge,
    DRGGraph,
    DRGNode,
    bridge_org_edge_to_drg_edge,
    graph_document_to_dict,
    model_to_graph_dict,
)
from charter.packs import pack_document_dict
from charter.activation.synthesizer import project_drg as _project_drg

from specify_cli.migration import rewrite_opposed_by as _rewrite_opposed_by

# ---------------------------------------------------------------------------
# The three writer shapes
# ---------------------------------------------------------------------------


class MappingWriter(Protocol):
    """A writer that serialises a single ``DRGNode`` / ``DRGEdge`` to a mapping.

    ``name`` is a **read-only** property (not a bare mutable attribute) so a
    ``frozen`` dataclass adapter structurally satisfies it.
    """

    @property
    def name(self) -> str: ...

    def node_to_mapping(self, node: DRGNode) -> dict[str, object]: ...

    def edge_to_mapping(self, edge: DRGEdge) -> dict[str, object]: ...


class DocumentWriter(Protocol):
    """A writer that serialises a whole ``DRGGraph`` document to a mapping."""

    @property
    def name(self) -> str: ...

    def document_to_mapping(self, graph: DRGGraph) -> dict[str, object]: ...


class ModelBridge(Protocol):
    """A writer that *mints* a ``DRGEdge`` from a foreign fragment-side edge."""

    @property
    def name(self) -> str: ...

    def bridge(self, fragment_edge: object, /, **ctx: object) -> DRGEdge | None: ...


# ---------------------------------------------------------------------------
# Function-backed adapters. Each wraps existing module-level writer functions so
# the registry does not require those modules to import it (no self-registration)
# and each carries a stable ``name`` used in failure messages (W-5).
# ---------------------------------------------------------------------------

_NodeFn = Callable[[DRGNode], dict[str, Any]]
_EdgeFn = Callable[[DRGEdge], dict[str, Any]]
_DocumentFn = Callable[[DRGGraph], dict[str, Any]]


@dataclass(frozen=True)
class _FunctionMappingWriter:
    """Adapts a pair of ``(node_fn, edge_fn)`` module functions to ``MappingWriter``."""

    name: str
    node_fn: _NodeFn
    edge_fn: _EdgeFn

    def node_to_mapping(self, node: DRGNode) -> dict[str, object]:
        return self.node_fn(node)

    def edge_to_mapping(self, edge: DRGEdge) -> dict[str, object]:
        return self.edge_fn(edge)


@dataclass(frozen=True)
class _FunctionDocumentWriter:
    """Adapts a ``(DRGGraph) -> dict`` module function to ``DocumentWriter``."""

    name: str
    document_fn: _DocumentFn

    def document_to_mapping(self, graph: DRGGraph) -> dict[str, object]:
        return self.document_fn(graph)


@dataclass(frozen=True)
class _OrgEdgeModelBridge:
    """Adapts ``charter.offering.drg.merge.bridge_org_edge_to_drg_edge`` to ``ModelBridge``.

    The wrapped function returns ``(edge, conflict)``; the bridge surface exposes
    only the minted edge (``None`` on refusal). The endpoint-resolution context
    (``node_id_to_urn`` / ``built_in_urns`` / ``source``) is passed through
    ``**ctx`` so the adapter stays faithful to the real call site without
    re-implementing endpoint binding.
    """

    name: str

    def bridge(self, fragment_edge: object, /, **ctx: object) -> DRGEdge | None:
        edge, _conflict = bridge_org_edge_to_drg_edge(
            fragment_edge,
            cast("Mapping[str, str]", ctx["node_id_to_urn"]),
            cast("Collection[str]", ctx["built_in_urns"]),
            str(ctx["source"]),
        )
        return edge


# ---------------------------------------------------------------------------
# The registry. Explicit ``Final`` tuples — the single source of truth for which
# writers exist. Adding a persistence site means adding a member here. The
# element type is the Protocol shape; the ``check_*`` assertions below pin that
# each concrete adapter structurally satisfies it (and that mypy agrees).
# ---------------------------------------------------------------------------

MAPPING_WRITERS: Final[tuple[MappingWriter, ...]] = (
    _FunctionMappingWriter(
        name="extractor",
        node_fn=model_to_graph_dict,
        edge_fn=model_to_graph_dict,
    ),
    _FunctionMappingWriter(
        name="charter.activation.synthesizer.project_drg",
        node_fn=_project_drg._node_to_dict,
        edge_fn=_project_drg._edge_to_dict,
    ),
    _FunctionMappingWriter(
        name="specify_cli.migration.rewrite_opposed_by",
        node_fn=_rewrite_opposed_by._node_to_dict,
        edge_fn=_rewrite_opposed_by._edge_to_dict,
    ),
)

DOCUMENT_WRITERS: Final[tuple[DocumentWriter, ...]] = (
    _FunctionDocumentWriter(
        name="extractor._dump_graph_document",
        document_fn=graph_document_to_dict,
    ),
    _FunctionDocumentWriter(
        name="charter.activation.synthesizer.project_drg._document_dict",
        document_fn=_project_drg._document_dict,
    ),
    _FunctionDocumentWriter(
        name="specify_cli.migration.rewrite_opposed_by._document_dict",
        document_fn=_rewrite_opposed_by._document_dict,
    ),
    _FunctionDocumentWriter(
        name="charter.offering.packs.pack_assembler.pack_document_dict",
        document_fn=pack_document_dict,
    ),
)

MODEL_BRIDGES: Final[tuple[ModelBridge, ...]] = (
    _OrgEdgeModelBridge(name="charter.offering.drg.merge.bridge_org_edge_to_drg_edge"),
)


__all__ = [
    "DOCUMENT_WRITERS",
    "MAPPING_WRITERS",
    "MODEL_BRIDGES",
    "DocumentWriter",
    "MappingWriter",
    "ModelBridge",
]
