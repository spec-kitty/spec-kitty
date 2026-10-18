"""Integration tests for event emission (WP08 -- T039).

Tests cover:
- Event log path creation and sanitization
- Event persistence through the spec-kitty-events ledger write contract
- Event ordering across middleware pipeline
- Event filtering (read_events with event_type filter)
- All 8 canonical event types
- Contract refusals: a refused record is not written, with no local fallback
- Torn-tail repair: the fragment is moved to a sidecar before the append
- ClarificationMiddleware emits 3 event types
- Scope activation emits GlossaryScopeActivated
- Event emission at middleware boundaries
- Round-trip: emit -> persist -> read
- Edge cases: corrupt JSONL, empty files, concurrent writes
"""

import json
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import patch
from dataclasses import dataclass, field

import pytest

import glossary.events as events_module
from spec_kitty_events.persistence import LedgerValidationError, build_record, serialize_record

from glossary.events import (
    TORN_TAIL_SUFFIX,
    _persist_event,
    _repair_torn_tail,
    append_event,
    build_clarification_requested,
    build_clarification_resolved,
    build_generation_blocked,
    build_glossary_scope_activated,
    build_semantic_check_evaluated,
    build_sense_updated,
    build_step_checkpointed,
    build_term_candidate_observed,
    emit_clarification_requested,
    emit_clarification_resolved,
    emit_generation_blocked_event,
    emit_scope_activated,
    emit_semantic_check_evaluated,
    emit_sense_updated,
    emit_step_checkpointed,
    emit_term_candidate_observed,
    get_event_log_path,
    read_events,
    _sanitize_mission_id,
)
from glossary.extraction import ExtractedTerm
from glossary.models import (
    ConflictType,
    SemanticConflict,
    SenseRef,
    Severity,
    TermSurface,
)
from glossary.scope import GlossaryScope
from glossary.strictness import Strictness

pytestmark = pytest.mark.fast
# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@dataclass
class MockContext:
    """Mock execution context for event emission tests."""

    step_id: str = "step-001"
    mission_id: str = "041-mission"
    run_id: str = "run-001"
    actor_id: str = "user:alice"
    metadata: dict[str, Any] = field(default_factory=dict)
    step_input: dict[str, Any] = field(default_factory=dict)
    step_output: dict[str, Any] = field(default_factory=dict)
    extracted_terms: list[Any] = field(default_factory=list)
    conflicts: list[SemanticConflict] = field(default_factory=list)
    effective_strictness: str = "medium"


@pytest.fixture
def mock_context():
    """Create a mock execution context."""
    return MockContext()


@pytest.fixture
def temp_event_log(tmp_path):
    """Create temporary event log directory."""
    events_dir = tmp_path / ".kittify" / "events" / "glossary"
    events_dir.mkdir(parents=True)
    return events_dir


@pytest.fixture
def sample_conflict():
    """Create a sample SemanticConflict for testing."""
    return SemanticConflict(
        term=TermSurface("workspace"),
        conflict_type=ConflictType.AMBIGUOUS,
        severity=Severity.HIGH,
        confidence=0.9,
        candidate_senses=[
            SenseRef("workspace", "team_domain", "Git worktree directory", 0.9),
            SenseRef("workspace", "team_domain", "VS Code workspace file", 0.7),
        ],
        context="description field",
    )


@pytest.fixture
def sample_extracted_term():
    """Create a sample ExtractedTerm for testing."""
    return ExtractedTerm(
        surface="workspace",
        source="casing_pattern",
        confidence=0.8,
        original="Workspace",
    )


# ---------------------------------------------------------------------------
# T036: Event Log Path and Sanitization
# ---------------------------------------------------------------------------


class TestEventLogPath:
    """Tests for get_event_log_path() and path sanitization."""

    def test_creates_directory(self, tmp_path):
        """Event log path helper creates directory if it does not exist."""
        event_log_path = get_event_log_path(tmp_path, "041-mission")
        assert event_log_path.parent.exists()
        assert event_log_path.name == "041-mission.events.jsonl"

    def test_creates_nested_directory(self, tmp_path):
        """Creates full .kittify/events/glossary/ hierarchy."""
        event_log_path = get_event_log_path(tmp_path, "test-mission")
        assert (tmp_path / ".kittify" / "events" / "glossary").is_dir()
        assert event_log_path.suffix == ".jsonl"

    def test_returns_correct_filename(self, tmp_path):
        """Filename matches {mission_id}.events.jsonl pattern."""
        path = get_event_log_path(tmp_path, "my-mission-42")
        assert path.name == "my-mission-42.events.jsonl"

    def test_sanitizes_special_characters(self, tmp_path):
        """Special characters in mission_id are replaced with hyphens."""
        path = get_event_log_path(tmp_path, "path/to/mission")
        assert "/" not in path.name
        assert path.name == "path-to-mission.events.jsonl"

    def test_sanitize_mission_id_preserves_safe_chars(self):
        """Safe characters are preserved in sanitized mission ID."""
        assert _sanitize_mission_id("simple-mission_42.v1") == "simple-mission_42.v1"

    def test_sanitize_mission_id_replaces_slashes(self):
        """Slashes are replaced with hyphens."""
        assert _sanitize_mission_id("path/to/mission") == "path-to-mission"

    def test_sanitize_mission_id_replaces_spaces(self):
        """Spaces are replaced with hyphens."""
        assert _sanitize_mission_id("my mission") == "my-mission"

    def test_idempotent_directory_creation(self, tmp_path):
        """Calling get_event_log_path twice does not fail."""
        get_event_log_path(tmp_path, "m1")
        path = get_event_log_path(tmp_path, "m1")
        assert path.parent.is_dir()

    def test_different_missions_different_files(self, tmp_path):
        """Each mission gets its own event log file."""
        p1 = get_event_log_path(tmp_path, "mission-a")
        p2 = get_event_log_path(tmp_path, "mission-b")
        assert p1 != p2
        assert p1.name == "mission-a.events.jsonl"
        assert p2.name == "mission-b.events.jsonl"


# ---------------------------------------------------------------------------
# T036: Event Payload Builders
# ---------------------------------------------------------------------------


