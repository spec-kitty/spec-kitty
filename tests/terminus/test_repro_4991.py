"""Repro #4991 — a resumed merge ignores the persisted ``ConsolidationState.target_branch``.

Mechanism (DEBRIEF §4, root R4 / companion C-1): the merge target lives in FOUR
places (meta.json / lanes.json / ``ConsolidationState.target_branch`` / ``--target``). The
executor drives off the meta/lanes target and ``ConsolidationState.target_branch`` is
write-only — never consulted on ``--resume``. So an interrupted
``merge --target develop`` that persisted ``target_branch="develop"`` resumes
against meta's ``main`` instead of ``develop``. Backstopped by C-1 (WP09):
merge target = one persisted resolved authority.

RED-first: the resume is driven through the REAL ``spec-kitty merge --resume`` CLI
(no ``_run_git`` / subprocess mocking). The persisted resume state is written with
``save_state`` — fixture setup, exactly as ``tests/merge/test_issue_4764_terminus_safety.py``
does, not a mock. Today the resume re-resolves the target to ``main`` (it refuses
with ``MERGE_UNSAFE_PRIMARY_OFF_TARGET`` / "expected 'main'") and never lands the
approved work on ``develop`` → the develop-reachability assertion fails →
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


def _persist_interrupted_develop_merge(mission: CoordMission, wp_ids: list[str]) -> None:
    """Persist the state an interrupted ``merge --target develop`` would leave."""
    from specify_cli.consolidation.reconciliation import write_post_fix_marker
    from specify_cli.consolidation.state import ConsolidationState, save_state

    state = ConsolidationState(
        mission_id=mission.mission_id,
        mission_slug=mission.slug,
        target_branch="develop",
        wp_order=list(wp_ids),
    )
    state.current_wp = wp_ids[0]
    state.strategy = "merge"
    save_state(state, mission.repo)
    # WP10 integration (FR-012): mark this as a POST-fix in-flight crash so the
    # resumed merge is not refused by the FR-012 legacy guard.
    write_post_fix_marker(mission.repo, mission.mission_id)


def test_4991_resume_honors_persisted_target_branch_not_stale_meta(tmp_path: Path) -> None:
    """The resume judges the persisted ``develop``, never meta's ``main``.

    #5783 (operator ruling 2026-11-16): the write target stays the RECORDED ``main``, which
    the checkout on ``develop`` cannot commit to, so the resume is refused up front with
    ``TARGET_OVERRIDE_RECORDED_TARGET_UNWRITABLE`` instead of landing on ``develop`` and
    leaving the bookkeeping uncommitted. The #4991 half still holds: the persisted target is
    the one judged (pre-fix the resume re-resolved to meta's ``main``), and ``main`` gets nothing.
    """
    mission = build_coord_mission(tmp_path, wps=("WP01",), mid8="01M4991A")
    git(mission.repo, "branch", "develop", "main")
    git(mission.repo, "checkout", "-q", "develop")  # primary on the intended target
    approved = mission.approved_shas_from_lane_tips(["WP01"])  # PRE-resume, from lane tips
    _persist_interrupted_develop_merge(mission, ["WP01"])
    tips_before = {b: git(mission.repo, "rev-parse", b).stdout.strip() for b in ("main", "develop")}

    result = run_terminus(mission, ["consolidate", "--resume", "--yes"])

    output = " ".join((result.stdout + result.stderr).split())
    assert result.returncode == 1, output
    assert "TARGET_OVERRIDE_RECORDED_TARGET_UNWRITABLE" in output, output
    assert "Refusing to land the mission branch on 'develop'" in output, (
        f"the resume must judge the persisted develop target, not meta's main (#4991). output={output}"
    )
    assert "spec-kitty consolidate --abort" in output, f"a resume refusal points at --abort. output={output}"
    assert {b: git(mission.repo, "rev-parse", b).stdout.strip() for b in ("main", "develop")} == tips_before, output
    for shas in approved.values():
        for sha in shas:
            assert not sha_reachable(mission.repo, sha, "main"), f"approved commit {sha[:10]} landed on stale-meta 'main' (#4991)"
