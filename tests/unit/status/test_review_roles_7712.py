"""#7712: the implementer of record survives a profile-less claim and a forced rewind.

Replays WP03 of open-packs Mission ``enforcement-vocabulary-01M7PMJW``: a bare ``claude``
claim, a forced ``in_review -> for_review`` re-submission carrying the implementer's
profile, and a forced ``for_review -> in_progress`` rewind. The implementer of record is
the claim, refined (fill-only, #7159) by a re-submission the implementer records as its own
act (``move-task --as-implementer``: role ``implementer``). A reviewer's ordinary hand-back
(role ``reviewer``) fills nothing. A forced claim, or another identity's claim, never changes
the implementer of record: it is kept beside it, and an approval must be independent of both.
"""

from __future__ import annotations

from typing import cast

import pytest

from specify_cli.status import actor_full_identity
from specify_cli.status.models import ActorField, Lane, StatusEvent
from specify_cli.status.review_roles import (
    implementer_identities,
    independent_of_implementers,
    latest_implementer_identity,
    profileless_claim_warning,
)

pytestmark = pytest.mark.unit

_SEQ = iter(range(1, 10_000))


def _actor(tool: str, profile: str | None, role: str) -> dict[str, str | None]:
    return {"tool": tool, "model": None, "profile": profile, "role": role}


def _ev(
    from_lane: Lane,
    to_lane: Lane,
    actor: object,
    *,
    force: bool = False,
    review_ref: str | None = None,
    wp: str = "WP03",
) -> StatusEvent:
    n = next(_SEQ)
    return StatusEvent(
        event_id=f"01M7{n:022d}",
        mission_slug="enforcement-vocabulary-01M7PMJW",
        wp_id=wp,
        from_lane=from_lane,
        to_lane=to_lane,
        at=f"2026-11-18T06:{n % 60:02d}:00+00:00",
        actor=cast(ActorField, actor),
        force=force,
        execution_mode="direct_repo",
        review_ref=review_ref,
    )


BARE_IMPL = _actor("claude", None, "implementer")
BARE_REVIEW = _actor("claude", None, "reviewer")
CARLA_AS_REVIEWER = _actor("claude", "curator-carla", "reviewer")  # role stamped by role_for_hop, as recorded at 06:44:25
CARLA = _actor("claude", "curator-carla", "implementer")  # --as-implementer records this role
RENATA = _actor("claude", "reviewer-renata", "reviewer")


def _wp03_until_review() -> list[StatusEvent]:
    """06:29:45 claim, 06:31:25 submission, 06:40:03 review claim -- all recorded as bare ``claude``."""
    return [
        _ev(Lane.PLANNED, Lane.CLAIMED, BARE_IMPL),
        _ev(Lane.CLAIMED, Lane.IN_PROGRESS, BARE_IMPL),
        _ev(Lane.IN_PROGRESS, Lane.FOR_REVIEW, BARE_IMPL),
        _ev(Lane.FOR_REVIEW, Lane.IN_REVIEW, BARE_REVIEW),
    ]


def _resubmitted() -> list[StatusEvent]:
    """06:44:25 as ``move-task --to for_review --force --as-implementer --agent claude::curator-carla`` records it."""
    return [*_wp03_until_review(), _ev(Lane.IN_REVIEW, Lane.FOR_REVIEW, CARLA, force=True)]


def test_wp03_resubmission_out_of_in_review_completes_the_bare_claim() -> None:
    """Gap 2: the implementer's re-submission completes the claim; no forced rewind is needed."""
    assert latest_implementer_identity(_resubmitted(), "WP03") == "claude::curator-carla"


def test_wp03_resubmission_recorded_as_a_reviewer_hand_back_fills_nothing() -> None:
    """The 06:44:25 event as recorded (role ``reviewer``) cannot be told apart from a reviewer handing back."""
    events = [*_wp03_until_review(), _ev(Lane.IN_REVIEW, Lane.FOR_REVIEW, CARLA_AS_REVIEWER, force=True)]
    assert latest_implementer_identity(events, "WP03") == "claude::"


@pytest.mark.parametrize(
    ("claim", "hand_back", "approver"),
    [
        ("claude", "claude:opus:reviewer-renata", "claude:sonnet:implementer-ivan"),  # S1
        ("claude::implementer-ivan", "claude:opus:implementer-ivan", "claude:sonnet:implementer-ivan"),  # S7
    ],
)
def test_a_reviewer_hand_back_never_makes_the_implementer_look_independent(claim: str, hand_back: str, approver: str) -> None:
    """Squad finding: filling a bare claim from the reviewer's hand-back invents independence evidence."""
    reviewer = {"tool": "claude", "model": hand_back.split(":")[1], "profile": hand_back.split(":")[2], "role": "reviewer"}
    events = [
        _ev(Lane.PLANNED, Lane.CLAIMED, claim),
        _ev(Lane.CLAIMED, Lane.IN_PROGRESS, claim),
        _ev(Lane.IN_PROGRESS, Lane.FOR_REVIEW, claim),
        _ev(Lane.FOR_REVIEW, Lane.IN_REVIEW, reviewer),
        _ev(Lane.IN_REVIEW, Lane.FOR_REVIEW, reviewer, force=True),
    ]
    assert not independent_of_implementers(implementer_identities(events, "WP03"), approver)


