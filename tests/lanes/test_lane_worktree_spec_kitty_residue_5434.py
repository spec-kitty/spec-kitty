"""#5434 red-first: a lane worktree's ``.spec-kitty/`` residue must not make it look dirty.

``spec-kitty review`` drops ``.spec-kitty/review-lock.json`` into the lane worktree. The next
``implement`` in the same lane re-enters ``allocate_lane_worktree`` through the REUSE route,
whose ``_validate_worktree_clean`` refuses on ANY ``git status`` entry — so the untracked
review lock trips :class:`DirtyWorktreeError` and the implementer is blocked (#5434).

The fix (research D2) writes ``.spec-kitty/`` to the repository's COMMON-dir
``info/exclude`` (shared across every worktree, the only exclude git honours for a worktree)
at the single allocation choke point. The per-worktree ``info/exclude`` git never reads is the
masked bug.

This repository's own tracked ``.gitignore`` already lists ``.spec-kitty/``, which MASKS the
defect — so this builds a consumer-like repo whose tracked ``.gitignore`` does NOT contain it.
Assertions are on real ``git status --porcelain`` output and the real ``DirtyWorktreeError``,
never on "a file was written". RED at HEAD; WP03 turns it green.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.worktree_allocator import allocate_lane_worktree

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox, pytest.mark.regression]

_SLUG = "010-consumer-feat"
_REVIEW_LOCK = Path(".spec-kitty") / "review-lock.json"
_REVIEW_LOCK_BYTES = '{"wp_id": "WP01", "locked_at": "2026-10-11T00:00:00+00:00"}\n'


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=check,
        capture_output=True,
        text=True,
    )


def _make_consumer_repo(root: Path) -> None:
    """A consumer-like repo whose TRACKED ``.gitignore`` does NOT ignore ``.spec-kitty/``."""
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    _git(root, "config", "commit.gpgsign", "false")
    # Deliberately omit ``.spec-kitty/`` — a real consumer repo does not ignore it, and this
    # repo's own ``.gitignore`` listing it is exactly what masks #5434.
    (root / ".gitignore").write_text(".worktrees/\n", encoding="utf-8")
    (root / "README.md").write_text("# consumer\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")


def _manifest() -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=_SLUG,
        mission_id=_SLUG,
        mission_branch=f"kitty/mission-{_SLUG}",
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=("WP01", "WP02"),
                write_scope=("src/**",),
                predicted_surfaces=(),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at="2026-10-11T00:00:00+00:00",
        computed_from="test",
    )


def _porcelain(worktree: Path) -> list[str]:
    out = _git(worktree, "status", "--porcelain").stdout
    return [line for line in out.splitlines() if line.strip()]


def _drop_review_lock(worktree: Path) -> None:
    lock = worktree / _REVIEW_LOCK
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(_REVIEW_LOCK_BYTES, encoding="utf-8")


def test_review_lock_residue_does_not_dirty_the_reused_lane_worktree(tmp_path: Path) -> None:
    """Core #5434: the review lock must be invisible to ``git status``, and REUSE must not refuse."""
    repo = tmp_path / "repo"
    _make_consumer_repo(repo)
    manifest = _manifest()

    wt_path, _branch = allocate_lane_worktree(repo, _SLUG, "WP01", manifest)
    assert wt_path.exists()
    assert _porcelain(wt_path) == [], "fixture sanity: a freshly-allocated lane worktree is clean"

    # What ``spec-kitty review`` leaves behind in the lane worktree.
    _drop_review_lock(wt_path)

    # RED at HEAD: ``.spec-kitty/`` is not excluded, so the lock shows as an untracked entry.
    assert _porcelain(wt_path) == [], (
        f"the lane worktree must stay clean with a .spec-kitty/ review lock present (#5434); git status --porcelain: {_porcelain(wt_path)!r}"
    )

    # RED at HEAD: the next WP in the same lane re-enters via REUSE and refuses on the lock.
    wt_again, _branch2 = allocate_lane_worktree(repo, _SLUG, "WP02", manifest)
    assert wt_again == wt_path


def test_review_lock_residue_survives_crash_recovery_reattach(tmp_path: Path) -> None:
    """#5434 crash-recovery variant: the dir was removed but the lane branch survives.

    After git re-attaches the lane worktree (``worktree_path.exists()`` was False, branch
    present), a ``.spec-kitty/`` review lock dropped into it must again be invisible to
    ``git status`` and must not refuse the next REUSE allocation.
    """
    repo = tmp_path / "repo"
    _make_consumer_repo(repo)
    manifest = _manifest()

    wt_path, branch = allocate_lane_worktree(repo, _SLUG, "WP01", manifest)
    assert wt_path.exists()

    # Crash shape: the worktree directory is gone, the lane branch survives.
    _git(repo, "worktree", "remove", "--force", str(wt_path))
    assert not wt_path.exists()
    assert _git(repo, "rev-parse", "--verify", f"refs/heads/{branch}", check=False).returncode == 0

    # Re-allocation re-attaches the worktree to its surviving branch (crash-recovery route).
    recovered, branch2 = allocate_lane_worktree(repo, _SLUG, "WP01", manifest)
    assert recovered == wt_path and branch2 == branch
    assert recovered.exists()

    _drop_review_lock(recovered)

    # RED at HEAD: the re-attached worktree has no common-dir exclude for ``.spec-kitty/``.
    assert _porcelain(recovered) == [], (
        f"the re-attached lane worktree must stay clean with a .spec-kitty/ review lock present (#5434); git status --porcelain: {_porcelain(recovered)!r}"
    )

    # RED at HEAD: a subsequent REUSE allocation must not refuse over the review lock.
    reused, _branch3 = allocate_lane_worktree(repo, _SLUG, "WP02", manifest)
    assert reused == wt_path
