"""WP-status backfill: the snapshot must carry every WP file (#5579).

The reduced snapshot omits WPs that have no lane events (ADR 2026-06-07-3), so a
Mission whose log seeds only some WPs under-counts on every read surface that
lists WPs from ``tasks/WP*.md``. These tests pin the canonical repair.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.migration import backfill_runtime_state as b
from specify_cli.status.reducer import materialize_snapshot

pytestmark = [pytest.mark.fast]

MISSION_ID = "01JMISSIONULID0000000000BB"
SLUG = "demo-mission-01JMISSI"
PLANNED_SEED_ID = "01AAAAAAAAAAAAAAAAAAAAAAB1"
SEED_AT = "2026-01-02T03:04:05+00:00"


def _write_wp_file(tasks_dir: Path, wp_id: str) -> None:
    (tasks_dir / f"{wp_id}-demo.md").write_text(
        f"---\nwork_package_id: {wp_id}\ntitle: Demo {wp_id}\nexecution_mode: code_change\n---\n\n# {wp_id}\n",
        encoding="utf-8",
    )


def _planned_row(wp_id: str, event_id: str) -> dict[str, object]:
    return {
        "event_id": event_id,
        "mission_slug": SLUG,
        "mission_id": MISSION_ID,
        "wp_id": wp_id,
        "from_lane": "genesis",
        "to_lane": "planned",
        "at": SEED_AT,
        "actor": "tester",
        "force": False,
        "execution_mode": "worktree",
    }


def _build_mission(tmp_path: Path, *, wp_ids: tuple[str, ...], seeded: tuple[str, ...]) -> Path:
    """Create ``kitty-specs/<slug>`` with *wp_ids* files and planned seeds for *seeded* only."""
    feature_dir = tmp_path / "kitty-specs" / SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_id": MISSION_ID, "mission_slug": SLUG, "mission_type": "software-dev"}),
        encoding="utf-8",
    )
    for wp_id in wp_ids:
        _write_wp_file(tasks_dir, wp_id)
    if seeded:
        rows = [_planned_row(wp_id, f"01AAAAAAAAAAAAAAAAAAAAAAB{index}") for index, wp_id in enumerate(seeded, start=1)]
        (feature_dir / "status.events.jsonl").write_text(
            "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
            encoding="utf-8",
        )
    return feature_dir


@pytest.mark.regression
def test_issue_5579_repair_makes_snapshot_count_every_wp_file(tmp_path: Path) -> None:
    """#5579: a log seeding only WP01 leaves WP02/WP03 out of the snapshot; the repair fixes it."""
    feature_dir = _build_mission(tmp_path, wp_ids=("WP01", "WP02", "WP03"), seeded=("WP01",))
    assert set(materialize_snapshot(feature_dir).work_packages) == {"WP01"}

    result = b.apply_wp_status_backfill(feature_dir, dry_run=False, evidence=None)

    assert result.error is None
    assert set(materialize_snapshot(feature_dir).work_packages) == {"WP01", "WP02", "WP03"}
