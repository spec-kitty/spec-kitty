"""Tests confirming zero PII fields survive the status write paths.

Covers T014 (WP03):
- status/store.py::append_events_atomic() strips PII before writing
- decisions/emit.py::_append_raw_event() strips PII for DecisionPointOpened/Resolved
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_events_atomic

pytestmark = [pytest.mark.unit, pytest.mark.fast]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PII_FIELDS = [
    "machine_name",
    "hostname",
    "workspace_path",
    "developer_name",
    "developer_email",
    "session_started_at",
]

NON_PII_FIELDS = [
    "event_id",
    "mission_slug",
    "wp_id",
    "at",
    "actor",
    "from_lane",
    "to_lane",
    "force",
    "execution_mode",
]

_BASE_ULID = "01HXYZ0123456789ABCDEFGHJK"
_MISSION_SLUG = "test-mission"


def _make_event(
    event_id: str = _BASE_ULID,
    mission_slug: str = _MISSION_SLUG,
) -> StatusEvent:
    """Build a minimal StatusEvent (model has no PII fields currently)."""
    return StatusEvent(
        event_id=event_id,
        mission_slug=mission_slug,
        wp_id="WP01",
        from_lane=Lane.PLANNED,
        to_lane=Lane.CLAIMED,
        at="2026-06-01T10:00:00Z",
        actor="claude",
        force=False,
        execution_mode="worktree",
    )


def _read_written_lines(feature_dir: Path) -> list[dict]:
    """Read all JSON lines from status.events.jsonl in feature_dir."""
    events_path = feature_dir / "status.events.jsonl"
    if not events_path.exists():
        return []
    lines = []
    for raw in events_path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if stripped:
            lines.append(json.loads(stripped))
    return lines


def _all_keys_recursive(obj: object) -> set[str]:
    """Collect all dict keys at every nesting level."""
    keys: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.add(k)
            keys.update(_all_keys_recursive(v))
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            keys.update(_all_keys_recursive(item))
    return keys


# ---------------------------------------------------------------------------
# T014a — the single-event append path strips PII (append_events_atomic)
#
# Strategy: patch sanitize_event_for_log inside the store module to inject
# PII into the dict it receives, then assert the PII is gone from the file.
# This verifies that the sanitizer call is wired in and runs before serialization.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("pii_field", PII_FIELDS)
def test_pii_absent_from_status_events_jsonl(
    tmp_path: Path,
    pii_field: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PII field absent from written line: sanitizer is called before serialization."""
    import specify_cli.status.store as store_module
    from specify_cli.events import sanitize_event_for_log

    # Intercept: inject PII into the dict that reaches sanitize_event_for_log,
    # then delegate to the real sanitizer. The output must not contain the PII field.
    def injecting_sanitizer(d: dict) -> dict:
        d_with_pii = {**d, pii_field: "sensitive-value"}
        return sanitize_event_for_log(d_with_pii)

    monkeypatch.setattr(store_module, "sanitize_event_for_log", injecting_sanitizer)

    event = _make_event()
    append_events_atomic(tmp_path, [event])

    lines = _read_written_lines(tmp_path)
    assert len(lines) == 1, "Expected exactly one line written"
    all_keys = _all_keys_recursive(lines[0])
    assert pii_field not in all_keys, (
        f"PII field {pii_field!r} must not appear in written event; found keys: {all_keys}"
    )


@pytest.mark.parametrize("non_pii_field", NON_PII_FIELDS)
def test_non_pii_fields_preserved_in_status_events_jsonl(
    tmp_path: Path,
    non_pii_field: str,
) -> None:
    """Non-PII fields are preserved in written output."""
    event = _make_event()
    append_events_atomic(tmp_path, [event])

    lines = _read_written_lines(tmp_path)
    assert len(lines) == 1
    assert non_pii_field in lines[0], (
        f"Non-PII field {non_pii_field!r} must be preserved; got keys: {set(lines[0].keys())}"
    )


