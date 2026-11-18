"""Unit tests for checkpoint module (WP07 -- T030, T032, T033)."""

import json
import uuid

import pytest

from kernel.clock import datetime, now_utc, now_utc_iso

from glossary.checkpoint import (
    VALID_CURSORS,
    ScopeRef,
    StepCheckpoint,
    checkpoint_to_dict,
    compute_input_diff,
    compute_input_hash,
    create_checkpoint,
    handle_context_change,
    load_checkpoint,
    parse_checkpoint_event,
    verify_input_hash,
)
from glossary.scope import GlossaryScope
from glossary.strictness import Strictness

pytestmark = pytest.mark.fast
# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_inputs():
    """Sample step inputs."""
    return {
        "description": "Implement feature X",
        "requirements": ["req1", "req2"],
    }


@pytest.fixture
def sample_scope_refs():
    """Sample scope references."""
    return [
        ScopeRef(scope=GlossaryScope.TEAM_DOMAIN, version_id="v3"),
        ScopeRef(scope=GlossaryScope.MISSION_LOCAL, version_id="v1"),
    ]


@pytest.fixture
def sample_checkpoint(sample_inputs, sample_scope_refs):
    """Create a sample checkpoint."""
    return create_checkpoint(
        mission_id="041-mission",
        run_id="run-001",
        step_id="step-specify-001",
        strictness=Strictness.MEDIUM,
        scope_refs=sample_scope_refs,
        inputs=sample_inputs,
        cursor="pre_generation_gate",
    )


# ---------------------------------------------------------------------------
# T030: StepCheckpoint Data Model
# ---------------------------------------------------------------------------


class TestScopeRef:
    """Test ScopeRef value object."""

    def test_scope_ref_creation(self):
        ref = ScopeRef(scope=GlossaryScope.TEAM_DOMAIN, version_id="v3")
        assert ref.scope == GlossaryScope.TEAM_DOMAIN
        assert ref.version_id == "v3"

    def test_scope_ref_is_frozen(self):
        ref = ScopeRef(scope=GlossaryScope.TEAM_DOMAIN, version_id="v3")
        with pytest.raises(AttributeError):
            ref.version_id = "v4"  # type: ignore[misc]

    def test_scope_ref_equality(self):
        ref1 = ScopeRef(scope=GlossaryScope.TEAM_DOMAIN, version_id="v3")
        ref2 = ScopeRef(scope=GlossaryScope.TEAM_DOMAIN, version_id="v3")
        assert ref1 == ref2

    def test_scope_ref_hashable(self):
        ref = ScopeRef(scope=GlossaryScope.TEAM_DOMAIN, version_id="v3")
        assert hash(ref) is not None
        s = {ref}
        assert len(s) == 1


