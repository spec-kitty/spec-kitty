"""Behind-own-HEAD resume remedy classifier (WP05 / FR-011, traces #4982 #4997).

After an interrupted terminus the ``update-ref`` that advanced the target and the
``reset --hard`` that refreshes the checkout are two *unlinked* steps (DEBRIEF
§2 R1). When the second step never runs, the primary checkout is merely **behind
its own HEAD**: the lane's already-merged files read as staged deletions /
"local changes". The pre-fix resume dirty-preflight advised "Commit …", which
stages those deletions into a new commit that *reverts the integrated merge* —
resume then skips the lane as integrated and ``main`` lands without the WP's
code while every WP is marked done and the command exits 0.

These tests build **real** git repositories (no ``_run_git`` mocking — the
ancestry probe must run for real, mirroring WP01's discipline) and assert the
classifier in :mod:`specify_cli.merge.preflight`:

* distinguishes behind-own-HEAD from genuine local changes via the ancestry
  probe, NOT a file-name heuristic;
* never advises the merge-reverting "Commit" remedy in the behind-HEAD case;
* still emits the normal commit/stash/revert remedy for a genuinely dirty tree;
* surfaces a blocked state (never a silent pass) when an ``index.lock`` shows a
  ``reset --hard`` was interrupted mid-transaction.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.merge.preflight import (
    ResumeRemedyKind,
    classify_resume_dirty_remedy,
)

# Real ``git`` runs against a tmp repo, so this is an integration test that
# requires a git repo (Rule 1) and must NOT carry ``fast`` (Rule 2 — subprocess
# work would poison the inner-loop profile). ``non_sandbox`` mirrors the sibling
# subprocess-backed merge tests (trampoline bug: subprocess).
pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox]


def _git(repo: Path, *args: str) -> str:
    """Run ``git`` in *repo*, returning stripped stdout (raises on failure)."""
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / "alpha.txt").write_text("alpha\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "C0 base")
    return repo


def _make_behind_own_head_repo(tmp_path: Path) -> tuple[Path, str]:
    """Return ``(repo, lane_branch)`` for a checkout left behind its own HEAD.

    Models the interrupted terminus: the lane is merged onto ``main`` by
    advancing the ref (``git update-ref``), but the ``reset --hard`` that would
    refresh the working checkout never runs — so the lane's file reads as a
    staged deletion even though HEAD already carries it.
    """
    repo = _init_repo(tmp_path)
    # Lane work: add beta.txt on a lane branch cut from C0.
    _git(repo, "checkout", "-b", "lane-x")
    (repo / "beta.txt").write_text("beta\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "C1 lane work")
    lane_sha = _git(repo, "rev-parse", "lane-x")
    # Back to main with the pre-merge tree still checked out (no beta.txt on
    # disk, index still at C0).
    _git(repo, "checkout", "main")
    # Advance the target ref to the lane tip WITHOUT resetting the checkout —
    # the interrupted-terminus state (update-ref ran, reset --hard did not).
    _git(repo, "update-ref", "refs/heads/main", lane_sha)
    return repo, "lane-x"


def _make_genuinely_dirty_repo(tmp_path: Path) -> tuple[Path, str]:
    """Return ``(repo, lane_branch)`` for a real uncommitted edit, merge NOT landed.

    The lane exists but has NOT been integrated into HEAD, and the working tree
    carries a genuine uncommitted edit to a tracked file unrelated to the lane.
    """
    repo = _init_repo(tmp_path)
    _git(repo, "checkout", "-b", "lane-x")
    (repo / "beta.txt").write_text("beta\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "C1 lane work (unintegrated)")
    _git(repo, "checkout", "main")
    # A genuine, uncommitted local modification to a tracked file.
    (repo / "alpha.txt").write_text("alpha edited locally\n", encoding="utf-8")
    return repo, "lane-x"


# --- behind-own-HEAD -------------------------------------------------------


def test_behind_own_head_classified_via_ancestry_not_local_changes(
    tmp_path: Path,
) -> None:
    repo, lane_branch = _make_behind_own_head_repo(tmp_path)

    # Sanity: the state really is dirty (staged deletion of the merged file).
    porcelain = _git(repo, "status", "--porcelain")
    assert "beta.txt" in porcelain

    remedy = classify_resume_dirty_remedy(repo, lane_branch=lane_branch)

    assert remedy.kind is ResumeRemedyKind.BEHIND_OWN_HEAD
    assert remedy.kind is not ResumeRemedyKind.LOCAL_CHANGES


def test_behind_own_head_remedy_never_advises_commit(tmp_path: Path) -> None:
    repo, lane_branch = _make_behind_own_head_repo(tmp_path)

    remedy = classify_resume_dirty_remedy(repo, lane_branch=lane_branch)

    # The merge-reverting trap: committing the staged deletions reverts the
    # already-integrated lane. The behind-HEAD remedy must NEVER advise it.
    assert not any("commit" in line.lower() for line in remedy.remediation)
    # It must advise the safe fast-forward / reset-to-HEAD recovery instead.
    joined = "\n".join(remedy.remediation).lower()
    assert "reset --hard head" in joined


# --- contrast: genuine local changes (no over-classification) --------------


def test_genuinely_dirty_tree_still_gets_normal_commit_remedy(
    tmp_path: Path,
) -> None:
    repo, lane_branch = _make_genuinely_dirty_repo(tmp_path)

    remedy = classify_resume_dirty_remedy(repo, lane_branch=lane_branch)

    assert remedy.kind is ResumeRemedyKind.LOCAL_CHANGES
    joined = "\n".join(remedy.remediation).lower()
    # The normal remedy legitimately offers commit/stash/revert here — nothing
    # is being reverted because the lane never landed in HEAD.
    assert "commit" in joined or "stash" in joined


def test_behind_head_and_dirty_remedies_differ(tmp_path: Path) -> None:
    behind_repo, behind_lane = _make_behind_own_head_repo(tmp_path / "behind")
    dirty_repo, dirty_lane = _make_genuinely_dirty_repo(tmp_path / "dirty")

    behind = classify_resume_dirty_remedy(behind_repo, lane_branch=behind_lane)
    dirty = classify_resume_dirty_remedy(dirty_repo, lane_branch=dirty_lane)

    assert behind.kind is not dirty.kind
    assert behind.remediation != dirty.remediation


# --- edge: index.lock (reset --hard blocked mid-transaction) ---------------


def test_index_lock_surfaces_blocked_state_not_silent_pass(
    tmp_path: Path,
) -> None:
    repo, lane_branch = _make_behind_own_head_repo(tmp_path)
    # A ``reset --hard`` that was blocked mid-transaction leaves index.lock.
    git_dir = Path(_git(repo, "rev-parse", "--absolute-git-dir"))
    (git_dir / "index.lock").write_text("", encoding="utf-8")

    remedy = classify_resume_dirty_remedy(repo, lane_branch=lane_branch)

    assert remedy.kind is ResumeRemedyKind.BLOCKED_INDEX_LOCK
    joined = "\n".join(remedy.remediation).lower()
    assert "index.lock" in joined
    # Never a silent pass, and never the merge-reverting commit advice.
    assert remedy.remediation
    assert not any("git commit" in line.lower() for line in remedy.remediation)
