"""Compare-and-swap discipline for :func:`advance_branch_ref` (WP02 / FR-003).

The forward merge advance must move ``refs/heads/<branch>`` with a real
compare-and-swap ``git update-ref <ref> <new> <expected_old>`` (3-arg), the
same discipline the rollback path :func:`restore_branch_ref` already uses. The
old 2-arg ``git update-ref <ref> <new>`` was guarded only by a non-atomic
``merge-base --is-ancestor`` precheck: a concurrent writer moving the ref
between that precheck and the write would be silently clobbered (#4996).

These are real-git tests over throwaway temp repositories. ``_run_git`` is
wrapped only to *observe* the argv git is actually invoked with (and, in the
race test, to move the ref out-of-band inside the read→write window); the git
subprocess itself is never mocked.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from specify_cli.git import ref_advance
from specify_cli.git.ref_advance import RefAdvanceError, advance_branch_ref

# Real-git tests over throwaway temp repos that shell out to the git binary via
# subprocess -- git_repo for the real-repo tier, non_sandbox because the tests
# invoke the git subprocess directly (mirrors the sibling git/merge suites).
pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]


def _git(cwd: Path, *args: str) -> str:
    """Run a real git command in *cwd*, returning trimmed stdout."""
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _init_repo(root: Path) -> None:
    _git(root, "init", "--quiet")
    _git(root, "config", "user.email", "cas@example.com")
    _git(root, "config", "user.name", "CAS Test")
    _git(root, "config", "commit.gpgsign", "false")


def _commit(root: Path, filename: str, content: str, message: str) -> str:
    (root / filename).write_text(content, encoding="utf-8")
    _git(root, "add", filename)
    _git(root, "commit", "--quiet", "-m", message)
    return _git(root, "rev-parse", "HEAD")


def _ref_value(root: Path, branch: str) -> str:
    return _git(root, "rev-parse", f"refs/heads/{branch}")


def _update_ref_argvs(calls: list[list[str]]) -> list[list[str]]:
    """The recorded ``git`` argv lists that are ``update-ref`` invocations."""
    return [args for args in calls if args and args[0] == "update-ref"]


@pytest.fixture
def spy_run_git(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[Callable[[list[str]], None] | None], list[list[str]]]:
    """Install a ``_run_git`` spy, returning the list of recorded argv lists.

    The spy delegates to the real ``_run_git`` (git actually runs); it only
    records the ``args`` list of each call. An optional ``on_call`` hook fires
    with the argv *before* each delegation so a test can perturb repository
    state (e.g. an out-of-band ref move) inside a specific window.
    """
    recorded: list[list[str]] = []
    real_run_git = ref_advance._run_git

    def _install(on_call: Callable[[list[str]], None] | None = None) -> list[list[str]]:
        def _spy(
            cwd: Path,
            args: list[str],
            *,
            env: dict[str, str] | None = None,
        ) -> subprocess.CompletedProcess[str]:
            recorded.append(list(args))
            if on_call is not None:
                on_call(args)
            return real_run_git(cwd, args, env=env)

        monkeypatch.setattr(ref_advance, "_run_git", _spy)
        return recorded

    return _install


def test_advance_issues_three_arg_cas_argv(
    tmp_path: Path,
    spy_run_git: Callable[[Callable[[list[str]], None] | None], list[list[str]]],
) -> None:
    """Happy path: the write is a 3-arg CAS naming the expected old OID."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    old_sha = _commit(repo, "a.txt", "one", "c0")
    _git(repo, "branch", "target", old_sha)
    new_sha = _commit(repo, "a.txt", "two", "c1")  # FF descendant of old_sha

    recorded = spy_run_git(None)

    advance_branch_ref(repo, "target", new_sha, expected_old_sha=old_sha)

    assert _ref_value(repo, "target") == new_sha

    update_refs = _update_ref_argvs(recorded)
    assert update_refs == [["update-ref", "refs/heads/target", new_sha, old_sha]], (
        f"advance must issue exactly one 3-arg (4-token) CAS update-ref, got {update_refs!r}"
    )
    # Guard against regression to the non-atomic 2-arg form.
    for argv in update_refs:
        assert len(argv) == 4, f"update-ref must be 3-arg CAS, got 2-arg: {argv!r}"


