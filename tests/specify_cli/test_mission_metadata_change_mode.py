"""Tests for the change_mode field in mission metadata."""

from __future__ import annotations

import json

import pytest

from specify_cli.mission_metadata import (
    VALID_CHANGE_MODES,
    _normalize_change_mode,
    get_change_mode,
    load_meta,
    set_change_mode,
    validate_meta,
    write_meta,
)


pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _minimal_meta() -> dict:
    """Return a minimal valid meta dict with all required fields."""
    return {
        "slug": "test-feature",
        "mission_slug": "test-feature",
        "friendly_name": "Test Feature",
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-04-13T00:00:00+00:00",
    }


def _write_minimal_meta(feature_dir, extra=None):
    """Write a minimal valid meta.json, optionally merging *extra* keys."""
    meta = _minimal_meta()
    if extra:
        meta.update(extra)
    feature_dir.mkdir(parents=True, exist_ok=True)
    write_meta(feature_dir, meta)
    return meta


# ── validate_meta ────────────────────────────────────────────────────────


def test_validate_meta_without_change_mode_passes():
    meta = _minimal_meta()
    errors = validate_meta(meta)
    assert errors == []


def test_validate_meta_with_bulk_edit_passes():
    meta = _minimal_meta()
    meta["change_mode"] = "bulk_edit"
    errors = validate_meta(meta)
    assert errors == []


def test_validate_meta_with_invalid_change_mode_fails():
    meta = _minimal_meta()
    meta["change_mode"] = "yolo"
    errors = validate_meta(meta)
    assert len(errors) == 1
    assert "Invalid change_mode" in errors[0]
    assert "'yolo'" in errors[0]


# ── set_change_mode ──────────────────────────────────────────────────────


def test_set_change_mode_bulk_edit(tmp_path):
    _write_minimal_meta(tmp_path)
    result = set_change_mode(tmp_path, "bulk_edit")
    assert result["change_mode"] == "bulk_edit"
    # Round-trip: reload from disk
    reloaded = load_meta(tmp_path)
    assert reloaded["change_mode"] == "bulk_edit"


def test_set_change_mode_accepts_str_path(tmp_path):
    """A bare ``str`` feature_dir is coerced to Path and behaves identically
    to a Path argument (regression for #3436 -- the documented shell one-liner
    passes a string and must not raise ``TypeError``)."""
    _write_minimal_meta(tmp_path)
    result = set_change_mode(str(tmp_path), "bulk_edit")
    assert result["change_mode"] == "bulk_edit"
    # Round-trip: reload from disk to confirm the write actually landed.
    reloaded = load_meta(tmp_path)
    assert reloaded["change_mode"] == "bulk_edit"


def test_set_change_mode_str_and_path_equivalent(tmp_path):
    """str and Path inputs produce identical results."""
    path_dir = tmp_path / "as_path"
    str_dir = tmp_path / "as_str"
    _write_minimal_meta(path_dir)
    _write_minimal_meta(str_dir)

    via_path = set_change_mode(path_dir, "bulk_edit")
    via_str = set_change_mode(str(str_dir), "bulk_edit")

    assert via_path["change_mode"] == via_str["change_mode"] == "bulk_edit"


def test_set_change_mode_invalid_raises(tmp_path):
    _write_minimal_meta(tmp_path)
    with pytest.raises(ValueError, match="Invalid change_mode"):
        set_change_mode(tmp_path, "nope")


def test_set_change_mode_missing_meta_raises(tmp_path):
    # No meta.json on disk at all
    with pytest.raises(FileNotFoundError):
        set_change_mode(tmp_path, "bulk_edit")


# ── get_change_mode ──────────────────────────────────────────────────────


def test_get_change_mode_absent_returns_none(tmp_path):
    _write_minimal_meta(tmp_path)
    assert get_change_mode(tmp_path) is None


