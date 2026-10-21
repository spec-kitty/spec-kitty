"""The cascade walk stops at a deactivated artifact (FR-010/FR-011, operator ruling ``cascade_walk_through_denied``).

Engine-level and pure (synthetic graphs). Pins data-model.md §7: a denied node
is recorded and not expanded; a node reachable over another non-denied path is
still activated; scope is decided before deny; ``include_deactivated`` restores
the full walk; and every node of the full walk lands in exactly one bucket.
"""

from __future__ import annotations

import random

import pytest

from charter.activation.cascade import (
    CascadeScope,
    ReferencedArtifact,
    cascade_activation_targets,
    referenced_but_not_cascaded,
)
from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.drg.models import DRGEdge, DRGGraph, DRGNode, NodeKind, Relation

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_P = "directive:P"
_C = "tactic:C"
_G = "procedure:G"
_S = "styleguide:S"


def _graph(nodes: list[tuple[str, NodeKind]], edges: list[tuple[str, str, Relation]]) -> DRGGraph:
    return DRGGraph(
        schema_version="1.0",
        generated_at="2026-10-20T00:00:00Z",
        generated_by="test",
        nodes=[DRGNode(urn=urn, kind=kind) for urn, kind in nodes],
        edges=[DRGEdge(source=src, target=tgt, relation=rel) for src, tgt, rel in edges],
    )


def _chain(*extra: tuple[str, str, Relation]) -> DRGGraph:
    """``P -requires-> C -requires-> G`` plus ``P -suggests-> S``, plus *extra* edges."""
    return _graph(
        [(_P, NodeKind.DIRECTIVE), (_C, NodeKind.TACTIC), (_G, NodeKind.PROCEDURE), (_S, NodeKind.STYLEGUIDE)],
        [(_P, _C, Relation.REQUIRES), (_C, _G, Relation.REQUIRES), (_P, _S, Relation.SUGGESTS), *extra],
    )


def test_the_walk_stops_at_a_denied_node() -> None:
    result = cascade_activation_targets(_chain(), _P, CascadeScope.all(), deactivated_urns=frozenset({_C}))

    assert result.activated == {"styleguide": ["S"]}
    assert result.skipped_deactivated == {
        "tactic": [ReferencedArtifact(ArtifactKind.TACTIC, "C", _C, via_requires=True, required_by=(_P,))],
    }
    assert result.unreached_behind_deactivated == {"procedure": ["G"]}


def test_a_node_reachable_over_another_path_is_still_activated() -> None:
    result = cascade_activation_targets(_chain((_P, _G, Relation.SUGGESTS)), _P, CascadeScope.all(), deactivated_urns=frozenset({_C}))

    assert result.activated == {"procedure": ["G"], "styleguide": ["S"]}
    assert result.unreached_behind_deactivated == {}
    assert list(result.skipped_deactivated) == ["tactic"]


def test_a_suggested_denied_node_is_not_flagged_as_required() -> None:
    graph = _graph([(_P, NodeKind.DIRECTIVE), (_C, NodeKind.TACTIC)], [(_P, _C, Relation.SUGGESTS)])

    result = cascade_activation_targets(graph, _P, CascadeScope.all(), deactivated_urns=frozenset({_C}))

    assert result.skipped_deactivated == {"tactic": [ReferencedArtifact(ArtifactKind.TACTIC, "C", _C)]}


def test_scope_is_decided_before_deny() -> None:
    scope = CascadeScope(kinds=frozenset({ArtifactKind.STYLEGUIDE, ArtifactKind.PROCEDURE}))

    result = cascade_activation_targets(_chain(), _P, scope, deactivated_urns=frozenset({_C}))

    assert result.skipped_by_scope == {"tactic": ["C"]}
    assert result.skipped_deactivated == {}
    assert result.unreached_behind_deactivated == {"procedure": ["G"]}
    assert result.activated == {"styleguide": ["S"]}


def test_include_deactivated_restores_the_full_walk() -> None:
    result = cascade_activation_targets(_chain(), _P, CascadeScope.all(), deactivated_urns=frozenset({_C}), include_deactivated=True)

    assert result.activated == {"procedure": ["G"], "styleguide": ["S"], "tactic": ["C"]}
    assert result.skipped_deactivated == {}
    assert result.unreached_behind_deactivated == {}


