"""Repo-root write-checkout occupancy and dirtiness helpers (#5100 IC-03 / T018).

A single_branch mission's repo-root lane has no worktree of its own -- every
WP in it executes directly in the shared write checkout. Two or more
single_branch missions (or two WPs of the same mission) can therefore contend
for that ONE checkout at once. This module supplies the two pure(ish) reads
``implement``'s repo-root-lane refusal path composes:

- :func:`in_progress_wps_in_write_checkout` -- is another WP (from ANY
  single_branch mission) already ``in_progress`` in this checkout?
- :func:`dirty_paths` -- does the checkout carry uncommitted changes outside
  spec-kitty's own status/runtime artifacts?

Kept out of ``worktree_allocator.py`` (a different concern: THAT module
allocates/reuses a *lane worktree*; this module inspects the *shared
repo-root checkout* no allocation ever touches) and out of
``workspace/context.py`` (a pure resolver, no git/status I/O).
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kernel.git import GitPath
from mission_runtime import MissionArtifactKind, MissionTopology, is_single_branch, placement_seam, resolve_topology, single_branch_write_ref

__all__ = ["SharedWorkspaceWriter", "dirty_paths", "in_progress_wps_in_write_checkout", "is_single_branch_repo_root_lane", "shared_workspace_writers"]

#: Lanes in which a WP counts as a writer of its workspace (advisory #5099 warning).
_WRITER_LANES: frozenset[str] = frozenset({"in_progress", "in_review"})
_IN_PROGRESS_LANES: frozenset[str] = frozenset({"in_progress"})


@dataclass(frozen=True)
class SharedWorkspaceWriter:
    """Another actor's WP that is ``in_progress`` / ``in_review`` in the same workspace."""

    mission_slug: str
    wp_id: str
    lane: str
    actor: str | None

    def warning(self) -> str:
        """The one-line advisory rendered by ``agent action implement`` / ``review`` (#5099)."""
        by = self.actor or "an unknown actor"
        return f"Warning: {self.mission_slug}/{self.wp_id} is {self.lane} by {by} in this workspace; one writer per checkout."


def is_single_branch_repo_root_lane(repo_root: Path, mission_slug: str, lane_or_workspace: object) -> bool:
    """True when *lane_or_workspace* is the repository-root lane of a ``single_branch`` Mission (the shared write checkout).

    The one predicate behind the claim lock, the repo-root claim guard and the shared-workspace
    advisory. *lane_or_workspace* is an :class:`~specify_cli.lanes.models.ExecutionLane` or a
    resolved workspace (anything :func:`specify_cli.lanes.compute.is_repo_root_lane` accepts).
    A planning WP of a lanes/coord Mission also sits in the repo-root lane, so the lane alone
    is not enough: the Mission's STORED topology must be ``single_branch`` as well.
    """
    from specify_cli.lanes.compute import is_repo_root_lane

    return bool(is_repo_root_lane(lane_or_workspace)) and is_single_branch(resolve_topology(repo_root, mission_slug))


def _repo_root_lane_claim(feature_dir: Path) -> tuple[frozenset[str], str | None]:
    """Repo-root-lane WP ids and the manifest's target branch for *feature_dir*.

    The WP ids are those assigned to a repo-root lane in ``lanes.json``: empty
    when the mission has no ``lanes.json`` (a legacy flat mission whose WPs
    never ran in the shared checkout) or no WP in a repo-root lane (an
    unmigrated single_branch mission keeps its WPs in CODE lanes -- each with
    its own worktree). A corrupt ``lanes.json`` also reads as empty: one bad
    mission's manifest must not block every OTHER mission's implement.

    The target branch is the manifest's ``target_branch`` -- the value the
    claim path pins an occupant's write branch from -- returned from the same
    read so the scan needs no second one; ``None`` when there is no usable
    manifest.
    """
    from specify_cli.lanes.compute import is_repo_root_lane
    from specify_cli.lanes.persistence import CorruptLanesError, read_lanes_json

    try:
        manifest = read_lanes_json(feature_dir)
    except CorruptLanesError:
        return frozenset(), None
    if manifest is None:
        return frozenset(), None
    wp_ids = frozenset(wp_id for lane in manifest.lanes if is_repo_root_lane(lane) for wp_id in lane.wp_ids)
    return wp_ids, manifest.target_branch


