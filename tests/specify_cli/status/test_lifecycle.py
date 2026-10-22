"""Tests for canonical mission lifecycle derivation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kernel.clock import UTC, datetime, timedelta
from specify_cli.status.lifecycle import (
    derive_mission_lifecycle,
    generate_lifecycle_json,
    is_mission_completed,
)
from specify_cli.status.models import Lane, StatusEvent
from tests._support.status_seed import seed_status_event

pytestmark = pytest.mark.fast


def _write_meta(
    feature_dir: Path,
    *,
    mission_id: str = "01ARZ3NDEKTSV4RRFFQ69G5FAV",
    created_at: str = "2026-04-01T10:00:00+00:00",
    merged_at: str | None = None,
) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, object] = {
        "created_at": created_at,
        "friendly_name": feature_dir.name,
        "mission_id": mission_id,
        "mission_number": int(feature_dir.name.split("-", 1)[0]),
        "mission_slug": feature_dir.name,
        "mission_type": "software-dev",
        "slug": feature_dir.name,
        "target_branch": "main",
    }
    if merged_at is not None:
        meta["merged_at"] = merged_at
        meta["merged_into"] = "main"
    (feature_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _append_event(
    feature_dir: Path,
    *,
    wp_id: str,
    to_lane: str,
    at: str,
    event_id: str,
    from_lane: str = "planned",
) -> None:
    seed_status_event(
        feature_dir,
        StatusEvent(
            event_id=event_id,
            mission_slug=feature_dir.name,
            wp_id=wp_id,
            from_lane=Lane(from_lane),
            to_lane=Lane(to_lane),
            at=at,
            actor="test-agent",
            force=False,
            execution_mode="worktree",
            mission_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
        ),
    )


def test_derive_active_state_from_recent_in_progress_work(tmp_path: Path) -> None:
    now = datetime(2026, 4, 22, 12, 0, tzinfo=UTC)
    feature_dir = tmp_path / "kitty-specs" / "034-active"
    _write_meta(feature_dir)
    _append_event(
        feature_dir,
        wp_id="WP01",
        to_lane="in_progress",
        at="2026-04-21T12:00:00+00:00",
        event_id="01TESTACTIVE00000000000001",
    )

    result = derive_mission_lifecycle(feature_dir, now=now)

    assert result.state == "active"
    assert result.surface_state == "active"
    assert result.active_wp_count == 1
    assert result.completion_pct == pytest.approx(30.0)


def test_derive_recently_completed_and_archived_states(tmp_path: Path) -> None:
    root = tmp_path / "kitty-specs"
    recent_dir = root / "035-recent"
    archived_dir = root / "036-archived"
    _write_meta(recent_dir)
    _write_meta(archived_dir)
    _append_event(
        recent_dir,
        wp_id="WP01",
        to_lane="done",
        at="2026-04-21T12:00:00+00:00",
        event_id="01TESTCOMPLETE000000000001",
    )
    _append_event(
        archived_dir,
        wp_id="WP01",
        to_lane="done",
        at="2026-04-10T12:00:00+00:00",
        event_id="01TESTCOMPLETE000000000002",
    )

    now = datetime(2026, 4, 22, 12, 0, tzinfo=UTC)
    recent = derive_mission_lifecycle(recent_dir, now=now)
    archived = derive_mission_lifecycle(archived_dir, now=now)

    assert recent.state == "recently_completed"
    assert recent.surface_state == "recently_completed"
    assert archived.state == "archived"
    assert archived.surface_state is None


def test_derive_stale_and_abandoned_states_for_old_active_work(tmp_path: Path) -> None:
    root = tmp_path / "kitty-specs"
    stale_dir = root / "037-stale"
    abandoned_dir = root / "038-abandoned"
    _write_meta(stale_dir)
    _write_meta(abandoned_dir)
    _append_event(
        stale_dir,
        wp_id="WP01",
        to_lane="for_review",
        at="2026-04-05T12:00:00+00:00",
        event_id="01TESTSTALE000000000000001",
    )
    _append_event(
        abandoned_dir,
        wp_id="WP01",
        to_lane="blocked",
        at="2026-03-20T12:00:00+00:00",
        event_id="01TESTSTALE000000000000002",
    )

    now = datetime(2026, 4, 22, 12, 0, tzinfo=UTC)
    stale = derive_mission_lifecycle(stale_dir, now=now)
    abandoned = derive_mission_lifecycle(abandoned_dir, now=now)

    assert stale.state == "stale"
    assert stale.surface_state is None
    assert abandoned.state == "abandoned"
    assert abandoned.surface_state is None


def test_derive_recoverable_state_from_meta_when_event_log_missing(tmp_path: Path) -> None:
    feature_dir = tmp_path / "kitty-specs" / "039-recoverable"
    created_at = (datetime(2026, 4, 22, 12, 0, tzinfo=UTC) - timedelta(days=2)).isoformat()
    _write_meta(feature_dir, created_at=created_at)

    result = derive_mission_lifecycle(
        feature_dir,
        now=datetime(2026, 4, 22, 12, 0, tzinfo=UTC),
    )

    assert result.state == "recoverable"
    assert result.has_event_log is False
    assert result.total_wps == 0


def test_generate_lifecycle_json_writes_machine_facing_file(tmp_path: Path) -> None:
    feature_dir = tmp_path / "kitty-specs" / "040-derived"
    _write_meta(feature_dir)
    _append_event(
        feature_dir,
        wp_id="WP01",
        to_lane="claimed",
        at="2026-04-21T08:00:00+00:00",
        event_id="01TESTDERIVED0000000000001",
    )

    derived_dir = tmp_path / ".kittify" / "derived"
    generate_lifecycle_json(
        feature_dir,
        derived_dir,
        now=datetime(2026, 4, 22, 12, 0, tzinfo=UTC),
    )

    data = json.loads((derived_dir / "040-derived" / "lifecycle.json").read_text(encoding="utf-8"))
    assert data["mission_slug"] == "040-derived"
    assert data["state"] == "active"
    assert data["surface_state"] == "active"


# ---------------------------------------------------------------------------
# is_mission_completed predicate (#1926): the post-mission-event precondition.
# ---------------------------------------------------------------------------


def test_is_mission_completed_true_when_merged_at_present(tmp_path: Path) -> None:
    feature_dir = tmp_path / "kitty-specs" / "050-merged"
    _write_meta(feature_dir, merged_at="2026-04-03T10:00:00+00:00")
    # No event log at all, but the merge marker alone signals completion.
    assert is_mission_completed(feature_dir) is True


def test_is_mission_completed_true_when_all_wps_terminal(tmp_path: Path) -> None:
    feature_dir = tmp_path / "kitty-specs" / "051-terminal"
    _write_meta(feature_dir)  # no merge marker
    _append_event(
        feature_dir,
        wp_id="WP01",
        to_lane="done",
        at="2026-04-21T12:00:00+00:00",
        event_id="01TESTTERMINAL0000000000001",
        from_lane="approved",
    )
    # recently_completed / archived both classify as completed.
    assert is_mission_completed(
        feature_dir, now=datetime(2026, 4, 22, 12, 0, tzinfo=UTC)
    ) is True


def test_is_mission_completed_false_for_active_wip(tmp_path: Path) -> None:
    feature_dir = tmp_path / "kitty-specs" / "052-wip"
    _write_meta(feature_dir)  # no merge marker
    _append_event(
        feature_dir,
        wp_id="WP01",
        to_lane="in_progress",
        at="2026-04-21T12:00:00+00:00",
        event_id="01TESTWIP000000000000000001",
    )
    assert is_mission_completed(
        feature_dir, now=datetime(2026, 4, 22, 12, 0, tzinfo=UTC)
    ) is False


def test_is_mission_completed_false_for_recoverable_no_events(tmp_path: Path) -> None:
    feature_dir = tmp_path / "kitty-specs" / "053-recoverable"
    _write_meta(feature_dir)  # no merge marker, no events → recoverable
    assert is_mission_completed(
        feature_dir, now=datetime(2026, 4, 22, 12, 0, tzinfo=UTC)
    ) is False


def test_lifecycle_carries_mission_id(tmp_path: Path) -> None:
    """#2331: the derived lifecycle + lifecycle.json expose the canonical ULID,
    so a consumer can re-link a mission to its identity from a materialized view."""
    ulid = "01KWN9D0MJ79NK1T90RWYY2Y7R"
    feature_dir = tmp_path / "kitty-specs" / "054-carries-id"
    _write_meta(feature_dir, mission_id=ulid)

    result = derive_mission_lifecycle(
        feature_dir, now=datetime(2026, 4, 22, 12, 0, tzinfo=UTC)
    )
    assert result.mission_id == ulid
    assert result.to_dict()["mission_id"] == ulid

    derived_dir = tmp_path / ".kittify" / "derived"
    generate_lifecycle_json(
        feature_dir, derived_dir, now=datetime(2026, 4, 22, 12, 0, tzinfo=UTC)
    )
    written = json.loads(
        (derived_dir / "054-carries-id" / "lifecycle.json").read_text(encoding="utf-8")
    )
    assert written["mission_id"] == ulid
