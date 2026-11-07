"""Unit tests for ``lane_branch_has_commit_beyond_base`` (S2 / #7278, FR-010, FR-012, FR-014)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.lanes._git import lane_branch_has_commit_beyond_base

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.invalid")
    _git(tmp_path, "config", "user.name", "Test")
    _git(tmp_path, "config", "commit.gpgsign", "false")
    (tmp_path / "a.txt").write_text("a\n", encoding="utf-8")
    _git(tmp_path, "add", "a.txt")
    _git(tmp_path, "commit", "-q", "-m", "base")
    return tmp_path


def _commit(repo: Path, name: str) -> None:
    (repo / name).write_text(name, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "-q", "-m", name)


def test_branch_with_commit_beyond_base(repo: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "lane")
    _commit(repo, "b.txt")
    _git(repo, "checkout", "-q", "main")
    assert lane_branch_has_commit_beyond_base(repo, "main", "lane") is True


def test_branch_without_commit_beyond_base(repo: Path) -> None:
    _git(repo, "branch", "lane")
    assert lane_branch_has_commit_beyond_base(repo, "main", "lane") is False


def test_missing_branch_is_none(repo: Path) -> None:
    assert lane_branch_has_commit_beyond_base(repo, "main", "nope") is None


def test_unresolvable_base_fails_closed(repo: Path) -> None:
    _git(repo, "branch", "lane")
    assert lane_branch_has_commit_beyond_base(repo, "no-such-base", "lane") is False


def test_dash_prefixed_ref_not_option(repo: Path) -> None:
    # A base or branch beginning with '-' must never be read as an option.
    _git(repo, "branch", "lane")
    assert lane_branch_has_commit_beyond_base(repo, "--all", "lane") is False
    assert lane_branch_has_commit_beyond_base(repo, "main", "--all") is None
    assert lane_branch_has_commit_beyond_base(repo, "-n1", "-n1") is None
