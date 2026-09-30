"""Deterministic mission planner with DAG-based step resolution.

WP11 addition: ``_resolve_workflow_for_mission`` / ``resolve_next_workflow_action``
------------------------------------------------------------------------------------
Slice F WP11 adds a lightweight workflow-resolver shim on top of the existing
DAG-based runtime planner.  The two entry points are kept separate so the
internal ``plan_next`` (DAG engine, used by ``engine.py`` and
``runtime_bridge.py``) is not disturbed.

* ``_resolve_workflow_for_mission(mission_dir)`` — reads ``meta.json``,
  extracts ``workflow_id``, and returns the validated ``WorkflowSequence``
  from project overrides or shipped defaults (defaulting to
  ``software-dev-default`` when ``workflow_id`` is absent). Unknown ids
  propagate ``UnknownWorkflowError`` — no silent fallback (FR-015 binding).
* ``PlanResult`` — lightweight dataclass returned by
  ``resolve_next_workflow_action``.
* ``resolve_next_workflow_action(mission_dir, current_action)`` — looks up the
  workflow and resolves the next action from the graph.  Returns a
  ``PlanResult``.  Raises ``ValueError`` when ``current_action`` is not in the
  workflow, and ``UnknownWorkflowError`` for unknown workflow ids.

Layer rule (C-001 / NFR-003): this module lives inside the runtime package
(``runtime.next._internal_runtime``).  The imports from
``workflow_registry`` and ``workflow_schema`` stay within the same package;
no ``charter`` or ``doctrine`` (Python modules) imports.

``kernel.clock`` is the one sanctioned exception (mission
``kernel-clock-single-door``, D-1): this invariant is about runtime
re-extractability -- not depending on the doctrine-family internals that
would break if ``runtime`` were ever split back into its own package -- not
about general purity. ``kernel`` is the stdlib-only layer floor every
package may import (it is not part of the doctrine family and carries no
doctrine-family coupling), so a ``kernel.clock`` import does not violate the
re-extractability rationale this rule protects.
"""

from __future__ import annotations

import dataclasses
import hashlib
from pathlib import Path
from typing import Any

from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.core.paths import load_meta_fail_closed

# Internalized from spec-kitty-runtime 0.4.3 as part of
# `shared-package-boundary-cutover-01KQ22DS` (mission). See
# `runtime-standalone-package-retirement-01KQ20Z8` for the upstream
# public-API inventory.
from runtime.next._internal_runtime.schema import (
    AuditStep,
    DecisionRequest,
    MissionPolicySnapshot,
    MissionRunSnapshot,
    MissionTemplate,
    NextDecision,
    PromptStep,
    StepContextBundle,
)
from runtime.next._internal_runtime.workflow_registry import (
    get_workflow,
    list_available_workflows,
)
from runtime.next._internal_runtime.workflow_schema import ActionStep, WorkflowSequence
from runtime.next.decision import DecisionKind

# No __all__ declaration here: the workflow-resolver additions (PlanResult,
# _resolve_workflow_for_mission, resolve_next_workflow_action) are intentionally
# kept as non-exported symbols so the symbol-level dead-code gate does not
# require them to have callers in other src/ files.  They are exercised by
# integration tests and by prompt_builder._workflow_for, which reaches this
# function indirectly via runtime_bridge_engine.resolve_workflow_for_mission
# (the FR-013 sole-home adapter wrapper) rather than importing it directly.


# ---------------------------------------------------------------------------
# Workflow-resolver shim (Slice F WP11, FR-013 / FR-014 / FR-015 / C-008)
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class PlanResult:
    """Result of ``resolve_next_workflow_action``.

    Attributes
    ----------
    current_action:
        The action passed in as the current state of the mission.
    next_action:
        The action that follows ``current_action`` in the workflow graph,
        or ``None`` when ``current_action`` is a terminal action.
    workflow_id:
        The workflow that was consulted (either from ``meta.json`` or the
        ``software-dev-default`` fallback).
    """

    current_action: str
    next_action: str | None
    workflow_id: str


