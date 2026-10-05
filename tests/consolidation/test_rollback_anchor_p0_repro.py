"""Reproductions of two P0 rollback-anchor bugs (#5686, #5666), now per-PR guards.

Both started as intentional red-first P0 reproductions (ADR 2026-07-17-1),
held out of every run except the nightly ``p0-repro`` lane by their marker.
Mission rollback-anchor-authority fixed both and removed the markers (FR-010,
SC-001), which turned each into an ordinary per-PR guard.

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
  runs, after this run's squash. The reconciliation FAIL path used to reset the
  target itself (the retired ``_rollback_target_after_failed_reconciliation``)
  with a compare-and-swap whose expected value was the tip it had just read, so
  the concurrent commit was discarded from the target. The fix leaves the
  restore to the single rollback door (#5385), which compare-and-swaps against
  the post tip THIS run recorded and reports the foreign move as NOT restored.
  The guard drives a real in-process ``consolidate`` through that door and is an
  ordinary per-PR test (no ``p0_repro`` marker).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
import typer

from specify_cli.consolidation import executor
from specify_cli.consolidation.rollback import (
    BranchOutcomeKind,
    begin_attempt,
    capture_pre_mutation_snapshot,
    rollback_to_snapshot,
)
from specify_cli.consolidation.state import ConsolidationState
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from tests.terminus.lanes_fixture import build_lanes_mission

pytestmark = [pytest.mark.git_repo]

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


@pytest.mark.fast
def test_second_abort_never_reports_restored_over_an_unrecorded_landing(tmp_path: Path) -> None:
    """A second ``--abort`` must not report a full restore while the target keeps an unverified landing.

    Intentional red-first P0 reproduction of #5686. Sequence, through the
    rollback authority's public entry points in the order consolidate calls
    them: snapshot + ``begin_attempt`` (claim), the squash lands on the target,
    SIGKILL before the phase recorder (no post tip), ``--abort`` (refuses), a
    re-run's claim (``begin_attempt`` again; the re-run then fails without
    moving anything), and ``--abort`` again.

    Mutation note (F6): this repro goes red only when BOTH halves of the fix are
    reverted -- ``begin_attempt``'s unsettled mark AND ``_settle_outcomes``
    re-adding a ``NOT_RESTORED`` branch to the unsettled set -- because the first
    ``--abort`` re-marks the target unsettled on its own. The ``begin_attempt``
    half alone is pinned by
    ``test_rollback_authority.py::test_kill_left_landing_without_an_abort_stays_unexplained_at_the_next_attempt``.
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


@pytest.mark.integration
def test_failed_reconciliation_rollback_keeps_a_concurrent_target_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The reconciliation FAIL rollback must never discard a commit another actor landed on the target.

    #5666, driven through the production entry point: a real in-process
    ``consolidate`` squashes the mission onto the target, then a teammate (or
    another Mission's status transition) commits on top of the landing in the
    repository root checkout just before the gate runs. That foreign path is
    un-attributable, so the real gate FAILs, and the single rollback door runs.
    The rollback may refuse, but the concurrent commit must stay reachable from
    the target and the door must say why it kept it.
    """
    mission = build_lanes_mission(tmp_path, wps=("WP01",), target_branch="develop", mid8="01M5666F")
    target = mission.target_branch
    original_gate = executor._phase_reconcile_before_teardown
    foreign: list[str] = []

    def gate_after_a_teammate_commit(run: executor._MergeRunState) -> None:
        assert _git(mission.repo, "symbolic-ref", "--short", "HEAD") == target, "precondition: the root checkout is on the target"
        foreign.append(_commit(mission.repo, "teammate-commit"))
        original_gate(run)

    monkeypatch.setattr(executor, "_phase_reconcile_before_teardown", gate_after_a_teammate_commit)
    monkeypatch.setenv("HOME", str(mission.home))
    monkeypatch.chdir(mission.repo)

    with pytest.raises(typer.Exit) as excinfo:
        executor._run_lane_based_consolidation(mission.repo, mission.slug, push=False, delete_branch=None, remove_worktree=None, assume_yes=True)

    output = " ".join(capsys.readouterr().out.split())
    assert excinfo.value.exit_code == 1, f"the gate must FAIL on the foreign path. output={output}"
    assert foreign, "precondition: the gate ran after the teammate commit"
    assert "Reconciliation FAILED" in output and "teammate-commit.txt" in output, f"precondition: the real gate FAILs on the foreign path. output={output}"
    assert _is_ancestor(mission.repo, foreign[0], target), (
        f"the reconciliation-FAIL rollback reset {target} to {_rev(mission.repo, target)[:7]} and discarded the concurrent "
        f"commit {foreign[0][:7]}; it is only in the reflog now. output={output}"
    )
    assert re.search(rf"NOT restored {re.escape(target)} .*moved by another actor", output), (
        f"the door must report the target NOT restored because another actor moved it. output={output}"
    )
    assert (mission.repo / "teammate-commit.txt").is_file(), "the teammate's file must survive in the repository root checkout"
