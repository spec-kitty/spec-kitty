"""The commit router classifies a symlink argument by where the link lives (#5671)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from specify_cli.coordination.commit_router import _dirty_paths_in_checkout, _is_directly_in_worktree, _relpath


def _symlink(link: Path, target: str | Path) -> None:
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError):
        pytest.skip("os.symlink unavailable (Windows without developer mode)")


@pytest.mark.unit
@pytest.mark.fast
def test_in_worktree_link_pointing_outside_is_still_in_the_worktree(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    worktree.mkdir()
    outside = tmp_path / "outside" / "real.md"
    outside.parent.mkdir()
    outside.write_text("x")
    _symlink(worktree / "link.md", outside)
    assert _is_directly_in_worktree(worktree / "link.md", worktree) is True


@pytest.mark.unit
@pytest.mark.fast
def test_foreign_file_is_not_in_the_worktree(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    worktree.mkdir()
    (tmp_path / "other.md").write_text("x")
    assert _is_directly_in_worktree(tmp_path / "other.md", worktree) is False


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for key in list(os.environ):
        if key.startswith(("GIT_", "SPEC_KITTY_")):
            monkeypatch.delenv(key)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(home / ".gitconfig"))
    r = tmp_path / "repo"
    r.mkdir()

    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=r, check=True, capture_output=True)

    git("init", "--template=", "-q", "-b", "work")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "T")
    git("config", "commit.gpgsign", "false")
    (r / "real.md").write_text("base\n")
    git("add", "-A")
    git("commit", "-q", "-m", "init")
    return r


@pytest.mark.git_repo
@pytest.mark.non_sandbox
@pytest.mark.regression
def test_new_link_is_dirty_when_the_target_is_clean(repo: Path) -> None:
    _symlink(repo / "link.md", "real.md")
    assert _dirty_paths_in_checkout(repo, (repo / "link.md",)) == (repo / "link.md",)


@pytest.mark.git_repo
@pytest.mark.non_sandbox
@pytest.mark.regression
def test_committed_link_is_clean_when_only_the_target_has_wip(repo: Path) -> None:
    _symlink(repo / "link.md", "real.md")
    subprocess.run(["git", "add", "link.md"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", "link"], cwd=repo, check=True, capture_output=True)
    (repo / "real.md").write_text("base\nWIP\n")
    assert _dirty_paths_in_checkout(repo, (repo / "link.md",)) == ()


def test_relpath_renders_a_symlink_loop_instead_of_raising(tmp_path: Path) -> None:
    _symlink(tmp_path / "loop", "loop")
    assert _relpath(tmp_path, tmp_path / "loop" / "x.md").endswith("loop/x.md")


def test_is_directly_in_worktree_is_false_for_a_symlink_loop(tmp_path: Path) -> None:
    _symlink(tmp_path / "loop", "loop")
    assert _is_directly_in_worktree(tmp_path / "loop" / "x.md", tmp_path) is False
