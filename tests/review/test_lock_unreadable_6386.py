"""Unit tests for the review lock's field validation and pre-claim check (#6386).

A committed or tracked lock is refused (``REVIEW_LOCK_COMMITTED``) whatever its
content; an untracked lock is refused only when it cannot be read
(``REVIEW_LOCK_UNREADABLE``).
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

from specify_cli.review.lock import (
    LOCK_REL_PATH,
    REVIEW_LOCK_COMMITTED,
    REVIEW_LOCK_UNREADABLE,
    ReviewLock,
    ReviewLockReadError,
    review_lock_refusal,
)

pytestmark = pytest.mark.fast

_VALID = {"worktree_path": "/w", "wp_id": "WP01", "agent": "claude", "started_at": "2026-10-21T00:00:00+00:00", "pid": 1}


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    (root / "README.md").write_text("x\n")
    _git(root, "add", "README.md")
    _git(root, "commit", "-qm", "init")
    return root


def _write_lock(worktree: Path, content: str) -> Path:
    lock = worktree / LOCK_REL_PATH
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(content)
    return lock


# --- from_dict -------------------------------------------------------------


def test_from_dict_round_trips_a_saved_lock() -> None:
    assert ReviewLock.from_dict(dict(_VALID)).to_dict() == _VALID


@pytest.mark.parametrize(
    ("data", "fragment"),
    [
        ({}, "missing field(s) worktree_path, wp_id, agent, started_at, pid"),
        ({**_VALID, "extra": 1}, "unknown field(s) extra"),
        ({k: v for k, v in _VALID.items() if k != "pid"} | {"x": 1}, "missing field(s) pid; unknown field(s) x"),
        ({**_VALID, "pid": "1"}, "wrong type: pid"),
        ({**_VALID, "pid": True}, "wrong type: pid"),
        ({**_VALID, "agent": None}, "wrong type: agent"),
        ([], "expected a JSON object, found list"),
    ],
)
def test_from_dict_names_what_is_wrong(data: Any, fragment: str) -> None:
    with pytest.raises(TypeError) as excinfo:
        ReviewLock.from_dict(data)
    assert fragment in str(excinfo.value)


def test_load_of_empty_object_names_the_file_and_fields(tmp_path: Path) -> None:
    """The reported ``{}`` lock: a ``ReviewLockReadError`` naming the path and the missing fields."""
    lock = _write_lock(tmp_path, "{}")
    with pytest.raises(ReviewLockReadError) as excinfo:
        ReviewLock.load(tmp_path)
    assert excinfo.value.path == str(lock)
    assert "missing field(s)" in str(excinfo.value)
    assert "__init__" not in str(excinfo.value)


# --- review_lock_refusal: existing workspace ------------------------------


def test_existing_workspace_without_lock_passes(repo: Path) -> None:
    assert review_lock_refusal(repo, exists=True, repo_root=repo, checkout_ref=None, branch="main") is None


def test_existing_workspace_with_valid_lock_passes(repo: Path) -> None:
    _write_lock(repo, json.dumps({**_VALID, "pid": os.getpid()}))
    assert review_lock_refusal(repo, exists=True, repo_root=repo, checkout_ref=None, branch="main") is None


def test_untracked_unreadable_lock_offers_delete_and_is_left_alone(repo: Path) -> None:
    lock = _write_lock(repo, "{not json")

    message = review_lock_refusal(repo, exists=True, repo_root=repo, checkout_ref=None, branch="main")

    assert message is not None
    assert message.startswith(f"{REVIEW_LOCK_UNREADABLE}:")
    assert str(lock) in message
    assert f"rm {lock}" in message
    assert "git -C" not in message
    assert lock.read_text() == "{not json", "the check never rewrites the lock"


def _commit_lock(repo: Path, content: str) -> Path:
    lock = _write_lock(repo, content)
    _git(repo, "add", "-f", LOCK_REL_PATH)
    _git(repo, "commit", "-qm", "oops")
    return lock


def test_tracked_unreadable_lock_offers_untrack(repo: Path) -> None:
    _commit_lock(repo, "{}")

    message = review_lock_refusal(repo, exists=True, repo_root=repo, checkout_ref=None, branch="main")

    assert message is not None
    assert message.startswith(f"{REVIEW_LOCK_COMMITTED}:")
    assert "is tracked by git and cannot be read (missing field(s)" in message
    assert "committed on main" in message
    assert f"git -C {repo} rm -q {LOCK_REL_PATH}" in message
    assert "git worktree add" not in message, "the workspace already exists"


@pytest.mark.parametrize("exists", [True, False])
def test_a_git_failure_refuses_instead_of_reading_as_no_lock(tmp_path: Path, exists: bool) -> None:
    """Fail closed: a checkout git cannot read (here, not a repository) is not "no committed lock"."""
    _write_lock(tmp_path, json.dumps({**_VALID, "pid": os.getpid()}))
    ref = None if exists else "main"

    message = review_lock_refusal(tmp_path, exists=exists, repo_root=tmp_path, checkout_ref=ref, branch="main")

    assert message is not None
    assert message.startswith(f"{REVIEW_LOCK_UNREADABLE}:")
    assert "git could not check it" in message


# --- review_lock_refusal: workspace still to be created -------------------


def test_missing_workspace_reads_the_committed_blob(repo: Path, tmp_path: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "kitty/lane-a")
    _write_lock(repo, "{}")
    _git(repo, "add", "-f", LOCK_REL_PATH)
    _git(repo, "commit", "-qm", "oops")
    _git(repo, "checkout", "-q", "main")
    worktree = tmp_path / "lane"

    message = review_lock_refusal(worktree, exists=False, repo_root=repo, checkout_ref="kitty/lane-a", branch="kitty/lane-a")

    assert message is not None
    assert message.startswith(f"{REVIEW_LOCK_COMMITTED}:")
    assert f"kitty/lane-a:{LOCK_REL_PATH}" in message
    assert "committed on kitty/lane-a" in message
    assert f"git worktree add {worktree} kitty/lane-a" in message
    assert f"git -C {worktree} rm -q {LOCK_REL_PATH}" in message
    assert "commit -m" not in message, "no raw git-commit recipe is printed"
    assert not worktree.exists()


def test_missing_workspace_cut_from_a_start_point_names_that_source(repo: Path, tmp_path: Path) -> None:
    """No local lane branch: the lock comes from the start point, so the remedy names it, with no worktree command."""
    _write_lock(repo, "{}")
    _git(repo, "add", "-f", LOCK_REL_PATH)
    _git(repo, "commit", "-qm", "oops")

    message = review_lock_refusal(tmp_path / "lane", exists=False, repo_root=repo, checkout_ref="HEAD", branch="kitty/lane-a")

    assert message is not None
    assert f"committed on HEAD; it must not be. Remove {LOCK_REL_PATH} there" in message
    assert "git worktree add" not in message


def test_missing_workspace_falls_back_to_the_ref_when_no_branch(repo: Path, tmp_path: Path) -> None:
    _write_lock(repo, "[]")
    _git(repo, "add", "-f", LOCK_REL_PATH)
    _git(repo, "commit", "-qm", "oops")

    message = review_lock_refusal(tmp_path / "lane", exists=False, repo_root=repo, checkout_ref="main", branch=None)

    assert message is not None and "committed on main" in message


def test_missing_workspace_without_a_committed_lock_passes(repo: Path, tmp_path: Path) -> None:
    assert review_lock_refusal(tmp_path / "lane", exists=False, repo_root=repo, checkout_ref="main", branch="b") is None


# --- a committed lock is refused whatever its content (operator ruling, option a) ---


def test_missing_workspace_with_a_readable_committed_lock_is_refused(repo: Path, tmp_path: Path) -> None:
    """A valid lock with a stale PID used to be overwritten in place, leaving the tracked file modified."""
    _commit_lock(repo, json.dumps(_VALID))

    message = review_lock_refusal(tmp_path / "lane", exists=False, repo_root=repo, checkout_ref="main", branch="main")

    assert message is not None
    assert message.startswith(f"{REVIEW_LOCK_COMMITTED}: refusing to start the review; the review lock main:{LOCK_REL_PATH} is tracked by git.")
    assert "cannot be read" not in message
    assert "The work package was not claimed for review." in message
    assert f"rm -q {LOCK_REL_PATH}" in message


def test_existing_workspace_with_a_readable_tracked_lock_is_refused(repo: Path) -> None:
    lock = _commit_lock(repo, json.dumps({**_VALID, "pid": os.getpid()}))

    message = review_lock_refusal(repo, exists=True, repo_root=repo, checkout_ref=None, branch="main")

    assert message is not None
    assert message.startswith(f"{REVIEW_LOCK_COMMITTED}: refusing to start the review; the review lock {lock} is tracked by git.")
    assert f"git -C {repo} rm -q {LOCK_REL_PATH}" in message
    assert json.loads(lock.read_text())["pid"] == os.getpid(), "the check never rewrites the lock"


def test_tracked_lock_deleted_by_a_release_is_still_refused(repo: Path) -> None:
    """The #6386 collateral: release unlinked a tracked lock, leaving ``D .spec-kitty/review-lock.json``."""
    lock = _commit_lock(repo, json.dumps(_VALID))
    lock.unlink()

    message = review_lock_refusal(repo, exists=True, repo_root=repo, checkout_ref=None, branch="main")

    assert message is not None and message.startswith(f"{REVIEW_LOCK_COMMITTED}:")
    assert f"git -C {repo} rm -q {LOCK_REL_PATH}" in message


