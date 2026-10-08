"""Org-layer charter composition policy (WP09 / Mission B WP06).

This module defines the :class:`OrgCharterPolicy` Pydantic model and the
loader / merger that produce a merged policy across all configured org
doctrine packs.  It also exposes :func:`apply_org_charter_pre_fill`,
which non-destructively pre-fills the project-level charter interview
answers YAML with org-level defaults.

Architectural note
------------------
Org charter composition is an activation concern (mission
``charter-pack-cutover-01M491G6``, FR-010 / OD-9), next to its siblings
``org_pack_discovery`` and ``org_expected_artifacts``. It reads the pack
registry from :mod:`charter.offering.drg.org_pack_config` and imports nothing
from ``specify_cli``.

The pure side-effect (writing to ``answers.yaml``) is implemented in
``charter.activation.interview.apply_org_charter_pre_fill_to_answers``, which
accepts the merged policy data as plain Python (dict + list).

Public API
----------
- :class:`GovernancePolicy` — single governance policy entry
- :class:`OrgCharterPolicy` — top-level schema for ``org-charter.yaml``
- :func:`load_org_charter_policy` — load policy from a single pack root
- :func:`load_org_charter_policies` — load and merge across all packs
- :func:`apply_org_charter_pre_fill` — pre-fill interview answers on disk
- :func:`apply_org_charter_to_interview` — pre-fill an in-memory
  ``CharterInterview`` before the interactive prompt loop (FR-026)
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml as pyyaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from charter.activation.activation_engine import EffectiveSet
from charter.activation.activations import ActivationEntry, _activation_identity_key
from charter.activation.org_pack_discovery import last_non_empty_token, union_required_tokens
from charter.activation.kind_vocabulary import (
    UnrepresentableDirectiveIdError,
    resolve_selected_id_to_stem,
)
from charter.offering.artifact_kinds import ORG_REQUIRABLE_KIND_FIELDS, ArtifactKind
from charter.offering.drg.org_pack_config import load_pack_registry
from charter.offering.packs.pack_assembler import AssemblyResult, assemble_pack
from charter.offering.packs.pack_validator import ValidationIssue, ValidationResult, validate_pack
from charter.offering.packs.retired_fields import (
    RETIRED_PACK_FIELD,
    SCOPE_ORG_CHARTER,
    RetiredPackFieldError,
    raise_retired_field_at,
    reject_retired_fields,
    retired_field_errors,
)
from kernel.charter_pack_paths import pack_org_charter


if TYPE_CHECKING:
    from charter.activation.pack_context import PackContext

__all__ = [
    "GovernancePolicy",
    "OrgCharterCycleError",
    "OrgCharterExtensionError",
    "REQUIRED_KIND_FIELDS",
    "load_org_charter_policy",
    "load_org_charter_policies",
    "apply_org_charter_pre_fill",
    "apply_org_charter_to_interview",
    "validate_org_required_directive_stems",
    "validate_pack_with_org_charter",
    "assemble_pack_with_org_charter",
]


# ---------------------------------------------------------------------------
# Constants — the canonical list of artifact kinds an org pack can mandate.
#
# Naming parity rule (Mission B WP01 + WP06): every entry here corresponds
# to a ``selected_<kind>`` field on :class:`charter.activation.schemas.GovernanceCharterConfig`
# and a ``required_<kind>`` field on :class:`OrgCharterPolicy`.  The
# byte-identical parity is pinned by
# ``tests/architectural/test_artifact_selection_completeness.py``.
# ---------------------------------------------------------------------------


#: Artifact-kind suffixes (plural) for which an org pack may declare a
#: ``required_<kind>`` list.  Order matches the mission's selection-schema
#: ordering and is used by the union loop in
#: :func:`apply_org_charter_to_interview` and the merge loop in
#: :func:`load_org_charter_policies`.
REQUIRED_KIND_FIELDS: tuple[str, ...] = ORG_REQUIRABLE_KIND_FIELDS

#: The subset of :data:`REQUIRED_KIND_FIELDS` the interview seeds (config promotion
#: and the ``selected_<kind>`` overlay). A kind whose absent activation key already
#: puts the org-required ids in force (``ArtifactKind.effective_when_absent ==
#: "required"``) is left out: writing its key would freeze today's list, so a later
#: addition to the org's ``required_<kind>`` would stop applying.
_INTERVIEW_SEEDED_KIND_FIELDS: tuple[str, ...] = tuple(kind for kind in REQUIRED_KIND_FIELDS if ArtifactKind.from_plural(kind).effective_when_absent != "required")


# ---------------------------------------------------------------------------
# Schema models
# ---------------------------------------------------------------------------


class GovernancePolicy(BaseModel):
    """A single governance policy entry.

    Enforcement is *advisory-only* in this mission — only the literal
    string ``"advisory"`` is honoured today.  Other values parse and
    surface as advisories (see :func:`validate_org_charter_file`).
    """

    model_config = ConfigDict(extra="forbid")

    field: str
    value: str | bool
    enforcement: str = "advisory"


#: The ``org-charter.yaml`` schema version new and scaffolded files declare.
ORG_CHARTER_SCHEMA_VERSION = 2

#: Versions that differ only by the retired-field rejection, which applies to
#: every version alike, so an ``extends:`` chain may mix them (#3732).
_CHAIN_COMPATIBLE_SCHEMA_VERSIONS = frozenset({1, ORG_CHARTER_SCHEMA_VERSION})


class OrgCharterPolicy(BaseModel):
    """Top-level model for ``org-charter.yaml``.

    Empty instance (the default constructor) represents *no org policy*
    and is used as the zero-effect fallback when no packs configure
    ``org-charter.yaml``.

    Mission B WP06 extends this model with one ``required_<kind>`` list
    per :data:`REQUIRED_KIND_FIELDS` entry.  Each list mirrors the
    matching ``selected_<kind>`` field on
    :class:`charter.activation.schemas.GovernanceCharterConfig` (parity pinned by
    ``tests/architectural/test_artifact_selection_completeness.py``).
    Empty defaults preserve NFR-005 backward compatibility — existing
    ``org-charter.yaml`` files that only declare ``required_directives``
    parse unchanged.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: int = ORG_CHARTER_SCHEMA_VERSION
    """Schema version for the org-charter format.

    2 (#3732): activation entries use ``charter_pack_id``; the retired field
    name is rejected with ``RETIRED_PACK_FIELD``. A file that declares ``1``
    still validates as long as it carries no retired field (data-model.md
    "Enforced activations"), and versions 1 and 2 may share an ``extends:``
    chain (:data:`_CHAIN_COMPATIBLE_SCHEMA_VERSIONS`).

    Backward-compat: YAML files may store this as a string (``"1"``)
    or an integer.  The ``_coerce_schema_version`` validator normalises
    both forms to ``int`` before validation so existing packs continue
    to parse unchanged (FR-001 / WP09 T053).
    """

    extends: str | None = None
    """Optional base pack name to extend (FR-001 / WP09 T054).

    When set, the pack inherits from the named base pack via the
    :func:`_resolve_chain` resolver.  ``None`` preserves the
    backward-compatible flat-union behaviour for packs that pre-date
    the extends mechanism.
    """

    org_name: str | None = None
    interview_defaults: dict[str, str | bool] = Field(default_factory=dict)
    required_directives: list[str] = Field(default_factory=list)
    required_tactics: list[str] = Field(default_factory=list)
    required_paradigms: list[str] = Field(default_factory=list)
    required_styleguides: list[str] = Field(default_factory=list)
    required_toolguides: list[str] = Field(default_factory=list)
    required_procedures: list[str] = Field(default_factory=list)
    required_agent_profiles: list[str] = Field(default_factory=list)
    required_mission_step_contracts: list[str] = Field(default_factory=list)
    required_glossary_packs: list[str] = Field(default_factory=list)
    required_assets: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    skill_namespace: str | None = None
    """Namespace prefix pack skills render under (``<namespace>-<id>``).

    Reserved built-in prefixes (``spk-``, ``spec-kitty-``, ``spec-kitty.``) are
    refused by the pack-skill validator; WP03 owns the activation semantics. The
    grammar is checked where a skill is rendered, not here, so a bad namespace never
    discards the pack's other policy.
    """
    governance_policies: list[GovernancePolicy] = Field(default_factory=list)
    activations: list[ActivationEntry] = Field(default_factory=list)
    """Org-pack-level activation registry (FR-008 / WP06 T028).  Each pack
    may ship its own activations list; the cross-pack merge concatenates
    them and deduplicates on the 4-tuple identity
    ``(activation_context, charter_pack_id, artifact_id, artifact_kind)``
    keeping the *last* occurrence (declaration-order precedence)."""

    @model_validator(mode="before")
    @classmethod
    def _reject_retired_fields(cls, data: object) -> object:
        """Reject a retired top-level field (scope ``SCOPE_ORG_CHARTER``) by name."""
        reject_retired_fields(data, scope=SCOPE_ORG_CHARTER, path=None)
        return data

    @field_validator("schema_version", mode="before")
    @classmethod
    def _coerce_schema_version(cls, v: object) -> int:
        """Coerce a string ``schema_version`` (e.g. ``"1"``) to ``int``.

        Backward-compat for org-charter YAML files written before WP09
        switched the field type from ``str`` to ``int``.  Non-numeric
        strings raise ``ValueError`` (surfaced as ``ValidationError``).
        """
        if isinstance(v, bool):
            # bool is a subclass of int; reject explicitly because a
            # boolean schema_version is never meaningful.
            raise ValueError("schema_version must be an integer, not bool")
        if isinstance(v, int):
            return v
        if isinstance(v, str):
            return int(v)
        raise ValueError(f"schema_version must be an int or numeric string, got {type(v).__name__}")


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class OrgCharterCycleError(Exception):
    """Raised when an ``extends:`` chain contains a cycle (FR-002 / WP09 T056).

    The full cycle path (including the repeated node) is preserved on
    :attr:`cycle_path` so callers can render an operator-friendly diagnostic.
    """

    def __init__(self, cycle_path: list[str]) -> None:
        self.cycle_path = list(cycle_path)
        super().__init__(f"Cycle detected in extends: chain: {' → '.join(self.cycle_path)}")


