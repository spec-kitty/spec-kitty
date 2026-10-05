"""Failure-atomic rollback of a failed create (git refs, coord surface, scaffolds).

Moved from ``mission_creation.py`` (#5634); reshaped by the decision-core and seam
cleanups. ``mission_creation`` re-exports every name defined here. A call to a name
tests patch on ``mission_creation``, or to a function another ``mission_creation*``
module owns, goes through a lazy in-function
``from specify_cli.core import mission_creation as _mc`` import (never at module scope).
"""

from __future__ import annotations

import contextlib
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.core.mission_creation_decisions import (
    CasReset,
    Delete,
    Noop,
    coord_rollback_action,
    coord_rollback_needs_current_tip,
    orphan_scaffold_candidates,
    plan_orphan_scaffold_removal,
)
from kernel.git import GitCommandError, tracked_paths
from specify_cli.core.git_ops import get_current_branch
from specify_cli.git.ref_advance import RefRestoreError, restore_branch_ref
from specify_cli.lanes.branch_naming import (
    strip_numeric_prefix,
)


# WP12 (FR-011 / #3339): coordination branches are the only branch refs a
# mission-create mints, and their names are all ``kitty/mission-<slug>-<mid8>``.
# The glob lets the failure-atomic rollback diff pre- vs post-create refs so it
# deletes exactly the orphan branch an aborted create left behind.
_COORDINATION_BRANCH_GLOB = "kitty/mission-*"


# ---------------------------------------------------------------------------
# Failure-atomic git rollback (WP12 / FR-011 / #3339)
# ---------------------------------------------------------------------------


def _list_coordination_branches(repo_root: Path) -> frozenset[str]:
    """Return the local ``kitty/mission-*`` branch names in ``repo_root``.

    Used to diff the coordination branches present before vs after a
    mission-create so the rollback deletes exactly the ref an aborted create
    minted, never a pre-existing one. A non-git or failing ``git`` invocation
    yields an empty set (nothing to roll back).
    """
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "branch",
            "--list",
            _COORDINATION_BRANCH_GLOB,
            "--format=%(refname:short)",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return frozenset()
    return frozenset(line.strip() for line in result.stdout.splitlines() if line.strip())


def _rev_parse_or_none(repo_root: Path, ref: str) -> str | None:
    """Return ``ref``'s commit SHA in ``repo_root``, or ``None`` on any failure."""
    result = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", ref],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _path_is_tracked_by_git(repo_root: Path, path: Path) -> bool:
    """True when git tracks any file under ``path``.

    Ordinary early refusals precede staging. A late refusal can follow the
    first scaffold commit, however, so preserve any indexed content. Refuse
    deletion whenever Git cannot establish that the path is disposable.
    """
    try:
        return bool(tracked_paths(repo_root, pathspecs=(str(path),)))
    except GitCommandError:
        # Refuse deletion whenever Git cannot establish that the path is disposable.
        return True


def _failure_is_disposable_create_refusal(exc: BaseException) -> bool:
    """Recognize commit preconditions whose recovery permits another create.

    Protection, checkout mismatch, and missing destination normally fail at
    preflight. Repeat checks at commit time can still refuse, so clean up only
    their new, untracked scaffolds. Persistence failures retain their explicit
    resume-probe evidence. Both scaffold and origin commits wrap exceptions;
    inspect their causes rather than only the surface type.
    """
    from specify_cli.git.commit_helpers import (
        ProtectedBranchRefused,
        SafeCommitDestinationNotFound,
        SafeCommitHeadMismatch,
    )

    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        if isinstance(current, (ProtectedBranchRefused, SafeCommitHeadMismatch, SafeCommitDestinationNotFound)):
            return True
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return False


def _plan_orphan_scaffold_removal(
    repo_root: Path,
    *,
    mission_slug: str,
    pre_existing_scaffolds: frozenset[str],
) -> tuple[Path, ...]:
    """Decide which scaffolds a failed create may delete — BEFORE any rollback.

    Rollback restores the original index as well as the branch ref. The index
    check must happen first, before it forgets files indexed by this create.
    """
    from specify_cli.core import mission_creation as _mc

    mission_slug = strip_numeric_prefix(mission_slug)
    post_names = _mc._list_mission_scaffolds(repo_root)
    candidates = orphan_scaffold_candidates(post_names=post_names, pre_names=pre_existing_scaffolds, mission_slug=mission_slug)
    # Tracking is probed per candidate, in sorted order, exactly as before.
    tracked = frozenset(name for name in candidates if _path_is_tracked_by_git(repo_root, repo_root / KITTY_SPECS_DIR / name))
    removable = plan_orphan_scaffold_removal(post_names=post_names, pre_names=pre_existing_scaffolds, mission_slug=mission_slug, tracked=tracked)
    return tuple(repo_root / KITTY_SPECS_DIR / name for name in removable)


