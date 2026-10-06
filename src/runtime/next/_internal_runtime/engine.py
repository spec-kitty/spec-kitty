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
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal, cast
from uuid import uuid4

import yaml
from pydantic import BaseModel, ConfigDict

from kernel.clock import now_utc, now_utc_iso
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
    DecisionAnswer,
    DecisionRequest,
    MissionPolicySnapshot,
    MissionRunSnapshot,
    MissionRuntimeError,
    MissionTemplate,
    NextDecision,
    PromptStep,
    RACIRoleBinding,
    load_mission_template_file,
)
from runtime.next._internal_runtime.significance import (
    SignificanceEvaluatedPayload,
    SignificanceScore,
    SoftGateDecision,
    evaluate_significance,
    parse_band_cutoffs_from_policy,
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


def _record_step_completed(run_dir: Path, run_id: str, step_id: str, agent_id: str, result: ResultType, emitter: RuntimeEventEmitter) -> None:
    """Persist + emit ``NextStepAutoCompleted`` for the step the result closed."""
    payload = NextStepAutoCompletedPayload(run_id=run_id, step_id=step_id, agent_id=agent_id, result=result, actor=_actor(agent_id))
    _append_event(run_dir, NEXT_STEP_AUTO_COMPLETED, payload.model_dump(mode="json"))
    emitter.emit_next_step_auto_completed(payload)


def _record_significance(run_dir: Path, payload: SignificanceEvaluatedPayload, emitter: RuntimeEventEmitter) -> None:
    """Persist + emit the ``SignificanceEvaluated`` event of an audit gate."""
    _append_event(run_dir, "SignificanceEvaluated", payload.model_dump(mode="json"))
    emitter.emit_significance_evaluated(payload)


def _record_step_issued(run_dir: Path, run_id: str, step_id: str, agent_id: str, emitter: RuntimeEventEmitter) -> None:
    """Persist + emit ``NextStepIssued`` for the step the plan issues."""
    payload = NextStepIssuedPayload(run_id=run_id, step_id=step_id, agent_id=agent_id, actor=_actor(agent_id))
    _append_event(run_dir, NEXT_STEP_ISSUED, payload.model_dump(mode="json"))
    emitter.emit_next_step_issued(payload)


def _request_decision_input(
    run_dir: Path,
    run_id: str,
    decision: NextDecision,
    agent_id: str,
    pending: dict[str, Any],
    emitter: RuntimeEventEmitter,
) -> dict[str, Any]:
    """Persist input-keyed decisions in ``pending`` so they are answerable.

    Only records + emits on first occurrence (``decision.decision_id`` not yet
    in ``pending``) to avoid duplicates on re-poll. Returns the pending map
    (a new map when the request was added, ``pending`` itself otherwise)."""
    assert decision.decision_id is not None
    if decision.decision_id in pending:
        return pending
    actor = _actor(agent_id)
    request = DecisionRequest(
        decision_id=decision.decision_id,
        step_id=decision.step_id or "",
        question=decision.question or "",
        options=decision.options or [],
        requested_by=actor,
        requested_at=now_utc(),
    )
    requested_payload = DecisionInputRequestedPayload(
        run_id=run_id,
        decision_id=decision.decision_id,
        step_id=decision.step_id or "",
        question=decision.question or "",
        options=tuple(decision.options or []),
        input_key=decision.input_key,
        actor=actor,
    )
    _append_event(run_dir, DECISION_INPUT_REQUESTED, requested_payload.model_dump(mode="json"))
    emitter.emit_decision_input_requested(requested_payload)
    return {**pending, decision.decision_id: request.model_dump(mode="json")}


def _record_run_completed(run_dir: Path, run_id: str, mission_key: str, agent_id: str, emitter: RuntimeEventEmitter) -> None:
    """Persist + emit ``MissionRunCompleted`` (the transition into terminal)."""
    payload = MissionRunCompletedPayload(run_id=run_id, mission_type=mission_key, actor=_actor(agent_id))
    _append_event(run_dir, MISSION_RUN_COMPLETED, payload.model_dump(mode="json"))
    emitter.emit_mission_run_completed(payload)


def _commit_advance(
    run_ref: MissionRunRef,
    plan: AdvancePlan,
    agent_id: str,
    emitter: RuntimeEventEmitter,
    *,
    before_run_completed: Callable[[], None] | None = None,
) -> None:
    """Persist + emit a plan: the events in their historical order, then the snapshot.

    ``before_run_completed`` is an abort-only guard: on the transition into
    terminal it runs before ``MissionRunCompleted`` is recorded. If it raises,
    the error propagates, events already appended (step completed,
    significance) stay, ``MissionRunCompleted`` is not appended and
    ``state.json`` is not written. It is not called on a re-poll of an
    already-terminal run (no completed step)."""
    run_dir = Path(run_ref.run_dir)
    snapshot = plan.snapshot
    decision = plan.decision

    if plan.completed_step_id is not None:
        _record_step_completed(run_dir, snapshot.run_id, plan.completed_step_id, agent_id, plan.result, emitter)
    if plan.significance is not None:
        _record_significance(run_dir, plan.significance, emitter)

    issued_step_id: str | None = None
    pending_decisions = dict(snapshot.pending_decisions)
    if decision.kind == "step" and decision.step_id:
        issued_step_id = decision.step_id
        _record_step_issued(run_dir, snapshot.run_id, decision.step_id, agent_id, emitter)
    elif decision.kind == "decision_required" and decision.decision_id:
        pending_decisions = _request_decision_input(run_dir, snapshot.run_id, decision, agent_id, pending_decisions, emitter)
    elif decision.kind == "terminal" and plan.completed_step_id is not None:
        # Only on the transition into terminal (last step just completed), not on re-polls.
        if before_run_completed is not None:
            before_run_completed()
        _record_run_completed(run_dir, snapshot.run_id, snapshot.mission_key, agent_id, emitter)

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


def commit_advance(
    run_ref: MissionRunRef,
    plan: AdvancePlan,
    agent_id: str,
    emitter: RuntimeEventEmitter | None = None,
    *,
    before_run_completed: Callable[[], None] | None = None,
) -> NextDecision:
    """Commit a plan a caller already computed with :func:`plan_advance`.

    The caller planned first (the bridge resolves a WP-iteration step's
    workspace before anything is persisted) and commits THAT plan -- the
    engine does not plan a second time. The plan is refused with
    :class:`StaleAdvancePlan`, writing nothing, when the run's persisted state
    is no longer the state it was planned from: committing it would overwrite
    newer progress.

    ``before_run_completed`` is an abort-only guard called on the transition
    into terminal, before ``MissionRunCompleted`` is recorded; if it raises,
    the error propagates, ``MissionRunCompleted`` is not appended and
    ``state.json`` is not written (events already appended stay). It runs
    after the stale-plan check, which still writes nothing.
    """
    if _read_snapshot(Path(run_ref.run_dir)) != plan.source:
        raise StaleAdvancePlan(f"Run '{plan.source.run_id}' changed after the advance was planned; plan again.")
    _commit_advance(run_ref, plan, agent_id, emitter or NullEmitter(), before_run_completed=before_run_completed)
    return plan.decision


_AUDIT_PREFIX = "audit:"
_INPUT_PREFIX = "input:"
_MEDIUM_BAND_ANSWERS = frozenset({"decide_solo", "open_stand_up", "defer"})


def _raci_binding(
    decisions: dict[str, Any],
    snapshot: MissionRunSnapshot,
    decision_id: str,
) -> tuple[str | None, str | None]:
    """WP06: the persisted RACI ``(source, override_reason)`` for a decision's step."""
    raci_step_id: str | None = None
    if decision_id.startswith(_AUDIT_PREFIX):
        raci_step_id = decision_id[len(_AUDIT_PREFIX) :]
    elif decision_id.startswith(_INPUT_PREFIX):
        # For input decisions, check if there's an issued step with RACI
        raci_step_id = snapshot.issued_step_id
    record = decisions.get(f"raci:{raci_step_id}") if raci_step_id else None
    if isinstance(record, dict):
        return record.get("source"), record.get("override_reason")
    return None, None


def _significance_band(decisions: dict[str, Any], decision_id: str) -> str | None:
    """WP05: the effective significance band name recorded for an audit decision."""
    sig_data = decisions.get(f"significance:{decision_id}")
    if not isinstance(sig_data, dict):
        return None
    band = sig_data.get("effective_band")
    return band.get("name") if isinstance(band, dict) else band


def _audit_denial_reason(actor: ActorIdentity, inputs: dict[str, Any]) -> str | None:
    """Why ``actor`` may not answer an audit decision, or ``None`` when allowed."""
    mission_owner_id = _resolve_mission_owner_id(inputs)
    if actor.actor_type != "human":
        return "Audit decisions require a human actor"
    if not mission_owner_id:
        return "Audit decisions require mission_owner_id to be set in inputs"
    if actor.actor_id != mission_owner_id:
        return f"Audit decisions require mission owner '{mission_owner_id}'"
    return None


def _validate_audit_answer(band: str | None, answer: str) -> None:
    """WP05: significance-aware answer validation (T015 when no band was evaluated)."""
    if band == "medium":
        if answer not in _MEDIUM_BAND_ANSWERS:
            raise MissionRuntimeError(f"Medium-band decision requires one of {sorted(_MEDIUM_BAND_ANSWERS)}, got: {answer!r}")
    elif band == "high":
        if answer not in ("approve", "reject"):
            raise MissionRuntimeError(f"High-band decision requires one of {{'approve', 'reject'}}, got: {answer!r}")
    elif answer not in ("approve", "reject"):
        raise MissionRuntimeError(f"Invalid audit answer '{answer}': must be 'approve' or 'reject'")


def _authorize_audit_answer(
    run_dir: Path,
    snapshot: MissionRunSnapshot,
    decision_id: str,
    answer: str,
    actor: ActorIdentity,
    raci_source: str | None,
    raci_override_reason: str | None,
) -> str:
    """T014: audit owner checks, then answer validation. Returns the authority role.

    A denial appends ``DecisionAuthorityDenied`` (``rationale_linkage`` null)
    and raises; nothing else is written."""
    authority_role = "mission_owner"
    deny_reason = _audit_denial_reason(actor, snapshot.inputs)
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
                "rationale_linkage": None,
                "reason": deny_reason,
                "raci_source": raci_source,
                "override_reason": raci_override_reason,
            },
        )
        raise MissionRuntimeError(deny_reason)
    _validate_audit_answer(_significance_band(snapshot.decisions, decision_id), answer)
    return authority_role