class TestEventPayloadBuilders:
    """Tests for build_*() event payload functions."""

    def test_scope_activated_payload(self):
        """GlossaryScopeActivated has all required fields."""
        event = build_glossary_scope_activated(
            scope_id="team_domain",
            glossary_version_id="v3",
            mission_id="041-mission",
            run_id="run-001",
            timestamp="2026-02-16T12:00:00+00:00",
        )
        assert event["event_type"] == "GlossaryScopeActivated"
        assert event["scope_id"] == "team_domain"
        assert event["glossary_version_id"] == "v3"
        assert event["mission_id"] == "041-mission"
        assert event["run_id"] == "run-001"
        assert event["timestamp"] == "2026-02-16T12:00:00+00:00"

    def test_term_candidate_observed_payload(self):
        """TermCandidateObserved has all required fields."""
        event = build_term_candidate_observed(
            term="workspace",
            source_step="step-001",
            actor_id="user:alice",
            confidence=0.8,
            extraction_method="casing_pattern",
            context="description field",
            mission_id="041-mission",
            run_id="run-001",
        )
        assert event["event_type"] == "TermCandidateObserved"
        assert event["term"] == "workspace"
        assert event["confidence"] == 0.8
        assert event["extraction_method"] == "casing_pattern"

    def test_semantic_check_evaluated_payload(self):
        """SemanticCheckEvaluated has all required fields."""
        event = build_semantic_check_evaluated(
            step_id="step-001",
            mission_id="041-mission",
            run_id="run-001",
            findings=[],
            overall_severity="low",
            confidence=1.0,
            effective_strictness="medium",
            recommended_action="proceed",
            blocked=False,
        )
        assert event["event_type"] == "SemanticCheckEvaluated"
        assert event["blocked"] is False
        assert event["findings"] == []

    def test_generation_blocked_payload(self):
        """GenerationBlockedBySemanticConflict has all required fields."""
        event = build_generation_blocked(
            step_id="step-001",
            mission_id="041-mission",
            run_id="run-001",
            conflicts=[{"term": "workspace", "severity": "high"}],
            strictness_mode="medium",
            effective_strictness="medium",
        )
        assert event["event_type"] == "GenerationBlockedBySemanticConflict"
        assert len(event["conflicts"]) == 1
        assert event["strictness_mode"] == "medium"

    def test_clarification_requested_payload(self):
        """GlossaryClarificationRequested has all required fields."""
        event = build_clarification_requested(
            question="What does 'workspace' mean?",
            term="workspace",
            options=["Git worktree", "VS Code workspace"],
            urgency="high",
            mission_id="041-mission",
            run_id="run-001",
            step_id="step-001",
            conflict_id="uuid-1234",
        )
        assert event["event_type"] == "GlossaryClarificationRequested"
        assert event["term"] == "workspace"
        assert len(event["options"]) == 2
        assert event["conflict_id"] == "uuid-1234"

    def test_clarification_requested_auto_generates_conflict_id(self):
        """conflict_id is auto-generated if not provided."""
        event = build_clarification_requested(
            question="Q",
            term="t",
            options=[],
            urgency="low",
            mission_id="m",
            run_id="r",
            step_id="s",
        )
        assert len(event["conflict_id"]) == 36  # UUID format

    def test_clarification_resolved_payload(self):
        """GlossaryClarificationResolved has all required fields."""
        event = build_clarification_resolved(
            conflict_id="uuid-1234",
            term_surface="workspace",
            selected_sense={
                "surface": "workspace",
                "scope": "team_domain",
                "definition": "Git worktree",
                "confidence": 0.9,
            },
            actor={"actor_id": "user:alice", "actor_type": "human", "display_name": "Alice"},
            resolution_mode="interactive",
            provenance={
                "source": "user_clarification",
                "timestamp": "2026-02-16T12:00:00+00:00",
                "actor_id": "user:alice",
            },
        )
        assert event["event_type"] == "GlossaryClarificationResolved"
        assert event["conflict_id"] == "uuid-1234"
        assert event["resolution_mode"] == "interactive"

    def test_sense_updated_payload(self):
        """GlossarySenseUpdated has all required fields."""
        event = build_sense_updated(
            term_surface="workspace",
            scope="team_domain",
            new_sense={
                "surface": "workspace",
                "scope": "team_domain",
                "definition": "Git worktree",
                "confidence": 1.0,
                "status": "active",
            },
            actor={"actor_id": "user:alice", "actor_type": "human", "display_name": "Alice"},
            update_type="create",
            provenance={
                "source": "user_clarification",
                "timestamp": "2026-02-16T12:00:00+00:00",
                "actor_id": "user:alice",
            },
        )
        assert event["event_type"] == "GlossarySenseUpdated"
        assert event["update_type"] == "create"
        assert event["new_sense"]["confidence"] == 1.0

    def test_step_checkpointed_payload(self):
        """StepCheckpointed has all required fields."""
        event = build_step_checkpointed(
            mission_id="041-mission",
            run_id="run-001",
            step_id="step-001",
            strictness="medium",
            scope_refs=[{"scope": "team_domain", "version_id": "v3"}],
            input_hash="a" * 64,
            cursor="pre_generation_gate",
            retry_token=str(uuid.uuid4()),
        )
        assert event["event_type"] == "StepCheckpointed"
        assert event["input_hash"] == "a" * 64
        assert event["cursor"] == "pre_generation_gate"

    def test_all_builders_include_timestamp(self):
        """All event builders generate a timestamp if not provided."""
        builders = [
            lambda: build_glossary_scope_activated("s", "v", "m", "r"),
            lambda: build_term_candidate_observed("t", "s", "a", 0.5, "m", "c", "m", "r"),
            lambda: build_semantic_check_evaluated("s", "m", "r", [], "low", 1.0, "medium", "proceed", False),
            lambda: build_generation_blocked("s", "m", "r", [], "medium", "medium"),
            lambda: build_clarification_requested("q", "t", [], "low", "m", "r", "s"),
            lambda: build_clarification_resolved("c", "t", {}, {}, "interactive", {}),
            lambda: build_sense_updated("t", "s", {}, {}, "create", {}),
            lambda: build_step_checkpointed(
                "m", "r", "s", "medium", [], "a" * 64, "pre_generation_gate", str(uuid.uuid4())
            ),
        ]
        for builder in builders:
            event = builder()
            assert "timestamp" in event
            assert event["timestamp"] is not None

    def test_all_payloads_json_serializable(self):
        """All event payloads can be serialized to JSON."""
        events = [
            build_glossary_scope_activated("s", "v", "m", "r"),
            build_term_candidate_observed("t", "s", "a", 0.5, "m", "c", "m", "r"),
            build_semantic_check_evaluated("s", "m", "r", [], "low", 1.0, "medium", "proceed", False),
            build_generation_blocked("s", "m", "r", [], "medium", "medium"),
            build_clarification_requested("q", "t", [], "low", "m", "r", "s"),
            build_clarification_resolved("c", "t", {}, {}, "interactive", {}),
            build_sense_updated("t", "s", {}, {}, "create", {}),
            build_step_checkpointed("m", "r", "s", "medium", [], "a" * 64, "pre_generation_gate", str(uuid.uuid4())),
        ]
        for event in events:
            # Must not raise
            serialized = json.dumps(event, sort_keys=True)
            assert isinstance(serialized, str)


# ---------------------------------------------------------------------------
# T038: Event Persistence (JSONL append and read)
def _term_event(term: str = "workspace") -> dict[str, Any]:
    """A real TermCandidateObserved record that satisfies the events contract."""
    return build_term_candidate_observed(
        term=term,
        source_step="step-001",
        actor_id="user:alice",
        confidence=0.8,
        extraction_method="casing_pattern",
        context="description field",
        mission_id="041-mission",
        run_id="run-001",
        timestamp="2026-02-16T12:00:00+00:00",
    )


