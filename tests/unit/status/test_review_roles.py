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


def test_forced_approved_reopen_with_the_operator_sentinel_is_counted() -> None:
    """#6955: the operator-rewind sentinel is not a reviewer verdict.

    ``approved -> in_progress`` without feedback now records ``force-override``
    (the payload the pinned wire contract admits). Reading that marker as a
    reviewer verdict hid the re-opener from this projection, so their own later
    approval looked like an independent review.
    """
    reworker = "codex:gpt-5:implementer-ivan:implementer"
    events = [
        _ev(Lane.PLANNED, Lane.CLAIMED, IMPL),
        _ev(Lane.CLAIMED, Lane.IN_PROGRESS, IMPL),
        _ev(Lane.IN_PROGRESS, Lane.FOR_REVIEW, IMPL),
        _ev(Lane.FOR_REVIEW, Lane.IN_REVIEW, REVW),
        _ev(Lane.IN_REVIEW, Lane.APPROVED, REVW),
        _ev(Lane.APPROVED, Lane.IN_PROGRESS, reworker, review_ref="force-override"),
    ]
    assert latest_implementer_actor(events, "WP01") == reworker


def test_a_real_review_pointer_on_the_approved_reopen_is_still_a_reviewer_verdict() -> None:
    """Positive control: a resolvable pointer on the same edge stays a reviewer act."""
    events = [
        _ev(Lane.PLANNED, Lane.CLAIMED, IMPL),
        _ev(Lane.CLAIMED, Lane.IN_PROGRESS, IMPL),
        _ev(Lane.IN_REVIEW, Lane.APPROVED, REVW),
        _ev(Lane.APPROVED, Lane.IN_PROGRESS, REVW, review_ref="review-cycle://WP01/2"),
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


# ---------------------------------------------------------------------------
# #7159 (operator ruling): the implementer's own ``for_review`` submission refines
# the recorded claim identity. It fills segments the claim did not record and never
# contradicts one, so a reviewer or another actor never becomes implementer of record
# by submitting.
# ---------------------------------------------------------------------------


def _identity(events: list[StatusEvent]) -> str | None:
    from specify_cli.status import latest_implementer_identity

    return latest_implementer_identity(events, "WP01")


def _submitted(events: list[StatusEvent], actor: object) -> list[StatusEvent]:
    return [*events, _ev(Lane.IN_PROGRESS, Lane.FOR_REVIEW, actor)]


def _claimed(actor: object) -> list[StatusEvent]:
    return [_ev(Lane.PLANNED, Lane.CLAIMED, actor), _ev(Lane.CLAIMED, Lane.IN_PROGRESS, actor)]


def test_identity_is_the_claim_identity_without_a_submission() -> None:
    assert _identity(_claimed(IMPL)) == "claude:opus:implementer-ivan"


def test_identity_is_none_without_a_claim() -> None:
    assert _identity([_ev(Lane.IN_PROGRESS, Lane.FOR_REVIEW, IMPL)]) is None


def test_a_full_submission_refines_a_bare_claim() -> None:
    assert _identity(_submitted(_claimed("claude"), "claude:claude-opus-5-5:implementer-ivan")) == "claude:claude-opus-5-5:implementer-ivan"


def test_a_submission_fills_only_the_unrecorded_segment() -> None:
    claim = {"tool": "claude", "model": None, "profile": "python-pedro", "role": "implementer"}
    assert _identity(_submitted(_claimed(claim), "claude:claude-opus-5-5:python-pedro")) == "claude:claude-opus-5-5:python-pedro"


@pytest.mark.parametrize(
    "submitter",
    [
        "claude:claude-opus-5-5:reviewer-renata",  # a recorded profile differs
        "codex:gpt-5:python-pedro",  # another tool
    ],
)
def test_a_contradicting_submission_never_replaces_the_claim(submitter: str) -> None:
    claim = {"tool": "claude", "model": None, "profile": "python-pedro", "role": "implementer"}
    assert _identity(_submitted(_claimed(claim), submitter)) == "claude::python-pedro"


def test_a_submission_before_the_latest_claim_is_ignored() -> None:
    events = [*_submitted(_claimed("claude"), "claude:claude-opus-5-5:implementer-ivan"), *_claimed("claude")]
    assert _identity(events) == "claude::"


@pytest.mark.parametrize("actor", ["user", SEED, ""])
def test_a_placeholder_or_seed_submission_is_ignored(actor: str) -> None:
    assert _identity(_submitted(_claimed("claude"), actor)) == "claude::"


def test_a_reviewer_rework_verdict_does_not_refine_the_claim() -> None:
    events = [*_claimed("claude"), _ev(Lane.FOR_REVIEW, Lane.IN_PROGRESS, "claude:claude-sonnet-5-5:reviewer-renata", review_ref="review-cycle-1.md")]
    assert _identity(events) == "claude::"


def test_another_work_packages_submission_is_ignored() -> None:
    events = [*_claimed("claude"), _ev(Lane.IN_PROGRESS, Lane.FOR_REVIEW, "claude:claude-opus-5-5:implementer-ivan", wp="WP02")]
    assert _identity(events) == "claude::"


def test_a_forced_submission_is_ignored() -> None:
    from dataclasses import replace

    forced = replace(_ev(Lane.IN_PROGRESS, Lane.FOR_REVIEW, "claude:claude-opus-5-5:implementer-ivan"), force=True)
    assert _identity([*_claimed("claude"), forced]) == "claude::"


def test_a_move_into_for_review_from_another_lane_is_ignored() -> None:
    events = [*_claimed("claude"), _ev(Lane.IN_PROGRESS, Lane.BLOCKED, "claude"), _ev(Lane.BLOCKED, Lane.FOR_REVIEW, "claude:claude-opus-5-5:implementer-ivan")]
    assert _identity(events) == "claude::"


def test_a_planned_frontmatter_profile_never_fills_the_claim() -> None:
    planned = {"tool": "claude", "model": None, "profile": "implementer-ivan", "role": "implementer", "profile_source": "wp_frontmatter"}
    assert _identity(_submitted(_claimed("claude"), planned)) == "claude::"


def test_a_malformed_submission_never_fills_the_claim() -> None:
    assert _identity(_submitted(_claimed("claude"), "claude:m:p:r:extra")) == "claude::"