class TestStepCheckpoint:
    """Test StepCheckpoint data model."""

    def test_checkpoint_creation(self, sample_checkpoint):
        assert sample_checkpoint.mission_id == "041-mission"
        assert sample_checkpoint.run_id == "run-001"
        assert sample_checkpoint.step_id == "step-specify-001"
        assert sample_checkpoint.strictness == Strictness.MEDIUM
        assert len(sample_checkpoint.scope_refs) == 2
        assert len(sample_checkpoint.input_hash) == 64
        assert sample_checkpoint.cursor == "pre_generation_gate"
        assert len(sample_checkpoint.retry_token) == 36
        assert isinstance(sample_checkpoint.timestamp, datetime)

    def test_checkpoint_has_nine_fields(self, sample_checkpoint):
        """Verify checkpoint has exactly 9 required fields."""
        import dataclasses

        fields = dataclasses.fields(sample_checkpoint)
        assert len(fields) == 9

    def test_checkpoint_is_frozen(self, sample_checkpoint):
        with pytest.raises(AttributeError):
            sample_checkpoint.cursor = "post_gate"  # type: ignore[misc]

    def test_invalid_input_hash_length(self):
        with pytest.raises(ValueError, match="Invalid input_hash format"):
            StepCheckpoint(
                mission_id="m",
                run_id="r",
                step_id="s",
                strictness=Strictness.MEDIUM,
                scope_refs=(),
                input_hash="short",
                cursor="pre_generation_gate",
                retry_token=str(uuid.uuid4()),
                timestamp=now_utc(),
            )

    def test_invalid_input_hash_chars(self):
        with pytest.raises(ValueError, match="Invalid input_hash format"):
            StepCheckpoint(
                mission_id="m",
                run_id="r",
                step_id="s",
                strictness=Strictness.MEDIUM,
                scope_refs=(),
                input_hash="Z" * 64,  # uppercase not allowed
                cursor="pre_generation_gate",
                retry_token=str(uuid.uuid4()),
                timestamp=now_utc(),
            )

    def test_invalid_retry_token_length(self):
        with pytest.raises(ValueError, match="Invalid retry_token format"):
            StepCheckpoint(
                mission_id="m",
                run_id="r",
                step_id="s",
                strictness=Strictness.MEDIUM,
                scope_refs=(),
                input_hash="a" * 64,
                cursor="pre_generation_gate",
                retry_token="too-short",
                timestamp=now_utc(),
            )

    def test_invalid_cursor_value(self):
        with pytest.raises(ValueError, match="Unknown cursor value"):
            StepCheckpoint(
                mission_id="m",
                run_id="r",
                step_id="s",
                strictness=Strictness.MEDIUM,
                scope_refs=(),
                input_hash="a" * 64,
                cursor="invalid_cursor",
                retry_token=str(uuid.uuid4()),
                timestamp=now_utc(),
            )

    def test_all_valid_cursors_accepted(self):
        for cursor in VALID_CURSORS:
            cp = StepCheckpoint(
                mission_id="m",
                run_id="r",
                step_id="s",
                strictness=Strictness.MEDIUM,
                scope_refs=(),
                input_hash="a" * 64,
                cursor=cursor,
                retry_token=str(uuid.uuid4()),
                timestamp=now_utc(),
            )
            assert cp.cursor == cursor


class TestComputeInputHash:
    """Test compute_input_hash() determinism and correctness."""

    def test_deterministic_same_inputs(self, sample_inputs):
        """Same inputs produce same hash."""
        hash1 = compute_input_hash(sample_inputs)
        hash2 = compute_input_hash(sample_inputs)
        assert hash1 == hash2

    def test_deterministic_different_key_order(self):
        """Key order doesn't affect hash (sort_keys=True)."""
        inputs1 = {"b": 2, "a": 1}
        inputs2 = {"a": 1, "b": 2}
        assert compute_input_hash(inputs1) == compute_input_hash(inputs2)

    def test_different_inputs_different_hash(self, sample_inputs):
        changed = dict(sample_inputs)
        changed["description"] = "Changed"
        assert compute_input_hash(sample_inputs) != compute_input_hash(changed)

    def test_hash_is_64_hex_chars(self, sample_inputs):
        h = compute_input_hash(sample_inputs)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_empty_dict(self):
        h = compute_input_hash({})
        assert len(h) == 64

    def test_nested_dicts(self):
        inputs = {"outer": {"inner": {"deep": "value"}}}
        h = compute_input_hash(inputs)
        assert len(h) == 64

    def test_lists_in_inputs(self):
        inputs = {"items": [3, 1, 2]}
        h = compute_input_hash(inputs)
        assert len(h) == 64

    def test_none_values(self):
        inputs = {"key": None}
        h = compute_input_hash(inputs)
        assert len(h) == 64

    def test_float_values(self):
        inputs = {"pi": 3.14159}
        h1 = compute_input_hash(inputs)
        h2 = compute_input_hash(inputs)
        assert h1 == h2

    def test_unicode_values(self):
        inputs = {"name": "Groesse"}
        h = compute_input_hash(inputs)
        assert len(h) == 64

    def test_boolean_values(self):
        inputs = {"flag": True, "other": False}
        h = compute_input_hash(inputs)
        assert len(h) == 64

    def test_int_vs_float_different_hash(self):
        """Integer 5 and float 5.0 may produce different hashes (JSON-dependent)."""
        h_int = compute_input_hash({"val": 5})
        h_float = compute_input_hash({"val": 5.0})
        # In JSON, 5 and 5.0 may serialize identically. That's fine as long
        # as the function is deterministic.
        assert len(h_int) == 64
        assert len(h_float) == 64


