"""The consolidation record's baseline after a rollback (#6770) — a clean rollback must leave nothing
that bends the next attempt's baseline.

The reported shape (a recurrence of closed #5667 on 4.0.0rc8): a ``consolidate
--strategy merge`` FAILs reconciliation, the single rollback door restores every branch it
moved, and the target is back at ``T0`` — but the transaction record survives. The next
plain ``consolidate`` therefore *auto-resumes* it and reuses attempt 1's
``pre_mutation_target_sha`` (``T0``) as the reconciliation window base, so every commit
landed on the target between the attempts is offered to the verifier as mission content and
reported "un-attributable". Attempt 2 then FAILs for content it never authored, and its own
rollback restores the target over that content. Afterwards a plain ``--abort`` refuses too,
because the clean rollback already dropped the recorded post-mutation tips
(``rollback._clear_bookkeeping``), so the operator's commit reads as an "unrecorded move".

The invariant under test: **a transaction record survives only while some of its attempt is
still on the target.** A rollback that fully undoes its attempt clears the record, so the
next run is genuinely fresh and derives its window base from the target's current tip; a
rollback that keeps a foreign commit keeps the record, and while it survives attempt 1's
persisted base is still the honest one.

Contract-named, not issue-named: the rule these tests guard is the record's lifecycle across
consolidation attempts (see ``kitty-specs/consolidate-rerun-fresh-baseline-01M67HZD/
contracts/rollback-record-lifecycle.md``); #6770 is the report that produced it.

Red-first: every test is written against the post-fix expectation and fails on the un-fixed
tree (the attempt's baseline is still on disk, attempt 2 raises, ``--abort`` exits 1). Real git
and the real ``_run_lane_based_consolidation`` / ``spec-kitty consolidate`` entry points
throughout; the only patches are the one-shot reconciliation FAIL, the window-base spy and the
foreign-commit injection, all of which delegate to the production call.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import typer

from specify_cli.consolidation import executor, phase_claim
from specify_cli.consolidation.reconciliation import (
    Divergence,
    MergeOutcomeVerifier,
    VerifyResult,
)
from specify_cli.consolidation.state import load_state
from tests.terminus.conftest import (
    CoordMission,
    blob_present_at,
    run_terminus,
)
from tests.terminus.lanes_fixture import build_lanes_mission
from tests.terminus.rollback_harness import flat, ref_shas, state_path

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_TARGET = "develop"
_FAIL_HEADER = "Reconciliation FAILED"
_ROLLBACK_REPORT = "Rollback to the pre-consolidation snapshot"


def _consolidate(mission: CoordMission, monkeypatch: pytest.MonkeyPatch) -> None:
    """Drive the real executor in-process, exactly as ``spec-kitty consolidate`` does."""
    monkeypatch.setenv("HOME", str(mission.home))
    monkeypatch.chdir(mission.repo)
    executor._run_lane_based_consolidation(
        mission.repo,
        mission.slug,
        push=False,
        delete_branch=None,
        remove_worktree=None,
        assume_yes=True,
    )


def _one_shot_gate_fail(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Make the REAL gate FAIL exactly once, then delegate to the real verifier.

    A permanently patched verifier would make attempt 2's pass vacuous: the point of the
    repro is that attempt 2 reaches the real reconciliation path and is judged only by the
    commits that landed since the target's *current* tip.
    """
    failed = VerifyResult.failed(Divergence(missing_approved=(("WP01", "a" * 40),)))
    real_verify = MergeOutcomeVerifier.verify
    calls: list[int] = []

    def verify_once(self: MergeOutcomeVerifier, target_ref: str, claim: object) -> VerifyResult:
        calls.append(len(calls) + 1)
        if len(calls) == 1:
            return failed
        return real_verify(self, target_ref, claim)

    monkeypatch.setattr(MergeOutcomeVerifier, "verify", verify_once)
    return calls


