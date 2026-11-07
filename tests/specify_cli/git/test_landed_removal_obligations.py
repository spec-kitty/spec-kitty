"""The proof obligations of a landed removal (ADR 2026-11-06-1, #7264), one test each.

Every test drives :func:`guarded_landed_removal` on a real repository with a
real remote, so the obligation is shown on git's own behaviour, not on a fake.
Each was run red against a guard with that one obligation's check removed.
"""

from __future__ import annotations

import os
import shlex
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from specify_cli.coordination.coherence import NothingIsResidue
from specify_cli.git import destructive_guard, ref_advance
from specify_cli.git.destructive_guard import (
    BRANCH_DELETE_REFUSED_BY_GIT,
    BRANCH_IS_PRIMARY,
    DESTRUCTIVE_OP_ONLY_COPY,
    BRANCH_TIP_MOVED,
    LANDING_REF_UNNAMED,
    MERGE_UNSAFE_WORKTREE_DIRTY,
    NOT_LANDED_ON_NAMED_REMOTE,
    PROCESS_IN_WORKTREE,
    PROCESS_PROOF_UNAVAILABLE,
    REFLOG_DISCARDED_REF_PREFIX,
    WORKTREE_REMOVE_REFUSED_BY_GIT,
    WORKTREE_TIP_MOVED,
    DestructiveOpRefused,
    LandedRemoval,
    LandedRemovalResult,
    guarded_landed_removal,
    recreate_command,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_BRANCH = "land-x"
_ORIGIN_MAIN = "refs/remotes/origin/main"


def _git(cwd: Path, *args: str) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True, env=env).stdout


def _rev(cwd: Path, rev: str) -> str:
    return _git(cwd, "rev-parse", rev).strip()


def _commit(cwd: Path, name: str, body: str = "x\n") -> str:
    (cwd / name).write_text(body, encoding="utf-8")
    _git(cwd, "add", "--", name)
    _git(cwd, "commit", "-q", "-m", name)
    return _rev(cwd, "HEAD")


def _ref_exists(cwd: Path, ref: str) -> bool:
    return subprocess.run(["git", "rev-parse", "--verify", "--quiet", ref], cwd=cwd, capture_output=True).returncode == 0


def _object_exists(cwd: Path, sha: str) -> bool:
    return subprocess.run(["git", "cat-file", "-e", f"{sha}^{{commit}}"], cwd=cwd, capture_output=True).returncode == 0


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _commit(root, "base.txt")
    remote = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", str(remote))
    _git(root, "remote", "add", "origin", str(remote))
    _git(root, "push", "-q", "origin", "main")
    _git(root, "fetch", "-q", "origin")
    return root


def _land(repo: Path, branch: str = _BRANCH) -> tuple[Path, str]:
    """A worktree on ``branch`` with one commit, merged into main and pushed: landed on origin/main."""
    worktree = repo / ".worktrees" / branch
    _git(repo, "worktree", "add", "-q", "-b", branch, str(worktree), "main")
    tip = _commit(worktree, f"{branch}.txt")
    _git(repo, "merge", "-q", "--ff-only", branch)
    _git(repo, "push", "-q", "origin", "main")
    _git(repo, "fetch", "-q", "origin")
    return worktree, tip


def _removal(worktree: Path, tip: str, *, branch: str | None = _BRANCH, remote: str = "origin", landing_ref: str = _ORIGIN_MAIN) -> LandedRemoval:
    return LandedRemoval(worktree=worktree, branch=branch, tip=tip, remote=remote, landing_ref=landing_ref)


def _ancestor(repo: Path) -> Callable[[str, str], bool]:
    def absorbed(tip: str, ref: str) -> bool:
        return subprocess.run(["git", "merge-base", "--is-ancestor", tip, ref], cwd=repo, capture_output=True).returncode == 0

    return absorbed


def _remove(repo: Path, removal: LandedRemoval, *, busy: bool | None = False) -> LandedRemovalResult:
    return guarded_landed_removal(repo, removal, context=NothingIsResidue(), processes_in=lambda _path: busy, absorbed=_ancestor(repo))


def _refused(repo: Path, removal: LandedRemoval, *, busy: bool | None = False) -> str:
    with pytest.raises(DestructiveOpRefused) as info:
        _remove(repo, removal, busy=busy)
    assert removal.worktree.exists(), "a refusal before the removal removes nothing"
    return info.value.error_code


