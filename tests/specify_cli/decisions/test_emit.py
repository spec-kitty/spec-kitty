"""Tests for decisions.emit — T016.

Covers:
- emit_decision_opened produces correct event_type and planning_interview origin_surface.
- emit_decision_resolved with RESOLVED terminal_outcome emits correct event with final_answer.
- emit_decision_resolved with DEFERRED terminal_outcome emits correct event with rationale.
- Round-trip: each payload validates against the Pydantic model.
"""

from __future__ import annotations

import json
import logging
from kernel.clock import UTC, datetime
from pathlib import Path


from specify_cli.decisions.emit import emit_decision_opened, emit_decision_resolved
from specify_cli.decisions.models import DecisionStatus, IndexEntry, OriginFlow
from spec_kitty_events.decisionpoint import (
    DECISION_POINT_OPENED,
    DECISION_POINT_RESOLVED,
    DECISIONPOINT_SCHEMA_VERSION,
    DecisionPointOpenedInterviewPayload,
    DecisionPointResolvedInterviewPayload,
)
from spec_kitty_events.decision_moment import OriginSurface


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

MISSION_SLUG = "test-mission-01KPWT8PXXX"
MISSION_ID = "01KPWT8PNY8683QX3WBW6VXYM7"
ACTOR = "test-actor"


class _DirectMissionDirSeam:
    """Stub placement seam returning ``repo_root/kitty-specs/<slug>`` directly.

    write-side-seam-matrix-tracer-01KYP3MH WP02 Move A: ``emit.py`` now routes
    ``_mission_dir`` through ``placement_seam(...).read_dir(STATUS_STATE)``
    rather than the kind-blind ``resolve_feature_dir_for_mission`` — stub the
    seam constructor instead so these emission tests keep targeting event
    serialization, not mission/topology lookup.
    """

    def __init__(self, repo_root: Path, mission_slug: str) -> None:
        self._repo_root = repo_root
        self._mission_slug = mission_slug

    def read_dir(self, kind: object) -> Path:
        return self._repo_root / "kitty-specs" / self._mission_slug


@pytest.fixture(autouse=True)
def _direct_mission_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """These emission tests target event serialization, not mission lookup."""
    monkeypatch.setattr(
        "specify_cli.decisions.emit.placement_seam",
        _DirectMissionDirSeam,
    )


def _make_entry(
    decision_id: str,
    status: DecisionStatus = DecisionStatus.OPEN,
    step_id: str | None = "charter.q1",
    slot_key: str | None = None,
    final_answer: str | None = None,
    rationale: str | None = None,
    other_answer: bool = False,
    resolved_at: datetime | None = None,
    resolved_by: str | None = None,
) -> IndexEntry:
    return IndexEntry(
        decision_id=decision_id,
        origin_flow=OriginFlow.CHARTER,
        step_id=step_id,
        slot_key=slot_key,
        input_key="auth_strategy",
        question="Which auth strategy?",
        options=("session", "oauth2"),
        status=status,
        final_answer=final_answer,
        rationale=rationale,
        other_answer=other_answer,
        created_at=datetime(2026, 4, 23, 10, 0, 0, tzinfo=UTC),
        resolved_at=resolved_at,
        resolved_by=resolved_by,
        mission_id=MISSION_ID,
        mission_slug=MISSION_SLUG,
    )


def _read_events(repo_root: Path, mission_slug: str) -> list[dict]:
    path = repo_root / "kitty-specs" / mission_slug / "status.events.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Tests: emit_decision_opened
# ---------------------------------------------------------------------------


def test_emit_decision_opened_writes_event(tmp_path: Path) -> None:
    """emit_decision_opened appends a DecisionPointOpened event."""
    entry = _make_entry("01AAAAAAAAAAAAAAAAAAAAAAAA")
    lamport = emit_decision_opened(
        tmp_path, MISSION_SLUG, decision_id="01AAAAAAAAAAAAAAAAAAAAAAAA", entry=entry, actor=ACTOR
    )

    events = _read_events(tmp_path, MISSION_SLUG)
    assert len(events) == 1
    assert events[0]["event_type"] == DECISION_POINT_OPENED
    assert lamport == 1


def test_emit_decision_opened_event_type(tmp_path: Path) -> None:
    """Event has event_type=DecisionPointOpened."""
    entry = _make_entry("01BBBBBBBBBBBBBBBBBBBBBBBB")
    emit_decision_opened(
        tmp_path, MISSION_SLUG, decision_id="01BBBBBBBBBBBBBBBBBBBBBBBB", entry=entry, actor=ACTOR
    )
    events = _read_events(tmp_path, MISSION_SLUG)
    assert events[0]["event_type"] == DECISION_POINT_OPENED


