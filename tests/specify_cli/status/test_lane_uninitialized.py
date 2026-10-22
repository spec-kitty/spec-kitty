"""RED-first contract tests for ``Lane.UNINITIALIZED`` (#2675 core, WP05).

Locks three foundational contracts before the product code exists:

1. ``Lane.UNINITIALIZED`` is a real StrEnum member (value ``"uninitialized"``)
   distinct from ``Lane.GENESIS``.
2. ``get_wp_lane`` returns a pure ``Lane.UNINITIALIZED`` (never a bare
   ``str``) for both the empty-event-log path and the WP-absent-from-
   snapshot path.
3. ``specify_cli.status.transitions`` remains import-safe once the member
   exists (the FSM sweeps every ``Lane`` member at import time).

See also: the display-exclusion assertion, which pins that the reducer's
summary never leaks an ``"uninitialized"`` key (T043's regression guard).
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from specify_cli.status.lane_reader import get_wp_lane
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.reducer import reduce
from specify_cli.status.store import EVENTS_FILENAME, read_events
from tests._support.status_seed import seed_status_event

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _make_event(
    *,
    event_id: str = "01HXYZ0000000000000000000A",
    mission_slug: str = "060-lane-uninitialized",
    wp_id: str = "WP01",
    from_lane: Lane = Lane.GENESIS,
    to_lane: Lane = Lane.PLANNED,
    at: str = "2026-07-15T12:00:00Z",
    actor: str = "claude-opus",
) -> StatusEvent:
    """Helper to build a production-shaped StatusEvent (mirrors test_reducer.py)."""
    return StatusEvent(
        event_id=event_id,
        mission_slug=mission_slug,
        wp_id=wp_id,
        from_lane=from_lane,
        to_lane=to_lane,
        at=at,
        actor=actor,
        force=False,
        execution_mode="worktree",
    )


class TestLaneUninitializedMember:
    """Contract 1: the StrEnum member exists, is documented, and is distinct."""

    def test_value_is_uninitialized_string(self) -> None:
        assert Lane.UNINITIALIZED.value == "uninitialized"

    def test_strenum_equality_contract_holds(self) -> None:
        # StrEnum equality against its own .value must hold — this is the
        # bridge WP06's still-string-based consumers rely on during the
        # migration window.
        assert Lane.UNINITIALIZED == "uninitialized"

    def test_distinct_from_genesis(self) -> None:
        assert Lane.UNINITIALIZED is not Lane.GENESIS
        assert Lane.UNINITIALIZED.value != Lane.GENESIS.value


class TestFsmImportSafety:
    """Contract 3: the FSM import-time sweep over ``Lane`` does not crash."""

    def test_transitions_module_imports_cleanly(self) -> None:
        module = importlib.import_module("specify_cli.status.transitions")
        assert module is not None

    def test_uninitialized_state_resolves_without_raising(self) -> None:
        from specify_cli.status.wp_state import wp_state_for

        state = wp_state_for(Lane.UNINITIALIZED)
        assert state.lane is Lane.UNINITIALIZED

    def test_uninitialized_state_has_no_allowed_targets(self) -> None:
        """Non-transitionable: allowed_targets() is EMPTY (no injected edges)."""
        from specify_cli.status.wp_state import wp_state_for

        state = wp_state_for(Lane.UNINITIALIZED)
        assert state.allowed_targets() == frozenset()

    def test_transition_matrix_edge_count_unchanged(self) -> None:
        """Empty allowed_targets() must add ZERO edges — count stays 29."""
        from specify_cli.status.transitions import ALLOWED_TRANSITIONS

        assert len(ALLOWED_TRANSITIONS) == 29

    def test_uninitialized_is_unreachable_as_a_transition_endpoint(self) -> None:
        """Harden (#2675): ``UNINITIALIZED`` must never be a from- or to-lane
        of any allowed transition.

        This is what makes it safe for ``_CANONICAL_LANE_VALUES``
        (``sync/emitter.py``), ``VALID_LANES``
        (``migration/mission_state.py``), and ``_VALID_LANES``
        (``migration/rebuild_state.py``) to admit ``"uninitialized"`` merely
        by deriving from ``get_all_lane_values()`` / full ``Lane`` iteration
        — those whitelists stay inert only as long as no transition can ever
        emit with ``from_lane`` or ``to_lane`` equal to ``"uninitialized"``.
        If a future edge ever targets or originates from ``UNINITIALIZED``,
        those widened whitelists stop being inert and this test must fail
        first.
        """
        from specify_cli.status.transitions import ALLOWED_TRANSITIONS

        endpoints = {lane for edge in ALLOWED_TRANSITIONS for lane in edge}
        assert Lane.UNINITIALIZED.value not in endpoints


class TestGetWpLaneEmptyEventLog:
    """Contract 2a: event log exists but is empty -> Lane.UNINITIALIZED."""

    def test_returns_uninitialized_member_for_empty_log(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "060-lane-uninitialized"
        feature_dir.mkdir(parents=True)
        # File exists but has zero events (has_event_log() True, read_events() []).
        (feature_dir / EVENTS_FILENAME).touch()

        result = get_wp_lane(feature_dir, "WP01")

        assert result == Lane.UNINITIALIZED
        assert isinstance(result, Lane)


class TestGetWpLaneAbsentFromSnapshot:
    """Contract 2b: WP has no events (other WPs do) -> Lane.UNINITIALIZED."""

    def test_returns_uninitialized_member_for_absent_wp(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "060-lane-uninitialized"
        feature_dir.mkdir(parents=True)
        seed_status_event(
            feature_dir,
            _make_event(event_id="01HXYZ0000000000000000000A", wp_id="WP01"),
        )
        # Sanity: the seeded WP really is durable before asserting on the absent one.
        assert read_events(feature_dir)

        result = get_wp_lane(feature_dir, "WPZZ")

        assert result == Lane.UNINITIALIZED
        assert isinstance(result, Lane)


class TestDisplayExclusion:
    """Regression guard for T043: no ``"uninitialized"`` key in any summary."""

    def test_reducer_summary_excludes_uninitialized(self) -> None:
        events = [
            _make_event(event_id="01HXYZ0000000000000000000A", wp_id="WP01"),
        ]
        snapshot = reduce(events)

        assert "uninitialized" not in snapshot.summary
        assert Lane.UNINITIALIZED.value not in snapshot.summary
