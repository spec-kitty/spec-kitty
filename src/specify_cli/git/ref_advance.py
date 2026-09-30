"""Branch ref advance with checked-out-worktree resync (#1826).

The merge pipeline advances ``refs/heads/<branch>`` via ``git update-ref``
from detached temporary worktrees. ``update-ref`` is plumbing: it bypasses
git's checked-out-branch protection and updates nothing in any worktree that
has the branch checked out. That worktree is left with an index/working tree
*behind its own HEAD* — the next safe-commit through it sees phantom staged
deletions, and a plain ``git commit`` from its stale index would silently
delete the advanced commits' files from the branch (#1826).

:func:`advance_branch_ref` is the sanctioned way for the merge pipeline to
advance a branch ref. Safe commits use the narrower
:func:`advance_branch_ref_for_commit`, which CAS-advances only when the target
branch is checked out exactly in the worktree whose requested index paths the
caller reconciles. **Invariant: no sibling worktree may be left checked out
behind a ref either function advanced.** An architectural ratchet
(``tests/architectural/test_merge_pipeline_ratchets.py``) enforces that no
raw ``update-ref`` subprocess invocation exists in ``src/specify_cli``
outside this module (AC-B3).

Atomicity: :func:`advance_branch_ref` moves the ref with a compare-and-swap
``git update-ref <ref> <new> <expected_old>`` (3-arg), mirroring the
rollback path :func:`restore_branch_ref`. Correctness rests on that CAS, not
on any external lock: if the ref changed between the value the caller read at
the start of its merge transaction and the write, ``update-ref`` returns
non-zero and this function raises :class:`RefAdvanceError` rather than
clobbering the concurrent writer's commit (FR-003). It never falls back to a
2-arg write and never retries. The merge pipeline may still serialize its own
call sites, but that serialization is no longer what makes the advance safe —
the ``__global_merge__`` lock is unlinkable by ``merge --abort`` (#4996), so
resting correctness on it was the latent hazard this CAS closes.
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

# Marker substring :func:`_dirty_entries` appends to an untracked/ignored entry it
# flags as a reset-hard obstruction (as opposed to a tracked-change entry, appended
# raw with no suffix). :func:`reset_would_obstruct_untracked` matches on this marker
# to ask ONLY the obstruction question through :func:`_dirty_entries` -- not "is
# anything at all dirty" -- without re-deriving the classification itself (INV-3;
# a second module-level ``git status --porcelain``-parsing predicate is exactly the
# regression ``tests/architectural/test_destructive_op_routing.py`` (T019) guards
# against).
_RESET_OBSTRUCTION_MARKER: str = "would be overwritten by reset --hard to "

# Sentinel for the short OID displayed when a ref has no current value yet.
_UNBORN: str = "<unborn>"

# The all-zero OID: ``git update-ref <ref> <new> <zero>`` asserts the ref does
# not already exist, the CAS form of creating an unborn ref.
_ZERO_OID: str = "0" * 40


def _cas_expected_old(expected_old_sha: str | None, observed_old_sha: str) -> str:
    """Resolve the compare-and-swap *old value* token for ``git update-ref``.

    ``expected_old_sha`` is the value the caller read at the start of its merge
    transaction (WP06 threads it). When absent — the interim default until that
    wiring lands — fall back to the value :func:`advance_branch_ref` observed at
    entry, so the write is still an atomic CAS rather than an unconditional
    2-arg overwrite. An ``<unborn>`` observed value maps to the zero OID, which
    ``git update-ref`` reads as "the ref must not already exist".
    """
    candidate = expected_old_sha if expected_old_sha is not None else observed_old_sha
    return _ZERO_OID if candidate == _UNBORN else candidate


def _update_branch_ref_cas(
    repo_root: Path,
    ref: str,
    new_sha: str,
    expected_old_sha: str,
    *,
    env: dict[str, str] | None = None,
    message: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Perform the single canonical compare-and-swap ref write."""
    args = ["update-ref"]
    if message is not None:
        args.extend(["-m", message])
    args.extend([ref, new_sha, expected_old_sha])
    return _run_git(repo_root, args, env=env)


