"""Regression tests for FR-601, FR-602: .kittify/metadata.yaml version sync check.

Tests T7.1 and T7.2 from WP07 mission 079-post-555-release-hardening.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Import validator functions directly from the script
from scripts.release.validate_release import (
    ReleaseValidatorError,
    load_metadata_yaml_version,
    validate_metadata_yaml_version_sync,
)

pytestmark = [pytest.mark.integration]


def _write_kittify(tmp_path: Path, version: str) -> None:
    kittify_dir = tmp_path / ".kittify"
    kittify_dir.mkdir(parents=True, exist_ok=True)
    (kittify_dir / "metadata.yaml").write_text(
        f"spec_kitty:\n  version: {version}\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# T7.1 — Version mismatch fails
# ---------------------------------------------------------------------------


def test_version_mismatch_fails(tmp_path: Path) -> None:
    """FR-601: sync check raises on version mismatch."""
    _write_kittify(tmp_path, "3.1.1a3")

    issue = validate_metadata_yaml_version_sync("3.1.1", tmp_path)

    assert issue is not None
    assert "3.1.1" in issue.message
    assert "3.1.1a3" in issue.message
    assert "metadata.yaml" in issue.message or (issue.hint and "metadata.yaml" in issue.hint)


def test_version_mismatch_message_names_both_files(tmp_path: Path) -> None:
    """FR-602: error message names both files so the user knows what to fix."""
    _write_kittify(tmp_path, "3.0.0")

    issue = validate_metadata_yaml_version_sync("3.1.1a3", tmp_path)

    assert issue is not None
    full_text = issue.message + (issue.hint or "")
    assert "pyproject.toml" in full_text or "3.1.1a3" in full_text
    assert "metadata.yaml" in full_text or "3.0.0" in full_text


# ---------------------------------------------------------------------------
# T7.2 — Version match passes
# ---------------------------------------------------------------------------


def test_version_match_passes(tmp_path: Path) -> None:
    """FR-601: no issue returned when versions agree."""
    _write_kittify(tmp_path, "3.1.1")

    issue = validate_metadata_yaml_version_sync("3.1.1", tmp_path)

    assert issue is None


def test_prerelease_version_match_passes(tmp_path: Path) -> None:
    """Prerelease versions that match should not produce an issue."""
    _write_kittify(tmp_path, "3.1.1a3")

    issue = validate_metadata_yaml_version_sync("3.1.1a3", tmp_path)

    assert issue is None


# ---------------------------------------------------------------------------
# Edge-cases for load_metadata_yaml_version
# ---------------------------------------------------------------------------


def test_missing_kittify_directory_returns_error_issue(tmp_path: Path) -> None:
    """Missing .kittify/metadata.yaml surfaced as a ValidationIssue, not a crash."""
    issue = validate_metadata_yaml_version_sync("3.1.1", tmp_path)

    assert issue is not None
    assert "metadata.yaml" in issue.message.lower() or "kittify" in issue.message.lower()


def test_load_metadata_yaml_version_raises_on_missing_file(tmp_path: Path) -> None:
    """load_metadata_yaml_version raises ReleaseValidatorError when file absent."""
    with pytest.raises(ReleaseValidatorError, match="metadata.yaml"):
        load_metadata_yaml_version(tmp_path)


def test_load_metadata_yaml_version_raises_when_version_absent(tmp_path: Path) -> None:
    """load_metadata_yaml_version raises when spec_kitty.version key is missing."""
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify" / "metadata.yaml").write_text(
        "spec_kitty:\n  initialized_at: '2026-01-01'\n",
        encoding="utf-8",
    )
    with pytest.raises(ReleaseValidatorError, match="missing spec_kitty.version"):
        load_metadata_yaml_version(tmp_path)
