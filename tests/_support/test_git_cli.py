"""Unit tests for :mod:`tests._support.git_cli`."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests._support.git_cli import commit_init_leftovers, git_out, real_git_command

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


def test_real_git_command_resolves_an_existing_ref_in_the_given_repo(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    commit_init_leftovers(repo, "first")

    ret, out, _err = real_git_command(["git", "rev-parse", "main"], repo)

    assert (ret, out.strip()) == (0, git_out(repo, "rev-parse", "HEAD"))


def test_real_git_command_reports_an_unknown_object_instead_of_raising(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    ret, out, err = real_git_command(["git", "rev-parse", "--verify", "d4f8a1c2e6b09f37a5c1e8b2f4a6d0c9e3b7f1a2^{commit}"], repo)

    assert ret != 0
    assert out.strip() == ""
    assert err.strip() != ""