def compose_template_with_workflow(
    template: MissionTemplate,
    workflow: WorkflowSequence,
) -> MissionTemplate:
    """Return a runtime template whose steps follow *workflow*.

    The workflow artifact owns public action ordering; the runtime still needs
    a ``MissionTemplate`` DAG. This adapter keeps the live ``spec-kitty next``
    path on the same planner while preserving existing step metadata when an
    action matches a shipped/custom mission step.
    """
    by_id = {step.id: step for step in template.steps}
    composed: list[PromptStep] = []
    previous_id: str | None = None

    if workflow.initial == "specify" and "discovery" in by_id and "discovery" not in {
        action.action_name for action in workflow.actions
    }:
        discovery = by_id["discovery"]
        composed.append(
            PromptStep(
                id=discovery.id,
                title=discovery.title,
                description=discovery.description,
                prompt=discovery.prompt,
                prompt_template=discovery.prompt_template,
                expected_output=discovery.expected_output,
                requires_inputs=discovery.requires_inputs,
                depends_on=[],
                raci=discovery.raci,
                raci_override_reason=discovery.raci_override_reason,
                agent_profile=discovery.agent_profile,
                contract_ref=discovery.contract_ref,
            )
        )
        previous_id = "discovery"

    for action in workflow.actions:
        source = by_id.get(action.action_name)
        depends_on = [previous_id] if previous_id is not None else []
        if source is not None:
            step = PromptStep(
                id=source.id,
                title=source.title,
                description=action.description or source.description,
                prompt=source.prompt,
                prompt_template=source.prompt_template,
                expected_output=source.expected_output,
                requires_inputs=source.requires_inputs,
                depends_on=depends_on,
                raci=source.raci,
                raci_override_reason=source.raci_override_reason,
                agent_profile=action.agent_profile or source.agent_profile,
                contract_ref=source.contract_ref,
            )
        else:
            step = PromptStep(
                id=action.action_name,
                title=action.action_name.replace("-", " ").title(),
                description=action.description,
                prompt_template=f"{action.action_name}.md",
                requires_inputs=[action.human_in_the_loop] if action.human_in_the_loop else [],
                depends_on=depends_on,
                agent_profile=action.agent_profile,
            )
        composed.append(step)
        previous_id = action.action_name

    return MissionTemplate(
        mission=template.mission,
        steps=composed,
        audit_steps=template.audit_steps,
    )


def _resolve_workflow_for_mission(mission_dir: Path) -> WorkflowSequence:
    """Return the ``WorkflowSequence`` for the mission rooted at *mission_dir*.

    Reads ``meta.json`` (if present) and extracts ``workflow_id``.  When
    ``workflow_id`` is absent (pre-Slice-F missions) the permanent default
    ``software-dev-default`` is returned — this is the NEW-2 resolution
    (opt-in, not migration-required).

    Raises
    ------
    UnknownWorkflowError
        When ``workflow_id`` is present in ``meta.json`` but cannot be
        resolved by the registry.  FR-015 binding: no silent fallback.
    """
    project_root = _infer_project_root(mission_dir)
    # FR-007 / #3162: routed through the ONE fail-closed reader — a missing
    # meta.json still absorbs to None (the pre-Slice-F default arm); a corrupt
    # or non-object one raises the typed MissionMetaReadError instead of a raw
    # ValueError.
    meta = load_meta_fail_closed(mission_dir)
    if meta is None:
        return get_workflow("software-dev-default", project_root=project_root)
    workflow_id: str | None = meta.get("workflow_id")
    if workflow_id is None:
        return get_workflow("software-dev-default", project_root=project_root)
    # Unknown ids propagate UnknownWorkflowError — no silent fallback (FR-015).
    return get_workflow(workflow_id, project_root=project_root)


def _infer_project_root(mission_dir: Path) -> Path | None:
    """Infer the project root that owns *mission_dir* for `.kittify` lookup."""
    current = mission_dir.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".kittify").exists():
            return candidate
        if candidate.name == KITTY_SPECS_DIR:
            return candidate.parent
    return None


