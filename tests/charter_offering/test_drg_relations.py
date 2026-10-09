"""Tests for the DRG relation vocabulary and reverse-adjacency accessor (WP02).

Covers:

- ``Relation.SPECIALIZES_FROM`` enum membership/value (T005, FR-001) and its
  distinctness from ``Relation.DELEGATES_TO``.
- ``DRGGraph.edges_to`` reverse adjacency (T006): with/without relation filter
  and the no-incoming-edges case.
- The no-leak regression (T007, FR-002): a ``specializes_from`` lineage edge
  must never appear as a ``delegates_to`` handoff edge, neither via
  :meth:`DRGGraph.edges_from` nor via :func:`walk_edges`.
"""

from __future__ import annotations

import pytest

from charter.offering.drg.models import DRGEdge, DRGGraph, DRGNode, NodeKind, Relation
from charter.offering.drg.query import resolve_transitive_refs, walk_edges

pytestmark = [pytest.mark.doctrine, pytest.mark.fast]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_graph(
    nodes: list[tuple[str, NodeKind]],
    edges: list[tuple[str, str, Relation]],
) -> DRGGraph:
    """Build a minimal in-memory :class:`DRGGraph` for a test."""
    return DRGGraph(
        schema_version="1.0",
        generated_at="2026-06-01T00:00:00Z",
        generated_by="test",
        nodes=[DRGNode(urn=urn, kind=kind) for urn, kind in nodes],
        edges=[
            DRGEdge(source=src, target=tgt, relation=rel)
            for src, tgt, rel in edges
        ],
    )


# Two agent-profile nodes used across the lineage tests.
_A = ("agent_profile:child", NodeKind.AGENT_PROFILE)
_B = ("agent_profile:parent", NodeKind.AGENT_PROFILE)


# ---------------------------------------------------------------------------
# T005 -- Relation.SPECIALIZES_FROM enum
# ---------------------------------------------------------------------------


def test_specializes_from_value() -> None:
    assert Relation.SPECIALIZES_FROM.value == "specializes_from"
    assert Relation("specializes_from") is Relation.SPECIALIZES_FROM


def test_specializes_from_distinct_from_delegates_to() -> None:
    # Lineage and runtime handoff are different relations (FR-001 vs FR-002).
    assert Relation.SPECIALIZES_FROM is not Relation.DELEGATES_TO
    assert Relation.SPECIALIZES_FROM.value != Relation.DELEGATES_TO.value


def test_specializes_from_is_member() -> None:
    assert Relation.SPECIALIZES_FROM in set(Relation)


# ---------------------------------------------------------------------------
# T006 -- DRGGraph.edges_to reverse adjacency
# ---------------------------------------------------------------------------


def test_edges_to_returns_incoming_edges() -> None:
    graph = _make_graph(
        nodes=[_A, _B],
        edges=[("agent_profile:child", "agent_profile:parent", Relation.SPECIALIZES_FROM)],
    )
    incoming = graph.edges_to("agent_profile:parent")
    assert {(e.source, e.target, e.relation) for e in incoming} == {
        ("agent_profile:child", "agent_profile:parent", Relation.SPECIALIZES_FROM)
    }
    assert incoming[0].source == "agent_profile:child"
    assert incoming[0].target == "agent_profile:parent"
    assert incoming[0].relation is Relation.SPECIALIZES_FROM


def test_edges_to_inverts_edges_from() -> None:
    graph = _make_graph(
        nodes=[_A, _B],
        edges=[("agent_profile:child", "agent_profile:parent", Relation.SPECIALIZES_FROM)],
    )
    # edges_from(child) and edges_to(parent) describe the same edge from
    # opposite directions; edges_from(parent) and edges_to(child) are empty.
    assert graph.edges_from("agent_profile:child") == graph.edges_to(
        "agent_profile:parent"
    )
    assert graph.edges_from("agent_profile:parent") == []
    assert graph.edges_to("agent_profile:child") == []


def test_edges_to_relation_filter() -> None:
    graph = _make_graph(
        nodes=[_A, _B, ("agent_profile:other", NodeKind.AGENT_PROFILE)],
        edges=[
            ("agent_profile:child", "agent_profile:parent", Relation.SPECIALIZES_FROM),
            ("agent_profile:other", "agent_profile:parent", Relation.SUGGESTS),
        ],
    )
    lineage = graph.edges_to("agent_profile:parent", Relation.SPECIALIZES_FROM)
    assert [e.source for e in lineage] == ["agent_profile:child"]

    suggests = graph.edges_to("agent_profile:parent", Relation.SUGGESTS)
    assert [e.source for e in suggests] == ["agent_profile:other"]

    # Unfiltered returns both incoming edges.
    assert {e.source for e in graph.edges_to("agent_profile:parent")} == {
        "agent_profile:child",
        "agent_profile:other",
    }