def _authorize_llm_answer(inputs: dict[str, Any], decision_id: str, actor: ActorIdentity) -> tuple[str, str]:
    """An LLM answer needs a delegation with a rationale. Returns ``(role, rationale)``."""
    delegation = _resolve_delegation_record(inputs, decision_id)
    if delegation is None:
        raise MissionRuntimeError(f"LLM actor '{actor.actor_id}' is not delegated for decision '{decision_id}'")

    authority_role = delegation.get("authority_role") or "delegated_llm"
    if not isinstance(authority_role, str):
        authority_role = "delegated_llm"

    rationale_raw = delegation.get("rationale_linkage")
    rationale = rationale_raw.strip() if isinstance(rationale_raw, str) else ""
    if not rationale:
        raise MissionRuntimeError(f"LLM delegation for decision '{decision_id}' must include non-empty rationale_linkage")
    return authority_role, rationale


def _record_soft_gate(
    decisions: dict[str, Any],
    decision_id: str,
    answer: str,
    actor: ActorIdentity,
) -> None:
    """Medium band: persist the ``SoftGateDecision`` under ``soft_gate:<decision_id>``."""
    # `answer` is validated upstream against the SoftGate action set
    # (`decide_solo` / `open_stand_up` / `defer`); pydantic re-validates
    # at SoftGateDecision construction so the cast is a typing assist
    # rather than a trust boundary widening.
    soft_gate_action = cast(Literal["decide_solo", "open_stand_up", "defer"], answer)
    actor_type = cast(Literal["human", "llm", "service"], actor.actor_type)
    soft_gate = SoftGateDecision(
        decision_id=decision_id,
        action=soft_gate_action,
        actor=RACIRoleBinding(actor_type=actor_type, actor_id=actor.actor_id),
        timestamp=now_utc(),
        significance_score=SignificanceScore.model_validate(decisions[f"significance:{decision_id}"]),
        outcome=soft_gate_action if answer == "decide_solo" else None,
    )
    decisions[f"soft_gate:{decision_id}"] = soft_gate.model_dump(mode="json")


