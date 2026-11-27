"""The authored-content walk and the approved-content presence check of the reconciliation gate.

Mission consolidation-window-provenance-01M6Y84D, WP15 (C-007). ONE slice, ONE first-parent history walk:
:func:`_final_authored_walk` is looked up by the blob and deletion readers, by the presence lane content
and three times by :func:`_collect_authored` (the full walk, the reviewed-merges walk and the own-base-bounded
walk), so a patch of that one name must reach every lookup through a single module namespace. Splitting the
authorship walk from the presence check would let a second walk appear unnoticed.

It holds the authored-blob and authored-deletion readers (#5013, #5022), the per-lane contribution record,
the presence scope and the lane content measured from each lane's own base (#5788, #5968), the presence
verdict :func:`unmet_approved_content` (#5571) and the dependency-merge attribution of a lane's reviewed
merges (#7307). Moved verbatim out of ``reconciliation.py``; no verdict changed. That module re-exports
every name, so no caller changes (C-005).

Before a default Mission lands, its planning lane is walked on the Mission branch (#7860, FR-012,
:func:`_lane_walk_range`), fail closed, from ``lanes.json``'s planning pin to the coordination base.
Each approved work package is credited only inside its own window, from the commit that introduced
its claim on the Mission branch (``wp_evidence.planning_evidence_window``, the evidence axis' one
decision) to the coordination base, counting only the commits that descend from that claim commit
(``git rev-list --ancestry-path``: a commit a merge brought in beside the claim never came after
it), and only for its own ``owned_files`` (:func:`_planning_scope`, operator ruling R2,
2026-11-27). No merge commit is in any window, so no merge is credited by SHA, patch-id, blob or
deletion: a merge that resolved a conflict lists the resolved path, and its blob can carry a change
made before the claim (review 6). The final-state walk reads the whole first-parent spine, so a path
whose newest change is such a merge is attributed to nothing, never to an older credited commit
(fail closed). A commit enters the claim by SHA and patch-id only when every path
it changes is credited there or is bookkeeping (:func:`_scoped_commits`); a mixed commit, and every
copy of it, stays un-attributable on the merge / rebase closed world while its credited blobs still
count on the squash axis. The lane authors nothing (:func:`_approved_planning_scope`) when any of its
work packages is not approved (canceled, in flight, or with no status row: the claim admits a commit
by its paths, never by who made it, operator ruling R1), when any ``owned_files`` cannot be read,
when a pattern has fewer than two literal leading path segments and names no top-level file
(:func:`_is_whole_tree_pattern`, ``planning_lane_scope``), when every ``owned_files`` list is empty,
or when any approved work package's window start cannot be proven. No attestation lifts this
planning-lane credit rule. An un-attributable FAIL about the lane's paths then names the lane, the
reason, the work packages and the remedy (``planning_lane_scope.planning_lane_notes``), with no
change to the verdict.

Two residuals of that window. The planning lane has no approval-stamp bound: a change to an
approved work package's owned path made after its approval, by any commit on the Mission branch,
still counts as approved authorship. And ``owned_files`` is read from the working tree's task
files (the placement seam's ``tasks/`` directory), not at ``coord_base_ref``, and ``--resume``
does not freeze it, so an ``owned_files`` edit between runs changes the scope.
"""

from __future__ import annotations

import functools
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NamedTuple

from specify_cli.consolidation.approved_bound import approval_presync_stamp, approval_stamp
from specify_cli.consolidation.git_probes import (
    GitProbeError,
    changed_paths_of,
    commit_parents,
    commits_in_range,
    commits_on_ancestry_path,
    first_parent_changed_paths,
    is_merge_commit,
    patch_id_of,
    path_state_at,
    sha_reachable_from,
)
from specify_cli.consolidation.planning_lane_scope import is_whole_tree_pattern as _is_whole_tree_pattern
from specify_cli.consolidation.reconciliation_canceled import _fully_canceled_lane_commits
from specify_cli.consolidation.reconciliation_claim_types import (
    _GAP_ABSENT,
    _GAP_UNCHANGED,
    ApprovedLaneContent,
    LaneContribution,
    MissingApprovedContent,
    PresenceGap,
)
from specify_cli.consolidation.reconciliation_kernel import (
    _dependency_lane_ids,
    _is_approved_wp,
    _is_bookkeeping,
    _lane_branch_for,
    _lane_first_parent_spine,
    _lane_is_approved,
    _LaneWalk,
)
from specify_cli.consolidation.wp_attribution import first_governed_open_stamp, lane_dependency_merges, lane_own_commits
from specify_cli.lanes.compute import is_planning_lane
from specify_cli.lanes.models import ExecutionLane, LanesManifest


def _unsuperseded_holders(holders: Sequence[ApprovedLaneContent]) -> list[ApprovedLaneContent]:
    """The holders of a path no OTHER holder built atop (a dependent lane supersedes its dependency)."""
    return [holder for holder in holders if not any(holder.lane_id in other.ancestors for other in holders if other is not holder)]


def _presence_gap(states: set[str | None], target: str | None, started_from: Callable[[], set[str | None]]) -> PresenceGap | None:
    """``"absent"`` / ``"unchanged"`` when the *target* state is none of *states*, else ``None``.

    A target holding another, third content is NOT a gap here: that is a merge
    resolution or a later legitimate edit, which the blob-attribution and
    closed-world axes already judge. What this axis adds is the case they cannot
    see because the content is simply not there: the path is absent although
    every unsuperseded lane ends with it present, or the target still holds a
    state the lane started from (the approved change, or deletion, never landed).
    *started_from* is read only when it can decide.
    """
    if target in states:
        return None
    if target is None:
        return _GAP_ABSENT
    return _GAP_UNCHANGED if target in started_from() else None


