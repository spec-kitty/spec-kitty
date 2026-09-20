"""Pure transition-decision core for ``agent tasks move-task`` (WP03).

This module lifts ``move_task``'s **transition decision** out of the interleaved
command body into ONE pure function, :func:`decide_transition`, plus the pure
lane-hop shaper :func:`build_transition_plan` it delegates to. It is a
behaviour-preserving (pure-parity) extraction: it **reproduces move_task's exact
current behaviour** (research D4 / FR-004 / NFR-001) — including the pre-existing
skip-vs-refuse divergence that ``#2300`` defers, and the OLD
partial-write-on-refusal *timing* of the two proceed-side-effect persists
(review-artifact override and arbiter decision). The pure core owns the
decision; the imperative SHELL still executes those two persists at their
ORIGINAL guard positions — the override persist inside the rejected-verdict
proceed arm (before feedback/subtasks/review-currency/done-ancestry/issue-matrix)
and the arbiter persist before the issue-matrix guard — so a later guard's
refusal (exit 1) still leaves the OLD partial write on disk, exactly as the
un-refactored command did. Those two positions are surfaced to the shell as pure
early signals (:func:`override_persist_signal`, :func:`arbiter_persist_signal`)
computed from early facts alone. This module does not reconcile or unify
behaviour.

EXCEPTION (review-verdict-write-integrity-01KZ1CGF, FR-001): :func:`_guard_rejected_verdict`'s
plain-refuse arm — a latest ``"rejected"`` verdict with no
``--skip-review-artifact-check`` — is an INTENTIONAL, one-off behaviour change,
not a pure-parity reproduction. See that function's docstring for the full
rationale: refusing was the old command's only way to prevent a silent
approve-over-rejection when nothing could record a genuine approval; now that
``_mt_finalize_plan`` persists a real approved artifact, the ordinary
reject-fix-approve path is allowed to proceed instead of dead-ending at the
mission's one documented escape hatch.

EXCEPTION (FIX-M2-03): :func:`_guard_agent_ownership`'s
``GENERIC_IMPLEMENTATION_ACTORS`` early-return is a second INTENTIONAL,
one-off behaviour change, not a pure-parity reproduction. See that function's
docstring for the full rationale.

Design (functional core / imperative shell):

* The orchestrator (``move_task``) performs all filesystem / git / clock reads
  and passes the resulting FACTS in a frozen :class:`MoveTaskRequest`.
* :func:`decide_transition` is **pure** — no filesystem, git, status-emission,
  rendering, or clock access — and returns a :data:`TransitionOutcome`:
  - :class:`RefuseExit1` — a guard failed; the shell prints the error (plus any
    ``console_warning`` lines) and exits 1.
  - :class:`Emit` — the transition proceeds; ``skip_primary`` encodes the coord
    skip-exit-0 arm (the WP-file commit to the protected primary is skipped, the
    coord emission still happens), and the proceed-authorisation flags tell the
    shell which side effects (review-artifact override, planned-rollback review
    cycle, arbiter decision) to execute before the emit loop.
* The two DURABLE proceed persists (override + arbiter) are additionally gated by
  the pure :func:`override_persist_signal` / :func:`arbiter_persist_signal`
  helpers, which the shell consults to fire each persist at its OLD guard
  position — before the later guards that could still refuse — preserving the
  original partial-write-on-refusal behaviour.

The coord skip arm is encoded as ``Emit(skip_primary=True)`` — **not** a no-emit
terminal — because ``move_task`` still emits the transition to the coordination
branch and exits 0 in that arm (spec §Behavior-parity guard). ``move_task`` has
no exit-0-without-emit path, so no separate ``SkipExit0`` terminal is minted here.

The guard sequence mirrors the live command exactly (order is load-bearing — the
first failing guard wins). Each guard is a small pure helper so the aggregate
complexity stays within the ≤15 ceiling (NFR-003) and every branch is directly
unit-testable (NFR-002).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from specify_cli.cli.commands.agent.tasks_finalize_validation import (
    _is_backward_transition,
    _lane_targets_for_emit,
)
from specify_cli.cli.commands.agent.tasks_parsing_validation import (
    _self_review_fallback_option_error,
)
from specify_cli.status import (
    GENERIC_IMPLEMENTATION_ACTORS,
    GuardContext,
    Lane,
    resolve_lane_alias,
    validate_transition,
    wp_state_for,
)
from specify_cli.status import _actor_key

# Terminal lanes that build approval evidence + run the rejected-verdict guard.
_APPROVAL_LANES: tuple[str, ...] = (Lane.APPROVED, Lane.DONE)
# Lanes whose forward move validates subtasks + review currency.
_REVIEW_GATE_LANES: tuple[str, ...] = (Lane.FOR_REVIEW, Lane.APPROVED, Lane.DONE)


# ---------------------------------------------------------------------------
# Request (pre-read facts) + outcome value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MoveTaskRequest:
    """Every fact ``decide_transition`` needs — all resolved by the shell.

    The shell (``move_task``) performs the I/O (dir resolution, event reads,
    review-artifact reads, git ancestry, protection-policy checks, reviewer
    auto-detection) and freezes the results here so the decision is pure.
    """

    task_id: str
    target_lane: str
    old_lane: str
    force: bool
    agent: str | None
    current_agent: str | None
    note: str | None
    auto_commit: bool
    target_branch: str
    skip_target_branch_commit: bool
    tracker_ref_values: tuple[str, ...]
    assignee: str | None
    shell_pid: str | None
    self_review_fallback: bool
    intended_reviewer: str | None
    reviewer_failure_reason: str | None
    # Pre-computed protected-branch refusal string (None when not applicable).
    protected_error: str | None
    # Latest review-cycle verdict + artifact name (APPROVAL_LANES only).
    review_verdict: str | None
    review_artifact_name: str | None
    skip_review_artifact_check: bool
    # Review-feedback file facts (resolved absolute path shown in messages).
    feedback_provided: bool
    feedback_source: str | None
    feedback_exists: bool
    feedback_is_file: bool
    feedback_content: str | None
    # Review-gate facts (REVIEW_GATE_LANES).
    unchecked_subtasks: tuple[str, ...]
    review_ready: bool
    review_guidance: tuple[str, ...]
    # done-ancestry facts (DONE only).
    done_execution_mode: str | None
    done_merged: bool
    done_merge_msg: str
    done_override_reason: str | None
    # issue-matrix approval blocker (APPROVAL_LANES only; None when clear).
    issue_matrix_blocker: str | None
    # Arbiter-override detection (I/O in the shell).
    is_arbiter_override: bool
    # Approval evidence inputs (reviewer auto-detected / approval-ref defaulted).
    effective_reviewer: str | None
    effective_approval_ref: str | None
    # FR-003 / T008 subtask-gate re-source seam (default None in the WP02 window).
    # When the shell supplies ``feature_dir``, ``_guard_subtasks`` resolves
    # "unchecked" unconditionally from the reduced-snapshot ``subtasks`` slot;
    # while ``feature_dir`` is None it falls back to the legacy
    # ``unchecked_subtasks`` tuple (tasks.md-derived). The legacy fallback is
    # retired in WP10 once every writer emits the slot (C-001).
    feature_dir: Path | None = None
    repo_root: Path | None = None
    # FR-006 (canonical-state-recovery WP02): threaded through so the
    # protected-branch metadata refusal below can name a concrete repair
    # command. ``None`` is tolerated (message degrades to a generic mention)
    # so every pre-existing direct ``MoveTaskRequest(...)`` construction stays
    # valid without updating every call site.
    mission_slug: str | None = None


@dataclass(frozen=True)
class TransitionPlan:
    """The pure lane-hop shape the emit loop executes."""

    canonical_lane: str
    transition_targets: list[str]
    emit_force: bool
    emit_reason: str | None
    emit_review_ref: str | None


@dataclass(frozen=True)
class RefuseExit1:
    """A guard failed: the shell prints ``error`` (+ warning) and exits 1."""

    error: str
    diagnostic: dict[str, Any] | None = None
    console_warning: tuple[str, ...] = ()


@dataclass(frozen=True)
class Emit:
    """The transition proceeds; the shell executes the plan + authorised effects."""

    plan: TransitionPlan
    skip_primary: bool
    evidence_dict: dict[str, Any] | None
    note_text: str | None
    authorize_review_override: bool = False
    planned_rollback: bool = False
    arbiter_forward: bool = False
    done_override_note: bool = False


TransitionOutcome = Emit | RefuseExit1


# ---------------------------------------------------------------------------
# Pure lane-hop shaper (arbiter / force / backward / coord skip inputs)
# ---------------------------------------------------------------------------


def _wire_contract_allows_force_free(
    old_lane: str,
    new_lane: str,
    reason: str | None,
    review_ref: str | None,
) -> bool:
    """Ask the SHARED ``spec-kitty-events`` contract whether this backward edge
    is legal *without* ``force`` (#3307).

    The emit decision must be governed by the wire contract the SaaS ingestion
    endpoint enforces — not only the CLI-local FSM. The two historically gave
    opposite answers for the review-rejection family (``*-> planned`` and
    ``in_review -> in_progress``): the local FSM accepted them force-free given
    plan-layer evidence, while the shared package declares them
    ``force=True``-required, so contract-invalid ``force=False`` events were
    emitted and queued silently, only to be rejected 11+ days later at sync.

    Fail-closed: if the candidate cannot even be represented as a force-free
    wire payload, treat the edge as force-required.
    """
    from spec_kitty_events import validate_transition as _wire_validate
    from spec_kitty_events.status import ExecutionMode, Lane, StatusTransitionPayload

    try:
        candidate = StatusTransitionPayload(
            mission_slug="_wire_probe",
            wp_id="_wire_probe",
            from_lane=Lane(old_lane),
            to_lane=Lane(new_lane),
            actor="cli",
            force=False,
            reason=reason,
            execution_mode=ExecutionMode("direct_repo"),
            review_ref=review_ref,
            evidence=None,
        )
    except (ValueError, TypeError):
        return False
    return bool(_wire_validate(candidate).valid)


def build_transition_plan(
    *,
    old_lane: str,
    target_lane: str,
    force: bool,
    review_feedback_pointer: str | None,
    arb_review_ref: str | None,
    note_text: str | None,
    review_result: object | None = None,
) -> TransitionPlan:
    """Compute the canonical lane, hop list, force flag, reason, and review_ref.

    Reproduces ``move_task`` lines building ``emit_review_ref`` / ``canonical_lane``
    / ``emit_reason`` / ``transition_targets``. ``review_feedback_pointer`` and
    ``arb_review_ref`` are threaded in by the shell after it runs the
    planned-rollback / arbiter side effects (they are ``None`` on the happy path).

    FR-015 (force provenance): a backward edge is NOT blindly auto-promoted to
    ``emit_force=True``. We ask the FSM whether the edge is legal *force-free*
    given the plan-layer evidence (``reason`` / ``review_ref``, plus
    ``review_result`` when the caller supplies it). This is edge-agnostic — there
    is deliberately **no hard-coded edge list** (it would rot if the transition
    matrix changes; ``contracts/emit-force.md``).

    #3307: the FSM verdict alone is NOT sufficient to stay force-free. The wire
    event we emit is consumed by the SaaS ingestion endpoint, which enforces the
    **shared** ``spec-kitty-events`` contract — and that contract declares the
    review-rejection family (``in_progress|for_review|in_review|approved ->
    planned`` and ``in_review -> in_progress``) ``force=True``-required
    regardless of evidence. So we gate on BOTH: stay force-free only when the
    internal FSM *and* the shared wire contract agree (see
    :func:`_wire_contract_allows_force_free`); otherwise emit ``force=True`` with
    the structured rewind rationale. This keeps the emitted event conformant with
    the very package this project vendors, instead of producing ``force=False``
    events its own dependency rejects.

    ``review_result`` is the seam WP06 threads its structured review outcome
    (reviewer + verdict + reference) into for the two ``in_review -> *`` edges; it
    still feeds the internal FSM verdict, but the shared wire contract is now the
    binding gate for the family's force flag.
    """
    canonical_lane = resolve_lane_alias(target_lane)

    emit_review_ref: str | None = None
    if target_lane == Lane.PLANNED and review_feedback_pointer:
        emit_review_ref = review_feedback_pointer
    elif old_lane == Lane.FOR_REVIEW and resolve_lane_alias(target_lane) in (Lane.IN_PROGRESS, Lane.PLANNED) and force:
        emit_review_ref = "force-override"

    # Arbiter override reuses the rejection's review_ref when no base ref applies.
    if arb_review_ref and emit_review_ref is None:
        emit_review_ref = arb_review_ref

    # #3307: the shared wire contract requires a ``review_ref`` on the
    # review-rollback edges out of ``for_review`` / ``in_review`` / ``approved``
    # into ``in_progress`` / ``planned`` — and, for ``in_review -> in_progress``,
    # ``force=True`` does NOT exempt it (that edge is outside the mandatory-force
    # ``*-> planned`` family). When a structured ``review_result`` carries a
    # reference, thread it onto the wire so the emitted event conforms instead of
    # being rejected at sync for a missing ``review_ref``.
    if emit_review_ref is None and review_result is not None:
        review_result_ref = getattr(review_result, "reference", None)
        if isinstance(review_result_ref, str) and review_result_ref.strip():
            emit_review_ref = review_result_ref

    emit_reason: str | None = note_text if note_text else None
    if force and not emit_reason:
        emit_reason = f"Force move to {target_lane}"

    emit_force = force
    if not emit_reason:
        emit_reason = f"Force move to {target_lane}" if force else f"move-task: {old_lane} -> {target_lane}"

    if not force and _is_backward_transition(old_lane, canonical_lane):
        # FR-015: ask the FSM whether this backward edge is legal WITHOUT force,
        # given the plan-layer evidence we carry. Only promote emit_force when the
        # FSM genuinely rejects the force-free transition. Edge-agnostic by design —
        # the query works for ANY backward edge; only the evidence supplied differs,
        # so the three plan-reachable edges resolve force-free while the two
        # in_review->* edges (review_result=None in WP02) do not.
        ctx_with_evidence = GuardContext(
            reason=emit_reason,
            review_ref=emit_review_ref,
            review_result=review_result,
        )
        legal_force_free, _ = validate_transition(old_lane, canonical_lane, ctx_with_evidence)
        # #3307: stay force-free ONLY when the internal FSM *and* the shared
        # wire contract (the one the SaaS ingestion endpoint enforces) both
        # accept the edge force-free. When the wire contract requires force —
        # the review-rejection family does — emit ``force=True`` and carry the
        # structured rewind rationale below, rather than silently emitting a
        # contract-invalid ``force=False`` event.
        wire_allows_force_free = _wire_contract_allows_force_free(old_lane, canonical_lane, emit_reason, emit_review_ref)
        emit_force = not (legal_force_free and wire_allows_force_free)
        original_reason = None if emit_reason is None or emit_reason.startswith("move-task: ") else emit_reason
        reason_parts = [f"backward rewind: {old_lane} -> {canonical_lane}"]
        if review_feedback_pointer and review_feedback_pointer != "force-override":
            reason_parts.append(review_feedback_pointer)
        if original_reason:
            reason_parts.append(original_reason)
        emit_reason = ": ".join(reason_parts)

    transition_targets = [canonical_lane]
    if not emit_force:
        transition_targets = _lane_targets_for_emit(old_lane, canonical_lane)

    return TransitionPlan(
        canonical_lane=canonical_lane,
        transition_targets=transition_targets,
        emit_force=emit_force,
        emit_reason=emit_reason,
        emit_review_ref=emit_review_ref,
    )


# ---------------------------------------------------------------------------
# Guard helpers (pure; each returns a RefuseExit1 or None). Order matters.
# ---------------------------------------------------------------------------


def _guard_self_review(req: MoveTaskRequest) -> RefuseExit1 | None:
    error = _self_review_fallback_option_error(
        enabled=req.self_review_fallback,
        target_lane=req.target_lane,
        force=req.force,
        intended_reviewer=req.intended_reviewer,
        failure_reason=req.reviewer_failure_reason,
    )
    return RefuseExit1(error) if error else None


def _guard_unsupported_skip_metadata(req: MoveTaskRequest) -> RefuseExit1 | None:
    if not req.skip_target_branch_commit:
        return None
    unsupported: list[str] = []
    if req.tracker_ref_values:
        unsupported.append("tracker_refs")
    if req.assignee:
        unsupported.append("assignee")
    if req.shell_pid:
        unsupported.append("shell_pid")
    if req.note:
        unsupported.append("activity_log")
    if not unsupported:
        return None
    mission_hint = f" --mission {req.mission_slug}" if req.mission_slug else " --mission <slug>"
    return RefuseExit1(
        "Cannot persist WP frontmatter/activity metadata on protected "
        f"branch '{req.target_branch}' while coordination topology is active: "
        f"{', '.join(unsupported)}. Rerun from an allowed "
        "branch, omit those metadata flags, use --no-auto-commit, or run "
        f"`spec-kitty doctor mission-state --fix{mission_hint}` if canonical "
        "state also needs to be re-established.",
        diagnostic={
            "error": "WP_METADATA_UNSUPPORTED_ON_PROTECTED_COORD_BRANCH",
            "target_branch": req.target_branch,
            "fields": unsupported,
        },
    )


def _guard_protected_branch(req: MoveTaskRequest) -> RefuseExit1 | None:
    if req.auto_commit and not req.skip_target_branch_commit and req.protected_error:
        return RefuseExit1(req.protected_error)
    return None


def _guard_agent_ownership(req: MoveTaskRequest) -> RefuseExit1 | None:
    # FIX-M2-03: a WP's assignee is a GENERIC_IMPLEMENTATION_ACTORS placeholder
    # (``implement-command``) whenever it was claimed through the internal
    # ``spec-kitty implement`` compat surface without ``--actor`` -- a
    # documented, supported call shape (see implement.py's own docstring:
    # "This command remains available as a compatibility surface for direct
    # callers"), not a real owner. status/work_package_lifecycle.py's own
    # claim/in_progress ownership check already treats this placeholder as
    # unclaimed-in-practice (``_actors_compatible(..., allow_generic_existing=
    # True)``); this guard previously compared ``current_agent`` by raw
    # equality only, so any real ``--agent`` value permanently tripped the
    # ownership-mismatch refusal against a WP no real agent ever claimed,
    # forcing every caller to pass ``--force`` for a conflict that was never
    # real. Matching the SAME allowance here keeps the two ownership checks
    # consistent instead of one silently stricter than the other.
    # #4673/T011: compare through the SAME tool-scoped ``_actor_key`` projection
    # WP01 reconciled the impl-claim comparison with, instead of raw string
    # equality. Two representations of ONE agent (a full compact
    # ``tool:model:profile:role`` string vs. its dict-shaped equivalent) round-
    # trip to the SAME key, so a dict-vs-compact submit no longer trips this
    # gate even though WP01's reconciliation lives one layer down and never
    # reached this raw comparison before.
    current_key = _actor_key(req.current_agent)
    requested_key = _actor_key(req.agent)
    if current_key in GENERIC_IMPLEMENTATION_ACTORS:
        return None
    if not (current_key and requested_key and current_key != requested_key and not req.force):
        return None
    warning = (
        "",
        "[bold red]⚠️  AGENT OWNERSHIP WARNING[/bold red]",
        f"   {req.task_id} is currently assigned to: [cyan]{req.current_agent}[/cyan]",
        f"   You are trying to move it as: [yellow]{req.agent}[/yellow]",
        "",
        "   If you are the correct agent, use --force to override.",
        "   If not, you may be modifying the wrong WP!",
        "",
    )
    error = f"Agent mismatch: {req.task_id} is assigned to '{req.current_agent}', not '{req.agent}'. Use --force to override."
    target_lane = resolve_lane_alias(req.target_lane)
    current_lane = resolve_lane_alias(req.old_lane)
    # The command is still attempting a rejection-verdict save when a
    # concurrent winner has already advanced the lane to ``planned``.
    is_rejection_save = target_lane == Lane.PLANNED and req.feedback_provided
    is_approval_save = target_lane in _APPROVAL_LANES
    diagnostic = None
    if req.auto_commit and (is_rejection_save or is_approval_save):
        # Preserve the ownership policy and exit code while making this
        # verdict-command refusal causal and machine-verifiable.
        diagnostic = {
            "result": "error",
            "code": "ownership_refusal",
            "error": error,
            "current_lane": current_lane,
            "requested_lane": target_lane,
            "assigned_agent": req.current_agent,
            "requesting_agent": req.agent,
            "verdict_durably_persisted": False,
            "evidence_ref": None,
            "destination_ref": None,
        }
    return RefuseExit1(
        error,
        diagnostic=diagnostic,
        console_warning=warning,
    )


def _guard_rejected_verdict(req: MoveTaskRequest) -> RefuseExit1 | None:
    """Refuse arms of the rejected-verdict guard (APPROVAL_LANES only).

    FR-001 (review-verdict-write-integrity-01KZ1CGF): a latest verdict of
    ``"rejected"`` no longer fails-closed the ORDINARY approve path by itself.
    Before the durable writer existed (T001/T005's ``_persist_approved_review_cycle``
    — since WP06's verdict-seam extraction, a top-level function in
    ``tasks_verdict_persistence.py``, not this file), refusing here was the only
    way to stop a rejected verdict from being silently approved over — there was
    nothing that could record a genuine approval artifact, so blocking was
    the safest failure mode. Now that ``tasks_move_task.py``'s ``_mt_finalize_plan``
    calls into that function and persists a real ``verdict: approved``
    review-cycle artifact once the transition proceeds, continuing to refuse
    would keep the ordinary reject-fix-approve path hitting the "only escape
    hatch" this mission exists to close (spec.md User Story 1, Acceptance
    Scenarios 1 & 2 / SC-002 / NFR-002).

    What this guard still refuses:

    * An unparseable verdict (the artifact itself is broken) — unrelated to
      rejection, always refused.
    * ``--skip-review-artifact-check`` supplied WITHOUT ``--note`` — the
      arbiter-override mechanism (:func:`_authorize_review_override`,
      spec.md Edge Cases) still requires durable justification when a
      caller explicitly invokes it. The override flag is no longer
      *required* to approve after a rejection, but if a caller chooses to
      use it anyway, it must still carry a reason.

    The PROCEED-with-override arm is not a refusal — it is signalled by
    :func:`_authorize_review_override`.
    """
    if req.target_lane not in _APPROVAL_LANES or req.review_artifact_name is None:
        return None
    if req.review_verdict is None:
        return RefuseExit1(
            f"{req.task_id} {req.review_artifact_name} has no parseable review verdict.\nRepair the review artifact before approving or marking done."
        )
    if req.review_verdict == "rejected" and req.skip_review_artifact_check and not (req.note.strip() if isinstance(req.note, str) else ""):
        return RefuseExit1("--skip-review-artifact-check requires --note so override evidence is durable.")
    return None


def _authorize_review_override(req: MoveTaskRequest) -> bool:
    """True when the rejected-verdict override arm proceeds (persist evidence)."""
    return (
        req.target_lane in _APPROVAL_LANES
        and req.review_artifact_name is not None
        and req.review_verdict == "rejected"
        and req.skip_review_artifact_check
        and bool(req.note.strip() if isinstance(req.note, str) else "")
    )


def _guard_feedback_file(req: MoveTaskRequest) -> RefuseExit1 | None:
    if not req.feedback_provided:
        return None
    if not req.feedback_exists:
        return RefuseExit1(f"Review feedback file not found: {req.feedback_source}")
    if not req.feedback_is_file:
        return RefuseExit1(f"Review feedback path is not a file: {req.feedback_source}")
    return None


def _planned_rollback_message(task_id: str, old_lane: str) -> str:
    """Source-aware refusal text for a ``--to planned`` move lacking feedback.

    PURE and message-only (F-51 / #3937): it reads the source lane's FSM
    adjacency solely to SHAPE the string; it never decides whether to refuse
    (that is :func:`_guard_planned_rollback`'s unconditional job). ``planned``'s
    reachability from ``old_lane`` selects the arm:

    * **Arm A** — ``planned`` IS a legal rollback target (``in_review``,
      ``in_progress``, ``approved``, ``genesis``): the honest recovery is the
      review-feedback cycle, so the existing text is returned verbatim.
    * **Arm B** — ``planned`` is NOT reachable (``blocked``, ``canceled``,
      ``done``, ``uninitialized``): name the source lane's real legal targets
      (or state it is terminal), and for ``blocked`` point at the resume edge
      ``--to in_progress`` — never tell the operator to fabricate a review file.

    The ``blocked`` resume hint is itself FSM-gated (it is emitted only while
    ``in_progress`` is a legal target of ``blocked``), so it can never advertise
    an illegal target if the state machine's edges change — the same
    misleading-refusal class F-51 exists to prevent, one layer down.
    """
    source = Lane(resolve_lane_alias(old_lane))
    state = wp_state_for(source)
    if Lane.PLANNED in state.allowed_targets():
        return (
            f"❌ Moving {task_id} to 'planned' requires review feedback.\n\n"
            "Please provide feedback:\n"
            "  1. Create feedback file: echo '**Issue**: Description' > feedback.md\n"
            f"  2. Run: spec-kitty agent tasks move-task {task_id} "
            "--to planned --review-feedback-file feedback.md\n\n"
            "This requirement cannot be bypassed with --force."
        )
    source_value = source.value
    targets = sorted(target.value for target in state.allowed_targets())
    lines = [f"❌ Cannot move {task_id} from '{source_value}' to 'planned': 'planned' is not reachable from '{source_value}'."]
    if not targets:
        lines.append(f"\n\n'{source_value}' is a terminal lane with no onward transitions.")
    else:
        legal = ", ".join(f"--to {target}" for target in targets)
        lines.append(f"\n\nLegal targets from '{source_value}': {legal}.")
        if source == Lane.BLOCKED and Lane.IN_PROGRESS in state.allowed_targets():
            lines.append(f"\nTo resume this work package, run: spec-kitty agent tasks move-task {task_id} --to in_progress.")
    return "".join(lines)


def _guard_planned_rollback(req: MoveTaskRequest) -> RefuseExit1 | None:
    if req.target_lane != Lane.PLANNED:
        return None
    if not (req.feedback_provided and req.feedback_exists and req.feedback_is_file):
        return RefuseExit1(_planned_rollback_message(req.task_id, req.old_lane))
    if not (req.feedback_content or "").strip():
        return RefuseExit1(f"Review feedback file is empty: {req.feedback_source}")
    return None


def _snapshot_unchecked_subtasks(req: MoveTaskRequest) -> tuple[str, ...] | None:
    """Incomplete subtask ids from the WP01 reduced-snapshot ``subtasks`` slot.

    FR-003 / T008: re-source the review gate's notion of "unchecked" from the
    event-sourced snapshot rather than ``tasks.md`` bytes. Returns the tuple of
    subtask ids whose reduced status is not the done-equivalent, or ``None`` to
    signal "snapshot source unavailable — use the legacy ``unchecked_subtasks``
    fallback".

    The snapshot is authoritative only when it is actually available:

    * ``req.feature_dir`` is None (the WP02 runtime window) — return ``None``
      (legacy fallback).
    * the event stream is empty or the WP has no reduced entry yet (writers not
      cut over) — return ``None`` (C-001 symmetric-window: a snapshot-first reader
      must never strand a WP whose slot has not been populated).

    A WP present in the snapshot with zero subtasks yields an empty tuple (guard
    passes — nothing to block on), mirroring ``_infer_subtasks_complete``'s
    ``total == 0`` branch. The legacy fallback is retired in WP10.
    """
    feature_dir = req.feature_dir
    if feature_dir is None:
        return None

    # Lazy import: the snapshot read is I/O and only runs once the shell supplies
    # a feature_dir, so the pure decision core keeps a minimal import graph.
    from specify_cli.status import wp_snapshot_state

    # Shared reduce->get accessor (IC-08). An empty log -> no entry -> None ->
    # legacy fallback, identical to the prior explicit empty-stream guard.
    wp_state = wp_snapshot_state(feature_dir, req.task_id)
    if wp_state is None:
        return None
    subtasks = wp_state.get("subtasks") or {}
    return tuple(str(sid) for sid, status in subtasks.items() if str(status) != str(Lane.DONE))


def _guard_subtasks(req: MoveTaskRequest) -> RefuseExit1 | None:
    if req.target_lane not in _REVIEW_GATE_LANES or req.force:
        return None
    # FR-003 / T008: prefer the reduced-snapshot subtasks slot; fall back to the
    # legacy tasks.md-derived tuple during the migration window (C-001).
    snapshot_unchecked = _snapshot_unchecked_subtasks(req)
    unchecked = snapshot_unchecked if snapshot_unchecked is not None else req.unchecked_subtasks
    if not unchecked:
        return None
    error = f"Cannot move {req.task_id} to {req.target_lane} - unchecked subtasks:\n"
    for task in unchecked:
        error += f"  - [ ] {task}\n"
    error += "\nMark these complete first:\n"
    for task in unchecked[:3]:
        error += f"  spec-kitty agent tasks mark-status {task} --status done\n"
    error += "\nOr use --force to override (not recommended)"
    return RefuseExit1(error)


def _guard_review_currency(req: MoveTaskRequest) -> RefuseExit1 | None:
    if req.target_lane not in _REVIEW_GATE_LANES or req.review_ready:
        return None
    error = f"Cannot move {req.task_id} to {req.target_lane}\n\n"
    error += "\n".join(req.review_guidance)
    if not req.force:
        error += "\n\nOr use --force to override (not recommended)"
    return RefuseExit1(error)


def _guard_done_ancestry(req: MoveTaskRequest) -> RefuseExit1 | None:
    if req.target_lane != Lane.DONE or req.done_execution_mode != "code_change":
        return None
    if req.done_merged:
        return None
    if _done_override_reason(req):
        return None
    return RefuseExit1(
        f"Cannot move {req.task_id} to done without verified merge ancestry.\n"
        f"{req.done_merge_msg}\n"
        f"If review just passed, move it to approved first:\n"
        f'  spec-kitty agent tasks move-task {req.task_id} --to approved --note "Review passed"\n'
        f'To proceed anyway, provide --done-override-reason "<why this is acceptable>".'
    )


def _guard_issue_matrix(req: MoveTaskRequest) -> RefuseExit1 | None:
    if req.target_lane in _APPROVAL_LANES and req.issue_matrix_blocker:
        return RefuseExit1(req.issue_matrix_blocker)
    return None


_GUARDS = (
    _guard_self_review,
    _guard_unsupported_skip_metadata,
    _guard_protected_branch,
    _guard_agent_ownership,
    _guard_rejected_verdict,
    _guard_feedback_file,
    _guard_planned_rollback,
    _guard_subtasks,
    _guard_review_currency,
    _guard_done_ancestry,
    _guard_issue_matrix,
)

# The two DURABLE proceed persists fire at fixed positions in the OLD guard
# sequence. Deriving the slice bounds from guard identity (not literals) keeps the
# OLD-timing signals correct if the guard order is ever reshuffled.
_REJECTED_VERDICT_GUARD_INDEX = _GUARDS.index(_guard_rejected_verdict)
_ISSUE_MATRIX_GUARD_INDEX = _GUARDS.index(_guard_issue_matrix)


def _guards_clear(req: MoveTaskRequest, guards: tuple[Any, ...]) -> bool:
    """True when none of ``guards`` refuses ``req`` (pure prefix evaluation)."""
    return all(guard(req) is None for guard in guards)


def override_persist_signal(req: MoveTaskRequest) -> bool:
    """OLD-timing gate for the review-artifact override persist (FR-004).

    In the un-refactored ``move_task`` the override evidence is written INSIDE the
    rejected-verdict guard's proceed arm (guard position 5), BEFORE the
    feedback-file, subtasks, review-currency, done-ancestry and issue-matrix
    guards run. The shell fires the persist when this returns ``True``, so a LATER
    guard's refusal (exit 1) still leaves the OLD partial write on disk.

    Returns ``True`` only when every guard that PRECEDES the rejected-verdict arm
    (self-review, unsupported-skip, protected-branch, agent-ownership) clears AND
    the rejected-verdict proceed arm authorises the override — mirroring the
    original short-circuit where an earlier guard refusal never reached the
    persist. Pure: consumes early facts only.
    """
    preceding = _GUARDS[:_REJECTED_VERDICT_GUARD_INDEX]
    return _guards_clear(req, preceding) and _authorize_review_override(req)


def arbiter_persist_signal(req: MoveTaskRequest) -> bool:
    """OLD-timing gate for the arbiter-override decision persist (FR-004).

    In the un-refactored ``move_task`` the arbiter decision JSON is written just
    BEFORE the issue-matrix guard. The shell fires the persist when this returns
    ``True``, so an issue-matrix refusal (exit 1) still leaves the OLD partial
    write on disk.

    Returns ``True`` only when every guard up to and including done-ancestry
    clears AND the move is an arbiter override — mirroring the original ordering
    where any earlier guard refusal never reached the persist. Pure: the arbiter
    fact (``is_arbiter_override``) is resolved by the shell and frozen on ``req``.
    """
    preceding = _GUARDS[:_ISSUE_MATRIX_GUARD_INDEX]
    return _guards_clear(req, preceding) and req.is_arbiter_override


# ---------------------------------------------------------------------------
# Reason / evidence / done-override helpers (pure)
# ---------------------------------------------------------------------------


def _done_override_reason(req: MoveTaskRequest) -> str | None:
    reason = req.done_override_reason
    return reason.strip() if isinstance(reason, str) else reason


def _effective_note_text(req: MoveTaskRequest) -> tuple[str | None, bool]:
    """Return ``(note_text, done_override_applied)`` folding the done-override note.

    Reproduces ``move_task``: the user note is stripped, and on a code-change
    ``done`` move with no merge ancestry but an override reason, the override note
    is appended (and a console warning is emitted — signalled by the bool).
    """
    user_note = req.note.strip() if isinstance(req.note, str) else req.note
    note_text = user_note
    if req.target_lane == Lane.DONE and req.done_execution_mode == "code_change" and not req.done_merged:
        override_reason = _done_override_reason(req)
        if override_reason:
            override_note = f"Done override: {override_reason}"
            note_text = f"{note_text} | {override_note}" if note_text else override_note
            return note_text, True
    return note_text, False


def _approval_evidence(req: MoveTaskRequest) -> dict[str, Any] | None:
    if req.target_lane not in _APPROVAL_LANES:
        return None
    return {
        "review": {
            "reviewer": req.effective_reviewer,
            "verdict": Lane.APPROVED,
            "reference": req.effective_approval_ref or "force-override",
        },
    }


# ---------------------------------------------------------------------------
# The single pure decision entry point
# ---------------------------------------------------------------------------


def decide_transition(req: MoveTaskRequest) -> TransitionOutcome:
    """Decide the move_task transition purely (FR-004 / NFR-001).

    Runs the guard sequence in the live command's order and returns the first
    :class:`RefuseExit1`; if every guard clears, returns an :class:`Emit` carrying
    the lane-hop plan, the coord ``skip_primary`` flag, approval evidence, and the
    proceed-authorisation flags the shell executes side effects from.
    """
    for guard in _GUARDS:
        refusal = guard(req)
        if refusal is not None:
            return refusal

    note_text, done_override_note = _effective_note_text(req)
    plan = build_transition_plan(
        old_lane=req.old_lane,
        target_lane=req.target_lane,
        force=req.force,
        review_feedback_pointer=None,
        arb_review_ref=None,
        note_text=note_text,
    )
    return Emit(
        plan=plan,
        skip_primary=req.skip_target_branch_commit,
        evidence_dict=_approval_evidence(req),
        note_text=note_text,
        authorize_review_override=_authorize_review_override(req),
        planned_rollback=req.target_lane == Lane.PLANNED,
        arbiter_forward=req.is_arbiter_override,
        done_override_note=done_override_note,
    )
