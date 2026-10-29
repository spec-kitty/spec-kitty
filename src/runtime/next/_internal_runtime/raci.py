"""RACI inference and resolution engine.

Provides deterministic RACI role assignment for mission steps.
All operations are local-only, offline, and deterministic.
"""

# Internalized from spec-kitty-runtime 0.4.3 as part of
# `shared-package-boundary-cutover-01KQ22DS` (mission). See
# `runtime-standalone-package-retirement-01KQ20Z8` for the upstream
# public-API inventory.
from __future__ import annotations

from typing import Any, Literal, cast

from spec_kitty_events import (
    HUMAN_IN_CHARGE_ACTOR_ID,
    UNKNOWN_ACTOR_ID,
    RaciRoleBinding,
    ResolvedRaciSnapshot,
)

from runtime.next._internal_runtime.schema import (
    AuditStep,
    MissionPolicySnapshot,
    MissionRuntimeError,
    PromptStep,
    RACIAssignment,
    RACIEscalationPayload,
    RACIRoleSpec,
)

ActorType = Literal["human", "llm", "service"]


def bind_actor(actor_type: ActorType, actor_id: str | None) -> RaciRoleBinding:
    """Build a resolved RACI binding, filling a missing id with the sentinel.

    A ``None`` or blank ``actor_id`` maps to ``HUMAN_IN_CHARGE_ACTOR_ID`` for a
    human and to ``UNKNOWN_ACTOR_ID`` for an llm or service (operator ruling
    on #6445, 2026-10-19). A present id is kept as given.
    """
    if actor_id is not None and actor_id.strip():
        return RaciRoleBinding(actor_type=actor_type, actor_id=actor_id)
    sentinel = HUMAN_IN_CHARGE_ACTOR_ID if actor_type == "human" else UNKNOWN_ACTOR_ID
    return RaciRoleBinding(actor_type=actor_type, actor_id=sentinel)


def _inferred_assignment(
    step: PromptStep | AuditStep,
    mission_policy: MissionPolicySnapshot,  # noqa: ARG001
) -> tuple[RACIAssignment, str]:
    """The default RACI assignment for a step type and the rule that chose it.

    - PromptStep → R:llm, A:human — rule ``prompt_default``
    - AuditStep (blocking) → R:human, A:human — rule ``audit_blocking``
    - AuditStep (advisory) → R:llm, A:human — rule ``audit_advisory``
    """
    if isinstance(step, AuditStep) and step.audit.enforcement == "blocking":
        responsible: ActorType = "human"
        rule = "audit_blocking"
    elif isinstance(step, AuditStep):
        responsible = "llm"
        rule = "audit_advisory"
    else:
        responsible = "llm"
        rule = "prompt_default"
    assignment = RACIAssignment(
        responsible=RACIRoleSpec(actor_type=responsible),
        accountable=RACIRoleSpec(actor_type="human"),
    )
    return assignment, rule


def infer_raci(
    step: PromptStep | AuditStep,
    mission_policy: MissionPolicySnapshot,
) -> ResolvedRaciSnapshot:
    """Infer default RACI bindings from step type, with sentinel actor ids.

    The engine persists this when ``resolve_raci`` cannot resolve a required
    role from the runtime inputs, so every role carries the sentinel for its
    type (see :func:`bind_actor`).

    Args:
        step: The mission step to infer RACI for.
        mission_policy: Current mission policy snapshot.

    Returns:
        ResolvedRaciSnapshot with source="inferred" and the applicable rule name.
    """
    assignment, rule = _inferred_assignment(step, mission_policy)
    return ResolvedRaciSnapshot(
        step_id=step.id,
        responsible=bind_actor(assignment.responsible.actor_type, assignment.responsible.actor_id),
        accountable=bind_actor(assignment.accountable.actor_type, assignment.accountable.actor_id),
        consulted=[bind_actor(c.actor_type, c.actor_id) for c in assignment.consulted],
        informed=[bind_actor(i.actor_type, i.actor_id) for i in assignment.informed],
        source="inferred",
        inferred_rule=rule,
    )


def validate_raci_assignment(
    assignment: RACIAssignment,
    step: PromptStep | AuditStep,
) -> tuple[bool, list[str]]:
    """Validate RACI assignment against P0 invariants.

    Checks:
    - Accountable must be human
    - For blocking audit steps: responsible must be human
    - LLM never in R/A for blocking audit decisions

    Args:
        assignment: The RACI assignment to validate.
        step: The step this assignment applies to.

    Returns:
        (is_valid, error_messages) tuple.
    """
    errors: list[str] = []

    # P0: accountable must always be human
    if assignment.accountable.actor_type != "human":
        errors.append(
            f"P0 invariant violation: accountable must be human, "
            f"got '{assignment.accountable.actor_type}'"
        )

    # For blocking audit: responsible must be human
    if (
        isinstance(step, AuditStep)
        and step.audit.enforcement == "blocking"
        and assignment.responsible.actor_type != "human"
    ):
        errors.append(
            f"Blocking audit step '{step.id}': responsible must be human, "
            f"got '{assignment.responsible.actor_type}'"
        )

    return (len(errors) == 0, errors)


