"""orchestrator-api work-package lifecycle verbs (#5628).

``resolve-workspace``, ``start-implementation``, ``start-review``,
``transition`` and ``append-history``. Registered on the app by
``commands.py``.
"""

from __future__ import annotations

import json
import uuid
from kernel.clock import now_utc_stamp
from pathlib import Path
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, NoReturn

if TYPE_CHECKING:
    from specify_cli.lanes.models import ExecutionLane, LanesManifest

import typer

from specify_cli.core.contract_gate import validate_outbound_payload
from specify_cli.status import wp_state_for
from specify_cli.status import Lane
from specify_cli.status import ReviewResult
from specify_cli.status import parse_review_result_json

from .envelope import (
    make_envelope,
    parse_and_validate_policy,
    policy_to_dict,
)


from . import _common
from ._common import (
    _HELP_ACTOR,
    _HELP_MISSION_SLUG,
    _HELP_POLICY,
    _emit,
    _fail,
    _parse_policy_or_fail,
    _planning_read_dir,
)


_HELP_WP_ID = "Work package ID"


def _transition_requires_policy(lane: str) -> bool:
    """Return True if transitioning to *lane* requires ``--policy`` metadata.

    A transition requires policy when the target's WPState is neither terminal,
    blocked, nor not-yet-started — i.e. claimed/in_progress/for_review/in_review/
    approved. Note this is intentionally NARROWER than ``WPState.is_run_affecting``
    (which also counts ``planned`` as active): a transition to ``planned`` does not
    require policy. The two are distinct concepts despite the historical shared name
    (#1775 review FSM-7); do not collapse them.
    """
    state = wp_state_for(lane)
    return state.progress_bucket() not in ("not_started", "terminal") and not state.is_blocked


def _fail_wp_not_found(cmd: str, wp: str, mission: str) -> NoReturn:
    """The ONE ``WP_NOT_FOUND`` emission (S1192 5×; locks error-surface parity)."""
    _fail(cmd, "WP_NOT_FOUND", f"Work package '{wp}' not found in {mission}")


def _resolve_wp_file(tasks_dir: Path, wp_id: str) -> Path | None:
    """Locate the task file for a WP, accepting suffixed filenames.

    Checks for an exact match first (WP07.md), then falls back to any
    file whose name starts with '<wp_id>-' (e.g. WP07-adapter-implementations.md).
    Returns the first match found, or None if no file exists.
    """
    exact = tasks_dir / f"{wp_id}.md"
    if exact.exists():
        return exact
    for p in sorted(tasks_dir.glob(f"{wp_id}-*.md")):
        return p
    return None


@dataclass(frozen=True)
class _StartWorkspace:
    """The workspace resolved for a WP at start-implementation.

    For a lane WP (lanes.json present and the WP is assigned to a lane) the lane
    fields are populated and ``workspace_path`` is a real lane worktree. For a
    legacy / non-lane mission (no lanes.json, or a planning-artifact WP) the lane
    fields stay ``None`` and ``workspace_path`` is the historical bare path —
    preserving the prior contract for those missions.
    """

    workspace_path: str
    lane_id: str | None = None
    lane_branch: str | None = None
    lane_base_ref: str | None = None


def _status_execution_mode_for_start_workspace(start_ws: _StartWorkspace | None) -> str:
    """``ResolvedWorkspace.status_execution_mode``'s value for a ``_StartWorkspace`` (#5100 R-10).

    ``None`` (no workspace was resolved -- every topology except single_branch
    for a non-claim transition) stamps ``"worktree"``, exactly as before R-10.

    The orchestrator-api's own workspace resolver (:func:`_resolve_start_workspace`
    / :func:`_resolve_existing_workspace`) returns ``_StartWorkspace``, not a
    :class:`~specify_cli.workspace.context.ResolvedWorkspace` -- so it cannot
    read the property directly. ``is_repo_root_lane`` is duck-typed on any
    object carrying a ``lane_id`` attribute (the same trick ``implement.py``'s
    ``_resolve_execution_lane`` already relies on for ``ResolvedWorkspace``
    itself), so this reuses the ONE canonical repo-root-lane predicate instead
    of re-deriving a second, divergent ``"direct_repo"`` check.
    """
    from specify_cli.lanes.compute import is_repo_root_lane

    return "direct_repo" if start_ws is not None and is_repo_root_lane(start_ws) else "worktree"


def _repo_root_lane_branch(main_repo_root: Path, mission: str, manifest: Any) -> str:
    """Branch a repo-root lane WP executes on (#5100 B1).

    The mission's recorded ``meta.mission_branch`` applies ONLY to a mission whose
    STORED topology is ``single_branch``; in a ``lanes`` / coordination mission a
    repo-root (planning-artifact) WP runs on the target branch. The rule is the
    one :func:`mission_runtime.resolve_single_branch_write_ref` -- never
    ``manifest.mission_branch``, a stale copy after a protected landing clears
    the meta field.
    """
    from mission_runtime import resolve_single_branch_write_ref

    return resolve_single_branch_write_ref(main_repo_root, mission, str(manifest.target_branch))


