"""A claim-integrity REFUSE stops the consolidation BEFORE any mutation.

``_capture_reconciliation_claim`` builds the fail-closed approved-WP claim at
transaction start. A claim carrying a ``refusal`` (e.g. an approved lane branch
that no longer exists), an unresolved surface, or a vacuous claim must act there,
not at the post-mutation gate after lane consolidation, the bake, and the
mission->target squash already moved refs.

Contract (FR-001/FR-002): a claim-integrity refusal exits non-zero with recovery
guidance BEFORE the first mutating phase; the target, coordination/mission
branch and lane branch SHAs, ``state.json`` bookkeeping and the status event
logs are unchanged. A resume whose reconciliation already PASSed for the current
target tip is NOT refused.

Driven through the REAL ``spec-kitty consolidate`` CLI over real git (NFR-004,
nothing mocked). ``pytest.mark.regression`` here means "issue-pinned e2e".

Provenance: #5338 (claim-time refusal), #5021 (already-PASSed resume exemption).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.consolidation.reconciliation import ApprovedWpCommitSet, build_approved_wp_set, claim_integrity_refusal
from tests.terminus.conftest import (
    CoordMission,
    blob_present_at,
    build_coord_mission,
    fold_lanes_into_mission_branch,
    plant_canceled_commit,
    run_terminus,
)
from tests.terminus.conftest import _git_out as git_out
from tests.terminus.rollback_harness import delete_lane_branch, full_snapshot, state_path
from tests.terminus.test_repro_5021 import _complete_squash_then_recreate_mid_teardown_state

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]


def test_resume_claim_refuse_acts_before_any_mutation(tmp_path: Path) -> None:
    """US1-AS1: fresh gate FAIL, then an approved lane branch is deleted, then
    ``--resume``: the claim now REFUSEs and the run must stop pre-mutation."""
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8="01M5338A")
    _, _, planted = plant_canceled_commit(mission, canceled_wp="WP03", carrier_wp="WP02")

    first = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])
    assert first.returncode != 0, f"fixture precondition: the fresh run must gate-FAIL. stdout={first.stdout}\nstderr={first.stderr}"
    assert not blob_present_at(mission.repo, mission.target_branch, planted), "fixture precondition: the failed fresh run must restore the target"

    delete_lane_branch(mission, "WP01")
    before = full_snapshot(mission)
    assert before["state"] is not None, "fixture precondition: the failed fresh run must leave a resumable state.json"

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--resume", "--yes"])
    output = " ".join((result.stdout + result.stderr).split())  # rich wraps long lines

    assert result.returncode != 0, f"a claim-time REFUSE must exit non-zero. output={output}"
    after = full_snapshot(mission)
    assert after["target"] == before["target"], f"target moved during a refused resume ({before['target']} -> {after['target']}). output={output}"
    assert after["coord"] == before["coord"], f"coordination/mission branch moved during a refused resume. output={output}"
    assert after["lanes"] == before["lanes"], f"a lane branch moved during a refused resume. output={output}"
    assert after["state"] == before["state"], f"state.json bookkeeping changed during a refused resume: {before['state']} -> {after['state']}"
    assert after["target_events"] == before["target_events"], "the target status event log changed"
    assert after["coord_events"] == before["coord_events"], "the coordination status event log changed"
    assert not blob_present_at(mission.repo, mission.target_branch, planted), "the canceled file reached the target"
    assert "efused" in output and "does not exist in git" in output, f"expected recovery guidance naming the lane-branch reason. output={output}"
    assert "Squashing" not in output, f"the run reached the squash phase before refusing. output={output}"


def test_fresh_claim_refuse_leaves_no_state(tmp_path: Path) -> None:
    """US1-AS2: a FRESH run whose claim REFUSEs leaves no state.json and moves nothing."""
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8="01M5338B")
    fold_lanes_into_mission_branch(mission, ["WP01"])
    delete_lane_branch(mission, "WP01")
    before = full_snapshot(mission)
    worktrees_before = git_out(mission.repo, "worktree", "list", "--porcelain")
    assert before["state"] is None, "fixture precondition: no consolidation record exists yet"
    assert before["coord_events"], "non-vacuity: the coordination status event log exists before the run"

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])
    output = " ".join((result.stdout + result.stderr).split())  # rich wraps long lines

    assert result.returncode != 0, f"a claim-time REFUSE must exit non-zero. output={output}"
    assert state_path(mission) is None, f"a refused FRESH run must not leave a state.json behind. output={output}"
    after = full_snapshot(mission)
    assert after["target"] == before["target"], f"target moved. output={output}"
    assert after["coord"] == before["coord"], f"coordination/mission branch moved. output={output}"
    assert after["lanes"] == before["lanes"], f"a lane branch moved. output={output}"
    assert after["target_events"] == before["target_events"], "the target status event log changed"
    assert after["coord_events"] == before["coord_events"], "the coordination status event log changed"
    assert git_out(mission.repo, "worktree", "list", "--porcelain") == worktrees_before, "a worktree was added or removed"
    assert "does not exist in git" in output, f"expected the lane-branch reason in the guidance. output={output}"


def test_already_passed_resume_is_not_refused(tmp_path: Path) -> None:
    """FR-002 control (non-vacuous): the lane branch is genuinely gone, the persisted
    ``reconciliation_passed_target_sha`` equals the target tip, and the resume
    still completes -- the exemption, not an absent refusal."""
    mission = build_coord_mission(tmp_path, wps=("WP01",), mid8="01M5338C")
    _complete_squash_then_recreate_mid_teardown_state(mission, "WP01", ["WP01"])

    lane_branch = mission.lane_branches["WP01"]
    gone = subprocess.run(["git", "rev-parse", "--verify", "-q", lane_branch], cwd=mission.repo, capture_output=True, text=True, check=False)
    assert gone.returncode != 0, "control non-vacuity: the approved lane branch must really be gone before the resume"

    claim = _rebuild_claim_in_process(mission)
    assert claim_integrity_refusal(claim) is not None, "control non-vacuity: the claim must be refusable, so a pass proves the #5021 exemption"

    result = run_terminus(mission, ["consolidate", "--resume", "--yes"])
    assert result.returncode == 0, f"FR-002: an already-PASSed resume must not be refused. stdout={result.stdout}\nstderr={result.stderr}"
    assert git_out(mission.repo, "rev-parse", mission.target_branch)


def _rebuild_claim_in_process(mission: CoordMission) -> ApprovedWpCommitSet:
    from specify_cli.lanes.persistence import read_lanes_json

    manifest = read_lanes_json(mission.feature_dir)
    assert manifest is not None
    return build_approved_wp_set(
        mission.repo,
        mission.feature_dir,
        manifest,
        coord_base_ref=mission.coord_branch,
    )
