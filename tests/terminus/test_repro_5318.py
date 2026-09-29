"""Repro #5318 (coordination topology) -- a gate FAIL must roll back EVERY branch.

Pre-fix, a reconciliation-gate FAIL restored only the TARGET branch
(``_rollback_target_after_failed_reconciliation``). The coordination branch kept
the lane merge, the mission-number bake, the ``done`` events and the seed
commits, and ``state.json`` still claimed ``mission_number_baked`` /
``completed_wps``; a later ``--resume`` or fresh run therefore saw an empty
authored range and false-FAILed or double-applied work.

Contract (FR-004/FR-006, ``contracts/rollback-authority.md``): after the gate
FAIL the target AND the coordination branch are back at their pre-run SHAs, the
lane branches are untouched, the persisted claim bookkeeping is cleared, and
after removing the cause a ``--resume`` (or a plain re-run) succeeds with the
approved work attributed on the target.

Driven through the REAL ``spec-kitty consolidate`` CLI over real git, asserting
real ``git rev-parse`` SHAs and ``state.json`` bytes (NFR-004, nothing mocked).
Vacuous-oracle guard (#5344 class): today's code already restores the TARGET, so
the load-bearing assertions are the coordination-branch and state ones, plus the
reflog proof that the coordination branch really moved during the run and was
moved BACK by the restore.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from tests.terminus.conftest import (
    CoordMission,
    blob_present_at,
    build_coord_mission,
    plant_canceled_commit,
    run_terminus,
)
from tests.terminus.conftest import _git as git

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]


def state_bookkeeping(mission: CoordMission) -> dict[str, object] | None:
    found = sorted((mission.repo / ".kittify" / "runtime" / "merge").glob("*/state.json"))
    if not found:
        return None
    payload = json.loads(found[0].read_text(encoding="utf-8"))
    return {key: payload.get(key) for key in ("mission_number_baked", "completed_wps", "reconciliation_passed_target_sha")}


def rev_or_gone(mission: CoordMission, ref: str) -> str:
    proc = subprocess.run(["git", "rev-parse", "--verify", "-q", ref], cwd=mission.repo, capture_output=True, text=True, check=False)
    return proc.stdout.strip() or "<gone>"


def ref_shas(mission: CoordMission) -> dict[str, str]:
    """Real SHAs of the target, coordination/mission branch and every lane branch."""
    shas = {"target": rev_or_gone(mission, mission.target_branch), "coord": rev_or_gone(mission, mission.coord_branch)}
    for wp, branch in sorted(mission.lane_branches.items()):
        shas[f"lane:{wp}"] = rev_or_gone(mission, branch)
    return shas


def reflog_shas(mission: CoordMission, branch: str) -> list[str]:
    """Reflog SHAs of ``refs/heads/<branch>``, newest first."""
    proc = subprocess.run(
        ["git", "reflog", "show", "--format=%H", f"refs/heads/{branch}"],
        cwd=mission.repo,
        capture_output=True,
        text=True,
        check=False,
    )
    return [line for line in proc.stdout.split() if line]


def flat(result: subprocess.CompletedProcess[str]) -> str:
    """stdout+stderr with rich's line wrapping collapsed."""
    return " ".join((result.stdout + result.stderr).split())


def restored_pairs(output: str, branch: str) -> list[tuple[str, str]]:
    """``(post, pre)`` short-SHA pairs of every ``restored <branch> <post> -> <pre>`` report line."""
    pattern = rf"restored\s+{re.escape(branch)}\s+([0-9a-f]{{7}}) -> ([0-9a-f]{{7}})"
    return re.findall(pattern, output)


_REPORT_HEADER = "Rollback to the pre-consolidation snapshot:"


def assert_report_is_truthful(output: str) -> None:
    """The appended rollback report exists and never claims that nothing was mutated (FR-009).

    Scoped to the report, the FR-009 surface this mission owns. The gate's own
    guidance line (``MergeOutcomeVerifier.recovery_guidance``) was already made
    truthful on this branch (0523585e): it describes the restore as in progress and
    defers to this report, and is pinned separately in
    ``tests/consolidation/test_reconciliation.py``.
    """
    assert _REPORT_HEADER in output, f"the rollback report must follow the refusal guidance. output={output}"
    report = output[output.index(_REPORT_HEADER) :]
    assert "no refs/worktrees were mutated" not in report, f"FR-009: the report must not claim nothing was mutated. report={report}"


