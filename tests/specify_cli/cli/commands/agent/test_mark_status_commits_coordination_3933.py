"""#3933: ``mark-status`` commits its subtask annotation on every topology under auto-commit.

#5655 made ``mark-status`` commit only on single_branch Missions. On a
coordination Mission it left ``status.events.jsonl`` and ``status.json``
modified in the coordination worktree until a later ``move-task`` happened to
commit them, so a gate in between saw them as dirt (observed in research.md).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.integration.cli_mission_fixture_7545 import create_mission, dirty, flat, init_repo

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.timeout(900)]


@pytest.fixture()
def mission(tmp_path: Path):
    repo, env = init_repo(tmp_path)
    mission = create_mission(repo, env, "delta", topology="coord")
    mission.run("agent", "action", "implement", "WP01", "--agent", "claude", "--mission", mission.slug, check=True)
    return mission


def test_mark_status_leaves_the_coordination_worktree_clean(mission) -> None:
    coord = mission.coordination_worktree()

    proc = mission.run("agent", "tasks", "mark-status", "T001", "--status", "done", "--mission", mission.slug)

    assert proc.returncode == 0, flat(proc)[-2000:]
    assert dirty(coord) == []


def test_no_auto_commit_still_leaves_the_annotation_uncommitted(mission) -> None:
    """Control: the operator's explicit opt-out keeps its meaning."""
    coord = mission.coordination_worktree()

    proc = mission.run("agent", "tasks", "mark-status", "T001", "--status", "done", "--no-auto-commit", "--mission", mission.slug)

    assert proc.returncode == 0, flat(proc)[-2000:]
    assert any(path.endswith("status.events.jsonl") for path in dirty(coord))
