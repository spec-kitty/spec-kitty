"""Tests for specify_cli.events.sanitizer.sanitize_event_for_log.

Coverage targets:
  - T004: PII field removal (parametrized per field, nested, mutation check,
          preserved fields)
  - T005: Session timestamp replacement edge cases
"""

from __future__ import annotations

import pytest

from specify_cli.events.sanitizer import sanitize_event_for_log

pytestmark = [pytest.mark.unit, pytest.mark.fast]
# ---------------------------------------------------------------------------
# T004 — PII field removal
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "pii_field",
    [
        "machine_name",
        "hostname",
        "workspace_path",
        "developer_name",
        "developer_email",
    ],
)
def test_pii_field_stripped_top_level(pii_field: str) -> None:
    """Each PII field is removed from a top-level envelope."""
    envelope = {"event_type": "TestEvent", pii_field: "sensitive-value"}
    result = sanitize_event_for_log(envelope)
    assert pii_field not in result
    assert result["event_type"] == "TestEvent"


@pytest.mark.parametrize(
    "pii_field",
    [
        "machine_name",
        "hostname",
        "workspace_path",
        "developer_name",
        "developer_email",
    ],
)
def test_pii_field_stripped_nested(pii_field: str) -> None:
    """Each PII field is removed when nested inside a payload dict."""
    # canonical-producer-exempt: #1198 -- sanitizer unit test must exercise raw envelope input.
    envelope = {
        "event_type": "TestEvent",
        "payload": {pii_field: "sensitive-value", "safe_field": "keep"},
    }
    result = sanitize_event_for_log(envelope)
    assert pii_field not in result["payload"]
    assert result["payload"]["safe_field"] == "keep"


def test_all_pii_fields_stripped_together() -> None:
    """All five PII fields are removed when present simultaneously."""
    envelope = {
        "event_type": "TestEvent",
        "machine_name": "dev-mbp",
        "hostname": "dev-mbp.local",
        "workspace_path": "/Users/tester/project",
        "developer_name": "Test User",
        "developer_email": "tester@example.com",
        "node_id": "keep-this",
    }
    result = sanitize_event_for_log(envelope)
    for pii_field in ("machine_name", "hostname", "workspace_path", "developer_name", "developer_email"):
        assert pii_field not in result
    assert result["node_id"] == "keep-this"
    assert result["event_type"] == "TestEvent"


def test_pii_stripped_from_nested_payload() -> None:
    """PII is removed from nested payload dict; safe fields survive."""
    # canonical-producer-exempt: #1198 -- sanitizer unit test must exercise raw envelope input.
    envelope = {
        "event_type": "E",
        "payload": {"machine_name": "x", "safe_field": "keep"},
    }
    result = sanitize_event_for_log(envelope)
    assert "machine_name" not in result["payload"]
    assert result["payload"]["safe_field"] == "keep"


def test_pii_stripped_from_deeply_nested_dict() -> None:
    """PII is removed at arbitrary nesting depth."""
    envelope = {
        "event_type": "E",
        "outer": {
            "inner": {
                "developer_email": "x@y.com",
                "safe": "present",
            }
        },
    }
    result = sanitize_event_for_log(envelope)
    assert "developer_email" not in result["outer"]["inner"]
    assert result["outer"]["inner"]["safe"] == "present"


def test_pii_stripped_inside_list_of_dicts() -> None:
    """PII fields inside list elements that are dicts are also removed."""
    envelope = {
        "event_type": "E",
        "items": [
            {"machine_name": "bad", "value": "good"},
            {"hostname": "bad2", "other": "ok"},
        ],
    }
    result = sanitize_event_for_log(envelope)
    assert "machine_name" not in result["items"][0]
    assert result["items"][0]["value"] == "good"
    assert "hostname" not in result["items"][1]
    assert result["items"][1]["other"] == "ok"


def test_does_not_mutate_input() -> None:
    """Input dict must not be mutated by the sanitizer."""
    original: dict[str, object] = {
        "machine_name": "x",
        "payload": {"developer_email": "y@z.com"},
    }
    sanitize_event_for_log(original)
    assert original == {
        "machine_name": "x",
        "payload": {"developer_email": "y@z.com"},
    }


def test_non_pii_fields_preserved() -> None:
    """Fields that are explicitly NOT PII are passed through unchanged."""
    # canonical-producer-exempt: #1198 -- sanitizer unit test must exercise raw envelope input.
    preserved_fields = {
        "node_id": "node-abc",
        "build_id": "build-123",
        "mission_id": "01KT119Y",
        "project_uuid": "8a4a7da6-a97c-4bb4-893a-b31664abfee4",
        "git_branch": "main",
        "head_commit_sha": "deadbeef",
        "event_type": "SomeEvent",
        "payload": {"custom_field": "value"},
    }
    result = sanitize_event_for_log(preserved_fields)
    for key, value in preserved_fields.items():
        assert result[key] == value


def test_empty_envelope_returned_unchanged() -> None:
    """Empty envelope returns an empty dict without errors."""
    result = sanitize_event_for_log({})
    assert result == {}


def test_envelope_with_no_pii_unchanged() -> None:
    """Envelope with no PII or timestamp fields is returned structurally identical."""
    # canonical-producer-exempt: #1198 -- sanitizer unit test must exercise raw envelope input.
    envelope = {
        "event_type": "Foo",
        "mission_id": "m1",
        "payload": {"key": "value"},
    }
    result = sanitize_event_for_log(envelope)
    assert result == envelope


def test_list_of_scalars_not_affected() -> None:
    """Lists containing non-dict items are preserved as-is."""
    envelope = {"event_type": "E", "tags": ["a", "b", "c"]}
    result = sanitize_event_for_log(envelope)
    assert result["tags"] == ["a", "b", "c"]