class OrgCharterExtensionError(Exception):
    """Raised when a named base pack is not present in the loaded pack set.

    FR-002 / WP09 T057: when a pack's ``extends:`` field names a pack that
    has not been loaded, the chain resolver fails loudly with the missing
    pack name and the chain walked so far.
    """

    def __init__(self, missing_pack: str, chain: list[str]) -> None:
        self.missing_pack = missing_pack
        self.chain = list(chain)
        super().__init__(f"Base pack '{missing_pack}' not found. Chain: {' → '.join(self.chain)}")


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def _yaml() -> YAML:
    y = YAML(typ="safe")
    return y


# ---------------------------------------------------------------------------
# T014 — org-required union into the project's activation source
#
# ``promote_activations`` (charter.activation.activation_engine) is the single
# append-only write path used below. It never resolves the effective set
# itself (C-008: it arrives as caller-supplied data), so this module asks the
# one public seam, ``charter.activation.effective_set`` (FR-015, #4400).
#
# consolidate-charter-bundle WP02: the write target itself (``config.yaml``
# vs the migrated ``charter.yaml``) is resolved by
# :func:`charter.activation.pack_manager.resolve_activation_write_target` — the single
# shared pointer-resolution implementation on the write side (INV-2/INV-5),
# so this module no longer maintains its own config-loading duplicate.
# ---------------------------------------------------------------------------


