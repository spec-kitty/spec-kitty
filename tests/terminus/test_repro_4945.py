"""Repro #4945 — a re-lettered lane ships a REMOVED WP's code onto the target.

Mechanism (DEBRIEF §4, roots R3/R4): lane identity is positional
(``lane-{chr(...)}`` re-lettering on WP removal + re-finalize,
``lanes/compute.py``) rather than bound to the persisted git branch. When a WP is
removed and lanes are re-lettered, the removed WP's real commit still rides a
surviving lane's history, and ``spec-kitty merge`` consolidates it — exit 0, no
tree-vs-claim post-condition. Backstopped by S-D (WP06) + stable lane identity
(C-4). The observable defect is identical to the terminus invariant: a removed
WP's commit is reachable from the target after an exit-0 merge.

RED-first: driven through the REAL ``spec-kitty merge`` CLI (no ``_run_git`` /
subprocess mocking); approved SHAs come from lane-branch tips (RN-Q3). Today the
removed commit is reachable → ``xfail(strict=True)``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.terminus.conftest import (
    build_coord_mission,
    patch_ids_in_window,
    plant_canceled_commit,
    run_terminus,
    sha_reachable,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def test_4945_re_lettered_lane_must_not_ship_removed_wp_code(tmp_path: Path) -> None:
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8="01M4945A")
    pre_target = mission.rev(mission.target_branch)
    # WP03 was removed; its code still rides the surviving WP02 lane's history.
    removed_sha, removed_pid = plant_canceled_commit(mission, canceled_wp="WP03", carrier_wp="WP02")
    approved = mission.approved_shas_from_lane_tips(["WP01", "WP02"])  # PRE-merge tips

    result = run_terminus(mission, ["merge", "--mission", mission.slug, "--strategy", "merge", "--yes"])

    if result.returncode == 0:
        for shas in approved.values():
            for sha in shas:
                assert sha_reachable(mission.repo, sha, mission.target_branch)
        window = patch_ids_in_window(mission.repo, pre_target, mission.target_branch)
        assert removed_pid not in window, (
            f"removed WP03 commit {removed_sha[:10]} (patch-id {removed_pid[:12]}) shipped to "
            f"{mission.target_branch} through a re-lettered/surviving lane while merge exited 0 (#4945)"
        )
    else:
        assert not sha_reachable(mission.repo, removed_sha, mission.target_branch)
