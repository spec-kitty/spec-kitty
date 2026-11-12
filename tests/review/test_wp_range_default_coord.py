"""Operator ruling Q10 on a default-settled ``lanes_with_coord`` Mission (#7578, H1 control).

A Mission created without ``--topology`` that settles ``lanes_with_coord`` uses its topic branch as
the coordination branch, and its PRIMARY partition (where the planning lane writes) stays on that
topic branch until it lands. Its planning work package's status events and work therefore share a
branch, so the review range is still derived from its status-event commits.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mission_runtime import MissionArtifactKind, placement_seam
from specify_cli.lanes.persistence import read_lanes_json
from specify_cli.review.wp_range import RangeSource, RangeStatus, resolve_wp_review_range
from specify_cli.status.emit import emit_status_transition
from tests.specify_cli.cli.commands.agent.test_finalize_topology_settlement import (
    _quiet_status_fanout,  # noqa: F401 -- autouse fixture re-exported into this module
    git,
    make_default_mission,
    run_finalize,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox]

_PLANNING_PATH = "docs/plan.md"


def _transition(write_dir: Path, slug: str, to_lane: str) -> str:
    """Record one WP01 transition in the status write checkout and commit it alone; returns the commit."""
    submission = to_lane == "for_review"
    reason = "planning submission" if submission else None
    emit_status_transition(mission_dir=write_dir, mission_slug=slug, wp_id="WP01", to_lane=to_lane, actor="claude", force=submission, reason=reason)
    checkout = write_dir.parents[1]
    git(checkout, "add", "-A", "kitty-specs")
    git(checkout, "commit", "-qm", f"chore: WP01 {to_lane}")
    return git(checkout, "rev-parse", "HEAD")


def test_default_settled_coord_planning_wp_still_gets_the_derived_range(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("SPEC_KITTY_NO_NAG", "SPEC_KITTY_NON_INTERACTIVE"):
        monkeypatch.delenv(key, raising=False)
    mission = make_default_mission(tmp_path, (_PLANNING_PATH, "src/one.py", "src/two.py"), planning=(1,))
    code, payload = run_finalize(mission)
    assert code == 0, payload
    seam = placement_seam(mission.root, mission.slug)
    assert seam.write_target(MissionArtifactKind.STATUS_STATE).ref == seam.write_target(MissionArtifactKind.WORK_PACKAGE_TASK).ref == mission.topic, "precondition"
    manifest = read_lanes_json(mission.coord_mission_dir)
    planning_lane = manifest.lane_for_wp("WP01") if manifest is not None else None
    assert planning_lane is not None and planning_lane.lane_id == "lane-planning", "precondition"
    write_dir = seam.write_dir(MissionArtifactKind.STATUS_STATE).path
    checkout = write_dir.parents[1]

    claim = _transition(write_dir, mission.slug, "claimed")
    (checkout / _PLANNING_PATH).parent.mkdir(parents=True, exist_ok=True)
    (checkout / _PLANNING_PATH).write_text("# plan\n", encoding="utf-8")
    git(checkout, "add", _PLANNING_PATH)
    git(checkout, "commit", "-qm", "docs: WP01 plan")
    work = git(checkout, "rev-parse", "HEAD")
    _transition(write_dir, mission.slug, "in_progress")
    tip = _transition(write_dir, mission.slug, "for_review")

    found = resolve_wp_review_range(mission.root, mission.slug, "WP01", owned_files=(_PLANNING_PATH,))

    assert found.status is RangeStatus.DERIVED, found
    assert (found.base, found.base_source) == (claim, RangeSource.EVENT_COMMIT)
    assert (found.tip, found.tip_source) == (tip, RangeSource.EVENT_COMMIT)
    assert [commit.sha for commit in found.commits] == [work]
    assert [change.path for change in found.files] == [_PLANNING_PATH]
