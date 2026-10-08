"""Bundle schema versioning and compatibility registry.

Provides the compatibility registry that maps bundle integer schema versions
to supported CLI version ranges. Used by charter modules to decide whether
a bundle can be read natively or needs migration.

Dependency direction: charter -> charter.offering (never reversed).
This module must NOT import from charter.*.
"""

from __future__ import annotations

import dataclasses
import hashlib
from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from charter.offering.yaml_utils import canonical_yaml
from kernel.clock import from_epoch

# --- Constants ---

CURRENT_BUNDLE_SCHEMA_VERSION: int = 2
"""The bundle schema version written by Phase 7 synthesis."""

MIN_READABLE_BUNDLE_SCHEMA: int = 1
"""Oldest bundle schema version this CLI can read (after migration)."""

MAX_READABLE_BUNDLE_SCHEMA: int = 2
"""Newest bundle schema version this CLI reads natively."""


# --- Enums ---


class BundleCompatibilityStatus(str, Enum):
    """Compatibility status of a bundle with the current CLI."""

    COMPATIBLE = "COMPATIBLE"
    NEEDS_MIGRATION = "NEEDS_MIGRATION"
    INCOMPATIBLE_OLD = "INCOMPATIBLE_OLD"
    INCOMPATIBLE_NEW = "INCOMPATIBLE_NEW"
    MISSING_VERSION = "MISSING_VERSION"


# --- Dataclasses ---


@dataclasses.dataclass(frozen=True)
class BundleCompatibilityResult:
    """Result of a bundle compatibility check."""

    status: BundleCompatibilityStatus
    bundle_version: int | None
    supported_min: int
    supported_max: int
    message: str
    exit_code: int

    @property
    def is_compatible(self) -> bool:
        """True if the bundle can be used without migration."""
        return self.status == BundleCompatibilityStatus.COMPATIBLE

    @property
    def needs_migration(self) -> bool:
        """True if the bundle needs migration before use."""
        return self.status in (
            BundleCompatibilityStatus.NEEDS_MIGRATION,
            BundleCompatibilityStatus.MISSING_VERSION,
        )


@dataclasses.dataclass
class MigrationResult:
    """Result of running a migration on a bundle."""

    changes_made: list[str]
    errors: list[str]
    from_version: int
    to_version: int


# --- Core functions ---


def check_bundle_compatibility(bundle_version: int | None) -> BundleCompatibilityResult:
    """Check whether a bundle schema version is compatible with this CLI.

    Pure function — no filesystem I/O.

    Args:
        bundle_version: Integer schema version read from bundle metadata,
            or None if the field was absent.

    Returns:
        BundleCompatibilityResult describing status and remediation action.
    """
    if bundle_version is None:
        return BundleCompatibilityResult(
            status=BundleCompatibilityStatus.MISSING_VERSION,
            bundle_version=None,
            supported_min=MIN_READABLE_BUNDLE_SCHEMA,
            supported_max=MAX_READABLE_BUNDLE_SCHEMA,
            message=(
                "Bundle schema version not found; treating as v1. "
                "Run `spec-kitty upgrade`."
            ),
            exit_code=1,
        )

    if bundle_version == CURRENT_BUNDLE_SCHEMA_VERSION:
        return BundleCompatibilityResult(
            status=BundleCompatibilityStatus.COMPATIBLE,
            bundle_version=bundle_version,
            supported_min=MIN_READABLE_BUNDLE_SCHEMA,
            supported_max=MAX_READABLE_BUNDLE_SCHEMA,
            message=f"Bundle schema version {bundle_version} is supported.",
            exit_code=0,
        )

    if MIN_READABLE_BUNDLE_SCHEMA <= bundle_version < CURRENT_BUNDLE_SCHEMA_VERSION:
        return BundleCompatibilityResult(
            status=BundleCompatibilityStatus.NEEDS_MIGRATION,
            bundle_version=bundle_version,
            supported_min=MIN_READABLE_BUNDLE_SCHEMA,
            supported_max=MAX_READABLE_BUNDLE_SCHEMA,
            message=(
                f"Bundle schema version {bundle_version} requires migration. "
                "Run `spec-kitty upgrade`."
            ),
            exit_code=1,
        )

    if bundle_version < MIN_READABLE_BUNDLE_SCHEMA:
        return BundleCompatibilityResult(
            status=BundleCompatibilityStatus.INCOMPATIBLE_OLD,
            bundle_version=bundle_version,
            supported_min=MIN_READABLE_BUNDLE_SCHEMA,
            supported_max=MAX_READABLE_BUNDLE_SCHEMA,
            message=(
                f"Bundle schema version {bundle_version} predates the earliest "
                f"supported version ({MIN_READABLE_BUNDLE_SCHEMA}). Contact support."
            ),
            exit_code=1,
        )

    # bundle_version > MAX_READABLE_BUNDLE_SCHEMA
    return BundleCompatibilityResult(
        status=BundleCompatibilityStatus.INCOMPATIBLE_NEW,
        bundle_version=bundle_version,
        supported_min=MIN_READABLE_BUNDLE_SCHEMA,
        supported_max=MAX_READABLE_BUNDLE_SCHEMA,
        message=(
            f"Bundle schema version {bundle_version} is newer than this CLI "
            f"supports ({MAX_READABLE_BUNDLE_SCHEMA}). Upgrade your CLI."
        ),
        exit_code=1,
    )


