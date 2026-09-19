"""Unit tests for merge state persistence module.

Tests the MergeState dataclass, state persistence at the canonical per-mission
location (.kittify/runtime/merge/<mission_id>/state.json), and lock management.
"""

from __future__ import annotations


import pytest

pytestmark = pytest.mark.fast

from specify_cli.merge.state import (
    MergeState,
    MergeStateReadError,
    acquire_merge_lock,
    clear_state,
    get_state_path,
    has_active_merge,
    is_merge_locked,
    load_state,
    release_merge_lock,
    save_state,
)


MISSION_ID = "057-test-feature"


class TestMergeStateDataclass:
    """Tests for MergeState dataclass."""

    def test_create_minimal(self):
        state = MergeState(
            mission_id=MISSION_ID,
            mission_slug="test-feature",
            target_branch="main",
            wp_order=["WP01", "WP02", "WP03"],
        )
        assert state.mission_id == MISSION_ID
        assert state.mission_slug == "test-feature"
        assert state.target_branch == "main"
        assert state.wp_order == ["WP01", "WP02", "WP03"]
        assert state.completed_wps == []
        assert state.current_wp is None
        assert state.has_pending_conflicts is False
        assert state.strategy == "merge"
        assert state.workspace_path is None

    def test_remaining_wps(self):
        state = MergeState(
            mission_id=MISSION_ID,
            mission_slug="test-feature",
            target_branch="main",
            wp_order=["WP01", "WP02", "WP03"],
            completed_wps=["WP01"],
        )
        assert state.remaining_wps == ["WP02", "WP03"]

    def test_remaining_wps_all_complete(self):
        state = MergeState(
            mission_id=MISSION_ID,
            mission_slug="test-feature",
            target_branch="main",
            wp_order=["WP01", "WP02"],
            completed_wps=["WP01", "WP02"],
        )
        assert state.remaining_wps == []

    def test_progress_percent_zero(self):
        state = MergeState(
            mission_id=MISSION_ID,
            mission_slug="test-feature",
            target_branch="main",
            wp_order=["WP01", "WP02", "WP03"],
        )
        assert state.progress_percent == 0.0

    def test_progress_percent_partial(self):
        state = MergeState(
            mission_id=MISSION_ID,
            mission_slug="test-feature",
            target_branch="main",
            wp_order=["WP01", "WP02", "WP03", "WP04"],
            completed_wps=["WP01", "WP02"],
        )
        assert state.progress_percent == 50.0

    def test_progress_percent_complete(self):
        state = MergeState(
            mission_id=MISSION_ID,
            mission_slug="test-feature",
            target_branch="main",
            wp_order=["WP01", "WP02"],
            completed_wps=["WP01", "WP02"],
        )
        assert state.progress_percent == 100.0

    def test_progress_percent_empty_wp_order(self):
        state = MergeState(
            mission_id=MISSION_ID,
            mission_slug="test-feature",
            target_branch="main",
            wp_order=[],
        )
        assert state.progress_percent == 0.0

    def test_mark_wp_complete(self):
        state = MergeState(
            mission_id=MISSION_ID,
            mission_slug="test-feature",
            target_branch="main",
            wp_order=["WP01", "WP02"],
            current_wp="WP01",
            has_pending_conflicts=True,
        )
        state.mark_wp_complete("WP01")
        assert "WP01" in state.completed_wps
        assert state.current_wp is None
        assert state.has_pending_conflicts is False

    def test_mark_wp_complete_no_duplicate(self):
        state = MergeState(
            mission_id=MISSION_ID,
            mission_slug="test-feature",
            target_branch="main",
            wp_order=["WP01", "WP02"],
            completed_wps=["WP01"],
        )
        state.mark_wp_complete("WP01")
        assert state.completed_wps == ["WP01"]  # Still only one entry

    def test_set_current_wp(self):
        state = MergeState(
            mission_id=MISSION_ID,
            mission_slug="test-feature",
            target_branch="main",
            wp_order=["WP01", "WP02"],
        )
        state.set_current_wp("WP02")
        assert state.current_wp == "WP02"

    def test_set_pending_conflicts(self):
        state = MergeState(
            mission_id=MISSION_ID,
            mission_slug="test-feature",
            target_branch="main",
            wp_order=["WP01"],
        )
        state.set_pending_conflicts(True)
        assert state.has_pending_conflicts is True
        state.set_pending_conflicts(False)
        assert state.has_pending_conflicts is False

    def test_workspace_path_field(self):
        state = MergeState(
            mission_id=MISSION_ID,
            mission_slug="test-feature",
            target_branch="main",
            wp_order=["WP01"],
            workspace_path="/path/to/workspace",
        )
        assert state.workspace_path == "/path/to/workspace"

    def test_to_dict(self):
        state = MergeState(
            mission_id=MISSION_ID,
            mission_slug="test-feature",
            target_branch="main",
            wp_order=["WP01", "WP02"],
            completed_wps=["WP01"],
            current_wp="WP02",
            strategy="squash",
        )
        d = state.to_dict()
        assert d["mission_id"] == MISSION_ID
        assert d["mission_slug"] == "test-feature"
        assert d["target_branch"] == "main"
        assert d["wp_order"] == ["WP01", "WP02"]
        assert d["completed_wps"] == ["WP01"]
        assert d["current_wp"] == "WP02"
        assert d["strategy"] == "squash"

    def test_from_dict(self):
        data = {
            "mission_id": MISSION_ID,
            "mission_slug": "test-feature",
            "target_branch": "main",
            "wp_order": ["WP01", "WP02"],
            "completed_wps": ["WP01"],
            "current_wp": "WP02",
            "has_pending_conflicts": True,
            "strategy": "squash",
            "workspace_path": None,
            "started_at": "2026-01-18T10:00:00",
            "updated_at": "2026-01-18T10:30:00",
        }
        state = MergeState.from_dict(data)
        assert state.mission_id == MISSION_ID
        assert state.mission_slug == "test-feature"
        assert state.completed_wps == ["WP01"]
        assert state.current_wp == "WP02"
        assert state.has_pending_conflicts is True


