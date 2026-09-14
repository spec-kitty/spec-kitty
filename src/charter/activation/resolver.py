"""Charter-centric governance resolver.

Resolves active governance from charter selections and validates
selected references against available profile/tool catalogs.

Exports ``DoctrineService`` — an activation-aware wrapper around
:class:`charter.offering.service.DoctrineService`.  The wrapper applies per-kind
activation filters from :class:`~charter.activation.pack_context.PackContext` to nine
gated properties: ``paradigms``, ``procedures``, ``agent_profiles``
(pre-existing) plus ``directives``, ``tactics``, ``styleguides``,
``toolguides``, ``mission_step_contracts``, and ``glossary_packs`` (FR-005,
charter-sole-door-bypass-closure-01KZ3WAA WP01).  All other properties
delegate to the inner doctrine service transparently via ``__getattr__``.

It also exposes :attr:`DoctrineService.agent_profile_repository` — a second,
explicitly-named accessor (FR-001) returning the raw, lineage/mutation-capable
:class:`~charter.offering.agent_profiles.repository.AgentProfileRepository` for
callers that need ``register_overlay()`` or ``get_provenance()``, which the
filtered ``agent_profiles`` dict cannot support; and
:meth:`DoctrineService.raw_repository` (FR-002 Option A) — the generic,
per-kind form of that same "filtered dict can't do repository ops" escape
hatch, for provenance-scan callers that need raw ``list_all()``/
``get_provenance()`` access across any of the nine gated kinds.

Finally (FR-003, charter-sole-door-bypass-closure-01KZ3WAA WP05) this module
is the **sole charter-layer door** onto ``doctrine/resolver.py``'s 6-tier
asset resolution chain. The tier functions themselves stay in
``doctrine/resolver.py`` (charter must import charter.offering, never the reverse);
what lives here is the entry point — see the "6-tier resolution axis"
section of :class:`DoctrineService`. Before WP05,
``charter.activation.template_resolver.CharterTemplateResolver`` was a *second*
charter-layer object reaching ``charter.offering.resolver`` independently of this
one; it is now a thin delegate onto these methods.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from charter.activation.catalog import DoctrineCatalog, load_doctrine_catalog, resolve_doctrine_root
from charter.activation.kind_vocabulary import ArtifactKind, UnknownArtifactIdError, resolve_artifact_urn
from charter.activation.reference_resolver import resolve_references_transitively
from charter.activation.schemas import DirectivesConfig, DoctrineSelectionConfig
from charter.activation.sync import (
    load_directives_config,
    load_governance_config,
)
from charter.offering.drg.migration.id_normalizer import normalize_directive_id
from charter.offering.missions.repository import MissionTemplateRepository

# FR-003: the ONLY import of ``charter.offering.resolver``'s tier functions in the
# charter layer. Aliased with a ``_doctrine_`` prefix so a reader of a call
# site inside this module can never mistake the doctrine tier function for a
# charter-layer helper of the same bare name.
from charter.offering.resolver import (
    ResolutionResult,
    resolve_command as _doctrine_resolve_command,
    resolve_mission as _doctrine_resolve_mission,
    resolve_template as _doctrine_resolve_template,
)

__all__ = [
    "DEFAULT_TOOL_REGISTRY",
    "DoctrineService",
    "GovernanceResolution",
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
    from charter.offering.paradigms.models import Paradigm
    from charter.offering.procedures.models import Procedure
    from charter.offering.styleguides.models import Styleguide
    from charter.offering.tactics.models import Tactic
    from charter.offering.toolguides.models import Toolguide
    import charter.offering.service as _doctrine_service_module
    from charter.activation.interview import CharterInterview
    from charter.activation.pack_context import PackContext

_LOGGER = logging.getLogger(__name__)

DEFAULT_TEMPLATE_SET = "software-dev-default"
DEFAULT_TOOL_REGISTRY: frozenset[str] = frozenset({"spec-kitty", "git"})

#: The nine gated-property kinds :meth:`DoctrineService.raw_repository`
#: recognizes -- exactly the kinds with a gated ``dict`` property above.
_RAW_REPOSITORY_KINDS: frozenset[str] = frozenset(
    {
        "paradigms",
        "procedures",
        "agent_profiles",
        "directives",
        "tactics",
        "styleguides",
        "toolguides",
        "mission_step_contracts",
        "glossary_packs",
    }
)

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


def _resolve_unmatched_directive_token(token: str, all_directives: dict[str, Directive]) -> str:
    """Resolve an ``activated_directives`` token that failed URN resolution.

    A token already present in *all_directives* names a known catalog id
    verbatim (a legacy exact-id alias) and is returned as-is -- no signal
    needed, this is a resolvable identity. Anything else is the
    **fully-unresolvable** path: the token is neither URN-resolvable nor a
    known catalog id, so it is best-effort normalized (#4240) and a WARNING
    names both the raw token and the normalized form, since this can
    silently co-activate an unrelated directive (or activate nothing) with
    no other signal to the operator.
    """
    if token in all_directives:
        return token
    normalized: str = normalize_directive_id(token)
    _LOGGER.warning(
        "unresolved directive activation token %r; best-effort normalized to %r",
        token,
        normalized,
    )
    return normalized


# ---------------------------------------------------------------------------
# Activation-aware DoctrineService wrapper (Pattern B + C wiring)
# ---------------------------------------------------------------------------


class DoctrineService:
    """Activation-aware wrapper around :class:`charter.offering.service.DoctrineService`.

    Applies per-kind activation filters from
    :class:`~charter.activation.pack_context.PackContext` when accessing the nine gated
    properties: ``paradigms``, ``procedures``, ``agent_profiles``,
    ``directives``, ``tactics``, ``styleguides``, ``toolguides``,
    ``mission_step_contracts``, and ``glossary_packs``.  All other attributes
    delegate transparently to the underlying doctrine service.

    Layer rule
    ----------
    This class lives in ``charter.*`` so it can import ``PackContext``
    without violating the ``doctrine ← charter`` dependency direction.
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
        _inner: _doctrine_service_module.DoctrineService,
        pack_context: PackContext | None = None,
    ) -> None:
        # Use object.__setattr__ to bypass any potential descriptor magic.
        object.__setattr__(self, "_inner", _inner)
        object.__setattr__(self, "_pack_context", pack_context)
        self._resolved_directive_activation_ids: frozenset[str] | None = None

    # ------------------------------------------------------------------
    # Pattern B: flat catalog activation filter (paradigms, procedures)
    # ------------------------------------------------------------------

    @property
    def paradigms(self) -> dict[str, Paradigm]:
        """Return paradigms dict, filtered by ``activated_paradigms`` when set."""
        all_paradigms: dict[str, Paradigm] = {item.id: item for item in self._inner.paradigms.list_all()}
        pack_ctx: PackContext | None = object.__getattribute__(self, "_pack_context")
        if pack_ctx is not None and pack_ctx.activated_paradigms is not None:
            return {k: v for k, v in all_paradigms.items() if k in pack_ctx.activated_paradigms}
        return all_paradigms

    @property
    def procedures(self) -> dict[str, Procedure]:
        """Return procedures dict, filtered by ``activated_procedures`` when set."""
        all_procedures: dict[str, Procedure] = {item.id: item for item in self._inner.procedures.list_all()}
        pack_ctx: PackContext | None = object.__getattribute__(self, "_pack_context")
        if pack_ctx is not None and pack_ctx.activated_procedures is not None:
            return {k: v for k, v in all_procedures.items() if k in pack_ctx.activated_procedures}
        return all_procedures

    # ------------------------------------------------------------------
    # Pattern C: direct repository activation filter (agent_profiles)
    # ------------------------------------------------------------------

    @property
    def agent_profiles(self) -> dict[str, AgentProfile]:
        """Return agent profiles dict, filtered by ``activated_agent_profiles`` when set."""
        all_profiles: dict[str, AgentProfile] = {p.profile_id: p for p in self._inner.agent_profiles.list_all()}
        pack_ctx: PackContext | None = object.__getattribute__(self, "_pack_context")
        if pack_ctx is not None and pack_ctx.activated_agent_profiles is not None:
            return {k: v for k, v in all_profiles.items() if k in pack_ctx.activated_agent_profiles}
        return all_profiles

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
        pack_ctx: PackContext | None = object.__getattribute__(self, "_pack_context")
        if pack_ctx is None or pack_ctx.activated_directives is None:
            return all_directives
        if not pack_ctx.activated_directives:
            return {}

        # PackContext and the inner repositories are snapshots. Resolve once
        # for this service; a newly built service observes changed files/config.
        if self._resolved_directive_activation_ids is None:
            doctrine_root = resolve_doctrine_root()
            activated: set[str] = set()
            for token in pack_ctx.activated_directives:
                try:
                    urn = resolve_artifact_urn(
                        ArtifactKind.DIRECTIVE,
                        token,
                        doctrine_root=doctrine_root,
                        org_roots=list(pack_ctx.org_roots),
                        layer_roots={"project": pack_ctx.repo_root / ".kittify"},
                    )
                    activated.add(urn.split(":", 1)[1])
                except UnknownArtifactIdError:
                    activated.add(_resolve_unmatched_directive_token(token, all_directives))
            self._resolved_directive_activation_ids = frozenset(activated)
        activated_ids = self._resolved_directive_activation_ids
        return {key: item for key, item in all_directives.items() if key in activated_ids}

    @property
    def tactics(self) -> dict[str, Tactic]:
        """Return tactics dict, filtered by ``activated_tactics`` when set."""
        all_tactics: dict[str, Tactic] = {item.id: item for item in self._inner.tactics.list_all()}
        pack_ctx: PackContext | None = object.__getattribute__(self, "_pack_context")
        if pack_ctx is not None and pack_ctx.activated_tactics is not None:
            return {k: v for k, v in all_tactics.items() if k in pack_ctx.activated_tactics}
        return all_tactics

    @property
    def styleguides(self) -> dict[str, Styleguide]:
        """Return styleguides dict, filtered by ``activated_styleguides`` when set."""
        all_styleguides: dict[str, Styleguide] = {item.id: item for item in self._inner.styleguides.list_all()}
        pack_ctx: PackContext | None = object.__getattribute__(self, "_pack_context")
        if pack_ctx is not None and pack_ctx.activated_styleguides is not None:
            return {k: v for k, v in all_styleguides.items() if k in pack_ctx.activated_styleguides}
        return all_styleguides

    @property
    def toolguides(self) -> dict[str, Toolguide]:
        """Return toolguides dict, filtered by ``activated_toolguides`` when set."""
        all_toolguides: dict[str, Toolguide] = {item.id: item for item in self._inner.toolguides.list_all()}
        pack_ctx: PackContext | None = object.__getattribute__(self, "_pack_context")
        if pack_ctx is not None and pack_ctx.activated_toolguides is not None:
            return {k: v for k, v in all_toolguides.items() if k in pack_ctx.activated_toolguides}
        return all_toolguides

    @property
    def mission_step_contracts(self) -> dict[str, MissionStepContract]:
        """Return mission step contracts dict, filtered by ``activated_mission_step_contracts`` when set."""
        all_contracts: dict[str, MissionStepContract] = {item.id: item for item in self._inner.mission_step_contracts.list_all()}
        pack_ctx: PackContext | None = object.__getattribute__(self, "_pack_context")
        if pack_ctx is not None and pack_ctx.activated_mission_step_contracts is not None:
            return {k: v for k, v in all_contracts.items() if k in pack_ctx.activated_mission_step_contracts}
        return all_contracts

    @property
    def glossary_packs(self) -> dict[str, GlossaryPack]:
        """Return glossary packs dict, filtered by ``activated_glossary_packs`` when set."""
        all_glossary_packs: dict[str, GlossaryPack] = {item.id: item for item in self._inner.glossary_packs.list_all()}
        pack_ctx: PackContext | None = object.__getattribute__(self, "_pack_context")
        if pack_ctx is not None and pack_ctx.activated_glossary_packs is not None:
            return {k: v for k, v in all_glossary_packs.items() if k in pack_ctx.activated_glossary_packs}
        return all_glossary_packs

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
          it answers "which layer supplied this artifact" (``"builtin"`` /
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
        second, unwrapped ``charter.offering.service.DoctrineService`` (the FR-002
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
    # ONE charter-layer door. ``doctrine/resolver.py``'s tier functions
    # (``_resolve_asset``, ``resolve_mission``) are NOT moved, renamed, or
    # duplicated — they stay in doctrine because charter imports doctrine and
    # never the reverse. What consolidates here is the *entry point*: before
    # WP05, ``charter.activation.template_resolver.CharterTemplateResolver`` reached
    # ``charter.offering.resolver`` independently of this class, giving the charter
    # layer two doors onto the same chain (C-001 violation). It is now a thin
    # delegate onto the methods below, and
    # ``specify_cli/runtime/resolver.py``'s tier-6 routing calls them
    # directly.
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
        return _doctrine_resolve_template(name, project_dir, mission)

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
        return _doctrine_resolve_command(name, project_dir, mission)

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
        return _doctrine_resolve_mission(name, project_dir)

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
        """Delegate unknown attribute access to the inner doctrine service."""
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


def _validate_paradigm_selection(
    selected_paradigms: list[str],
    doctrine_catalog: DoctrineCatalog,
) -> None:
    """Raise GovernanceResolutionError if any selected paradigm is not in the built-in catalog."""
    if not selected_paradigms or "paradigms" not in doctrine_catalog.domains_present:
        return
    missing = sorted(p for p in selected_paradigms if p not in doctrine_catalog.paradigms)
    if missing:
        raise GovernanceResolutionError(
            [
                "Charter selected unavailable paradigm(s): " + ", ".join(missing),
                "Available built-in paradigms: " + (", ".join(sorted(doctrine_catalog.paradigms)) or "(none)"),
                "Update charter selected_paradigms to values present in packs/built-in/paradigms/.",
            ]
        )


def _resolve_paradigm_base(
    doctrine_catalog: DoctrineCatalog,
    repo_root: Path,
    diagnostics: list[str],
) -> tuple[list[str], str]:
    """Resolve the *base* paradigm set and its provenance label (FR-013),
    mirroring :func:`_resolve_directive_base`'s three-state guard for
    ``PackContext.activated_paradigms``. There was NO ``activated_*`` read
    for paradigms anywhere in this module before this fix.

    Unlike directives, paradigm ids have no stem-vs-canonical distinction in
    this repo's authoring convention — every built-in paradigm file's ``id:``
    field IS the filename-stem slug — so no normalizer call is needed or
    added here (Union/Exclusion Boundary Audit boundary 3; out of scope,
    vacuously satisfied).

    * ``activated_paradigms is None`` (key absent from config; e.g. a bare,
      unconfigured project) → the built-in catalog default
      (``sorted(doctrine_catalog.paradigms)``), source ``"catalog_fallback"``,
      with a diagnostic naming the fallback and its size.
    * ``activated_paradigms == frozenset()`` (explicit opt-out) → ``[]``,
      source ``"activation"``.
    * ``activated_paradigms == {ids}`` → ``sorted(ids)``, source
      ``"activation"``.

    The ``is None`` check is deliberate and MUST NOT be collapsed to a
    truthiness check, mirroring :func:`_resolve_directive_base`'s identical
    guard for directives — ``frozenset()`` is falsy, so a truthiness collapse
    would silently re-route the explicit opt-out case back to the catalog
    default it exists to suppress.
    """
    from charter.activation.pack_context import PackContext  # noqa: PLC0415 — lazy; avoids circular import

    activated_paradigms = PackContext.from_config(repo_root).activated_paradigms
    if activated_paradigms is None:
        base = sorted(doctrine_catalog.paradigms)
        diagnostics.append(f"No activated paradigm set configured; using built-in catalog default ({len(base)} paradigms).")
        return base, "catalog_fallback"
    return sorted(activated_paradigms), "activation"


def _resolve_tools_selection(
    doctrine: DoctrineSelectionConfig,
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
    selected_tools = doctrine.available_tools
    if selected_tools:
        unioned = sorted(set(selected_tools) | available_tools)
        added_from_charter = sorted(set(selected_tools) - available_tools)
        if added_from_charter:
            diagnostics.append("Charter declared additional tool(s) beyond the runtime registry: " + ", ".join(added_from_charter) + ".")
        return unioned, "charter+registry"

    diagnostics.append("No available_tools selection provided; using runtime tool registry fallback.")
    return sorted(available_tools), "registry_only"


def _resolve_directive_base(
    doctrine: DoctrineSelectionConfig,
    directives_cfg: DirectivesConfig,
    doctrine_catalog: DoctrineCatalog,
    repo_root: Path,
    diagnostics: list[str],
) -> tuple[list[str], str]:
    """Resolve the *base* directive set and its provenance label, before the
    additive project-local layer (see :func:`_resolve_directives_selection`).

    Base authority order (INVERTED from the pre-FR-012 priority): the
    ``activated_*``-derived value is ALWAYS computed first as the base, and
    ``doctrine.selected_directives`` — the charter-authored selection — is
    then UNIONED onto that base when non-empty. It never substitutes for the
    base (mirrors :func:`_resolve_directives_selection`'s existing
    base-plus-project-local union shape). Previously, a non-empty
    ``doctrine.selected_directives`` short-circuited and returned verbatim,
    silently overriding ``activated_directives`` any time a project had ever
    made an explicit charter selection (FR-012).

    Three-state guard (``pack_context.py:144``), preserved verbatim:

    * ``activated_directives is None`` (key absent from config; e.g. a bare,
      unconfigured project) → the built-in catalog default
      (``sorted(doctrine_catalog.directives)``), source ``"catalog_fallback"``,
      with a diagnostic naming the fallback and its size.
    * ``activated_directives == frozenset()`` (explicit opt-out) → ``[]``,
      source ``"activation"``.
    * ``activated_directives == {ids}`` → each id normalized via
      :func:`~charter.activation.profile_resolution._normalize_directive_id`
      (``PackContext.activated_directives`` legitimately stores STEM-form ids
      — proven live by
      ``test_answers_inert_and_org_union.py::TestOrgRequiredIdFormNormalizedBeforePromotion``
      — and a stem-form id must never leak into the resolved base
      un-normalized; Union/Exclusion Boundary Audit boundary 1), then sorted,
      source ``"activation"``.

    The ``is None`` check is deliberate and MUST NOT be collapsed to a
    truthiness check (``activated_directives or frozenset()`` /
    ``if activated_directives:``): ``frozenset()`` is falsy, so a truthiness
    collapse would silently re-route the explicit opt-out case back to the
    catalog default it exists to suppress.

    ``doctrine.selected_directives`` is validated against the local + built-in
    catalog BEFORE the union runs — an entry not in ``valid_ids`` raises
    ``GovernanceResolutionError`` rather than silently dropping (boundary 2,
    unchanged, already "fails loud").
    """
    from charter.activation.pack_context import PackContext  # noqa: PLC0415 — lazy; avoids circular import
    from charter.activation.profile_resolution import _normalize_directive_id  # noqa: PLC0415 — lazy; avoids circular import

    local_ids = {d.id for d in directives_cfg.directives}
    valid_ids = set(local_ids)
    if doctrine_catalog.directives:
        valid_ids.update(doctrine_catalog.directives)

    activated_directives = PackContext.from_config(repo_root).activated_directives
    if activated_directives is None:
        base = sorted({_normalize_directive_id(d) for d in doctrine_catalog.directives})
        diagnostics.append(f"No activated directive set configured; using built-in catalog default ({len(base)} directives).")
        base_source = "catalog_fallback"
    else:
        base = sorted({_normalize_directive_id(d) for d in activated_directives})
        base_source = "activation"

    if not doctrine.selected_directives:
        return base, base_source

    missing = sorted(d for d in doctrine.selected_directives if d not in valid_ids)
    if missing:
        raise GovernanceResolutionError(
            [
                "Charter selected unavailable directive(s): " + ", ".join(missing),
                "Declare these IDs in the charter.yaml 'directives:' section or add them to packs/built-in/directives/.",
            ]
        )

    base_set = set(base)
    added = [d for d in doctrine.selected_directives if d not in base_set]
    if added:
        diagnostics.append(f"Charter selected {len(added)} directive(s) beyond the {base_source} base: " + ", ".join(added) + ".")
    else:
        diagnostics.append(
            f"All {len(doctrine.selected_directives)} charter-selected directive(s) already present in "
            f"the {base_source} base; none added: " + ", ".join(doctrine.selected_directives) + "."
        )
    unioned = list(dict.fromkeys([*base, *doctrine.selected_directives]))
    return unioned, f"{base_source}+charter"


def _resolve_directives_selection(
    doctrine: DoctrineSelectionConfig,
    directives_cfg: DirectivesConfig,
    doctrine_catalog: DoctrineCatalog,
    repo_root: Path,
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
    base, base_source = _resolve_directive_base(doctrine, directives_cfg, doctrine_catalog, repo_root, diagnostics)

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
    doctrine: DoctrineSelectionConfig,
    doctrine_catalog: DoctrineCatalog,
    fallback_template_set: str,
    diagnostics: list[str],
) -> tuple[str, str]:
    """Resolve template set from charter selection or fallback."""
    if doctrine.template_set:
        if "template_sets" in doctrine_catalog.domains_present and doctrine.template_set not in doctrine_catalog.template_sets:
            raise GovernanceResolutionError(
                [
                    f"Charter selected unavailable template_set: '{doctrine.template_set}'",
                    "Available template sets: " + (", ".join(sorted(doctrine_catalog.template_sets)) or "(none)"),
                    "Update charter template_set to a value available in doctrine missions.",
                ]
            )
        return doctrine.template_set, "charter"

    diagnostics.append(f"Template set not selected in charter; fallback '{fallback_template_set}' applied.")
    return fallback_template_set, "fallback"


def resolve_project_governance(
    repo_root: Path,
    *,
    tool_registry: set[str] | None = None,
    fallback_template_set: str = DEFAULT_TEMPLATE_SET,
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
    doctrine_catalog = load_doctrine_catalog()
    doctrine = governance.charter
    diagnostics: list[str] = []

    # FR-013: activated_paradigms is the base; doctrine.selected_paradigms
    # (validated exactly as before, unchanged — boundary 4, already "fails
    # loud") unions onto it, never substitutes for it. Previously this was an
    # unconditional passthrough with no activated_* read at all.
    selected_paradigms_raw = list(doctrine.selected_paradigms)
    _validate_paradigm_selection(selected_paradigms_raw, doctrine_catalog)
    paradigm_base, paradigm_base_source = _resolve_paradigm_base(doctrine_catalog, repo_root, diagnostics)
    if selected_paradigms_raw:
        paradigm_base_set = set(paradigm_base)
        added_paradigms = [p for p in selected_paradigms_raw if p not in paradigm_base_set]
        if added_paradigms:
            diagnostics.append(f"Charter selected {len(added_paradigms)} paradigm(s) beyond the {paradigm_base_source} base: " + ", ".join(added_paradigms) + ".")
        else:
            diagnostics.append(
                f"All {len(selected_paradigms_raw)} charter-selected paradigm(s) already present in the "
                f"{paradigm_base_source} base; none added: " + ", ".join(selected_paradigms_raw) + "."
            )
        selected_paradigms = list(dict.fromkeys([*paradigm_base, *selected_paradigms_raw]))
    else:
        selected_paradigms = paradigm_base

    available_tools = tool_registry or set(DEFAULT_TOOL_REGISTRY)
    resolved_tools, tools_source = _resolve_tools_selection(doctrine, available_tools, diagnostics)
    resolved_directives, directives_source = _resolve_directives_selection(doctrine, directives_cfg, doctrine_catalog, repo_root, diagnostics)
    template_set, template_set_source = _resolve_template_set_selection(doctrine, doctrine_catalog, fallback_template_set, diagnostics)

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
    doctrine_service: DoctrineService,
    interview: CharterInterview,
    *,
    graph: DRGGraph | None = None,
    repo_root: Path | None = None,
) -> GovernanceResolution:
    """Resolve governance selections for a specific agent profile."""
    normalized_profile_id = profile_id.strip()
    if not normalized_profile_id:
        raise ValueError("Profile ID is required for profile-aware governance resolution.")

    # Pattern C: agent_profiles may be a filtered dict (DoctrineService wrapper)
    # or a repository (raw charter.offering.service.DoctrineService / MagicMock in tests).
    agent_profiles_attr = doctrine_service.agent_profiles
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
        doctrine_service,
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