def get_bundle_schema_version(charter_dir: Path) -> int | None:
    """Read the bundle_schema_version integer from <charter_dir>/charter.yaml.

    consolidate-charter-bundle (WP07 / T030): re-pointed from the retired
    ``<charter_dir>/metadata.yaml`` top-level ``bundle_schema_version`` key
    onto ``<charter_dir>/charter.yaml``'s ``metadata.bundle_schema_version``
    (``charter.activation.schemas.CharterYamlMetadata`` -- data-model.md keeps this
    one field across the Landmine 2 retirement of ``charter_hash`` /
    ``extraction_mode`` / ``sections_parsed``). Callers pass the SAME
    ``charter_dir`` (``.kittify/charter/``) as before; only the filename and
    the nesting under ``metadata:`` changed. This module must not import
    ``charter.*`` (dependency direction: charter -> charter.offering, never
    reversed), so the read is a plain YAML dict-walk, not a pydantic
    validation.

    Args:
        charter_dir: Path to the charter bundle directory containing
            charter.yaml.

    Returns:
        Integer schema version, or None if the file is absent, the
        ``metadata`` section or ``bundle_schema_version`` key is absent, the
        value is null, or the value is not an integer.
        Never raises.
    """
    charter_yaml_path = charter_dir / "charter.yaml"
    if not charter_yaml_path.exists():
        return None
    yaml = YAML()
    data = yaml.load(charter_yaml_path)
    if not isinstance(data, dict):
        return None
    metadata = data.get("metadata")
    if not isinstance(metadata, dict):
        return None
    value = metadata.get("bundle_schema_version")
    if not isinstance(value, int):
        return None
    return value


# --- Migration registry ---

# Maps from_version → migration_function
_MIGRATIONS: dict[int, Callable[[Path, bool], MigrationResult]] = {}
PRE_PHASE7_MIGRATION_SENTINEL = "(pre-phase7-migration)"


def _compute_v2_synthesis_manifest_hash(manifest_data: dict[str, object]) -> str:
    """Hash a migrated v2 synthesis manifest using verifier-visible defaults."""
    fields_for_hash = {
        k: v for k, v in manifest_data.items() if k != "manifest_hash"
    }
    fields_for_hash["schema_version"] = "2"
    fields_for_hash.setdefault("mission_id", None)
    fields_for_hash.setdefault("built_in_only", False)
    return hashlib.sha256(canonical_yaml(fields_for_hash)).hexdigest()  # noqa: TID251 - production raw SHA-256 owner


def _dump_yaml_safe(
    yaml_rt: YAML,
    path: Path,
    data: dict[str, Any],
    errors: list[str],
    *,
    what: str,
) -> None:
    """Write *data* to *path* via a ``BytesIO`` round-trip, recording failures.

    Collapses the ``io.BytesIO -> yaml.dump -> write_bytes`` block that was
    previously repeated 4x across :func:`migrate_v1_to_v2`'s three phases and
    :func:`repair_v2_synthesis_manifest_defaults` into one S1192-clean
    helper. Any failure is appended to *errors* as ``"Failed to write
    {what}: {exc}"`` rather than raised, matching the original per-site
    ``except Exception`` guards (each migration phase/site must keep
    reporting partial progress via ``MigrationResult.errors`` instead of
    aborting the whole migration on one bad write).
    """
    try:
        import io as _io

        buf = _io.BytesIO()
        yaml_rt.dump(data, buf)
        path.write_bytes(buf.getvalue())
    except Exception as exc:  # noqa: BLE001 - migration writers report failures via `errors`, never raise past their MigrationResult contract
        errors.append(f"Failed to write {what}: {exc}")


