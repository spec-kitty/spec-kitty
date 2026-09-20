"""Refuse-before-destroy guard primitive (mission #4752/#4753, WP01).

Merge and worktree cleanup previously forked roughly a dozen independent
dirty-worktree predicates across the codebase (the grounding squad found
~9). Each was a fresh chance to under-detect local state and let a
destructive git command (``reset --hard``, ``worktree remove --force``,
``merge --abort``) silently destroy uncommitted operator work. This module
is the ONE shared, git-plumbing-pure chokepoint (INV-3 / FR-007 / NFR-006):
every live destroy site routes through :func:`guarded_worktree_remove` (or
the narrower :func:`assert_checkout_on_target` /
:func:`assert_worktree_clean` assertions) instead of hand-rolling another
dirty check.

git-plumbing purity (C-005): this module imports **zero** ``specify_cli``
application modules or ``coordination.*`` — only its git-plumbing sibling
:mod:`specify_cli.git.ref_advance` (same layer, relative import) and the
standard library. The residue/churn classifier
(``coordination.coherence.is_toolchain_generated_churn``) is INJECTED by the
caller via the required ``is_residue`` keyword; this module never imports it
itself, mirroring the pattern ``ref_advance._dirty_entries`` already
established (#1878 / #2795 / FR-012).

:class:`DestructiveOpRefused` is a NEW, distinct typed refusal. It must
never be conflated with
:class:`specify_cli.git.commit_helpers.SafeCommitHeadMismatch`, which has
several downstream catchers whose semantics this mission does not touch
(C-002).
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from . import ref_advance

MERGE_UNSAFE_PRIMARY_OFF_TARGET = "MERGE_UNSAFE_PRIMARY_OFF_TARGET"
MERGE_UNSAFE_PRIMARY_DIRTY = "MERGE_UNSAFE_PRIMARY_DIRTY"
MERGE_UNSAFE_WORKTREE_DIRTY = "MERGE_UNSAFE_WORKTREE_DIRTY"

_RESUME_NOTE = "then resume the operation (e.g. `spec-kitty merge --resume`)"


class DestructiveOpRefused(Exception):
    """Pre-mutation refusal to run a destructive git operation.

    Raised BEFORE any destructive command (``reset --hard``,
    ``worktree remove --force``, ``merge --abort``) runs — the refusal
    itself is the invariant (NFR-001): on raise, nothing has mutated and the
    repository is byte-identical to before the call.

    Modeled on :class:`specify_cli.git.ref_advance.RefAdvanceDirtyWorktreeError`
    (``error_code`` + human message + remediation), but kept as a fully
    separate exception type — see the module docstring's C-002 note.
    """

    def __init__(
        self,
        *,
        error_code: str,
        remediation: str,
        worktree_path: Path | None = None,
        current_branch: str | None = None,
        expected_branch: str | None = None,
        dirty_entries: list[str] | None = None,
    ) -> None:
        self.error_code = error_code
        self.worktree_path = worktree_path
        self.current_branch = current_branch
        self.expected_branch = expected_branch
        self.dirty_entries = list(dirty_entries) if dirty_entries else []
        self.remediation = remediation
        super().__init__(self._build_message())

    def _build_message(self) -> str:
        lines = [f"Refusing destructive operation ({self.error_code})."]
        if self.worktree_path is not None:
            lines.append(f"  Worktree: {self.worktree_path}")
        if self.current_branch is not None or self.expected_branch is not None:
            lines.append(f"  Branch: currently on {self.current_branch!r}, expected {self.expected_branch!r}.")
        if self.dirty_entries:
            entries = "\n".join(f"    {entry}" for entry in self.dirty_entries)
            lines.append(f"  Dirty entries:\n{entries}")
        lines.append(f"  Remediation: {self.remediation}")
        return "\n".join(lines)


class RemoveOutcome(StrEnum):
    """Result bucket for :func:`guarded_worktree_remove` (contract: RemoveResult)."""

    REMOVED = "removed"
    RETAINED_DIRTY = "retained_dirty"


@dataclass(frozen=True)
class RemoveResult:
    """Outcome of a :func:`guarded_worktree_remove` call."""

    outcome: RemoveOutcome
    worktree_path: Path


def _run_git(
    cwd: Path,
    args: list[str],
    *,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def _current_branch(repo_root: Path, env: dict[str, str] | None) -> str:
    """Reuse the rev-parse logic of ``merge/preflight._enforce_planning_artifact_target_branch``.

    Mirrored rather than imported: that function lives in
    ``specify_cli.merge.preflight`` (the application layer, not git
    plumbing) and this module must not import it (C-005).
    """
    result = _run_git(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"], env=env)
    return result.stdout.strip() if result.returncode == 0 else ""


def assert_checkout_on_target(
    repo_root: Path,
    expected_branch: str,
    *,
    env: dict[str, str] | None = None,
) -> None:
    """Raise :class:`DestructiveOpRefused` when ``HEAD`` is off ``expected_branch``.

    No side effects; safe to call speculatively before any mutation.
    """
    current = _current_branch(repo_root, env)
    if current == expected_branch:
        return
    raise DestructiveOpRefused(
        error_code=MERGE_UNSAFE_PRIMARY_OFF_TARGET,
        worktree_path=repo_root,
        current_branch=current or None,
        expected_branch=expected_branch,
        remediation=(f"Checkout {expected_branch!r} in {repo_root} before retrying ({_RESUME_NOTE})."),
    )


def assert_worktree_clean(
    worktree: Path,
    *,
    new_sha: str | None = None,
    is_residue: Callable[[str], bool],
    env: dict[str, str] | None = None,
    error_code: str = MERGE_UNSAFE_WORKTREE_DIRTY,
    treat_untracked_as_dirty: bool = False,
) -> None:
    """Raise :class:`DestructiveOpRefused` when ``worktree`` holds local state.

    Delegates to :func:`ref_advance._dirty_entries` (residue-aware,
    ``--ignored``, tree-obstruction, meta-lock exemption) with the injected
    ``is_residue`` classifier — this module introduces no new, parallel
    dirty predicate (INV-3).

    ``new_sha`` is optional: when supplied, an untracked/ignored path that
    would be clobbered by resetting to ``new_sha`` is also treated as dirty
    (mirrors ``advance_branch_ref``'s obstruction check). When omitted, only
    tracked local changes (net of the injected residue exemption) count.

    ``error_code`` lets the caller pick the refusal vocabulary for its site:
    the default is the lane/coord ``MERGE_UNSAFE_WORKTREE_DIRTY``; the
    merge preflight passes ``MERGE_UNSAFE_PRIMARY_DIRTY`` when guarding the
    primary checkout (US1 AC2 / FR-002). The refusal semantics are identical;
    only the operator-facing code differs.

    ``treat_untracked_as_dirty`` (#4753 Finding A): forwarded to
    :func:`ref_advance._dirty_entries` unchanged — see that function's
    docstring. Pass ``True`` for a worktree this call is guarding ahead of a
    ``git worktree remove --force`` (an untracked-only operator file there is
    destroyed by the removal, unlike a ``reset --hard``'s obstruction-only
    exposure). Defaults to ``False``.
    """
    target_paths: set[str] = ref_advance._target_tree_paths(worktree, new_sha, env) if new_sha else set()
    dirty = ref_advance._dirty_entries(
        worktree,
        env,
        new_sha=new_sha or "HEAD",
        target_paths=target_paths,
        is_residue=is_residue,
        treat_untracked_as_dirty=treat_untracked_as_dirty,
    )
    if not dirty:
        return
    raise DestructiveOpRefused(
        error_code=error_code,
        worktree_path=worktree,
        dirty_entries=dirty,
        remediation=(f"Commit, stash, or revert the local changes in {worktree}, {_RESUME_NOTE}."),
    )


def _repo_root_for_worktree(worktree: Path, env: dict[str, str] | None) -> Path:
    """Resolve the primary repository root from a linked worktree.

    ``git worktree remove`` must run against the shared repository, not
    inside the worktree being removed. ``--git-common-dir`` resolves to the
    primary repo's ``.git`` directory from any linked worktree.
    """
    result = _run_git(
        worktree,
        ["rev-parse", "--path-format=absolute", "--git-common-dir"],
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Could not resolve the repository root for worktree {worktree}: {result.stderr.strip() or result.stdout.strip()}")
    return Path(result.stdout.strip()).parent


def _remove_worktree_force(worktree: Path, env: dict[str, str] | None) -> None:
    repo_root = _repo_root_for_worktree(worktree, env)
    result = _run_git(
        repo_root,
        ["worktree", "remove", str(worktree), "--force"],
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git worktree remove --force failed for {worktree}: {result.stderr.strip() or result.stdout.strip()}")


def guarded_worktree_remove(
    worktree: Path,
    *,
    retain: bool,
    is_residue: Callable[[str], bool],
    env: dict[str, str] | None = None,
) -> RemoveResult:
    """The shared removal chokepoint every live destroy site routes through.

    Runs :func:`assert_worktree_clean` unless ``retain`` is ``True``; on a
    clean worktree it performs the inline ``git worktree remove --force``;
    when ``retain`` is set and the worktree is dirty it KEEPS the worktree
    (no removal) and reports ``retained_dirty`` instead of raising. This is
    NOT ``core/vcs/git.py``'s ``remove_workspace`` (dead code, zero
    production callers) — it is the new single authority.

    Both dirty scans pass ``treat_untracked_as_dirty=True`` (#4753 Finding A):
    a removal — either branch — deletes the whole worktree directory tree, so
    an untracked-only operator file (never flagged by the obstruction-only
    default, which is correct only for a ``reset --hard``) must still be
    detected before it is destroyed.
    """
    if not retain:
        assert_worktree_clean(
            worktree,
            is_residue=is_residue,
            env=env,
            treat_untracked_as_dirty=True,
        )
        _remove_worktree_force(worktree, env)
        return RemoveResult(outcome=RemoveOutcome.REMOVED, worktree_path=worktree)

    dirty = ref_advance._dirty_entries(
        worktree,
        env,
        new_sha="HEAD",
        target_paths=set(),
        is_residue=is_residue,
        treat_untracked_as_dirty=True,
    )
    if dirty:
        return RemoveResult(outcome=RemoveOutcome.RETAINED_DIRTY, worktree_path=worktree)

    _remove_worktree_force(worktree, env)
    return RemoveResult(outcome=RemoveOutcome.REMOVED, worktree_path=worktree)
