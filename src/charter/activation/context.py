"""Charter context bootstrap for prompt generation."""

# ⚠️ ORCHESTRATION SHIM (#2532 de-godding complete — do NOT add new
# responsibilities here). The former ~3243 LOC module was decomposed into
# cohesive sibling modules — see #2532 (WP04 leaf clusters, WP05 render
# seams, WP06 service seams + residual). New context-resolution logic
# belongs in a sibling, not here; this file stays the 3 public orchestrators
# (``build_charter_context`` / ``build_charter_context_include`` /
# ``build_charter_context_json``) plus the FR-009 re-export block that keeps
# every relocated private symbol importable from ``charter.activation.context`` for
# existing test coverage.

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    import charter.offering.service as _offering_service_module

    from charter.activation.scope import CharterScope

from ruamel.yaml import YAML as YAML

from charter.activation.action_doctrine_bundle import (
    _ActionDoctrineBundle as _ActionDoctrineBundle,
    _load_action_doctrine_bundle as _load_action_doctrine_bundle,
    _resolve_action_bundle as _resolve_action_bundle,
)
from charter.bundle import CHARTER_MD, CHARTER_YAML
from charter.activation.charter_md_parsing import _extract_policy_summary as _extract_policy_summary
from charter.activation.context_contract import CONTEXT_SCHEMA_VERSION as CONTEXT_SCHEMA_VERSION
from charter.activation.context_json import (
    _EMPTY_ORG_CHARTER as _EMPTY_ORG_CHARTER,
    _bundle_root_for_json as _bundle_root_for_json,
    _project_charter_json_block as _project_charter_json_block,
    _project_directive_entries as _project_directive_entries,
    _project_directive_entries_with_source as _project_directive_entries_with_source,
)
from charter.activation.context_renderers.artifact_bodies import (
    _jsonable_artifact_value as _jsonable_artifact_value,
)
from charter.activation.context_renderers.bootstrap_text import (
    _render_bootstrap_text as _render_bootstrap_text,
)
from charter.activation.context_renderers.compact_governance import (
    _compact_section_block as _compact_section_block,
)
from charter.activation.context_renderers.delivery_table import (
    _Gate as _Gate,
    _classify_artifact_urns as _classify_artifact_urns,
    action_bundle_bucket as action_bundle_bucket,
    action_bundle_gate as action_bundle_gate,
)
from charter.activation.context_renderers.profile_sections import (
    _render_profile_sections as _render_profile_sections,
)
from charter.activation.context_renderers.reference_pointers import (
    _load_references as _load_references,  # FR-009 preserved surface (no internal use)
)
from charter.activation.context_renderers.template_include import (
    _render_agent_profile_include_selector,
    _render_catalog_kind_include_selector,
    _render_doctrine_artifact_include as _render_doctrine_artifact_include,  # FR-009 preserved surface
    _render_generic_artifact_include,
    _render_section_include_selector,
    _render_template_include,
    _resolve_include_kind,
)
from charter.activation.context_result_builders import (
    CharterContextResult as CharterContextResult,
    build_bootstrap_context_result as _bootstrap_context_result,
    build_compact_bundle_context_result as _compact_bundle_context_result,
    build_missing_charter_context_result as _missing_charter_context_result,
    build_non_bootstrap_context_result as _non_bootstrap_context_result,
)
from charter.activation.context_state import (
    KITTIFY_DIRNAME as KITTIFY_DIRNAME,
    _MIN_EFFECTIVE_DEPTH as _MIN_EFFECTIVE_DEPTH,
    _prepare_context_state as _prepare_context_state,
)
from charter.activation.active_charter_service_builder import (
    _build_active_charter_service as _build_active_charter_service,
    _build_offering_service as _build_offering_service,
)
from charter.activation import progressive_disclosure as _pd
from charter.activation.governance_references import collect_governance_reference_status
from charter.activation.language_scope import infer_repo_languages as infer_repo_languages
from charter.activation.org_pack_discovery import (
    _iter_org_charter_docs as _iter_org_charter_docs,
    _load_doctrine_selection as _load_doctrine_selection,
    _missing_pack_diagnostic as _missing_pack_diagnostic,
    _read_org_required_selections as _read_org_required_selections,
)
from charter.activation.profile_resolution import (
    _ACTIVATION_AWARE_PROFILE_MAPS as _ACTIVATION_AWARE_PROFILE_MAPS,
    _activation_aware_profile_map as _activation_aware_profile_map,
    _default_agent_profile_repository as _default_agent_profile_repository,
    _existing_org_roots as _existing_org_roots,
    _load_agent_profile as _load_agent_profile,
)

