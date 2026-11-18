"""#7712: the implementer of record survives a profile-less claim and a forced rewind.

Replays WP03 of open-packs Mission ``enforcement-vocabulary-01M7PMJW``: a bare ``claude``
claim, a forced ``in_review -> for_review`` re-submission carrying the implementer's
profile, and a forced ``for_review -> in_progress`` rewind. The implementer of record is
the claim, refined (fill-only, #7159) by the re-submission; a forced hop into an
implementing lane refines it under the same rule and never replaces it, and an identity
that cannot refine it is still an implementer an approval must be independent of.
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
CARLA_AS_REVIEWER = _actor("claude", "curator-carla", "reviewer")  # role stamped by role_for_hop
CARLA = _actor("claude", "curator-carla", "implementer")
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
    """06:44:25: the forced ``in_review -> for_review`` re-submission with the implementer's profile."""
    return [*_wp03_until_review(), _ev(Lane.IN_REVIEW, Lane.FOR_REVIEW, CARLA_AS_REVIEWER, force=True, review_ref="force-override")]


def test_wp03_resubmission_out_of_in_review_completes_the_bare_claim() -> None:
    """Gap 2: the re-submission's profile is no longer dropped; no forced rewind is needed."""
    assert latest_implementer_identity(_resubmitted(), "WP03") == "claude::curator-carla"


def test_wp03_reviewer_under_another_profile_is_independent_after_the_resubmission() -> None:
    events = [*_resubmitted(), _ev(Lane.FOR_REVIEW, Lane.IN_REVIEW, RENATA)]
    assert independent_of_implementers(implementer_identities(events, "WP03"), actor_full_identity(RENATA))


def test_wp03_full_recorded_sequence_resolves_to_carla() -> None:
    """The log as recorded, forced rewind and fresh submission included."""
    events = [
        *_resubmitted(),
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
        _ev(Lane.IN_REVIEW, Lane.FOR_REVIEW, CARLA_AS_REVIEWER, force=True),
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


def test_a_forced_rewind_by_the_claims_own_agent_refines_it() -> None:
    events = [
        *_wp03_until_review(),
        _ev(Lane.IN_REVIEW, Lane.IN_PROGRESS, CARLA, force=True, review_ref="force-override"),
    ]
    assert implementer_identities(events, "WP03") == ("claude::curator-carla",)


def test_an_unforced_claim_still_replaces_the_implementer_of_record() -> None:
    """The explicit, recorded takeover: an unforced claim (e.g. ``agent action implement``) is a new claim."""
    events = [
        _ev(Lane.PLANNED, Lane.CLAIMED, _actor("claude", "python-pedro", "implementer")),
        _ev(Lane.IN_REVIEW, Lane.IN_PROGRESS, _actor("gemini", "python-pedro", "implementer")),
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
