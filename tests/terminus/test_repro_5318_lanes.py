"""Repro #5318 (LANES topology) -- the MISSION branch must be restored on a gate FAIL.

In LANES topology there is no coordination branch: the lanes fold into the
mission branch (``kitty/mission-...``) which is then squashed onto the target.
Pre-fix, a gate FAIL restored only the target and left the mission branch at the
lane-merge + bake commit, so the next run's first-parent authored range was
empty. Contract (FR-004/FR-006): the mission branch is back at its pre-run SHA.

Real ``spec-kitty consolidate`` CLI over the real-git LANES builder
(``tests/terminus/lanes_fixture.py``); real SHAs and a reflog vacuous-oracle guard.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.terminus.conftest import blob_present_at, plant_canceled_commit, run_terminus
from tests.terminus.lanes_fixture import build_lanes_mission
from tests.terminus.test_repro_5318 import flat, ref_shas, reflog_shas, restored_pairs, state_bookkeeping

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]


def test_5318_lanes_gate_fail_restores_the_mission_branch(tmp_path: Path) -> None:
    mission = build_lanes_mission(tmp_path, wps=("WP01", "WP02"), target_branch="develop", mid8="01M5318L")
    _, _, planted = plant_canceled_commit(mission, canceled_wp="WP03", carrier_wp="WP02")
    before = ref_shas(mission)
    reflog_before = len(reflog_shas(mission, mission.coord_branch))

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])
    output = flat(result)
    after = ref_shas(mission)

    assert result.returncode != 0, f"fixture precondition: the run must gate-FAIL. output={output}"
    assert not blob_present_at(mission.repo, mission.target_branch, planted), f"the canceled file reached the target. output={output}"
    assert after["target"] == before["target"], f"target not restored. output={output}"
    assert after["coord"] == before["coord"], (
        f"#5318: the mission branch was left at the lane-merge + bake commit ({before['coord']} -> {after['coord']}). output={output}"
    )
    assert {k: v for k, v in after.items() if k.startswith("lane:")} == {k: v for k, v in before.items() if k.startswith("lane:")}

    bookkeeping = state_bookkeeping(mission)
    assert bookkeeping is not None
    assert bookkeeping["mission_number_baked"] is False, f"state still claims the bake: {bookkeeping}"
    assert bookkeeping["completed_wps"] == [], f"state still claims completed WPs: {bookkeeping}"

    reflog = reflog_shas(mission, mission.coord_branch)
    assert len(reflog) - reflog_before >= 2, f"the mission branch must have advanced AND been restored; reflog={reflog}"
    assert reflog[0] == before["coord"], f"newest reflog entry is not the pre-run SHA; reflog={reflog}"
    pairs = restored_pairs(output, mission.coord_branch)
    assert pairs and pairs[0][0] != pairs[0][1], f"the report must name the mission-branch restore (post != pre). output={output}"
