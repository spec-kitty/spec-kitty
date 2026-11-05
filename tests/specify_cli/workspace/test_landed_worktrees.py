"""Safety matrix for the landed-worktree assessment and prune (#7173, WP03, T013).

Real repositories with a bare ``origin``. Only a worktree whose verdict is
``landed`` may be removed, and the prune re-assesses it right before acting.
The process probe is injected: a fake ``/proc`` (empty, so nothing is busy)
for the ordinary cases, and a view linking the real ``/proc`` entry of a real
``sleep`` process for the running-process case.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest

from specify_cli.git import destructive_guard
from specify_cli.git.destructive_guard import (
    DESTRUCTIVE_OP_ONLY_COPY,
    WORKTREE_PARTIALLY_REMOVED,
    WORKTREE_REMOVE_REFUSED_BY_GIT,
    DestructiveOpRefused,
    RemoveResult,
)
from specify_cli.lanes.lane_tip import AbsorptionUnsupported
from specify_cli.workspace import landed_worktrees, process_probe
from specify_cli.workspace.landed_worktrees import (
    PruneOutcome,
    Reason,
    Verdict,
    WorktreeAssessment,
    WorktreeVerdict,
    assess_worktrees,
    prune_landed,
)
from specify_cli.workspace.process_probe import ProcessProbeResult, processes_with_cwd_under

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_MISSION_LANE = "kitty/mission-foo-01ABCDEF-lane-a"
_OLD_DATE = "2001-02-03T04:05:06+00:00"


def _git(cwd: Path, *args: str, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False, env=env)
    if result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed in {cwd}: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout


def _rev(cwd: Path, rev: str) -> str:
    return _git(cwd, "rev-parse", rev).strip()


def _commit(cwd: Path, name: str, content: str) -> str:
    (cwd / name).write_text(content, encoding="utf-8")
    _git(cwd, "add", "-A")
    _git(cwd, "commit", "-q", "-m", f"add {name}")
    return _rev(cwd, "HEAD")


def _init(path: Path) -> Path:
    path.mkdir()
    _git(path, "init", "-q", "-b", "main")
    _git(path, "config", "user.email", "t@example.invalid")
    _git(path, "config", "user.name", "T")
    _git(path, "config", "commit.gpgsign", "false")
    (path / ".gitignore").write_text(".venv/\n", encoding="utf-8")
    _commit(path, "src.py", "x = 1\n")
    return path


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repository whose ``main`` is pushed to a bare ``origin``."""
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    root = _init(tmp_path / "repo")
    _git(root, "remote", "add", "origin", str(origin))
    _git(root, "push", "-q", "-u", "origin", "main")
    return root


def _worktree(root: Path, name: str, *, start: str = "main") -> Path:
    path = root.parent / f"wt-{name.replace('/', '_')}"
    _git(root, "worktree", "add", "-q", "-b", name, str(path), start)
    return path


def _land_by_rebase(root: Path, branch: str) -> tuple[Path, str]:
    """A worktree whose commit was re-created on ``main`` with a NEW SHA (rebase merge)."""
    worktree = _worktree(root, branch)
    tip = _commit(worktree, f"{branch}.txt", f"{branch}\n")
    _git(worktree, "push", "-q", "origin", branch)
    env = {**os.environ, "GIT_COMMITTER_DATE": _OLD_DATE}
    _git(root, "cherry-pick", tip, env=env)
    _git(root, "push", "-q", "origin", "main")
    _git(root, "fetch", "-q", "origin")
    landed = _rev(root, "refs/remotes/origin/main")
    assert landed != tip, "the rebase fixture must rewrite the SHA (non-vacuity)"
    assert subprocess.run(["git", "merge-base", "--is-ancestor", tip, landed], cwd=root, check=False).returncode != 0
    return worktree, tip


def _idle_probe(tmp_path: Path) -> landed_worktrees.ProbeFn:
    empty = tmp_path / "proc-empty"
    empty.mkdir(exist_ok=True)

    def probe(paths: Sequence[Path]) -> ProcessProbeResult:
        return processes_with_cwd_under(paths, proc_root=empty)

    return probe


def _by_path(assessment: WorktreeAssessment, worktree: Path) -> WorktreeVerdict:
    matches = [v for v in assessment.verdicts if v.path.resolve() == worktree.resolve()]
    assert len(matches) == 1, assessment
    return matches[0]


def _registered(root: Path, worktree: Path) -> bool:
    return str(worktree.resolve()) in _git(root, "worktree", "list", "--porcelain")


