"""Bridge between CLI ``decide_next()`` and the CLI-internal ``_internal_runtime`` engine.

The runtime is now internalized as part of mission
``shared-package-boundary-cutover-01KQ22DS``; production code no longer imports
the standalone ``spec-kitty-runtime`` PyPI package.

This module owns the advance path of ``spec-kitty next``
(``decide_next_via_runtime`` and its ``_dn_*`` phases):

1. Starting or loading a mission run (persisted under .kittify/runtime/)
2. Delegating step planning to the runtime DAG planner
3. Handling WP-level iteration within "implement" and "review" steps
4. Enforcing CLI-level guards (artifact checks, WP status)
5. Preserving the existing JSON output contract

The read path (query mode, answer mode) lives in ``runtime_bridge_query``; the
public names CLI callers read here are plain re-exports of the seams' own
objects (see the re-export block below).

Underscore-prefixed functions in the ``runtime_bridge_*`` seam modules that the
bridge calls are a package-internal seam API, not module-private.

Run state is stored locally under ``.kittify/runtime/runs/<run_id>/``.
A tracked-mission-to-run compatibility index currently lives at
``.kittify/runtime/feature-runs.json``.
"""

# ─────────────────────────────────────────────────────────────────────────────
# Seam map (#2531 decomposition, #2561 delegate retirement, #2560 split).
#
# This module keeps the advance path, the CLI guard composition
# (``_check_cli_guards``) and the owned-coordination workspace helpers
# (``_resolve_owned_coordination_workspace`` /
# ``_is_transient_git_worktree_contention``, imported from here by
# ``specify_cli.coordination.coord_seed``). Everything else lives in one
# owning seam under ``runtime/next/``; the bridge calls each name on its seam
# (``_<seam>.<name>``) and keeps no forwarder, so a test patches a name on
# the seam that owns it:
#
#   runtime_bridge_query.py             query mode (read) + answer mode (write)
#   runtime_bridge_decision_mapping.py  NextDecision -> Decision mapping, the
#                                       WP-board / WP-iteration selector, the
#                                       merged / finalized-board short-circuits
#   runtime_bridge_decision_log.py      the coordination-aware decision-log
#                                       wrapper (_wrap_with_decision_git_log)
#   runtime_bridge_guards.py            guard facts + the WP-advance guard
#   runtime_bridge_engine.py            sole home of _internal_runtime engine /
#                                       planner private access (FR-013)
#   runtime_bridge_composition.py       composition dispatch + composed guard
#   runtime_bridge_io.py                narrow I/O ports (run index, template
#                                       discovery, run lifecycle, fact port)
#   runtime_bridge_identity.py          coord-branch / mission-ULID / feature-dir
#                                       resolution (leaf)
#   runtime_bridge_retrospective.py     retrospective / learning capture
#   runtime_bridge_cores.py             pure leaves: tasks.md parse family,
#                                       guard inversion, DecisionEnvelope
#
# RULES (do NOT regress):
#   * No ``runtime_bridge_*`` seam imports this module, at module scope or
#     deferred (tests/runtime/test_runtime_bridge_query_seam_layout.py), and
#     the bridge defines, exposes and loads no seam-owned name
#     (tests/runtime/test_bridge_no_compat_delegates.py).
#   * Never reach into ``_internal_runtime.engine`` / ``.planner`` directly
#     from this module — go through ``runtime_bridge_engine`` (arch-guarded,
#     see ``tests/runtime/test_bridge_engine.py``).
#   * ``__all__`` (below) covers the 8 public names only (governs
#     ``import *``).
#
# De-godding effort: https://github.com/spec-kitty/spec-kitty/issues/2531
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import dataclasses
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from kernel.clock import now_utc_iso

from runtime.next._internal_runtime import (
    MissionRunRef,
    NextDecision,
    next_step as runtime_next_step,
)
from runtime.next import runtime_bridge_composition as _composition
from runtime.next import runtime_bridge_cores as _cores
from runtime.next import runtime_bridge_decision_log as _decision_log
from runtime.next import runtime_bridge_decision_mapping as _mapping
from runtime.next import runtime_bridge_engine as _engine_adapter
from runtime.next import runtime_bridge_guards as _guards
from runtime.next import runtime_bridge_identity as _identity_seam
from runtime.next import runtime_bridge_io as _io_seam

# Public names kept for callers outside this package (CLI modules look them up
# here); they are the very same objects the owning seams define. Runtime-internal
# calls go through the owning seam (``_io_seam.get_or_start_run(...)``), so patch
# the seam to intercept the runtime's own calls; patching these names here only
# affects the CLI callers that import them from the bridge.
from runtime.next.runtime_bridge_decision_log import DecisionGitLogUnavailable
from runtime.next.runtime_bridge_io import build_operational_context_for_claim, get_or_start_run
from runtime.next.runtime_bridge_query import (
    MissionNotFoundError,
    QueryModeValidationError,
    answer_decision_via_runtime,
    query_current_state,
)
from runtime.next import runtime_bridge_retrospective as _retrospective_seam

# The bridge keeps no forwarders or self-aliases for names the seams own: a
# parse-family, retrospective or composition-input helper is called on its
# owning seam (``_cores`` / ``_retrospective_seam`` / ``_composition``) at each
# call site below, and a test patches it there.

from specify_cli.core.constants import MISSION_TYPE_SOFTWARE_DEV
from specify_cli.mission import get_mission_type
from specify_cli.missions._read_path_resolver import MissionSelectorAmbiguous
from specify_cli.status import CanonicalStatusNotFoundError
from runtime.next.decision import (
    Decision,
    DecisionKind,
    _build_prompt_or_error,
    _build_prompt_safe,
    _compute_wp_progress,
    _state_to_action,
)
from runtime.next._internal_runtime.events import RuntimeEventEmitter, runtime_emitter_for_mission, seed_runtime_emitter
from mission_runtime import ActionContextError, OwnedCheckout, OwnedRefusalCode

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

# MISSION_RUNTIME_YAML / MISSION_YAML moved to runtime_bridge_io.py (T017 —
# their only residual users, the discovery cluster, moved with them).


def _resolve_owned_coordination_workspace(
    workspace_type: Any,
    repo_root: Path,
    mission_slug: str,
    mid8: str,
) -> Path:
    """Materialize after transient shared git-worktree registry contention.

    Two distinct owned missions may reach ``git worktree add`` concurrently.
    Their filesystem destinations do not overlap, but git serializes updates to
    the shared worktree registry.  Retry only that subprocess failure; durable
    failures still surface unchanged once the bounded window is spent: at
    most 20 attempts with a linear back-off of 0.05 s x 1..19, i.e. a
    worst case of about 9.5 s of sleeping.  This avoids
    a second persistent lock file and therefore cannot leak ownership locks.
    """
    import subprocess
    import time

    attempts = 20
    for attempt in range(attempts):
        try:
            resolved: Path = workspace_type.resolve(repo_root, mission_slug, mid8)
            return resolved
        except subprocess.CalledProcessError as exc:
            if not _is_transient_git_worktree_contention(exc):
                raise
            if attempt == attempts - 1:
                raise
            time.sleep(0.05 * (attempt + 1))
    raise AssertionError("unreachable coordination workspace retry tail")


