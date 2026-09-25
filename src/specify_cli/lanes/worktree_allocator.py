"""Lane worktree allocation.

Allocates or reuses worktrees for execution lanes. Each lane gets
exactly one worktree and one branch. Sequential WPs in the same
lane share the worktree — no recreation between WPs.

The mission integration branch is created (if absent) when the
first lane worktree is allocated.

#1348 (WP04): when the mission carries a ``coordination_branch`` field
in ``meta.json`` (new-topology missions, WP03+), the lane branch is
parented on the coordination branch rather than the legacy
``mission_branch`` field, and the lane worktree gets a sparse-checkout
policy registered so it cannot see ``status.events.jsonl`` or
``status.json`` (FR-024 / FR-025 / FR-029).
"""

from __future__ import annotations

from mission_runtime import MissionArtifactKind, placement_seam
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from specify_cli.coordination import register_lane_sparse_checkout
from specify_cli.core.errors import StructuredError
from specify_cli.core.vcs.git import capture_branch_tip
from specify_cli.lanes._git import branch_exists as _branch_exists
from specify_cli.lanes.branch_naming import lane_branch_name, resolve_mid8, worktree_path as _worktree_path
from specify_cli.lanes.merge import (
    _ephemeral_merge_driver_activation,
    _make_merge_env,
)
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.planning_commit_classify import PinClass, classify_recorded_pin
from specify_cli.mission_metadata import load_meta

if TYPE_CHECKING:
    # #4889: type-only -- the runtime import lives inside
    # ``_refuse_if_lane_destroyed`` to avoid a module-level cross-package
    # import (mirrors ``_fresh_lane_parent_ref``'s existing lazy-import style
    # for the same ``workspace.context`` module).
    from specify_cli.workspace.context import WorkspaceContext

# Issue #4827 / research.md D5: the single recovery command every orphaned-pin
# consumer (the merge helper here, `implement_support.check_claim_ancestry`,
# and `tasks_move_task._mt_resolve_owned_review_base`) names in its
# operator-facing message. Hoisted once so the three call sites cannot drift
# on the literal text (Sonar S1192).
ORPHANED_PIN_RECOVERY_HINT = "spec-kitty agent mission finalize-tasks --refresh-planning-commit --allow-orphaned"


class LaneTopology(Enum):
    """The derived-parent source for a lane allocation."""

    COORD = "coord"
    LEGACY = "legacy"


class LaneAllocationRoute(Enum):
    """The closed set of routes that can allocate or recover a lane worktree."""

    FRESH_COORD = "fresh_coord"
    FRESH_LEGACY = "fresh_legacy"
    REUSE = "reuse"
    CRASH_RECOVERY = "crash_recovery"


@dataclass(frozen=True)
class LaneBaseDecision:
    """The parent-ref decision returned by the lane-allocation seam.

    ``parent_ref`` is origin-aware (#4969): on a FRESH route with no explicit
    ``base`` it prefers ``origin/<branch>`` over the topology-derived parent,
    and is the ref the lane *worktree* branches from
    (:func:`_create_lane_worktree`). ``topology_parent_ref`` is the
    pre-override topology parent (``coordination_branch`` for coord topology,
    ``mission_branch`` for legacy, or the explicit ``base``) -- it names the
    mission INTEGRATION branch to ensure exists (:func:`_ensure_mission_branch`),
    which is a distinct concern from the lane worktree's parent and must never
    be origin-substituted (#5001).
    """

    parent_ref: str
    base_honored: bool
    route: LaneAllocationRoute
    topology: LaneTopology
    topology_parent_ref: str


class DirtyWorktreeError(Exception):
    """Raised when a lane worktree has uncommitted changes during handoff."""


class LaneNotFoundError(Exception):
    """Raised when a WP is not assigned to any lane."""


class DependencyLaneMergeConflictError(StructuredError):
    """Raised when merging a dependency lane tip into a dependent lane conflicts.

    Issue #1684: a dependent lane's worktree base must contain the approved
    tips of every lane it ``depends_on_lanes``. When two dependency lanes (or a
    dependency lane and the lane base) touch overlapping content, the merge that
    propagates their code cannot auto-resolve. We fail CLOSED — the half-merged
    state is aborted before this is raised so the worktree is never left in a
    conflicted state — and hand the operator a structured ``next_step``.
    """

    error_code: str = "DEPENDENCY_LANE_MERGE_CONFLICT"

    def __init__(self, lane_id: str, dep_lane_id: str, dep_branch: str) -> None:
        self.lane_id = lane_id
        self.dep_lane_id = dep_lane_id
        self.dep_branch = dep_branch
        self.next_step = f"merge {dep_branch!r} into lane {lane_id!r} manually, resolve the conflicts, commit, then re-run the implement command for this WP."
        super().__init__(f"cannot auto-merge dependency lane {dep_lane_id!r} ({dep_branch}) into lane {lane_id!r}: the merge conflicts. {self.next_step}")

    def to_dict(self) -> dict[str, object]:
        payload = super().to_dict()
        payload["lane_id"] = self.lane_id
        payload["dep_lane_id"] = self.dep_lane_id
        payload["dep_branch"] = self.dep_branch
        payload["next_step"] = self.next_step
        return payload


class UnhonorableBaseError(StructuredError):
    """Raised when a supplied ``--base`` cannot be honored by the active route.

    #3571 (P0) / D2 / D3 / FR-004 / FR-009 / FR-010: an operator's explicit
    ``base`` binds the parent a FRESH lane branches from. Four routes cannot
    apply it without either fabricating success or re-parenting work that
    belongs to Mission M8's two-route reconciliation, so each fails loud
    instead of silently ignoring (or partially honoring) the operator's
    intent:

    * ``"reuse"`` -- the lane worktree already exists (:func:`allocate_lane_worktree`
      reuse early-return); an existing lane cannot be re-parented (D3).
    * ``"crash_recovery"`` -- the lane branch exists but its worktree directory
      is gone; re-attaching cannot re-parent either (D3).
    * ``"dependency_lane"`` -- the lane has a non-empty ``depends_on_lanes``;
      honoring ``base`` would require re-parenting coord-descended dependency
      tips onto it, which would re-import unrelated ancestry (D2/FR-009, the
      M8 seam).
    * ``"detached_base"`` -- ``base`` shares no common ancestor with the
      recorded planning-artifact commit (FR-010); merging would require
      ``--allow-unrelated-histories``, which fabricates a lineage the
      operator did not ask for.

    ``route``, ``wp_id``, and ``base`` are built INTO the exception (never
    duplicated as inline f-strings at each of the four raise sites) and are
    surfaced machine-readably via :meth:`to_dict` for the orchestrator-api
    envelope (NFR-004).
    """

    error_code: str = "UNHONORABLE_BASE"

    def __init__(self, *, route: str, wp_id: str, base: str) -> None:
        self.route = route
        self.wp_id = wp_id
        self.base = base
        super().__init__(
            f"Cannot honor --base {base!r} for {wp_id!r}: the {route!r} route "
            "cannot re-parent an already-committed lane. See the mission M8 "
            "two-route reconciliation for the deferred general fix."
        )

    def to_dict(self) -> dict[str, object]:
        payload = super().to_dict()
        payload["route"] = self.route
        payload["wp_id"] = self.wp_id
        payload["base"] = self.base
        return payload


