"""The runtime-moment producer at the consolidated emitter seam (E3, #3929).

The mission runtime journals each run transition to its canonical
``run.events.jsonl`` and then calls the :class:`RuntimeEventEmitter` the bridge
obtained from ``runtime_emitter_for_mission``. This producer is what that seam
returns in a normal CLI process: it publishes the six ``mission_next`` runtime
moments (run started/completed, step issued/auto-completed, decision input
requested/answered) through the existing bounded lifecycle fan-out
(``status.adapters.fire_lifecycle_saas_fanout`` -> the Zeitgeist moment
handler), exactly the path decision and mission-lifecycle moments already take.

Identity and time come from the journal, never from this process:

* The moment's ``timestamp`` is the journal record's own occurrence stamp.
* Its ``event_id`` is a UUID5 of ``(run_id, journal line, event type)``. The
  engine appends a record and then emits it, so the most recent record with the
  same type and payload *is* this transition. A reconstructed producer, a
  retried publish, or a buffered flush that arrives after later records all
  resolve to the same line and therefore the same ``event_id``; a genuinely new
  transition is a new line and a new id. Consumers that upsert on ``event_id``
  (Team Kitty's Pulse) see one moment per transition. That is transition-level
  idempotency of what is published, not a delivery guarantee: the fan-out stays
  bounded, best-effort and unretried.

A moment whose run journal or journal record cannot be found is not published:
without a canonical identity it could only be published under an invented one.

Engine payloads carry run/step/decision correlation but leave the optional
``mission_slug``/``mission_id`` empty. Per contract rule S11 the factory
resolves the mission's identity once and the published payload is stamped with
it when those fields are empty; the journal record is matched on the engine's
own payload, so stamping never changes a moment's identity.

The product is per-call and stateless (contract rules S9-S10): it never depends
on seeding order, so ``seed_from_snapshot`` is a no-op, and ``MissionRunStarted``
emitted before any seed publishes like every other moment. Wire content is owned
by the ``spec_kitty_events`` codec behind the fan-out, which keeps decision
question/option/answer prose out of moment attrs.

Nothing here raises into the runtime: a failure is logged and the moment is
dropped, so local mission state is unaffected by relay, credential, codec or
journal problems.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from runtime.next._internal_runtime.events import (
    DECISION_INPUT_ANSWERED,
    DECISION_INPUT_REQUESTED,
    MISSION_RUN_COMPLETED,
    MISSION_RUN_STARTED,
    NEXT_STEP_AUTO_COMPLETED,
    NEXT_STEP_ISSUED,
    DecisionInputAnsweredPayload,
    DecisionInputRequestedPayload,
    MissionRunCompletedPayload,
    MissionRunStartedPayload,
    NextStepAutoCompletedPayload,
    NextStepIssuedPayload,
)
from runtime.next._internal_runtime.significance import (
    SignificanceEvaluatedPayload,
    TimeoutExpiredPayload,
)
from specify_cli.core.constants import KITTIFY_DIR
from specify_cli.core.paths import assert_safe_path_segment
from specify_cli.mission_metadata import resolve_mission_identity

__all__ = ["RuntimeMomentProducer"]

logger = logging.getLogger(__name__)

RUN_JOURNAL_NAME = "run.events.jsonl"
_RUNS_RELATIVE = Path(KITTIFY_DIR) / "runtime" / "runs"
_EVENT_ID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "urn:spec-kitty:runtime-moment")


@dataclass(frozen=True)
class JournalRecord:
    """One canonical run-journal line that a published moment is keyed on."""

    line: int
    timestamp: str


def find_run_journal(feature_dir: Path, run_id: str) -> Path | None:
    """Return ``<root>/.kittify/runtime/runs/<run_id>/run.events.jsonl`` above ``feature_dir``.

    Runs live under the repository root that ``get_or_start_run`` was given.
    Walking up from the mission directory reaches that root from the primary
    checkout and from a worktree nested inside it. An unsafe ``run_id`` is never
    joined into a path.
    """
    try:
        safe_run_id: str = assert_safe_path_segment(run_id)
    except ValueError:
        return None
    for root in (feature_dir, *feature_dir.parents):
        candidate = root / _RUNS_RELATIVE / safe_run_id / RUN_JOURNAL_NAME
        if candidate.is_file():
            return candidate
    return None


def latest_matching_record(journal: Path, event_type: str, payload: dict[str, Any]) -> JournalRecord | None:
    """Return the most recent journal line carrying exactly this event type and payload."""
    match: JournalRecord | None = None
    with journal.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            record = _parse_record(line)
            if record is None:
                continue
            if record.get("event_type") == event_type and record.get("payload") == payload:
                match = JournalRecord(line=line_number, timestamp=str(record.get("timestamp") or ""))
    return match


def _parse_record(line: str) -> dict[str, Any] | None:
    """Parse one journal line; a blank or torn line (crash mid-append) is skipped."""
    stripped = line.strip()
    if not stripped:
        return None
    try:
        record = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    return record if isinstance(record, dict) else None


def moment_event_id(run_id: str, record: JournalRecord, event_type: str) -> str:
    """The deterministic ``event_id`` of the moment published for one journal line."""
    return str(uuid.uuid5(_EVENT_ID_NAMESPACE, f"{run_id}:{record.line}:{event_type}"))


def _resolve_mission_id(feature_dir: Path) -> str | None:
    """The mission's canonical ULID when ``meta.json`` records one; identity is informational (S11)."""
    try:
        mission_id: str | None = resolve_mission_identity(feature_dir).mission_id
    except Exception:  # noqa: BLE001 -- as in NullEmitter.for_mission, the seam must never raise
        return None
    return mission_id


