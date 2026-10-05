"""Regression (#5669): the move-task dirty gate must not block ``mission-events.jsonl``.

``spec-kitty next`` appends ``kitty-specs/<slug>/mission-events.jsonl`` — its own
tracked, write-only lifecycle observability log — and leaves it uncommitted. The
move-task dirty gate (``_validate_ready_for_review`` →
``_validate_research_artifacts`` → :func:`classify_dirty_paths` → ``_is_benign`` →
:func:`_is_review_handoff_survivor_path`) then refuses ``move-task --to approved``
(and ``for_review`` / ``done``) with "Blocking: N uncommitted file(s)".

The fix is a **scoped**, exact-anchored survivor in the per-gate review-handoff
classifier ONLY (``kitty-specs/<slug>/mission-events.jsonl``). The C-002 boundary
forbids widening the shared/destructive-gate owner
(``coordination.coherence.is_self_bookkeeping_churn`` /
``is_toolchain_generated_churn``), which feeds consolidate/accept/merge and whose
answer ``mission-events.jsonl`` has live research-gate readers depending on.
"""

from __future__ import annotations

import pytest

from specify_cli.coordination.coherence import (
    is_self_bookkeeping_churn,
    is_toolchain_generated_churn,
)
from specify_cli.review.dirty_classifier import classify_dirty_paths

pytestmark = [pytest.mark.fast, pytest.mark.regression]

_SLUG = "some-slug"
_MISSION_EVENTS = f"kitty-specs/{_SLUG}/mission-events.jsonl"


# ---------------------------------------------------------------------------
# T006(a) — POSITIVE: mission-root mission-events.jsonl is BENIGN (was RED)
# ---------------------------------------------------------------------------


def test_mission_events_log_is_benign_survivor() -> None:
    """With only ``mission-events.jsonl`` dirty, the gate must not block it.

    RED on the merge-base: before the fix ``_is_review_handoff_survivor_path``
    does not recognise the log, so it falls through to ``owning_wp_for_path``
    (which returns ``None`` — not a ``tasks/WPxx-*`` path) and is classified
    blocking.
    """
    blocking, benign = classify_dirty_paths([_MISSION_EVENTS], wp_id="WP01", mission_slug=_SLUG)
    assert blocking == []
    assert benign == [_MISSION_EVENTS]


# ---------------------------------------------------------------------------
# T006(b) — NEGATIVE controls: look-alikes and real work stay BLOCKING
# ---------------------------------------------------------------------------


def test_mission_events_lookalike_outside_kitty_specs_stays_blocking() -> None:
    """An operator file merely NAMED ``mission-events.jsonl`` is real dirt."""
    path = "src/app/mission-events.jsonl"
    blocking, benign = classify_dirty_paths([path], wp_id="WP01", mission_slug=_SLUG)
    assert blocking == [path]
    assert benign == []


def test_mission_events_one_level_too_deep_stays_blocking() -> None:
    """``kitty-specs/<slug>/research/mission-events.jsonl`` is NOT the mission-root
    log; the ``[^/]+`` anchor must not cross a ``/`` so it stays blocking."""
    path = f"kitty-specs/{_SLUG}/research/mission-events.jsonl"
    blocking, benign = classify_dirty_paths([path], wp_id="WP01", mission_slug=_SLUG)
    assert blocking == [path]
    assert benign == []


def test_genuine_source_path_stays_blocking() -> None:
    """A genuinely-owned source edit is still real, blocking dirt."""
    path = "src/specify_cli/review/dirty_classifier.py"
    blocking, benign = classify_dirty_paths([path], wp_id="WP01", mission_slug=_SLUG)
    assert blocking == [path]
    assert benign == []


def test_mission_events_benign_alongside_real_dirt() -> None:
    """The survivor is scoped: a co-dirty operator file still blocks the handoff."""
    source = "src/specify_cli/review/dirty_classifier.py"
    blocking, benign = classify_dirty_paths([_MISSION_EVENTS, source], wp_id="WP01", mission_slug=_SLUG)
    assert blocking == [source]
    assert benign == [_MISSION_EVENTS]


# ---------------------------------------------------------------------------
# T008 — C-002 GUARD: the global/destructive-gate owner is UNCHANGED
# ---------------------------------------------------------------------------


def test_global_churn_owner_still_treats_mission_events_as_real_dirt() -> None:
    """C-002: the shared owner that feeds consolidate/accept/merge must NOT be
    widened. ``mission-events.jsonl`` stays real dirt for those destructive gates;
    only the per-gate review-handoff survivor exempts it."""
    assert is_self_bookkeeping_churn(_MISSION_EVENTS) is False
    assert is_toolchain_generated_churn(_MISSION_EVENTS) is False
