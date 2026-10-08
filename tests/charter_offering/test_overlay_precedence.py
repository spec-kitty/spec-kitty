"""T021 — Overlay precedence + provenance after relocation (FR-008).

The relocation changed *where* built-in content lives on disk
(``packs/built-in/<kind>/``) but MUST NOT change the three-layer overlay
semantics that ``charter.offering.drg.merge.merge_three_layers`` implements. This
verifies, on a synthetic ``built-in + org + project`` overlay, the three
properties the move could plausibly have broken:

(a) *tier precedence* — a higher tier overriding a built-in URN wins
    (``built-in < org < project``).
(b) *origin-tier provenance is path-independent* — ``_tag_source`` tags a node
    that came from the relocated built-in tier as ``"built-in"`` regardless of
    the filesystem path it now loads from. A real, moved built-in URN is used
    so this is not a synthetic-only claim.
(c) *additive edges* — no built-in edge is dropped when an overlay adds edges
    (``merge_three_layers`` is additive on edges, full-node replacement on
    override).
"""

from __future__ import annotations

from typing import Any

import pytest

from charter.offering.drg.loader import load_built_in_graph
from charter.offering.drg.merge import merge_three_layers
from charter.offering.drg.models import DRGEdge, DRGGraph, DRGNode, NodeKind, Relation
from charter.offering.drg.org_pack_loader import OrgDRGFragment

pytestmark = [pytest.mark.fast, pytest.mark.doctrine, pytest.mark.corpus]


def _graph(
    nodes: list[DRGNode] | None = None,
    edges: list[DRGEdge] | None = None,
) -> DRGGraph:
    return DRGGraph(
        schema_version="1.0",
        generated_at="2026-07-30T00:00:00Z",
        generated_by="overlay-precedence-test",
        nodes=nodes or [],
        edges=edges or [],
    )


def _fragment(
    pack_name: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> OrgDRGFragment:
    return OrgDRGFragment.model_validate(
        {
            "pack_name": pack_name,
            "source_kind": "local_path",
            "source_ref": f"/nonexistent/{pack_name}",
            "layer_index": 1,
            "provenance_marker": "org",
            "nodes": nodes,
            "edges": edges,
        }
    )


# ---------------------------------------------------------------------------
# (a) tier precedence: built-in < org < project
# ---------------------------------------------------------------------------


def test_org_overrides_built_in_node() -> None:
    built_in = _graph(
        nodes=[DRGNode(urn="directive:shared-d", kind=NodeKind.DIRECTIVE, label="BuiltIn")]
    )
    org = _fragment(
        "acme",
        nodes=[{"id": "shared-d", "kind": "directives", "title": "OrgLabel"}],
        edges=[],
    )

    merged = merge_three_layers(built_in=built_in, org_fragments=[org], project=None)

    node = next(n for n in merged.nodes if n.urn == "directive:shared-d")
    assert node.label == "OrgLabel"
    assert node.provenance == "org:acme"


def test_project_overrides_org_and_built_in_node() -> None:
    built_in = _graph(
        nodes=[DRGNode(urn="directive:shared-d", kind=NodeKind.DIRECTIVE, label="BuiltIn")]
    )
    org = _fragment(
        "acme",
        nodes=[{"id": "shared-d", "kind": "directives", "title": "OrgLabel"}],
        edges=[],
    )
    project = _graph(
        nodes=[DRGNode(urn="directive:shared-d", kind=NodeKind.DIRECTIVE, label="ProjectLabel")]
    )

    merged = merge_three_layers(built_in=built_in, org_fragments=[org], project=project)

    node = next(n for n in merged.nodes if n.urn == "directive:shared-d")
    assert node.label == "ProjectLabel"
    assert node.provenance == "project"


# ---------------------------------------------------------------------------
# (b) origin-tier provenance is path-independent for a real moved built-in URN
# ---------------------------------------------------------------------------


def test_moved_built_in_urn_is_tagged_built_in() -> None:
    """A real relocated built-in node still tags as ``built-in`` (origin tier).

    The node's content now loads from ``packs/built-in/directives/`` yet the
    provenance marker is tier-derived, not path-derived — so it must read
    ``built-in``.
    """
    real = load_built_in_graph()
    merged = merge_three_layers(built_in=real, org_fragments=[], project=None)

    sample_urn = "directive:DIRECTIVE_001"
    node = next((n for n in merged.nodes if n.urn == sample_urn), None)
    assert node is not None, f"{sample_urn} missing from the relocated built-in graph"
    assert node.provenance == "built-in"

    # No moved built-in node is tagged anything other than the origin tier.
    assert all(n.provenance == "built-in" for n in merged.nodes)
    assert all(e.provenance == "built-in" for e in merged.edges)


# ---------------------------------------------------------------------------
# (c) additive edges: no built-in edge dropped when an overlay adds edges
# ---------------------------------------------------------------------------


def test_overlay_adding_an_edge_drops_no_built_in_edge() -> None:
    built_in = _graph(
        nodes=[
            DRGNode(urn="tactic:t-alpha", kind=NodeKind.TACTIC, label="T"),
            DRGNode(urn="directive:d-alpha", kind=NodeKind.DIRECTIVE, label="D"),
        ],
        edges=[
            DRGEdge(
                source="tactic:t-alpha",
                target="directive:d-alpha",
                relation=Relation.APPLIES,
            )
        ],
    )
    org = _fragment(
        "acme",
        nodes=[],
        edges=[
            {
                "source": "tactic:t-alpha",
                "target": "directive:d-alpha",
                "relation": "suggests",
            }
        ],
    )

    merged = merge_three_layers(built_in=built_in, org_fragments=[org], project=None)

    edge_triples = {(e.source, e.target, e.relation) for e in merged.edges}
    # The built-in edge survives...
    assert ("tactic:t-alpha", "directive:d-alpha", Relation.APPLIES) in edge_triples
    # ...alongside the additive org edge.
    assert ("tactic:t-alpha", "directive:d-alpha", Relation.SUGGESTS) in edge_triples

    built_in_edge = next(
        e for e in merged.edges if e.relation == Relation.APPLIES
    )
    assert built_in_edge.provenance == "built-in"
