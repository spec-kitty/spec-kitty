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

``_advance_run_state_after_composition`` (bridge:1800, CC23) duplicates the
engine's own ``next_step`` success branch to enforce the single-dispatch
invariant (FR-001) for composition-backed actions. Its body is **adapter-owned
logic** (moved here, reduced to CC<=15 via the ``_mark_step_completed`` /
``_apply_decision_effects`` / ``_emit_step_issued`` / ``_emit_decision_required``
/ ``_emit_terminal`` helpers below) — ``runtime_bridge.py`` keeps only a thin
residual compat delegate that forwards to :func:`advance_run_state_after_composition`
so its heavy monkeypatch surface (8x patch + 9x attr, contracts/compat-surface.md)
still intercepts at the delegate.

That function also calls back into five symbols that stay owned by
``runtime_bridge.py`` (``_map_runtime_decision``, ``_resolve_retrospective_policy_for_runtime``,
``_retrospective_blocks_completion``, ``_resolve_mission_id_for_terminus``,
``_run_retrospective_learning_capture`` — none are engine-privates, so none move
in this WP). Those calls are made through a **local, live import of the
``runtime_bridge`` module** (never a module-level import — ``runtime_bridge``
imports this adapter at its own top level, so a top-level back-import here
would be circular) so the WP02 compat guard's per-symbol sentinel patches on
``runtime_bridge.<name>`` are observed exactly as before the extraction.
"""

from __future__ import annotations

from pathlib import Path

from specify_cli.core.owned_mission import effective_root_kwargs
from typing import TYPE_CHECKING, Any

from kernel.clock import now_utc
from runtime.next._internal_runtime import engine as _engine
from runtime.next._internal_runtime import planner as _planner
from runtime.next._internal_runtime.events import (
    DECISION_INPUT_REQUESTED,
    MISSION_RUN_COMPLETED,
    NEXT_STEP_AUTO_COMPLETED,
    NEXT_STEP_ISSUED,
    seed_runtime_emitter,
)
from runtime.next._internal_runtime.schema import DecisionRequest, MissionPolicySnapshot, MissionRunSnapshot, MissionTemplate
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


def resolve_workflow_for_mission(mission_dir: Path) -> WorkflowSequence:
    """Wrap ``_internal_runtime.planner._resolve_workflow_for_mission`` (live
    attribute lookup; FR-013 concentration)."""
    return _planner._resolve_workflow_for_mission(mission_dir)


# ---------------------------------------------------------------------------
# T012 — ``_advance_run_state_after_composition`` body (CC23 -> <=15)
# ---------------------------------------------------------------------------


def _mark_step_completed(
    run_dir: Path,
    snapshot: MissionRunSnapshot,
    agent: str,
    sync_emitter: RuntimeEventEmitter,
) -> tuple[MissionRunSnapshot, bool]:
    """Mark the issued step completed (success path only); emit + persist.

    Returns ``(snapshot, did_complete_step)`` — ``did_complete_step`` tells the
    terminal branch whether a step genuinely just completed (avoids a duplicate
    ``MissionRunCompleted`` emit on re-poll).
    """
    did_complete_step = snapshot.issued_step_id is not None
    if snapshot.issued_step_id is None:
        return snapshot, did_complete_step

    completed_steps = list(snapshot.completed_steps)
    completed_step_id = snapshot.issued_step_id
    if completed_step_id not in completed_steps:
        completed_steps.append(completed_step_id)
    snapshot = snapshot.model_copy(update={"issued_step_id": None, "completed_steps": completed_steps})

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
    return snapshot, did_complete_step


def _live_template_path(snapshot: MissionRunSnapshot) -> Path | None:
    """Resolve the on-disk template path for drift detection, if it still exists."""
    if not snapshot.template_path:
        return None
    candidate = Path(snapshot.template_path)
    return candidate if candidate.exists() else None


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
) -> None:
    """Run the retrospective gate (if configured) and emit ``MissionRunCompleted``.

    Calls back into ``runtime_bridge`` via a local, live module import — these
    five symbols are not engine-privates and stay owned by ``runtime_bridge.py``
    (see module docstring); the local import keeps the WP02 compat guard's
    sentinel patches on ``runtime_bridge.<name>`` observed unchanged.
    """
    from runtime.next import runtime_bridge as _rb  # noqa: PLC0415 — deferred to avoid the circular top-level import (runtime_bridge imports this adapter)

    policy, _source_map, policy_error = _rb._resolve_retrospective_policy_for_runtime(repo_root)
    retrospective_enabled = bool(getattr(policy, "enabled", False))
    # WP18 (#2561): _retrospective_blocks_completion is reached directly from
    # its owning seam now that the runtime_bridge façade re-export was retired
    # (nothing patches ``runtime_bridge._retrospective_blocks_completion``).
    block_on_retrospective = _retrospective._retrospective_blocks_completion(policy)
    mission_id = _rb._resolve_mission_id_for_terminus(feature_dir)

    if retrospective_enabled and block_on_retrospective:
        if policy_error is not None:
            raise policy_error
        _rb._run_retrospective_learning_capture(
            mission_id=mission_id,
            mission_slug=mission_slug,
            feature_dir=feature_dir,
            repo_root=repo_root,
            block_on_failure=True,
        )

    actor = RuntimeActorIdentity(actor_id=agent, actor_type="llm", provider=None, model=None, tool=None)
    payload = MissionRunCompletedPayload(run_id=snapshot.run_id, mission_type=snapshot.mission_key, actor=actor)
    _append_event(run_dir, MISSION_RUN_COMPLETED, payload.model_dump(mode="json"))
    sync_emitter.emit_mission_run_completed(payload)

    if retrospective_enabled and not block_on_retrospective:
        _rb._run_retrospective_learning_capture(
            mission_id=mission_id,
            mission_slug=mission_slug,
            feature_dir=feature_dir,
            repo_root=repo_root,
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
) -> MissionRunSnapshot:
    """Dispatch the 3 ``next_step``-mirroring branches, then fold the result
    (``issued_step_id`` / ``pending_decisions``) back into the snapshot."""
    issued_step_id = snapshot.issued_step_id
    pending_decisions = dict(snapshot.pending_decisions)

    if decision.kind == DecisionKind.step and decision.step_id:
        issued_step_id = decision.step_id
        _emit_step_issued(run_dir, snapshot, decision.step_id, agent, sync_emitter)
    elif decision.kind == DecisionKind.decision_required and decision.decision_id:
        pending_decisions = _emit_decision_required(run_dir, snapshot, decision, decision.decision_id, agent, pending_decisions, sync_emitter)
    elif decision.kind == DecisionKind.terminal and did_complete_step:
        _emit_terminal(run_dir, snapshot, agent, mission_slug, repo_root, feature_dir, sync_emitter)

    return snapshot.model_copy(update={"issued_step_id": issued_step_id, "pending_decisions": pending_decisions})


def _seed_emitter(sync_emitter: RuntimeEventEmitter, snapshot: Any) -> None:
    """Seed optional producer state through the canonical nonfatal seam."""
    seed_runtime_emitter(sync_emitter, snapshot)


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
    effective_root: Path | None = None,
) -> Decision:
    """Advance run state after a successful composed action and return a Decision.

    Adapter-owned reimplementation of the success branch of
    ``spec_kitty_runtime.engine.next_step`` (single-dispatch invariant, FR-001 /
    FR-002 / phase6-composition-stabilization-01KQ2JAS) — reuses the same
    engine primitives ``runtime_next_step`` uses internally (``_read_snapshot``,
    ``_append_event``, ``_load_frozen_template``, ``plan_next``,
    ``_write_snapshot``) plus the same ``RuntimeEventEmitter``, without
    re-entering the legacy DAG dispatch. Returns the same ``Decision`` shape
    ``runtime_next_step(...)`` would have produced for the same advance
    (FR-005); only the dispatch path differs.

    ``runtime_bridge._advance_run_state_after_composition`` is a thin residual
    compat delegate that forwards here (contracts/compat-surface.md).
    """
    from runtime.next import runtime_bridge as _rb  # noqa: PLC0415 — deferred to avoid the circular top-level import

    run_dir = Path(run_ref.run_dir)
    snapshot = _read_snapshot(run_dir)
    _seed_emitter(sync_emitter, snapshot)

    snapshot, did_complete_step = _mark_step_completed(run_dir, snapshot, agent, sync_emitter)

    template = _load_frozen_template(run_dir)
    decision = plan_next(
        snapshot,
        template,
        snapshot.policy_snapshot,
        actor_context={"agent_id": agent},
        live_template_path=_live_template_path(snapshot),
    )

    snapshot = _apply_decision_effects(
        run_dir=run_dir,
        snapshot=snapshot,
        decision=decision,
        agent=agent,
        mission_slug=mission_slug,
        repo_root=repo_root,
        feature_dir=feature_dir,
        did_complete_step=did_complete_step,
        sync_emitter=sync_emitter,
    )
    _write_snapshot(run_dir, snapshot)

    return _rb._map_runtime_decision(
        decision,
        agent,
        mission_slug,
        mission_type,
        repo_root,
        feature_dir,
        timestamp,
        progress,
        origin,
        **effective_root_kwargs(effective_root),
    )
