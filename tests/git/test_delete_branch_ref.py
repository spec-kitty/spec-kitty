"""Compare-and-swap delete for :func:`delete_branch_ref` (#5570).

``git update-ref -d refs/heads/<b> <expected_sha>`` removes the branch only while it
still points at the tip the caller approved, so a commit that landed after the approval
is never made unreachable. These are real-git tests over throwaway temp repositories;
the git subprocess is never mocked.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.git.ref_advance import (
    RefDeleteCheckedOutError,
    RefDeleteError,
    RefDeleteMismatchError,
    delete_branch_ref,
)

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]

_BRANCH = "kitty/mission-demo"


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True)
    return result.stdout.strip()


def _commit(root: Path, filename: str, message: str) -> str:
    (root / filename).write_text(message, encoding="utf-8")
    _git(root, "add", filename)
    _git(root, "commit", "--quiet", "-m", message)
    return _git(root, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "--quiet", "-b", "main")
    _git(root, "config", "user.email", "cas@example.com")
    _git(root, "config", "user.name", "CAS Test")
    _git(root, "config", "commit.gpgsign", "false")
    _commit(root, "seed.txt", "seed")
    return root


def _branch_tip(root: Path, branch: str) -> str | None:
    probe = subprocess.run(["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=str(root), capture_output=True, text=True, check=False)
    return probe.stdout.strip() if probe.returncode == 0 else None


def _commit_on_branch(root: Path, branch: str, message: str) -> str:
    """Land a real commit on ``branch`` from a throwaway worktree (the branch is not checked out in ``root``)."""
    scratch = root.parent / f"scratch-{message}"
    _git(root, "worktree", "add", "--quiet", str(scratch), branch)
    try:
        return _commit(scratch, f"{message}.txt", message)
    finally:
        _git(root, "worktree", "remove", "--force", str(scratch))


def test_deletes_the_branch_at_the_expected_tip(repo: Path) -> None:
    _git(repo, "branch", _BRANCH)
    tip = _branch_tip(repo, _BRANCH)
    assert tip is not None

    delete_branch_ref(repo, _BRANCH, tip)

    assert _branch_tip(repo, _BRANCH) is None


def test_refuses_and_keeps_the_branch_when_the_tip_moved(repo: Path) -> None:
    _git(repo, "branch", _BRANCH)
    approved = _branch_tip(repo, _BRANCH)
    assert approved is not None
    late = _commit_on_branch(repo, _BRANCH, "late")

    with pytest.raises(RefDeleteMismatchError) as caught:
        delete_branch_ref(repo, _BRANCH, approved)

    assert _branch_tip(repo, _BRANCH) == late, "the late commit must stay the branch tip"
    assert caught.value.actual_sha == late
    assert caught.value.expected_sha == approved
    assert _BRANCH in str(caught.value)
    assert late[:12] in str(caught.value)
    assert caught.value.error_code == "REF_DELETE_TIP_MOVED"


def test_refuses_a_missing_branch_as_a_mismatch(repo: Path) -> None:
    expected = _git(repo, "rev-parse", "HEAD")

    with pytest.raises(RefDeleteMismatchError) as caught:
        delete_branch_ref(repo, _BRANCH, expected)

    assert caught.value.actual_sha is None
    assert "no longer exists" in str(caught.value)


def test_deletes_a_packed_ref_at_the_expected_tip(repo: Path) -> None:
    _git(repo, "branch", _BRANCH)
    _git(repo, "pack-refs", "--all", "--prune")
    assert not (repo / ".git" / "refs" / "heads" / "kitty").exists(), "fixture invalid: the ref must be packed only"
    tip = _branch_tip(repo, _BRANCH)
    assert tip is not None

    delete_branch_ref(repo, _BRANCH, tip)

    assert _branch_tip(repo, _BRANCH) is None


def test_refuses_a_moved_packed_ref(repo: Path) -> None:
    _git(repo, "branch", _BRANCH)
    approved = _branch_tip(repo, _BRANCH)
    assert approved is not None
    late = _commit_on_branch(repo, _BRANCH, "late")
    _git(repo, "pack-refs", "--all", "--prune")

    with pytest.raises(RefDeleteMismatchError):
        delete_branch_ref(repo, _BRANCH, approved)

    assert _branch_tip(repo, _BRANCH) == late


def test_refuses_a_branch_checked_out_in_a_worktree(repo: Path, tmp_path: Path) -> None:
    """``update-ref -d`` ignores checkouts; the helper keeps ``git branch -D``'s protection (#3926)."""
    _git(repo, "branch", _BRANCH)
    tip = _branch_tip(repo, _BRANCH)
    assert tip is not None
    checkout = tmp_path / "coord-checkout"
    _git(repo, "worktree", "add", "--quiet", str(checkout), _BRANCH)

    with pytest.raises(RefDeleteCheckedOutError) as caught:
        delete_branch_ref(repo, _BRANCH, tip)

    assert _branch_tip(repo, _BRANCH) == tip
    assert caught.value.worktree_path == checkout
    assert isinstance(caught.value, RefDeleteError)


def test_refuses_the_branch_checked_out_in_the_repository_root(repo: Path) -> None:
    tip = _branch_tip(repo, "main")
    assert tip is not None

    with pytest.raises(RefDeleteCheckedOutError):
        delete_branch_ref(repo, "main", tip)

    assert _branch_tip(repo, "main") == tip


def test_a_git_failure_that_is_not_a_tip_mismatch_raises_the_base_error(repo: Path) -> None:
    """A refusal with the tip unchanged (a held ref lock) is the base error, never a tip mismatch."""
    _git(repo, "branch", _BRANCH)
    tip = _branch_tip(repo, _BRANCH)
    assert tip is not None
    lock = repo / ".git" / "refs" / "heads" / "kitty" / "mission-demo.lock"
    lock.write_text("", encoding="utf-8")

    with pytest.raises(RefDeleteError) as caught:
        delete_branch_ref(repo, _BRANCH, tip)

    assert not isinstance(caught.value, RefDeleteMismatchError)
    assert _branch_tip(repo, _BRANCH) == tip
