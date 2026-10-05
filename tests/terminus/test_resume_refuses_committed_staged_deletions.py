"""#5571 -- committing the staged deletions of an interrupted consolidate must not ship a mission without its code.

A REAL ``spec-kitty consolidate`` is SIGKILLed in the window #1826 describes: the
mission (coordination) branch ref has been advanced by the first lane merge, but
the ``git reset --hard`` that refreshes the coordination worktree never ran. The
worktree then sits behind its own HEAD and the lane's files read as STAGED
DELETIONS. The operator follows the advice the CLI used to print ("Commit ...")
with a plain ``git commit`` in the coordination worktree, which records a revert
of the lane's code on the mission branch. The ancestry skip now sees
the lane as an ancestor, so ``consolidate --resume`` used to skip it, marked every
WP ``done`` and exited 0 with the code missing.

The resumed run must refuse, mark no WP ``done`` and leave the target at the
pre-mutation snapshot. Re-pinned by rollback-anchor-authority WP03 (#5686, FR-005,
US2 AS2): the operator's commit sits on the mission branch at a tip the merge
record cannot explain (neither its restore target nor a tip a persisted advance
intent proves), so the resume now refuses earlier, before any step that could move
a branch, with ``UNEXPLAINED_BRANCH_MOVE`` naming that branch. The approved-content
presence axis (``APPROVED_CONTENT_MISSING``) stays the backstop behind it.

Nothing is mocked and no deletion is hand-written (no ``git rm``): the kill is the
shared fault hook (``tests.terminus.approved_content_support.InterruptedConsolidate``)
that SIGKILLs the ``spec-kitty`` process right after the mission-branch ref advance
and before the coordination worktree's ``reset --hard``; the staged deletions are what
that kill leaves behind. Each negative has a same-fixture positive control (the
"revert" remedy instead of "commit").
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer

from specify_cli.status.reducer import materialize_snapshot
from tests.terminus.approved_content_support import InterruptedConsolidate
from tests.terminus.conftest import CoordMission, blob_present_at
from tests.terminus.conftest import _git as git
from tests.terminus.conftest import _git_out as git_out

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

STRATEGIES = ("squash", "merge")
ERROR_CODE = "UNEXPLAINED_BRANCH_MOVE"  # re-pinned from APPROVED_CONTENT_MISSING (WP03, FR-005)
WP_PATHS = {"WP01": "src/pkg/wp01.py", "WP02": "src/pkg/wp02.py"}


#: R2: the UNEXPLAINED_BRANCH_MOVE remedies, in order (inspect, move it yourself, release with its warning).
_REMEDY_ORDER = ("git log ", "move the branch yourself", "--release-branch")
_RELEASE_WARNING = "a release keeps every commit listed above on the branch"


def _assert_remedy_order(output: str) -> None:
    positions = [output.find(marker) for marker in _REMEDY_ORDER]
    assert all(p >= 0 for p in positions) and positions == sorted(positions), f"remedies out of order {positions}. output={output}"
    assert _RELEASE_WARNING in output, f"the release remedy must warn that it keeps the commits. output={output}"


class Interrupted(InterruptedConsolidate):
    """The shared interrupted-consolidate fixture (killed at the coordination resync), plus what the operator may do next."""

    def __init__(self, tmp_path: Path, strategy: str, mid8: str) -> None:
        super().__init__(tmp_path, "kill_coord", strategy, mid8=mid8)
        self.coord_wt = self.lagging

    def operator_commits_staged_deletions(self) -> None:
        """The advice the CLI used to print: record what ``git status`` shows."""
        git(self.coord_wt, "commit", "-qm", "operator: commit the staged changes")

    def operator_reverts_staged_deletions(self) -> None:
        """The correct remedy: discard the phantom staged deletions."""
        git(self.coord_wt, "reset", "--hard", "HEAD")


def wp_lanes(mission: CoordMission, ref: str, scratch: Path) -> dict[str, str]:
    """Each WP's lane in the status log as of *ref*, reduced in a directory under *scratch* (nothing is written to the repository)."""
    events = git_out(mission.repo, "show", f"{ref}:kitty-specs/{mission.slug}/status.events.jsonl")
    feature_dir = scratch / f"snap-{mission.mid8}-{ref.replace('/', '_')}"
    feature_dir.mkdir(parents=True)
    (feature_dir / "status.events.jsonl").write_text(events, encoding="utf-8")
    snapshot = materialize_snapshot(feature_dir)
    return {wp: str(state["lane"]) for wp, state in snapshot.work_packages.items()}


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_5571_committed_staged_deletions_make_resume_refuse(tmp_path: Path, strategy: str) -> None:
    run = Interrupted(tmp_path, strategy, mid8="01M55710")
    mission = run.mission
    run.operator_commits_staged_deletions()
    assert blob_present_at(mission.repo, mission.coord_branch, WP_PATHS["WP01"]) is False, "fixture precondition: the committed deletions removed WP01's code"

    rc, flat = run.resume()

    assert rc != 0, f"resume after the operator committed the staged deletions must refuse, got exit 0 ({strategy}):\n{flat}"
    assert ERROR_CODE in flat, f"expected {ERROR_CODE} in the refusal:\n{flat}"
    assert mission.coord_branch in flat, f"the refusal must name the branch the record cannot explain:\n{flat}"
    _assert_remedy_order(flat)
    assert mission.rev(mission.target_branch) == run.pre_target, "target must be restored to the pre-mutation snapshot"
    assert not blob_present_at(mission.repo, mission.target_branch, WP_PATHS["WP01"])
    for ref in (mission.target_branch, mission.coord_branch):
        lanes = wp_lanes(mission, ref, tmp_path)
        assert "done" not in lanes.values(), f"no WP may be marked done on {ref}: {lanes}"


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_5571_control_reverting_the_staged_deletions_lands_all_code(tmp_path: Path, strategy: str) -> None:
    """Same fixture and interruption; the operator discards the staged deletions instead of committing them."""
    run = Interrupted(tmp_path, strategy, mid8="01M55711")
    mission = run.mission
    run.operator_reverts_staged_deletions()

    rc, flat = run.resume()

    assert rc == 0, f"resume after discarding the staged deletions must land the mission ({strategy}):\n{flat}"
    for wp, path in WP_PATHS.items():
        assert blob_present_at(mission.repo, mission.target_branch, path), f"{wp}'s approved code must be on the target"


