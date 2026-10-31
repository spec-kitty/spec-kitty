"""The late-teardown projection carries every coordination record, or the resume refuses (#6791).

Dev-assist disposition (mission-wrap-up-sequence): kept, renamed after the CONTRACT it guards
(the late-teardown projection of a resumed consolidation) rather than after the issue that
reported it, so the file outlives #6791 as the regression suite for that contract.

`consolidate --resume` after a ``COORD_TEARDOWN_KEPT_ONLY_COPY`` refusal projects the coordination
commits that landed after the teardown gate onto the target (#5570). The projection's path selector
excluded the two gate matrices, so a verdict recorded between the refusal and the resume -- exactly
what the refusal's own instructions lead an operator to do -- was dropped with the coordination
branch and the mission landed with the row still ``in-mission``.

The end-to-end cases drive the REAL CLI through the same fixture shape as the #5965 refusal/resume
family (``tests/consolidation/test_teardown_refusal_resume.py``): a real ``move-task --to planned``
leaves an untracked review cycle in the coordination worktree, a real ``agent issue-verdict`` writes
the verdict commit, and a real ``consolidate --resume`` has to carry it.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.coordination.teardown import COORD_TEARDOWN_KEPT_ONLY_COPY_EXIT_CODE
from specify_cli.tasks.issue_matrix import IssueMatrixEntry, build_issue_matrix_document
from tests.terminus.conftest import CoordMission, blob_present_at, build_coord_mission, run_terminus

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_AGENT = "claude"
_ISSUE = "#6791"
_REVIEW_FEEDBACK = "Reviewer feedback: the retry path swallows the timeout. Fix before approval.\n"
_SUBTASKS_ANCHOR = "agent: implementer-ivan\n"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _coord_worktree(mission: CoordMission) -> Path:
    return mission.repo / ".worktrees" / f"{mission.slug}-coord"


def _matrix_path(base: Path, mission: CoordMission) -> Path:
    return base / "kitty-specs" / mission.slug / "issue-matrix.json"


def _write_matrix(base: Path, mission: CoordMission, *, verdict: str, evidence_ref: str) -> Path:
    """Seed the structured issue matrix in the SHAPE the canonical writer produces."""
    rows = {_ISSUE: IssueMatrixEntry(verdict=verdict, evidence_ref=evidence_ref, title="late projection")}
    path = _matrix_path(base, mission)
    path.write_text(json.dumps(build_issue_matrix_document(rows), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _target_verdict(mission: CoordMission) -> tuple[str, str]:
    """The verdict + evidence_ref the TARGET branch holds for the tracked issue."""
    raw = _git(mission.repo, "show", f"{mission.target_branch}:kitty-specs/{mission.slug}/issue-matrix.json")
    row = json.loads(raw)["rows"][_ISSUE]
    return row["verdict"], row["evidence_ref"]


def _declare_subtask_rosters(mission: CoordMission) -> None:
    """Give each WP file the ``subtasks`` key every production WP file carries, committed on both branches."""
    for base in (mission.repo, _coord_worktree(mission)):
        for wp_file in sorted((base / "kitty-specs" / mission.slug / "tasks").glob("WP0?-work.md")):
            wp_file.write_text(wp_file.read_text(encoding="utf-8").replace(_SUBTASKS_ANCHOR, f"{_SUBTASKS_ANCHOR}subtasks: []\n"), encoding="utf-8")
        _git(base, "add", "-A", "kitty-specs")
        _git(base, "commit", "-qm", "chore(fixture): declare empty subtask rosters")


def _seed_matrix(mission: CoordMission, *, target: tuple[str, str] = ("in-mission", "pending"), coord: tuple[str, str] = ("in-mission", "pending")) -> None:
    """Seed the matrix per surface before the run: the target's fill and the coordination copy."""
    for base, (verdict, evidence_ref) in ((mission.repo, target), (_coord_worktree(mission), coord)):
        path = _write_matrix(base, mission, verdict=verdict, evidence_ref=evidence_ref)
        _git(base, "add", str(path.relative_to(base)))
        _git(base, "commit", "-qm", "chore(fixture): seed the issue matrix")