def test_untracked_readable_lock_passes(repo: Path) -> None:
    """An ordinary lock (ignored or untracked) is not refused; ``acquire`` judges its liveness."""
    _write_lock(repo, json.dumps(_VALID))
    assert review_lock_refusal(repo, exists=True, repo_root=repo, checkout_ref=None, branch="main") is None


def test_missing_workspace_without_a_ref_passes(repo: Path, tmp_path: Path) -> None:
    assert review_lock_refusal(tmp_path / "lane", exists=False, repo_root=repo, checkout_ref=None, branch=None) is None


def test_missing_workspace_with_unknown_ref_passes(repo: Path, tmp_path: Path) -> None:
    """An unresolvable ref is not a lock problem; worktree creation reports it."""
    assert review_lock_refusal(tmp_path / "lane", exists=False, repo_root=repo, checkout_ref="nope", branch="nope") is None


# --- remedy accuracy (pre-PR review) -----------------------------------------


def test_pre_claim_text_says_nothing_was_claimed(tmp_path: Path) -> None:
    _write_lock(tmp_path, "{}")
    message = review_lock_refusal(tmp_path, exists=True, repo_root=tmp_path, checkout_ref=None, branch="b")
    assert message is not None
    assert "The work package was not claimed for review." in message
    assert "already recorded" not in message


