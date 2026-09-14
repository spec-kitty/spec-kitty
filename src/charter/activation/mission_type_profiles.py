"""Mission-type-scoped governance resolution — the single charter-mediated seam.

Mission-type profiles are built-in doctrine-side YAML files at
``src/charter/offering/missions/<mission_type>/governance-profile.yaml``.  Each
profile declares the default selections and activations for missions of
that type.

The **one** entry point is :func:`resolve_mission_type_context`.  It reads the
mission type (explicit argument → ``feature_dir/meta.json``), then resolves an
ordered, structured :class:`ResolvedMissionType` bundle both consumers converge
on: ``runtime.next.prompt_builder`` (Surface B) and the action-doctrine path.
It subsumes the three historical functions (``resolve_action_sequence``,
``resolve_mission_type_governance``, ``load_profile``); no second resolution
path remains (C-002).

The four canonical mission types are:

* ``software-dev``
* ``documentation``
* ``research``
* ``plan``

Profiles for other mission_type values are not part of the built-in profile set.
The resolver hard-fails (``UnknownMissionTypeError``) when the mission type
matches no built-in profile AND the project charter has not declared its own
``selected_<kind>`` overrides.  Silent fallback to ``software-dev-default`` is
explicitly forbidden by FR-001 / FR-003.  A *typeless* mission (no type at all)
degrades to a **neutral** bundle — never software-dev (FR-003a).

Two distinct hard-fail policies are preserved as explicit branches:

* **governance** tolerates an unknown type when a project override exists;
* **action-sequence** validates strictly against the activation set.

See:

* ``kitty-specs/mission-type-doctrine-authority-01KXH6GE/contracts/resolution-and-enforcement.md``
  (C1) for the seam contract.
* ``kitty-specs/mission-type-doctrine-authority-01KXH6GE/data-model.md`` for the
  ``ResolvedMissionType`` / ``ResolvedGovernance`` shapes.

Layer rule
----------
``src/charter/`` MUST NOT import from ``specify_cli`` (C-001, hard ratchet
pinned by ``tests/architectural/test_layer_rules.py``).  This module stays
self-contained accordingly; imports from ``doctrine`` are allowed (charter ->
doctrine is the canonical dependency direction).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from charter.activation.action_grain import aggregate_action_grain
from charter.activation.activations import ActivationEntry
from charter.bundle import CHARTER_YAML
from charter.activation.charter_yaml_io import load_charter_yaml
from charter.activation.mission_type_key import canonical_mission_type_key, read_mission_type
from charter.activation.sync import apply_legacy_governance_selection_key_compat

if TYPE_CHECKING:
    from charter.activation.mission_type_profile_repository import MissionTypeProfileRepository
    from charter.offering.missions.mission_step_repository import _PackContextLike
    from charter.offering.missions.models import MissionType

__all__ = [
    "CrossGrainDoubleDeclarationError",
    "GovernancePayload",
    "MissionTypeEmptyActionSequenceError",
    "MissionTypeProfile",
    "ResolvedGovernance",
    "ResolvedMissionType",
    "UnknownMissionTypeError",
    "existing_mission_types",
    "resolve_action_sequence_layer",
    "resolve_mission_type_context",
    "resolve_mission_type_key",
    "validate_activatable_mission_type",
]


#: The ordered governance kinds carried by :class:`ResolvedGovernance`.  The
#: order is load-bearing for deterministic rendering (NFR-007).
_GOVERNANCE_KINDS: tuple[str, ...] = (
    "directives",
    "tactics",
    "paradigms",
    "styleguides",
    "toolguides",
    "procedures",
    "agent_profiles",
)


#: The parsed ``<type>/expected-artifacts.yaml`` manifest: a top-level mapping
#: (``schema_version`` / ``mission_type`` / ``required_by_step`` / ...) owned
#: and versioned by doctrine (``charter.offering.missions.repository``).  This is a
#: **type alias**, not a pydantic model — a model would force ``src/charter``
#: to own and validate a schema that belongs to the doctrine layer, crossing
#: the charter -> doctrine boundary the wrong direction (C-001).  Charter
#: treats the manifest as opaque passthrough data; only its outer shape
#: (a string-keyed mapping) is asserted here.
_ExpectedArtifactsManifest = Mapping[str, Any]


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


class MissionTypeProfile(BaseModel):
    """Mission-type-scoped governance profile.

    Mirrors the shape documented in data-model.md §6 and
    contracts/mission-type-profile.md.  ``extra="forbid"`` so typos in
    the YAML surface immediately rather than silently rendering empty
    selections.

    Overlay identity (``id``)
    -------------------------
    ``BaseDoctrineRepository`` (``doctrine/base.py``) keys every overlay on the
    raw YAML ``id`` field and **skips id-less overlay files** (``base.py:249``),
    so a project override at
    ``.kittify/doctrine/mission_types/<type>/governance-profile.yaml`` only
    field-merges onto the shipped profile when it carries an ``id``.  This
    profile therefore exposes an ``id`` that is bound to ``mission_type`` by an
    invariant: **``id == mission_type`` for every profile** (shipped or
    project).  When the YAML omits ``id`` the validator derives it from
    ``mission_type`` (backward-compatible for direct model construction); when
    both are present they MUST agree, or field-merge would mis-key silently.
    Every shipped ``governance-profile.yaml`` (software-dev today; the other
    three authored by WP06/07/08) MUST carry ``id`` equal to its
    ``mission_type``.
    """

    model_config = ConfigDict(extra="forbid")

    mission_type: str
    #: Overlay identity for the ``doctrine/base.py`` builtin → org → project
    #: stack.  Bound to ``mission_type`` by :meth:`_bind_id_to_mission_type`
    #: (defaults to ``mission_type`` when absent; MUST equal it when present).
    id: str = ""
    template_set: str | None = None
    selected_directives: list[str] = Field(default_factory=list)
    selected_tactics: list[str] = Field(default_factory=list)
    selected_paradigms: list[str] = Field(default_factory=list)
    selected_styleguides: list[str] = Field(default_factory=list)
    selected_toolguides: list[str] = Field(default_factory=list)
    selected_procedures: list[str] = Field(default_factory=list)
    selected_agent_profiles: list[str] = Field(default_factory=list)
    selected_mission_step_contracts: list[str] = Field(default_factory=list)
    available_tools: list[str] = Field(default_factory=list)
    activations: list[ActivationEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def _bind_id_to_mission_type(self) -> MissionTypeProfile:
        """Enforce the ``id == mission_type`` overlay invariant.

        A blank ``id`` (the default, and the case for direct model construction
        or an ``id``-less YAML) is derived from ``mission_type``.  A non-blank
        ``id`` that disagrees with ``mission_type`` is a construction-time
        error: ``doctrine/base.py`` keys overlays on ``id``, so a mismatch would
        route a project override onto the wrong shipped profile silently.
        """
        if not self.id:
            self.id = self.mission_type
        elif self.id != self.mission_type:
            raise ValueError(
                f"MissionTypeProfile.id ({self.id!r}) must equal mission_type "
                f"({self.mission_type!r}). The overlay stack in doctrine/base.py "
                "keys on id; a mismatch would mis-key a project override onto the "
                "wrong shipped profile."
            )
        return self


@dataclass(frozen=True)
class GovernancePayload:
    """Rendered governance payload for a mission-type-resolved context.

    Carries the rendered prompt text plus the resolved ``mission_type``
    so callers (and the ATDD test) can sanity-check that the resolver
    routed to the correct profile.
    """

    text: str
    mission_type: str


class UnknownMissionTypeError(ValueError):
    """Raised when a mission type cannot be resolved to a loadable profile.

    The hard-fail behaviour is the FR-001 / FR-003 contract: there MUST NOT be
    a silent ``software-dev-default`` fallback for non-software missions.  The
    message MUST contain the unknown ``mission_type`` verbatim so operators can
    diagnose typos or missing profile files.

    FR-009: The message MUST also list the registered (activated) mission
    type IDs so operators know what values are valid.

    FR-006 / SC-003 (#3183): ``mission_type_id`` is not always absent from
    ``registered_ids`` — a project may activate a custom type
    (``existing_mission_types()`` returns it) that still has no resolvable
    ``MissionTypeProfile`` / mission-type definition on disk (see
    :func:`resolve_mission_type_context`'s ``_resolve_action_slot`` caller).
    That is a genuinely different fact from "not activated at all", so the
    message states it separately ("is activated but has no loadable
    profile") instead of folding the id into the same "Unknown mission type
    ... Registered types: ..." sentence, which would call the same id both
    unknown and registered at once.

    Attributes
    ----------
    mission_type_id:
        The mission type ID that failed to resolve.
    registered_ids:
        Sorted list of activated mission type IDs at the time of the error.
    """

    def __init__(
        self,
        mission_type_id: str,
        registered_ids: list[str] | None = None,
    ) -> None:
        self.mission_type_id = mission_type_id
        self.registered_ids: list[str] = registered_ids if registered_ids is not None else []
        if mission_type_id in self.registered_ids:
            # Activated-but-unresolvable case (#3183): naming this id both
            # "unknown" and "registered" in one sentence is the defect this
            # branch exists to avoid. State the two real facts separately.
            message = (
                f"Mission type {mission_type_id!r} is activated but has no "
                "loadable profile."
            )
            other_registered = [
                rid for rid in self.registered_ids if rid != mission_type_id
            ]
            if other_registered:
                others_str = ", ".join(other_registered)
                message += f" Other activated mission types: {others_str}."
        elif self.registered_ids:
            ids_str = ", ".join(self.registered_ids)
            message = (
                f"Unknown mission type {mission_type_id!r}. "
                f"Registered types: {ids_str}."
            )
        else:
            message = (
                f"Unknown mission type {mission_type_id!r}. "
                "No registered mission types are available."
            )
        super().__init__(message)


class MissionTypeEmptyActionSequenceError(ValueError):
    """Raised when a mission type resolves with no action sequence (FR-004).

    This is the mission's own dominant risk (CL-003, mission
    ``up-mission-type-seam-01KZY1JB``): an org- or project-layer
    mission-type YAML that carries only ``schema_version``/``id``/
    ``display_name`` (no ``action_sequence``) loads CLEAN --
    :class:`~charter.offering.missions.models.MissionType`'s ``action_sequence``
    field is ``list[str] | None``, and its own validator
    (``MissionType._validate_action_sequence``) only enforces the
    non-empty invariant when the field is **not** ``None``. Before this
    error existed, a mission of that type would resolve "successfully"
    through :func:`_resolve_action_slot` and plan **nothing** -- the
    ``list(mission.action_sequence or [])`` silent-empty degradation, with
    no error anywhere (NFR-002).

    Mirrors :class:`UnknownMissionTypeError`'s shape (a plain ``ValueError``
    subclass carrying structured attributes plus a formatted message,
    raised at the same call site for an analogous configuration-
    inconsistency case) per FR-004's explicit instruction to follow that
    precedent rather than a bare ``ValueError``/``Exception``.

    A built-in mission type can never trigger this: every shipped
    ``packs/built-in/missions/mission_types/*.yaml`` resolves a non-empty
    ``action_sequence`` by construction (either YAML-authored or
    WP02-projected via ``_inject_projected_fields``), locked by
    ``tests/runtime/test_runtime_seam.py``'s golden-parity suite across all
    four built-in types. This error is therefore reachable only for a type
    that resolved through the org or project layer (FR-001/FR-002).

    Attributes
    ----------
    mission_type_id:
        The mission type ID that resolved with an empty action sequence.
    layer:
        The layer the mission type resolved from -- ``"org"`` or
        ``"project"`` (never ``"built-in"``; see above).
    """

    def __init__(self, mission_type_id: str, layer: str) -> None:
        self.mission_type_id = mission_type_id
        self.layer = layer
        super().__init__(
            f"mission type `{mission_type_id}` resolved from layer `{layer}` "
            "has an empty action sequence."
        )


class CrossGrainDoubleDeclarationError(ValueError):
    """Raised when one artifact is declared in both governance grains (FR-013).

    A single artifact URN MUST appear in **at most one** grain — the type-grain
    (``governance-profile.yaml``) OR the action-grain (action index) — never
    both.  Comparison is on the **canonical URN**, so ``003-foo``,
    ``DIRECTIVE_003`` and ``urn:directive:003`` all collide.  A double
    declaration is a construction-time error, not a silent de-duplication.

    Attributes
    ----------
    kind:
        The governance kind the collision was found in (e.g. ``directives``).
    artifact:
        The action-grain artifact id that collided with the type grain.
    """

    def __init__(self, kind: str, artifact: str) -> None:
        self.kind = kind
        self.artifact = artifact
        super().__init__(
            f"Artifact {artifact!r} is declared in both the type grain and the "
            f"action grain for governance kind {kind!r}. An artifact may appear "
            "in at most one grain (FR-013); remove the duplicate declaration."
        )


@dataclass(frozen=True)
class ResolvedGovernance:
    """Structured, ordered governance selections for a mission type.

    Each ``selected_*`` field is an **ordered** ``list[str]`` (an explicit,
    tested sort — NFR-007), not a set, so rendering is deterministic.  Built by
    unioning the type grain (``governance-profile.yaml``) with the action grain
    (action index), de-conflicting on canonical URN (double declaration across
    grains is forbidden, FR-013).
    """

    selected_directives: list[str] = field(default_factory=list)
    selected_tactics: list[str] = field(default_factory=list)
    selected_paradigms: list[str] = field(default_factory=list)
    selected_styleguides: list[str] = field(default_factory=list)
    selected_toolguides: list[str] = field(default_factory=list)
    selected_procedures: list[str] = field(default_factory=list)
    selected_agent_profiles: list[str] = field(default_factory=list)
    provenance: str = "builtin"

    @classmethod
    def from_grains(
        cls,
        *,
        type_grain: Mapping[str, list[str]],
        action_grain: Mapping[str, list[str]],
        provenance: str = "builtin",
    ) -> ResolvedGovernance:
        """Union ``type_grain`` ∪ ``action_grain`` into ordered selections.

        For each governance kind the two grains are merged, de-conflicted on
        canonical URN, and sorted deterministically.  A URN present in **both**
        grains raises :class:`CrossGrainDoubleDeclarationError` (FR-013).
        """
        merged: dict[str, list[str]] = {}
        for kind in _GOVERNANCE_KINDS:
            merged[f"selected_{kind}"] = _merge_disjoint_grain(
                kind,
                list(type_grain.get(kind, [])),
                list(action_grain.get(kind, [])),
            )
        return cls(provenance=provenance, **merged)


@dataclass(frozen=True)
class ResolvedMissionType:
    """In-memory bundle produced by :func:`resolve_mission_type_context`.

    ``mission_type`` is the canonicalized key (``None`` for a typeless mission).
    ``governance_text`` / ``action_sequence`` are populated eagerly on the hot
    path; ``template_set`` is projected lazily from the activated doctrine
    :class:`~charter.offering.missions.models.MissionType` artifact.

    ``governance`` (WP03), ``template_set``, ``expected_artifacts`` (WP10) and
    ``step_contracts`` (WP11) are resolved **lazily** (NFR-001): ``governance`` triggers the
    FR-013 type-grain / action-grain union (which reads every one of the
    mission type's ``actions/*/index.yaml`` files off disk via
    :func:`charter.activation.action_grain.aggregate_action_grain`); ``expected_artifacts``
    and ``step_contracts`` each read a separate doctrine artefact off disk. The
    FSM / runtime-next callers of :func:`resolve_mission_type_context` consume
    only ``action_sequence``, so none of the three ever fire on the hot path.
    Deferring all three disk-reading slots behind ``@cached_property`` keeps the
    hot path well under the 100ms budget while preserving the public read
    shape: ``bundle.governance`` is still a non-``None``
    :class:`ResolvedGovernance` for a registered type, ``bundle.expected_artifacts``
    is still a non-``None`` dict for a registered type, and
    ``bundle.step_contracts`` is still the ordered list, and
    ``bundle.template_set`` is an immutable mapping or explicit ``None``. Each
    is memoised on first access, so repeated reads stay cheap.
    """

    mission_type: str | None
    governance_text: str
    action_sequence: list[str]
    provenance: str
    #: Deferred resolver for the activated doctrine artifact's template
    #: mapping. ``None`` yields ``None`` for the neutral/typeless bundle.
    _template_set_thunk: Callable[[], Mapping[str, str] | None] | None = field(
        default=None, repr=False, compare=False
    )
    #: Deferred resolver for ``governance``. ``None`` yields ``None`` (the
    #: neutral/typeless bundle). Excluded from ``eq``/``repr``: equality and
    #: determinism hinge on the eager, hot-path fields plus the memoised
    #: values callers actually assert on, not on the thunk identity.
    _governance_thunk: Callable[[], ResolvedGovernance] | None = field(
        default=None, repr=False, compare=False
    )
    #: Deferred resolver for ``expected_artifacts``. ``None`` yields ``None``
    #: (the neutral/typeless bundle). Excluded from ``eq``/``repr`` so equality
    #: and determinism hinge on the eager, hot-path fields only.
    _expected_artifacts_thunk: Callable[[], _ExpectedArtifactsManifest | None] | None = field(
        default=None, repr=False, compare=False
    )
    #: Deferred resolver for ``step_contracts``. ``None`` yields ``[]``.
    _step_contracts_thunk: Callable[[], list[str]] | None = field(
        default=None, repr=False, compare=False
    )

    @cached_property
    def governance(self) -> ResolvedGovernance | None:
        """Lazily resolve the FR-013 type-grain/action-grain union (memoised).

        ``None`` for the neutral/typeless bundle. Triggers
        :class:`CrossGrainDoubleDeclarationError` on first access if a URN is
        double-declared — a construction-time concern deferred to first read,
        NOT eliminated. Nothing on the hot ``action_sequence`` path touches
        this property (verified: no ``src/`` reader besides this class).
        """
        if self._governance_thunk is None:
            return None
        return self._governance_thunk()

    @cached_property
    def template_set(self) -> Mapping[str, str] | None:
        """Lazily expose the activated doctrine artifact's immutable mapping."""
        if self._template_set_thunk is None:
            return None
        return self._template_set_thunk()

    @cached_property
    def expected_artifacts(self) -> _ExpectedArtifactsManifest | None:
        """Lazily resolve the WP10 expected-artifacts slot (memoised)."""
        if self._expected_artifacts_thunk is None:
            return None
        return self._expected_artifacts_thunk()

    @cached_property
    def step_contracts(self) -> list[str]:
        """Lazily resolve the WP11 ordered step-contract IDs (memoised)."""
        if self._step_contracts_thunk is None:
            return []
        return self._step_contracts_thunk()


