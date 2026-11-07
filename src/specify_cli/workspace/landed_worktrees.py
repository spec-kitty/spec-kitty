"""Landed-worktree assessment and prune (#7173, WP03).

An operator who lands a change through a pull request is left with its
worktree and local branch. :func:`assess_worktrees` gives every registered
worktree a verdict; :func:`prune_landed` removes only the ``landed`` ones.

Safety is the bar: nothing is removed unless its committed work is proven to
be on ``<remote>/<primary>``, nothing uncommitted is in it, and no process is
standing in it. ``<remote>`` defaults to ``origin`` and is selectable (#7214):
a clone whose canonical repository is another remote (the landing runbook's
``upstream``) proves against that remote's primary ref instead, and only that
ref — the proof is never "any remote that happens to contain the tip". The
verdict rule (``data-model.md``, first match wins):

1. main worktree, or the worktree ``current_dir`` is in -> ``excluded``
2. prunable (directory gone; git's own ``worktree prune`` territory) -> ``excluded``
3. bare -> ``excluded``
4. detached and outside ``<repo>/.worktrees/`` -> ``excluded``
   (``DETACHED_OUTSIDE_WORKTREES``): spec-kitty's own scratch checkouts
   (``kitty-merge-*``, review baselines) are detached and live elsewhere, and
   are owned by the command that made them. ``excluded`` rather than
   ``not_landed``: the verdict is about scope, not about where the work is,
   the same as the main and current worktrees.
5. a Mission branch (``parse_mission_slug_from_branch``) -> ``mission_owned``
   (report-only: ``consolidate``, ``retain_worktrees``, ``DESTROYED_LANE`` /
   ``LANE_WORK_TIP_UNKNOWN`` own those worktrees, C-004), except a lane of a
   consolidated or pr-accepted Mission with no active consolidation record and
   no retention (:func:`released_mission_lane`, FR-039): it goes on to the
   steps below like any other worktree
6. locked -> ``not_landed`` (``LOCKED``)
7. local state -> ``not_landed``: dirty by the guard's own predicate (tracked
   or untracked, nothing is residue), or an index entry flagged
   ``assume-unchanged`` / ``skip-worktree`` (``git status`` hides an edit
   behind either) -> ``UNCOMMITTED_CHANGES``; an ignored path holding a
   repository store (a ``.git`` / ``.hg`` / ``.jj`` / ``.svn`` entry, or a
   git dir under any name such as a bare ``mirror.git`` or a
   ``--separate-git-dir`` target: history of its own) ->
   ``NESTED_REPOSITORY``. Other ignored files such as ``.venv/`` do not count,
   but the removal deletes them, so they are listed on the verdict
   (``ignored_paths`` / ``ignored_count``). Before those: a rebase, merge,
   cherry-pick, revert or bisect in progress (its state lives only in the
   worktree's git dir) -> ``OPERATION_IN_PROGRESS``, except a rebase whose
   ``head-name`` is a Mission branch -> ``mission_owned`` (a rebasing lane is
   detached, so step 5 cannot see its branch).
8. the primary branch was not resolved from ``<remote>/HEAD`` or a common name
   (main, master, develop) -> ``unproven`` (``PRIMARY_UNRESOLVED``);
   ``refs/remotes/<remote>/<primary>`` missing -> ``unproven``
9. tip not absorbed into it (``lane_tip.is_absorbed``: ancestor, else a
   ``merge-tree --write-tree`` no-op; covers merge, rebase and squash
   landings) -> ``not_landed``; ``AbsorptionUnsupported`` -> ``unproven``
10. a branch whose tip is an ancestor of ``<remote>/<primary>`` and whose
    reflog records no commit (only creation, reset, pull, fast-forward merge,
    rebase... entries) ->
    ``not_landed`` (``NO_OWN_COMMITS``): nobody worked on it, so the prune
    does not decide for the operator that it is done. A branch with no
    reflog at all -> ``unproven`` (``REFLOG_MISSING``). An expired reflog
    therefore errs toward keeping the worktree.
11. process probe unavailable -> ``unproven``; a process cwd inside ->
    ``not_landed`` (``PROCESS_RUNNING``). One ``/proc`` scan serves every
    candidate (NFR-003). A same-uid process whose cwd cannot be read is
    skipped and counted in ``WorktreeAssessment.uninspected_processes``
    (operator ruling ``plan.prune.unreadable_process``: skip and report).
12. otherwise -> ``landed``

Nothing here contacts a remote (NFR-002): ``<remote>/<primary>`` is read as a
local ref, and naming a remote never turns into a fetch. A stale one mostly
under-reports (an older ref absorbs less), but it can also vouch for a commit
since force-pushed off the remote, so nothing the prune removes relies on it
to stay reachable.

The prune re-assesses each ``landed`` worktree right before it acts, then
hands the removal to :func:`~specify_cli.git.destructive_guard.guarded_landed_removal`,
which discharges the proof obligations of ADR 2026-11-06-1 (#7264) before it
destroys anything: the landing ref is a configured remote's tracking ref and
still absorbs the tip (O3, re-run with this module's absorption proof), the
worktree is still at that tip (O5), no process stands in it (O2, this
module's ``/proc`` probe), it is clean (O1), and the commits that would be
lost are recorded first (O4): a detached tip no local branch or tag reaches
under ``refs/spec-kitty/discarded/detached/<sha>``, and every commit that only
the worktree ``HEAD`` reflog or the branch reflog still reaches (#7211; local
refs only, and less those whose change is verbatim on the landing ref, O6) under
``refs/spec-kitty/discarded/reflog/<sha>``. The worktree is then removed
without ``--force`` (O7) and the branch deleted by compare-and-swap at the
proven tip (O5, #7212), with its tip recorded under
``refs/spec-kitty/discarded/<branch>`` when no local branch or tag holds its
commits. Every outcome carries the command that brings it back (O8). Every
refusal is recorded per worktree, under this report's vocabulary, and the run
continues (I1).

Residuals of the process probe (documented for operators, WP06): only
processes owned by the current uid are considered (U1), so another user's
process inside a worktree is not detected; and a process whose cwd cannot be
read (non-dumpable, or otherwise refused) is not detected either, only
counted.

A remote name the repository does not configure is refused before any verdict
(:func:`assess_worktrees` returns an ``error``), because a typo that reported
every worktree ``unproven`` would read as "nothing landed" — the silent
failure #7214 fixed.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from kernel.git import GitCommandError, decode_path, run_git
from kernel.git.listing import ignored_entries, index_entries
from kernel.git.remote import configured_remotes, tracking_ref
from specify_cli.git.worktree_listing import WorktreeEntry, worktree_entries
from specify_cli.coordination.coherence import NothingIsResidue
from specify_cli.core.git_ops import COMMON_PRIMARY_BRANCHES, resolve_primary_branch
from specify_cli.git.destructive_guard import (
    BRANCH_CHECKED_OUT,
    BRANCH_DELETE_REFUSED_BY_GIT,
    BRANCH_TIP_MOVED,
    LANDING_REF_UNNAMED,
    MERGE_UNSAFE_WORKTREE_DIRTY,
    NOT_LANDED_ON_NAMED_REMOTE,
    PROCESS_IN_WORKTREE,
    PROCESS_PROOF_UNAVAILABLE,
    WORKTREE_TIP_MOVED,
    AbsorptionProof,
    DestructiveOpRefused,
    LandedRemoval,
    LandedRemovalResult,
    ProcessProbe,
    assert_worktree_clean,
    guarded_landed_removal,
    recreate_command,
)
from specify_cli.lanes.branch_naming import parse_mission_slug_from_branch, resolve_mid8
from specify_cli.lanes.lane_tip import AbsorptionUnsupported, is_absorbed
from specify_cli.workspace.process_probe import ProcessProbeResult, processes_with_cwd_under

__all__ = [
    "BRANCH_DELETE_FAILED",
    "BRANCH_MOVED",
    "DEFAULT_REMOTE",
    "NOT_REGISTERED",
    "TIP_MOVED",
    "WORKTREE_REMOVE_FAILED",
    "ProbeFn",
    "PruneOutcome",
    "Reason",
    "Verdict",
    "WorktreeAssessment",
    "WorktreeVerdict",
    "assess_worktrees",
    "prune_landed",
]

DEFAULT_REMOTE = "origin"
"""The remote whose tracking refs prove a landing when the caller names none."""

ProbeFn = Callable[[Sequence[Path]], ProcessProbeResult]
"""The running-process probe; injectable so tests can fake ``/proc``."""

# Prune refusal codes beside the guard's own ``error_code`` values and the
# re-assessment ``Reason`` codes.
TIP_MOVED = "TIP_MOVED"
"""The worktree's HEAD changed between the assessment and the removal."""
NOT_REGISTERED = "NOT_REGISTERED"
"""The worktree is no longer registered when the prune reaches it."""
WORKTREE_REMOVE_FAILED = "WORKTREE_REMOVE_FAILED"
"""The guard could not run (e.g. the repository root could not be resolved)."""
BRANCH_MOVED = "BRANCH_MOVED"
"""The branch tip changed after the assessment; the branch is kept."""
BRANCH_DELETE_FAILED = "BRANCH_DELETE_FAILED"
"""The branch delete failed after the worktree was removed; the branch is kept."""


