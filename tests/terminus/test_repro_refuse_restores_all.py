"""Repro -- a gate REFUSE on a fresh fold-all-lanes run restores EVERY branch.

All lanes are folded into the mission/coordination branch before consolidating,
so the approved lanes resolve no commits of their own and the gate REFUSEs
("no approved lane resolved any commits ... authored-blob set is empty") AFTER
the squash already advanced the target. Pre-fix nothing was restored and the
text falsely claimed "no refs/worktrees were mutated". Contract (FR-004/FR-009):
target AND coordination branch are back at their pre-run SHAs, the report shows
the coordination-branch restore, and the appended report never claims that
nothing was mutated. Since #5359 the gate's REFUSE path CAS-restores the target
itself before the rollback authority runs, so the report shows the target's
idempotent ``unchanged <target> (already at <pre>)`` line (as for a gate FAIL).

Real ``spec-kitty consolidate`` CLI over real git; real SHAs.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.terminus.conftest import build_coord_mission, fold_lanes_into_mission_branch, run_terminus
from tests.terminus.test_repro_5318 import assert_report_is_truthful, flat, ref_shas, restored_pairs

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]


def test_refuse_after_fold_all_lanes_restores_target_and_coordination(tmp_path: Path) -> None:
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8="01M5318F")
    fold_lanes_into_mission_branch(mission, ["WP01", "WP02"])
    before = ref_shas(mission)

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])
    output = flat(result)
    after = ref_shas(mission)

    assert result.returncode != 0, f"fixture precondition: the gate must REFUSE. output={output}"
    assert "authored-blob set is empty" in output, f"fixture precondition: the empty-authored-set REFUSE. output={output}"
    assert after["target"] == before["target"], f"target left advanced ({before['target']} -> {after['target']}). output={output}"
    assert after["coord"] == before["coord"], f"coordination branch left advanced ({before['coord']} -> {after['coord']}). output={output}"
    assert re.search(rf"unchanged\s+{re.escape(mission.target_branch)}\s+\(already at {before['target'][:7]}\)", output), (
        f"the report must show the target's idempotent 'unchanged (already at <pre>)' line (the #5359 gate restored it). output={output}"
    )
    assert restored_pairs(output, mission.coord_branch), f"the report must show the coordination-branch restore. output={output}"
    assert_report_is_truthful(output)