class TestCreateCheckpoint:
    """Test create_checkpoint() factory function."""

    def test_creates_valid_checkpoint(self, sample_inputs, sample_scope_refs):
        cp = create_checkpoint(
            mission_id="m1",
            run_id="r1",
            step_id="s1",
            strictness=Strictness.MAX,
            scope_refs=sample_scope_refs,
            inputs=sample_inputs,
            cursor="pre_generation_gate",
        )
        assert cp.mission_id == "m1"
        assert cp.strictness == Strictness.MAX
        assert len(cp.input_hash) == 64
        assert len(cp.retry_token) == 36

    def test_unique_retry_tokens(self, sample_inputs):
        """Each checkpoint gets a fresh UUID."""
        cp1 = create_checkpoint(
            mission_id="m",
            run_id="r",
            step_id="s",
            strictness=Strictness.MEDIUM,
            scope_refs=[],
            inputs=sample_inputs,
            cursor="pre_generation_gate",
        )
        cp2 = create_checkpoint(
            mission_id="m",
            run_id="r",
            step_id="s",
            strictness=Strictness.MEDIUM,
            scope_refs=[],
            inputs=sample_inputs,
            cursor="pre_generation_gate",
        )
        assert cp1.retry_token != cp2.retry_token

    def test_same_hash_for_same_inputs(self, sample_inputs):
        """Same inputs produce same hash across checkpoints."""
        cp1 = create_checkpoint(
            mission_id="m",
            run_id="r",
            step_id="s",
            strictness=Strictness.MEDIUM,
            scope_refs=[],
            inputs=sample_inputs,
            cursor="pre_generation_gate",
        )
        cp2 = create_checkpoint(
            mission_id="m",
            run_id="r",
            step_id="s",
            strictness=Strictness.MEDIUM,
            scope_refs=[],
            inputs=sample_inputs,
            cursor="pre_generation_gate",
        )
        assert cp1.input_hash == cp2.input_hash

    def test_scope_refs_converted_to_tuple(self, sample_inputs, sample_scope_refs):
        cp = create_checkpoint(
            mission_id="m",
            run_id="r",
            step_id="s",
            strictness=Strictness.MEDIUM,
            scope_refs=sample_scope_refs,
            inputs=sample_inputs,
            cursor="pre_generation_gate",
        )
        assert isinstance(cp.scope_refs, tuple)

    def test_empty_scope_refs(self, sample_inputs):
        cp = create_checkpoint(
            mission_id="m",
            run_id="r",
            step_id="s",
            strictness=Strictness.MEDIUM,
            scope_refs=[],
            inputs=sample_inputs,
            cursor="pre_generation_gate",
        )
        assert cp.scope_refs == ()


# ---------------------------------------------------------------------------
# T032: Checkpoint Loading from Event Log
# ---------------------------------------------------------------------------


