"""Engine-adapter seam for ``runtime.next.runtime_bridge`` (FR-013, #2531 WP03).

**Sole home of the FR-013 grep-complete ``_internal_runtime`` engine/planner
private surface** — the five names ``_read_snapshot`` / ``_load_frozen_template``
(from ``_internal_runtime.engine``), ``_append_event`` / ``_write_snapshot``, and
``plan_next`` (from ``_internal_runtime.planner``), plus the sixth name,
``_resolve_workflow_for_mission`` (also from ``_internal_runtime.planner``),
concentrated here via the ``resolve_workflow_for_mission`` wrapper as the
retro follow-up to the WP03 boundary from ``data-model.md`` §Engine-adapter
surface. ``prompt_builder.py`` now routes through that wrapper instead of
importing the planner private directly — the concentration is complete.
Concentrates every one of the five call sites that used to live scattered across
``runtime_bridge.py`` into a single seam — the grep-complete site list from
``data-model.md`` §Engine-adapter surface: ``:1322``/``:1375``
(``_load_frozen_template``, the classic misses) plus ``:1800``/``:1840``/
``:2606``/``:3261``/``:3416``. No other module under ``src/runtime/next/`` may
import or attribute-access these two ``_internal_runtime`` submodules — enforced
by the architecture guard in ``tests/runtime/test_bridge_engine.py``.

Each wrapper below re-exposes the identical private name it wraps and delegates
via a **live module-attribute lookup** (``_engine.<name>(...)`` /
``_planner.<name>(...)``), never a cached ``from ... import name`` binding. This
preserves the exact behavior the WP01 parity oracle depends on: the oracle
patches ``_internal_runtime.engine._append_event`` / ``._write_snapshot`` /
``._read_snapshot`` directly on the source module
(``tests/runtime/_bridge_oracle.py::capture_side_effects``), and a live
attribute lookup observes that patch regardless of which module performs the
call — a snapshotted ``from module import name`` would not.

``advance_run_state_after_composition`` duplicates the engine's own
``next_step`` success branch to enforce the single-dispatch invariant (FR-001)
for composition-backed actions. Its body is **adapter-owned logic** (reduced to
CC<=15 via the ``_mark_step_completed`` / ``_apply_decision_effects`` /
``_emit_step_issued`` / ``_emit_decision_required`` / ``_emit_terminal``
helpers below). This module owns it outright: the bridge calls
``_engine_adapter.advance_run_state_after_composition`` directly and holds no
forwarding delegate, so a test that replaces it patches
``runtime_bridge_engine.advance_run_state_after_composition``.

That function also calls back into two symbols that stay owned by
``runtime_bridge.py`` (``_is_wp_iteration_step`` and ``_map_runtime_decision``,
reached through a deferred import of the ``runtime_bridge`` module because the
bridge imports this adapter at its own top level and a module-level back-import
would be circular). The retrospective names it needs are owned by
``runtime_bridge_retrospective`` and are called there directly, so a test that
intercepts one patches it on that module.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import yaml

from kernel.clock import now_utc
from mission_runtime import OwnedCheckout
from runtime.next._internal_runtime import engine as _engine
from runtime.next._internal_runtime import planner as _planner
from runtime.next._internal_runtime.events import (
    DECISION_INPUT_REQUESTED,
    MISSION_RUN_COMPLETED,
    NEXT_STEP_AUTO_COMPLETED,
    NEXT_STEP_ISSUED,
    seed_runtime_emitter,
)
from runtime.next._internal_runtime.schema import DecisionRequest, MissionPolicySnapshot, MissionRunSnapshot, MissionRuntimeError, MissionTemplate
from runtime.next import runtime_bridge_retrospective as _retrospective
from runtime.next.decision import DecisionKind
from spec_kitty_events.mission_next import (
    DecisionInputRequestedPayload,
    MissionRunCompletedPayload,
    NextStepAutoCompletedPayload,
    NextStepIssuedPayload,
    RuntimeActorIdentity,
)

if TYPE_CHECKING:
    from runtime.next._internal_runtime import MissionRunRef, NextDecision
    from runtime.next._internal_runtime.engine import AdvancePlan, ResultType
    from runtime.next._internal_runtime.workflow_schema import WorkflowSequence
    from runtime.next.decision import Decision
    from runtime.next._internal_runtime.events import RuntimeEventEmitter

# ---------------------------------------------------------------------------
# T011 — grep-complete engine/planner private-access wrappers
# ---------------------------------------------------------------------------


def _append_event(run_dir: Path, event_type: str, payload: dict[str, Any]) -> None:
    """Wrap ``_internal_runtime.engine._append_event`` (live attribute lookup)."""
    _engine._append_event(run_dir, event_type, payload)


def _read_snapshot(run_dir: Path) -> MissionRunSnapshot:
    """Wrap ``_internal_runtime.engine._read_snapshot`` (live attribute lookup)."""
    return _engine._read_snapshot(run_dir)


def _write_snapshot(run_dir: Path, snapshot: MissionRunSnapshot) -> None:
    """Wrap ``_internal_runtime.engine._write_snapshot`` (live attribute lookup)."""
    _engine._write_snapshot(run_dir, snapshot)


def _load_frozen_template(run_dir: Path) -> MissionTemplate:
    """Wrap ``_internal_runtime.engine._load_frozen_template`` (live attribute lookup)."""
    return _engine._load_frozen_template(run_dir)


def plan_next(
    snapshot: MissionRunSnapshot,
    mission_template: MissionTemplate,
    policy_snapshot: MissionPolicySnapshot,
    actor_context: dict[str, Any] | None = None,
    live_template_path: Path | None = None,
) -> NextDecision:
    """Wrap ``_internal_runtime.planner.plan_next`` (live attribute lookup)."""
    return _planner.plan_next(
        snapshot,
        mission_template,
        policy_snapshot,
        actor_context=actor_context,
        live_template_path=live_template_path,
    )


#: Reading/planning failures of a read-only advance preview: an unreadable run
#: or template (``OSError`` / ``ValueError``, which covers pydantic validation
#: and JSON errors), a runtime error, or malformed template YAML. The real
#: advance that follows reads the same files and reports them with its own
#: existing semantics, so a caller that catches these only skips its
#: pre-resolution -- it never changes behaviour.
StaleAdvancePlan = _engine.StaleAdvancePlan
PLAN_UNAVAILABLE_ERRORS = (OSError, ValueError, MissionRuntimeError, yaml.YAMLError)


def plan_advance(run_ref: MissionRunRef, agent_id: str, result: str = "success") -> AdvancePlan:
    """Wrap ``_internal_runtime.engine.plan_advance`` (live attribute lookup) --
    the engine's single, pure "apply the result and plan the next step"
    authority (WP11 review cycle 1, findings 3/4)."""
    return _engine.plan_advance(run_ref, agent_id, cast("ResultType", result))


def commit_advance(run_ref: MissionRunRef, plan: AdvancePlan, agent_id: str, emitter: RuntimeEventEmitter | None = None) -> NextDecision:
    """Wrap ``_internal_runtime.engine.commit_advance`` (live attribute lookup):
    commit a plan the caller already computed (no second planning). Raises
    :class:`StaleAdvancePlan` -- writing nothing -- when the run moved on."""
    return _engine.commit_advance(run_ref, plan, agent_id, emitter)


def apply_result(snapshot: MissionRunSnapshot, result: ResultType) -> tuple[MissionRunSnapshot, str | None]:
    """Wrap ``_internal_runtime.engine.apply_result`` (live attribute lookup)."""
    return _engine.apply_result(snapshot, result)


def resolve_workflow_for_mission(mission_dir: Path) -> WorkflowSequence:
    """Wrap ``_internal_runtime.planner._resolve_workflow_for_mission`` (live
    attribute lookup; FR-013 concentration)."""
    return _planner._resolve_workflow_for_mission(mission_dir)


# ---------------------------------------------------------------------------
# T012 — ``advance_run_state_after_composition`` body (CC23 -> <=15)
# ---------------------------------------------------------------------------


def _emit_step_completed(
    run_dir: Path,
    snapshot: MissionRunSnapshot,
    completed_step_id: str,
    agent: str,
    sync_emitter: RuntimeEventEmitter,
) -> None:
    """Persist + emit the ``NextStepAutoCompleted`` event of a success."""
    actor = RuntimeActorIdentity(actor_id=agent, actor_type="llm", provider=None, model=None, tool=None)
    payload = NextStepAutoCompletedPayload(
        run_id=snapshot.run_id,
        step_id=completed_step_id,
        agent_id=agent,
        result="success",
        actor=actor,
    )
    _append_event(run_dir, NEXT_STEP_AUTO_COMPLETED, payload.model_dump(mode="json"))
    sync_emitter.emit_next_step_auto_completed(payload)


def _mark_step_completed(
    run_dir: Path,
    snapshot: MissionRunSnapshot,
    agent: str,
    sync_emitter: RuntimeEventEmitter,
) -> tuple[MissionRunSnapshot, bool]:
    """Mark the issued step completed (success path only); emit + persist.

    Returns ``(snapshot, did_complete_step)`` -- ``did_complete_step`` tells the
    terminal branch whether a step genuinely just completed (avoids a duplicate
    ``MissionRunCompleted`` emit on re-poll). The state change itself is the
    engine's :func:`apply_result`.
    """
    applied, completed_step_id = apply_result(snapshot, "success")
    if completed_step_id is None:
        return snapshot, False
    _emit_step_completed(run_dir, applied, completed_step_id, agent, sync_emitter)
    return applied, True


def _live_template_path(snapshot: MissionRunSnapshot) -> Path | None:
    """Resolve the on-disk template path for drift detection, if it still exists."""
    return _engine.existing_template_path(snapshot)


def _emit_step_issued(
    run_dir: Path,
    snapshot: MissionRunSnapshot,
    step_id: str,
    agent: str,
    sync_emitter: RuntimeEventEmitter,
) -> None:
    actor = RuntimeActorIdentity(actor_id=agent, actor_type="llm", provider=None, model=None, tool=None)
    payload = NextStepIssuedPayload(run_id=snapshot.run_id, step_id=step_id, agent_id=agent, actor=actor)
    _append_event(run_dir, NEXT_STEP_ISSUED, payload.model_dump(mode="json"))
    sync_emitter.emit_next_step_issued(payload)


def _emit_decision_required(
    run_dir: Path,
    snapshot: MissionRunSnapshot,
    decision: NextDecision,
    decision_id: str,
    agent: str,
    pending_decisions: dict[str, Any],
    sync_emitter: RuntimeEventEmitter,
) -> dict[str, Any]:
    """Persist + emit a decision-input-request; only on first occurrence (no dupes on re-poll)."""
    if decision_id in pending_decisions:
        return pending_decisions

    actor = RuntimeActorIdentity(actor_id=agent, actor_type="llm", provider=None, model=None, tool=None)
    request = DecisionRequest(
        decision_id=decision_id,
        step_id=decision.step_id or "",
        question=decision.question or "",
        options=decision.options or [],
        requested_by=actor,
        requested_at=now_utc(),
    )
    pending_decisions = dict(pending_decisions)
    pending_decisions[decision_id] = request.model_dump(mode="json")

    payload = DecisionInputRequestedPayload(
        run_id=snapshot.run_id,
        decision_id=decision_id,
        step_id=decision.step_id or "",
        question=decision.question or "",
        options=tuple(decision.options or []),
        input_key=decision.input_key,
        actor=actor,
    )
    _append_event(run_dir, DECISION_INPUT_REQUESTED, payload.model_dump(mode="json"))
    sync_emitter.emit_decision_input_requested(payload)
    return pending_decisions


def _emit_terminal(
    run_dir: Path,
    snapshot: MissionRunSnapshot,
    agent: str,
    mission_slug: str,
    repo_root: Path,
    feature_dir: Path,
    sync_emitter: RuntimeEventEmitter,
    owned: OwnedCheckout | None = None,
) -> None:
    """Run the retrospective gate (if configured) and emit ``MissionRunCompleted``.

    The retrospective policy, mission-id and capture calls go straight to
    ``runtime_bridge_retrospective``, which owns them (see module docstring).

    owned-checkout-lifecycle-authority WP11 (FR-009): retrospective policy is
    a P-local governance read for an owned mission.
    """
    config_root = owned.owned_root if owned is not None else repo_root
    policy, _source_map, policy_error = _retrospective._resolve_retrospective_policy_for_runtime(config_root)
    retrospective_enabled = bool(getattr(policy, "enabled", False))
    # WP18 (#2561): _retrospective_blocks_completion lives in
    # runtime_bridge_retrospective and is reached directly on that seam;
    # runtime_bridge carries no re-export of it.
    block_on_retrospective = _retrospective._retrospective_blocks_completion(policy)
    mission_id = _retrospective._resolve_mission_id_for_terminus(feature_dir)

    if retrospective_enabled and block_on_retrospective:
        if policy_error is not None:
            raise policy_error
        _retrospective._run_retrospective_learning_capture(
            mission_id=mission_id,
            mission_slug=mission_slug,
            feature_dir=feature_dir,
            repo_root=config_root,
            block_on_failure=True,
        )

    actor = RuntimeActorIdentity(actor_id=agent, actor_type="llm", provider=None, model=None, tool=None)
    payload = MissionRunCompletedPayload(run_id=snapshot.run_id, mission_type=snapshot.mission_key, actor=actor)
    _append_event(run_dir, MISSION_RUN_COMPLETED, payload.model_dump(mode="json"))
    sync_emitter.emit_mission_run_completed(payload)

    if retrospective_enabled and not block_on_retrospective:
        _retrospective._run_retrospective_learning_capture(
            mission_id=mission_id,
            mission_slug=mission_slug,
            feature_dir=feature_dir,
            repo_root=config_root,
            block_on_failure=False,
        )


def _apply_decision_effects(
    *,
    run_dir: Path,
    snapshot: MissionRunSnapshot,
    decision: NextDecision,
    agent: str,
    mission_slug: str,
    repo_root: Path,
    feature_dir: Path,
    did_complete_step: bool,
    sync_emitter: RuntimeEventEmitter,
    owned: OwnedCheckout | None = None,
) -> MissionRunSnapshot:
    """Dispatch the 3 ``next_step``-mirroring branches, then fold the result
    (``issued_step_id`` / ``pending_decisions``) back into the snapshot."""
    issued_step_id = snapshot.issued_step_id
    pending_decisions = dict(snapshot.pending_decisions)

    if decision.kind == DecisionKind.step and decision.step_id:
        issued_step_id = decision.step_id
        _emit_step_issued(run_dir, snapshot, decision.step_id, agent, sync_emitter)
    elif decision.kind == DecisionKind.decision_required and decision.decision_id:
        pending_decisions = _emit_decision_required(
            run_dir, snapshot, decision, decision.decision_id, agent, pending_decisions, sync_emitter
        )
    elif decision.kind == DecisionKind.terminal and did_complete_step:
        _emit_terminal(run_dir, snapshot, agent, mission_slug, repo_root, feature_dir, sync_emitter, owned=owned)

    return snapshot.model_copy(update={"issued_step_id": issued_step_id, "pending_decisions": pending_decisions})


def _seed_emitter(sync_emitter: RuntimeEventEmitter, snapshot: Any) -> None:
    """Seed optional producer state through the canonical nonfatal seam."""
    seed_runtime_emitter(sync_emitter, snapshot)


@dataclass(frozen=True)
class CompositionAdvancePlan:
    """What :func:`advance_run_state_after_composition` will commit, computed
    with no writes: the snapshot after the success result was applied, the
    step id that result completed (``None`` when nothing was issued) and the
    planner's next decision."""

    snapshot: MissionRunSnapshot
    decision: NextDecision
    completed_step_id: str | None


