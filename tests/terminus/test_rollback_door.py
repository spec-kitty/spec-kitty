"""Every post-mutation consolidate exit rolls back through one door (#5385).

Pre-fix, only the reconciliation gate (and ``--abort``) called the single CAS
rollback authority. Any other exit between the first mutation
(``_phase_merge_lanes``) and the gate relied on per-phase ``git revert`` helpers
or on nothing, so the target (and the mission branch) stayed advanced past the
pre-run snapshot. The literal #5385 shape: a LANES mission targeting protected
``main`` squashes onto ``main``, then ``BookkeepingPolicyRefused`` escapes
``_phase_record_done_and_project`` as a raw traceback with ``main`` advanced.

Contract (``kitty-specs/single-rollback-authority-01M3RCP4/contracts/rollback-door.md``):
a non-zero ``typer.Exit``, any other exception, or an interrupt raised anywhere
in that span restores the target and the mission branch to their pre-run tips
through ``rollback_to_snapshot``, prints the one rollback report, moves no lane
branch, and re-raises the original error.

Real git throughout: the only patch is the failure injection, a wrapper
that calls the ORIGINAL phase (so its real mutation happens and its post tips are
recorded) and then raises.

#5666: a reconciliation FAIL is restored by this door too; the gate itself
moves nothing. The door compare-and-swaps against the post tip this run
recorded, so a commit another actor lands on the target after the landing is
kept and reported NOT restored, while with no foreign commit (the US1 AS3
positive control) the target is fully restored and the repository root checkout
is clean. Both run on the LANES and the coordination topology fixtures.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
import typer

from specify_cli.consolidation import executor
from specify_cli.consolidation.reconciliation import Divergence, MergeOutcomeVerifier, VerifyResult
from specify_cli.consolidation.state import get_state_path
from tests.terminus.conftest import CoordMission, blob_present_at, build_coord_mission, run_terminus
from tests.terminus.lanes_fixture import build_lanes_mission
from tests.terminus.rollback_harness import flat, ref_shas, reflog_shas

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_REPORT_HEADER = "Rollback to the pre-consolidation snapshot"

_PHASES = (
    "_phase_merge_lanes",
    "_phase_bake_and_pre_target_done",
    "_phase_mission_to_target",
    "_phase_capture_and_baseline",
    "_phase_record_done_and_project",
    "_phase_porcelain_invariant",
    "_phase_commit_and_assert",
)
# Phases that run after the squash moved the target: the target reflog proves it moved.
_TARGET_MOVED_PHASES = frozenset(_PHASES[2:])


def _exit_one() -> BaseException:
    return typer.Exit(1)


def _planted() -> BaseException:
    return RuntimeError("planted")


def _interrupt() -> BaseException:
    return KeyboardInterrupt()


_RAISES: dict[str, Callable[[], BaseException]] = {"exit1": _exit_one, "runtime": _planted, "interrupt": _interrupt}

_CASES = [(phase, kind) for phase in _PHASES for kind in ("exit1", "runtime")] + [("_phase_mission_to_target", "interrupt")]


def _inject_after(monkeypatch: pytest.MonkeyPatch, phase: str, make_error: Callable[[], BaseException]) -> None:
    """Replace ``executor.<phase>`` with a wrapper that runs the real phase, then raises."""
    original = getattr(executor, phase)

    def failing(run: object) -> None:
        original(run)
        raise make_error()

    monkeypatch.setattr(executor, phase, failing)


def _consolidate(mission: CoordMission, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(mission.home))
    monkeypatch.chdir(mission.repo)
    executor._run_lane_based_consolidation(mission.repo, mission.slug, push=False, delete_branch=None, remove_worktree=None, assume_yes=True)


def _record(mission: CoordMission) -> dict[str, object] | None:
    path = get_state_path(mission.repo, mission.mission_id)
    if not path.exists():
        return None
    payload: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
    return payload


def _mid8(phase: str, kind: str) -> str:
    return f"01M538{_PHASES.index(phase)}{'ERK'[list(_RAISES).index(kind)]}"


def _assert_moved_and_restored(mission: CoordMission, branch: str, pre: str, reflog_before: int) -> None:
    """Vacuity guard: *branch* really moved during the run and its newest reflog entry is the restore."""
    reflog = reflog_shas(mission, branch)
    assert len(reflog) - reflog_before >= 2, f"{branch} must have advanced AND been restored during the run; reflog={reflog}"
    assert reflog[0] == pre, f"{branch}: newest reflog entry is not the pre-run SHA; reflog={reflog}"
    assert len(set(reflog[: len(reflog) - reflog_before])) >= 2, f"vacuous oracle: {branch} never left its pre-run SHA"


@pytest.mark.parametrize(("phase", "kind"), _CASES, ids=[f"{p.removeprefix('_phase_')}-{k}" for p, k in _CASES])
def test_failure_in_a_post_mutation_phase_restores_every_movable_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], phase: str, kind: str
) -> None:
    mission = build_lanes_mission(tmp_path, wps=("WP01", "WP02"), target_branch="develop", mid8=_mid8(phase, kind))
    before = ref_shas(mission)
    target_reflog = len(reflog_shas(mission, mission.target_branch))
    mission_reflog = len(reflog_shas(mission, mission.coord_branch))
    make_error = _RAISES[kind]
    _inject_after(monkeypatch, phase, make_error)

    with pytest.raises(type(make_error())) as excinfo:
        _consolidate(mission, monkeypatch)

    if kind == "exit1":
        assert isinstance(excinfo.value, typer.Exit) and excinfo.value.exit_code == 1
    if kind == "runtime":
        assert str(excinfo.value) == "planted", "the ORIGINAL exception must propagate unchanged"
    output = " ".join(capsys.readouterr().out.split())
    after = ref_shas(mission)
    assert after["target"] == before["target"], f"#5385: {phase} failure left the target advanced. output={output}"
    assert after["coord"] == before["coord"], f"#5385: {phase} failure left the mission branch advanced. output={output}"
    assert {k: v for k, v in after.items() if k.startswith("lane:")} == {k: v for k, v in before.items() if k.startswith("lane:")}, "a lane branch moved"
    assert _REPORT_HEADER in output, f"the rollback report must be printed. output={output}"
    assert not blob_present_at(mission.repo, mission.target_branch, "src/pkg/wp01.py"), "the squashed content must be gone from the target"

    _assert_moved_and_restored(mission, mission.coord_branch, before["coord"], mission_reflog)
    if phase in _TARGET_MOVED_PHASES:
        _assert_moved_and_restored(mission, mission.target_branch, before["target"], target_reflog)


def test_dirty_target_checkout_is_reported_not_restored_and_the_record_is_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The porcelain invariant trips on a real dirty target checkout; the rollback never overwrites it."""
    mission = build_lanes_mission(tmp_path, wps=("WP01", "WP02"), target_branch="develop", mid8="01M5385D")
    before = ref_shas(mission)
    original = executor._phase_capture_and_baseline

    def dirty_after(run: object) -> None:
        original(run)
        (mission.repo / "README.md").write_text("operator edit\n", encoding="utf-8")

    monkeypatch.setattr(executor, "_phase_capture_and_baseline", dirty_after)

    with pytest.raises(typer.Exit) as excinfo:
        _consolidate(mission, monkeypatch)

    assert excinfo.value.exit_code == 1
    output = " ".join(capsys.readouterr().out.split())
    after = ref_shas(mission)
    assert "Post-merge working-tree invariant violated" in output, f"precondition: the real invariant must trip. output={output}"
    assert f"NOT restored {mission.target_branch}" in output, f"the dirty target checkout must be reported NOT restored. output={output}"
    assert after["target"] != before["target"], "the dirty target is left where it is, never overwritten"
    assert (mission.repo / "README.md").read_text(encoding="utf-8") == "operator edit\n", "the operator's edit must survive"
    assert after["coord"] == before["coord"], f"the mission branch must still be restored. output={output}"
    assert _record(mission) is not None, "a partial rollback keeps the record for --abort"