__all__ = [
    "BOOTSTRAP_ACTIONS",
    "CharterContextResult",
    "build_charter_context",
    "build_charter_context_include",
    "build_charter_context_json",
]


_LOGGER = logging.getLogger(__name__)


BOOTSTRAP_ACTIONS: frozenset[str] = frozenset({"specify", "plan", "implement", "review"})


def _action_node_declared(bundle: _ActionDoctrineBundle, action: str) -> bool:
    """FR-001 (#3596, ADR 2026-08-21-1-charter-gate-predicate-inversion).

    Node-URN membership predicate -- NOT an empty-grain check.
    ``resolve_context`` already degrades an undeclared node to empty grain,
    and action nodes are activation-filter-exempt while their ``scope``-edge
    targets are not; a declared-but-activation-starved node therefore
    legitimately yields ``True`` (the caller then renders ``bootstrap`` with
    possibly empty typed arrays -- this is correct, not a bug).

    ``bundle.merged`` is the single per-call DRG carrier (NFR-001 -- no
    second load, no memoization); it is ``None`` exactly when the mission
    type was unresolved (typeless), which must always yield ``False``
    (``compact``, FR-003).  ``bundle.mission`` mirrors the type used to
    resolve the bundle (``resolved_type or ""`` -- see
    ``_load_action_doctrine_bundle`` in
    ``charter.activation.action_doctrine_bundle``),
    so reusing it here keeps the membership test on the exact node the
    bundle was resolved against.

    Kept in this module (rather than alongside ``_ActionDoctrineBundle`` in
    ``charter.activation.action_doctrine_bundle``) because it is WP02's owned-files
    boundary (``rc3-charter-gate-predicate-inversion``, #3596): both
    consumers (``build_charter_context`` / ``build_charter_context_json``
    below) live here, and this predicate is inseparable from the two gate
    sites it backs.
    """
    return bundle.merged is not None and (
        f"action:{bundle.mission}/{action}" in bundle.merged.node_urns()
    )


