"""Mission run engine for deterministic `next()` progression."""

# Internalized from spec-kitty-runtime 0.4.3 as part of
# `shared-package-boundary-cutover-01KQ22DS` (mission). See
# `runtime-standalone-package-retirement-01KQ20Z8` for the upstream
# public-API inventory.
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Literal, cast
from uuid import uuid4

import yaml
from pydantic import BaseModel, ConfigDict

from kernel.clock import now_utc, now_utc_iso
from runtime.next._internal_runtime.contracts import RemediationPayload
from runtime.next._internal_runtime.discovery import DiscoveryContext, discover_missions, load_mission_template
from spec_kitty_events.mission_next import (
    DecisionInputAnsweredPayload,
    DecisionInputRequestedPayload,
    MissionRunCompletedPayload,
    MissionRunStartedPayload,
    NextStepAutoCompletedPayload,
    NextStepIssuedPayload,
    RuntimeActorIdentity,
)
from runtime.next._internal_runtime.events import (
    DECISION_INPUT_ANSWERED,
    DECISION_INPUT_REQUESTED,
    MISSION_RUN_COMPLETED,
    MISSION_RUN_STARTED,
    NEXT_STEP_AUTO_COMPLETED,
    NEXT_STEP_ISSUED,
    NullEmitter,
    RuntimeEventEmitter,
)
from runtime.next._internal_runtime.planner import plan_next
from runtime.next._internal_runtime.raci import infer_raci, resolve_raci
from runtime.next._internal_runtime.schema import (
    ActorIdentity,
    AuditStep,
    ContextType,
    ContextTypeRegistry,
    DecisionAnswer,
    DecisionRequest,
    MissionPolicySnapshot,
    MissionRunSnapshot,
    MissionRuntimeError,
    MissionTemplate,
    NextDecision,
    PromptStep,
    RACIRoleBinding,
    ResolvedRACIBinding,
    StepContextContract,
    load_mission_template_file,
)
from runtime.next._internal_runtime.significance import (
    SignificanceEvaluatedPayload,
    SignificanceScore,
    SoftGateDecision,
    TimeoutExpiredPayload,
    TimeoutEscalationResult,
    compute_escalation_targets,
    evaluate_significance,
    parse_band_cutoffs_from_policy,
    parse_timeout_from_policy,
)


ResultType = Literal["success", "failed", "blocked"]


def _find_step_by_id(
    template: MissionTemplate, step_id: str
) -> PromptStep | AuditStep | None:
    """Look up a step by ID across both steps and audit_steps."""
    prompt_step: PromptStep
    for prompt_step in template.steps:
        if prompt_step.id == step_id:
            return prompt_step
    audit_step: AuditStep
    for audit_step in template.audit_steps:
        if audit_step.id == step_id:
            return audit_step
    return None


class MissionRunRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    run_dir: str
    mission_key: str
    # NEW — back-references to the concrete Mission (FR-026/FR-027)
    # Optional for backward-compat: existing runs without these fields load with None defaults.
    mission_id: str | None = None    # canonical ULID from meta.json
    mission_slug: str | None = None  # human-readable slug


def _runtime_runs_dir(run_store: Path | None = None) -> Path:
    if run_store is not None:
        return run_store
    return Path.cwd() / ".kittify" / "runtime" / "runs"


def _append_event(run_dir: Path, event_type: str, payload: dict[str, Any]) -> None:
    event_file = run_dir / "run.events.jsonl"
    # canonical-producer-exempt: #1248 -- local runtime journal mirrors package-retired schema.
    event = {
        "event_type": event_type,
        "timestamp": now_utc_iso(),
        "payload": payload,
    }
    # Serialize before appending, then flush and fsync for durability. Append
    # mode preserves earlier records, but a failed write or crash can still
    # leave a partial final line; this is not an atomic record publication.
    # The journal is per-run, single-writer.
    line = json.dumps(event, sort_keys=True, default=str) + "\n"
    with open(event_file, "a", encoding="utf-8") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())


def _read_snapshot(run_dir: Path) -> MissionRunSnapshot:
    with open(run_dir / "state.json", encoding="utf-8") as handle:
        raw = json.load(handle)
    return MissionRunSnapshot.model_validate(raw)


def _write_snapshot(run_dir: Path, snapshot: MissionRunSnapshot) -> None:
    # FR-015: stage the cursor in a same-directory tmp file (same filesystem),
    # fsync, then publish with os.replace (atomic on POSIX and NTFS) -- the
    # ``reducer.materialize`` shape. A crash at any point leaves either the
    # previous complete state.json or the new one, never a torn file.
    target = run_dir / "state.json"
    tmp = run_dir / "state.json.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(snapshot.model_dump(mode="json"), handle, indent=2, sort_keys=True, default=str)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, target)


def _freeze_template(run_dir: Path, template: MissionTemplate, template_path: str) -> str:
    """Freeze the template into the run directory and return its SHA-256 hash.

    The frozen copy is the verbatim YAML bytes from disk if the path exists,
    otherwise a canonical YAML dump of the loaded template.
    """
    source_path = Path(template_path)
    if source_path.exists() and source_path.is_file():
        yaml_bytes = source_path.read_bytes()
    else:
        yaml_bytes = yaml.dump(
            template.model_dump(), default_flow_style=False, sort_keys=True
        ).encode("utf-8")

    frozen_path = run_dir / "mission_template_frozen.yaml"
    frozen_path.write_bytes(yaml_bytes)

    return hashlib.sha256(yaml_bytes).hexdigest()  # noqa: TID251 - production raw SHA-256 owner


def _load_frozen_template(run_dir: Path) -> MissionTemplate:
    """Load the frozen template from the run directory."""
    frozen_path = run_dir / "mission_template_frozen.yaml"
    if not frozen_path.exists():
        raise MissionRuntimeError(f"Frozen template not found: {frozen_path}")
    return load_mission_template_file(frozen_path)


def _resolve_template_path(template_key: str, context: DiscoveryContext | None) -> str:
    """Resolve the actual filesystem path for a template key.

    For explicit file paths, resolve directly.
    For discovery-based keys, find the selected mission's resolved path.
    This ensures template_path always points to a real file for drift detection.
    """
    candidate = Path(template_key)
    if candidate.exists():
        if candidate.is_dir():
            candidate = candidate / "mission.yaml"
        return str(candidate.resolve())

    # Key-based: look up via discovery (use default context if None,
    # matching load_mission_template behavior).
    effective_context = context if context is not None else DiscoveryContext()
    discovered = discover_missions(effective_context)
    for item in discovered:
        if item.key == template_key and item.selected:
            return item.path  # already resolved by discovery

    return template_key  # last resort (shouldn't happen if template loaded OK)