def test_get_change_mode_present_returns_value(tmp_path):
    _write_minimal_meta(tmp_path, extra={"change_mode": "bulk_edit"})
    assert get_change_mode(tmp_path) == "bulk_edit"


# ── round-trip preservation ──────────────────────────────────────────────


def test_change_mode_preserved_through_write_meta(tmp_path):
    """Ensure change_mode survives a write_meta round-trip without being dropped."""
    meta = _minimal_meta()
    meta["change_mode"] = "bulk_edit"
    tmp_path.mkdir(parents=True, exist_ok=True)
    write_meta(tmp_path, meta)

    reloaded = load_meta(tmp_path)
    assert reloaded["change_mode"] == "bulk_edit"

    # Write again (simulating another mutation) and verify persistence
    reloaded["target_branch"] = "develop"
    write_meta(tmp_path, reloaded)
    final = load_meta(tmp_path)
    assert final["change_mode"] == "bulk_edit"
    assert final["target_branch"] == "develop"


# ── _normalize_change_mode (WP01 repair helper) ──────────────────────────────


def test_normalize_change_mode_absent_is_noop():
    """No ``change_mode`` key → nothing to normalize, meta unchanged."""
    meta = _minimal_meta()
    dropped = _normalize_change_mode(meta)
    assert dropped is None
    assert "change_mode" not in meta


def test_normalize_change_mode_preserves_bulk_edit():
    """The canonical ``bulk_edit`` value is preserved (never widened away)."""
    meta = _minimal_meta()
    meta["change_mode"] = "bulk_edit"
    dropped = _normalize_change_mode(meta)
    assert dropped is None
    assert meta["change_mode"] == "bulk_edit"


@pytest.mark.parametrize(
    ("value", "expected_dropped"),
    [
        ("regular", "regular"),  # the specific retired legacy value (FR-001)
        ("yolo", "yolo"),  # any unknown string (FR-011)
        ("", ""),  # empty string
        ("BULK_EDIT", "BULK_EDIT"),  # case variant is NOT canonical
        (42, "42"),  # non-string / malformed (FR-011)
        (None, "None"),  # present-but-null
        (["bulk_edit"], "['bulk_edit']"),  # wrapped/malformed structure
        ({"mode": "bulk_edit"}, "{'mode': 'bulk_edit'}"),
    ],
)
def test_normalize_change_mode_drops_non_canonical(value, expected_dropped):
    """Every non-``bulk_edit`` value is normalized to ABSENT and the stringified
    dropped value is faithfully returned (fidelity, #4780)."""
    meta = _minimal_meta()
    meta["change_mode"] = value
    dropped = _normalize_change_mode(meta)
    assert dropped == expected_dropped
    assert "change_mode" not in meta


def test_normalize_change_mode_is_idempotent():
    """A second call after healing reports no change (NFR-002)."""
    meta = _minimal_meta()
    meta["change_mode"] = "regular"
    assert _normalize_change_mode(meta) == "regular"
    assert _normalize_change_mode(meta) is None


def test_normalize_change_mode_does_not_touch_other_fields():
    """Only ``change_mode`` is affected; sibling keys are left intact."""
    meta = _minimal_meta()
    meta["change_mode"] = "regular"
    _normalize_change_mode(meta)
    assert meta["mission_slug"] == "test-feature"
    assert meta["target_branch"] == "main"


def test_normalize_change_mode_does_not_widen_vocabulary(tmp_path):
    """Repair heals reads, but the write-guard/vocabulary stay locked to bulk_edit.

    The normalize helper is a *read-path* repair; it must not relax what
    ``set_change_mode`` will persist. ``VALID_CHANGE_MODES`` is unchanged and the
    write-guard still rejects the very value repair silently drops (FR-004/C-001).
    """
    assert set(VALID_CHANGE_MODES) == {"bulk_edit"}
    _write_minimal_meta(tmp_path)
    with pytest.raises(ValueError, match="Invalid change_mode"):
        set_change_mode(tmp_path, "regular")
