"""Tests for FR-009 tension-arbiter annotation on ``resolve_context`` (WP02).

WP02 of mission ``governance-at-the-gate``: ``resolve_context`` (and the
``_ActionGovernanceBundle`` it feeds) gains two additive, trailing, hashable
fields -- ``tension_arbiters`` and ``unarbitrated_tensions`` -- surfacing
``reconciles_tension``/``in_tension_with`` edges reachable from an action's
resolved scope, without a second graph walk (spec.md FR-009, NFR-003,
NFR-004; tasks.md WP02).

Covers:

- T1 (red-first): a delivered bundle whose action-scope pulls in
  ``DIRECTIVE_024`` + ``DIRECTIVE_025`` (mirroring the real
  ``024-locality-of-change`` / ``025-boy-scout-rule`` /
  ``reconcile-change-scope-tensions`` corpus edges, see
  ``packs/built-in/directives/reconcile-change-scope-tensions.directive.yaml``
  and ``src/charter/offering/drg/migration/hand_authored_overlay.py``)
  produces ``tension_arbiters`` mapping the reconciler to both sides, while a
  declared ``in_tension_with`` pair with no reachable reconciler surfaces in
  ``unarbitrated_tensions``.
- The ``in_tension_with`` edge is queried regardless of which endpoint the
  graph stores as ``source`` (the relation is symmetric, C-002 in
  ``models.py``'s ``Relation`` docstring).
- A reconciler need not itself be in the action's resolved scope to
  arbitrate a pair that is (SC-008: "a delivered bundle ... carries its
  reconciler").
- Both new fields are hashable tuples (not dict/list), preserving
  ``ResolvedContext``'s frozen-dataclass auto-``__hash__`` (brownfield
  constraint, tasks.md WP02 T2).
- The no-tension-in-scope case is unchanged: both fields default to ``()``
  and pre-existing artifact/glossary resolution is untouched (NFR-003).
"""

from __future__ import annotations

import pytest

from charter.offering.drg.models import DRGEdge, DRGGraph, DRGNode, NodeKind, Relation
from charter.offering.drg.query import ResolvedContext, resolve_context

pytestmark = [pytest.mark.doctrine, pytest.mark.fast]


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
        edges=[DRGEdge(source=src, target=tgt, relation=rel) for src, tgt, rel in edges],
    )


_ACTION = "action:software-dev/implement"
_DIRECTIVE_024 = "directive:DIRECTIVE_024"
_DIRECTIVE_025 = "directive:DIRECTIVE_025"
_RECONCILER = "directive:RECONCILE_CHANGE_SCOPE_TENSIONS"
_UNARBITRATED_A = "directive:DIRECTIVE_TENSION_A"
_UNARBITRATED_B = "directive:DIRECTIVE_TENSION_B"


def _tension_graph() -> DRGGraph:
    """Mirrors the real corpus shape: a reconciled pair + an unreconciled pair.

    ``_RECONCILER`` is deliberately NOT scoped from ``_ACTION`` -- it is
    reachable only through its ``reconciles_tension`` edges, proving a
    reconciler need not itself be in the action's resolved scope to
    arbitrate a pair that is (SC-008).
    """
    return _make_graph(
        nodes=[
            (_ACTION, NodeKind.ACTION),
            (_DIRECTIVE_024, NodeKind.DIRECTIVE),
            (_DIRECTIVE_025, NodeKind.DIRECTIVE),
            (_RECONCILER, NodeKind.DIRECTIVE),
            (_UNARBITRATED_A, NodeKind.DIRECTIVE),
            (_UNARBITRATED_B, NodeKind.DIRECTIVE),
        ],
        edges=[
            (_ACTION, _DIRECTIVE_024, Relation.SCOPE),
            (_ACTION, _DIRECTIVE_025, Relation.SCOPE),
            (_ACTION, _UNARBITRATED_A, Relation.SCOPE),
            (_ACTION, _UNARBITRATED_B, Relation.SCOPE),
            (_DIRECTIVE_024, _DIRECTIVE_025, Relation.IN_TENSION_WITH),
            (_UNARBITRATED_A, _UNARBITRATED_B, Relation.IN_TENSION_WITH),
            (_RECONCILER, _DIRECTIVE_024, Relation.RECONCILES_TENSION),
            (_RECONCILER, _DIRECTIVE_025, Relation.RECONCILES_TENSION),
        ],
    )