def _is_transient_git_worktree_contention(
    exc: Any,
) -> bool:
    """Recognize Git's shared worktree-registry contention diagnostics.

    Two kinds are transient: lock contention, and a sibling registry entry
    caught mid-mutation by another process (#5894).
    """
    if getattr(exc, "returncode", None) != 128:
        return False
    output = "\n".join(str(value) for value in (getattr(exc, "stderr", ""), getattr(exc, "stdout", "")) if value).casefold()
    return _is_git_lock_contention(output) or _is_sibling_registry_entry_in_flight(output)


def _is_git_lock_contention(output: str) -> bool:
    """Git's lock-file diagnostics (another process holds the lock)."""
    lock_exists = "file exists" in output and ("config.lock" in output or ("unable to create" in output and ".lock" in output))
    return lock_exists or ("could not lock config file" in output and "file exists" in output) or ("another git process" in output and "lock" in output)


# A shared-registry entry path: ``.../worktrees/<id>``. The lookbehind keeps
# this repository's own ``.worktrees/<slug>`` checkouts from matching.
_REGISTRY_ENTRY = r"(?<!\.)/worktrees/[^/'\s]+"
_EMPTY_COMMONDIR = re.compile(_REGISTRY_ENTRY + r"/commondir: success\b")
_VANISHED_ENTRY = re.compile(r"invalid path '[^']*" + _REGISTRY_ENTRY + r"/?'")


def _is_sibling_registry_entry_in_flight(output: str) -> bool:
    """A sibling ``.git/worktrees/<id>`` entry another process is mutating.

    ``git worktree list`` reads every registered entry. ``git worktree add``
    writes the entry's ``commondir`` last (truncate, then write), so a reader
    can find it zero bytes long (``failed to read .../worktrees/<id>/commondir:
    Success``); ``git worktree remove`` deletes the entry directory under a
    reader (``Invalid path '.../worktrees/<id>'``). Both are the normal
    in-flight state of another process's entry. Each wording must name a
    registry entry on the same match: a real read failure (``Permission
    denied``, ``Is a directory``) or a path outside the registry is durable.
    An entry that stays broken still refuses once the bounded retry is spent.
    """
    normalized = output.replace("\\", "/")
    return bool(_EMPTY_COMMONDIR.search(normalized) or _VANISHED_ENTRY.search(normalized))


# ---------------------------------------------------------------------------
# Feature → Run index — owned by runtime_bridge_io.py (T017).
#
# tasks.md parse family — bodies moved to runtime_bridge_cores.py (#2531
# WP06, T021; verbatim, zero-dependency pure leaf). ``TASKS_GLOB`` and the
# WP-iteration step set are owned by runtime_bridge_decision_mapping.py
# (#2560); the guards below read them there.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Guard evaluation (CLI-level, not runtime-level)
# ---------------------------------------------------------------------------



def _check_cli_guards(
    step_id: str,
    feature_dir: Path,
    *,
    mission_family: str | None = None,
    repo_root: Path | None = None,
    owned: OwnedCheckout | None = None,
) -> list[str]:
    """Evaluate the CLI guards for ``step_id`` and return the failures.

    Gathers an :func:`runtime_bridge_io.gather_artifact_presence` snapshot and
    folds it through :func:`runtime_bridge_cores.evaluate_guards_strict`, which
    raises for an unregistered mission family. ``wp_advance_ready`` is not part
    of the gathered snapshot: for ``implement``/``review`` it is read here from
    :func:`runtime_bridge_guards._should_advance_wp_step` and set on the snapshot.

    ``mission_family`` is supplied by runtime paths that already resolved the
    primary-anchored mission type. Direct callers may omit it to preserve the
    legacy feature-dir lookup behavior.

    ``repo_root`` (#3704 WP03, FR-003) is forwarded to
    :func:`runtime_bridge_io.gather_artifact_presence` for org-tier
    ``expected-artifacts.yaml`` resolution (#3704 WP02, FR-008); defaults to
    ``None`` (built-in tree only — today's exact behavior for every existing
    caller that does not yet pass a real ``repo_root``).

    Returns list of failure descriptions; empty list means all guards pass.
    """
    mission_family = mission_family if mission_family is not None else get_mission_type(feature_dir)
    snapshot = _io_seam.gather_artifact_presence(
        feature_dir,
        mission_family=mission_family,
        step_id=step_id,
        repo_root=repo_root,
        owned=owned,
    )
    if step_id in ("implement", "review"):
        # Intentionally NOT anchored (no repo_root=/mission_slug= forwarded), even
        # though repo_root is in scope above for gather_artifact_presence: this call
        # is reachable only from _dn_dependency_gate's WP-iteration branch (#3884
        # INT-001), and only AFTER that branch's own anchored _should_advance_wp_step
        # call (repo_root=repo_root, mission_slug=mission_slug) already returned
        # True for the identical (step_id, feature_dir) — see the "All WPs done for
        # this step" comment at its call site. Do not "fix" this by anchoring it; if
        # phase ordering ever changes so this can be reached with WPs still pending,
        # this needs a repo_root=/mission_slug= forward of its own, mirroring
        # _dn_dependency_gate's call, not a silent carry-forward assumption.
        snapshot = dataclasses.replace(snapshot, wp_advance_ready=_guards._should_advance_wp_step(step_id, feature_dir))
    return _cores.evaluate_guards_strict(snapshot)


# ---------------------------------------------------------------------------
# Composition dispatch (WP02 / mission software-dev-composition-rewrite-01KQ26CY)
# ---------------------------------------------------------------------------
#
# The cluster lives in ``runtime_bridge_composition.py`` (#2531 WP08) — see
# that module's docstring for the constraints (C-001/C-002/C-003/C-008) that
# govern it. The bridge reaches it as ``_composition.<name>``; it keeps no
# forwarder for any of the cluster's names (#2561).