def _lane_base_ref(main_repo_root: Path, mission: str, manifest: object) -> str:
    """Back-compat delegator to the hoisted single base-ref authority.

    The lane-base resolution now lives with the shared ``for_review`` gate
    (:func:`specify_cli.lanes.for_review_gate.resolve_lane_base_ref`) so the gate
    leaf and this surface's workspace resolvers consult ONE implementation. Kept
    as a module-level name for the two workspace resolvers below (and existing
    callers) that already reference it.
    """
    from specify_cli.lanes.for_review_gate import resolve_lane_base_ref

    base_ref: str = resolve_lane_base_ref(main_repo_root, mission, manifest)
    return base_ref


def _enforce_claim_ancestry(
    cmd: str,
    main_repo_root: Path,
    mission: str,
    mission_dir: Path,
    wp: str,
    workspace_path: Path,
) -> None:
    """POST-materialize claim-ancestry gate (C-WP03/FR-007/C-005) -- the ONE
    call site shared by both of THIS module's claim paths
    (``start_implementation``'s composite and ``transition``'s raw
    ``--to claimed``), boundary-leak fix: the allocator's reuse-path self-heal
    already reached ``orchestrator_api`` via ``_resolve_start_workspace``
    (always calls ``allocate_lane_worktree``), but the ancestry GATE did not.

    Delegates the predicate + self-heal-retry contract to
    :func:`specify_cli.lanes.implement_support.resolve_claim_ancestry_gate` --
    the same shared helper the CLI seam (``workflow.py``'s ``implement()``)
    calls -- so this module and the CLI can never independently diverge on
    the ancestry decision. Fails with the structured ``ANCESTRY_NOT_ESTABLISHED``
    envelope (never a bare exception) so an external orchestrator gets the
    same contract every other claim-time refusal here already provides.
    """
    from specify_cli.lanes.implement_support import resolve_claim_ancestry_gate

    result = resolve_claim_ancestry_gate(main_repo_root, mission, mission_dir, wp, workspace_path)
    if result.ok:
        return
    _fail(
        cmd,
        "ANCESTRY_NOT_ESTABLISHED",
        (f"cannot claim {wp}: ancestry could not be established after self-heal for: {', '.join(result.missing_refs)}"),
        {
            **_common._mission_identity_payload(mission_dir),
            "wp_id": wp,
            "missing_refs": list(result.missing_refs),
        },
    )


def _lane_assignment_or_legacy(main_repo_root: Path, mission: str, wp: str) -> tuple[LanesManifest, ExecutionLane] | _StartWorkspace:
    """Shared prologue of the two workspace resolvers (ONE fallback grammar).

    Returns the ``(manifest, lane)`` pair when ``wp`` is lane-assigned;
    otherwise the legacy bare-path ``_StartWorkspace`` — the WP-based worktree
    form ``{mission}-{wp}`` with no mid8 (the seam reproduces the historical
    name byte-identically since lane naming takes no Mission identity input,
    WP07) — so legacy / non-lane missions keep working unchanged.

    lanes.json is PRIMARY-partition — read from the primary surface (#2118).
    SSOT: this is the ONLY place this surface decides lane-vs-legacy; a future
    fallback-grammar change is a single edit.
    """
    from specify_cli.lanes.branch_naming import worktree_path as _wt_path
    from specify_cli.lanes.persistence import read_lanes_json

    manifest = read_lanes_json(_planning_read_dir(main_repo_root, mission))
    lane = manifest.lane_for_wp(wp) if manifest is not None else None
    if manifest is None or lane is None:
        return _StartWorkspace(workspace_path=str(_wt_path(main_repo_root, mission, lane_id=wp)))
    return manifest, lane


def _ensure_repo_root_checkout_or_fail(cmd: str, main_repo_root: Path, mission: str, mission_dir: Path, wp: str) -> None:
    """Run ``implement``'s WRITE_CHECKOUT_* refusals for a repo-root lane (#5100 B5)."""
    from kernel.errors import GuardedReadError
    from specify_cli.core.errors import StructuredError
    from specify_cli.lanes.implement_support import _ensure_repo_root_checkout_available
    from specify_cli.workspace.context import resolve_workspace_for_wp

    try:
        resolved = resolve_workspace_for_wp(main_repo_root, mission, wp)
        _ensure_repo_root_checkout_available(main_repo_root, mission, wp, resolved)
    except StructuredError as exc:
        _fail(cmd, exc.error_code, str(exc), {**_common._mission_identity_payload(mission_dir), "wp_id": wp, **exc.to_dict()})
    except (ValueError, FileNotFoundError, GuardedReadError) as exc:
        # The resolver's real failure set: unusable WP metadata / a WP outside
        # every lane (ValueError), a missing WP file (FileNotFoundError), and
        # the typed corrupt/missing lanes.json + meta reads (GuardedReadError).
        _fail(cmd, "LANE_ALLOCATION_FAILED", str(exc), {**_common._mission_identity_payload(mission_dir), "wp_id": wp, "reason": str(exc)})


