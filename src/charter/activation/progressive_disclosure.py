"""Progressive disclosure of doctrine context (WP15, ADR 2026-07-28-1).

Complete delivery made *affordable*: everything reachable is either delivered
inline (``requires`` — eager) or **named with the guidance that says when to
fetch it** (``suggests`` — a link carrying ``when``). Never silently absent.

This is the **default cadence**, not an opt-in mode. A link is not a truncation
(NFR-003): the artefact stays named and addressable, which is the property the
carrying mission exists to protect. Completeness is satisfied by the **union of
inlined and linked ids** equalling the delivered set — there is no cap on that
union.

The functions here are pure over a resolved :class:`~charter.offering.drg.models.DRGGraph`
so the delivery cadence is testable without loading the whole doctrine tree, and
so ``charter.activation.context`` does not grow to carry them (context.py is single-owned by
WP10 and held near-flat).
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Any

from charter.offering.drg.models import Relation

if TYPE_CHECKING:
    from charter.repository_protocol import ArtifactRepository
    from charter.offering.drg.models import DRGEdge, DRGGraph

#: The stated default rendered for an *uncovered* ``suggests`` edge — one of the
#: 118 (of 337) that carry no authored ``when`` (ADR 2026-07-28-1). A link with
#: this text is still a link: the artefact is named and fetchable. The default
#: makes the authoring gap **visible**, never blank (T081) — an empty string
#: would read as "no guidance intended" rather than "guidance not yet written".
STATED_DEFAULT_WHEN: str = (
    "Fetch when this artefact's guidance applies to the work at hand "
    "(no specific trigger authored yet)."
)

#: Delivery cadence markers attached to each delivered artefact DTO (T082).
DELIVERY_INLINE: str = "inline"
DELIVERY_LINK: str = "link"


def bare_id(urn: str) -> str:
    """Return the artefact id from a DRG URN (``directive:DIRECTIVE_010`` -> ``DIRECTIVE_010``).

    The delivered arrays key on the bare id, so references key on it too — that
    is what makes the union-of-ids completeness check (T084) well defined.
    """
    return urn.split(":", 1)[1] if ":" in urn else urn


def edge_to_reference(edge: DRGEdge) -> dict[str, str | None]:
    """Project one DRG edge into a ``{id, relation, when, reason}`` reference (T081).

    ``relation``/``reason`` are the edge's own fields, unmodified. ``when`` is the
    edge's own field for a covered ``suggests`` edge; an *uncovered* ``suggests``
    edge renders :data:`STATED_DEFAULT_WHEN` rather than an empty string so the
    authoring gap stays visible.
    """
    when = edge.when
    if not when and edge.relation is Relation.SUGGESTS:
        when = STATED_DEFAULT_WHEN
    return {
        "id": bare_id(edge.target),
        "relation": edge.relation.value,
        "when": when,
        "reason": edge.reason,
    }


def outbound_references(merged: DRGGraph, urn: str) -> list[dict[str, str | None]]:
    """Every outbound edge of *urn* as a reference entry (the DTO's ``references[]``)."""
    return [edge_to_reference(edge) for edge in merged.edges_from(urn)]


def requires_closure(merged: DRGGraph, roots: Iterable[str]) -> set[str]:
    """Transitive closure of *roots* over ``requires`` edges only (the eager set).

    ``requires`` is unconditional — a required artefact is delivered inline with
    no ``when`` to evaluate (ADR: cadence follows the relation, C-011).
    """
    seen: set[str] = set(roots)
    stack: list[str] = list(seen)
    while stack:
        node = stack.pop()
        for edge in merged.edges_from(node, Relation.REQUIRES):
            if edge.target not in seen:
                seen.add(edge.target)
                stack.append(edge.target)
    return seen


def partition_delivery(
    merged: DRGGraph,
    roots: Iterable[str],
    delivered_urns: Iterable[str],
) -> tuple[set[str], set[str]]:
    """Split the delivered set into ``(inline_urns, link_urns)`` by cadence (T082).

    ``inline`` = the ``requires`` closure of *roots* intersected with the
    delivered set (eager). ``link`` = everything else delivered (the
    ``suggests``-reached artefacts, emitted as links). The union is the whole
    delivered set — nothing is dropped.
    """
    delivered = set(delivered_urns)
    inline = requires_closure(merged, roots) & delivered
    return inline, delivered - inline


def link_references(
    merged: DRGGraph,
    roots: Iterable[str],
    delivered_urns: Iterable[str],
    *,
    bridge_urns: Iterable[str] = (),
) -> list[dict[str, str | None]]:
    """The complete link set naming every delivered artefact (completeness, T084).

    Emits one reference per ``(target-id, relation)`` for every edge whose source
    is a root, a delivered artefact, **or** a *bridge* URN, and whose target is
    delivered. Computed over ``roots ∪ delivered ∪ bridge_urns`` — not only the
    inline DTOs — so a ``suggests`` chain (``root ~> a ~> b ~> c`` where ``b`` is
    itself only linked) still names its deep members: every delivered artefact
    has an inbound edge from within ``roots ∪ delivered`` by construction of the
    reachable closure, **provided every intermediate hop is itself delivered**.

    That proviso does not hold when a hop is of a kind the bundle deliberately
    never delivers (e.g. ``paradigm`` — see ``charter.activation.context``'s NodeKind
    delivery table): such a node is genuinely reachable during resolution and
    can sit on the only path to a delivered artefact, yet it is excluded from
    the ``delivered`` set by policy, so it would never act as a source and the
    artefact on the far side would be neither inlined nor named — a silent
    delivery gap despite ``delivered`` correctly containing it. ``bridge_urns``
    closes that gap: pass every URN actually visited during resolution
    (including excluded kinds) so pass-through hops still act as reference
    sources, without pulling them into ``delivered`` or ``inline`` themselves.

    This is the "completeness by naming" guarantee: the union of inlined and
    referenced ids equals the delivered set, with no cap.
    """
    delivered = set(delivered_urns)
    sources = set(roots) | delivered | set(bridge_urns)
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, str | None]] = []
    for source in sorted(sources):
        for edge in merged.edges_from(source):
            if edge.target not in delivered:
                continue
            key = (bare_id(edge.target), edge.relation.value)
            if key in seen:
                continue
            seen.add(key)
            out.append(edge_to_reference(edge))
    return out


