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
from kernel.git.runner import GitCommandError
from specify_cli.core.vcs.git import git_diff_names, git_merge_base
from specify_cli.lanes.compute import is_planning_lane
from specify_cli.lanes.models import ExecutionLane
from specify_cli.state.contract import is_target_owned_path

#: Placeholders used when the remedy cannot name the concrete value.
MISSION_PLACEHOLDER = "<mission>"
WP_PLACEHOLDER = "<WP>"


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
    *,
    mission_slug: str | None = None,
) -> StaleCheckResult:
    """Check if a lane branch has diverged from the mission branch on overlapping files.

    Algorithm:
    1. Find the merge-base between lane and mission branches.
    2. Diff mission branch from merge-base → files mission has changed.
    3. Diff lane branch from merge-base → files lane has changed.
    4. Intersect the two sets.
    5. If non-empty, the lane is stale.

    Args:
        lane: The ExecutionLane being checked.
        lane_branch: Git branch name of the lane.
        mission_branch: Git branch name of the mission integration branch.
        repo_root: Path to the main repository.
        mission_slug: Mission handle the remedy names (``<mission>`` when unknown).

    Returns:
        StaleCheckResult with is_stale, overlapping files, and remediation.
    """
    # Find merge-base.
    merge_base = git_merge_base(repo_root, lane_branch, mission_branch)
    if merge_base is None:
        # No common ancestor — branches are unrelated. Not stale.
        return StaleCheckResult(is_stale=False)

    # Files changed in mission since merge-base.
    # FR-013: advisory only — a failed diff reads as "not stale"; nothing is written or skipped on it.
    mission_files = set(git_diff_names(repo_root, merge_base, mission_branch))

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
        remediation=_stale_remediation(lane, lane_branch, mission_branch, mission_slug=mission_slug),
    )


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


def _reentry_command(lane: ExecutionLane, mission_slug: str | None) -> str:
    """The A-10 re-entry command: re-running ``implement`` runs the lane sync point (auto-rebase)."""
    wp_id = lane.wp_ids[0] if len(lane.wp_ids) == 1 else WP_PLACEHOLDER
    return f"spec-kitty agent action implement {wp_id} --mission {mission_slug or MISSION_PLACEHOLDER}"


def _stale_remediation(
    lane: ExecutionLane,
    lane_branch: str,
    mission_branch: str,
    *,
    mission_slug: str | None = None,
) -> str:
    """Build the operator-facing fix-it command for a stale lane.

    A code lane (FR-091, #7285) is refreshed through the CLI, never by hand:
    re-running ``spec-kitty agent action implement <WP> --mission <handle>``
    runs the lifecycle sync point, which auto-rebases the lane onto the
    Mission branch (A-10, ``tests/lanes/test_stale_remediation_cli_command.py``).
    The remedy names no ``.worktrees/`` path and no ``git merge``.

    The canonical planning lane (:func:`is_planning_lane`) never has a
    ``.worktrees/`` entry -- it resolves to the repository-root checkout on
    the mission's target branch. The lane sync point skips repository-root
    lanes, so no ``spec-kitty`` command refreshes it and its remedy keeps the
    manual steps. A raw ``git merge`` on the planning lane frequently conflicts
    on ``status.json``, a derived projection of ``status.events.jsonl``;
    ``spec-kitty agent status materialize`` rebuilds it from the event log
    (the cross-schema edge is tracked separately as #3531).
    """
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
    handle = mission_slug or MISSION_PLACEHOLDER
    return (
        f"Lane {lane.lane_id} must incorporate changes from {mission_branch} before it is consolidated. "
        f"Refresh it through auto-rebase: {_reentry_command(lane, mission_slug)}"
        + ("" if len(lane.wp_ids) == 1 else f" (any WP of the lane: {', '.join(lane.wp_ids)})")
        + f". If the auto-rebase stops on a conflict, resolve it in the lane checkout the command names, "
        f"commit there, then re-run: spec-kitty consolidate --mission {handle}"
    )
