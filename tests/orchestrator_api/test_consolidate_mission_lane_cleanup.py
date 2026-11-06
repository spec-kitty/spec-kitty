"""``orchestrator-api consolidate-mission`` reports per-lane cleanup outcomes (S5, FR-039a, SC-012, contract 1.24.0).

The orchestrator path and ``spec-kitty consolidate`` share one lane-cleanup module, so the same
Mission shape yields the same per-lane outcome on both. Driven through the REAL CLI over real git.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tests.consolidation.test_lane_cleanup_kept_report import (
    add_lane_worktrees,
    consolidate_args,
    lane_branch,
    lane_cleanup_block,
    lane_cleanup_json,
    lane_worktree,
    output,
    ref_exists,
)
from tests.terminus.conftest import CoordMission, build_coord_mission, run_terminus

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_OUTCOME_WORDS = {"Removed": "removed", "Kept": "kept", "Retained": "retained_by_policy"}


def _build(tmp_path: Path, mid8: str) -> CoordMission:
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8=mid8)
    add_lane_worktrees(mission, ("lane-a",))
    return mission


def _executor_outcomes(result: subprocess.CompletedProcess[str]) -> list[tuple[str, str]]:
    pairs = []
    for line in lane_cleanup_block(result):
        word, lane_id = line.split()[:2]
        if word in _OUTCOME_WORDS:
            pairs.append((lane_id, _OUTCOME_WORDS[word]))
    return pairs


def test_orchestrator_and_executor_same_lane_outcome(tmp_path: Path) -> None:
    host_mission = _build(tmp_path / "host", "01M7280G")
    host = run_terminus(host_mission, consolidate_args(host_mission))
    assert host.returncode == 0, output(host)

    api_mission = _build(tmp_path / "api", "01M7280H")
    api = run_terminus(api_mission, ["orchestrator-api", "consolidate-mission", "--mission", api_mission.slug])
    assert api.returncode == 0, output(api)

    envelope = json.loads([line for line in api.stdout.splitlines() if line.strip().startswith("{")][-1])
    assert envelope["contract_version"] == "1.24.0", envelope
    assert envelope["success"] is True, envelope
    cleanup = lane_cleanup_json(api)
    api_outcomes = [(str(entry["lane_id"]), str(entry["outcome"])) for entry in cleanup]
    assert api_outcomes == _executor_outcomes(host), f"{output(host)}\n{envelope}"
    assert api_outcomes == [("lane-a", "removed"), ("lane-b", "removed")]
    for entry in cleanup:
        assert set(entry) == {"lane_id", "branch", "worktree", "outcome", "code", "remedy", "command", "recreate"}, entry
    assert not lane_worktree(api_mission, "lane-a").exists(), output(api)
    for lane_id in ("lane-a", "lane-b"):
        assert not ref_exists(api_mission.repo, f"refs/heads/{lane_branch(api_mission, lane_id)}"), output(api)
