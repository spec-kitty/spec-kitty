"""CLI materialization adapter around the shared status reducer.

``status.events.jsonl`` is authoritative. The committed ``status.json`` file is
a derived, human-readable snapshot for older readers; it is regenerated from
the diary and must never be treated as the source of truth.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from spec_kitty_events.diary import State, reduce_parsed
from spec_kitty_events.status import reduce as reduce_shared_state

from specify_cli.mission_metadata import resolve_mission_identity

from .models import (
    InnerStateChanged,
    Lane,
    RetrospectiveSnapshot,
    ReviewResult,
    StatusEvent,
    StatusSnapshot,
)
from .store import StoreError, read_event_stream, read_events_raw

#: Prefixes of the CLI's auto-synthesized cancel reasons. A legacy canceled
#: event whose reason matches one is classified ``synthetic``; any other
#: non-empty reason is treated as operator-authored.
_SYNTHETIC_REASON_PREFIXES: tuple[str, ...] = ("Force move to ", "move-task: ")

#: Derived snapshot written beside the authoritative event diary.
SNAPSHOT_FILENAME = "status.json"

#: The materialized-snapshot schema version a brand-new mission (and any
#: mission already recorded at this version) materializes at. Bumped when a
#: new derived read-root field is added to the snapshot -- #4786's
#: ``implementer_of_record`` is the field that motivated introducing this
#: concept at all (see :func:`_target_schema_version`).
CURRENT_SNAPSHOT_SCHEMA_VERSION = 2

#: The implicit schema version of every snapshot with no ``schema_version``
#: key at all -- every snapshot ever materialized before this concept
#: existed, frozen archives included.
_LEGACY_SNAPSHOT_SCHEMA_VERSION = 1


def _cancellation_reason_source(event: StatusEvent) -> str:
    """Classify a canceled event's provenance as ``operator`` or ``synthetic``."""
    if event.reason_source is not None:
        return event.reason_source
    reason = event.reason
    if reason is None or not reason.strip():
        return "synthetic"
    if reason.startswith(_SYNTHETIC_REASON_PREFIXES):
        return "synthetic"
    return "operator"


def _state_to_snapshot(state: State) -> StatusSnapshot:
    """Convert the shared reducer state to the CLI's snapshot facade type."""
    return StatusSnapshot(
        mission_slug=state.mission_slug,
        materialized_at=state.materialized_at,
        event_count=state.event_count,
        last_event_id=state.last_event_id,
        work_packages=state.work_packages,
        summary=state.summary,
        mission_number=state.mission_number,
        mission_type=state.mission_type,
    )


def _project_cancellation_provenance(
    events: Iterable[StatusEvent],
    snapshot: StatusSnapshot,
) -> None:
    """Preserve the CLI's cancellation provenance compatibility slots.

    The shared reducer owns the common diary fold. Cancellation provenance was
    added to the CLI after the shared reducer port, so this narrow projection
    keeps that accepted CLI behavior until the shared contract carries it.
    """
    seen_event_ids: set[str] = set()
    unique_events = [
        event
        for event in sorted(events, key=lambda item: (item.at, item.event_id))
        if event.event_id not in seen_event_ids and not seen_event_ids.add(event.event_id)
    ]
    for event in unique_events:
        if event.to_lane != Lane.CANCELED:
            continue
        state = snapshot.work_packages.get(event.wp_id)
        if state is None or state.get("lane") != str(event.to_lane):
            continue
        state["cancellation_reason"] = event.reason
        state["reason_source"] = _cancellation_reason_source(event)


#: Read-root derived slot exposing durable implementer-claim provenance
#: (see :func:`_project_implementer_attribution`). Deliberately a NEW key —
#: never one of ``WPInnerStateDelta._SCALAR_FIELDS`` — so it can never be
#: folded, cleared, or blanked by the live-claim replace/release machinery
#: (the fold/release path the projection is required to never touch).
IMPLEMENTER_OF_RECORD_SLOT = "implementer_of_record"


