"""Unit tests for the runtime-moment producer at the emitter seam (#3929).

The engine-free half of the E3 coverage: journal-derived identity and time,
transition-level idempotency, mission identity stamping (S11), the fail-closed
drops, fan-out failure isolation, codec compatibility of every envelope the
producer builds, and the status seam's registration under the moment-handler
gate. The real bridge walk lives in ``test_runtime_moments.py``.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import BaseModel
from spec_kitty_events.mission_next import (
    DecisionInputAnsweredPayload,
    DecisionInputRequestedPayload,
    MissionRunCompletedPayload,
    MissionRunStartedPayload,
    NextStepAutoCompletedPayload,
    NextStepIssuedPayload,
    RuntimeActorIdentity,
)
from spec_kitty_events.zeitgeist_attrs import to_zeitgeist_attrs

from runtime.next._internal_runtime import events as events_mod
from runtime.next._internal_runtime.events import NullEmitter, RuntimeEventEmitter
from specify_cli.events import runtime_moments as rm
from specify_cli.events.runtime_moments import JournalRecord, RuntimeMomentProducer
from specify_cli.status import adapters, zeitgeist_bridge

pytestmark = [pytest.mark.unit, pytest.mark.fast]

RUN_ID = "0123456789abcdef0123456789abcdef"
SLUG = "042-runtime-moments"
MISSION_ULID = "01KNRQK0R1ZDS8Z57M1TRXF0XR"
STAMP = "2026-09-13T21:00:00+00:00"
LATER_STAMP = "2026-09-13T21:05:00+00:00"
PRODUCER_LOGGER = "specify_cli.events.runtime_moments"

EMIT_METHOD_BY_KIND = {
    "MissionRunStarted": "emit_mission_run_started",
    "NextStepIssued": "emit_next_step_issued",
    "NextStepAutoCompleted": "emit_next_step_auto_completed",
    "DecisionInputRequested": "emit_decision_input_requested",
    "DecisionInputAnswered": "emit_decision_input_answered",
    "MissionRunCompleted": "emit_mission_run_completed",
}


def _actor() -> RuntimeActorIdentity:
    return RuntimeActorIdentity(actor_id="test-agent", actor_type="llm")


def _payload(kind: str, *, step_id: str = "specify") -> BaseModel:
    payloads: dict[str, BaseModel] = {
        "MissionRunStarted": MissionRunStartedPayload(run_id=RUN_ID, mission_type="software-dev", actor=_actor()),
        "NextStepIssued": NextStepIssuedPayload(run_id=RUN_ID, step_id=step_id, agent_id="test-agent", actor=_actor()),
        "NextStepAutoCompleted": NextStepAutoCompletedPayload(run_id=RUN_ID, step_id=step_id, agent_id="test-agent", result="success", actor=_actor()),
        "DecisionInputRequested": DecisionInputRequestedPayload(
            run_id=RUN_ID,
            decision_id="input:approval",
            step_id="collect_input",
            question="Ship the release?",
            options=("yes", "no"),
            input_key="approval",
            actor=_actor(),
        ),
        "DecisionInputAnswered": DecisionInputAnsweredPayload(run_id=RUN_ID, decision_id="input:approval", answer="yes, ship it", actor=_actor()),
        "MissionRunCompleted": MissionRunCompletedPayload(run_id=RUN_ID, mission_type="software-dev", actor=_actor()),
    }
    return payloads[kind]


def _layout(root: Path, mission_parent: Path | None = None) -> tuple[Path, Path]:
    """A repository root holding one run; returns ``(feature_dir, journal_path)``."""
    feature_dir = (mission_parent or root) / "kitty-specs" / SLUG
    feature_dir.mkdir(parents=True)
    run_dir = root / ".kittify" / "runtime" / "runs" / RUN_ID
    run_dir.mkdir(parents=True)
    return feature_dir, run_dir / "run.events.jsonl"


def _append(journal: Path, kind: str, payload: BaseModel, timestamp: str = STAMP) -> None:
    """Append one record exactly as ``engine._append_event`` serialises it."""
    record = {"event_type": kind, "timestamp": timestamp, "payload": payload.model_dump(mode="json")}
    with journal.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, default=str) + "\n")


def _emit(producer: RuntimeMomentProducer, kind: str, payload: BaseModel) -> None:
    getattr(producer, EMIT_METHOD_BY_KIND[kind])(payload)


def _stamped(payload: BaseModel, **identity: str) -> dict[str, Any]:
    return {**payload.model_dump(mode="json"), "mission_slug": SLUG, **identity}


@pytest.fixture
def published(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    captured: list[dict[str, Any]] = []
    monkeypatch.setattr("specify_cli.status.fire_lifecycle_saas_fanout", lambda **kwargs: captured.append(kwargs))
    return captured


def _producer(feature_dir: Path) -> RuntimeMomentProducer:
    return RuntimeMomentProducer.for_mission(feature_dir=feature_dir, mission_slug=SLUG, mission_type="software-dev")


# ---------------------------------------------------------------------------
# Seam conformance and statelessness (RISK-2, S9-S10)
# ---------------------------------------------------------------------------


def test_producer_implements_every_emit_method_of_the_protocol(tmp_path: Path) -> None:
    producer = _producer(tmp_path)
    protocol_methods = [name for name in RuntimeEventEmitter.__dict__ if name.startswith("emit_")]

    assert len(protocol_methods) == 8
    assert [name for name in protocol_methods if not callable(getattr(producer, name, None))] == []


def test_seeding_is_a_side_effect_free_noop(tmp_path: Path, published: list[dict[str, Any]]) -> None:
    feature_dir, journal = _layout(tmp_path)
    producer = _producer(feature_dir)

    assert producer.seed_from_snapshot(object()) is None
    assert producer.seed_from_snapshot(None) is None
    assert published == []
    assert not journal.exists()


def test_significance_and_timeout_are_not_runtime_moments(tmp_path: Path, published: list[dict[str, Any]]) -> None:
    producer = _producer(tmp_path)

    producer.emit_significance_evaluated(cast(Any, object()))
    producer.emit_decision_timeout_expired(cast(Any, object()))

    assert published == []


# ---------------------------------------------------------------------------
# Journal-derived identity and time
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", sorted(EMIT_METHOD_BY_KIND))
def test_each_runtime_moment_publishes_its_journal_record(tmp_path: Path, published: list[dict[str, Any]], kind: str) -> None:
    feature_dir, journal = _layout(tmp_path)
    payload = _payload(kind)
    _append(journal, kind, payload)

    _emit(_producer(feature_dir), kind, payload)

    assert len(published) == 1
    call = published[0]
    assert call["log_path"] == journal
    assert call["envelope"] == {
        "event_id": rm.moment_event_id(RUN_ID, JournalRecord(line=1, timestamp=STAMP), kind),
        "event_type": kind,
        "aggregate_id": SLUG,
        "timestamp": STAMP,
        "payload": _stamped(payload),
    }


def test_republishing_the_same_record_reuses_its_event_id(tmp_path: Path, published: list[dict[str, Any]]) -> None:
    """A retried publish or a reconstructed producer is the same moment, not a new one."""
    feature_dir, journal = _layout(tmp_path)
    payload = _payload("NextStepIssued")
    _append(journal, "NextStepIssued", payload)

    _emit(_producer(feature_dir), "NextStepIssued", payload)
    _emit(_producer(feature_dir), "NextStepIssued", payload)

    first, second = (call["envelope"] for call in published)
    assert first == second


def test_a_new_transition_with_an_identical_payload_is_a_new_moment(tmp_path: Path, published: list[dict[str, Any]]) -> None:
    """A re-issued step journals a second record, so it publishes under a second identity."""
    feature_dir, journal = _layout(tmp_path)
    payload = _payload("NextStepIssued")
    producer = _producer(feature_dir)

    _append(journal, "NextStepIssued", payload, STAMP)
    _emit(producer, "NextStepIssued", payload)
    _append(journal, "NextStepIssued", payload, LATER_STAMP)
    _emit(producer, "NextStepIssued", payload)

    first, second = (call["envelope"] for call in published)
    assert first["event_id"] != second["event_id"]
    assert (first["timestamp"], second["timestamp"]) == (STAMP, LATER_STAMP)


def test_a_buffered_flush_after_later_records_resolves_its_own_record(tmp_path: Path, published: list[dict[str, Any]]) -> None:
    feature_dir, journal = _layout(tmp_path)
    completed = _payload("NextStepAutoCompleted", step_id="specify")
    issued = _payload("NextStepIssued", step_id="plan")
    _append(journal, "NextStepAutoCompleted", completed, STAMP)
    _append(journal, "NextStepIssued", issued, LATER_STAMP)

    _emit(_producer(feature_dir), "NextStepAutoCompleted", completed)

    envelope = published[0]["envelope"]
    assert envelope["timestamp"] == STAMP
    assert envelope["event_id"] == rm.moment_event_id(RUN_ID, JournalRecord(line=1, timestamp=STAMP), "NextStepAutoCompleted")


def test_blank_torn_and_non_object_lines_are_skipped(tmp_path: Path) -> None:
    _feature_dir, journal = _layout(tmp_path)
    payload = _payload("MissionRunStarted")
    journal.write_text('\n{"event_type": "MissionRunStarted", "tor\n[1, 2]\n', encoding="utf-8")
    _append(journal, "MissionRunStarted", payload)

    record = rm.latest_matching_record(journal, "MissionRunStarted", payload.model_dump(mode="json"))

    assert record == JournalRecord(line=4, timestamp=STAMP)


def test_the_journal_is_found_from_a_mission_dir_nested_in_a_worktree(tmp_path: Path) -> None:
    feature_dir, journal = _layout(tmp_path, mission_parent=tmp_path / ".worktrees" / f"{SLUG}-coord")
    _append(journal, "MissionRunStarted", _payload("MissionRunStarted"))

    assert rm.find_run_journal(feature_dir, RUN_ID) == journal


@pytest.mark.parametrize("run_id", ["", "..", "../escape", "a/b"])
def test_an_unsafe_run_id_never_resolves_a_journal(tmp_path: Path, run_id: str) -> None:
    feature_dir, _journal = _layout(tmp_path)

    assert rm.find_run_journal(feature_dir, run_id) is None


# ---------------------------------------------------------------------------
# Mission identity stamping (S11)
# ---------------------------------------------------------------------------


def test_the_published_payload_carries_the_mission_ulid_from_meta(tmp_path: Path, published: list[dict[str, Any]]) -> None:
    feature_dir, journal = _layout(tmp_path)
    (feature_dir / "meta.json").write_text(json.dumps({"mission_id": MISSION_ULID}), encoding="utf-8")
    payload = _payload("MissionRunStarted")
    _append(journal, "MissionRunStarted", payload)

    _emit(_producer(feature_dir), "MissionRunStarted", payload)

    envelope = published[0]["envelope"]
    assert envelope["payload"] == _stamped(payload, mission_id=MISSION_ULID)
    assert envelope["event_id"] == rm.moment_event_id(RUN_ID, JournalRecord(line=1, timestamp=STAMP), "MissionRunStarted"), (
        "stamping identity never changes which journal record the moment is keyed on"
    )


def test_engine_supplied_identity_is_never_overwritten(tmp_path: Path, published: list[dict[str, Any]]) -> None:
    feature_dir, journal = _layout(tmp_path)
    (feature_dir / "meta.json").write_text(json.dumps({"mission_id": MISSION_ULID}), encoding="utf-8")
    payload = MissionRunCompletedPayload(
        run_id=RUN_ID,
        mission_type="software-dev",
        actor=_actor(),
        mission_slug="engine-slug",
        mission_id="01ENGINESUPPLIED0000000000",
    )
    _append(journal, "MissionRunCompleted", payload)

    _emit(_producer(feature_dir), "MissionRunCompleted", payload)

    stamped = published[0]["envelope"]["payload"]
    assert (stamped["mission_slug"], stamped["mission_id"]) == ("engine-slug", "01ENGINESUPPLIED0000000000")


def test_an_unreadable_meta_degrades_to_slug_only_identity(tmp_path: Path, published: list[dict[str, Any]]) -> None:
    feature_dir, journal = _layout(tmp_path)
    (feature_dir / "meta.json").write_text("{not json", encoding="utf-8")
    payload = _payload("NextStepIssued")
    _append(journal, "NextStepIssued", payload)

    _emit(_producer(feature_dir), "NextStepIssued", payload)

    assert published[0]["envelope"]["payload"] == _stamped(payload)


# ---------------------------------------------------------------------------
# Fail-closed drops and failure isolation
# ---------------------------------------------------------------------------


def test_a_run_without_a_journal_publishes_nothing(tmp_path: Path, published: list[dict[str, Any]], caplog: pytest.LogCaptureFixture) -> None:
    feature_dir = tmp_path / "kitty-specs" / SLUG
    feature_dir.mkdir(parents=True)

    with caplog.at_level(logging.WARNING, logger=PRODUCER_LOGGER):
        _emit(_producer(feature_dir), "MissionRunStarted", _payload("MissionRunStarted"))

    assert published == []
    assert "no run journal" in caplog.text


def test_an_unjournalled_moment_publishes_nothing(tmp_path: Path, published: list[dict[str, Any]], caplog: pytest.LogCaptureFixture) -> None:
    feature_dir, journal = _layout(tmp_path)
    _append(journal, "MissionRunStarted", _payload("MissionRunStarted"))

    with caplog.at_level(logging.WARNING, logger=PRODUCER_LOGGER):
        _emit(_producer(feature_dir), "MissionRunCompleted", _payload("MissionRunCompleted"))

    assert published == []
    assert "not journalled" in caplog.text


def test_a_fanout_failure_never_raises_into_the_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    feature_dir, journal = _layout(tmp_path)
    payload = _payload("DecisionInputAnswered")
    _append(journal, "DecisionInputAnswered", payload)

    def explode(**_kwargs: Any) -> None:
        raise RuntimeError("relay unreachable")

    monkeypatch.setattr("specify_cli.status.fire_lifecycle_saas_fanout", explode)

    with caplog.at_level(logging.WARNING, logger=PRODUCER_LOGGER):
        _emit(_producer(feature_dir), "DecisionInputAnswered", payload)

    assert "not published" in caplog.text


# ---------------------------------------------------------------------------
# Every envelope decodes through the real lifecycle handler and codec
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", sorted(EMIT_METHOD_BY_KIND))
def test_every_envelope_projects_through_the_released_codec_without_decision_prose(
    tmp_path: Path, published: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    feature_dir, journal = _layout(tmp_path)
    (feature_dir / "meta.json").write_text(json.dumps({"mission_id": MISSION_ULID}), encoding="utf-8")
    payload = _payload(kind)
    _append(journal, kind, payload)
    _emit(_producer(feature_dir), kind, payload)

    broadcast: list[tuple[BaseModel, Any]] = []
    monkeypatch.setattr(zeitgeist_bridge, "_broadcast_moment", lambda model, envelope, **_kw: broadcast.append((model, envelope)))
    zeitgeist_bridge.lifecycle_moment_handler(**published[0])

    assert len(broadcast) == 1, f"the lifecycle handler must accept the {kind} envelope"
    attrs = to_zeitgeist_attrs(*broadcast[0])
    assert attrs["event_id"] == published[0]["envelope"]["event_id"]
    assert attrs["occurred_at"] == STAMP
    assert attrs["run_id"] == RUN_ID
    assert {"question", "options", "answer"}.isdisjoint(attrs)


# ---------------------------------------------------------------------------
# Registration by the status seam, under the moment-handler gate
# ---------------------------------------------------------------------------


@pytest.fixture
def production_wiring() -> Iterator[None]:
    events_mod.reset_runtime_emitter_factory()
    try:
        adapters.ensure_runtime_moment_producer()
        yield
    finally:
        events_mod.reset_runtime_emitter_factory()


@pytest.mark.usefixtures("production_wiring")
def test_the_status_seam_registers_the_producer(tmp_path: Path) -> None:
    adapters.ensure_runtime_moment_producer()  # idempotent re-registration must not raise

    product = events_mod.runtime_emitter_for_mission(feature_dir=tmp_path, mission_slug=SLUG, mission_type="software-dev")

    assert isinstance(product, RuntimeMomentProducer)


@pytest.mark.usefixtures("production_wiring")
def test_the_moment_handler_gate_disarms_the_producer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPEC_KITTY_NO_MOMENT_HANDLERS", "1")

    product = events_mod.runtime_emitter_for_mission(feature_dir=tmp_path, mission_slug=SLUG, mission_type="software-dev")

    assert isinstance(product, NullEmitter)


@pytest.mark.usefixtures("production_wiring")
def test_idempotent_reregistration_is_logged_at_debug(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG, logger="runtime.next._internal_runtime.events"):
        events_mod.register_runtime_emitter_factory(RuntimeMomentProducer.for_mission)

    assert "rebinding" in caplog.text


def test_moment_handler_wiring_never_registers_the_runtime_producer(tmp_path: Path) -> None:
    """The status import-tail wiring must not touch the runtime seam: that re-enters ``runtime.next`` mid-import."""
    events_mod.reset_runtime_emitter_factory()
    try:
        adapters.ensure_zeitgeist_moment_handlers()

        product = events_mod.runtime_emitter_for_mission(feature_dir=tmp_path, mission_slug=SLUG, mission_type="software-dev")

        assert isinstance(product, NullEmitter)
    finally:
        events_mod.reset_runtime_emitter_factory()
