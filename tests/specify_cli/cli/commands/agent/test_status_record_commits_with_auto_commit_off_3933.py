"""#3933 F-39/F-73: with ``auto_commit: false`` a transition's record is still committed whole.

``move-task`` always commits its lane transition (the status door commits it,
whatever ``auto_commit`` says). With the project default ``auto_commit: false``
it then left the rest of that same record uncommitted: the ``--note``
annotation, the refreshed ``status.json`` and, on an approval or rejection, the
review-cycle verdict. ``mark-status`` left its subtask annotation uncommitted
too. Every work package of Mission ``cli-owns-its-commits-01M75NTA`` needed a
hand commit for it.

The rule now: the status record a command writes is committed unless the
operator passes ``--no-auto-commit`` explicitly. ``auto_commit`` keeps governing
the operator's own work (lane deliverables are never committed for them).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.integration.cli_mission_fixture_7545 import create_mission, dirty, flat, git, init_repo

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.timeout(1200)]


@pytest.fixture()
def mission(tmp_path: Path):
    repo, env = init_repo(tmp_path)
    mission = create_mission(repo, env, "eta", topology="single_branch")
    mission.run("agent", "config", "set", "auto_commit", "false", check=True)
    if dirty(repo):
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "auto_commit: false")
    mission.run("agent", "action", "implement", "WP01", "--agent", "claude", "--mission", mission.slug, check=True)
    (repo / "src" / "eta").mkdir(parents=True)
    (repo / "src" / "eta" / "mod.py").write_text("E = 1\n", encoding="utf-8")
    git(repo, "add", "src/eta")
    git(repo, "commit", "-qm", "WP01: eta")
    return mission


def _status_dirt(mission) -> list[str]:
    return [path for path in dirty(mission.repo) if path.startswith(f"kitty-specs/{mission.slug}/")]


def test_a_transition_record_is_committed_whole_with_auto_commit_off(mission) -> None:
    proc = mission.run("agent", "tasks", "mark-status", "T001", "--status", "done", "--mission", mission.slug)
    assert proc.returncode == 0, flat(proc)[-2000:]
    assert _status_dirt(mission) == []

    proc = mission.run("agent", "tasks", "move-task", "WP01", "--to", "for_review", "--agent", "claude", "--note", "ready", "--mission", mission.slug)
    assert proc.returncode == 0, flat(proc)[-3000:]
    assert _status_dirt(mission) == []

    mission.run("agent", "action", "review", "WP01", "--agent", "codex", "--mission", mission.slug, check=True)
    proc = mission.run("agent", "tasks", "move-task", "WP01", "--to", "approved", "--agent", "codex", "--note", "looks good", "--mission", mission.slug)
    assert proc.returncode == 0, flat(proc)[-3000:]
    assert _status_dirt(mission) == [], "the approval's note, snapshot and review-cycle verdict must be committed with it"
    assert "NOT committed" not in flat(proc)


def test_explicit_no_auto_commit_keeps_the_annotation_local(mission) -> None:
    """Control: the operator's explicit opt-out keeps its meaning."""
    proc = mission.run("agent", "tasks", "mark-status", "T001", "--status", "done", "--no-auto-commit", "--mission", mission.slug)

    assert proc.returncode == 0, flat(proc)[-2000:]
    assert any(path.endswith("status.events.jsonl") for path in _status_dirt(mission))


def test_operator_code_is_never_committed_by_a_status_move(mission) -> None:
    """Control (#5905): the status record commits, the operator's uncommitted code does not."""
    mission.run("agent", "tasks", "mark-status", "T001", "--status", "done", "--mission", mission.slug, check=True)
    (mission.repo / "src" / "eta" / "scratch.py").write_text("WIP = True\n", encoding="utf-8")

    mission.run("agent", "tasks", "move-task", "WP01", "--to", "blocked", "--agent", "claude", "--note", "waiting", "--mission", mission.slug)

    assert "src/eta/scratch.py" in dirty(mission.repo)
    assert _status_dirt(mission) == []