def test_the_happy_path_removes_the_worktree_and_deletes_the_branch(repo: Path) -> None:
    worktree, tip = _land(repo)

    result = _remove(repo, _removal(worktree, tip))

    assert not worktree.exists()
    assert result.branch_deleted and result.refusal is None
    assert not _ref_exists(repo, f"refs/heads/{_BRANCH}")


# O1 -- clean tree ------------------------------------------------------------


def test_o1_a_dirty_tree_is_refused(repo: Path) -> None:
    worktree, tip = _land(repo)
    (worktree / "notes.txt").write_text("only copy\n", encoding="utf-8")

    assert _refused(repo, _removal(worktree, tip)) == MERGE_UNSAFE_WORKTREE_DIRTY
    assert (worktree / "notes.txt").read_text(encoding="utf-8") == "only copy\n"


# O2 -- no live process -------------------------------------------------------


def test_o2_a_live_process_is_refused(repo: Path) -> None:
    worktree, tip = _land(repo)

    assert _refused(repo, _removal(worktree, tip), busy=True) == PROCESS_IN_WORKTREE


def test_o2_a_probe_that_cannot_tell_is_refused_not_passed(repo: Path) -> None:
    worktree, tip = _land(repo)

    assert _refused(repo, _removal(worktree, tip), busy=None) == PROCESS_PROOF_UNAVAILABLE


# O3 -- landed against a named remote -------------------------------------------


@pytest.mark.parametrize(
    ("remote", "landing_ref"),
    [
        ("upstream", "refs/remotes/upstream/main"),  # not a configured remote
        ("origin", "refs/heads/main"),  # a local branch is not a remote's proof
        ("origin", "refs/remotes/other/main"),  # the ref belongs to another remote
        ("", "refs/remotes//main"),  # a blank remote never falls back to origin
        ("origin", "refs/remotes/origin/gone"),  # named, but not fetched
    ],
)
def test_o3_the_landing_ref_must_be_a_configured_remotes_tracking_ref(repo: Path, remote: str, landing_ref: str) -> None:
    worktree, tip = _land(repo)
    _git(repo, "update-ref", "refs/remotes/other/main", tip)
    _git(repo, "update-ref", "refs/remotes/upstream/main", tip)  # the ref exists, so only "not configured" can refuse it

    assert _refused(repo, _removal(worktree, tip, remote=remote, landing_ref=landing_ref)) == LANDING_REF_UNNAMED


def test_o3_a_fork_clone_proves_against_the_remote_it_names(repo: Path, tmp_path: Path) -> None:
    """#7214: origin is a fork that never moves; the landing is on upstream, which the caller names."""
    worktree, tip = _land(repo)
    upstream = tmp_path / "upstream.git"
    _git(tmp_path, "clone", "-q", "--bare", str(tmp_path / "origin.git"), str(upstream))
    _git(repo, "remote", "add", "upstream", str(upstream))
    _git(repo, "fetch", "-q", "upstream")
    _git(repo, "update-ref", _ORIGIN_MAIN, f"{tip}~1")  # the fork's main is behind: no proof there

    assert _refused(repo, _removal(worktree, tip)) == NOT_LANDED_ON_NAMED_REMOTE

    result = _remove(repo, _removal(worktree, tip, remote="upstream", landing_ref="refs/remotes/upstream/main"))
    assert result.branch_deleted and not worktree.exists()


def test_o3_the_absorption_proof_is_rerun_at_destruction_time(repo: Path) -> None:
    worktree, tip = _land(repo)
    _git(repo, "update-ref", _ORIGIN_MAIN, f"{tip}~1")  # the remote ref was rewound since the assessment

    assert _refused(repo, _removal(worktree, tip)) == NOT_LANDED_ON_NAMED_REMOTE


# O4 -- reflog-only commits are kept --------------------------------------------


def _expire_and_collect(repo: Path) -> None:
    _git(repo, "-c", "gc.reflogExpire=now", "-c", "gc.reflogExpireUnreachable=now", "reflog", "expire", "--expire=now", "--expire-unreachable=now", "--all")
    _git(repo, "gc", "-q", "--prune=now")