def _remove_orphan_mission_scaffolds(planned: tuple[Path, ...]) -> None:
    """Remove only the disposable scaffolds identified before git rollback.

    Main's skipped bootstrap commits are successful creations and never reach
    this cleanup. An actual aborted create must not leave a second, untracked
    mission on retry. Indexed content and diagnostic failures are retained.
    Deletion is best-effort and must never mask the original failure.
    """
    for candidate in planned:
        with contextlib.suppress(OSError):
            shutil.rmtree(candidate)


@dataclass(frozen=True, slots=True)
class _CoordCreateRollbackContext:
    """Snapshot T032/FR-002a needs to undo a coordination surface a failed create produced.

    ``mission_slug_formatted`` and ``mid8`` are minted inside
    ``_create_mission_core_impl`` (brownfield scout, "Rollback (top risk)"),
    so the outer ``create_mission_core`` wrapper cannot name the coordination
    worktree any other way. The impl records this in the
    :class:`CreateRollbackJournal` the outer function passes in, as soon as the
    coordination branch name is known (right after ``_build_create_meta``
    returns) -- before the seed or the creation-events commit can fail.
    """

    #: The REPOSITORY root -- the coordination worktree always lives under it
    #: (``<repo_root>/.worktrees/...``), never under an owned checkout, so
    #: this is carried explicitly rather than reusing the caller's rollback
    #: root (which is the owned checkout for an owned create).
    repo_root: Path
    mission_slug_formatted: str
    mid8: str
    coordination_branch: str
    #: ``True`` when THIS create minted (or force-recreated) the branch --
    #: safe to delete on rollback. ``False`` means a pre-existing branch was
    #: silently reused (idempotent re-run); rollback must CAS-reset it to
    #: ``pre_seed_coord_tip`` instead of deleting another create's branch.
    coordination_branch_created: bool
    #: The branch's tip immediately after ``ensure_coordination_branch``
    #: returned, before this create's own seed/creation-events commit could
    #: move it. ``None`` when the branch did not exist yet (always true when
    #: ``coordination_branch_created`` is ``True``).
    pre_seed_coord_tip: str | None = None


@dataclass(slots=True)
class CreateRollbackJournal:
    """What a create produced that its failure-atomic wrapper must undo.

    ``create_mission_core`` makes one journal per create and passes it to
    ``_create_mission_core_impl``, which records into it as effects happen; the
    wrapper's ``except`` path reads it. Replaces the one-element list holder.
    """

    #: The coordination surface this create materialized, or ``None``.
    coord: _CoordCreateRollbackContext | None = None

    def record_coord(self, ctx: _CoordCreateRollbackContext) -> None:
        """Record the coordination surface; the first record wins, as the list holder's ``[0]`` did."""
        if self.coord is None:
            self.coord = ctx


