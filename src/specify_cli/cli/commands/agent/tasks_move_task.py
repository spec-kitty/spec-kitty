"""The ``move-task`` command family, relocated out of ``tasks.py`` (WP05, #2305).

Mission ``tasks-py-degod-wave2-01KWH9EQ`` FR-001/FR-002: the LARGEST family —
``_do_move_task`` + the 23 ``_mt_*`` phase helpers + ``_MoveTaskState`` +
``_default_move_task_ports`` — lives here, moved VERBATIM from ``tasks.py``.
The ``@app.command`` Typer wrapper (``move_task``) stays in ``tasks.py`` and
delegates to :func:`_do_move_task` (the byte-frozen ``--help`` surface is the
registration shim's).

**Orchestration shape** (unchanged): the Typer command declares the CLI
surface; ``_do_move_task`` gathers facts (I/O), runs the pure
``decide_transition`` core (``tasks_transition_core``), and executes the
resulting ``Emit`` through the two coord WRITE capabilities
(``commit_status`` for each lane hop, ``commit_artifact`` for the primary
WP-file commit) and the coord READ authority (``feature_write_dir`` resolves
the FR-010 coord husk — NEVER a primary kind). The
partial-write-on-refusal timing (override/arbiter persists at their OLD guard
positions) and the coord skip-exit-0 arm are preserved verbatim.

**C-001 divergence wiring**: ``move_task`` is the ONLY command with the
``_skip_target_branch_commit`` pre-gate (skip-exit-0 on coord topology +
protected branch). The pre-gate call sits at its original position in
``_mt_resolve_targets`` — before the protected-branch refusal and the
authoritative event-log read — reaching the shared helper via
``_tasks._skip_target_branch_commit``; the coord harness T004 (skip arm +
wrong-leg detector) pins it.

**Seam bridge** (research.md D1/D7): the relocated bodies reach every patched
seam symbol through a lazy in-function import of the ``tasks`` module
(``from specify_cli.cli.commands.agent import tasks as _tasks``) and call
``_tasks.<attr>(...)``, so every historical ``@patch("...agent.tasks.<sym>")``
/ ``monkeypatch.setattr(tasks, ...)`` keeps INTERCEPTING after the move.
``tasks.py`` re-imports the family in the explicit ``as`` re-export form, so
``tasks.<name>`` stays a module attribute. Symbols with ZERO patch sites and a
canonical home outside ``tasks.py`` are imported directly at module scope
(cycle-safe: none of those modules import ``tasks``).

Per-symbol routing/interception evidence:
``kitty-specs/tasks-py-degod-wave2-01KWH9EQ/seam-checklist.md`` (Layer 4 of
the parity contract).

**Verdict-persistence seam extraction** (WP06, mission
``review-cycle-verdict-seam-rebuild-01KZ2W7W``, C-003 ruling
``DM-01KZ3VBAWZ1B5XC25EDGN99BJP``): four verdict-relevant bodies now live in
``tasks_verdict_persistence.py`` instead of here — the inline verdict
resolver formerly inside ``_mt_gather_review_facts``, the OLD-timing
review-artifact override persist formerly the body of
``_mt_fire_override_persist``, the ``_persist_approved_review_cycle``
closure + adjacent rollback block formerly inside ``_mt_finalize_plan``, and
the arbiter-decision persist try/except formerly inside
``_run_arbiter_override``. ``_mt_gather_review_facts``,
``_mt_fire_override_persist`` and ``_run_arbiter_override`` themselves STAY
here (frozen ``tasks.<name>`` compat symbols pinned by name in
``test_tasks_compat_surface.py``) and now call into the new module for the
extracted substance — see ``tasks_verdict_persistence.py``'s own module
docstring for the per-site detail and the C-003 grounds.

**Transition-gate seam extraction** (#5629): the pre-review / transition-gate
family (phase C.5 — gate binding, scope and baseline resolution, dispatch,
verdict translation, byproduct enrolment) lives in
``tasks_move_task_gates.py``, moved VERBATIM. Every symbol is re-imported here
in the ``as`` re-export form, so ``tasks_move_task.<name>`` and ``tasks.<name>``
still resolve; ``_do_move_task`` still calls ``_mt_run_pre_review_gate`` through
this module, so a patch on that name keeps intercepting.
"""

from __future__ import annotations

import fnmatch
import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from kernel.clock import format_stamp, now_utc
from kernel.git import GitCommandError, GitPath, StatusEntry, status_entries
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer

if TYPE_CHECKING:
    from specify_cli.workspace.context import ResolvedWorkspace

from mission_runtime import ActionContextError, MissionArtifactKind, OwnedRefusalCode, placement_seam
from specify_cli.agent_tasks_ports import (
    MissionHandle,
    TasksPorts,
)
from specify_cli.cli.commands.agent.tasks_finalize_validation import (
    _read_transactional_wp_lane,
)
from specify_cli.cli.commands.agent.tasks_parsing_validation import (
    _issue_matrix_approval_blocker,
    _self_review_fallback_option_error,
)
from specify_cli.cli.commands.agent.tasks_transition_core import (
    Emit,
    MoveTaskRequest,
    RefuseExit1,
    TransitionPlan,
    _effective_note_text,
    arbiter_persist_signal,
    is_review_rejection_edge,
)
from specify_cli.cli.commands.agent.tasks_verdict_persistence import (
    VerdictDurabilitySignal,
    VerdictPersistenceFailure,
    VerdictRevertCompoundFailure,
    persist_arbiter_override_decision,
    persist_review_override_before_guard,
    resolve_review_verdict_facts,
    revert_committed_verdict_write,
)
from specify_cli.cli.console import err_console
from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.core.paths import assert_safe_path_segment, is_worktree_context
from mission_runtime import OwnedCheckout
from specify_cli.core.owned_mission import require_unstaged_index
from specify_cli.core.vcs.git import git_merge_base, merge_base_changed_files_checked
from specify_cli.mission_metadata import resolve_mission_identity
from specify_cli.review.cycle import (
    synthetic_auto_approval_ref,
)
from specify_cli.status import (
    EVENTS_FILENAME,
    EventPersistenceError,
    Lane,
    ReviewResult,
    ResolvedBinding,
    StatusEvent,
    TransitionError,
    WPInnerStateDelta,
    actor_identity_str,
    read_authored_wp_frontmatter,
    resolve_lane_alias,
)
from specify_cli.status import latest_implementer_actor
from specify_cli.task_utils import (
    WorkPackage,
    ensure_lane,
)
from specify_cli.upgrade.pre30_guard import Pre30LayoutError, check_pre30_layout

from specify_cli.cli.commands.agent.tasks_move_task_hops import (
    _binding_role_for_lane as _binding_role_for_lane,
    _mt_hop_review_ref as _mt_hop_review_ref,
    _mt_hop_reason_source as _mt_hop_reason_source,
    _mt_hop_policy_metadata as _mt_hop_policy_metadata,
    _mt_approval_policy_metadata as _mt_approval_policy_metadata,
    _mt_hop_actor as _mt_hop_actor,
    _mt_hop_review_result as _mt_hop_review_result,
    _mt_plan_review_result as _mt_plan_review_result,
    _mt_reassignment_binding_fields as _mt_reassignment_binding_fields,
    _build_claim_review_override as _build_claim_review_override,
    _mt_shell_pid_baseline as _mt_shell_pid_baseline,
)
from specify_cli.cli.commands.agent.tasks_move_task_executor import (
    _mt_finalize_plan as _mt_finalize_plan,
    _mt_persist_rejection_cycle as _mt_persist_rejection_cycle,
    _mt_emit_transitions as _mt_emit_transitions,
    _mt_emit_runtime_state as _mt_emit_runtime_state,
    _mt_warn_unstamped_approval as _mt_warn_unstamped_approval,
    _mt_persist_wp_file as _mt_persist_wp_file,
    _mt_release_review_lock as _mt_release_review_lock,
    _mt_execute as _mt_execute,
    _RollbackResetSummary as _RollbackResetSummary,
    _mt_build_rollback_summary as _mt_build_rollback_summary,
    _mt_rollback_subtasks_reset as _mt_rollback_subtasks_reset,
)

from specify_cli.cli.commands.agent.tasks_move_task_gates import (
    _PRE_REVIEW_CONFIG_KEY_BLOCK as _PRE_REVIEW_CONFIG_KEY_BLOCK,
    _PRE_REVIEW_CONFIG_KEY_TEST_COMMAND as _PRE_REVIEW_CONFIG_KEY_TEST_COMMAND,
    _PRE_REVIEW_CONFIG_KEY_TEST_COMMAND_REPLACEMENT as _PRE_REVIEW_CONFIG_KEY_TEST_COMMAND_REPLACEMENT,
    _PRE_REVIEW_FRONTMATTER_KEY as _PRE_REVIEW_FRONTMATTER_KEY,
    _PRE_REVIEW_TEST_COMMAND_DEPRECATION as _PRE_REVIEW_TEST_COMMAND_DEPRECATION,
    _pre_review_gate_filter_groups as _pre_review_gate_filter_groups,
    _pre_review_gate_composite_routing as _pre_review_gate_composite_routing,
    _mt_review_config_section as _mt_review_config_section,
    _mt_pre_review_block_enabled as _mt_pre_review_block_enabled,
    _mt_pre_review_gate_declared as _mt_pre_review_gate_declared,
    _mt_pre_review_gate_env_disable_reason as _mt_pre_review_gate_env_disable_reason,
    _mt_pre_review_gate_skip_reason as _mt_pre_review_gate_skip_reason,
    _mt_pre_review_scope_override as _mt_pre_review_scope_override,
    _mt_resolve_pre_review_workspace as _mt_resolve_pre_review_workspace,
    _mt_pre_review_changed_files as _mt_pre_review_changed_files,
    _mt_pre_review_dirty_paths as _mt_pre_review_dirty_paths,
    _mt_pre_review_gate_with_override_scope as _mt_pre_review_gate_with_override_scope,
    _mt_empty_scope_verdict as _mt_empty_scope_verdict,
    _PRE_REVIEW_GATE_NOT_DECLARED_REASON as _PRE_REVIEW_GATE_NOT_DECLARED_REASON,
    _mt_not_declared_skip_verdict as _mt_not_declared_skip_verdict,
    _mt_cancelled_verdict as _mt_cancelled_verdict,
    _mt_pre_review_gate_metadata as _mt_pre_review_gate_metadata,
    _PRE_REVIEW_BLOCK_UNENFORCEABLE_HINT as _PRE_REVIEW_BLOCK_UNENFORCEABLE_HINT,
    _mt_pre_review_gate_console_warning as _mt_pre_review_gate_console_warning,
    _mt_pre_review_gate_block_message as _mt_pre_review_gate_block_message,
    _TransitionGateInputs as _TransitionGateInputs,
    _TransitionGateEffect as _TransitionGateEffect,
    _mt_warn_pre_review_test_command_deprecated as _mt_warn_pre_review_test_command_deprecated,
    _mt_resolve_scope_source as _mt_resolve_scope_source,
    _mt_resolve_active_gate_bindings as _mt_resolve_active_gate_bindings,
    _mt_resolve_gate_baseline as _mt_resolve_gate_baseline,
    _mt_build_transition_gate_context as _mt_build_transition_gate_context,
    _mt_fail_open_gate as _mt_fail_open_gate,
    _mt_dispatch_one_gate as _mt_dispatch_one_gate,
    _mt_dispatch_transition_gates as _mt_dispatch_transition_gates,
    _PRE_REVIEW_GATE_RUNNING_NOTICE as _PRE_REVIEW_GATE_RUNNING_NOTICE,
    _mt_human_gate_status_observer as _mt_human_gate_status_observer,
    _mt_collect_transition_gate_verdicts as _mt_collect_transition_gate_verdicts,
    _mt_resolve_transition_gate_inputs as _mt_resolve_transition_gate_inputs,
    _mt_resolve_transition_gate_verdicts as _mt_resolve_transition_gate_verdicts,
    _mt_gate_representative as _mt_gate_representative,
    _mt_translate_gate_verdicts as _mt_translate_gate_verdicts,
    _mt_emit_skipped_gate as _mt_emit_skipped_gate,
    _mt_emit_transition_gate_effect as _mt_emit_transition_gate_effect,
    _mt_run_transition_gates as _mt_run_transition_gates,
    _mt_enrol_gate_byproducts as _mt_enrol_gate_byproducts,
    _mt_run_pre_review_gate as _mt_run_pre_review_gate,
)


