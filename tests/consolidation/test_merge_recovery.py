"""Tests for merge interruption and recovery (WP01 / 067).

Covers:
- ConsolidationState lifecycle in _run_lane_based_consolidation (T001)
- Cleanup preserving state.json (T002)
- Event dedup guard in _mark_wp_merged_done (T003)
- Resume/abort CLI paths (T004)
- Retry tolerance for missing worktrees/branches (T005)
- macOS FSEvents delay (T005)
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]  # non_sandbox: trampoline bug: subprocess
from specify_cli.consolidation.state import (
    ConsolidationState,
    clear_state,
    get_state_path,
    load_state,
    save_state,
)
from specify_cli.consolidation.workspace import (
    _worktree_removal_delay,
    cleanup_merge_workspace,
    create_merge_workspace,
    get_merge_runtime_dir,
)


MISSION_ID = "067-test-feature"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a minimal git repository for testing."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    (tmp_path / "README.md").write_text("# Test\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    return tmp_path


# ---------------------------------------------------------------------------
# T001: ConsolidationState lifecycle
# ---------------------------------------------------------------------------


class TestMergeStateLifecycle:
    """Test that ConsolidationState is created, updated per-WP, and consulted on resume."""

    def test_merge_creates_state(self, tmp_path: Path):
        """ConsolidationState is created at merge start."""
        state = ConsolidationState(
            mission_id=MISSION_ID,
            mission_slug=MISSION_ID,
            target_branch="main",
            wp_order=["WP01", "WP02", "WP03"],
        )
        save_state(state, tmp_path)

        loaded = load_state(tmp_path, MISSION_ID)
        assert loaded is not None
        assert loaded.mission_id == MISSION_ID
        assert loaded.wp_order == ["WP01", "WP02", "WP03"]
        assert loaded.completed_wps == []

    def test_state_updated_per_wp(self, tmp_path: Path):
        """State is saved after each WP's done-recording."""
        state = ConsolidationState(
            mission_id=MISSION_ID,
            mission_slug=MISSION_ID,
            target_branch="main",
            wp_order=["WP01", "WP02", "WP03"],
        )
        save_state(state, tmp_path)

        # Simulate marking WP01 as current then complete
        state.set_current_wp("WP01")
        save_state(state, tmp_path)

        loaded = load_state(tmp_path, MISSION_ID)
        assert loaded is not None
        assert loaded.current_wp == "WP01"

        state.mark_wp_complete("WP01")
        save_state(state, tmp_path)

        loaded = load_state(tmp_path, MISSION_ID)
        assert loaded is not None
        assert loaded.completed_wps == ["WP01"]
        assert loaded.current_wp is None

    def test_resume_skips_completed_wps(self, tmp_path: Path):
        """On resume, completed WPs from state are skipped."""
        state = ConsolidationState(
            mission_id=MISSION_ID,
            mission_slug=MISSION_ID,
            target_branch="main",
            wp_order=["WP01", "WP02", "WP03"],
            completed_wps=["WP01"],
        )
        save_state(state, tmp_path)

        loaded = load_state(tmp_path, MISSION_ID)
        assert loaded is not None
        assert loaded.remaining_wps == ["WP02", "WP03"]

        completed_set = set(loaded.completed_wps)
        remaining = [wp for wp in loaded.wp_order if wp not in completed_set]
        assert remaining == ["WP02", "WP03"]


# ---------------------------------------------------------------------------
# T002: Cleanup preserves state.json
# ---------------------------------------------------------------------------