class DestroyedLaneError(StructuredError):
    """Raised when a WP's lane was destroyed but its work was never reachable.

    Issue #4889 (P0): when a lane's worktree AND local branch are both gone
    while the WP is still non-terminal (``in_progress`` / ``blocked`` /
    ``for_review`` / ``in_review``), and the persisted lane tip is not an
    ancestor of ``lanes_manifest.target_branch``, silently falling through to
    the FRESH route re-cuts an empty lane from the coordination/mission tip,
    prints success, and strands the WP's committed work with nothing pointing
    at it any more. This fails CLOSED instead: no worktree/branch is created,
    no lane metadata is touched (FR-003), and the diagnostic names the missing
    branch plus a concrete recovery path (the commit is not gone -- only
    unreferenced -- so ``git reflog`` / ``git fsck --lost-found`` can locate
    it for a manual ``git branch <name> <sha>`` recovery).

    Subclasses :class:`StructuredError` (-> ``RuntimeError``), NOT bare
    ``Exception`` (contrast :class:`DirtyWorktreeError` /
    :class:`LaneNotFoundError` above): the orchestrator-api's existing
    ``except (..., RuntimeError)`` arm at
    ``orchestrator_api/commands.py::_resolve_start_workspace`` must catch this
    and surface a structured ``LANE_ALLOCATION_FAILED`` envelope rather than a
    raw traceback (NFR-004) -- without any edit to that file (it is outside
    this WP's owned files).
    """

    error_code: str = "DESTROYED_LANE"

    def __init__(self, *, lane_id: str, wp_id: str, branch_name: str) -> None:
        self.lane_id = lane_id
        self.wp_id = wp_id
        self.branch_name = branch_name
        self.next_step = (
            f"the commit(s) are not deleted, only unreferenced -- recover the tip "
            f"first: check `git reflog {branch_name}` (if the reflog entry survived) "
            f"or `git fsck --lost-found` (dangling commits) in the repository, "
            f"re-create the branch with `git branch {branch_name} <recovered-sha>`, "
            f"then re-run the implement command for {wp_id!r}."
        )
        super().__init__(
            f"cannot allocate lane {lane_id!r} for {wp_id!r}: its branch "
            f"{branch_name!r} and worktree are both gone, the WP is still "
            f"non-terminal, and its committed work is not reachable from the "
            f"target branch -- refusing to silently re-cut an empty lane and "
            f"strand that work. {self.next_step}"
        )

    def to_dict(self) -> dict[str, object]:
        payload = super().to_dict()
        payload["lane_id"] = self.lane_id
        payload["wp_id"] = self.wp_id
        payload["branch_name"] = self.branch_name
        payload["next_step"] = self.next_step
        return payload


# #4889 FR-002: canonical WP lane values the guard treats as "allocated
# before, work in flight" -- matches the WP prompt / contract's non-terminal
# post-allocation set exactly. Terminal (``done``/``canceled``) and
# pre-allocation (``planned``/``claimed``) are deliberately excluded.
_DESTROYED_LANE_TRIGGER_STATES = frozenset({"in_progress", "blocked", "for_review", "in_review"})


def _canonical_wp_lane_value(repo_root: Path, mission_slug: str, wp_id: str) -> str | None:
    """Return the canonical WP lane value from the COORD status surface, or ``None``.

    #4889 T004: reads via ``placement_seam(...).read_dir(STATUS_STATE)`` (the
    coord-aware seam, already imported at module scope) rather than
    hand-rolling ``materialize(repo_root/"kitty-specs"/mission_slug)`` -- on a
    coord-topology mission the latter reads the sparse-excluded PRIMARY tree
    and silently no-ops (never seeing the real event log), which would mean
    this guard never fires on the create-time-default coord topology (#2514).
    ``None`` when no event log has been bootstrapped yet (WP never finalized)
    or the WP is absent from the reduced snapshot -- never a trigger.
    """
    from specify_cli.status.lane_reader import CanonicalStatusNotFoundError, get_wp_lane

    status_dir = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.STATUS_STATE)
    try:
        lane = get_wp_lane(status_dir, wp_id)
    except CanonicalStatusNotFoundError:
        return None
    return str(lane.value)


def _lane_tip_reachable_from_target(
    repo_root: Path,
    context: WorkspaceContext,
    target_branch: str,
) -> bool:
    """Return True when the persisted lane tip is an ancestor of ``target_branch``.

    #4889 FR-009 / contract "re-open after merge": ``context.base_commit`` is
    the only SHA the persisted :class:`WorkspaceContext` carries. When it is
    already reachable from ``target_branch`` the mission has since absorbed
    that lineage (e.g. a real, non-squash merge landed it) and the guard must
    NOT fire -- a lane re-opened in that state is not stranding anything, and
    refusing would be a false positive (NFR-001). A missing ``base_commit``
    fails closed (treated as unreachable, never silently waved through).
    """
    if not context.base_commit:
        return False
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", context.base_commit, target_branch],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _refuse_if_lane_destroyed(
    repo_root: Path,
    mission_slug: str,
    wp_id: str,
    lane_id: str,
    branch: str,
    target_branch: str,
) -> None:
    """Raise :class:`DestroyedLaneError` when a WP's destroyed lane must fail closed.

    Called only once neither the lane branch nor its worktree exists (the
    REUSE / CRASH_RECOVERY gates above already ruled those two out), so this
    is purely the decision table's last row: CTX present, STATE non-terminal,
    tip unreachable from target (see ``../data-model.md#4889-destroyed-lane-
    decision-table``). A genuinely fresh lane (no persisted context -- FR-001)
    or a lane whose tip already landed on the target branch (FR-009 resume)
    are both no-ops here, falling through to the normal FRESH route.
    """
    from specify_cli.workspace.context import find_context_for_wp

    context = find_context_for_wp(repo_root, mission_slug, wp_id)
    if context is None:
        return

    state = _canonical_wp_lane_value(repo_root, mission_slug, wp_id)
    if state not in _DESTROYED_LANE_TRIGGER_STATES:
        return

    if _lane_tip_reachable_from_target(repo_root, context, target_branch):
        return

    raise DestroyedLaneError(lane_id=lane_id, wp_id=wp_id, branch_name=branch)


class PlanningCommitMergeConflictError(StructuredError):
    """Raised when merging the recorded planning-artifact commit conflicts.

    FR-009 / ADR ``2026-07-29-1`` (#2993): a freshly created (or reused /
    recovered) lane worktree merges in the recorded finalize-tasks planning
    commit (``LanesManifest.planning_commit_sha``) on top of its existing
    ``coordination_branch`` / ``mission_branch`` parentage, so the lane's own
    history contains the mission's spec/tasks artifacts. That merge is expected
    to be conflict-free in practice — ``coordination_branch``'s own commits are
    COORD-partition status/matrix files, disjoint from the PRIMARY-partition
    planning files the recorded commit carries — but a genuinely conflicting
    tree fails CLOSED here rather than leaving a half-merged worktree. The
    merge is aborted before this is raised.
    """

    error_code: str = "PLANNING_COMMIT_MERGE_CONFLICT"

    def __init__(
        self,
        lane_id: str,
        planning_commit_sha: str,
        *,
        wp_task_conflicts: list[str] | None = None,
    ) -> None:
        self.lane_id = lane_id
        self.planning_commit_sha = planning_commit_sha
        # #4889 T006 (FR-009 resilience, belt-and-braces for #4905): an
        # ``add/add`` conflict specifically on a ``tasks/WP*.md`` path at this
        # merge site means a PRIMARY-partition WP-task blob landed on the
        # coordination side -- the exact #4905 defect this mission's WP02
        # fixes at the commit-routing seam. Optional and empty by default so
        # every pre-existing raise site / caller keeps its byte-identical
        # message (backward compatible, NFR-005-style).
        self.wp_task_conflicts = list(wp_task_conflicts) if wp_task_conflicts else []
        self.next_step = (
            f"merge {planning_commit_sha!r} into the lane {lane_id!r} worktree "
            "manually, resolve the conflicts, commit, then re-run the implement "
            "command for this WP."
        )
        detail = ""
        if self.wp_task_conflicts:
            paths = ", ".join(self.wp_task_conflicts)
            detail = (
                f" WP task file(s) {paths} conflicted -- this shape means a "
                "PRIMARY-partition tasks/WP*.md blob landed on the coordination "
                "side (#4905, the coord-commit path partition fix); investigate "
                "the commit-routing seam rather than treating this as a generic "
                "content conflict."
            )
        super().__init__(
            f"cannot auto-merge the recorded planning commit {planning_commit_sha!r} into lane {lane_id!r}: the merge conflicts.{detail} {self.next_step}"
        )

    def to_dict(self) -> dict[str, object]:
        payload = super().to_dict()
        payload["lane_id"] = self.lane_id
        payload["planning_commit_sha"] = self.planning_commit_sha
        payload["next_step"] = self.next_step
        if self.wp_task_conflicts:
            payload["wp_task_conflicts"] = self.wp_task_conflicts
        return payload


