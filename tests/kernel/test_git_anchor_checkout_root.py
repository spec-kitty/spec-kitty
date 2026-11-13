"""``kernel.git_anchor.checkout_root_containing``: the checkout that contains a path (#7546, FR-001).

Real repositories: the repository root checkout (``.git`` directory), a linked worktree
(``.git`` file), a path that does not exist yet, and a symbolic-link loop (the walk runs
over the lexical form).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from kernel.git_anchor import checkout_root_containing

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "--allow-empty", "-m", "init")
    return root


@pytest.fixture(autouse=True)
def _ceiling_above(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Bound every walk at *tmp_path*, so a checkout above the test folder never answers."""
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.resolve()))


def test_repository_root_checkout_has_a_git_directory_and_a_missing_path_resolves_to_it(repo: Path) -> None:
    assert (repo / ".git").is_dir()
    assert checkout_root_containing(repo) == repo.resolve()
    assert checkout_root_containing(repo / "kitty-specs" / "not-yet" / "created") == repo.resolve()


def test_linked_worktree_has_a_git_file_and_is_its_own_checkout(repo: Path) -> None:
    worktree = repo / ".worktrees" / "probe-coord"
    _git(repo, "worktree", "add", "-q", "-b", "topic", str(worktree))
    assert (worktree / ".git").is_file()
    inner = worktree / "kitty-specs" / "probe"
    inner.mkdir(parents=True)
    assert checkout_root_containing(inner) == worktree.resolve()


def test_a_symbolic_link_loop_answers_the_walk_over_its_lexical_form(repo: Path) -> None:
    loop = repo / "loop"
    loop.symlink_to(loop)
    assert checkout_root_containing(loop / "kitty-specs") == repo