def repair_v2_synthesis_manifest_defaults(
    bundle_root: Path,
    dry_run: bool = False,
) -> MigrationResult:
    """Repair current v2 manifests that predate verifier-visible defaults."""
    _yaml = YAML()
    _yaml.default_flow_style = False
    _yaml.explicit_start = False

    manifest_path = bundle_root / "synthesis-manifest.yaml"
    if not manifest_path.exists():
        return MigrationResult(changes_made=[], errors=[], from_version=2, to_version=2)

    try:
        manifest_data = _yaml.load(manifest_path)
    except Exception as exc:  # noqa: BLE001
        return MigrationResult(
            changes_made=[],
            errors=[f"Failed to load synthesis-manifest.yaml: {exc}"],
            from_version=2,
            to_version=2,
        )

    if not isinstance(manifest_data, dict) or manifest_data.get("schema_version") != "2":
        return MigrationResult(changes_made=[], errors=[], from_version=2, to_version=2)
    if "built_in_only" in manifest_data:
        return MigrationResult(changes_made=[], errors=[], from_version=2, to_version=2)

    stored_hash = manifest_data.get("manifest_hash")
    if not isinstance(stored_hash, str):
        return MigrationResult(
            changes_made=[],
            errors=["Cannot repair synthesis-manifest.yaml: manifest_hash is missing or invalid."],
            from_version=2,
            to_version=2,
        )

    legacy_fields_for_hash = {
        k: v for k, v in manifest_data.items() if k != "manifest_hash"
    }
    legacy_hash = hashlib.sha256(canonical_yaml(legacy_fields_for_hash)).hexdigest()  # noqa: TID251 - production raw SHA-256 owner
    if legacy_hash != stored_hash:
        return MigrationResult(
            changes_made=[],
            errors=[
                "Cannot repair synthesis-manifest.yaml: existing manifest_hash does not "
                "match the pre-built_in_only v2 payload."
            ],
            from_version=2,
            to_version=2,
        )

    manifest_data["built_in_only"] = False
    manifest_data["manifest_hash"] = _compute_v2_synthesis_manifest_hash(manifest_data)
    changes_made = [str(manifest_path)]

    if not dry_run:
        write_errors: list[str] = []
        _dump_yaml_safe(
            _yaml, manifest_path, manifest_data, write_errors, what="synthesis-manifest.yaml"
        )
        if write_errors:
            return MigrationResult(
                changes_made=[],
                errors=write_errors,
                from_version=2,
                to_version=2,
            )

    return MigrationResult(
        changes_made=changes_made,
        errors=[],
        from_version=2,
        to_version=2,
    )


def _register_migration(
    from_version: int,
    fn: Callable[[Path, bool], MigrationResult],
) -> None:
    """Register a migration function for a given from-version.

    Args:
        from_version: The bundle schema version this migration upgrades from.
        fn: Callable accepting (bundle_root, dry_run) and returning MigrationResult.
    """
    _MIGRATIONS[from_version] = fn


def migrate_v1_to_v2(bundle_root: Path, dry_run: bool = False) -> MigrationResult:
    """Migrate a v1 charter bundle to v2 format (Phase 7 provenance hardening).

    Adds the mandatory Phase 7 fields to provenance sidecars and the
    synthesis manifest, and stamps ``bundle_schema_version: 2`` in
    ``charter.yaml``'s ``metadata:`` section (consolidate-charter-bundle
    #2773 re-homed this from the retired ``metadata.yaml``; see the body).

    Sentinel values are used for fields that cannot be reconstructed from
    the v1 state:
    - ``synthesizer_version: "(pre-phase7-migration)"``
    - ``synthesis_run_id: "(pre-phase7-migration)"``
    - ``produced_at: <file mtime in ISO 8601 UTC>`` (or sentinel on OSError)
    - ``source_input_ids: <copy of existing source_urns>``
    - ``corpus_snapshot_id: "(none)"`` (only when the existing value is null)

    Args:
        bundle_root: Path to the ``.kittify/charter/`` directory.
        dry_run: If True, compute and report changes without writing any files.

    Returns:
        MigrationResult with ``changes_made`` listing every file that was (or
        would be) updated.  ``errors`` is empty on success.
    """
    _yaml = YAML()
    _yaml.default_flow_style = False
    _yaml.explicit_start = False

    changes_made: list[str] = []
    errors: list[str] = []

    # Three independent sequential phases (each an (changes, errors) pair,
    # merged below) — extracted to keep this orchestrator's cognitive
    # complexity within the ruff C901 limit (15).
    sidecar_changes, sidecar_errors = _migrate_provenance_sidecars(bundle_root, dry_run, _yaml)
    changes_made.extend(sidecar_changes)
    errors.extend(sidecar_errors)

    manifest_changes, manifest_errors = _migrate_synthesis_manifest(bundle_root, dry_run, _yaml)
    changes_made.extend(manifest_changes)
    errors.extend(manifest_errors)

    charter_changes, charter_errors = _stamp_charter_bundle_version(bundle_root, dry_run, _yaml)
    changes_made.extend(charter_changes)
    errors.extend(charter_errors)

    return MigrationResult(
        changes_made=changes_made,
        errors=errors,
        from_version=1,
        to_version=2,
    )