_LANES_MISSING_ON_PLANNED_EXIT_MESSAGE = (
    "Cannot move {task_id} out of 'planned': lanes.json is absent for mission "
    "'{mission_slug}'. Run `spec-kitty doctor mission-state --fix --mission "
    "{mission_slug}` to rebuild execution lanes from the canonical event log, "
    "then retry."
)


def _default_move_task_ports() -> TasksPorts:
    """Production port bundle for ``move_task`` (coord router bound to tasks.py)."""
    from specify_cli.cli.commands.agent import tasks as _tasks

    return TasksPorts(
        fs=_tasks.RealFsReader(),
        # move_task routes BOTH seams through the ``tasks`` namespace (it was the
        # only family to override ``commit_status``); no ``target_branch``.
        coord=_tasks.seam_coord_router(route_emit=True),
        git=_tasks.RealGitOps(),
        render=_tasks.RealRender(),
    )


class _PostTransitionSideEffectFailure(RuntimeError):
    """A transition committed, but a later owned-checkout side effect failed."""

    def __init__(
        self,
        cause: Exception,
        signal: VerdictDurabilitySignal | None,
    ) -> None:
        super().__init__(str(cause))
        self.cause = cause
        self.signal = signal


@dataclass
class _MoveTaskState:
    """Mutable orchestration state threaded through ``move_task``'s phases.

    The single-body command tracked ~30 loose locals across gather → decide →
    execute; the phase helpers exchange this one value object instead. Not frozen:
    each phase fills its own slice in the same order the original body did.
    """

    # --- raw command inputs ---
    task_id: str
    to: str
    mission: str | None
    agent: str | None
    assignee: str | None
    shell_pid: str | None
    note: str | None
    review_feedback_file: Path | None
    approval_ref: str | None
    reviewer: str | None
    self_review_fallback: bool
    intended_reviewer: str | None
    reviewer_failure_reason: str | None
    done_override_reason: str | None
    force: bool
    tracker_ref: list[str] | None
    skip_review_artifact_check: bool
    auto_commit: bool | None
    json_output: bool
    skip_pre_review_gate: bool = False
    model: str | None = None
    profile: str | None = None
    invocation_id: str | None = None
    owned: OwnedCheckout | None = None
    # --- phase A: resolved targets ---
    target_lane: Lane = Lane.PLANNED
    repo_root: Path = field(default_factory=Path)
    main_repo_root: Path = field(default_factory=Path)
    target_branch: str = ""
    mission_slug: str = ""
    tracker_ref_values: tuple[str, ...] = ()
    skip_target_branch_commit: bool = False
    resolved_auto_commit: bool = False
    feature_dir: Path = field(default_factory=Path)
    mt_feature_dir: Path = field(default_factory=Path)
    wp: WorkPackage | None = None
    old_lane: Lane = Lane.PLANNED
    current_agent: str | None = None
    resolved_binding: ResolvedBinding | None = None
    # --- phase B: decision facts ---
    verdict_artifact_path: Path | None = None
    resolved_feedback_source: Path | None = None
    request: MoveTaskRequest | None = None
    # --- phase C: decision ---
    decision: Emit | None = None
    arb_review_ref: str | None = None
    # --- phase C.5: pre-review regression gate (WP02 T004/T005) ---
    pre_review_gate_metadata: dict[str, Any] | None = None
    review_base_ref: str | None = None
    # --- phase D: emit plan ---
    emit_plan: TransitionPlan | None = None
    evidence_dict: dict[str, Any] | None = None
    note_text: str | None = None
    actor: str = "user"
    canonical_lane: str | None = None
    review_feedback_pointer: str | None = None
    rejected_review_result: ReviewResult | None = None
    # SC-007: the structured review outcome (reviewer + verdict + reference) WP06
    # threads into ``build_transition_plan`` (WP02's optional ``review_result``
    # seam) so the two ``in_review -> *`` edges it owns are force-free instead of
    # ``force=True``. ``None`` off the in_review-exit edges (WP02 owns the rest).
    plan_review_result: ReviewResult | None = None
    # --- phase E/F: emit + persist ---
    event: StatusEvent | None = None
    final_hop_actor: str | None = None
    # True once the claim triple (``shell_pid``/``shell_pid_created_at``/``agent``)
    # rode a real ``planned -> claimed`` transition's ``policy_metadata`` sidecar
    # (FR-004), so :func:`_mt_emit_runtime_state` does NOT re-emit it as an
    # off-axis ``InnerStateChanged`` delta.
    claim_emitted: bool = False
    # WP11 (T048/T049/T050): the durability signal from whichever verdict
    # writer ``_mt_finalize_plan`` called this invocation (approval or planned-
    # rollback rejection -- the two are mutually exclusive per lane, so at
    # most one assigns this). ``None`` when neither writer ran, or the
    # approval no-op guard fired (nothing was written). Read by ``_mt_output``
    # to surface T049/T050's ``--json`` key, and by ``_do_move_task`` to know
    # whether T048's revert-compensator has anything to undo after a later
    # ``_mt_execute`` failure.
    pending_verdict_write: VerdictDurabilitySignal | None = None
    # True immediately after the first durable status hop. Later failures must
    # report partial application and retain any verdict referenced by that hop.
    transition_applied: bool = False
    # #3578: the operator signal for the otherwise-silent rollback-to-``planned``
    # delta (subtask reset + claim release + review-override clear), including the
    # FR-003 work-state split. Set by ``_build_claim_review_override`` whenever the
    # target lane is ``planned``; read by ``_mt_output`` to emit the human line +
    # JSON fields. ``None`` on every non-rollback move.
    rollback_reset_summary: _RollbackResetSummary | None = None
    # Authoritative from-lane resolved inside the status lock immediately
    # before the current transition attempt.  ``old_lane`` predates verdict
    # queue waiting and can be stale when a concurrent reviewer moves first.
    authoritative_lane_at_emit: Lane | None = None


# --- phase A: resolve targets (I/O) -----------------------------------------


def _mt_warn_worktree_kitty_specs(st: _MoveTaskState) -> None:
    """Informational note when a worktree carries a stale ``kitty-specs/`` copy."""
    from specify_cli.cli.commands.agent import tasks as _tasks

    cwd = Path.cwd().resolve()
    if not (is_worktree_context(cwd) and not st.json_output and cwd != st.main_repo_root):
        return
    worktree_kitty = None
    current = cwd
    while current != current.parent and ".worktrees" in str(current):
        if (current / KITTY_SPECS_DIR).exists():
            worktree_kitty = current / KITTY_SPECS_DIR
            break
        current = current.parent
    if worktree_kitty is None:
        return
    # #2037: st.mission_slug threads back to the operator-typed `--mission` CLI
    # value (no `assert_safe_path_segment` upstream on this path). This is a
    # read-only `.exists()` probe feeding an informational note, so an unsafe
    # slug fails closed by skipping the note rather than raising.
    try:
        assert_safe_path_segment(st.mission_slug)
    except ValueError:
        logging.getLogger(__name__).warning(
            "Refusing to probe worktree kitty-specs/ with unsafe mission_slug %r (traversal guard); skipping the informational note.",
            st.mission_slug,
        )
        return
    if (worktree_kitty / st.mission_slug / "tasks").exists():
        _tasks.console.print(f"[dim]Note: Using planning repo's kitty-specs/ on {st.target_branch} (worktree copy ignored)[/dim]")


def _mt_resolve_current_agent(st: _MoveTaskState) -> str | None:
    """Resolve the prior-owner agent from the reduced snapshot (FR-007, IC-04).

    The WP file no longer carries the ``agent`` runtime field post-cutover, so the
    ownership read routes onto the ungated snapshot accessor instead of
    ``extract_scalar(frontmatter, "agent")``. Extracted (not inlined) so the
    snapshot read is a unit-testable seam and the cx-15 ``_mt_emit_runtime_state``
    off-axis emit path is left untouched (D-14). Returns ``None`` for an unclaimed
    WP (no snapshot ``agent`` slot) — matching the pre-reroute "no agent in
    frontmatter" result.
    """
    from specify_cli.status import wp_snapshot_state

    snapshot = wp_snapshot_state(st.feature_dir, st.task_id)
    if snapshot is None:
        return None
    agent = snapshot.get("agent")
    return str(agent) if agent else None


def _mt_preflight_owned_request(st: _MoveTaskState) -> None:
    """Reject unsupported owned-checkout modes before any mission write.

    #3980: the ``OWNED_SYNC_UNSUPPORTED`` refusal died with the launch
    flip — owned checkouts publish moments like any checkout. The fan-out
    handlers registered on the status emit seam are individually bounded and
    non-raising (``status/adapters.py``), and the Zeitgeist moment handler
    no-ops without a session/team, so an owned transition under active sync
    completes with at worst a skipped fan-out warning.
    """
    assert st.owned is not None
    require_unstaged_index(st.owned)
    if st.target_lane not in (
        Lane.PLANNED,
        Lane.CLAIMED,
        Lane.IN_PROGRESS,
        Lane.FOR_REVIEW,
        Lane.IN_REVIEW,
        Lane.APPROVED,
    ):
        raise ActionContextError(
            "OWNED_TRANSITION_UNSUPPORTED",
            "Owned checkout supports the local review lifecycle through approval only.",
        )
    if (
        st.force
        or st.skip_pre_review_gate
        or st.skip_review_artifact_check
        or st.self_review_fallback
        or st.intended_reviewer
        or st.reviewer_failure_reason
        or st.done_override_reason
    ):
        raise ActionContextError(
            OwnedRefusalCode.OWNED_OPTION_UNSUPPORTED,
            "Review overrides are not supported with --owned-checkout.",
        )


