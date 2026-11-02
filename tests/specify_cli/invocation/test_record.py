"""Tests for the Op event models, MinimalViableTrailPolicy, and tier helpers.

Sections:
- Schema-contract tests for OpStartedEvent / OpCompletedEvent / parse_op_event
  (pins contracts/op-record-events.md: required-field enforcement, None-field
  omission, round-trip of both contract examples, dispatch parsing, and
  legacy-line detection).
- MinimalViableTrailPolicy / tier helper tests.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from specify_cli.invocation.errors import LegacyRecordError
from specify_cli.invocation.record import (
    MINIMAL_VIABLE_TRAIL_POLICY,
    TIER_3_ACTIONS,
    MinimalViableTrailPolicy,
    OpCompletedEvent,
    OpStartedEvent,
    TierPolicy,
    parse_op_event,
    promote_to_evidence,
    tier_eligible,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]
_ULID = "01ABCDEFGHJKMNPQRSTVWXYZ12"
_CONTRACT_ULID = "01KTK5JBD69FQ8XVRFV1J630MJ"

# Contract examples (contracts/op-record-events.md), verbatim.
CONTRACT_STARTED = {
    "event": "started",
    "invocation_id": _CONTRACT_ULID,
    "profile_id": "implementer-iris",
    "action": "implement",
    "request_text": "fix that bug",
    "actor": "claude",
    "mode_of_work": "task_execution",
    "governance_context_hash": "d5ccab5678dcc4c8",
    "governance_context_available": True,
    "router_confidence": "canonical_verb",
    "started_at": "2026-06-10T20:00:00+00:00",
}
CONTRACT_COMPLETED = {
    "event": "completed",
    "invocation_id": _CONTRACT_ULID,
    "completed_at": "2026-06-10T20:25:00+00:00",
    "outcome": "done",
    "closed_by": "agent",
    "evidence_ref": ".kittify/evidence/01KTK5JBD69FQ8XVRFV1J630MJ",
}


def _started_kwargs(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = dict(CONTRACT_STARTED)
    data.pop("event")
    data.update(overrides)
    return data


def _completed_kwargs(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = dict(CONTRACT_COMPLETED)
    data.pop("event")
    data.update(overrides)
    return data


# ---------------------------------------------------------------------------
# OpStartedEvent schema contract
# ---------------------------------------------------------------------------


class TestOpStartedEvent:
    def test_contract_example_round_trips(self) -> None:
        event = OpStartedEvent.model_validate(CONTRACT_STARTED)
        assert json.loads(event.to_jsonl_line()) == CONTRACT_STARTED

    def test_missing_action_raises(self) -> None:
        kwargs = _started_kwargs()
        kwargs.pop("action")
        with pytest.raises(ValidationError):
            OpStartedEvent(**kwargs)  # type: ignore[arg-type]

    def test_empty_action_raises(self) -> None:
        with pytest.raises(ValidationError):
            OpStartedEvent(**_started_kwargs(action=""))  # type: ignore[arg-type]

    @pytest.mark.parametrize("field", ["profile_id", "actor", "mode_of_work", "started_at"])
    def test_empty_required_string_fields_raise(self, field: str) -> None:
        with pytest.raises(ValidationError):
            OpStartedEvent(**_started_kwargs(**{field: ""}))  # type: ignore[arg-type]

    def test_invalid_ulid_raises(self) -> None:
        with pytest.raises(ValidationError):
            OpStartedEvent(**_started_kwargs(invocation_id="not-a-ulid"))  # type: ignore[arg-type]

    def test_frozen(self) -> None:
        event = OpStartedEvent.model_validate(CONTRACT_STARTED)
        with pytest.raises(ValidationError):
            event.action = "other"  # type: ignore[misc]

    def test_none_fields_omitted_from_jsonl(self) -> None:
        event = OpStartedEvent(**_started_kwargs(router_confidence=None))  # type: ignore[arg-type]
        data = json.loads(event.to_jsonl_line())
        assert "router_confidence" not in data
        assert "mission_id" not in data
        assert "wp_id" not in data

    def test_mission_and_wp_present_when_set(self) -> None:
        event = OpStartedEvent(
            **_started_kwargs(
                mission_id="01KTK5JBD69FQ8XVRFV1J630MJ",
                wp_id="WP01",
            )  # type: ignore[arg-type]
        )
        data = json.loads(event.to_jsonl_line())
        assert data["mission_id"] == "01KTK5JBD69FQ8XVRFV1J630MJ"
        assert data["wp_id"] == "WP01"

    def test_schema_declares_no_model_identifier(self) -> None:
        """#7013: no field of the started event names a model."""
        assert "model_id" not in OpStartedEvent.model_fields

    def test_legacy_line_with_model_id_parses_and_is_not_re_emitted(self) -> None:
        """#7013: a pre-change record stays readable and is never re-written with the key."""
        legacy = {**CONTRACT_STARTED, "model_id": "claude-opus-4-6"}
        # Positive control on the same fixture: the probe can see the key when it
        # is there, so the absence assertions below are not vacuous.
        assert legacy["model_id"] == "claude-opus-4-6"

        event = parse_op_event(legacy)
        assert isinstance(event, OpStartedEvent)
        assert "model_id" not in json.loads(event.to_jsonl_line())
        assert "claude-opus-4-6" not in event.to_jsonl_line()

    def test_request_text_may_be_empty(self) -> None:
        # Empty only legitimate for query mode — no model-level gate (executor enforces).
        event = OpStartedEvent(**_started_kwargs(request_text="", mode_of_work="query"))  # type: ignore[arg-type]
        assert event.request_text == ""

    def test_mode_of_work_value_constrained(self) -> None:
        with pytest.raises(ValidationError):
            OpStartedEvent(**_started_kwargs(mode_of_work="bogus"))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# OpCompletedEvent schema contract