# ---------------------------------------------------------------------------
# T014b — append_events_atomic() strips PII
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("pii_field", PII_FIELDS)
def test_pii_absent_from_atomic_batch_write(
    tmp_path: Path,
    pii_field: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PII field absent from written lines in atomic batch write."""
    import specify_cli.status.store as store_module
    from specify_cli.events import sanitize_event_for_log

    def injecting_sanitizer(d: dict) -> dict:
        d_with_pii = {**d, pii_field: "sensitive-value"}
        return sanitize_event_for_log(d_with_pii)

    monkeypatch.setattr(store_module, "sanitize_event_for_log", injecting_sanitizer)

    event1 = _make_event(event_id="01HXYZ0123456789ABCDEFGHJK")
    event2 = _make_event(event_id="01HXYZ0123456789ABCDEFGHJM", mission_slug="test-mission-2")

    append_events_atomic(tmp_path, [event1, event2])

    lines = _read_written_lines(tmp_path)
    assert len(lines) == 2, "Expected two lines written"
    for line in lines:
        all_keys = _all_keys_recursive(line)
        assert pii_field not in all_keys, (
            f"PII field {pii_field!r} must not appear in any written event; found keys: {all_keys}"
        )


# ---------------------------------------------------------------------------
# T014c — decisions/emit.py _append_raw_event() strips PII
# ---------------------------------------------------------------------------

# The five direct-removal PII fields are stripped recursively at every level.
# session_started_at/session_ended_at are replaced at the TOP-LEVEL envelope only
# (not inside nested payload dicts) — this is by design in sanitize_event_for_log.
_RECURSIVE_PII_FIELDS = [f for f in PII_FIELDS if f != "session_started_at"]
_TOP_LEVEL_PII_FIELDS = PII_FIELDS  # all six fields are stripped from the top level


@pytest.mark.parametrize("pii_field", _TOP_LEVEL_PII_FIELDS)
def test_pii_absent_from_decision_point_opened_event_top_level(
    tmp_path: Path,
    pii_field: str,
) -> None:
    """Top-level PII fields must not appear in written DecisionPointOpened events."""
    from specify_cli.decisions.emit import _append_raw_event

    events_path = tmp_path / "status.events.jsonl"
    # canonical-producer-exempt: #1198 -- sanitizer regression test injects top-level PII into raw event envelope.
    event_dict: dict = {
        "event_id": "01HXYZ0123456789ABCDEFGHJK",
        "at": "2026-06-01T10:00:00+00:00",
        "event_type": "DecisionPointOpened",
        "payload": {
            "decision_point_id": "01HXYZ0123456789ABCDEFGHJK",
            "question": "Which auth strategy?",
        },
        pii_field: "sensitive-top-level-value",
    }

    _append_raw_event(events_path, event_dict)

    lines = _read_written_lines(tmp_path)
    assert len(lines) == 1
    # Only check top-level keys for this test
    assert pii_field not in lines[0], (
        f"PII field {pii_field!r} must not appear at top level in written DecisionPointOpened event; "
        f"found keys: {set(lines[0].keys())}"
    )


@pytest.mark.parametrize("pii_field", _RECURSIVE_PII_FIELDS)
def test_pii_absent_from_decision_point_opened_event_nested(
    tmp_path: Path,
    pii_field: str,
) -> None:
    """Nested PII fields (excluding session timestamps) must not appear anywhere."""
    from specify_cli.decisions.emit import _append_raw_event

    events_path = tmp_path / "status.events.jsonl"
    # canonical-producer-exempt: #1198 -- sanitizer regression test injects nested PII into raw event envelope.
    event_dict: dict = {
        "event_id": "01HXYZ0123456789ABCDEFGHJK",
        "at": "2026-06-01T10:00:00+00:00",
        "event_type": "DecisionPointOpened",
        "payload": {
            "decision_point_id": "01HXYZ0123456789ABCDEFGHJK",
            "question": "Which auth strategy?",
            pii_field: "sensitive-payload-value",
        },
        pii_field: "sensitive-top-level-value",
    }

    _append_raw_event(events_path, event_dict)

    lines = _read_written_lines(tmp_path)
    assert len(lines) == 1
    all_keys = _all_keys_recursive(lines[0])
    assert pii_field not in all_keys, (
        f"PII field {pii_field!r} must not appear in written DecisionPointOpened event; "
        f"found keys: {all_keys}"
    )


@pytest.mark.parametrize("pii_field", _RECURSIVE_PII_FIELDS)
def test_pii_absent_from_decision_point_resolved_event(
    tmp_path: Path,
    pii_field: str,
) -> None:
    """PII fields absent from DecisionPointResolved event at all nesting levels."""
    from specify_cli.decisions.emit import _append_raw_event

    events_path = tmp_path / "status.events.jsonl"
    # canonical-producer-exempt: #1198 -- sanitizer regression test injects nested PII into raw event envelope.
    event_dict: dict = {
        "event_id": "01HXYZ0123456789ABCDEFGHJM",
        "at": "2026-06-01T10:01:00+00:00",
        "event_type": "DecisionPointResolved",
        "payload": {
            "decision_point_id": "01HXYZ0123456789ABCDEFGHJK",
            "terminal_outcome": "resolved",
            "final_answer": "oauth2",
            pii_field: "sensitive-payload-value",
        },
        pii_field: "sensitive-top-level-value",
    }

    _append_raw_event(events_path, event_dict)

    lines = _read_written_lines(tmp_path)
    assert len(lines) == 1
    all_keys = _all_keys_recursive(lines[0])
    assert pii_field not in all_keys, (
        f"PII field {pii_field!r} must not appear in written DecisionPointResolved event; "
        f"found keys: {all_keys}"
    )


def test_non_pii_fields_preserved_in_decision_event(tmp_path: Path) -> None:
    """Non-PII fields in decision events are preserved after sanitization."""
    from specify_cli.decisions.emit import _append_raw_event

    events_path = tmp_path / "status.events.jsonl"
    # canonical-producer-exempt: #1198 -- sanitizer regression test asserts raw decision envelope preservation.
    event_dict = {
        "event_id": "01HXYZ0123456789ABCDEFGHJK",
        "at": "2026-06-01T10:00:00+00:00",
        "event_type": "DecisionPointOpened",
        "payload": {
            "decision_point_id": "01HXYZ0123456789ABCDEFGHJK",
            "mission_id": "01KPWT8PNY8683QX3WBW6VXYM7",
            "question": "Which auth strategy?",
        },
    }

    _append_raw_event(events_path, event_dict)

    lines = _read_written_lines(tmp_path)
    assert len(lines) == 1
    written = lines[0]
    assert written["event_id"] == "01HXYZ0123456789ABCDEFGHJK"
    assert written["event_type"] == "DecisionPointOpened"
    assert written["payload"]["question"] == "Which auth strategy?"
    assert written["payload"]["mission_id"] == "01KPWT8PNY8683QX3WBW6VXYM7"


def test_lamport_proxy_returned_by_append_raw_event(tmp_path: Path) -> None:
    """_append_raw_event returns the 1-based line count (Lamport proxy)."""
    from specify_cli.decisions.emit import _append_raw_event

    events_path = tmp_path / "status.events.jsonl"
    count1 = _append_raw_event(events_path, {"event_id": "A", "event_type": "X"})
    count2 = _append_raw_event(events_path, {"event_id": "B", "event_type": "Y"})

    assert count1 == 1
    assert count2 == 2


def test_sanitizer_is_called_in_append_events_atomic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify sanitize_event_for_log is actually called during append_events_atomic."""
    import specify_cli.status.store as store_module

    call_count = {"n": 0}
    real_sanitizer = store_module.sanitize_event_for_log

    def tracking_sanitizer(d: dict) -> dict:
        call_count["n"] += 1
        return real_sanitizer(d)

    monkeypatch.setattr(store_module, "sanitize_event_for_log", tracking_sanitizer)

    events = [
        _make_event(event_id="01HXYZ0123456789ABCDEFGHJK"),
        _make_event(event_id="01HXYZ0123456789ABCDEFGHJM"),
    ]
    append_events_atomic(tmp_path, events)

    assert call_count["n"] == 2, (
        f"sanitize_event_for_log must be called once per event; called {call_count['n']} times"
    )


def test_sanitizer_is_called_in_append_raw_event(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify sanitize_event_for_log runs exactly once for a decisions _append_raw_event row.

    Since fsm-write-path-integrity WP07 the decision row lands through the
    store's ``append_raw_rows_atomic`` (under the mission lock), which is where
    the sanitizer call lives now -- ``decisions/emit.py`` no longer calls it
    itself, so the tracker patches the store module.
    """
    import specify_cli.status.store as store_module
    from specify_cli.decisions.emit import _append_raw_event

    call_count = {"n": 0}
    real_sanitizer = store_module.sanitize_event_for_log

    def tracking_sanitizer(d: dict) -> dict:
        call_count["n"] += 1
        return real_sanitizer(d)

    monkeypatch.setattr(store_module, "sanitize_event_for_log", tracking_sanitizer)

    events_path = tmp_path / "status.events.jsonl"
    _append_raw_event(events_path, {"event_id": "A", "event_type": "X"})

    assert call_count["n"] == 1, "sanitize_event_for_log must be called once per _append_raw_event"
