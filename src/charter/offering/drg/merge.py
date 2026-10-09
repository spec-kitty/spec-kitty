"""Canonical three-layer DRG merge (doctrine-owned).

This module owns the **canonical relationship merge** for the Doctrine
Reference Graph (OQ-2(ii) / C-009). It overlays the built-in DRG with
organisation-tier fragments and an optional project-tier graph, producing a
single merged :class:`~charter.offering.drg.models.DRGGraph` whose nodes and edges
carry a declared ``provenance`` field.

Relocated from ``charter.drg`` (mission
``org-doctrine-profile-integrity-activation-closure-01KT1TV1`` WP03). The
merge is pure graph logic and depends only on the ``doctrine`` and ``kernel``
layers — it MUST NOT import from ``charter`` or ``specify_cli`` (layer rule,
``tests/architectural/test_layer_rules.py``). Charter retains the
activation-aware filtering/aggregation (``filter_graph_by_activation``) and
re-exports the public names below so existing ``from charter.drg import …``
call sites keep working.

Provenance semantics (data-model.md §2):

* ``"built-in"`` — built-in layer (Mission A);
* ``"org:<pack_name>"`` — contributed by an :class:`OrgDRGFragment`;
* ``"project"`` — contributed by the project layer.

FR-003 (this WP): an org/project fragment edge whose relation label is not a
canonical :class:`Relation` member (or a known alias) now raises a structured
:class:`UnknownRelationError` instead of being silently dropped. This brings
the org-fragment path to parity with the project-fragment Pydantic path, which
already rejects unknown relations loudly. A valid ``specializes_from`` lineage
edge (WP02 added the enum member) resolves identically across shipped, org, and
project tiers.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal, TypeVar

from pydantic import BaseModel

from charter.offering.drg.models import (
    DRGEdge,
    DRGGraph,
    DRGNode,
    NodeKind,
    Relation,
    is_valid_urn,
)
from charter.offering.drg.org_pack_loader import ORG_PLURAL_TO_SINGULAR_KIND, OrgDRGFragment

# WP04 (org-doctrine-profile-integrity-closeout): ``_tag_source`` is generic
# over the concrete frozen-model type so callers (DRGNode / DRGEdge) retain
# their precise type through provenance tagging instead of being widened to
# ``BaseModel`` (which produced 4 ``mypy --strict`` errors at the merge sites).
# Python 3.11 has no PEP 695 inline syntax, so a module-level ``TypeVar`` is used.
_ModelT = TypeVar("_ModelT", bound=BaseModel)

__all__ = [
    "OrgDRGConflict",
    "OrgDRGConflictError",
    "UnknownRelationError",
    "bridge_org_edge_to_drg_edge",
    "merge_three_layers",
]

_logger = logging.getLogger(__name__)


# FR-010 (WP08): the plural -> singular map used to be a hand-restated copy of
# the org-pack kind universe living HERE, and it had drifted two kinds behind
# its source — a pack declaring a ``mission_types`` or ``glossary_packs`` node
# crashed the merge with a bare ``KeyError``. It is now
# ``ORG_PLURAL_TO_SINGULAR_KIND``, derived beside the universe it inverts
# (``org_pack_loader._derive_plural_to_singular``), so a kind admitted to
# ``_ORG_DRG_KIND_ALIASES`` without a singular fails at import rather than
# mid-merge. Read that name directly at the call site — do NOT re-alias it
# here, or this module quietly becomes the restatement again.


#: Operator-friendly relation aliases mapping a fragment-authored verb to a
#: canonical :class:`Relation`. ``refines`` is NO LONGER aliased — it is now a
#: first-class ``Relation.REFINES`` (#2079) and resolves via the canonical
#: branch in :func:`_resolve_relation`. ``extends`` is overlay-inheritance
#: language and maps to ``Relation.SPECIALIZES_FROM`` (lineage), NOT to the inert
#: ``Relation.APPLIES`` sink. INVARIANT: an alias MUST NOT map to
#: ``Relation.APPLIES`` — no *activation* traversal follows ``APPLIES``, so aliasing
#: an authored relation onto it silently turns the edge into a no-op for cascade and
#: context resolution (the #2079 defect class). An earlier revision of this comment
#: said "no traversal reads APPLIES", which is false and is what allowed WP09's
#: defect to ship: ``orphan.py``'s ``directive`` rule reads it and ``project_drg.py``
#: emits it. Neither saved the retyped edge, whose target is a ``procedure``.
_RELATION_ALIASES: dict[str, Relation] = {
    "extends": Relation.SPECIALIZES_FROM,
}


# ---------------------------------------------------------------------------
# Conflict reporting (FR-004, FR-005)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OrgDRGConflict:
    """A typed conflict report for built-in/org/project layer disagreements.

    Per data-model §3:

    * ``edge_override`` — an org fragment edge collides with a built-in edge.
    * ``node_override`` — an org fragment node collides with a built-in node.
    * ``kind_mismatch`` — an org fragment node declares a kind not in the
      8-kind universe (in practice this is caught at validation time by
      ``_OrgDRGNode`` in ``charter.offering.drg.org_pack_loader``).
    * ``layer_rule_violation`` — a node body_path / import reaches across
      the architectural layer boundary (C-001 binding).
    * ``unresolved_edge_endpoint`` — FR-010. An edge endpoint names nothing
      the merge can bind: not a node the fragment declares, not a URN whose
      kind prefix is a :class:`NodeKind`, and not a bare id present in any
      already-merged layer. Before WP08 this shape was returned as ``None``
      and dropped without warning or record — ADR ``2026-07-26-3``'s
      silent-drop path.
    * ``ambiguous_edge_endpoint`` — FR-010. A bare endpoint id resolves to
      more than one kind (e.g. both ``directive:x`` and ``tactic:x`` exist).
      Before WP08 the directive interpretation always silently won, because
      an unresolved bare target was minted as ``directive:<id>`` outright.
    * ``malformed_urn`` — FR-010. A URN the bridge would have to mint or
      forward is not syntactically valid
      (``charter.offering.drg.models.is_valid_urn``). Before WP08 this escaped as a
      raw ``pydantic_core.ValidationError`` from inside the merge rather than
      as a typed pack error.

    ``target_id`` carries the offending token itself for the three FR-010
    kinds and ``org_value`` the edge/node that declared it — so ``kind`` says
    *why*, ``target_id`` says *which token*, and ``org_value`` says *where*.

    ``resolution_applied`` values:

    * ``hard_fail`` — the merge raises :class:`OrgDRGConflictError`.
    * ``built_in_wins`` — silent precedence (the built-in value is retained).
    * ``project_wins`` — silent precedence (the project value is retained).
    * ``org_override`` — a SAME-KIND org node permissibly substitutes a built-in
      node in place (the org value wins, with a WARNING for operator visibility).
      Non-fatal: the merge does NOT raise. Whether a given repo *tolerates* this
      override is a per-repo governance TEST (see
      ``tests/architectural/test_builtin_override_policy.py``), not a merge-time
      prohibition.
    """

    kind: Literal[
        "edge_override",
        "node_override",
        "kind_mismatch",
        "layer_rule_violation",
        "unresolved_edge_endpoint",
        "ambiguous_edge_endpoint",
        "malformed_urn",
    ]
    conflicting_layers: list[str]
    target_id: str
    built_in_value: Any | None
    org_value: Any
    project_value: Any | None
    resolution_applied: Literal[
        "hard_fail", "built_in_wins", "project_wins", "org_override"
    ]


#: Per-conflict-class operator remediation, rendered by
#: :meth:`OrgDRGConflictError._format_message` for the classes actually
#: present. Every :attr:`OrgDRGConflict.kind` needs an entry — a class with no
#: remediation hands the operator a label and no way to act on it (the gate is
#: ``test_every_conflict_class_carries_a_remediation_line``).
_OVERRIDE_REMEDIATION = (
    "Remediation (override): remove the override from the org pack, OR "
    "escalate the built-in invariant change via a spec-kitty governance "
    "proposal."
)

_CONFLICT_REMEDIATIONS: dict[str, str] = {
    "edge_override": _OVERRIDE_REMEDIATION,
    "node_override": _OVERRIDE_REMEDIATION,
    "layer_rule_violation": (
        "Remediation (layer rule): an org-pack node must not reference "
        "src/specify_cli/ — doctrine sits below the runtime layer."
    ),
    "kind_mismatch": (
        "Remediation (kind): declare the node under a canonical org-pack "
        "plural kind (charter.offering.drg.org_pack_loader._ORG_DRG_KIND_ALIASES)."
    ),
    "unresolved_edge_endpoint": (
        "Remediation (endpoint): an edge endpoint must be either a bare id "
        "the fragment declares in its own nodes:, or a fully-qualified DRG "
        "URN '<kind>:<id>' whose <kind> is a NodeKind member (e.g. "
        "'agent_profile:researcher-ryan'). Nothing else resolves."
    ),
    "ambiguous_edge_endpoint": (
        "Remediation (ambiguity): this bare id exists under more than one "
        "kind. Qualify it as '<kind>:<id>' to say which one you mean."
    ),
    "malformed_urn": (
        "Remediation (URN syntax): a URN is '<lower_snake_kind>:<id>' where "
        "the id may contain letters, digits, '_', '/', '.' and '-' only."
    ),
}


class OrgDRGConflictError(Exception):
    """Raised when an org-DRG fragment violates the layer rule or
    overrides a built-in invariant in a non-recoverable way.

    Carries one or more :class:`OrgDRGConflict` records. The message is
    operator-actionable and lists each conflict's kind, target, layers,
    and applied resolution.

    **Mixed payload.** :func:`merge_three_layers` accumulates *every* conflict
    it finds and raises with the whole list as soon as any one of them is
    ``hard_fail``, so an instance routinely carries advisory records
    (``org_override`` and friends — permitted precedence the operator should
    still see) next to the fatal refusals that caused the raise. Splitting this
    into two exception types was considered and rejected: the merge would have
    to either discard the advisory records or raise a type carrying both
    anyway, which is this type. What was actually missing is a *reader* for the
    ``resolution_applied`` discriminant — every consumer had to re-derive the
    partition from a ``Literal`` string and every consumer skipped it, which is
    how a refused pack came to be reported healthy. :attr:`hard_failures` and
    :attr:`advisory_conflicts` put that partition on the type that owns the
    invariant, so a caller routes by severity instead of by convention.
    """

    def __init__(self, conflicts: list[OrgDRGConflict]):
        self.conflicts = list(conflicts)
        super().__init__(self._format_message(self.conflicts))

    @property
    def hard_failures(self) -> list[OrgDRGConflict]:
        """The conflicts that made the merge refuse — never empty in practice.

        These are fatal: the merged graph does not exist, so anything a caller
        would have computed *from* it (completeness checks, override
        adjudication) did not run either. A caller must surface these on
        whatever channel its health verdict reads, not on an advisory one.
        """
        return [c for c in self.conflicts if c.resolution_applied == "hard_fail"]

    @property
    def advisory_conflicts(self) -> list[OrgDRGConflict]:
        """The conflicts that were resolved by precedence, not refused.

        ``built_in_wins`` / ``project_wins`` / ``org_override`` — reportable for
        operator visibility, but they did not cause the raise and must not be
        escalated to an error by a caller that cannot tell them apart.
        """
        return [c for c in self.conflicts if c.resolution_applied != "hard_fail"]

    @property
    def hard_failure_messages(self) -> list[str]:
        """One flat operator-readable line per fatal refusal.

        The CLI collectors report findings on a ``list[str]`` errors channel
        (that is what ``CharterPackHealthReport.healthy`` reads). Formatting lives
        here, next to :meth:`_format_message`, so the three collectors share one
        wording instead of each inventing its own.
        """
        return [
            f"org-DRG hard failure: {c.kind} target={c.target_id} "
            f"layers={c.conflicting_layers}"
            for c in self.hard_failures
        ]

    @staticmethod
    def _format_message(conflicts: list[OrgDRGConflict]) -> str:
        lines = [f"{len(conflicts)} org-DRG conflict(s):"]
        for c in conflicts:
            lines.append(
                f"  - kind={c.kind}, target_id={c.target_id}, "
                f"layers={c.conflicting_layers}, resolution={c.resolution_applied}"
            )
        # One remediation per conflict class actually present, so an
        # operator is never told to "remove the override" for what is really
        # a typo'd edge endpoint (FR-010 — guidance has to be followable).
        present = {c.kind for c in conflicts}
        for kind, remediation in _CONFLICT_REMEDIATIONS.items():
            if kind in present and remediation not in lines:
                lines.append(remediation)
        return "\n".join(lines)


class UnknownRelationError(Exception):
    """Raised when a fragment edge declares an unrecognised relation label (FR-003).

    Before this WP the org-fragment bridge silently returned ``None`` for an
    unknown relation, dropping the edge without trace, while the project-tier
    Pydantic path rejected the same input loudly. C0.3 normalises the
    asymmetry: an org or project fragment edge whose ``relation`` is neither a
    canonical :class:`Relation` value nor a known alias now fails closed with a
    structured, operator-actionable error that names the offending relation,
    the source fragment, and the valid token set. A valid ``specializes_from``
    lineage edge (and every other canonical relation) is unaffected.
    """

    def __init__(self, relation: str, source_marker: str) -> None:
        self.relation = relation
        self.source_marker = source_marker
        self.valid_relations = sorted(r.value for r in Relation)
        self.valid_aliases = sorted(_RELATION_ALIASES)
        super().__init__(
            f"Unknown DRG relation {relation!r} in fragment {source_marker!r}: "
            f"not a canonical relation and not a known alias. "
            f"Valid relations: {self.valid_relations}. "
            f"Valid aliases: {self.valid_aliases}. "
            "Remediation: use one of the valid relations/aliases, or extend "
            "the Relation enum via a spec-kitty governance proposal."
        )


#: Structured, testable error codes (NFR-005) for the global URN-uniqueness
#: scan (FR-008/FR-004, D-04 revised). Keyed by URN prefix so
#: :func:`_check_node_urn_unique` stays reusable if a future kind is added to
#: the node-declarable-but-not-augmentation-eligible set.
_DUPLICATE_URN_ERROR_CODES: dict[str, str] = {
    "asset:": "duplicate_asset_id",
    "template:": "duplicate_template_id",
}

#: The node-declarable-but-not-augmentation-eligible kinds the global
#: uniqueness scan covers (D-04 revised / research.md D-03). Expressed as
#: :class:`NodeKind` members (built-in/project layers) and as the org-pack
#: canonical plural strings (org layer, pre-bridge) respectively.
_URN_UNIQUENESS_NODE_KINDS: frozenset[NodeKind] = frozenset(
    {NodeKind.ASSET, NodeKind.TEMPLATE}
)
_URN_UNIQUENESS_ORG_KINDS: frozenset[str] = frozenset({"assets", "templates"})


class DuplicateURNError(Exception):
    """Raised when an ``asset:``/``template:`` URN occurs more than once
    anywhere in the merged three-layer node set (FR-008/FR-004, NFR-005).

    TEMPLATE and ASSET are node-declarable but NOT augmentation-eligible
    (D-04 revised, ``research.md``): a same-URN collision for either kind
    carries no legitimate override/augmentation meaning, so it is genuine
    author ambiguity and fails loud with a distinct, structured, testable
    ``code`` — ``duplicate_asset_id`` or ``duplicate_template_id`` — instead
    of being silently resolved by the layered-override machinery the other 9
    kinds rely on (org-vs-org first-wins in :func:`_merge_org_fragment`,
    built-in-vs-org override in :func:`_resolve_builtin_collision`, and the
    project-vs-any override in :func:`merge_three_layers`). That machinery is
    untouched for the other 9 kinds — this scan is scoped strictly by URN
    prefix (``drg/models.py`` enforces URN-prefix == kind, so an
    ``asset:``/``template:`` URN can only ever collide with its own kind).
    """

    def __init__(self, code: str, urn: str, count: int) -> None:
        self.code = code
        self.urn = urn
        self.count = count
        super().__init__(
            f"{code}: URN {urn!r} appears {count} times across the merged "
            "built-in/org/project layers — asset and template ids must be "
            "globally unique. Remediation: rename the id in one of the "
            "colliding packs/layers."
        )


# ---------------------------------------------------------------------------
# Provenance tagging
# ---------------------------------------------------------------------------


def _tag_source(obj: _ModelT, source: str) -> _ModelT:
    """Return a copy of *obj* with its declared ``provenance`` field set.

    DRGNode / DRGEdge now declare a typed ``provenance: str | None`` field
    (FR-013, D2-revised). Provenance is set via ``model_copy(update=...)`` so
    the field is populated through the model's own validation surface instead
    of the former ``object.__setattr__`` sidecar. Consumers read the field
    directly (``node.provenance``) or, where the graph object is duck-typed,
    via ``getattr(node, "provenance", None)``.

    .. note::
        The field is named ``provenance`` (NOT ``source``) to avoid colliding
        with ``DRGEdge.source``, which is the source-endpoint URN. Using
        ``source`` as the marker name caused an earlier sidecar to silently
        overwrite the endpoint URN on every merged edge (P0 bug, Robert review
        2026-05).
    """
    return obj.model_copy(update={"provenance": source})


# ---------------------------------------------------------------------------
# Layer rule + invariants
# ---------------------------------------------------------------------------


def _violates_layer_rule(node: Any) -> bool:
    """C-001 / FR-005 — an org node reaching across the layer boundary.

    Conservative heuristic: any reference (in ``body_path`` or other text
    fields) to ``src/specify_cli/`` or ``specify_cli.`` is treated as a
    smuggling attempt. False positives surface as operator-actionable
    errors; an org pack should never legitimately reference the runtime layer.
    """
    text_blobs: list[str] = []
    if node.body_path:
        text_blobs.append(node.body_path)
    if node.title:
        text_blobs.append(node.title)
    text_blobs.append(node.id)
    return any(
        "src/specify_cli/" in blob or "specify_cli." in blob for blob in text_blobs
    )


def _built_in_invariant_ids(built_in: DRGGraph) -> frozenset[str]:
    """The set of built-in URNs that an org node may collide with.

    Every built-in node URN is returned. A collision is no longer an automatic
    hard-fail: an org node whose URN matches a built-in URN **and whose kind
    matches** is permitted to override the built-in in place (permitted-but-
    visible — a ``node_override`` conflict with ``resolution_applied =
    "org_override"`` is recorded and a WARNING is emitted). A collision whose
    kind DIFFERS (kind-drift) still hard-fails: an override may replace a
    built-in's content, never its kind. Layer-rule violations also still
    hard-fail.

    Whether a given repo *tolerates* a built-in override is a per-repo
    governance TEST (``tests/architectural/test_builtin_override_policy.py``
    consults ``.kittify/charter-packs/replaceable-builtins.yaml``), not a merge-time
    prohibition.
    """
    return frozenset(n.urn for n in built_in.nodes)


# ---------------------------------------------------------------------------
# Fragment → DRG bridging
# ---------------------------------------------------------------------------


def _bridge_org_node_to_drg_node(
    node: Any, source: str
) -> tuple[str, DRGNode] | OrgDRGConflict:
    """Mint a URN-shaped :class:`DRGNode` from a fragment-side node.

    URN convention: ``<singular_kind>:<id>`` (e.g. ``directive:sox-controls``).
    The ``source`` is attached via :func:`_tag_source`.

    FR-010: both failure modes now return a typed :class:`OrgDRGConflict`
    instead of escaping as a raw exception —

    * an unmappable plural kind (``ORG_PLURAL_TO_SINGULAR_KIND`` has no entry)
      used to raise a bare ``KeyError``;
    * an ``id`` that cannot form a syntactically valid URN — ``_OrgDRGNode.id``
      is a free-form ``str`` — used to raise ``pydantic_core.ValidationError``
      from inside :class:`DRGNode` construction.

    Returns:
        ``(urn, drg_node)`` on success, or the :class:`OrgDRGConflict` that
        explains the refusal.
    """
    singular = ORG_PLURAL_TO_SINGULAR_KIND.get(node.kind)
    if singular is None:
        return OrgDRGConflict(
            kind="kind_mismatch",
            conflicting_layers=[source],
            target_id=node.kind,
            built_in_value=None,
            org_value=node.model_dump(),
            project_value=None,
            resolution_applied="hard_fail",
        )
    urn = f"{singular}:{node.id}"
    if not is_valid_urn(urn):
        return OrgDRGConflict(
            kind="malformed_urn",
            conflicting_layers=[source],
            target_id=urn,
            built_in_value=None,
            org_value=node.model_dump(),
            project_value=None,
            resolution_applied="hard_fail",
        )
    drg_node = DRGNode(urn=urn, kind=NodeKind(singular), label=node.title)
    return urn, _tag_source(drg_node, source)


def _resolve_relation(relation_value: str, source_marker: str) -> Relation:
    """Resolve a fragment edge relation label to a canonical :class:`Relation`.

    FR-003: a label that is neither a canonical relation value nor a known
    alias raises :class:`UnknownRelationError` (fail closed) rather than
    dropping the edge silently.
    """
    canonical_relations = {r.value for r in Relation}
    if relation_value in canonical_relations:
        return Relation(relation_value)
    if relation_value in _RELATION_ALIASES:
        return _RELATION_ALIASES[relation_value]
    raise UnknownRelationError(relation_value, source_marker)


#: The ``NodeKind`` prefixes a fully-qualified endpoint may carry. Derived
#: from the enum so a new kind is addressable the moment it is declared.
_NODE_KIND_PREFIXES: frozenset[str] = frozenset(kind.value for kind in NodeKind)

#: The subset of :attr:`OrgDRGConflict.kind` an endpoint refusal can produce.
#: A narrowed alias (rather than the full literal) so the resolver's return
#: type states exactly which records it is able to emit.
_EndpointConflictKind = Literal[
    "unresolved_edge_endpoint",
    "ambiguous_edge_endpoint",
    "malformed_urn",
]


class _EndpointResolutionError(Exception):
    """Internal control-flow signal: an edge endpoint could not be bound.

    Private to this module. :func:`_resolve_edge_endpoint` raises it so its
    success type stays a plain ``str`` — returning ``(str | None, kind | None)``
    would force every caller to re-assert a correlation the type system cannot
    see, and an unreachable "impossible" branch is exactly the inert code this
    mission removes. :func:`bridge_org_edge_to_drg_edge` converts it into the
    caller-visible :class:`OrgDRGConflict`; it never escapes the module.
    """

    def __init__(self, conflict_kind: _EndpointConflictKind, raw: str) -> None:
        self.conflict_kind = conflict_kind
        self.raw = raw
        super().__init__(f"cannot resolve DRG edge endpoint {raw!r}: {conflict_kind}")


def _resolve_edge_endpoint(
    raw: str,
    node_id_to_urn: Mapping[str, str],
    built_in_urns: Collection[str],
) -> str:
    """Resolve one fragment-authored edge endpoint to a canonical URN (FR-010).

    **One policy, both endpoints.** The bridge previously ran two different
    and asymmetric rules — a source had to be a fragment-local node id (miss →
    silently dropped) while a target fell back to ``directive:<id>`` (miss → a
    phantom node of an invented kind). That asymmetry is the structural cause
    of the mission's D1, D2, D3 and D5 defects, so it is replaced by a single
    ordered precedence applied to both:

    1. **Fragment-local bare id** — the pack's own node, its nearest scope.
    2. **Fully-qualified URN** — ``<kind>:<id>`` where ``<kind>`` is a
       :class:`NodeKind` member and the whole token is syntactically valid.
       Accepted verbatim: it is unambiguous by construction, and it is exactly
       what ``org_pack_loader._collect_augmentation_edges`` emits.
    3. **Bare id resolvable against the BUILT-IN layer** — matched on the id
       half of a built-in URN, which recovers the *declared* kind instead of
       inventing one. Exactly one match resolves; more than one is ambiguous.

    Rule 3 reads the built-in layer ONLY, never the running merge state. Were
    it to consult earlier fragments, whether a pack's bare cross-pack
    reference resolved would depend on the operator's ``charter_packs.org.packs``
    ordering — an order-dependent graph is a silent-difference generator of
    the same family this mission closes. Cross-pack references must be
    qualified (rule 2), which is order-independent by construction.

    Existence is deliberately NOT required for case 2: a fully-qualified
    endpoint may legitimately name a node contributed by a *later* layer (the
    project layer merges after the org fragments) or by a sibling pack this
    merge did not load, so at mint time the question is genuinely unanswerable.
    The check is therefore **deferred, not dropped** — see
    :func:`_dangling_org_endpoints`, which :func:`merge_three_layers` runs once
    every layer is in.

    An earlier revision of this docstring named :mod:`charter.offering.drg.validator`
    as the owner and stopped there. The reasoning was right but the control did
    not run: no production caller of :func:`merge_three_layers` invoked
    ``validate_graph``/``assert_valid``, so a typo in a qualified endpoint
    merged clean as a dangling edge with nothing said. Deferring to a control
    the call graph never reaches is the same silence this mission closes, one
    layer up.

    Args:
        raw: The endpoint token exactly as the fragment author wrote it.
        node_id_to_urn: Bare id -> minted URN for this fragment's own nodes.
        built_in_urns: Every built-in node URN — a fixed, order-independent
            index.

    Returns:
        The canonical URN the endpoint binds to.

    Raises:
        _EndpointResolutionError: when the endpoint binds to nothing, to more
            than one kind, or is a malformed URN.
    """
    local = node_id_to_urn.get(raw)
    if local is not None:
        return local

    prefix, separator, _ = raw.partition(":")
    if separator and prefix in _NODE_KIND_PREFIXES:
        if is_valid_urn(raw):
            return raw
        # URN-shaped and a real kind, but unparseable — a typed pack error,
        # not a raw pydantic failure surfacing from DRGEdge construction.
        raise _EndpointResolutionError("malformed_urn", raw)

    matches = sorted(
        {urn for urn in built_in_urns if ":" in urn and urn.partition(":")[2] == raw}
    )
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise _EndpointResolutionError("ambiguous_edge_endpoint", raw)
    raise _EndpointResolutionError("unresolved_edge_endpoint", raw)


def _endpoint_conflict(
    conflict_kind: _EndpointConflictKind, raw: str, edge: Any, source: str
) -> OrgDRGConflict:
    """Build the typed record for an endpoint the bridge refused to bind."""
    return OrgDRGConflict(
        kind=conflict_kind,
        conflicting_layers=[source],
        target_id=raw,
        built_in_value=None,
        org_value=edge.model_dump(),
        project_value=None,
        resolution_applied="hard_fail",
    )


@dataclass(frozen=True)
class _OrgEdgeContribution:
    """One org-contributed edge, kept next to the fragment edge that authored it.

    :func:`_resolve_edge_endpoint` accepts a fully-qualified endpoint verbatim
    without proving it exists, because a later layer may still supply the node.
    Collecting that deferral needs two things the merged :class:`DRGEdge` alone
    cannot give back: the *authored* fragment edge (so the conflict record can
    show the operator the declaration they wrote, ``reason`` field and all) and
    the ``org:<pack>`` marker that names which pack to go fix.
    """

    minted: DRGEdge
    authored: Any
    source_marker: str


class _OrgEdgeCollector:
    """Owns edge identity for the org layer: one triple, one edge.

    An edge IS its ``(source, target, relation)`` triple — that is already the
    graph's own identity notion (:func:`charter.offering.drg.validator.validate_graph`
    calls a repeated triple an error), so the same relationship declared twice
    must contribute one edge, with the first declaring pack keeping provenance
    exactly as org-vs-org node collisions do.

    This used to be attempted in ``org_pack_loader.load_org_pack``, which
    reconciled the field-projection edges against the fragment-authored ones.
    But it keyed on the RAW, pre-resolution endpoint strings, and once endpoint
    canonicalisation moved into :func:`_resolve_edge_endpoint` the bare and
    qualified spelling of one relationship became two keys resolving to one
    triple — so the merged graph got the edge twice.

    The loader could not fix that in place: resolving a bare id the fragment
    does not declare requires the BUILT-IN layer (rule 3), which the loader
    never sees. Identity therefore belongs *here*, after resolution — one
    authority rather than a partial one upstream that looked complete. Keying a
    second dedup on raw strings as well would just recreate the drift.

    The collapse keeps the FIRST contribution and drops the rest, so the loser's
    authored ``reason:`` is not the contribution of record — the merged
    :class:`DRGEdge` carries the endpoints and the relation, not either
    declaration's prose. That is silent for the routine
    restatements (see :func:`_warn_discarded_edge_rationale`) and loud for the
    one case where it destroys something an author wrote.
    """

    def __init__(self) -> None:
        self._contributions: list[_OrgEdgeContribution] = []
        self._kept: dict[tuple[str, str, str], _OrgEdgeContribution] = {}

    def add(self, minted: DRGEdge, authored: Any, source_marker: str) -> bool:
        """Record *minted* unless its triple was already contributed.

        Returns ``True`` when the caller should append the edge to the merged
        graph, ``False`` when it is a restatement of one already there.
        """
        key = (minted.source, minted.target, minted.relation.value)
        kept = self._kept.get(key)
        if kept is not None:
            _warn_discarded_edge_rationale(kept, authored, source_marker)
            return False
        contribution = _OrgEdgeContribution(minted, authored, source_marker)
        self._kept[key] = contribution
        self._contributions.append(contribution)
        return True

    @property
    def contributions(self) -> list[_OrgEdgeContribution]:
        """The surviving org contributions, in declaration order."""
        return self._contributions


def _warn_discarded_edge_rationale(
    kept: _OrgEdgeContribution,
    authored: Any,
    source_marker: str,
) -> None:
    """WARN when collapsing a restated edge would discard a distinct rationale.

    The dedup itself stays silent by design, and deliberately so: restating one
    relationship is *routine*. A field projection plus an explicit declaration,
    or a bare plus a qualified spelling, are both sanctioned authoring shapes
    that collapse on every healthy merge, so warning on the collapse would fire
    on correct packs — a gate that flags everything tells you nothing.

    What is not routine is a restatement that carries its OWN authored
    ``reason:``, different from the survivor's. Then the collapse is not
    deduplication, it is information loss: two governance authors documented the
    same relationship for different stated reasons and only the first survives
    as the contribution of record. An earlier revision defended that silence by
    pointing at org-vs-org *node* collisions, which are equally quiet. But that
    argues the node path is also wrong, not that this one is right — and a
    silent difference is the defect class this bridge exists to close.

    **Both sides must have been written by an author.** The predicate reads
    ``reason``, which
    :class:`charter.offering.drg.org_pack_loader._OrgDRGEdge` reserves for the author's
    own words: a field-projection edge carries its machine provenance on
    :class:`~charter.offering.drg.org_pack_loader._ProjectedOrgDRGEdge`'s separate
    ``generated_reason``, and ``extra="forbid"`` keeps YAML from writing there.
    So "has a ``reason``" IS "an author wrote a reason", structurally, with no
    string-matching against text this codebase itself emits.

    That matters because the shape it excludes is *healthy*, not marginal: a
    legacy ``enhances:`` field plus the explicit fragment edge that documents
    and will replace it is exactly what the loader's retained projection path
    exists to support during the migration window. Warning there discarded no
    author's words, named one pack as if it were two, and proposed the opposite
    of the right remedy (mint a second relationship, rather than delete the
    legacy field).

    Visible, not fatal — the merged edge is correct either way; only the
    operator's record of *why* is incomplete, and that is theirs to reconcile.
    """
    discarded_reason = getattr(authored, "reason", None)
    surviving_reason = getattr(kept.authored, "reason", None)
    if not discarded_reason or not surviving_reason:
        return
    if discarded_reason == surviving_reason:
        return
    edge = kept.minted
    if source_marker == kept.source_marker:
        _logger.warning(
            "Org doctrine %r declares the edge (%s --%s--> %s) twice with "
            "different reasons, so it is collapsed to one edge and only the "
            "first rationale survives. Discarded: %r (kept: %r). Keep one "
            "declaration and fold both rationales into it.",
            source_marker,
            edge.source,
            edge.relation.value,
            edge.target,
            discarded_reason,
            surviving_reason,
        )
        return
    _logger.warning(
        "Org doctrine %r restates the edge (%s --%s--> %s) already contributed "
        "by %r, so it is collapsed to one edge and only the first rationale "
        "survives. Discarded reason from %r: %r (kept: %r). Reconcile the two "
        "packs onto a single rationale — the triple can only carry one edge.",
        source_marker,
        edge.source,
        edge.relation.value,
        edge.target,
        kept.source_marker,
        source_marker,
        discarded_reason,
        surviving_reason,
    )


def _dangling_org_endpoints(
    contributions: Iterable[_OrgEdgeContribution],
    merged_nodes: Mapping[str, DRGNode],
) -> list[tuple[str, str]]:
    """Return ``(source_marker, urn)`` for org endpoints that bind to nothing.

    The post-assembly half of the endpoint policy. Only rule 2 of
    :func:`_resolve_edge_endpoint` (a fully-qualified URN accepted verbatim) can
    reach this state — rule 1 binds to a node the fragment itself contributes
    and rule 3 binds to a built-in URN, and both are in *merged_nodes* by
    construction. So this collects the deferral rather than adding a second,
    overlapping existence check.

    **Visible, not fatal.** The merge deliberately does not refuse here, because
    it cannot tell a typo from a legitimate reference into a sibling pack the
    operator has not configured — and callers legitimately merge a *subset* of
    the graph on purpose (``charter lint`` merges org fragments against an
    EMPTY built-in graph to isolate pack-level conflicts; refusing would break
    every qualified endpoint it sees). Completeness is the caller's question to
    ask, so this reports and lets the caller judge, exactly as
    :func:`_warn_builtin_override` does for a permitted-but-visible override.

    What the merge does owe — and now discharges — is that nothing lands in
    silence: every dangling endpoint gets a WARNING naming the pack and the
    token, whichever caller ran the merge. Any caller that merged the COMPLETE
    graph — the real shipped built-in against every configured pack — escalates
    the same finding to a structured error via
    :func:`charter.offering.drg.validator.validate_dangling_references`, whose docstring
    carries the predicate. Today that is ``doctor charter-packs`` (both its JSON
    collector and its human section) and ``charter status``; it is a rule about
    the merge, not a property of a particular command.

    Scoped to org contributions on purpose. Built-in and project edges are not
    minted by this bridge; adjudicating them here would report defects the
    org-pack author cannot act on, against layers this function has no
    provenance for.
    """
    dangling: list[tuple[str, str]] = []
    for contribution in contributions:
        edge = contribution.minted
        # A self-edge whose single endpoint dangles is one defect, not two.
        for urn in dict.fromkeys((edge.source, edge.target)):
            if urn in merged_nodes:
                continue
            dangling.append((contribution.source_marker, urn))
    return dangling


def _warn_dangling_org_endpoints(
    dangling: Iterable[tuple[str, str]],
) -> None:
    """Emit one WARNING per org endpoint that names nothing in the merged graph.

    Mirrors :func:`_warn_builtin_override` / :func:`_warn_project_override`:
    the merge permits the shape but refuses to let it pass unseen.
    """
    for source_marker, urn in dangling:
        _logger.warning(
            "Org doctrine %r declares an edge endpoint %r that names no node in "
            "any merged layer. The edge is kept (the endpoint may belong to a "
            "sibling pack this merge did not load) but it resolves to nothing "
            "here — check the token for a typo, or configure the pack that "
            "declares it. `spec-kitty doctor charter-packs` reports this as an error.",
            source_marker,
            urn,
        )


def bridge_org_edge_to_drg_edge(
    edge: Any,
    node_id_to_urn: Mapping[str, str],
    built_in_urns: Collection[str],
    source: str,
) -> tuple[DRGEdge | None, OrgDRGConflict | None]:
    """Mint a URN-shaped :class:`DRGEdge` from a fragment-side edge.

    Both endpoints go through :func:`_resolve_edge_endpoint`. An endpoint that
    cannot be bound yields a typed :class:`OrgDRGConflict` (FR-010) instead of
    the bare ``None`` this function used to return, so the drop is recorded and
    the merge hard-fails with an operator-actionable message.

    FR-003: an unknown relation label still raises
    :class:`UnknownRelationError` (via :func:`_resolve_relation`).

    Contract W-3: every ``DRGEdge`` field the fragment schema can express is set
    on the minted edge. Beyond the endpoints and relation, the fragment can
    express the author's ``reason`` -- an ``_OrgDRGEdge`` field this bridge used
    to drop before any writer ran. It is carried through here (machine
    provenance ``generated_reason`` is projection-only, is not a ``DRGEdge``
    field, and is intentionally not mapped). ``provenance`` is attached below by
    :func:`_tag_source`.

    Returns:
        ``(edge, None)`` on success, ``(None, conflict)`` on refusal.
    """
    relation = _resolve_relation(edge.relation, source)

    try:
        source_urn, target_urn = (
            _resolve_edge_endpoint(raw, node_id_to_urn, built_in_urns)
            for raw in (edge.source, edge.target)
        )
    except _EndpointResolutionError as exc:
        return None, _endpoint_conflict(exc.conflict_kind, exc.raw, edge, source)

    drg_edge = DRGEdge(
        source=source_urn,
        target=target_urn,
        relation=relation,
        reason=getattr(edge, "reason", None),
    )
    return _tag_source(drg_edge, source), None


def _resolve_builtin_collision(
    urn: str,
    org_node: Any,
    drg_node: DRGNode,
    merged_nodes: dict[str, DRGNode],
    conflicts: list[OrgDRGConflict],
    source_marker: str,
) -> None:
    """Resolve an org node whose URN collides with a built-in node.

    Kind-drift (the org node's kind DIFFERS from the built-in node's kind) is a
    ``hard_fail``: an override may replace a built-in's content, never its kind.
    A SAME-KIND collision is PERMITTED — the org node substitutes the built-in
    in place (``merged_nodes[urn] = drg_node``), a ``node_override`` conflict
    with ``resolution_applied = "org_override"`` is recorded, and a WARNING is
    emitted. In-place URN substitution preserves the built-in's inbound and
    outbound edges (no rehoming), mirroring the project-layer override path.
    """
    built_in_node = merged_nodes[urn]
    if drg_node.kind != built_in_node.kind:
        conflicts.append(
            OrgDRGConflict(
                kind="node_override",
                conflicting_layers=["built-in", source_marker],
                target_id=urn,
                built_in_value=built_in_node.model_dump(),
                org_value=org_node.model_dump(),
                project_value=None,
                resolution_applied="hard_fail",
            )
        )
        return
    merged_nodes[urn] = drg_node
    conflicts.append(
        OrgDRGConflict(
            kind="node_override",
            conflicting_layers=["built-in", source_marker],
            target_id=urn,
            built_in_value=built_in_node.model_dump(),
            org_value=org_node.model_dump(),
            project_value=None,
            resolution_applied="org_override",
        )
    )
    _warn_builtin_override(urn, source_marker)


def _filter_surviving_org_nodes(
    fragment: OrgDRGFragment,
    conflicts: list[OrgDRGConflict],
    source_marker: str,
) -> list[Any]:
    """Return fragment nodes that pass the layer-rule check.

    Nodes that violate the layer rule are recorded as ``hard_fail``
    ``layer_rule_violation`` conflicts and excluded from the merge.
    Extracted from :func:`_merge_org_fragment` to keep its cognitive
    complexity within the ruff C901 limit (15).
    """
    surviving_nodes: list[Any] = []
    for node in fragment.nodes:
        if _violates_layer_rule(node):
            conflicts.append(
                OrgDRGConflict(
                    kind="layer_rule_violation",
                    conflicting_layers=[source_marker],
                    target_id=node.id,
                    built_in_value=None,
                    org_value=node.model_dump(),
                    project_value=None,
                    resolution_applied="hard_fail",
                )
            )
            continue
        surviving_nodes.append(node)
    return surviving_nodes


def _merge_org_fragment(
    fragment: OrgDRGFragment,
    merged_nodes: dict[str, DRGNode],
    merged_edges: list[DRGEdge],
    invariant_urns: frozenset[str],
    conflicts: list[OrgDRGConflict],
    collector: _OrgEdgeCollector,
) -> None:
    """Merge one org-DRG fragment into *merged_nodes* / *merged_edges*.

    Extracted from :func:`merge_three_layers` to keep its cyclomatic
    complexity within the ruff C901 limit (15).

    A built-in URN collision is delegated to :func:`_resolve_builtin_collision`:
    a SAME-KIND org node permissibly overrides the built-in in place (a
    ``node_override`` conflict with ``resolution_applied = "org_override"`` plus
    a WARNING); a kind-drift collision still hard-fails. Whether the repo
    tolerates a permitted override is a per-repo governance test, not a merge
    prohibition.
    """
    source_marker = f"org:{fragment.pack_name}"
    surviving_nodes = _filter_surviving_org_nodes(fragment, conflicts, source_marker)

    node_id_to_urn: dict[str, str] = {}
    for node in surviving_nodes:
        minted = _bridge_org_node_to_drg_node(node, source_marker)
        if isinstance(minted, OrgDRGConflict):
            conflicts.append(minted)
            continue
        urn, drg_node = minted
        node_id_to_urn[node.id] = urn
        if urn in invariant_urns:
            _resolve_builtin_collision(
                urn, node, drg_node, merged_nodes, conflicts, source_marker
            )
            continue
        if urn not in merged_nodes:
            merged_nodes[urn] = drg_node

    # Endpoints resolve against this fragment's own nodes plus the BUILT-IN
    # layer — never the running merge state. ``invariant_urns`` is exactly the
    # built-in URN set, so the result does not depend on where this pack sits
    # in the operator's declaration order.
    for edge in fragment.edges:
        drg_edge, conflict = bridge_org_edge_to_drg_edge(
            edge, node_id_to_urn, invariant_urns, source_marker
        )
        if conflict is not None:
            conflicts.append(conflict)
            continue
        # ``collector.add`` is the single authority on org edge identity: a
        # relationship restated in another spelling (or by another pack)
        # contributes once.
        if drg_edge is not None and collector.add(drg_edge, edge, source_marker):
            merged_edges.append(drg_edge)


def _warn_builtin_override(urn: str, source_marker: str) -> None:
    """Emit a WARNING when a same-kind org node overrides a built-in node.

    Mirrors :func:`_warn_project_override`. The override is permitted by the
    merge (kind matches), but is surfaced for operator visibility: a per-repo
    governance test decides whether the override is allowed for this repo.
    """
    _logger.warning(
        "Org doctrine %r overrides built-in node %r (same-kind override). "
        "This is permitted by the merge but visible by design; a per-repo "
        "governance test (replaceable-builtins allowlist) decides whether the "
        "override is sanctioned.",
        source_marker,
        urn,
    )


def _warn_project_override(urn: str, existing_provenance: str) -> None:
    """Emit a WARNING when the project layer overrides a built-in/org node.

    Called from :func:`merge_three_layers` only. Extracted to keep the merge
    function's cyclomatic complexity within the ruff C901 threshold.
    """
    _logger.warning(
        "Project doctrine overrides %s node %r (was provenance=%r). "
        "This is allowed by design (project > org > built-in precedence); "
        "flag here for operator visibility.",
        existing_provenance,
        urn,
        existing_provenance,
    )


# ---------------------------------------------------------------------------
# Global URN-uniqueness scan (FR-008, FR-004, D-04 revised)
# ---------------------------------------------------------------------------


def _check_node_urn_unique(prefix: str, nodes: Iterable[DRGNode]) -> None:
    """Hard-fail if any URN starting with *prefix* occurs more than once in
    *nodes* (FR-008/FR-004, D-04 revised).

    Order-independent: duplicates are detected by counting occurrences per
    URN rather than depending on iteration/insertion order, so the same
    collision is caught regardless of which layer or pack declared it first.

    Extracted as a standalone helper — NOT nested inside
    :func:`_merge_org_fragment`, which is already at the ruff C901
    complexity ceiling — and scoped strictly by *prefix*. Callers must never
    widen this check to another kind's prefix: the other 9 kinds' layered
    override tolerance (org-vs-org first-wins, built-in-vs-org override,
    project-vs-any override) depends on same-URN collisions being resolved,
    not rejected, and ``drg/models.py`` enforces URN-prefix == kind so this
    scan can never observe a cross-kind collision.
    """
    counts = Counter(node.urn for node in nodes if node.urn.startswith(prefix))
    duplicate_urn = next((urn for urn, n in counts.items() if n > 1), None)
    if duplicate_urn is None:
        return
    raise DuplicateURNError(
        code=_DUPLICATE_URN_ERROR_CODES[prefix],
        urn=duplicate_urn,
        count=counts[duplicate_urn],
    )


def _asset_template_candidates(
    built_in: DRGGraph,
    org_fragments: list[OrgDRGFragment],
    project: DRGGraph | None,
) -> list[DRGNode]:
    """Collect every ``asset:``/``template:`` node contributed by any of the
    three layers, WITHOUT the layered-override collapsing that
    :func:`merge_three_layers` applies when building ``merged_nodes``.

    This is deliberately a *raw* union, not a lookup against the deduplicated
    merge output: TEMPLATE and ASSET have no legitimate override semantics
    (D-04 revised), so a built-in-vs-org or org-vs-org same-URN collision that
    the override machinery would otherwise silently resolve in place must
    still be visible to :func:`_check_node_urn_unique` as a duplicate.

    A fragment node that fails the layer-rule check, declares an unmappable
    kind, or cannot form a valid URN is never reached here:
    :func:`merge_three_layers` raises :class:`OrgDRGConflictError` for any
    hard-fail conflict before this function's result is consulted. The
    :class:`OrgDRGConflict` return from :func:`_bridge_org_node_to_drg_node` is
    therefore unreachable in practice, but is skipped rather than unpacked so
    this helper stays total under any future caller ordering.
    """
    candidates: list[DRGNode] = [
        node for node in built_in.nodes if node.kind in _URN_UNIQUENESS_NODE_KINDS
    ]
    for fragment in org_fragments:
        source_marker = f"org:{fragment.pack_name}"
        for node in fragment.nodes:
            if node.kind not in _URN_UNIQUENESS_ORG_KINDS:
                continue
            minted = _bridge_org_node_to_drg_node(node, source_marker)
            if isinstance(minted, OrgDRGConflict):
                continue
            candidates.append(minted[1])
    if project is not None:
        candidates.extend(
            node for node in project.nodes if node.kind in _URN_UNIQUENESS_NODE_KINDS
        )
    return candidates


# ---------------------------------------------------------------------------
# Canonical merge (FR-001, FR-003, FR-005)
# ---------------------------------------------------------------------------


def merge_three_layers(
    built_in: DRGGraph,
    org_fragments: list[OrgDRGFragment],
    project: DRGGraph | None,
) -> DRGGraph:
    """Overlay built-in → org → project layers (FR-001, FR-003, FR-005).

    Precedence: project > org > built-in. Operator-authored project doctrine
    may override both built-in and org tiers. When the project layer overrides
    a built-in or org node, a ``logging.warning`` is emitted with the URN +
    original layer so the override is visible in operator output but does not
    block the merge. Use :class:`OrgDRGConflict` records to query overrides
    programmatically.

    Org-tier nodes that collide with a built-in node are resolved by kind:

    * **Same-kind** collision — PERMITTED. The org node substitutes the built-in
      in place (preserving the built-in's inbound/outbound edges, mirroring the
      project-layer override), a ``node_override`` conflict with
      ``resolution_applied='org_override'`` is recorded, and a WARNING is
      emitted. The merge does NOT raise. Whether a given repo *tolerates* this
      override is a per-repo governance TEST
      (``tests/architectural/test_builtin_override_policy.py`` consulting
      ``.kittify/charter-packs/replaceable-builtins.yaml``), not a merge prohibition.
    * **Kind-drift** collision (org kind DIFFERS from built-in kind) — hard-fails
      with :class:`OrgDRGConflictError` (``resolution_applied='hard_fail'``). An
      override may replace a built-in's content, never its kind.

    Layer-rule violations (org nodes reaching into ``src/specify_cli/``) always
    hard-fail. An org/project fragment edge with an unrecognised relation label
    raises :class:`UnknownRelationError` (FR-003 — no silent drop).

    FR-010 (WP08): an org edge whose **endpoint** cannot be bound also
    hard-fails, with an ``unresolved_edge_endpoint`` /
    ``ambiguous_edge_endpoint`` / ``malformed_urn`` conflict record naming the
    offending token. Both endpoints obey one resolution policy (see
    :func:`_resolve_edge_endpoint`): fragment-local bare id, then
    fully-qualified URN, then a bare id matched against an already-merged
    layer by its *declared* kind. The bridge no longer drops an unresolvable
    source in silence and no longer invents a ``directive:`` kind for an
    unresolvable target.

    A fully-qualified endpoint is accepted verbatim at mint time (a later layer
    may still supply the node) and re-checked here against the fully-assembled
    node set — see :func:`_dangling_org_endpoints`. An org endpoint that names
    nothing in any merged layer is **not** a hard fail (the merge cannot tell a
    typo from a reference into a sibling pack the caller did not load, and
    ``charter lint`` merges against an empty built-in on purpose) but it always
    emits a WARNING naming the pack and the token, so no caller — present or
    future — can consume such an edge unwarned.
    :func:`charter.offering.drg.validator.validate_dangling_references` is how a caller
    that owns graph completeness escalates the same finding to an error.

    Every node and edge in the returned graph carries a declared ``provenance``
    field readable via ``node.provenance``:

    * ``"built-in"`` — built-in layer (Mission A);
    * ``"org:<pack_name>"`` — contributed by an :class:`OrgDRGFragment`;
    * ``"project"`` — contributed by the project layer.

    Parameters
    ----------
    built_in:
        The built-in DRG. Treated as the source of truth for invariants.
    org_fragments:
        Loaded org-tier fragments in declaration order. For a same-kind
        collision at a built-in URN the org node substitutes in place, and the
        last org pack that declares it wins (``_resolve_builtin_collision``).
        A kind-drift collision with a built-in node is a hard failure.
    project:
        Optional project-tier DRG (``.kittify/charter-packs/graph.yaml`` loaded and
        merged elsewhere). When ``None``, the merge collapses to the
        built-in+org case.

    Returns
    -------
    DRGGraph:
        The merged graph. Nodes and edges carry the declared ``provenance`` field.

    Raises
    ------
    OrgDRGConflictError:
        On a layer-rule violation OR a kind-drift built-in collision (org kind
        differs from the built-in kind). A SAME-KIND built-in override does NOT
        raise (it is recorded as an ``org_override`` conflict). The error
        carries the full conflict list; the caller can inspect ``exc.conflicts``.
    UnknownRelationError:
        On an org/project fragment edge with an unrecognised relation label
        (FR-003).
    DuplicateURNError:
        On a duplicate ``asset:`` or ``template:`` URN anywhere across the
        built-in, org, and project layers (FR-008/FR-004, D-04 revised). This
        is a global, order-independent, prefix-scoped check that runs once
        after all three layers are assembled — it does not affect any other
        kind's layered-override tolerance.
    """
    conflicts: list[OrgDRGConflict] = []
    collector = _OrgEdgeCollector()

    # Seed the merged maps with the built-in layer.
    merged_nodes: dict[str, DRGNode] = {
        n.urn: _tag_source(n, "built-in") for n in built_in.nodes
    }
    merged_edges: list[DRGEdge] = [
        _tag_source(e, "built-in") for e in built_in.edges
    ]

    invariant_urns = _built_in_invariant_ids(built_in)

    for fragment in org_fragments:
        _merge_org_fragment(
            fragment,
            merged_nodes,
            merged_edges,
            invariant_urns,
            conflicts,
            collector,
        )

    if any(c.resolution_applied == "hard_fail" for c in conflicts):
        raise OrgDRGConflictError(conflicts)

    if project is not None:
        for node in project.nodes:
            if node.urn in merged_nodes:
                existing_provenance = merged_nodes[node.urn].provenance or "unknown"
                _warn_project_override(node.urn, existing_provenance)
            merged_nodes[node.urn] = _tag_source(node, "project")
        for edge in project.edges:
            merged_edges.append(_tag_source(edge, "project"))

    # Post-assembly endpoint existence. A fully-qualified org endpoint is
    # accepted verbatim at mint time because the project layer had not merged
    # yet; now it has, so the deferral is collected here rather than left to a
    # validator that no caller of this function was actually running.
    _warn_dangling_org_endpoints(
        _dangling_org_endpoints(collector.contributions, merged_nodes)
    )

    # Global URN-uniqueness scan (FR-008/FR-004, D-04 revised): a single
    # post-merge, order-independent, prefix-scoped check covering all three
    # collision surfaces (built-in-vs-org, org-vs-org, project-vs-any) for the
    # two node-declarable-but-not-augmentation-eligible kinds. Runs on the raw
    # per-layer union (not ``merged_nodes``), since TEMPLATE/ASSET have no
    # legitimate override semantics and the override machinery above would
    # otherwise hide a same-URN collision by collapsing it in place.
    asset_template_candidates = _asset_template_candidates(
        built_in, org_fragments, project
    )
    _check_node_urn_unique("asset:", asset_template_candidates)
    _check_node_urn_unique("template:", asset_template_candidates)

    return DRGGraph(
        schema_version=built_in.schema_version,
        generated_at=built_in.generated_at,
        generated_by=built_in.generated_by,
        nodes=list(merged_nodes.values()),
        edges=merged_edges,
    )