def test_advance_fails_closed_when_ref_moves_between_read_and_write(
    tmp_path: Path,
    spy_run_git: Callable[[Callable[[list[str]], None] | None], list[list[str]]],
) -> None:
    """A concurrent ref move in the read→write window fails the advance closed.

    The advance reads the old value up front, passes the FF precheck, then a
    concurrent writer moves the ref. The CAS write must fail (git returns
    non-zero because on-disk != expected), :class:`RefAdvanceError` is raised,
    and the ref is left at the concurrent writer's value -- never clobbered to
    ``new_sha``, never overwritten by a 2-arg fallback or a retry.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    old_sha = _commit(repo, "a.txt", "one", "c0")
    _git(repo, "branch", "target", old_sha)
    concurrent_sha = _commit(repo, "a.txt", "rival", "concurrent")  # FF from old_sha
    new_sha = _commit(repo, "a.txt", "mine", "advance-target")  # FF from concurrent

    def _move_ref_once(args: list[str]) -> None:
        # Fire just before the CAS write: simulate a concurrent writer that has
        # advanced the ref since ``advance_branch_ref`` read ``old_sha``.
        # ``worktree list`` is the first ``_run_git`` call after the FF precheck
        # (the tree/status listings run through ``kernel.git``, outside the spy).
        if args and args[0] == "worktree" and _ref_value(repo, "target") == old_sha:
            _git(repo, "update-ref", "refs/heads/target", concurrent_sha, old_sha)

    recorded = spy_run_git(_move_ref_once)

    with pytest.raises(RefAdvanceError):
        advance_branch_ref(repo, "target", new_sha, expected_old_sha=old_sha)

    # Fail-closed: the concurrent writer's value is preserved, not clobbered.
    assert _ref_value(repo, "target") == concurrent_sha
    assert _ref_value(repo, "target") != new_sha

    # Every update-ref the advance issued was a 3-arg CAS: no 2-arg fallback,
    # and exactly one advance-owned CAS attempt (no retry-to-clobber).
    advance_writes = [argv for argv in _update_ref_argvs(recorded) if argv[1:3] == ["refs/heads/target", new_sha]]
    assert advance_writes == [["update-ref", "refs/heads/target", new_sha, old_sha]], (
        f"advance must attempt exactly one 3-arg CAS and never retry or fall back to a 2-arg write, got {advance_writes!r}"
    )


def test_advance_without_expected_old_falls_back_to_observed_value(
    tmp_path: Path,
    spy_run_git: Callable[[Callable[[list[str]], None] | None], list[list[str]]],
) -> None:
    """Interim default (WP06 not yet wired): CAS on the observed old value.

    When no ``expected_old_sha`` is threaded, the write is still a 3-arg CAS --
    it uses the value observed at entry -- so existing merge call sites keep
    working atomically until WP06 passes the transaction-start value. It must
    never degrade to an unconditional 2-arg overwrite.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    old_sha = _commit(repo, "a.txt", "one", "c0")
    _git(repo, "branch", "target", old_sha)
    new_sha = _commit(repo, "a.txt", "two", "c1")

    recorded = spy_run_git(None)

    advance_branch_ref(repo, "target", new_sha)

    assert _ref_value(repo, "target") == new_sha
    update_refs = _update_ref_argvs(recorded)
    assert update_refs == [["update-ref", "refs/heads/target", new_sha, old_sha]], (
        f"the interim default must still issue a 3-arg CAS on the observed old value, got {update_refs!r}"
    )