# Single-dispatch invariant (FR-001 / phase6-composition-stabilization-01KQ2JAS):
# After a composition-backed software-dev action succeeds, run state must still
# advance through the next public step — but the legacy ``runtime_next_step``
# DAG dispatch handler MUST NOT be invoked for the same action attempt. The
# advancement itself is owned by
# ``runtime_bridge_engine.advance_run_state_after_composition``.
#
# ---------------------------------------------------------------------------
# Main bridge functions
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Decision-builder residual (#2531 WP07, FR-011) — every ``Decision(...)``
# construction below is routed through ``runtime_bridge_cores.step_or_
# blocked`` over a ``runtime_bridge_cores.DecisionEnvelope`` by
# ``runtime_bridge_decision_mapping._materialize_decision`` (#2560), which
# supplies the one genuinely I/O-bearing dependency the pure core needs (the
# step branch's on-disk prompt-file check). Callers thread the
# non-deterministic fields (timestamp/run_id/decision_id) — the core itself
# never stamps them (NFR-003).
# ---------------------------------------------------------------------------


def _primary_mission_is_completed(primary_metadata_dir: Path) -> bool:
    """Return whether the PRIMARY checkout proves the mission is MERGED.

    Deliberately gated on the merge marker alone (squad pass 1 on PR #845):
    ``is_mission_completed`` is also True for an unmerged mission whose WPs are
    all terminal, and short-circuiting there skips the final advance that
    appends ``MissionRunCompleted`` and runs the retrospective completion gate.
    Fail-closed and non-raising: a corrupt primary ``meta.json``
    (``MissionMetaReadError``) reads as not-merged.
    """
    from specify_cli.core.paths import MissionMetaReadError
    from specify_cli.status import StoreError, is_mission_merged

    if not (primary_metadata_dir / "meta.json").is_file():
        return False
    try:
        return bool(is_mission_merged(primary_metadata_dir))
    except (StoreError, MissionMetaReadError):
        return False


@dataclasses.dataclass(frozen=True)
class DecideNextContext:
    """Frozen value carrier threading ``decide_next_via_runtime``'s shared
    locals through its four-phase early-return chain (FR-010,
    data-model.md §DecideNextContext): bootstrap -> dependency-gate ->
    composition-dispatch -> decision-materialize.

    Populated once by the bootstrap phase; carries no I/O of its own. This
    is an internal residual type — never re-exported, not a new public
    surface (NFR-004) — so the ``decision.py:428`` lazy edge to the
    orchestrator stays lazy (C-007).
    """

    agent: str
    mission_slug: str
    result: str
    repo_root: Path
    feature_dir: Path
    now: str
    mission_type: str
    sync_emitter: RuntimeEventEmitter
    emitter_for_engine: Any
    origin: dict[str, Any]
    progress: dict[str, int | float] | None
    run_ref: MissionRunRef
    run_dir: Path
    current_step_id: str | None
    # owned-checkout-lifecycle-authority WP11 (FR-009): the validated
    # ownership fact, when this call runs under an owned checkout. ``None``
    # for every non-owned mission — the historical, byte-identical path.
    owned: OwnedCheckout | None = None


def _owned_coordination_unavailable_decision(agent: str, mission_slug: str, mission_type: str, now: str, exc: BaseException) -> Decision:
    """The typed ``blocked`` Decision of an unavailable owned coordination workspace."""
    return _mapping._materialize_decision(
        _cores.DecisionEnvelope(
            kind=DecisionKind.blocked,
            agent=agent,
            mission_slug=mission_slug,
            mission=mission_type,
            mission_state="unknown",
            timestamp=now,
            reason=(
                f"Coordination worktree registry is unavailable for mission {mission_slug!r} ({exc}). "
                "Try 'git worktree prune' or 'spec-kitty doctor coordination --fix'."
            ),
            error_code=OwnedRefusalCode.OWNED_COORDINATION_WORKSPACE_UNAVAILABLE.value,
        )
    )


def _dn_bootstrap(
    agent: str,
    mission_slug: str,
    result: str,
    repo_root: Path,
    *,
    owned: OwnedCheckout | None = None,
) -> tuple[DecideNextContext | None, Decision | None]:
    """Phase 1/4 of ``decide_next_via_runtime`` (FR-010) — resolve
    feature/mission/run and build the shared :class:`DecideNextContext`.

    Unlike the other three phases this one cannot accept a
    ``DecideNextContext`` as input (there is nothing to thread yet), so its
    signature is the raw entry params in, ``(ctx, decision)`` out: exactly
    one of the pair is non-``None``. A non-``None`` ``Decision`` means
    bootstrap itself short-circuited (feature dir missing / run failed to
    start) and the caller must return it immediately without running the
    remaining phases.
    """
    is_owned_call = owned is not None

    if not is_owned_call:
        feature_dir = _identity_seam._resolve_runtime_feature_dir(repo_root, mission_slug)
        primary_metadata_dir: Path | None = _identity_seam._primary_runtime_feature_dir(repo_root, mission_slug)
    else:
        from mission_runtime import MissionArtifactKind, mission_context_for

        try:
            mission_context = mission_context_for(
                repo_root,
                mission_slug,
                owned=owned,
                tolerate_unmaterialized_coord=True,  # FR-022: a declared-but-not-yet-created coordination worktree is read/materialised, not refused
            )
        except ActionContextError as exc:
            if not _decision_log._is_owned_coordination_unavailable(exc):
                raise
            return None, _owned_coordination_unavailable_decision(agent, mission_slug, "unknown", now_utc_iso(), exc)
        status_dir = mission_context.artifact(MissionArtifactKind.STATUS_STATE).read_dir
        primary_metadata_dir = mission_context.artifact(MissionArtifactKind.PRIMARY_METADATA).read_dir
        feature_dir = status_dir if status_dir.is_dir() else primary_metadata_dir
    now = now_utc_iso()

    if not feature_dir.is_dir():
        return None, _mapping._materialize_decision(
            _cores.DecisionEnvelope(
                kind=DecisionKind.blocked,
                agent=agent,
                mission_slug=mission_slug,
                mission="unknown",
                mission_state="unknown",
                timestamp=now,
                reason=f"Feature directory not found: {feature_dir}",
            )
        )

    # ``meta.json`` (the mission-type source) lives on the topology-BLIND PRIMARY
    # checkout; the coordination worktree's sparse policy excludes it. Reading the
    # type off the coord-aware ``feature_dir`` yields an empty meta -> the neutral
    # ``""`` from ``get_mission_type`` (post-#883 no software-dev default), which
    # then breaks runtime template resolution. Anchor the type read on the primary
    # dir, mirroring ``runtime_bridge_decision_log._mission_routes_through_coordination`` (FR-001).
    from mission_runtime import MissionArtifactKind, placement_seam  # noqa: PLC0415

    mission_type = get_mission_type(
        placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.PRIMARY_METADATA) if primary_metadata_dir is None else primary_metadata_dir
    )
    if primary_metadata_dir is not None and _primary_mission_is_completed(primary_metadata_dir):
        return None, _mapping._materialize_decision(
            _cores.DecisionEnvelope(
                kind=DecisionKind.terminal,
                agent=agent,
                mission_slug=mission_slug,
                mission=mission_type,
                mission_state="done",
                timestamp=now,
                reason="Mission is already completed",
            )
        )
    # E3 (#3929): register the runtime-moment producer at this entry, never while
    # ``specify_cli.status`` imports (that re-enters ``runtime.next`` mid-import).
    from specify_cli.status import ensure_runtime_moment_producer  # noqa: PLC0415

    ensure_runtime_moment_producer()
    sync_emitter = runtime_emitter_for_mission(
        feature_dir=feature_dir,
        mission_slug=mission_slug,
        mission_type=mission_type,
    )
    # Root discipline (contracts/owned-checkout-carrier.md §7): callees that
    # are not yet owned-aware receive ``owned.owned_root`` in the root
    # argument they already have — the run store, the lifecycle store,
    # composition policy and git cwd all stay at P for an owned mission,
    # preserving today's owned behaviour.
    config_root = owned.owned_root if owned is not None else repo_root

    # Wrap with DecisionGitLog so decision events are durably committed to
    # the coordination branch (spec-kitty #1546, FR-001–FR-005).
    from specify_cli.coordination.workspace import CoordinationWorkspaceUnavailable

    try:
        if not is_owned_call:
            emitter_for_engine: Any = _decision_log._wrap_with_decision_git_log(sync_emitter, mission_slug, repo_root)
        else:
            emitter_for_engine = _decision_log._wrap_with_decision_git_log(
                sync_emitter,
                mission_slug,
                repo_root,
                owned=owned,
            )
    except (CoordinationWorkspaceUnavailable, ActionContextError) as exc:
        # #4867 / FR-012 / O8: an owned caller gets a typed ``blocked``
        # decision instead of an opaque ``fatal: ... commondir: Success``
        # escaping as a Python traceback. The transient-lock retry already
        # ran inside ``_resolve_owned_coordination_workspace`` — reaching
        # here means the failure is durable. WP04's
        # ``ActionContextError(OWNED_COORDINATION_WORKSPACE_UNAVAILABLE)`` (an
        # unmaterialized surface read) maps identically; any other
        # ``ActionContextError`` is not ours to translate.
        if not _decision_log._is_owned_coordination_unavailable(exc):
            raise
        return None, _owned_coordination_unavailable_decision(agent, mission_slug, mission_type, now, exc)

    # Resolve origin info
    origin: dict[str, Any] = {}
    try:
        from specify_cli.runtime.resolver import resolve_mission as resolve_mission_path

        mission_result = resolve_mission_path(mission_type, config_root)
        origin = {
            "mission_tier": getattr(mission_result.tier, "value", str(mission_result.tier)),
            "mission_path": str(mission_result.path.parent),
        }
    except FileNotFoundError:
        origin = {"mission_tier": "unknown", "mission_path": "unknown"}

    progress = _compute_wp_progress(feature_dir)

    # Get or start runtime run (before result handling so failed/blocked
    # decisions include canonical run_id, step_id, and mission_state)
    try:
        run_ref = _io_seam.get_or_start_run(mission_slug, config_root, mission_type, emitter=emitter_for_engine, owned=owned)
    except Exception as exc:
        return None, _mapping._materialize_decision(
            _cores.DecisionEnvelope(
                kind=DecisionKind.blocked,
                agent=agent,
                mission_slug=mission_slug,
                mission=mission_type,
                mission_state="unknown",
                timestamp=now,
                reason=f"Failed to start/load runtime run: {exc}",
                progress=progress,
                origin=origin,
            )
        )

    run_dir = Path(run_ref.run_dir)

    # Read current run state
    try:
        snapshot = _engine_adapter._read_snapshot(run_dir)
        current_step_id = snapshot.issued_step_id
    except Exception:
        current_step_id = None
    else:
        seed_runtime_emitter(sync_emitter, snapshot)

    # FR-017: populate the runtime OperationalContext at the `next` decision
    # boundary via the extracted helper (keeps the bootstrap phase flat). The
    # builder is read-only — it never allocates a worktree or emits a status
    # event (NFR-004).
    operational_context = _io_seam._build_operational_context_for_decision(
        agent=agent,
        run_ref=run_ref,
        feature_dir=feature_dir,
        repo_root=config_root,
        step_id=current_step_id,
        mission_state=current_step_id,
    )
    logger.debug(
        "decide_next operational context: model=%s profile=%s role=%s activity=%s",
        operational_context.active_model,
        operational_context.active_profile,
        operational_context.active_role,
        operational_context.current_activity,
    )

    return (
        DecideNextContext(
            agent=agent,
            mission_slug=mission_slug,
            result=result,
            repo_root=repo_root,
            feature_dir=feature_dir,
            now=now,
            mission_type=mission_type,
            sync_emitter=sync_emitter,
            emitter_for_engine=emitter_for_engine,
            origin=origin,
            progress=progress,
            run_ref=run_ref,
            run_dir=run_dir,
            current_step_id=current_step_id,
            owned=owned,
        ),
        None,
    )


