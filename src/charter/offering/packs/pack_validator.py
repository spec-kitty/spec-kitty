"""Pack-layout validation for org doctrine packs.

See ``kitty-specs/layered-doctrine-org-layer-01KRNPEE/contracts/pack-layout.md``
for the normative contract enforced here.

Validation performs (in order):

1. **Directory existence**.
2. **Per-artifact schema validation** against the relevant Pydantic model.
3. **ID uniqueness** within each artifact type directory.
4. **DRG extension validation** when ``drg/`` is present: every URN referenced
   by a fragment edge must resolve to a node in ``built-in ∪ pack-artifacts``
   and no extension may modify an existing built-in node's ``kind``.
5. **Intent-aware collision checks** (FR-011..FR-013, mission
   ``charter-ux-and-org-pack-vocabulary-01KSAF14``): consult each pack
   artifact's ``enhances`` / ``overrides`` fields and emit one of the
   following categories per the precedence table in
   ``kitty-specs/charter-ux-and-org-pack-vocabulary-01KSAF14/contracts/pack-validator-advisory.md``:

   * ``intent_conflict`` ERROR — both fields declared.
   * ``unknown_target`` ERROR — declared target ID is not a built-in.
   * ``same_id_collision`` ADVISORY (reworded) — same-ID collision with no declared intent.

6. **Optional duplicate DRG edge advisories**.
7. **ASSET sidecar manifest safety checks** when an ``assets/`` directory is
   present: path containment (``asset_path_escape``) and mime/extension
   consistency (``asset_mime_invalid``). This is a loose-contract kind —
   the referenced blob is never scanned, only its ``*.asset.yaml`` sidecar
   manifest is, and cross-pack id-uniqueness is intentionally NOT enforced
   here (see WP03's merge scan).
8. **Org-pack validation through the runtime loader** (#4189, #4200): when
   ``drg/fragment.yaml`` exists the whole pack is loaded through
   :func:`charter.offering.drg.org_pack_loader.load_org_pack` (single schema
   authority); when it does not, any ``mission_types/*/governance-profile.yaml``
   is still validated through the loader's own collector so a CLI-green pack
   cannot crash the runtime loader later. Faults are attributed to the file
   they actually live in (``source_file``), and an unreadable fragment is an
   I/O finding, not a masked YAML parse error.
9. **Optional org-charter.yaml validation** through the caller-supplied
   :data:`OrgCharterCheck` hook (org charter composition is an activation
   concern); a pack that ships ``org-charter.yaml`` with no hook supplied gets
   an ``org_charter_unchecked`` error, never a silent skip.

Issue ``category`` values surfaced via ``ValidationIssue.category``:
``schema_invalid``, ``duplicate_id``, ``drg_dangling_edge``, ``drg_kind_drift``,
``duplicate_drg_edge``, ``same_id_collision``, ``unknown_target``,
``intent_conflict``, ``asset_path_escape``, ``asset_mime_invalid``,
``profile_skipped``, ``org_pack_missing``, ``unreadable_file``,
``pack_sanction``, plus
structural categories for the ``pack`` and ``org-charter`` artifact types.

The exported entry points are intentionally small:

* :func:`validate_pack`
* :func:`render_validation_result`

ValidationIssue and ValidationResult are module-local records used to build,
return, and render findings. Their types and direct module access are unchanged.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

__all__ = [
    "OrgCharterCheck",
    "ValidationIssue",
    "ValidationResult",
    "artifact_schema_registry",
    "validate_pack",
    "render_validation_result",
]


# ---------------------------------------------------------------------------
# Plural artifact kinds that carry the augmentation vocabulary.
#
# FR-030 single-source: derived from
# ``charter.offering.drg.org_pack_loader.augmentation_plural_kinds()`` rather than a
# second hand-synced table. Adding an augmentation-eligible kind is a one-line
# change at that single source and both the loader auto-emitter and this
# validator pick it up. Coverage is the full augmentation-eligible set:
# the original five (tactics, styleguides, paradigms, procedures,
# agent_profiles) plus the newly-covered kinds (directives, toolguides,
# mission_step_contracts, mission_types — FR-028, FR-032).
# ---------------------------------------------------------------------------

from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.packs.pack_descriptor import load_pack_descriptor
from charter.offering.packs.retired_fields import RETIRED_PACK_FIELD, RetiredPackFieldError
from charter.offering.drg.merge import _EndpointResolutionError, _resolve_edge_endpoint
from charter.offering.drg.override_policy import (
    PACK_POLICY_FILENAME,
    OverridePolicyError,
    load_pack_sanction,
    pack_sanction_present,
    sanction_reason_missing,
)
from charter.offering.drg.org_pack_loader import (
    ORG_PLURAL_TO_SINGULAR_KIND,
    OrgPackMissingError,
    OrgPackParseError,
    OrgPackSchemaError,
    augmentation_plural_kinds,
    load_org_pack,
)
from charter.offering.drg.migration.id_normalizer import normalize_directive_id
from charter.offering.pack_paths import BuiltInContentDirNotAvailable, PackRootNotFound, built_in_dir
from charter.offering.packs.presets import (
    ACTIVATED_KINDS_KEY,
    MISSION_TYPE_ACTIVATIONS_KEY,
    ActivationPreset,
    PresetFormatError,
    kind_gate_omissions,
    load_preset_file,
    preset_activation_key,
    preset_files,
)
from kernel.charter_pack_paths import pack_drg_fragment, pack_org_charter

_AUGMENTATION_PLURAL_KINDS: frozenset[str] = augmentation_plural_kinds()
FragmentIntent = dict[str, dict[str, tuple[dict[str, str], Path]]]


# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------


@dataclass
class ValidationIssue:
    """A single issue surfaced by :func:`validate_pack`.

    The ``category`` field classifies the issue (FR-012, FR-013 — mission
    ``charter-ux-and-org-pack-vocabulary-01KSAF14``). Valid values:

    * ``schema_invalid`` — schema validation error.
    * ``duplicate_id`` — two artifacts share the same ID within a kind.
    * ``drg_dangling_edge`` — a fragment edge references an unknown URN.
    * ``drg_kind_drift`` — a fragment attempts to change a built-in node's kind.
    * ``duplicate_drg_edge`` — same edge declared in two fragments.
    * ``same_id_collision`` — pack ID matches a built-in with no declared intent.
    * ``unknown_target`` — declared ``enhances`` / ``overrides`` target is not a built-in.
    * ``intent_conflict`` — both ``enhances`` and ``overrides`` declared on one artifact.
    * ``asset_path_escape`` — an ASSET manifest's ``path`` resolves outside the
      pack's ``assets/`` root (absolute, ``..``-escape, or symlink escape).
    * ``asset_mime_invalid`` — an ASSET manifest's ``mime`` is not a well-formed
      ``type/subtype`` value, or disagrees with the path extension's guessed type.
    * ``profile_skipped`` — an agent-profile file was recorded by
      ``AgentProfileRepository`` as skipped (e.g. a post-merge field-conflict
      failure), surfaced here so ``pack validate`` reports it without a
      separate ``spec-kitty doctor doctrine --json`` invocation.
    * ``drg_root_graph_missing`` — the pack's ``drg/`` directory contains one
      or more ``*.graph.yaml`` fragments but the pack has no top-level
      ``*.graph.yaml`` **and** no ``drg/fragment.yaml`` — the runtime
      (``src/charter/activation/_drg_helpers.py:load_validated_graph``) reads pack-root
      ``*.graph.yaml`` and ``drg/fragment.yaml``, so a ``drg/*.graph.yaml``
      graph fragment is the one DRG shape no runtime path consumes.
    * ``org_pack_missing`` — the runtime org-pack loader reported a missing
      referenced pack/artifact (:class:`OrgPackMissingError`) — a missing
      thing, not a parse fault (#4200).
    * ``unreadable_file`` — an org-pack file exists but cannot be read
      (``OSError``: permissions, or the path is a directory) — an I/O fault,
      never a masked YAML parse error (#4200).
    * ``preset_format`` — a ``presets/<name>.yaml`` file is malformed (the
      message names the field).
    * ``preset_unresolved_id`` — a preset lists an id the offering does not
      ship (the message names the file and the id).
    * ``preset_kind_gate`` — a preset's ``activated_kinds`` omits a kind it
      lists ids for.
    * ``not_found`` / ``parse_error`` / ``advisory`` — structural categories.
    """

    severity: str  # "error" | "advisory"
    artifact_type: str  # "directives", "drg", "org-charter", ...
    artifact_id: str | None
    file: str
    message: str
    category: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "severity": self.severity,
            "artifact_type": self.artifact_type,
            "artifact_id": self.artifact_id,
            "file": self.file,
            "message": self.message,
        }
        if self.category is not None:
            payload["category"] = self.category
        return payload


@dataclass
class ValidationResult:
    """Aggregate outcome of pack validation."""

    ok: bool
    errors: list[ValidationIssue] = field(default_factory=list)
    advisories: list[ValidationIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "errors": [issue.to_dict() for issue in self.errors],
            "advisories": [issue.to_dict() for issue in self.advisories],
        }


# ---------------------------------------------------------------------------
# Artifact-type registry
# ---------------------------------------------------------------------------


def artifact_schema_registry() -> dict[str, tuple[str, type[BaseModel]]]:
    """Map plural directory name → ``(glob_pattern, pydantic_model)``.

    Imported lazily to avoid loading the heavy doctrine package at module
    import time (keeps ``--help`` snappy).
    """
    from charter.offering.agent_profiles.profile import AgentProfile
    from charter.offering.assets.models import AssetManifest
    from charter.offering.directives.models import Directive
    from charter.offering.missions.step_contracts import MissionStepContract
    from charter.offering.paradigms.models import Paradigm
    from charter.offering.procedures.models import Procedure
    from charter.offering.styleguides.models import Styleguide
    from charter.offering.tactics.models import Tactic
    from charter.offering.toolguides.models import Toolguide

    # Only the schema model is curated per kind; the directory plural and the
    # file glob come from ArtifactKind (#5538).
    models: dict[ArtifactKind, type[BaseModel]] = {
        ArtifactKind.DIRECTIVE: Directive,
        ArtifactKind.TACTIC: Tactic,
        ArtifactKind.STYLEGUIDE: Styleguide,
        ArtifactKind.TOOLGUIDE: Toolguide,
        ArtifactKind.PARADIGM: Paradigm,
        ArtifactKind.PROCEDURE: Procedure,
        ArtifactKind.AGENT_PROFILE: AgentProfile,
        ArtifactKind.MISSION_STEP_CONTRACT: MissionStepContract,
        # ASSET is a loose-contract kind (FR-005/FR-011): the manifest is the
        # validated surface, the referenced blob itself is never scanned.
        # There is deliberately no "skip the blob schema" branch — the glob
        # only ever targets the sidecar `*.asset.yaml`, so this manifest is
        # validated exactly like the other nine kinds' YAML. The additional
        # containment/mime safety checks live in a separate pass
        # (_validate_asset_manifests), not here.
        ArtifactKind.ASSET: AssetManifest,
    }
    return {kind.plural: (kind.glob_pattern, model) for kind, model in models.items()}


# ---------------------------------------------------------------------------
# YAML helpers
# ---------------------------------------------------------------------------


def _yaml_parser() -> YAML:
    return YAML(typ="safe")


def _scan_files(directory: Path, glob: str) -> list[Path]:
    """Return sorted files matching *glob*; recursive for styleguides and assets."""
    if directory.name in {"styleguides", "assets"}:
        return sorted(directory.rglob(glob))
    return sorted(directory.glob(glob))


def _safe_load(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Parse *path* as YAML.  Returns ``(data, error_msg)``."""
    try:
        data = _yaml_parser().load(path)
    except (YAMLError, OSError) as exc:
        return None, f"YAML parse error: {exc}"
    if data is None:
        return None, "empty YAML document"
    if not isinstance(data, dict):
        return None, "expected a YAML mapping at top level"
    return data, None


# ---------------------------------------------------------------------------
# Per-directory artifact scan (extracted to keep ``validate_pack`` simple)
# ---------------------------------------------------------------------------


def _scan_artifact_directory(  # noqa: PLR0913 — small helper kept private to this module
    *,
    plural: str,
    type_dir: Path,
    glob: str,
    schema_cls: type[BaseModel],
    errors: list[ValidationIssue],
    pack_artifact_urns: set[str],
    pack_artifact_ids_per_type: dict[str, set[str]],
    pack_artifacts_data: dict[str, dict[str, tuple[dict[str, Any], Path]]],
) -> None:
    """Walk one artifact-type directory and update the shared collectors.

    Side-effects only: appends to ``errors``, mutates the URN /
    ID-per-type / raw-data collectors. Extracted from
    :func:`validate_pack` so the entry point stays under ruff's C901 limit.
    """
    seen_ids: dict[str, Path] = {}
    for yaml_file in _scan_files(type_dir, glob):
        data, parse_err = _safe_load(yaml_file)
        if parse_err is not None:
            errors.append(
                ValidationIssue(
                    severity="error",
                    artifact_type=plural,
                    artifact_id=None,
                    file=str(yaml_file),
                    message=parse_err,
                    category="parse_error",
                )
            )
            continue
        assert data is not None  # mypy
        artifact_id = data.get("id")
        # FR-011 (WP06): when both `overrides` and `enhances` are declared
        # in the raw YAML, route the issue through the intent-aware pass
        # (it emits `intent_conflict`) instead of the generic
        # `schema_invalid` from the Pydantic cross-field validator.
        both_intent_fields_set = (
            isinstance(data.get("overrides"), str) and bool(data.get("overrides")) and isinstance(data.get("enhances"), str) and bool(data.get("enhances"))
        )
        if isinstance(artifact_id, str) and artifact_id and plural in _AUGMENTATION_PLURAL_KINDS:
            pack_artifacts_data.setdefault(plural, {}).setdefault(artifact_id, (data, yaml_file))
            if both_intent_fields_set:
                # The intent-aware pass owns the error. Track the ID so
                # downstream checks still see it as a known artifact.
                pack_artifact_ids_per_type.setdefault(plural, set()).add(artifact_id)
                seen_ids[artifact_id] = yaml_file
                urn_kind = _plural_to_urn_kind(plural)
                if urn_kind is not None:
                    pack_artifact_urns.add(f"{urn_kind}:{artifact_id}")
                continue
        try:
            schema_cls.model_validate(data)
        except ValidationError as exc:
            errors.append(
                ValidationIssue(
                    severity="error",
                    artifact_type=plural,
                    artifact_id=str(artifact_id) if artifact_id else None,
                    file=str(yaml_file),
                    message=(f"schema validation failed: {exc.errors()[0].get('msg', exc)}"),
                    category="schema_invalid",
                )
            )
            continue
        if not isinstance(artifact_id, str) or not artifact_id:
            # Defensive guard: schema enforces non-empty string ids.
            continue
        if artifact_id in seen_ids:
            errors.append(
                ValidationIssue(
                    severity="error",
                    artifact_type=plural,
                    artifact_id=artifact_id,
                    file=str(yaml_file),
                    message=(f"duplicate id '{artifact_id}' (also defined in {seen_ids[artifact_id].name})"),
                    category="duplicate_id",
                )
            )
            continue
        seen_ids[artifact_id] = yaml_file
        pack_artifact_ids_per_type.setdefault(plural, set()).add(artifact_id)
        pack_artifacts_data.setdefault(plural, {}).setdefault(artifact_id, (data, yaml_file))
        urn_kind = _plural_to_urn_kind(plural)
        if urn_kind is not None:
            pack_artifact_urns.add(f"{urn_kind}:{artifact_id}")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def validate_pack(
    pack_dir: Path,
    *,
    check_drg_root: bool = True,
    org_charter_check: OrgCharterCheck | None = None,
) -> ValidationResult:
    """Validate a doctrine pack directory.

    Returns a :class:`ValidationResult` with ``ok=False`` if any error was
    found.  Advisories do not affect ``ok``.

    ``check_drg_root`` (FR-004, default ``True``): when ``True``, also runs
    :func:`_check_drg_root_graph_missing` — a pack whose DRG content lives
    only under ``drg/*.graph.yaml`` fragments with no pack-root
    ``*.graph.yaml`` and no ``drg/fragment.yaml`` is flagged, since the runtime
    (``src/charter/activation/_drg_helpers.py:load_validated_graph``) reads pack-root
    ``*.graph.yaml`` and ``drg/fragment.yaml`` but never ``drg/*.graph.yaml``.
    Callers that know their own output can never produce that mismatch shape
    (e.g. ``pack_assembler.assemble_pack``'s internal round-trip check) pass
    ``check_drg_root=False``.

    ``org_charter_check``: the org-charter leg (see :data:`OrgCharterCheck`).
    When the pack ships ``org-charter.yaml`` and no check is supplied, an
    ``org_charter_unchecked`` error is recorded instead of skipping the leg.
    """
    errors: list[ValidationIssue] = []
    advisories: list[ValidationIssue] = []

    if not pack_dir.exists() or not pack_dir.is_dir():
        errors.append(
            ValidationIssue(
                severity="error",
                artifact_type="pack",
                artifact_id=None,
                file=str(pack_dir),
                message=f"pack directory not found: {pack_dir}",
                category="not_found",
            )
        )
        return ValidationResult(ok=False, errors=errors, advisories=advisories)

    registry = artifact_schema_registry()

    # Collect all artifact IDs present in this pack (used by DRG and advisory).
    pack_artifact_urns: set[str] = set()
    pack_artifact_ids_per_type: dict[str, set[str]] = {}
    # Capture raw per-artifact YAML data keyed by ``(plural, id) -> (data, file)``
    # so the intent-aware collision pass can inspect ``enhances`` / ``overrides``
    # fields (FR-011..FR-013, WP06 T037).
    pack_artifacts_data: dict[str, dict[str, tuple[dict[str, Any], Path]]] = {}

    for plural, (glob, schema_cls) in registry.items():
        type_dir = pack_dir / plural
        if not type_dir.is_dir():
            continue
        _scan_artifact_directory(
            plural=plural,
            type_dir=type_dir,
            glob=glob,
            schema_cls=schema_cls,
            errors=errors,
            pack_artifact_urns=pack_artifact_urns,
            pack_artifact_ids_per_type=pack_artifact_ids_per_type,
            pack_artifacts_data=pack_artifacts_data,
        )

    # FR-002: surface AgentProfileRepository's post-merge profile-skip
    # diagnostics inline, deduplicated against files the generic scan above
    # already flagged schema_invalid.
    already_flagged_files = {issue.file for issue in errors if issue.artifact_type == "agent_profiles"}
    errors.extend(_check_profile_skipped_diagnostics(pack_dir, already_flagged_files))

    errors.extend(_validate_org_fragment(pack_dir))

    # DRG validation (only if drg/ exists).
    drg_dir = pack_dir / "drg"
    if drg_dir.is_dir():
        drg_errors, drg_advisories = _validate_drg(drg_dir, pack_artifact_urns)
        errors.extend(drg_errors)
        advisories.extend(drg_advisories)

    # FR-004: warn when DRG content lives only under drg/*.graph.yaml with
    # no pack-root graph — the shape the runtime never reads. Additive and
    # independent of _validate_drg's fragment-content checks above.
    if check_drg_root:
        errors.extend(_check_drg_root_graph_missing(pack_dir, drg_dir))

    # ASSET sidecar safety checks (T015): a separate pass mirroring the DRG
    # seam above, NOT inlined in the branchy _scan_artifact_directory loop.
    # Only manifests that already passed the generic schema scan (recorded
    # in pack_artifacts_data) are checked here — malformed manifests were
    # already flagged as schema_invalid by that scan. Does NOT enforce
    # global id-uniqueness across packs (WP03's merge scan owns that).
    asset_errors, asset_advisories = _validate_asset_manifests(pack_dir, pack_artifacts_data.get("assets", {}))
    errors.extend(asset_errors)
    advisories.extend(asset_advisories)

    # FR-011..FR-013 (WP06 T037): intent-aware collision messages. This replaces
    # the legacy unconditional ``_built_in_id_collision_advisories`` pass.
    # FR-028 hard cutover retired ``enhances``/``overrides`` inline fields on
    # tactics and styleguides.  Pre-collect DRG fragment intent so the
    # field-based pass can suppress same-ID advisories for artifacts whose
    # intent is declared via DRG edges instead of inline fields.
    built_in_ids_per_kind = _load_built_in_ids_per_kind()
    fragment_intent: FragmentIntent = {}
    if drg_dir.is_dir():
        fragment_intent = _collect_fragment_edge_intent(drg_dir)
    intent_errors, intent_advisories = _intent_aware_collision_messages(
        pack_artifacts_data,
        built_in_ids_per_kind,
        fragment_intent=fragment_intent,
    )
    errors.extend(intent_errors)
    advisories.extend(intent_advisories)

    # FR-031 (T016): apply the SAME intent-aware precedence to augmentation
    # relationships authored as DRG **fragment edges** — the authoring surface
    # for the newly-covered kinds (directives, toolguides, mission step
    # contracts, mission types), which under the locked fragment-only model
    # (data-model §3) cannot carry the legacy ``enhances`` / ``overrides``
    # fields. Reading fragment edges gives the new kinds parity with the
    # original five: declared intent suppresses the same-ID advisory, an
    # unknown target hard-errors, and both relations on one source ->
    # ``intent_conflict``.
    if drg_dir.is_dir():
        frag_errors, frag_advisories = _intent_aware_collision_messages_from_edges(
            fragment_intent,
            built_in_ids_per_kind,
            pack_artifacts_data,
        )
        errors.extend(frag_errors)
        advisories.extend(frag_advisories)

    # FR-014 (#5767): a pack-root replaceable-builtins.yaml is parsed by the
    # single sanction parser so a broken file never ships.
    if pack_sanction_present(pack_dir):
        sanction_errors, sanction_advisories = _validate_pack_sanction(pack_dir, _built_in_node_urns())
        errors.extend(sanction_errors)
        advisories.extend(sanction_advisories)

    # The authored pack.yaml descriptor (a retired field is RETIRED_PACK_FIELD, #3732).
    errors.extend(_validate_pack_descriptor(pack_dir))

    # FR-019: activation presets under presets/ (format, id resolution, kind gate).
    errors.extend(_validate_presets(pack_dir))

    # T044: the optional org-charter.yaml leg runs through the caller's hook;
    # without one, an org-charter.yaml is an explicit error, never skipped.
    advisories_or_errors = _check_org_charter(pack_dir, pack_artifact_ids_per_type.get("directives", set()), org_charter_check)
    for issue in advisories_or_errors:
        if issue.severity == "error":
            errors.append(issue)
        else:
            advisories.append(issue)

    return ValidationResult(
        ok=len(errors) == 0,
        errors=errors,
        advisories=advisories,
    )


# ---------------------------------------------------------------------------
# Activation presets (FR-019)
# ---------------------------------------------------------------------------

#: ``artifact_type`` of every preset finding.
_PRESET_ARTIFACT_TYPE = "preset"
_MISSION_TYPE_URN_KIND = "mission_type"


def _canonical_urn(urn_kind: str, artifact_id: str) -> str:
    """Return ``<kind>:<id>`` with a directive id in its canonical ``DIRECTIVE_NNN`` form."""
    if urn_kind == ArtifactKind.DIRECTIVE.value:
        return f"{urn_kind}:{normalize_directive_id(artifact_id)}"
    return f"{urn_kind}:{artifact_id}"


def _preset_offering_urns(pack_dir: Path) -> frozenset[str]:
    """Return the URNs a preset id may resolve to: built-in plus the pack's own nodes.

    A pack's ``parent_pack`` ancestors are not consulted: a bare pack directory
    does not say where its ancestors live, so an id that only an ancestor ships
    is reported unresolved (recorded decision, WP07 T038).
    """
    known = set(_built_in_node_urns()) | set(_pack_node_urns(pack_dir) or frozenset())
    canonical: set[str] = set()
    for urn in known:
        urn_kind, _, artifact_id = urn.partition(":")
        canonical.add(_canonical_urn(urn_kind, artifact_id))
    return frozenset(canonical)


def _preset_issue(path: Path, message: str, category: str) -> ValidationIssue:
    return ValidationIssue(
        severity="error",
        artifact_type=_PRESET_ARTIFACT_TYPE,
        artifact_id=path.stem,
        file=str(path),
        message=message,
        category=category,
    )


def _unresolved_preset_ids(preset: ActivationPreset, known_urns: AbstractSet[str]) -> list[tuple[str, str]]:
    """Return ``(key, id)`` for every id of *preset* outside *known_urns*."""
    listed: list[tuple[str, str, str]] = [
        (preset_activation_key(kind), kind.value, artifact_id) for kind in preset.listed_kinds() for artifact_id in preset.activations[preset_activation_key(kind)]
    ]
    listed.extend((MISSION_TYPE_ACTIVATIONS_KEY, _MISSION_TYPE_URN_KIND, mission_type) for mission_type in preset.mission_type_activations or ())
    return [(key, artifact_id) for key, urn_kind, artifact_id in listed if _canonical_urn(urn_kind, artifact_id) not in known_urns]


def _validate_presets(pack_dir: Path) -> list[ValidationIssue]:
    """Validate every preset under ``presets/``: format, id resolution and kind gate.

    A malformed file is one ``preset_format`` error naming the field; an id
    that resolves neither in the built-in pack nor in this pack is a
    ``preset_unresolved_id`` error naming the file and the id; an
    ``activated_kinds`` that leaves out a kind the preset lists ids for is a
    ``preset_kind_gate`` error naming the missing plurals.
    """
    files = preset_files(pack_dir)
    if not files:
        return []
    issues: list[ValidationIssue] = []
    known_urns: frozenset[str] | None = None
    for path in files:
        try:
            preset = load_preset_file(path)
        except PresetFormatError as exc:
            issues.append(_preset_issue(path, f"malformed preset {path.name}: {exc.field}: {exc.detail}", "preset_format"))
            continue
        if known_urns is None:
            known_urns = _preset_offering_urns(pack_dir)
        for key, artifact_id in _unresolved_preset_ids(preset, known_urns):
            issues.append(_preset_issue(path, f"preset {path.name}: {key} id {artifact_id!r} does not resolve in the offering", "preset_unresolved_id"))
        omitted = kind_gate_omissions(preset)
        if omitted:
            issues.append(
                _preset_issue(path, f"preset {path.name}: {ACTIVATED_KINDS_KEY} omits {', '.join(omitted)}, which the preset lists ids for", "preset_kind_gate")
            )
    return issues


# ---------------------------------------------------------------------------
# Authored pack.yaml descriptor
# ---------------------------------------------------------------------------

#: The authored descriptor's file name and ``artifact_type``.
_PACK_DESCRIPTOR_FILENAME = "pack.yaml"
_PACK_DESCRIPTOR_ARTIFACT_TYPE = "pack"


def _descriptor_issue(path: Path, message: str, category: str, artifact_id: str | None = None) -> ValidationIssue:
    return ValidationIssue(
        severity="error",
        artifact_type=_PACK_DESCRIPTOR_ARTIFACT_TYPE,
        artifact_id=artifact_id,
        file=str(path),
        message=message,
        category=category,
    )


def _validate_pack_descriptor(pack_dir: Path) -> list[ValidationIssue]:
    """Validate the pack's authored ``pack.yaml``, when it has one.

    A retired field is one ``RETIRED_PACK_FIELD`` error naming the file, the
    field and its replacement (the message of
    :class:`~charter.offering.packs.retired_fields.RetiredPackFieldError`); any
    other schema failure is ``schema_invalid`` and an unparseable or unreadable
    file is ``parse_error``.
    """
    path = pack_dir / _PACK_DESCRIPTOR_FILENAME
    if not path.is_file():
        return []
    try:
        load_pack_descriptor(path)
    except RetiredPackFieldError as exc:
        return [_descriptor_issue(path, f"{RETIRED_PACK_FIELD}: {exc}", RETIRED_PACK_FIELD, artifact_id=exc.field)]
    except ValidationError as exc:
        return [_descriptor_issue(path, f"{_PACK_DESCRIPTOR_FILENAME} schema validation failed: {exc.errors()[0].get('msg', exc)}", "schema_invalid")]
    except (YAMLError, OSError) as exc:
        return [_descriptor_issue(path, f"unreadable {_PACK_DESCRIPTOR_FILENAME}: {exc}", "parse_error")]
    return []


# ---------------------------------------------------------------------------
# DRG validation
# ---------------------------------------------------------------------------

#: Glob for a pack's DRG-graph fragments/root file (PR-M-004: hoisted here
#: because the literal recurred 4x across this module, crossing CLAUDE.md's
#: Sonar S1192 >=3x duplicate-literal threshold).
_DRG_GRAPH_GLOB = "*.graph.yaml"


def _plural_to_urn_kind(plural: str) -> str | None:
    """Return the DRG ``NodeKind`` string matching this artifact plural.

    Derived from :class:`ArtifactKind` (#5538), so every kind the schema
    registry scans registers its URNs -- including ``assets``, which a former
    hand-copied map omitted, making a DRG edge to a pack's own asset read as
    dangling. ``None`` for a plural that names no artifact kind.
    """
    try:
        return ArtifactKind.from_plural(plural).value
    except KeyError:
        return None


def _validate_org_fragment(pack_dir: Path) -> list[ValidationIssue]:
    """Validate the pack's org surfaces through the runtime loading authority.

    When ``drg/fragment.yaml`` exists, the whole pack is loaded through
    :func:`load_org_pack` — the single schema authority (single-loader
    direction, #4189). Sibling-source faults (a governance-profile
    selection) carry their own file via the error's ``source_file`` and are
    reported against that file, never mis-attributed to the fragment.

    When no fragment exists, the fragment layer is optional — but a
    governance profile is read by that same loader the moment any fragment
    appears, so a profile fault is validated here directly rather than being
    gated on the fragment's presence (#4200 defect 3: a CLI-green pack must
    not be able to crash the runtime loader later). ``load_org_pack`` itself
    cannot run here: it raises :class:`OrgPackMissingError` for a
    fragment-less pack by contract (FR-004 strict mode), so the check routes
    through the same collector the loader calls — one authority, no second
    schema table.
    """
    fragment = pack_drg_fragment(pack_dir)
    if fragment.exists():
        try:
            load_org_pack(pack_name=pack_dir.name, pack_root=pack_dir, layer_index=1)
        except (OrgPackMissingError, OrgPackParseError, OrgPackSchemaError, OSError) as exc:
            return [_org_load_finding(exc, fallback_file=fragment)]
        return []
    return _validate_org_governance_profiles(pack_dir)


def _validate_org_governance_profiles(pack_dir: Path) -> list[ValidationIssue]:
    """Validate ``mission_types/*/governance-profile.yaml`` with no fragment present.

    Runs the loader's own collector directly so a malformed ``selected_*``
    selection is a CLI finding even when the pack ships no
    ``drg/fragment.yaml`` — the exact shape that previously passed green
    here while raising at runtime once a fragment appeared (#4200 defect 3).
    """
    if not (pack_dir / "mission_types").is_dir():
        return []
    from charter.offering.drg.org_governance import (  # noqa: PLC0415 — lazy: mirrors the loader's own lazy import of the collector
        collect_org_governance_scope_edges,
    )

    try:
        collect_org_governance_scope_edges(pack_dir)
    except (OrgPackSchemaError, OSError) as exc:
        return [_org_load_finding(exc, fallback_file=pack_dir)]
    return []


def _built_in_node_urns() -> frozenset[str]:
    """Return every built-in DRG node URN (empty when the graph is unavailable)."""
    from charter.offering.drg.loader import DRGLoadError, load_built_in_graph

    try:
        return frozenset(node.urn for node in load_built_in_graph().nodes)
    except (ModuleNotFoundError, DRGLoadError, OSError):
        return frozenset()


def _pack_node_urns(pack_dir: Path) -> frozenset[str] | None:
    """Return the URNs of the nodes the pack contributes, or ``None`` if unloadable.

    Goes through :func:`load_org_pack` (the runtime authority), so nodes minted
    from artifact files count as well as nodes declared in ``drg/fragment.yaml``.
    A load failure is already reported by :func:`_validate_org_fragment`.
    """
    try:
        fragment = load_org_pack(pack_name=pack_dir.name, pack_root=pack_dir, layer_index=1)
    except (OrgPackMissingError, OrgPackParseError, OrgPackSchemaError, OSError):
        return None
    return frozenset(f"{ORG_PLURAL_TO_SINGULAR_KIND.get(node.kind, node.kind)}:{node.id}" for node in fragment.nodes)


def _sanction_issue(severity: str, file: Path, urn: str | None, message: str) -> ValidationIssue:
    return ValidationIssue(
        severity=severity,
        artifact_type="pack",
        artifact_id=urn,
        file=str(file),
        message=message,
        category="pack_sanction",
    )


def _validate_pack_sanction(pack_dir: Path, built_in_urns: frozenset[str]) -> tuple[list[ValidationIssue], list[ValidationIssue]]:
    """Validate ``<pack>/replaceable-builtins.yaml`` (FR-014).

    Errors: any parse/shape failure reported by the single sanction parser, and a
    ``directive:`` entry with an empty reason. Advisory: an entry naming a URN
    that is not a built-in this pack overrides (inert, never an error). The
    advisory is skipped when the pack's own nodes cannot be loaded, or when the
    built-in graph is unavailable (``built_in_urns`` empty) — without the set of
    real built-ins, every entry would otherwise look inert.
    """
    sanction_file = pack_dir / PACK_POLICY_FILENAME
    try:
        policy = load_pack_sanction(pack_dir.name, pack_dir)
    except OverridePolicyError as exc:
        return [_sanction_issue("error", sanction_file, None, str(exc))], []

    errors: list[ValidationIssue] = []
    advisories: list[ValidationIssue] = []
    pack_urns = _pack_node_urns(pack_dir)
    for entry in policy.entries:
        if sanction_reason_missing(entry.urn, entry.reason):
            errors.append(
                _sanction_issue(
                    "error",
                    sanction_file,
                    entry.urn,
                    f"{PACK_POLICY_FILENAME}: directive override '{entry.urn}' requires a non-empty reason",
                )
            )
        elif pack_urns is not None and built_in_urns and not (entry.urn in built_in_urns and entry.urn in pack_urns):
            advisories.append(
                _sanction_issue(
                    "advisory",
                    sanction_file,
                    entry.urn,
                    f"{PACK_POLICY_FILENAME}: '{entry.urn}' is not a built-in this pack overrides; the entry is inert",
                )
            )
    return errors, advisories


def _org_load_finding(exc: Exception, fallback_file: Path) -> ValidationIssue:
    """Map one org-pack load fault to a finding naming its real source file.

    Sibling-source faults (a governance profile) carry their own
    ``source_file``; a missing pack names the path it was expected at; an
    ``OSError`` names ``exc.filename`` when the OS handed it back; fragment
    faults name the fragment. The category distinguishes a missing
    referenced pack (``org_pack_missing``) and an unreadable file
    (``unreadable_file``) from genuine parse and schema faults — none of the
    four is conflated with another (#4200 defect 2 and nit a).
    """
    source = getattr(exc, "source_file", None)
    if source is not None:
        file = str(source)
    elif isinstance(exc, OrgPackMissingError):
        file = exc.configured_path
    elif isinstance(exc, OSError) and exc.filename is not None:
        file = str(exc.filename)
    else:
        file = str(fallback_file)
    if isinstance(exc, OrgPackSchemaError):
        category = "schema_invalid"
    elif isinstance(exc, OrgPackParseError):
        category = "parse_error"
    elif isinstance(exc, OrgPackMissingError):
        category = "org_pack_missing"
    else:
        category = "unreadable_file"
    message = f"unreadable org-pack file: {exc}" if isinstance(exc, OSError) else str(exc)
    return ValidationIssue(
        severity="error",
        artifact_type="drg",
        artifact_id=None,
        file=file,
        message=message,
        category=category,
    )


def _validate_drg(
    drg_dir: Path,
    pack_artifact_urns: set[str],
) -> tuple[list[ValidationIssue], list[ValidationIssue]]:
    """Validate the pack's DRG extension fragments.

    Performs:

    * load all ``*.graph.yaml`` fragments;
    * load the built-in DRG (best-effort — missing built-in graph is treated
      as an empty node set so the validator still runs in stripped test
      environments);
    * verify every fragment edge references a URN in
      ``built-in ∪ pack_artifact_urns``;
    * verify no fragment node overrides a built-in node's ``kind``;
    * advisory for duplicate edges across fragments.
    """
    errors: list[ValidationIssue] = []
    advisories: list[ValidationIssue] = []

    try:
        from charter.offering.drg.loader import DRGLoadError, load_built_in_graph, load_graph
        from charter.offering.drg.models import DRGGraphSchemaError
    except ModuleNotFoundError:  # pragma: no cover - doctrine package always present
        return errors, advisories

    fragments = sorted(drg_dir.glob(_DRG_GRAPH_GLOB))
    if not fragments:
        return errors, advisories

    # Load built-in graph (best-effort) via the canonical seam (WP03, #2680).
    built_in_urns: set[str] = set()
    built_in_kinds: dict[str, str] = {}
    try:
        built_in_graph = load_built_in_graph()
        built_in_urns = {n.urn for n in built_in_graph.nodes}
        built_in_kinds = {n.urn: n.kind.value for n in built_in_graph.nodes}
    except (ModuleNotFoundError, DRGLoadError, OSError):
        # Test environments may strip the built-in graph; carry on with an
        # empty built-in set so dangling-edge detection still operates over
        # the pack's own URNs.
        pass

    known_urns = built_in_urns | pack_artifact_urns
    seen_edges: dict[tuple[str, str, str], Path] = {}

    for fragment in fragments:
        try:
            graph = load_graph(fragment)
        except DRGGraphSchemaError as exc:
            errors.append(
                ValidationIssue(
                    severity="error",
                    artifact_type="drg",
                    artifact_id=None,
                    file=str(fragment),
                    message=str(exc),
                    category="schema_invalid",
                )
            )
            continue
        except DRGLoadError as exc:
            errors.append(
                ValidationIssue(
                    severity="error",
                    artifact_type="drg",
                    artifact_id=None,
                    file=str(fragment),
                    message=f"failed to load DRG fragment: {exc}",
                )
            )
            continue

        # Nodes: must not change built-in node kinds.
        for node in graph.nodes:
            built_in_kind = built_in_kinds.get(node.urn)
            if built_in_kind is not None and built_in_kind != node.kind.value:
                errors.append(
                    ValidationIssue(
                        severity="error",
                        artifact_type="drg",
                        artifact_id=node.urn,
                        file=str(fragment),
                        message=(f"node {node.urn} attempts to change built-in kind {built_in_kind!r} → {node.kind.value!r}"),
                        category="drg_kind_drift",
                    )
                )
            # Adding new nodes is fine; track them as known URNs.
            known_urns.add(node.urn)

        # Edges: source and target must resolve.
        for edge in graph.edges:
            for role, urn in (("source", edge.source), ("target", edge.target)):
                if urn not in known_urns:
                    errors.append(
                        ValidationIssue(
                            severity="error",
                            artifact_type="drg",
                            artifact_id=urn,
                            file=str(fragment),
                            message=(f"dangling DRG edge — {role} URN {urn!r} not in built-in or pack artifact set"),
                            category="drg_dangling_edge",
                        )
                    )
            key = (edge.source, edge.target, edge.relation.value)
            if key in seen_edges:
                advisories.append(
                    ValidationIssue(
                        severity="advisory",
                        artifact_type="drg",
                        artifact_id=None,
                        file=str(fragment),
                        message=(f"duplicate edge ({edge.source} -[{edge.relation.value}]-> {edge.target}) already present in {seen_edges[key].name}"),
                        category="duplicate_drg_edge",
                    )
                )
            else:
                seen_edges[key] = fragment

    return errors, advisories


def _check_drg_root_graph_missing(
    pack_dir: Path,
    drg_dir: Path,
) -> list[ValidationIssue]:
    """Flag the one DRG shape no runtime path reads: ``drg/*.graph.yaml``.

    The runtime (``src/charter/activation/_drg_helpers.py:load_validated_graph``) reads a
    pack-root ``*.graph.yaml`` **and** ``drg/fragment.yaml`` (the latter folded
    via the DRG read-path bridge, mission ``drg-read-path-bridge-01M0CHVZ``,
    #3573). A ``drg/*.graph.yaml`` graph fragment is read by neither path, so it
    is genuinely-unread DRG content. This finding fires when ``drg/`` contains at
    least one ``*.graph.yaml`` fragment AND the pack root has no ``*.graph.yaml``.

    A coexisting ``drg/fragment.yaml`` does **not** suppress the finding: the
    fragment's ``requires``/``suggests`` edges do cascade, but a
    ``drg/*.graph.yaml`` graph document is a *distinct* shape the fragment does
    not express and no runtime path reads, so the author still needs the signal.
    The validator and the runtime graphless-warning answer different questions —
    the runtime warning fires when a pack contributes *nothing* to cascade (so a
    fragment satisfies it), while this finding fires when a *specific*
    ``drg/*.graph.yaml`` document goes unread (independent of the fragment). They
    are not mirror predicates.

    This does not contradict the runtime (C-001 / NFR-003): the finding never
    claims ``drg/fragment.yaml`` is unread — a ``fragment.yaml``-only pack ships
    no ``drg/*.graph.yaml`` and so never matches this glob (SC-003 / US3 AC1).
    The message states the real runtime read-set and drops the earlier false
    blanket "not drg/ fragments" claim. Uses the identical glob string
    ``_validate_drg`` uses so the two scans are consistent by construction (AC-5).
    """
    if not drg_dir.is_dir():
        return []
    if not sorted(drg_dir.glob(_DRG_GRAPH_GLOB)):
        return []
    if sorted(pack_dir.glob(_DRG_GRAPH_GLOB)):
        return []
    return [
        ValidationIssue(
            severity="error",
            artifact_type="drg",
            artifact_id=None,
            file=str(pack_dir),
            message=(
                "DRG content exists under drg/*.graph.yaml with no pack-root "
                "*.graph.yaml. The runtime "
                "(src/charter/activation/_drg_helpers.py:load_validated_graph) reads "
                "pack-root *.graph.yaml and drg/fragment.yaml; drg/*.graph.yaml "
                "graph fragments are the unread shape — this pack's "
                "drg/*.graph.yaml content will not be read as authored."
            ),
            category="drg_root_graph_missing",
        )
    ]


# ---------------------------------------------------------------------------
# ASSET sidecar manifest validation (T015-T017)
# ---------------------------------------------------------------------------


def _validate_asset_manifests(
    pack_dir: Path,
    asset_manifests: dict[str, tuple[dict[str, Any], Path]],
) -> tuple[list[ValidationIssue], list[ValidationIssue]]:
    """Validate ASSET sidecar manifests: path containment + mime consistency.

    Invoked once per pack (mirrors the ``if drg_dir.is_dir(): _validate_drg(...)``
    seam), deliberately kept separate from the branchy per-file
    :func:`_scan_artifact_directory` loop. *asset_manifests* is the
    ``{id: (raw_data, source_file)}`` slice already collected by the generic
    schema scan for the ``"assets"`` plural — manifests that failed schema
    validation (missing/blank ``id``/``mime``/``path``) never reach this
    function; they were already flagged ``schema_invalid`` by that scan.

    This does **not** enforce cross-pack global id-uniqueness — that is
    WP03's merge-time scan. Here: manifest well-formedness (already handled
    by the schema), path containment, and mime consistency.
    """
    errors: list[ValidationIssue] = []
    advisories: list[ValidationIssue] = []
    if not asset_manifests:
        return errors, advisories

    assets_root = (pack_dir / "assets").resolve(strict=False)
    for artifact_id in sorted(asset_manifests):
        data, source_file = asset_manifests[artifact_id]
        raw_path = data.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            continue  # defensive guard: schema already enforces non-empty path

        escape_error = _check_asset_path_containment(
            assets_root=assets_root,
            artifact_id=artifact_id,
            raw_path=raw_path,
            source_file=source_file,
        )
        if escape_error is not None:
            errors.append(escape_error)
            continue

        raw_mime = data.get("mime")
        if not isinstance(raw_mime, str) or not raw_mime:
            continue  # defensive guard: schema already enforces non-empty mime

        mime_error = _check_asset_mime(
            artifact_id=artifact_id,
            raw_mime=raw_mime,
            raw_path=raw_path,
            source_file=source_file,
        )
        if mime_error is not None:
            errors.append(mime_error)

    return errors, advisories


def _check_asset_path_containment(
    *,
    assets_root: Path,
    artifact_id: str,
    raw_path: str,
    source_file: Path,
) -> ValidationIssue | None:
    """Reuse the shared containment primitive to enforce path safety.

    Delegates to
    :func:`charter.offering.drg.org_pack_config.resolve_relative_path_within_root` —
    the same primitive :meth:`OrgPackConfig.effective_root` uses for
    ``subdir`` containment — rather than a sixth hand-rolled
    resolve-then-``relative_to`` implementation.

    Returns an ``asset_path_escape`` error issue when *raw_path* is absolute,
    contains a ``..`` component, or resolves (symlink-aware) outside
    *assets_root*; ``None`` when containment holds.
    """
    from charter.offering.drg.org_pack_config import (
        OrgPackSubdirEscapeError,
        resolve_relative_path_within_root,
    )

    try:
        resolve_relative_path_within_root(assets_root, raw_path)
    except OrgPackSubdirEscapeError as exc:
        return ValidationIssue(
            severity="error",
            artifact_type="assets",
            artifact_id=artifact_id,
            file=str(source_file),
            message=(f"asset path {raw_path!r} escapes the pack's assets/ root: {exc}"),
            category="asset_path_escape",
        )
    return None


def _check_asset_mime(
    *,
    artifact_id: str,
    raw_mime: str,
    raw_path: str,
    source_file: Path,
) -> ValidationIssue | None:
    """Validate ``mime`` shape (``type/subtype``) and path-extension consistency.

    Returns an ``asset_mime_invalid`` error issue when *raw_mime* is not a
    well-formed ``type/subtype`` value, or when Python's
    ``mimetypes.guess_type`` can infer a type from *raw_path*'s extension and
    it disagrees with the declared *raw_mime*; ``None`` when both checks
    pass (or when no type can be guessed from the extension — nothing to
    compare against).
    """
    import mimetypes

    mime_type, sep, mime_subtype = raw_mime.partition("/")
    if not sep or not mime_type or not mime_subtype:
        return ValidationIssue(
            severity="error",
            artifact_type="assets",
            artifact_id=artifact_id,
            file=str(source_file),
            message=(f"asset mime {raw_mime!r} is not a well-formed 'type/subtype' value"),
            category="asset_mime_invalid",
        )

    guessed_mime, _ = mimetypes.guess_type(raw_path)
    if guessed_mime is not None and guessed_mime != raw_mime:
        return ValidationIssue(
            severity="error",
            artifact_type="assets",
            artifact_id=artifact_id,
            file=str(source_file),
            message=(f"asset mime {raw_mime!r} is inconsistent with path {raw_path!r} (guessed {guessed_mime!r} from its extension)"),
            category="asset_mime_invalid",
        )
    return None


# ---------------------------------------------------------------------------
# Agent-profile skip diagnostics (FR-002)
# ---------------------------------------------------------------------------


def _check_profile_skipped_diagnostics(
    pack_dir: Path,
    already_flagged_files: set[str],
) -> list[ValidationIssue]:
    """Surface ``AgentProfileRepository``'s post-merge skip diagnostics.

    Reuses ``AgentProfileRepository.skipped_profiles()`` directly (AC-4)
    rather than a second skip-detection heuristic: the pack under validation
    is treated as the sole org source, matching how the runtime loads a real
    org pack. Deduplicated against files already flagged ``schema_invalid``
    by the generic per-file scan, so one root cause is not reported twice
    under two unrelated-looking categories (AC-2).

    An absent ``agent_profiles/`` directory is safe by construction —
    ``AgentProfileRepository``'s own ``_load_layer`` guard
    (``if not directory.exists(): return loaded``) handles it internally, so
    this never needs a defensive ``is_dir()`` check before construction
    (AC-5).

    Construction seam: ``AgentProfileRepository`` is built directly, on
    purpose — NOT routed through ``charter.offering.service.DoctrineService``. This
    call site validates an arbitrary ``pack_dir`` (a pack under authoring,
    not this repo's own doctrine layer), so it needs an explicit
    ``org_roots`` override; the sole-door architectural gate
    (``tests/architectural/test_charter_sole_door_doctrine_service.py``)
    bans raw ``charter.offering.service.DoctrineService`` construction outside
    ``charter.activation.doctrine_service_builder``, and that builder's public entry
    point (``build_activation_aware_doctrine_service``) takes only
    ``repo_root`` and self-resolves ``org_roots`` — it cannot target an
    arbitrary pack directory. The gate's documented escape hatch,
    constructing ``charter.activation.resolver.DoctrineService`` directly, requires an
    *already-built* raw inner ``charter.offering.service.DoctrineService``, which is
    the very construction the gate forbids here. Direct
    ``AgentProfileRepository`` construction is therefore the correct seam;
    do not "fix" this back to a ``DoctrineService`` wrapper.

    PR-M-001: direct construction does not remove the need for a guard —
    ``AgentProfileRepository.__init__`` resolves the built-in content
    directory via the fail-closed ``built_in_dir()`` seam (pinned by
    ``tests/doctrine/test_pack_root_resolver.py``), which can raise in a
    stripped environment. Guarded here exactly like the sibling
    ``_load_built_in_ids_per_kind`` guards the same seam, except the failure
    is surfaced as a ``profile_skipped`` ``ValidationIssue`` rather than
    silently degraded, since this diagnostic's whole purpose is reporting
    profile-load problems rather than a best-effort collision lookup.
    """
    from charter.offering.agent_profiles.repository import AgentProfileRepository

    try:
        repo = AgentProfileRepository(org_dirs=[pack_dir / "agent_profiles"])
        skipped_profiles = repo.skipped_profiles()
    except (PackRootNotFound, BuiltInContentDirNotAvailable) as exc:
        return [
            ValidationIssue(
                severity="error",
                artifact_type="agent_profiles",
                artifact_id=None,
                file=str(pack_dir / "agent_profiles"),
                message=(f"unable to resolve agent-profile diagnostics: {exc}"),
                category="profile_skipped",
            )
        ]
    issues: list[ValidationIssue] = []
    for skip in skipped_profiles:
        if skip.path in already_flagged_files:
            continue
        issues.append(
            ValidationIssue(
                severity="error",
                artifact_type="agent_profiles",
                artifact_id=skip.profile_id,
                file=skip.path,
                message=skip.error_summary,
                category="profile_skipped",
            )
        )
    return issues


# ---------------------------------------------------------------------------
# Built-in ID lookup (shared by intent-aware collision pass, WP06 T037)
# ---------------------------------------------------------------------------


def _kind_singular(plural: str) -> str:
    """Return the singular form of an artifact plural for human-facing messages.

    Resolved through :class:`ArtifactKind`, then the org-pack universe map
    for the one plural outside the enum (``mission_types``), never a suffix
    heuristic (#5538). The org map alone is not enough: it keys mission steps
    on the canonical ``mission_steps``, not the ``mission_step_contracts``
    directory plural this module scans. An unknown plural is echoed back.
    """
    urn_kind = _plural_to_urn_kind(plural)
    if urn_kind is not None:
        return urn_kind
    singular: str = ORG_PLURAL_TO_SINGULAR_KIND.get(plural, plural)
    return singular


def _load_built_in_ids_per_kind() -> dict[str, set[str]]:
    """Return the set of built-in artifact IDs per plural directory.

    Best-effort: when the built-in doctrine root cannot be located (stripped
    test environment), returns an empty mapping. Callers must treat absent
    entries as "no known built-ins for this kind", which downgrades the
    intent-aware pass to a no-op for that kind.
    """
    ids_per_kind: dict[str, set[str]] = {}
    # Built-in content flattened to packs/built-in/<kind>/ (relocation mission);
    # resolve via the shared built_in_dir(kind) seam rather than a locally
    # bound "built-in" root joined per-plural (the variable-indirected drift
    # class this seam exists to close).
    registry = artifact_schema_registry()
    parser = _yaml_parser()
    for plural, (glob, _schema) in registry.items():
        try:
            kind_dir = built_in_dir(ArtifactKind.from_plural(plural))
        except (
            PackRootNotFound,  # pragma: no cover - defensive; packs always present
            BuiltInContentDirNotAvailable,  # carve-out kind (e.g. mission_step_contracts)
        ):
            continue
        if not kind_dir.is_dir():
            continue
        collected: set[str] = set()
        for built_in_file in kind_dir.rglob(glob):
            try:
                data = parser.load(built_in_file)
            except (YAMLError, OSError):
                continue
            if isinstance(data, dict) and isinstance(data.get("id"), str):
                collected.add(data["id"])
        if collected:
            ids_per_kind[plural] = collected
    return ids_per_kind


# ---------------------------------------------------------------------------
# Intent-aware collision pass (FR-011..FR-013, WP06 T037)
# ---------------------------------------------------------------------------


def _intent_aware_collision_messages(
    pack_artifacts: dict[str, dict[str, tuple[dict[str, Any], Path]]],
    built_in_ids_per_kind: dict[str, set[str]],
    fragment_intent: FragmentIntent | None = None,
) -> tuple[list[ValidationIssue], list[ValidationIssue]]:
    """Emit intent-aware errors and advisories for pack artifacts.

    Implements the precedence table from
    ``kitty-specs/charter-ux-and-org-pack-vocabulary-01KSAF14/contracts/pack-validator-advisory.md``:

    1. Both ``overrides`` and ``enhances`` set -> ``intent_conflict`` ERROR.
    2. ``overrides`` references unknown built-in ID -> ``unknown_target`` ERROR.
    3. ``enhances`` references unknown built-in ID -> ``unknown_target`` ERROR.
    4. Either field declared and target valid -> suppress advisory.
    5. Neither declared, ID matches built-in -> ``same_id_collision`` ADVISORY (reworded).
       Exception: if ``fragment_intent`` carries a valid declared intent via DRG
       edge (FR-028 migration path for kinds where inline fields are retired), the
       advisory is suppressed here to maintain parity.
    6. Neither declared, no built-in collision -> nothing.

    Returns ``(errors, advisories)``.
    """
    errors: list[ValidationIssue] = []
    advisories: list[ValidationIssue] = []

    for plural in sorted(pack_artifacts):
        artifacts = pack_artifacts[plural]
        built_ins = built_in_ids_per_kind.get(plural, set())
        singular = _kind_singular(plural)
        for art_id in sorted(artifacts):
            data, source_file = artifacts[art_id]
            overrides_field = data.get("overrides")
            enhances_field = data.get("enhances")
            overrides_set = isinstance(overrides_field, str) and overrides_field
            enhances_set = isinstance(enhances_field, str) and enhances_field

            # 1. Both declared -> intent_conflict ERROR. The Pydantic model's
            #    validator typically catches this at schema time, but we
            #    duplicate the check here so the same precedence applies even
            #    when the schema layer is bypassed or skipped.
            if overrides_set and enhances_set:
                errors.append(
                    ValidationIssue(
                        severity="error",
                        artifact_type=plural,
                        artifact_id=art_id,
                        file=str(source_file),
                        message=(f"overrides and enhances are mutually exclusive on {singular} {art_id}"),
                        category="intent_conflict",
                    )
                )
                continue

            # 2. overrides target unknown -> unknown_target ERROR.
            if overrides_set and overrides_field not in built_ins:
                errors.append(
                    ValidationIssue(
                        severity="error",
                        artifact_type=plural,
                        artifact_id=art_id,
                        file=str(source_file),
                        message=(f"{singular} {art_id} declares overrides: {overrides_field}, but no built-in {singular} with that id exists"),
                        category="unknown_target",
                    )
                )
                continue

            # 3. enhances target unknown -> unknown_target ERROR.
            if enhances_set and enhances_field not in built_ins:
                errors.append(
                    ValidationIssue(
                        severity="error",
                        artifact_type=plural,
                        artifact_id=art_id,
                        file=str(source_file),
                        message=(f"{singular} {art_id} declares enhances: {enhances_field}, but no built-in {singular} with that id exists"),
                        category="unknown_target",
                    )
                )
                continue

            # 4. Either declared and target valid -> suppress advisory.
            if overrides_set or enhances_set:
                continue

            # 5. Neither declared and ID matches built-in -> reworded advisory.
            if art_id in built_ins:
                # FR-028 migration path: inline fields retired on some kinds;
                # check DRG fragment edges as the authoritative intent source.
                if fragment_intent is not None:
                    edge_record = (fragment_intent.get(plural) or {}).get(art_id)
                    if edge_record is not None:
                        intent_map = edge_record[0] if isinstance(edge_record, tuple) else edge_record
                        edge_enhances = intent_map.get("enhances") if isinstance(intent_map, dict) else None
                        edge_overrides = intent_map.get("overrides") if isinstance(intent_map, dict) else None
                        if edge_enhances == art_id or edge_overrides == art_id:
                            continue  # valid declared intent via DRG edge suppresses advisory
                advisories.append(
                    ValidationIssue(
                        severity="advisory",
                        artifact_type=plural,
                        artifact_id=art_id,
                        file=str(source_file),
                        message=(
                            f"artifact id {art_id!r} will field-merge into the "
                            f"built-in {singular} — declare "
                            f"'enhances: {art_id}' to suppress this advisory, "
                            f"or 'overrides: {art_id}' to declare a full replacement"
                        ),
                        category="same_id_collision",
                    )
                )

            # 6. Neither declared and no built-in collision -> no message.

    return errors, advisories


# ---------------------------------------------------------------------------
# Fragment-edge intent pass (FR-031, T016) — parity for the newly-covered kinds
# ---------------------------------------------------------------------------


def _urn_to_plural(urn: str) -> tuple[str, str] | None:
    """Split a ``kind:id`` URN into ``(plural_dir, artifact_id)``.

    Returns ``None`` when the URN is malformed or its singular kind has no
    plural directory in the augmentation-eligible set.
    """
    singular, sep, artifact_id = urn.partition(":")
    if not sep or not singular or not artifact_id:
        return None
    plural = _SINGULAR_TO_PLURAL_AUGMENTATION.get(singular)
    if plural is None:
        return None
    return plural, artifact_id


def _fold_augmentation_edges(
    edges: Iterable[tuple[str, str, str]],
    source_path: Path,
    intent: dict[str, dict[str, tuple[dict[str, str], Path]]],
    augmentation_relations: set[str],
) -> None:
    """Fold ``(source, target, relation)`` triples into *intent* in place.

    Shared by the ``drg/*.graph.yaml`` glob loop and the ``drg/fragment.yaml``
    branch of :func:`_collect_fragment_edge_intent` (#5494), so both authoring
    surfaces populate the same precedence-table input through one code path.
    """
    for source_urn, target_urn, relation in edges:
        if relation not in augmentation_relations:
            continue
        source = _urn_to_plural(source_urn)
        target = _urn_to_plural(target_urn)
        if source is None or target is None:
            continue
        plural, art_id = source
        if plural not in _AUGMENTATION_PLURAL_KINDS:
            continue
        record = intent.setdefault(plural, {}).setdefault(art_id, ({}, source_path))[0]
        record[relation] = target[1]


def _collect_fragment_yaml_edges(
    drg_dir: Path,
) -> list[tuple[str, str, str]] | None:
    """Read ``(source, target, relation)`` triples from ``drg/fragment.yaml``.

    Reuses the single org-fragment loading authority (:func:`load_org_pack`,
    #4189 single-loader direction) — the same one :func:`_validate_org_fragment`
    calls — rather than a second YAML parser. Best-effort: a fragment that
    fails to load returns ``None`` (no edges to fold) because
    ``_validate_org_fragment`` already surfaces the load error as a finding.
    Returns ``None`` (not ``[]``) when no ``fragment.yaml`` exists, so callers
    can distinguish "nothing to fold" from "empty edges list".

    Endpoints are qualified to ``kind:id`` before they are returned
    (:func:`_qualify_fragment_edge`), so a bare-id endpoint — a documented
    valid spelling the runtime resolver accepts — folds like the qualified
    form instead of being dropped by :func:`_urn_to_plural` (#5494).
    """
    fragment_yaml = pack_drg_fragment(drg_dir.parent)
    if not fragment_yaml.exists():
        return None
    try:
        fragment = load_org_pack(pack_name=drg_dir.parent.name, pack_root=drg_dir.parent, layer_index=1)
    except (OrgPackMissingError, OrgPackParseError, OrgPackSchemaError, OSError):
        return None
    # Mint fragment-local URNs exactly as the runtime bridge does
    # (``merge._bridge_org_node_to_drg_node``: ``<singular_kind>:<id>``).
    node_id_to_urn = {node.id: f"{ORG_PLURAL_TO_SINGULAR_KIND[node.kind]}:{node.id}" for node in fragment.nodes if node.kind in ORG_PLURAL_TO_SINGULAR_KIND}
    qualified = (_qualify_fragment_edge(edge.source, edge.target, edge.relation, node_id_to_urn) for edge in fragment.edges)
    return [edge for edge in qualified if edge is not None]


def _qualify_fragment_endpoint(
    raw: str,
    node_id_to_urn: Mapping[str, str],
    bare_fallback_kind: str | None,
) -> str | None:
    """Qualify one ``drg/fragment.yaml`` endpoint to a ``kind:id`` URN (#5494).

    Rules 1 (fragment-local bare id) and 2 (fully-qualified URN) are the
    canonical runtime resolver's own — :func:`_resolve_edge_endpoint` is
    called with an empty built-in index rather than re-implemented here.

    Rule 3 (a bare id bound against the built-in layer) is replaced by its
    validator analogue: a bare *target* takes the source's kind
    (*bare_fallback_kind*). Augmentation relations are same-kind, so an
    existing built-in still binds, and a missing one reaches the
    precedence table's ``unknown_target`` error — the validator's
    counterpart of the runtime's ``unresolved_edge_endpoint`` — instead of
    being dropped.

    Returns ``None`` (the edge is not folded) for a bare non-local source
    (no kind to borrow) or an endpoint the resolver refuses as malformed.
    """
    try:
        resolved: str = _resolve_edge_endpoint(raw, node_id_to_urn, ())
    except _EndpointResolutionError:
        if bare_fallback_kind is None or ":" in raw:
            return None
        return f"{bare_fallback_kind}:{raw}"
    return resolved


def _qualify_fragment_edge(
    source: str,
    target: str,
    relation: str,
    node_id_to_urn: Mapping[str, str],
) -> tuple[str, str, str] | None:
    """Qualify both endpoints of one fragment edge, source first.

    The source is resolved first so a bare target can borrow its kind
    (:func:`_qualify_fragment_endpoint`). Returns ``None`` when either
    endpoint cannot be qualified.
    """
    source_urn = _qualify_fragment_endpoint(source, node_id_to_urn, None)
    if source_urn is None:
        return None
    target_urn = _qualify_fragment_endpoint(target, node_id_to_urn, source_urn.partition(":")[0])
    if target_urn is None:
        return None
    return source_urn, target_urn, relation


def _collect_fragment_edge_intent(
    drg_dir: Path,
) -> FragmentIntent:
    """Read augmentation/lineage intent from DRG fragment edges.

    Returns ``{plural: {artifact_id: (intent, fragment_path)}}`` where
    *intent* maps the declared relation name (``enhances`` / ``overrides``) to
    its target artifact id. ``specializes_from`` is a lineage relation, not an
    augmentation-collision intent, so it is intentionally not folded into the
    same-ID/unknown-target precedence here (it neither suppresses nor conflicts
    with augmentation intent). Best-effort: unparseable fragments are skipped
    (``_validate_drg`` surfaces those load errors).

    Two authoring surfaces are folded into one ``intent`` mapping (#5494):
    ``drg/*.graph.yaml`` (the original shape) and ``drg/fragment.yaml`` (the
    org-fragment shape the runtime actually reads via ``load_org_pack``,
    since ``*.graph.yaml`` alone is a hard ``drg_root_graph_missing`` error
    per #3387). The record path stored with the intent (``fragment_path``)
    is always the file the edge was authored in, so messages name the right
    file.
    """
    from charter.offering.drg.models import Relation

    try:
        from charter.offering.drg.loader import DRGLoadError, load_graph
        from charter.offering.drg.models import DRGGraphSchemaError
    except ModuleNotFoundError:  # pragma: no cover - doctrine always present
        return {}

    augmentation_relations = {Relation.ENHANCES.value, Relation.OVERRIDES.value}
    intent: dict[str, dict[str, tuple[dict[str, str], Path]]] = {}
    for fragment in sorted(drg_dir.glob(_DRG_GRAPH_GLOB)):
        try:
            graph = load_graph(fragment)
        except (DRGLoadError, DRGGraphSchemaError):
            continue
        _fold_augmentation_edges(
            ((edge.source, edge.target, edge.relation.value) for edge in graph.edges),
            fragment,
            intent,
            augmentation_relations,
        )

    org_fragment_edges = _collect_fragment_yaml_edges(drg_dir)
    if org_fragment_edges is not None:
        _fold_augmentation_edges(
            org_fragment_edges,
            pack_drg_fragment(drg_dir.parent),
            intent,
            augmentation_relations,
        )

    return intent


def _intent_aware_collision_messages_from_edges(
    fragment_intent: FragmentIntent,
    built_in_ids_per_kind: dict[str, set[str]],
    field_artifacts: dict[str, dict[str, tuple[dict[str, Any], Path]]],
) -> tuple[list[ValidationIssue], list[ValidationIssue]]:
    """Apply the intent-aware precedence to fragment-authored augmentation edges.

    Mirrors :func:`_intent_aware_collision_messages` but sources intent from
    fragment edges. Artifacts already covered by the field-based pass
    (*field_artifacts*) are skipped to avoid duplicate diagnostics.

    Precedence (parity with the original five, FR-031):

    1. both ``enhances`` and ``overrides`` declared for one source ->
       ``intent_conflict`` ERROR.
    2. target not a known built-in -> ``unknown_target`` ERROR.
    3. valid intent declared -> suppress the same-ID advisory (no message).
    """
    errors: list[ValidationIssue] = []
    advisories: list[ValidationIssue] = []

    for plural in sorted(fragment_intent):
        built_ins = built_in_ids_per_kind.get(plural, set())
        singular = _kind_singular(plural)
        field_ids = set(field_artifacts.get(plural, {}))
        for art_id in sorted(fragment_intent[plural]):
            if art_id in field_ids:
                # Skip when the field-based path declared intent via inline
                # fields — it owns the advisory for that artifact.
                # Also skip when the artifact ID does NOT collide with a
                # built-in: no advisory was produced by the field-based path
                # and processing the edge here would produce a spurious
                # ``unknown_target`` error for self-referential augmentation
                # edges that declare intent on non-built-in IDs.
                #
                # FR-028 retired ``enhances``/``overrides`` inline fields on
                # tactics and styleguides. For those artifacts the field-based
                # path produces a ``same_id_collision`` advisory (no inline
                # intent) even though the edge-based path carries the correct
                # declared intent.  We must NOT skip those artifacts so the
                # edge-based path can suppress the advisory.
                field_data = field_artifacts.get(plural, {}).get(art_id)
                has_field_intent = False
                if field_data is not None:
                    raw_data = field_data[0]
                    has_field_intent = bool(raw_data.get("enhances") or raw_data.get("overrides"))
                has_builtin_collision = art_id in built_ins
                if has_field_intent or not has_builtin_collision:
                    continue  # field-based path handles it, or no collision exists
                # Fall through: built-in collision exists but inline intent was
                # retired (FR-028); edge-based path takes over.
            record, fragment = fragment_intent[plural][art_id]
            overrides_target = record.get("overrides")
            enhances_target = record.get("enhances")

            if overrides_target and enhances_target:
                errors.append(
                    ValidationIssue(
                        severity="error",
                        artifact_type=plural,
                        artifact_id=art_id,
                        file=str(fragment),
                        message=(f"overrides and enhances are mutually exclusive on {singular} {art_id} (declared via DRG fragment edges)"),
                        category="intent_conflict",
                    )
                )
                continue

            for relation, target in (
                ("overrides", overrides_target),
                ("enhances", enhances_target),
            ):
                if target and target not in built_ins:
                    errors.append(
                        ValidationIssue(
                            severity="error",
                            artifact_type=plural,
                            artifact_id=art_id,
                            file=str(fragment),
                            message=(f"{singular} {art_id} declares {relation}: {target} (via DRG fragment edge), but no built-in {singular} with that id exists"),
                            category="unknown_target",
                        )
                    )
            # Valid declared intent suppresses the same-ID advisory: emit nothing.

    return errors, advisories


#: Singular URN kind -> plural directory, restricted to augmentation-eligible
#: kinds. Derived from the single source in ``org_pack_loader`` (FR-030) so the
#: fragment-edge intent pass never re-declares the kind set.
def _build_singular_to_plural() -> dict[str, str]:
    from charter.offering.drg.org_pack_loader import AUGMENTATION_ELIGIBLE_KINDS

    return dict(AUGMENTATION_ELIGIBLE_KINDS)


_SINGULAR_TO_PLURAL_AUGMENTATION: dict[str, str] = _build_singular_to_plural()


# ---------------------------------------------------------------------------
# org-charter.yaml validation hook (T044, research A.3 #4)
# ---------------------------------------------------------------------------

#: The org-charter leg of :func:`validate_pack`: given the pack's
#: ``org-charter.yaml`` path and the directive ids the pack ships, return the
#: findings. Org charter composition is an activation concern, so the check is
#: supplied by the caller (the org-charter composing entry) rather than
#: imported here.
OrgCharterCheck = Callable[[Path, AbstractSet[str]], list[ValidationIssue]]

#: Category of the finding recorded when a pack ships ``org-charter.yaml`` but
#: the caller supplied no :data:`OrgCharterCheck`: never skipped silently.
ORG_CHARTER_UNCHECKED_CATEGORY = "org_charter_unchecked"


def _check_org_charter(
    pack_dir: Path,
    pack_directive_ids: AbstractSet[str],
    org_charter_check: OrgCharterCheck | None,
) -> list[ValidationIssue]:
    """Run the org-charter leg, or record that it could not run."""
    charter_path = pack_org_charter(pack_dir)
    if not charter_path.exists():
        return []
    if org_charter_check is None:
        return [
            ValidationIssue(
                severity="error",
                artifact_type="org-charter",
                artifact_id=None,
                file=str(charter_path),
                message=("org charter not validated: no checker supplied (validate the pack through the org-charter composing entry)"),
                category=ORG_CHARTER_UNCHECKED_CATEGORY,
            )
        ]
    return org_charter_check(charter_path, pack_directive_ids)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_validation_result(
    result: ValidationResult,
    *,
    json_output: bool = False,
) -> None:
    """Render *result* to stdout.

    Human format::

        ✓ pack/directives/foo.directive.yaml — OK
        ✗ pack/directives/bar.directive.yaml — Error: missing required field 'title'
        ⚠ advisory: artifact id 'DIR-003' overrides a built-in directive
        Pack validation: 1 error, 1 advisory

    JSON format::

        {"ok": false, "errors": [...], "advisories": [...]}
    """
    if json_output:
        print(json.dumps(result.to_dict(), sort_keys=True))
        return

    for issue in result.errors:
        prefix = f"{issue.artifact_type}"
        if issue.artifact_id:
            prefix += f"/{issue.artifact_id}"
        category_suffix = f" ({issue.category})" if issue.category else ""
        print(f"✗ {issue.file} [{prefix}]{category_suffix} — Error: {issue.message}")

    for issue in result.advisories:
        prefix = f"{issue.artifact_type}"
        if issue.artifact_id:
            prefix += f"/{issue.artifact_id}"
        category_suffix = f" ({issue.category})" if issue.category else ""
        print(f"⚠ advisory [{prefix}]{category_suffix}: {issue.message}")

    summary = (
        f"Pack validation: {len(result.errors)} error"
        f"{'s' if len(result.errors) != 1 else ''}, "
        f"{len(result.advisories)} advisor"
        f"{'ies' if len(result.advisories) != 1 else 'y'}"
    )
    print(summary)
