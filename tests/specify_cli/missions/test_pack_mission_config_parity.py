"""Pack ``mission.yaml`` must equal the copy the CLI runs (FR-023, SC-009, C-008).

``specify_cli.mission`` pins built-in mission types to the ``src`` copy, so the
pack copy is only trustworthy while it is byte-equal to it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.fast

REPO_ROOT = Path(__file__).resolve().parents[3]
MISSION_TYPES = ("software-dev", "documentation", "research", "plan")


@pytest.mark.parametrize("mission_type", MISSION_TYPES)
def test_pack_mission_yaml_equals_src_copy(mission_type: str) -> None:
    pack = REPO_ROOT / "packs" / "built-in" / "missions" / mission_type / "mission.yaml"
    src = REPO_ROOT / "src" / "specify_cli" / "missions" / mission_type / "mission.yaml"
    if not src.exists():
        pytest.skip("src copy retired; parity no longer applies")
    assert pack.read_bytes() == src.read_bytes()