def _started_from(path: str, holders: Sequence[ApprovedLaneContent], base: Callable[[], str | None], state_at: StateAt | None) -> set[str | None]:
    """The states *holders* started *path* from: the pre-consolidation state, and what each dependency held when it was built on.

    A dependent lane starts from its dependency's tip, so a target that landed
    the dependency's change but not the lane's own still holds what the lane
    started from, not the pre-consolidation state.
    """
    started = {base()}
    if state_at is not None:
        started.update(state_at(fork, path) for holder in holders for fork in holder.dependency_forks.values())
    return started


StateAt = Callable[[str, str], str | None]


def _owns_change(holder: ApprovedLaneContent, path: str, holders: Sequence[ApprovedLaneContent], state_at: StateAt | None) -> bool:
    """False when *holder* only carries what a dependency lane held when *holder* was built on it.

    A dependent lane's first-parent spine includes the dependency lane's commits
    (the allocator fast-forwards them in), so its final state for a path it never
    touched is the dependency's state at that moment. Such a lane neither
    supersedes the dependency (which may have moved on since, e.g. reverted the
    path) nor is the author to name. Unknown (no probe, or no recorded fork)
    counts as its own change, the stricter reading.
    """
    if state_at is None:
        return True
    carried = holder.final_state[path]
    forks = (holder.dependency_forks.get(other.lane_id) for other in holders if other is not holder)
    return not any(fork is not None and state_at(fork, path) == carried for fork in forks)


def _dropped_own_change(holder: ApprovedLaneContent, path: str, base: str | None, state_at: StateAt | None) -> bool:
    """True when *holder*'s final state for *path* is a net change only a LOSS explains on the target.

    Three facts, all read at the lane's own base (``fork_point``), never against
    the target alone:

    * the target still holds *path* as the lane found it (*base* equals the state
      at the fork point). A target that edited, deleted or renamed the path itself
      since the lane was cut produces a merge resolution, not a dropped change;
    * the lane's final state differs from the state at its fork point. A lane that
      left the path as it found it (changed and reverted, by itself or through the
      lanes it was built on) has nothing to land;
    * the lane tip really holds that final state. When a merge on the lane's own
      spine took another version, the lane does not end on what its commits say.

    A content without ``tip`` / ``fork_point`` (hand-built) is read as cut from the
    pre-consolidation target: only the net-change fact applies, against *base*.
    """
    final: str | None = holder.final_state[path]
    if state_at is None or holder.tip is None or holder.fork_point is None:
        return final != base
    found_at_fork = state_at(holder.fork_point, path)
    return found_at_fork == base and final != found_at_fork and state_at(holder.tip, path) == final


def _missing_entries(path: str, holders: Sequence[ApprovedLaneContent], unmet: set[str | None], found: PresenceGap) -> list[MissingApprovedContent]:
    """One :class:`MissingApprovedContent` per unmet state, naming every holder that ended on it."""
    entries: list[MissingApprovedContent] = []
    for state in sorted(unmet, key=lambda value: (value is not None, value or "")):
        owners = [holder for holder in holders if holder.final_state[path] == state]
        wp_ids = tuple(dict.fromkeys(wp for owner in owners for wp in owner.wp_ids))
        entries.append(MissingApprovedContent(wp_ids=wp_ids, lane_ids=tuple(owner.lane_id for owner in owners), path=path, expected=state, found=found))
    return entries


def _path_gap(
    path: str,
    holders: Sequence[ApprovedLaneContent],
    target: str | None,
    base_state: Callable[[], str | None],
    state_at: StateAt | None,
) -> list[MissingApprovedContent]:
    """The unmet approved states of ONE path (the body of :func:`unmet_approved_content`).

    The common case costs nothing beyond the target read: the target holds a
    state an unsuperseded holder ended on. Only a candidate gap pays for the
    lane-base reads that decide whether it is a dropped change.
    """
    unsuperseded = _unsuperseded_holders(holders)
    if (
        _presence_gap({holder.final_state[path] for holder in unsuperseded}, target, functools.partial(_started_from, path, unsuperseded, base_state, state_at))
        is None
    ):
        return []
    authors = [holder for holder in holders if _owns_change(holder, path, holders, state_at)]
    live = _unsuperseded_holders(authors)
    found = _presence_gap({holder.final_state[path] for holder in live}, target, functools.partial(_started_from, path, live, base_state, state_at))
    if found is None:
        return []
    base = base_state()
    unmet = {holder.final_state[path] for holder in live if _dropped_own_change(holder, path, base, state_at)}
    return _missing_entries(path, authors, unmet, found)


def unmet_approved_content(
    contents: Sequence[ApprovedLaneContent],
    *,
    target_state: Callable[[str], str | None],
    base_state: Callable[[str], str | None],
    skip: Callable[[str], bool] | None = None,
    state_at: StateAt | None = None,
) -> list[MissingApprovedContent]:
    """Pure presence verdict (#5571): approved lane content the target does not hold.

    Per path, the lanes holding a final state for it are reduced to those no other
    holder was built atop (a dependent lane supersedes the lanes it depends on: it
    deleted, renamed away or reverted the path). Those unsuperseded states are the
    only ones the target must hold. Lanes that are not in *contents* -- canceled or
    unapproved -- never supersede anything, because the claim builder only records
    approved lanes. Independent lanes that ended on different states for one path
    are a merge-resolution case: the target must hold one of them, or something
    else entirely, but not nothing. *skip* names the paths judged elsewhere
    (bookkeeping, canceled WP content).

    A gap is reported only for a lane's OWN NET change on a path the target left
    alone since the lane was cut (:func:`_owns_change`, :func:`_dropped_own_change`),
    judged against the lane's own base through *state_at* ``(ref, path)``. Comparing
    a lane's final state with the target alone would read every path the lanes left
    net unchanged, and every path the target moved meanwhile, as approved work
    dropped. Without *state_at* each lane is taken as cut from the pre-consolidation
    target (*base_state*).
    """
    holders_by_path: dict[str, list[ApprovedLaneContent]] = {}
    for content in contents:
        for path in content.final_state:
            holders_by_path.setdefault(path, []).append(content)
    missing: list[MissingApprovedContent] = []
    for path in sorted(holders_by_path):
        if skip is not None and skip(path):
            continue
        base = functools.cache(functools.partial(base_state, path))
        missing.extend(_path_gap(path, holders_by_path[path], target_state(path), base, state_at))
    return missing