def test_claimed_text_says_the_claim_was_recorded(tmp_path: Path) -> None:
    _write_lock(tmp_path, "{}")
    message = review_lock_refusal(tmp_path, exists=True, repo_root=tmp_path, checkout_ref=None, branch="b", claimed=True)
    assert message is not None
    assert "The review claim was already recorded" in message
    assert "not claimed" not in message


def test_tracked_lock_without_a_branch_name_names_the_checked_out_branch(repo: Path) -> None:
    """A repository root checkout resolves with no branch name; the remedy names HEAD's branch, never ``None``."""
    _write_lock(repo, "{}")
    _git(repo, "add", "-f", LOCK_REL_PATH)
    _git(repo, "commit", "-qm", "oops")

    message = review_lock_refusal(repo, exists=True, repo_root=repo, checkout_ref=None, branch=None)

    assert message is not None
    assert "committed on main" in message and "None" not in message


def test_tracked_lock_on_a_detached_head_still_reads(repo: Path) -> None:
    _write_lock(repo, "{}")
    _git(repo, "add", "-f", LOCK_REL_PATH)
    _git(repo, "commit", "-qm", "oops")
    _git(repo, "checkout", "-q", "--detach")

    message = review_lock_refusal(repo, exists=True, repo_root=repo, checkout_ref=None, branch=None)

    assert message is not None and "committed on the checked-out branch" in message


def test_paths_with_spaces_are_quoted(tmp_path: Path) -> None:
    worktree = tmp_path / "with space"
    lock = _write_lock(worktree, "{}")
    message = review_lock_refusal(worktree, exists=True, repo_root=worktree, checkout_ref=None, branch="b")
    assert message is not None
    assert f"rm '{lock}'" in message