class TestStatePersistence:
    """Tests for save_state, load_state, and clear_state at canonical location."""

    def test_save_and_load_state(self, tmp_path):
        state = MergeState(
            mission_id=MISSION_ID,
            mission_slug="test-feature",
            target_branch="main",
            wp_order=["WP01", "WP02", "WP03"],
            completed_wps=["WP01"],
            current_wp="WP02",
        )
        save_state(state, tmp_path)

        loaded = load_state(tmp_path, MISSION_ID)
        assert loaded is not None
        assert loaded.mission_id == MISSION_ID
        assert loaded.mission_slug == "test-feature"
        assert loaded.wp_order == ["WP01", "WP02", "WP03"]
        assert loaded.completed_wps == ["WP01"]
        assert loaded.current_wp == "WP02"

    def test_state_written_to_canonical_location(self, tmp_path):
        """State file must be at .kittify/runtime/merge/<mission_id>/state.json."""
        state = MergeState(
            mission_id=MISSION_ID,
            mission_slug="test-feature",
            target_branch="main",
            wp_order=["WP01"],
        )
        save_state(state, tmp_path)

        expected_path = tmp_path / ".kittify" / "runtime" / "merge" / MISSION_ID / "state.json"
        assert expected_path.exists(), f"State file not found at {expected_path}"

    def test_get_state_path_with_mission_id(self, tmp_path):
        path = get_state_path(tmp_path, MISSION_ID)
        assert path == tmp_path / ".kittify" / "runtime" / "merge" / MISSION_ID / "state.json"

    def test_get_state_path_legacy_no_mission_id(self, tmp_path):
        """Legacy path: no mission_id → old .kittify/merge-state.json location."""
        path = get_state_path(tmp_path)
        assert path == tmp_path / ".kittify" / "merge-state.json"

    def test_load_state_missing_file(self, tmp_path):
        result = load_state(tmp_path, MISSION_ID)
        assert result is None

    def test_load_state_scan_finds_first_active(self, tmp_path):
        """load_state() without mission_id scans runtime dir for first match."""
        state = MergeState(
            mission_id=MISSION_ID,
            mission_slug="test-feature",
            target_branch="main",
            wp_order=["WP01", "WP02"],
            completed_wps=["WP01"],
        )
        save_state(state, tmp_path)

        loaded = load_state(tmp_path)
        assert loaded is not None
        assert loaded.mission_id == MISSION_ID

    def test_load_state_invalid_json(self, tmp_path):
        """WP07/#4746 (cli-error-surface-seam): a corrupt state.json for an
        EXPLICITLY-named mission_id fails closed with a typed
        ``MergeStateReadError`` rather than silently masquerading as "no
        merge in progress" -- see ``_load_state_file``'s docstring.
        """
        state_file = tmp_path / ".kittify" / "runtime" / "merge" / MISSION_ID / "state.json"
        state_file.parent.mkdir(parents=True)
        state_file.write_text("not valid json{", encoding="utf-8")

        with pytest.raises(MergeStateReadError):
            load_state(tmp_path, MISSION_ID)

    def test_load_state_missing_fields(self, tmp_path):
        """WP07/#4746: schema-invalid (but syntactically valid) JSON for an
        explicit mission_id also fails closed -- see test_load_state_invalid_json.
        """
        state_file = tmp_path / ".kittify" / "runtime" / "merge" / MISSION_ID / "state.json"
        state_file.parent.mkdir(parents=True)
        state_file.write_text('{"mission_id": "test"}', encoding="utf-8")

        with pytest.raises(MergeStateReadError):
            load_state(tmp_path, MISSION_ID)  # Missing required fields

    def test_clear_state_with_mission_id(self, tmp_path):
        state = MergeState(
            mission_id=MISSION_ID,
            mission_slug="test-feature",
            target_branch="main",
            wp_order=["WP01"],
        )
        save_state(state, tmp_path)

        state_path = get_state_path(tmp_path, MISSION_ID)
        assert state_path.exists()

        result = clear_state(tmp_path, MISSION_ID)
        assert result is True
        assert not state_path.exists()

    def test_clear_state_no_file(self, tmp_path):
        result = clear_state(tmp_path, MISSION_ID)
        assert result is False

    def test_clear_state_scan_removes_first_active(self, tmp_path):
        """clear_state() without mission_id removes the first active state found."""
        state = MergeState(
            mission_id=MISSION_ID,
            mission_slug="test-feature",
            target_branch="main",
            wp_order=["WP01"],
        )
        save_state(state, tmp_path)

        result = clear_state(tmp_path)
        assert result is True
        assert not get_state_path(tmp_path, MISSION_ID).exists()

    def test_save_creates_runtime_directory(self, tmp_path):
        state = MergeState(
            mission_id=MISSION_ID,
            mission_slug="test-feature",
            target_branch="main",
            wp_order=["WP01"],
        )
        runtime_dir = tmp_path / ".kittify" / "runtime" / "merge" / MISSION_ID
        assert not runtime_dir.exists()

        save_state(state, tmp_path)

        assert runtime_dir.exists()
        assert (runtime_dir / "state.json").exists()

    def test_per_mission_scoping(self, tmp_path):
        """Two missions have independent state files."""
        state_a = MergeState(
            mission_id="feature-a",
            mission_slug="feature-a",
            target_branch="main",
            wp_order=["WP01"],
        )
        state_b = MergeState(
            mission_id="feature-b",
            mission_slug="feature-b",
            target_branch="main",
            wp_order=["WP01", "WP02"],
        )
        save_state(state_a, tmp_path)
        save_state(state_b, tmp_path)

        loaded_a = load_state(tmp_path, "feature-a")
        loaded_b = load_state(tmp_path, "feature-b")

        assert loaded_a is not None
        assert loaded_a.mission_id == "feature-a"
        assert loaded_b is not None
        assert loaded_b.mission_id == "feature-b"
        assert loaded_b.wp_order == ["WP01", "WP02"]


