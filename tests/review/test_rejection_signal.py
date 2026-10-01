"""Unit tests for the documented-review-rejection predicate (#2267)."""

from __future__ import annotations

import pytest

from specify_cli.review.rejection_signal import (
    is_backward_rework_move,
    is_documented_review_rejection,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_REF = "review-cycle://mission/WP01/review-cycle-1.md"


@pytest.mark.parametrize(
    "event",
    [
        {"review_ref": _REF},
        {"review_ref": "feedback://legacy/WP01.md"},
        {"evidence": {"review": {"reference": _REF, "verdict": "changes_requested"}}},
        {"evidence": "reviewer notes inline"},
    ],
)
def test_documented_feedback_is_recognised(event: dict) -> None:
    assert is_documented_review_rejection({"from_lane": "in_review", "to_lane": "planned", **event}) is True


@pytest.mark.parametrize(
    "event",
    [
        {},
        {"review_ref": ""},
        {"review_ref": "   "},
        {"review_ref": "force-override"},
        {"review_ref": "action-review-claim"},
        {"review_ref": "workflow-review-claim"},
        {"review_ref": "review:WP01"},
        {"review_ref": "approval:WP01"},
        {"evidence": {"review": {"reference": _REF, "verdict": "approved"}}},
        {"evidence": {"review": {"reference": "force-override", "verdict": "changes_requested"}}},
        {"evidence": {"note": "no review section"}},
        {"evidence": "  "},
    ],
)
def test_markers_and_approvals_are_not_feedback(event: dict) -> None:
    assert is_documented_review_rejection({"from_lane": "in_review", "to_lane": "planned", **event}) is False


@pytest.mark.parametrize(
    ("from_lane", "to_lane"),
    [
        ("for_review", "planned"),
        ("for_review", "in_progress"),
        ("in_review", "planned"),
        ("in_review", "claimed"),
        ("in_progress", "planned"),
        ("approved", "planned"),
        ("done", "in_progress"),
    ],
)
def test_backward_rework_moves(from_lane: str, to_lane: str) -> None:
    event = {"from_lane": from_lane, "to_lane": to_lane, "review_ref": _REF}
    assert is_backward_rework_move(event) is True
    assert is_documented_review_rejection(event) is True


@pytest.mark.parametrize(
    ("from_lane", "to_lane"),
    [
        ("planned", "in_progress"),
        ("in_progress", "for_review"),
        ("in_review", "approved"),
        ("blocked", "planned"),
        ("in_progress", "in_progress"),
    ],
)
def test_forward_and_lateral_moves_are_not_rejections(from_lane: str, to_lane: str) -> None:
    event = {"from_lane": from_lane, "to_lane": to_lane, "review_ref": _REF}
    assert is_backward_rework_move(event) is False
    assert is_documented_review_rejection(event) is False


def test_backward_move_without_feedback_is_not_a_rejection() -> None:
    event = {"from_lane": "for_review", "to_lane": "planned", "force": True, "review_ref": "force-override"}
    assert is_backward_rework_move(event) is True
    assert is_documented_review_rejection(event) is False
