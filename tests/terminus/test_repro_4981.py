"""Repro #4981 — teardown runs without projecting post-bookkeeping commits.

Mechanism (DEBRIEF §4, root R2): coordination teardown captures the coord tip but
projects only ``status.events.jsonl`` / ``status.json`` at a fixed phase, then
``branch -D`` runs with no reachability check — so a commit reachable through a
lane but appended/consolidated after the bookkeeping checkpoint is dropped while
the merge still exits 0. Backstopped by S-B (coord teardown coupled to full
projection + coord-ref CAS) and detected by S-D (the reconciliation gate). WP06.

The observable is the epic invariant (S-D): after an exit-0 merge every approved
lane commit is reachable from target AND no excluded/removed commit is. This repro
uses a two-lane mission where a removed WP's commit rides the second lane's
history — teardown consolidates and ships it while dropping nothing visibly, and
the merge exits 0.

RED-first: driven through the REAL ``spec-kitty merge`` CLI (no ``_run_git`` /
subprocess mocking); approved SHAs from lane-branch tips (RN-Q3). Today the removed
commit reaches the target after an exit-0 merge → ``xfail(strict=True)``.
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


def test_4981_teardown_preserves_claim_and_excludes_removed_commit(tmp_path: Path) -> None:
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8="01M4981A")
    pre_target = mission.rev(mission.target_branch)
    removed_sha, removed_pid, _planted = plant_canceled_commit(mission, canceled_wp="WP81", carrier_wp="WP02")
    approved = mission.approved_shas_from_lane_tips(["WP01", "WP02"])  # PRE-merge tips

    result = run_terminus(mission, ["merge", "--mission", mission.slug, "--strategy", "merge", "--yes"])

    if result.returncode == 0:
        # No approved work dropped by teardown.
        for wp_id, shas in approved.items():
            for sha in shas:
                assert sha_reachable(mission.repo, sha, mission.target_branch), f"approved {wp_id} commit {sha[:10]} dropped during teardown (#4981)"
        # No removed commit projected onto target.
        window = patch_ids_in_window(mission.repo, pre_target, mission.target_branch)
        assert removed_pid not in window, (
            f"removed WP81 commit {removed_sha[:10]} shipped to {mission.target_branch} after an exit-0 merge — teardown projected an excluded commit (#4981)"
        )
    else:
        assert not sha_reachable(mission.repo, removed_sha, mission.target_branch)


def test_4981_default_squash_must_not_ship_removed_commit(tmp_path: Path) -> None:
    """Default-squash variant of #4981 (NO ``--strategy``) — the DEFAULT flow.

    RED at HEAD: teardown consolidates the carrier lane and the default squash
    exits 0 with ``src/pkg/wp81_removed.py`` on the target. Under squash neither
    the lane-tip SHA nor the removed commit's patch-id survives, so the observable
    is squash-sound **blob presence**. Goes GREEN when WP03/WP05 land the closed-
    world blob-attribution axis (FAIL → CAS rollback → removed file absent)."""
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8="01M4981S")
    pre_target = mission.rev(mission.target_branch)
    _removed_sha, _removed_pid, planted_path = plant_canceled_commit(mission, canceled_wp="WP81", carrier_wp="WP02")

    result = run_terminus(mission, ["merge", "--mission", mission.slug, "--yes"])

    assert not blob_present_at(mission.repo, mission.target_branch, planted_path), (
        f"removed WP81 file {planted_path} SHIPPED to {mission.target_branch} under the DEFAULT squash at exit {result.returncode} (#5013)"
    )
    assert result.returncode != 0, "default squash must FAIL the content axis and exit non-zero"
    assert mission.rev(mission.target_branch) == pre_target, "on a content-axis FAIL the target must be CAS-rolled-back to its pre-merge base"
    assert output_names_content_fail(result), "the merge output must name the un-attributable content / reconciliation FAIL"
