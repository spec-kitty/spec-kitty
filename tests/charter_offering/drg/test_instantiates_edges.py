"""Coverage for the ``mission_type -> step -> template`` graph-back (WP06, FR-009/FR-011).

``extract_template_instantiation_edges`` (``charter.offering.drg.migration.extractor``)
mints a mission-qualified ``template:<mission>/<file>`` node per step-carried
``MissionStepTemplateRef`` and one ``action:<mission>/<step> --instantiates-->
template:<mission>/<file>`` edge per pair, consuming WP01's
``iter_template_refs`` (the sole traversal of ``MissionStep.template``, C-003)
rather than re-walking ``step.template`` independently.

This module pins:

1. **Positive edge assertion** -- every expected ``instantiates`` edge (one
   per shipped step carrying a ``template`` ref, N=8: software-dev's 2 +
   documentation/research/plan x {spec, plan}) exists in the shipped, freshly
   regenerated graph -- both source and target sides.
2. **Action-sourced landing** -- the edges are emitted with an ``action:``
   source URN, so they land in ``action.graph.yaml`` under the DD-8 per-kind
   sharding partition (source-node-kind determines fragment), never in
   ``template.graph.yaml``.
3. **Bare exemplars untouched** -- the 16 pre-existing un-mission-qualified
   ``template:<name>`` nodes (#2712) are wired only via their pre-existing
   ``procedure``/``tactic`` ``scope`` edges (never via ``instantiates``); this
   pass only ever mints mission-qualified URNs, so it cannot accidentally
   target one of them, and their shipped ``template.graph.yaml`` fragment
   keeps its ``edges: []`` (templates are a target-only node kind, DD-8).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.offering.drg.migration.extractor import (
    extract_template_instantiation_edges,
    generate_graph,
)
from charter.offering.drg.models import NodeKind, Relation

pytestmark = [pytest.mark.doctrine, pytest.mark.fast, pytest.mark.corpus]

# Relocated built-in pack root (mission relocate-builtin-doctrine-packs-01KYT87F):
# the shipped ``*.graph.yaml`` fragments now live under ``packs/built-in/``.
DOCTRINE_ROOT: Path = Path(__file__).resolve().parents[3] / "packs" / "built-in"

#: The expected ``(mission_type, step_id, template_file)`` triples, hand-pinned
#: against the shipped ``step.yaml`` authoring (independent of the extractor
#: under test -- a change to either side without updating the other must go
#: red). N=8 -- software-dev's 2 (specify, plan) + documentation/research/plan
#: x {spec-equivalent, plan-equivalent} steps.
_EXPECTED_TRIPLES: tuple[tuple[str, str, str], ...] = (
    ("documentation", "design", "documentation-plan-template.md"),
    ("documentation", "discover", "documentation-spec-template.md"),
    ("plan", "plan", "plan-plan-skeleton.md"),
    ("plan", "specify", "plan-spec-skeleton.md"),
    ("research", "methodology", "research-plan-template.md"),
    ("research", "scoping", "research-spec-template.md"),
    ("software-dev", "plan", "plan-template.md"),
    ("software-dev", "specify", "spec-template.md"),
)


def _expected_edges() -> set[tuple[str, str]]:
    return {
        (
            f"action:{mission_type}/{step_id}",
            f"template:{mission_type}/{template_file}",
        )
        for mission_type, step_id, template_file in _EXPECTED_TRIPLES
    }


class TestExtractTemplateInstantiationEdges:
    """Direct coverage of the new extractor pass (before graph composition)."""

    def test_mints_exactly_the_expected_triples(self) -> None:
        nodes, edges = extract_template_instantiation_edges(DOCTRINE_ROOT)

        assert len(_EXPECTED_TRIPLES) == 8
        assert len(nodes) == len(_EXPECTED_TRIPLES)
        assert len(edges) == len(_EXPECTED_TRIPLES)

        actual_edges = {(edge.source, edge.target) for edge in edges}
        assert actual_edges == _expected_edges()

        for edge in edges:
            assert edge.relation is Relation.INSTANTIATES

        for node in nodes:
            assert node.kind is NodeKind.TEMPLATE
            assert node.urn.startswith("template:")

    def test_edges_are_sorted_by_source_then_target(self) -> None:
        _nodes, edges = extract_template_instantiation_edges(DOCTRINE_ROOT)
        pairs = [(edge.source, edge.target) for edge in edges]
        assert pairs == sorted(pairs)


class TestShippedGraphCarriesInstantiatesEdges:
    """Positive assertion against the fully-composed, freshly regenerated graph."""

    def test_every_expected_instantiates_edge_exists(self, tmp_path: Path) -> None:
        graph = generate_graph(DOCTRINE_ROOT, tmp_path / "graph.yaml")

        node_urns = {node.urn for node in graph.nodes}
        actual_edges = {
            (edge.source, edge.target)
            for edge in graph.edges
            if edge.relation is Relation.INSTANTIATES
        }

        expected = _expected_edges()
        assert actual_edges == expected

        for source_urn, target_urn in expected:
            assert source_urn in node_urns, f"missing action node {source_urn}"
            assert target_urn in node_urns, f"missing template node {target_urn}"

    def test_instantiates_edges_are_action_sourced(self, tmp_path: Path) -> None:
        # DD-8 sharding partitions edges by source-node kind, so an
        # ``instantiates`` edge must have an ``action:`` source to land in
        # ``action.graph.yaml`` (not ``template.graph.yaml``, which is
        # nodes-only for this pass).
        graph = generate_graph(DOCTRINE_ROOT, tmp_path / "graph.yaml")

        instantiates_edges = [
            edge for edge in graph.edges if edge.relation is Relation.INSTANTIATES
        ]
        assert instantiates_edges, "expected at least one instantiates edge"
        for edge in instantiates_edges:
            assert edge.source.startswith("action:")
            assert edge.target.startswith("template:")


class TestBareTemplateExemplarsUntouched:
    """The 16 pre-existing un-mission-qualified template nodes are never an
    ``instantiates`` target, and their node count is unchanged by this pass."""

    def test_bare_exemplar_node_count_unchanged(self, tmp_path: Path) -> None:
        graph = generate_graph(DOCTRINE_ROOT, tmp_path / "graph.yaml")

        bare_template_urns = {
            node.urn
            for node in graph.nodes
            if node.kind is NodeKind.TEMPLATE and "/" not in node.urn.split(":", 1)[1]
        }
        assert len(bare_template_urns) == 16

    def test_bare_exemplars_are_never_an_instantiates_target(
        self, tmp_path: Path
    ) -> None:
        graph = generate_graph(DOCTRINE_ROOT, tmp_path / "graph.yaml")

        bare_template_urns = {
            node.urn
            for node in graph.nodes
            if node.kind is NodeKind.TEMPLATE and "/" not in node.urn.split(":", 1)[1]
        }
        instantiates_targets = {
            edge.target for edge in graph.edges if edge.relation is Relation.INSTANTIATES
        }
        assert bare_template_urns.isdisjoint(instantiates_targets)

    def test_shipped_template_fragment_has_no_edges(self) -> None:
        # DD-8: ``template`` is a target-only node kind -- its fragment carries
        # nodes only, regardless of how many other kinds target those nodes.
        fragment_path = DOCTRINE_ROOT / "template.graph.yaml"
        text = fragment_path.read_text(encoding="utf-8")
        assert text.rstrip().endswith("edges: []")