def _resolve_start_workspace(cmd: str, main_repo_root: Path, mission: str, mission_dir: Path, wp: str) -> _StartWorkspace:
    """Resolve (allocating if needed) the workspace for ``wp``.

    When the mission has a lanes manifest and ``wp`` is assigned to a lane, this
    mirrors spec-kitty's native implement flow: it allocates (or reuses) the lane
    worktree on its lane branch — parented on the coordination branch, with
    approved dependency-lane tips merged into the base — so ``merge-mission`` has
    a real lane branch to integrate and dependent WPs see their dependencies'
    code. Idempotent: re-invoking reuses the existing lane worktree and re-merges
    any newly-approved dependency tips.

    When there is no lanes.json (legacy / non-lane missions) or ``wp`` is not in
    any lane (planning-artifact WP), it falls back to the historical bare-path
    behaviour (via :func:`_lane_assignment_or_legacy`) so those missions keep
    working unchanged.

    A genuine allocation failure for a lane WP (dirty reuse, dependency-merge
    conflict) fails closed with ``LANE_ALLOCATION_FAILED``.
    """
    assignment = _lane_assignment_or_legacy(main_repo_root, mission, wp)
    if isinstance(assignment, _StartWorkspace):
        return assignment
    manifest, lane = assignment

    from specify_cli.lanes.compute import is_repo_root_lane

    if is_repo_root_lane(lane):
        # Repo-root lane: the WP executes directly in the write checkout,
        # never a ``.worktrees/…`` path — ``allocate_lane_worktree`` /
        # ``predict_lane_worktree`` refuse the planning lane id (#5100,
        # T009). Record the claim base ONCE (idempotent-by-absence) so the
        # for_review gate has a starting point (WP02/T007).
        from specify_cli.lanes.claim_base import record_claim_base

        # #5100 B5: the single_branch write-checkout refusals (wrong branch /
        # occupied / dirty) run on this path too, so sequential execution cannot
        # be bypassed by driving the orchestrator API instead of ``implement``.
        _ensure_repo_root_checkout_or_fail(cmd, main_repo_root, mission, mission_dir, wp)
        record_claim_base(main_repo_root, main_repo_root, mission, wp)
        return _StartWorkspace(
            workspace_path=str(main_repo_root),
            lane_id=lane.lane_id,
            lane_branch=_repo_root_lane_branch(main_repo_root, mission, manifest),
            lane_base_ref=_lane_base_ref(main_repo_root, mission, manifest),
        )

    from specify_cli.lanes.worktree_allocator import (
        DependencyLaneMergeConflictError,
        DirtyWorktreeError,
        LaneNotFoundError,
        UnhonorableBaseError,
        allocate_lane_worktree,
    )

    try:
        worktree_path, lane_branch = allocate_lane_worktree(
            repo_root=main_repo_root,
            mission_slug=mission,
            wp_id=wp,
            lanes_manifest=manifest,
        )
    except (
        LaneNotFoundError,
        DirtyWorktreeError,
        DependencyLaneMergeConflictError,
        UnhonorableBaseError,
        RuntimeError,
    ) as exc:
        # NFR-004: a StructuredError refusal (UnhonorableBaseError,
        # DestroyedLaneError) carries a machine-readable error_code (and
        # route/wp_id/base, or lane_id/branch_name/next_step) via to_dict() —
        # merge it into the data payload so a caller can branch on
        # data["error_code"] == "UNHONORABLE_BASE" / "DESTROYED_LANE" rather
        # than substring-matching the message (#4889: the destroyed-lane P0
        # exists to protect this orchestrator caller, so its structured fields
        # must reach it, not just str(exc)). The top-level envelope error_code
        # stays "LANE_ALLOCATION_FAILED" (the generic allocation-failure
        # surface). The plain-RuntimeError members of this tuple lack to_dict(),
        # so `hasattr` leaves their payload untouched.
        _fail(
            cmd,
            "LANE_ALLOCATION_FAILED",
            str(exc),
            # #2512: include the refusal reason in the data payload so the
            # orchestrator can surface a diagnostic without parsing the envelope
            # message string.  The message field already carries str(exc) but is
            # not structurally queryable; "reason" makes the cause machine-readable.
            {
                **_common._mission_identity_payload(mission_dir),
                "wp_id": wp,
                "reason": str(exc),
                **(exc.to_dict() if hasattr(exc, "to_dict") else {}),
            },
        )

    # _fail is NoReturn (always raises typer.Exit), so this is reached only on the
    # success path, where worktree_path / lane_branch are bound.
    return _StartWorkspace(
        workspace_path=str(worktree_path),
        lane_id=lane.lane_id,
        lane_branch=lane_branch,
        lane_base_ref=_lane_base_ref(main_repo_root, mission, manifest),
    )


