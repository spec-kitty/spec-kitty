"""Tests for CharterBundleV2Migration (m_3_2_0rc35_charter_bundle_v2).

Covers:
- T018: detect / apply / idempotency / dry_run / metadata stamp
"""

from __future__ import annotations

from pathlib import Path

from ruamel.yaml import YAML

from specify_cli.upgrade.migrations.m_3_2_0rc35_charter_bundle_v2 import (
    CharterBundleV2Migration,
)
from specify_cli.upgrade.migrations.m_3_2_0rc35_charter_manifest_defaults_repair import (
    CharterManifestDefaultsRepair,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]
_yaml = YAML()
_yaml.default_flow_style = False
_yaml.explicit_start = False


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    import io
    buf = io.BytesIO()
    _yaml.dump(data, buf)
    path.write_bytes(buf.getvalue())


def _load_yaml(path: Path) -> dict:
    return _yaml.load(path)  # type: ignore[return-value]


def _write_minimal_charter_yaml(
    charter_dir: Path, bundle_schema_version: int | None = None
) -> None:
    """Write a minimal charter.yaml, optionally stamping ``metadata.bundle_schema_version``.

    consolidate-charter-bundle (WP07 / T030): ``charter.offering.versioning.
    get_bundle_schema_version`` now reads this file's ``metadata:`` section
    instead of the retired ``<charter_dir>/metadata.yaml`` top-level key —
    these Phase-7-provenance fixtures need a real ``charter.yaml`` on disk
    for the version oracle to see anything other than ``None``.
    ``bundle_schema_version=None`` omits the ``metadata:`` key entirely
    (the "predates this field" / v1 state).
    """
    document: dict = {
        "schema_version": "2.0.0",
        "catalog": {"mission": "", "template_set": "", "languages": [], "references": []},
    }
    if bundle_schema_version is not None:
        document["metadata"] = {"bundle_schema_version": bundle_schema_version}
    _write_yaml(charter_dir / "charter.yaml", document)


def _create_v1_bundle(project_path: Path) -> None:
    """Create a minimal v1 charter bundle under project_path/.kittify/charter/."""
    charter_dir = project_path / ".kittify" / "charter"

    # metadata.yaml — no bundle_schema_version field (treated as v1)
    _write_yaml(
        charter_dir / "metadata.yaml",
        {
            "timestamp_utc": "2026-01-01T00:00:00Z",
            "extracted_at": "2026-01-01T00:00:00Z",
        },
    )
    # charter.yaml WITHOUT a metadata.bundle_schema_version key — the
    # version oracle (get_bundle_schema_version) reads None, same v1 signal
    # the retired metadata.yaml-without-the-field used to give.
    _write_minimal_charter_yaml(charter_dir)

    # provenance sidecar — schema_version "1", missing v2 fields
    _write_yaml(
        charter_dir / "provenance" / "directive-use-prs.yaml",
        {
            "schema_version": "1",
            "artifact_urn": "drg:directive:directive-use-prs",
            "artifact_kind": "directive",
            "artifact_slug": "directive-use-prs",
            "artifact_content_hash": "a" * 64,
            "inputs_hash": "b" * 64,
            "adapter_id": "fixture",
            "adapter_version": "1.0.0",
            "generated_at": "2026-01-01T00:00:00Z",
            "source_section": "review_policy",
            "source_urns": ["drg:directive:DIR-001"],
            "corpus_snapshot_id": None,
            # Missing v2 fields: synthesizer_version, synthesis_run_id,
            #                    produced_at, source_input_ids
        },
    )

    # synthesis-manifest.yaml — schema_version "1", missing v2 fields
    _write_yaml(
        charter_dir / "synthesis-manifest.yaml",
        {
            "schema_version": "1",
            "created_at": "2026-01-01T00:00:00Z",
            "run_id": "01TEST000000000000000000001",
            "adapter_id": "fixture",
            "adapter_version": "1.0.0",
            "artifacts": [],
        },
    )


