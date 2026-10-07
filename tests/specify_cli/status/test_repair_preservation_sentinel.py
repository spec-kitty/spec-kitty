"""Green sentinel: the repair's lane-row canonicalization must never again
destroy the FSM guard inputs (WP04, NFR-004; #3051/#3541).

This pins commit ``bec7c25273`` ("fix(migration): stop mission-state repair
destroying review_result and log order"). Before ``bec7c25273`` the repair's
hand-written allowlist omitted ``review_result``, a hard FSM guard input (every
transition out of ``in_review`` is rejected without it), silently converting
valid history into unvalidatable events. Since #5811 the allowlist is gone: a
lane row round-trips through ``StatusEvent`` (``_round_trip_lane_row``), so this
sentinel is re-pinned to that single authority.

This is a **guard, not a red-first regression**: it is GREEN on the merge base
and stays GREEN after WP04. Any WP that reintroduces the destruction (dropping
``review_result`` or the other guard-carrying fields) turns this red — which is
exactly the false red WP04 forbids a later WP from manufacturing.
"""

from __future__ import annotations

import pytest

from specify_cli.migration.mission_state import _round_trip_lane_row

# Module-level marker so every node is collected by a main-push job
# (#2957 CI-collection-completeness): matches the sibling status unit tests.
pytestmark = [pytest.mark.unit, pytest.mark.fast]

_MISSION_ID = "01J000000000000000000SENTL"

# The fields the round trip must carry through unchanged. ``review_ref``
# / ``evidence`` / ``review_result`` are the in_review→approved/rejected guard
# inputs; ``reason`` / ``policy_metadata`` are first-class StatusEvent payload.
_GUARD_FIELDS = ("reason", "review_ref", "evidence", "review_result", "policy_metadata")


def _normalized_review_row() -> dict[str, object]:
    """A normalized row carrying every guard field with a distinctive value."""
    return {
        "event_id": "01J000000000000000000EVENT",
        "mission_slug": "sentinel-mission",
        "wp_id": "WP01",
        "from_lane": "in_review",
        "to_lane": "approved",
        "at": "2026-07-28T07:55:23+00:00",
        "actor": "claude",
        "force": False,
        "execution_mode": "worktree",
        "reason": "sentinel-reason",
        "review_ref": "review/sentinel",
        "evidence": {"review": {"reviewer": "r", "verdict": "approved", "reference": "ref"}},
        "review_result": {"reviewer": "r", "verdict": "approved", "reference": "ref"},
        "policy_metadata": {"origin": "sentinel"},
    }


def test_round_trip_preserves_review_result() -> None:
    """``review_result`` survives canonicalization (bec7c25273)."""
    row = _normalized_review_row()

    canonical = _round_trip_lane_row(row, [])

    assert canonical["review_result"] == row["review_result"]


def test_round_trip_preserves_all_fsm_guard_inputs() -> None:
    """Every guard-carrying field survives verbatim (bec7c25273)."""
    row = {**_normalized_review_row(), "mission_id": _MISSION_ID}

    canonical = _round_trip_lane_row(row, [])

    for field_name in _GUARD_FIELDS:
        assert canonical[field_name] == row[field_name], (
            f"{field_name} must be preserved by the lane-row round trip (regressing it manufactures the bec7c25273 false red)"
        )
    assert canonical["mission_id"] == _MISSION_ID
