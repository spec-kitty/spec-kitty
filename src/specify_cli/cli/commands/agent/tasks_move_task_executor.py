"""The ``move-task`` executor seam, extracted from ``tasks_move_task`` (#5629).

Plan finalisation, transition emission, persistence, review-lock release and
rollback-summary helpers moved VERBATIM; no behaviour changed.
``tasks_move_task`` re-imports the moved symbols from here so existing
``tasks_move_task.<name>`` references keep resolving. ``_MoveTaskState`` is
imported for typing only. Where a patch must point: see the patch-seam rule in
the ``tasks_move_task_gates`` module docstring.

Import-cycle invariant: this module imports ``tasks_move_task_hops`` at module
scope, but ``tasks_move_task_hops`` reaches names from this module only via
function-local (lazy) imports. That must never become a module-scope import,
or the two modules form an import cycle.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

from specify_cli.cli.commands.agent.tasks_move_task_hops import (
    _binding_role_for_lane,
    _build_claim_review_override,
    _mt_hop_actor,
    _mt_hop_policy_metadata,
    _mt_hop_reason_source,
    _mt_hop_review_ref,
    _mt_hop_review_result,
    _mt_plan_review_result,
    _mt_reassignment_binding_fields,
    _mt_shell_pid_baseline,
)

if TYPE_CHECKING:
    from specify_cli.cli.commands.agent.tasks_move_task import _MoveTaskState

from mission_runtime import MissionArtifactKind
from specify_cli.agent_tasks_ports import (
    MissionHandle,
    TasksPorts,
)
from specify_cli.cli.commands.agent.tasks_transition_core import (
    build_transition_plan,
    is_review_rejection_edge,
)
from specify_cli.cli.commands.agent.tasks_verdict_persistence import (
    _persist_approved_review_cycle,
    persist_rejected_review_cycle_for_rollback,
)
from specify_cli.core.commit_guard import GuardCapability
from specify_cli.status import (
    Lane,
    StatusEvent,
    TransitionRequest,
    WPInnerStateDelta,
    _actor_key,
    mission_lock_key,
    resolve_lane_alias,
)


def _mt_persist_rejection_cycle(st: _MoveTaskState, ports: TasksPorts) -> None:
    """Persist the rejection review cycle for a review-rejection edge (#4899).

    Campsite tidy-first extraction (WP01 T004) of the pointer-restore-and-
    persist block formerly inline in :func:`_mt_finalize_plan`. Behaviour-
    preserving: the caller (``decision.is_review_rejection and
    st.resolved_feedback_source is not None``) is unchanged; this is the
    unconditional body only.

    `persist_rejected_review_cycle_for_rollback` (tasks_verdict_persistence,
    frozen boundary) writes the rejected artifact's ``reviewer_agent`` from
    ``st.agent`` alone, which ignores a caller-declared ``--reviewer`` that
    differs from ``--agent`` (the WP actor driving this CLI invocation, not
    necessarily the reviewer). Thread the already-resolved reviewer identity
    through ``st.agent`` for just this call, then restore it immediately so
    every OTHER consumer of ``st.agent`` (the real actor/agent facts) is
    unaffected.
    """
    from specify_cli.cli.commands.agent.tasks_move_task import _mt_resolve_reviewer_identity

    declared_agent = st.agent
    st.agent = _mt_resolve_reviewer_identity(st)
    try:
        st.pending_verdict_write = persist_rejected_review_cycle_for_rollback(st, ports)
    finally:
        st.agent = declared_agent


def _mt_finalize_plan(st: _MoveTaskState, ports: TasksPorts) -> None:
    """Execute the decision's authorised side-effect *inputs* and finalize the plan.

    The override/arbiter persists already fired at their OLD guard positions — they
    are NOT repeated here. Only the planned-rollback review cycle (which produces
    the feedback pointer) runs, then the plan is rebuilt when a side-effect produced
    a ``review_ref``.

    T004/T005 (review-verdict-write-integrity-01KZ1CGF): both the rejection
    write AND the ordinary approval write now route through the generalized,
    commit-durable ``create_rejected_review_cycle`` — ``ports.coord`` (the
    ``CoordCommitRouter``) is threaded in as ``commit_router`` so every write
    this function makes is actually git-committed (closes #2697), not left
    untracked.

    WP06 (verdict-seam extraction): the former nested
    ``_persist_approved_review_cycle`` closure and the adjacent
    planned-rollback persist block now live in ``tasks_verdict_persistence``
    as :func:`tasks_verdict_persistence._persist_approved_review_cycle`
    (de-nested into a top-level function, same name, per C-003 ruling
    DM-01KZ3VBAWZ1B5XC25EDGN99BJP CONDITION 2) and
    :func:`persist_rejected_review_cycle_for_rollback`; this function calls
    into both.

    WP11 (T048, ``DM-01KZ6JE62Q6CQ24DMBX8KZZ5R9``): both writers now return a
    ``VerdictDurabilitySignal`` describing what they just wrote (or ``None``
    for the approval no-op guard) — captured onto ``st.pending_verdict_write``
    so ``_do_move_task`` can revert an already-committed write if the LATER
    ``_mt_execute`` transition-emit fails. The two calls are mutually
    exclusive per lane (a planned rollback targets ``planned``; the approval
    writer only fires for ``APPROVED``/``DONE``), so at most one assigns it.
    """
    from specify_cli.cli.commands.agent import tasks as _tasks
    from specify_cli.cli.commands.agent.tasks_move_task import _mt_resolve_active_reviewer_identity

    assert st.decision is not None
    decision = st.decision
    st.emit_plan = decision.plan
    st.evidence_dict = decision.evidence_dict
    st.note_text = decision.note_text
    # #4670/FR-005: an agent-driven completion that omits --agent no longer
    # silently attributes the verdict to the git user -- it resolves the
    # identity that actually claimed the review (for_review -> in_review)
    # from the event log first. A WP with no recorded review claim (or a
    # claim genuinely made by a human) falls through to "user" unchanged
    # (FR-006: never fabricate an agent identity that was never asserted).
    st.actor = st.agent or _mt_resolve_active_reviewer_identity(st) or "user"
    st.canonical_lane = decision.plan.canonical_lane

    if decision.is_review_rejection and st.resolved_feedback_source is not None:
        _mt_persist_rejection_cycle(st, ports)
    if st.target_lane in (Lane.APPROVED, Lane.DONE):
        st.pending_verdict_write = _persist_approved_review_cycle(st, ports)
        durability_signal = st.pending_verdict_write
        if durability_signal is not None and durability_signal.durably_persisted and durability_signal.review_cycle is not None and st.evidence_dict is not None:
            # DoneEvidence and ReviewResult share one approval identity. Once
            # Git verification succeeds, replace the earlier caller token with
            # the canonical review-cycle pointer; the token remains preserved
            # in the committed artifact body without becoming event authority.
            canonical_result = durability_signal.review_cycle.review_result
            st.evidence_dict["review"] = {
                "reviewer": canonical_result.reviewer,
                "verdict": canonical_result.verdict,
                "reference": canonical_result.reference,
            }
    if decision.done_override_note and not st.json_output:
        _tasks.console.print("[yellow]⚠️  Proceeding with done override; reason recorded in history/events.[/yellow]")
    # SC-007: WP06 owns the two ``in_review -> *`` edges re-scoped from WP02.
    # Build the structured review outcome BEFORE the plan rebuild so it can be
    # threaded into ``build_transition_plan`` (WP02's optional ``review_result``
    # seam) — the FSM then accepts those backward edges force-free instead of
    # promoting ``emit_force=True``.
    st.plan_review_result = _mt_plan_review_result(st)
    if decision.is_review_rejection or decision.arbiter_forward:
        # FR-006 (IC-04) NOTE: a forward ``in_review -> {approved,done}`` edge
        # is deliberately NOT added to this trigger. An earlier attempt widened
        # it here and threaded ``st.plan_review_result.reference`` into
        # ``emit_review_ref`` via ``build_transition_plan`` — but
        # ``st.plan_review_result`` (computed above) and the ``hop_review_
        # result`` ``_mt_emit_transitions`` independently selects via
        # ``_mt_hop_review_result`` are NOT always the same object: on a
        # non-durably-persisted write (``--no-auto-commit`` / local-only),
        # ``_mt_hop_review_result`` falls back to ``st.evidence_dict["review"]``
        # (built from ``effective_approval_ref``, the pointer-only
        # ``--approval-ref`` / synthetic-token value, #4327)
        # while ``_mt_plan_review_result``'s non-durable fallback does not —
        # two independently-computed reference strings that can diverge,
        # tripping ``_check_review_result_consistency``'s "review_ref must
        # match review_result.reference" guard (caught by the REAL CLI in
        # ``tests/integration/test_review_cycle_rejection_only.py::
        # test_approving_a_rejected_wp_writes_no_verdict_artifact`` — the
        # FAKE-ports orchestration test never exercises that guard). FR-006's
        # ``review_ref`` is instead derived per-hop, directly from the SAME
        # ``hop_review_result`` object that becomes the request's
        # ``review_result`` — see ``_mt_emit_transitions`` below — guaranteeing
        # consistency by construction rather than by keeping two independent
        # computations in sync.
        st.emit_plan = build_transition_plan(
            old_lane=str(st.old_lane),
            target_lane=str(st.target_lane),
            force=st.force,
            review_feedback_pointer=st.review_feedback_pointer,
            arb_review_ref=st.arb_review_ref,
            note_text=st.note_text,
            review_result=st.plan_review_result,
        )


def _mt_emit_transitions(st: _MoveTaskState, ports: TasksPorts) -> None:
    """Emit each lane hop through the coord WRITE ``commit_status`` capability."""
    from specify_cli.cli.commands.agent import tasks as _tasks
    from specify_cli.cli.commands.agent.tasks_move_task import _mt_current_event_lane, _mt_owned_workspace

    assert st.emit_plan is not None
    emit_plan = st.emit_plan
    emit_force = emit_plan.emit_force
    emit_reason = emit_plan.emit_reason
    emit_review_ref = emit_plan.emit_review_ref
    current_event_lane = _mt_current_event_lane(st)
    event: StatusEvent | None = None
    final_hop_actor = st.actor
    # #5100 R-10: the honest stamp for every hop this call emits -- resolved
    # ONCE (the WP's lane assignment does not change mid-call), reusing the
    # SAME owned-vs-lane branch every other workspace read in this module
    # takes, so it can never drift from what those reads report.
    from specify_cli.lanes.persistence import CorruptLanesError, MissingLanesError

    try:
        emit_workspace = _mt_owned_workspace(st) if st.owned is not None else _tasks.resolve_workspace_for_wp(st.main_repo_root, st.mission_slug, st.task_id)
        emit_execution_mode = emit_workspace.status_execution_mode
    except (ValueError, FileNotFoundError, MissingLanesError, CorruptLanesError):
        # Mirrors the SAME tolerant fallback ``_mt_commit_lane_deliverables`` /
        # ``_mt_done_ancestry_facts`` already apply for a mission without a
        # resolvable lane workspace (missions without lanes.json included) --
        # the stamp degrades to the model default rather than failing the
        # transition this function's caller has already committed to emitting.
        emit_execution_mode = "worktree"
    for target in emit_plan.transition_targets:
        st.authoritative_lane_at_emit = event.to_lane if event is not None else Lane(resolve_lane_alias(current_event_lane))
        hop_actor = _mt_hop_actor(st, event, current_event_lane, target)
        hop_review_result = _mt_hop_review_result(st, event, current_event_lane, target, hop_actor)
        hop_policy_metadata = _mt_hop_policy_metadata(st, target)
        binding_role = _binding_role_for_lane(target)
        transition_actor: str | dict[str, str | None] = hop_actor
        annotation_delta = None
        if binding_role is not None and st.resolved_binding is not None:
            from specify_cli.status import build_self_asserting_actor

            # FR-005: route the compact ``--agent`` value through the single
            # self-asserting actor seam — only the parsed BARE tool reaches
            # actor.tool, absent segments stay None, and the dispatch binding
            # wins over the self-asserted parse.
            transition_actor = build_self_asserting_actor(
                role=binding_role,
                agent=st.agent,
                fallback_tool=hop_actor,
                binding=st.resolved_binding,
            )
            annotation_delta = st.resolved_binding.to_delta(role=binding_role)
            if target == Lane.CLAIMED and st.agent:
                # #4673/T012: thread the claim owner through the SAME
                # annotation-delta channel ``role`` already rides here, not only
                # the transition's ``policy_metadata`` sidecar. The shared
                # spec-kitty-events reducer folds ALL transitions first, THEN
                # ALL ``InnerStateChanged`` annotations in one dedicated
                # post-pass (never interleaved by timestamp,
                # ``diary.reduce_parsed`` steps 3-4) — so a stale
                # ``release_runtime_claim`` annotation from an EARLIER
                # rejection is replayed AFTER this claim's
                # ``policy_metadata``-derived ``agent`` has already landed in
                # the transition pass, clobbering it back to falsy
                # (``_CLAIM_RELEASE_SLOTS``). Carrying ``agent`` on this
                # transition's own ``annotation_delta`` puts a fresh,
                # later-timestamped replacement value in the SAME post-pass
                # the stale release runs in, so the latest-wins replace-slot
                # rule (``_apply_annotation_delta``) lets it win regardless of
                # the non-interleaved fold order — the identical immunity
                # ``role`` already has (C-006 mechanism (b)).
                annotation_delta = replace(annotation_delta, agent=st.agent)
        if target == Lane.CLAIMED and st.shell_pid:
            # FR-004: the claim triple rode this transition's policy_metadata —
            # do NOT re-emit it as an off-axis InnerStateChanged delta.
            st.claim_emitted = True
        event = ports.coord.commit_status(
            TransitionRequest(
                feature_dir=st.feature_dir,
                mission_slug=st.mission_slug,
                wp_id=st.task_id,
                to_lane=target,
                actor=transition_actor,
                force=emit_force,
                reason=emit_reason,
                reason_source=_mt_hop_reason_source(st, target),
                evidence=st.evidence_dict if target in (Lane.APPROVED, Lane.DONE) else None,
                policy_metadata=hop_policy_metadata,
                review_ref=_mt_hop_review_ref(emit_review_ref, target, hop_review_result),
                workspace_context=f"move-task:{st.repo_root}",
                subtasks_complete=(True if target in (Lane.FOR_REVIEW, Lane.APPROVED) and not emit_force else None),
                implementation_evidence_present=(True if target in (Lane.FOR_REVIEW, Lane.APPROVED) and not emit_force else None),
                execution_mode=emit_execution_mode,
                repo_root=st.main_repo_root,
                # #3866: thread the validated fact so the per-hop identity
                # derivation does not re-run the ownership validation.
                owned=st.owned,
                review_result=hop_review_result,
                annotation_delta=annotation_delta,
            ),
            capability=GuardCapability.STANDARD,
        ).event
        st.transition_applied = True
        final_hop_actor = hop_actor
        # review_ref only applies to the (first) rollback hop, never forward hops.
        emit_review_ref = None
    st.event = event
    st.final_hop_actor = final_hop_actor
    _mt_warn_approval(st)


def _mt_warn_approval(st: _MoveTaskState) -> None:
    """Tell the operator now when this approval recorded no lane head (#5668) or is a forced approval that is no review (#5721)."""
    import typer

    from specify_cli.cli.commands.agent import tasks as _tasks
    from specify_cli.consolidation.approved_bound import approval_warnings

    def _load() -> list[StatusEvent]:
        return list(
            _tasks.read_events_transactional(
                feature_dir=st.feature_dir,
                mission_slug=st.mission_slug,
                repo_root=st.main_repo_root,
                owned=st.owned,
            )
        )

    for warning in approval_warnings(st.event, _load, repo_root=st.main_repo_root, mission_slug=st.mission_slug):
        typer.echo(warning, err=True)


@dataclass(frozen=True)
class _RollbackResetSummary:
    """Operator signal for the otherwise-silent rollback-to-``planned`` delta (#3578).

    A rollback to ``planned`` applies three deltas the operator never saw: it
    resets every roster subtask to ``planned`` (so the review gate re-blocks off
    the snapshot, #2513), releases the runtime claim (``release_runtime_claim``),
    and clears the review-override slot. Each half of the fail-loud discipline
    (epics #3410/#3549) needs a signal — this value object carries the count and
    the two sibling actions, plus the FR-003 work-state split: ``previously_
    completed`` names roster ids that were DONE in an earlier cycle (re-verify,
    do not rebuild), kept distinct from ``never_completed`` ones so the flat reset
    no longer conflates work-state with review-state (SC-003).
    """

    reset_ids: tuple[str, ...]
    previously_completed: tuple[str, ...]
    never_completed: tuple[str, ...]
    claim_released: bool
    review_override_cleared: bool

    @property
    def reset_count(self) -> int:
        return len(self.reset_ids)


def _mt_build_rollback_summary(st: _MoveTaskState, ports: TasksPorts, reset: Mapping[str, Lane]) -> _RollbackResetSummary:
    """Compute the #3578 operator summary for a rollback-to-``planned`` delta.

    ``reset`` is the already-resolved reset map (its keys are the authored
    roster). The work-state split reads the PRE-reset reduced snapshot: a roster
    id whose snapshot status is DONE was completed in an earlier cycle. The read
    fails closed exactly like the review gate — an absent/silent snapshot reports
    every roster id incomplete (never a false "already done") — so an operator is
    never told work is preserved when it is not.
    """
    from specify_cli.core.subtask_rows import unchecked_subtask_ids_from_snapshot

    roster = tuple(reset.keys())
    previously_completed: tuple[str, ...] = ()
    never_completed: tuple[str, ...] = ()
    if roster:
        handle = MissionHandle(repo_root=st.main_repo_root, mission_slug=st.mission_slug, owned=getattr(st, "owned", None))
        feature_dir = ports.fs.planning_read_dir(handle, kind=MissionArtifactKind.TASKS_INDEX)
        not_done = set(unchecked_subtask_ids_from_snapshot(feature_dir, st.task_id, roster))
        previously_completed = tuple(tid for tid in roster if tid not in not_done)
        never_completed = tuple(tid for tid in roster if tid in not_done)
    return _RollbackResetSummary(
        reset_ids=roster,
        previously_completed=previously_completed,
        never_completed=never_completed,
        claim_released=True,
        review_override_cleared=True,
    )


def _mt_rollback_subtasks_reset(st: _MoveTaskState, ports: TasksPorts) -> dict[str, Lane]:
    """Subtask-reset delta for a rollback to ``planned`` (#2513, via the log).

    A WP rolled back to ``planned`` must be fully re-implemented — leaving its
    completion state intact would let the review gate pass immediately on the
    next ``for_review`` with no work re-done. With subtask completion
    event-sourced (WP04), the intent is now expressed as an ``InnerStateChanged``
    ``subtasks`` delta resetting every roster row to ``planned`` (the gate
    re-blocks off the snapshot) rather than unchecking the ``tasks.md`` checkbox
    bytes — so ``tasks.md`` stays byte-stable (AC-5).

    The roster (which task ids belong to this WP) is the authored WP-file
    ``subtasks:`` frontmatter list — static design intent — read through the
    TASKS_INDEX (primary) read dir, never ``Path.cwd()`` (SC-008 / #2647).
    Returns an empty mapping only for an explicitly authored empty roster.
    """
    from specify_cli.core.subtask_rows import authored_subtask_roster

    handle = MissionHandle(repo_root=st.main_repo_root, mission_slug=st.mission_slug, owned=getattr(st, "owned", None))
    feature_dir = ports.fs.planning_read_dir(handle, kind=MissionArtifactKind.TASKS_INDEX)
    roster = authored_subtask_roster(feature_dir, st.task_id)
    return dict.fromkeys(roster, Lane.PLANNED)


def _mt_emit_runtime_state(st: _MoveTaskState, ports: TasksPorts) -> None:
    """Emit the move-task runtime-state deltas as off-axis ``InnerStateChanged``.

    The god-write is cut (FR-006/FR-007/FR-008, AC-5): the WP file stops carrying
    runtime state — the event log carries it.

    - The claim triple (``shell_pid``/``shell_pid_created_at``/``agent``) for a
      real ``planned -> claimed`` transition already rode that transition's
      ``policy_metadata`` sidecar (FR-004; see :func:`_mt_hop_policy_metadata`)
      and is flagged on ``st.claim_emitted`` — it is NOT re-emitted here. A
      reassignment/refresh OUTSIDE the claim transition is an off-axis delta.
    - ``assignee``, the Activity-Log ``note`` (FR-007), and the ``tracker_refs``
      **union** (FR-006) are off-axis deltas.
    - A rollback to ``planned`` carries a ``subtasks`` reset so the review gate
      re-blocks off the snapshot (#2513, via the log — not the checkbox).

    Every emit resolves its write target from ``st.feature_dir`` — resolved from
    stored topology in :func:`_mt_resolve_targets` — never ``Path.cwd()``
    (SC-008 / #2647; ``emit_inner_state_changed`` re-canonicalizes it there too).

    FR-007 (#2939): on a durable-commit move-task (``st.resolved_auto_commit``
    True) the post-transition annotation is emitted through the commit-durable
    ``emit_inner_state_changed_transactional`` — the sibling of the lane hop's
    own ``emit_status_transition_transactional`` — so on a coordination
    topology the coord ``status.events.jsonl`` / ``status.json`` are committed in
    their OWN atomic status transaction (mirroring the transition), leaving no
    dirty status tree when ``move-task`` returns. On a coord-less topology it
    degrades to the same uncommitted write the pre-fix path used (no-op parity).

    ``st.resolved_auto_commit`` False (``--no-auto-commit`` / a caller that
    intentionally bypasses the commit/router leg entirely) skips the
    transactional path altogether and calls the plain, uncommitted
    ``emit_inner_state_changed`` directly — the annotation still gets
    written+materialized, it just is not routed through a
    ``BookkeepingTransaction`` that would try to resolve/materialize a coord
    worktree the caller never asked to touch (regression #3460: a coord
    mission with a declared-but-not-yet-materialized coordination worktree
    made the transactional emit raise ``BookkeepingWorktreeMissing`` even
    though auto_commit was off and no commit was ever wanted).

    The generic ``emit_inner_state_changed`` stays partition-agnostic (untouched);
    the durability decision lives at this caller/commit layer.
    """
    from specify_cli.coordination.status_transition import emit_runtime_annotation

    fields: dict[str, Any] = {}
    if not st.claim_emitted:
        # #4673/T011: a rollback to ``planned`` (rejection) ALSO carries
        # ``release_runtime_claim=True`` in this SAME delta (added below via
        # ``_build_claim_review_override``). The reducer applies that release
        # clear BEFORE its replace-slot loop, so a concrete ``agent`` value
        # present in the SAME delta overwrites the just-cleared slot — by
        # design, for a genuine same-move re-plant (an explicit fresh claim
        # on the rollback itself, ``test_rollback_with_explicit_agent_
        # replants_claim``). But an ORDINARY rejection's ``st.agent`` is just
        # the REVIEWER re-asserting their OWN already-current identity (the
        # reviewer's own review-claim already stamped the runtime ``agent``
        # slot to their identity before the rejection runs) — stamping it
        # again here re-clobbers the release right back to the reviewer, so
        # the slot never actually shows "released" (#4673's precise live
        # root). The two cases are distinguished by whether ``st.agent`` is
        # genuinely NEW relative to the prior owner (``st.current_agent``,
        # resolved before this move): a same-identity restamp on a
        # ``PLANNED`` target is suppressed (lets the release take effect); a
        # DIFFERING identity on a ``PLANNED`` target is a real re-plant and
        # still wins over the release, exactly as before.
        #
        # #4899 (WP01, Fold 5 -- KEEP AS-IS, deliberately NOT routed through
        # ``is_review_rejection_edge``): the re-implement edge (in_review ->
        # in_progress) intentionally RETAINS the implementer's runtime claim
        # (resume-in-place) rather than releasing it to the pool -- routing
        # this restamp-suppress check through the rejection-edge predicate
        # would widen the release to the re-implement edge too and regress
        # resume-in-place. Only the ``PLANNED`` target release-suppress
        # window is in scope here; see the truth-table cell in
        # ``test_tasks_move_task_seam.py`` asserting the claim survives.
        if st.agent and not (st.target_lane == Lane.PLANNED and _actor_key(st.agent) == _actor_key(st.current_agent)):
            fields["agent"] = st.agent
            fields.update(_mt_reassignment_binding_fields(st))
        if st.shell_pid:
            pid = int(st.shell_pid)
            fields["shell_pid"] = pid
            baseline = _mt_shell_pid_baseline(pid)
            if baseline is not None:
                fields["shell_pid_created_at"] = baseline
    if st.assignee:
        fields["assignee"] = st.assignee
    # FR-007: a USER-supplied Activity-Log note becomes a ``note`` annotation. The
    # synthetic ``Moved to <lane>`` fallback the old god-write wrote is already
    # captured by the transition's ``reason`` — re-emitting it would only add a
    # redundant trailing annotation, so it is not emitted off-axis (the WP file
    # no longer carries runtime state at all -- the event log is sole authority).
    if st.note_text:
        fields["note"] = st.note_text
    if st.tracker_ref_values:
        fields["tracker_refs"] = list(st.tracker_ref_values)
    # #4899 (WP01, Fold 5 -- KEEP AS-IS): claim-review-override stays scoped
    # to the ``PLANNED`` target only. The re-implement edge (in_review ->
    # in_progress) does not release the runtime claim to the pool -- it
    # resumes in place with the SAME implementer -- so this is deliberately
    # NOT routed through ``is_review_rejection_edge``.
    if st.target_lane == Lane.PLANNED:
        fields.update(_build_claim_review_override(st, ports))

    delta = WPInnerStateDelta(**fields)
    if delta.is_empty():
        return
    # An owned run is always auto-commit (refused otherwise while resolving
    # targets); #3866 threads the validated fact so the annotation's identity
    # derivation does not re-run the ownership validation. The transactional-vs-
    # plain selection lives in the coordination-owned ``emit_runtime_annotation``.
    emit_runtime_annotation(
        owned=getattr(st, "owned", None),
        auto_commit=st.resolved_auto_commit,
        feature_dir=st.feature_dir,
        wp_id=st.task_id,
        delta=delta,
        actor=st.final_hop_actor or st.actor,
        mission_slug=st.mission_slug,
        repo_root=st.main_repo_root,
    )


def _mt_persist_wp_file(st: _MoveTaskState, ports: TasksPorts) -> None:
    """Record the move-task runtime state — event-only (IC-04 flip complete).

    Runtime state is emitted as ``InnerStateChanged`` annotations (plus the claim
    ``policy_metadata`` that rode the transition). Post-cutover the WP file no
    longer carries runtime state — the event log is the sole authority. WP04 (IC-03)
    made the readers unconditional and dropped the retired phase-authority
    predicate + facade export; this WP removes the last consumer of that gate here,
    so the former early-return (once the flag was on) and the ``_mt_dual_write_wp_file``
    god-write it guarded (``agent``/``assignee``/``shell_pid`` + Activity-Log) are
    both deleted (FR-007, D-14). ``_mt_emit_runtime_state`` (the off-axis emit) is unchanged.
    """
    assert st.wp is not None and st.decision is not None
    _mt_emit_runtime_state(st, ports)


def _mt_release_review_lock(st: _MoveTaskState) -> None:
    """FR-017 / FR-018: release the review lock when review terminates.

    Placed AFTER the lane-transition commit so a failed release never rolls back
    the recorded transition; failures are logged, never fatal.
    """
    from specify_cli.cli.commands.agent import tasks as _tasks
    from specify_cli.cli.commands.agent.tasks_move_task import _mt_owned_workspace

    # #4899 (WP01, Fold 4): the re-implement edge (in_review -> in_progress)
    # also terminates review and must release the lock, or a stuck lock
    # blocks the WP's next for_review -> in_review claim. Extended via the
    # SAME rejection-edge predicate rather than adding Lane.IN_PROGRESS to
    # ``release_to`` outright -- that would also (wrongly) release the lock
    # for an ordinary claimed -> in_progress / for_review -> in_progress
    # move; the predicate scopes the extra release to exactly the
    # in_review-sourced re-implement edge.
    release_from = (Lane.FOR_REVIEW, Lane.IN_REVIEW, Lane.IN_PROGRESS)
    release_to = (Lane.APPROVED, Lane.PLANNED)
    releases_lock = st.target_lane in release_to or is_review_rejection_edge(st.old_lane, st.target_lane)
    if not (st.old_lane in release_from and releases_lock):
        return
    try:
        from specify_cli.review.lock import ReviewLock

        lock_workspace = _mt_owned_workspace(st) if st.owned is not None else _tasks.resolve_workspace_for_wp(st.main_repo_root, st.mission_slug, st.task_id)
        ReviewLock.release(Path(lock_workspace.worktree_path))
    except Exception as _release_exc:  # pragma: no cover - defensive
        logging.getLogger(__name__).warning(
            "Review lock release failed for %s in %s: %s",
            st.task_id,
            st.mission_slug,
            _release_exc,
        )


def _mt_execute(st: _MoveTaskState, ports: TasksPorts) -> None:
    """Emit the transition(s) + persist the WP file under the status lock."""
    from specify_cli.cli.commands.agent import tasks as _tasks

    status_lock_root = st.owned.owned_root if st.owned is not None else st.main_repo_root
    with _tasks.feature_status_lock(status_lock_root, mission_lock_key(st.feature_dir, repo_root=status_lock_root)):
        _mt_emit_transitions(st, ports)
        if st.self_review_fallback:
            from specify_cli.status import emit_reviewer_self_approval

            emit_reviewer_self_approval(
                st.feature_dir,
                mission_slug=st.mission_slug,
                wp_id=st.task_id,
                implementing_actor=st.final_hop_actor or "",
                intended_reviewer=(st.intended_reviewer or "").strip(),
                failure_reason=(st.reviewer_failure_reason or "").strip(),
                fallback_approved=True,
            )
        _mt_persist_wp_file(st, ports)
    # The rollback-to-``planned`` reset is now the ``subtasks`` reset delta emitted
    # inside ``_mt_persist_wp_file`` (#2513-via-snapshot) — the out-of-lock uncheck
    # seam is gone. The review-lock release still runs last on the rollback path
    # (D2 ordering preserved).
    _mt_release_review_lock(st)
