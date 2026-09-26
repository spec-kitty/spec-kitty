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
    blob_present_at,
    build_coord_mission,
    output_names_content_fail,
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
    removed_sha, removed_pid, _planted = plant_canceled_commit(mission, canceled_wp="WP03", carrier_wp="WP02")
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


def test_4945_default_squash_must_not_ship_removed_wp_code(tmp_path: Path) -> None:
    """Default-squash variant of #4945 (NO ``--strategy``) — the DEFAULT flow.

    RED at HEAD: a removed WP's code rides the surviving carrier lane and the
    default squash consolidates it, exiting 0 with ``src/pkg/wp03_removed.py`` on
    the target. Squash preserves neither the lane-tip SHA nor the removed commit's
    patch-id, so the only sound observable is **blob presence**. Goes GREEN when
    WP03/WP05 land the closed-world blob-attribution axis (FAIL → CAS rollback →
    removed file absent)."""
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8="01M4945S")
    pre_target = mission.rev(mission.target_branch)
    _removed_sha, _removed_pid, planted_path = plant_canceled_commit(mission, canceled_wp="WP03", carrier_wp="WP02")

    result = run_terminus(mission, ["merge", "--mission", mission.slug, "--yes"])

    assert not blob_present_at(mission.repo, mission.target_branch, planted_path), (
        f"removed WP03 file {planted_path} SHIPPED to {mission.target_branch} under the DEFAULT squash at exit {result.returncode} (#5013)"
    )
    assert result.returncode != 0, "default squash must FAIL the content axis and exit non-zero"
    assert mission.rev(mission.target_branch) == pre_target, "on a content-axis FAIL the target must be CAS-rolled-back to its pre-merge base"
    assert output_names_content_fail(result), "the merge output must name the un-attributable content / reconciliation FAIL"