class TestHasActiveMerge:
    """Tests for has_active_merge function."""

    def test_no_state_file(self, tmp_path):
        assert has_active_merge(tmp_path, MISSION_ID) is False

    def test_active_merge_with_remaining_wps(self, tmp_path):
        state = MergeState(
            mission_id=MISSION_ID,
            mission_slug="test-feature",
            target_branch="main",
            wp_order=["WP01", "WP02"],
            completed_wps=["WP01"],
        )
        save_state(state, tmp_path)
        assert has_active_merge(tmp_path, MISSION_ID) is True

    def test_no_active_merge_all_complete(self, tmp_path):
        state = MergeState(
            mission_id=MISSION_ID,
            mission_slug="test-feature",
            target_branch="main",
            wp_order=["WP01", "WP02"],
            completed_wps=["WP01", "WP02"],
        )
        save_state(state, tmp_path)
        assert has_active_merge(tmp_path, MISSION_ID) is False

    def test_has_active_merge_scan(self, tmp_path):
        """has_active_merge() without mission_id scans all missions."""
        state = MergeState(
            mission_id=MISSION_ID,
            mission_slug="test-feature",
            target_branch="main",
            wp_order=["WP01", "WP02"],
            completed_wps=["WP01"],
        )
        save_state(state, tmp_path)
        assert has_active_merge(tmp_path) is True