def start_mission_run(
    template_key: str,
    inputs: dict[str, Any] | None,
    policy_snapshot: MissionPolicySnapshot,
    context: DiscoveryContext | None = None,
    run_store: Path | None = None,
    emitter: RuntimeEventEmitter | None = None,
    template_override: MissionTemplate | None = None,
    template_path_override: str | None = None,
    mission_slug: str | None = None,   # NEW — FR-028/FR-029: back-ref to concrete mission
    mission_id: str | None = None,     # NEW — FR-028/FR-029: canonical ULID from meta.json
) -> MissionRunRef:
    """Start and persist a new mission run with template freezing."""
    emitter = emitter or NullEmitter()
    template = template_override or load_mission_template(template_key, context=context)

    runs_dir = _runtime_runs_dir(run_store)
    run_id = uuid4().hex
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    # Always resolve to a real filesystem path for drift detection.
    template_path = template_path_override or _resolve_template_path(template_key, context)

    # Freeze template and compute hash.
    template_hash = _freeze_template(run_dir, template, template_path)

    snapshot = MissionRunSnapshot(
        run_id=run_id,
        mission_key=template.mission.key,
        template_path=template_path,
        template_hash=template_hash,
        policy_snapshot=policy_snapshot,
        issued_step_id=None,
        completed_steps=[],
        inputs=inputs or {},
        decisions={},
        pending_decisions={},
        blocked_reason=None,
        mission_id=mission_id,
        mission_slug=mission_slug,
    )
    _write_snapshot(run_dir, snapshot)
    actor = RuntimeActorIdentity(
        actor_id="system", actor_type="service", provider=None, model=None, tool=None
    )
    payload = MissionRunStartedPayload(run_id=run_id, mission_type=template.mission.key, actor=actor)
    _append_event(run_dir, MISSION_RUN_STARTED, payload.model_dump(mode="json"))
    emitter.emit_mission_run_started(payload)

    return MissionRunRef(
        run_id=run_id,
        run_dir=str(run_dir),
        mission_key=template.mission.key,
        mission_id=mission_id,
        mission_slug=mission_slug,
    )


class AdvancePlan(BaseModel):
    """What one ``next_step`` will do, computed WITHOUT writing or emitting
    anything (owned-checkout-lifecycle-authority WP11, review cycle 1
    findings 3/4).

    ``snapshot`` is the run state the ``decision`` was planned from -- the
    result applied, any audit-significance LOW auto-proceed folded in, and the
    significance / RACI records added to ``decisions`` -- but not yet holding
    the issuance (``issued_step_id`` / ``pending_decisions``), which
    :func:`_commit_advance` adds. ``significance`` is the event the commit
    emits when an audit gate was evaluated.
    """

    model_config = ConfigDict(frozen=True)

    source: MissionRunSnapshot
    snapshot: MissionRunSnapshot
    decision: NextDecision
    result: ResultType
    completed_step_id: str | None
    significance: SignificanceEvaluatedPayload | None = None


def apply_result(snapshot: MissionRunSnapshot, result: ResultType) -> tuple[MissionRunSnapshot, str | None]:
    """The engine's one "complete the issued step" prelude (pure).

    Returns ``(snapshot, completed_step_id)``: the issued step moves to
    ``completed_steps`` on ``success``, or a ``blocked_reason`` is recorded on
    ``failed`` / ``blocked``; either way the issued marker is cleared.
    ``completed_step_id`` is ``None`` (and the snapshot unchanged) when no
    step was issued.
    """
    completed_step_id = snapshot.issued_step_id
    if not completed_step_id:
        return snapshot, None
    completed_steps = list(snapshot.completed_steps)
    blocked_reason = snapshot.blocked_reason
    if result == "success":
        if completed_step_id not in completed_steps:
            completed_steps.append(completed_step_id)
    elif result == "failed":
        blocked_reason = f"Previous step '{completed_step_id}' failed; manual intervention required."
    elif result == "blocked":
        blocked_reason = f"Previous step '{completed_step_id}' reported blocked state."
    applied = snapshot.model_copy(
        update={"issued_step_id": None, "completed_steps": completed_steps, "blocked_reason": blocked_reason},
    )
    return applied, completed_step_id


def existing_template_path(snapshot: MissionRunSnapshot) -> Path | None:
    """The on-disk template path for drift detection, when it still exists."""
    if not snapshot.template_path:
        return None
    candidate = Path(snapshot.template_path)
    return candidate if candidate.exists() else None


def _evaluate_audit_significance(
    decision: NextDecision,
    snapshot: MissionRunSnapshot,
    template: MissionTemplate,
    policy: MissionPolicySnapshot,
    agent_id: str,
    actor_context: dict[str, Any],
    live_template_path: Path | None,
) -> tuple[NextDecision, MissionRunSnapshot, SignificanceEvaluatedPayload | None]:
    """WP05 significance evaluation for an ``audit:`` decision (pure).

    LOW auto-proceeds (the gate completes and the planner re-plans to the
    next step), MEDIUM offers the soft gate, HIGH keeps the approve/reject
    decision. Returns the possibly-replaced decision, the snapshot it now
    stands on and the ``SignificanceEvaluated`` payload for the commit."""
    assert decision.decision_id is not None
    sig_step_id = decision.decision_id[len("audit:") :]
    sig_step = _find_step_by_id(template, sig_step_id)
    if not isinstance(sig_step, AuditStep) or sig_step.significance is None:
        return decision, snapshot, None

    score = evaluate_significance(
        dimension_scores=sig_step.significance.dimensions,
        hard_trigger_classes=sig_step.significance.hard_triggers,
        band_cutoffs=parse_band_cutoffs_from_policy(policy),
    )
    decisions = dict(snapshot.decisions)
    decisions[f"significance:{decision.decision_id}"] = score.model_dump(mode="json")

    # Resolve RACI for the audit step (needed for timeout escalation)
    raci_inputs = {**snapshot.inputs, "agent_id": agent_id}
    try:
        resolved_raci = resolve_raci(sig_step, raci_inputs, policy)
        decisions[f"raci:{sig_step_id}"] = resolved_raci.model_dump(mode="json")
    except MissionRuntimeError:
        decisions[f"raci:{sig_step_id}"] = infer_raci(sig_step, policy).model_dump(mode="json")

    payload = SignificanceEvaluatedPayload(
        run_id=snapshot.run_id,
        decision_id=decision.decision_id,
        step_id=sig_step_id,
        significance_score=score.model_dump(mode="json"),
        hard_trigger_classes=tuple(ht.class_id for ht in score.hard_trigger_classes),
        effective_band=score.effective_band.name,
        actor=RACIRoleBinding(actor_type="service", actor_id="runtime"),
    )
    snapshot = snapshot.model_copy(update={"decisions": decisions})

    if score.effective_band.name == "low":
        # LOW band: auto-proceed -- no human gate; re-plan for the actual next decision.
        completed = list(snapshot.completed_steps)
        if sig_step_id not in completed:
            completed.append(sig_step_id)
        snapshot = snapshot.model_copy(update={"issued_step_id": None, "completed_steps": completed})
        decision = plan_next(
            snapshot,
            template,
            policy,
            actor_context={**actor_context, "agent_id": agent_id},
            live_template_path=live_template_path,
        )
    elif score.effective_band.name == "medium":
        # MEDIUM band: soft gate with different options
        decision = NextDecision(
            kind="decision_required",
            run_id=snapshot.run_id,
            mission_key=snapshot.mission_key,
            step_id=decision.step_id,
            step_title=decision.step_title,
            decision_id=decision.decision_id,
            question=decision.question,
            options=["decide_solo", "open_stand_up", "defer"],
        )
    # HIGH band: keep existing decision (approve/reject) -- no change needed
    return decision, snapshot, payload