def _project_implementer_attribution(
    events: Iterable[StatusEvent],
    snapshot: StatusSnapshot,
) -> None:
    """Derive durable implementer-claim provenance from the raw event stream.

    #4786's root cause: ``agent`` is a *live-claim* slot that legitimately
    changes hands (implementer -> reviewer) and is correctly RELEASED on a
    review-rejection rollback via the explicit ``release_runtime_claim``
    annotation (#4673) — that release must not be undone. But nothing else
    owned durable *implementer* provenance once the live claim was released,
    so an ordinary reject -> re-review -> approve cycle (no fresh ``--agent``)
    reached ``accept`` reporting no owner at all.

    This is a sibling of :func:`_project_cancellation_provenance`: a narrow,
    read-only, idempotent projection over the immutable raw stream. The ONLY
    transition that ever writes the live ``agent`` runtime slot is a real
    ``planned -> claimed`` hop (the claim exception in
    ``spec_kitty_events.diary._wp_state_from_event`` — carrying the claimant
    in its ``policy_metadata['agent']`` sidecar), so that same transition is
    the durable implementer-of-record fact. The most recent such claim (by
    ``(at, event_id)``) wins, mirroring re-claim-after-rollback. A WP with no
    claim event yields NOTHING (no key written) — never a fabricated owner.

    Exposed on :data:`IMPLEMENTER_OF_RECORD_SLOT`, a slot the fold/release
    path never touches — the live ``agent`` claim keeps its existing
    release semantics byte-for-byte (#4673).
    """
    seen_event_ids: set[str] = set()
    unique_events: list[StatusEvent] = []
    for event in sorted(events, key=lambda item: (item.at, item.event_id)):
        if event.event_id in seen_event_ids:
            continue
        seen_event_ids.add(event.event_id)
        unique_events.append(event)
    for event in unique_events:
        if not (event.from_lane == Lane.PLANNED and event.to_lane == Lane.CLAIMED):
            continue
        claimant = (event.policy_metadata or {}).get("agent")
        if not claimant:
            continue
        state = snapshot.work_packages.get(event.wp_id)
        if state is None:
            continue
        # Latest-wins: unique_events is sorted ascending, so a later claim
        # (a genuine re-claim after rollback) overwrites an earlier one.
        state[IMPLEMENTER_OF_RECORD_SLOT] = str(claimant)


def reduce(
    events: list[StatusEvent],
    annotations: list[InnerStateChanged] | None = None,
) -> StatusSnapshot:
    """Reduce typed CLI events through the shared diary reducer."""
    snapshot = _state_to_snapshot(reduce_parsed(events, annotations or []))
    _project_cancellation_provenance(events, snapshot)
    _project_implementer_attribution(events, snapshot)
    return snapshot


def wp_snapshot_state(feature_dir: Path, wp_id: str) -> Mapping[str, Any] | None:
    """Return the reduced per-WP runtime state for *wp_id*, or ``None``."""
    stream = read_event_stream(feature_dir)
    snapshot = reduce(stream.transitions, stream.annotations)
    return cast("Mapping[str, Any] | None", snapshot.work_packages.get(wp_id))


@dataclass(frozen=True)
class ReviewResultLookup:
    """Outcome of resolving the event-sourced ``review_result`` verdict."""

    slot_present: bool
    result: ReviewResult | None


def review_result_from_state(state: Mapping[str, Any]) -> ReviewResultLookup:
    """Resolve the event-sourced review verdict from a reduced WP state."""
    if "review_result" not in state:
        return ReviewResultLookup(slot_present=False, result=None)
    raw = state["review_result"]
    if raw is None:
        return ReviewResultLookup(slot_present=True, result=None)
    if not isinstance(raw, Mapping):
        return ReviewResultLookup(slot_present=True, result=None)
    try:
        return ReviewResultLookup(
            slot_present=True,
            result=ReviewResult.from_dict(dict(raw)),
        )
    except (KeyError, TypeError, ValueError):
        return ReviewResultLookup(slot_present=True, result=None)


def event_sourced_review_result(feature_dir: Path, wp_id: str) -> ReviewResultLookup:
    """Resolve a WP's event-sourced review verdict, failing closed."""
    try:
        state = wp_snapshot_state(feature_dir, wp_id)
    except StoreError:
        return ReviewResultLookup(slot_present=False, result=None)
    if state is None:
        return ReviewResultLookup(slot_present=False, result=None)
    return review_result_from_state(state)


def _reduce_retrospective(raw_events: list[dict[str, Any]]) -> RetrospectiveSnapshot:
    """Reduce CLI retrospective lifecycle rows from the raw event diary."""
    retro_events = [event for event in raw_events if str(event.get("event_name", "")).startswith("retrospective.")]
    if not retro_events:
        return RetrospectiveSnapshot(status="absent")

    retro_events_sorted = sorted(
        retro_events,
        key=lambda event: (str(event.get("at", "")), str(event.get("event_id", ""))),
    )

    requested_events = [event for event in retro_events_sorted if event.get("event_name") == "retrospective.requested"]
    mode = None
    if requested_events:
        payload = requested_events[-1].get("payload") or {}
        mode_data = payload.get("mode")
        if mode_data is not None:
            try:
                from specify_cli.retrospective.schema import Mode

                mode = Mode.model_validate(mode_data)
            except Exception:
                mode = None

    terminal_names = {
        "retrospective.completed",
        "retrospective.skipped",
        "retrospective.failed",
    }
    terminal_events = [event for event in retro_events_sorted if event.get("event_name") in terminal_names]
    if terminal_events:
        latest_terminal = terminal_events[-1]
        terminal_name = str(latest_terminal.get("event_name", ""))
        if terminal_name == "retrospective.completed":
            retro_status = "completed"
        elif terminal_name == "retrospective.skipped":
            retro_status = "skipped"
        else:
            retro_status = "failed"
        payload = latest_terminal.get("payload") or {}
        record_path_value = payload.get("record_path")
        record_path = record_path_value if isinstance(record_path_value, str) else None
    else:
        retro_status = "pending"
        record_path = None

    proposals_total = sum(1 for event in retro_events if event.get("event_name") == "retrospective.proposal.generated")
    proposals_applied = sum(1 for event in retro_events if event.get("event_name") == "retrospective.proposal.applied")
    proposals_rejected = sum(1 for event in retro_events if event.get("event_name") == "retrospective.proposal.rejected")
    proposals_pending = max(0, proposals_total - proposals_applied - proposals_rejected)

    return RetrospectiveSnapshot(
        status=retro_status,
        mode=mode,
        record_path=record_path,
        proposals_total=proposals_total,
        proposals_applied=proposals_applied,
        proposals_rejected=proposals_rejected,
        proposals_pending=proposals_pending,
    )


