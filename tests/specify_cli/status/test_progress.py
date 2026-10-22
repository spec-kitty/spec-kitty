"""Tests for lane-weighted progress computation (status/progress.py)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.status.models import Lane, StatusEvent, StatusSnapshot
from specify_cli.status.progress import (
    DEFAULT_LANE_WEIGHTS,
    ProgressResult,
    WPProgress,
    compute_weighted_progress,
    generate_progress_json,
)
from specify_cli.status.reducer import reduce
from tests._support.status_seed import seed_status_event

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.unit, pytest.mark.fast]

def _make_snapshot(
    mission_slug: str,
    wp_lanes: dict[str, str],
) -> StatusSnapshot:
    """Build a StatusSnapshot directly from a WP->lane mapping."""
    work_packages = {
        wp_id: {
            "lane": lane,
            "actor": "test",
            "last_transition_at": "2026-01-01T00:00:00+00:00",
            "last_event_id": f"01TEST{wp_id}",
            "force_count": 0,
        }
        for wp_id, lane in wp_lanes.items()
    }
    summary: dict[str, int] = {lane.value: 0 for lane in Lane}
    for lane in wp_lanes.values():
        summary[lane] = summary.get(lane, 0) + 1

    return StatusSnapshot(
        mission_slug=mission_slug,
        materialized_at="2026-01-01T00:00:00+00:00",
        event_count=len(wp_lanes),
        last_event_id=None,
        work_packages=work_packages,
        summary=summary,
    )


def _make_event(
    mission_slug: str,
    wp_id: str,
    from_lane: str,
    to_lane: str,
    event_id: str,
    at: str = "2026-01-01T12:00:00+00:00",
) -> StatusEvent:
    return StatusEvent(
        event_id=event_id,
        mission_slug=mission_slug,
        wp_id=wp_id,
        from_lane=Lane(from_lane),
        to_lane=Lane(to_lane),
        at=at,
        actor="test-agent",
        force=False,
        execution_mode="worktree",
    )


# ---------------------------------------------------------------------------
# Default lane weights
# ---------------------------------------------------------------------------


def test_default_lane_weights_present():
    """DEFAULT_LANE_WEIGHTS covers every Lane enum member (full-roster map)."""
    expected_lanes = {lane.value for lane in Lane}
    assert set(DEFAULT_LANE_WEIGHTS.keys()) == expected_lanes


def test_done_weight_is_one():
    assert DEFAULT_LANE_WEIGHTS["done"] == 1.0


def test_planned_weight_is_zero():
    assert DEFAULT_LANE_WEIGHTS["planned"] == 0.0


def test_in_progress_weight_is_30_percent():
    assert DEFAULT_LANE_WEIGHTS["in_progress"] == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# Equal-weight scenarios
# ---------------------------------------------------------------------------


def test_three_done_out_of_five_is_60_percent():
    """3 done out of 5 WPs with equal weights → 60%."""
    snapshot = _make_snapshot(
        "test-feature",
        {
            "WP01": "done",
            "WP02": "done",
            "WP03": "done",
            "WP04": "planned",
            "WP05": "planned",
        },
    )
    result = compute_weighted_progress(snapshot)
    assert result.percentage == pytest.approx(60.0)
    assert result.done_count == 3
    assert result.total_count == 5


def test_all_done_is_100_percent():
    """All WPs done → 100%."""
    snapshot = _make_snapshot("test-feature", {"WP01": "done", "WP02": "done"})
    result = compute_weighted_progress(snapshot)
    assert result.percentage == pytest.approx(100.0)
    assert result.done_count == 2


def test_all_planned_is_0_percent():
    """All WPs planned → 0%."""
    snapshot = _make_snapshot("test-feature", {"WP01": "planned", "WP02": "planned"})
    result = compute_weighted_progress(snapshot)
    assert result.percentage == pytest.approx(0.0)
    assert result.done_count == 0


def test_all_in_progress_is_30_percent():
    """All WPs in_progress → ~30% (lane weight 0.3)."""
    snapshot = _make_snapshot(
        "test-feature",
        {"WP01": "in_progress", "WP02": "in_progress", "WP03": "in_progress"},
    )
    result = compute_weighted_progress(snapshot)
    assert result.percentage == pytest.approx(30.0)


def test_mixed_lanes_weighted_correctly():
    """Mix of lanes uses correct lane weights in formula."""
    # WP01 = for_review (0.6), WP02 = in_progress (0.3), WP03 = planned (0.0)
    # Expected: (0.6 + 0.3 + 0.0) / 3 * 100 = 30.0
    snapshot = _make_snapshot(
        "test-feature",
        {"WP01": "for_review", "WP02": "in_progress", "WP03": "planned"},
    )
    result = compute_weighted_progress(snapshot)
    expected = (0.6 + 0.3 + 0.0) / 3 * 100
    assert result.percentage == pytest.approx(expected)


def test_approved_lane_weight_is_80_percent():
    """Single WP in 'approved' → 80%."""
    snapshot = _make_snapshot("test-feature", {"WP01": "approved"})
    result = compute_weighted_progress(snapshot)
    assert result.percentage == pytest.approx(80.0)


def test_blocked_contributes_zero():
    """Blocked WPs do not contribute to progress."""
    # WP01=done, WP02=blocked → (1.0 + 0.0) / 2 * 100 = 50%
    snapshot = _make_snapshot("test-feature", {"WP01": "done", "WP02": "blocked"})
    result = compute_weighted_progress(snapshot)
    assert result.percentage == pytest.approx(50.0)


def test_canceled_contributes_zero():
    """Canceled WPs do not contribute to progress."""
    snapshot = _make_snapshot("test-feature", {"WP01": "done", "WP02": "canceled"})
    result = compute_weighted_progress(snapshot)
    assert result.percentage == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# Zero WPs
# ---------------------------------------------------------------------------


def test_zero_wps_returns_zero_percent():
    """Empty feature → 0%, no error."""
    snapshot = _make_snapshot("test-feature", {})
    result = compute_weighted_progress(snapshot)
    assert result.percentage == 0.0
    assert result.total_count == 0
    assert result.done_count == 0
    assert result.per_wp == []
    assert result.per_lane_counts == {}


# ---------------------------------------------------------------------------
# Custom weights
# ---------------------------------------------------------------------------


def test_custom_wp_weights_change_percentage():
    """Custom WP weights shift the result toward heavier WPs."""
    # WP01=done (weight=3), WP02=planned (weight=1)
    # Expected: (3*1.0 + 1*0.0) / (3+1) * 100 = 75%
    snapshot = _make_snapshot("test-feature", {"WP01": "done", "WP02": "planned"})
    result = compute_weighted_progress(snapshot, wp_weights={"WP01": 3.0, "WP02": 1.0})
    assert result.percentage == pytest.approx(75.0)


def test_custom_lane_weights_override_defaults():
    """Custom lane weights replace the default weights."""
    snapshot = _make_snapshot("test-feature", {"WP01": "in_progress"})
    result = compute_weighted_progress(snapshot, lane_weights={"in_progress": 0.5})
    assert result.percentage == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# ProgressResult structure
# ---------------------------------------------------------------------------


def test_per_lane_counts_populated():
    """per_lane_counts correctly tallies WPs per lane."""
    snapshot = _make_snapshot(
        "test-feature",
        {"WP01": "done", "WP02": "done", "WP03": "in_progress"},
    )
    result = compute_weighted_progress(snapshot)
    assert result.per_lane_counts["done"] == 2
    assert result.per_lane_counts["in_progress"] == 1
    assert "planned" not in result.per_lane_counts


def test_per_wp_breakdown_length():
    """per_wp contains one entry per WP."""
    snapshot = _make_snapshot("test-feature", {"WP01": "done", "WP02": "planned"})
    result = compute_weighted_progress(snapshot)
    assert len(result.per_wp) == 2


def test_per_wp_fractional_progress():
    """per_wp fractional_progress = lane_weight * wp_weight."""
    snapshot = _make_snapshot("test-feature", {"WP01": "for_review"})
    result = compute_weighted_progress(snapshot)
    wp = result.per_wp[0]
    assert wp.wp_id == "WP01"
    assert wp.lane == "for_review"
    assert wp.lane_weight == pytest.approx(0.6)
    assert wp.wp_weight == pytest.approx(1.0)
    assert wp.fractional_progress == pytest.approx(0.6)


def test_result_is_json_serialisable():
    """ProgressResult.to_dict() produces JSON-serialisable output."""
    snapshot = _make_snapshot("test-feature", {"WP01": "done", "WP02": "in_progress"})
    result = compute_weighted_progress(snapshot)
    json_str = json.dumps(result.to_dict())
    parsed = json.loads(json_str)
    assert parsed["mission_slug"] == "test-feature"
    assert "percentage" in parsed
    assert "per_wp" in parsed


def test_progress_result_to_dict_uses_mission_slug_key():
    result = ProgressResult(
        mission_slug="064-complete-mission-identity-cutover",
        percentage=12.5,
        done_count=1,
        total_count=4,
        per_lane_counts={"claimed": 1},
        per_wp=[],
    )

    payload = result.to_dict()
    assert payload["mission_slug"] == "064-complete-mission-identity-cutover"


def test_progress_result_to_dict_names_weighted_and_done_semantics():
    snapshot = _make_snapshot(
        "test-feature",
        {"WP01": "approved", "WP02": "approved"},
    )
    result = compute_weighted_progress(snapshot)

    payload = result.to_dict()

    assert payload["progress_semantics"] == "weighted_readiness"
    assert payload["percentage"] == pytest.approx(80.0)
    assert payload["weighted_percentage"] == pytest.approx(80.0)
    assert payload["done_percentage"] == pytest.approx(0.0)
    assert payload["done_count"] == 0
    assert payload["total_count"] == 2


def test_progress_result_to_dict_done_percentage_for_mixed_state():
    snapshot = _make_snapshot(
        "test-feature",
        {"WP01": "done", "WP02": "approved", "WP03": "planned"},
    )
    result = compute_weighted_progress(snapshot)

    payload = result.to_dict()

    assert payload["weighted_percentage"] == pytest.approx(60.0)
    assert payload["done_percentage"] == pytest.approx(33.3333)


def test_progress_result_to_dict_empty_state_has_zero_done_and_weighted_percentages():
    result = compute_weighted_progress(_make_snapshot("test-feature", {}))

    payload = result.to_dict()

    assert payload["progress_semantics"] == "weighted_readiness"
    assert payload["weighted_percentage"] == 0.0
    assert payload["done_percentage"] == 0.0


# ---------------------------------------------------------------------------
# generate_progress_json integration
# ---------------------------------------------------------------------------


def test_generate_progress_json_writes_file(tmp_path):
    """generate_progress_json writes progress.json to derived_dir/<slug>/."""
    feature_dir = tmp_path / "kitty-specs" / "001-test-feature"
    feature_dir.mkdir(parents=True)

    # Add events so reducer has data
    event = _make_event("001-test-feature", "WP01", "planned", "done", "01TESTAAAAAAAAAAAAAAAAAAA1")
    seed_status_event(feature_dir, event)

    derived_dir = tmp_path / ".kittify" / "derived"
    generate_progress_json(feature_dir, derived_dir)

    progress_file = derived_dir / "001-test-feature" / "progress.json"
    assert progress_file.exists()
    data = json.loads(progress_file.read_text())
    assert data["mission_slug"] == "001-test-feature"
    assert data["percentage"] == pytest.approx(100.0)


def test_generate_progress_json_empty_feature(tmp_path):
    """generate_progress_json handles features with no events (0%)."""
    feature_dir = tmp_path / "kitty-specs" / "002-empty"
    feature_dir.mkdir(parents=True)

    derived_dir = tmp_path / ".kittify" / "derived"
    generate_progress_json(feature_dir, derived_dir)

    progress_file = derived_dir / "002-empty" / "progress.json"
    assert progress_file.exists()
    data = json.loads(progress_file.read_text())
    assert data["percentage"] == 0.0
    assert data["total_count"] == 0


def test_generate_progress_json_falls_back_to_feature_dir_name_when_snapshot_slug_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import specify_cli.status.progress as progress_module

    feature_dir = tmp_path / "kitty-specs" / "064-complete-mission-identity-cutover"
    feature_dir.mkdir(parents=True)
    derived_dir = tmp_path / ".kittify" / "derived"

    snapshot = StatusSnapshot(
        mission_slug="",
        materialized_at="2026-01-01T00:00:00+00:00",
        event_count=0,
        last_event_id=None,
        work_packages={},
        summary={lane.value: 0 for lane in Lane},
    )
    monkeypatch.setattr(progress_module, "materialize", lambda _: snapshot)

    generate_progress_json(feature_dir, derived_dir)

    progress_file = derived_dir / "064-complete-mission-identity-cutover" / "progress.json"
    assert progress_file.exists()
