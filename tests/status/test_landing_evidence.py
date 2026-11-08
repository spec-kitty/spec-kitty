"""The one terminal-WP landing-evidence rule (#7433, ADR ``2026-11-06-2`` amendment 2026-11-08).

Exercised on the target's copy (:func:`landing_evidence_at_target`), the source the
``COORDINATION_BRANCH_DELETED`` remedy reads. The migration tests cover the door-routed reader.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.status.landing_evidence import LandingEvidence, LandingVerdict, landing_evidence_at_target

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _event(wp_id: str, from_lane: str, to_lane: str, at: str, actor: str = "t") -> str:
    return json.dumps(
        {
            "actor": actor,
            "at": at,
            "event_id": f"{wp_id}-{to_lane}-{at}",
            "evidence": None,
            "execution_mode": "worktree",
            "force": True,
            "from_lane": from_lane,
            "mission_slug": "m",
            "reason": None,
            "review_ref": None,
            "to_lane": to_lane,
            "wp_id": wp_id,
        }
    )


def _mission(tmp_path: Path, *lines: str) -> Path:
    feature_dir = tmp_path / "kitty-specs" / "m"
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(json.dumps({"mission_slug": "m", "topology": "lanes"}), encoding="utf-8")
    if lines:
        (feature_dir / "status.events.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return feature_dir


def test_landed_log_yields_the_latest_done_date(tmp_path: Path) -> None:
    feature_dir = _mission(
        tmp_path,
        _event("WP01", "approved", "done", "2026-01-02T00:00:00+00:00"),
        _event("WP02", "approved", "done", "2026-01-03T00:00:00Z"),
    )

    evidence = landing_evidence_at_target(tmp_path, feature_dir)

    assert evidence == LandingEvidence(LandingVerdict.LANDED, merged_at="2026-01-03T00:00:00+00:00")
    assert evidence.holds
    assert "every work package is done or canceled" in evidence.reason


def test_migration_seeded_done_does_not_set_the_date_when_a_real_done_exists(tmp_path: Path) -> None:
    """A ``migration:*`` done event (e.g. #5579's backfill) restates history near creation time;
    the date comes from the latest done event a person or the tool wrote."""
    feature_dir = _mission(
        tmp_path,
        _event("WP01", "approved", "done", "2026-09-03T00:00:00+00:00"),
        _event("WP02", "approved", "done", "2026-09-05T00:00:00+00:00", actor="migration:backfill_wp_status"),
    )

    evidence = landing_evidence_at_target(tmp_path, feature_dir)

    assert evidence == LandingEvidence(LandingVerdict.LANDED, merged_at="2026-09-03T00:00:00+00:00")


def test_only_migration_seeded_done_events_still_supply_the_date(tmp_path: Path) -> None:
    """With no other done event, the migration seed is the only date there is (operator ruling)."""
    feature_dir = _mission(
        tmp_path,
        _event("WP01", "approved", "done", "2026-08-31T00:00:01+00:00", actor="migration:backfill_wp_status"),
    )

    evidence = landing_evidence_at_target(tmp_path, feature_dir)

    assert evidence == LandingEvidence(LandingVerdict.LANDED, merged_at="2026-08-31T00:00:01+00:00")


def test_log_with_only_lifecycle_events_records_no_work_package(tmp_path: Path) -> None:
    lifecycle = json.dumps({"event_type": "MissionCreated", "event_id": "x", "timestamp": "2026-01-01T00:00:00+00:00", "payload": {}})
    feature_dir = _mission(tmp_path, lifecycle)

    evidence = landing_evidence_at_target(tmp_path, feature_dir)

    assert evidence.verdict is LandingVerdict.NO_WORK_PACKAGES
    assert not evidence.holds


def test_missing_log_is_no_status_log(tmp_path: Path) -> None:
    assert landing_evidence_at_target(tmp_path, _mission(tmp_path)).verdict is LandingVerdict.NO_STATUS_LOG


def test_unfinished_detail_names_each_open_work_package(tmp_path: Path) -> None:
    feature_dir = _mission(
        tmp_path,
        _event("WP01", "approved", "done", "2026-01-02T00:00:00+00:00"),
        _event("WP02", "planned", "in_progress", "2026-01-02T00:00:00+00:00"),
    )

    evidence = landing_evidence_at_target(tmp_path, feature_dir)

    assert (evidence.verdict, evidence.detail) == (LandingVerdict.UNFINISHED, "WP02 in_progress")
    assert evidence.reason == "not every work package is done or canceled (WP02 in_progress)"


def test_missing_mission_directory_is_unreadable_never_landed(tmp_path: Path) -> None:
    evidence = landing_evidence_at_target(tmp_path, tmp_path / "kitty-specs" / "absent")

    assert evidence.verdict is LandingVerdict.UNREADABLE
    assert evidence.detail
