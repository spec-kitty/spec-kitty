"""The planning lane's Mission-branch authorship walk before a default Mission lands (#7860, FR-012).

Moved out of ``reconciliation_authorship`` (review 8: that module was at its 1,200-line limit);
no verdict changed apart from the rename and copy lineage below. ``reconciliation_authorship``
imports :func:`_planning_walk` and :func:`_scoped_final_walk` from here, and every planning name
(window, scope, ownership, window starts) is looked up in this one namespace, so a patch of one
reaches every read, ``planning_lane_scope``'s notes included.

Before a default Mission lands, its planning lane is walked on the Mission branch, fail closed,
from ``lanes.json``'s planning pin to the coordination base (:func:`_lane_walk_range`). Each
approved work package is credited only inside its own window, from the commit that introduced its
claim on the Mission branch (``wp_evidence.planning_evidence_window``, the evidence axis' one
decision) to the coordination base, counting only the commits that descend from that claim commit
(``git rev-list --ancestry-path``: a commit a merge brought in beside the claim never came after
it), and only for its own ``owned_files`` (:func:`_planning_scope`, operator ruling R2,
2026-11-27). No merge commit is in any window, so no merge is credited by SHA, patch-id, blob or
deletion: a merge that resolved a conflict lists the resolved path, and its blob can carry a change
made before the claim (review 6). The final-state walk (:func:`_scoped_final_walk`) reads the whole
first-parent spine, oldest first, and attributes a path's final blob or deletion only when every
commit of that spine that changed the path is credited for it there: that blob holds every earlier
change to the file, so a path changed by a merge, by a commit before the claim, or by any other
commit no window credits, is attributed to nothing, never through a later credited commit (fail
closed, review 7). Each commit is read with rename and copy detection (``git diff -C`` against its
first parent): a renamed or copied path also carries every uncredited change its source had on the
walk, so a file made before the claim and then moved or copied by a credited commit is attributed to
nothing under its new name either (review 8). So an owned-path change made before the claim is never
its work. A commit enters the claim by SHA and patch-id only when every path it changes is credited
there or is bookkeeping (:func:`_scoped_commits`); a mixed commit, and every copy of it, stays
un-attributable on the merge / rebase closed world while its credited blobs still count on the
squash axis. The lane authors nothing (:func:`_approved_planning_scope`) when any of its work
packages is not approved (canceled, in flight, or with no status row: the claim admits a commit by
its paths, never by who made it, operator ruling R1), when any ``owned_files`` cannot be read, when
a pattern has fewer than two literal leading path segments and names no top-level file
(:func:`_is_whole_tree_pattern`, ``planning_lane_scope``), when every ``owned_files`` list is empty,
or when any approved work package's window start cannot be proven. No attestation lifts this
planning-lane credit rule. An un-attributable FAIL about the lane's paths then names the lane, the
reason, the work packages and the remedy (``planning_lane_scope.planning_lane_notes``), with no
change to the verdict.

Residuals of that window. The planning lane has no approval-stamp bound: a change to an approved
work package's owned path made after its approval, by any commit on the Mission branch, still
counts as approved authorship. ``owned_files`` is read from the working tree's task files (the
placement seam's ``tasks/`` directory), not at ``coord_base_ref``, and ``--resume`` does not freeze
it, so an ``owned_files`` edit between runs changes the scope. And copy detection is git's default:
a copy whose source the same commit left unchanged reads as an added file, whose whole content the
review diff shows.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NamedTuple

from specify_cli.consolidation.git_probes import (
    GitProbeError,
    LineageChange,
    changed_paths_of,
    commits_on_ancestry_path,
    first_parent_lineage_changes,
    path_state_at,
)
from specify_cli.consolidation.planning_lane_scope import is_whole_tree_pattern as _is_whole_tree_pattern
from specify_cli.consolidation.reconciliation_kernel import (
    _is_approved_wp,
    _is_bookkeeping,
    _lane_branch_for,
    _lane_first_parent_spine,
)
from specify_cli.lanes.compute import is_planning_lane
from specify_cli.lanes.models import ExecutionLane, LanesManifest


def _planning_lane_mission_branch_window(repo_root: Path, lanes_manifest: LanesManifest, coord_base_ref: str) -> tuple[str, str] | None:
    """``(planning pin, frozen Mission-branch tip)`` when the planning lane writes to the Mission branch (#7860, FR-012), else ``None``.

    Before a default Mission lands, its planning lane writes to its Mission branch
    (:func:`mission_runtime.planning_write_ref`, looked up at call time), which *coord_base_ref*
    (the coordination base, the Mission branch's pre-mutation tip) already carries; measured
    ``coord_base_ref..<target>`` the planning lane authors nothing, so its owned content outside
    the bookkeeping paths reads as un-attributable at the gate. The planning work is instead read
    from ``lanes.json``'s planning pin to that frozen tip. ``None`` (every other shape, no pin, or
    a write branch that cannot be decided) keeps today's range: a planning lane that authors
    nothing, so the gate still refuses content it cannot attribute (fail closed). The evidence
    axis, which runs before the collectors, already refused an undecidable write branch.
    """
    import mission_runtime

    pin = lanes_manifest.planning_commit_sha
    if not pin:
        return None
    try:
        ref = mission_runtime.planning_write_ref(repo_root, lanes_manifest.mission_slug, lanes_manifest.target_branch)
    except (mission_runtime.PlanningWriteRefUnavailable, mission_runtime.PlanningCheckoutMissing):
        return None
    return (pin, coord_base_ref) if ref.on_mission_branch else None


def _lane_walk_range(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    lane: ExecutionLane,
    coord_base_ref: str,
    sb_window: tuple[str, str] | None,
    planning_scope: Sequence[str] = (),
) -> tuple[str, str, tuple[str, ...]]:
    """``(base, tip, scope)`` of a lane's authorship walk; a non-empty *scope* scopes the walk (:func:`_collect_authored`).

    A code lane walks ``coord_base_ref..<lane branch>`` and a ``single_branch`` planning lane its
    *sb_window*, as before. The planning lane of a default Mission that has not landed walks its
    Mission-branch window (:func:`_planning_lane_mission_branch_window`), scoped to
    *planning_scope*: the owned paths of its approved work packages (:func:`_planning_scope`,
    which also says when there is none), never the lane's ``write_scope``. The Mission branch also
    carries status, canceled and other Mission work, which must never read as approved planning
    authorship. An empty *planning_scope* keeps today's range and authors nothing: it never turns
    the Mission-branch window into an unscoped walk (the empty tuple means "unscoped" for every other range).
    """
    if is_planning_lane(lane):
        if sb_window:
            return sb_window[0], sb_window[1], ()
        window = _planning_lane_mission_branch_window(repo_root, lanes_manifest, coord_base_ref) if planning_scope else None
        if window is not None:
            return window[0], window[1], tuple(planning_scope)
    return coord_base_ref, _lane_branch_for(lanes_manifest, lane.lane_id), ()


def _planning_ownership(repo_root: Path, mission_slug: str, wp_ids: Sequence[str]) -> dict[str, tuple[str, ...]]:
    """*wp_ids*' authored ``owned_files`` globs, read through the evidence axis' one reader; an unresolved id is absent."""
    from specify_cli.consolidation.wp_evidence import read_wp_ownership

    # ``feature_dir`` is unused by the reader (it reads the placement seam's tasks dir, never a fallback).
    resolved, _reasons, _tasks_dir = read_wp_ownership(repo_root, mission_slug, repo_root, tuple(wp_ids))
    return dict(resolved)


def _approved_planning_scope(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    lane: ExecutionLane,
    work_packages: Mapping[str, Mapping[str, object]],
) -> dict[str, tuple[str, ...]]:
    """Each planning work package's ``owned_files``, or ``{}`` when they cannot scope the window (fail closed).

    ``{}`` when any work package of the lane is not approved (:func:`_is_approved_wp`: canceled,
    in flight, or with no status row; operator ruling R1, 2026-11-27): the claim admits a commit by
    its paths, never by who made it, so a canceled or in-flight work package's commit into an
    approved path, whatever its own ``owned_files`` say, would otherwise read as approved work.
    ``{}`` as well when any ``owned_files`` cannot be read (no partial scope) or any pattern is too
    broad (:func:`_is_whole_tree_pattern`).
    """
    if not lane.wp_ids or not all(_is_approved_wp(wp, work_packages) for wp in lane.wp_ids):
        return {}
    owned = _planning_ownership(repo_root, lanes_manifest.mission_slug, lane.wp_ids)
    if any(wp not in owned for wp in lane.wp_ids):
        return {}
    if any(_is_whole_tree_pattern(pattern) for patterns in owned.values() for pattern in patterns):
        return {}
    return {wp: tuple(owned[wp]) for wp in lane.wp_ids}


def _planning_window_starts(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    lane: ExecutionLane,
    wp_ids: Sequence[str],
    events: Callable[[], Sequence[Any] | None] | None,
) -> dict[str, str] | None:
    """Each work package's window start, the commit that introduced its claim on the Mission branch, or ``None``.

    Read through the evidence axis' one decision (:func:`~specify_cli.consolidation.wp_evidence.planning_evidence_window`,
    operator ruling R2, 2026-11-27). ``None`` (the lane then authors nothing) when no event reader
    was given, when any start cannot be proven, or when the shape is not the Mission-branch window.
    """
    from specify_cli.consolidation.wp_evidence import PlanningWindowUnresolved, planning_evidence_window

    if events is None:
        return None
    starts: dict[str, str] = {}
    for wp_id in wp_ids:
        try:
            window = planning_evidence_window(repo_root, lanes_manifest, lane, wp_id, events)
        except PlanningWindowUnresolved:
            return None
        if window is None:
            return None
        starts[wp_id] = window[0]
    return starts


@dataclass(frozen=True)
class _PlanningScope:
    """Per approved work package: its ``owned_files`` and its window's commits (ruling R2).

    The window holds the commits of ``<claim commit>..<coordination base>`` that descend from the claim
    commit, less every merge commit (review 6): a merge that resolved a conflict lists the resolved path
    and its blob can carry a change made before the claim, so no merge is ever credited.
    """

    windows: tuple[tuple[tuple[str, ...], frozenset[str]], ...]

    @property
    def patterns(self) -> tuple[str, ...]:
        """Every owned pattern of the lane, whatever the window."""
        return tuple(sorted({pattern for owned, _commits in self.windows for pattern in owned}))

    def at(self, sha: str) -> tuple[str, ...]:
        """The owned patterns of the work packages whose window holds *sha*."""
        return tuple(pattern for owned, commits in self.windows if sha in commits for pattern in owned)

    def owns(self, sha: str, path: str) -> bool:
        """True when *path* lies in the ``owned_files`` of a work package whose window holds *sha*."""
        from specify_cli.ownership.matching import matches_owned

        patterns = self.at(sha)
        return bool(patterns) and matches_owned(path, patterns)


def _planning_scope(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    lane: ExecutionLane,
    work_packages: Mapping[str, Mapping[str, object]],
    coord_base_ref: str,
    events: Callable[[], Sequence[Any] | None] | None,
) -> _PlanningScope | None:
    """The :class:`_PlanningScope` of a planning lane, or ``None`` when the lane authors nothing (fail closed).

    ``None`` when :func:`_approved_planning_scope` gives nothing, when any work package's window
    start cannot be computed (:func:`_planning_window_starts`), or when a window's commits cannot be
    read. A scope whose every ``owned_files`` list is empty has no patterns and keeps today's range.
    """
    owned = _approved_planning_scope(repo_root, lanes_manifest, lane, work_packages)
    if not owned:
        return None
    starts = _planning_window_starts(repo_root, lanes_manifest, lane, tuple(owned), events)
    if starts is None or any(wp not in starts for wp in owned):
        return None
    try:
        windows = tuple((owned[wp], frozenset(commits_on_ancestry_path(repo_root, starts[wp], coord_base_ref, no_merges=True))) for wp in owned)
    except GitProbeError:
        return None
    return _PlanningScope(windows)


class _ScopedCommits(NamedTuple):
    """A scoped walk's commits: those touching the scope (order kept) and those changing nothing outside it."""

    touching: list[str]
    whole: frozenset[str]