class RefAdvanceError(RuntimeError):
    """A branch-ref advance failed at the git level (non-dirty cause)."""

    error_code = "REF_ADVANCE_FAILED"


class RefResyncError(RefAdvanceError):
    """The compare-and-swap ref write SUCCEEDED but a checkout resync failed.

    Unlike a plain :class:`RefAdvanceError` (e.g. a CAS refusal: ANOTHER actor
    moved the ref), the ref now holds the value THIS caller wrote. Callers that
    attribute ref moves (the consolidation rollback recorder) must treat it as
    their own move. The worktree named in the message is behind its own HEAD.
    """

    error_code = "REF_RESYNC_FAILED"


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
            f"then resume the consolidation (`spec-kitty consolidate --resume`)."
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
    """Return True when an untracked/ignored path may be clobbered by reset.

    A reset clobbers *path* when the target tree has that exact path, a path
    inside it, or a path that is one of its ancestors. The ancestor case is a
    tracked directory replaced by a tracked file: ignored ``src/store/local.txt``
    is destroyed when the incoming tree contains file ``src/store`` (#5400).
    Matches use slash-delimited components, so ``store`` does not obstruct
    ``storehouse``. An empty local path never obstructs.
    """
    if not path:
        return False
    as_directory = f"{path}/"
    return any(target == path or target.startswith(as_directory) or path.startswith(f"{target}/") for target in target_paths)


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
                dirty.append(f"{line} ({_RESET_OBSTRUCTION_MARKER}{new_sha[:12]})")
            continue
        if line.startswith("!!"):
            if _path_obstructs_target_tree(path, target_paths):
                dirty.append(f"{line} ({_RESET_OBSTRUCTION_MARKER}{new_sha[:12]})")
            continue
        # A tracked ``meta.json`` whose only diff against HEAD is the claim-time
        # VCS lock is a regenerable stamp, not destructive local state: the
        # resync discards it and the next claim rewrites it (#2795 / C-010). A
        # genuine meta edit still falls through and blocks (no false-open).
        if Path(path).name == _META_FILENAME and _meta_change_is_vcs_lock_only(worktree, path, env):
            continue
        dirty.append(line)
    return dirty


def reset_would_obstruct_untracked(
    repo_root: Path,
    ref: str = "HEAD",
    *,
    env: dict[str, str] | None = None,
) -> bool:
    """True when ``git reset --hard <ref>`` would clobber an untracked-or-ignored file.

    #4997 (follow-up, data-loss). ``git reset --hard`` overwrites any UNTRACKED
    **or IGNORED** path that collides with a path tracked in ``ref``'s tree --
    ``git diff`` is blind to both, and scanning only untracked files (e.g. ``git
    ls-files --others --exclude-standard``) hides gitignored paths, reopening the
    hole for a path a mission force-added (``git add -f``) despite a
    ``.gitignore`` entry: the operator's genuine gitignored file at that same
    path would be silently clobbered by the reset.

    This is the PUBLIC seam for a caller outside this module (the ``merge/``
    layer, INV-3) to ask that obstruction question without reaching into this
    module's private helpers. It delegates entirely to :func:`_dirty_entries` --
    the single obstruction authority this module already reuses for
    :func:`advance_branch_ref` -- and simply asks whether any of the entries it
    returns are one it tagged as a reset-hard obstruction (``??``/``!!``
    entries matching :data:`_RESET_OBSTRUCTION_MARKER`), ignoring tracked-change
    entries: this seam answers only "would the reset clobber untracked/ignored
    local state", not "is the worktree dirty" in general -- callers that also
    need the tracked-change question (e.g. :func:`specify_cli.consolidation.preflight
    .is_pure_behind_head_lag`) answer it separately (``git diff --quiet``
    against their own base). No new ``git status --porcelain``-parsing
    predicate is introduced (T019 of
    ``tests/architectural/test_destructive_op_routing.py``).

    Fail-closed: any git error (non-zero exit) or unexpected exception returns
    True -- a reset whose safety could not be proven is never treated as safe.
    """
    try:
        target_paths = _target_tree_paths(repo_root, ref, env)
        dirty = _dirty_entries(repo_root, env, new_sha=ref, target_paths=target_paths)
    except Exception:
        return True
    return any(_RESET_OBSTRUCTION_MARKER in entry for entry in dirty)


