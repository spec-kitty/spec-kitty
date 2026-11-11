"""The one status read door: a declared source per topology and coordination state.

ADR ``docs/adr/4.x/2026-11-06-2-one-status-read-contract.md`` (FR-001, FR-003, FR-004, FR-061,
NFR-001). :func:`resolve_status_read` is the only way a status read finds its source; readers
consume the returned :class:`StatusReadSurface` through :func:`read_status_events`,
:func:`read_status_stream`, :func:`read_status_text` and :func:`materialize_status`. Writers keep the write seam.

Sources (checked in this order):

1. the Mission has landed (``mission_runtime.mission_has_landed``) -> ``CONSOLIDATED_TARGET``,
   before any coordination probe, so a coordination branch torn down by consolidation never
   reads as ``CoordinationBranchDeleted``;
2. ``single_branch``, ``lanes`` and provisional Missions -> ``WRITE_CHECKOUT`` (the repository
   root checkout's working tree, or the validated owned checkout). For a
   ``topology_source: default`` Mission the write checkout is the checkout that holds the
   Mission topic branch (``meta.mission_branch``, FR-061); when no checkout holds it, a lane
   worktree holds it, or the holder carries no Mission directory, the declared source is the
   committed topic branch, ``MISSION_BRANCH_REF``;
3. ``coord`` / ``lanes_with_coord``:
   - materialized coordination worktree -> ``COORD_WORKTREE``;
   - empty or unmaterialized -> ``COORD_BRANCH_REF`` (one ``git cat-file --batch``);
   - the branch holds no log yet (pre-seed) -> ``WRITE_CHECKOUT`` with ``fallback_reason`` set;
   - deleted without landing -> ``CoordinationBranchDeleted`` (unchanged).

Every input root is normalized first: a lane root (and a coordination worktree root) re-anchors
to the main repository root, and an unreadable worktree registry fails closed.

``resolve_status_surface_with_anchor`` (``coordination/surface_resolver.py``) delegates its
source decision here and projects it to the legacy path form until WP06/WP07 move its callers
onto the door.
"""

from __future__ import annotations

import enum
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING

from mission_runtime import MissionTopology, routes_through_coordination

if TYPE_CHECKING:
    from mission_runtime import OwnedCheckout

    from specify_cli.coordination.status_service import RefRead
    from specify_cli.coordination.surface_resolver import CoordinationWorktreeUnmaterialized
    from specify_cli.status.models import EventStream, StatusEvent, StatusSnapshot

__all__ = [
    "materialize_status",
    "read_status_events",
    "read_status_stream",
    "read_status_text",
    "ref_source_remedy",
    "unmaterialized_coordination_refusal",
    "resolve_committed_status_read",
    "resolve_consolidated_target_read",
    "resolve_landing_evidence_read",
    "resolve_primary_partition_dir",
    "resolve_status_read",
]

_EVENTS_FILENAME = "status.events.jsonl"
_KITTY_SPECS = "kitty-specs"
_HEADS_PREFIX = "refs/heads/"
_TOPOLOGY_SOURCE_DEFAULT = "default"

PRE_SEED_FALLBACK_REASON = (
    "pre-seed: the coordination branch {branch!r} holds no {events} for this Mission yet, so the write checkout is read (declared fallback, ADR 2026-11-06-2)"
)


class StatusReadSource(enum.StrEnum):
    """The declared source of a status read (data model §2)."""

    WRITE_CHECKOUT = "write_checkout"
    """``single_branch``, ``lanes``, provisional; also the declared pre-seed fallback."""
    COORD_WORKTREE = "coord_worktree"
    """``coord`` / ``lanes_with_coord``, coordination worktree materialized."""
    COORD_BRANCH_REF = "coord_branch_ref"
    """``coord`` / ``lanes_with_coord``, coordination worktree empty or absent."""
    CONSOLIDATED_TARGET = "consolidated_target"
    """The Mission has landed on its target."""
    MISSION_BRANCH_REF = "mission_branch_ref"
    """A ``topology_source: default`` Mission whose topic branch no usable checkout holds (WP05 decision)."""