# ---------------------------------------------------------------------------
# Charter API — activation set
# ---------------------------------------------------------------------------


def existing_mission_types(repo_root: Path) -> list[str]:
    """Return sorted, deduplicated IDs of activated mission types for the project.

    Only types that are explicitly activated in the project charter are returned.
    Non-activated types are excluded regardless of their presence in the doctrine
    layer.  Conversely, a project MAY activate a custom (non-built-in) mission
    type id, and that id is returned as-is; this function does not intersect
    against the built-in catalog, since doing so would silently drop
    legitimately-activated custom types (locked in by
    ``tests/charter/test_action_sequence_dispatch.py::TestExistingMissionTypes::test_returns_custom_type_when_activated``).
    Being returned here means only that the id is *activated* — it does not by
    itself mean the type will resolve end to end. A custom id still needs a
    ``MissionTypeProfile`` that :func:`resolve_mission_type_context` can
    actually load (governance slot) and/or a doctrine-layer action-sequence
    definition (action slot); lacking either, resolution still hard-fails with
    :class:`UnknownMissionTypeError`, even though the id appears in this
    function's return value — :class:`UnknownMissionTypeError` distinguishes
    that "activated but has no loadable profile" case from a genuinely
    unregistered id (FR-006, #3183) rather than calling the same id both
    unknown and registered.

    Reads ``.kittify/config.yaml`` via :class:`~charter.activation.pack_context.PackContext`
    to obtain the activation set. ``PackContext.activated_mission_types`` is
    the sole activation authority for this gate (WP04): it is read directly
    from the provisioned ``mission_type_activations`` key, with no implicit
    "all built-ins" backfill when that key is absent.  Provisioning
    (``spec-kitty init`` / ``spec-kitty upgrade``) is the only writer of a
    non-empty set. This is a **read / gating** path: an unprovisioned project
    returns an EMPTY list here WITHOUT raising (construction is now total,
    WP04). The actionable fail-closed for "a mission requires at least one
    activated mission type" fires only at the mission-create / require
    boundary (``create_mission_core``), never on this read path.

    FR-006 activation gate — this function IS the gate, and it pre-existed FR-006
    ---------------------------------------------------------------------------
    **This function is the FR-006 activation gate for the 10th doctrine-artifact
    kind (mission-type), and it already existed, unchanged in substance, before
    the mission that added FR-006.** Its body has returned exactly
    ``sorted(pack_context.activated_mission_types)`` — i.e. filtered by the
    project's activation set, never the unfiltered doctrine-layer catalog —
    since before this mission touched this file. ``PackContext.activated_mission_types``
    is not three-state like the other activation fields
    (:class:`~charter.activation.pack_context.PackContext` docstring); it is always a
    concrete ``frozenset[str]`` at construction time -- read directly from the
    provisioned ``mission_type_activations`` key, with **no** implicit
    collapse to :func:`~charter.offering.missions.mission_type_repository.builtin_mission_type_id_set`
    when the key is absent (WP04 removed that backfill; an absent key resolves
    to ``frozenset()`` and construction stays total -- the fail-closed moved
    to the create/require boundary instead of raising here). That
    concreteness, plus this function's filtering return statement, is what
    makes mission-type gating binary (filtered / not) rather than the
    three-state ``None``/``frozenset()``/``{ids}`` branching the other 9
    kinds require.

    What this mission actually did here: it **verified** the gate was live (by
    reverting this module to its pre-mission state and confirming the mission's
    own regression suite,
    ``tests/charter/test_mission_type_activation_gating.py``, still passes
    against the reverted code — DIRECTIVE_041, mine the pre-existing behaviour
    before claiming a fix), and it **added regression coverage**
    (``tests/charter/test_mission_type_activation_gating.py``) to keep the gate
    durable going forward. It did **not** add a new gate, and the one edit made
    to :func:`resolve_mission_type_context` (wrapping the already-list
    ``registered`` in a ``frozenset`` before the membership check) was
    semantically identical to checking membership on the list directly — a
    cosmetic change, not a behavioural one, now reverted. See that function's
    short pointer comment for where the (pre-existing) check is applied.

    FR-018: This function is the **single source of truth** for
    "what mission types are activated".  Do not duplicate this logic elsewhere.

    Parameters
    ----------
    repo_root:
        Repository root containing ``.kittify/config.yaml``.

    Returns
    -------
    list[str]
        Sorted, deduplicated activated mission type IDs.
    """
    from charter.activation.pack_context import PackContext  # noqa: PLC0415 — lazy; avoids circular

    pack_context = PackContext.from_config(repo_root)
    return sorted(pack_context.activated_mission_types)


