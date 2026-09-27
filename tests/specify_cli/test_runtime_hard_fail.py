"""Tests for runtime hard-fail when canonical status is absent.

Verifies that:
1. Event log absent -> hard-fail with CanonicalStatusNotFoundError
2. Event log exists, WP missing -> "uninitialized"
3. Event log exists, WP has state -> correct lane returned
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.status.lane_reader import (
    CanonicalStatusNotFoundError,
    get_all_wp_lanes,
    get_wp_lane,
    has_event_log,
)
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import EVENTS_FILENAME, append_event


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.unit, pytest.mark.fast]

def _make_feature_dir(tmp_path: Path, slug: str = "099-test-feature") -> Path:
    """Create a minimal feature directory with a WP file."""
    feature_dir = tmp_path / "kitty-specs" / slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "WP01.md").write_text(
        "---\nwork_package_id: WP01\ntitle: Test WP01\n---\n# WP01\n",
        encoding="utf-8",
    )
    (tasks_dir / "WP02.md").write_text(
        "---\nwork_package_id: WP02\ntitle: Test WP02\n---\n# WP02\n",
        encoding="utf-8",
    )
    return feature_dir


def _write_event(feature_dir: Path, wp_id: str, to_lane: str, from_lane: str = "planned") -> None:
    """Append a single status event to the feature's event log."""
    event = StatusEvent(
        event_id=f"01TEST{wp_id}{to_lane.upper()[:4]}",
        mission_slug=feature_dir.name,
        wp_id=wp_id,
        from_lane=Lane(from_lane),
        to_lane=Lane(to_lane),
        at="2026-03-30T12:00:00+00:00",
        actor="test-agent",
        force=False,
        execution_mode="worktree",
    )
    append_event(feature_dir, event)


# ---------------------------------------------------------------------------
# Scenario 1: Event log absent -> hard-fail
# ---------------------------------------------------------------------------


class TestEventLogAbsent:
    """When status.events.jsonl does not exist, all readers must hard-fail."""

    def test_has_event_log_returns_false(self, tmp_path: Path) -> None:
        feature_dir = _make_feature_dir(tmp_path)
        assert not has_event_log(feature_dir)

    def test_get_wp_lane_raises(self, tmp_path: Path) -> None:
        feature_dir = _make_feature_dir(tmp_path)
        with pytest.raises(CanonicalStatusNotFoundError, match="Canonical status not found"):
            get_wp_lane(feature_dir, "WP01")

    def test_get_wp_lane_error_mentions_finalize_tasks(self, tmp_path: Path) -> None:
        feature_dir = _make_feature_dir(tmp_path)
        with pytest.raises(CanonicalStatusNotFoundError, match="finalize-tasks"):
            get_wp_lane(feature_dir, "WP01")

    def test_get_wp_lane_error_includes_mission_slug(self, tmp_path: Path) -> None:
        feature_dir = _make_feature_dir(tmp_path, slug="060-my-feature")
        with pytest.raises(CanonicalStatusNotFoundError, match="060-my-feature"):
            get_wp_lane(feature_dir, "WP01")

    def test_get_all_wp_lanes_raises(self, tmp_path: Path) -> None:
        feature_dir = _make_feature_dir(tmp_path)
        with pytest.raises(CanonicalStatusNotFoundError, match="Canonical status not found"):
            get_all_wp_lanes(feature_dir)

    def test_work_package_lane_property_raises(self, tmp_path: Path) -> None:
        """WorkPackage.lane should propagate CanonicalStatusNotFoundError."""
        from specify_cli.task_utils import WorkPackage, split_frontmatter

        feature_dir = _make_feature_dir(tmp_path)
        wp_path = feature_dir / "tasks" / "WP01.md"
        text = wp_path.read_text(encoding="utf-8")
        front, body, padding = split_frontmatter(text)

        wp = WorkPackage(
            feature=feature_dir.name,
            path=wp_path,
            current_lane="planned",
            relative_subpath=Path("WP01.md"),
            frontmatter=front,
            body=body,
            padding=padding,
        )
        with pytest.raises(CanonicalStatusNotFoundError):
            _ = wp.lane

    def test_get_lane_from_frontmatter_raises(self, tmp_path: Path) -> None:
        """get_lane_from_frontmatter should propagate CanonicalStatusNotFoundError."""
        from specify_cli.task_utils import get_lane_from_frontmatter

        feature_dir = _make_feature_dir(tmp_path)
        wp_path = feature_dir / "tasks" / "WP01.md"
        with pytest.raises(CanonicalStatusNotFoundError):
            get_lane_from_frontmatter(wp_path)

    def test_dashboard_count_wps_by_lane_raises(self, tmp_path: Path) -> None:
        """Dashboard _count_wps_by_lane should propagate CanonicalStatusNotFoundError."""
        from specify_cli.dashboard.scanner import _count_wps_by_lane

        feature_dir = _make_feature_dir(tmp_path)
        tasks_dir = feature_dir / "tasks"
        with pytest.raises(CanonicalStatusNotFoundError):
            _count_wps_by_lane(tasks_dir)