class TestLockManagement:
    """Tests for acquire/release/check lock functions."""

    def test_acquire_lock_creates_file(self, tmp_path):
        result = acquire_merge_lock(MISSION_ID, tmp_path)
        assert result is True

        lock_path = tmp_path / ".kittify" / "runtime" / "merge" / MISSION_ID / "lock"
        assert lock_path.exists()

    def test_acquire_lock_fails_if_already_locked(self, tmp_path):
        acquire_merge_lock(MISSION_ID, tmp_path)
        result = acquire_merge_lock(MISSION_ID, tmp_path)
        assert result is False

    def test_release_lock_removes_file(self, tmp_path):
        acquire_merge_lock(MISSION_ID, tmp_path)
        release_merge_lock(MISSION_ID, tmp_path)

        lock_path = tmp_path / ".kittify" / "runtime" / "merge" / MISSION_ID / "lock"
        assert not lock_path.exists()

    def test_release_lock_noop_if_not_locked(self, tmp_path):
        # Should not raise
        release_merge_lock(MISSION_ID, tmp_path)

    def test_is_merge_locked_false_initially(self, tmp_path):
        assert is_merge_locked(MISSION_ID, tmp_path) is False

    def test_is_merge_locked_true_after_acquire(self, tmp_path):
        acquire_merge_lock(MISSION_ID, tmp_path)
        assert is_merge_locked(MISSION_ID, tmp_path) is True

    def test_is_merge_locked_false_after_release(self, tmp_path):
        acquire_merge_lock(MISSION_ID, tmp_path)
        release_merge_lock(MISSION_ID, tmp_path)
        assert is_merge_locked(MISSION_ID, tmp_path) is False

    def test_lock_creates_runtime_directory(self, tmp_path):
        runtime_dir = tmp_path / ".kittify" / "runtime" / "merge" / MISSION_ID
        assert not runtime_dir.exists()

        acquire_merge_lock(MISSION_ID, tmp_path)

        assert runtime_dir.exists()

    def test_locks_are_per_mission(self, tmp_path):
        """Locking mission-a does not affect mission-b."""
        acquire_merge_lock("mission-a", tmp_path)

        assert is_merge_locked("mission-a", tmp_path) is True
        assert is_merge_locked("mission-b", tmp_path) is False


class TestStateRoundTrip:
    """Integration tests for complete state round-trip."""

    def test_complete_workflow(self, tmp_path):
        # Start merge
        state = MergeState(
            mission_id=MISSION_ID,
            mission_slug="017-feature",
            target_branch="main",
            wp_order=["WP01", "WP02", "WP03"],
            strategy="squash",
        )
        save_state(state, tmp_path)

        # Merge WP01
        state.set_current_wp("WP01")
        save_state(state, tmp_path)

        state.mark_wp_complete("WP01")
        save_state(state, tmp_path)

        # Simulate interruption - load from file
        loaded = load_state(tmp_path, MISSION_ID)
        assert loaded is not None
        assert loaded.completed_wps == ["WP01"]
        assert loaded.remaining_wps == ["WP02", "WP03"]
        assert loaded.progress_percent == pytest.approx(33.33, rel=0.01)

        # Continue with WP02
        loaded.set_current_wp("WP02")
        save_state(loaded, tmp_path)

        loaded.mark_wp_complete("WP02")
        save_state(loaded, tmp_path)

        # Verify final state
        final = load_state(tmp_path, MISSION_ID)
        assert final is not None
        assert final.completed_wps == ["WP01", "WP02"]
        assert final.remaining_wps == ["WP03"]
        assert final.progress_percent == pytest.approx(66.67, rel=0.01)
