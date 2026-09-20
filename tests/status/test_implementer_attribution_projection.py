"""#4786 (WP04, T016/T018) — the read-root implementer-attribution projection.

Root cause: ``agent`` is a *live-claim* slot that legitimately changes hands
(implementer -> reviewer) and is correctly RELEASED on a review-rejection
rollback via the explicit ``release_runtime_claim`` annotation (#4673) — that
release must not be undone. But nothing else owned durable *implementer*
provenance once the live claim was released, so an ordinary
reject -> re-review -> approve cycle (no fresh ``--agent``) reported no owner
at all downstream (the accept gate, WP04 T015/T017 — see
``tests/acceptance/test_accept_gate_rejection_cycle.py``).

``reducer._project_implementer_attribution`` is a sibling of the existing
``reducer._project_cancellation_provenance``: a narrow, read-only, idempotent
projection over the immutable raw event stream that re-derives "who most
recently claimed this WP as implementer" from the ``planned -> claimed``
transition's ``policy_metadata['agent']`` sidecar — the ONLY transition that
ever writes the live ``agent`` runtime slot. The derived value lands on a
SEPARATE snapshot slot (``implementer_of_record``) the fold/release path
never touches.

This file also covers the companion T018 narrowing of
``status.doctor.check_blanked_runtime_slots``: a blank live ``agent`` slot
explained by a recoverable ``implementer_of_record`` is a
legitimately-released, historically-owned WP, not corrupt canonical state.
"""

from __future__ import annotations

import pytest

from specify_cli.status.doctor import Category, check_blanked_runtime_slots
from specify_cli.status.models import (
    InnerStateChanged,
    Lane,
    StatusEvent,
    WPInnerStateDelta,
)
from specify_cli.status.reducer import IMPLEMENTER_OF_RECORD_SLOT, reduce

pytestmark = [pytest.mark.fast]

_MISSION_SLUG = "canonical-state-recovery-4786"


def _ulid(suffix: str) -> str:
    return ("01M04" + suffix).ljust(26, "0")[:26]


def _claim_event(
    *,
    event_id: str,
    wp_id: str,
    at: str,
    agent: str,
    actor: str | None = None,
) -> StatusEvent:
    """A real ``planned -> claimed`` transition carrying the claimant sidecar."""
    return StatusEvent(
        event_id=event_id,
        mission_slug=_MISSION_SLUG,
        wp_id=wp_id,
        from_lane=Lane.PLANNED,
        to_lane=Lane.CLAIMED,
        at=at,
        actor=actor or agent,
        force=False,
        execution_mode="worktree",
        policy_metadata={"agent": agent},
    )


def _forward_event(*, event_id: str, wp_id: str, from_lane: Lane, to_lane: Lane, at: str, actor: str) -> StatusEvent:
    return StatusEvent(
        event_id=event_id,
        mission_slug=_MISSION_SLUG,
        wp_id=wp_id,
        from_lane=from_lane,
        to_lane=to_lane,
        at=at,
        actor=actor,
        force=False,
        execution_mode="worktree",
    )


def _release_annotation(*, event_id: str, wp_id: str, at: str, actor: str) -> InnerStateChanged:
    """The off-axis annotation ``move-task --to planned`` emits on rollback (#4673)."""
    return InnerStateChanged(
        event_id=event_id,
        wp_id=wp_id,
        at=at,
        actor=actor,
        delta=WPInnerStateDelta(release_runtime_claim=True),
    )


# ---------------------------------------------------------------------------
# T016 — the projection itself
# ---------------------------------------------------------------------------


def test_derives_implementer_of_record_for_a_claimed_wp() -> None:
    """A real ``planned -> claimed`` claim yields a derived implementer-of-record."""
    claim = _claim_event(event_id=_ulid("A1"), wp_id="WP01", at="2026-09-20T00:00:01+00:00", agent="impl-alice")
    snapshot = reduce([claim], [])
    assert snapshot.work_packages["WP01"][IMPLEMENTER_OF_RECORD_SLOT] == "impl-alice"


def test_never_owned_wp_yields_no_derived_slot() -> None:
    """A WP with no claim event at all yields NOTHING — never a fabricated owner."""
    seeded = _forward_event(
        event_id=_ulid("B1"),
        wp_id="WP02",
        from_lane=Lane.GENESIS,
        to_lane=Lane.PLANNED,
        at="2026-09-20T00:00:01+00:00",
        actor="operator",
    )
    snapshot = reduce([seeded], [])
    assert IMPLEMENTER_OF_RECORD_SLOT not in snapshot.work_packages["WP02"]