def _order_lane_content(contents: list[ApprovedLaneContent]) -> tuple[ApprovedLaneContent, ...]:
    """Dependency order: every lane after the lanes it depends on, ties by lane id (deterministic)."""
    remaining = {content.lane_id: content for content in contents}
    ordered: list[ApprovedLaneContent] = []
    while remaining:
        ready = sorted(lane_id for lane_id, content in remaining.items() if not (content.ancestors & remaining.keys()))
        if not ready:  # a dependency cycle is invalid input elsewhere; stay deterministic rather than loop
            ready = sorted(remaining)
        for lane_id in ready:
            ordered.append(remaining.pop(lane_id))
    return tuple(ordered)


def _dependency_forks(repo_root: Path, lanes_manifest: LanesManifest, branch: str, spine: Sequence[str], ancestors: Iterable[str]) -> dict[str, str]:
    """Dependency lane id -> the commit of that lane *branch* was built on (newest spine commit the dependency also holds).

    One range read per dependency lane, no path read. A dependency whose branch
    cannot be read, or none of whose commits sit on the spine (it came in through
    a true merge commit), records nothing: the lane's held paths then count as its
    own, the stricter reading.
    """
    forks: dict[str, str] = {}
    for dependency in ancestors:
        try:
            ahead = frozenset(commits_in_range(repo_root, _lane_branch_for(lanes_manifest, dependency), branch))
        except GitProbeError:
            continue
        fork = next((sha for sha in spine if sha not in ahead), None)
        if fork is not None:
            forks[dependency] = fork
    return forks


def _lane_content(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    lane: ExecutionLane,
    work_packages: Mapping[str, Mapping[str, object]],
    spine: Sequence[str],
    lane_blobs: set[tuple[str, str]],
    lane_deletions: set[str],
) -> ApprovedLaneContent:
    """An approved lane's final path state, from the SAME walk that produced ``authored_blobs`` (#5571).

    *spine* is the lane's whole first-parent spine, newest first: its head is the
    lane tip and the first parent of its oldest commit is the commit the lane was
    cut from. Both are recorded as refs for the verifier, never read here.
    """
    state: dict[str, str | None] = dict.fromkeys(lane_deletions)
    state.update(dict(lane_blobs))
    approved_wps = tuple(wp for wp in lane.wp_ids if _is_approved_wp(wp, work_packages))
    ancestors = _dependency_lane_ids(lanes_manifest, lane)
    return ApprovedLaneContent(
        lane_id=lane.lane_id,
        wp_ids=approved_wps,
        ancestors=frozenset(ancestors),
        final_state=state,
        tip=spine[0] if spine else None,
        fork_point=f"{spine[-1]}^" if spine else None,
        dependency_forks=_dependency_forks(repo_root, lanes_manifest, _lane_branch_for(lanes_manifest, lane.lane_id), spine, ancestors),
    )


def _approved_stamps(lane: object, work_packages: Mapping[str, Mapping[str, object]], presence: _PresenceScope | None) -> tuple[str, ...]:
    """The approval stamps of *lane*'s WPs that are in an approved membership lane (#7307); canceled WPs never count."""
    if presence is None:
        return ()
    stamps: list[str] = []
    for wp in getattr(lane, "wp_ids", ()):
        if not _is_approved_wp(wp, work_packages):
            continue
        # #7802: the pre-sync stamp is a reach anchor too. It is a first-parent ancestor
        # of ``lane_head``, so it never keeps a merge ``lane_head`` would not keep, and it
        # still reaches the lane's earlier merges in a clone that lacks the reviewer's
        # unpushed sync merge (``lane_head``).
        for stamp in (presence.approval_stamps.get(wp), presence.approval_presync_stamps.get(wp)):
            if stamp:
                stamps.append(stamp)
    return tuple(stamps)


def _drop_unreviewed_merges(repo_root: Path, spine: list[str], stamps: Sequence[str]) -> list[str]:
    """*spine* less every merge commit no approval stamp in *stamps* reaches (#7307).

    Returns *spine* itself when nothing is dropped. A merge whose parents cannot be read
    is dropped (attributes less; the verifier then REFUSEs on its own probe error).
    """
    kept: list[str] = []
    dropped = False
    for sha in spine:
        try:
            merge = is_merge_commit(repo_root, sha)
        except GitProbeError:
            dropped = True
            continue
        if not merge or any(sha_reachable_from(repo_root, sha, stamp) for stamp in stamps):
            kept.append(sha)
        else:
            dropped = True
    return kept if dropped else spine


def _own_dependency_merges(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    lane: object,
    work_packages: Mapping[str, Mapping[str, object]],
    spine: Sequence[str],
) -> frozenset[str]:
    """*lane*'s merges of its declared, not fully canceled, dependency lanes on its *spine* (#7307)."""
    tips = [
        _lane_branch_for(lanes_manifest, dep.lane_id)
        for dep in lanes_manifest.lanes
        if dep.lane_id in tuple(getattr(lane, "depends_on_lanes", ()) or ()) and _lane_is_approved(dep, work_packages)
    ]
    # ``lane_dependency_merges`` comes from a mypy-skipped module (#7334): the
    # typed local keeps the return honest instead of leaking ``Any``.
    merges: frozenset[str] = lane_dependency_merges(repo_root, spine, tips)
    return merges