def _apply_v2_sidecar_defaults(data: dict[str, Any], sidecar_path: Path) -> None:
    """Mutate *data* in place with v2 provenance-sidecar field defaults.

    Extracted from :func:`_migrate_provenance_sidecars` (itself extracted
    from :func:`migrate_v1_to_v2`, phase 1 of 3) to keep cognitive
    complexity within the ruff C901 limit (15). See that function's
    docstring for the sentinel-value semantics.
    """
    data.setdefault("synthesizer_version", PRE_PHASE7_MIGRATION_SENTINEL)
    data.setdefault("synthesis_run_id", PRE_PHASE7_MIGRATION_SENTINEL)

    if "produced_at" not in data:
        try:
            mtime = sidecar_path.stat().st_mtime
            data["produced_at"] = from_epoch(mtime).isoformat()
        except OSError:
            data["produced_at"] = PRE_PHASE7_MIGRATION_SENTINEL

    if "source_input_ids" not in data:
        data["source_input_ids"] = list(data.get("source_urns", []))

    if data.get("corpus_snapshot_id") is None:
        data["corpus_snapshot_id"] = "(none)"

    data["schema_version"] = "2"


def _migrate_provenance_sidecars(
    bundle_root: Path, dry_run: bool, yaml_rt: YAML
) -> tuple[list[str], list[str]]:
    """Migrate every v1 provenance sidecar under ``<bundle_root>/provenance`` to v2.

    Extracted from :func:`migrate_v1_to_v2` (phase 1 of 3) to keep its
    cognitive complexity within the ruff C901 limit (15); see that
    function's docstring for the sentinel-value semantics. Returns
    ``(changes_made, errors)`` for the caller to merge.
    """
    changes_made: list[str] = []
    errors: list[str] = []
    provenance_dir = bundle_root / "provenance"
    if not provenance_dir.exists():
        return changes_made, errors

    for sidecar_path in sorted(provenance_dir.glob("*.yaml")):
        try:
            data = yaml_rt.load(sidecar_path)
        except Exception as exc:  # noqa: BLE001 - per-sidecar load failure must not abort sibling sidecars; reported via `errors`
            errors.append(f"Failed to load sidecar {sidecar_path.name}: {exc}")
            continue

        if not isinstance(data, dict):
            errors.append(
                f"Sidecar {sidecar_path.name} is not a YAML mapping; skipping."
            )
            continue

        if data.get("schema_version") == "2":
            continue  # Already migrated — skip (idempotent).

        _apply_v2_sidecar_defaults(data, sidecar_path)
        changes_made.append(str(sidecar_path))
        if not dry_run:
            _dump_yaml_safe(
                yaml_rt, sidecar_path, data, errors, what=f"sidecar {sidecar_path.name}"
            )

    return changes_made, errors


def _migrate_synthesis_manifest(
    bundle_root: Path, dry_run: bool, yaml_rt: YAML
) -> tuple[list[str], list[str]]:
    """Migrate ``<bundle_root>/synthesis-manifest.yaml`` to v2 field defaults.

    Extracted from :func:`migrate_v1_to_v2` (phase 2 of 3) to keep its
    cognitive complexity within the ruff C901 limit (15). Returns
    ``(changes_made, errors)`` for the caller to merge.
    """
    changes_made: list[str] = []
    errors: list[str] = []
    manifest_path = bundle_root / "synthesis-manifest.yaml"
    if not manifest_path.exists():
        return changes_made, errors

    try:
        manifest_data = yaml_rt.load(manifest_path)
    except Exception as exc:  # noqa: BLE001 - load failure must still let phases 1/3 run; reported via `errors`
        errors.append(f"Failed to load synthesis-manifest.yaml: {exc}")
        return changes_made, errors

    if not isinstance(manifest_data, dict) or manifest_data.get("schema_version") == "2":
        return changes_made, errors

    manifest_data.setdefault("synthesizer_version", PRE_PHASE7_MIGRATION_SENTINEL)
    manifest_data.setdefault("mission_id", None)
    manifest_data.setdefault("built_in_only", False)
    manifest_data["schema_version"] = "2"
    manifest_data["manifest_hash"] = _compute_v2_synthesis_manifest_hash(manifest_data)

    changes_made.append(str(manifest_path))
    if not dry_run:
        _dump_yaml_safe(
            yaml_rt, manifest_path, manifest_data, errors, what="synthesis-manifest.yaml"
        )

    return changes_made, errors