class TestEventPersistence:
    """Tests for append_event() and read_events()."""

    def test_append_creates_file(self, tmp_path):
        """append_event creates the JSONL file if it does not exist."""
        log_path = tmp_path / "test.events.jsonl"
        append_event(_term_event(), log_path)
        assert log_path.exists()

    def test_append_writes_one_json_line_per_event(self, tmp_path):
        """Each event is written as one JSON line."""
        log_path = tmp_path / "test.events.jsonl"
        append_event(_term_event("alpha"), log_path)
        append_event(_term_event("beta"), log_path)

        lines = [line for line in log_path.read_text().splitlines() if line.strip()]
        assert [json.loads(line)["term"] for line in lines] == ["alpha", "beta"]

    def test_append_creates_parent_directory(self, tmp_path):
        """append_event creates parent directories if they do not exist."""
        log_path = tmp_path / "new" / "dir" / "test.events.jsonl"
        append_event(_term_event(), log_path)
        assert log_path.exists()

    def test_append_writes_the_contract_line(self, tmp_path):
        """The written line is exactly the contract's serialization of the record."""
        log_path = tmp_path / "test.events.jsonl"
        event = _term_event()
        append_event(event, log_path)
        assert log_path.read_bytes() == serialize_record(build_record(event))

    def test_append_refuses_an_unknown_event_type_and_writes_nothing(self, tmp_path):
        """A type the contract does not register is refused; there is no local fallback."""
        log_path = tmp_path / "test.events.jsonl"
        with pytest.raises(LedgerValidationError):
            append_event({"event_type": "NotAGlossaryEvent"}, log_path)
        assert not log_path.exists()

    def test_append_refuses_an_invalid_record_and_leaves_the_log_unchanged(self, tmp_path):
        """A record that fails its payload contract is refused and the log is untouched."""
        log_path = tmp_path / "test.events.jsonl"
        append_event(_term_event(), log_path)
        before = log_path.read_bytes()
        invalid = _term_event()
        invalid["confidence"] = "high"
        with pytest.raises(LedgerValidationError):
            append_event(invalid, log_path)
        assert log_path.read_bytes() == before

    def test_read_events_empty_file(self, tmp_path):
        """read_events on empty file yields nothing."""
        log_path = tmp_path / "empty.events.jsonl"
        log_path.write_text("")
        events = list(read_events(log_path))
        assert events == []

    def test_read_events_nonexistent_file(self, tmp_path):
        """read_events on nonexistent file yields nothing."""
        log_path = tmp_path / "missing.events.jsonl"
        events = list(read_events(log_path))
        assert events == []

    def test_read_events_returns_all(self, tmp_path):
        """read_events returns all events without filter."""
        log_path = tmp_path / "test.events.jsonl"
        log_path.write_text(
            '{"event_type": "A", "val": 1}\n{"event_type": "B", "val": 2}\n{"event_type": "C", "val": 3}\n'
        )
        events = list(read_events(log_path))
        assert len(events) == 3
        assert [e["event_type"] for e in events] == ["A", "B", "C"]

    def test_read_events_filters_by_type(self, tmp_path):
        """read_events filters by event_type when specified."""
        log_path = tmp_path / "test.events.jsonl"
        log_path.write_text(
            '{"event_type": "TermCandidateObserved", "term": "a"}\n'
            '{"event_type": "SemanticCheckEvaluated", "step_id": "s1"}\n'
            '{"event_type": "TermCandidateObserved", "term": "b"}\n'
        )
        events = list(read_events(log_path, event_type="TermCandidateObserved"))
        assert len(events) == 2
        assert events[0]["term"] == "a"
        assert events[1]["term"] == "b"

    def test_read_events_skips_malformed_lines(self, tmp_path):
        """Malformed JSON lines are skipped with warning."""
        log_path = tmp_path / "test.events.jsonl"
        log_path.write_text('{"event_type": "A", "val": 1}\nnot valid json\n{"event_type": "B", "val": 2}\n')
        events = list(read_events(log_path))
        assert len(events) == 2

    def test_read_events_skips_blank_lines(self, tmp_path):
        """Blank lines are skipped."""
        log_path = tmp_path / "test.events.jsonl"
        log_path.write_text('{"event_type": "A"}\n\n   \n{"event_type": "B"}\n')
        events = list(read_events(log_path))
        assert len(events) == 2

    def test_round_trip_append_read(self, tmp_path):
        """Events survive round-trip: append_event -> read_events."""
        log_path = tmp_path / "test.events.jsonl"

        original = build_term_candidate_observed(
            term="workspace",
            source_step="step-001",
            actor_id="user:alice",
            confidence=0.8,
            extraction_method="casing_pattern",
            context="description field",
            mission_id="041-mission",
            run_id="run-001",
            timestamp="2026-02-16T12:00:00+00:00",
        )
        append_event(original, log_path)

        events = list(read_events(log_path))
        assert len(events) == 1
        assert events[0]["term"] == "workspace"
        assert events[0]["confidence"] == 0.8
        assert events[0]["event_type"] == "TermCandidateObserved"

    def test_multiple_appends_preserve_order(self, tmp_path):
        """Multiple appends maintain insertion order."""
        log_path = tmp_path / "test.events.jsonl"

        for i in range(10):
            append_event(_term_event(f"term{i}"), log_path)

        events = list(read_events(log_path))
        assert [event["term"] for event in events] == [f"term{i}" for i in range(10)]


# ---------------------------------------------------------------------------
# Contract refusal: no local fallback (#6399)
# ---------------------------------------------------------------------------


class TestContractRefusal:
    """A record the contract refuses is not written by any path."""

    def test_emit_with_repo_root_writes_jsonl(self, tmp_path, sample_extracted_term, mock_context):
        emit_term_candidate_observed(
            term=sample_extracted_term,
            context=mock_context,
            repo_root=tmp_path,
        )
        events_dir = tmp_path / ".kittify" / "events" / "glossary"
        jsonl_files = list(events_dir.glob("*.events.jsonl"))
        assert len(jsonl_files) == 1

    def test_emit_without_repo_root_does_not_write(self, sample_extracted_term, mock_context, tmp_path):
        emit_term_candidate_observed(
            term=sample_extracted_term,
            context=mock_context,
            repo_root=None,
        )
        events_dir = tmp_path / ".kittify" / "events" / "glossary"
        assert not events_dir.exists()

    def test_emit_of_a_refused_record_returns_none_and_writes_nothing(
        self, tmp_path, sample_extracted_term, mock_context, caplog
    ):
        """The refusal is logged, the caller gets None, and the log stays empty."""
        invalid = _term_event()
        invalid["confidence"] = "high"
        with patch("glossary.events.build_term_candidate_observed", return_value=invalid):
            event = emit_term_candidate_observed(
                term=sample_extracted_term,
                context=mock_context,
                repo_root=tmp_path,
            )
        assert event is None
        assert "Failed to emit TermCandidateObserved" in caplog.text
        log_path = get_event_log_path(tmp_path, mock_context.mission_id)
        assert not log_path.exists() or log_path.read_text() == ""


