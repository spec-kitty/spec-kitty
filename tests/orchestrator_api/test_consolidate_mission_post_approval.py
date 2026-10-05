"""``orchestrator-api consolidate-mission`` refuses a lane holding a post-approval commit (#5668).

The orchestrator-api merges code lanes directly (``consolidate_lane_into_mission``,
then ``integrate_mission_into_target``) with no reconciliation claim and no gate, so it
landed a content commit made on a lane after review approved it. It must evaluate the
approved bound before its first lane merge and fail with the ``PREFLIGHT_FAILED``
envelope, carrying the refusal code machine-readably in ``data["preflight_error_code"]``,
with no branch moved. The same mission without the late commit still consolidates.

Driven through the REAL ``spec-kitty orchestrator-api`` CLI over real git.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tests.terminus.conftest import CoordMission, blob_present_at, run_terminus
from tests.terminus.post_approval_support import (
    LATE_PATH,
    WP01_PATH,
    add_post_approval_commit,
    build_post_approval_coord_mission,
    build_post_approval_lanes_mission,
)
from tests.terminus.rollback_harness import flat, ref_shas

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_REFUSAL_CODE = "LANE_MOVED_AFTER_APPROVAL"
_TARGET = "develop"


def _consolidate_mission(mission: CoordMission) -> subprocess.CompletedProcess[str]:
    return run_terminus(mission, ["orchestrator-api", "consolidate-mission", "--mission", mission.slug, "--strategy", "squash"])


def _envelope(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    """The JSON envelope: the last non-empty stdout line (the success path's branch cleanup prints first)."""
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert lines, f"expected a JSON envelope on stdout. output={flat(result)}"
    envelope = json.loads(lines[-1])
    assert isinstance(envelope, dict)
    return envelope


def _build(tmp_path: Path, topology: str) -> CoordMission:
    if topology == "coord":
        return build_post_approval_coord_mission(tmp_path, target_branch=_TARGET)
    return build_post_approval_lanes_mission(tmp_path, target_branch=_TARGET)


@pytest.mark.parametrize("topology", ["lanes", "coord"])
def test_post_approval_commit_is_refused_before_any_lane_merges(tmp_path: Path, topology: str) -> None:
    mission = _build(tmp_path, topology)
    add_post_approval_commit(mission)
    before = ref_shas(mission)

    result = _consolidate_mission(mission)

    output = flat(result)
    assert result.returncode != 0, f"a post-approval commit must be refused. output={output}"
    envelope = _envelope(result)
    assert envelope["success"] is False, envelope
    data = envelope["data"]
    assert isinstance(data, dict)
    assert envelope["error_code"] == "PREFLIGHT_FAILED", envelope
    assert data["preflight_error_code"] == _REFUSAL_CODE, envelope
    assert ref_shas(mission) == before, f"no branch tip may move. output={output}"
    assert not blob_present_at(mission.repo, _TARGET, LATE_PATH), "the unreviewed file must not be on the target"
    assert not blob_present_at(mission.repo, mission.coord_branch, LATE_PATH), "the unreviewed file must not be on the mission branch"


@pytest.mark.parametrize("topology", ["lanes", "coord"])
def test_control_untouched_approved_mission_consolidates(tmp_path: Path, topology: str) -> None:
    mission = _build(tmp_path, topology)

    result = _consolidate_mission(mission)

    output = flat(result)
    assert result.returncode == 0, output
    assert _envelope(result)["success"] is True, output
    assert blob_present_at(mission.repo, _TARGET, WP01_PATH), output


def test_a_placement_failure_of_any_kind_falls_back_to_the_mission_branch_base(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The base resolution tolerates what the executor tolerates: an unresolvable placement (not only a git error) reads as "no coordination tip"."""
    import mission_runtime
    from specify_cli.lanes.persistence import read_lanes_json
    from specify_cli.orchestrator_api.consolidation import _approved_bound_claim_base

    mission = _build(tmp_path, "lanes")
    manifest = read_lanes_json(mission.feature_dir)
    assert manifest is not None

    def _boom(*_args: object, **_kwargs: object) -> object:
        raise ValueError("placement cannot be resolved")

    monkeypatch.setattr(mission_runtime, "resolve_placement_only", _boom)

    assert _approved_bound_claim_base(mission.repo, mission.slug, manifest) == ref_shas(mission)["coord"]
