"""``ActiveCharterService`` builders (WP06 T031, #2532) — the US1-frozen region.

Relocated verbatim from ``charter.activation.context``: :func:`_build_offering_service`
and :func:`_build_active_charter_service` — the **LAST** cluster of
the ``context.py`` decomposition (research.md Decision 7/8, extraction step
13). This is the region US1 (#3064 / mission
``charter-delivery-finish-context-degod``'s empty-charter workstream) touched
via ``_build_active_charter_service``'s "always wrap" contract
(R5); it was extracted here byte-identical against the then-frozen US1 code.

FR-008 unification (charter-sole-door-bypass-closure-01KZ3WAA WP01): this
module now also exposes the single canonical
:func:`build_active_charter_service` — the ONE public entry point
that replaces ``specify_cli.doctrine_service_factory.build_active_charter_service``
(the latter becomes a thin re-export of this one, C-001). It is itself a
thin delegate to :func:`_build_active_charter_service` — the
SINGLE body in this module that constructs
:class:`~charter.activation.resolver.ActiveCharterService` (cycle-2 review fix, Blocker 2:
the public function previously duplicated that body's construction logic
for the ``org_roots=None`` case, re-creating inside one module the exact
C-001 divergence risk the WP exists to close). It also collapses the "build
raw, conditionally wrap" pattern previously duplicated inline at
``specify_cli/charter_runtime/lint/checks/org_layer.py`` (both provenance-
scan sites now route the raw inner construction through
:func:`_build_offering_service` below — the one place in this codebase that
constructs a raw ``charter.offering.service.CharterOfferingService`` — then wrap with
``charter.activation.resolver.ActiveCharterService(inner, pack_context=None)``, the
sanctioned unfiltered-diagnostic form; see that module's docstring) and
``specify_cli/cli/commands/charter/generate.py`` (FR-002). The two former
"canonical" builders diverged on two axes; the unification always picks the
*fuller* behaviour on each:

* ``active_languages=infer_repo_languages(repo_root)`` is always computed
  (the pre-existing behaviour of :func:`_build_offering_service` below, i.e.
  this module's own prior behaviour). Issue #3292: this was, until then, an
  independent computation from ``charter.activation.compiler.compile_charter``'s own
  ``catalog.languages`` stamp -- a compile with no active-language signal
  wrote a persisted empty list that this builder's *next* invocation of
  :func:`~charter.activation.language_scope.infer_repo_languages` then read back as
  authoritative "admit none", degrading language-scoped styleguides/
  toolguides on the second and every subsequent ``charter generate``. Both
  call sites now route through the exact same function (``compile_charter``
  additionally passes its in-memory interview, which this builder --
  lacking one -- does not), so they can no longer diverge. See
  :func:`~charter.activation.language_scope.infer_repo_languages`'s docstring for the
  full resolution contract.
* ``org_roots`` is always self-resolved via
  :func:`charter.offering.drg.org_pack_config.resolve_org_roots` when a caller does
  not supply an explicit override (the prior behaviour of
  ``specify_cli.doctrine_service_factory``'s builder) — no caller can
  silently lose the org layer by omitting the argument.

Cycle note: :func:`_build_active_charter_service` calls
:func:`_build_offering_service` via a function-local
``from charter.activation.context import _build_offering_service`` rather than a direct
intra-module reference. Several existing tests (e.g.
``tests/charter/test_context_include_activation.py::_patch_service``) patch
only ``charter.activation.context._build_offering_service`` and rely on that single seam
covering BOTH the wrapped (agent-profile) and unwrapped paths — a guarantee
that held for free while both functions lived in ``charter.activation.context`` itself.
Routing the inner call back through ``charter.activation.context`` (which re-exports
this module's :func:`_build_offering_service` by reference) preserves that
single-patch-point contract after the relocation. :func:`_build_offering_service`
similarly resolves ``infer_repo_languages`` via a function-local import from
``charter.activation.context`` — ``tests/charter/test_context.py`` patches
``charter.activation.context.infer_repo_languages`` directly. The private
:func:`_build_active_charter_service` keeps its ``org_roots``
override parameter (unlike the new public function) precisely so this
existing patch seam and its callers (``charter.activation.context``'s agent-profile
include branch, ``charter.activation.profile_resolution``) are unaffected by the
unification.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from charter.activation.resolver import ActiveCharterService
    import charter.offering.service as _offering_service_module
    from charter.activation.interview import CharterInterview

from charter.activation._doctrine_paths import resolve_project_root

__all__ = [
    "_build_active_charter_service",
    "_build_offering_service",
    "build_active_charter_service",
]


def _build_offering_service(
    repo_root: Path,
    *,
    org_roots: list[Path] | None = None,
    agent_profile_overlay_dir: Path | None = None,
    interview: CharterInterview | None = None,
    prefer_interview: bool = False,
) -> _offering_service_module.CharterOfferingService:
    """Build a CharterOfferingService for the given repo root.

    The project-root candidate list (in priority order):
    1. ``.kittify/doctrine/``  — Phase 3 synthesis target (FR-009 / T025).
    2. ``src/charter/offering/``       — code-local built-in-layer path.
    3. ``doctrine/``           — flat fallback.

    Discovery is conditional on directory presence so legacy (pre-synthesis)
    projects see byte-identical behaviour (R-2 mitigation).

    Cross-reference: ``compiler._default_active_charter_service`` uses the same
    ``resolve_project_root`` helper from ``charter.activation._doctrine_paths``.

    WP07: callers in ``specify_cli`` may supply explicit *org_roots* (a list
    of org doctrine snapshot paths) so the resulting service includes the
    configured org layer in provenance tracking.  Charter-internal callers
    omit the argument and get the built-in-plus-project baseline.

    #3176 (WP02): callers may also supply *agent_profile_overlay_dir* to point
    the inner service's agent-profile project overlay at an arbitrary path
    (e.g. ``.kittify/agent_profiles``). Like *org_roots*, it is passed into
    :class:`~charter.offering.service.CharterOfferingService` **only when set**, so
    charter-internal callers that omit it see byte-identical kwargs (NFR-002).

    #4614 / FR-011 (split-brain fix): a *regenerate* re-derives the project
    languages from the current interview, so the language gate this service
    applies must resolve under the SAME languages ``compile_charter`` stamps.
    *interview* / *prefer_interview* are forwarded to the one
    ``infer_repo_languages`` call **only when set**; every other caller keeps the
    compiled-first, argument-free ``infer_repo_languages(repo_root)`` call.
    """
    from charter.offering.service import CharterOfferingService

    # Patch seam, see module docstring.
    from charter.activation.context import infer_repo_languages  # noqa: PLC0415

    # No built_in_root kwarg: the repositories self-resolve
    # ``packs/built-in/<kind>`` via the built_in_dir seam (default None is
    # behaviour-preserving here; WP04 drops the now-dead param from
    # CharterOfferingService entirely). Mission relocate-builtin-doctrine-packs moved
    # the built-in artefacts out of ``src/doctrine`` into ``packs/built-in``; a
    # ``resolve_offering_root()`` here would point at the emptied ``src/doctrine``
    # tree and silently load nothing.
    project_root = resolve_project_root(repo_root)
    if interview is None and not prefer_interview:
        active_languages = infer_repo_languages(repo_root)
    else:
        active_languages = infer_repo_languages(repo_root, interview=interview, prefer_interview=prefer_interview)
    # Only pass ``org_roots``/``agent_profile_overlay_dir`` when each carries a
    # value so charter-internal callers see byte-identical kwargs (preserves
    # existing test stubs and downstream constructors that may not declare the
    # parameters). Nested rather than ``**kwargs``-unpacked so ``mypy --strict``
    # can still type-check every argument against the constructor signature.
    if agent_profile_overlay_dir is not None:
        if org_roots:
            return CharterOfferingService(
                project_root=project_root,
                active_languages=active_languages,
                org_roots=org_roots,
                agent_profile_overlay_dir=agent_profile_overlay_dir,
            )
        return CharterOfferingService(
            project_root=project_root,
            active_languages=active_languages,
            agent_profile_overlay_dir=agent_profile_overlay_dir,
        )
    if org_roots:
        return CharterOfferingService(
            project_root=project_root,
            active_languages=active_languages,
            org_roots=org_roots,
        )
    return CharterOfferingService(
        project_root=project_root,
        active_languages=active_languages,
    )


def _self_resolve_existing_org_roots(repo_root: Path) -> list[Path]:
    """Return every configured org-pack root for *repo_root* that exists on disk.

    Single call site for the FR-008 "org_roots always self-resolved" axis —
    both :func:`_build_active_charter_service`'s default and
    :func:`build_active_charter_service` route through this one
    helper so the resolution rule can never drift between them. Delegates to
    the shared :func:`charter.offering.drg.org_pack_config.resolve_existing_org_roots`
    primitive (#3525 Fold A) — this was the precedent every other
    "does this org root exist" consumer now routes onto instead of
    re-implementing the filter comprehension independently.
    """
    from charter.offering.drg.org_pack_config import resolve_existing_org_roots  # noqa: PLC0415

    roots: list[Path] = resolve_existing_org_roots(repo_root)
    return roots


def _build_active_charter_service(
    repo_root: Path,
    *,
    org_roots: list[Path] | None = None,
    agent_profile_overlay_dir: Path | None = None,
    interview: CharterInterview | None = None,
    prefer_interview: bool = False,
) -> ActiveCharterService:
    """Build an *activation-aware* doctrine service for ``--include`` fetches.

    FR-016: ``charter context --include agent-profile:<id>`` must inherit the
    charter activation gate so that a non-activated profile is treated as a
    structured miss rather than silently rendered. This is the **scoped**
    counterpart to :func:`_build_offering_service`: it builds the same inner
    service (identical kwargs) and wraps it with the activation-aware
    :class:`charter.activation.resolver.ActiveCharterService`, supplying a freshly constructed
    :class:`~charter.activation.pack_context.PackContext` for *repo_root*.

    Only the ``agent-profile`` include branch routes through this helper; the
    other five callers of :func:`_build_offering_service` are deliberately left
    on the unwrapped service so their return type and behaviour are unchanged.

    Single builder contract (R5): the service is ALWAYS wrapped, even when
    ``activated_agent_profiles is None``. The wrapper's three-state filter
    treats ``None`` as "admit all", so the unrestricted case stays byte-identical
    in *behaviour* to the legacy fetch path while giving both activation-service
    builders one contract — ``_inner`` is always valid and ``.agent_profiles``
    is always a gated ``dict``.

    FR-008: when *org_roots* is not supplied (the common case — charter's own
    callers historically left this ``None``), it is now self-resolved via
    :func:`_self_resolve_existing_org_roots` rather than left empty, matching
    :func:`build_active_charter_service`'s always-self-resolve
    behaviour. An explicit *org_roots* override (e.g.
    ``charter.activation.context``'s ``--org-root``-driven single-path list, or
    ``charter.activation.profile_resolution``'s pre-resolved list) is still honoured
    verbatim — this only closes the "caller passed nothing" gap.
    """
    from charter.activation.context import _build_offering_service  # noqa: PLC0415
    from charter.activation.pack_context import PackContext
    from charter.activation.resolver import ActiveCharterService

    resolved_org_roots = org_roots if org_roots is not None else _self_resolve_existing_org_roots(repo_root)
    # Forward ``agent_profile_overlay_dir`` only when set: the common ``None``
    # case must reach ``_build_offering_service`` with the byte-identical
    # ``(repo_root, org_roots=...)`` call the ``charter.context`` monkeypatch
    # stubs (``lambda repo_root, *, org_roots=None: ...``) expect — passing the
    # extra kwarg unconditionally raises ``TypeError`` against those stubs
    # (NFR-002). The overlay is still threaded through whenever a caller
    # (e.g. the profiles projection) actually supplies it.
    # *interview* / *prefer_interview* (#4614) follow the same "only when set"
    # rule so a stub without those parameters keeps working.
    language_kwargs: dict[str, Any] = {}
    if interview is not None or prefer_interview:
        language_kwargs = {"interview": interview, "prefer_interview": prefer_interview}
    if agent_profile_overlay_dir is not None:
        inner = _build_offering_service(
            repo_root,
            org_roots=resolved_org_roots,
            agent_profile_overlay_dir=agent_profile_overlay_dir,
            **language_kwargs,
        )
    else:
        inner = _build_offering_service(repo_root, org_roots=resolved_org_roots, **language_kwargs)
    pack_context = PackContext.from_config(repo_root)
    return ActiveCharterService(inner, pack_context=pack_context)


def build_active_charter_service(
    repo_root: Path,
    *,
    agent_profile_overlay_dir: Path | None = None,
    interview: CharterInterview | None = None,
    prefer_interview: bool = False,
) -> ActiveCharterService:
    """Build the ONE canonical activation-aware ``ActiveCharterService`` (FR-008, C-001).

    This is the single unified builder — replacing
    ``specify_cli.doctrine_service_factory.build_active_charter_service``
    (now a thin re-export of this function) and the inline "build raw,
    conditionally wrap" pattern previously duplicated in
    ``specify_cli/charter_runtime/lint/checks/org_layer.py`` and
    ``specify_cli/cli/commands/charter/generate.py`` (FR-002). See this
    module's docstring for the two behavioural axes the unification picks the
    *fuller* option on (``active_languages`` always computed, ``org_roots``
    always self-resolved).

    Unlike the private :func:`_build_active_charter_service`, this
    public function exposes no ``org_roots`` override — every current call site
    wants the fully-resolved, activation-aware service; a caller that needs an
    explicit ``org_roots`` override (or the unfiltered diagnostic mode,
    ``pack_context=None``) constructs :class:`charter.activation.resolver.ActiveCharterService`
    directly, per the "unfiltered-diagnostic contract" documented in this
    mission's ``data-model.md``. The one override it does forward is
    *agent_profile_overlay_dir* (see below).

    Parameters
    ----------
    repo_root:
        Repository root containing ``.kittify/config.yaml``.
    interview, prefer_interview:
        #4614 / FR-011: ``charter generate --from-interview`` passes the
        current interview with ``prefer_interview=True`` so the language gate
        resolves under the languages the regenerate is about to stamp, not the
        stale compiled list. Defaults keep the compiled-first behaviour.

    Returns
    -------
    charter.activation.resolver.ActiveCharterService
        The activation-aware wrapper, always wrapped (never a raw, unwrapped
        service — closing the fail-open gap FR-002 named at the three
        collapsed call sites above).

    Cycle-2 review fix (Blocker 2): this is a **thin delegate** to
    :func:`_build_active_charter_service` with no ``org_roots``
    override, rather than a second copy of its construction body. Prior to
    this fix, both functions independently called ``ActiveCharterService(...)``
    with byte-identical logic for the ``org_roots=None`` case — exactly the
    C-001 "two canonical builders can silently diverge" risk this WP exists
    to close, re-created *inside* this one module. Only one body may
    construct the wrapper now; this function exists purely for the
    no-override call shape every current caller wants.

    #3176 (WP02): the optional *agent_profile_overlay_dir* is the one override
    this public builder does forward — it points the inner service's
    agent-profile project overlay at a caller-chosen path (e.g.
    ``.kittify/agent_profiles``). Note that the production consumer
    ``specify_cli.tool_surface.profiles.projection.default_profile_repository``
    does NOT use this public builder: it calls the private
    :func:`_build_active_charter_service` with ``org_roots=[]`` to
    suppress org-root self-resolution (C-008 — org profiles must enter
    exclusively through the activation gate, which this self-resolving public
    builder cannot express) while still threading the overlay seam. This
    public ``agent_profile_overlay_dir`` param is therefore test-covered
    (``tests/charter/test_builder_overlay_seam.py``) but has no current
    production caller; it is kept because it is harmless and exercised. Default
    ``None`` keeps the delegation byte-identical (NFR-002); this stays a thin
    delegate — no second wrapper construction site (C-006).
    """
    if interview is None and not prefer_interview:
        return _build_active_charter_service(repo_root, agent_profile_overlay_dir=agent_profile_overlay_dir)
    return _build_active_charter_service(
        repo_root,
        agent_profile_overlay_dir=agent_profile_overlay_dir,
        interview=interview,
        prefer_interview=prefer_interview,
    )
