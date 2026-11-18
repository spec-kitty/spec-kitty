"""Skip-worktree landing refusal for every consolidate (#7692).

Split out of :mod:`specify_cli.consolidation.preflight` at landing (#7696 NIT): a checkout the
landing writes into must not hide files from git with the skip-worktree or assume-unchanged bit.
"""

from __future__ import annotations

import os
import shlex
from pathlib import Path
from typing import TYPE_CHECKING

from kernel.git import GitCommandError, index_entries
from kernel.git import changed_paths as git_changed_paths
from specify_cli.core.constants import KITTY_SPECS_DIR

if TYPE_CHECKING:
    from specify_cli.coordination.types import Refused
    from specify_cli.lanes.models import LanesManifest

#: ``git ls-files -v`` tags: ``S`` is skip-worktree; a lowercase tag is assume-unchanged.
_SKIP_WORKTREE_TAG = "S"


def _index_bit(main_repo: Path, rel_path: Path) -> tuple[str, str] | None:
    """``(bit name, the command that clears it)`` when *rel_path* carries skip-worktree and/or assume-unchanged, else ``None``.

    ``ls-files -v`` tags ``S`` (skip-worktree), a lowercase letter (assume-unchanged) and ``s``
    (both). One ``update-index`` call clears only one of the two bits, so for ``s`` the command is
    two calls joined by ``&&`` (re-review LOW-4). A probe that cannot run reads as no bit: the
    primary-checkout precheck that follows refuses any probe failure on its own.
    """
    try:
        entries = index_entries(main_repo, pathspecs=(rel_path.as_posix(),), tags=True)
    except GitCommandError:
        return None
    tag = (entries[0].tag or "") if entries else ""
    path = shlex.quote(rel_path.as_posix())
    flags = [flag for flag, present in (("--no-skip-worktree", tag.upper() == _SKIP_WORKTREE_TAG), ("--no-assume-unchanged", tag.islower())) if present]
    if not flags:
        return None
    names = {"--no-skip-worktree": "skip-worktree", "--no-assume-unchanged": "assume-unchanged"}
    return " and ".join(names[flag] for flag in flags), " && ".join(f"git update-index {flag} {path}" for flag in flags)


#: ``ls-files -v`` tags of a skip-worktree entry: ``S``, or ``s`` when it also carries assume-unchanged (review SW-2).
_SKIP_WORKTREE_TAGS = frozenset({_SKIP_WORKTREE_TAG, _SKIP_WORKTREE_TAG.lower()})


#: A checkout the landing resyncs holds a skip-worktree index entry, its file present in the working
#: tree, at a path the landing writes: the resync's ``git reset --hard`` cannot update it.
CHECKOUT_SKIP_WORKTREE_ENTRIES = "CHECKOUT_SKIP_WORKTREE_ENTRIES"


def _present_skip_worktree_paths(checkout: Path) -> list[str]:
    """Index entries of *checkout* carrying the skip-worktree bit whose file EXISTS in its working tree.

    A sparse-checkout exclusion sets the same bit but leaves no file, so it is never listed: only a
    bit set by hand (``git update-index --skip-worktree``) is. A probe that cannot run lists nothing.
    """
    try:
        entries = index_entries(checkout, tags=True)
    except GitCommandError:
        return []
    flagged = (entry.path.as_posix() for entry in entries if entry.tag in _SKIP_WORKTREE_TAGS)
    return [path for path in dict.fromkeys(flagged) if os.path.lexists(checkout / path)]


def _landing_paths(main_repo: Path, target_branch: str, branches: list[str]) -> set[str]:
    """Every path the Mission and lane branches change since they left *target_branch* (``<target>...<branch>``)."""
    paths: set[str] = set()
    for branch in branches:
        try:
            paths.update(path.as_posix() for path in git_changed_paths(main_repo, f"{target_branch}...{branch}"))
        except GitCommandError:
            continue
    return paths


