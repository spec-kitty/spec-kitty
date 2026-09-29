"""Smoke test for the LANES real-CLI fixture builder (WP02 / T011)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mission_runtime.context import MissionTopology
from mission_runtime.resolution import resolve_topology
from tests.terminus.conftest import git_rev, run_terminus
from tests.terminus.lanes_fixture import build_lanes_mission

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def test_lanes_fixture_resolves_lanes_topology_without_coordination_branch(tmp_path: Path) -> None:
    mission = build_lanes_mission(tmp_path, wps=("WP01", "WP02"))

    assert resolve_topology(mission.repo, mission.slug) is MissionTopology.LANES
    meta = json.loads((mission.feature_dir / "meta.json").read_text())
    assert "coordination_branch" not in meta
    assert git_rev(mission.repo, mission.coord_branch)  # the MISSION branch exists
    assert all(git_rev(mission.repo, b) for b in mission.lane_branches.values())
    assert mission.target_branch == "develop"


def test_lanes_fixture_consolidate_dry_run_exits_zero(tmp_path: Path) -> None:
    mission = build_lanes_mission(tmp_path)
    # run_terminus runs `python -m specify_cli` with PYTHONPATH=<this worktree>/src (conftest._SRC).
    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--dry-run"])
    assert result.returncode == 0, result.stdout + result.stderr


def test_planning_lane_variant_leaves_planning_wp_claimable(tmp_path: Path) -> None:
    mission = build_lanes_mission(tmp_path, with_planning_lane_wp=True, planning_depends_on_code=False, approve_planning_wp=False)
    manifest = json.loads((mission.feature_dir / "lanes.json").read_text())
    assert [lane["lane_id"] for lane in manifest["lanes"]] == ["lane-a", "lane-planning"]
    events = (mission.feature_dir / "status.events.jsonl").read_text()
    assert '"wp_id": "WP02"' not in events and '"wp_id": "WP01"' in events
    assert resolve_topology(mission.repo, mission.slug) is MissionTopology.LANES
