"""``spec-kitty accept`` refuses on stale origin status evidence (FR-003/FR-008/FR-009, SC-004).

A teammate (clone B) pushes a rejection event on the coordination branch; this
clone (A) has not pulled. The REAL ``accept`` CLI must say so before it reads the
acceptance summary, and the opt-outs / read-only modes must not refuse.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.terminus.conftest import CoordMission, _event, build_coord_mission, run_terminus
from tests.terminus.two_clone_support import attach_and_push, clone_from, isolated_git_env, make_bare_remote, unreachable_remote

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_STATUS_LOG = "status.events.jsonl"
_STALE = "ORIGIN_STATUS_STALE"
_UNREACHABLE = "ORIGIN_UNREACHABLE"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


@dataclass
class TwoCloneMission:
    mission: CoordMission
    bare: Path
    second: Path

    def teammate_rejects(self) -> None:
        """Clone B appends a rejection event to the coordination branch's status log and pushes it."""
        branch = self.mission.coord_branch
        _git(self.second, "fetch", "-q", "origin", branch)
        _git(self.second, "checkout", "-q", "-B", branch, f"origin/{branch}")
        log = self.second / "kitty-specs" / self.mission.slug / _STATUS_LOG
        rejection = _event(self.mission, "WP01", "approved", "planned")
        log.write_text(log.read_text(encoding="utf-8") + json.dumps(rejection, sort_keys=True) + "\n", encoding="utf-8")
        _git(self.second, "add", str(log.relative_to(self.second)))
        _git(self.second, "commit", "-q", "-m", "status: teammate rejects WP01")
        _git(self.second, "push", "-q", "origin", f"{branch}:{branch}")


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TwoCloneMission:
    isolated_git_env(monkeypatch, tmp_path)
    mission = build_coord_mission(tmp_path / "c", wps=("WP01",))
    bare = make_bare_remote(tmp_path)
    attach_and_push(mission.repo, bare, [mission.target_branch, mission.coord_branch, *mission.lane_branches.values()])
    _git(bare, "symbolic-ref", "HEAD", f"refs/heads/{mission.target_branch}")
    return TwoCloneMission(mission=mission, bare=bare, second=clone_from(bare, tmp_path / "second"))


def _accept(world: TwoCloneMission, *extra: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return run_terminus(world.mission, ["accept", "--mission", world.mission.slug, "--json", *extra], env=env)


def _flat(result: subprocess.CompletedProcess[str]) -> str:
    return " ".join((result.stdout + "\n" + result.stderr).split())


def test_accept_refuses_when_a_teammate_pushed_a_rejection(world: TwoCloneMission) -> None:
    world.teammate_rejects()

    result = _accept(world)

    assert result.returncode == 1, result.stdout + result.stderr
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["error_code"] == _STALE
    assert world.mission.coord_branch in payload["error"]
    assert "--origin-check warn" in payload["error"]
    assert payload["origin_freshness"][0]["state"] == "behind"
    assert payload["origin_freshness"][0]["branch"] == world.mission.coord_branch


def test_accept_up_to_date_control_is_not_refused_for_freshness(world: TwoCloneMission) -> None:
    result = _accept(world)

    assert _STALE not in _flat(result)
    assert _UNREACHABLE not in _flat(result)


@pytest.mark.parametrize("how", ["flag", "environment"])
def test_accept_warn_opt_out_is_not_refused_for_freshness(world: TwoCloneMission, how: str) -> None:
    world.teammate_rejects()
    flag = ["--origin-check", "warn"] if how == "flag" else []
    env = {"SPEC_KITTY_ORIGIN_CHECK": "warn"} if how == "environment" else None

    result = _accept(world, *flag, env=env)

    flat = _flat(result)
    assert '"error_code": "ORIGIN_STATUS_STALE"' not in flat
    assert "origin check is warn" in flat


@pytest.mark.parametrize("read_only_flag", ["--no-commit", "--diagnose"])
def test_accept_read_only_modes_warn_and_never_refuse(world: TwoCloneMission, read_only_flag: str) -> None:
    world.teammate_rejects()

    result = _accept(world, read_only_flag)

    flat = _flat(result)
    assert '"error_code": "ORIGIN_STATUS_STALE"' not in flat
    assert "source: read-only" in flat
    assert _STALE in flat


def test_accept_refuses_when_the_remote_is_unreachable(world: TwoCloneMission) -> None:
    unreachable_remote(world.mission.repo)

    result = _accept(world)

    assert result.returncode == 1, result.stdout + result.stderr
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["error_code"] == _UNREACHABLE
    assert payload["origin_freshness"][0]["state"] == "unreachable"


def test_accept_unreachable_warn_opt_out_is_not_refused(world: TwoCloneMission) -> None:
    unreachable_remote(world.mission.repo)

    result = _accept(world, "--origin-check", "warn")

    assert '"error_code": "ORIGIN_UNREACHABLE"' not in _flat(result)
    assert _UNREACHABLE in _flat(result)


def test_accept_without_a_remote_is_not_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A mission with no remote at all has nothing to be stale against (verdict ``no_remote``)."""
    isolated_git_env(monkeypatch, tmp_path)
    mission = build_coord_mission(tmp_path / "solo", wps=("WP01",))

    result = run_terminus(mission, ["accept", "--mission", mission.slug, "--json"])

    assert _STALE not in _flat(result)
    assert _UNREACHABLE not in _flat(result)
