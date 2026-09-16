"""Scoped, shared-reference-safe cascade engine over the merged DRG.

This module is the consumer of the ``cascade_scope`` value threaded — but not
consumed — through :mod:`charter.activation.activation_engine` (WP10). It turns a single
``charter activate`` / ``charter deactivate`` request into the set of *referenced*
artifacts that should cascade, as **pure graph logic** over the merged Doctrine
Reference Graph (DRG). There are **no per-kind special cases** (FR-016, C-005,
I-AC3): every decision branches on graph reachability, never on ``kind ==``.

Design (FR-013..016, data model §6, contracts C3.2/C3.3/C3.4)
------------------------------------------------------------

* :class:`CascadeScope` is an explicit value object. ``--cascade all`` parses to
  :data:`CascadeScope.ALL` (the all-kind shorthand); ``--cascade
  agent-profile,tactic`` parses to an explicit ``frozenset`` of
  :class:`~charter.offering.artifact_kinds.ArtifactKind`. **Absence** of ``--cascade``
  parses to ``None`` and **never** means all (Contract C3.3). The scope string is
  never collapsed to a bool.

* :func:`cascade_activation_targets` walks the DRG **forward** along the doctrine
  reference relations (:data:`_REFERENCE_RELATIONS`) from the activation source,
  bucketing reachable artifacts by kind, then keeps only the kinds the scope
  selects (FR-014). Kinds referenced but *outside* the scope are reported as
  skipped-by-scope.

* :func:`referenced_but_not_cascaded` is the no-cascade path (FR-013): when
  ``--cascade`` is absent it returns the referenced-but-not-activated artifacts
  (by kind) plus a recovery hint so the CLI (WP12) can warn (Contract C3.2).

* :func:`deactivation_plan` is the shared-reference-safe removal path
  (FR-015/016, C-005, I-AC2). A cascade candidate is **exclusive** iff it is
  unreachable (forward closure over :data:`_REFERENCE_RELATIONS`) from **every**
  other still-activated source once ``target_urn`` is removed. Exclusive
  candidates are deactivated; **shared** candidates are skipped and the still-
  referencing active source is named. No shared artifact is ever removed
  (Contract C3.4). Exclusivity is computed via reverse reachability — the inverse
  of the forward closure, using ``edges_to`` adjacency — over the merged DRG.

Layering
--------
Charter layer: this module imports only ``doctrine`` (the DRG models, query
primitives, and the canonical :class:`ArtifactKind`). It never imports
``specify_cli`` (C-001) and performs no I/O — it is pure graph logic over data
handed in by the caller (the CLI in WP12).

Wiring note (C-007)
-------------------
The public symbols below gain their first caller in **WP12** (the charter
activation CLI), which depends on this WP and merges after it. WP10 already
threads a ``cascade_scope`` parameter into ``plan_activation`` /
``plan_deactivation`` for the seam shape; WP12 will parse the CLI string with
:meth:`CascadeScope.parse`, call into this engine, and fold the results into the
``ActivationPlan.cascade_targets`` / ``warnings`` fields. The dead-symbol gate is
satisfied at mission-merge per the WP11 Definition of Done.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import ClassVar

from charter.offering.artifact_kinds import CHARTER_ACTIVATABLE_KINDS, ArtifactKind
from charter.offering.drg.models import DRGEdge, DRGGraph, Relation

__all__ = [
    "CascadeScope",
    "DeactivationPlan",
    "ReferencedArtifact",
    "SharedSkip",
    "cascade_activation_targets",
    "deactivation_plan",
    "referenced_but_not_cascaded",
]


#: The doctrine reference relations the cascade follows. A cascade activates the
#: artifacts an activated artifact *references*; per R-012 / FR-016 the DRG is the
#: canonical reference model, so cascade traversal is opt-in by this relation set
#: rather than per-kind logic. ``REQUIRES`` (hard dependency) and ``SUGGESTS``
#: (soft recommendation) are the legacy charter-resolver reference set
#: (see :func:`charter.offering.drg.query.resolve_transitive_refs`). ``REFINES`` (#2079)
#: is followed too: a refinement is a traversable reference at least as
#: load-bearing as a suggestion, so activating an artifact cascades to what it
#: refines — this is the wiring that keeps ``REFINES`` from being born inert.
#:
#: ``SCOPE`` and ``INSTANTIATES`` join the set per ADR 2026-08-20-1 (#2829) to
#: follow the **action hop**. A ``mission_type`` node carries
#: ``requires → action`` edges and, since #3604, ``scope → governance`` edges
#: for its type-wide selections; an ``action`` node carries ``scope → governance``
#: ({directive, tactic, styleguide, …}) and ``instantiates → template`` — it has
#: no requires/suggests/refines edges. Without ``scope``/``instantiates`` the
#: forward closure reaches the ``action`` node and stops, so activating any of the
#: four built-in mission types cascaded to nobody. ``scope`` is the direct #2829
#: fix (action → governance); ``instantiates`` is followed so the action hop is
#: complete and mission-type actions are treated like the pre-existing sources
#: that already reach templates. Its non-activatable ``template`` targets are
#: dropped at *candidacy* (see :func:`_referenced_artifacts`), not by omitting the
#: relation — traversal reach and candidacy are separate concerns. The remaining
#: relations stay excluded (lineage, overlay, runtime handoff, tension,
#: anti-pattern) so the cascade never over-reaches; the ADR tabulates why.
_REFERENCE_RELATIONS: frozenset[Relation] = frozenset(
    {
        Relation.REQUIRES,
        Relation.SUGGESTS,
        Relation.REFINES,
        Relation.SCOPE,
        Relation.INSTANTIATES,
    }
)

#: Recovery hint surfaced with the no-cascade warning (FR-013, Contract C3.2).
_NO_CASCADE_HINT: str = (
    "Re-run with `--cascade <scope>` (e.g. `--cascade all` for every referenced "
    "kind) to activate the referenced artifacts, or run `charter consistency-check` "
    "to confirm the activation set is coherent."
)


def _kind_of(urn: str) -> ArtifactKind | None:
    """Resolve the :class:`ArtifactKind` for a URN's ``<kind>:`` prefix.

    Returns ``None`` when the prefix is not one of the eight canonical artifact
    kinds (e.g. ``action:``, ``glossary:`` nodes, or a malformed URN). Cascade
    only ever activates/deactivates artifact-kind nodes, so non-artifact nodes
    are simply not cascade candidates — this keeps the engine kind-agnostic
    (it never branches on a *specific* kind, only on whether the node is an
    artifact at all).
    """
    prefix = urn.split(":", 1)[0] if ":" in urn else urn
    try:
        return ArtifactKind(prefix)
    except ValueError:
        return None


def _bare_id(urn: str) -> str:
    """Strip the ``<kind>:`` prefix from *urn*, returning the bare artifact ID."""
    return urn.split(":", 1)[1] if ":" in urn else urn


def _bucket_by_kind(refs: list[ReferencedArtifact]) -> dict[str, list[str]]:
    """Bucket *refs* by kind value into per-kind sorted lists of bare IDs.

    Issue #3772: the single kind-bucketing seam for the cascade result/report
    fields -- the ``setdefault(...).append(...)`` + per-list ``sort()`` block
    ``cascade_activation_targets`` and ``referenced_but_not_cascaded`` each
    duplicated (and ``deactivation_plan``'s kind-filtered field now shares
    too). Every caller sorts each bucket's IDs so rendering is deterministic;
    bucket insertion order follows *refs*, which callers already sort by
    ``(kind, artifact_id)`` upstream.
    """
    buckets: dict[str, list[str]] = {}
    for ref in refs:
        buckets.setdefault(ref.kind.value, []).append(ref.artifact_id)
    for ids in buckets.values():
        ids.sort()
    return buckets


# ---------------------------------------------------------------------------
# CascadeScope value object (T048; data model §6; Contract C3.3)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CascadeScope:
    """Explicit cascade scope: the all-kind shorthand or an explicit kind set.

    Either :data:`is_all` is ``True`` (the ``--cascade all`` shorthand, which
    selects *every* referenced kind) or :attr:`kinds` is an explicit, non-empty
    ``frozenset`` of :class:`ArtifactKind`. **Absence** of ``--cascade`` is
    represented as ``None`` at call sites (never a :class:`CascadeScope`) and
    **never** means all (Contract C3.3). The scope is a value object, not a bool
    — the requested scope survives intact from CLI to engine.
    """

    is_all: bool = False
    kinds: frozenset[ArtifactKind] = field(default_factory=frozenset)

    #: The literal CLI token for the all-kind shorthand.
    ALL_TOKEN: ClassVar[str] = "all"  # noqa: S105

    def __post_init__(self) -> None:
        if self.is_all and self.kinds:
            raise ValueError(
                "CascadeScope is either the all-kind shorthand (is_all=True) or an "
                "explicit kind set, not both."
            )
        if not self.is_all and not self.kinds:
            raise ValueError(
                "CascadeScope with is_all=False requires at least one kind. "
                "Use scope=None at the call site to express 'no cascade'."
            )

    def selects(self, kind: ArtifactKind) -> bool:
        """Return ``True`` when *kind* is in scope (always ``True`` for ``ALL``)."""
        return self.is_all or kind in self.kinds

    @classmethod
    def all(cls) -> CascadeScope:
        """Return the explicit all-kind shorthand scope (``--cascade all``)."""
        return cls(is_all=True)

    @classmethod
    def parse(cls, raw: str | None) -> CascadeScope | None:
        """Parse a raw CLI ``--cascade`` value into a :class:`CascadeScope`.

        Parameters
        ----------
        raw:
            The raw CLI string. ``None`` (flag absent) or an empty/whitespace
            string returns ``None`` — **no cascade** (never all, Contract C3.3).
            ``"all"`` returns the all-kind shorthand. A comma-separated list of
            operator kind tokens (e.g. ``"agent-profile,tactic"``) returns an
            explicit kind set; each token is resolved through
            :meth:`ArtifactKind.from_operator_token`, so a hyphenated or
            underscored token both work and an unknown token raises a structured
            ``ValueError`` (no silent fallback — R-009).

        Returns
        -------
        CascadeScope | None
            ``None`` for absent/empty input; otherwise the parsed scope.

        Raises
        ------
        ValueError
            If a kind token is not a known operator kind token (the message
            lists the valid tokens). ``mission-type`` raises the distinct
            :class:`~charter.offering.artifact_kinds.MissionTypeNotAnArtifactKind`
            (a ``ValueError`` subclass) since it is not an artifact kind.
        """
        if raw is None:
            return None
        stripped = raw.strip()
        if not stripped:
            return None
        if stripped.lower() == cls.ALL_TOKEN:
            return cls.all()
        tokens = [tok.strip() for tok in stripped.split(",") if tok.strip()]
        if not tokens:
            return None
        kinds = frozenset(ArtifactKind.from_operator_token(tok) for tok in tokens)
        return cls(kinds=kinds)


# ---------------------------------------------------------------------------
# Forward reachability (shared primitive)
# ---------------------------------------------------------------------------


def _forward_reference_closure(
    adj: dict[str, list[str]],
    sources: set[str],
) -> set[str]:
    """Forward transitive closure over a pre-built reference adjacency.

    BFS from *sources* following *adj*; returns every reachable URN **excluding**
    the seed sources themselves (the cascade targets are the artifacts a source
    *references*, not the source). ``adj`` is the forward adjacency restricted to
    :data:`_REFERENCE_RELATIONS`.
    """
    visited: set[str] = set(sources)
    queue: deque[str] = deque(sources)
    while queue:
        current = queue.popleft()
        for neighbor in adj.get(current, ()):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    return visited - sources


def _reference_adjacency(edges: list[DRGEdge]) -> dict[str, list[str]]:
    """Build forward adjacency (source → [target]) over :data:`_REFERENCE_RELATIONS`."""
    adj: dict[str, list[str]] = {}
    for edge in edges:
        if edge.relation in _REFERENCE_RELATIONS:
            adj.setdefault(edge.source, []).append(edge.target)
    return adj


def _referenced_artifacts(
    graph: DRGGraph, source_urn: str
) -> tuple[list[ReferencedArtifact], list[ReferencedArtifact]]:
    """Return activatable and kind-filtered nodes referenced from *source_urn*.

    Pure forward closure over :data:`_REFERENCE_RELATIONS`, filtered twice:
    non-artifact nodes are dropped because :func:`_kind_of` returns ``None``,
    and artifact-kind nodes are partitioned by the canonical
    :data:`charter.offering.artifact_kinds.CHARTER_ACTIVATABLE_KINDS`
    membership into ``activatable`` and ``kind_filtered``. The closure still
    reaches kind-filtered nodes, but this shared seam collects them so every
    caller can report what it saw. Each list is sorted by
    ``(kind, artifact_id)`` for deterministic rendering.

    Returns
    -------
    tuple[list[ReferencedArtifact], list[ReferencedArtifact]]
        ``(activatable, kind_filtered)`` — charter-activatable nodes, then
        structurally non-activatable (``template``/``asset``) nodes.
    """
    adj = _reference_adjacency(graph.edges)
    reachable = _forward_reference_closure(adj, {source_urn})
    activatable: list[ReferencedArtifact] = []
    kind_filtered: list[ReferencedArtifact] = []
    for urn in reachable:
        kind = _kind_of(urn)
        if kind is None:
            continue
        ref = ReferencedArtifact(kind=kind, artifact_id=_bare_id(urn), urn=urn)
        if kind not in CHARTER_ACTIVATABLE_KINDS:
            kind_filtered.append(ref)
            continue
        activatable.append(ref)
    activatable.sort(key=lambda r: (r.kind.value, r.artifact_id))
    kind_filtered.sort(key=lambda r: (r.kind.value, r.artifact_id))
    return activatable, kind_filtered


# ---------------------------------------------------------------------------
# Referenced-artifact record (no-cascade warning + activation report)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReferencedArtifact:
    """A single artifact referenced from an activation source.

    Carries both the bucketed kind and the bare config ID so the CLI can render a
    per-kind list and the engine can fold IDs into ``cascade_targets``.
    """

    kind: ArtifactKind
    artifact_id: str
    urn: str


# ---------------------------------------------------------------------------
# T049 — scoped cascade activation (FR-014, Contract C3.3)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CascadeActivationResult:
    """Outcome of a scoped cascade activation.

    Attributes
    ----------
    activated:
        Kind → sorted bare IDs that fall **within** scope and were selected for
        activation. ``--cascade all`` returns every referenced kind here.
    skipped_by_scope:
        Kind → sorted bare IDs that were referenced but fall **outside** scope.
        These are reported so the operator sees exactly what the explicit scope
        excluded (auditability, R-005).
    not_cascaded_kind_filtered:
        Kind → sorted bare IDs that were reached but are structurally
        non-activatable (``template``/``asset``, C-001) — collected by the
        shared :func:`_referenced_artifacts` seam instead of being silently
        dropped (issue #3705, FR-001/FR-002). Never overlaps ``activated`` or
        ``skipped_by_scope`` (C-006).
    """

    activated: dict[str, list[str]] = field(default_factory=dict)
    skipped_by_scope: dict[str, list[str]] = field(default_factory=dict)
    not_cascaded_kind_filtered: dict[str, list[str]] = field(default_factory=dict)


def cascade_activation_targets(
    graph: DRGGraph,
    source_urn: str,
    scope: CascadeScope,
) -> CascadeActivationResult:
    """Compute scoped cascade activation targets for *source_urn* (FR-014).

    Walks the DRG forward along :data:`_REFERENCE_RELATIONS` from *source_urn*,
    buckets the referenced artifact-kind nodes by kind, and partitions them by
    *scope*: kinds the scope selects go to ``activated``; kinds it does not go to
    ``skipped_by_scope``. ``--cascade all`` selects every referenced kind. Pure
    graph logic — the partition branches only on :meth:`CascadeScope.selects`,
    never on a specific kind (FR-016).

    Parameters
    ----------
    graph:
        The merged DRG (already validated upstream).
    source_urn:
        Full URN of the artifact being activated (e.g.
        ``"agent_profile:python-pedro"``).
    scope:
        The explicit cascade scope (never ``None`` here — the caller routes the
        no-cascade case to :func:`referenced_but_not_cascaded`).

    Returns
    -------
    CascadeActivationResult
        Per-kind activated IDs and per-kind skipped-by-scope IDs, each list
        sorted for deterministic rendering.
    """
    activatable, kind_filtered = _referenced_artifacts(graph, source_urn)
    in_scope = [ref for ref in activatable if scope.selects(ref.kind)]
    out_of_scope = [ref for ref in activatable if not scope.selects(ref.kind)]
    activated = _bucket_by_kind(in_scope)
    skipped = _bucket_by_kind(out_of_scope)
    not_cascaded_kind_filtered = _bucket_by_kind(kind_filtered)
    return CascadeActivationResult(
        activated=activated,
        skipped_by_scope=skipped,
        not_cascaded_kind_filtered=not_cascaded_kind_filtered,
    )


# ---------------------------------------------------------------------------
# T050 — no-cascade warning (FR-013, Contract C3.2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NoCascadeReport:
    """The data the CLI needs to warn when ``--cascade`` is absent (FR-013).

    Attributes
    ----------
    source_urn:
        The artifact that was activated directly.
    skipped:
        Per-kind sorted bare IDs that *would* have cascaded but were not
        activated (because no ``--cascade`` was supplied).
    not_cascaded_kind_filtered:
        Per-kind sorted bare IDs of referenced nodes that are structurally
        non-activatable (``asset``/``template``, ADR 2026-08-20-1) and so
        were never candidates for cascading regardless of ``--cascade``
        (FR-005, mission ``cascade-asset-silent-drop-01M0RME0`` WP03). Same
        kind -> sorted-bare-IDs shape as ``skipped``, but a *distinct* reason:
        re-running with ``--cascade`` would not activate these.
    recovery_hint:
        Actionable recovery string naming the ``--cascade`` re-run and the
        consistency-check (Contract C3.2).
    """

    source_urn: str
    skipped: dict[str, list[str]] = field(default_factory=dict)
    not_cascaded_kind_filtered: dict[str, list[str]] = field(default_factory=dict)
    recovery_hint: str = _NO_CASCADE_HINT

    @property
    def has_skipped(self) -> bool:
        """``True`` when there is anything for the no-cascade warning to report.

        FR-005a (mission ``cascade-asset-silent-drop-01M0RME0`` WP03): checks
        BOTH ``skipped`` and ``not_cascaded_kind_filtered`` -- a source whose
        ONLY referenced nodes are kind-filtered leaves ``skipped`` empty, and
        the original ``any(self.skipped.values())``-only check returned
        ``False`` here, short-circuiting the caller's render loop before it
        was ever reached: the exact silent-drop bug #3705 reports, one level
        up, inside this mission's own fix. Additive to the existing check
        (NFR-004) -- a source with only activatable-kind skipped refs (the
        pre-existing case) still triggers this exactly as before.
        """
        return any(self.skipped.values()) or any(self.not_cascaded_kind_filtered.values())


def referenced_but_not_cascaded(
    graph: DRGGraph,
    source_urn: str,
) -> NoCascadeReport:
    """Return the referenced-but-not-cascaded artifacts for the no-cascade warning.

    The FR-013 path: when ``charter activate`` runs **without** ``--cascade``, the
    direct activation still completes, but the operator should be warned about the
    referenced artifacts that were *not* activated. This returns those artifacts
    bucketed by kind plus a recovery hint (Contract C3.2). Pure forward closure
    over :data:`_REFERENCE_RELATIONS`; no per-kind logic.

    Parameters
    ----------
    graph:
        The merged DRG.
    source_urn:
        Full URN of the artifact that was activated directly.

    Returns
    -------
    NoCascadeReport
        The skipped reference kinds (sorted IDs), the kind-filtered reference
        kinds (sorted IDs, FR-005), and the recovery hint. When the source
        references nothing at all, both ``skipped`` and
        ``not_cascaded_kind_filtered`` are empty and ``has_skipped`` is
        ``False`` (the caller emits no warning).
    """
    activatable, kind_filtered = _referenced_artifacts(graph, source_urn)
    skipped = _bucket_by_kind(activatable)
    not_cascaded_kind_filtered = _bucket_by_kind(kind_filtered)
    return NoCascadeReport(
        source_urn=source_urn,
        skipped=skipped,
        not_cascaded_kind_filtered=not_cascaded_kind_filtered,
    )


# ---------------------------------------------------------------------------
# T051 — shared-reference-safe deactivation (FR-015/016, C-005, Contract C3.4)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SharedSkip:
    """A cascade candidate skipped because it is still referenced (C-005).

    Attributes
    ----------
    urn:
        The shared candidate's URN (not deactivated).
    referencing_active_urn:
        A still-activated source that continues to reference *urn*. Named in the
        report so the operator understands *why* it was kept (Contract C3.4).
    """

    urn: str
    referencing_active_urn: str


@dataclass(frozen=True)
class DeactivationPlan:
    """Result of a shared-reference-safe cascade deactivation (FR-015/016).

    Attributes
    ----------
    deactivate:
        Sorted URNs of cascade candidates that are **exclusive** to the removed
        target (unreachable from every other still-activated source) and may be
        deactivated.
    skipped_shared:
        :class:`SharedSkip` records for candidates that remain reachable from
        another still-activated source — kept (never removed) with the
        referencing source named (Contract C3.4, no silent removal).
    not_cascaded_kind_filtered:
        Kind → sorted bare IDs of nodes reached by the candidate collection
        that are structurally non-activatable (``template``/``asset``, C-001)
        — collected by the shared :func:`_referenced_artifacts` seam instead
        of being silently dropped (issue #3705, FR-007). Unified to the same
        kind → sorted-bare-IDs shape as ``CascadeActivationResult``'s and
        ``NoCascadeReport``'s equivalent fields (issue #3772): the flat
        ``list[str]`` of URNs this field previously carried rendered
        identically only through a colon-boundary lexical-order coincidence,
        and any non-render consumer would have seen two different payloads
        under one field name. Never overlaps ``deactivate`` or any
        ``SharedSkip`` in ``skipped_shared`` (C-006).
    """

    deactivate: list[str] = field(default_factory=list)
    skipped_shared: list[SharedSkip] = field(default_factory=list)
    not_cascaded_kind_filtered: dict[str, list[str]] = field(default_factory=dict)


def deactivation_plan(
    graph: DRGGraph,
    target_urn: str,
    scope: CascadeScope,
    *,
    active_urns: set[str],
) -> DeactivationPlan:
    """Compute a shared-reference-safe cascade deactivation plan (FR-015/016, C-005).

    The candidate set is the in-scope artifacts referenced (forward closure over
    :data:`_REFERENCE_RELATIONS`) by *target_urn*. A candidate is **exclusive** —
    and therefore safe to deactivate — iff it is unreachable from **every** other
    still-activated source once *target_urn* is removed from the active set.
    Exclusivity is determined by reverse reachability over the merged DRG: the
    candidate is kept if it lies in the forward reference closure of any remaining
    active source. Shared candidates are recorded in ``skipped_shared`` with the
    still-referencing active source named, and are **never** removed (Contract
    C3.4, I-AC2). Pure graph logic — no ``kind ==`` branches (FR-016, I-AC3).

    Parameters
    ----------
    graph:
        The merged DRG.
    target_urn:
        Full URN of the artifact being deactivated.
    scope:
        Cascade scope limiting which referenced kinds are candidates for
        cascade deactivation.
    active_urns:
        The set of currently-activated source URNs (the activation set *before*
        this deactivation). *target_urn* is removed from this set when computing
        the "other still-activated sources" so its own references never keep a
        candidate alive.

    Returns
    -------
    DeactivationPlan
        ``deactivate`` (sorted exclusive URNs) and ``skipped_shared``
        (sorted by candidate URN).
    """
    adj = _reference_adjacency(graph.edges)

    # Candidate set: in-scope artifacts referenced by the target.
    candidates: set[str] = set()
    activatable, kind_filtered = _referenced_artifacts(graph, target_urn)
    for ref in activatable:
        if scope.selects(ref.kind):
            candidates.add(ref.urn)

    # FR-007 (issue #3705): report the kind-filtered nodes the shared
    # `_referenced_artifacts` seam collected instead of silently dropping
    # them — the deactivation-side half of C-002's cross-command symmetry
    # (ADR 2026-08-20-1). Populated from `kind_filtered` directly, never
    # through the `scope.selects()`-gated candidate loop above (C-006): a
    # kind-filtered node was never a deactivation candidate and this does
    # not change that, it only reports what was reached. Kind-bucketed
    # through the same `_bucket_by_kind` seam as the activate-side fields
    # (issue #3772).
    not_cascaded_kind_filtered = _bucket_by_kind(kind_filtered)

    # Remaining active sources (target excluded — its references must not keep a
    # candidate alive). For each remaining source, the set of artifacts it still
    # reaches; mapped back so we can name a referencing source for shared skips.
    remaining_sources = active_urns - {target_urn}
    reachable_by_source: dict[str, set[str]] = {
        source: _forward_reference_closure(adj, {source})
        for source in remaining_sources
    }

    deactivate: list[str] = []
    skipped_shared: list[SharedSkip] = []
    for candidate in candidates:
        # Find a still-active source (deterministic: lowest URN) that still
        # references the candidate. If one exists the candidate is shared.
        referencing = sorted(
            source
            for source, reached in reachable_by_source.items()
            if candidate in reached
        )
        if referencing:
            skipped_shared.append(
                SharedSkip(urn=candidate, referencing_active_urn=referencing[0])
            )
        else:
            deactivate.append(candidate)

    deactivate.sort()
    skipped_shared.sort(key=lambda s: s.urn)
    return DeactivationPlan(
        deactivate=deactivate,
        skipped_shared=skipped_shared,
        not_cascaded_kind_filtered=not_cascaded_kind_filtered,
    )