def _scoped_commits(repo_root: Path, shas: Sequence[str], scope: _PlanningScope, mission_slug: str) -> _ScopedCommits:
    """The commits of *shas* that change a path *scope* credits there, and those whose every path it credits or is bookkeeping.

    A path is credited at a commit only when it lies in the ``owned_files`` of an approved work
    package whose own window holds that commit (:meth:`_PlanningScope.owns`). Only a ``whole``
    commit may enter the claim by SHA and patch-id: a mixed commit (a credited path plus any other)
    would otherwise attribute its other change, and every cherry-picked copy of it, on the merge /
    rebase closed world. Its credited blobs are still attributed. Bookkeeping is the gate's own
    :func:`_is_bookkeeping`. An unreadable commit is dropped (fail closed).
    """
    touching: list[str] = []
    whole: set[str] = set()
    for sha in shas:
        try:
            paths = changed_paths_of(repo_root, sha)
        except GitProbeError:
            continue
        credited = [scope.owns(sha, path) for path in paths]
        if not any(credited):
            continue
        touching.append(sha)
        if all(owned or _is_bookkeeping(path, mission_slug, None) for path, owned in zip(paths, credited, strict=True)):
            whole.add(sha)
    return _ScopedCommits(touching, frozenset(whole))


class _LaneAuthorshipWalk(NamedTuple):
    """A lane's authorship walk; ``whole`` and ``scope`` are ``None`` on an unscoped walk (every spine commit may enter by SHA).

    ``first_parent`` is the lane's whole first-parent spine. A scoped walk's ``spine`` holds only the
    commits it credits, so its final-state walk reads ``first_parent`` instead: a path any change of
    which it does not credit (a merge, review 6; a change before the claim, review 7) is then
    attributed to nothing, never to an older commit (:func:`_scoped_final_walk`).
    """

    base: str
    branch: str
    spine: list[str]
    whole: frozenset[str] | None
    scope: _PlanningScope | None
    first_parent: list[str]


