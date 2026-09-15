"""Status-owned transition pipeline: the single validation/build authority.

This module is the ONE place in the tree where a status transition is
validated and its :class:`StatusEvent` is built (decision Q4,
``01M1V80R6F6RTMR7Y3C2WBKR32``; spec FR-005; contract
``contracts/emit-pipeline.md`` §1). It is the promotion of
``coordination/status_transition.py::_prepare_event`` into the ``status``
package, verbatim and in step order:

    1. alias-resolve ``to_lane``;
    2. infer the review gates (``subtasks_complete``,
       ``implementation_evidence_present``) only for
       ``in_progress -> for_review`` without ``force``;
    3. alias-collapse check -> ``PreparedTransition(event=None, ...)``;
    4. build done-evidence;
    5. build the :class:`GuardContext`;
    6. ``validate_transition`` -- the only call per emit anywhere in the tree;
    7. ``build_status_event`` and attach the claim annotation.

Layering (constraint C-006): ``status`` never imports ``coordination``. This
module imports ``status.models``, ``status.transitions``, ``status.wp_state``
and the module-private helpers of ``status.emit`` (decision Q6, recorded in
``design-notes/WP02-pipeline.md``) -- never ``specify_cli.coordination``.
``tests/architectural/test_status_module_boundary.py`` and the AST pin in
``tests/status/test_transition_pipeline.py`` enforce the direction.

Purity (invariant P-1): zero writes, zero locks, zero git, zero fan-out in
this module. It returns a value; the composition shells (flat/primary in
``status/emit.py``; transactional in ``coordination/status_transition.py``)
own the lock, the append, the materialize, the frontmatter mirror, and the
fan-out. In particular the pipeline only *requests* the phase-gated
frontmatter ``lane`` mirror (``mirror_frontmatter_lane=True``); it never
calls ``_mirror_phase1_frontmatter_lane`` itself, which stays the tree's only
``write_frontmatter`` of ``lane`` (``test_2093_authority_invariant.py``).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from kernel.clock import now_utc_iso

from . import emit as _emit
from .models import (
    DoneEvidence,
    GuardContext,
    InnerStateChanged,
    Lane,
    StatusEvent,
    TransitionRequest,
    actor_identity_str,
)
from .transitions import resolve_lane_alias, validate_transition
from .wp_state import annotate

if TYPE_CHECKING:
    from specify_cli.core.dependency_graph import DependencyReadiness

#: Injected I/O seams (contract §1). ``Callable[..., ...]`` mirrors the shape
#: of today's helpers; tests pass fakes with the same call signature.
SubtasksDirResolver = Callable[..., Path]
SubtasksCompleteInferrer = Callable[..., "bool | None"]
ImplementationEvidenceInferrer = Callable[..., "bool | None"]


@dataclass(frozen=True)
class PreparedTransition:
    """The pipeline's value-level output (contract §1, data-model §4).

    ``event is None`` marks the alias-collapse no-op arm: a legacy alias
    resolved to the WP's current lane, so no transition is appended and the
    shell only runs the phase-gated frontmatter mirror.
    """

    event: StatusEvent | None
    resolved_lane: str
    annotation: InnerStateChanged | None
    mirror_frontmatter_lane: bool


def _default_resolve_subtasks_dir(
    feature_dir: Path,
    repo_root: Path | None,
    mission_slug: str,
    *,
    effective_root: Path | None = None,
) -> Path:
    """Today's resolver: the canonical ``resolve_subtasks_gate_dir`` seam.

    Imported lazily exactly as the shells did before the promotion -- the
    ``missions`` package must not be pulled in at ``status`` import time.
    """
    from specify_cli.missions._read_path_resolver import resolve_subtasks_gate_dir  # noqa: PLC0415

    resolved: Path = resolve_subtasks_gate_dir(
        feature_dir,
        repo_root,
        mission_slug,
        effective_root=effective_root,
    )
    return resolved


def _annotation_for_request(
    request: TransitionRequest,
    *,
    at: str | None = None,
) -> InnerStateChanged | None:
    """Build the claim annotation carried by *request*, without I/O.

    Promoted verbatim from ``coordination/status_transition.py``; it only
    mints a ULID and a timestamp.
    """
    if request.annotation_delta is None:
        return None
    if request.wp_id is None or request.actor is None:
        raise TypeError("claim annotations require wp_id and actor")
    return annotate(
        request.wp_id,
        request.annotation_delta,
        actor=request.actor,
        at=at or now_utc_iso(),
        event_id=_emit._generate_ulid(),
    )


def _infer_review_gates(
    *,
    request: TransitionRequest,
    feature_dir: Path,
    mission_slug: str,
    wp_id: str,
    from_lane: str,
    resolved_lane: str,
    resolve_subtasks_dir: SubtasksDirResolver | None,
    infer_subtasks_complete: SubtasksCompleteInferrer | None,
    infer_implementation_evidence: ImplementationEvidenceInferrer | None,
) -> tuple[bool | None, bool | None]:
    """Step 2: infer the two review gates for ``in_progress -> for_review``.

    Verbatim from ``_prepare_event``: the subtask gate is inferred only when
    the transition is not forced; the implementation-evidence gate only when
    the caller left it ``None``. Every other edge passes the request's hints
    through untouched.
    """
    subtasks_complete = request.subtasks_complete
    implementation_evidence_present = request.implementation_evidence_present
    review_handoff = from_lane == Lane.IN_PROGRESS and resolved_lane == Lane.FOR_REVIEW
    if not request.force and review_handoff:
        # T012/FR-002 (#2574 single seam): route through the canonical
        # resolve_subtasks_gate_dir seam so a coord-topology mission's
        # completeness check reads the PRIMARY tasks.md, not a
        # coordination-branch husk. When ``request.repo_root`` is None the
        # seam recovers the primary root from ``feature_dir``'s git ancestry.
        resolver = resolve_subtasks_dir or _default_resolve_subtasks_dir
        subtasks_dir = resolver(
            feature_dir,
            request.repo_root,
            mission_slug,
            effective_root=request.effective_root,
        )
        infer_subtasks = infer_subtasks_complete or _emit._infer_subtasks_complete
        subtasks_complete = infer_subtasks(
            subtasks_dir,
            wp_id,
            status_dir=feature_dir,
        )
    if implementation_evidence_present is None and review_handoff:
        infer_evidence = infer_implementation_evidence or _emit._infer_implementation_evidence
        implementation_evidence_present = infer_evidence(feature_dir, wp_id)
    return subtasks_complete, implementation_evidence_present


def _validated_inline_fields(
    request: TransitionRequest,
) -> tuple[str | None, str | None]:
    """Enforce the #4327 new-write inline moment rules on *request*.

    Returns the validated ``(summary, review_ref)`` the event must carry:
    ``summary`` (when supplied) is one printable line of at most 240 UTF-8
    bytes; ``review_ref`` (when supplied) is pointer-shaped. A violation
    raises :class:`TransitionError` carrying the validator's named
    field/bound/size message, so every existing catch-site (CLI shells,
    orchestrator API, lifecycle) reports it through its own clean error
    path. This module is the single validation/build authority, so this is
    the one enforcement point that no programmatic caller can bypass.
    ``review_result.reference`` is deliberately NOT validated here: it has a
    legacy-compat read path (a rework on a mission whose review artifact was
    persisted before #4327 legitimately still carries a prose reference),
    and rewriting those persisted artifacts is out of scope ("existing
    persisted events without rewriting Git history").
    """
    from .moment_fields import (
        ReviewRefValidationError,
        SummaryValidationError,
        validate_review_ref,
        validate_summary,
    )

    try:
        summary = validate_summary(request.summary) if request.summary is not None else None
        review_ref = validate_review_ref(request.review_ref, repo_root=request.repo_root) if request.review_ref is not None else None
    except (SummaryValidationError, ReviewRefValidationError) as exc:
        raise _emit.TransitionError(str(exc)) from exc
    return summary, review_ref


def prepare_transition(
    *,
    request: TransitionRequest,
    feature_dir: Path,
    mission_slug: str,
    mission_id: str | None,
    from_lane: str,
    readiness: DependencyReadiness | None = None,
    at: str | None = None,
    resolve_subtasks_dir: SubtasksDirResolver | None = None,
    infer_subtasks_complete: SubtasksCompleteInferrer | None = None,
    infer_implementation_evidence: ImplementationEvidenceInferrer | None = None,
    default_workspace_context: bool = True,
) -> PreparedTransition:
    """Validate *request* against *from_lane* and build its event (pure).

    Args:
        request: The transition request. ``wp_id``, ``to_lane`` and ``actor``
            are required; a missing one raises ``TypeError``.
        feature_dir: The shell's WRITE surface (``txn.feature_dir`` under a
            coordination topology; the canonical primary dir otherwise). Used
            as the status surface for gate inference and as the default
            workspace-context root.
        mission_slug: Mission handle stamped on the event.
        mission_id: Canonical ULID identity stamped on the event (``None``
            for legacy missions).
        from_lane: The WP's current lane, derived by the shell in-lock
            exactly once (NFR-004). The pipeline never reads the log itself.
        readiness: Dependency-readiness verdict resolved by the shell
            in-lock against its write surface (FR-013). Threaded into
            ``GuardContext.dependency_ready`` as ``readiness.satisfied``;
            ``None`` means no verdict was supplied and the guard passes
            (C-004 fail-open). Both shells always supply one.
        at: Optional producer timestamp for the event and its annotation
            (batch shells stamp monotonic offsets; ``None`` means now).
        resolve_subtasks_dir: Injected resolver for the subtask gate's
            PRIMARY ``tasks`` surface. ``None`` selects today's helper
            (``resolve_subtasks_gate_dir``).
        infer_subtasks_complete: Injected subtask-gate reader. ``None``
            selects ``emit._infer_subtasks_complete``.
        infer_implementation_evidence: Injected evidence reader. ``None``
            selects ``emit._infer_implementation_evidence``.
        default_workspace_context: Policy knob for a request that omits
            ``workspace_context``. ``True`` (the default; the flat single
            door and both transactional doors) synthesises
            ``<execution_mode>:<repo_root or feature_dir>`` so the
            ``claimed -> in_progress`` guard is satisfied. ``False`` leaves
            it ``None`` and the guard refuses that edge with the historical
            ``"requires workspace context"`` message (``wp_state.py``), the
            only guard that reads it -- every other edge is unaffected.
            Provenance: the plain batch door (``emit._prepare_batch``)
            deliberately skipped the default on that edge (#946); mission
            ``fsm-write-path-integrity-01M1TZV6`` WP02 dropped the skip for
            door parity (``design-notes/WP02-pipeline.md`` §6 row D-2;
            mission-review DRIFT-3); operator decision 2026-09-07 reverted
            it to fail-closed, expressed here so the pipeline stays the
            single validation authority instead of re-inlining the rule in
            the shell.

    Returns:
        A :class:`PreparedTransition`. ``event is None`` is the alias-collapse
        no-op arm (mirror only, nothing to append).

    Raises:
        TypeError: when ``wp_id``/``to_lane``/``actor`` is missing.
        TransitionError: when :func:`validate_transition` refuses the edge,
            or when the request's inline moment fields fail the #4327
            new-write rules (see :func:`_validated_inline_fields`).
    """
    if request.wp_id is None or request.to_lane is None or request.actor is None:
        raise TypeError("Each status transition requires wp_id, to_lane, and actor")

    # Step 0 (#4327, scope clarification 2026-09-14): enforce the new-write
    # summary and pointer rules HERE -- the shared creation boundary every
    # emission shell funnels through -- not only at the Typer options, so a
    # programmatic caller (orchestrator API, lifecycle, workflow executor)
    # cannot bypass validation. The CLI commands validate the same fields
    # earlier still, before any review-cycle artifact is written; this is
    # the backstop that makes the boundary itself fail-closed.
    summary, review_ref = _validated_inline_fields(request)

    # Step 1: alias-resolve.
    raw_to_lane = str(request.to_lane).strip().lower()
    resolved_lane = resolve_lane_alias(str(request.to_lane))

    workspace_context = request.workspace_context
    if workspace_context is None and default_workspace_context:
        context_root = request.repo_root if request.repo_root is not None else feature_dir
        workspace_context = f"{request.execution_mode}:{context_root}"

    # Step 2: infer the review gates.
    subtasks_complete, implementation_evidence_present = _infer_review_gates(
        request=request,
        feature_dir=feature_dir,
        mission_slug=mission_slug,
        wp_id=request.wp_id,
        from_lane=from_lane,
        resolved_lane=resolved_lane,
        resolve_subtasks_dir=resolve_subtasks_dir,
        infer_subtasks_complete=infer_subtasks_complete,
        infer_implementation_evidence=infer_implementation_evidence,
    )

    # Step 3: alias-collapse -> no-op arm. The shell runs the mirror; the
    # pipeline only requests it (P-1: no writes here).
    if _emit._legacy_alias_collapses_to_current_lane(raw_to_lane, resolved_lane, from_lane):
        return PreparedTransition(
            event=None,
            resolved_lane=resolved_lane,
            annotation=None,
            mirror_frontmatter_lane=True,
        )

    # Step 4: done-evidence.
    done_evidence: DoneEvidence | None = None
    if request.evidence is not None:
        done_evidence = _emit._build_done_evidence(request.evidence)

    # Step 5 + 6: guard context and the tree's only validate_transition call.
    # The dependency verdict is tri-state (FR-012): the shell's in-lock
    # readiness becomes ``dependency_ready``; no verdict stays ``None`` and the
    # guard passes (C-004 fail-open, decision Q8).
    ok, error_msg = validate_transition(
        from_lane,
        resolved_lane,
        GuardContext(
            force=request.force,
            actor=actor_identity_str(request.actor),
            workspace_context=workspace_context,
            subtasks_complete=subtasks_complete,
            implementation_evidence_present=implementation_evidence_present,
            reason=request.reason,
            review_ref=review_ref,
            evidence=done_evidence,
            review_result=request.review_result,
            current_actor=request.current_actor,
            dependency_ready=None if readiness is None else readiness.satisfied,
        ),
    )
    if not ok:
        raise _emit.TransitionError(error_msg)

    # Step 7: build the event, then its claim annotation. The annotation is
    # minted after the event and shares its ``at``; ULIDs are not monotonic
    # within a millisecond, so no sort order between the two is claimed. The
    # reducer folds annotations in a post-transition partition pass, so their
    # relative ULID order is not load-bearing.
    event = _emit.build_status_event(
        mission_slug=mission_slug,
        wp_id=request.wp_id,
        from_lane=from_lane,
        to_lane=resolved_lane,
        actor=request.actor,
        at=at,
        mission_id=mission_id,
        force=request.force,
        execution_mode=request.execution_mode,
        reason=request.reason,
        # Provenance discriminator (FR-001): threaded from the request so the
        # canonical move-task command's cancel event carries operator/synthetic
        # onto the persisted StatusEvent.
        reason_source=request.reason_source,
        review_ref=review_ref,
        summary=summary,
        evidence=done_evidence,
        review_result=request.review_result,
        policy_metadata=request.policy_metadata,
    )
    return PreparedTransition(
        event=event,
        resolved_lane=resolved_lane,
        annotation=_annotation_for_request(request, at=at),
        mirror_frontmatter_lane=True,
    )


# The three injected-I/O callable aliases stay module-level for annotations but are
# not exported: no src/ caller names them (dead-symbol gate, #470).
__all__ = [
    "PreparedTransition",
    "prepare_transition",
]