def _has_branch(root: Path, branch: str) -> bool:
    return subprocess.run(["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=root, check=False, capture_output=True).returncode == 0


@pytest.fixture
def sleeper() -> Iterator[list[subprocess.Popen[bytes]]]:
    procs: list[subprocess.Popen[bytes]] = []
    yield procs
    for proc in procs:
        proc.kill()
        proc.wait()


def _view_probe(tmp_path: Path, pids: Sequence[int]) -> landed_worktrees.ProbeFn:
    """A ``/proc`` holding only *pids*, each linked to its real ``/proc`` entry."""
    view = tmp_path / "proc-view"
    view.mkdir(exist_ok=True)
    for pid in pids:
        (view / str(pid)).symlink_to(Path("/proc") / str(pid))

    def probe(paths: Sequence[Path]) -> ProcessProbeResult:
        return processes_with_cwd_under(paths, proc_root=view)

    return probe


# ---------------------------------------------------------------------------
# SC-001: the full fixture
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not Path("/proc/self").exists(), reason="needs a real /proc for the running process")
def test_only_the_rebase_merged_worktree_is_removed(repo: Path, tmp_path: Path, sleeper: list[subprocess.Popen[bytes]]) -> None:
    landed, tip = _land_by_rebase(repo, "land-x")
    open_wt = _worktree(repo, "open-y")
    _commit(open_wt, "new.txt", "unpushed work\n")
    dirty = _worktree(repo, "dirty-z")
    (dirty / "src.py").write_text("x = 2\n", encoding="utf-8")
    busy, _ = _land_by_rebase(repo, "busy-w")
    sleeper.append(subprocess.Popen(["sleep", "30"], cwd=busy))
    mission = _worktree(repo, _MISSION_LANE)
    probe = _view_probe(tmp_path, [p.pid for p in sleeper])

    assessment = assess_worktrees(repo, current_dir=repo, probe=probe)

    assert assessment.error is None
    assert assessment.primary_ref == "refs/remotes/origin/main"
    assert _by_path(assessment, repo).reason is Reason.MAIN_WORKTREE
    assert _by_path(assessment, landed).verdict is Verdict.LANDED
    assert _by_path(assessment, open_wt).reason is Reason.CONTENT_NOT_ON_PRIMARY
    assert _by_path(assessment, dirty).reason is Reason.UNCOMMITTED_CHANGES
    assert _by_path(assessment, busy).reason is Reason.PROCESS_RUNNING
    assert _by_path(assessment, mission).verdict is Verdict.MISSION_OWNED
    assert [v.path for v in assessment.verdicts if v.removable] == [_by_path(assessment, landed).path]

    outcomes = prune_landed(repo, current_dir=repo, probe=probe)

    assert [(o.removed, o.branch, o.branch_deleted) for o in outcomes] == [(True, "land-x", True)]
    assert not landed.exists()
    assert not _has_branch(repo, "land-x")
    for kept in (open_wt, dirty, busy, mission):
        assert kept.exists() and _registered(repo, kept)
    assert _has_branch(repo, _MISSION_LANE)
    assert outcomes[0].tip == tip


def test_recreate_restores_the_same_sha(repo: Path, tmp_path: Path) -> None:
    """SC-003: the printed recreate command brings the exact tip back."""
    _, tip = _land_by_rebase(repo, "land-x")

    [outcome] = prune_landed(repo, current_dir=repo, probe=_idle_probe(tmp_path))

    assert outcome.recreate == f"git branch land-x {tip}"
    # Only the remote-tracking origin/land-x holds the tip, and a remote-tracking
    # ref does not count (fold C): the tip is kept under a discarded ref.
    assert outcome.kept_ref == "refs/spec-kitty/discarded/land-x"
    subprocess.run(outcome.recreate.split(), cwd=repo, check=True)
    assert _rev(repo, "refs/heads/land-x") == tip


def test_deleted_remote_head_keeps_the_tip_under_a_discarded_ref(repo: Path, tmp_path: Path) -> None:
    _, tip = _land_by_rebase(repo, "land-x")
    _git(repo, "push", "-q", "origin", "--delete", "land-x")
    _git(repo, "fetch", "-q", "--prune", "origin")

    [outcome] = prune_landed(repo, current_dir=repo, probe=_idle_probe(tmp_path))

    assert outcome.removed and outcome.branch_deleted
    assert outcome.kept_ref == "refs/spec-kitty/discarded/land-x"
    assert _rev(repo, "refs/spec-kitty/discarded/land-x") == tip
    assert outcome.to_json()["kept_ref"] == "refs/spec-kitty/discarded/land-x"


def test_squash_merged_is_landed(repo: Path, tmp_path: Path) -> None:
    worktree = _worktree(repo, "squash-x")
    _commit(worktree, "a.txt", "a\n")
    tip = _commit(worktree, "b.txt", "b\n")
    _git(repo, "merge", "-q", "--squash", "squash-x")
    _git(repo, "commit", "-q", "-m", "squash")
    _git(repo, "push", "-q", "origin", "main")
    assert _rev(repo, "HEAD") != tip

    verdict = _by_path(assess_worktrees(repo, current_dir=repo, probe=_idle_probe(tmp_path)), worktree)

    assert verdict.verdict is Verdict.LANDED
    assert verdict.reason is Reason.LANDED
    assert verdict.removable


@pytest.mark.parametrize("kind", ["tracked", "untracked"])
def test_local_changes_keep_the_worktree(repo: Path, tmp_path: Path, kind: str) -> None:
    worktree, _ = _land_by_rebase(repo, "land-x")
    if kind == "tracked":
        (worktree / "src.py").write_text("x = 3\n", encoding="utf-8")
    else:
        (worktree / "notes.txt").write_text("only copy\n", encoding="utf-8")

    verdict = _by_path(assess_worktrees(repo, current_dir=repo, probe=_idle_probe(tmp_path)), worktree)
    outcomes = prune_landed(repo, current_dir=repo, probe=_idle_probe(tmp_path))

    assert (verdict.verdict, verdict.reason) == (Verdict.NOT_LANDED, Reason.UNCOMMITTED_CHANGES)
    assert not verdict.removable
    assert outcomes == []
    assert worktree.exists() and _has_branch(repo, "land-x")


def test_an_ignored_virtualenv_alone_does_not_block(repo: Path, tmp_path: Path) -> None:
    worktree, _ = _land_by_rebase(repo, "land-x")
    (worktree / ".venv" / "lib").mkdir(parents=True)
    (worktree / ".venv" / "lib" / "big.bin").write_bytes(b"\0" * 1024)

    assert _by_path(assess_worktrees(repo, current_dir=repo, probe=_idle_probe(tmp_path)), worktree).verdict is Verdict.LANDED
    [outcome] = prune_landed(repo, current_dir=repo, probe=_idle_probe(tmp_path))

    assert outcome.removed
    assert not worktree.exists()


def test_a_partly_removed_worktree_is_reported_removed_and_keeps_its_branch(repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """git unregisters the worktree, then fails on a file it cannot delete: a husk is left, the branch stays.

    The failure is injected at the guard's git seam (#5691: a chmod denial is vacuous as root): the real
    ``git worktree remove`` runs, then the file git could not delete is left behind and git's error is returned.
    """
    worktree, tip = _land_by_rebase(repo, "land-x")
    leftover = worktree / ".venv" / "locked" / "pinned.bin"
    real_run_git = destructive_guard._run_git

    def remove_fails_part_way(cwd: Path, args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        result = real_run_git(cwd, args, **kwargs)
        if args[:2] != ["worktree", "remove"] or result.returncode != 0:
            return result
        leftover.parent.mkdir(parents=True)
        leftover.write_bytes(b"\0")
        return subprocess.CompletedProcess(result.args, 255, "", f"error: failed to delete '{worktree}': Permission denied\n")

    monkeypatch.setattr(destructive_guard, "_run_git", remove_fails_part_way)

    [outcome] = prune_landed(repo, current_dir=repo, probe=_idle_probe(tmp_path))

    assert (outcome.removed, outcome.branch_deleted, outcome.refusal) == (True, False, WORKTREE_PARTIALLY_REMOVED)
    assert not _registered(repo, worktree) and leftover.exists()
    assert _rev(repo, "land-x") == tip


def test_an_unpushed_commit_is_not_landed(repo: Path, tmp_path: Path) -> None:
    worktree = _worktree(repo, "open-y")
    _commit(worktree, "new.txt", "new content\n")

    verdict = _by_path(assess_worktrees(repo, current_dir=repo, probe=_idle_probe(tmp_path)), worktree)

    assert (verdict.verdict, verdict.reason) == (Verdict.NOT_LANDED, Reason.CONTENT_NOT_ON_PRIMARY)
    assert prune_landed(repo, current_dir=repo, probe=_idle_probe(tmp_path)) == []
    assert worktree.exists()


def test_a_running_process_keeps_the_worktree(repo: Path, tmp_path: Path, sleeper: list[subprocess.Popen[bytes]]) -> None:
    worktree, _ = _land_by_rebase(repo, "land-x")
    (worktree / "deep").mkdir()
    sleeper.append(subprocess.Popen(["sleep", "30"], cwd=worktree / "deep"))
    probe = _view_probe(tmp_path, [sleeper[0].pid])

    verdict = _by_path(assess_worktrees(repo, current_dir=repo, probe=probe), worktree)

    assert (verdict.verdict, verdict.reason) == (Verdict.NOT_LANDED, Reason.PROCESS_RUNNING)
    assert prune_landed(repo, current_dir=repo, probe=probe) == []
    assert worktree.exists()


def test_an_unavailable_process_probe_is_unproven(repo: Path, tmp_path: Path) -> None:
    worktree, _ = _land_by_rebase(repo, "land-x")

    def missing(paths: Sequence[Path]) -> ProcessProbeResult:
        return processes_with_cwd_under(paths, proc_root=tmp_path / "no-proc")

    verdict = _by_path(assess_worktrees(repo, current_dir=repo, probe=missing), worktree)

    assert (verdict.verdict, verdict.reason) == (Verdict.UNPROVEN, Reason.PROCESS_PROOF_UNAVAILABLE)
    assert prune_landed(repo, current_dir=repo, probe=missing) == []
    assert worktree.exists()


def test_an_unreadable_unrelated_process_is_counted_and_the_worktree_stays_landed(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sleeper: list[subprocess.Popen[bytes]]
) -> None:
    """Operator ruling plan.prune.unreadable_process: skip and report."""
    worktree, _ = _land_by_rebase(repo, "land-x")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    sleeper.append(subprocess.Popen(["sleep", "30"], cwd=elsewhere))
    hidden = tmp_path / "hidden"
    hidden.mkdir()
    sleeper.append(subprocess.Popen(["sleep", "30"], cwd=hidden))
    probe = _view_probe(tmp_path, [p.pid for p in sleeper])
    real = process_probe._read_cwd

    def denied(link: Path) -> str:
        if link.parent.name == str(sleeper[1].pid):
            raise PermissionError(13, "Permission denied", str(link))
        return real(link)

    monkeypatch.setattr(process_probe, "_read_cwd", denied)

    assessment = assess_worktrees(repo, current_dir=repo, probe=probe)

    assert _by_path(assessment, worktree).verdict is Verdict.LANDED
    assert assessment.uninspected_processes == 1
    assert assessment.to_json()["uninspected_processes"] == 1
    [outcome] = prune_landed(repo, current_dir=repo, probe=probe, assessment=assessment)
    assert outcome.removed


def test_a_locked_worktree_is_kept(repo: Path, tmp_path: Path) -> None:
    worktree, _ = _land_by_rebase(repo, "land-x")
    _git(repo, "worktree", "lock", "--reason", "mine", str(worktree))

    verdict = _by_path(assess_worktrees(repo, current_dir=repo, probe=_idle_probe(tmp_path)), worktree)

    assert (verdict.verdict, verdict.reason) == (Verdict.NOT_LANDED, Reason.LOCKED)
    assert prune_landed(repo, current_dir=repo, probe=_idle_probe(tmp_path)) == []
    assert worktree.exists()


def _stop_rebase_at_start(worktree: Path) -> None:
    """``git rebase -i main`` halted by a ``break`` before its first pick: HEAD is detached, the worktree clean."""
    env = {**os.environ, "GIT_SEQUENCE_EDITOR": "sed -i '1i break'"}
    _git(worktree, "rebase", "-q", "-i", "main", env=env)
    assert subprocess.run(["git", "symbolic-ref", "-q", "HEAD"], cwd=worktree, check=False).returncode != 0


def _absorbed_lane(repo: Path, branch: str, *, commits: int = 1) -> Path:
    """A worktree under .worktrees/ whose commits were fast-forwarded onto ``main`` and pushed."""
    worktree = repo / ".worktrees" / "lane"
    _git(repo, "worktree", "add", "-q", "-b", branch, str(worktree), "main")
    for index in range(commits):
        _commit(worktree, f"lane-{index}.txt", f"lane {index}\n")
    _git(repo, "merge", "-q", "--ff-only", branch)
    _git(repo, "push", "-q", "origin", "main")
    _git(repo, "fetch", "-q", "origin")
    return worktree


@pytest.mark.parametrize("rebasing", [False, True], ids=["mission-lane", "mission-lane-mid-rebase"])
def test_a_mission_lane_is_report_only_even_when_absorbed(repo: Path, tmp_path: Path, rebasing: bool) -> None:
    """A rebase stopped mid-way detaches HEAD; ``head-name`` still makes the lane the Mission's."""
    worktree = _absorbed_lane(repo, _MISSION_LANE)
    if rebasing:
        _stop_rebase_at_start(worktree)

    verdict = _by_path(assess_worktrees(repo, current_dir=repo, probe=_idle_probe(tmp_path)), worktree)

    assert (verdict.verdict, verdict.reason) == (Verdict.MISSION_OWNED, Reason.MISSION_LANE)
    assert prune_landed(repo, current_dir=repo, probe=_idle_probe(tmp_path)) == []
    assert worktree.exists() and _has_branch(repo, _MISSION_LANE)


@pytest.mark.parametrize("operation", ["rebase", "bisect"])
def test_a_worktree_with_an_operation_in_progress_is_kept(repo: Path, tmp_path: Path, operation: str) -> None:
    """Detached and clean mid-operation, otherwise landed: the operation's state lives only in the worktree's git dir."""
    worktree = _absorbed_lane(repo, "land-x", commits=3)
    if operation == "rebase":
        _stop_rebase_at_start(worktree)
    else:
        _git(worktree, "bisect", "start", "HEAD", "HEAD~3")
        assert subprocess.run(["git", "symbolic-ref", "-q", "HEAD"], cwd=worktree, check=False).returncode != 0

    verdict = _by_path(assess_worktrees(repo, current_dir=repo, probe=_idle_probe(tmp_path)), worktree)

    assert (verdict.verdict, verdict.reason) == (Verdict.NOT_LANDED, Reason.OPERATION_IN_PROGRESS)
    assert prune_landed(repo, current_dir=repo, probe=_idle_probe(tmp_path)) == []
    assert worktree.exists() and _has_branch(repo, "land-x")


def test_without_origin_everything_is_unproven(tmp_path: Path) -> None:
    root = _init(tmp_path / "solo")
    worktree = _worktree(root, "land-x")

    assessment = assess_worktrees(root, current_dir=root, probe=_idle_probe(tmp_path))

    assert (_by_path(assessment, worktree).verdict, _by_path(assessment, worktree).reason) == (Verdict.UNPROVEN, Reason.PRIMARY_REF_MISSING)
    assert prune_landed(root, current_dir=root, probe=_idle_probe(tmp_path)) == []
    assert worktree.exists()


def test_a_detached_worktree_at_a_main_commit_is_removed_without_a_branch_delete(repo: Path, tmp_path: Path) -> None:
    worktree = repo / ".worktrees" / "detached"
    _git(repo, "worktree", "add", "-q", "--detach", str(worktree), "main")
    head = _rev(repo, "main")
    branches_before = _git(repo, "branch", "--format=%(refname)")

    [outcome] = prune_landed(repo, current_dir=repo, probe=_idle_probe(tmp_path))

    assert outcome.removed and outcome.branch is None and not outcome.branch_deleted
    assert outcome.recreate == f"git worktree add --detach {outcome.path} {head}"
    assert not worktree.exists()
    assert _git(repo, "branch", "--format=%(refname)") == branches_before
    # The tip is on local main: nothing to keep.
    assert outcome.kept_ref is None
    assert _git(repo, "for-each-ref", "refs/spec-kitty/") == ""


def test_the_worktree_the_command_runs_in_is_excluded(repo: Path, tmp_path: Path) -> None:
    worktree, _ = _land_by_rebase(repo, "land-x")
    (worktree / "sub").mkdir()

    verdict = _by_path(assess_worktrees(repo, current_dir=worktree / "sub", probe=_idle_probe(tmp_path)), worktree)

    assert (verdict.verdict, verdict.reason) == (Verdict.EXCLUDED, Reason.CURRENT_WORKTREE)
    assert prune_landed(repo, current_dir=worktree / "sub", probe=_idle_probe(tmp_path)) == []
    assert worktree.exists()


def test_a_prunable_worktree_is_excluded(repo: Path, tmp_path: Path) -> None:
    worktree, _ = _land_by_rebase(repo, "land-x")
    shutil.rmtree(worktree)  # test-only: simulate a directory deleted by hand

    verdict = _by_path(assess_worktrees(repo, current_dir=repo, probe=_idle_probe(tmp_path)), worktree)

    assert (verdict.verdict, verdict.reason) == (Verdict.EXCLUDED, Reason.PRUNABLE)
    assert prune_landed(repo, current_dir=repo, probe=_idle_probe(tmp_path)) == []
    assert _has_branch(repo, "land-x")


# ---------------------------------------------------------------------------
# Re-assess before act (TOCTOU)
# ---------------------------------------------------------------------------


def test_a_file_appearing_between_assess_and_act_keeps_the_worktree(repo: Path, tmp_path: Path) -> None:
    worktree, _ = _land_by_rebase(repo, "land-x")
    idle = _idle_probe(tmp_path)
    calls: list[int] = []

    def racing(paths: Sequence[Path]) -> ProcessProbeResult:
        # The first probe runs during the initial assessment, after its dirty check.
        if not calls:
            (worktree / "late.txt").write_text("written during the prune\n", encoding="utf-8")
        calls.append(len(paths))
        return idle(paths)

    [outcome] = prune_landed(repo, current_dir=repo, probe=racing)

    assert not outcome.removed and not outcome.branch_deleted
    assert outcome.refusal == Reason.UNCOMMITTED_CHANGES
    assert (worktree / "late.txt").exists() and _has_branch(repo, "land-x")


def test_a_commit_between_assess_and_act_keeps_the_worktree(repo: Path, tmp_path: Path) -> None:
    worktree, _ = _land_by_rebase(repo, "land-x")
    probe = _idle_probe(tmp_path)
    assessment = assess_worktrees(repo, current_dir=repo, probe=probe)
    assert _by_path(assessment, worktree).removable
    _commit(worktree, "late.txt", "late commit\n")

    [outcome] = prune_landed(repo, current_dir=repo, probe=probe, assessment=assessment)

    assert not outcome.removed
    assert outcome.refusal == Reason.CONTENT_NOT_ON_PRIMARY
    assert worktree.exists()


def test_a_landed_commit_between_assess_and_act_is_still_kept_because_the_tip_moved(repo: Path, tmp_path: Path) -> None:
    worktree, _ = _land_by_rebase(repo, "land-x")
    probe = _idle_probe(tmp_path)
    assessment = assess_worktrees(repo, current_dir=repo, probe=probe)
    _git(worktree, "reset", "-q", "--hard", "origin/main")  # a new tip, itself landed

    [outcome] = prune_landed(repo, current_dir=repo, probe=probe, assessment=assessment)

    assert not outcome.removed
    assert outcome.refusal == landed_worktrees.TIP_MOVED
    assert worktree.exists()


def test_a_git_refusal_is_recorded_and_the_run_continues(repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    first, _ = _land_by_rebase(repo, "land-a")
    second, _ = _land_by_rebase(repo, "land-b")
    probe = _idle_probe(tmp_path)
    assessment = assess_worktrees(repo, current_dir=repo, probe=probe)
    # Locked after the assessment, and the re-assessment is made to miss it: git itself must refuse.
    _git(repo, "worktree", "lock", str(first))
    real = landed_worktrees._reassess

    def stale(root: Path, path: Path, ctx: landed_worktrees._Context) -> WorktreeVerdict | None:
        verdict = real(root, path, ctx)
        if verdict is not None and verdict.reason is Reason.LOCKED:
            return WorktreeVerdict(path=verdict.path, branch=verdict.branch, tip=verdict.tip, verdict=Verdict.LANDED, reason=Reason.LANDED, detail="")
        return verdict

    monkeypatch.setattr(landed_worktrees, "_reassess", stale)

    outcomes = {o.branch: o for o in prune_landed(repo, current_dir=repo, probe=probe, assessment=assessment)}

    assert outcomes["land-a"].refusal == WORKTREE_REMOVE_REFUSED_BY_GIT
    assert not outcomes["land-a"].removed and not outcomes["land-a"].branch_deleted
    assert first.exists() and _has_branch(repo, "land-a")
    assert outcomes["land-b"].removed and outcomes["land-b"].branch_deleted
    assert not second.exists()


def test_a_branch_moved_after_removal_is_not_deleted(repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The guard's branch delete is not compare-and-swap: the prune compares the tip itself first."""
    worktree, tip = _land_by_rebase(repo, "land-x")
    real_remove = landed_worktrees.guarded_worktree_remove

    def remove_then_move(worktree_path: Path, **kwargs: Any) -> RemoveResult:
        result = real_remove(worktree_path, **kwargs)
        _git(repo, "branch", "-f", "land-x", "main")  # someone moved the branch meanwhile
        return result

    monkeypatch.setattr(landed_worktrees, "guarded_worktree_remove", remove_then_move)

    [outcome] = prune_landed(repo, current_dir=repo, probe=_idle_probe(tmp_path))

    assert outcome.removed and not outcome.branch_deleted
    assert outcome.refusal == landed_worktrees.BRANCH_MOVED
    assert _has_branch(repo, "land-x")
    assert not worktree.exists()
    assert outcome.recreate == f"git worktree add {outcome.path} land-x", "the branch was kept: recreate the worktree on it"
    _git(repo, *shlex.split(outcome.recreate)[1:])
    assert worktree.exists() and _git(worktree, "branch", "--show-current").strip() == "land-x"


def test_a_branch_delete_failure_is_a_per_worktree_refusal(repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """I1: the worktree is gone but ``git branch -D`` fails: recorded, the run continues."""
    _land_by_rebase(repo, "land-a")
    _land_by_rebase(repo, "land-b")

    def failing(root: Path, branch: str, **_: object) -> str | None:
        if branch == "land-a":
            raise RuntimeError("git branch -D failed")
        return None

    monkeypatch.setattr(landed_worktrees, "guarded_branch_delete", failing)

    outcomes = {o.branch: o for o in prune_landed(repo, current_dir=repo, probe=_idle_probe(tmp_path))}

    assert outcomes["land-a"].removed and not outcomes["land-a"].branch_deleted
    assert outcomes["land-a"].refusal == landed_worktrees.BRANCH_DELETE_FAILED
    assert outcomes["land-b"].removed and outcomes["land-b"].branch_deleted


# ---------------------------------------------------------------------------
# Model, JSON and error shape
# ---------------------------------------------------------------------------


def test_an_unreadable_worktree_list_is_an_error_not_a_verdict(tmp_path: Path) -> None:
    plain = tmp_path / "not-a-repo"
    plain.mkdir()

    assessment = assess_worktrees(plain, current_dir=plain, probe=_idle_probe(tmp_path))

    assert assessment.error
    assert assessment.verdicts == ()
    assert prune_landed(plain, current_dir=plain, probe=_idle_probe(tmp_path)) == []


def test_json_shapes_use_the_data_model_field_names(repo: Path, tmp_path: Path) -> None:
    _land_by_rebase(repo, "land-x")
    assessment = assess_worktrees(repo, current_dir=repo, probe=_idle_probe(tmp_path))

    payload = assessment.to_json()

    assert set(payload) == {"primary_ref", "verdicts", "error", "uninspected_processes"}
    assert set(payload["verdicts"][0]) == {"path", "branch", "tip", "verdict", "reason", "detail", "removable", "ignored_paths", "ignored_count"}
    assert {v["verdict"] for v in payload["verdicts"]} == {"excluded", "landed"}
    outcome = PruneOutcome(path=Path("/x"), branch=None, tip="abc", removed=False, branch_deleted=False, kept_ref=None, recreate="r", refusal=None)
    assert set(outcome.to_json()) == {
        "path",
        "branch",
        "tip",
        "removed",
        "branch_deleted",
        "kept_ref",
        "recreate",
        "refusal",
        "kept_commits",
    }
    assert outcome.to_json()["kept_commits"] == [], "the #7211 key is additive and empty by default"
    kept = PruneOutcome(
        path=Path("/x"),
        branch="b",
        tip="abc",
        removed=True,
        branch_deleted=True,
        kept_ref=None,
        recreate="r",
        refusal=None,
        kept_commits=("refs/spec-kitty/discarded/reflog/abc",),
    )
    assert kept.to_json()["kept_commits"] == ["refs/spec-kitty/discarded/reflog/abc"]


def test_assessment_probes_processes_once_for_many_worktrees(repo: Path, tmp_path: Path) -> None:
    """NFR-003: one process scan serves 20 worktrees."""
    for index in range(20):
        _git(repo, "worktree", "add", "-q", "--detach", str(repo / ".worktrees" / f"many-{index}"), "main")
    idle = _idle_probe(tmp_path)
    calls: list[int] = []

    def counting(paths: Sequence[Path]) -> ProcessProbeResult:
        calls.append(len(paths))
        return idle(paths)

    assessment = assess_worktrees(repo, current_dir=repo, probe=counting)

    assert calls == [20]
    assert sum(v.removable for v in assessment.verdicts) == 20


# ---------------------------------------------------------------------------
# Squad folds (#7173 pre-PR adversarial squad)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("flag", ["--assume-unchanged", "--skip-worktree"])
def test_an_edit_hidden_by_an_index_flag_is_uncommitted(repo: Path, tmp_path: Path, flag: str) -> None:
    """Fold A: ``git status`` does not show an edit behind assume-unchanged / skip-worktree."""
    worktree, _ = _land_by_rebase(repo, "land-x")
    _git(worktree, "update-index", flag, "src.py")
    (worktree / "src.py").write_text("x = 99  # only copy\n", encoding="utf-8")
    assert _git(worktree, "status", "--porcelain") == "", "non-vacuity: status hides the edit"

    verdict = _by_path(assess_worktrees(repo, current_dir=repo, probe=_idle_probe(tmp_path)), worktree)

    assert (verdict.verdict, verdict.reason) == (Verdict.NOT_LANDED, Reason.UNCOMMITTED_CHANGES)
    assert verdict.detail == "hidden by index flag: src.py"
    assert prune_landed(repo, current_dir=repo, probe=_idle_probe(tmp_path)) == []
    assert (worktree / "src.py").read_text(encoding="utf-8") == "x = 99  # only copy\n"


def test_an_index_flag_set_after_the_assessment_keeps_the_worktree(repo: Path, tmp_path: Path) -> None:
    """Fold A, re-assessment: the flag check runs again right before removal."""
    worktree, _ = _land_by_rebase(repo, "land-x")
    probe = _idle_probe(tmp_path)
    assessment = assess_worktrees(repo, current_dir=repo, probe=probe)
    assert _by_path(assessment, worktree).removable
    _git(worktree, "update-index", "--skip-worktree", "src.py")
    (worktree / "src.py").write_text("late\n", encoding="utf-8")

    [outcome] = prune_landed(repo, current_dir=repo, probe=probe, assessment=assessment)

    assert not outcome.removed
    assert outcome.refusal == Reason.UNCOMMITTED_CHANGES
    assert worktree.exists()


@pytest.mark.parametrize("git_entry", ["dir", "file"])
def test_a_nested_repository_in_an_ignored_directory_is_kept(repo: Path, tmp_path: Path, git_entry: str) -> None:
    """Fold B: a nested repo inside an ignored path can hold commits that exist nowhere else."""
    worktree, _ = _land_by_rebase(repo, "land-x")
    nested = worktree / ".venv" / "src" / "pkg"
    nested.mkdir(parents=True)
    if git_entry == "dir":
        _git(nested, "init", "-q")
    else:
        (nested / ".git").write_text("gitdir: /elsewhere\n", encoding="utf-8")

    verdict = _by_path(assess_worktrees(repo, current_dir=repo, probe=_idle_probe(tmp_path)), worktree)

    assert (verdict.verdict, verdict.reason) == (Verdict.NOT_LANDED, Reason.NESTED_REPOSITORY)
    assert ".venv/" in verdict.detail
    assert prune_landed(repo, current_dir=repo, probe=_idle_probe(tmp_path)) == []
    assert nested.exists()


@pytest.mark.parametrize("store", ["bare-clone", "separate-git-dir", "hg", "jj", "svn"])
def test_a_bare_or_renamed_repository_store_in_an_ignored_directory_is_kept(repo: Path, tmp_path: Path, store: str) -> None:
    """Fold B follow-up: a git dir not named ``.git`` (bare clone, ``--separate-git-dir``) or another VCS store is a nested repository."""
    worktree, _ = _land_by_rebase(repo, "land-x")
    vendor = worktree / ".venv" / "vendor"
    vendor.mkdir(parents=True)
    if store == "bare-clone":
        _git(vendor, "clone", "-q", "--bare", str(repo), "mirror.git")
    elif store == "separate-git-dir":
        work = tmp_path / "elsewhere-work"
        _git(tmp_path, "init", "-q", f"--separate-git-dir={vendor / 'x.gitdir'}", str(work))
    else:
        (vendor / "pkg" / f".{store}").mkdir(parents=True)
    assert not list(vendor.rglob(".git")), "non-vacuity: no entry is named .git"

    verdict = _by_path(assess_worktrees(repo, current_dir=repo, probe=_idle_probe(tmp_path)), worktree)

    assert (verdict.verdict, verdict.reason) == (Verdict.NOT_LANDED, Reason.NESTED_REPOSITORY)
    assert prune_landed(repo, current_dir=repo, probe=_idle_probe(tmp_path)) == []
    assert vendor.exists()


def test_a_directory_merely_named_like_git_parts_is_not_a_repository(repo: Path, tmp_path: Path) -> None:
    """Positive control: ``HEAD`` without ``objects/`` and ``refs/`` is not a git dir."""
    worktree, _ = _land_by_rebase(repo, "land-x")
    (worktree / ".venv" / "lib").mkdir(parents=True)
    (worktree / ".venv" / "lib" / "HEAD").write_text("x\n", encoding="utf-8")
    (worktree / ".venv" / "lib" / "refs").mkdir()

    assert _by_path(assess_worktrees(repo, current_dir=repo, probe=_idle_probe(tmp_path)), worktree).verdict is Verdict.LANDED


def test_ignored_paths_that_removal_deletes_are_listed(repo: Path, tmp_path: Path) -> None:
    """Fold H: count and up to five names of the ignored paths the removal deletes."""
    _git(repo, "rm", "-q", "--cached", ".gitignore")
    (repo / ".gitignore").write_text(".venv/\n*.log\n.env\n", encoding="utf-8")
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "-q", "-m", "ignore more")
    _git(repo, "push", "-q", "origin", "main")
    worktree, _ = _land_by_rebase(repo, "land-x")
    (worktree / ".venv").mkdir()
    (worktree / ".venv" / "x").write_text("x", encoding="utf-8")
    (worktree / ".env").write_text("SECRET=1\n", encoding="utf-8")
    for index in range(5):
        (worktree / f"run{index}.log").write_text("log\n", encoding="utf-8")

    verdict = _by_path(assess_worktrees(repo, current_dir=repo, probe=_idle_probe(tmp_path)), worktree)

    assert verdict.verdict is Verdict.LANDED
    assert verdict.ignored_count == 7
    assert verdict.ignored_paths == (".env", ".venv/", "run0.log", "run1.log", "run2.log")
    assert verdict.to_json()["ignored_count"] == 7
    assert verdict.to_json()["ignored_paths"] == [".env", ".venv/", "run0.log", "run1.log", "run2.log"]


def _detached_squash_landed(repo: Path) -> tuple[Path, str]:
    worktree = repo / ".worktrees" / "det"
    _git(repo, "worktree", "add", "-q", "--detach", str(worktree), "main")
    tip = _commit(worktree, "det.txt", "det\n")
    _git(repo, "merge", "-q", "--squash", tip)
    _git(repo, "commit", "-q", "-m", "squash det")
    _git(repo, "push", "-q", "origin", "main")
    return worktree, tip


def test_a_squash_landed_detached_tip_is_kept_under_a_discarded_ref(repo: Path, tmp_path: Path) -> None:
    """Fold D: no branch holds a squash-landed detached tip; record it before removal."""
    worktree, tip = _detached_squash_landed(repo)

    [outcome] = prune_landed(repo, current_dir=repo, probe=_idle_probe(tmp_path))

    assert outcome.removed and outcome.branch is None
    assert outcome.kept_ref == f"refs/spec-kitty/discarded/detached/{tip}"
    assert _rev(repo, outcome.kept_ref) == tip
    assert not worktree.exists()


def test_a_detached_tip_that_cannot_be_kept_keeps_the_worktree(repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    worktree, _ = _detached_squash_landed(repo)

    def refuse(repo_root: Path, sha: str, **_: object) -> str:
        raise DestructiveOpRefused(error_code=DESTRUCTIVE_OP_ONLY_COPY, remediation="cannot write")

    monkeypatch.setattr(landed_worktrees, "keep_detached_tip", refuse)

    [outcome] = prune_landed(repo, current_dir=repo, probe=_idle_probe(tmp_path))

    assert not outcome.removed
    assert outcome.refusal == DESTRUCTIVE_OP_ONLY_COPY
    assert worktree.exists() and _registered(repo, worktree)


@pytest.mark.parametrize("moved_by", ["created-only", "fast-forward-merge", "rebase"])
def test_a_branch_with_no_own_commits_is_report_only(repo: Path, tmp_path: Path, moved_by: str) -> None:
    """Fold E: a branch at a main commit was never worked on (made, or only moved onto main); do not delete it."""
    worktree = _worktree(repo, "idle")
    if moved_by != "created-only":
        _commit(repo, "later.txt", "later\n")
        _git(repo, "push", "-q", "origin", "main")
        _git(worktree, "fetch", "-q", "origin")
        if moved_by == "rebase":
            _git(worktree, "rebase", "-q", "origin/main")
        else:
            _git(worktree, "merge", "-q", "--ff-only", "origin/main")
        assert _rev(worktree, "HEAD") == _rev(repo, "main")
        newest = _git(repo, "reflog", "show", "--format=%gs", "refs/heads/idle").splitlines()[0]
        assert newest.startswith({"rebase": "rebase (finish)", "fast-forward-merge": "merge origin/main: Fast-forward"}[moved_by]), newest

    verdict = _by_path(assess_worktrees(repo, current_dir=repo, probe=_idle_probe(tmp_path)), worktree)

    assert (verdict.verdict, verdict.reason) == (Verdict.NOT_LANDED, Reason.NO_OWN_COMMITS)
    assert "no commits were made on this branch" in verdict.detail
    assert prune_landed(repo, current_dir=repo, probe=_idle_probe(tmp_path)) == []
    assert worktree.exists() and _has_branch(repo, "idle")


def test_a_branch_without_a_reflog_is_unproven(repo: Path, tmp_path: Path) -> None:
    """Fold E: no reflog, so whether commits were made on the branch cannot be told."""
    worktree = _worktree(repo, "nolog")
    _git(repo, "reflog", "delete", "--rewrite", "refs/heads/nolog@{0}")
    common = Path(_git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir").strip())
    (common / "logs" / "refs" / "heads" / "nolog").unlink(missing_ok=True)

    verdict = _by_path(assess_worktrees(repo, current_dir=repo, probe=_idle_probe(tmp_path)), worktree)

    assert (verdict.verdict, verdict.reason) == (Verdict.UNPROVEN, Reason.REFLOG_MISSING)
    assert worktree.exists()


def test_a_detached_worktree_outside_dot_worktrees_is_excluded(repo: Path, tmp_path: Path) -> None:
    """Fold F: spec-kitty's own scratch checkouts (kitty-merge-*, review baselines) are detached and live elsewhere."""
    worktree = tmp_path / "kitty-merge-scratch"
    _git(repo, "worktree", "add", "-q", "--detach", str(worktree), "main")

    verdict = _by_path(assess_worktrees(repo, current_dir=repo, probe=_idle_probe(tmp_path)), worktree)

    assert (verdict.verdict, verdict.reason) == (Verdict.EXCLUDED, Reason.DETACHED_OUTSIDE_WORKTREES)
    assert prune_landed(repo, current_dir=repo, probe=_idle_probe(tmp_path)) == []
    assert worktree.exists()


def test_an_unresolved_primary_branch_is_unproven(tmp_path: Path) -> None:
    """Fold J: no origin/HEAD and no common primary name -- the primary is only a guess (the current branch)."""
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "trunk", str(origin))
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "trunk")
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "T")
    _commit(root, "src.py", "x = 1\n")
    _git(root, "remote", "add", "origin", str(origin))
    _git(root, "push", "-q", "-u", "origin", "trunk")
    worktree, _ = _land_by_rebase_on(root, "land-x", "trunk")

    verdict = _by_path(assess_worktrees(root, current_dir=root, probe=_idle_probe(tmp_path)), worktree)

    assert (verdict.verdict, verdict.reason) == (Verdict.UNPROVEN, Reason.PRIMARY_UNRESOLVED)
    # Positive control: once origin/HEAD names it, the same worktree is landed.
    _git(root, "remote", "set-head", "origin", "trunk")
    assert _by_path(assess_worktrees(root, current_dir=root, probe=_idle_probe(tmp_path)), worktree).verdict is Verdict.LANDED


def _land_by_rebase_on(root: Path, branch: str, primary: str) -> tuple[Path, str]:
    worktree = _worktree(root, branch, start=primary)
    tip = _commit(worktree, f"{branch}.txt", f"{branch}\n")
    _git(root, "cherry-pick", tip)
    _git(root, "push", "-q", "origin", primary)
    return worktree, tip


def test_absorption_unsupported_is_unproven(repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fold I: a git without ``merge-tree --write-tree`` proves nothing."""
    worktree, _ = _land_by_rebase(repo, "land-x")

    def unsupported(*_: object, **__: object) -> bool:
        raise AbsorptionUnsupported("git too old")

    monkeypatch.setattr(landed_worktrees, "is_absorbed", unsupported)

    verdict = _by_path(assess_worktrees(repo, current_dir=repo, probe=_idle_probe(tmp_path)), worktree)

    assert (verdict.verdict, verdict.reason) == (Verdict.UNPROVEN, Reason.ABSORPTION_UNSUPPORTED)
    assert prune_landed(repo, current_dir=repo, probe=_idle_probe(tmp_path)) == []


def test_a_branch_checked_out_in_another_worktree_is_kept(repo: Path, tmp_path: Path) -> None:
    """Fold I: the worktree goes, the branch stays while another (locked) worktree has it checked out."""
    worktree, tip = _land_by_rebase(repo, "land-x")
    second = repo.parent / "wt-second"
    _git(repo, "worktree", "add", "-q", "--force", str(second), "land-x")
    _git(repo, "worktree", "lock", str(second))

    [outcome] = prune_landed(repo, current_dir=repo, probe=_idle_probe(tmp_path))

    assert outcome.removed and not outcome.branch_deleted
    assert outcome.refusal == Reason.BRANCH_IN_OTHER_WORKTREE
    assert not worktree.exists() and second.exists() and _has_branch(repo, "land-x")
    _git(repo, *shlex.split(outcome.recreate)[1:])  # git refuses a second checkout of land-x: the printed command must not need one
    assert _rev(worktree, "HEAD") == tip


def test_a_worktree_on_the_primary_branch_is_removed_and_the_branch_kept(repo: Path, tmp_path: Path) -> None:
    """The local primary branch is never deleted; the outcome says so and the recreate command puts the worktree back on it."""
    _git(repo, "switch", "-q", "-c", "side")
    worktree = repo / ".worktrees" / "primary"
    _git(repo, "worktree", "add", "-q", str(worktree), "main")
    tip = _rev(repo, "main")

    [outcome] = prune_landed(repo, current_dir=repo, probe=_idle_probe(tmp_path))

    assert (outcome.removed, outcome.branch_deleted, outcome.refusal) == (True, False, landed_worktrees.BRANCH_IS_PRIMARY)
    assert not worktree.exists() and _rev(repo, "main") == tip
    _git(repo, *shlex.split(outcome.recreate)[1:])
    assert _git(worktree, "branch", "--show-current").strip() == "main"


def test_a_stale_origin_ref_cannot_lose_a_rewritten_commit(repo: Path, tmp_path: Path) -> None:
    """Fold C end to end: the local origin/main still vouches for a commit force-pushed off the remote."""
    worktree = _worktree(repo, "st")
    tip = _commit(worktree, "st.txt", "st\n")
    _git(repo, "merge", "-q", "--ff-only", "st")
    _git(repo, "push", "-q", "origin", "main")
    _git(repo, "reset", "-q", "--hard", "HEAD~1")
    _git(repo, "push", "-q", "-f", "origin", "main:main")
    # Model a stale remote-tracking ref explicitly: whether a push updates it depends on the git version.
    _git(repo, "update-ref", "refs/remotes/origin/main", tip)
    assert _rev(repo, "refs/remotes/origin/main") == tip
    assert tip not in _git(repo, "ls-remote", "origin", "refs/heads/main")

    [outcome] = prune_landed(repo, current_dir=repo, probe=_idle_probe(tmp_path))

    assert outcome.removed and outcome.branch_deleted
    assert outcome.kept_ref == "refs/spec-kitty/discarded/st"
    assert _rev(repo, outcome.kept_ref) == tip


def test_a_worktree_with_a_submodule_is_refused_by_git(repo: Path, tmp_path: Path) -> None:
    """Fold I: git itself refuses to remove a worktree holding a submodule; recorded, nothing removed."""
    sub = _init(tmp_path / "subsrc")
    allow = ("-c", "protocol.file.allow=always")
    _git(repo, *allow, "submodule", "add", "-q", str(sub), "sub")
    _git(repo, "commit", "-q", "-m", "add submodule")
    _git(repo, "push", "-q", "origin", "main")
    worktree, _ = _land_by_rebase(repo, "land-x")
    _git(worktree, *allow, "submodule", "update", "-q", "--init")

    [outcome] = prune_landed(repo, current_dir=repo, probe=_idle_probe(tmp_path))

    assert not outcome.removed
    assert outcome.refusal == WORKTREE_REMOVE_REFUSED_BY_GIT
    assert (worktree / "sub" / "src.py").exists()


# ---------------------------------------------------------------------------
# Reflog reachability (#7211): a destroyed reflog must not orphan a commit
# ---------------------------------------------------------------------------

_RELOG_PREFIX = "refs/spec-kitty/discarded/reflog/"


def _reflog_refs(root: Path) -> list[str]:
    return [line for line in _git(root, "for-each-ref", "--format=%(refname)", _RELOG_PREFIX).splitlines() if line]


def _refs_holding(root: Path, sha: str) -> list[str]:
    return [line for line in _git(root, "for-each-ref", "--contains", sha, "--format=%(refname)").splitlines() if line]


def _expire_and_gc(root: Path) -> None:
    _git(root, "-c", "gc.reflogExpire=now", "-c", "gc.reflogExpireUnreachable=now", "gc", "--prune=now", "--quiet")


def _object_exists(root: Path, sha: str) -> bool:
    return subprocess.run(["git", "cat-file", "-e", f"{sha}^{{commit}}"], cwd=root, check=False, capture_output=True).returncode == 0


def _three_commit_rebase_landing(repo: Path) -> tuple[Path, list[str]]:
    """Three commits whose SHAs are rewritten onto ``main`` (this repository's landing style)."""
    worktree = _worktree(repo, "rebase3")
    shas = [_commit(worktree, f"r{index}.txt", f"r{index}\n") for index in range(3)]
    env = {**os.environ, "GIT_COMMITTER_DATE": _OLD_DATE}
    _git(repo, "cherry-pick", *shas, env=env)
    _git(repo, "push", "-q", "origin", "main")
    _git(repo, "fetch", "-q", "origin")
    assert not set(shas) & {_rev(repo, "refs/remotes/origin/main")}, "the fixture must rewrite the SHAs"
    return worktree, shas


def test_a_rebase_landing_keeps_no_reflog_ref(repo: Path, tmp_path: Path) -> None:
    """SC-003: the pre-rebase half of a landing is superseded, not lost, so nothing is recorded."""
    worktree, shas = _three_commit_rebase_landing(repo)

    [outcome] = prune_landed(repo, current_dir=repo, probe=_idle_probe(tmp_path))

    assert outcome.removed
    assert outcome.kept_commits == ()
    assert _reflog_refs(repo) == []
    # Positive control: the branch reflog really did hold three SHAs the primary
    # does not contain by ancestry, so the empty keep list is a decision about
    # them, not an empty candidate set. They stay reachable through the guard's
    # own tip record, which is not a reflog ref.
    for sha in shas:
        is_ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", sha, "refs/remotes/origin/main"], cwd=repo, check=False)
        assert is_ancestor.returncode != 0, f"{sha} must not be an ancestor of the primary"
    assert outcome.kept_ref == "refs/spec-kitty/discarded/rebase3", outcome.kept_ref
    assert _rev(repo, outcome.kept_ref or "") == shas[-1], "the guard's tip record is what keeps them"


def test_a_reflog_only_commit_is_recorded_once_and_survives_a_second_prune(repo: Path, tmp_path: Path) -> None:
    worktree = _worktree(repo, "detached-orphan")
    _commit(worktree, "landed.txt", "landed\n")
    _git(worktree, "checkout", "-q", "--detach")
    orphan = _commit(worktree, "orphan.txt", "orphan\n")
    _git(worktree, "switch", "-q", "detached-orphan")
    _git(repo, "merge", "-q", "--ff-only", "detached-orphan")
    _git(repo, "push", "-q", "origin", "main")
    _git(repo, "fetch", "-q", "origin")

    [outcome] = prune_landed(repo, current_dir=repo, probe=_idle_probe(tmp_path))
    assert outcome.kept_commits == (f"{_RELOG_PREFIX}{orphan}",)
    _expire_and_gc(repo)
    assert _object_exists(repo, orphan), "the record must survive an aggressive gc"

    assert prune_landed(repo, current_dir=repo, probe=_idle_probe(tmp_path)) == []
    assert _rev(repo, f"{_RELOG_PREFIX}{orphan}") == orphan, "a second prune must not move the record"


def test_a_reflog_commit_that_cannot_be_recorded_keeps_the_worktree(repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SC-004: the record step is load-bearing; without it the prune removes nothing."""
    worktree = _worktree(repo, "detached-orphan")
    _commit(worktree, "landed.txt", "landed\n")
    _git(worktree, "checkout", "-q", "--detach")
    orphan = _commit(worktree, "orphan.txt", "orphan\n")
    _git(worktree, "switch", "-q", "detached-orphan")
    _git(repo, "merge", "-q", "--ff-only", "detached-orphan")
    _git(repo, "push", "-q", "origin", "main")
    _git(repo, "fetch", "-q", "origin")

    def refuse(repo_root: Path, sha: str, **_: object) -> str:
        assert sha == orphan, "the refusal must be for the reflog-only commit"
        raise DestructiveOpRefused(error_code=DESTRUCTIVE_OP_ONLY_COPY, remediation="cannot write")

    monkeypatch.setattr(landed_worktrees, "keep_reflog_tip", refuse)

    [outcome] = prune_landed(repo, current_dir=repo, probe=_idle_probe(tmp_path))

    assert not outcome.removed
    assert outcome.refusal == DESTRUCTIVE_OP_ONLY_COPY
    assert worktree.exists() and _registered(repo, worktree)
    assert _has_branch(repo, "detached-orphan")


def test_the_prune_never_contacts_a_remote(repo: Path, tmp_path: Path) -> None:
    """NFR-001: origin points at a path that does not exist, and the prune still removes."""
    worktree, _ = _three_commit_rebase_landing(repo)
    _git(repo, "remote", "set-url", "origin", str(tmp_path / "gone.git"))

    [outcome] = prune_landed(repo, current_dir=repo, probe=_idle_probe(tmp_path))

    assert outcome.removed, "the prune reads local refs only; an unreachable origin URL must not matter"
    assert not worktree.exists()


def test_reachability_keeps_only_the_candidates_no_ref_reaches(repo: Path, tmp_path: Path) -> None:
    """The rule itself: `rev-list <shas> --not --all`, intersected with the candidates."""
    worktree = _worktree(repo, "reflog-rule")
    reached = _commit(worktree, "reached.txt", "reached\n")
    _git(worktree, "checkout", "-q", "--detach")
    orphan = _commit(worktree, "orphan.txt", "orphan\n")
    _git(worktree, "switch", "-q", "reflog-rule")

    assert landed_worktrees._unreachable_after_prune(repo, [reached, orphan]) == [orphan]
    assert landed_worktrees._unreachable_after_prune(repo, []) == []


def test_a_reflog_only_commit_whose_patch_is_on_the_primary_is_not_recorded(repo: Path, tmp_path: Path) -> None:
    """The patch narrowing, non-vacuously: the commit is unreachable but its patch is not lost."""
    worktree = _worktree(repo, "same-patch")
    _commit(worktree, "landed.txt", "landed\n")
    _git(worktree, "checkout", "-q", "--detach")
    orphan = _commit(worktree, "same.txt", "same\n")
    _git(worktree, "switch", "-q", "same-patch")
    _git(worktree, "cherry-pick", orphan, env={**os.environ, "GIT_COMMITTER_DATE": _OLD_DATE})
    tip = _rev(worktree, "HEAD")
    assert tip != orphan, "the fixture must land the patch as a different commit"
    _git(repo, "merge", "-q", "--ff-only", "same-patch")
    _git(repo, "push", "-q", "origin", "main")
    _git(repo, "fetch", "-q", "origin")

    [outcome] = prune_landed(repo, current_dir=repo, probe=_idle_probe(tmp_path))

    assert outcome.removed
    assert outcome.kept_commits == (), "a patch that is already on the primary is superseded, not lost"
    assert _refs_holding(repo, orphan) == [], "nothing reached it, and nothing needed to"


def _merge_with_unique_content(repo: Path) -> tuple[Path, str]:
    """A landed branch whose *reflog* holds a merge carrying an edit no patch on the primary covers.

    Both parents' patches land on ``main`` (so every non-merge commit between the
    primary and the merge reads ``-`` in ``git cherry``), while the merge itself
    was committed with one further edit that exists nowhere else.
    """
    worktree = _worktree(repo, "merge-only")
    _commit(worktree, "landed.txt", "landed\n")
    _git(repo, "checkout", "-q", "-b", "other-side", "main")
    side = _commit(repo, "g.txt", "g\n")
    _git(repo, "checkout", "-q", "main")
    branch = _commit(worktree, "f.txt", "f\n")
    _git(worktree, "merge", "--no-commit", "--no-ff", "other-side")
    _commit(worktree, "h.txt", "merge-only\n")  # the merge commit carries an edit of its own
    merge = _rev(worktree, "HEAD")
    assert _git(repo, "rev-list", "--merges", "-n1", merge).strip(), "the merge must be a merge commit"
    _git(worktree, "reset", "-q", "--hard", branch)  # the merge now lives only in the reflog
    _git(repo, "merge", "-q", "--ff-only", "merge-only")
    _git(repo, "cherry-pick", side)  # the other parent's patch lands too, under a new SHA
    _git(repo, "push", "-q", "origin", "main")
    _git(repo, "fetch", "-q", "origin")
    main = _git(repo, "rev-list", "refs/remotes/origin/main")
    assert merge not in main and _git(repo, "cherry", "refs/remotes/origin/main", merge).count("+ ") == 0, (
        "the fixture must leave the merge's own edit uncovered while every non-merge patch reads '-'"
    )
    assert "h.txt" not in _git(repo, "ls-tree", "--name-only", "refs/remotes/origin/main")
    return worktree, merge


def test_a_merge_whose_resolution_exists_nowhere_else_is_recorded(repo: Path, tmp_path: Path) -> None:
    """Review finding: git cherry omits merges, so all `-` patches never prove a merge's content."""
    worktree, merge = _merge_with_unique_content(repo)

    [outcome] = prune_landed(repo, current_dir=repo, probe=_idle_probe(tmp_path))

    assert outcome.removed
    assert outcome.kept_ref is None, "the landed tip needs no ref, so everything else is at risk"
    assert f"{_RELOG_PREFIX}{merge}" in outcome.kept_commits, outcome.kept_commits
    _expire_and_gc(repo)
    assert _object_exists(repo, merge), "a merge's own resolution is carried by no patch"