def _normalize_required_ids(
    kind_plural: str,
    raw_ids: list[str],
    *,
    offering_root: Path | None,
    org_roots: list[Path] | None = None,
    layer_roots: dict[str, Path] | None = None,
    warnings: list[str] | None = None,
) -> list[str]:
    """Normalize every id in *raw_ids* (a ``required_<kind_plural>`` list) to stem form.

    ``config.activated_<kind>`` stores config/file-stem ids and the
    derivation reads stems (:mod:`charter.activation.compiler`,
    :func:`~charter.activation.kind_vocabulary.resolve_artifact_urn`) — promoting an
    org-required id verbatim in its natural canonical form
    (e.g. ``DIRECTIVE_001``) writes a value the derivation can never match,
    historically crashing the compiled reference set (#2529). Declared
    directive IDs remain readable for recovery, but producers always write
    stems. An unavailable *offering_root* or unknown ID preserves the raw
    input for existing downstream validation. A known identity whose filenames
    select another directive raises instead; promotion callers may collect
    warnings and skip only that ambiguous identity.
    """
    if offering_root is None:
        return list(raw_ids)
    kind = ArtifactKind.from_plural(kind_plural)
    normalized: list[str] = []
    for raw_id in raw_ids:
        try:
            stem = resolve_selected_id_to_stem(
                kind,
                raw_id,
                offering_root=offering_root,
                org_roots=org_roots,
                layer_roots=layer_roots,
            )
        except UnrepresentableDirectiveIdError as exc:
            if warnings is None:
                raise
            warnings.append(f"Could not promote org-required directive {raw_id!r}; skipped. {exc}")
            continue
        normalized.append(stem if stem is not None else raw_id)
    return normalized


def _effective_sets_for_absent_keys(repo_root: Path, promotions: Mapping[str, list[str]], config_data: Mapping[str, Any]) -> dict[str, EffectiveSet]:
    """The effective set of every absent promoted key (FR-015, #4400).

    Activation keys resolve through the one public seam. A ``required_<kind>``
    whose key is not an activation key (``activated_assets``: the kind is not
    charter-activatable, so no activation filter reads the key) has nothing
    effective to preserve; it resolves to an empty set and is written as the
    org-required list, as before.
    """
    from charter.activation.effective_set import resolve_effective_sets
    from charter.activation.pack_manager import YAML_KEY_MAP

    absent = [key for key in promotions if config_data.get(key) is None]
    activation_keys = set(YAML_KEY_MAP.values())
    seam_keys = [key for key in absent if key in activation_keys]
    sets = resolve_effective_sets(repo_root, seam_keys) if seam_keys else {}
    for key in absent:
        if key not in activation_keys:
            sets[key] = EffectiveSet(kind=key.removeprefix("activated_"), yaml_key=key)
    return sets


def _promote_org_required_to_config(policy: OrgCharterPolicy, repo_root: Path) -> list[str]:
    """Union every ``required_<kind>`` in *policy* into ``config.activated_<kind>``.

    Mechanism note (squad finding): ``apply_org_charter_to_interview`` used to
    mutate only ``interview_data.selected_<kind>``, which fed the charter
    compiler before WP02. Once the compiler switched to reading
    ``config.activated_*`` exclusively (WP02, FR-003), that mutation became
    inert — org-required artefacts would silently stop reaching the compiled
    reference set. This promotes the SAME ids directly into
    ``.kittify/config.yaml`` through
    :func:`charter.activation.activation_engine.promote_activations`, the shared
    append-only primitive (WP06) — the only write path used here (no
    hand-rolled second writer, no direct ``save`` call).

    Id-form normalization (squad finding #2529): each ``required_<kind>`` id
    is normalized to config-stem form via :func:`_normalize_required_ids`
    before being handed to ``promote_activations`` — see that function's
    docstring. Resolving the doctrine root is best-effort: if it cannot be
    resolved (rare — a broken/uninstalled doctrine package), ids are
    promoted verbatim, matching this function's pre-fix behaviour rather
    than failing the whole (non-destructive, advisory) pre-fill flow.

    Only kinds with a non-empty ``required_<kind>`` are included in the
    promotion set (and never a kind that is in force by default while its key is
    absent -- see :data:`_INTERVIEW_SEEDED_KIND_FIELDS`), so kinds the org pack
    does not mandate are left in their
    existing three-state ``config.yaml`` shape — an absent key still means
    "all built-ins active" (:meth:`charter.activation.pack_context.PackContext.from_config`)
    for those kinds.

    Absent-key safety (FR-015, #4400): for a kind whose ``activated_<kind>``
    key is not yet present, the effective set is resolved through
    :func:`charter.activation.effective_set.resolve_effective_sets` and seeded
    before the org-required ids are appended, so nothing effective is lost.
    When that set cannot be resolved the key stays absent and a message names
    it; a bare restrictive list is never written.
    """
    from charter.activation.activation_engine import promote_activations
    from charter.activation.catalog import resolve_offering_root
    from charter.activation.pack_manager import resolve_activation_write_target

    target_path, config_data, save = resolve_activation_write_target(repo_root)
    # A kind that is in force by default is promoted only when the project
    # already lists it explicitly: an explicit list is exactly that list, so the
    # org-required ids must be unioned in. An absent key is never seeded.
    promotable = [kind for kind in REQUIRED_KIND_FIELDS if kind in _INTERVIEW_SEEDED_KIND_FIELDS or f"activated_{kind}" in config_data]
    required_by_kind: dict[str, list[str]] = {kind: list(getattr(policy, f"required_{kind}")) for kind in promotable if getattr(policy, f"required_{kind}")}
    if not required_by_kind:
        return []

    try:
        offering_root: Path | None = resolve_offering_root()
    except Exception:  # noqa: BLE001 — normalization is best-effort, see docstring
        offering_root = None

    from charter.activation.layer_roots import (
        resolve_layer_roots,
        resolve_org_root_chain,
    )

    org_roots = resolve_org_root_chain(repo_root)
    layer_roots = resolve_layer_roots(repo_root)
    warnings: list[str] = []
    promotions: dict[str, list[str]] = {
        f"activated_{kind}": _normalize_required_ids(
            kind,
            raw_ids,
            offering_root=offering_root,
            org_roots=org_roots,
            layer_roots=layer_roots,
            warnings=warnings,
        )
        for kind, raw_ids in required_by_kind.items()
    }

    outcome = promote_activations(
        promotions,
        config_path=target_path,
        config_data=config_data,
        save=save,
        effective_sets=_effective_sets_for_absent_keys(repo_root, promotions, config_data),
    )

    promoted = [f"Promoted {len(plan.activated)} org-required id(s) into {plan.yaml_key} (config-authority)." for plan in outcome.committed if plan.activated]
    return warnings + promoted + outcome.left_absent_messages()