def test_without_a_deny_set_the_result_is_unchanged() -> None:
    assert cascade_activation_targets(_chain(), _P, CascadeScope.all()) == cascade_activation_targets(
        _chain(), _P, CascadeScope.all(), deactivated_urns=frozenset()
    )


def test_a_denied_node_behind_a_denied_node_is_reported_deactivated_not_unreached() -> None:
    result = cascade_activation_targets(_chain(), _P, CascadeScope.all(), deactivated_urns=frozenset({_C, _G}))

    assert result.unreached_behind_deactivated == {}
    assert result.skipped_deactivated["procedure"] == [ReferencedArtifact(ArtifactKind.PROCEDURE, "G", _G)]


def test_the_no_cascade_report_lists_denied_nodes_as_deactivated() -> None:
    report = referenced_but_not_cascaded(_chain(), _P, deactivated_urns=frozenset({_C}))

    assert report.skipped == {"procedure": ["G"], "styleguide": ["S"]}
    assert report.deactivated == {"tactic": ["C"]}
    assert report.has_skipped


# --------------------------------------------------------------------------- #
# Partition invariant over seeded random DAGs
# --------------------------------------------------------------------------- #

_KINDS = (NodeKind.DIRECTIVE, NodeKind.TACTIC, NodeKind.PROCEDURE, NodeKind.STYLEGUIDE, NodeKind.TEMPLATE)
_RELATIONS = (Relation.REQUIRES, Relation.SUGGESTS, Relation.SCOPE)


def _random_case(seed: int) -> tuple[DRGGraph, frozenset[str], CascadeScope]:
    rng = random.Random(seed)
    urns = [f"{rng.choice(_KINDS).value}:n{index}" for index in range(14)]
    nodes = [(urn, NodeKind(urn.split(":", 1)[0])) for urn in urns]
    edges = [(urns[i], urns[j], rng.choice(_RELATIONS)) for i in range(len(urns)) for j in range(i + 1, len(urns)) if rng.random() < 0.18]
    denied = frozenset(urn for urn in urns[1:] if rng.random() < 0.25)
    kinds = frozenset(rng.sample([ArtifactKind.TACTIC, ArtifactKind.PROCEDURE, ArtifactKind.STYLEGUIDE, ArtifactKind.DIRECTIVE], 3))
    scope = CascadeScope.all() if seed % 2 else CascadeScope(kinds=kinds)
    return _graph(nodes, edges), denied, scope


def _full_walk(graph: DRGGraph, source: str, avoid: frozenset[str] = frozenset()) -> set[str]:
    """Nodes reachable from *source*; an *avoid* node is reached but never expanded (an independent oracle)."""
    seen, frontier = {source}, [source]
    while frontier:
        current = frontier.pop()
        for edge in graph.edges:
            if edge.source == current and edge.target not in seen:
                seen.add(edge.target)
                if edge.target not in avoid:
                    frontier.append(edge.target)
    return seen - {source}


@pytest.mark.parametrize("seed", range(12))
def test_every_node_of_the_full_walk_lands_in_exactly_one_bucket(seed: int) -> None:
    graph, denied, scope = _random_case(seed)
    source = graph.nodes[0].urn

    result = cascade_activation_targets(graph, source, scope, deactivated_urns=denied)

    buckets = [
        {f"{kind}:{item}" for kind, ids in result.activated.items() for item in ids},
        {f"{kind}:{item}" for kind, ids in result.skipped_by_scope.items() for item in ids},
        {ref.urn for refs in result.skipped_deactivated.values() for ref in refs},
        {f"{kind}:{item}" for kind, ids in result.unreached_behind_deactivated.items() for item in ids},
        {f"{kind}:{item}" for kind, ids in result.not_cascaded_kind_filtered.items() for item in ids},
    ]
    assert sum(len(bucket) for bucket in buckets) == len(set().union(*buckets))  # pairwise disjoint
    assert set().union(*buckets) == _full_walk(graph, source)
    # Per-node placement against an independent oracle: what a non-denied path reaches.
    open_reach = _full_walk(graph, source, avoid=denied) - denied
    activated, out_of_scope, deactivated, unreached, filtered = buckets
    assert activated <= open_reach
    assert not unreached & open_reach
    assert deactivated <= denied
    for urn in open_reach - out_of_scope - filtered:
        assert urn in activated, urn