def test_reconciled_pair_maps_to_its_arbiter() -> None:
    ctx = resolve_context(_tension_graph(), _ACTION, depth=2)
    assert ctx.tension_arbiters == ((_RECONCILER, (_DIRECTIVE_024, _DIRECTIVE_025)),)


def test_unreconciled_pair_surfaces_in_unarbitrated_tensions() -> None:
    ctx = resolve_context(_tension_graph(), _ACTION, depth=2)
    assert ctx.unarbitrated_tensions == ((_UNARBITRATED_A, _UNARBITRATED_B),)


def test_reconciled_pair_absent_from_unarbitrated_tensions() -> None:
    ctx = resolve_context(_tension_graph(), _ACTION, depth=2)
    for pair in ctx.unarbitrated_tensions:
        assert _DIRECTIVE_024 not in pair
        assert _DIRECTIVE_025 not in pair


def test_unreconciled_pair_absent_from_tension_arbiters() -> None:
    ctx = resolve_context(_tension_graph(), _ACTION, depth=2)
    arbitrated = {urn for _arbiter, urns in ctx.tension_arbiters for urn in urns}
    assert _UNARBITRATED_A not in arbitrated
    assert _UNARBITRATED_B not in arbitrated


def test_tension_pair_with_out_of_scope_endpoint_is_excluded() -> None:
    """In-scope filter: a declared tension whose partner is NOT resolved from the
    action appears in NEITHER field (the ``edge.<endpoint> in all_artifacts``
    guard). ``in_tension_with`` is not a scope-bearing relation, so the partner is
    never pulled into the delivered bundle. Closes the WP02-review MINOR: the
    negative branch of the in-scope filter was previously untested."""
    out_of_scope = "directive:DIRECTIVE_OUT_OF_SCOPE"
    graph = _make_graph(
        nodes=[
            (_ACTION, NodeKind.ACTION),
            (_DIRECTIVE_024, NodeKind.DIRECTIVE),
            (out_of_scope, NodeKind.DIRECTIVE),
        ],
        edges=[
            (_ACTION, _DIRECTIVE_024, Relation.SCOPE),
            (_DIRECTIVE_024, out_of_scope, Relation.IN_TENSION_WITH),
        ],
    )
    ctx = resolve_context(graph, _ACTION, depth=2)
    assert ctx.tension_arbiters == ()
    assert ctx.unarbitrated_tensions == ()


def test_arbiter_need_not_be_in_action_scope() -> None:
    """SC-008: the reconciler bridges a co-delivered pair even though it is
    itself unreachable from the action node by ``scope``/``requires``/``suggests``.
    """
    ctx = resolve_context(_tension_graph(), _ACTION, depth=2)
    assert _RECONCILER not in ctx.artifact_urns
    assert ctx.tension_arbiters[0][0] == _RECONCILER