class OrphanedPlanningCommitError(StructuredError):
    """Raised when the recorded ``planning_commit_sha`` is orphaned or foreign.

    Issue #4827 / research.md D5/D6: :func:`classify_recorded_pin` (WP01)
    classifies the RECORDED pin against the planning target-branch tip
    (never a lane worktree's HEAD -- C-006). ``ORPHANED`` means the commit
    object still exists but is no longer reachable from that tip (the
    mid-mission rebase shape); ``FOREIGN`` means the object is absent
    entirely. Either way, merging the pin would build on a dead base --
    a problem no amount of manual conflict resolution can fix, unlike a
    genuine :class:`PlanningCommitMergeConflictError` on a still-reachable
    (``ADVANCED``) pin. Only ``finalize-tasks --refresh-planning-commit
    --allow-orphaned`` can re-point the mission-wide record, so this is
    raised as a DISTINCT, sibling exception (never a subclass of
    :class:`PlanningCommitMergeConflictError`) so the fresh-path
    ``except PlanningCommitMergeConflictError`` in
    :func:`allocate_lane_worktree` does not catch it and loop the operator
    through a remove-and-recreate cycle that only helps a transient
    conflict, never a stale mission-wide pin.
    """

    error_code: str = "ORPHANED_PLANNING_COMMIT"

    def __init__(self, lane_id: str, planning_commit_sha: str, pin_class: PinClass) -> None:
        self.lane_id = lane_id
        self.planning_commit_sha = planning_commit_sha
        self.pin_class = pin_class
        if pin_class is PinClass.FOREIGN:
            # A FOREIGN pin's object is absent from this repository, so a
            # re-pin cannot recover it and ``--allow-orphaned`` would be
            # refused by finalize (FR-004). Point at investigation, not the
            # recovery flag, so the operator is not sent on a two-hop path
            # that ends in a refusal (#4827 review LOW / DD-10).
            self.next_step = (
                f"the recorded planning commit {planning_commit_sha!r} is foreign "
                f"(its commit object is absent from this repository, not merely unreachable); "
                f"a re-pin cannot recover an absent object -- investigate how this SHA was "
                f"recorded and repair the mission's planning provenance before retrying this WP."
            )
        else:
            self.next_step = (
                f"the recorded planning commit {planning_commit_sha!r} is orphaned "
                f"(no longer reachable from the mission's target-branch tip); run "
                f"{ORPHANED_PIN_RECOVERY_HINT!r} to re-point it, then retry this WP."
            )
        super().__init__(
            f"cannot merge the recorded planning commit {planning_commit_sha!r} into lane "
            f"{lane_id!r}: it is {pin_class.value} against the target-branch tip. {self.next_step}"
        )

    def to_dict(self) -> dict[str, object]:
        payload = super().to_dict()
        payload["lane_id"] = self.lane_id
        payload["planning_commit_sha"] = self.planning_commit_sha
        payload["pin_class"] = self.pin_class.value
        payload["next_step"] = self.next_step
        return payload


def predict_lane_worktree(repo_root: Path, mission_slug: str, lane_id: str) -> tuple[Path, str]:
    """The ONE lane-worktree placement decision (path + branch), read-only.

    Both the write authority (:func:`allocate_lane_worktree`) and read-only
    mirrors (``orchestrator-api resolve-workspace``, its transition guard)
    consume this, so the compose grammar is single-sited and a future mid8
    cutover is one edit.

    Emit-don't-guess: routes the on-disk worktree name through the canonical
    WP01 seam instead of an ad-hoc f-string. Passes ``mission_id=None`` so the
    seam reproduces the legacy ``f"{slug}-{lane}"`` grammar byte-identically
    (the historical call sites carried no mid8); introducing a mission_id here
    would append ``-{mid8}`` and rename every existing lane worktree.
    """
    branch = lane_branch_name(mission_slug, lane_id)
    worktree_path = _worktree_path(repo_root, mission_slug, mission_id=None, lane_id=lane_id)
    return worktree_path, branch