# ---------------------------------------------------------------------------
# The seam: resolve_mission_type_context
# ---------------------------------------------------------------------------


def resolve_mission_type_context(
    repo_root: Path,
    *,
    mission_type: str | None = None,
    feature_dir: Path | None = None,
) -> ResolvedMissionType:
    """Resolve the single charter-mediated mission-type context bundle.

    Behaviour (contract C1)
    ------------------------
    * Resolves the type key: explicit ``mission_type`` → ``feature_dir/meta.json``
      → typeless.
    * **Typeless** (no type at all) → a neutral bundle, never software-dev
      (FR-003a).
    * **Unknown *typed*** mission (type present, unrecognised, no project
      override) → :class:`UnknownMissionTypeError` (FR-003).  Never software-dev.
    * **Known type, empty grain** → empty resolved selections, no error (FR-004).
    * Governance = type-grain ∪ action-grain, ordered, URN-deconflicted
      (FR-013, NFR-007).
    * The two hard-fail policies (governance tolerant when a project override
      exists; action-sequence strict) are preserved as explicit branches.

    The activation gate applied below (``is_registered``) is the FR-006 gate;
    it pre-existed this mission and lives in
    :func:`existing_mission_types` — see that function's docstring for the
    full account of what this mission verified versus added.

    Activated-but-unresolvable message fix (FR-006, #3183): an activated
    custom type id that has no resolvable ``MissionTypeProfile`` on disk
    still hard-fails via :class:`UnknownMissionTypeError` from the action
    slot, but the message no longer lists the very id it names among its own
    ``registered_ids`` as if that were a contradiction — e.g. activating only
    ``my-custom`` and resolving it now raises "Mission type 'my-custom' is
    activated but has no loadable profile." instead of the old "Unknown
    mission type 'my-custom'. Registered types: my-custom." See
    :class:`UnknownMissionTypeError`'s own docstring for the branch that
    distinguishes the two cases, and
    ``tests/charter/test_mission_type_profiles.py::TestResolveMissionTypeGovernanceValidation::test_activated_but_unresolvable_profile_message_is_not_contradictory``
    for the red-first reproduction this fix answers.

    Parameters
    ----------
    repo_root:
        Repository root for the project under resolution.
    mission_type:
        Explicit mission type key (takes precedence over ``feature_dir``).
    feature_dir:
        The mission's ``kitty-specs/<mission-slug>/`` directory; its
        ``meta.json`` is the source of truth for ``mission_type`` when
        ``mission_type`` is not given.

    Returns
    -------
    ResolvedMissionType
        The resolved bundle (both consumers converge on this).
    """
    type_key = _resolve_type_key(mission_type, feature_dir)
    if type_key is None:
        return _neutral_context()

    # FR-006 activation gate (pre-existing — see existing_mission_types()'s
    # docstring): the candidate type is checked for membership in the
    # project's activated-mission-type set, surfaced here through
    # existing_mission_types(), FR-006/FR-018's single source of truth.
    # `registered` stays an ordered list (not a set) so
    # UnknownMissionTypeError.registered_ids keeps its documented list shape.
    registered = existing_mission_types(repo_root)
    is_registered = type_key in registered
    has_override = _project_has_doctrine_overrides(repo_root)

    # FR-002 (WP04): construct the real PackContext and thread it into both
    # projection slots below -- sibling to (not a replacement for) the
    # PackContext existing_mission_types() already builds one call-frame
    # down purely to compute `registered`/`is_registered`, above. This is a
    # second, separate construction: CL-001 forbids threading a
    # project-dependent value into MissionTypeRepository.default()'s
    # cls-keyed cache, so the two call sites deliberately do not share one
    # PackContext instance -- each constructs its own from the same
    # repo_root. PackContext.from_config() is a plain read (no caching of
    # its own) and is called this way at every other charter call site
    # (see e.g. charter.activation.compiler, charter.activation.action_doctrine_bundle).
    from charter.activation.pack_context import PackContext  # noqa: PLC0415 — lazy; avoids circular

    pack_context = PackContext.from_config(repo_root)

    governance_provenance, governance_text, governance_thunk = _resolve_governance_slot(
        type_key,
        registered=registered,
        is_registered=is_registered,
        has_override=has_override,
        repo_root=repo_root,
    )
    action_sequence = _resolve_action_slot(
        type_key,
        registered=registered,
        is_registered=is_registered,
        pack_context=pack_context,
    )
    return ResolvedMissionType(
        mission_type=type_key,
        governance_text=governance_text,
        action_sequence=action_sequence,
        provenance=governance_provenance,
        # The FR-013 union (governance) + template mapping + WP11
        # (step-contract artefact, FR-008) + WP10 (doctrine gate tree) each read
        # off disk; defer all four so the
        # FSM hot path (action_sequence only) stays under the NFR-001 100ms
        # budget. Each is memoised on first access.
        _governance_thunk=governance_thunk,
        _template_set_thunk=lambda: _resolve_template_set_slot(
            type_key, is_registered=is_registered, pack_context=pack_context
        ),
        _step_contracts_thunk=lambda: _resolve_step_contracts_slot(
            type_key, is_registered=is_registered
        ),
        _expected_artifacts_thunk=lambda: _resolve_expected_artifacts_slot(
            type_key, is_registered=is_registered, repo_root=repo_root
        ),
    )