def _resolve_existing_workspace(main_repo_root: Path, mission: str, wp: str) -> _StartWorkspace:
    """Read-only companion of :func:`_resolve_start_workspace` (#2337).

    Resolves the WP's lane ``workspace_path`` + ``lane_branch`` for its EXISTING
    lane via the canonical naming seams (``lane_branch_name`` + ``worktree_path``)
    — WITHOUT allocating, creating, validating-clean, or merging dependency tips.
    Lets a caller obtain the workspace for a WP already past start-implementation
    (e.g. an external orchestrator resuming a ``for_review`` WP) without the
    ``planned->claimed->in_progress`` composite transition start-implementation
    performs. Shares start-implementation's legacy/non-lane fallback via
    :func:`_lane_assignment_or_legacy`, and takes placement from the allocator's
    own :func:`~specify_cli.lanes.worktree_allocator.predict_lane_worktree` seam
    so the read-only mirror can never diverge from what the write authority
    would create.
    """
    from specify_cli.lanes.compute import is_repo_root_lane
    from specify_cli.lanes.worktree_allocator import predict_lane_worktree

    assignment = _lane_assignment_or_legacy(main_repo_root, mission, wp)
    if isinstance(assignment, _StartWorkspace):
        return assignment
    manifest, lane = assignment

    if is_repo_root_lane(lane):
        # Repo-root lane: mirrors _resolve_start_workspace's read side, but
        # this function is read-only (no allocation, no claim-base write).
        return _StartWorkspace(
            workspace_path=str(main_repo_root),
            lane_id=lane.lane_id,
            lane_branch=_repo_root_lane_branch(main_repo_root, mission, manifest),
            lane_base_ref=_lane_base_ref(main_repo_root, mission, manifest),
        )

    worktree_path, lane_branch = predict_lane_worktree(main_repo_root, mission, lane.lane_id)
    return _StartWorkspace(
        workspace_path=str(worktree_path),
        lane_id=lane.lane_id,
        lane_branch=lane_branch,
        lane_base_ref=_lane_base_ref(main_repo_root, mission, manifest),
    )


def _existing_workspace_for_stamp(cmd: str, main_repo_root: Path, mission: str, mission_dir: Path, wp: str) -> _StartWorkspace | None:
    """Existing-lane mirror used ONLY to stamp a status event's ``execution_mode`` (#5100 R-10).

    A repo-root-lane WP exists only in a STORED ``single_branch`` mission, so
    only there does the stamp differ from the historical ``"worktree"``; every
    other topology returns ``None`` (stamp ``"worktree"``) WITHOUT reading
    ``lanes.json`` -- a corrupt manifest must not break a ``--to done`` /
    ``--to approved`` transition on a mission that never needed it. Inside
    single_branch, an unreadable manifest / WP maps to the error envelope, not
    a traceback.
    """
    from kernel.errors import GuardedReadError
    from mission_runtime import is_single_branch, resolve_topology

    if not is_single_branch(resolve_topology(main_repo_root, mission)):
        return None
    try:
        return _resolve_existing_workspace(main_repo_root, mission, wp)
    except (ValueError, FileNotFoundError, GuardedReadError) as exc:
        _fail(cmd, "TRANSITION_REJECTED", str(exc), {**_common._mission_identity_payload(mission_dir), "wp_id": wp, "reason": str(exc)})


def resolve_workspace(
    mission: str = typer.Option(..., "--mission", help=_HELP_MISSION_SLUG),
    wp: str = typer.Option(..., "--wp", help=_HELP_WP_ID),
) -> None:
    """Read-only: resolve a WP's lane workspace_path + prompt_path (+ lane fields).

    Does NOT allocate/create/validate-clean/transition — the read-only companion
    of ``start-implementation`` for a WP already past implementation (e.g. a
    ``for_review`` WP an external orchestrator wants to review on resume, where
    calling start-implementation would wrongly re-transition it). Contract >= 1.2.0.
    """
    cmd = "resolve-workspace"
    main_repo_root = _common._get_main_repo_root()
    mission_dir = _common._resolve_mission_dir_or_fail(cmd, main_repo_root, mission)

    wp_path = _resolve_wp_file(_planning_read_dir(main_repo_root, mission) / "tasks", wp)
    if wp_path is None:
        _fail_wp_not_found(cmd, wp, mission)
        return

    ws = _resolve_existing_workspace(main_repo_root, mission, wp)
    # --mission accepts mission_id / mid8 / slug; the payload's mission_slug is
    # the RESOLVED identity, never the raw selector echoed back.
    data: dict[str, Any] = {
        **_common._mission_identity_payload(mission_dir),
        "wp_id": wp,
        "workspace_path": ws.workspace_path,
        "prompt_path": str(wp_path),
    }
    if ws.lane_id is not None:
        data["lane_id"] = ws.lane_id
        data["lane_branch"] = ws.lane_branch
        data["lane_base_ref"] = ws.lane_base_ref
    validate_outbound_payload(data, "orchestrator_api")
    envelope = make_envelope(command=cmd, success=True, data=data)
    _emit(envelope)


