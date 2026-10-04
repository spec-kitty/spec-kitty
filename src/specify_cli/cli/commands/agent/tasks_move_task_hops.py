"""The ``move-task`` hop-builder seam, extracted from ``tasks_move_task`` (#5629).

Hop-planning policy builders moved VERBATIM; no behaviour changed.
``tasks_move_task`` re-imports every symbol in the ``as`` re-export form.
``_MoveTaskState`` is imported for typing only (no module-scope import of
``tasks_move_task``). Where a patch must point: see the patch-seam rule in the
``tasks_move_task_gates`` module docstring.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from specify_cli.cli.commands.agent.tasks_move_task import _MoveTaskState

from specify_cli.agent_tasks_ports import (
    TasksPorts,
)
from specify_cli.cli.commands.agent.tasks_transition_core import (
    is_review_rejection_edge,
)
from specify_cli.review.cycle import (
    synthetic_approval_ref,
    synthetic_review_ref,
)
from specify_cli.status import (
    APPROVED,
    REJECTED,
    Lane,
    ReviewOverride,
    ReviewResult,
    StatusEvent,
    emission_event_verdict,
    resolve_lane_alias,
)


def _mt_plan_review_result(st: _MoveTaskState) -> ReviewResult | None:
    """Structured review outcome justifying a force-free exit from ``in_review``.

    SC-007: WP06 owns the two ``in_review -> *`` edges re-scoped from WP02
    (``in_review -> planned`` and ``in_review -> in_progress``). It threads this
    ``ReviewResult`` (reviewer + verdict + reference) into
    :func:`build_transition_plan` (WP02's optional ``review_result`` seam) so the
    FSM accepts the backward edge force-free — the review outcome justifies the
    reverse transition instead of a raw ``force`` flag. Returns ``None`` off the
    in_review exit so every other edge is untouched (WP02 owns the other 3 edges
    and the ``build_transition_plan`` signature — WP06 only consumes them).

    A rejection to ``planned`` already minted a structured result via the review
    cycle (:attr:`rejected_review_result`); reuse it so its ``reference`` matches
    the emitted ``review_ref`` (the ``_check_review_result_consistency`` guard).
    Likewise, an automatic approval that durably verified a review-cycle artifact
    reuses that cycle's canonical result so the event references the exact evidence
    bytes. Local-only and no-cycle approval paths retain their historical caller
    reference because they have no verified durable evidence identity to claim.
    """
    from specify_cli.cli.commands.agent.tasks_move_task import _mt_resolve_reviewer_identity

    if st.old_lane != Lane.IN_REVIEW:
        return None
    if st.rejected_review_result is not None:
        return st.rejected_review_result
    reviewer = _mt_resolve_reviewer_identity(st)
    if st.target_lane in (Lane.APPROVED, Lane.DONE):
        durability_signal = st.pending_verdict_write
        if durability_signal is not None and durability_signal.durably_persisted and durability_signal.review_cycle is not None:
            return durability_signal.review_cycle.review_result
        # FR-005: route through the canonical bridge instead of hardcoding
        # the event-vocabulary literal -- this hop is an approval outcome
        # (the emission-scoped "approved" artifact verdict), so its event
        # verdict is derived the same way any other approval is.
        verdict = emission_event_verdict(APPROVED)
        reference = (st.approval_ref or synthetic_approval_ref(st.task_id)).strip() or synthetic_approval_ref(st.task_id)
    else:
        verdict = emission_event_verdict(REJECTED)
        # #4327: pointer-only — the review-feedback pointer or the synthetic
        # ``review:<WP>`` token, never the operator's ``--note`` prose (which
        # stays whole in ``reason``).
        reference = (st.review_feedback_pointer or synthetic_review_ref(st.task_id)).strip() or synthetic_review_ref(st.task_id)
    return ReviewResult(reviewer=reviewer, verdict=verdict, reference=reference)


def _mt_hop_review_result(
    st: _MoveTaskState,
    event: StatusEvent | None,
    current_event_lane: str,
    target: str,
    hop_actor: str,
) -> ReviewResult | None:
    """Select the authoritative ``ReviewResult`` when a hop leaves review."""
    rejected = st.rejected_review_result
    in_review = (event is not None and event.to_lane == Lane.IN_REVIEW) or (event is None and current_event_lane == Lane.IN_REVIEW)
    durability_signal = st.pending_verdict_write
    if is_review_rejection_edge(st.old_lane, target) and rejected is not None:
        if in_review:
            return rejected
        if durability_signal is not None and durability_signal.durably_persisted and durability_signal.review_cycle is not None:
            # A queued rejection may have resolved its plan from ``in_review``
            # before the preceding writer emits.  By the time this writer owns
            # the status transaction, the canonical lane is then ``planned``
            # and its serialized hop is ``planned -> planned``.  The durable
            # cycle created by *this* invocation remains the verdict authority:
            # preserve that exact verified result on the self-transition rather
            # than dropping it merely because another writer moved the lane.
            return durability_signal.review_cycle.review_result
    if (
        in_review
        and st.plan_review_result is not None
        and durability_signal is not None
        and durability_signal.durably_persisted
        and durability_signal.review_cycle is not None
    ):
        # A verified review-cycle is the evidence identity for this approval.
        # Prefer the canonical plan result over the older DoneEvidence approval
        # token; local-only and no-cycle paths continue through the legacy arm.
        return st.plan_review_result
    if in_review and st.evidence_dict is not None:
        review_section = st.evidence_dict.get("review", {})
        return ReviewResult(
            reviewer=review_section.get("reviewer", hop_actor),
            verdict=review_section.get("verdict", Lane.APPROVED),
            reference=review_section.get("reference", f"auto-forward:{st.task_id}"),
        )
    # SC-007: a force-free ``in_review -> {planned,in_progress}`` exit carries the
    # same structured review outcome threaded into the plan (WP06) so the
    # commit-time FSM guard accepts it without a ``force`` flag.
    if in_review and st.plan_review_result is not None:
        return st.plan_review_result
    return None


def _mt_hop_actor(st: _MoveTaskState, event: StatusEvent | None, current_event_lane: str, target: str) -> str:
    """Resolve the actor for one emit hop.

    Impl handoff preserves the WP agent (``current_agent``, unchanged). #4670/
    FR-004/FR-005 (the load-bearing site: this actor is what actually lands on
    the emitted ``StatusEvent``): a hop LEAVING ``in_review`` with ``--agent``
    omitted resolves the identity that claimed the review from the event log
    (:func:`_mt_resolve_active_reviewer_identity`) instead of silently
    defaulting to the git user -- covering both the approval
    (``in_review -> approved/done``) and rejection (``in_review -> planned``)
    verdict hops alike, since neither carries ``--to rejected`` (no such
    lane). A WP with no recorded review claim keeps the pre-existing
    ``"user"`` fallback (FR-006: never fabricate an unasserted identity).
    """
    from specify_cli.cli.commands.agent.tasks_move_task import _mt_resolve_active_reviewer_identity

    from_lane_for_hop = event.to_lane if event is not None else resolve_lane_alias(current_event_lane)
    if st.agent:
        return st.agent
    if from_lane_for_hop == Lane.IN_PROGRESS and target == Lane.FOR_REVIEW and st.current_agent:
        return st.current_agent
    if from_lane_for_hop == Lane.IN_REVIEW:
        resolved_reviewer = _mt_resolve_active_reviewer_identity(st)
        if resolved_reviewer:
            return resolved_reviewer
    return "user"


def _mt_shell_pid_baseline(pid: int) -> str | None:
    """Best-effort PID-reuse identity baseline for a claim (D3b / #2580).

    Mirrors ``frontmatter.write_shell_pid_claim``'s baseline capture WITHOUT
    resurrecting a WP-file write — WP07 owns that symbol; WP06 only records the
    baseline alongside ``shell_pid`` in the event stream (claim ``policy_metadata``
    or an ``InnerStateChanged`` delta). Degrades to ``None`` when uncapturable
    (a claim still succeeds; ``stale_detection`` treats an absent baseline as a
    legacy claim, zero regression).
    """
    from specify_cli.core.process_liveness import capture_creation_time_baseline

    baseline: str | None = capture_creation_time_baseline(pid)
    return baseline


def _mt_approval_policy_metadata(st: _MoveTaskState) -> dict[str, Any]:
    """FR-006 (IC-04): the APPROVED/DONE hop's ``policy_metadata`` sidecar.

    Gate-side decision evidence — closes the brownfield gap where an approval
    event carried no ``policy_metadata`` at all. ``tool`` is the effective
    reviewer identity already resolved onto ``st.request`` by
    ``_mt_gather_late_facts`` (``_mt_approval_facts``, auto-detected from git
    when ``--reviewer`` is absent); it falls back through ``st.reviewer`` /
    ``st.agent`` / ``st.actor`` for callers that construct ``_MoveTaskState``
    directly without running the full pipeline (unit tests). ``profile``/
    ``model`` come from ``st.resolved_binding`` — re-resolved with
    ``action="review"`` at ``_mt_resolve_targets`` for an APPROVED/DONE
    target so this never stamps the wrong (IMPLEMENT-action) profile/model
    onto a reviewer's decision. Always returns a non-``None`` dict (SC-006):
    an absent binding still yields explicit ``None`` profile/model fields
    rather than omitting the sidecar entirely.
    """
    tool = (st.request.effective_reviewer if st.request is not None else None) or st.reviewer or st.agent or st.actor or "unknown"
    binding = st.resolved_binding
    metadata: dict[str, Any] = {
        "tool": tool,
        "profile": binding.agent_profile if binding is not None else None,
        "model": binding.model if binding is not None else None,
    }
    if st.shell_pid:
        metadata["shell_pid"] = st.shell_pid
    return metadata


def _mt_hop_policy_metadata(st: _MoveTaskState, target: str) -> dict[str, Any] | None:
    """Resolve the ``policy_metadata`` sidecar for one emit hop.

    FR-004: the claim triple (``shell_pid``/``shell_pid_created_at``/``agent``)
    rides the real ``planned -> claimed`` transition's ``policy_metadata`` — the
    reducer's claim fold extracts those exact keys into the snapshot runtime
    slots (``build_claim_policy_metadata`` is the WP01 shape authority). The
    pre-review-gate metadata rides the ``* -> for_review`` hop. FR-006: the
    APPROVED/DONE hop carries the gate-side decision-evidence sidecar
    (``_mt_approval_policy_metadata``, IC-04). ``None`` otherwise.
    """
    if target == Lane.CLAIMED and st.shell_pid:
        from specify_cli.status import build_claim_policy_metadata

        pid = int(st.shell_pid)
        baseline = _mt_shell_pid_baseline(pid)
        claim_metadata: dict[str, Any] = build_claim_policy_metadata(pid, baseline or "", st.agent or st.actor or "unknown")
        return claim_metadata
    if target == Lane.FOR_REVIEW and st.pre_review_gate_metadata is not None:
        return {"pre_review_gate": st.pre_review_gate_metadata}
    if target in (Lane.APPROVED, Lane.DONE):
        return _mt_approval_policy_metadata(st)
    return None


def _mt_hop_reason_source(st: _MoveTaskState, target: str) -> str | None:
    """Resolve the ``reason_source`` provenance discriminator for one emit hop.

    FR-001 (mission completion-terminal-state): a cancellation is accept-eligible
    only when the operator authored the reason via ``--note``. Scoped to the
    ``canceled`` target — every other lane hop leaves ``reason_source`` ``None``
    (provenance is not tracked for non-cancel moves; the synthetic default reason
    they carry is unchanged). A non-empty operator note (trimmed, so a
    whitespace-only ``--note`` is not operator-authored, T002) yields
    ``"operator"``; a bare ``--force`` cancel with no note — or a whitespace note
    — yields ``"synthetic"``, which is what makes FR-003's blocker reachable
    through the canonical command.
    """
    if resolve_lane_alias(target) != Lane.CANCELED:
        return None
    note = st.note.strip() if isinstance(st.note, str) else None
    return "operator" if note else "synthetic"


def _binding_role_for_lane(lane: Lane | str) -> str | None:
    """Map a target lane to its resolved-binding role.

    Shared by :func:`_mt_emit_transitions` (in ``tasks_move_task_executor``; the live transition-emit path,
    which needs the ``None`` case to skip binding-role annotation for any
    lane that is neither a claim nor a review-claim) and
    :func:`_mt_reassignment_binding_fields` (the off-transition reassignment
    path, which always wants a role and falls back to ``"implementer"`` at
    its own call site — collapses the previously duplicated role map).

    FR-006 (IC-04): APPROVED/DONE are also reviewer-role decisions — the
    approving/completing actor, never the implementer — so the resolved
    binding's structured actor (``build_self_asserting_actor``) and
    annotation delta are stamped there too, symmetric with IN_REVIEW.
    """
    if lane == Lane.CLAIMED:
        return "implementer"
    if lane in (Lane.IN_REVIEW, Lane.APPROVED, Lane.DONE):
        return "reviewer"
    return None


def _mt_hop_review_ref(emit_review_ref: str | None, target: str, hop_review_result: ReviewResult | None) -> str | None:
    """FR-006 (IC-04): resolve one hop's ``review_ref``.

    ``emit_review_ref`` (the plan-level value ``build_transition_plan`` sets
    ONLY for backward/rollback hops) always wins when already populated. For
    a forward APPROVED/DONE hop it is derived from the SAME ``hop_review_
    result`` object this hop already threads onto the request's
    ``review_result`` — never independently recomputed — so
    ``_check_review_result_consistency``'s "review_ref must match
    review_result.reference" guard can never observe a mismatch (an earlier
    approach rebuilt ``st.emit_plan`` with ``st.plan_review_result``
    instead, which is a SEPARATE computation from ``hop_review_result`` on
    the non-durably-persisted approval path — see the note on
    ``_mt_finalize_plan``'s plan-rebuild trigger for the exact divergence
    that tripped).
    """
    if emit_review_ref is not None:
        return emit_review_ref
    if target not in (Lane.APPROVED, Lane.DONE) or hop_review_result is None:
        return None
    candidate = getattr(hop_review_result, "reference", None)
    return candidate if isinstance(candidate, str) and candidate.strip() else None


def _mt_reassignment_binding_fields(st: _MoveTaskState) -> dict[str, Any]:
    """Resolved actual for an off-transition agent reassignment."""
    if not st.agent or st.resolved_binding is None:
        return {}
    role = _binding_role_for_lane(st.target_lane) or "implementer"
    delta = st.resolved_binding.to_delta(role=role)
    binding_fields: dict[str, Any] = delta.to_dict()
    return binding_fields


def _build_claim_review_override(st: _MoveTaskState, ports: TasksPorts) -> dict[str, Any]:
    """Compute the rollback-to-``planned`` off-axis field additions.

    SIDE EFFECT (#3578, adversarial review finding 1a): besides returning the
    ``additions`` dict, this records the operator signal for the three deltas on
    ``st.rollback_reset_summary`` (read later by :func:`_mt_output`). The summary
    is built HERE because this is the one place that resolves the reset map, and
    the completion split it carries must read the PRE-reset snapshot — which is
    still intact at this point (the reset delta is not emitted until
    :func:`_mt_emit_runtime_state` returns from this helper).

    Campsite extraction (WP02, verdict-seam-boundary-hardening-01KZG179,
    T007/NFR-004): pulled out of :func:`_mt_emit_runtime_state` (cc=14, close
    to the 15 ceiling) so that function keeps headroom.

    - The ``subtasks`` reset (if any) re-blocks the review gate off the
      snapshot (#2513, via the log — not the checkbox).
    - ``#2512`` / partition-authority-residuals (#2960 follow-up): a rollback
      to ``planned`` RELEASES the prior claim so the rolled-back WP exposes no
      live claim marker. Field repro: an agent process was killed (macOS
      idle-sleep) leaving ``agent``/``shell_pid`` behind; the rollback reset
      the lane but not the claim, so the next resume failed
      ``LANE_ALLOCATION_FAILED``. With the god-write cut the claim now lives
      in the reduced snapshot (the claim transition's ``policy_metadata``),
      and it was released in NEITHER surface — so the release is emitted here
      off-axis as an ``InnerStateChanged`` carrying the explicit
      ``release_runtime_claim=True`` marker (see ``WPInnerStateDelta`` /
      ``_apply_annotation_delta``), which the reducer honors as a real clear
      of the claim triple, DISTINCT from a bare ``agent=""`` corruption
      no-op (#2960). Set UNCONDITIONALLY — a SAME-move re-plant of a fresh
      claim (an explicit ``--agent``/``--shell-pid`` override, already staged
      in the caller's ``fields`` dict before this helper's return value is
      merged in) still wins: the reducer applies the release clear BEFORE its
      replace-slot loop, so a concrete value present in the same delta
      overwrites the just-cleared slot. This helper therefore no longer needs
      to inspect the caller's existing fields to decide whether to release —
      the override precedence lives in the reducer, not here.
    - The ``review`` runtime slot records durable evidence that a REJECTED
      review was superseded by an approval override
      (``_persist_review_artifact_override``). A rollback to ``planned`` --
      whether via a fresh rejection (the common case) or any other route
      back to ``planned`` -- means that prior "superseded by approval" note
      no longer describes the WP's state, so it is released here alongside
      the claim triple: an all-empty ``ReviewOverride`` sentinel, which
      ``_apply_annotation_delta`` (reducer) folds to a cleared (``None``)
      snapshot slot rather than persisting an empty override. Without this a
      reader of ``status.json`` could see a withdrawn "approved" verdict on a
      WP that is actually back in ``planned`` awaiting rework.
    """
    from specify_cli.cli.commands.agent.tasks_move_task_executor import _mt_build_rollback_summary, _mt_rollback_subtasks_reset

    additions: dict[str, Any] = {}
    reset = _mt_rollback_subtasks_reset(st, ports)
    if reset:
        additions["subtasks"] = reset
    additions["release_runtime_claim"] = True
    additions["review"] = ReviewOverride(at="", actor="", wp_id="", reason="")
    # #3578: capture the operator signal for all three otherwise-silent deltas
    # (subtask reset + claim release + review-override clear) so ``_mt_output``
    # can surface them as a human line + JSON fields. Set unconditionally on a
    # rollback-to-``planned`` — the siblings apply even for an empty roster.
    st.rollback_reset_summary = _mt_build_rollback_summary(st, ports, reset)
    return additions
