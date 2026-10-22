"""Completeness gate for the DRG writer registry (mission ``doctrine-delivery-reachability``).

The registry (``specify_cli.drg_writers.registry``) enumerates every site that
persists ``DRGNode`` / ``DRGEdge`` / ``DRGGraph`` state, so a field added to a
model later cannot be silently dropped by a writer nobody remembered to update.

These tests **iterate the registry** — they carry no hand-written list of
writers. Verification is by *mutation*: a fully-populated instance carrying a
field the writer does not restate must survive every member, and the failure
message must name the offending member and the dropped field (contract W-5).

Subtask mapping:
- T004 — structural: the three tuples exist, carry the documented members, and
  every member has a unique, stable ``name``.
- T005 — W-1 / W-1a for the mapping writers (``project_drg`` was the unguarded
  one; ``rewrite_opposed_by`` restates its keys and drops a *novel* field).
- T006 — W-2 for the document writer.
- T007 — the subclass-based mutation fixture, iterated across every registry
  shape, asserting the failure names the member.
"""

from __future__ import annotations

import pytest
from pydantic import Field

from charter.offering.drg.migration import extractor
from charter.offering.drg.models import DRGEdge, DRGGraph, DRGNode, Relation
from specify_cli.drg_writers.registry import (
    DOCUMENT_WRITERS,
    MAPPING_WRITERS,
    MODEL_BRIDGES,
    MappingWriter,
)
# The tests and helpers shared with this suite's always-on lift live once, in
# ``tests/architectural/_lifted_drg_writers_registry_completeness.py`` (#5015); importing a test is what makes pytest collect it here.
from tests.architectural._lifted_drg_writers_registry_completeness import (
    _full_node,
    _expected_node_keys,
)
from tests.architectural._lifted_drg_writers_registry_completeness import (
    test_every_mapping_writer_emits_every_declared_node_field as test_every_mapping_writer_emits_every_declared_node_field,
)
from tests.architectural._lifted_drg_writers_registry_completeness import (
    test_every_mapping_writer_preserves_a_novel_node_field as test_every_mapping_writer_preserves_a_novel_node_field,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


# ---------------------------------------------------------------------------
# Fully-populated instances (W-1: totality is only meaningful when every field
# carries a value, so an omit-when-empty rule cannot make the gate vacuous).
# ---------------------------------------------------------------------------


def _full_edge() -> DRGEdge:
    return DRGEdge(
        source="tactic:a",
        target="tactic:b",
        relation=Relation.REQUIRES,
        when="a condition",
        reason="a rationale",
        provenance="org:acme",
    )


def _full_graph() -> DRGGraph:
    return DRGGraph(
        schema_version="1.0",
        generated_at="STATIC",
        generated_by="test",
        nodes=[_full_node()],
        edges=[_full_edge()],
    )


def _expected_edge_keys() -> set[str]:
    return set(DRGEdge.model_fields) - extractor.FIELDS_WITHHELD_FROM_GRAPH_OUTPUT


# ---------------------------------------------------------------------------
# Subclass mutation fixtures (T007). The models are not frozen but reject
# attribute injection and extra kwargs, so subclassing is the only route to a
# genuinely-novel field; ``DRGGraph`` does not re-validate, so a mutated
# node/edge survives into a graph and reaches the document writer.
# ---------------------------------------------------------------------------


class _EdgeWithNovelFields(DRGEdge):
    novel_scalar: str | None = "planted-edge-value"
    novel_empty: list[str] = Field(default_factory=list)


class _GraphWithNovelField(DRGGraph):
    novel_document_key: str = "planted-doc-value"


def _mutated_edge() -> _EdgeWithNovelFields:
    return _EdgeWithNovelFields(
        source="tactic:a", target="tactic:b", relation=Relation.REQUIRES,
        when="w", reason="r",
    )


# ---------------------------------------------------------------------------
# T004 — structural: the three shapes exist and are named
# ---------------------------------------------------------------------------


def test_the_registry_declares_three_distinct_writer_shapes() -> None:
    """One Protocol cannot hold all five sites; the registry has three tuples."""
    assert len(MAPPING_WRITERS) >= 3
    assert len(DOCUMENT_WRITERS) >= 1
    assert len(MODEL_BRIDGES) >= 1


def test_every_registry_member_carries_a_unique_stable_name() -> None:
    """W-5 failure messages name the member, so every member needs a name."""
    names = [w.name for w in MAPPING_WRITERS]
    names += [w.name for w in DOCUMENT_WRITERS]
    names += [w.name for w in MODEL_BRIDGES]
    assert all(isinstance(n, str) and n for n in names)
    assert len(names) == len(set(names)), f"duplicate registry member names: {names}"


def test_the_three_hand_restating_writers_are_all_registered() -> None:
    """The extractor, project_drg and rewrite_opposed_by mapping sites all join."""
    mapping_names = {w.name for w in MAPPING_WRITERS}
    assert any("extractor" in n for n in mapping_names)
    assert any("project_drg" in n for n in mapping_names)
    assert any("rewrite_opposed_by" in n for n in mapping_names)


# ---------------------------------------------------------------------------
# T005 — W-1: every mapping writer emits every declared field (fully populated)
# ---------------------------------------------------------------------------


def test_every_mapping_writer_emits_every_declared_edge_field() -> None:
    edge = _full_edge()
    for writer in MAPPING_WRITERS:
        emitted = set(writer.edge_to_mapping(edge))
        missing = _expected_edge_keys() - emitted
        assert not missing, f"{writer.name} dropped edge field(s) {missing}"


# ---------------------------------------------------------------------------
# T005 / T007 — W-1a: a novel field (populated AND empty) survives every writer
# ---------------------------------------------------------------------------


def test_every_mapping_writer_preserves_a_novel_edge_field() -> None:
    edge = _mutated_edge()
    for writer in MAPPING_WRITERS:
        emitted = set(writer.edge_to_mapping(edge))
        assert "novel_scalar" in emitted, f"{writer.name} dropped novel_scalar"
        assert "novel_empty" in emitted, (
            f"{writer.name} dropped novel_empty (the empty-value hole, W-1a)"
        )


# ---------------------------------------------------------------------------
# T006 — W-2: the document writer emits every DRGGraph field
# ---------------------------------------------------------------------------


def test_every_document_writer_emits_every_graph_field() -> None:
    graph = _full_graph()
    expected = set(DRGGraph.model_fields) - extractor.FIELDS_WITHHELD_FROM_GRAPH_OUTPUT
    for writer in DOCUMENT_WRITERS:
        emitted = set(writer.document_to_mapping(graph))
        missing = expected - emitted
        assert not missing, f"{writer.name} dropped document field(s) {missing}"


def test_every_document_writer_preserves_a_novel_graph_field() -> None:
    graph = _GraphWithNovelField(
        schema_version="1.0",
        generated_at="STATIC",
        generated_by="test",
        nodes=[_full_node()],
        edges=[_full_edge()],
    )
    for writer in DOCUMENT_WRITERS:
        emitted = set(writer.document_to_mapping(graph))
        assert "novel_document_key" in emitted, (
            f"{writer.name} dropped novel_document_key (W-2)"
        )


# ---------------------------------------------------------------------------
# T007 — the mutation is executable: reverting any writer's derivation reds
# this, naming the member. Modelled as an explicit per-member scan so the
# failure message is member-scoped (W-5), and it iterates the registry rather
# than enumerating writers inline.
# ---------------------------------------------------------------------------


def _node_drop_report(writer: MappingWriter, node: DRGNode, expected: set[str]) -> str | None:
    """Return a W-5 failure message naming *writer* + the dropped fields, or ``None``.

    Factored so the message format (member name + missing field set) is asserted
    by executable code rather than only living inside an f-string that fires on a
    real regression.
    """
    missing = expected - set(writer.node_to_mapping(node))
    if not missing:
        return None
    return f"{writer.name} dropped node field(s) {missing}"


class _DroppingWriter:
    """A deliberately-broken ``MappingWriter`` that restates keys and drops the rest."""

    name = "deliberately.broken.writer"

    def node_to_mapping(self, node: DRGNode) -> dict[str, object]:
        return {"urn": node.urn, "kind": node.kind.value}  # drops label + tags

    def edge_to_mapping(self, edge: DRGEdge) -> dict[str, object]:
        return {"source": edge.source, "target": edge.target}


def test_the_failure_message_names_the_member_and_the_missing_field() -> None:
    """W-5: a drop must produce a message naming the member and the field.

    Proven against a broken stub so the guarantee does not depend on a real
    writer being regressed. The live registry members must produce no report.
    """
    report = _node_drop_report(_DroppingWriter(), _full_node(), _expected_node_keys())
    assert report is not None
    assert "deliberately.broken.writer" in report
    assert "tags" in report or "label" in report


def test_no_live_registry_member_drops_a_node_field() -> None:
    """The same W-5 scan over the live registry yields no report (all derived)."""
    assert MAPPING_WRITERS  # non-empty, so the scan is not vacuous
    reports = [
        _node_drop_report(w, _full_node(), _expected_node_keys()) for w in MAPPING_WRITERS
    ]
    assert all(r is None for r in reports), [r for r in reports if r]