class Verdict(StrEnum):
    LANDED = "landed"
    NOT_LANDED = "not_landed"
    MISSION_OWNED = "mission_owned"
    UNPROVEN = "unproven"
    EXCLUDED = "excluded"


class Reason(StrEnum):
    UNCOMMITTED_CHANGES = "UNCOMMITTED_CHANGES"
    CONTENT_NOT_ON_PRIMARY = "CONTENT_NOT_ON_PRIMARY"
    PROCESS_RUNNING = "PROCESS_RUNNING"
    LOCKED = "LOCKED"
    PRUNABLE = "PRUNABLE"
    MISSION_LANE = "MISSION_LANE"
    PRIMARY_REF_MISSING = "PRIMARY_REF_MISSING"
    PRIMARY_UNRESOLVED = "PRIMARY_UNRESOLVED"
    NESTED_REPOSITORY = "NESTED_REPOSITORY"
    NO_OWN_COMMITS = "NO_OWN_COMMITS"
    REFLOG_MISSING = "REFLOG_MISSING"
    DETACHED_OUTSIDE_WORKTREES = "DETACHED_OUTSIDE_WORKTREES"
    PROCESS_PROOF_UNAVAILABLE = "PROCESS_PROOF_UNAVAILABLE"
    ABSORPTION_UNSUPPORTED = "ABSORPTION_UNSUPPORTED"
    MAIN_WORKTREE = "MAIN_WORKTREE"
    CURRENT_WORKTREE = "CURRENT_WORKTREE"
    BRANCH_IN_OTHER_WORKTREE = "BRANCH_IN_OTHER_WORKTREE"
    OPERATION_IN_PROGRESS = "OPERATION_IN_PROGRESS"
    LANDED = "LANDED"


