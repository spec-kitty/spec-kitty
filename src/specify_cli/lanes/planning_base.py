"""The target-branch commit immediately before a Mission path first appeared (#7209, #7210).

The #6715 evidence window is ``planning_commit..<tip>``. Where no planning commit was ever
recorded, the one authority for a base read from git is :func:`resolve_planning_base_commit`.
Two callers anchor it on different Mission paths:

* ``consolidate --skip-lanes`` (#7209, ``consolidation.entry_preflight``): a Mission with no
  ``lanes.json`` anchors on the Mission directory, ``kitty-specs/<slug>/``.
* ``finalize-tasks`` (#7210, ``mission_finalize_planning_pin``): a ``lanes.json`` that predates the
  pin anchors on the work package task files, ``kitty-specs/<slug>/tasks/WP*.md``, through
  :func:`resolve_finalize_planning_base`, which also requires every lane branch to contain the
  base. On a direct history that is the tip a timely finalize would have recorded.

A derived base is a fact read from git and claims nothing about review (operator ruling
2026-11-05, ADR ``2026-10-04-5`` Amendment 2026-11-05). The window it opens can be wider than a
recorded one. The window itself stays computed only in ``consolidation.wp_evidence``.
"""

from __future__ import annotations

from pathlib import Path

from kernel.git import GitCommandError, run_git
from specify_cli.consolidation.git_probes import GitProbeError, commit_parents
from specify_cli.lanes.branch_naming import code_lane_branch_name

__all__ = ["mission_dir_pathspec", "resolve_finalize_planning_base", "resolve_planning_base_commit"]


def mission_dir_pathspec(mission_slug: str) -> str:
    """The Mission directory, ``kitty-specs/<slug>`` (the ``--skip-lanes`` anchor, #7209)."""
    return f"kitty-specs/{mission_slug}"


def mission_wp_tasks_pathspec(mission_slug: str) -> str:
    """The Mission's work package task files, ``kitty-specs/<slug>/tasks/WP*.md`` (the finalize anchor, #7210)."""
    return f":(glob)kitty-specs/{mission_slug}/tasks/WP*.md"


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


def resolve_finalize_planning_base(repo_root: Path, target_branch: str, mission_slug: str) -> str | None:
    """The base ``finalize-tasks`` and ``doctor mission-state --fix`` record for a pin-less Mission (#7210).

    :func:`resolve_planning_base_commit` over the Mission's ``tasks/WP*.md``, accepted only when
    every existing lane branch of the Mission contains it. The evidence window is a tree diff
    ``base..lane``, so a base holding content the lane never had reads that content as the lane's
    implementation: a work package with no commits would land. That happens when the tasks reach
    the target by a merge or a rebase after the lane was cut. No such base is recorded, so the
    fail-closed refusal stands.
    """
    base = resolve_planning_base_commit(repo_root, target_branch, mission_wp_tasks_pathspec(mission_slug))
    if base is None:
        return None
    pattern = f"refs/heads/{code_lane_branch_name(mission_slug, 'lane-*')}"
    try:
        lanes = run_git(repo_root, "for-each-ref", "--format=%(refname)", pattern).stdout.decode("utf-8", "replace").split()
        containing = run_git(repo_root, "for-each-ref", f"--contains={base}", "--format=%(refname)", pattern).stdout.decode("utf-8", "replace").split()
    except GitCommandError:
        return None
    return base if set(lanes) <= set(containing) else None