def test_o4_a_commit_only_the_worktree_head_reflog_reached_survives_gc(repo: Path) -> None:
    worktree, _ = _land(repo)
    _git(worktree, "checkout", "-q", "--detach")
    orphan = _commit(worktree, "detached-work.txt")
    _git(worktree, "switch", "-q", _BRANCH)
    tip = _rev(worktree, "HEAD")

    result = _remove(repo, _removal(worktree, tip))
    _expire_and_collect(repo)

    assert result.kept_commits == (f"{REFLOG_DISCARDED_REF_PREFIX}{orphan}",)
    assert _object_exists(repo, orphan), "the reflog-only commit must outlive the prune and a gc"


def test_o4_a_remote_tracking_ref_does_not_vouch_for_a_reflog_only_commit(repo: Path) -> None:
    """Operator ruling 2026-11-06: only local refs keep a commit alive; a remote-tracking ref can be rewritten by the next fetch."""
    worktree, _ = _land(repo)
    _git(worktree, "checkout", "-q", "--detach")
    orphan = _commit(worktree, "pushed-elsewhere.txt")
    _git(repo, "push", "-q", "origin", f"{orphan}:refs/heads/side")
    _git(repo, "fetch", "-q", "origin")
    _git(worktree, "switch", "-q", _BRANCH)
    assert _rev(repo, "refs/remotes/origin/side") == orphan

    result = _remove(repo, _removal(worktree, _rev(worktree, "HEAD")))

    assert f"{REFLOG_DISCARDED_REF_PREFIX}{orphan}" in result.kept_commits


