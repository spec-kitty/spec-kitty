"""Repro #4977 — a CANCELED WP's code lands on the target via a dependent lane.

Mechanism (DEBRIEF §4, root R3): a WP whose code was canceled/removed still has a
real commit that a *dependent* (carrier) lane merged in. ``spec-kitty merge``
consolidates the carrier lane and exits 0 — shipping the canceled diff onto the
target, because NO code diffs the target tree against the approved-WP commit set
(the Terminus Reconciliation Gate / S-D is absent). Backstopped by S-D (WP06).

RED-first: driven through the REAL ``spec-kitty merge`` CLI (no ``_run_git`` /
subprocess mocking). Today the merge exits 0 and the canceled commit is reachable
from the target → the "not reachable" assertion fails → ``xfail(strict=True)``.
The excluded-commit check is patch-id based so a re-lettered/cherry-picked copy is
caught too, and it is non-vacuous even though the derived canceled set is empty
(the planted commit is removed work, absent from ``lanes.json``).
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


def test_4977_canceled_code_via_dependent_lane_must_not_reach_target(tmp_path: Path) -> None:
    mission = build_coord_mission(tmp_path, wps=("WP01",), mid8="01M4977A")
    pre_target = mission.rev(mission.target_branch)
    canceled_sha, canceled_pid = plant_canceled_commit(mission, canceled_wp="WP77", carrier_wp="WP01")
    approved = mission.approved_shas_from_lane_tips(["WP01"])  # PRE-merge, from lane tips

    result = run_terminus(mission, ["merge", "--mission", mission.slug, "--strategy", "merge", "--yes"])

    if result.returncode == 0:
        # Approved work must still be present (never sacrificed to close the leak).
        for shas in approved.values():
            for sha in shas:
                assert sha_reachable(mission.repo, sha, mission.target_branch)
        # THE bug: the canceled diff must NOT be reachable from the target.
        window = patch_ids_in_window(mission.repo, pre_target, mission.target_branch)
        assert canceled_pid not in window, (
            f"canceled WP77 commit {canceled_sha[:10]} (patch-id {canceled_pid[:12]}) shipped to "
            f"{mission.target_branch} via a dependent lane while merge exited 0 (#4977)"
        )
    else:
        # Post-fix: an honest refusal that ships nothing excluded.
        assert not sha_reachable(mission.repo, canceled_sha, mission.target_branch)