def test_derived_slot_survives_live_claim_release() -> None:
    """The live ``agent`` slot is released (#4673) but the derived slot persists.

    This is the exact shape of an ordinary reject -> re-review -> approve
    cycle: the claim triple is cleared off-axis by ``release_runtime_claim``,
    but the durable implementer-of-record fact must still be recoverable.
    """
    claim = _claim_event(event_id=_ulid("C1"), wp_id="WP03", at="2026-09-20T00:00:01+00:00", agent="impl-bob")
    release = _release_annotation(event_id=_ulid("C2"), wp_id="WP03", at="2026-09-20T00:00:05+00:00", actor="reviewer-carl")
    snapshot = reduce([claim], [release])
    wp = snapshot.work_packages["WP03"]
    assert wp.get("agent") is None  # the live claim slot is genuinely released
    assert wp[IMPLEMENTER_OF_RECORD_SLOT] == "impl-bob"  # but history is not lost


def test_latest_reclaim_wins_over_an_earlier_claim() -> None:
    """A genuine re-claim after rollback replaces the derived attribution (latest-wins)."""
    first_claim = _claim_event(event_id=_ulid("D1"), wp_id="WP04", at="2026-09-20T00:00:01+00:00", agent="impl-alice")
    release = _release_annotation(event_id=_ulid("D2"), wp_id="WP04", at="2026-09-20T00:00:05+00:00", actor="reviewer-carl")
    reclaim = _claim_event(event_id=_ulid("D3"), wp_id="WP04", at="2026-09-20T00:00:06+00:00", agent="impl-dana")
    snapshot = reduce([first_claim, reclaim], [release])
    assert snapshot.work_packages["WP04"][IMPLEMENTER_OF_RECORD_SLOT] == "impl-dana"


def test_projection_is_idempotent_and_read_only() -> None:
    """Reducing the same stream twice yields the identical derived slot (pure)."""
    claim = _claim_event(event_id=_ulid("E1"), wp_id="WP05", at="2026-09-20T00:00:01+00:00", agent="impl-eve")
    events = [claim]
    first = reduce(list(events), [])
    second = reduce(list(events), [])
    assert first.work_packages["WP05"][IMPLEMENTER_OF_RECORD_SLOT] == second.work_packages["WP05"][IMPLEMENTER_OF_RECORD_SLOT] == "impl-eve"
    # Read-only: re-deriving never mutates the source events.
    assert claim.policy_metadata == {"agent": "impl-eve"}


def test_claim_event_with_empty_agent_sidecar_derives_nothing() -> None:
    """An empty ``agent`` claim sidecar is a no-op — never a blank derived owner."""
    claim = _claim_event(event_id=_ulid("F1"), wp_id="WP06", at="2026-09-20T00:00:01+00:00", agent="")
    snapshot = reduce([claim], [])
    assert IMPLEMENTER_OF_RECORD_SLOT not in snapshot.work_packages["WP06"]


# ---------------------------------------------------------------------------
# T018 — doctor.check_blanked_runtime_slots narrowing
# ---------------------------------------------------------------------------


def test_blanked_agent_with_recoverable_history_is_not_flagged() -> None:
    """A blank ``agent`` explained by ``implementer_of_record`` is not corrupt."""
    snapshot = {
        "work_packages": {
            "WP01": {
                "lane": str(Lane.FOR_REVIEW),
                "agent": "",
                IMPLEMENTER_OF_RECORD_SLOT: "impl-alice",
            },
        }
    }
    assert check_blanked_runtime_slots(snapshot) == []


def test_blanked_agent_without_recoverable_history_is_still_flagged() -> None:
    """A blank ``agent`` with NO derivable claim history is still genuine corruption."""
    snapshot = {
        "work_packages": {
            "WP01": {"lane": str(Lane.FOR_REVIEW), "agent": ""},
        }
    }
    findings = check_blanked_runtime_slots(snapshot)
    assert len(findings) == 1
    assert findings[0].category == Category.BLANKED_RUNTIME_SLOT
    assert "spec-kitty doctor mission-state --fix --mission" in findings[0].recommended_action


def test_other_blank_scalar_slots_are_unaffected_by_the_narrowing() -> None:
    """The narrowing is scoped to ``agent`` alone — an unrelated blank slot still flags."""
    snapshot = {
        "work_packages": {
            "WP01": {
                "lane": str(Lane.IN_PROGRESS),
                "assignee": "",
                IMPLEMENTER_OF_RECORD_SLOT: "impl-alice",
            },
        }
    }
    findings = check_blanked_runtime_slots(snapshot)
    assert len(findings) == 1
    assert findings[0].message.startswith("WP01 runtime slot 'assignee'")