def _mt_guard_planned_boundary_lanes(st: _MoveTaskState) -> None:
    """Refuse a transition out of ``planned`` when ``lanes.json`` is absent.

    #4758 defense-in-depth (FR-002/FR-006): even if the legacy
    ``agent tasks finalize-tasks`` path regresses and seeds the event log
    without computing ``lanes.json`` (WP01's co-located-write fix), a WP must
    not be able to leave ``planned`` into a canonical-state shape every
    downstream gate (``implement``, review, approval) refuses with no
    documented repair. ``lanes.json`` is the PRIMARY-partition ``LANE_STATE``
    artifact (see ``workspace/context.py``'s ``resolve_workspace_for_wp``) —
    read through the same seam, not the coord husk ``mt_feature_dir``.

    Scoped to the ordinary lane-topology path only: an ``--owned-checkout``
    single-branch selection resolves its own review base separately
    (``_mt_resolve_owned_review_base``, only for the ``for_review``/
    ``approved`` hops) and never required ``lanes.json`` to leave ``planned``
    -- widening this guard onto owned checkouts would refuse transitions that
    were never gated by lane computation.
    """
    if st.owned is not None:
        return
    if st.old_lane != Lane.PLANNED or st.target_lane == Lane.PLANNED:
        return
    from specify_cli.lanes.persistence import read_lanes_json

    lanes_read_dir = placement_seam(st.main_repo_root, st.mission_slug).read_dir(MissionArtifactKind.LANE_STATE)
    if read_lanes_json(lanes_read_dir) is not None:
        return
    from specify_cli.cli.commands.agent import tasks as _tasks

    _tasks._output_error(
        st.json_output,
        _LANES_MISSING_ON_PLANNED_EXIT_MESSAGE.format(task_id=st.task_id, mission_slug=st.mission_slug),
    )
    raise typer.Exit(1)


def _mt_apply_owned_targets(st: _MoveTaskState, owned: OwnedCheckout) -> None:
    """Owned arm of target resolution: every branch and slug comes off the validated fact.

    No project-root probe, no ``get_main_repo_root`` and no mission-handle
    walk -- ownership was validated exactly once at the Typer edge
    (``tasks._resolve_task_owned``).
    """
    if not st.resolved_auto_commit:
        raise ActionContextError(OwnedRefusalCode.OWNED_OPTION_UNSUPPORTED, "Owned status changes require auto-commit.")
    try:
        WPInnerStateDelta(
            agent=st.agent,
            assignee=st.assignee,
            note=st.note,
            shell_pid=int(st.shell_pid) if st.shell_pid else None,
            tracker_refs=st.tracker_ref,
        )
    except (ValueError, TypeError) as exc:
        raise ActionContextError(OwnedRefusalCode.OWNED_INPUT_INVALID, str(exc)) from exc
    st.mission_slug = owned.mission_slug
    st.main_repo_root, st.target_branch = owned.repository_root, owned.write_branch


def _mt_resolve_targets(st: _MoveTaskState, ports: TasksPorts) -> None:
    """Resolve roots/branch/feature-dir and load the WP + its canonical lane."""
    from specify_cli.cli.commands.agent import tasks as _tasks

    st.target_lane = Lane(ensure_lane(st.to))
    owned = st.owned
    if owned is not None:
        _mt_preflight_owned_request(st)
        repo_root = owned.owned_root
    else:
        located_root = _tasks.locate_project_root()
        if located_root is None:
            _tasks._output_error(st.json_output, "Could not locate project root")
            raise typer.Exit(1)
        repo_root = located_root
    st.repo_root = repo_root
    # FR-010 / FR-019: one-shot sparse-checkout warning before any read/mutate.
    _tasks._emit_sparse_session_warning(repo_root, command="spec-kitty agent tasks move-task")
    st.resolved_auto_commit = _tasks.get_auto_commit_default(repo_root) if st.auto_commit is None else st.auto_commit
    if owned is not None:
        _mt_apply_owned_targets(st, owned)
    else:
        st.mission_slug = _tasks._find_mission_slug(explicit_mission=st.mission, json_output=st.json_output, repo_root=repo_root)
        st.main_repo_root, st.target_branch = _tasks._ensure_target_branch_checked_out(repo_root, st.mission_slug, st.json_output)
    from specify_cli.cli.commands.agent.workflow import _resolve_dispatch_binding

    claim_mission_id: str | None = None
    if st.invocation_id is not None:
        # read-side-seam-primary-primitive-closure-01KYKMMT WP06 (T029): routed
        # off the retiring ``primary_feature_dir_for_mission`` wrapper onto the
        # seam directly — PRIMARY_METADATA, since the read is meta.json's
        # ``mission_id`` (resolve_mission_identity). WP08 (T036): dropped the
        # caller-side canonicalizer fold — redundant with the seam's own
        # internal fold for a PRIMARY-partition kind.
        primary_feature_dir = placement_seam(
            st.main_repo_root,
            st.mission_slug,
            owned=st.owned,
        ).read_dir(MissionArtifactKind.PRIMARY_METADATA)
        claim_mission_id = resolve_mission_identity(primary_feature_dir).mission_id
    st.resolved_binding = _resolve_dispatch_binding(
        model=st.model,
        profile=st.profile,
        invocation_id=st.invocation_id,
        repo_root=st.owned.owned_root if st.owned else st.main_repo_root,
        mission_id=claim_mission_id,
        wp_id=st.task_id,
        # FR-006 (IC-04): APPROVED/DONE are reviewer-role decisions, not
        # implementer ones -- resolving them with action="implement" (the
        # pre-WP04 brownfield gap) stamped the WRONG profile/model onto the
        # approval's policy_metadata (``_mt_approval_policy_metadata``).
        action=("review" if st.target_lane in (Lane.IN_REVIEW, Lane.APPROVED, Lane.DONE) else "implement"),
    )
    st.skip_target_branch_commit = (
        _tasks._skip_target_branch_commit(st.main_repo_root, st.mission_slug, st.target_branch) if st.resolved_auto_commit and st.owned is None else False
    )
    # Protected-branch status-commit refusal — a hard early exit that MUST fire
    # before the authoritative event-log read below (``_read_transactional_wp_lane``),
    # matching the pre-rewire order. Deferring it into the decision core (pass 1)
    # let an un-bootstrapped event log raise "Canonical status not found" first,
    # masking the protected-branch refusal (issue #1386 regression).
    if st.resolved_auto_commit and not st.skip_target_branch_commit:
        protected_error = _tasks._protected_branch_status_commit_error(st.target_branch, st.main_repo_root, "spec-kitty agent tasks move-task", st.mission_slug)
        if protected_error is not None:
            self_review_error = _self_review_fallback_option_error(
                enabled=st.self_review_fallback,
                target_lane=str(st.target_lane),
                force=st.force,
                intended_reviewer=st.intended_reviewer,
                failure_reason=st.reviewer_failure_reason,
            )
            if self_review_error is not None:
                _tasks._output_error(st.json_output, self_review_error)
                raise typer.Exit(1)
            _tasks._output_error(st.json_output, protected_error)
            raise typer.Exit(1)
    st.tracker_ref_values = tuple(t.strip() for t in (st.tracker_ref or []) if t and t.strip())
    _mt_warn_worktree_kitty_specs(st)
    # Boundary guard — hard-reject pre-3.0 layout before any WP mutation.
    # WP06 FR-010 (T027): the shared coord-status dir STAYS on the coord husk.
    # ``feature_write_dir`` wraps ``resolve_feature_dir_for_mission`` (the kind-blind
    # coord-husk leg) — the SAME on-disk dir the pre-rewire body read; it feeds the
    # pre30 guard, the authoritative event-log lane read (``_read_transactional_wp_lane``),
    # and the coord override persist. It is NEVER repointed to a primary kind — that
    # would move the event-log read off the coord husk and reintroduce the split-brain
    # FR-010 closes.
    handle = MissionHandle(repo_root=st.main_repo_root, mission_slug=st.mission_slug, owned=st.owned)
    st.mt_feature_dir = ports.coord.feature_write_dir(handle)
    try:
        check_pre30_layout(st.mt_feature_dir)
    except Pre30LayoutError as e:
        _tasks._output_error(st.json_output, str(e))
        raise typer.Exit(1) from None
    st.wp = _tasks.locate_work_package(
        repo_root,
        st.mission_slug,
        st.task_id,
        owned=st.owned,
    )
    # Lane is event-log-only; read from the canonical coord-husk event log.
    st.old_lane = _read_transactional_wp_lane(
        feature_dir=st.mt_feature_dir,
        mission_slug=st.mission_slug,
        wp_id=st.task_id,
        repo_root=st.main_repo_root,
        owned=st.owned,
    )
    if st.owned is not None and st.old_lane not in (
        Lane.PLANNED,
        Lane.CLAIMED,
        Lane.IN_PROGRESS,
        Lane.FOR_REVIEW,
        Lane.IN_REVIEW,
        Lane.APPROVED,
    ):
        raise ActionContextError(
            "OWNED_TRANSITION_UNSUPPORTED",
            "Owned checkout does not support transitions from this lane.",
        )
    # #4758 FR-002: refuse leaving ``planned`` with no ``lanes.json`` to rebuild
    # from, before any mission write below.
    _mt_guard_planned_boundary_lanes(st)
    # Event-store write leg — the SAME coord husk as ``mt_feature_dir``.
    st.feature_dir = st.mt_feature_dir
    if st.owned is not None and st.target_lane in (Lane.FOR_REVIEW, Lane.APPROVED):
        st.review_base_ref = _mt_resolve_owned_review_base(st)
    # FR-007 / IC-04: prior-owner attribution is snapshot-sourced (the WP file no
    # longer carries the ``agent`` runtime field post-cutover) — read via the
    # ungated snapshot accessor in an extracted helper, not
    # ``extract_scalar(frontmatter, "agent")``.
    st.current_agent = _mt_resolve_current_agent(st)


# --- phase B: gather decision facts (I/O) -----------------------------------


