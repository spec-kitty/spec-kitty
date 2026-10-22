"""Tests for the read_target_branch_from_meta primitive (FR-005 / #2139).

Red-first: before the primitive exists, all tests in this file fail with
ImportError.  After T020-T022 land, they must all pass (GREEN).

Design contract:
- field-absent  (meta.json missing OR target_branch key absent) → None
- read-failure  (corrupt JSON or I/O error)                     → MissionMetaReadError
                                                                   (fail-closed, never silent default)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.core.paths import MissionMetaReadError, read_target_branch_from_meta
from tests._support.eacces import deny_path_method

pytestmark = [pytest.mark.unit, pytest.mark.fast]


# ---------------------------------------------------------------------------
# Field-present cases
# ---------------------------------------------------------------------------


def test_field_present_returns_branch(tmp_path: Path) -> None:
    """When meta.json has target_branch, the primitive returns it as a string."""
    feature_dir = tmp_path / "mission"
    feature_dir.mkdir()
    (feature_dir / "meta.json").write_text(
        '{"mission_slug": "test", "target_branch": "feat/my-branch"}',
        encoding="utf-8",
    )

    result = read_target_branch_from_meta(feature_dir)

    assert result == "feat/my-branch"


def test_field_present_non_main_branch(tmp_path: Path) -> None:
    """Non-default target_branch values are returned verbatim."""
    feature_dir = tmp_path / "mission"
    feature_dir.mkdir()
    (feature_dir / "meta.json").write_text(
        '{"target_branch": "2.x"}', encoding="utf-8"
    )

    assert read_target_branch_from_meta(feature_dir) == "2.x"


# ---------------------------------------------------------------------------
# Field-absent cases (must return None, not a silent default)
# ---------------------------------------------------------------------------


def test_field_absent_in_valid_meta_returns_none(tmp_path: Path) -> None:
    """meta.json is present and valid JSON, but target_branch key is missing → None.

    RED pre-fix: the old code returned the fallback branch string.
    GREEN post-fix: primitive returns None; caller supplies the documented default.
    """
    feature_dir = tmp_path / "mission"
    feature_dir.mkdir()
    (feature_dir / "meta.json").write_text(
        '{"mission_slug": "test", "mission_id": "01KXXXXXXXXXXXXXXXXXXX0000"}',
        encoding="utf-8",
    )

    result = read_target_branch_from_meta(feature_dir)

    assert result is None, (
        "field-absent must return None so callers apply the documented default; "
        "returning a branch string here conflates absent-with-failed"
    )


def test_meta_file_absent_returns_none(tmp_path: Path) -> None:
    """meta.json does not exist at all → None (field-absent, not an error)."""
    feature_dir = tmp_path / "mission"
    feature_dir.mkdir()
    # No meta.json created

    result = read_target_branch_from_meta(feature_dir)

    assert result is None


def test_target_branch_null_in_meta_returns_none(tmp_path: Path) -> None:
    """target_branch explicitly set to null in JSON → None (treated as absent)."""
    feature_dir = tmp_path / "mission"
    feature_dir.mkdir()
    (feature_dir / "meta.json").write_text(
        '{"target_branch": null}', encoding="utf-8"
    )

    result = read_target_branch_from_meta(feature_dir)

    assert result is None


def test_target_branch_empty_string_in_meta_returns_none(tmp_path: Path) -> None:
    """target_branch explicitly set to empty string → None (treated as absent)."""
    feature_dir = tmp_path / "mission"
    feature_dir.mkdir()
    (feature_dir / "meta.json").write_text(
        '{"target_branch": ""}', encoding="utf-8"
    )

    result = read_target_branch_from_meta(feature_dir)

    assert result is None


# ---------------------------------------------------------------------------
# Read-failure cases — must raise MissionMetaReadError (fail-closed)
# ---------------------------------------------------------------------------


def test_corrupt_json_raises_mission_meta_read_error(tmp_path: Path) -> None:
    """meta.json exists but contains invalid JSON → MissionMetaReadError.

    RED pre-fix: the old code silently returned the fallback branch.
    GREEN post-fix: structured error is raised so the corruption is surfaced.
    """
    feature_dir = tmp_path / "mission"
    feature_dir.mkdir()
    (feature_dir / "meta.json").write_text("{not valid json", encoding="utf-8")

    with pytest.raises(MissionMetaReadError) as exc_info:
        read_target_branch_from_meta(feature_dir)

    err = exc_info.value
    assert "meta.json" in str(err), "error message must name the corrupt file"


def test_mission_meta_read_error_carries_path_and_cause(tmp_path: Path) -> None:
    """MissionMetaReadError exposes meta_path and cause attributes."""
    feature_dir = tmp_path / "mission"
    feature_dir.mkdir()
    (feature_dir / "meta.json").write_text("{broken", encoding="utf-8")

    with pytest.raises(MissionMetaReadError) as exc_info:
        read_target_branch_from_meta(feature_dir)

    err = exc_info.value
    assert err.meta_path == feature_dir / "meta.json"
    assert err.cause is not None


def test_non_object_json_raises_mission_meta_read_error(tmp_path: Path) -> None:
    """meta.json contains valid JSON but top level is an array → MissionMetaReadError."""
    feature_dir = tmp_path / "mission"
    feature_dir.mkdir()
    (feature_dir / "meta.json").write_text("[1, 2, 3]", encoding="utf-8")

    with pytest.raises(MissionMetaReadError):
        read_target_branch_from_meta(feature_dir)


def test_io_error_raises_mission_meta_read_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """I/O failure reading meta.json → MissionMetaReadError (fail-closed).

    RED pre-fix: the old code silently returned the fallback branch.
    GREEN post-fix: structured error is raised.
    """
    feature_dir = tmp_path / "mission"
    feature_dir.mkdir()
    meta_path = feature_dir / "meta.json"
    meta_path.write_text('{"target_branch": "main"}', encoding="utf-8")
    # Deny the read at the seam: root reads a chmod(0o200) file (#5691).
    for attr in ("read_text", "read_bytes"):
        deny_path_method(monkeypatch, attr, meta_path)

    with pytest.raises(MissionMetaReadError):
        read_target_branch_from_meta(feature_dir)