def start_implementation(
    mission: str = typer.Option(..., "--mission", help=_HELP_MISSION_SLUG),
    wp: str = typer.Option(..., "--wp", help=_HELP_WP_ID),
    actor: str = typer.Option(..., "--actor", help=_HELP_ACTOR),
    policy: str = typer.Option(None, "--policy", help=_HELP_POLICY),
) -> None:
    """Composite transition: planned->claimed->in_progress (idempotent)."""
    cmd = "start-implementation"

    # Policy required
    if not policy:
        _fail(cmd, "POLICY_METADATA_REQUIRED", "--policy is required for start-implementation")
        return

    policy_dict = _parse_policy_or_fail(cmd, policy)

    main_repo_root = _common._get_main_repo_root()
    mission_dir = _common._resolve_mission_dir_or_fail(cmd, main_repo_root, mission)

    wp_path = _resolve_wp_file(_planning_read_dir(main_repo_root, mission) / "tasks", wp)
    if wp_path is None:
        _fail_wp_not_found(cmd, wp, mission)
        return

    from specify_cli.core.dependency_graph import dependency_readiness_for_wp, parse_wp_dependencies
    from specify_cli.status import reduce
    from specify_cli.status import read_events

    # Reduce once off the same (coord-aware) status surface the lane map already
    # reads, so the provenance map threaded into the gate is consistent with the
    # lanes it decides against.
    _snapshot = reduce(read_events(mission_dir))
    wp_lanes = {wp_id: state.get("lane", Lane.PLANNED) for wp_id, state in _snapshot.work_packages.items()}
    # Only gate the not-yet-started claim transition. Re-invoking start-implementation
    # on a WP that is already in_progress/for_review/.../approved is a no-op resume
    # in the lifecycle layer and must not be rejected just because a dependency later
    # regressed out of approved/done.
    _self_lane = wp_state_for(wp_lanes.get(wp, Lane.PLANNED)).lane
    if _self_lane in (Lane.PLANNED, Lane.CLAIMED):
        # Thread per-dependency provenance (FR-009): start-implementation is the
        # external-API CLAIM gate (mutating planned→claimed→in_progress), the
        # equivalent of implement.py's `_ensure_wp_claim_preconditions`. Without
        # this a dependent of a canceled-with-operator-provenance WP reproduces
        # the #2945 strand on the orchestrator-api claim path.
        # Pre-flight UX only (FR-014, fsm-write-path-integrity WP04). The authoritative
        # dependency gate is `GuardContext.dependency_ready`, resolved in-lock by the emit shells.
        dependency_readiness = dependency_readiness_for_wp(
            wp,
            parse_wp_dependencies(wp_path),
            wp_lanes,
            provenance=_snapshot.work_packages,
        )
        if not dependency_readiness.satisfied:
            blocked = ", ".join(dependency_readiness.unsatisfied)
            _fail(
                cmd,
                "DEPENDENCIES_NOT_SATISFIED",
                (f"dependencies_not_satisfied: {wp} depends on {blocked}; all dependencies must be approved or done before implementation can start"),
                {
                    **_common._mission_identity_payload(mission_dir),
                    "wp_id": wp,
                    "unsatisfied_dependencies": list(dependency_readiness.unsatisfied),
                },
            )
            return

    from specify_cli.status import TransitionError
    from specify_cli.status import WorkPackageClaimConflict, start_implementation_status

    # Allocate the REAL lane worktree (lane branch + dependency-lane tips merged)
    # when the mission has lanes, mirroring the native implement flow so
    # merge-mission has a lane branch to integrate. Legacy / non-lane missions
    # keep the historical bare path.
    start_ws = _resolve_start_workspace(cmd, main_repo_root, mission, mission_dir, wp)
    workspace_path = start_ws.workspace_path
    prompt_path = str(wp_path)
    status_execution_mode = _status_execution_mode_for_start_workspace(start_ws)

    # Seam C-005 (#3281/FR-007): POST-materialize, after allocation/self-heal
    # above, BEFORE the claim transition below emits any status event. Never
    # move this above ``_resolve_start_workspace`` -- see
    # ``_enforce_claim_ancestry``'s docstring for the deadlock hazard.
    _enforce_claim_ancestry(cmd, main_repo_root, mission, mission_dir, wp, Path(workspace_path))

    # #3946 (F-78): a reused lane's persisted workspace context must follow the
    # WP that just claimed it, exactly as the native ``implement`` flow refreshes
    # it via the same helper — otherwise every later lane commit warns
    # ACTIVE_WP_CONTEXT_STALE and the guard scopes against the prior WP. No-op
    # when the lane has no context (an orchestrator-driven mission never created
    # one; that shape is unchanged). ``mission_dir.name`` is the canonical
    # mission directory name the native flow saves the context under.
    from specify_cli.lanes.implement_support import refresh_reused_lane_context

    refresh_reused_lane_context(
        main_repo_root,
        mission_dir.name,
        start_ws.lane_id,
        wp,
        parse_wp_dependencies(wp_path),
    )

    try:
        start_result = start_implementation_status(
            feature_dir=mission_dir,
            mission_slug=mission,
            wp_id=wp,
            actor=actor,
            workspace_context=workspace_path,
            execution_mode=status_execution_mode,
            repo_root=main_repo_root,
            policy_metadata=policy_dict,
        )
    except WorkPackageClaimConflict as exc:
        _fail(
            cmd,
            "WP_ALREADY_CLAIMED",
            str(exc),
            {
                **_common._mission_identity_payload(mission_dir),
                "claimed_by": exc.claimed_by,
                "requesting_actor": exc.requesting_actor,
            },
        )
        return
    except TransitionError as exc:
        _fail(cmd, "TRANSITION_REJECTED", str(exc))
        return

    data = {
        **_common._mission_identity_payload(mission_dir),
        "wp_id": wp,
        "from_lane": start_result.from_lane,
        "to_lane": Lane.IN_PROGRESS,
        "workspace_path": workspace_path,
        "prompt_path": prompt_path,
        "policy_metadata_recorded": True,
        "no_op": start_result.no_op,
    }
    if start_ws.lane_id is not None:
        # Lane WP: carry the lane identity the orchestrator needs to commit and
        # gate. Omitted for legacy / non-lane missions (unchanged contract).
        data["lane_id"] = start_ws.lane_id
        data["lane_branch"] = start_ws.lane_branch
        data["lane_base_ref"] = start_ws.lane_base_ref
    validate_outbound_payload(data, "orchestrator_api")
    envelope = make_envelope(
        command=cmd,
        success=True,
        data=data,
    )
    _emit(envelope)


