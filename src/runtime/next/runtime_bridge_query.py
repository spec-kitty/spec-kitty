"""Query (read) and answer (write) entry points of ``spec-kitty next`` (#2560).

Mission ``runtime-bridge-query-seam-01M490EQ`` moved this cluster out of
``runtime_bridge.py`` verbatim:

* ``query_current_state`` — returns the mission's current state without
  advancing the run, with its decision builders
  (``_build_finalized_override_query_decision``,
  ``_build_initial_query_decision``, ``_build_decision_required_query``,
  ``_build_runtime_query_decision``) and helpers
  (``_query_resolve_mission_context``, ``_query_read_runtime_plan``,
  ``_query_dispatch_decision``, ``_is_read_path_error``);
* ``answer_decision_via_runtime`` — the one write entry point: starts a run if
  needed, records the answer to a pending decision through the runtime engine,
  and commits it to the decision log through the decision-log wrapper;
* their exceptions ``QueryModeValidationError`` and ``MissionNotFoundError``.

``query_current_state``, ``answer_decision_via_runtime``,
``QueryModeValidationError`` and ``MissionNotFoundError`` stay importable from
``runtime.next.runtime_bridge`` as the same objects (plain re-exports): the CLI
reads them there. Code in this module calls its collaborators on their owning
modules (``_mapping``, ``_decision_log``, ``_engine_adapter``, ``_io_seam``,
``_cores``) or through the names imported below, so a test that steers the read
path patches the collaborator here or on its owning module, never on the bridge.

Import rule (pinned by ``tests/runtime/test_runtime_bridge_query_seam_layout.py``):
this module never imports ``runtime_bridge``; the bridge imports it.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from kernel.clock import now_utc_iso
from mission_runtime import OwnedCheckout
from runtime.next import runtime_bridge_cores as _cores
from runtime.next import runtime_bridge_decision_log as _decision_log
from runtime.next import runtime_bridge_decision_mapping as _mapping
from runtime.next import runtime_bridge_engine as _engine_adapter
from runtime.next import runtime_bridge_io as _io_seam
from runtime.next._internal_runtime import provide_decision_answer as runtime_provide_decision_answer
from runtime.next._internal_runtime.events import runtime_emitter_for_mission, seed_runtime_emitter
from runtime.next._internal_runtime.schema import ActorIdentity, MissionRuntimeError, load_mission_template_file
from runtime.next.decision import Decision, DecisionKind, _compute_wp_progress
from specify_cli.mission import get_mission_type


# FR-001 / C-IC02: the typed read-path codes whose fidelity MUST be preserved
# across the next-family catch-sites. These are *read-path topology* failures
# (the mission exists but its status read surface is broken / ambiguous), as
# opposed to a genuinely-missing mission (``FEATURE_CONTEXT_UNRESOLVED`` and the
# like), which legitimately stays ``MISSION_NOT_FOUND``. Collapsing a code in
# this set into ``MISSION_NOT_FOUND`` mis-routes the operator (the disease #15).
_READ_PATH_ERROR_CODES: frozenset[str] = frozenset(
    {
        "STATUS_READ_PATH_NOT_FOUND",
        "COORDINATION_BRANCH_DELETED",
        "MISSION_AMBIGUOUS_SELECTOR",
    }
)


def _is_read_path_error(exc: object) -> bool:
    """Return True when *exc* carries a typed read-path topology code (C-IC02)."""
    return getattr(exc, "code", None) in _READ_PATH_ERROR_CODES


class QueryModeValidationError(ValueError):
    """Raised when query mode cannot produce a truthful read-only preview."""


class MissionNotFoundError(Exception):
    """Raised when a mission handle cannot be resolved to an existing mission.

    Carries the attempted handle so callers can include it in structured
    error output (FR-004 / WP03 — fail-closed next query mode), plus an
    actionable ``next_step`` remediation so operators are told concretely how
    to recover (list available missions / verify the handle). The ``next_step``
    affordance restores the operator guidance the superseded
    ``QueryModeValidationError`` used to carry (#1911).
    """

    error_code: str = "MISSION_NOT_FOUND"

    def __init__(self, handle: str, next_step: str | None = None) -> None:
        self.handle = handle
        # #4723: 'spec-kitty mission list' enumerates mission TYPES
        # (software-dev, research, …), never real mission handles — it cannot
        # reveal a colliding pair of missions, and following its own advice
        # would not surface anything actionable. 'spec-kitty doctor topology'
        # enumerates every mission's real handle from kitty-specs/.
        self.next_step = next_step or (f"Run 'spec-kitty doctor topology' to see available missions, then re-run with a valid handle (attempted: '{handle}').")
        super().__init__(f"Mission not found: '{handle}'")


def _build_finalized_override_query_decision(
    *,
    agent: str | None,
    mission_slug: str,
    mission_type: str,
    now: str,
    progress: dict[str, Any] | None,
    emitted_run_id: str | None,
    repo_root: Path,
    finalized_override: str,
    owned: OwnedCheckout | None = None,
) -> Decision:
    override_wp_id: str | None = None
    if finalized_override == "done":
        mission_state = "done"
        preview_step = None
        reason = "All work packages are done"
    elif finalized_override.startswith("blocked:"):
        mission_state = "blocked"
        preview_step = None
        reason = finalized_override.split(":", 1)[1].replace("_", " ")
    else:
        mission_state = finalized_override
        preview_step = finalized_override
        reason = None
        if finalized_override == "implement":
            from mission_runtime import MissionArtifactKind, mission_context_for
            from runtime.next.discovery import preview_claimable_wp

            mission_context = mission_context_for(
                repo_root,
                mission_slug,
                owned=owned,
                tolerate_unmaterialized_coord=True,  # FR-022: a declared-but-not-yet-created coordination worktree is read/materialised, not refused
            )
            preview = preview_claimable_wp(
                mission_context.artifact(MissionArtifactKind.WORK_PACKAGE_TASK).read_dir,
                status_dir=mission_context.artifact(MissionArtifactKind.STATUS_STATE).read_dir,
            )
            override_wp_id = preview.wp_id
            if preview.wp_id is None and preview.selection_reason is not None:
                reason = preview.selection_reason
    return _mapping._materialize_decision(
        _cores.DecisionEnvelope(
            kind=DecisionKind.query,
            agent=agent,
            mission_slug=mission_slug,
            mission=mission_type,
            mission_state=mission_state,
            timestamp=now,
            reason=reason,
            progress=progress,
            run_id=emitted_run_id,
            preview_step=preview_step,
            wp_id=override_wp_id,
        )
    )


def _build_initial_query_decision(
    *,
    runtime_decision: Any,
    agent: str | None,
    mission_slug: str,
    mission_type: str,
    now: str,
    progress: dict[str, Any] | None,
    emitted_run_id: str | None,
) -> Decision:
    return _mapping._materialize_decision(
        _cores.DecisionEnvelope(
            kind=DecisionKind.query,
            agent=agent,
            mission_slug=mission_slug,
            mission=mission_type,
            mission_state="not_started",
            timestamp=now,
            reason=None,
            progress=progress,
            run_id=emitted_run_id,
            preview_step=runtime_decision.step_id,
        )
    )


def _build_decision_required_query(
    *,
    runtime_decision: Any,
    snapshot: Any,
    agent: str | None,
    mission_slug: str,
    mission_type: str,
    now: str,
    progress: dict[str, Any] | None,
    emitted_run_id: str | None,
) -> Decision:
    return _mapping._materialize_decision(
        _cores.DecisionEnvelope(
            kind=DecisionKind.query,
            agent=agent,
            mission_slug=mission_slug,
            mission=mission_type,
            mission_state=snapshot.issued_step_id or runtime_decision.step_id or "unknown",
            timestamp=now,
            reason=None,
            progress=progress,
            run_id=emitted_run_id,
            step_id=snapshot.issued_step_id or runtime_decision.step_id,
            decision_id=runtime_decision.decision_id,
            input_key=runtime_decision.input_key,
            question=runtime_decision.question,
            options=runtime_decision.options,
        )
    )


def _build_runtime_query_decision(
    *,
    runtime_decision: Any,
    snapshot: Any,
    agent: str | None,
    mission_slug: str,
    mission_type: str,
    now: str,
    progress: dict[str, Any] | None,
    emitted_run_id: str | None,
) -> Decision:
    mission_state = runtime_decision.step_id or "unknown"
    blocked_reason: str | None = None
    if runtime_decision.kind == DecisionKind.terminal:
        mission_state = "done"
    elif runtime_decision.kind == DecisionKind.blocked:
        mission_state = snapshot.issued_step_id or runtime_decision.step_id or "blocked"
        blocked_reason = snapshot.blocked_reason or getattr(runtime_decision, "reason", None)
    return _mapping._materialize_decision(
        _cores.DecisionEnvelope(
            kind=DecisionKind.query,
            agent=agent,
            mission_slug=mission_slug,
            mission=mission_type,
            mission_state=mission_state,
            timestamp=now,
            reason=blocked_reason,
            progress=progress,
            run_id=emitted_run_id,
            step_id=snapshot.issued_step_id or runtime_decision.step_id,
        )
    )


def query_current_state(
    agent: str | None,
    mission_slug: str,
    repo_root: Path,
    *,
    owned: OwnedCheckout | None = None,
) -> Decision:
    """Return current mission state without advancing the DAG.

    Reads the run snapshot idempotently. Does NOT call next_step().
    Returns a Decision with kind=DecisionKind.query and is_query=True.

    Committed-authority pre-check (#2947, D13): before any workspace
    selection (``mission_context_for`` below), a merged mission
    (``mission_terminal_verdict`` is ``terminal``) short-circuits to
    ``kind: query`` / ``mission_state: "done"`` — query mode's structural
    ``kind: query`` contract (never ``kind: terminal`` here); a
    ``blocked_conflict`` verdict short-circuits to ``kind: blocked``. A
    ``"none"`` verdict falls through unchanged (F5), so
    ``_finalized_task_board_override_step`` (D9) never runs for a merged
    mission.

    Args:
        agent: Agent name (for Decision construction only).
        mission_slug: Mission slug (e.g. '069-planning-pipeline-integrity').
        repo_root: Repository root path.
    """
    now = now_utc_iso()
    merged_short_circuit = _mapping._merged_mission_short_circuit(
        repo_root=repo_root,
        mission_slug=mission_slug,
        agent=agent,
        now=now,
        terminal_kind=DecisionKind.query,
        owned=owned,
    )
    if merged_short_circuit is not None:
        return merged_short_circuit

    mission_context = _query_resolve_mission_context(repo_root, mission_slug, owned=owned)
    mission_slug = mission_context.mission_slug

    from mission_runtime import MissionArtifactKind

    task_board = mission_context.artifact(MissionArtifactKind.WORK_PACKAGE_TASK)
    status_state = mission_context.artifact(MissionArtifactKind.STATUS_STATE)

    if not task_board.read_dir.is_dir():
        # Conscious decision (C-IC02): reaching here means the resolver RESOLVED
        # a directory and verified it ``exists()`` (see resolution.py), yet it is
        # not a directory on disk — i.e. the canonical mission dir name resolved
        # to a regular file. That is a genuinely malformed / missing mission, not
        # a read-path topology miss, so ``MISSION_NOT_FOUND`` is the correct,
        # deliberately-kept classification here (NOT a read-path collapse).
        raise MissionNotFoundError(mission_slug)

    mission_type = mission_context.mission_type
    task_error = _mapping._wp_task_surface_error(task_board.read_dir, status_state.read_dir, mission_slug)
    if task_error is not None:
        # Query remains a read-only query decision, but an inconsistent task
        # surface cannot produce truthful file-derived progress. Match the
        # advancing board's fail-closed recovery without emitting partial totals.
        return _mapping._materialize_decision(
            _cores.DecisionEnvelope(
                kind=DecisionKind.query,
                agent=agent,
                mission_slug=mission_slug,
                mission=mission_type,
                mission_state="blocked",
                timestamp=now,
                reason=task_error,
            )
        )

    progress = _compute_wp_progress(task_board.read_dir, status_dir=status_state.read_dir)

    # Root discipline: the run store (and the template/policy reads that start
    # an ephemeral preview run) live at P for an owned mission.
    config_root = owned.owned_root if owned is not None else repo_root
    run_ref = _io_seam._existing_run_ref(mission_slug, config_root, mission_type, owned=owned)
    ephemeral_run_store: Path | None = None

    # Read current step WITHOUT calling next_step(). When no step has been
    # issued yet, use the planner read-only to compute a truthful preview.
    # The try/finally below guarantees the ephemeral run store is cleaned up
    # on every return path (success, raise, or early exit).
    try:
        run_ref, ephemeral_run_store, snapshot, runtime_decision = _query_read_runtime_plan(
            run_ref,
            mission_slug,
            mission_type,
            config_root,
        )

        # Query mode never persists the ephemeral run it bootstraps for a
        # not-yet-started mission. Returning that run's id in the JSON would
        # mislead callers into thinking they can issue ``spec-kitty next
        # --mission <slug> --result …`` against it; in reality the run state
        # is wiped in the finally block before the function returns. Only
        # emit ``run_id`` when the run is a real, persisted one.
        emitted_run_id: str | None = None
        if ephemeral_run_store is None:
            emitted_run_id = getattr(run_ref, "run_id", None)

        return _query_dispatch_decision(
            task_board=task_board,
            status_state=status_state,
            progress=progress,
            snapshot=snapshot,
            runtime_decision=runtime_decision,
            agent=agent,
            mission_slug=mission_slug,
            mission_type=mission_type,
            now=now,
            repo_root=repo_root,
            owned=owned,
            emitted_run_id=emitted_run_id,
        )
    finally:
        if ephemeral_run_store is not None:
            shutil.rmtree(ephemeral_run_store, ignore_errors=True)


def _query_resolve_mission_context(
    repo_root: Path,
    mission_slug: str,
    *,
    owned: OwnedCheckout | None = None,
) -> Any:
    """Campsite extraction (T058) of ``query_current_state``'s mission-context
    resolution: the try/except ``ActionContextError`` -> read-path
    pass-through / ``MissionNotFoundError`` mapping. Behaviour-preserving —
    no change to the exception shapes this raises."""
    from mission_runtime import ActionContextError, mission_context_for

    try:
        return mission_context_for(
            repo_root,
            mission_slug,
            owned=owned,
            tolerate_unmaterialized_coord=True,  # FR-022: a fresh coordination mission is queryable before its worktree exists
        )
    except ActionContextError as exc:
        # FR-001 / C-IC02: pass a typed *read-path* error through VERBATIM. The
        # resolver already produced the precise code (e.g.
        # COORDINATION_BRANCH_DELETED / STATUS_READ_PATH_NOT_FOUND) plus the real
        # read-path remediation; collapsing it into a generic MISSION_NOT_FOUND
        # ("run mission list") points the operator the wrong way (the mission is
        # not missing — its read path is broken; the disease #15). The command
        # layer surfaces ``exc.code`` + checked paths from the typed error.
        if _is_read_path_error(exc):
            raise
        # A genuinely-missing mission (e.g. FEATURE_CONTEXT_UNRESOLVED — no mission
        # directory at all) is legitimately MISSION_NOT_FOUND (FR-004 / WP03).
        raise MissionNotFoundError(mission_slug) from exc


def _query_read_runtime_plan(
    run_ref: Any,
    mission_slug: str,
    mission_type: str,
    repo_root: Path,
) -> tuple[Any, Path | None, Any, Any]:
    """Campsite extraction (T058) of ``query_current_state``'s nested
    ephemeral-run-and-planner try/except. Returns
    ``(run_ref, ephemeral_run_store, snapshot, runtime_decision)``.
    Behaviour-preserving."""
    ephemeral_run_store: Path | None = None
    try:
        if run_ref is None:
            run_ref, ephemeral_run_store = _io_seam._start_ephemeral_query_run(
                mission_slug,
                mission_type,
                repo_root,
            )
            snapshot = _engine_adapter._read_snapshot(Path(run_ref.run_dir))
            template_path = Path(run_ref.run_dir) / "mission_template_frozen.yaml"
            template = load_mission_template_file(template_path)
        else:
            snapshot = _engine_adapter._read_snapshot(Path(run_ref.run_dir))
            template_path = Path(snapshot.template_path)
            template = load_mission_template_file(template_path)
        runtime_decision = _engine_adapter.plan_next(
            snapshot,
            template,
            snapshot.policy_snapshot,
            live_template_path=template_path,
        )
    except QueryModeValidationError:
        raise
    except Exception as exc:
        raise QueryModeValidationError(f"Could not read query state for mission '{mission_slug}': {exc}") from exc
    return run_ref, ephemeral_run_store, snapshot, runtime_decision


def _query_dispatch_decision(
    *,
    task_board: Any,
    status_state: Any,
    progress: dict[str, Any] | None,
    snapshot: Any,
    runtime_decision: Any,
    agent: str | None,
    mission_slug: str,
    mission_type: str,
    now: str,
    repo_root: Path,
    owned: OwnedCheckout | None,
    emitted_run_id: str | None,
) -> Decision:
    """Campsite extraction (T058) of ``query_current_state``'s
    finalized-override / initial / decision-required / runtime branch
    ladder. Behaviour-preserving."""
    finalized_override = _mapping._finalized_task_board_override_step(
        task_board.read_dir,
        progress,
        status_dir=status_state.read_dir,
    )
    if finalized_override is not None:
        return _build_finalized_override_query_decision(
            agent=agent,
            mission_slug=mission_slug,
            mission_type=mission_type,
            now=now,
            progress=progress,
            emitted_run_id=emitted_run_id,
            repo_root=repo_root,
            finalized_override=finalized_override,
            owned=owned,
        )

    if not snapshot.completed_steps and not snapshot.pending_decisions and not snapshot.decisions:
        if runtime_decision.kind in {DecisionKind.step, DecisionKind.decision_required} and runtime_decision.step_id:
            return _build_initial_query_decision(
                runtime_decision=runtime_decision,
                agent=agent,
                mission_slug=mission_slug,
                mission_type=mission_type,
                now=now,
                progress=progress,
                emitted_run_id=emitted_run_id,
            )
        raise QueryModeValidationError(f"Mission '{mission_type}' has no issuable first step for run '{mission_slug}'")

    if runtime_decision.kind == DecisionKind.decision_required:
        return _build_decision_required_query(
            runtime_decision=runtime_decision,
            snapshot=snapshot,
            agent=agent,
            mission_slug=mission_slug,
            mission_type=mission_type,
            now=now,
            progress=progress,
            emitted_run_id=emitted_run_id,
        )

    return _build_runtime_query_decision(
        runtime_decision=runtime_decision,
        snapshot=snapshot,
        agent=agent,
        mission_slug=mission_slug,
        mission_type=mission_type,
        now=now,
        progress=progress,
        emitted_run_id=emitted_run_id,
    )


def answer_decision_via_runtime(
    mission_slug: str,
    decision_id: str,
    answer: str,
    agent: str,
    repo_root: Path,
    *,
    actor_type: str = "human",
    owned: OwnedCheckout | None = None,
) -> None:
    """Answer a pending decision.

    CLI answers are human-authored by default even though the command still
    carries an ``--agent`` identity for the surrounding mission loop.
    """
    import logging

    logger = logging.getLogger(__name__)

    from mission_runtime import ActionContextError, resolve_action_context

    try:
        _ctx = resolve_action_context(
            repo_root,
            action="tasks",
            feature=mission_slug,
            owned=owned,
        )
        feature_dir = Path(_ctx.feature_dir)
    except ActionContextError as exc:
        # FR-001 / C-IC02: preserve the typed read-path error IDENTICALLY on the
        # decision-answer path (the same fidelity obligation as the query path).
        # Collapsing it into a generic "not found" MissionRuntimeError would drop
        # ``exc.code`` (e.g. COORDINATION_BRANCH_DELETED) and the read-path
        # remediation, mis-routing the operator. Log the context, then re-raise
        # the typed ActionContextError so the command layer surfaces its code.
        logger.warning(
            "answer_decision_via_runtime: read-path error (%s) for mission %r in repo %s — cannot answer decision %r",
            exc.code,
            mission_slug,
            repo_root,
            decision_id,
        )
        raise
    if not feature_dir.is_dir():
        logger.warning(
            "answer_decision_via_runtime: mission %r resolved to missing dir %s — cannot answer decision %r",
            mission_slug,
            feature_dir,
            decision_id,
        )
        raise MissionRuntimeError(f"Mission {mission_slug!r} not found; cannot answer decision {decision_id!r}")
    mission_type = get_mission_type(feature_dir)
    config_root = owned.owned_root if owned is not None else repo_root
    run_ref = _io_seam.get_or_start_run(mission_slug, config_root, mission_type, owned=owned)
    # E3 (#3929): same bridge-entry registration as the decide path.
    from specify_cli.status import ensure_runtime_moment_producer  # noqa: PLC0415

    ensure_runtime_moment_producer()
    sync_emitter = runtime_emitter_for_mission(
        feature_dir=feature_dir,
        mission_slug=mission_slug,
        mission_type=mission_type,
    )
    try:
        snapshot = _engine_adapter._read_snapshot(Path(run_ref.run_dir))
    except Exception as exc:
        logger.warning(
            "answer_decision_via_runtime: failed to seed emitter from snapshot for run %r: %s",
            run_ref.run_dir,
            exc,
        )
    else:
        seed_runtime_emitter(sync_emitter, snapshot)
    # Wrap with DecisionGitLog so the answered decision is committed to the
    # coordination branch (spec-kitty #1546, FR-001–FR-005).
    answer_emitter: Any = _decision_log._wrap_with_decision_git_log(sync_emitter, mission_slug, repo_root, owned=owned)
    actor = ActorIdentity(actor_id=agent, actor_type=actor_type, provider=None, model=None, tool=None)
    runtime_provide_decision_answer(
        run_ref,
        decision_id,
        answer,
        actor,
        emitter=answer_emitter,
    )
