"""WP01/T005 — failing verification for the drupalling-dries DRG lineage.

Mission ``drupalling-dries-profile-01M28X69``. RED half of red-first
discipline: none of the ``drupalling-dries`` graph nodes/edges exist yet, so
every assertion below must fail for *absence* (empty edge lists / missing
node), never for an import or collection error.

Covers contract C-P2 (lineage resolves to the implementer persona) and C-P3
(directive/tactic edges minted from the profile's ``*-references``), per
``contracts/profile-contract.md`` and ``data-model.md`` E3/E7.

Endpoint form (C-002 / CLAUDE.md's "routing"/"primary" footgun sibling): both
edge endpoints must be ``<kind>:<id>`` with ``kind`` a real ``NodeKind``
member -- the shape ``urn:profile:...`` is refused at merge with
``unresolved_edge_endpoint`` and has, per CLAUDE.md, once silently dropped a
documented edge. This suite asserts the form explicitly rather than assuming
it.

Graph-loading idiom follows ``tests/doctrine/drg/test_builtin_graph_seam.py``
and ``tests/doctrine/drg/test_validator_profile_edges.py`` (the real shipped
built-in DRG via ``load_built_in_graph``, and ``DRGGraph.edges_from`` /
``.node_urns`` for queries -- never a hand-rolled parse of the fragments).
"""

from __future__ import annotations

import re

import pytest

from charter.offering.drg.loader import load_built_in_graph
from charter.offering.drg.models import DRGGraph, NodeKind, Relation

pytestmark = [pytest.mark.fast, pytest.mark.doctrine, pytest.mark.corpus]

_DRIES = "agent_profile:drupalling-dries"
_IMPLEMENTER_IVAN = "agent_profile:implementer-ivan"

# C-P3 / R-005: the inherited directive and tactic set.
_EXPECTED_DIRECTIVE_TARGETS = tuple(f"directive:DIRECTIVE_{code}" for code in ("010", "024", "025", "030", "034", "051"))
_EXPECTED_TACTIC_TARGETS = (
    "tactic:dependency-hygiene",
    "tactic:tdd-red-green-refactor",
    "tactic:supply-chain-install-safety",
    "tactic:bug-fixing-checklist",
)

# C-002: endpoint form is ``<kind>:<id>`` where kind is a real NodeKind member.
_URN_FORM = re.compile(r"^[a-z_]+:[A-Za-z0-9_.-]+$")


@pytest.fixture(scope="module")
def graph() -> DRGGraph:
    """The shipped built-in DRG -- the same seam every peer test in this
    directory uses (test_builtin_graph_seam.py, test_profile_suggests_delivery.py).
    """
    return load_built_in_graph()


class TestLineageEdge:
    """C-P2: exactly one ``specializes_from`` edge, targeting implementer-ivan."""

    def test_exactly_one_specializes_from_edge(self, graph: DRGGraph) -> None:
        # Arrange / Assumption-check: none beyond the shared fixture.
        # Act
        edges = graph.edges_from(_DRIES, Relation.SPECIALIZES_FROM)
        # Assert
        assert len(edges) == 1, f"expected exactly one specializes_from edge from {_DRIES!r}, got {edges}"

    def test_specializes_from_targets_implementer_ivan(self, graph: DRGGraph) -> None:
        # Arrange
        edges = graph.edges_from(_DRIES, Relation.SPECIALIZES_FROM)
        # Assumption-check
        assert edges, f"no specializes_from edges from {_DRIES!r} yet"
        # Act
        targets = [edge.target for edge in edges]
        # Assert
        assert targets == [_IMPLEMENTER_IVAN]

    def test_lineage_target_node_exists(self, graph: DRGGraph) -> None:
        # Arrange / Act
        node_urns = graph.node_urns()
        # Assert
        assert _IMPLEMENTER_IVAN in node_urns