def resolve_raci(
    step: PromptStep | AuditStep,
    inputs: dict[str, Any],
    mission_policy: MissionPolicySnapshot,
) -> ResolvedRaciSnapshot:
    """Resolve RACI to concrete actors using runtime inputs.

    Resolution order:
    1. If step has explicit raci block → use it (source="explicit")
    2. Otherwise → infer defaults (source="inferred")

    Actor ID resolution:
    - actor_type="human" with no or blank actor_id → resolved from inputs["mission_owner_id"]
    - actor_type="llm" with no or blank actor_id → resolved from inputs.get("agent_id")
    - actor_type="service" with no or blank actor_id → resolved from inputs.get("service_id")

    Fail-closed: unresolvable R/A roles raise MissionRuntimeError with
    RACIEscalationPayload. Unresolvable C/I roles take the sentinel for their
    type (:func:`bind_actor`).

    Args:
        step: The mission step to resolve RACI for.
        inputs: Runtime inputs dict (mission_owner_id, agent_id, etc.).
        mission_policy: Current mission policy snapshot.

    Returns:
        ResolvedRaciSnapshot whose every role carries an actor id.

    Raises:
        MissionRuntimeError: When a required role (R/A) cannot be resolved.
    """
    inferred_rule: str | None = None
    override_reason: str | None = None
    if step.raci is not None:
        # Explicit override path
        assignment = step.raci
        override_reason = step.raci_override_reason  # guaranteed non-None by schema validator

        is_valid, errors = validate_raci_assignment(assignment, step)
        if not is_valid:
            raise MissionRuntimeError(
                f"Invalid explicit RACI for step '{step.id}': {'; '.join(errors)}"
            )
    else:
        assignment, inferred_rule = _inferred_assignment(step, mission_policy)

    return ResolvedRaciSnapshot(
        step_id=step.id,
        responsible=_resolve_actor(assignment.responsible, "responsible", step.id, inputs),
        accountable=_resolve_actor(assignment.accountable, "accountable", step.id, inputs),
        consulted=[_resolve_actor_optional(c, inputs) for c in assignment.consulted],
        informed=[_resolve_actor_optional(i, inputs) for i in assignment.informed],
        source="explicit" if step.raci is not None else "inferred",
        inferred_rule=inferred_rule,
        override_reason=override_reason,
    )


def _resolve_actor(
    binding: RACIRoleSpec,
    role_name: str,
    step_id: str,
    inputs: dict[str, Any],
) -> RaciRoleBinding:
    """Resolve a required actor binding to a concrete actor ID.

    Fail-closed: raises MissionRuntimeError if the actor cannot be resolved.
    """
    resolved_id = _given_or_input_id(binding, inputs)
    if resolved_id is None:
        input_key = _actor_type_to_input_key(binding.actor_type)
        escalation = RACIEscalationPayload(
            run_id=inputs.get("run_id", "unknown"),
            step_id=step_id,
            unresolved_role=cast(
                Literal["responsible", "accountable"],
                role_name if role_name in ("responsible", "accountable") else "responsible",
            ),
            actor_type_expected=binding.actor_type,
            reason=f"Cannot resolve {role_name} actor: '{input_key}' not found in inputs",
            resolution_hint=f"Provide '{input_key}' in mission inputs",
        )
        raise MissionRuntimeError(
            f"RACI escalation for step '{step_id}': {escalation.reason}"
        )

    return RaciRoleBinding(actor_type=binding.actor_type, actor_id=resolved_id)


def _resolve_actor_optional(
    binding: RACIRoleSpec,
    inputs: dict[str, Any],
) -> RaciRoleBinding:
    """Resolve an optional actor binding (C/I roles).

    Non-blocking: an id that cannot be resolved from the inputs takes the
    sentinel for the actor type (:func:`bind_actor`).
    """
    return bind_actor(binding.actor_type, _given_or_input_id(binding, inputs))


def _given_or_input_id(binding: RACIRoleSpec, inputs: dict[str, Any]) -> str | None:
    """The template's own non-blank actor id, else the one the inputs name."""
    if binding.actor_id is not None and binding.actor_id.strip():
        return binding.actor_id
    return _lookup_actor_id(binding.actor_type, inputs)


def _lookup_actor_id(actor_type: str, inputs: dict[str, Any]) -> str | None:
    """Look up actor ID from inputs based on actor type."""
    key = _actor_type_to_input_key(actor_type)
    value = inputs.get(key)
    if isinstance(value, str):
        value = value.strip()
        return value if value else None
    return None


def _actor_type_to_input_key(actor_type: str) -> str:
    """Map actor type to the expected input key."""
    mapping = {
        "human": "mission_owner_id",
        "llm": "agent_id",
        "service": "service_id",
    }
    return mapping.get(actor_type, actor_type)