class RuntimeMomentProducer:
    """Publish the six runtime moments for one mission (a per-call product, S9)."""

    def __init__(self, *, feature_dir: Path, mission_slug: str, mission_id: str | None = None) -> None:
        self._feature_dir = feature_dir
        self._mission_slug = mission_slug
        self._mission_id = mission_id

    @classmethod
    def for_mission(cls, *, feature_dir: Path, mission_slug: str, mission_type: str) -> RuntimeMomentProducer:
        """The factory registered with ``register_runtime_emitter_factory``."""
        del mission_type  # the payloads carry the mission type where the contract defines it
        return cls(feature_dir=feature_dir, mission_slug=mission_slug, mission_id=_resolve_mission_id(feature_dir))

    def seed_from_snapshot(self, snapshot: Any) -> None:
        """No-op: identity comes from each payload and its journal record, never from seeding (S10)."""
        del snapshot

    def emit_mission_run_started(self, payload: MissionRunStartedPayload) -> None:
        self._publish(MISSION_RUN_STARTED, payload)

    def emit_next_step_issued(self, payload: NextStepIssuedPayload) -> None:
        self._publish(NEXT_STEP_ISSUED, payload)

    def emit_next_step_auto_completed(self, payload: NextStepAutoCompletedPayload) -> None:
        self._publish(NEXT_STEP_AUTO_COMPLETED, payload)

    def emit_decision_input_requested(self, payload: DecisionInputRequestedPayload) -> None:
        self._publish(DECISION_INPUT_REQUESTED, payload)

    def emit_decision_input_answered(self, payload: DecisionInputAnsweredPayload) -> None:
        self._publish(DECISION_INPUT_ANSWERED, payload)

    def emit_mission_run_completed(self, payload: MissionRunCompletedPayload) -> None:
        self._publish(MISSION_RUN_COMPLETED, payload)

    def emit_significance_evaluated(self, payload: SignificanceEvaluatedPayload) -> None:
        """Not a runtime moment: significance stays in the local run journal."""
        del payload

    def emit_decision_timeout_expired(self, payload: TimeoutExpiredPayload) -> None:
        """Not a runtime moment: timeout expiry stays in the local run journal."""
        del payload

    def _publish(self, event_type: str, payload: BaseModel) -> None:
        try:
            self._publish_journalled(event_type, payload)
        except Exception:
            logger.warning(
                "Runtime moment %s not published; mission runtime state unaffected",
                event_type,
                exc_info=True,
            )

    def _publish_journalled(self, event_type: str, payload: BaseModel) -> None:
        payload_dict = payload.model_dump(mode="json")
        run_id = str(payload_dict.get("run_id") or "")
        journal = find_run_journal(self._feature_dir, run_id)
        if journal is None:
            logger.warning("Runtime moment %s not published: no run journal for run %r", event_type, run_id)
            return
        record = latest_matching_record(journal, event_type, payload_dict)
        if record is None:
            logger.warning("Runtime moment %s not published: not journalled in %s", event_type, journal)
            return

        from specify_cli.status import adapters  # noqa: PLC0415 -- the status seam registers this producer

        envelope = {
            "event_id": moment_event_id(run_id, record, event_type),
            "event_type": event_type,
            "aggregate_id": self._mission_slug,
            "timestamp": record.timestamp,
            "payload": self._with_mission_identity(payload_dict),
        }
        adapters.fire_lifecycle_saas_fanout(envelope=envelope, log_path=journal)

    def _with_mission_identity(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Stamp the mission's slug and ULID into the published payload where the engine left them empty."""
        stamped = dict(payload)
        if not stamped.get("mission_slug"):
            stamped["mission_slug"] = self._mission_slug
        if self._mission_id and not stamped.get("mission_id"):
            stamped["mission_id"] = self._mission_id
        return stamped