def resolve_mission_type_key(
    *,
    mission_type: str | None = None,
    feature_dir: Path | None = None,
) -> str | None:
    """Resolve the canonical mission-type key: explicit arg → ``meta.json`` → None.

    This is the boundary-safe key resolver the action-doctrine path keys off
    (WP04 / #883).  It is the *same* precedence and canonicalization the full
    :func:`resolve_mission_type_context` seam applies, factored out so the
    action-doctrine bundle can obtain the mission type WITHOUT triggering
    governance / action-sequence resolution (and its ``UnknownMissionTypeError``
    hard-fail, which is enforced on the governance surface separately).

    A blank / absent value (typeless mission, or a genuinely mission-less
    caller passing neither argument) degrades to ``None``.  ``None`` is the
    neutral, typeless result — callers MUST treat it as "no mission type" and
    degrade accordingly (FR-003a); it is NEVER substituted with a software-dev
    default (FR-001, FR-012).

    Parameters
    ----------
    mission_type:
        Explicit mission type key (takes precedence over ``feature_dir``).
    feature_dir:
        The mission's ``kitty-specs/<mission-slug>/`` directory; its
        ``meta.json`` ``mission_type`` field is the source of truth when
        ``mission_type`` is not given.
    """
    return _resolve_type_key(mission_type, feature_dir)


def _neutral_context() -> ResolvedMissionType:
    """Return the neutral (typeless) bundle — never software-dev (FR-003a)."""
    return ResolvedMissionType(
        mission_type=None,
        governance_text="",
        action_sequence=[],
        provenance="builtin",
        # Typeless bundle: all four lazy slots stay at their neutral defaults
        # (``governance`` -> ``None``, ``expected_artifacts`` -> ``None``,
        # ``step_contracts`` -> ``[]``, ``template_set`` -> ``None``).
    )


