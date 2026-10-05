"""Red-first reproductions of two open P0 rollback-anchor bugs (#5686, #5666).

Both are intentional red-first P0 reproductions (ADR 2026-07-17-1): they fail
on ``main`` because of the product defect and are held out of every run except
the nightly ``p0-repro`` lane by the ``p0_repro`` marker. The fix PR removes
the marker, which turns each into an ordinary per-PR guard.

Shared root cause: the consolidation rollback anchors on a tip it did not
record for this run. Real temp git repos, no git mocking.

* #5686 -- ``consolidate`` is killed after the squash landed on the target but
  before the phase recorder ran. The first ``--abort`` correctly refuses
  (``NOT_RESTORED``, unrecorded move). The re-run's claim then calls
  :func:`begin_attempt`, which adopts the unrecorded landing as the target's
  restore target, so the second ``--abort`` reports ``ALREADY_AT_SNAPSHOT``,
  counts as a full restore and clears the record while the target still holds
  the never-reconciled squash.
* #5666 -- a commit lands on the target from elsewhere while ``consolidate``
  runs, after this run's squash. The reconciliation FAIL path
  (:func:`_rollback_target_after_failed_reconciliation`) resets the target to
  the pre-mutation tip with a compare-and-swap whose expected value is the tip
  it just read, so the concurrent commit is discarded from the target.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.consolidation.config import MergeStrategy
from specify_cli.consolidation.executor import _MergeRunState
from specify_cli.consolidation.phase_gate import _rollback_target_after_failed_reconciliation
from specify_cli.consolidation.rollback import (
    BranchOutcomeKind,
    begin_attempt,
    capture_pre_mutation_snapshot,
    rollback_to_snapshot,
)
from specify_cli.consolidation.state import ConsolidationState
from specify_cli.lanes.models import ExecutionLane, LanesManifest

pytestmark = [pytest.mark.git_repo, pytest.mark.fast]

_SLUG = "m-01ABCDEF"
_MISSION_ID = "01ABCDEF" + "0" * 18
_MISSION_BRANCH = f"kitty/mission-{_SLUG}"
_TARGET = "main"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


def _rev(repo: Path, branch: str) -> str:
    return _git(repo, "rev-parse", f"refs/heads/{branch}")


def _commit(repo: Path, name: str) -> str:
    """Commit a new file on the checked-out branch (the target)."""
    (repo / f"{name}.txt").write_text(f"{name}\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", name)
    return _git(repo, "rev-parse", "HEAD")


def _is_ancestor(repo: Path, commit: str, branch: str) -> bool:
    result = subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", commit, f"refs/heads/{branch}"], check=False)
    return result.returncode == 0


def _manifest() -> LanesManifest:
    lane = ExecutionLane(lane_id="lane-a", wp_ids=("WP01",), write_scope=(), predicted_surfaces=(), depends_on_lanes=(), parallel_group=0)
    return LanesManifest(
        version=1,
        mission_slug=_SLUG,
        mission_id=_MISSION_ID,
        mission_branch=_MISSION_BRANCH,
        target_branch=_TARGET,
        lanes=[lane],
        computed_at="2026-01-01T00:00:00+00:00",
        computed_from="test",
    )


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-qb", _TARGET, str(repo)], check=True)
    for key, value in (("user.email", "t@t.com"), ("user.name", "T"), ("commit.gpgsign", "false")):
        _git(repo, "config", key, value)
    (repo / ".gitignore").write_text(".kittify/runtime/\n", encoding="utf-8")  # merge state is never tracked
    _commit(repo, "base")
    _git(repo, "branch", _MISSION_BRANCH)
    return repo


@pytest.mark.p0_repro(issue=5686)
def test_second_abort_never_reports_restored_over_an_unrecorded_landing(tmp_path: Path) -> None:
    """A second ``--abort`` must not report a full restore while the target keeps an unverified landing.

    Intentional red-first P0 reproduction of #5686. Sequence, through the
    rollback authority's public entry points in the order consolidate calls
    them: snapshot + ``begin_attempt`` (claim), the squash lands on the target,
    SIGKILL before the phase recorder (no post tip), ``--abort`` (refuses), a
    re-run's claim (``begin_attempt`` again; the re-run then fails without
    moving anything), and ``--abort`` again.
    """
    repo = _init_repo(tmp_path)
    manifest = _manifest()
    state = ConsolidationState(mission_id=_MISSION_ID, mission_slug=_SLUG, target_branch=_TARGET, wp_order=["WP01"])

    snapshot = capture_pre_mutation_snapshot(repo, state, manifest, coord_ref=None)[_TARGET]
    begin_attempt(repo, state)
    landed = _commit(repo, "squash-landed")  # killed before record_post_mutation_tips ran

    first_abort = rollback_to_snapshot(repo, state, target_branch=_TARGET)
    target_outcome = next(o for o in first_abort.outcomes if o.branch == _TARGET)
    assert target_outcome.kind is BranchOutcomeKind.NOT_RESTORED, "precondition: the first --abort refuses the unrecorded move"
    assert not first_abort.fully_restored

    begin_attempt(repo, state)  # the re-run's claim; the squash then refuses as a no-op
    second_abort = rollback_to_snapshot(repo, state, target_branch=_TARGET)

    assert _rev(repo, _TARGET) == landed, "precondition: nothing between the aborts moved the target"
    assert not second_abort.fully_restored, (
        f"--abort reported a full restore (target outcome: "
        f"{next(o for o in second_abort.outcomes if o.branch == _TARGET).kind}) while {_TARGET} is still at the "
        f"unrecorded landing {landed[:7]} instead of the pre-consolidation snapshot {snapshot[:7]}; "
        "the record would be cleared over a never-reconciled target"
    )


def _run_state(repo: Path, pre_sha: str) -> _MergeRunState:
    manifest = _manifest()
    state = ConsolidationState(mission_id=_MISSION_ID, mission_slug=_SLUG, target_branch=_TARGET, wp_order=["WP01"])
    run = _MergeRunState(
        main_repo=repo,
        mission_slug=_SLUG,
        canonical_id=_MISSION_ID,
        canonical_mission_id=_MISSION_ID,
        feature_dir=repo / "kitty-specs" / _SLUG,
        target_feature_dir=repo / "kitty-specs" / _SLUG,
        lanes_manifest=manifest,
        all_wp_ids=["WP01"],
        push=False,
        delete_branch=False,
        remove_worktree=False,
        strategy=MergeStrategy.SQUASH,
        assume_yes=True,
        planning_artifact_only=False,
        state=state,
        is_resume=False,
    )
    run.target_expected_old_sha = pre_sha
    return run


@pytest.mark.p0_repro(issue=5666)
def test_failed_reconciliation_rollback_keeps_a_concurrent_target_commit(tmp_path: Path) -> None:
    """The reconciliation FAIL rollback must never discard a commit another actor landed on the target.

    Intentional red-first P0 reproduction of #5666: the squash lands on the
    target, a teammate (or another Mission's status transition) commits on top
    of it, then the gate FAILs and the rollback runs. The rollback may refuse,
    but the concurrent commit must stay reachable from the target.
    """
    repo = _init_repo(tmp_path)
    pre_sha = _rev(repo, _TARGET)
    _commit(repo, "squash-landed")
    foreign = _commit(repo, "teammate-commit")
    run = _run_state(repo, pre_sha)

    _rollback_target_after_failed_reconciliation(run)

    assert _is_ancestor(repo, foreign, _TARGET), (
        f"the reconciliation-FAIL rollback reset {_TARGET} to {_rev(repo, _TARGET)[:7]} and discarded the concurrent "
        f"commit {foreign[:7]}; it is only in the reflog now"
    )
