"""Shared mechanics for writing a Mission's ``meta.json`` during a consolidation (#7692).

One home for "write ``meta.json`` under the Mission write lock, keep the bytes before and
written, commit it on a branch, undo it by compare-and-swap". The mission-number bake
(:mod:`specify_cli.consolidation.mission_number.bake`) uses these today and the retarget
phase reuses them.

**Mechanics only, never policy.** Each caller owns what a refusal means: the bake is
fail-open (it surfaces an unbaked number and returns ``False``), the retarget is
fail-closed. Nothing here logs, warns or raises a refusal of its own; every outcome is
returned to the caller, which keeps its own messages.
"""

from __future__ import annotations

import copy
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from kernel.atomic import observe_writes, stop_observing_writes
from kernel.git import run_git, status_entries, tree_entry
from specify_cli.consolidation.git_probes import mission_residue_context, path_is_under_worktrees
from specify_cli.consolidation.workspace import remove_scratch_worktree
from specify_cli.git.ref_advance import RefAdvanceDirtyWorktreeError, advance_branch_ref
from specify_cli.mission_metadata import load_meta, locked_update_meta

__all__ = [
    "MetaBranchOutcome",
    "MetaBranchRefusal",
    "MetaBranchWrite",
    "MetaMutate",
    "commit_meta_on_branch",
    "locked_update_meta_capturing",
    "primary_checkout_refusal",
    "undo_meta_write",
]

#: Edits a fresh ``meta.json`` dict in place; returns ``True`` when it changed it.
#: It must be a pure function of the dict: :func:`commit_meta_on_branch` calls it once on
#: a copy (the pre-lock idempotency read) and once under the lock.
MetaMutate = Callable[[dict[str, Any]], bool]

#: Seconds before the primary ``meta.json`` ``hash-object`` probe is killed: a
#: clean filter can block on a prompt, and a timeout is a refusal.
_META_BLOB_PROBE_TIMEOUT_SECONDS = 60.0

_META_FILENAME = "meta.json"


def locked_update_meta_capturing(feature_dir: Path, mutate: MetaMutate, *, repo_root: Path | None) -> tuple[bytes, bytes] | None:
    """Apply *mutate* to *feature_dir*'s ``meta.json`` under the Mission write lock.

    The read, the idempotency decision (*mutate* returning ``False``) and the write run in
    ONE hold of the lock, on a fresh read, so a concurrent writer of another ``meta.json``
    field is never overwritten. The lock is held for the ``meta.json`` write only. The write
    is ``locked_update_meta(..., validate=False)``: merge-time tolerance for legacy or
    partial metadata, with atomic writes and the standard format.

    Returns:
        ``(bytes before, bytes written)``, both read inside the hold; ``None`` when *mutate*
        returned ``False`` (nothing written).
    """
    meta_path = feature_dir / _META_FILENAME
    wrote = False
    before: list[bytes] = []
    written: list[bytes] = []

    def apply(fresh: dict[str, Any]) -> bool:
        nonlocal wrote
        if not mutate(fresh):
            return False
        before.append(meta_path.read_bytes())
        wrote = True
        return True

    token = observe_writes(lambda path, content: written.append(content) if path.name == _META_FILENAME else None)
    try:
        locked_update_meta(feature_dir, apply, repo_root=repo_root, validate=False)
    finally:
        stop_observing_writes(token)
    return (before[-1], written[-1]) if wrote and before and written else None


def undo_meta_write(meta_path: Path, original: bytes, written: bytes, repo_root: Path) -> str | None:
    """Put ``meta.json`` back after a refused commit, only while it still holds what was written.

    A compare-and-swap inside the Mission write lock (plan A8): a field another writer set
    since is never erased. Returns a note when the file was left as it is because it
    changed, else ``None``.
    """
    from specify_cli.mission_metadata import restore_meta_text

    restored = restore_meta_text(meta_path.parent, original.decode("utf-8"), expected_current=written.decode("utf-8"), repo_root=repo_root)
    return None if restored else f"{meta_path} was changed by another writer after this write and was left as it is"