def _released_then_fresh(tmp_path: Path, mid8: str, *, drop_wp01: bool) -> tuple[Interrupted, str]:
    """Kill at the coordination resync, keep the mission branch with an explicit release, then return the fresh run's fixture.

    ``drop_wp01``: the operator commits the staged deletions (WP01's code leaves the
    mission branch). Otherwise the operator discards them and the killed advance's
    intent is removed from the record, so ``--abort`` cannot restore the branch and
    the release keeps it with WP01's code intact (the positive control).
    """
    from specify_cli.consolidation.state import get_state_path
    from tests.terminus.conftest import run_terminus

    run = Interrupted(tmp_path, "squash", mid8=mid8)
    mission = run.mission
    if drop_wp01:
        run.operator_commits_staged_deletions()
    else:
        run.operator_reverts_staged_deletions()
        path = get_state_path(mission.repo, mission.mission_id)
        data = json.loads(path.read_text(encoding="utf-8"))
        data.get("advance_intents", {}).pop(mission.coord_branch, None)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    run.operator_clears_stale_locks()
    released = run_terminus(
        mission,
        ["consolidate", "--abort", "--mission", mission.slug, "--release-branch", mission.coord_branch, "--release-reason", "keep the operator commit"],
    )
    released_out = " ".join((released.stdout + released.stderr).split())
    assert released.returncode == 0, f"fixture precondition: the release clears the record:\n{released_out}"
    assert blob_present_at(mission.repo, mission.coord_branch, WP_PATHS["WP01"]) is not drop_wp01, "fixture precondition: WP01's code on the kept branch"
    return run, released_out


