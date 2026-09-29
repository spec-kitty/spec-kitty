"""Repro #5338 -- a claim-time REFUSE must act BEFORE any mutation.

``_capture_reconciliation_claim`` builds the fail-closed approved-WP claim at
transaction start, but pre-fix it only acted on a ``GitProbeError``: a claim
carrying a ``refusal`` (e.g. an approved lane branch that no longer exists), an
unresolved surface, or a vacuous claim was stored and ignored until
``MergeOutcomeVerifier.verify`` at the post-mutation gate -- after lane
consolidation, the bake, and the mission->target squash had already moved refs.

Contract (FR-001/FR-002): a claim-integrity refusal exits non-zero with recovery
guidance BEFORE the first mutating phase; the target, coordination/mission
branch and lane branch SHAs, ``state.json`` bookkeeping and the status event
logs are unchanged. A resume whose reconciliation already PASSed for the current
target tip (#5021) is NOT refused.

Driven through the REAL ``spec-kitty consolidate`` CLI over real git (NFR-004,
nothing mocked). ``pytest.mark.regression`` here means "issue-pinned e2e", the
same convention as the sibling repros.
"""

from __future__ import annotations

import json
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
from tests.terminus.conftest import _git as git
from tests.terminus.conftest import _git_out as git_out
from tests.terminus.test_repro_5021 import _complete_squash_then_recreate_mid_teardown_state

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]


def _state_path(mission: CoordMission) -> Path | None:
    found = sorted((mission.repo / ".kittify" / "runtime" / "merge").glob("*/state.json"))
    return found[0] if found else None


def _state_bookkeeping(mission: CoordMission) -> dict[str, object] | None:
    path = _state_path(mission)
    if path is None:
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {key: payload.get(key) for key in ("mission_number_baked", "completed_wps")}


def _resolve_or_gone(mission: CoordMission, ref: str) -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", "-q", ref],
        cwd=mission.repo,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout.strip() or "<gone>"


def _event_log_bytes(mission: CoordMission, ref: str) -> str:
    proc = subprocess.run(
        ["git", "show", f"{ref}:kitty-specs/{mission.slug}/status.events.jsonl"],
        cwd=mission.repo,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout


def _snapshot(mission: CoordMission) -> dict[str, object]:
    """Real SHAs + bookkeeping + event-log bytes for every ref the run may move."""
    return {
        "target": _resolve_or_gone(mission, mission.target_branch),
        "coord": _resolve_or_gone(mission, mission.coord_branch),
        "lanes": {wp: _resolve_or_gone(mission, branch) for wp, branch in sorted(mission.lane_branches.items())},
        "state": _state_bookkeeping(mission),
        "target_events": _event_log_bytes(mission, mission.target_branch),
        "coord_events": _event_log_bytes(mission, mission.coord_branch),
    }


def _delete_lane_branch(mission: CoordMission, wp_id: str) -> None:
    git(mission.repo, "branch", "-D", mission.lane_branches[wp_id])


def test_5338_resume_claim_refuse_acts_before_any_mutation(tmp_path: Path) -> None:
    """US1-AS1: fresh gate FAIL, then an approved lane branch is deleted, then
    ``--resume``: the claim now REFUSEs and the run must stop pre-mutation."""
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8="01M5338A")
    _, _, planted = plant_canceled_commit(mission, canceled_wp="WP03", carrier_wp="WP02")

    first = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])
    assert first.returncode != 0, f"fixture precondition: the fresh run must gate-FAIL. stdout={first.stdout}\nstderr={first.stderr}"
    assert not blob_present_at(mission.repo, mission.target_branch, planted), "fixture precondition: the failed fresh run must restore the target"

    _delete_lane_branch(mission, "WP01")
    before = _snapshot(mission)
    assert before["state"] is not None, "fixture precondition: the failed fresh run must leave a resumable state.json"

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--resume", "--yes"])
    output = " ".join((result.stdout + result.stderr).split())  # rich wraps long lines

    assert result.returncode != 0, f"#5338: a claim-time REFUSE must exit non-zero. output={output}"
    after = _snapshot(mission)
    assert after["target"] == before["target"], f"#5338: target moved during a refused resume ({before['target']} -> {after['target']}). output={output}"
    assert after["coord"] == before["coord"], f"#5338: coordination/mission branch moved during a refused resume. output={output}"
    assert after["lanes"] == before["lanes"], f"#5338: a lane branch moved during a refused resume. output={output}"
    assert after["state"] == before["state"], f"#5338: state.json bookkeeping changed during a refused resume: {before['state']} -> {after['state']}"
    assert after["target_events"] == before["target_events"], "#5338: the target status event log changed"
    assert after["coord_events"] == before["coord_events"], "#5338: the coordination status event log changed"
    assert not blob_present_at(mission.repo, mission.target_branch, planted), "#5338: the canceled file reached the target"
    assert "efused" in output and "does not exist in git" in output, f"#5338: expected recovery guidance naming the lane-branch reason. output={output}"
    assert "Squashing" not in output, f"#5338: the run reached the squash phase before refusing. output={output}"


def test_5338_fresh_claim_refuse_leaves_no_state(tmp_path: Path) -> None:
    """US1-AS2: a FRESH run whose claim REFUSEs leaves no state.json and moves nothing."""
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8="01M5338B")
    fold_lanes_into_mission_branch(mission, ["WP01"])
    _delete_lane_branch(mission, "WP01")
    before = _snapshot(mission)
    assert before["state"] is None, "fixture precondition: no consolidation record exists yet"

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])
    output = " ".join((result.stdout + result.stderr).split())  # rich wraps long lines

    assert result.returncode != 0, f"#5338: a claim-time REFUSE must exit non-zero. output={output}"
    assert _state_path(mission) is None, f"#5338: a refused FRESH run must not leave a state.json behind. output={output}"
    after = _snapshot(mission)
    assert after["target"] == before["target"], f"#5338: target moved. output={output}"
    assert after["coord"] == before["coord"], f"#5338: coordination/mission branch moved. output={output}"
    assert after["lanes"] == before["lanes"], f"#5338: a lane branch moved. output={output}"
    assert "does not exist in git" in output, f"#5338: expected the lane-branch reason in the guidance. output={output}"


def test_5338_fr002_already_passed_resume_is_not_refused(tmp_path: Path) -> None:
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