# ---------------------------------------------------------------------------
# Scenario 2: Event log exists, WP missing -> "uninitialized"
# ---------------------------------------------------------------------------


class TestEventLogExistsWPMissing:
    """When event log exists but a WP has no events, return 'uninitialized'."""

    def test_has_event_log_returns_true(self, tmp_path: Path) -> None:
        feature_dir = _make_feature_dir(tmp_path)
        _write_event(feature_dir, "WP01", "claimed")
        assert has_event_log(feature_dir)

    def test_known_wp_returns_correct_lane(self, tmp_path: Path) -> None:
        feature_dir = _make_feature_dir(tmp_path)
        _write_event(feature_dir, "WP01", "claimed")
        assert get_wp_lane(feature_dir, "WP01") == "claimed"

    def test_unknown_wp_returns_uninitialized(self, tmp_path: Path) -> None:
        feature_dir = _make_feature_dir(tmp_path)
        _write_event(feature_dir, "WP01", "claimed")
        assert get_wp_lane(feature_dir, "WP02") == "uninitialized"

    def test_get_all_wp_lanes_excludes_missing(self, tmp_path: Path) -> None:
        feature_dir = _make_feature_dir(tmp_path)
        _write_event(feature_dir, "WP01", "claimed")
        lanes = get_all_wp_lanes(feature_dir)
        assert "WP01" in lanes
        assert "WP02" not in lanes

    def test_work_package_lane_returns_uninitialized(self, tmp_path: Path) -> None:
        """WorkPackage.lane for a WP not in the event log returns 'uninitialized'."""
        from specify_cli.task_utils import WorkPackage, split_frontmatter

        feature_dir = _make_feature_dir(tmp_path)
        # Only WP01 has an event
        _write_event(feature_dir, "WP01", "claimed")

        wp_path = feature_dir / "tasks" / "WP02.md"
        text = wp_path.read_text(encoding="utf-8")
        front, body, padding = split_frontmatter(text)

        wp = WorkPackage(
            feature=feature_dir.name,
            path=wp_path,
            current_lane="planned",
            relative_subpath=Path("WP02.md"),
            frontmatter=front,
            body=body,
            padding=padding,
        )
        assert wp.lane == "uninitialized"

    def test_empty_event_log_returns_uninitialized(self, tmp_path: Path) -> None:
        """An existing but empty event log file: all WPs are uninitialized."""
        feature_dir = _make_feature_dir(tmp_path)
        (feature_dir / EVENTS_FILENAME).write_text("", encoding="utf-8")
        assert has_event_log(feature_dir)
        assert get_wp_lane(feature_dir, "WP01") == "uninitialized"

    def test_dashboard_count_excludes_uninitialized_wps(self, tmp_path: Path) -> None:
        """Dashboard excludes WPs not yet seeded in the event log."""
        from specify_cli.dashboard.scanner import _count_wps_by_lane

        feature_dir = _make_feature_dir(tmp_path)
        _write_event(feature_dir, "WP01", "in_progress", from_lane="planned")
        tasks_dir = feature_dir / "tasks"
        counts = _count_wps_by_lane(tasks_dir)
        assert counts["doing"] == 1  # WP01 (in_progress -> doing display)
        assert counts["planned"] == 0  # WP02 is genesis/uninitialized and not displayed


# ---------------------------------------------------------------------------
# Scenario 3: Event log exists, WP has state -> correct lane
# ---------------------------------------------------------------------------


