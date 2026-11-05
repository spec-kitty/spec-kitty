"""Unit tests for the git-derived planning-commit base (#7209, #7210)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.lanes.derived_planning_base import (
    derive_base_before_first_add,
    mission_meta_pathspec,
    mission_wp_tasks_pathspec,
)

pytestmark = pytest.mark.git_repo

SLUG = "demo-mission"


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
    return root


def test_returns_parent_of_the_commit_that_first_added_meta_json(repo: Path) -> None:
    base = _commit(repo, "README.md", "init")
    _commit(repo, f"kitty-specs/{SLUG}/meta.json", "create mission")
    _commit(repo, f"kitty-specs/{SLUG}/meta.json", "edit meta")
    _commit(repo, "src/code.py", "implement")

    assert derive_base_before_first_add(repo, "main", mission_meta_pathspec(SLUG)) == base


def test_wp_tasks_pathspec_matches_only_wp_task_files(repo: Path) -> None:
    _commit(repo, "README.md", "init")
    _commit(repo, f"kitty-specs/{SLUG}/tasks/README.md", "tasks readme")
    before_wps = _commit(repo, f"kitty-specs/{SLUG}/spec.md", "spec")
    _commit(repo, f"kitty-specs/{SLUG}/tasks/WP01-first.md", "add WP01")
    _commit(repo, f"kitty-specs/{SLUG}/tasks/WP02-second.md", "add WP02")

    assert derive_base_before_first_add(repo, "main", mission_wp_tasks_pathspec(SLUG)) == before_wps


def test_other_missions_files_are_not_matched(repo: Path) -> None:
    _commit(repo, "README.md", "init")
    _commit(repo, "kitty-specs/demo-mission-two/meta.json", "other mission")

    assert derive_base_before_first_add(repo, "main", mission_meta_pathspec(SLUG)) is None


def test_none_when_the_adding_commit_is_the_root_commit(repo: Path) -> None:
    _commit(repo, f"kitty-specs/{SLUG}/meta.json", "root adds meta")

    assert derive_base_before_first_add(repo, "main", mission_meta_pathspec(SLUG)) is None


def test_none_when_the_target_ref_does_not_resolve(repo: Path) -> None:
    _commit(repo, f"kitty-specs/{SLUG}/meta.json", "root adds meta")
    _commit(repo, "src/code.py", "more")

    assert derive_base_before_first_add(repo, "no-such-branch", mission_meta_pathspec(SLUG)) is None


def test_none_outside_a_git_repository(tmp_path: Path) -> None:
    assert derive_base_before_first_add(tmp_path, "main", mission_meta_pathspec(SLUG)) is None


def test_only_history_reachable_from_the_target_counts(repo: Path) -> None:
    _commit(repo, "README.md", "init")
    _git(repo, "checkout", "-q", "-b", "side")
    _commit(repo, f"kitty-specs/{SLUG}/meta.json", "create on side")
    _git(repo, "checkout", "-q", "main")

    assert derive_base_before_first_add(repo, "main", mission_meta_pathspec(SLUG)) is None
