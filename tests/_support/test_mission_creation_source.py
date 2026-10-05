"""The mission_creation source helper must cover every module of the family (#5634)."""

from __future__ import annotations

import pytest

from tests._support.mission_creation_source import (
    CORE_DIR,
    DECISIONS,
    FACADE,
    LEAVES,
    MISSION_CREATION_MODULE_PATHS,
    family_source,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_helper_lists_every_mission_creation_module_on_disk() -> None:
    on_disk = set(CORE_DIR.glob("mission_creation*.py"))
    assert set(MISSION_CREATION_MODULE_PATHS) == on_disk
    assert FACADE in on_disk
    assert DECISIONS in on_disk


def test_leaves_are_the_family_minus_facade_and_decisions() -> None:
    assert set(LEAVES) == set(MISSION_CREATION_MODULE_PATHS) - {FACADE, DECISIONS}
    assert LEAVES, "the split produced no leaf modules"


def test_family_source_strips_the_routing_qualifier() -> None:
    """Structural pins match bare ``Name`` calls; a surviving ``_mc.`` hides a routed call from them."""
    source = family_source()
    assert "_mc." not in source
    assert "def create_mission_core(" in source
