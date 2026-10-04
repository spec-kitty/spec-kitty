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

from collections.abc import Sequence
from pathlib import Path

from kernel.git import GitPath
from mission_runtime import MissionArtifactKind, MissionTopology, is_single_branch, placement_seam, single_branch_write_ref

__all__ = ["dirty_paths", "in_progress_wps_in_write_checkout"]


def _repo_root_lane_wp_ids(feature_dir: Path) -> frozenset[str]:
    """WP ids assigned to a repo-root lane in *feature_dir*'s ``lanes.json``.

    Empty when the mission has no ``lanes.json`` (a legacy flat mission whose
    WPs never ran in the shared checkout) or no WP in a repo-root lane (an
    unmigrated single_branch mission keeps its WPs in CODE lanes -- each with
    its own worktree). A corrupt ``lanes.json`` also reads as empty: one bad
    mission's manifest must not block every OTHER mission's implement.
    """
    from specify_cli.lanes.compute import is_repo_root_lane
    from specify_cli.lanes.persistence import CorruptLanesError, read_lanes_json

    try:
        manifest = read_lanes_json(feature_dir)
    except CorruptLanesError:
        return frozenset()
    if manifest is None:
        return frozenset()
    return frozenset(wp_id for lane in manifest.lanes if is_repo_root_lane(lane) for wp_id in lane.wp_ids)


def _writes_to_another_branch(feature_dir: Path, topology: MissionTopology, current_branch: str | None) -> bool:
    """True when the mission's write branch is known and is not *current_branch* (#5680).

    A single_branch mission's status is authoritative only on its write
    branch: the protected-target mint recorded as ``meta.json``
    ``mission_branch``, else ``target_branch``
    (:func:`mission_runtime.single_branch_write_ref`, the one write-branch
    rule). A copy of its status on any other branch -- carried there by
    branching off, or by integrating a merge without ``consolidate`` -- is a
    snapshot, not the mission's live state, so it cannot occupy this checkout.

    Fails closed (``False``: the mission still counts) whenever either side is
    unknown: a detached HEAD, or no ``target_branch``. Called only after
    :func:`read_topology` has parsed the same ``meta.json``.
    """
    from specify_cli.core.paths import load_meta_fail_closed

    if current_branch is None:
        return False
    meta = load_meta_fail_closed(feature_dir) or {}
    target_branch = meta.get("target_branch")
    if not isinstance(target_branch, str) or not target_branch:
        return False
    return single_branch_write_ref(topology, meta.get("mission_branch"), target_branch) != current_branch


def _occupancy_candidate_wp_ids(feature_dir: Path, current_branch: str | None) -> frozenset[str]:
    """Repo-root-lane WP ids of *feature_dir* when its mission can occupy the checkout.

    Empty for every mission that cannot hold the shared write checkout, so the
    caller reads the status log only for real candidates (filters 1-4 of
    :func:`in_progress_wps_in_write_checkout`): a mission whose ``meta.json``
    cannot be read, whose stored topology is not ``single_branch``, that has
    no WP in a repo-root lane, that is completed, or whose write branch is not
    *current_branch*.
    """
    from specify_cli.core.paths import MissionMetaReadError
    from specify_cli.migration.backfill_topology import read_topology
    from specify_cli.status import is_mission_completed

    try:
        topology = read_topology(feature_dir)
    except (FileNotFoundError, MissionMetaReadError, ValueError):
        return frozenset()
    if not is_single_branch(topology):
        return frozenset()
    repo_root_wp_ids = _repo_root_lane_wp_ids(feature_dir)
    if not repo_root_wp_ids or is_mission_completed(feature_dir):
        return frozenset()
    if _writes_to_another_branch(feature_dir, topology, current_branch):
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
    (:func:`specify_cli.migration.backfill_topology.read_topology`) is
    ``single_branch``. Missions are filtered cheapest-first so the status-log
    read (the only expensive step) happens for real candidates only:

    1. stored topology is ``single_branch`` (one ``meta.json`` read);
    2. ``lanes.json`` exists and assigns at least one WP to a repo-root lane
       -- a legacy flat mission with no ``lanes.json`` (topology *derived* as
       single_branch) never ran a WP in the checkout, and neither did an
       unmigrated single_branch mission whose WPs sit in code lanes;
    3. the mission is not completed
       (:func:`specify_cli.status.is_mission_completed`);
    4. the mission's write branch is the branch *write_checkout* is on
       (#5680; see :func:`_writes_to_another_branch`) -- a status copy on
       any other branch is not that mission's live status, so a mission
       merged into this branch without ``consolidate`` no longer occupies
       it. Unknown branches fail closed;
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
    from specify_cli.context.mission_resolver import FsMissionResolver
    from specify_cli.core.git_ops import get_current_branch
    from specify_cli.status import Lane
    from specify_cli.status import read_events as _read_events
    from specify_cli.status import reduce as _reduce_events

    write_checkout_resolved = write_checkout.resolve()
    if write_checkout_resolved != repo_root.resolve():
        # No single_branch mission's checkout can be anything other than
        # repo_root without a persisted alternate root -- see the docstring.
        return []

    # One branch read per scan (NFR-001): every candidate is compared to it.
    current_branch = get_current_branch(write_checkout_resolved)
    occupied: list[tuple[str, str]] = []
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
            if wp_state.get("lane") == Lane.IN_PROGRESS:
                occupied.append((mission_slug, wp_id))
    return occupied


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