# ---------------------------------------------------------------------------


class TestOpCompletedEvent:
    def test_contract_example_round_trips(self) -> None:
        event = OpCompletedEvent.model_validate(CONTRACT_COMPLETED)
        assert json.loads(event.to_jsonl_line()) == CONTRACT_COMPLETED

    def test_outcome_required_no_default(self) -> None:
        kwargs = _completed_kwargs()
        kwargs.pop("outcome")
        with pytest.raises(ValidationError):
            OpCompletedEvent(**kwargs)  # type: ignore[arg-type]

    def test_outcome_none_rejected(self) -> None:
        with pytest.raises(ValidationError):
            OpCompletedEvent(**_completed_kwargs(outcome=None))  # type: ignore[arg-type]

    def test_closed_by_required_no_default(self) -> None:
        kwargs = _completed_kwargs()
        kwargs.pop("closed_by")
        with pytest.raises(ValidationError):
            OpCompletedEvent(**kwargs)  # type: ignore[arg-type]

    def test_closed_by_value_constrained(self) -> None:
        with pytest.raises(ValidationError):
            OpCompletedEvent(**_completed_kwargs(closed_by="elf"))  # type: ignore[arg-type]

    def test_no_started_only_fields(self) -> None:
        fields = set(OpCompletedEvent.model_fields)
        assert fields == {
            "event",
            "invocation_id",
            "completed_at",
            "outcome",
            "closed_by",
            "evidence_ref",
        }

    def test_evidence_ref_omitted_when_none(self) -> None:
        event = OpCompletedEvent(**_completed_kwargs(evidence_ref=None))  # type: ignore[arg-type]
        data = json.loads(event.to_jsonl_line())
        assert "evidence_ref" not in data

    def test_frozen(self) -> None:
        event = OpCompletedEvent.model_validate(CONTRACT_COMPLETED)
        with pytest.raises(ValidationError):
            event.outcome = "failed"  # type: ignore[misc]

    def test_invalid_ulid_raises(self) -> None:
        with pytest.raises(ValidationError):
            OpCompletedEvent(**_completed_kwargs(invocation_id="x" * 26))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# parse_op_event dispatch + legacy detection
# ---------------------------------------------------------------------------