# ---------------------------------------------------------------------------
# Torn-tail repair (#6399)
# ---------------------------------------------------------------------------


class TestTornTailRepair:
    """A tail a crash left without a newline is moved aside before the append."""

    def test_fragment_moves_to_sidecar_and_the_append_lands_on_a_whole_line(self, tmp_path, caplog):
        log_path = tmp_path / "torn.events.jsonl"
        append_event(_term_event("before"), log_path)
        whole = log_path.read_bytes()
        with log_path.open("ab") as handle:
            handle.write(b'{"event_type": "TermCandi')

        append_event(_term_event("after"), log_path)

        assert [event["term"] for event in read_events(log_path)] == ["before", "after"]
        assert log_path.read_bytes().startswith(whole)
        sidecar = log_path.with_name(log_path.name + TORN_TAIL_SUFFIX)
        assert sidecar.read_bytes() == b'{"event_type": "TermCandi\n'
        assert "Repaired torn tail" in caplog.text

    def test_a_log_with_no_whole_line_is_moved_aside_entirely(self, tmp_path):
        log_path = tmp_path / "torn.events.jsonl"
        log_path.write_bytes(b"\xef\xbb\xbf")

        append_event(_term_event(), log_path)

        assert log_path.read_bytes() == serialize_record(build_record(_term_event()))
        sidecar = log_path.with_name(log_path.name + TORN_TAIL_SUFFIX)
        assert sidecar.read_bytes() == b"\xef\xbb\xbf\n"

    def test_fragments_accumulate_in_the_sidecar(self, tmp_path):
        log_path = tmp_path / "torn.events.jsonl"
        for fragment in (b"first", b"second"):
            with log_path.open("ab") as handle:
                handle.write(fragment)
            append_event(_term_event(), log_path)
        sidecar = log_path.with_name(log_path.name + TORN_TAIL_SUFFIX)
        assert sidecar.read_bytes() == b"first\nsecond\n"
        assert len(list(read_events(log_path))) == 2

    def test_a_second_repairer_finds_a_whole_tail_and_changes_nothing(self, tmp_path):
        log_path = tmp_path / "whole.events.jsonl"
        append_event(_term_event(), log_path)
        before = log_path.read_bytes()

        assert _repair_torn_tail(log_path) is None
        assert log_path.read_bytes() == before
        assert not log_path.with_name(log_path.name + TORN_TAIL_SUFFIX).exists()

    def test_the_last_newline_is_found_across_scan_blocks(self, tmp_path, monkeypatch):
        monkeypatch.setattr("glossary.events._TAIL_SCAN_BLOCK", 4)
        log_path = tmp_path / "torn.events.jsonl"
        append_event(_term_event(), log_path)
        whole = log_path.read_bytes()
        with log_path.open("ab") as handle:
            handle.write(b"a torn tail longer than one block")

        assert _repair_torn_tail(log_path) is not None
        assert log_path.read_bytes() == whole


# ---------------------------------------------------------------------------
# T037: Event Emission at Middleware Boundaries
# ---------------------------------------------------------------------------


class TestTermCandidateObservedEmission:
    """Tests for emit_term_candidate_observed()."""

    def test_emits_event_returns_dict(self, tmp_path, sample_extracted_term, mock_context):
        """TermCandidateObserved returns event dict."""
        event = emit_term_candidate_observed(
            term=sample_extracted_term,
            context=mock_context,
            repo_root=tmp_path,
        )
        assert event is not None
        assert event["event_type"] == "TermCandidateObserved"
        assert event["term"] == "workspace"
        assert event["confidence"] == 0.8

    def test_returns_event_without_repo_root(self, sample_extracted_term, mock_context):
        """Returns event dict even without repo_root (log only)."""
        event = emit_term_candidate_observed(
            term=sample_extracted_term,
            context=mock_context,
            repo_root=None,
        )
        assert event is not None
        assert event["event_type"] == "TermCandidateObserved"

    def test_event_has_correct_fields(self, tmp_path, sample_extracted_term, mock_context):
        """Event payload has all Feature 007 required fields."""
        event = emit_term_candidate_observed(
            term=sample_extracted_term,
            context=mock_context,
            repo_root=tmp_path,
        )
        required_fields = [
            "event_type",
            "term",
            "source_step",
            "actor_id",
            "confidence",
            "extraction_method",
            "context",
            "mission_id",
            "run_id",
            "timestamp",
        ]
        for field_name in required_fields:
            assert field_name in event, f"Missing field: {field_name}"


class TestSemanticCheckEvaluatedEmission:
    """Tests for emit_semantic_check_evaluated()."""

    def test_emits_event_no_conflicts(self, tmp_path, mock_context):
        """SemanticCheckEvaluated emitted for no-conflict case."""
        event = emit_semantic_check_evaluated(
            context=mock_context,
            conflicts=[],
            repo_root=tmp_path,
        )
        assert event is not None
        assert event["event_type"] == "SemanticCheckEvaluated"
        assert event["blocked"] is False
        assert event["recommended_action"] == "proceed"
        assert event["overall_severity"] == "low"

    def test_emits_event_with_conflicts(self, tmp_path, mock_context, sample_conflict):
        """SemanticCheckEvaluated includes conflict findings."""
        event = emit_semantic_check_evaluated(
            context=mock_context,
            conflicts=[sample_conflict],
            repo_root=tmp_path,
        )
        assert event is not None
        assert len(event["findings"]) == 1
        assert event["overall_severity"] == "high"
        assert event["recommended_action"] == "block"
        assert event["blocked"] is True

    def test_computes_overall_severity_from_max(self, tmp_path, mock_context):
        """Overall severity is the maximum of all conflict severities."""
        low_conflict = SemanticConflict(
            term=TermSurface("term1"),
            conflict_type=ConflictType.UNKNOWN,
            severity=Severity.LOW,
            confidence=0.5,
        )
        med_conflict = SemanticConflict(
            term=TermSurface("term2"),
            conflict_type=ConflictType.UNKNOWN,
            severity=Severity.MEDIUM,
            confidence=0.7,
        )
        event = emit_semantic_check_evaluated(
            context=mock_context,
            conflicts=[low_conflict, med_conflict],
            repo_root=tmp_path,
        )
        assert event["overall_severity"] == "medium"

    def test_effective_strictness_from_context(self, tmp_path, mock_context):
        """Uses effective_strictness from context."""
        mock_context.effective_strictness = Strictness.MAX
        event = emit_semantic_check_evaluated(
            context=mock_context,
            conflicts=[],
            repo_root=tmp_path,
        )
        assert event["effective_strictness"] == "max"

    def test_unresolved_strictness_is_written_as_medium(self, tmp_path, mock_context):
        """An unresolved strictness (None on the context) is written as "medium", never "None".

        The semantic-check middleware emits before the generation gate resolves
        strictness, so the context still carries None here (#6399).
        """
        from spec_kitty_events.persistence import build_record

        mock_context.effective_strictness = None
        event = emit_semantic_check_evaluated(
            context=mock_context,
            conflicts=[],
            repo_root=tmp_path,
        )
        assert event["effective_strictness"] == "medium"
        build_record(event)  # conforms to the spec-kitty-events contract


