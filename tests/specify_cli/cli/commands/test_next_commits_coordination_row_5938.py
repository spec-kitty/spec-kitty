"""#5938: ``next`` commits the event row it writes into the coordination worktree.

Every ``spec-kitty next --result success`` appends a ``MissionNextInvoked`` row
to ``kitty-specs/<mission>/mission-events.jsonl``. On a coordination Mission that
file lives in the coordination worktree, and ``next`` left it untracked there,
so ``consolidate`` later refused ``MERGE_UNSAFE_WORKTREE_DIRTY`` on a file the
tool itself wrote. The #5669 ruling keeps the log real dirt for every gate, so
the fix is that ``next`` commits it; it is never exempted.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.integration.cli_mission_fixture_7545 import create_mission, dirty, flat, git, init_repo

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.timeout(900)]


@pytest.fixture()
def mission(tmp_path: Path):
    repo, env = init_repo(tmp_path)
    return create_mission(repo, env, "beta", topology="coord")


def _next(mission):
    return mission.run("next", "--agent", "claude", "--mission", mission.slug, "--json", "--result", "success")


def test_next_leaves_the_coordination_worktree_clean(mission) -> None:
    coord = mission.coordination_worktree()
    assert dirty(coord) == []

    proc = _next(mission)

    assert proc.returncode == 0, flat(proc)[-2000:]
    assert dirty(coord) == []
    committed = git(coord, "show", "--name-only", "--format=%s", "HEAD").splitlines()
    assert committed[0].startswith("chore(next): record next invocation")
    assert f"kitty-specs/{mission.slug}/mission-events.jsonl" in committed


def test_next_never_commits_an_operator_file_in_the_coordination_worktree(mission) -> None:
    coord = mission.coordination_worktree()
    (coord / "operator-notes.md").write_text("mine\n", encoding="utf-8")

    proc = _next(mission)

    assert proc.returncode == 0, flat(proc)[-2000:]
    assert dirty(coord) == ["operator-notes.md"]


def test_a_lane_cut_after_next_still_moves_to_review(mission) -> None:
    """The committed row reaches lanes parented on the coordination branch.

    The lane guard must tolerate that inherited, tool-written log exactly like
    the inherited status pair; before the predicate, ``move-task --to
    for_review`` refused with "kitty-specs/ changes are not allowed on lane
    branches".
    """
    assert _next(mission).returncode == 0
    mission.run("implement", "WP01", "--mission", mission.slug, check=True)
    lane = next(path for path in sorted((mission.repo / ".worktrees").iterdir()) if "-lane-" in path.name)
    (lane / "src" / "beta").mkdir(parents=True)
    (lane / "src" / "beta" / "mod.py").write_text("B = 1\n", encoding="utf-8")
    git(lane, "add", "src/beta")
    git(lane, "commit", "-qm", "WP01: beta")
    mission.run("agent", "tasks", "mark-status", "T001", "--status", "done", "--mission", mission.slug, check=True)

    proc = mission.run("agent", "tasks", "move-task", "WP01", "--to", "for_review", "--agent", "claude", "--mission", mission.slug)

    assert proc.returncode == 0, flat(proc)[-3000:]


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("kitty-specs/m-01ABCDEF/mission-events.jsonl", True),
        ("kitty-specs\\m-01ABCDEF\\mission-events.jsonl", True),
        ("kitty-specs/m-01ABCDEF/research/mission-events.jsonl", False),
        ("src/app/mission-events.jsonl", False),
        ("kitty-specs/m-01ABCDEF/status.events.jsonl", False),
    ],
)
def test_mission_event_log_predicate(path: str, expected: bool) -> None:
    from specify_cli.mission_v1.events import is_mission_event_log_path

    assert is_mission_event_log_path(path) is expected