def load_org_charter_policy(pack_path: Path) -> OrgCharterPolicy | None:
    """Load ``org-charter.yaml`` from a single pack root.

    Returns ``None`` when the file is absent or unreadable.  Raises
    :class:`pydantic.ValidationError` (re-raised) when the file exists but
    fails schema validation — callers that want resilience should catch.

    A retired field (#3732) raises
    :class:`~charter.offering.packs.retired_fields.RetiredPackFieldError`
    located at the ``org-charter.yaml`` path instead (code
    ``RETIRED_PACK_FIELD``, the field and its replacement). Callers that skip a
    malformed pack must re-raise it: dropping the pack would silently lose its
    required directives, policies and activations (fail closed, FR-003).
    """
    charter_path = pack_org_charter(pack_path)
    if not charter_path.exists():
        return None
    try:
        text = charter_path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.strip():
        return None
    try:
        data = _yaml().load(text)
    except Exception:  # noqa: BLE001 — YAML parse failures degrade to None
        return None
    if not isinstance(data, dict):
        return None
    try:
        return OrgCharterPolicy.model_validate(data)
    except ValidationError as exc:
        raise_retired_field_at(exc, charter_path)
        raise


def _build_pack_set(
    pack_context: PackContext,
) -> dict[str, OrgCharterPolicy]:
    """Scan ``pack_context.pack_roots`` for ``org-charter.yaml`` files.

    Returns a dict keyed by pack directory name (``pack_root.name``)
    mapping to the loaded :class:`OrgCharterPolicy`.  Roots that lack an
    ``org-charter.yaml`` or fail to parse are skipped (the loader returns
    ``None`` for both cases — malformed packs surface their own errors
    elsewhere in the pipeline).

    WP09 T062-chain: this helper replaces direct ``config.yaml`` reads
    inside :func:`_resolve_chain` whenever a :class:`PackContext` is
    supplied to :func:`load_org_charter_policies`.
    """
    pack_set: dict[str, OrgCharterPolicy] = {}
    for pack_root in pack_context.pack_roots:
        try:
            policy = load_org_charter_policy(pack_root)
        except RetiredPackFieldError:
            # Fail closed (FR-003, #3732): a retired field is operator-actionable;
            # skipping the pack would silently drop its whole policy.
            raise
        except Exception:  # noqa: BLE001, S112 — malformed pack policy is skipped
            continue
        if policy is None:
            continue
        pack_set[pack_root.name] = policy
    return pack_set


def _resolve_chain(
    pack_name: str,
    pack_set: dict[str, OrgCharterPolicy],
) -> list[OrgCharterPolicy]:
    """Resolve the ``extends:`` chain starting from ``pack_name``.

    Delegates the topology walk (cycle detection, missing-base detection,
    base-first ordering) to the canonical charter-layer resolver
    :func:`charter.offering.packs.extends.resolve_extends_order`. This module no longer
    maintains its own depth-first walk — per C-005 / R-10 there is a single
    ``extends:`` resolution mechanism, and the charter-layer functions are it
    (FR-008). This loader only maps the resolved order back to the loaded
    :class:`OrgCharterPolicy` objects and re-raises the charter-layer errors as
    the established ``OrgCharter*`` exceptions so existing callers/tests see an
    unchanged contract.

    Parameters
    ----------
    pack_name:
        Name of the overlay pack whose chain to resolve.  Must be a key
        in ``pack_set``.
    pack_set:
        Name-keyed dict of all loaded policies, typically produced by
        :func:`_build_pack_set`.

    Returns
    -------
    list[OrgCharterPolicy]
        Chain in resolution order, base first.

    Raises
    ------
    OrgCharterExtensionError
        When a pack's ``extends:`` field names a pack absent from
        ``pack_set``.
    OrgCharterCycleError
        When a cycle is detected (a pack already in the chain re-appears).
    """
    from charter.offering.packs.extends import (
        ExtendsBaseNotFoundError,
        ExtendsCycleError,
        resolve_extends_order,
    )

    extends_edges = {name: policy.extends for name, policy in pack_set.items()}
    try:
        order = resolve_extends_order(pack_name, extends_edges)
    except ExtendsCycleError as exc:
        raise OrgCharterCycleError(exc.cycle_path) from exc
    except ExtendsBaseNotFoundError as exc:
        raise OrgCharterExtensionError(exc.missing_base, exc.chain) from exc

    return [pack_set[name] for name in order]