class TestParseOpEvent:
    def test_dispatches_started(self) -> None:
        assert isinstance(parse_op_event(dict(CONTRACT_STARTED)), OpStartedEvent)

    def test_dispatches_completed(self) -> None:
        assert isinstance(parse_op_event(dict(CONTRACT_COMPLETED)), OpCompletedEvent)

    def test_legacy_completed_without_closed_by_raises_legacy_error(self) -> None:
        legacy = {
            "event": "completed",
            "invocation_id": _CONTRACT_ULID,
            "profile_id": "implementer-iris",
            "action": "",
            "actor": "unknown",
            "completed_at": "2026-06-10T20:25:00+00:00",
            "outcome": None,
        }
        with pytest.raises(LegacyRecordError) as exc_info:
            parse_op_event(legacy)
        assert exc_info.value.invocation_id == _CONTRACT_ULID
        assert "spec-kitty upgrade" in str(exc_info.value)

    def test_legacy_started_missing_v2_fields_raises_legacy_error(self) -> None:
        legacy = {
            "event": "started",
            "invocation_id": _CONTRACT_ULID,
            "profile_id": "implementer-iris",
            "action": "implement",
            # legacy v1 line: no mode_of_work, actor may default "unknown"
        }
        with pytest.raises(LegacyRecordError):
            parse_op_event(legacy)

    def test_non_lifecycle_event_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="not an Op lifecycle event"):
            parse_op_event({"event": "artifact_link", "invocation_id": _CONTRACT_ULID})

    def test_legacy_error_is_distinct_and_catchable(self) -> None:
        from specify_cli.invocation.errors import InvocationError

        assert issubclass(LegacyRecordError, InvocationError)
        assert not issubclass(LegacyRecordError, ValidationError)


def _make_started(**overrides: object) -> OpStartedEvent:
    defaults: dict[str, object] = {
        "invocation_id": _ULID,
        "profile_id": "implementer-fixture",
        "action": "generate",
        "request_text": "implement the new behaviour",
        "governance_context_hash": "abcdef0123456789",
        "governance_context_available": True,
        "actor": "claude",
        "mode_of_work": "task_execution",
        "router_confidence": "exact",
        "started_at": "2026-04-21T12:00:00+00:00",
    }
    defaults.update(overrides)
    return OpStartedEvent(**defaults)  # type: ignore[arg-type]