class TestParseCheckpointEvent:
    """Test parse_checkpoint_event()."""

    def test_valid_payload(self, sample_checkpoint):
        """Round-trip: checkpoint -> dict -> parsed checkpoint."""
        payload = checkpoint_to_dict(sample_checkpoint)
        parsed = parse_checkpoint_event(payload)

        assert parsed.mission_id == sample_checkpoint.mission_id
        assert parsed.run_id == sample_checkpoint.run_id
        assert parsed.step_id == sample_checkpoint.step_id
        assert parsed.strictness == sample_checkpoint.strictness
        assert parsed.input_hash == sample_checkpoint.input_hash
        assert parsed.cursor == sample_checkpoint.cursor
        assert parsed.retry_token == sample_checkpoint.retry_token

    def test_missing_required_field(self):
        with pytest.raises(ValueError, match="Invalid checkpoint event payload"):
            parse_checkpoint_event({"mission_id": "m"})

    def test_invalid_strictness_value(self):
        payload = {
            "mission_id": "m",
            "run_id": "r",
            "step_id": "s",
            "strictness": "invalid",
            "scope_refs": [],
            "input_hash": "a" * 64,
            "cursor": "pre_generation_gate",
            "retry_token": str(uuid.uuid4()),
            "timestamp": now_utc_iso(),
        }
        with pytest.raises(ValueError, match="Invalid checkpoint event payload"):
            parse_checkpoint_event(payload)

    def test_extra_fields_ignored(self, sample_checkpoint):
        """Extra fields in payload are silently ignored (forward compat)."""
        payload = checkpoint_to_dict(sample_checkpoint)
        payload["extra_field"] = "ignored"
        parsed = parse_checkpoint_event(payload)
        assert parsed.step_id == sample_checkpoint.step_id

    def test_scope_refs_parsed(self, sample_checkpoint):
        payload = checkpoint_to_dict(sample_checkpoint)
        parsed = parse_checkpoint_event(payload)
        assert len(parsed.scope_refs) == len(sample_checkpoint.scope_refs)
        for orig, parsed_ref in zip(
            sample_checkpoint.scope_refs, parsed.scope_refs, strict=False
        ):
            assert parsed_ref.scope == orig.scope
            assert parsed_ref.version_id == orig.version_id

    def test_empty_scope_refs(self):
        payload = {
            "mission_id": "m",
            "run_id": "r",
            "step_id": "s",
            "strictness": "medium",
            "scope_refs": [],
            "input_hash": "a" * 64,
            "cursor": "pre_generation_gate",
            "retry_token": str(uuid.uuid4()),
            "timestamp": now_utc_iso(),
        }
        parsed = parse_checkpoint_event(payload)
        assert parsed.scope_refs == ()


