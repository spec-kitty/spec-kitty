"""Stale-lane merge blocker.

A lane branch is stale when:
1. The mission branch carries commits the lane does not contain (``lane..mission``;
   a change the lane already holds, e.g. a dependency lane merged into both, does
   not count, #7311).
2. The files those commits change overlap with the lane's changed files.

This uses file-level intersection (git diff --name-only) rather than
glob-level matching to avoid false positives.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path

from kernel.git.listing import log_paths, tree_entries
from kernel.git.runner import GitCommandError, run_git
from specify_cli.core.vcs.git import git_diff_names, git_merge_base
from specify_cli.lanes.compute import is_planning_lane
from specify_cli.lanes.models import ExecutionLane
from specify_cli.state.contract import is_target_owned_path

#: Placeholders used when the remedy cannot name the concrete value.
MISSION_PLACEHOLDER = "<mission>"
WP_PLACEHOLDER = "<WP>"
#: ``implement`` refuses to start or resume a work package without ``--agent`` (who works on it).
AGENT_PLACEHOLDER = "<agent>"


@dataclass(frozen=True)
class SiblingLane:
    """Another lane of the Mission whose consolidated change makes a lane stale (#7755)."""

    lane_id: str
    branch: str


@dataclass
class StaleCheckResult:
    """Result of a stale-lane check.

    ``auto_rebase_halt`` is the reason the in-run auto-rebase stopped (``None`` when none ran);
    ``sibling_lanes`` are the lanes whose consolidated change overlaps ``stale_files`` and is
    missing from the stale lane. Both are filled in by :func:`refine_stale_result` (#7755).
    """

    is_stale: bool
    stale_files: list[str] = field(default_factory=list)
    remediation: str | None = None
    auto_rebase_halt: str | None = None
    sibling_lanes: tuple[SiblingLane, ...] = ()


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
        mission_slug: Mission handle the remedy names (``<mission>`` when unknown).

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
        remediation=_stale_remediation(lane, lane_branch, mission_branch, mission_slug=mission_slug),
    )


def _mission_side_changes(repo_root: Path, lane_branch: str, mission_branch: str, merge_base: str) -> set[str]:
    """Paths changed by commits reachable from the mission branch but not from the lane (#7311).

    A change the lane already contains (for example a dependency lane's commit
    merged into both) is not mission-side work the lane lacks. A merge commit
    contributes only what its own resolution introduced (``--diff-merges=remerge``:
    the diff against git's automatic re-merge), so content a merge carried in from
    a parent is attributed to that parent's commits (an octopus merge, which git skips
    under ``remerge``, contributes its full diff against its first parent). A failed probe falls back to
    the whole ``merge_base..mission_branch`` diff, the strictest superset.
    """
    try:
        paths = log_paths(repo_root, f"{lane_branch}..{mission_branch}", remerge_merges=True)
    except GitCommandError:
        return set(git_diff_names(repo_root, merge_base, mission_branch))
    return {str(path) for path in paths}


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


def find_sibling_lanes(
    repo_root: Path,
    lane_branch: str,
    mission_branch: str,
    candidates: Sequence[SiblingLane],
    stale_files: Sequence[str],
) -> tuple[SiblingLane, ...]:
    """The *candidates* whose change makes the lane stale (#7755), in candidate order.

    A candidate counts when the Mission branch reaches its branch tip (it was consolidated)
    and a commit on it that the lane lacks (``lane..candidate``) touches one of
    *stale_files*. Two git probes per candidate, run only on the stale path. A failed probe
    drops that candidate: the remedy then falls back to the Mission-branch wording.
    """
    wanted = set(stale_files)
    found: list[SiblingLane] = []
    for candidate in candidates:
        if candidate.branch in (lane_branch, mission_branch):
            continue
        try:
            reached = run_git(repo_root, "merge-base", "--is-ancestor", candidate.branch, mission_branch, check=False).returncode == 0
            if reached and wanted & {str(path) for path in log_paths(repo_root, f"{lane_branch}..{candidate.branch}")}:
                found.append(candidate)
        except GitCommandError:
            continue
    return tuple(found)


