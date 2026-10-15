"""OPEN P0 #5814 -- red-first reproduction (nightly ``p0_repro`` lane only).

``spec-kitty orchestrator-api consolidate-mission`` has no canceled-with-provenance
exclusion: its lane loop merges EVERY lane in ``lanes.json`` into the mission branch
and squashes onto the target. So a fully-canceled lane whose work package committed
content before it was canceled (with operator provenance) is merged anyway -- the
canceled code lands on the target, the envelope answers ``success: true``, and the
status log still records the work package as ``canceled``. The host
``spec-kitty consolidate`` skips such a lane
(``consolidation/executor.py``: ``if _lane_fully_canceled(...): continue``); the
orchestrator-api path has no equivalent guard (``orchestrator_api/consolidation.py``'s
unconditional lane loop). ``main`` carries the #5722 approved-bound fix and still
reproduces this -- a canceled lane is not an approved lane, so that gate does not catch it.

Reuses the allocator-faithful terminus harness (same one the #5668/#5722 sibling
``test_consolidate_mission_post_approval.py`` drives): ``WP01`` on ``lane-a`` commits
content, is approved, then reopened and canceled with operator provenance; ``WP02`` on
an independent ``lane-b`` is approved. Then the REAL ``orchestrator-api consolidate-mission``
runs.

Ideal, asserted here and RED until #5814 is fixed: the canceled ``WP01``'s content
(``src/pkg/wp01.py``) must NOT be on the target after consolidate-mission -- the same
outcome host ``consolidate`` produces. Today it lands at ``success: true``. The fix PR
removes the ``p0_repro`` marker. See ADR 2026-07-17-1 and
docs/development/reference/red-main-and-release-readiness.md.
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


@pytest.mark.p0_repro(issue=5814)
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