def _consolidate_fresh(mission: CoordMission, monkeypatch: pytest.MonkeyPatch, *, strategy: str = "squash") -> None:
    from specify_cli.consolidation import executor
    from specify_cli.consolidation.config import MergeStrategy

    monkeypatch.setenv("HOME", str(mission.home))
    monkeypatch.chdir(mission.repo)
    executor._run_lane_based_consolidation(
        mission.repo, mission.slug, push=False, delete_branch=None, remove_worktree=None, assume_yes=True, strategy=MergeStrategy(strategy)
    )


def test_5571_released_deletion_commit_reaches_the_presence_axis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """#5788: the approved-content presence axis guards end to end when the operator's commit reaches the gate through an EXPLAINED path.

    The operator commits the staged deletions, then keeps that commit with an
    explicit release (``--abort --release-branch``), which clears the record. The
    next consolidation therefore starts fresh, skips the lane whose commits are
    ancestors of the mission branch, and squashes a mission branch without WP01's
    code: the gate must FAIL with ``APPROVED_CONTENT_MISSING`` naming WP01, and the
    door must leave the target at its pre-run tip.
    """
    run, _ = _released_then_fresh(tmp_path, "01M55712", drop_wp01=True)
    mission = run.mission

    with pytest.raises(typer.Exit) as excinfo:
        _consolidate_fresh(mission, monkeypatch)

    output = " ".join(capsys.readouterr().out.split())
    assert excinfo.value.exit_code == 1, output
    assert "APPROVED_CONTENT_MISSING" in output and "WP01" in output, f"the presence axis must name the dropped WP:\n{output}"
    assert ERROR_CODE not in output, f"the explained path must reach the gate, not the unexplained-move refusal:\n{output}"
    assert mission.rev(mission.target_branch) == run.pre_target, "the door restores the target"
    assert not blob_present_at(mission.repo, mission.target_branch, WP_PATHS["WP02"]), "nothing of the failed landing stays"


def test_5571_control_a_released_branch_keeping_the_code_is_not_reported_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Same fixture, WP01's code genuinely present on the released mission branch: the presence axis stays silent.

    Residual (fail closed, reported to the orchestrator): the run still does not land.
    The authorship axes measure a lane from the mission branch tip, which already
    carries lane-a, so the squash blob axis finds WP01's file attributable to no
    approved WP and the gate FAILs; the door restores the target. Measuring
    authorship from the target's tip instead would also attribute mission-branch
    commits made outside every lane (a design decision, not taken here).
    """
    run, released_out = _released_then_fresh(tmp_path, "01M55715", drop_wp01=False)
    mission = run.mission
    assert "kept" in released_out, f"fixture precondition: the release kept the mission branch:\n{released_out}"

    with pytest.raises(typer.Exit) as excinfo:
        _consolidate_fresh(mission, monkeypatch)

    output = " ".join(capsys.readouterr().out.split())
    assert excinfo.value.exit_code == 1, output
    assert "APPROVED_CONTENT_MISSING" not in output, f"present approved content is never reported missing:\n{output}"
    assert "src/pkg/wp01.py" in output and "belongs to NO approved WP" in output, f"the residual: the blob axis refuses:\n{output}"
    assert mission.rev(mission.target_branch) == run.pre_target, "the door restores the target"


def test_5571_control_a_released_branch_keeping_the_code_is_refused_under_merge_too(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The same residual under ``--strategy merge``: the closed-world axis refuses the lane the released branch already carries.

    The authorship axes measure a lane from the mission-branch tip, which already
    holds lane-a, so lane-a's commits are reachable from the target and belong to no
    approved WP's authorship. Fail closed: the presence axis stays silent and the
    door restores the target.
    """
    run, _ = _released_then_fresh(tmp_path, "01M55716", drop_wp01=False)
    mission = run.mission

    with pytest.raises(typer.Exit) as excinfo:
        _consolidate_fresh(mission, monkeypatch, strategy="merge")

    output = " ".join(capsys.readouterr().out.split())
    assert excinfo.value.exit_code == 1, output
    assert "APPROVED_CONTENT_MISSING" not in output, f"present approved content is never reported missing:\n{output}"
    assert "content commit" in output and "belongs to NO approved WP" in output, f"the residual: the closed-world axis refuses:\n{output}"
    assert mission.rev(mission.target_branch) == run.pre_target, "the door restores the target"