@dataclass(frozen=True)
class UnmaterializedCoordination:
    """The door's fact that a coordination worktree is not materialized (``CoordState.UNMATERIALIZED``).

    The door still reads the committed branch (or the declared pre-seed fallback) for such a
    Mission; this fact lets a caller that must refuse the cell (the ``next`` board selector,
    FR-002) do so without probing the placement seam again. ``mission_slug`` is the PRIMARY
    Mission directory name, the name the coordination worktree is composed from.
    """

    mission_slug: str
    mid8: str
    coordination_branch: str
    primary_dir: Path


_PATH_SOURCES = frozenset({StatusReadSource.WRITE_CHECKOUT, StatusReadSource.COORD_WORKTREE})
_REF_SOURCES = frozenset({StatusReadSource.COORD_BRANCH_REF, StatusReadSource.MISSION_BRANCH_REF})


@dataclass(frozen=True)
class StatusReadSurface:
    """One declared status source (data model §2).

    Invariants (checked on construction): exactly one of ``path`` and ``ref`` is set; ``path``
    exists whenever it is set; the path sources carry a path and the ref sources a ref;
    ``fallback_reason`` is set only for a coordination topology read from ``WRITE_CHECKOUT``.
    ``path`` is the Mission directory (``status.events.jsonl`` lives inside it).

    ``prefetched`` is the ref read the door already made to decide the source, reused by the
    read functions so a ref-sourced read costs one object-read subprocess (NFR-001). It is not
    part of the value's identity.
    """

    topology: MissionTopology
    source: StatusReadSource
    mission_dir_name: str
    path: Path | None
    repo_root: Path
    ref: str | None
    fallback_reason: str | None = None
    prefetched: RefRead | None = field(default=None, compare=False, repr=False)
    unmaterialized: UnmaterializedCoordination | None = field(default=None, compare=False, repr=False)
    """Set when the coordination worktree is not materialized; not part of the value's identity."""

    def __post_init__(self) -> None:
        if (self.path is None) == (self.ref is None):
            raise ValueError("a status read surface sets exactly one of path and ref")
        if self.path is not None and not self.path.exists():
            raise ValueError(f"status read path {self.path} does not exist")
        if self.source in _PATH_SOURCES and self.path is None:
            raise ValueError(f"{self.source} reads a path, not a ref")
        if self.source in _REF_SOURCES and self.ref is None:
            raise ValueError(f"{self.source} reads a ref, not a path")
        if self.fallback_reason is not None and not (self.source is StatusReadSource.WRITE_CHECKOUT and routes_through_coordination(self.topology)):
            raise ValueError("fallback_reason is set only for a coordination topology read from the write checkout")

    @property
    def parser_dir(self) -> Path:
        """The Mission directory the event parser anchors legacy identity lookups on."""
        return self.path if self.path is not None else self.repo_root / _KITTY_SPECS / self.mission_dir_name


@dataclass(frozen=True)
class _Decision:
    """The door's source decision, before the surface invariants are applied.

    ``legacy_path`` / ``primary_anchor`` are the path form ``resolve_status_surface_with_anchor``
    projects for its not-yet-migrated callers (WP06/WP07).
    """

    topology: MissionTopology
    source: StatusReadSource
    mission_dir_name: str
    repo_root: Path
    path: Path | None
    ref: str | None
    legacy_path: Path
    primary_anchor: Path
    fallback_reason: str | None = None
    prefetched: RefRead | None = None
    unmaterialized: UnmaterializedCoordination | None = None

    def surface(self) -> StatusReadSurface:
        return StatusReadSurface(
            topology=self.topology,
            source=self.source,
            mission_dir_name=self.mission_dir_name,
            path=self.path,
            repo_root=self.repo_root,
            ref=self.ref,
            fallback_reason=self.fallback_reason,
            prefetched=self.prefetched,
            unmaterialized=self.unmaterialized,
        )


@dataclass(frozen=True)
class _MissionFacts:
    repo_root: Path
    mission_dir_name: str
    primary_dir: Path
    meta: Mapping[str, object]
    topology: MissionTopology
    coord_branch: str | None


# ---------------------------------------------------------------------------
# Public door
# ---------------------------------------------------------------------------