def _fold_policies(
    policies: list[OrgCharterPolicy],
    *,
    strict_schema_version: bool = False,
) -> OrgCharterPolicy:
    """Fold a list of policies (declaration order) into one resolved policy.

    This is the single canonical merge-fold body extracted from the three
    historical hand-rolled copies (``_merge_chain``, the legacy
    ``load_org_charter_policies`` path, and the ``_load_with_pack_context``
    cross-pack fold).  See #1894.

    Fold semantics (identical across all callers):

    * ``required_<kind>`` (all 8) — **union**; later policies add, never
      remove.  Result preserves first-seen order.
    * ``interview_defaults`` — **per-key replacement** via ``dict.update``;
      later key wins; unmentioned earlier keys survive.
    * ``governance_policies`` — concatenated and deduplicated by
      ``(field, value)`` keeping the *last* occurrence.
    * ``activations`` — concatenated and deduplicated on the 4-tuple
      identity key keeping the *last* occurrence.
    * ``org_name`` — last non-empty value wins.
    * ``skill_namespace`` — last non-empty value wins.
    * ``extends`` — always ``None`` on the merged result (the merged policy
      is the resolved snapshot, not a chain link).

    ``schema_version`` handling is the one historical point of divergence
    and is parameterised by *strict_schema_version*:

    * ``True`` (the ``_merge_chain`` / extends-chain behaviour, WP09 T059):
      every policy in *policies* **must** share the same ``schema_version``;
      a mismatch raises ``ValueError`` with both versions surfaced.  The
      single shared version is carried onto the result.
    * ``False`` (the legacy ``config.yaml`` path and the cross-pack fold):
      **no mismatch check** — the last truthy ``schema_version`` wins, with
      a ``1`` fallback when none is truthy.

    NOTE (#1894): the lenient (``strict_schema_version=False``) branch is a
    LATENT inconsistency preserved deliberately — historically the legacy
    path None-guarded ``schema_version`` while ``_merge_chain`` enforced
    set-equality.  This extraction makes the delta an explicit parameter
    rather than silent drift; it does not "fix" the lenient semantics.
    """
    if not policies:
        return OrgCharterPolicy()

    resolved_schema_version = _resolve_fold_schema_version(policies, strict_schema_version=strict_schema_version)

    merged_interview_defaults: dict[str, str | bool] = {}
    merged_required: dict[str, list[str]] = {kind: [] for kind in REQUIRED_KIND_FIELDS}
    merged_governance: list[GovernancePolicy] = []
    activation_dedup: dict[tuple[str, str, str, str], ActivationEntry] = {}
    org_name: str | None = None
    skill_namespace: str | None = None

    for policy in policies:
        if policy.org_name:
            org_name = policy.org_name
        skill_namespace = last_non_empty_token(skill_namespace, policy.skill_namespace)
        # Per-key replacement: later key wins; earlier keys not overridden
        # remain in place.
        merged_interview_defaults.update(policy.interview_defaults)
        _accumulate_required(merged_required, policy)
        merged_governance.extend(policy.governance_policies)
        for entry in policy.activations:
            activation_dedup[_activation_identity_key(entry)] = entry

    return OrgCharterPolicy(
        schema_version=resolved_schema_version,
        extends=None,
        org_name=org_name,
        interview_defaults=merged_interview_defaults,
        required_directives=merged_required["directives"],
        required_tactics=merged_required["tactics"],
        required_paradigms=merged_required["paradigms"],
        required_styleguides=merged_required["styleguides"],
        required_toolguides=merged_required["toolguides"],
        required_procedures=merged_required["procedures"],
        required_agent_profiles=merged_required["agent_profiles"],
        required_mission_step_contracts=merged_required["mission_step_contracts"],
        required_glossary_packs=merged_required["glossary_packs"],
        required_assets=merged_required["assets"],
        required_skills=merged_required["skills"],
        skill_namespace=skill_namespace,
        governance_policies=_dedupe_governance(merged_governance),
        activations=list(activation_dedup.values()),
    )


def _resolve_fold_schema_version(policies: list[OrgCharterPolicy], *, strict_schema_version: bool) -> int:
    """Resolve the merged ``schema_version`` for a fold (see :func:`_fold_policies`)."""
    if strict_schema_version:
        # --- T059: schema_version must match across the chain -------------
        versions = {p.schema_version for p in policies}
        if len(versions) > 1 and not versions <= _CHAIN_COMPATIBLE_SCHEMA_VERSIONS:
            raise ValueError(
                f"schema_version mismatch in extends: chain. Versions found: {sorted(versions)}. All packs in a chain must share the same schema_version."
            )
        return max(versions)
    # Lenient: last truthy schema_version wins; 1 fallback (see NOTE).
    last_truthy: int | None = None
    for policy in policies:
        if policy.schema_version:
            last_truthy = policy.schema_version
    return last_truthy if last_truthy is not None else 1


def _accumulate_required(merged_required: dict[str, list[str]], policy: OrgCharterPolicy) -> None:
    """Union ``required_<kind>`` from *policy* into *merged_required* (first-seen order)."""
    for kind in REQUIRED_KIND_FIELDS:
        union_required_tokens(merged_required[kind], getattr(policy, f"required_{kind}"))


def _dedupe_governance(
    merged_governance: list[GovernancePolicy],
) -> list[GovernancePolicy]:
    """Dedupe governance policies by ``(field, value)``, keeping the LAST entry."""
    seen: dict[tuple[str, str | bool], GovernancePolicy] = {}
    for gp in merged_governance:
        seen[(gp.field, gp.value)] = gp
    return list(seen.values())


