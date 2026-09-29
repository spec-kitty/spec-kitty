"""Regression tests for review/arbiter.py — WP05: Migrate Slice 3: Review & Tasks.

Tests verify that:
- _is_arbiter_override() uses typed Lane enum comparisons (not raw strings)
- Arbiter override detection logic is unchanged after migration
- All lane comparison scenarios work correctly with typed Lane enum
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.review.arbiter import (
    ArbiterCategory,
    ArbiterChecklist,
    ArbiterDecision,
    _is_arbiter_override,
    create_arbiter_decision,
    is_arbiter_override_history,
    parse_category_from_note,
)
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event


pytestmark = pytest.mark.fast


def _make_event(
    feature_dir: Path,
    wp_id: str,
    from_lane: Lane,
    to_lane: Lane,
    *,
    review_ref: str | None = None,
) -> StatusEvent:
    """Helper to create and append a StatusEvent."""
    event = StatusEvent(
        event_id=f"01TEST{wp_id}{from_lane}{to_lane}".replace("_", "")[:26].upper().ljust(26, "0"),
        mission_slug=feature_dir.name,
        wp_id=wp_id,
        from_lane=from_lane,
        to_lane=to_lane,
        at="2026-04-09T12:00:00+00:00",
        actor="test-actor",
        force=True,
        execution_mode="direct_repo",
        review_ref=review_ref,
    )
    append_event(feature_dir, event)
    return event


# ---------------------------------------------------------------------------
# Tests for _is_arbiter_override() using live arbiter function
# ---------------------------------------------------------------------------


def test_is_arbiter_override_returns_false_when_not_forced(tmp_path: Path) -> None:
    """force=False → no override, regardless of lane values."""
    feature_dir = tmp_path / "kitty-specs" / "080-test"
    feature_dir.mkdir(parents=True)
    _make_event(feature_dir, "WP01", Lane.FOR_REVIEW, Lane.PLANNED, review_ref="rev://ref/1")

    result = _is_arbiter_override(feature_dir, "WP01", "planned", "approved", force=False)

    assert result is False


def test_is_arbiter_override_returns_false_when_old_lane_not_planned(tmp_path: Path) -> None:
    """force=True but old_lane != planned → not an override."""
    feature_dir = tmp_path / "kitty-specs" / "080-test"
    feature_dir.mkdir(parents=True)
    _make_event(feature_dir, "WP01", Lane.FOR_REVIEW, Lane.PLANNED, review_ref="rev://ref/1")

    result = _is_arbiter_override(feature_dir, "WP01", "in_progress", "approved", force=True)

    assert result is False


def test_is_arbiter_override_returns_false_when_target_lane_invalid(tmp_path: Path) -> None:
    """force=True, old_lane=planned, but target_lane not in forward targets → not override."""
    feature_dir = tmp_path / "kitty-specs" / "080-test"
    feature_dir.mkdir(parents=True)
    _make_event(feature_dir, "WP01", Lane.FOR_REVIEW, Lane.PLANNED, review_ref="rev://ref/1")

    result = _is_arbiter_override(feature_dir, "WP01", "planned", "in_progress", force=True)

    assert result is False


def test_is_arbiter_override_returns_false_when_no_events(tmp_path: Path) -> None:
    """No events for WP → cannot be a rejection override."""
    feature_dir = tmp_path / "kitty-specs" / "080-test"
    feature_dir.mkdir(parents=True)

    result = _is_arbiter_override(feature_dir, "WP01", "planned", "approved", force=True)

    assert result is False


def test_is_arbiter_override_returns_false_when_latest_event_not_rejection(tmp_path: Path) -> None:
    """Latest event is not a rejection (for_review → planned with review_ref) → not override."""
    feature_dir = tmp_path / "kitty-specs" / "080-test"
    feature_dir.mkdir(parents=True)
    # Latest event: planned → claimed (not a rejection)
    _make_event(feature_dir, "WP01", Lane.PLANNED, Lane.CLAIMED)

    result = _is_arbiter_override(feature_dir, "WP01", "planned", "approved", force=True)

    assert result is False


def test_is_arbiter_override_false_for_forced_rework_to_for_review(tmp_path: Path) -> None:
    """Forced planned→for_review after a rejection is rework, not an override (#5196)."""
    feature_dir = tmp_path / "kitty-specs" / "080-test"
    feature_dir.mkdir(parents=True)
    _make_event(feature_dir, "WP01", Lane.FOR_REVIEW, Lane.PLANNED, review_ref="rev://ref/1")

    result = _is_arbiter_override(feature_dir, "WP01", "planned", "for_review", force=True)

    assert result is False  # re-pinned (#5196): was True; rework is not an override


def test_is_arbiter_override_false_for_forced_rework_to_claimed(tmp_path: Path) -> None:
    """Forced planned→claimed after a rejection is rework, not an override (#5196)."""
    feature_dir = tmp_path / "kitty-specs" / "080-test"
    feature_dir.mkdir(parents=True)
    _make_event(feature_dir, "WP01", Lane.FOR_REVIEW, Lane.PLANNED, review_ref="rev://ref/1")

    result = _is_arbiter_override(feature_dir, "WP01", "planned", "claimed", force=True)

    assert result is False  # re-pinned (#5196): was True; rework is not an override


def test_is_arbiter_override_valid_for_approved_target(tmp_path: Path) -> None:
    """Arbiter can override to 'approved' (a decision target)."""
    feature_dir = tmp_path / "kitty-specs" / "080-test"
    feature_dir.mkdir(parents=True)
    _make_event(feature_dir, "WP01", Lane.FOR_REVIEW, Lane.PLANNED, review_ref="rev://ref/1")

    result = _is_arbiter_override(feature_dir, "WP01", "planned", "approved", force=True)

    assert result is True


def test_is_arbiter_override_requires_review_ref_in_latest_event(tmp_path: Path) -> None:
    """for_review→planned transition without review_ref is NOT a rejection."""
    feature_dir = tmp_path / "kitty-specs" / "080-test"
    feature_dir.mkdir(parents=True)
    # for_review → planned but NO review_ref (unusual, not a rejection)
    _make_event(feature_dir, "WP01", Lane.FOR_REVIEW, Lane.PLANNED, review_ref=None)

    result = _is_arbiter_override(feature_dir, "WP01", "planned", "approved", force=True)

    assert result is False


def test_is_arbiter_override_uses_latest_event_only(tmp_path: Path) -> None:
    """Checks only the latest event, not the entire history."""
    feature_dir = tmp_path / "kitty-specs" / "080-test"
    feature_dir.mkdir(parents=True)
    # First: for_review → planned (rejection) with review_ref
    _make_event(feature_dir, "WP01", Lane.FOR_REVIEW, Lane.PLANNED, review_ref="rev://ref/1")
    # Then: planned → claimed (not a rejection, this is the latest)
    _make_event(feature_dir, "WP01", Lane.PLANNED, Lane.CLAIMED)

    result = _is_arbiter_override(feature_dir, "WP01", "planned", "approved", force=True)

    # Latest event is planned→claimed, not a rejection → no override
    assert result is False


# ---------------------------------------------------------------------------
# Tests for Lane enum type safety (typed comparisons)
# ---------------------------------------------------------------------------


def test_lane_enum_for_review_comparison() -> None:
    """Lane.FOR_REVIEW equals 'for_review' (StrEnum property)."""
    assert Lane.FOR_REVIEW == "for_review"
    assert Lane("for_review") == Lane.FOR_REVIEW


def test_lane_enum_planned_comparison() -> None:
    """Lane.PLANNED equals 'planned' (StrEnum property)."""
    assert Lane.PLANNED == "planned"
    assert Lane("planned") == Lane.PLANNED


def test_arbiter_decision_targets_are_approval_lanes_only() -> None:
    """Only approval lanes are arbiter-override targets (#5196).

    Replaces a self-referential literal-set check that pinned the retired
    ``{for_review, claimed, approved}`` target set and could never fail.
    """
    from specify_cli.review import arbiter

    expected = frozenset({Lane.APPROVED, Lane.DONE})
    assert expected == arbiter._ARBITER_DECISION_TARGETS


# ---------------------------------------------------------------------------
# Tests for arbiter decision functions (verify live module functions)
# ---------------------------------------------------------------------------


def test_create_arbiter_decision_returns_decision() -> None:
    """create_arbiter_decision produces a valid ArbiterDecision."""
    decision = create_arbiter_decision(
        arbiter_name="operator",
        category=ArbiterCategory.PRE_EXISTING_FAILURE,
        explanation="Test failure was pre-existing.",
    )
    assert decision.arbiter == "operator"
    assert decision.category == ArbiterCategory.PRE_EXISTING_FAILURE
    assert decision.explanation == "Test failure was pre-existing."
    assert decision.checklist is not None
    assert decision.decided_at is not None


def test_parse_category_from_note_pre_existing() -> None:
    """parse_category_from_note parses [pre_existing_failure] prefix."""
    category, explanation = parse_category_from_note("[pre_existing_failure] Test was failing before")
    assert category == ArbiterCategory.PRE_EXISTING_FAILURE
    assert explanation == "Test was failing before"


def test_parse_category_from_note_custom_fallback() -> None:
    """parse_category_from_note falls back to CUSTOM for unrecognised prefix."""
    category, explanation = parse_category_from_note("Some freeform note without category")
    assert category == ArbiterCategory.CUSTOM
    assert explanation == "Some freeform note without category"


def test_arbiter_checklist_roundtrip() -> None:
    """ArbiterChecklist serialises and deserialises correctly."""
    checklist = ArbiterChecklist(
        is_pre_existing=True,
        is_correct_context=True,
        is_in_scope=False,
        is_environmental=False,
        should_follow_on=True,
    )
    data = checklist.to_dict()
    restored = ArbiterChecklist.from_dict(data)
    assert restored == checklist


# ---------------------------------------------------------------------------
# Truth table (contract arbiter-override-classification): (latest-event shape, target lane) -> is override?
# Force on, old lane planned, WP01's latest event is the given shape.
# ---------------------------------------------------------------------------

_SHAPES: dict[str, tuple[Lane, Lane, str | None]] = {
    "for_review_rejection": (Lane.FOR_REVIEW, Lane.PLANNED, "rev://ref/1"),
    "in_review_rejection": (Lane.IN_REVIEW, Lane.PLANNED, "rev://ref/1"),
    "rollback_without_ref": (Lane.FOR_REVIEW, Lane.PLANNED, None),
    "reopen_from_approved": (Lane.APPROVED, Lane.PLANNED, "rev://ref/1"),
    "non_rejection": (Lane.PLANNED, Lane.CLAIMED, None),
}

_TARGETS = ("for_review", "claimed", "in_progress", "approved", "done")

_CHARACTERIZATION: dict[str, tuple[bool, bool, bool, bool, bool]] = {
    # Expected result per target, in _TARGETS order.
    # Deltas vs. the base (#5196): rework targets are never overrides; the
    # in_review source now counts; ``done`` is a decision target.
    "for_review_rejection": (False, False, False, True, True),
    "in_review_rejection": (False, False, False, True, True),
    "rollback_without_ref": (False, False, False, False, False),
    "reopen_from_approved": (False, False, False, False, False),
    "non_rejection": (False, False, False, False, False),
}

_CHARACTERIZATION_CASES = [
    pytest.param(shape, target, expected[i], id=f"{shape}-{target}") for shape, expected in _CHARACTERIZATION.items() for i, target in enumerate(_TARGETS)
]


def _seed_shape(feature_dir: Path, shape: str) -> None:
    from_lane, to_lane, ref = _SHAPES[shape]
    _make_event(feature_dir, "WP01", from_lane, to_lane, review_ref=ref)


def _evaluate(feature_dir: Path, target: str, *, force: bool = True, old_lane: str = "planned") -> bool:
    return _is_arbiter_override(feature_dir, "WP01", old_lane, target, force=force)


@pytest.mark.parametrize(("shape", "target", "expected"), _CHARACTERIZATION_CASES)
def test_truth_table_shape_by_target(tmp_path: Path, shape: str, target: str, expected: bool) -> None:
    feature_dir = tmp_path / "kitty-specs" / "080-test"
    feature_dir.mkdir(parents=True)
    _seed_shape(feature_dir, shape)

    assert _evaluate(feature_dir, target) is expected


@pytest.mark.parametrize("target", _TARGETS)
@pytest.mark.parametrize(("force", "old_lane"), [(False, "planned"), (True, "in_progress"), (False, "in_progress")])
def test_truth_table_gates_dominate(tmp_path: Path, target: str, force: bool, old_lane: str) -> None:
    """Without force, or with an old lane other than planned, nothing is an override."""
    feature_dir = tmp_path / "kitty-specs" / "080-test"
    feature_dir.mkdir(parents=True)
    _seed_shape(feature_dir, "for_review_rejection")

    assert _evaluate(feature_dir, target, force=force, old_lane=old_lane) is False


def _shape_event(shape: str, wp_id: str = "WP01") -> StatusEvent:
    from_lane, to_lane, ref = _SHAPES[shape]
    return StatusEvent(
        event_id="01TESTPURE0000000000000000",
        mission_slug="080-test",
        wp_id=wp_id,
        from_lane=from_lane,
        to_lane=to_lane,
        at="2026-04-09T12:00:00+00:00",
        actor="test-actor",
        force=True,
        execution_mode="direct_repo",
        review_ref=ref,
    )


@pytest.mark.parametrize(("shape", "target", "expected"), _CHARACTERIZATION_CASES)
def test_pure_history_matches_truth_table(shape: str, target: str, expected: bool) -> None:
    """The pure predicate answers the same table as the read_events shell."""
    assert is_arbiter_override_history([_shape_event(shape)], "WP01", "planned", target, True) is expected


def test_pure_history_ignores_other_wps_events() -> None:
    events = [_shape_event("for_review_rejection"), _shape_event("non_rejection", wp_id="WP02")]

    assert is_arbiter_override_history(events, "WP01", "planned", "approved", True) is True
    assert is_arbiter_override_history(events, "WP03", "planned", "approved", True) is False