class TestGenerationBlockedEmission:
    """Tests for emit_generation_blocked_event()."""

    def test_emits_blocked_event(self, tmp_path, sample_conflict):
        """GenerationBlockedBySemanticConflict emitted with conflict details."""
        event = emit_generation_blocked_event(
            step_id="step-001",
            mission_id="041-mission",
            conflicts=[sample_conflict],
            strictness_mode=Strictness.MEDIUM,
            run_id="run-001",
            repo_root=tmp_path,
        )
        assert event is not None
        assert event["event_type"] == "GenerationBlockedBySemanticConflict"
        assert len(event["conflicts"]) == 1
        assert event["strictness_mode"] == "medium"

    def test_serializes_conflicts(self, tmp_path, sample_conflict):
        """Conflict objects are serialized to dicts."""
        event = emit_generation_blocked_event(
            step_id="s",
            mission_id="m",
            conflicts=[sample_conflict],
            strictness_mode=Strictness.MAX,
            repo_root=tmp_path,
        )
        conflict_dict = event["conflicts"][0]
        assert conflict_dict["term"]["surface_text"] == "workspace"
        assert conflict_dict["severity"] == "high"

    def test_handles_string_strictness(self, tmp_path, sample_conflict):
        """Accepts string strictness mode (not just enum)."""
        event = emit_generation_blocked_event(
            step_id="s",
            mission_id="m",
            conflicts=[sample_conflict],
            strictness_mode="medium",
            repo_root=tmp_path,
        )
        assert event["strictness_mode"] == "medium"

    def test_logs_only_without_repo_root(self, sample_conflict):
        """Without repo_root, event is returned but not persisted."""
        event = emit_generation_blocked_event(
            step_id="s",
            mission_id="m",
            conflicts=[sample_conflict],
            strictness_mode=Strictness.MEDIUM,
        )
        assert event is not None
        assert event["event_type"] == "GenerationBlockedBySemanticConflict"


class TestStepCheckpointedEmission:
    """Tests for emit_step_checkpointed()."""

    def test_emits_checkpoint_event(self, tmp_path):
        """StepCheckpointed emitted with correct fields."""
        from glossary.checkpoint import create_checkpoint, ScopeRef

        checkpoint = create_checkpoint(
            mission_id="041-mission",
            run_id="run-001",
            step_id="step-001",
            strictness=Strictness.MEDIUM,
            scope_refs=[ScopeRef(GlossaryScope.TEAM_DOMAIN, "v3")],
            inputs={"description": "test"},
            cursor="pre_generation_gate",
        )

        event = emit_step_checkpointed(checkpoint, project_root=tmp_path)
        assert event is not None
        assert event["event_type"] == "StepCheckpointed"
        assert event["step_id"] == "step-001"
        assert event["cursor"] == "pre_generation_gate"

    def test_logs_only_without_project_root(self):
        """Without project_root, checkpoint is logged but not persisted."""
        from glossary.checkpoint import create_checkpoint

        checkpoint = create_checkpoint(
            mission_id="m",
            run_id="r",
            step_id="s",
            strictness=Strictness.OFF,
            scope_refs=[],
            inputs={},
            cursor="pre_generation_gate",
        )

        event = emit_step_checkpointed(checkpoint, project_root=None)
        assert event is not None
        assert event["event_type"] == "StepCheckpointed"


class TestClarificationEmission:
    """Tests for emit_clarification_requested/resolved/sense_updated."""

    def test_requested_event(self, tmp_path, mock_context, sample_conflict):
        """GlossaryClarificationRequested emitted for a conflict."""
        event = emit_clarification_requested(
            conflict=sample_conflict,
            context=mock_context,
            conflict_id="test-uuid",
            repo_root=tmp_path,
        )
        assert event is not None
        assert event["event_type"] == "GlossaryClarificationRequested"
        assert event["term"] == "workspace"
        assert event["conflict_id"] == "test-uuid"
        assert len(event["options"]) == 2
        assert event["urgency"] == "high"

    @pytest.mark.parametrize("prior_check_id", ["absent", None, ""])
    def test_requested_omits_semantic_check_event_id_without_a_prior_check(
        self, tmp_path, mock_context, sample_conflict, prior_check_id
    ):
        """No preceding semantic check leaves the reference out instead of writing "" (#6399)."""
        from spec_kitty_events.persistence import build_record

        if prior_check_id != "absent":
            mock_context.semantic_check_event_id = prior_check_id
        event = emit_clarification_requested(
            conflict=sample_conflict,
            context=mock_context,
            repo_root=tmp_path,
        )
        assert "semantic_check_event_id" not in event
        build_record(event)  # conforms to the spec-kitty-events contract

    def test_requested_carries_the_prior_semantic_check_event_id(self, tmp_path, mock_context, sample_conflict):
        """A preceding semantic check is referenced by its event id."""
        mock_context.semantic_check_event_id = "check-001"
        event = emit_clarification_requested(
            conflict=sample_conflict,
            context=mock_context,
            repo_root=tmp_path,
        )
        assert event["semantic_check_event_id"] == "check-001"

    def test_requested_auto_generates_id(self, tmp_path, mock_context, sample_conflict):
        """conflict_id is auto-generated if not provided."""
        event = emit_clarification_requested(
            conflict=sample_conflict,
            context=mock_context,
            repo_root=tmp_path,
        )
        assert len(event["conflict_id"]) == 36  # UUID

    def test_resolved_event(self, tmp_path, mock_context, sample_conflict):
        """GlossaryClarificationResolved emitted with selected sense."""
        selected = sample_conflict.candidate_senses[0]
        event = emit_clarification_resolved(
            conflict_id="test-uuid",
            conflict=sample_conflict,
            selected_sense=selected,
            context=mock_context,
            repo_root=tmp_path,
        )
        assert event is not None
        assert event["event_type"] == "GlossaryClarificationResolved"
        assert event["conflict_id"] == "test-uuid"
        assert event["selected_sense"]["definition"] == "Git worktree directory"
        assert event["resolution_mode"] == "interactive"

    def test_sense_updated_event(self, tmp_path, mock_context, sample_conflict):
        """GlossarySenseUpdated emitted for custom sense."""
        event = emit_sense_updated(
            conflict=sample_conflict,
            custom_definition="A project workspace directory",
            scope_value="team_domain",
            context=mock_context,
            repo_root=tmp_path,
        )
        assert event is not None
        assert event["event_type"] == "GlossarySenseUpdated"
        assert event["new_sense"]["definition"] == "A project workspace directory"
        assert event["update_type"] == "create"

    def test_scope_activated_event(self, tmp_path):
        """GlossaryScopeActivated emitted correctly."""
        event = emit_scope_activated(
            scope_id="team_domain",
            glossary_version_id="v3",
            mission_id="041-mission",
            run_id="run-001",
            repo_root=tmp_path,
        )
        assert event is not None
        assert event["event_type"] == "GlossaryScopeActivated"
        assert event["scope_id"] == "team_domain"