def test_commit_advance_uses_parent_cas_without_hard_resync(
    tmp_path: Path,
    spy_run_git: Callable[[Callable[[list[str]], None] | None], list[list[str]]],
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    old_sha = _commit(repo, "a.txt", "one", "c0")
    _git(repo, "branch", "target", old_sha)
    new_sha = _commit(repo, "a.txt", "two", "c1")
    _git(repo, "checkout", "--quiet", "target")

    recorded = spy_run_git(None)

    ref_advance.advance_branch_ref_for_commit(
        repo,
        repo,
        "target",
        new_sha,
        expected_old_sha=old_sha,
        message="safe commit",
    )

    assert _ref_value(repo, "target") == new_sha
    assert _update_ref_argvs(recorded) == [["update-ref", "-m", "safe commit", "refs/heads/target", new_sha, old_sha]]
    assert not any(args[:2] == ["reset", "--hard"] for args in recorded)


def test_commit_advance_fails_closed_when_parent_ref_moves_before_cas(
    tmp_path: Path,
    spy_run_git: Callable[[Callable[[list[str]], None] | None], list[list[str]]],
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    old_sha = _commit(repo, "a.txt", "one", "c0")
    _git(repo, "branch", "target", old_sha)
    _git(repo, "branch", "concurrent", old_sha)
    _git(repo, "branch", "candidate", old_sha)

    _git(repo, "checkout", "--quiet", "concurrent")
    concurrent_sha = _commit(repo, "rival.txt", "rival", "concurrent")
    _git(repo, "checkout", "--quiet", "candidate")
    new_sha = _commit(repo, "mine.txt", "mine", "candidate")
    _git(repo, "checkout", "--quiet", "target")

    def move_target_before_cas(args: list[str]) -> None:
        if args and args[0] == "update-ref":
            _git(repo, "update-ref", "refs/heads/target", concurrent_sha, old_sha)

    recorded = spy_run_git(move_target_before_cas)

    with pytest.raises(RefAdvanceError):
        ref_advance.advance_branch_ref_for_commit(
            repo,
            repo,
            "target",
            new_sha,
            expected_old_sha=old_sha,
            message="safe commit",
        )

    assert _ref_value(repo, "target") == concurrent_sha
    advance_writes = [args for args in _update_ref_argvs(recorded) if args[-2:] == [new_sha, old_sha]]
    assert advance_writes == [["update-ref", "-m", "safe commit", "refs/heads/target", new_sha, old_sha]]


def test_commit_advance_refuses_a_second_checked_out_target_worktree(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    old_sha = _commit(repo, "a.txt", "one", "c0")
    _git(repo, "branch", "target", old_sha)
    _git(repo, "branch", "candidate", old_sha)
    _git(repo, "checkout", "--quiet", "candidate")
    new_sha = _commit(repo, "candidate.txt", "candidate", "candidate")
    _git(repo, "checkout", "--quiet", "target")

    other_worktree = tmp_path / "other-worktree"
    _git(repo, "worktree", "add", "--quiet", "--detach", str(other_worktree), old_sha)
    _git(other_worktree, "symbolic-ref", "HEAD", "refs/heads/target")

    checkouts = [line for line in _git(repo, "worktree", "list", "--porcelain").splitlines() if line == "branch refs/heads/target"]
    assert len(checkouts) == 2, "test setup must expose two worktrees on the target branch"

    with pytest.raises(RefAdvanceError, match="other worktree"):
        ref_advance.advance_branch_ref_for_commit(
            repo,
            repo,
            "target",
            new_sha,
            expected_old_sha=old_sha,
            message="safe commit",
        )

    assert _ref_value(repo, "target") == old_sha


def test_commit_advance_refuses_when_target_is_not_checked_out_in_reconciled_worktree(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    old_sha = _commit(repo, "a.txt", "one", "c0")
    _git(repo, "branch", "target", old_sha)
    _git(repo, "branch", "candidate", old_sha)
    _git(repo, "checkout", "--quiet", "candidate")
    new_sha = _commit(repo, "candidate.txt", "candidate", "candidate")

    with pytest.raises(RefAdvanceError, match="not checked out"):
        ref_advance.advance_branch_ref_for_commit(
            repo,
            repo,
            "target",
            new_sha,
            expected_old_sha=old_sha,
            message="safe commit",
        )

    assert _ref_value(repo, "target") == old_sha


def test_resync_failure_after_a_successful_cas_raises_ref_resync_error(
    tmp_path: Path,
    spy_run_git: Callable[[Callable[[list[str]], None] | None], list[list[str]]],
) -> None:
    """Slice-10 F1: the ref MOVED (our CAS won) but the checkout resync failed.

    The caller must be able to tell this from a CAS refusal (another actor moved
    the ref): :class:`RefResyncError` is a :class:`RefAdvanceError` subclass, the
    ref is at ``new_sha`` and the message still names the resync repair.
    """
    from specify_cli.git.ref_advance import RefResyncError

    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    old_sha = _commit(repo, "a.txt", "one", "c0")
    _git(repo, "checkout", "-q", "-b", "target")
    new_sha = _commit(repo, "a.txt", "two", "c1")
    _git(repo, "update-ref", "refs/heads/target", old_sha, new_sha)
    _git(repo, "reset", "-q", "--hard", "target")

    def _lock_index_on_cas(args: list[str]) -> None:
        if args and args[0] == "update-ref":
            (repo / ".git" / "index.lock").write_text("", encoding="utf-8")

    spy_run_git(_lock_index_on_cas)

    with pytest.raises(RefResyncError, match="failed to resync") as raised:
        advance_branch_ref(repo, "target", new_sha, expected_old_sha=old_sha)

    assert isinstance(raised.value, RefAdvanceError)
    assert _ref_value(repo, "target") == new_sha, "the CAS succeeded: the ref moved"