def _record_step_raci(
    snapshot: MissionRunSnapshot,
    template: MissionTemplate,
    step_id: str,
    policy: MissionPolicySnapshot,
    agent_id: str,
) -> MissionRunSnapshot:
    """WP06: resolve (best-effort, else infer) the RACI binding for the issued step (pure)."""
    step_obj = _find_step_by_id(template, step_id)
    if step_obj is None:
        return snapshot
    decisions = dict(snapshot.decisions)
    raci_inputs = {**snapshot.inputs, "agent_id": agent_id}
    try:
        decisions[f"raci:{step_id}"] = resolve_raci(step_obj, raci_inputs, policy).model_dump(mode="json")
    except MissionRuntimeError:
        # Inputs insufficient for full resolution -- record the inferred binding.
        decisions[f"raci:{step_id}"] = infer_raci(step_obj, policy).model_dump(mode="json")
    return snapshot.model_copy(update={"decisions": decisions})


def plan_advance(
    run_ref: MissionRunRef,
    agent_id: str,
    result: ResultType = "success",
    policy_snapshot: MissionPolicySnapshot | None = None,
    actor_context: dict[str, Any] | None = None,
) -> AdvancePlan:
    """Compute what ``next_step`` will issue -- WITHOUT persisting or emitting.

    The engine's single planning authority: applies ``result`` to the issued
    step (:func:`apply_result`), plans the next step from the frozen template
    (passing the live template path for drift detection), folds in the audit
    significance evaluation including its LOW re-plan, and records the RACI
    binding of an issued step. :func:`next_step` commits exactly this plan, so
    a caller that inspects it first (the bridge resolves a WP-iteration
    step's workspace before the advance is persisted) can never see a
    different step than the one that is then issued.
    """
    run_dir = Path(run_ref.run_dir)
    snapshot = _read_snapshot(run_dir)
    source = snapshot
    # Use caller-provided policy, else fall back to persisted policy from run start.
    policy = policy_snapshot or snapshot.policy_snapshot
    # Plan from the frozen template, not the live file.
    template = _load_frozen_template(run_dir)
    live_template_path = existing_template_path(snapshot)
    context = {**(actor_context or {}), "agent_id": agent_id}

    snapshot, completed_step_id = apply_result(snapshot, result)
    decision = plan_next(snapshot, template, policy, actor_context=context, live_template_path=live_template_path)

    significance: SignificanceEvaluatedPayload | None = None
    if decision.kind == "decision_required" and decision.decision_id and decision.decision_id.startswith("audit:"):
        decision, snapshot, significance = _evaluate_audit_significance(
            decision, snapshot, template, policy, agent_id, actor_context or {}, live_template_path
        )
    if decision.kind == "step" and decision.step_id:
        snapshot = _record_step_raci(snapshot, template, decision.step_id, policy, agent_id)

    return AdvancePlan(
        source=source,
        snapshot=snapshot,
        decision=decision,
        result=result,
        completed_step_id=completed_step_id,
        significance=significance,
    )


def _actor(agent_id: str) -> RuntimeActorIdentity:
    return RuntimeActorIdentity(actor_id=agent_id, actor_type="llm", provider=None, model=None, tool=None)


def _commit_advance(run_ref: MissionRunRef, plan: AdvancePlan, agent_id: str, emitter: RuntimeEventEmitter) -> None:
    """Persist + emit a plan: the events in their historical order, then the snapshot."""
    run_dir = Path(run_ref.run_dir)
    snapshot = plan.snapshot
    decision = plan.decision
    actor = _actor(agent_id)

    if plan.completed_step_id is not None:
        completed_payload = NextStepAutoCompletedPayload(
            run_id=snapshot.run_id,
            step_id=plan.completed_step_id,
            agent_id=agent_id,
            result=plan.result,
            actor=actor,
        )
        _append_event(run_dir, NEXT_STEP_AUTO_COMPLETED, completed_payload.model_dump(mode="json"))
        emitter.emit_next_step_auto_completed(completed_payload)

    if plan.significance is not None:
        _append_event(run_dir, "SignificanceEvaluated", plan.significance.model_dump(mode="json"))
        emitter.emit_significance_evaluated(plan.significance)

    issued_step_id: str | None = None
    pending_decisions = dict(snapshot.pending_decisions)
    if decision.kind == "step" and decision.step_id:
        issued_step_id = decision.step_id
        issued_payload = NextStepIssuedPayload(run_id=snapshot.run_id, step_id=decision.step_id, agent_id=agent_id, actor=actor)
        _append_event(run_dir, NEXT_STEP_ISSUED, issued_payload.model_dump(mode="json"))
        emitter.emit_next_step_issued(issued_payload)
    elif decision.kind == "decision_required" and decision.decision_id:
        # Persist input-keyed decisions in pending_decisions so they're answerable.
        # Only emit event + persist on first occurrence to avoid duplicates on re-poll.
        if decision.decision_id not in pending_decisions:
            request = DecisionRequest(
                decision_id=decision.decision_id,
                step_id=decision.step_id or "",
                question=decision.question or "",
                options=decision.options or [],
                requested_by=actor,
                requested_at=now_utc(),
            )
            pending_decisions[decision.decision_id] = request.model_dump(mode="json")
            requested_payload = DecisionInputRequestedPayload(
                run_id=snapshot.run_id,
                decision_id=decision.decision_id,
                step_id=decision.step_id or "",
                question=decision.question or "",
                options=tuple(decision.options or []),
                input_key=decision.input_key,
                actor=actor,
            )
            _append_event(run_dir, DECISION_INPUT_REQUESTED, requested_payload.model_dump(mode="json"))
            emitter.emit_decision_input_requested(requested_payload)
    elif decision.kind == "terminal" and plan.completed_step_id is not None:
        # Only emit on the transition into terminal (last step just completed),
        # not on re-polls of an already-terminal run.
        completed_run_payload = MissionRunCompletedPayload(run_id=snapshot.run_id, mission_type=snapshot.mission_key, actor=actor)
        _append_event(run_dir, MISSION_RUN_COMPLETED, completed_run_payload.model_dump(mode="json"))
        emitter.emit_mission_run_completed(completed_run_payload)

    _write_snapshot(
        run_dir,
        snapshot.model_copy(update={"issued_step_id": issued_step_id, "pending_decisions": pending_decisions}),
    )