def _resolve_type_key(mission_type: str | None, feature_dir: Path | None) -> str | None:
    """Resolve the canonical mission-type key: explicit arg → meta.json → None.

    A blank / absent value degrades to ``None`` (typeless) via the single
    boundary-safe canonicalizer (WP02); it is never substituted with a
    software-dev default.
    """
    if mission_type is not None:
        return canonical_mission_type_key(mission_type)
    if feature_dir is None:
        return None
    return _read_meta_mission_type(feature_dir)


def _read_meta_mission_type(feature_dir: Path) -> str | None:
    """Return the canonical ``mission_type`` key from ``feature_dir/meta.json``.

    Loads the mission's ``meta.json`` (file I/O stays here, per the dict-in seam
    design) and delegates the field-extract + canonicalization to the one shared
    runtime reader :func:`charter.mission_type_key.read_mission_type` (rc3 M5
    FR-001 — the M3↔M5 reconciliation: the charter path and the CLI path resolve
    through the *same* authority so they cannot re-diverge). Reads only the
    canonical ``mission_type`` field (never legacy ``mission``, FR-002).

    Best-effort: a missing / unreadable / malformed ``meta.json`` — or a
    ``meta.json`` without a ``mission_type`` key — degrades to ``None`` (the
    neutral, typeless result), never a software-dev default.
    """
    meta_path = feature_dir / "meta.json"
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return read_mission_type(data)


def _resolve_governance_slot(
    mission_type: str,
    *,
    registered: list[str],
    is_registered: bool,
    has_override: bool,
    repo_root: Path,
) -> tuple[str, str, Callable[[], ResolvedGovernance]]:
    """Resolve the governance slot under the **tolerant** hard-fail policy.

    Hard-fails only when the type is neither registered nor covered by a project
    override — otherwise it resolves (an unknown type with a project override is
    tolerated; a known type with an empty grain resolves empty, FR-004). This
    **registration guard stays eager** — it is a cheap, in-memory activation-set
    check, not a disk-reading concern, so there is no reason to defer it (and
    deferring it would turn a construction-time hard-fail into a
    first-property-access hard-fail, changing the FR-003 contract).

    The profile is loaded through :class:`~charter.activation.mission_type_profile_repository.MissionTypeProfileRepository`
    so a per-type project override at
    ``.kittify/doctrine/mission_types/<type>/governance-profile.yaml`` field-merges
    onto the shipped baseline via the shared ``doctrine/base.py`` overlay
    (project > org > builtin) — no second merge site is added here.  ``provenance``
    reflects the winning layer for that type and is computed **eagerly** here
    (``repo.get_provenance``), independent of the governance union — callers must
    not force the union just to read the provenance.

    Only the FR-013 type-grain/action-grain union is deferred: it is returned as
    a closure (``governance_thunk``) rather than resolved inline.  The union
    reads every one of ``mission_type``'s ``actions/*/index.yaml`` files off disk
    (:func:`charter.activation.action_grain.aggregate_action_grain`), so deferring it keeps
    the hot ``action_sequence`` path free of that I/O (NFR-001).

    Returns
    -------
    tuple[str, str, Callable[[], ResolvedGovernance]]
        ``(provenance, governance_text, governance_thunk)``.
    """
    if not is_registered and not has_override:
        raise UnknownMissionTypeError(mission_type, registered_ids=registered)

    repo = _mission_type_profile_repository(repo_root)
    profile = repo.get(mission_type)
    provenance = repo.get_provenance(mission_type) or "project"
    text = _render_profile_payload(profile, mission_type)

    def governance_thunk() -> ResolvedGovernance:
        from charter.activation.mission_type_profile_repository import (  # noqa: PLC0415 — lazy; avoids cycle (mirrors _mission_type_profile_repository below)
            builtin_missions_root,
        )

        # consume the promoted builtin_missions_root() — WP06 #2668
        built_in_dir = builtin_missions_root()
        action_grain = aggregate_action_grain(built_in_dir, mission_type)
        return ResolvedGovernance.from_grains(
            type_grain=_profile_type_grain(profile),
            action_grain=action_grain,
            provenance=provenance,
        )

    return provenance, text, governance_thunk


def resolve_action_sequence_layer(
    mission_type_id: str,
    *,
    mission_types_dirs: tuple[Path, ...],
    pack_context: _PackContextLike,
) -> str:
    """Name the layer that resolved *mission_type_id*, for FR-004's error message.

    Public (PR-BOUNDARY-001, pre-merge squad, mission
    up-mission-type-seam-01KZY1JB): also called from
    ``specify_cli.cli.commands.charter.mission_type.resolve_mission_type_source_layer``,
    which previously imported this by its private,
    leading-underscore name (bypassing the facade discipline the sibling
    ``resolve_layered_roster`` applies one line above it, via the
    ``charter.missions`` door). Renamed and added to this module's
    ``__all__`` so the cross-module dependency is a documented, discoverable
    part of the public contract instead of an unlisted private import.

    Mirrors :func:`~charter.offering.missions.mission_type_repository.resolve_layered_mission_types`'s
    own precedence (project > org, earliest ``pack_root`` wins > built-in-
    equivalent, CL-005) but only determines *which* layer's file exists for
    *mission_type_id* -- it does not re-parse or re-validate any YAML, since
    :func:`_resolve_action_slot` already has the resolved
    :class:`~charter.offering.missions.models.MissionType` in hand by the time this
    is called. Used solely to name the layer in
    :class:`MissionTypeEmptyActionSequenceError`'s message; callers only
    reach this helper once the type's action sequence is already known to be
    empty, so the built-in-equivalent fallback below is unreachable in
    practice (see that class's docstring) -- it is named as the honest
    default rather than raising a second error inside an error path.
    """
    # CL-005 path layout comes from the single authority in
    # charter.offering.missions.mission_type_repository (#3427) -- the same
    # constants resolve_layered_mission_types itself scans -- never re-spelled
    # inline here: the pre-#3427 inline literals silently pointed at the old
    # path if the authority's constants ever moved. Lazy import mirrors
    # _resolve_action_slot's own import of the same module below.
    from charter.offering.missions.mission_type_repository import (  # noqa: PLC0415 — lazy; mirrors _resolve_action_slot below
        ORG_MISSION_TYPES_SUBDIR,
        PROJECT_MISSION_TYPES_RELATIVE,
    )

    project_dir = pack_context.repo_root.joinpath(*PROJECT_MISSION_TYPES_RELATIVE)
    if (project_dir / f"{mission_type_id}.yaml").is_file():
        return "project"

    protected_pack_roots = {base_dir.parent for base_dir in mission_types_dirs}
    for pack_root in pack_context.pack_roots:
        if pack_root in protected_pack_roots:
            continue  # already handled by the built-in-equivalent layer
        if (pack_root / ORG_MISSION_TYPES_SUBDIR / f"{mission_type_id}.yaml").is_file():
            return "org"

    return "built-in"


