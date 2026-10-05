"""Kill-window and interleave scenarios of the record-anchored rollback authority (#5686, #5666).

Rollback-anchor-authority WP03 (T015). Every scenario runs the production path:
the REAL ``spec-kitty`` CLI in a subprocess where a kill must be modelled (a
``sys.executable -c`` runner that ends the process with ``os._exit(137)`` at a
chosen point, exactly what a SIGKILL leaves behind), and the in-process driver
otherwise. Each one shares :func:`_lanes_mission` with its positive control
(:func:`test_positive_control_the_same_fixture_consolidates`).

* US2 AS1 -- a kill right after the target's compare-and-swap ``update-ref``
  (before and after the checkout resync): ``--abort`` adopts the persisted advance
  intent and restores the target, the repository root checkout is clean and the
  record is cleared.
* US2 AS2/AS3 -- the same kill without a provable intent (the chain removed from
  the record, equivalent to a commit-based move): every re-run refuses with
  ``UNEXPLAINED_BRANCH_MOVE`` and changes nothing; every ``--abort`` reports the
  target NOT restored and keeps the record. No text carries a destructive recipe.
* FR-005 ordering -- the refusal comes before the operator attestations and the
  coord-strand heal.
* US4 AS2 -- an orderly FAIL exit (a foreign commit on the landing) does not
  settle the target: the re-run refuses and ``--abort`` keeps the record.
* US1 AS2 -- a foreign commit between two phases, with the next phase committing
  on top of it, is never recorded as this run's post tip; the door keeps it.
* Orchestrator ruling -- a coord-strand heal that cannot clear its marker leaves
  the coordination branch unsettled, so the claim refuses.
* Residual (fail closed) -- an in-span move that reports no intent (the plain
  ``safe_commit`` of the ``done`` bookkeeping on a LANES target; the primary-tree
  mission-number bake is the other such site) killed before its recorder is
  unprovable and refused.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
import typer

from specify_cli.consolidation import executor
from specify_cli.consolidation.state import get_state_path, load_state
from tests.terminus.conftest import _SRC, CoordMission, _bootstrapped_home_template, run_terminus
from tests.terminus.lanes_fixture import build_lanes_mission
from tests.terminus.rollback_harness import flat, ref_shas

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_CODE = "UNEXPLAINED_BRANCH_MOVE"
_ERROR_CODE_LINE = f"Error code: {_CODE}."
_DESTRUCTIVE = ("reset --hard", "branch -f", "update-ref")
_KILLED = 137


#: R2: the UNEXPLAINED_BRANCH_MOVE remedies, in order (inspect, move it yourself, release with its warning).
_REMEDY_ORDER = ("git log ", "move the branch yourself", "--release-branch")
_RELEASE_WARNING = "a release keeps every commit listed above on the branch"


def _assert_remedy_order(output: str) -> None:
    positions = [output.find(marker) for marker in _REMEDY_ORDER]
    assert all(p >= 0 for p in positions) and positions == sorted(positions), f"remedies out of order {positions}. output={output}"
    assert _RELEASE_WARNING in output, f"the release remedy must warn that it keeps the commits. output={output}"


# Ends the REAL CLI with ``os._exit(137)`` at the target's branch advance. ``before-resync``
# dies between the compare-and-swap ``update-ref`` and the checkout resync (the root
# checkout is left behind its own HEAD); ``after-advance`` dies once ``advance_branch_ref``
# finished (ref moved, checkout resynced), before the phase recorder runs.
_RUNNER = """
import os, sys
import specify_cli
from specify_cli.git import ref_advance

mode, target = sys.argv[1], sys.argv[2]
_real_resync = ref_advance._resync_checkouts

def _resync_then_maybe_die(checkouts, branch, env, *, context):
    advancing = branch == target and context.startswith("Advanced")
    if advancing and mode == "before-resync":
        os._exit(137)
    _real_resync(checkouts, branch, env, context=context)
    if advancing and mode == "after-advance":
        os._exit(137)

ref_advance._resync_checkouts = _resync_then_maybe_die
sys.argv = ["spec-kitty", *sys.argv[3:]]
specify_cli.main()
"""

# Ends the REAL CLI right after the first plain ``safe_commit`` lands on the target: the
# ``commit --only`` path of ``git/commit_helpers.py`` (``_run_commit_capture_sha``) reports no
# advance intent. In a LANES run it is the ``done`` bookkeeping commit inside the door span.
_PLAIN_COMMIT_RUNNER = """
import os, subprocess, sys
import specify_cli
from specify_cli.git import commit_helpers