def _merge_chain(chain: list[OrgCharterPolicy]) -> OrgCharterPolicy:
    """Merge a base-first ``chain`` into a single resolved :class:`OrgCharterPolicy`.

    Thin wrapper over :func:`_fold_policies` with strict ``schema_version``
    matching (C-002 / WP09 T058-T059): every pack in an ``extends:`` chain
    must share the same ``schema_version``; a mismatch raises ``ValueError``.
    All other fold semantics are documented on :func:`_fold_policies`.
    """
    return _fold_policies(chain, strict_schema_version=True)


def load_org_charter_policies(
    repo_root: Path,
    pack_context: PackContext | None = None,
) -> OrgCharterPolicy:
    """Load and merge ``org-charter.yaml`` across all configured packs.

    Merge semantics (declaration order, last pack wins on collisions):

    * ``schema_version`` — last non-empty value wins.
    * ``org_name`` — last non-empty value wins.
    * ``interview_defaults`` — dict update; later packs overwrite earlier.
    * ``required_<kind>`` (every kind in :data:`REQUIRED_KIND_FIELDS`) — union,
      preserving first-seen order across packs.
    * ``governance_policies`` — concatenated, deduplicated by
      ``(field, value)`` keeping the *last* occurrence.
    * ``activations`` — concatenated, deduplicated on the 4-tuple
      ``(activation_context, charter_pack_id, artifact_id, artifact_kind)``
      keeping the *last* occurrence (per data-model.md §5 / FR-008).

    Returns an *empty* :class:`OrgCharterPolicy` (all defaults) when no
    packs are configured or none ship an ``org-charter.yaml``.

    Parameters
    ----------
    repo_root:
        Repository root containing ``.kittify/config.yaml``.
    pack_context:
        Optional pre-validated :class:`charter.activation.pack_context.PackContext`
        (FR-001 / WP09 T061-sig).  When supplied, pack discovery and
        ``extends:`` chain resolution use
        :attr:`PackContext.pack_roots` instead of reading
        ``.kittify/config.yaml`` directly.  Defaults to ``None`` for
        backward compatibility — callers migrate in WP10.
    """
    if pack_context is not None:
        return _load_with_pack_context(pack_context)

    registry = load_pack_registry(repo_root)
    if not registry.packs:
        return OrgCharterPolicy()

    from charter.offering.drg.org_pack_config import (
        OrgPackEnvVarUnsetError,
        OrgPackSubdirEscapeError,
    )

    policies: list[OrgCharterPolicy] = []
    for pack in registry.packs:
        try:
            policy = load_org_charter_policy(pack.effective_root(repo_root))
        except (OrgPackEnvVarUnsetError, OrgPackSubdirEscapeError, RetiredPackFieldError):
            # Fail closed (FR-003): an unset env var, a symlink-escape or a
            # retired field (#3732) is an operator-actionable config error,
            # not a malformed policy file — swallowing it here would silently
            # drop this pack's required directives/tactics/activations with
            # no signal.
            raise
        except Exception:  # noqa: BLE001, S112 — malformed pack policy is skipped
            continue
        if policy is None:
            continue
        policies.append(policy)

    # Legacy config.yaml path: lenient schema_version (last truthy wins).
    # See #1894 / _fold_policies NOTE for the historical strict-vs-lenient delta.
    return _fold_policies(policies, strict_schema_version=False)


def _load_with_pack_context(pack_context: PackContext) -> OrgCharterPolicy:
    """Load and merge org-charter policies via a :class:`PackContext`.

    Builds the pack set from ``pack_context.pack_roots``, then for each
    pack that declares ``extends:`` resolves and merges the chain.  Packs
    without ``extends:`` collapse into the flat-union path so callers
    that never adopt ``extends:`` see no behavioural change (FR-001 /
    WP09 T062-chain).

    The cross-pack merge then folds the per-pack resolved policies into a
    single :class:`OrgCharterPolicy` using the same union/per-key/dedup
    semantics as the legacy ``config.yaml`` path above.
    """
    pack_set = _build_pack_set(pack_context)
    if not pack_set:
        return OrgCharterPolicy()

    # Resolve each pack's chain.  Packs that act as a "base" for another
    # pack will be re-walked via that overlay's chain, but the merge
    # union semantics handle this idempotently.
    resolved_per_pack: list[OrgCharterPolicy] = []
    for pack_root in pack_context.pack_roots:
        name = pack_root.name
        if name not in pack_set:
            continue
        chain = _resolve_chain(name, pack_set)
        resolved_per_pack.append(_merge_chain(chain))

    # Cross-pack fold: union required_<kind>, per-key interview_defaults,
    # last non-empty org_name, dedup governance + activations.  Lenient
    # schema_version (last truthy wins) matches the legacy config.yaml path;
    # strict matching is already enforced per chain inside _merge_chain.
    # See #1894 / _fold_policies NOTE for the historical strict-vs-lenient delta.
    return _fold_policies(resolved_per_pack, strict_schema_version=False)


# ---------------------------------------------------------------------------
# Interview pre-fill
# ---------------------------------------------------------------------------


def _policy_has_any_required(policy: OrgCharterPolicy) -> bool:
    """Return True when *policy* declares at least one ``required_<kind>``."""
    return any(getattr(policy, f"required_{kind}") for kind in REQUIRED_KIND_FIELDS)


