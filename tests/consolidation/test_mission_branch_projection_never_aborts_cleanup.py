"""#7747 Tier R review N4: the Mission-branch proof is optional evidence, read after the verified landing.

An unexpected exception while building it must never abort cleanup: the lanes are then judged by the
content proof alone (no projection), which keeps any lane it cannot prove.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest

from specify_cli.consolidation import phase_teardown
from specify_cli.consolidation.lane_cleanup import LaneCleanupItem

if TYPE_CHECKING:
    from specify_cli.consolidation.run_state import _MergeRunState

_ITEMS = (LaneCleanupItem(lane_id="lane-a", worktree=Path("/nonexistent/lane-a"), branch="kitty/mission-demo-lane-a", expected_tip="a" * 40),)
_TWO_LANES = (
    *_ITEMS,
    LaneCleanupItem(lane_id="lane-b", worktree=Path("/nonexistent/lane-b"), branch="kitty/mission-demo-lane-b", expected_tip="c" * 40),
)


def _run(approved: tuple[str, ...] = ("WP01", "WP02")) -> _MergeRunState:
    """A stub run carrying only the fields the projection reads: lane-a holds WP01, lane-b WP02."""
    lanes = (SimpleNamespace(lane_id="lane-a", wp_ids=("WP01",)), SimpleNamespace(lane_id="lane-b", wp_ids=("WP02",)))
    manifest = SimpleNamespace(target_branch="main", mission_branch="kitty/mission-demo", mission_slug="demo", lanes=lanes)
    stub = SimpleNamespace(
        main_repo=Path("/nonexistent"),
        lanes_manifest=manifest,
        state=SimpleNamespace(reconciliation_passed_target_sha="b" * 40),
        approved_wp_set=SimpleNamespace(approved=dict.fromkeys(approved, ("d" * 40,))),
    )
    return cast("_MergeRunState", stub)


def _captured_tips(monkeypatch: pytest.MonkeyPatch, run: _MergeRunState, items: tuple[LaneCleanupItem, ...]) -> list[str]:
    seen: list[str] = []

    def capture(repo_root: object, mission_branch: object, landing: object, tips: list[str], mission_slug: object) -> None:
        seen.extend(tips)

    monkeypatch.setattr(phase_teardown, "mission_branch_projection", capture)
    phase_teardown._mission_branch_projection(run, items)
    return seen


def test_only_lanes_whose_work_packages_are_all_approved_are_projected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tier R confirm N2: a lane with a work package outside the approved claim is neither proven nor credited."""
    assert _captured_tips(monkeypatch, _run(approved=("WP01",)), _TWO_LANES) == ["a" * 40]


def test_every_approved_lane_is_projected(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _captured_tips(monkeypatch, _run(), _TWO_LANES) == ["a" * 40, "c" * 40]


def test_no_approved_claim_means_no_projection(monkeypatch: pytest.MonkeyPatch) -> None:
    run = _run()
    run.approved_wp_set = None
    assert _captured_tips(monkeypatch, run, _TWO_LANES) == []


def test_an_unexpected_error_in_the_proof_yields_no_projection(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("unexpected")

    monkeypatch.setattr(phase_teardown, "mission_branch_projection", boom)
    assert phase_teardown._mission_branch_projection(_run(), _ITEMS) is None


def test_no_lane_means_no_projection() -> None:
    assert phase_teardown._mission_branch_projection(_run(), ()) is None