target = sys.argv[1]
_real = commit_helpers._run_commit_capture_sha

def _commit_then_die(repo_path, *args, **kwargs):
    result = _real(repo_path, *args, **kwargs)
    head = subprocess.run(["git", "-C", str(repo_path), "symbolic-ref", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    if result[0] is not None and head == target:
        os._exit(137)
    return result

commit_helpers._run_commit_capture_sha = _commit_then_die
sys.argv = ["spec-kitty", *sys.argv[2:]]
specify_cli.main()
"""


# ----------------------------------------------------------------------------- harness


def _lanes_mission(tmp_path: Path, mid8: str, *, wps: Sequence[str] = ("WP01",)) -> CoordMission:
    """The ONE fixture builder of every scenario and of the positive control (LANES, target ``develop``)."""
    mission = build_lanes_mission(tmp_path, wps=wps, target_branch="develop", mid8=mid8)
    shutil.copytree(_bootstrapped_home_template(), mission.home, dirs_exist_ok=True)
    return mission


def _cli_env(mission: CoordMission) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_SRC)
    env["HOME"] = str(mission.home)
    env["SPEC_KITTY_NO_UPGRADE_CHECK"] = "1"
    env.pop("VIRTUAL_ENV", None)
    return env


def _run_script(mission: CoordMission, script: str, args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", script, *args], cwd=str(mission.repo), env=_cli_env(mission), capture_output=True, text=True, check=False, timeout=120
    )


def _consolidate_args(mission: CoordMission) -> list[str]:
    return ["consolidate", "--mission", mission.slug, "--yes"]


def _killed_at_target_advance(mission: CoordMission, mode: str) -> subprocess.CompletedProcess[str]:
    result = _run_script(mission, _RUNNER, [mode, mission.target_branch, *_consolidate_args(mission)])
    assert result.returncode == _KILLED, f"fixture precondition: the run must be killed at the target advance. output={flat(result)}"
    return result


def _rerun(mission: CoordMission) -> subprocess.CompletedProcess[str]:
    return run_terminus(mission, _consolidate_args(mission))


def _abort(mission: CoordMission) -> subprocess.CompletedProcess[str]:
    return run_terminus(mission, ["consolidate", "--abort", "--mission", mission.slug])


def _state_path(mission: CoordMission) -> Path:
    return get_state_path(mission.repo, mission.mission_id)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False)


def _rev(repo: Path, branch: str) -> str:
    return _git(repo, "rev-parse", f"refs/heads/{branch}").stdout.strip()


def _is_ancestor(repo: Path, commit: str, branch: str) -> bool:
    return _git(repo, "merge-base", "--is-ancestor", commit, f"refs/heads/{branch}").returncode == 0


def _tracked_dirty(repo: Path) -> str:
    return _git(repo, "status", "--porcelain", "--untracked-files=no").stdout.strip()


def _drop_intent_chain(mission: CoordMission, branch: str) -> None:
    """Remove ``branch``'s advance-intent chain from the REAL record (a move with no persisted proof)."""
    path = _state_path(mission)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert branch in data.get("advance_intents", {}), f"fixture precondition: the killed advance persisted an intent. record={data}"
    del data["advance_intents"][branch]
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _assert_no_destructive_recipe(output: str) -> None:
    assert not any(recipe in output for recipe in _DESTRUCTIVE), f"C-002: no destructive recipe in operator text. output={output}"


def _assert_refused_unexplained(result: subprocess.CompletedProcess[str], branch: str) -> str:
    output = flat(result)
    assert result.returncode == 1, f"the re-run must refuse with exit 1. output={output}"
    assert _ERROR_CODE_LINE in output and branch in output, f"the refusal must name {_CODE} and the branch. output={output}"
    _assert_no_destructive_recipe(output)
    _assert_remedy_order(output)
    return output


def _assert_abort_keeps_the_record(mission: CoordMission, result: subprocess.CompletedProcess[str]) -> None:
    output = flat(result)
    target = mission.target_branch
    assert result.returncode == 1, f"--abort must not succeed over an unexplained tip. output={output}"
    assert re.search(rf"NOT restored {re.escape(target)}\b", output), f"--abort must report {target} NOT restored. output={output}"
    assert not re.search(rf"(?<!NOT )\b(unchanged|restored)\s+{re.escape(target)}\s", output), f"never 'unchanged'/'restored' for {target}. output={output}"
    assert "Branches restored to their pre-consolidation commits" not in output, output
    _assert_no_destructive_recipe(output)
    assert _state_path(mission).is_file(), "the record is kept"
    state = load_state(mission.repo, mission.mission_id)
    assert state is not None and target in state.unsettled_refs, "the target stays unsettled"


# ------------------------------------------------------------------ positive control


def test_positive_control_the_same_fixture_consolidates(tmp_path: Path) -> None:
    """No kill, no foreign commit: the same fixture and runner consolidate successfully."""
    mission = _lanes_mission(tmp_path, "01M5686C")
    before = ref_shas(mission)

    result = _run_script(mission, _RUNNER, ["none", mission.target_branch, *_consolidate_args(mission)])

    assert result.returncode == 0, f"the control run must succeed. output={flat(result)}"
    assert _rev(mission.repo, mission.target_branch) != before["target"], "the landing advanced the target"
    assert not _state_path(mission).exists(), "a successful run clears its record"


# -------------------------------------------------------------------- US2 AS1 (adopt)


@pytest.mark.parametrize("mode", ["before-resync", "after-advance"])
def test_abort_after_a_kill_at_the_target_advance_adopts_the_intent_and_restores(tmp_path: Path, mode: str) -> None:
    mission = _lanes_mission(tmp_path, "01M5686K" if mode == "before-resync" else "01M5686V")
    before = ref_shas(mission)
    _killed_at_target_advance(mission, mode)
    assert _rev(mission.repo, mission.target_branch) != before["target"], "fixture precondition: the kill left the landing on the target"

    result = _abort(mission)

    output = flat(result)
    assert result.returncode == 0, f"--abort must restore a provable kill-left advance. output={output}"
    assert _rev(mission.repo, mission.target_branch) == before["target"], f"the target is back at its pre-run tip. output={output}"
    assert re.search(rf"restored {re.escape(mission.target_branch)} .*\(adopted interrupted advance\)", output), output
    assert _tracked_dirty(mission.repo) == "", f"the repository root checkout is clean. status={_tracked_dirty(mission.repo)}"
    assert not _state_path(mission).exists(), "a full restore clears the record"


# -------------------------------------------------------------- US2 AS2/AS3 (refuse)


def _remove_the_dead_runs_lock(mission: CoordMission) -> None:
    """The killed process never released the global merge lock; the operator removes it, as ``MergeLockError`` says."""
    lock = mission.repo / ".kittify" / "runtime" / "merge" / "__global_merge__" / "lock"
    assert lock.is_file(), "fixture precondition: the killed run left its lock behind"
    lock.unlink()


def _unprovable_kill(tmp_path: Path, mid8: str, *, wps: Sequence[str] = ("WP01",)) -> CoordMission:
    mission = _lanes_mission(tmp_path, mid8, wps=wps)
    _killed_at_target_advance(mission, "after-advance")
    _remove_the_dead_runs_lock(mission)
    _drop_intent_chain(mission, mission.target_branch)
    return mission


def test_unprovable_kill_left_move_is_refused_idempotently_and_never_restored(tmp_path: Path) -> None:
    mission = _unprovable_kill(tmp_path, "01M5686U")
    landed = _rev(mission.repo, mission.target_branch)
    refs = ref_shas(mission)
    record = _state_path(mission).read_bytes()

    for attempt in (1, 2):
        output = _assert_refused_unexplained(_rerun(mission), mission.target_branch)
        assert landed in output, f"the refusal names the live SHA (attempt {attempt}). output={output}"
        assert _state_path(mission).read_bytes() == record, f"the refusal changes nothing in the record (attempt {attempt})"
        assert ref_shas(mission) == refs, f"the refusal moves no branch (attempt {attempt})"

    for _attempt in (1, 2):
        _assert_abort_keeps_the_record(mission, _abort(mission))
        assert _rev(mission.repo, mission.target_branch) == landed, "--abort never moves an unexplained tip"


def _ordering_fixture(tmp_path: Path, mid8: str, *, provable: bool) -> CoordMission:
    """A kill-left target landing (provable or not), a valid attestation request and a pending coord-reconcile marker."""
    mission = _lanes_mission(tmp_path, mid8)
    _cancel_wp_on_target(mission, "WP09")  # before the run: a target commit after the kill would itself be unexplained
    _killed_at_target_advance(mission, "after-advance")
    _remove_the_dead_runs_lock(mission)
    if not provable:
        _drop_intent_chain(mission, mission.target_branch)
    state_path = _state_path(mission)
    data = json.loads(state_path.read_text(encoding="utf-8"))
    data["pending_coord_reconcile"] = {
        "coord_ref": mission.coord_branch,  # LANES: the mission branch; the unexplained branch is the target
        "captured_sha": data["pre_mutation_refs"][mission.coord_branch],
        "coord_worktree": str(mission.repo),
        "stranded_wp_ids": ["WP01"],
    }
    state_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return mission


class _HealReached(Exception):
    """Stops the positive control once the heal is reached (the ordering is all it proves)."""


def _consolidate_with_attestation(mission: CoordMission, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(mission.home))
    monkeypatch.chdir(mission.repo)
    executor._run_lane_based_consolidation(
        mission.repo,
        mission.slug,
        push=False,
        delete_branch=None,
        remove_worktree=None,
        assume_yes=True,
        attest_canceled_superseded=("WP09",),
        attest_reason="x",
    )


def test_the_refusal_precedes_the_attestations_and_the_heal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """FR-005: nothing that can move a branch runs before the refusal (attestation status commits, the strand heal)."""
    mission = _ordering_fixture(tmp_path, "01M5686O", provable=False)
    state_path = _state_path(mission)
    record = state_path.read_bytes()
    refs = ref_shas(mission)
    events = (mission.feature_dir / "status.events.jsonl").read_text(encoding="utf-8")
    called: list[str] = []
    for name in ("_record_operator_attestations", "_heal_pending_coord_reconcile"):
        real = getattr(executor, name)
        monkeypatch.setattr(executor, name, _spy(called, name, real))

    with pytest.raises(typer.Exit) as excinfo:
        _consolidate_with_attestation(mission, monkeypatch)

    output = " ".join(capsys.readouterr().out.split())
    assert excinfo.value.exit_code == 1 and _ERROR_CODE_LINE in output, output
    assert called == [], f"neither the attestations nor the heal may run before the refusal: {called}"
    assert "Operator attestation recorded" not in output
    assert (mission.feature_dir / "status.events.jsonl").read_text(encoding="utf-8") == events, "no status event appended"
    assert ref_shas(mission) == refs, "no revert or status commit was created"
    assert state_path.read_bytes() == record, "the record is unchanged"


def test_positive_control_the_attestations_and_the_heal_run_when_the_move_is_explained(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Same fixture with the intent chain kept: the move is provable, so both spies fire (the pin above is not vacuous)."""
    mission = _ordering_fixture(tmp_path, "01M5686P", provable=True)
    called: list[str] = []
    monkeypatch.setattr(executor, "_record_operator_attestations", _spy(called, "_record_operator_attestations", executor._record_operator_attestations))

    def heal_reached(_run: Any) -> None:
        called.append("_heal_pending_coord_reconcile")
        raise _HealReached

    monkeypatch.setattr(executor, "_heal_pending_coord_reconcile", heal_reached)

    with pytest.raises(_HealReached):
        _consolidate_with_attestation(mission, monkeypatch)

    output = " ".join(capsys.readouterr().out.split())
    assert called == ["_record_operator_attestations", "_heal_pending_coord_reconcile"], output
    assert _ERROR_CODE_LINE not in output, output


def _cancel_wp_on_target(mission: CoordMission, wp: str) -> None:
    """Record an operator cancellation of ``wp`` on the target (so the attestation request is valid if reached)."""
    from tests.terminus.conftest import _cancel_event

    log = mission.feature_dir / "status.events.jsonl"
    with log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_cancel_event(mission, wp), sort_keys=True) + "\n")
    (mission.feature_dir / "tasks" / f"{wp}-work.md").write_text(f"---\nwork_package_id: {wp}\ntitle: {wp}\n---\n# {wp}\n", encoding="utf-8")
    _git(mission.repo, "add", "-A", str(mission.feature_dir))
    _git(mission.repo, "commit", "-qm", f"operator cancels {wp}")


def _spy(calls: list[str], name: str, real: Any) -> Any:
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        calls.append(name)
        return real(*args, **kwargs)

    return wrapper


# ------------------------------------------------------- US4 AS2 (orderly exit, FAIL)


def _teammate_commit(repo: Path, name: str) -> str:
    """Another actor commits ONLY its own file in the repository root checkout (never this run's pending bookkeeping)."""
    path = f"{name}.txt"
    (repo / path).write_text(f"{name}\n", encoding="utf-8")
    _git(repo, "add", "--", path)
    _git(repo, "commit", "-qm", name, "--only", "--", path)
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _consolidate_in_process(mission: CoordMission) -> None:
    executor._run_lane_based_consolidation(mission.repo, mission.slug, push=False, delete_branch=None, remove_worktree=None, assume_yes=True)


def test_an_orderly_fail_exit_does_not_settle_the_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    mission = _lanes_mission(tmp_path, "01M5686E")
    real_gate = executor._phase_reconcile_before_teardown
    foreign: list[str] = []

    def gate_after_a_teammate_commit(run: Any) -> None:
        foreign.append(_teammate_commit(mission.repo, "teammate-commit"))
        real_gate(run)

    monkeypatch.setattr(executor, "_phase_reconcile_before_teardown", gate_after_a_teammate_commit)
    monkeypatch.setenv("HOME", str(mission.home))
    monkeypatch.chdir(mission.repo)
    with pytest.raises(typer.Exit):
        _consolidate_in_process(mission)
    first = " ".join(capsys.readouterr().out.split())
    assert re.search(rf"NOT restored {re.escape(mission.target_branch)} .*moved by another actor", first), first
    monkeypatch.setattr(executor, "_phase_reconcile_before_teardown", real_gate)
    record = _state_path(mission).read_bytes()

    with pytest.raises(typer.Exit) as excinfo:
        _consolidate_in_process(mission)

    output = " ".join(capsys.readouterr().out.split())
    assert excinfo.value.exit_code == 1 and _ERROR_CODE_LINE in output, f"the orderly FAIL left the target unsettled. output={output}"
    assert _state_path(mission).read_bytes() == record
    _assert_abort_keeps_the_record(mission, _abort(mission))
    assert _is_ancestor(mission.repo, foreign[0], mission.target_branch), "the teammate's commit survives"


# ------------------------------------------------- US1 AS2 (interleave between phases)


def test_a_foreign_commit_between_phases_survives_the_door(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    mission = _lanes_mission(tmp_path, "01M5686I")
    real_phase = executor._phase_commit_and_assert
    foreign: list[str] = []

    def commit_after_a_teammate_commit(run: Any) -> None:
        foreign.append(_teammate_commit(mission.repo, "teammate-between-phases"))
        real_phase(run)

    monkeypatch.setattr(executor, "_phase_commit_and_assert", commit_after_a_teammate_commit)
    monkeypatch.setenv("HOME", str(mission.home))
    monkeypatch.chdir(mission.repo)

    with pytest.raises(typer.Exit) as excinfo:
        _consolidate_in_process(mission)

    output = " ".join(capsys.readouterr().out.split())
    target = mission.target_branch
    assert excinfo.value.exit_code == 1, f"the gate FAILs on the foreign path. output={output}"
    assert _rev(mission.repo, target) != foreign[0], "precondition: the phase committed on top of the foreign commit"
    assert _is_ancestor(mission.repo, foreign[0], target), f"the foreign commit stays reachable from {target}. output={output}"
    assert re.search(rf"NOT restored {re.escape(target)} ", output), f"the door reports {target} NOT restored. output={output}"


# ---------------------------------------------- ruling: a heal that cannot clear refuses


def test_a_heal_that_cannot_clear_its_marker_leaves_the_coordination_branch_refused(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from unittest.mock import patch

    from tests.consolidation.test_issue_2711_merge_rollback_resume_coherence import COORD_BRANCH, MISSION_ID, _bootstrap_coord_mission, _init_git_repo
    from tests.consolidation.test_issue_2786_revert_failure_split_brain import _run_merge_with_target_failing

    repo = tmp_path / "repo"
    _init_git_repo(repo)
    _bootstrap_coord_mission(repo)
    _run_merge_with_target_failing(repo, coord_moved_by_another_actor=True)
    capsys.readouterr()
    foreign_tip = _rev(repo, COORD_BRANCH)
    record = get_state_path(repo, MISSION_ID).read_bytes()

    with patch.object(executor, "_heal_pending_coord_reconcile", lambda _run: None):
        exc = _run_merge_with_target_failing(repo, coord_moved_by_another_actor=False)

    output = " ".join(capsys.readouterr().out.split())
    assert isinstance(exc, typer.Exit) and exc.exit_code == 1, f"the claim must refuse; got {exc!r}. output={output}"
    assert _ERROR_CODE_LINE in output and COORD_BRANCH in output, output
    assert get_state_path(repo, MISSION_ID).read_bytes() == record, "the refusal keeps the record unchanged"
    assert _rev(repo, COORD_BRANCH) == foreign_tip, "the coordination branch is untouched"


# --------------------------------------------- residual: an in-span move with no intent


def test_a_kill_after_an_intentless_in_span_commit_is_refused(tmp_path: Path) -> None:
    """Residual (fail closed): a plain ``safe_commit`` on the target reports no intent; killed before its recorder it is refused."""
    mission = _lanes_mission(tmp_path, "01M5686N")
    before = ref_shas(mission)
    killed = _run_script(mission, _PLAIN_COMMIT_RUNNER, [mission.target_branch, *_consolidate_args(mission)])
    assert killed.returncode == _KILLED, f"fixture precondition: the plain target commit must be killed. output={flat(killed)}"
    landed = _rev(mission.repo, mission.target_branch)
    assert landed != before["target"], "fixture precondition: the plain commit moved the target"
    state = load_state(mission.repo, mission.mission_id)
    assert state is not None and landed not in state.advance_intents.get(mission.target_branch, []), "precondition: no intent proves it"
    _remove_the_dead_runs_lock(mission)
    record = _state_path(mission).read_bytes()

    output = _assert_refused_unexplained(_rerun(mission), mission.target_branch)

    assert landed in output and _state_path(mission).read_bytes() == record, f"the refusal changes nothing. output={output}"
    _assert_abort_keeps_the_record(mission, _abort(mission))


# ------------------------- P1: a foreign commit between the pre-check and the claim


def _promote_intent_to_recorded_post(mission: CoordMission, branch: str) -> str:
    """Turn the killed advance's intent into a recorded post tip (a kill after the phase recorder ran)."""
    path = _state_path(mission)
    data = json.loads(path.read_text(encoding="utf-8"))
    landed = _rev(mission.repo, branch)
    assert landed in data.get("advance_intents", {}).get(branch, []), f"fixture precondition: the intent proves the landing. record={data}"
    del data["advance_intents"][branch]
    data.setdefault("post_mutation_refs", {})[branch] = landed
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return landed


def test_a_foreign_commit_between_the_precheck_and_the_claim_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A commit landing on the target after the pre-check (e.g. during an interactive prompt) is not this process's own move.

    The resume starts with the target at its recorded post tip, so the pre-check
    passes. A teammate then commits on the target before the claim. The claim must
    not carry that commit as this run's post tip (a later rollback would CAS it
    away); it refuses ``UNEXPLAINED_BRANCH_MOVE`` and the commit stays.
    """
    mission = _lanes_mission(tmp_path, "01M5686F")
    _killed_at_target_advance(mission, "after-advance")
    _remove_the_dead_runs_lock(mission)
    _promote_intent_to_recorded_post(mission, mission.target_branch)
    real_gates = executor._phase_gates_and_state
    foreign: list[str] = []

    def gates_after_a_teammate_commit(run: Any) -> None:
        _git(mission.repo, "checkout", "-q", mission.target_branch)
        foreign.append(_teammate_commit(mission.repo, "teammate-during-the-gates"))
        real_gates(run)

    monkeypatch.setattr(executor, "_phase_gates_and_state", gates_after_a_teammate_commit)
    monkeypatch.setenv("HOME", str(mission.home))
    monkeypatch.chdir(mission.repo)

    with pytest.raises(typer.Exit) as excinfo:
        _consolidate_in_process(mission)

    output = " ".join(capsys.readouterr().out.split())
    assert foreign, f"fixture precondition: the teammate commit landed before the claim. output={output}"
    assert excinfo.value.exit_code == 1 and _ERROR_CODE_LINE in output, f"the claim must refuse the foreign commit. output={output}"
    assert _rev(mission.repo, mission.target_branch) == foreign[0], "the teammate's commit stays the target tip"
    state = load_state(mission.repo, mission.mission_id)
    assert state is not None and state.post_mutation_refs.get(mission.target_branch) != foreign[0], "never carried as this run's post"