def _mt_resolve_feedback(st: _MoveTaskState) -> tuple[str | None, bool, bool, str | None]:
    """Resolve the ``--review-feedback-file`` facts (+ planned-rollback content)."""
    if st.review_feedback_file is None:
        return None, False, False, None
    candidate = st.review_feedback_file.expanduser()
    candidate = candidate.resolve() if candidate.is_absolute() else (Path.cwd() / candidate).resolve()
    source_str = str(candidate)
    exists = candidate.exists()
    is_file = candidate.is_file()
    content: str | None = None
    if exists and is_file:
        st.resolved_feedback_source = candidate
        if is_review_rejection_edge(str(st.old_lane), str(st.target_lane)):
            content = candidate.read_text(encoding="utf-8").strip()
    return source_str, exists, is_file, content


def _mt_build_request(
    st: _MoveTaskState,
    *,
    protected_error: str | None,
    review_verdict: str | None,
    review_artifact_name: str | None,
    feedback: tuple[str | None, bool, bool, str | None],
    unchecked_subtasks: tuple[str, ...],
    review_ready: bool,
    review_guidance: tuple[str, ...],
    latest_implementer: str | None = None,
) -> MoveTaskRequest:
    """Assemble the pass-1 ``MoveTaskRequest`` (late facts default to skip-safe)."""
    feedback_source_str, feedback_exists, feedback_is_file, feedback_content = feedback
    return MoveTaskRequest(
        task_id=st.task_id,
        target_lane=str(st.target_lane),
        old_lane=str(st.old_lane),
        force=st.force,
        agent=st.agent,
        current_agent=st.current_agent,
        note=st.note,
        auto_commit=bool(st.resolved_auto_commit),
        target_branch=st.target_branch,
        skip_target_branch_commit=st.skip_target_branch_commit,
        tracker_ref_values=tuple(st.tracker_ref_values),
        assignee=st.assignee,
        shell_pid=st.shell_pid,
        self_review_fallback=st.self_review_fallback,
        intended_reviewer=st.intended_reviewer,
        reviewer_failure_reason=st.reviewer_failure_reason,
        protected_error=protected_error,
        review_verdict=review_verdict,
        review_artifact_name=review_artifact_name,
        skip_review_artifact_check=st.skip_review_artifact_check,
        feedback_provided=st.review_feedback_file is not None,
        feedback_source=feedback_source_str,
        feedback_exists=feedback_exists,
        feedback_is_file=feedback_is_file,
        feedback_content=feedback_content,
        unchecked_subtasks=unchecked_subtasks,
        review_ready=review_ready,
        review_guidance=review_guidance,
        done_execution_mode=None,
        done_merged=False,
        done_merge_msg="",
        done_override_reason=st.done_override_reason,
        issue_matrix_blocker=None,
        is_arbiter_override=False,
        effective_reviewer=None,
        effective_approval_ref=None,
        mission_slug=st.mission_slug,
        latest_implementer=latest_implementer,
    )


def _lane_deliverable_paths(worktree_path: Path, entries: Iterable[StatusEntry]) -> tuple[Path, ...]:
    """Turn status entries into absolute deliverable paths.

    A rename/copy names two paths: stage both the source (its deletion) and the
    destination, skipping any side that is spec-kitty runtime state.
    """
    from specify_cli.cli.commands.agent.tasks_shared import _filter_runtime_state_paths

    sides: list[GitPath] = []
    for entry in entries:
        sides.extend(side for side in (entry.orig_path, entry.path) if side is not None)
    deliverable = _filter_runtime_state_paths(StatusEntry(xy="??", path=side) for side in sides)
    return tuple(worktree_path / str(entry.path) for entry in deliverable)


