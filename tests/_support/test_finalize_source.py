"""The finalize source helper must cover every module of the family (#5627)."""

from __future__ import annotations

import pytest

from tests._support.finalize_source import AGENT_DIR, FINALIZE_MODULE_PATHS, finalize_family_source

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_helper_lists_every_finalize_module_on_disk() -> None:
    on_disk = set(AGENT_DIR.glob("mission_finalize*.py"))
    assert set(FINALIZE_MODULE_PATHS) == on_disk


def test_family_source_strips_the_routing_qualifier() -> None:
    """Structural pins match bare ``Name`` calls; a surviving ``_mf.`` hides a routed call from them."""
    assert "_mf." not in finalize_family_source()
