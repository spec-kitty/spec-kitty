"""``resync_checkouts_to_tip``: bring a branch's checkouts back to its CURRENT tip, never move the ref (#5638).

Real-git tests over throwaway temp repositories; nothing is mocked.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.git.ref_advance import RefAdvanceDirtyWorktreeError, RefAdvanceError, resync_checkouts_to_tip

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]

_BRANCH = "coord"
_STATUS = "status.events.jsonl"


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True).stdout.strip()


def _repo_with_checkout(tmp_path: Path) -> tuple[Path, Path, str]:
    """A repo whose ``coord`` branch is checked out in a linked worktree; returns (repo, worktree, tip)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--quiet", "-b", "main")
    for key, value in (("user.email", "t@example.com"), ("user.name", "T"), ("commit.gpgsign", "false")):
        _git(repo, "config", key, value)
    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    _git(repo, "add", "base.txt")
    _git(repo, "commit", "--quiet", "-m", "base")
    worktree = tmp_path / "coord-wt"
    _git(repo, "worktree", "add", "-q", "-b", _BRANCH, str(worktree))
    (worktree / _STATUS).write_text("approved\ndone\n", encoding="utf-8")
    (worktree / "notes.md").write_text("notes\n", encoding="utf-8")
    _git(worktree, "add", "-A")
    _git(worktree, "commit", "--quiet", "-m", "done")
    return repo, worktree, _git(repo, "rev-parse", f"refs/heads/{_BRANCH}")


def _is_status(path: str) -> bool:
    return path.endswith(_STATUS)


def test_residue_only_drift_is_reset_to_the_tip_and_the_ref_stays(tmp_path: Path) -> None:
    repo, worktree, tip = _repo_with_checkout(tmp_path)
    (worktree / _STATUS).write_text("approved\n", encoding="utf-8")

    reset = resync_checkouts_to_tip(repo, _BRANCH, is_residue=_is_status)

    assert [p.resolve() for p in reset] == [worktree.resolve()]
    assert (worktree / _STATUS).read_text(encoding="utf-8") == "approved\ndone\n"
    assert _git(repo, "rev-parse", f"refs/heads/{_BRANCH}") == tip
    assert _git(worktree, "status", "--porcelain") == ""


def test_a_consistent_checkout_is_left_alone(tmp_path: Path) -> None:
    repo, _worktree, _tip = _repo_with_checkout(tmp_path)

    assert resync_checkouts_to_tip(repo, _BRANCH, is_residue=_is_status) == []


def test_a_non_residue_edit_refuses_and_nothing_is_reset(tmp_path: Path) -> None:
    repo, worktree, _tip = _repo_with_checkout(tmp_path)
    (worktree / _STATUS).write_text("approved\n", encoding="utf-8")
    (worktree / "notes.md").write_text("operator edit\n", encoding="utf-8")

    with pytest.raises(RefAdvanceDirtyWorktreeError):
        resync_checkouts_to_tip(repo, _BRANCH, is_residue=_is_status)

    assert (worktree / "notes.md").read_text(encoding="utf-8") == "operator edit\n"
    assert (worktree / _STATUS).read_text(encoding="utf-8") == "approved\n"


def test_a_missing_branch_raises(tmp_path: Path) -> None:
    repo, _worktree, _tip = _repo_with_checkout(tmp_path)

    with pytest.raises(RefAdvanceError, match="no-such-branch"):
        resync_checkouts_to_tip(repo, "no-such-branch")