def _planning_walk(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    lane: ExecutionLane,
    work_packages: Mapping[str, Mapping[str, object]],
    coord_base_ref: str,
    sb_window: tuple[str, str] | None,
    events: Callable[[], Sequence[Any] | None] | None = None,
) -> _LaneAuthorshipWalk:
    """*lane*'s walk; the planning scope (:func:`_planning_scope`) is read only for a planning lane with no ``single_branch`` window."""
    scope = _planning_scope(repo_root, lanes_manifest, lane, work_packages, coord_base_ref, events) if is_planning_lane(lane) and not sb_window else None
    base, branch, patterns = _lane_walk_range(repo_root, lanes_manifest, lane, coord_base_ref, sb_window, scope.patterns if scope else ())
    first_parent = _lane_first_parent_spine(repo_root, base, branch)
    if not patterns or scope is None:
        return _LaneAuthorshipWalk(base, branch, first_parent, None, None, first_parent)
    scoped = _scoped_commits(repo_root, first_parent, scope, lanes_manifest.mission_slug)
    return _LaneAuthorshipWalk(base, branch, scoped.touching, scoped.whole, scope, first_parent)


def _touched_paths(change: LineageChange) -> tuple[str, ...]:
    """The paths *change* changed: its own path, plus the source a rename removed."""
    if change.renamed and change.source is not None:
        return (change.path, change.source)
    return (change.path,)


