"""``consolidate --abort`` restores the pre-mutation snapshot before it clears the record.

Contract (FR-005/FR-007/FR-011, SC-005/SC-006, ``contracts/rollback-authority.md``):
``--abort`` restores every snapshotted branch through the single CAS rollback
authority FIRST, and clears the record only after a full restore. Without that,
the NEXT fresh run would capture the ADVANCED base as its own "pre-run" state.

Trigger (all REAL, nothing mocked): a LANES mission whose target is the protected
``main`` raises an uncaught ``BookkeepingPolicyRefused`` in
``_phase_record_done_and_project`` AFTER the squash advanced the target and AFTER the
post-mutation tips were recorded for the ``_phase_mission_to_target`` phase. That exit
is OUTSIDE the reconciliation gate, so the in-process rollback does not run and the
run leaves a genuine crash residue (advanced ``main`` + advanced mission branch + a
resumable ``state.json``) for ``--abort`` to deal with.

Cases that a real CLI run cannot produce say so in their docstring:

* the pre-fix record deletes the new keys from a REAL ``state.json`` (models a record
  written by the previous release -- there is no other way to obtain one);
* the FR-011 verified landing reuses ``test_repro_5021``'s real mid-teardown fixture and
  adds the real pre-run tips as ``pre_mutation_refs`` (that fixture predates the snapshot).

Provenance: #5318 (abort), #5338 (abort after a deleted lane branch), #5385 (crash trigger).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.coordination.surface_resolver import materialize_coord_surface_for_write
from specify_cli.consolidation.state import ConsolidationState, acquire_merge_lock, get_state_path, save_state
from tests.terminus.conftest import CoordMission, blob_present_at, build_coord_mission, plant_canceled_commit, run_terminus
from tests.terminus.conftest import _git as git
from tests.terminus.lanes_fixture import build_lanes_mission
from tests.terminus.rollback_harness import (
    delete_lane_branch,
    failing_gate_run,
    flat,
    full_snapshot,
    ref_shas,
    remove_carrier_cause,
    restored_pairs,
)
from tests.terminus.test_repro_5021 import _complete_squash_then_recreate_mid_teardown_state

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_GLOBAL_LOCK = "__global_merge__"
_NEW_SNAPSHOT_KEYS = ("pre_mutation_refs", "restore_targets", "post_mutation_refs")


def _abort(mission: CoordMission) -> subprocess.CompletedProcess[str]:
    return run_terminus(mission, ["consolidate", "--abort", "--mission", mission.slug])


def _state_path(mission: CoordMission) -> Path:
    return get_state_path(mission.repo, mission.mission_id)


def _read_state(mission: CoordMission) -> dict[str, object]:
    return json.loads(_state_path(mission).read_text(encoding="utf-8"))


def _crashed_lanes_run(tmp_path: Path, mid8: str) -> tuple[CoordMission, dict[str, str]]:
    """LANES mission on protected ``main``: a real post-squash crash (#5385), refs advanced."""
    mission = build_lanes_mission(tmp_path, wps=("WP01", "WP02"), target_branch="main", mid8=mid8)
    before = ref_shas(mission)
    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])
    output = flat(result)
    assert result.returncode != 0, f"fixture precondition: the run must crash. output={output}"
    assert "PROTECTED_BRANCH_REFUSED" in output, f"fixture precondition: the crash must be the #5385 policy refusal. output={output}"
    after = ref_shas(mission)
    assert after["target"] != before["target"], "fixture precondition: the squash must have advanced the target before the crash"
    assert after["coord"] != before["coord"], "fixture precondition: the mission branch must have advanced (lane merges + bake)"
    assert _state_path(mission).exists(), "fixture precondition: a crashed run leaves a resumable record"
    return mission, before


