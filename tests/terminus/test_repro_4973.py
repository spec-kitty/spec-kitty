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

from tests.terminus.conftest import build_coord_mission, run_terminus

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


def test_4973_strand_heal_must_not_revert_third_party_later_event(tmp_path: Path) -> None:
    from specify_cli.merge.state import MergeState, save_state

    mission = build_coord_mission(tmp_path, wps=("WP01",), mid8="01M4973A")
    coord_wt = mission.repo / ".worktrees" / f"{mission.slug}-coord"
    coord_feature = coord_wt / "kitty-specs" / mission.slug
    captured_sha = mission.rev(mission.coord_branch)

    # A stranded committed ``done`` for WP01 on the coordination branch (the state
    # an interrupted/rolled-back merge leaves — done recorded, lane not on target).
    done_event = {
        "actor": "claude",
        "at": "2026-09-24T01:00:00+00:00",
        "event_id": "01HXYZ4973DONE0000000000001",
        "evidence": None,
        "execution_mode": "worktree",
        "feature_slug": mission.slug,
        "force": False,
        "from_lane": "approved",
        "reason": None,
        "review_ref": None,
        "to_lane": "done",
        "wp_id": "WP01",
    }
    events_path = coord_feature / "status.events.jsonl"
    with events_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(done_event, sort_keys=True) + "\n")
    _git(coord_wt, "add", "-A")
    _git(coord_wt, "commit", "-qm", "stranded done WP01")

    # An INDEPENDENT third party appends a LATER commit to the coord surface.
    (coord_wt / _THIRD_PARTY_FILE).write_text("third-party later work\n", encoding="utf-8")
    _git(coord_wt, "add", "-A")
    _git(coord_wt, "commit", "-qm", "third-party later event")

    # The marker a real interrupted merge would have persisted for the resume heal.
    state = MergeState(
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
    }
    save_state(state, mission.repo)

    result = run_terminus(mission, ["merge", "--resume", "--mission", mission.slug, "--yes"])

    # Corrected invariant: the third party's later event survives the heal — either
    # it reached the target (exit 0) or it is still on the coord branch (refusal).
    survived = _blob_on_ref(mission.repo, mission.target_branch, _THIRD_PARTY_FILE) or (
        bool(mission.rev(mission.coord_branch)) and _blob_on_ref(mission.repo, mission.coord_branch, _THIRD_PARTY_FILE)
    )
    assert survived, (
        f"the strand-heal's content-blind `git revert {captured_sha[:10]}..HEAD` erased a third "
        f"party's later coord event (exit {result.returncode}); the heal must revert only the "
        f"recorded stranded SHAs (#4973)"
    )