def build_charter_context(
    repo_root: Path,
    *,
    profile: str | None = None,
    action: str,
    mark_loaded: bool = True,
    depth: int | None = None,
    org_root: Path | None = None,
    scope: CharterScope | None = None,
    mission_type: str | None = None,
    feature_dir: Path | None = None,
    suppress_project_resolver: bool = False,
) -> CharterContextResult:
    """Build charter context by querying the Doctrine Reference Graph.

    Parameters
    ----------
    suppress_project_resolver:
        WP03/#3064 -- when ``True``, the compact-mode governance block does
        NOT merge the project catalog-fallback directives resolved by
        :func:`charter.activation.resolver.resolve_project_governance`. Under a wholly
        empty charter that resolver catalog-falls-back to every built-in
        directive (research.md Decision 4); this keyword lets the
        empty-charter/generic-agent dispatch seam
        (``specify_cli.invocation.executor``) suppress that specific merge
        without changing ``_resolve_directives_selection`` — or this
        function's default behaviour — for any other caller. Defaults to
        ``False`` (bootstrap-mode rendering is unaffected either way; only
        the compact-mode render paths consult this flag).
    mission_type:
        Explicit canonical mission type (e.g. ``documentation``) for the action
        doctrine grain.  Takes precedence over ``feature_dir``.  When both are
        ``None`` the action grain is typeless and resolves to an empty bundle —
        never software-dev (FR-003a).  This replaces the retired
        ``template_set``-as-mission-type inference (#883 / FR-002).
    feature_dir:
        The mission's ``kitty-specs/<mission-slug>/`` directory; its
        ``meta.json`` ``mission_type`` field keys the action doctrine grain when
        ``mission_type`` is not given.
    org_root:
        Optional path to the configured org doctrine snapshot.  When provided,
        the three-layer (built-in + org + project) DRG overlay is used and the
        ``ActiveCharterService`` is constructed with the org layer included.
        Charter-layer callers leave this as ``None``; ``specify_cli`` callers
        resolve the value via :func:`charter.offering.drg.org_pack_config.resolve_org_roots`
        and pass it explicitly (preserving the kernel <- doctrine <- charter <-
        specify_cli dependency direction).
    scope:
        Optional :class:`charter.activation.scope.CharterScope` produced by
        :func:`charter.activation.scope_router.build_with_scope`.  When provided, the
        effective ``repo_root`` for this call is ``scope.root`` so the
        nearest-enclosing charter is used instead of the repository root.
        This satisfies FR-010 spec wording: callers MAY pass a pre-resolved
        scope or rely on the :func:`build_with_scope` convenience wrapper.
        When ``scope`` is ``None`` the argument is ignored and *repo_root* is
        used as-is (backward-compatible with all existing callers).

        MEDIUM-2 (post-merge remediation cycle 1): added as a keyword-only
        pass-through so the FR-010 spec contract "SHALL accept an optional
        scope parameter" is honoured without breaking the WP07 call-site
        signature.
    """
    # MEDIUM-2: honour the scope kwarg by overriding repo_root when provided.
    if scope is not None:
        repo_root = scope.root
    profile_record = _load_agent_profile(profile, repo_root) if profile else None

    # WP06 / FR-015 — surface a loud diagnostic when the consumer's
    # config references an org pack whose snapshot is missing on disk.
    # We render the diagnostic into the bootstrap text (rather than
    # raising) so the prompt body carries the actionable error to the
    # operator even when the caller does not catch the exception.
    missing_pack_diagnostic = _missing_pack_diagnostic(repo_root)

    from charter.activation.sync import ensure_charter_bundle_fresh

    sync_result = ensure_charter_bundle_fresh(repo_root)
    canonical_root = sync_result.canonical_root if sync_result and sync_result.canonical_root else repo_root

    normalized = action.strip().lower()
    # FR-005 (charter-pack-usage-journey WP03): the presence gate below is
    # authoritative on ``charter.yaml`` (``bundle.CHARTER_YAML``) -- a
    # charter.yaml-only project (charter.md deleted, SC-002) must still
    # render. It is deliberately an OR with the legacy ``charter.md`` check
    # (mode is "missing" only when BOTH are absent), not a hard swap: a wide
    # swath of the existing suite seeds only ``charter.md`` (pre-charter.yaml
    # fixtures that predate this mission), and a strict charter.yaml-only
    # gate regresses every one of them to "missing" -- verified via a full
    # ``-k charter`` sweep (26 failures) before landing on this OR form.
    # ``charter_path`` stays a ``CHARTER_MD`` reference because the
    # prose/section readers further down (the bootstrap "Source:" line,
    # ``_extract_policy_summary``, the ``--include section:<id>`` selector)
    # legitimately need ``charter.md`` — collapsing the two onto one path
    # constant is the C-003 regression this WP guards against.
    #
    # FR-002 (doctrine-charter-split-unification WP01) — CLASSIFICATION, so a
    # later reader does not "tidy" this into something it was never meant to be:
    #
    #   * This is the **C-003 prose-presence gate**: it answers "is there any
    #     charter surface to render for a human?" — present when EITHER the
    #     ``charter.yaml`` authority OR the ``charter.md`` readable secondary
    #     exists. ``charter.yaml`` takes **precedence** for governance (the
    #     compiled bundle and ``_load_references``' ``catalog.references``
    #     projection are read from it, never parsed out of ``charter.md``);
    #     ``charter.md`` contributes prose only.
    #   * It is deliberately **NOT an authority-presence gate**. Those are
    #     FR-003/004/006 (the retired dashboard, analysis, the ``--json``
    #     ``project_charter.present`` signal). FR-003 left with the bundled
    #     dashboard (#5530); FR-004
    #     (``analysis_report._charter_path``) prefers ``charter.yaml`` and falls
    #     back to ``charter.md`` when ``charter.yaml`` has not been compiled
    #     yet -- restored md-fallback (landing-fold fix), not a yaml-only
    #     signal. FR-006 (``_project_charter_json_block``, the ``--json``
    #     ``project_charter.present`` signal) keys SOLELY on ``charter.yaml``
    #     by deliberate contract (no md fallback; see the ``#2787`` contract
    #     note). The divergence between this OR-gate and FR-006's yaml-only
    #     signal is intentional, not drift; FR-003/004's md-fallback narrows
    #     that divergence but does not close it (yaml still takes precedence
    #     when both exist).
    #   * Therefore: do **NOT** tidy this into a strict ``charter.yaml``-only
    #     gate. Doing so demotes every ``charter.md``-only project to "missing"
    #     (26 fixtures, above) and contradicts the charter.md-as-secondary
    #     model. The four presence cells and the yaml-precedence differential
    #     are pinned in ``tests/charter/test_context_prose_presence_pin.py``.
    charter_path = canonical_root / CHARTER_MD
    charter_yaml_path = canonical_root / CHARTER_YAML

    def _augment(text: str) -> str:
        if missing_pack_diagnostic:
            return missing_pack_diagnostic + "\n\n" + text
        return text

    state_bundle = _prepare_context_state(repo_root, normalized, depth)

    # WP11 (T060/B-3) — compute the bundle BEFORE the depth-tier branch so it
    # is delivered on EVERY load; the old order returned compact before it existed.
    # FR-001/FR-004 (rc3-charter-gate-predicate-inversion WP02, #3596): the
    # bundle is now resolved for EVERY action -- bootstrap (fast-path) actions
    # already needed it to render their grain; non-bootstrap actions now pay
    # the same single graph load (NFR-001, no memoization -- see the ADR) so
    # the node-URN membership predicate below can test the actually-declared
    # DRG action node instead of the coarse BOOTSTRAP_ACTIONS set. This does
    # NOT depend on charter.md/charter.yaml presence (it reads only the DRG +
    # org/project doctrine), so it is safe to resolve ahead of the
    # charter-presence gate below.
    doctrine_bundle = _resolve_action_bundle(
        repo_root,
        action=normalized,
        effective_depth=state_bundle.effective_depth,
        org_root=org_root,
        mission_type=mission_type,
        feature_dir=feature_dir,
    )

    # FR-001/FR-002: the 4-token fast path always renders bootstrap without
    # consulting the predicate (AC-1, unchanged). Every other action gates on
    # node-URN membership -- NOT empty-grain (a declared-but-activation-starved
    # node legitimately renders bootstrap with empty typed arrays; see
    # `_action_node_declared`'s docstring). An undeclared action returns HERE,
    # before the charter-presence gate below -- preserving the pre-fix
    # semantics that a non-bootstrap action's compact governance render never
    # depended on charter.md/charter.yaml existing (``_non_bootstrap_context_result``
    # sources project directives from ``.kittify/config.yaml``/charter.yaml
    # directly and degrades gracefully when absent).
    if normalized not in BOOTSTRAP_ACTIONS and not _action_node_declared(
        doctrine_bundle, normalized
    ):
        return _non_bootstrap_context_result(
            repo_root,
            normalized,
            depth,
            profile_record,
            suppress_project_resolver=suppress_project_resolver,
            augment=_augment,
        )

    # From here the action WILL deliver grain (fast-path or a declared node),
    # so the charter-presence gate applies -- matching the pre-fix ordering
    # for bootstrap actions (this is a NEW dependency for a declared
    # non-fast-path action, since it now reaches the same rendering path).
    if not charter_yaml_path.exists() and not charter_path.exists():
        return _missing_charter_context_result(normalized, state_bundle, augment=_augment)

    if state_bundle.effective_depth < _MIN_EFFECTIVE_DEPTH:
        # Steady-state load: deliver via the widened compact rail (T061/FR-010).
        return _compact_bundle_context_result(
            repo_root,
            normalized,
            state_bundle,
            profile_record,
            doctrine_bundle,
            suppress_project_resolver=suppress_project_resolver,
            mark_loaded=mark_loaded,
            augment=_augment,
        )

    return _bootstrap_context_result(
        repo_root,
        normalized,
        charter_path,
        canonical_root,
        state_bundle,
        doctrine_bundle,
        profile_record,
        mark_loaded=mark_loaded,
        augment=_augment,
    )


