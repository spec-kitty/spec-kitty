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

from kernel.git import GitCommandError
from specify_cli.review import lock as lock_module
from specify_cli.review.lock import (
    LOCK_REL_PATH,
    REVIEW_LOCK_COMMITTED,
    REVIEW_LOCK_UNREADABLE,
    ReviewLock,
    ReviewLockReadError,
    review_lock_refusal,
)

pytestmark = pytest.mark.fast

_NOT_A_REPO = "<not-a-repository>"

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
def test_from_dict_names_what_is_wrong(data: Any, fragment: str, tmp_path: Path) -> None:
    with pytest.raises(TypeError) as excinfo:
        ReviewLock.from_dict(data)
    assert fragment in str(excinfo.value)
    # The same record on disk: ``load`` names the file and the fields, never an unattributed ``__init__`` error.
    lock = _write_lock(tmp_path, json.dumps(data))
    with pytest.raises(ReviewLockReadError) as loaded:
        ReviewLock.load(tmp_path)
    assert loaded.value.path == str(lock)
    assert fragment in str(loaded.value)
    assert "__init__" not in str(loaded.value)


# --- review_lock_refusal: existing workspace ------------------------------


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


@pytest.mark.parametrize(
    ("exists", "returncode", "stderr"),
    [
        pytest.param(False, 128, "fatal: not a git repository", id="missing-workspace-outside-a-repository"),
        pytest.param(True, 128, "fatal: unable to read index", id="existing-fatal-other-than-not-a-repository"),
        pytest.param(True, 1, "error: not a git repository", id="existing-not-a-repository-text-but-wrong-exit"),
        pytest.param(True, 255, "boom", id="existing-other-failure"),
    ],
)
def test_a_git_failure_refuses_instead_of_reading_as_no_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, exists: bool, returncode: int, stderr: str) -> None:
    """Fail closed: a git failure other than "not inside a repository" is not "no committed lock"."""
    _write_lock(tmp_path, json.dumps({**_VALID, "pid": os.getpid()}))
    ref = None if exists else "main"

    def fail(cwd: Path, path: str) -> bool:
        raise GitCommandError(argv=("ls-files",), cwd=cwd, returncode=returncode, stderr=stderr)

    if exists:
        monkeypatch.setattr(lock_module, "is_tracked", fail)

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


@pytest.mark.parametrize(
    ("content", "ref", "branch", "fragment"),
    [
        pytest.param("{}", "HEAD", "kitty/lane-a", f"committed on HEAD; it must not be. Remove {LOCK_REL_PATH} there", id="start-point"),
        pytest.param("[]", "main", None, "committed on main", id="ref-when-no-branch"),
    ],
)
def test_missing_workspace_remedy_names_the_source_ref(repo: Path, tmp_path: Path, content: str, ref: str, branch: str | None, fragment: str) -> None:
    """No local lane branch: the lock comes from the ref, so the remedy names it, with no worktree command."""
    _write_lock(repo, content)
    _git(repo, "add", "-f", LOCK_REL_PATH)
    _git(repo, "commit", "-qm", "oops")

    message = review_lock_refusal(tmp_path / "lane", exists=False, repo_root=repo, checkout_ref=ref, branch=branch)

    assert message is not None
    assert fragment in message
    assert "git worktree add" not in message


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


@pytest.mark.parametrize(
    ("lock_content", "exists", "ref"),
    [
        pytest.param(None, True, None, id="existing-without-lock"),
        pytest.param(json.dumps(_VALID), True, None, id="existing-untracked-readable-lock"),
        pytest.param(None, False, "main", id="missing-without-committed-lock"),
        pytest.param(None, False, None, id="missing-without-a-ref"),
        pytest.param(None, False, "nope", id="missing-with-unknown-ref"),
        pytest.param(json.dumps(_VALID), True, _NOT_A_REPO, id="existing-outside-any-repository"),
    ],
)
def test_no_refusal_without_a_tracked_or_unreadable_lock(repo: Path, tmp_path: Path, lock_content: str | None, exists: bool, ref: str | None) -> None:
    """An ordinary lock (untracked) or none passes, and an unresolvable ref is for worktree creation to report."""
    if lock_content is not None:
        _write_lock(repo, lock_content)
    if ref == _NOT_A_REPO:
        # A workspace outside any repository cannot hold a tracked lock; the readable lock passes.
        worktree, ref = tmp_path / "plain", None
        worktree.mkdir()
        _write_lock(worktree, lock_content or "")
    else:
        worktree = repo if exists else tmp_path / "lane"

    assert review_lock_refusal(worktree, exists=exists, repo_root=repo, checkout_ref=ref, branch="main") is None


# --- remedy accuracy (pre-PR review) -----------------------------------------


@pytest.mark.parametrize(
    ("claimed", "said", "unsaid"),
    [(False, "The work package was not claimed for review.", "already recorded"), (True, "The review claim was already recorded", "not claimed")],
)
def test_claim_line_matches_whether_the_claim_was_recorded(tmp_path: Path, claimed: bool, said: str, unsaid: str) -> None:
    _write_lock(tmp_path, "{}")
    message = review_lock_refusal(tmp_path, exists=True, repo_root=tmp_path, checkout_ref=None, branch="b", claimed=claimed)
    assert message is not None
    assert said in message
    assert unsaid not in message


@pytest.mark.parametrize(
    ("detach", "expected"),
    [(False, "committed on main"), (True, "committed on the checked-out branch")],
    ids=["attached-head", "detached-head"],
)
def test_tracked_lock_without_a_branch_name_names_the_checked_out_branch(repo: Path, detach: bool, expected: str) -> None:
    """A repository root checkout resolves with no branch name; the remedy names HEAD's branch (or says so), never ``None``."""
    _write_lock(repo, "{}")
    _git(repo, "add", "-f", LOCK_REL_PATH)
    _git(repo, "commit", "-qm", "oops")
    if detach:
        _git(repo, "checkout", "-q", "--detach")

    message = review_lock_refusal(repo, exists=True, repo_root=repo, checkout_ref=None, branch=None)

    assert message is not None
    assert expected in message and "None" not in message


def test_paths_with_spaces_are_quoted(tmp_path: Path) -> None:
    worktree = tmp_path / "with space"
    lock = _write_lock(worktree, "{}")
    message = review_lock_refusal(worktree, exists=True, repo_root=worktree, checkout_ref=None, branch="b")
    assert message is not None
    assert f"rm '{lock}'" in message