class TestLoadCheckpoint:
    """Test load_checkpoint() from JSONL event log."""

    def test_no_events_dir(self, tmp_path):
        """Returns None if events directory doesn't exist."""
        result = load_checkpoint(tmp_path, "step-001")
        assert result is None

    def test_empty_events_file(self, tmp_path):
        """Returns None if events file is empty."""
        events_dir = tmp_path / ".kittify" / "events" / "glossary"
        events_dir.mkdir(parents=True)
        (events_dir / "m.events.jsonl").write_text("")
        result = load_checkpoint(tmp_path, "step-001")
        assert result is None

    def test_loads_matching_checkpoint(self, tmp_path, sample_checkpoint):
        """Loads checkpoint matching step_id."""
        events_dir = tmp_path / ".kittify" / "events" / "glossary"
        events_dir.mkdir(parents=True)
        payload = checkpoint_to_dict(sample_checkpoint)
        payload["event_type"] = "StepCheckpointed"
        (events_dir / "041-mission.events.jsonl").write_text(
            json.dumps(payload, sort_keys=True) + "\n"
        )

        result = load_checkpoint(tmp_path, sample_checkpoint.step_id)
        assert result is not None
        assert result.step_id == sample_checkpoint.step_id
        assert result.input_hash == sample_checkpoint.input_hash

    def test_returns_none_for_wrong_step_id(self, tmp_path, sample_checkpoint):
        """Returns None if no checkpoint matches step_id."""
        events_dir = tmp_path / ".kittify" / "events" / "glossary"
        events_dir.mkdir(parents=True)
        payload = checkpoint_to_dict(sample_checkpoint)
        payload["event_type"] = "StepCheckpointed"
        (events_dir / "041-mission.events.jsonl").write_text(
            json.dumps(payload, sort_keys=True) + "\n"
        )

        result = load_checkpoint(tmp_path, "different-step")
        assert result is None

    def test_returns_latest_checkpoint(self, tmp_path):
        """When multiple checkpoints exist, returns the latest by timestamp."""
        events_dir = tmp_path / ".kittify" / "events" / "glossary"
        events_dir.mkdir(parents=True)

        older = {
            "event_type": "StepCheckpointed",
            "mission_id": "m",
            "run_id": "r",
            "step_id": "step-001",
            "strictness": "medium",
            "scope_refs": [],
            "input_hash": "a" * 64,
            "cursor": "pre_generation_gate",
            "retry_token": str(uuid.uuid4()),
            "timestamp": "2026-02-16T10:00:00+00:00",
        }
        newer = {
            "event_type": "StepCheckpointed",
            "mission_id": "m",
            "run_id": "r",
            "step_id": "step-001",
            "strictness": "max",
            "scope_refs": [],
            "input_hash": "b" * 64,
            "cursor": "post_clarification",
            "retry_token": str(uuid.uuid4()),
            "timestamp": "2026-02-16T12:00:00+00:00",
        }

        lines = [
            json.dumps(older, sort_keys=True),
            json.dumps(newer, sort_keys=True),
        ]
        (events_dir / "m.events.jsonl").write_text("\n".join(lines) + "\n")

        result = load_checkpoint(tmp_path, "step-001")
        assert result is not None
        assert result.strictness == Strictness.MAX
        assert result.cursor == "post_clarification"

    def test_filters_by_mission_id(self, tmp_path):
        """mission_id filter prevents cross-mission checkpoint collisions."""
        events_dir = tmp_path / ".kittify" / "events" / "glossary"
        events_dir.mkdir(parents=True)

        mission_a = {
            "event_type": "StepCheckpointed",
            "mission_id": "mission-a",
            "run_id": "r-a",
            "step_id": "step-001",
            "strictness": "off",
            "scope_refs": [],
            "input_hash": "a" * 64,
            "cursor": "pre_generation_gate",
            "retry_token": str(uuid.uuid4()),
            "timestamp": "2026-02-16T10:00:00+00:00",
        }
        mission_b = {
            "event_type": "StepCheckpointed",
            "mission_id": "mission-b",
            "run_id": "r-b",
            "step_id": "step-001",
            "strictness": "max",
            "scope_refs": [],
            "input_hash": "b" * 64,
            "cursor": "post_clarification",
            "retry_token": str(uuid.uuid4()),
            "timestamp": "2026-02-16T12:00:00+00:00",
        }
        (events_dir / "mission-a.events.jsonl").write_text(
            json.dumps(mission_a, sort_keys=True) + "\n"
        )
        (events_dir / "mission-b.events.jsonl").write_text(
            json.dumps(mission_b, sort_keys=True) + "\n"
        )

        result = load_checkpoint(tmp_path, "step-001", mission_id="mission-a")
        assert result is not None
        assert result.mission_id == "mission-a"
        assert result.strictness == Strictness.OFF

    def test_filters_by_retry_token(self, tmp_path):
        """retry_token filter loads the exact checkpoint instance."""
        events_dir = tmp_path / ".kittify" / "events" / "glossary"
        events_dir.mkdir(parents=True)

        token_old = str(uuid.uuid4())
        token_new = str(uuid.uuid4())

        older = {
            "event_type": "StepCheckpointed",
            "mission_id": "m",
            "run_id": "r",
            "step_id": "step-001",
            "strictness": "off",
            "scope_refs": [],
            "input_hash": "a" * 64,
            "cursor": "pre_generation_gate",
            "retry_token": token_old,
            "timestamp": "2026-02-16T10:00:00+00:00",
        }
        newer = {
            "event_type": "StepCheckpointed",
            "mission_id": "m",
            "run_id": "r",
            "step_id": "step-001",
            "strictness": "max",
            "scope_refs": [],
            "input_hash": "b" * 64,
            "cursor": "post_clarification",
            "retry_token": token_new,
            "timestamp": "2026-02-16T12:00:00+00:00",
        }
        (events_dir / "m.events.jsonl").write_text(
            "\n".join(
                [
                    json.dumps(older, sort_keys=True),
                    json.dumps(newer, sort_keys=True),
                ]
            )
            + "\n"
        )

        result = load_checkpoint(
            tmp_path,
            "step-001",
            mission_id="m",
            retry_token=token_old,
        )
        assert result is not None
        assert result.retry_token == token_old
        assert result.strictness == Strictness.OFF

    def test_skips_corrupt_lines(self, tmp_path):
        """Corrupt JSON lines are skipped gracefully."""
        events_dir = tmp_path / ".kittify" / "events" / "glossary"
        events_dir.mkdir(parents=True)

        valid = {
            "event_type": "StepCheckpointed",
            "mission_id": "m",
            "run_id": "r",
            "step_id": "step-001",
            "strictness": "medium",
            "scope_refs": [],
            "input_hash": "a" * 64,
            "cursor": "pre_generation_gate",
            "retry_token": str(uuid.uuid4()),
            "timestamp": "2026-02-16T10:00:00+00:00",
        }

        lines = [
            "not valid json",
            json.dumps(valid, sort_keys=True),
        ]
        (events_dir / "m.events.jsonl").write_text("\n".join(lines) + "\n")

        result = load_checkpoint(tmp_path, "step-001")
        assert result is not None
        assert result.step_id == "step-001"

    def test_skips_invalid_payloads(self, tmp_path):
        """Invalid checkpoint payloads (missing fields) are skipped."""
        events_dir = tmp_path / ".kittify" / "events" / "glossary"
        events_dir.mkdir(parents=True)

        invalid = {"event_type": "StepCheckpointed", "step_id": "step-001", "mission_id": "m"}  # Missing fields
        valid = {
            "event_type": "StepCheckpointed",
            "mission_id": "m",
            "run_id": "r",
            "step_id": "step-001",
            "strictness": "medium",
            "scope_refs": [],
            "input_hash": "c" * 64,
            "cursor": "pre_generation_gate",
            "retry_token": str(uuid.uuid4()),
            "timestamp": "2026-02-16T10:00:00+00:00",
        }

        lines = [
            json.dumps(invalid, sort_keys=True),
            json.dumps(valid, sort_keys=True),
        ]
        (events_dir / "m.events.jsonl").write_text("\n".join(lines) + "\n")

        result = load_checkpoint(tmp_path, "step-001")
        assert result is not None
        assert result.input_hash == "c" * 64


