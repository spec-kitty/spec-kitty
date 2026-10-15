"""Truth-table tests for the pure latest-implementer projection (#5196)."""

from __future__ import annotations

from typing import cast

import pytest

from specify_cli.status import is_latest_implementer, latest_implementer_actor, latest_implementer_event
from specify_cli.status.models import ActorField, Lane, StatusEvent
from specify_cli.status.work_package_lifecycle import _actor_key

pytestmark = pytest.mark.unit

IMPL = "claude:opus:implementer-ivan:implementer"
REVW = "codex:gpt-5:reviewer-renata:reviewer"
SEED = "migration:backfill_runtime_state"
VERDICT_SEED = "migration:verdict_provenance_backfill"
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


@pytest.mark.parametrize("latest", [None, "", "implement-command", "user", "unknown"])
def test_is_latest_implementer_false_for_missing_or_generic_latest(latest: str | None) -> None:
    assert is_latest_implementer(latest, IMPL) is False
    # Even a requester that projects to the same generic key is not an implementer.
    assert is_latest_implementer(latest, latest or "user") is False


def test_is_latest_implementer_same_tool_compact_vs_dict_shaped() -> None:
    dict_actor = {"tool": "claude", "model": "opus", "profile": "implementer-ivan", "role": "implementer"}
    assert is_latest_implementer(IMPL, dict_actor) is True
    assert is_latest_implementer("claude", IMPL) is True
    assert is_latest_implementer(IMPL, IMPL) is True


def test_is_latest_implementer_false_for_a_different_tool() -> None:
    assert is_latest_implementer(IMPL, REVW) is False
    assert is_latest_implementer(IMPL, {"tool": "codex", "model": "gpt-5"}) is False


def test_is_latest_implementer_false_when_requester_projects_to_no_key() -> None:
    assert is_latest_implementer(IMPL, None) is False


def test_latest_implementer_event_returns_the_qualifying_event() -> None:
    claim = _ev(Lane.PLANNED, Lane.CLAIMED, IMPL)
    events = [claim, _ev(Lane.IN_REVIEW, Lane.IN_PROGRESS, REVW, review_ref="review-cycle-1.md")]
    assert latest_implementer_event(events, "WP01") is claim
    assert latest_implementer_event(events, "WP02") is None


def test_latest_implementer_event_skips_generic_and_migration_actors() -> None:
    claim = _ev(Lane.PLANNED, Lane.CLAIMED, IMPL)
    events = [
        claim,
        _ev(Lane.CLAIMED, Lane.IN_PROGRESS, "unknown"),
        _ev(Lane.CLAIMED, Lane.IN_PROGRESS, "implement-command"),
        _ev(Lane.PLANNED, Lane.CLAIMED, SEED),
    ]
    assert latest_implementer_event(events, "WP01") is claim


def test_latest_implementer_event_keeps_the_full_recorded_identity() -> None:
    other = "claude:opus:reviewer-renata:reviewer"
    event = latest_implementer_event([_ev(Lane.PLANNED, Lane.CLAIMED, IMPL)], "WP01")
    assert event is not None and event.actor == IMPL and event.actor != other


@pytest.mark.parametrize(
    ("actor", "expected"),
    [
        pytest.param({"tool": "claude", "model": "opus", "profile": "ivan", "role": "implementer"}, "claude:opus:ivan", id="dict-drops-role"),
        pytest.param("claude:opus:ivan:reviewer", "claude:opus:ivan", id="compact-drops-role"),
        pytest.param("claude", "claude::", id="bare-tool"),
        pytest.param({"tool": "claude", "role": "reviewer"}, "claude::", id="dict-tool-only"),
        pytest.param(":opus", ":opus", id="no-tool-segment-kept-as-recorded"),
        pytest.param({"role": "reviewer"}, None, id="role-only-dict"),
        pytest.param("  ", None, id="blank"),
        pytest.param(None, None, id="missing"),
    ],
)
def test_actor_full_identity_is_tool_model_profile(actor: object, expected: str | None) -> None:
    """#5340: one actor reduction for the hollow-review check; the role never splits one agent in two."""
    from specify_cli.status import actor_full_identity

    assert actor_full_identity(actor) == expected


@pytest.mark.regression
def test_latest_implementer_event_skips_an_appended_backfill_seed() -> None:
    """#6257: a ``migration:`` seed appended after the real claim is not the implementer of record."""
    first = _ev(Lane.PLANNED, Lane.CLAIMED, IMPL)
    latest_real = _ev(Lane.CLAIMED, Lane.IN_PROGRESS, IMPL)
    events = [first, latest_real, _ev(Lane.PLANNED, Lane.CLAIMED, SEED)]
    assert latest_implementer_event(events, "WP01") is latest_real
    assert latest_implementer_actor(events, "WP01") == IMPL


@pytest.mark.regression
def test_latest_implementer_event_skips_a_verdict_seed_into_in_progress() -> None:
    """#6257: the verdict-provenance seed leaves ``in_review`` with no ``review_ref``, so it is not a rework verdict.

    Control: the same real claim is returned when the seed is absent.
    """
    claim = _ev(Lane.PLANNED, Lane.CLAIMED, IMPL)
    assert latest_implementer_actor([claim], "WP01") == IMPL
    events = [claim, _ev(Lane.IN_REVIEW, Lane.IN_PROGRESS, VERDICT_SEED)]
    assert latest_implementer_event(events, "WP01") is claim
    assert latest_implementer_actor(events, "WP01") == IMPL


@pytest.mark.regression
@pytest.mark.parametrize("with_generic_claim", [False, True], ids=["seeds-only", "seeds-and-generic"])
def test_seeds_only_has_no_implementer(with_generic_claim: bool) -> None:
    """#6257 / US2-4: a WP whose only implementing events are seeds has no implementer of record (fails closed)."""
    events = [_ev(Lane.PLANNED, Lane.CLAIMED, SEED), _ev(Lane.IN_REVIEW, Lane.IN_PROGRESS, VERDICT_SEED)]
    if with_generic_claim:
        events.insert(1, _ev(Lane.CLAIMED, Lane.IN_PROGRESS, "user"))
    assert latest_implementer_event(events, "WP01") is None
    assert latest_implementer_actor(events, "WP01") is None


@pytest.mark.regression
def test_latest_implementer_event_skips_a_dict_seed_actor() -> None:
    """#6257: a structured actor whose identity string is ``migration:...`` is a seed too.

    Control: the same dict shape with a real tool name still qualifies.
    """
    dict_seed = {"tool": SEED, "model": None, "profile": None, "role": None}
    dict_real = {"tool": "codex", "model": "gpt-5", "profile": None, "role": "implementer"}
    claim = _ev(Lane.PLANNED, Lane.CLAIMED, IMPL)
    assert latest_implementer_event([claim, _ev(Lane.CLAIMED, Lane.IN_PROGRESS, dict_seed)], "WP01") is claim
    real_dict_event = _ev(Lane.CLAIMED, Lane.IN_PROGRESS, dict_real)
    assert latest_implementer_event([claim, real_dict_event], "WP01") is real_dict_event
