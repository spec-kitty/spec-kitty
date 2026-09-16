"""Shared lifecycle operations for work-package starts.

These helpers are the single status-facing implementation of "start work" for
agent commands, the internal implement command, and orchestrator-api. Workspace
creation stays with the caller; durable lane transitions live here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from specify_cli.status.emit import TransitionError
from specify_cli.status.locking import feature_status_lock
from specify_cli.status.review_claim_predicate import review_claim_decision
from specify_cli.status.models import (
    ActorField,
    Lane,
    StatusEvent,
    TransitionRequest,
    WPInnerStateDelta,
    actor_identity_str,
)
from specify_cli.workspace import canonicalize_feature_dir

#: Placeholder assignee identities written by callers that claim a WP without
#: a real agent identity (``implement-command`` — the internal ``spec-kitty
#: implement`` compat surface's default ``effective_actor`` when invoked
#: without ``--actor``, per its own docstring "compatibility surface for
#: direct callers"; ``unknown`` — a generic fallback elsewhere; ``user`` —
#: ``agent tasks move-task``'s ``st.agent or "user"`` fallback
#: (``tasks_move_task.py::_mt_execute``) when a lane is moved without
#: ``--agent``, e.g. a bare ``move-task WP04 --to in_progress``). None is a
#: real owner, so every ownership check in this module (and, per FIX-M2-03,
#: :mod:`specify_cli.cli.commands.agent.tasks_transition_core`'s
#: ``move-task`` agent-ownership guard) treats a WP whose CURRENT assignee is
#: one of these as unclaimed-in-practice: the first real agent identity to
#: touch it becomes the de facto owner, no ``--force`` required. Without
#: ``user`` here, the #3938 shape — ``move-task WP04 --to in_progress``
#: (actor ``user``) then ``agent action implement WP04 --agent <agent>`` —
#: refused the documented no-op resume with "already claimed for
#: implementation by 'user'" and aborted before the prompt was regenerated.
#: Public (no leading underscore) so both ownership checks share the ONE
#: definition instead of drifting out of sync (the original private
#: ``_GENERIC_IMPLEMENTATION_ACTORS`` spelling here only ever gated the
#: claim/in_progress start path; ``move-task`` silently lacked the same
#: allowance until FIX-M2-03).
GENERIC_IMPLEMENTATION_ACTORS = frozenset({"implement-command", "unknown", "user"})


class WorkPackageClaimConflict(TransitionError):
    """Raised when another actor owns an implementation or review claim."""

    def __init__(
        self,
        wp_id: str,
        claimed_by: str,
        requesting_actor: ActorField,
        *,
        review: bool = False,
    ) -> None:
        kind = "review" if review else "implementation"
        super().__init__(f"WP {wp_id} is already claimed for {kind} by '{claimed_by}'")
        self.wp_id = wp_id
        self.claimed_by = claimed_by
        self.requesting_actor = actor_identity_str(requesting_actor)


class WorkPackageStartRejected(TransitionError):
    """Raised when a WP cannot be started from its current lane."""


@dataclass(frozen=True)
class WorkPackageStartResult:
    """Outcome for an idempotent implementation/review start operation."""

    wp_id: str
    from_lane: Lane
    to_lane: Lane
    actor: ActorField
    events: tuple[StatusEvent, ...]
    no_op: bool = False
    claimed_by: str | None = None

    @property
    def status_changed(self) -> bool:
        return bool(self.events)


def _repo_root_for_lock(feature_dir: Path, repo_root: Path | None) -> Path:
    """Resolve the repo root used for per-feature status locking.

    Thin shim — delegates to the single shared implementation in
    :func:`specify_cli.workspace.root_resolver.resolve_status_lock_root`
    (WP02 / SC-002 consolidation).
    """
    from specify_cli.workspace.root_resolver import resolve_status_lock_root

    return resolve_status_lock_root(feature_dir, repo_root)


def _actor_key(actor: object | None) -> str | None:
    if actor is None:
        return None
    typed_actor = cast(ActorField, actor) if isinstance(actor, (str, dict)) else str(actor)
    value = actor_identity_str(typed_actor).strip()
    return value or None


def _actors_compatible(existing: object | None, requested: object | None, *, allow_generic_existing: bool = False) -> bool:
    existing_key = _actor_key(existing)
    requested_key = _actor_key(requested)
    if existing_key is None or requested_key is None:
        return True
    if existing_key == requested_key:
        return True
    return allow_generic_existing and existing_key in GENERIC_IMPLEMENTATION_ACTORS


def start_implementation_status(
    *,
    feature_dir: Path,
    mission_slug: str,
    wp_id: str,
    actor: ActorField,
    workspace_context: str,
    execution_mode: str,
    repo_root: Path | None = None,
    policy_metadata: dict[str, Any] | None = None,
    ensure_sync_daemon: bool = True,
    allow_rework: bool = False,
    rework_reason: str = "Re-implementing after review feedback",
    annotation_delta: WPInnerStateDelta | None = None,
) -> WorkPackageStartResult:
    """Idempotently move a WP into ``in_progress`` for an implementation actor."""
    # Lazy import breaks the status↔coordination cycle (status/__init__ imports
    # this module; coordination.status_transition imports back into status via
    # coordination.transaction). Deferring to call time lets the facade finish
    # initializing before coordination is touched.
    from specify_cli.coordination.status_transition import (
        emit_status_transition_batch_transactional,
        emit_status_transition_transactional,
        read_current_wp_state_transactional,
    )

    feature_dir = canonicalize_feature_dir(feature_dir)
    lock_root = _repo_root_for_lock(feature_dir, repo_root)

    with feature_status_lock(lock_root, feature_dir.name):
        current = read_current_wp_state_transactional(
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id=wp_id,
            repo_root=repo_root,
        )
        current_lane = current.lane
        current_actor = current.actor

        if current_lane == Lane.GENESIS:
            raise WorkPackageStartRejected(
                f"WP {wp_id} is not finalized; run `spec-kitty agent mission finalize-tasks`"
            )

        if current_lane == Lane.PLANNED:
            events = emit_status_transition_batch_transactional(
                [
                    TransitionRequest(
                        feature_dir=feature_dir,
                        mission_slug=mission_slug,
                        wp_id=wp_id,
                        to_lane=Lane.CLAIMED,
                        actor=actor,
                        execution_mode=execution_mode,
                        repo_root=repo_root,
                        policy_metadata=policy_metadata,
                    ),
                    TransitionRequest(
                        feature_dir=feature_dir,
                        mission_slug=mission_slug,
                        wp_id=wp_id,
                        to_lane=Lane.IN_PROGRESS,
                        actor=actor,
                        workspace_context=workspace_context,
                        execution_mode=execution_mode,
                        repo_root=repo_root,
                        policy_metadata=policy_metadata,
                        annotation_delta=annotation_delta,
                    ),
                ],
                ensure_sync_daemon=ensure_sync_daemon,
            )
            return WorkPackageStartResult(
                wp_id,
                Lane.PLANNED,
                Lane.IN_PROGRESS,
                actor,
                tuple(events),
                claimed_by=actor_identity_str(actor),
            )

        if current_lane == Lane.CLAIMED:
            if not _actors_compatible(current_actor, actor, allow_generic_existing=True):
                raise WorkPackageClaimConflict(wp_id, current_actor or "unknown", actor)
            events = emit_status_transition_batch_transactional(
                [
                    TransitionRequest(
                        feature_dir=feature_dir,
                        mission_slug=mission_slug,
                        wp_id=wp_id,
                        to_lane=Lane.IN_PROGRESS,
                        actor=actor,
                        workspace_context=workspace_context,
                        execution_mode=execution_mode,
                        repo_root=repo_root,
                        policy_metadata=policy_metadata,
                        annotation_delta=annotation_delta,
                    )
                ],
                ensure_sync_daemon=ensure_sync_daemon,
            )
            return WorkPackageStartResult(
                wp_id,
                Lane.CLAIMED,
                Lane.IN_PROGRESS,
                actor,
                tuple(events),
                claimed_by=actor_identity_str(actor),
            )

        if current_lane == Lane.IN_PROGRESS:
            if not _actors_compatible(current_actor, actor, allow_generic_existing=True):
                raise WorkPackageClaimConflict(wp_id, current_actor or "unknown", actor)
            return WorkPackageStartResult(wp_id, Lane.IN_PROGRESS, Lane.IN_PROGRESS, actor, (), no_op=True, claimed_by=current_actor)

        if allow_rework and current_lane in {Lane.FOR_REVIEW, Lane.APPROVED, Lane.IN_REVIEW}:
            event = emit_status_transition_transactional(
                TransitionRequest(
                    feature_dir=feature_dir,
                    mission_slug=mission_slug,
                    wp_id=wp_id,
                    to_lane=Lane.IN_PROGRESS,
                    actor=actor,
                    force=True,
                    reason=rework_reason,
                    workspace_context=workspace_context,
                    execution_mode=execution_mode,
                    repo_root=repo_root,
                    policy_metadata=policy_metadata,
                    annotation_delta=annotation_delta,
                ),
                ensure_sync_daemon=ensure_sync_daemon,
            )
            return WorkPackageStartResult(
                wp_id,
                current_lane,
                Lane.IN_PROGRESS,
                actor,
                (event,),
                claimed_by=actor_identity_str(actor),
            )

    raise WorkPackageStartRejected(f"WP {wp_id} is in '{current_lane}', cannot start implementation")


def start_review_status(
    *,
    feature_dir: Path,
    mission_slug: str,
    wp_id: str,
    actor: ActorField,
    workspace_context: str,
    execution_mode: str,
    repo_root: Path | None = None,
    policy_metadata: dict[str, Any] | None = None,
    ensure_sync_daemon: bool = True,
    review_ref: str | None = "action-review-claim",
    annotation_delta: WPInnerStateDelta | None = None,
) -> WorkPackageStartResult:
    """Idempotently move a WP into ``in_review`` for a reviewer actor."""
    # Lazy import breaks the status↔coordination cycle (see start_implementation_status).
    from specify_cli.coordination.status_transition import (
        emit_status_transition_transactional,
        read_current_wp_state_transactional,
    )

    feature_dir = canonicalize_feature_dir(feature_dir)
    lock_root = _repo_root_for_lock(feature_dir, repo_root)

    with feature_status_lock(lock_root, feature_dir.name):
        current = read_current_wp_state_transactional(
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id=wp_id,
            repo_root=repo_root,
        )
        current_lane = current.lane
        current_actor = current.actor
        current_role = current.role

        if current_lane == Lane.FOR_REVIEW:
            event = emit_status_transition_transactional(
                TransitionRequest(
                    feature_dir=feature_dir,
                    mission_slug=mission_slug,
                    wp_id=wp_id,
                    to_lane=Lane.IN_REVIEW,
                    actor=actor,
                    reason="Started review via action command",
                    review_ref=review_ref,
                    workspace_context=workspace_context,
                    execution_mode=execution_mode,
                    repo_root=repo_root,
                    policy_metadata=policy_metadata,
                    annotation_delta=annotation_delta,
                ),
                ensure_sync_daemon=ensure_sync_daemon,
            )
            return WorkPackageStartResult(
                wp_id,
                Lane.FOR_REVIEW,
                Lane.IN_REVIEW,
                actor,
                (event,),
                claimed_by=actor_identity_str(actor),
            )

        if current_lane == Lane.IN_REVIEW:
            # Role-aware collision (FR-003): the genuine reviewer-vs-reviewer
            # gate. Role rides the in-lock ``CurrentWpState`` read (no split-brain
            # / no guard-path plumbing). Collision is best-effort — a binding-less
            # holder has ``current_role=None`` and degrades to ALLOW. The requester
            # role is part of the symmetric predicate contract but is not consulted.
            requesting_role = actor.get("role") if isinstance(actor, dict) else None
            decision = review_claim_decision(
                current_actor,
                current_role,
                _actor_key(actor),
                requesting_role,
            )
            if decision.is_collision:
                raise WorkPackageClaimConflict(wp_id, decision.holder or "unknown", actor, review=True)
            return WorkPackageStartResult(wp_id, Lane.IN_REVIEW, Lane.IN_REVIEW, actor, (), no_op=True, claimed_by=current_actor)

    raise WorkPackageStartRejected(f"WP {wp_id} is in '{current_lane}', cannot start review")