def test_o4_a_record_that_cannot_be_written_removes_nothing(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    worktree, _ = _land(repo)
    _git(worktree, "checkout", "-q", "--detach")
    _commit(worktree, "detached-work.txt")
    _git(worktree, "switch", "-q", _BRANCH)
    monkeypatch.setattr(ref_advance, "write_bookkeeping_ref", lambda *_a, **_k: False)

    assert _refused(repo, _removal(worktree, _rev(worktree, "HEAD"))) == DESTRUCTIVE_OP_ONLY_COPY
    assert _ref_exists(repo, f"refs/heads/{_BRANCH}")


# O5 -- compare-and-swap --------------------------------------------------------


def test_o5_a_worktree_that_moved_after_the_proof_is_refused(repo: Path) -> None:
    worktree, tip = _land(repo)
    _commit(worktree, "late.txt")

    assert _refused(repo, _removal(worktree, tip)) == WORKTREE_TIP_MOVED


def test_o5_a_branch_moved_while_the_delete_runs_is_kept(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    worktree, tip = _land(repo)
    real = ref_advance.delete_branch_ref
    moved: list[str] = []

    def move_then_delete(repo_root: Path, branch: str, expected_sha: str, *, env: dict[str, str] | None = None) -> None:
        _git(repo, "branch", "-f", branch, "main~1")
        moved.append(_rev(repo, branch))
        real(repo_root, branch, expected_sha, env=env)

    monkeypatch.setattr(ref_advance, "delete_branch_ref", move_then_delete)

    result = _remove(repo, _removal(worktree, tip))

    assert not worktree.exists()
    assert (result.branch_deleted, result.refusal) == (False, BRANCH_TIP_MOVED)
    assert moved and _rev(repo, _BRANCH) == moved[0], "the moved branch must survive"


# O6 -- rebase-merged SHAs ------------------------------------------------------


def test_o6_the_pre_rebase_half_of_a_rebase_landing_is_not_recorded(repo: Path) -> None:
    """The pre-rebase commit is reachable from nothing, but replaying it onto the landing ref changes nothing."""
    worktree = repo / ".worktrees" / _BRANCH
    _git(repo, "worktree", "add", "-q", "-b", _BRANCH, str(worktree), "main")
    pre_rebase = _commit(worktree, "feature.txt")
    _commit(repo, "other.txt")  # main moved on, so the landing is a real rebase
    _git(worktree, "rebase", "-q", "main")
    tip = _rev(worktree, "HEAD")
    assert tip != pre_rebase
    _git(repo, "merge", "-q", "--ff-only", _BRANCH)
    _git(repo, "push", "-q", "origin", "main")
    _git(repo, "fetch", "-q", "origin")

    result = _remove(repo, _removal(worktree, tip))

    assert result.kept_commits == (), "a superseded, patch-equivalent commit is not lost and needs no record"


def test_o6_a_reflog_only_commit_whose_patch_is_not_on_the_ref_is_recorded(repo: Path) -> None:
    """Negative control: the same reflog shape with a patch that never landed keeps its record."""
    worktree, _ = _land(repo)
    dropped = _commit(worktree, "dropped.txt")
    _git(worktree, "reset", "-q", "--hard", "HEAD~1")

    result = _remove(repo, _removal(worktree, _rev(worktree, "HEAD")))

    assert result.kept_commits == (f"{REFLOG_DISCARDED_REF_PREFIX}{dropped}",)


def _dropped_commit(repo: Path, worktree: Path, *, name: str, body: str | None) -> str:
    """A commit made in ``worktree`` and dropped with ``reset --hard``: only the reflogs still reach it."""
    if body is None:
        _git(worktree, "commit", "-q", "--allow-empty", "-m", name)
        dropped = _rev(worktree, "HEAD")
    else:
        dropped = _commit(worktree, name, body)
    _git(worktree, "reset", "-q", "--hard", "HEAD~1")
    return dropped


def _land_on_main(repo: Path, *, name: str, body: str | None) -> None:
    if body is None:
        _git(repo, "commit", "-q", "--allow-empty", "-m", name)
    else:
        _commit(repo, name, body)
    _git(repo, "push", "-q", "origin", "main")
    _git(repo, "fetch", "-q", "origin")


def test_o6_a_change_that_differs_only_in_whitespace_is_not_proof(repo: Path) -> None:
    """Squad finding: `git cherry`'s patch-id ignores whitespace, so an indented line read as landed and was lost."""
    worktree, _ = _land(repo)
    dropped = _dropped_commit(repo, worktree, name="f.py", body="def f():\n    print(1)\n")
    _land_on_main(repo, name="f.py", body="def f():\nprint(1)\n")

    result = _remove(repo, _removal(worktree, _rev(worktree, "HEAD")))

    assert result.kept_commits == (f"{REFLOG_DISCARDED_REF_PREFIX}{dropped}",)


def test_o6_an_empty_commit_is_never_proof(repo: Path) -> None:
    """An empty commit carries only its message; an unrelated empty commit on the ref does not prove it landed."""
    worktree, _ = _land(repo)
    dropped = _dropped_commit(repo, worktree, name="design note", body=None)
    _land_on_main(repo, name="unrelated empty", body=None)

    result = _remove(repo, _removal(worktree, _rev(worktree, "HEAD")))

    assert result.kept_commits == (f"{REFLOG_DISCARDED_REF_PREFIX}{dropped}",)


# O7 -- never --force -----------------------------------------------------------


def test_o7_a_locked_worktree_is_left_to_gits_own_refusal(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    worktree, tip = _land(repo)
    _git(repo, "worktree", "lock", str(worktree))
    argv: list[list[str]] = []
    real = destructive_guard._run_git

    def recording(cwd: Path, args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        argv.append(list(args))
        return real(cwd, args, **kwargs)

    monkeypatch.setattr(destructive_guard, "_run_git", recording)

    assert _refused(repo, _removal(worktree, tip)) == WORKTREE_REMOVE_REFUSED_BY_GIT
    assert ["worktree", "remove", "--", str(worktree)] in argv
    assert not any("--force" in args or "-f" in args for args in argv)


# O8 -- a recreate hint -----------------------------------------------------------


def test_o8_the_recreate_hint_brings_the_branch_back_at_its_tip(repo: Path) -> None:
    worktree, tip = _land(repo)

    result = _remove(repo, _removal(worktree, tip))
    _git(repo, *shlex.split(result.recreate)[1:])

    assert _rev(repo, _BRANCH) == tip


def test_o8_a_kept_branch_gets_its_worktree_back(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    worktree, tip = _land(repo)

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise ref_advance.RefDeleteError("refused")

    monkeypatch.setattr(ref_advance, "delete_branch_ref", refuse)

    result = _remove(repo, _removal(worktree, tip))
    _git(repo, *shlex.split(result.recreate)[1:])

    assert (result.refusal, result.branch_deleted) == (BRANCH_DELETE_REFUSED_BY_GIT, False)
    assert _git(worktree, "branch", "--show-current").strip() == _BRANCH


def test_o8_a_detached_worktree_comes_back_detached_at_its_tip(repo: Path) -> None:
    worktree, tip = _land(repo)
    _git(worktree, "checkout", "-q", "--detach")

    result = _remove(repo, _removal(worktree, tip, branch=None))
    assert result.recreate == recreate_command(worktree, None, tip, branch_kept=False)
    _git(repo, *shlex.split(result.recreate)[1:])

    assert _rev(worktree, "HEAD") == tip


def test_the_local_copy_of_the_landing_branch_is_never_deleted(repo: Path) -> None:
    """The worktree on local ``main`` may go; the branch the landing is proven against stays."""
    _git(repo, "switch", "-q", "-c", "dev")
    worktree = repo / ".worktrees" / "main"
    _git(repo, "worktree", "add", "-q", str(worktree), "main")
    tip = _rev(worktree, "HEAD")

    result = _remove(repo, _removal(worktree, tip, branch="main"))

    assert not worktree.exists()
    assert (result.branch_deleted, result.refusal) == (False, BRANCH_IS_PRIMARY)
    assert _rev(repo, "main") == tip
    _git(repo, *shlex.split(result.recreate)[1:])  # the pruned worktree held the primary, so nothing else has it checked out
    assert _git(worktree, "branch", "--show-current").strip() == "main"


# Squad follow-ups (pre-PR adversarial review) -------------------------------------


def test_o4_a_commit_only_the_branch_reflog_reached_survives_gc(repo: Path) -> None:
    """The branch half of O4: the commit is in the branch reflog and in no worktree's HEAD reflog."""
    worktree, tip = _land(repo)
    scratch = repo.parent / "scratch"
    _git(repo, "worktree", "add", "-q", "--detach", str(scratch), tip)
    orphan = _commit(scratch, "branch-only.txt")
    _git(repo, "worktree", "remove", str(scratch))
    _git(repo, "update-ref", "-m", "moved by hand", f"refs/heads/{_BRANCH}", orphan)
    _git(repo, "update-ref", "-m", "moved back", f"refs/heads/{_BRANCH}", tip)
    assert orphan not in _git(worktree, "reflog", "show", "--format=%H", "HEAD").split()

    result = _remove(repo, _removal(worktree, tip))
    _expire_and_collect(repo)

    assert result.kept_commits == (f"{REFLOG_DISCARDED_REF_PREFIX}{orphan}",)
    assert _object_exists(repo, orphan)


def test_o4_a_commit_only_the_remote_landing_ref_reaches_is_still_recorded(repo: Path) -> None:
    """Pushed to origin/main but on no local ref: the remote-tracking ref does not vouch (empty range is no proof)."""
    worktree, _ = _land(repo)
    dropped = _dropped_commit(repo, worktree, name="pushed.txt", body="pushed\n")
    _git(repo, "push", "-q", "origin", f"{dropped}:refs/heads/main")
    _git(repo, "fetch", "-q", "origin")

    result = _remove(repo, _removal(worktree, _rev(worktree, "HEAD")))

    assert f"{REFLOG_DISCARDED_REF_PREFIX}{dropped}" in result.kept_commits


def test_o4_an_unreadable_reflog_removes_nothing(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    worktree, tip = _land(repo)
    real = destructive_guard._run_git

    def reflog_fails(cwd: Path, args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if args[:2] == ["reflog", "show"]:
            return subprocess.CompletedProcess(args, 128, "", "fatal: corrupt reflog")
        return real(cwd, args, **kwargs)

    monkeypatch.setattr(destructive_guard, "_run_git", reflog_fails)

    assert _refused(repo, _removal(worktree, tip)) == DESTRUCTIVE_OP_ONLY_COPY


def test_o4_a_reflog_that_cannot_be_opened_removes_nothing(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``git reflog show`` exits 0 on a file it can't open, so the guard must read the file itself."""
    worktree, tip = _land(repo)
    real_read_bytes = Path.read_bytes

    def denied(path: Path) -> bytes:
        if path.name == "HEAD" and path.parent.name == "logs":
            raise PermissionError(13, "Permission denied", str(path))
        return real_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", denied)

    assert _refused(repo, _removal(worktree, tip)) == DESTRUCTIVE_OP_ONLY_COPY
    assert worktree.exists()


def test_o4_a_corrupt_branch_reflog_removes_nothing(repo: Path) -> None:
    """Branch reflogs live in the common directory, not the worktree's own git directory."""
    worktree, tip = _land(repo)
    branch = _git(worktree, "symbolic-ref", "--short", "HEAD").strip()
    (repo / ".git" / "logs" / "refs" / "heads" / branch).write_text("not a reflog\n", encoding="utf-8")

    assert _refused(repo, _removal(worktree, tip)) == DESTRUCTIVE_OP_ONLY_COPY
    assert worktree.exists()


def test_o4_a_corrupt_reflog_removes_nothing(repo: Path) -> None:
    """On a file it can't parse, ``git reflog show`` exits 0 and prints the current commit."""
    worktree, tip = _land(repo)
    log = Path(_git(worktree, "rev-parse", "--path-format=absolute", "--git-path", "logs/HEAD").strip())
    log.write_text("not a reflog\n", encoding="utf-8")

    assert _refused(repo, _removal(worktree, tip)) == DESTRUCTIVE_OP_ONLY_COPY
    assert worktree.exists()


def test_o4_reachability_that_git_cannot_answer_keeps_every_candidate(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    real = destructive_guard._run_git

    def rev_list_fails(cwd: Path, args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if args[:2] == ["rev-list", "--stdin"]:
            return subprocess.CompletedProcess(args, 128, "", "fatal")
        return real(cwd, args, **kwargs)

    monkeypatch.setattr(destructive_guard, "_run_git", rev_list_fails)
    head = _rev(repo, "HEAD")

    assert destructive_guard._unreached_by_local_refs(repo, [head], None) == [head]


def test_o5_a_commit_made_during_the_slow_checks_is_caught_before_the_removal(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The window between the first tip check and the removal: a detached worktree has no branch delete to refuse."""
    worktree, tip = _land(repo)
    _git(worktree, "checkout", "-q", "--detach")
    real = destructive_guard._keep_before_removal
    late: list[str] = []

    def keep_then_commit(repo_root: Path, removal: LandedRemoval, env: dict[str, str] | None) -> tuple[str | None, tuple[str, ...]]:
        kept = real(repo_root, removal, env)
        late.append(_commit(worktree, "late.txt"))
        return kept

    monkeypatch.setattr(destructive_guard, "_keep_before_removal", keep_then_commit)

    assert _refused(repo, _removal(worktree, tip, branch=None)) == WORKTREE_TIP_MOVED
    assert late and _rev(worktree, "HEAD") == late[0]


def test_o5_a_worktree_list_failure_in_the_delete_keeps_the_branch(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    worktree, tip = _land(repo)

    def cannot_list(*_args: object, **_kwargs: object) -> None:
        raise ref_advance.RefAdvanceError("worktree list failed")

    monkeypatch.setattr(ref_advance, "delete_branch_ref", cannot_list)

    result = _remove(repo, _removal(worktree, tip))

    assert (result.branch_deleted, result.refusal) == (False, BRANCH_DELETE_REFUSED_BY_GIT)
    assert _rev(repo, _BRANCH) == tip


def test_o5_a_branch_already_gone_is_not_a_refusal(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    worktree, tip = _land(repo)
    real = destructive_guard._remove_worktree

    def remove_then_drop_branch(path: Path, env: dict[str, str] | None, *, force: bool) -> None:
        real(path, env, force=force)
        _git(repo, "branch", "-D", _BRANCH)

    monkeypatch.setattr(destructive_guard, "_remove_worktree", remove_then_drop_branch)

    result = _remove(repo, _removal(worktree, tip))

    assert (result.branch_deleted, result.refusal) == (False, None)
    assert result.recreate == recreate_command(worktree, _BRANCH, tip, branch_kept=False)


def test_o8_the_recreate_hint_is_quoted_for_cmd_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(destructive_guard, "is_windows", lambda: True)

    hint = recreate_command(Path("C:/work/my tree"), "land-x", "abc123", branch_kept=True)

    assert hint == 'git worktree add "C:/work/my tree" land-x'
