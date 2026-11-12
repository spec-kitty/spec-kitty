"""One clear/restore door for the reconciliation PASS anchor (coord-closeout-leftovers WP01).

``ConsolidationState.reconciliation_passed_target_sha`` (#5021) is cleared by the
rollback authority and restored by the executor's failure door. Both writes go
through two pure field mutators on the record, so a field that must travel with
the anchor (#7491, added in WP02) is cleared and restored in one place.
"""

from __future__ import annotations

import pytest

from specify_cli.consolidation.state import ConsolidationState

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _state(anchor: str | None) -> ConsolidationState:
    return ConsolidationState(
        mission_id="m",
        mission_slug="m",
        target_branch="main",
        wp_order=["WP01"],
        reconciliation_passed_target_sha=anchor,
    )


def _assert_round_trips(state: ConsolidationState) -> None:
    assert ConsolidationState.from_dict(state.to_dict()) == state


def test_clear_drops_a_recorded_anchor_and_reports_the_change() -> None:
    state = _state("abc")

    assert state.clear_reconciliation_pass() is True
    assert state.reconciliation_passed_target_sha is None
    _assert_round_trips(state)


def test_clear_without_an_anchor_reports_no_change() -> None:
    state = _state(None)

    assert state.clear_reconciliation_pass() is False
    assert state.reconciliation_passed_target_sha is None
    _assert_round_trips(state)


def test_restore_writes_a_different_anchor_and_reports_the_change() -> None:
    state = _state("def")

    assert state.restore_reconciliation_pass("abc") is True
    assert state.reconciliation_passed_target_sha == "abc"
    _assert_round_trips(state)


def test_restore_of_the_same_anchor_reports_no_change() -> None:
    state = _state("abc")

    assert state.restore_reconciliation_pass("abc") is False
    assert state.reconciliation_passed_target_sha == "abc"
    _assert_round_trips(state)


def test_restore_of_none_clears_the_anchor() -> None:
    state = _state("abc")

    assert state.restore_reconciliation_pass(None) is True
    assert state.reconciliation_passed_target_sha is None
    _assert_round_trips(state)


def test_restore_of_none_without_an_anchor_reports_no_change() -> None:
    state = _state(None)

    assert state.restore_reconciliation_pass(None) is False
    assert state.reconciliation_passed_target_sha is None
    _assert_round_trips(state)


def test_helpers_leave_every_other_field_untouched() -> None:
    state = _state("abc")
    before = state.to_dict()

    state.clear_reconciliation_pass()
    state.restore_reconciliation_pass("abc")

    assert state.to_dict() == before