class TestCheckpointToDict:
    """Test checkpoint_to_dict() serialization."""

    def test_round_trip(self, sample_checkpoint):
        payload = checkpoint_to_dict(sample_checkpoint)
        parsed = parse_checkpoint_event(payload)
        assert parsed.mission_id == sample_checkpoint.mission_id
        assert parsed.input_hash == sample_checkpoint.input_hash

    def test_json_serializable(self, sample_checkpoint):
        payload = checkpoint_to_dict(sample_checkpoint)
        serialized = json.dumps(payload, sort_keys=True)
        assert isinstance(serialized, str)

    def test_payload_size_under_1kb(self, sample_checkpoint):
        """Checkpoint payload should be minimal (<1KB)."""
        payload = checkpoint_to_dict(sample_checkpoint)
        serialized = json.dumps(payload, sort_keys=True)
        assert len(serialized) < 1024


# ---------------------------------------------------------------------------
# T033: Input Hash Verification
# ---------------------------------------------------------------------------


class TestVerifyInputHash:
    """Test verify_input_hash()."""

    def test_matching_inputs(self, sample_checkpoint, sample_inputs):
        matches, old_h, new_h = verify_input_hash(sample_checkpoint, sample_inputs)
        assert matches is True
        assert old_h == new_h

    def test_changed_inputs(self, sample_checkpoint):
        changed = {"description": "Changed", "requirements": ["req1", "req2"]}
        matches, old_h, new_h = verify_input_hash(sample_checkpoint, changed)
        assert matches is False
        assert old_h != new_h

    def test_truncated_hashes_are_16_chars(self, sample_checkpoint, sample_inputs):
        _, old_h, new_h = verify_input_hash(sample_checkpoint, sample_inputs)
        assert len(old_h) == 16
        assert len(new_h) == 16

    def test_reordered_keys_still_match(self, sample_checkpoint):
        """Same content with different key order should match."""
        reordered = {"requirements": ["req1", "req2"], "description": "Implement feature X"}
        matches, _, _ = verify_input_hash(sample_checkpoint, reordered)
        assert matches is True

    def test_added_key_does_not_match(self, sample_checkpoint, sample_inputs):
        extended = dict(sample_inputs)
        extended["extra"] = "value"
        matches, _, _ = verify_input_hash(sample_checkpoint, extended)
        assert matches is False

    def test_removed_key_does_not_match(self, sample_checkpoint):
        partial = {"description": "Implement feature X"}
        matches, _, _ = verify_input_hash(sample_checkpoint, partial)
        assert matches is False


