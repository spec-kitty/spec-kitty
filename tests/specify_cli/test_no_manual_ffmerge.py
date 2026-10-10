"""End-to-end test: zero manual ff-merges after coordination-branch writes.

WP09 / FR-010 / Issue #1878 — ff-merge treadmill elimination.

After ``advance_branch_ref`` is called as the post-write primary-ref sync,
the primary branch must be up-to-date with the coordination branch without
the operator running ``git merge --ff-only`` by hand.

These tests assert the invariant at the unit level:
  * ``advance_branch_ref`` with ``context`` (WP13 retired the former
    ``coord_owned_filenames`` frozenset param onto the canonical churn owner)
    does NOT abort when coord-owned residue (``status.events.jsonl``,
    ``status.json``) is present in a checked-out worktree.
  * After a write to the coord branch followed by ``advance_branch_ref``, the
    primary branch is at the same SHA — ``git log main..coord`` is empty.
  * No ``git merge --ff-only`` call appears anywhere in the test helpers (the
    test itself is the proof that no manual step is needed).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.residue_predicate import residue_when
from specify_cli.coordination.coherence import is_toolchain_generated_churn
from specify_cli.git.ref_advance import (
    advance_branch_ref,
    RefAdvanceDirtyWorktreeError,
    RefAdvanceNonFastForwardError,
    RefRestoreError,
    restore_branch_ref,
)

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=check,
    )


def _sha(repo: Path, ref: str = "HEAD") -> str:
    return _git(repo, "rev-parse", ref).stdout.strip()


def _init_repo(
    tmp_path: Path,
    primary_branch: str = "main",
    coord_branch: str = "kitty/mission-myslug-01ABCDEF",
) -> tuple[Path, Path]:
    """Set up a repo with a primary branch and a coordination branch.

    Returns ``(repo_root, coord_worktree_path)``.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", primary_branch)
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")

    # Initial commit on primary branch
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "initial commit")

    # Create coord branch from same point
    _git(repo, "branch", coord_branch)

    # Add a coord worktree checked out to the coord branch
    coord_wt = tmp_path / "coord-worktree"
    _git(repo, "worktree", "add", str(coord_wt), coord_branch)

    return repo, coord_wt


# ---------------------------------------------------------------------------
# T044a — after a coord write + advance_branch_ref, primary is up-to-date
# ---------------------------------------------------------------------------


def test_primary_ref_up_to_date_after_coord_write(tmp_path: Path) -> None:
    """Primary branch tracks coord HEAD after advance_branch_ref — no manual ff-merge needed."""
    primary_branch = "main"
    coord_branch = "kitty/mission-myslug-01ABCDEF"
    repo, coord_wt = _init_repo(tmp_path, primary_branch, coord_branch)

    # Write an artifact to the coord branch (simulates planning commit)
    artifact = coord_wt / "spec.md"
    artifact.write_text("# Spec\n", encoding="utf-8")
    _git(coord_wt, "add", "spec.md")
    _git(coord_wt, "commit", "-q", "-m", "Add spec")

    coord_sha = _sha(coord_wt)

    # Primary branch is now behind — confirm it
    behind = _git(
        repo,
        "log",
        "--oneline",
        f"{primary_branch}..{coord_branch}",
    ).stdout.strip()
    assert behind, "Primary should be behind coord before advance"

    # Advance the primary ref — this is what WP09 wires up automatically
    advance_branch_ref(repo, primary_branch, coord_sha)

    # Primary is now at coord HEAD — no manual ff-merge needed
    primary_sha = _sha(repo, primary_branch)
    assert primary_sha == coord_sha, f"Primary branch should be at coord HEAD after advance_branch_ref; primary={primary_sha[:12]} coord={coord_sha[:12]}"

    # Confirm git log shows empty gap (primary up-to-date with coord)
    gap = _git(
        repo,
        "log",
        "--oneline",
        f"{primary_branch}..{coord_branch}",
    ).stdout.strip()
    assert gap == "", f"git log {primary_branch}..{coord_branch} should be empty after advance; got: {gap!r}"