def _resolve_action_slot(
    mission_type: str,
    *,
    registered: list[str],
    is_registered: bool,
    pack_context: _PackContextLike,
) -> list[str]:
    """Resolve the action sequence under the **strict** validation policy.

    The action sequence validates against the activation set with no escape
    hatch: an activated-but-undefined type raises.  An unregistered type that
    was tolerated by the governance slot (project override present) has no
    built-in action sequence, so it degrades to an empty list.

    **WP04 (FR-002, mission up-mission-type-seam-01KZY1JB):** resolves
    through :func:`~charter.offering.missions.mission_type_repository.resolve_layered_mission_types`
    -- the new, separate, module-level layered factory (WP03) -- instead of
    the built-in-only :meth:`MissionTypeRepository.default`. This is a
    repository-call **swap**, not argument-threading: the built-in-only
    accessor had no ``pack_context`` parameter to thread through in the
    first place. ``mission_types_dirs`` is the same built-in-equivalent root
    :meth:`MissionTypeRepository.default` itself resolves
    (``MissionTemplateRepository.default_missions_root() / "mission_types"``),
    so a project with no org/project mission-type packs activated
    (``pack_context`` resolving to the same built-in-only roster) sees
    byte-identical output to the pre-WP04 code path (User Story 3 AC1,
    locked by ``tests/runtime/test_runtime_seam.py``'s golden-parity suite).

    **WP06 (FR-004/CL-003, mission up-mission-type-seam-01KZY1JB):** a
    resolved type whose action sequence is empty -- own or, after the
    ``extends`` fallback, inherited -- no longer degrades to ``[]`` here. It
    raises :class:`MissionTypeEmptyActionSequenceError` naming the type id
    and the layer :func:`resolve_action_sequence_layer` attributes it to.
    Built-in types never trigger this (see that error class's docstring for
    why); this closes the CL-003 silent "plans nothing, reports success" gap
    that only became reachable once WP04 wired a non-built-in-layer roster
    into this function.

    **WP06 confirmation (S-B cutover, mission-step-authority):**
    ``mission.action_sequence`` below is already the WP02-projected value —
    ``MissionTypeRepository._load`` overlays ``project_action_sequence(steps)``
    onto the raw YAML field (via ``_inject_projected_fields``) before
    :class:`~charter.offering.missions.models.MissionType` validates, falling back to
    the authored YAML only while a given type's projection is still empty
    (pre-WP07). This resolver was never a bypass; it reads the injected
    model through the layered factory, which is itself memoized
    (``functools.cache``, keyed on ``(mission_types_dirs, pack_context)``) so
    this call never re-walks ``mission-steps/`` on the hot path. See
    ``tests/runtime/test_runtime_seam.py`` for the seam-equivalence lock
    (all 4 built-in types) and the extends-fallback check below.
    """
    if not is_registered:
        return []

    from charter.offering.missions.mission_type_repository import (  # noqa: PLC0415
        resolve_layered_mission_types,
    )
    from charter.offering.missions.repository import MissionTemplateRepository  # noqa: PLC0415

    mission_types_dirs = (MissionTemplateRepository.default_missions_root() / "mission_types",)
    roster = resolve_layered_mission_types(mission_types_dirs, pack_context)
    mission = roster.get(mission_type)
    if mission is None:
        # The type is activated but has no YAML definition resolvable in
        # any layer (built-in, org, or project).  This is a configuration
        # inconsistency; report it clearly rather than returning an empty
        # sequence.
        raise UnknownMissionTypeError(mission_type, registered_ids=registered)

    action_sequence = _resolve_with_extends_fallback(mission, roster)

    if not action_sequence:
        # FR-004/CL-003 (WP06): an org- or project-layer type -- built-in
        # types always resolve non-empty, see
        # MissionTypeEmptyActionSequenceError's docstring -- that reaches
        # here has no usable action sequence, own or inherited. Silently
        # returning [] would plan nothing and report success (NFR-002);
        # raise loudly instead, naming the id and the resolving layer.
        layer = resolve_action_sequence_layer(
            mission_type,
            mission_types_dirs=mission_types_dirs,
            pack_context=pack_context,
        )
        raise MissionTypeEmptyActionSequenceError(mission_type, layer)

    return action_sequence


def _resolve_with_extends_fallback(
    mission: MissionType, roster: Mapping[str, MissionType]
) -> list[str]:
    """Own action_sequence, or single-level extends fallback if own is empty.

    Factored out of :func:`_resolve_action_slot` (WP01, mission
    charter-activate-empty-action-sequence-01M0STSX) so both it and
    :func:`validate_activatable_mission_type` converge on the exact same
    extends-fallback rule instead of inlining it twice (DRY). Only a
    single-level fallback is attempted -- top-level ``extends`` only, no
    chain traversal -- mirroring :func:`_resolve_action_slot`'s pre-existing
    behavior exactly. A parent that is itself unresolvable or also empty
    leaves the result empty, deferring the "empty action sequence" decision
    to the caller rather than making it here.
    """
    action_sequence = list(mission.action_sequence or [])
    if not action_sequence and mission.extends is not None:
        parent = roster.get(mission.extends)
        if parent is not None:
            action_sequence = list(parent.action_sequence or [])
    return action_sequence


def validate_activatable_mission_type(mission_type_id: str, *, repo_root: Path) -> None:
    """Fail-closed activation-time gate (FR-001/NFR-001): raise if *mission_type_id*
    would resolve an empty action sequence (after the single-level ``extends``
    fallback) were it activated. No-ops when *mission_type_id* has no resolvable
    YAML in any layer at all -- that configuration inconsistency is already governed
    by ``plan_activation``'s ``UnknownActivationIdError`` (raised moments later,
    inside ``CharterPackManager.activate()`` via the ``available_ids`` membership
    check), which this function does not weaken, duplicate, or race (FR-004 note:
    this is a *different* pre-existing check than the read path's
    ``UnknownMissionTypeError``, and this function defers to the activation-time one).
    Bridge to spec.md's Edge Cases: spec.md names the read path's
    ``UnknownMissionTypeError`` as the general governance for "no resolvable YAML in
    any layer"; on this activation-time path specifically, it is
    ``plan_activation``'s ``available_ids`` membership check -- a distinct,
    pre-existing gate on a different module -- that actually fires first, before this
    function's caller (``activate_cmd``) is ever reached for such a candidate. The
    two named errors are not in tension: each is simply the check that governs its
    own path (read vs. activation-time), and this function correctly no-ops rather
    than re-deriving or racing either one.

    Deliberately called from the CLI seam (``activate.py``), NOT from
    ``activation_engine.plan_activation()``/``commit_plan()``: that module's own
    docstring states it performs no filesystem discovery and no ``config.yaml``
    load of its own (C-008) -- resolving whether a candidate's action sequence is
    empty requires exactly the filesystem-touching resolution
    :func:`_resolve_action_slot` performs. This function unconditionally runs that
    same resolution (not gated on ``is_registered``, unlike
    :func:`_resolve_action_slot`) precisely because, at activation time, the
    candidate is by definition not yet registered -- gating on ``is_registered``
    here would short-circuit to a no-op and reproduce the defect this function
    exists to close (issue #3702).

    Raises
    ------
    MissionTypeEmptyActionSequenceError
        If the candidate's own action sequence, or its single-level ``extends``
        fallback, is empty.
    """
    from charter.activation.pack_context import PackContext  # noqa: PLC0415 — lazy; avoids circular
    from charter.offering.missions.mission_type_repository import (  # noqa: PLC0415
        resolve_layered_mission_types,
    )
    from charter.offering.missions.repository import MissionTemplateRepository  # noqa: PLC0415

    pack_context = PackContext.from_config(repo_root)
    mission_types_dirs = (MissionTemplateRepository.default_missions_root() / "mission_types",)
    roster = resolve_layered_mission_types(mission_types_dirs, pack_context)
    mission = roster.get(mission_type_id)
    if mission is None:
        # No resolvable YAML in any layer -- not this function's concern
        # (see docstring); plan_activation's UnknownActivationIdError
        # governs that case.
        return

    action_sequence = _resolve_with_extends_fallback(mission, roster)
    if not action_sequence:
        layer = resolve_action_sequence_layer(
            mission_type_id,
            mission_types_dirs=mission_types_dirs,
            pack_context=pack_context,
        )
        raise MissionTypeEmptyActionSequenceError(mission_type_id, layer)


