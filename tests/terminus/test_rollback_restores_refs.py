"""A consolidation that fails or refuses after mutating restores EVERY run-movable branch.

Contract (FR-004/FR-006/FR-009/FR-011, ``contracts/rollback-authority.md``): after
a reconciliation-gate FAIL, a gate REFUSE, or a squash-projection refusal, the
target AND the coordination/mission branch are back at their pre-run SHAs, lane
branches are untouched, the persisted claim bookkeeping is cleared, and the
appended rollback report is truthful. After removing the cause, ``--resume`` or
a plain re-run succeeds with the approved work attributed on the target. A
landing verified by an EARLIER attempt is kept.

Driven through the REAL ``spec-kitty consolidate`` CLI over real git, asserting
real ``git rev-parse`` SHAs and ``state.json`` bytes (NFR-004). Vacuous-oracle
guard (#5344 class): the gate FAIL path already restored the TARGET before the
single rollback authority existed, so the load-bearing assertions are the
coordination/mission-branch and state ones, plus the reflog proof that the branch
really moved during the run and was moved BACK by the restore.

Provenance: #5318 (gate FAIL, coord + LANES topology), #5332 (projection refusal),
#5359 (gate REFUSE restores the target itself).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from specify_cli.consolidation import executor
from tests.terminus.conftest import blob_present_at, build_coord_mission, fold_lanes_into_mission_branch, plant_canceled_commit, run_terminus
from tests.terminus.conftest import _git as git
from tests.terminus.lanes_fixture import build_lanes_mission
from tests.terminus.rollback_harness import (
    assert_report_is_truthful,
    failing_gate_run,
    flat,
    ref_shas,
    reflog_shas,
    remove_carrier_cause,
    restored_pairs,
    state_bookkeeping,
)
from tests.terminus.test_repro_5021 import _complete_squash_then_recreate_mid_teardown_state

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_NOTES_BASELINE = "l1\nl2\nl3\nl4\nl5\nl6\n"
_PROJECTION_REFUSE_TEXT = "projected coordination bookkeeping content did not land"


# --------------------------------------------------------------------------- #
# Reconciliation-gate FAIL
# --------------------------------------------------------------------------- #


def test_gate_fail_restores_target_and_coordination_branch(tmp_path: Path) -> None:
    mission, planted, before, reflog_before, result = failing_gate_run(tmp_path, "01M5318A")
    output = flat(result)
    after = ref_shas(mission)

    assert not blob_present_at(mission.repo, mission.target_branch, planted), f"the canceled file reached the target. output={output}"
    assert after["target"] == before["target"], f"target not restored ({before['target']} -> {after['target']}). output={output}"
    assert after["coord"] == before["coord"], f"coordination branch left advanced ({before['coord']} -> {after['coord']}). output={output}"
    lanes = {k: v for k, v in after.items() if k.startswith("lane:")}
    assert lanes == {k: v for k, v in before.items() if k.startswith("lane:")}, "a lane branch moved"

    bookkeeping = state_bookkeeping(mission)
    assert bookkeeping is not None, "a failed run must leave a resumable state.json"
    assert bookkeeping["mission_number_baked"] is False, f"state still claims the bake: {bookkeeping}"
    assert bookkeeping["completed_wps"] == [], f"state still claims completed WPs: {bookkeeping}"

    # Vacuous-oracle guard: the branch really moved during the run, and the NEWEST reflog entry is the restore.
    reflog = reflog_shas(mission, mission.coord_branch)
    assert len(reflog) - reflog_before >= 2, f"the coordination branch must have advanced AND been restored during the run; reflog={reflog}"
    assert reflog[0] == before["coord"], f"newest reflog entry is not the pre-run SHA; reflog={reflog}"
    assert len(set(reflog[: len(reflog) - reflog_before])) >= 2, "vacuous oracle: the coordination branch never left its pre-run SHA"

    pairs = restored_pairs(output, mission.coord_branch)
    assert pairs, f"the report must name the coordination-branch restore. output={output}"
    post, pre = pairs[0]
    assert post != pre and pre == before["coord"][:7], f"restore line must go post->pre-run SHA: {pairs}"
    assert_report_is_truthful(output)
    assert re.search(rf"unchanged\s+{re.escape(mission.target_branch)}\s+\(already at {before['target'][:7]}\)", output), (
        f"the report must show the target's idempotent 'unchanged (already at <pre>)' line. output={output}"
    )


def test_gate_fail_restores_the_mission_branch_in_lanes_topology(tmp_path: Path) -> None:
    """LANES has no coordination branch: the lanes fold into the mission branch, which must be restored."""
    mission = build_lanes_mission(tmp_path, wps=("WP01", "WP02"), target_branch="develop", mid8="01M5318L")
    _, _, planted = plant_canceled_commit(mission, canceled_wp="WP03", carrier_wp="WP02")
    before = ref_shas(mission)
    reflog_before = len(reflog_shas(mission, mission.coord_branch))

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])
    output = flat(result)
    after = ref_shas(mission)

    assert result.returncode != 0, f"fixture precondition: the run must gate-FAIL. output={output}"
    assert not blob_present_at(mission.repo, mission.target_branch, planted), f"the canceled file reached the target. output={output}"
    assert after["target"] == before["target"], f"target not restored. output={output}"
    assert after["coord"] == before["coord"], (
        f"the mission branch was left at the lane-merge + bake commit ({before['coord']} -> {after['coord']}). output={output}"
    )
    assert {k: v for k, v in after.items() if k.startswith("lane:")} == {k: v for k, v in before.items() if k.startswith("lane:")}

    bookkeeping = state_bookkeeping(mission)
    assert bookkeeping is not None
    assert bookkeeping["mission_number_baked"] is False, f"state still claims the bake: {bookkeeping}"
    assert bookkeeping["completed_wps"] == [], f"state still claims completed WPs: {bookkeeping}"

    reflog = reflog_shas(mission, mission.coord_branch)
    assert len(reflog) - reflog_before >= 2, f"the mission branch must have advanced AND been restored; reflog={reflog}"
    assert reflog[0] == before["coord"], f"newest reflog entry is not the pre-run SHA; reflog={reflog}"
    pairs = restored_pairs(output, mission.coord_branch)
    assert pairs and pairs[0][0] != pairs[0][1], f"the report must name the mission-branch restore (post != pre). output={output}"


@pytest.mark.parametrize("resume", [True, False], ids=["resume", "plain-rerun"])
def test_after_removing_the_cause_the_next_run_succeeds(tmp_path: Path, resume: bool) -> None:
    mission, planted, _before, _reflog_before, _result = failing_gate_run(tmp_path, "01M5318R" if resume else "01M5318P")
    remove_carrier_cause(mission, "WP02")

    args = ["consolidate", "--mission", mission.slug, *(["--resume"] if resume else []), "--yes"]
    second = run_terminus(mission, args)

    assert second.returncode == 0, f"after removing the cause the next run must succeed. output={flat(second)}"
    assert blob_present_at(mission.repo, mission.target_branch, "src/pkg/wp01.py"), "WP01 approved work must be attributed on the target"
    assert blob_present_at(mission.repo, mission.target_branch, "src/pkg/wp02.py"), "WP02 approved work must be attributed on the target"
    assert not blob_present_at(mission.repo, mission.target_branch, planted), "the canceled file must never reach the target"


# --------------------------------------------------------------------------- #
# Reconciliation-gate REFUSE
# --------------------------------------------------------------------------- #


def test_gate_refuse_after_fold_all_lanes_restores_target_and_coordination(tmp_path: Path) -> None:
    """All lanes folded into the coordination branch: the approved lanes resolve no commits of their own,
    so the gate REFUSEs ("authored-blob set is empty") AFTER the squash advanced the target. The gate
    CAS-restores the target itself, so the report shows its idempotent ``unchanged`` line."""
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8="01M5318F")
    fold_lanes_into_mission_branch(mission, ["WP01", "WP02"])
    before = ref_shas(mission)

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])
    output = flat(result)
    after = ref_shas(mission)

    assert result.returncode != 0, f"fixture precondition: the gate must REFUSE. output={output}"
    assert "authored-blob set is empty" in output, f"fixture precondition: the empty-authored-set REFUSE. output={output}"
    assert after["target"] == before["target"], f"target left advanced ({before['target']} -> {after['target']}). output={output}"
    assert after["coord"] == before["coord"], f"coordination branch left advanced ({before['coord']} -> {after['coord']}). output={output}"
    assert re.search(rf"unchanged\s+{re.escape(mission.target_branch)}\s+\(already at {before['target'][:7]}\)", output), (
        f"the report must show the target's idempotent 'unchanged (already at <pre>)' line. output={output}"
    )
    assert restored_pairs(output, mission.coord_branch), f"the report must show the coordination-branch restore. output={output}"
    assert_report_is_truthful(output)


# --------------------------------------------------------------------------- #
# Squash-projection refusal
# --------------------------------------------------------------------------- #


def _notes_rel(slug: str) -> str:
    return f"kitty-specs/{slug}/notes/n.md"


def _diverge_notes(mission_repo: Path, slug: str, target_branch: str, lane_branch: str) -> None:
    """Lane edits line 1; the target independently edits line 6 (non-overlapping)."""
    notes = mission_repo / _notes_rel(slug)
    git(mission_repo, "checkout", "-q", target_branch)
    notes.write_text(_NOTES_BASELINE.replace("l6", "l6 target"), encoding="utf-8")
    git(mission_repo, "commit", "-qam", "chore: target-side notes edit")
    git(mission_repo, "checkout", "-q", lane_branch)
    notes.write_text(_NOTES_BASELINE.replace("l1", "l1 lane"), encoding="utf-8")
    git(mission_repo, "commit", "-qam", "chore: lane notes edit")
    git(mission_repo, "checkout", "-q", target_branch)


def test_fresh_projection_refusal_restores_target_and_coordination(tmp_path: Path) -> None:
    """Real trigger: a projected path with NO merge driver (``kitty-specs/<slug>/notes/n.md``).

    It is bookkeeping for the blob-attribution axis (the gate PASSes) and stays projected,
    but has no ``.gitattributes`` driver, so the projection proof's driver replay raises
    ``GitProbeError`` and the proof REFUSEs after the squash advanced the target. The run's
    OWN PASS anchor must not survive (post-tasks BLOCKER 1).
    """
    slug = "terminus-01M5332A"
    mission = build_coord_mission(tmp_path, wps=("WP01",), mid8="01M5332A", extra_base_files={_notes_rel(slug): _NOTES_BASELINE})
    _diverge_notes(mission.repo, mission.slug, mission.target_branch, mission.lane_branch("WP01"))
    before = ref_shas(mission)

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])
    output = flat(result)
    after = ref_shas(mission)

    assert result.returncode == 1, f"a projection refusal must exit 1. output={output}"
    assert _PROJECTION_REFUSE_TEXT in output, f"fixture precondition: the run must hit the projection refusal (real no-driver trigger). output={output}"
    assert after["target"] == before["target"], f"target left advanced ({before['target']} -> {after['target']}). output={output}"
    assert after["coord"] == before["coord"], f"coordination branch left advanced ({before['coord']} -> {after['coord']}). output={output}"
    assert not blob_present_at(mission.repo, mission.target_branch, "src/pkg/wp01.py"), "the refused squash content must be rolled back off the target"
    assert restored_pairs(output, mission.target_branch), f"the report must show the target RESTORED line. output={output}"
    assert restored_pairs(output, mission.coord_branch), f"the report must show the coordination-branch RESTORED line. output={output}"
    bookkeeping = state_bookkeeping(mission)
    assert bookkeeping is not None
    assert bookkeeping["reconciliation_passed_target_sha"] is None, f"BLOCKER 1: the refused run's own PASS anchor must not survive. {bookkeeping}"
    assert bookkeeping["mission_number_baked"] is False and bookkeeping["completed_wps"] == [], bookkeeping


def test_earlier_verified_landing_is_kept_on_resume_projection_refusal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """FR-011 control: a resume whose anchor (from an EARLIER attempt) equals the target tip keeps the landing.

    A real trigger cannot reach this (a resume has nothing new to project once the landing
    is verified), so it drives the production shell in-process and stubs ONLY
    ``_assert_squash_projected_content_landed`` to refuse (state and git are real).
    """
    mission = build_coord_mission(tmp_path, wps=("WP01",), mid8="01M5332B")
    anchored_tip = _complete_squash_then_recreate_mid_teardown_state(mission, "WP01", ["WP01"])
    before = ref_shas(mission)
    assert before["target"] == anchored_tip

    def _refuse(_run: object) -> None:
        raise executor.typer.Exit(1)

    monkeypatch.setattr(executor, "_assert_squash_projected_content_landed", _refuse)
    monkeypatch.setenv("HOME", str(mission.home))
    monkeypatch.chdir(mission.repo)

    with pytest.raises(executor.typer.Exit) as excinfo:
        executor._run_lane_based_consolidation(mission.repo, mission.slug, push=False, delete_branch=None, remove_worktree=None, assume_yes=True)

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "Kept the landing verified by an earlier reconciliation" in " ".join((captured.out + captured.err).split())
    after = ref_shas(mission)
    assert after["target"] == anchored_tip, "FR-011: the landing verified by an earlier reconciliation must be KEPT"
    assert blob_present_at(mission.repo, mission.target_branch, "src/pkg/wp01.py")
    bookkeeping = state_bookkeeping(mission)
    assert bookkeeping is not None and bookkeeping["reconciliation_passed_target_sha"] == anchored_tip, "the earlier anchor must stay intact"