def _rollback_coordination_surface(ctx: _CoordCreateRollbackContext) -> None:
    """Best-effort: undo the coordination worktree/branch a failed create produced (T032/US1.5).

    Never raises — a failure here must not mask the original creation
    failure. The worktree is torn down BEFORE the branch is touched, because
    git refuses to delete (or reset, while checked out) a branch that is
    checked out in a worktree.

    Every byte the coordination worktree holds at this point was written by
    THIS create (the seed and/or the creation-events commit — or nothing, if
    the failure struck before either ran): clearing the Mission dir before
    teardown is therefore sanctioned (D6), not a destructive-guard bypass —
    ``CoordinationWorkspace.teardown`` refuses a dirty worktree, and the
    untracked seed content left behind by an interrupted create would
    otherwise orphan the worktree forever.
    """
    from specify_cli.coordination.teardown import teardown_coordination_topology
    from specify_cli.missions._read_path_resolver import coord_feature_dir

    repo_root = ctx.repo_root
    coord_mission_dir = coord_feature_dir(repo_root, ctx.mission_slug_formatted, ctx.mid8)
    if coord_mission_dir.exists():
        with contextlib.suppress(OSError):
            shutil.rmtree(coord_mission_dir)
    with contextlib.suppress(Exception):
        # The single shared teardown seam; a half-created mission has no retrospective to persist,
        # and the surface being discarded is this create's own, so the ledger guard is skipped.
        teardown_coordination_topology(repo_root, ctx.mission_slug_formatted, ctx.mid8, persist=False, check_ledger=False)
    subprocess.run(
        ["git", "-C", str(repo_root), "worktree", "prune"],
        capture_output=True,
        text=True,
        check=False,
    )
    current_tip = None
    if coord_rollback_needs_current_tip(created=ctx.coordination_branch_created, pre_seed_tip=ctx.pre_seed_coord_tip):
        current_tip = _rev_parse_or_none(repo_root, ctx.coordination_branch)
    action = coord_rollback_action(
        created=ctx.coordination_branch_created,
        pre_seed_tip=ctx.pre_seed_coord_tip,
        current_tip=current_tip,
    )
    match action:
        case Delete():
            subprocess.run(
                ["git", "-C", str(repo_root), "branch", "-D", ctx.coordination_branch],
                capture_output=True,
                text=True,
                check=False,
            )
        case CasReset(expected=expected, to=to):
            # A pre-existing coordination branch this create reused is CAS-reset
            # to its own pre-create tip, never deleted (it may belong to another
            # mission's history, e.g. a prior ``force_recreate`` run).
            with contextlib.suppress(RefRestoreError):
                restore_branch_ref(repo_root, ctx.coordination_branch, to, expected_current_sha=expected)
        case Noop():
            return


def _restore_git_state_after_failed_create(
    repo_root: Path,
    *,
    original_branch: str | None,
    original_commit: str | None,
    original_index_tree: str | None,
    pre_existing_coordination_branches: frozenset[str],
    coord_rollback: _CoordCreateRollbackContext | None = None,
) -> None:
    """Best-effort rollback of a failed mission-create's git side-effects.

    Restores the operator's original checkout and deletes any coordination
    branch this create-run minted (FR-011, #3339), so a failed create leaves
    the operator on their original branch with no orphan branch.
    ``coord_rollback`` (T032/FR-002a), when supplied, additionally tears down
    the coordination worktree this create materialized before any branch is
    touched — see :func:`_rollback_coordination_surface`.

    Rollback is best-effort and never raises — it must not mask the original
    creation failure. The checkout is restored *before* any branch delete
    because git refuses to delete a branch that is currently checked out.

    Single-writer assumption: mission-create is an operator action, so the
    coordination-branch diff (present now minus present before) identifies
    exactly the ref this call minted.
    """

    # 1. Restore the operator's checkout first (a checked-out branch cannot be
    #    deleted).
    if original_branch is not None:
        current = get_current_branch(repo_root)
        if current is not None and current != original_branch:
            subprocess.run(
                ["git", "-C", str(repo_root), "checkout", original_branch],
                capture_output=True,
                text=True,
                check=False,
            )
        if original_commit is not None:
            current_tip_result = subprocess.run(
                ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=False,
            )
            current_tip = current_tip_result.stdout.strip() if current_tip_result.returncode == 0 else None
            if current_tip and current_tip != original_commit:
                # A late failure can occur after the metadata commit. Restore
                # only this branch ref with compare-and-swap; keep the partial
                # scaffold in the worktree for resume-probe diagnosis.
                with contextlib.suppress(RefRestoreError):
                    restore_branch_ref(
                        repo_root,
                        original_branch,
                        original_commit,
                        expected_current_sha=current_tip,
                    )
            if original_index_tree is not None:
                # Restore the exact pre-invocation index, including unrelated
                # staged user changes, without touching worktree files.
                subprocess.run(
                    ["git", "-C", str(repo_root), "read-tree", original_index_tree],
                    capture_output=True,
                    text=True,
                    check=False,
                )
    # 1.5. Undo the coordination worktree (and, for a branch THIS create
    #      minted, the branch too) before the generic branch-diff sweep below
    #      -- git refuses to delete a branch still checked out in a worktree.
    if coord_rollback is not None:
        _rollback_coordination_surface(coord_rollback)
    # 2. Delete only the coordination branches that appeared during this create.
    orphaned = _list_coordination_branches(repo_root) - pre_existing_coordination_branches
    for branch in sorted(orphaned):
        subprocess.run(
            ["git", "-C", str(repo_root), "branch", "-D", branch],
            capture_output=True,
            text=True,
            check=False,
        )