def test_record_is_truthful_after_rollback_and_a_rerun_succeeds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """The kept record claims nothing, and a re-run after removing the cause lands both lanes."""
    mission = build_lanes_mission(tmp_path, wps=("WP01", "WP02"), target_branch="develop", mid8="01M5385S")
    before = ref_shas(mission)
    with monkeypatch.context() as patch:
        _inject_after(patch, "_phase_record_done_and_project", _planted)
        with pytest.raises(RuntimeError, match="planted"):
            _consolidate(mission, patch)
    capsys.readouterr()
    assert ref_shas(mission) == before, "precondition: the failed run was fully rolled back"
    record = _record(mission)
    assert record is not None, "a fully rolled-back run keeps its record for a resume"
    assert record["completed_wps"] == [], record
    assert record["mission_number_baked"] is False, record

    _consolidate(mission, monkeypatch)

    for wp_file in ("src/pkg/wp01.py", "src/pkg/wp02.py"):
        assert blob_present_at(mission.repo, mission.target_branch, wp_file), f"{wp_file} must land on the target after the re-run"


def test_protected_main_lanes_mission_never_leaves_main_advanced(tmp_path: Path) -> None:
    """The literal #5385 shape through the real CLI: LANES mission, protected ``main``."""
    mission = build_lanes_mission(tmp_path, wps=("WP01", "WP02"), target_branch="main", mid8="01M5385M")
    before = ref_shas(mission)

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])
    output = flat(result)

    assert result.returncode != 0, f"the protected-target done write must fail the run. output={output}"
    assert ref_shas(mission)["target"] == before["target"], f"#5385: main left advanced. output={output}"
    assert not blob_present_at(mission.repo, mission.target_branch, "src/pkg/wp01.py"), "squashed content must not stay on main"