def resolve_status_read(repo_root: Path, mission: str, *, owned: OwnedCheckout | None = None) -> StatusReadSurface:
    """Resolve the one declared status source of *mission* (ADR 2026-11-06-2).

    Raises:
        WorktreeRegistryUnavailable: the worktree registry cannot be read (root normalization).
        CoordinationBranchDeleted: a coordination branch was deleted without landing.
        StatusSurfaceRefUnreadable: the coordination ref cannot be read (never an empty history).
        StatusReadPathNotFound / FileNotFoundError: the Mission cannot be found.
    """
    if owned is not None and not routes_through_coordination(owned.topology):
        return StatusReadSurface(
            topology=owned.topology,
            source=StatusReadSource.WRITE_CHECKOUT,
            mission_dir_name=owned.mission_dir.name,
            path=owned.mission_dir,
            repo_root=owned.repository_root,
            ref=None,
        )
    if owned is not None:
        # An owned coordination Mission (FR-007, ADR 2026-11-06-2 Amendment 2026-11-11): its
        # Mission directory, meta.json, landed check and pre-seed fallback come from the owned
        # checkout; the coordination state is probed under the repository root, where the
        # coordination worktree is registered.
        return decide_status_read(owned.repository_root, mission, primary_dir=owned.mission_dir).surface()
    return decide_status_read(repo_root, mission).surface()


def unmaterialized_coordination_refusal(surface: StatusReadSurface) -> CoordinationWorktreeUnmaterialized | None:
    """The placement seam's refusal for a surface whose coordination worktree is not materialized.

    ``None`` for every other surface. The exception is built by its one factory
    (``CoordinationWorktreeUnmaterialized.for_mission``) from the door's own facts, so its
    message and ``next_step`` are the ones the placement seam raises for the same cell; the
    remedy keeps one composer. Built on demand: composing ``next_step`` runs a git probe.
    """
    facts = surface.unmaterialized
    if facts is None:
        return None
    from specify_cli.coordination.surface_resolver import CoordinationWorktreeUnmaterialized

    refusal: CoordinationWorktreeUnmaterialized = CoordinationWorktreeUnmaterialized.for_mission(
        repo_root=surface.repo_root,
        mission_slug=facts.mission_slug,
        mid8=facts.mid8,
        coordination_branch=facts.coordination_branch,
        primary_candidate=facts.primary_dir,
    )
    return refusal


def resolve_committed_status_read(repo_root: Path, mission: str) -> StatusReadSurface | None:
    """The committed coordination ref of *mission*, read explicitly (never the worktree file).

    For a durable-history reader (consolidation resume progress, FR-007) that must not count
    roll-backable worktree bytes. Returns a ``COORD_BRANCH_REF`` surface whatever the
    coordination worktree's state, or ``None`` when there is no committed history to read:
    no readable ``meta.json``, a topology without coordination, or a coordination ref that
    names no object (absent branch, or *repo_root* not a git repository). A ref that exists but
    cannot be read raises ``StatusSurfaceRefUnreadable`` from the read functions (FR-004).
    """
    from specify_cli.coordination.status_service import ref_names_object
    from specify_cli.coordination.surface_resolver import _coord_mid8
    from specify_cli.core.paths import load_meta_fail_closed
    from specify_cli.missions._read_path_resolver import coord_feature_dir, normalized_status_read_root

    with normalized_status_read_root(_reanchor_coordination_worktree(repo_root)) as root:
        _candidate, dir_name, primary_dir = _locate_mission(root, mission)
        meta = load_meta_fail_closed(primary_dir) if primary_dir.is_dir() else None
        if meta is None:
            return None
        facts = _facts(root, dir_name, primary_dir, meta, None)
        if not routes_through_coordination(facts.topology) or facts.coord_branch is None:
            return None
        ref = f"{_HEADS_PREFIX}{facts.coord_branch}"
        if not ref_names_object(root, ref):
            return None
        coord_dir: Path = coord_feature_dir(root, dir_name, _coord_mid8(dict(meta), dir_name, root))
        return StatusReadSurface(
            topology=facts.topology,
            source=StatusReadSource.COORD_BRANCH_REF,
            mission_dir_name=coord_dir.name,
            path=None,
            repo_root=root,
            ref=ref,
        )


def resolve_consolidated_target_read(repo_root: Path, primary_dir: Path) -> StatusReadSurface:
    """The ``CONSOLIDATED_TARGET`` surface of the Mission whose PRIMARY directory is *primary_dir*.

    The target's copy in the repository root checkout, where consolidation lands the log. For a
    reader that asks whether that copy shows a landing (#7433) when the door cannot answer
    ``CONSOLIDATED_TARGET`` itself because ``merged_at`` is missing. ``repo_root`` must already
    be the main repository root. Raises ``ValueError`` when *primary_dir* does not exist.
    """
    return _consolidated_decision(repo_root, primary_dir.name, primary_dir, None).surface()