def test_abort_restores_every_snapshotted_branch(tmp_path: Path) -> None:
    mission, before = _crashed_lanes_run(tmp_path, "01M5318A")

    result = _abort(mission)
    output = flat(result)
    after = ref_shas(mission)

    assert result.returncode == 0, f"a fully restored abort exits 0. output={output}"
    assert after["target"] == before["target"], f"--abort left the target advanced ({before['target']} -> {after['target']}). output={output}"
    assert after["coord"] == before["coord"], f"--abort left the mission branch advanced. output={output}"
    assert {k: v for k, v in after.items() if k.startswith("lane:")} == {k: v for k, v in before.items() if k.startswith("lane:")}
    assert not blob_present_at(mission.repo, mission.target_branch, "src/pkg/wp01.py"), "the squashed content must be gone from the target"
    assert not _state_path(mission).exists(), "the record is cleared only after the restore"
    assert restored_pairs(output, mission.target_branch), f"the report must name the target restore. output={output}"
    assert restored_pairs(output, mission.coord_branch), f"the report must name the mission-branch restore. output={output}"


def test_abort_refuses_to_destroy_another_actors_commit(tmp_path: Path) -> None:
    """SC-005: a branch moved by someone else after the crash keeps its commit; the record stays; exit 1."""
    mission, _before = _crashed_lanes_run(tmp_path, "01M5318B")
    recorded_post = _read_state(mission)["post_mutation_refs"]
    assert isinstance(recorded_post, dict) and mission.coord_branch in recorded_post, "the crashed run must have recorded its post tips"
    tip = git(mission.repo, "rev-parse", mission.coord_branch).stdout.strip()
    tree = git(mission.repo, "rev-parse", f"{tip}^{{tree}}").stdout.strip()
    moved = git(mission.repo, "commit-tree", tree, "-p", tip, "-m", "another actor's commit").stdout.strip()
    git(mission.repo, "update-ref", f"refs/heads/{mission.coord_branch}", moved, tip)

    result = _abort(mission)
    output = flat(result)

    assert result.returncode == 1, f"SC-005: an abort that cannot restore a branch exits 1. output={output}"
    assert ref_shas(mission)["coord"] == moved, f"SC-005: the moved branch must be untouched. output={output}"
    assert "NOT restored" in output and "moved by another actor" in output, f"the report must fail for the CAS reason. output={output}"
    assert f"expected {str(recorded_post[mission.coord_branch])[:7]}" in output, f"expected must be the recorded post tip. output={output}"
    assert f"observed {moved[:7]}" in output, f"observed must be the moved commit. output={output}"
    assert _state_path(mission).exists(), "SC-005: the record is KEPT so nothing is lost"
    assert "Kept the consolidation record" in output, f"the operator must be told the record was kept. output={output}"


def test_abort_after_a_kill_before_post_tips_were_recorded_keeps_the_record(tmp_path: Path) -> None:
    """Kill window (slice-10 F1): an advanced branch with no recorded post tip is never reported restored.

    A SIGKILL inside a ref-moving phase, before its recorder ran, cannot be produced by a
    real CLI run on demand. It is modelled on the crashed run's REAL ``state.json``: the
    post tips are emptied, exactly what ``begin_attempt`` leaves before the first
    recorder runs. Pre-fold, ``--abort`` reported the advanced ``main`` and mission branch
    as "kept (not moved by this run)", exited 0 and cleared the record over them.
    """
    mission, _before = _crashed_lanes_run(tmp_path, "01M5318K")
    payload = _read_state(mission)
    payload["post_mutation_refs"] = {}
    _state_path(mission).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    advanced = ref_shas(mission)

    result = _abort(mission)
    output = flat(result)

    assert result.returncode == 1, f"an abort that cannot account for an advanced branch exits 1. output={output}"
    assert _state_path(mission).exists(), "the record is KEPT so the snapshot is not lost"
    assert ref_shas(mission) == advanced, f"nothing may be moved without a recorded post tip. output={output}"
    for branch in (mission.target_branch, mission.coord_branch):
        assert f"NOT restored {branch}" in output, f"{branch} must be named NOT restored. output={output}"
    assert "no post-mutation tip was recorded" in output, f"the reason must be stated. output={output}"
    assert "not moved by this run" not in output, f"an advanced branch must never be reported untouched. output={output}"
    assert "Kept the consolidation record" in output, f"the operator must be told the record was kept. output={output}"