def _run_is_untouched(run_dir: Path) -> bool:
    """True when the persisted run has never advanced: no completed step and no
    decision, pending or answered (query mode's initial-step predicate). An
    unreadable or malformed snapshot is NOT untouched, so the caller keeps its existing path."""
    try:
        snapshot = _engine_adapter._read_snapshot(run_dir)
        return not snapshot.completed_steps and not snapshot.pending_decisions and not snapshot.decisions
    except Exception:
        return False


def _dn_finalized_board_override(ctx: DecideNextContext) -> Decision | None:
    """Front phase of ``decide_next_via_runtime`` (#5310) — advance first-contact
    parity with query mode.

    Query mode applies the finalized-board override at the top of
    ``_query_dispatch_decision``; advance used to reach the board only once the
    persisted run already sat on a WP-iteration step, so a first-contact advance
    against a finalized board booted ``discovery`` and walked the DAG from its
    first step. This phase consults the SAME board authority
    (:func:`_resolve_wp_board_action`; never a re-derived claimability) before
    the DAG phases, for an advancing ``success`` result against an *untouched*
    run (nothing completed, no decisions: the same "never advanced" predicate
    query mode uses for its initial-step branch). A run that already walked the
    DAG owns its own progression (``_dn_dependency_gate`` /
    ``_dn_composition_dispatch``); pre-empting it would leave the run state
    behind the decision it issued.

    A board dispatch (``implement``/``review``) or a named ``blocked:*`` verdict
    is materialized the way the WP-iteration path does; every other board answer
    (decline for accept/done/no finalized board, coord/task-surface errors) falls
    through unchanged so pre-finalize and terminal behaviour stay byte-identical.
    """
    if ctx.result != "success" or not _run_is_untouched(ctx.run_dir):
        return None
    board = _mapping._resolve_wp_board_action(mission_slug=ctx.mission_slug, repo_root=ctx.repo_root, owned=ctx.owned)
    if board.action is not None and board.board_step is not None:
        return _mapping._build_wp_iteration_decision(
            board.board_step,
            ctx.agent,
            ctx.mission_slug,
            ctx.mission_type,
            ctx.feature_dir,
            ctx.repo_root,
            ctx.now,
            ctx.progress,
            ctx.origin,
            ctx.run_ref,
            owned=ctx.owned,
        )
    if board.blocked_reason is not None and board.board_step is not None and board.board_step.startswith("blocked:"):
        return _mapping._materialize_decision(
            _cores.DecisionEnvelope(
                kind=DecisionKind.blocked,
                agent=ctx.agent,
                mission_slug=ctx.mission_slug,
                mission=ctx.mission_type,
                mission_state="blocked",
                timestamp=ctx.now,
                reason=board.blocked_reason,
                progress=ctx.progress,
                origin=ctx.origin,
                run_id=ctx.run_ref.run_id,
            )
        )
    return None