def test_in_tension_with_queried_regardless_of_edge_direction() -> None:
    """``in_tension_with`` is symmetric and stored as one canonical edge
    (lexicographically-smaller URN as source, per ``Relation``'s docstring).
    Reversing which endpoint is authored as ``source``/``target`` must not
    change the resolved annotation.
    """
    reversed_direction = _make_graph(
        nodes=[
            (_ACTION, NodeKind.ACTION),
            (_DIRECTIVE_024, NodeKind.DIRECTIVE),
            (_DIRECTIVE_025, NodeKind.DIRECTIVE),
            (_RECONCILER, NodeKind.DIRECTIVE),
        ],
        edges=[
            (_ACTION, _DIRECTIVE_024, Relation.SCOPE),
            (_ACTION, _DIRECTIVE_025, Relation.SCOPE),
            # Authored with the opposite source/target ordering.
            (_DIRECTIVE_025, _DIRECTIVE_024, Relation.IN_TENSION_WITH),
            (_RECONCILER, _DIRECTIVE_024, Relation.RECONCILES_TENSION),
            (_RECONCILER, _DIRECTIVE_025, Relation.RECONCILES_TENSION),
        ],
    )
    ctx = resolve_context(reversed_direction, _ACTION, depth=2)
    assert ctx.tension_arbiters == ((_RECONCILER, (_DIRECTIVE_024, _DIRECTIVE_025)),)


def test_half_reconciled_pair_stays_unarbitrated() -> None:
    """A reconciler bridging only ONE side of the pair does not count (mirrors
    ``consistency_check._tension_reconciled_urns``'s "half-reconciled" rule).
    """
    half_reconciled = _make_graph(
        nodes=[
            (_ACTION, NodeKind.ACTION),
            (_DIRECTIVE_024, NodeKind.DIRECTIVE),
            (_DIRECTIVE_025, NodeKind.DIRECTIVE),
            (_RECONCILER, NodeKind.DIRECTIVE),
        ],
        edges=[
            (_ACTION, _DIRECTIVE_024, Relation.SCOPE),
            (_ACTION, _DIRECTIVE_025, Relation.SCOPE),
            (_DIRECTIVE_024, _DIRECTIVE_025, Relation.IN_TENSION_WITH),
            (_RECONCILER, _DIRECTIVE_024, Relation.RECONCILES_TENSION),
            # No reconciles_tension edge to _DIRECTIVE_025.
        ],
    )
    ctx = resolve_context(half_reconciled, _ACTION, depth=2)
    assert ctx.tension_arbiters == ()
    assert ctx.unarbitrated_tensions == ((_DIRECTIVE_024, _DIRECTIVE_025),)


def test_no_tension_edges_defaults_to_empty_tuples() -> None:
    """Common case (no tension edges in scope): both fields are ``()`` and
    pre-existing artifact/glossary resolution is unaffected (NFR-003).
    """
    plain = _make_graph(
        nodes=[
            (_ACTION, NodeKind.ACTION),
            (_DIRECTIVE_024, NodeKind.DIRECTIVE),
        ],
        edges=[(_ACTION, _DIRECTIVE_024, Relation.SCOPE)],
    )
    ctx = resolve_context(plain, _ACTION, depth=2)
    assert ctx.tension_arbiters == ()
    assert ctx.unarbitrated_tensions == ()
    assert ctx.artifact_urns == frozenset({_DIRECTIVE_024})
    assert ctx.glossary_scopes == frozenset()


def test_resolved_context_stays_hashable() -> None:
    """The frozen dataclass's auto-``__hash__`` must survive the new fields
    (brownfield constraint, tasks.md WP02 T2): both fields are tuples, never
    a dict or list.
    """
    ctx = resolve_context(_tension_graph(), _ACTION, depth=2)
    assert isinstance(ctx.tension_arbiters, tuple)
    assert isinstance(ctx.unarbitrated_tensions, tuple)
    hash(ctx)  # must not raise
    assert {ctx, ctx} == {ctx}


def test_resolved_context_defaults_are_backward_compatible() -> None:
    """A pre-existing two-positional-arg construction site stays byte-valid
    (tasks.md WP02: "every existing construction site must remain valid
    unchanged")."""
    ctx = ResolvedContext(frozenset({"directive:DIRECTIVE_001"}), frozenset())
    assert ctx.tension_arbiters == ()
    assert ctx.unarbitrated_tensions == ()
