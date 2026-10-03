"""Repro #4973 — the coord strand-heal reverts a RANGE, erasing a third party's
later event on the append-only status log.

Mechanism (DEBRIEF §4, root R3 / S-B): when a merge strands a committed coord
``done`` and leaves a ``pending_coord_reconcile`` marker, the next
``merge --resume`` heals via ``repair_coord_strand`` — a forward
``git revert captured_sha..HEAD`` over the coordination branch. That range is
content-blind: if an independent third party appended a LATER commit to the coord
surface after the captured checkpoint, the revert erases it too, so the later
event never reaches the target. The heal must revert ONLY the recorded (stranded)
SHAs, never a third party's later event. Backstopped by a SHA-scoped revert (S-B,
WP06/WP07).

#5572 re-pin: the original third-party commit below does NOT touch the status log, so on its
own it could never fail the heal for a status-log reason (a vacuous false green). The marker
now records the strand's own SHA (``strand_shas``, as the production writer does), and a second
case plants a REAL status-log commit (a reviewer reopen through the production status shell)
after the stranded ``done``: the heal must refuse and the reopen must survive.

RED-first: driven through the REAL ``spec-kitty merge --resume`` CLI (no
``_run_git`` / subprocess mocking). The ``pending_coord_reconcile`` marker + a
committed stranded ``done`` reproduce exactly the on-disk state a real interrupted
merge leaves; ``doctor coordination --fix`` does NOT drive this heal (it is wired
only into ``merge/executor``), so the resume path is used. Today the third party's
later commit does not survive to the target → the "survives" assertion fails →
``xfail(strict=True)``.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.coordination.status_transition import emit_status_transition_transactional
from specify_cli.status.models import TransitionRequest
from tests.terminus.conftest import CoordMission, build_coord_mission, run_terminus

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_THIRD_PARTY_FILE = "THIRD_PARTY.txt"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True)


def _blob_on_ref(repo: Path, ref: str, path: str) -> bool:
    return (
        subprocess.run(
            ["git", "-C", str(repo), "cat-file", "-e", f"{ref}:{path}"],
            capture_output=True,
            text=True,
            check=False,
        ).returncode
        == 0
    )


def _strand_done(mission: CoordMission, wp_id: str) -> str:
    """Strand ``wp_id``'s ``done`` as a REAL status commit on the coord branch; return its SHA.

    Emitted through the production coordination status shell so its timestamp orders after the
    fixture's ``approved`` events. A hand-written event dated before them reduces to
    ``approved`` (observed in the two-WP case), so its "strand" is a no-op the heal never sees (#5572).
    """
    request = TransitionRequest(
        feature_dir=mission.feature_dir,
        mission_slug=mission.slug,
        wp_id=wp_id,
        to_lane="done",
        actor="spec-kitty-merge",
        repo_root=mission.repo,
        evidence={"review": {"reviewer": "reviewer-renata", "verdict": "approved", "reference": "review-approve-4973"}},
    )
    emit_status_transition_transactional(request)
    return mission.rev(mission.coord_branch)


def test_4973_strand_heal_must_not_revert_third_party_later_event(tmp_path: Path) -> None:
    from specify_cli.consolidation.state import ConsolidationState, save_state

    mission = build_coord_mission(tmp_path, wps=("WP01",), mid8="01M4973A")
    coord_wt = mission.repo / ".worktrees" / f"{mission.slug}-coord"
    captured_sha = mission.rev(mission.coord_branch)

    # A stranded committed ``done`` for WP01 on the coordination branch (the state
    # an interrupted/rolled-back merge leaves — done recorded, lane not on target).
    strand_sha = _strand_done(mission, "WP01")

    # An INDEPENDENT third party appends a LATER commit to the coord surface.
    (coord_wt / _THIRD_PARTY_FILE).write_text("third-party later work\n", encoding="utf-8")
    _git(coord_wt, "add", "-A")
    _git(coord_wt, "commit", "-qm", "third-party later event")

    # The marker a real interrupted merge would have persisted for the resume heal.
    state = ConsolidationState(
        mission_id=mission.mission_id,
        mission_slug=mission.slug,
        target_branch=mission.target_branch,
        wp_order=["WP01"],
    )
    state.current_wp = "WP01"
    state.pending_coord_reconcile = {
        "coord_ref": mission.coord_branch,
        "captured_sha": captured_sha,
        "coord_worktree": str(coord_wt),
        "stranded_wp_ids": ["WP01"],
        "revert_error": None,
        "detected_at": "2026-09-24T01:00:00+00:00",
        "strand_shas": [strand_sha],
    }
    save_state(state, mission.repo)

    result = run_terminus(mission, ["consolidate", "--resume", "--mission", mission.slug, "--yes"])

    # Corrected invariant: the third party's later event survives the heal — either
    # it reached the target (exit 0) or it is still on the coord branch (refusal).
    survived = _blob_on_ref(mission.repo, mission.target_branch, _THIRD_PARTY_FILE) or (
        bool(mission.rev(mission.coord_branch)) and _blob_on_ref(mission.repo, mission.coord_branch, _THIRD_PARTY_FILE)
    )
    # The heal really ran (the strand was live, recorded and the range held no foreign status
    # commit): the stranded ``done`` is reverted, so the survival above is not vacuous (#5572).
    rel = f"kitty-specs/{mission.slug}/status.events.jsonl"
    raw = _git(mission.repo, "show", f"{mission.coord_branch}:{rel}").stdout
    wp01 = [json.loads(line) for line in raw.splitlines() if line.strip() and json.loads(line)["wp_id"] == "WP01"]
    assert wp01[-1]["to_lane"] != "done", "the recorded stranded done must have been reverted by the heal"
    assert survived, (
        f"the strand-heal's content-blind `git revert {captured_sha[:10]}..HEAD` erased a third "
        f"party's later coord event (exit {result.returncode}); the heal must revert only the "
        f"recorded stranded SHAs (#4973)"
    )


def test_4973_resume_heal_refuses_a_real_status_commit_after_the_strand(tmp_path: Path) -> None:
    """A reviewer's rework cycle is REAL status-log commits: ``--resume`` must not revert them (#5572)."""
    from specify_cli.consolidation.state import ConsolidationState, save_state
    from specify_cli.status.models import ReviewResult
    from tests.terminus.mixed_lane_support import ensure_wp01_subtasks_roster, transition

    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8="01M4973B")
    ensure_wp01_subtasks_roster(mission)
    coord_wt = mission.repo / ".worktrees" / f"{mission.slug}-coord"
    captured_sha = mission.rev(mission.coord_branch)

    strand_sha = _strand_done(mission, "WP02")

    # WP01's rework cycle after the strand: reopen, then re-approve — real status commits
    # through the production shell, so the mission is merge-ready again and the heal runs.
    actor = "reviewer-renata"
    transition(mission, "WP01", "in_progress", actor=actor, review_ref="review-reopen-4973")
    transition(mission, "WP01", "for_review", actor=actor, subtasks_complete=True)
    transition(mission, "WP01", "in_review", actor=actor)
    transition(
        mission,
        "WP01",
        "approved",
        actor=actor,
        review_result=ReviewResult(reviewer=actor, verdict="approved", reference="review-reopen-4973"),
    )

    state = ConsolidationState(
        mission_id=mission.mission_id,
        mission_slug=mission.slug,
        target_branch=mission.target_branch,
        wp_order=["WP01", "WP02"],
    )
    state.current_wp = "WP02"
    state.pending_coord_reconcile = {
        "coord_ref": mission.coord_branch,
        "captured_sha": captured_sha,
        "coord_worktree": str(coord_wt),
        "stranded_wp_ids": ["WP02"],
        "revert_error": None,
        "detected_at": "2026-09-24T01:00:00+00:00",
        "strand_shas": [strand_sha],
    }
    save_state(state, mission.repo)

    result = run_terminus(mission, ["consolidate", "--resume", "--mission", mission.slug, "--yes"])

    flat = " ".join((result.stdout + result.stderr).split())
    assert "NOT reverted" in flat, f"the resume must say the stranded done was not reverted (exit {result.returncode}):\n{flat}"
    # No heal ran: the rework cycle's commits are still all in the coord history.
    rel = f"kitty-specs/{mission.slug}/status.events.jsonl"
    raw = _git(mission.repo, "show", f"{mission.coord_branch}:{rel}").stdout
    wp01 = [json.loads(line) for line in raw.splitlines() if line.strip() and json.loads(line)["wp_id"] == "WP01"]
    assert [e["to_lane"] for e in wp01[-4:]] == ["in_progress", "for_review", "in_review", "approved"], (
        f"the resume heal erased WP01's rework cycle (exit {result.returncode}):\n{flat}"
    )