def profile_channel_references(
    merged: DRGGraph,
    seeds: Iterable[str],
    reached: Iterable[str],
    delivered_urns: Iterable[str],
) -> list[dict[str, str | None]]:
    """Suggests-delivered references for the profile channel (WP01, IC-01/C2).

    The profile channel (``charter.offering.drg.reachability.profile_channel_reachable``)
    now follows ``suggests`` edges. For every artefact it reaches *only* through a
    ``suggests`` edge, the consumer must surface that edge's ``when`` clause as
    the delivered doctrine's applicability condition (``STATED_DEFAULT_WHEN`` when
    the edge is ``when``-less). This function is that projection.

    **Why reuse** :func:`link_references` **and not walk per reached node (D11):**
    ``when`` lives on the *inbound* edge ``source -> target`` that reaches an
    artefact, and ``profile_channel_reachable`` returns ``visited - seed_set`` —
    it **strips the profile seeds**, which are exactly the sources of the
    first-hop Family A/B edges (``architect -> DDD``,
    ``python-pedro -> DISCIPLINED_REFACTORING``). A per-reached-node
    ``edges_from(reached, SUGGESTS)`` would therefore miss those edges and surface
    no ``when`` for the headline families. :func:`link_references` iterates
    ``roots ∪ delivered ∪ bridge_urns`` as edge sources, so passing the seeds as
    ``roots`` restores the stripped first-hop edges. Note ``reached ∪ seeds ==
    visited`` (``walk_edges`` adds the start nodes to ``visited``), so the
    ``bridge_urns`` here is reconstructed from values the caller already holds —
    **no second walk**.

    **Requires precedence (C3/A4):** an artefact inside the *seeds'*
    ``requires``-closure is delivered eager (inline elsewhere) and is *excluded*
    from this link set — :func:`partition_delivery` computes the split and only
    the ``link`` side is projected. A diamond artefact reachable via both
    ``requires`` (from a seed) and ``suggests`` therefore delivers once, eager,
    and never appears here as a link.

    Args:
        merged: The merged DRG graph.
        seeds: The profile-channel seeds (the ``roots``, sources of first-hop
            ``suggests`` edges the walk stripped).
        reached: The full reachable set (``profile_channel_reachable``'s return);
            ``reached ∪ seeds`` reconstructs the walk's ``visited`` for pass-through
            hops of never-delivered kinds (e.g. a linking ``paradigm``).
        delivered_urns: The kind-filtered subset of *reached* the consumer renders
            (the render-layer NodeKind delivery table, C4). Only edges whose
            target is in this set project a reference.

    Returns:
        One ``{id, relation, when, reason}`` reference per ``(target-id, relation)``
        of the ``suggests``-delivered (link) subset, deterministically ordered.
    """
    seed_set = set(seeds)
    delivered = set(delivered_urns)
    _inline, link = partition_delivery(merged, seed_set, delivered)
    bridge = set(reached) | seed_set  # == walk_edges ``visited`` (D11)
    return link_references(merged, seed_set, link, bridge_urns=bridge)