def _make_completed(**overrides: object) -> OpCompletedEvent:
    defaults: dict[str, object] = {
        "invocation_id": _ULID,
        "completed_at": "2026-04-21T13:00:00+00:00",
        "outcome": "done",
        "closed_by": "agent",
    }
    defaults.update(overrides)
    return OpCompletedEvent(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# MinimalViableTrailPolicy tests
# ---------------------------------------------------------------------------


def test_mvt_policy_is_frozen_dataclass_instance() -> None:
    """MINIMAL_VIABLE_TRAIL_POLICY must be a MinimalViableTrailPolicy instance, not a dict."""
    assert isinstance(MINIMAL_VIABLE_TRAIL_POLICY, MinimalViableTrailPolicy)
    assert not isinstance(MINIMAL_VIABLE_TRAIL_POLICY, dict)


def test_mvt_policy_is_frozen() -> None:
    """Frozen dataclass raises on attribute assignment."""
    with pytest.raises(Exception):  # FrozenInstanceError (subclass of AttributeError)
        MINIMAL_VIABLE_TRAIL_POLICY.tier_1 = None  # type: ignore[misc]


def test_mvt_policy_tiers_are_tier_policy_instances() -> None:
    assert isinstance(MINIMAL_VIABLE_TRAIL_POLICY.tier_1, TierPolicy)
    assert isinstance(MINIMAL_VIABLE_TRAIL_POLICY.tier_2, TierPolicy)
    assert isinstance(MINIMAL_VIABLE_TRAIL_POLICY.tier_3, TierPolicy)


def test_mvt_policy_tier_1_is_mandatory() -> None:
    assert MINIMAL_VIABLE_TRAIL_POLICY.tier_1.mandatory is True
    assert MINIMAL_VIABLE_TRAIL_POLICY.tier_2.mandatory is False
    assert MINIMAL_VIABLE_TRAIL_POLICY.tier_3.mandatory is False


def test_mvt_policy_tier_1_name() -> None:
    assert MINIMAL_VIABLE_TRAIL_POLICY.tier_1.name == "every_invocation"


def test_mvt_policy_tier_2_name() -> None:
    assert MINIMAL_VIABLE_TRAIL_POLICY.tier_2.name == "evidence_artifact"


def test_mvt_policy_tier_3_name() -> None:
    assert MINIMAL_VIABLE_TRAIL_POLICY.tier_3.name == "durable_project_state"


def test_mvt_policy_storage_paths_present() -> None:
    assert "{invocation_id}" in MINIMAL_VIABLE_TRAIL_POLICY.tier_1.storage_path
    assert "{invocation_id}" in MINIMAL_VIABLE_TRAIL_POLICY.tier_2.storage_path
    assert "{mission_slug}" in MINIMAL_VIABLE_TRAIL_POLICY.tier_3.storage_path


# ---------------------------------------------------------------------------
# TierEligibility / tier_eligible tests
# ---------------------------------------------------------------------------


def test_tier_eligible_tier1_always_true() -> None:
    assert tier_eligible(_make_started(action="implement")).tier_1 is True


def test_tier_eligible_tier2_requires_evidence_ref() -> None:
    started = _make_started(action="implement")
    assert tier_eligible(started, None).tier_2 is False
    assert tier_eligible(started, _make_completed()).tier_2 is False
    assert tier_eligible(started, _make_completed(evidence_ref=".kittify/evidence/test/")).tier_2 is True


@pytest.mark.parametrize("action", ["specify", "plan", "tasks", "merge", "accept"])
def test_tier_eligible_tier3_for_durable_actions(action: str) -> None:
    assert tier_eligible(_make_started(action=action)).tier_3 is True


@pytest.mark.parametrize("action", ["review", "implement"])
def test_tier_eligible_tier3_not_for_non_durable_actions(action: str) -> None:
    assert tier_eligible(_make_started(action=action)).tier_3 is False


# ---------------------------------------------------------------------------
# promote_to_evidence tests
# ---------------------------------------------------------------------------


def _evidence_record() -> OpCompletedEvent:
    return _make_completed(invocation_id="01KPQRX2EVGMRVB4Q1JQBAZJV3")


def test_promote_to_evidence_creates_files(tmp_path: Path) -> None:
    artifact = promote_to_evidence(_evidence_record(), tmp_path, "# Evidence\n\nThis is evidence.")
    assert artifact.evidence_file.exists()
    assert artifact.record_snapshot.exists()
    assert artifact.evidence_file.read_text() == "# Evidence\n\nThis is evidence."


def test_promote_to_evidence_record_snapshot_is_valid_json(tmp_path: Path) -> None:
    artifact = promote_to_evidence(_evidence_record(), tmp_path, "content")
    data = json.loads(artifact.record_snapshot.read_text())
    assert data["invocation_id"] == "01KPQRX2EVGMRVB4Q1JQBAZJV3"
    assert data["closed_by"] == "agent"


def test_promote_to_evidence_creates_exactly_two_files(tmp_path: Path) -> None:
    artifact = promote_to_evidence(_evidence_record(), tmp_path, "content")
    assert len(list(artifact.directory.iterdir())) == 2


def test_promote_to_evidence_directory_named_by_invocation_id(tmp_path: Path) -> None:
    artifact = promote_to_evidence(_evidence_record(), tmp_path, "content")
    assert artifact.directory.name == "01KPQRX2EVGMRVB4Q1JQBAZJV3"
    assert artifact.invocation_id == "01KPQRX2EVGMRVB4Q1JQBAZJV3"


# ---------------------------------------------------------------------------
# TIER_3_ACTIONS tests
# ---------------------------------------------------------------------------


def test_tier3_actions_contains_expected() -> None:
    assert {"specify", "plan", "tasks", "merge", "accept"} <= TIER_3_ACTIONS


def test_tier3_actions_excludes_review_and_implement() -> None:
    assert "review" not in TIER_3_ACTIONS
    assert "implement" not in TIER_3_ACTIONS


def test_tier3_actions_is_frozenset() -> None:
    assert isinstance(TIER_3_ACTIONS, frozenset)
