"""Action-doctrine bundle resolution (WP06 T029, #2532).

Relocated verbatim from ``charter.activation.context`` (single-owner, no-net-growth for
that file). Resolves DRG-backed action doctrine artifacts for a given
``(action, mission_type/feature_dir)`` pair into an :class:`_ActionDoctrineBundle`
— the payload both the bootstrap-text renderer and the ``--json`` entrypoint
consume.

Cycle note: ``_build_offering_service`` and ``_normalize_directive_id`` are
imported function-locally / from their sibling homes respectively; the
former stays routed through ``charter.activation.context`` (the single test-patchable
seam every other builder-consuming module already uses — see
``context_renderers/compact_governance.py``'s cycle note for the
established precedent) rather than importing
``charter.activation.active_charter_service_builder`` directly, so patching
``charter.activation.context._build_offering_service`` continues to redirect every
caller, moved or not.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from charter.activation.pack_context import PackContext
    from charter.offering.drg.models import DRGGraph
    import charter.offering.service as _offering_service_module

from charter.activation.catalog import load_offering_catalog
from charter.activation.language_scope import infer_repo_languages
from charter.activation.org_pack_discovery import _read_org_required_selections
from charter.activation.profile_resolution import _normalize_directive_id
from charter.offering.drg.models import NodeKind

__all__ = [
    "_ActionDoctrineBundle",
    "_load_action_doctrine_bundle",
    "_resolve_action_bundle",
]


_LOGGER = logging.getLogger(__name__)


def _catalog_default_or_activated(
    activated: frozenset[str] | None,
    catalog_default: frozenset[str],
) -> set[str]:
    """Three-state collapse for one ``pack_context.activated_<kind>`` field
    (WP02, Decision Record 2, FR-006/007/008/014).

    ``None`` (key genuinely absent -- covers BOTH a wholly-absent
    ``pack_context`` and a supplied ``PackContext`` whose field is ``None``;
    callers collapse those two to the same argument before calling this)
    resolves to the ``catalog_default`` argument -- NEVER an empty set, per
    the union/exclusion boundary invariant this WP exists to enforce.
    ``frozenset()`` (explicit, present, empty) and any non-empty frozenset
    pass through verbatim, preserved distinctly from the catalog-default
    case: this is the one state that stays empty (explicit "exclude
    everything"), and it is only ever reachable when a real ``PackContext``
    is supplied with that field explicitly set. Directive-specific
    stem-to-canonical normalization (``_normalize_directive_id``) is each
    caller's own job, applied on top of this helper's result -- not every
    kind needs it (tactics/paradigms have no stem-vs-canonical distinction;
    see the WP's Union/Exclusion Boundary Audit).

    ``catalog_default`` (WP02 ruling 2, ``reviews/wp02.ruling-2.md``): the
    caller passes ``_graph_and_catalog_default_ids`` below -- the ACTIVE DRG
    graph being resolved against, unioned with the real built-in catalog --
    never a bare ``load_offering_catalog()`` call. Binding "all built-ins"
    to a hardcoded real catalog is what made a mocked/injected graph and the
    real allowlist disagree (#883, the org-pack-chain regression): a
    fictional or org-authored id genuinely present in the graph being
    resolved was excluded for not being in a catalog the graph was never
    asked to match. Unioning rather than replacing keeps a graph that omits
    a kind entirely (a directive-only test fixture with zero tactic/paradigm
    nodes) still widening to the full real catalog for that kind -- WP02's
    own ``test_activated_tactics_and_paradigms_absent_widen_to_full_catalog``
    depends on exactly this.
    """
    if activated is None:
        return set(catalog_default)
    return set(activated)


def _graph_and_catalog_default_ids(
    graph: DRGGraph, kind: NodeKind, catalog_default: frozenset[str]
) -> frozenset[str]:
    """The "all built-ins" default for one artifact *kind* (WP02 ruling 2).

    Union of *catalog_default* (``load_offering_catalog()``'s real built-in
    set for *kind*) with every *kind*-node bare id the ACTIVE *graph* itself
    carries. In production the merged graph already contains the real
    catalog as its built-in layer, so this union is a no-op there --
    behaviour is unchanged. Under an injected or mocked graph (test
    fixtures) or one augmented with org-pack content, the union additionally
    admits ids the graph declares but the real catalog does not ship,
    closing the #883 / org-pack-chain allowlist collision without ever
    narrowing below the real catalog (see ``_catalog_default_or_activated``'s
    docstring for why narrowing would break WP02's own T007 step 5 fixture).
    """
    graph_ids = {
        node.urn.split(":", 1)[1]
        for node in graph.nodes
        if node.kind is kind and ":" in node.urn
    }
    return frozenset(graph_ids | catalog_default)


@dataclass(frozen=True)
class _ActionDoctrineBundle:
    """Resolved action doctrine artifacts for bootstrap rendering.

    ``procedure_ids``/``asset_ids`` are WP10 additions (FR-009/FR-011); ``mission``
    and ``service`` are kept though the contract sketch omits them.
    """

    mission: str
    directive_ids: list[str]
    tactic_ids: list[str]
    styleguide_ids: list[str]
    toolguide_ids: list[str]
    procedure_ids: list[str]
    asset_ids: list[str]
    service: _offering_service_module.CharterOfferingService
    # WP01 (deliver-loaded-doctrine, FR-001/FR-002): glossary-pack ids delivered
    # to the ``glossary_packs`` slot, mirroring ``procedure_ids``/``asset_ids``.
    # Defaulted (not a trailing required field) so the pre-existing bundle
    # constructors that predate the glossary slot stay valid byte-for-byte.
    glossary_pack_ids: list[str] = field(default_factory=list)
    # WP15 (progressive disclosure, out-of-map): the resolved DRG and the
    # traversal roots, carried so the JSON entrypoint can render each artefact's
    # ``references[]`` and split the requires-eager / suggests-linked cadence
    # without re-loading and re-filtering the graph.
    merged: DRGGraph | None = None
    roots: tuple[str, ...] = ()
    # WP15/D2a: every URN actually visited while resolving the action node
    # (``resolve_context``'s raw ``artifact_urns``, before the NodeKind
    # delivery table drops never-delivered kinds like ``paradigm``). Carried
    # separately from ``roots`` so progressive disclosure can use excluded-kind
    # pass-through hops as reference sources without widening the
    # requires-eager/inline set (see ``progressive_disclosure.link_references``
    # ``bridge_urns``).
    bridge_urns: tuple[str, ...] = ()
    # WP02 (governance-at-the-gate, FR-009): co-delivered ``in_tension_with``
    # pairs mapped to the reconciler(s) that bridge BOTH sides, carried
    # verbatim from ``ResolvedContext.tension_arbiters`` -- see that
    # attribute's docstring for the field shape and why it is a tuple of
    # tuples rather than a dict (frozen-dataclass hashability). Defaulted
    # trailing field so every pre-existing bundle constructor stays valid.
    tension_arbiters: tuple[tuple[str, tuple[str, ...]], ...] = ()
    # WP02: co-delivered ``in_tension_with`` pairs with no reachable
    # reconciler, carried verbatim from
    # ``ResolvedContext.unarbitrated_tensions``.
    unarbitrated_tensions: tuple[tuple[str, str], ...] = ()


#: Bundle slots whose artifacts can carry ``applies_to_languages`` (directives cannot).
_LANGUAGE_SCOPED_SLOTS = ("tactics", "styleguides", "toolguides", "procedures")


def _drop_scope_filtered_ids(
    ids_by_slot: Mapping[str, tuple[str, ...]],
    service: _offering_service_module.CharterOfferingService,
    repo_root: Path,
) -> Mapping[str, tuple[str, ...]]:
    """For any project with a language signal, drop ids the service scope-filtered out (FR-009, #5357).

    The DRG action walk is language-blind, so it still names language-scoped
    artifacts (e.g. ``python-conventions``) that the language-gated repositories
    refuse to resolve; left in, they surface as bare ids. This applies to every
    declared language set (unknown or recognised). Only a project with no
    language signal (``None``) admits everything and is left untouched.
    """
    if not ids_by_slot or infer_repo_languages(repo_root) is None:
        return ids_by_slot
    filtered = dict(ids_by_slot)
    for slot in _LANGUAGE_SCOPED_SLOTS:
        scope_filtered: frozenset[str] = getattr(getattr(service, slot, None), "scope_filtered_ids", frozenset())
        filtered[slot] = tuple(artifact_id for artifact_id in ids_by_slot.get(slot, ()) if artifact_id not in scope_filtered)
    return filtered


def _resolve_action_bundle(
    repo_root: Path,
    *,
    action: str,
    effective_depth: int,
    org_root: Path | None,
    mission_type: str | None,
    feature_dir: Path | None,
) -> _ActionDoctrineBundle:
    """Resolve the action doctrine bundle with the WP06 org-root fallback
    (extracted WP11/T060 so every-load delivery computes it once, before the
    depth-tier branch, without growing ``build_charter_context``).

    #3525 Fold B: when the caller does not supply an explicit *org_root*
    override, the fallback now resolves the FULL declaration-ordered chain
    of existing org packs (not just the first) and threads it through as
    *org_roots* — closing the same first-match-wins gap fixed in
    ``mission_step_contracts/executor.py``. An explicit *org_root* override
    (e.g. a ``--org-root``-driven single-path caller) is honoured verbatim
    and does not widen into the chain.
    """
    effective_org_root = org_root
    effective_org_roots: list[Path] | None = None
    if effective_org_root is None:
        from charter.offering.drg.org_pack_config import resolve_existing_org_roots  # noqa: PLC0415

        effective_org_roots = resolve_existing_org_roots(repo_root)
        if effective_org_roots:
            # Legacy single-root field, kept for org_root-only callers/back-compat
            # (e.g. any consumer of ``_ActionDoctrineBundle`` that still expects a
            # single representative root); the DRG merge itself uses the full
            # ``effective_org_roots`` chain below, not this single value.
            effective_org_root = effective_org_roots[0]

    from charter.activation.pack_context import PackContext as _PackContext  # noqa: PLC0415

    return _load_action_doctrine_bundle(
        repo_root=repo_root,
        action=action,
        effective_depth=effective_depth,
        org_root=effective_org_root,
        org_roots=effective_org_roots,
        pack_context=_PackContext.from_config(repo_root),
        mission_type=mission_type,
        feature_dir=feature_dir,
    )


def _load_action_doctrine_bundle(
    *,
    repo_root: Path,
    action: str,
    effective_depth: int,
    org_root: Path | None = None,
    org_roots: list[Path] | None = None,
    pack_context: PackContext | None = None,
    mission_type: str | None = None,
    feature_dir: Path | None = None,
) -> _ActionDoctrineBundle:
    """Load DRG-backed action doctrine artifacts for bootstrap rendering.

    The mission type keying off which the ``action:<mission_type>/<action>``
    node is resolved comes from ``meta.json`` (via ``feature_dir``) or an
    explicit ``mission_type`` argument — NEVER from the project-level
    ``template_set`` (the #883 leak, WP04 / FR-002).  ``template_set`` is
    retained solely for template-file selection (C-004) and no longer proxies
    the mission type on this governance path.

    A typeless mission (no ``mission_type`` and no ``meta.json`` type — the
    genuinely mission-less callers) degrades to an EMPTY action bundle; it is
    never resolved as software-dev (FR-003a).

    #3525 Fold B: *org_roots*, when supplied, carries the full
    declaration-ordered org-pack chain and is threaded straight through to
    :func:`charter.activation._drg_helpers.load_validated_graph` (which prefers it over
    *org_root*) AND to the ``ActiveCharterService`` built below — both halves now
    see every configured pack, not just *org_root*'s single representative
    entry. Callers that only ever supplied *org_root* (no chain resolved)
    keep the pre-fix single-root behaviour byte-identical.
    """
    from charter.activation._drg_helpers import DRGProjectValidationError, load_validated_graph
    from charter.activation.context import _build_offering_service  # noqa: PLC0415
    from charter.activation.context_renderers.delivery_table import _classify_artifact_urns
    from charter.activation.drg_activation import filter_graph_by_activation, load_org_drg
    from charter.activation.mission_type_profiles import resolve_mission_type_key
    from charter.offering.drg.loader import DRGLoadError
    from charter.offering.drg.query import resolve_context

    service = _build_offering_service(
        repo_root,
        org_roots=org_roots if org_roots else ([org_root] if org_root else None),
    )
    resolved_type = resolve_mission_type_key(
        mission_type=mission_type, feature_dir=feature_dir
    )

    # The DRG load honours the built-in + org + project three-layer overlay
    # (WP07 T034; charter-internal callers pass org_root=None for two layers).
    # An unloadable overlay or a validation error introduced by the project
    # overlay is orthogonal to charter-level selection rendering, so we collapse
    # it to an empty bundle and log a WARNING (WP04).
    ids_by_slot: Mapping[str, tuple[str, ...]] = {}
    merged_graph: DRGGraph | None = None
    roots: tuple[str, ...] = ()
    bridge_urns: tuple[str, ...] = ()
    tension_arbiters: tuple[tuple[str, tuple[str, ...]], ...] = ()
    unarbitrated_tensions: tuple[tuple[str, str], ...] = ()
    # A typeless mission has no action:<type>/<action> node to resolve; skip the
    # DRG action resolution entirely so no doctrine is inferred (FR-003a).
    if resolved_type is not None:
        try:
            merged = load_validated_graph(
                repo_root,
                org_root=org_root,
                org_roots=org_roots,
                org_fragments=load_org_drg(repo_root, strict=False),
                project_degrade=True,
            )
            # FR-032, FR-035 (WP08): apply activation filter before resolving context.
            if pack_context is not None:
                merged = filter_graph_by_activation(merged, pack_context)

            # WP02 (Decision Record 2, FR-006/007/008/014): project_directives /
            # selected_tactics / selected_paradigms are re-derived from
            # pack_context.activated_* instead of the stale
            # governance.charter.selected_* (_load_doctrine_selection). A
            # wholly-absent pack_context collapses to the SAME "no filter
            # configured" state as a supplied PackContext whose field is
            # None -- both resolve to the "all built-ins" default, never
            # empty sets (see _catalog_default_or_activated and
            # tests/charter/test_activation_consumers.py's
            # *_none_path_matches_no_filter_at_all regression net).
            #
            # WP02 ruling 2 (reviews/wp02.ruling-2.md): "all built-ins" now
            # resolves from THIS resolution's own active graph (``merged``,
            # already activation-filtered above) unioned with the real
            # built-in catalog -- never a bare load_offering_catalog() call
            # alone -- via _graph_and_catalog_default_ids. Computed here,
            # after ``merged`` exists and before any consumption site (roots
            # below, _classify_artifact_urns) iterates it; the typeless-
            # mission branch below never loads a graph and never consumes
            # these three names, so nothing needs them precomputed earlier.
            catalog = load_offering_catalog()
            activated_directives_arg = (
                pack_context.activated_directives if pack_context is not None else None
            )
            project_directives = {
                _normalize_directive_id(d)
                for d in _catalog_default_or_activated(
                    activated_directives_arg,
                    _graph_and_catalog_default_ids(merged, NodeKind.DIRECTIVE, catalog.directives),
                )
            }
            activated_tactics_arg = (
                pack_context.activated_tactics if pack_context is not None else None
            )
            selected_tactics = _catalog_default_or_activated(
                activated_tactics_arg,
                _graph_and_catalog_default_ids(merged, NodeKind.TACTIC, catalog.tactics),
            )
            activated_paradigms_arg = (
                pack_context.activated_paradigms if pack_context is not None else None
            )
            selected_paradigms = _catalog_default_or_activated(
                activated_paradigms_arg,
                _graph_and_catalog_default_ids(merged, NodeKind.PARADIGM, catalog.paradigms),
            )

            # Preserve the org-pack required_<kind> union (Decision Record 2's
            # confirmed-legitimate, separate concept) onto the activated_*-derived
            # set above -- never onto the retired selected_* set. Applies even when
            # the project side is an EXPLICIT empty activated_directives (spec Edge
            # Cases): "explicitly empty" means the project contributes nothing, not
            # that the union step itself is skipped.
            org_required = _read_org_required_selections(repo_root)
            # MANDATORY (TASKS-FRESH2-001, severity 4): normalize each org-required
            # directive entry before it joins project_directives -- required_directives:
            # is legitimately authored in either stem or canonical form (verified live,
            # tests/charter/test_answers_inert_and_org_union.py::
            # TestOrgRequiredIdFormNormalizedBeforePromotion), while the DRG's
            # artifact_id and load_offering_catalog().directives are canonical-only.
            # Skipping this would reproduce Decision Record 2's own silent-exclusion
            # mechanism via the org-required path.
            project_directives |= {_normalize_directive_id(d) for d in org_required["directives"]}
            # Tactics/paradigms have no stem-vs-canonical distinction anywhere in this
            # repo's authoring convention (verified live -- no _normalize_tactic_id/
            # _normalize_paradigm_id exists in src/) -- the raw org-required entry IS
            # already canonical; see the Union/Exclusion Boundary Audit (boundary 4).
            selected_tactics |= set(org_required["tactics"])
            selected_paradigms |= set(org_required["paradigms"])


            # Explicitly activated project directives govern the project even
            # without an action edge. The filtered graph is the activation
            # authority; repository provenance distinguishes local roots from
            # built-ins, which retain their action-scoped delivery.
            local_directives = {
                node.urn.split(":", 1)[1]
                for node in merged.nodes
                if node.kind.value == "directive"
                and service.directives.get_provenance(node.urn.split(":", 1)[1]) == "project"
            } if pack_context is not None and pack_context.activated_directives is not None else set()
            action_urn = f"action:{resolved_type}/{action}"
            resolved = resolve_context(merged, action_urn, depth=effective_depth)
            ids_by_slot = _classify_artifact_urns(
                resolved.artifact_urns,
                merged,
                project_directives,
                selected_tactics,
                selected_paradigms,
                action_urn=action_urn,
                additional_directives=local_directives,
            )
            # WP15: carry the graph + traversal roots for progressive disclosure.
            # Roots mirror ``_classify_artifact_urns``: the action node plus the
            # project/selected start URNs whose requires-closure is delivered eager.
            merged_graph = merged
            roots = (
                action_urn,
                *(f"directive:{d}" for d in project_directives | local_directives),
                *(f"tactic:{t}" for t in selected_tactics),
                *(f"paradigm:{p}" for p in selected_paradigms),
            )
            # D2a: ``resolve_context``'s raw ``artifact_urns`` can reach a
            # delivered (slotted) artefact only through a node of an
            # excluded kind (e.g. ``paradigm:brownfield-onboarding``
            # ``suggests``-> ``tactic:test-to-system-reconstruction``, with no
            # paradigm selected). ``_classify_artifact_urns`` correctly never
            # delivers the paradigm itself, but that leaves it out of both
            # ``roots`` and ``delivered`` — so ``link_references`` can never
            # walk its outbound edge and the tactic ends up delivered yet
            # neither inlined nor named, silently. Carrying the raw resolved
            # set as bridge URNs restores it as a reference source without
            # making it delivered or inline.
            bridge_urns = tuple(resolved.artifact_urns)
            # WP02 (FR-009): carried verbatim from ``resolve_context`` --
            # no second graph walk here, the bundle just forwards what
            # ``resolved`` already computed.
            tension_arbiters = resolved.tension_arbiters
            unarbitrated_tensions = resolved.unarbitrated_tensions
        except (DRGLoadError, DRGProjectValidationError) as exc:
            _LOGGER.warning(
                "DRG action resolution skipped for %s/%s: %s. "
                "Charter-level selections still render.",
                resolved_type,
                action,
                exc,
            )

    ids_by_slot = _drop_scope_filtered_ids(ids_by_slot, service, repo_root)

    return _ActionDoctrineBundle(
        mission=resolved_type or "",
        directive_ids=list(ids_by_slot.get("directives", ())),
        tactic_ids=list(ids_by_slot.get("tactics", ())),
        styleguide_ids=list(ids_by_slot.get("styleguides", ())),
        toolguide_ids=list(ids_by_slot.get("toolguides", ())),
        procedure_ids=list(ids_by_slot.get("procedures", ())),
        asset_ids=list(ids_by_slot.get("assets", ())),
        glossary_pack_ids=list(ids_by_slot.get("glossary_packs", ())),
        service=service,
        merged=merged_graph,
        roots=roots,
        bridge_urns=bridge_urns,
        tension_arbiters=tension_arbiters,
        unarbitrated_tensions=unarbitrated_tensions,
    )