def next_step(
    run_ref: MissionRunRef,
    agent_id: str,
    result: ResultType = "success",
    policy_snapshot: MissionPolicySnapshot | None = None,
    actor_context: dict[str, Any] | None = None,
    context: DiscoveryContext | None = None,  # noqa: ARG001
    emitter: RuntimeEventEmitter | None = None,
) -> NextDecision:
    """Advance current issued step and compute the next deterministic decision.

    Plans from the frozen template, not the live file. Passes live template
    path for drift detection. Uses persisted policy_snapshot from run state;
    caller override takes precedence. Plan (:func:`plan_advance`) then commit
    (:func:`_commit_advance`) -- the two halves share one plan.
    """
    plan = plan_advance(run_ref, agent_id, result, policy_snapshot=policy_snapshot, actor_context=actor_context)
    _commit_advance(run_ref, plan, agent_id, emitter or NullEmitter())
    return plan.decision


class StaleAdvancePlan(MissionRuntimeError):
    """The run's persisted state changed after the plan was computed."""


def commit_advance(run_ref: MissionRunRef, plan: AdvancePlan, agent_id: str, emitter: RuntimeEventEmitter | None = None) -> NextDecision:
    """Commit a plan a caller already computed with :func:`plan_advance`.

    The caller planned first (the bridge resolves a WP-iteration step's
    workspace before anything is persisted) and commits THAT plan -- the
    engine does not plan a second time. The plan is refused with
    :class:`StaleAdvancePlan`, writing nothing, when the run's persisted state
    is no longer the state it was planned from: committing it would overwrite
    newer progress.
    """
    if _read_snapshot(Path(run_ref.run_dir)) != plan.source:
        raise StaleAdvancePlan(f"Run '{plan.source.run_id}' changed after the advance was planned; plan again.")
    _commit_advance(run_ref, plan, agent_id, emitter or NullEmitter())
    return plan.decision


def provide_decision_answer(  # noqa: C901
    run_ref: MissionRunRef,
    decision_id: str,
    answer: str,
    actor: ActorIdentity,
    emitter: RuntimeEventEmitter | None = None,
) -> None:
    """Answer a pending decision.

    For input-keyed decisions (input:X), writes into inputs.
    For audit decisions (audit:X), approves or rejects the audit checkpoint:
      - "approve": adds audit_step_id to completed_steps; run continues.
      - "reject": sets blocked_reason; run is permanently blocked.
    """
    emitter = emitter or NullEmitter()
    run_dir = Path(run_ref.run_dir)
    snapshot = _read_snapshot(run_dir)

    pending = dict(snapshot.pending_decisions)
    if decision_id not in pending:
        raise MissionRuntimeError(
            f"Decision '{decision_id}' not found in pending_decisions for run '{snapshot.run_id}'"
        )

    decisions = dict(snapshot.decisions)
    inputs = dict(snapshot.inputs)
    completed_steps = list(snapshot.completed_steps)
    blocked_reason = snapshot.blocked_reason
    authority_role = actor.actor_type
    rationale_linkage: str | None = None
    raci_source: str | None = None
    raci_override_reason: str | None = None

    # WP06: Look up persisted RACI binding for the step associated with this decision.
    _raci_step_id: str | None = None
    if decision_id.startswith("audit:"):
        _raci_step_id = decision_id[len("audit:"):]
    elif decision_id.startswith("input:"):
        # For input decisions, check if there's an issued step with RACI
        _raci_step_id = snapshot.issued_step_id

    raci_key = f"raci:{_raci_step_id}" if _raci_step_id else None
    raci_record = decisions.get(raci_key) if raci_key else None
    if isinstance(raci_record, dict):
        raci_source = raci_record.get("source")
        raci_override_reason = raci_record.get("override_reason")

    # T014: Detect audit: prefix and validate answer before creating DecisionAnswer.
    if decision_id.startswith("audit:"):
        audit_step_id = decision_id[len("audit:"):]
        mission_owner_id = _resolve_mission_owner_id(inputs)
        authority_role = "mission_owner"

        deny_reason: str | None = None
        if actor.actor_type != "human":
            deny_reason = "Audit decisions require a human actor"
        elif not mission_owner_id:
            deny_reason = "Audit decisions require mission_owner_id to be set in inputs"
        elif actor.actor_id != mission_owner_id:
            deny_reason = f"Audit decisions require mission owner '{mission_owner_id}'"

        if deny_reason is not None:
            _append_event(
                run_dir,
                "DecisionAuthorityDenied",
                {
                    "run_id": snapshot.run_id,
                    "decision_id": decision_id,
                    "actor_type": actor.actor_type,
                    "actor_id": actor.actor_id,
                    "authority_role": authority_role,
                    "rationale_linkage": rationale_linkage,
                    "reason": deny_reason,
                    "raci_source": raci_source,
                    "override_reason": raci_override_reason,
                },
            )
            raise MissionRuntimeError(deny_reason)

        # WP05: Significance-aware answer validation.
        # Check if this audit decision has a significance evaluation.
        _sig_key = f"significance:{decision_id}"
        _sig_data = decisions.get(_sig_key)
        _effective_band_name: str | None = None
        if _sig_data is not None and isinstance(_sig_data, dict):
            _eb = _sig_data.get("effective_band")
            _effective_band_name = _eb.get("name") if isinstance(_eb, dict) else _eb

        if _effective_band_name == "medium":
            _valid_medium = {"decide_solo", "open_stand_up", "defer"}
            if answer not in _valid_medium:
                raise MissionRuntimeError(
                    f"Medium-band decision requires one of {sorted(_valid_medium)}, got: {answer!r}"
                )
        elif _effective_band_name == "high":
            if answer not in ("approve", "reject"):
                raise MissionRuntimeError(
                    f"High-band decision requires one of {{'approve', 'reject'}}, got: {answer!r}"
                )
        else:
            # No significance evaluation — existing validation (T015).
            if answer not in ("approve", "reject"):
                raise MissionRuntimeError(
                    f"Invalid audit answer '{answer}': must be 'approve' or 'reject'"
                )
    elif actor.actor_type == "llm":
        delegation = _resolve_delegation_record(inputs, decision_id)
        if delegation is None:
            raise MissionRuntimeError(
                f"LLM actor '{actor.actor_id}' is not delegated for decision '{decision_id}'"
            )

        authority_role = delegation.get("authority_role") or "delegated_llm"
        if not isinstance(authority_role, str):
            authority_role = "delegated_llm"

        rationale_raw = delegation.get("rationale_linkage")
        if isinstance(rationale_raw, str):
            rationale_linkage = rationale_raw.strip() or None
        if rationale_linkage is None:
            raise MissionRuntimeError(
                f"LLM delegation for decision '{decision_id}' must include non-empty rationale_linkage"
            )

    answer_data = DecisionAnswer(
        decision_id=decision_id,
        answer=answer,
        answered_by=actor,
        answered_at=now_utc(),
    )
    decision_record = answer_data.model_dump(mode="json")
    decision_record.update(_authority_metadata(
        actor, authority_role, rationale_linkage,
        raci_source=raci_source,
        override_reason=raci_override_reason,
    ))
    decisions[decision_id] = decision_record
    del pending[decision_id]

    if decision_id.startswith("audit:"):
        # WP05: Significance-aware gate handling.
        _sig_key_handle = f"significance:{decision_id}"
        _sig_data_handle = decisions.get(_sig_key_handle)
        _eb_name_handle: str | None = None
        if _sig_data_handle is not None and isinstance(_sig_data_handle, dict):
            _eb_h = _sig_data_handle.get("effective_band")
            _eb_name_handle = _eb_h.get("name") if isinstance(_eb_h, dict) else _eb_h

        if _eb_name_handle == "medium":
            # Medium-band: persist SoftGateDecision
            _sig_score_obj = SignificanceScore.model_validate(_sig_data_handle)
            # `answer` is validated upstream against the SoftGate action set
            # (`decide_solo` / `open_stand_up` / `defer`); pydantic re-validates
            # at SoftGateDecision construction so the cast is a typing assist
            # rather than a trust boundary widening.
            _soft_gate_action = cast(
                Literal["decide_solo", "open_stand_up", "defer"], answer
            )
            _actor_type_lit = cast(
                Literal["human", "llm", "service"], actor.actor_type
            )
            _soft_gate = SoftGateDecision(
                decision_id=decision_id,
                action=_soft_gate_action,
                actor=RACIRoleBinding(actor_type=_actor_type_lit, actor_id=actor.actor_id),
                timestamp=now_utc(),
                significance_score=_sig_score_obj,
                outcome=_soft_gate_action if answer == "decide_solo" else None,
            )
            decisions[f"soft_gate:{decision_id}"] = _soft_gate.model_dump(mode="json")

            if answer == "decide_solo":
                # Gate clears — add to completed_steps
                if audit_step_id not in completed_steps:
                    completed_steps.append(audit_step_id)
            else:
                # open_stand_up / defer: gate stays open, re-add to pending
                pending[decision_id] = snapshot.pending_decisions[decision_id]
        else:
            # HIGH band or no significance: existing behavior
            if answer == "approve":
                # T016: Add audit_step_id to completed_steps so DAG can advance.
                if audit_step_id not in completed_steps:
                    completed_steps.append(audit_step_id)
            else:
                # T017: Set blocked_reason; run is permanently blocked.
                blocked_reason = f"Audit step '{audit_step_id}' rejected by {actor.actor_id}"

    elif decision_id.startswith("input:"):
        # For input-keyed decisions, write the answer into inputs so requires_inputs is satisfied.
        input_key = decision_id[len("input:"):]
        inputs[input_key] = answer

    snapshot = MissionRunSnapshot(
        run_id=snapshot.run_id,
        mission_key=snapshot.mission_key,
        template_path=snapshot.template_path,
        template_hash=snapshot.template_hash,
        policy_snapshot=snapshot.policy_snapshot,
        issued_step_id=snapshot.issued_step_id,
        completed_steps=completed_steps,
        inputs=inputs,
        decisions=decisions,
        pending_decisions=pending,
        blocked_reason=blocked_reason,
        mission_id=snapshot.mission_id,
        mission_slug=snapshot.mission_slug,
    )
    _write_snapshot(run_dir, snapshot)

    # T018: Emit DECISION_INPUT_ANSWERED event for both approve and reject paths.
    da_payload = DecisionInputAnsweredPayload(
        run_id=snapshot.run_id, decision_id=decision_id, answer=answer, actor=actor,
    )
    _append_event(run_dir, DECISION_INPUT_ANSWERED, da_payload.model_dump(mode="json"))
    emitter.emit_decision_input_answered(da_payload)