# ── Command 5: start-review ────────────────────────────────────────────────


def start_review(
    mission: str = typer.Option(..., "--mission", help=_HELP_MISSION_SLUG),
    wp: str = typer.Option(..., "--wp", help=_HELP_WP_ID),
    actor: str = typer.Option(..., "--actor", help=_HELP_ACTOR),
    policy: str = typer.Option(None, "--policy", help=_HELP_POLICY),
    review_ref: str = typer.Option(None, "--review-ref", help="Review feedback reference (optional, not required for for_review→in_review)"),
) -> None:
    """Transition a WP from for_review to in_review (reviewer claims review)."""
    cmd = "start-review"

    if not policy:
        _fail(cmd, "POLICY_METADATA_REQUIRED", "--policy is required for start-review")
        return

    try:
        policy_obj = parse_and_validate_policy(policy)
    except ValueError as exc:
        _fail(cmd, "POLICY_VALIDATION_FAILED", str(exc))
        return

    policy_dict = policy_to_dict(policy_obj)

    main_repo_root = _common._get_main_repo_root()
    mission_dir = _common._resolve_mission_dir_or_fail(cmd, main_repo_root, mission)

    wp_path = _resolve_wp_file(_planning_read_dir(main_repo_root, mission) / "tasks", wp)
    if wp_path is None:
        _fail_wp_not_found(cmd, wp, mission)
        return

    from specify_cli.status import TransitionError
    from specify_cli.status import WorkPackageClaimConflict, start_review_status

    prompt_path = str(wp_path)
    # #5100 R-10: read-only mirror of the WP's EXISTING lane assignment (no
    # allocation) -- start-review runs after implementation, so the WP is
    # already lane-assigned; this is the honest stamp, not a hardcoded guess.
    review_ws = _existing_workspace_for_stamp(cmd, main_repo_root, mission, mission_dir, wp)

    try:
        start_result = start_review_status(
            feature_dir=mission_dir,
            mission_slug=mission,
            wp_id=wp,
            actor=actor,
            review_ref=review_ref,
            workspace_context=f"orchestrator-api:{main_repo_root}",
            execution_mode=_status_execution_mode_for_start_workspace(review_ws),
            repo_root=main_repo_root,
            policy_metadata=policy_dict,
        )
    except WorkPackageClaimConflict as exc:
        _fail(
            cmd,
            "WP_ALREADY_CLAIMED",
            str(exc),
            {
                **_common._mission_identity_payload(mission_dir),
                "claimed_by": exc.claimed_by,
                "requesting_actor": exc.requesting_actor,
            },
        )
        return
    except TransitionError as exc:
        _fail(cmd, "TRANSITION_REJECTED", str(exc))
        return

    data = {
        **_common._mission_identity_payload(mission_dir),
        "wp_id": wp,
        "from_lane": start_result.from_lane,
        "to_lane": Lane.IN_REVIEW,
        "prompt_path": prompt_path,
        "policy_metadata_recorded": True,
        "no_op": start_result.no_op,
    }
    validate_outbound_payload(data, "orchestrator_api")
    envelope = make_envelope(
        command=cmd,
        success=True,
        data=data,
    )
    _emit(envelope)


# ── Command 6: transition ──────────────────────────────────────────────────


def _enforce_for_review_commit_gate(cmd: str, main_repo_root: Path, mission: str, mission_dir: Path, wp: str, force: bool) -> None:
    """Reject an in_progress->for_review transition that has no commit on the lane.

    Thin orchestrator adapter over the shared, surface-neutral gate leaf
    (:func:`specify_cli.lanes.for_review_gate.evaluate_for_review_gate`): the leaf
    decides (returning a :class:`GateDecision`) and THIS surface renders the
    envelope ``_fail`` from that decision. The envelope (``NoReturn``) never
    leaks into the leaf, so ``agent status emit`` (WP09) can consume the same
    gate and render its own CLI error. No-ops when bypassed (``--force``) or when
    the gate does not apply (no lanes.json, or the WP is not in any lane).
    """
    from specify_cli.lanes.for_review_gate import (
        GateDecision,
        evaluate_for_review_gate,
    )

    decision: GateDecision = evaluate_for_review_gate(main_repo_root, mission, wp, force=force)
    if not decision.passed:
        _fail(
            cmd,
            "TRANSITION_REJECTED",
            decision.reason,
            {
                **_common._mission_identity_payload(mission_dir),
                "wp_id": wp,
                "lane_id": decision.lane_id,
            },
        )