# ---------------------------------------------------------------------------
# T037: Event Ordering
# ---------------------------------------------------------------------------


class TestEventOrdering:
    """Tests for event ordering across middleware pipeline."""

    def test_pipeline_event_order_returns_correct_types(
        self, tmp_path, mock_context, sample_extracted_term, sample_conflict
    ):
        """Events are emitted in pipeline order: extraction -> check -> gate."""
        # 1. Extraction emits TermCandidateObserved
        e1 = emit_term_candidate_observed(
            term=sample_extracted_term,
            context=mock_context,
            repo_root=tmp_path,
        )

        # 2. Semantic check emits SemanticCheckEvaluated
        e2 = emit_semantic_check_evaluated(
            context=mock_context,
            conflicts=[sample_conflict],
            repo_root=tmp_path,
        )

        # 3. Gate emits GenerationBlockedBySemanticConflict
        e3 = emit_generation_blocked_event(
            step_id=mock_context.step_id,
            mission_id=mock_context.mission_id,
            conflicts=[sample_conflict],
            strictness_mode=Strictness.MEDIUM,
            run_id=mock_context.run_id,
            repo_root=tmp_path,
        )

        # Verify event types returned
        assert e1["event_type"] == "TermCandidateObserved"
        assert e2["event_type"] == "SemanticCheckEvaluated"
        assert e3["event_type"] == "GenerationBlockedBySemanticConflict"

    def test_full_pipeline_with_clarification_types(
        self, tmp_path, mock_context, sample_extracted_term, sample_conflict
    ):
        """Full pipeline returns all 5 event types in correct order."""
        # 1. Scope activation
        e1 = emit_scope_activated(
            scope_id="team_domain",
            glossary_version_id="v1",
            mission_id=mock_context.mission_id,
            run_id=mock_context.run_id,
            repo_root=tmp_path,
        )

        # 2. Extraction
        e2 = emit_term_candidate_observed(
            term=sample_extracted_term,
            context=mock_context,
            repo_root=tmp_path,
        )

        # 3. Check
        e3 = emit_semantic_check_evaluated(
            context=mock_context,
            conflicts=[sample_conflict],
            repo_root=tmp_path,
        )

        # 4. Clarification requested
        e4 = emit_clarification_requested(
            conflict=sample_conflict,
            context=mock_context,
            conflict_id="c-001",
            repo_root=tmp_path,
        )

        # 5. Clarification resolved
        e5 = emit_clarification_resolved(
            conflict_id="c-001",
            conflict=sample_conflict,
            selected_sense=sample_conflict.candidate_senses[0],
            context=mock_context,
            repo_root=tmp_path,
        )

        # Verify all 5 event types
        expected_types = [
            "GlossaryScopeActivated",
            "TermCandidateObserved",
            "SemanticCheckEvaluated",
            "GlossaryClarificationRequested",
            "GlossaryClarificationResolved",
        ]
        actual_types = [e["event_type"] for e in [e1, e2, e3, e4, e5]]
        assert actual_types == expected_types
        assert e4["semantic_check_event_id"] == e3["event_id"]

    def test_multiple_terms_emit_multiple_events(self, tmp_path, mock_context):
        """Each extracted term produces its own TermCandidateObserved event."""
        terms = [
            ExtractedTerm("workspace", "metadata_hint", 1.0, "workspace"),
            ExtractedTerm("mission", "metadata_hint", 1.0, "mission"),
            ExtractedTerm("api", "casing_pattern", 0.8, "API"),
        ]

        events = []
        for term in terms:
            e = emit_term_candidate_observed(
                term=term,
                context=mock_context,
                repo_root=tmp_path,
            )
            events.append(e)

        assert len(events) == 3
        assert all(e["event_type"] == "TermCandidateObserved" for e in events)


# ---------------------------------------------------------------------------
# ClarificationMiddleware emits 3 clarification events
# ---------------------------------------------------------------------------


class TestClarificationMiddlewareEmitsEvents:
    """Tests: ClarificationMiddleware must emit:
    - GlossaryClarificationRequested when user defers
    - GlossaryClarificationResolved when user selects candidate
    - GlossarySenseUpdated when user provides custom sense
    """

    def test_deferred_emits_clarification_requested(self, tmp_path, mock_context, sample_conflict):
        """ClarificationMiddleware emits GlossaryClarificationRequested when deferring."""
        from glossary.clarification import ClarificationMiddleware

        mock_context.conflicts = [sample_conflict]

        # Patch at the events module level (clarification.py uses local imports)
        with patch("glossary.events.emit_clarification_requested") as mock_emit:
            mock_emit.return_value = {"event_type": "GlossaryClarificationRequested"}
            middleware = ClarificationMiddleware(repo_root=tmp_path)
            middleware.process(mock_context)
            mock_emit.assert_called_once()
            call_kwargs = mock_emit.call_args
            assert call_kwargs[1]["conflict"] == sample_conflict
            assert call_kwargs[1]["repo_root"] == tmp_path

    def test_select_emits_clarification_resolved(self, tmp_path, mock_context, sample_conflict):
        """ClarificationMiddleware emits GlossaryClarificationResolved on selection."""
        from glossary.clarification import ClarificationMiddleware

        mock_context.conflicts = [sample_conflict]

        def fake_prompt(conflict, candidates):
            return ("select", None)

        middleware = ClarificationMiddleware(repo_root=tmp_path, prompt_fn=fake_prompt)

        # Patch at the events module level (clarification.py uses local imports)
        with (
            patch("glossary.events.emit_clarification_requested") as mock_requested,
            patch("glossary.events.emit_clarification_resolved") as mock_emit,
        ):
            mock_requested.return_value = {"event_type": "GlossaryClarificationRequested"}
            mock_emit.return_value = {"event_type": "GlossaryClarificationResolved"}
            middleware.process(mock_context)
            mock_requested.assert_called_once()
            mock_emit.assert_called_once()
            call_kwargs = mock_emit.call_args[1]
            assert call_kwargs["conflict"] == sample_conflict
            assert call_kwargs["resolution_mode"] == "interactive"
            assert call_kwargs["repo_root"] == tmp_path

    def test_custom_sense_emits_sense_updated(self, tmp_path, mock_context, sample_conflict):
        """ClarificationMiddleware emits GlossarySenseUpdated on custom definition."""
        from glossary.clarification import ClarificationMiddleware

        mock_context.conflicts = [sample_conflict]

        def fake_prompt(conflict, candidates):
            return ("custom", "My custom definition")

        middleware = ClarificationMiddleware(repo_root=tmp_path, prompt_fn=fake_prompt)

        # Patch at the events module level (clarification.py uses local imports)
        with patch("glossary.events.emit_sense_updated") as mock_emit:
            mock_emit.return_value = {"event_type": "GlossarySenseUpdated"}
            middleware.process(mock_context)
            mock_emit.assert_called_once()
            call_kwargs = mock_emit.call_args[1]
            assert call_kwargs["conflict"] == sample_conflict
            assert call_kwargs["custom_definition"] == "My custom definition"
            assert call_kwargs["repo_root"] == tmp_path

    def test_custom_sense_updates_store_for_same_run_resolution(self, tmp_path, mock_context, sample_conflict):
        """Custom sense updates are immediately visible to subsequent lookups."""
        from glossary.clarification import ClarificationMiddleware
        from glossary.store import GlossaryStore

        mock_context.conflicts = [sample_conflict]

        def fake_prompt(conflict, candidates):
            return ("custom", "My custom definition")

        store = GlossaryStore(event_log_path=tmp_path / "events.jsonl")
        middleware = ClarificationMiddleware(
            repo_root=tmp_path,
            prompt_fn=fake_prompt,
            glossary_store=store,
        )

        with patch("glossary.events.emit_sense_updated") as mock_emit:
            mock_emit.return_value = {"event_type": "GlossarySenseUpdated"}
            middleware.process(mock_context)

        senses = store.lookup("workspace", ("team_domain",))
        assert any(s.definition == "My custom definition" for s in senses)

    def test_middleware_removes_resolved_conflicts(self, tmp_path, mock_context, sample_conflict):
        """Resolved conflicts are removed from context.conflicts."""
        from glossary.clarification import ClarificationMiddleware

        mock_context.conflicts = [sample_conflict]

        def fake_prompt(conflict, candidates):
            return ("select", None)

        middleware = ClarificationMiddleware(repo_root=tmp_path, prompt_fn=fake_prompt)
        middleware.process(mock_context)

        assert len(mock_context.conflicts) == 0
        assert len(mock_context.resolved_conflicts) == 1

    def test_no_conflicts_returns_context_unchanged(self, tmp_path, mock_context):
        """No conflicts means no events emitted."""
        from glossary.clarification import ClarificationMiddleware

        mock_context.conflicts = []
        middleware = ClarificationMiddleware(repo_root=tmp_path)
        result = middleware.process(mock_context)
        assert result is mock_context