def _trusted_history_roots(
    lanes_manifest: LanesManifest,
    lane: ExecutionLane,
    work_packages: Mapping[str, Mapping[str, object]],
    presence: _PresenceScope | None,
    coord_base_ref: str,
) -> tuple[str, ...]:
    """The refs whose history a reviewed merge on *lane* may bring in as authorship (#7626).

    The Mission branch, both as the claim measures from it (*coord_base_ref*, which a
    coordination topology freezes at the first attempt's tip) and as the run froze it
    (``presence.mission_tip``, the pre-mutation tip: an operator's resolutions of conflicts
    live there and reach a lane only through a merge the lane's reviewer then saw). The
    LIVE branch is never a root: a foreign branch merged into a lane before its approval
    and into the Mission branch afterwards would otherwise turn trusted, the #4977 carrier
    shape. The target's pre-run tip (``presence.base``: content the
    target already had), and the approval stamps of every OTHER approved lane's WPs
    (content in another reviewed tip). The
    lane's own stamps are left out: they reach every merge on its own spine, so they
    would trust any branch merged into the lane, the #4977 carrier shape.
    """
    if presence is None:
        return ()
    roots = [coord_base_ref, presence.mission_tip or "", presence.base]
    for other in lanes_manifest.lanes:
        if other.lane_id != lane.lane_id and _lane_is_approved(other, work_packages):
            roots.extend(_approved_stamps(other, work_packages, presence))
    return tuple(dict.fromkeys(root for root in roots if root))


def _authoring_merges(repo_root: Path, spine: Sequence[str], roots: Sequence[str]) -> frozenset[str]:
    """The merge commits on *spine* that author what they brought into the lane (#7626).

    *spine* is the lane's reviewed authorship spine (:func:`_drop_unreviewed_merges`
    already removed every merge no approval stamp reaches), so each merge here was in
    a reviewed tip. It authors only when EVERY non-first parent is trusted history,
    reachable from one of *roots* (:func:`_trusted_history_roots`): the mission
    branch, the target's pre-run tip, or another approved lane's reviewed tip. A
    merge of any other branch (a foreign or removed WP's branch, the #4977 carrier)
    authors nothing, as before #7626. A probe error leaves the merge out (attributes
    less; fail-closed).

    Not the same question as :func:`_own_dependency_merges` (#7307), which keeps a
    lane's merges of its DECLARED dependency lanes as authorship by SHA only (the
    closed-world axis). This one decides which merges author BLOBS for the squash
    axis, over a wider root set. Keep the two trust models apart.
    """
    if not roots:
        return frozenset()
    authoring: set[str] = set()
    for sha in spine:
        try:
            parents = commit_parents(repo_root, sha)
        except GitProbeError:
            continue
        if len(parents) < 2:
            continue
        if all(any(sha_reachable_from(repo_root, parent, root) for root in roots) for parent in parents[1:]):
            authoring.add(sha)
    return frozenset(authoring)


def _final_authored_walk(
    repo_root: Path,
    first_parent_shas: list[str],
    *,
    authoring_merges: frozenset[str] = frozenset(),
    keep: Callable[[str, str], bool] | None = None,
) -> tuple[set[tuple[str, str]], set[str]]:
    """FINAL ``(path, blob)``s AND final DELETED paths across a lane's first-parent spine (F5, #5022).

    Walks the spine newest→oldest (``git rev-list`` order) and, per path, keeps
    only the FIRST (hence newest, hence final) state seen — so a superseded
    intermediate ``v1`` is dropped in favor of the lane's final ``v2``, and a path
    deleted-then-re-added ends up present (in ``blobs``), never in ``deletions``. A
    merge commit on the spine contributes nothing (its combined diff is empty for
    a clean auto-merge), so a second-parent-smuggled blob/deletion is never
    recorded as authored. Each newly seen path is read ONCE, with
    :func:`path_state_at` at its newest touching commit. ``None`` means the path is
    absent there: its newest touching commit deletes it, so it is marked seen and
    recorded in ``deletions`` instead of ``blobs`` — the lane's own final state for
    that path IS "deleted", so it is legitimate authored authority for the squash
    deletion-attribution axis (#5022), not merely "no shippable blob". A raised
    :class:`GitProbeError` means the history could not be read; that is never a
    deletion (#5048(b)). It propagates, re-raised with the path and the commit
    named, so the claim refuses through its existing probe-error channel.

    Computed in ONE spine walk (not two) so :func:`_collect_authored` — the sole
    production caller — never re-reads the same commits' diffs twice.

    *authoring_merges* (#7626) are the spine's merge commits that author what they
    brought in (:func:`_authoring_merges`: reviewed, and every non-first parent is
    trusted history). For those, the touched paths are the merge's first-parent
    diff (:func:`first_parent_changed_paths`) instead of its combined diff, so the
    blob the merge left at a path is the lane's final state there. Every other
    merge keeps contributing nothing, as above. Empty by default: the presence axis
    and every pre-#7626 caller read the walk unchanged.

    *keep* (#7860) is ``(sha, path) -> bool``: a path whose newest touching commit it rejects is
    marked seen and recorded nowhere, so an older commit cannot stand in for it. ``None`` keeps
    every path.

    FIX D (#5001 landing remediation) — the invariant this axis rests on: the
    squash content axis's soundness depends on lanes being sliced by DISJOINT
    write-scope (project doctrine: lanes collapse by write-scope, not
    dependency — each lane owns a distinct set of paths). Under that invariant
    each content path is authored by exactly ONE approved lane, so "the FINAL
    first-parent blob per (lane, path), unioned across approved lanes" and "the
    final blob per path, full stop" coincide — there is no path two approved
    lanes both touch to disambiguate between. When two approved lanes DO modify
    the SAME path (the invariant violated in practice), this axis alone would
    false-FAIL whenever their independently-resolved final blobs differ from the
    squash's (correctly merged/rebased) resolution. That gap is closed
    downstream for every derivable shape (#7626, widening #5051's two-lane
    recognizer): :func:`is_legitimate_merge_resolution` attributes the CLEAN
    ``git merge-tree`` fold of every approved lane that authored the path plus
    the target's pre-run tip, and a reviewed merge whose second parent is
    trusted history authors what it brought in (*authoring_merges*, below). Only
    a hand resolution that reached the target outside any reviewed lane stays
    unattributable, pinned as
    ``test_squash_three_way_merge_resolution_is_unattributable`` (strict
    ``xfail``, #5053). That is the SAFE direction (refuse/rollback a legitimate
    merge, never ship unattributed content).
    """
    seen_paths: set[str] = set()
    blobs: set[tuple[str, str]] = set()
    deletions: set[str] = set()
    for sha in first_parent_shas:
        touched = first_parent_changed_paths(repo_root, sha) if sha in authoring_merges else changed_paths_of(repo_root, sha)
        for path in touched:
            if path in seen_paths:
                continue
            seen_paths.add(path)
            if keep is not None and not keep(sha, path):
                continue
            try:
                state = path_state_at(repo_root, sha, path)
            except GitProbeError as exc:
                raise GitProbeError(f"reading {path} at {sha[:10]} on the lane spine failed: {exc}") from exc
            if state is None:
                deletions.add(path)  # absent at its newest touching commit: final state deleted
            else:
                blobs.add((path, state))
    return blobs, deletions


