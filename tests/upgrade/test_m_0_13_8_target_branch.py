"""Tests for target_branch migration (0.13.7 → 0.13.8)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.upgrade.migrations.m_0_13_8_target_branch import TargetBranchMigration

pytestmark = pytest.mark.fast


@pytest.fixture
def repo_with_features(tmp_path: Path) -> Path:
    """Create a test repository with multiple features."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    kitty_specs = repo_root / "kitty-specs"
    kitty_specs.mkdir()

    # Feature 020 - legacy feature without target_branch
    feature_020 = kitty_specs / "020-legacy-feature"
    feature_020.mkdir()
    meta_020 = {
        "feature_number": "020",
        "slug": "020-legacy-feature",
        "mission": "software-dev",
    }
    (feature_020 / "meta.json").write_text(json.dumps(meta_020, indent=2))

    # Feature 024 - legacy feature without target_branch
    feature_024 = kitty_specs / "024-another-feature"
    feature_024.mkdir()
    meta_024 = {
        "feature_number": "024",
        "slug": "024-another-feature",
        "mission": "software-dev",
    }
    (feature_024 / "meta.json").write_text(json.dumps(meta_024, indent=2))

    # Feature 025 - should auto-detect as 2.x from spec.md
    feature_025 = kitty_specs / "025-cli-event-log-integration"
    feature_025.mkdir()
    meta_025 = {
        "feature_number": "025",
        "slug": "025-cli-event-log-integration",
        "mission": "software-dev",
    }
    (feature_025 / "meta.json").write_text(json.dumps(meta_025, indent=2))

    # Add spec.md with target branch marker
    spec_025 = """# Feature 025: CLI Event Log Integration

**Target Branch**: 2.x

This feature targets the 2.x branch for SaaS platform development.
"""
    (feature_025 / "spec.md").write_text(spec_025)

    return repo_root


def test_detect_finds_features_without_target_branch(repo_with_features: Path):
    """Test migration detects features missing target_branch field."""
    migration = TargetBranchMigration()

    # Should detect that migration is needed
    needs_migration = migration.detect(repo_with_features)
    assert needs_migration is True


def test_detect_skips_when_all_have_target_branch(tmp_path: Path):
    """Test migration skips when all features have target_branch."""
    repo_root = tmp_path / "repo"
    kitty_specs = repo_root / "kitty-specs"
    feature_dir = kitty_specs / "020-feature"
    feature_dir.mkdir(parents=True)

    meta = {
        "feature_number": "020",
        "slug": "020-feature",
        "target_branch": "main",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2))

    migration = TargetBranchMigration()
    needs_migration = migration.detect(repo_root)
    assert needs_migration is False


def test_can_apply_returns_true(repo_with_features: Path):
    """Test migration can always be applied."""
    migration = TargetBranchMigration()

    can_apply, message = migration.can_apply(repo_with_features)
    assert can_apply is True
    assert message == ""


def test_apply_adds_target_branch_to_legacy_features(repo_with_features: Path):
    """Test migration adds target_branch='main' to legacy features."""
    migration = TargetBranchMigration()

    result = migration.apply(repo_with_features, dry_run=False)

    assert result.success is True
    assert len(result.changes_made) >= 2  # At least 020 and 024

    # Check Feature 020
    meta_020_file = repo_with_features / "kitty-specs" / "020-legacy-feature" / "meta.json"
    meta_020 = json.loads(meta_020_file.read_text())
    assert meta_020["target_branch"] == "main"

    # Check Feature 024
    meta_024_file = repo_with_features / "kitty-specs" / "024-another-feature" / "meta.json"
    meta_024 = json.loads(meta_024_file.read_text())
    assert meta_024["target_branch"] == "main"


def test_apply_detects_025_as_2x_target(repo_with_features: Path):
    """Test migration auto-detects Feature 025 as 2.x from spec.md."""
    migration = TargetBranchMigration()

    result = migration.apply(repo_with_features, dry_run=False)

    assert result.success is True

    # Check Feature 025
    meta_025_file = repo_with_features / "kitty-specs" / "025-cli-event-log-integration" / "meta.json"
    meta_025 = json.loads(meta_025_file.read_text())
    assert meta_025["target_branch"] == "2.x"

    # Should have a warning about auto-detection
    assert any("auto-detected target_branch=2.x" in warning for warning in result.warnings)


def test_apply_uses_primary_branch_as_default(
    repo_with_features: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """Features without explicit markers inherit the repo's primary branch."""
    monkeypatch.setattr(
        "specify_cli.upgrade.feature_meta.resolve_primary_branch",
        lambda _repo_root: "2.x",
    )

    migration = TargetBranchMigration()
    result = migration.apply(repo_with_features, dry_run=False)

    assert result.success is True

    meta_020 = json.loads((repo_with_features / "kitty-specs" / "020-legacy-feature" / "meta.json").read_text())
    meta_024 = json.loads((repo_with_features / "kitty-specs" / "024-another-feature" / "meta.json").read_text())

    assert meta_020["target_branch"] == "2.x"
    assert meta_024["target_branch"] == "2.x"


def test_apply_dry_run_does_not_modify_files(repo_with_features: Path):
    """Test dry run doesn't modify any files."""
    migration = TargetBranchMigration()

    # Read original meta files
    meta_020_before = (repo_with_features / "kitty-specs" / "020-legacy-feature" / "meta.json").read_text()

    result = migration.apply(repo_with_features, dry_run=True)

    assert result.success is True
    assert len(result.changes_made) >= 2

    # Verify file unchanged
    meta_020_after = (repo_with_features / "kitty-specs" / "020-legacy-feature" / "meta.json").read_text()
    assert meta_020_before == meta_020_after

    # Check dry run messages
    assert any("Would add" in change for change in result.changes_made)


def test_apply_skips_features_with_existing_target_branch(tmp_path: Path):
    """Test migration skips features that already have target_branch."""
    repo_root = tmp_path / "repo"
    kitty_specs = repo_root / "kitty-specs"

    # Feature already has target_branch
    feature_dir = kitty_specs / "020-feature"
    feature_dir.mkdir(parents=True)
    meta = {
        "feature_number": "020",
        "slug": "020-feature",
        "target_branch": "main",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2))

    migration = TargetBranchMigration()
    result = migration.apply(repo_root, dry_run=False)

    # Should succeed but make no changes
    assert result.success is True
    assert len(result.changes_made) == 0


