"""UTF-8 git metadata retains non-ASCII worktree paths and exclusion patterns."""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.core.git_ops import exclude_from_git_index
from specify_cli.core.vcs.git import GitVCS
from specify_cli.core.worktree import _exclude_from_git

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_non_ascii_worktree_pointer_and_exclusions(tmp_path: Path) -> None:
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    git_dir = tmp_path / "données"
    (git_dir / "info").mkdir(parents=True)
    (worktree / ".git").write_text(f"gitdir: {git_dir}\n", encoding="utf-8")
    exclude = git_dir / "info" / "exclude"
    exclude.write_text("déjà/\n", encoding="utf-8")
    assert GitVCS()._get_git_dir(worktree) == git_dir
    _exclude_from_git(worktree, ["déjà/", "nouveau-é/"])
    assert exclude.read_text(encoding="utf-8").count("déjà/") == 1
    assert "nouveau-é/" in exclude.read_text(encoding="utf-8")


def test_non_ascii_repository_exclusions(tmp_path: Path) -> None:
    exclude = tmp_path / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True)
    exclude.write_text("déjà/\n", encoding="utf-8")
    exclude_from_git_index(tmp_path, ["déjà/", "nouveau-é/"])
    assert exclude.read_text(encoding="utf-8").count("déjà/") == 1
    assert "nouveau-é/" in exclude.read_text(encoding="utf-8")