def _walk_commit(repo_root: Path, sha: str, scope: _PlanningScope, dropped: frozenset[str], newest: dict[str, str], tainted: set[str]) -> None:
    """Record *sha*'s changes on the oldest-first walk: each path's newest commit, and the paths it taints.

    A path is tainted when *sha* changed it without being credited for it there (or *sha* is
    *dropped*), or when *sha* renamed or copied it from a source an earlier change already
    tainted (the content moves with its history, review 8).
    """
    changes = first_parent_lineage_changes(repo_root, sha)
    inherited = {change.path for change in changes if change.source is not None and change.source in tainted}
    for change in changes:
        for path in _touched_paths(change):
            newest[path] = sha
            if sha in dropped or not scope.owns(sha, path):
                tainted.add(path)
    tainted |= inherited


def _scoped_final_walk(repo_root: Path, first_parent: Sequence[str], scope: _PlanningScope, dropped: frozenset[str]) -> tuple[set[tuple[str, str]], set[str]]:
    """The final ``(path, blob)``s and deleted paths a planning scope credits on *first_parent* (#7860, reviews 7 and 8).

    *first_parent* is the first-parent spine (``pin..coordination base``), newest first, as
    :func:`_lane_first_parent_spine` gives it; it is walked oldest first. A path's final state is
    attributed only when EVERY commit of that spine that changed it is credited for it at that
    commit (:meth:`_PlanningScope.owns`), and, when a commit renamed or copied it, its source was
    attributable too. A path's final blob holds every earlier change to the file, so one uncredited
    change (made before the claim, outside every window, by a merge, by another work package, or
    by a *dropped* commit), to the path or to a path it was moved or copied from, leaves the path
    attributed to nothing, fail closed. Each commit is read through its first-parent diff with
    rename and copy detection (:func:`first_parent_lineage_changes`), so a clean merge's
    brought-in paths count as its changes. A git error propagates, re-raised with the path named
    when a state cannot be read, like ``reconciliation_authorship._final_authored_walk``.
    """
    newest: dict[str, str] = {}
    tainted: set[str] = set()
    for sha in reversed(first_parent):
        _walk_commit(repo_root, sha, scope, dropped, newest, tainted)
    blobs: set[tuple[str, str]] = set()
    deletions: set[str] = set()
    for path, sha in newest.items():
        if path in tainted:
            continue
        try:
            state = path_state_at(repo_root, sha, path)
        except GitProbeError as exc:
            raise GitProbeError(f"reading {path} at {sha[:10]} on the planning walk failed: {exc}") from exc
        if state is None:
            deletions.add(path)
        else:
            blobs.add((path, state))
    return blobs, deletions


__all__ = [
    "_LaneAuthorshipWalk",
    "_PlanningScope",
    "_ScopedCommits",
    "_approved_planning_scope",
    "_lane_walk_range",
    "_planning_lane_mission_branch_window",
    "_planning_ownership",
    "_planning_scope",
    "_planning_walk",
    "_planning_window_starts",
    "_scoped_commits",
    "_scoped_final_walk",
]
