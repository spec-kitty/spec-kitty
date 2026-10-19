"""Charter-centric governance resolver.

Resolves active governance from charter selections and validates
selected references against available profile/tool catalogs.

Exports ``ActiveCharterService`` — an activation-aware wrapper around
:class:`charter.offering.service.CharterOfferingService`.  The wrapper applies per-kind
activation filters from :class:`~charter.activation.pack_context.PackContext` to nine
gated properties: ``paradigms``, ``procedures``, ``agent_profiles``
(pre-existing) plus ``directives``, ``tactics``, ``styleguides``,
``toolguides``, ``mission_step_contracts``, and ``glossary_packs`` (FR-005,
charter-sole-door-bypass-closure-01KZ3WAA WP01).  All other properties
delegate to the inner offering service transparently via ``__getattr__``.

It also exposes :attr:`ActiveCharterService.agent_profile_repository` — a second,
explicitly-named accessor (FR-001) returning the raw, lineage/mutation-capable
:class:`~charter.offering.agent_profiles.repository.AgentProfileRepository` for
callers that need ``register_overlay()`` or ``get_provenance()``, which the
filtered ``agent_profiles`` dict cannot support; and
:meth:`ActiveCharterService.raw_repository` (FR-002 Option A) — the generic,
per-kind form of that same "filtered dict can't do repository ops" escape
hatch, for provenance-scan callers that need raw ``list_all()``/
``get_provenance()`` access across any of the nine gated kinds.

Finally (FR-003, charter-sole-door-bypass-closure-01KZ3WAA WP05) this module
is the **sole charter-layer door** onto ``charter/offering/resolver.py``'s 6-tier
asset resolution chain. The tier functions themselves stay in
``charter/offering/resolver.py`` (charter must import charter.offering, never the reverse);
what lives here is the entry point — see the "6-tier resolution axis"
section of :class:`ActiveCharterService`. Before WP05,
``charter.activation.template_resolver.CharterTemplateResolver`` was a *second*
charter-layer object reaching ``charter.offering.resolver`` independently of this
one; WP05 reduced it to a thin delegate onto these methods, and it was later
pruned as a Cat-7 dead module (#6009), leaving this module the sole door.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from charter.activation.catalog import OfferingCatalog, load_offering_catalog
from charter.activation.identity_index import IdentityIndex
from charter.activation.kind_vocabulary import ArtifactKind
from charter.activation.reference_resolver import resolve_references_transitively
from charter.activation.schemas import DirectivesConfig, GovernanceCharterConfig
from charter.activation.sync import (
    load_directives_config,
    load_governance_config,
)
from charter.offering.drg.migration.id_normalizer import normalize_directive_id
from charter.offering.missions.repository import MissionTemplateRepository

# FR-003: the ONLY import of ``charter.offering.resolver``'s tier functions in the
# charter layer. Aliased with an ``_offering_`` prefix so a reader of a call
# site inside this module can never mistake the offering tier function for a
# charter-layer helper of the same bare name.
from charter.offering.resolver import (
    ResolutionResult,
    resolve_command as _offering_resolve_command,
    resolve_mission as _offering_resolve_mission,
    resolve_template as _offering_resolve_template,
)

__all__ = [
    "DEFAULT_TOOL_REGISTRY",
    "ActiveCharterService",
    "GovernanceResolution",
    "UNKNOWN_SELECTION_DIAGNOSTIC",
    "GovernanceResolutionError",
    "collect_governance_diagnostics",
    "resolve_governance_for_profile",
    "resolve_project_governance",
]


if TYPE_CHECKING:
    from charter.offering.agent_profiles.profile import AgentProfile
    from charter.offering.agent_profiles.repository import AgentProfileRepository
    from charter.offering.directives.models import Directive
    from charter.offering.drg.models import DRGGraph
    from charter.offering.glossary_packs.models import GlossaryPack
    from charter.offering.missions.step_contracts import MissionStepContract
    from charter.offering.pack_skills.models import PackSkill
    from charter.offering.paradigms.models import Paradigm
    from charter.offering.procedures.models import Procedure
    from charter.offering.styleguides.models import Styleguide
    from charter.offering.tactics.models import Tactic
    from charter.offering.toolguides.models import Toolguide
    import charter.offering.service as _offering_service_module
    from charter.activation.interview import CharterInterview
    from charter.activation.pack_context import PackContext

_LOGGER = logging.getLogger(__name__)

_T = TypeVar("_T")

DEFAULT_TEMPLATE_SET = "software-dev-default"

#: Fixed Mission-wide wording for a selected id no layer knows (#6407). Selections are
#: dropped with this diagnostic instead of erasing the whole governance resolution.
UNKNOWN_SELECTION_DIAGNOSTIC = (
    "Unknown selected {kind} '{token}' dropped: not found in built-in, org packs (charter_packs.org.packs)"
    + " or .kittify/charter-packs/; see 'spec-kitty charter list'."
)

#: Shared remediation sentence for an unavailable template set (Sonar S1192).
_TEMPLATE_SET_REMEDIATION = (
    "Update charter template_set to one of the available template sets, or provide it through a project override"
    + " (see 'spec-kitty charter list --show-available')."
)
DEFAULT_TOOL_REGISTRY: frozenset[str] = frozenset({"spec-kitty", "git"})

#: The nine gated-property kinds :meth:`ActiveCharterService.raw_repository`
#: recognizes -- exactly the kinds with a gated ``dict`` property above.
#: Derived from the single :class:`ArtifactKind` authority (issue #5409): the
#: charter-activatable kinds that own a standalone repository. ``ANTI_PATTERN``
#: is activatable but carries **no** gated repository property (it is a
#: re-kinded node inside another kind's fragment, never a standalone
#: ``*.anti_pattern.yaml`` repository), so it is excluded here — the one
#: activatable kind without a raw repository.
_RAW_REPOSITORY_KINDS: frozenset[str] = frozenset(kind.plural for kind in ArtifactKind if kind.activatable and kind is not ArtifactKind.ANTI_PATTERN)

# ---------------------------------------------------------------------------
# FR-003 (WP05): the 6-tier resolution axis — shared vocabulary
# ---------------------------------------------------------------------------

#: Default mission key for the tier chain. Mirrors ``charter.offering.resolver``'s own
#: per-function default so the factory entry point is a behaviour-preserving
#: pass-through rather than a second policy about "which mission". Private
#: (and absent from ``__all__``) because it is only ever a default argument
#: value baked into the signatures below — no caller imports it, and the
#: symbol-level dead-code gate rightly rejects an unimported export.
_DEFAULT_RESOLUTION_MISSION = "software-dev"

#: Tier-6 subdirectory names, matching ``charter.offering.resolver._resolve_asset``'s
#: ``subdir`` vocabulary.
_COMMAND_TEMPLATES_SUBDIR = "command-templates"
_CONTENT_TEMPLATES_SUBDIR = "templates"


@lru_cache(maxsize=8)
def _mission_template_repository(missions_root: str) -> MissionTemplateRepository:
    """Return a cached :class:`MissionTemplateRepository` for *missions_root*.

    Replaces the ``lru_cache``d ``_charter_template_resolver_for()`` helper
    that used to live in ``specify_cli/runtime/resolver.py`` (FR-003): the
    cache moves into charter alongside the resolution entry point, so the
    "repeated package-default lookups reuse the same repository" property is preserved
    without runtime holding a charter object of its own. Keyed on the
    stringified root because ``functools.lru_cache`` needs a hashable key and
    ``Path`` equality is already string equality here.
    """
    return MissionTemplateRepository(Path(missions_root))


# ---------------------------------------------------------------------------
# Activation-aware ActiveCharterService wrapper (Pattern B + C wiring)
# ---------------------------------------------------------------------------


class ActiveCharterService:
    """Activation-aware wrapper around :class:`charter.offering.service.CharterOfferingService`.

    Applies per-kind activation filters from
    :class:`~charter.activation.pack_context.PackContext` when accessing the nine gated
    properties: ``paradigms``, ``procedures``, ``agent_profiles``,
    ``directives``, ``tactics``, ``styleguides``, ``toolguides``,
    ``mission_step_contracts``, and ``glossary_packs``.  All other attributes
    delegate transparently to the underlying offering service.

    Layer rule
    ----------
    This class lives in ``charter.*`` so it can import ``PackContext``
    without violating the ``charter.offering ← charter.activation`` dependency direction.
    Callers in ``specify_cli.*`` pass a real :class:`PackContext`; callers
    in ``charter.*`` may pass ``pack_context=None`` for unfiltered access.

    Three-state filtering semantics
    --------------------------------
    * ``pack_context is None`` → no filtering; return all artifacts.
    * ``pack_context.activated_<kind> is None`` → key absent from config;
      return all artifacts (backward-compat / new-project default).
    * ``pack_context.activated_<kind> == frozenset()`` → key present but
      empty; return empty dict (explicit opt-out).
    * ``pack_context.activated_<kind> = {ids}`` → return only those IDs.
    """

    def __init__(
        self,
        _inner: _offering_service_module.CharterOfferingService,
        pack_context: PackContext | None = None,
        identity: IdentityIndex | None = None,
    ) -> None:
        # Use object.__setattr__ to bypass any potential descriptor magic.
        object.__setattr__(self, "_inner", _inner)
        object.__setattr__(self, "_pack_context", pack_context)
        object.__setattr__(self, "_identity", identity)
        object.__setattr__(self, "_activated_id_cache", {})

    # ------------------------------------------------------------------
    # Identity: activation tokens may be file stems or declared ids (#6406).
    # ------------------------------------------------------------------

    def _identity_index(self, pack_ctx: PackContext) -> IdentityIndex:
        """Return the per-service identity index, building it from *pack_ctx* on first use."""
        identity: IdentityIndex | None = object.__getattribute__(self, "_identity")
        if identity is None:
            identity = IdentityIndex.from_pack_context(pack_ctx, repo_root=pack_ctx.repo_root)
            object.__setattr__(self, "_identity", identity)
        return identity

    def _gated(self, kind: ArtifactKind, all_items: dict[str, _T], activated: frozenset[str] | None) -> dict[str, _T]:
        """Filter *all_items* (keyed by declared id) by activation tokens, in either spelling.

        ``None`` admits everything (key absent). Tokens resolve to declared ids once per
        kind per service; a token no layer knows but that names a delivered item is kept
        verbatim, and any other unknown token is logged (#4240) and kept best-effort.
        """
        if activated is None:
            return all_items
        cache: dict[ArtifactKind, frozenset[str]] = object.__getattribute__(self, "_activated_id_cache")
        ids = cache.get(kind)
        if ids is None:
            pack_ctx: PackContext = object.__getattribute__(self, "_pack_context")
            identity = self._identity_index(pack_ctx)
            resolved: set[str] = set()
            warnings: list[str] = []
            for token in activated:
                if token in all_items and not identity.knows(kind, token):
                    resolved.add(token)
                else:
                    resolved.add(identity.activation_id(kind, token, warnings))
            for warning in warnings:
                _LOGGER.warning("%s", warning)
            ids = frozenset(resolved)
            cache[kind] = ids
        return {key: item for key, item in all_items.items() if key in ids}

    def _activation_for(self, field_name: str) -> frozenset[str] | None:
        pack_ctx: PackContext | None = object.__getattribute__(self, "_pack_context")
        if pack_ctx is None:
            return None
        value: frozenset[str] | None = getattr(pack_ctx, field_name)
        return value

    # ------------------------------------------------------------------
    # Pattern B: flat catalog activation filter (paradigms, procedures)
    # ------------------------------------------------------------------

    @property
    def paradigms(self) -> dict[str, Paradigm]:
        """Return paradigms dict, filtered by ``activated_paradigms`` when set."""
        all_paradigms: dict[str, Paradigm] = {item.id: item for item in self._inner.paradigms.list_all()}
        return self._gated(ArtifactKind.PARADIGM, all_paradigms, self._activation_for("activated_paradigms"))

    @property
    def procedures(self) -> dict[str, Procedure]:
        """Return procedures dict, filtered by ``activated_procedures`` when set."""
        all_procedures: dict[str, Procedure] = {item.id: item for item in self._inner.procedures.list_all()}
        return self._gated(ArtifactKind.PROCEDURE, all_procedures, self._activation_for("activated_procedures"))

    # ------------------------------------------------------------------
    # Pattern C: direct repository activation filter (agent_profiles)
    # ------------------------------------------------------------------

    @property
    def agent_profiles(self) -> dict[str, AgentProfile]:
        """Return agent profiles dict, filtered by ``activated_agent_profiles`` when set."""
        all_profiles: dict[str, AgentProfile] = {p.profile_id: p for p in self._inner.agent_profiles.list_all()}
        return self._gated(ArtifactKind.AGENT_PROFILE, all_profiles, self._activation_for("activated_agent_profiles"))

    # ------------------------------------------------------------------
    # FR-005: six more mechanical Pattern B properties (identical filtering
    # shape to paradigms/procedures above -- a reviewer diffing any two of
    # the nine gated getters should see the same structure modulo the kind
    # name; see contracts/charter-doctrine-service-contract.md "Gated
    # properties").
    # ------------------------------------------------------------------

    @property
    def directives(self) -> dict[str, Directive]:
        """Return directives selected by exact IDs or canonical filename stems.

        Org directive IDs need not resemble their filenames. Resolve activation
        stems through the shared vocabulary before falling back to legacy ID
        aliases, and compare exact identities so distinct declarations do not
        become co-activated merely because their normalized spellings collide.
        """
        all_directives: dict[str, Directive] = {item.id: item for item in self._inner.directives.list_all()}
        return self._gated(ArtifactKind.DIRECTIVE, all_directives, self._activation_for("activated_directives"))

    @property
    def tactics(self) -> dict[str, Tactic]:
        """Return tactics dict, filtered by ``activated_tactics`` when set."""
        all_tactics: dict[str, Tactic] = {item.id: item for item in self._inner.tactics.list_all()}
        return self._gated(ArtifactKind.TACTIC, all_tactics, self._activation_for("activated_tactics"))

    @property
    def styleguides(self) -> dict[str, Styleguide]:
        """Return styleguides dict, filtered by ``activated_styleguides`` when set."""
        all_styleguides: dict[str, Styleguide] = {item.id: item for item in self._inner.styleguides.list_all()}
        return self._gated(ArtifactKind.STYLEGUIDE, all_styleguides, self._activation_for("activated_styleguides"))

    @property
    def toolguides(self) -> dict[str, Toolguide]:
        """Return toolguides dict, filtered by ``activated_toolguides`` when set."""
        all_toolguides: dict[str, Toolguide] = {item.id: item for item in self._inner.toolguides.list_all()}
        return self._gated(ArtifactKind.TOOLGUIDE, all_toolguides, self._activation_for("activated_toolguides"))

    @property
    def mission_step_contracts(self) -> dict[str, MissionStepContract]:
        """Return mission step contracts dict, filtered by ``activated_mission_step_contracts`` when set."""
        all_contracts: dict[str, MissionStepContract] = {item.id: item for item in self._inner.mission_step_contracts.list_all()}
        return self._gated(ArtifactKind.MISSION_STEP_CONTRACT, all_contracts, self._activation_for("activated_mission_step_contracts"))

    @property
    def glossary_packs(self) -> dict[str, GlossaryPack]:
        """Return glossary packs dict, filtered by ``activated_glossary_packs`` when set."""
        all_glossary_packs: dict[str, GlossaryPack] = {item.id: item for item in self._inner.glossary_packs.list_all()}
        return self._gated(ArtifactKind.GLOSSARY_PACK, all_glossary_packs, self._activation_for("activated_glossary_packs"))

    @property
    def skills(self) -> dict[str, PackSkill]:
        """Return pack skills dict, filtered by ``activated_skills`` when set."""
        all_skills: dict[str, PackSkill] = {item.id: item for item in self._inner.skills.list_all()}
        return self._gated(ArtifactKind.SKILL, all_skills, self._activation_for("activated_skills"))

    # ------------------------------------------------------------------
    # FR-001: pinned lineage/mutation accessor (NOT a gated property --
    # deliberately outside the three-state activation contract above).
    # ------------------------------------------------------------------

    @property
    def agent_profile_repository(self) -> AgentProfileRepository:
        """Return the raw, lineage/mutation-capable ``AgentProfileRepository``.

        Pinned contract (charter-sole-door-bypass-closure-01KZ3WAA WP01,
        FR-001): the filtered ``agent_profiles`` dict above cannot support
        ``register_overlay()`` (needed by
        ``specify_cli.tool_surface.profiles.projection``) or
        ``get_provenance()`` (needed by ``specify_cli.invocation.registry``
        and ``specify_cli.invocation.org_profiles``) because a ``dict`` has
        neither method. This accessor gives those callers the raw repository
        object directly, instead of reaching into ``._inner`` themselves
        (the FR-010 reach-around this accessor exists to close).

        Semantics (pinned, not a default -- see
        contracts/charter-doctrine-service-contract.md "Lineage/mutation
        accessor semantics"):

        * ``register_overlay()`` mutates the underlying repository's lineage
          graph in place. It does NOT create a way to read an unfiltered
          profile through the gated :attr:`agent_profiles` property
          afterward -- that property's three-state activation filter still
          applies on every read, including reads that follow a mutation.
          Mutation capability and activation filtering are orthogonal.
        * ``get_provenance()`` is a read-only lookup on the raw repository;
          it answers "which layer supplied this artifact" (``"built-in"`` /
          ``"org"`` / ``"project"``), a question the activation filter does
          not answer and is not gated by it.
        * ``resolve_profile()``'s ``specializes_from`` lineage traversal
          reads through the raw repository and MAY cross into a deactivated
          parent profile -- lineage composition is a below-the-activation-
          grain operation ("what does this profile inherit from," not "is
          this profile enabled"). This is a fresh design decision for this
          accessor, not an extension of existing precedent: the raw-dict
          branch in :func:`resolve_governance_for_profile` below (module
          docstring reference: "Pattern C") is an ``isinstance(dict)``
          compatibility fallback for raw services/mocks, not a real
          lineage-traversal case -- with this wrapper, ``agent_profiles`` is
          already a ``dict`` and ``.get()`` runs, so no lineage traversal
          actually happens there (softened per post-tasks squad review).
        """
        repository: AgentProfileRepository = self._inner.agent_profiles
        return repository

    # ------------------------------------------------------------------
    # FR-002 Option A (charter-sole-door-bypass-closure-01KZ3WAA WP01
    # cycle 2): generic raw-repository accessor, the per-kind form of the
    # same "filtered dict can't do repository ops" problem
    # :attr:`agent_profile_repository` solves for ``agent_profiles``.
    # ------------------------------------------------------------------

    def raw_repository(self, kind: str) -> Any:
        """Return the raw, unfiltered repository object for artifact *kind*.

        The nine gated properties above (:attr:`paradigms` through
        :attr:`glossary_packs`) all return a filtered ``dict`` — a shape
        with neither ``.list_all()`` nor ``.get_provenance()``. Provenance-
        scan callers (e.g.
        ``specify_cli.charter_runtime.lint.checks.org_layer.OrgOverridesBuiltinChecker``)
        need those raw repository operations directly. This is the named,
        sanctioned way to reach them without either (a) reconstructing a
        second, unwrapped ``charter.offering.service.CharterOfferingService`` (the FR-002
        violation this accessor exists to close) or (b) reaching into
        ``._inner`` from outside ``charter.activation.resolver`` (the FR-010
        reach-around this module's accessors close generally).

        This is a read-only structural accessor — it does not apply charter
        activation filtering. Raw repository operations
        (``list_all()``/``get_provenance()``) answer "what artifacts exist
        and which layer supplied them," a question the activation filter
        does not gate (mirrors :attr:`agent_profile_repository`'s
        documented semantics for the identical case).

        Returns ``None`` for a *kind* outside the nine gated kinds, mirroring
        the ``getattr(service, kind, None)`` degrade-silently pattern this
        accessor replaces at ``org_layer.py``'s call sites, rather than
        raising — that module's checkers are advisory-only and expect a
        missing/unrecognized kind to be a silent skip, not a hard failure.
        """
        if kind not in _RAW_REPOSITORY_KINDS:
            return None
        inner = object.__getattribute__(self, "_inner")
        return getattr(inner, kind, None)

    # ------------------------------------------------------------------
    # FR-003 (charter-sole-door-bypass-closure-01KZ3WAA WP05): the 6-tier
    # template/command/mission resolution axis.
    #
    # ONE charter-layer door. ``charter/offering/resolver.py``'s tier functions
    # (``_resolve_asset``, ``resolve_mission``) are NOT moved, renamed, or
    # duplicated — they stay in ``charter.offering`` because charter.activation
    # imports the offering and never the reverse. What consolidates here is the *entry point*: before
    # WP05, ``charter.activation.template_resolver.CharterTemplateResolver`` reached
    # ``charter.offering.resolver`` independently of this class, giving the charter
    # layer two doors onto the same chain (C-001 violation). WP05 reduced it to a
    # thin delegate onto the methods below; it was later pruned as a Cat-7 dead
    # module (#6009). ``specify_cli/runtime/resolver.py``'s tier-6 routing calls
    # these methods directly.
    #
    # ---- Ungated by design (do NOT add activation filtering here) --------
    # Unlike the nine gated properties above, these methods apply NO charter
    # activation filter, and that is deliberate: the 6-tier chain has no
    # activation concept today (there is no ``activated_templates`` /
    # ``activated_missions`` key in ``PackContext``), so there is nothing to
    # filter by. Gating templates is FR-005's separate scope; conflating it
    # here would invent policy the charter never declared.
    #
    # ---- Why ``@staticmethod`` (T019's construction-contract resolution) --
    # Consequence of "ungated by design": these methods read ZERO instance
    # state — neither ``_inner`` nor ``_pack_context`` participates. Declaring
    # them static encodes that contract structurally, so a future edit cannot
    # quietly start consulting activation state without changing the
    # signature, and it dissolves the construction-contract mismatch T019
    # named rather than papering over it. The alternative considered and
    # rejected — making them instance methods and building the activation-
    # aware factory at ``specify_cli/runtime/resolver.py``'s tier-6 call site
    # (from the ``project_dir`` already threaded through the chain) — would
    # have coupled pure-filesystem template resolution to charter governance
    # config loading (``PackContext.from_config`` + ``resolve_org_roots`` +
    # ``infer_repo_languages``) for state these methods provably never read,
    # newly making template lookup fail-closed on a malformed
    # ``.kittify/config.yaml``. See the mirroring note at that call site.
    # ------------------------------------------------------------------

    @staticmethod
    def resolve_content_asset(
        name: str,
        project_dir: Path,
        mission: str = _DEFAULT_RESOLUTION_MISSION,
    ) -> ResolutionResult:
        """Resolve a content template through the full 6-tier chain.

        Behaviour-preserving pass-through to
        :func:`charter.offering.resolver.resolve_template` (OVERRIDE > LEGACY > ORG >
        GLOBAL_MISSION > GLOBAL > PACKAGE_DEFAULT). Ungated by design — see
        the section comment above.

        Args:
            name: Template filename with extension (e.g. ``"spec-template.md"``).
            project_dir: Project root containing ``.kittify/``.
            mission: Mission key used for tiers 3-5.

        Returns:
            The winning :class:`~charter.offering.resolver.ResolutionResult`.

        Raises:
            FileNotFoundError: If no tier provides the requested template.
        """
        return _offering_resolve_template(name, project_dir, mission)

    @staticmethod
    def resolve_command_asset(
        name: str,
        project_dir: Path,
        mission: str = _DEFAULT_RESOLUTION_MISSION,
    ) -> ResolutionResult:
        """Resolve a command template through the full 6-tier chain.

        Behaviour-preserving pass-through to
        :func:`charter.offering.resolver.resolve_command`. Ungated by design — see
        the section comment above.

        Args:
            name: Command template filename with extension (e.g. ``"plan.md"``).
            project_dir: Project root containing ``.kittify/``.
            mission: Mission key used for tiers 3-5.

        Returns:
            The winning :class:`~charter.offering.resolver.ResolutionResult`.

        Raises:
            FileNotFoundError: If no tier provides the requested command template.
        """
        return _offering_resolve_command(name, project_dir, mission)

    @staticmethod
    def resolve_mission_definition(name: str, project_dir: Path) -> ResolutionResult:
        """Resolve a ``mission.yaml`` through the mission-config tier chain.

        Behaviour-preserving pass-through to
        :func:`charter.offering.resolver.resolve_mission`. Missions are inherently
        mission-scoped, so that chain has five tiers (no GLOBAL tier).
        Ungated by design — see the section comment above.

        Args:
            name: Mission key (e.g. ``"software-dev"``).
            project_dir: Project root containing ``.kittify/``.

        Returns:
            The winning :class:`~charter.offering.resolver.ResolutionResult`.

        Raises:
            FileNotFoundError: If no tier provides the mission config.
        """
        return _offering_resolve_mission(name, project_dir)

    @staticmethod
    def resolve_package_default_asset_path(
        *,
        missions_root: Path,
        mission: str,
        subdir: str,
        name: str,
    ) -> Path | None:
        """Resolve the tier-6 (PACKAGE_DEFAULT) path for an asset, or ``None``.

        A tier-6-**only** entry point, deliberately separate from
        :meth:`resolve_content_asset` / :meth:`resolve_command_asset`:
        ``specify_cli/runtime/resolver.py`` carries its own tiers 1-5
        (explicitly out of this mission's scope as deferred debt) and needs to
        ask charter for tier 6 alone. Keeping the ``subdir`` → repository-method
        dispatch here is what lets that caller stop knowing
        :class:`MissionTemplateRepository`'s shape — the intent its existing
        "runtime never binds directly to doctrine's repository shape" comment
        already declared.

        *missions_root* is a parameter rather than instance state because the
        caller's root is ``get_package_asset_root()``, which honours the
        ``SPEC_KITTY_TEMPLATE_ROOT`` override; hard-wiring
        ``MissionTemplateRepository.default()`` here (as
        ``charter.offering.resolver``'s own tier 6 does) would silently drop that
        override. That divergence between the two tier-6 implementations is
        pre-existing, named deferred debt — this method preserves the caller's
        side of it verbatim rather than "fixing" it out of scope.

        Args:
            missions_root: Package missions root to look under.
            mission: Mission key.
            subdir: ``"command-templates"``, ``"templates"``, or any other
                subdirectory (handled by the literal-path fallback).
            name: Asset filename with extension.

        Returns:
            The package-default path, or ``None`` when the asset is absent.
        """
        repository = _mission_template_repository(str(missions_root))
        if subdir == _COMMAND_TEMPLATES_SUBDIR:
            # Command templates are keyed by stem, not filename (repository
            # contract). ``Path(name).stem`` preserves the exact normalization
            # the runtime caller applied before FR-003 moved it here.
            return repository._command_template_path(mission, Path(name).stem)
        if subdir == _CONTENT_TEMPLATES_SUBDIR:
            return repository._content_template_path(mission, name)
        fallback = Path(missions_root) / mission / subdir / name
        return fallback if fallback.is_file() else None

    @staticmethod
    def resolve_package_default_mission_config_path(
        *,
        missions_root: Path,
        mission: str,
    ) -> Path | None:
        """Resolve the tier-5 (PACKAGE_DEFAULT) ``mission.yaml`` path, or ``None``.

        The mission-config counterpart of
        :meth:`resolve_package_default_asset_path`; same rationale for taking
        *missions_root* as a parameter.

        Args:
            missions_root: Package missions root to look under.
            mission: Mission key.

        Returns:
            The package-default ``mission.yaml`` path, or ``None`` when absent.
        """
        return _mission_template_repository(str(missions_root))._mission_config_path(mission)

    # ------------------------------------------------------------------
    # Delegation: all other attributes forwarded to the inner service
    # ------------------------------------------------------------------

    def __getattr__(self, name: str) -> Any:
        """Delegate unknown attribute access to the inner offering service."""
        inner = object.__getattribute__(self, "_inner")
        return getattr(inner, name)


class GovernanceResolutionError(ValueError):
    """Raised when charter selections reference unavailable entities."""

    def __init__(self, issues: list[str]) -> None:
        self.issues = issues
        message = "Governance resolution failed:\n- " + "\n- ".join(issues)
        super().__init__(message)


@dataclass(frozen=True)
class GovernanceResolution:
    """Resolved governance activation result."""

    paradigms: list[str]
    directives: list[str]
    tools: list[str]
    template_set: str
    metadata: dict[str, str]
    tactics: list[str] = field(default_factory=list)
    styleguides: list[str] = field(default_factory=list)
    toolguides: list[str] = field(default_factory=list)
    procedures: list[str] = field(default_factory=list)
    # WP10/T058 (V-4): assets keep GovernanceResolution one kind wide as the
    # delivery bundle. Populated only from the canonical PackContext /
    # resolve_config_activated_roots path — never a second store reader.
    assets: list[str] = field(default_factory=list)
    profile_id: str | None = None
    role: str | None = None
    diagnostics: list[str] = field(default_factory=list)


def _drop_unknown(kind: str, token: str, diagnostics: list[str]) -> None:
    """Record that *token* was dropped because no layer knows it (#6407)."""
    diagnostics.append(UNKNOWN_SELECTION_DIAGNOSTIC.format(kind=kind, token=token))


def _resolve_selected_paradigms(
    selected_paradigms: list[str],
    offering_catalog: OfferingCatalog,
    identity: IdentityIndex,
    diagnostics: list[str],
) -> list[str]:
    """Map each selected paradigm to its declared id; drop (with a diagnostic) unknown ones.

    Known means: any layer of the identity index (built-in, org packs, project) or the
    loaded offering catalog. When the catalog carries no paradigms domain at all, an
    index-unknown token passes through unvalidated (nothing to validate it against).
    """
    resolved: list[str] = []
    validate = "paradigms" in offering_catalog.domains_present
    for token in selected_paradigms:
        declared = identity.selection_id(ArtifactKind.PARADIGM, token)
        if declared is None and (token in offering_catalog.paradigms or not validate):
            declared = token
        if declared is None:
            _drop_unknown("paradigm", token, diagnostics)
        elif declared not in resolved:
            resolved.append(declared)
    return resolved


def _resolve_paradigm_base(
    offering_catalog: OfferingCatalog,
    pack_ctx: PackContext,
    identity: IdentityIndex,
    diagnostics: list[str],
) -> tuple[list[str], str]:
    """Resolve the *base* paradigm set and its provenance label (FR-013),
    mirroring :func:`_resolve_directive_base`'s three-state guard for
    ``PackContext.activated_paradigms``.

    * ``activated_paradigms is None`` (key absent from config; e.g. a bare,
      unconfigured project) -> the built-in catalog default
      (``sorted(offering_catalog.paradigms)``), source ``"catalog_fallback"``,
      with a diagnostic naming the fallback and its size.
    * ``activated_paradigms == frozenset()`` (explicit opt-out) -> ``[]``,
      source ``"activation"``.
    * ``activated_paradigms == {tokens}`` -> each token mapped to its declared id
      (an activation list may hold a file stem or a declared id), sorted,
      source ``"activation"``.

    The ``is None`` check is deliberate and MUST NOT be collapsed to a
    truthiness check: ``frozenset()`` is falsy, so a truthiness collapse would
    silently re-route the explicit opt-out case back to the catalog default it
    exists to suppress.
    """
    activated_paradigms = pack_ctx.activated_paradigms
    if activated_paradigms is None:
        base = sorted(offering_catalog.paradigms)
        diagnostics.append(f"No activated paradigm set configured; using built-in catalog default ({len(base)} paradigms).")
        return base, "catalog_fallback"
    warnings: list[str] = []
    ids = {identity.activation_id(ArtifactKind.PARADIGM, token, warnings) for token in activated_paradigms}
    for warning in warnings:
        _LOGGER.warning("%s", warning)
    return sorted(ids), "activation"


def _resolve_tools_selection(
    charter_config: GovernanceCharterConfig,
    available_tools: set[str],
    diagnostics: list[str],
) -> tuple[list[str], str]:
    """Resolve tool list as the union of registry baseline and charter selection.

    The runtime tool registry is the *baseline* (tools the framework guarantees
    are present, e.g. ``git``, ``spec-kitty``). The charter's
    ``available_tools`` list is a *declaration* of additional tools the project
    has adopted (e.g. ``pytest``, ``mypy``, ``ruff``). The effective resolved
    set is therefore the **union** of the two sets, not the intersection — a
    charter that declares ``mypy`` does not need the runtime registry to
    pre-register ``mypy`` for the declaration to take effect.

    Returns ``(sorted_tools, source)`` where ``source`` is one of:
      - ``"charter+registry"`` — charter declared one or more tools; the
        resolved set unions them with the registry baseline.
      - ``"registry_only"`` — charter did not declare any tools; the resolved
        set falls back to the registry baseline alone.

    A diagnostic is emitted only when the charter is silent, mirroring the
    pre-union behaviour so operators continue to see the "fallback applied"
    cue when their charter omits the declaration.
    """
    selected_tools = charter_config.available_tools
    if selected_tools:
        unioned = sorted(set(selected_tools) | available_tools)
        added_from_charter = sorted(set(selected_tools) - available_tools)
        if added_from_charter:
            diagnostics.append("Charter declared additional tool(s) beyond the runtime registry: " + ", ".join(added_from_charter) + ".")
        return unioned, "charter+registry"

    diagnostics.append("No available_tools selection provided; using runtime tool registry fallback.")
    return sorted(available_tools), "registry_only"


def _resolve_selected_directives(
    selected: list[str],
    local_ids: set[str],
    catalog_ids: set[str],
    identity: IdentityIndex,
    diagnostics: list[str],
) -> list[str]:
    """Map each selected directive to its declared id; drop (with a diagnostic) unknown ones.

    The identity index resolves a stem or declared id in any layer. Charter-local
    ``directives:`` ids and the loaded offering catalog stay valid through the id
    normaliser, the legacy spelling bridge (``001-...`` <-> ``DIRECTIVE_001``).
    """
    resolved: list[str] = []
    for token in selected:
        declared = identity.selection_id(ArtifactKind.DIRECTIVE, token)
        if declared is None:
            legacy = normalize_directive_id(token)
            declared = legacy if legacy in local_ids or legacy in catalog_ids else None
        if declared is None:
            _drop_unknown("directive", token, diagnostics)
        elif declared not in resolved:
            resolved.append(declared)
    return resolved


def _report_charter_selection(noun: str, resolved: list[str], base: list[str], base_source: str, diagnostics: list[str]) -> None:
    """Append the "beyond the base" / "none added" diagnostic for a resolved charter selection.

    Silent when nothing resolved (every entry was unknown): the unknown-selection
    diagnostics already say so, and "All 0 ... none added" would be misleading.
    """
    if not resolved:
        return
    base_set = set(base)
    added = [item for item in resolved if item not in base_set]
    if added:
        diagnostics.append(f"Charter selected {len(added)} {noun}(s) beyond the {base_source} base: " + ", ".join(added) + ".")
    else:
        diagnostics.append(f"All {len(resolved)} charter-selected {noun}(s) already present in the {base_source} base; none added: " + ", ".join(resolved) + ".")


def _resolve_directive_base(
    charter_config: GovernanceCharterConfig,
    directives_cfg: DirectivesConfig,
    offering_catalog: OfferingCatalog,
    pack_ctx: PackContext,
    identity: IdentityIndex,
    diagnostics: list[str],
) -> tuple[list[str], str]:
    """Resolve the *base* directive set and its provenance label, before the
    additive project-local layer (see :func:`_resolve_directives_selection`).

    Base authority order: the ``activated_*``-derived value is ALWAYS computed
    first as the base, and ``charter_config.selected_directives`` is then UNIONED
    onto that base when non-empty. It never substitutes for the base (FR-012).

    Three-state guard (``pack_context.py:144``), preserved verbatim:

    * ``activated_directives is None`` (key absent from config) -> the built-in
      catalog default (``sorted(offering_catalog.directives)``, spelled as the
      catalog spells it), source ``"catalog_fallback"``, with a diagnostic naming
      the fallback and its size (C-007: membership unchanged).
    * ``activated_directives == frozenset()`` (explicit opt-out) -> ``[]``,
      source ``"activation"``.
    * ``activated_directives == {tokens}`` -> each token resolved through the
      identity index to its DECLARED id (``qa-003-no-fake-green`` -> ``QA_003``;
      a legacy token that no layer knows falls back to the normaliser with a
      warning), sorted, source ``"activation"``.

    The ``is None`` check MUST NOT be collapsed to a truthiness check:
    ``frozenset()`` is falsy and would re-route the explicit opt-out case back
    to the catalog default it exists to suppress.

    ``charter_config.selected_directives`` resolves through the identity index
    (every layer). An entry no layer knows is dropped and reported through
    ``diagnostics`` (:data:`UNKNOWN_SELECTION_DIAGNOSTIC`) instead of raising: one
    mistyped id must not erase the whole governance resolution (#6407).
    """
    local_ids = {normalize_directive_id(d.id) for d in directives_cfg.directives}
    catalog_ids = {normalize_directive_id(d) for d in offering_catalog.directives}

    activated_directives = pack_ctx.activated_directives
    if activated_directives is None:
        base = sorted(catalog_ids)
        diagnostics.append(f"No activated directive set configured; using built-in catalog default ({len(base)} directives).")
        base_source = "catalog_fallback"
    else:
        warnings: list[str] = []
        base = sorted({identity.activation_id(ArtifactKind.DIRECTIVE, token, warnings) for token in activated_directives})
        for warning in warnings:
            _LOGGER.warning("%s", warning)
        base_source = "activation"

    if not charter_config.selected_directives:
        return base, base_source

    selected_directives = _resolve_selected_directives(list(charter_config.selected_directives), local_ids, catalog_ids, identity, diagnostics)

    _report_charter_selection("directive", selected_directives, base, base_source, diagnostics)
    if not selected_directives:
        return base, base_source
    return list(dict.fromkeys([*base, *selected_directives])), f"{base_source}+charter"


def _resolve_directives_selection(
    charter_config: GovernanceCharterConfig,
    directives_cfg: DirectivesConfig,
    offering_catalog: OfferingCatalog,
    pack_ctx: PackContext,
    identity: IdentityIndex,
    diagnostics: list[str],
) -> tuple[list[str], str]:
    """Resolve the effective directive list as the base set **plus** an additive
    project-local layer declared in ``charter.yaml``'s ``directives:`` section.

    The base set + its provenance label come from
    :func:`_resolve_directive_base` (explicit charter selection → config
    activation → built-in catalog default). Project-local directives declared in
    the ``charter.yaml`` ``directives:`` section are then **unioned** onto that
    base — they never replace it (the historical branch-2 replace dropped the
    entire resolved set; see #3728). Mirrors the union-plus-diagnostic shape of
    :func:`_resolve_tools_selection`.

    * No local declarations → ``(base, base_source)`` unchanged.
    * One or more local declarations → ``(dedup(base ++ local), f"{base_source}
      +project_local")`` with a diagnostic naming how many/which local
      directives merged and onto which base. Base order is preserved and no base
      id is ever dropped (INV-1/INV-2/INV-3/INV-5).
    """
    base, base_source = _resolve_directive_base(charter_config, directives_cfg, offering_catalog, pack_ctx, identity, diagnostics)

    local_ids = [d.id for d in directives_cfg.directives]
    if not local_ids:
        return base, base_source

    resolved = list(dict.fromkeys([*base, *local_ids]))
    base_set = set(base)
    added = [d for d in local_ids if d not in base_set]
    if added:
        diagnostics.append(f"Merged {len(added)} project-local directive(s) onto the {base_source} set: " + ", ".join(added) + ".")
    else:
        diagnostics.append(f"All {len(local_ids)} project-local directive(s) already present in the {base_source} set; none added: " + ", ".join(local_ids) + ".")
    return resolved, f"{base_source}+project_local"


def _resolve_template_set_selection(
    charter_config: GovernanceCharterConfig,
    offering_catalog: OfferingCatalog,
    fallback_template_set: str,
    diagnostics: list[str],
) -> tuple[str, str]:
    """Resolve template set from charter selection or fallback."""
    if charter_config.template_set:
        if "template_sets" in offering_catalog.domains_present and charter_config.template_set not in offering_catalog.template_sets:
            raise GovernanceResolutionError(
                [
                    f"Charter selected unavailable template_set: '{charter_config.template_set}'",
                    "Available template sets: " + (", ".join(sorted(offering_catalog.template_sets)) or "(none)"),
                    _TEMPLATE_SET_REMEDIATION,
                ]
            )
        return charter_config.template_set, "charter"

    diagnostics.append(f"Template set not selected in charter; fallback '{fallback_template_set}' applied.")
    return fallback_template_set, "fallback"


def resolve_project_governance(
    repo_root: Path,
    *,
    tool_registry: set[str] | None = None,
    fallback_template_set: str = DEFAULT_TEMPLATE_SET,
    identity: IdentityIndex | None = None,
) -> GovernanceResolution:
    """Resolve active governance from project + org charter selection data.

    This resolver consumes the charter-mediated **project + org** doctrine
    selections from the hand-authored ``.kittify/charter/charter.yaml``
    ``governance:`` and ``directives:`` sections (the retired standalone
    ``governance.yaml`` / ``directives.yaml`` files are no longer read).  It is
    intentionally *narrow* to that surface: it does NOT read ``meta.json`` or
    per-mission overrides.

    The companion resolver
    :func:`charter.activation.mission_type_profiles.resolve_mission_type_context`
    handles **mission-type** scoped governance (``meta.json mission_type``
    → built-in governance profile).  The two resolvers compose at the
    prompt-builder layer: the mission-type resolver runs first to fill
    documentation / research / plan defaults, then this resolver fills
    project + org selections on top.  Keeping them as two named functions
    (rather than one umbrella) preserves the FR-003 hard-fail contract on
    the mission-type side and the rich :class:`GovernanceResolution`
    dataclass on the project + org side.

    """
    governance = load_governance_config(repo_root)
    directives_cfg = load_directives_config(repo_root)
    offering_catalog = load_offering_catalog()
    charter_config = governance.charter
    diagnostics: list[str] = []

    # FR-013: activated_paradigms is the base; charter_config.selected_paradigms
    # (validated exactly as before, unchanged — boundary 4, already "fails
    # loud") unions onto it, never substitutes for it. Previously this was an
    # unconditional passthrough with no activated_* read at all.
    from charter.activation.pack_context import PackContext  # noqa: PLC0415 — lazy; avoids circular import

    pack_ctx = PackContext.from_config(repo_root)
    if identity is None:
        identity = IdentityIndex.from_pack_context(pack_ctx, repo_root=repo_root)

    selected_paradigms_raw = _resolve_selected_paradigms(list(charter_config.selected_paradigms), offering_catalog, identity, diagnostics)
    paradigm_base, paradigm_base_source = _resolve_paradigm_base(offering_catalog, pack_ctx, identity, diagnostics)
    _report_charter_selection("paradigm", selected_paradigms_raw, paradigm_base, paradigm_base_source, diagnostics)
    selected_paradigms = list(dict.fromkeys([*paradigm_base, *selected_paradigms_raw]))

    available_tools = tool_registry or set(DEFAULT_TOOL_REGISTRY)
    resolved_tools, tools_source = _resolve_tools_selection(charter_config, available_tools, diagnostics)
    resolved_directives, directives_source = _resolve_directives_selection(charter_config, directives_cfg, offering_catalog, pack_ctx, identity, diagnostics)
    template_set, template_set_source = _resolve_template_set_selection(charter_config, offering_catalog, fallback_template_set, diagnostics)

    return GovernanceResolution(
        paradigms=selected_paradigms,
        directives=resolved_directives,
        tactics=[],
        styleguides=[],
        toolguides=[],
        procedures=[],
        tools=resolved_tools,
        template_set=template_set,
        metadata={
            "tools_source": tools_source,
            "directives_source": directives_source,
            "template_set_source": template_set_source,
        },
        diagnostics=diagnostics,
    )


def resolve_governance_for_profile(
    profile_id: str,
    role: str | None,
    charter_service: ActiveCharterService,
    interview: CharterInterview,
    *,
    graph: DRGGraph | None = None,
    repo_root: Path | None = None,
) -> GovernanceResolution:
    """Resolve governance selections for a specific agent profile."""
    normalized_profile_id = profile_id.strip()
    if not normalized_profile_id:
        raise ValueError("Profile ID is required for profile-aware governance resolution.")

    # Pattern C: agent_profiles may be a filtered dict (ActiveCharterService wrapper)
    # or a repository (raw charter.offering.service.CharterOfferingService / MagicMock in tests).
    agent_profiles_attr = charter_service.agent_profiles
    if isinstance(agent_profiles_attr, dict):
        profile = agent_profiles_attr.get(normalized_profile_id)
        if profile is None:
            raise ValueError(f"Agent profile '{normalized_profile_id}' not found.")
    else:
        try:
            profile = agent_profiles_attr.resolve_profile(normalized_profile_id)
        except KeyError as exc:
            raise ValueError(f"Agent profile '{normalized_profile_id}' not found.") from exc

    profile_directives = [ref.code.strip() for ref in profile.directive_references if ref.code.strip()]
    merged_directives = _merge_unique(profile_directives, interview.selected_directives)
    resolution_graph = resolve_references_transitively(
        merged_directives,
        charter_service,
        graph=graph,
        repo_root=repo_root,
    )
    diagnostics = [f"Unresolved reference: {artifact_type}/{artifact_id}" for artifact_type, artifact_id in resolution_graph.unresolved]

    return GovernanceResolution(
        paradigms=list(interview.selected_paradigms),
        directives=merged_directives,
        tactics=list(resolution_graph.tactics),
        styleguides=list(resolution_graph.styleguides),
        toolguides=list(resolution_graph.toolguides),
        procedures=list(resolution_graph.procedures),
        tools=list(interview.available_tools),
        template_set=DEFAULT_TEMPLATE_SET,
        metadata={
            "directives_source": "profile+interview",
            "profile_directives_count": str(len(profile_directives)),
            "interview_directives_count": str(len(interview.selected_directives)),
        },
        profile_id=profile.profile_id,
        role=role.strip() if role and role.strip() else None,
        diagnostics=diagnostics,
    )


def collect_governance_diagnostics(
    repo_root: Path,
    *,
    tool_registry: set[str] | None = None,
    fallback_template_set: str = DEFAULT_TEMPLATE_SET,
) -> list[str]:
    """Collect diagnostics for planning/runtime checks."""
    try:
        resolution = resolve_project_governance(
            repo_root,
            tool_registry=tool_registry,
            fallback_template_set=fallback_template_set,
        )
    except GovernanceResolutionError as exc:
        return exc.issues
    return resolution.diagnostics


def _merge_unique(primary: list[str], secondary: list[str]) -> list[str]:
    merged: list[str] = []
    for value in [*primary, *secondary]:
        item = str(value).strip()
        if item and item not in merged:
            merged.append(item)
    return merged