def artifact_to_dict(artifact: object, source: str) -> dict[str, object]:
    """Render one doctrine artefact as a JSON DTO (id + provenance + best-effort fields).

    Relocated verbatim from ``charter.activation.context`` (single-owner, no-net-growth) so
    the DTO shape and its progressive-disclosure decoration live together.
    """
    item_id = getattr(artifact, "id", None)
    title = getattr(artifact, "title", None) or getattr(artifact, "name", None)
    summary = getattr(artifact, "intent", None) or getattr(artifact, "purpose", None)
    out: dict[str, object] = {
        "id": item_id if isinstance(item_id, str) else "",
        "source": source if source in {"builtin", "org", "project"} else "builtin",
    }
    if isinstance(title, str) and title:
        out["title"] = title
    if isinstance(summary, str) and summary:
        out["summary"] = summary
    return out


def reconstruct_urns(ids_by_kind: dict[str, Iterable[str]]) -> tuple[str, ...]:
    """Rebuild DRG URNs from a ``{kind: [id, ...]}`` mapping (delivered-set input)."""
    return tuple(
        f"{kind}:{artifact_id}"
        for kind, ids in ids_by_kind.items()
        for artifact_id in ids
    )


def _decorate_entry(
    entry: dict[str, object],
    *,
    kind: str,
    artifact: object,
    merged: DRGGraph | None,
    inline_urns: frozenset[str],
    include_all: bool,
    body_of: Callable[[object], object] | None,
) -> None:
    """Attach ``references``, ``delivery`` and (for inline) ``body`` to a DTO in place.

    A ``None`` graph means the DRG could not be resolved on this path; the entry
    is left undecorated (plain provenance DTO) rather than carrying an empty,
    misleading cadence — the non-action ``all_directives`` list flows through
    here with no graph and must stay a plain list.
    """
    if merged is None:
        return
    urn = f"{kind}:{entry.get('id', '')}"
    entry["references"] = outbound_references(merged, urn)
    is_inline = include_all or urn in inline_urns
    entry["delivery"] = DELIVERY_INLINE if is_inline else DELIVERY_LINK
    if is_inline and artifact is not None and body_of is not None:
        body = body_of(artifact)
        if body:
            entry["body"] = body


def collect_typed_artifacts(
    repository: ArtifactRepository[Any],
    artifact_ids: list[str],
    *,
    kind: str,
    merged: DRGGraph | None = None,
    inline_urns: frozenset[str] = frozenset(),
    include_all: bool = False,
    body_of: Callable[[object], object] | None = None,
) -> list[dict[str, object]]:
    """Look up *artifact_ids* in *repository*, emit DTOs decorated for progressive disclosure.

    Each entry carries provenance (relocated from ``charter.activation.context``) plus the
    WP15 additions: ``references[]`` (T081), a ``delivery`` marker (T082), and,
    for inline artefacts, a ``body`` when *body_of* is supplied. Under
    *include_all* every artefact is delivered inline — a strict superset of the
    progressive render for the same grain (T083).
    """
    entries: list[dict[str, object]] = []
    for artifact_id in artifact_ids:
        try:
            artifact = repository.get(artifact_id)
            source = repository.get_provenance(artifact_id) or "builtin"
        except (AttributeError, KeyError):
            artifact, source = None, "builtin"
        entry: dict[str, object] = (
            {"id": artifact_id, "source": source}
            if artifact is None
            else artifact_to_dict(artifact, source)
        )
        _decorate_entry(
            entry,
            kind=kind,
            artifact=artifact,
            merged=merged,
            inline_urns=inline_urns,
            include_all=include_all,
            body_of=body_of,
        )
        entries.append(entry)
    return entries