def test_restore_branch_ref_refuses_to_clobber_concurrent_advance(tmp_path: Path) -> None:
    """Rollback CAS leaves a branch alone after another writer advances it."""
    coord_branch = "kitty/mission-myslug-01ABCDEF"
    repo, coord_wt = _init_repo(tmp_path, coord_branch=coord_branch)
    restored_sha = _sha(repo, "main")

    (coord_wt / "first.txt").write_text("first\n", encoding="utf-8")
    _git(coord_wt, "add", "first.txt")
    _git(coord_wt, "commit", "-q", "-m", "first advance")
    expected_current_sha = _sha(coord_wt)

    (coord_wt / "concurrent.txt").write_text("concurrent\n", encoding="utf-8")
    _git(coord_wt, "add", "concurrent.txt")
    _git(coord_wt, "commit", "-q", "-m", "concurrent advance")
    concurrent_sha = _sha(coord_wt)

    with pytest.raises(RefRestoreError):
        restore_branch_ref(
            repo,
            coord_branch,
            restored_sha,
            expected_current_sha=expected_current_sha,
        )

    assert _sha(repo, coord_branch) == concurrent_sha


# ---------------------------------------------------------------------------
# T044b — coord-owned residue does NOT abort advance_branch_ref (T041)
# ---------------------------------------------------------------------------


def test_coord_owned_residue_does_not_abort_advance(tmp_path: Path) -> None:
    """Coord-owned status files on the primary checkout are excluded from the dirty check."""
    primary_branch = "main"
    coord_branch = "kitty/mission-myslug-01ABCDEF"
    repo, coord_wt = _init_repo(tmp_path, primary_branch, coord_branch)

    # Write a real artifact to the coord branch
    artifact = coord_wt / "plan.md"
    artifact.write_text("# Plan\n", encoding="utf-8")
    _git(coord_wt, "add", "plan.md")
    _git(coord_wt, "commit", "-q", "-m", "Add plan")
    coord_sha = _sha(coord_wt)

    # Simulate coord-owned residue present in the MAIN checkout's working tree,
    # at the CANONICAL location directly under the mission dir (not nested
    # under a WP subdirectory -- that is not where the status log/snapshot
    # actually live; a nested placement would not classify as STATUS_STATE).
    # These files are legitimately present after a status event write on the
    # primary checkout — they must not cause RefAdvanceDirtyWorktreeError.
    mission_dir = repo / "kitty-specs" / "my-mission"
    mission_dir.mkdir(parents=True, exist_ok=True)
    for filename in ("status.events.jsonl", "status.json"):
        (mission_dir / filename).write_text('{"event": "dummy"}\n', encoding="utf-8")

    # advance_branch_ref WITH a residue context must succeed despite residue
    advance_branch_ref(
        repo,
        primary_branch,
        coord_sha,
        context=residue_when(is_toolchain_generated_churn),
    )

    primary_sha = _sha(repo, primary_branch)
    assert primary_sha == coord_sha, "Primary should be at coord HEAD even when coord-owned residue is present"


def test_tracked_coord_owned_status_change_no_longer_blocks_advance(tmp_path: Path) -> None:
    """WP13 (IC-07c) / #2795 / FR-012: a tracked, locally-edited status snapshot
    is now ALSO toolchain-generated churn, agreeing with every other
    churn-classifying gate (``merge/git_probes.py``,
    ``review/dirty_classifier.py``) -- closing the cross-gate disagreement
    :mod:`tests.architectural.test_cross_gate_churn_agreement` pins (C7).

    Superseded predecessor: this test used to be
    ``test_tracked_coord_owned_status_change_still_blocks_advance``, asserting
    the OPPOSITE (a tracked status-file edit blocks the advance) under the
    narrower, pre-WP13 ``coord_owned_filenames`` mechanism, which only ever
    excluded UNTRACKED entries. WP13 routes ``_dirty_entries`` through
    ``context`` for BOTH tracked and untracked entries, so this scenario now
    exempts rather than blocks -- matching ``merge/git_probes.py`` /
    ``review/dirty_classifier.py``, which already treated a tracked-modified
    status/matrix file as benign churn before this WP.
    """
    primary_branch = "main"
    coord_branch = "kitty/mission-myslug-01ABCDEF"
    repo, coord_wt = _init_repo(tmp_path, primary_branch, coord_branch)

    status_file = repo / "kitty-specs" / "my-mission" / "status.json"
    status_file.parent.mkdir(parents=True)
    status_file.write_text('{"lane": "planned"}\n', encoding="utf-8")
    _git(repo, "add", "kitty-specs/my-mission/status.json")
    _git(repo, "commit", "-q", "-m", "Seed status snapshot")

    _git(coord_wt, "reset", "--hard", primary_branch)
    artifact = coord_wt / "plan.md"
    artifact.write_text("# Plan\n", encoding="utf-8")
    _git(coord_wt, "add", "plan.md")
    _git(coord_wt, "commit", "-q", "-m", "Add plan")
    coord_sha = _sha(coord_wt)

    status_file.write_text('{"lane": "locally-edited"}\n', encoding="utf-8")

    advance_branch_ref(
        repo,
        primary_branch,
        coord_sha,
        context=residue_when(is_toolchain_generated_churn),
    )

    assert _sha(repo, primary_branch) == coord_sha, "a tracked, locally-edited status.json is toolchain churn post-WP13; the advance must succeed, not refuse."


