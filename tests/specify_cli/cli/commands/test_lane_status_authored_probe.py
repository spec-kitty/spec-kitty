"""FR-045: the ``LANE_STATUS_AUTHORED`` doctor finding.

Mission ``lane-worktree-model-hardening-01M6QY1M`` WP10 (S6). A live lane
branch carries a lane-authored status change when a commit of the lane's own
(reachable from the lane, from none of the status-surface branches) touches the
Mission status files. Status bytes merged into the lane from the surface
(coordination, or the target branch of a ``lanes`` Mission) do not count, also
after the surface branch has moved on since the lane was cut.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.cli.commands._sparse_checkout_doctor import find_lane_status_authored
from specify_cli.lanes.lane_checkout import lane_mission_dir_name_from_meta
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_SLUG = "s6doc"
_MISSION_ID = "01M6QY1MBBBBBBBBBBBBBBBBBB"
_COORD = "kitty/mission-s6doc-01M6QY1M-coordination"
_LANE = "kitty/mission-s6doc-lane-a"


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout


def _commit_on(repo: Path, branch: str, rel: str, text: str, message: str) -> None:
    _git(repo, "checkout", "-q", branch)
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    _git(repo, "add", rel)
    _git(repo, "commit", "-q", "-m", message)
    _git(repo, "checkout", "-q", "main")


def _project(tmp_path: Path, *, topology: str = "lanes_with_coord", lanes: tuple[str, ...] = ("lane-a",)) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    meta: dict[str, str] = {"mission_slug": _SLUG, "mission_id": _MISSION_ID, "topology": topology, "target_branch": "main"}
    if topology == "lanes_with_coord":
        meta["coordination_branch"] = _COORD
    lane_dir = lane_mission_dir_name_from_meta(_SLUG, meta)
    primary = repo / "kitty-specs" / _SLUG
    primary.mkdir(parents=True)
    (primary / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    write_lanes_json(
        primary,
        LanesManifest(
            version=1,
            mission_slug=_SLUG,
            mission_id=_MISSION_ID,
            mission_branch="kitty/mission-s6doc-01M6QY1M",
            target_branch="main",
            lanes=[ExecutionLane(lane_id=lane, wp_ids=("WP01",), write_scope=(), predicted_surfaces=(), depends_on_lanes=(), parallel_group=0) for lane in lanes],
            computed_at="2026-11-06T12:00:00+00:00",
            computed_from="test",
        ),
    )
    status_dir = repo / "kitty-specs" / lane_dir
    status_dir.mkdir(parents=True, exist_ok=True)
    (status_dir / "status.events.jsonl").write_text('{"event_id": "E1"}\n', encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed")
    if topology == "lanes_with_coord":
        _git(repo, "branch", _COORD)
        _git(repo, "branch", _LANE, _COORD)
    return repo, lane_dir


def test_doctor_probe_ignores_merged_in_coord_bytes(tmp_path: Path) -> None:
    repo, lane_dir = _project(tmp_path)
    events = f"kitty-specs/{lane_dir}/status.events.jsonl"
    _commit_on(repo, _COORD, events, '{"event_id": "E1"}\n{"event_id": "E2"}\n', "coord status")
    _git(repo, "checkout", "-q", _LANE)
    _git(repo, "merge", "-q", "--no-edit", _COORD)
    _git(repo, "checkout", "-q", "main")

    assert find_lane_status_authored(repo) == []


def test_doctor_probe_reports_lane_authored_change(tmp_path: Path) -> None:
    repo, lane_dir = _project(tmp_path)
    events = f"kitty-specs/{lane_dir}/status.events.jsonl"
    _commit_on(repo, _LANE, events, '{"event_id": "E1"}\n{"event_id": "LANE"}\n', "hand-made lane status commit")
    _commit_on(repo, _LANE, "src.txt", "code\n", "lane code")

    findings = find_lane_status_authored(repo)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.code == "LANE_STATUS_AUTHORED"
    assert finding.lane_branch == _LANE
    assert finding.mission == _SLUG
    assert finding.paths == (events,)
    lane_status_commit = _git(repo, "log", "-1", "--format=%H", _LANE, "--", events).strip()
    assert finding.commits == (lane_status_commit,)


def test_doctor_probe_ignores_surface_status_reached_through_a_dependency_lane(tmp_path: Path) -> None:
    """B3 regression, the shape of a ``lanes`` Mission: no coordination branch, the status surface is the target.

    Lanes are cut from the Mission branch. The target then records status
    transitions; a dependency lane merges the target (the planning lane), and
    the lane merges that dependency lane. Every status byte the lane carries is
    on the target, so nothing is lane-authored, although the target moved on
    after the lane was cut and the lane's blob differs from the Mission branch.
    """
    repo, lane_dir = _project(tmp_path, topology="lanes", lanes=("lane-a", "lane-b"))
    mission_branch = "kitty/mission-s6doc-01M6QY1M"
    lane_b = "kitty/mission-s6doc-lane-b"
    events = f"kitty-specs/{lane_dir}/status.events.jsonl"
    _git(repo, "branch", mission_branch)
    _git(repo, "branch", _LANE, mission_branch)
    _git(repo, "branch", lane_b, mission_branch)
    _commit_on(repo, "main", events, '{"event_id": "E1"}\n{"event_id": "T1"}\n', "chore(spec-kitty): status transition WP01")
    _commit_on(repo, lane_b, "b.txt", "b\n", "lane-b code")
    _git(repo, "checkout", "-q", lane_b)
    _git(repo, "merge", "-q", "--no-edit", "main")
    _git(repo, "checkout", "-q", _LANE)
    _git(repo, "merge", "-q", "--no-edit", lane_b)
    _git(repo, "checkout", "-q", "main")
    _commit_on(repo, "main", events, '{"event_id": "E1"}\n{"event_id": "T1"}\n{"event_id": "T2"}\n', "chore(spec-kitty): status transition WP02")

    assert find_lane_status_authored(repo) == []

    _commit_on(repo, _LANE, events, '{"event_id": "E1"}\n{"event_id": "T1"}\n{"event_id": "LANE"}\n', "hand-made lane status commit")
    assert [finding.lane_branch for finding in find_lane_status_authored(repo)] == [_LANE]