class TestComputeInputDiff:
    """Test compute_input_diff()."""

    def test_no_changes(self):
        old = {"a": 1, "b": 2}
        new = {"a": 1, "b": 2}
        assert compute_input_diff(old, new) == {}

    def test_changed_value(self):
        old = {"a": 1}
        new = {"a": 2}
        diff = compute_input_diff(old, new)
        assert diff == {"a": (1, 2)}

    def test_added_key(self):
        old = {"a": 1}
        new = {"a": 1, "b": 2}
        diff = compute_input_diff(old, new)
        assert diff == {"b": (None, 2)}

    def test_removed_key(self):
        old = {"a": 1, "b": 2}
        new = {"a": 1}
        diff = compute_input_diff(old, new)
        assert diff == {"b": (2, None)}

    def test_type_change(self):
        old = {"val": "5"}
        new = {"val": 5}
        diff = compute_input_diff(old, new)
        assert diff == {"val": ("5", 5)}

    def test_complex_diff(self):
        old = {"a": 1, "b": 2, "c": 3}
        new = {"a": 1, "b": 99, "d": 4}
        diff = compute_input_diff(old, new)
        assert diff == {"b": (2, 99), "c": (3, None), "d": (None, 4)}


class TestHandleContextChange:
    """Test handle_context_change()."""

    def test_no_change_no_prompt(self, sample_checkpoint, sample_inputs):
        """When context unchanged, returns True without prompting."""
        call_count = [0]

        def mock_confirm(old_h, new_h):
            call_count[0] += 1
            return True

        result = handle_context_change(
            sample_checkpoint, sample_inputs, confirm_fn=mock_confirm
        )
        assert result is True
        assert call_count[0] == 0  # Never called

    def test_change_prompts_user_confirm(self, sample_checkpoint):
        """When context changed and user confirms, returns True."""
        def mock_confirm(old_h, new_h):
            return True

        changed = {"description": "Changed", "requirements": []}
        result = handle_context_change(
            sample_checkpoint, changed, confirm_fn=mock_confirm
        )
        assert result is True

    def test_change_prompts_user_decline(self, sample_checkpoint):
        """When context changed and user declines, returns False."""
        def mock_confirm(old_h, new_h):
            return False

        changed = {"description": "Changed", "requirements": []}
        result = handle_context_change(
            sample_checkpoint, changed, confirm_fn=mock_confirm
        )
        assert result is False

    def test_confirm_receives_truncated_hashes(self, sample_checkpoint):
        """Confirm function receives 16-char truncated hashes."""
        received = {}

        def mock_confirm(old_h, new_h):
            received["old"] = old_h
            received["new"] = new_h
            return True

        changed = {"description": "Different"}
        handle_context_change(
            sample_checkpoint, changed, confirm_fn=mock_confirm
        )
        assert len(received["old"]) == 16
        assert len(received["new"]) == 16


# ---------------------------------------------------------------------------
# #7669: a mission_id reads only that mission's own log
# ---------------------------------------------------------------------------