def plan_composition_advance(run_ref: MissionRunRef, agent: str) -> CompositionAdvancePlan:
    """Plan (never persist) the run-state advance after a successful composed
    action: the engine's :func:`apply_result` prelude, then the planner on the
    frozen template. Pure, so the bridge can resolve a planned WP-iteration
    step's workspace BEFORE :func:`advance_run_state_after_composition`
    persists anything (FR-008)."""
    run_dir = Path(run_ref.run_dir)
    applied, completed_step_id = apply_result(_read_snapshot(run_dir), "success")
    decision = plan_next(
        applied,
        _load_frozen_template(run_dir),
        applied.policy_snapshot,
        actor_context={"agent_id": agent},
        live_template_path=_live_template_path(applied),
    )
    return CompositionAdvancePlan(snapshot=applied, decision=decision, completed_step_id=completed_step_id)


def advance_run_state_after_composition(
    *,
    run_ref: MissionRunRef,
    agent: str,
    mission_slug: str,
    mission_type: str,
    repo_root: Path,
    feature_dir: Path,
    timestamp: str,
    progress: dict[str, int | float] | None,
    origin: dict[str, Any],
    sync_emitter: RuntimeEventEmitter,
    plan: CompositionAdvancePlan,
    owned: OwnedCheckout | None = None,
    wp_resolution: tuple[str | None, str | None, str | None, str | None, str] | None = None,
) -> Decision:
    """Advance run state after a successful composed action and return a Decision.

    Adapter-owned reimplementation of the success branch of
    ``spec_kitty_runtime.engine.next_step`` (single-dispatch invariant, FR-001 /
    FR-002 / phase6-composition-stabilization-01KQ2JAS) -- reuses the same
    engine primitives ``runtime_next_step`` uses internally (``apply_result``,
    ``_read_snapshot``, ``_append_event``, ``_load_frozen_template``,
    ``plan_next``, ``_write_snapshot``) plus the same ``RuntimeEventEmitter``,
    without re-entering the legacy DAG dispatch. Returns the same ``Decision``
    shape ``runtime_next_step(...)`` would have produced for the same advance
    (FR-005); only the dispatch path differs.

    Plan first, commit second (FR-008): the caller's ``plan`` (pure) is what
    gets committed, and when it is a WP-iteration step the caller's
    ``wp_resolution`` -- its board action and workspace, the bridge's ONE
    :func:`runtime_bridge._resolve_planned_wp_workspace` -- was resolved BEFORE
    this call, so a resolution failure propagated typed with nothing
    persisted. This function never plans or resolves on its own (a fallback
    here would resolve AFTER the first write -- the wedge): a WP-iteration
    plan handed over without its resolution is refused up front with
    ``ValueError``, nothing persisted.

    The bridge's composition dispatch calls this function directly; a test
    that replaces it patches ``runtime_bridge_engine.advance_run_state_after_composition``.
    """
    from runtime.next import runtime_bridge as _rb  # noqa: PLC0415 — deferred to avoid the circular top-level import

    step_id = plan.decision.step_id
    if wp_resolution is None and plan.decision.kind == "step" and step_id and _rb._is_wp_iteration_step(step_id):
        raise ValueError(
            f"advance_run_state_after_composition: the WP-iteration step {step_id!r} "
            "needs the caller's wp_resolution (resolved before the advance is persisted)"
        )
    run_dir = Path(run_ref.run_dir)
    _seed_emitter(sync_emitter, _read_snapshot(run_dir))

    snapshot = plan.snapshot
    did_complete_step = plan.completed_step_id is not None
    if plan.completed_step_id is not None:
        _emit_step_completed(run_dir, snapshot, plan.completed_step_id, agent, sync_emitter)

    snapshot = _apply_decision_effects(
        run_dir=run_dir,
        snapshot=snapshot,
        decision=plan.decision,
        agent=agent,
        mission_slug=mission_slug,
        repo_root=repo_root,
        feature_dir=feature_dir,
        did_complete_step=did_complete_step,
        sync_emitter=sync_emitter,
        owned=owned,
    )
    _write_snapshot(run_dir, snapshot)

    return _rb._map_runtime_decision(
        plan.decision,
        agent,
        mission_slug,
        mission_type,
        repo_root,
        feature_dir,
        timestamp,
        progress,
        origin,
        owned=owned,
        wp_resolution=wp_resolution,
    )