def _apply_audit_answer(
    snapshot: MissionRunSnapshot,
    decisions: dict[str, Any],
    completed_steps: list[str],
    pending: dict[str, Any],
    decision_id: str,
    answer: str,
    actor: ActorIdentity,
) -> str | None:
    """WP05 significance-aware gate handling. Mutates the working maps in place.

    Returns the (possibly new) ``blocked_reason``. The MEDIUM re-add of an
    open gate reads the ORIGINAL ``snapshot.pending_decisions``."""
    audit_step_id = decision_id[len(_AUDIT_PREFIX) :]
    if _significance_band(decisions, decision_id) == "medium":
        _record_soft_gate(decisions, decision_id, answer, actor)
        if answer == "decide_solo":
            # Gate clears -- add to completed_steps
            if audit_step_id not in completed_steps:
                completed_steps.append(audit_step_id)
        else:
            # open_stand_up / defer: gate stays open, re-add to pending
            pending[decision_id] = snapshot.pending_decisions[decision_id]
        return snapshot.blocked_reason
    # HIGH band or no significance: existing behavior
    if answer == "approve":
        # T016: Add audit_step_id to completed_steps so DAG can advance.
        if audit_step_id not in completed_steps:
            completed_steps.append(audit_step_id)
        return snapshot.blocked_reason
    # T017: Set blocked_reason; run is permanently blocked.
    return f"Audit step '{audit_step_id}' rejected by {actor.actor_id}"


