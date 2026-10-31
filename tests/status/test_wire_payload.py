"""Canonical ``WPStatusChanged`` payload builder (#6449).

The migration/TeamSpace dry-run used to hand-assemble this payload as a plain
dict -- a second authority for the event shape. These tests pin the one canonical
builder:

1. the exact wire key set and null policy (the 3.0.0 transport fixture and a real
   local row both keep explicit nulls for ``reason``/``review_ref``/``evidence``),
2. ``mission_id`` carried when the event has one and absent (not ``null``) when it
   does not -- the field the hand-built dict silently dropped,
3. a coverage ratchet: every ``StatusTransitionPayload`` model field is either
   mapped from a ``StatusEvent`` or declared producer-supplied-only, so a future
   contract field fails here instead of vanishing from the payload,
4. construction-time validation through the package model, and
5. the historical overrides the dry-run owns replacing only the named fields.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from spec_kitty_events.status import StatusTransitionPayload

from specify_cli import status
from specify_cli.status import wire_payload
from specify_cli.status.models import DoneEvidence, Lane, RepoEvidence, ReviewApproval, StatusEvent

pytestmark = pytest.mark.fast

_MISSION_ID = "01M68JCJ9ACY7K2HH4TVY8G19V"


def _event(**overrides: Any) -> StatusEvent:
    """A real ``claimed -> in_progress`` transition, the common dry-run row."""
    fields: dict[str, Any] = {
        "event_id": "01KQHRB8GCFJAX7HM4ZY52AQGR",
        "mission_slug": "042-demo",
        "mission_id": _MISSION_ID,
        "wp_id": "WP01",
        "from_lane": Lane.CLAIMED,
        "to_lane": Lane.IN_PROGRESS,
        "at": "2026-01-01T00:00:00+00:00",
        "actor": "claude",
        "force": False,
        "execution_mode": "worktree",
    }
    fields.update(overrides)
    return StatusEvent(**fields)


def _done_evidence() -> DoneEvidence:
    return DoneEvidence(
        review=ReviewApproval(reviewer="reviewer-renata", verdict="approved", reference="review-cycle://42"),
        repos=[RepoEvidence(repo="spec-kitty", branch="main", commit="abc1234")],
    )


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True)


# ---------------------------------------------------------------------------
# T001 -- wire key set and null policy
# ---------------------------------------------------------------------------


def test_payload_matches_the_contract_key_set_and_null_policy() -> None:
    payload = status.build_status_event_payload(_event())

    # canonical-event-exempt(comparison): the expectation is the hand-rolled wire
    # contract itself (the 3.0.0 fixture's key set and its explicit nulls); building
    # it from the same model would make this assertion tautological.
    expected = {
        "mission_slug": "042-demo",
        "mission_id": _MISSION_ID,
        "wp_id": "WP01",
        "from_lane": "claimed",
        "to_lane": "in_progress",
        "actor": "claude",
        "force": False,
        "reason": None,
        "execution_mode": "worktree",
        "review_ref": None,
        "evidence": None,
    }

    assert _canonical(payload) == _canonical(expected)
    assert "summary" not in payload


def test_legacy_event_without_mission_id_omits_the_key_instead_of_nulling_it() -> None:
    payload = status.build_status_event_payload(_event(mission_id=None))

    assert "mission_id" not in payload
    # positive control on the same builder: the field IS carried when set
    assert status.build_status_event_payload(_event())["mission_id"] == _MISSION_ID


def test_done_evidence_rides_as_the_contract_shape() -> None:
    payload = status.build_status_event_payload(
        _event(to_lane=Lane.DONE, evidence=_done_evidence()),
    )

    assert payload["evidence"] == _done_evidence().to_dict()
    # the model, not the local dataclass, is the authority on the emitted shape
    assert StatusTransitionPayload.model_validate(payload).evidence is not None


# ---------------------------------------------------------------------------
# T002 -- coverage ratchet against the contract model
# ---------------------------------------------------------------------------


def test_every_contract_field_is_mapped_or_declared_producer_supplied() -> None:
    declared = set(wire_payload._EVENT_FIELD_ATTRS) | set(wire_payload._PRODUCER_SUPPLIED_FIELDS)

    assert declared == set(StatusTransitionPayload.model_fields)


def test_producer_supplied_exclusion_cannot_grow_silently() -> None:
    assert wire_payload._PRODUCER_SUPPLIED_FIELDS == frozenset({"summary"})


# ---------------------------------------------------------------------------
# T005 -- construction-time validation and override discipline
# ---------------------------------------------------------------------------


def test_force_without_reason_is_rejected_at_construction() -> None:
    with pytest.raises(Exception) as excinfo:
        status.build_status_event_payload(_event(force=True, to_lane=Lane.PLANNED))

    assert "reason" in str(excinfo.value)
    # positive control: the same forced edge builds once a reason is supplied
    assert status.build_status_event_payload(_event(force=True, to_lane=Lane.PLANNED, reason="rewind"))["force"] is True


def test_approved_without_evidence_is_rejected_at_construction() -> None:
    with pytest.raises(Exception) as excinfo:
        status.build_status_event_payload(_event(to_lane=Lane.APPROVED))

    assert "evidence" in str(excinfo.value)
    # positive control: the same edge builds with evidence
    assert status.build_status_event_payload(_event(to_lane=Lane.APPROVED, evidence=_done_evidence()))["to_lane"] == "approved"


def test_unknown_override_key_is_refused() -> None:
    with pytest.raises(ValueError, match="summry"):
        status.build_status_event_payload(_event(), overrides={"summry": "typo"})

    # positive control: a known override key is accepted
    overridden = status.build_status_event_payload(_event(), overrides={"review_ref": "review-cycle://7"})
    assert overridden["review_ref"] == "review-cycle://7"


def test_overrides_replace_only_the_named_fields() -> None:
    event = _event(from_lane=Lane.IN_PROGRESS, to_lane=Lane.IN_REVIEW)
    payload = status.build_status_event_payload(
        event,
        overrides={"from_lane": "for_review", "evidence": _done_evidence().to_dict()},
    )

    assert payload["from_lane"] == "for_review"
    assert payload["evidence"] == _done_evidence().to_dict()
    # untouched fields still come from the event
    assert payload["to_lane"] == "in_review"
    assert payload["wp_id"] == event.wp_id
    assert payload["mission_id"] == event.mission_id