def test_emit_decision_opened_origin_surface(tmp_path: Path) -> None:
    """Payload has origin_surface=planning_interview."""
    entry = _make_entry("01CCCCCCCCCCCCCCCCCCCCCCCC")
    emit_decision_opened(
        tmp_path, MISSION_SLUG, decision_id="01CCCCCCCCCCCCCCCCCCCCCCCC", entry=entry, actor=ACTOR
    )
    events = _read_events(tmp_path, MISSION_SLUG)
    payload = events[0]["payload"]
    assert payload["origin_surface"] == OriginSurface.PLANNING_INTERVIEW.value


def test_emit_decision_opened_payload_roundtrip(tmp_path: Path) -> None:
    """Payload round-trips through DecisionPointOpenedInterviewPayload."""
    entry = _make_entry("01DDDDDDDDDDDDDDDDDDDDDDDD")
    emit_decision_opened(
        tmp_path, MISSION_SLUG, decision_id="01DDDDDDDDDDDDDDDDDDDDDDDD", entry=entry, actor=ACTOR
    )
    events = _read_events(tmp_path, MISSION_SLUG)
    payload_dict = events[0]["payload"]
    # Should not raise
    model = DecisionPointOpenedInterviewPayload.model_validate(payload_dict)
    assert model.decision_point_id == "01DDDDDDDDDDDDDDDDDDDDDDDD"
    assert model.origin_surface == OriginSurface.PLANNING_INTERVIEW
    assert model.question == "Which auth strategy?"
    assert model.actor_id == ACTOR


def test_emit_decision_opened_step_id_wire_uses_slot_key_fallback(tmp_path: Path) -> None:
    """When step_id is None, slot_key is used as the wire step_id."""
    entry = _make_entry("01EEEEEEEEEEEEEEEEEEEEEEEE", step_id=None, slot_key="specify.q1")
    emit_decision_opened(
        tmp_path, MISSION_SLUG, decision_id="01EEEEEEEEEEEEEEEEEEEEEEEE", entry=entry, actor=ACTOR
    )
    events = _read_events(tmp_path, MISSION_SLUG)
    payload = events[0]["payload"]
    assert payload["step_id"] == "specify.q1"


# ---------------------------------------------------------------------------
# Tests: emit_decision_resolved (resolved)
# ---------------------------------------------------------------------------


def test_emit_decision_resolved_writes_resolved_event(tmp_path: Path) -> None:
    """emit_decision_resolved emits DecisionPointResolved."""
    entry = _make_entry(
        "01FFFFFFFFFFFFFFFFFFFFFFFG",
        status=DecisionStatus.RESOLVED,
        final_answer="oauth2",
        resolved_at=datetime(2026, 4, 23, 10, 1, 0, tzinfo=UTC),
        resolved_by=ACTOR,
    )
    lamport = emit_decision_resolved(
        tmp_path, MISSION_SLUG, decision_id="01FFFFFFFFFFFFFFFFFFFFFFFG", entry=entry, actor=ACTOR
    )
    events = _read_events(tmp_path, MISSION_SLUG)
    assert len(events) == 1
    assert events[0]["event_type"] == DECISION_POINT_RESOLVED
    assert lamport == 1


def test_emit_decision_resolved_payload_has_final_answer(tmp_path: Path) -> None:
    """Resolved event payload contains final_answer."""
    entry = _make_entry(
        "01GGGGGGGGGGGGGGGGGGGGGGGX",
        status=DecisionStatus.RESOLVED,
        final_answer="session",
        resolved_at=datetime(2026, 4, 23, 10, 2, 0, tzinfo=UTC),
        resolved_by=ACTOR,
    )
    emit_decision_resolved(
        tmp_path, MISSION_SLUG, decision_id="01GGGGGGGGGGGGGGGGGGGGGGGX", entry=entry, actor=ACTOR
    )
    events = _read_events(tmp_path, MISSION_SLUG)
    payload = events[0]["payload"]
    assert payload["terminal_outcome"] == "resolved"
    assert payload["final_answer"] == "session"


