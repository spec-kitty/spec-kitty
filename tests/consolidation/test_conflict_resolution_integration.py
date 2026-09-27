"""Conflict resolution integration tests (T079).

Tests rollback-beats-forward precedence, non-conflicting events for
different WPs, duplicate event ID deduplication, concurrent forward
events (timestamp-wins), and deduplication determinism.
"""

from __future__ import annotations

from pathlib import Path

from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.reducer import reduce
from specify_cli.status.store import append_event, read_events

import pytest

pytestmark = pytest.mark.git_repo

# ── Helpers ──────────────────────────────────────────────────────

def _make_event(
    event_id: str,
    wp_id: str,
    from_lane: str,
    to_lane: str,
    at: str,
    *,
    actor: str = "agent-1",
    force: bool = False,
    reason: str | None = None,
    review_ref: str | None = None,
    mission_slug: str = "099-conflict-test",
) -> StatusEvent:
    """Create a StatusEvent with sensible defaults."""
    return StatusEvent(
        event_id=event_id,
        mission_slug=mission_slug,
        wp_id=wp_id,
        from_lane=Lane(from_lane),
        to_lane=Lane(to_lane),
        at=at,
        actor=actor,
        force=force,
        execution_mode="worktree",
        reason=reason,
        review_ref=review_ref,
    )

# ── Tests ────────────────────────────────────────────────────────

class TestRollbackBeatsForwardProgression:
    """T079: Rollback events take precedence over forward transitions
    when they occur at the same timestamp."""

    def test_rollback_beats_forward_progression(self):
        """A reviewer rollback (for_review->in_progress with review_ref)
        beats a concurrent forward transition at the same timestamp."""
        # Concurrent events at the same timestamp:
        # 1. Forward: for_review -> done (agent moves forward)
        # 2. Rollback: for_review -> in_progress (reviewer requests changes)

        # First get WP01 to for_review state
        setup_events = [
            _make_event("01AAA00000000000000000001A", "WP01", "planned", "claimed",
                        "2026-01-15T10:00:00+00:00"),
            _make_event("01AAA00000000000000000002A", "WP01", "claimed", "in_progress",
                        "2026-01-15T10:01:00+00:00"),
            _make_event("01AAA00000000000000000003A", "WP01", "in_progress", "for_review",
                        "2026-01-15T10:02:00+00:00"),
        ]

        # Concurrent events at the SAME timestamp
        same_ts = "2026-01-15T10:03:00+00:00"

        forward_event = _make_event(
            "01AAA00000000000000000004B",  # Sorts AFTER rollback by event_id
            "WP01", "for_review", "done", same_ts,
            actor="auto-merge",
        )
        rollback_event = _make_event(
            "01AAA00000000000000000004A",  # Sorts BEFORE forward by event_id
            "WP01", "for_review", "in_progress", same_ts,
            actor="reviewer-1",
            review_ref="PR#42-changes-requested",
        )

        # Process forward first, then rollback (rollback should win)
        all_events = setup_events + [forward_event, rollback_event]
        snapshot = reduce(all_events)

        assert snapshot.work_packages["WP01"]["lane"] == "in_progress"

    def test_rollback_beats_forward_reversed_order(self):
        """Even if events are provided in reversed order, rollback still wins."""
        setup_events = [
            _make_event("01BBB00000000000000000001A", "WP01", "planned", "claimed",
                        "2026-01-15T10:00:00+00:00"),
            _make_event("01BBB00000000000000000002A", "WP01", "claimed", "in_progress",
                        "2026-01-15T10:01:00+00:00"),
            _make_event("01BBB00000000000000000003A", "WP01", "in_progress", "for_review",
                        "2026-01-15T10:02:00+00:00"),
        ]

        same_ts = "2026-01-15T10:03:00+00:00"

        rollback_event = _make_event(
            "01BBB00000000000000000004A",
            "WP01", "for_review", "in_progress", same_ts,
            actor="reviewer-1",
            review_ref="PR#42-changes-requested",
        )
        forward_event = _make_event(
            "01BBB00000000000000000004B",
            "WP01", "for_review", "done", same_ts,
            actor="auto-merge",
        )

        # Provide rollback first, then forward
        all_events = setup_events + [rollback_event, forward_event]
        snapshot = reduce(all_events)

        assert snapshot.work_packages["WP01"]["lane"] == "in_progress"

