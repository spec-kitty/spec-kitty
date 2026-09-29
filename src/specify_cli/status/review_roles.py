"""Pure latest-implementer projection for the move-task ownership guard.

Mission ``rework-is-not-an-override`` (#5196). The ownership guard compares the
slot occupant's *tool* with the requester's. After a review rejection the slot
holds the reviewer, so the implementer's ordinary rework resume (and the
reviewer's next claim) looked like an ownership conflict. The guard resolves
"who is the WP's latest implementer" from this projection instead of the slot.

This is a pure leaf: it performs no I/O and reads only the events it is given
(precedent: :mod:`specify_cli.status.review_claim_predicate`). Contract:
``kitty-specs/rework-is-not-an-override-01M3MQV6/contracts/ownership-role-allowance.md``.
"""

from __future__ import annotations

from collections.abc import Sequence

from specify_cli.status.models import Lane, StatusEvent, actor_identity_str
from specify_cli.status.work_package_lifecycle import GENERIC_IMPLEMENTATION_ACTORS, _actor_key

__all__ = ["latest_implementer_actor"]

_IMPLEMENTING_LANES: frozenset[str] = frozenset({Lane.CLAIMED.value, Lane.IN_PROGRESS.value})
_REVIEWER_SOURCE_LANES: frozenset[str] = frozenset({Lane.FOR_REVIEW.value, Lane.IN_REVIEW.value, Lane.APPROVED.value})


def _is_reviewer_rework_verdict(event: StatusEvent) -> bool:
    """A reviewer rework verdict: leaves a review lane with a ``review_ref`` set.

    Sibling predicate — keep in lockstep: ``review.arbiter._is_rejection_event``
    encodes the same "a reviewer verdict happened" concept for the arbiter-override
    check and so uses a deliberately NARROWER lane set (``to == planned`` only,
    sources ``for_review``/``in_review``). A future change to "what counts as a
    reviewer verdict" must be weighed against both. (#5196)
    """
    return Lane(event.from_lane).value in _REVIEWER_SOURCE_LANES and bool(event.review_ref)


def _qualifies(event: StatusEvent) -> bool:
    if Lane(event.to_lane).value not in _IMPLEMENTING_LANES:
        return False
    if _is_reviewer_rework_verdict(event):
        return False
    return _actor_key(event.actor) not in GENERIC_IMPLEMENTATION_ACTORS


def latest_implementer_actor(events: Sequence[StatusEvent], wp_id: str) -> str | None:
    """Return the actor of ``wp_id``'s latest implementing claim, or ``None``.

    Scans newest-first for the first event into ``claimed``/``in_progress`` that
    is neither a reviewer rework verdict nor made by a generic placeholder actor.
    A string actor is returned as recorded; a dict-shaped resolved-binding actor
    is returned as its identity string (bare tool), which ``_actor_key`` accepts.
    """
    for event in reversed(events):
        if event.wp_id != wp_id or not _qualifies(event):
            continue
        actor = actor_identity_str(event.actor)
        return actor or None
    return None
