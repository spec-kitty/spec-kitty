"""Canonical mission lifecycle derivation for local and Teamspace-facing surfaces.

This module intentionally sits above the WP lane model.  It translates
authoritative mission status snapshots into a small set of product-facing
states that can be shared by CLI UX, migrations, and downstream consumers.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kernel.clock import UTC, Clock, DEFAULT_CLOCK, datetime, from_epoch, parse_iso, timedelta
from specify_cli.mission_metadata import resolve_mission_identity
from specify_cli.status.lifecycle_events import (
    FOLLOW_UP_RECORDED,
    LOCAL_ONLY_LIFECYCLE_EVENT_TYPES,
    MISSION_REOPENED,
    mission_event_log_path,
    read_lifecycle_events,
)
from specify_cli.status.models import NON_DISPLAY_LANES, Lane, StatusSnapshot
from specify_cli.status.progress import compute_weighted_progress
from specify_cli.status.store import EVENTS_FILENAME, read_events
from specify_cli.status.wp_state import wp_state_for

DERIVED_LIFECYCLE_FILENAME = "lifecycle.json"

MISSION_RECENT_COMPLETION_WINDOW_DAYS = 3
MISSION_STALE_THRESHOLD_DAYS = 14
MISSION_ABANDONED_THRESHOLD_DAYS = 30

_ACTIVE_LANES = frozenset(
    {
        Lane.CLAIMED,
        Lane.IN_PROGRESS,
        Lane.FOR_REVIEW,
        Lane.IN_REVIEW,
        Lane.APPROVED,
        Lane.BLOCKED,
    }
)


@dataclass(frozen=True)
class MissionLifecycleResult:
    """Derived mission lifecycle state for machine-facing surfaces."""

    mission_slug: str
    mission_number: int | None
    mission_type: str | None
    state: str
    surface_state: str | None
    reason: str
    last_activity_at: datetime | None
    last_transition_at: datetime | None
    age_days: int | None
    completion_pct: float
    event_count: int
    total_wps: int
    active_wp_count: int
    blocked_wp_count: int
    review_wp_count: int
    terminal_wp_count: int
    has_event_log: bool
    # Canonical mission identity (#2331). Surfaced in ``lifecycle.json`` so the
    # derived view carries the ULID, not only the slug — letting a consumer (e.g.
    # the dashboard registry) re-link a mission to its canonical id from a
    # materialized view. ``None`` only for pre-3.1.1 missions without a mission_id.
    mission_id: str | None = None
    # Post-mission lifecycle facts (WP01 / FR-002). ``post_mission_events`` holds
    # the ``MissionReopened`` + ``FollowUpRecorded`` envelopes sorted by
    # ``(timestamp, event_id)`` so ``lifecycle.json`` stays byte-stable; rendered
    # by ``status/views.py`` (WP02). ``last_follow_up_at`` is the timestamp of the
    # most recent ``FollowUpRecorded`` event (None when there are none).
    post_mission_events: tuple[dict[str, Any], ...] = ()
    last_follow_up_at: datetime | None = None
    stale_after_days: int = MISSION_STALE_THRESHOLD_DAYS
    abandoned_after_days: int = MISSION_ABANDONED_THRESHOLD_DAYS

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission_slug": self.mission_slug,
            "mission_id": self.mission_id,
            "mission_number": self.mission_number,
            "mission_type": self.mission_type,
            "state": self.state,
            "surface_state": self.surface_state,
            "reason": self.reason,
            "last_activity_at": self.last_activity_at.isoformat() if self.last_activity_at else None,
            "last_transition_at": self.last_transition_at.isoformat() if self.last_transition_at else None,
            "age_days": self.age_days,
            "completion_pct": round(self.completion_pct, 1),
            "event_count": self.event_count,
            "total_wps": self.total_wps,
            "active_wp_count": self.active_wp_count,
            "blocked_wp_count": self.blocked_wp_count,
            "review_wp_count": self.review_wp_count,
            "terminal_wp_count": self.terminal_wp_count,
            "has_event_log": self.has_event_log,
            "post_mission_events": list(self.post_mission_events),
            "last_follow_up_at": self.last_follow_up_at.isoformat() if self.last_follow_up_at else None,
            "stale_after_days": self.stale_after_days,
            "abandoned_after_days": self.abandoned_after_days,
        }


def _empty_snapshot(mission_slug: str, mission_number: int | None, mission_type: str | None) -> StatusSnapshot:
    # Fifth display-filter site (squad-found, #2675): previously built with NO
    # filter at all, so it leaked "genesis": 0 today and would leak
    # "uninitialized": 0 once that member exists. Route through the single
    # NON_DISPLAY_LANES authority like every other summary builder.
    return StatusSnapshot(
        mission_slug=mission_slug,
        materialized_at="",
        event_count=0,
        last_event_id=None,
        work_packages={},
        summary={lane.value: 0 for lane in Lane if lane not in NON_DISPLAY_LANES},
        mission_number=str(mission_number) if mission_number is not None else None,
        mission_type=mission_type,
    )


def _parse_dt(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parsed = parse_iso(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _fallback_created_at(feature_dir: Path) -> datetime | None:
    from specify_cli.core.paths import load_meta_fail_closed

    meta = load_meta_fail_closed(feature_dir) or {}
    created_at = _parse_dt(meta.get("created_at"))
    if created_at is not None:
        return created_at

    try:
        return from_epoch(feature_dir.stat().st_mtime)
    except OSError:
        return None


def _derive_last_transition_at(snapshot: StatusSnapshot) -> datetime | None:
    candidates = [_parse_dt(wp_state.get("last_transition_at")) for wp_state in snapshot.work_packages.values() if isinstance(wp_state, dict)]
    filtered = [candidate for candidate in candidates if candidate is not None]
    if filtered:
        return max(filtered)
    return _parse_dt(snapshot.materialized_at)


# Post-mission events (reopen / follow-up) ARE the local-only lifecycle set by
# design; alias the single public owner rather than re-declaring the membership.
_POST_MISSION_EVENT_TYPES = LOCAL_ONLY_LIFECYCLE_EVENT_TYPES


def _event_sort_key(event: dict[str, Any]) -> tuple[str, str]:
    """Stable ordering key ``(timestamp, event_id)`` for post-mission events.

    Sorting on these fields (rather than file order) keeps ``lifecycle.json``
    byte-stable regardless of read order (research.md R-A2).
    """
    timestamp = event.get("timestamp")
    event_id = event.get("event_id")
    return (
        timestamp if isinstance(timestamp, str) else "",
        event_id if isinstance(event_id, str) else "",
    )


def _collect_post_mission_events(feature_dir: Path) -> tuple[dict[str, Any], ...]:
    """Return ``MissionReopened`` + ``FollowUpRecorded`` events, deterministically sorted."""
    log_path = mission_event_log_path(feature_dir)
    if not log_path.exists():
        return ()
    relevant = [event for event in read_lifecycle_events(log_path) if event.get("event_type") in _POST_MISSION_EVENT_TYPES]
    relevant.sort(key=_event_sort_key)
    return tuple(relevant)


def _latest_event_time(event: dict[str, Any]) -> datetime | None:
    """Best-effort event timestamp.

    Prefers the typed payload timestamp (``reopened_at`` / ``recorded_at``) and
    falls back to the envelope ``timestamp`` so historical events without a
    payload time still order correctly.
    """
    payload = event.get("payload")
    if isinstance(payload, dict):
        for key in ("reopened_at", "recorded_at"):
            parsed = _parse_dt(payload.get(key))
            if parsed is not None:
                return parsed
    return _parse_dt(event.get("timestamp"))


def _last_reopen_at(events: tuple[dict[str, Any], ...]) -> datetime | None:
    times = [_latest_event_time(event) for event in events if event.get("event_type") == MISSION_REOPENED]
    filtered = [t for t in times if t is not None]
    return max(filtered) if filtered else None


def _last_follow_up_at(events: tuple[dict[str, Any], ...]) -> datetime | None:
    times = [_latest_event_time(event) for event in events if event.get("event_type") == FOLLOW_UP_RECORDED]
    filtered = [t for t in times if t is not None]
    return max(filtered) if filtered else None


def _last_merge_marker_at(feature_dir: Path) -> datetime | None:
    """Timestamp of the last merge/completion marker from ``meta.json``.

    ``spec-kitty mission reopen`` clears ``merged_*`` (IC-02), so after a re-open
    this is typically ``None``. A subsequent re-merge re-stamps ``merged_at`` (by
    :func:`specify_cli.merge.baseline.record_baseline_merge_commit`); when that
    postdates the latest re-open the mission is no longer ``reopened``. The
    ``merged_at`` marker itself is restored by #4090 — its writer had been
    deleted in #2258. Returns the datetime (not a bool) so :func:`_is_reopened`
    can compare it against the last re-open time.
    """
    from specify_cli.core.paths import load_meta_fail_closed

    meta = load_meta_fail_closed(feature_dir) or {}
    return _parse_dt(meta.get("merged_at"))


def _is_reopened(
    *,
    last_reopen_at: datetime | None,
    last_merge_at: datetime | None,
) -> bool:
    """True when the latest re-open postdates the last merge marker (FR-002)."""
    if last_reopen_at is None:
        return False
    if last_merge_at is None:
        return True
    return last_reopen_at > last_merge_at


def _classify_state(
    *,
    total_wps: int,
    active_wp_count: int,
    terminal_wp_count: int,
    age_days: int | None,
    is_reopened: bool = False,
) -> tuple[str, str | None, str]:
    # FR-002 crux: a re-open event postdating the last merge marker makes the
    # mission actionable again regardless of WP terminality. The event is the
    # single authority here — WP lanes are NOT mutated by a re-open (D-A2).
    if is_reopened:
        return (
            "reopened",
            "reopened",
            "Mission was re-opened after merge and is actionable again.",
        )

    if active_wp_count > 0:
        if age_days is not None and age_days >= MISSION_ABANDONED_THRESHOLD_DAYS:
            return ("abandoned", None, "Active work appears abandoned and should stay off primary surfaces.")
        if age_days is not None and age_days >= MISSION_STALE_THRESHOLD_DAYS:
            return ("stale", None, "Active work has gone stale and should be recovered before it resurfaces.")
        return ("active", "active", "Mission has live work in progress or review.")

    if total_wps > 0 and terminal_wp_count == total_wps:
        if age_days is not None and age_days <= MISSION_RECENT_COMPLETION_WINDOW_DAYS:
            return ("recently_completed", "recently_completed", "Mission completed recently and still deserves short-lived visibility.")
        return ("archived", None, "Mission is completed and now belongs in history rather than the default surface.")

    if age_days is not None and age_days >= MISSION_ABANDONED_THRESHOLD_DAYS:
        return ("abandoned", None, "Mission never reached an active terminal state and now looks abandoned.")
    if age_days is not None and age_days >= MISSION_STALE_THRESHOLD_DAYS:
        return ("stale", None, "Mission is recoverable but stale and should not pollute primary surfaces.")
    return ("recoverable", None, "Mission is recoverable history and not active enough for the default surface.")


# States in which a mission counts as having *reached completion* — i.e. all
# work packages are terminal. These are the classifier outputs that mean
# "all-WPs-terminal" (see ``_classify_state``). ``merged_at`` in ``meta.json``
# is treated as an independent completion signal alongside these (see
# ``is_mission_completed``).
_COMPLETED_LIFECYCLE_STATES = frozenset({"recently_completed", "archived"})


def is_mission_merged(feature_dir: Path) -> bool:
    """Return ``True`` iff the mission carries a LIVE merge marker (#801, #4090).

    Narrower than :func:`is_mission_completed`: ONLY the explicit ``merged_at``
    marker counts — an unmerged mission whose WPs are all terminal
    (``recently_completed`` / ``archived``) is NOT merged. Gates that must fire
    exclusively on merged missions (the runtime bootstrap short-circuit at
    ``runtime_bridge.py`` :1600, the resolver's primary re-anchor at
    ``surface_resolver.py`` :745) use this predicate so a normally-completing
    mission still finalizes its run and passes the retrospective gate.

    Reopen-aware (IC-02, #4090): a mission is merged iff ``merged_at`` is present
    AND no ``MissionReopened`` event postdates it. ``spec-kitty mission reopen``
    both clears ``merged_*`` from ``meta.json`` and appends the event; this
    predicate is event-sourced (no meta-mutating clearer of its own), so a
    re-opened mission reads as NOT merged even in the defense-in-depth case where
    the marker survives on a diverged surface. A re-merge re-stamps a fresh
    ``merged_at`` that postdates the re-open, restoring ``True``.
    """
    last_merge_at = _last_merge_marker_at(feature_dir)
    if last_merge_at is None:
        return False
    last_reopen_at = _last_reopen_at(_collect_post_mission_events(feature_dir))
    return not _is_reopened(last_reopen_at=last_reopen_at, last_merge_at=last_merge_at)


def is_mission_completed(
    feature_dir: Path,
    *,
    now: datetime | None = None,
    clock: Clock = DEFAULT_CLOCK,
) -> bool:
    """Return ``True`` iff the mission has reached completion (#1926).

    Completion is the precondition for post-mission lifecycle facts
    (``MissionReopened`` / ``FollowUpRecorded``): those events are only valid
    once a mission has actually completed. A mission is completed when EITHER:

    * ``merged_at`` is present in ``meta.json`` (an explicit merge marker), OR
    * ``derive_mission_lifecycle`` classifies it as completed
      (``recently_completed`` / ``archived`` — i.e. every WP is terminal).

    Fail-closed: any state that is not provably completed returns ``False``.

    Note the intentional self-correcting behaviour after a re-open: a
    ``MissionReopened`` event clears ``merged_at`` and flips the derived state to
    ``reopened`` (active), so this predicate returns ``False`` again — further
    post-mission events are correctly blocked until the mission is *re-completed*
    (re-merged or all WPs terminal once more).
    """
    if _last_merge_marker_at(feature_dir) is not None:
        return True
    lifecycle = derive_mission_lifecycle(feature_dir, now=now, clock=clock)
    return lifecycle.state in _COMPLETED_LIFECYCLE_STATES


def derive_mission_lifecycle(
    feature_dir: Path,
    *,
    now: datetime | None = None,
    clock: Clock = DEFAULT_CLOCK,
) -> MissionLifecycleResult:
    """Return canonical lifecycle state for one mission directory.

    ``clock``: injectable :class:`kernel.clock.Clock` (kernel-clock-single-door
    FR-009); defaults to :data:`kernel.clock.DEFAULT_CLOCK`. Used only when
    ``now`` (an explicit value) is omitted.
    """
    now = (now if now is not None else clock.now()).astimezone(UTC)
    identity = resolve_mission_identity(feature_dir)
    has_event_log = (feature_dir / EVENTS_FILENAME).exists()

    if has_event_log:
        from specify_cli.status.reducer import reduce

        snapshot = reduce(read_events(feature_dir))
        snapshot.mission_number = str(identity.mission_number) if identity.mission_number is not None else None
        snapshot.mission_type = identity.mission_type
        if not snapshot.mission_slug:
            snapshot.mission_slug = identity.mission_slug or feature_dir.name
    else:
        snapshot = _empty_snapshot(identity.mission_slug or feature_dir.name, identity.mission_number, identity.mission_type)

    progress = compute_weighted_progress(snapshot)
    total_wps = len(snapshot.work_packages)
    active_wp_count = 0
    blocked_wp_count = 0
    review_wp_count = 0
    terminal_wp_count = 0

    for wp_state in snapshot.work_packages.values():
        # Defensive defaults match the write side (#1775 review M4): an unseeded
        # or corrupt-lane WP is genesis (non-active), not planned — so it does not
        # inflate active_wp_count below.
        lane_value = wp_state.get("lane", Lane.GENESIS)
        try:
            lane = Lane(str(lane_value))
        except ValueError:
            lane = Lane.GENESIS
        wp_lifecycle_state = wp_state_for(lane)
        if lane in _ACTIVE_LANES:
            active_wp_count += 1
        if wp_lifecycle_state.is_blocked:
            blocked_wp_count += 1
        if wp_lifecycle_state.progress_bucket() == "review":
            review_wp_count += 1
        if wp_lifecycle_state.is_terminal:
            terminal_wp_count += 1

    last_transition_at = _derive_last_transition_at(snapshot)
    last_activity_at = last_transition_at or _fallback_created_at(feature_dir)
    age_days = None
    if last_activity_at is not None:
        age_delta = now - last_activity_at
        age_days = max(0, int(age_delta / timedelta(days=1)))

    post_mission_events = _collect_post_mission_events(feature_dir)
    last_reopen_at = _last_reopen_at(post_mission_events)
    last_follow_up_at = _last_follow_up_at(post_mission_events)
    last_merge_at = _last_merge_marker_at(feature_dir)
    is_reopened = _is_reopened(
        last_reopen_at=last_reopen_at,
        last_merge_at=last_merge_at,
    )

    mission_state, surface_state, reason = _classify_state(
        total_wps=total_wps,
        active_wp_count=active_wp_count,
        terminal_wp_count=terminal_wp_count,
        age_days=age_days,
        is_reopened=is_reopened,
    )

    return MissionLifecycleResult(
        mission_slug=snapshot.mission_slug or identity.mission_slug or feature_dir.name,
        mission_id=identity.mission_id,
        mission_number=identity.mission_number,
        mission_type=identity.mission_type,
        state=mission_state,
        surface_state=surface_state,
        reason=reason,
        last_activity_at=last_activity_at,
        last_transition_at=last_transition_at,
        age_days=age_days,
        completion_pct=progress.percentage,
        event_count=snapshot.event_count,
        total_wps=total_wps,
        active_wp_count=active_wp_count,
        blocked_wp_count=blocked_wp_count,
        review_wp_count=review_wp_count,
        terminal_wp_count=terminal_wp_count,
        has_event_log=has_event_log,
        post_mission_events=post_mission_events,
        last_follow_up_at=last_follow_up_at,
    )


def generate_lifecycle_json(
    feature_dir: Path,
    derived_dir: Path,
    *,
    now: datetime | None = None,
    clock: Clock = DEFAULT_CLOCK,
) -> None:
    """Write ``lifecycle.json`` for one mission under ``.kittify/derived``."""
    lifecycle = derive_mission_lifecycle(feature_dir, now=now, clock=clock)
    mission_slug = lifecycle.mission_slug or feature_dir.name
    output_dir = derived_dir / mission_slug
    output_dir.mkdir(parents=True, exist_ok=True)

    out_path = output_dir / DERIVED_LIFECYCLE_FILENAME
    tmp_path = out_path.with_suffix(".json.tmp")
    tmp_path.write_text(
        json.dumps(lifecycle.to_dict(), sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(str(tmp_path), str(out_path))
