"""Regression tests for worktree-aware status read resolution (#984).

FR-013: get_status_read_root() returns the current worktree root when called
        from inside a worktree.
FR-014: get_status_read_root() returns the main repo root when called from the
        main checkout.
FR-015: read-only status commands (agent tasks status) read events from the
        current worktree, not from the primary checkout.

Bug reproduction:
    Create a worktree with divergent status.events.jsonl from the main checkout.
    Run `spec-kitty agent tasks status --json` from the worktree.
    Without the fix: command reads main checkout's events → false result.
    With the fix: command reads the worktree's own events → correct result.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.core.paths import get_status_read_root


pytestmark = pytest.mark.git_repo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _init_git_repo(path: Path) -> None:
    """Initialise a minimal git repository at *path* with an initial commit."""
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@test.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Test"], check=True, capture_output=True)
    # Need at least one commit so worktree add works
    readme = path / "README.md"
    readme.write_text("# Test\n")
    subprocess.run(["git", "-C", str(path), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "commit", "-m", "init"], check=True, capture_output=True)


def _add_worktree(main_path: Path, worktree_path: Path, branch: str) -> None:
    """Add a git worktree at *worktree_path* on a new *branch*."""
    subprocess.run(
        ["git", "-C", str(main_path), "worktree", "add", "-b", branch, str(worktree_path)],
        check=True,
        capture_output=True,
    )


def _write_events(feature_dir: Path, events_json: list[dict]) -> None:
    """Write a status.events.jsonl file in *feature_dir*."""
    feature_dir.mkdir(parents=True, exist_ok=True)
    events_file = feature_dir / "status.events.jsonl"
    events_file.write_text(
        "\n".join(json.dumps(e, sort_keys=True) for e in events_json) + "\n"
    )


def _make_event(wp_id: str, to_lane: str, mission_slug: str = "test-mission") -> dict:
    """Build a minimal status event dict for testing."""
    return {
        "actor": "claude",
        "at": "2026-05-12T10:00:00+00:00",
        "event_id": f"01TEST{wp_id}{to_lane[:3].upper()}",
        "evidence": None,
        "execution_mode": "worktree",
        "feature_slug": mission_slug,
        "force": False,
        "from_lane": "planned",
        "reason": None,
        "review_ref": None,
        "to_lane": to_lane,
        "wp_id": wp_id,
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def two_worktree_setup(tmp_path: Path) -> dict:
    """Create a main repo and one linked worktree with divergent event logs.

    Layout:
        tmp_path/
          main/           ← main git checkout
            .kittify/     ← marks this as a spec-kitty project root
            kitty-specs/
              test-mission/
                status.events.jsonl  ← contains WP01 → done (main's view)
          worktree/       ← linked git worktree (branch: kitty/test-lane-a)
            kitty-specs/
              test-mission/
                status.events.jsonl  ← contains WP01 → in_progress (wt's view)
    """
    main = tmp_path / "main"
    main.mkdir()
    _init_git_repo(main)

    # Add .kittify/ so locate_project_root() recognises this as a project root
    (main / ".kittify").mkdir()

    worktree = tmp_path / "worktree"
    _add_worktree(main, worktree, "kitty/test-lane-a")

    # Write divergent event logs
    mission_slug = "test-mission"
    main_feature_dir = main / "kitty-specs" / mission_slug
    wt_feature_dir = worktree / "kitty-specs" / mission_slug

    main_events = [_make_event("WP01", "done", mission_slug)]
    wt_events = [_make_event("WP01", "in_progress", mission_slug)]

    _write_events(main_feature_dir, main_events)
    _write_events(wt_feature_dir, wt_events)

    # Commit the events in the main repo so the worktree can see them via git
    subprocess.run(
        ["git", "-C", str(main), "add", "-A"],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(main), "commit", "-m", "add test mission events"],
        check=True, capture_output=True,
    )

    return {
        "main": main,
        "worktree": worktree,
        "mission_slug": mission_slug,
        "main_feature_dir": main_feature_dir,
        "wt_feature_dir": wt_feature_dir,
        "main_events": main_events,
        "wt_events": wt_events,
    }


# ---------------------------------------------------------------------------
# T028: get_status_read_root() unit tests
# ---------------------------------------------------------------------------

class TestGetStatusReadRoot:
    """Unit tests for the get_status_read_root() helper (FR-013, FR-014)."""

    def test_main_repo_returns_main_root(self, two_worktree_setup: dict) -> None:
        """From the main checkout, get_status_read_root() returns the main root."""
        main: Path = two_worktree_setup["main"]
        result = get_status_read_root(main)
        assert result == main.resolve()

    def test_worktree_returns_worktree_root(self, two_worktree_setup: dict) -> None:
        """From a linked worktree, get_status_read_root() returns the *worktree* root.

        This is the core of FR-013: the resolver must NOT follow the .git file
        back to the main repo when resolving a read-only path from a worktree.
        """
        worktree: Path = two_worktree_setup["worktree"]
        result = get_status_read_root(worktree)
        assert result == worktree.resolve()

    def test_worktree_root_differs_from_main_root(self, two_worktree_setup: dict) -> None:
        """Worktree root must differ from main root (not collapsed to main)."""
        main: Path = two_worktree_setup["main"]
        worktree: Path = two_worktree_setup["worktree"]
        main_result = get_status_read_root(main)
        wt_result = get_status_read_root(worktree)
        assert main_result != wt_result

    def test_subdirectory_of_worktree_returns_worktree_root(self, two_worktree_setup: dict) -> None:
        """Starting from a subdirectory inside the worktree also returns the worktree root."""
        worktree: Path = two_worktree_setup["worktree"]
        subdir = worktree / "src" / "some" / "package"
        subdir.mkdir(parents=True, exist_ok=True)
        result = get_status_read_root(subdir)
        assert result == worktree.resolve()

    def test_non_git_directory_falls_back_gracefully(self, tmp_path: Path) -> None:
        """Outside any git repo, get_status_read_root() falls back without crashing."""
        plain_dir = tmp_path / "plain"
        plain_dir.mkdir()
        # get_main_repo_root falls back to returning the resolved cwd,
        # so we just verify no exception is raised.
        try:
            result = get_status_read_root(plain_dir)
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"get_status_read_root() raised unexpectedly: {exc}")
        # Result is a Path — may be the fallback cwd
        assert isinstance(result, Path)


# ---------------------------------------------------------------------------
# T031: Regression — divergent event logs per worktree
# ---------------------------------------------------------------------------

class TestWorktreeEventLogIsolation:
    """Regression tests for #984: status reads must be worktree-local.

    These tests verify that get_status_read_root() produces a different path
    from the main repo when called from a linked worktree, and that reading
    events through that path returns the worktree-local events (not the main
    checkout's).
    """

    def test_status_read_from_main_repo_reads_main_events(
        self, two_worktree_setup: dict
    ) -> None:
        """get_status_read_root() from main → events from main's feature dir."""
        from specify_cli.status.store import read_events

        main: Path = two_worktree_setup["main"]
        mission_slug: str = two_worktree_setup["mission_slug"]
        expected_lane = "done"  # main's WP01 event has to_lane=done

        read_root = get_status_read_root(main)
        feature_dir = read_root / "kitty-specs" / mission_slug
        events = read_events(feature_dir)

        assert len(events) == 1, f"Expected 1 event from main, got: {events}"
        assert events[0].to_lane.value == expected_lane, (
            f"Main repo event should have to_lane='{expected_lane}', "
            f"got: {events[0].to_lane}"
        )

    def test_status_read_from_worktree_reads_worktree_events(
        self, two_worktree_setup: dict
    ) -> None:
        """get_status_read_root() from worktree → events from worktree's feature dir.

        This is the core regression test for #984: when running from a detached
        worktree, status reads must return THE WORKTREE'S events, not the main
        checkout's potentially-divergent state.

        To reproduce the bug, revert the routing change so get_status_read_root()
        becomes get_main_repo_root() — this test will fail, confirming the test
        exercises the actual fix.
        """
        from specify_cli.status.store import read_events

        worktree: Path = two_worktree_setup["worktree"]
        mission_slug: str = two_worktree_setup["mission_slug"]
        expected_lane = "in_progress"  # worktree's WP01 event has to_lane=in_progress

        # This is the fix: get_status_read_root returns the worktree root, not main.
        read_root = get_status_read_root(worktree)
        assert read_root == worktree.resolve(), (
            f"Expected read root to be the worktree ({worktree.resolve()}), "
            f"got {read_root}. This would indicate the fix has been reverted."
        )

        feature_dir = read_root / "kitty-specs" / mission_slug
        events = read_events(feature_dir)

        assert len(events) == 1, f"Expected 1 event from worktree, got: {events}"
        assert events[0].to_lane.value == expected_lane, (
            f"Worktree event should have to_lane='{expected_lane}', "
            f"got: {events[0].to_lane}. "
            f"If this is 'done', the fix has been reverted and #984 is back."
        )

    def test_regression_guard_revert_would_fail(
        self, two_worktree_setup: dict
    ) -> None:
        """Demonstrates that using get_main_repo_root() from a worktree reads the WRONG events.

        This test documents the pre-fix behaviour: if you replace
        get_status_read_root() with get_main_repo_root(), the events you get
        are from the main repo (to_lane=done), not the worktree (to_lane=in_progress).

        Reviewers: this test asserts the BUGGY behaviour for documentation only.
        If it starts failing it means the main repo's event log was also modified
        to in_progress (making the bug undetectable) — that would be a test
        infrastructure issue, not a code regression.
        """
        from specify_cli.core.paths import get_main_repo_root
        from specify_cli.status.store import read_events

        worktree: Path = two_worktree_setup["worktree"]
        mission_slug: str = two_worktree_setup["mission_slug"]

        # The old (buggy) resolver always returns the main repo root
        buggy_root = get_main_repo_root(worktree)
        feature_dir = buggy_root / "kitty-specs" / mission_slug
        events = read_events(feature_dir)

        # Without the fix: main repo's events are "done" (wrong when in worktree)
        assert len(events) == 1
        assert events[0].to_lane.value == "done", (
            "The main repo event log has changed. The regression guard needs updating."
        )
