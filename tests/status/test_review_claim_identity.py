"""Unit tests for the review-claimant fact and review identity equality (#7569, #7573)."""

from __future__ import annotations

import pytest

from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.review_roles import latest_review_claim_identity, same_review_identity

pytestmark = [pytest.mark.fast, pytest.mark.unit]

_RENATA = "claude:sonnet:reviewer-renata"


def _event(n: int, to_lane: Lane, actor: object, *, force: bool = False, wp_id: str = "WP01", from_lane: Lane = Lane.FOR_REVIEW) -> StatusEvent:
    return StatusEvent(
        event_id=f"evt-{n:02d}",
        mission_slug="m",
        wp_id=wp_id,
        from_lane=from_lane,
        to_lane=to_lane,
        at=f"2026-01-01T00:00:{n:02d}+00:00",
        actor=actor,
        force=force,
        execution_mode="worktree",
    )


def test_unforced_claim_is_the_claimant() -> None:
    assert latest_review_claim_identity([_event(1, Lane.IN_REVIEW, _RENATA)], "WP01") == _RENATA


def test_structured_claim_actor_is_returned_in_compact_form() -> None:
    actor = {"tool": "claude", "model": "sonnet", "profile": "reviewer-renata", "role": "reviewer"}
    assert latest_review_claim_identity([_event(1, Lane.IN_REVIEW, actor)], "WP01") == _RENATA


@pytest.mark.parametrize(
    ("actor", "force"),
    [
        (_RENATA, True),
        ("migration:backfill", False),
        ("user", False),
    ],
    ids=["forced", "migration", "placeholder"],
)
def test_non_claim_entry_has_no_claimant(actor: str, force: bool) -> None:
    assert latest_review_claim_identity([_event(1, Lane.IN_REVIEW, actor, force=force)], "WP01") is None


def test_newest_claim_wins() -> None:
    events = [
        _event(1, Lane.IN_REVIEW, "codex::reviewer-ralph"),
        _event(2, Lane.PLANNED, "codex::reviewer-ralph", from_lane=Lane.IN_REVIEW),
        _event(3, Lane.IN_REVIEW, _RENATA),
        _event(4, Lane.APPROVED, _RENATA, from_lane=Lane.IN_REVIEW),
    ]
    assert latest_review_claim_identity(events, "WP01") == _RENATA


def test_newest_entry_that_is_no_claim_never_reaches_back() -> None:
    events = [_event(1, Lane.IN_REVIEW, _RENATA), _event(2, Lane.IN_REVIEW, "user", force=True)]
    assert latest_review_claim_identity(events, "WP01") is None


def test_other_work_packages_and_no_entry_are_ignored() -> None:
    assert latest_review_claim_identity([_event(1, Lane.IN_REVIEW, _RENATA, wp_id="WP02")], "WP01") is None
    assert latest_review_claim_identity([], "WP01") is None


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        (_RENATA, _RENATA, True),
        (_RENATA, "claude:sonnet:reviewer-renata:reviewer", True),
        ("claude", "claude", True),
        ("claude", _RENATA, False),
        (_RENATA, "claude", False),
        (_RENATA, "claude:sonnet:reviewer-ralph", False),
        (_RENATA, "claude:opus:reviewer-renata", False),
        (_RENATA, "codex:sonnet:reviewer-renata", False),
        ("claude::reviewer-renata", _RENATA, False),
        (None, _RENATA, False),
        (_RENATA, "", False),
        (None, None, False),
    ],
    ids=[
        "same-full-identity",
        "role-only-difference",
        "same-bare-tool",
        "bare-tool-vs-profiled",
        "profiled-vs-bare-tool",
        "different-profile",
        "different-model",
        "different-tool",
        "model-on-one-side-only",
        "none-left",
        "blank-right",
        "both-none",
    ],
)
def test_same_review_identity_truth_table(left: str | None, right: str | None, expected: bool) -> None:
    assert same_review_identity(left, right) is expected