_DETACHED_OUTSIDE_DETAIL = "a detached worktree outside .worktrees/ (a scratch checkout of another command)"

_GUARD_REFUSALS: dict[str, str] = {
    BRANCH_TIP_MOVED: BRANCH_MOVED,
    BRANCH_CHECKED_OUT: Reason.BRANCH_IN_OTHER_WORKTREE.value,
    BRANCH_DELETE_REFUSED_BY_GIT: BRANCH_DELETE_FAILED,
    WORKTREE_TIP_MOVED: TIP_MOVED,
    PROCESS_IN_WORKTREE: Reason.PROCESS_RUNNING.value,
    PROCESS_PROOF_UNAVAILABLE: Reason.PROCESS_PROOF_UNAVAILABLE.value,
    NOT_LANDED_ON_NAMED_REMOTE: Reason.CONTENT_NOT_ON_PRIMARY.value,
    LANDING_REF_UNNAMED: Reason.PRIMARY_REF_MISSING.value,
    MERGE_UNSAFE_WORKTREE_DIRTY: Reason.UNCOMMITTED_CHANGES.value,
}
"""The guard's refusals, under the vocabulary this report already uses (the others keep the guard's own code)."""

_SHOWN_IGNORED = 5
"""How many ignored path names a verdict carries (the count is always complete)."""


@dataclass(frozen=True)
class WorktreeVerdict:
    """One worktree's verdict.

    ``ignored_paths`` (at most five names, sorted) and ``ignored_count`` (all of
    them) describe the ignored files a removal deletes with the worktree, e.g.
    ``.venv/`` or ``.env``; both are empty unless the assessment reached the
    local-state step and found the worktree otherwise clean.
    """

    path: Path
    branch: str | None
    tip: str | None
    verdict: Verdict
    reason: Reason
    detail: str
    ignored_paths: tuple[str, ...] = ()
    ignored_count: int = 0

    @property
    def removable(self) -> bool:
        return self.verdict is Verdict.LANDED

    def to_json(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "branch": self.branch,
            "tip": self.tip,
            "verdict": self.verdict.value,
            "reason": self.reason.value,
            "detail": self.detail,
            "removable": self.removable,
            "ignored_paths": list(self.ignored_paths),
            "ignored_count": self.ignored_count,
        }


@dataclass(frozen=True)
class PruneOutcome:
    path: Path
    branch: str | None
    tip: str | None
    removed: bool
    branch_deleted: bool
    kept_ref: str | None
    recreate: str
    refusal: str | None
    kept_commits: tuple[str, ...] = ()

    def to_json(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "branch": self.branch,
            "tip": self.tip,
            "removed": self.removed,
            "branch_deleted": self.branch_deleted,
            "kept_ref": self.kept_ref,
            "recreate": self.recreate,
            "refusal": self.refusal,
            "kept_commits": list(self.kept_commits),
        }


@dataclass(frozen=True)
class WorktreeAssessment:
    """Every verdict of one assessment.

    ``uninspected_processes`` counts same-uid processes the process probe
    skipped because their cwd could not be read (0 when no worktree reached
    the probe step), so a report can say "N processes could not be inspected".
    ``remote`` names the remote the verdicts were proven against, so a payload
    can never be mistaken for one produced against another remote.
    """

    primary_ref: str | None
    verdicts: tuple[WorktreeVerdict, ...]
    error: str | None = None
    uninspected_processes: int = 0
    remote: str = DEFAULT_REMOTE

    def to_json(self) -> dict[str, Any]:
        return {
            "primary_ref": self.primary_ref,
            "verdicts": [verdict.to_json() for verdict in self.verdicts],
            "error": self.error,
            "uninspected_processes": self.uninspected_processes,
        }


@dataclass(frozen=True)
class _Context:
    repo_root: Path
    remote: str
    primary: str
    primary_resolved: bool
    primary_ref: str
    primary_ref_present: bool
    current: Path | None
    probe: ProbeFn

    @property
    def worktrees_dir(self) -> Path:
        return _resolved(self.repo_root / ".worktrees")


@dataclass(frozen=True)
class _Candidate:
    """A worktree that passed every check before the process probe, with the ignored paths its removal deletes."""

    ignored: tuple[str, ...]


def _resolved(path: Path) -> Path:
    return path.resolve(strict=False)