def resolve_next_workflow_action(
    mission_dir: Path,
    current_action: str,
) -> PlanResult:
    """Resolve the next action for *mission_dir* given *current_action*.

    Uses the workflow declared in ``meta.json::workflow_id`` (defaulting to
    ``software-dev-default`` when absent — FR-013 / NEW-2 permanent default).

    Returns
    -------
    PlanResult
        With ``next_action=None`` when ``current_action`` is a terminal action.

    Raises
    ------
    UnknownWorkflowError
        When ``workflow_id`` in ``meta.json`` cannot be resolved (FR-015 —
        no silent fallback).  Propagated from ``_resolve_workflow_for_mission``
        without modification so the registry's diagnostic message (listing
        available workflow ids via ``list_available_workflows``) reaches the
        caller intact.
    ValueError
        When ``current_action`` is not present in the workflow's action graph.
    """
    workflow: WorkflowSequence = _resolve_workflow_for_mission(mission_dir)
    by_name: dict[str, ActionStep] = {a.action_name: a for a in workflow.actions}
    action: ActionStep | None = by_name.get(current_action)
    if action is None:
        available_workflows = list_available_workflows(project_root=_infer_project_root(mission_dir))
        raise ValueError(
            f"action {current_action!r} not in workflow {workflow.workflow_id!r}. "
            f"Available actions: {sorted(by_name)}. "
            f"Available workflows: {available_workflows}"
        )
    next_action: str | None = action.next[0] if action.next else None
    return PlanResult(
        current_action=current_action,
        next_action=next_action,
        workflow_id=workflow.workflow_id,
    )


def _resolve_next_unified_step(
    template: MissionTemplate,
    snapshot: MissionRunSnapshot,
) -> PromptStep | AuditStep | None:
    """Find the next runnable step via deterministic DAG traversal.

    Combined sequence: regular steps first (template order), then audit steps
    (template order, with depends_on resolved).

    1. Skip completed steps (in snapshot.completed_steps)
    2. Skip the currently issued step (snapshot.issued_step_id)
    3. For each remaining step, verify all depends_on are in completed_steps
    4. Among eligible steps, return the first by combined sequence order
    5. Return None if no step is eligible (all done or all blocked)
    """
    completed = set(snapshot.completed_steps)

    for step in template.steps:
        if step.id in completed:
            continue
        if step.id == snapshot.issued_step_id:
            continue
        unmet = [dep for dep in step.depends_on if dep not in completed]
        if unmet:
            continue
        return step

    for audit_step in template.audit_steps:
        if audit_step.id in completed:
            continue
        if audit_step.id == snapshot.issued_step_id:
            continue
        unmet = [dep for dep in audit_step.depends_on if dep not in completed]
        if unmet:
            continue
        return audit_step

    return None


def _has_remaining_steps(
    template: MissionTemplate,
    snapshot: MissionRunSnapshot,
) -> bool:
    """Return True if there are uncompleted steps (excluding issued), in both regular and audit lists."""
    for step in template.steps:
        if step.id in snapshot.completed_steps:
            continue
        if step.id == snapshot.issued_step_id:
            continue
        return True
    for audit_step in template.audit_steps:
        if audit_step.id in snapshot.completed_steps:
            continue
        if audit_step.id == snapshot.issued_step_id:
            continue
        return True
    return False


def _check_template_drift(
    snapshot: MissionRunSnapshot,
    live_template_path: Path,
) -> str | None:
    """Return drift reason if live template hash differs from frozen hash.
    Returns None if no drift or if live template doesn't exist."""
    if not live_template_path.exists():
        return None
    live_bytes = live_template_path.read_bytes()
    live_hash = hashlib.sha256(live_bytes).hexdigest()  # noqa: TID251 - production raw SHA-256 owner
    if live_hash != snapshot.template_hash:
        return "Template changed during active run. Migration required."
    return None


