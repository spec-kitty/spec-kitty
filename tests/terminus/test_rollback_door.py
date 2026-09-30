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
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
import typer

from specify_cli.consolidation import executor
from specify_cli.consolidation.state import get_state_path
from tests.terminus.conftest import CoordMission, blob_present_at, run_terminus
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