def remove_carrier_cause(mission: CoordMission, carrier_wp: str) -> None:
    """Drop the planted canceled merge from the carrier lane (its first parent is the original tip)."""
    branch = mission.lane_branches[carrier_wp]
    first_parent = git(mission.repo, "rev-parse", f"{branch}^1").stdout.strip()
    git(mission.repo, "update-ref", f"refs/heads/{branch}", first_parent)


def _failing_run(tmp_path: Path, mid8: str) -> tuple[CoordMission, str, dict[str, str], int, subprocess.CompletedProcess[str]]:
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8=mid8)
    _, _, planted = plant_canceled_commit(mission, canceled_wp="WP03", carrier_wp="WP02")
    before = ref_shas(mission)
    reflog_before = len(reflog_shas(mission, mission.coord_branch))
    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])
    assert result.returncode != 0, f"fixture precondition: the run must gate-FAIL. output={flat(result)}"
    return mission, planted, before, reflog_before, result


def test_5318_gate_fail_restores_target_and_coordination_branch(tmp_path: Path) -> None:
    mission, planted, before, reflog_before, result = _failing_run(tmp_path, "01M5318A")
    output = flat(result)
    after = ref_shas(mission)

    assert not blob_present_at(mission.repo, mission.target_branch, planted), f"the canceled file reached the target. output={output}"
    assert after["target"] == before["target"], f"#5318: target not restored ({before['target']} -> {after['target']}). output={output}"
    assert after["coord"] == before["coord"], f"#5318: coordination branch left advanced ({before['coord']} -> {after['coord']}). output={output}"
    lanes = {k: v for k, v in after.items() if k.startswith("lane:")}
    assert lanes == {k: v for k, v in before.items() if k.startswith("lane:")}, "#5318: a lane branch moved"

    bookkeeping = state_bookkeeping(mission)
    assert bookkeeping is not None, "a failed run must leave a resumable state.json"
    assert bookkeeping["mission_number_baked"] is False, f"#5318: state still claims the bake: {bookkeeping}"
    assert bookkeeping["completed_wps"] == [], f"#5318: state still claims completed WPs: {bookkeeping}"

    # Vacuous-oracle guard: the branch really moved during the run, and the NEWEST reflog entry is the restore.
    reflog = reflog_shas(mission, mission.coord_branch)
    assert len(reflog) - reflog_before >= 2, f"the coordination branch must have advanced AND been restored during the run; reflog={reflog}"
    assert reflog[0] == before["coord"], f"#5318: newest reflog entry is not the pre-run SHA; reflog={reflog}"
    assert len(set(reflog[: len(reflog) - reflog_before])) >= 2, "vacuous oracle: the coordination branch never left its pre-run SHA"

    pairs = restored_pairs(output, mission.coord_branch)
    assert pairs, f"#5318: the report must name the coordination-branch restore. output={output}"
    post, pre = pairs[0]
    assert post != pre and pre == before["coord"][:7], f"restore line must go post->pre-run SHA: {pairs}"
    assert_report_is_truthful(output)
    assert re.search(rf"unchanged\s+{re.escape(mission.target_branch)}\s+\(already at {before['target'][:7]}\)", output), (
        f"the report must show the target's idempotent 'unchanged (already at <pre>)' line. output={output}"
    )


@pytest.mark.parametrize("resume", [True, False], ids=["resume", "plain-rerun"])
def test_5318_after_removing_the_cause_the_next_run_succeeds(tmp_path: Path, resume: bool) -> None:
    mission, planted, _before, _reflog_before, _result = _failing_run(tmp_path, "01M5318R" if resume else "01M5318P")
    remove_carrier_cause(mission, "WP02")

    args = ["consolidate", "--mission", mission.slug, *(["--resume"] if resume else []), "--yes"]
    second = run_terminus(mission, args)

    assert second.returncode == 0, f"#5318: after removing the cause the next run must succeed. output={flat(second)}"
    assert blob_present_at(mission.repo, mission.target_branch, "src/pkg/wp01.py"), "WP01 approved work must be attributed on the target"
    assert blob_present_at(mission.repo, mission.target_branch, "src/pkg/wp02.py"), "WP02 approved work must be attributed on the target"
    assert not blob_present_at(mission.repo, mission.target_branch, planted), "the canceled file must never reach the target"
