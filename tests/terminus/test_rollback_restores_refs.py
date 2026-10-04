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

One smoke per behaviour family (#5618 part 2): the gate-FAIL replay, the
remove-the-cause resume and the unreadable-window refusal stay end to end. The LANES
topology snapshot, the plain re-run, the gate REFUSE, the fresh projection refusal and the
earlier-verified-landing replays are pinned at the seam instead, each proven by a planted
break that turns its guard red: the mission branch missing from the snapshot candidates,
``_clear_bookkeeping`` not clearing ``completed_wps``, the single rollback door never calling
the authority, and a verified landing no longer refused. Guards:
``tests/consolidation/test_rollback_authority.py``,
``tests/consolidation/test_executor_rollback_wiring.py``,
``tests/consolidation/test_single_rollback_authority.py``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from kernel.git import GitCommandError

from specify_cli.consolidation import executor
from tests.terminus.conftest import blob_present_at, build_coord_mission, run_terminus
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
from tests.consolidation.executor_family import setattr_executor_family

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]


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


def test_after_removing_the_cause_the_resume_succeeds(tmp_path: Path) -> None:
    mission, planted, _before, _reflog_before, _result = failing_gate_run(tmp_path, "01M5318R")
    remove_carrier_cause(mission, "WP02")

    second = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--resume", "--yes"])

    assert second.returncode == 0, f"after removing the cause the resume must succeed. output={flat(second)}"
    assert blob_present_at(mission.repo, mission.target_branch, "src/pkg/wp01.py"), "WP01 approved work must be attributed on the target"
    assert blob_present_at(mission.repo, mission.target_branch, "src/pkg/wp02.py"), "WP02 approved work must be attributed on the target"
    assert not blob_present_at(mission.repo, mission.target_branch, planted), "the canceled file must never reach the target"


# --------------------------------------------------------------------------- #
# Squash-projection refusal
# --------------------------------------------------------------------------- #


def test_unreadable_projection_window_refuses_and_rolls_back_like_a_refuse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """FR-013 (git-paths-are-data WP03 fold): a failed coord-window read inside the
    squash projection proof runs AFTER the fresh PASS anchor was saved. It must take
    the same refusal + rollback path as a content-proof REFUSE — never a traceback
    that skips the rollback and leaves a PASS anchor a later ``--abort`` trusts."""
    mission = build_coord_mission(tmp_path, wps=("WP01",), mid8="01M5332C")
    before = ref_shas(mission)

    def _unreadable(main_repo: Path, *_args: object) -> list[str]:
        raise GitCommandError(argv=("diff",), cwd=main_repo, returncode=128, stderr="fatal: bad object")

    setattr_executor_family(monkeypatch, "_post_checkpoint_mission_paths", _unreadable)
    monkeypatch.setenv("HOME", str(mission.home))
    monkeypatch.chdir(mission.repo)

    with pytest.raises(executor.typer.Exit) as excinfo:
        executor._run_lane_based_consolidation(mission.repo, mission.slug, push=False, delete_branch=None, remove_worktree=None, assume_yes=True)

    assert excinfo.value.exit_code == 1
    output = " ".join(capsys.readouterr().out.split())
    assert "coordination bookkeeping window could not be read" in output, output
    after = ref_shas(mission)
    assert after["target"] == before["target"], f"target left advanced. output={output}"
    assert after["coord"] == before["coord"], f"coordination branch left advanced. output={output}"
    assert restored_pairs(output, mission.target_branch), f"the report must show the target RESTORED line. output={output}"
    bookkeeping = state_bookkeeping(mission)
    assert bookkeeping is not None
    assert bookkeeping["reconciliation_passed_target_sha"] is None, f"the refused run's own PASS anchor must not survive. {bookkeeping}"