def _checkouts_ready_for(
    repo_root: Path,
    branch: str,
    new_sha: str,
    env: dict[str, str] | None,
    is_residue: Callable[[str], bool] | None,
    *,
    old_sha: str,
) -> list[Path]:
    """List worktrees with ``branch`` checked out, refusing if any is dirty.

    Runs strictly BEFORE the ref moves so a refusal is atomic (nothing
    advanced, nothing reset). Shared by :func:`advance_branch_ref` and
    :func:`restore_branch_ref` (``resync_checkouts=True``).
    """
    ref = f"refs/heads/{branch}"
    checkouts = [entry.path for entry in _list_worktrees(repo_root, env) if not entry.detached and entry.branch == ref]
    target_paths = _target_tree_paths(repo_root, new_sha, env)
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
    return checkouts


def _resync_checkouts(
    checkouts: list[Path],
    branch: str,
    env: dict[str, str] | None,
    *,
    context: str,
) -> None:
    """Hard-reset each checkout to the (already moved) ``branch`` ref (#1826).

    Raises :class:`RefResyncError` (the ref already moved) when a reset fails.
    """
    for worktree in checkouts:
        reset = _run_git(worktree, ["reset", "--hard", branch], env=env)
        if reset.returncode != 0:
            raise RefResyncError(
                f"{context} but "
                f"failed to resync the checked-out worktree at {worktree}: "
                f"{reset.stderr.strip() or reset.stdout.strip()}. "
                f"The worktree is behind its own HEAD (#1826); repair with "
                f"`git -C {worktree} reset --hard` once the cause is fixed."
            )


def advance_branch_ref(
    repo_root: Path,
    branch: str,
    new_sha: str,
    *,
    expected_old_sha: str | None = None,
    env: dict[str, str] | None = None,
    is_residue: Callable[[str], bool] | None = None,
) -> None:
    """Advance ``refs/heads/<branch>`` to ``new_sha`` and resync checkouts.

    Invariant (#1826): **no worktree may be left checked out behind a ref
    this function advanced.** After a successful return, every worktree with
    ``branch`` checked out has HEAD == index == working tree == ``new_sha``
    (CONSISTENT). With no such checkout, behavior is identical to a raw
    compare-and-swap ``git update-ref`` plus the worktree scan.

    Order of operations (atomic refusal): all checked-out worktrees are
    dirty-checked BEFORE the ref moves, so a refusal leaves the ref, every
    worktree, and the merge state exactly as found. The ref itself moves under
    a compare-and-swap ``git update-ref <ref> <new_sha> <expected_old>`` — a
    concurrent move fails the write closed (FR-003), mirroring
    :func:`restore_branch_ref`; there is no 2-arg fallback and no retry.

    Args:
        repo_root: Primary repository root (where the ref lives).
        branch: Short branch name (no ``refs/heads/`` prefix).
        new_sha: Commit SHA the branch ref advances to.
        expected_old_sha: The ref value the caller read at the start of its
            merge transaction, used as the compare-and-swap *old value* so a
            concurrent move between that read and this write fails closed
            (FR-003). Keyword-only. **Interim default** ``None`` falls back to
            the value observed at entry, keeping existing merge call sites
            atomic until WP06 threads the transaction-start value; WP06 must
            pass it explicitly at every call site (``lanes/merge.py``,
            ``merge/ordering.py``, ``coordination/commit_router.py``).
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
        RefAdvanceError: the worktree scan failed at the git level, or the
            compare-and-swap ``update-ref`` failed because the ref changed
            since it was read (fail-closed; never a 2-arg fallback or a retry).
        RefResyncError: the ``RefAdvanceError`` subclass raised when the ref
            WAS advanced but a checked-out worktree could not be resynced.
    """
    ref = f"refs/heads/{branch}"

    old_sha_result = _run_git(repo_root, ["rev-parse", "--verify", "--quiet", ref], env=env)
    old_sha = old_sha_result.stdout.strip() if old_sha_result.returncode == 0 else _UNBORN

    if old_sha != _UNBORN:
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

    checkouts = _checkouts_ready_for(repo_root, branch, new_sha, env, is_residue, old_sha=old_sha)

    expected_old = _cas_expected_old(expected_old_sha, old_sha)
    result = _update_branch_ref_cas(repo_root, ref, new_sha, expected_old, env=env)
    if result.returncode != 0:
        raise RefAdvanceError(
            f"Compare-and-swap advance of {branch!r} "
            f"({old_sha[:12]} -> {new_sha[:12]}) failed: the ref no longer "
            f"matches the expected value {expected_old[:12]} — it changed "
            f"since it was read. Refusing to clobber the concurrent update "
            f"(no 2-arg fallback, no retry). "
            f"git: {result.stderr.strip() or result.stdout.strip()}"
        )

    _resync_checkouts(
        checkouts,
        branch,
        env,
        context=f"Advanced {branch} ({old_sha[:12]} -> {new_sha[:12]})",
    )


