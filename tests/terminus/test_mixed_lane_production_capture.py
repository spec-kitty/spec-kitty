"""Canceled-content verdicts hold when every attribution stamp comes from the real production capture path, never a hand-written one.

The fixture builder's own hand-written events stand in for "what the real
workflow would have recorded"; this file closes that gap. The mission is built
with ``canceled_lifecycle="none"`` (WP02 left ``planned``: zero events, zero
commits), then WP02's ENTIRE lifecycle -- and, for the superseded twin, WP01's
rework -- is driven through
``specify_cli.coordination.status_transition.emit_status_transition_transactional``,
the coord-topology transactional shell that injects the real
``probe_lane_head``. Consolidation runs through the REAL ``spec-kitty
consolidate`` CLI (:func:`tests.terminus.conftest.run_terminus`). Unsuperseded
canceled content FAILs; the superseded twin PASSes.

Driving the full ``spec-kitty implement`` / ``agent tasks move-task`` CLI would
need the complete mission scaffold (worktrees, lane checkouts, agent profile
resolution) this synthetic fixture does not carry; the transitions therefore
run in-process through the production shell against the SAME on-disk repo and
coordination worktree the CLI's consolidate reads.

Originally the #5046 SC-006 production-path proof (mission
mixed-lane-authorship-soundness-01M3M7Y0).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.status.models import ReviewResult
from tests.terminus.conftest import CoordMission, build_coord_mission_mixed_lane_canceled, git_rev, run_terminus
from tests.terminus.conftest import _git as git
from tests.terminus.mixed_lane_support import FAIL_HEADER, FAIL_WHO, LANE_NAME, collapse, ensure_wp01_subtasks_roster, reapprove_wp01, transition

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_LEAKED_PATH = "src/pkg/wp02_new.py"
_ACTOR = "production-capture-test"


def _drive_wp02_live(mission: CoordMission, lane_branch: str) -> None:
    """WP02's ENTIRE lifecycle, live, through the production shell:
    genesis -> planned -> claimed -> in_progress -> [real commit] -> canceled.

    The in_progress / canceled stamps must equal the lane's rev-parse taken just
    before the first / just after the last commit (not merely "a stamp exists").
    """
    transition(mission, "WP02", "planned", actor=_ACTOR)  # genesis -> planned
    transition(mission, "WP02", "claimed", actor=_ACTOR)

    lane_head_before_first_commit = git_rev(mission.repo, lane_branch)
    in_progress_event = transition(mission, "WP02", "in_progress", actor=_ACTOR)
    assert in_progress_event.policy_metadata is not None
    assert in_progress_event.policy_metadata["lane_head"] == lane_head_before_first_commit, (
        "WP02's in_progress stamp must equal the lane's rev-parse taken just before its first commit"
    )

    git(mission.repo, "checkout", "-q", lane_branch)
    leaked = mission.repo / _LEAKED_PATH
    leaked.parent.mkdir(parents=True, exist_ok=True)
    leaked.write_text("def wp02_new():\n    return 'wp02 leaked'\n", encoding="utf-8")
    git(mission.repo, "add", _LEAKED_PATH)
    git(mission.repo, "commit", "-qm", "wp02 commits real content, live")
    lane_head_after_last_commit = git_rev(mission.repo, lane_branch)
    git(mission.repo, "checkout", "-q", mission.target_branch)

    cancel_event = transition(mission, "WP02", "canceled", actor=_ACTOR, reason_source="operator")
    assert cancel_event.policy_metadata is not None
    assert cancel_event.policy_metadata["lane_head"] == lane_head_after_last_commit, (
        "WP02's canceled stamp must equal the lane's rev-parse taken just after its last commit"
    )


def _drive_wp01_superseding_rework(mission: CoordMission, lane_branch: str) -> None:
    """WP01's REWORK, live, through the production shell: approved ->
    in_progress -> [real commit fully rewriting WP02's leaked path] ->
    for_review -> in_review -> approved. The newest toucher of every path the
    canceled WP touched must be a non-canceled commit for it to count as
    superseded."""
    transition(mission, "WP01", "in_progress", actor=_ACTOR, review_ref="review-wp01-rework")

    git(mission.repo, "checkout", "-q", lane_branch)
    leaked = mission.repo / _LEAKED_PATH
    leaked.write_text("def wp02_new():\n    return 'wp01 rewrote this entirely'\n", encoding="utf-8")
    git(mission.repo, "add", _LEAKED_PATH)
    git(mission.repo, "commit", "-qm", "wp01 rework supersedes wp02's content")
    git(mission.repo, "checkout", "-q", mission.target_branch)

    transition(mission, "WP01", "for_review", actor=_ACTOR, subtasks_complete=True)
    transition(mission, "WP01", "in_review", actor=_ACTOR)
    transition(
        mission,
        "WP01",
        "approved",
        actor=_ACTOR,
        review_result=ReviewResult(reviewer=_ACTOR, verdict="approved", reference="review-wp01-rework"),
    )


def _build_live_capture_mission(tmp_path: Path, mid8: str) -> CoordMission:
    mission = build_coord_mission_mixed_lane_canceled(
        tmp_path,
        canceled_changes=(),  # ignored: canceled_lifecycle="none" drives WP02 live instead
        stamp_attribution=True,
        canceled_lifecycle="none",
        mid8=mid8,
    )
    ensure_wp01_subtasks_roster(mission)
    return mission


def test_production_path_unsuperseded_canceled_content_fails(tmp_path: Path) -> None:
    """WP02's lifecycle driven live, its real commit never superseded:
    consolidation FAILs, naming WP02, the lane and the path, and restores the target.

    WP02 committed after WP01's approval, so WP01 is approved again first (#5720): the
    approval-stamp bound then passes and the canceled-content verdict is what the run reports."""
    mission = _build_live_capture_mission(tmp_path, "01M5046P")
    _drive_wp02_live(mission, mission.lane_branches["WP02"])
    reapprove_wp01(mission, actor=_ACTOR)

    pre_sha = mission.rev(mission.target_branch)
    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])

    flat = collapse(result.stdout + "\n" + result.stderr)
    assert result.returncode != 0, f"unsuperseded canceled WP02 content driven through the production shell must be refused, got exit 0:\n{flat}"
    assert FAIL_HEADER in flat, f"expected the FAIL verdict header in output:\n{flat}"
    assert FAIL_WHO in flat, f"expected the FAIL verdict to name '{FAIL_WHO}':\n{flat}"
    assert LANE_NAME in flat, f"expected the FAIL verdict to name the lane '{LANE_NAME}':\n{flat}"
    assert f"'{_LEAKED_PATH}'" in flat, f"expected the FAIL verdict to name the offending path '{_LEAKED_PATH}':\n{flat}"
    assert mission.rev(mission.target_branch) == pre_sha, "target must be restored to its pre-consolidation SHA on FAIL"


def test_production_path_superseded_twin_passes(tmp_path: Path) -> None:
    """The same live drive plus a live WP01 rework that fully rewrites WP02's
    leaked path: consolidation exits 0."""
    mission = _build_live_capture_mission(tmp_path, "01M5046Q")
    lane_branch = mission.lane_branches["WP02"]
    _drive_wp02_live(mission, lane_branch)
    _drive_wp01_superseding_rework(mission, lane_branch)

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])

    flat = collapse(result.stdout + "\n" + result.stderr)
    assert result.returncode == 0, f"a superseding WP01 rework driven through the production shell must consolidate cleanly, got:\n{flat}"