def _writes_to_another_branch(
    meta: Mapping[str, Any],
    topology: MissionTopology,
    lanes_target_branch: str | None,
    current_branch: str | None,
) -> bool:
    """True when the mission's write branch is known, agreed and is not *current_branch* (#5680).

    A single_branch mission's status is authoritative only on its write
    branch: the protected-target mint recorded as ``meta.json``
    ``mission_branch``, else the target branch
    (:func:`mission_runtime.single_branch_write_ref`, the one write-branch
    rule). A copy of its status on any other branch -- carried there by
    branching off, or by integrating a merge without ``consolidate`` -- is a
    snapshot, not the mission's live state, so it cannot occupy this checkout.

    The write branch is computed from BOTH places that name a target: the
    scan's ``meta.json`` ``target_branch`` and *lanes_target_branch* (the
    manifest value the claim path pins an occupant's write branch from,
    ``workspace.context``). The mission is skipped only when both yield the
    SAME ref and it is not *current_branch*. Fails closed (``False``: the
    mission still counts) whenever anything is unknown or contested: a
    detached HEAD, no usable target in either file, or the two files naming
    different write branches -- then the WP may be claimable on the current
    branch, so it must keep blocking. This deliberately does not apply the
    primary-branch default of
    :func:`specify_cli.core.paths.read_target_branch_from_meta`: an occupant
    whose target is unrecorded keeps blocking rather than being assumed to
    write elsewhere. *meta* is the mission's already-loaded ``meta.json``;
    this reads nothing itself.
    """
    if current_branch is None:
        return False
    meta_target = meta.get("target_branch")
    if not isinstance(meta_target, str) or not meta_target:
        return False
    if not isinstance(lanes_target_branch, str) or not lanes_target_branch:
        return False
    mission_branch = meta.get("mission_branch")
    meta_ref = single_branch_write_ref(topology, mission_branch, meta_target)
    lanes_ref = single_branch_write_ref(topology, mission_branch, lanes_target_branch)
    return meta_ref == lanes_ref and meta_ref != current_branch


def _occupancy_candidate_wp_ids(feature_dir: Path, current_branch: str | None) -> frozenset[str]:
    """Repo-root-lane WP ids of *feature_dir* when its mission can occupy the checkout.

    Empty for every mission that cannot hold the shared write checkout, so the
    caller reads the status log only for real candidates (filters 1-4 of
    :func:`in_progress_wps_in_write_checkout`): a mission whose ``meta.json``
    cannot be read, whose stored topology is not ``single_branch``, that has
    no WP in a repo-root lane, that is completed, or whose write branch --
    computed from ``meta.json`` AND ``lanes.json`` -- is agreed and is not
    *current_branch*.
    """
    from specify_cli.core.paths import MissionMetaReadError, load_meta_fail_closed
    from specify_cli.migration.backfill_topology import topology_from_meta
    from specify_cli.status import is_mission_completed

    # One meta.json read per mission and one lanes.json read per mission
    # (NFR-001): the topology and the write branch come from the meta dict, the
    # repo-root WP ids and the manifest's target from the single manifest read.
    try:
        meta = load_meta_fail_closed(feature_dir)
        if meta is None:
            return frozenset()
        topology = topology_from_meta(meta, feature_dir)
    except (MissionMetaReadError, ValueError):
        return frozenset()
    if not is_single_branch(topology):
        return frozenset()
    repo_root_wp_ids, lanes_target_branch = _repo_root_lane_claim(feature_dir)
    if not repo_root_wp_ids or is_mission_completed(feature_dir):
        return frozenset()
    if _writes_to_another_branch(meta, topology, lanes_target_branch, current_branch):
        return frozenset()
    return repo_root_wp_ids


