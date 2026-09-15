"""Tests for MissionIdentity.mission_id field and resolve_mission_identity() (T019 / FR-203)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from ulid import ULID

from specify_cli.mission_metadata import MissionIdentity, resolve_mission_identity

pytestmark = pytest.mark.fast


def _write_meta(feature_dir: Path, meta: dict) -> None:
    """Write a minimal meta.json to the feature directory."""
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# T3.4 — MissionIdentity exposes mission_id
# ---------------------------------------------------------------------------


def test_resolve_mission_identity_includes_mission_id(tmp_path: Path) -> None:
    """resolve_mission_identity() returns MissionIdentity with mission_id populated from meta.json."""
    ulid_val = str(ULID())
    feature_dir = tmp_path / "001-test-feature"
    _write_meta(feature_dir, {
        "mission_slug": "001-test-feature",
        "mission_number": "001",
        "mission_type": "software-dev",
        "slug": "001-test-feature",
        "friendly_name": "test feature",
        "target_branch": "main",
        "created_at": "2026-04-09T00:00:00+00:00",
        "mission_id": ulid_val,
    })

    identity = resolve_mission_identity(feature_dir)

    assert isinstance(identity, MissionIdentity)
    assert identity.mission_id is not None
    assert identity.mission_id == ulid_val
    assert len(identity.mission_id) == 26
    ULID.from_str(identity.mission_id)


# ---------------------------------------------------------------------------
# T3.5 — Legacy mission (no mission_id) is tolerated
# ---------------------------------------------------------------------------


def test_resolve_mission_identity_tolerates_legacy_mission(tmp_path: Path) -> None:
    """resolve_mission_identity() with no mission_id in meta.json returns mission_id=None (no exception)."""
    feature_dir = tmp_path / "001-legacy-feature"
    _write_meta(feature_dir, {
        "mission_slug": "001-legacy-feature",
        "mission_number": "001",
        "mission_type": "software-dev",
        "slug": "001-legacy-feature",
        "friendly_name": "legacy feature",
        "target_branch": "main",
        "created_at": "2025-01-01T00:00:00+00:00",
        # mission_id intentionally absent
    })

    identity = resolve_mission_identity(feature_dir)

    assert isinstance(identity, MissionIdentity)
    assert identity.mission_id is None  # No exception, just None


def test_mission_identity_dataclass_has_mission_id_field() -> None:
    """MissionIdentity dataclass has mission_id field with None default."""
    identity = MissionIdentity(
        mission_slug="001-test",
        mission_number="001",
        mission_type="software-dev",
    )
    assert hasattr(identity, "mission_id")
    assert identity.mission_id is None


def test_mission_identity_mission_id_can_be_set() -> None:
    """MissionIdentity.mission_id can be set to a ULID string."""
    ulid_val = str(ULID())
    identity = MissionIdentity(
        mission_slug="001-test",
        mission_number="001",
        mission_type="software-dev",
        mission_id=ulid_val,
    )
    assert identity.mission_id == ulid_val
