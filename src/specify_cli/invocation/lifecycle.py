"""Profile-invocation lifecycle store (WP05 / issue #843).

This module manages the local append-only store for paired
`ProfileInvocationRecord` lifecycle entries written by ``spec-kitty next``.

Storage layout (#7003)
----------------------
- One file per record at ``kitty-ops/lifecycle/<ulid>.json``, holding a single
  ``ProfileInvocationRecord`` line (sorted-key JSON, see
  ``record.ProfileInvocationRecord.to_json_line``). No two branches ever write
  the same file, so two Mission PRs never conflict on the lifecycle store.
- The legacy log ``kitty-ops/lifecycle.jsonl`` (one record per line) stays
  readable and is never written again. It is not migrated.
- Append-only: a record file is created once and never rewritten; a second
  ``started`` record for the same ``canonical_action_id`` is its own file.

Read order
----------
:func:`read_lifecycle_records` returns the legacy log's lines in insertion
order first, then the per-record files sorted by (``at`` as UTC, ulid). The
ulid is generated monotonically within one process, so two records with the
same ``at`` keep their write order.

Pairing semantics
-----------------
- For every ``started`` record there should eventually exist exactly one
  paired ``completed`` or ``failed`` record sharing the same
  ``canonical_action_id``.
- A ``started`` without a partner is an *orphan*; the doctor surface lists
  these so mid-cycle agent crashes are observable.
- ``find_orphans`` and ``compute_pairing_rate`` are pure functions over the
  record list. The doctor surface is wired separately.

The contract is documented in
``kitty-specs/release-3-2-0a6-tranche-2-01KQ9MKP/contracts/invocation-lifecycle.md``
and ``data-model.md`` §4.
"""

from __future__ import annotations

from kernel.event_log_append import EventLogAppendError, append_event_log_lines
from kernel.clock import UTC, datetime, now_utc
import json
import threading
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ulid import ULID

from specify_cli.invocation.record import (
    ProfileInvocationPhase,
    ProfileInvocationRecord,
)

#: The legacy shared log: read-only since #7003, kept readable, never migrated.
LIFECYCLE_LOG_RELATIVE_PATH = Path("kitty-ops") / "lifecycle.jsonl"
#: The one-file-per-record directory every new record is written to (#7003).
LIFECYCLE_RECORDS_RELATIVE_DIR = Path("kitty-ops") / "lifecycle"
#: Suffix of a per-record file: ``<ulid>.json``.
LIFECYCLE_RECORD_SUFFIX = ".json"

_ULID_LOCK = threading.Lock()
_last_record_id: ULID | None = None


class LifecycleRecordExistsError(EventLogAppendError):
    """A per-record file already holds content; a record file is never rewritten."""


def lifecycle_log_path(repo_root: Path) -> Path:
    """Return the absolute path of the legacy lifecycle JSONL log under ``repo_root``."""
    return repo_root / LIFECYCLE_LOG_RELATIVE_PATH


def lifecycle_records_dir(repo_root: Path) -> Path:
    """Return the absolute path of the per-record lifecycle directory under ``repo_root``."""
    return repo_root / LIFECYCLE_RECORDS_RELATIVE_DIR


def lifecycle_record_files(repo_root: Path) -> frozenset[Path]:
    """Return every per-record file currently under ``repo_root``'s record directory."""
    directory = lifecycle_records_dir(repo_root)
    if not directory.is_dir():
        return frozenset()
    return frozenset(path for path in directory.glob(f"*{LIFECYCLE_RECORD_SUFFIX}") if path.is_file())


def _new_record_id() -> str:
    """Return a ULID that sorts after every one this process issued before.

    A plain ULID is random within one millisecond, so two records written in
    the same millisecond could sort out of write order. The read order breaks
    an ``at`` tie on the ulid, so it must follow write order.
    """
    global _last_record_id
    with _ULID_LOCK:
        candidate = ULID()
        if _last_record_id is not None and candidate.bytes <= _last_record_id.bytes:
            candidate = ULID.from_int(int(_last_record_id) + 1)
        _last_record_id = candidate
        return str(candidate)


def _refuse_existing_content(existing: bytes) -> None:
    if existing:
        raise LifecycleRecordExistsError("lifecycle record file already exists; a record is never rewritten")


# ---------------------------------------------------------------------------
# Read / write
# ---------------------------------------------------------------------------


def append_lifecycle_record(repo_root: Path, record: ProfileInvocationRecord) -> Path:
    """Write ``record`` to its own ``kitty-ops/lifecycle/<ulid>.json``; return that path.

    Creates the directory if missing. Append-only: the file is new, and a
    name that already holds content refuses (:class:`LifecycleRecordExistsError`)
    with nothing written. The legacy ``lifecycle.jsonl`` is never written.
    """
    directory = lifecycle_records_dir(repo_root)
    path = directory / f"{_new_record_id()}{LIFECYCLE_RECORD_SUFFIX}"
    # interim-locked-append: retires at the #6193 handover (kernel.event_log_append).
    # One family lock on the record directory, so lock files do not grow with records.
    append_event_log_lines(
        path,
        [record.to_json_line()],
        lock_anchor=directory,
        create_parents=True,
        no_follow=True,
        precondition=_refuse_existing_content,
    )
    return path


