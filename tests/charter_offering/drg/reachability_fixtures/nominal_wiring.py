"""The nominal-wiring trap fixture (T047).

PR #3007 "wired" eight activated orphans by giving each an inbound edge, and an
*incidence* check (``_orphan_urns``) then read them as fixed. But four of the
eight attached to a source that was itself unreachable, so no action-channel
traversal arrives at them — they were wired on paper and delivered to nobody.

This fixture reproduces that shape at minimal scale:

    action:demo/build --scope--> directive:in-scope
    directive:in-scope --requires--> toolguide:properly-wired      (positive control)

    tactic:unreachable-source --requires--> styleguide:nominally-wired
        (^ the source has NO inbound edge from anything an action scopes)

Incidence verdict: ``tactic:unreachable-source`` and ``styleguide:nominally-wired``
are both incident to an edge, so incidence calls them "wired" / not-orphan.

Reachability verdict (``resolve_context`` from ``action:demo/build``):
``{directive:in-scope, toolguide:properly-wired}`` are reachable; the
nominally-wired pair is **not**, because the ``requires`` edge into
``styleguide:nominally-wired`` originates from an unreachable source.

``toolguide:properly-wired`` is the positive control: wiring to a *reachable*
source (a scoped directive) does confer reachability, so the fixture also proves
the traversal is not simply refusing every ``requires`` target.
"""

from __future__ import annotations

from charter.offering.drg.models import DRGEdge, DRGGraph, DRGNode, NodeKind, Relation

#: Seed action node for the fixture's action channel.
ACTION_URN = "action:demo/build"

#: Reachable at depth 1 — the action scopes it directly.
IN_SCOPE_DIRECTIVE = "directive:in-scope"

#: Reachable via a ``requires`` edge from the scoped directive (positive
#: control: wiring to a *reachable* source works).
PROPERLY_WIRED = "toolguide:properly-wired"

#: Unreachable: nothing an action scopes reaches it. It is nonetheless the
#: *source* of an edge, so an incidence check de-orphans it.
UNREACHABLE_SOURCE = "tactic:unreachable-source"

#: The trap: it has an inbound ``requires`` edge (so incidence says "wired"),
#: but that edge originates from :data:`UNREACHABLE_SOURCE`, so no action-channel
#: traversal arrives — it must be reported UNREACHABLE.
NOMINALLY_WIRED = "styleguide:nominally-wired"


def nominal_wiring_graph() -> DRGGraph:
    """Return the nominal-wiring trap graph described in the module docstring."""
    nodes = [
        DRGNode(urn=ACTION_URN, kind=NodeKind.ACTION),
        DRGNode(urn=IN_SCOPE_DIRECTIVE, kind=NodeKind.DIRECTIVE),
        DRGNode(urn=PROPERLY_WIRED, kind=NodeKind.TOOLGUIDE),
        DRGNode(urn=UNREACHABLE_SOURCE, kind=NodeKind.TACTIC),
        DRGNode(urn=NOMINALLY_WIRED, kind=NodeKind.STYLEGUIDE),
    ]
    edges = [
        DRGEdge(source=ACTION_URN, target=IN_SCOPE_DIRECTIVE, relation=Relation.SCOPE),
        DRGEdge(
            source=IN_SCOPE_DIRECTIVE,
            target=PROPERLY_WIRED,
            relation=Relation.REQUIRES,
        ),
        DRGEdge(
            source=UNREACHABLE_SOURCE,
            target=NOMINALLY_WIRED,
            relation=Relation.REQUIRES,
        ),
    ]
    return DRGGraph(
        schema_version="1.0",
        generated_at="2026-07-29T00:00:00+00:00",
        generated_by="reachability_fixtures.nominal_wiring",
        nodes=nodes,
        edges=edges,
    )


def incident_urns(graph: DRGGraph) -> frozenset[str]:
    """URNs incident to at least one edge — the *incidence* (orphan) verdict.

    This is the wrong method for a reachability question: it counts an edge in
    either direction, so it de-orphans a node wired to an unreachable source.
    Provided here so the gate can contrast it against the traversal answer.
    """
    incident: set[str] = set()
    for edge in graph.edges:
        incident.add(edge.source)
        incident.add(edge.target)
    return frozenset(incident)