def restore_branch_ref(
    repo_root: Path,
    branch: str,
    restored_sha: str,
    *,
    expected_current_sha: str,
    resync_checkouts: bool = False,
    is_residue: Callable[[str], bool] | None = None,
    env: dict[str, str] | None = None,
) -> None:
    """Restore a branch ref with compare-and-swap semantics after failure.

    This is the rollback-only counterpart to :func:`advance_branch_ref`.
    It deliberately permits a non-fast-forward move, but only when the ref is
    still at ``expected_current_sha``.

    By DEFAULT (``resync_checkouts=False``) callers own restoration of the
    affected checkout's index and intentionally retain worktree files for
    diagnosis. With ``resync_checkouts=True`` every worktree that has
    ``branch`` checked out is dirty-checked BEFORE the ref moves (a dirty
    checkout raises :class:`RefAdvanceDirtyWorktreeError` and nothing is
    mutated; ``is_residue`` excludes toolchain churn exactly as in
    :func:`advance_branch_ref`), the ref then moves under the same
    compare-and-swap, and each checkout is hard-reset to the restored ref via
    the shared :func:`_resync_checkouts` (HEAD == index == worktree).
    """
    ref = f"refs/heads/{branch}"
    checkouts: list[Path] = []
    if resync_checkouts:
        checkouts = _checkouts_ready_for(
            repo_root,
            branch,
            restored_sha,
            env,
            is_residue,
            old_sha=expected_current_sha,
        )
    result = _update_branch_ref_cas(repo_root, ref, restored_sha, expected_current_sha, env=env)
    if result.returncode != 0:
        raise RefRestoreError(
            f"Failed to restore {branch!r} from {expected_current_sha[:12]} to {restored_sha[:12]}: {result.stderr.strip() or result.stdout.strip()}"
        )
    _resync_checkouts(
        checkouts,
        branch,
        env,
        context=f"Restored {branch} ({expected_current_sha[:12]} -> {restored_sha[:12]})",
    )


