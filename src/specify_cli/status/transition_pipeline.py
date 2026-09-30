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
from typing import TYPE_CHECKING, Any

from kernel.clock import now_utc_iso

from . import emit as _emit
from .lane_head import LANE_HEAD_KEY
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
    from mission_runtime import OwnedCheckout
    from specify_cli.core.dependency_graph import DependencyReadiness
    from .lane_head import LaneHeadProbe

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
    owned: OwnedCheckout | None = None,
) -> Path:
    """Today's resolver: the canonical ``resolve_subtasks_gate_dir`` seam.

    Imported lazily exactly as the shells did before the promotion -- the
    ``missions`` package must not be pulled in at ``status`` import time.
    Receives ``owned=`` from the pipeline (FR-003) when a request holds a
    fact, and hands that fact straight to the converted seam.
    """
    from specify_cli.missions._read_path_resolver import resolve_subtasks_gate_dir  # noqa: PLC0415

    resolved: Path = resolve_subtasks_gate_dir(feature_dir, repo_root, mission_slug, owned=owned)
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
            owned=request.owned,
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


def _stamped_policy_metadata(
    *,
    request: TransitionRequest,
    mission_slug: str,
    lane_head_probe: LaneHeadProbe | None,
    repo_root: Path | None,
) -> dict[str, Any] | None:
    """Return *request*'s ``policy_metadata`` with a best-effort lane-head stamp (FR-001).

    ``lane_head_probe is None`` means no stamp: P-1 (purity) forbids this
    module from ever defaulting to a real probe, so the composition shells
    are the only source of one. When a probe IS supplied, the repo root it
    is called with prefers ``request.repo_root``; the *repo_root* keyword is
    only a fallback for a request that omits it (the shells resolve and pass
    both, but ``request.repo_root`` wins so a caller that pre-populated the
    request is honored). Any missing repo root, or a probe result of
    ``None`` (no lane, no branch, any git/read error -- the probe itself
    never raises), leaves ``policy_metadata`` byte-identical to what the
    request already carried. ``request.owned`` is forwarded so an owned
    transition's probe reads the lane map from the fact, never from the
    repository root.
    """
    # Annotated local (mirrors `emit._repo_root_for_lane_head`): under this
    # repo's project-wide `specify_cli.*` mypy `follow_imports = "skip"`
    # (pyproject.toml `[tool.mypy]`), a narrow-file `mypy --strict` check on
    # this module alone sees `TransitionRequest.policy_metadata` as `Any`
    # (its concrete `dict[str, Any] | None` annotation lives in the skipped
    # `status.models`), so returning it verbatim trips `no-any-return`. The
    # annotation on this local re-asserts the field's real, already-declared
    # type without a `cast`.
    request_policy_metadata: dict[str, Any] | None = request.policy_metadata
    if lane_head_probe is None or request.wp_id is None:
        return request_policy_metadata
    effective_repo_root = request.repo_root if request.repo_root is not None else repo_root
    if effective_repo_root is None:
        return request_policy_metadata
    sha = lane_head_probe(repo_root=effective_repo_root, mission_slug=mission_slug, wp_id=request.wp_id, owned=request.owned)
    if not sha:
        return request_policy_metadata
    return {**(request_policy_metadata or {}), LANE_HEAD_KEY: sha}


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
    lane_head_probe: LaneHeadProbe | None = None,
    repo_root: Path | None = None,
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
        lane_head_probe: Injected lane-branch-head resolver (FR-001). ``None``
            (the default) means no stamp -- P-1 forbids this module from
            defaulting to a real probe itself; the shells inject
            ``status.lane_head.probe_lane_head`` at all four call sites. When
            supplied, its result (or lack of one) only ever appends
            ``policy_metadata["lane_head"]``; it never changes any other
            field or refuses the transition.
        repo_root: The canonical repository root the shell resolved for the
            lane-head probe (fallback when ``request.repo_root`` is
            ``None``). Unused when ``lane_head_probe`` is ``None``.

    Returns:
        A :class:`PreparedTransition`. ``event is None`` is the alias-collapse
        no-op arm (mirror only, nothing to append).

    Raises:
        TypeError: when ``wp_id``/``to_lane``/``actor`` is missing.
        TransitionError: when :func:`validate_transition` refuses the edge.
    """
    if request.wp_id is None or request.to_lane is None or request.actor is None:
        raise TypeError("Each status transition requires wp_id, to_lane, and actor")

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
            review_ref=request.review_ref,
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
    #
    # FR-001 (mixed-lane-authorship-soundness-01M3M7Y0/WP03): best-effort
    # lane-head stamp, appended to policy_metadata just before the event is
    # built. Byte-identical to today when lane_head_probe is None or the
    # probe finds nothing to stamp.
    stamped_policy_metadata = _stamped_policy_metadata(
        request=request,
        mission_slug=mission_slug,
        lane_head_probe=lane_head_probe,
        repo_root=repo_root,
    )
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
        review_ref=request.review_ref,
        evidence=done_evidence,
        review_result=request.review_result,
        policy_metadata=stamped_policy_metadata,
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
