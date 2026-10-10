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
standard library. Disposability is decided from a caller-supplied CONTEXT
(``coordination.coherence.ResidueContext``, structurally a
:class:`ref_advance.ResidueClassifier`): the caller says which checkout and
Mission it is destroying, and the guard asks the context whether each dirty
path is regenerable residue (#5965 / #5966). This module
never imports the classifier itself (#1878 / #2795 / FR-012).

:class:`DestructiveOpRefused` is a NEW, distinct typed refusal. It must
never be conflated with
:class:`specify_cli.git.commit_helpers.SafeCommitHeadMismatch`, which has
several downstream catchers whose semantics this mission does not touch
(C-002).
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from kernel.git import GitPath, status_entries

from . import ref_advance
from .ref_advance import ResidueClassifier

MERGE_UNSAFE_PRIMARY_OFF_TARGET = "MERGE_UNSAFE_PRIMARY_OFF_TARGET"
MERGE_UNSAFE_PRIMARY_DIRTY = "MERGE_UNSAFE_PRIMARY_DIRTY"
MERGE_UNSAFE_WORKTREE_DIRTY = "MERGE_UNSAFE_WORKTREE_DIRTY"
DESTRUCTIVE_OP_ONLY_COPY = "DESTRUCTIVE_OP_ONLY_COPY"
BRANCH_HAS_UNIQUE_COMMITS = "BRANCH_HAS_UNIQUE_COMMITS"

FORCE_RECREATE_INTENT = "force_recreate"
"""``operator_intent`` of ``mission create --force-recreate``: the operator asked for the branch to be discarded."""

_RESUME_NOTE = "then resume the operation (e.g. `spec-kitty consolidate --resume`)"


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
            entries = ref_advance.format_entry_lines(self.dirty_entries)
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
    stdin: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
        env=env,
        input=stdin,
    )


def _current_branch(repo_root: Path, env: dict[str, str] | None) -> str:
    """Reuse the rev-parse logic of ``merge/preflight._enforce_planning_artifact_target_branch``.

    Mirrored rather than imported: that function lives in
    ``specify_cli.consolidation.preflight`` (the application layer, not git
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
    context: ResidueClassifier,
    env: dict[str, str] | None = None,
    error_code: str = MERGE_UNSAFE_WORKTREE_DIRTY,
    treat_untracked_as_dirty: bool = False,
) -> None:
    """Raise :class:`DestructiveOpRefused` when ``worktree`` holds local state.

    Delegates to :func:`ref_advance._dirty_entries` (residue-aware,
    ``--ignored``, tree-obstruction, meta-lock exemption) with the injected
    ``context`` classifier — this module introduces no new, parallel
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

    ``context`` is required (the guard decides disposability from the checkout
    role, #5965 / #5966), so a missing context can never default to a
    destructive answer. It is applied to ``worktree`` as-is: the caller names
    the role of the checkout it guards.

    ``treat_untracked_as_dirty`` (#4753 Finding A): forwarded to
    :func:`ref_advance._dirty_entries` unchanged — see that function's
    docstring. Pass ``True`` for a worktree this call is guarding ahead of a
    ``git worktree remove --force`` (an untracked-only operator file there is
    destroyed by the removal, unlike a ``reset --hard``'s obstruction-only
    exposure). Defaults to ``False``.
    """
    target_paths: frozenset[GitPath] = ref_advance._target_tree_paths(worktree, new_sha, env) if new_sha else frozenset()
    dirty = ref_advance._dirty_entries(
        worktree,
        env,
        new_sha=new_sha or "HEAD",
        target_paths=target_paths,
        is_disposable=context.is_disposable,
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
        ["worktree", "remove", "--force", "--", str(worktree)],
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git worktree remove --force failed for {worktree}: {result.stderr.strip() or result.stdout.strip()}")


def guarded_worktree_remove(
    worktree: Path,
    *,
    retain: bool,
    context: ResidueClassifier,
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
            context=context,
            env=env,
            treat_untracked_as_dirty=True,
        )
        _remove_worktree_force(worktree, env)
        return RemoveResult(outcome=RemoveOutcome.REMOVED, worktree_path=worktree)

    dirty = ref_advance._dirty_entries(
        worktree,
        env,
        new_sha="HEAD",
        target_paths=frozenset(),
        is_disposable=context.is_disposable,
        treat_untracked_as_dirty=True,
    )
    if dirty:
        return RemoveResult(outcome=RemoveOutcome.RETAINED_DIRTY, worktree_path=worktree)

    _remove_worktree_force(worktree, env)
    return RemoveResult(outcome=RemoveOutcome.REMOVED, worktree_path=worktree)


def _git_ok(cwd: Path, args: list[str], env: dict[str, str] | None) -> str:
    result = _run_git(cwd, args, env=env)
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {cwd}: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout


def guarded_reset_hard(
    worktree: Path,
    target: str,
    *,
    context: ResidueClassifier,
    env: dict[str, str] | None = None,
) -> None:
    """``git reset --hard <target>`` in ``worktree``, refusing first when it would destroy the only copy.

    Tracked changes and any untracked path ``target`` would overwrite count as
    local state unless ``context`` proves them disposable. Nothing is mutated
    on refusal.
    """
    assert_worktree_clean(worktree, new_sha=target, context=context, env=env)
    _git_ok(worktree, ["reset", "--hard", target], env)


def _merge_owned_paths(worktree: Path, env: dict[str, str] | None) -> frozenset[str]:
    """Paths an in-progress merge itself touched (auto-merged or conflicted): ``merge --abort`` regenerates them."""
    if _run_git(worktree, ["rev-parse", "-q", "--verify", "MERGE_HEAD"], env=env).returncode != 0:
        return frozenset()
    base = _run_git(worktree, ["merge-base", "HEAD", "MERGE_HEAD"], env=env)
    if base.returncode != 0:
        return frozenset()
    changed = _run_git(worktree, ["diff", "--name-only", base.stdout.strip(), "MERGE_HEAD"], env=env)
    return frozenset(changed.stdout.split("\n")) - {""} if changed.returncode == 0 else frozenset()


def _stage_blob(worktree: Path, stage: int, path: str, env: dict[str, str] | None) -> bytes | None:
    """The bytes of ``path`` at index ``stage`` (1 base, 2 ours, 3 theirs), or ``None`` when that stage is absent."""
    result = subprocess.run(["git", "show", f":{stage}:{path}"], cwd=str(worktree), capture_output=True, check=False, env=env)
    return result.stdout if result.returncode == 0 else None


def _strip_conflict_markers(data: bytes) -> bytes:
    """``data`` without conflict-marker lines and without a diff3 base section.

    Marker labels and the conflict style differ between ``git merge`` and
    ``git merge-file`` (and with the operator's ``merge.conflictStyle``); the
    ours/theirs content between the markers does not.
    """
    kept: list[bytes] = []
    in_base = False
    for line in data.split(b"\n"):
        if line.startswith(b"|||||||"):
            in_base = True
        elif line.startswith(b"======="):
            in_base = False
        elif not in_base and not line.startswith((b"<<<<<<<", b">>>>>>>")):
            kept.append(line)
    return b"\n".join(kept)


def _git_conflict_result(worktree: Path, path: str, env: dict[str, str] | None) -> bytes | None:
    """The file as ``git merge`` leaves it for an unmerged ``path`` (markers included), or ``None`` when git cannot say."""
    ours, theirs = _stage_blob(worktree, 2, path, env), _stage_blob(worktree, 3, path, env)
    if ours is None or theirs is None:
        return ours if theirs is None else theirs
    base = _stage_blob(worktree, 1, path, env) or b""
    with tempfile.TemporaryDirectory() as scratch:
        files = [Path(scratch) / name for name in ("ours", "base", "theirs")]
        for file, blob in zip(files, (ours, base, theirs), strict=True):
            file.write_bytes(blob)
        merged = subprocess.run(["git", "merge-file", "-p", *(str(file) for file in files)], capture_output=True, check=False)
    return merged.stdout if merged.returncode >= 0 and merged.returncode < 128 else None


def _edited_conflicts(worktree: Path, env: dict[str, str] | None) -> list[str]:
    """Display lines for unmerged paths whose working-tree file differs from git's own conflict result (an operator edit)."""
    edited: list[str] = []
    for entry in status_entries(worktree, env=env):
        if not entry.is_conflicted:
            continue
        rel = str(entry.path)
        expected = _git_conflict_result(worktree, rel, env)
        file = worktree / rel
        actual = file.read_bytes() if file.is_file() else None
        if expected is None or actual is None or _strip_conflict_markers(actual) != _strip_conflict_markers(expected):
            edited.append(f"{entry.display()} (conflict resolution edited in the working tree)")
    return edited


def guarded_merge_abort(
    worktree: Path,
    *,
    context: ResidueClassifier,
    env: dict[str, str] | None = None,
) -> None:
    """``git merge --abort`` in ``worktree``, refusing when it would discard an operator's own edit.

    The merge's own results are regenerable and exempt: a cleanly merged path
    outright, a conflicted path only while its working-tree file still equals
    what git left (an operator's half-done resolution of it is refused). Every
    other local change is judged by ``context``.
    """
    merge_paths = _merge_owned_paths(worktree, env)
    dirty = ref_advance._dirty_entries(
        worktree,
        env,
        new_sha="HEAD",
        target_paths=frozenset(),
        is_disposable=lambda path: path in merge_paths or context.is_disposable(path),
    )
    dirty = [*dirty, *_edited_conflicts(worktree, env)]
    if dirty:
        raise DestructiveOpRefused(
            error_code=DESTRUCTIVE_OP_ONLY_COPY,
            worktree_path=worktree,
            dirty_entries=dirty,
            remediation=f"Commit, stash, or move the local changes in {worktree}, {_RESUME_NOTE}.",
        )
    _git_ok(worktree, ["merge", "--abort"], env)


def _prunable_paths_on_disk(repo_root: Path, env: dict[str, str] | None) -> list[str]:
    """Registered worktrees git marks prunable whose directory nevertheless exists."""
    listing = _git_ok(repo_root, ["worktree", "list", "--porcelain"], env)
    present: list[str] = []
    for block in listing.split("\n\n"):
        lines = block.strip().split("\n")
        path = next((line[len("worktree ") :] for line in lines if line.startswith("worktree ")), None)
        if path is not None and any(line.startswith("prunable") for line in lines) and Path(path).exists():
            present.append(path)
    return present


def guarded_worktree_prune(repo_root: Path, *, env: dict[str, str] | None = None) -> None:
    """``git worktree prune``, refusing when a registration it would drop still has a directory on disk."""
    present = _prunable_paths_on_disk(repo_root, env)
    if present:
        raise DestructiveOpRefused(
            error_code=DESTRUCTIVE_OP_ONLY_COPY,
            worktree_path=repo_root,
            dirty_entries=present,
            remediation="These registered worktrees still exist on disk; move or remove them deliberately, then re-run.",
        )
    _git_ok(repo_root, ["worktree", "prune"], env)


def _unique_commits(repo_root: Path, branch: str, extra_not: list[str], env: dict[str, str] | None) -> list[str]:
    """Commits on ``branch`` that no other local ref, remote ref or tag (and none of ``extra_not``) reaches."""
    own_ref = f"refs/heads/{branch}"
    refs = _git_ok(repo_root, ["for-each-ref", "--format=%(refname) %(objectname)", "refs/heads", "refs/remotes", "refs/tags"], env)
    others = [line.split(" ")[1] for line in refs.splitlines() if line and line.split(" ")[0] != own_ref]
    negated = "".join(f"^{rev}\n" for rev in [*others, *extra_not])
    result = _run_git(repo_root, ["rev-list", own_ref, "--stdin"], env=env, stdin=negated)
    if result.returncode != 0:
        raise RuntimeError(f"git rev-list failed in {repo_root}: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout.split()


def guarded_branch_delete(
    repo_root: Path,
    branch: str,
    *,
    creation_base: str | None,
    operator_intent: str | None = None,
    env: dict[str, str] | None = None,
) -> None:
    """``git branch -D <branch>``, refused while the branch holds commits that exist nowhere else (FR-009).

    Deletion is allowed when the branch has no commit beyond ``creation_base``
    or every commit is reachable from another ref. A branch that does not exist
    is a no-op.

    ``operator_intent`` names the one explicit request that skips the
    unique-commit check: :data:`FORCE_RECREATE_INTENT` (``mission create
    --force-recreate``, where the operator asked for the branch to be discarded).
    Any other value is a :class:`ValueError`. A routing gate pins the single
    caller allowed to pass it.
    """
    if operator_intent not in (None, FORCE_RECREATE_INTENT):
        raise ValueError(f"unknown operator_intent {operator_intent!r}; expected None or {FORCE_RECREATE_INTENT!r}")
    if _run_git(repo_root, ["rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"], env=env).returncode != 0:
        return
    if operator_intent is not None:
        _git_ok(repo_root, ["branch", "-D", "--", branch], env)
        return
    unique = _unique_commits(repo_root, branch, [], env)
    if unique and creation_base is not None:
        unique = _unique_commits(repo_root, branch, [creation_base], env)
    if unique:
        raise DestructiveOpRefused(
            error_code=BRANCH_HAS_UNIQUE_COMMITS,
            current_branch=branch,
            dirty_entries=[f"{sha[:12]} (only on {branch})" for sha in unique],
            remediation=f"Merge or keep branch {branch!r}; nothing was deleted.",
        )
    _git_ok(repo_root, ["branch", "-D", "--", branch], env)


def _make_writable_and_retry(function: Callable[[str], object], name: str, _exc: object) -> None:
    """``shutil.rmtree`` error hook (``onerror`` and ``onexc`` alike): clear a read-only bit (git objects on Windows) and retry once."""
    for target in (Path(name), Path(name).parent):
        os.chmod(target, stat.S_IRWXU)  # removal is governed by the parent's write bit on POSIX
    function(name)


def _rmtree_writable(path: Path) -> None:
    # ``onexc`` replaced the deprecated ``onerror`` in 3.12; the project floor is 3.11.
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_make_writable_and_retry)
    else:
        shutil.rmtree(path, onerror=_make_writable_and_retry)


def _checkout_toplevel(path: Path, env: dict[str, str] | None) -> Path | None:
    result = _run_git(path, ["rev-parse", "--show-toplevel"], env=env)
    return Path(result.stdout.strip()).resolve() if result.returncode == 0 else None


def _ignored_local_state(toplevel: Path, prefix: str, context: ResidueClassifier, env: dict[str, str] | None) -> list[str]:
    """Display lines for ignored files under ``prefix`` that ``context`` does not prove disposable.

    A directory that is not itself a checkout root lies in its enclosing
    checkout, where ``git status`` hides ignored entries (an ignored
    ``.worktrees/`` husk holding ``work.py`` looks clean). Nothing there is
    regenerable unless the classifier says so, so each ignored file counts.
    """
    entries = status_entries(toplevel, untracked="all", ignored=True, env=env)
    return [
        f"{entry.display()} (ignored by the enclosing checkout, so git status hides it)"
        for entry in entries
        if entry.is_ignored and str(entry.path).startswith(prefix) and not context.is_disposable(str(entry.path))
    ]


def guarded_tree_delete(
    path: Path,
    *,
    context: ResidueClassifier,
    env: dict[str, str] | None = None,
) -> None:
    """Delete directory ``path``, which is (or lies inside) a git checkout, unless that discards the only copy.

    Only local state under ``path`` counts. A path that is not inside a git
    checkout cannot be proven disposable here and is refused: use
    ``kernel.tree_removal.remove_tool_owned_tree`` for a tree the tool owns.
    A missing path is a no-op.
    """
    if not path.exists():
        return
    resolved = path.resolve()
    toplevel = _checkout_toplevel(resolved, env)
    if toplevel is None:
        raise DestructiveOpRefused(
            error_code=DESTRUCTIVE_OP_ONLY_COPY,
            worktree_path=path,
            dirty_entries=[str(path)],
            remediation="This directory is not a git checkout, so nothing proves it disposable; nothing was deleted.",
        )
    prefix = "" if resolved == toplevel else resolved.relative_to(toplevel).as_posix() + "/"
    dirty = ref_advance._dirty_entries(
        toplevel,
        env,
        new_sha="HEAD",
        target_paths=frozenset(),
        is_disposable=lambda rel: (not rel.startswith(prefix)) or context.is_disposable(rel),
        treat_untracked_as_dirty=True,
    )
    if prefix:
        dirty += _ignored_local_state(toplevel, prefix, context, env)
    if dirty:
        raise DestructiveOpRefused(
            error_code=DESTRUCTIVE_OP_ONLY_COPY,
            worktree_path=path,
            dirty_entries=dirty,
            remediation=f"Commit, stash, or move the local changes under {path}, {_RESUME_NOTE}.",
        )
    _rmtree_writable(path)