def advance_branch_ref_for_commit(
    repo_root: Path,
    worktree_root: Path,
    branch: str,
    new_sha: str,
    *,
    expected_old_sha: str,
    message: str,
    env: dict[str, str] | None = None,
) -> None:
    """CAS-advance a safe-commit target without resyncing unrelated paths.

    This narrow seam is only for ``safe_commit``'s path-scoped index
    transaction: after this returns, that caller reconciles the requested
    paths itself. Unlike :func:`advance_branch_ref`, it must not hard-reset a
    worktree, because doing so would discard unrelated staged or working-tree
    state. Before writing, it verifies that the target ref is checked out
    exactly in ``worktree_root``; otherwise a raw ref move could leave a
    sibling checkout stale (#1826), or leave the caller without a checkout to
    reconcile.
    """
    ref = f"refs/heads/{branch}"
    resolved_worktree = worktree_root.resolve()
    checkouts = [entry for entry in _list_worktrees(repo_root, env) if not entry.detached and entry.branch == ref]
    if len(checkouts) > 1:
        raise RefAdvanceError(f"Refusing safe-commit advance of {branch!r}: it is checked out in another worktree too (more than one worktree total).")
    if not checkouts:
        raise RefAdvanceError(f"Refusing safe-commit advance of {branch!r}: it is not checked out in the worktree safe_commit reconciles at {resolved_worktree}.")
    if checkouts[0].path.resolve() != resolved_worktree:
        raise RefAdvanceError(
            f"Refusing safe-commit advance of {branch!r}: it is checked out in other worktree "
            f"{checkouts[0].path.resolve()}, not the worktree safe_commit reconciles at {resolved_worktree}."
        )

    updated = _update_branch_ref_cas(
        repo_root,
        ref,
        new_sha,
        expected_old_sha,
        env=env,
        message=message,
    )
    if updated.returncode != 0:
        detail = (updated.stderr or updated.stdout).strip()
        raise RefAdvanceError(
            f"Compare-and-swap safe-commit advance of {branch!r} failed: expected "
            f"{expected_old_sha[:12]}; refusing to clobber a concurrent ref update. "
            f"git: {detail or 'git update-ref failed'}"
        )


# ---------------------------------------------------------------------------
# Spec Kitty bookkeeping refs (``refs/spec-kitty/**``)
# ---------------------------------------------------------------------------

#: Namespace of the bookkeeping refs spec-kitty records for itself (lane work
#: tips, repo-root claim bases). They are never branches and never checked
#: out, so the #1826 worktree-resync hazard :func:`advance_branch_ref` guards
#: against cannot arise; they still go through this module so the AC-B3
#: ratchet keeps every raw ``update-ref`` in one place.
BOOKKEEPING_REF_PREFIX: str = "refs/spec-kitty/"


class BookkeepingRefError(ValueError):
    """A bookkeeping-ref write named a ref outside ``refs/spec-kitty/``."""

    error_code = "BOOKKEEPING_REF_OUT_OF_NAMESPACE"


def _require_bookkeeping_ref(ref: str) -> None:
    if not ref.startswith(BOOKKEEPING_REF_PREFIX) or ref == BOOKKEEPING_REF_PREFIX:
        raise BookkeepingRefError(
            f"Refusing to write {ref!r}: only {BOOKKEEPING_REF_PREFIX}** bookkeeping refs are written here; branch refs go through advance_branch_ref()."
        )


def write_bookkeeping_ref(repo_root: Path, ref: str, sha: str) -> bool:
    """Point the bookkeeping ref *ref* at *sha*; return ``True`` on success.

    A plain (2-arg) ``git update-ref``: bookkeeping refs are single-writer
    records owned by their caller, which decides whether a failure matters
    (a best-effort recorder ignores ``False``; a mandatory one raises).

    Raises:
        BookkeepingRefError: *ref* is not under ``refs/spec-kitty/`` -- a
            branch or any other namespace must never be moved through here.
    """
    _require_bookkeeping_ref(ref)
    return _run_git(repo_root, ["update-ref", ref, sha]).returncode == 0


def delete_bookkeeping_ref(repo_root: Path, ref: str) -> bool:
    """Delete the bookkeeping ref *ref*; return ``True`` on success.

    Deleting an already-absent ref succeeds (``git update-ref -d`` is a
    no-op for a missing ref), so callers may treat this as idempotent.

    Raises:
        BookkeepingRefError: *ref* is not under ``refs/spec-kitty/``.
    """
    _require_bookkeeping_ref(ref)
    return _run_git(repo_root, ["update-ref", "-d", ref]).returncode == 0
