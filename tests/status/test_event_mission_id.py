"""Contract tests for status event mission_id migration (WP05 T027 + T028).

FR-023: New events carry mission_id (ULID) as canonical machine identity.
FR-053: Reader tolerates legacy event logs that carry only mission_slug.

Test scenarios:
    T027 — Back-compat read:
        Fixture 1: Legacy event log (aggregate identity = mission_slug only)
        Fixture 2: New-format event log (mission_id ULID)
        Fixture 3: Mixed log (both shapes interleaved)
        All three must reduce to equivalent state via the public reader API.

    T028 — Round-trip: emit → read → assert aggregate_id == meta.json.mission_id
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from specify_cli.status.emit import emit_status_transition
from specify_cli.status.models import Lane, StatusEvent, TransitionRequest, ULID_PATTERN
from specify_cli.status.store import EVENTS_FILENAME, read_events

pytestmark = pytest.mark.fast

# ---------------------------------------------------------------------------
# Helpers / shared constants
# ---------------------------------------------------------------------------

_MISSION_SLUG = "083-mission-id-canonical-identity-migration"
_MISSION_ID = "01KNXQS9ATWWFXS3K5ZJ9E5008"  # example ULID (26 chars, valid Crockford base32)
_META_JSON = {
    "mission_id": _MISSION_ID,
    "mission_slug": _MISSION_SLUG,
    "mission_number": 83,
    "mission_type": "software-dev",
}

_LEGACY_EVENT: dict[str, Any] = {
    "actor": "claude",
    "at": "2026-01-01T00:00:00+00:00",
    "event_id": "01JXXXXXXXXXXXXXXXXXXXXXXXXX",
    "evidence": None,
    "execution_mode": "worktree",
    "force": False,
    "from_lane": "planned",
    "mission_slug": _MISSION_SLUG,
    "policy_metadata": None,
    "reason": None,
    "review_ref": None,
    "to_lane": "claimed",
    "wp_id": "WP01",
}

_NEW_FORMAT_EVENT: dict[str, Any] = {
    "actor": "claude",
    "at": "2026-01-01T00:00:00+00:00",
    "event_id": "01JXXXXXXXXXXXXXXXXXXXXXXXXX",
    "evidence": None,
    "execution_mode": "worktree",
    "force": False,
    "from_lane": "planned",
    "mission_id": _MISSION_ID,
    "mission_slug": _MISSION_SLUG,
    "policy_metadata": None,
    "reason": None,
    "review_ref": None,
    "to_lane": "claimed",
    "wp_id": "WP01",
}


def _write_events(events_path: Path, events: list[dict[str, Any]]) -> None:
    """Write a list of event dicts to a JSONL file."""
    events_path.parent.mkdir(parents=True, exist_ok=True)
    with events_path.open("w", encoding="utf-8") as fh:
        for event in events:
            fh.write(json.dumps(event, sort_keys=True) + "\n")


from tests.status.conftest import seed_wp_to_planned as _seed_planned


def _make_feature_dir(tmp_path: Path, slug: str = _MISSION_SLUG, with_meta: bool = True) -> Path:
    """Create a minimal feature directory under kitty-specs/<slug>/."""
    kitty_specs = tmp_path / "kitty-specs"
    feature_dir = kitty_specs / slug
    feature_dir.mkdir(parents=True)
    if with_meta:
        meta_path = feature_dir / "meta.json"
        meta_path.write_text(json.dumps(_META_JSON, indent=2), encoding="utf-8")
    return feature_dir


# ---------------------------------------------------------------------------
# T027 — Fixture 1: Legacy event log (mission_slug only)
# ---------------------------------------------------------------------------


class TestLegacyEventRead:
    """Fixture 1: events on disk carry only mission_slug (pre-WP05 format)."""

    def test_read_events_returns_list(self, tmp_path: Path) -> None:
        feature_dir = _make_feature_dir(tmp_path)
        events_path = feature_dir / EVENTS_FILENAME
        _write_events(events_path, [_LEGACY_EVENT])

        events = read_events(feature_dir)
        assert len(events) == 1

    def test_legacy_event_has_correct_mission_slug(self, tmp_path: Path) -> None:
        feature_dir = _make_feature_dir(tmp_path)
        events_path = feature_dir / EVENTS_FILENAME
        _write_events(events_path, [_LEGACY_EVENT])

        events = read_events(feature_dir)
        assert events[0].mission_slug == _MISSION_SLUG

    def test_legacy_event_resolves_mission_id_from_meta(self, tmp_path: Path) -> None:
        """Reader must resolve mission_id from meta.json for legacy events."""
        feature_dir = _make_feature_dir(tmp_path)
        events_path = feature_dir / EVENTS_FILENAME
        _write_events(events_path, [_LEGACY_EVENT])

        events = read_events(feature_dir)
        assert events[0].mission_id == _MISSION_ID

    def test_legacy_event_mission_id_is_ulid(self, tmp_path: Path) -> None:
        """Resolved mission_id must match ULID pattern."""
        feature_dir = _make_feature_dir(tmp_path)
        events_path = feature_dir / EVENTS_FILENAME
        _write_events(events_path, [_LEGACY_EVENT])

        events = read_events(feature_dir)
        assert events[0].mission_id is not None
        assert ULID_PATTERN.match(events[0].mission_id), (
            f"Expected ULID, got {events[0].mission_id!r}"
        )

    def test_legacy_event_missing_meta_yields_none_mission_id(self, tmp_path: Path) -> None:
        """When meta.json is absent, mission_id should be None (not an error)."""
        feature_dir = _make_feature_dir(tmp_path, with_meta=False)
        events_path = feature_dir / EVENTS_FILENAME
        _write_events(events_path, [_LEGACY_EVENT])

        events = read_events(feature_dir)
        assert events[0].mission_id is None

    def test_legacy_event_correct_lane_state(self, tmp_path: Path) -> None:
        """Reducer state derived from legacy events must be correct."""
        from specify_cli.status.reducer import reduce

        feature_dir = _make_feature_dir(tmp_path)
        events_path = feature_dir / EVENTS_FILENAME
        _write_events(events_path, [_LEGACY_EVENT])

        events = read_events(feature_dir)
        snapshot = reduce(events)
        assert snapshot.work_packages["WP01"]["lane"] == "claimed"


# ---------------------------------------------------------------------------
# T027 — Fixture 2: New-format event log (mission_id ULID)
# ---------------------------------------------------------------------------


class TestNewFormatEventRead:
    """Fixture 2: events carry mission_id (post-WP05 format, drift window closed)."""

    def test_new_format_event_has_mission_id(self, tmp_path: Path) -> None:
        feature_dir = _make_feature_dir(tmp_path)
        events_path = feature_dir / EVENTS_FILENAME
        _write_events(events_path, [_NEW_FORMAT_EVENT])

        events = read_events(feature_dir)
        assert events[0].mission_id == _MISSION_ID

    def test_new_format_event_has_correct_mission_slug(self, tmp_path: Path) -> None:
        feature_dir = _make_feature_dir(tmp_path)
        events_path = feature_dir / EVENTS_FILENAME
        _write_events(events_path, [_NEW_FORMAT_EVENT])

        events = read_events(feature_dir)
        assert events[0].mission_slug == _MISSION_SLUG

    def test_new_format_event_mission_id_is_ulid(self, tmp_path: Path) -> None:
        feature_dir = _make_feature_dir(tmp_path)
        events_path = feature_dir / EVENTS_FILENAME
        _write_events(events_path, [_NEW_FORMAT_EVENT])

        events = read_events(feature_dir)
        assert events[0].mission_id is not None
        assert ULID_PATTERN.match(events[0].mission_id)

    def test_new_format_event_lane_state_equivalent(self, tmp_path: Path) -> None:
        """State derived from new-format events must equal state from legacy events."""
        from specify_cli.status.reducer import reduce

        feature_dir = _make_feature_dir(tmp_path)
        events_path = feature_dir / EVENTS_FILENAME
        _write_events(events_path, [_NEW_FORMAT_EVENT])

        events = read_events(feature_dir)
        snapshot = reduce(events)
        assert snapshot.work_packages["WP01"]["lane"] == "claimed"


# ---------------------------------------------------------------------------
# T027 — Fixture 3: Mixed log (both shapes interleaved)
# ---------------------------------------------------------------------------


class TestMixedEventLogRead:
    """Fixture 3: event log contains both legacy and new-format events."""

    @pytest.fixture
    def mixed_events(self) -> list[dict[str, Any]]:
        legacy = {**_LEGACY_EVENT, "event_id": "01JXXXXXXXXXXXXXXXXXAAAAAAAA", "wp_id": "WP01", "to_lane": "claimed"}
        new_format = {
            **_NEW_FORMAT_EVENT,
            "event_id": "01JXXXXXXXXXXXXXXXXXBBBBBBBB",
            "wp_id": "WP02",
            "from_lane": "planned",
            "to_lane": "claimed",
        }
        return [legacy, new_format]

    def test_mixed_log_read_count(self, tmp_path: Path, mixed_events: list[dict[str, Any]]) -> None:
        feature_dir = _make_feature_dir(tmp_path)
        events_path = feature_dir / EVENTS_FILENAME
        _write_events(events_path, mixed_events)

        events = read_events(feature_dir)
        assert len(events) == 2

    def test_mixed_log_all_have_mission_id(self, tmp_path: Path, mixed_events: list[dict[str, Any]]) -> None:
        """All events in a mixed log must resolve to a mission_id."""
        feature_dir = _make_feature_dir(tmp_path)
        events_path = feature_dir / EVENTS_FILENAME
        _write_events(events_path, mixed_events)

        events = read_events(feature_dir)
        for event in events:
            assert event.mission_id == _MISSION_ID, (
                f"Expected mission_id={_MISSION_ID!r} for {event.wp_id}, got {event.mission_id!r}"
            )

    def test_mixed_log_all_have_correct_slug(self, tmp_path: Path, mixed_events: list[dict[str, Any]]) -> None:
        feature_dir = _make_feature_dir(tmp_path)
        events_path = feature_dir / EVENTS_FILENAME
        _write_events(events_path, mixed_events)

        events = read_events(feature_dir)
        for event in events:
            assert event.mission_slug == _MISSION_SLUG

    def test_mixed_log_reducer_produces_coherent_state(
        self, tmp_path: Path, mixed_events: list[dict[str, Any]]
    ) -> None:
        """Mixed log must reduce to the same lane state for both WPs."""
        from specify_cli.status.reducer import reduce

        feature_dir = _make_feature_dir(tmp_path)
        events_path = feature_dir / EVENTS_FILENAME
        _write_events(events_path, mixed_events)

        events = read_events(feature_dir)
        snapshot = reduce(events)
        assert snapshot.work_packages["WP01"]["lane"] == "claimed"
        assert snapshot.work_packages["WP02"]["lane"] == "claimed"

    def test_legacy_and_new_format_produce_equivalent_state(self, tmp_path: Path) -> None:
        """Fixture 1 and Fixture 2 must produce equivalent snapshot state."""
        from specify_cli.status.reducer import reduce

        # Fixture 1: legacy only
        feature_dir_legacy = _make_feature_dir(tmp_path / "legacy")
        _write_events(feature_dir_legacy / EVENTS_FILENAME, [_LEGACY_EVENT])
        legacy_snapshot = reduce(read_events(feature_dir_legacy))

        # Fixture 2: new format only
        feature_dir_new = _make_feature_dir(tmp_path / "new")
        _write_events(feature_dir_new / EVENTS_FILENAME, [_NEW_FORMAT_EVENT])
        new_snapshot = reduce(read_events(feature_dir_new))

        # Same WP state for WP01
        assert legacy_snapshot.work_packages["WP01"]["lane"] == new_snapshot.work_packages["WP01"]["lane"]


# ---------------------------------------------------------------------------
# T027 — New event serialization: to_dict includes mission_id (no legacy_aggregate_id)
# ---------------------------------------------------------------------------


class TestNewEventSerialization:
    """Verify the on-disk shape for new events (mission_id present)."""

    def test_to_dict_includes_mission_id(self) -> None:
        event = StatusEvent(
            event_id="01KNXQS9ATWWFXS3K5ZJ9E5001",
            mission_slug=_MISSION_SLUG,
            mission_id=_MISSION_ID,
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
            at="2026-01-01T00:00:00+00:00",
            actor="claude",
            force=False,
            execution_mode="worktree",
        )
        d = event.to_dict()
        assert d["mission_id"] == _MISSION_ID

    def test_to_dict_omits_legacy_aggregate_id_after_drift_window_closure(self) -> None:
        """After drift-window closure, legacy_aggregate_id must not appear in new events."""
        event = StatusEvent(
            event_id="01KNXQS9ATWWFXS3K5ZJ9E5001",
            mission_slug=_MISSION_SLUG,
            mission_id=_MISSION_ID,
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
            at="2026-01-01T00:00:00+00:00",
            actor="claude",
            force=False,
            execution_mode="worktree",
        )
        d = event.to_dict()
        assert "legacy_aggregate_id" not in d
        assert d["mission_id"] == _MISSION_ID

    def test_to_dict_omits_legacy_aggregate_id_for_legacy_events(self) -> None:
        """Events without mission_id must not carry legacy_aggregate_id."""
        event = StatusEvent(
            event_id="01KNXQS9ATWWFXS3K5ZJ9E5002",
            mission_slug=_MISSION_SLUG,
            mission_id=None,  # legacy: no mission_id
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
            at="2026-01-01T00:00:00+00:00",
            actor="claude",
            force=False,
            execution_mode="worktree",
        )
        d = event.to_dict()
        assert "mission_id" not in d
        assert "legacy_aggregate_id" not in d


# ---------------------------------------------------------------------------
# T028 — Round-trip: emit → read → assert aggregate_id == meta.json.mission_id
# ---------------------------------------------------------------------------


class TestRoundTripMissionId:
    """T028: emit a new event, read it back, confirm mission_id matches meta.json."""

    @pytest.fixture
    def feature_dir_with_meta(self, tmp_path: Path) -> Path:
        """Feature directory with meta.json containing mission_id, WP01 seeded to planned."""
        feature_dir = _make_feature_dir(tmp_path)
        _seed_planned(feature_dir, "WP01", slug=_MISSION_SLUG)
        return feature_dir

    def test_emitted_event_carries_mission_id_from_meta(
        self, feature_dir_with_meta: Path
    ) -> None:
        """New events emitted by the pipeline must have mission_id == meta.json.mission_id."""
        feature_dir = feature_dir_with_meta

        with patch("specify_cli.status.emit._status_fan_out"):
            emit_status_transition(TransitionRequest(
                feature_dir=feature_dir,
                mission_slug=_MISSION_SLUG,
                wp_id="WP01",
                to_lane="claimed",
                actor="claude",
            ))

        events = read_events(feature_dir)
        # Filter to the WP01 claimed transition (bootstrap may already exist)
        claimed_events = [e for e in events if e.wp_id == "WP01" and str(e.to_lane) == "claimed"]
        assert claimed_events, "Expected at least one claimed event for WP01"

        event = claimed_events[-1]
        assert event.mission_id == _MISSION_ID, (
            f"Expected mission_id={_MISSION_ID!r}, got {event.mission_id!r}"
        )

    def test_emitted_event_aggregate_id_is_ulid(self, feature_dir_with_meta: Path) -> None:
        """T028: aggregate identity of new events (mission_id) must be a valid ULID."""
        feature_dir = feature_dir_with_meta

        with patch("specify_cli.status.emit._status_fan_out"):
            emit_status_transition(TransitionRequest(
                feature_dir=feature_dir,
                mission_slug=_MISSION_SLUG,
                wp_id="WP01",
                to_lane="claimed",
                actor="claude",
            ))

        events = read_events(feature_dir)
        claimed_events = [e for e in events if e.wp_id == "WP01" and str(e.to_lane) == "claimed"]
        assert claimed_events

        event = claimed_events[-1]
        assert event.mission_id is not None
        assert ULID_PATTERN.match(event.mission_id), (
            f"mission_id {event.mission_id!r} does not match ULID pattern"
        )

    def test_emitted_event_omits_legacy_aggregate_id(
        self, feature_dir_with_meta: Path
    ) -> None:
        """On-disk event must not carry legacy_aggregate_id after drift-window closure."""
        import json as _json

        feature_dir = feature_dir_with_meta

        with patch("specify_cli.status.emit._status_fan_out"):
            emit_status_transition(TransitionRequest(
                feature_dir=feature_dir,
                mission_slug=_MISSION_SLUG,
                wp_id="WP01",
                to_lane="claimed",
                actor="claude",
            ))

        events_path = feature_dir / EVENTS_FILENAME
        raw_lines = events_path.read_text(encoding="utf-8").strip().splitlines()
        # Find the claimed event for WP01
        claimed_raw = [
            _json.loads(line)
            for line in raw_lines
            if _json.loads(line).get("wp_id") == "WP01"
            and _json.loads(line).get("to_lane") == "claimed"
        ]
        assert claimed_raw, "Expected at least one claimed event for WP01 in JSONL"

        raw_event = claimed_raw[-1]
        assert "legacy_aggregate_id" not in raw_event

    def test_emitted_event_mission_id_matches_meta_json(
        self, feature_dir_with_meta: Path
    ) -> None:
        """T028: Complete round-trip verification — emitted mission_id == meta.json.mission_id."""
        import json as _json

        feature_dir = feature_dir_with_meta

        # Verify meta.json value
        meta = _json.loads((feature_dir / "meta.json").read_text())
        expected_mission_id = meta["mission_id"]
        expected_slug = meta["mission_slug"]

        with patch("specify_cli.status.emit._status_fan_out"):
            emit_status_transition(TransitionRequest(
                feature_dir=feature_dir,
                mission_slug=_MISSION_SLUG,
                wp_id="WP01",
                to_lane="claimed",
                actor="claude",
            ))

        events = read_events(feature_dir)
        claimed_events = [e for e in events if e.wp_id == "WP01" and str(e.to_lane) == "claimed"]
        assert claimed_events

        event = claimed_events[-1]
        # Primary assertion: aggregate identity matches meta.json
        assert event.mission_id == expected_mission_id
        # Slug consistency: mission_slug field still matches
        assert event.mission_slug == expected_slug

    def test_round_trip_no_mission_id_in_meta_yields_none(self, tmp_path: Path) -> None:
        """Legacy mission without mission_id in meta.json: emitted event has mission_id=None."""
        feature_dir = _make_feature_dir(tmp_path, with_meta=True)
        # Overwrite meta.json without mission_id
        meta_without_id = {
            "mission_slug": _MISSION_SLUG,
            "mission_number": 83,
            "mission_type": "software-dev",
        }
        (feature_dir / "meta.json").write_text(json.dumps(meta_without_id), encoding="utf-8")
        _seed_planned(feature_dir, "WP01", slug=_MISSION_SLUG)

        with patch("specify_cli.status.emit._status_fan_out"):
            emit_status_transition(TransitionRequest(
                feature_dir=feature_dir,
                mission_slug=_MISSION_SLUG,
                wp_id="WP01",
                to_lane="claimed",
                actor="claude",
            ))

        events = read_events(feature_dir)
        claimed_events = [e for e in events if e.wp_id == "WP01" and str(e.to_lane) == "claimed"]
        assert claimed_events

        event = claimed_events[-1]
        assert event.mission_id is None
