"""Tests for charter.offering.versioning — compatibility registry and bundle schema version."""

from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.offering.versioning import (
    CURRENT_BUNDLE_SCHEMA_VERSION,
    MAX_READABLE_BUNDLE_SCHEMA,
    MIN_READABLE_BUNDLE_SCHEMA,
    PRE_PHASE7_MIGRATION_SENTINEL,
    BundleCompatibilityResult,
    BundleCompatibilityStatus,
    MigrationResult,
    _apply_v2_sidecar_defaults,
    _dump_yaml_safe,
    _migrate_provenance_sidecars,
    _migrate_synthesis_manifest,
    _stamp_charter_bundle_version,
    check_bundle_compatibility,
    get_bundle_schema_version,
    repair_v2_synthesis_manifest_defaults,
    run_migration,
)

pytestmark = pytest.mark.fast


def _write_v1_bundle(bundle_root: Path) -> Path:
    provenance_dir = bundle_root / "provenance"
    provenance_dir.mkdir(parents=True, exist_ok=True)
    (bundle_root / "metadata.yaml").write_text(
        "timestamp_utc: 2026-01-01T00:00:00Z\n",
        encoding="utf-8",
    )
    (provenance_dir / "directive-use-prs.yaml").write_text(
        "\n".join(
            [
                "schema_version: '1'",
                "artifact_urn: drg:directive:directive-use-prs",
                "artifact_kind: directive",
                "artifact_slug: directive-use-prs",
                f"artifact_content_hash: {'a' * 64}",
                f"inputs_hash: {'b' * 64}",
                "adapter_id: fixture",
                "adapter_version: 1.0.0",
                "generated_at: '2026-01-01T00:00:00Z'",
                "source_section: review_policy",
                "source_urns:",
                "  - drg:directive:DIR-001",
                "corpus_snapshot_id: null",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (bundle_root / "synthesis-manifest.yaml").write_text(
        "\n".join(
            [
                "schema_version: '1'",
                "created_at: '2026-01-01T00:00:00Z'",
                "run_id: '01TEST000000000000000000001'",
                "adapter_id: fixture",
                "adapter_version: 1.0.0",
                "artifacts: []",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return provenance_dir / "directive-use-prs.yaml"


# ---------------------------------------------------------------------------
# Constants sanity check
# ---------------------------------------------------------------------------


def test_constants_have_expected_values() -> None:
    assert CURRENT_BUNDLE_SCHEMA_VERSION == 2
    assert MIN_READABLE_BUNDLE_SCHEMA == 1
    assert MAX_READABLE_BUNDLE_SCHEMA == 2


# ---------------------------------------------------------------------------
# check_bundle_compatibility — status and exit_code
# ---------------------------------------------------------------------------


def test_compatible_current_version() -> None:
    result = check_bundle_compatibility(2)
    assert result.status == BundleCompatibilityStatus.COMPATIBLE
    assert result.exit_code == 0
    assert result.bundle_version == 2


def test_needs_migration_v1() -> None:
    result = check_bundle_compatibility(1)
    assert result.status == BundleCompatibilityStatus.NEEDS_MIGRATION
    assert result.exit_code == 1
    assert result.bundle_version == 1


def test_missing_version() -> None:
    result = check_bundle_compatibility(None)
    assert result.status == BundleCompatibilityStatus.MISSING_VERSION
    assert result.exit_code == 1
    assert result.bundle_version is None


def test_incompatible_new() -> None:
    result = check_bundle_compatibility(99)
    assert result.status == BundleCompatibilityStatus.INCOMPATIBLE_NEW
    assert result.exit_code == 1
    assert result.bundle_version == 99


def test_incompatible_old_zero() -> None:
    result = check_bundle_compatibility(0)
    assert result.status == BundleCompatibilityStatus.INCOMPATIBLE_OLD
    assert result.exit_code == 1
    assert result.bundle_version == 0


def test_incompatible_old_negative() -> None:
    result = check_bundle_compatibility(-1)
    assert result.status == BundleCompatibilityStatus.INCOMPATIBLE_OLD
    assert result.exit_code == 1
    assert result.bundle_version == -1


# ---------------------------------------------------------------------------
# check_bundle_compatibility — message content
# ---------------------------------------------------------------------------


def test_compatible_message_contains_version() -> None:
    result = check_bundle_compatibility(2)
    assert "2" in result.message
    assert "supported" in result.message.lower()


def test_needs_migration_message_contains_spec_kitty_upgrade() -> None:
    result = check_bundle_compatibility(1)
    assert "spec-kitty upgrade" in result.message


def test_missing_version_message_contains_spec_kitty_upgrade() -> None:
    result = check_bundle_compatibility(None)
    assert "spec-kitty upgrade" in result.message


def test_incompatible_old_message_contains_contact_support() -> None:
    result = check_bundle_compatibility(0)
    assert "contact support" in result.message.lower()
    assert str(MIN_READABLE_BUNDLE_SCHEMA) in result.message


def test_incompatible_new_message_contains_upgrade_cli() -> None:
    result = check_bundle_compatibility(99)
    assert "upgrade your cli" in result.message.lower()
    assert str(MAX_READABLE_BUNDLE_SCHEMA) in result.message


# ---------------------------------------------------------------------------
# check_bundle_compatibility — supported_min/max fields
# ---------------------------------------------------------------------------


def test_result_carries_supported_range() -> None:
    result = check_bundle_compatibility(2)
    assert result.supported_min == MIN_READABLE_BUNDLE_SCHEMA
    assert result.supported_max == MAX_READABLE_BUNDLE_SCHEMA


# ---------------------------------------------------------------------------
# BundleCompatibilityResult.is_compatible property
# ---------------------------------------------------------------------------


def test_is_compatible_property_true_for_compatible() -> None:
    result = check_bundle_compatibility(CURRENT_BUNDLE_SCHEMA_VERSION)
    assert result.is_compatible is True


def test_is_compatible_property_false_for_needs_migration() -> None:
    assert check_bundle_compatibility(1).is_compatible is False


def test_is_compatible_property_false_for_missing_version() -> None:
    assert check_bundle_compatibility(None).is_compatible is False


def test_is_compatible_property_false_for_incompatible_old() -> None:
    assert check_bundle_compatibility(0).is_compatible is False


def test_is_compatible_property_false_for_incompatible_new() -> None:
    assert check_bundle_compatibility(99).is_compatible is False


# ---------------------------------------------------------------------------
# BundleCompatibilityResult.needs_migration property
# ---------------------------------------------------------------------------


def test_needs_migration_property_true_for_needs_migration() -> None:
    assert check_bundle_compatibility(1).needs_migration is True


def test_needs_migration_property_true_for_missing_version() -> None:
    assert check_bundle_compatibility(None).needs_migration is True


def test_needs_migration_property_false_for_compatible() -> None:
    assert check_bundle_compatibility(CURRENT_BUNDLE_SCHEMA_VERSION).needs_migration is False


def test_needs_migration_property_false_for_incompatible_old() -> None:
    assert check_bundle_compatibility(0).needs_migration is False


def test_needs_migration_property_false_for_incompatible_new() -> None:
    assert check_bundle_compatibility(99).needs_migration is False


# ---------------------------------------------------------------------------
# BundleCompatibilityResult is frozen (immutable)
# ---------------------------------------------------------------------------


def test_result_is_frozen() -> None:
    result = check_bundle_compatibility(2)
    with pytest.raises((AttributeError, TypeError)):
        result.exit_code = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# get_bundle_schema_version
#
# consolidate-charter-bundle (WP07 / T030): the read target moved from
# ``<charter_dir>/metadata.yaml`` (top-level ``bundle_schema_version`` key,
# now RETIRED) to ``<charter_dir>/charter.yaml``'s ``metadata:`` section
# (``charter.activation.schemas.CharterYamlMetadata`` keeps this one field across the
# Landmine 2 retirement). Fixtures below write ``charter.yaml`` with the
# field nested under ``metadata:`` instead of ``metadata.yaml`` flat.
# ---------------------------------------------------------------------------


def test_returns_none_when_file_absent(tmp_path: Path) -> None:
    result = get_bundle_schema_version(tmp_path)
    assert result is None


def test_returns_none_when_field_absent(tmp_path: Path) -> None:
    charter_yaml = tmp_path / "charter.yaml"
    charter_yaml.write_text("metadata:\n  generated_at: '2026-01-01'\n")
    assert get_bundle_schema_version(tmp_path) is None


def test_returns_none_when_metadata_section_absent(tmp_path: Path) -> None:
    charter_yaml = tmp_path / "charter.yaml"
    charter_yaml.write_text("schema_version: '2.0.0'\n")
    assert get_bundle_schema_version(tmp_path) is None


def test_returns_int_when_present(tmp_path: Path) -> None:
    charter_yaml = tmp_path / "charter.yaml"
    charter_yaml.write_text("metadata:\n  bundle_schema_version: 2\n")
    result = get_bundle_schema_version(tmp_path)
    assert result == 2
    assert isinstance(result, int)


def test_returns_none_when_field_is_null(tmp_path: Path) -> None:
    charter_yaml = tmp_path / "charter.yaml"
    charter_yaml.write_text("metadata:\n  bundle_schema_version: null\n")
    assert get_bundle_schema_version(tmp_path) is None


def test_returns_none_when_field_is_string(tmp_path: Path) -> None:
    """String values (e.g. '2') should not be accepted — must be int."""
    charter_yaml = tmp_path / "charter.yaml"
    charter_yaml.write_text("metadata:\n  bundle_schema_version: '2'\n")
    assert get_bundle_schema_version(tmp_path) is None


def test_returns_none_when_file_is_not_a_mapping(tmp_path: Path) -> None:
    charter_yaml = tmp_path / "charter.yaml"
    charter_yaml.write_text("- item1\n- item2\n")
    assert get_bundle_schema_version(tmp_path) is None


def test_returns_correct_version_for_v1(tmp_path: Path) -> None:
    charter_yaml = tmp_path / "charter.yaml"
    charter_yaml.write_text("metadata:\n  bundle_schema_version: 1\n")
    assert get_bundle_schema_version(tmp_path) == 1


def test_ruamel_yaml_roundtrip_writes_integer(tmp_path: Path) -> None:
    """Verify ruamel.yaml serializes bundle_schema_version as an integer, not string."""
    from ruamel.yaml import YAML

    charter_yaml_path = tmp_path / "charter.yaml"
    yaml = YAML()
    yaml.dump({"metadata": {"bundle_schema_version": 2}, "other": "data"}, charter_yaml_path)

    # Read back and confirm type is int
    result = get_bundle_schema_version(tmp_path)
    assert result == 2
    assert isinstance(result, int)


# ---------------------------------------------------------------------------
# run_migration — error path
# ---------------------------------------------------------------------------


def test_run_migration_raises_key_error_for_unregistered_version(tmp_path: Path) -> None:
    with pytest.raises(KeyError, match="99"):
        run_migration(99, tmp_path)


def test_run_migration_v1_returns_migration_result(tmp_path: Path) -> None:
    """The v1 migration (WP03 implementation) returns a MigrationResult; does not raise."""
    # A metadata.yaml without bundle_schema_version is treated as v1 and gets stamped.
    (tmp_path / "metadata.yaml").write_text(
        "charter_slug: test-charter\n", encoding="utf-8"
    )
    # consolidate-charter-bundle (WP07 / T030): step 3 now stamps
    # charter.yaml's metadata section, not the retired metadata.yaml.
    (tmp_path / "charter.yaml").write_text(
        "schema_version: '2.0.0'\n", encoding="utf-8"
    )
    result = run_migration(1, tmp_path)
    assert isinstance(result, MigrationResult)
    assert result.from_version == 1
    assert result.to_version == 2
    assert result.errors == []
    assert any("charter.yaml" in change for change in result.changes_made)


def test_run_migration_v1_backfills_manifest_and_sidecar_fields(tmp_path: Path) -> None:
    from charter.activation.synthesizer.manifest import load_yaml, verify_manifest_hash

    _write_v1_bundle(tmp_path)

    result = run_migration(1, tmp_path)

    assert result.errors == []
    manifest_path = tmp_path / "synthesis-manifest.yaml"
    manifest = manifest_path.read_text(encoding="utf-8")
    sidecar = (tmp_path / "provenance" / "directive-use-prs.yaml").read_text(
        encoding="utf-8"
    )
    assert "synthesizer_version: (pre-phase7-migration)" in manifest
    assert "mission_id:" in manifest
    assert "built_in_only: false" in manifest
    verify_manifest_hash(load_yaml(manifest_path))
    assert "synthesizer_version: (pre-phase7-migration)" in sidecar
    assert "synthesis_run_id: (pre-phase7-migration)" in sidecar
    assert "source_input_ids:" in sidecar


def test_run_migration_v1_uses_sentinel_when_sidecar_stat_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target_sidecar = _write_v1_bundle(tmp_path)
    original_stat = Path.stat

    def _patched_stat(path: Path, *args, **kwargs):  # type: ignore[no-untyped-def]
        if path == target_sidecar:
            raise OSError("stat blocked for test")
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", _patched_stat)

    result = run_migration(1, tmp_path)

    assert result.errors == []
    sidecar = (tmp_path / "provenance" / "directive-use-prs.yaml").read_text(
        encoding="utf-8"
    )
    assert "produced_at: (pre-phase7-migration)" in sidecar


def _write_legacy_v2_manifest(
    bundle_root: Path,
    *,
    stored_hash: str | None = None,
) -> Path:
    import hashlib

    from charter.offering.yaml_utils import canonical_yaml
    from ruamel.yaml import YAML

    manifest_data = {
        "schema_version": "2",
        "mission_id": None,
        "created_at": "2026-01-01T00:00:00Z",
        "run_id": "01TEST000000000000000000001",
        "adapter_id": "fixture",
        "adapter_version": "1.0.0",
        "synthesizer_version": "3.2.6",
        "artifacts": [],
    }
    manifest_data["manifest_hash"] = stored_hash or hashlib.sha256(  # noqa: TID251 — legacy v2 manifest self-hash fixture
        canonical_yaml(manifest_data)
    ).hexdigest()

    manifest_path = bundle_root / "synthesis-manifest.yaml"
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.explicit_start = False
    yaml.dump(manifest_data, manifest_path)
    return manifest_path


def test_repair_v2_manifest_no_manifest_is_noop(tmp_path: Path) -> None:
    result = repair_v2_synthesis_manifest_defaults(tmp_path)

    assert result.changes_made == []
    assert result.errors == []


def test_repair_v2_manifest_load_error_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import charter.offering.versioning as versioning

    (tmp_path / "synthesis-manifest.yaml").write_text("schema_version: '2'\n")

    class BrokenYaml:
        default_flow_style = False
        explicit_start = False

        def load(self, _text: str) -> dict:
            raise RuntimeError("boom")

    monkeypatch.setattr(versioning, "YAML", BrokenYaml)

    result = repair_v2_synthesis_manifest_defaults(tmp_path)

    assert result.changes_made == []
    assert result.errors == ["Failed to load synthesis-manifest.yaml: boom"]


def test_repair_v2_manifest_ignores_non_v2_and_already_current(tmp_path: Path) -> None:
    from ruamel.yaml import YAML

    manifest_path = tmp_path / "synthesis-manifest.yaml"
    yaml = YAML()
    yaml.dump({"schema_version": "1"}, manifest_path)
    assert repair_v2_synthesis_manifest_defaults(tmp_path).changes_made == []

    yaml.dump({"schema_version": "2", "built_in_only": False}, manifest_path)
    assert repair_v2_synthesis_manifest_defaults(tmp_path).changes_made == []


def test_repair_v2_manifest_missing_hash_is_error(tmp_path: Path) -> None:
    from ruamel.yaml import YAML

    YAML().dump({"schema_version": "2"}, tmp_path / "synthesis-manifest.yaml")

    result = repair_v2_synthesis_manifest_defaults(tmp_path)

    assert result.changes_made == []
    assert result.errors == [
        "Cannot repair synthesis-manifest.yaml: manifest_hash is missing or invalid."
    ]


def test_repair_v2_manifest_hash_mismatch_is_error(tmp_path: Path) -> None:
    _write_legacy_v2_manifest(tmp_path, stored_hash="0" * 64)

    result = repair_v2_synthesis_manifest_defaults(tmp_path)

    assert result.changes_made == []
    assert result.errors == [
        "Cannot repair synthesis-manifest.yaml: existing manifest_hash does not "
        "match the pre-built_in_only v2 payload."
    ]


def test_repair_v2_manifest_writes_canonical_default(tmp_path: Path) -> None:
    from charter.activation.synthesizer.manifest import load_yaml, verify_manifest_hash
    from ruamel.yaml import YAML

    manifest_path = _write_legacy_v2_manifest(tmp_path)

    result = repair_v2_synthesis_manifest_defaults(tmp_path)

    assert result.changes_made == [str(manifest_path)]
    assert result.errors == []
    assert YAML().load(manifest_path)["built_in_only"] is False
    verify_manifest_hash(load_yaml(manifest_path))


def test_repair_v2_manifest_dry_run_reports_without_write(tmp_path: Path) -> None:
    from ruamel.yaml import YAML

    manifest_path = _write_legacy_v2_manifest(tmp_path)

    result = repair_v2_synthesis_manifest_defaults(tmp_path, dry_run=True)

    assert result.changes_made == [str(manifest_path)]
    assert result.errors == []
    assert "built_in_only" not in YAML().load(manifest_path)


def test_repair_v2_manifest_write_error_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest_path = _write_legacy_v2_manifest(tmp_path)
    original_write_bytes = Path.write_bytes

    def patched_write_bytes(path: Path, data: bytes) -> int:
        if path == manifest_path:
            raise OSError("disk full")
        return original_write_bytes(path, data)

    monkeypatch.setattr(Path, "write_bytes", patched_write_bytes)

    result = repair_v2_synthesis_manifest_defaults(tmp_path)

    assert result.changes_made == []
    assert result.errors == ["Failed to write synthesis-manifest.yaml: disk full"]


# ---------------------------------------------------------------------------
# MigrationResult dataclass
# ---------------------------------------------------------------------------


def test_migration_result_construction() -> None:
    result = MigrationResult(
        changes_made=["updated metadata.yaml"],
        errors=[],
        from_version=1,
        to_version=2,
    )
    assert result.from_version == 1
    assert result.to_version == 2
    assert result.changes_made == ["updated metadata.yaml"]
    assert result.errors == []


# ---------------------------------------------------------------------------
# No circular imports — charter.offering.versioning must not touch charter.*
# ---------------------------------------------------------------------------


def test_versioning_does_not_import_charter() -> None:
    """charter.offering.versioning must not introduce charter.* (the activation layer)
    into sys.modules.

    Mission ``charter-code-topology-01M152G1`` relocated the top-level
    ``doctrine`` package to ``src/charter/offering`` (C-004: ``offering`` MAY
    be imported by ``charter``'s activation side, never the reverse). Because
    ``charter.offering.versioning`` now physically lives at
    ``charter.offering.versioning``, an in-layer sibling import like
    ``charter.offering.yaml_utils`` textually starts with ``"charter"`` too —
    so the boundary this test enforces is "doesn't import the ACTIVATION
    side" (``charter.<non-offering>``), not merely "doesn't start with the
    string charter". Same self-reference exemption as
    ``test_charter_offering_does_not_import_activation.py``.
    """
    import sys

    # Trigger import (already loaded, but explicit)
    import charter.offering.versioning  # noqa: F401

    charter_modules = [k for k in sys.modules if k.startswith("charter")]
    # If charter's activation side was imported by versioning itself that
    # would be a violation. We can't guarantee charter isn't loaded by OTHER
    # tests, but we can inspect the module's __file__ and check it doesn't
    # directly import upward into charter's activation layer.
    import ast
    import inspect

    source = inspect.getsource(charter.offering.versioning)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module == "charter.offering" or node.module.startswith(
                    "charter.offering."
                ) or not node.module.startswith("charter"), (
                    f"charter.offering.versioning imports from charter's activation layer: {node.module}"
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name == "charter.offering" or alias.name.startswith(
                        "charter.offering."
                    ) or not alias.name.startswith("charter"), (
                        f"charter.offering.versioning imports charter's activation layer: {alias.name}"
                    )


def test_versioning_charter_filename_literals_match_charter_bundle() -> None:
    """charter.offering.versioning's hardcoded "charter.yaml"/"charter.md" filename
    literals must stay byte-for-byte in sync with charter.bundle's canonical
    CHARTER_YAML/CHARTER_MD constants.

    charter.offering.versioning cannot import charter.bundle directly (PERMANENT
    layering exception recorded in
    tests/architectural/charter_path_literal_allowlist.yaml for the
    get_bundle_schema_version and migrate_v1_to_v2 sites -- see
    test_versioning_does_not_import_charter above), so its filename literals
    are a second, independent copy of the same "charter.yaml"/"charter.md"
    names charter.bundle owns canonically. Nothing kept those two copies
    equal. This test replicates the same cross-boundary sync pattern already
    used by test_bundle_file_lists_stay_in_sync
    (tests/specify_cli/charter_freshness/test_computer.py) for
    charter_runtime/freshness/computer.py's own doctrine-adjacent literal:
    only the TEST is allowed to import both sides of the boundary; the
    product code under test never does.

    Self-mutation proof: renaming charter.bundle.CHARTER_YAML/CHARTER_MD's
    filename (e.g. "charter.yaml" -> "charter.yml") without updating the
    matching literal(s) hardcoded in src/charter/offering/versioning.py turns this
    red.
    """
    import ast
    import inspect

    import charter.offering.versioning
    from charter.bundle import CHARTER_MD, CHARTER_YAML

    source = inspect.getsource(charter.offering.versioning)
    tree = ast.parse(source)
    literals_found = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value in {"charter.yaml", "charter.md"}
    }

    assert literals_found, (
        "charter.offering.versioning no longer contains any 'charter.yaml'/'charter.md' "
        "string literal. If versioning.py was refactored to remove the "
        "permanent-layering literal entirely, the two src/charter/offering/versioning.py "
        "entries in tests/architectural/charter_path_literal_allowlist.yaml "
        "should be drained too."
    )

    canonical_names = {CHARTER_YAML.name, CHARTER_MD.name}
    stale = literals_found - canonical_names
    assert not stale, (
        f"charter.offering.versioning hardcodes filename literal(s) {sorted(stale)} that "
        f"no longer match charter.bundle's canonical basenames "
        f"{sorted(canonical_names)}. PERMANENT (layering): charter.offering.versioning "
        "cannot import charter.bundle to fix this automatically -- update the "
        "hardcoded literal(s) in src/charter/offering/versioning.py to match the rename."
    )


# ---------------------------------------------------------------------------
# WP03 T011 — direct unit tests for the helpers extracted from
# migrate_v1_to_v2 to keep its cognitive complexity within the ruff C901
# limit (15): _dump_yaml_safe, _apply_v2_sidecar_defaults,
# _migrate_provenance_sidecars, _migrate_synthesis_manifest,
# _stamp_charter_bundle_version.
# ---------------------------------------------------------------------------


def _rt_yaml() -> YAML:
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.explicit_start = False
    return yaml


class TestDumpYamlSafeDirect:
    def test_writes_data_and_records_no_error_on_success(self, tmp_path: Path) -> None:
        target = tmp_path / "out.yaml"
        errors: list[str] = []
        _dump_yaml_safe(_rt_yaml(), target, {"a": 1}, errors, what="out.yaml")

        assert errors == []
        assert target.exists()
        assert _rt_yaml().load(target) == {"a": 1}

    def test_write_failure_is_appended_to_errors_not_raised(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = tmp_path / "out.yaml"
        original_write_bytes = Path.write_bytes

        def _patched_write_bytes(path: Path, data: bytes) -> int:
            if path == target:
                raise OSError("disk full")
            return original_write_bytes(path, data)

        monkeypatch.setattr(Path, "write_bytes", _patched_write_bytes)
        errors: list[str] = []

        _dump_yaml_safe(_rt_yaml(), target, {"a": 1}, errors, what="out.yaml")

        assert errors == ["Failed to write out.yaml: disk full"]
        assert not target.exists()


class TestApplyV2SidecarDefaultsDirect:
    def test_fills_sentinel_defaults_and_stamps_schema_version(
        self, tmp_path: Path
    ) -> None:
        sidecar_path = tmp_path / "sidecar.yaml"
        sidecar_path.write_text("schema_version: '1'\n", encoding="utf-8")
        data: dict[str, object] = {"schema_version": "1", "source_urns": ["drg:directive:X"]}

        _apply_v2_sidecar_defaults(data, sidecar_path)

        assert data["schema_version"] == "2"
        assert data["synthesizer_version"] == PRE_PHASE7_MIGRATION_SENTINEL
        assert data["synthesis_run_id"] == PRE_PHASE7_MIGRATION_SENTINEL
        assert data["source_input_ids"] == ["drg:directive:X"]
        assert data["corpus_snapshot_id"] == "(none)"
        assert "produced_at" in data

    def test_preserves_existing_explicit_values(self, tmp_path: Path) -> None:
        sidecar_path = tmp_path / "sidecar.yaml"
        sidecar_path.write_text("schema_version: '1'\n", encoding="utf-8")
        data: dict[str, object] = {
            "schema_version": "1",
            "synthesizer_version": "3.2.6",
            "produced_at": "2026-01-01T00:00:00Z",
            "source_input_ids": ["already-set"],
            "corpus_snapshot_id": "snap-123",
        }

        _apply_v2_sidecar_defaults(data, sidecar_path)

        assert data["synthesizer_version"] == "3.2.6"
        assert data["produced_at"] == "2026-01-01T00:00:00Z"
        assert data["source_input_ids"] == ["already-set"]
        assert data["corpus_snapshot_id"] == "snap-123"

    def test_uses_sentinel_when_stat_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sidecar_path = tmp_path / "sidecar.yaml"
        sidecar_path.write_text("schema_version: '1'\n", encoding="utf-8")

        def _patched_stat(path: Path, *args: object, **kwargs: object) -> object:
            raise OSError("stat blocked for test")

        monkeypatch.setattr(Path, "stat", _patched_stat)
        data: dict[str, object] = {"schema_version": "1"}

        _apply_v2_sidecar_defaults(data, sidecar_path)

        assert data["produced_at"] == PRE_PHASE7_MIGRATION_SENTINEL


class TestMigrateProvenanceSidecarsDirect:
    def test_no_provenance_dir_is_a_noop(self, tmp_path: Path) -> None:
        changes, errors = _migrate_provenance_sidecars(tmp_path, False, _rt_yaml())
        assert changes == []
        assert errors == []

    def test_already_migrated_sidecar_is_skipped_idempotently(
        self, tmp_path: Path
    ) -> None:
        provenance_dir = tmp_path / "provenance"
        provenance_dir.mkdir()
        sidecar = provenance_dir / "already-v2.yaml"
        _rt_yaml().dump({"schema_version": "2"}, sidecar)

        changes, errors = _migrate_provenance_sidecars(tmp_path, False, _rt_yaml())

        assert changes == []
        assert errors == []

    def test_non_mapping_sidecar_is_reported_as_an_error(self, tmp_path: Path) -> None:
        provenance_dir = tmp_path / "provenance"
        provenance_dir.mkdir()
        (provenance_dir / "list.yaml").write_text("- a\n- b\n", encoding="utf-8")

        changes, errors = _migrate_provenance_sidecars(tmp_path, False, _rt_yaml())

        assert changes == []
        assert len(errors) == 1
        assert "not a YAML mapping" in errors[0]

    def test_dry_run_reports_changes_without_writing(self, tmp_path: Path) -> None:
        provenance_dir = tmp_path / "provenance"
        provenance_dir.mkdir()
        sidecar = provenance_dir / "v1.yaml"
        _rt_yaml().dump({"schema_version": "1"}, sidecar)

        changes, errors = _migrate_provenance_sidecars(tmp_path, True, _rt_yaml())

        assert changes == [str(sidecar)]
        assert errors == []
        assert _rt_yaml().load(sidecar) == {"schema_version": "1"}


class TestMigrateSynthesisManifestDirect:
    def test_no_manifest_is_a_noop(self, tmp_path: Path) -> None:
        changes, errors = _migrate_synthesis_manifest(tmp_path, False, _rt_yaml())
        assert changes == []
        assert errors == []

    def test_already_v2_manifest_is_a_noop(self, tmp_path: Path) -> None:
        manifest_path = tmp_path / "synthesis-manifest.yaml"
        _rt_yaml().dump({"schema_version": "2"}, manifest_path)

        changes, errors = _migrate_synthesis_manifest(tmp_path, False, _rt_yaml())

        assert changes == []
        assert errors == []

    def test_load_error_is_reported_and_does_not_raise(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        manifest_path = tmp_path / "synthesis-manifest.yaml"
        manifest_path.write_text("schema_version: '1'\n", encoding="utf-8")

        yaml_rt = _rt_yaml()

        def _broken_load(_path: Path) -> None:
            raise RuntimeError("boom")

        monkeypatch.setattr(yaml_rt, "load", _broken_load)

        changes, errors = _migrate_synthesis_manifest(tmp_path, False, yaml_rt)

        assert changes == []
        assert errors == ["Failed to load synthesis-manifest.yaml: boom"]

    def test_v1_manifest_gets_v2_defaults_and_hash(self, tmp_path: Path) -> None:
        manifest_path = tmp_path / "synthesis-manifest.yaml"
        _rt_yaml().dump({"schema_version": "1", "artifacts": []}, manifest_path)

        changes, errors = _migrate_synthesis_manifest(tmp_path, False, _rt_yaml())

        assert changes == [str(manifest_path)]
        assert errors == []
        written = _rt_yaml().load(manifest_path)
        assert written["schema_version"] == "2"
        assert written["synthesizer_version"] == PRE_PHASE7_MIGRATION_SENTINEL
        assert "manifest_hash" in written


class TestStampCharterBundleVersionDirect:
    def test_no_charter_yaml_is_a_noop(self, tmp_path: Path) -> None:
        changes, errors = _stamp_charter_bundle_version(tmp_path, False, _rt_yaml())
        assert changes == []
        assert errors == []

    def test_already_stamped_is_a_noop(self, tmp_path: Path) -> None:
        charter_yaml = tmp_path / "charter.yaml"
        _rt_yaml().dump({"metadata": {"bundle_schema_version": 2}}, charter_yaml)

        changes, errors = _stamp_charter_bundle_version(tmp_path, False, _rt_yaml())

        assert changes == []
        assert errors == []

    def test_missing_metadata_section_is_created(self, tmp_path: Path) -> None:
        charter_yaml = tmp_path / "charter.yaml"
        _rt_yaml().dump({"schema_version": "2.0.0"}, charter_yaml)

        changes, errors = _stamp_charter_bundle_version(tmp_path, False, _rt_yaml())

        assert changes == [str(charter_yaml)]
        assert errors == []
        written = _rt_yaml().load(charter_yaml)
        assert written["metadata"]["bundle_schema_version"] == 2
        assert written["schema_version"] == "2.0.0"  # other sections untouched

    def test_dry_run_reports_change_without_writing(self, tmp_path: Path) -> None:
        charter_yaml = tmp_path / "charter.yaml"
        _rt_yaml().dump({"metadata": {"generated_at": "2026-01-01"}}, charter_yaml)

        changes, errors = _stamp_charter_bundle_version(tmp_path, True, _rt_yaml())

        assert changes == [str(charter_yaml)]
        assert errors == []
        assert "bundle_schema_version" not in _rt_yaml().load(charter_yaml)["metadata"]
