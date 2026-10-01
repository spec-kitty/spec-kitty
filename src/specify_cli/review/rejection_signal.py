"""Documented review rejection: the one predicate every signal consumer reads (#2267).

A reviewer sends a work package back with ``move-task WP## --to planned
--force --review-feedback-file <path>``. The resulting status event moves the
WP backward and carries a ``review_ref`` pointing at the ``review-cycle-N.md``
artifact. Before this module the retrospective generator owned a private
predicate that only recognised rewinds out of ``in_review``/``approved``, and
consolidate's hollow-review check read the raw ``force_count``; one documented
rejection was reported as a guard bypass, a lane bounce and undocumented
rework.

A *documented review rejection* is a backward rework move (into ``planned``,
``claimed`` or ``in_progress`` from a later lane) that carries documented
review feedback. Feedback is documented when the event names a resolvable
review pointer: a ``review_ref`` or a changes-requested review evidence whose
reference is not an operational sentinel (``force-override``,
``action-review-claim``) or a synthetic marker (``review:<WP>``) -- those are
minted precisely when no feedback artifact exists.

Readers: ``retrospective.generator`` (rejection, lane-friction, force-override
and implementation-cycle detectors) and ``consolidation.preflight`` (the
hollow-review ``force_count`` discount).

Sibling predicates with deliberately different purposes, on typed
``StatusEvent`` objects: ``review.arbiter._is_rejection_event`` (arbiter
override history) and ``status.review_roles._is_reviewer_rework_verdict``
(latest-implementer projection). Weigh a change to "what counts as a reviewer
verdict" against both.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from specify_cli.review.cycle import is_non_resolvable_review_ref
from specify_cli.status import Lane, is_changes_requested

__all__ = [
    "BACKWARD_REWORK_MOVES",
    "has_documented_review_feedback",
    "is_backward_rework_move",
    "is_documented_review_rejection",
]

_REWORK_TARGETS = (Lane.PLANNED.value, Lane.CLAIMED.value, Lane.IN_PROGRESS.value)

#: Backward moves into an implementation lane. ``move-task --to <lane> --force``
#: can rewind from any lane, including terminal ``done`` (#3687), so every
#: rewind out of a later lane counts.
BACKWARD_REWORK_MOVES: frozenset[tuple[str, str]] = frozenset(
    {
        (source, target)
        for source, targets in (
            (Lane.FOR_REVIEW.value, _REWORK_TARGETS),
            (Lane.IN_REVIEW.value, _REWORK_TARGETS),
            (Lane.IN_PROGRESS.value, (Lane.PLANNED.value, Lane.CLAIMED.value)),
            (Lane.APPROVED.value, _REWORK_TARGETS),
            (Lane.DONE.value, _REWORK_TARGETS),
        )
        for target in targets
    }
)


def _is_documented_pointer(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and not is_non_resolvable_review_ref(value.strip())


def has_documented_review_feedback(event: Mapping[str, Any]) -> bool:
    """True when a lane event carries a resolvable review-feedback pointer."""
    if _is_documented_pointer(event.get("review_ref")):
        return True
    evidence = event.get("evidence")
    if isinstance(evidence, Mapping):
        review = evidence.get("review")
        if isinstance(review, Mapping):
            return _is_documented_pointer(review.get("reference")) and is_changes_requested(review.get("verdict"))
        return False
    return isinstance(evidence, str) and bool(evidence.strip())


def is_backward_rework_move(event: Mapping[str, Any]) -> bool:
    """True when the event moves a WP backward into an implementation lane."""
    return (event.get("from_lane", ""), event.get("to_lane", "")) in BACKWARD_REWORK_MOVES


def is_documented_review_rejection(event: Mapping[str, Any]) -> bool:
    """True when the event is a backward rework move carrying documented feedback."""
    return is_backward_rework_move(event) and has_documented_review_feedback(event)