def provide_decision_answer(
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
        raise MissionRuntimeError(f"Decision '{decision_id}' not found in pending_decisions for run '{snapshot.run_id}'")

    decisions = dict(snapshot.decisions)
    inputs = dict(snapshot.inputs)
    completed_steps = list(snapshot.completed_steps)
    blocked_reason = snapshot.blocked_reason
    authority_role = actor.actor_type
    rationale_linkage: str | None = None
    raci_source, raci_override_reason = _raci_binding(decisions, snapshot, decision_id)

    is_audit = decision_id.startswith(_AUDIT_PREFIX)
    if is_audit:
        authority_role = _authorize_audit_answer(run_dir, snapshot, decision_id, answer, actor, raci_source, raci_override_reason)
    elif actor.actor_type == "llm":
        authority_role, rationale_linkage = _authorize_llm_answer(inputs, decision_id, actor)

    answer_data = DecisionAnswer(
        decision_id=decision_id,
        answer=answer,
        answered_by=actor,
        answered_at=now_utc(),
    )
    decision_record = answer_data.model_dump(mode="json")
    decision_record.update(
        _authority_metadata(
            actor,
            authority_role,
            rationale_linkage,
            raci_source=raci_source,
            override_reason=raci_override_reason,
        )
    )
    decisions[decision_id] = decision_record
    del pending[decision_id]

    if is_audit:
        blocked_reason = _apply_audit_answer(snapshot, decisions, completed_steps, pending, decision_id, answer, actor)
    elif decision_id.startswith(_INPUT_PREFIX):
        # For input-keyed decisions, write the answer into inputs so requires_inputs is satisfied.
        inputs[decision_id[len(_INPUT_PREFIX) :]] = answer

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
        run_id=snapshot.run_id,
        decision_id=decision_id,
        answer=answer,
        actor=actor,
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
