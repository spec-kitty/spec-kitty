"""The planning lane's Mission-branch authorship walk before a default Mission lands (#7860, FR-012).

Moved out of ``reconciliation_authorship`` (review 8: that module was at its 1,200-line limit);
no verdict changed apart from the rename and copy lineage below. ``reconciliation_authorship``
imports :func:`_planning_walk` and :func:`_scoped_final_walk` from here, and every planning name
(window, scope, ownership, window starts) is looked up in this one namespace, so a patch of one
reaches every read, ``planning_lane_scope``'s notes included.

Before a default Mission lands, its planning lane is walked on the Mission branch, fail closed, from
``lanes.json``'s planning pin to the coordination base (:func:`_lane_walk_range`). Each approved
work package is credited only inside its own window, from the commit that introduced its claim on
the Mission branch (``wp_evidence.planning_evidence_window``, the evidence axis' one decision) to
the commit that introduced its newest review approval, else its newest forced move into ``approved``
(:func:`_planning_window_ends`, ``wp_evidence.planning_approval_end``; review M1), counting only the commits that descend from that claim commit (``git rev-list
--ancestry-path``: a commit a merge brought in beside the claim never came after it), and only for
its own ``owned_files``, read as committed at the coordination base (:func:`_planning_ownership`, review M2;
``--resume`` already freezes that base), (:func:`_planning_scope`, operator ruling R2, 2026-11-27). No merge commit
is in any window, so no merge is credited by SHA, patch-id, blob or deletion: a merge that resolved
a conflict lists the resolved path, and its blob can carry a change made before the claim (review
6). The final-state walk (:func:`_scoped_final_walk`) reads the whole first-parent spine from the
recorded Mission base (:func:`_taint_spine`, :func:`_taint_base`,
``mission_base.resolve_mission_base``) to the coordination base, oldest first: the squash axis diffs
the landing from the target, so the planning pin and every commit made on the Mission branch before
it are in the landing too (review 9). Only a recorded base (``mission_base_sha``, written at create)
that is a commit on the target (an ancestor of the target's pre-run tip) starts it: a derived base
can sit above a commit made on the Mission branch before the scaffold (review 10), and so can a
hand-written one, which only the target check rejects (review 11). It attributes a path's final blob
or deletion only when every commit of that spine that changed the path is credited for it there:
that blob holds every earlier change to the file, so a path changed by a merge, by a commit before
the claim (one before the pin included), or by any other commit no window credits, is attributed to
nothing, never through a later credited commit (fail closed, review 7). Each commit is read with
rename and copy detection (``git diff -C`` against its first parent): a renamed or copied path also
carries every uncredited change its source had on the walk, so a file made before the claim and then
moved or copied by a credited commit is attributed to nothing under its new name either (review 8).
So an owned-path change made before the claim is never its work. A commit enters the claim by SHA
and patch-id only when every path it changes is credited there or is bookkeeping
(:func:`_scoped_commits`); a mixed commit, and every copy of it, stays un-attributable on the merge
/ rebase closed world while its credited blobs still count on the squash axis. The lane authors
nothing (:func:`_approved_planning_scope`) when any of its work packages is not approved (canceled,
in flight, or with no status row: the claim admits a commit by its paths, never by who made it,
operator ruling R1), when any ``owned_files`` cannot be read, when a pattern has fewer than two
literal leading path segments and names no top-level file (:func:`_is_whole_tree_pattern`,
``planning_lane_scope``), when every ``owned_files`` list is empty, when any approved work package's
window start or end (its approval commit) cannot be proven, or when the Mission records no Mission base (a derived one is not
trusted), its recorded base is not a commit on the target or not below the pin, or its spine cannot
be read. No attestation lifts this planning-lane credit rule. An un-attributable FAIL about the
lane's paths then names the lane, the reason, the work packages and the remedy
(``planning_lane_scope.planning_lane_notes``), with no change to the verdict.

Residuals of that window. Two shapes read as an added
file, credited as the commit's own work, whose whole content the review diff shows as added lines:
a copy whose source the same commit left unchanged (copy detection is git's default ``-C``, not
``--find-copies-harder``, whose cost grows with the tree: about 170 ms a commit on a 41,000-file
repository, against 3 ms), and a rename git scores below its similarity threshold,
which reads as a delete and an add. Last, a target change brought into the Mission branch (a
merge of the target, a rebase onto it or a cherry-pick of it, before ``finalize-tasks`` or a merge
after it) to a file a work package then edits makes that file un-attributable (fail closed: the change is on the taint
walk and no window credits it), although only the reviewed edit is missing from the target. The
FAIL prints no planning-lane note when the lane credits other work, and there is no verified
remedy; #7891 tracks naming the tainting commit in the FAIL.
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
    first_parent_commits_in_range,
    first_parent_lineage_changes,
    is_ancestor_strict,
    path_state_at,
)
from specify_cli.consolidation.mission_base import MissionBase, MissionBaseProvenance
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


def _planning_ownership(repo_root: Path, mission_slug: str, wp_ids: Sequence[str], ref: str) -> dict[str, tuple[str, ...]]:
    """*wp_ids*' authored ``owned_files`` globs as committed at *ref* (the Mission-branch tip judged); an unresolved id is absent.

    Read from the committed task files (``wp_evidence.read_wp_ownership_at_ref``), never the
    working tree, so an uncommitted widening cannot widen the credit (review M2). *ref* is the
    claim's coordination base, which ``--resume`` already freezes (``pre_mutation_coord_sha``).
    """
    from specify_cli.consolidation.wp_evidence import read_wp_ownership_at_ref

    resolved, _reasons = read_wp_ownership_at_ref(repo_root, mission_slug, tuple(wp_ids), ref)
    return dict(resolved)


def _approved_planning_scope(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    lane: ExecutionLane,
    work_packages: Mapping[str, Mapping[str, object]],
    coord_base_ref: str,
) -> dict[str, tuple[str, ...]]:
    """Each planning work package's ``owned_files`` committed at *coord_base_ref*, or ``{}`` when they cannot scope the window (fail closed).

    ``{}`` when any work package of the lane is not approved (:func:`_is_approved_wp`: canceled,
    in flight, or with no status row; operator ruling R1, 2026-11-27): the claim admits a commit by
    its paths, never by who made it, so a canceled or in-flight work package's commit into an
    approved path, whatever its own ``owned_files`` say, would otherwise read as approved work.
    ``{}`` as well when any ``owned_files`` cannot be read (no partial scope) or any pattern is too
    broad (:func:`_is_whole_tree_pattern`).
    """
    if not lane.wp_ids or not all(_is_approved_wp(wp, work_packages) for wp in lane.wp_ids):
        return {}
    owned = _planning_ownership(repo_root, lanes_manifest.mission_slug, lane.wp_ids, coord_base_ref)
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


def _planning_window_ends(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    wp_ids: Sequence[str],
    events: Callable[[], Sequence[Any] | None] | None,
) -> dict[str, str] | None:
    """Each work package's window end, the commit on the Mission branch that introduced its newest approval, or ``None``.

    The planning lane's approval bound (review M1, mirroring ``approved_bound`` on a code lane): a
    change to an owned path after the approval is not approved authorship, so it is
    un-attributable and the gate FAILs. ``None`` (the lane then authors nothing) when no event
    reader was given or any end cannot be proven.
    """
    from specify_cli.consolidation.wp_evidence import PlanningWindowUnresolved, planning_approval_end

    if events is None:
        return None
    ends: dict[str, str] = {}
    for wp_id in wp_ids:
        try:
            ends[wp_id] = planning_approval_end(repo_root, lanes_manifest, wp_id, events())
        except PlanningWindowUnresolved:
            return None
    return ends


@dataclass(frozen=True)
class _PlanningScope:
    """Per approved work package: its ``owned_files`` and its window's commits (ruling R2).

    The window holds the commits of ``<claim commit>..<approval commit>`` that descend from the claim
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
    start or end cannot be computed (:func:`_planning_window_starts`, :func:`_planning_window_ends`), or when a window's commits cannot be
    read. A scope whose every ``owned_files`` list is empty has no patterns and keeps today's range.
    """
    owned = _approved_planning_scope(repo_root, lanes_manifest, lane, work_packages, coord_base_ref)
    if not owned:
        return None
    starts = _planning_window_starts(repo_root, lanes_manifest, lane, tuple(owned), events)
    if starts is None or any(wp not in starts for wp in owned):
        return None
    ends = _planning_window_ends(repo_root, lanes_manifest, tuple(owned), events)
    if ends is None or any(wp not in ends for wp in owned):
        return None
    try:
        windows = tuple((owned[wp], frozenset(commits_on_ancestry_path(repo_root, starts[wp], ends[wp], no_merges=True))) for wp in owned)
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
    :func:`_is_bookkeeping`. A commit whose paths cannot be read raises :class:`GitProbeError` (the gate REFUSEs).
    """
    touching: list[str] = []
    whole: set[str] = set()
    for sha in shas:
        paths = changed_paths_of(repo_root, sha)
        credited = [scope.owns(sha, path) for path in paths]
        if not any(credited):
            continue
        touching.append(sha)
        if all(owned or _is_bookkeeping(path, mission_slug, None) for path, owned in zip(paths, credited, strict=True)):
            whole.add(sha)
    return _ScopedCommits(touching, frozenset(whole))