def _final_authored_blobs(repo_root: Path, first_parent_shas: list[str]) -> set[tuple[str, str]]:
    """FINAL ``(path, blob)`` per path across a lane's first-parent spine (F5).

    Thin wrapper over :func:`_final_authored_walk` kept as an independently
    testable/importable name; :func:`_collect_authored` calls the combined walk
    directly rather than through this wrapper, to avoid a second spine walk.
    """
    blobs, _deletions = _final_authored_walk(repo_root, first_parent_shas)
    return blobs


def _final_authored_deletions(repo_root: Path, first_parent_shas: list[str]) -> set[str]:
    """FINAL deleted paths across a lane's first-parent spine (#5022 / WP1 T002).

    A path P is a member iff the FIRST (newest) commit on the spine that touches
    P deletes it — the lane's own final state for P is "deleted". A path
    added-then-deleted within the lane IS a member (final state deleted); a path
    deleted-then-re-added is NOT (its final state is present, and it is in
    :func:`_final_authored_blobs` instead — see :func:`_final_authored_walk` for
    the shared newest-first spine walk both draw from).

    Thin wrapper over :func:`_final_authored_walk`, kept as an independently
    testable/importable name; :func:`_collect_authored` calls the combined walk
    directly rather than through this wrapper, to avoid a second spine walk.
    """
    _blobs, deletions = _final_authored_walk(repo_root, first_parent_shas)
    return deletions


def _record_lane_path_contribution(
    path_contributions: dict[str, list[LaneContribution]],
    lane: ExecutionLane,
    lane_blobs: set[tuple[str, str]],
    authored: list[str],
) -> None:
    """Record *lane*'s contribution to every path in its own FINAL blob set.

    Extracted from :func:`_collect_authored` (Sonar complexity ceiling): a lane
    with no authored commits or no final blobs contributes nothing (there is
    no still-resolvable lane commit to record). *authored* is the lane's first-parent
    spine AFTER the fully-canceled lanes' commits are dropped (#5569), so a canceled
    commit is never recorded as the lane's commit. ``authored[0]`` (newest) is
    the lane's own tip on its first-parent spine — a raw SHA, always resolvable
    for the lifetime of the transaction even after a branch ref is deleted; it
    CAN be a merge commit, which is exactly why a fresh :class:`LaneContribution`
    is built PER PATH (never one shared object reused across every path): each
    carries THIS path's own final first-parent-authored blob
    (:attr:`LaneContribution.authored_blob`, ``_blob`` from *lane_blobs*) — the
    fail-closed guard input :func:`is_legitimate_merge_resolution` checks
    the lane's raw tip-tree blob against before trusting a simulation that feeds
    that tip's FULL tree (#5124 landing fold).
    """
    if not lane_blobs or not authored:
        return
    lane_commit = authored[0]
    for path, blob in lane_blobs:
        path_contributions.setdefault(path, []).append(LaneContribution(lane_id=lane.lane_id, lane_commit=lane_commit, authored_blob=blob))


class _AuthoredClaim(NamedTuple):
    """What :func:`_collect_authored` derives from the approved lanes' spines, in its historical positional order."""

    shas: frozenset[str]
    patch_ids: frozenset[str]
    blobs: frozenset[tuple[str, str]]
    deletions: frozenset[str]
    path_contributions: Mapping[str, tuple[LaneContribution, ...]]
    lane_content: tuple[ApprovedLaneContent, ...]


