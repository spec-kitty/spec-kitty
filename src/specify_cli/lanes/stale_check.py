"""Stale-lane merge blocker.

A lane branch is stale when:
1. The mission branch has advanced since the lane last incorporated it.
2. The changed files in the mission overlap with the lane's changed files.

This uses file-level intersection (git diff --name-only) rather than
glob-level matching to avoid false positives.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from kernel.git.listing import tree_entries
from kernel.git.runner import GitCommandError, decode_path, run_git
from specify_cli.core.vcs.git import git_diff_names, git_merge_base
from specify_cli.lanes.compute import is_planning_lane
from specify_cli.lanes.models import ExecutionLane
from specify_cli.state.contract import is_target_owned_path


@dataclass
class StaleCheckResult:
    """Result of a stale-lane check."""

    is_stale: bool
    stale_files: list[str] = field(default_factory=list)
    remediation: str | None = None


def check_lane_staleness(
    lane: ExecutionLane,
    lane_branch: str,
    mission_branch: str,
    repo_root: Path,
) -> StaleCheckResult:
    """Check if a lane branch has diverged from the mission branch on overlapping files.

    Algorithm:
    1. Find the merge-base between lane and mission branches.
    2. Collect the files changed by commits on the mission branch that the
       lane does not contain (``lane..mission``) → files mission has changed.
    3. Diff lane branch from merge-base → files lane has changed.
    4. Intersect the two sets.
    5. If non-empty, the lane is stale.

    Args:
        lane: The ExecutionLane being checked.
        lane_branch: Git branch name of the lane.
        mission_branch: Git branch name of the mission integration branch.
        repo_root: Path to the main repository.

    Returns:
        StaleCheckResult with is_stale, overlapping files, and remediation.
    """
    # Find merge-base.
    merge_base = git_merge_base(repo_root, lane_branch, mission_branch)
    if merge_base is None:
        # No common ancestor — branches are unrelated. Not stale.
        return StaleCheckResult(is_stale=False)

    # Files the mission branch changed that the lane does not already contain (#7311).
    mission_files = _mission_side_changes(repo_root, lane_branch, mission_branch, merge_base)

    if not mission_files:
        # Mission hasn't advanced with any file changes. Not stale.
        return StaleCheckResult(is_stale=False)

    # Files changed in lane since merge-base.
    lane_files = set(git_diff_names(repo_root, merge_base, lane_branch))

    # Intersection = files both sides changed.
    overlap = _filter_benign_overlaps(sorted(mission_files & lane_files), lane_branch, mission_branch, repo_root)

    if not overlap:
        return StaleCheckResult(is_stale=False)

    return StaleCheckResult(
        is_stale=True,
        stale_files=overlap,
        remediation=_stale_remediation(lane, lane_branch, mission_branch),
    )


def _mission_side_changes(repo_root: Path, lane_branch: str, mission_branch: str, merge_base: str) -> set[str]:
    """Paths changed by commits reachable from the mission branch but not from the lane (#7311).

    A change the lane already contains (for example a dependency lane's commit
    merged into both) is not mission-side work the lane lacks. A merge commit
    contributes only what its own resolution introduced (``--diff-merges=remerge``:
    the diff against git's automatic re-merge), so content a merge carried in from
    a parent is attributed to that parent's commits. A failed probe falls back to
    the whole ``merge_base..mission_branch`` diff, the strictest superset.
    """
    try:
        result = run_git(
            repo_root,
            "log",
            "--format=",
            "--name-only",
            "--no-renames",
            "--diff-merges=remerge",
            f"{lane_branch}..{mission_branch}",
            "--",
        )
    except GitCommandError:
        return set(git_diff_names(repo_root, merge_base, mission_branch))
    return {decode_path(line) for line in result.stdout.splitlines() if line.strip()}


def _filter_benign_overlaps(overlap: list[str], lane_branch: str, mission_branch: str, repo_root: Path) -> list[str]:
    """Drop overlaps that carry no semantic lane work, keeping the input order.

    Two kinds are benign (#5457):

    * target-owned bookkeeping (``is_target_owned_path``), which the upgrade
      writes on every branch;
    * any path whose tree entry (mode and object id, or absence) is identical at
      the lane tip and the mission tip: equal end states merge trivially.
    """
    candidates = [path for path in overlap if not is_target_owned_path(path)]
    if not candidates:
        return []
    lane_entries = _tree_entry_ids(repo_root, lane_branch, candidates)
    mission_entries = _tree_entry_ids(repo_root, mission_branch, candidates)
    if lane_entries is None or mission_entries is None:
        # A failed probe cannot prove identity: keep every candidate stale.
        return candidates
    return [path for path in candidates if lane_entries.get(path) != mission_entries.get(path)]


def _tree_entry_ids(repo_root: Path, ref: str, paths: list[str]) -> dict[str, tuple[str, str]] | None:
    """Map each of ``paths`` present at ``ref`` to ``(mode, object id)``; ``None`` when the probe fails."""
    try:
        entries = tree_entries(repo_root, ref, pathspecs=paths)
    except (GitCommandError, ValueError):
        return None
    return {str(entry.path): (entry.mode, entry.oid) for entry in entries}


def _stale_remediation(lane: ExecutionLane, lane_branch: str, mission_branch: str) -> str:
    """Build the operator-facing fix-it command for a stale lane.

    The canonical planning lane (:func:`is_planning_lane`) never has a
    ``.worktrees/`` entry -- it resolves to the repository-root checkout on
    the mission's target branch (see ``lane_branch_name``'s ``lane-planning``
    special case). Pointing that lane's remediation at a worktree glob names a
    directory that cannot exist by construction.

    A raw ``git merge`` on the planning lane frequently conflicts on
    ``status.json``: it is a derived projection of ``status.events.jsonl``
    (see ``_NON_DIVERGENT_CANONICAL_ARTIFACTS`` in
    ``tests/architectural/test_merge_reconciliation_class_guard.py`` --
    intentionally driver-exempt, so no ``.gitattributes`` merge driver is
    registered for it here). ``spec-kitty agent status materialize``
    deterministically rebuilds it from the event log, turning an
    unreconcilable git conflict into a regenerate-and-``git add`` step. This
    is verified for the same-schema conflict this remediation targets; the
    cross-schema all-zeros edge (a log written under a different status
    schema) is out of scope and tracked separately as #3531.

    A code lane's worktree may be absent (cleaned up, or never created on this
    clone), so the remedy names the branch and how to find or recreate its
    checkout instead of a ``cd .worktrees/*`` glob that may match nothing (#7311).
    """
    wp = lane.wp_ids[0] if lane.wp_ids else "<WP>"
    if is_planning_lane(lane):
        return (
            f"Lane {lane.lane_id} must incorporate mission changes before merging. "
            f"This lane runs in the repository-root checkout (no worktree) on "
            f"branch '{lane_branch}'. From the repository root: "
            f"git checkout {lane_branch} && git merge {mission_branch}. "
            f"If that merge reports a conflict on status.json (a derived "
            f"projection of status.events.jsonl that git cannot text-merge), "
            f"do not hand-edit it -- rebuild it from the event log instead: "
            f"spec-kitty agent status materialize --mission <id> && "
            f"git add kitty-specs/<id>/status.json"
        )
    return (
        f"Lane {lane.lane_id} must incorporate mission changes before merging. "
        f"In the checkout of branch '{lane_branch}' (find it with: git worktree list; "
        f"if none exists, recreate it with: spec-kitty implement {wp}), run: "
        f"git merge {mission_branch}"
    )