def transition(
    mission: str = typer.Option(..., "--mission", help=_HELP_MISSION_SLUG),
    wp: str = typer.Option(..., "--wp", help=_HELP_WP_ID),
    to: str = typer.Option(..., "--to", help="Target lane"),
    actor: str = typer.Option(..., "--actor", help=_HELP_ACTOR),
    note: str = typer.Option(None, "--note", help="Reason/note for the transition"),
    policy: str = typer.Option(None, "--policy", help="Policy metadata JSON (required for run-affecting lanes)"),
    force: bool = typer.Option(False, "--force", help="Force the transition"),
    review_ref: str = typer.Option(None, "--review-ref", help="Review reference"),
    review_result_json: str = typer.Option(
        None,
        "--review-result-json",
        help="JSON structured review outcome for transitions from in_review",
    ),
    evidence_json: str = typer.Option(None, "--evidence-json", help="JSON string with done evidence"),
    subtasks_complete: bool = typer.Option(None, "--subtasks-complete", help="Whether required subtasks are complete for in_progress->for_review"),
    implementation_evidence_present: bool = typer.Option(
        None, "--implementation-evidence-present", help="Whether implementation evidence exists for in_progress->for_review"
    ),
) -> None:
    """Emit a single lane transition for a WP."""
    cmd = "transition"

    from specify_cli.status import resolve_lane_alias

    to_lane = resolve_lane_alias(to)

    # Policy required for transitions into active-execution lanes (not planned).
    policy_dict: dict[str, Any] | None = None
    if _transition_requires_policy(to_lane):
        if not policy:
            _fail(
                cmd,
                "POLICY_METADATA_REQUIRED",
                f"--policy is required when transitioning to '{to_lane}'",
            )
            return
        policy_dict = _parse_policy_or_fail(cmd, policy)
    elif policy:
        # Optional policy for non-run-affecting lanes
        policy_dict = _parse_policy_or_fail(cmd, policy)

    evidence: dict[str, Any] | None = None
    if evidence_json is not None:
        try:
            parsed_evidence = json.loads(evidence_json)
        except json.JSONDecodeError as exc:
            _fail(cmd, "USAGE_ERROR", f"Invalid JSON in --evidence-json: {exc}")
            return
        if not isinstance(parsed_evidence, dict):
            _fail(cmd, "USAGE_ERROR", "--evidence-json must decode to a JSON object")
            return
        evidence = parsed_evidence

    review_result: ReviewResult | None = None
    if review_result_json is not None:
        try:
            review_result = parse_review_result_json(review_result_json)
        except ValueError as exc:
            _fail(cmd, "USAGE_ERROR", str(exc))
            return

    main_repo_root = _common._get_main_repo_root()
    mission_dir = _common._resolve_mission_dir_or_fail(cmd, main_repo_root, mission)

    wp_path = _resolve_wp_file(_planning_read_dir(main_repo_root, mission) / "tasks", wp)
    if wp_path is None:
        _fail_wp_not_found(cmd, wp, mission)
        return

    if to_lane == Lane.FOR_REVIEW:
        _enforce_for_review_commit_gate(cmd, main_repo_root, mission, mission_dir, wp, force)
        transition_ws = _existing_workspace_for_stamp(cmd, main_repo_root, mission, mission_dir, wp)
    elif to_lane == Lane.CLAIMED:
        # Seam C-005 (#3281/FR-007): early-return-equivalent for every OTHER
        # target lane -- this predicate only ever runs for a raw `--to
        # claimed` transition. Allocates/self-heals the lane workspace
        # (mirrors start_implementation's own `_resolve_start_workspace`
        # call) and enforces ancestry BEFORE the `claimed` event below.
        transition_ws = _resolve_start_workspace(cmd, main_repo_root, mission, mission_dir, wp)
        _enforce_claim_ancestry(cmd, main_repo_root, mission, mission_dir, wp, Path(transition_ws.workspace_path))
    else:
        # #5100 R-10: every other target lane still needs an honest stamp --
        # read-only mirror of the WP's EXISTING lane, no allocation, and only
        # for single_branch (elsewhere the historical "worktree" stamp stands).
        transition_ws = _existing_workspace_for_stamp(cmd, main_repo_root, mission, mission_dir, wp)

    from specify_cli.coordination.status_transition import emit_status_transition_transactional
    from specify_cli.status import TransitionError
    from specify_cli.status import TransitionRequest

    try:
        event = emit_status_transition_transactional(
            TransitionRequest(
                feature_dir=mission_dir,
                mission_slug=mission,
                wp_id=wp,
                to_lane=to_lane,
                actor=actor,
                reason=note,
                force=force,
                evidence=evidence,
                review_ref=review_ref,
                review_result=review_result,
                subtasks_complete=subtasks_complete,
                implementation_evidence_present=implementation_evidence_present,
                execution_mode=_status_execution_mode_for_start_workspace(transition_ws),
                repo_root=main_repo_root,
                policy_metadata=policy_dict,
            ),
        )
    except TransitionError as exc:
        _fail(cmd, "TRANSITION_REJECTED", str(exc))
        return

    # T032 (#5115 review cycle 2, Issue 2): this for_review transition does
    # not always auto-commit, so under a foreign post-commit hook it is
    # otherwise the only chance to record this lane's tip before a later
    # touch. Gated on the RESOLVED event lane (covers --force too). Best-
    # effort: never raises, never fails a transition that already landed.
    if event.to_lane == Lane.FOR_REVIEW:
        from specify_cli.lanes.lane_tip import record_tip_for_wp

        record_tip_for_wp(main_repo_root, mission, wp)

    data = {
        **_common._mission_identity_payload(mission_dir),
        "wp_id": wp,
        "from_lane": str(event.from_lane),
        "to_lane": str(event.to_lane),
        "policy_metadata_recorded": policy_dict is not None,
    }
    validate_outbound_payload(data, "orchestrator_api")
    envelope = make_envelope(
        command=cmd,
        success=True,
        data=data,
    )
    _emit(envelope)


