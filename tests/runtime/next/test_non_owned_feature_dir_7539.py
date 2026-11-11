"""A non-owned decision's ``feature_dir`` after bootstrap keeps main's value (#7539 squad fold 2).

Bootstrap reads the status read door once, after the decision-log wrap. An owned call takes its
status directory from that read; a non-owned call keeps the ``feature_dir`` it resolved before the
wrap, the directory ``sync_emitter`` is built from. Values per #7507 cell, as main (78c48ce9)
produces them:

* materialized: the coordination worktree's Mission directory;
* empty and unmaterialized: the PRIMARY Mission directory (the wrap restores or materializes the
  coordination worktree only after ``feature_dir`` was resolved);
* landed with a retained, materialized coordination worktree: bootstrap answers ``terminal``
  and builds no context.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mission_runtime import MissionTopology
from runtime.next import runtime_bridge
from tests.runtime.next.test_board_query_read_door_7507 import EMPTY, MATERIALIZED, UNMATERIALIZED, _coord_cell_mission
from tests.runtime.next.test_materialization_report import COMPLETED_PRIMARY, SHORT_CIRCUIT, _landed_coord_mission

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _coord_mission_dir(repo: Path, slug: str) -> Path:
    return repo / ".worktrees" / f"{slug}-coord" / "kitty-specs" / slug


def _primary_mission_dir(repo: Path, slug: str) -> Path:
    return repo / "kitty-specs" / slug


_EXPECTED_DIR = {
    MATERIALIZED: _coord_mission_dir,
    EMPTY: _primary_mission_dir,
    UNMATERIALIZED: _primary_mission_dir,
}


@pytest.mark.parametrize("cell", [MATERIALIZED, EMPTY, UNMATERIALIZED])
def test_non_owned_feature_dir_is_the_pre_wrap_directory(tmp_path: Path, cell: str) -> None:
    repo, slug = _coord_cell_mission(tmp_path, MissionTopology.COORD, cell)

    ctx, decision = runtime_bridge._dn_bootstrap("pedro", slug, "success", repo)

    assert decision is None
    assert ctx is not None
    assert ctx.feature_dir == _EXPECTED_DIR[cell](repo, slug)


@pytest.mark.parametrize("arm", [SHORT_CIRCUIT, COMPLETED_PRIMARY])
def test_landed_mission_with_a_retained_worktree_builds_no_context(tmp_path: Path, arm: str) -> None:
    repo, slug, _coord_root, coord_mission_dir = _landed_coord_mission(tmp_path, arm, MATERIALIZED)
    assert coord_mission_dir.is_dir()

    ctx, decision = runtime_bridge._dn_bootstrap("pedro", slug, "success", repo)

    assert ctx is None
    assert decision is not None
    assert str(decision.kind) == "terminal"