def resolve_landing_evidence_read(repo_root: Path, mission: str) -> StatusReadSurface:
    """The surface that holds a Mission's landing evidence (#7433): the door's own decision.

    One declared exception: when the door refuses because the coordination branch is gone
    (``CoordinationBranchDeleted``), the evidence is the target's copy
    (:func:`resolve_consolidated_target_read`): consolidation removes the coordination branch
    after it lands the log on the target, so that copy is the only committed log left. Whether
    it shows a landing is the caller's question; this function only names where to look.

    Raises what :func:`resolve_status_read` raises, except ``CoordinationBranchDeleted``.
    """
    from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted

    try:
        return resolve_status_read(repo_root, mission)
    except CoordinationBranchDeleted as refused:
        return resolve_consolidated_target_read(Path(refused.repo_root), Path(refused.primary_candidate))


def decide_status_read(
    repo_root: Path,
    mission: str,
    topology: MissionTopology | None = None,
    *,
    for_write: bool = False,
    primary_dir: Path | None = None,
) -> _Decision:
    """The door's decision, shared with the legacy path projection of the surface resolver.

    ``topology`` is a caller-threaded stored topology (the legacy resolver signature);
    ``for_write`` skips the landed check and the pre-seed probe (a write never reads the
    target's copy and never falls back to the write checkout). ``primary_dir`` is the owned
    checkout's Mission directory (``OwnedCheckout.mission_dir``): when given, the Mission is not
    located under *repo_root*; that directory is its PRIMARY directory (meta.json, the landed
    check, the pre-seed fallback), while the coordination state is still probed under
    *repo_root*. The legacy projection never passes it.
    """
    from specify_cli.missions._read_path_resolver import normalized_status_read_root

    with normalized_status_read_root(_reanchor_coordination_worktree(repo_root)) as root:
        return _decide(root, mission, topology, for_write=for_write, owned_dir=primary_dir)


def _decide(root: Path, mission: str, topology: MissionTopology | None, *, for_write: bool, owned_dir: Path | None = None) -> _Decision:
    candidate, dir_name, primary_dir = _locate_mission(root, mission) if owned_dir is None else (owned_dir, owned_dir.name, owned_dir)
    if not for_write and _has_landed(primary_dir):
        return _consolidated_decision(root, dir_name, primary_dir, topology)
    meta, husk = _read_meta(root, candidate, dir_name, primary_dir, husk_allowed=owned_dir is None)
    if husk is not None:
        return _path_decision(root, dir_name, husk, StatusReadSource.COORD_WORKTREE, MissionTopology.COORD, anchor=husk)
    if meta is None:
        return _meta_unreadable_decision(root, dir_name, primary_dir, candidate)
    facts = _facts(root, dir_name, primary_dir, meta, topology)
    if not routes_through_coordination(facts.topology) or facts.coord_branch is None:
        return _write_checkout_decision(facts)
    return _coordination_decision(facts, for_write=for_write)


# ---------------------------------------------------------------------------
# Locating the Mission and its metadata
# ---------------------------------------------------------------------------


def _reanchor_coordination_worktree(repo_root: Path) -> Path:
    """Re-anchor a registered coordination worktree root to the main repository root.

    Only a root under a ``.worktrees/<name>-coord`` segment is checked against the registry, so
    every other input costs nothing here (the lane re-anchor is ``canonical_status_read_root``'s).
    """
    from specify_cli.coordination.surface_resolver import WorktreeTopology, classify_worktree_topology
    from specify_cli.core.paths import get_main_repo_root

    resolved = repo_root.resolve(strict=False)
    if not any(part.endswith("-coord") for part in resolved.parts) or ".worktrees" not in resolved.parts:
        return repo_root
    if classify_worktree_topology(resolved) is not WorktreeTopology.COORD_WORKTREE:
        return repo_root
    main_root: Path = get_main_repo_root(resolved)
    return main_root


