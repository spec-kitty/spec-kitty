"""A refused coordination teardown is a safe, resumable failure (#5965, FR-005a/FR-005b, D3/D4, C-005).

``consolidate`` reaches the coordination teardown AFTER the reconciliation gate passed and the
landing was verified. When the coordination worktree holds the only copy of operator files (an
uncommitted review cycle written by a real ``move-task --to planned``, a hand-written trace), the
guard refuses, and the run must:

* exit with its own code (``COORD_TEARDOWN_KEPT_ONLY_COPY``, 76), naming the kept files;
* keep the landing (the target is NOT rolled back: teardown runs after the rollback door, and the
  rollback authority would refuse a verified landing anyway);
* keep the coordination branch, worktree and marker TOGETHER (never the branch deleted while the
  worktree survives);
* finish on ``consolidate --resume`` once the operator moved the files out, or committed them inside
  ``kitty-specs/<mission>/`` (the late projection then lands them on the target).

The end-to-end cases drive the REAL CLI through the same fixture shape as the #5965 reproduction
(``tests/consolidation/test_coord_teardown_only_copy_5965.py``). The seam-level cases pin the
``--abort`` leg, the lane-role refusal and the rollback authority's refusal of a verified landing.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest
import typer

from specify_cli.consolidation.rollback import rollback_to_snapshot
from specify_cli.consolidation.state import ConsolidationState, get_state_path
from specify_cli.coordination.teardown import (
    COORD_TEARDOWN_KEPT_ONLY_COPY,
    COORD_TEARDOWN_KEPT_ONLY_COPY_EXIT_CODE,
    CoordTeardownKeptOnlyCopy,
)
from tests.terminus.conftest import CoordMission, blob_present_at, build_coord_mission, run_terminus

if TYPE_CHECKING:
    from specify_cli.consolidation.run_state import _MergeRunState

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_AGENT = "claude"
_REVIEW_FEEDBACK = "Reviewer feedback: the retry path swallows the timeout. Fix before approval.\n"
_TRACE_NOTES = "# notes\nhand-written operator trace: see WP02 rejection.\n"
_SUBTASKS_ANCHOR = "agent: implementer-ivan\n"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _coord_worktree(mission: CoordMission) -> Path:
    return mission.repo / ".worktrees" / f"{mission.slug}-coord"


def _flat(result: subprocess.CompletedProcess[str]) -> str:
    return " ".join((result.stdout + result.stderr).split())


def _declare_subtask_rosters(mission: CoordMission) -> None:
    """Give each WP file the ``subtasks`` key every production WP file carries, committed on both branches."""
    for base in (mission.repo, _coord_worktree(mission)):
        for wp_file in sorted((base / "kitty-specs" / mission.slug / "tasks").glob("WP0?-work.md")):
            wp_file.write_text(wp_file.read_text(encoding="utf-8").replace(_SUBTASKS_ANCHOR, f"{_SUBTASKS_ANCHOR}subtasks: []\n"), encoding="utf-8")
        _git(base, "add", "-A", "kitty-specs")
        _git(base, "commit", "-qm", "chore(fixture): declare empty subtask rosters")


def _move_task(mission: CoordMission, wp: str, to: str, *extra: str) -> None:
    args = ["agent", "tasks", "move-task", wp, "--to", to, "--mission", mission.slug, "--agent", _AGENT, "--no-auto-commit", *extra]
    result = run_terminus(mission, args)
    assert result.returncode == 0, f"fixture invalid: move-task {wp} --to {to} failed.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"


def _consolidate(mission: CoordMission, *extra: str) -> subprocess.CompletedProcess[str]:
    return run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes", *extra])


class _RefusedRun:
    """A coordination Mission whose ``consolidate`` landed and then refused the teardown."""

    def __init__(self, mission: CoordMission, tmp_path: Path, result: subprocess.CompletedProcess[str]) -> None:
        self.mission = mission
        self.tmp_path = tmp_path
        self.result = result
        self.worktree = _coord_worktree(mission)
        mission_dir = self.worktree / "kitty-specs" / mission.slug
        self.review_cycle = mission_dir / "tasks" / "WP02-work" / "review-cycle-1.md"
        self.traces = mission_dir / "traces" / "notes.md"
        self.review_bytes = b""

    @property
    def output(self) -> str:
        return f"stdout:\n{self.result.stdout}\nstderr:\n{self.result.stderr}"

    def branch_exists(self) -> bool:
        ref = f"refs/heads/{self.mission.coord_branch}"
        probe = subprocess.run(["git", "-C", str(self.mission.repo), "rev-parse", "--verify", "--quiet", ref], capture_output=True, check=False)
        return probe.returncode == 0


@pytest.fixture
def refused_run(tmp_path: Path) -> _RefusedRun:
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8="01M5965C")
    _declare_subtask_rosters(mission)
    feedback_file = tmp_path / "feedback.md"
    feedback_file.write_text(_REVIEW_FEEDBACK, encoding="utf-8")
    _move_task(mission, "WP02", "planned", "--review-feedback-file", str(feedback_file))
    _move_task(mission, "WP02", "canceled", "--note", "dropped from scope")
    run = _RefusedRun(mission, tmp_path, subprocess.CompletedProcess([], 0))
    assert run.review_cycle.is_file(), "fixture invalid: the rejection must leave the review cycle in the coordination worktree"
    run.traces.parent.mkdir(exist_ok=True)
    run.traces.write_text(_TRACE_NOTES, encoding="utf-8")
    run.review_bytes = run.review_cycle.read_bytes()
    run.result = _consolidate(mission)
    return run


def test_refusal_keeps_landing_and_the_whole_coordination_triple(refused_run: _RefusedRun) -> None:
    run, mission = refused_run, refused_run.mission
    output = run.output

    assert run.result.returncode == COORD_TEARDOWN_KEPT_ONLY_COPY_EXIT_CODE, output
    flat = _flat(run.result)
    assert COORD_TEARDOWN_KEPT_ONLY_COPY in flat and "review-cycle-1.md" in flat and "notes.md" in flat, output
    assert "spec-kitty consolidate --resume" in flat, output
    assert run.review_cycle.read_bytes() == run.review_bytes and run.traces.read_text(encoding="utf-8") == _TRACE_NOTES, output
    assert run.worktree.is_dir() and run.branch_exists(), f"the coordination worktree and branch must stay together\n{output}"
    # C-005: the landing stands (WP01's code reached the target) and the persisted PASS anchor names exactly the live target tip,
    # which is what makes a refused teardown derivable and makes the rollback authority refuse to undo it.
    assert blob_present_at(mission.repo, mission.target_branch, "src/pkg/wp01.py"), output
    state = json.loads(get_state_path(mission.repo, mission.mission_id).read_text(encoding="utf-8"))
    assert state["reconciliation_passed_target_sha"] == mission.rev(mission.target_branch), output


def test_resume_after_moving_the_files_out_completes_teardown(refused_run: _RefusedRun) -> None:
    run, mission = refused_run, refused_run.mission
    assert run.result.returncode == COORD_TEARDOWN_KEPT_ONLY_COPY_EXIT_CODE, run.output
    target_before = mission.rev(mission.target_branch)
    saved = run.tmp_path / "saved"
    saved.mkdir()
    shutil.move(str(run.review_cycle), saved / "review-cycle-1.md")
    shutil.move(str(run.traces), saved / "notes.md")

    resumed = _consolidate(mission, "--resume")

    output = f"stdout:\n{resumed.stdout}\nstderr:\n{resumed.stderr}"
    assert resumed.returncode == 0, output
    assert not run.worktree.exists() and not run.branch_exists(), output
    assert (saved / "review-cycle-1.md").read_bytes() == run.review_bytes
    assert mission.rev(mission.target_branch) == target_before or blob_present_at(mission.repo, mission.target_branch, "src/pkg/wp01.py"), output


def test_resume_after_committing_inside_the_mission_dir_lands_the_files(refused_run: _RefusedRun) -> None:
    """The gate re-anchors on the tip the late projection reached, so the operator's own commit is landed, not torn down."""
    run, mission = refused_run, refused_run.mission
    assert run.result.returncode == COORD_TEARDOWN_KEPT_ONLY_COPY_EXIT_CODE, run.output
    relative = [str(path.relative_to(run.worktree)) for path in (run.review_cycle, run.traces)]
    _git(run.worktree, "add", "--", *relative)
    _git(run.worktree, "commit", "-qm", "chore: keep the review feedback and the trace")

    resumed = _consolidate(mission, "--resume")

    output = f"stdout:\n{resumed.stdout}\nstderr:\n{resumed.stderr}"
    assert resumed.returncode == 0, output
    assert not run.worktree.exists() and not run.branch_exists(), output
    for path in relative:
        landed = blob_present_at(mission.repo, mission.target_branch, path)
        assert landed, f"{path} must have been landed on the target before the coordination branch was deleted\n{output}"


