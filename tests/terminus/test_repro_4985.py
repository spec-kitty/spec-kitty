"""Repro #4985 — an explicit ``--target`` is lost to stale meta across a crash.

Mechanism (DEBRIEF §4, root R4 / companion C-1): meta.json records
``target_branch: main`` while the operator ran ``merge --target develop``. When the
merge is interrupted and resumed, the explicit-flag provenance is not persisted as
the authority, so the stale meta ``main`` wins over the operator's explicit
``develop``. Backstopped by C-1 (WP09): the resolved target is persisted ONCE as
the single authority, and an explicit ``--target`` always wins over stale meta.

RED-first: driven through the REAL ``spec-kitty merge --resume --target develop``
CLI (no ``_run_git`` / subprocess mocking); the interrupted state is written with
``save_state`` (fixture setup, not a mock). Today the resumed merge still resolves
against meta's ``main`` and never lands the approved work on ``develop`` →
``xfail(strict=True)``. Approved SHAs come from lane-branch tips (RN-Q3).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.terminus.conftest import (
    CoordMission,
    build_coord_mission,
    run_terminus,
    sha_reachable,
)
from tests.terminus.conftest import _git as git

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _persist_interrupted_merge(mission: CoordMission, wp_ids: list[str], target: str) -> None:
    from specify_cli.merge.reconciliation import write_post_fix_marker
    from specify_cli.merge.state import MergeState, save_state

    state = MergeState(
        mission_id=mission.mission_id,
        mission_slug=mission.slug,
        target_branch=target,
        wp_order=list(wp_ids),
    )
    state.current_wp = wp_ids[0]
    state.strategy = "merge"
    save_state(state, mission.repo)
    # WP10 integration (FR-012): mark this as a POST-fix in-flight crash so the
    # resumed merge is not refused by the FR-012 legacy guard.
    write_post_fix_marker(mission.repo, mission.mission_id)


def test_4985_explicit_target_wins_over_stale_meta_on_resume(tmp_path: Path) -> None:
    # meta.json declares target_branch=main (the fixture default / stale value).
    mission = build_coord_mission(tmp_path, wps=("WP01",), mid8="01M4985A")
    assert mission.target_branch == "main"
    git(mission.repo, "branch", "develop", "main")
    git(mission.repo, "checkout", "-q", "develop")
    approved = mission.approved_shas_from_lane_tips(["WP01"])
    _persist_interrupted_merge(mission, ["WP01"], target="develop")

    # The operator re-states the explicit target on resume; it must win over stale meta.
    run_terminus(mission, ["merge", "--resume", "--target", "develop", "--yes"])

    for shas in approved.values():
        for sha in shas:
            assert sha_reachable(mission.repo, sha, "develop"), (
                f"approved commit {sha[:10]} did NOT land on the explicit --target 'develop' after --resume — stale meta 'main' won (#4985)"
            )
    # And the stale target must NOT have received the work.
    for shas in approved.values():
        for sha in shas:
            assert not sha_reachable(mission.repo, sha, "main"), f"approved commit {sha[:10]} landed on stale-meta 'main' instead of develop (#4985)"