def test_wp03_reviewer_under_another_profile_is_independent_after_the_resubmission() -> None:
    events = [*_resubmitted(), _ev(Lane.FOR_REVIEW, Lane.IN_REVIEW, RENATA)]
    assert independent_of_implementers(implementer_identities(events, "WP03"), actor_full_identity(RENATA))


def test_wp03_full_recorded_sequence_resolves_to_carla() -> None:
    """The log as recorded: the forced rewind is kept beside the claim, the unforced submission completes it."""
    events = [
        *_wp03_until_review(),
        _ev(Lane.IN_REVIEW, Lane.FOR_REVIEW, CARLA_AS_REVIEWER, force=True, review_ref="force-override"),
        _ev(Lane.FOR_REVIEW, Lane.IN_PROGRESS, CARLA, force=True, review_ref="force-override"),
        _ev(Lane.IN_PROGRESS, Lane.FOR_REVIEW, CARLA),
        _ev(Lane.FOR_REVIEW, Lane.IN_REVIEW, RENATA),
    ]
    assert latest_implementer_identity(events, "WP03") == "claude::curator-carla"
    assert implementer_identities(events, "WP03") == ("claude::curator-carla",)
    assert independent_of_implementers(implementer_identities(events, "WP03"), actor_full_identity(RENATA))


def test_a_bare_claim_is_still_not_independent_of_a_same_tool_reviewer() -> None:
    """Non-goal guard: without the re-submission, one-sided segments still prove nothing (R1)."""
    events = [*_wp03_until_review(), _ev(Lane.FOR_REVIEW, Lane.IN_REVIEW, RENATA)]
    assert not independent_of_implementers(implementer_identities(events, "WP03"), actor_full_identity(RENATA))


def test_a_contradicting_resubmission_out_of_in_review_never_changes_the_claim() -> None:
    claim = _actor("claude", "python-pedro", "implementer")
    events = [
        _ev(Lane.PLANNED, Lane.CLAIMED, claim),
        _ev(Lane.IN_PROGRESS, Lane.FOR_REVIEW, claim),
        _ev(Lane.IN_REVIEW, Lane.FOR_REVIEW, CARLA, force=True),
    ]
    assert latest_implementer_identity(events, "WP03") == "claude::python-pedro"


# --- Gap 3: a forced hop into an implementing lane refines, never replaces ---------------


def test_a_third_identitys_forced_rewind_does_not_become_the_implementer_of_record() -> None:
    claim = _actor("claude", "python-pedro", "implementer")
    intruder = _actor("codex", "operator-olga", "implementer")
    events = [
        _ev(Lane.PLANNED, Lane.CLAIMED, claim),
        _ev(Lane.CLAIMED, Lane.IN_PROGRESS, claim),
        _ev(Lane.IN_PROGRESS, Lane.FOR_REVIEW, claim),
        _ev(Lane.FOR_REVIEW, Lane.IN_PROGRESS, intruder, force=True, review_ref="force-override"),
    ]
    assert latest_implementer_identity(events, "WP03") == "claude::python-pedro"
    # The original implementer still cannot approve its own work...
    identities = implementer_identities(events, "WP03")
    assert not independent_of_implementers(identities, "claude::python-pedro")
    # ...and the re-opener, who may have reworked it, cannot approve it either (#6955).
    assert not independent_of_implementers(identities, actor_full_identity(intruder))
    assert independent_of_implementers(identities, "gemini::reviewer-renata")


def test_a_forced_same_tool_rewind_with_another_profile_does_not_replace_the_claim() -> None:
    claim = _actor("claude", "python-pedro", "implementer")
    events = [
        _ev(Lane.PLANNED, Lane.CLAIMED, claim),
        _ev(Lane.APPROVED, Lane.IN_PROGRESS, RENATA, force=True, review_ref="force-override"),
    ]
    assert latest_implementer_identity(events, "WP03") == "claude::python-pedro"
    assert implementer_identities(events, "WP03") == ("claude::python-pedro", "claude::reviewer-renata")


def test_a_forced_rewind_that_agrees_with_a_bare_claim_is_kept_beside_it() -> None:
    """S4: a forced rewind by a same-tool reviewer never fills the claim, so the bare implementer stays unproven."""
    events = [
        *_wp03_until_review(),
        _ev(Lane.IN_REVIEW, Lane.IN_PROGRESS, RENATA, force=True, review_ref="force-override"),
    ]
    assert implementer_identities(events, "WP03") == ("claude::", "claude::reviewer-renata")
    assert not independent_of_implementers(implementer_identities(events, "WP03"), "claude:sonnet:implementer-ivan")