# --------------------------------------------------------------------------- #
# #5666: a reconciliation FAIL restores through the door only
# --------------------------------------------------------------------------- #


def _build(topology: str, tmp_path: Path, mid8: str) -> CoordMission:
    if topology == "lanes":
        return build_lanes_mission(tmp_path, wps=("WP01", "WP02"), target_branch="develop", mid8=mid8)
    return build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8=mid8)


def _force_gate_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    """The real gate runs, but its verifier returns a proven FAIL (the verdict under test)."""
    failed = VerifyResult.failed(Divergence(missing_approved=(("WP01", "a" * 40),)))
    monkeypatch.setattr(MergeOutcomeVerifier, "verify", lambda self, target_ref, claim: failed)


def _porcelain(repo: Path) -> list[str]:
    """``git status --porcelain`` lines, minus the kept consolidation record (``.kittify/`` is untracked in these fixtures)."""
    out = subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if line != "?? .kittify/"]


def _commit_on_target(mission: CoordMission, name: str) -> str:
    """A teammate's commit on the target, made in the repository root checkout."""
    checked_out = subprocess.run(["git", "symbolic-ref", "--short", "HEAD"], cwd=mission.repo, capture_output=True, text=True, check=True)
    assert checked_out.stdout.strip() == mission.target_branch, "precondition: the root checkout is on the target"
    (mission.repo / name).write_text("teammate work\n", encoding="utf-8")
    subprocess.run(["git", "add", name], cwd=mission.repo, check=True)
    subprocess.run(["git", "commit", "-qm", f"teammate: {name}"], cwd=mission.repo, check=True)
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=mission.repo, capture_output=True, text=True, check=True).stdout.strip()


_TOPOLOGIES = ("lanes", "coord")


