"""Tests for mission_v1 event emission (WP05).

The MissionModel callback-wiring half of this module was retired with the
mission-DSL v1 runtime (mission dead-port-disposition-01M1TZVN); only the
events module survives.

Covers:
- emit_event writes correct JSONL structure
- Read-back produces correct event dicts
- Multiple events produce multiple JSONL lines
- emit_event with feature_dir=None does not write a file
- emit_event with read-only directory logs warning, no exception
- _read_events on non-existent file returns empty list
- _read_events skips corrupt lines gracefully
- Timestamps are ISO 8601 UTC
"""

from __future__ import annotations

import json
import logging
import stat
from kernel.clock import parse_iso
from pathlib import Path

import pytest

from specify_cli.mission_v1.events import (
    MISSION_EVENTS_FILE,
    emit_event,
    _read_events,
)


# ---------------------------------------------------------------------------
# T019 / T020 -- emit_event and JSONL writer
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.unit, pytest.mark.fast]


class TestEmitEvent:
    """Tests for the emit_event function."""

    def test_writes_jsonl_line(self, tmp_path: Path) -> None:
        """emit_event writes a single JSONL line to the feature dir."""
        emit_event("phase_entered", {"state": "plan"}, "test-mission", tmp_path)

        events_file = tmp_path / MISSION_EVENTS_FILE
        assert events_file.exists()

        lines = events_file.read_text().splitlines()
        assert len(lines) == 1

        event = json.loads(lines[0])
        assert event["type"] == "phase_entered"
        assert event["mission"] == "test-mission"
        assert event["payload"] == {"state": "plan"}
        assert "timestamp" in event

    def test_event_structure(self, tmp_path: Path) -> None:
        """Emitted event has exactly the expected keys."""
        emit_event("guard_failed", {"guard": "has_spec"}, "my-mission", tmp_path)

        events = _read_events(tmp_path)
        assert len(events) == 1

        event = events[0]
        assert set(event.keys()) == {"type", "timestamp", "mission", "payload"}
        assert event["type"] == "guard_failed"
        assert event["mission"] == "my-mission"
        assert event["payload"] == {"guard": "has_spec"}

    def test_timestamp_is_iso8601_utc(self, tmp_path: Path) -> None:
        """Timestamp is a valid ISO 8601 string in UTC."""
        emit_event("phase_entered", {"state": "alpha"}, "ts-test", tmp_path)

        events = _read_events(tmp_path)
        ts = events[0]["timestamp"]

        # Must parse as ISO 8601
        parsed = parse_iso(ts)
        # Must be UTC (offset-aware with +00:00)
        assert parsed.tzinfo is not None
        assert parsed.utcoffset().total_seconds() == 0

    def test_multiple_events_append(self, tmp_path: Path) -> None:
        """Multiple emit_event calls produce multiple JSONL lines."""
        emit_event("phase_entered", {"state": "alpha"}, "multi", tmp_path)
        emit_event("phase_exited", {"state": "alpha"}, "multi", tmp_path)
        emit_event("phase_entered", {"state": "beta"}, "multi", tmp_path)

        events = _read_events(tmp_path)
        assert len(events) == 3
        assert events[0]["type"] == "phase_entered"
        assert events[0]["payload"]["state"] == "alpha"
        assert events[1]["type"] == "phase_exited"
        assert events[2]["type"] == "phase_entered"
        assert events[2]["payload"]["state"] == "beta"

    def test_sorted_keys_in_jsonl(self, tmp_path: Path) -> None:
        """JSONL lines have sorted keys for deterministic output."""
        emit_event("phase_entered", {"state": "x"}, "sorted", tmp_path)

        events_file = tmp_path / MISSION_EVENTS_FILE
        raw_line = events_file.read_text().strip()
        parsed = json.loads(raw_line)
        keys = list(parsed.keys())
        assert keys == sorted(keys)

    def test_no_feature_dir_no_file(self, tmp_path: Path) -> None:
        """emit_event with feature_dir=None writes no file."""
        emit_event("phase_entered", {"state": "alpha"}, "test")
        # No file anywhere
        events_file = tmp_path / MISSION_EVENTS_FILE
        assert not events_file.exists()

    def test_readonly_dir_logs_warning_no_exception(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """emit_event on a read-only directory logs a warning but does not raise."""
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()

        # Make directory read-only
        readonly_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)

        try:
            with caplog.at_level(logging.WARNING):
                # This must NOT raise
                emit_event("phase_entered", {"state": "x"}, "test", readonly_dir)

            assert any("Failed to emit event" in r.message for r in caplog.records)
        finally:
            # Restore write permission for cleanup
            readonly_dir.chmod(stat.S_IRWXU)

    def test_default_mission_name_empty(self, tmp_path: Path) -> None:
        """Default mission_name is empty string."""
        emit_event("phase_entered", {"state": "x"}, feature_dir=tmp_path)

        events = _read_events(tmp_path)
        assert events[0]["mission"] == ""


# ---------------------------------------------------------------------------
# T020 -- _read_events
# ---------------------------------------------------------------------------


class TestReadEvents:
    """Tests for the _read_events function."""

    def test_nonexistent_file_returns_empty(self, tmp_path: Path) -> None:
        """_read_events on a directory with no events file returns []."""
        assert _read_events(tmp_path) == []

    def test_empty_file_returns_empty(self, tmp_path: Path) -> None:
        """_read_events on an empty file returns []."""
        (tmp_path / MISSION_EVENTS_FILE).write_text("")
        assert _read_events(tmp_path) == []

    def test_corrupt_line_skipped(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """Corrupt JSONL lines are skipped with a warning, valid lines returned."""
        events_file = tmp_path / MISSION_EVENTS_FILE
        events_file.write_text(
            '{"type":"good","timestamp":"2026-01-01T00:00:00+00:00","mission":"t","payload":{}}\n'
            "NOT VALID JSON\n"
            '{"type":"also_good","timestamp":"2026-01-01T00:00:01+00:00","mission":"t","payload":{}}\n'
        )

        with caplog.at_level(logging.WARNING):
            events = _read_events(tmp_path)

        assert len(events) == 2
        assert events[0]["type"] == "good"
        assert events[1]["type"] == "also_good"
        assert any("Corrupt event line" in r.message for r in caplog.records)

    def test_blank_lines_ignored(self, tmp_path: Path) -> None:
        """Blank lines in the JSONL file are silently skipped."""
        events_file = tmp_path / MISSION_EVENTS_FILE
        events_file.write_text(
            '{"type":"a","timestamp":"2026-01-01T00:00:00+00:00","mission":"t","payload":{}}\n'
            "\n"
            "\n"
            '{"type":"b","timestamp":"2026-01-01T00:00:01+00:00","mission":"t","payload":{}}\n'
        )

        events = _read_events(tmp_path)
        assert len(events) == 2
