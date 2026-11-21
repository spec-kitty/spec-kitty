"""The repair the accept gate may print, derived from the state machine (#5781).

``review_roles.implementer_claim_target`` names the implementing lane a work package can be
claimed into from its current lane, or ``None``; and a claim by a generic placeholder actor
names no implementer of record, so such a work package keeps the missing-implementer issue.
"""

from __future__ import annotations

import pytest

from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.review_roles import implementer_claim_target, implementer_release_target, latest_implementer_identity

pytestmark = pytest.mark.fast

_EXPECTED = {
    "planned": Lane.CLAIMED,
    "claimed": Lane.IN_PROGRESS,
    "blocked": Lane.IN_PROGRESS,
    "in_progress": None,
    "for_review": None,
    "in_review": None,
    "approved": None,
    "done": None,
    "canceled": None,
    "genesis": None,
}


@pytest.mark.parametrize(("lane", "expected"), sorted(_EXPECTED.items()))
def test_each_lane_names_only_a_claim_the_state_machine_allows(lane: str, expected: Lane | None) -> None:
    assert implementer_claim_target(lane) == expected


def test_the_doing_alias_resolves_to_in_progress() -> None:
    assert implementer_claim_target("doing") is None
    assert implementer_claim_target("doing") == implementer_claim_target(Lane.IN_PROGRESS)


def test_an_unknown_lane_offers_no_repair_instead_of_raising() -> None:
    assert implementer_claim_target("not-a-lane") is None


def _claim(actor: str) -> list[StatusEvent]:
    def hop(n: int, frm: str, to: str) -> StatusEvent:
        return StatusEvent(
            event_id=f"01JTARGET00000000000000{n:03d}",
            mission_slug="m",
            wp_id="WP01",
            from_lane=Lane(frm),
            to_lane=Lane(to),
            at=f"2026-11-20T00:00:0{n}+00:00",
            actor=actor,
            force=False,
            execution_mode="worktree",
        )

    return [hop(1, "planned", "claimed"), hop(2, "claimed", "in_progress")]


@pytest.mark.parametrize("generic", ["user", "implement-command"])
def test_a_claim_by_a_generic_actor_names_no_implementer(generic: str) -> None:
    """An API or host claim by a placeholder actor (e.g. ``start-implementation --actor user``)."""
    assert latest_implementer_identity(_claim(generic), "WP01") is None


def test_a_claim_by_a_real_actor_names_it() -> None:
    assert latest_implementer_identity(_claim("claude"), "WP01") == "claude::"


@pytest.mark.parametrize("lane", sorted(_EXPECTED))
def test_only_in_progress_is_released_to_planned_for_a_new_claim(lane: str) -> None:
    """in_progress -> planned needs only a reason; review lanes leave by a verdict, terminal ones not at all."""
    expected = Lane.PLANNED if lane == "in_progress" else None
    assert implementer_release_target(lane) == expected


def test_release_target_tolerates_aliases_and_unknown_lanes() -> None:
    assert implementer_release_target("doing") == Lane.PLANNED
    assert implementer_release_target("not-a-lane") is None
