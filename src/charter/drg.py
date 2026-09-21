"""Charter facade for DRG (Doctrine Reference Graph) offering types.

This module is the charter-layer proxy for runtime callers that historically
imported from ``charter.offering.drg`` directly. The runtime → charter → doctrine
boundary (ADR 2026-03-27-1, tightened by mission
``charter-mediated-doctrine-selection-01KRTZCA``) requires runtime modules
under ``src/specify_cli/`` to reach doctrine artifacts only through such
charter facades.

This file is a pure re-export module — the offering-type surface only
(``ArtifactKind``, ``DRGNode``, ``NodeKind``, the org-DRG schema/exception
types, and the loader/query functions that live in ``charter.offering.drg.*``).

Schema / fragment models live in ``charter.offering.drg.org_pack_loader``
(PR #1119 DDD-boundary fix): ``OrgDRGFragment``, ``OrgPackMissingError``.
Charter re-exports them here so existing ``from charter.drg import …`` call
sites remain valid without crossing the layer boundary directly.

Activation-aware logic split (mission ``charter-activation-split-01M16ZSE``,
DEC-1): the org-DRG loader (``load_org_drg``) and the FR-018 activation
filter (``filter_graph_by_activation`` + its private helpers) now live in
:mod:`charter.activation.drg_activation` — they read project-charter
activation state (:class:`~charter.activation.pack_context.PackContext`),
which is an activation concern, not an offering-type concern. Import those
two from there:

    from charter.activation.drg_activation import (
        filter_graph_by_activation,
        load_org_drg,
    )

``merge_three_layers`` is a pure ``charter.offering.drg.merge`` re-export
(no activation state), so it stays available on this offering facade too and
is *also* re-exported from ``charter.activation.drg_activation`` for callers
already importing the split trio — both paths resolve the same symbol.

Slice F WP06 design notes
-------------------------

The org-DRG fragment schema (``OrgDRGFragment``) intentionally uses a
simpler node/edge shape than ``charter.offering.drg.models.DRGNode`` /
``DRGEdge``. The reason is C-009: the contract round-trip gate exercises
the YAML example in
``kitty-specs/<mission>/contracts/org-drg-schema.md`` which uses plural
kinds (``kind: directives``) and human-friendly fields (``id``, ``title``,
``body_path``). The built-in DRGNode uses URNs and singular enum kinds. To
satisfy both surfaces:

* Fragment-side parsing uses private node/edge models declared in
  ``charter.offering.drg.org_pack_loader``. Their ``kind`` field is constrained
  to the Mission B 8-kind plural universe (C-009 binding).
* ``merge_three_layers`` bridges fragment nodes onto the built-in DRG by
  minting URNs of the form ``<singular_kind>:<id>`` (e.g. ``directive:sox-controls``).
* Provenance is threaded via the declared ``provenance`` field on the DRG
  models (FR-013, D2-revised). The merge returns a ``DRGGraph`` whose node /
  edge objects carry their ``provenance`` set through ``model_copy``;
  consumers read it directly with ``node.provenance``.

This matches data-model.md §2's stated provenance semantics
(``source: built-in | org:<pack> | project``) while honouring the
contract YAML shape that the FR-140 round-trip gate enforces.
"""

from __future__ import annotations

# ArtifactKind / slug_for are re-exported from the curated public surface
# ``charter.offering.api`` (not ``charter.offering.artifact_kinds`` directly) so the
# PUBLIC wheel symbols gain a live in-repo caller — the from-``charter.offering.api``
# wiring the no-dead-symbol gate (``tests/architectural/test_no_dead_symbols.py``) and
# the strict T007 live-caller assertion (``test_doctrine_public_surface.py``) depend
# on. Object identity is unchanged: ``charter.offering.api.ArtifactKind is
# charter.offering.artifact_kinds.ArtifactKind`` (mission ``doctrine-public-api-surface``
# WP03, FR-003 / NFR-002 / contract C1).
from charter.offering.api import ArtifactKind, slug_for
from charter.offering.base import DoctrineLayerCollisionWarning
from charter.offering.drg import (
    DRGLoadError,
    DRGValidationError,
    load_built_in_graph,
    load_graph,
    load_graph_or_dir,
    merge_layers,
    validate_dangling_references,
)
from charter.offering.drg.merge import (
    OrgDRGConflict,
    OrgDRGConflictError,
    merge_three_layers,
    UnknownRelationError,
)
from charter.offering.drg.merge import (
    bridge_org_edge_to_drg_edge,
)
from charter.offering.drg.migration.extractor import (
    FIELDS_WITHHELD_FROM_GRAPH_OUTPUT,
    graph_document_to_dict,
    model_to_graph_dict,
)
from charter.offering.drg.models import DRGEdge, DRGGraph, DRGNode, NodeKind, Relation
from charter.offering.drg.org_pack_config import (
    OrgPackEnvVarUnsetError,
    OrgPackSubdirEscapeError,
    load_pack_registry as load_pack_registry,
    resolve_existing_org_roots,
    resolve_org_dirs,
    resolve_org_roots,
)
from charter.offering.drg.org_pack_loader import (
    OrgDRGFragment,
    OrgPackMissingError,
    OrgPackParseError,
    OrgPackSchemaError,
    load_org_pack,
)
from charter.offering.drg.query import ResolvedContext, resolve_context
from charter.offering.drg.project_scan import scan_project_artifacts

__all__ = [
    "merge_three_layers",
    "ArtifactKind",
    "DRGEdge",
    "DRGGraph",
    "DRGLoadError",
    "DRGNode",
    "DRGValidationError",
    "DoctrineLayerCollisionWarning",
    "FIELDS_WITHHELD_FROM_GRAPH_OUTPUT",
    "NodeKind",
    "OrgDRGConflict",
    "OrgDRGConflictError",
    "OrgDRGFragment",
    "OrgPackEnvVarUnsetError",
    "OrgPackMissingError",
    "OrgPackParseError",
    "OrgPackSchemaError",
    "OrgPackSubdirEscapeError",
    "Relation",
    "ResolvedContext",
    "UnknownRelationError",
    "bridge_org_edge_to_drg_edge",
    "graph_document_to_dict",
    "load_built_in_graph",
    "load_graph",
    "load_graph_or_dir",
    "load_org_pack",
    "merge_layers",
    "model_to_graph_dict",
    "resolve_context",
    "scan_project_artifacts",
    "resolve_existing_org_roots",
    "resolve_org_dirs",
    "resolve_org_roots",
    "slug_for",
    "validate_dangling_references",
]