def test_abort_keeps_the_operators_fix_and_a_fresh_run_succeeds(tmp_path: Path) -> None:
    """The gate FAIL restored in-process; the operator then fixes the carrier lane; ``--abort`` must keep that fix.

    Regression guard (green before AND after the fix): the danger is an authority that "restores"
    the lane to its snapshot and destroys the operator's commit (post-tasks BLOCKER 2).
    """
    mission, planted, before, _reflog, _result = failing_gate_run(tmp_path, "01M5318C")
    remove_carrier_cause(mission, "WP02")
    fixed_lane_tip = ref_shas(mission)["lane:WP02"]
    assert fixed_lane_tip != before["lane:WP02"], "fixture precondition: the operator's rewrite moved the lane"

    aborted = _abort(mission)

    assert aborted.returncode == 0, f"abort after an in-process restore must succeed. output={flat(aborted)}"
    assert ref_shas(mission)["lane:WP02"] == fixed_lane_tip, "the operator's carrier-lane fix must survive --abort"
    assert not _state_path(mission).exists()

    # ``--abort``'s existing coordination teardown (FR-016, not this WP) removes the coordination
    # worktree; the next run refuses with "materialize the coordination worktree", so the operator does.
    materialize_coord_surface_for_write(mission.repo, mission.slug)
    fresh = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])
    assert fresh.returncode == 0, f"a fresh run after abort must succeed. output={flat(fresh)}"
    for wp_file in ("src/pkg/wp01.py", "src/pkg/wp02.py"):
        assert blob_present_at(mission.repo, mission.target_branch, wp_file), f"{wp_file} must be attributed on the target"
    assert not blob_present_at(mission.repo, mission.target_branch, planted)


def test_abort_keeps_a_verified_landing(tmp_path: Path) -> None:
    """FR-011 / SC-006: a record whose PASS anchor equals the target tip is never rolled back by ``--abort``."""
    mission = build_coord_mission(tmp_path, wps=("WP01",), mid8="01M5318D")
    pre_run = ref_shas(mission)
    landed_tip = _complete_squash_then_recreate_mid_teardown_state(mission, "WP01", ["WP01"])
    # 5021's fixture predates the snapshot: add the REAL pre-run tips it never recorded.
    payload = _read_state(mission)
    payload["pre_mutation_refs"] = {mission.target_branch: pre_run["target"], mission.coord_branch: pre_run["coord"]}
    _state_path(mission).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    result = _abort(mission)
    output = flat(result)

    assert result.returncode == 1, f"FR-011: --abort over a verified landing exits 1. output={output}"
    assert "Kept the landing verified by an earlier reconciliation" in output, output
    assert ref_shas(mission)["target"] == landed_tip, "the verified landing must be untouched"
    assert blob_present_at(mission.repo, mission.target_branch, "src/pkg/wp01.py")
    assert _state_path(mission).exists(), "the record is kept"


def test_abort_of_a_pre_fix_record_keeps_todays_behaviour_with_a_notice(tmp_path: Path) -> None:
    """A record without a snapshot (older release): abort clears it as before, and says nothing was restored.

    A real older-shape record cannot be produced by the current release, so the new keys are
    deleted from a REAL ``state.json`` written by a crashed run.
    """
    mission, before = _crashed_lanes_run(tmp_path, "01M5318E")
    payload = _read_state(mission)
    for key in _NEW_SNAPSHOT_KEYS:
        payload.pop(key)
    _state_path(mission).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    advanced = ref_shas(mission)

    result = _abort(mission)
    output = flat(result)

    assert result.returncode == 0, f"a pre-fix record keeps today's exit 0. output={output}"
    assert "no pre-mutation snapshot was recorded" in output, f"the operator must be told nothing was restored. output={output}"
    assert not _state_path(mission).exists()
    assert ref_shas(mission) == advanced != before, "without a snapshot no branch is moved"


