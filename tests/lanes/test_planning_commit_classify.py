"""Tests for the shared recorded-pin classifier (issue #4827, WP01).

Uses real git repos (not mocks), matching ``tests/lanes/test_git_existence.py``
and the ``test_issue_4141_refresh_planning_commit.py`` harness idiom, so the
ancestor/presence predicates are exercised against actual ``git`` behavior
rather than a simulated one.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.lanes.planning_commit_classify import (
    PinClass,
    _is_ancestor,
    _object_present,
    classify_recorded_pin,
)

pytestmark = pytest.mark.git_repo

FOREIGN_SHA = "d" * 40


def _run(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True,
    )


def _make_git_repo(path: Path) -> None:
    """Create a minimal git repo with an initial commit on ``main``."""
    subprocess.run(["git", "init", "-b", "main", str(path)], capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(path),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(path),
        capture_output=True,
        check=True,
    )
    (path / "README.md").write_text("init\n")
    subprocess.run(["git", "add", "."], cwd=str(path), capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=str(path),
        capture_output=True,
        check=True,
    )


def _commit(repo_root: Path, name: str, message: str) -> str:
    """Commit one marker file on the CURRENT branch and return its SHA."""
    (repo_root / name).write_text(f"{name}\n", encoding="utf-8")
    _run(repo_root, "add", "-A")
    _run(repo_root, "commit", "-q", "-m", message)
    return _rev_parse(repo_root, "HEAD")


def _amend_last_commit(repo_root: Path, message: str) -> str:
    """Rewrite the current HEAD commit in place and return the NEW SHA.

    This orphans the previous HEAD: the old commit object is left dangling
    (present in the object store, present in no ref's ancestry) — the shape a
    mid-mission planning rebase produces.
    """
    _run(repo_root, "commit", "--amend", "-q", "-m", message)
    return _rev_parse(repo_root, "HEAD")


def _rev_parse(repo_root: Path, ref: str) -> str:
    return _run(repo_root, "rev-parse", "--verify", ref).stdout.strip()


# ---------------------------------------------------------------------------
# classify_recorded_pin
# ---------------------------------------------------------------------------


def test_classify_advanced_when_recorded_is_ancestor_of_tip(tmp_path: Path) -> None:
    _make_git_repo(tmp_path)
    recorded_sha = _commit(tmp_path, "wp01.md", "recorded planning commit")
    tip = _commit(tmp_path, "wp02.md", "a later planning amendment")
    assert recorded_sha != tip

    assert classify_recorded_pin(tmp_path, recorded_sha, tip) == PinClass.ADVANCED


def test_classify_advanced_when_recorded_equals_tip(tmp_path: Path) -> None:
    _make_git_repo(tmp_path)
    tip = _rev_parse(tmp_path, "HEAD")

    assert classify_recorded_pin(tmp_path, tip, tip) == PinClass.ADVANCED


def test_classify_orphaned_when_recorded_present_but_rewritten_away(tmp_path: Path) -> None:
    """The rebase shape: recorded SHA still exists but is no longer reachable."""
    _make_git_repo(tmp_path)
    recorded_sha = _commit(tmp_path, "wp01.md", "recorded planning commit")
    new_tip = _amend_last_commit(tmp_path, "recorded planning commit (rebased)")
    assert new_tip != recorded_sha

    assert classify_recorded_pin(tmp_path, recorded_sha, new_tip) == PinClass.ORPHANED


def test_classify_foreign_when_recorded_object_absent(tmp_path: Path) -> None:
    _make_git_repo(tmp_path)
    tip = _rev_parse(tmp_path, "HEAD")

    assert classify_recorded_pin(tmp_path, FOREIGN_SHA, tip) == PinClass.FOREIGN


def test_classify_indeterminate_when_target_tip_is_none(tmp_path: Path) -> None:
    """Uncapturable tip (non-git / unresolvable branch) degrades, never aborts."""
    _make_git_repo(tmp_path)
    recorded_sha = _rev_parse(tmp_path, "HEAD")

    assert classify_recorded_pin(tmp_path, recorded_sha, None) == PinClass.INDETERMINATE


def test_classify_indeterminate_when_recorded_sha_is_none(tmp_path: Path) -> None:
    """No recorded pin to classify: the caller decides, the classifier does not guess."""
    _make_git_repo(tmp_path)
    tip = _rev_parse(tmp_path, "HEAD")

    assert classify_recorded_pin(tmp_path, None, tip) == PinClass.INDETERMINATE


def test_classify_indeterminate_on_non_git_repo_root_with_no_tip(tmp_path: Path) -> None:
    """A non-git workspace: the caller could never have captured a tip either."""
    assert classify_recorded_pin(tmp_path, FOREIGN_SHA, None) == PinClass.INDETERMINATE


# ---------------------------------------------------------------------------
# _object_present
# ---------------------------------------------------------------------------


def test_object_present_true_for_existing_commit(tmp_path: Path) -> None:
    _make_git_repo(tmp_path)
    sha = _rev_parse(tmp_path, "HEAD")

    assert _object_present(tmp_path, sha) is True


def test_object_present_false_for_foreign_sha(tmp_path: Path) -> None:
    _make_git_repo(tmp_path)

    assert _object_present(tmp_path, FOREIGN_SHA) is False


def test_object_present_true_for_dangling_amended_commit(tmp_path: Path) -> None:
    _make_git_repo(tmp_path)
    recorded_sha = _commit(tmp_path, "wp01.md", "recorded planning commit")
    _amend_last_commit(tmp_path, "recorded planning commit (rebased)")

    assert _object_present(tmp_path, recorded_sha) is True


def test_object_present_false_and_never_raises_for_non_git_cwd(tmp_path: Path) -> None:
    assert _object_present(tmp_path, FOREIGN_SHA) is False


def test_object_present_false_and_never_raises_for_missing_repo_root(tmp_path: Path) -> None:
    assert _object_present(tmp_path / "does-not-exist", FOREIGN_SHA) is False


# ---------------------------------------------------------------------------
# _is_ancestor
# ---------------------------------------------------------------------------


def test_is_ancestor_true_when_recorded_precedes_tip(tmp_path: Path) -> None:
    _make_git_repo(tmp_path)
    recorded_sha = _commit(tmp_path, "wp01.md", "recorded planning commit")
    tip = _commit(tmp_path, "wp02.md", "a later planning amendment")

    assert _is_ancestor(tmp_path, recorded_sha, tip) is True


def test_is_ancestor_false_when_rewritten_away(tmp_path: Path) -> None:
    _make_git_repo(tmp_path)
    recorded_sha = _commit(tmp_path, "wp01.md", "recorded planning commit")
    new_tip = _amend_last_commit(tmp_path, "recorded planning commit (rebased)")

    assert _is_ancestor(tmp_path, recorded_sha, new_tip) is False


def test_is_ancestor_false_for_foreign_sha(tmp_path: Path) -> None:
    _make_git_repo(tmp_path)
    tip = _rev_parse(tmp_path, "HEAD")

    assert _is_ancestor(tmp_path, FOREIGN_SHA, tip) is False


def test_is_ancestor_false_and_never_raises_for_non_git_cwd(tmp_path: Path) -> None:
    assert _is_ancestor(tmp_path, FOREIGN_SHA, FOREIGN_SHA) is False


def test_is_ancestor_false_and_never_raises_for_missing_repo_root(tmp_path: Path) -> None:
    assert _is_ancestor(tmp_path / "does-not-exist", FOREIGN_SHA, FOREIGN_SHA) is False
