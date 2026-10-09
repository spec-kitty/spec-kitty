"""DRG graph query primitives -- pure graph traversal, no charter semantics.

Provides :func:`walk_edges` for generic BFS edge traversal,
:func:`resolve_context` for the multi-step action context resolution
algorithm, and :func:`resolve_transitive_refs` as a bucketed wrapper
over :func:`walk_edges` for the charter resolver/compiler cutover.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from charter.offering.drg.models import DRGGraph, NodeKind, Relation


def _empty_buckets() -> dict[NodeKind, list[str]]:
    """One bucket per :class:`NodeKind`, seeded from the enum itself.

    Totality is what closes the drop, and it is structural: the seed is
    ``NodeKind``, so a member added tomorrow gets a bucket without anyone
    editing this module.
    """
    return {kind: [] for kind in NodeKind}


#: Legacy named fields, keyed by the field name so this table can never itself
#: become a partial kind-keyed lookup (the failure mode
#: ``tests/charter_offering/drg/test_kind_mapping_totality.py`` exists to catch). It is
#: deliberately *not* the source of totality -- :func:`_empty_buckets` is. This
#: only records which kinds additionally answer to a named attribute, so the
#: two surfaces stay one truth.
_KIND_BY_LEGACY_FIELD: dict[str, NodeKind] = {
    "directives": NodeKind.DIRECTIVE,
    "tactics": NodeKind.TACTIC,
    "paradigms": NodeKind.PARADIGM,
    "styleguides": NodeKind.STYLEGUIDE,
    "toolguides": NodeKind.TOOLGUIDE,
    "procedures": NodeKind.PROCEDURE,
    "agent_profiles": NodeKind.AGENT_PROFILE,
    "mission_step_contracts": NodeKind.MISSION_STEP_CONTRACT,
    "templates": NodeKind.TEMPLATE,
    "assets": NodeKind.ASSET,
}


@dataclass(frozen=True)
class ResolvedContext:
    """Result of resolving governance context from the DRG.

    Attributes:
        artifact_urns: All resolved artifact URNs (directives, tactics,
            styleguides, toolguides, etc.) reachable from the action node.
        glossary_scopes: Glossary scope URNs reachable via ``vocabulary``
            edges from the resolved artifacts.
        tension_arbiters: FR-009 -- co-delivered ``in_tension_with`` pairs
            (both endpoints inside :attr:`artifact_urns`) mapped to the
            reconciler(s) that carry a ``reconciles_tension`` edge to BOTH
            sides, as ``(arbiter_urn, (arbitrated_urn, ...))`` pairs. A
            trailing, defaulted, hashable field (tuple of tuples, not a
            dict) so the frozen dataclass's auto-``__hash__`` stays intact.
        unarbitrated_tensions: FR-009 -- co-delivered ``in_tension_with``
            pairs with no reachable reconciler, as ``(source, target)``
            pairs (canonical lexicographic order, matching how
            ``in_tension_with`` itself is stored). Trailing, defaulted,
            hashable (tuple of tuples) for the same reason.
    """

    artifact_urns: frozenset[str]
    glossary_scopes: frozenset[str]
    tension_arbiters: tuple[tuple[str, tuple[str, ...]], ...] = ()
    unarbitrated_tensions: tuple[tuple[str, str], ...] = ()


def walk_edges(
    graph: DRGGraph,
    start_urns: set[str],
    relations: set[Relation],
    max_depth: int | None = None,
) -> set[str]:
    """BFS traversal following only edges matching *relations*.

    Args:
        graph: The DRG graph to walk.
        start_urns: Seed URNs to start from.
        relations: Only follow edges whose relation is in this set.
        max_depth: Maximum number of hops from any start node.
            ``None`` means walk until exhausted (transitive closure).

    Returns:
        Set of all visited node URNs (including start nodes that exist
        in the graph).
    """
    if not start_urns:
        return set()

    # Pre-compute adjacency for the requested relations
    adj: dict[str, list[str]] = {}
    for edge in graph.edges:
        if edge.relation in relations:
            adj.setdefault(edge.source, []).append(edge.target)

    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque()

    for urn in start_urns:
        visited.add(urn)
        queue.append((urn, 0))

    while queue:
        current, depth = queue.popleft()
        if max_depth is not None and depth >= max_depth:
            continue
        for neighbor in adj.get(current, []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, depth + 1))

    return visited


def _tension_annotations(
    graph: DRGGraph,
    all_artifacts: set[str],
) -> tuple[tuple[tuple[str, tuple[str, ...]], ...], tuple[tuple[str, str], ...]]:
    """Annotate co-delivered tension pairs with their arbiter, if any (FR-009).

    Single bounded pass over ``graph.edges`` -- not a second
    :func:`walk_edges` BFS -- so the common case (no tension edges touching
    *all_artifacts*) stays cheap (NFR-003). ``in_tension_with`` is stored as
    one canonical edge per pair (lexicographically-smaller URN as source,
    per :class:`Relation`'s docstring), so a plain ``edges`` scan already
    sees every pair regardless of which endpoint a caller might expect to
    query from.

    Args:
        graph: The DRG graph already loaded for this resolution.
        all_artifacts: The action's resolved artifact URNs (scope + requires
            + suggests) -- a tension pair counts as "in scope" only when
            BOTH endpoints are delivered together.

    Returns:
        ``(tension_arbiters, unarbitrated_tensions)`` -- see
        :class:`ResolvedContext` for the field shapes. A reconciler need not
        itself be inside *all_artifacts* to arbitrate a pair that is; only
        the tension pair's own two endpoints must be.
    """
    tension_pairs: set[tuple[str, str]] = {
        (edge.source, edge.target)
        for edge in graph.edges
        if edge.relation is Relation.IN_TENSION_WITH
        and edge.source in all_artifacts
        and edge.target in all_artifacts
    }
    if not tension_pairs:
        return (), ()

    reconcilers_by_target: dict[str, set[str]] = {}
    for edge in graph.edges:
        if edge.relation is Relation.RECONCILES_TENSION:
            reconcilers_by_target.setdefault(edge.target, set()).add(edge.source)

    arbiters: dict[str, set[str]] = {}
    unarbitrated: set[tuple[str, str]] = set()
    for source, target in tension_pairs:
        common_arbiters = reconcilers_by_target.get(source, set()) & reconcilers_by_target.get(
            target, set()
        )
        if not common_arbiters:
            unarbitrated.add((source, target))
            continue
        for arbiter in common_arbiters:
            arbiters.setdefault(arbiter, set()).update((source, target))

    tension_arbiters = tuple(
        (arbiter, tuple(sorted(arbitrated))) for arbiter, arbitrated in sorted(arbiters.items())
    )
    unarbitrated_tensions = tuple(sorted(unarbitrated))
    return tension_arbiters, unarbitrated_tensions


def resolve_context(
    graph: DRGGraph,
    action_urn: str,
    depth: int = 2,
) -> ResolvedContext:
    """Resolve governance context for an action by walking the DRG.

    The algorithm:

    1. **Scope** -- walk ``scope`` edges from *action_urn* (depth 1) to
       find directly scoped artifacts.
    2. **Requires** -- walk ``requires`` edges from scoped artifacts
       transitively (no depth limit) to find hard dependencies.
    3. **Suggests** -- walk ``suggests`` edges from scoped artifacts up
       to *depth* hops to find soft recommendations.
    4. **Vocabulary** -- walk ``vocabulary`` edges from all resolved nodes
       (depth 1) to find glossary scopes.
    5. **Tension annotation** (FR-009) -- annotate co-delivered
       ``in_tension_with`` pairs with their reconciler via
       :func:`_tension_annotations`, a single bounded ``edges`` scan (not a
       second :func:`walk_edges` traversal), so the no-tension-in-scope case
       stays as cheap as before this step existed.

    Args:
        graph: Merged DRG graph.
        action_urn: URN of the action node (e.g.
            ``"action:software-dev/implement"``).
        depth: Maximum hops for ``suggests`` edges. Also controls
            extended artifact inclusion.

    Returns:
        :class:`ResolvedContext` with artifact and glossary URNs.
    """
    # Step 1: scope edges (depth 1) from action node
    scoped = walk_edges(graph, {action_urn}, {Relation.SCOPE}, max_depth=1)
    # Remove the action node itself -- we only want the scoped artifacts
    scoped_artifacts = scoped - {action_urn}

    # Step 2: requires edges transitively from scoped artifacts
    required = walk_edges(graph, scoped_artifacts, {Relation.REQUIRES}, max_depth=None)

    # Step 3: suggests edges from scoped artifacts to depth hops
    suggested = walk_edges(graph, scoped_artifacts, {Relation.SUGGESTS}, max_depth=depth)

    # Combine all artifact URNs
    all_artifacts = scoped_artifacts | required | suggested

    # Step 4: vocabulary edges (depth 1) from all resolved nodes
    vocab_walk = walk_edges(graph, all_artifacts, {Relation.VOCABULARY}, max_depth=1)
    glossary_scopes = vocab_walk - all_artifacts

    # Step 5: tension annotation (FR-009) -- bounded, no second BFS walk.
    tension_arbiters, unarbitrated_tensions = _tension_annotations(graph, all_artifacts)

    return ResolvedContext(
        artifact_urns=frozenset(all_artifacts),
        glossary_scopes=frozenset(glossary_scopes),
        tension_arbiters=tension_arbiters,
        unarbitrated_tensions=unarbitrated_tensions,
    )


@dataclass(frozen=True)
class ResolveTransitiveRefsResult:
    """Transitive closure of doctrine artifacts reachable from a set of starting URNs,
    bucketed by :class:`NodeKind`.

    Field values are bare IDs (URN without the ``"<kind>:"`` prefix), preserving the
    legacy-compatible field shape for callers during the
    Phase 1 cutover (see WP03 in
    ``kitty-specs/excise-doctrine-curation-and-inline-references-01KP54J6/``).

    Each per-kind list is returned sorted lexicographically so that downstream
    rendering is deterministic.

    Totality (WP03 of ``doctrine-silence-guards-01KYFV7Q``, FR-003/SC-002)
    ---------------------------------------------------------------------
    The named fields cover ten of :class:`NodeKind`'s sixteen members, so
    bucketing that reads only those fields discarded ``action``,
    ``anti_pattern``, ``glossary``, ``glossary_pack``, ``glossary_scope`` and
    ``mission_type`` -- kinds the shipped graph carries *today*, not
    hypothetical ones. :attr:`by_kind` is the total view: one entry for every
    member, so nothing can fall out and a kind added later is carried without
    touching this class.

    Loudness here is *totality*, not an exception, and that is deliberate.
    The frozen contract at
    ``kitty-specs/excise-doctrine-curation-and-inline-references-01KP54J6/contracts/resolve-transitive-refs.contract.md``
    (:89, :204) states this function records rather than raises; raising on
    ``anti_pattern`` would also break the live graph. A result that loses
    nothing has no shortfall left to announce.
    """

    directives: list[str] = field(default_factory=list)
    tactics: list[str] = field(default_factory=list)
    paradigms: list[str] = field(default_factory=list)
    styleguides: list[str] = field(default_factory=list)
    toolguides: list[str] = field(default_factory=list)
    procedures: list[str] = field(default_factory=list)
    agent_profiles: list[str] = field(default_factory=list)
    mission_step_contracts: list[str] = field(default_factory=list)
    templates: list[str] = field(default_factory=list)
    assets: list[str] = field(default_factory=list)
    # Edges whose target URN was not found in the graph, stored as
    # ``(source_urn, target_urn)``. Always ``[]`` when the input graph has
    # passed :func:`charter.offering.drg.validator.assert_valid`, since the validator
    # rejects dangling targets at load time.
    unresolved: list[tuple[str, str]] = field(default_factory=list)
    #: Bare IDs bucketed by *every* :class:`NodeKind`, including the six with
    #: no named field above. Callers that must not lose a kind read this.
    by_kind: Mapping[NodeKind, list[str]] = field(default_factory=_empty_buckets)

    def __post_init__(self) -> None:
        """Reconcile the named fields and :attr:`by_kind` into one truth.

        Callers still construct this result with named keyword arguments only
        (``charter.activation.compiler``, ``charter.activation.reference_resolver``). Left alone,
        those instances would expose a populated ``directives`` beside an empty
        ``by_kind`` -- closing one silent drop by opening another for whoever
        reads the new surface. So whichever side was supplied fills the other,
        and supplying both with conflicting content is a programming error
        rather than a silently-picked winner.
        """
        buckets = _empty_buckets()
        for kind, ids in self.by_kind.items():
            buckets[kind] = list(ids)

        for field_name, kind in _KIND_BY_LEGACY_FIELD.items():
            named: list[str] = getattr(self, field_name)
            bucketed = buckets[kind]
            if named and bucketed and named != bucketed:
                raise ValueError(
                    f"ResolveTransitiveRefsResult.{field_name} and "
                    f"by_kind[{kind.value}] disagree: {named!r} vs {bucketed!r}"
                )
            reconciled = bucketed or list(named)
            buckets[kind] = reconciled
            object.__setattr__(self, field_name, reconciled)

        object.__setattr__(self, "by_kind", MappingProxyType(buckets))

    @property
    def is_complete(self) -> bool:
        """``True`` when all referenced artifacts were resolved (legacy-symmetric)."""
        return len(self.unresolved) == 0


def resolve_transitive_refs(
    graph: DRGGraph,
    *,
    start_urns: set[str],
    relations: set[Relation],
    max_depth: int | None = None,
) -> ResolveTransitiveRefsResult:
    """Walk ``relations`` edges from ``start_urns``, bucketing reachable nodes by kind.

    Thin wrapper over :func:`walk_edges` that groups the flat result set by
    :class:`NodeKind` and strips the URN prefix from each per-kind list.
    Designed as a behavior-equivalent replacement for the legacy charter
    transitive resolver during the Phase 1 cutover
    (``kitty-specs/excise-doctrine-curation-and-inline-references-01KP54J6``).

    Args:
        graph: The DRG graph to walk. The graph MUST already have passed
            :func:`charter.offering.drg.validator.assert_valid`; this function does
            not re-validate.
        start_urns: Seed URNs (e.g. ``"directive:001-architectural-integrity-standard"``).
            Start URNs whose node is absent from ``graph`` are recorded in
            ``unresolved`` rather than raising.
        relations: Set of :class:`Relation` values to follow. For legacy
            parity with the charter resolver/compiler, callers pass
            ``{Relation.REQUIRES, Relation.SUGGESTS}``.
        max_depth: Forwarded to :func:`walk_edges`. ``None`` means transitive
            closure.

    Returns:
        :class:`ResolveTransitiveRefsResult` with per-kind bucketed bare IDs.
        Each per-kind list is sorted lexicographically. Every
        :class:`NodeKind` is represented in
        :attr:`~ResolveTransitiveRefsResult.by_kind`, including the six with no
        named field; a visited node is never discarded for being of an
        unexpected kind.

    Raises:
        Nothing. ``requires`` cycles are rejected at load time by
        :func:`assert_valid`; cycles in other relation kinds are benign
        under BFS-with-visited-set inside :func:`walk_edges`. Unknown start
        URNs are recorded in ``unresolved``, per the frozen contract. WP03 of
        ``doctrine-silence-guards-01KYFV7Q`` kept that promise intact by
        closing the kind drop with totality rather than an exception.
    """
    visited_urns = walk_edges(
        graph,
        start_urns=start_urns,
        relations=relations,
        max_depth=max_depth,
    )

    buckets = _empty_buckets()
    unresolved: list[tuple[str, str]] = []

    for urn in visited_urns:
        node = graph.get_node(urn)
        if node is None:
            # Defensive: assert_valid should prevent dangling URNs in a
            # validated graph. If one slips through (including an unknown
            # start URN), record it with itself as both source and target.
            unresolved.append((urn, urn))
            continue
        # Strip "<kind>:" prefix from the URN when writing into the bucket.
        bare_id = urn.split(":", 1)[1] if ":" in urn else urn
        buckets[node.kind].append(bare_id)

    for kind in NodeKind:
        buckets[kind].sort()
    unresolved.sort()

    # Hand-listing the ten named fields here is what lost the other six
    # (WP03/T013). Pass the total bucket map instead and let
    # ``__post_init__`` project the legacy names off it, so the enumeration
    # exists in exactly one place and that place is seeded from ``NodeKind``.
    return ResolveTransitiveRefsResult(unresolved=unresolved, by_kind=buckets)