def test_apply_handles_malformed_json(tmp_path: Path):
    """Test migration handles malformed JSON gracefully."""
    repo_root = tmp_path / "repo"
    kitty_specs = repo_root / "kitty-specs"

    # Create feature with malformed JSON
    feature_dir = kitty_specs / "020-broken"
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text("{invalid json")

    migration = TargetBranchMigration()
    result = migration.apply(repo_root, dry_run=False)

    # Should fail but report error
    assert result.success is False
    assert len(result.errors) == 1
    assert "Malformed JSON" in result.errors[0]


def test_apply_handles_missing_kitty_specs(tmp_path: Path):
    """Test migration handles missing kitty-specs directory."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    # No kitty-specs directory created

    migration = TargetBranchMigration()
    result = migration.apply(repo_root, dry_run=False)

    assert result.success is True
    assert "No features found" in result.changes_made[0]


def test_migration_preserves_json_formatting(repo_with_features: Path):
    """Test migration preserves pretty-printed JSON formatting."""
    migration = TargetBranchMigration()

    result = migration.apply(repo_with_features, dry_run=False)
    assert result.success is True

    # Check JSON is still pretty-printed
    meta_file = repo_with_features / "kitty-specs" / "020-legacy-feature" / "meta.json"
    content = meta_file.read_text()

    # Should have indentation
    assert "  " in content  # 2-space indent
    # Should end with newline
    assert content.endswith("\n")
    # Should be valid JSON
    meta = json.loads(content)
    assert "target_branch" in meta


def test_migration_metadata():
    """Test migration has correct metadata."""
    migration = TargetBranchMigration()

    assert migration.migration_id == "0.13.8_target_branch"
    assert migration.description == "Add target_branch field to feature metadata"
    assert migration.target_version == "0.13.8"


# --- #2479: meta.json reads routed onto the canonical load_meta reader ------
#
# The detect()/apply() reads now go through ``mission_metadata.load_meta``, so
# the malformed set is the canonical one (JSON syntax error, undecodable bytes,
# non-object top level). These pin the behaviour at the edges where the old
# inline ``json.loads`` diverged from it.


def _legacy_feature(repo_root: Path, raw: bytes) -> Path:
    feature_dir = repo_root / "kitty-specs" / "020-legacy"
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_bytes(raw)
    return feature_dir


@pytest.mark.parametrize("raw", [b"[1, 2]", b'"scalar"'], ids=["array", "scalar"])
def test_detect_skips_non_object_meta(tmp_path: Path, raw: bytes) -> None:
    """A non-object meta.json is malformed: detect() skips it rather than flagging it."""
    _legacy_feature(tmp_path, raw)

    assert TargetBranchMigration().detect(tmp_path) is False


def test_detect_skips_undecodable_meta(tmp_path: Path) -> None:
    """Non-UTF-8 bytes are malformed: detect() skips them instead of crashing."""
    _legacy_feature(tmp_path, b"\xff\xfe{")

    assert TargetBranchMigration().detect(tmp_path) is False


def test_apply_records_error_for_non_object_meta(tmp_path: Path) -> None:
    """A non-object meta.json is reported per mission instead of crashing apply()."""
    feature_dir = _legacy_feature(tmp_path, b"[1, 2]")

    result = TargetBranchMigration().apply(tmp_path, dry_run=False)

    assert result.success is False
    assert len(result.errors) == 1
    assert result.errors[0].startswith(f"Malformed JSON in {feature_dir.name}/meta.json:")
    assert (feature_dir / "meta.json").read_bytes() == b"[1, 2]"


def test_apply_reports_unreadable_meta_as_failed_update(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An I/O failure reading meta.json keeps the pre-routing "Failed to update" label."""
    feature_dir = _legacy_feature(tmp_path, b'{"slug": "020-legacy"}')
    meta_path = feature_dir / "meta.json"
    real_read_text = Path.read_text

    def _read_text(self: Path, encoding: str | None = None, errors: str | None = None) -> str:
        if self == meta_path:
            raise PermissionError(13, "Permission denied", str(self))
        return real_read_text(self, encoding=encoding, errors=errors)

    monkeypatch.setattr(Path, "read_text", _read_text)

    result = TargetBranchMigration().apply(tmp_path, dry_run=False)

    assert result.success is False
    assert len(result.errors) == 1
    assert result.errors[0].startswith(f"Failed to update {feature_dir.name}/meta.json:")