@pytest.mark.parametrize("topology", _TOPOLOGIES)
def test_gate_fail_without_a_foreign_commit_fully_restores_through_the_door(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], topology: str
) -> None:
    """US1 AS3 positive control: no foreign commit, a gate FAIL, a full restore and a clean root checkout."""
    mission = _build(topology, tmp_path, f"01M5666{topology[0].upper()}")
    before = ref_shas(mission)
    target_reflog = len(reflog_shas(mission, mission.target_branch))
    _force_gate_fail(monkeypatch)

    with pytest.raises(typer.Exit) as excinfo:
        _consolidate(mission, monkeypatch)

    assert excinfo.value.exit_code == 1
    output = " ".join(capsys.readouterr().out.split())
    assert "Reconciliation FAILED" in output, f"precondition: the gate must FAIL. output={output}"
    assert _REPORT_HEADER in output, f"the door's rollback report must be printed. output={output}"
    assert re.search(rf"restored {re.escape(mission.target_branch)} [0-9a-f]{{7}} -> {before['target'][:7]}", output), (
        f"the door, not the gate, must restore the target. output={output}"
    )
    report = output[output.index(_REPORT_HEADER) :]
    assert "NOT restored" not in report, f"a FAIL with no foreign commit must restore fully. report={report}"
    after = ref_shas(mission)
    assert after["target"] == before["target"], f"target not restored. output={output}"
    assert after["coord"] == before["coord"], f"mission/coordination branch not restored. output={output}"
    _assert_moved_and_restored(mission, mission.target_branch, before["target"], target_reflog)
    assert _porcelain(mission.repo) == [], f"the repository root checkout must be clean after the restore: {_porcelain(mission.repo)!r}"
    assert not blob_present_at(mission.repo, mission.target_branch, "src/pkg/wp01.py"), "the landed content must be gone from the target"


@pytest.mark.parametrize("topology", _TOPOLOGIES)
def test_gate_fail_keeps_a_concurrent_target_commit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], topology: str) -> None:
    """#5666 end to end: the real gate FAILs on a teammate's un-attributable commit, which the door keeps."""
    mission = _build(topology, tmp_path, f"01M5666{'XY'[_TOPOLOGIES.index(topology)]}")
    before = ref_shas(mission)
    original_gate = executor._phase_reconcile_before_teardown
    foreign: list[str] = []

    def gate_after_a_teammate_commit(run: executor._MergeRunState) -> None:
        foreign.append(_commit_on_target(mission, "teammate.txt"))
        original_gate(run)

    monkeypatch.setattr(executor, "_phase_reconcile_before_teardown", gate_after_a_teammate_commit)

    with pytest.raises(typer.Exit) as excinfo:
        _consolidate(mission, monkeypatch)

    assert excinfo.value.exit_code == 1
    output = " ".join(capsys.readouterr().out.split())
    assert "Reconciliation FAILED" in output and "teammate.txt" in output, f"precondition: the real gate FAILs on the foreign path. output={output}"
    assert foreign and ref_shas(mission)["target"] == foreign[0], f"#5666: the teammate commit must stay the target tip. output={output}"
    assert re.search(rf"NOT restored {re.escape(mission.target_branch)} .*moved by another actor", output), output
    assert (mission.repo / "teammate.txt").is_file(), "the teammate's file must survive in the repository root checkout"
    assert ref_shas(mission)["coord"] == before["coord"], f"the mission/coordination branch is still restored. output={output}"