class TestCleanupPreservesState:
    """Test that cleanup_merge_workspace preserves state.json."""

    def test_cleanup_preserves_state_file(self, git_repo: Path):
        """cleanup_merge_workspace removes worktree but preserves state.json."""
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=git_repo, capture_output=True, text=True, check=True,
        ).stdout.strip()

        # Create workspace and state
        create_merge_workspace(MISSION_ID, branch, git_repo)
        state = ConsolidationState(
            mission_id=MISSION_ID,
            mission_slug=MISSION_ID,
            target_branch="main",
            wp_order=["WP01"],
        )
        save_state(state, git_repo)

        state_path = get_state_path(git_repo, MISSION_ID)
        assert state_path.exists()

        # Create an extra temp file in the runtime dir
        runtime_dir = get_merge_runtime_dir(MISSION_ID, git_repo)
        extra_file = runtime_dir / "temp-data.txt"
        extra_file.write_text("temporary", encoding="utf-8")

        cleanup_merge_workspace(MISSION_ID, git_repo)

        # State file must survive
        assert state_path.exists(), "state.json was destroyed by cleanup!"
        # Extra file should be removed
        assert not extra_file.exists(), "Temp file should have been removed"

    def test_clear_state_removes_file(self, tmp_path: Path):
        """clear_state removes the state.json file."""
        state = ConsolidationState(
            mission_id=MISSION_ID,
            mission_slug=MISSION_ID,
            target_branch="main",
            wp_order=["WP01"],
        )
        save_state(state, tmp_path)

        state_path = get_state_path(tmp_path, MISSION_ID)
        assert state_path.exists()

        result = clear_state(tmp_path, MISSION_ID)
        assert result is True
        assert not state_path.exists()

    def test_state_does_not_persist_after_full_cleanup_and_clear(self, git_repo: Path):
        """After cleanup + clear_state, state file is gone."""
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=git_repo, capture_output=True, text=True, check=True,
        ).stdout.strip()

        create_merge_workspace(MISSION_ID, branch, git_repo)
        state = ConsolidationState(
            mission_id=MISSION_ID,
            mission_slug=MISSION_ID,
            target_branch="main",
            wp_order=["WP01"],
        )
        save_state(state, git_repo)

        cleanup_merge_workspace(MISSION_ID, git_repo)
        clear_state(git_repo, MISSION_ID)

        assert load_state(git_repo, MISSION_ID) is None


# ---------------------------------------------------------------------------
# T003: Event dedup guard
# ---------------------------------------------------------------------------