def test_the_claims_own_unforced_hop_refines_it() -> None:
    events = [_ev(Lane.PLANNED, Lane.CLAIMED, BARE_IMPL), _ev(Lane.CLAIMED, Lane.IN_PROGRESS, CARLA)]
    assert implementer_identities(events, "WP03") == ("claude::curator-carla",)


def test_an_unforced_takeover_is_kept_beside_the_implementer_of_record() -> None:
    """``agent action implement`` by another agent out of review: both implemented the work package."""
    events = [
        _ev(Lane.PLANNED, Lane.CLAIMED, _actor("claude", "python-pedro", "implementer")),
        _ev(Lane.IN_REVIEW, Lane.IN_PROGRESS, _actor("gemini", "python-pedro", "implementer")),
    ]
    assert implementer_identities(events, "WP03") == ("claude::python-pedro", "gemini::python-pedro")


@pytest.mark.parametrize("unblocker", ["X", "A"])
def test_an_unforced_unblock_does_not_wipe_the_forced_reopener(unblocker: str) -> None:
    """S2 / S2b: a forced reopen then an unforced ``blocked -> in_progress`` keeps both implementers."""
    a = _actor("claude", "python-pedro", "implementer")
    x = _actor("codex", "operator-olga", "implementer")
    events = [
        _ev(Lane.PLANNED, Lane.CLAIMED, a),
        _ev(Lane.CLAIMED, Lane.IN_PROGRESS, a),
        _ev(Lane.APPROVED, Lane.IN_PROGRESS, x, force=True, review_ref="force-override"),
        _ev(Lane.IN_PROGRESS, Lane.BLOCKED, x),
        _ev(Lane.BLOCKED, Lane.IN_PROGRESS, x if unblocker == "X" else a),
    ]
    identities = implementer_identities(events, "WP03")
    assert not independent_of_implementers(identities, "claude::python-pedro")
    assert not independent_of_implementers(identities, "codex::operator-olga")


def test_a_fresh_planned_claim_starts_a_new_cycle() -> None:
    events = [
        _ev(Lane.PLANNED, Lane.CLAIMED, _actor("claude", "python-pedro", "implementer")),
        _ev(Lane.APPROVED, Lane.IN_PROGRESS, _actor("codex", "operator-olga", "implementer"), force=True),
        _ev(Lane.IN_PROGRESS, Lane.PLANNED, _actor("codex", "operator-olga", "reviewer"), review_ref="review-cycle-2.md"),
        _ev(Lane.PLANNED, Lane.CLAIMED, _actor("gemini", "python-pedro", "implementer")),
    ]
    assert implementer_identities(events, "WP03") == ("gemini::python-pedro",)


def test_a_forced_claim_with_no_earlier_claim_is_the_implementer() -> None:
    events = [_ev(Lane.PLANNED, Lane.CLAIMED, CARLA, force=True)]
    assert implementer_identities(events, "WP03") == ("claude::curator-carla",)


def test_no_implementer_is_independent_of_nothing() -> None:
    assert implementer_identities([], "WP03") == ()
    assert not independent_of_implementers((), "claude::reviewer-renata")
    assert not independent_of_implementers(("claude::python-pedro",), None)


# --- Claim-time warning -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("actor", "warns"),
    [
        (BARE_IMPL, True),
        ("claude", True),
        (CARLA, False),
        ({"tool": "claude", "model": "claude-x", "profile": None, "role": "implementer"}, False),
        ("user", False),  # a placeholder names no implementer; nothing to complete
        ("migration:backfill_runtime_state", False),
    ],
)
def test_profileless_claim_warning(actor: object, warns: bool) -> None:
    warning = profileless_claim_warning(_ev(Lane.PLANNED, Lane.CLAIMED, actor))
    if not warns:
        assert warning is None
        return
    assert warning == (
        "Warning: WP03 was claimed as 'claude' with no profile or model recorded, so `spec-kitty accept` and "
        "`spec-kitty consolidate` will refuse an approval by another 'claude' identity with REVIEW_NOT_INDEPENDENT "
        "(SINGLE_BRANCH_REVIEW_NOT_INDEPENDENT on a single_branch Mission). Record your identity: claim with "
        "--agent claude:<model>:<profile> (or --profile <profile>), or submit with "
        "`spec-kitty agent tasks move-task WP03 --to for_review --agent claude::<profile>`."
    )


def test_no_claim_warning_for_a_non_claim_or_a_review_verdict() -> None:
    assert profileless_claim_warning(_ev(Lane.IN_PROGRESS, Lane.FOR_REVIEW, BARE_IMPL)) is None
    assert profileless_claim_warning(_ev(Lane.IN_REVIEW, Lane.IN_PROGRESS, BARE_REVIEW, review_ref="review-cycle-1.md")) is None
    assert profileless_claim_warning(None) is None