class TestEventLogExistsWPHasState:
    """When event log has state for the WP, return the correct lane."""

    def test_planned_lane(self, tmp_path: Path) -> None:
        feature_dir = _make_feature_dir(tmp_path)
        # Write a planned->planned event (bootstrap)
        event = StatusEvent(
            event_id="01TESTBOOTWP01",
            mission_slug=feature_dir.name,
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.PLANNED,
            at="2026-03-30T12:00:00+00:00",
            actor="bootstrap",
            force=False,
            execution_mode="direct_repo",
        )
        append_event(feature_dir, event)
        assert get_wp_lane(feature_dir, "WP01") == "planned"

    def test_in_progress_lane(self, tmp_path: Path) -> None:
        feature_dir = _make_feature_dir(tmp_path)
        _write_event(feature_dir, "WP01", "claimed")
        _write_event(feature_dir, "WP01", "in_progress", from_lane="claimed")
        assert get_wp_lane(feature_dir, "WP01") == "in_progress"

    def test_done_lane(self, tmp_path: Path) -> None:
        feature_dir = _make_feature_dir(tmp_path)
        _write_event(feature_dir, "WP01", "claimed")
        _write_event(feature_dir, "WP01", "in_progress", from_lane="claimed")
        _write_event(feature_dir, "WP01", "for_review", from_lane="in_progress")
        _write_event(feature_dir, "WP01", "approved", from_lane="for_review")
        # done requires evidence — write raw event
        event = StatusEvent(
            event_id="01TESTDONEWP01",
            mission_slug=feature_dir.name,
            wp_id="WP01",
            from_lane=Lane.APPROVED,
            to_lane=Lane.DONE,
            at="2026-03-30T18:00:00+00:00",
            actor="merge",
            force=False,
            execution_mode="worktree",
        )
        append_event(feature_dir, event)
        assert get_wp_lane(feature_dir, "WP01") == "done"

    def test_multiple_wps_correct_lanes(self, tmp_path: Path) -> None:
        feature_dir = _make_feature_dir(tmp_path)
        _write_event(feature_dir, "WP01", "in_progress")
        _write_event(feature_dir, "WP02", "for_review")
        lanes = get_all_wp_lanes(feature_dir)
        assert lanes["WP01"] == "in_progress"
        assert lanes["WP02"] == "for_review"

    def test_no_frontmatter_consulted(self, tmp_path: Path) -> None:
        """Even if frontmatter says 'done', event log lane is authoritative."""
        feature_dir = _make_feature_dir(tmp_path)
        # Write frontmatter with lane: done
        wp_path = feature_dir / "tasks" / "WP01.md"
        wp_path.write_text(
            "---\nwork_package_id: WP01\ntitle: Test\nlane: done\n---\n# WP01\n",
            encoding="utf-8",
        )
        # But event log says claimed
        _write_event(feature_dir, "WP01", "claimed")
        assert get_wp_lane(feature_dir, "WP01") == "claimed"

    def test_get_lane_from_frontmatter_uses_event_log(self, tmp_path: Path) -> None:
        """get_lane_from_frontmatter reads from event log, not frontmatter."""
        from specify_cli.task_utils import get_lane_from_frontmatter

        feature_dir = _make_feature_dir(tmp_path)
        wp_path = feature_dir / "tasks" / "WP01.md"
        wp_path.write_text(
            "---\nwork_package_id: WP01\ntitle: Test\nlane: done\n---\n# WP01\n",
            encoding="utf-8",
        )
        _write_event(feature_dir, "WP01", "for_review")
        assert get_lane_from_frontmatter(wp_path) == "for_review"


# ---------------------------------------------------------------------------
# Merge preflight: hard-fail on missing canonical state
# ---------------------------------------------------------------------------


class TestMergePreflightHardFail:
    """merge.py _mark_wp_merged_done handles absent canonical state explicitly."""

    def test_mark_wp_merged_done_skips_without_event_log(self, tmp_path: Path) -> None:
        """_mark_wp_merged_done should not invent done state without canonical history."""
        from specify_cli.cli.commands.consolidate import _mark_wp_merged_done

        feature_dir = _make_feature_dir(tmp_path)
        _mark_wp_merged_done(
            repo_root=tmp_path,
            mission_slug=feature_dir.name,
            wp_id="WP01",
            target_branch="main",
        )
        assert not (feature_dir / EVENTS_FILENAME).exists()