def build_charter_context_include(
    repo_root: Path,
    selector: str,
    *,
    action: str | None = None,
    org_root: Path | None = None,
) -> str:
    """Render one fetch-deferred governance selector.

    The selector kind is routed through the canonical
    :meth:`~charter.offering.artifact_kinds.ArtifactKind.from_operator_token` resolver
    (WP01), so hyphenated operator tokens such as ``agent-profile`` and
    ``mission-step-contract`` resolve to their canonical underscore kinds
    without a per-surface kind table (R-009 / CC-4). The two non-artifact
    selectors — ``section`` (a charter heading) and ``artifact`` (the
    best-effort activation selector) — are handled before the canonical
    resolver. ``template:<mission>/<name>`` resolves through WP18's
    :func:`charter.offering.template_catalog.resolve_template_by_id` (FR-034).

    Unknown selector kinds fail closed with the canonical vocabulary error
    raised by :meth:`ArtifactKind.from_operator_token` (no silent fallback).
    """
    from charter.offering.artifact_kinds import ArtifactKind

    kind, separator, identifier = selector.partition(":")
    kind = kind.strip().lower()
    identifier = identifier.strip()
    if not separator or not kind or not identifier:
        raise ValueError("Expected --include selector in '<kind>:<id>' form.")

    if kind == "section":
        return _render_section_include_selector(repo_root, selector, identifier, action)

    org_roots = [org_root] if org_root is not None else None

    if kind == "artifact":
        service = _build_offering_service(repo_root, org_roots=org_roots)
        return _render_generic_artifact_include(service, identifier)

    # Route every other kind through the canonical operator-token resolver so
    # hyphenated tokens (``agent-profile``) and canonical underscore tokens
    # (``agent_profile``) both resolve, and unknown tokens fail closed with the
    # shared vocabulary error (no second kind enumeration here — CC-4).
    resolved_kind = _resolve_include_kind(kind, selector)

    if resolved_kind is ArtifactKind.TEMPLATE:
        return _render_template_include(repo_root, identifier, selector)

    canonical_kind = resolved_kind.value

    # FR-016: the agent-profile fetch path — and, as of M4, the glossary-pack
    # fetch path — inherit the charter activation gate, so they (and only they)
    # use the activation-aware service; every other include kind stays on the
    # unwrapped service. Glossary is gated because M4 gives ``GLOSSARY_PACK`` an
    # activation-gated delivery slot AND newly advertises a
    # ``--include glossary-pack:<id>`` fetch pointer
    # (``_format_inline_glossary_body``); that fetch pointer must honor the same
    # gate its delivery slot advertises, or ``--include`` leaks back the term
    # definitions the charter withheld from a de-activated pack. This needs no
    # renderer change: the activation-aware ``charter.activation.resolver.ActiveCharterService``
    # already gates ``glossary_packs`` (returning a filtered
    # ``dict[str, GlossaryPack]``), and the catalog renderer reaches the repo
    # via ``getattr(service, attr).get(id)`` — a filtered ``dict``'s ``.get``
    # is call-compatible with the repository's, so the gated service drops
    # straight into the CATALOG renderer. Agent-profile keeps its dedicated
    # renderer; glossary routes through the shared catalog render/return below,
    # exactly as it would on the plain service — only the service it renders on
    # differs. The gated service is built HERE, once (not inside a sibling
    # helper), so this stays the sole call site of
    # ``_build_active_charter_service`` — several tests monkeypatch
    # that name on this module.
    gated_service = None
    if canonical_kind in (
        ArtifactKind.AGENT_PROFILE.value,
        ArtifactKind.GLOSSARY_PACK.value,
    ):
        gated_service = _build_active_charter_service(
            repo_root, org_roots=org_roots
        )
        if canonical_kind == ArtifactKind.AGENT_PROFILE.value:
            return _render_agent_profile_include_selector(
                gated_service, canonical_kind, identifier, selector
            )

    # Shared catalog render/return. ``service`` is the gated service for the
    # glossary-pack branch and the plain service (built here — the sole call
    # site of ``_build_offering_service`` several tests monkeypatch) for every
    # other kind. The ``cast`` reconciles the two nominally distinct
    # ``ActiveCharterService`` classes; the renderer only reads ``.glossary_packs``
    # (a gated ``dict``) off the gated service, so it is structurally
    # sufficient.
    service = (
        cast("_offering_service_module.CharterOfferingService", gated_service)
        if gated_service is not None
        else _build_offering_service(repo_root, org_roots=org_roots)
    )
    result = _render_catalog_kind_include_selector(
        service, canonical_kind, identifier, selector
    )
    if result is not None:
        return result

    raise ValueError(f"Unsupported --include selector kind '{kind}'.")


