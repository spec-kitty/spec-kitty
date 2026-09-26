"""Repro #5018 — a mixed approved+canceled write-scope lane false-FAILs under
``--strategy merge`` because exclusion is computed at LANE granularity.

Mechanism: ``_collect_excluded`` (``merge/reconciliation.py``) adds ALL of a
lane's tip commits to the excluded set the moment the lane lists ANY
canceled-with-provenance WP (``if not any(wp in excluded_canceled_wp_ids for wp
in lane.wp_ids): continue`` — the guard only skips a lane with NO canceled WP at
all). A mixed lane — an approved survivor sharing the lane with a canceled
sibling — therefore has its survivor's own legitimately-approved first-parent
commits added to ``excluded_shas`` too. ``_reachable_excluded`` then flags those
commits as "excluded content reachable from the target" and the merge FAILs +
reverts, even though nothing removed ever shipped.

RED-first, driven through the REAL ``spec-kitty merge`` CLI (no ``_run_git`` /
subprocess mocking): at the pre-fix HEAD the survivor's own commit was
misclassified as excluded-and-reachable, so the merge FAILed (non-zero exit)
instead of the desired PASS (pinned ``xfail(strict=True)`` while red). GREEN
now that ``_collect_excluded`` subtracts the approved lanes' first-parent
authored SHAs/patch-ids (T005).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.terminus.conftest import (
    build_coord_mission_mixed_lane,
    run_terminus,
    sha_reachable,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]


def test_5018_mixed_lane_survivor_commits_must_not_be_excluded(tmp_path: Path) -> None:
    mission = build_coord_mission_mixed_lane(
        tmp_path,
        survivor_wp="WP01",
        canceled_wp="WP02",
        mid8="01M5018A",
    )
    survivor_shas = mission.approved_shas_from_lane_tips(["WP01"])["WP01"]
    assert survivor_shas, "the fixture must plant at least one real survivor commit"

    result = run_terminus(mission, ["merge", "--mission", mission.slug, "--strategy", "merge", "--yes"])

    assert result.returncode == 0, (
        f"a mixed approved+canceled lane must PASS the reconciliation gate under "
        f"--strategy merge (the survivor's own commits are approved authorship, "
        f"not excluded content) — got exit {result.returncode}:\n{result.stdout}\n{result.stderr}"
    )
    for sha in survivor_shas:
        assert sha_reachable(mission.repo, sha, mission.target_branch), f"approved WP01 commit {sha[:10]} did not land on {mission.target_branch} (#5018)"