def plan_next(
    snapshot: MissionRunSnapshot,
    mission_template: MissionTemplate,
    policy_snapshot: MissionPolicySnapshot,
    actor_context: dict[str, Any] | None = None,
    live_template_path: Path | None = None,
) -> NextDecision:
    """Compute the next deterministic decision for a mission run.

    Uses DAG-based resolution instead of linear step_index.
    Checks pending decisions before DAG traversal.
    Detects template drift if live_template_path is provided.
    """
    actor_context = actor_context or {}

    # Blocked reason takes priority over everything.
    if snapshot.blocked_reason:
        return NextDecision(
            kind=DecisionKind.blocked.value,
            run_id=snapshot.run_id,
            mission_key=snapshot.mission_key,
            reason=snapshot.blocked_reason,
        )

    # Template drift detection.
    if live_template_path is not None:
        drift_reason = _check_template_drift(snapshot, live_template_path)
        if drift_reason:
            return NextDecision(
                kind=DecisionKind.blocked.value,
                run_id=snapshot.run_id,
                mission_key=snapshot.mission_key,
                reason=drift_reason,
            )

    # Pending decisions block before DAG traversal.
    if snapshot.pending_decisions:
        first_key = sorted(snapshot.pending_decisions.keys())[0]  # deterministic
        req = DecisionRequest.model_validate(snapshot.pending_decisions[first_key])
        # Derive input_key from decision_id prefix for input-keyed decisions.
        input_key: str | None = None
        if req.decision_id.startswith("input:"):
            input_key = req.decision_id[len("input:"):]
        return NextDecision(
            kind=DecisionKind.decision_required.value,
            run_id=snapshot.run_id,
            mission_key=snapshot.mission_key,
            step_id=req.step_id,
            decision_id=req.decision_id,
            input_key=input_key,
            question=req.question,
            options=req.options if req.options else None,
            reason="pending_decision",
        )

    # DAG-based step resolution (unified: PromptStep + AuditStep).
    step = _resolve_next_unified_step(mission_template, snapshot)

    if step is None:
        # Distinguish true completion from unschedulable DAG.
        if _has_remaining_steps(mission_template, snapshot):
            return NextDecision(
                kind=DecisionKind.blocked.value,
                run_id=snapshot.run_id,
                mission_key=snapshot.mission_key,
                reason="No eligible steps: remaining steps have unmet dependencies.",
            )
        return NextDecision(
            kind=DecisionKind.terminal.value,
            run_id=snapshot.run_id,
            mission_key=snapshot.mission_key,
            reason="All mission steps completed",
        )

    # --- AuditStep handling ---
    if isinstance(step, AuditStep):
        if step.audit.enforcement == "blocking":
            # Blocking audit → decision_required; input_key is None for audit decisions.
            return NextDecision(
                kind=DecisionKind.decision_required.value,
                run_id=snapshot.run_id,
                mission_key=snapshot.mission_key,
                step_id=step.id,
                step_title=step.title,
                decision_id=f"audit:{step.id}",
                input_key=None,
                question=f"Audit checkpoint: {step.title}. Approve to continue?",
                options=["approve", "reject"],
            )
        else:
            # Advisory audit → emit as a regular step; no requires_inputs check.
            context = StepContextBundle(
                run_id=snapshot.run_id,
                mission_key=snapshot.mission_key,
                step_id=step.id,
                step_title=step.title,
                step_description=step.description,
                expected_output=None,
                policy_snapshot=policy_snapshot,
                actor_context=actor_context,
            )
            return NextDecision(
                kind=DecisionKind.step.value,
                run_id=snapshot.run_id,
                mission_key=snapshot.mission_key,
                step_id=step.id,
                step_title=step.title,
                prompt=f"Execute audit step '{step.id}': {step.title}",
                context=context,
            )

    # --- PromptStep handling ---
    # Check for missing required inputs -> emit input-keyed decision.
    missing_inputs = [
        required
        for required in step.requires_inputs
        if required not in snapshot.inputs and required not in snapshot.decisions
    ]
    if missing_inputs:
        missing = missing_inputs[0]
        decision_id = f"input:{missing}"
        return NextDecision(
            kind=DecisionKind.decision_required.value,
            run_id=snapshot.run_id,
            mission_key=snapshot.mission_key,
            step_id=step.id,
            decision_id=decision_id,
            input_key=missing,
            question=f"Input required before step '{step.id}': provide value for '{missing}'.",
            reason="missing_required_input",
        )

    context = StepContextBundle(
        run_id=snapshot.run_id,
        mission_key=snapshot.mission_key,
        step_id=step.id,
        step_title=step.title,
        step_description=step.description,
        expected_output=step.expected_output,
        policy_snapshot=policy_snapshot,
        actor_context=actor_context,
    )

    prompt = step.prompt or f"Execute step '{step.id}': {step.title}"

    return NextDecision(
        kind=DecisionKind.step.value,
        run_id=snapshot.run_id,
        mission_key=snapshot.mission_key,
        step_id=step.id,
        step_title=step.title,
        prompt=prompt,
        context=context,
    )