def apply_org_charter_pre_fill(repo_root: Path) -> list[str]:
    """Non-destructively pre-fill interview answers from org charter policies.

    Returns a list of human-readable messages describing what was
    pre-filled.  Returns an empty list when:

    * no org packs are configured;
    * none of the configured packs ship an ``org-charter.yaml``;
    * the merged policy has neither ``interview_defaults`` nor any
      ``required_<kind>`` lists to apply.

    The actual side-effect on ``answers.yaml`` is delegated to the
    ``charter`` layer (which cannot import ``specify_cli``) so the
    dependency direction is preserved.
    """
    from charter.activation.invocation_context import ProjectContext

    registry = load_pack_registry(repo_root)
    if not registry.packs:
        return []

    pack_context = None
    try:
        ctx = ProjectContext.from_repo(repo_root)
        pack_context = ctx.require_pack_context()
    except Exception:  # noqa: BLE001 — pack_context is best-effort
        pass

    merged_policy = load_org_charter_policies(repo_root, pack_context=pack_context)
    if not merged_policy.interview_defaults and not _policy_has_any_required(merged_policy):
        return []

    answers_path = repo_root / ".kittify" / "charter" / "interview" / "answers.yaml"

    # The pure data helper lives in the charter layer.
    from charter.activation.interview import apply_org_charter_pre_fill_to_answers

    result: list[str] = apply_org_charter_pre_fill_to_answers(
        answers_path=answers_path,
        interview_defaults=dict(merged_policy.interview_defaults),
        required_directives=list(merged_policy.required_directives),
    )
    return result


def apply_org_charter_to_interview(
    interview_data: Any,
    repo_root: Path,
    pack_context: PackContext | None = None,
) -> list[str]:
    """Pre-fill an in-memory ``CharterInterview`` with org charter defaults,
    and promote org-required artefacts to config-authority (T014).

    Mutates ``interview_data.answers`` and ``interview_data.selected_<kind>``
    in place for every kind in :data:`_INTERVIEW_SEEDED_KIND_FIELDS`, AND unions every
    ``required_<kind>`` into ``.kittify/config.yaml`` ``activated_<kind>`` via
    :func:`_promote_org_required_to_config`. Behaviour is non-destructive:

    * Sets a key in ``interview_data.answers`` only when it is missing,
      so the interactive prompt then shows the org default as its starting
      value and the operator can confirm or override it (FR-026).
    * Appends entries from each ``required_<kind>`` to
      ``interview_data.selected_<kind>`` only when not already present
      (union-preserving-first-seen-order). This mutation is now purely an
      interview-record / interactive-prompt convenience — the charter
      compiler reads ``config.activated_*`` exclusively (WP02, FR-003), so
      ``interview_data.selected_<kind>`` is inert for activation (SC-004).
    * Initialises ``selected_<kind>`` to an empty list when the interview
      object does not already declare the attribute — keeps pre-fill safe
      for legacy interview objects that predate the Mission B schema.
    * Appends the same ``required_<kind>`` ids into
      ``config.yaml``'s ``activated_<kind>`` (append-only, idempotent) so the
      artefacts the org pack mandates actually resolve in the compiled
      reference set — this is the channel that matters post-WP02.

    Returns a list of human-readable messages describing what was applied.
    Returns ``[]`` when no org packs are configured, none ship an
    ``org-charter.yaml``, or the merged policy contributes nothing.
    """

    registry = load_pack_registry(repo_root)
    if not registry.packs:
        return []

    merged_policy = load_org_charter_policies(repo_root, pack_context=pack_context)
    if not merged_policy.interview_defaults and not _policy_has_any_required(merged_policy):
        return []

    messages: list[str] = []

    prefilled = 0
    for key, value in merged_policy.interview_defaults.items():
        if key not in interview_data.answers:
            interview_data.answers[key] = str(value)
            prefilled += 1

    messages.extend(_promote_org_required_to_config(merged_policy, repo_root))

    for kind in _INTERVIEW_SEEDED_KIND_FIELDS:
        required_list: list[str] = list(getattr(merged_policy, f"required_{kind}"))
        if not required_list:
            continue
        # Initialise the selection attribute defensively — legacy interview
        # shapes may not declare every Mission-B-added selection field.
        if not hasattr(interview_data, f"selected_{kind}") or getattr(interview_data, f"selected_{kind}") is None:
            try:
                setattr(interview_data, f"selected_{kind}", [])
            except (AttributeError, TypeError):
                # Frozen dataclass that refuses re-binding; skip this kind.
                continue
        selected_list = getattr(interview_data, f"selected_{kind}")
        new_required = [d for d in required_list if d not in selected_list]
        if new_required:
            selected_list.extend(new_required)
            label = "directive(s)" if kind == "directives" else f"{kind}"
            messages.append(f"Pre-selected {len(new_required)} {label} from org charter required_{kind}.")

    if prefilled:
        messages.append(f"Pre-filled {prefilled} interview default(s) from org charter.")

    return messages


# ---------------------------------------------------------------------------
# JSON block helper (consumed by org_charter_loader)
# ---------------------------------------------------------------------------


def validate_org_required_directive_stems(repo_root: Path) -> None:
    """Reject ambiguous mandatory directives before charter/config writes.

    Interview promotion is advisory and can preserve valid siblings while
    reporting skipped identities. Generation rechecks current org policy so
    required ambiguity cannot disappear behind an earlier warning. Input reads
    may still append encoding-provenance ledger entries. Unknown-ID validation
    retains its existing path.
    """
    from charter.activation.catalog import resolve_offering_root

    from charter.activation.layer_roots import resolve_layer_roots, resolve_org_root_chain

    policy = load_org_charter_policies(repo_root)
    if policy.required_directives:
        _normalize_required_ids(
            "directives",
            list(policy.required_directives),
            offering_root=resolve_offering_root(),
            org_roots=resolve_org_root_chain(repo_root),
            layer_roots=resolve_layer_roots(repo_root),
        )


# ---------------------------------------------------------------------------
# Pack tooling org-charter legs (research A.3 #4)
#
# ``validate_pack`` and ``assemble_pack`` live in the offering tier and take
# their org-charter leg as a hook, because org charter composition is an
# activation concern. The two composing entries below are the doors every
# caller uses, so no caller can skip the org-charter leg.
# ---------------------------------------------------------------------------


