"""Charter facade for the charter pack model and tooling.

The public door for ``specify_cli`` to the pack model and tooling that live in
:mod:`charter.offering.packs` (mission ``charter-pack-cutover-01M491G6``, FR-010 /
OD-9). Object-identity re-exports only: every name here *is* the offering
object, so no wrapper, alias or shim can drift from it
(``tests/architectural/test_charter_facades_reexport_offering.py``).

``specify_cli`` modules import these names from here, never from
``charter.offering.packs.*`` directly, so the runtime -> charter -> offering
boundary (``tests/architectural/test_runtime_charter_doctrine_boundary.py``)
holds without growing its lazy-import baseline (NFR-002).

``validate_pack`` and ``assemble_pack`` take their org-charter leg as a hook;
callers use the org-charter composing entries ``validate_pack_with_org_charter``
and ``assemble_pack_with_org_charter``, re-exported here from
:mod:`charter.activation.org_charter` (org charter composition is an activation
concern; this module is not under ``charter.offering``, so importing
``charter.activation`` here keeps the offering -> activation gate green).
"""

from __future__ import annotations

from charter.activation.org_charter import (
    assemble_pack_with_org_charter,
    validate_pack_with_org_charter,
)
from charter.offering.packs.builtin_manifest import (
    builtin_manifest_is_fresh,
    generate_builtin_manifest,
)
from charter.offering.packs.pack_assembler import (
    AssemblyResult,
    assemble_pack,
    pack_document_dict,
    render_assembly_result,
)
from charter.offering.packs.pack_manifest import (
    RECOGNISED_ARTIFACT_DIRS,
    count_snapshot_artifacts,
    safe_urlsplit,
    snapshot_sha256,
    source_fingerprint,
    strip_source_credentials,
    write_pack_manifest,
)
from charter.offering.packs.presets import (
    ActivationPreset,
    OfferingPack,
    PresetFormatError,
    PresetNotFoundError,
    discover_presets,
    list_offering_packs,
    load_preset,
    load_preset_file,
    preset_activation_keys,
    render_example_preset,
    write_example_preset,
)
from charter.offering.packs.pack_validator import (
    ValidationIssue,
    artifact_schema_registry,
    render_validation_result,
    validate_pack,
)
from charter.offering.packs.retired_fields import (
    RETIRED_PACK_FIELD,
    RetiredPackFieldError,
)

__all__ = [
    "RECOGNISED_ARTIFACT_DIRS",
    "RETIRED_PACK_FIELD",
    "ActivationPreset",
    "AssemblyResult",
    "OfferingPack",
    "PresetFormatError",
    "PresetNotFoundError",
    "RetiredPackFieldError",
    "ValidationIssue",
    "artifact_schema_registry",
    "assemble_pack",
    "assemble_pack_with_org_charter",
    "builtin_manifest_is_fresh",
    "count_snapshot_artifacts",
    "discover_presets",
    "generate_builtin_manifest",
    "list_offering_packs",
    "load_preset",
    "load_preset_file",
    "pack_document_dict",
    "preset_activation_keys",
    "render_assembly_result",
    "render_example_preset",
    "write_example_preset",
    "render_validation_result",
    "safe_urlsplit",
    "snapshot_sha256",
    "source_fingerprint",
    "strip_source_credentials",
    "validate_pack",
    "validate_pack_with_org_charter",
    "write_pack_manifest",
]
