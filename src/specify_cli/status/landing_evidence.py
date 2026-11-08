"""Terminal-WP landing evidence for a Mission without ``merged_at`` (#7433, ADR ``2026-11-06-2``).

The one "has this Mission landed" signal is the reopen-aware ``merged_at`` marker
(:func:`mission_runtime.mission_has_landed`). A Mission that landed before consolidation wrote it
(#4090) has none. This module answers, from the committed status log only, whether such a
Mission's log shows a landing; the ``merged_at`` backfill and the ``COORDINATION_BRANCH_DELETED``
remedy both ask it, so the rule exists once (operator ruling 2026-11-08):

* **Holds** when every work package in the log is terminal (``done`` or ``canceled``), at least
  one is ``done``, and the log records no ``MissionReopened`` event.
* **Date** is the ``at`` of the latest transition to ``done`` in that log, as an aware-UTC
  ISO-8601 string (naive stamps are read as UTC).

``mission_number`` is not evidence: ``doctor mission-state --fix`` assigns it to Missions that
never landed (#5471). Nothing here reads git history.

The log is read through the status read door (:func:`~specify_cli.status.read_surface.
resolve_landing_evidence_read`): the coordination surface when it still exists, the write checkout
for a coordination-less Mission, and the target's copy once the coordination branch is gone.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from kernel.clock import UTC, parse_iso

if TYPE_CHECKING:
    from specify_cli.status.models import StatusEvent
    from specify_cli.status.read_surface import StatusReadSurface

__all__ = [
    "LandingEvidence",
    "LandingVerdict",
    "landing_evidence_at_target",
    "landing_evidence_from_surface",
    "read_landing_evidence",
]

_DONE = "done"
_TERMINAL_LANES = frozenset({_DONE, "canceled"})


class LandingVerdict(StrEnum):
    """Why a Mission's committed status log does or does not show a landing."""

    LANDED = "landed"
    REOPENED = "reopened"
    NO_STATUS_LOG = "no_status_log"
    NO_WORK_PACKAGES = "no_work_packages"
    UNFINISHED = "unfinished"
    NO_DONE = "no_done"
    NO_DONE_DATE = "no_done_date"
    UNREADABLE = "unreadable"


_REASONS: Mapping[LandingVerdict, str] = {
    LandingVerdict.LANDED: "every work package is done or canceled, at least one is done, and the Mission was never reopened",
    LandingVerdict.REOPENED: "a MissionReopened event is recorded",
    LandingVerdict.NO_STATUS_LOG: "the Mission has no status log",
    LandingVerdict.NO_WORK_PACKAGES: "the status log records no work package",
    LandingVerdict.UNFINISHED: "not every work package is done or canceled",
    LandingVerdict.NO_DONE: "no work package is done (all canceled)",
    LandingVerdict.NO_DONE_DATE: "no transition to done carries a readable timestamp",
    LandingVerdict.UNREADABLE: "the status log cannot be read",
}


@dataclass(frozen=True)
class LandingEvidence:
    """The verdict on one Mission's committed status log.

    ``merged_at`` is set only when the verdict is ``LANDED``; ``detail`` names what was seen
    (the unfinished work packages, or the read error).
    """

    verdict: LandingVerdict
    merged_at: str | None = None
    detail: str = ""

    @property
    def holds(self) -> bool:
        return self.verdict is LandingVerdict.LANDED

    @property
    def summary(self) -> str:
        """The verdict in words, without the per-Mission detail."""
        return _REASONS[self.verdict]

    @property
    def reason(self) -> str:
        """The verdict in words, with the per-Mission detail when there is one."""
        return f"{self.summary} ({self.detail})" if self.detail else self.summary


def _aware_utc_iso(raw: str) -> str | None:
    """*raw* as an aware-UTC ISO-8601 string (naive read as UTC), or ``None`` when unparseable."""
    try:
        parsed = parse_iso(raw)
    except (TypeError, ValueError):
        return None
    aware = parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    return aware.isoformat()


def _latest_at(events: Iterable[StatusEvent]) -> str | None:
    stamps = (_aware_utc_iso(str(event.at)) for event in events)
    parsed = [stamp for stamp in stamps if stamp is not None]
    return max(parsed, key=parse_iso) if parsed else None