def primary_checkout_refusal(main_repo: Path, rel_meta: Path, target_branch: str) -> str | None:
    """Why the primary checkout must not receive a ``meta.json`` commit on *target_branch*, or ``None``.

    #5443 / FR-010: the commit may only land on ``target_branch`` and may only
    carry ``meta.json``. Refuses a detached HEAD, a checkout on another
    branch, and a ``meta.json`` that is not tracked in HEAD or already differs from it
    (index or worktree) -- the operator's own edit is never read-modified-written.

    ``git status`` alone cannot prove the worktree side: ``assume-unchanged`` and
    ``skip-worktree`` hide an edit from it, so the worktree blob, filtered or raw,
    must equal HEAD's entry (a CRLF blob already in HEAD under ``core.autocrlf``
    only matches the raw hash).
    """
    head = subprocess.run(
        ["git", "symbolic-ref", "--quiet", "--short", "HEAD"],
        cwd=str(main_repo),
        capture_output=True,
        text=True,
    )
    branch = head.stdout.strip() if head.returncode == 0 else ""
    if not branch:
        return "primary checkout is on a detached HEAD"
    if branch != target_branch:
        return f"primary checkout is on {branch!r}, not the merge target {target_branch!r}"
    # Tracked-in-HEAD AND clean: an untracked (or gitignored) meta.json also
    # "differs from HEAD" and carries content that is not ours to commit.
    # A failing probe is a refusal too -- never an exception out of the caller.
    try:
        head_entry = tree_entry(main_repo, "HEAD", rel_meta.as_posix())
        if head_entry is None:
            return f"{rel_meta} is not tracked on {target_branch!r}"
        if status_entries(main_repo, pathspecs=(rel_meta.as_posix(),), untracked="no"):
            return f"{rel_meta} has uncommitted changes on the primary checkout"
        rel = rel_meta.as_posix()
        worktree_oids = {
            run_git(main_repo, *flags, "--", rel, timeout=_META_BLOB_PROBE_TIMEOUT_SECONDS).stdout.decode("ascii").strip()
            for flags in (("hash-object",), ("hash-object", "--no-filters"))
        }
        if head_entry.oid not in worktree_oids:
            return f"{rel_meta} differs from HEAD on the primary checkout (an assume-unchanged or skip-worktree edit)"
    except Exception as exc:  # noqa: BLE001 - any probe failure means "do not commit"
        return f"could not verify {rel_meta} is clean on the primary checkout ({exc})"
    return None


class MetaBranchOutcome(Enum):
    """What :func:`commit_meta_on_branch` did."""

    WRITTEN = "written"
    NO_META_ON_BRANCH = "no_meta_on_branch"
    UNCHANGED = "unchanged"
    REFUSED = "refused"


class MetaBranchRefusal(Enum):
    """Why :func:`commit_meta_on_branch` wrote nothing, for a ``REFUSED`` outcome."""

    #: ``git worktree add --detach`` failed; ``detail`` is its stderr.
    WORKTREE_UNAVAILABLE = "worktree_unavailable"
    #: The composed ``meta.json`` path lies under ``.worktrees/``; ``detail`` is that path.
    META_PATH_UNDER_WORKTREES = "meta_path_under_worktrees"
    #: ``meta.json`` on the branch is malformed or not a JSON object; ``detail`` is its path.
    NOT_A_JSON_OBJECT = "not_a_json_object"
    #: The path to stage lies under ``.worktrees/`` (FR-035); ``detail`` is that path.
    STAGE_PATH_UNDER_WORKTREES = "stage_path_under_worktrees"


@dataclass(frozen=True)
class MetaBranchWrite:
    """The result of :func:`commit_meta_on_branch`.

    ``new_sha`` is set for ``WRITTEN``; ``refusal`` and ``detail`` for ``REFUSED``.
    ``unchanged_on_read`` tells an ``UNCHANGED`` found on the pre-lock read (``True``) from
    one found under the lock (``False``: another writer got there first).
    """

    outcome: MetaBranchOutcome
    new_sha: str | None = None
    refusal: MetaBranchRefusal | None = None
    detail: str = ""
    unchanged_on_read: bool = False


def _refused(refusal: MetaBranchRefusal, detail: object) -> MetaBranchWrite:
    return MetaBranchWrite(MetaBranchOutcome.REFUSED, refusal=refusal, detail=str(detail))


