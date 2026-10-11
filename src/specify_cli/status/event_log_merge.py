"""Helpers for semantically merging append-only status event logs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import Lane, NON_DISPLAY_LANES


class EventLogMergeError(Exception):
    """Raised when an event-log merge cannot be completed safely."""


# The linear lifecycle lanes in forward order (``planned``..``done``), used to
# tell a backward (rejection/revert) move from forward progress. ``blocked`` and
# ``canceled`` are non-linear and carry no forward rank; the two non-display
# sentinels (``genesis``/``uninitialized``) never appear on a transition edge.
_NON_LINEAR_LANES: frozenset[Lane] = NON_DISPLAY_LANES | {Lane.BLOCKED, Lane.CANCELED}
_FORWARD_RANK: dict[str, int] = {
    lane.value: rank
    for rank, lane in enumerate(lane for lane in Lane if lane not in _NON_LINEAR_LANES)
}


def _is_decision_destination(from_lane: str, to_lane: str) -> bool:
    """Whether a departure encodes a human stop/undo a silent LWW fold must not bury.

    True for a cancellation (``to_lane == 'canceled'``) or a backward move in the
    linear lifecycle (a rejection/revert, e.g. ``in_review -> planned``). A purely
    forward fork (e.g. ``planned -> in_progress`` against ``planned ->
    for_review``) carries no such decision: the union keeps both event rows and
    the reducer picks one, the clean-merge behaviour #5759 relies on. A move whose
    endpoint is non-linear (``blocked``) is not itself a reject/revert.
    """
    if to_lane == Lane.CANCELED.value:
        return True
    src = _FORWARD_RANK.get(from_lane)
    dst = _FORWARD_RANK.get(to_lane)
    if src is None or dst is None:
        return False
    return dst < src


def read_event_log_text(text: str, *, source: str = "<memory>") -> list[dict[str, Any]]:
    """Read status.events.jsonl-style content from an in-memory string."""
    events: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise EventLogMergeError(
                f"{source}: invalid JSON on line {line_number}: {exc}"
            ) from exc
        if not isinstance(payload, dict):
            raise EventLogMergeError(
                f"{source}: line {line_number} is not a JSON object"
            )
        event_id = payload.get("event_id")
        if not isinstance(event_id, str) or not event_id.strip():
            raise EventLogMergeError(
                f"{source}: line {line_number} is missing a valid event_id"
            )
        # Non-status event types (e.g. tracker events) may lack 'at' or
        # 'timestamp'; accept them and sort them first via empty-string key.
        events.append(payload)
    return events


def _read_event_file(path: Path) -> list[dict[str, Any]]:
    """Read a status.events.jsonl-style file from an arbitrary path."""
    if not path.exists():
        return []
    return read_event_log_text(path.read_text(encoding="utf-8"), source=str(path))


def detect_concurrent_fork(
    base_events: list[dict[str, Any]],
    ours_events: list[dict[str, Any]],
    theirs_events: list[dict[str, Any]],
) -> str | None:
    """Return a conflict description when ours and theirs diverge concurrently (#5967).

    The union merge driver cannot safely fold two teammates' logs when both
    sides, from the SAME lane for the SAME work package, independently
    transitioned it to DIFFERENT lanes — e.g. one clone's ``in_progress ->
    canceled`` against another's stale ``in_progress -> for_review``, or one
    reviewer's ``in_review -> planned`` rejection against another's stale
    ``in_review -> approved``. The wall-clock LWW reducer would silently apply
    whichever row sorts last and bury the other, landing descoped or rejected
    work at exit 0.

    A fork is reported only when BOTH sides carry a non-base ("extra")
    transition departing the same ``from_lane`` to more than one distinct
    ``to_lane`` AND at least one of those destinations is a *decision* a silent
    fold must not bury -- a cancellation or a backward (rejection/revert) move
    (see ``_is_decision_destination``). A purely forward fork (both sides
    advancing the same WP to different downstream lanes, e.g. ``planned ->
    in_progress`` against ``planned -> for_review``) is NOT reported: the union
    keeps both rows and the reducer picks one, the clean-merge guarantee #5759
    relies on. A one-sided extension, the same decision on both sides, and
    concurrent work on DIFFERENT work packages are likewise not forks. Reported,
    not resolved: the caller fails the merge so git leaves a conflict for a human
    (the safe pre-#5759 behaviour). Returns ``None`` when there is no such fork.
    """
    base_ids = {event.get("event_id") for event in base_events}

    def _departures(events: list[dict[str, Any]]) -> dict[str, dict[str, set[str]]]:
        by_wp: dict[str, dict[str, set[str]]] = {}
        for event in events:
            if event.get("event_id") in base_ids:
                continue  # shared history, never a concurrent departure
            from_lane = event.get("from_lane")
            to_lane = event.get("to_lane")
            wp_id = event.get("wp_id")
            if not from_lane or not to_lane or not wp_id:
                continue  # annotations / non-transition rows carry no lane edge
            by_wp.setdefault(str(wp_id), {}).setdefault(str(from_lane), set()).add(str(to_lane))
        return by_wp

    ours = _departures(ours_events)
    theirs = _departures(theirs_events)
    for wp_id in sorted(ours.keys() & theirs.keys()):
        for from_lane in sorted(ours[wp_id].keys() & theirs[wp_id].keys()):
            destinations = ours[wp_id][from_lane] | theirs[wp_id][from_lane]
            if len(destinations) > 1 and any(
                _is_decision_destination(from_lane, destination) for destination in destinations
            ):
                return (
                    f"work package {wp_id}: concurrent transitions from "
                    f"'{from_lane}' to {sorted(destinations)} were made in two "
                    "clones without a pull between them; a union merge would "
                    "silently drop one. Pull, reconcile the divergence by hand "
                    "(keep the cancel/rejection, redo the other), then re-run."
                )
    return None


def merge_event_payloads(*event_groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Union event payloads, dedupe by event_id, sort by timestamp."""
    merged: dict[str, dict[str, Any]] = {}
    for group in event_groups:
        for event in group:
            event_id = event["event_id"]
            existing = merged.get(event_id)
            if existing is not None and existing != event:
                raise EventLogMergeError(
                    f"Conflicting payloads found for event_id {event_id!r}"
                )
            merged[event_id] = event

    return sorted(
        merged.values(),
        key=lambda payload: (
            str(payload.get("at") or payload.get("timestamp", "")),
            str(payload["event_id"]),
        ),
    )


def merge_event_log_texts(*texts: str) -> str:
    """Union JSONL event-log texts and serialize deterministic JSONL."""
    merged = merge_event_payloads(
        *[
            read_event_log_text(text, source=f"<merge-stage-{idx}>")
            for idx, text in enumerate(texts, start=1)
        ]
    )
    return "".join(json.dumps(event, sort_keys=True) + "\n" for event in merged)


def merge_event_log_files(
    *,
    base_path: Path,
    ours_path: Path,
    theirs_path: Path,
    output_path: Path | None = None,
) -> None:
    """Merge three event logs into ``output_path`` (defaults to ``ours_path``)."""
    merged = merge_event_payloads(
        _read_event_file(base_path),
        _read_event_file(ours_path),
        _read_event_file(theirs_path),
    )
    target = output_path or ours_path
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        for event in merged:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