class TestEventDedupGuard:
    """Test that _has_transition_to prevents duplicate event emissions."""

    def test_has_transition_to_empty_log(self, tmp_path: Path):
        """Returns False when there is no event log."""
        from specify_cli.cli.commands.consolidate import _has_transition_to

        feature_dir = tmp_path / "kitty-specs" / MISSION_ID
        feature_dir.mkdir(parents=True)

        assert _has_transition_to(feature_dir, MISSION_ID, "WP01", "done", tmp_path) is False

    def test_has_transition_to_finds_match(self, tmp_path: Path):
        """Returns True when the target transition exists in the log."""
        from specify_cli.cli.commands.consolidate import _has_transition_to

        feature_dir = tmp_path / "kitty-specs" / MISSION_ID
        feature_dir.mkdir(parents=True)

        # Write a fake event to the JSONL file
        events_file = feature_dir / "status.events.jsonl"
        event = {
            "event_id": "01TEST001",
            "mission_slug": MISSION_ID,
            "wp_id": "WP01",
            "from_lane": "approved",
            "to_lane": "done",
            "at": "2026-04-06T12:00:00+00:00",
            "actor": "merge",
            "force": False,
            "execution_mode": "worktree",
        }
        events_file.write_text(json.dumps(event, sort_keys=True) + "\n", encoding="utf-8")

        assert _has_transition_to(feature_dir, MISSION_ID, "WP01", "done", tmp_path) is True

    def test_has_transition_to_no_match(self, tmp_path: Path):
        """Returns False when the target transition does not match."""
        from specify_cli.cli.commands.consolidate import _has_transition_to

        feature_dir = tmp_path / "kitty-specs" / MISSION_ID
        feature_dir.mkdir(parents=True)

        events_file = feature_dir / "status.events.jsonl"
        event = {
            "event_id": "01TEST002",
            "mission_slug": MISSION_ID,
            "wp_id": "WP01",
            "from_lane": "for_review",
            "to_lane": "approved",
            "at": "2026-04-06T12:00:00+00:00",
            "actor": "merge",
            "force": False,
            "execution_mode": "worktree",
        }
        events_file.write_text(json.dumps(event, sort_keys=True) + "\n", encoding="utf-8")

        # WP01 has approved but NOT done
        assert _has_transition_to(feature_dir, MISSION_ID, "WP01", "done", tmp_path) is False
        assert _has_transition_to(feature_dir, MISSION_ID, "WP01", "approved", tmp_path) is True

    def test_has_transition_to_different_wp(self, tmp_path: Path):
        """Dedup is per-WP: WP02 done does not match WP01."""
        from specify_cli.cli.commands.consolidate import _has_transition_to

        feature_dir = tmp_path / "kitty-specs" / MISSION_ID
        feature_dir.mkdir(parents=True)

        events_file = feature_dir / "status.events.jsonl"
        event = {
            "event_id": "01TEST003",
            "mission_slug": MISSION_ID,
            "wp_id": "WP02",
            "from_lane": "approved",
            "to_lane": "done",
            "at": "2026-04-06T12:00:00+00:00",
            "actor": "merge",
            "force": False,
            "execution_mode": "worktree",
        }
        events_file.write_text(json.dumps(event, sort_keys=True) + "\n", encoding="utf-8")

        assert _has_transition_to(feature_dir, MISSION_ID, "WP01", "done", tmp_path) is False
        assert _has_transition_to(feature_dir, MISSION_ID, "WP02", "done", tmp_path) is True

    def test_reconcile_completed_wps_drops_missing_done_evidence(self, tmp_path: Path):
        """Resume state cannot skip a WP when its uncommitted done event was lost."""
        from specify_cli.cli.commands.consolidate import _reconcile_completed_wps_for_resume

        feature_dir = tmp_path / "kitty-specs" / MISSION_ID
        feature_dir.mkdir(parents=True)
        state = ConsolidationState(
            mission_id=MISSION_ID,
            mission_slug=MISSION_ID,
            target_branch="main",
            wp_order=["WP01"],
            completed_wps=["WP01"],
        )
        save_state(state, tmp_path)

        confirmed = _reconcile_completed_wps_for_resume(
            feature_dir=feature_dir,
            mission_slug=MISSION_ID,
            merge_state=state,
            repo_root=tmp_path,
        )

        assert confirmed == set()
        loaded = load_state(tmp_path, MISSION_ID)
        assert loaded is not None
        assert loaded.completed_wps == []

    def test_reconcile_completed_wps_keeps_existing_done_evidence(self, tmp_path: Path):
        """Resume state remains complete when the canonical done event survived."""
        from specify_cli.cli.commands.consolidate import _reconcile_completed_wps_for_resume

        feature_dir = tmp_path / "kitty-specs" / MISSION_ID
        feature_dir.mkdir(parents=True)
        (feature_dir / "status.events.jsonl").write_text(
            json.dumps(
                {
                    "event_id": "01TESTDONE",
                    "mission_slug": MISSION_ID,
                    "wp_id": "WP01",
                    "from_lane": "approved",
                    "to_lane": "done",
                    "at": "2026-04-06T12:00:00+00:00",
                    "actor": "merge",
                    "force": False,
                    "execution_mode": "worktree",
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        state = ConsolidationState(
            mission_id=MISSION_ID,
            mission_slug=MISSION_ID,
            target_branch="main",
            wp_order=["WP01"],
            completed_wps=["WP01"],
        )
        save_state(state, tmp_path)

        confirmed = _reconcile_completed_wps_for_resume(
            feature_dir=feature_dir,
            mission_slug=MISSION_ID,
            merge_state=state,
            repo_root=tmp_path,
        )

        assert confirmed == {"WP01"}
        loaded = load_state(tmp_path, MISSION_ID)
        assert loaded is not None
        assert loaded.completed_wps == ["WP01"]


# ---------------------------------------------------------------------------
# T004: Resume / Abort
# ---------------------------------------------------------------------------


class TestResumeAbort:
    """Test the resume/abort state management paths."""

    def test_resume_with_no_state_errors(self, tmp_path: Path):
        """Resume when no state exists should detect no state."""
        loaded = load_state(tmp_path, MISSION_ID)
        assert loaded is None

    def test_resume_with_existing_state_loads(self, tmp_path: Path):
        """Resume loads the existing state and reports remaining WPs."""
        state = ConsolidationState(
            mission_id=MISSION_ID,
            mission_slug=MISSION_ID,
            target_branch="main",
            wp_order=["WP01", "WP02", "WP03"],
            completed_wps=["WP01"],
        )
        save_state(state, tmp_path)

        loaded = load_state(tmp_path, MISSION_ID)
        assert loaded is not None
        assert loaded.remaining_wps == ["WP02", "WP03"]
        assert loaded.progress_percent == pytest.approx(33.33, rel=0.01)

    def test_abort_cleans_state(self, tmp_path: Path):
        """Abort removes the state file."""
        state = ConsolidationState(
            mission_id=MISSION_ID,
            mission_slug=MISSION_ID,
            target_branch="main",
            wp_order=["WP01", "WP02"],
            completed_wps=["WP01"],
        )
        save_state(state, tmp_path)

        cleared = clear_state(tmp_path, MISSION_ID)
        assert cleared is True
        assert load_state(tmp_path, MISSION_ID) is None

    def test_abort_cleans_workspace_and_state(self, git_repo: Path):
        """Abort removes both workspace and state."""
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=git_repo, capture_output=True, text=True, check=True,
        ).stdout.strip()

        create_merge_workspace(MISSION_ID, branch, git_repo)
        state = ConsolidationState(
            mission_id=MISSION_ID,
            mission_slug=MISSION_ID,
            target_branch="main",
            wp_order=["WP01"],
        )
        save_state(state, git_repo)

        # Abort sequence: clear state, then cleanup workspace
        clear_state(git_repo, MISSION_ID)
        cleanup_merge_workspace(MISSION_ID, git_repo)

        assert load_state(git_repo, MISSION_ID) is None
        runtime_dir = get_merge_runtime_dir(MISSION_ID, git_repo)
        assert not runtime_dir.exists()

    def test_auto_resume_detects_existing_state(self, tmp_path: Path):
        """When merge is called without --resume but state exists, it is detected."""
        state = ConsolidationState(
            mission_id=MISSION_ID,
            mission_slug=MISSION_ID,
            target_branch="main",
            wp_order=["WP01", "WP02"],
            completed_wps=["WP01"],
        )
        save_state(state, tmp_path)

        loaded = load_state(tmp_path, MISSION_ID)
        assert loaded is not None
        assert loaded.remaining_wps == ["WP02"]


# ---------------------------------------------------------------------------
# T005: Retry tolerance
# ---------------------------------------------------------------------------


class TestRetryTolerance:
    """Test tolerance for missing worktrees/branches on retry."""

    def test_cleanup_tolerates_missing_worktree(self, git_repo: Path):
        """cleanup_merge_workspace should not error if worktree never existed."""
        # Create state in runtime dir so it exists
        state = ConsolidationState(
            mission_id=MISSION_ID,
            mission_slug=MISSION_ID,
            target_branch="main",
            wp_order=["WP01"],
        )
        save_state(state, git_repo)

        # Cleanup without ever creating a worktree should not raise
        cleanup_merge_workspace(MISSION_ID, git_repo)

        # State should survive (preserved by selective cleanup)
        loaded = load_state(git_repo, MISSION_ID)
        assert loaded is not None

    # Double cleanup (workspace already gone) is covered by
    # test_merge_workspace_unit.py::TestCleanupMergeWorkspace::test_cleanup_is_idempotent.

    def test_resume_after_partial_cleanup(self, git_repo: Path):
        """After cleanup removes worktree but state persists, resume works."""
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=git_repo, capture_output=True, text=True, check=True,
        ).stdout.strip()

        create_merge_workspace(MISSION_ID, branch, git_repo)

        state = ConsolidationState(
            mission_id=MISSION_ID,
            mission_slug=MISSION_ID,
            target_branch="main",
            wp_order=["WP01", "WP02"],
            completed_wps=["WP01"],
        )
        save_state(state, git_repo)

        # Simulate partial cleanup (worktree removed, state preserved)
        cleanup_merge_workspace(MISSION_ID, git_repo)

        # State should survive
        loaded = load_state(git_repo, MISSION_ID)
        assert loaded is not None
        assert loaded.completed_wps == ["WP01"]
        assert loaded.remaining_wps == ["WP02"]

    def test_macos_fsevents_delay_on_darwin(self):
        """On darwin, delay is 2.0 seconds by default."""
        with patch("specify_cli.consolidation.workspace.sys") as mock_sys:
            mock_sys.platform = "darwin"
            with patch.dict("os.environ", {}, clear=True):
                delay = _worktree_removal_delay()
                assert delay == 2.0

    def test_no_delay_on_linux(self):
        """On linux, delay is 0.0 seconds by default."""
        with patch("specify_cli.consolidation.workspace.sys") as mock_sys:
            mock_sys.platform = "linux"
            with patch.dict("os.environ", {}, clear=True):
                delay = _worktree_removal_delay()
                assert delay == 0.0

    def test_delay_override_via_env(self):
        """SPEC_KITTY_WORKTREE_REMOVAL_DELAY env var overrides platform default."""
        with patch.dict("os.environ", {"SPEC_KITTY_WORKTREE_REMOVAL_DELAY": "0.5"}):
            delay = _worktree_removal_delay()
            assert delay == 0.5

    def test_delay_zero_disables_via_env(self):
        """Setting SPEC_KITTY_WORKTREE_REMOVAL_DELAY=0 disables delay."""
        with patch.dict("os.environ", {"SPEC_KITTY_WORKTREE_REMOVAL_DELAY": "0"}):
            delay = _worktree_removal_delay()
            assert delay == 0.0