def test_emit_decision_resolved_payload_roundtrip(tmp_path: Path) -> None:
    """Resolved payload round-trips through DecisionPointResolvedInterviewPayload."""
    entry = _make_entry(
        "01HHHHHHHHHHHHHHHHHHHHHHHX",
        status=DecisionStatus.RESOLVED,
        final_answer="oauth2",
        resolved_at=datetime(2026, 4, 23, 10, 3, 0, tzinfo=UTC),
        resolved_by=ACTOR,
    )
    emit_decision_resolved(
        tmp_path, MISSION_SLUG, decision_id="01HHHHHHHHHHHHHHHHHHHHHHHX", entry=entry, actor=ACTOR
    )
    events = _read_events(tmp_path, MISSION_SLUG)
    payload_dict = events[0]["payload"]
    model = DecisionPointResolvedInterviewPayload.model_validate(payload_dict)
    assert model.terminal_outcome.value == "resolved"
    assert model.final_answer == "oauth2"
    assert model.origin_surface == OriginSurface.PLANNING_INTERVIEW


# ---------------------------------------------------------------------------
# Tests: emit_decision_resolved (deferred)
# ---------------------------------------------------------------------------


def test_emit_decision_resolved_deferred_has_rationale(tmp_path: Path) -> None:
    """Deferred event has no final_answer and rationale is set."""
    entry = _make_entry(
        "01IIIIIIIIIIIIIIIIIIIIIIIIX",
        status=DecisionStatus.DEFERRED,
        rationale="discuss with team",
        resolved_at=datetime(2026, 4, 23, 10, 4, 0, tzinfo=UTC),
        resolved_by=ACTOR,
    )
    emit_decision_resolved(
        tmp_path, MISSION_SLUG, decision_id="01IIIIIIIIIIIIIIIIIIIIIIIIX", entry=entry, actor=ACTOR
    )
    events = _read_events(tmp_path, MISSION_SLUG)
    payload = events[0]["payload"]
    assert payload["event_type"] if "event_type" in payload else events[0]["event_type"] == DECISION_POINT_RESOLVED
    assert events[0]["event_type"] == DECISION_POINT_RESOLVED
    assert payload["terminal_outcome"] == "deferred"
    assert payload.get("final_answer") is None
    assert payload["rationale"] == "discuss with team"


def test_emit_decision_resolved_deferred_payload_roundtrip(tmp_path: Path) -> None:
    """Deferred payload validates against Pydantic model."""
    entry = _make_entry(
        "01JJJJJJJJJJJJJJJJJJJJJJJX",
        status=DecisionStatus.DEFERRED,
        rationale="revisit later",
        resolved_at=datetime(2026, 4, 23, 10, 5, 0, tzinfo=UTC),
        resolved_by=ACTOR,
    )
    emit_decision_resolved(
        tmp_path, MISSION_SLUG, decision_id="01JJJJJJJJJJJJJJJJJJJJJJJX", entry=entry, actor=ACTOR
    )
    events = _read_events(tmp_path, MISSION_SLUG)
    payload_dict = events[0]["payload"]
    model = DecisionPointResolvedInterviewPayload.model_validate(payload_dict)
    assert model.terminal_outcome.value == "deferred"
    assert model.final_answer is None
    assert model.rationale == "revisit later"


# ---------------------------------------------------------------------------
# Tests: fan-out (#324) -- ordering, exact identity, transport-failure
# ---------------------------------------------------------------------------


def test_emit_decision_opened_fanout_sees_the_append_already_durable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fan-out must run strictly after the local append, never racing it.

    Proven by reading the events file back from *inside* the fake fan-out
    call: if the append hadn't already completed and been flushed, the file
    would be empty or missing at that point.
    """
    entry = _make_entry("01KAAAAAAAAAAAAAAAAAAAAAAA")
    seen_lines: list[str] = []

    def fake_fanout(*, envelope: dict, log_path: Path) -> None:
        seen_lines.extend(log_path.read_text().splitlines())

    monkeypatch.setattr("specify_cli.status.fire_lifecycle_saas_fanout", fake_fanout)

    emit_decision_opened(
        tmp_path, MISSION_SLUG, decision_id="01KAAAAAAAAAAAAAAAAAAAAAAA", entry=entry, actor=ACTOR
    )

    assert len(seen_lines) == 1
    assert json.loads(seen_lines[0])["event_type"] == DECISION_POINT_OPENED


def test_emit_decision_opened_fanout_envelope_matches_the_local_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The envelope offered to fan-out carries the same identity/kind/payload
    as the event already durably appended -- no second source of truth."""
    entry = _make_entry("01KCCCCCCCCCCCCCCCCCCCCCCC")
    captured: dict = {}

    def fake_fanout(*, envelope: dict, log_path: Path) -> None:
        captured["envelope"] = envelope
        captured["log_path"] = log_path

    monkeypatch.setattr("specify_cli.status.fire_lifecycle_saas_fanout", fake_fanout)

    emit_decision_opened(
        tmp_path, MISSION_SLUG, decision_id="01KCCCCCCCCCCCCCCCCCCCCCCC", entry=entry, actor=ACTOR
    )

    local_event = _read_events(tmp_path, MISSION_SLUG)[0]
    envelope = captured["envelope"]
    assert envelope["event_id"] == local_event["event_id"]
    assert envelope["event_type"] == DECISION_POINT_OPENED == local_event["event_type"]
    assert envelope["aggregate_id"] == MISSION_SLUG
    assert envelope["schema_version"] == DECISIONPOINT_SCHEMA_VERSION
    assert envelope["timestamp"] == local_event["at"]
    assert envelope["payload"] == local_event["payload"]
    assert captured["log_path"] == tmp_path / "kitty-specs" / MISSION_SLUG / "status.events.jsonl"