def _mt_resolve_owned_review_base(st: _MoveTaskState) -> str:
    """Resolve one immutable, suitable review base for an owned checkout."""
    from specify_cli.cli.commands.agent import tasks as _tasks
    from specify_cli.core.vcs.git import capture_branch_tip
    from specify_cli.lanes.persistence import require_lanes_json
    from specify_cli.lanes.planning_commit_classify import PinClass, classify_recorded_pin
    from specify_cli.lanes.worktree_allocator import ORPHANED_PIN_RECOVERY_HINT

    assert st.owned is not None
    owned = st.owned
    manifest = require_lanes_json(st.feature_dir)
    declared = manifest.planning_commit_sha
    if not declared:
        raise ActionContextError(
            "OWNED_REVIEW_BASE_INVALID",
            "Owned review requires lanes.json planning_commit_sha.",
        )

    # #4827/WP03/T015: `rev-parse --verify` below only proves the object is
    # PRESENT -- it succeeds identically for a healthy pin and for an
    # ORPHANED one (rewritten out of the target branch's history but not
    # garbage-collected), so a bare presence check would silently compute the
    # review diff against a DEAD base (invariant-lens Finding 2). Classify
    # against the TARGET-BRANCH tip -- captured from `st.main_repo_root`
    # (== `owned.repository_root`), NOT `owned.owned_root` (the selected, possibly-stale
    # checkout being reviewed) -- and fail closed before any diff is
    # computed. Reconciled to the same classification the allocator's merge
    # helper and `check_claim_ancestry` use (research.md D5).
    #
    # ``FOREIGN`` (the object never existed at all) is deliberately left to
    # the pre-existing `resolve_commit`/`OWNED_REVIEW_BASE_INVALID` path
    # below rather than folded in here: D3 refuses a foreign object even
    # with `--allow-orphaned`, so naming that recovery for a foreign SHA
    # would point at a fix that cannot work -- the existing "must resolve to
    # commits" refusal is already the correct, unrecoverable-data diagnosis.
    target_tip = capture_branch_tip(st.main_repo_root, st.target_branch)
    pin_class = classify_recorded_pin(owned.owned_root, declared, target_tip)
    if pin_class is PinClass.ORPHANED:
        raise ActionContextError(
            "OWNED_REVIEW_BASE_ORPHANED",
            f"Recorded planning commit {declared} is orphaned against the "
            f"target-branch tip -- the owned-review base would be computed against a "
            f"dead ancestor. Run {ORPHANED_PIN_RECOVERY_HINT!r} to re-point it, then retry.",
        )

    def resolve_commit(ref: str) -> str | None:
        result = _tasks.subprocess.run(
            ["git", "rev-parse", "--verify", f"{ref}^{{commit}}"],
            cwd=str(owned.owned_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if result.returncode != 0:
            return None
        resolved = result.stdout.strip()
        return resolved or None

    base_commit = resolve_commit(declared)
    head_commit = resolve_commit("HEAD")
    if base_commit is None or head_commit is None:
        raise ActionContextError(
            "OWNED_REVIEW_BASE_INVALID",
            "Owned review base and HEAD must resolve to commits in the selected checkout.",
        )
    if base_commit == head_commit:
        raise ActionContextError(
            "OWNED_REVIEW_BASE_INVALID",
            "Owned review base must differ from HEAD.",
        )
    if git_merge_base(owned.owned_root, head_commit, base_commit) != base_commit:
        raise ActionContextError(
            "OWNED_REVIEW_BASE_INVALID",
            "Owned review base must be an ancestor of HEAD in the selected checkout.",
        )
    return base_commit


def _mt_owned_workspace(st: _MoveTaskState) -> ResolvedWorkspace:
    """The owned single-branch checkout as the WP's workspace.

    Routed through the ONE owned-workspace constructor,
    :func:`specify_cli.workspace.context.resolve_workspace_for_wp` with the
    fact (architecture review item 5): move-task never hand-builds a second
    owned ``ResolvedWorkspace`` shape. That arm yields the owned-checkout
    resolution kind (#5100 R-10: a checkout-root kind, so the status stamp
    reads ``direct_repo``), the fact's checkout as ``worktree_path`` and its
    ``write_branch`` as ``branch_name``.
    """
    from specify_cli.workspace.context import resolve_workspace_for_wp

    assert st.owned is not None
    return resolve_workspace_for_wp(st.owned.repository_root, st.mission_slug, st.task_id, owned=st.owned)


def _drop_lane_coord_residue(worktree_path: Path, paths: tuple[Path, ...]) -> tuple[Path, ...]:
    """Seam-A guard for the raw lane-deliverable commit (#2549 / FR-003 / T012).

    ``_mt_commit_lane_deliverables`` commits lane deliverables through a RAW
    ``safe_commit`` on the LANE branch -- it BYPASSES the kind-aware
    ``commit_for_mission`` classifier (and the ``BookkeepingTransaction`` Seam-A
    guard) entirely. The ``_filter_runtime_state_paths`` deny-list only strips
    spec-kitty's ``.spec-kitty/`` / ``.kittify/`` runtime dirs -- it does NOT
    exclude a coord-partition artifact (``status.events.jsonl`` / ``status.json``
    / ``acceptance-matrix.json`` / ``issue-matrix.md``). So if a coord-residue
    file ever surfaces in the lane worktree's ``git status`` (e.g. a
    ``move-task --force`` that materialised a status snapshot into a lane whose
    sparse-checkout exclusion is absent/stale), the raw commit would land it on
    the LANE ref -- the residual #2549 leak.

    This filter routes the deliverable set through Seam A: a coord-partition
    artifact (:func:`~specify_cli.coordination.coherence.is_coord_residue_churn`)
    is DROPPED from the lane commit so it never lands on the lane branch (the
    coord-owned status log is authored on the coordination branch by the
    transactional emitter, never carried on a lane; the lane's copy is stale
    residue). Every genuine PRIMARY deliverable (code, ``tasks/WP*.md``) is
    preserved. Withdrawn Trigger A is respected: this NEVER touches the
    status->coord routing, only status->LANE.
    """
    from specify_cli.coordination.coherence import is_coord_residue_churn

    kept: list[Path] = []
    for path in paths:
        try:
            rel = path.relative_to(worktree_path).as_posix()
        except ValueError:
            rel = path.name
        if is_coord_residue_churn(rel):
            continue
        kept.append(path)
    return tuple(kept)


def _mt_owned_file_patterns(st: _MoveTaskState) -> tuple[str, ...]:
    """Return normalized authored ownership patterns for the selected WP."""
    assert st.wp is not None
    metadata, _body = read_authored_wp_frontmatter(st.wp.path)
    return tuple(pattern.replace("\\", "/").removeprefix("./") for pattern in metadata.owned_files if pattern.strip())


def _mt_matches_owned_file(path: str, patterns: tuple[str, ...]) -> bool:
    """Match a repository-relative path with commit-guard-compatible globs."""
    normalized = path.replace("\\", "/").removeprefix("./")
    for pattern in patterns:
        if fnmatch.fnmatch(normalized, pattern):
            return True
        prefix = pattern.replace("/**", "").replace("/*", "").rstrip("/")
        if prefix and normalized.startswith(prefix + "/"):
            return True
    return False


def _mt_require_owned_implementation(st: _MoveTaskState) -> None:
    """Require a committed implementation delta in the WP's authored scope."""
    assert st.owned is not None
    assert st.review_base_ref is not None
    patterns = _mt_owned_file_patterns(st)
    changed = merge_base_changed_files_checked(
        st.owned.owned_root,
        st.review_base_ref,
        diff_filter="ACDMRTUXB",
    )
    if changed is None:
        # Guard (FR-013): an unreadable diff refuses with its own message.
        raise ActionContextError(
            "OWNED_IMPLEMENTATION_MISSING",
            "Owned review could not read the committed change set: the merge-base diff against review base "
            f"{st.review_base_ref} (lanes.json `planning_commit_sha`) failed in {st.owned.owned_root}. "
            "Make sure that commit is reachable in this checkout (fetch it, or recreate the local branch that carries it), "
            f"or repoint `planning_commit_sha` in {st.feature_dir / 'lanes.json'} to a commit that is an ancestor of HEAD, then retry.",
        )
    if not patterns or not any(_mt_matches_owned_file(path, patterns) for path in changed):
        raise ActionContextError(
            "OWNED_IMPLEMENTATION_MISSING",
            "Owned review requires a committed change matching WP owned_files.",
        )


def _mt_commit_lane_deliverables(st: _MoveTaskState) -> None:
    """Commit finished lane deliverables before a review transition (#2335).

    A killed implementer can leave its deliverables uncommitted in the lane
    worktree; without this, ``move-task --to for_review`` dead-ends demanding a
    manual in-worktree ``git commit`` — violating the tool-drives-commits rule.
    When auto-commit is enabled, stage + commit the finished deliverables via the
    tool (``safe_commit`` on the lane branch) so the readiness guard sees a clean
    tree. Best-effort: any failure leaves the tree untouched and the existing
    ``_validate_ready_for_review`` guard explains the situation.
    """
    from specify_cli.cli.commands.agent import tasks as _tasks
    from specify_cli.lanes.persistence import CorruptLanesError, MissingLanesError

    if st.owned is not None:
        workspace = _mt_owned_workspace(st)
    else:
        try:
            workspace = _tasks.resolve_workspace_for_wp(st.main_repo_root, st.mission_slug, st.task_id)
        except (ValueError, FileNotFoundError, MissingLanesError, CorruptLanesError):
            # No resolvable lane workspace (missions without lanes.json included) —
            # nothing to recover; the readiness guard stays authoritative.
            return
    # Only a workspace with a real branch to commit onto carries deliverables
    # to auto-commit; a planning-artifact WP has no lane branch at all
    # (branch_name is None) — nothing to do. #5100 WP04: ``branch_name`` is
    # the actual discriminator, not ``resolution_kind`` -- an owned checkout
    # (``owned_checkout``) and a single_branch repo-root code WP (``repo_root``)
    # are both checkout roots (never ``lane_workspace``) yet each has a real branch (the owned
    # target branch, or the mission/target branch) with genuine deliverables
    # to auto-commit, same as an isolated lane worktree.
    if workspace.branch_name is None:
        return
    if st.owned is None and workspace.resolution_kind == "repo_root":
        # single_branch repo-root WP: the write checkout is the operator's whole
        # repository-root checkout, so ``git status`` there holds unrelated and
        # stray files (``.env.local`` ...). Sweeping them into a "deliverables"
        # commit could land them on a protected target -- and would let a
        # no-work WP pass the gate. The WP author commits their own work; the
        # claim-base for_review gate then refuses when there is none.
        if not st.json_output:
            _tasks.console.print(
                f"[yellow]Note:[/yellow] {st.task_id} runs in the repository root checkout; "
                "commit your WP work yourself before moving to for_review (no auto-commit)."
            )
        return
    worktree_path = workspace.worktree_path
    if not worktree_path.exists():
        return

    try:
        status = status_entries(worktree_path, untracked=None)
    except GitCommandError:
        # Advisory: a failed probe just skips the best-effort auto-commit; the
        # for_review uncommitted-changes guard still runs and blocks the move.
        return
    # Reuse the guard's runtime-state filter so we only commit genuine deliverables
    # (never spec-kitty's own review-lock / .kittify bookkeeping).
    filtered = _tasks._filter_runtime_state_paths(status)
    if not filtered:
        return
    paths = _lane_deliverable_paths(worktree_path, filtered)
    # Seam-A (#2549 / FR-003 / T012): never let a coord-partition artifact land
    # on the lane branch via this raw ``safe_commit`` path.
    paths = _drop_lane_coord_residue(worktree_path, paths)
    if not paths:
        return
    if st.owned is not None:
        patterns = _mt_owned_file_patterns(st)
        outside_scope = sorted(
            path.relative_to(worktree_path).as_posix() for path in paths if not _mt_matches_owned_file(path.relative_to(worktree_path).as_posix(), patterns)
        )
        if outside_scope:
            raise ActionContextError(
                "OWNED_DELIVERABLE_SCOPE_REFUSED",
                "Owned auto-commit includes files outside WP owned_files: " + ", ".join(outside_scope),
            )

    try:
        from mission_runtime import CommitTarget

        from specify_cli.git import safe_commit

        safe_commit(
            repo_root=st.main_repo_root,
            worktree_root=worktree_path,
            target=CommitTarget(ref=workspace.branch_name),
            message=f"chore({st.task_id}): commit lane deliverables for review",
            paths=paths,
            owned=st.owned,
        )
        # #5115/WP07 (FR-018): spec-kitty's own for_review auto-commit is a
        # lane advance -- record the tip explicitly (defense in depth
        # alongside the post-commit hook this same commit already triggers
        # when installed). Harmless no-op for a repo-root/owned checkout's
        # non-lane branch (nothing ever reads a tip ref keyed on that name).
        from specify_cli.lanes.lane_tip import record_tip

        record_tip(st.main_repo_root, workspace.branch_name)
        if not st.json_output:
            _tasks.console.print(f"[cyan]Committed lane deliverables for {st.task_id} on {workspace.branch_name} before review.[/cyan]")
    except Exception as exc:  # noqa: BLE001 — best-effort; the guard explains on failure
        if not st.json_output:
            _tasks.console.print(f"[yellow]Warning:[/yellow] could not auto-commit lane deliverables for {st.task_id}: {exc}")


def _mt_gather_review_facts(st: _MoveTaskState) -> None:
    """Gather the early (guard-gating) facts and build the pass-1 request."""
    from specify_cli.cli.commands.agent import tasks as _tasks

    assert st.wp is not None
    # Protected-branch refusal already fired as a hard early exit in
    # ``_mt_resolve_targets`` (before the event-log read) — if the branch were
    # protected we would never reach here, so this is always None by construction.
    protected_error: str | None = None
    review_verdict: str | None = None
    review_artifact_name: str | None = None
    if st.target_lane in (Lane.APPROVED, Lane.DONE):
        review_verdict, st.verdict_artifact_path, review_artifact_name = resolve_review_verdict_facts(st.wp.path)
    feedback = _mt_resolve_feedback(st)
    unchecked_subtasks: tuple[str, ...] = ()
    if st.target_lane in (Lane.FOR_REVIEW, Lane.APPROVED, Lane.DONE) and not st.force:
        unchecked_subtasks = tuple(
            _tasks._check_unchecked_subtasks(
                st.repo_root,
                st.mission_slug,
                st.task_id,
                st.force,
                owned=st.owned,
            )
        )
    review_ready = True
    review_guidance: tuple[str, ...] = ()
    if st.target_lane in (Lane.FOR_REVIEW, Lane.APPROVED, Lane.DONE):
        # A for_review auto-commit is deliberately deferred until the real
        # pre-review gate permits progress. The initial decision still runs
        # every other read-only guard before that gate; readiness is refreshed
        # immediately after the deferred commit. Other lanes and explicit
        # no-auto-commit moves retain their original validation order.
        defer_readiness = st.target_lane == Lane.FOR_REVIEW and st.resolved_auto_commit and not st.force
        if not defer_readiness:
            validation_options: dict[str, Any] = {}
            if st.owned is not None:
                assert st.review_base_ref is not None
                validation_options = {
                    "owned": st.owned,
                    "workspace_override": _mt_owned_workspace(st),
                    "review_base_ref": st.review_base_ref,
                    "check_kitty_specs": False,
                }
            is_valid, guidance = _tasks._validate_ready_for_review(
                st.repo_root,
                st.mission_slug,
                st.task_id,
                st.force,
                target_lane=str(st.target_lane),
                **validation_options,
            )
            review_ready = is_valid
            review_guidance = tuple(guidance)
    # #5196: resolve "who is the WP's latest implementer" once (one extra event
    # read) so the ownership guard can admit the review-loop roles. Fail closed
    # toward today's behaviour: any read failure leaves ``None`` (no allowance).
    latest_implementer: str | None = None
    try:
        latest_implementer = latest_implementer_actor(
            _tasks.read_events_transactional(
                feature_dir=st.feature_dir,
                mission_slug=st.mission_slug,
                repo_root=st.main_repo_root,
                owned=st.owned,
            ),
            st.task_id,
        )
    except Exception:  # noqa: BLE001 — fail closed toward today's behaviour (R-03)
        latest_implementer = None
    st.request = _mt_build_request(
        st,
        protected_error=protected_error,
        review_verdict=review_verdict,
        review_artifact_name=review_artifact_name,
        feedback=feedback,
        unchecked_subtasks=unchecked_subtasks,
        review_ready=review_ready,
        review_guidance=review_guidance,
        latest_implementer=latest_implementer,
    )


def _mt_complete_deferred_for_review_readiness(st: _MoveTaskState) -> None:
    """Commit deliverables and refresh readiness only after the gate permits."""
    from specify_cli.cli.commands.agent import tasks as _tasks

    if not (st.target_lane == Lane.FOR_REVIEW and st.resolved_auto_commit and not st.force):
        return
    assert st.request is not None
    _mt_commit_lane_deliverables(st)
    owned: OwnedCheckout | None = None
    workspace_override: object | None = None
    review_base_ref: str | None = None
    check_kitty_specs = True
    if st.owned is not None:
        assert st.review_base_ref is not None
        _mt_require_owned_implementation(st)
        owned = st.owned
        workspace_override = _mt_owned_workspace(st)
        review_base_ref = st.review_base_ref
        check_kitty_specs = False
    is_valid, guidance = _tasks._validate_ready_for_review(
        st.repo_root,
        st.mission_slug,
        st.task_id,
        st.force,
        target_lane=str(st.target_lane),
        owned=owned,
        workspace_override=workspace_override,
        review_base_ref=review_base_ref,
        check_kitty_specs=check_kitty_specs,
    )
    st.request = replace(
        st.request,
        review_ready=is_valid,
        review_guidance=tuple(guidance),
    )
    _mt_run_decision(st)


# --- phase C: two-pass decision + partial-write persists ---------------------


def _mt_fire_override_persist(st: _MoveTaskState) -> None:
    """OLD-timing review-artifact override (FR-004 partial-write-on-refusal).

    Thin forwarder onto
    :func:`tasks_verdict_persistence.persist_review_override_before_guard`
    (WP06 verdict-seam extraction). Kept as a real, natively-defined symbol
    here (frozen compat surface: ``tasks.py`` re-exports it, and
    ``test_tasks_compat_surface.py`` pins it as native to this module) so
    every historical ``tasks.<name>`` reference keeps resolving — mirrors the
    house forwarder precedent already established by
    :func:`_mt_run_pre_review_gate` -> :func:`_mt_run_transition_gates`. Do
    NOT inline the body back here.
    """
    persist_review_override_before_guard(st)


def _mt_done_ancestry_facts(st: _MoveTaskState) -> tuple[str | None, bool, str]:
    """Late fact: done-transition execution mode + branch-merge ancestry."""
    from specify_cli.cli.commands.agent import tasks as _tasks

    if st.target_lane != Lane.DONE:
        return None, False, ""
    try:
        done_workspace = _tasks.resolve_workspace_for_wp(st.main_repo_root, st.mission_slug, st.task_id)
        done_execution_mode: str | None = done_workspace.execution_mode
    except (ValueError, FileNotFoundError):
        done_execution_mode = "code_change"
    done_merged = False
    done_merge_msg = ""
    if done_execution_mode == "code_change":
        done_merged, done_merge_msg = _tasks._wp_branch_merged_into_target(
            repo_root=st.main_repo_root,
            mission_slug=st.mission_slug,
            wp_id=st.task_id,
            target_branch=st.target_branch,
        )
    return done_execution_mode, done_merged, done_merge_msg


def _mt_issue_matrix_facts(st: _MoveTaskState) -> str | None:
    """Late fact: issue-matrix approval blocker.

    read-side-seam-primary-primitive-closure-01KYKMMT WP06 (T029): the blind
    primitive ``primary_feature_dir_for_mission`` — formerly reached via the
    ``_tasks.<attr>`` patch seam (``@patch("...agent.tasks.
    primary_feature_dir_for_mission")``, test_pre30_guard_wiring /
    test_patched_primary_feature_dir_intercepts_issue_matrix_facts) — is routed
    off that retiring wrapper onto the kind-aware seam directly. Kind is
    ``SPEC``, not ``ISSUE_MATRIX``: ``_issue_matrix_approval_blocker``'s
    ``primary_feature_dir`` argument is consulted ONLY to detect ``spec.md``'s
    referenced issues (a genuine PRIMARY-partition artifact); the
    issue-matrix.md read itself uses ``st.feature_dir`` — the caller's already
    topology-resolved COORD surface — unchanged.

    WP08 (T036): the caller-side canonicalizer fold DROPPED — redundant with
    the seam's own internal fold for a PRIMARY-partition kind (``SPEC``); the
    handle is passed straight through.
    """
    if st.target_lane not in (Lane.APPROVED, Lane.DONE):
        return None
    blocker: str | None = _issue_matrix_approval_blocker(
        st.feature_dir,
        target_lane=st.target_lane,
        primary_feature_dir=placement_seam(
            st.main_repo_root,
            st.mission_slug,
            owned=st.owned,
        ).read_dir(MissionArtifactKind.SPEC),
    )
    return blocker


def _mt_approval_facts(st: _MoveTaskState) -> tuple[str | None, str | None]:
    """Late fact: auto-detected reviewer + defaulted approval reference.

    #4327: ``--note`` never fills the approval reference — the ref slot is
    pointer-only, so it takes ``--approval-ref`` or the synthetic
    ``auto-approval:<WP>:<date>`` token, and the operator's prose stays in
    ``reason`` (the durable local slot the codec keeps off the wire).
    """
    from specify_cli.cli.commands.agent import tasks as _tasks

    if st.target_lane not in (Lane.APPROVED, Lane.DONE):
        return None, None
    effective_reviewer = st.reviewer or _tasks._detect_reviewer_name()
    effective_approval_ref = st.approval_ref or synthetic_auto_approval_ref(st.task_id, format_stamp(now_utc(), "%Y%m%d"))
    return effective_reviewer, effective_approval_ref


def _mt_gather_late_facts(st: _MoveTaskState) -> None:
    """Gather pass-2 facts (allowed to raise) and rebuild the request."""
    from specify_cli.cli.commands.agent import tasks as _tasks

    assert st.request is not None
    done_execution_mode, done_merged, done_merge_msg = _mt_done_ancestry_facts(st)
    issue_matrix_blocker = _mt_issue_matrix_facts(st)
    effective_reviewer, effective_approval_ref = _mt_approval_facts(st)
    is_arbiter_override = _tasks._detect_arbiter_override(st.feature_dir, st.task_id, st.old_lane, resolve_lane_alias(st.target_lane), st.force)
    st.request = replace(
        st.request,
        done_execution_mode=done_execution_mode,
        done_merged=done_merged,
        done_merge_msg=done_merge_msg,
        issue_matrix_blocker=issue_matrix_blocker,
        is_arbiter_override=is_arbiter_override,
        effective_reviewer=effective_reviewer,
        effective_approval_ref=effective_approval_ref,
    )


def _mt_fire_arbiter_persist(st: _MoveTaskState) -> None:
    """OLD-timing arbiter-decision persist (FR-004 partial-write-on-refusal).

    Fires before pass 2 runs the issue-matrix guard, so an issue-matrix refusal
    still leaves the arbiter JSON on disk. ``arb_review_ref`` links the forward
    event to the rejection it overrides.
    """
    from specify_cli.cli.commands.agent import tasks as _tasks

    assert st.request is not None
    if not arbiter_persist_signal(st.request):
        return
    arb_note_text, _ = _effective_note_text(st.request)
    st.arb_review_ref = _tasks._run_arbiter_override(
        feature_dir=st.feature_dir,
        mission_slug=st.mission_slug,
        main_repo_root=st.main_repo_root,
        task_id=st.task_id,
        note_text=arb_note_text,
        agent=st.agent,
        json_output=st.json_output,
    )


def _mt_run_decision(st: _MoveTaskState) -> None:
    """Two-pass pure decision; RefuseExit1 short-circuits with the guard output."""
    from specify_cli.cli.commands.agent import tasks as _tasks

    assert st.request is not None
    # OLD-timing override persist BEFORE the guard sequence (pass 1).
    _mt_fire_override_persist(st)
    decision = _tasks.decide_transition(st.request)
    if not isinstance(decision, RefuseExit1):
        # Early guards cleared — gather the late (possibly-raising) facts, fire the
        # OLD-timing arbiter persist ahead of the issue-matrix guard, then re-decide.
        _mt_gather_late_facts(st)
        _mt_fire_arbiter_persist(st)
        assert st.request is not None
        decision = _tasks.decide_transition(st.request)
    if isinstance(decision, RefuseExit1):
        if not st.json_output:
            for warn_line in decision.console_warning:
                _tasks.console.print(warn_line)
        _tasks._output_error(st.json_output, decision.error, diagnostic=decision.diagnostic)
        raise typer.Exit(1)
    st.decision = decision


# --- phase C.5: transition gates — extracted to ``tasks_move_task_gates`` (#5629) ---


# --- phase D: finalize emit plan --------------------------------------------


def _mt_resolve_reviewer_identity(st: _MoveTaskState) -> str:
    """Resolve the effective reviewer identity: ``--reviewer``, else ``--agent``,
    else the emit actor, else ``"unknown"``.

    Shared by the rejected review-cycle artifact's ``reviewer_agent`` frontmatter
    (:func:`_mt_finalize_plan`) and the structured :class:`ReviewResult` derivation
    (:func:`_mt_plan_review_result`) so the two never diverge (the caller-declared
    ``--reviewer`` identity, when present, is authoritative over the WP *actor*
    driving the CLI invocation).
    """
    return (st.reviewer or st.agent or st.actor or "unknown").strip() or "unknown"


def _mt_resolve_active_reviewer_identity(st: _MoveTaskState) -> str | None:
    """Resolve the identity that claimed review (``for_review -> in_review``)
    from the event log, for an agent-driven completion that omits ``--agent``
    (#4670, FR-005).

    Reads the WP's transition events and returns the projected identity
    (:func:`~specify_cli.status.actor_identity_str`) of the MOST RECENT
    ``* -> in_review`` hop -- the review claim (``action review --agent
    <identity>``, or its test-fixture equivalent) that is authoritative for
    "who is reviewing this WP right now". Returns ``None`` when no such
    event is on record (an unclaimed/force-bypassed WP), so every caller
    falls through to its own pre-existing default instead of fabricating an
    identity that was never asserted (FR-006).

    Returns ``None`` without attempting a read when ``mission_slug`` is
    unset (the ``_MoveTaskState`` dataclass default, ``""``) -- a state
    built without ever resolving targets (e.g. a unit test driving a single
    phase helper directly against a bare ``_make_state()``-style fixture)
    has no real event log to consult.
    """
    if not st.mission_slug:
        return None

    from specify_cli.cli.commands.agent import tasks as _tasks

    events = _tasks.read_events_transactional(
        feature_dir=st.feature_dir,
        mission_slug=st.mission_slug,
        repo_root=st.main_repo_root,
        owned=st.owned,
    )
    for existing_event in reversed(events):
        if existing_event.wp_id == st.task_id and existing_event.to_lane == Lane.IN_REVIEW:
            identity = actor_identity_str(existing_event.actor).strip()
            return identity or None
    return None


# --- phase E: emit the lane transition(s) via commit_status ------------------


def _mt_current_event_lane(st: _MoveTaskState) -> str:
    """The WP's current canonical lane (the emit chain's from-lane seed)."""
    from specify_cli.cli.commands.agent import tasks as _tasks

    current_event_lane: str | None = None
    for existing_event in reversed(
        _tasks.read_events_transactional(
            feature_dir=st.feature_dir,
            mission_slug=st.mission_slug,
            repo_root=st.main_repo_root,
            owned=st.owned,
        )
    ):
        if existing_event.wp_id == st.task_id:
            current_event_lane = str(existing_event.to_lane)
            break
    if current_event_lane is None:
        # No canonical state — finalize-tasks must run first (#1589).
        from specify_cli.status import uninitialized_status_error

        raise RuntimeError(uninitialized_status_error(st.mission_slug, st.task_id, st.feature_dir))
    return current_event_lane


# --- phase F: persist the WP file + primary commit via commit_artifact --------


# --- phase H: review-lock release + result output ----------------------------


def _mt_output(st: _MoveTaskState) -> None:
    """Emit the success envelope + dependent-WP warnings (coord skip arm aware)."""
    from specify_cli.cli.commands.agent import tasks as _tasks

    assert st.decision is not None and st.wp is not None
    event_fields = _tasks._status_event_result_fields(st.event)
    # WP03: the coord skip arm's polymorphic ``--json`` envelope is driven by the
    # core decision (``Emit.skip_primary``), not the raw fact.
    status_events_path = _tasks._coord_status_events_path(st.main_repo_root, st.mission_slug) if st.decision.skip_primary else None
    result: dict[str, object] = {
        "result": "success",
        "transition_applied": True,
        "task_id": st.task_id,
        "old_lane": st.old_lane,
        "new_lane": st.target_lane,
        "path": str(st.wp.path),
        "event_id": event_fields["event_id"],
        "work_package_id": st.task_id,
        "to_lane": event_fields["to_lane"] or st.canonical_lane,
        "status_events_path": str(status_events_path or (st.feature_dir / EVENTS_FILENAME)),
    }
    if st.decision.skip_primary:
        result["wp_file_update"] = "skipped"
        result["wp_file_update_reason"] = "protected branch with coordination topology; status event is authoritative on the coordination branch"
        if st.agent:
            result["frontmatter_fields_skipped"] = ["agent"]
    if st.review_feedback_pointer is not None:
        result["review_feedback"] = st.review_feedback_pointer
    if st.pre_review_gate_metadata is not None:
        result["pre_review_gate"] = st.pre_review_gate_metadata
    # WP11 (T049/T050): an explicit ``false`` (never a bare missing key) so a
    # machine consumer never has to infer non-durability from absence.
    # ``verdict_durability_skip_reason`` distinguishes FR-013's sanctioned
    # ``--no-auto-commit`` case from the protected-primary-coord case (T050) —
    # present only when non-durable, since a durable write has no "reason".
    if st.pending_verdict_write is not None:
        outcome = st.pending_verdict_write.outcome
        if "review_feedback" not in result and st.pending_verdict_write.review_cycle is not None:
            result["review_feedback"] = st.pending_verdict_write.review_cycle.pointer
        result["verdict_durably_persisted"] = outcome.verdict_durably_persisted
        result["durability_classification"] = outcome.classification
        result["durability_reason"] = outcome.reason
        result["evidence_ref"] = outcome.evidence_ref
        result["destination_ref"] = outcome.destination_ref
        if outcome.reason is not None:
            result["verdict_durability_skip_reason"] = outcome.reason
    message = f"[green]✓[/green] Moved {st.task_id} from {st.old_lane} to {st.target_lane}"
    # #3578: surface the rollback-to-``planned`` deltas that were previously
    # silent — the subtask reset count (+ work-state split, FR-003) and the two
    # sibling actions (claim release, review-override clear) — as both JSON
    # fields and a human line, so an operator knows what to re-mark.
    if st.rollback_reset_summary is not None:
        _mt_apply_rollback_signal(result, st.rollback_reset_summary)
        message += "\n" + _mt_rollback_signal_lines(st.rollback_reset_summary)
    _tasks._output_result(st.json_output, result, message)
    # Check for dependent WP warnings when moving to for_review (T083).
    _tasks._check_dependent_warnings(st.repo_root, st.mission_slug, st.task_id, st.target_lane, st.json_output)


def _mt_post_transition_diagnostic(
    failure: _PostTransitionSideEffectFailure,
) -> dict[str, object]:
    """Describe an owned move whose durable transition preceded a later failure."""
    diagnostic: dict[str, object] = {
        "result": "error",
        "error": str(failure.cause),
        "transition_applied": True,
        "verdict_durably_persisted": False,
        "evidence_ref": None,
        "destination_ref": None,
    }
    if isinstance(failure.cause, ActionContextError):
        diagnostic["error_code"] = failure.cause.code
    if failure.signal is not None:
        outcome = failure.signal.outcome
        diagnostic.update(
            {
                "verdict_durably_persisted": outcome.verdict_durably_persisted,
                "durability_classification": outcome.classification,
                "durability_reason": outcome.reason,
                "evidence_ref": outcome.evidence_ref,
                "destination_ref": outcome.destination_ref,
            }
        )
    return diagnostic


def _mt_apply_rollback_signal(result: dict[str, object], summary: _RollbackResetSummary) -> None:
    """Add the #3578 rollback operator signal to the ``--json`` envelope."""
    result["subtasks_reset_count"] = summary.reset_count
    result["subtasks_reset_ids"] = list(summary.reset_ids)
    result["subtasks_previously_completed"] = list(summary.previously_completed)
    result["subtasks_never_completed"] = list(summary.never_completed)
    result["runtime_claim_released"] = summary.claim_released
    result["review_override_cleared"] = summary.review_override_cleared


def _mt_rollback_signal_lines(summary: _RollbackResetSummary) -> str:
    """Render the #3578 rollback operator signal as human-readable lines."""
    # Wording stays accurate for EVERY move to ``planned`` — a review rollback,
    # but also a plain ``claimed -> planned`` un-claim or ``blocked -> planned``
    # (adversarial review finding 1b): all three reset the roster, so avoid
    # implying the WP necessarily came from review.
    lines = [f"[yellow]↺ Reset {summary.reset_count} subtask(s) to planned[/yellow] — re-mark completed work before this WP re-enters review."]
    if summary.previously_completed:
        lines.append(
            f"  • {len(summary.previously_completed)} completed in an earlier "
            f"cycle ({', '.join(summary.previously_completed)}): re-verify, "
            "don't rebuild from scratch."
        )
    if summary.never_completed:
        lines.append(f"  • {len(summary.never_completed)} never completed ({', '.join(summary.never_completed)}).")
    lines.append("  • runtime claim released; any review-override cleared (the WP exposes no live claim and no superseded approval).")
    return "\n".join(lines)


@dataclass(frozen=True)
class _MoveTaskArgs:
    """Parameter object for ``_do_move_task``'s raw CLI-facing arguments.

    T033 (#2649): the pre-extraction signature carried 21 individual
    parameters (task_id..skip_pre_review_gate, plus the ``ports`` DI seam) —
    over the local ≤13 ceiling. Grouping every raw input into ONE dataclass
    (field set and defaults mirror the pre-extraction signature exactly,
    NFR-002) collapses the call surface to ``(args, *, ports)`` — 2
    parameters — leaving headroom for future flags (e.g. draft PR #2639) to
    join this dataclass instead of re-breaching the ceiling. Module-private
    (C-008/NFR-004): no net-new public symbol.
    """

    task_id: str
    to: str
    mission: str | None
    agent: str | None
    assignee: str | None
    shell_pid: str | None
    note: str | None
    review_feedback_file: Path | None
    approval_ref: str | None
    reviewer: str | None
    self_review_fallback: bool
    intended_reviewer: str | None
    reviewer_failure_reason: str | None
    done_override_reason: str | None
    force: bool
    tracker_ref: list[str] | None
    skip_review_artifact_check: bool
    auto_commit: bool | None
    json_output: bool
    skip_pre_review_gate: bool = False
    model: str | None = None
    profile: str | None = None
    invocation_id: str | None = None
    owned: OwnedCheckout | None = None


def _do_move_task(args: _MoveTaskArgs, *, ports: TasksPorts | None = None) -> None:
    """Orchestrate ``move-task`` over the WP03 core + WP02 ports (C-005 seam).

    ``ports=None`` builds the production bundle (coord router bound to this
    module's patchable symbols). Tests inject a Fake bundle to observe the executed
    side-effects (T029). The phase helpers run in the SAME order as the original
    single body: resolve → gather → decide → finalize → execute → output.

    T033 (#2649): ``args`` groups the 19 raw CLI-facing inputs the original
    21-parameter signature carried individually — see :class:`_MoveTaskArgs`.

    T048 (``DM-01KZ6JE62Q6CQ24DMBX8KZZ5R9``): ``_mt_execute`` is wrapped
    in-line (not factored into a new named helper -- the widened ``owned_
    files`` grant is scoped to this diff only, and adding a new top-level
    symbol here would also require registering it in ``test_tasks_compat_
    surface.py``'s consolidated re-export guard, which is out of this WP's
    two named purposes). On a transition-emit failure, an already-committed
    verdict write is actively reverted before the failure propagates -- the
    write-then-emit call order stays UNCHANGED (``_mt_finalize_plan`` already
    ran; this only wraps the pre-existing, unmodified ``_mt_execute`` step).
    A revert-compensator failure is NOT swallowed into the original error --
    see :class:`tasks_verdict_persistence.VerdictRevertError`'s rationale;
    the bare original exception (unchanged type/traceback) is re-raised on a
    successful revert, and only a revert FAILURE escalates to a new,
    explicitly compounded error (:class:`tasks_verdict_persistence.
    VerdictRevertCompoundFailure`, #3773 item 2 -- carries the durability
    signal so the ``--json`` envelope's ``verdict_durably_persisted`` field
    stays populated on this compound path too, not just prose).
    """
    from specify_cli.cli.commands.agent import tasks as _tasks

    ports = ports or _default_move_task_ports()
    st = _MoveTaskState(
        task_id=args.task_id,
        to=args.to,
        mission=args.mission,
        agent=args.agent,
        model=args.model,
        profile=args.profile,
        invocation_id=args.invocation_id,
        assignee=args.assignee,
        shell_pid=args.shell_pid,
        note=args.note,
        review_feedback_file=args.review_feedback_file,
        approval_ref=args.approval_ref,
        reviewer=args.reviewer,
        self_review_fallback=args.self_review_fallback,
        intended_reviewer=args.intended_reviewer,
        reviewer_failure_reason=args.reviewer_failure_reason,
        done_override_reason=args.done_override_reason,
        force=args.force,
        tracker_ref=args.tracker_ref,
        skip_review_artifact_check=args.skip_review_artifact_check,
        auto_commit=args.auto_commit,
        json_output=args.json_output,
        skip_pre_review_gate=args.skip_pre_review_gate,
        owned=args.owned,
    )
    try:
        _mt_resolve_targets(st, ports)
        # Fail on an unbootstrapped event log before review/workspace gates can
        # mask the actionable root cause (for example, a dependency cycle that
        # prevented finalize-tasks from creating lanes.json; #1589).
        _mt_current_event_lane(st)
        _mt_gather_review_facts(st)
        _mt_run_decision(st)
        _mt_run_pre_review_gate(st)
        _mt_complete_deferred_for_review_readiness(st)
        _mt_finalize_plan(st, ports)
        try:
            _mt_execute(st, ports)
        except Exception as execute_error:
            if st.owned is not None and st.transition_applied:
                raise _PostTransitionSideEffectFailure(
                    execute_error,
                    st.pending_verdict_write,
                ) from execute_error
            if st.pending_verdict_write is not None:
                try:
                    revert_committed_verdict_write(st, st.pending_verdict_write)
                except Exception as revert_error:
                    # #3773 item 2: carry the structured durability signal on
                    # this compound-failure path (not just prose) -- see
                    # ``VerdictRevertCompoundFailure``'s docstring for why
                    # ``st.pending_verdict_write`` is always durably-persisted
                    # here.
                    raise VerdictRevertCompoundFailure(
                        f"Transition emit failed for {st.task_id} ({execute_error}); "
                        f"the FR-002 revert-compensator ALSO failed to undo the "
                        f"already-committed verdict write ({revert_error}). Operator "
                        f"attention required -- a committed verdict may still exist.",
                        signal=st.pending_verdict_write,
                    ) from execute_error
            raise
        _mt_output(st)
    except typer.Exit:
        raise
    except Exception as e:
        if args.owned is not None and isinstance(e, ActionContextError):
            # Unified owned-refusal output (#5445): human mode on stderr as
            # ``Error: [<CODE>] <message>``, ``--json`` mode indented -- the
            # same shape ``emit_owned_refusal`` renders. Not routed through
            # ``emit_owned_refusal`` itself: this catch-all accepts ANY
            # ``ActionContextError`` (including codes outside the registered
            # owned-refusal vocabulary; see
            # ``test_context_error_envelope_is_opt_in``), and
            # ``emit_owned_refusal`` fails closed on an unregistered code.
            if args.json_output:
                print(json.dumps({"error_code": e.code, "error": str(e)}, indent=2))
            else:
                err_console.print(f"Error: [{e.code}] {e}")
            raise typer.Exit(1) from e
        if isinstance(e, _PostTransitionSideEffectFailure):
            diagnostic: dict[str, object] | None = _mt_post_transition_diagnostic(e)
        elif isinstance(e, VerdictPersistenceFailure):
            outcome = e.signal.outcome
            diagnostic = {
                "result": "error",
                "error": str(e),
                "verdict_durably_persisted": outcome.verdict_durably_persisted,
                "durability_classification": outcome.classification,
                "durability_reason": outcome.reason,
                "evidence_ref": outcome.evidence_ref,
                "destination_ref": outcome.destination_ref,
            }
        elif isinstance(e, VerdictRevertCompoundFailure):
            # #3773 item 2: same envelope shape as the ``VerdictPersistenceFailure``
            # branch above -- every field read off the SAME ``VerdictDurabilitySignal
            # .outcome`` shape, so a machine consumer parses one shape for both. This
            # is the revert-compensator-also-failed compound path (VerdictRevertError,
            # including the ``VerdictSaveBusy`` queue-busy case): the verdict write
            # itself was already durably committed (``VerdictRevertCompoundFailure``'s
            # docstring), so ``outcome.verdict_durably_persisted`` reads ``True`` here
            # -- never a guess, never a hand-written literal.
            outcome = e.signal.outcome
            diagnostic = {
                "result": "error",
                "error": str(e),
                "verdict_durably_persisted": outcome.verdict_durably_persisted,
                "durability_classification": outcome.classification,
                "durability_reason": outcome.reason,
                "evidence_ref": outcome.evidence_ref,
                "destination_ref": outcome.destination_ref,
            }
        elif isinstance(e, TransitionError):
            current_lane = st.authoritative_lane_at_emit or st.old_lane
            diagnostic = {
                "result": "error",
                "code": "invalid_transition",
                "error": str(e),
                "current_lane": current_lane.value,
                "requested_lane": (st.canonical_lane or resolve_lane_alias(str(st.target_lane))),
                "verdict_durably_persisted": False,
                "evidence_ref": None,
                "destination_ref": None,
            }
        else:
            diagnostic = e.to_diagnostic() if isinstance(e, EventPersistenceError) else None
        if diagnostic is not None and st.canonical_lane is not None and not isinstance(e, TransitionError):
            diagnostic["failed_event_to_lane"] = diagnostic.get("to_lane")
            diagnostic["to_lane"] = st.canonical_lane
            diagnostic["requested_lane"] = st.canonical_lane
        _tasks._output_error(args.json_output, str(e), diagnostic=diagnostic)
        raise typer.Exit(1) from None


# ===========================================================================
# WP09 (tasks-py-degod-wave2-01KWH9EQ / FR-008, IC-07): the final
# registration-shim sweep relocates the move_task-family stragglers that
# remained ``tasks.py``-resident after WP05 — the arbiter override pair
# (``_detect_arbiter_override`` / ``_run_arbiter_override``), the coord
# event-path probe (``_coord_status_events_path``), the event-field shaper
# (``_status_event_result_fields``) and the reviewer detector
# (``_detect_reviewer_name``). Moved VERBATIM except that patched seam
# symbols (``resolve_topology``, ``subprocess``, ``read_events_transactional``,
# ``console`` — research.md D7 / the ``__all__`` seam-infra names) are now
# routed through ``_tasks.<attr>`` (lazy in-function import) so every
# historical ``@patch("...agent.tasks.<sym>")`` keeps INTERCEPTING.
# ``tasks.py`` re-imports each name in the explicit ``as`` re-export form, so
# ``tasks.<name>`` stays a module attribute (NFR-002).
# ===========================================================================


def _coord_status_events_path(repo_root: Path, mission_slug: str) -> Path | None:
    """Return coord-worktree status event path when coord topology is active."""
    try:
        from specify_cli.coordination.workspace import CoordinationWorkspace
        from specify_cli.lanes.branch_naming import mission_dir_name, resolve_transaction_mid8
        from specify_cli.missions._read_path_resolver import candidate_feature_dir_for_mission
        from specify_cli.status import EVENTS_FILENAME

        # Topology resolver (FR-004): resolve the on-disk mid8 from the embedded
        # ``<slug>-<mid8>`` tail; "" for a legacy/flattened mission (no coord dir).
        mid8 = resolve_transaction_mid8(mission_slug, mission_id=None, mid8=None, coordination_branch=None)
        if not mid8:
            return None
        # Delegate the idempotent ``<slug>-<mid8>`` compose to the seam so the
        # inline endswith-dedup (the #1949 reinvention WP09 bans) lives only in
        # lanes.branch_naming (FR-010).
        mission_dir = mission_dir_name(mission_slug, mid8=mid8)
        coord_root = CoordinationWorkspace.worktree_path(repo_root, mission_slug, mid8)
        if not coord_root.exists():
            return None
        coord_feature_dir: Path = candidate_feature_dir_for_mission(coord_root, mission_dir)
        events_path: Path = coord_feature_dir / EVENTS_FILENAME
        return events_path
    except Exception:
        return None


def _status_event_result_fields(event: object | None) -> dict[str, str | None]:
    """Return JSON-safe status event fields for command output."""
    if event is None:
        return {"event_id": None, "to_lane": None}

    event_id = getattr(event, "event_id", None)
    if not isinstance(event_id, str):
        event_id = None

    to_lane = getattr(event, "to_lane", None)
    if to_lane is None:
        to_lane_value = None
    else:
        raw_value = getattr(to_lane, "value", to_lane)
        to_lane_value = raw_value if isinstance(raw_value, str) else str(raw_value)

    return {"event_id": event_id, "to_lane": to_lane_value}


def _detect_reviewer_name() -> str:
    """Detect reviewer name from git config, with safe fallback."""
    from specify_cli.cli.commands.agent import tasks as _tasks

    try:
        result = _tasks.subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip() or "unknown"
    except (_tasks.subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def _detect_arbiter_override(
    feature_dir: Path,
    task_id: str,
    old_lane: Lane,
    target_canonical: str,
    force: bool,
) -> bool:
    """Return whether this move is an arbiter override (WP03 I/O for the core).

    A ``--force`` move from ``planned`` straight to ``approved`` or ``done`` that
    follows a rejection (from ``for_review`` or ``in_review``) is an arbiter
    override; forced rework moves are not (#5196). Detection reads the event
    log; the pure ``decide_transition`` core consumes the boolean result.
    """
    try:
        from specify_cli.review.arbiter import _is_arbiter_override
    except ImportError:
        return False
    return bool(_is_arbiter_override(feature_dir, task_id, old_lane, target_canonical, force))


def _run_arbiter_override(
    *,
    feature_dir: Path,
    mission_slug: str,
    main_repo_root: Path,
    task_id: str,
    note_text: str | None,
    agent: str | None,
    json_output: bool,
) -> str | None:
    """Persist the arbiter decision and return the rejection's ``review_ref``.

    Executes the arbiter-override side effect once ``decide_transition`` has
    authorised it (``Emit.arbiter_forward``). Returns the derived ``review_ref``
    so the emit plan can link the forward event to the rejection it overrides.

    FR-016 (WP07, arbiter-root-threading): this function's own already-resolved
    ``main_repo_root`` parameter is now threaded straight through to
    :func:`persist_arbiter_override_decision` (and, from there, into
    :func:`specify_cli.review.arbiter.persist_arbiter_decision`'s now-required
    ``repo_root``) instead of being dropped on the floor and left to that
    function's retired ``feature_dir.parent.parent`` self-inference — a
    wrong-partition bug under a materialized coordination topology, where
    ``feature_dir`` here may already be the coord-husk mission dir.

    WP06 (verdict-seam extraction): the persist try/except (and its exception
    handling) now lives in ``tasks_verdict_persistence`` as
    :func:`persist_arbiter_override_decision`; this function builds the
    decision and calls straight into it instead of running the try/except
    inline.
    """
    from specify_cli.cli.commands.agent import tasks as _tasks

    try:
        from specify_cli.review.arbiter import (
            create_arbiter_decision,
            parse_category_from_note,
        )
    except ImportError:
        return None

    _arb_events = _tasks.read_events_transactional(
        feature_dir=feature_dir,
        mission_slug=mission_slug,
        repo_root=main_repo_root,
    )
    _arb_wp_events = [e for e in _arb_events if e.wp_id == task_id]
    _arb_latest = _arb_wp_events[-1] if _arb_wp_events else None
    _arb_review_ref = _arb_latest.review_ref if _arb_latest else None

    _arb_category, _arb_explanation = parse_category_from_note(note_text)
    _arb_actor = agent or "operator"
    arbiter_decision = create_arbiter_decision(
        arbiter_name=_arb_actor,
        category=_arb_category,
        explanation=_arb_explanation,
    )
    persist_arbiter_override_decision(
        feature_dir=feature_dir,
        wp_id=task_id,
        review_ref=_arb_review_ref,
        decision=arbiter_decision,
        category=_arb_category,
        explanation=_arb_explanation,
        json_output=json_output,
        main_repo_root=main_repo_root,
    )

    return _arb_review_ref