def _dn_dependency_gate(ctx: DecideNextContext) -> Decision | None:
    """Phase 2/4 of ``decide_next_via_runtime`` (FR-010) — the
    dependency/guard gate: the WP-iteration stay-in-step check (plus its
    on-advance guard check), and the non-WP-step guard check. Returns a
    blocked/step ``Decision`` when a guard holds the run in place, else
    ``None`` to fall through to composition-dispatch.
    """
    agent = ctx.agent
    mission_slug = ctx.mission_slug
    mission_type = ctx.mission_type
    feature_dir = ctx.feature_dir
    repo_root = ctx.repo_root
    owned = ctx.owned
    now = ctx.now
    progress = ctx.progress
    origin = ctx.origin
    run_ref = ctx.run_ref
    current_step_id = ctx.current_step_id

    # WP iteration check: if we're on a WP step and WPs remain, don't advance runtime
    if ctx.result == "success" and current_step_id and _mapping._is_wp_iteration_step(current_step_id):
        try:
            should_advance = _guards._should_advance_wp_step(current_step_id, feature_dir, repo_root=repo_root, mission_slug=mission_slug, owned=owned)
        except CanonicalStatusNotFoundError as exc:
            return _mapping._materialize_decision(
                _cores.DecisionEnvelope(
                    kind=DecisionKind.blocked,
                    agent=agent,
                    mission_slug=mission_slug,
                    mission=mission_type,
                    mission_state=current_step_id,
                    timestamp=now,
                    reason=str(exc),
                    progress=progress,
                    origin=origin,
                    run_id=run_ref.run_id,
                    step_id=current_step_id,
                ),
                [str(exc)],
            )
        except MissionSelectorAmbiguous as exc:  # NEW — FR-010 (#3884)
            return _mapping._materialize_decision(
                _cores.DecisionEnvelope(
                    kind=DecisionKind.blocked,
                    agent=agent,
                    mission_slug=mission_slug,
                    mission=mission_type,
                    mission_state=current_step_id,
                    timestamp=now,
                    reason=str(exc),
                    progress=progress,
                    origin=origin,
                    run_id=run_ref.run_id,
                    step_id=current_step_id,
                ),
                [str(exc)],
            )
        if not should_advance:
            # Stay in current step, return WP-level action
            return _mapping._build_wp_iteration_decision(
                current_step_id,
                agent,
                mission_slug,
                mission_type,
                feature_dir,
                repo_root,
                now,
                progress,
                origin,
                run_ref,
                owned=owned,
            )
        # All WPs done for this step — check guards before advancing.
        #
        # Unlike the non-WP pre-check below (deliberately scoped to
        # ``software-dev`` only, #3407), this WP-iteration branch runs for
        # every mission family whose current step is ``implement``/``review``
        # (``_WP_ITERATION_STEPS``) — including ``software-dev`` and
        # ``plan``, both of which ARE registered in ``_GUARD_TABLES``, but
        # also any custom mission family that has no guard-table entry at
        # all (#3627). ``_check_cli_guards`` -> ``evaluate_guards_strict``
        # fails closed with ``UnregisteredMissionFamilyError`` for such a
        # family by design (see its own docstring); that is correct for the
        # scoped non-WP pre-check, but here it must degrade to "no guard
        # failures" instead of crashing the WP-iteration advance decision —
        # composition-dispatch's own tolerant ``evaluate_guards`` remains the
        # authority for those custom families, exactly as it already is for
        # every non-WP-iteration step of theirs.
        try:
            guard_failures = _check_cli_guards(
                current_step_id,
                feature_dir,
                mission_family=mission_type,
                repo_root=repo_root,
                owned=owned,
            )
        except _cores.UnregisteredMissionFamilyError:
            logger.warning(
                "Unregistered mission_family %r reached the CLI guard path; returning a neutral (empty) guard result.",
                mission_type,
            )
            guard_failures = []
        if guard_failures:
            return _mapping._build_wp_iteration_decision(
                current_step_id,
                agent,
                mission_slug,
                mission_type,
                feature_dir,
                repo_root,
                now,
                progress,
                origin,
                run_ref,
                guard_failures=guard_failures,
                owned=owned,
            )

    # Check guards for non-WP steps before advancing.
    #
    # This CLI-native pre-check (#3407 M3) is scoped to the ``software-dev``
    # mission family only. Its ``kind=step`` "re-issue the current step"
    # semantic belongs to software-dev's linear specify → plan → tasks CLI
    # vocabulary; it must NOT pre-empt composition dispatch for the other
    # families. For ``documentation`` / ``research`` / ``plan`` and every
    # custom mission type, the composed-action guard (Phase 3) is the
    # authority — it surfaces the same missing-artifact failure as a
    # ``kind=blocked`` decision (the fail-CLOSED contract, spec.md AC of the
    # documentation/research runtime walks) and, unlike ``_check_cli_guards``
    # here, degrades gracefully for guard-table-unregistered custom families
    # instead of raising ``UnregisteredMissionFamilyError``. Gating on the
    # family keeps software-dev byte-identical to its pre-#3407 behavior
    # (AC-14) while restoring the correct blocked decision for the composed
    # families (WP06 wrongly routed them through this ``kind=step`` path).
    if ctx.result == "success" and current_step_id and not _mapping._is_wp_iteration_step(current_step_id) and mission_type == MISSION_TYPE_SOFTWARE_DEV:
        guard_failures = _check_cli_guards(
            current_step_id,
            feature_dir,
            mission_family=mission_type,
            repo_root=repo_root,
            owned=owned,
        )
        if guard_failures:
            action, wp_id, workspace_path = _state_to_action(
                current_step_id,
                mission_slug,
                feature_dir,
                repo_root,
                mission_type,
                owned=owned,
            )
            prompt_file: str | None = None
            prompt_error: str | None = None
            prompt_error_code: str | None = None
            if action:
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
            else:
                prompt_error = f"no action mapped for step '{current_step_id}'; cannot resolve prompt"
            # WP06 (FR-006/FR-013) / WP07 (FR-011): step_or_blocked never
            # issues kind=step with an unresolvable prompt_file — it falls
            # back to kind=blocked using this pre-computed reason (matches
            # the original "prompt_file is None" branch's literal exactly;
            # the "resolved-but-vanished-by-construction-time" race uses the
            # core's own hard-coded literal — see DecisionEnvelope's
            # docstring for why that is safe to share across sites).
            return _mapping._materialize_decision(
                _cores.DecisionEnvelope(
                    kind=DecisionKind.step,
                    agent=agent,
                    mission_slug=mission_slug,
                    mission=mission_type,
                    mission_state=current_step_id,
                    timestamp=now,
                    reason=prompt_error or "prompt_file_not_resolvable",
                    action=action,
                    wp_id=wp_id,
                    workspace_path=workspace_path,
                    prompt_file=prompt_file,
                    progress=progress,
                    origin=origin,
                    run_id=run_ref.run_id,
                    step_id=current_step_id,
                    error_code=prompt_error_code,
                ),
                guard_failures,
            )

    return None


