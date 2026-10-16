"""Regression guard for #5814 -- consolidate-mission must skip a fully-canceled lane.

``spec-kitty orchestrator-api consolidate-mission`` previously had no
canceled-with-provenance exclusion: its lane loop merged EVERY lane in ``lanes.json``
into the mission branch and squashed onto the target, so a fully-canceled lane whose
work package committed content before it was canceled (with operator provenance) was
merged anyway -- the canceled code landed on the target at ``success: true`` while the
status log still recorded the work package as ``canceled``. The host
``spec-kitty consolidate`` skips such a lane (``consolidation/phase_advance.py``:
``if lane_fully_canceled(...): continue``); the orchestrator-api path now reuses the
same canonical predicate (``lanes.compute.lane_fully_canceled``) and excluded set
(``acceptably_canceled_wp_ids``) before its lane loop.

Reuses the allocator-faithful terminus harness (same one the #5668/#5722 sibling
``test_consolidate_mission_post_approval.py`` drives): ``WP01`` on ``lane-a`` commits
content, is approved, then reopened and canceled with operator provenance; ``WP02`` on
an independent ``lane-b`` is approved. Then the REAL ``orchestrator-api consolidate-mission``
runs. Asserted: the canceled ``WP01``'s content (``src/pkg/wp01.py``) is NOT on the
target -- the same outcome host ``consolidate`` produces -- while the approved survivor
``WP02`` still lands. Fixed in #5814; this is now a per-PR regression guard (runs beside
its sibling in the nightly integration/shard lanes).
"""

from __future__ import annotations

import subprocess

import pytest

from tests.terminus.canceled_dependency_support import WP01_PATH, WP02_PATH, build_canceled_dependency_mission
from tests.terminus.conftest import CoordMission, blob_present_at, run_terminus
from tests.terminus.rollback_harness import flat

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_TARGET = "develop"


def _consolidate_mission(mission: CoordMission) -> subprocess.CompletedProcess[str]:
    return run_terminus(mission, ["orchestrator-api", "consolidate-mission", "--mission", mission.slug, "--strategy", "squash"])


def test_consolidate_mission_must_not_land_fully_canceled_lane_content(tmp_path) -> None:  # noqa: ANN001 -- pytest tmp_path
    built = build_canceled_dependency_mission(tmp_path, wp01_final="canceled", depends=False, target_branch=_TARGET)
    mission = built.mission

    result = _consolidate_mission(mission)
    output = flat(result)

    # Fixture invariant: the approved survivor (WP02) is the proof the scenario reached a real
    # consolidation, so a PASS means "canceled content stayed off the target", not "nothing ran".
    assert blob_present_at(mission.repo, _TARGET, WP02_PATH) or result.returncode != 0, (
        f"fixture did not reach a real consolidation of the approved lane. output={output}"
    )

    assert not blob_present_at(mission.repo, _TARGET, WP01_PATH), (
        "ideal: orchestrator-api consolidate-mission must NOT land a fully-canceled lane's content on the target "
        f"(host consolidate skips it); got WP01's canceled content on {_TARGET} with rc={result.returncode} "
        f"-- canceled code shipped, the reviewer's rejection undone (#5814). output={output}"
    )
