"""The one owner of merge, revert and squash conclusions (#5443, FR-013, C-005).

An automatic commit records exactly the paths the operation wrote, and
``safe_commit`` enforces that with an explicit path list. A merge, revert,
cherry-pick or squash *conclusion* cannot take a pathspec, because git commits
the whole in-progress index. Every such conclusion in ``src/`` therefore goes
through this module, and the commit-scope gate
(``tests/architectural/test_commit_scope_owner.py``) exempts only
:func:`run_committing_op` and :func:`conclude_in_progress_op`, by symbol.

The design relies on these git behaviours (verified on 2026-10-07 and pinned by
``tests/git_ops/test_merge_conclusion_owner.py``):

1. ``git merge --no-commit --no-edit -m MSG <b>`` followed by
   ``git commit --no-edit`` records ``MSG``: ``MERGE_MSG`` carries the ``-m``.
2. While ``MERGE_HEAD`` exists, ``git commit -m x -- <path>`` fails with
   "cannot do a partial commit during a merge". A conclusion cannot be
   path-scoped, so it needs an owner rather than a pathspec rule.
3. ``git merge --no-commit`` on a fast-forwardable branch fast-forwards and
   leaves no ``MERGE_HEAD``.
4. A committing ``git merge`` refuses to start over an unrelated staged file.
5. ``git merge --squash`` on a fast-forwardable branch *accepts* an unrelated
   staged file and keeps it staged, so the squash commit would sweep it in. A
   squash is concluded only in a worktree proven fresh (:class:`FreshWorktree`):
   linked, detached, and with an index that matches HEAD. Untracked files and
   unstaged edits are allowed, because ``commit -m`` never commits them.
6. A committing ``git revert`` refuses over an unrelated staged file, while
   ``revert --no-commit`` and ``cherry-pick --no-commit`` accept it. A
   committing revert is never rewritten into ``--no-commit`` plus a conclusion,
   because that would weaken git's own guard; :func:`run_committing_op` refuses
   ``--no-commit``.
7. ``git commit --amend --only --no-edit --allow-empty -- r`` amends only
   ``r``. That path-scoped amend needs no owner (C-005's recorded exception).
8. Concluding with ``git commit`` runs ``pre-commit``, ``commit-msg`` and
   ``post-commit``; a committing ``git merge`` runs ``pre-merge-commit``,
   ``commit-msg`` and ``post-merge``. Committing merges and reverts keep their
   exact argv and are only *run by* :func:`run_committing_op`, so the operator's
   hooks see what they saw before. Nothing here passes ``--no-verify``.

``env`` is always explicit: callers pass their pipeline's environment, and
``None`` means "inherit" (the lifecycle rollback inherits today). This module
never reads ``os.environ``.
"""

from __future__ import annotations

import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from kernel.git import GitCommandError, status_entries

__all__ = [
    "MergeConclusionRefused",
    "conclude_in_progress_op",
    "mint_fresh_worktree",
    "run_committing_op",
]

Env = Mapping[str, str] | None

#: The committing operations :func:`run_committing_op` may run.
COMMITTING_OPS = frozenset({"merge", "revert"})

# Arguments that would turn a committing op into a non-committing one, skip hooks, or
# conclude something this call did not start.
_REFUSED_ARGS = frozenset({"--no-verify", "--no-commit", "-n", "--squash", "--continue"})
_HOOKS_PATH_KEY = "core.hookspath="
_IN_PROGRESS_REFS = (("merge", "MERGE_HEAD"), ("revert", "REVERT_HEAD"), ("cherry-pick", "CHERRY_PICK_HEAD"))
_SQUASH = "squash"
_SQUASH_MSG = "SQUASH_MSG"
_MINTED = object()


class MergeConclusionRefused(RuntimeError):
    """The owner refused to commit; the message names the worktree and the reason."""

    def __init__(self, worktree: Path, reason: str) -> None:
        self.worktree = worktree
        self.reason = reason
        super().__init__(f"merge conclusion refused in {worktree}: {reason}")


@dataclass(frozen=True)
class FreshWorktree:
    """Proof that *worktree* was a detached, linked worktree at *head* with nothing staged.

    Only :func:`mint_fresh_worktree` can create one. A squash conclusion
    requires it, because ``git merge --squash`` keeps unrelated staged files
    (git fact 5).
    """

    worktree: Path
    head: str
    _minted: object = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._minted is not _MINTED:
            raise TypeError("FreshWorktree is minted only by mint_fresh_worktree()")


def _gpg_prefix(disable_gpgsign: bool) -> list[str]:
    return ["-c", "commit.gpgsign=false"] if disable_gpgsign else []


def _run_git(worktree: Path, args: Sequence[str], env: Env, *, disable_gpgsign: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *_gpg_prefix(disable_gpgsign), *args],
        cwd=str(worktree),
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def _git_output(worktree: Path, args: Sequence[str], env: Env) -> str:
    result = _run_git(worktree, args, env)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise MergeConclusionRefused(worktree, f"git {' '.join(args)} failed: {detail}")
    return result.stdout.strip()


def _git_path(worktree: Path, args: Sequence[str], env: Env) -> Path:
    """A path git prints (relative to *worktree* unless absolute), resolved."""
    printed = Path(_git_output(worktree, args, env))
    return (printed if printed.is_absolute() else worktree / printed).resolve()


def _head(worktree: Path, env: Env) -> str:
    return _git_output(worktree, ["rev-parse", "--verify", "HEAD"], env)


