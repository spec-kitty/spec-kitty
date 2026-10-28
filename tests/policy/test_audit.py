"""Tests for policy audit log."""

import json

import pytest

from kernel.errors import GuardedReadError
from specify_cli.policy.audit import (
    AUDIT_FILENAME,
    PolicyAuditEvent,
    PolicyAuditReadError,
    append_audit_event,
    create_audit_event,
    read_audit_events,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

class TestPolicyAuditEvent:
    def test_create_event(self):
        event = create_audit_event(
            event_type="risk_override",
            mission_slug="010-feat",
            actor="claude",
            reason="Operator approved high-risk parallelization",
            details={"risk_score": 0.8, "threshold": 0.6},
        )
        assert event.event_type == "risk_override"
        assert event.mission_slug == "010-feat"
        assert event.event_id  # ULID generated
        assert event.at  # Timestamp generated

    def test_round_trip_json(self):
        event = create_audit_event(
            event_type="merge_gate_override",
            mission_slug="010-feat",
            actor="robert",
            reason="Manual override",
        )
        line = event.to_json_line()
        restored = PolicyAuditEvent.from_json_line(line)
        assert restored.event_id == event.event_id
        assert restored.event_type == event.event_type
        assert restored.actor == event.actor


class TestAuditPersistence:
    def test_append_and_read(self, tmp_path):
        e1 = create_audit_event("risk_override", "feat", "alice", "reason 1")
        e2 = create_audit_event("merge_gate_override", "feat", "bob", "reason 2")

        append_audit_event(tmp_path, e1)
        append_audit_event(tmp_path, e2)

        events = read_audit_events(tmp_path)
        assert len(events) == 2
        assert events[0].event_type == "risk_override"
        assert events[1].event_type == "merge_gate_override"

    def test_read_empty(self, tmp_path):
        events = read_audit_events(tmp_path)
        assert events == []

    def test_read_missing_file(self, tmp_path):
        events = read_audit_events(tmp_path / "nonexistent")
        assert events == []


class TestGuardedRead:
    """#6588: a malformed line is refused with a named, path- and line-bearing error."""

    def _write(self, feature_dir, *lines):
        good = create_audit_event("risk_override", "feat", "alice", "ok").to_json_line()
        (feature_dir / AUDIT_FILENAME).write_text("\n".join([good, *lines]) + "\n", encoding="utf-8")
        return feature_dir / AUDIT_FILENAME

    def _valid_payload(self):
        return json.loads(create_audit_event("risk_override", "feat", "bob", "why").to_json_line())

    @pytest.mark.parametrize(
        ("mutate", "fragment"),
        [
            (lambda d: d.pop("actor"), "missing field(s): actor"),
            (lambda d: d.update(surplus=1), "unexpected field(s): surplus"),
            (lambda d: d.update(reason=7), "field 'reason' must be a string"),
            (lambda d: d.update(details=[1]), "field 'details' must be an object"),
        ],
    )
    def test_malformed_fields_name_path_and_line(self, tmp_path, mutate, fragment):
        payload = self._valid_payload()
        mutate(payload)
        path = self._write(tmp_path, json.dumps(payload))

        with pytest.raises(PolicyAuditReadError) as excinfo:
            read_audit_events(tmp_path)

        assert excinfo.value.path == str(path)
        assert "line 2" in excinfo.value.reason
        assert fragment in excinfo.value.reason
        assert isinstance(excinfo.value, GuardedReadError)

    @pytest.mark.parametrize("line", ["{not json", "[1, 2]", '"text"', "[" * 100_000])
    def test_malformed_json_names_path_and_line(self, tmp_path, line):
        path = self._write(tmp_path, "", line)

        with pytest.raises(PolicyAuditReadError) as excinfo:
            read_audit_events(tmp_path)

        assert excinfo.value.path == str(path)
        assert "line 3" in excinfo.value.reason

    def test_from_json_line_refuses_missing_field_with_value_error(self):
        payload = self._valid_payload()
        payload.pop("at")

        with pytest.raises(ValueError, match="missing field\\(s\\): at"):
            PolicyAuditEvent.from_json_line(json.dumps(payload))

    def test_non_utf8_file_is_a_guarded_read_error(self, tmp_path):
        (tmp_path / AUDIT_FILENAME).write_bytes(b"\xff\xfe\n")

        with pytest.raises(PolicyAuditReadError):
            read_audit_events(tmp_path)

    def test_line_number_is_the_physical_line_despite_unicode_separators(self, tmp_path):
        payload = self._valid_payload()
        payload["reason"] = "line\u2028separator"
        path = self._write(tmp_path, json.dumps(payload, ensure_ascii=False), "{not json")

        with pytest.raises(PolicyAuditReadError) as excinfo:
            read_audit_events(tmp_path)

        assert excinfo.value.path == str(path)
        assert "line 3" in excinfo.value.reason

