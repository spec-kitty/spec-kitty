"""Pin the lane vocabulary to the ``spec_kitty_events`` package (#6448).

The events package owns the lane vocabulary. ``specify_cli.status_lanes``
derives ``PACKAGE_LANES`` from it and ``CANONICAL_LANES`` (the authorable
subset) by removing ``NON_AUTHORABLE_LANES``. These tests fail when the
package and the CLI drift, and when a hand-typed lane list reappears.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TypeGuard

import pytest
from spec_kitty_events.status import Lane as PackageLane

from specify_cli import status_lanes
from specify_cli.status.event_log_merge import _FORWARD_RANK
from specify_cli.status.models import Lane as CliLane

pytestmark = pytest.mark.fast

_EXPECTED_CANONICAL_LANES: tuple[str, ...] = (
    "planned",
    "claimed",
    "in_progress",
    "for_review",
    "in_review",
    "approved",
    "done",
    "blocked",
    "canceled",
)
_READ_SENTINEL = "uninitialized"
_MIN_LIST_LENGTH = 3


def test_package_lanes_mirror_the_events_enum() -> None:
    assert tuple(lane.value for lane in PackageLane) == status_lanes.PACKAGE_LANES


def test_canonical_lanes_are_package_lanes_minus_non_authorable_in_order() -> None:
    derived = tuple(lane for lane in status_lanes.PACKAGE_LANES if lane not in status_lanes.NON_AUTHORABLE_LANES)
    assert derived == status_lanes.CANONICAL_LANES
    # The literal is the ratchet proving the derivation changed no behaviour.
    assert _EXPECTED_CANONICAL_LANES == status_lanes.CANONICAL_LANES


def test_genesis_is_the_only_non_authorable_lane() -> None:
    assert frozenset({"genesis"}) == status_lanes.NON_AUTHORABLE_LANES
    assert "genesis" not in status_lanes.CANONICAL_LANES


def test_cli_lane_enum_matches_package_plus_read_sentinel() -> None:
    cli_values = {lane.value for lane in CliLane}
    assert cli_values == set(status_lanes.PACKAGE_LANES) | {_READ_SENTINEL}


def _is_hand_typed_lane_list(node: ast.AST, lane_values: frozenset[str]) -> TypeGuard[ast.Tuple | ast.List | ast.Set]:
    if not isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return False
    if len(node.elts) < _MIN_LIST_LENGTH:
        return False
    return all(isinstance(elt, ast.Constant) and elt.value in lane_values for elt in node.elts)


def test_status_lanes_holds_no_hand_typed_lane_list() -> None:
    lane_values = frozenset(lane.value for lane in PackageLane)
    tree = ast.parse(Path(status_lanes.__file__).read_text(encoding="utf-8"))
    offenders = [node.lineno for node in ast.walk(tree) if _is_hand_typed_lane_list(node, lane_values)]
    assert offenders == [], f"hand-typed lane list(s) at line(s) {offenders} in status_lanes.py"


def test_hand_typed_lane_list_detector_flags_a_literal() -> None:
    lane_values = frozenset(lane.value for lane in PackageLane)
    flagged = ast.parse('("planned", "claimed", "done")', mode="eval").body
    short = ast.parse('("planned", "done")', mode="eval").body
    mixed = ast.parse('("planned", "claimed", "not-a-lane")', mode="eval").body
    assert _is_hand_typed_lane_list(flagged, lane_values)
    assert not _is_hand_typed_lane_list(short, lane_values)
    assert not _is_hand_typed_lane_list(mixed, lane_values)


def test_event_log_merge_forward_rank_excludes_genesis_and_keeps_order() -> None:
    assert "genesis" not in _FORWARD_RANK
    ordered = sorted(_FORWARD_RANK, key=_FORWARD_RANK.__getitem__)
    assert ordered == ["planned", "claimed", "in_progress", "for_review", "in_review", "approved", "done"]