def _latest_done_at(transitions: Iterable[StatusEvent]) -> str | None:
    """The latest ``done`` ``at``, preferring events a person or the tool wrote over migration seeds.

    A migration-synthesized ``done`` (e.g. ``migration:backfill_wp_status``, #5579) restates
    history at roughly the Mission's creation time, not its landing, so it supplies the date
    only when no other ``done`` event exists (operator ruling, 2026-11-08).
    """
    from specify_cli.status.models import is_migration_actor

    done = [event for event in transitions if str(event.to_lane) == _DONE]
    real = [event for event in done if not is_migration_actor(event.actor)]
    return _latest_at(real) or _latest_at(done)


def _unfinished(work_packages: Mapping[str, Any]) -> list[str]:
    lanes = {wp_id: str(state.get("lane", "")) if isinstance(state, Mapping) else "" for wp_id, state in work_packages.items()}
    return [f"{wp_id} {lane or 'unknown'}" for wp_id, lane in sorted(lanes.items()) if lane not in _TERMINAL_LANES]


def _has_done(work_packages: Mapping[str, Any]) -> bool:
    return any(isinstance(state, Mapping) and str(state.get("lane", "")) == _DONE for state in work_packages.values())


def _is_reopened(text: str) -> bool:
    from specify_cli.status.lifecycle_events import MISSION_REOPENED, lifecycle_events_from_text

    return any(event.get("event_type") == MISSION_REOPENED for event in lifecycle_events_from_text(text))


def _evidence_from_text(parser_dir: Path, text: str | None) -> LandingEvidence:
    from specify_cli.status.reducer import reduce
    from specify_cli.status.store import read_event_stream_from_text

    if text is None or not text.strip():
        return LandingEvidence(LandingVerdict.NO_STATUS_LOG)
    if _is_reopened(text):
        return LandingEvidence(LandingVerdict.REOPENED)
    stream = read_event_stream_from_text(parser_dir, text)
    work_packages = reduce(stream.transitions, stream.annotations).work_packages
    if not work_packages:
        return LandingEvidence(LandingVerdict.NO_WORK_PACKAGES)
    unfinished = _unfinished(work_packages)
    if unfinished:
        return LandingEvidence(LandingVerdict.UNFINISHED, detail=", ".join(unfinished))
    if not _has_done(work_packages):
        return LandingEvidence(LandingVerdict.NO_DONE)
    merged_at = _latest_done_at(stream.transitions)
    if merged_at is None:
        return LandingEvidence(LandingVerdict.NO_DONE_DATE)
    return LandingEvidence(LandingVerdict.LANDED, merged_at=merged_at)


def _read_errors() -> tuple[type[BaseException], ...]:
    """The failures that mean "this log cannot be read", never "this Mission landed"."""
    from specify_cli.coordination.status_service import StatusSurfaceRefUnreadable
    from specify_cli.coordination.surface_resolver import WorktreeRegistryUnavailable
    from specify_cli.core.paths import MissionMetaReadError
    from specify_cli.missions._read_path_resolver import StatusReadPathNotFound
    from specify_cli.status.store import StoreError

    return (StatusSurfaceRefUnreadable, WorktreeRegistryUnavailable, MissionMetaReadError, StatusReadPathNotFound, StoreError, OSError, ValueError)


def landing_evidence_from_surface(surface: StatusReadSurface) -> LandingEvidence:
    """The verdict on the log at *surface* (raises the door's read errors)."""
    from specify_cli.status.read_surface import read_status_text

    return _evidence_from_text(surface.parser_dir, read_status_text(surface))


def read_landing_evidence(repo_root: Path, mission: str) -> LandingEvidence:
    """The verdict on *mission*'s committed status log, read through the door. Never raises a read error.

    A log that cannot be read (unreadable ref, corrupt line, unknown Mission) is
    ``UNREADABLE`` with the error as ``detail``: it is never evidence of a landing.
    """
    from specify_cli.status.read_surface import resolve_landing_evidence_read

    try:
        return landing_evidence_from_surface(resolve_landing_evidence_read(repo_root, mission))
    except _read_errors() as exc:
        return LandingEvidence(LandingVerdict.UNREADABLE, detail=str(exc))


def landing_evidence_at_target(repo_root: Path, primary_dir: Path) -> LandingEvidence:
    """The verdict on the target's copy of the log (the door refused: the coordination branch is gone).

    For the ``COORDINATION_BRANCH_DELETED`` remedy, which cannot re-enter the door that is raising
    it. Same source :func:`read_landing_evidence` falls back to, so both callers judge one log.
    Never raises a read error.
    """
    from specify_cli.status.read_surface import resolve_consolidated_target_read

    try:
        return landing_evidence_from_surface(resolve_consolidated_target_read(repo_root, primary_dir))
    except _read_errors() as exc:
        return LandingEvidence(LandingVerdict.UNREADABLE, detail=str(exc))