class _LaneAuthorshipWalk(NamedTuple):
    """A lane's authorship walk; ``whole`` and ``scope`` are ``None`` on an unscoped walk (every spine commit may enter by SHA).

    ``first_parent`` is the spine its final states are read from. On an unscoped walk it is the
    lane's whole first-parent spine. A scoped walk's ``spine`` holds only the commits it credits
    (``pin..coordination base``), and its ``first_parent`` is the taint spine, from the Mission
    base to the coordination base (:func:`_taint_spine`, review 9): a path any change of which it
    does not credit (a merge, review 6; a change before the claim, review 7; a change committed
    before the planning pin, review 9) is then attributed to nothing, never to an older commit
    (:func:`_scoped_final_walk`).
    """

    base: str
    branch: str
    spine: list[str]
    whole: frozenset[str] | None
    scope: _PlanningScope | None
    first_parent: list[str]


def _taint_base(repo_root: Path, mission_base: MissionBase | None, target_base: str | None) -> str | None:
    """Where the taint walk may start: a **recorded** Mission base that is a commit on the target (reviews 10 and 11).

    Mirrors ``reconciliation_closed_world._pre_mission_attribution``: a derived base is the first
    parent of the Mission's first scaffold commit, not the commit the branch was cut from, so a
    commit made on the Mission branch before the scaffold sits at or below it. That commit is in
    the landing (the squash axis diffs from the target's pre-run tip), is not exempt as pre-Mission
    history (only a recorded base exempts) and would not be on a taint walk from the derived base,
    so a credited edit of its file would land it unreviewed (fail-open).

    A recorded value is validated too (review 11): ``mission_base.resolve_mission_base`` checks it
    only against the Mission's origin (the scaffold commit's first parent), which a hand-written
    pre-scaffold commit passes. The commit a Mission branch was cut from was a tip of the target,
    so the base is used only when it is an ancestor of (or equal to) *target_base*, the target's
    pre-run tip (the claim's ``excluded_window_base``): then everything below it is on the target
    already. One ``git merge-base --is-ancestor`` probe. ``None`` (the planning lane then authors
    nothing) for a derived or unavailable base, or none, for no *target_base*, for a base that is
    not on the target (a hand-written Mission-branch commit, a rewritten target or a retargeted
    Mission) and when the probe cannot run.
    """
    if mission_base is None or mission_base.provenance is not MissionBaseProvenance.RECORDED:
        return None
    sha = mission_base.sha
    if sha is None or target_base is None:
        return None
    try:
        on_target = is_ancestor_strict(repo_root, sha, target_base)
    except GitProbeError:
        return None
    return sha if on_target else None