def build_charter_context_json(
    repo_root: Path,
    *,
    action: str,
    org_root: Path | None = None,
    depth: int | None = None,
    org_charter_block: dict[str, object] | None = None,
    mission_type: str | None = None,
    feature_dir: Path | None = None,
    include_all: bool = False,
) -> dict[str, object]:
    """Return the structured JSON payload for ``charter context --json``.

    The payload contains:

    * ``context_schema_version`` — the top-level contract version stamp
      (:data:`~charter.activation.context_contract.CONTEXT_SCHEMA_VERSION`, #2787).
      Distinct from the nested ``org_charter.schema_version`` field, which
      versions one imported org policy document rather than this envelope.
      See ``charter.activation.context_contract`` for the versioned key ledger this
      payload is expected to satisfy (a *tracking* contract for now — not
      yet frozen; see that module's docstring).
    * ``action`` / ``mode`` — same surface as :class:`CharterContextResult`.
    * ``directives`` / ``tactics`` / ``styleguides`` / ``toolguides`` —
      action-scoped typed artifact arrays, each entry carrying a ``"source"``
      provenance field (``"builtin"`` | ``"org"`` | ``"project"``).
    * ``all_directives`` — every directive ID exposed by the project
      governance resolver, including directives extracted from the
      project-local charter even when the action-scoped ``directives`` array
      is empty.
    * ``project_charter`` — the loaded project-local charter. FR-006:
      ``present``/``path`` key on the authoritative ``charter.yaml`` bundle
      (survives ``charter.md`` deletion); ``charter.md``'s own presence/path
      are the secondary ``charter_md_present``/``charter_md_path`` fields.
    * ``org_charter`` — additive block describing org-layer governance
      policies (empty when no org pack ships an ``org-charter.yaml``).

    The *org_charter_block* is supplied by the caller as pre-loaded data —
    the charter layer must not import from ``specify_cli`` (ADR 2026-03-27-1),
    so any org-charter policy loading happens in the higher layer and is
    passed in here as a plain mapping.  Defaults to ``{"present": false,
    "packs": []}`` when omitted.

    Returns an empty-shell payload when the action is not a bootstrap action
    (the textual ``charter context`` surface is still authoritative for
    non-bootstrap actions).
    """
    normalized = action.strip().lower()
    # Single governance resolution: both ``all_directives`` and the resolution-
    # level ``directives_source`` provenance come from one
    # ``resolve_project_governance`` call (no double-resolve per payload).
    all_directives, directives_source = _project_directive_entries_with_source(repo_root)
    payload: dict[str, object] = {
        "context_schema_version": CONTEXT_SCHEMA_VERSION,
        "action": normalized,
        "directives": [],
        "tactics": [],
        "styleguides": [],
        "toolguides": [],
        "all_directives": all_directives,
        # NEW (#3728, FR-007): resolution-level provenance — which branch
        # resolved the directive set (``"catalog_fallback+project_local"`` etc.),
        # or ``null`` when the resolver raised. Distinct from the per-entry
        # ``all_directives[].source`` artifact-origin field.
        "directives_source": directives_source,
        "references": [],
        "project_charter": _project_charter_json_block(repo_root),
        "org_charter": (
            dict(org_charter_block) if org_charter_block is not None else dict(_EMPTY_ORG_CHARTER)
        ),
        "governance_references": [],
    }
    selection = _load_doctrine_selection(repo_root)
    payload["governance_references"] = [
        status.to_dict()
        for status in collect_governance_reference_status(
            repo_root,
            selection.governance_references,
        )
    ]

    state_bundle = _prepare_context_state(repo_root, normalized, depth)
    # WP11 (T060/B-3) — no depth<minimum early return: the ``--json`` half of
    # every-load delivery (where SC-001/002 are measured) delivers at every depth.

    # SPEC-ARCH-002 (T018): route through the self-resolving wrapper, the
    # same one ``build_charter_context`` (plain-text) already uses above —
    # NOT the private ``_load_action_doctrine_bundle`` directly. When
    # ``org_root`` is None, ``_resolve_action_bundle`` widens to the FULL
    # declaration-ordered org-pack chain via ``resolve_existing_org_roots``
    # (see ``charter.activation.action_doctrine_bundle``); calling
    # ``_load_action_doctrine_bundle`` directly here bypassed that widening
    # entirely and always resolved at most one org pack.
    #
    # FR-001/FR-004 (rc3-charter-gate-predicate-inversion WP02, #3596): the
    # bundle is resolved BEFORE the mode decision -- once (NFR-001, no
    # memoization) -- so a non-fast-path action can be tested for node-URN
    # membership instead of being ruled out by the coarse BOOTSTRAP_ACTIONS
    # set before a bundle ever existed.
    bundle = _resolve_action_bundle(
        repo_root,
        action=normalized,
        effective_depth=state_bundle.effective_depth,
        org_root=org_root,
        mission_type=mission_type,
        feature_dir=feature_dir,
    )

    # FR-001/FR-002: the 4-token fast path always delivers bootstrap without
    # consulting the predicate (AC-1, unchanged). Every other action gates on
    # node-URN membership -- NOT empty-grain (see
    # `_action_node_declared`'s docstring for the activation-starved case).
    if normalized not in BOOTSTRAP_ACTIONS and not _action_node_declared(
        bundle, normalized
    ):
        # WP11 (B-6) — non-bootstrap, undeclared actions carry no action
        # grain; ruled OUT explicitly (empty typed arrays), not an
        # early-return before a bundle -- the bundle above already resolved.
        payload["mode"] = "compact"
        return payload

    payload["mode"] = "bootstrap"
    service = bundle.service
    # WP15 progressive disclosure (default cadence): DTOs carry ``references[]``
    # (T081); ``requires``-reachable is inline/eager, ``suggests``-reached is
    # link/lazy (T082); ``include_all`` inlines the whole closure — a strict
    # superset (T083); the link set names every delivered artefact so the union
    # of inlined + referenced ids equals the delivered set, no cap (T084).
    payload.update(
        _pd.build_disclosure_payload(
            repos_by_kind={
                "directive": (service.directives, bundle.directive_ids),
                "tactic": (service.tactics, bundle.tactic_ids),
                "styleguide": (service.styleguides, bundle.styleguide_ids),
                "toolguide": (service.toolguides, bundle.toolguide_ids),
                # #3389: ``procedure`` is a first-class typed array. Two kinds
                # stay reference-only and travel through ``extra_delivered``
                # instead of getting their own typed array, folded into the flat
                # ``references[]`` link set by ``build_disclosure_payload``:
                #   * ``asset`` (#3037) — no resolution/install path.
                #   * ``glossary_pack`` (M4) — delivered as a term-name surface
                #     list on the bootstrap-TEXT path (WP01) and surfaced in JSON
                #     only as a ``references[]`` link, NOT a typed array: its
                #     terms are pulled on demand via
                #     ``--include glossary-pack:<id>``. Mirrors the deliberate
                #     ``asset`` asymmetry so both delivered-but-reference-only
                #     kinds are documented; adding a typed ``glossary``/
                #     ``glossary_packs`` array would change the top-level key set
                #     and require a ``context_schema_version`` bump — do not.
                "procedure": (service.procedures, bundle.procedure_ids),
            },
            extra_delivered={
                "asset": bundle.asset_ids,
                "glossary_pack": bundle.glossary_pack_ids,
            },
            merged=bundle.merged,
            roots=bundle.roots,
            include_all=include_all,
            body_of=_jsonable_artifact_value,
            bridge_urns=bundle.bridge_urns,
        )
    )
    return payload