def commit_meta_on_branch(
    main_repo: Path,
    branch: str,
    mission_slug: str,
    mutate: MetaMutate,
    *,
    message: str,
    scratch_prefix: str = "kitty-metawrite-",
) -> MetaBranchWrite:
    """Apply *mutate* to ``meta.json`` on *branch* and commit it there, without touching any checkout.

    Runs in a fresh detached scratch worktree of *branch*: composes the in-branch
    ``meta.json`` path (never a nested ``.worktrees/`` copy), writes it under the Mission
    write lock (keyed on *main_repo*'s primary ``meta.json``), commits exactly that file
    (``git commit --only -- <rel_meta>``; hooks run) and fast-forwards *branch* by
    compare-and-swap, resyncing any checkout that holds it. The scratch worktree is removed
    in every case.

    C-005 recorded exception: this is the ONE pathspec'd ``commit --only`` in a detached
    temp worktree (``safe_commit`` refuses a detached HEAD).

    The caller checks the slug (``assert_safe_path_segment``) and that *branch* exists.
    A dirty checkout holding *branch* raises
    :class:`RefAdvanceDirtyWorktreeError`, its text extended with the consolidate next step.
    """
    scratch = Path(tempfile.mkdtemp(prefix=scratch_prefix))
    try:
        added = subprocess.run(
            ["git", "worktree", "add", "--detach", str(scratch), branch],
            cwd=str(main_repo),
            capture_output=True,
            text=True,
        )
        if added.returncode != 0:
            return _refused(MetaBranchRefusal.WORKTREE_UNAVAILABLE, added.stderr.strip())
        return _commit_in_scratch(main_repo, scratch, branch, mission_slug, mutate, message=message)
    finally:
        # The scratch worktree is this function's own checkout (tool-owned, #5965).
        remove_scratch_worktree(scratch)


def _commit_in_scratch(
    main_repo: Path,
    scratch: Path,
    branch: str,
    mission_slug: str,
    mutate: MetaMutate,
    *,
    message: str,
) -> MetaBranchWrite:
    """The body of :func:`commit_meta_on_branch` once the scratch worktree exists."""
    # FR-037 (#1772 Bug 3): resolve the IN-BRANCH mission dir for the detached worktree, never a
    # nested-worktree meta.json -- the branch tree carries the canonical dir under ``kitty-specs/``.
    from specify_cli.missions._read_path_resolver import compose_meta_json_path

    meta_path = compose_meta_json_path(scratch, mission_slug)
    if path_is_under_worktrees(meta_path):
        return _refused(MetaBranchRefusal.META_PATH_UNDER_WORKTREES, meta_path)
    if not meta_path.exists():
        return MetaBranchWrite(MetaBranchOutcome.NO_META_ON_BRANCH)
    # Canonical reader (FR-005/WP12): on_malformed="none" absorbs a JSON-syntax error AND a
    # non-dict top level to None.
    meta_data = load_meta(meta_path.parent, on_malformed="none")
    if not isinstance(meta_data, dict):
        return _refused(MetaBranchRefusal.NOT_A_JSON_OBJECT, meta_path)
    if not mutate(copy.deepcopy(meta_data)):
        return MetaBranchWrite(MetaBranchOutcome.UNCHANGED, unchanged_on_read=True)
    # ``repo_root=main_repo`` keys the lock on the main repository's primary meta.json, never the
    # scratch copy. The lock is released before any ``git`` subprocess below runs.
    if locked_update_meta_capturing(meta_path.parent, mutate, repo_root=main_repo) is None:
        return MetaBranchWrite(MetaBranchOutcome.UNCHANGED)
    rel_meta = meta_path.relative_to(scratch)
    if path_is_under_worktrees(rel_meta):
        # FR-035: never stage a path under .worktrees/ (defense in depth).
        return _refused(MetaBranchRefusal.STAGE_PATH_UNDER_WORKTREES, rel_meta)
    # ``--only`` needs no prior ``git add``; hooks still run.
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "commit", "--only", "-m", message, "--", rel_meta.as_posix()],
        cwd=str(scratch),
        capture_output=True,
        check=True,
    )
    new_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(scratch),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    # Fast-forward the branch ref, resyncing any worktree that has it checked out (#1826 / AC-B2).
    # Toolchain churn on the primary checkout is excluded from the dirty gate through the single
    # canonical churn owner (#1878 / #2795 / FR-012).
    try:
        advance_branch_ref(main_repo, branch, new_sha, context=mission_residue_context(main_repo, mission_slug))
    except RefAdvanceDirtyWorktreeError as exc:
        # #7600 fold: the error names only the blocker; this is a consolidate step, so
        # append its next step (the lane/Mission merge text) and keep the type.
        from specify_cli.lanes.consolidation import lane_merge_error_text

        exc.args = (lane_merge_error_text(exc),)
        raise
    return MetaBranchWrite(MetaBranchOutcome.WRITTEN, new_sha=new_sha)
