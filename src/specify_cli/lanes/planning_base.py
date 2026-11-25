"""The target-branch commit immediately before a Mission path first appeared (#7209, #7210).

The #6715 evidence window is ``planning_commit..<tip>``. Where no planning commit was ever
recorded, this module is the one authority for a base read from git, with two entry points:

* ``consolidate --skip-lanes`` (#7209, ``consolidation.entry_preflight``): a Mission with no
  ``lanes.json`` anchors on the Mission directory, ``kitty-specs/<slug>/``, through
  :func:`resolve_planning_base_commit` (the first appearance).
* ``finalize-tasks`` and ``doctor mission-state --fix`` (#7210): a ``lanes.json`` that predates the
  pin anchors on the Mission's task files (``tasks/*.md`` but the scaffold ``README.md``) through
  :func:`resolve_finalize_planning_base`: the last appearance (#7297 items 4 and 5), and every lane
  branch must contain the base. On a direct history that is the tip a timely finalize would have
  recorded.

A derived base is a fact read from git and claims nothing about review (operator ruling
2026-11-05, ADR ``2026-10-04-5`` Amendment 2026-11-05). The window it opens can be wider than a
recorded one. The window itself stays computed only in ``consolidation.wp_evidence``.

Two more pin facts live here so the pin has one authority (#7793, #7297, ADR ``2026-10-04-5``
Amendment 2026-11-22):

* :func:`pin_branch_line` -- the branch a Mission's pin is captured from, refreshed against and
  derived on. For a ``single_branch`` Mission that is its ``mission_branch``, the tip of its
  evidence window ``planning_commit..mission_branch``; otherwise the target branch.
* :func:`follow_pin_by_patch_id` -- the rebased copy of an orphaned pin: the one commit on the
  branch with the same patch-id. A rebase rewrites SHAs and keeps each commit's change.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from kernel.git import GitCommandError, NameStatusEntry, changed_entries, run_git
from specify_cli.consolidation.git_probes import GitProbeError, commit_parents, commits_in_range, patch_id_of
from specify_cli.lanes.branch_naming import code_lane_branch_name

__all__ = [
    "follow_pin_by_patch_id",
    "mission_dir_pathspec",
    "pin_branch_line",
    "resolve_finalize_planning_base",
    "resolve_planning_base_commit",
]

#: git's empty tree: the "parent" a root commit's changes are read against.
_EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

PatchIdMiss = Literal["no_patch_id", "no_match", "ambiguous", "upstream_only"]


def mission_dir_pathspec(mission_slug: str) -> str:
    """The Mission directory, ``kitty-specs/<slug>`` (the ``--skip-lanes`` anchor, #7209)."""
    return f"kitty-specs/{mission_slug}"


def mission_task_files_pathspecs(mission_slug: str) -> tuple[str, str]:
    """Every task file of the Mission, ``tasks/*.md`` except the scaffold's ``README.md`` (#7297 item 5).

    Anchoring on any task file, not only ``WP*.md``, keeps a task file first committed under
    another name and renamed to ``WP*`` later from moving the base past the work (a late pin).
    ``mission create`` scaffolds ``tasks/README.md``; it is no task, so it never anchors.
    """
    return (f":(glob)kitty-specs/{mission_slug}/tasks/*.md", f":(exclude)kitty-specs/{mission_slug}/tasks/README.md")


def pin_branch_line(meta: Mapping[str, Any], target_branch: str) -> str:
    """The branch the pin is captured from, refreshed against and derived on (#7297 item 2).

    A STORED ``single_branch`` Mission that records a ``mission_branch`` reads its evidence window
    as ``planning_commit..mission_branch``, so its pin belongs on that branch: a pin taken from the
    target tip sits below the branch's fork point, and a rebase onto a newer target then widens the
    window to the target's new commits. Every other Mission keeps *target_branch*. Pure: no git.
    """
    from mission_runtime import is_single_branch

    from specify_cli.migration.backfill_topology import stored_topology

    mission_branch = meta.get("mission_branch")
    if isinstance(mission_branch, str) and mission_branch.strip() and is_single_branch(stored_topology(meta)):
        return mission_branch
    return target_branch


@dataclass(frozen=True)
class PatchIdFollow:
    """Where an orphaned pin went: the one commit with its patch-id (``sha``), or why none (``miss``).

    Exactly one of ``sha`` / ``miss`` is set. ``candidates`` lists the matches that count (two or
    more only for ``miss == "ambiguous"``); ``upstream_only`` means every match is on an upstream.
    """

    sha: str | None
    miss: PatchIdMiss | None = None
    candidates: tuple[str, ...] = ()


def follow_pin_by_patch_id(repo_root: Path, pin: str, tip: str, *, upstream_refs: tuple[str, ...] = ()) -> PatchIdFollow:
    """The rebased copy of the orphaned *pin* on *tip*'s history, matched by patch-id (#7793).

    Scans ``merge-base(pin, tip)..tip``: the commits the rebase rewrote plus the upstream commits it
    moved onto, one patch-id each (bounded). A pin with an empty diff (a merge, an empty commit)
    has no patch-id to follow (``no_patch_id``); no equal patch-id is ``no_match``; more than one
    is ``ambiguous``. Never guesses, never returns the tip for lack of a match.

    A match reachable from one of *upstream_refs* (the target and primary branches) is the
    upstream's own copy, not the Mission's: when the planning change also landed upstream, the
    rebase drops the Mission's copy as already applied, and pinning the upstream copy would open
    the window over every upstream commit after it (#7793 review B2). Such matches never count;
    when they are the only ones the miss is ``upstream_only``.

    Raises:
        GitProbeError: a git probe failed. The caller refuses rather than read it as a miss.
    """
    wanted = patch_id_of(repo_root, pin)
    if not wanted:
        return PatchIdFollow(sha=None, miss="no_patch_id")
    try:
        base = run_git(repo_root, "merge-base", pin, tip).stdout.decode("utf-8", "replace").strip()
    except GitCommandError as exc:
        # ``merge-base`` exits 1 with no output when the two histories share no commit.
        if exc.returncode == 1 and not exc.stderr.strip():
            base = ""
        else:
            raise GitProbeError(f"git merge-base {pin} {tip} failed: {exc}") from exc
    matches = tuple(sha for sha in (commits_in_range(repo_root, base, tip) if base else _all_commits(repo_root, tip)) if patch_id_of(repo_root, sha) == wanted)
    candidates = tuple(sha for sha in matches if not _on_any_upstream(repo_root, sha, upstream_refs))
    if matches and not candidates:
        return PatchIdFollow(sha=None, miss="upstream_only")
    if len(candidates) == 1:
        return PatchIdFollow(sha=candidates[0], candidates=candidates)
    return PatchIdFollow(sha=None, miss="ambiguous" if candidates else "no_match", candidates=candidates)


def _on_any_upstream(repo_root: Path, sha: str, upstream_refs: tuple[str, ...]) -> bool:
    """True when *sha* is reachable from one of *upstream_refs* (a missing ref reaches nothing)."""
    for ref in upstream_refs:
        try:
            run_git(repo_root, "merge-base", "--is-ancestor", sha, ref)
        except GitCommandError as exc:
            if exc.returncode == 1:
                continue  # not an ancestor
            if run_git(repo_root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", check=False).returncode != 0:
                continue  # the ref does not exist here
            raise GitProbeError(f"git merge-base --is-ancestor {sha} {ref} failed: {exc}") from exc
        return True
    return False


def _all_commits(repo_root: Path, tip: str) -> list[str]:
    """Every commit reachable from *tip* (unrelated histories: no merge-base bounds the scan)."""
    try:
        out = run_git(repo_root, "rev-list", tip).stdout.decode("utf-8", "replace")
    except GitCommandError as exc:
        raise GitProbeError(f"git rev-list {tip} failed: {exc}") from exc
    return [line for line in out.splitlines() if line.strip()]


def resolve_planning_base_commit(repo_root: Path, target_branch: str, pathspec: str) -> str | None:
    """The target-branch commit immediately before *pathspec* first appeared on *target_branch*.

    The earliest commit on the target's FIRST-PARENT line that touched *pathspec*; the base is
    that commit's first parent.

    ``--first-parent`` is load-bearing (#7209 review): plain ``git log`` follows side branches, so
    the oldest commit touching the path can be a planning branch cut from a much older tip,
    merged in later. Its parent then predates unrelated work that already landed on the target, and
    the over-broad window would admit an approved work package whose owned file only changed BEFORE
    the Mission appeared. Walking the first-parent line picks the commit where the path first
    appeared ON the target (a direct commit, or the merge that brought it in).

    Known limit, tracked as #7229: the window is a tree diff, so it cannot tell "the target gained
    this path after the Mission started" from "the Mission's own branch merged the target in and
    the target was then fast-forwarded onto that merge" -- there the base lands below the Mission's
    artifacts and pre-Mission content is inside the window. A ref's prior tip cannot be
    reconstructed from refs (reflogs are local), and every cheap ancestry probe either misses it or
    false-refuses ordinary histories.

    The PARENT is the base, not the introducing commit itself: a Mission whose first commit carries
    its planning artifacts AND a work-package change together (a squashed history, the shape of the
    #2745 fixture) would otherwise get an empty window and a false ``IMPLEMENTATION_MISSING``. A
    root introducing commit has no parent and is its own base.

    Returns ``None`` when the path never reached the target branch's history, git cannot read it,
    or the repository is shallow (a shallow boundary has no parents, so it would pass as a root).
    Never fabricates a base (no timestamp, no current tip): an unresolvable window keeps the
    fail-closed refusal.
    """
    try:
        if run_git(repo_root, "rev-parse", "--is-shallow-repository").stdout.strip() == b"true":
            return None
        history = run_git(repo_root, "log", "--first-parent", "--format=%H", target_branch, "--", pathspec)
    except GitCommandError:
        return None
    commits = [line.strip() for line in history.stdout.decode("utf-8", "replace").splitlines() if line.strip()]
    if not commits:
        return None
    introducing = commits[-1]  # ``git log`` prints newest first
    try:
        parents = commit_parents(repo_root, introducing)
    except (GitProbeError, OSError):
        # An unreadable parent probe is "no base" (fail closed), never an exception out of
        # the caller while it still has work to judge.
        return None
    return parents[0] if parents else introducing


def _last_appearance_base(repo_root: Path, branch: str, pathspecs: tuple[str, ...]) -> str | None:
    """The first parent of the commit after which *pathspecs* last went from absent to present.

    The #7209 walk (first-parent, the parent is the base, a root is its own base, shallow refuses),
    with one change for #7297 item 4: tasks removed and later re-added anchor on the re-add. The
    first-ever touch would open the window over everything committed while no task existed.
    """
    try:
        if run_git(repo_root, "rev-parse", "--is-shallow-repository").stdout.strip() == b"true":
            return None
        history = run_git(repo_root, "log", "--first-parent", "--reverse", "--format=%H", branch, "--", *pathspecs)
    except GitCommandError:
        return None
    commits = [line.strip() for line in history.stdout.decode("utf-8", "replace").splitlines() if line.strip()]
    present: set[str] = set()
    introducing: str | None = None
    for commit in commits:
        try:
            entries = _first_parent_changes(repo_root, commit, pathspecs)
        except (GitCommandError, GitProbeError, OSError):
            return None
        was_empty = not present
        for entry in entries:
            if entry.status.startswith("D"):
                present.discard(str(entry.path))
            else:
                present.add(str(entry.path))
        if was_empty and present:
            introducing = commit
    if introducing is None:
        return None
    try:
        parents = commit_parents(repo_root, introducing)
    except (GitProbeError, OSError):
        return None
    return parents[0] if parents else introducing


def _first_parent_changes(repo_root: Path, commit: str, pathspecs: tuple[str, ...]) -> tuple[NameStatusEntry, ...]:
    """*commit*'s changes to *pathspecs* against its first parent (a root commit: against nothing)."""
    parents = commit_parents(repo_root, commit)
    base = parents[0] if parents else _EMPTY_TREE
    entries: tuple[NameStatusEntry, ...] = changed_entries(repo_root, base, commit, pathspecs=pathspecs, glob=True)
    return entries


def resolve_finalize_planning_base(repo_root: Path, target_branch: str, mission_slug: str) -> str | None:
    """The base ``finalize-tasks`` and ``doctor mission-state --fix`` record for a pin-less Mission (#7210).

    The commit before the Mission's task files (``tasks/*.md`` but the scaffold ``README.md``) last
    appeared on *target_branch*'s first-parent line (:func:`_last_appearance_base`; #7297 items 4
    and 5), accepted only when every existing lane branch of the Mission contains it. Callers pass
    the pin branch line (:func:`pin_branch_line`) as *target_branch*. The evidence window is a tree
    diff ``base..lane``, so a base holding content the lane never had reads that content as the
    lane's implementation: a work package with no commits would land. That happens when the tasks
    reach the target by a merge or a rebase after the lane was cut. No such base is recorded, so
    the fail-closed refusal stands.
    """
    base = _last_appearance_base(repo_root, target_branch, mission_task_files_pathspecs(mission_slug))
    if base is None:
        return None
    pattern = f"refs/heads/{code_lane_branch_name(mission_slug, 'lane-*')}"
    try:
        lanes = run_git(repo_root, "for-each-ref", "--format=%(refname)", pattern).stdout.decode("utf-8", "replace").split()
        containing = run_git(repo_root, "for-each-ref", f"--contains={base}", "--format=%(refname)", pattern).stdout.decode("utf-8", "replace").split()
    except GitCommandError:
        return None
    return base if set(lanes) <= set(containing) else None