@dataclass(frozen=True)
class _PresenceScope:
    """What the presence axis measures every approved code lane from (#5788, #5792 review M1).

    ``base`` is the target's pre-mutation tip (:func:`_bound_claim_base`). ``carried``
    are the commits after ``base`` the mission branch (*coord_base_ref*) already
    holds, or ``None`` when that range cannot be read. ``lane_bases`` maps a lane id
    to its own base, the lane head when its first governed work began
    (:func:`~specify_cli.consolidation.wp_attribution.first_governed_open_stamp`, the
    closed world's first anchor), ``None`` when no stamp names it. ``canceled`` are
    the fully-canceled lanes' own commits measured from ``base`` (L1: the same base as
    the spine they are subtracted from).
    """

    base: str
    carried: frozenset[str] | None
    lane_bases: Mapping[str, str | None]
    canceled: frozenset[str]
    #: Each WP's newest approval stamp (:func:`approval_stamp`), ``None`` when unstamped (#7307).
    approval_stamps: Mapping[str, str | None] = field(default_factory=dict)
    #: Each WP's newest approval's pre-sync stamp (:func:`approval_presync_stamp`), ``None`` when absent (#7802).
    approval_presync_stamps: Mapping[str, str | None] = field(default_factory=dict)
    #: The Mission branch's frozen tip (SHA) the run measures from, ``None`` when none is known (#7626).
    mission_tip: str | None = None


def _presence_scope(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    excluded_ids: frozenset[str],
    *,
    base: str,
    coord_base_ref: str,
    events: Sequence[Any] | None,
    mission_tip: str | None = None,
) -> _PresenceScope:
    """Build the :class:`_PresenceScope` of one claim: one range read for the mission branch, the event log already read."""
    try:
        carried: frozenset[str] | None = frozenset(commits_in_range(repo_root, base, coord_base_ref))
    except GitProbeError:
        carried = None
    lane_bases = {lane.lane_id: first_governed_open_stamp(events, frozenset(lane.wp_ids)) for lane in lanes_manifest.lanes} if events is not None else {}
    # The gate-time presence axis reads the dependency-lane tips live (FR-015 freezes the claim-time readers only).
    canceled = _fully_canceled_lane_commits(repo_root, lanes_manifest, excluded_ids, base, base, frozen_tips=None)
    wp_ids = [wp for lane in lanes_manifest.lanes for wp in lane.wp_ids] if events is not None else []
    stamps = {wp: approval_stamp(events, wp) for wp in wp_ids} if events is not None else {}
    presync = {wp: approval_presync_stamp(events, wp) for wp in wp_ids} if events is not None else {}
    return _PresenceScope(
        base=base,
        carried=carried,
        lane_bases=lane_bases,
        canceled=canceled,
        approval_stamps=stamps,
        approval_presync_stamps=presync,
        mission_tip=mission_tip,
    )


def _presence_range_unreadable_refusal(
    lanes_manifest: LanesManifest,
    work_packages: Mapping[str, Mapping[str, object]],
    presence: _PresenceScope,
    coord_base_ref: str,
) -> str | None:
    """The refusal text when an approved code lane would be measured from a mission-branch range that cannot be read, else ``None``.

    Fail-closed, like the squash blob axis (#5013: a git-probe error REFUSEs, it never
    passes vacuously): measuring the lane from *coord_base_ref* instead would restore the
    reading #5788 exists to prevent, so a release that dropped approved code over an
    unreadable range would ship. A claim with no approved code lane measures nothing
    here and is not refused.
    """
    if presence.carried is not None:
        return None
    if not any(_lane_is_approved(lane, work_packages) and not is_planning_lane(lane) for lane in lanes_manifest.lanes):
        return None
    return (
        f"the commits between '{presence.base}' and the mission branch ('{coord_base_ref}') could not be read, "
        "so the approved lanes' code cannot be checked for presence on the target. "
        "Recovery: restore or repair that branch, then re-run"
    )


def _commits_before(repo_root: Path, base: str, lane_base: str | None) -> frozenset[str] | None:
    """The commits after *base* that *lane_base* reaches (they predate the lane's own work), or ``None`` when unknown."""
    if lane_base is None:
        return None
    try:
        return frozenset(commits_in_range(repo_root, base, lane_base))
    except GitProbeError:
        return None


def _presence_spine(repo_root: Path, presence: _PresenceScope, lane_id: str, branch: str) -> list[str]:
    """*lane*'s presence spine: ``base..lane`` first-parent, less what the mission branch carried from before the lane's own base.

    A commit the mission branch carries is the lane's own only when the lane's own
    base does not reach it: the lane authored it after its first governed claim and
    an earlier attempt merged it (#5788). A mission-branch commit made outside every
    lane before the lane was cut is reached by that base and is never the lane's
    content (M1). With no readable lane base every carried commit is dropped, the
    pre-#5788 reading. Raises :class:`GitProbeError` when the mission-branch range
    cannot be read: the claim refuses first (:func:`_presence_range_unreadable_refusal`),
    and this never falls back to the authorship walk, the reading #5788 prevents.
    """
    if presence.carried is None:
        raise GitProbeError(f"the commits after '{presence.base}' that the mission branch carries could not be read")
    before = _commits_before(repo_root, presence.base, presence.lane_bases.get(lane_id))
    dropped = presence.carried if before is None else presence.carried & before
    return [sha for sha in _lane_first_parent_spine(repo_root, presence.base, branch) if sha not in dropped]


def _presence_lane_content(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    lane: ExecutionLane,
    work_packages: Mapping[str, Mapping[str, object]],
    walk: _LaneWalk,
    presence: _PresenceScope | None,
    canceled_lane_commits: frozenset[str],
) -> ApprovedLaneContent:
    """*lane*'s :class:`ApprovedLaneContent`, measured from the lane's own base (:func:`_presence_spine`).

    The fully-canceled lanes' commits are dropped before the final states are read,
    both the claim's set and the one measured from the presence base (L1). The
    authorship walk is reused when the presence spine is the same commit list and
    drops nothing more (the common case: the mission branch carries none of the
    lane's commits), so no second diff walk is paid then (L2).
    """
    if presence is None:
        return _lane_content(repo_root, lanes_manifest, lane, work_packages, walk.spine, walk.blobs, walk.deletions)
    spine = _presence_spine(repo_root, presence, lane.lane_id, walk.branch)
    canceled = canceled_lane_commits | presence.canceled
    authored = [sha for sha in spine if sha not in canceled]
    if spine == walk.spine and authored == [sha for sha in walk.spine if sha not in canceled_lane_commits]:
        return _lane_content(repo_root, lanes_manifest, lane, work_packages, walk.spine, walk.blobs, walk.deletions)
    blobs, deletions = _final_authored_walk(repo_root, authored)
    return _lane_content(repo_root, lanes_manifest, lane, work_packages, spine, blobs, deletions)


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
    commits it credits, so its final-state walk reads ``first_parent`` instead: a path whose newest
    change it does not credit (a merge, review 6) is then attributed to nothing, never to an older commit.
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


