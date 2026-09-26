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
    blob_present_at,
    build_coord_mission,
    output_names_content_fail,
    patch_ids_in_window,
    plant_canceled_commit,
    run_terminus,
    sha_reachable,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def test_4977_canceled_code_via_dependent_lane_must_not_reach_target(tmp_path: Path) -> None:
    mission = build_coord_mission(tmp_path, wps=("WP01",), mid8="01M4977A")
    pre_target = mission.rev(mission.target_branch)
    canceled_sha, canceled_pid, _planted = plant_canceled_commit(mission, canceled_wp="WP77", carrier_wp="WP01")
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


def test_4977_default_squash_must_not_ship_canceled_file(tmp_path: Path) -> None:
    """Default-squash variant of #4977 (NO ``--strategy``) — the DEFAULT flow.

    RED at HEAD: the default squash consolidates the carrier lane and exits 0,
    shipping ``src/pkg/wp77_removed.py`` onto the target (probe-confirmed: the pass
    line even says "content reachability deferred under squash strategy"). The
    observable is squash-sound **blob presence**, never a SHA/patch-id (squash
    destroys both). Goes GREEN when WP03/WP05 land the closed-world blob-attribution
    axis: the merge then FAILs, CAS-rolls the target back to its pre-merge base, and
    the removed file is absent."""
    mission = build_coord_mission(tmp_path, wps=("WP01",), mid8="01M4977S")
    pre_target = mission.rev(mission.target_branch)
    _canceled_sha, _canceled_pid, planted_path = plant_canceled_commit(mission, canceled_wp="WP77", carrier_wp="WP01")

    result = run_terminus(mission, ["merge", "--mission", mission.slug, "--yes"])

    # RED expectation the fix will flip (squash-sound: blob/tree presence).
    assert not blob_present_at(mission.repo, mission.target_branch, planted_path), (
        f"canceled WP77 file {planted_path} SHIPPED to {mission.target_branch} under the DEFAULT squash at exit {result.returncode} (#5013)"
    )
    # The gate must FAIL and CAS-roll the target back to its pre-merge base.
    assert result.returncode != 0, "default squash must FAIL the content axis and exit non-zero"
    assert mission.rev(mission.target_branch) == pre_target, "on a content-axis FAIL the target must be CAS-rolled-back to its pre-merge base"
    # Pin the FAIL cause — NOT mere absence (which any abort satisfies).
    assert output_names_content_fail(result), "the merge output must name the un-attributable content / reconciliation FAIL"
