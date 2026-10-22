"""Tests for MissionIdentity.mission_id field and resolve_mission_identity() (T019 / FR-203)."""

from __future__ import annotations


import pytest
from ulid import ULID

from specify_cli.mission_metadata import MissionIdentity
# The tests and helpers shared with this suite's always-on lift live once, in
# ``tests/architectural/_lifted_mission_metadata.py`` (#5015); importing a test is what makes pytest collect it here.
from tests.architectural._lifted_mission_metadata import test_resolve_mission_identity_includes_mission_id as test_resolve_mission_identity_includes_mission_id
from tests.architectural._lifted_mission_metadata import (
    test_resolve_mission_identity_tolerates_legacy_mission as test_resolve_mission_identity_tolerates_legacy_mission,
)

pytestmark = pytest.mark.fast


# ---------------------------------------------------------------------------
# T3.4 — MissionIdentity exposes mission_id
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# T3.5 — Legacy mission (no mission_id) is tolerated
# ---------------------------------------------------------------------------


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
