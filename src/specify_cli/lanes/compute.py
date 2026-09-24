"""Lane computation algorithm.

Groups work packages into execution lanes using a union-find structure.
Two WPs are placed in the same lane when:

1. They have overlapping owned_files globs (write-scope conflict).
2. They share predicted surface tags and ownership is not provably disjoint.

Dependency edges do not collapse lanes by themselves. They are preserved as
lane-level dependencies so disjoint upstream workstreams can run in parallel and
fan-in WPs become the synchronization point.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import ClassVar

from specify_cli.core.dependency_graph import topological_sort
from kernel.clock import now_utc_iso
from specify_cli.lanes.branch_naming import mission_branch_name
from specify_cli.lanes.models import CollapseEvent, CollapseReport, ExecutionLane, LanesManifest
from specify_cli.ownership.models import WorkProductKind, OwnershipManifest
from specify_cli.ownership.validation import _globs_overlap


# Canonical lane-id for all planning-artifact WPs.
# Planning-artifact WPs are first-class lane-owned entities; they share one
# canonical lane that resolves to the main repository checkout (never a worktree).
PLANNING_LANE_ID = "lane-planning"


def is_planning_lane(lane: object) -> bool:
    """Return True when *lane* is the canonical planning-artifact lane.

    This is the single seam where "what counts as a planning lane" is decided.
    Today the backing is the static ``PLANNING_LANE_ID`` constant; that constant
    is intentionally an internal implementation detail of this predicate. The
    classification is expected to become charter / mission-type-derived and
    surfaced via the shared context objects (domain epic #1666); when that lands
    only the body of this predicate (and :func:`is_planning_artifact_only`) needs
    to change — call sites must keep asking the lane/manifest semantic question
    rather than comparing against the constant or a string literal directly.

    # TODO(#1666): when planning-ness becomes charter/mission-type-derived, this
    # predicate's BACKING (and possibly its signature → context-aware) changes
    # here; callers must keep asking the semantic question via this seam.
    """
    return getattr(lane, "lane_id", None) == PLANNING_LANE_ID


def is_planning_artifact_only(lanes_manifest: object) -> bool:
    """Return True when every lane in *lanes_manifest* is a planning lane.

    A planning-artifact-only mission has no code lanes; its closeout writes
    directly to the target branch without a mission branch. See
    :func:`is_planning_lane` for the forward-compatibility note on the backing
    of this classification (#1666).
    """
    lanes = list(getattr(lanes_manifest, "lanes", None) or [])
    return bool(lanes) and all(is_planning_lane(lane) for lane in lanes)


class LaneComputationError(Exception):
    """Raised when lane computation cannot produce a valid lane assignment.

    This is a hard failure — no lanes.json is written when this is raised.
    """


@dataclass(frozen=True, slots=True)
class CycleLane:
    """Immutable work-package membership for one lane in a detected cycle."""

    lane_id: str
    wp_ids: tuple[str, ...]


class LaneDependencyCycleError(LaneComputationError):
    """Raised when the final execution-lane dependency graph is cyclic."""

    error_code: ClassVar[str] = "LANE_DEPENDENCY_CYCLE"

    def __init__(
        self,
        cycle_path: tuple[str, ...],
        cycle_lanes: tuple[CycleLane, ...],
    ) -> None:
        self.cycle_path = cycle_path
        self.cycle_lanes = cycle_lanes
        super().__init__("Execution-lane dependency cycle detected: " + " -> ".join(cycle_path))


# Surface taxonomy for conflict detection.
# If two WPs predict the same surface, they are presumed to overlap.
SURFACE_TAXONOMY: tuple[str, ...] = (
    "dashboard",
    "workspace",
    "app-shell",
    "legacy-cleanup",
    "tests",
    "tracker-integration",
    "artifact-rendering",
    "api",
)

# Keywords that map to surface tags (case-insensitive substring match).
_SURFACE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "dashboard": ("dashboard", "landing page", "landing-page"),
    "workspace": ("workspace", "mission workspace"),
    "app-shell": ("app shell", "app-shell", "navigation", "sidebar", "layout"),
    "legacy-cleanup": ("legacy", "cleanup", "deprecat", "remov"),
    "tests": ("test suite", "test infrastructure", "e2e test", "integration test"),
    "tracker-integration": ("tracker", "saas", "sync"),
    "artifact-rendering": ("artifact", "render", "template"),
    "api": ("api", "endpoint", "route", "view"),
}


# ---------------------------------------------------------------------------
# Union-Find
# ---------------------------------------------------------------------------


class _UnionFind:
    """Disjoint-set data structure with union-by-rank and path compression."""

    def __init__(self, elements: list[str]) -> None:
        self._parent: dict[str, str] = {e: e for e in elements}
        self._rank: dict[str, int] = dict.fromkeys(elements, 0)

    def find(self, x: str) -> str:
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self._rank[ra] < self._rank[rb]:
            ra, rb = rb, ra
        self._parent[rb] = ra
        if self._rank[ra] == self._rank[rb]:
            self._rank[ra] += 1

    def groups(self) -> dict[str, list[str]]:
        """Return mapping of root → list of members."""
        result: dict[str, list[str]] = {}
        for element in self._parent:
            root = self.find(element)
            result.setdefault(root, []).append(element)
        return result


# ---------------------------------------------------------------------------
# Surface inference
# ---------------------------------------------------------------------------


def infer_surfaces(wp_body: str) -> list[str]:
    """Infer surface tags from WP body text using keyword matching.

    Args:
        wp_body: The markdown body of a work package.

    Returns:
        List of matched surface taxonomy tags.
    """
    body_lower = wp_body.lower()
    matched: list[str] = []
    for surface, keywords in _SURFACE_KEYWORDS.items():
        if any(kw in body_lower for kw in keywords):
            matched.append(surface)
    return matched


# ---------------------------------------------------------------------------
# Collapse report helpers
# ---------------------------------------------------------------------------


def _describe_overlap(
    manifest_a: OwnershipManifest,
    manifest_b: OwnershipManifest,
) -> str:
    """Return a human-readable description of which globs overlap between two manifests."""
    overlapping: list[str] = []
    for glob_a in manifest_a.owned_files:
        for glob_b in manifest_b.owned_files:
            if _globs_overlap(glob_a, glob_b):
                overlapping.append(f"{glob_a!r} vs {glob_b!r}")
    if overlapping:
        return "overlapping globs: " + ", ".join(overlapping)
    return "write-scope overlap"


def _dependency_relationship_evidence(
    wp_a: str,
    wp_b: str,
    dependency_graph: dict[str, list[str]],
) -> str | None:
    """Return direct-dependency evidence for a pair when present."""
    if wp_b in dependency_graph.get(wp_a, []):
        return f"{wp_a} depends on {wp_b}"
    if wp_a in dependency_graph.get(wp_b, []):
        return f"{wp_b} depends on {wp_a}"
    return None


def _are_disjoint(
    manifest_a: OwnershipManifest,
    manifest_b: OwnershipManifest,
) -> bool:
    """Return True if no glob from manifest_a overlaps with any glob from manifest_b."""
    for glob_a in manifest_a.owned_files:
        for glob_b in manifest_b.owned_files:
            if _globs_overlap(glob_a, glob_b):
                return False
    return True


def _transitive_deps(
    dependency_graph: dict[str, list[str]],
) -> dict[str, set[str]]:
    """Build the transitive closure of the dependency graph.

    Returns a mapping of WP ID → set of all WPs it transitively depends on.
    """
    cache: dict[str, set[str]] = {}
    visiting: set[str] = set()

    def _reach(wp_id: str) -> set[str]:
        if wp_id in cache:
            return cache[wp_id]
        if wp_id in visiting:
            return set()
        visiting.add(wp_id)
        direct = set(dependency_graph.get(wp_id, []))
        result: set[str] = set(direct)
        try:
            for dep in direct:
                result.update(_reach(dep))
        finally:
            visiting.discard(wp_id)
        cache[wp_id] = result
        return result

    for wp in dependency_graph:
        _reach(wp)
    return cache


def _count_independent_collapses(
    events: list[CollapseEvent],
    dependency_graph: dict[str, list[str]],
) -> int:
    """Count events where wp_a and wp_b have no direct or transitive dependency relationship."""
    if not events:
        return 0
    transitive = _transitive_deps(dependency_graph)
    count = 0
    for event in events:
        if event.rule == "dependency":
            continue  # By definition not independent
        a, b = event.wp_a, event.wp_b
        if b not in transitive.get(a, set()) and a not in transitive.get(b, set()):
            count += 1
    return count


# ---------------------------------------------------------------------------
# Overlap pair detection
# ---------------------------------------------------------------------------


def find_overlap_pairs(
    manifests: dict[str, OwnershipManifest],
) -> list[tuple[str, str]]:
    """Return pairs of WP IDs whose owned_files globs overlap.

    Args:
        manifests: Mapping of WP ID to OwnershipManifest.

    Returns:
        List of (wp_a, wp_b) tuples with overlapping write scopes.
    """
    pairs: list[tuple[str, str]] = []
    wp_ids = sorted(manifests.keys())
    for wp_a, wp_b in combinations(wp_ids, 2):
        for glob_a in manifests[wp_a].owned_files:
            for glob_b in manifests[wp_b].owned_files:
                if _globs_overlap(glob_a, glob_b):
                    pairs.append((wp_a, wp_b))
                    break
            else:
                continue
            break
    return pairs


def _find_lane_dependency_cycle(
    lane_deps: dict[str, set[str]],
) -> tuple[str, ...] | None:
    """Return the first deterministic closed directed cycle, if one exists.

    Roots and dependencies are visited lexically. The iterative traversal avoids
    imposing Python's recursion limit on the number of execution lanes.
    """
    nodes = sorted(set(lane_deps).union(*(set(deps) for deps in lane_deps.values())))
    state: dict[str, int] = dict.fromkeys(nodes, 0)

    for root in nodes:
        if state[root] != 0:
            continue

        active_path: list[str] = [root]
        active_index: dict[str, int] = {root: 0}
        traversal: list[tuple[str, tuple[str, ...], int]] = [(root, tuple(sorted(lane_deps.get(root, set()))), 0)]
        state[root] = 1

        while traversal:
            node, dependencies, next_index = traversal[-1]
            if next_index >= len(dependencies):
                traversal.pop()
                active_path.pop()
                active_index.pop(node)
                state[node] = 2
                continue

            dependency = dependencies[next_index]
            traversal[-1] = (node, dependencies, next_index + 1)
            dependency_state = state[dependency]
            if dependency_state == 0:
                state[dependency] = 1
                active_index[dependency] = len(active_path)
                active_path.append(dependency)
                traversal.append(
                    (
                        dependency,
                        tuple(sorted(lane_deps.get(dependency, set()))),
                        0,
                    )
                )
                continue
            if dependency_state == 1:
                cycle = active_path[active_index[dependency] :] + [dependency]
                unique_cycle = cycle[:-1]
                smallest_index = unique_cycle.index(min(unique_cycle))
                normalized = unique_cycle[smallest_index:] + unique_cycle[:smallest_index]
                return tuple(normalized + [normalized[0]])

    return None


# ---------------------------------------------------------------------------
# Stable lane identity (C-4 / FR-010)
# ---------------------------------------------------------------------------


def _next_free_lane_id(used: set[str]) -> str:
    """Return the lowest ``lane-<letter>`` positional id not already claimed.

    With no read-back (``used`` filling in group order) this reproduces the
    historical ``lane-a``, ``lane-b``, … minting byte-for-byte; when some ids
    are already bound by read-back it skips them so a freshly minted lane never
    collides with a bound one.
    """
    letter = ord("a")
    while True:
        candidate = f"lane-{chr(letter)}"
        if candidate not in used:
            return candidate
        letter += 1


def _assign_stable_lane_ids(
    sorted_groups: list[list[str]],
    previous_lanes: LanesManifest | None,
) -> list[str]:
    """Assign a ``lane_id`` per computed group, reading back bound ids (PP-F5).

    Identity is bound to a lane's git branch at creation. On a re-finalize the
    id is **read back** from ``previous_lanes`` — never re-minted positionally —
    so removing a WP and re-finalizing cannot re-letter a surviving lane onto a
    different WP's branch (#4945). A group inherits the previously persisted lane
    whose WP membership it overlaps most (deterministic; ties broken by lane id);
    each prior id is claimed at most once, so read-back never overwrites or
    duplicates a bound id. Genuinely new lanes — and every lane on a first
    finalize (``previous_lanes is None``) — mint the next free positional id.
    """
    existing: dict[str, set[str]] = {}
    if previous_lanes is not None:
        for lane in previous_lanes.lanes:
            # The planning lane owns a fixed, non-positional id — never a
            # candidate for a code lane's read-back.
            if is_planning_lane(lane):
                continue
            existing[lane.lane_id] = set(lane.wp_ids)

    assigned: dict[int, str] = {}
    used: set[str] = set()

    # Pass 1: read back a bound id for each group by best membership overlap.
    for index, group in enumerate(sorted_groups):
        group_set = set(group)
        best_lane_id: str | None = None
        best_overlap = 0
        for lane_id, members in sorted(existing.items()):
            if lane_id in used:
                continue
            overlap = len(group_set & members)
            if overlap > best_overlap:
                best_overlap = overlap
                best_lane_id = lane_id
        if best_lane_id is not None:
            assigned[index] = best_lane_id
            used.add(best_lane_id)

    # Pass 2: mint the next free positional id for every unbound group.
    for index in range(len(sorted_groups)):
        if index not in assigned:
            fresh = _next_free_lane_id(used)
            assigned[index] = fresh
            used.add(fresh)

    return [assigned[index] for index in range(len(sorted_groups))]


# ---------------------------------------------------------------------------
# Main computation
# ---------------------------------------------------------------------------


def compute_lanes(
    dependency_graph: dict[str, list[str]],
    ownership_manifests: dict[str, OwnershipManifest],
    mission_slug: str,
    target_branch: str = "main",
    wp_bodies: dict[str, str] | None = None,
    mission_id: str | None = None,
    previous_lanes: LanesManifest | None = None,
) -> LanesManifest:
    """Compute execution lanes from dependency graph and ownership manifests.

    Algorithm:
    1. Separate planning_artifact WPs from code WPs.
    2. Union code WPs with overlapping owned_files (rule 1).
    3. Union code WPs sharing predicted surfaces when ownership is not
       provably disjoint (rule 2).
    4. Preserve dependency edges as lane-level dependencies.
    5. Build ExecutionLane per disjoint set, sorted internally by topo order.
    6. Compute lane-level dependencies and parallel groups.
    7. Collect all planning_artifact WPs into a single ``lane-planning`` lane.

    Planning-artifact WPs are first-class lane-owned entities assigned to the
    canonical ``PLANNING_LANE_ID`` (``"lane-planning"``).  That lane resolves to
    the main repository checkout, never a ``.worktrees/`` directory.

    Args:
        dependency_graph: WP ID → list of dependency WP IDs.
        ownership_manifests: WP ID → OwnershipManifest.
        mission_slug: Mission identifier.
        target_branch: Branch the mission merges into.
        wp_bodies: Optional WP ID → body text for surface inference.
        previous_lanes: The ``lanes.json`` manifest from a prior finalize, when
            one exists. Lane identity is bound to its git branch at creation and
            **read back** here on every subsequent finalize (C-4 / FR-010,
            PP-F5) — a surviving lane keeps its ``lane_id`` across a WP-removal
            re-finalize instead of being re-lettered positionally onto a
            different WP's branch (#4945). ``None`` (a first finalize) mints
            positional ids exactly as before.

    Returns:
        An acyclic LanesManifest ready for persistence.

    Raises:
        LaneDependencyCycleError: If the complete post-collapse lane graph is cyclic.
    """
    resolved_mission_id = mission_id  # WP04/FR-004: None for legacy; never substitute slug

    # Collect all WP IDs from the graph.
    all_wp_ids = sorted(dependency_graph.keys())
    if not all_wp_ids:
        return _empty_manifest(mission_slug, target_branch, resolved_mission_id, planning_artifact_wps=[])

    # Separate planning_artifact WPs from code WPs.
    # Both sets receive lane assignments:
    # - code WPs → lane-a, lane-b, … (computed below via union-find)
    # - planning_artifact WPs → single canonical PLANNING_LANE_ID lane
    code_wp_ids: list[str] = []
    planning_artifact_wp_ids: list[str] = []
    for wp_id in all_wp_ids:
        manifest = ownership_manifests.get(wp_id)
        if manifest and manifest.execution_mode == WorkProductKind.PLANNING_ARTIFACT:
            planning_artifact_wp_ids.append(wp_id)
            continue
        if not manifest:
            raise LaneComputationError(
                f"Executable WP '{wp_id}' has no ownership manifest. "
                f"Ensure owned_files and execution_mode are set in WP frontmatter, "
                f"or run finalize-tasks to infer them."
            )
        code_wp_ids.append(wp_id)

    if not code_wp_ids and not planning_artifact_wp_ids:
        return _empty_manifest(mission_slug, target_branch, resolved_mission_id, planning_artifact_wps=[])

    if not code_wp_ids:
        # Only planning-artifact WPs — build the lane-planning lane and return.
        planning_lane = _build_planning_lane(planning_artifact_wp_ids, ownership_manifests)
        return LanesManifest(
            version=1,
            mission_slug=mission_slug,
            mission_id=resolved_mission_id,
            mission_branch=mission_branch_name(mission_slug, mission_id=mission_id),
            target_branch=target_branch,
            lanes=[planning_lane],
            computed_at=now_utc_iso(),
            computed_from="dependency_graph+ownership",
            planning_artifact_wps=list(planning_lane.wp_ids),
        )

    # Build union-find over code WPs.
    uf = _UnionFind(code_wp_ids)
    collapse_events: list[CollapseEvent] = []

    # Rule 1: Overlapping write scopes → same lane.
    code_manifests = {wp: ownership_manifests[wp] for wp in code_wp_ids if wp in ownership_manifests}
    for wp_a, wp_b in find_overlap_pairs(code_manifests):
        if uf.find(wp_a) != uf.find(wp_b):
            overlap = _describe_overlap(code_manifests[wp_a], code_manifests[wp_b])
            dep_evidence = _dependency_relationship_evidence(wp_a, wp_b, dependency_graph)
            evidence = f"{overlap}; {dep_evidence}" if dep_evidence else overlap
            collapse_events.append(
                CollapseEvent(
                    wp_a=wp_a,
                    wp_b=wp_b,
                    rule="write_scope_overlap",
                    evidence=evidence,
                )
            )
        uf.union(wp_a, wp_b)

    # Rule 2: Shared predicted surfaces → same lane.
    # Only merges WPs when ownership is NOT provably disjoint. If both WPs have
    # manifests and their owned_files are disjoint, skip the merge — a shared
    # surface keyword is not enough evidence of a real conflict.
    if wp_bodies:
        wp_surfaces: dict[str, list[str]] = {}
        for wp_id in code_wp_ids:
            body = wp_bodies.get(wp_id, "")
            wp_surfaces[wp_id] = infer_surfaces(body)

        for wp_a, wp_b in combinations(code_wp_ids, 2):
            surfaces_a = set(wp_surfaces.get(wp_a, []))
            surfaces_b = set(wp_surfaces.get(wp_b, []))
            if surfaces_a & surfaces_b:
                # Only merge if ownership is NOT provably disjoint.
                # Absence of a manifest means we cannot prove disjointness → merge.
                ma = code_manifests.get(wp_a)
                mb = code_manifests.get(wp_b)
                if ma and mb and _are_disjoint(ma, mb):
                    continue  # Disjoint ownership — surface match is not enough
                shared = sorted(surfaces_a & surfaces_b)
                if uf.find(wp_a) != uf.find(wp_b):
                    collapse_events.append(
                        CollapseEvent(
                            wp_a=wp_a,
                            wp_b=wp_b,
                            rule="surface_heuristic",
                            evidence=f"shared surfaces {shared} with non-disjoint ownership",
                        )
                    )
                uf.union(wp_a, wp_b)

    # Build lane groups from union-find.
    raw_groups = uf.groups()

    # T010: Assert every executable WP appears in exactly one lane group.
    assigned_wps: set[str] = set()
    for group_members in raw_groups.values():
        assigned_wps.update(group_members)

    missing_wps = set(code_wp_ids) - assigned_wps
    if missing_wps:
        raise LaneComputationError(
            f"Executable WPs not assigned to any lane: {sorted(missing_wps)}. "
            f"Verify that these WPs appear in the dependency_graph and have "
            f"ownership manifests in frontmatter."
        )

    # Order WPs within each lane by topological sort.
    lanes: list[ExecutionLane] = []

    # Sort groups deterministically by lowest WP ID in each group.
    sorted_groups = sorted(raw_groups.values(), key=lambda g: min(g))

    # C-4 / FR-010 (PP-F5): bind each lane's id to its branch by reading back a
    # previously minted id; only genuinely new lanes mint a fresh positional id.
    lane_ids = _assign_stable_lane_ids(sorted_groups, previous_lanes)

    # Build a sub-graph for each group to topologically sort within it.
    for group_index, group_wps in enumerate(sorted_groups):
        group_set = set(group_wps)
        sub_graph = {wp: [d for d in dependency_graph.get(wp, []) if d in group_set] for wp in group_wps}
        ordered_wps = topological_sort(sub_graph)

        # Collect write scopes and surfaces for the lane.
        lane_write_scope: set[str] = set()
        lane_surfaces: set[str] = set()
        for wp_id in ordered_wps:
            m = ownership_manifests.get(wp_id)
            if m:
                lane_write_scope.update(m.owned_files)
            if wp_bodies:
                lane_surfaces.update(infer_surfaces(wp_bodies.get(wp_id, "")))

        lane_id = lane_ids[group_index]

        lanes.append(
            ExecutionLane(
                lane_id=lane_id,
                wp_ids=tuple(ordered_wps),
                write_scope=tuple(sorted(lane_write_scope)),
                predicted_surfaces=tuple(sorted(lane_surfaces)),
                depends_on_lanes=(),  # Filled in below.
                parallel_group=0,  # Filled in below.
            )
        )

    # Compute lane-level dependencies.
    # Lane B depends on lane A if any WP in B depends on any WP in A
    # (and they are in different lanes).
    #
    # P2.7 fix: planning-artifact WPs participate in this calculation.
    # A code WP that depends on a planning-artifact WP must have a lane
    # edge to PLANNING_LANE_ID, and a planning-artifact WP that depends
    # on a code WP must put PLANNING_LANE_ID downstream of that code
    # lane. Without this, the lane planner happily fan-outs lanes that
    # should be sequential, and the merge order silently violates the
    # declared dependency graph.
    wp_to_lane: dict[str, str] = {}
    for lane in lanes:
        for wp_id in lane.wp_ids:
            wp_to_lane[wp_id] = lane.lane_id
    # Map every planning-artifact WP to the canonical lane id so
    # cross-mode deps (code -> planning, planning -> code) resolve.
    for planning_wp_id in planning_artifact_wp_ids:
        wp_to_lane[planning_wp_id] = PLANNING_LANE_ID

    # Seed lane_deps for every lane we know about — including
    # PLANNING_LANE_ID when the mission has any planning-artifact WPs.
    lane_deps: dict[str, set[str]] = {lane.lane_id: set() for lane in lanes}
    if planning_artifact_wp_ids:
        lane_deps[PLANNING_LANE_ID] = set()

    # Iterate every WP (code AND planning) so cross-mode dependency
    # edges are captured.
    for wp_id in code_wp_ids + planning_artifact_wp_ids:
        my_lane = wp_to_lane.get(wp_id)
        if not my_lane:
            continue
        for dep in dependency_graph.get(wp_id, []):
            dep_lane = wp_to_lane.get(dep)
            if dep_lane and dep_lane != my_lane:
                lane_deps[my_lane].add(dep_lane)

    cycle_path = _find_lane_dependency_cycle(lane_deps)
    if cycle_path is not None:
        lane_members: dict[str, list[str]] = {lane_id: [] for lane_id in lane_deps}
        for wp_id, lane_id in wp_to_lane.items():
            lane_members[lane_id].append(wp_id)
        cycle_lanes = tuple(CycleLane(lane_id=lane_id, wp_ids=tuple(sorted(lane_members[lane_id]))) for lane_id in cycle_path[:-1])
        raise LaneDependencyCycleError(cycle_path, cycle_lanes)

    # Assign parallel groups via topological sort of lane DAG.
    # Lanes at the same depth in the DAG can run in parallel.
    # The planning lane participates in the depth calculation when
    # the mission has any planning-artifact WPs so its parallel_group
    # honours upstream code-lane dependencies (P2.7).
    depth_input_lanes = list(lanes)
    if planning_artifact_wp_ids:
        # Synthesise a placeholder ExecutionLane for the depth calc.
        # The real planning lane is constructed below; this stand-in
        # exists only so PLANNING_LANE_ID appears in the topo input.
        depth_input_lanes.append(
            ExecutionLane(
                lane_id=PLANNING_LANE_ID,
                wp_ids=tuple(sorted(planning_artifact_wp_ids)),
                write_scope=(),
                predicted_surfaces=("planning",),
                depends_on_lanes=tuple(sorted(lane_deps[PLANNING_LANE_ID])),
                parallel_group=0,
            )
        )
    lane_depth = _compute_lane_depths(depth_input_lanes, lane_deps)

    # Rebuild lanes with depends_on_lanes and parallel_group.
    final_lanes: list[ExecutionLane] = []
    for lane in lanes:
        final_lanes.append(
            ExecutionLane(
                lane_id=lane.lane_id,
                wp_ids=lane.wp_ids,
                write_scope=lane.write_scope,
                predicted_surfaces=lane.predicted_surfaces,
                depends_on_lanes=tuple(sorted(lane_deps[lane.lane_id])),
                parallel_group=lane_depth[lane.lane_id],
            )
        )

    mission_branch = mission_branch_name(mission_slug, mission_id=mission_id)

    # Assign planning-artifact WPs to a single canonical lane-planning lane.
    # This lane resolves to the main repository checkout, not a .worktrees/ directory.
    all_lanes = list(final_lanes)
    if planning_artifact_wp_ids:
        planning_lane = _build_planning_lane(
            planning_artifact_wp_ids,
            ownership_manifests,
            depends_on_lanes=tuple(sorted(lane_deps[PLANNING_LANE_ID])),
            parallel_group=lane_depth.get(PLANNING_LANE_ID, 0),
        )
        all_lanes.append(planning_lane)
    all_lanes = sorted(all_lanes, key=lambda lane: (lane.parallel_group, lane.lane_id))

    # planning_artifact_wps is a derived view populated from lane-planning's wp_ids
    # for backward compatibility — do NOT use it as the authoritative source.
    derived_planning_artifact_wps: list[str] = list(planning_artifact_wp_ids)

    # Build the collapse report with independent-WP collapse count.
    independent_collapsed = _count_independent_collapses(collapse_events, dependency_graph)
    collapse_report = CollapseReport(
        events=collapse_events,
        independent_wps_collapsed=independent_collapsed,
    )

    return LanesManifest(
        version=1,
        mission_slug=mission_slug,
        mission_id=resolved_mission_id,
        mission_branch=mission_branch,
        target_branch=target_branch,
        lanes=all_lanes,
        computed_at=now_utc_iso(),
        computed_from="dependency_graph+ownership",
        planning_artifact_wps=derived_planning_artifact_wps,
        collapse_report=collapse_report,
    )


def _build_planning_lane(
    planning_artifact_wp_ids: list[str],
    ownership_manifests: dict[str, OwnershipManifest],
    *,
    depends_on_lanes: tuple[str, ...] = (),
    parallel_group: int = 0,
) -> ExecutionLane:
    """Build the canonical lane-planning ExecutionLane for all planning-artifact WPs.

    All planning-artifact WPs in a mission are grouped into one lane with
    ``lane_id == PLANNING_LANE_ID``.  This lane resolves to the main repository
    checkout at runtime (see ``resolve_workspace_for_wp``).

    P2.7: ``depends_on_lanes`` and ``parallel_group`` come from the lane
    DAG calculation in ``compute_lanes`` so cross-mode dependencies
    (code WP → planning WP, or planning WP → code WP) are honoured at
    lane scheduling time. Defaults to no upstream lanes / parallel
    group 0 for backwards compatibility with the all-planning-only
    short-circuit.
    """
    write_scope: set[str] = set()
    for wp_id in planning_artifact_wp_ids:
        m = ownership_manifests.get(wp_id)
        if m:
            write_scope.update(m.owned_files)

    return ExecutionLane(
        lane_id=PLANNING_LANE_ID,
        wp_ids=tuple(sorted(planning_artifact_wp_ids)),
        write_scope=tuple(sorted(write_scope)),
        predicted_surfaces=("planning",),
        depends_on_lanes=depends_on_lanes,
        parallel_group=parallel_group,
    )


def _compute_lane_depths(
    lanes: list[ExecutionLane],
    lane_deps: dict[str, set[str]],
) -> dict[str, int]:
    """Compute the depth (parallel group) of each lane in the lane DAG.

    Lanes with no dependencies get depth 0. A lane's depth is one plus
    the maximum depth of its dependencies.

    Self-loops and cycles in ``lane_deps`` are detected via the
    ``in_progress`` guard and treated as depth-0 anchors rather than
    recursing infinitely. Cycle detection is best-effort: the depth value
    returned for a cycle's lanes may not reflect graph reality, but the
    function will not blow the recursion stack. Callers that need cycle-
    accurate depths should validate the lane graph before invoking.
    """
    depths: dict[str, int] = {}
    in_progress: set[str] = set()

    def _depth(lane_id: str) -> int:
        if lane_id in depths:
            return depths[lane_id]
        if lane_id in in_progress:
            # Cycle (or self-loop) detected: break the recursion by treating
            # the current lane as a depth-0 anchor. The cycle is logged via
            # ``compute_lanes``'s validation; here we just stop the infinite
            # recursion so the caller can surface a clean diagnostic.
            return 0
        in_progress.add(lane_id)
        try:
            deps = lane_deps.get(lane_id, set())
            # Filter out self-references to prevent depth(L) = 1 + depth(L).
            non_self_deps = {d for d in deps if d != lane_id}
            if not non_self_deps:
                depths[lane_id] = 0
            else:
                depths[lane_id] = 1 + max(_depth(d) for d in non_self_deps)
        finally:
            in_progress.discard(lane_id)
        return depths[lane_id]

    for lane in lanes:
        _depth(lane.lane_id)

    return depths


def _empty_manifest(
    mission_slug: str,
    target_branch: str,
    mission_id: str | None,
    planning_artifact_wps: list[str] | None = None,
) -> LanesManifest:
    """Return an empty LanesManifest (no code WPs to lane)."""
    # WP04/FR-004: mission_id is now str | None from the caller. When it is None
    # (legacy mission without a backfilled ULID) the branch composer uses the
    # legacy naming form (no mid8 suffix). The slug-as-sentinel idiom is removed.
    return LanesManifest(
        version=1,
        mission_slug=mission_slug,
        mission_id=mission_id,
        mission_branch=mission_branch_name(mission_slug, mission_id=mission_id),
        target_branch=target_branch,
        lanes=[],
        computed_at=now_utc_iso(),
        computed_from="dependency_graph+ownership",
        planning_artifact_wps=planning_artifact_wps or [],
    )
