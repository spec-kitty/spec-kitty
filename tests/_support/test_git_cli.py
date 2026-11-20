"""Unit tests for :mod:`tests._support.git_cli`."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests._support.git_cli import commit_init_leftovers, git_out

pytestmark = [pytest.mark.git_repo]


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    for args in (("init", "-q", "-b", "main"), ("config", "user.name", "T"), ("config", "user.email", "t@example.invalid"), ("config", "commit.gpgsign", "false")):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
    return repo


def test_commits_leftovers_on_an_unborn_branch(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "a.txt").write_text("a\n", encoding="utf-8")

    assert commit_init_leftovers(repo, "init") is True

    assert git_out(repo, "log", "--format=%s") == "init"
    assert git_out(repo, "status", "--porcelain") == ""


def test_makes_no_commit_on_a_clean_tree(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    commit_init_leftovers(repo, "first")

    assert commit_init_leftovers(repo, "second") is False

    assert git_out(repo, "rev-list", "--count", "HEAD") == "1"