# ---------------------------------------------------------------------------
# Scope activation emits GlossaryScopeActivated
# ---------------------------------------------------------------------------


class TestScopeActivationEmitsEvent:
    """Tests: scope activation calls emit_scope_activated."""

    def test_activate_scope_calls_emit_scope_activated(self, tmp_path):
        """activate_scope() calls emit_scope_activated with correct params."""
        from glossary.scope import activate_scope, GlossaryScope

        # Patch at events module level (scope.py uses local import inside activate_scope)
        with patch("glossary.events.emit_scope_activated") as mock_emit:
            mock_emit.return_value = {"event_type": "GlossaryScopeActivated"}
            activate_scope(
                scope=GlossaryScope.TEAM_DOMAIN,
                version_id="v3",
                mission_id="041-mission",
                run_id="run-001",
                repo_root=tmp_path,
            )
            mock_emit.assert_called_once_with(
                scope_id="team_domain",
                glossary_version_id="v3",
                mission_id="041-mission",
                run_id="run-001",
                repo_root=tmp_path,
            )

    def test_activate_scope_no_repo_root(self):
        """activate_scope() works without repo_root (log only)."""
        from glossary.scope import activate_scope, GlossaryScope

        # Patch at events module level (scope.py uses local import inside activate_scope)
        with patch("glossary.events.emit_scope_activated") as mock_emit:
            mock_emit.return_value = {"event_type": "GlossaryScopeActivated"}
            activate_scope(
                scope=GlossaryScope.MISSION_LOCAL,
                version_id="v1",
                mission_id="m",
                run_id="r",
                repo_root=None,
            )
            mock_emit.assert_called_once()


# ---------------------------------------------------------------------------
# Every write goes through the spec-kitty-events write contract (#6399)
# ---------------------------------------------------------------------------


class TestWritesThroughTheContract:
    """Every glossary write goes through the spec-kitty-events write contract (#6399)."""

    def test_persist_event_writes_the_contract_line(self, tmp_path):
        event = _term_event()
        _persist_event(event, tmp_path, "test-mission")
        log_path = get_event_log_path(tmp_path, "test-mission")
        assert log_path.read_bytes() == serialize_record(build_record(event))

    def test_persist_event_adds_an_event_id(self, tmp_path):
        event = _term_event()
        event.pop("event_id", None)
        _persist_event(event, tmp_path, "test-mission")
        assert isinstance(event["event_id"], str)

    def test_persist_event_propagates_a_refusal(self, tmp_path):
        with pytest.raises(LedgerValidationError):
            _persist_event({"event_type": "NotAGlossaryEvent"}, tmp_path, "test-mission")

    def test_sense_updated_is_written_through_the_contract(self, tmp_path, mock_context, sample_conflict):
        """GlossarySenseUpdated takes the same path as every other glossary event."""
        with patch("glossary.events._ledger_append", wraps=events_module._ledger_append) as ledger_append:
            event = emit_sense_updated(
                conflict=sample_conflict,
                custom_definition="A git worktree",
                scope_value="team_domain",
                context=mock_context,
                repo_root=tmp_path,
            )
        assert event is not None
        ledger_append.assert_called_once()
        log_path = get_event_log_path(tmp_path, mock_context.mission_id)
        assert log_path.read_bytes() == serialize_record(build_record(event))

    def test_no_local_fallback_writer_remains(self):
        """The retired fallback writer and its availability flag are gone."""
        assert not hasattr(events_module, "_local_append_event")
        assert not hasattr(events_module, "EVENTS_AVAILABLE")


# ---------------------------------------------------------------------------
# T037: Middleware Integration
# ---------------------------------------------------------------------------


class TestMiddlewareEventIntegration:
    """Tests for event emission at actual middleware boundaries."""

    def test_extraction_middleware_emits_events(self, tmp_path):
        """GlossaryCandidateExtractionMiddleware emits TermCandidateObserved."""
        from glossary.middleware import (
            GlossaryCandidateExtractionMiddleware,
            MockContext,
        )

        middleware = GlossaryCandidateExtractionMiddleware(repo_root=tmp_path)
        context = MockContext(
            metadata={
                "glossary_watch_terms": ["workspace"],
            },
            step_input={"description": 'The "workspace" is important'},
            step_output={},
        )
        # Add context attributes needed by event emission
        context.step_id = "step-001"  # type: ignore[attr-defined]
        context.mission_id = "test-mission"  # type: ignore[attr-defined]
        context.run_id = "run-001"  # type: ignore[attr-defined]
        context.actor_id = "user:test"  # type: ignore[attr-defined]

        middleware.process(context)

        # Should have at least one extracted term
        assert len(context.extracted_terms) >= 1

    def test_generation_gate_emits_blocked_event(self, tmp_path, sample_conflict):
        """GenerationGateMiddleware raises BlockedByConflict."""
        from glossary.middleware import GenerationGateMiddleware
        from glossary.exceptions import BlockedByConflict

        context = MockContext(
            step_id="step-001",
            mission_id="test-mission",
            run_id="run-001",
            conflicts=[sample_conflict],
        )
        context.inputs = {"desc": "test"}

        gate = GenerationGateMiddleware(
            repo_root=tmp_path,
            runtime_override=Strictness.MEDIUM,
        )

        with pytest.raises(BlockedByConflict):
            gate.process(context)