def _locate_mission(root: Path, mission: str) -> tuple[Path, str, Path]:
    """``(candidate dir, canonical Mission dir name, PRIMARY dir)`` -- one canonicalization.

    The raw path primitives stay in the surface resolver, the read-side module the
    placement-seam bypass gate sanctions (``test_no_read_side_bypass.py``).
    """
    from specify_cli.coordination.surface_resolver import locate_status_mission

    located: tuple[Path, str, Path] = locate_status_mission(root, mission)
    return located


def _has_landed(primary_dir: Path) -> bool:
    from mission_runtime import mission_has_landed

    return mission_has_landed(primary_dir)


def _read_meta(
    root: Path,
    candidate: Path,
    dir_name: str,
    primary_dir: Path,
    *,
    husk_allowed: bool = True,
) -> tuple[Mapping[str, object] | None, Path | None]:
    """Read ``meta.json`` (candidate first, then PRIMARY); return a husk dir when it is the surface.

    A coordination-worktree candidate carrying its own ``meta.json`` is the surface unless the
    PRIMARY stored topology is coordination-less (the #2062 husk-authority rule). An owned
    checkout's Mission directory is never a husk (``husk_allowed=False``), even when that
    checkout itself sits under ``.worktrees``.
    """
    from specify_cli.coordination.surface_resolver import _husk_is_authoritative_surface
    from specify_cli.core.paths import load_meta_fail_closed

    meta: Mapping[str, object] | None = load_meta_fail_closed(candidate)
    if meta is not None and husk_allowed and ".worktrees" in candidate.parts and _husk_is_authoritative_surface(root, dir_name):
        return meta, candidate
    if meta is None:
        meta = load_meta_fail_closed(primary_dir)
    return meta, None


def _stored_or_derived(threaded: MissionTopology | None, meta: Mapping[str, object]) -> MissionTopology:
    from specify_cli.coordination.surface_resolver import _effective_surface_topology

    raw_coord = meta.get("coordination_branch")
    topology: MissionTopology = _effective_surface_topology(threaded, dict(meta), str(raw_coord) if raw_coord else None)
    return topology


def _facts(root: Path, dir_name: str, primary_dir: Path, meta: Mapping[str, object], topology: MissionTopology | None) -> _MissionFacts:
    raw_coord = meta.get("coordination_branch")
    return _MissionFacts(
        repo_root=root,
        mission_dir_name=dir_name,
        primary_dir=primary_dir,
        meta=meta,
        topology=_stored_or_derived(topology, meta),
        coord_branch=str(raw_coord) if raw_coord else None,
    )


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------


def _path_decision(
    root: Path,
    dir_name: str,
    path: Path,
    source: StatusReadSource,
    topology: MissionTopology,
    *,
    anchor: Path | None = None,
    fallback_reason: str | None = None,
) -> _Decision:
    return _Decision(
        topology=topology,
        source=source,
        mission_dir_name=dir_name,
        repo_root=root,
        path=path,
        ref=None,
        legacy_path=path / _EVENTS_FILENAME,
        primary_anchor=anchor if anchor is not None else path,
        fallback_reason=fallback_reason,
    )


def _consolidated_decision(root: Path, dir_name: str, primary_dir: Path, topology: MissionTopology | None) -> _Decision:
    """``CONSOLIDATED_TARGET``: the target's copy in the repository root checkout.

    The landed signal is read from that same ``meta.json``, so the directory exists whenever
    this source is chosen (the ADR's "target not checked out" open point cannot reach a missing
    path here).
    """
    from specify_cli.core.paths import load_meta_fail_closed

    meta = load_meta_fail_closed(primary_dir) or {}
    resolved = _stored_or_derived(topology, meta)
    return _path_decision(root, dir_name, primary_dir, StatusReadSource.CONSOLIDATED_TARGET, resolved)


def _meta_unreadable_decision(root: Path, dir_name: str, primary_dir: Path, candidate: Path) -> _Decision:
    """No readable ``meta.json`` anywhere: the existing directory, PRIMARY first, or not found."""
    if primary_dir.exists():
        return _path_decision(root, dir_name, primary_dir, StatusReadSource.WRITE_CHECKOUT, MissionTopology.SINGLE_BRANCH)
    if candidate.exists():
        in_worktree = ".worktrees" in candidate.parts
        source = StatusReadSource.COORD_WORKTREE if in_worktree else StatusReadSource.WRITE_CHECKOUT
        topology = MissionTopology.COORD if in_worktree else MissionTopology.SINGLE_BRANCH
        return _path_decision(root, dir_name, candidate, source, topology)
    raise FileNotFoundError(f"meta.json not found for mission {dir_name!r} at {candidate}")