def _create_v2_bundle(project_path: Path) -> None:
    """Create a minimal v2 charter bundle under project_path/.kittify/charter/."""
    charter_dir = project_path / ".kittify" / "charter"

    _write_yaml(
        charter_dir / "metadata.yaml",
        {"bundle_schema_version": 2, "timestamp_utc": "2026-01-01T00:00:00Z"},
    )
    _write_minimal_charter_yaml(charter_dir, bundle_schema_version=2)

    _write_yaml(
        charter_dir / "provenance" / "directive-use-prs.yaml",
        {
            "schema_version": "2",
            "artifact_urn": "drg:directive:directive-use-prs",
            "artifact_kind": "directive",
            "artifact_slug": "directive-use-prs",
            "artifact_content_hash": "a" * 64,
            "inputs_hash": "b" * 64,
            "adapter_id": "fixture",
            "adapter_version": "1.0.0",
            "generated_at": "2026-01-01T00:00:00Z",
            "source_section": "review_policy",
            "source_urns": ["drg:directive:DIR-001"],
            "synthesizer_version": "3.2.0rc35",
            "synthesis_run_id": "01TEST000000000000000000001",
            "produced_at": "2026-01-01T00:00:00+00:00",
            "source_input_ids": ["drg:directive:DIR-001"],
            "corpus_snapshot_id": "(none)",
        },
    )

    # Compute a real manifest_hash for the v2 manifest.
    from charter.offering.yaml_utils import canonical_yaml
    import hashlib

    fields_for_hash = {
        "schema_version": "2",
        "mission_id": None,
        "created_at": "2026-01-01T00:00:00Z",
        "run_id": "01TEST000000000000000000001",
        "adapter_id": "fixture",
        "adapter_version": "1.0.0",
        "synthesizer_version": "3.2.0rc35",
        "artifacts": [],
        "built_in_only": False,
    }
    manifest_hash = hashlib.sha256(canonical_yaml(fields_for_hash)).hexdigest()  # noqa: TID251 — migration preserves existing manifest hash verbatim, not charter.hasher.hash_content() freshness

    _write_yaml(
        charter_dir / "synthesis-manifest.yaml",
        {
            "schema_version": "2",
            "mission_id": None,
            "created_at": "2026-01-01T00:00:00Z",
            "run_id": "01TEST000000000000000000001",
            "adapter_id": "fixture",
            "adapter_version": "1.0.0",
            "synthesizer_version": "3.2.0rc35",
            "manifest_hash": manifest_hash,
            "artifacts": [],
            "built_in_only": False,
        },
    )


def _create_legacy_v2_bundle_without_built_in_only(project_path: Path) -> None:
    """Create a v2 bundle from before manifest built_in_only was introduced."""
    _create_v2_bundle(project_path)

    import hashlib

    from charter.offering.yaml_utils import canonical_yaml

    manifest_path = (
        project_path / ".kittify" / "charter" / "synthesis-manifest.yaml"
    )
    manifest = _load_yaml(manifest_path)
    manifest.pop("built_in_only")
    manifest.pop("manifest_hash")
    manifest["manifest_hash"] = hashlib.sha256(  # noqa: TID251 — legacy v2 manifest self-hash fixture
        canonical_yaml(manifest)
    ).hexdigest()
    _write_yaml(manifest_path, manifest)


def _create_bundle_with_metadata_version(project_path: Path, version: int) -> None:
    """Create a charter bundle whose metadata advertises a specific version."""
    charter_dir = project_path / ".kittify" / "charter"
    _write_yaml(
        charter_dir / "metadata.yaml",
        {
            "bundle_schema_version": version,
            "timestamp_utc": "2026-01-01T00:00:00Z",
        },
    )
    _write_minimal_charter_yaml(charter_dir, bundle_schema_version=version)


# ---------------------------------------------------------------------------
# detect() tests
# ---------------------------------------------------------------------------


def test_detect_v1_bundle_returns_true(tmp_path: Path) -> None:
    """detect() returns True for a v1 bundle (no bundle_schema_version in metadata)."""
    _create_v1_bundle(tmp_path)
    migration = CharterBundleV2Migration()
    assert migration.detect(tmp_path) is True


def test_detect_v2_bundle_returns_false(tmp_path: Path) -> None:
    """detect() returns False when the bundle is already at v2."""
    _create_v2_bundle(tmp_path)
    migration = CharterBundleV2Migration()
    assert migration.detect(tmp_path) is False


def test_detect_current_v2_manifest_repair_returns_true(tmp_path: Path) -> None:
    """Current-version bundles still detect when the manifest repair is pending."""
    _create_legacy_v2_bundle_without_built_in_only(tmp_path)

    assert CharterBundleV2Migration().detect(tmp_path) is True


def test_registry_includes_current_version_manifest_repair(tmp_path: Path) -> None:
    """Same-version upgrade runs must include the repair migration."""
    from specify_cli.upgrade.registry import MigrationRegistry

    _create_legacy_v2_bundle_without_built_in_only(tmp_path)

    migrations = MigrationRegistry.get_applicable(
        "3.2.0rc35",
        "3.2.0rc35",
        project_path=tmp_path,
    )

    assert any(
        migration.migration_id == CharterManifestDefaultsRepair.migration_id
        for migration in migrations
    )