def in_progress_wps_in_write_checkout(
    repo_root: Path,
    write_checkout: Path,
    *,
    exclude: tuple[str, str] | None = None,
) -> list[tuple[str, str]]:
    """Return ``(mission_slug, wp_id)`` pairs ``in_progress`` in *write_checkout*.

    A WP occupies the shared repo-root checkout only when it sits in a
    repo-root lane (:func:`specify_cli.lanes.compute.is_repo_root_lane`) of a
    mission whose STORED topology
    (:func:`specify_cli.migration.backfill_topology.topology_from_meta`) is
    ``single_branch``. Missions are filtered cheapest-first so the status-log
    read (the only expensive step) happens for real candidates only:

    1. stored topology is ``single_branch`` (one ``meta.json`` read);
    2. ``lanes.json`` exists and assigns at least one WP to a repo-root lane
       -- a legacy flat mission with no ``lanes.json`` (topology *derived* as
       single_branch) never ran a WP in the checkout, and neither did an
       unmigrated single_branch mission whose WPs sit in code lanes;
    3. the mission is not completed
       (:func:`specify_cli.status.is_mission_completed`);
    4. the mission's write branch, computed from ``meta.json`` AND
       ``lanes.json`` (#5680; see :func:`_writes_to_another_branch`), is
       the branch *write_checkout* is on, or cannot be established -- a
       detached HEAD, no usable target in either file, or the two files
       naming different write branches all fail closed (the mission
       counts). A status copy on any other branch is not that mission's
       live status, so a mission merged into this branch without
       ``consolidate`` no longer occupies it;
    5. the status snapshot: a repo-root-lane WP whose lane is ``in_progress``.

    A single_branch mission's write checkout has no persisted alternate root
    (``effective_root`` is a per-invocation resolver parameter, never written
    to disk), so every such mission's checkout is *repo_root* -- compared
    against *write_checkout* directly rather than re-resolving each mission's
    workspace.

    A mission whose ``meta.json`` cannot be read (missing/corrupt) is
    skipped: it never rendered here before this scan existed either, and one
    bad mission's metadata must not block every OTHER mission's implement.

    *exclude* removes one ``(mission_slug, wp_id)`` pair from the result --
    the caller's own WP, so resuming a WP it already holds ``in_progress``
    never reads as occupancy by another WP (contract's resume exemption).
    """
    occupied = _writers_in_write_checkout(repo_root, write_checkout, lanes=_IN_PROGRESS_LANES, exclude=exclude)
    return [(writer.mission_slug, writer.wp_id) for writer in occupied]


def _writers_in_write_checkout(
    repo_root: Path,
    write_checkout: Path,
    *,
    lanes: Collection[str],
    exclude: tuple[str, str] | None,
) -> list[SharedWorkspaceWriter]:
    """The occupancy scan of :func:`in_progress_wps_in_write_checkout`, generalised to any *lanes*."""
    from specify_cli.context.mission_resolver import FsMissionResolver
    from specify_cli.core.git_ops import get_current_branch
    from specify_cli.status import read_events as _read_events
    from specify_cli.status import reduce as _reduce_events

    write_checkout_resolved = write_checkout.resolve()
    if write_checkout_resolved != repo_root.resolve():
        # No single_branch mission's checkout can be anything other than
        # repo_root without a persisted alternate root -- see the docstring.
        return []

    # One branch read per scan (NFR-001): every candidate is compared to it.
    current_branch = get_current_branch(write_checkout_resolved)
    occupied: list[SharedWorkspaceWriter] = []
    # One walk of kitty-specs/ (the resolver port); the per-mission seam
    # lookup would re-walk the tree for every mission (quadratic).
    for mission in FsMissionResolver(repo_root).all_missions():
        mission_slug = mission.mission_slug
        repo_root_wp_ids = _occupancy_candidate_wp_ids(mission.feature_dir, current_branch)
        if not repo_root_wp_ids:
            continue

        # single_branch has no coordination partition: the status log is read
        # through the same seam, which resolves it to the primary mission dir.
        snapshot = _reduce_events(_read_events(placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.STATUS_STATE)))
        for wp_id, wp_state in snapshot.work_packages.items():
            if wp_id not in repo_root_wp_ids or exclude == (mission_slug, wp_id):
                continue
            lane = str(wp_state.get("lane"))
            if lane in lanes:
                actor = wp_state.get("actor")
                occupied.append(SharedWorkspaceWriter(mission_slug, wp_id, lane, str(actor) if actor else None))
    return occupied