def _resolve_mission_owner_id(inputs: dict[str, Any]) -> str | None:
    owner_id = inputs.get("mission_owner_id")
    if isinstance(owner_id, str):
        owner_id = owner_id.strip()
        if owner_id:
            return owner_id
    return None


def _resolve_delegation_record(inputs: dict[str, Any], decision_id: str) -> dict[str, Any] | None:
    delegations = inputs.get("llm_delegations")
    if not isinstance(delegations, dict):
        return None
    for key in (decision_id, "*"):
        record = delegations.get(key)
        if isinstance(record, dict):
            return record
    return None


def _authority_metadata(
    actor: ActorIdentity,
    authority_role: str,
    rationale_linkage: str | None,
    raci_source: str | None = None,
    override_reason: str | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "actor_type": actor.actor_type,
        "actor_id": actor.actor_id,
        "authority_role": authority_role,
        "rationale_linkage": rationale_linkage,
    }
    if raci_source is not None:
        metadata["raci_source"] = raci_source
    if override_reason is not None:
        metadata["override_reason"] = override_reason
    return metadata


# ============================================================================
# WP04: Timeout Escalation & Engine API
# ============================================================================


def notify_decision_timeout(
    run_ref: MissionRunRef,
    decision_id: str,
    actor: RACIRoleBinding,
    emitter: RuntimeEventEmitter | None = None,
) -> TimeoutEscalationResult:
    """Notify the runtime that a decision has timed out.

    Called by the host process (caller manages wall-clock timers per C-004).
    The runtime computes escalation targets, emits timeout-expired event,
    and persists the timeout record. The run remains blocked (fail-closed).

    Args:
        run_ref: Reference to the mission run
        decision_id: The decision that timed out (e.g., "audit:deploy-approval")
        actor: System actor identity (typically service/runtime)
        emitter: Optional event emitter (uses NullEmitter if None)

    Returns:
        TimeoutEscalationResult with escalation targets and event payload

    Raises:
        MissionRuntimeError: If decision not found, RACI not resolved, or significance not evaluated
    """
    emitter = emitter or NullEmitter()
    run_dir = Path(run_ref.run_dir)
    snapshot = _read_snapshot(run_dir)

    # Extract step_id from decision_id (strip "audit:" prefix)
    step_id = decision_id[len("audit:"):] if decision_id.startswith("audit:") else decision_id

    # Load RACI binding from decisions
    raci_key = f"raci:{step_id}"
    raci_data = snapshot.decisions.get(raci_key)
    if raci_data is None or not isinstance(raci_data, dict):
        raise MissionRuntimeError(f"No RACI binding for step '{step_id}'")
    raci_binding = ResolvedRACIBinding.model_validate(raci_data)

    # Load significance score from decisions
    sig_key = f"significance:{decision_id}"
    sig_data = snapshot.decisions.get(sig_key)
    if sig_data is None or not isinstance(sig_data, dict):
        raise MissionRuntimeError(f"No significance evaluation for decision '{decision_id}'")

    # Determine effective_band from stored significance score
    effective_band_data = sig_data.get("effective_band")
    effective_band = effective_band_data.get("name") if isinstance(effective_band_data, dict) else effective_band_data

    if effective_band not in ("medium", "high"):
        raise MissionRuntimeError(
            f"Unexpected effective_band '{effective_band}' for decision '{decision_id}'. "
            f"Only 'medium' and 'high' bands can timeout."
        )

    # Compute escalation targets
    escalation_targets = compute_escalation_targets(raci_binding, effective_band)

    # Determine timeout_configured_seconds from policy
    timeout_seconds = parse_timeout_from_policy(snapshot.policy_snapshot)

    # Build TimeoutExpiredPayload
    payload = TimeoutExpiredPayload(
        run_id=snapshot.run_id,
        decision_id=decision_id,
        step_id=step_id,
        significance_score=sig_data,
        effective_band=effective_band,
        timeout_configured_seconds=timeout_seconds,
        escalation_targets=escalation_targets,
        raci_snapshot=raci_data,
        actor=actor,
    )

    # Emit timeout event BEFORE persisting (consistent with existing patterns)
    _append_event(run_dir, "DecisionTimeoutExpired", payload.model_dump(mode="json"))
    emitter.emit_decision_timeout_expired(payload)

    # T020: Persist timeout event to decisions dict
    updated_decisions = dict(snapshot.decisions)
    updated_decisions[f"timeout:{decision_id}"] = payload.model_dump(mode="json")

    # Build updated snapshot (frozen model, so create new)
    updated_snapshot = MissionRunSnapshot(
        run_id=snapshot.run_id,
        mission_key=snapshot.mission_key,
        template_path=snapshot.template_path,
        template_hash=snapshot.template_hash,
        policy_snapshot=snapshot.policy_snapshot,
        issued_step_id=snapshot.issued_step_id,
        completed_steps=snapshot.completed_steps,
        inputs=snapshot.inputs,
        decisions=updated_decisions,
        pending_decisions=snapshot.pending_decisions,
        blocked_reason=snapshot.blocked_reason,
        mission_id=snapshot.mission_id,
        mission_slug=snapshot.mission_slug,
    )

    # Save to state.json
    _write_snapshot(run_dir, updated_snapshot)

    return TimeoutEscalationResult(
        decision_id=decision_id,
        escalation_targets=escalation_targets,
        band=effective_band,
        timeout_expired_payload=payload,
    )