def _commit_on_target(mission: CoordMission, name: str) -> str:
    """A commit landed on the target between attempts, made in the repository root checkout."""
    head = subprocess.run(
        ["git", "symbolic-ref", "--short", "HEAD"],
        cwd=mission.repo,
        capture_output=True,
        text=True,
        check=True,
    )
    assert head.stdout.strip() == mission.target_branch, "precondition: the root checkout is on the target"
    (mission.repo / name).write_text("operator fix between attempts\n", encoding="utf-8")
    subprocess.run(["git", "add", name], cwd=mission.repo, check=True)
    subprocess.run(["git", "commit", "-qm", f"operator: {name}"], cwd=mission.repo, check=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=mission.repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    return subprocess.run(["git", "merge-base", "--is-ancestor", ancestor, descendant], cwd=repo, check=False).returncode == 0


def _output(capsys: pytest.CaptureFixture[str]) -> str:
    captured = capsys.readouterr()
    return " ".join((captured.out + captured.err).split())


def test_a_clean_fail_rollback_rebaselines_the_record_and_the_rerun_uses_the_current_target_tip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """FR-001 + FR-002: no record survives, and attempt 2's window base is the target's live tip."""
    mission = build_lanes_mission(tmp_path, wps=("WP01", "WP02"), target_branch=_TARGET, mid8="01M6770A")
    before = ref_shas(mission)
    calls = _one_shot_gate_fail(monkeypatch)

    with pytest.raises(typer.Exit) as excinfo:
        _consolidate(mission, monkeypatch)
    assert excinfo.value.exit_code == 1
    first = _output(capsys)
    assert calls == [1], f"the gate must FAIL exactly once; calls={calls}"
    assert _FAIL_HEADER in first, f"precondition: the gate must FAIL. output={first}"
    assert _ROLLBACK_REPORT in first, f"precondition: the door must print its rollback report. output={first}"
    report = first[first.index(_ROLLBACK_REPORT) :]
    assert "NOT restored" not in report, f"precondition: this FAIL has no foreign commit, so the restore is total. report={report}"
    assert ref_shas(mission) == before, "precondition: every branch is back at its pre-run tip"

    # FR-001: nothing of attempt 1 remains to change how the next run behaves — the record
    # keeps the Mission's provenance but loses the transaction it was anchored to.
    record = load_state(mission.repo, mission.mission_id)
    assert record is not None, "the Mission's record survives a clean rollback (a resume still re-derives from it)"
    assert record.pre_mutation_target_sha is None, "the failed attempt's window base must not survive it"
    assert record.pre_mutation_refs == {}, "the failed attempt's snapshot must not survive it"
    assert record.completed_wps == [], "the failed attempt's progress must not survive it"

    # An operator commit lands on the target between the attempts (T0 -> T1).
    t1 = _commit_on_target(mission, "TEAM.md")

    # FR-002: the re-run is fresh, so its reconciliation window base is T1, not T0.
    bases: list[str | None] = []
    real_build = phase_claim.build_approved_wp_set

    def spy(*args: object, **kwargs: object) -> object:
        bases.append(kwargs.get("excluded_window_base"))  # type: ignore[arg-type]
        return real_build(*args, **kwargs)

    monkeypatch.setattr(phase_claim, "build_approved_wp_set", spy)
    _consolidate(mission, monkeypatch)  # must not raise: the commit between attempts is not mission content

    second = _output(capsys)
    assert bases and bases[-1] == t1, (
        f"the re-run's reconciliation window base must be the target's current tip {t1[:7]}; got {bases} (T0 would re-flag the operator's commit). output={second}"
    )
    assert _is_ancestor(mission.repo, t1, mission.target_branch), "the commit between attempts must stay on the target"
    for owned in ("src/pkg/wp01.py", "src/pkg/wp02.py"):
        assert blob_present_at(mission.repo, mission.target_branch, owned), f"{owned} must land on the target after the re-run"


def test_a_plain_abort_after_a_clean_fail_rollback_is_a_no_op_not_a_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """FR-003: with nothing left to undo, the documented recovery command must not refuse."""
    mission = build_lanes_mission(tmp_path, wps=("WP01", "WP02"), target_branch=_TARGET, mid8="01M6770B")
    before = ref_shas(mission)
    _one_shot_gate_fail(monkeypatch)

    with pytest.raises(typer.Exit):
        _consolidate(mission, monkeypatch)
    assert ref_shas(mission) == before, "precondition: the failed attempt was fully rolled back"
    capsys.readouterr()

    # The reported sequence: the target moves after the clean rollback (the operator's fix
    # for the first failure, a teammate's commit), and only THEN does the operator abort.
    # With the stale record still on disk this is the wedge: "moved since the snapshot but no
    # post-mutation tip was recorded", exit 1, record kept.
    _commit_on_target(mission, "after-the-failed-attempt.txt")

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--abort"])

    output = flat(result)
    assert result.returncode == 0, f"a plain --abort must not refuse once the rollback left nothing behind. output={output}"
    assert "Kept the consolidation record" not in output, f"no record may be kept after a total restore. output={output}"
    assert "Aborted" in output and "cleaned up" in output, f"the abort must report a clean finish. output={output}"
    assert state_path(mission) is None, "the abort must have cleared what was left of the record"


def test_a_partial_rollback_keeps_the_record_with_its_pre_mutation_base(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """FR-004 on the same fixture: the *kept* half, with attempt 1's window base intact.

    Same door, opposite verdict. A commit another actor lands on the target while the run is
    in flight is never restored, so the record must survive and must still carry the true
    transaction-start tip. This is the positive control for FR-001's clear: without it, a
    door that cleared unconditionally would pass every other test in this file.
    """
    mission = build_lanes_mission(tmp_path, wps=("WP01", "WP02"), target_branch=_TARGET, mid8="01M6770C")
    before = ref_shas(mission)
    original_gate = executor._phase_reconcile_before_teardown
    foreign: list[str] = []

    def gate_after_a_teammate_commit(run: executor._MergeRunState) -> None:
        foreign.append(_commit_on_target(mission, "teammate.txt"))
        original_gate(run)

    monkeypatch.setattr(executor, "_phase_reconcile_before_teardown", gate_after_a_teammate_commit)

    with pytest.raises(typer.Exit):
        _consolidate(mission, monkeypatch)

    output = _output(capsys)
    assert foreign and "NOT restored" in output, f"precondition: the foreign commit must be kept, not restored. output={output}"
    assert ref_shas(mission)["target"] == foreign[0], "the teammate's commit must stay the target tip"

    record = load_state(mission.repo, mission.mission_id)
    assert record is not None, "a partial rollback must keep the record: the un-restored commit still needs it"
    assert record.pre_mutation_target_sha == before["target"], (
        "while the record survives, attempt 1's persisted base is still the honest window base (its landing is still on the target)"
    )