def skip_worktree_landing_refusal(main_repo: Path, mission_slug: str, lanes_manifest: LanesManifest, *, target_branch: str) -> Refused | None:
    """``CHECKOUT_SKIP_WORKTREE_ENTRIES`` when a checkout the run resyncs holds a skip-worktree entry it writes, else ``None``.

    The run moves the Mission branch (each lane is consolidated into it) and *target_branch* (the landing) with
    :func:`~specify_cli.git.ref_advance.advance_branch_ref`, which resyncs every checkout holding
    the branch, and writes its bookkeeping (``meta.json``, the status files) into the Mission
    directory of the checkout on the target. A skip-worktree entry there hides the run's own write
    from the bookkeeping commit: the post-merge ``meta.json`` (``baseline_merge_commit``) is left out
    ("No post-merge bookkeeping changes to commit"), the baseline validation fails, and the
    rollback's resync back to the snapshot then fails on the now-edited file ("not uptodate"),
    leaving the landing staged in the checkout and the merge record behind. Refusing Mission
    directory entries is the real fix. Entries on paths the Mission and lane branches change are
    refused conservatively: an EDITED skip-worktree file is invisible to ``git status`` and to the
    dirty-checkout gate, so the resync would overwrite or trip on it; an unedited one would land,
    and is refused anyway. The resync contract is unchanged.

    Judged per checkout holding *target_branch* or the Mission branch: its entries tagged ``S`` or
    ``s`` (skip-worktree, alone or with assume-unchanged) whose path exists in the working tree
    (``lexists``: a dangling symlink counts; a sparse-checkout exclusion has no file and never
    does), under the Mission directory or among the paths the Mission and lane branches change
    (:func:`_landing_paths`, read only when such an entry exists). An assume-unchanged bit alone is
    not refused: the bookkeeping commit stages its write. The index listing is ``ls-files``, which
    expands a sparse index in memory (git >= 2.35's ``--sparse`` is above the git floor). Read-only
    and lock-free; a probe that cannot run is left to the run's own refusals.
    """
    from specify_cli.coordination.types import Refused
    from specify_cli.git.ref_advance import RefAdvanceError, worktrees_with_branch_checked_out
    from specify_cli.lanes.compute import lane_created_branch

    mission_prefix = f"{KITTY_SPECS_DIR}/{mission_slug}/"
    written: set[str] | None = None
    for branch in dict.fromkeys(b for b in (target_branch, lanes_manifest.mission_branch) if b):
        try:
            checkouts = worktrees_with_branch_checked_out(main_repo, branch)
        except RefAdvanceError:
            continue
        for checkout in checkouts:
            flagged = _present_skip_worktree_paths(checkout)
            if not flagged:
                continue
            if written is None:
                branches = [lanes_manifest.mission_branch, *(lane_created_branch(lanes_manifest, lane.lane_id) for lane in lanes_manifest.lanes)]
                written = _landing_paths(main_repo, target_branch, [b for b in dict.fromkeys(branches) if b and b != target_branch])
            hits = [path for path in flagged if path.startswith(mission_prefix) or path in written]
            if hits:
                return _skip_worktree_refused(main_repo, checkout, branch, hits, Refused)
    return None


def _skip_worktree_refused(main_repo: Path, checkout: Path, branch: str, hits: list[str], refused: type[Refused]) -> Refused:
    quoted = " ".join(shlex.quote(path) for path in hits)
    git = "git" if checkout.resolve() == main_repo.resolve() else f"git -C {shlex.quote(str(checkout))}"
    return refused(
        error_code=CHECKOUT_SKIP_WORKTREE_ENTRIES,
        message=(
            f"the checkout at {checkout} holds '{branch}' and marks {len(hits)} file(s) this consolidation writes as "
            f"skip-worktree ({', '.join(hits[:5])}{', ...' if len(hits) > 5 else ''}); git would leave the run's writes "
            "out of its commits and could not resync the checkout."
        ),
        destination_ref=branch,
        next_step=(
            f"Clear the bit (`{git} update-index --no-skip-worktree {quoted}`), then re-run. If the checkout uses "
            f"sparse-checkout and these paths are excluded by its patterns (`{git} sparse-checkout list`), include them "
            f"instead (`{git} sparse-checkout add <dir>` or `{git} sparse-checkout disable`): git sets the bit again "
            "on the next checkout otherwise."
        ),
    )
