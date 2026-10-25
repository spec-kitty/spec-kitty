"""Mission archiving — a first-class lifecycle operation (FR-015 / US6 / IC-13).

Archiving turns a *terminal* mission (``merged`` or ``canceled``) into an
immutable, explicitly-legacy :class:`ArchivedMission` snapshot: it is excluded
from live validation but kept **enumerable**, so retiring a mission never hides
unresolved state.

The four ``AM`` guards are the whole point of this surface — an ungoverned
archive would be a one-command escape from any acceptance failure:

* **AM-1 — Terminal only.** Archiving is refused unless the mission is already
  terminal (``merged`` / ``canceled``), and always requires a stated reason.
* **AM-2 — No violation may be filed away.** Archiving is refused while any
  negative invariant is recorded ``still_present`` — a violation is resolved,
  not archived past.
* **AM-3 — Visible, not deleted.** An archived mission drops out of live
  validation (:func:`is_mission_archived`) but stays enumerable
  (:func:`list_archived_missions`), so the debt remains discoverable.
* **AM-4 — Never automatic.** Archiving is operator-invoked only. It is
  unreachable from any lifecycle step, including the FR-014 backfill migration:
  there is no automated caller — ``archived_by`` is a required operator
  identity with no default, and no migration module imports this one.
* **AM-5 — Cancellation clears deferrals; abandonment is not a deadlock.**
  Cancelling a mission resolves its outstanding ``deferred_to_consolidation``
  invariants to a ``canceled`` disposition (they were never going to be judged —
  the mission is abandoned, not completed), so an abandoned mission with a
  dangling deferral is still archivable. Deferrals never block archiving here;
  only ``still_present`` does (AM-2).

The authority boundary: this module *reads* the canonical status snapshot and
acceptance matrix and *appends* to an immutable registry. It never re-implements
status reduction or matrix parsing, and never mutates mission state.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from kernel.event_log_append import append_event_log_lines
from kernel.clock import now_utc_iso
from pathlib import Path
from typing import Any

from specify_cli.acceptance.matrix import (
    DEFERRED_TO_CONSOLIDATION,
    read_acceptance_matrix,
)
from specify_cli.mission_metadata import resolve_mission_identity
from specify_cli.status import materialize_snapshot

# --- Terminal-state vocabulary (data-model.md ArchivedMission) -------------
# The two terminal states that make archiving permissible. ``merged`` is
# terminal-by-completion; ``canceled`` is terminal-by-abandonment.
MERGED = "merged"
CANCELED = "canceled"
TERMINAL_STATES = frozenset({MERGED, CANCELED})

# The invariant Result that blocks archiving (AM-2). This is the canonical
# matrix Result string (see ``acceptance.matrix.TERMINAL_INVARIANT_RESULTS``);
# a rename there is caught by the ``still_present``-refused scenario test rather
# than a load-time assert.
STILL_PRESENT = "still_present"

# The disposition an outstanding deferral is resolved to when a mission is
# cancelled (AM-5). It is NOT a matrix Result value — it is the archive-time
# record that the deferral was abandoned rather than judged.
CANCELED_DISPOSITION = "canceled"

# The append-only, immutable archive registry. One JSON object per line keeps
# every ArchivedMission an explicitly-legacy snapshot (AM-3): records are only
# ever appended and read, never rewritten.
ARCHIVE_REGISTRY_RELPATH = Path(".kittify") / "archive" / "archived-missions.jsonl"


class MissionArchiveRefused(Exception):
    """An archive attempt was refused by one of the ``AM`` guards.

    Carries the guard ``code`` (e.g. ``"AM-1"``) and a stated ``reason`` so the
    CLI can surface *why* without re-deriving it.
    """

    def __init__(self, code: str, reason: str) -> None:
        self.code = code
        self.reason = reason
        super().__init__(f"{code}: {reason}")


@dataclass(frozen=True)
class ArchivedMission:
    """The immutable record produced when an operator archives a mission.

    Mirrors data-model.md ``ArchivedMission`` (AM fields).
    """

    mission_id: str
    archived_by: str
    archived_at: str
    reason: str
    terminal_state_at_archive: str  # ``merged`` | ``canceled``

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ArchivedMission:
        return cls(
            mission_id=str(data["mission_id"]),
            archived_by=str(data["archived_by"]),
            archived_at=str(data["archived_at"]),
            reason=str(data["reason"]),
            terminal_state_at_archive=str(data["terminal_state_at_archive"]),
        )


@dataclass(frozen=True)
class ArchiveEligibility:
    """The pure verdict of the AM-1/AM-2 guards, independent of any I/O."""

    eligible: bool
    refusal_code: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class DeferralDisposition:
    """AM-5: an outstanding deferral resolved by cancellation."""

    invariant_id: str
    disposition: str  # always ``CANCELED_DISPOSITION`` here


def _utc_now_iso() -> str:
    return now_utc_iso()


# ---------------------------------------------------------------------------
# Pure guards (no filesystem / git) — the testable heart of the operation
# ---------------------------------------------------------------------------


def evaluate_archive_eligibility(
    *,
    terminal_state: str | None,
    invariant_results: Iterable[str],
    reason: str,
) -> ArchiveEligibility:
    """Decide whether an archive is permitted, per AM-1 and AM-2.

    Pure and filesystem-free so the guard logic is exercised directly rather
    than through a mission fixture.

    * **AM-1**: a stated ``reason`` is required and the mission must be terminal
      (``merged`` / ``canceled``). A non-terminal mission cannot be archived.
    * **AM-2**: refused while any invariant is ``still_present``.

    A ``deferred_to_consolidation`` invariant is deliberately NOT a blocker
    (AM-5): a cancelled mission with a dangling deferral is archivable.
    """
    if not reason or not reason.strip():
        return ArchiveEligibility(
            eligible=False,
            refusal_code="AM-1",
            reason="a stated reason is required to archive a mission",
        )
    if terminal_state not in TERMINAL_STATES:
        return ArchiveEligibility(
            eligible=False,
            refusal_code="AM-1",
            reason=(
                "mission is not terminal (must be merged or canceled); "
                f"resolved terminal state: {terminal_state!r}"
            ),
        )
    if any(result == STILL_PRESENT for result in invariant_results):
        return ArchiveEligibility(
            eligible=False,
            refusal_code="AM-2",
            reason=(
                "a still_present invariant must be resolved, not archived past"
            ),
        )
    return ArchiveEligibility(eligible=True)


def resolve_deferrals_for_cancellation(
    invariants: Iterable[tuple[str, str]],
    *,
    terminal_state: str | None,
) -> list[DeferralDisposition]:
    """AM-5: map outstanding deferrals to a ``canceled`` disposition.

    Only cancellation clears deferrals — a ``merged`` mission's deferrals are
    left untouched (NI-5 already prevented ``done`` while one was live). Each
    element of ``invariants`` is an ``(invariant_id, result)`` pair.
    """
    if terminal_state != CANCELED:
        return []
    return [
        DeferralDisposition(invariant_id=inv_id, disposition=CANCELED_DISPOSITION)
        for inv_id, result in invariants
        if result == DEFERRED_TO_CONSOLIDATION
    ]


# ---------------------------------------------------------------------------
# Canonical state readers (delegate to the status snapshot + matrix)
# ---------------------------------------------------------------------------


def resolve_terminal_state(feature_dir: Path) -> str | None:
    """Resolve a mission's terminal state from the canonical status snapshot.

    * every WP ``done`` → ``merged`` (terminal-by-completion)
    * every WP terminal with at least one ``canceled`` → ``canceled``
      (terminal-by-abandonment)
    * any WP in a non-terminal lane, or no WPs at all → ``None`` (not terminal)
    """
    snapshot = materialize_snapshot(feature_dir)
    lanes = [str(wp.get("lane", "")) for wp in snapshot.work_packages.values()]
    if not lanes:
        return None
    if all(lane == "done" for lane in lanes):
        return MERGED
    if all(lane in {"done", "canceled"} for lane in lanes) and any(
        lane == "canceled" for lane in lanes
    ):
        return CANCELED
    return None


def read_invariants(feature_dir: Path) -> list[tuple[str, str]]:
    """Return ``(invariant_id, result)`` pairs from the acceptance matrix."""
    matrix = read_acceptance_matrix(feature_dir)
    if matrix is None:
        return []
    return [(ni.invariant_id, ni.result) for ni in matrix.negative_invariants]


# ---------------------------------------------------------------------------
# Immutable registry (append-only) — AM-3 enumerability
# ---------------------------------------------------------------------------


def archive_registry_path(project_root: Path) -> Path:
    """Path to the append-only archived-missions registry."""
    return project_root / ARCHIVE_REGISTRY_RELPATH


def append_archive_record(project_root: Path, record: ArchivedMission) -> Path:
    """Append one immutable ArchivedMission record to the registry."""
    path = archive_registry_path(project_root)
    # interim-locked-append: retires at the #6193 handover (kernel.event_log_append).
    append_event_log_lines(path, [json.dumps(record.to_dict(), sort_keys=True)], create_parents=True)
    return path


def list_archived_missions(project_root: Path) -> list[ArchivedMission]:
    """Enumerate archived missions (AM-3 — visible, not deleted).

    Malformed lines are skipped rather than crashing enumeration, so one bad
    record never hides the rest of the debt from the operator.
    """
    path = archive_registry_path(project_root)
    if not path.exists():
        return []
    records: list[ArchivedMission] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            records.append(ArchivedMission.from_dict(json.loads(stripped)))
        except (json.JSONDecodeError, KeyError):
            continue
    return records


def is_mission_archived(project_root: Path, mission_id: str) -> bool:
    """True when ``mission_id`` has an archive record (excluded from live validation)."""
    return any(
        record.mission_id == mission_id
        for record in list_archived_missions(project_root)
    )


# ---------------------------------------------------------------------------
# Operator entry point
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ArchiveOutcome:
    """The result of a successful archive: the record + AM-5 dispositions."""

    record: ArchivedMission
    cleared_deferrals: list[DeferralDisposition]


def archive_mission(
    *,
    project_root: Path,
    feature_dir: Path,
    archived_by: str,
    reason: str,
    now: str | None = None,
    terminal_state_resolver: Callable[[Path], str | None] = resolve_terminal_state,
    invariants_reader: Callable[[Path], list[tuple[str, str]]] = read_invariants,
) -> ArchiveOutcome:
    """Archive a mission, enforcing AM-1..AM-5.

    ``archived_by`` is a required operator identity — there is no default, so no
    automated lifecycle step can archive anonymously (AM-4). The state readers
    are injectable purely for testing; production always resolves through the
    canonical status snapshot and acceptance matrix.

    Raises:
        MissionArchiveRefused: when AM-1 or AM-2 blocks the archive.
    """
    if not archived_by or not archived_by.strip():
        # AM-4 backstop: an archive must name a human operator.
        raise MissionArchiveRefused(
            "AM-4", "archiving requires an operator identity (--by)"
        )

    terminal_state = terminal_state_resolver(feature_dir)
    invariants = invariants_reader(feature_dir)

    eligibility = evaluate_archive_eligibility(
        terminal_state=terminal_state,
        invariant_results=[result for _inv_id, result in invariants],
        reason=reason,
    )
    if not eligibility.eligible:
        # A non-eligible verdict always carries both a code and a stated reason;
        # the ``or`` fallbacks keep the type total without a narrowing assert.
        raise MissionArchiveRefused(
            eligibility.refusal_code or "AM-1",
            eligibility.reason or "archive refused",
        )

    cleared = resolve_deferrals_for_cancellation(
        invariants, terminal_state=terminal_state
    )

    identity = resolve_mission_identity(feature_dir)
    mission_id = identity.mission_id or identity.mission_slug
    record = ArchivedMission(
        mission_id=mission_id,
        archived_by=archived_by.strip(),
        archived_at=now or _utc_now_iso(),
        reason=reason.strip(),
        # ``terminal_state`` is guaranteed non-None here by the AM-1 guard.
        terminal_state_at_archive=str(terminal_state),
    )
    append_archive_record(project_root, record)
    return ArchiveOutcome(record=record, cleared_deferrals=cleared)