def _taint_spine(repo_root: Path, mission_base: str | None, pin: str, coord_base_ref: str) -> list[str] | None:
    """The first-parent spine ``<Mission base>..<coordination base>`` the taint walk reads, or ``None`` (fail closed).

    *mission_base* is the **recorded** Mission base only, and only when it is a commit on the
    target (:func:`_taint_base`, reviews 10 and 11): the commit the Mission branch was cut from,
    written to meta.json at create (#7560). The squash axis diffs the landing from the target's
    pre-run tip, so every Mission-branch commit above it is in the landing: the commits between it
    and the planning pin and the pin commit itself included. Because :func:`_taint_base` checked
    that the base is an ancestor of (or equal to) the target's pre-run tip, everything below it is
    on the target already. A derived base, or a recorded one that is not on the target, gives no
    such guarantee (a commit made on the Mission branch before the scaffold can sit below it), so it
    never reaches here.
    No window credits a commit before a claim (operator ruling R2), so each commit of the spine
    taints the paths it changed. ``None`` (the lane then authors nothing) when there is no recorded
    base, when it is not an ancestor of the pin, or when git cannot read either.
    """
    if mission_base is None:
        return None
    try:
        if not is_ancestor_strict(repo_root, mission_base, pin):
            return None
        spine: list[str] = first_parent_commits_in_range(repo_root, mission_base, coord_base_ref)
    except GitProbeError:
        return None
    return spine


