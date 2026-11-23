"""``orchestrator-api consolidate-mission`` reports per-lane cleanup outcomes (S5, FR-039a, SC-012, contract 1.25.0).

The orchestrator path and ``spec-kitty consolidate`` share one lane-cleanup module, so the same
Mission shape yields the same per-lane outcome on both (the 1.25.0 value itself is pinned in
``tests/specify_cli/orchestrator_api/test_contract_version.py``). Driven through the REAL CLI over real git.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.orchestrator_api.envelope import CONTRACT_VERSION
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


def _build(tmp_path: Path, mid8: str, worktrees: tuple[str, ...] = ("lane-a", "lane-b")) -> CoordMission:
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8=mid8)
    # #7325: a lane is removed only through the landing proof, which needs its worktree;
    # a worktree-less lane is kept on both paths alike (LANDING_PROOF_UNAVAILABLE).
    add_lane_worktrees(mission, worktrees)
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
    assert envelope["contract_version"] == CONTRACT_VERSION, envelope
    assert envelope["success"] is True, envelope
    cleanup = lane_cleanup_json(api)
    api_outcomes = [(str(entry["lane_id"]), str(entry["outcome"])) for entry in cleanup]
    assert api_outcomes == _executor_outcomes(host), f"{output(host)}\n{envelope}"
    assert api_outcomes == [("lane-a", "removed"), ("lane-b", "removed")]
    for entry in cleanup:
        assert set(entry) == {"lane_id", "branch", "worktree", "outcome", "code", "remedy", "command", "recreate"}, entry
    for lane_id in ("lane-a", "lane-b"):
        assert not lane_worktree(api_mission, lane_id).exists(), output(api)
        assert not ref_exists(api_mission.repo, f"refs/heads/{lane_branch(api_mission, lane_id)}"), output(api)


def test_orchestrator_and_executor_keep_a_worktreeless_lane_alike(tmp_path: Path) -> None:
    """#7325 kept-case parity: lane-a has a worktree, lane-b has none; both paths keep lane-b the same way."""
    host_mission = _build(tmp_path / "host", "01M7280J", worktrees=("lane-a",))
    host = run_terminus(host_mission, consolidate_args(host_mission))
    assert host.returncode == 0, output(host)

    api_mission = _build(tmp_path / "api", "01M7280K", worktrees=("lane-a",))
    api = run_terminus(api_mission, ["orchestrator-api", "consolidate-mission", "--mission", api_mission.slug])
    assert api.returncode == 0, output(api)

    cleanup = lane_cleanup_json(api)
    api_outcomes = [(str(entry["lane_id"]), str(entry["outcome"])) for entry in cleanup]
    assert api_outcomes == _executor_outcomes(host), f"{output(host)}\n{cleanup}"
    assert api_outcomes == [("lane-a", "removed"), ("lane-b", "kept")]
    [kept] = [entry for entry in cleanup if entry["lane_id"] == "lane-b"]
    assert kept["code"] == "LANDING_PROOF_UNAVAILABLE" and kept["command"] is None, kept
    assert "LANDING_PROOF_UNAVAILABLE" in "\n".join(lane_cleanup_block(host)), output(host)
    assert "then run: None" not in output(host)
    for mission in (host_mission, api_mission):
        assert ref_exists(mission.repo, f"refs/heads/{lane_branch(mission, 'lane-b')}"), output(api)
