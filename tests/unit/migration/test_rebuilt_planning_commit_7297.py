"""#7297 item 2 / review N1: the doctor rebuild derives on the pin branch line, over real git."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.migration.mission_state import _rebuilt_planning_commit

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

SLUG = "demo-01ABCDEF"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _commit(repo: Path, rel: str, message: str) -> str:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(message + "\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    _git(root, "config", "commit.gpgsign", "false")
    _commit(root, "README.md", "init")
    return root


def test_a_single_branch_mission_derives_on_its_mission_branch(repo: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "kitty/mission-demo-01ABCDEF")
    before_tasks = _commit(repo, f"kitty-specs/{SLUG}/spec.md", "spec")
    _commit(repo, f"kitty-specs/{SLUG}/tasks/WP01-a.md", "tasks")
    meta = {"topology": "single_branch", "mission_branch": "kitty/mission-demo-01ABCDEF", "target_branch": "main"}

    assert _rebuilt_planning_commit(repo, SLUG, "main", meta=meta) == (before_tasks, True)
    # The control: read on the target branch alone, the tasks are not there and the tip stands in.
    assert _rebuilt_planning_commit(repo, SLUG, "main") == (_git(repo, "rev-parse", "main"), False)


def test_nothing_derivable_and_no_tip_leaves_the_pin_unset(repo: Path) -> None:
    assert _rebuilt_planning_commit(repo, SLUG, "no-such-branch") == (None, False)