def _ref_exists(repo_root: Path, ref: str) -> bool:
    """A local ref read (``rev-parse --verify``); never a remote contact."""
    try:
        result = run_git(repo_root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", check=False)
    except GitCommandError:
        return False
    return result.returncode == 0


def _current_worktree(entries: Sequence[WorktreeEntry], current_dir: Path) -> Path | None:
    """The deepest registered worktree that contains ``current_dir`` (linked worktrees may nest in the main one)."""
    here = _resolved(current_dir)
    containing = [_resolved(entry.path) for entry in entries if here.is_relative_to(_resolved(entry.path))]
    return max(containing, key=lambda path: len(path.parts), default=None)


def _primary_resolved(repo_root: Path, primary: str, remote: str = DEFAULT_REMOTE) -> bool:
    """``True`` when ``primary`` came from ``refs/remotes/<remote>/HEAD`` or is a common primary name.

    ``resolve_primary_branch(bias=False)`` finally falls back to the checked-out
    branch; such a guess cannot be the reference that proves a landing.
    """
    if primary in COMMON_PRIMARY_BRANCHES:
        return True
    return _remote_head_branch(repo_root, remote) == primary


def _remote_head_branch(repo_root: Path, remote: str) -> str | None:
    """The branch ``refs/remotes/<remote>/HEAD`` points at, or ``None`` when unresolved.

    A local symbolic-ref read: :func:`kernel.git.remote.describe_remote_head`
    answers the same question by contacting the remote (``git remote show``),
    which this check must never do (NFR-002).
    """
    ref = f"refs/remotes/{remote}/HEAD"
    try:
        result = run_git(repo_root, "symbolic-ref", "--quiet", ref, check=False)
    except GitCommandError:
        return None
    if result.returncode != 0:
        return None
    target = decode_path(result.stdout).strip()
    prefix = f"refs/remotes/{remote}/"
    return target.removeprefix(prefix) if target.startswith(prefix) and len(target) > len(prefix) else None


def _primary_for(repo_root: Path, remote: str) -> str:
    """The primary branch name to prove against: the named remote's ``HEAD``, else the resolver.

    ``resolve_primary_branch`` is ``origin``-biased (its first probe is
    ``origin/HEAD``), so the named remote's own head wins when it has one.
    """
    return _remote_head_branch(repo_root, remote) or resolve_primary_branch(repo_root, bias=False)


def _context(
    repo_root: Path,
    entries: Sequence[WorktreeEntry],
    current_dir: Path,
    probe: ProbeFn,
    remote: str = DEFAULT_REMOTE,
) -> _Context:
    primary = _primary_for(repo_root, remote)
    primary_ref = tracking_ref(remote, primary)
    return _Context(
        repo_root=repo_root,
        remote=remote,
        primary=primary,
        primary_resolved=_primary_resolved(repo_root, primary, remote),
        primary_ref=primary_ref,
        primary_ref_present=_ref_exists(repo_root, primary_ref),
        current=_current_worktree(entries, current_dir),
        probe=probe,
    )


def _verdict(entry: WorktreeEntry, verdict: Verdict, reason: Reason, detail: str, ignored: Sequence[str] = ()) -> WorktreeVerdict:
    return WorktreeVerdict(
        path=entry.path,
        branch=entry.branch,
        tip=entry.head,
        verdict=verdict,
        reason=reason,
        detail=detail,
        ignored_paths=tuple(sorted(ignored)[:_SHOWN_IGNORED]),
        ignored_count=len(ignored),
    )


def _shown(paths: Sequence[str]) -> str:
    return ", ".join(paths[:_SHOWN_IGNORED]) + (" ..." if len(paths) > _SHOWN_IGNORED else "")


def _structural(entry: WorktreeEntry, is_main: bool, ctx: _Context) -> WorktreeVerdict | None:
    """Steps 1-5: what the worktree list alone decides."""
    if is_main:
        return _verdict(entry, Verdict.EXCLUDED, Reason.MAIN_WORKTREE, "the main worktree is never removed")
    if ctx.current is not None and _resolved(entry.path) == ctx.current:
        return _verdict(entry, Verdict.EXCLUDED, Reason.CURRENT_WORKTREE, "the command runs in this worktree")
    if entry.prunable:
        return _verdict(entry, Verdict.EXCLUDED, Reason.PRUNABLE, "its directory is gone; `git worktree prune` owns it")
    if entry.bare:
        return _verdict(entry, Verdict.EXCLUDED, Reason.MAIN_WORKTREE, "a bare repository entry")
    if entry.branch is None and not _resolved(entry.path).is_relative_to(ctx.worktrees_dir):
        return _verdict(entry, Verdict.EXCLUDED, Reason.DETACHED_OUTSIDE_WORKTREES, _DETACHED_OUTSIDE_DETAIL)
    if entry.branch is not None and parse_mission_slug_from_branch(entry.branch) is not None and not released_mission_lane(ctx.repo_root, entry.branch):
        return _verdict(entry, Verdict.MISSION_OWNED, Reason.MISSION_LANE, "a Mission branch; consolidate owns its worktree")
    if entry.locked:
        return _verdict(entry, Verdict.NOT_LANDED, Reason.LOCKED, "the worktree is locked")
    return None


def _mission_meta_for_lane(repo_root: Path, branch: str) -> dict[str, Any] | None:
    """The ``meta.json`` of the Mission whose lane ``branch`` is, matched by mid8 (new form) or slug (legacy); ``None`` when not exactly one."""
    parsed = parse_mission_slug_from_branch(branch)
    if parsed is None or parsed.lane_id is None:
        return None
    from specify_cli.context.mission_resolver import iter_kitty_specs_children
    from specify_cli.mission_metadata import load_meta_or_empty

    matches: list[dict[str, Any]] = []
    for mission_dir in iter_kitty_specs_children(repo_root):
        # Missing or unreadable meta.json: the Mission is skipped, as before (#7276).
        meta = load_meta_or_empty(mission_dir)
        if not meta:
            continue
        mission_id = str(meta.get("mission_id") or "")
        if parsed.mid8_token is not None:
            matched = resolve_mid8(mission_dir.name, mission_id=mission_id or None) == parsed.mid8_token
        else:
            matched = mission_dir.name == parsed.slug
        if matched:
            matches.append(meta)
    return matches[0] if len(matches) == 1 else None


def _is_released(meta: dict[str, Any]) -> bool:
    """Consolidated (``merged_at``) or accepted in pr mode."""
    if str(meta.get("merged_at") or "").strip():
        return True
    return bool(str(meta.get("accepted_at") or "").strip()) and meta.get("acceptance_mode") == "pr"


def released_mission_lane(repo_root: Path, branch: str) -> bool:
    """FR-039: a lane of a consolidated or pr-accepted Mission with no active consolidation record and no retention.

    Such a lane leaves the report-only ``mission_owned`` scope and is judged by the same proofs as any
    landed worktree (absorption, local state, process probe, the guard). Anything unreadable, an
    active record (``.kittify/runtime/merge/<mission_id>/state.json``) or a declared retention
    (``retain_worktrees`` / ``retain_branches`` present and not ``false``: a malformed value retains) keeps it report-only.
    """
    meta = _mission_meta_for_lane(repo_root, branch)
    if meta is None or not _is_released(meta):
        return False
    if any(key in meta and meta[key] is not False for key in ("retain_worktrees", "retain_branches")):
        return False
    mission_id = str(meta.get("mission_id") or "").strip()
    if not mission_id:
        return False
    return not os.path.lexists(repo_root / ".kittify" / "runtime" / "merge" / mission_id / "state.json")


def _flagged_index_paths(worktree: Path) -> list[str]:
    """Index entries flagged ``assume-unchanged`` (lowercase tag) or ``skip-worktree`` (``S``) whose file is on disk.

    ``git status`` hides an edit to either, so such a file may hold the only
    copy of a change. An entry whose file is absent (a sparse checkout's
    skip-worktree entries) has nothing on disk the removal could destroy.
    """
    flagged = [str(entry.path) for entry in index_entries(worktree, tags=True) if entry.tag and (entry.tag.islower() or entry.tag == "S")]
    return [path for path in flagged if os.path.lexists(worktree / path)]


def _ignored_paths(worktree: Path) -> list[str]:
    """The ignored, untracked paths in ``worktree``, collapsed to the outermost wholly ignored directory (``dir/``)."""
    return [f"{entry.path}/" if entry.is_directory else str(entry.path) for entry in ignored_entries(worktree)]


_VCS_STORE_NAMES = frozenset({".git", ".hg", ".jj", ".svn"})
"""Entry names that hold a version-control store (git, Mercurial, Jujutsu, Subversion)."""

_GIT_DIR_SUBDIRS = ("objects", "refs")


def _looks_like_git_dir(dirpath: str, dirnames: Sequence[str], filenames: Sequence[str]) -> bool:
    """git's own bare-repository heuristic: a ``HEAD`` file beside ``objects/`` and ``refs/``.

    Catches a git dir under any name: a bare clone (``mirror.git``) or a
    ``--separate-git-dir`` target.
    """
    return "HEAD" in filenames and all(name in dirnames for name in _GIT_DIR_SUBDIRS) and os.path.isfile(os.path.join(dirpath, "HEAD"))


def _holds_repository(path: Path) -> bool:
    """``True`` when ``path`` is, or holds anywhere beneath it, a repository store.

    A store is an entry named ``.git``, ``.hg``, ``.jj`` or ``.svn``, or a
    directory that looks like a git dir under any name. The walk stops at the
    first hit, never follows a symlink and never descends into a store.
    """
    if not path.is_dir() or path.is_symlink():
        return False
    for dirpath, dirnames, filenames in os.walk(path, followlinks=False):
        if _VCS_STORE_NAMES.intersection(dirnames) or _VCS_STORE_NAMES.intersection(filenames):
            return True
        if _looks_like_git_dir(dirpath, dirnames, filenames):
            return True
    return False


_OPERATION_MARKERS = ("rebase-merge", "rebase-apply", "MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "BISECT_LOG")
"""Git-dir entries that mark a rebase, merge, cherry-pick, revert or bisect in progress."""

_REBASE_HEAD_NAMES = ("rebase-merge/head-name", "rebase-apply/head-name")
"""The branch a rebase in progress will move when it finishes (``refs/heads/<b>``)."""


def _git_paths(worktree: Path, names: Sequence[str]) -> list[Path]:
    """``git rev-parse --git-path`` for each of ``names``, resolved against ``worktree``."""
    args = [arg for name in names for arg in ("--git-path", name)]
    listed = run_git(worktree, "rev-parse", *args)
    return [worktree / line for line in decode_path(listed.stdout).splitlines()]


def _rebased_branch(worktree: Path) -> str | None:
    """The branch a rebase in progress in ``worktree`` belongs to, or ``None``."""
    for head_name in _git_paths(worktree, _REBASE_HEAD_NAMES):
        if head_name.is_file():
            ref = head_name.read_text(encoding="utf-8").strip()
            return ref.removeprefix("refs/heads/") if ref.startswith("refs/heads/") else None
    return None


def _operation_in_progress(entry: WorktreeEntry) -> WorktreeVerdict | None:
    """A rebase/merge/cherry-pick/revert/bisect in progress: its state lives only in this worktree's git dir.

    A rebasing Mission lane is detached mid-rebase; its ``head-name`` still
    names the Mission branch, so it stays the Mission's.
    """
    active = [marker for marker in _git_paths(entry.path, _OPERATION_MARKERS) if os.path.lexists(marker)]
    if not active:
        return None
    rebased = _rebased_branch(entry.path)
    if rebased is not None and parse_mission_slug_from_branch(rebased) is not None:
        return _verdict(entry, Verdict.MISSION_OWNED, Reason.MISSION_LANE, f"a Mission branch ({rebased}) mid-rebase; consolidate owns its worktree")
    return _verdict(entry, Verdict.NOT_LANDED, Reason.OPERATION_IN_PROGRESS, f"a git operation is in progress: {_shown([marker.name for marker in active])}")


def _local_state(entry: WorktreeEntry) -> WorktreeVerdict | tuple[str, ...]:
    """Step 7: a verdict for local state the removal would destroy, or the ignored paths it deletes."""
    try:
        in_progress = _operation_in_progress(entry)
        if in_progress is not None:
            return in_progress
        assert_worktree_clean(entry.path, context=NothingIsResidue(), treat_untracked_as_dirty=True)
        flagged = _flagged_index_paths(entry.path)
        ignored = _ignored_paths(entry.path)
    except DestructiveOpRefused as exc:
        return _verdict(entry, Verdict.NOT_LANDED, Reason.UNCOMMITTED_CHANGES, f"local changes: {_shown(exc.dirty_entries)}")
    except (GitCommandError, RuntimeError, OSError) as exc:
        # Fail closed: a status that cannot be read proves nothing is uncommitted.
        return _verdict(entry, Verdict.NOT_LANDED, Reason.UNCOMMITTED_CHANGES, f"status could not be read: {exc}")
    if flagged:
        return _verdict(entry, Verdict.NOT_LANDED, Reason.UNCOMMITTED_CHANGES, f"hidden by index flag: {_shown(flagged)}")
    nested = [path for path in ignored if _holds_repository(entry.path / path)]
    if nested:
        return _verdict(entry, Verdict.NOT_LANDED, Reason.NESTED_REPOSITORY, f"a nested repository inside ignored: {_shown(nested)}")
    return tuple(ignored)


def _absorption(entry: WorktreeEntry, ctx: _Context) -> WorktreeVerdict | None:
    """Steps 8-9: is the tip's committed work on ``<remote>/<primary>``?"""
    if not ctx.primary_resolved:
        detail = f"the primary branch {ctx.primary!r} is only a guess: set it with `git remote set-head {ctx.remote} <branch>`"
        return _verdict(entry, Verdict.UNPROVEN, Reason.PRIMARY_UNRESOLVED, detail)
    if not ctx.primary_ref_present:
        return _verdict(
            entry,
            Verdict.UNPROVEN,
            Reason.PRIMARY_REF_MISSING,
            f"{ctx.primary_ref} does not exist locally: run `git fetch {ctx.remote}`",
        )
    if entry.head is None:
        return _verdict(entry, Verdict.NOT_LANDED, Reason.CONTENT_NOT_ON_PRIMARY, "the worktree has no commit")
    try:
        absorbed = is_absorbed(ctx.repo_root, entry.head, ctx.primary_ref, base=None)
    except AbsorptionUnsupported as exc:
        return _verdict(entry, Verdict.UNPROVEN, Reason.ABSORPTION_UNSUPPORTED, str(exc))
    if not absorbed:
        return _verdict(entry, Verdict.NOT_LANDED, Reason.CONTENT_NOT_ON_PRIMARY, f"{entry.head[:12]} has work not on {ctx.primary_ref}")
    return None


_OWN_COMMIT_ACTIONS = ("commit", "cherry-pick", "merge")
"""Reflog subject (``%gs``) prefixes that record a commit made on the branch.

``commit``, ``commit (amend)``, ``commit (merge)``, ``cherry-pick`` and a
``merge`` that made a merge commit count. ``branch: Created from``,
``reset``, ``pull``, a fast-forward ``merge ...: Fast-forward`` and
``rebase (finish)`` do not: they move the branch onto commits made elsewhere
(a rebase's own picks are recorded on ``HEAD``, not on the branch). Erring
this way only keeps more worktrees report-only."""

_FAST_FORWARD_SUFFIX = ": Fast-forward"


def _records_own_commit(subject: str) -> bool:
    return subject.startswith(_OWN_COMMIT_ACTIONS) and not (subject.startswith("merge") and subject.endswith(_FAST_FORWARD_SUFFIX))


def _is_ancestor(repo_root: Path, tip: str, ref: str) -> bool:
    """``True`` unless git says ``tip`` is NOT an ancestor of ``ref`` (an error counts as an ancestor: the stricter reflog check then applies)."""
    try:
        result = run_git(repo_root, "merge-base", "--is-ancestor", tip, ref, check=False)
    except GitCommandError:
        return True
    return result.returncode != 1


def _reflog_subjects(repo_root: Path, branch: str) -> list[str] | None:
    """The branch's reflog subjects, newest first; ``None`` when it has no reflog or it cannot be read."""
    ref = f"refs/heads/{branch}"
    try:
        if run_git(repo_root, "reflog", "exists", ref, check=False).returncode != 0:
            return None
        listed = run_git(repo_root, "reflog", "show", "--format=%gs", ref)
    except GitCommandError:
        return None
    subjects = decode_path(listed.stdout).splitlines()
    return subjects or None


def _own_commits(entry: WorktreeEntry, ctx: _Context) -> WorktreeVerdict | None:
    """Step 10: a branch sitting on ``<remote>/<primary>`` that nobody committed on is not the prune's to delete."""
    if entry.branch is None or entry.head is None or not _is_ancestor(ctx.repo_root, entry.head, ctx.primary_ref):
        return None
    subjects = _reflog_subjects(ctx.repo_root, entry.branch)
    if subjects is None:
        return _verdict(entry, Verdict.UNPROVEN, Reason.REFLOG_MISSING, f"branch {entry.branch} has no reflog; whether commits were made on it cannot be told")
    if not any(_records_own_commit(subject) for subject in subjects):
        return _verdict(entry, Verdict.NOT_LANDED, Reason.NO_OWN_COMMITS, "no commits were made on this branch; remove it by hand if you are done with it")
    return None


def _pre_probe(entry: WorktreeEntry, is_main: bool, ctx: _Context) -> WorktreeVerdict | _Candidate:
    early = _structural(entry, is_main, ctx)
    if early is not None:
        return early
    local = _local_state(entry)
    if isinstance(local, WorktreeVerdict):
        return local
    return _absorption(entry, ctx) or _own_commits(entry, ctx) or _Candidate(ignored=local)


def _after_probe(entry: WorktreeEntry, probe: ProcessProbeResult, ctx: _Context, candidate: _Candidate) -> WorktreeVerdict:
    """Steps 11-12."""
    if not probe.available:
        return _verdict(entry, Verdict.UNPROVEN, Reason.PROCESS_PROOF_UNAVAILABLE, probe.detail or "running processes cannot be checked", candidate.ignored)
    if entry.path in probe.busy:
        return _verdict(entry, Verdict.NOT_LANDED, Reason.PROCESS_RUNNING, "a process is running inside the worktree")
    return _verdict(entry, Verdict.LANDED, Reason.LANDED, f"{(entry.head or '')[:12]} is on {ctx.primary_ref}", candidate.ignored)


def _evaluate(entries: Sequence[WorktreeEntry], indices: Sequence[int], ctx: _Context) -> tuple[list[WorktreeVerdict], int]:
    """Verdicts for ``entries[i]`` for each ``i`` in ``indices``, in order, and the probe's uninspected count.

    One process probe serves every candidate that reaches step 9.
    """
    decided: dict[int, WorktreeVerdict] = {}
    uninspected = 0
    pending: dict[int, _Candidate] = {}
    for index in indices:
        early = _pre_probe(entries[index], index == 0, ctx)
        if isinstance(early, _Candidate):
            pending[index] = early
        else:
            decided[index] = early
    if pending:
        probe = ctx.probe([entries[index].path for index in pending])
        uninspected = probe.uninspected
        for index, candidate in pending.items():
            decided[index] = _after_probe(entries[index], probe, ctx, candidate)
    return [decided[index] for index in indices], uninspected


def _unconfigured_remote_error(repo_root: Path, remote: str) -> str | None:
    """The refusal for a remote name that cannot prove anything, else ``None``.

    A blank name (``--remote "$UNSET"``) is refused first: ``origin`` is the
    default for an *omitted* option, never a fallback for an empty one, or a
    script with an unset variable would silently prove against ``origin`` again.
    A name is otherwise only refused when the repository has remotes to compare
    it with: a clone with no remote at all keeps the older, quieter answer (every
    worktree ``unproven`` / ``PRIMARY_REF_MISSING``), and an unreadable remote
    list is no proof that the name is wrong. Both fall through to the missing
    ``<remote>/<primary>`` ref, which fails closed either way.
    """
    if not remote.strip():
        return f"a remote name is required; got {remote!r}"
    configured = configured_remotes(repo_root)
    if not configured or remote in configured:
        return None
    return f"no such remote {remote!r}; configured remotes: {', '.join(configured)}"


def assess_worktrees(
    repo_root: Path,
    *,
    current_dir: Path,
    probe: ProbeFn = processes_with_cwd_under,
    remote: str = DEFAULT_REMOTE,
) -> WorktreeAssessment:
    """One verdict per registered worktree, main worktree first. Read-only.

    ``remote`` names the remote whose primary ref proves a landing (default
    ``origin``). A remote the repository does not configure yields an ``error``
    and no verdicts rather than a report that reads as "nothing landed".
    """
    error = _unconfigured_remote_error(repo_root, remote)
    if error is not None:
        return WorktreeAssessment(primary_ref=None, verdicts=(), error=error, remote=remote)
    try:
        entries = worktree_entries(repo_root)
    except GitCommandError as exc:
        return WorktreeAssessment(primary_ref=None, verdicts=(), error=f"the worktree list cannot be read: {exc}", remote=remote)
    ctx = _context(repo_root, entries, current_dir, probe, remote)
    verdicts, uninspected = _evaluate(entries, range(len(entries)), ctx)
    return WorktreeAssessment(
        primary_ref=ctx.primary_ref,
        verdicts=tuple(verdicts),
        uninspected_processes=uninspected,
        remote=remote,
    )


def _reassess(repo_root: Path, path: Path, ctx: _Context) -> WorktreeVerdict | None:
    """A fresh verdict for the one worktree at ``path`` (fresh list entry, dirty check, absorption, probe)."""
    entries = worktree_entries(repo_root)
    target = _resolved(path)
    for index, entry in enumerate(entries):
        if _resolved(entry.path) == target:
            return _evaluate(entries, [index], ctx)[0][0]
    return None


def _recreate(verdict: WorktreeVerdict, *, refusal: str | None) -> str:
    """The command that brings back a worktree the prune refused to remove (its branch is kept)."""
    command: str = recreate_command(
        verdict.path,
        verdict.branch,
        verdict.tip or "",
        branch_kept=refusal is not None,
        checked_out_elsewhere=refusal == Reason.BRANCH_IN_OTHER_WORKTREE,
    )
    return command


def _outcome(verdict: WorktreeVerdict, *, refusal: str) -> PruneOutcome:
    """A worktree the prune kept: nothing was removed, ``refusal`` says why."""
    return PruneOutcome(
        path=verdict.path,
        branch=verdict.branch,
        tip=verdict.tip,
        removed=False,
        branch_deleted=False,
        kept_ref=None,
        recreate=_recreate(verdict, refusal=refusal),
        refusal=refusal,
    )


def _still_landed_refusal(repo_root: Path, verdict: WorktreeVerdict, ctx: _Context) -> str | None:
    """``None`` when a fresh assessment still says ``landed`` at the same tip; otherwise the refusal code (TOCTOU)."""
    try:
        fresh = _reassess(repo_root, verdict.path, ctx)
    except GitCommandError:
        return NOT_REGISTERED
    if fresh is None:
        return NOT_REGISTERED
    if not fresh.removable:
        return fresh.reason.value
    if fresh.tip != verdict.tip or fresh.branch != verdict.branch:
        return TIP_MOVED
    return None


def _process_probe(ctx: _Context) -> ProcessProbe:
    """O2 evidence for the guard: the prune's ``/proc`` probe for one worktree (``None`` when it cannot tell)."""

    def busy(path: Path) -> bool | None:
        result = ctx.probe([path])
        return (path in result.busy) if result.available else None

    return busy


def _absorption_proof(repo_root: Path) -> AbsorptionProof:
    """O3 evidence for the guard: ``lane_tip.is_absorbed``; an unsupported git is no proof."""

    def absorbed(tip: str, landing_ref: str) -> bool:
        try:
            proven: bool = is_absorbed(repo_root, tip, landing_ref, base=None)
            return proven
        except AbsorptionUnsupported:
            return False

    return absorbed


def _removed(verdict: WorktreeVerdict, result: LandedRemovalResult) -> PruneOutcome:
    refusal = _GUARD_REFUSALS.get(result.refusal, result.refusal) if result.refusal is not None else None
    return PruneOutcome(
        path=verdict.path,
        branch=verdict.branch,
        tip=verdict.tip,
        removed=True,
        branch_deleted=result.branch_deleted,
        kept_ref=result.kept_ref,
        recreate=result.recreate,
        refusal=refusal,
        kept_commits=result.kept_commits,
    )


def _prune_one(repo_root: Path, verdict: WorktreeVerdict, ctx: _Context) -> PruneOutcome:
    """Re-assess, then hand the removal to the guard, which discharges every proof obligation (ADR 2026-11-06-1)."""
    refusal = _still_landed_refusal(repo_root, verdict, ctx)
    if refusal is not None:
        return _outcome(verdict, refusal=refusal)
    if verdict.tip is None:
        return _outcome(verdict, refusal=TIP_MOVED)
    removal = LandedRemoval(worktree=verdict.path, branch=verdict.branch, tip=verdict.tip, remote=ctx.remote, landing_ref=ctx.primary_ref)
    try:
        result = guarded_landed_removal(
            repo_root,
            removal,
            context=NothingIsResidue(),
            processes_in=_process_probe(ctx),
            absorbed=_absorption_proof(repo_root),
        )
    except DestructiveOpRefused as exc:
        return _outcome(verdict, refusal=_GUARD_REFUSALS.get(exc.error_code, exc.error_code))
    except (GitCommandError, RuntimeError, OSError):
        return _outcome(verdict, refusal=WORKTREE_REMOVE_FAILED)
    return _removed(verdict, result)


def prune_landed(
    repo_root: Path,
    *,
    current_dir: Path,
    probe: ProbeFn = processes_with_cwd_under,
    assessment: WorktreeAssessment | None = None,
    remote: str | None = None,
) -> list[PruneOutcome]:
    """Remove each ``landed`` worktree, then its branch; one outcome per ``landed`` verdict.

    ``assessment`` lets a caller that already assessed (to report) reuse it;
    every worktree is re-assessed right before it is removed either way. An
    unreadable worktree list yields no outcome (``assess_worktrees`` reports it).
    ``remote`` is the remote whose primary ref proves a landing; omitted, it is
    the assessment's own remote (else ``origin``). Naming a different remote
    than the assessment was made against is a :class:`ValueError`: the verdicts
    would be reported against one remote and acted on against another.
    """
    if assessment is not None and remote is not None and remote != assessment.remote:
        raise ValueError(f"the assessment was proven against {assessment.remote!r}, not {remote!r}")
    proving = remote if remote is not None else (assessment.remote if assessment is not None else DEFAULT_REMOTE)
    current = assessment if assessment is not None else assess_worktrees(repo_root, current_dir=current_dir, probe=probe, remote=proving)
    landed = [verdict for verdict in current.verdicts if verdict.removable]
    if current.error is not None or not landed:
        return []
    try:
        ctx = _context(repo_root, worktree_entries(repo_root), current_dir, probe, proving)
    except GitCommandError:
        return []
    return [_prune_one(repo_root, verdict, ctx) for verdict in landed]