def refine_stale_result(
    result: StaleCheckResult,
    lane: ExecutionLane,
    lane_branch: str,
    mission_branch: str,
    *,
    mission_slug: str | None = None,
    auto_rebase_halt: str | None = None,
    sibling_lanes: Sequence[SiblingLane] = (),
) -> StaleCheckResult:
    """*result* with the in-run auto-rebase halt reason and the sibling lanes, its remedy rebuilt (#7755)."""
    if not result.is_stale:
        return result
    siblings = tuple(sibling_lanes)
    return replace(
        result,
        auto_rebase_halt=auto_rebase_halt,
        sibling_lanes=siblings,
        remediation=_stale_remediation(
            lane,
            lane_branch,
            mission_branch,
            mission_slug=mission_slug,
            auto_rebase_halt=auto_rebase_halt,
            sibling_lanes=siblings,
        ),
    )


def _reentry_command(lane: ExecutionLane, mission_slug: str | None) -> str:
    """The A-10 re-entry command: re-running ``implement`` runs the lane sync point (auto-rebase)."""
    wp_id = lane.wp_ids[0] if len(lane.wp_ids) == 1 else WP_PLACEHOLDER
    return f"spec-kitty agent action implement {wp_id} --mission {mission_slug or MISSION_PLACEHOLDER}"


def _reopen_step(lane: ExecutionLane, handle: str) -> str:
    """#7754: at ``consolidate`` every WP is approved and ``implement`` refuses an approved WP, so reopen first."""
    wp_ids = lane.wp_ids or (WP_PLACEHOLDER,)
    commands = " and ".join(f"spec-kitty agent tasks move-task {wp_id} --to planned --review-feedback-file <file> --mission {handle}" for wp_id in wp_ids)
    noun = "work package is" if len(wp_ids) == 1 else "work packages are"
    return (
        f"The lane's {noun} approved and `spec-kitty agent action implement` refuses an approved work package, "
        f"so reopen {'it' if len(wp_ids) == 1 else 'each of them'} first (this costs a re-review): {commands}."
    )


def _cause_sentence(lane: ExecutionLane, mission_branch: str, siblings: tuple[SiblingLane, ...]) -> str:
    """What the lane lacks: a sibling lane's branch (#7755), else the Mission branch."""
    if not siblings:
        return f"Lane {lane.lane_id} must incorporate changes from {mission_branch} before it is consolidated."
    named = ", ".join(f"lane {sibling.lane_id} (branch {sibling.branch})" for sibling in siblings)
    return (
        f"The overlapping change comes from {named}, consolidated into {mission_branch} ahead of it. "
        f"Rolling {mission_branch} back to its pre-run tip can remove that change again, so refreshing from "
        f"{mission_branch} can bring in nothing: lane {lane.lane_id} must incorporate "
        f"{'that branch' if len(siblings) == 1 else 'those branches'} itself before it is consolidated."
    )


def _refresh_step(lane: ExecutionLane, mission_slug: str | None) -> str:
    """Re-enter the lane, then refresh it from the Mission branch through the auto-rebase (no sibling lane known)."""
    any_wp = "" if len(lane.wp_ids) == 1 else f" (any WP of the lane: {', '.join(lane.wp_ids)})"
    return (
        f"Then re-enter it with {_reentry_command(lane, mission_slug)}{any_wp}, which refreshes the lane through auto-rebase; "
        f"if the auto-rebase stops on a conflict, resolve it in the lane checkout the command names and commit there."
    )