# ============================================================================
# WP02: Transition-Gate Engine - Deterministic Context Resolution
# ============================================================================


class TransitionGate:
    """Core gate evaluation logic that validates context bindings before step entry.

    The TransitionGate evaluates whether a step can be entered by checking:
    1. All required contexts can be resolved
    2. Resolved contexts are not ambiguous (multiple equally valid candidates)
    3. Resolved contexts pass validation rules

    If all checks pass, the gate returns 'ready'. Otherwise, it returns a
    RemediationPayload with structured error information and actionable hints.
    """

    def __init__(
        self,
        contract: StepContextContract,
        available_bindings: dict[str, Any],
        context_registry: ContextTypeRegistry | None = None,
        local_discovery_root: Path | None = None,
    ):
        """Initialize TransitionGate.

        Args:
            contract: The StepContextContract defining required/optional contexts
            available_bindings: Dict of available context bindings from all sources
            context_registry: ContextTypeRegistry for type validation (optional)
            local_discovery_root: Root path for local filesystem discovery (optional)
        """
        self.contract = contract
        self.available_bindings = available_bindings
        self.registry = context_registry or ContextTypeRegistry()
        self.local_discovery_root = local_discovery_root or Path.cwd()

    def evaluate(self) -> str | RemediationPayload:
        """Evaluate the transition gate.

        Returns:
            'ready' if all required contexts are resolved and valid
            RemediationPayload if any required context fails resolution or validation
        """
        # Evaluate all required contexts
        for context_type in self.contract.requires:
            result = self._evaluate_context(context_type, required=True)
            if isinstance(result, RemediationPayload):
                return result

        return "ready"

    def _evaluate_context(
        self,
        context_type: ContextType,
        required: bool = True
    ) -> str | RemediationPayload:
        """Evaluate a single context.

        Args:
            context_type: The ContextType to evaluate
            required: Whether this context is required (blocking) or optional

        Returns:
            'ready' if context resolved and valid
            RemediationPayload if context failed resolution or validation
        """
        # Attempt context resolution using precedence chain
        resolution_result = resolve_context(
            context_type.type,
            context_type,
            self.available_bindings,
            self.registry,
            self.local_discovery_root
        )

        if isinstance(resolution_result, RemediationPayload):
            # Resolution failed
            if required:
                return resolution_result
            else:
                # Optional context failed; log but don't block
                return "ready"

        resolved_value = resolution_result

        # Validate the resolved binding against declared rules
        is_valid, validation_error = validate_binding(resolved_value, context_type)
        if not is_valid:
            payload = RemediationPayload.invalid(
                context_name=context_type.type,
                candidates=[{"value": resolved_value}],
                validation_failures=[validation_error] if validation_error else None,
                resolver_metadata={
                    "context_type": context_type.type,
                    "validation_rule_failed": True
                }
            )
            return payload

        return "ready"


