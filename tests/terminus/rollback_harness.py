"""Shared helpers for the consolidation rollback end-to-end tests.

Real git, real ``spec-kitty consolidate`` CLI, nothing mocked. Used by
``test_rollback_restores_refs.py``, ``test_abort_restores_snapshot.py`` and
``test_claim_refusal_before_mutation.py``.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from tests.terminus.conftest import CoordMission, build_coord_mission, plant_canceled_commit, run_terminus
from tests.terminus.conftest import _git as git

_REPORT_HEADER = "Rollback to the pre-consolidation snapshot:"


def state_path(mission: CoordMission) -> Path | None:
    """The mission's persisted consolidation ``state.json``, or ``None`` when no record exists."""
    found = sorted((mission.repo / ".kittify" / "runtime" / "merge").glob("*/state.json"))
    return found[0] if found else None


def state_bookkeeping(mission: CoordMission) -> dict[str, object] | None:
    path = state_path(mission)
    if path is None:
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
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


def event_log_bytes(mission: CoordMission, ref: str) -> str:
    proc = subprocess.run(
        ["git", "show", f"{ref}:kitty-specs/{mission.slug}/status.events.jsonl"],
        cwd=mission.repo,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout


def full_snapshot(mission: CoordMission) -> dict[str, object]:
    """Real SHAs + bookkeeping + event-log bytes for every ref the run may move."""
    bookkeeping = state_bookkeeping(mission)
    return {
        "target": rev_or_gone(mission, mission.target_branch),
        "coord": rev_or_gone(mission, mission.coord_branch),
        "lanes": {wp: rev_or_gone(mission, branch) for wp, branch in sorted(mission.lane_branches.items())},
        "state": None if bookkeeping is None else {k: bookkeeping[k] for k in ("mission_number_baked", "completed_wps")},
        "target_events": event_log_bytes(mission, mission.target_branch),
        "coord_events": event_log_bytes(mission, mission.coord_branch),
    }


def delete_lane_branch(mission: CoordMission, wp_id: str) -> None:
    git(mission.repo, "branch", "-D", mission.lane_branches[wp_id])


def flat(result: subprocess.CompletedProcess[str]) -> str:
    """stdout+stderr with rich's line wrapping collapsed."""
    return " ".join((result.stdout + result.stderr).split())


def restored_pairs(output: str, branch: str) -> list[tuple[str, str]]:
    """``(post, pre)`` short-SHA pairs of every ``restored <branch> <post> -> <pre>`` report line."""
    pattern = rf"restored\s+{re.escape(branch)}\s+([0-9a-f]{{7}}) -> ([0-9a-f]{{7}})"
    return re.findall(pattern, output)


def assert_report_is_truthful(output: str) -> None:
    """The appended rollback report exists and never claims that nothing was mutated (FR-009).

    The gate's own guidance line (``MergeOutcomeVerifier.recovery_guidance``) is
    pinned separately in ``tests/consolidation/test_reconciliation.py``.
    """
    assert _REPORT_HEADER in output, f"the rollback report must follow the refusal guidance. output={output}"
    report = output[output.index(_REPORT_HEADER) :]
    assert "no refs/worktrees were mutated" not in report, f"FR-009: the report must not claim nothing was mutated. report={report}"


def remove_carrier_cause(mission: CoordMission, carrier_wp: str) -> None:
    """Drop the planted canceled merge from the carrier lane (its first parent is the original tip)."""
    branch = mission.lane_branches[carrier_wp]
    first_parent = git(mission.repo, "rev-parse", f"{branch}^1").stdout.strip()
    git(mission.repo, "update-ref", f"refs/heads/{branch}", first_parent)


def failing_gate_run(tmp_path: Path, mid8: str) -> tuple[CoordMission, str, dict[str, str], int, subprocess.CompletedProcess[str]]:
    """Coordination mission whose carrier lane holds a canceled WP's commit: the fresh run gate-FAILs."""
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8=mid8)
    _, _, planted = plant_canceled_commit(mission, canceled_wp="WP03", carrier_wp="WP02")
    before = ref_shas(mission)
    reflog_before = len(reflog_shas(mission, mission.coord_branch))
    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])
    assert result.returncode != 0, f"fixture precondition: the run must gate-FAIL. output={flat(result)}"
    return mission, planted, before, reflog_before, result
