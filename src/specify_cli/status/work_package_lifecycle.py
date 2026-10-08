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
from specify_cli.status.models import parse_agent_boundary_string
from specify_cli.status.locking import feature_status_lock
from specify_cli.status.mission_write import mission_lock_key
from specify_cli.status.review_claim_predicate import review_claim_decision
from specify_cli.status.models import (
    FORCE_NOTE_HINT,
    FORCE_NOTE_REQUIRED,
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
#: The placeholder a refusal names when no actor is on record.
_UNKNOWN_ACTOR = "unknown"

GENERIC_IMPLEMENTATION_ACTORS = frozenset({"implement-command", _UNKNOWN_ACTOR, "user"})


class WorkPackageClaimConflict(TransitionError):
    """Raised when another actor owns an implementation or review claim."""

    def __init__(
        self,
        wp_id: str,
        claimed_by: str,
        requesting_actor: ActorField,
        *,
        review: bool = False,
        submitted: bool = False,
    ) -> None:
        if submitted:
            # A for_review WP is a submission, not a claim: say who may withdraw it.
            holder = claimed_by if claimed_by not in ("", _UNKNOWN_ACTOR) else "none on record"
            super().__init__(f"WP {wp_id} is in for_review; only its implementer of record ({holder}) may withdraw it, or an operator with {FORCE_NOTE_HINT}")
        else:
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
    """Project ANY actor representation to the impl-claim comparison key.

    #4665/C-002/C-005: ``actor_identity_str`` (status/models.py, byte-identical
    to the upstream ``spec-kitty-events`` reducer) projects a *dict*
    resolved-binding actor to its bare ``tool``, but returns a compact
    ``tool:model:profile:role`` *string* actor VERBATIM -- the two
    representations of ONE agent then compare unequal and self-conflict
    (#4665). The shared projection stays untouched (C-005); reconciliation
    happens ONLY here, in the CLI-local comparison layer (C-002), by parsing
    a compact-string actor down to its bare tool too, reusing the closed
    #2861 parser (:func:`~specify_cli.status.emit.parse_agent_boundary_string`)
    instead of inventing new parsing. The key stays a bare ``str`` (never a
    tuple/struct, C-002) and role-blind by design -- reviewer-vs-implementer
    distinctness lives on the SEPARATE review-claim role channel
    (``review_claim_predicate.review_claim_decision``), not here. A bare-tool
    string (e.g. ``"codex"`` or a generic placeholder like ``"unknown"``) has
    no ``":"`` and round-trips through the parser unchanged, so the
    ``GENERIC_IMPLEMENTATION_ACTORS`` membership test below is unaffected.
    """
    if actor is None:
        return None
    typed_actor = cast(ActorField, actor) if isinstance(actor, (str, dict)) else str(actor)
    projected = actor_identity_str(typed_actor)
    if isinstance(typed_actor, str) and projected:
        try:
            tool, _model, _profile, _role = parse_agent_boundary_string(projected)
        except ValueError:
            tool = projected
        projected = tool
    value = projected.strip()
    return value or None


def _actors_compatible(existing: object | None, requested: object | None, *, allow_generic_existing: bool = False) -> bool:
    existing_key = _actor_key(existing)
    requested_key = _actor_key(requested)
    if existing_key is None or requested_key is None:
        return True
    if existing_key == requested_key:
        return True
    return allow_generic_existing and existing_key in GENERIC_IMPLEMENTATION_ACTORS


def _read_events_for_implementer(
    *,
    feature_dir: Path,
    mission_slug: str,
    repo_root: Path | None,
) -> list[StatusEvent] | None:
    """The mission's transactional event read, or ``None`` on any read failure (#5377).

    The one place this module reads the log through ``coordination``: both the
    implementer-of-record admission and the refusal label go through it, so
    no second status-to-coordination read site exists.
    """
    # Lazy imports: ``review_roles`` imports this module (a top-level import would
    # cycle) and ``coordination.status_transition`` imports back into status.
    from specify_cli.coordination.status_transition import read_events_transactional

    try:
        return list(read_events_transactional(feature_dir=feature_dir, mission_slug=mission_slug, repo_root=repo_root))
    except Exception:  # fail closed toward the existing claim-conflict refusal (#5377)
        return None


def _admits_implementer_of_record(
    *,
    feature_dir: Path,
    mission_slug: str,
    wp_id: str,
    actor: ActorField,
    repo_root: Path | None,
) -> bool:
    """Whether ``actor`` is ``wp_id``'s implementer of record (#5377).

    Same projection ``move-task`` uses since #5196. Fails closed: any read or
    projection failure returns ``False`` so the caller keeps refusing. An admitted
    resume writes no event, so the reduced slot still names the reviewer while the
    returned ``claimed_by`` names the implementer; the next ``move-task`` passes
    through the same projection.
    """
    from specify_cli.status.review_roles import is_latest_implementer, latest_implementer_actor

    events = _read_events_for_implementer(feature_dir=feature_dir, mission_slug=mission_slug, repo_root=repo_root)
    if events is None:
        return False
    try:
        return is_latest_implementer(latest_implementer_actor(events, wp_id), actor)
    except Exception:  # fail closed toward the existing claim-conflict refusal (#5377)
        return False


_REVIEW_LANES: frozenset[Lane] = frozenset({Lane.FOR_REVIEW, Lane.IN_REVIEW, Lane.APPROVED})


def _reject_force_outside_review_lanes(
    wp_id: str,
    current_lane: Lane,
    review_lane_exit: bool,
    operator_force_note: str | None,
) -> None:
    """Refuse an operator force, before any write, unless the WP is in a review lane."""
    if operator_force_note is None:
        return
    if not operator_force_note.strip():
        raise WorkPackageStartRejected(FORCE_NOTE_REQUIRED)
    if not review_lane_exit or current_lane not in _REVIEW_LANES:
        raise WorkPackageStartRejected(f"--force only applies to a WP in for_review, in_review or approved; {wp_id} is in '{current_lane}'")


def _review_lane_exit_reason(
    *,
    feature_dir: Path,
    mission_slug: str,
    wp_id: str,
    current_lane: Lane,
    current_actor: object | None,
    actor: ActorField,
    repo_root: Path | None,
    operator_force_note: str | None,
) -> str:
    """Return the honest event reason for leaving a review lane, or raise the refusal (#5446)."""
    if operator_force_note is not None:
        return f"Operator force: {operator_force_note.strip()}"
    if current_lane == Lane.IN_REVIEW:
        raise WorkPackageClaimConflict(wp_id, str(current_actor or _UNKNOWN_ACTOR), actor, review=True)
    if current_lane == Lane.APPROVED:
        raise WorkPackageStartRejected(
            f"WP {wp_id} is approved; implementation cannot resume it. To rework it run "
            f"`spec-kitty agent tasks move-task {wp_id} --to planned --review-feedback-file <file>`, "
            f"or, as an operator, {FORCE_NOTE_HINT}"
        )
    if not _admits_implementer_of_record(
        feature_dir=feature_dir,
        mission_slug=mission_slug,
        wp_id=wp_id,
        actor=actor,
        repo_root=repo_root,
    ):
        raise WorkPackageClaimConflict(
            wp_id,
            _implementer_of_record_label(feature_dir, mission_slug, wp_id, repo_root),
            actor,
            submitted=True,
        )
    return f"Implementer of record withdrew {wp_id} from for_review to continue implementation"


def _implementer_of_record_label(feature_dir: Path, mission_slug: str, wp_id: str, repo_root: Path | None) -> str:
    """Name the implementer of record for a refusal message; ``"unknown"`` on any read failure."""
    from specify_cli.status.review_roles import latest_implementer_actor

    events = _read_events_for_implementer(feature_dir=feature_dir, mission_slug=mission_slug, repo_root=repo_root)
    if events is None:
        return _UNKNOWN_ACTOR
    try:
        return latest_implementer_actor(events, wp_id) or _UNKNOWN_ACTOR
    except Exception:  # a failed projection only degrades the message; the refusal stands
        return _UNKNOWN_ACTOR


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
    review_lane_exit: bool = False,
    operator_force_note: str | None = None,
    annotation_delta: WPInnerStateDelta | None = None,
) -> WorkPackageStartResult:
    """Idempotently move a WP into ``in_progress`` for an implementation actor.

    ``review_lane_exit`` is an explicit opt-in held only by ``agent action
    implement``: without it every review lane (``for_review``, ``in_review``,
    ``approved``) is rejected. With it, a review lane is left only by the
    implementer of record withdrawing an unclaimed ``for_review`` submission, or
    by an operator supplying ``operator_force_note`` (#5446).
    """
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

    with feature_status_lock(lock_root, mission_lock_key(feature_dir, repo_root=lock_root)):
        current = read_current_wp_state_transactional(
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id=wp_id,
            repo_root=repo_root,
        )
        current_lane = current.lane
        current_actor = current.actor

        if current_lane == Lane.GENESIS:
            raise WorkPackageStartRejected(f"WP {wp_id} is not finalized; run `spec-kitty agent mission finalize-tasks`")

        _reject_force_outside_review_lanes(wp_id, current_lane, review_lane_exit, operator_force_note)

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
                raise WorkPackageClaimConflict(wp_id, current_actor or _UNKNOWN_ACTOR, actor)
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
                # #5377: after a reviewer's rework verdict the slot holds the
                # reviewer; the implementer of record still resumes (no event).
                if not _admits_implementer_of_record(
                    feature_dir=feature_dir,
                    mission_slug=mission_slug,
                    wp_id=wp_id,
                    actor=actor,
                    repo_root=repo_root,
                ):
                    raise WorkPackageClaimConflict(wp_id, current_actor or _UNKNOWN_ACTOR, actor)
                return WorkPackageStartResult(wp_id, Lane.IN_PROGRESS, Lane.IN_PROGRESS, actor, (), no_op=True, claimed_by=actor_identity_str(actor))
            return WorkPackageStartResult(wp_id, Lane.IN_PROGRESS, Lane.IN_PROGRESS, actor, (), no_op=True, claimed_by=current_actor)

        if review_lane_exit and current_lane in _REVIEW_LANES:
            reason = _review_lane_exit_reason(
                feature_dir=feature_dir,
                mission_slug=mission_slug,
                wp_id=wp_id,
                current_lane=current_lane,
                current_actor=current_actor,
                actor=actor,
                repo_root=repo_root,
                operator_force_note=operator_force_note,
            )
            event = emit_status_transition_transactional(
                TransitionRequest(
                    feature_dir=feature_dir,
                    mission_slug=mission_slug,
                    wp_id=wp_id,
                    to_lane=Lane.IN_PROGRESS,
                    actor=actor,
                    force=True,
                    reason=reason,
                    workspace_context=workspace_context,
                    execution_mode=execution_mode,
                    repo_root=repo_root,
                    policy_metadata=policy_metadata,
                    annotation_delta=annotation_delta,
                ),
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

    with feature_status_lock(lock_root, mission_lock_key(feature_dir, repo_root=lock_root)):
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
                raise WorkPackageClaimConflict(wp_id, decision.holder or _UNKNOWN_ACTOR, actor, review=True)
            return WorkPackageStartResult(wp_id, Lane.IN_REVIEW, Lane.IN_REVIEW, actor, (), no_op=True, claimed_by=current_actor)

    raise WorkPackageStartRejected(f"WP {wp_id} is in '{current_lane}', cannot start review")
