"""Pure event-id prefix/fork classification (mission coord-artifact-single-home-01M3V4BE, WP03).

The single, neutral home for the "carry exactly once, refuse a fork" rule
(research D3; data-model.md I-SEED-4). Pure over event-id sequences: no git,
no locking, no filesystem access. Both
:mod:`specify_cli.coordination.coord_seed` (the one-time coordination-surface
seed) and the WP17 fork detector import this module instead of each keeping a
private copy of the classifier (NFR-004 single-authority discipline).
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

__all__ = [
    "DuplicateEventIdError",
    "MalformedEventLogLineError",
    "PrefixVerdict",
    "classify_prefix",
    "event_ids_of",
    "merged_log_bytes",
    "non_blank_lines_of",
]


class MalformedEventLogLineError(ValueError):
    """A JSONL event-log line could not be parsed.

    Raised rather than silently skipped (NFR-002's zero-loss rule): a
    malformed line never quietly disappears from the carried content.
    """

    def __init__(self, *, line_number: int, line: str) -> None:
        self.line_number = line_number
        self.line = line
        super().__init__(f"malformed event-log line {line_number}: {line!r}")


class DuplicateEventIdError(ValueError):
    """The same ``event_id`` appears twice within one event-log stream (NFR-002)."""

    def __init__(self, *, event_id: str) -> None:
        self.event_id = event_id
        super().__init__(f"duplicate event_id within one log stream: {event_id!r}")


def _is_blank_line(line: str) -> bool:
    """Return whether *line* carries no content once whitespace is stripped."""
    return not line.strip()


def non_blank_lines_of(lines: Iterable[str]) -> tuple[str, ...]:
    """Return *lines* with blank entries removed, preserving order and content verbatim.

    Byte-faithful: a kept line is returned exactly as given (no stripping,
    no re-encoding) so a caller can later re-join kept lines without
    re-serializing anything.
    """
    return tuple(line for line in lines if not _is_blank_line(line))


def event_ids_of(lines: Iterable[str]) -> tuple[str, ...]:
    """Parse a JSONL event log's ``event_id`` sequence from *lines*.

    Blank lines are skipped. A malformed line raises
    :class:`MalformedEventLogLineError` rather than being silently dropped. A
    duplicate ``event_id`` within the same sequence raises
    :class:`DuplicateEventIdError` -- never silently de-duplicated.
    """
    ids: list[str] = []
    seen: set[str] = set()
    for line_number, raw_line in enumerate(lines, start=1):
        if _is_blank_line(raw_line):
            continue
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise MalformedEventLogLineError(line_number=line_number, line=raw_line) from exc
        if not isinstance(payload, dict) or "event_id" not in payload:
            raise MalformedEventLogLineError(line_number=line_number, line=raw_line)
        event_id = str(payload["event_id"])
        if event_id in seen:
            raise DuplicateEventIdError(event_id=event_id)
        seen.add(event_id)
        ids.append(event_id)
    return tuple(ids)


@dataclass(frozen=True)
class PrefixVerdict:
    """The outcome of comparing a root and a coordination event-id sequence."""

    kind: Literal["carry_tail", "nothing", "fork"]
    tail_start: int = 0
    first_divergence: tuple[str | None, str | None] = (None, None)


def classify_prefix(root_ids: tuple[str, ...], coord_ids: tuple[str, ...]) -> PrefixVerdict:
    """Classify *root_ids* against *coord_ids* per the carry/fork rule (D3, I-SEED-4).

    - ``coord_ids`` empty, or a proper prefix of ``root_ids``: ``carry_tail``
      starting at ``len(coord_ids)``.
    - ``root_ids`` a prefix of ``coord_ids`` (including equality): ``nothing``
      to carry.
    - Neither is a prefix of the other: ``fork``, naming the first diverging
      pair.
    """
    if root_ids[: len(coord_ids)] == coord_ids:
        if len(coord_ids) >= len(root_ids):
            return PrefixVerdict(kind="nothing")
        return PrefixVerdict(kind="carry_tail", tail_start=len(coord_ids))
    if coord_ids[: len(root_ids)] == root_ids:
        return PrefixVerdict(kind="nothing")
    shortest = min(len(root_ids), len(coord_ids))
    first_index = next((i for i in range(shortest) if root_ids[i] != coord_ids[i]), shortest)
    root_value = root_ids[first_index] if first_index < len(root_ids) else None
    coord_value = coord_ids[first_index] if first_index < len(coord_ids) else None
    return PrefixVerdict(kind="fork", first_divergence=(root_value, coord_value))


def _ensure_trailing_newline(line: str) -> str:
    """Return *line* with exactly one trailing ``\\n`` appended if it lacks one.

    B9: a coordination (or root) file's final kept line commonly lacks a
    trailing newline (a plain editor save, or the last line of a file nobody
    appended to since). Joining two line sequences without normalising that
    glues the next row onto the previous one byte-for-byte
    (``{"event_id":"a"}{"event_id":"b"}\\n``), corrupting the merged JSONL.
    This still never re-serializes a row's own bytes -- it only guarantees
    the line TERMINATOR between rows, which is metadata the JSONL format
    requires, not content.
    """
    return line if line.endswith("\n") else line + "\n"


def merged_log_bytes(
    root_lines: tuple[str, ...],
    coord_lines: tuple[str, ...],
    verdict: PrefixVerdict,
) -> bytes:
    """Compose the merged log content for *verdict*, byte-faithful (never re-serialized).

    ``root_lines`` / ``coord_lines`` must be the SAME blank-filtered sequences
    (:func:`non_blank_lines_of`) that produced the event ids fed to
    :func:`classify_prefix`, so ``verdict.tail_start`` indexes correctly.

    Every kept line gets a trailing ``\\n`` if it does not already have one
    (B9) -- never gluing two rows together when a file's last kept line
    lacks a terminator.
    """
    if verdict.kind == "fork":
        raise ValueError("cannot merge a forked log; raise COORD_SEED_FORK_REFUSED instead")
    kept = coord_lines if verdict.kind == "nothing" else (*coord_lines, *root_lines[verdict.tail_start :])
    return "".join(_ensure_trailing_newline(line) for line in kept).encode("utf-8")