def test_runner_repairs_current_v2_after_original_migration_was_recorded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Already-recorded original migration must not suppress same-version repair."""
    from charter.activation.synthesizer.manifest import load_yaml, verify_manifest_hash
    from specify_cli.upgrade.ledger import MigrationLedger, build_record
    from specify_cli.upgrade.runner import MigrationRunner

    _create_legacy_v2_bundle_without_built_in_only(tmp_path)
    # The original migration was already applied -- recorded in the LEDGER (the
    # applied authority post-cutover), NOT metadata.yaml. The same-version repair
    # migration must still run even though the original is settled.
    MigrationLedger(tmp_path).append(build_record(CharterBundleV2Migration(), "success"))

    runner = MigrationRunner(tmp_path)
    monkeypatch.setattr(runner.detector, "detect_version", lambda: "3.2.0rc35")
    monkeypatch.setattr(
        "specify_cli.upgrade.runner.MigrationRegistry.get_applicable",
        lambda _from, _to, project_path=None: [  # noqa: ARG005
            CharterBundleV2Migration(),
            CharterManifestDefaultsRepair(),
        ],
    )

    result = runner.upgrade("3.2.0rc35", include_worktrees=False)

    assert result.success is True
    assert result.migrations_skipped == [CharterBundleV2Migration.migration_id]
    assert result.migrations_applied == [CharterManifestDefaultsRepair.migration_id]
    manifest_path = tmp_path / ".kittify" / "charter" / "synthesis-manifest.yaml"
    assert _load_yaml(manifest_path)["built_in_only"] is False
    verify_manifest_hash(load_yaml(manifest_path))


def test_detect_no_charter_returns_false(tmp_path: Path) -> None:
    """detect() returns False when no charter directory exists."""
    migration = CharterBundleV2Migration()
    assert migration.detect(tmp_path) is False


def test_can_apply_rejects_incompatible_old_bundle(tmp_path: Path) -> None:
    """Version 0 bundles are too old and must not enter the v1->v2 migration."""
    _create_bundle_with_metadata_version(tmp_path, 0)
    can_apply, reason = CharterBundleV2Migration().can_apply(tmp_path)
    assert can_apply is False
    assert "predates the earliest supported version" in reason


# ---------------------------------------------------------------------------
# apply() tests
# ---------------------------------------------------------------------------


def test_apply_migrates_sidecar_to_v2(tmp_path: Path) -> None:
    """apply() adds all v2 fields to a v1 sidecar."""
    _create_v1_bundle(tmp_path)
    migration = CharterBundleV2Migration()
    result = migration.apply(tmp_path)

    assert len(result.changes_made) > 0, "Expected changes_made to be non-empty"
    assert len(result.errors) == 0, f"Unexpected errors: {result.errors}"

    # Sidecar should now parse cleanly as ProvenanceEntry v2.
    from charter.activation.synthesizer.synthesize_pipeline import ProvenanceEntry

    sidecar = _load_yaml(
        tmp_path / ".kittify" / "charter" / "provenance" / "directive-use-prs.yaml"
    )
    entry = ProvenanceEntry(**sidecar)
    assert entry.schema_version == "2"
    assert entry.synthesizer_version == "(pre-phase7-migration)"
    assert entry.corpus_snapshot_id == "(none)"
    assert entry.synthesis_run_id == "(pre-phase7-migration)"
    assert entry.source_input_ids == ["drg:directive:DIR-001"]


def test_apply_idempotent(tmp_path: Path) -> None:
    """Running apply() twice: second run reports no changes_made."""
    _create_v1_bundle(tmp_path)
    migration = CharterBundleV2Migration()
    migration.apply(tmp_path)
    result2 = migration.apply(tmp_path)
    assert result2.changes_made == [], (
        f"Second apply() should be a no-op; got: {result2.changes_made}"
    )


def test_apply_updates_metadata_yaml(tmp_path: Path) -> None:
    """apply() stamps bundle_schema_version: 2 in metadata.yaml."""
    _create_v1_bundle(tmp_path)
    CharterBundleV2Migration().apply(tmp_path)

    from charter.offering.versioning import get_bundle_schema_version

    version = get_bundle_schema_version(tmp_path / ".kittify" / "charter")
    assert version == 2


def test_apply_manifest_gets_v2_fields(tmp_path: Path) -> None:
    """apply() upgrades synthesis-manifest.yaml to v2 with schema_version and manifest_hash."""
    from charter.activation.synthesizer.manifest import load_yaml, verify_manifest_hash

    _create_v1_bundle(tmp_path)
    CharterBundleV2Migration().apply(tmp_path)

    manifest_path = tmp_path / ".kittify" / "charter" / "synthesis-manifest.yaml"
    manifest = _load_yaml(manifest_path)
    assert manifest["schema_version"] == "2"
    assert "synthesizer_version" in manifest
    assert manifest["mission_id"] is None
    assert manifest["built_in_only"] is False
    assert len(manifest["manifest_hash"]) == 64, (
        f"manifest_hash should be a 64-char hex digest, got: {manifest['manifest_hash']!r}"
    )
    verify_manifest_hash(load_yaml(manifest_path))


def test_apply_manifest_hash_verifies_after_v2_migration(tmp_path: Path) -> None:
    """Migrated manifests must satisfy the v2 self-hash contract."""
    from charter.activation.synthesizer.manifest import load_yaml, verify_manifest_hash

    _create_v1_bundle(tmp_path)
    CharterBundleV2Migration().apply(tmp_path)

    manifest = load_yaml(
        tmp_path / ".kittify" / "charter" / "synthesis-manifest.yaml"
    )
    verify_manifest_hash(manifest)


def test_apply_repairs_current_v2_manifest_missing_built_in_only(tmp_path: Path) -> None:
    """Current v2 bundles with legacy self-hashes get a canonical manifest repair."""
    from charter.activation.synthesizer.manifest import load_yaml, verify_manifest_hash

    _create_legacy_v2_bundle_without_built_in_only(tmp_path)

    result = CharterBundleV2Migration().apply(tmp_path)

    assert result.success is True
    assert result.errors == []
    assert result.changes_made == [
        str(tmp_path / ".kittify" / "charter" / "synthesis-manifest.yaml")
    ]
    manifest_path = tmp_path / ".kittify" / "charter" / "synthesis-manifest.yaml"
    manifest_data = _load_yaml(manifest_path)
    assert manifest_data["built_in_only"] is False
    verify_manifest_hash(load_yaml(manifest_path))


def test_apply_current_v2_manifest_repair_is_dry_run_safe(tmp_path: Path) -> None:
    """Dry-run reports the legacy v2 manifest repair without mutating the file."""
    _create_legacy_v2_bundle_without_built_in_only(tmp_path)
    manifest_path = tmp_path / ".kittify" / "charter" / "synthesis-manifest.yaml"

    result = CharterBundleV2Migration().apply(tmp_path, dry_run=True)

    assert result.success is True
    assert result.changes_made == [str(manifest_path)]
    assert "built_in_only" not in _load_yaml(manifest_path)


def test_apply_dry_run_makes_no_changes(tmp_path: Path) -> None:
    """apply(dry_run=True) reports what would change but does not mutate files."""
    _create_v1_bundle(tmp_path)
    migration = CharterBundleV2Migration()
    result = migration.apply(tmp_path, dry_run=True)

    assert len(result.changes_made) > 0, (
        "dry_run should still report the files that would change"
    )

    # Files must NOT have been mutated.
    sidecar = _load_yaml(
        tmp_path / ".kittify" / "charter" / "provenance" / "directive-use-prs.yaml"
    )
    assert sidecar.get("schema_version") == "1", (
        "dry_run must not write the sidecar; schema_version should remain '1'"
    )


def test_apply_no_charter_returns_success_no_changes(tmp_path: Path) -> None:
    """apply() on a project with no charter dir returns success with no changes."""
    migration = CharterBundleV2Migration()
    result = migration.apply(tmp_path)
    assert result.success is True
    assert result.changes_made == []
    assert result.errors == []


def test_apply_result_success_true(tmp_path: Path) -> None:
    """apply() result.success is True on a clean v1->v2 migration."""
    _create_v1_bundle(tmp_path)
    result = CharterBundleV2Migration().apply(tmp_path)
    assert result.success is True


def test_apply_incompatible_old_bundle_returns_error(tmp_path: Path) -> None:
    """apply() returns a structured failure instead of raising on version 0."""
    _create_bundle_with_metadata_version(tmp_path, 0)
    result = CharterBundleV2Migration().apply(tmp_path)
    assert result.success is False
    assert result.changes_made == []
    assert result.errors
    assert "predates the earliest supported version" in result.errors[0]
