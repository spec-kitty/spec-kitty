"""An advancing ``next`` decision reads the status read door once (#7539 item 1, NFR-002).

Mission ``runtime-status-read-door-01M73HHB`` follow-up (pre-PR squad rows 8, 13 and 15).

The #7507 Mission (WP01 ``planned``, WP02 ``for_review`` committed on the coordination branch),
with its coordination worktree **materialized**, **empty** or **unmaterialized**. An advancing
``decide_next_via_runtime`` dispatches WP01's ``implement`` in every cell (the bootstrap's
decision-log wrap restores or materializes the worktree first). The counting spy patches the
``specify_cli.status`` package attribute, as ``test_board_query_read_door_7507`` does.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

import specify_cli.status as status_package
from mission_runtime import MissionTopology
from runtime.next.runtime_bridge import decide_next_via_runtime
from tests.runtime._next_mission_scaffold import analysis_is_current
from tests.runtime.next.test_board_query_read_door_7507 import CELLS, _coord_cell_mission

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

#: Door reads per advancing decision: the bootstrap's one read, carried to every board reader.
_DOOR_READS_PER_ADVANCING_DECISION = 3


def _counting(monkeypatch: pytest.MonkeyPatch, owner: Any, name: str) -> list[object]:
    calls: list[object] = []
    real: Callable[..., Any] = getattr(owner, name)

    def _spy(*args: Any, **kwargs: Any) -> Any:
        calls.append(args)
        return real(*args, **kwargs)

    monkeypatch.setattr(owner, name, _spy)
    return calls


@pytest.mark.parametrize("cell", CELLS)
def test_advancing_decision_door_reads(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cell: str) -> None:
    repo, slug = _coord_cell_mission(tmp_path, MissionTopology.COORD, cell)
    door_reads = _counting(monkeypatch, status_package, "resolve_status_read")

    decision = decide_next_via_runtime("pedro", slug, "success", repo, analysis_currency=analysis_is_current)

    assert str(decision.kind) == "step", decision.reason
    assert decision.action == "implement"
    assert decision.wp_id == "WP01"
    assert decision.mission_state == "implement"
    assert decision.progress is not None
    assert decision.progress["planned_wps"] == 1
    assert decision.progress["for_review_wps"] == 1
    assert len(door_reads) == _DOOR_READS_PER_ADVANCING_DECISION