class _RefusedRun:
    """A coordination Mission whose ``consolidate`` landed and then refused the teardown."""

    def __init__(self, mission: CoordMission, tmp_path: Path) -> None:
        self.mission = mission
        self.tmp_path = tmp_path
        self.worktree = _coord_worktree(mission)
        mission_dir = self.worktree / "kitty-specs" / mission.slug
        self.review_cycle = mission_dir / "tasks" / "WP02-work" / "review-cycle-1.md"
        self.result: subprocess.CompletedProcess[str] | None = None

    @property
    def output(self) -> str:
        assert self.result is not None
        return f"stdout:\n{self.result.stdout}\nstderr:\n{self.result.stderr}"

    def branch_exists(self) -> bool:
        probe = subprocess.run(
            ["git", "-C", str(self.mission.repo), "rev-parse", "--verify", "--quiet", f"refs/heads/{self.mission.coord_branch}"],
            capture_output=True,
            check=False,
        )
        return probe.returncode == 0

    def projection_commits(self) -> int:
        """How many late-projection commits the target received (never more than one per resume)."""
        log = _git(self.mission.repo, "log", "--format=%s", self.mission.target_branch)
        return sum(1 for line in log.splitlines() if "project coordination commits that landed during teardown" in line)

    def commit_review_cycle(self) -> None:
        """Commit A: the refusal's own instruction ("commit them on the coordination branch")."""
        _git(self.worktree, "add", str(self.review_cycle.relative_to(self.worktree)))
        _git(self.worktree, "commit", "-qm", "chore: commit review-cycle artifacts before coordination teardown")

    def record_verdict(self) -> str:
        """Commit B: the real ``agent issue-verdict`` writer, routed to the coordination surface."""
        verdict = run_terminus(
            self.mission,
            [
                "agent",
                "issue-verdict",
                "--mission",
                self.mission.slug,
                "--issue",
                _ISSUE,
                "--verdict",
                "fixed",
                "--actor",
                "tester",
                "--evidence-ref",
                "tests/consolidation/test_late_teardown_projection",
            ],
        )
        assert verdict.returncode == 0, f"fixture invalid: issue-verdict failed.\nstdout:\n{verdict.stdout}\nstderr:\n{verdict.stderr}"
        assert "committed" in verdict.stdout and self.mission.coord_branch in verdict.stdout, verdict.stdout
        return verdict.stdout

    def resume(self, *extra: str) -> subprocess.CompletedProcess[str]:
        return run_terminus(self.mission, ["consolidate", "--mission", self.mission.slug, "--resume", "--yes", *extra])


def _refuse_teardown(mission: CoordMission, tmp_path: Path) -> _RefusedRun:
    """Drive a REAL ``COORD_TEARDOWN_KEPT_ONLY_COPY`` refusal on an approved, merge-ready mission."""
    feedback_file = tmp_path / "feedback.md"
    feedback_file.write_text(_REVIEW_FEEDBACK, encoding="utf-8")
    for extra in (
        ("--to", "planned", "--review-feedback-file", str(feedback_file)),
        ("--to", "canceled", "--note", "dropped from scope"),
    ):
        moved = run_terminus(mission, ["agent", "tasks", "move-task", "WP02", *extra, "--mission", mission.slug, "--agent", _AGENT, "--no-auto-commit"])
        assert moved.returncode == 0, f"fixture invalid: move-task {extra} failed.\nstdout:\n{moved.stdout}\nstderr:\n{moved.stderr}"
    run = _RefusedRun(mission, tmp_path)
    assert run.review_cycle.is_file(), "fixture invalid: the rejection must leave the review cycle in the coordination worktree"
    run.result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])
    assert run.result.returncode == COORD_TEARDOWN_KEPT_ONLY_COPY_EXIT_CODE, run.output
    return run


@pytest.fixture
def refused_run(tmp_path: Path) -> _RefusedRun:
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8="01M6791A")
    _declare_subtask_rosters(mission)
    _seed_matrix(mission)
    return _refuse_teardown(mission, tmp_path)


def test_resume_projects_a_verdict_recorded_after_the_teardown_refusal(refused_run: _RefusedRun) -> None:
    """#6791: commit A (artifacts) and commit B (verdict) both land; the branch goes; the row is terminal."""
    run, mission = refused_run, refused_run.mission
    assert _target_verdict(mission) == ("in-mission", "pending"), "fixture invalid: the target must start with the placeholder verdict"
    run.commit_review_cycle()
    run.record_verdict()
    late_tracer = run.worktree / "kitty-specs" / mission.slug / "traces" / "late-window.md"
    late_tracer.parent.mkdir(exist_ok=True)
    late_tracer.write_text("# late window\noperator trace written after the teardown refusal.\n", encoding="utf-8")
    _git(run.worktree, "add", str(late_tracer.relative_to(run.worktree)))
    _git(run.worktree, "commit", "-qm", "chore: record a trace in the late window")

    resumed = run.resume()

    output = f"stdout:\n{resumed.stdout}\nstderr:\n{resumed.stderr}"
    assert resumed.returncode == 0, output
    assert not run.worktree.exists() and not run.branch_exists(), output
    # Commit B's content: the terminal verdict the operator recorded, not the stale placeholder.
    assert _target_verdict(mission) == ("fixed", "tests/consolidation/test_late_teardown_projection"), output
    # Commit A's content still lands alongside it (the #5570 behaviour is not traded away), and so
    # does every other coordination record the window carries.
    for path in (run.review_cycle, late_tracer):
        assert blob_present_at(mission.repo, mission.target_branch, str(path.relative_to(run.worktree))), output
    assert run.projection_commits() == 1, f"the whole window lands as ONE projection commit\n{output}"
    # And the working tree the operator is left in agrees with the landed commit.
    assert (
        _matrix_path(mission.repo, mission).read_text(encoding="utf-8")
        == _git(mission.repo, "show", f"{mission.target_branch}:kitty-specs/{mission.slug}/issue-matrix.json") + "\n"
    )