class TestNonConflictingEventsForDifferentWPs:
    """T079: Events for different WPs don't interfere."""

    def test_non_conflicting_events_for_different_wps(self):
        """Two WPs transitioning independently don't conflict."""
        events = [
            _make_event("01CCC00000000000000000001A", "WP01", "planned", "claimed",
                        "2026-01-15T10:00:00+00:00", actor="agent-1"),
            _make_event("01CCC00000000000000000002A", "WP02", "planned", "claimed",
                        "2026-01-15T10:00:00+00:00", actor="agent-2"),
            _make_event("01CCC00000000000000000003A", "WP01", "claimed", "in_progress",
                        "2026-01-15T10:01:00+00:00", actor="agent-1"),
            _make_event("01CCC00000000000000000004A", "WP02", "claimed", "in_progress",
                        "2026-01-15T10:01:00+00:00", actor="agent-2"),
        ]

        snapshot = reduce(events)

        assert snapshot.work_packages["WP01"]["lane"] == "in_progress"
        assert snapshot.work_packages["WP01"]["actor"] == "agent-1"
        assert snapshot.work_packages["WP02"]["lane"] == "in_progress"
        assert snapshot.work_packages["WP02"]["actor"] == "agent-2"

class TestDuplicateEventIdsDeduplicated:
    """T079: Duplicate event_ids are deduplicated (first occurrence wins)."""

    def test_duplicate_event_ids_deduplicated(self):
        """When two events share the same event_id, only the first is kept."""
        duplicate_id = "01DDD00000000000000000001A"

        events = [
            _make_event(duplicate_id, "WP01", "planned", "claimed",
                        "2026-01-15T10:00:00+00:00"),
            _make_event(duplicate_id, "WP01", "planned", "in_progress",
                        "2026-01-15T10:01:00+00:00"),
        ]

        snapshot = reduce(events)

        # Only first occurrence kept -> WP01 should be "claimed" not "in_progress"
        assert snapshot.work_packages["WP01"]["lane"] == "claimed"
        assert snapshot.event_count == 1

class TestConcurrentForwardEventsTimestampWins:
    """T079: When two non-rollback forward events have different timestamps,
    the later one wins naturally through sort order."""

    def test_concurrent_forward_events_timestamp_wins(self):
        """Later timestamp wins for two forward events."""
        events = [
            _make_event("01EEE00000000000000000001A", "WP01", "planned", "claimed",
                        "2026-01-15T10:00:00+00:00"),
            _make_event("01EEE00000000000000000002A", "WP01", "claimed", "in_progress",
                        "2026-01-15T10:01:00+00:00"),
            _make_event("01EEE00000000000000000003A", "WP01", "in_progress", "for_review",
                        "2026-01-15T10:02:00+00:00"),
        ]

        snapshot = reduce(events)

        # The last event (for_review) wins because it has the latest timestamp
        assert snapshot.work_packages["WP01"]["lane"] == "for_review"
        assert snapshot.work_packages["WP01"]["last_event_id"] == "01EEE00000000000000000003A"

class TestDeduplicationPreservesDeterminism:
    """T079: Deduplication is deterministic regardless of input order."""

    def test_deduplication_preserves_determinism(self):
        """Shuffling events with duplicates still produces the same result."""
        dup_id = "01FFF00000000000000000001A"
        unique_id = "01FFF00000000000000000002A"

        events_order_1 = [
            _make_event(dup_id, "WP01", "planned", "claimed",
                        "2026-01-15T10:00:00+00:00"),
            _make_event(dup_id, "WP01", "planned", "blocked",
                        "2026-01-15T10:00:01+00:00"),
            _make_event(unique_id, "WP01", "claimed", "in_progress",
                        "2026-01-15T10:01:00+00:00"),
        ]

        events_order_2 = [
            _make_event(unique_id, "WP01", "claimed", "in_progress",
                        "2026-01-15T10:01:00+00:00"),
            _make_event(dup_id, "WP01", "planned", "claimed",
                        "2026-01-15T10:00:00+00:00"),
            _make_event(dup_id, "WP01", "planned", "blocked",
                        "2026-01-15T10:00:01+00:00"),
        ]

        snapshot1 = reduce(events_order_1)
        snapshot2 = reduce(events_order_2)

        assert snapshot1.work_packages == snapshot2.work_packages
        assert snapshot1.summary == snapshot2.summary
        assert snapshot1.event_count == snapshot2.event_count

    def test_dedup_with_persistence(self, tmp_path: Path):
        """Deduplication works correctly through the store layer."""
        feature_dir = tmp_path / "kitty-specs" / "099-dedup-test"
        feature_dir.mkdir(parents=True)

        dup_id = "01GGG00000000000000000001A"
        event1 = _make_event(dup_id, "WP01", "planned", "claimed",
                             "2026-01-15T10:00:00+00:00",
                             mission_slug="099-dedup-test")
        event2 = _make_event(dup_id, "WP01", "planned", "blocked",
                             "2026-01-15T10:00:01+00:00",
                             mission_slug="099-dedup-test")

        append_event(feature_dir, event1)
        append_event(feature_dir, event2)

        # Both lines are in the file
        events_raw = read_events(feature_dir)
        assert len(events_raw) == 2  # Both are in the file

        # But reducer deduplicates
        snapshot = reduce(events_raw)
        assert snapshot.event_count == 1
        assert snapshot.work_packages["WP01"]["lane"] == "claimed"