def _guard_base_honorable(
    base: str | None,
    route: str,
    wp_id: str,
    *,
    lane: ExecutionLane | None = None,
    planning_sha: str | None = None,
    repo_root: Path | None = None,
) -> None:
    """Raise :class:`UnhonorableBaseError` when ``base`` cannot be honored at ``route``.

    The single call-site for all four fail-loud triggers (D2/D3/FR-004/FR-009/
    FR-010) so each guard body in :func:`allocate_lane_worktree` stays a flat
    ``if`` (Sonar S3776 cognitive-nesting) rather than composing the message
    inline at each of the four raise sites. ``base is None`` is always a
    no-op — these routes only need to fail loud when an operator actually
    supplied a base this route cannot apply.

    Routes:
        ``"reuse"`` / ``"crash_recovery"``: unconditional once ``base`` is
            supplied — an already-created lane cannot be re-parented (D3).
        ``"dependency_lane"``: raises only when ``lane.depends_on_lanes`` is
            non-empty (D2/FR-009) — a no-dependency lane is fine.
        ``"detached_base"``: raises only when ``planning_sha`` is recorded
            AND shares no common ancestor with ``base`` (FR-010), checked via
            ``git merge-base`` in ``repo_root`` BEFORE the worktree/branch is
            created (atomicity — no half-created lane on failure).
    """
    if base is None:
        return
    if route in ("reuse", "crash_recovery"):
        raise UnhonorableBaseError(route=route, wp_id=wp_id, base=base)
    if route == "dependency_lane":
        if lane is not None and lane.depends_on_lanes:
            raise UnhonorableBaseError(route=route, wp_id=wp_id, base=base)
        return
    if route == "detached_base":
        if planning_sha is None or repo_root is None:
            return
        result = subprocess.run(
            ["git", "merge-base", base, planning_sha],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise UnhonorableBaseError(route=route, wp_id=wp_id, base=base)


def _resolve_lane_parent(
    base: str | None,
    coordination_branch: str | None,
    mission_branch: str,
) -> str:
    """Return the parent ref a freshly-created lane branches from (D1/C-005).

    ``base`` — when supplied — fully REPLACES the topology-derived parent
    (``coordination_branch`` for coord topology, ``mission_branch`` for
    legacy); it is never layered on top of it. ``base=None`` reproduces the
    prior topology-derived parent exactly (byte-identical legacy behaviour,
    C-005/FR-006).
    """
    if base is not None:
        return base
    return coordination_branch if coordination_branch is not None else mission_branch


def _guard_route_base(
    base: str | None,
    route: LaneAllocationRoute,
    wp_id: str,
    *,
    lane: ExecutionLane | None,
    planning_sha: str | None,
    repo_root: Path | None,
) -> None:
    """Dispatch an allocation route to its applicable base-refusal triggers."""

    if route is LaneAllocationRoute.REUSE:
        _guard_base_honorable(base, "reuse", wp_id)
        return
    if route is LaneAllocationRoute.CRASH_RECOVERY:
        _guard_base_honorable(base, "crash_recovery", wp_id)
        return
    _guard_base_honorable(
        base,
        "detached_base",
        wp_id,
        planning_sha=planning_sha,
        repo_root=repo_root,
    )
    _guard_base_honorable(base, "dependency_lane", wp_id, lane=lane)


_FRESH_ROUTES = frozenset({LaneAllocationRoute.FRESH_COORD, LaneAllocationRoute.FRESH_LEGACY})


def resolve_lane_base_or_refuse(
    *,
    base: str | None,
    route: LaneAllocationRoute,
    coordination_branch: str | None,
    mission_branch: str,
    wp_id: str,
    lane: ExecutionLane | None = None,
    planning_sha: str | None = None,
    repo_root: Path | None = None,
    branch: str | None = None,
) -> LaneBaseDecision:
    """Resolve a lane parent ref, or refuse a base the route cannot honor.

    This is the sole parent-ref decision point for lane allocation. ``None``
    preserves the topology-derived parent. An explicit base replaces that parent
    only on an honorable fresh route; reuse, crash recovery, dependency-bearing,
    and detached-base routes raise before creation side effects.

    #4969 origin-preference: on a FRESH route (``FRESH_COORD`` / ``FRESH_LEGACY``)
    with no explicit ``base``, the topology-derived parent is further resolved
    through :func:`_fresh_lane_parent_ref`'s origin-aware probe so the returned
    ``parent_ref`` is already origin-preferring -- callers never compute a
    parent ref outside this seam.

    The returned :class:`LaneBaseDecision` carries both refs: ``parent_ref``
    is origin-aware and feeds the lane *worktree*'s parent; ``topology_parent_ref``
    is the pre-override topology parent and feeds the mission INTEGRATION
    branch's ensure-exists call (#5001) -- the two must not be conflated.
    """

    _guard_route_base(
        base,
        route,
        wp_id,
        lane=lane,
        planning_sha=planning_sha,
        repo_root=repo_root,
    )
    topology = LaneTopology.COORD if coordination_branch is not None else LaneTopology.LEGACY
    topology_parent = _resolve_lane_parent(
        base,
        coordination_branch,
        mission_branch,
    )
    parent_ref = _fresh_lane_parent_ref(
        repo_root,
        branch,
        base,
        topology_parent,
        route,
    )
    return LaneBaseDecision(
        parent_ref=parent_ref,
        base_honored=base is not None,
        route=route,
        topology=topology,
        topology_parent_ref=topology_parent,
    )


def _fresh_lane_parent_ref(
    repo_root: Path | None,
    branch: str | None,
    base: str | None,
    topology_parent_ref: str,
    route: LaneAllocationRoute,
) -> str:
    """Return the ref a FRESH lane branches from, preferring ``origin/<branch>`` (#4969).

    PRIVATE helper called only by :func:`resolve_lane_base_or_refuse` -- the
    single seam for every lane parent-ref decision. Never call this from an
    allocation call site directly.

    WP10 integration (C-4 / #4969): when the operator supplied no explicit
    ``--base``, an approved lane that exists only as ``refs/remotes/origin/<branch>``
    (pushed by a teammate, dropped locally) must root the fresh cut instead of the
    topology-derived parent — otherwise the fresh cut from the local mission/coord
    branch SHADOWS the pushed work. Delegates the origin-ref probe to
    :func:`~specify_cli.workspace.context.resolve_lane_base_ref` so this site and
    ``implement._validate_base_ref`` (WP03) agree on what "the origin lane exists"
    means; the resolver falls back to ``topology_parent_ref`` when no origin ref
    exists (offline / never pushed) — byte-identical to the prior local cut. An
    explicit ``base`` already fully replaced the parent (D1) and is never
    origin-overridden. Only applies to a FRESH route (``FRESH_COORD`` /
    ``FRESH_LEGACY``); reuse, crash-recovery, and any route missing ``repo_root``
    or ``branch`` return the topology-derived parent unchanged.
    """
    if base is not None or route not in _FRESH_ROUTES or repo_root is None or branch is None:
        return topology_parent_ref
    from specify_cli.workspace.context import resolve_lane_base_ref

    resolved: str = resolve_lane_base_ref(repo_root, branch, fallback_base=topology_parent_ref)
    return resolved


def allocate_lane_worktree(
    repo_root: Path,
    mission_slug: str,
    wp_id: str,
    lanes_manifest: LanesManifest,
    base: str | None = None,
) -> tuple[Path, str]:
    """Allocate or reuse the worktree for the lane containing wp_id.

    Returns (worktree_path, branch_name).

    If the lane worktree already exists (from a prior WP in the same lane),
    validates it is clean and returns the existing path.

    If the lane worktree does not exist, creates the mission branch (if
    needed) and then creates the lane worktree branching from it.

    Issue #1684 — cross-lane dependency propagation: a lane may declare
    ``depends_on_lanes``. The dependent lane's worktree base must contain the
    approved tips of those dependency lanes so the dependent WP can see the
    sibling-lane code it builds on. Both the FRESH-creation path and the
    REUSE path merge in every resolvable dependency-lane tip (in
    ``parallel_group`` then ``lane_id`` order). The merge is idempotent —
    already-merged tips fast-forward to a no-op — so re-entering a lane after a
    dependency was approved late (the WP05/WP09 double-hit on 01KTYGTE) picks up
    the newly-approved tip. A dependency lane whose branch no longer resolves
    (merged-and-deleted post-mission) is skipped with a warning; a true merge
    conflict fails closed with :class:`DependencyLaneMergeConflictError` after
    aborting the merge (never a half-merged worktree).

    #3571 (P0) / D1/D2/D3: ``base``, when supplied, is threaded as an EXPLICIT
    parameter (never smuggled through ``lanes_manifest.mission_branch``) and
    fully REPLACES the topology-derived parent on a fresh no-dependency lane
    (D1). Four routes cannot honor a supplied ``base`` and fail loud instead
    (:class:`UnhonorableBaseError`, never a silent no-op / warn-and-continue):
    lane-worktree reuse, branch-exists crash-recovery, a dependency-bearing
    lane, and a base detached from the recorded planning commit (FR-010).

    Args:
        repo_root: Absolute path to the main repository.
        mission_slug: Feature slug for branch naming.
        wp_id: Work package ID to allocate a worktree for.
        lanes_manifest: The computed lanes manifest.
        base: Optional explicit base ref (``--base``). ``None`` reproduces
            prior topology-derived-parent behaviour exactly (NFR-005).

    Returns:
        Tuple of (worktree_path, branch_name).

    Raises:
        LaneNotFoundError: If wp_id is not in any lane.
        DirtyWorktreeError: If reusing a worktree that has uncommitted changes.
        DependencyLaneMergeConflictError: If a dependency lane tip cannot be
            auto-merged into the lane (fail-closed, merge aborted first).
        UnhonorableBaseError: If ``base`` is supplied but the active route
            cannot honor it (D2/D3/FR-009/FR-010).
        RuntimeError: If git operations fail.
    """
    lane = lanes_manifest.lane_for_wp(wp_id)
    if lane is None:
        raise LaneNotFoundError(f"{wp_id} is not assigned to any execution lane in lanes.json")

    # C-006 (#4827/WP03): capture the TARGET-BRANCH tip ONCE, for every
    # _merge_recorded_planning_commit call below to classify the recorded pin
    # against -- NEVER a lane worktree's own HEAD (that is a different
    # question, the pre-existing "is this lane already merged?" no-op gate;
    # see classify_recorded_pin's own C-006 docstring note and #2993). Reuses
    # the canonical `capture_branch_tip` (returns `None` on failure, never the
    # "unknown" sentinel `implement_support._rev_parse` uses for frontmatter
    # display) so an unresolvable target branch degrades the classifier to
    # `INDETERMINATE` -- the pre-#4827 behaviour -- rather than misclassifying.
    target_tip = capture_branch_tip(repo_root, lanes_manifest.target_branch)

    # Placement (path + branch) comes from the single predict seam — the write
    # authority and the read-only mirrors must never diverge on this decision.
    worktree_path, branch = predict_lane_worktree(repo_root, mission_slug, lane.lane_id)

    if worktree_path.exists():
        # FL1 (D3): an existing lane worktree cannot be re-parented onto a
        # newly-supplied base — the seam refuses BEFORE reuse side effects.
        resolve_lane_base_or_refuse(
            base=base,
            route=LaneAllocationRoute.REUSE,
            coordination_branch=None,
            mission_branch=lanes_manifest.mission_branch,
            wp_id=wp_id,
        )
        # Reuse existing lane worktree — validate it is clean first.
        _validate_worktree_clean(worktree_path, lane.lane_id)
        # FR-009 (#2993) reuse-path self-heal: a lane created before this fix
        # (or before a later finalize-tasks re-run recorded a newer SHA) picks
        # up the recorded planning commit here. Idempotent no-op once merged.
        _merge_recorded_planning_commit(repo_root, worktree_path, lane.lane_id, lanes_manifest.planning_commit_sha, target_tip)
        # #1684 reuse-path catch-up: a dependency lane may have been approved
        # *after* this worktree was created. Merge any newly-approved dep tips
        # so the dependent lane sees them. Idempotent: already-merged tips are
        # ancestors and skip.
        _merge_dependency_lane_tips(repo_root, worktree_path, mission_slug, lane, lanes_manifest)
        return worktree_path, branch

    # #1348 (WP04): pick the parent branch.
    #
    #   New-topology missions (meta.json has ``coordination_branch``):
    #     parent the lane on the coordination branch and register the
    #     status-files sparse-checkout exclusion.
    #
    #   Legacy missions (no ``coordination_branch``): fall back to the
    #     ``mission_branch`` field. No sparse-checkout. WP08 will harden
    #     the legacy path further; for now we preserve existing behaviour.
    #
    # #2514 (WP04): hoisted above the crash-recovery branch below so BOTH the
    # recovery path and the fresh-create path see the same two values without
    # recomputing them twice — see ``_register_sparse_checkout_if_coord``.
    coordination_branch = _read_coordination_branch(repo_root, mission_slug)
    # Route through the authoritative resolver (WP03 / FR-009, F-1). The
    # former raising ``mid8`` + try/except is replaced by resolve_mid8's
    # decline-to-``""`` contract; ``or None`` preserves the prior ``None``
    # behaviour so the downstream registration guard is unchanged.
    short_id = resolve_mid8(mission_slug, mission_id=lanes_manifest.mission_id) or None

    # #2512: crash-recovery path — branch exists but worktree directory was
    # lost (e.g. agent process killed by OS idle-sleep).  Re-attach the
    # worktree to its existing branch instead of creating a new branch (which
    # would fail with "branch already exists").  Prune stale worktree registry
    # entries first so git does not reject the re-attachment on the grounds
    # that the branch is "already checked out" in the now-gone worktree.
    if _branch_exists(repo_root, branch):
        # FL2 (D3): a branch that already exists (worktree dir gone) cannot
        # be re-parented by re-attaching — the seam refuses BEFORE recovery.
        resolve_lane_base_or_refuse(
            base=base,
            route=LaneAllocationRoute.CRASH_RECOVERY,
            coordination_branch=coordination_branch,
            mission_branch=lanes_manifest.mission_branch,
            wp_id=wp_id,
        )
        subprocess.run(
            ["git", "worktree", "prune"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
        )
        _recover_lane_worktree(repo_root, worktree_path, branch)
        _validate_worktree_clean(worktree_path, lane.lane_id)
        # #2514: re-register the sparse-checkout exclusion on recovery too —
        # a recovered coord-topology lane worktree must not re-leak
        # status.events.jsonl / status.json (Scenario 2).
        _register_sparse_checkout_if_coord(
            worktree_path,
            mission_slug,
            coordination_branch,
            short_id,
        )
        # FR-009 (#2993) crash-recovery self-heal: mirrors the reuse-path call
        # below — a re-attached lane picks up the recorded planning commit too.
        _merge_recorded_planning_commit(repo_root, worktree_path, lane.lane_id, lanes_manifest.planning_commit_sha, target_tip)
        _merge_dependency_lane_tips(repo_root, worktree_path, mission_slug, lane, lanes_manifest)
        return worktree_path, branch

    # #4889 (P0) fail-closed pre-flight: neither the branch nor the worktree
    # exists at this point (the REUSE / CRASH_RECOVERY gates above already
    # returned otherwise). Before falling through to a FRESH route, refuse to
    # silently re-cut an empty lane over a WP whose prior committed work is
    # still non-terminal and unreachable from the target branch.
    _refuse_if_lane_destroyed(
        repo_root,
        mission_slug,
        wp_id,
        lane.lane_id,
        branch,
        lanes_manifest.target_branch,
    )

    # Fresh routes resolve their parent through the single seam before either
    # creation helper runs. Detached-base and dependency refusals therefore
    # leave no half-created lane, and no route computes a parent ref inline.
    if coordination_branch is not None:
        decision = resolve_lane_base_or_refuse(
            base=base,
            route=LaneAllocationRoute.FRESH_COORD,
            coordination_branch=coordination_branch,
            mission_branch=lanes_manifest.mission_branch,
            wp_id=wp_id,
            lane=lane,
            planning_sha=lanes_manifest.planning_commit_sha,
            repo_root=repo_root,
            branch=branch,
        )
        _ensure_branch_exists(
            repo_root,
            coordination_branch,
            lanes_manifest.target_branch,
        )
        _create_lane_worktree(
            repo_root,
            worktree_path,
            branch,
            decision.parent_ref,
        )
        # Register the sparse-checkout policy so the lane filesystem does
        # NOT contain status.events.jsonl / status.json. Only meaningful
        # when we have a mid8; new-topology missions always do because
        # WP03 mints the coord branch only when mission_id is present.
        _register_sparse_checkout_if_coord(
            worktree_path,
            mission_slug,
            coordination_branch,
            short_id,
        )
    else:
        decision = resolve_lane_base_or_refuse(
            base=base,
            route=LaneAllocationRoute.FRESH_LEGACY,
            coordination_branch=None,
            mission_branch=lanes_manifest.mission_branch,
            wp_id=wp_id,
            lane=lane,
            planning_sha=lanes_manifest.planning_commit_sha,
            repo_root=repo_root,
            branch=branch,
        )
        _ensure_mission_branch(
            repo_root,
            decision.topology_parent_ref,
            lanes_manifest.target_branch,
        )
        _create_lane_worktree(
            repo_root,
            worktree_path,
            branch,
            decision.parent_ref,
        )

    # FR-009 (#2993) / ADR 2026-07-29-1: merge the recorded finalize-tasks
    # planning-artifact commit into the freshly created lane, on top of its
    # coordination_branch / mission_branch parentage (never in place of it —
    # see the ADR's coord-descent guard). A no-op when the manifest predates
    # this field (backward compatible).
    #
    # FR-006/#3281 (T010): fresh-path atomicity, scoped. A conflict here is
    # not itself catastrophic — the merge helper already aborts the
    # half-merge before raising (the worktree's tree is clean, never left
    # conflicted) — but without this, the just-created worktree stays
    # registered with nothing further ever touching it: a bare retry would
    # hit ``worktree_path.exists()`` above and take the REUSE route, which
    # re-runs this exact merge and fails identically forever. Removing the
    # worktree (branch intentionally kept — see below) makes a retry take
    # the CRASH-RECOVERY route instead, which re-attaches and re-runs the
    # same idempotent self-heal, so the operator's manual fix (per the
    # error's own ``next_step``) is picked up on the next attempt.
    # #4827/WP03: deliberately narrow to the GENERIC conflict only.
    # `OrphanedPlanningCommitError` is a sibling, not a subclass (see its
    # docstring), so it is NOT caught here -- an orphaned/foreign pin leaves
    # the just-created worktree registered rather than being removed and
    # re-tried forever via crash-recovery, which would just re-classify
    # `orphaned` again on every attempt until an operator re-pins.
    try:
        _merge_recorded_planning_commit(repo_root, worktree_path, lane.lane_id, lanes_manifest.planning_commit_sha, target_tip)
    except PlanningCommitMergeConflictError:
        # Only the WORKTREE is removed, not the branch: a retry then resolves
        # via the crash-recovery path above (branch exists, worktree dir
        # gone), which re-attaches and re-merges rather than needing this
        # function to duplicate that recovery logic.
        _remove_lane_worktree(repo_root, worktree_path)
        raise

    # #1684 fresh-path propagation: merge approved dependency-lane tips on top
    # of the chosen base (coordination or legacy mission branch) so the
    # dependent lane sees sibling code.
    _merge_dependency_lane_tips(repo_root, worktree_path, mission_slug, lane, lanes_manifest)

    return worktree_path, branch


def _wp_task_file_conflict_paths(merge_stdout: str) -> list[str]:
    """Extract ``tasks/WP*.md`` conflict paths from a git-merge conflict report.

    #4889 T006 (belt-and-braces for #4905): a plain ``git merge`` conflict
    report includes a line per conflicting path, e.g. ``CONFLICT (add/add):
    Merge conflict in kitty-specs/<slug>/tasks/WP01-foo.md``. This is a
    minimal, best-effort text scan (not a duplicate of the real #4905 fix,
    which is WP02's commit-routing partition) -- it only names the path so
    :class:`PlanningCommitMergeConflictError` can point at the right root
    cause instead of a bare git conflict dump. Returns an empty list when no
    such line is present (the overwhelming majority of conflicts, which stay
    on the existing generic diagnostic).
    """
    return sorted(
        {
            line.split("Merge conflict in", 1)[1].strip()
            for line in merge_stdout.splitlines()
            if "CONFLICT" in line and "Merge conflict in" in line and "tasks/WP" in line
        }
    )


def _merge_recorded_planning_commit(
    repo_root: Path,
    worktree_path: Path,
    lane_id: str,
    planning_commit_sha: str | None,
    target_tip: str | None = None,
) -> None:
    """Merge the recorded finalize-tasks planning commit into a lane worktree.

    FR-009 / ADR ``2026-07-29-1`` (#2993): a lane branched purely off
    ``coordination_branch`` (or the legacy ``mission_branch``) has no common
    ancestor with the primary ``target_branch`` commit that carries
    ``spec.md``/``tasks.md``/``tasks/WP*.md`` — ``coordination_branch`` is minted
    at mission-create time, BEFORE planning exists. Merging the RECORDED
    (never re-derived live) planning-artifact SHA into the lane gives it BOTH
    ancestries: the ``coordination_branch`` lineage the sparse-checkout / status
    machinery and the WP04 (#1348) coord-descent guard still require
    (unaffected — this only ADDS an ancestor, it never changes the lane's
    primary parent), and the planning-artifact lineage #2993 requires.

    ``planning_commit_sha`` is ``None`` for a ``lanes.json`` written before this
    fix (backward compatibility) — a no-op in that case, reproducing pre-WP01
    behaviour exactly.

    #4827/WP03 (D5/D6, C-006): ``target_tip`` MUST be the planning
    target-branch tip (e.g. captured via ``capture_branch_tip(repo_root,
    lanes_manifest.target_branch)``), never a lane worktree's ``HEAD`` --
    passing a lane HEAD here would misfire on every healthy fresh coord lane
    (#2993). BEFORE the pre-existing lane-HEAD no-op gate below, the recorded
    pin is classified against that tip via
    :func:`~specify_cli.lanes.planning_commit_classify.classify_recorded_pin`;
    an ``ORPHANED``/``FOREIGN`` classification raises
    :class:`OrphanedPlanningCommitError` unconditionally -- even when the pin
    already happens to be an ancestor of this worktree's own HEAD (D6: the
    stale-pin error fires for as long as the mission-wide record stays
    orphaned; only a ``finalize-tasks --refresh-planning-commit
    --allow-orphaned`` re-pin clears it). ``target_tip=None`` (an
    unresolvable target branch, or a caller that predates this parameter)
    degrades the classifier to ``INDETERMINATE``, which is a no-op here --
    byte-identical to the pre-#4827 behaviour. An ``ADVANCED`` (reachable)
    pin also falls through unchanged: the lane-HEAD no-op gate and the
    genuine-content-conflict merge path below are untouched by this WP.

    Idempotent: a SHA already an ancestor of ``HEAD`` is skipped (no-op),
    which is what makes it safe to call from the worktree-reuse and
    crash-recovery paths as well as fresh creation — an existing lane
    self-heals the next time it is touched, and a lane re-entered after a
    ``finalize-tasks`` re-run picks up a newer recorded value.

    Raises:
        OrphanedPlanningCommitError: if the recorded pin is orphaned or
            foreign against ``target_tip`` (#4827).
        PlanningCommitMergeConflictError: if the merge of a still-reachable
            pin conflicts (fail closed; the half-merge is aborted before this
            is raised).
    """
    if planning_commit_sha is None:
        return
    pin_class = classify_recorded_pin(repo_root, planning_commit_sha, target_tip)
    if pin_class in (PinClass.ORPHANED, PinClass.FOREIGN):
        raise OrphanedPlanningCommitError(lane_id, planning_commit_sha, pin_class)
    is_ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", planning_commit_sha, "HEAD"],
        cwd=str(worktree_path),
        capture_output=True,
        text=True,
    )
    if is_ancestor.returncode == 0:
        return
    # #2709/#2711 self-heal: ``spec-kitty init`` writes the ``.gitattributes``
    # mapping (e.g. ``kitty-specs/**/status.events.jsonl merge=spec-kitty-
    # event-log``) but cannot always register the matching git-config driver
    # definitions at init time (the project may not be a git repo yet). Without
    # the git-config half, a divergent-on-both-sides bookkeeping file
    # (status.events.jsonl, meta.json, traces/*.md, ...) falls back to a plain
    # 3-way merge and conflicts here instead of reconciling via its custom
    # driver. Mirrors ``auto_rebase.attempt_auto_rebase``'s identical self-heal
    # call (performed inside the activation context manager below).
    #
    # #4120: the OTHER half of the same gap — the driver's *attribute mapping*
    # can be missing too. The lane base structurally predates the mission's
    # planning commits (``coordination_branch``/``mission_branch`` is minted
    # before planning exists — that is exactly why this merge runs), so the lane
    # worktree's checked-out tree may carry no committed ``.gitattributes`` at
    # all (fresh repos, projects initialized before the mapping landed, or a
    # lane base cut before the commit that added it). Without an active
    # mapping, the add/add collision this merge is EXPECTED to produce on the
    # append-only ``status.events.jsonl`` (a lone finalize-tasks bootstrap event
    # on the lane side against the full specify/plan history on the planning
    # side, both added after a merge-base that predates the file) is not
    # union-merged by the ``spec-kitty-event-log`` driver — it surfaces as a
    # raw git conflict the operator must splice by hand. Activate the driver
    # attribute mappings ephemerally for exactly this merge — the same
    # ``_ephemeral_merge_driver_activation`` the squash mission→target merge
    # uses — so the union drivers fire regardless of what the branch committed.
    # The seeding is torn down before returning (never persisted into a later
    # ``auto_rebase`` — the #2709/#2711 regression), and a genuinely conflicting
    # tree still fails closed below.
    # Issue #87: the registered drivers invoke bare ``spec-kitty ...`` (e.g.
    # ``merge-driver-event-log``), so the merge subprocess must resolve that
    # name to the RUNNING CLI, not to whatever the ambient PATH happens to
    # carry — an agent harness / CI wrapper may not have this CLI on PATH at
    # all. Route through the pipeline's single env authority (AC-F1).
    env = _make_merge_env()
    with _ephemeral_merge_driver_activation(repo_root):
        merge = subprocess.run(
            [
                "git",
                "merge",
                "--no-edit",
                "-m",
                f"Merge recorded planning-artifact commit into {lane_id} (FR-009)",
                planning_commit_sha,
            ],
            cwd=str(worktree_path),
            capture_output=True,
            text=True,
            env=env,
        )
    if merge.returncode != 0:
        # #4889 T006: capture the WP-task-file diagnostic BEFORE aborting --
        # the conflict markers only exist in ``merge.stdout`` while the merge
        # is still open.
        wp_task_conflicts = _wp_task_file_conflict_paths(merge.stdout)
        subprocess.run(
            ["git", "merge", "--abort"],
            cwd=str(worktree_path),
            capture_output=True,
            text=True,
            env=env,
        )
        raise PlanningCommitMergeConflictError(lane_id, planning_commit_sha, wp_task_conflicts=wp_task_conflicts)


def _ordered_dependency_lanes(
    lane: ExecutionLane,
    lanes_manifest: LanesManifest,
) -> list[ExecutionLane]:
    """Resolve a lane's ``depends_on_lanes`` ids to lane objects, in merge order.

    Ordered by ``(parallel_group, lane_id)`` — the same topological order
    ``compute_lanes`` sorts lanes into and that ``merge`` consumes — so multiple
    dependency tips are merged deterministically from the earliest group up.

    Dependency lane ids that do not resolve to a lane in the manifest are
    skipped (defensive — ``compute_lanes`` only emits real lane ids).
    """
    by_id = {dep_lane.lane_id: dep_lane for dep_lane in lanes_manifest.lanes}
    resolved = [by_id[dep_id] for dep_id in lane.depends_on_lanes if dep_id in by_id]
    return sorted(resolved, key=lambda dep: (dep.parallel_group, dep.lane_id))


def _create_branch_from(
    repo_root: Path,
    branch: str,
    parent: str,
    *,
    label: str = "branch",
) -> None:
    """Create ``branch`` pointing at ``parent`` (no worktree), or raise.

    ``label`` only tunes the error wording (``"branch"`` vs ``"mission
    branch"``) so callers keep their historical messages.
    """
    result = subprocess.run(
        ["git", "branch", branch, parent],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to create {label} {branch} from {parent}: {result.stderr.strip()}")


def _current_head(worktree_path: Path) -> str | None:
    """Return the commit SHA at ``worktree_path``'s HEAD, or ``None``.

    Used to snapshot a lane worktree's ref before the dependency-merge loop so
    a later-dependency conflict can roll the lane back atomically (#1915). On an
    unborn HEAD or any git failure we return ``None`` and the caller skips the
    reset — there is no committed state to preserve.
    """
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"],
        cwd=str(worktree_path),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    head = result.stdout.strip()
    return head or None


def _merge_dependency_lane_tips(
    repo_root: Path,
    worktree_path: Path,
    mission_slug: str,
    lane: ExecutionLane,
    lanes_manifest: LanesManifest,
) -> None:
    """Merge each dependency lane's tip into ``worktree_path`` (issue #1684).

    For every lane in ``lane.depends_on_lanes`` (resolved in ``parallel_group``
    then ``lane_id`` order), resolve its branch through the canonical
    :func:`lane_branch_name` grammar — never a name-guessing f-string — and
    ``git merge`` its tip into the dependent lane's worktree. This is what
    propagates an approved sibling lane's committed code into the lane that
    depends on it.

    Semantics:

    * **Idempotent.** A dep tip already contained in HEAD is an ancestor and is
      skipped (no empty merge commit, no-op on the reuse path).
    * **Missing branch → warn + skip.** A dependency lane that was
      merged-and-deleted post-mission no longer resolves; we emit a warning and
      fall back to the existing base rather than crashing (mirrors the
      ``--base main`` recovery surface).
    * **Conflict → fail closed AND atomic (#1915).** A merge that cannot
      auto-resolve is aborted (``git merge --abort``) and the lane is then reset
      hard to the ref recorded BEFORE the loop, so no *earlier* clean dep merge
      survives a *later* dep conflict. Without this, ``git merge --abort`` only
      undoes the conflicting merge, orphaning a partially-propagated state the
      operator never asked for. The whole multi-dep loop is all-or-nothing.

    FR-008 (#3571): an explicit ``base`` is threaded into
    :func:`allocate_lane_worktree` as its own parameter (never smuggled
    through ``lanes_manifest.mission_branch``) and selects the *root* a
    fresh **no-dependency** lane branches from (D1) — this function only
    ever runs for such lanes, because a dependency-bearing lane combined
    with an explicit ``base`` fails loud before creation
    (:class:`UnhonorableBaseError`, FR-009/D2) rather than merging a
    coord-descended dependency tip on top of a base-alone lane.
    """
    ordered = _ordered_dependency_lanes(lane, lanes_manifest)
    if not ordered:
        return
    # #2709/#2711 self-heal: same rationale as
    # ``_merge_recorded_planning_commit`` above — a both-sides-divergent
    # ``kitty-specs/**`` bookkeeping file must reconcile via its custom merge
    # driver, not produce a plain-3-way-merge conflict. #4120 extends the same
    # fix to the attribute-mapping half: the driver definitions alone are inert
    # when the lane worktree's tree carries no committed ``.gitattributes``
    # mapping (see ``_merge_recorded_planning_commit``'s #4120 note), so the
    # whole dep-merge loop runs inside the ephemeral driver activation —
    # seeded before the first merge, torn down after the last (never persisted
    # into a later ``auto_rebase``, the #2709/#2711 regression).
    # Issue #87: same rationale as ``_merge_recorded_planning_commit`` — the
    # drivers fire inside this merge and resolve ``spec-kitty`` by name, so
    # route the env through the pipeline's single authority (AC-F1) instead
    # of inheriting whatever PATH the caller happens to have.
    env = _make_merge_env()
    # Snapshot the lane ref before the loop so a later-dep conflict can roll
    # the worktree back to its exact pre-merge HEAD (#1915 atomicity).
    pre_loop_ref = _current_head(worktree_path)
    with _ephemeral_merge_driver_activation(repo_root):
        for dep_lane in ordered:
            dep_branch = lane_branch_name(mission_slug, dep_lane.lane_id)
            if not _branch_exists(repo_root, dep_branch):
                # Merged-and-deleted (or never-started) dependency lane: fall back
                # to the existing base. Do not crash, do not silently swallow —
                # surface a warning so the operator can use --base if needed.
                print(
                    f"WARNING: dependency lane {dep_lane.lane_id!r} branch "
                    f"{dep_branch!r} does not resolve; lane {lane.lane_id!r} will "
                    f"not contain its tip (it may have been merged-and-deleted). "
                    f"If you need its code, re-run with an explicit --base."
                )
                continue
            # Already an ancestor of HEAD? Then it is already merged — skip so we
            # do not create a redundant merge commit (idempotent reuse-path).
            is_ancestor = subprocess.run(
                ["git", "merge-base", "--is-ancestor", dep_branch, "HEAD"],
                cwd=str(worktree_path),
                capture_output=True,
                text=True,
            )
            if is_ancestor.returncode == 0:
                continue
            merge = subprocess.run(
                [
                    "git",
                    "merge",
                    "--no-edit",
                    "-m",
                    f"Merge dependency lane {dep_lane.lane_id} into {lane.lane_id}",
                    dep_branch,
                ],
                cwd=str(worktree_path),
                capture_output=True,
                text=True,
                env=env,
            )
            if merge.returncode != 0:
                # Fail closed AND atomic (#1915): abort the half-merge, then reset
                # hard to the pre-loop ref so no EARLIER clean dep merge survives
                # this LATER conflict. The worktree is left exactly as it was before
                # the loop began — clean, for the operator's manual merge.
                subprocess.run(
                    ["git", "merge", "--abort"],
                    cwd=str(worktree_path),
                    capture_output=True,
                    text=True,
                    env=env,
                )
                if pre_loop_ref is not None:
                    subprocess.run(
                        ["git", "reset", "--hard", pre_loop_ref],
                        cwd=str(worktree_path),
                        capture_output=True,
                        text=True,
                    )
                raise DependencyLaneMergeConflictError(lane.lane_id, dep_lane.lane_id, dep_branch)


def _register_sparse_checkout_if_coord(
    worktree_path: Path,
    mission_slug: str,
    coordination_branch: str | None,
    short_id: str | None,
) -> None:
    """Register the status-files sparse-checkout exclusion, if applicable.

    #2514 (WP04): the single call site for the coord-topology sparse-checkout
    guard — both the fresh-create path and the crash-recovery path
    (:func:`allocate_lane_worktree`) route through here instead of
    maintaining two independently-drifting copies of the same guard. A
    recovered coord-topology lane worktree must not re-leak
    ``status.events.jsonl`` / ``status.json`` any more than a freshly-created
    one does.

    Both guards are preserved exactly as explicit ``is not None`` checks
    (never weakened to implicit truthiness): ``coordination_branch`` is
    ``None`` for legacy (no-coord) missions, and ``short_id`` is ``None``
    when ``resolve_mid8`` declines to resolve a mid8. Either ``None`` makes
    this a no-op — byte-identical to the pre-WP04 non-coord path.
    """
    if coordination_branch is not None and short_id is not None:
        register_lane_sparse_checkout(worktree_path, mission_slug, short_id)


def _read_coordination_branch(
    repo_root: Path,
    mission_slug: str,
) -> str | None:
    """Return the ``coordination_branch`` field from ``meta.json``.

    Returns ``None`` for legacy missions (no field, or no meta.json).

    The meta.json is in the main checkout under
    ``kitty-specs/<mission_slug>/meta.json`` — the same place WP03's
    mission_create writes it.
    """
    # FR-001 (#2185): this is the chicken-and-egg coord discovery — it reads
    # ``meta.json`` (PRIMARY_METADATA, PRIMARY-partition) to *discover* whether the
    # mission routes through a coordination branch. The kind-aware seam is
    # topology-blind for PRIMARY kinds, so it correctly anchors on the PRIMARY
    # checkout where ``meta.json`` lives post-#2106 (the coord husk has none / a
    # STATUS-only one) — never the coord-aware resolver (which would need the very
    # answer this read produces).
    meta_dir = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.PRIMARY_METADATA)
    data = load_meta(meta_dir, on_malformed="none")
    if data is None:
        return None
    value = data.get("coordination_branch")
    if isinstance(value, str) and value:
        return value
    return None


def _ensure_branch_exists(
    repo_root: Path,
    branch: str,
    fallback_parent: str,
) -> None:
    """Create ``branch`` from ``fallback_parent`` if it does not exist.

    Used for the coordination-branch path: WP03 normally creates the
    coordination branch at ``mission create`` time, but legacy
    upgrade-in-place projects may still hit this code path with the
    branch missing. We defensively recreate from the target branch
    rather than crashing.
    """
    if _branch_exists(repo_root, branch):
        return
    _create_branch_from(repo_root, branch, fallback_parent)


def _validate_worktree_clean(worktree_path: Path, lane_id: str) -> None:
    """Fail if the worktree has uncommitted changes.

    This prevents a WP from inheriting dirty state from a prior WP
    in the same lane.
    """
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(worktree_path),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git status failed in {worktree_path}: {result.stderr.strip()}")
    if result.stdout.strip():
        raise DirtyWorktreeError(f"Lane {lane_id} worktree at {worktree_path} has uncommitted changes. Commit or stash before starting the next WP.")


def _ensure_mission_branch(
    repo_root: Path,
    mission_branch: str,
    target_branch: str,
) -> None:
    """Create the mission integration branch if it doesn't exist.

    The mission branch is created from the target branch (e.g., main).
    It is a regular branch, not backed by a worktree.
    """
    if _branch_exists(repo_root, mission_branch):
        return
    _create_branch_from(
        repo_root,
        mission_branch,
        target_branch,
        label="mission branch",
    )


def _create_lane_worktree(
    repo_root: Path,
    worktree_path: Path,
    branch: str,
    base_branch: str,
) -> None:
    """Create a git worktree for a lane branch."""
    worktree_path.parent.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        ["git", "worktree", "add", "-b", branch, str(worktree_path), base_branch],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to create lane worktree at {worktree_path}: {result.stderr.strip()}")


def _recover_lane_worktree(
    repo_root: Path,
    worktree_path: Path,
    existing_branch: str,
) -> None:
    """Recreate worktree from existing branch (recovery mode).

    Uses ``git worktree add <path> <branch>`` WITHOUT ``-b`` to attach
    to an already-existing branch. This is the recovery path for when
    the agent process crashed and the branch survived but the worktree
    was lost.

    Raises:
        RuntimeError: If the git worktree add command fails.
    """
    worktree_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["git", "worktree", "add", str(worktree_path), existing_branch],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to recover worktree at {worktree_path}: {result.stderr.strip()}")


def _remove_lane_worktree(repo_root: Path, worktree_path: Path) -> None:
    """Remove a just-created lane worktree (fresh-path atomicity, FR-006/#3281/T010).

    Sibling to :func:`_create_lane_worktree` / :func:`_recover_lane_worktree`.
    Used ONLY on a fresh-path :func:`_merge_recorded_planning_commit` conflict:
    that merge helper already aborts the half-merge (the worktree's tree is
    clean, never left conflicted) before raising, so a targeted
    ``git worktree remove`` is enough — no heavy rollback machinery is built
    here (deliberately scoped per the post-plan squad's LOW-severity
    disposition for FR-006). ``--force`` is used defensively (e.g. a
    just-registered sparse-checkout config file) even though the tree is
    expected clean.

    Only the WORKTREE registration is removed; the branch is intentionally
    left intact so a retry resolves via :func:`allocate_lane_worktree`'s
    crash-recovery route (branch exists, worktree dir gone) rather than this
    helper duplicating that recovery logic.

    Best-effort: a removal failure is reported to stderr but does not raise
    or shadow the caller's original :class:`PlanningCommitMergeConflictError`
    — leaving a worktree registered is a secondary, recoverable-by-operator
    hygiene concern, never the primary failure this WP fixes.
    """
    result = subprocess.run(
        ["git", "worktree", "remove", "--force", str(worktree_path)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"Warning: failed to remove leftover lane worktree {worktree_path} after a planning-commit merge conflict: {result.stderr.strip()}")