def _dn_composition_blocked_decision(
    ctx: DecideNextContext,
    current_step_id: str,
    composition_failures: list[str],
) -> Decision:
    """Build the blocked ``Decision`` for a composition-dispatch guard
    failure — the ``_state_to_action`` -> ``_build_prompt_safe`` prompt
    resolution the composition-dispatch phase needs when the executor
    reports guard failures instead of advancing (FR-008 composition
    guard-failure surface). Split out of ``_dn_composition_dispatch`` to
    keep that phase's own complexity down; it re-extracts nothing WP06-08
    already own — it is pure orchestration plumbing local to this phase.
    """
    action, wp_id, workspace_path = _state_to_action(
        current_step_id,
        ctx.mission_slug,
        ctx.feature_dir,
        ctx.repo_root,
        ctx.mission_type,
        owned=ctx.owned,
    )
    prompt_file = (
        _build_prompt_safe(
            action,
            ctx.feature_dir,
            ctx.mission_slug,
            wp_id,
            ctx.agent,
            ctx.repo_root,
            ctx.mission_type,
            owned=ctx.owned,
        )
        if action
        else None
    )
    return _mapping._materialize_decision(
        _cores.DecisionEnvelope(
            kind=DecisionKind.blocked,
            agent=ctx.agent,
            mission_slug=ctx.mission_slug,
            mission=ctx.mission_type,
            mission_state=current_step_id,
            timestamp=ctx.now,
            reason=composition_failures[0],
            action=action,
            wp_id=wp_id,
            workspace_path=workspace_path,
            prompt_file=prompt_file,
            progress=ctx.progress,
            origin=ctx.origin,
            run_id=ctx.run_ref.run_id,
            step_id=current_step_id,
        ),
        composition_failures,
    )


def _advance_failed_decision(ctx: DecideNextContext, composed_action: str, exc: Exception) -> Decision:
    """EDGE-003 contract: any advancement-helper failure must surface as a
    structured ``blocked`` Decision, not as a Python traceback, and MUST NOT
    silently fall through to the legacy DAG dispatch handler."""
    logger.exception(
        "advancement helper failed after composition for %s/%s",
        ctx.mission_type,
        composed_action,
    )
    return _mapping._materialize_decision(
        _cores.DecisionEnvelope(
            kind=DecisionKind.blocked,
            agent=ctx.agent,
            mission_slug=ctx.mission_slug,
            mission=ctx.mission_type,
            mission_state=ctx.current_step_id,
            timestamp=ctx.now,
            reason=(f"Run-state advancement after composition failed for {ctx.mission_type}/{composed_action}: {type(exc).__name__}: {exc}"),
            progress=ctx.progress,
            origin=ctx.origin,
            run_id=ctx.run_ref.run_id,
            step_id=ctx.current_step_id,
        )
    )


def _dn_plan_composition_advance(ctx: DecideNextContext, composed_action: str) -> tuple[Any, _mapping._WpIterationResolution | None] | Decision:
    """Plan (pure; the engine's own :func:`plan_advance`, #2562) the run-state
    advance after a successful composed action and resolve a planned WP step's
    workspace BEFORE anything is persisted (FR-008).

    Returns ``(plan, wp_resolution)`` for :func:`_dn_composition_dispatch` to
    commit, or the EDGE-003 ``blocked`` Decision when the plan itself cannot be
    computed. The resolution runs OUTSIDE any ``except``: a typed failure
    propagates unwrapped, and because nothing has been written the run stays
    untouched."""
    try:
        plan = _engine_adapter.plan_advance(ctx.run_ref, ctx.agent, "success")
    except Exception as exc:  # noqa: BLE001 — EDGE-003: a planning failure is a structured blocked Decision
        return _advance_failed_decision(ctx, composed_action, exc)
    wp_resolution = _resolve_planned_wp_workspace(
        plan.decision,
        mission_slug=ctx.mission_slug,
        mission_type=ctx.mission_type,
        feature_dir=ctx.feature_dir,
        repo_root=ctx.repo_root,
        owned=ctx.owned,
    )
    return plan, wp_resolution


def _dn_advance_composition_or_refusal(
    ctx: DecideNextContext,
    composed_action: str,
    *,
    plan: Any,
    wp_resolution: _mapping._WpIterationResolution | None,
) -> Decision:
    """Commit the composition advance. A retrospective-gate refusal (B6) is
    caught before the generic handler and reads exactly as on the legacy path;
    any other advancement-helper failure surfaces as the EDGE-003 ``blocked``
    Decision (the legacy DAG dispatch handler is never entered as a fallback)."""
    try:
        return _engine_adapter.advance_run_state_after_composition(
            run_ref=ctx.run_ref,
            agent=ctx.agent,
            mission_slug=ctx.mission_slug,
            mission_type=ctx.mission_type,
            repo_root=ctx.repo_root,
            feature_dir=ctx.feature_dir,
            timestamp=ctx.now,
            progress=ctx.progress,
            origin=ctx.origin,
            sync_emitter=ctx.emitter_for_engine,
            owned=ctx.owned,
            plan=plan,
            wp_resolution=wp_resolution,
        )
    except _retrospective_seam.RetrospectiveGateRefused as refusal:
        return _retrospective_gate_refused_decision(ctx, refusal)
    except Exception as exc:  # noqa: BLE001 — EDGE-003: any advancement-helper failure surfaces as a blocked Decision
        return _advance_failed_decision(ctx, composed_action, exc)