def test_emit_decision_opened_survives_a_fanout_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A relay/transport failure is logged and dropped -- it can never roll
    back or otherwise affect the canonical local write that already
    happened before fan-out was attempted."""
    entry = _make_entry("01KBBBBBBBBBBBBBBBBBBBBBBB")

    def exploding_fanout(*, envelope: dict, log_path: Path) -> None:
        raise RuntimeError("relay unreachable")

    monkeypatch.setattr("specify_cli.status.fire_lifecycle_saas_fanout", exploding_fanout)
    caplog.set_level(logging.WARNING)

    lamport = emit_decision_opened(
        tmp_path, MISSION_SLUG, decision_id="01KBBBBBBBBBBBBBBBBBBBBBBB", entry=entry, actor=ACTOR
    )

    assert lamport == 1
    events = _read_events(tmp_path, MISSION_SLUG)
    assert len(events) == 1
    assert events[0]["event_type"] == DECISION_POINT_OPENED
    assert "Zeitgeist fan-out failed" in caplog.text


def test_emit_decision_resolved_fanout_envelope_matches_the_local_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    entry = _make_entry(
        "01KDDDDDDDDDDDDDDDDDDDDDDD",
        status=DecisionStatus.RESOLVED,
        final_answer="oauth2",
        resolved_at=datetime(2026, 4, 23, 10, 6, 0, tzinfo=UTC),
        resolved_by=ACTOR,
    )
    captured: dict = {}

    def fake_fanout(*, envelope: dict, log_path: Path) -> None:
        captured["envelope"] = envelope

    monkeypatch.setattr("specify_cli.status.fire_lifecycle_saas_fanout", fake_fanout)

    emit_decision_resolved(
        tmp_path, MISSION_SLUG, decision_id="01KDDDDDDDDDDDDDDDDDDDDDDD", entry=entry, actor=ACTOR
    )

    local_event = _read_events(tmp_path, MISSION_SLUG)[0]
    envelope = captured["envelope"]
    assert envelope["event_id"] == local_event["event_id"]
    assert envelope["event_type"] == DECISION_POINT_RESOLVED == local_event["event_type"]
    assert envelope["payload"] == local_event["payload"]


def test_emit_decision_resolved_survives_a_fanout_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    entry = _make_entry(
        "01KEEEEEEEEEEEEEEEEEEEEEEE",
        status=DecisionStatus.RESOLVED,
        final_answer="session",
        resolved_at=datetime(2026, 4, 23, 10, 7, 0, tzinfo=UTC),
        resolved_by=ACTOR,
    )

    def exploding_fanout(*, envelope: dict, log_path: Path) -> None:
        raise RuntimeError("relay unreachable")

    monkeypatch.setattr("specify_cli.status.fire_lifecycle_saas_fanout", exploding_fanout)
    caplog.set_level(logging.WARNING)

    lamport = emit_decision_resolved(
        tmp_path, MISSION_SLUG, decision_id="01KEEEEEEEEEEEEEEEEEEEEEEE", entry=entry, actor=ACTOR
    )

    assert lamport == 1
    events = _read_events(tmp_path, MISSION_SLUG)
    assert len(events) == 1
    assert events[0]["event_type"] == DECISION_POINT_RESOLVED
    assert "Zeitgeist fan-out failed" in caplog.text
