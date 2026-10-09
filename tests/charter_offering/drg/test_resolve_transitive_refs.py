"""Tests for :func:`charter.offering.drg.query.resolve_transitive_refs`.

Covers all 7 contract dimensions from
``kitty-specs/excise-doctrine-curation-and-inline-references-01KP54J6/contracts/resolve-transitive-refs.contract.md``:

1. Deterministic output (lists sorted lexicographically).
2. Empty start set.
3. Unknown starting URN lands in ``unresolved``.
4. Edge-kind filter restricts traversal.
5. Bucketing by kind (and URN-prefix stripping).
6. Behavioral equivalence with the legacy transitive resolver on a graph
   whose edges mirror pre-WP02 ``tactic_refs`` chains. Uses a synthetic
   doctrine service because WP02 already removed the ``tactic_refs``
   attribute from :class:`charter.offering.directives.models.Directive`, so the
   legacy resolver can no longer follow shipped inline refs.
7. ``max_depth`` forwarded correctly to :func:`walk_edges`.
"""

from __future__ import annotations

import pytest

from charter.offering.drg.models import DRGEdge, DRGGraph, DRGNode, NodeKind, Relation
from charter.offering.drg.query import (
    ResolveTransitiveRefsResult,
    resolve_transitive_refs,
)
from charter.offering.drg.validator import assert_valid

pytestmark = [pytest.mark.doctrine, pytest.mark.fast, pytest.mark.corpus]


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
        generated_at="2026-04-14T00:00:00Z",
        generated_by="test",
        nodes=[DRGNode(urn=urn, kind=kind) for urn, kind in nodes],
        edges=[
            DRGEdge(source=src, target=tgt, relation=rel)
            for src, tgt, rel in edges
        ],
    )


# ---------------------------------------------------------------------------
# Dimension 1 -- deterministic, sorted output
# ---------------------------------------------------------------------------


def test_results_are_lexicographically_sorted() -> None:
    """Per-kind lists are sorted regardless of graph or edge insertion order."""
    graph = _make_graph(
        nodes=[
            ("directive:root", NodeKind.DIRECTIVE),
            ("tactic:zeta", NodeKind.TACTIC),
            ("tactic:alpha", NodeKind.TACTIC),
            ("tactic:mu", NodeKind.TACTIC),
        ],
        edges=[
            ("directive:root", "tactic:zeta", Relation.REQUIRES),
            ("directive:root", "tactic:alpha", Relation.REQUIRES),
            ("directive:root", "tactic:mu", Relation.REQUIRES),
        ],
    )
    assert_valid(graph)

    result = resolve_transitive_refs(
        graph,
        start_urns={"directive:root"},
        relations={Relation.REQUIRES},
    )

    assert result.tactics == ["alpha", "mu", "zeta"]
    assert result.directives == ["root"]


def test_same_input_same_output() -> None:
    graph = _make_graph(
        nodes=[
            ("directive:a", NodeKind.DIRECTIVE),
            ("tactic:b", NodeKind.TACTIC),
        ],
        edges=[("directive:a", "tactic:b", Relation.REQUIRES)],
    )
    assert_valid(graph)
    first = resolve_transitive_refs(
        graph, start_urns={"directive:a"}, relations={Relation.REQUIRES}
    )
    second = resolve_transitive_refs(
        graph, start_urns={"directive:a"}, relations={Relation.REQUIRES}
    )
    assert first == second


# ---------------------------------------------------------------------------
# Dimension 2 -- empty start set
# ---------------------------------------------------------------------------


def test_empty_start_set_returns_empty_result() -> None:
    graph = _make_graph(
        nodes=[("directive:a", NodeKind.DIRECTIVE)],
        edges=[],
    )
    result = resolve_transitive_refs(
        graph, start_urns=set(), relations={Relation.REQUIRES}
    )
    assert result == ResolveTransitiveRefsResult()
    assert result.is_complete


# ---------------------------------------------------------------------------
# Dimension 3 -- unknown start URN lands in unresolved (no raise)
# ---------------------------------------------------------------------------


def test_unknown_start_urn_records_unresolved_and_does_not_raise() -> None:
    graph = _make_graph(
        nodes=[("directive:known", NodeKind.DIRECTIVE)],
        edges=[],
    )
    result = resolve_transitive_refs(
        graph,
        start_urns={"directive:missing"},
        relations={Relation.REQUIRES},
    )
    assert ("directive:missing", "directive:missing") in result.unresolved
    assert not result.is_complete
    assert result.directives == []


# ---------------------------------------------------------------------------
# Dimension 4 -- edge-kind filter
# ---------------------------------------------------------------------------


