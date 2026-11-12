"""#7578 ruling Q8: consolidation reads no window stamp of a commit-to-target ``single_branch`` Mission.

Pins the one predicate (:func:`is_commit_to_target_meta`), the event filter, and the guarded seams:
the claim's event log (``_ClaimEventLog``, which feeds the canceled-work attribution), the
``--dependency-ref`` guard (``_recorded_lane_heads``) and the ``--attest-approved-reviewed`` validation
(``plan_approved_attestations``). Every other Mission's events pass through unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from specify_cli.consolidation import approved_attestation
from specify_cli.consolidation.commit_to_target_stamps import (
    WINDOW_STAMP_KEYS,
    consolidation_events,
    is_commit_to_target_meta,
    is_commit_to_target_mission,
    without_window_stamps,
)
from specify_cli.consolidation.reconciliation_closed_world import _recorded_lane_heads
from specify_cli.consolidation.reconciliation_kernel import _ClaimEventLog
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.status import LANE_HEAD_KEY, WP_WINDOW_KEY, Lane, StatusEvent
from specify_cli.status.store import append_events_atomic

pytestmark = [pytest.mark.fast]

_TARGET = "main"
_SHA = "3f1c0d9e8b7a6f5e4d3c2b1a0f9e8d7c6b5a4f3e"
_SLUG = "ctt-01CTTFIX"
_CTT_META: dict[str, Any] = {"topology": "single_branch", "target_branch": _TARGET}
_MINTED_META: dict[str, Any] = {"topology": "single_branch", "target_branch": _TARGET, "mission_branch": "kitty/mission-x"}
_LANES_META: dict[str, Any] = {"topology": "lanes", "target_branch": _TARGET}


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


# --------------------------------------------------------------------------- the predicate


@pytest.mark.parametrize(
    ("meta", "expected"),
    [
        pytest.param(_CTT_META, True, id="commit-to-target"),
        pytest.param({**_CTT_META, "commit_to_target": True}, True, id="commit-to-target-flagged"),
        pytest.param(_MINTED_META, False, id="minted-mission-branch"),
        pytest.param(_LANES_META, False, id="lanes"),
        pytest.param({"target_branch": _TARGET}, False, id="no-stored-topology"),
        pytest.param({"topology": "single_branch"}, False, id="no-target"),
        pytest.param({"topology": "single_branch", "target_branch": ""}, False, id="empty-target"),
        pytest.param({"topology": "single_branch", "target_branch": 7}, False, id="non-string-target"),
    ],
)
def test_is_commit_to_target_meta(meta: dict[str, Any], expected: bool) -> None:
    assert is_commit_to_target_meta(meta) is expected


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


def test_consolidation_events_strips_only_a_commit_to_target_mission(tmp_path: Path) -> None:
    events = [_STAMPED_OPEN, _STAMPED_APPROVAL]
    ctt = consolidation_events(_mission_dir(tmp_path / "ctt", _CTT_META, []), events)
    minted = consolidation_events(_mission_dir(tmp_path / "minted", _MINTED_META, []), events)

    assert all(WINDOW_STAMP_KEYS.isdisjoint(event.policy_metadata or {}) for event in ctt)
    assert minted == events


# --------------------------------------------------------------------------- the guarded seams


@pytest.mark.parametrize(("meta", "stamped"), [pytest.param(_CTT_META, False, id="ctt"), pytest.param(_MINTED_META, True, id="minted")])
def test_claim_event_log_reads_no_stamp_of_a_commit_to_target_mission(tmp_path: Path, meta: dict[str, Any], stamped: bool) -> None:
    """Seam 1: the claim's event log, which the canceled-work attribution and the compound refusal read."""
    events = _ClaimEventLog(_mission_dir(tmp_path, meta, [_STAMPED_OPEN, _STAMPED_APPROVAL])).read()

    assert events is not None and len(events) == 2
    assert any(LANE_HEAD_KEY in (event.policy_metadata or {}) for event in events) is stamped


@pytest.mark.parametrize(("meta", "expected"), [pytest.param(_CTT_META, frozenset(), id="ctt"), pytest.param(_MINTED_META, frozenset({_SHA}), id="minted")])
def test_recorded_lane_heads_of_a_commit_to_target_mission_is_empty(tmp_path: Path, meta: dict[str, Any], expected: frozenset[str]) -> None:
    """Seam 2: the ``--dependency-ref`` "names Mission work" guard sees no stamp of a commit-to-target Mission."""
    assert _recorded_lane_heads(_mission_dir(tmp_path, meta, [_STAMPED_OPEN, _STAMPED_APPROVAL])) == expected


def _manifest() -> LanesManifest:
    lane = ExecutionLane(lane_id="lane-planning", wp_ids=("WP01",), write_scope=(), predicted_surfaces=(), depends_on_lanes=(), parallel_group=0)
    return LanesManifest(
        version=1,
        mission_slug=_SLUG,
        mission_id=None,
        mission_branch=_TARGET,
        target_branch=_TARGET,
        lanes=[lane],
        computed_at="2026-11-12T00:00:00+00:00",
        computed_from="test",
    )


@pytest.mark.parametrize(("meta", "stamp_seen"), [pytest.param(_CTT_META, False, id="ctt"), pytest.param(_MINTED_META, True, id="minted")])
def test_attestation_validation_sees_no_stamp_of_a_commit_to_target_mission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, meta: dict[str, Any], stamp_seen: bool
) -> None:
    """Seam 3: ``plan_approved_attestations`` validates against stamp-free events for a commit-to-target Mission."""
    feature_dir = _mission_dir(tmp_path, meta, [_STAMPED_OPEN, _STAMPED_APPROVAL])
    seen: list[bool] = []

    def _validate(requested: Any, reason: Any, *, events: Any, claim_lanes: Any) -> tuple[str, ...]:
        seen.append(any(LANE_HEAD_KEY in (event.policy_metadata or {}) for event in events))
        return ()

    monkeypatch.setattr(approved_attestation, "validate_approved_attestation_request", _validate)

    plan = approved_attestation.plan_approved_attestations(
        tmp_path, feature_dir, _manifest(), ["WP01"], "reviewed", excluded_canceled_wp_ids=(), frozen_dependency_tips=None
    )

    assert seen == [stamp_seen]
    assert plan == {}
