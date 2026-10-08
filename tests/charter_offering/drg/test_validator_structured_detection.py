"""Structured duplicate/dangling detection helpers (charter-synthesize-
reconciliation WP01, amendment #3).

``duplicate_edge_triples`` / ``dangling_endpoints`` are the extracted SSOT
both ``validate_graph`` (string formatting) and
``charter.activation.synthesizer.reconcile`` (preserved-vs-new-emit provenance
classification) consume. This module pins:

1. The structured helpers themselves return the right edges.
2. ``validate_graph``'s string output is byte-identical to its pre-extraction
   shape (the extraction must not be observable from the outside).
"""

from __future__ import annotations

import pytest

from charter.offering.drg.models import DRGEdge, DRGGraph, DRGNode, NodeKind, Relation
from charter.offering.drg.validator import (
    _validate_duplicate_edges,
    dangling_endpoints,
    duplicate_edge_triples,
    validate_dangling_references,
    validate_graph,
)

pytestmark = [pytest.mark.doctrine, pytest.mark.fast]


def _graph(nodes: list[DRGNode], edges: list[DRGEdge]) -> DRGGraph:
    return DRGGraph(schema_version="1.0", generated_at="STATIC", generated_by="test", nodes=nodes, edges=edges)


class TestDuplicateEdgeTriples:
    def test_no_duplicates_returns_empty(self) -> None:
        node_a = DRGNode(urn="tactic:a", kind=NodeKind.TACTIC)
        node_b = DRGNode(urn="tactic:b", kind=NodeKind.TACTIC)
        edge = DRGEdge(source="tactic:a", target="tactic:b", relation=Relation.APPLIES)
        graph = _graph([node_a, node_b], [edge])
        assert duplicate_edge_triples(graph) == []

    def test_second_occurrence_of_a_triple_is_returned(self) -> None:
        node_a = DRGNode(urn="tactic:a", kind=NodeKind.TACTIC)
        node_b = DRGNode(urn="tactic:b", kind=NodeKind.TACTIC)
        first = DRGEdge(source="tactic:a", target="tactic:b", relation=Relation.APPLIES)
        second = DRGEdge(source="tactic:a", target="tactic:b", relation=Relation.APPLIES)
        graph = _graph([node_a, node_b], [first, second])

        duplicates = duplicate_edge_triples(graph)

        assert duplicates == [second]

    def test_different_relation_is_not_a_duplicate(self) -> None:
        node_a = DRGNode(urn="tactic:a", kind=NodeKind.TACTIC)
        node_b = DRGNode(urn="tactic:b", kind=NodeKind.TACTIC)
        applies = DRGEdge(source="tactic:a", target="tactic:b", relation=Relation.APPLIES)
        in_tension = DRGEdge(source="tactic:a", target="tactic:b", relation=Relation.IN_TENSION_WITH)
        graph = _graph([node_a, node_b], [applies, in_tension])

        assert duplicate_edge_triples(graph) == []

    def test_validate_duplicate_edges_string_output_unchanged(self) -> None:
        node_a = DRGNode(urn="tactic:a", kind=NodeKind.TACTIC)
        node_b = DRGNode(urn="tactic:b", kind=NodeKind.TACTIC)
        first = DRGEdge(source="tactic:a", target="tactic:b", relation=Relation.APPLIES)
        second = DRGEdge(source="tactic:a", target="tactic:b", relation=Relation.APPLIES)
        graph = _graph([node_a, node_b], [first, second])

        errors = _validate_duplicate_edges(graph)

        assert errors == ["Duplicate edge: (tactic:a --applies--> tactic:b)"]


class TestDanglingEndpoints:
    def test_no_dangling_returns_empty(self) -> None:
        node_a = DRGNode(urn="tactic:a", kind=NodeKind.TACTIC)
        node_b = DRGNode(urn="tactic:b", kind=NodeKind.TACTIC)
        edge = DRGEdge(source="tactic:a", target="tactic:b", relation=Relation.APPLIES)
        graph = _graph([node_a, node_b], [edge])
        assert dangling_endpoints(graph) == []

    def test_dangling_target_edge_is_returned_once(self) -> None:
        node_a = DRGNode(urn="tactic:a", kind=NodeKind.TACTIC)
        edge = DRGEdge(source="tactic:a", target="tactic:missing", relation=Relation.APPLIES)
        graph = _graph([node_a], [edge])

        assert dangling_endpoints(graph) == [edge]

    def test_edge_dangling_on_both_sides_appears_once(self) -> None:
        edge = DRGEdge(source="tactic:missing-a", target="tactic:missing-b", relation=Relation.APPLIES)
        graph = _graph([], [edge])

        assert dangling_endpoints(graph) == [edge]

    def test_validate_dangling_references_string_output_unchanged_both_sides(self) -> None:
        edge = DRGEdge(source="tactic:missing-a", target="tactic:missing-b", relation=Relation.APPLIES)
        graph = _graph([], [edge])

        errors = validate_dangling_references(graph)

        assert errors == [
            "Dangling source: edge (tactic:missing-a --applies--> tactic:missing-b) "
            "references non-existent node 'tactic:missing-a'",
            "Dangling target: edge (tactic:missing-a --applies--> tactic:missing-b) "
            "references non-existent node 'tactic:missing-b'",
        ]

    def test_validate_graph_still_reports_both_duplicate_and_dangling(self) -> None:
        node_a = DRGNode(urn="tactic:a", kind=NodeKind.TACTIC)
        node_b = DRGNode(urn="tactic:b", kind=NodeKind.TACTIC)
        dup1 = DRGEdge(source="tactic:a", target="tactic:b", relation=Relation.APPLIES)
        dup2 = DRGEdge(source="tactic:a", target="tactic:b", relation=Relation.APPLIES)
        dangling = DRGEdge(source="tactic:a", target="tactic:missing", relation=Relation.APPLIES)
        graph = _graph([node_a, node_b], [dup1, dup2, dangling])

        errors = validate_graph(graph)

        assert "Duplicate edge: (tactic:a --applies--> tactic:b)" in errors
        assert (
            "Dangling target: edge (tactic:a --applies--> tactic:missing) "
            "references non-existent node 'tactic:missing'"
        ) in errors