def read_lifecycle_records(repo_root: Path) -> list[ProfileInvocationRecord]:
    """Return all lifecycle records: legacy lines first, then per-record files.

    The legacy ``lifecycle.jsonl`` lines come in insertion order; the
    per-record files follow, sorted by (``at`` as UTC, ulid). Returns ``[]``
    when neither exists. Skips malformed lines and files rather than raising
    — a corrupt record is preferable as a doctor signal than an aborted CLI
    command.
    """
    return _read_legacy_records(lifecycle_log_path(repo_root)) + _read_record_files(lifecycle_records_dir(repo_root))


def _parse_record_line(line: str) -> ProfileInvocationRecord | None:
    if not line.strip():
        return None
    try:
        return ProfileInvocationRecord.from_dict(json.loads(line))
    except (json.JSONDecodeError, KeyError, ValueError, TypeError, AttributeError):
        # Tolerate corrupt/unknown content — doctor will surface it via the
        # orphan check or other diagnostics rather than crashing the caller.
        return None


def _read_text_or_none(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _read_legacy_records(path: Path) -> list[ProfileInvocationRecord]:
    raw = _read_text_or_none(path) if path.is_file() else None
    if raw is None:
        return []
    parsed = (_parse_record_line(line) for line in raw.splitlines())
    return [record for record in parsed if record is not None]


def _utc_at(record: ProfileInvocationRecord) -> datetime:
    at: datetime = record.at
    return at.replace(tzinfo=UTC) if at.tzinfo is None else at.astimezone(UTC)


def _read_record_files(directory: Path) -> list[ProfileInvocationRecord]:
    if not directory.is_dir():
        return []
    keyed: list[tuple[datetime, str, ProfileInvocationRecord]] = []
    for path in directory.glob(f"*{LIFECYCLE_RECORD_SUFFIX}"):
        raw = _read_text_or_none(path) if path.is_file() else None
        record = _parse_record_line(raw) if raw is not None else None
        if record is not None:
            keyed.append((_utc_at(record), path.stem, record))
    keyed.sort(key=lambda entry: (entry[0], entry[1]))
    return [record for _, _, record in keyed]


# ---------------------------------------------------------------------------
# Pair-matching
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LifecycleGroup:
    """All records sharing one ``(mission_id, canonical_action_id)`` key.

    Records are stored in read order (see :func:`read_lifecycle_records`). The group key includes
    ``mission_id`` so two missions issuing the same ``mission_state::action``
    cannot cross-pair (which would silently mask a real orphan).
    """

    canonical_action_id: str
    mission_id: str
    records: tuple[ProfileInvocationRecord, ...]

    @property
    def started(self) -> tuple[ProfileInvocationRecord, ...]:
        return tuple(r for r in self.records if r.phase == "started")

    @property
    def completions(self) -> tuple[ProfileInvocationRecord, ...]:
        return tuple(r for r in self.records if r.phase in ("completed", "failed"))

    @property
    def is_orphan(self) -> bool:
        """True iff at least one started record is unpaired.

        A group is orphaned when the count of ``started`` records exceeds
        the count of completions. Re-issuing ``started`` for the same id
        therefore cannot silently mask the original orphan.
        """
        return len(self.started) > len(self.completions)


def group_by_action(records: Iterable[ProfileInvocationRecord]) -> list[LifecycleGroup]:
    """Group records by ``(mission_id, canonical_action_id)`` preserving order.

    Mission identity participates in the group key so cross-mission collisions
    on the same ``mission_state::action`` string cannot balance each other.
    """
    buckets: dict[tuple[str, str], list[ProfileInvocationRecord]] = defaultdict(list)
    order: list[tuple[str, str]] = []
    for r in records:
        key = (r.mission_id, r.canonical_action_id)
        if key not in buckets:
            order.append(key)
        buckets[key].append(r)
    return [
        LifecycleGroup(
            canonical_action_id=cid,
            mission_id=mid,
            records=tuple(buckets[(mid, cid)]),
        )
        for (mid, cid) in order
    ]


def find_orphans(
    records: Iterable[ProfileInvocationRecord],
) -> list[LifecycleGroup]:
    """Return groups containing one or more unpaired ``started`` records.

    These are the records the doctor surface flags as mid-cycle losses.
    """
    return [g for g in group_by_action(records) if g.is_orphan]


def find_latest_unpaired_started(
    records: Iterable[ProfileInvocationRecord],
    *,
    agent: str | None = None,
    mission_id: str | None = None,
) -> ProfileInvocationRecord | None:
    """Return the most recent ``started`` record without a paired completion.

    Filters by ``agent`` and ``mission_id`` when provided. The "most recent"
    is the latest ``at``, normalised to UTC. Which ``started`` of a group is
    unpaired follows the read order of :func:`read_lifecycle_records`.
    """
    grouped = group_by_action(records)
    candidates: list[ProfileInvocationRecord] = []
    for group in grouped:
        if not group.is_orphan:
            continue
        # The orphan started is the most-recent started without a partner.
        # Since one extra started can produce multiple unpaired starteds,
        # match each unpaired one independently.
        deficit = len(group.started) - len(group.completions)
        unpaired = list(group.started)[-deficit:]
        candidates.extend(unpaired)

    candidates = [
        r for r in candidates
        if (agent is None or r.agent == agent)
        and (mission_id is None or r.mission_id == mission_id)
    ]
    if not candidates:
        return None
    # Return the latest by ``at`` as UTC (a naive legacy ``at`` mixed with aware
    # ones must not raise); break ties on the canonical id.
    return max(candidates, key=lambda r: (_utc_at(r), r.canonical_action_id))


def compute_pairing_rate(records: Iterable[ProfileInvocationRecord]) -> float:
    """Return the fraction of ``started`` records that have a partner.

    Returns ``1.0`` when there are no started records (vacuously paired).
    Used by the integration test against the NFR-006 95% floor.
    """
    materialised = list(records)
    started = sum(1 for r in materialised if r.phase == "started")
    if started == 0:
        return 1.0
    completions = sum(1 for r in materialised if r.phase in ("completed", "failed"))
    paired = min(started, completions)
    return paired / started


# ---------------------------------------------------------------------------
# Doctor surface helpers
# ---------------------------------------------------------------------------


def doctor_orphan_report(repo_root: Path) -> dict[str, object]:
    """Return a JSON-serialisable orphan report for the doctor surface.

    Shape::

        {
            "orphan_count": int,
            "orphans": [
                {
                    "canonical_action_id": str,
                    "agent": str,
                    "mission_id": str,
                    "wp_id": str | None,
                    "started_at": ISO string,
                }
                ...
            ],
            "total_groups": int,
            "pairing_rate": float in [0.0, 1.0],
        }
    """
    records = read_lifecycle_records(repo_root)
    orphans = find_orphans(records)
    orphan_entries: list[dict[str, object]] = []
    for group in orphans:
        deficit = len(group.started) - len(group.completions)
        for started_record in list(group.started)[-deficit:]:
            orphan_entries.append({
                "canonical_action_id": started_record.canonical_action_id,
                "agent": started_record.agent,
                "mission_id": started_record.mission_id,
                "wp_id": started_record.wp_id,
                "started_at": _format_at(started_record.at),
            })
    return {
        "orphan_count": len(orphan_entries),
        "orphans": orphan_entries,
        "total_groups": len(group_by_action(records)),
        "pairing_rate": compute_pairing_rate(records),
    }


def _format_at(at: datetime) -> str:
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    return at.isoformat()


# ---------------------------------------------------------------------------
# next-cmd wiring helpers (used by cli/commands/next_cmd.py)
# ---------------------------------------------------------------------------


def make_canonical_action_id(mission_step: str, action_name: str) -> str:
    """Build the ``mission_step::action`` id used by ``started`` and its pair.

    Trims surrounding whitespace and rejects empty inputs early — the writers
    must never produce a canonical id with empty halves.
    """
    step = (mission_step or "").strip()
    action = (action_name or "").strip()
    if not step or not action:
        raise ValueError(
            f"canonical_action_id requires non-empty mission_step and action_name, "
            f"got mission_step={mission_step!r} action_name={action_name!r}"
        )
    return f"{step}::{action}"


def write_started(
    repo_root: Path,
    *,
    canonical_action_id: str,
    agent: str,
    mission_id: str,
    wp_id: str | None = None,
    at: datetime | None = None,
) -> ProfileInvocationRecord:
    """Append a ``started`` lifecycle record to the local store.

    Returns the record written (caller may want to log/echo it).
    """
    record = ProfileInvocationRecord(
        canonical_action_id=canonical_action_id,
        phase="started",
        at=at or now_utc(),
        agent=agent,
        mission_id=mission_id,
        wp_id=wp_id,
    )
    append_lifecycle_record(repo_root, record)
    return record


def write_paired_completion(
    repo_root: Path,
    *,
    started: ProfileInvocationRecord,
    phase: ProfileInvocationPhase,
    reason: str | None = None,
    at: datetime | None = None,
) -> ProfileInvocationRecord:
    """Append a ``completed`` or ``failed`` record paired with ``started``.

    Re-uses the started record's ``canonical_action_id`` verbatim — the
    canonical id is read once at issuance and never re-computed at
    completion time (per FR-011 and the contract Always-true rules).
    """
    if phase == "started":
        raise ValueError("write_paired_completion phase must be 'completed' or 'failed'")
    record = ProfileInvocationRecord(
        canonical_action_id=started.canonical_action_id,
        phase=phase,
        at=at or now_utc(),
        agent=started.agent,
        mission_id=started.mission_id,
        wp_id=started.wp_id,
        reason=reason,
    )
    append_lifecycle_record(repo_root, record)
    return record
