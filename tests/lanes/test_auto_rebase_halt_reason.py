"""FR-003 (squad-3 F1): the stale refusal says why the in-run auto-rebase did not refresh the lane.

* A conflict lists EXACTLY the conflicted paths: two conflicting paths are both named, and an
  overlapping path both sides changed without conflicting (the control) is not.
* A missing lane checkout is a halt reason of its own: "no lane checkout, so no in-run auto-rebase ran".
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from specify_cli.lanes.models import ExecutionLane
from specify_cli.lanes.stale_check import StaleCheckResult
from tests.lanes.test_auto_rebase_record import _MISSION, _LANE, _commit, _git, _init_repo, _lane_worktree, _rebase

pytestmark = pytest.mark.git_repo

_TEN = "".join(f"line {n}\n" for n in range(1, 11))


def _conflict_shape(tmp_path: Path) -> tuple[Path, Path]:
    """``one.py`` and ``two.py`` conflict; ``wide.txt`` is changed by both sides in far-apart lines (merges cleanly)."""
    root = _init_repo(tmp_path)
    for name in ("one.py", "two.py"):
        _commit(root, name, "value = 0\n", f"seed {name}")
    _commit(root, "wide.txt", _TEN, "seed wide.txt")
    _git(root, "branch", "-f", _MISSION, "main")
    worktree = _lane_worktree(root)
    _commit(worktree, "one.py", "value = 1\n", "lane: one")
    _commit(worktree, "two.py", "value = 1\n", "lane: two")
    _commit(worktree, "wide.txt", _TEN.replace("line 1\n", "lane line 1\n"), "lane: wide head")
    _git(root, "checkout", "-q", _MISSION)
    _commit(root, "one.py", "value = 2\n", "mission: one")
    _commit(root, "two.py", "value = 2\n", "mission: two")
    _commit(root, "wide.txt", _TEN.replace("line 10\n", "mission line 10\n"), "mission: wide tail")
    _git(root, "checkout", "-q", "main")
    return root, worktree


def _listed_paths(halt_reason: str) -> list[str]:
    match = re.search(r"conflicted paths: (.+?)(?:;|$)", halt_reason)
    assert match is not None, halt_reason
    return [path.strip() for path in match.group(1).split(",")]


def test_conflict_halt_lists_exactly_the_conflicted_paths(tmp_path: Path) -> None:
    root, worktree = _conflict_shape(tmp_path)

    report = _rebase(root, worktree)

    assert report.succeeded is False
    assert report.halt_reason is not None
    assert _listed_paths(report.halt_reason) == ["one.py", "two.py"]
    assert "wide.txt" not in report.halt_reason  # control: overlapping, not conflicting


def _lane() -> ExecutionLane:
    return ExecutionLane(lane_id="lane-a", wp_ids=("WP01",), write_scope=("src",), predicted_surfaces=(), depends_on_lanes=(), parallel_group=0)


def test_missing_lane_checkout_is_a_stated_halt_reason(tmp_path: Path) -> None:
    from specify_cli.lanes.consolidation import _try_auto_rebase_if_stale
    from specify_cli.lanes.stale_check import NO_LANE_CHECKOUT_HALT

    root = _init_repo(tmp_path)
    stale = StaleCheckResult(is_stale=True, stale_files=["shared.py"])

    result, halt = _try_auto_rebase_if_stale(stale, _lane(), _LANE, _MISSION, "x-01ABCDEF", root)

    assert result is stale
    assert halt == NO_LANE_CHECKOUT_HALT
    assert NO_LANE_CHECKOUT_HALT == "no lane checkout, so no in-run auto-rebase ran"


def test_missing_lane_checkout_reason_leads_the_remedy() -> None:
    from specify_cli.lanes.stale_check import NO_LANE_CHECKOUT_HALT, refine_stale_result

    stale = StaleCheckResult(is_stale=True, stale_files=["shared.py"])

    refined = refine_stale_result(stale, _lane(), _LANE, _MISSION, mission_slug="demo", auto_rebase_halt=NO_LANE_CHECKOUT_HALT)

    text = refined.remediation or ""
    assert text.startswith(f"Lane lane-a has no lane checkout, so no in-run auto-rebase ran onto {_MISSION}. "), text
    assert "stopped:" not in text, text