def _existing_schema_version(status_path: Path) -> int | None:
    """Return the ``schema_version`` recorded in an existing on-disk snapshot.

    ``None`` covers every case that must NOT be treated as "already on the
    current schema": the file does not exist, is unreadable, is not valid
    JSON, is not a JSON object, has no ``schema_version`` key, or the key's
    value is not an int. Every snapshot materialized before this concept
    existed (frozen archives included) falls into "no key at all" and reads
    back as ``None`` here.
    """
    try:
        raw = status_path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    value = data.get("schema_version")
    return value if isinstance(value, int) else None


def _target_schema_version(feature_dir: Path) -> int:
    """Resolve the schema version THIS ``materialize_snapshot`` call emits at.

    A brand-new mission (no ``status.json`` on disk yet) always materializes
    at :data:`CURRENT_SNAPSHOT_SCHEMA_VERSION` -- carrying the #4786
    ``implementer_of_record`` projection from its very first snapshot.

    An EXISTING snapshot keys its replay off its OWN recorded
    ``schema_version`` rather than off anything about the current code: a
    snapshot already recorded at :data:`CURRENT_SNAPSHOT_SCHEMA_VERSION`
    stays there; a snapshot with no ``schema_version`` key at all -- every
    snapshot ever materialized before this concept existed, frozen archives
    included -- replays at the legacy schema forever, so that a canonical
    replay of a frozen archive
    (``tests/architectural/test_archive_root_byte_identical.py``) stays
    byte-identical to the committed file without weakening that freeze gate,
    and without this reducer needing to know which missions are archived.
    """
    status_path = feature_dir / SNAPSHOT_FILENAME
    if not status_path.exists():
        return CURRENT_SNAPSHOT_SCHEMA_VERSION
    if _existing_schema_version(status_path) == CURRENT_SNAPSHOT_SCHEMA_VERSION:
        return CURRENT_SNAPSHOT_SCHEMA_VERSION
    return _LEGACY_SNAPSHOT_SCHEMA_VERSION


def materialize_to_json(snapshot: StatusSnapshot) -> str:
    """Serialize a snapshot to deterministic, human-readable JSON."""
    return (
        json.dumps(
            snapshot.to_dict(),
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )


def materialize_snapshot(feature_dir: Path) -> StatusSnapshot:
    """Read events and reduce them to the exact snapshot materialize writes."""
    stream = read_event_stream(feature_dir)
    raw_events = read_events_raw(feature_dir)
    snapshot = _state_to_snapshot(reduce_shared_state(raw_events))
    _project_cancellation_provenance(stream.transitions, snapshot)
    # #4786 archive-freeze fix: the implementer-of-record projection is a NEW
    # derived field. Injecting it unconditionally would mean a canonical
    # replay of a pre-#4786 (frozen/archived) snapshot no longer reproduces
    # that snapshot's committed bytes
    # (tests/architectural/test_archive_root_byte_identical.py). Only emit it
    # -- and the schema_version marker that records having done so -- when
    # this snapshot is targeting the current schema; a legacy-schema replay
    # (an existing on-disk snapshot with no schema_version key) stays exactly
    # as it was pre-#4786.
    if _target_schema_version(feature_dir) >= CURRENT_SNAPSHOT_SCHEMA_VERSION:
        _project_implementer_attribution(stream.transitions, snapshot)
        snapshot.schema_version = CURRENT_SNAPSHOT_SCHEMA_VERSION
    identity = resolve_mission_identity(feature_dir)
    snapshot.mission_number = str(identity.mission_number) if identity.mission_number is not None else None
    snapshot.mission_type = identity.mission_type

    retro_snapshot = _reduce_retrospective(raw_events)
    if retro_snapshot.status != "absent":
        snapshot.retrospective = retro_snapshot

    return snapshot


def materialize(feature_dir: Path) -> StatusSnapshot:
    """Read events, reduce a snapshot, and atomically write ``status.json``."""
    snapshot = materialize_snapshot(feature_dir)
    json_str = materialize_to_json(snapshot)

    out_path = feature_dir / SNAPSHOT_FILENAME
    tmp_path = feature_dir / (SNAPSHOT_FILENAME + ".tmp")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not (out_path.exists() and out_path.read_text(encoding="utf-8") == json_str):
        tmp_path.write_text(json_str, encoding="utf-8")
        os.replace(tmp_path, out_path)

    return snapshot
