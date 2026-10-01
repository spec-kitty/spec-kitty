"""FR-015 regression: move-task --to approved must not trip the guard when
the only untracked content in the lane worktree is spec-kitty's own review
lock state.

This test drives ``_validate_ready_for_review`` directly with ``target_lane``
set to ``approved`` and confirms:

1. A worktree whose only dirty path is ``.spec-kitty/review-lock.json``
   PASSES validation without ``--force`` (happy path).
2. A worktree with genuine source-code drift STILL FAILS validation, proving
   that the deny-list is scoped and does not mask real uncommitted work.
3. When genuine drift blocks, the retry hint names ``approved`` (the caller's
   target lane), not a hard-coded ``for_review``.

It also covers the ``ReviewLock.release()`` cleanup contract: after a
successful release the parent ``.spec-kitty/`` directory is removed when it
is empty.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from kernel.git import GitPath, StatusEntry
from specify_cli.cli.commands.agent.tasks import (
    _RUNTIME_STATE_DENY_LIST,
    _filter_runtime_state_paths,
    _validate_ready_for_review,
)
from specify_cli.review.lock import LOCK_DIR, LOCK_FILE, ReviewLock
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event
from tests.lane_test_utils import lane_branch_name, lane_worktree_path, write_single_lane_manifest

pytestmark = pytest.mark.git_repo


# ---------------------------------------------------------------------------
# Fixture: lane worktree + committed implementation + no other dirty state
# ---------------------------------------------------------------------------


@pytest.fixture
def lane_worktree_repo(tmp_path: Path) -> tuple[Path, Path, str]:
    """Stand up a git repo with a single-lane mission and a clean worktree.

    Returns (main_repo_root, worktree_path, mission_slug).
    """
    repo = tmp_path / "repo"
    repo.mkdir()

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True, capture_output=True)

    (repo / ".kittify").mkdir()
    (repo / ".kittify" / "config.yaml").write_text("# config\n")

    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo, check=True, capture_output=True)

    mission_slug = "wp06-approve-guard"
    feature_dir = repo / "kitty-specs" / mission_slug
    (feature_dir / "tasks").mkdir(parents=True)
    write_single_lane_manifest(feature_dir, wp_ids=("WP01",))

    (feature_dir / "tasks" / "WP01-feature.md").write_text(
        "---\nwork_package_id: WP01\ntitle: Feature\nagent: test\nshell_pid: ''\n---\n\n"
        "# WP01\n\n## Activity Log\n\n- 2025-01-01T00:00:00Z – system – lane=planned\n",
        encoding="utf-8",
    )

    for lane_val in ("planned", "in_progress", "for_review"):
        append_event(
            feature_dir,
            StatusEvent(
                event_id=f"seed-WP01-{lane_val}",
                mission_slug=mission_slug,
                wp_id="WP01",
                from_lane=Lane.PLANNED,
                to_lane=Lane(lane_val),
                at="2025-01-01T00:00:00+00:00",
                actor="test-fixture",
                force=True,
                execution_mode="worktree",
            ),
        )

    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Seed mission"], cwd=repo, check=True, capture_output=True)

    worktree = lane_worktree_path(repo, mission_slug)
    subprocess.run(
        ["git", "worktree", "add", "-b", lane_branch_name(mission_slug), str(worktree), "main"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    (worktree / "feature.py").write_text("# implementation\n")
    subprocess.run(["git", "add", "."], cwd=worktree, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat(WP01): implement"], cwd=worktree, check=True, capture_output=True)

    return repo, worktree, mission_slug


# ---------------------------------------------------------------------------
# Deny-list unit checks
# ---------------------------------------------------------------------------


def test_deny_list_is_fixed_named_tuple() -> None:
    """C-003: deny list must be a fixed named tuple, not a pattern/regex."""
    assert isinstance(_RUNTIME_STATE_DENY_LIST, tuple)
    assert ".spec-kitty/" in _RUNTIME_STATE_DENY_LIST
    assert ".kittify/" in _RUNTIME_STATE_DENY_LIST
    # C-003: no glob/regex-flavoured entries
    for entry in _RUNTIME_STATE_DENY_LIST:
        assert "*" not in entry
        assert "?" not in entry


def test_filter_strips_review_lock_line() -> None:
    entries = (
        StatusEntry(xy="??", path=GitPath.parse(".spec-kitty/review-lock.json")),
        StatusEntry(xy=" M", path=GitPath.parse("src/feature.py")),
    )
    filtered = [str(entry.path) for entry in _filter_runtime_state_paths(entries)]
    assert filtered == ["src/feature.py"]


def test_filter_preserves_non_denylisted_paths() -> None:
    entries = (
        StatusEntry(xy="??", path=GitPath.parse("src/feature.py")),
        StatusEntry(xy=" M", path=GitPath.parse("docs/note.md")),
    )
    filtered = [str(entry.path) for entry in _filter_runtime_state_paths(entries)]
    assert filtered == ["src/feature.py", "docs/note.md"]


# ---------------------------------------------------------------------------
# FR-015 happy path: approve without --force when only .spec-kitty/ is dirty
# ---------------------------------------------------------------------------


@patch("specify_cli.cli.commands.agent.tasks.get_mission_type", return_value="software-dev")
def test_approve_passes_without_force_when_only_spec_kitty_dirty(
    _mock_mission: Mock,
    lane_worktree_repo: tuple[Path, Path, str],
) -> None:
    repo, worktree, mission_slug = lane_worktree_repo

    # Simulate the review lock acquired during review.
    ReviewLock.acquire(worktree, wp_id="WP01", agent="reviewer")
    assert (worktree / LOCK_DIR / LOCK_FILE).exists()

    is_valid, guidance = _validate_ready_for_review(
        repo_root=worktree,
        mission_slug=mission_slug,
        wp_id="WP01",
        force=False,
        target_lane="approved",
    )
    assert is_valid is True, f"Guidance unexpectedly blocked approve: {guidance}"
    assert guidance == []


# ---------------------------------------------------------------------------
# FR-018 post-transition state: .spec-kitty/ removed after release
# ---------------------------------------------------------------------------


def test_release_removes_empty_spec_kitty_directory(
    lane_worktree_repo: tuple[Path, Path, str],
) -> None:
    _, worktree, _ = lane_worktree_repo

    ReviewLock.acquire(worktree, wp_id="WP01", agent="reviewer")
    assert (worktree / LOCK_DIR).is_dir()

    ReviewLock.release(worktree)

    assert not (worktree / LOCK_DIR / LOCK_FILE).exists()
    assert not (worktree / LOCK_DIR).exists(), ".spec-kitty/ should be cleaned up when empty"


def test_release_is_idempotent(lane_worktree_repo: tuple[Path, Path, str]) -> None:
    _, worktree, _ = lane_worktree_repo

    # Called before any acquire — must not raise.
    ReviewLock.release(worktree)
    # Acquire then release twice — the second call must be a no-op.
    ReviewLock.acquire(worktree, wp_id="WP01", agent="reviewer")
    ReviewLock.release(worktree)
    ReviewLock.release(worktree)

    assert not (worktree / LOCK_DIR).exists()


def test_release_preserves_directory_with_other_content(
    lane_worktree_repo: tuple[Path, Path, str],
) -> None:
    _, worktree, _ = lane_worktree_repo
    ReviewLock.acquire(worktree, wp_id="WP01", agent="reviewer")

    # Some other tooling drops a sibling file under .spec-kitty/
    other = worktree / LOCK_DIR / "other.json"
    other.write_text("{}")

    ReviewLock.release(worktree)

    assert not (worktree / LOCK_DIR / LOCK_FILE).exists()
    assert (worktree / LOCK_DIR).is_dir(), "Non-empty .spec-kitty/ must be preserved"
    assert other.exists()


# ---------------------------------------------------------------------------
# C-004: genuine drift still blocks approve, and retry text uses target_lane
# ---------------------------------------------------------------------------


@patch("specify_cli.cli.commands.agent.tasks.get_mission_type", return_value="software-dev")
def test_genuine_drift_still_blocks_approve_and_retry_says_approved(
    _mock_mission: Mock,
    lane_worktree_repo: tuple[Path, Path, str],
) -> None:
    repo, worktree, mission_slug = lane_worktree_repo

    # Acquire the review lock AND add genuine uncommitted source code.
    ReviewLock.acquire(worktree, wp_id="WP01", agent="reviewer")
    (worktree / "uncommitted.py").write_text("# genuine drift\n")

    is_valid, guidance = _validate_ready_for_review(
        repo_root=worktree,
        mission_slug=mission_slug,
        wp_id="WP01",
        force=False,
        target_lane="approved",
    )

    assert is_valid is False, "Genuine uncommitted source code must still block (C-004)"
    joined = "\n".join(guidance)
    assert "uncommitted.py" in joined, f"Real drift file must be named in guidance:\n{joined}"
    assert ".spec-kitty/" not in joined, "Runtime-state paths must be filtered out of guidance"
    # FR-015 retry text parameterized on target_lane
    assert "--to approved" in joined
    assert "--to for_review" not in joined
