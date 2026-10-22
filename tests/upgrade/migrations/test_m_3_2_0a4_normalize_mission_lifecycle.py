"""Tests for upgrade migration m_3_2_0a4_normalize_mission_lifecycle."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.status.lifecycle import generate_lifecycle_json
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.progress import generate_progress_json
from tests._support.status_seed import seed_status_event
from specify_cli.status.views import write_derived_views
from specify_cli.upgrade.migrations.m_3_2_0a4_normalize_mission_lifecycle import (
    NormalizeMissionLifecycleMigration,
)

pytestmark = pytest.mark.fast


def _write_meta(
    feature_dir: Path,
    *,
    mission_id: str | None = None,
    mission_number: int | str = "046",
) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "created_at": "2026-04-21T10:00:00+00:00",
        "friendly_name": feature_dir.name,
        "mission_number": mission_number,
        "mission_slug": feature_dir.name,
        "mission_type": "software-dev",
        "slug": feature_dir.name,
        "target_branch": "main",
    }
    if mission_id is not None:
        payload["mission_id"] = mission_id
    (feature_dir / "meta.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_task(feature_dir: Path) -> None:
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / "WP01-test.md").write_text(
        "---\n"
        "title: Test WP\n"
        "lane: in_progress\n"
        "---\n",
        encoding="utf-8",
    )


def _append_event(feature_dir: Path) -> None:
    seed_status_event(
        feature_dir,
        StatusEvent(
            event_id="01TESTUPGRADE0000000000001",
            mission_slug=feature_dir.name,
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.DONE,
            at="2026-04-21T12:00:00+00:00",
            actor="test-agent",
            force=False,
            execution_mode="worktree",
            mission_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
        ),
    )


def test_detect_returns_true_for_legacy_repo(tmp_path: Path) -> None:
    feature_dir = tmp_path / "kitty-specs" / "046-upgrade-legacy"
    (tmp_path / ".kittify").mkdir()
    _write_meta(feature_dir, mission_id=None)
    _write_task(feature_dir)

    migration = NormalizeMissionLifecycleMigration()

    assert migration.detect(tmp_path) is True


def test_detect_returns_false_for_already_normalized_repo(tmp_path: Path) -> None:
    feature_dir = tmp_path / "kitty-specs" / "046-upgrade-current"
    derived_dir = tmp_path / ".kittify" / "derived"
    (tmp_path / ".kittify").mkdir()
    _write_meta(feature_dir, mission_id="01ARZ3NDEKTSV4RRFFQ69G5FAV", mission_number=46)
    _append_event(feature_dir)
    write_derived_views(feature_dir, derived_dir)
    generate_progress_json(feature_dir, derived_dir)
    generate_lifecycle_json(feature_dir, derived_dir)

    migration = NormalizeMissionLifecycleMigration()

    assert migration.detect(tmp_path) is False


def test_apply_repairs_legacy_repo_and_reports_changes(tmp_path: Path) -> None:
    feature_dir = tmp_path / "kitty-specs" / "046-upgrade-apply"
    (tmp_path / ".kittify").mkdir()
    _write_meta(feature_dir, mission_id=None)
    _write_task(feature_dir)

    migration = NormalizeMissionLifecycleMigration()
    result = migration.apply(tmp_path, dry_run=False)

    assert result.success is True
    assert any("046-upgrade-apply" in change for change in result.changes_made)
    assert (feature_dir / "status.events.jsonl").exists()
    assert (tmp_path / ".kittify" / "derived" / "046-upgrade-apply" / "lifecycle.json").exists()
