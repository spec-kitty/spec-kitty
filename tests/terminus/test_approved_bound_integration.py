"""#5668 -- an attestation survives the run's own ``approved -> done`` record and the gate re-check (US2 scenario 6).

Three work packages' worth of behaviour meet here: the operator attestation (it supplies
the lane head of an approval that recorded none), the approved-bound claim check (it reads
that attestation as the bound) and the gate's lane re-check (it asks whether the lanes
moved since the claim). The run then records ``approved -> done`` for every work package,
which must not read as a new approval or disturb the attested bound.

Driven through the REAL ``spec-kitty consolidate`` CLI (a subprocess), both strategies and
both topologies, over the stamp-less approval of :func:`strip_approval_stamps`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.consolidation.approved_bound import APPROVED_REVIEWED, ATTEST_APPROVED_FLAG
from specify_cli.coordination.surface_resolver import resolve_status_surface
from tests.terminus.conftest import CoordMission, blob_present_at, run_terminus
from tests.terminus.mixed_lane_support import collapse
from tests.terminus.post_approval_support import WP01_PATH, WP02_PATH, Topology, build_post_approval_mission, strip_approval_stamps

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_BANNER = "Reconciliation verified"
_REASON = "read every line of lane-a; it is the reviewed work"


def _wp01_events(mission: CoordMission) -> list[dict[str, object]]:
    log = resolve_status_surface(mission.repo, mission.slug)
    events = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [event for event in events if event["wp_id"] == "WP01"]


@pytest.mark.parametrize("strategy", ["squash", "merge"])
@pytest.mark.parametrize("topology", ["lanes", "coord"])
def test_an_attested_approval_consolidates_and_is_recorded_before_the_done_record(tmp_path: Path, topology: Topology, strategy: str) -> None:
    mission = build_post_approval_mission(tmp_path, topology)
    strip_approval_stamps(mission, "WP01")

    result = run_terminus(
        mission,
        ["consolidate", "--mission", mission.slug, "--yes", "--strategy", strategy, ATTEST_APPROVED_FLAG, "WP01", "--attest-reason", _REASON],
    )
    flat = collapse(result.stdout + "\n" + result.stderr)

    assert result.returncode == 0, f"an attested approval must consolidate ({topology}/{strategy}):\n{flat}"
    assert _BANNER in flat
    assert blob_present_at(mission.repo, mission.target_branch, WP01_PATH) and blob_present_at(mission.repo, mission.target_branch, WP02_PATH)
    events = _wp01_events(mission)
    attested = [i for i, event in enumerate(events) if (event.get("policy_metadata") or {}).get("attestation") == APPROVED_REVIEWED]
    done = [i for i, event in enumerate(events) if event["from_lane"] == "approved" and event["to_lane"] == "done"]
    assert len(attested) == 1 and len(done) == 1, f"expected one attestation and one approved -> done record:\n{events}"
    assert attested[0] < done[0], "the attestation must precede the run's own done record"
    assert events[-1]["to_lane"] == "done", "WP01 ends done"