def _dn_composition_dispatch(ctx: DecideNextContext) -> Decision | None:
    """Phase 3/4 of ``decide_next_via_runtime`` (FR-010) — composition
    dispatch (mission `software-dev-composition-rewrite-01KQ26CY`).

    For the built-in `software-dev` mission's five public actions, route the
    just-completed step through `StepContractExecutor.execute` BEFORE we let
    the runtime planner advance run state. The composition produces the
    invocation_id chain (host harness interprets it); a structured guard
    failure surface (Decision.kind=blocked, guard_failures populated) is
    used in lieu of a Python traceback when the executor raises
    `StepContractExecutionError`. C-008 gates this on `action_sequence`
    membership for the resolved mission type -- any mission type, not just
    `software-dev`; a step outside its own sequence falls through (returns
    ``None``) to composition unchanged so decision-materialize runs the
    runtime planner next.
    """
    agent = ctx.agent
    mission_type = ctx.mission_type
    feature_dir = ctx.feature_dir
    current_step_id = ctx.current_step_id
    # Root discipline (FR-009): composition policy and task-board resolution
    # are P-local governance reads for an owned mission.
    config_root = ctx.owned.owned_root if ctx.owned is not None else ctx.repo_root

    if (
        ctx.result == "success"
        and current_step_id
        and _composition._should_dispatch_via_composition(
            mission_type,
            current_step_id,
            run_dir=ctx.run_dir,
            repo_root=config_root,
        )
    ):
        composed_action = _composition._normalize_action_for_composition(current_step_id)
        # R-005: for custom missions, the active step's ``agent_profile`` is
        # the source of truth for ``profile_hint``. For built-in missions
        # (e.g., ``software-dev``), built-in templates do NOT set
        # ``agent_profile``, so this resolves to ``None`` and the executor's
        # ``_resolve_profile_hint`` falls back to ``_ACTION_PROFILE_DEFAULTS``
        # — preserving byte-identical built-in dispatch behavior (FR-010).
        resolved_profile, runtime_contract = _composition._composition_dispatch_inputs(
            repo_root=config_root,
            run_dir=ctx.run_dir,
            mission=mission_type,
            step_id=current_step_id,
            action=composed_action,
        )
        composition_failures = _composition._dispatch_via_composition(
            repo_root=config_root,
            mission=mission_type,
            action=composed_action,
            actor=agent,
            profile_hint=resolved_profile,
            request_text=None,
            mode_of_work=None,
            feature_dir=feature_dir,
            # Thread the original step_id so the post-action guard can branch
            # on substep semantics for legacy tasks_outline/tasks_packages/
            # tasks_finalize. Without this, the collapsed guard demands the
            # terminal post-finalize state on every substep and blocks the
            # live tasks_outline → tasks_packages → tasks_finalize flow.
            legacy_step_id=current_step_id,
            contract=runtime_contract,
            owned=ctx.owned,
        )
        if composition_failures:
            return _dn_composition_blocked_decision(ctx, current_step_id, composition_failures)
        # Composition succeeded; advance run state via the
        # composition-specific advancement helper and short-circuit the
        # legacy ``runtime_next_step`` fall-through (FR-001/FR-002). Plan and
        # resolve first (FR-008), then commit. The helper emits the same
        # lane / state events the legacy path emits, through the
        # decision-log-wrapped engine emitter so a ``DecisionInputRequested``
        # it raises is durably recorded (ADR 2026-09-06-2 (c)); any error from
        # it surfaces through the existing ``Decision`` ``blocked`` shape
        # (EDGE-003) — the legacy DAG dispatch handler is **not** entered as a
        # fallback.
        planned = _dn_plan_composition_advance(ctx, composed_action)
        if isinstance(planned, Decision):
            return planned
        plan, wp_resolution = planned
        return _dn_advance_composition_or_refusal(ctx, composed_action, plan=plan, wp_resolution=wp_resolution)

    return None


def _retrospective_gate_refused_decision(ctx: DecideNextContext, refusal: _retrospective_seam.RetrospectiveGateRefused) -> Decision:
    """The one ``blocked`` Decision of a refused terminal advance, on the legacy
    and the composition path alike. ``guard_failures`` is the gate's
    ``code: detail`` when the refusal carries a gate decision. The engine's
    ``before_run_completed`` guard raised before anything was written, so the
    run is exactly as other writers left it."""
    return _mapping._materialize_decision(
        _cores.DecisionEnvelope(
            kind=DecisionKind.blocked,
            agent=ctx.agent,
            mission_slug=ctx.mission_slug,
            mission=ctx.mission_type,
            mission_state=ctx.current_step_id or "unknown",
            timestamp=ctx.now,
            reason=f"Retrospective gate refused completion: {refusal.cause}",
            progress=ctx.progress,
            origin=ctx.origin,
        ),
        list(refusal.guard_failures),
    )


def _resolve_planned_wp_workspace(
    decision: NextDecision,
    *,
    mission_slug: str,
    mission_type: str,
    feature_dir: Path,
    repo_root: Path,
    owned: OwnedCheckout | None,
) -> _mapping._WpIterationResolution | None:
    """THE single place a planned WP-iteration step's board action + workspace
    is resolved BEFORE the advance is persisted (FR-008 / R-06), shared by the
    legacy ``runtime_next_step`` path (:func:`_dn_decision_materialize`) and
    the composition path (``advance_run_state_after_composition``).

    ``None`` unless ``decision`` is a WP-iteration step. A resolution failure
    PROPAGATES -- typed, carrying its ``error_code`` -- before anything is
    written, so the run stays at the issued step instead of being advanced
    into a step whose workspace cannot be resolved (the wedge). It is
    deliberately never wrapped into a ``blocked`` Decision (FR-008)."""
    if decision.kind != "step" or not decision.step_id or not _mapping._is_wp_iteration_step(decision.step_id):
        return None
    return _mapping._wp_iteration_action_and_state(
        decision.step_id,
        mission_slug,
        mission_type,
        feature_dir,
        repo_root,
        owned=owned,
    )


def _dn_preresolve_wp_workspace(ctx: DecideNextContext) -> tuple[Any, _mapping._WpIterationResolution | None]:
    """Plan the advance (the engine's own pure :func:`plan_advance`) and resolve
    the step it will issue BEFORE anything is persisted. Returns ``(plan,
    resolution)``; ``(None, None)`` when no plan can be previewed. The plan is
    then COMMITTED by :func:`_dn_advance_engine` -- the engine plans once."""
    try:
        plan = _engine_adapter.plan_advance(ctx.run_ref, ctx.agent, ctx.result)
    except _engine_adapter.PLAN_UNAVAILABLE_ERRORS:
        logger.debug("advance preview unavailable for %s; advancing without pre-resolution", ctx.mission_slug, exc_info=True)
        return None, None
    resolution = _resolve_planned_wp_workspace(
        plan.decision,
        mission_slug=ctx.mission_slug,
        mission_type=ctx.mission_type,
        feature_dir=ctx.feature_dir,
        repo_root=ctx.repo_root,
        owned=ctx.owned,
    )
    return plan, resolution


