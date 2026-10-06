"""End-to-end pins for #5572 — a reviewer's later status reopen survives the strand
repair on both entry points (``doctor coordination --fix`` and ``consolidate --resume``).

A rolled-back consolidation byte-restores the coordination worktree's status files
while the coordination branch still carries the committed ``done`` strand. Before
#5572, a reviewer's reopen (``agent status emit WP01 --to in_progress --force``) built
on those stale bytes, printed OK and silently dropped the stranded ``done``; #5633 made
that write refuse with ``COORD_STATUS_SURFACE_DIVERGED``. Since #5638 the rollback
authority brings the coordination checkout back to the coordination tip it leaves in
place, so the reopen lands on top of the committed ``done`` with no hand repair, and
the strand repair leaves it alone.

Fixture (REAL failed consolidation, nothing hand-written):

1. a coordination mission with two approved WPs;
2. ``spec-kitty consolidate`` runs in a subprocess whose driver makes the target
   advance fail AFTER the pre-target ``done`` bookkeeping committed, and lets
   another actor commit an unrelated file on the coordination branch first. The
   rollback authority never restores over a commit it did not record, so the
   committed ``done`` strand stays and the writer persists the
   ``pending_coord_reconcile`` marker;
3. a REAL ``spec-kitty agent status emit WP01 --to in_progress --force`` reopens WP01.

Both entry points that share ``repair_coord_strand`` are exercised. Every refusal
asserts the coordination event log and ref are byte-identical before and after.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.terminus.conftest import CoordMission, _cli_env, build_coord_mission, git_rev, run_terminus
from tests.terminus.rollback_harness import event_log_bytes, flat, state_path

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_REOPEN_ACTOR = "reviewer-renata"
_REOPENED_WP = "WP01"
_STRANDED_WP = "WP02"
# Upstream names the foreign-commit refusal in prose (no stable code); pin its wording.
_FOREIGN_REFUSAL = "did not record"
_DIVERGED_CODE = "COORD_STATUS_SURFACE_DIVERGED"
_ENTRY_POINTS = ("doctor", "resume")

# Runs inside the consolidate subprocess: the target advance fails AFTER the pre-target
# ``done`` commit, with another actor's unrelated commit landing on the coordination
# branch first (so the rollback door cannot restore it and the marker survives).
_DRIVER = textwrap.dedent(
    """
    import os
    import subprocess
    import sys
    from pathlib import Path

    COORD_WT = Path(os.environ["REPRO_5572_COORD_WT"])


    def _foreign_commit():
        note = Path(os.environ["REPRO_5572_NOTE"])
        (COORD_WT / note).write_text("another actor\\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(COORD_WT), "add", str(note)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(COORD_WT), "commit", "-qm", "another actor"], check=True, capture_output=True)


    def _boom(*args, **kwargs):
        raise RuntimeError("injected #5572 target-advance failure")


    from specify_cli.consolidation import executor
    from specify_cli.lanes import consolidation as lane_consolidation

    lane_consolidation.integrate_mission_into_target = _boom
    _real_phase = executor._phase_mission_to_target


    def _phase_then_foreign_commit(run):
        # After the phase's own post-tip recording, so the rollback door sees a coordination
        # tip it did not record and reports the branch NOT restored (marker survives).
        try:
            _real_phase(run)
        except BaseException:
            _foreign_commit()
            raise


    executor._phase_mission_to_target = _phase_then_foreign_commit

    from specify_cli import main

    sys.argv[0] = "spec-kitty"
    main()
    """
)


@dataclass(frozen=True)
class Stranded:
    """A real failed consolidation's leftovers."""

    mission: CoordMission
    coord_worktree: Path
    captured_sha: str
    strand_tip: str


def _marker(mission: CoordMission) -> dict[str, object]:
    path = state_path(mission)
    assert path is not None, "fixture precondition: the failed consolidation must persist a state record"
    marker = json.loads(path.read_text(encoding="utf-8")).get("pending_coord_reconcile")
    assert marker, "fixture precondition: the writer must persist a pending_coord_reconcile marker"
    assert isinstance(marker, dict)
    return marker


def _failed_consolidation(tmp_path: Path) -> Stranded:
    mission = build_coord_mission(tmp_path, wps=(_REOPENED_WP, _STRANDED_WP), mid8="01M5572A")
    coord_worktree = mission.repo / ".worktrees" / f"{mission.slug}-coord"
    env = _cli_env(mission.home)
    env["REPRO_5572_COORD_WT"] = str(coord_worktree)
    env["REPRO_5572_NOTE"] = f"kitty-specs/{mission.slug}/notes-by-another-actor.md"
    result = subprocess.run(
        [sys.executable, "-c", _DRIVER, "consolidate", "--mission", mission.slug, "--yes"],
        cwd=str(mission.repo),
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    assert result.returncode != 0, f"fixture precondition: the injected failure must fail the run. output={flat(result)}"
    marker = _marker(mission)
    return Stranded(
        mission=mission,
        coord_worktree=coord_worktree,
        captured_sha=str(marker["captured_sha"]),
        strand_tip=git_rev(mission.repo, mission.coord_branch),
    )


def _emit_reopen(mission: CoordMission) -> subprocess.CompletedProcess[str]:
    """The reviewer's REAL ``agent status emit`` reopen of WP01 (no cleaning of any tree)."""
    return run_terminus(
        mission,
        [
            "agent",
            "status",
            "emit",
            _REOPENED_WP,
            "--to",
            "in_progress",
            "--actor",
            _REOPEN_ACTOR,
            "--force",
            "--reason",
            "reviewer reopen (#5572)",
            "--mission",
            mission.slug,
        ],
    )


def _reopen(stranded: Stranded) -> str:
    """REAL reviewer reopen of WP01; returns the coordination commit it landed."""
    mission = stranded.mission
    # Real path, nothing hand-cleaned: the rollback left the coordination checkout at the
    # coordination tip (#5638), so the reopen lands on the first try.
    before = git_rev(mission.repo, mission.coord_branch)
    emit = _emit_reopen(mission)
    assert emit.returncode == 0, f"fixture precondition: the reopen must succeed. output={flat(emit)}"
    after = git_rev(mission.repo, mission.coord_branch)
    assert after != before, "fixture precondition: the reopen must commit to the coordination branch"
    in_range = subprocess.run(
        ["git", "-C", str(mission.repo), "rev-list", f"{stranded.captured_sha}..{mission.coord_branch}"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    assert after in in_range, "fixture precondition: the reopen commit must sit inside captured_sha..HEAD"
    return after


def _lane(mission: CoordMission, wp_id: str) -> str:
    """Last committed lane of *wp_id* on the coordination branch (append order)."""
    lane = ""  # also the value when the coordination branch no longer exists
    for line in event_log_bytes(mission, mission.coord_branch).splitlines():
        event = json.loads(line)
        if event["wp_id"] == wp_id:
            lane = str(event["to_lane"])
    return lane


def _run_entry(mission: CoordMission, entry: str) -> subprocess.CompletedProcess[str]:
    if entry == "doctor":
        return run_terminus(mission, ["doctor", "coordination", "--fix", "--mission", mission.slug])
    return run_terminus(mission, ["consolidate", "--resume", "--mission", mission.slug, "--yes"])


def _compact(result: subprocess.CompletedProcess[str]) -> str:
    """Output with all whitespace removed (rich wraps long tokens such as SHAs)."""
    return "".join((result.stdout + result.stderr).split())


def _assert_refused(
    stranded: Stranded,
    result: subprocess.CompletedProcess[str],
    code: str,
    before: tuple[str, str],
) -> None:
    mission = stranded.mission
    out = flat(result)
    assert code in out, f"the refusal must carry {code}. output={out}"
    assert "Healed" not in out, f"a refused repair must never claim Healed. output={out}"
    assert result.returncode != 0, f"a refused repair must exit non-zero. output={out}"
    after = (event_log_bytes(mission, mission.coord_branch), git_rev(mission.repo, mission.coord_branch))
    assert after == before, "a refusal must leave the coordination event log and ref byte-identical"


def _coord_status_diff(stranded: Stranded) -> str:
    """``git status`` of the coordination worktree's status files (empty when they equal HEAD)."""
    rel = f"kitty-specs/{stranded.mission.slug}"
    return subprocess.run(
        ["git", "-C", str(stranded.coord_worktree), "status", "--porcelain", "--", f"{rel}/status.events.jsonl", f"{rel}/status.json"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def test_5638_rollback_leaves_the_coord_checkout_at_the_coord_tip(tmp_path: Path) -> None:
    """No hand-cleaning: the rollback could not restore the coordination branch (another
    actor committed on it), so it keeps the committed ``done``. The coordination checkout
    must match that tip, not the pre-``done`` bytes the bookkeeping byte-restore wrote.
    """
    stranded = _failed_consolidation(tmp_path)

    assert _coord_status_diff(stranded) == "", (
        f"the rollback left the coordination worktree's status files dirty against HEAD (#5638): {_coord_status_diff(stranded)!r}"
    )
    assert _lane(stranded.mission, _STRANDED_WP) == "done"


def test_5572_real_path_reopen_on_the_rolled_back_tree_never_drops_the_strand(tmp_path: Path) -> None:
    """No hand-cleaning: a reviewer's real ``agent status emit`` after the rollback must not
    drop the committed ``done``. Since #5638 it lands on the coordination tip, so it no longer
    needs the ``COORD_STATUS_SURFACE_DIVERGED`` refusal (the guard stays as the backstop).
    """
    stranded = _failed_consolidation(tmp_path)
    mission = stranded.mission
    assert _lane(mission, _STRANDED_WP) == "done"

    result = _emit_reopen(mission)

    out = flat(result)
    assert _DIVERGED_CODE not in out, f"the rolled-back coordination checkout must not diverge from its tip (#5638). output={out}"
    assert result.returncode == 0, f"the reopen must land. output={out}"
    assert _lane(mission, _STRANDED_WP) == "done", (
        f"the reopen silently dropped the committed `done` of {_STRANDED_WP} (now {_lane(mission, _STRANDED_WP)!r}) — output={out} (#5572)"
    )
    assert _lane(mission, _REOPENED_WP) == "in_progress"


def test_5572_reopen_survives_the_strand_repair(tmp_path: Path, entry: str = "resume") -> None:
    stranded = _failed_consolidation(tmp_path)
    mission = stranded.mission
    reopen_sha = _reopen(stranded)
    assert _lane(mission, _REOPENED_WP) == "in_progress"
    assert _lane(mission, _STRANDED_WP) == "done"
    before = (event_log_bytes(mission, mission.coord_branch), git_rev(mission.repo, mission.coord_branch))

    result = _run_entry(mission, entry)

    assert _lane(mission, _REOPENED_WP) == "in_progress", (
        f"`{entry}` reverted the reviewer's reopen of {_REOPENED_WP} (now reads {_lane(mission, _REOPENED_WP)!r}) — output={flat(result)} (#5572)"
    )
    _assert_refused(stranded, result, _FOREIGN_REFUSAL, before)
    assert reopen_sha[:10] in _compact(result), "the refusal must name the foreign reopen commit (abbreviated)"


@pytest.mark.parametrize("entry", _ENTRY_POINTS)
def test_5572_control_plain_strand_still_heals(tmp_path: Path, entry: str) -> None:
    """Same fixture minus the reopen: the recorded strand is reverted."""
    stranded = _failed_consolidation(tmp_path)
    mission = stranded.mission
    assert _lane(mission, _STRANDED_WP) == "done"

    result = _run_entry(mission, entry)

    out = flat(result)
    assert _FOREIGN_REFUSAL not in out, f"a plain strand must not be refused. output={out}"
    if entry == "doctor":
        assert result.returncode == 0, f"output={out}"
        assert "Healed" in out
        assert _lane(mission, _STRANDED_WP) == "approved"
        assert _lane(mission, _REOPENED_WP) == "approved"
    else:
        # The heal ran at resume start, then the consolidation completed (and tore the
        # coordination branch down), so the observable is a verified, successful run.
        assert result.returncode == 0, f"a plain strand must heal and let the resume finish. output={out}"
        assert "Reconciliation verified" in out
    state = state_path(mission)
    assert state is None or not json.loads(state.read_text(encoding="utf-8")).get("pending_coord_reconcile")