def test_resume_refuses_a_late_commit_outside_the_mission_dir(refused_run: _RefusedRun) -> None:
    """Late projection carries only mission-dir paths, so a commit elsewhere would die with the branch: it refuses instead."""
    run, mission = refused_run, refused_run.mission
    assert run.result.returncode == COORD_TEARDOWN_KEPT_ONLY_COPY_EXIT_CODE, run.output
    for path in (run.review_cycle, run.traces):
        path.unlink()
    stray = run.worktree / "operator-scratch.txt"
    stray.write_text("only copy of an operator file, committed outside the Mission directory\n", encoding="utf-8")
    _git(run.worktree, "add", "operator-scratch.txt")
    _git(run.worktree, "commit", "-qm", "chore: operator scratch")
    kept_tip = _git(run.mission.repo, "rev-parse", mission.coord_branch)

    resumed = _consolidate(mission, "--resume")

    output = f"stdout:\n{resumed.stdout}\nstderr:\n{resumed.stderr}"
    assert resumed.returncode != 0, output
    assert "operator-scratch.txt" in _flat(resumed), output
    assert run.branch_exists() and _git(mission.repo, "rev-parse", mission.coord_branch) == kept_tip, f"the commit must survive\n{output}"
    assert run.worktree.is_dir(), output


