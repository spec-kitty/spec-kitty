"""Focused tests for the destroyed-lane guard's pure decision table.

WP01 campsite split (single-branch-topology-honesty-01M3M22V, T001/T003):
``_refuse_if_lane_destroyed`` was restructured into a pure decision function
(``_destroyed_lane_verdict``) plus a thin effect wrapper that raises. These
tests pin the decision table directly -- no git repo, no status surface, no
``WorkspaceContext`` required -- independent of how ``_refuse_if_lane_
destroyed`` gathers its inputs in production.

See ``src/specify_cli/lanes/worktree_allocator.py`` (``_DESTROYED_LANE_
TRIGGER_STATES``, ``_destroyed_lane_verdict``) and
``../../kitty-specs/implement-lane-recut-and-planning-commit-integrity-01M3CM55/
data-model.md#4889-destroyed-lane-decision-table``.
"""

from __future__ import annotations

import pytest

from specify_cli.lanes.worktree_allocator import (
    _DESTROYED_LANE_TRIGGER_STATES,
    _destroyed_lane_verdict,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_no_context_proceeds_even_when_other_inputs_would_otherwise_refuse() -> None:
    """No persisted context short-circuits to ``proceed`` (FR-001, fresh lane)."""
    verdict = _destroyed_lane_verdict(
        has_context=False,
        wp_state="in_progress",
        status_unreadable=True,
        base_reachable=False,
    )
    assert verdict == "proceed"


def test_unreadable_status_with_context_refuses_unreadable() -> None:
    """A confirmed context plus an unreadable status surface fails closed."""
    verdict = _destroyed_lane_verdict(
        has_context=True,
        wp_state=None,
        status_unreadable=True,
        base_reachable=False,
    )
    assert verdict == "refuse_unreadable"


@pytest.mark.parametrize("wp_state", sorted(_DESTROYED_LANE_TRIGGER_STATES))
def test_trigger_state_with_unreachable_base_refuses_destroyed(wp_state: str) -> None:
    """Every non-terminal trigger state refuses when the base never landed."""
    verdict = _destroyed_lane_verdict(
        has_context=True,
        wp_state=wp_state,
        status_unreadable=False,
        base_reachable=False,
    )
    assert verdict == "refuse_destroyed"


@pytest.mark.parametrize("wp_state", sorted(_DESTROYED_LANE_TRIGGER_STATES))
def test_trigger_state_with_reachable_base_proceeds(wp_state: str) -> None:
    """FR-009 resume: a reachable base waves the guard through even in a trigger state."""
    verdict = _destroyed_lane_verdict(
        has_context=True,
        wp_state=wp_state,
        status_unreadable=False,
        base_reachable=True,
    )
    assert verdict == "proceed"


@pytest.mark.parametrize("wp_state", ["planned", "claimed", "done", "canceled"])
def test_non_trigger_state_proceeds_regardless_of_base_reachability(wp_state: str) -> None:
    """Pre-allocation and terminal states are never a trigger, base or not."""
    verdict = _destroyed_lane_verdict(
        has_context=True,
        wp_state=wp_state,
        status_unreadable=False,
        base_reachable=False,
    )
    assert verdict == "proceed"