def test_edges_to_no_incoming_edges() -> None:
    graph = _make_graph(
        nodes=[_A, _B],
        edges=[("agent_profile:child", "agent_profile:parent", Relation.SPECIALIZES_FROM)],
    )
    # A leaf with no incoming edges, and a relation filter that matches nothing.
    assert graph.edges_to("agent_profile:child") == []
    assert graph.edges_to("agent_profile:parent", Relation.DELEGATES_TO) == []


def test_edges_to_filter_excludes_nonmatching_relation() -> None:
    graph = _make_graph(
        nodes=[_A, _B],
        edges=[("agent_profile:child", "agent_profile:parent", Relation.SPECIALIZES_FROM)],
    )
    assert graph.edges_to("agent_profile:parent", Relation.DELEGATES_TO) == []


# ---------------------------------------------------------------------------
# T007 -- No-leak regression: lineage MUST NOT surface as delegation (FR-002)
# ---------------------------------------------------------------------------


def test_lineage_does_not_leak_into_delegation_edges_from() -> None:
    """A specializes_from edge must not be visible to a DELEGATES_TO query."""
    graph = _make_graph(
        nodes=[_A, _B],
        edges=[("agent_profile:child", "agent_profile:parent", Relation.SPECIALIZES_FROM)],
    )
    # The lineage edge exists...
    assert graph.edges_from("agent_profile:child", Relation.SPECIALIZES_FROM)
    # ...but it is invisible to a delegation query.
    assert graph.edges_from("agent_profile:child", Relation.DELEGATES_TO) == []


def test_lineage_not_reachable_via_delegation_walk() -> None:
    """walk_edges over DELEGATES_TO must not traverse a lineage edge."""
    graph = _make_graph(
        nodes=[_A, _B],
        edges=[("agent_profile:child", "agent_profile:parent", Relation.SPECIALIZES_FROM)],
    )
    reachable = walk_edges(
        graph,
        start_urns={"agent_profile:child"},
        relations={Relation.DELEGATES_TO},
    )
    # Only the seed node is visited; the parent is NOT reachable because the
    # only connecting edge is lineage, not delegation.
    assert reachable == {"agent_profile:child"}
    assert "agent_profile:parent" not in reachable

    # Sanity check: walking the lineage relation DOES reach the parent, proving
    # the edge is present and the negative result above is meaningful.
    via_lineage = walk_edges(
        graph,
        start_urns={"agent_profile:child"},
        relations={Relation.SPECIALIZES_FROM},
    )
    assert via_lineage == {"agent_profile:child", "agent_profile:parent"}


# ---------------------------------------------------------------------------
# WP07/T027 -- transitively-reached asset nodes must surface in `.assets`,
# not be silently dropped from the ResolveTransitiveRefsResult bucket.
# ---------------------------------------------------------------------------


def test_resolve_transitive_refs_includes_transitively_reached_asset() -> None:
    """A `requires`-transitive asset node must appear in `.assets`.

    Regression for the dropped-node bug: `buckets` was populated for every
    `NodeKind` (including `ASSET`) but the constructor call at the bottom of
    `resolve_transitive_refs` never read `buckets[NodeKind.ASSET]`, so any
    asset reached transitively was silently discarded from the result.
    """
    graph = _make_graph(
        nodes=[
            ("directive:root-directive", NodeKind.DIRECTIVE),
            ("tactic:middle-tactic", NodeKind.TACTIC),
            ("asset:leaf-icon", NodeKind.ASSET),
        ],
        edges=[
            ("directive:root-directive", "tactic:middle-tactic", Relation.REQUIRES),
            ("tactic:middle-tactic", "asset:leaf-icon", Relation.REQUIRES),
        ],
    )

    result = resolve_transitive_refs(
        graph,
        start_urns={"directive:root-directive"},
        relations={Relation.REQUIRES},
    )

    assert result.assets == ["leaf-icon"]
    assert result.tactics == ["middle-tactic"]
    assert result.unresolved == []
