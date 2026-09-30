"""Tests for lifecycle_events.py (WP03 — T015) and summary classifier (T017).

Covers:
- T015: Three canonical event types + emit helpers.
- T017: classify_mission_record — four states.

FR-016: No env-var mutation in this test file.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.retrospective.lifecycle_events import (
    Actor,
    RetrospectiveCaptured,
    RetrospectiveCaptureFailed,
    RetrospectiveSkipped,
    emit_captured,
    emit_capture_failed,
    emit_skipped,
)
from specify_cli.retrospective.schema import (
    GenActor,
    GenEvidenceRef,
    GenFinding,
    GenProposal,
    GenProvenance,
    GenRetrospectiveRecord,
    RecordValidationError,
)
from specify_cli.retrospective.summary import classify_mission_record

pytestmark = [pytest.mark.unit, pytest.mark.fast]

# ---------------------------------------------------------------------------
# Test fixture helpers
# ---------------------------------------------------------------------------

MISSION_ID = "01KS049J4V9CSWBKJHTY2FB69H"
MISSION_SLUG = "test-lifecycle-events-01KS049J"

_RUNTIME_ACTOR = Actor(kind="runtime", id="spec-kitty-cli@3.2.0", display="spec-kitty runtime")
_HUMAN_ACTOR = Actor(kind="human", id="robert@spec-kitty.ai", display="Robert Douglass")

_POLICY_SOURCE = {
    "enabled": "<default>",
    "timing": "<default>",
    "failure_policy": "<default>",
}

_STRICT_POLICY_SOURCE = {
    "enabled": ".kittify/charter/charter.md:retrospective.enabled",
    "timing": ".kittify/charter/charter.md:retrospective.timing",
    "failure_policy": ".kittify/charter/charter.md:retrospective.failure_policy",
}


def make_gen_record(
    *,
    findings_status: str = "ran_no_findings",
    provenance_kind: str = "runtime_post_completion",
    helped: list[GenFinding] | None = None,
    proposals: list[GenProposal] | None = None,
    evidence_refs: list[GenEvidenceRef] | None = None,
) -> GenRetrospectiveRecord:
    """Build a minimal valid GenRetrospectiveRecord for event emission tests."""
    return GenRetrospectiveRecord(
        schema_version=1,
        mission_id=MISSION_ID,
        mission_slug=MISSION_SLUG,
        mission_number=None,
        friendly_name="Test Lifecycle Events Mission",
        mission_type="software-dev",
        target_branch="main",
        created_at="2026-05-19T10:00:00+00:00",
        created_by=GenActor(kind="runtime", id="spec-kitty-cli@3.2.0"),
        provenance=GenProvenance(
            kind=provenance_kind,
            invoked_at="2026-05-19T10:00:00+00:00",
            policy_resolved_from=_POLICY_SOURCE,
        ),
        policy_source=dict(_POLICY_SOURCE),
        findings_status=findings_status,
        helped=helped or [],
        not_helpful=[],
        gaps=[],
        proposals=proposals or [],
        evidence_refs=evidence_refs or [],
        generator_version="1.0",
    )


def _read_events(feature_dir: Path) -> list[dict]:
    """Read all lines from status.events.jsonl as dicts."""
    events_path = feature_dir / "status.events.jsonl"
    if not events_path.exists():
        return []
    result = []
    for line in events_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            result.append(json.loads(line))
    return result


# ---------------------------------------------------------------------------
# T015: Event types — dataclass shape
# ---------------------------------------------------------------------------


class TestEventTypeShapes:
    def test_retrospective_captured_to_dict(self) -> None:
        """RetrospectiveCaptured.to_dict() produces the correct envelope shape."""
        event = RetrospectiveCaptured(
            event_id="01KS049J4V9CSWBKJHTY2FB100",
            lamport=1,
            at="2026-05-19T10:00:00+00:00",
            actor=_RUNTIME_ACTOR,
            mission_id=MISSION_ID,
            mission_slug=MISSION_SLUG,
            execution_mode="main",
            findings_status="has_findings",
            record_path="kitty-specs/" + MISSION_SLUG + "/retrospective.yaml",
            generator_version="1.0",
            policy_source=dict(_POLICY_SOURCE),
            provenance_kind="runtime_post_completion",
            proposal_count=2,
            evidence_ref_count=3,
        )
        d = event.to_dict()

        assert d["type"] == "RetrospectiveCaptured"
        assert d["schema_version"] == 1
        assert d["mission_id"] == MISSION_ID
        assert d["mission_slug"] == MISSION_SLUG
        assert d["wp_id"] is None
        assert d["force"] is False
        assert d["findings_status"] == "has_findings"
        assert d["provenance_kind"] == "runtime_post_completion"
        assert d["proposal_count"] == 2
        assert d["evidence_ref_count"] == 3

    def test_retrospective_capture_failed_to_dict(self) -> None:
        """RetrospectiveCaptureFailed.to_dict() produces the correct envelope shape."""
        event = RetrospectiveCaptureFailed(
            event_id="01KS049J4V9CSWBKJHTY2FB101",
            lamport=2,
            at="2026-05-19T10:01:00+00:00",
            actor=_RUNTIME_ACTOR,
            mission_id=MISSION_ID,
            mission_slug=MISSION_SLUG,
            execution_mode="main",
            failure_category="missing_artifacts",
            failure_message="Missing status.events.jsonl",
            remediation_hint="Run spec-kitty migrate normalize-lifecycle.",
            policy_source=dict(_POLICY_SOURCE),
            attempted_provenance_kind="runtime_post_completion",
            missing_artifacts=["kitty-specs/test-mission/status.events.jsonl"],
        )
        d = event.to_dict()

        assert d["type"] == "RetrospectiveCaptureFailed"
        assert d["failure_category"] == "missing_artifacts"
        assert d["failure_message"] == "Missing status.events.jsonl"
        assert d["remediation_hint"] is not None
        assert d["missing_artifacts"] == ["kitty-specs/test-mission/status.events.jsonl"]
        assert d["wp_id"] is None
        assert d["force"] is False

    def test_retrospective_skipped_to_dict(self) -> None:
        """RetrospectiveSkipped.to_dict() produces the correct envelope shape."""
        event = RetrospectiveSkipped(
            event_id="01KS049J4V9CSWBKJHTY2FB102",
            lamport=3,
            at="2026-05-19T10:02:00+00:00",
            actor=_HUMAN_ACTOR,
            mission_id=MISSION_ID,
            mission_slug=MISSION_SLUG,
            execution_mode="main",
            skip_reason="Strict gate blocking; will author retrospective post-merge.",
            skip_reason_source="cli_flag",
            policy_source=dict(_STRICT_POLICY_SOURCE),
            bypassed_provenance_kind="runtime_strict_gate",
            would_have_attempted=True,
        )
        d = event.to_dict()

        assert d["type"] == "RetrospectiveSkipped"
        assert d["skip_reason"] == "Strict gate blocking; will author retrospective post-merge."
        assert d["skip_reason_source"] == "cli_flag"
        assert d["bypassed_provenance_kind"] == "runtime_strict_gate"
        assert d["would_have_attempted"] is True
        assert d["wp_id"] is None
        assert d["force"] is False

    def test_all_events_have_sorted_keys_in_jsonl(self) -> None:
        """When serialized with sort_keys=True, the keys must be already sorted."""
        events = [
            RetrospectiveCaptured(
                event_id="A" * 26, lamport=1, at="2026-05-19T10:00:00+00:00",
                actor=_RUNTIME_ACTOR, mission_id=MISSION_ID, mission_slug=MISSION_SLUG,
                findings_status="ran_no_findings", record_path="/path",
                generator_version="1.0", policy_source={}, provenance_kind="explicit_create",
            ),
            RetrospectiveCaptureFailed(
                event_id="B" * 26, lamport=2, at="2026-05-19T10:01:00+00:00",
                actor=_RUNTIME_ACTOR, mission_id=MISSION_ID, mission_slug=MISSION_SLUG,
                failure_category="other", failure_message="err", policy_source={},
                attempted_provenance_kind="runtime_post_completion",
            ),
            RetrospectiveSkipped(
                event_id="C" * 26, lamport=3, at="2026-05-19T10:02:00+00:00",
                actor=_HUMAN_ACTOR, mission_id=MISSION_ID, mission_slug=MISSION_SLUG,
                skip_reason="test reason", skip_reason_source="cli_flag", policy_source={},
            ),
        ]
        for event in events:
            d = event.to_dict()
            line = json.dumps(d, sort_keys=True)
            parsed = json.loads(line)
            keys = list(parsed.keys())
            assert keys == sorted(keys), f"Keys not sorted for {d['type']}: {keys}"


# ---------------------------------------------------------------------------
# T015: Emit helpers
# ---------------------------------------------------------------------------


class TestEmitCaptured:
    def test_emit_captured_writes_to_jsonl(self, tmp_path: Path) -> None:
        """emit_captured appends a RetrospectiveCaptured event to status.events.jsonl."""
        record = make_gen_record(findings_status="has_findings")
        feature_dir = tmp_path / "kitty-specs" / MISSION_SLUG
        feature_dir.mkdir(parents=True)

        event = emit_captured(
            record,
            tmp_path,
            provenance_kind="runtime_post_completion",
            actor=_RUNTIME_ACTOR,
        )

        assert isinstance(event, RetrospectiveCaptured)
        events = _read_events(feature_dir)
        assert len(events) == 1
        assert events[0]["type"] == "RetrospectiveCaptured"
        assert events[0]["event_id"] == event.event_id
        assert events[0]["mission_id"] == MISSION_ID

    def test_emit_captured_returns_ulid(self, tmp_path: Path) -> None:
        """emit_captured returns an event with a ULID event_id."""
        record = make_gen_record()
        feature_dir = tmp_path / "kitty-specs" / MISSION_SLUG
        feature_dir.mkdir(parents=True)

        event = emit_captured(record, tmp_path, provenance_kind="explicit_create", actor=_RUNTIME_ACTOR)
        assert len(event.event_id) == 26

    def test_emit_captured_rejects_synthesize_fabricate_with_findings(self, tmp_path: Path) -> None:
        """emit_captured rejects synthesize_fabricate + has_findings (defense-in-depth)."""
        record = make_gen_record(
            findings_status="has_findings",
            helped=[GenFinding(id="h-001", category="process", summary="A finding")],
        )
        feature_dir = tmp_path / "kitty-specs" / MISSION_SLUG
        feature_dir.mkdir(parents=True)

        with pytest.raises(RecordValidationError) as exc_info:
            emit_captured(
                record,
                tmp_path,
                provenance_kind="synthesize_fabricate",
                actor=_RUNTIME_ACTOR,
            )
        assert "synthesize_fabricate" in str(exc_info.value)

    def test_emit_captured_synthesize_fabricate_ran_no_findings_ok(self, tmp_path: Path) -> None:
        """emit_captured accepts synthesize_fabricate + ran_no_findings."""
        record = make_gen_record(findings_status="ran_no_findings")
        feature_dir = tmp_path / "kitty-specs" / MISSION_SLUG
        feature_dir.mkdir(parents=True)

        event = emit_captured(
            record, tmp_path,
            provenance_kind="synthesize_fabricate",
            actor=_RUNTIME_ACTOR,
        )
        assert event.provenance_kind == "synthesize_fabricate"

    def test_emit_captured_append_only(self, tmp_path: Path) -> None:
        """emit_captured appends; does not overwrite existing events."""
        record = make_gen_record()
        feature_dir = tmp_path / "kitty-specs" / MISSION_SLUG
        feature_dir.mkdir(parents=True)

        emit_captured(record, tmp_path, provenance_kind="explicit_create", actor=_RUNTIME_ACTOR)
        emit_captured(record, tmp_path, provenance_kind="backfill", actor=_RUNTIME_ACTOR)

        events = _read_events(feature_dir)
        assert len(events) == 2


class TestEmitCaptureFailed:
    def test_emit_capture_failed_writes_to_jsonl(self, tmp_path: Path) -> None:
        """emit_capture_failed appends to status.events.jsonl."""
        feature_dir = tmp_path / "kitty-specs" / MISSION_SLUG
        feature_dir.mkdir(parents=True)

        event = emit_capture_failed(
            MISSION_ID,
            MISSION_SLUG,
            tmp_path,
            failure_category="missing_artifacts",
            failure_message="Missing artifacts",
            remediation_hint="Run migrate normalize-lifecycle.",
            policy_source=_POLICY_SOURCE,
            attempted_provenance_kind="runtime_post_completion",
            missing_artifacts=["kitty-specs/test/status.events.jsonl"],
            actor=_RUNTIME_ACTOR,
        )

        assert isinstance(event, RetrospectiveCaptureFailed)
        events = _read_events(feature_dir)
        assert len(events) == 1
        assert events[0]["type"] == "RetrospectiveCaptureFailed"
        assert events[0]["failure_category"] == "missing_artifacts"

    def test_emit_capture_failed_remediation_hint_can_be_none(self, tmp_path: Path) -> None:
        """emit_capture_failed accepts None remediation_hint."""
        feature_dir = tmp_path / "kitty-specs" / MISSION_SLUG
        feature_dir.mkdir(parents=True)

        event = emit_capture_failed(
            MISSION_ID, MISSION_SLUG, tmp_path,
            failure_category="other",
            failure_message="Unknown failure",
            remediation_hint=None,
            policy_source={},
            attempted_provenance_kind="explicit_create",
            missing_artifacts=None,
            actor=_RUNTIME_ACTOR,
        )
        assert event.remediation_hint is None
        events = _read_events(feature_dir)
        assert events[0]["remediation_hint"] is None


class TestEmitSkipped:
    def test_emit_skipped_writes_to_jsonl(self, tmp_path: Path) -> None:
        """emit_skipped appends a RetrospectiveSkipped event."""
        feature_dir = tmp_path / "kitty-specs" / MISSION_SLUG
        feature_dir.mkdir(parents=True)

        event = emit_skipped(
            MISSION_ID,
            MISSION_SLUG,
            tmp_path,
            skip_reason="Strict gate blocking; will author post-merge.",
            skip_reason_source="cli_flag",
            policy_source=_STRICT_POLICY_SOURCE,
            actor=_HUMAN_ACTOR,
        )

        assert isinstance(event, RetrospectiveSkipped)
        events = _read_events(feature_dir)
        assert len(events) == 1
        assert events[0]["type"] == "RetrospectiveSkipped"
        assert events[0]["skip_reason"] == "Strict gate blocking; will author post-merge."

    def test_emit_skipped_empty_reason_raises(self, tmp_path: Path) -> None:
        """emit_skipped with empty skip_reason raises ValueError."""
        feature_dir = tmp_path / "kitty-specs" / MISSION_SLUG
        feature_dir.mkdir(parents=True)

        with pytest.raises(ValueError, match="skip_reason MUST be non-empty"):
            emit_skipped(
                MISSION_ID,
                MISSION_SLUG,
                tmp_path,
                skip_reason="",
                skip_reason_source="cli_flag",
                policy_source={},
                actor=_HUMAN_ACTOR,
            )

    def test_emit_skipped_whitespace_only_reason_raises(self, tmp_path: Path) -> None:
        """emit_skipped with whitespace-only skip_reason raises ValueError."""
        feature_dir = tmp_path / "kitty-specs" / MISSION_SLUG
        feature_dir.mkdir(parents=True)

        with pytest.raises(ValueError, match="skip_reason MUST be non-empty"):
            emit_skipped(
                MISSION_ID,
                MISSION_SLUG,
                tmp_path,
                skip_reason="   ",
                skip_reason_source="cli_flag",
                policy_source={},
                actor=_HUMAN_ACTOR,
            )

    def test_emit_skipped_bypassed_provenance_always_runtime_strict_gate(self, tmp_path: Path) -> None:
        """bypassed_provenance_kind is always runtime_strict_gate."""
        feature_dir = tmp_path / "kitty-specs" / MISSION_SLUG
        feature_dir.mkdir(parents=True)

        event = emit_skipped(
            MISSION_ID, MISSION_SLUG, tmp_path,
            skip_reason="Test reason.",
            skip_reason_source="cli_flag",
            policy_source={},
            actor=_HUMAN_ACTOR,
        )
        assert event.bypassed_provenance_kind == "runtime_strict_gate"
        events = _read_events(feature_dir)
        assert events[0]["bypassed_provenance_kind"] == "runtime_strict_gate"


class TestEventRoundTrip:
    """Verify all three event types serialize to JSONL and read back cleanly."""

    def test_captured_round_trip(self, tmp_path: Path) -> None:
        """RetrospectiveCaptured JSONL round-trip is byte-equal after sort_keys."""
        record = make_gen_record(findings_status="ran_no_findings")
        feature_dir = tmp_path / "kitty-specs" / MISSION_SLUG
        feature_dir.mkdir(parents=True)

        emitted = emit_captured(record, tmp_path, provenance_kind="explicit_create", actor=_RUNTIME_ACTOR)

        events = _read_events(feature_dir)
        assert len(events) == 1
        raw_line = (feature_dir / "status.events.jsonl").read_text().strip()
        parsed = json.loads(raw_line)

        # The serialized event must round-trip without data loss.
        assert parsed["event_id"] == emitted.event_id
        assert parsed["findings_status"] == "ran_no_findings"
        assert parsed["provenance_kind"] == "explicit_create"

        # Keys must be sorted in the JSONL output.
        keys = list(parsed.keys())
        assert keys == sorted(keys)

    def test_failed_round_trip(self, tmp_path: Path) -> None:
        """RetrospectiveCaptureFailed JSONL round-trip is byte-equal after sort_keys."""
        feature_dir = tmp_path / "kitty-specs" / MISSION_SLUG
        feature_dir.mkdir(parents=True)

        emitted = emit_capture_failed(
            MISSION_ID, MISSION_SLUG, tmp_path,
            failure_category="generator_exception",
            failure_message="Timeout during analysis",
            remediation_hint=None,
            policy_source=_POLICY_SOURCE,
            attempted_provenance_kind="runtime_post_completion",
            missing_artifacts=None,
            actor=_RUNTIME_ACTOR,
        )

        raw_line = (feature_dir / "status.events.jsonl").read_text().strip()
        parsed = json.loads(raw_line)

        assert parsed["event_id"] == emitted.event_id
        assert parsed["failure_category"] == "generator_exception"

        keys = list(parsed.keys())
        assert keys == sorted(keys)

    def test_skipped_round_trip(self, tmp_path: Path) -> None:
        """RetrospectiveSkipped JSONL round-trip is byte-equal after sort_keys."""
        feature_dir = tmp_path / "kitty-specs" / MISSION_SLUG
        feature_dir.mkdir(parents=True)

        emitted = emit_skipped(
            MISSION_ID, MISSION_SLUG, tmp_path,
            skip_reason="Testing round-trip.",
            skip_reason_source="ci_environment",
            policy_source=_STRICT_POLICY_SOURCE,
            actor=_HUMAN_ACTOR,
        )

        raw_line = (feature_dir / "status.events.jsonl").read_text().strip()
        parsed = json.loads(raw_line)

        assert parsed["event_id"] == emitted.event_id
        assert parsed["skip_reason"] == "Testing round-trip."
        assert parsed["skip_reason_source"] == "ci_environment"

        keys = list(parsed.keys())
        assert keys == sorted(keys)

    def test_lamport_increments_across_events(self, tmp_path: Path) -> None:
        """Successive events get incrementing lamport values."""
        feature_dir = tmp_path / "kitty-specs" / MISSION_SLUG
        feature_dir.mkdir(parents=True)

        record = make_gen_record()
        e1 = emit_captured(record, tmp_path, provenance_kind="explicit_create", actor=_RUNTIME_ACTOR)
        e2 = emit_capture_failed(
            MISSION_ID, MISSION_SLUG, tmp_path,
            failure_category="other", failure_message="err",
            remediation_hint=None, policy_source={},
            attempted_provenance_kind="explicit_create",
            missing_artifacts=None, actor=_RUNTIME_ACTOR,
        )

        assert e2.lamport > e1.lamport


# ---------------------------------------------------------------------------
# T017: classify_mission_record
# ---------------------------------------------------------------------------


class TestClassifyMissionRecord:
    def _make_gen_record_yaml(
        self,
        tmp_path: Path,
        mission_id: str,
        findings_status: str,
    ) -> Path:
        """Write a minimal GenRetrospectiveRecord YAML to tmp_path/retrospective.yaml."""
        record_dir = tmp_path
        record_dir.mkdir(parents=True, exist_ok=True)
        retro_path = record_dir / "retrospective.yaml"

        content = {
            "schema_version": 1,
            "mission_id": mission_id,
            "mission_slug": "test-classify",
            "mission_number": None,
            "friendly_name": "Test",
            "mission_type": "software-dev",
            "target_branch": "main",
            "created_at": "2026-05-19T10:00:00+00:00",
            "created_by": {"kind": "runtime", "id": "spec-kitty", "display": None},
            "provenance": {
                "kind": "runtime_post_completion",
                "invoked_at": "2026-05-19T10:00:00+00:00",
                "policy_resolved_from": {},
                "command": None,
            },
            "policy_source": {"enabled": "<default>"},
            "findings_status": findings_status,
            "helped": [],
            "not_helpful": [],
            "gaps": [],
            "proposals": [],
            "evidence_refs": [],
            "generator_version": "1.0",
            "provenance_history": [],
        }

        import yaml as _yaml  # stdlib yaml for simple dict write
        try:
            retro_path.write_text(_yaml.dump(content), encoding="utf-8")
        except ImportError:
            # Fall back to ruamel
            from ruamel.yaml import YAML
            import io
            y = YAML()
            buf = io.StringIO()
            y.dump(content, buf)
            retro_path.write_text(buf.getvalue(), encoding="utf-8")
        return record_dir

    def test_classify_has_findings(self, tmp_path: Path) -> None:
        """Record with findings_status=has_findings → 'has_findings'."""
        feature_dir = self._make_gen_record_yaml(tmp_path, MISSION_ID, "has_findings")
        result = classify_mission_record(feature_dir)
        assert result == "has_findings"

    def test_classify_ran_no_findings(self, tmp_path: Path) -> None:
        """Record with findings_status=ran_no_findings → 'ran_no_findings'."""
        feature_dir = self._make_gen_record_yaml(tmp_path, MISSION_ID, "ran_no_findings")
        result = classify_mission_record(feature_dir)
        assert result == "ran_no_findings"

    def test_classify_missing_no_events(self, tmp_path: Path) -> None:
        """No record + no events → 'missing'."""
        feature_dir = tmp_path / "empty"
        feature_dir.mkdir()
        result = classify_mission_record(feature_dir)
        assert result == "missing"

    def test_classify_missing_with_captured_event(self, tmp_path: Path) -> None:
        """No record + captured event (no failed after) → 'missing'.

        If there's a RetrospectiveCaptured event but no record on disk, the
        record may have been cleaned up. classify_mission_record still returns
        'missing' since it checks the YAML file.
        """
        feature_dir = tmp_path / "with-captured"
        feature_dir.mkdir()

        # Write a captured event to the event log.
        events_path = feature_dir / "status.events.jsonl"
        events_path.write_text(
            json.dumps({
                "type": "RetrospectiveCaptured",
                "lamport": 5,
                "at": "2026-05-19T10:00:00+00:00",
                "mission_id": MISSION_ID,
                "mission_slug": MISSION_SLUG,
            }, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        result = classify_mission_record(feature_dir)
        # No YAML file on disk → missing (even though there's a Captured event).
        assert result == "missing"

    def test_classify_failed_recent_failed_event(self, tmp_path: Path) -> None:
        """No record + recent Failed event > any Captured event → 'failed'."""
        feature_dir = tmp_path / "with-failed"
        feature_dir.mkdir()

        events_path = feature_dir / "status.events.jsonl"
        events_path.write_text(
            json.dumps({
                "type": "RetrospectureCaptureFailed",
                "lamport": 1,
                "at": "2026-05-19T09:00:00+00:00",
                "mission_id": MISSION_ID,
            }, sort_keys=True) + "\n" +
            json.dumps({
                "type": "RetrospectiveCaptureFailed",
                "lamport": 5,
                "at": "2026-05-19T10:00:00+00:00",
                "mission_id": MISSION_ID,
                "mission_slug": MISSION_SLUG,
            }, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        result = classify_mission_record(feature_dir)
        assert result == "failed"

    def test_classify_failed_captured_then_failed(self, tmp_path: Path) -> None:
        """No record + Captured lamport=3, Failed lamport=7 → 'failed'."""
        feature_dir = tmp_path / "captured-then-failed"
        feature_dir.mkdir()

        events_path = feature_dir / "status.events.jsonl"
        events_path.write_text(
            json.dumps({
                "type": "RetrospectiveCaptured",
                "lamport": 3,
                "at": "2026-05-19T09:00:00+00:00",
            }, sort_keys=True) + "\n" +
            json.dumps({
                "type": "RetrospectiveCaptureFailed",
                "lamport": 7,
                "at": "2026-05-19T10:00:00+00:00",
            }, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        result = classify_mission_record(feature_dir)
        assert result == "failed"

    def test_classify_not_failed_when_captured_after_failed(self, tmp_path: Path) -> None:
        """No record + Failed lamport=3, Captured lamport=7 → 'missing' (not failed)."""
        feature_dir = tmp_path / "failed-then-captured"
        feature_dir.mkdir()

        events_path = feature_dir / "status.events.jsonl"
        events_path.write_text(
            json.dumps({
                "type": "RetrospectiveCaptureFailed",
                "lamport": 3,
                "at": "2026-05-19T09:00:00+00:00",
            }, sort_keys=True) + "\n" +
            json.dumps({
                "type": "RetrospectiveCaptured",
                "lamport": 7,
                "at": "2026-05-19T10:00:00+00:00",
            }, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        result = classify_mission_record(feature_dir)
        # Captured is more recent than Failed → not "failed"
        assert result == "missing"

    def test_classify_record_with_unknown_findings_status_falls_back_to_has_findings(
        self, tmp_path: Path
    ) -> None:
        """Record with unrecognized findings_status falls through to 'has_findings'."""
        feature_dir = tmp_path / "unknown-status"
        feature_dir.mkdir()
        retro_path = feature_dir / "retrospective.yaml"
        # findings_status has an unrecognized value → GenRecord path falls through,
        # Pydantic path also fails → conservatively returns "has_findings".
        retro_path.write_text(
            "findings_status: unknown_value\nschema_version: 1\n",
            encoding="utf-8",
        )
        result = classify_mission_record(feature_dir)
        # Falls through to conservative "has_findings" return.
        assert result == "has_findings"

    def test_classify_unreadable_record_file_returns_has_findings(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When record file exists but read raises, returns 'has_findings' conservatively."""
        feature_dir = tmp_path / "unreadable"
        feature_dir.mkdir()
        retro_path = feature_dir / "retrospective.yaml"
        retro_path.write_text("schema_version: 1\n", encoding="utf-8")

        original_read_text = Path.read_text

        def failing_read_text(self: Path, *args: object, **kwargs: object) -> str:
            if self.name == "retrospective.yaml":
                raise OSError("Simulated unreadable")
            return original_read_text(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", failing_read_text)
        result = classify_mission_record(feature_dir)
        # Both YAML and Pydantic fallback fail → "has_findings" conservative.
        assert result == "has_findings"

    def test_classify_pydantic_fallback_completed_with_findings(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pydantic fallback: non-dict YAML + completed record with findings → 'has_findings'."""
        feature_dir = tmp_path / "pydantic-fallback-findings"
        feature_dir.mkdir()
        retro_path = feature_dir / "retrospective.yaml"
        # Write YAML that is a list (not a dict) — first try falls through since not isinstance(raw, dict).
        retro_path.write_text("- status: completed\n", encoding="utf-8")

        # Mock read_record and the Pydantic record object.
        from unittest.mock import MagicMock
        import specify_cli.retrospective.summary as _summary_mod
        mock_record = MagicMock()
        mock_record.status = "completed"
        mock_record.helped = [MagicMock()]
        mock_record.not_helpful = []
        mock_record.gaps = []
        mock_record.proposals = []
        monkeypatch.setattr(_summary_mod, "read_record", lambda _path: mock_record)

        result = classify_mission_record(feature_dir)
        assert result == "has_findings"

    def test_classify_pydantic_fallback_completed_no_findings(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pydantic fallback: non-dict YAML + completed record with no findings → 'ran_no_findings'."""
        feature_dir = tmp_path / "pydantic-fallback-empty"
        feature_dir.mkdir()
        retro_path = feature_dir / "retrospective.yaml"
        retro_path.write_text("- status: completed\n", encoding="utf-8")

        from unittest.mock import MagicMock
        import specify_cli.retrospective.summary as _summary_mod
        mock_record = MagicMock()
        mock_record.status = "completed"
        mock_record.helped = []
        mock_record.not_helpful = []
        mock_record.gaps = []
        mock_record.proposals = []
        monkeypatch.setattr(_summary_mod, "read_record", lambda _path: mock_record)

        result = classify_mission_record(feature_dir)
        assert result == "ran_no_findings"

    def test_classify_non_integer_lamport_treated_as_zero(self, tmp_path: Path) -> None:
        """Non-integer lamport values in events are treated as 0 for comparison."""
        feature_dir = tmp_path / "bad-lamport"
        feature_dir.mkdir()
        events_path = feature_dir / "status.events.jsonl"
        events_path.write_text(
            json.dumps({
                "type": "RetrospectiveCaptureFailed",
                "lamport": "not-a-number",
                "at": "2026-05-19T10:00:00+00:00",
            }, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        result = classify_mission_record(feature_dir)
        # lamport="not-a-number" is treated as 0, so failed_lp(0) > captured_lp(0) is False.
        assert result == "missing"

    def test_classify_non_integer_captured_lamport_treated_as_zero(
        self, tmp_path: Path
    ) -> None:
        """Non-integer captured lamport falls back to 0 so failed event can win."""
        feature_dir = tmp_path / "bad-captured-lamport"
        feature_dir.mkdir()
        events_path = feature_dir / "status.events.jsonl"
        events_path.write_text(
            json.dumps({
                "type": "RetrospectiveCaptured",
                "lamport": "bad",
                "at": "2026-05-19T09:00:00+00:00",
            }, sort_keys=True) + "\n" +
            json.dumps({
                "type": "RetrospectiveCaptureFailed",
                "lamport": 3,
                "at": "2026-05-19T10:00:00+00:00",
            }, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        result = classify_mission_record(feature_dir)
        # captured_lp=0 (bad lamport), failed_lp=3 → failed_lp > captured_lp → "failed".
        assert result == "failed"

    def test_classify_no_retro_events_only_lane_events(self, tmp_path: Path) -> None:
        """No record + only lane events (no retro type field) → 'missing'."""
        feature_dir = tmp_path / "lane-only"
        feature_dir.mkdir()

        events_path = feature_dir / "status.events.jsonl"
        events_path.write_text(
            json.dumps({
                "actor": "claude",
                "at": "2026-05-19T09:00:00+00:00",
                "event_id": "01KS049J4V9CSWBKJHTY2FB001",
                "from_lane": "planned",
                "to_lane": "claimed",
                "wp_id": "WP01",
            }, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        result = classify_mission_record(feature_dir)
        assert result == "missing"


# ---------------------------------------------------------------------------
# Edge-case tests for lifecycle_events branch coverage (FR-021)
# ---------------------------------------------------------------------------


class TestLifecycleEventsEdgeCases:
    """Branch-coverage tests for emit helpers and _next_lamport."""

    def test_emit_captured_empty_mission_slug_raises(self, tmp_path: Path) -> None:
        """emit_captured with empty mission_slug raises ValueError."""
        import dataclasses
        record = make_gen_record()
        bad_record = dataclasses.replace(record, mission_slug="")
        with pytest.raises(ValueError, match="mission_slug must be non-empty"):
            emit_captured(
                bad_record,
                tmp_path,
                provenance_kind="runtime_post_completion",
                actor=_RUNTIME_ACTOR,
            )

    def test_emit_capture_failed_empty_mission_slug_raises(self, tmp_path: Path) -> None:
        """emit_capture_failed with empty mission_slug raises ValueError."""
        with pytest.raises(ValueError, match="mission_slug must be non-empty"):
            emit_capture_failed(
                MISSION_ID,
                "",  # empty mission_slug
                tmp_path,
                failure_category="other",
                failure_message="test error",
                remediation_hint=None,
                policy_source={},
                attempted_provenance_kind="runtime_post_completion",
                missing_artifacts=None,
                actor=_RUNTIME_ACTOR,
            )

    def test_emit_skipped_empty_mission_slug_raises(self, tmp_path: Path) -> None:
        """emit_skipped with empty mission_slug raises ValueError."""
        with pytest.raises(ValueError, match="mission_slug must be non-empty"):
            emit_skipped(
                MISSION_ID,
                "",  # empty mission_slug
                tmp_path,
                skip_reason="Test reason.",
                skip_reason_source="cli_flag",
                policy_source={},
                actor=_RUNTIME_ACTOR,
            )

    def test_next_lamport_skips_blank_lines(self, tmp_path: Path) -> None:
        """_next_lamport skips blank/whitespace lines in the events file."""
        from specify_cli.retrospective.lifecycle_events import _next_lamport
        feature_dir = tmp_path / "kitty-specs" / MISSION_SLUG
        feature_dir.mkdir(parents=True)
        events_path = feature_dir / "status.events.jsonl"
        events_path.write_text(
            '{"lamport": 5, "type": "RetrospectiveCaptured"}\n'
            '\n'
            '   \n'
            '{"lamport": 3, "type": "RetrospectiveCaptureFailed"}\n',
            encoding="utf-8",
        )
        result = _next_lamport(feature_dir)
        assert result == 6  # max(5,3) + 1

    def test_next_lamport_skips_invalid_json_lines(self, tmp_path: Path) -> None:
        """_next_lamport skips lines with invalid JSON (JSONDecodeError)."""
        from specify_cli.retrospective.lifecycle_events import _next_lamport
        feature_dir = tmp_path / "kitty-specs" / MISSION_SLUG
        feature_dir.mkdir(parents=True)
        events_path = feature_dir / "status.events.jsonl"
        events_path.write_text(
            '{"lamport": 7, "type": "RetrospectiveCaptured"}\n'
            'not valid json {{{{\n'
            '{"lamport": 2, "type": "RetrospectiveCaptureFailed"}\n',
            encoding="utf-8",
        )
        result = _next_lamport(feature_dir)
        assert result == 8  # max(7,2) + 1

    def test_next_lamport_handles_oserror_gracefully(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_next_lamport returns 1 (safe default) if the events file is unreadable (OSError)."""
        from specify_cli.retrospective.lifecycle_events import _next_lamport
        feature_dir = tmp_path / "kitty-specs" / MISSION_SLUG
        feature_dir.mkdir(parents=True)
        events_path = feature_dir / "status.events.jsonl"
        events_path.write_text('{"lamport": 5}\n', encoding="utf-8")

        original_read_text = Path.read_text

        def failing_read_text(self: Path, *args: object, **kwargs: object) -> str:
            if self.name == "status.events.jsonl":
                raise OSError("Simulated unreadable file")
            return original_read_text(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", failing_read_text)
        result = _next_lamport(feature_dir)
        # OSError is caught; last_lamport stays 0, so returns 0+1=1.
        assert result == 1


# ---------------------------------------------------------------------------
# Coverage tests for summary.py helper functions (pre-WP03 uncovered paths)
# ---------------------------------------------------------------------------


class TestSummaryHelperEdgeCases:
    """Edge-case coverage for pre-WP03 helper functions in summary.py."""

    def test_is_legacy_naive_datetime_gets_utc_added(self) -> None:
        """_is_legacy handles a naive datetime string (no tz info) without error."""
        from specify_cli.retrospective.summary import _is_legacy
        # A clearly old date — naive datetime → gets UTC added → should be legacy.
        result = _is_legacy("2025-01-01T00:00:00")
        assert result is True

    def test_is_legacy_invalid_string_returns_false(self) -> None:
        """_is_legacy returns False on an unparseable datetime string."""
        from specify_cli.retrospective.summary import _is_legacy
        result = _is_legacy("not-a-date")
        assert result is False

    def test_mission_is_in_flight_no_meta_json(self, tmp_path: Path) -> None:
        """_mission_is_in_flight returns False if meta.json doesn't exist."""
        from specify_cli.retrospective.summary import _mission_is_in_flight
        result = _mission_is_in_flight(tmp_path / "no-such-dir")
        assert result is False

    def test_mission_is_in_flight_in_progress_status(self, tmp_path: Path) -> None:
        """_mission_is_in_flight returns True when status is non-terminal."""
        from specify_cli.retrospective.summary import _mission_is_in_flight
        mission_dir = tmp_path / "mission"
        mission_dir.mkdir()
        (mission_dir / "meta.json").write_text(
            '{"status": "in_progress"}', encoding="utf-8"
        )
        result = _mission_is_in_flight(mission_dir)
        assert result is True

    def test_most_recent_gen_event_skips_blank_and_bad_json(self, tmp_path: Path) -> None:
        """_most_recent_gen_event handles blank lines and JSONDecodeError gracefully."""
        from specify_cli.retrospective.summary import _most_recent_gen_event
        feature_dir = tmp_path / "events-test"
        feature_dir.mkdir()
        events_path = feature_dir / "status.events.jsonl"
        events_path.write_text(
            '{"type": "RetrospectiveCaptured", "lamport": 5}\n'
            '\n'
            'bad json {{{\n'
            '{"type": "RetrospectiveCaptured", "lamport": 3}\n',
            encoding="utf-8",
        )
        result = _most_recent_gen_event(feature_dir, "RetrospectiveCaptured")
        assert result is not None
        assert result["lamport"] == 5

    def test_mission_is_in_flight_exception_returns_false(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_mission_is_in_flight returns False on json.loads error."""
        from specify_cli.retrospective.summary import _mission_is_in_flight
        mission_dir = tmp_path / "bad-json-mission"
        mission_dir.mkdir()
        (mission_dir / "meta.json").write_text("not valid json !!!", encoding="utf-8")
        result = _mission_is_in_flight(mission_dir)
        assert result is False

    def test_read_proposal_events_empty_slug_returns_zeros(self, tmp_path: Path) -> None:
        """_read_proposal_events with empty mission_slug returns (0, 0, 0)."""
        from specify_cli.retrospective.summary import _read_proposal_events
        result = _read_proposal_events(tmp_path, "")
        assert result == (0, 0, 0)

    def test_read_proposal_events_no_events_file_returns_zeros(self, tmp_path: Path) -> None:
        """_read_proposal_events with no events file returns (0, 0, 0)."""
        from specify_cli.retrospective.summary import _read_proposal_events
        result = _read_proposal_events(tmp_path, "no-such-mission")
        assert result == (0, 0, 0)

    def test_read_proposal_events_counts_events(self, tmp_path: Path) -> None:
        """_read_proposal_events counts proposal events correctly."""
        from specify_cli.retrospective.summary import _read_proposal_events
        mission_slug = "test-mission-prop"
        feature_dir = tmp_path / "kitty-specs" / mission_slug
        feature_dir.mkdir(parents=True)
        events_path = feature_dir / "status.events.jsonl"
        events_path.write_text(
            '{"event_name": "retrospective.proposal.generated"}\n'
            '{"event_name": "retrospective.proposal.generated"}\n'
            '{"event_name": "retrospective.proposal.applied"}\n'
            '{"event_name": "retrospective.proposal.rejected"}\n'
            'bad json\n'
            '\n',
            encoding="utf-8",
        )
        gen, app, rej = _read_proposal_events(tmp_path, mission_slug)
        assert gen == 2
        assert app == 1
        assert rej == 1

    def test_most_recent_gen_event_oserror_returns_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_most_recent_gen_event returns None on OSError reading events file."""
        from specify_cli.retrospective.summary import _most_recent_gen_event
        feature_dir = tmp_path / "events-oserror"
        feature_dir.mkdir()
        events_path = feature_dir / "status.events.jsonl"
        events_path.write_text('{"type": "RetrospectiveCaptured", "lamport": 1}\n', encoding="utf-8")

        original_read_text = Path.read_text

        def failing_read_text(self: Path, *args: object, **kwargs: object) -> str:
            if self.name == "status.events.jsonl":
                raise OSError("Simulated unreadable")
            return original_read_text(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", failing_read_text)
        result = _most_recent_gen_event(feature_dir, "RetrospectiveCaptured")
        assert result is None
