"""``kernel.git_anchor.checkout_root_containing``: the checkout that contains a path (#7546, FR-001).

Real repositories: the repository root checkout (``.git`` directory), a linked worktree
(``.git`` file), a nested folder, a path that does not exist yet, a path outside every
checkout, and a symbolic-link start (the answer is the resolved checkout).
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


def test_repository_root_checkout_contains_itself(repo: Path) -> None:
    assert checkout_root_containing(repo) == repo.resolve()


def test_nested_folder_and_a_path_not_yet_created_resolve_to_the_root_checkout(repo: Path) -> None:
    nested = repo / "kitty-specs" / "mission"
    nested.mkdir(parents=True)
    assert checkout_root_containing(nested) == repo.resolve()
    assert checkout_root_containing(nested / "not-yet" / "created") == repo.resolve()


def test_linked_worktree_is_its_own_checkout(repo: Path) -> None:
    worktree = repo / ".worktrees" / "probe-coord"
    _git(repo, "worktree", "add", "-q", "-b", "topic", str(worktree))
    assert (worktree / ".git").is_file()
    inner = worktree / "kitty-specs" / "probe"
    inner.mkdir(parents=True)
    assert checkout_root_containing(inner) == worktree.resolve()


def test_path_outside_every_checkout_is_none(tmp_path: Path) -> None:
    outside = tmp_path / "elsewhere" / "kitty-specs"
    outside.mkdir(parents=True)
    assert checkout_root_containing(outside) is None


def test_symlinked_start_answers_the_resolved_checkout(repo: Path, tmp_path: Path) -> None:
    nested = repo / "kitty-specs"
    nested.mkdir()
    link = tmp_path / "alias"
    link.symlink_to(nested, target_is_directory=True)
    assert checkout_root_containing(link) == repo.resolve()
