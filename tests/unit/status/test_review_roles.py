"""Truth-table tests for the pure latest-implementer projection (#5196)."""

from __future__ import annotations

from typing import cast

import pytest

from specify_cli.status import latest_implementer_actor
from specify_cli.status.models import ActorField, Lane, StatusEvent
from specify_cli.status.work_package_lifecycle import _actor_key

pytestmark = pytest.mark.unit

IMPL = "claude:opus:implementer-ivan:implementer"
REVW = "codex:gpt-5:reviewer-renata:reviewer"
_SEQ = iter(range(1, 10_000))


def _ev(from_lane: Lane, to_lane: Lane, actor: object, *, wp: str = "WP01", review_ref: str | None = None) -> StatusEvent:
    n = next(_SEQ)
    return StatusEvent(
        event_id=f"01HZ{n:022d}",
        mission_slug="rework-fixture-01M3MQZZ",
        wp_id=wp,
        from_lane=from_lane,
        to_lane=to_lane,
        at=f"2026-01-01T00:00:{n % 60:02d}+00:00",
        actor=cast(ActorField, actor),
        force=False,
        execution_mode="worktree",
        review_ref=review_ref,
    )


def test_plain_implementer_claim_is_counted() -> None:
    events = [_ev(Lane.PLANNED, Lane.CLAIMED, IMPL)]
    assert latest_implementer_actor(events, "WP01") == IMPL


def test_reviewer_rework_rejection_with_review_ref_is_skipped() -> None:
    events = [
        _ev(Lane.PLANNED, Lane.CLAIMED, IMPL),
        _ev(Lane.CLAIMED, Lane.IN_PROGRESS, IMPL),
        _ev(Lane.IN_REVIEW, Lane.IN_PROGRESS, REVW, review_ref="review-cycle-1.md"),
    ]
    assert latest_implementer_actor(events, "WP01") == IMPL


def test_legacy_review_claim_for_review_to_in_progress_is_skipped() -> None:
    events = [
        _ev(Lane.PLANNED, Lane.CLAIMED, IMPL),
        _ev(Lane.FOR_REVIEW, Lane.IN_PROGRESS, REVW, review_ref="action-review-claim"),
    ]
    assert latest_implementer_actor(events, "WP01") == IMPL


def test_action_implement_takeover_without_review_ref_is_counted() -> None:
    events = [
        _ev(Lane.PLANNED, Lane.CLAIMED, IMPL),
        _ev(Lane.IN_REVIEW, Lane.IN_PROGRESS, "gemini:2.5-pro:python-pedro:implementer"),
    ]
    assert latest_implementer_actor(events, "WP01") == "gemini:2.5-pro:python-pedro:implementer"


def test_forced_planned_claim_with_copied_review_ref_is_counted() -> None:
    events = [
        _ev(Lane.PLANNED, Lane.CLAIMED, "gemini:2.5-pro:python-pedro:implementer"),
        _ev(Lane.PLANNED, Lane.CLAIMED, IMPL, review_ref="review-cycle-1.md"),
    ]
    assert latest_implementer_actor(events, "WP01") == IMPL


@pytest.mark.parametrize("generic", ["user", "implement-command", "unknown"])
def test_generic_actors_are_skipped(generic: str) -> None:
    events = [_ev(Lane.PLANNED, Lane.CLAIMED, IMPL), _ev(Lane.CLAIMED, Lane.IN_PROGRESS, generic)]
    assert latest_implementer_actor(events, "WP01") == IMPL


def test_no_qualifying_event_returns_none() -> None:
    events = [
        _ev(Lane.GENESIS, Lane.PLANNED, "fixture"),
        _ev(Lane.IN_PROGRESS, Lane.FOR_REVIEW, IMPL),
        _ev(Lane.FOR_REVIEW, Lane.IN_REVIEW, REVW),
    ]
    assert latest_implementer_actor(events, "WP01") is None
    assert latest_implementer_actor([], "WP01") is None


def test_other_wps_events_are_ignored() -> None:
    events = [_ev(Lane.PLANNED, Lane.CLAIMED, IMPL), _ev(Lane.PLANNED, Lane.CLAIMED, REVW, wp="WP02")]
    assert latest_implementer_actor(events, "WP01") == IMPL


def test_dict_shaped_actor_is_returned_and_projects_through_actor_key() -> None:
    actor = {"tool": "codex", "model": "gpt-5", "profile": "python-pedro", "role": "implementer"}
    result = latest_implementer_actor([_ev(Lane.PLANNED, Lane.CLAIMED, actor)], "WP01")
    assert result == "codex"
    assert _actor_key(result) == _actor_key(actor) == "codex"