def test_abort_refuses_while_another_missions_merge_is_live(tmp_path: Path) -> None:
    mission, _before = _crashed_lanes_run(tmp_path, "01M5318F")
    advanced = ref_shas(mission)
    other_id = "01M5318ZZZ" + "0" * 16
    save_state(ConsolidationState(mission_id=other_id, mission_slug="other-mission", target_branch="main", wp_order=["WP01"]), mission.repo)
    assert acquire_merge_lock(_GLOBAL_LOCK, mission.repo, owner_token=other_id)

    result = _abort(mission)
    output = flat(result)

    assert result.returncode == 1, f"a live foreign lock refuses the abort. output={output}"
    assert ref_shas(mission) == advanced, "nothing may be restored while another merge is live"
    assert _state_path(mission).exists(), "nothing may be cleared while another merge is live"
    assert "another mission" in output, f"the refusal must say why. output={output}"


def test_abort_after_a_crashed_resume_still_restores(tmp_path: Path) -> None:
    """A resumed attempt that re-moves nothing must not orphan attempt 1's post tips.

    Real #5385 crash, then ``--resume`` (crashes the same way: lanes already
    consolidated, target already squashed, so no phase re-moves a branch), then
    ``--abort``. The post tips attempt 1 recorded are still the CAS expectation for
    every branch sitting at them, so the abort restores instead of wedging on
    "no post-mutation tip was recorded".
    """
    mission, before = _crashed_lanes_run(tmp_path, "01M5318R")
    resumed = run_terminus(mission, ["consolidate", "--resume", "--mission", mission.slug, "--yes"])
    assert resumed.returncode != 0, f"precondition: the resume crashes the same way. output={flat(resumed)}"
    assert ref_shas(mission)["target"] != before["target"], "precondition: the target is still advanced"

    result = _abort(mission)
    output = flat(result)
    after = ref_shas(mission)

    assert result.returncode == 0, f"--abort after a crashed resume must restore, not wedge. output={output}"
    assert after["target"] == before["target"], f"target left advanced. output={output}"
    assert after["coord"] == before["coord"], f"mission branch left advanced. output={output}"
    assert not _state_path(mission).exists(), "the record is cleared after a full restore"
    assert "no post-mutation tip was recorded" not in output, output


def test_abort_after_a_lane_branch_was_deleted_is_not_wedged(tmp_path: Path) -> None:
    """A vanished snapshotted LANE branch is reported with a recreate hint, never a wedge (slice-10 F3).

    Recovery path: gate FAIL (restored in-process), the operator deletes an approved lane
    branch, ``--resume`` refuses at claim time, then ``--abort``. Everything else is already
    at its snapshot, so the abort must succeed and tell the operator how to recreate the lane.
    """
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8="01M9WEDG")
    plant_canceled_commit(mission, canceled_wp="WP03", carrier_wp="WP02")
    first = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])
    assert first.returncode != 0, f"fixture precondition: the fresh run must gate-FAIL. stdout={first.stdout}\nstderr={first.stderr}"
    lane = mission.lane_branches["WP01"]
    assert _state_path(mission).exists(), "fixture precondition: the failed run leaves a resumable record"
    pre_refs = _read_state(mission)["pre_mutation_refs"]
    assert isinstance(pre_refs, dict) and lane in pre_refs, f"fixture precondition: the lane is snapshotted: {pre_refs}"
    lane_snapshot = pre_refs[lane]
    delete_lane_branch(mission, "WP01")
    resumed = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--resume", "--yes"])
    assert resumed.returncode != 0, "fixture precondition: the resume refuses at claim time"
    before = full_snapshot(mission)

    aborted = _abort(mission)
    output = flat(aborted)

    assert aborted.returncode == 0, f"a missing lane branch must not wedge --abort. output={output}"
    assert not _state_path(mission).exists(), f"the record is cleared after the (otherwise full) restore. output={output}"
    after = full_snapshot(mission)
    assert (after["target"], after["coord"]) == (before["target"], before["coord"]), f"nothing needed restoring. output={output}"
    assert f"lane branch {lane} no longer exists" in output, f"the report must name the vanished lane. output={output}"
    assert f"git branch {lane} {lane_snapshot}" in output, f"the report must give the recreate command. output={output}"
    assert "nothing was rolled back" not in output.lower(), f"no blanket refusal. output={output}"
