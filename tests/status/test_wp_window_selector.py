"""The FR-021 window-opener selector lives in ``specify_cli.status`` (Mission review-context-wp-diff-01M774QF, WP01).

The selector moved verbatim from ``consolidation/wp_attribution.py`` so that ``runtime`` and
``review`` can share it without importing ``consolidation`` (C-005, C-007). These tests pin
the one definition: the old import path and the ``specify_cli.status`` facade re-export the
same objects, and a smoke of the rework / rewind / gap rules runs against the new home. They
are pure: events are built in memory and the predicates are dict-backed fakes, so no git is read.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import pytest

import specify_cli.status as status_facade
from specify_cli.consolidation import wp_attribution
from specify_cli.status import Lane, StatusEvent, lane_head, wp_window_selector
from specify_cli.status.wp_window import encode_open
from specify_cli.status.wp_window_selector import (
    WindowGap,
    WindowGapReason,
    WindowOpen,
    window_open_of,
    window_opener_events,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_SLUG = "review-context-wp-diff-01M774QF"
_MOVED_NAMES = (
    "window_open_of",
    "window_opener_events",
    "OpenerSelection",
    "WindowOpen",
    "WindowGap",
    "WindowGapReason",
    "is_migration_event",
)

SHA_A = "a" * 40
SHA_B = "b" * 40
# B descends from A; neither has another parent in this hand-drawn graph.
_PARENT: Mapping[str, str | None] = {SHA_A: None, SHA_B: SHA_A}


def _ancestry(sha: str) -> set[str]:
    seen: set[str] = set()
    cursor: str | None = sha
    while cursor is not None and cursor in _PARENT:
        seen.add(cursor)
        cursor = _PARENT[cursor]
    return seen


def _is_ancestor(a: str, b: str) -> bool:
    return a in _PARENT and a in _ancestry(b)


def _on_lane(_sha: str) -> bool:
    return True


class _Ids:
    def __init__(self) -> None:
        self.count = 0

    def __call__(self) -> str:
        self.count += 1
        return f"01M774QF{self.count:018d}"


def _event(
    ids: Callable[[], str],
    from_lane: Lane,
    to_lane: Lane,
    *,
    window: dict[str, Any] | None = None,
    actor: str = "claude",
    wp_id: str = "WP01",
) -> StatusEvent:
    return StatusEvent(
        event_id=ids(),
        mission_slug=_SLUG,
        wp_id=wp_id,
        from_lane=from_lane,
        to_lane=to_lane,
        at="2026-11-12T10:00:00+00:00",
        actor=actor,
        force=False,
        execution_mode="worktree",
        policy_metadata=None if window is None else {"wp_window": window},
    )


def _open(events: list[StatusEvent]) -> WindowOpen | WindowGap:
    return window_open_of(events, "WP01", on_lane=_on_lane, is_ancestor=_is_ancestor)


@pytest.fixture
def ids() -> _Ids:
    return _Ids()


# --------------------------------------------------------------------------- #
# One definition, re-exported
# --------------------------------------------------------------------------- #


def test_facade_re_exports_read_lane_head_without_advertising_it() -> None:
    assert status_facade.read_lane_head is lane_head.read_lane_head
    assert "read_lane_head" not in status_facade.__all__


@pytest.mark.parametrize("name", _MOVED_NAMES)
def test_old_path_and_facade_resolve_to_the_one_definition(name: str) -> None:
    moved = getattr(wp_window_selector, name)
    assert getattr(wp_attribution, name) is moved
    assert getattr(status_facade, name) is moved


def test_selector_is_defined_in_the_status_package() -> None:
    assert wp_window_selector.window_open_of.__module__ == "specify_cli.status.wp_window_selector"
    assert wp_window_selector.WindowGap.__module__ == "specify_cli.status.wp_window_selector"


# --------------------------------------------------------------------------- #
# FR-021 smoke: rework keeps the window, a rewind starts a new one
# --------------------------------------------------------------------------- #


def test_review_rejection_keeps_the_window(ids: _Ids) -> None:
    events = [
        _event(ids, Lane.PLANNED, Lane.CLAIMED, window=encode_open(SHA_A)),
        _event(ids, Lane.CLAIMED, Lane.IN_PROGRESS),
        _event(ids, Lane.IN_PROGRESS, Lane.FOR_REVIEW),
        _event(ids, Lane.FOR_REVIEW, Lane.PLANNED),
        _event(ids, Lane.PLANNED, Lane.CLAIMED, window=encode_open(SHA_B)),
    ]
    assert _open(events) == WindowOpen(SHA_A)


def test_rewind_to_planned_starts_a_new_window(ids: _Ids) -> None:
    events = [
        _event(ids, Lane.PLANNED, Lane.CLAIMED, window=encode_open(SHA_A)),
        _event(ids, Lane.CLAIMED, Lane.IN_PROGRESS),
        _event(ids, Lane.IN_PROGRESS, Lane.PLANNED),
        _event(ids, Lane.PLANNED, Lane.CLAIMED, window=encode_open(SHA_B)),
    ]
    assert _open(events) == WindowOpen(SHA_B)


# --------------------------------------------------------------------------- #
# Gap smoke
# --------------------------------------------------------------------------- #


def test_opener_without_wp_window_is_a_not_recorded_gap(ids: _Ids) -> None:
    assert _open([_event(ids, Lane.PLANNED, Lane.CLAIMED)]) == WindowGap(WindowGapReason.NOT_RECORDED)


def test_leading_lane_branch_missing_opener_is_skipped(ids: _Ids) -> None:
    missing = {"schema_version": 1, "gap": {"reason": "lane_branch_missing", "detail": "no branch"}}
    events = [
        _event(ids, Lane.PLANNED, Lane.CLAIMED, window=missing),
        _event(ids, Lane.CLAIMED, Lane.IN_PROGRESS, window=encode_open(SHA_A)),
    ]
    assert window_opener_events(events, "WP01", cycle=True).skipped_branch_missing == 1
    assert _open(events) == WindowOpen(SHA_A)


def test_migration_actor_event_is_ignored(ids: _Ids) -> None:
    events = [
        _event(ids, Lane.PLANNED, Lane.CLAIMED, window=encode_open(SHA_B), actor="migration:backfill"),
        _event(ids, Lane.PLANNED, Lane.CLAIMED, window=encode_open(SHA_A)),
    ]
    assert window_opener_events(events, "WP01", cycle=False).candidates == (events[1],)
    assert _open(events) == WindowOpen(SHA_A)
    assert wp_window_selector.is_migration_event(events[0])
    assert not wp_window_selector.is_migration_event(events[1])
