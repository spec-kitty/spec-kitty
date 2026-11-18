"""#7612: ``safe_commit(allow_root_commit=True)`` makes the root commit of an unborn branch.

The commit-scope census (``tests/architectural/test_commit_scope_owner.py``) keeps
``safe_commit`` the one owner of a path-scoped commit, so the repository's first
commit goes through it too, behind an explicit opt-in. Without the opt-in an unborn
destination is still refused, and the opt-in cannot be combined with the modes that
need a parent.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from specify_cli.core.commit_guard import GuardCapability
from specify_cli.git.commit_helpers import CommitResult, SafeCommitDestinationNotFound, SafeCommitHeadMismatch, safe_commit

pytestmark = [pytest.mark.git_repo]


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout


@pytest.fixture
def unborn(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "trunk")
    _git(repo, "config", "user.name", "QA")
    _git(repo, "config", "user.email", "qa@example.invalid")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "mine.txt").write_text("written\n", encoding="utf-8")
    (repo / "other.txt").write_text("operator\n", encoding="utf-8")
    (repo / "staged.txt").write_text("operator staged\n", encoding="utf-8")
    _git(repo, "add", "staged.txt")
    return repo


def _commit(repo: Path, **kwargs: Any) -> CommitResult:
    return safe_commit(
        repo_root=repo,
        worktree_root=repo,
        destination_ref="trunk",
        message="root",
        paths=(Path("mine.txt"),),
        capability=GuardCapability.UPGRADE_BOOKKEEPING,
        **kwargs,
    )


def test_root_commit_holds_only_the_requested_paths(unborn: Path) -> None:
    result = _commit(unborn, allow_root_commit=True)

    sha = _git(unborn, "rev-parse", "HEAD").strip()
    assert result.sha == sha
    assert _git(unborn, "rev-list", "--parents", "-n", "1", "HEAD").split() == [sha]
    assert _git(unborn, "ls-tree", "-r", "--name-only", "HEAD").split() == ["mine.txt"]
    # The operator's staged entry stays staged; their untracked file stays untracked.
    assert _git(unborn, "diff", "--cached", "--name-only").split() == ["staged.txt"]
    assert "?? other.txt" in _git(unborn, "status", "--porcelain")


def test_unborn_destination_without_the_opt_in_is_still_refused(unborn: Path) -> None:
    with pytest.raises(SafeCommitDestinationNotFound):
        _commit(unborn)
    assert subprocess.run(["git", "rev-parse", "--verify", "-q", "HEAD"], cwd=unborn, check=False).returncode != 0


def test_the_opt_in_never_lands_on_a_branch_head_does_not_name(unborn: Path) -> None:
    with pytest.raises(SafeCommitHeadMismatch):
        safe_commit(
            repo_root=unborn,
            worktree_root=unborn,
            destination_ref="elsewhere",
            message="root",
            paths=(Path("mine.txt"),),
            capability=GuardCapability.UPGRADE_BOOKKEEPING,
            allow_root_commit=True,
        )


@pytest.mark.parametrize(
    "extra",
    [
        {"index_deletions": (Path("staged.txt"),)},
        {"expected_parent_sha": "0" * 40},
    ],
    ids=["index_deletions", "expected_parent_sha"],
)
def test_the_opt_in_refuses_modes_that_need_a_parent(unborn: Path, extra: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="root commit has no parent"):
        _commit(unborn, allow_root_commit=True, **extra)


def test_the_opt_in_is_harmless_on_a_born_branch(unborn: Path) -> None:
    _git(unborn, "commit", "-q", "-m", "first", "--", "staged.txt")
    parent = _git(unborn, "rev-parse", "HEAD").strip()

    _commit(unborn, allow_root_commit=True)

    assert _git(unborn, "rev-parse", "HEAD^").strip() == parent