def _stamp_charter_bundle_version(
    bundle_root: Path, dry_run: bool, yaml_rt: YAML
) -> tuple[list[str], list[str]]:
    """Stamp ``bundle_schema_version: 2`` into ``charter.yaml``'s ``metadata:`` section.

    Extracted from :func:`migrate_v1_to_v2` (phase 3 of 3) to keep its
    cognitive complexity within the ruff C901 limit (15).

    consolidate-charter-bundle (WP07 / T030): re-pointed from the retired
    ``<bundle_root>/metadata.yaml`` (folded into charter.yaml, then deleted)
    onto ``<bundle_root>/charter.yaml``'s ``metadata:`` section -- the SAME
    file/section :func:`get_bundle_schema_version` reads (this function is
    its counterpart writer). This module must not import ``charter.*``
    (dependency direction: charter -> charter.offering, never reversed), so the
    write is a plain round-trip YAML dict-walk, touching only the
    ``metadata.bundle_schema_version`` key -- every other top-level section
    (governance/directives/catalog/activation) loaded from disk is
    re-dumped unchanged. Guarded on existence: a project that has not run
    the WP07 fold migration yet has no charter.yaml, and this step
    correctly no-ops rather than fabricating one. Returns
    ``(changes_made, errors)`` for the caller to merge.
    """
    changes_made: list[str] = []
    errors: list[str] = []
    charter_yaml_path = bundle_root / "charter.yaml"
    if not charter_yaml_path.exists():
        return changes_made, errors

    try:
        charter_yaml_data = yaml_rt.load(charter_yaml_path)
    except Exception as exc:  # noqa: BLE001 - load failure must still let phases 1/2 have run; reported via `errors`
        errors.append(f"Failed to load charter.yaml: {exc}")
        return changes_made, errors

    if not isinstance(charter_yaml_data, dict):
        return changes_made, errors

    metadata_section = charter_yaml_data.get("metadata")
    if not isinstance(metadata_section, dict):
        metadata_section = {}
        charter_yaml_data["metadata"] = metadata_section

    if metadata_section.get("bundle_schema_version") == 2:
        return changes_made, errors

    metadata_section["bundle_schema_version"] = 2
    changes_made.append(str(charter_yaml_path))
    if not dry_run:
        _dump_yaml_safe(
            yaml_rt, charter_yaml_path, charter_yaml_data, errors, what="charter.yaml"
        )

    return changes_made, errors


_register_migration(1, migrate_v1_to_v2)


def run_migration(
    from_version: int, bundle_root: Path, dry_run: bool = False
) -> MigrationResult:
    """Run the registered migration for the given from-version.

    Args:
        from_version: The bundle schema version to migrate from.
        bundle_root: Path to the bundle root directory.
        dry_run: If True, report changes without applying them.

    Returns:
        MigrationResult describing what was changed.

    Raises:
        KeyError: If no migration is registered for from_version.
    """
    if from_version not in _MIGRATIONS:
        raise KeyError(f"No migration registered for bundle version {from_version}")
    fn = _MIGRATIONS[from_version]
    return fn(bundle_root, dry_run)


__all__ = [
    "CURRENT_BUNDLE_SCHEMA_VERSION",
    # MIN_READABLE_BUNDLE_SCHEMA, MAX_READABLE_BUNDLE_SCHEMA: demoted — no
    # cross-module src/ from-import callers (WP01 harden-dead-symbol-gate-01KW0RJR).
    "BundleCompatibilityStatus",
    # BundleCompatibilityResult: demoted — no cross-module src/ from-import
    # callers (WP01 harden-dead-symbol-gate-01KW0RJR).
    # MigrationResult: demoted — no cross-module src/ from-import callers (WP01).
    "check_bundle_compatibility",
    "get_bundle_schema_version",
    # migrate_v1_to_v2: demoted — no cross-module src/ from-import callers;
    # called only via register-arg dispatch (WP01 harden-dead-symbol-gate-01KW0RJR).
    "repair_v2_synthesis_manifest_defaults",
    "run_migration",
]