@pytest.mark.parametrize("topology", _TOPOLOGIES)
def test_a_commit_landing_during_verification_refuses_and_is_never_anchored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], topology: str
) -> None:
    """F3 (a): a PASS over a target that moved during ``verify()`` is a REFUSE; the door keeps the commit and no anchor is written."""
    mission = _build(topology, tmp_path, f"01M5686{'VW'[_TOPOLOGIES.index(topology)]}")
    pre_run_target = ref_shas(mission)["target"]
    foreign: list[str] = []

    def verify_while_a_teammate_commits(self: MergeOutcomeVerifier, target_ref: str, claim: object) -> VerifyResult:
        foreign.append(_commit_on_target(mission, "during-verify.txt"))
        return VerifyResult.passed()

    monkeypatch.setattr(MergeOutcomeVerifier, "verify", verify_while_a_teammate_commits)

    with pytest.raises(typer.Exit) as excinfo:
        _consolidate(mission, monkeypatch)

    assert excinfo.value.exit_code == 1
    output = " ".join(capsys.readouterr().out.split())
    assert "moved while reconciliation was verifying" in output, output
    assert foreign and ref_shas(mission)["target"] == foreign[0], f"the commit that landed during verification must be kept. output={output}"
    assert re.search(rf"NOT restored {re.escape(mission.target_branch)} .*moved by another actor", output), output
    record = _record(mission)
    assert record is not None and record.get("reconciliation_passed_target_sha") is None, "a moved target is never anchored as verified"
    # Fold review: honest, non-destructive next steps (C-002); a plain resume cannot succeed here.
    assert f"git log {pre_run_target}..{foreign[0]}" in output, output
    assert f'spec-kitty consolidate --abort --release-branch {mission.target_branch} --release-reason "<why>"' in output, output
    assert "will refuse with UNEXPLAINED_BRANCH_MOVE" in output, output
    assert "then re-run `spec-kitty consolidate --resume`" not in output, output
    assert not any(recipe in output for recipe in ("reset --hard", "branch -f", "update-ref", "push --force")), output

    with pytest.raises(typer.Exit) as resumed:
        _consolidate(mission, monkeypatch)
    resume_output = " ".join(capsys.readouterr().out.split())
    assert resumed.value.exit_code == 1 and "Error code: UNEXPLAINED_BRANCH_MOVE." in resume_output, resume_output
    assert ref_shas(mission)["target"] == foreign[0], "the refused resume moves nothing"


def test_the_pass_anchor_is_persisted_only_after_the_projection_proof(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """F3 (b): while the squash projection proof runs, no PASS anchor is on disk; a projection refusal leaves none behind."""
    from specify_cli.consolidation import phase_gate

    mission = _build("coord", tmp_path, "01M5686A")
    anchors_seen: list[object] = []

    def refusing_projection_proof(run: executor._MergeRunState) -> None:
        record = _record(mission)
        anchors_seen.append(None if record is None else record.get("reconciliation_passed_target_sha"))
        raise typer.Exit(1)

    monkeypatch.setattr(phase_gate, "_assert_squash_projected_content_landed", refusing_projection_proof)

    with pytest.raises(typer.Exit):
        _consolidate(mission, monkeypatch)

    assert anchors_seen == [None], f"the anchor must not be persisted before the projection proof passed: {anchors_seen}"
    record = _record(mission)
    assert record is None or record.get("reconciliation_passed_target_sha") is None


def test_a_commit_landing_during_the_projection_proof_refuses_and_is_never_anchored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """P3: the moved-target check runs again right before the PASS anchor, so a move during the projection proof is caught too."""
    from specify_cli.consolidation import phase_gate

    mission = _build("lanes", tmp_path, "01M5686Q")
    real_proof = phase_gate._assert_squash_projected_content_landed
    foreign: list[str] = []

    def proof_then_a_teammate_commit(run: executor._MergeRunState) -> None:
        real_proof(run)
        foreign.append(_commit_on_target(mission, "during-projection.txt"))

    monkeypatch.setattr(phase_gate, "_assert_squash_projected_content_landed", proof_then_a_teammate_commit)

    with pytest.raises(typer.Exit) as excinfo:
        _consolidate(mission, monkeypatch)

    output = " ".join(capsys.readouterr().out.split())
    assert excinfo.value.exit_code == 1 and "moved while reconciliation was verifying" in output, output
    assert foreign and ref_shas(mission)["target"] == foreign[0], f"the commit that landed during the projection proof is kept. output={output}"
    assert re.search(rf"NOT restored {re.escape(mission.target_branch)} .*moved by another actor", output), output
    record = _record(mission)
    assert record is not None and record.get("reconciliation_passed_target_sha") is None, "a moved target is never anchored as verified"