def _resolve_expected_artifacts_slot(
    mission_type: str,
    *,
    is_registered: bool,
    repo_root: Path,
) -> _ExpectedArtifactsManifest | None:
    """Resolve the expected-artifacts gate manifest from the doctrine tree.

    Populated from the now-canonical doctrine ``<type>/expected-artifacts.yaml``
    (WP10 / IC-07) after the upward reconcile, so the bundle carries the gate
    manifest that the dossier reader also reads. Returns ``None`` when the
    type is unregistered or has no gate manifest at any tier.

    **Retired mirror, now validated (WP02, #3770, FR-006):** this slot used
    to read the raw, UNVALIDATED parsed-YAML mapping directly off
    ``MissionTemplateRepository`` -- bypassing schema validation entirely,
    the mirror this mission most needed to fix. It now delegates the whole
    load (org-tier included, FR-008/contract C-4) to
    :func:`charter.activation.manifest_loader.load_manifest` (WP01's
    relocated, cached authority; doctrine-native, so this stays C-001-safe --
    ``charter.activation`` importing ``charter.activation`` is not a
    boundary crossing) and re-projects the validated
    :class:`~charter.offering.missions.expected_artifact_manifest.ExpectedArtifactManifest`
    back to a plain mapping via ``.model_dump()`` -- preserving this slot's
    existing ``Mapping``-shaped public contract (:attr:`ResolvedMissionType.expected_artifacts`,
    NFR-001 byte-compatibility) while gaining real schema validation as a
    side effect: a schema-invalid manifest now raises ``ManifestSchemaError``
    (see Raises below) instead of silently handing a bad raw mapping to
    every reader of this slot.

    Absent ⇒ ``None`` unconditionally (the ``is_registered`` short-circuit
    below, and the authority's own "no manifest at either tier" case) --
    this slot's own guard-table input is unchanged by this WP (C-003).

    Raises:
        ManifestSchemaError: A *found*, syntactically-valid manifest that
            fails schema validation (``extra="forbid"``) -- propagated
            unchanged from the authority, for BOTH tiers, BEFORE this
            function ever makes a None-vs-present decision. Not caught
            here: this slot must not re-swallow it.
        MalformedManifestError: A *found* manifest that fails to parse as
            YAML at all (or is present-but-unreadable, or a non-mapping)
            -- propagated unchanged from the authority, for BOTH tiers
            (mission ``expected-artifacts-loader-unification-01M1C9VQ``,
            #3412, closed the org-tier gap; the built-in tier already
            raised this in ``1763bf2ae3``).
    """
    if not is_registered:
        return None

    from charter.activation.manifest_loader import load_manifest  # noqa: PLC0415

    manifest = load_manifest(mission_type, repo_root=repo_root)
    if manifest is None:
        return None
    # `charter.*` is `follow_imports = "skip"` in [tool.mypy] (pyproject.toml)
    # so this module's mypy run doesn't walk unrelated pre-existing strict
    # debt elsewhere in the charter package; that also erases `load_manifest`'s
    # real (pydantic model) return type down to `Any`, so `.model_dump()`'s
    # actual `dict[str, Any]` return type is invisible here too. The cast
    # documents the type `model_dump()` actually returns at runtime -- mypy
    # is not wrong about the code, only blind to it through this boundary
    # (mirrors the identical rationale on `_resolve_org_manifest_mapping` in
    # `runtime.next.runtime_bridge_io`).
    return cast("_ExpectedArtifactsManifest", manifest.model_dump())


def _resolve_template_set_slot(
    mission_type: str,
    *,
    is_registered: bool,
    pack_context: _PackContextLike,
) -> Mapping[str, str] | None:
    """Project the activated doctrine mission type's immutable template mapping.

    The step authority (``MissionStep.template``) is the sole source. The
    similarly named governance-profile scalar is intentionally not read
    here. A defensive copy prevents consumers from mutating repository-owned
    model state, while :class:`types.MappingProxyType` preserves
    deterministic insertion order behind a read-only public surface.

    **S-C cutover (mission-step-creatability-01KXQA6R WP01, FR-002):** the
    persisted ``MissionType.template_set`` field is retired and this slot no
    longer reads it -- it computes
    ``project_template_set(steps)`` directly from
    ``MissionStepRepository.resolve_all_for_mission_type(mission_type,
    pack_context=pack_context)``.

    **WP04 (FR-002, mission up-mission-type-seam-01KZY1JB):** *pack_context*
    is the real ``PackContext`` :func:`resolve_mission_type_context` already
    constructs -- threaded straight through here (argument-threading only;
    ``MissionStepRepository.resolve_all_for_mission_type`` already accepts a
    ``pack_context`` parameter, this sibling module's own already-live
    pattern) so an org/project mission type's step-authored templates
    resolve for real instead of being invisible to a hardcoded
    ``pack_context=None``. For a project with no org/project mission-type
    packs activated, the resolved roster is identical to the built-in-only
    roster, so built-in-type output is unaffected (User Story 3 AC1,
    ``tests/runtime/test_runtime_seam.py``'s golden-parity suite). Threading
    the real ``pack_context`` also means the shared
    ``resolve_all_for_mission_type`` cache (NFR-003) is warm whenever
    :class:`MissionTypeRepository`'s ``action_sequence`` overlay already
    resolved the same ``(mission_type, pack_context)`` pair in this process
    -- one filesystem walk serves both consumers. This is the *dict*
    template mapping (per-type template mapping), never the unrelated
    ``charter.offering.template_set`` scalar (charter selection authority in
    ``resolver.py``/``compiler.py``/etc.) — C-002 keeps those surfaces
    fenced off.
    """
    if not is_registered:
        return None

    from charter.offering.missions.mission_step_repository import MissionStepRepository  # noqa: PLC0415
    from charter.offering.missions.step_projection import project_template_set  # noqa: PLC0415

    steps = list(
        MissionStepRepository.default()
        .resolve_all_for_mission_type(mission_type, pack_context=pack_context)
        .values()
    )
    template_set = project_template_set(steps)
    if template_set is None:
        return None
    return MappingProxyType(dict(template_set))


def _resolve_step_contracts_slot(
    mission_type: str,
    *,
    is_registered: bool,
) -> list[str]:
    """Resolve the mission type's step contracts from the doctrine artefact.

    FR-008 / SC-007: the doctrine ``MissionStepContractRepository`` is the
    single source for a type's step contracts — there is no ``specify_cli``
    copy. An unregistered type that the governance slot tolerated (a project
    override is present) has no built-in step contracts, so it degrades to an
    empty list, mirroring :func:`_resolve_action_slot`.
    """
    if not is_registered:
        return []

    from charter.offering.missions.step_contracts import (  # noqa: PLC0415 — lazy; charter -> doctrine is canonical
        resolve_step_contract_ids,
    )

    return resolve_step_contract_ids(mission_type)


# ---------------------------------------------------------------------------
# Grain construction + disjointness guard (FR-013)
# ---------------------------------------------------------------------------


def _profile_type_grain(profile: MissionTypeProfile | None) -> Mapping[str, list[str]]:
    """Project a :class:`MissionTypeProfile` into a governance grain mapping."""
    if profile is None:
        return {}
    return {
        "directives": list(profile.selected_directives),
        "tactics": list(profile.selected_tactics),
        "paradigms": list(profile.selected_paradigms),
        "styleguides": list(profile.selected_styleguides),
        "toolguides": list(profile.selected_toolguides),
        "procedures": list(profile.selected_procedures),
        "agent_profiles": list(profile.selected_agent_profiles),
    }