def test_diverged_primary_ref_is_not_rewound(tmp_path: Path) -> None:
    """Clean divergence still refuses: auto-advance must never rewind primary."""
    primary_branch = "main"
    coord_branch = "kitty/mission-myslug-01ABCDEF"
    repo, coord_wt = _init_repo(tmp_path, primary_branch, coord_branch)

    primary_only = repo / "primary-only.txt"
    primary_only.write_text("primary\n", encoding="utf-8")
    _git(repo, "add", "primary-only.txt")
    _git(repo, "commit", "-q", "-m", "Primary-only commit")
    primary_sha = _sha(repo, primary_branch)

    coord_only = coord_wt / "coord-only.txt"
    coord_only.write_text("coord\n", encoding="utf-8")
    _git(coord_wt, "add", "coord-only.txt")
    _git(coord_wt, "commit", "-q", "-m", "Coord-only commit")
    coord_sha = _sha(coord_wt)

    with pytest.raises(RefAdvanceNonFastForwardError):
        advance_branch_ref(repo, primary_branch, coord_sha)

    assert _sha(repo, primary_branch) == primary_sha


# ---------------------------------------------------------------------------
# T044c — dirty (non-residue) tracked changes still block advance (NFR-002)
# ---------------------------------------------------------------------------


def test_genuine_dirty_tracked_changes_still_block_advance(tmp_path: Path) -> None:
    """Non-residue uncommitted tracked changes in the main checkout must still abort.

    ``advance_branch_ref`` uses ``git worktree list --porcelain`` to find all
    worktrees that have the primary branch checked out.  The main repo itself
    is registered as the first worktree entry, so dirty tracked changes there
    are detected without needing an additional worktree add.
    """
    primary_branch = "main"
    coord_branch = "kitty/mission-myslug-01ABCDEF"
    repo, coord_wt = _init_repo(tmp_path, primary_branch, coord_branch)

    # Write artifact to coord
    artifact = coord_wt / "tasks.md"
    artifact.write_text("# Tasks\n", encoding="utf-8")
    _git(coord_wt, "add", "tasks.md")
    _git(coord_wt, "commit", "-q", "-m", "Add tasks")
    coord_sha = _sha(coord_wt)

    # Create a staged tracked change in the MAIN checkout (not a residue file).
    # The main repo is the first worktree listed by `git worktree list`, so
    # the dirty check fires against it before the ref moves.
    dirty = repo / "README.md"
    dirty.write_text("MODIFIED\n", encoding="utf-8")
    _git(repo, "add", "README.md")

    # advance_branch_ref must refuse (NFR-002: no silent data discard)
    with pytest.raises(RefAdvanceDirtyWorktreeError):
        advance_branch_ref(
            repo,
            primary_branch,
            coord_sha,
            context=residue_when(is_toolchain_generated_churn),
        )


# ---------------------------------------------------------------------------
# T044d — idempotency: calling advance_branch_ref twice is a no-op
# ---------------------------------------------------------------------------


def test_advance_branch_ref_is_idempotent(tmp_path: Path) -> None:
    """Calling advance_branch_ref twice on the same SHA leaves things stable."""
    primary_branch = "main"
    coord_branch = "kitty/mission-myslug-01ABCDEF"
    repo, coord_wt = _init_repo(tmp_path, primary_branch, coord_branch)

    artifact = coord_wt / "meta.json"
    artifact.write_text('{"mission_id": "01ABCDEF"}\n', encoding="utf-8")
    _git(coord_wt, "add", "meta.json")
    _git(coord_wt, "commit", "-q", "-m", "Add meta")
    coord_sha = _sha(coord_wt)

    # First advance
    advance_branch_ref(repo, primary_branch, coord_sha)
    sha_after_first = _sha(repo, primary_branch)
    assert sha_after_first == coord_sha

    # Second advance (same SHA) — must be a no-op, no exception
    advance_branch_ref(repo, primary_branch, coord_sha)
    sha_after_second = _sha(repo, primary_branch)
    assert sha_after_second == coord_sha, "Second advance must be idempotent"