def _incorporate_route(lane: ExecutionLane, handle: str, siblings: tuple[SiblingLane, ...]) -> str:
    """The re-review route when sibling lanes are known (WP07, ruling DM-01M88RZDBP57ZTYJHC5NP0ZH4R): one runnable command per line.

    Re-entering the first WP claims it again; ``--incorporate`` (WP08) merges each sibling lane at its
    newest approval stamp, never its live tip, so the reconciliation gate can trust the merge once a new
    independent approval reaches it. Every WP the reopen step sent back is re-entered and handed back.
    """
    wp_ids = lane.wp_ids or (WP_PLACEHOLDER,)
    first = wp_ids[0]
    agent = f"--agent {AGENT_PLACEHOLDER}"
    implement = f"spec-kitty agent action implement {first} --mission {handle}"
    lines = [f"{implement} {agent}"]
    for sibling in siblings:
        lines.append(f"{implement} --incorporate {sibling.lane_id} {agent}")
        lines.append("If it stops on a conflict, resolve it in the lane checkout that command names and commit the merge there.")
    lines.append(f"spec-kitty agent tasks move-task {first} --to for_review --mission {handle}")
    for wp_id in wp_ids[1:]:
        lines.append(f"spec-kitty agent action implement {wp_id} --mission {handle} {agent}")
        lines.append(f"spec-kitty agent tasks move-task {wp_id} --to for_review --mission {handle}")
    approves = "approves it again" if len(wp_ids) == 1 else "approves each of them again"
    lines.append(f"An independent reviewer reviews {' and '.join(wp_ids)} and {approves}; the new approval must reach the incorporation merge.")
    lines.append(f"spec-kitty consolidate --mission {handle}")
    lead = (
        f"Then run, in order, naming yourself as {AGENT_PLACEHOLDER} (the first command claims {first} again; "
        "each incorporation merges that sibling lane at its approval stamp, never its live tip):"
    )
    return lead + "".join(f"\n  {line}" for line in lines)


def _stale_remediation(
    lane: ExecutionLane,
    lane_branch: str,
    mission_branch: str,
    *,
    mission_slug: str | None = None,
    auto_rebase_halt: str | None = None,
    sibling_lanes: tuple[SiblingLane, ...] = (),
) -> str:
    """Build the operator-facing fix-it text for a stale lane.

    A code lane (FR-091, #7285) is refreshed through the CLI where one exists:
    re-entering the WP with ``spec-kitty agent action implement <WP> --mission <handle>``
    runs the lifecycle sync point, which auto-rebases the lane onto the Mission branch
    (A-10, ``tests/lanes/test_stale_remediation_cli_command.py``). The remedy names no
    ``.worktrees/`` path.

    The stale check runs at ``consolidate``, where every WP is approved and
    ``implement`` refuses an approved WP (#7754), so the remedy starts with the
    reopen step and says what it costs. When the overlap comes from a sibling lane
    consolidated earlier in the same run (#7755), the run's rollback restores the
    Mission branch without it, so refreshing from the Mission branch brings in
    nothing. The remedy then names the sibling lane (its branch is never moved by
    the rollback) and prints the re-review route one command per line: re-enter the
    WP, ``implement <WP> --incorporate <sibling lane>`` (which merges the sibling at
    its approval stamp, WP08), resolve and commit, ``move-task --to for_review``, an
    independent review, then ``consolidate`` (WP07). It never prints ``git merge``
    or a ``.worktrees/`` path (A-10). When the in-run auto-rebase stopped, its
    reason leads the text.

    The canonical planning lane (:func:`is_planning_lane`) never has a
    ``.worktrees/`` entry -- it resolves to the repository-root checkout on
    the mission's target branch. The lane sync point skips repository-root
    lanes, so no ``spec-kitty`` command refreshes it and its remedy keeps the
    manual steps. A raw ``git merge`` on the planning lane frequently conflicts
    on ``status.json``, a derived projection of ``status.events.jsonl``;
    ``spec-kitty agent status materialize`` rebuilds it from the event log
    (the cross-schema edge is tracked separately as #3531).

    A code lane's worktree may be absent (cleaned up, or never created on this
    clone); the re-entry command recreates it, so the remedy never names a
    worktree path glob that may match nothing (#7311).
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
    halt = f"The in-run auto-rebase of lane {lane.lane_id} onto {mission_branch} stopped: {auto_rebase_halt}. " if auto_rebase_halt else ""
    head = f"{halt}{_cause_sentence(lane, mission_branch, sibling_lanes)} {_reopen_step(lane, handle)} "
    if sibling_lanes:
        return head + _incorporate_route(lane, handle, sibling_lanes)
    return (
        f"{head}{_refresh_step(lane, mission_slug)} "
        f"Then hand the lane's work back for review; once it is approved again, re-run: spec-kitty consolidate --mission {handle}"
    )