def _lane_mates_writing(repo_root: Path, mission_slug: str, wp_id: str, lane_wp_ids: Sequence[str]) -> list[SharedWorkspaceWriter]:
    """Other WPs of the same lane worktree that are ``in_progress`` / ``in_review``."""
    from specify_cli.status import read_events as _read_events
    from specify_cli.status import reduce as _reduce_events

    mates = [other for other in lane_wp_ids if other != wp_id]
    if not mates:
        return []
    snapshot = _reduce_events(_read_events(placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.STATUS_STATE)))
    writers: list[SharedWorkspaceWriter] = []
    for other in mates:
        state = snapshot.work_packages.get(other)
        lane = str(state.get("lane")) if state else ""
        if lane in _WRITER_LANES:
            actor = state.get("actor") if state else None
            writers.append(SharedWorkspaceWriter(mission_slug, other, lane, str(actor) if actor else None))
    return writers


def shared_workspace_writers(
    repo_root: Path,
    mission_slug: str,
    wp_id: str,
    workspace: Any,
    actor: str | None,
) -> list[SharedWorkspaceWriter]:
    """Other actors' WPs ``in_progress`` / ``in_review`` in *workspace* (advisory, #5099; never refuses).

    A single_branch repo-root workspace is the shared write checkout, so the
    cross-Mission occupancy scan applies (generalised to both writer lanes). A lane
    worktree is shared by the other WPs of the same lane. The calling WP is
    excluded, and only a writer whose actor differs from *actor* is reported (an
    unknown actor counts as different).
    """
    from specify_cli.lanes.compute import is_repo_root_lane

    if is_repo_root_lane(workspace):
        if not is_single_branch_repo_root_lane(repo_root, mission_slug, workspace):
            return []
        found = _writers_in_write_checkout(repo_root, repo_root, lanes=_WRITER_LANES, exclude=(mission_slug, wp_id))
    else:
        found = _lane_mates_writing(repo_root, mission_slug, wp_id, list(getattr(workspace, "lane_wp_ids", []) or []))
    return [writer for writer in found if writer.actor is None or writer.actor != actor]


def _is_owned_path(path: GitPath, owned_prefixes: Sequence[str]) -> bool:
    """True when *path* is, or is nested under, one of *owned_prefixes*.

    A prefix ending in ``/`` owns the directory and everything below it (a
    collapsed untracked directory entry equal to the directory is owned too);
    any other prefix owns exactly that path. Comparison is by path component.
    """
    for prefix in owned_prefixes:
        owned = GitPath.parse(prefix)
        if prefix.endswith("/"):
            if owned.contains(path):
                return True
        elif path == owned:
            return True
    return False


def dirty_paths(write_checkout: Path, *, owned_prefixes: Sequence[str]) -> list[str]:
    """Return changed paths in *write_checkout*, excluding *owned_prefixes*.

    Reuses the worktree allocator's single ``git status`` vehicle
    (:func:`specify_cli.lanes.worktree_allocator._git_status_entries`)
    instead of duplicating its subprocess call. A path equal to, or nested
    under (prefix ending in ``/``), any of *owned_prefixes* -- spec-kitty's
    own status/runtime artifacts, e.g. ``kitty-specs/<slug>/status.events.jsonl``,
    ``kitty-specs/<slug>/status.json``, ``.kittify/`` -- is never reported as
    dirty; the caller decides the concrete prefix list (NFR-004: names what
    it excludes). A rename reports its new path.

    Raises:
        RuntimeError: ``git status`` failed (fail closed); the shared vehicle
            wraps the underlying :class:`~kernel.git.GitCommandError`.
    """
    from specify_cli.lanes.worktree_allocator import _git_status_entries

    paths: list[str] = []
    for entry in _git_status_entries(write_checkout):
        if not entry.path.parts or _is_owned_path(entry.path, owned_prefixes):
            continue
        paths.append(f"{entry.path}/" if entry.is_directory else str(entry.path))
    return paths