def _lane_final_walk(repo_root: Path, walk: _LaneAuthorshipWalk, dropped: frozenset[str]) -> tuple[set[tuple[str, str]], set[str]]:
    """:func:`_final_authored_walk` of *walk* less the *dropped* commits.

    A scoped walk (#7860) reads the whole first-parent spine and keeps a path only where its newest
    change is credited by an approved work package's own window (:meth:`_PlanningScope.owns`), so a
    merge that last changed the path (review 6) leaves it attributed to nothing.
    """
    if walk.scope is None:
        return _final_authored_walk(repo_root, [sha for sha in walk.spine if sha not in dropped])
    return _final_authored_walk(repo_root, [sha for sha in walk.first_parent if sha not in dropped], keep=walk.scope.owns)


def _collect_authored(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    work_packages: Mapping[str, Mapping[str, object]],
    coord_base_ref: str,
    sb_window: tuple[str, str] | None = None,
    *,
    canceled_lane_commits: frozenset[str],
    presence: _PresenceScope | None = None,
    events: Callable[[], Sequence[Any] | None] | None = None,
) -> _AuthoredClaim:
    """Approved lanes → their OWN first-parent SHAs + patch-ids + FINAL blobs + FINAL deletions + multi-lane paths.

    The authorship claim the closed-world content checks attribute against. A lane
    contributes its authorship only when at least one of its WPs is approved/done (a
    fully-canceled lane's commits are NOT approved authorship). Authorship is the
    lane's **first-parent** spine (``git rev-list --first-parent``): a commit a lane
    merged IN from another branch (a removed WP's commit smuggled via a carrier
    merge's second parent) is excluded, so it is never mistaken for approved work.
    Merge commits on the spine yield an empty patch-id and contribute only their SHA.

    *canceled_lane_commits* (#5569, :func:`_fully_canceled_lane_commits`) are dropped
    from every lane's spine before anything is derived from it: a fully-canceled
    dependency lane's commit that the allocator fast-forwarded onto an approved lane's
    first-parent spine is canceled content, never approved authorship. Dropping it
    here removes its SHA, patch-id, blob and deletion from the claim at once, so
    ``_collect_excluded`` keeps it excluded and the squash blob axis cannot attribute
    it. Only the canceled lane's OWN commits go; the approved lane's own commits, and
    ancestry both lanes inherited, stay.

    ``authored_blobs`` (#5013 WS1) is the squash-sound content axis's authority: the
    FINAL first-parent blob per (lane, path), unioned across approved lanes.
    ``authored_deletions`` (#5022 / WP1) is its deletion analogue: the FINAL
    first-parent-DELETED path per lane, unioned across approved lanes — the
    squash deletion-attribution axis's authority for a legitimate approved
    deletion.

    The fifth element, ``path_contributions`` (FR-009 of #5051, widened by #7626;
    smuggled-tip guard from the #5124 landing fold), is derived in this SAME
    per-lane walk, never a second one: for each approved lane, every path in that
    lane's own ``lane_blobs`` records its OWN per-path :class:`LaneContribution`
    (:func:`_record_lane_path_contribution`), carrying that path's own authored
    blob. Every path at least one lane authored is present, with all its
    contributions in manifest order: the merge derivation folds them with the
    target's pre-run tip (:func:`is_legitimate_merge_resolution`).

    A CODE lane's reviewed merges whose every non-first parent is trusted history
    (:func:`_authoring_merges` over :func:`_trusted_history_roots`: the mission
    branch, the target's pre-run tip, another approved lane's approval stamps)
    author what they brought in (#7626): the walk then reads them through their
    first-parent diff. The presence element below keeps the plain walk.

    The sixth element (#5571) is each approved CODE lane's final path state in
    dependency order (:class:`ApprovedLaneContent`), taken from that same walk.
    A planning (repo-root) lane is left out: its commits already sit on the
    target, so there is nothing to integrate and nothing to be missing.

    *presence* (#5788, #5792 review M1, :class:`_PresenceScope`) is what that sixth
    element measures a lane from: ``base..lane`` from the target's pre-mutation tip
    (:func:`_bound_claim_base`), less the commits the mission branch already carries
    that the lane's own base (its first governed claim stamp) also reaches. Measured
    from *coord_base_ref* alone, a lane the mission branch already carries (an
    earlier attempt merged it; that attempt's later commit, kept by the operator,
    then dropped its content) has an empty range, so its approved content would
    never be judged; measured from the target tip alone, a mission-branch commit
    made outside every lane before the lane was cut would read as the lane's
    approved content. The authorship axes keep *coord_base_ref*. ``None`` measures
    from *coord_base_ref* too.

    *events* (#7860) reads the status events for the planning lane's per-work-package windows
    (:func:`_planning_window_starts`); without it a default Mission's planning lane authors nothing.
    """
    shas: set[str] = set()
    patch_ids: set[str] = set()
    blobs: set[tuple[str, str]] = set()
    deletions: set[str] = set()
    path_contributions: dict[str, list[LaneContribution]] = {}
    lane_contents: list[ApprovedLaneContent] = []
    for lane in lanes_manifest.lanes:
        if not _lane_is_approved(lane, work_packages):
            continue
        walk = _planning_walk(repo_root, lanes_manifest, lane, work_packages, coord_base_ref, sb_window, events)
        base, branch, first_parent, whole = walk.base, walk.branch, walk.spine, walk.whole
        full_authored = [sha for sha in first_parent if sha not in canceled_lane_commits]
        full_blobs, full_deletions = _lane_final_walk(repo_root, walk, canceled_lane_commits)
        # #7307 review: a merge on the spine counts toward this lane's authorship only
        # when one of its approved WPs' approval stamps reaches it (it was in a reviewed
        # tip). A merge made after the approval is the lane's unreviewed work: the
        # approved bound skips merges, so it is left out here and the verifier judges
        # what it adds beyond its parents (a clean merge carries nothing; any own
        # content FAILs), on the closed-world and the squash blob axes alike.
        reviewed = full_authored if is_planning_lane(lane) else _drop_unreviewed_merges(repo_root, full_authored, _approved_stamps(lane, work_packages, presence))
        # Presence (#5788/#5571): measured from the FULL ``coord_base_ref..lane``
        # spine, unchanged — approved content must be PRESENT on the target.
        if not is_planning_lane(lane):
            lane_contents.append(
                _presence_lane_content(
                    repo_root,
                    lanes_manifest,
                    lane,
                    work_packages,
                    _LaneWalk(base, branch, first_parent, full_blobs, full_deletions),
                    presence,
                    canceled_lane_commits,
                )
            )
        # Authorship (#5968): the squash blob-attribution axis attributes a
        # target blob to the claim when it is some approved lane's authored
        # content. A DEPENDENT lane fast-forwards its dependency's commits onto
        # its own first-parent spine at implement time; when the dependency is
        # REWRITTEN (reset/amend) and re-approved after the fork, that stale
        # inherited copy is no longer reachable from the re-approved dependency
        # but still rides the dependent lane's spine, so the default squash
        # lands it and the axis would attribute it to the dependent lane. Bound
        # such a lane's authorship to its OWN creation base
        # (``first_governed_open_stamp``, carried on ``presence.lane_bases``):
        # everything that base reaches predates the lane's own work and is the
        # dependency's authorship, never this lane's. Measuring from the lane's
        # own base rather than the dependency's current tip is what catches the
        # rewrite. Shrinking the authorship is the fail-closed direction (never
        # attributes more).
        #
        # Only lanes that DECLARE a dependency are bounded: an independent
        # lane's first-parent spine is entirely its own authorship, with nothing
        # inherited to exclude, so bounding it could only wrongly drop its own
        # content (e.g. when its first-claim stamp was recorded at a later tip
        # rather than the creation base). Gating on ``depends_on_lanes`` keeps
        # the fix to the exact shape it closes.
        authored = reviewed
        lane_blobs, lane_deletions = (full_blobs, full_deletions) if reviewed is full_authored else _final_authored_walk(repo_root, reviewed)
        lane_own_base = presence.lane_bases.get(lane.lane_id) if (presence is not None and not is_planning_lane(lane) and lane.depends_on_lanes) else None
        if lane_own_base is not None:
            own = lane_own_commits(repo_root, base, reviewed, [lane_own_base])
            if len(own) != len(reviewed):
                authored = [sha for sha in reviewed if sha in own]
                lane_blobs, lane_deletions = _final_authored_walk(repo_root, authored)
        if not is_planning_lane(lane):
            authoring = _authoring_merges(repo_root, authored, _trusted_history_roots(lanes_manifest, lane, work_packages, presence, coord_base_ref))
            if authoring:
                lane_blobs, lane_deletions = _final_authored_walk(repo_root, authored, authoring_merges=authoring)
        # A scoped walk (#7860 review 2) admits by SHA and patch-id only the commits whose every
        # path is in scope or bookkeeping (``whole``); a mixed commit keeps only its in-scope blobs.
        for sha in authored if whole is None else [sha for sha in authored if sha in whole]:
            shas.add(sha)
            pid = patch_id_of(repo_root, sha)
            if pid:
                patch_ids.add(pid)
        # #7307: the lane's own REVIEWED dependency merges (``reviewed`` holds only
        # merges an approval stamp reaches) stay its authorship by SHA even when the
        # #5968 own-base bound above drops them (they predate the first claim stamp).
        # Only the SHA: their blobs stay the dependency's (#5968).
        shas |= _own_dependency_merges(repo_root, lanes_manifest, lane, work_packages, reviewed)
        blobs |= lane_blobs
        deletions |= lane_deletions
        _record_lane_path_contribution(path_contributions, lane, lane_blobs, authored)
    contributions_by_path = {path: tuple(contributions) for path, contributions in path_contributions.items()}
    return _AuthoredClaim(frozenset(shas), frozenset(patch_ids), frozenset(blobs), frozenset(deletions), contributions_by_path, _order_lane_content(lane_contents))


__all__ = [
    "StateAt",
    "_AuthoredClaim",
    "_PresenceScope",
    "_approved_stamps",
    "_collect_authored",
    "_commits_before",
    "_dependency_forks",
    "_drop_unreviewed_merges",
    "_dropped_own_change",
    "_final_authored_blobs",
    "_final_authored_deletions",
    "_final_authored_walk",
    "_lane_content",
    "_missing_entries",
    "_order_lane_content",
    "_own_dependency_merges",
    "_owns_change",
    "_path_gap",
    "_presence_gap",
    "_presence_lane_content",
    "_presence_range_unreadable_refusal",
    "_presence_scope",
    "_presence_spine",
    "_record_lane_path_contribution",
    "_started_from",
    "_unsuperseded_holders",
    "unmet_approved_content",
]
