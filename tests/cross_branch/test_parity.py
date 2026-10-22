"""Cross-branch parity tests (T078).

Verifies that the reducer produces deterministic, byte-identical output
from a fixed set of events with known event_ids and timestamps.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.status.models import StatusEvent
from specify_cli.status.reducer import materialize_to_json, reduce

pytestmark = [pytest.mark.integration]

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_sample_events() -> list[StatusEvent]:
    """Load the fixed sample events from the JSONL fixture."""
    events_path = FIXTURES_DIR / "sample_events.jsonl"
    events: list[StatusEvent] = []
    for line in events_path.read_text(encoding="utf-8").strip().split("\n"):
        if not line.strip():
            continue
        data = json.loads(line)
        events.append(StatusEvent.from_dict(data))
    return events


def _load_expected_snapshot() -> dict:
    """Load the expected snapshot from the JSON fixture."""
    path = FIXTURES_DIR / "expected_snapshot.json"
    return json.loads(path.read_text(encoding="utf-8"))


class TestReducerParity:
    """T078: Reducer produces expected snapshot from fixed events."""

    def test_reducer_produces_expected_snapshot(self):
        """Reduce the 10 sample events and verify all fields match
        the expected snapshot (except materialized_at, which is dynamic)."""
        events = _load_sample_events()
        assert len(events) == 10

        snapshot = reduce(events)

        expected = _load_expected_snapshot()

        # Feature slug
        assert snapshot.mission_slug == expected.get("mission_slug", expected.get("mission_slug"))

        # Event count
        assert snapshot.event_count == expected["event_count"]

        # Last event ID
        assert snapshot.last_event_id == expected["last_event_id"]

        # Work packages (exact match)
        assert snapshot.work_packages == expected["work_packages"]

        # Summary counts (exact match)
        assert snapshot.summary == expected["summary"]

    def test_deterministic_byte_identical_output(self):
        """Two independent reduce() calls produce byte-identical JSON
        (excluding materialized_at timestamp)."""
        events = _load_sample_events()

        snapshot1 = reduce(events)
        snapshot2 = reduce(events)

        json1 = materialize_to_json(snapshot1)
        json2 = materialize_to_json(snapshot2)

        # Parse both and compare everything except materialized_at
        data1 = json.loads(json1)
        data2 = json.loads(json2)

        # Remove dynamic fields
        data1.pop("materialized_at")
        data2.pop("materialized_at")

        # Deterministic byte-identical output
        canonical1 = json.dumps(data1, sort_keys=True, indent=2) + "\n"
        canonical2 = json.dumps(data2, sort_keys=True, indent=2) + "\n"
        assert canonical1 == canonical2

    def test_shuffle_order_same_result(self):
        """Events shuffled in a different order still produce the same
        snapshot (reducer sorts by (at, event_id))."""
        events = _load_sample_events()

        # Reverse the events
        reversed_events = list(reversed(events))

        snapshot_normal = reduce(events)
        snapshot_reversed = reduce(reversed_events)

        # Work packages must be identical
        assert snapshot_normal.work_packages == snapshot_reversed.work_packages
        assert snapshot_normal.summary == snapshot_reversed.summary
        assert snapshot_normal.event_count == snapshot_reversed.event_count
        assert snapshot_normal.last_event_id == snapshot_reversed.last_event_id

    def test_fixtures_file_integrity(self):
        """Verify the fixture files are well-formed and consistent."""
        events = _load_sample_events()
        expected = _load_expected_snapshot()

        # All events should have the same mission_slug
        slugs = {e.mission_slug for e in events}
        assert slugs == {"099-parity-test"}
        assert slugs.pop() == expected.get("mission_slug", expected.get("mission_slug"))

        # All event_ids should be unique
        event_ids = [e.event_id for e in events]
        assert len(event_ids) == len(set(event_ids))

        # All timestamps should be ISO 8601
        for event in events:
            assert "T" in event.at
            assert "+" in event.at or "Z" in event.at

    def test_expected_snapshot_covers_all_wps(self):
        """Verify the expected snapshot mentions all WPs from the events."""
        events = _load_sample_events()
        expected = _load_expected_snapshot()

        event_wp_ids = {e.wp_id for e in events}
        snapshot_wp_ids = set(expected["work_packages"].keys())

        assert event_wp_ids == snapshot_wp_ids

    def test_materialize_to_file_matches_expected(self, tmp_path: Path):
        """Write events to disk, materialize, and compare with expected."""
        from specify_cli.status.reducer import materialize
        from tests._support.status_seed import seed_status_event

        events = _load_sample_events()
        expected = _load_expected_snapshot()

        feature_dir = tmp_path / "kitty-specs" / "099-parity-test"
        feature_dir.mkdir(parents=True)

        for event in events:
            seed_status_event(feature_dir, event)

        snapshot = materialize(feature_dir)

        # Compare deterministic fields
        assert snapshot.work_packages == expected["work_packages"]
        assert snapshot.summary == expected["summary"]
        assert snapshot.event_count == expected["event_count"]
        assert snapshot.last_event_id == expected["last_event_id"]