def _dn_advance_engine(
    ctx: DecideNextContext,
    plan: Any,
    engine_emitter: Any,
    before_run_completed: Callable[[], None] | None = None,
) -> NextDecision:
    """Persist the advance: commit the previewed ``plan`` when there is one
    (no second planning), else -- or when the run moved past the plan
    (:class:`StaleAdvancePlan`) -- the engine's own ``next_step``.

    ``before_run_completed`` (the retrospective gate) goes to whichever of the
    two commits, so the gate runs before anything is appended on every path.

    The engine path re-plans a stale advance through ``next_step``, which
    re-applies ``success`` and so can complete a step this caller never ran,
    while the composition path refuses it with a ``blocked`` Decision; making
    the engine path refuse too is tracked in #5854."""
    if plan is not None:
        try:
            return _engine_adapter.commit_advance(ctx.run_ref, plan, ctx.agent, engine_emitter, before_run_completed=before_run_completed)
        except _engine_adapter.StaleAdvancePlan:
            logger.debug("advance plan for %s is stale; re-planning through next_step", ctx.mission_slug, exc_info=True)
    return runtime_next_step(
        ctx.run_ref,
        agent_id=ctx.agent,
        result=ctx.result,
        emitter=engine_emitter,
        before_run_completed=before_run_completed,
    )


def _dn_decision_materialize(ctx: DecideNextContext) -> Decision:
    """Phase 4/4 of ``decide_next_via_runtime`` (FR-010) — advance via the
    runtime planner and materialize the terminal/step/query ``Decision``
    through WP07's Decision-builder. Always returns a ``Decision`` (never
    ``None``): this is the chain's terminal phase.

    The retrospective gate is the engine's abort-only ``before_run_completed``
    guard, passed to whichever commit runs (FR-009, FR-011): a refusal raises
    before anything is appended to ``run.events.jsonl`` or ``state.json``, so
    nothing is captured, buffered or rolled back. The default post-completion
    policy is best-effort and runs after the commit, once, on the transition
    into terminal only.
    """
    # Root discipline (FR-009): retrospective policy is a P-local governance
    # read for an owned mission.
    config_root = ctx.owned.owned_root if ctx.owned is not None else ctx.repo_root
    terminal_retrospective = _engine_adapter.TerminalRetrospective(
        config_root=config_root,
        mission_slug=ctx.mission_slug,
        feature_dir=ctx.feature_dir,
    )

    # T061 step 3: resolve a WP-iteration step's workspace BEFORE anything is
    # persisted; a failure propagates here with the run directory untouched.
    preview_plan, preresolved = _dn_preresolve_wp_workspace(ctx)
    preview_step_id = preview_plan.decision.step_id if preview_plan is not None else None

    # Use the DecisionGitLog-wrapped emitter as the engine's emitter so that
    # decision events are durably committed to the coordination branch.
    try:
        runtime_decision = _dn_advance_engine(
            ctx,
            preview_plan,
            ctx.emitter_for_engine,
            terminal_retrospective.before_run_completed,
        )
    except _retrospective_seam.RetrospectiveGateRefused as refusal:
        return _retrospective_gate_refused_decision(ctx, refusal)
    except Exception as exc:
        return _mapping._materialize_decision(
            _cores.DecisionEnvelope(
                kind=DecisionKind.blocked,
                agent=ctx.agent,
                mission_slug=ctx.mission_slug,
                mission=ctx.mission_type,
                mission_state=ctx.current_step_id or "unknown",
                timestamp=ctx.now,
                reason=f"Runtime engine error: {exc}",
                progress=ctx.progress,
                origin=ctx.origin,
            )
        )

    terminal_retrospective.after_run_completed()

    return _mapping._map_runtime_decision(
        runtime_decision,
        ctx.agent,
        ctx.mission_slug,
        ctx.mission_type,
        ctx.repo_root,
        ctx.feature_dir,
        ctx.now,
        ctx.progress,
        ctx.origin,
        owned=ctx.owned,
        # Reuse the pre-persist resolution only for the very step it was
        # computed for; any other outcome resolves normally in the mapper.
        wp_resolution=preresolved if runtime_decision.step_id == preview_step_id else None,
    )


def decide_next_via_runtime(
    agent: str,
    mission_slug: str,
    result: str,
    repo_root: Path,
    *,
    owned: OwnedCheckout | None = None,
) -> Decision:
    """Main entry point replacing old decide_next().

    A linear four-phase early-return chain over :class:`DecideNextContext`
    (FR-010): bootstrap builds the context (and may itself short-circuit —
    feature dir missing / run failed to start); dependency-gate,
    composition-dispatch, and decision-materialize each take ``ctx`` and
    return ``Decision | None``, the first non-``None`` short-circuiting.
    decision-materialize is the terminal phase and always resolves.

    Flow:
    0. Committed-authority pre-check (#2947, D13) — a merged mission
       (``mission_terminal_verdict`` is ``terminal``/``blocked_conflict``)
       short-circuits BEFORE workspace selection / run start, returning
       ``kind: terminal`` (no run created) or ``kind: blocked``. A ``"none"``
       verdict falls through unchanged (F5).
    1. Resolve mission_type from meta.json
    2. get_or_start_run() to obtain MissionRunRef
    3. Check if current step is a WP-iteration step
       a. If yes and WPs remain: skip runtime advance, build WP prompt, return step
       b. If yes and all WPs done: call next_step(result="success") to advance
    4. For non-WP steps: call next_step(run_ref, agent, result) directly
    5. Map NextDecision -> Decision (preserving JSON contract)
    """
    merged_short_circuit = _mapping._merged_mission_short_circuit(
        repo_root=repo_root,
        mission_slug=mission_slug,
        agent=agent,
        now=now_utc_iso(),
        terminal_kind=DecisionKind.terminal,
        owned=owned,
    )
    if merged_short_circuit is not None:
        return merged_short_circuit

    ctx, early_decision = _dn_bootstrap(
        agent,
        mission_slug,
        result,
        repo_root,
        owned=owned,
    )
    if early_decision is not None:
        return early_decision
    assert ctx is not None  # _dn_bootstrap always pairs a ctx with None (or vice versa)

    for phase in (_dn_finalized_board_override, _dn_dependency_gate, _dn_composition_dispatch, _dn_decision_materialize):
        decision = phase(ctx)
        if decision is not None:
            return decision

    raise AssertionError(  # pragma: no cover — decision-materialize always resolves
        "decide_next_via_runtime: no phase produced a Decision"
    )


# ---------------------------------------------------------------------------
# Public surface (FR-007 / #2531 WP03). Governs ``from runtime_bridge import *``
# ONLY. It lists the 8 public names; seam-owned private names are not
# re-exported here.
# ---------------------------------------------------------------------------
__all__ = [
    "DecisionGitLogUnavailable",
    "MissionNotFoundError",
    "QueryModeValidationError",
    "answer_decision_via_runtime",
    "build_operational_context_for_claim",
    "decide_next_via_runtime",
    "get_or_start_run",
    "query_current_state",
]
