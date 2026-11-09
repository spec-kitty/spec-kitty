"""NFR-007: the lane window check costs O(work packages) history queries, independent of the commit count (WP19).

Measured on ``approved_bound_refusal`` (the bound alone) over a passing one-lane Mission built through the
real status pipeline, by counting the ``git rev-list`` / ``git merge-base`` calls that reach
``specify_cli.consolidation.git_probes.run_command`` (``rev-parse`` does not count).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from specify_cli.consolidation import approved_bound, git_probes, write_branch_bound
from specify_cli.consolidation.reconciliation import approved_bound_refusal
from specify_cli.lanes.persistence import read_lanes_json
from specify_cli.lanes.worktree_allocator import allocate_lane_worktree
from tests.consolidation import characterization_support as cs
from tests.consolidation.resume_frozen_anchors_support import fixture_phase, require
from tests.terminus.canceled_dependency_support import ACTOR, _approve, _commit_in
from tests.terminus.mixed_lane_support import transition

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

#: History queries one more approved work package may add to a passing lane's check (NFR-007):
#: 1 ``on_lane`` merge-base for its chosen open SHA, at most k^2 = 4 topology merge-bases among
#: its cycle's k = 2 recorded openers (claimed, in_progress), 2 window rev-lists (approval stamp
#: and open SHA), and 1 tier-1 stamp merge-base (``stamp_refusal``).
_PER_WP_BUDGET = 8
_COUNTED = frozenset({"rev-list", "merge-base"})


def one_lane_mission(tmp_path: Path, *, wps: int, commits_per_wp: int) -> cs.ShapeMission:
    """One code lane; *wps* work packages built one after the other: claim, *commits_per_wp* commits, review, approve."""
    wp_ids = tuple(f"WP{index + 1:02d}" for index in range(wps))
    mission, manifest = cs._bootstrap_one_lane_coord(tmp_path, mid8=f"01M6Y9Q{wps % 10}", wps=wp_ids)
    for wp_id in wp_ids:
        tree, branch = allocate_lane_worktree(mission.repo, mission.slug, wp_id, manifest)
        for lane in ("planned", "claimed", "in_progress"):
            transition(mission, wp_id, lane, actor=ACTOR)
        for step in range(commits_per_wp):
            _commit_in(tree, f"src/pkg/{wp_id.lower()}_{step}.py", f"STEP = {step}\n", f"feat({mission.slug}): {wp_id} step {step}")
        _approve(mission, wp_id, reference=f"review-{wp_id}")
        mission.lane_branches[wp_id] = branch
    return cs._from_coord(mission, "coord", subject_wp=wp_ids[-1], window_wps=wp_ids)


def _status_dir(mission: cs.ShapeMission) -> Path:
    logs = [log for log in cs._event_logs(mission.repo) if log.parent != mission.feature_dir]
    return logs[0].parent if logs else mission.feature_dir


def _bound(mission: cs.ShapeMission) -> str | None:
    manifest = read_lanes_json(mission.feature_dir)
    if manifest is None:
        raise RuntimeError("the mission must have a lanes manifest")
    base = cs._git(mission.repo, "rev-parse", mission.target_branch)
    with cs.mission_environment(mission):
        refusal: str | None = approved_bound_refusal(mission.repo, _status_dir(mission), manifest, coord_base_ref=base, excluded_window_base=base)
    return refusal


@pytest.fixture
def counter(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    calls: list[str] = []
    real = git_probes.run_command

    def _counting(cmd: list[str], *args: Any, **kwargs: Any) -> Any:
        if len(cmd) > 1 and cmd[1] in _COUNTED:
            calls.append(cmd[1])
        return real(cmd, *args, **kwargs)

    monkeypatch.setattr(git_probes, "run_command", _counting)
    yield calls


def _cost(mission: cs.ShapeMission, calls: list[str]) -> int:
    calls.clear()
    refusal = _bound(mission)
    require(refusal is None, f"the measured lane must pass:\n{refusal}")
    return len(calls)


def _built(tmp_path: Path, *, wps: int, commits_per_wp: int) -> cs.ShapeMission:
    with fixture_phase():
        mission = one_lane_mission(tmp_path / f"w{wps}c{commits_per_wp}", wps=wps, commits_per_wp=commits_per_wp)
    for wp_id in mission.window_wps:
        openers = [event for event in cs._events(mission) if cs._is_opening(event, wp_id)]
        require(all((event.get("policy_metadata") or {}).get("wp_window", {}).get("open_sha") for event in openers), f"{wp_id} must record its window")
    return mission


@pytest.mark.parametrize("wps", [3, 6])
def test_window_check_cost_is_independent_of_commit_count(tmp_path: Path, counter: list[str], wps: int) -> None:
    few = _built(tmp_path, wps=wps, commits_per_wp=2)
    many = _built(tmp_path, wps=wps, commits_per_wp=20)

    assert _cost(few, counter) == _cost(many, counter)


def test_window_check_cost_grows_linearly_with_wps(tmp_path: Path, counter: list[str]) -> None:
    three = _cost(_built(tmp_path, wps=3, commits_per_wp=2), counter)
    six = _cost(_built(tmp_path, wps=6, commits_per_wp=2), counter)

    assert six - three <= 3 * _PER_WP_BUDGET, (three, six)


def test_exempt_set_computed_once_per_lane(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """WW-1: the exempt set of a window lane is computed once and shared by both tiers (``check_lane`` gets it)."""
    mission = _built(tmp_path, wps=3, commits_per_wp=2)
    calls: dict[str, int] = {"window": 0, "tier_one_own": 0}
    real = write_branch_bound.lane_exempt_commits

    def _window(*args: Any, **kwargs: Any) -> frozenset[str]:
        calls["window"] += 1
        result: frozenset[str] = real(*args, **kwargs)
        return result

    def _tier_one(*args: Any, **kwargs: Any) -> frozenset[str]:
        calls["tier_one_own"] += 1
        result: frozenset[str] = real(*args, **kwargs)
        return result

    monkeypatch.setattr(write_branch_bound, "lane_exempt_commits", _window)
    monkeypatch.setattr(approved_bound, "lane_exempt_commits", _tier_one)

    assert _bound(mission) is None
    assert calls == {"window": 1, "tier_one_own": 0}
