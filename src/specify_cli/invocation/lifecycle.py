"""Profile-invocation lifecycle store (WP05 / issue #843).

This module manages the local append-only store for paired
`ProfileInvocationRecord` lifecycle entries written by ``spec-kitty next``.

Storage layout
--------------
- One JSONL file at ``kitty-ops/lifecycle.jsonl``.
- Each line is a single ``ProfileInvocationRecord`` (sorted-key JSON, see
  ``record.ProfileInvocationRecord.to_json_line``).
- Append-only — a second ``started`` record for the same
  ``canonical_action_id`` is preserved as its own line; nothing is silently
  overwritten.

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

from kernel.event_log_append import append_event_log_lines
from kernel.clock import UTC, datetime, now_utc
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from specify_cli.invocation.record import (
    ProfileInvocationPhase,
    ProfileInvocationRecord,
)

LIFECYCLE_LOG_RELATIVE_PATH = Path("kitty-ops") / "lifecycle.jsonl"


def lifecycle_log_path(repo_root: Path) -> Path:
    """Return the absolute path of the lifecycle JSONL log under ``repo_root``."""
    return repo_root / LIFECYCLE_LOG_RELATIVE_PATH


# ---------------------------------------------------------------------------
# Read / write
# ---------------------------------------------------------------------------


def append_lifecycle_record(repo_root: Path, record: ProfileInvocationRecord) -> Path:
    """Append a record to the lifecycle log; return the path written.

    Creates the parent directory if missing. Append-only: never rewrites or
    removes an existing line.
    """
    path = lifecycle_log_path(repo_root)
    # interim-locked-append: retires at the #6193 handover (kernel.event_log_append).
    append_event_log_lines(path, [record.to_json_line()], create_parents=True)
    return path


def read_lifecycle_records(repo_root: Path) -> list[ProfileInvocationRecord]:
    """Return all lifecycle records in chronological (insertion) order.

    Returns ``[]`` when the log does not exist. Skips malformed lines rather
    than raising — a corrupt line is preferable as a doctor signal than an
    aborted CLI command.
    """
    path = lifecycle_log_path(repo_root)
    if not path.exists():
        return []
    out: list[ProfileInvocationRecord] = []
    raw = path.read_text(encoding="utf-8")
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            data = json.loads(line)
            out.append(ProfileInvocationRecord.from_dict(data))
        except (json.JSONDecodeError, KeyError, ValueError):
            # Tolerate corrupt/unknown lines — doctor will surface them via
            # the orphan check or other diagnostics rather than crashing the
            # caller mid-issue.
            continue
    return out


# ---------------------------------------------------------------------------
# Pair-matching
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LifecycleGroup:
    """All records sharing one ``(mission_id, canonical_action_id)`` key.

    Records are stored in insertion order. The group key includes
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
    is determined by insertion order (the lifecycle log is append-only and
    monotonic in wall-clock time within a single process).
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
    # Return the latest by ``at``; fall back to insertion order on ties.
    return max(candidates, key=lambda r: (r.at, r.canonical_action_id))


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
