"""Cancellation provenance in the ``next`` WP advancement gate."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.fast


def _write_canceled_wp(feature_dir: Path, *, reason_source: str) -> None:
    events: list[dict[str, Any]] = [
        {
            "actor": "test",
            "at": "2026-08-31T10:00:00+00:00",
            "event_id": "01TESTWP01PLANNED",
            "evidence": None,
            "execution_mode": "worktree",
            "feature_slug": "test-feature",
            "force": False,
            "from_lane": "planned",
            "reason": None,
            "review_ref": None,
            "to_lane": "planned",
            "wp_id": "WP01",
        },
        {
            "actor": "test",
            "at": "2026-08-31T10:01:00+00:00",
            "event_id": "01TESTWP01CANCELED",
            "evidence": None,
            "execution_mode": "worktree",
            "feature_slug": "test-feature",
            "force": False,
            "from_lane": "planned",
            "reason": "Operator chose to drop this work package",
            "reason_source": reason_source,
            "review_ref": None,
            "to_lane": "canceled",
            "wp_id": "WP01",
        },
    ]
    events_path = feature_dir / "status.events.jsonl"
    events_path.write_text(
        "".join(json.dumps(event) + "\n" for event in events),
        encoding="utf-8",
    )


@pytest.fixture()
def feature_dir(tmp_path: Path) -> Path:
    mission_dir = tmp_path / "kitty-specs" / "test-feature"
    tasks_dir = mission_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "WP01-test-task.md").write_text(
        "---\nwork_package_id: WP01\ntitle: Test WP\ndependencies: []\n---\nContent.\n",
        encoding="utf-8",
    )
    return mission_dir


def test_operator_canceled_wp_advances_review(feature_dir: Path) -> None:
    _write_canceled_wp(feature_dir, reason_source="operator")

    from runtime.next.runtime_bridge_guards import _should_advance_wp_step

    assert _should_advance_wp_step("review", feature_dir) is True


def test_synthetic_canceled_wp_blocks_review_but_advances_implement(feature_dir: Path) -> None:
    _write_canceled_wp(feature_dir, reason_source="synthetic")

    from runtime.next.runtime_bridge_guards import _should_advance_wp_step

    assert _should_advance_wp_step("review", feature_dir) is False
    assert _should_advance_wp_step("implement", feature_dir) is True


def test_operator_canceled_wp_does_not_hide_another_active_wp(feature_dir: Path) -> None:
    _write_canceled_wp(feature_dir, reason_source="operator")
    tasks_dir = feature_dir / "tasks"
    (tasks_dir / "WP02-test-task.md").write_text(
        "---\nwork_package_id: WP02\ntitle: Active WP\ndependencies: []\n---\nContent.\n",
        encoding="utf-8",
    )

    from runtime.next.runtime_bridge_guards import _should_advance_wp_step

    assert _should_advance_wp_step("review", feature_dir) is False