def _load_charter_mapping(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Parse *path* as a YAML mapping. Returns ``(data, error_msg)``."""
    try:
        data = _yaml().load(path)
    except (YAMLError, OSError) as exc:
        return None, f"YAML parse error: {exc}"
    if data is None:
        return None, "empty YAML document"
    if not isinstance(data, dict):
        return None, "expected a YAML mapping at top level"
    return data, None


def _org_charter_issue(path: Path, message: str, *, severity: str, artifact_id: str | None = None) -> ValidationIssue:
    return ValidationIssue(
        severity=severity,
        artifact_type="org-charter",
        artifact_id=artifact_id,
        file=str(path),
        message=message,
    )


def _schema_failure_issues(path: Path, exc: ValidationError) -> list[ValidationIssue]:
    """Map a schema failure to issues: a retired field is named, anything else is generic."""
    retired = retired_field_errors(exc)
    if retired:
        return [
            ValidationIssue(
                severity="error",
                artifact_type="org-charter",
                artifact_id=error.field,
                file=str(path),
                message=f"{RETIRED_PACK_FIELD}: {error.at(path)}",
                category=RETIRED_PACK_FIELD,
            )
            for error in retired
        ]
    return [_org_charter_issue(path, f"org-charter schema validation failed: {exc.errors()[0].get('msg', exc)}", severity="error")]


def validate_org_charter_file(path: Path, pack_directive_ids: AbstractSet[str] = frozenset()) -> list[ValidationIssue]:
    """Validate one pack's ``org-charter.yaml`` (the ``validate_pack`` org-charter leg).

    A parse or schema failure is an error; a non-advisory governance
    enforcement and a ``required_directives`` id the pack does not ship
    (*pack_directive_ids*) are advisories.
    """
    data, parse_err = _load_charter_mapping(path)
    if parse_err is not None or data is None:
        return [_org_charter_issue(path, parse_err or "empty YAML document", severity="error")]
    try:
        policy = OrgCharterPolicy.model_validate(data)
    except ValidationError as exc:
        return _schema_failure_issues(path, exc)

    issues: list[ValidationIssue] = []
    for gp in policy.governance_policies:
        if str(gp.enforcement) != "advisory":
            issues.append(
                _org_charter_issue(
                    path,
                    f"governance policy uses non-advisory enforcement {gp.enforcement!r}; only 'advisory' is recognised today",
                    severity="advisory",
                    artifact_id=gp.field,
                )
            )
    for required_id in policy.required_directives:
        if required_id not in pack_directive_ids:
            issues.append(
                _org_charter_issue(
                    path,
                    f"required_directive {required_id!r} not found in this pack's directives/ (may exist in another pack or in built-in doctrine)",
                    severity="advisory",
                    artifact_id=required_id,
                )
            )
    return issues


def merge_org_charter_files(paths: Sequence[Path], output_dir: Path) -> None:
    """Merge input packs' ``org-charter.yaml`` files into ``output_dir`` (the ``assemble_pack`` leg).

    Merge semantics:

    * ``interview_defaults``: dict update (last pack wins on key collision).
    * ``required_directives``: union, deduplicated, order preserved.
    * ``governance_policies``: concatenated, deduplicated by ``(field, value)``.

    Unreadable or non-mapping inputs are skipped; a merged payload that fails
    the schema writes nothing, and the assembled pack's own validation then
    reports the inputs.
    """
    merged = _merge_org_charter_payloads(paths)
    if merged is None:
        return
    pack_org_charter(output_dir).write_text(
        pyyaml.safe_dump(merged.model_dump(mode="json"), sort_keys=False),
        encoding="utf-8",
    )


def _merge_org_charter_payloads(paths: Sequence[Path]) -> OrgCharterPolicy | None:
    interview_defaults: dict[str, Any] = {}
    required_directives: list[str] = []
    governance_policies: list[dict[str, Any]] = []
    schema_version: str | None = None

    for path in paths:
        data, _err = _load_charter_mapping(path)
        if data is None:
            continue
        schema_version = data.get("schema_version", schema_version)
        interview_defaults.update(data.get("interview_defaults") or {})
        for rd in data.get("required_directives") or []:
            if rd not in required_directives:
                required_directives.append(rd)
        governance_policies.extend(gp for gp in data.get("governance_policies") or [] if isinstance(gp, dict))

    seen: set[tuple[Any, Any]] = set()
    deduped: list[dict[str, Any]] = []
    for gp in governance_policies:
        key = (gp.get("field"), gp.get("value"))
        if key not in seen:
            seen.add(key)
            deduped.append(gp)

    payload: dict[str, Any] = {
        "schema_version": schema_version or "1.0",
        "interview_defaults": interview_defaults,
        "required_directives": required_directives,
        "governance_policies": deduped,
    }
    try:
        return OrgCharterPolicy.model_validate(payload)
    except ValidationError:
        return None


def validate_pack_with_org_charter(pack_dir: Path, *, check_drg_root: bool = True) -> ValidationResult:
    """Validate a pack including its org-charter leg (the CLI's validation door)."""
    return validate_pack(pack_dir, check_drg_root=check_drg_root, org_charter_check=validate_org_charter_file)


def assemble_pack_with_org_charter(
    input_packs: list[Path],
    output_dir: Path,
    *,
    force: bool = False,
    conflicts_out: Path | None = None,
) -> AssemblyResult:
    """Assemble packs including the org-charter merge and validation legs (the CLI's door)."""
    return assemble_pack(
        input_packs,
        output_dir,
        force=force,
        conflicts_out=conflicts_out,
        org_charter_merge=merge_org_charter_files,
        org_charter_check=validate_org_charter_file,
    )