def _write_checkout_decision(facts: _MissionFacts) -> _Decision:
    """``WRITE_CHECKOUT``: the root checkout, or (FR-061) the checkout holding the topic branch."""
    decision = _path_decision(
        facts.repo_root,
        facts.mission_dir_name,
        facts.primary_dir,
        StatusReadSource.WRITE_CHECKOUT,
        facts.topology,
    )
    topic = _default_topic_branch(facts.meta)
    if topic is None:
        return decision
    held_dir = _topic_holder_mission_dir(facts.repo_root, topic, facts.mission_dir_name)
    if held_dir is not None:
        # The PRIMARY anchor is the topic holder too (WP05 obligation N1): a status write anchored
        # on it lands where this decision reads.
        return _path_decision(facts.repo_root, facts.mission_dir_name, held_dir, StatusReadSource.WRITE_CHECKOUT, facts.topology)
    return _Decision(
        topology=facts.topology,
        source=StatusReadSource.MISSION_BRANCH_REF,
        mission_dir_name=facts.mission_dir_name,
        repo_root=facts.repo_root,
        path=None,
        ref=f"{_HEADS_PREFIX}{topic}",
        legacy_path=facts.primary_dir / _EVENTS_FILENAME,
        primary_anchor=facts.primary_dir,
    )


def _coordination_decision(facts: _MissionFacts, *, for_write: bool) -> _Decision:
    """``coord`` / ``lanes_with_coord``: worktree file, committed branch, or declared pre-seed fallback."""
    from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted, _coord_mid8
    from specify_cli.missions._read_path_resolver import CoordState, coord_feature_dir, probe_coord_state

    assert facts.coord_branch is not None  # guarded by the caller
    mid8 = _coord_mid8(dict(facts.meta), facts.mission_dir_name, facts.repo_root)
    coord_dir: Path = coord_feature_dir(facts.repo_root, facts.mission_dir_name, mid8)
    state = probe_coord_state(facts.repo_root, facts.mission_dir_name, mid8, coordination_branch=facts.coord_branch)
    if state is CoordState.DELETED:
        raise CoordinationBranchDeleted.for_mission(
            repo_root=facts.repo_root,
            mission_slug=facts.mission_dir_name,
            mid8=mid8,
            coordination_branch=facts.coord_branch,
            primary_candidate=facts.primary_dir,
        )
    if state is CoordState.MATERIALIZED:
        return _path_decision(facts.repo_root, coord_dir.name, coord_dir, StatusReadSource.COORD_WORKTREE, facts.topology, anchor=facts.primary_dir)
    unmaterialized = None
    if state is CoordState.UNMATERIALIZED:
        unmaterialized = UnmaterializedCoordination(
            mission_slug=facts.mission_dir_name,
            mid8=mid8,
            coordination_branch=facts.coord_branch,
            primary_dir=facts.primary_dir,
        )
    decision = _coord_ref_decision(facts, coord_dir, for_write=for_write, worktree_present=state is CoordState.EMPTY)
    return replace(decision, unmaterialized=unmaterialized)


def _coord_ref_decision(facts: _MissionFacts, coord_dir: Path, *, for_write: bool, worktree_present: bool) -> _Decision:
    """Empty or unmaterialized: read the committed branch unless it holds no log yet (pre-seed).

    The legacy path projection of the pre-seed window keeps the path it named before the door
    (WP05): the repository root checkout for an EMPTY worktree, the composed coordination path
    for an unmaterialized one, so path-classifying callers (e.g. the WP status backfill's
    live-coordination refusal) keep their answer until WP06/WP07 move them onto the door.
    """
    from specify_cli.coordination.status_service import read_status_ref

    assert facts.coord_branch is not None
    ref = f"{_HEADS_PREFIX}{facts.coord_branch}"
    prefetched = None
    if not for_write:
        prefetched = read_status_ref(facts.repo_root, ref, _ref_events_path(coord_dir.name))
        if prefetched.absent and facts.primary_dir.exists():
            reason = PRE_SEED_FALLBACK_REASON.format(branch=facts.coord_branch, events=_EVENTS_FILENAME)
            decision = _path_decision(
                facts.repo_root,
                facts.mission_dir_name,
                facts.primary_dir,
                StatusReadSource.WRITE_CHECKOUT,
                facts.topology,
                fallback_reason=reason,
            )
            if worktree_present:
                return decision
            return replace(decision, legacy_path=coord_dir / _EVENTS_FILENAME)
    return _Decision(
        topology=facts.topology,
        source=StatusReadSource.COORD_BRANCH_REF,
        mission_dir_name=coord_dir.name,
        repo_root=facts.repo_root,
        path=None,
        ref=ref,
        legacy_path=coord_dir / _EVENTS_FILENAME,
        primary_anchor=facts.primary_dir,
        prefetched=prefetched,
    )