def test_resume_refuses_a_late_deletion_of_a_coordination_record(refused_run: _RefusedRun) -> None:
    """Forward-only: a projection cannot express a deletion, so it refuses instead of resurrecting or dropping it."""
    run, mission = refused_run, refused_run.mission
    matrix_rel = _matrix_path(run.worktree, mission).relative_to(run.worktree)
    _git(run.worktree, "rm", "-q", str(matrix_rel))
    _git(run.worktree, "commit", "-qm", "chore: delete the issue matrix on the coordination branch")
    before = _git(mission.repo, "show", f"{mission.target_branch}:{matrix_rel}")

    resumed = run.resume()

    output = f"stdout:\n{resumed.stdout}\nstderr:\n{resumed.stderr}"
    assert resumed.returncode != 0, output
    assert "issue-matrix.json" in " ".join((resumed.stdout + resumed.stderr).split()), output
    assert run.branch_exists() and run.worktree.is_dir(), f"the coordination branch and worktree must survive\n{output}"
    assert _git(mission.repo, "show", f"{mission.target_branch}:{matrix_rel}") == before, output


def _checkpoint_sha(mission: CoordMission) -> str:
    """The pre-mutation coordination tip the teardown projection compares against."""
    from specify_cli.consolidation.state import get_state_path

    state = json.loads(get_state_path(mission.repo, mission.mission_id).read_text(encoding="utf-8"))
    return str(state["pre_mutation_coord_sha"])


def _commit_matrix(base: Path, mission: CoordMission, *, verdict: str, evidence_ref: str, message: str) -> None:
    path = _write_matrix(base, mission, verdict=verdict, evidence_ref=evidence_ref)
    _git(base, "add", str(path.relative_to(base)))
    _git(base, "commit", "-qm", message)


def test_late_projection_never_overturns_a_terminal_verdict_the_target_holds(refused_run: _RefusedRun) -> None:
    """The projection the CLI calls refuses to overturn established evidence, and projects when it can.

    Seam-level on the SAME real refusd-teardown fixture the CLI cases use, because the target-side
    evidence has to be authored after the coordination branch was cut: the CLI refuses such a
    target move as ``UNEXPLAINED_BRANCH_MOVE`` long before the projection, which is a different
    guard with its own tests. The projection seam itself is the production function
    ``_land_late_coordination_commits`` calls, and the CLI-level case above is its positive control.
    """
    from specify_cli.consolidation.bookkeeping_projection import LateProjectionRefused, project_late_gate_matrix_commits

    run, mission = refused_run, refused_run.mission
    checkpoint = _checkpoint_sha(mission)
    matrix_rel = _matrix_path(mission.repo, mission).relative_to(mission.repo)
    assert _git(run.worktree, "rev-parse", mission.coord_branch), "fixture invalid: the coordination branch must survive"

    # -- the target holds an established judgement; the coordination copy regresses it ------
    _commit_matrix(
        mission.repo,
        mission,
        verdict="verified-already-fixed",
        evidence_ref="verified on main",
        message="chore: record the verified verdict on the target",
    )
    _commit_matrix(run.worktree, mission, verdict="in-mission", evidence_ref="regressed", message="chore: coordination copy that would overturn the verdict")
    target_bytes = (mission.repo / matrix_rel).read_bytes()

    with pytest.raises(LateProjectionRefused) as refused:
        project_late_gate_matrix_commits(main_repo=mission.repo, mission_slug=mission.slug, coord_ref=mission.coord_branch, checkpoint_sha=checkpoint)

    assert "issue-matrix.json" in str(refused.value), str(refused.value)
    assert "row #6791" in str(refused.value), str(refused.value)
    assert (mission.repo / matrix_rel).read_bytes() == target_bytes, "a refused projection must not touch the target"

    # -- positive control, same fixture: a promotion IS projected ---------------------------
    _commit_matrix(
        run.worktree,
        mission,
        verdict="fixed",
        evidence_ref="tests/consolidation/test_late_teardown_projection",
        message="chore: promote the verdict on the coordination branch",
    )

    written = project_late_gate_matrix_commits(main_repo=mission.repo, mission_slug=mission.slug, coord_ref=mission.coord_branch, checkpoint_sha=checkpoint)

    assert [path.name for path in written] == ["issue-matrix.json"], written
    assert json.loads((mission.repo / matrix_rel).read_text(encoding="utf-8"))["rows"][_ISSUE]["verdict"] == "fixed"