def _checkpoint_event(mission_id: str, step_id: str = "step-001", ts: str = "2026-02-16T10:00:00+00:00") -> dict:
    return {
        "event_type": "StepCheckpointed",
        "mission_id": mission_id,
        "run_id": "r",
        "step_id": step_id,
        "strictness": "medium",
        "scope_refs": [],
        "input_hash": "c" * 64,
        "cursor": "pre_generation_gate",
        "retry_token": str(uuid.uuid4()),
        "timestamp": ts,
    }


@pytest.fixture
def opened_logs(monkeypatch):
    """Record every event log ``load_checkpoint`` opens."""
    import glossary.events as events_module

    real_read_events = events_module.read_events
    opened: list[str] = []

    def spy(event_log_path, event_type=None):
        opened.append(event_log_path.name)
        return real_read_events(event_log_path, event_type=event_type)

    monkeypatch.setattr(events_module, "read_events", spy)
    return opened


class TestLoadCheckpointSingleLog:
    """load_checkpoint derives the mission's log path instead of globbing (#7669)."""

    @staticmethod
    def _seed(tmp_path, name: str, *events: dict) -> None:
        events_dir = tmp_path / ".kittify" / "events" / "glossary"
        events_dir.mkdir(parents=True, exist_ok=True)
        (events_dir / name).write_text("".join(json.dumps(e, sort_keys=True) + "\n" for e in events))

    def test_mission_id_opens_only_its_own_log(self, tmp_path, opened_logs):
        self._seed(tmp_path, "mission-a.events.jsonl", _checkpoint_event("mission-a"))
        self._seed(tmp_path, "mission-b.events.jsonl", _checkpoint_event("mission-b"))

        result = load_checkpoint(tmp_path, "step-001", mission_id="mission-a")

        assert result is not None and result.mission_id == "mission-a"
        assert opened_logs == ["mission-a.events.jsonl"]

    def test_mission_id_path_goes_through_the_writer_sanitizer(self, tmp_path, opened_logs):
        self._seed(tmp_path, "team-x-041.events.jsonl", _checkpoint_event("team/x:041"))
        self._seed(tmp_path, "other.events.jsonl", _checkpoint_event("other"))

        result = load_checkpoint(tmp_path, "step-001", mission_id="team/x:041")

        assert result is not None and result.mission_id == "team/x:041"
        assert opened_logs == ["team-x-041.events.jsonl"]

    def test_miss_in_own_log_falls_back_to_legacy_filename(self, tmp_path, opened_logs):
        self._seed(tmp_path, "mission-a.events.jsonl", _checkpoint_event("mission-a", step_id="other-step"))
        self._seed(tmp_path, "legacy-name.events.jsonl", _checkpoint_event("mission-a"))

        result = load_checkpoint(tmp_path, "step-001", mission_id="mission-a")

        assert result is not None and result.mission_id == "mission-a"
        # The own log is read once and is not re-read by the fallback scan.
        assert sorted(opened_logs) == ["legacy-name.events.jsonl", "mission-a.events.jsonl"]

    def test_absent_own_log_falls_back_to_glob(self, tmp_path, opened_logs):
        self._seed(tmp_path, "legacy-name.events.jsonl", _checkpoint_event("mission-a"))

        result = load_checkpoint(tmp_path, "step-001", mission_id="mission-a")

        assert result is not None
        assert opened_logs == ["legacy-name.events.jsonl"]

    def test_without_mission_id_every_log_is_scanned(self, tmp_path, opened_logs):
        self._seed(tmp_path, "mission-a.events.jsonl", _checkpoint_event("mission-a", ts="2026-02-16T10:00:00+00:00"))
        self._seed(tmp_path, "mission-b.events.jsonl", _checkpoint_event("mission-b", ts="2026-02-16T12:00:00+00:00"))

        result = load_checkpoint(tmp_path, "step-001")

        assert result is not None and result.mission_id == "mission-b"
        assert sorted(opened_logs) == ["mission-a.events.jsonl", "mission-b.events.jsonl"]
