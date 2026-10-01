"""The planning-commit merge names conflicting WP task files from the index, not git's prose.

Real-git tests: ``_wp_task_file_conflict_paths`` reads the unmerged set through
``kernel.git`` while the merge is still open (git-paths-are-data, #5392/#5400).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from specify_cli.lanes.worktree_allocator import _wp_task_file_conflict_paths

pytestmark = [pytest.mark.git_repo]

_WP_TASK = "kitty-specs/m é/tasks/WP01-a b.md"


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, check=check, capture_output=True, text=True, encoding="utf-8")


def _write(repo: Path, rel: str, text: str) -> None:
    target = repo / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "T")
    _git(root, "config", "commit.gpgsign", "false")
    _write(root, "README.md", "anchor\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "anchor")
    return root


def _conflict(repo: Path, rel: str, *, delete_on_lane: bool = False) -> None:
    """Leave an open merge of ``planning`` into ``lane`` that conflicts on *rel*."""
    _write(repo, rel, "base\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    _git(repo, "checkout", "-qb", "planning")
    _write(repo, rel, "planning\n")
    _git(repo, "commit", "-qam", "planning")
    _git(repo, "checkout", "-qb", "lane", "main")
    if delete_on_lane:
        _git(repo, "rm", "-q", rel)
    else:
        _write(repo, rel, "lane\n")
    _git(repo, "commit", "-qam", "lane")
    assert _git(repo, "merge", "--no-edit", "planning", check=False).returncode != 0


def _env() -> dict[str, str]:
    return dict(os.environ)


def test_content_conflict_on_a_wp_task_file_is_named_exactly(repo: Path) -> None:
    _conflict(repo, _WP_TASK)

    assert _wp_task_file_conflict_paths(repo, _env()) == [_WP_TASK]


def test_modify_delete_conflict_is_named_too(repo: Path) -> None:
    """git's prose has no "Merge conflict in" line for modify/delete; the index still lists it."""
    _conflict(repo, _WP_TASK, delete_on_lane=True)

    assert _wp_task_file_conflict_paths(repo, _env()) == [_WP_TASK]


def test_conflict_outside_tasks_is_not_a_wp_task_conflict(repo: Path) -> None:
    _conflict(repo, "kitty-specs/m/WP01-notes.md")

    assert _wp_task_file_conflict_paths(repo, _env()) == []


def test_unreadable_conflict_state_is_none(tmp_path: Path) -> None:
    assert _wp_task_file_conflict_paths(tmp_path, _env()) is None