# ── Command 7: append-history ──────────────────────────────────────────────


def append_history(
    mission: str = typer.Option(..., "--mission", help=_HELP_MISSION_SLUG),
    wp: str = typer.Option(..., "--wp", help=_HELP_WP_ID),
    actor: str = typer.Option(..., "--actor", help=_HELP_ACTOR),
    note: str = typer.Option(..., "--note", help="History note to append"),
) -> None:
    """Append a history entry via an ``InnerStateChanged`` ``note`` annotation.

    WP08 / FR-007 / T031: this cross-package (ACL-boundary) writer no longer
    mutates the WP prompt file's ``## Activity Log`` section directly -- it
    emits a ``note``-append delta through WP01's ``emit_inner_state_changed``.
    The write target is the coord-aware STATUS-partition mission directory
    (:func:`_resolve_mission_dir_or_fail` -- the SAME seam every other STATUS
    read/write in this module uses, e.g. ``accept_mission``'s
    ``materialize(mission_dir)``), never a ``Path.cwd()``-derived join
    (C-003 / #2647 -- see the SC-008 test).
    """
    cmd = "append-history"

    main_repo_root = _common._get_main_repo_root()
    # Existence/identity gate via the coord-aware read seam (typed miss
    # envelope). This is also the STATUS-partition mission directory the
    # annotation below is emitted into.
    mission_dir = _common._resolve_mission_dir_or_fail(cmd, main_repo_root, mission)

    # FR-003 / T013: the WP prompt file is a WORK_PACKAGE_TASK (primary kind),
    # so its EXISTENCE is checked on the PRIMARY checkout -- never the
    # coordination worktree (the planning→coord transit is removed, C-005).
    # Resolve it through the canonical per-kind read seam (``_planning_read_dir``
    # → ``resolve_planning_read_dir``, the same seam the sibling planning reads
    # use), NOT a raw handle-blind ``primary_feature_dir_for_mission`` call: that
    # primitive composes the handle verbatim, so a bare ``mid8`` / full ULID /
    # numeric handle would land on a DIVERGENT dir than where the WP prompt
    # actually lives (the #2136/#2164 write/placement divergence). The seam
    # folds the handle to its canonical ``<slug>-<mid8>`` dir for every form
    # (and propagates ``MissionSelectorAmbiguous`` -- no silent pick).
    primary_mission_dir = _planning_read_dir(main_repo_root, mission)
    wp_path = _resolve_wp_file(primary_mission_dir / "tasks", wp)
    if wp_path is None:
        _fail_wp_not_found(cmd, wp, mission)
        return

    from specify_cli.status import WPInnerStateDelta
    from specify_cli.status import StoreError
    from specify_cli.status import emit_inner_state_changed

    timestamp = now_utc_stamp()
    # Byte-identical to the historical rendered Activity Log line (FR-007
    # no-content-loss): the note carries the fully-formatted entry so no
    # information is lost even before a dedicated notes-render surface lands.
    entry_text = f"- [{timestamp}] {actor}: {note}"

    try:
        emit_inner_state_changed(
            mission_dir,
            wp,
            WPInnerStateDelta(note=entry_text),
            actor=actor,
            mission_slug=mission,
            repo_root=main_repo_root,
        )
    except (ValueError, StoreError) as exc:
        # A failed emit still surfaces the orchestrator-api's own structured
        # envelope (never a bare traceback) -- ``_fail`` is typed ``NoReturn``.
        _fail(cmd, "HISTORY_COMMIT_FAILED", str(exc))
        return

    entry_id = "hist-" + uuid.uuid4().hex

    data = {
        **_common._mission_identity_payload(primary_mission_dir),
        "wp_id": wp,
        "history_entry_id": entry_id,
    }
    validate_outbound_payload(data, "orchestrator_api")
    envelope = make_envelope(
        command=cmd,
        success=True,
        data=data,
    )
    _emit(envelope)


# ── Command 8: accept-mission ──────────────────────────────────────────────
