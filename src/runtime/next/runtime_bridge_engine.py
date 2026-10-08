"""Engine-adapter seam for ``runtime.next.runtime_bridge`` (FR-013, #2531 WP03).

**Sole home of the ``_internal_runtime`` engine/planner private surface.** No
other module under ``src/runtime/next/`` may import or attribute-access the
``_internal_runtime.engine`` / ``.planner`` submodules -- enforced by the
architecture guard in ``tests/runtime/test_bridge_engine.py``. The adapter
wraps the reads and the planning the bridge and its seams need
(``_read_snapshot``, ``_load_frozen_template``, ``plan_next``,
``resolve_workflow_for_mission`` for ``prompt_builder.py``, ``plan_advance``)
and the engine's one commit path (``commit_advance``). It writes no run event
and no snapshot of its own: the run-event journal and ``state.json`` are
written only by the engine's commit (#2562).

Each wrapper below re-exposes the identical private name it wraps and delegates
via a **live module-attribute lookup** (``_engine.<name>(...)`` /
``_planner.<name>(...)``), never a cached ``from ... import name`` binding. This
preserves the exact behavior the WP01 parity oracle depends on: the oracle
patches ``_internal_runtime.engine._append_event`` / ``._write_snapshot`` /
``._read_snapshot`` directly on the source module
(``tests/runtime/_bridge_oracle.py::capture_side_effects``), and a live
attribute lookup observes that patch regardless of which module performs the
call — a snapshotted ``from module import name`` would not.

``advance_run_state_after_composition`` commits the engine's own advance
plan for composition-backed actions (#2562): the bridge plans with
:func:`plan_advance`, the engine's single planning authority, and this
adapter commits that plan through :func:`commit_advance`, so a
composition-backed advance records exactly what ``next_step`` records (RACI
bindings, the audit significance evaluation, LOW auto-proceed). The adapter
no longer duplicates ``next_step``: it owns only the composition-specific
edges -- the FR-008 refusal of a WP-iteration plan without its workspace
resolution, emitter seeding, and the retrospective gate around
``MissionRunCompleted``. The bridge calls
``_engine_adapter.advance_run_state_after_composition`` directly and holds no
forwarding delegate, so a test that replaces it patches
``runtime_bridge_engine.advance_run_state_after_composition``.

That function maps its result through ``runtime_bridge_decision_mapping``
(``_is_wp_iteration_step`` and ``_map_runtime_decision``), imported at the top
level: the mapping module sits below both the bridge and this adapter, so the
deferred ``runtime_bridge`` back-import this adapter used before is gone
(#2560). A test that steers the mapping patches it on that module. The
retrospective names it needs are owned by ``runtime_bridge_retrospective`` and
are called there directly, so a test that intercepts one patches it on that
module.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import yaml

from mission_runtime import OwnedCheckout
from runtime.next._internal_runtime import engine as _engine
from runtime.next._internal_runtime import planner as _planner
from runtime.next._internal_runtime.events import seed_runtime_emitter
from runtime.next._internal_runtime.schema import MissionPolicySnapshot, MissionRunSnapshot, MissionRuntimeError, MissionTemplate
from runtime.next import runtime_bridge_decision_mapping as _mapping
from runtime.next import runtime_bridge_retrospective as _retrospective

if TYPE_CHECKING:
    from collections.abc import Callable

    from runtime.next._internal_runtime import MissionRunRef, NextDecision
    from runtime.next._internal_runtime.engine import AdvancePlan, ResultType
    from runtime.next._internal_runtime.workflow_schema import WorkflowSequence
    from runtime.next.decision import Decision
    from runtime.next._internal_runtime.events import RuntimeEventEmitter

# ---------------------------------------------------------------------------
# T011 — engine/planner private-access wrappers (reads and planning)
# ---------------------------------------------------------------------------


def _read_snapshot(run_dir: Path) -> MissionRunSnapshot:
    """Wrap ``_internal_runtime.engine._read_snapshot`` (live attribute lookup)."""
    return _engine._read_snapshot(run_dir)


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


def commit_advance(
    run_ref: MissionRunRef,
    plan: AdvancePlan,
    agent_id: str,
    emitter: RuntimeEventEmitter | None = None,
    *,
    before_run_completed: Callable[[], None] | None = None,
) -> NextDecision:
    """Wrap ``_internal_runtime.engine.commit_advance`` (live attribute lookup):
    commit a plan the caller already computed (no second planning). Raises
    :class:`StaleAdvancePlan` -- writing nothing -- when the run moved on.
    ``before_run_completed`` is the engine's abort-only guard on the
    transition into terminal (called before ``MissionRunCompleted``)."""
    return _engine.commit_advance(run_ref, plan, agent_id, emitter, before_run_completed=before_run_completed)


def resolve_workflow_for_mission(mission_dir: Path) -> WorkflowSequence:
    """Wrap ``_internal_runtime.planner._resolve_workflow_for_mission`` (live
    attribute lookup; FR-013 concentration)."""
    return _planner._resolve_workflow_for_mission(mission_dir)


# ---------------------------------------------------------------------------
# ``advance_run_state_after_composition`` -- commit the engine's plan
# ---------------------------------------------------------------------------


def _seed_emitter(sync_emitter: RuntimeEventEmitter, snapshot: Any) -> None:
    """Seed optional producer state through the canonical nonfatal seam."""
    seed_runtime_emitter(sync_emitter, snapshot)


class TerminalRetrospective:
    """The retrospective gate around ``MissionRunCompleted``, shared by the legacy
    ``next_step`` / ``commit_advance`` paths and the composition path.

    The policy is resolved lazily, on the first terminal call, so a
    non-terminal advance never reads it. :meth:`before_run_completed` is the
    engine's abort-only guard, called only on the transition into terminal:
    under a blocking policy it runs the policy error, if any, else the blocking
    capture, and maps any failure to the one typed
    :class:`RetrospectiveGateRefused`. The engine then aborts the commit before
    anything is written: no event, no emission, no ``state.json``.
    :meth:`after_run_completed` runs the non-blocking capture once the commit
    has returned, and only when the guard was reached, so a re-poll of an
    already-terminal run captures nothing.

    owned-checkout-lifecycle-authority WP11 (FR-009): retrospective policy is
    a P-local governance read for an owned mission, so ``config_root`` is the
    owned root when there is one.
    """

    def __init__(self, *, config_root: Path, mission_slug: str, feature_dir: Path) -> None:
        self._config_root = config_root
        self._mission_slug = mission_slug
        self._feature_dir = feature_dir
        self._resolved: tuple[bool, bool, Exception | None, str] | None = None
        self._reached_terminal = False

    def _resolve(self) -> tuple[bool, bool, Exception | None, str]:
        if self._resolved is None:
            policy, _source_map, policy_error = _retrospective._resolve_retrospective_policy_for_runtime(self._config_root)
            self._resolved = (
                bool(getattr(policy, "enabled", False)),
                _retrospective._retrospective_blocks_completion(policy),
                policy_error,
                _retrospective._resolve_mission_id_for_terminus(self._feature_dir),
            )
        return self._resolved

    def _capture(self, mission_id: str, *, block_on_failure: bool) -> None:
        _retrospective._run_retrospective_learning_capture(
            mission_id=mission_id,
            mission_slug=self._mission_slug,
            feature_dir=self._feature_dir,
            repo_root=self._config_root,
            block_on_failure=block_on_failure,
        )

    def before_run_completed(self) -> None:
        self._reached_terminal = True
        try:
            enabled, blocking, policy_error, mission_id = self._resolve()
            if enabled and blocking:
                if policy_error is not None:
                    raise policy_error
                self._capture(mission_id, block_on_failure=True)
        except Exception as exc:
            raise _retrospective.RetrospectiveGateRefused(exc) from exc

    def after_run_completed(self) -> None:
        if not self._reached_terminal:
            return
        enabled, blocking, _policy_error, mission_id = self._resolve()
        if enabled and not blocking:
            self._capture(mission_id, block_on_failure=False)


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
    plan: AdvancePlan,
    owned: OwnedCheckout | None = None,
    wp_resolution: tuple[str | None, str | None, str | None, str | None, str] | None = None,
) -> Decision:
    """Commit the engine's advance plan after a successful composed action and return a Decision.

    The bridge planned with :func:`plan_advance` -- the engine's one planning
    authority, so a composition-backed advance records the same RACI
    bindings, significance evaluation and LOW auto-proceed as ``next_step``
    (#2562) -- and this function commits that plan through
    :func:`commit_advance` without re-entering the legacy DAG dispatch
    (single-dispatch invariant, FR-001). It owns only the composition edges:

    * Plan first, commit second (FR-008): a WP-iteration plan handed over
      without the caller's ``wp_resolution`` -- the bridge's ONE
      :func:`runtime_bridge._resolve_planned_wp_workspace`, resolved before
      this call -- is refused up front with ``ValueError``, nothing persisted.
      This function never plans or resolves on its own.
    * The emitter is seeded from the persisted run before the first emit.
    * The retrospective gate around ``MissionRunCompleted``
      (:class:`TerminalRetrospective`): the blocking capture is the engine's
      ``before_run_completed`` guard, the non-blocking capture runs after the
      commit returned.

    A plan the run moved past raises :class:`StaleAdvancePlan` from the
    commit, writing nothing; it is not caught here (the bridge turns it into
    the EDGE-003 blocked Decision). Returns the same ``Decision`` shape
    ``runtime_next_step(...)`` would have produced for the same advance
    (FR-005). The bridge's composition dispatch calls this function directly;
    a test that replaces it patches
    ``runtime_bridge_engine.advance_run_state_after_composition``.
    """
    step_id = plan.decision.step_id
    if wp_resolution is None and plan.decision.kind == "step" and step_id and _mapping._is_wp_iteration_step(step_id):
        raise ValueError(
            f"advance_run_state_after_composition: the WP-iteration step {step_id!r} "
            "needs the caller's wp_resolution (resolved before the advance is persisted)"
        )
    _seed_emitter(sync_emitter, _read_snapshot(Path(run_ref.run_dir)))

    retrospective = TerminalRetrospective(
        config_root=owned.owned_root if owned is not None else repo_root,
        mission_slug=mission_slug,
        feature_dir=feature_dir,
    )
    commit_advance(run_ref, plan, agent, sync_emitter, before_run_completed=retrospective.before_run_completed)
    retrospective.after_run_completed()

    return _mapping._map_runtime_decision(
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