def test_edge_kind_filter_restricts_traversal() -> None:
    """``{REQUIRES: A->B, SUGGESTS: A->C, SCOPE: A->D}`` with ``{REQUIRES}`` -> only ``B``."""
    graph = _make_graph(
        nodes=[
            ("directive:A", NodeKind.DIRECTIVE),
            ("tactic:B", NodeKind.TACTIC),
            ("tactic:C", NodeKind.TACTIC),
            ("tactic:D", NodeKind.TACTIC),
        ],
        edges=[
            ("directive:A", "tactic:B", Relation.REQUIRES),
            ("directive:A", "tactic:C", Relation.SUGGESTS),
            ("directive:A", "tactic:D", Relation.SCOPE),
        ],
    )
    assert_valid(graph)

    result = resolve_transitive_refs(
        graph,
        start_urns={"directive:A"},
        relations={Relation.REQUIRES},
    )
    assert result.tactics == ["B"]


def test_multi_relation_filter_combines() -> None:
    """``{REQUIRES, SUGGESTS}`` walks both kinds but not ``SCOPE``."""
    graph = _make_graph(
        nodes=[
            ("directive:A", NodeKind.DIRECTIVE),
            ("tactic:B", NodeKind.TACTIC),
            ("tactic:C", NodeKind.TACTIC),
            ("tactic:D", NodeKind.TACTIC),
        ],
        edges=[
            ("directive:A", "tactic:B", Relation.REQUIRES),
            ("directive:A", "tactic:C", Relation.SUGGESTS),
            ("directive:A", "tactic:D", Relation.SCOPE),
        ],
    )
    assert_valid(graph)
    result = resolve_transitive_refs(
        graph,
        start_urns={"directive:A"},
        relations={Relation.REQUIRES, Relation.SUGGESTS},
    )
    assert result.tactics == ["B", "C"]


# ---------------------------------------------------------------------------
# Dimension 5 -- bucketing by kind, prefix stripping
# ---------------------------------------------------------------------------


def test_bucketing_by_kind_and_prefix_stripping() -> None:
    """Visited URNs land in the correct per-kind lists; URN prefix stripped."""
    graph = _make_graph(
        nodes=[
            ("directive:D1", NodeKind.DIRECTIVE),
            ("tactic:T1", NodeKind.TACTIC),
            ("paradigm:P1", NodeKind.PARADIGM),
            ("styleguide:S1", NodeKind.STYLEGUIDE),
            ("toolguide:TG1", NodeKind.TOOLGUIDE),
            ("procedure:PR1", NodeKind.PROCEDURE),
            ("agent_profile:AP1", NodeKind.AGENT_PROFILE),
            ("mission_step_contract:MSC1", NodeKind.MISSION_STEP_CONTRACT),
            ("template:TPL1", NodeKind.TEMPLATE),
        ],
        edges=[
            ("directive:D1", "tactic:T1", Relation.REQUIRES),
            ("directive:D1", "paradigm:P1", Relation.REQUIRES),
            ("directive:D1", "styleguide:S1", Relation.REQUIRES),
            ("directive:D1", "toolguide:TG1", Relation.REQUIRES),
            ("directive:D1", "procedure:PR1", Relation.REQUIRES),
            ("directive:D1", "agent_profile:AP1", Relation.REQUIRES),
            ("directive:D1", "mission_step_contract:MSC1", Relation.REQUIRES),
            ("directive:D1", "template:TPL1", Relation.REQUIRES),
        ],
    )
    assert_valid(graph)

    result = resolve_transitive_refs(
        graph,
        start_urns={"directive:D1"},
        relations={Relation.REQUIRES},
    )
    assert result.directives == ["D1"]
    assert result.tactics == ["T1"]
    assert result.paradigms == ["P1"]
    assert result.styleguides == ["S1"]
    assert result.toolguides == ["TG1"]
    assert result.procedures == ["PR1"]
    assert result.agent_profiles == ["AP1"]
    assert result.mission_step_contracts == ["MSC1"]
    assert result.templates == ["TPL1"]
    assert result.is_complete


# ---------------------------------------------------------------------------
# Dimension 6 -- behavioral equivalence with the legacy resolver
# ---------------------------------------------------------------------------
#
# The pre-WP03 transitive-reference helper has been deleted in T017 and
# the Phase 0 migration extractor has already mapped every inline-reference
# edge into the DRG as a ``requires`` edge (WP02). We therefore evaluate
# the R-2 equivalence contract by asserting the DRG walk output matches a
# hand-computed expected bucketed set on topologies that mirror the
# pre-WP02 inline-reference shape. This preserves the coverage intent
# without depending on deleted legacy code.


