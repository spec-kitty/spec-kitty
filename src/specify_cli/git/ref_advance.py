"""Branch ref advance with checked-out-worktree resync (#1826).

The merge pipeline advances ``refs/heads/<branch>`` via ``git update-ref``
from detached temporary worktrees. ``update-ref`` is plumbing: it bypasses
git's checked-out-branch protection and updates nothing in any worktree that
has the branch checked out. That worktree is left with an index/working tree
*behind its own HEAD* — the next safe-commit through it sees phantom staged
deletions, and a plain ``git commit`` from its stale index would silently
delete the advanced commits' files from the branch (#1826).

:func:`advance_branch_ref` is the single sanctioned way for the merge
pipeline to advance a branch ref. **Invariant: no worktree may be left
checked out behind a ref this function advanced.** An architectural ratchet
(``tests/architectural/test_merge_pipeline_ratchets.py``) enforces that no
raw ``update-ref`` subprocess invocation exists in ``src/specify_cli``
outside this module (AC-B3).

Locking: the three merge-pipeline call sites (``lanes/merge.py`` Stage-1
lane→mission advances and ``cli/commands/merge.py`` mission-number baking)
all run inside the global merge lock
(``acquire_merge_lock("__global_merge__", ...)``), which serializes every
merge operation. This helper therefore acquires NO lock of its own — adding
one would introduce a second lock ordering. Callers outside the merge
pipeline must hold an equivalent serialization guarantee.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

# Downward-only imports into the zero-dependency kernel root. ``ref_advance`` is
# git plumbing and must NOT import ``specify_cli`` (C-003, enforced by the
# NFR-004 ratchet in ``tests/architectural/test_layer_rules.py``); the kernel is
# the one layer reachable from both plumbing and application, so the malformed
# *definition* (``decode_meta``/``MetaDecodeError``) and the VCS-lock comparator
# (absent != present-but-null, C-005) live there and are consumed here.
from kernel.meta_decode import MetaDecodeError, decode_meta
from kernel.vcs_lock import is_vcs_lock_only_change

# Basename of the mission metadata file whose VCS-lock-only changes are tolerated.
_META_FILENAME: str = "meta.json"


class RefAdvanceError(RuntimeError):
    """A branch-ref advance failed at the git level (non-dirty cause)."""

    error_code = "REF_ADVANCE_FAILED"


class RefRestoreError(RuntimeError):
    """A compare-and-swap branch rollback failed at the git level."""

    error_code = "REF_RESTORE_FAILED"


class RefAdvanceNonFastForwardError(RefAdvanceError):
    """The requested ref advance would move a branch backwards or sideways."""

    error_code = "REF_ADVANCE_NON_FAST_FORWARD"

    def __init__(self, *, branch: str, old_sha: str, new_sha: str) -> None:
        self.branch = branch
        self.old_sha = old_sha
        self.new_sha = new_sha
        super().__init__(
            f"Refusing to advance branch {branch!r} ({old_sha[:12]} -> {new_sha[:12]}): target is not a fast-forward descendant of the current branch tip."
        )


@dataclass
class _WorktreeEntry:
    """One ``git worktree list --porcelain`` block."""

    path: Path
    branch: str | None = None
    detached: bool = False
    lines: list[str] = field(default_factory=list)


class RefAdvanceDirtyWorktreeError(RuntimeError):
    """A worktree with the advanced branch checked out holds local state.

    Raised BEFORE the ref is advanced and BEFORE any ``reset --hard`` runs
    (NFR-002: no silent data discard). Carries the full divergence context
    (NFR-003) so operators can resolve without forensic git archaeology.
    """

    error_code = "REF_ADVANCE_DIRTY_WORKTREE"

    def __init__(
        self,
        *,
        worktree_path: Path,
        branch: str,
        old_sha: str,
        new_sha: str,
        dirty_entries: list[str],
    ) -> None:
        self.worktree_path = worktree_path
        self.branch = branch
        self.old_sha = old_sha
        self.new_sha = new_sha
        self.dirty_entries = dirty_entries
        entries = "\n".join(f"    {entry}" for entry in dirty_entries)
        super().__init__(
            f"Refusing to advance branch {branch!r} "
            f"({old_sha[:12]} -> {new_sha[:12]}): the worktree at "
            f"{worktree_path} has it checked out and holds uncommitted local "
            f"changes that a resync (`git reset --hard`) would destroy "
            f"(#1826 / NFR-002).\n"
            f"  Dirty entries:\n{entries}\n"
            f"  Commit, stash, or revert these changes in {worktree_path}, "
            f"then resume the merge (`spec-kitty merge --resume`)."
        )


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


def _list_worktrees(repo_root: Path, env: dict[str, str] | None) -> list[_WorktreeEntry]:
    """Parse ``git worktree list --porcelain`` into entries."""
    result = _run_git(repo_root, ["worktree", "list", "--porcelain"], env=env)
    if result.returncode != 0:
        raise RefAdvanceError(f"Could not enumerate worktrees of {repo_root}: {result.stderr.strip() or result.stdout.strip()}")
    entries: list[_WorktreeEntry] = []
    current: _WorktreeEntry | None = None
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            current = _WorktreeEntry(path=Path(line.removeprefix("worktree ")))
            entries.append(current)
        elif current is not None and line.startswith("branch "):
            current.branch = line.removeprefix("branch ")
        elif current is not None and line == "detached":
            current.detached = True
    return entries


def _target_tree_paths(repo_root: Path, new_sha: str, env: dict[str, str] | None) -> set[str]:
    """Return tracked paths present at ``new_sha``."""
    result = _run_git(repo_root, ["ls-tree", "-r", "--name-only", new_sha], env=env)
    if result.returncode != 0:
        raise RefAdvanceError(f"Could not inspect target tree {new_sha}: {result.stderr.strip() or result.stdout.strip()}")
    return {line for line in result.stdout.splitlines() if line}


def _porcelain_path(line: str) -> str:
    """Extract the path field from a porcelain v1 status line."""
    path = line[3:]
    if " -> " in path:
        path = path.rsplit(" -> ", 1)[1]
    return path.rstrip("/")


def _path_obstructs_target_tree(path: str, target_paths: set[str]) -> bool:
    """Return True when an untracked/ignored path may be clobbered by reset."""
    if not path:
        return False
    prefix = f"{path}/"
    return any(target == path or target.startswith(prefix) for target in target_paths)


def _decode_meta_named(raw: str, *, source: str) -> dict[str, object]:
    """Decode ``meta.json`` *raw* content via the kernel L1, naming *source* on failure.

    :func:`kernel.meta_decode.decode_meta` owns the single malformed *definition*;
    its bare message does not name which file was unparseable. This plumbing
    caller owns the source-named message (mirroring L2's path-named contract) so
    a corrupt read fails loud identifying the ``meta.json`` blob (``HEAD:<path>``
    for a committed read, the filesystem path for a worktree read) instead of
    being silently absorbed (FR-003..FR-007).
    """
    try:
        parsed = decode_meta(raw, on_malformed="raise")
    except MetaDecodeError as exc:
        raise MetaDecodeError(f"Malformed meta.json at {source}: {exc}") from exc
    # ``on_malformed="raise"`` returns a mapping or raises; the ``None`` arm is
    # unreachable but keeps the return type total for mypy.
    return parsed if parsed is not None else {}


def _committed_meta_object(
    worktree: Path,
    path: str,
    env: dict[str, str] | None,
) -> dict[str, object]:
    """Return the ``meta.json`` object committed at ``HEAD:<path>``.

    Absent at HEAD (``git show`` returncode != 0, e.g. a newly added
    ``meta.json``) returns an empty dict -- so every working-copy key is treated
    as changed and a real file exceeds the lock set. A **present-but-unparseable**
    committed blob raises :class:`MetaDecodeError` naming ``HEAD:<path>`` (fail
    loud, FR-004/FR-006) instead of being silently absorbed.
    """
    result = _run_git(worktree, ["show", f"HEAD:{path}"], env=env)
    if result.returncode != 0:
        return {}
    return _decode_meta_named(result.stdout, source=f"HEAD:{path}")


def _meta_change_is_vcs_lock_only(
    worktree: Path,
    path: str,
    env: dict[str, str] | None,
) -> bool:
    """Whether the tracked-modified ``meta.json`` at ``path`` is a lock stamp.

    Decodes the working-copy object and the committed object through the kernel
    L1 and compares them with :func:`kernel.vcs_lock.is_vcs_lock_only_change`
    (sentinel comparator: absent != present-but-null, C-005). A missing working
    copy (or a deletion, ``OSError``) is genuine dirt (``False``) so it still
    blocks the advance; a **present-but-unparseable** working copy raises
    :class:`MetaDecodeError` naming the file (fail loud, FR-003/FR-005).
    """
    meta_path = worktree / path
    try:
        worktree_text = meta_path.read_text(encoding="utf-8")
    except OSError:
        return False
    worktree_meta = _decode_meta_named(worktree_text, source=str(meta_path))
    committed_meta = _committed_meta_object(worktree, path, env)
    return is_vcs_lock_only_change(committed_meta, worktree_meta)


def _dirty_entries(
    worktree: Path,
    env: dict[str, str] | None,
    *,
    new_sha: str,
    target_paths: set[str],
    is_residue: Callable[[str], bool] | None = None,
    treat_untracked_as_dirty: bool = False,
) -> list[str]:
    """Return porcelain entries that a ``reset --hard`` would destroy.

    Most untracked/ignored files survive ``git reset --hard``, but an
    untracked or ignored path that obstructs a tracked path in ``new_sha`` is
    overwritten by git during the reset. Treat those obstructions as local
    state and refuse before moving the ref (NFR-002).

    ``treat_untracked_as_dirty`` (#4753 Finding A): the obstruction-only rule
    above is correct for ``advance_branch_ref``'s ``reset --hard`` semantics
    (an untracked file that does NOT obstruct the target tree survives the
    reset unharmed), but it is WRONG for a ``git worktree remove --force``
    caller — that command deletes the entire worktree directory tree,
    obstruction or not, so an untracked-only operator file is destroyed even
    though this predicate's default reading called it safe. When True, every
    untracked (``??``) entry not exempted by ``is_residue`` counts as dirty,
    regardless of obstruction. Ignored (``!!``) entries are unaffected — they
    remain obstruction-gated, since an ignored path (build output, ``.venv``,
    caches) is expected disposable debris in either a reset or a removal.
    Defaults to ``False`` so every existing caller (``advance_branch_ref``) is
    byte-unchanged.

    Everything staged or unstaged against tracked paths is also unique local
    state and blocks the resync -- UNLESS ``is_residue`` recognizes it (see
    below), closing the #2795 / FR-012 cross-gate disagreement: a tracked
    entry used to have only the narrow ``_META_FILENAME`` vcs-lock escape, so
    a general toolchain-generated churn path (coordination-branch status
    residue, spec-kitty's own bookkeeping) was fatal here while every other
    churn-classifying gate (``merge/git_probes.py``,
    ``review/dirty_classifier.py``) already exempted it -- same file, opposite
    verdict. Consulting ``is_residue`` first, for BOTH tracked and untracked
    entries, makes this gate agree with the others (WP13 / IC-07c).

    Args:
        is_residue: Predicate returning True for a repo-relative path that is
            toolchain-generated churn (coordination-branch status/matrix
            residue, spec-kitty's own bookkeeping such as ``meta.json``) a
            caller wants excluded from the dirty check, for both untracked and
            tracked entries (#1878 / #2795 / FR-012). Pass
            :func:`specify_cli.coordination.coherence.is_toolchain_generated_churn`
            (this module stays git-plumbing and does not import it itself --
            the caller injects the classifier). ``None`` disables the
            exemption entirely (git-plumbing default: nothing is toolchain
            churn without an injected classifier).
    """
    result = _run_git(worktree, ["status", "--porcelain", "--ignored"], env=env)
    if result.returncode != 0:
        raise RefAdvanceError(f"Could not inspect worktree state at {worktree}: {result.stderr.strip() or result.stdout.strip()}")
    dirty: list[str] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        path = _porcelain_path(line)
        if is_residue is not None and is_residue(path):
            continue
        if line.startswith("??"):
            if treat_untracked_as_dirty:
                dirty.append(f"{line} (untracked local file would be discarded by worktree removal)")
                continue
            if _path_obstructs_target_tree(path, target_paths):
                dirty.append(f"{line} (would be overwritten by reset --hard to {new_sha[:12]})")
            continue
        if line.startswith("!!"):
            if _path_obstructs_target_tree(path, target_paths):
                dirty.append(f"{line} (would be overwritten by reset --hard to {new_sha[:12]})")
            continue
        # A tracked ``meta.json`` whose only diff against HEAD is the claim-time
        # VCS lock is a regenerable stamp, not destructive local state: the
        # resync discards it and the next claim rewrites it (#2795 / C-010). A
        # genuine meta edit still falls through and blocks (no false-open).
        if Path(path).name == _META_FILENAME and _meta_change_is_vcs_lock_only(worktree, path, env):
            continue
        dirty.append(line)
    return dirty


def advance_branch_ref(
    repo_root: Path,
    branch: str,
    new_sha: str,
    *,
    env: dict[str, str] | None = None,
    is_residue: Callable[[str], bool] | None = None,
) -> None:
    """Advance ``refs/heads/<branch>`` to ``new_sha`` and resync checkouts.

    Invariant (#1826): **no worktree may be left checked out behind a ref
    this function advanced.** After a successful return, every worktree with
    ``branch`` checked out has HEAD == index == working tree == ``new_sha``
    (CONSISTENT). With no such checkout, behavior is identical to a raw
    ``git update-ref`` plus the worktree scan.

    Order of operations (atomic refusal): all checked-out worktrees are
    dirty-checked BEFORE the ref moves, so a refusal leaves the ref, every
    worktree, and the merge state exactly as found.

    Args:
        repo_root: Primary repository root (where the ref lives).
        branch: Short branch name (no ``refs/heads/`` prefix).
        new_sha: Commit SHA the branch ref advances to.
        env: Optional subprocess environment (merge pipeline passes its
            ``_make_merge_env()`` result through).
        is_residue: Optional predicate excluding toolchain-generated-churn
            paths (coordination-branch status/matrix residue, e.g.
            ``status.events.jsonl`` / ``status.json``; spec-kitty's own
            bookkeeping, e.g. ``meta.json``) from the dirty-file check --
            for BOTH untracked and tracked entries -- so they do not abort a
            post-write ff-advance (#1878 / #2795 / FR-012). Pass
            ``specify_cli.coordination.coherence.is_toolchain_generated_churn``
            (this module is git plumbing and does not import that classifier
            itself -- the caller injects it, keeping the dependency direction
            one-way).

    Raises:
        RefAdvanceDirtyWorktreeError: a worktree with ``branch`` checked out
            holds uncommitted tracked changes (NFR-002/NFR-003); nothing was
            mutated.
        RefAdvanceError: the worktree scan, ``update-ref``, or a resync
            failed at the git level.
    """
    ref = f"refs/heads/{branch}"

    old_sha_result = _run_git(repo_root, ["rev-parse", "--verify", "--quiet", ref], env=env)
    old_sha = old_sha_result.stdout.strip() if old_sha_result.returncode == 0 else "<unborn>"

    if old_sha != "<unborn>":
        ff_check = _run_git(
            repo_root,
            ["merge-base", "--is-ancestor", old_sha, new_sha],
            env=env,
        )
        if ff_check.returncode == 1:
            raise RefAdvanceNonFastForwardError(
                branch=branch,
                old_sha=old_sha,
                new_sha=new_sha,
            )
        if ff_check.returncode != 0:
            raise RefAdvanceError(f"Could not verify fast-forward ancestry for {branch}: {ff_check.stderr.strip() or ff_check.stdout.strip()}")

    checkouts = [entry.path for entry in _list_worktrees(repo_root, env) if not entry.detached and entry.branch == ref]
    target_paths = _target_tree_paths(repo_root, new_sha, env)

    # Dirty check strictly BEFORE the ref mutation and BEFORE any reset path:
    # a refusal must be atomic (nothing advanced, nothing reset).
    for worktree in checkouts:
        dirty = _dirty_entries(
            worktree,
            env,
            new_sha=new_sha,
            target_paths=target_paths,
            is_residue=is_residue,
        )
        if dirty:
            raise RefAdvanceDirtyWorktreeError(
                worktree_path=worktree.resolve(),
                branch=branch,
                old_sha=old_sha,
                new_sha=new_sha,
                dirty_entries=dirty,
            )

    result = _run_git(repo_root, ["update-ref", ref, new_sha], env=env)
    if result.returncode != 0:
        raise RefAdvanceError(f"Failed to update {branch} ref: {result.stderr.strip() or result.stdout.strip()}")

    for worktree in checkouts:
        reset = _run_git(worktree, ["reset", "--hard", branch], env=env)
        if reset.returncode != 0:
            raise RefAdvanceError(
                f"Advanced {branch} ({old_sha[:12]} -> {new_sha[:12]}) but "
                f"failed to resync the checked-out worktree at {worktree}: "
                f"{reset.stderr.strip() or reset.stdout.strip()}. "
                f"The worktree is behind its own HEAD (#1826); repair with "
                f"`git -C {worktree} reset --hard` once the cause is fixed."
            )


def restore_branch_ref(
    repo_root: Path,
    branch: str,
    restored_sha: str,
    *,
    expected_current_sha: str,
) -> None:
    """Restore a branch ref with compare-and-swap semantics after failure.

    This is the rollback-only counterpart to :func:`advance_branch_ref`.
    It deliberately permits a non-fast-forward move, but only when the ref is
    still at ``expected_current_sha``. Callers own restoration of the affected
    checkout's index and intentionally retain worktree files for diagnosis.
    """
    ref = f"refs/heads/{branch}"
    result = _run_git(
        repo_root,
        ["update-ref", ref, restored_sha, expected_current_sha],
    )
    if result.returncode != 0:
        raise RefRestoreError(
            f"Failed to restore {branch!r} from {expected_current_sha[:12]} to {restored_sha[:12]}: {result.stderr.strip() or result.stdout.strip()}"
        )
