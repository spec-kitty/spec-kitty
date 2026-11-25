"""Fixtures shared by the lane landing proof tests (#7747, #7848)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.lanes.landed_mission_support import Landed, make_landed


@pytest.fixture
def landed(tmp_path: Path) -> Landed:
    """Coordination branch, a lane that synced with it once and committed its product, a squash landing."""
    return make_landed(tmp_path)
