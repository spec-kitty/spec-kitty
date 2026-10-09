"""Tests for tension-vocabulary read/validation surfaces (WP04).

Mission ``doctrine-tension-edges-01KY1WPC``, FR-004/FR-014:

- T022 (INV-001): a single stored ``in_tension_with`` edge must be
  discoverable from either endpoint URN via :class:`DRGGraph`'s existing
  ``edges_from``/``edges_to`` query helpers -- no new graph primitive is
  needed (Assumption A3).
- T023 (INV-004): a ``rejects`` edge whose target is not a
  ``NodeKind.ANTI_PATTERN`` node must raise a validation error via
  :func:`charter.offering.drg.validator.validate_graph` /
  :func:`charter.offering.drg.validator.assert_valid`.
"""

from __future__ import annotations

import pytest

from charter.offering.drg.models import DRGEdge, DRGGraph, DRGNode, NodeKind, Relation
from charter.offering.drg.validator import (
    DRGValidationError,
    assert_valid,
    validate_graph,
)

pytestmark = [pytest.mark.doctrine, pytest.mark.fast]


def _graph(nodes: list[DRGNode], edges: list[DRGEdge]) -> DRGGraph:
    return DRGGraph(
        schema_version="1.0",
        generated_at="STATIC",
        generated_by="test",
        nodes=nodes,
        edges=edges,
    )


class TestInTensionWithSymmetricRead:
    """T022 (INV-001): a single edge is queryable from either endpoint."""

    def test_single_edge_discoverable_from_both_endpoints(self) -> None:
        node_a = DRGNode(urn="tactic:tdd-first", kind=NodeKind.TACTIC)
        node_b = DRGNode(urn="tactic:test-after", kind=NodeKind.TACTIC)
        edge = DRGEdge(
            source="tactic:tdd-first",
            target="tactic:test-after",
            relation=Relation.IN_TENSION_WITH,
        )
        graph = _graph([node_a, node_b], [edge])

        # Rooted at the declared source: an outgoing edge.
        outgoing = graph.edges_from("tactic:tdd-first", relation=Relation.IN_TENSION_WITH)
        assert outgoing == [edge]

        # Rooted at the declared target: the SAME stored edge is discoverable
        # as an incoming edge -- no second edge was authored or synthesized.
        incoming = graph.edges_to("tactic:test-after", relation=Relation.IN_TENSION_WITH)
        assert incoming == [edge]

        # Cross-check: querying outgoing-from-target / incoming-to-source
        # correctly finds nothing (the relation is symmetric in meaning but
        # stored as a single directed edge, C-002).
        assert graph.edges_from("tactic:test-after", relation=Relation.IN_TENSION_WITH) == []
        assert graph.edges_to("tactic:tdd-first", relation=Relation.IN_TENSION_WITH) == []


class TestRejectsTargetValidation:
    """T021/T023 (INV-004): ``rejects`` edges must target an anti_pattern node."""

    def test_rejects_edge_to_anti_pattern_target_passes(self) -> None:
        good = DRGNode(urn="tactic:clean-commits", kind=NodeKind.TACTIC)
        smell = DRGNode(urn="anti_pattern:force-push-shared-branch", kind=NodeKind.ANTI_PATTERN)
        edge = DRGEdge(
            source="tactic:clean-commits",
            target="anti_pattern:force-push-shared-branch",
            relation=Relation.REJECTS,
        )
        graph = _graph([good, smell], [edge])

        assert validate_graph(graph) == []
        assert_valid(graph)  # must not raise

    def test_rejects_edge_to_non_anti_pattern_target_is_detected(self) -> None:
        good = DRGNode(urn="tactic:clean-commits", kind=NodeKind.TACTIC)
        wrong_kind_target = DRGNode(urn="tactic:test-after", kind=NodeKind.TACTIC)
        edge = DRGEdge(
            source="tactic:clean-commits",
            target="tactic:test-after",
            relation=Relation.REJECTS,
        )
        graph = _graph([good, wrong_kind_target], [edge])

        errors = validate_graph(graph)
        assert len(errors) == 1
        assert "anti_pattern" in errors[0]
        assert "tactic:test-after" in errors[0]

        with pytest.raises(DRGValidationError):
            assert_valid(graph)

    def test_rejects_edge_to_missing_target_not_double_reported(self) -> None:
        """A missing target is dangling (validate_graph's job), not a kind error."""
        good = DRGNode(urn="tactic:clean-commits", kind=NodeKind.TACTIC)
        edge = DRGEdge(
            source="tactic:clean-commits",
            target="anti_pattern:ghost",
            relation=Relation.REJECTS,
        )
        graph = _graph([good], [edge])

        errors = validate_graph(graph)
        assert any("Dangling target" in e for e in errors)
        assert not any("anti_pattern node" in e for e in errors)

    def test_non_rejects_relations_ignored(self) -> None:
        source = DRGNode(urn="tactic:clean-commits", kind=NodeKind.TACTIC)
        target = DRGNode(urn="tactic:test-after", kind=NodeKind.TACTIC)
        edge = DRGEdge(
            source="tactic:clean-commits",
            target="tactic:test-after",
            relation=Relation.REQUIRES,
        )
        graph = _graph([source, target], [edge])
        assert validate_graph(graph) == []


class TestAntiPatternNodeIsRejectedValidation:
    """INV-004 (reverse direction): an anti_pattern node must be rejected.

    :func:`_validate_rejects_targets` enforces the forward direction only
    (a ``rejects`` edge must land on an anti_pattern node). This mirrors
    that check in reverse: a node marked ``NodeKind.ANTI_PATTERN`` with zero
    inbound ``rejects`` edges is an orphaned "thing to avoid" that nothing
    actually avoids, and must be detected rather than pass silently.
    """

    def test_orphaned_anti_pattern_node_with_no_inbound_rejects_is_detected(
        self,
    ) -> None:
        """Red-first: a marked anti_pattern node nothing rejects must fail."""
        orphan = DRGNode(urn="anti_pattern:unreferenced-smell", kind=NodeKind.ANTI_PATTERN)
        graph = _graph([orphan], [])

        errors = validate_graph(graph)
        assert len(errors) == 1
        assert "anti_pattern:unreferenced-smell" in errors[0]

        with pytest.raises(DRGValidationError):
            assert_valid(graph)

    def test_anti_pattern_node_with_inbound_rejects_edge_passes(self) -> None:
        good = DRGNode(urn="tactic:clean-commits", kind=NodeKind.TACTIC)
        smell = DRGNode(urn="anti_pattern:force-push-shared-branch", kind=NodeKind.ANTI_PATTERN)
        edge = DRGEdge(
            source="tactic:clean-commits",
            target="anti_pattern:force-push-shared-branch",
            relation=Relation.REJECTS,
        )
        graph = _graph([good, smell], [edge])

        assert validate_graph(graph) == []
        assert_valid(graph)  # must not raise
