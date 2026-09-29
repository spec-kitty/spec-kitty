"""ConsolidationState snapshot fields + ``reconciliation_passed_for_tip`` (WP02 / T008)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.consolidation.state import (
    ConsolidationState,
    load_state,
    reconciliation_passed_for_tip,
    save_state,
)

pytestmark = pytest.mark.fast

_MAP_FIELDS = ("pre_mutation_refs", "post_mutation_refs", "restore_targets")


def _state(
    *,
    pre_mutation_refs: dict[str, str] | None = None,
    post_mutation_refs: dict[str, str] | None = None,
    restore_targets: dict[str, str] | None = None,
    reconciliation_passed_target_sha: str | None = None,
) -> ConsolidationState:
    return ConsolidationState(
        mission_id="M1",
        mission_slug="m-1",
        target_branch="develop",
        wp_order=["WP01"],
        pre_mutation_refs=pre_mutation_refs or {},
        post_mutation_refs=post_mutation_refs or {},
        restore_targets=restore_targets or {},
        reconciliation_passed_target_sha=reconciliation_passed_target_sha,
    )


def test_round_trip_through_disk(tmp_path: Path) -> None:
    state = _state(
        pre_mutation_refs={"develop": "a1"},
        post_mutation_refs={"develop": "b2"},
        restore_targets={"develop": "a1"},
    )
    save_state(state, tmp_path)
    loaded = load_state(tmp_path, "M1")
    assert loaded is not None
    assert loaded.pre_mutation_refs == {"develop": "a1"}
    assert loaded.post_mutation_refs == {"develop": "b2"}
    assert loaded.restore_targets == {"develop": "a1"}


def test_older_record_without_the_keys_loads_empty() -> None:
    legacy = _state().to_dict()
    for name in _MAP_FIELDS:
        del legacy[name]
    loaded = ConsolidationState.from_dict(legacy)
    assert all(getattr(loaded, name) == {} for name in _MAP_FIELDS)


@pytest.mark.parametrize("name", _MAP_FIELDS)
@pytest.mark.parametrize("bad", [None, "abc", ["a"], {"k": 1}, {"k": None}, {1: "x"}, True])
def test_malformed_values_load_as_empty_never_coerced(name: str, bad: object) -> None:
    data = _state().to_dict()
    data[name] = bad
    assert getattr(ConsolidationState.from_dict(data), name) == {}


def test_malformed_map_survives_json_round_trip() -> None:
    data = json.loads(json.dumps(_state().to_dict()))
    data["pre_mutation_refs"] = {"develop": 5}
    assert ConsolidationState.from_dict(data).pre_mutation_refs == {}


@pytest.mark.parametrize("name", ["snapshot_lane_branches", "resume_seeded_refs"])
@pytest.mark.parametrize("bad", ["lane-a", ["lane-a", 3], {"lane-a": "x"}, None])
def test_malformed_branch_lists_load_as_empty(name: str, bad: object) -> None:
    """Slice-10: a malformed branch list fails closed (``snapshot_lane_branches``: every branch run-movable)."""
    data = _state().to_dict()
    data[name] = bad
    assert getattr(ConsolidationState.from_dict(data), name) == []


def test_lane_branch_list_round_trips_and_is_absent_in_older_records() -> None:
    state = _state()
    state.snapshot_lane_branches = ["kitty/lane-a"]
    assert ConsolidationState.from_dict(json.loads(json.dumps(state.to_dict()))).snapshot_lane_branches == ["kitty/lane-a"]
    older = _state().to_dict()
    del older["snapshot_lane_branches"]
    assert ConsolidationState.from_dict(older).snapshot_lane_branches == []


def test_defaults_are_independent_dicts() -> None:
    first, second = _state(), _state()
    first.pre_mutation_refs["x"] = "y"
    assert second.pre_mutation_refs == {}


@pytest.mark.parametrize(
    ("passed", "current", "expected"),
    [
        (None, "", False),
        ("abc", "", False),
        (None, "abc", False),
        ("abc", "def", False),
        ("abc", "abc", True),
    ],
)
def test_reconciliation_passed_for_tip_truth_table(passed: str | None, current: str, expected: bool) -> None:
    assert reconciliation_passed_for_tip(_state(reconciliation_passed_target_sha=passed), current) is expected
