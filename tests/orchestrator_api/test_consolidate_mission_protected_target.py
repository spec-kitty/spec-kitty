"""``orchestrator-api consolidate-mission`` refuses a protected-target mission before any branch moves (#5385).

The orchestrator-api has its own lane consolidation path (``_execute_lane_merge``:
lane -> mission -> target, then ``done`` bookkeeping). A LANES mission whose
recorded target is the protected ``main`` records its ``done`` bookkeeping on
``main``, which the workflow mutation policy refuses. Without the up-front
preflight that path squashed onto ``main`` first and only then failed.

Both entries -- the code-lane path and the planning-artifact-only closeout (which
runs the CLI consolidation under a captured console) -- must fail with the
policy's own ``PROTECTED_BRANCH_REFUSED`` code in the JSON envelope, with ``main``
and the mission branch unmoved. An unprotected target still consolidates.

Driven through the REAL ``spec-kitty orchestrator-api`` CLI over real git.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tests.terminus.conftest import CoordMission, blob_present_at, run_terminus
from tests.terminus.lanes_fixture import build_lanes_mission
from tests.terminus.rollback_harness import flat, ref_shas

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_REFUSAL_CODE = "PROTECTED_BRANCH_REFUSED"


def _consolidate_mission(mission: CoordMission) -> subprocess.CompletedProcess[str]:
    return run_terminus(mission, ["orchestrator-api", "consolidate-mission", "--mission", mission.slug, "--strategy", "squash"])


def _envelope(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    """The JSON envelope: the last stdout line.

    The last line, not the only one: the success path's lane-branch cleanup
    lets ``git branch -D`` print "Deleted branch ..." to stdout first (a
    pre-existing leak outside this contract).
    """
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert lines, f"expected a JSON envelope on stdout. output={flat(result)}"
    envelope = json.loads(lines[-1])
    assert isinstance(envelope, dict)
    return envelope


def _assert_refused_unmoved(mission: CoordMission, result: subprocess.CompletedProcess[str], before: dict[str, str]) -> None:
    output = flat(result)
    assert result.returncode != 0, f"the protected-target consolidation must be refused. output={output}"
    envelope = _envelope(result)
    assert envelope["success"] is False, envelope
    assert _REFUSAL_CODE in json.dumps(envelope), f"the envelope must name the policy's refusal code. envelope={envelope}"
    assert "Traceback" not in result.stderr, result.stderr
    assert ref_shas(mission) == before, f"no branch tip may move. output={output}"


def test_code_lane_consolidation_on_protected_main_is_refused_before_any_branch_moves(tmp_path: Path) -> None:
    mission = build_lanes_mission(tmp_path, wps=("WP01", "WP02"), target_branch="main", mid8="01M5385O")
    before = ref_shas(mission)

    result = _consolidate_mission(mission)

    _assert_refused_unmoved(mission, result, before)
    assert not blob_present_at(mission.repo, "main", "src/pkg/wp01.py"), "no squashed content on main"


def test_planning_only_closeout_on_protected_main_surfaces_the_refusal_code(tmp_path: Path) -> None:
    mission = build_lanes_mission(tmp_path, wps=(), target_branch="main", mid8="01M5385Q", with_planning_lane_wp=True, planning_depends_on_code=False)
    before = ref_shas(mission)

    result = _consolidate_mission(mission)

    _assert_refused_unmoved(mission, result, before)


def test_control_unprotected_target_consolidates(tmp_path: Path) -> None:
    mission = build_lanes_mission(tmp_path, wps=("WP01", "WP02"), target_branch="develop", mid8="01M5385V")

    result = _consolidate_mission(mission)

    output = flat(result)
    assert result.returncode == 0, output
    assert _envelope(result)["success"] is True, output
    assert _REFUSAL_CODE not in output, output
    assert blob_present_at(mission.repo, "develop", "src/pkg/wp02.py"), output