def resolve_context(
    context_name: str,
    context_type: ContextType,
    available_bindings: dict[str, Any],
    _registry: ContextTypeRegistry,
    local_discovery_root: Path | None = None
) -> Any | RemediationPayload:
    """Resolve a context using the 5-point precedence chain.

    Resolver precedence (local-first, offline):
    1. Explicit step/run inputs (operator overrides)
    2. Prior ContextLedger bindings (from earlier steps)
    3. Mission run metadata (project context, branch, etc.)
    4. Deterministic local discovery (filesystem, branch state, cwd)
    5. Step-specific LOCAL fallback resolvers (only with explicit policy)

    Multiple candidates from the same resolver level = ambiguous (error).
    Try next resolver only if current returns nothing.
    No "best guess" auto-selection.

    Args:
        context_name: The name of the context to resolve
        context_type: The ContextType definition with validation rules
        available_bindings: All available bindings from all sources
        registry: ContextTypeRegistry for type info
        local_discovery_root: Root path for local discovery operations

    Returns:
        Resolved value if found and unambiguous
        RemediationPayload if resolution fails or ambiguous
    """
    if local_discovery_root is None:
        local_discovery_root = Path.cwd()

    resolver_metadata = {
        "context_name": context_name,
        "deterministic": context_type.deterministic,
    }

    # 1. Explicit step/run inputs (highest precedence)
    candidates = _resolve_explicit_inputs(context_name, available_bindings)
    if candidates:
        if len(candidates) > 1:
            return RemediationPayload.ambiguous(
                context_name=context_name,
                candidates=candidates,
                resolver_metadata={
                    **resolver_metadata,
                    "resolver": "explicit_inputs",
                    "precedence": 1,
                    "ambiguous_count": len(candidates)
                }
            )
        return candidates[0]["value"]

    # 2. Prior ContextLedger bindings
    candidates = _resolve_ledger_bindings(context_name, available_bindings)
    if candidates:
        if len(candidates) > 1:
            return RemediationPayload.ambiguous(
                context_name=context_name,
                candidates=candidates,
                resolver_metadata={
                    **resolver_metadata,
                    "resolver": "context_ledger",
                    "precedence": 2,
                    "ambiguous_count": len(candidates)
                }
            )
        return candidates[0]["value"]

    # 3. Mission run metadata
    candidates = _resolve_mission_metadata(context_name, available_bindings)
    if candidates:
        if len(candidates) > 1:
            return RemediationPayload.ambiguous(
                context_name=context_name,
                candidates=candidates,
                resolver_metadata={
                    **resolver_metadata,
                    "resolver": "mission_metadata",
                    "precedence": 3,
                    "ambiguous_count": len(candidates)
                }
            )
        return candidates[0]["value"]

    # 4. Deterministic local discovery
    candidates = _resolve_local_discovery(
        context_name,
        context_type,
        available_bindings,
        local_discovery_root
    )
    if candidates:
        if len(candidates) > 1:
            return RemediationPayload.ambiguous(
                context_name=context_name,
                candidates=candidates,
                resolver_metadata={
                    **resolver_metadata,
                    "resolver": "local_discovery",
                    "precedence": 4,
                    "ambiguous_count": len(candidates)
                }
            )
        return candidates[0]["value"]

    # 5. Step-specific LOCAL fallback resolvers (optional, requires explicit policy)
    # Note: Fallback resolvers must be explicitly enabled in mission policy
    # and are LOCAL-ONLY (no network access in V1)
    # Default behavior: fallback resolvers disabled (conservative, offline-first)

    # Check if mission policy explicitly allows fallback resolvers
    mission_metadata = available_bindings.get("mission_metadata", {})
    if not isinstance(mission_metadata, dict):
        mission_metadata = {}
    allow_fallback_resolvers = mission_metadata.get("allow_fallback_resolvers", False)

    if allow_fallback_resolvers:
        candidates = _resolve_fallback_local(context_name, available_bindings)
        if candidates:
            if len(candidates) > 1:
                return RemediationPayload.ambiguous(
                    context_name=context_name,
                    candidates=candidates,
                    resolver_metadata={
                        **resolver_metadata,
                        "resolver": "fallback_local",
                        "precedence": 5,
                        "ambiguous_count": len(candidates),
                        "policy_enabled": True
                    }
                )
            return candidates[0]["value"]

    # No candidates found in any resolver
    return RemediationPayload.missing(
        context_name=context_name,
        resolver_metadata={
            **resolver_metadata,
            "resolver_chain_exhausted": True
        }
    )


def _resolve_explicit_inputs(
    context_name: str,
    available_bindings: dict[str, Any]
) -> list[dict[str, Any]]:
    """Resolver 1: Check for explicit operator overrides.

    Sources:
    - Explicit step inputs
    - Command-line arguments (passed via available_bindings)
    - Environment variables (passed via available_bindings)

    Args:
        context_name: The context to resolve
        available_bindings: Dict with 'explicit_inputs' key

    Returns:
        List of candidate bindings (empty if not found)
        Each candidate: {"value": <value>, "source": <str>, "metadata": <dict>}

    Note: If explicit input value is a list/tuple, it's treated as multiple
    candidates (ambiguous). Each item becomes a separate candidate.
    """
    explicit = available_bindings.get("explicit_inputs", {})
    if not isinstance(explicit, dict):
        return []

    candidates = []
    if context_name in explicit:
        value = explicit[context_name]

        # If explicit input is a list or tuple, treat as multiple candidates (ambiguous)
        if isinstance(value, (list, tuple)):
            for i, item in enumerate(value):
                candidates.append({
                    "value": item,
                    "source": f"explicit_input:{context_name}[{i}]",
                    "metadata": {
                        "resolver": "explicit_inputs",
                        "precedence": 1,
                        "is_list": True,
                        "index": i
                    }
                })
        else:
            # Single value - normal candidate
            candidates.append({
                "value": value,
                "source": f"explicit_input:{context_name}",
                "metadata": {"resolver": "explicit_inputs", "precedence": 1}
            })

    return candidates


def _resolve_ledger_bindings(
    context_name: str,
    available_bindings: dict[str, Any]
) -> list[dict[str, Any]]:
    """Resolver 2: Check prior ContextLedger bindings.

    Sources:
    - ContextLedger from prior steps
    - ContextLedger from prior runs

    Args:
        context_name: The context to resolve
        available_bindings: Dict with 'ledger' key

    Returns:
        List of candidate bindings (empty if not found)
    """
    ledger = available_bindings.get("ledger", {})
    if not isinstance(ledger, dict):
        return []

    candidates = []
    if context_name in ledger:
        binding = ledger[context_name]
        # Handle both dict and non-dict values
        if isinstance(binding, dict):
            value = binding.get("value", binding)
            validation_status = binding.get("validation_status", "unknown")
        else:
            value = binding
            validation_status = "unknown"

        candidates.append({
            "value": value,
            "source": f"ledger:{context_name}",
            "metadata": {
                "resolver": "context_ledger",
                "precedence": 2,
                "validation_status": validation_status
            }
        })

    return candidates


def _resolve_mission_metadata(
    context_name: str,
    available_bindings: dict[str, Any]
) -> list[dict[str, Any]]:
    """Resolver 3: Check mission run metadata.

    Sources:
    - Mission YAML fields (project_uuid, feature_slug, target_branch, mission_key)
    - Mission run context

    Args:
        context_name: The context to resolve
        available_bindings: Dict with 'mission_metadata' key

    Returns:
        List of candidate bindings (empty if not found)
    """
    metadata = available_bindings.get("mission_metadata", {})
    if not isinstance(metadata, dict):
        return []

    candidates = []

    # Map common context names to metadata fields
    mapping = {
        "project_uuid": "project_uuid",
        "feature_slug": "feature_slug",
        "target_branch": "target_branch",
        "mission_key": "mission_key",
        "mission_name": "mission_name",
        "branch": "target_branch",  # Alias
    }

    if context_name in mapping:
        field = mapping[context_name]
        if field in metadata:
            candidates.append({
                "value": metadata[field],
                "source": f"mission_metadata:{field}",
                "metadata": {
                    "resolver": "mission_metadata",
                    "precedence": 3,
                    "field": field
                }
            })

    return candidates


