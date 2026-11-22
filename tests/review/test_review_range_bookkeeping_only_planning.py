"""A planning-lane review range made only of status bookkeeping is withheld (#7759, FR-013, C-003).

On a default-settled ``lanes_with_coord`` Mission the planning lane's status events and its work
share the topic branch, so the review range is derived from the status-event commits (operator
ruling Q10). When the work package's own commits are not on that branch (#7759: the planning work
was committed on the target), the derived range holds nothing but status-bookkeeping commits. It
must then read as unavailable with a named reason, never as a range that seems to hold the work.
The positive control keeps the range when a non-bookkeeping commit lies inside it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from types import SimpleNamespace

import pytest

from kernel.git import GitCommandError
from mission_runtime import MissionArtifactKind, MissionTopology, placement_seam
from specify_cli.review import wp_range
from specify_cli.review.context_block import describe_gap, render_review_context
from specify_cli.review.wp_range import RangeStatus, resolve_wp_review_range
from specify_cli.status.emit import emit_status_transition
from tests.specify_cli.cli.commands.agent.test_finalize_topology_settlement import (
    MISSION_DIR_TOKEN,
    _quiet_status_fanout,  # noqa: F401 -- autouse fixture re-exported into this module
    git,
    make_default_mission,
    run_finalize,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox]

# A planning WP confined to its Mission directory stays on lane-planning; a docs/ path would be
# normalised to code_change on a lane of its own (#7809).
_PLANNING_FILE = "plan.md"
_GAP = "planning_range_bookkeeping_only"


def _transition(write_dir: Path, slug: str, to_lane: str) -> None:
    """Record one WP01 transition in the status write checkout and commit it alone."""
    submission = to_lane == "for_review"
    reason = "planning submission" if submission else None
    emit_status_transition(mission_dir=write_dir, mission_slug=slug, wp_id="WP01", to_lane=to_lane, actor="claude", force=submission, reason=reason)
    checkout = write_dir.parents[1]
    git(checkout, "add", "-A", "kitty-specs")
    git(checkout, "commit", "-qm", f"chore: WP01 {to_lane}")


def _planning_path(slug: str) -> str:
    return f"kitty-specs/{slug}/{_PLANNING_FILE}"


def _planning_mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, with_work: bool) -> tuple[Path, str]:
    """A default-settled coordination Mission whose planning WP01 is submitted, with or without a work commit in range."""
    for key in ("SPEC_KITTY_NO_NAG", "SPEC_KITTY_NON_INTERACTIVE"):
        monkeypatch.delenv(key, raising=False)
    mission = make_default_mission(tmp_path, (f"{MISSION_DIR_TOKEN}/{_PLANNING_FILE}", "src/one.py", "src/two.py"), planning=(1,))
    code, payload = run_finalize(mission)
    assert code == 0, payload
    seam = placement_seam(mission.root, mission.slug)
    assert seam.write_target(MissionArtifactKind.STATUS_STATE).ref == seam.write_target(MissionArtifactKind.WORK_PACKAGE_TASK).ref == mission.topic, "precondition"
    write_dir = seam.write_dir(MissionArtifactKind.STATUS_STATE).path
    checkout = write_dir.parents[1]
    _transition(write_dir, mission.slug, "claimed")
    if with_work:
        planning_path = _planning_path(mission.slug)
        (checkout / planning_path).parent.mkdir(parents=True, exist_ok=True)
        (checkout / planning_path).write_text("# plan\n", encoding="utf-8")
        git(checkout, "add", planning_path)
        git(checkout, "commit", "-qm", "docs: WP01 plan")
    _transition(write_dir, mission.slug, "in_progress")
    _transition(write_dir, mission.slug, "for_review")
    return mission.root, mission.slug


def test_bookkeeping_only_planning_range_is_unavailable_with_its_reason(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, slug = _planning_mission(tmp_path, monkeypatch, with_work=False)

    found = resolve_wp_review_range(root, slug, "WP01", owned_files=(_planning_path(slug),))

    assert found.status is RangeStatus.UNAVAILABLE, found
    assert found.gap == _GAP
    reason = describe_gap(found.gap)
    assert reason != _GAP and reason.endswith(f"({_GAP})"), reason
    assert "status-bookkeeping" in reason
    block = render_review_context(found, ())
    assert f"REVIEW RANGE (WP01): unavailable — {reason}" in block


def test_planning_range_with_a_work_commit_keeps_its_range(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, slug = _planning_mission(tmp_path, monkeypatch, with_work=True)

    found = resolve_wp_review_range(root, slug, "WP01", owned_files=(_planning_path(slug),))

    assert found.status is RangeStatus.DERIVED, found
    assert [change.path for change in found.files] == [_planning_path(slug)]


# --------------------------------------------------------------------------- the check's own branches


def _ctx(*, lane_stamped: bool = False, topology: MissionTopology = MissionTopology.LANES_WITH_COORD) -> Any:
    """A duck-typed resolution context: only the fields the check reads."""
    return SimpleNamespace(lane_stamped=lane_stamped, surface=SimpleNamespace(topology=topology, mission_dir_name="m"), repo_root=Path("."))


@pytest.mark.parametrize(
    ("ctx", "base"),
    [
        pytest.param(_ctx(lane_stamped=True), "a", id="code-lane-never-judged"),
        pytest.param(_ctx(topology=MissionTopology.SINGLE_BRANCH), "a", id="single-branch-never-judged"),
        pytest.param(_ctx(), "b", id="empty-range-kept"),
    ],
)
def test_check_skips_what_it_does_not_judge(ctx: Any, base: str, monkeypatch: pytest.MonkeyPatch) -> None:
    def _never(*_args: object) -> int:
        raise AssertionError("no count expected")

    monkeypatch.setattr(wp_range, "_count", _never)
    assert wp_range._bookkeeping_only_planning_range(ctx, base, "b", ()) is False


def test_a_failed_count_keeps_the_range(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fail(*_args: object) -> int:
        raise GitCommandError(argv=("git", "rev-list"), cwd=Path("."), returncode=128, stderr="failed")

    monkeypatch.setattr(wp_range, "_count", _fail)
    assert wp_range._bookkeeping_only_planning_range(_ctx(), "a", "b", ()) is False


@pytest.mark.parametrize(("count", "expected"), [(0, True), (2, False)])
def test_the_count_decides(count: int, expected: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wp_range, "_count", lambda *_args: count)
    assert wp_range._bookkeeping_only_planning_range(_ctx(), "a", "b", ()) is expected


@pytest.mark.parametrize(
    "owned",
    [
        pytest.param(("kitty-specs/m/tasks.md",), id="task-index"),
        pytest.param(("./kitty-specs/m/tasks.md",), id="task-index-dot-slash"),
        pytest.param(("kitty-specs/m/status.*",), id="status-glob"),
        pytest.param(("kitty-specs/m/tasks/WP01-a.md", "kitty-specs/m/decisions/"), id="prompt-and-decisions"),
    ],
)
def test_a_planning_wp_that_owns_only_bookkeeping_is_never_withheld(owned: tuple[str, ...], monkeypatch: pytest.MonkeyPatch) -> None:
    """Its own work is bookkeeping by the exclusion set, so a zero count says nothing about it (L1)."""

    def _never(*_args: object) -> int:
        raise AssertionError("no count expected")

    monkeypatch.setattr(wp_range, "_count", _never)
    assert wp_range._bookkeeping_only_planning_range(_ctx(), "a", "b", (), owned_files=owned) is False


@pytest.mark.parametrize(
    "owned",
    [
        pytest.param(("kitty-specs/m/plan.md",), id="plan"),
        pytest.param(("kitty-specs/m/tasks.md", "kitty-specs/m/plan.md"), id="mixed"),
        pytest.param(("kitty-specs/m/tasks.md.bak",), id="task-index-lookalike"),
        pytest.param((), id="none-declared"),
    ],
)
def test_a_planning_wp_with_its_own_work_is_still_judged(owned: tuple[str, ...], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wp_range, "_count", lambda *_args: 0)
    assert wp_range._bookkeeping_only_planning_range(_ctx(), "a", "b", (), owned_files=owned) is True
