"""#5573 — a re-finalize must never move a started work package to another lane.

End-to-end reproduction through the real ``agent mission finalize-tasks``
command (Typer ``mission_app``, in-process), with real git, real status events
and a real allocated lane worktree.

Starting state for every test: a ``lanes`` mission whose first finalize gives
lane-a = [WP01] (``a.py``) and lane-b = [WP02] (``b.py``). A WP is "started"
when it is allocated and its status left ``planned``. The amendment then
forces an overlap and re-runs finalize-tasks.

* US1 AS1 / SC-001: a planned WP joining a started WP's lane must follow the
  started WP's recorded lane (lane-b), not the lowest lane id.
* US1 AS2: the same holds for a WP that is only ``claimed``.
* US1 AS3 (positive control): when the started WP already sits on lane-a, the
  merged lane is lane-a. This passes before the fix too.
* US2 AS1 / FR-005 / FR-006 / SC-003: two started lanes forced together refuse
  with ``LANE_MEMBERSHIP_FROZEN`` before writing anything; a same-fixture
  positive control proves the same WP03 addition succeeds without the collision.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.lanes.persistence import read_lanes_json
from specify_cli.lanes.worktree_allocator import allocate_lane_worktree
from tests.integration.refinalize_frozen_lanes_support import (
    add_wp03 as _add_wp03,
    amend_overlap as _amend_overlap,
    assert_saw_overlap as _assert_saw_overlap,
    commit_amendment as _commit_amendment,
    EVENTS as _EVENTS,
    finalize as _finalize,
    FinalizeResult as _FinalizeResult,
    git as _git,
    lane_topology as _topology,
    Mission as _Mission,
    setup_mission as _setup_mission,
    snapshot as _snapshot,
    spy_writers as _spy_writers,
    start_wp as _start,
    Started as _Started,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _assert_started_wp02_kept_lane_b(mission: _Mission, started: _Started, result: _FinalizeResult) -> None:
    assert result.exit_code == 0, result.output
    _assert_saw_overlap(result)
    after = read_lanes_json(mission.feature_dir)
    assert after is not None
    assert _topology(after) == [("lane-b", ("WP02", "WP01"))], (
        f"a planned WP joining a started WP's lane must follow the started WP's recorded lane (#5573); lanes after: {_topology(after)!r}"
    )
    worktree, branch = allocate_lane_worktree(mission.repo, mission.slug, "WP02", after)
    assert worktree == started.worktree
    assert branch == started.branch


def test_started_wp_keeps_its_lane_when_a_planned_wp_joins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mission = _setup_mission(tmp_path, monkeypatch)
    started = _start(mission, "WP02", commit_work=True, in_progress=True)
    _amend_overlap(mission, joiner="WP01", owner="WP02")
    _commit_amendment(mission)

    result = _finalize(mission.slug)

    _assert_started_wp02_kept_lane_b(mission, started, result)
    assert (started.worktree / "b.py").read_text(encoding="utf-8") == "b = 42\n"


def test_claimed_only_wp_keeps_its_lane(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mission = _setup_mission(tmp_path, monkeypatch)
    started = _start(mission, "WP02", commit_work=False, in_progress=False)
    _amend_overlap(mission, joiner="WP01", owner="WP02")
    _commit_amendment(mission)

    result = _finalize(mission.slug)

    _assert_started_wp02_kept_lane_b(mission, started, result)


def test_lane_follows_the_started_wp_not_lane_id_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive control: WP01 started on lane-a, WP02 joins it; the merged lane is lane-a."""
    mission = _setup_mission(tmp_path, monkeypatch)
    started = _start(mission, "WP01", commit_work=True, in_progress=True)
    _amend_overlap(mission, joiner="WP02", owner="WP01")
    _commit_amendment(mission)

    result = _finalize(mission.slug)

    assert result.exit_code == 0, result.output
    _assert_saw_overlap(result)
    after = read_lanes_json(mission.feature_dir)
    assert after is not None
    assert _topology(after) == [("lane-a", ("WP01", "WP02"))], _topology(after)
    worktree, _branch = allocate_lane_worktree(mission.repo, mission.slug, "WP01", after)
    assert worktree == started.worktree
    assert (worktree / "a.py").read_text(encoding="utf-8") == "a = 42\n"


def test_two_started_lanes_forced_together_refuse_before_writing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mission = _setup_mission(tmp_path, monkeypatch)
    _start(mission, "WP01", commit_work=True, in_progress=True)
    _start(mission, "WP02", commit_work=True, in_progress=True)
    _amend_overlap(mission, joiner="WP01", owner="WP02")
    # A new planned WP03 gives finalize a seed event to write, so a refusal
    # raised after seeding has something to write. Byte identity alone cannot
    # catch that: finalize's restore-on-exit (#5641) puts the bytes back. The
    # writer spies observe the write itself, which the restore cannot undo.
    _add_wp03(mission)
    _commit_amendment(mission)
    before = _snapshot(mission)
    head_before = _git(mission.repo, "rev-parse", "HEAD")
    spy = _spy_writers(monkeypatch)

    result = _finalize(mission.slug)

    assert result.exit_code == 1, f"two started lanes forced into one must refuse (#5573); output:\n{result.output}"
    payload = result.payload
    assert payload.get("error_code") == "LANE_MEMBERSHIP_FROZEN", payload
    assert payload.get("reason") == "started_lanes_collapsed", payload
    conflicts = payload.get("conflicts") or []
    assert any(
        sorted(conflict.get("wp_ids", [])) == ["WP01", "WP02"] and sorted(conflict.get("recorded_lanes", [])) == ["lane-a", "lane-b"] for conflict in conflicts
    ), conflicts
    assert str(payload.get("next_step") or "").strip(), payload
    # FR-005: the refusal comes before any status or manifest write.
    assert spy.status_writes_to(mission.feature_dir) == [], "the refusal must come before any status event is written"
    assert spy.lanes_writes_to(mission.feature_dir) == [], "the refusal must come before lanes.json is written"
    assert _snapshot(mission) == before, "a refused re-finalize must not write any planning or status file"
    assert _git(mission.repo, "rev-parse", "HEAD") == head_before, "a refused re-finalize must not commit"


def test_new_wp_without_collision_is_seeded_positive_control(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Same fixture as the refusal test, minus the collision: WP03 is added and seeded."""
    mission = _setup_mission(tmp_path, monkeypatch)
    _start(mission, "WP01", commit_work=True, in_progress=True)
    _start(mission, "WP02", commit_work=True, in_progress=True)
    _add_wp03(mission)
    _commit_amendment(mission)
    spy = _spy_writers(monkeypatch)

    result = _finalize(mission.slug)

    assert result.exit_code == 0, result.output
    # The spies are live: the same writers do record this run's writes.
    assert spy.status_writes_to(mission.feature_dir), "the status-writer spy must see WP03's seed event"
    assert spy.lanes_writes_to(mission.feature_dir), "the lanes-writer spy must see the lanes.json write"
    events = [json.loads(line) for line in (mission.feature_dir / _EVENTS).read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(event.get("wp_id") == "WP03" for event in events), "the positive control must seed WP03"
    after = read_lanes_json(mission.feature_dir)
    assert after is not None
    topology = dict(_topology(after))
    assert topology.get("lane-a") == ("WP01",), topology
    assert topology.get("lane-b") == ("WP02",), topology
    wp03_lanes = sorted(lane_id for lane_id, wp_ids in topology.items() if "WP03" in wp_ids)
    assert len(wp03_lanes) == 1, topology
    assert wp03_lanes[0] not in {"lane-a", "lane-b"}, topology