# -- seam-level cases ---------------------------------------------------------------------------


@pytest.fixture
def idle_coord_mission(tmp_path: Path) -> CoordMission:
    return build_coord_mission(tmp_path, wps=("WP01",), mid8="01M5965D")


def test_abort_teardown_with_only_copy_files_refuses_and_names_the_abort_remedy(idle_coord_mission: CoordMission) -> None:
    """``consolidate --abort`` reaches the same teardown seam, so it gets the refusal with its own follow-up command."""
    from specify_cli.cli.commands.consolidate import _teardown_coordination_for_abort

    mission = idle_coord_mission
    worktree = _coord_worktree(mission)
    kept = worktree / "kitty-specs" / mission.slug / "traces" / "notes.md"
    kept.parent.mkdir(exist_ok=True)
    kept.write_text(_TRACE_NOTES, encoding="utf-8")
    state = ConsolidationState(mission_id=mission.mission_id, mission_slug=mission.slug, target_branch=mission.target_branch, wp_order=[])

    with pytest.raises(typer.Exit) as exit_info:
        _teardown_coordination_for_abort(mission.repo, mission.slug, (mission.mission_id, state))

    assert exit_info.value.exit_code == COORD_TEARDOWN_KEPT_ONLY_COPY_EXIT_CODE
    assert kept.read_text(encoding="utf-8") == _TRACE_NOTES and worktree.is_dir()


def test_abort_teardown_without_only_copy_files_removes_the_worktree(idle_coord_mission: CoordMission) -> None:
    from specify_cli.cli.commands.consolidate import _teardown_coordination_for_abort

    mission = idle_coord_mission
    state = ConsolidationState(mission_id=mission.mission_id, mission_slug=mission.slug, target_branch=mission.target_branch, wp_order=[])

    _teardown_coordination_for_abort(mission.repo, mission.slug, (mission.mission_id, state))

    assert not _coord_worktree(mission).exists()