def _planning_walk(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    lane: ExecutionLane,
    work_packages: Mapping[str, Mapping[str, object]],
    coord_base_ref: str,
    sb_window: tuple[str, str] | None,
    events: Callable[[], Sequence[Any] | None] | None = None,
    mission_base: str | None = None,
) -> _LaneAuthorshipWalk:
    """*lane*'s walk; the planning scope (:func:`_planning_scope`) is read only for a planning lane with no ``single_branch`` window.

    A scoped walk needs its taint spine from *mission_base* (:func:`_taint_spine`); without one
    the lane keeps today's range and authors nothing (fail closed).
    """
    scope = _planning_scope(repo_root, lanes_manifest, lane, work_packages, coord_base_ref, events) if is_planning_lane(lane) and not sb_window else None
    base, branch, patterns = _lane_walk_range(repo_root, lanes_manifest, lane, coord_base_ref, sb_window, scope.patterns if scope else ())
    taint = _taint_spine(repo_root, mission_base, base, branch) if patterns and scope is not None else None
    if scope is None or taint is None:
        if patterns:
            base, branch, patterns = _lane_walk_range(repo_root, lanes_manifest, lane, coord_base_ref, sb_window, ())
        first_parent = _lane_first_parent_spine(repo_root, base, branch)
        return _LaneAuthorshipWalk(base, branch, first_parent, None, None, first_parent)
    scoped = _scoped_commits(repo_root, _lane_first_parent_spine(repo_root, base, branch), scope, lanes_manifest.mission_slug)
    return _LaneAuthorshipWalk(base, branch, scoped.touching, scoped.whole, scope, taint)


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

    *first_parent* is the taint spine (``<Mission base>..<coordination base>``, :func:`_taint_spine`), newest first, as
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
    "_planning_lane_mission_branch_window",
    "_planning_ownership",
    "_planning_scope",
    "_planning_walk",
    "_planning_window_ends",
    "_planning_window_starts",
    "_scoped_final_walk",
    "_taint_base",
    "_taint_spine",
]