#: Action-scoped JSON payload array name for each delivered kind. ``procedure``
#: is a first-class typed array (#3389); ``asset`` is deliberately absent — it
#: stays reference-only (no resolution/install path — #3037), folded into the
#: flat ``references[]`` via ``build_disclosure_payload``'s ``extra_delivered``.
_ARRAY_BY_KIND: dict[str, str] = {
    "directive": "directives",
    "tactic": "tactics",
    "styleguide": "styleguides",
    "toolguide": "toolguides",
    "procedure": "procedures",
}


def build_disclosure_payload(
    *,
    repos_by_kind: dict[str, tuple[ArtifactRepository[Any], list[str]]],
    extra_delivered: dict[str, list[str]],
    merged: DRGGraph | None,
    roots: Iterable[str],
    include_all: bool,
    body_of: Callable[[object], object] | None,
    bridge_urns: Iterable[str] = (),
) -> dict[str, object]:
    """Render the progressive-disclosure slice of the JSON payload (WP15).

    Returns the typed artefact arrays named in :data:`_ARRAY_BY_KIND` — one per
    kind in *repos_by_kind*, each entry decorated with ``references[]`` and a
    ``delivery`` cadence marker — plus the top-level ``references`` link set that
    names every delivered artefact (including any *extra_delivered* kind, which
    is delivered but not surfaced as its own array). ``procedure`` is a typed
    array (#3389); ``asset`` stays reference-only (#3037), so callers pass it via
    *extra_delivered*. Kept here so ``charter.activation.context`` stays flat (single-owner,
    no-net-growth) while owning only the call.

    *bridge_urns* is every URN actually visited while resolving the action's
    doctrine (e.g. ``resolve_context``'s raw ``artifact_urns``, before the
    NodeKind delivery table drops the never-delivered kinds). It is forwarded
    to :func:`link_references` only — never folded into ``roots`` here, so it
    cannot widen the ``requires``-eager/inline set — to keep excluded-kind
    pass-through hops (e.g. ``paradigm``) usable as reference sources.
    """
    inline_urns = (
        frozenset(requires_closure(merged, roots)) if merged is not None else frozenset()
    )
    out: dict[str, object] = {}
    delivered: dict[str, Iterable[str]] = {}
    for kind, (repository, ids) in repos_by_kind.items():
        out[_ARRAY_BY_KIND[kind]] = collect_typed_artifacts(
            repository,
            list(ids),
            kind=kind,
            merged=merged,
            inline_urns=inline_urns,
            include_all=include_all,
            body_of=body_of,
        )
        delivered[kind] = ids
    delivered.update(extra_delivered)
    out["references"] = (
        link_references(
            merged, roots, reconstruct_urns(delivered), bridge_urns=bridge_urns
        )
        if merged is not None
        else []
    )
    return out


#: Public API surface (landing-fold E1, PR #3070): only the names an external
#: caller actually reaches. ``build_disclosure_payload``, ``collect_typed_artifacts``
#: and ``requires_closure`` are called directly from ``charter.activation.context`` (the
#: live wiring); ``partition_delivery`` is genuinely forward API with no ``src/``
#: caller yet (see ``category_c_delivery_rail_forward_api`` in
#: ``tests/architectural/dead_symbol_allowlist.yaml``). Everything else this module
#: defines (``bare_id``, ``edge_to_reference``, ``outbound_references``,
#: ``link_references``, ``reconstruct_urns``, ``artifact_to_dict``,
#: ``DELIVERY_INLINE``/``DELIVERY_LINK``/``STATED_DEFAULT_WHEN``) is an
#: implementation detail reached only intra-module (by the functions above) or
#: from this module's own unit tests via direct module-attribute access — those
#: reads do not depend on ``__all__`` membership, so demoting these names here
#: does not break anything.
__all__ = [
    "build_disclosure_payload",
    "collect_typed_artifacts",
    "partition_delivery",
    "profile_channel_references",
    "requires_closure",
]