def test_kept_only_copy_message_lists_at_most_twenty_files_then_a_count() -> None:
    files = [f"?? kitty-specs/m/traces/note-{index:02d}.md" for index in range(25)]

    message = str(CoordTeardownKeptOnlyCopy(worktree_path=Path("/wt"), kept_files=files, follow_up_command="spec-kitty consolidate --abort"))

    assert "note-19.md" in message and "note-20.md" not in message
    assert "... and 5 more" in message
    assert "spec-kitty consolidate --abort" in message and COORD_TEARDOWN_KEPT_ONLY_COPY in message


def test_rollback_authority_refuses_to_undo_a_verified_landing(idle_coord_mission: CoordMission) -> None:
    """C-005 pin: a teardown refusal never reaches the rollback door, and if it did the verified landing is kept."""
    mission = idle_coord_mission
    target_tip = mission.rev(mission.target_branch)
    state = ConsolidationState(
        mission_id=mission.mission_id,
        mission_slug=mission.slug,
        target_branch=mission.target_branch,
        wp_order=[],
        pre_mutation_refs={mission.target_branch: target_tip},
        reconciliation_passed_target_sha=target_tip,
    )

    report = rollback_to_snapshot(mission.repo, state, target_branch=mission.target_branch)

    assert report.refused_verified_landing
    assert mission.rev(mission.target_branch) == target_tip


# -- lane leg -------------------------------------------------------------------------------------


def _lane_cleanup_run(mission: CoordMission) -> _MergeRunState:
    """The slice of ``_MergeRunState`` that ``_remove_lane_worktrees`` reads, over a real LANES Mission."""
    from types import SimpleNamespace

    from specify_cli.lanes.persistence import require_lanes_json

    return cast(
        "_MergeRunState",
        SimpleNamespace(
            main_repo=mission.repo,
            mission_slug=mission.slug,
            target_feature_dir=mission.feature_dir,
            lanes_manifest=require_lanes_json(mission.feature_dir),
        ),
    )


def _lane_worktrees(mission: CoordMission) -> list[Path]:
    return sorted((mission.repo / ".worktrees").glob(f"{mission.slug}-lane-*"))


def _materialize_lane_worktree(mission: CoordMission, lane_id: str = "lane-a") -> Path:
    """Check the lane branch out at the placement authority's predicted path (the fixture only cuts the branch)."""
    from specify_cli.lanes.worktree_allocator import predict_lane_worktree

    path, branch = predict_lane_worktree(mission.repo, mission.slug, lane_id)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    _git(mission.repo, "worktree", "add", str(path), branch)
    return Path(path)


def test_lane_worktree_with_uncommitted_rework_refuses_before_the_coordination_teardown(tmp_path: Path) -> None:
    """The lane leg runs BEFORE the coordination teardown, so it judges a lane checkout by the LANE role (spec edge case)."""
    from specify_cli.consolidation.phase_teardown import _remove_lane_worktrees
    from specify_cli.git.destructive_guard import DestructiveOpRefused
    from tests.terminus.lanes_fixture import build_lanes_mission

    mission = build_lanes_mission(tmp_path, wps=("WP01",), target_branch="develop", mid8="01M5965E")
    lane = _materialize_lane_worktree(mission)
    rework = lane / "kitty-specs" / mission.slug / "traces" / "notes.md"
    rework.parent.mkdir(parents=True, exist_ok=True)
    rework.write_text(_TRACE_NOTES, encoding="utf-8")

    with pytest.raises(DestructiveOpRefused) as refused:
        _remove_lane_worktrees(_lane_cleanup_run(mission))

    assert "notes.md" in str(refused.value)
    assert rework.read_text(encoding="utf-8") == _TRACE_NOTES and lane.is_dir()


def test_clean_lane_worktree_is_removed(tmp_path: Path) -> None:
    from specify_cli.consolidation.phase_teardown import _remove_lane_worktrees
    from tests.terminus.lanes_fixture import build_lanes_mission

    mission = build_lanes_mission(tmp_path, wps=("WP01",), target_branch="develop", mid8="01M5965F")
    _materialize_lane_worktree(mission)
    assert _lane_worktrees(mission)

    _remove_lane_worktrees(_lane_cleanup_run(mission))

    assert not _lane_worktrees(mission)
