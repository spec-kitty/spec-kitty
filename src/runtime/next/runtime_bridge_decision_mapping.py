"""Decision mapping shared by the runtime bridge's advance and read paths (#2560).

Mission ``runtime-bridge-query-seam-01M490EQ`` moved this cluster out of
``runtime_bridge.py`` verbatim. It turns a runtime ``NextDecision`` into the
CLI's ``Decision`` and owns the helpers that mapping needs:

* ``_materialize_decision`` (+ the ``_prompt_exists`` port) — the one wrapper
  over ``runtime_bridge_cores.step_or_blocked``;
* ``_map_runtime_decision`` and its ``_map_wp_step_decision`` /
  ``_map_non_wp_step_decision`` / ``_build_decision_required_prompt_file``
  extractions;
* the board-authority WP-iteration selector (``_WpBoardAction`` …
  ``_resolve_wp_board_action``) with ``_wp_iteration_action_and_state`` and
  ``_build_wp_iteration_decision``;
* the merged-mission and finalized-board short-circuits
  (``_merged_mission_short_circuit``, ``_finalized_task_board_override_step``
  with ``_count_wp_endings`` / ``_has_claimable_planned_wp``) and
  ``_wp_task_surface_error``.

Callers: ``runtime_bridge`` (``decide_next_via_runtime`` and its ``_dn_*``
phases), ``runtime_bridge_engine.advance_run_state_after_composition``, and the
query/answer read path. Each calls these names on this module, so a test that
steers one patches it here.

Import rule (pinned by ``tests/runtime/test_runtime_bridge_query_seam_layout.py``):
this module sits below its callers. It imports ``runtime_bridge_cores`` and
``runtime.next.decision`` and never imports ``runtime_bridge``,
``runtime_bridge_engine``, ``runtime_bridge_composition``, the query module or
the decision-log module, so the engine adapter can import it at its own top
level without the deferred back-edge it used before.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from mission_runtime import OwnedCheckout
from runtime.next import runtime_bridge_cores as _cores
from runtime.next._internal_runtime import MissionRunRef, NextDecision
from runtime.next.decision import (
    Decision,
    DecisionKind,
    _build_prompt_or_error,
    _compute_wp_progress,
    _find_first_wp_by_lane,
    _state_to_action,
)
from specify_cli.mission import get_mission_type
from specify_cli.status import CanonicalStatusNotFoundError, Lane, get_all_wp_snapshots
from specify_cli.status_lanes import has_operator_provenance, is_acceptable_ending


TASKS_GLOB = "WP*.md"


_WP_ITERATION_STEPS = frozenset({"implement", "review"})


def _is_wp_iteration_step(step_id: str) -> bool:
    """Check if a step is a WP-iteration step (implement, review)."""
    return step_id in _WP_ITERATION_STEPS


def _has_claimable_planned_wp(feature_dir: Path, *, status_dir: Path | None = None) -> bool:
    """True only when a ``planned`` WP is genuinely claimable (#5669).

    Gates the override's ``planned`` arm on the single dependency-aware
    claimability authority (``discovery.preview_claimable_wp``, C-001) instead of
    bare lane presence, so a dependency-walled ``planned`` WP never pins the
    board to ``implement`` while a sibling WP awaits review (#4860 is preserved:
    a walled WP is never dispatched for ``implement``).
    """
    from runtime.next.discovery import preview_claimable_wp

    return preview_claimable_wp(feature_dir, status_dir=status_dir).wp_id is not None


def _finalized_task_board_override_step(
    feature_dir: Path,
    progress: dict[str, int | float] | None,
    *,
    status_dir: Path | None = None,
) -> str | None:
    """Return the next step implied by finalized WP state, if available.

    This is intentionally narrow: it only overrides stale early runtime phases
    after a mission already has tasks.md, finalized WP files, and canonical WP
    lane state. It does not reorder non-finalized mission DAG execution.
    A board whose WPs all reach acceptable endings reports ``accept``; ``done``
    remains reserved for a board whose reduced lanes are all done, so an
    operator-canceled WP is never reported as done.

    Only a *claimable* ``planned`` WP reports ``implement``; a dependency-walled
    one falls through so a pending ``for_review`` WP reports ``review`` (#5669).
    ``claimed``/``in_progress`` WPs are a genuine resume and always report
    ``implement``.
    """
    if progress is None:
        return None
    total = int(progress.get("total_wps", 0) or 0)
    if total <= 0:
        return None
    if not (feature_dir / "tasks.md").is_file() or not (feature_dir / "tasks").is_dir():
        return None

    if _has_claimable_planned_wp(feature_dir, status_dir=status_dir):
        return "implement"
    if _find_first_wp_by_lane(feature_dir, "claimed", status_dir=status_dir) is not None:
        return "implement"
    if _find_first_wp_by_lane(feature_dir, "in_progress", status_dir=status_dir) is not None:
        return "implement"
    if _find_first_wp_by_lane(feature_dir, "for_review", status_dir=status_dir) is not None:
        return "review"
    if _find_first_wp_by_lane(feature_dir, "in_review", status_dir=status_dir) is not None:
        return "blocked:review_in_progress"

    done_endings, acceptable_endings = _count_wp_endings(
        feature_dir,
        status_dir=status_dir,
    )
    if acceptable_endings == total:
        return "done" if done_endings == total else "accept"
    return "blocked:no_actionable_wp"


def _reduced_wp_lane(wp_snapshot: Mapping[str, Any] | None) -> str:
    """Return the canonical lane slot from a reduced WP snapshot."""
    if wp_snapshot is None:
        return str(Lane.UNINITIALIZED)
    return str(wp_snapshot.get("lane", Lane.GENESIS))


def _count_wp_endings(
    feature_dir: Path,
    *,
    status_dir: Path | None = None,
) -> tuple[int, int]:
    """Count WP files whose reduced lanes are done and acceptable endings."""
    tasks_dir = feature_dir / "tasks"
    if not tasks_dir.is_dir():
        return 0, 0

    lane_read_dir = status_dir if status_dir is not None else feature_dir
    try:
        wp_snapshots = get_all_wp_snapshots(lane_read_dir)
    except CanonicalStatusNotFoundError:
        return 0, 0

    acceptable_endings = 0
    done_endings = 0
    for wp_file in sorted(tasks_dir.glob(TASKS_GLOB)):
        wp_match = re.match(r"(WP\d+)", wp_file.stem)
        wp_id = wp_match.group(1) if wp_match else wp_file.stem
        wp_snapshot = wp_snapshots.get(wp_id)
        lane = _reduced_wp_lane(wp_snapshot)
        if lane == str(Lane.DONE):
            done_endings += 1
        if is_acceptable_ending(
            lane,
            has_provenance=has_operator_provenance(wp_snapshot),
        ):
            acceptable_endings += 1
    return done_endings, acceptable_endings


def _prompt_exists(path: str) -> bool:
    """Production ``prompt_exists`` port for :func:`runtime_bridge_cores.step_or_blocked`.

    Mirrors ``Decision.__post_init__``'s own check (``decision.py:129``)
    exactly (``Path(prompt).is_file()``) — the injected predicate and the
    dataclass invariant agree on what "resolves on disk" means.
    """
    return Path(path).is_file()


def _materialize_decision(
    envelope: _cores.DecisionEnvelope,
    guard_failures: list[str] | None = None,
) -> Decision:
    """Thin residual wrapper around :func:`runtime_bridge_cores.step_or_blocked`
    supplying the production ``prompt_exists`` port (FR-011)."""
    return _cores.step_or_blocked(envelope, guard_failures, prompt_exists=_prompt_exists)


# (action, wp_id, workspace_path, blocked_reason, mission_state) -- the tuple
# :func:`_wp_iteration_action_and_state` returns.
_WpIterationResolution = tuple[str | None, str | None, str | None, str | None, str]


#: Reused across both #2947 short-circuit branches (S1192 — repeated literal).
_MERGED_MISSION_DONE_REASON = "All work packages are done"


def _merged_mission_short_circuit(
    *,
    repo_root: Path,
    mission_slug: str,
    agent: str | None,
    now: str,
    terminal_kind: str,
    owned: OwnedCheckout | None = None,
) -> Decision | None:
    """Committed-authority pre-check (#2947, D8/D9/D13/F5) shared by BOTH
    ``next`` entry points, called BEFORE either selects a workspace or starts
    a run.

    Consumes WP01's :func:`committed_authority.mission_terminal_verdict` —
    the PRIMARY-surface authority (never the coordination checkout) — so a
    merged mission is recognized from committed truth instead of a stale/
    artifact-missing coordination workspace fabricating an unstarted run
    (D9). ``mission_type`` is resolved off the same PRIMARY surface
    (:func:`runtime_bridge_identity._primary_runtime_feature_dir`) — never via workspace selection.

    ``terminal_kind`` lets the two callers diverge on the ONE dimension D13
    requires: :func:`decide_next_via_runtime` passes ``DecisionKind.terminal``
    (matching issue #2947's ``--result success`` repro, and creating NO run
    since this returns before workspace selection / ``get_or_start_run``);
    :func:`query_current_state` passes ``DecisionKind.query`` (query mode is
    structurally ``kind: query`` only — mirrors the finalized-override
    ``mission_state="done"`` precedent, :func:`_build_finalized_override_
    query_decision`). A ``blocked_conflict`` verdict honors the same mode
    split: advancing mode emits ``kind: blocked`` (an actionable blocked
    decision), while query mode emits ``kind: query`` with
    ``mission_state="blocked"`` — preserving the query-mode ``is_query`` /
    ``kind: query`` invariant and matching the finalized-override ``blocked:``
    precedent (never ``kind: blocked`` from a read-only query).

    F5 invariant: returns ``None`` for verdict ``"none"`` so the caller's
    existing behavior is BYTE-IDENTICAL to today (protects the many
    in-flight query/decide fixtures) — the only two verdicts this function
    ever materializes a ``Decision`` for are ``"terminal"`` and
    ``"blocked_conflict"``.

    #3829 item 1: the ``"none"`` fall-through also covers the
    handle-form errors ``mission_terminal_verdict`` declines on
    (traversal-unsafe / ambiguous handles) — the raw path-guard
    ``ValueError`` those handles used to raise FROM THIS SHORT-CIRCUIT
    pre-empted the caller's own typed classification
    (``resolve_handle_to_read_path`` → ``MissionNotFoundError`` /
    read-path code); declining restores the pre-#3825 error shapes
    byte-for-byte.
    """
    from runtime.next.committed_authority import mission_terminal_verdict, primary_surface_dir

    verdict = mission_terminal_verdict(repo_root, mission_slug, owned)
    if verdict == "none":
        return None

    mission_type = get_mission_type(primary_surface_dir(repo_root, mission_slug, owned))
    if verdict == "terminal":
        return _materialize_decision(
            _cores.DecisionEnvelope(
                kind=terminal_kind,
                agent=agent,
                mission_slug=mission_slug,
                mission=mission_type,
                mission_state="done",
                timestamp=now,
                reason=_MERGED_MISSION_DONE_REASON,
            )
        )
    # blocked_conflict — honor the mode: query mode keeps the structural
    # ``kind: query`` invariant (``mission_state="blocked"``, mirroring the
    # finalized-override ``blocked:`` precedent), advancing mode emits an
    # actionable ``kind: blocked``. Field set mirrors the inline blocked
    # emissions; no invented payload shape. The reason carries an operator
    # remediation affordance (#3829 item 2): the fail-closed block is
    # correct, but it previously named no recovery command — an operator
    # seeing ``kind: blocked`` indefinitely had no pointer to the board that
    # shows the straggling WP or to the move-task that resolves it.
    blocked_kind = DecisionKind.query if terminal_kind == DecisionKind.query else DecisionKind.blocked
    return _materialize_decision(
        _cores.DecisionEnvelope(
            kind=blocked_kind,
            agent=agent,
            mission_slug=mission_slug,
            mission=mission_type,
            mission_state="blocked",
            timestamp=now,
            reason=(
                "Merged mission has committed work packages that are not an "
                "acceptable ending (conflict). Inspect the committed board with "
                f"'spec-kitty agent tasks status --mission {mission_slug}' and "
                "resolve the straggling work package(s) — e.g. "
                f"'spec-kitty agent tasks move-task <wp> --to approved --mission {mission_slug}'."
            ),
        )
    )


# advancing-next-board-unification-01M3BGQ0 (#4980, #4975) — the single
# board-authority-backed WP-iteration action selector (NFR-002 / CT-7).
#
# Mirrors query mode's ``_build_finalized_override_query_decision`` exactly:
# the same coord-aware ``status_dir`` (resolved via ``mission_context_for``,
# never the bare ``feature_dir``), the same ``_finalized_task_board_
# override_step`` step derivation, and the same per-step WP resolution
# authority (``preview_claimable_wp`` for implement; the canonical
# ``_find_first_wp_by_lane`` for_review reader for review — C-003 forbids
# minting a fifth lane reader). ``_build_wp_iteration_decision`` and
# ``_map_wp_step_decision`` both route through this instead of the bare
# ``_state_to_action(step_id, feature_dir, ...)`` call that #4980/#4975 are
# two faces of (research.md's parallel-authority inventory items #1/#2).
@dataclasses.dataclass(frozen=True)
class _WpBoardAction:
    """Result of the single board-authority WP-iteration action selector.

    Exactly one of three shapes:

    * **dispatch** — ``action``/``wp_id``/``workspace_path`` set,
      ``blocked_reason`` ``None``.
    * **blocked floor** — ``blocked_reason`` set (a CT-4 runnable recovery
      command embedded in backticks), ``action``/``wp_id``/``workspace_path``
      ``None``.
    * **decline** — every field ``None``. The board authority has no
      finalized-board opinion yet (pre-finalize bootstrap, or the board says
      ``accept``/``done`` — that transition is owned by the leave-step
      boolean, not this selector). The caller falls back to
      :func:`_state_to_action` unchanged (FR-006).
    """

    board_step: str | None
    action: str | None
    wp_id: str | None
    workspace_path: str | None
    blocked_reason: str | None


_WP_BOARD_DECLINE = _WpBoardAction(board_step=None, action=None, wp_id=None, workspace_path=None, blocked_reason=None)


def _inspect_board_recovery_command(mission_slug: str) -> str:
    """CT-4's runnable recovery command for the generic 'inspect the board'
    blocked arms (``no_actionable_wp`` / ``review_in_progress`` / a
    claimable-WP race)."""
    return f"spec-kitty agent tasks status --mission {mission_slug}"


def _wp_blocked_action(board_step: str | None, reason: str) -> _WpBoardAction:
    return _WpBoardAction(board_step=board_step, action=None, wp_id=None, workspace_path=None, blocked_reason=reason)


def _wp_task_surface_error(task_board_dir: Path, status_dir: Path, mission_slug: str) -> str | None:
    """Return the canonical task-read error for any WP present in status state.

    Validate done WPs too: progress totals and terminal counts are derived
    from primary task files, so skipping a missing done task could erase it
    from the board and make the remaining tasks appear complete. Canceled WPs
    are skipped: canceling is the recorded way to retire a work package whose
    task file was removed on purpose, and a canceled WP never counts toward
    completion.
    """
    from runtime.next.prompt_builder import read_wp_task
    from specify_cli.status import CanonicalStatusNotFoundError, Lane, get_all_wp_lanes

    try:
        wp_lanes = get_all_wp_lanes(status_dir)
    except CanonicalStatusNotFoundError:
        return None

    tasks_dir = task_board_dir / "tasks"
    for wp_id, lane in sorted(wp_lanes.items()):
        if lane == Lane.CANCELED:
            continue
        try:
            read_wp_task(tasks_dir, wp_id, mission_slug)
        except (FileNotFoundError, ValueError) as exc:
            return str(exc)
    return None


def _wp_dispatch_action(board_step: str, action: str, wp_id: str, workspace_path: str) -> _WpBoardAction:
    return _WpBoardAction(board_step=board_step, action=action, wp_id=wp_id, workspace_path=workspace_path, blocked_reason=None)


def _resolve_wp_board_implement_action(
    mission_slug: str,
    repo_root: Path,
    task_board_dir: Path,
    status_dir: Path,
    *,
    owned: OwnedCheckout | None = None,
) -> _WpBoardAction:
    """CT-3 / FR-003: implement-branch WP resolution, mirroring query mode's
    ``_build_finalized_override_query_decision`` exactly (the same
    ``preview_claimable_wp`` dependency-aware authority, the same coord-aware
    ``status_dir``). A ``None`` claimable WP (e.g. the only planned-lane WP
    is dependency-walled) is a genuine blocked floor here — FR-005 forbids a
    WP-less ``kind=step`` dispatch."""
    from runtime.next.discovery import preview_claimable_wp
    from specify_cli.workspace.context import resolve_workspace_for_wp

    preview = preview_claimable_wp(task_board_dir, status_dir=status_dir)
    if preview.wp_id is None:
        reason = preview.selection_reason or "no claimable work package"
        return _wp_blocked_action(
            "implement",
            f"{reason}. Inspect the board: `{_inspect_board_recovery_command(mission_slug)}`.",
        )
    workspace_path = str(resolve_workspace_for_wp(repo_root, mission_slug, preview.wp_id, owned=owned).worktree_path)
    return _wp_dispatch_action("implement", "implement", preview.wp_id, workspace_path)


def _resolve_wp_board_review_action(
    mission_slug: str,
    repo_root: Path,
    task_board_dir: Path,
    status_dir: Path,
    *,
    owned: OwnedCheckout | None = None,
) -> _WpBoardAction:
    """CT-2 / FR-001: review-branch WP resolution via the canonical
    ``_find_first_wp_by_lane`` for_review reader (C-003 — no fifth lane
    reader is minted)."""
    from specify_cli.workspace.context import resolve_workspace_for_wp

    wp_id = _find_first_wp_by_lane(task_board_dir, "for_review", status_dir=status_dir)
    if wp_id is None:
        # A race between the board's own for_review probe and this re-read
        # — never a WP-less dispatch (FR-005); fall to the blocked floor.
        return _wp_blocked_action(
            "review",
            f"Board reported a reviewable work package but none was found on re-read. Inspect the board: `{_inspect_board_recovery_command(mission_slug)}`.",
        )
    workspace_path = str(resolve_workspace_for_wp(repo_root, mission_slug, wp_id, owned=owned).worktree_path)
    return _wp_dispatch_action("review", "review", wp_id, workspace_path)


def _resolve_wp_board_action(*, mission_slug: str, repo_root: Path, owned: OwnedCheckout | None = None) -> _WpBoardAction:
    """The single board-authority-backed WP-iteration action selector
    (NFR-002 / CT-7) both ``_build_wp_iteration_decision`` and
    ``_map_wp_step_decision`` consult instead of the bare ``_state_to_action``
    WP-iteration branches.

    Resolves the coord-aware ``status_dir``/``task_board_dir`` via
    ``mission_context_for`` exactly as query mode does (never the bare
    ``feature_dir`` the two callers otherwise hold — that is the #4975
    mechanism) and computes its OWN ``progress`` from the resolved
    ``task_board_dir`` (never a caller-supplied, potentially coord-blind
    ``progress`` — the bootstrap-computed ``ctx.progress`` is ``None`` for a
    coord mission because it is read off the coord-aware ``feature_dir``,
    which carries no ``tasks/``).

    NFR-003 (CT-5): an unmaterialized/deleted coordination surface is caught
    here and turned into a *named* blocked reason — never allowed to
    collapse into the generic ``no_actionable_wp`` floor and never
    substituted with an empty-primary read. ``mission_context_for``'s own
    status-surface derivation silently composes a not-yet-materialized coord
    path rather than raising (a pre-existing, documented "sanctioned
    degrade" distinct from the newer fail-closed policy ADR 2026-09-24-2
    introduced for ``resolve_artifact_surface``/``placement_seam.read_dir``)
    — so this selector probes ``placement_seam.read_dir`` first, purely for
    its raise, before trusting ``mission_context_for``'s directories for the
    real board reads. Mirrors the existing ``placement_seam(repo_root,
    mission_slug).read_dir(...)`` pattern this module already uses for
    ``PRIMARY_METADATA`` (see ``_mission_routes_through_coordination``
    above) — no new resolution mechanism, the canonical fail-closed
    authority applied to one more kind.
    """
    from mission_runtime import ActionContextError, MissionArtifactKind, mission_context_for, placement_seam
    from specify_cli.coordination.surface_resolver import (
        CoordinationBranchDeleted,
        CoordinationWorktreeUnmaterialized,
    )

    try:
        placement_seam(repo_root, mission_slug, owned=owned).read_dir(MissionArtifactKind.STATUS_STATE)
        mission_context = mission_context_for(repo_root, mission_slug, owned=owned)
    except CoordinationWorktreeUnmaterialized as exc:
        # #5113 / FR-014: the branch is present, only the worktree is not yet
        # materialized — the truthful recovery is to materialize it, never to
        # flatten (that arm is `CoordinationBranchDeleted`, handled below).
        # Surface the exception's OWN next_step (the single remedy authority,
        # surface_resolver._compose_next_step) rather than re-composing the
        # materialize command here — matching the sibling arm below, so the
        # `doctor coordination --fix` string has exactly one composer.
        return _wp_blocked_action(
            None,
            f"Coordination surface for mission {mission_slug!r} is not readable ({exc}). {exc.next_step}",
        )
    except CoordinationBranchDeleted as exc:
        # The declared coordination branch itself is gone (never created or
        # deleted) — surface the exception's OWN next_step (flatten guidance),
        # never the "Materialize it" text that only fits the sibling arm above.
        return _wp_blocked_action(
            None,
            f"Coordination surface for mission {mission_slug!r} is not readable ({exc}). {exc.next_step}",
        )
    except ActionContextError:
        # Mission context genuinely cannot be resolved -- decline and let the
        # caller's FR-006 fallback (_state_to_action) produce whatever it
        # would have produced pre-fix; bootstrap already succeeded, so this
        # is not expected on a live advancing call.
        return _WP_BOARD_DECLINE

    task_board_dir = mission_context.artifact(MissionArtifactKind.WORK_PACKAGE_TASK).read_dir
    status_dir = mission_context.artifact(MissionArtifactKind.STATUS_STATE).read_dir
    task_error = _wp_task_surface_error(task_board_dir, status_dir, mission_slug)
    if task_error is not None:
        return _wp_blocked_action(None, task_error)

    progress = _compute_wp_progress(task_board_dir, status_dir=status_dir)
    board_step = _finalized_task_board_override_step(task_board_dir, progress, status_dir=status_dir)

    if board_step is None or board_step in ("accept", "done"):
        return _WP_BOARD_DECLINE
    if board_step.startswith("blocked:"):
        sentinel = board_step.split(":", 1)[1]
        return _wp_blocked_action(
            board_step,
            f"No actionable work package ({sentinel.replace('_', ' ')}). Inspect the board: `{_inspect_board_recovery_command(mission_slug)}`.",
        )
    if board_step == "implement":
        return _resolve_wp_board_implement_action(mission_slug, repo_root, task_board_dir, status_dir, owned=owned)
    if board_step == "review":
        return _resolve_wp_board_review_action(mission_slug, repo_root, task_board_dir, status_dir, owned=owned)
    return _WP_BOARD_DECLINE  # forward-compat: an unrecognized board step declines rather than guesses


def _wp_iteration_action_and_state(
    step_id: str,
    mission_slug: str,
    mission_type: str,
    feature_dir: Path,
    repo_root: Path,
    *,
    owned: OwnedCheckout | None = None,
) -> tuple[str | None, str | None, str | None, str | None, str]:
    """Resolve ``(action, wp_id, workspace_path, blocked_reason,
    mission_state)`` for a WP-iteration step through the single board
    authority (NFR-002 / CT-7), falling back to :func:`_state_to_action`
    only when the board authority has no finalized-board opinion yet
    (FR-006 — bootstrap / pre-finalize behavior preserved byte-for-byte).

    ``blocked_reason`` non-``None`` means the caller MUST emit
    ``kind=blocked`` with this reason instead of a step dispatch (CT-4/CT-5)
    — a board ``blocked:*`` sentinel or a coord-read fail-closed error.

    When the board reports a step different from the stale issued
    ``step_id`` (e.g. board=``implement`` while issued=``review``, the
    #4980 re-dispatch), ``mission_state`` reflects the board's own step —
    matching query mode's ``_build_finalized_override_query_decision``
    (data-model.md's "post-fix required: mission_state = board step").
    """
    board = _resolve_wp_board_action(mission_slug=mission_slug, repo_root=repo_root, owned=owned)
    if board.blocked_reason is not None:
        return None, None, None, board.blocked_reason, step_id
    if board.action is not None:
        return board.action, board.wp_id, board.workspace_path, None, board.board_step or step_id
    action, wp_id, workspace_path = _state_to_action(step_id, mission_slug, feature_dir, repo_root, mission_type, owned=owned)
    return action, wp_id, workspace_path, None, step_id


def _build_wp_iteration_decision(
    step_id: str,
    agent: str,
    mission_slug: str,
    mission_type: str,
    feature_dir: Path,
    repo_root: Path,
    timestamp: str,
    progress: dict[str, Any] | None,
    origin: dict[str, Any],
    run_ref: MissionRunRef,
    guard_failures: list[str] | None = None,
    owned: OwnedCheckout | None = None,
) -> Decision:
    """Build a Decision for WP iteration within a step — routed through the
    single board-authority selector (NFR-002 / CT-7); see
    :func:`_wp_iteration_action_and_state`."""
    action, wp_id, workspace_path, blocked_reason, mission_state = _wp_iteration_action_and_state(
        step_id,
        mission_slug,
        mission_type,
        feature_dir,
        repo_root,
        owned=owned,
    )

    if blocked_reason is not None:
        return _materialize_decision(
            _cores.DecisionEnvelope(
                kind=DecisionKind.blocked,
                agent=agent,
                mission_slug=mission_slug,
                mission=mission_type,
                mission_state=mission_state,
                timestamp=timestamp,
                reason=blocked_reason,
                progress=progress,
                origin=origin,
                run_id=run_ref.run_id,
                step_id=step_id,
            ),
            guard_failures or [],
        )

    if action is None:
        return _materialize_decision(
            _cores.DecisionEnvelope(
                kind=DecisionKind.blocked,
                agent=agent,
                mission_slug=mission_slug,
                mission=mission_type,
                mission_state=mission_state,
                timestamp=timestamp,
                reason=f"No action mapped for step '{step_id}'",
                progress=progress,
                origin=origin,
                run_id=run_ref.run_id,
                step_id=step_id,
            ),
            guard_failures or [],
        )

    prompt_file, prompt_error, prompt_error_code = _build_prompt_or_error(
        action,
        feature_dir,
        mission_slug,
        wp_id,
        agent,
        repo_root,
        mission_type,
        owned=owned,
    )
    # WP06 (FR-006/FR-013) / WP07 (FR-011): step_or_blocked never issues
    # kind=step with an unresolvable prompt_file; see the analogous note in
    # decide_next_via_runtime for why the shared core's hard-coded
    # "prompt_file_not_resolvable" literal is safe for the
    # resolved-but-vanished-by-construction-time race.
    return _materialize_decision(
        _cores.DecisionEnvelope(
            kind=DecisionKind.step,
            agent=agent,
            mission_slug=mission_slug,
            mission=mission_type,
            mission_state=mission_state,
            timestamp=timestamp,
            reason=prompt_error or "no_prompt_template",
            action=action,
            wp_id=wp_id,
            workspace_path=workspace_path,
            prompt_file=prompt_file,
            progress=progress,
            origin=origin,
            run_id=run_ref.run_id,
            step_id=step_id,
            error_code=prompt_error_code,
        ),
        guard_failures or [],
    )


def _build_decision_required_prompt_file(
    decision: NextDecision,
    mission_slug: str,
    repo_root: Path,
    agent: str,
) -> str | None:
    """Best-effort ``decision_required`` prompt build (silently ``None`` on failure).

    Verbatim extraction of ``_map_runtime_decision``'s former inline
    try/except (#2531 WP07/T026 — CC reduction; no behavior change: a failed
    ``build_decision_prompt`` still yields ``prompt_file=None``, same as
    before)."""
    if not decision.question:
        return None
    from runtime.next.prompt_builder import build_decision_prompt

    try:
        _, prompt_path = build_decision_prompt(
            question=decision.question,
            options=decision.options,
            decision_id=decision.decision_id or "unknown",
            mission_slug=mission_slug,
            repo_root=repo_root,
            agent=agent,
        )
        return str(prompt_path)
    except Exception:
        return None


def _map_wp_step_decision(
    *,
    step_id: str,
    agent: str,
    mission_slug: str,
    mission_type: str,
    repo_root: Path,
    feature_dir: Path,
    timestamp: str,
    progress: dict[str, Any] | None,
    origin: dict[str, Any],
    run_id: str | None,
    owned: OwnedCheckout | None = None,
    wp_resolution: _WpIterationResolution | None = None,
) -> Decision:
    """WP-iteration branch of the ``kind="step"`` mapping (#2531 WP07/T026),
    now routed through the single board-authority selector (NFR-002 / CT-7)
    — see :func:`_wp_iteration_action_and_state`. Reached from the
    DAG-advance path (``_map_runtime_decision`` / ``_dn_decision_
    materialize``) whenever the engine just issued a fresh WP-iteration
    step (#4975: the coord implement-dispatch face).

    ``wp_resolution`` is the resolution ``_dn_decision_materialize`` already
    computed BEFORE persisting the advance (T061 step 3); when given, the
    workspace is not resolved a second time."""
    action, wp_id, workspace_path, blocked_reason, mission_state = (
        wp_resolution
        if wp_resolution is not None
        else _wp_iteration_action_and_state(
            step_id,
            mission_slug,
            mission_type,
            feature_dir,
            repo_root,
            owned=owned,
        )
    )
    if blocked_reason is not None:
        return _materialize_decision(
            _cores.DecisionEnvelope(
                kind=DecisionKind.blocked,
                agent=agent,
                mission_slug=mission_slug,
                mission=mission_type,
                mission_state=mission_state,
                timestamp=timestamp,
                reason=blocked_reason,
                progress=progress,
                origin=origin,
                run_id=run_id,
                step_id=step_id,
            )
        )
    if action is None:
        return _materialize_decision(
            _cores.DecisionEnvelope(
                kind=DecisionKind.blocked,
                agent=agent,
                mission_slug=mission_slug,
                mission=mission_type,
                mission_state=mission_state,
                timestamp=timestamp,
                reason=f"No action mapped for WP step '{step_id}'",
                progress=progress,
                origin=origin,
                run_id=run_id,
                step_id=step_id,
            )
        )
    prompt_file, prompt_error, prompt_error_code = _build_prompt_or_error(
        action,
        feature_dir,
        mission_slug,
        wp_id,
        agent,
        repo_root,
        mission_type,
        owned=owned,
    )
    return _materialize_decision(
        _cores.DecisionEnvelope(
            kind=DecisionKind.step,
            agent=agent,
            mission_slug=mission_slug,
            mission=mission_type,
            mission_state=mission_state,
            timestamp=timestamp,
            reason=prompt_error or "prompt_file_not_resolvable",
            action=action,
            wp_id=wp_id,
            workspace_path=workspace_path,
            prompt_file=prompt_file,
            progress=progress,
            origin=origin,
            run_id=run_id,
            step_id=step_id,
            error_code=prompt_error_code,
        )
    )


def _map_non_wp_step_decision(
    *,
    step_id: str | None,
    agent: str,
    mission_slug: str,
    mission_type: str,
    repo_root: Path,
    feature_dir: Path,
    timestamp: str,
    progress: dict[str, Any] | None,
    origin: dict[str, Any],
    run_id: str | None,
    owned: OwnedCheckout | None = None,
) -> Decision:
    """Non-WP branch of the ``kind="step"`` mapping (#2531 WP07/T026).

    Extracted verbatim from ``_map_runtime_decision``'s former non-WP
    triad — template-resolution via ``_state_to_action`` +
    ``_build_prompt_or_error``, collapsed via ``step_or_blocked``."""
    action, wp_id, workspace_path = _state_to_action(
        step_id or "unknown",
        mission_slug,
        feature_dir,
        repo_root,
        mission_type,
        owned=owned,
    )
    prompt_file: str | None = None
    prompt_error: str | None = None
    prompt_error_code: str | None = None
    if action or step_id:
        prompt_file, prompt_error, prompt_error_code = _build_prompt_or_error(
            action or step_id or "unknown",
            feature_dir,
            mission_slug,
            wp_id,
            agent,
            repo_root,
            mission_type,
            owned=owned,
        )
    else:
        prompt_error = "no action and no step_id; cannot resolve prompt"
    return _materialize_decision(
        _cores.DecisionEnvelope(
            kind=DecisionKind.step,
            agent=agent,
            mission_slug=mission_slug,
            mission=mission_type,
            mission_state=step_id or "unknown",
            timestamp=timestamp,
            reason=prompt_error or "no_prompt_template",
            action=action or step_id,
            wp_id=wp_id,
            workspace_path=workspace_path,
            prompt_file=prompt_file,
            progress=progress,
            origin=origin,
            run_id=run_id,
            step_id=step_id,
            error_code=prompt_error_code,
        )
    )


def _map_runtime_decision(
    decision: NextDecision,
    agent: str,
    mission_slug: str,
    mission_type: str,
    repo_root: Path,
    feature_dir: Path,
    timestamp: str,
    progress: dict[str, Any] | None,
    origin: dict[str, Any],
    *,
    owned: OwnedCheckout | None = None,
    wp_resolution: _WpIterationResolution | None = None,
) -> Decision:
    """Convert runtime NextDecision to CLI Decision dataclass.

    Exit-code contract (FR-008):
    - ``kind="terminal"`` → ``DecisionKind.terminal`` → ``next_cmd`` exits 0
    - ``kind="blocked"``  → ``DecisionKind.blocked``  → ``next_cmd`` exits 1
    - ``kind="step"``     → ``DecisionKind.step``     → ``next_cmd`` exits 0

    ``next_cmd.py`` maps the kind to exit code; this function must not change
    the kind semantics. Verified by:
    - ``tests/next/test_next_command_integration.py::TestNextCommandCLI::test_terminal_state_exit_code_zero``
    - ``tests/next/test_next_command_integration.py::TestNextCommandCLI::test_blocked_result_exit_code``

    #2531 WP07/T026: every branch now builds a
    :class:`runtime_bridge_cores.DecisionEnvelope` and materializes it via
    :func:`runtime_bridge_cores.step_or_blocked` (FR-011); the WP-step and
    non-WP-step branches (the former CC-heaviest part of this function) are
    extracted to :func:`_map_wp_step_decision` / :func:`_map_non_wp_step_
    decision` so this dispatcher stays a flat kind-lookup.
    """
    step_id = decision.step_id
    run_id = decision.run_id

    if decision.kind == DecisionKind.terminal:
        return _materialize_decision(
            _cores.DecisionEnvelope(
                kind=DecisionKind.terminal,
                agent=agent,
                mission_slug=mission_slug,
                mission=mission_type,
                mission_state="done",
                timestamp=timestamp,
                reason=decision.reason or "Mission complete",
                progress=progress,
                origin=origin,
                run_id=run_id,
                step_id=step_id,
            )
        )

    if decision.kind == DecisionKind.blocked:
        return _materialize_decision(
            _cores.DecisionEnvelope(
                kind=DecisionKind.blocked,
                agent=agent,
                mission_slug=mission_slug,
                mission=mission_type,
                mission_state=step_id or "unknown",
                timestamp=timestamp,
                reason=decision.reason,
                progress=progress,
                origin=origin,
                run_id=run_id,
                step_id=step_id,
            )
        )

    if decision.kind == DecisionKind.decision_required:
        prompt_file = _build_decision_required_prompt_file(decision, mission_slug, repo_root, agent)
        return _materialize_decision(
            _cores.DecisionEnvelope(
                kind=DecisionKind.decision_required,
                agent=agent,
                mission_slug=mission_slug,
                mission=mission_type,
                mission_state=step_id or "unknown",
                timestamp=timestamp,
                reason=decision.reason or "Decision required",
                progress=progress,
                origin=origin,
                run_id=run_id,
                step_id=step_id,
                decision_id=decision.decision_id,
                input_key=decision.input_key,
                question=decision.question,
                options=decision.options,
                prompt_file=prompt_file,
            )
        )

    # kind == "step"
    if step_id and _is_wp_iteration_step(step_id):
        return _map_wp_step_decision(
            step_id=step_id,
            agent=agent,
            mission_slug=mission_slug,
            mission_type=mission_type,
            repo_root=repo_root,
            feature_dir=feature_dir,
            timestamp=timestamp,
            progress=progress,
            origin=origin,
            run_id=run_id,
            owned=owned,
            wp_resolution=wp_resolution,
        )

    return _map_non_wp_step_decision(
        step_id=step_id,
        agent=agent,
        mission_slug=mission_slug,
        mission_type=mission_type,
        repo_root=repo_root,
        feature_dir=feature_dir,
        timestamp=timestamp,
        progress=progress,
        origin=origin,
        run_id=run_id,
        owned=owned,
    )
