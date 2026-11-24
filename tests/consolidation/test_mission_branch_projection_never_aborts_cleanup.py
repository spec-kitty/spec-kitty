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


def _run() -> _MergeRunState:
    """A stub run carrying only the fields the projection reads."""
    manifest = SimpleNamespace(target_branch="main", mission_branch="kitty/mission-demo", mission_slug="demo")
    stub = SimpleNamespace(main_repo=Path("/nonexistent"), lanes_manifest=manifest, state=SimpleNamespace(reconciliation_passed_target_sha="b" * 40))
    return cast("_MergeRunState", stub)


def test_an_unexpected_error_in_the_proof_yields_no_projection(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("unexpected")

    monkeypatch.setattr(phase_teardown, "mission_branch_projection", boom)
    assert phase_teardown._mission_branch_projection(_run(), _ITEMS) is None


def test_no_lane_means_no_projection() -> None:
    assert phase_teardown._mission_branch_projection(_run(), ()) is None