class TestDirectiveAndTacticRequiresEdges:
    """C-P3: requires edges are minted from the profile's *-references."""

    @pytest.mark.parametrize("target", _EXPECTED_DIRECTIVE_TARGETS)
    def test_requires_edge_to_directive(self, graph: DRGGraph, target: str) -> None:
        # Act
        edges = graph.edges_from(_DRIES, Relation.REQUIRES)
        targets = {edge.target for edge in edges}
        # Assert
        assert target in targets, f"missing requires edge {_DRIES!r} -> {target!r}"

    @pytest.mark.parametrize("target", _EXPECTED_TACTIC_TARGETS)
    def test_requires_edge_to_tactic(self, graph: DRGGraph, target: str) -> None:
        # Act
        edges = graph.edges_from(_DRIES, Relation.REQUIRES)
        targets = {edge.target for edge in edges}
        # Assert
        assert target in targets, f"missing requires edge {_DRIES!r} -> {target!r}"

    def test_every_requires_edge_endpoint_resolves(self, graph: DRGGraph) -> None:
        """C-P3: every requires-edge target the profile declares exists as a real node."""
        # Arrange
        node_urns = graph.node_urns()
        # Assumption-check: the profile node itself must exist before its
        # outgoing edges can be meaningfully checked.
        assert _DRIES in node_urns, f"profile node {_DRIES!r} not found"
        # Act
        edges = graph.edges_from(_DRIES, Relation.REQUIRES)
        dangling = [edge.target for edge in edges if edge.target not in node_urns]
        # Assert
        assert dangling == [], f"requires edges with unresolved targets: {dangling}"


class TestEndpointFormAndAcyclicity:
    """C-002 endpoint form; C-P2 the specializes_from subgraph is a DAG."""

    def test_specializes_from_endpoints_use_kind_colon_id_form(self, graph: DRGGraph) -> None:
        # Arrange
        edges = graph.edges_from(_DRIES, Relation.SPECIALIZES_FROM)
        # Assumption-check
        assert edges, f"no specializes_from edges from {_DRIES!r} yet"
        # Act / Assert
        for edge in edges:
            assert _URN_FORM.match(edge.source), f"malformed source endpoint {edge.source!r}"
            assert _URN_FORM.match(edge.target), f"malformed target endpoint {edge.target!r}"
            source_kind = edge.source.split(":", 1)[0]
            target_kind = edge.target.split(":", 1)[0]
            assert source_kind == NodeKind.AGENT_PROFILE.value, f"source kind {source_kind!r} is not a NodeKind member"
            assert target_kind == NodeKind.AGENT_PROFILE.value, f"target kind {target_kind!r} is not a NodeKind member"

    def test_specializes_from_subgraph_remains_acyclic(self, graph: DRGGraph) -> None:
        """A leaf edge from drupalling-dries to implementer-ivan cannot introduce
        a cycle (I3.2) -- walk the whole specializes_from relation with a
        proper on-path (gray/black) DFS and confirm no node reaches itself.
        """
        # Arrange: build adjacency across the *whole* specializes_from relation,
        # not just the one edge under test -- a real cycle-detector, not a
        # single-hop shortcut.
        adjacency: dict[str, list[str]] = {}
        for edge in graph.edges:
            if edge.relation == Relation.SPECIALIZES_FROM:
                adjacency.setdefault(edge.source, []).append(edge.target)

        # Assumption-check: the shipped graph already carries other
        # specializes_from lineage (e.g. python-pedro -> implementer-ivan),
        # so the adjacency built above is non-empty even before this mission's
        # edge exists.
        assert adjacency, "no specializes_from edges found in the built-in graph at all"

        # Act: 3-color (white/gray/black) DFS -- a node revisited while still
        # on the current recursion path (gray) is a real cycle; a node merely
        # reached again via a different, already-finished path (black) is not.
        white, gray, black = 0, 1, 2
        color: dict[str, int] = {}
        cyclic_nodes: list[str] = []

        def _visit(node: str) -> bool:
            color[node] = gray
            for neighbor in adjacency.get(node, []):
                state = color.get(neighbor, white)
                if state == gray:
                    return True
                if state == white and _visit(neighbor):
                    return True
            color[node] = black
            return False

        for node in adjacency:
            if color.get(node, white) == white and _visit(node):
                cyclic_nodes.append(node)

        # Assert
        assert cyclic_nodes == [], f"specializes_from cycle detected reachable from: {cyclic_nodes}"
