"""orchestrator-api ``accept-mission`` / ``consolidate-mission`` refuse on stale origin evidence (FR-004/FR-008/FR-009).

Drives the REAL orchestrator CLI against a real bare remote and a second clone
that pushed ahead. The refusal envelope keeps its existing codes
(``MISSION_NOT_READY`` / ``PREFLIGHT_FAILED``) and gains additive
``data.preflight_error_code(s)`` and ``data.origin_freshness`` (contract 1.11.0).
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.terminus.conftest import CoordMission, _event, build_coord_mission, run_terminus
from tests.terminus.lanes_fixture import build_lanes_mission
from tests._support.two_clone import attach_and_push, clone_from, isolated_git_env, make_bare_remote, unreachable_remote

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_STATUS_LOG = "status.events.jsonl"
_ORIGIN_CODES = ("ORIGIN_STATUS_STALE", "ORIGIN_LANE_STALE", "ORIGIN_UNREACHABLE")
_CONTRACT_VERSION = "1.11.0"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


@dataclass
class World:
    mission: CoordMission
    bare: Path
    second: Path

    def push_ahead(self, branch: str, *, status_event: bool = False) -> None:
        """Clone B commits on *branch* (a status event or a code file) and pushes it."""
        _git(self.second, "fetch", "-q", "origin", branch)
        _git(self.second, "checkout", "-q", "-B", branch, f"origin/{branch}")
        if status_event:
            log = self.second / "kitty-specs" / self.mission.slug / _STATUS_LOG
            line = json.dumps(_event(self.mission, "WP01", "approved", "planned"), sort_keys=True)
            log.write_text(log.read_text(encoding="utf-8") + line + "\n", encoding="utf-8")
            _git(self.second, "add", str(log.relative_to(self.second)))
        else:
            (self.second / "src" / "pkg" / "teammate.py").write_text("x = 1\n", encoding="utf-8")
            _git(self.second, "add", "src/pkg/teammate.py")
        _git(self.second, "commit", "-q", "-m", f"teammate work on {branch}")
        _git(self.second, "push", "-q", "origin", f"{branch}:{branch}")


def _world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, lanes: bool) -> World:
    isolated_git_env(monkeypatch, tmp_path)
    mission = build_lanes_mission(tmp_path / "m", wps=("WP01",)) if lanes else build_coord_mission(tmp_path / "m", wps=("WP01",))
    bare = make_bare_remote(tmp_path)
    attach_and_push(mission.repo, bare, [mission.target_branch, mission.coord_branch, *mission.lane_branches.values()])
    _git(bare, "symbolic-ref", "HEAD", f"refs/heads/{mission.target_branch}")
    return World(mission=mission, bare=bare, second=clone_from(bare, tmp_path / "second"))


@pytest.fixture
def coord_world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> World:
    return _world(tmp_path, monkeypatch, lanes=False)


@pytest.fixture
def lanes_world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> World:
    return _world(tmp_path, monkeypatch, lanes=True)


def _invoke(world: World, verb: str, *extra: str, env: dict[str, str] | None = None) -> dict[str, object]:
    return _invoke_with_stderr(world, verb, *extra, env=env)[0]


def _invoke_with_stderr(world: World, verb: str, *extra: str, env: dict[str, str] | None = None) -> tuple[dict[str, object], str]:
    args = ["orchestrator-api", verb, "--mission", world.mission.slug, *extra]
    if verb == "accept-mission":
        args += ["--actor", "test-orchestrator"]
    result = run_terminus(world.mission, args, env=env)
    lines = [line for line in result.stdout.splitlines() if line.startswith("{")]
    assert lines, f"no JSON envelope\nstdout={result.stdout}\nstderr={result.stderr}"
    envelope: dict[str, object] = json.loads(lines[0])
    return envelope, result.stderr


def _data(envelope: dict[str, object]) -> dict[str, object]:
    data = envelope["data"]
    assert isinstance(data, dict)
    return data


def _origin_codes_of(envelope: dict[str, object]) -> list[str]:
    data = _data(envelope)
    codes = data.get("preflight_error_codes", [])
    assert isinstance(codes, list)
    return [code for code in codes if code in _ORIGIN_CODES]


def _freshness(envelope: dict[str, object]) -> list[dict[str, object]]:
    rows = _data(envelope)["origin_freshness"]
    assert isinstance(rows, list)
    return rows


# --------------------------------------------------------------------------- accept-mission


def test_accept_mission_refuses_stale_status_evidence(coord_world: World) -> None:
    coord_world.push_ahead(coord_world.mission.coord_branch, status_event=True)

    envelope = _invoke(coord_world, "accept-mission")

    data = _data(envelope)
    assert envelope["success"] is False
    assert envelope["error_code"] == "MISSION_NOT_READY"
    assert envelope["contract_version"] == _CONTRACT_VERSION
    assert data["preflight_error_code"] == "ORIGIN_STATUS_STALE"
    assert data["preflight_error_codes"] == ["ORIGIN_STATUS_STALE"]
    assert _freshness(envelope)[0]["state"] == "behind"
    assert _freshness(envelope)[0]["branch"] == coord_world.mission.coord_branch
    assert "--origin-check warn" in str(data["errors"])


def test_accept_mission_up_to_date_control_is_not_refused_for_freshness(coord_world: World) -> None:
    envelope = _invoke(coord_world, "accept-mission")

    assert _origin_codes_of(envelope) == []
    assert _data(envelope).get("preflight_error_code") not in _ORIGIN_CODES


def test_accept_mission_refuses_when_the_remote_is_unreachable(coord_world: World) -> None:
    unreachable_remote(coord_world.mission.repo)

    envelope = _invoke(coord_world, "accept-mission")

    assert envelope["error_code"] == "MISSION_NOT_READY"
    assert _data(envelope)["preflight_error_code"] == "ORIGIN_UNREACHABLE"
    assert _freshness(envelope)[0]["state"] == "unreachable"
    assert _freshness(envelope)[0]["detail"], "an unreachable row says why the remote could not be reached"


def test_accept_mission_warn_opt_out_is_not_refused_for_freshness(coord_world: World) -> None:
    coord_world.push_ahead(coord_world.mission.coord_branch, status_event=True)

    envelope, stderr = _invoke_with_stderr(coord_world, "accept-mission", "--origin-check", "warn")

    assert _data(envelope).get("preflight_error_code") not in _ORIGIN_CODES
    assert "Warning:" in stderr and coord_world.mission.coord_branch in stderr, "warn mode must surface the freshness warning on stderr"


def test_accept_mission_environment_opt_out_is_not_refused_for_freshness(coord_world: World) -> None:
    coord_world.push_ahead(coord_world.mission.coord_branch, status_event=True)

    envelope = _invoke(coord_world, "accept-mission", env={"SPEC_KITTY_ORIGIN_CHECK": "warn"})

    assert _data(envelope).get("preflight_error_code") not in _ORIGIN_CODES


# --------------------------------------------------------------------------- consolidate-mission


def test_consolidate_mission_refuses_stale_status_evidence(coord_world: World) -> None:
    coord_world.push_ahead(coord_world.mission.coord_branch, status_event=True)

    envelope = _invoke(coord_world, "consolidate-mission")

    data = _data(envelope)
    assert envelope["success"] is False
    assert envelope["error_code"] == "PREFLIGHT_FAILED"
    assert envelope["contract_version"] == _CONTRACT_VERSION
    assert data["preflight_error_code"] == "ORIGIN_STATUS_STALE"
    assert _origin_codes_of(envelope)[0] == "ORIGIN_STATUS_STALE"
    assert data["target_branch"] == coord_world.mission.target_branch
    assert _freshness(envelope)[0]["state"] == "behind"


def test_consolidate_mission_refuses_a_stale_approved_lane(lanes_world: World) -> None:
    lane = lanes_world.mission.lane_branches["WP01"]
    lanes_world.push_ahead(lane)

    envelope = _invoke(lanes_world, "consolidate-mission")

    assert envelope["error_code"] == "PREFLIGHT_FAILED"
    assert _data(envelope)["preflight_error_code"] == "ORIGIN_LANE_STALE"
    rows = {str(row["branch"]): row for row in _freshness(envelope)}
    assert rows[lane]["state"] == "behind"


def test_consolidate_mission_reports_every_origin_code_evidence_first(lanes_world: World) -> None:
    lanes_world.push_ahead(lanes_world.mission.target_branch, status_event=True)
    lanes_world.push_ahead(lanes_world.mission.lane_branches["WP01"])

    envelope = _invoke(lanes_world, "consolidate-mission")

    data = _data(envelope)
    assert data["preflight_error_codes"] == ["ORIGIN_STATUS_STALE", "ORIGIN_LANE_STALE"]
    assert data["preflight_error_code"] == "ORIGIN_STATUS_STALE"


def test_consolidate_mission_up_to_date_control_is_not_refused_for_freshness(lanes_world: World) -> None:
    envelope = _invoke(lanes_world, "consolidate-mission")

    assert _origin_codes_of(envelope) == []


def test_consolidate_mission_refuses_when_the_remote_is_unreachable(lanes_world: World) -> None:
    unreachable_remote(lanes_world.mission.repo)

    envelope = _invoke(lanes_world, "consolidate-mission")

    assert envelope["error_code"] == "PREFLIGHT_FAILED"
    assert _data(envelope)["preflight_error_code"] == "ORIGIN_UNREACHABLE"
    assert {row["state"] for row in _freshness(envelope)} == {"unreachable"}
    assert all(row["detail"] for row in _freshness(envelope))
    assert _data(envelope)["target_branch"] == lanes_world.mission.target_branch


def test_consolidate_mission_warn_opt_out_is_not_refused_for_freshness(lanes_world: World) -> None:
    lanes_world.push_ahead(lanes_world.mission.lane_branches["WP01"])

    envelope, stderr = _invoke_with_stderr(lanes_world, "consolidate-mission", "--origin-check", "warn")

    assert _origin_codes_of(envelope) == []
    lane = lanes_world.mission.lane_branches["WP01"]
    assert "Warning:" in stderr and lane in stderr, "warn mode must surface the freshness warning on stderr, not silently pass"


# --------------------------------------------------------------------------- planning-only consolidate-mission


def _make_planning_only(world: World) -> None:
    """Rewrite ``lanes.json`` to a single planning lane so the Mission takes the planning-only closeout path."""
    from dataclasses import replace

    from specify_cli.lanes.models import ExecutionLane
    from specify_cli.lanes.persistence import read_lanes_json, write_lanes_json

    mission = world.mission
    manifest = read_lanes_json(mission.feature_dir)
    assert manifest is not None
    planning = ExecutionLane(
        lane_id="lane-planning",
        wp_ids=("WP01",),
        write_scope=(f"kitty-specs/{mission.slug}/**",),
        predicted_surfaces=("planning",),
        depends_on_lanes=(),
        parallel_group=0,
    )
    write_lanes_json(mission.feature_dir, replace(manifest, lanes=[planning]))
    _git(mission.repo, "add", "-A")
    _git(mission.repo, "commit", "-q", "-m", "lanes: planning only")


def _ls_remote_calls(trace: Path) -> int:
    return sum(1 for line in trace.read_text(encoding="utf-8").splitlines() if " ls-remote " in f"{line} ")


def test_consolidate_mission_planning_only_honours_warn_and_contacts_origin_once(lanes_world: World, tmp_path: Path) -> None:
    """The planning-only closeout re-enters the executor: it must neither ignore ``--origin-check warn`` nor gate twice."""
    _make_planning_only(lanes_world)
    lanes_world.push_ahead(lanes_world.mission.target_branch, status_event=True)
    trace = tmp_path / "git-trace.log"

    envelope, stderr = _invoke_with_stderr(
        lanes_world, "consolidate-mission", "--origin-check", "warn", env={"GIT_TRACE": str(trace), "SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS": "1"}
    )

    assert _origin_codes_of(envelope) == []
    assert "ORIGIN_STATUS_STALE" in stderr, "the orchestrator gate warns on stderr in warn mode"
    assert "Planning-artifact closeout failed" not in json.dumps(envelope), envelope
    assert _ls_remote_calls(trace) == 1
