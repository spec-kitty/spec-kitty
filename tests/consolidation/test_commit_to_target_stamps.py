"""#7578 ruling Q8: consolidation reads no window stamp of a commit-to-target ``single_branch`` Mission.

Pins the predicate's ``meta.json`` reading (:func:`is_commit_to_target_mission`; the pure predicate is
pinned in ``tests/lanes/test_single_branch_meta_predicates.py``), the event filter and the one
event-loading door, :func:`consolidation_events`. That the claim's event log, the ``--dependency-ref``
guard and the ``--attest-approved-reviewed`` validation all read through the door is pinned by
``test_single_consolidation_event_door.py``. Every other Mission's events pass through unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from specify_cli.consolidation.commit_to_target_stamps import (
    consolidation_events,
    is_commit_to_target_mission,
    without_window_stamps,
)
from specify_cli.status import LANE_HEAD_KEY, WP_WINDOW_KEY, Lane, StatusEvent
from specify_cli.status.store import append_events_atomic

pytestmark = [pytest.mark.fast]

_TARGET = "main"
_SHA = "3f1c0d9e8b7a6f5e4d3c2b1a0f9e8d7c6b5a4f3e"
_SLUG = "ctt-01CTTFIX"
_CTT_META: dict[str, Any] = {"topology": "single_branch", "target_branch": _TARGET}
_MINTED_META: dict[str, Any] = {"topology": "single_branch", "target_branch": _TARGET, "mission_branch": "kitty/mission-x"}


def _event(event_id: str, to_lane: Lane, from_lane: Lane, metadata: dict[str, Any] | None) -> StatusEvent:
    return StatusEvent(
        event_id=event_id,
        mission_slug=_SLUG,
        wp_id="WP01",
        from_lane=from_lane,
        to_lane=to_lane,
        at="2026-11-12T00:00:00+00:00",
        actor="alice",
        force=False,
        execution_mode="direct_repo",
        policy_metadata=metadata,
    )


_STAMPED_OPEN = _event("01KZ0000000000000000000001", Lane.CLAIMED, Lane.PLANNED, {LANE_HEAD_KEY: _SHA, WP_WINDOW_KEY: {"schema_version": 1, "open_sha": _SHA}})
_STAMPED_APPROVAL = _event("01KZ0000000000000000000002", Lane.APPROVED, Lane.IN_REVIEW, {LANE_HEAD_KEY: _SHA, "agent": "bob"})


def _mission_dir(tmp_path: Path, meta: dict[str, Any] | None, events: list[StatusEvent]) -> Path:
    feature_dir = tmp_path / "kitty-specs" / _SLUG
    feature_dir.mkdir(parents=True)
    if meta is not None:
        (feature_dir / "meta.json").write_text(json.dumps({"mission_slug": _SLUG, **meta}), encoding="utf-8")
    append_events_atomic(feature_dir, events)
    return feature_dir


# --------------------------------------------------------------------------- the predicate over meta.json


def test_is_commit_to_target_mission_reads_meta_json(tmp_path: Path) -> None:
    assert is_commit_to_target_mission(_mission_dir(tmp_path / "ctt", _CTT_META, []))
    assert not is_commit_to_target_mission(_mission_dir(tmp_path / "minted", _MINTED_META, []))
    assert not is_commit_to_target_mission(_mission_dir(tmp_path / "none", None, []))


# --------------------------------------------------------------------------- the filter


def test_without_window_stamps_keeps_other_metadata() -> None:
    stripped = without_window_stamps(_STAMPED_APPROVAL)

    assert stripped.policy_metadata == {"agent": "bob"}
    assert stripped.event_id == _STAMPED_APPROVAL.event_id and stripped.to_lane == _STAMPED_APPROVAL.to_lane


def test_without_window_stamps_leaves_none_when_only_stamps() -> None:
    assert without_window_stamps(_STAMPED_OPEN).policy_metadata is None


def test_without_window_stamps_returns_unstamped_events_as_is() -> None:
    plain = _event("01KZ0000000000000000000003", Lane.CLAIMED, Lane.PLANNED, {"agent": "alice"})
    empty = _event("01KZ0000000000000000000004", Lane.CLAIMED, Lane.PLANNED, None)

    assert without_window_stamps(plain) is plain
    assert without_window_stamps(empty) is empty


# --------------------------------------------------------------------------- the one door


@pytest.mark.parametrize(("meta", "stamped"), [pytest.param(_CTT_META, False, id="ctt"), pytest.param(_MINTED_META, True, id="minted")])
def test_consolidation_events_reads_no_stamp_of_a_commit_to_target_mission(tmp_path: Path, meta: dict[str, Any], stamped: bool) -> None:
    events = consolidation_events(_mission_dir(tmp_path, meta, [_STAMPED_OPEN, _STAMPED_APPROVAL]))

    assert len(events) == 2
    assert any(LANE_HEAD_KEY in (event.policy_metadata or {}) for event in events) is stamped
    assert any(WP_WINDOW_KEY in (event.policy_metadata or {}) for event in events) is stamped