def _merge_disjoint_grain(kind: str, type_ids: list[str], action_ids: list[str]) -> list[str]:
    """Union two grains for one kind, forbidding cross-grain double declaration.

    Comparison is on the **canonical URN** so ``003-foo`` / ``DIRECTIVE_003`` /
    ``urn:directive:003`` collide.  The result is de-duplicated (within a grain)
    and sorted deterministically (NFR-007).
    """
    type_keys = {_canonical_artifact_key(raw) for raw in type_ids}
    for raw in action_ids:
        if _canonical_artifact_key(raw) in type_keys:
            raise CrossGrainDoubleDeclarationError(kind, raw)

    seen: set[str] = set()
    unique: list[str] = []
    for raw in [*type_ids, *action_ids]:
        key = _canonical_artifact_key(raw)
        if key in seen:
            continue
        seen.add(key)
        unique.append(raw)
    return sorted(unique)


def _canonical_artifact_key(raw: str) -> str:
    """Normalize an artifact reference to a canonical comparison key.

    Handles the three declaration forms — ``003-slug``, ``DIRECTIVE_003`` and
    ``urn:directive:003`` — collapsing each to the same numeric core.  A
    reference with no numeric code degrades to its slugified, lower-cased form.
    """
    text = raw.strip().lower()
    if text.startswith("urn:"):
        text = text.split(":")[-1]
    match = re.search(r"\d+", text)
    if match:
        return str(int(match.group(0)))
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


# ---------------------------------------------------------------------------
# Loader (internal — the historical ``load_profile`` public export is retired)
# ---------------------------------------------------------------------------


def _mission_type_profile_repository(
    repo_root: Path | None,
) -> MissionTypeProfileRepository:
    """Construct the overlay-aware profile repository.

    ``repo_root is None`` yields a **shipped-only** repository (built-in layer,
    no project overlay) — the shape used by the built-in resolution ATDD suite.
    A concrete ``repo_root`` wires the project overlay at
    ``.kittify/doctrine/mission_types/`` so per-type overrides ride the
    ``doctrine/base.py`` stack.

    Imported lazily to avoid a charter-internal import cycle
    (``mission_type_profile_repository`` imports this module for the schema).
    """
    from charter.activation.mission_type_profile_repository import (  # noqa: PLC0415 — lazy; avoids cycle
        MissionTypeProfileRepository,
    )

    if repo_root is None:
        return MissionTypeProfileRepository()
    from charter.offering.drg.org_pack_config import resolve_org_dirs  # noqa: PLC0415 — lazy; mirrors MissionTypeProfileRepository import above

    return MissionTypeProfileRepository.for_project(
        repo_root, org_dirs=resolve_org_dirs(repo_root, "mission_types")
    )


def _load_mission_type_profile(
    mission_type: str,
    repo_root: Path | None = None,
) -> MissionTypeProfile | None:
    """Load the governance profile for ``mission_type`` through the overlay stack.

    Resolves ``src/charter/offering/missions/<mission_type>/governance-profile.yaml`` as
    the shipped baseline and — when ``repo_root`` is given — field-merges a
    project override from
    ``<repo_root>/.kittify/doctrine/mission_types/<mission_type>/governance-profile.yaml``
    via :class:`~charter.activation.mission_type_profile_repository.MissionTypeProfileRepository`
    (project > org > builtin; :class:`~charter.offering.base.DoctrineLayerCollisionWarning`
    on shadow).  Keying on the ``id == mission_type`` invariant means a profile
    whose declared type disagrees with its directory is simply not found under
    ``mission_type`` (returns ``None``) rather than silently mis-routed.

    Not on the resolver's own path
    -------------------------------
    :func:`resolve_mission_type_context` (via :func:`_resolve_governance_slot`)
    calls the repository's ``.get()`` directly and does not route through this
    wrapper.  The wrapper's live caller is
    :func:`charter.activation.action_grain.scan_builtin_cross_grain_duplicates` (the IC-11
    built-in dup-scan), which needs the bare profile lookup without the
    resolver's registration/hard-fail branching.

    Returns
    -------
    MissionTypeProfile | None
        ``None`` when no profile exists for ``mission_type`` in any layer.  A
        resolved :class:`MissionTypeProfile` otherwise.

    Raises
    ------
    pydantic.ValidationError
        When a matching YAML is structurally malformed.
    """
    profile: MissionTypeProfile | None = _mission_type_profile_repository(repo_root).get(mission_type)
    return profile


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _project_has_doctrine_overrides(repo_root: Path) -> bool:
    """Return ``True`` iff the project charter declares any selection.

    IC-04 (WP04): re-pointed from the retired ``.kittify/charter/
    governance.yaml`` onto ``charter.yaml``'s ``governance:`` section — a
    project "has overrides" when ``charter.yaml``'s ``governance.charter``
    carries at least one non-empty ``selected_<kind>`` list. The retired
    ``governance.doctrine`` key is read through the shared CR-01 compat shim.
    This is consulted by the governance slot to decide whether an unknown
    ``mission_type`` should hard-fail (no overrides) or merely skip the
    missing profile (overrides present).

    Best-effort: any I/O or parse failure collapses to ``False`` so a
    malformed charter.yaml never silences the hard-fail contract.
    """
    charter_yaml_path = repo_root / CHARTER_YAML
    if not charter_yaml_path.exists():
        return False
    try:
        data = load_charter_yaml(charter_yaml_path)
    except Exception:  # noqa: BLE001 — best-effort governance probe
        return False
    if not isinstance(data, dict):
        return False
    governance = data.get("governance")
    if not isinstance(governance, dict):
        return False
    doctrine = apply_legacy_governance_selection_key_compat(governance).get("charter")
    if not isinstance(doctrine, dict):
        return False
    for key, value in doctrine.items():
        if not key.startswith("selected_"):
            continue
        if isinstance(value, list) and value:
            return True
    return False


def _render_profile_payload(
    profile: MissionTypeProfile | None,
    mission_type: str,
) -> str:
    """Render a textual governance payload for ``profile``.

    The renderer is intentionally compact — it lists the mission_type,
    the resolved ``template_set`` (if any), and the per-kind selections.
    The ATDD contract only requires:

    * The payload MUST NOT contain ``software-dev-default`` when the
      mission_type is not ``software-dev``.
    * The payload text MUST carry a ``Mission-Type Governance Profile:
      <mission_type>`` header matching the ``meta.json mission_type``.

    Richer formatting (full doctrine-text expansion, fetch stanzas,
    section bodies) is the responsibility of
    :func:`charter.activation.context.build_charter_context` and the existing
    renderers in ``src/charter/context_renderers/``; this resolver
    surfaces a stable summary that downstream tooling can splice into
    its broader prompt.
    """
    lines: list[str] = []
    lines.append(f"Mission-Type Governance Profile: {mission_type}")
    if profile is None:
        lines.append("  - No built-in profile; project overrides apply.")
        return "\n".join(lines) + "\n"

    if profile.template_set is not None:
        lines.append(f"  template_set: {profile.template_set}")
    else:
        lines.append("  template_set: (none — mission resolves its own)")

    kind_fields: tuple[tuple[str, list[str]], ...] = (
        ("selected_directives", profile.selected_directives),
        ("selected_tactics", profile.selected_tactics),
        ("selected_paradigms", profile.selected_paradigms),
        ("selected_styleguides", profile.selected_styleguides),
        ("selected_toolguides", profile.selected_toolguides),
        ("selected_procedures", profile.selected_procedures),
        ("selected_agent_profiles", profile.selected_agent_profiles),
        ("selected_mission_step_contracts", profile.selected_mission_step_contracts),
    )
    for field_name, ids in kind_fields:
        if ids:
            lines.append(f"  {field_name}: {', '.join(ids)}")
        else:
            lines.append(f"  {field_name}: (none)")

    if profile.available_tools:
        lines.append(f"  available_tools: {', '.join(profile.available_tools)}")
    if profile.activations:
        lines.append(f"  activations: {len(profile.activations)} entries")

    return "\n".join(lines) + "\n"