def _ref_events_path(mission_dir_name: str) -> str:
    return f"{_KITTY_SPECS}/{mission_dir_name}/{_EVENTS_FILENAME}"


# ---------------------------------------------------------------------------
# FR-061: the PRIMARY partition of a ``topology_source: default`` Mission
# ---------------------------------------------------------------------------


def _default_topic_branch(meta: Mapping[str, object]) -> str | None:
    """The topic branch of a ``topology_source: default`` Mission, or ``None`` for every other Mission."""
    if meta.get("topology_source") != _TOPOLOGY_SOURCE_DEFAULT:
        return None
    branch = meta.get("mission_branch")
    return str(branch) if isinstance(branch, str) and branch.strip() else None


def _checkout_holding_branch(repo_root: Path, branch: str) -> Path | None:
    """The working tree that has *branch* checked out (git allows at most one), or ``None``."""
    result = subprocess.run(
        ["git", "-C", str(repo_root), "worktree", "list", "--porcelain"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return _holder_from_porcelain(result.stdout, f"{_HEADS_PREFIX}{branch}")


def _holder_from_porcelain(porcelain: str, full_ref: str) -> Path | None:
    current: Path | None = None
    for line in porcelain.splitlines():
        if line.startswith("worktree "):
            current = Path(line[len("worktree ") :])
        elif line == f"branch {full_ref}" and current is not None:
            return current
    return None


def _topic_holder_mission_dir(repo_root: Path, topic: str, mission_dir_name: str) -> Path | None:
    """The Mission directory in the checkout that holds *topic*, or ``None`` when there is none.

    ``None`` -- the caller then reads the committed topic branch (``MISSION_BRANCH_REF``) and
    never the repository root checkout's copy -- when:

    * no checkout holds the topic branch;
    * the holder is a registered lane worktree (ADR 2026-11-06-2: a status read never comes
      from a lane worktree; review cycle 1, N2);
    * the holder carries no Mission directory (review cycle 1, N3: no quiet fallback to the
      root's copy).
    """
    holder = non_lane_checkout_holding_branch(repo_root, topic)
    if holder is None:
        return None
    held_dir = holder / _KITTY_SPECS / mission_dir_name
    return held_dir if held_dir.is_dir() else None


def checkout_holding_branch(repo_root: Path, branch: str) -> Path | None:
    """Public face of the one "which checkout holds *branch*" probe (FR-061)."""
    return _checkout_holding_branch(repo_root, branch)


def non_lane_checkout_holding_branch(repo_root: Path, branch: str) -> Path | None:
    """The checkout holding *branch*, or ``None`` when none does or a registered lane worktree does (FR-061, N2)."""
    from specify_cli.coordination.surface_resolver import WorktreeTopology, classify_worktree_topology

    holder = _checkout_holding_branch(repo_root, branch)
    if holder is None or classify_worktree_topology(holder, repo_root=repo_root) is WorktreeTopology.LANE_WORKTREE:
        return None
    return holder


def topic_holder_mission_dir(repo_root: Path, topic: str, mission_dir_name: str) -> Path | None:
    """Public face of the topic-holder lookup the planning-read resolver shares (FR-061)."""
    return _topic_holder_mission_dir(repo_root, topic, mission_dir_name)


def resolve_primary_partition_dir(repo_root: Path, mission: str) -> Path | None:
    """The PRIMARY-partition Mission directory of a ``topology_source: default`` Mission (FR-061).

    Until the Mission lands, its PRIMARY partition lives on its topic branch
    (``meta.mission_branch``): the directory in the checkout that holds that branch. Returns
    ``None`` -- the caller keeps today's (target) placement -- for an explicit-topology or
    legacy Mission, a landed Mission, or a default Mission whose topic branch no checkout holds,
    a lane worktree holds, or whose holder carries no Mission directory (there is no directory
    to report; status reads take ``MISSION_BRANCH_REF``).
    """
    from specify_cli.core.paths import load_meta_fail_closed
    from specify_cli.missions._read_path_resolver import normalized_status_read_root

    with normalized_status_read_root(repo_root) as root:
        _candidate, dir_name, primary_dir = _locate_mission(root, mission)
        meta = load_meta_fail_closed(primary_dir) if primary_dir.is_dir() else None
        topic = _default_topic_branch(meta or {})
        if topic is None or _has_landed(primary_dir):
            return None
        return _topic_holder_mission_dir(root, topic, dir_name)


# ---------------------------------------------------------------------------
# Read functions (the only consumers of a surface)
# ---------------------------------------------------------------------------


def _ref_text(surface: StatusReadSurface) -> str | None:
    """The log text at the surface's ref, or ``None`` when the file is absent there."""
    from specify_cli.coordination.status_service import read_status_ref

    assert surface.ref is not None
    result = surface.prefetched
    if result is None:
        result = read_status_ref(surface.repo_root, surface.ref, _ref_events_path(surface.mission_dir_name))
    return None if result.data is None else result.data.decode("utf-8", errors="replace")


def read_status_text(surface: StatusReadSurface) -> str | None:
    """The raw log text at the surface's declared source, or ``None`` when there is no log.

    For readers that need every line of ``status.events.jsonl``, not only lane transitions and
    annotations (e.g. the retrospective gate's ``retrospective.*`` events). Read only; a ref read
    reuses the door's prefetched read (NFR-001) and an unreadable ref raises
    ``StatusSurfaceRefUnreadable`` (never an empty history).
    """
    if surface.path is None:
        return _ref_text(surface)
    events_path = surface.path / _EVENTS_FILENAME
    return events_path.read_text(encoding="utf-8") if events_path.is_file() else None


def read_status_stream(surface: StatusReadSurface) -> EventStream:
    """Transitions and annotations from the surface's declared source (read only)."""
    from specify_cli.status import EventStream, read_event_stream, read_event_stream_from_text

    if surface.path is not None:
        stream: EventStream = read_event_stream(surface.path)
        return stream
    text = _ref_text(surface)
    if text is None:
        return EventStream()
    parsed: EventStream = read_event_stream_from_text(surface.parser_dir, text)
    return parsed


def read_status_events(surface: StatusReadSurface) -> list[StatusEvent]:
    """Lane transitions from the surface's declared source (read only)."""
    return list(read_status_stream(surface).transitions)


def ref_source_remedy(surface: StatusReadSurface, mission_slug: str) -> str:
    """How an operator gives a ref-sourced status a checkout, for a command that needs a file.

    ``COORD_BRANCH_REF``: ``spec-kitty materialize`` materializes the coordination worktree
    (it adds an absent one and restores an empty one from the branch tip), after which the door
    reads ``COORD_WORKTREE``. ``MISSION_BRANCH_REF``: no checkout holds the Mission topic
    branch, so the operator checks it out. A path source needs no remedy (``ValueError``).
    """
    if surface.ref is None:
        raise ValueError(f"{surface.source} reads a path; it needs no checkout remedy")
    if surface.source is StatusReadSource.MISSION_BRANCH_REF:
        branch = surface.ref.removeprefix(_HEADS_PREFIX)
        return f"Check out the Mission branch with 'git switch {branch}' (or 'git worktree add <path> {branch}'), then re-run."
    return f"Materialize the coordination worktree with 'spec-kitty materialize --mission {mission_slug}', then re-run."


def materialize_status(surface: StatusReadSurface) -> StatusSnapshot:
    """The reduced snapshot of the surface's log (transitions and annotations), never written.

    Read only: writers use the write seam, and the on-disk ``status.json`` projection stays the
    write seam's (``status.reducer.materialize``).
    """
    from specify_cli.status import reduce

    stream = read_status_stream(surface)
    reduced: StatusSnapshot = reduce(stream.transitions, stream.annotations)
    return reduced