def _resolve_local_discovery(
    context_name: str,
    _context_type: ContextType,
    available_bindings: dict[str, Any],
    local_discovery_root: Path
) -> list[dict[str, Any]]:
    """Resolver 4: Deterministic local filesystem discovery.

    Sources:
    - Working directory and mission directory
    - Fixed known paths
    - Branch state (git info)
    - Artifact paths

    Offline-capable by design (no network calls).

    Args:
        context_name: The context to resolve
        context_type: ContextType with validation rules
        available_bindings: Dict with discovery hints
        local_discovery_root: Root path for searching

    Returns:
        List of candidate bindings (empty if not found)
    """
    candidates = []

    # Check discovery hints in available_bindings
    discovery_hints = available_bindings.get("discovery_hints", {})
    if context_name in discovery_hints:
        hint_value = discovery_hints[context_name]
        candidates.append({
            "value": hint_value,
            "source": f"discovery_hint:{context_name}",
            "metadata": {
                "resolver": "local_discovery",
                "precedence": 4,
                "type": "hint"
            }
        })

    # Check for artifact files that match context name pattern
    # E.g., "spec_artifact" -> look for spec.md, spec.yaml
    artifact_patterns = {
        "spec_artifact": ["spec.md", "spec.yaml"],
        "plan_artifact": ["plan.md", "plan.yaml"],
        "tasks_artifact": ["tasks.md", "tasks.yaml"],
        "research_artifact": ["research.md", "research.yaml"],
    }

    if context_name in artifact_patterns:
        for pattern in artifact_patterns[context_name]:
            potential_path = local_discovery_root / pattern
            if potential_path.exists():
                candidates.append({
                    "value": str(potential_path),
                    "source": f"local_discovery:{pattern}",
                    "metadata": {
                        "resolver": "local_discovery",
                        "precedence": 4,
                        "type": "artifact_file"
                    }
                })

    # Check for branch context (requires git state in available_bindings)
    if context_name == "target_branch":
        git_state = available_bindings.get("git_state", {})
        if "branch" in git_state:
            candidates.append({
                "value": git_state["branch"],
                "source": "git_state:branch",
                "metadata": {
                    "resolver": "local_discovery",
                    "precedence": 4,
                    "type": "git_state"
                }
            })

    return candidates


def _resolve_fallback_local(
    context_name: str,
    available_bindings: dict[str, Any]
) -> list[dict[str, Any]]:
    """Resolver 5: Step-specific LOCAL fallback resolvers.

    Fallback resolvers are optional and must be:
    1. Explicitly registered in mission policy
    2. LOCAL-ONLY (no network registries in V1)
    3. Defined by resolver_ref in ContextType

    Args:
        context_name: The context to resolve
        available_bindings: Dict with 'fallback_resolvers' key

    Returns:
        List of candidate bindings (empty if not found or policy not set)
    """
    fallback_resolvers = available_bindings.get("fallback_resolvers", {})
    if not isinstance(fallback_resolvers, dict):
        return []

    candidates = []
    if context_name in fallback_resolvers:
        resolver_data = fallback_resolvers[context_name]
        # Handle both dict and non-dict values
        value = resolver_data.get("value", resolver_data) if isinstance(resolver_data, dict) else resolver_data

        candidates.append({
            "value": value,
            "source": f"fallback_local:{context_name}",
            "metadata": {
                "resolver": "fallback_local",
                "precedence": 5,
                "policy_required": True,
                "local_only": True
            }
        })

    return candidates


def validate_binding(value: Any, context_type: ContextType) -> tuple[bool, str | None]:
    """Validate a resolved binding against declared validation rules.

    Args:
        value: The resolved value to validate
        context_type: ContextType with validation rules

    Returns:
        (is_valid, error_message) tuple
        If valid: (True, None)
        If invalid: (False, human-readable error message)
    """
    if not context_type.validation:
        # No validation rules; binding is valid
        return (True, None)

    # Validate each rule
    for rule_name, rule_value in context_type.validation.items():
        is_valid, error = _validate_rule(value, rule_name, rule_value)
        if not is_valid:
            return (False, error)

    return (True, None)


def _validate_rule(
    value: Any,
    rule_name: str,
    rule_value: Any
) -> tuple[bool, str | None]:
    """Validate a single rule.

    Args:
        value: The value to validate
        rule_name: Name of the validation rule
        rule_value: The rule specification/pattern (optional, depends on rule type)

    Returns:
        (is_valid, error_message) tuple

    Validation rules:
    - artifact_exists: Check if file exists at path (uses bound value as path, or rule_value if provided)
    - path_exists: Check if directory exists (uses bound value as path, or rule_value if provided)
    - slug_format: Check if value matches regex pattern (uses rule_value as pattern)
    """
    if rule_name == "artifact_exists":
        # Check if file exists at the path
        # Boolean True → validate bound value; False → skip; string → explicit path override
        if isinstance(rule_value, bool):
            if not rule_value:
                return (True, None)  # rule disabled
            check_path = str(value)
        elif rule_value:
            check_path = str(rule_value)  # explicit path override
        else:
            check_path = str(value)  # None/falsy → use bound value
        path = Path(check_path)
        if not path.exists() or not path.is_file():
            if rule_value and not isinstance(rule_value, bool):
                return (False, f"artifact_exists rule failed: expected artifact at {rule_value}, got {value}")
            else:
                return (False, f"artifact_exists: Artifact does not exist at {value}")
        return (True, None)

    elif rule_name == "path_exists":
        # Check if directory exists
        # Boolean True → validate bound value; False → skip; string → explicit path override
        if isinstance(rule_value, bool):
            if not rule_value:
                return (True, None)  # rule disabled
            check_path = str(value)
        elif rule_value:
            check_path = str(rule_value)  # explicit path override
        else:
            check_path = str(value)  # None/falsy → use bound value
        path = Path(check_path)
        if not path.exists() or not path.is_dir():
            if rule_value and not isinstance(rule_value, bool):
                return (False, f"path_exists rule failed: expected directory at {rule_value}, got {value}")
            else:
                return (False, f"path_exists: Directory does not exist at {value}")
        return (True, None)

    elif rule_name == "slug_format":
        # Check if value matches regex pattern
        # rule_value MUST be provided for this rule (the regex pattern)
        pattern = str(rule_value)
        if not re.match(f"^{pattern}$", str(value)):
            return (False, f"slug_format rule failed: value '{value}' does not match pattern '{pattern}'")
        return (True, None)

    else:
        return (False, f"Unknown validation rule '{rule_name}': "
                f"supported rules are artifact_exists, path_exists, slug_format")