def _detect_op(worktree: Path, env: Env) -> str | None:
    for op, ref in _IN_PROGRESS_REFS:
        if _run_git(worktree, ["rev-parse", "-q", "--verify", ref], env).returncode == 0:
            return op
    if _git_path(worktree, ["rev-parse", "--git-path", _SQUASH_MSG], env).exists():
        return _SQUASH
    return None


def mint_fresh_worktree(worktree: Path, env: Env) -> FreshWorktree:
    """Prove *worktree* is a linked, detached worktree whose index matches HEAD.

    Only the index counts. ``git merge --squash`` followed by ``commit -m``
    commits staged content alone, so an untracked file or an unstaged edit
    (for example one an operator ``post-checkout`` hook writes when the merge
    worktree is created) can never reach the squash commit, while anything
    already staged would (git fact 5). An unstaged edit to a path the squash
    touches is refused by ``git merge --squash`` itself.

    Raises:
        MergeConclusionRefused: naming the failed condition (and the staged paths).
    """
    if _git_path(worktree, ["rev-parse", "--git-dir"], env) == _git_path(worktree, ["rev-parse", "--git-common-dir"], env):
        raise MergeConclusionRefused(worktree, "not a linked worktree (this is the repository's primary checkout)")
    if _run_git(worktree, ["symbolic-ref", "-q", "HEAD"], env).returncode == 0:
        raise MergeConclusionRefused(worktree, "HEAD is on a branch; a fresh merge worktree is detached")
    try:
        entries = status_entries(worktree, untracked="no", env=env)
    except GitCommandError as exc:
        raise MergeConclusionRefused(worktree, f"cannot read the worktree status: {exc}") from exc
    staged = [entry for entry in entries if entry.index != " "]
    if staged:
        raise MergeConclusionRefused(worktree, "index differs from HEAD: " + ", ".join(str(entry.path) for entry in staged))
    return FreshWorktree(worktree=worktree, head=_head(worktree, env), _minted=_MINTED)


def _require_fresh(worktree: Path, fresh: FreshWorktree | None, env: Env) -> None:
    if fresh is None:
        raise MergeConclusionRefused(worktree, "a squash conclusion needs a FreshWorktree proof (git merge --squash keeps unrelated staged files)")
    if fresh.worktree.resolve() != worktree.resolve():
        raise MergeConclusionRefused(worktree, f"the FreshWorktree proof was minted for {fresh.worktree}")
    head = _head(worktree, env)
    if head != fresh.head:
        raise MergeConclusionRefused(worktree, f"HEAD moved from {fresh.head} to {head} after the FreshWorktree proof was minted")


def run_committing_op(
    worktree: Path,
    op: str,
    args: Sequence[str],
    *,
    env: Env,
    disable_gpgsign: bool,
) -> subprocess.CompletedProcess[str]:
    """Run ``git [-c commit.gpgsign=false] <op> <args...>`` in *worktree*, a merge or revert that commits.

    The argv is the caller's own, unchanged; git itself refuses to start over an
    unrelated staged file (git facts 4 and 6). The completed process is returned
    for the caller's existing returncode and abort handling.

    Raises:
        MergeConclusionRefused: before any subprocess, for an unknown *op*, empty
            or string *args*, or an argument that would skip hooks
            (``--no-verify``, ``-c core.hooksPath=``) or stop the op from
            committing (``--no-commit``, ``-n``, ``--squash``, ``--continue``).
    """
    if op not in COMMITTING_OPS:
        raise MergeConclusionRefused(worktree, f"unsupported operation {op!r}; expected one of {sorted(COMMITTING_OPS)}")
    if isinstance(args, str) or not args:
        raise MergeConclusionRefused(worktree, f"git {op} needs a non-empty argument list, got {args!r}")
    refused = [arg for arg in args if arg in _REFUSED_ARGS or arg.lower().startswith(_HOOKS_PATH_KEY)]
    if refused:
        raise MergeConclusionRefused(worktree, f"git {op} may not run with {refused}")
    return _run_git(worktree, [op, *args], env, disable_gpgsign=disable_gpgsign)


def conclude_in_progress_op(
    worktree: Path,
    *,
    env: Env,
    message: str | None = None,
    fresh: FreshWorktree | None = None,
    disable_gpgsign: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Commit the merge, revert, cherry-pick or squash in progress in *worktree*.

    Runs ``git [-c commit.gpgsign=false] commit --no-edit`` (or ``-m message``):
    never ``-a``, ``--no-verify``, a pathspec or ``--allow-empty``. A squash
    (``SQUASH_MSG`` present, no ``*_HEAD``) also requires *fresh*, minted for
    this worktree at its current HEAD. The completed process is returned; a
    rejecting hook leaves the op in progress for the caller's abort path.

    Raises:
        MergeConclusionRefused: nothing is in progress, *message* is empty, or a
            squash has no matching :class:`FreshWorktree`.
    """
    if message is not None and not message.strip():
        raise MergeConclusionRefused(worktree, "an explicit commit message must not be empty")
    op = _detect_op(worktree, env)
    if op is None:
        raise MergeConclusionRefused(worktree, "no merge, revert, cherry-pick or squash is in progress")
    if op == _SQUASH:
        _require_fresh(worktree, fresh, env)
    if message is None:
        return _run_git(worktree, ["commit", "--no-edit"], env, disable_gpgsign=disable_gpgsign)
    return _run_git(worktree, ["commit", "-m", message], env, disable_gpgsign=disable_gpgsign)