# ---------------------------------------------------------------------------
# T005 — Session timestamp replacement edge cases
# ---------------------------------------------------------------------------


def test_both_timestamps_replaced_with_duration() -> None:
    """Both timestamps present → session_duration_s computed, both originals removed."""
    envelope = {
        "session_started_at": "2026-06-01T07:00:00Z",
        "session_ended_at": "2026-06-01T07:05:30Z",
    }
    result = sanitize_event_for_log(envelope)
    assert "session_started_at" not in result
    assert "session_ended_at" not in result
    assert result["session_duration_s"] == 330  # 5 min 30 s


def test_both_timestamps_with_offset_timezone() -> None:
    """Both timestamps with +00:00 suffix → same computation as Z suffix."""
    envelope = {
        "session_started_at": "2026-06-01T10:00:00+00:00",
        "session_ended_at": "2026-06-01T10:01:00+00:00",
    }
    result = sanitize_event_for_log(envelope)
    assert result["session_duration_s"] == 60


def test_only_started_at_removed_no_replacement() -> None:
    """Only session_started_at → removed, no replacement, no KeyError."""
    envelope = {
        "event_type": "E",
        "session_started_at": "2026-06-01T07:00:00Z",
    }
    result = sanitize_event_for_log(envelope)
    assert "session_started_at" not in result
    assert "session_duration_s" not in result
    assert result["event_type"] == "E"


def test_only_ended_at_removed_no_replacement() -> None:
    """Only session_ended_at → removed, no replacement."""
    envelope = {
        "event_type": "E",
        "session_ended_at": "2026-06-01T07:05:30Z",
    }
    result = sanitize_event_for_log(envelope)
    assert "session_ended_at" not in result
    assert "session_duration_s" not in result
    assert result["event_type"] == "E"


def test_malformed_started_at_removed_no_exception() -> None:
    """Malformed session_started_at → field removed, no exception raised."""
    envelope = {
        "event_type": "E",
        "session_started_at": "not-a-date",
        "session_ended_at": "2026-06-01T07:05:30Z",
    }
    result = sanitize_event_for_log(envelope)
    assert "session_started_at" not in result
    # ended_at is popped too; since started parsed to None, no duration computed
    assert "session_ended_at" not in result
    assert "session_duration_s" not in result


def test_malformed_ended_at_removed_no_exception() -> None:
    """Malformed session_ended_at → field removed, no exception raised."""
    envelope = {
        "event_type": "E",
        "session_started_at": "2026-06-01T07:00:00Z",
        "session_ended_at": "INVALID",
    }
    result = sanitize_event_for_log(envelope)
    assert "session_ended_at" not in result
    assert "session_started_at" not in result
    assert "session_duration_s" not in result


@pytest.mark.parametrize(
    ("started", "ended"),
    [
        ("2026-01-01T10:00:00", "2026-01-01T10:05:00+00:00"),
        ("2026-01-01T10:00:00+00:00", "2026-01-01T10:05:00"),
    ],
    ids=["naive-start-aware-end", "aware-start-naive-end"],
)
def test_mixed_naive_aware_pair_dropped_without_duration(started: str, ended: str) -> None:
    """A naive/aware session pair is malformed: both removed, no duration, no TypeError (#7440)."""
    envelope = {"event_type": "E", "session_started_at": started, "session_ended_at": ended}
    result = sanitize_event_for_log(envelope)
    assert "session_started_at" not in result
    assert "session_ended_at" not in result
    assert "session_duration_s" not in result
    assert result["event_type"] == "E"


@pytest.mark.parametrize(
    ("started", "ended"),
    [
        ("2026-01-01T10:00:00", "2026-01-01T10:05:00"),
        ("2026-01-01T10:00:00+00:00", "2026-01-01T10:05:00+00:00"),
    ],
    ids=["both-naive", "both-aware"],
)
def test_same_kind_pair_still_yields_duration(started: str, ended: str) -> None:
    """Positive control for the mixed-pair case: a consistent pair keeps its duration."""
    result = sanitize_event_for_log({"session_started_at": started, "session_ended_at": ended})
    assert result["session_duration_s"] == 300


def test_neither_timestamp_field_output_unchanged() -> None:
    """Envelope with neither timestamp field is returned unchanged (modulo PII)."""
    envelope = {
        "event_type": "E",
        "node_id": "n1",
    }
    result = sanitize_event_for_log(envelope)
    assert result == {"event_type": "E", "node_id": "n1"}


def test_session_duration_already_present_not_overwritten() -> None:
    """Existing session_duration_s is preserved when no timestamp fields are present."""
    envelope = {
        "event_type": "E",
        "session_duration_s": 999,
    }
    result = sanitize_event_for_log(envelope)
    assert result["session_duration_s"] == 999


def test_pii_and_timestamps_stripped_together() -> None:
    """PII removal and timestamp replacement operate correctly in combination."""
    # canonical-producer-exempt: #1198 -- sanitizer unit test must exercise raw envelope input.
    envelope = {
        "event_type": "DecisionInputRequested",
        "machine_name": "dev-mbp",
        "session_started_at": "2026-06-01T07:00:00Z",
        "session_ended_at": "2026-06-01T07:01:00Z",
        "payload": {
            "workspace_path": "/Users/tester/project",
            "question": "Which strategy?",
        },
    }
    result = sanitize_event_for_log(envelope)
    assert "machine_name" not in result
    assert "session_started_at" not in result
    assert "session_ended_at" not in result
    assert result["session_duration_s"] == 60
    assert "workspace_path" not in result["payload"]
    assert result["payload"]["question"] == "Which strategy?"
    assert result["event_type"] == "DecisionInputRequested"
