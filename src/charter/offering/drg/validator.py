"""Graph-level validation beyond what Pydantic field validators catch.

Checks:
- Dangling edge references (source/target not in node URNs)
- Duplicate edges (same source + target + relation triple)
- Cycles in the ``requires`` subgraph (DFS-based)
- Symmetric profile-edge integrity (lineage/delegation edges, #1755)
- Rejects/anti_pattern integrity, both directions (INV-004)
"""

from __future__ import annotations

from collections import defaultdict

from charter.offering.drg.models import DRGEdge, DRGGraph, NodeKind, Relation

#: Relations whose *both* endpoints must be ``agent_profile`` nodes. Lineage
#: (``specializes_from``) and runtime delegation (``delegates_to``) are the two
#: profile-to-profile relations; an edge of either kind that touches a
#: non-profile node (or a missing node) is a structural defect regardless of
#: which endpoint declared it (#1755 — the former asymmetric blind spot).
_PROFILE_EDGE_RELATIONS: frozenset[Relation] = frozenset(
    {Relation.SPECIALIZES_FROM, Relation.DELEGATES_TO}
)


class DRGValidationError(Exception):
    """Raised by :func:`assert_valid` when graph integrity checks fail."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__(f"{len(errors)} validation error(s): {'; '.join(errors)}")


def validate_profile_edges(graph: DRGGraph) -> list[str]:
    """Validate profile-to-profile edges symmetrically (#1755).

    Lineage (``specializes_from``) and delegation (``delegates_to``) edges are
    profile-to-profile relations. Historically only the *outgoing* direction
    was exercised at resolution time (``edges_from`` on the declaring child),
    so a malformed edge declared *at* a profile but pointing at a non-profile
    target -- or a lineage cycle -- could slip through unnoticed. This check
    scans both directions so the defect is detected irrespective of which
    endpoint authored the edge:

    1. **Endpoint-kind integrity** -- both ``source`` and ``target`` of a
       profile edge must resolve to ``agent_profile`` nodes. Each endpoint is
       inspected independently (the symmetric part): a profile-edge whose
       *target* is a tactic is just as invalid as one whose *source* is.
    2. **Lineage acyclicity** -- the ``specializes_from`` subgraph must be a
       DAG. ``requires`` cycles are caught elsewhere; lineage needs its own
       check because the relation differs and a profile chain that loops back
       on itself would otherwise wedge ancestor resolution.

    Dangling references are reported by :func:`validate_graph`; this function
    only classifies endpoints it can resolve so the two checks never
    double-report the same missing-node defect.

    Returns a list of human-readable error messages (empty means valid).
    """
    errors: list[str] = []
    errors.extend(_validate_profile_edge_endpoints(graph))
    errors.extend(_validate_lineage_acyclicity(graph))
    return errors


def _validate_profile_edge_endpoints(graph: DRGGraph) -> list[str]:
    """Check both endpoints of every profile edge resolve to agent_profile nodes.

    Extracted from :func:`validate_profile_edges` (phase 1 of 2) to keep its
    cognitive complexity within the ruff C901 limit (15). Each endpoint is
    inspected independently, so a profile-edge whose *target* is a tactic is
    just as invalid as one whose *source* is.
    """
    errors: list[str] = []
    kind_by_urn = {n.urn: n.kind for n in graph.nodes}
    for edge in graph.edges:
        if edge.relation not in _PROFILE_EDGE_RELATIONS:
            continue
        for endpoint_name, urn in (("source", edge.source), ("target", edge.target)):
            kind = kind_by_urn.get(urn)
            if kind is None:
                continue  # missing node -> reported as dangling by validate_graph
            if kind is not NodeKind.AGENT_PROFILE:
                errors.append(
                    f"Profile-edge {endpoint_name} must be an agent_profile: "
                    f"edge ({edge.source} --{edge.relation.value}--> {edge.target}) "
                    f"has {endpoint_name} {urn!r} of kind {kind.value!r}"
                )
    return errors


def _validate_lineage_acyclicity(graph: DRGGraph) -> list[str]:
    """Check the ``specializes_from`` subgraph is a DAG (DFS-based).

    Extracted from :func:`validate_profile_edges` (phase 2 of 2) to keep its
    cognitive complexity within the ruff C901 limit (15).
    """
    errors: list[str] = []
    lineage_adj: dict[str, list[str]] = defaultdict(list)
    for edge in graph.edges:
        if edge.relation == Relation.SPECIALIZES_FROM:
            lineage_adj[edge.source].append(edge.target)

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = defaultdict(int)

    def _dfs(node: str, path: list[str]) -> None:
        color[node] = GRAY
        path.append(node)
        for neighbor in lineage_adj.get(node, []):
            if color[neighbor] == GRAY:
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:] + [neighbor]
                errors.append(
                    f"Cycle in specializes_from lineage: {' -> '.join(cycle)}"
                )
            elif color[neighbor] == WHITE:
                _dfs(neighbor, path)
        path.pop()
        color[node] = BLACK

    lineage_nodes = set(lineage_adj.keys())
    for targets in lineage_adj.values():
        lineage_nodes.update(targets)
    for node in sorted(lineage_nodes):
        if color[node] == WHITE:
            _dfs(node, [])

    return errors


def _validate_rejects_targets(graph: DRGGraph) -> list[str]:
    """Validate ``rejects`` edges point at an ``anti_pattern`` node (INV-004).

    A ``rejects`` edge (mission ``doctrine-tension-edges-01KY1WPC``, FR-003)
    is directional, from a good artefact to a marked anti-pattern/smell node.
    A ``rejects`` edge whose target does not resolve to a
    ``NodeKind.ANTI_PATTERN`` node is a structural defect -- the target is
    supposed to name a bad practice, not a co-valid rule -- and must raise a
    validation error rather than silently no-op.

    This validates authored structure only (is the edge well-formed); it runs
    regardless of whether the target is currently activated in any
    ``PackContext``.

    Dangling targets are reported by :func:`validate_dangling_references`;
    this check only classifies targets it can resolve so the two checks
    never double-report the same missing-node defect.

    Returns a list of human-readable error messages (empty means valid).
    """
    errors: list[str] = []
    kind_by_urn = {n.urn: n.kind for n in graph.nodes}
    for edge in graph.edges:
        if edge.relation is not Relation.REJECTS:
            continue
        kind = kind_by_urn.get(edge.target)
        if kind is None:
            continue  # missing node -> reported as dangling by validate_graph
        if kind is not NodeKind.ANTI_PATTERN:
            errors.append(
                f"Rejects-edge target must be an anti_pattern node: "
                f"edge ({edge.source} --{edge.relation.value}--> {edge.target}) "
                f"has target {edge.target!r} of kind {kind.value!r}"
            )
    return errors


def _validate_anti_pattern_nodes_are_rejected(graph: DRGGraph) -> list[str]:
    """Validate every ``anti_pattern`` node has >=1 inbound ``rejects`` edge.

    Reverse mirror of :func:`_validate_rejects_targets`: that check enforces
    the *forward* direction (a ``rejects`` edge must terminate at an
    ``anti_pattern`` node); this check enforces the *reverse* direction (a
    node marked ``NodeKind.ANTI_PATTERN`` must be the target of at least one
    ``rejects`` edge). Without this, a node tagged ``anti-pattern``/``smell``
    that nothing actually rejects would pass silently -- a bad practice
    named in the graph but not wired to anything that avoids it.

    Uses :meth:`DRGGraph.edges_to` (reverse-adjacency lookup) rather than a
    hand-rolled scan, mirroring the query helper already used by cascade
    traversal.

    Returns a list of human-readable error messages (empty means valid).
    """
    errors: list[str] = []
    for node in graph.nodes:
        if node.kind is not NodeKind.ANTI_PATTERN:
            continue
        if not graph.edges_to(node.urn, relation=Relation.REJECTS):
            errors.append(
                f"Orphaned anti_pattern node: {node.urn!r} is marked "
                "anti_pattern but has no inbound rejects edge"
            )
    return errors


def validate_dangling_references(graph: DRGGraph) -> list[str]:
    """Return errors for edges whose source/target is not a known node.

    Public because the org-pack merge path needs *this* check on its own, not
    the whole of :func:`validate_graph`. ``merge_three_layers`` itself only
    WARNs (see :func:`charter.offering.drg.merge._dangling_org_endpoints`): it cannot
    know whether its caller merged the whole graph or a deliberate subset.

    **When a caller must run this (the rule, not a list of surfaces).** Run it
    iff you merged the COMPLETE graph — in practice, iff you passed the real
    shipped built-in layer (``load_built_in_graph()``) plus every layer the
    operator configured. Such a caller can distinguish a typo from a forward
    reference, so for it a dangling endpoint is an error, not a warning. A
    caller that deliberately merged a SUBSET must not: ``charter lint`` merges
    org fragments against an intentionally EMPTY built-in to isolate pack-level
    conflicts, so every qualified endpoint dangles there by construction and
    the check would report only noise.

    An earlier revision of this docstring named the org-pack doctor command
    as "the one place" holding a complete graph. That was false — three runtime
    callers build the merge from byte-identical inputs, and stating the claim as
    a uniqueness rather than a predicate is what let two of them ship a clean
    bill for an unclean graph. State the predicate: if you are adding a caller,
    ask whether *your* merge was complete.

    Exposed rather than copied so there is one definition of "dangling" —
    a second, private-to-doctor restatement is how the three drifted kind maps
    in this codebase started. Runtime callers under ``src/specify_cli/`` reach
    it through the ``charter.drg`` facade, not this module (ADR 2026-03-27-1).
    """
    errors: list[str] = []
    urns = graph.node_urns()
    for edge in dangling_endpoints(graph):
        if edge.source not in urns:
            errors.append(
                f"Dangling source: edge ({edge.source} --{edge.relation}--> "
                f"{edge.target}) references non-existent node {edge.source!r}"
            )
        if edge.target not in urns:
            errors.append(
                f"Dangling target: edge ({edge.source} --{edge.relation}--> "
                f"{edge.target}) references non-existent node {edge.target!r}"
            )
    return errors


def dangling_endpoints(graph: DRGGraph) -> list[DRGEdge]:
    """Return each edge whose source and/or target is not a known node URN.

    Structured SSOT for "dangling edge" detection (charter-synthesize-
    reconciliation WP01, amendment #3). Both :func:`validate_dangling_references`
    (string formatting, above) and ``charter.activation.synthesizer.reconcile``
    (preserved-vs-new-emit provenance classification) consume this so
    "dangling" has exactly one definition, never a second re-implementation.

    An edge with a dangling endpoint on *either* side appears once here even
    when both sides dangle; :func:`validate_dangling_references` re-derives
    which side(s) dangled from ``graph.node_urns()`` to keep its
    one-message-per-dangling-endpoint output shape (and exact wording)
    unchanged.
    """
    urns = graph.node_urns()
    return [edge for edge in graph.edges if edge.source not in urns or edge.target not in urns]


def duplicate_edge_triples(graph: DRGGraph) -> list[DRGEdge]:
    """Return each edge that repeats an already-seen ``(source, target, relation)`` triple.

    Structured SSOT for "duplicate edge" detection (charter-synthesize-
    reconciliation WP01, amendment #3). Both :func:`_validate_duplicate_edges`
    (string formatting, below) and ``charter.activation.synthesizer.reconcile``
    (preserved-vs-new-emit provenance classification) consume this so
    "duplicate" has exactly one definition. Returns the second-and-later
    occurrence of each repeated triple, in graph edge order -- mirrors the
    prior inline scan exactly, so :func:`validate_graph`'s string output is
    unchanged.
    """
    duplicates: list[DRGEdge] = []
    seen_triples: set[tuple[str, str, str]] = set()
    for edge in graph.edges:
        triple = (edge.source, edge.target, edge.relation.value)
        if triple in seen_triples:
            duplicates.append(edge)
        seen_triples.add(triple)
    return duplicates


def _validate_duplicate_edges(graph: DRGGraph) -> list[str]:
    """Return errors for repeated ``(source, target, relation)`` triples."""
    return [
        f"Duplicate edge: ({edge.source} --{edge.relation}--> {edge.target})"
        for edge in duplicate_edge_triples(graph)
    ]


def _validate_requires_cycles(graph: DRGGraph) -> list[str]:
    """Return errors for cycles in the ``requires`` subgraph (DFS)."""
    errors: list[str] = []
    adj: dict[str, list[str]] = defaultdict(list)
    for edge in graph.edges:
        if edge.relation == Relation.REQUIRES:
            adj[edge.source].append(edge.target)

    # Standard DFS cycle detection with WHITE/GRAY/BLACK coloring
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = defaultdict(int)  # default WHITE

    def _dfs(node: str, path: list[str]) -> None:
        color[node] = GRAY
        path.append(node)
        for neighbor in adj.get(node, []):
            if color[neighbor] == GRAY:
                # Found a back edge -- extract the cycle
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:] + [neighbor]
                errors.append(
                    f"Cycle in requires: {' -> '.join(cycle)}"
                )
            elif color[neighbor] == WHITE:
                _dfs(neighbor, path)
        path.pop()
        color[node] = BLACK

    # Visit all nodes that participate in requires edges
    all_requires_nodes = set(adj.keys())
    for targets in adj.values():
        all_requires_nodes.update(targets)

    for node in sorted(all_requires_nodes):
        if color[node] == WHITE:
            _dfs(node, [])
    return errors


def validate_graph(graph: DRGGraph) -> list[str]:
    """Return a list of error messages (empty means valid).

    Checks performed:
    1. Dangling references -- every edge source/target must exist in nodes.
    2. Duplicate edges -- ``(source, target, relation)`` must be unique.
    3. Cycles in ``requires`` edges -- the requires subgraph must be a DAG.
    4. Symmetric profile-edge integrity -- lineage/delegation edges connect
       agent_profile nodes in both directions and lineage is acyclic (#1755).
    5. Rejects-target integrity -- ``rejects`` edges must target an
       ``anti_pattern`` node (INV-004, mission ``doctrine-tension-edges-01KY1WPC``).
    6. Anti-pattern-node integrity -- every ``anti_pattern`` node must be the
       target of at least one ``rejects`` edge (INV-004 reverse direction).
    """
    errors: list[str] = []
    errors.extend(validate_dangling_references(graph))
    errors.extend(_validate_duplicate_edges(graph))
    errors.extend(_validate_requires_cycles(graph))
    # -- 4. Symmetric profile-edge integrity (#1755) ------------------------
    errors.extend(validate_profile_edges(graph))
    # -- 5. Rejects-target integrity (INV-004) ------------------------------
    errors.extend(_validate_rejects_targets(graph))
    # -- 6. Anti-pattern-node integrity (INV-004 reverse) --------------------
    errors.extend(_validate_anti_pattern_nodes_are_rejected(graph))
    return errors


def assert_valid(graph: DRGGraph) -> None:
    """Raise :class:`DRGValidationError` if the graph has integrity errors."""
    errors = validate_graph(graph)
    if errors:
        raise DRGValidationError(errors)
