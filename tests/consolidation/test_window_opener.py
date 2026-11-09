"""The window opener reader (Mission consolidation-window-provenance-01M6Y84D, WP08).

``window_opener_events`` picks the events that may open a work package's window;
``window_open_of`` binds one of them to ``WindowOpen`` or a typed ``WindowGap``
(data-model section 3, contract ``status-event-wp-window.md`` R-1..R-5, FR-004,
FR-021, FR-022). Every test is pure: events are built in memory and the two
predicates are fakes over a hand-drawn commit graph, so no git is read.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import replace
from typing import Any

import pytest

from specify_cli.consolidation.wp_attribution import (
    OpenerSelection,
    WindowGap,
    WindowGapReason,
    WindowOpen,
    approval_window_open_stamp,
    window_open_of,
    window_opener_events,
)
from specify_cli.status import Lane, StatusEvent

pytestmark = [pytest.mark.fast]

_SLUG = "window-opener-01M6Y84D"

# A hand-drawn commit graph: A <- B <- C on the lane, X before A, U unrelated.
SHA_X = "0" * 40
SHA_A = "a" * 40
SHA_B = "b" * 40
SHA_C = "c" * 40
SHA_U = "e" * 40
SHA_GONE = "f" * 40  # not in this clone
_PARENT: Mapping[str, str | None] = {SHA_X: None, SHA_A: SHA_X, SHA_B: SHA_A, SHA_C: SHA_B, SHA_U: None}
_LANE = frozenset({SHA_X, SHA_A, SHA_B, SHA_C})


def _ancestry(sha: str) -> set[str]:
    seen: set[str] = set()
    cursor: str | None = sha
    while cursor is not None and cursor in _PARENT:
        seen.add(cursor)
        cursor = _PARENT[cursor]
    return seen


def is_ancestor(a: str, b: str) -> bool:
    """``a`` is an ancestor of or equal to ``b``; unknown SHAs are never ancestors (never raises)."""
    return a in _PARENT and a in _ancestry(b)


def on_lane(sha: str) -> bool:
    return sha in _LANE


class _Counter:
    def __init__(self) -> None:
        self.next = 0

    def __call__(self) -> str:
        self.next += 1
        return f"01M6Y84D{self.next:018d}"


def _event(
    ids: Callable[[], str],
    wp_id: str,
    from_lane: Lane,
    to_lane: Lane,
    *,
    window: Any = None,
    at: str = "2026-11-09T10:00:00+00:00",
    actor: str = "claude",
    force: bool = False,
) -> StatusEvent:
    metadata: dict[str, Any] | None = None if window is None else {"wp_window": window}
    return StatusEvent(
        event_id=ids(),
        mission_slug=_SLUG,
        wp_id=wp_id,
        from_lane=from_lane,
        to_lane=to_lane,
        at=at,
        actor=actor,
        force=force,
        execution_mode="worktree",
        policy_metadata=metadata,
    )


def opened(sha: str) -> dict[str, Any]:
    return {"schema_version": 1, "open_sha": sha}


def branch_missing(detail: str = "refs/heads/kitty/mission-x-lane-a not found") -> dict[str, Any]:
    return {"schema_version": 1, "gap": {"reason": "lane_branch_missing", "detail": detail}}


def capture_failed(cause: str = "git_error", detail: str = "fatal: bad object") -> dict[str, Any]:
    return {"schema_version": 1, "gap": {"reason": "capture_failed", "cause": cause, "detail": detail}}


def _open(events: Iterable[StatusEvent], wp_id: str = "WP01") -> WindowOpen | WindowGap:
    return window_open_of(list(events), wp_id, on_lane=on_lane, is_ancestor=is_ancestor)


@pytest.fixture
def ids() -> _Counter:
    return _Counter()


# --------------------------------------------------------------------------- #
# Value types
# --------------------------------------------------------------------------- #


def test_gap_reason_report_strings() -> None:
    assert [reason.report_text for reason in WindowGapReason] == [
        "not recorded",
        "capture failed",
        "lane branch missing",
        "not on lane",
    ]


# --------------------------------------------------------------------------- #
# R-1 .. R-3: binding the opener
# --------------------------------------------------------------------------- #


def test_single_recorded_claim_opens_window(ids: _Counter) -> None:
    events = [
        _event(ids, "WP01", Lane.PLANNED, Lane.PLANNED),
        _event(ids, "WP01", Lane.PLANNED, Lane.CLAIMED, window=opened(SHA_A)),
    ]
    assert _open(events) == WindowOpen(SHA_A)


def test_no_wp_window_key_is_not_recorded_gap(ids: _Counter) -> None:
    events = [_event(ids, "WP01", Lane.PLANNED, Lane.CLAIMED)]
    assert _open(events) == WindowGap(WindowGapReason.NOT_RECORDED)


def test_mixed_log_straddling_upgrade_reads_per_event(ids: _Counter) -> None:
    events = [
        _event(ids, "WP01", Lane.PLANNED, Lane.CLAIMED),  # written before the upgrade
        _event(ids, "WP02", Lane.PLANNED, Lane.CLAIMED, window=opened(SHA_B)),  # written after it
    ]
    assert _open(events, "WP01") == WindowGap(WindowGapReason.NOT_RECORDED)
    assert _open(events, "WP02") == WindowOpen(SHA_B)


def test_capture_failed_carries_cause_and_detail(ids: _Counter) -> None:
    events = [_event(ids, "WP01", Lane.PLANNED, Lane.CLAIMED, window=capture_failed("probe_error", "probe crashed"))]
    assert _open(events) == WindowGap(WindowGapReason.CAPTURE_FAILED, cause="probe_error", detail="probe crashed")


def test_leading_lane_branch_missing_is_skipped_then_in_progress_sha_opens(ids: _Counter) -> None:
    events = [
        _event(ids, "WP01", Lane.PLANNED, Lane.CLAIMED, window=branch_missing()),
        _event(ids, "WP01", Lane.CLAIMED, Lane.IN_PROGRESS, window=opened(SHA_A)),
    ]
    assert _open(events) == WindowOpen(SHA_A)
    selection = window_opener_events(events, "WP01", cycle=True)
    assert selection.skipped_branch_missing == 1
    assert [event.to_lane for event in selection.candidates] == [Lane.IN_PROGRESS]


def test_leading_lane_branch_missing_then_unusable_opener_is_that_gap(ids: _Counter) -> None:
    skip = _event(ids, "WP01", Lane.PLANNED, Lane.CLAIMED, window=branch_missing())
    unrecorded = _event(ids, "WP01", Lane.CLAIMED, Lane.IN_PROGRESS)
    failed = _event(ids, "WP01", Lane.CLAIMED, Lane.IN_PROGRESS, window=capture_failed())
    assert _open([skip, unrecorded]) == WindowGap(WindowGapReason.NOT_RECORDED)
    assert _open([skip, failed]) == WindowGap(WindowGapReason.CAPTURE_FAILED, cause="git_error", detail="fatal: bad object")


def test_only_lane_branch_missing_openers_give_lane_branch_missing_gap(ids: _Counter) -> None:
    events = [
        _event(ids, "WP01", Lane.PLANNED, Lane.CLAIMED, window=branch_missing("first")),
        _event(ids, "WP01", Lane.CLAIMED, Lane.IN_PROGRESS, window=branch_missing("second")),
        _event(ids, "WP01", Lane.IN_PROGRESS, Lane.FOR_REVIEW),
    ]
    assert _open(events) == WindowGap(WindowGapReason.LANE_BRANCH_MISSING, detail="second")


def test_lane_branch_missing_without_detail_reports_empty_detail(ids: _Counter) -> None:
    window = {"schema_version": 1, "gap": {"reason": "lane_branch_missing"}}
    events = [_event(ids, "WP01", Lane.PLANNED, Lane.CLAIMED, window=window)]
    assert _open(events) == WindowGap(WindowGapReason.LANE_BRANCH_MISSING, detail="")


def test_unrecorded_first_opener_is_not_replaced_by_later_recorded_one(ids: _Counter) -> None:
    events = [
        _event(ids, "WP01", Lane.PLANNED, Lane.CLAIMED),
        _event(ids, "WP01", Lane.CLAIMED, Lane.IN_PROGRESS, window=opened(SHA_A)),
    ]
    assert _open(events) == WindowGap(WindowGapReason.NOT_RECORDED)


def test_sha_less_candidates_after_a_sha_bearing_one_are_ignored(ids: _Counter) -> None:
    events = [
        _event(ids, "WP01", Lane.PLANNED, Lane.CLAIMED, window=opened(SHA_A)),
        _event(ids, "WP01", Lane.CLAIMED, Lane.IN_PROGRESS, window=capture_failed()),
        _event(ids, "WP01", Lane.IN_PROGRESS, Lane.BLOCKED),
        _event(ids, "WP01", Lane.BLOCKED, Lane.IN_PROGRESS, window=branch_missing()),
        _event(ids, "WP01", Lane.IN_PROGRESS, Lane.IN_PROGRESS),
    ]
    assert _open(events) == WindowOpen(SHA_A)


# --------------------------------------------------------------------------- #
# FR-021: cycles, rework, blocked, migration
# --------------------------------------------------------------------------- #


def test_rewind_to_planned_starts_new_cycle(ids: _Counter) -> None:
    events = [
        _event(ids, "WP01", Lane.PLANNED, Lane.CLAIMED, window=opened(SHA_A)),
        _event(ids, "WP01", Lane.CLAIMED, Lane.IN_PROGRESS, window=opened(SHA_A)),
        _event(ids, "WP01", Lane.IN_PROGRESS, Lane.PLANNED),
        _event(ids, "WP01", Lane.PLANNED, Lane.CLAIMED, window=opened(SHA_C)),
    ]
    assert _open(events) == WindowOpen(SHA_C)


def test_rewind_from_blocked_or_claimed_also_resets(ids: _Counter) -> None:
    for rewind_from in (Lane.BLOCKED, Lane.CLAIMED):
        events = [
            _event(ids, "WP01", Lane.PLANNED, Lane.CLAIMED, window=opened(SHA_A)),
            _event(ids, "WP01", Lane.CLAIMED, rewind_from),
            _event(ids, "WP01", rewind_from, Lane.PLANNED),
            _event(ids, "WP01", Lane.PLANNED, Lane.CLAIMED, window=opened(SHA_C)),
        ]
        assert _open(events) == WindowOpen(SHA_C), rewind_from


def test_rewind_with_no_new_opener_is_not_recorded(ids: _Counter) -> None:
    events = [
        _event(ids, "WP01", Lane.PLANNED, Lane.CLAIMED, window=opened(SHA_A)),
        _event(ids, "WP01", Lane.CLAIMED, Lane.PLANNED),
    ]
    assert _open(events) == WindowGap(WindowGapReason.NOT_RECORDED)


@pytest.mark.parametrize("rejected_from", [Lane.FOR_REVIEW, Lane.IN_REVIEW, Lane.APPROVED, Lane.DONE])
def test_review_rejection_to_planned_does_not_reset(ids: _Counter, rejected_from: Lane) -> None:
    events = [
        _event(ids, "WP01", Lane.PLANNED, Lane.CLAIMED, window=opened(SHA_A)),
        _event(ids, "WP01", Lane.CLAIMED, Lane.IN_PROGRESS, window=opened(SHA_A)),
        _event(ids, "WP01", Lane.IN_PROGRESS, Lane.FOR_REVIEW),
        _event(ids, "WP01", Lane.FOR_REVIEW, rejected_from),
        _event(ids, "WP01", rejected_from, Lane.PLANNED),
        _event(ids, "WP01", Lane.PLANNED, Lane.CLAIMED, window=opened(SHA_B)),
    ]
    assert _open(events) == WindowOpen(SHA_A)


def test_review_rejection_to_in_progress_does_not_reset(ids: _Counter) -> None:
    events = [
        _event(ids, "WP01", Lane.PLANNED, Lane.CLAIMED, window=opened(SHA_A)),
        _event(ids, "WP01", Lane.CLAIMED, Lane.IN_PROGRESS, window=opened(SHA_A)),
        _event(ids, "WP01", Lane.IN_PROGRESS, Lane.FOR_REVIEW),
        _event(ids, "WP01", Lane.FOR_REVIEW, Lane.IN_REVIEW),
        _event(ids, "WP01", Lane.IN_REVIEW, Lane.IN_PROGRESS, window=opened(SHA_B)),
    ]
    assert _open(events) == WindowOpen(SHA_A)


def test_blocked_opens_nothing(ids: _Counter) -> None:
    events = [
        # a blocked move never opens, even if it carried a (stray) window value
        _event(ids, "WP01", Lane.PLANNED, Lane.BLOCKED, window=opened(SHA_X)),
        _event(ids, "WP01", Lane.BLOCKED, Lane.CLAIMED, window=opened(SHA_A)),
    ]
    assert _open(events) == WindowOpen(SHA_A)
    only_blocked = [_event(ids, "WP02", Lane.PLANNED, Lane.BLOCKED, window=opened(SHA_X))]
    assert _open(only_blocked, "WP02") == WindowGap(WindowGapReason.NOT_RECORDED)


def test_migration_events_never_open_or_reset(ids: _Counter) -> None:
    events = [
        # a migration seed with an (ancestor) SHA would win if it counted as an opener
        _event(ids, "WP01", Lane.PLANNED, Lane.CLAIMED, window=opened(SHA_X), actor="migration:backfill"),
        _event(ids, "WP01", Lane.PLANNED, Lane.CLAIMED, window=opened(SHA_A)),
        # a migration rewind would start a new cycle (and open at C) if it counted
        _event(ids, "WP01", Lane.CLAIMED, Lane.PLANNED, actor="migration:backfill"),
        _event(ids, "WP01", Lane.PLANNED, Lane.CLAIMED, window=opened(SHA_C)),
    ]
    assert _open(events) == WindowOpen(SHA_A)
    selection = window_opener_events(events, "WP01", cycle=True)
    assert all(event.actor == "claude" for event in selection.candidates)


def test_other_work_packages_events_are_ignored(ids: _Counter) -> None:
    events = [
        _event(ids, "WP02", Lane.PLANNED, Lane.CLAIMED, window=opened(SHA_X)),
        _event(ids, "WP01", Lane.PLANNED, Lane.CLAIMED, window=opened(SHA_B)),
        _event(ids, "WP02", Lane.CLAIMED, Lane.PLANNED),
    ]
    assert _open(events) == WindowOpen(SHA_B)


# --------------------------------------------------------------------------- #
# Topology-first ordering with log-order fallback
# --------------------------------------------------------------------------- #


def test_skewed_clock_rework_cannot_narrow_window(ids: _Counter) -> None:
    claim = _event(ids, "WP01", Lane.PLANNED, Lane.CLAIMED, window=opened(SHA_A), at="2026-11-09T10:00:00+00:00")
    review = _event(ids, "WP01", Lane.CLAIMED, Lane.FOR_REVIEW, at="2026-11-09T11:00:00+00:00")
    # the rework clock runs behind: its ``at`` sorts before the claim, its SHA is a descendant
    rework = _event(ids, "WP01", Lane.FOR_REVIEW, Lane.IN_PROGRESS, window=opened(SHA_C), at="2026-11-09T09:00:00+00:00")
    assert _open([claim, review, rework]) == WindowOpen(SHA_A)
    # even when the log itself lists the descendant first (an ``at``-ordered union), topology wins
    assert _open([rework, claim, review]) == WindowOpen(SHA_A)


def test_unrelated_shas_fall_back_to_log_order(ids: _Counter) -> None:
    first = _event(ids, "WP01", Lane.PLANNED, Lane.CLAIMED, window=opened(SHA_U))
    second = _event(ids, "WP01", Lane.CLAIMED, Lane.IN_PROGRESS, window=opened(SHA_A))
    assert _open([first, second]) == WindowGap(WindowGapReason.NOT_ON_LANE, sha=SHA_U)
    # three candidates where no single SHA is an ancestor of every other: the first wins
    third = _event(ids, "WP01", Lane.IN_PROGRESS, Lane.IN_PROGRESS, window=opened(SHA_B))
    assert _open([second, first, third]) == WindowOpen(SHA_A)


def test_repeated_sha_does_not_break_the_chain(ids: _Counter) -> None:
    events = [
        _event(ids, "WP01", Lane.PLANNED, Lane.CLAIMED, window=opened(SHA_B)),
        _event(ids, "WP01", Lane.CLAIMED, Lane.IN_PROGRESS, window=opened(SHA_B)),
        _event(ids, "WP01", Lane.FOR_REVIEW, Lane.IN_PROGRESS, window=opened(SHA_C)),
    ]
    assert _open(events) == WindowOpen(SHA_B)


# --------------------------------------------------------------------------- #
# R-4: not on lane / unresolvable
# --------------------------------------------------------------------------- #


def test_sha_not_on_lane_is_not_on_lane_gap(ids: _Counter) -> None:
    events = [_event(ids, "WP01", Lane.PLANNED, Lane.CLAIMED, window=opened(SHA_U))]
    assert _open(events) == WindowGap(WindowGapReason.NOT_ON_LANE, sha=SHA_U)


def test_unresolvable_sha_is_not_on_lane_gap(ids: _Counter) -> None:
    events = [
        _event(ids, "WP01", Lane.PLANNED, Lane.CLAIMED, window=opened(SHA_GONE)),
        _event(ids, "WP01", Lane.CLAIMED, Lane.IN_PROGRESS, window=opened(SHA_A)),
    ]
    # neither predicate raises for an object this clone does not hold
    assert _open(events) == WindowGap(WindowGapReason.NOT_ON_LANE, sha=SHA_GONE)


# --------------------------------------------------------------------------- #
# R-5: malformed values are absent, flagged, never fatal
# --------------------------------------------------------------------------- #

_MALFORMED: dict[str, Any] = {
    "unknown_version": {"schema_version": 2, "open_sha": SHA_A},
    "bool_version": {"schema_version": True, "open_sha": SHA_A},
    "no_version": {"open_sha": SHA_A},
    "both_branches": {"schema_version": 1, "open_sha": SHA_A, "gap": {"reason": "lane_branch_missing"}},
    "neither_branch": {"schema_version": 1},
    "bad_hex_upper": {"schema_version": 1, "open_sha": "A" * 40},
    "bad_hex_short": {"schema_version": 1, "open_sha": "a" * 39},
    "sha_not_str": {"schema_version": 1, "open_sha": 7},
    "extra_key": {"schema_version": 1, "open_sha": SHA_A, "note": "x"},
    "not_an_object": "a" * 40,
    "gap_not_an_object": {"schema_version": 1, "gap": "lane_branch_missing"},
    "gap_extra_key": {"schema_version": 1, "gap": {"reason": "lane_branch_missing", "why": "x"}},
    "gap_unknown_reason": {"schema_version": 1, "gap": {"reason": "not_on_lane"}},
    "lane_branch_missing_with_cause": {"schema_version": 1, "gap": {"reason": "lane_branch_missing", "cause": "git_error"}},
    "capture_failed_without_cause": {"schema_version": 1, "gap": {"reason": "capture_failed"}},
    "capture_failed_unknown_cause": {"schema_version": 1, "gap": {"reason": "capture_failed", "cause": "oops"}},
    "detail_not_str": {"schema_version": 1, "gap": {"reason": "capture_failed", "cause": "git_error", "detail": 3}},
    "detail_too_long": {"schema_version": 1, "gap": {"reason": "capture_failed", "cause": "git_error", "detail": "x" * 501}},
}


@pytest.mark.parametrize("name", sorted(_MALFORMED))
def test_malformed_value_is_not_recorded_and_flagged(ids: _Counter, name: str) -> None:
    events = [
        _event(ids, "WP01", Lane.PLANNED, Lane.CLAIMED, window=_MALFORMED[name]),
        _event(ids, "WP01", Lane.CLAIMED, Lane.IN_PROGRESS, window=opened(SHA_A)),
    ]
    assert _open(events) == WindowGap(WindowGapReason.NOT_RECORDED, malformed=True)


def test_malformed_lane_branch_missing_is_not_skipped(ids: _Counter) -> None:
    events = [_event(ids, "WP01", Lane.PLANNED, Lane.CLAIMED, window=_MALFORMED["lane_branch_missing_with_cause"])]
    assert window_opener_events(events, "WP01", cycle=True).skipped_branch_missing == 0
    assert _open(events) == WindowGap(WindowGapReason.NOT_RECORDED, malformed=True)


def test_detail_at_the_length_limit_is_accepted(ids: _Counter) -> None:
    events = [_event(ids, "WP01", Lane.PLANNED, Lane.CLAIMED, window=capture_failed(detail="x" * 500))]
    assert _open(events) == WindowGap(WindowGapReason.CAPTURE_FAILED, cause="git_error", detail="x" * 500)


def test_policy_metadata_without_wp_window_is_not_recorded_unflagged(ids: _Counter) -> None:
    event = _event(ids, "WP01", Lane.PLANNED, Lane.CLAIMED)
    stamped = replace(event, policy_metadata={"lane_head": SHA_A})
    assert _open([stamped]) == WindowGap(WindowGapReason.NOT_RECORDED, malformed=False)


# --------------------------------------------------------------------------- #
# Forced approvals and the shared selector
# --------------------------------------------------------------------------- #


def test_forced_approval_without_opener_is_not_recorded(ids: _Counter) -> None:
    events = [
        _event(ids, "WP01", Lane.PLANNED, Lane.PLANNED),
        _event(ids, "WP01", Lane.PLANNED, Lane.APPROVED, force=True),
    ]
    assert _open(events) == WindowGap(WindowGapReason.NOT_RECORDED)
    assert window_opener_events(events, "WP01", cycle=True) == OpenerSelection(candidates=(), skipped=())


def _stamped(ids: _Counter, from_lane: Lane, to_lane: Lane, stamp: str | None, **kwargs: Any) -> StatusEvent:
    event = _event(ids, "WP01", from_lane, to_lane, **kwargs)
    metadata = dict(event.policy_metadata or {})
    if stamp is not None:
        metadata["lane_head"] = stamp
    return replace(event, policy_metadata=metadata or None)


def test_approval_window_open_stamp_unchanged_first_claim_rule(ids: _Counter) -> None:
    rewound = [
        _stamped(ids, Lane.PLANNED, Lane.BLOCKED, SHA_X),
        _stamped(ids, Lane.BLOCKED, Lane.CLAIMED, SHA_A, window=branch_missing()),
        _stamped(ids, Lane.CLAIMED, Lane.PLANNED, SHA_A),
        _stamped(ids, Lane.PLANNED, Lane.CLAIMED, SHA_C),
    ]
    # cycle=False: the first claim ever, even after a rewind, and no lane_branch_missing skip
    assert approval_window_open_stamp(rewound, "WP01") == SHA_A
    selection = window_opener_events(rewound, "WP01", cycle=False)
    assert selection.skipped_branch_missing == 0
    assert [event.to_lane for event in selection.candidates] == [Lane.CLAIMED, Lane.CLAIMED]
    # an unstamped first claim is never stood in for by a later stamped one
    unstamped_first = [_stamped(ids, Lane.PLANNED, Lane.CLAIMED, None), _stamped(ids, Lane.CLAIMED, Lane.IN_PROGRESS, SHA_B)]
    assert approval_window_open_stamp(unstamped_first, "WP01") is None
    # migration seeds and other work packages never count; no entry at all is None
    migrated = [_stamped(ids, Lane.PLANNED, Lane.CLAIMED, SHA_X, actor="migration:seed"), _stamped(ids, Lane.CLAIMED, Lane.IN_PROGRESS, SHA_B)]
    assert approval_window_open_stamp(migrated, "WP01") == SHA_B
    assert approval_window_open_stamp(migrated, "WP02") is None
