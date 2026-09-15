"""Tests for null mission_number schema (WP02 / T012).

Covers:
- resolve_mission_identity reads null -> None
- resolve_mission_identity reads int -> int
- resolve_mission_identity reads legacy "042" string -> 42
- resolve_mission_identity rejects "pending" with clear ValueError
- create_mission_core writes mission_number: null (JSON null) for new missions
- The write path always produces null, never a string sentinel
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from specify_cli.mission_metadata import resolve_mission_identity
from tests._factories import provision_test_charter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _write_meta(feature_dir: Path, meta: dict[str, Any]) -> None:
    """Write a meta.json for test fixtures."""
    (feature_dir / "meta.json").write_text(
        json.dumps(meta, indent=2) + "\n",
        encoding="utf-8",
    )


def _base_meta(**overrides: Any) -> dict[str, Any]:
    """Minimal valid meta.json content."""
    base: dict[str, Any] = {
        "mission_id": "01KNXQS9ATWWFXS3K5ZJ9E5008",
        "slug": "083-foo-bar",
        "mission_slug": "083-foo-bar",
        "friendly_name": "foo bar",
        "purpose_tldr": "Deliver foo bar cleanly for the team.",
        "purpose_context": "This mission delivers foo bar so product and engineering can move forward with a clear outcome and shared understanding.",
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-04-11T08:00:00+00:00",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# T008 coercion tests — resolve_mission_identity reads meta.json
# ---------------------------------------------------------------------------


def test_null_reads_as_none(tmp_path: Path) -> None:
    """meta.json with mission_number: null reads as mission_number=None."""
    feature_dir = tmp_path / "083-foo-bar"
    feature_dir.mkdir()
    _write_meta(feature_dir, _base_meta(mission_number=None))

    identity = resolve_mission_identity(feature_dir)
    assert identity.mission_number is None


def test_int_reads_as_int(tmp_path: Path) -> None:
    """meta.json with mission_number: 42 reads as 42."""
    feature_dir = tmp_path / "083-foo-bar"
    feature_dir.mkdir()
    _write_meta(feature_dir, _base_meta(mission_number=42))

    identity = resolve_mission_identity(feature_dir)
    assert identity.mission_number == 42
    assert isinstance(identity.mission_number, int)


def test_legacy_string_with_leading_zeros_reads_as_int(tmp_path: Path) -> None:
    """Legacy "042" string reads as 42 (leading zeros stripped)."""
    feature_dir = tmp_path / "083-foo-bar"
    feature_dir.mkdir()
    _write_meta(feature_dir, _base_meta(mission_number="042"))

    identity = resolve_mission_identity(feature_dir)
    assert identity.mission_number == 42
    assert isinstance(identity.mission_number, int)


def test_legacy_string_007_reads_as_7(tmp_path: Path) -> None:
    """Legacy "007" reads as 7."""
    feature_dir = tmp_path / "083-foo-bar"
    feature_dir.mkdir()
    _write_meta(feature_dir, _base_meta(mission_number="007"))

    identity = resolve_mission_identity(feature_dir)
    assert identity.mission_number == 7


def test_legacy_string_without_leading_zeros(tmp_path: Path) -> None:
    """Plain "83" reads as 83."""
    feature_dir = tmp_path / "083-foo-bar"
    feature_dir.mkdir()
    _write_meta(feature_dir, _base_meta(mission_number="83"))

    identity = resolve_mission_identity(feature_dir)
    assert identity.mission_number == 83


def test_empty_string_reads_as_none(tmp_path: Path) -> None:
    """Empty string "" reads as None (per canonical matrix)."""
    feature_dir = tmp_path / "083-foo-bar"
    feature_dir.mkdir()
    _write_meta(feature_dir, _base_meta(mission_number=""))

    identity = resolve_mission_identity(feature_dir)
    assert identity.mission_number is None


def test_missing_key_reads_as_none(tmp_path: Path) -> None:
    """Missing mission_number key reads as None."""
    feature_dir = tmp_path / "083-foo-bar"
    feature_dir.mkdir()
    meta = _base_meta()
    meta.pop("mission_number", None)  # ensure absent
    _write_meta(feature_dir, meta)

    identity = resolve_mission_identity(feature_dir)
    assert identity.mission_number is None


def test_pending_sentinel_raises_value_error(tmp_path: Path) -> None:
    """String "pending" raises ValueError with actionable message."""
    feature_dir = tmp_path / "083-foo-bar"
    feature_dir.mkdir()
    _write_meta(feature_dir, _base_meta(mission_number="pending"))

    with pytest.raises(ValueError, match="pending"):
        resolve_mission_identity(feature_dir)


def test_unassigned_sentinel_raises_value_error(tmp_path: Path) -> None:
    """String "unassigned" raises ValueError."""
    feature_dir = tmp_path / "083-foo-bar"
    feature_dir.mkdir()
    _write_meta(feature_dir, _base_meta(mission_number="unassigned"))

    with pytest.raises(ValueError, match="unassigned"):
        resolve_mission_identity(feature_dir)


def test_tbd_sentinel_raises_value_error(tmp_path: Path) -> None:
    """String "TBD" raises ValueError."""
    feature_dir = tmp_path / "083-foo-bar"
    feature_dir.mkdir()
    _write_meta(feature_dir, _base_meta(mission_number="TBD"))

    with pytest.raises(ValueError, match="TBD"):
        resolve_mission_identity(feature_dir)


def test_float_type_raises_type_error(tmp_path: Path) -> None:
    """Float type raises TypeError."""
    feature_dir = tmp_path / "083-foo-bar"
    feature_dir.mkdir()
    # Write raw JSON with a float
    raw = json.dumps(_base_meta(mission_number=42.5)) + "\n"
    (feature_dir / "meta.json").write_text(raw, encoding="utf-8")

    with pytest.raises(TypeError):
        resolve_mission_identity(feature_dir)


# ---------------------------------------------------------------------------
# Write path: create_mission_core must emit null, not a string
# ---------------------------------------------------------------------------


@pytest.mark.git_repo
def test_create_mission_core_writes_null_mission_number(temp_repo: Path) -> None:
    """Creating a new mission writes mission_number: null (JSON null)."""
    from specify_cli.core.mission_creation import create_mission_core

    # WP04 fail-closed: create_mission_core requires a provisioned charter.
    # Seed the default mission_type_activations via the production
    # provisioner (same shared helper used across the mission-creation
    # test harness).
    provision_test_charter(temp_repo)

    result = create_mission_core(
        temp_repo,
        "foo-bar",
        allow_worktree_context=True,
        friendly_name="Foo Bar",
        purpose_tldr="Deliver foo bar cleanly for the team.",
        purpose_context="This mission delivers foo bar so product and engineering can move forward with a clear outcome and shared understanding.",
    )

    meta_path = result.feature_dir / "meta.json"
    assert meta_path.exists()
    meta_raw = meta_path.read_text(encoding="utf-8")
    meta = json.loads(meta_raw)

    # The field must be JSON null (None in Python)
    assert meta.get("mission_number") is None
    # Must NOT be a string sentinel
    assert not isinstance(meta.get("mission_number"), str)


@pytest.mark.git_repo
def test_create_mission_core_mission_number_field_is_none_in_result(temp_repo: Path) -> None:
    """MissionCreationResult.mission_number is None for new missions."""
    from specify_cli.core.mission_creation import create_mission_core

    # WP04 fail-closed: create_mission_core requires a provisioned charter.
    provision_test_charter(temp_repo)

    result = create_mission_core(
        temp_repo,
        "bar-baz",
        allow_worktree_context=True,
        friendly_name="Bar Baz",
        purpose_tldr="Deliver bar baz cleanly for the team.",
        purpose_context="This mission delivers bar baz so product and engineering can move forward with a clear outcome and shared understanding.",
    )

    assert result.mission_number is None


@pytest.mark.git_repo
def test_create_mission_core_backfills_mid8_from_mission_id(temp_repo: Path) -> None:
    """Creating a new mission writes ``mid8`` = ``mission_id[:8]`` (#3474).

    The directory name already embeds the mid8; meta.json must carry the same
    canonical value so it is the single identity source rather than the
    directory name.
    """
    from specify_cli.core.mission_creation import create_mission_core

    provision_test_charter(temp_repo)

    result = create_mission_core(
        temp_repo,
        "mid8-backfill",
        allow_worktree_context=True,
        friendly_name="Mid8 Backfill",
        purpose_tldr="Deliver the mid8 backfill cleanly for the team.",
        purpose_context="This mission backfills the mid8 meta field so product and engineering have one canonical identity source.",
    )

    meta = json.loads((result.feature_dir / "meta.json").read_text(encoding="utf-8"))
    mission_id = meta["mission_id"]
    assert isinstance(mission_id, str) and len(mission_id) >= 8
    # Canonical backfill: first 8 chars of the ULID (#3474).
    assert meta["mid8"] == mission_id[:8]
    # The directory name embeds the same mid8 — one derivation, no drift.
    assert result.feature_dir.name.endswith(f"-{meta['mid8']}")


@pytest.mark.git_repo
def test_new_mission_feature_dir_uses_human_slug_mid8(temp_repo: Path) -> None:
    """The feature directory name uses <human-slug>-<mid8> format."""
    from specify_cli.core.mission_creation import create_mission_core

    # WP04 fail-closed: create_mission_core requires a provisioned charter.
    provision_test_charter(temp_repo)

    result = create_mission_core(
        temp_repo,
        "my-feature",
        allow_worktree_context=True,
        friendly_name="My Feature",
        purpose_tldr="Deliver my feature cleanly for the team.",
        purpose_context="This mission delivers my feature so product and engineering can move forward with a clear outcome and shared understanding.",
    )

    # Directory name must NOT start with a 3-digit prefix
    dir_name = result.feature_dir.name
    assert not (len(dir_name) > 3 and dir_name[:3].isdigit() and dir_name[3] == "-"), f"Directory name '{dir_name}' still uses the old NNN-slug format"
    # Must end with a mid8 (8 alphanumeric chars) separated by a hyphen
    parts = dir_name.rsplit("-", 1)
    assert len(parts) == 2, f"Expected <slug>-<mid8> format, got '{dir_name}'"
    mid8_part = parts[1]
    assert len(mid8_part) == 8, f"Expected 8-char mid8, got '{mid8_part}'"
    assert mid8_part.isalnum(), f"mid8 must be alphanumeric, got '{mid8_part}'"