# ---------------------------------------------------------------------------
# All 8 Event Types Coverage
# ---------------------------------------------------------------------------


class TestAll8EventTypes:
    """Verify all 8 canonical event types can be emitted."""

    def test_all_8_event_types_have_emitters(self):
        """All 8 event types have corresponding emit_* functions."""
        from glossary import events

        assert callable(events.emit_scope_activated)
        assert callable(events.emit_term_candidate_observed)
        assert callable(events.emit_semantic_check_evaluated)
        assert callable(events.emit_generation_blocked_event)
        assert callable(events.emit_clarification_requested)
        assert callable(events.emit_clarification_resolved)
        assert callable(events.emit_sense_updated)
        assert callable(events.emit_step_checkpointed)

    def test_all_8_event_types_return_correct_event_type(
        self, tmp_path, mock_context, sample_conflict, sample_extracted_term
    ):
        """Each emitter returns dict with correct event_type field."""
        from glossary.checkpoint import create_checkpoint

        events_returned = {}

        # 1. GlossaryScopeActivated
        events_returned["scope"] = emit_scope_activated(
            scope_id="team_domain",
            glossary_version_id="v1",
            mission_id="m",
            run_id="r",
        )

        # 2. TermCandidateObserved
        events_returned["term"] = emit_term_candidate_observed(
            term=sample_extracted_term,
            context=mock_context,
        )

        # 3. SemanticCheckEvaluated
        events_returned["check"] = emit_semantic_check_evaluated(
            context=mock_context,
            conflicts=[],
        )

        # 4. GenerationBlockedBySemanticConflict
        events_returned["blocked"] = emit_generation_blocked_event(
            step_id="s",
            mission_id="m",
            conflicts=[sample_conflict],
            strictness_mode="medium",
        )

        # 5. GlossaryClarificationRequested
        events_returned["requested"] = emit_clarification_requested(
            conflict=sample_conflict,
            context=mock_context,
        )

        # 6. GlossaryClarificationResolved
        events_returned["resolved"] = emit_clarification_resolved(
            conflict_id="c-1",
            conflict=sample_conflict,
            selected_sense=sample_conflict.candidate_senses[0],
            context=mock_context,
        )

        # 7. GlossarySenseUpdated
        events_returned["sense"] = emit_sense_updated(
            conflict=sample_conflict,
            custom_definition="Custom def",
            scope_value="team_domain",
            context=mock_context,
        )

        # 8. StepCheckpointed
        ckpt = create_checkpoint(
            mission_id="m",
            run_id="r",
            step_id="s",
            strictness=Strictness.MEDIUM,
            scope_refs=[],
            inputs={},
            cursor="pre_generation_gate",
        )
        events_returned["checkpoint"] = emit_step_checkpointed(ckpt)

        expected = {
            "scope": "GlossaryScopeActivated",
            "term": "TermCandidateObserved",
            "check": "SemanticCheckEvaluated",
            "blocked": "GenerationBlockedBySemanticConflict",
            "requested": "GlossaryClarificationRequested",
            "resolved": "GlossaryClarificationResolved",
            "sense": "GlossarySenseUpdated",
            "checkpoint": "StepCheckpointed",
        }

        for key, expected_type in expected.items():
            assert events_returned[key] is not None, f"{key} emitter returned None"
            assert events_returned[key]["event_type"] == expected_type, (
                f"{key}: expected {expected_type}, got {events_returned[key].get('event_type')}"
            )


# ---------------------------------------------------------------------------
# T039: Error Handling and Edge Cases
# ---------------------------------------------------------------------------


class TestEventEmissionErrorHandling:
    """Tests for error handling in event emission."""

    def test_emission_does_not_crash_on_error(self, mock_context, sample_extracted_term):
        """A failed write returns None and does not raise to the caller."""
        bad_root = Path("/dev/null/not/a/path")
        event = emit_term_candidate_observed(
            term=sample_extracted_term,
            context=mock_context,
            repo_root=bad_root,
        )
        assert event is None

    def test_emission_returns_none_when_the_write_fails(self, mock_context, sample_extracted_term, tmp_path):
        """An I/O failure in the contract writer is logged and nothing falls back."""
        with patch("glossary.events._ledger_append", side_effect=OSError("disk full")):
            event = emit_term_candidate_observed(
                term=sample_extracted_term,
                context=mock_context,
                repo_root=tmp_path,
            )
        assert event is None
        assert not get_event_log_path(tmp_path, mock_context.mission_id).exists()


class TestEventLogEdgeCases:
    """Edge cases for event log handling."""

    def test_empty_conflicts_list(self, tmp_path, mock_context):
        """Empty conflicts list produces valid event."""
        event = emit_semantic_check_evaluated(
            context=mock_context,
            conflicts=[],
            repo_root=tmp_path,
        )
        assert event["findings"] == []
        assert event["blocked"] is False

    def test_large_number_of_events(self, tmp_path):
        """Event log handles many events without issues."""
        log_path = tmp_path / "large.events.jsonl"
        for i in range(500):
            append_event(_term_event(f"term{i}"), log_path)

        events = list(read_events(log_path))
        assert len(events) == 500

    def test_unicode_in_events(self, tmp_path):
        """Unicode characters are handled correctly."""
        log_path = tmp_path / "unicode.events.jsonl"
        event = _term_event("Arbeitsbereich")
        append_event(event, log_path)

        events = list(read_events(log_path))
        assert len(events) == 1
        assert events[0]["term"] == "Arbeitsbereich"

    def test_concurrent_writes_produce_valid_jsonl(self, tmp_path):
        """Multiple sequential appends produce valid JSONL (each line parseable)."""
        log_path = tmp_path / "concurrent.events.jsonl"

        # Simulate concurrent-ish writes
        for i in range(20):
            append_event(_term_event(f"term{i}"), log_path)

        # All lines should parse
        events = list(read_events(log_path))
        assert len(events) == 20

    def test_filter_by_nonexistent_type(self, tmp_path):
        """Filtering by nonexistent event_type returns nothing."""
        log_path = tmp_path / "test.events.jsonl"
        append_event(_term_event(), log_path)
        events = list(read_events(log_path, event_type="Nonexistent"))
        assert events == []

    def test_event_without_event_type_field(self, tmp_path):
        """Events without event_type field are returned when no filter."""
        log_path = tmp_path / "test.events.jsonl"
        log_path.write_text('{"data": "no type"}\n')
        events = list(read_events(log_path))
        assert len(events) == 1
        assert events[0]["data"] == "no type"

    def test_event_without_event_type_filtered_out(self, tmp_path):
        """Events without event_type are filtered out when type filter set."""
        log_path = tmp_path / "test.events.jsonl"
        log_path.write_text('{"data": "no type"}\n')
        events = list(read_events(log_path, event_type="SomeType"))
        assert events == []