def test_behavioral_equivalence_directive_with_tactic_refs() -> None:
    """DRG walk on a pre-WP02-shaped topology (directive -> tactics via
    REQUIRES) produces the expected bucketed output."""
    graph = _make_graph(
        nodes=[
            ("directive:D", NodeKind.DIRECTIVE),
            ("tactic:T1", NodeKind.TACTIC),
            ("tactic:T2", NodeKind.TACTIC),
        ],
        edges=[
            ("directive:D", "tactic:T1", Relation.REQUIRES),
            ("directive:D", "tactic:T2", Relation.REQUIRES),
        ],
    )
    assert_valid(graph)

    drg = resolve_transitive_refs(
        graph,
        start_urns={"directive:D"},
        relations={Relation.REQUIRES, Relation.SUGGESTS},
    )

    # Expected values are what the legacy resolver would have produced on
    # the identical topology expressed via pre-WP02 inline `tactic_refs`.
    assert drg.directives == ["D"]
    assert drg.tactics == ["T1", "T2"]
    assert drg.styleguides == []
    assert drg.toolguides == []
    assert drg.procedures == []
    assert drg.is_complete


def test_behavioral_equivalence_multi_kind_chain() -> None:
    """Chained pre-WP02 topology across multiple directives produces the
    correct union of per-kind buckets."""
    graph = _make_graph(
        nodes=[
            ("directive:D1", NodeKind.DIRECTIVE),
            ("directive:D2", NodeKind.DIRECTIVE),
            ("tactic:T1", NodeKind.TACTIC),
            ("tactic:T2", NodeKind.TACTIC),
            ("styleguide:S1", NodeKind.STYLEGUIDE),
        ],
        edges=[
            ("directive:D1", "tactic:T1", Relation.REQUIRES),
            ("directive:D2", "tactic:T2", Relation.REQUIRES),
            ("tactic:T1", "styleguide:S1", Relation.REQUIRES),
        ],
    )
    assert_valid(graph)

    drg = resolve_transitive_refs(
        graph,
        start_urns={"directive:D1", "directive:D2"},
        relations={Relation.REQUIRES, Relation.SUGGESTS},
    )
    assert drg.directives == ["D1", "D2"]
    assert drg.tactics == ["T1", "T2"]
    assert drg.styleguides == ["S1"]
    assert drg.is_complete


def test_behavioral_equivalence_against_shipped_graph_is_consistent(
    built_in_graph: DRGGraph,
) -> None:
    """Sanity check on the shipped graph: the DRG walk from every directive
    URN produces a deterministic bucketed result and never stores unresolved
    edges (``assert_valid`` guarantees that)."""
    merged = built_in_graph
    assert_valid(merged)

    directive_urns = [n.urn for n in merged.nodes if n.kind == NodeKind.DIRECTIVE]
    assert directive_urns, "shipped graph must contain at least one directive"

    result = resolve_transitive_refs(
        merged,
        start_urns=set(directive_urns),
        relations={Relation.REQUIRES, Relation.SUGGESTS},
    )
    assert result.is_complete, f"unresolved on shipped graph: {result.unresolved}"
    # Every directive starts out in its own bucket.
    assert set(result.directives) == {urn.split(":", 1)[1] for urn in directive_urns}


# ---------------------------------------------------------------------------
# Dimension 7 -- max_depth forwarding
# ---------------------------------------------------------------------------


def test_max_depth_forwarding_excludes_deep_nodes() -> None:
    """``max_depth=1`` excludes depth-2 nodes."""
    graph = _make_graph(
        nodes=[
            ("directive:A", NodeKind.DIRECTIVE),
            ("tactic:B", NodeKind.TACTIC),
            ("tactic:C", NodeKind.TACTIC),
        ],
        edges=[
            ("directive:A", "tactic:B", Relation.REQUIRES),
            ("tactic:B", "tactic:C", Relation.REQUIRES),
        ],
    )
    assert_valid(graph)

    shallow = resolve_transitive_refs(
        graph,
        start_urns={"directive:A"},
        relations={Relation.REQUIRES},
        max_depth=1,
    )
    deep = resolve_transitive_refs(
        graph,
        start_urns={"directive:A"},
        relations={Relation.REQUIRES},
        max_depth=None,
    )

    assert shallow.tactics == ["B"]
    assert deep.tactics == ["B", "C"]


@pytest.mark.parametrize("max_depth", [0, 1, 2, None])
def test_max_depth_monotonic(max_depth: int | None) -> None:
    """Increasing depth only adds nodes, never removes them."""
    graph = _make_graph(
        nodes=[
            ("directive:A", NodeKind.DIRECTIVE),
            ("tactic:B", NodeKind.TACTIC),
            ("tactic:C", NodeKind.TACTIC),
        ],
        edges=[
            ("directive:A", "tactic:B", Relation.REQUIRES),
            ("tactic:B", "tactic:C", Relation.REQUIRES),
        ],
    )
    result = resolve_transitive_refs(
        graph,
        start_urns={"directive:A"},
        relations={Relation.REQUIRES},
        max_depth=max_depth,
    )
    # At depth 0: only the start node; depth 1: + B; depth 2 / None: + C.
    if max_depth == 0:
        assert result.tactics == []
    elif max_depth == 1:
        assert result.tactics == ["B"]
    else:
        assert result.tactics == ["B", "C"]
