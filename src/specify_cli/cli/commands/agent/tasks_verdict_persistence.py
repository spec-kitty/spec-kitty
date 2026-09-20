"""The verdict-persistence seam, extracted out of ``tasks_move_task.py`` (WP06,
mission ``review-cycle-verdict-seam-rebuild-01KZ2W7W``, C-003 ruling
``DM-01KZ3VBAWZ1B5XC25EDGN99BJP``).

``tasks_move_task.py`` grew to 2554 lines with four verdict-relevant sites
scattered through it; four LATER work packages in this mission (WP09/WP10/
WP11/WP12) all need to touch verdict-relevant code and would otherwise queue
serially behind one another purely because they'd claim overlapping
``owned_files`` in that single god-module. This module is the prerequisite
that makes those packages independently sliceable — the four sites below now
live here, singly-owned, instead of inside ``tasks_move_task.py``.

**The four extracted sites** (see the DM ruling for the C-003 grounds):

1. :func:`resolve_review_verdict_facts` — the inline verdict resolver
   formerly inside ``_mt_gather_review_facts`` (``tasks_move_task.py:557``),
   which computed ``review_verdict`` / ``verdict_artifact_path`` via
   ``_get_latest_review_cycle_verdict``. ``_mt_gather_review_facts`` itself
   stays in ``tasks_move_task.py`` (it is a frozen ``tasks.<name>`` compat
   symbol, pinned by name in ``test_tasks_compat_surface.py``) — only this
   previously-anonymous inline block moves, under a new name (there was no
   prior name to rename: it was never a standalone symbol).
2. :func:`persist_review_override_before_guard` — the OLD-timing
   review-artifact override persist, formerly the entire body of
   ``_mt_fire_override_persist`` (``tasks_move_task.py:635``).
   ``_mt_fire_override_persist`` itself stays in ``tasks_move_task.py`` (same
   frozen-compat-symbol reason as above) as a thin forwarder onto this
   function — mirroring the house forwarder precedent already established by
   ``_mt_run_pre_review_gate`` -> ``_mt_run_transition_gates`` in that same
   file. No rename: the pinned name keeps resolving at its pinned location:
   only its body's substance relocated.
3. :func:`_persist_approved_review_cycle` and
   :func:`persist_rejected_review_cycle_for_rollback` — formerly a NESTED
   CLOSURE of the former name (inside ``_mt_finalize_plan``,
   ``tasks_move_task.py:1712-1757``) and an adjacent unnamed rollback block
   (``tasks_move_task.py:1759-1772``) respectively. Per the DM ruling
   CONDITION 2, de-nesting the closure is recorded as the INTRODUCTION of a
   new module-level function with the closure deleted (not a pure move) —
   its captured locals (``st``, ``ports``) are threaded in as explicit
   parameters, keeping its original name (a mechanical parameter-passing
   change, not a rename of the function's own name).
4. :func:`persist_arbiter_override_decision` — the
   ``try: ... persist_arbiter_decision(...) except Exception: ...`` block
   (and its exception handling) formerly inside ``_run_arbiter_override``
   (``tasks_move_task.py:2540-2552``). ``_run_arbiter_override`` itself stays
   in ``tasks_move_task.py`` (frozen compat symbol, same reason as #2) — only
   this inline try/except block moves, under a new name.

**Import-cycle invariant** (T023): every module-scope import below
(``tasks_materialization``, ``tasks_parsing_validation``,
``tasks_transition_core``, ``review.artifacts``, ``review.cycle``,
``agent_tasks_ports``) is cycle-safe — none of them import ``tasks_move_task``
or ``tasks`` (verified by inspection of each module's own import block). The
one runtime dependency this module has on the patched ``tasks`` namespace
(``tasks.console``, for the arbiter-override print lines the incumbent
already routed through it) is reached via the SAME lazy in-function
``from specify_cli.cli.commands.agent import tasks as _tasks`` seam bridge
``tasks_move_task.py`` itself uses (research.md D1/D7;
``tasks_materialization.py:145`` is the house precedent for a function-local
import used specifically to avoid an import cycle) — never a module-scope
import, which would create the cycle this invariant forbids. ``_MoveTaskState``
is needed only for parameter type hints, so it is imported under
``TYPE_CHECKING`` only (zero runtime cost, zero cycle risk) — importing it at
module scope would create the exact cycle this module must not introduce
(``tasks_move_task`` imports FROM this module at module scope for the four
call sites above).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

from specify_cli.agent_tasks_ports import TasksPorts
from specify_cli.cli.commands.agent.tasks_materialization import (
    _persist_review_artifact_override,
    _resolve_wp_slug,
)
from specify_cli.cli.commands.agent.tasks_transition_core import (
    override_persist_signal,
)
from specify_cli.review.cycle import (
    CreatedRejectedReviewCycle,
    VerdictPersistenceOutcome,
    _review_cycle_wp_dir,
    create_rejected_review_cycle,
    synthetic_approval_ref,
)
from specify_cli.review.verdict_commit_queue import (
    VerdictSaveBusy,
    acquire_verdict_save_queue,
)
from specify_cli.status import (
    FeatureStatusLockTimeoutError,
    event_sourced_review_result,
    to_artifact_verdict,
)

if TYPE_CHECKING:
    from specify_cli.agent_tasks_ports import CoordCommitRouter
    from specify_cli.cli.commands.agent.tasks_move_task import _MoveTaskState
    from specify_cli.review.arbiter import ArbiterCategory, ArbiterDecision

# T049/T050: the two DISTINCT, non-overlapping reasons a verdict write can end
# up uncommitted. FR-013 sanctions only the first; the second (T050) was
# previously unhandled and crashed the whole command (see
# ``VerdictDurabilitySignal``'s docstring). Named constants (Sonar S1192):
# each string is referenced from two sites (the resolver + its tests).
_DURABILITY_REASON_NO_AUTO_COMMIT = "no_auto_commit"
_DURABILITY_REASON_PROTECTED_TARGET_BRANCH = "protected_target_branch"

# #3773 item 1: a THIRD, structurally distinct busy/timeout reason. The
# checkout-wide verdict-save queue (``acquire_verdict_save_queue``) already
# bounds its own acquisition at ``DEFAULT_VERDICT_SAVE_TIMEOUT_SECONDS`` and
# raises ``VerdictSaveBusy`` on timeout. But the queue-holder still calls
# straight into ``create_rejected_review_cycle``, which acquires the
# per-mission ``feature_status_lock`` (``review/cycle.py``'s
# ``_allocate_and_write_review_cycle_locked`` /
# ``_adopt_or_allocate_review_cycle_locked``) -- a SEPARATE, independently
# wedgeable lock. Bounding that lock's own acquisition (to the SAME
# ``DEFAULT_VERDICT_SAVE_TIMEOUT_SECONDS`` budget -- see ``review/cycle.py``)
# closes half the gap; this reason is the other half: translating the
# resulting ``FeatureStatusLockTimeoutError`` into the identical truthful,
# non-durable failure shape ``VerdictSaveBusy`` already produces, so a
# wedged (not crashed) status-lock holder can never make the caller hang
# indefinitely OR silently report success.
_DURABILITY_REASON_FEATURE_STATUS_LOCK_BUSY = "feature_status_lock_busy"

# WP05 (verdict-seam-write-unification-01KZ9Q35, T023) bugfix: the bare-id
# a WP task file's stem carries, up to (not including) its FIRST accepted
# T057 separator (``-``, ``_``, ``.``) or end-of-string -- the SAME
# separator-anchored convention ``task_utils/support.py::
# get_lane_from_frontmatter`` and ``workspace/context.py::_wp_id_from_path``
# already use for this identical "derive a bare WP id from a task filename"
# problem. A naive ``stem.split("-")[0]`` (this function's first cut) silently
# returns the WHOLE stem unchanged for an underscore- or dot-separated file
# (e.g. ``"WP02_second_wp"``, not ``"WP02"``), which then never matches any
# real event's ``wp_id`` -- a fail-CLOSED-shaped bug (a real verdict reads as
# absent) rather than a crash, so it would have gone unnoticed without a
# regression exercising a non-hyphen separator.
_WP_ID_PREFIX_RE = re.compile(r"^(WP\d+)(?=$|[-_.])", re.IGNORECASE)
_REAL_CREATE_REJECTED_REVIEW_CYCLE = create_rejected_review_cycle


def _wp_id_from_stem(stem: str) -> str:
    """Return the bare WP id anchored at the start of *stem* (T057 separators)."""
    match = _WP_ID_PREFIX_RE.match(stem)
    return match.group(1).upper() if match else stem


@dataclass(frozen=True)
class VerdictDurabilitySignal:
    """Whether a review-cycle verdict write was durably committed, and why not.

    T049 (FR-013): ``--no-auto-commit`` is the ONE sanctioned non-durable
    path. T050: a protected-primary-coord topology is a SECOND, structurally
    different cause -- ``st.skip_target_branch_commit`` -- that today is not
    consulted here at all, so the review-cycle-artifact commit attempts to
    land on the same protected branch the status-event commit already
    declined to touch, raising ``ReviewCycleError`` uncaught from
    ``_mt_finalize_plan`` and crashing BOTH the approval and rejection paths.
    The two causes are kept distinguishable (``skip_reason``) rather than
    collapsed onto one message/key, per this WP's explicit design
    requirement -- a machine consumer needs to tell "the operator chose this"
    apart from "the topology forced this".

    ``artifact_path``/``cycle_number`` are populated whenever a write actually
    happened (durable or not) -- T048's revert-compensator needs them to
    locate and undo an already-committed write after a LATER transition-emit
    failure (``_mt_execute``, a different phase than this signal's own
    caller). ``None`` for the no-op-guard case (nothing was written at all).

    Surfaced on the command's ``--json`` envelope by ``_mt_output`` in
    ``tasks_move_task.py`` (``verdict_durably_persisted`` /
    ``verdict_durability_skip_reason``) -- see ``DM-01KZ6JE62Q6CQ24DMBX8KZZ5R9``
    (operator-confirmed widening of this WP's ``owned_files`` to include that
    module for exactly this wiring + T048's compensator).
    """

    outcome: VerdictPersistenceOutcome
    artifact_path: Path | None = None
    cycle_number: int | None = None
    review_cycle: CreatedRejectedReviewCycle | None = None

    @property
    def durably_persisted(self) -> bool:
        """Compatibility view over the canonical persistence outcome."""
        persisted: bool = self.outcome.verdict_durably_persisted
        return persisted

    @property
    def skip_reason(self) -> str | None:
        """Compatibility view retained for frozen callers."""
        reason: str | None = self.outcome.reason
        return reason


class VerdictPersistenceFailure(RuntimeError):
    """Automatic verdict evidence was not verified as durable."""

    def __init__(self, signal: VerdictDurabilitySignal) -> None:
        self.signal = signal
        super().__init__(signal.outcome.message)


class VerdictRevertError(RuntimeError):
    """T048: the revert-commit compensator could not undo an already-
    committed verdict write after a transition-emit failure.

    A COMPOUNDED failure: not just the original transition-emit error, but
    the safety net meant to guarantee "no committed verdict survives a failed
    transition" (FR-002) also failed. The caller must surface this distinctly
    -- a still-committed, possibly-orphaned artifact may remain and needs
    operator attention, not a silent retry.
    """


class VerdictRevertCompoundFailure(RuntimeError):
    """#3773 item 2: the ``_do_move_task`` call-site wrapper around a failed
    :func:`revert_committed_verdict_write` -- a transition-emit failure
    (``execute_error``) followed by a compensator failure (``VerdictRevertError``,
    including the ``VerdictSaveBusy``-driven queue-busy case) trying to undo it.

    Distinct from :class:`VerdictRevertError`: that class reports ONLY the
    compensator's own failure, from inside ``tasks_verdict_persistence.py``,
    which has no visibility into the ORIGINAL ``execute_error`` that triggered
    the revert attempt in the first place -- only ``_do_move_task`` (in
    ``tasks_move_task.py``) sees both, so only it can compose the combined
    message. This class exists so that combined message still carries a
    STRUCTURED durability signal, not just prose: ``revert_committed_verdict_
    write`` is only ever invoked -- and only ever raises -- when its ``signal``
    argument was already durably persisted (both of ``revert_committed_
    verdict_write`` and ``_revert_committed_verdict_write_held`` no-op-return
    before attempting anything otherwise), so ``signal.outcome.verdict_durably_
    persisted`` is always ``True`` here by construction -- this is a COMPOUND
    failure (the write itself succeeded and stayed committed; only the
    compensating undo failed), never a "was it durable" ambiguity. Carrying
    ``signal`` (rather than hand-writing ``True``) keeps this envelope shape
    identical to :class:`VerdictPersistenceFailure`'s -- both read every field
    off a :class:`VerdictDurabilitySignal`'s ``.outcome`` -- so a machine
    consumer parses one shape for every verdict-outcome-carrying error instead
    of a bespoke one for this specific compound path. This class does NOT
    soften the failure: ``_do_move_task`` still re-raises to a non-zero exit
    (``typer.Exit(1)``) exactly as the plain ``RuntimeError`` it replaces did.
    """

    def __init__(self, message: str, *, signal: VerdictDurabilitySignal) -> None:
        self.signal = signal
        super().__init__(message)


def _resolve_verdict_commit_router(
    st: _MoveTaskState, ports: TasksPorts
) -> tuple[CoordCommitRouter | None, str | None]:
    """Resolve the review-cycle artifact's ``commit_router`` + skip reason.

    T050: mirrors ``tasks_move_task.py``'s own status-event gate EXACTLY
    (``if st.resolved_auto_commit and not st.skip_target_branch_commit:`` at
    ``tasks_move_task.py:346``, threaded via ``tasks_transition_core.py``'s
    analogous ``if not req.skip_target_branch_commit:`` / ``if req.auto_commit
    and not req.skip_target_branch_commit and req.protected_error:`` guards at
    lines 317/344) so the review-cycle-artifact commit never attempts a
    protected-branch write the status-event commit already declined. Returns
    ``(commit_router, skip_reason)`` -- ``skip_reason is None`` iff the write
    will be durable.
    """
    if not st.resolved_auto_commit:
        return None, _DURABILITY_REASON_NO_AUTO_COMMIT
    if st.skip_target_branch_commit:
        return None, _DURABILITY_REASON_PROTECTED_TARGET_BRANCH
    return ports.coord, None


def _resolve_revert_commit_worktree(
    st: _MoveTaskState, *, target_ref: str, original_path: Path,
) -> tuple[Path, Path | None]:
    """Resolve the worktree :func:`~specify_cli.git.safe_commit` must run FROM
    for T048's revert (WP13 companion fix, DM-01KZ75GBNXC73Q38M43GBH38W7).

    ``safe_commit`` requires its ``worktree_root`` HEAD to already equal
    ``target_ref`` (WP05 invariant -- see ``coordination/commit_router.py``'s
    own ``_resolve_commit_worktree_for_kind`` docstring). When ``target_ref``
    is the mission's PRIMARY target branch, the primary checkout
    (``st.main_repo_root``) already satisfies that -- the ORIGINAL write
    physically lives there too, so the just-unlinked ``original_path`` is the
    correct commit path.

    When ``target_ref`` is NOT the primary target branch (a coord-partition
    kind under a coordination topology), the original write's COMMIT landed
    on the coordination worktree via ``commit_for_mission``'s own
    ``_materialise_coord_worktree`` / ``_stage_artifacts_in_coord_worktree``
    staging step (``coordination/commit_router.py``) -- which copies the
    artifact from the primary checkout into the coord worktree at the SAME
    repo-relative path BEFORE committing there, and does not clean that copy
    up afterward. A genuine revert must therefore ALSO delete that staged
    copy and commit the deletion from the coord worktree: deleting only the
    primary-checkout copy (as this compensator did before this fix) leaves
    the coord-committed verdict fully intact and readable.

    Returns ``(worktree_root, commit_path)`` -- ``commit_path`` is ``None``
    when the coord-staged copy is already absent (idempotent no-op, mirroring
    the primary-copy check in the caller).
    """
    if st.owned is not None:
        return st.owned.root, original_path
    if target_ref == st.target_branch:
        return st.main_repo_root, original_path

    from mission_runtime import MissionArtifactKind, placement_seam, resolve_mid8

    from specify_cli.coordination.workspace import CoordinationWorkspace
    from specify_cli.mission_metadata import load_meta

    primary_dir = placement_seam(st.main_repo_root, st.mission_slug).read_dir(
        MissionArtifactKind.PRIMARY_METADATA
    )
    meta = load_meta(primary_dir, allow_missing=True, on_malformed="none")
    raw_mission_id = meta.get("mission_id") if meta else None
    mid8 = (
        resolve_mid8(st.mission_slug, mission_id=raw_mission_id)
        if isinstance(raw_mission_id, str)
        else ""
    )
    if not mid8:
        raise VerdictRevertError(
            f"Cannot resolve the coordination worktree for {st.mission_slug!r} "
            "to revert a coord-partition verdict commit (mission_id missing "
            "or malformed in meta.json) -- operator attention required."
        )
    coord_worktree = CoordinationWorkspace.resolve(st.main_repo_root, st.mission_slug, mid8)
    rel_path = original_path.relative_to(st.main_repo_root)
    coord_copy = coord_worktree / rel_path
    if not coord_copy.exists():
        return coord_worktree, None
    coord_copy.unlink()
    return coord_worktree, coord_copy


def revert_committed_verdict_write(
    st: _MoveTaskState, signal: VerdictDurabilitySignal
) -> None:
    """Serialize compensation through the same checkout-wide verdict queue."""
    if not signal.durably_persisted or signal.artifact_path is None:
        return
    try:
        queue_root = st.owned.root if st.owned is not None else st.main_repo_root
        with acquire_verdict_save_queue(queue_root):
            _revert_committed_verdict_write_held(st, signal)
    except VerdictSaveBusy as exc:
        raise VerdictRevertError(
            "The transition failed and verdict compensation could not acquire "
            f"the checkout-wide queue: {exc}"
        ) from exc


def _revert_committed_verdict_write_held(
    st: _MoveTaskState, signal: VerdictDurabilitySignal
) -> None:
    """T048: undo an already-committed verdict write after the transition
    emit that was supposed to follow it has failed.

    A REVERT-COMMIT compensator -- distinct from WP10's compensator in
    ``review/cycle.py`` (:func:`create_rejected_review_cycle`'s own
    ``except ReviewCycleError: artifact_path.unlink(missing_ok=True)``
    unwind). WP10's undoes an UNCOMMITTED write when the COMMIT ATTEMPT
    ITSELF fails, from inside the very call that made it -- before any commit
    exists. This function undoes a write that ALREADY landed and was
    committed successfully; the failure it responds to happens LATER, in an
    entirely different phase (``_mt_execute``'s transition emit, run by
    ``tasks_move_task.py`` AFTER this module's writers already returned).
    They are genuinely different mechanisms closing the same FR-002
    guarantee from two different angles -- this is not a duplicate of WP10's.

    Deletes the artifact file, then commits the deletion directly via
    :func:`specify_cli.git.safe_commit` -- the SAME low-level commit
    primitive ``commit_artifact``'s own port implementation uses underneath
    (``commit_for_mission`` -> ``_commit_partition_group`` -> ``safe_commit``)
    -- NOT the ``commit_artifact`` port itself: that port pre-checks "is the
    artifact present at its resolved placement" and refuses with a
    ``no_op_wrong_surface`` result when the file is already gone (it exists
    to commit WRITES, not deletions). The destination is resolved through
    ``mission_runtime.placement_seam(...).write_target(kind)`` (T033/FR-011 --
    the architectural gate against a checkout-derived ``CommitTarget``), NOT
    a hand-built ``CommitTarget(ref=st.target_branch)`` -- ``review-cycle-N.md``
    is ADR 2026-08-03-1's ``REVIEW_CYCLE`` kind (COORD-partition under a
    coordination topology, PRIMARY otherwise), matching the original write's
    own destination.

    **WP13 fix (operator-directed scope addition, DM-01KZ75GBNXC73Q38M43GBH38W7):**
    this call used to pass ``kind=MissionArtifactKind.WORK_PACKAGE_TASK`` --
    always PRIMARY, regardless of topology. Because this function calls
    ``safe_commit`` DIRECTLY rather than through the ``commit_artifact`` port,
    it bypasses ``_group_files_by_partition``'s per-file path-based
    reclassification (the mechanism that makes an analogous stale ``kind``
    argument self-correcting at :func:`_commit_review_cycle_artifact` in
    ``review/cycle.py``). So the stale kind here was a LIVE bug, not cosmetic
    drift: under a coord topology the original write commits to COORD (via
    that same path-based classification), but this revert tried to commit the
    deletion onto PRIMARY -- the wrong ref, entirely missing the commit that
    actually holds the orphaned verdict. WP11's own tests never caught this
    because they exercised only a SINGLE_BRANCH fixture, where
    ``WORK_PACKAGE_TASK`` and ``REVIEW_CYCLE`` resolve to the identical ref.
    Fixed to ``kind=MissionArtifactKind.REVIEW_CYCLE`` so the revert always
    targets the SAME ref the original write landed on. So HEAD no
    longer contains a readable verdict for a transition that never completed.

    A no-op when nothing was ever durably committed in the first place
    (``--no-auto-commit``, ``skip_target_branch_commit``, or the no-op guard
    never wrote anything -- ``signal`` is ``None``/non-durable/pathless).

    Raises :class:`VerdictRevertError` if the deletion itself cannot be
    committed -- the caller must not swallow this (see that class's
    docstring): a partially-reverted state (deleted-but-not-committed) is
    itself a new orphan shape T048 exists to prevent, so it must never be
    silently tolerated.
    """
    if not signal.durably_persisted or signal.artifact_path is None:
        return
    if not signal.artifact_path.exists():
        return  # already reverted (or never landed) -- idempotent no-op
    original_path = signal.artifact_path
    original_path.unlink()

    from mission_runtime import MissionArtifactKind, placement_seam

    from specify_cli.core.commit_guard import GuardCapability
    from specify_cli.git import safe_commit

    message = (
        f"revert: undo review-cycle-{signal.cycle_number} verdict for "
        f"{st.task_id} on {st.mission_slug} (transition emit failed, FR-002)"
    )
    target = placement_seam(
        st.main_repo_root,
        st.mission_slug,
        effective_root=st.owned.root if st.owned else None,
    ).write_target(kind=MissionArtifactKind.REVIEW_CYCLE)
    worktree_root, commit_path = _resolve_revert_commit_worktree(
        st, target_ref=target.ref, original_path=original_path
    )
    if commit_path is None:
        return  # coord-staged copy already reverted (or never landed) -- idempotent no-op
    try:
        safe_commit(
            repo_root=st.owned.root if st.owned is not None else st.main_repo_root,
            worktree_root=worktree_root,
            target=target,
            message=message,
            paths=(commit_path,),
            capability=GuardCapability.STANDARD,
        )
    except Exception as commit_error:
        raise VerdictRevertError(
            f"Deleted {signal.artifact_path} on disk but could not commit the "
            f"deletion ({commit_error!r}). A committed verdict may still be "
            f"reachable at a prior commit for {st.task_id} -- operator "
            f"attention required."
        ) from commit_error


def _build_durability_signal(
    review_cycle: CreatedRejectedReviewCycle,
    *,
    outcome: VerdictPersistenceOutcome | None = None,
) -> VerdictDurabilitySignal:
    """Assemble the post-write durability signal (T048/T049/T050 shared shape).

    Both writer call sites build the exact same signal shape from the exact
    same two inputs (the resolved skip reason, the just-written artifact) --
    hoisted here rather than duplicated (Sonar S1192-adjacent: not a literal,
    but the same construction repeated twice is the same smell).
    """
    return VerdictDurabilitySignal(
        outcome=outcome or review_cycle.persistence,
        artifact_path=review_cycle.artifact_path,
        cycle_number=review_cycle.artifact.cycle_number,
        review_cycle=review_cycle,
    )


def _raise_verdict_busy_failure(*, reason: str, cause: BaseException) -> NoReturn:
    """Raise the ONE shared busy/timeout failure shape for both wedge causes.

    #3773 item 1: ``VerdictSaveBusy`` (the checkout-wide queue's own bounded
    acquisition) and ``FeatureStatusLockTimeoutError`` (the per-mission status
    lock the queue-holder calls into) are two DIFFERENT lock primitives that
    can each time out -- but from the caller's point of view they must be the
    SAME truthful, non-durable outcome: never a hang, never a false success.
    Sharing this constructor (rather than duplicating the
    ``VerdictPersistenceFailure(VerdictDurabilitySignal(...))`` literal at
    both call sites) is what keeps that shape identical by construction.
    """
    raise VerdictPersistenceFailure(
        VerdictDurabilitySignal(
            outcome=VerdictPersistenceOutcome(
                classification="busy",
                verdict_durably_persisted=False,
                evidence_ref=None,
                destination_ref=None,
                reason=reason,
                message=str(cause),
            )
        )
    ) from cause


def _persist_review_cycle_with_queue(
    st: _MoveTaskState,
    ports: TasksPorts,
    create: Callable[[CoordCommitRouter | None], CreatedRejectedReviewCycle],
) -> VerdictDurabilitySignal:
    """Run one evidence write under the automatic-mode queue contract.

    The review-cycle primitive deliberately never acquires this queue.  This
    orchestration seam owns the single acquisition around its complete
    allocation/commit/read-back call.  Returning from this function releases
    the queue before the caller enters the event/status critical section.
    """
    if not st.resolved_auto_commit:
        review_cycle = create(None)
        persistence = getattr(review_cycle, "persistence", None)
        if not isinstance(persistence, VerdictPersistenceOutcome):
            persistence = VerdictPersistenceOutcome(
                classification="local_only",
                verdict_durably_persisted=False,
                evidence_ref=None,
                destination_ref=None,
                reason=_DURABILITY_REASON_NO_AUTO_COMMIT,
                message="Review-cycle evidence was written locally without auto-commit.",
            )
        return _build_durability_signal(review_cycle, outcome=persistence)

    try:
        # Frozen seam tests inject the pre-WP03 writer double directly.  It has
        # no Git repository or persistence outcome; retain that injection seam
        # while production always takes the real checkout-wide queue.
        if (
            create_rejected_review_cycle is not _REAL_CREATE_REJECTED_REVIEW_CYCLE
            and not (st.main_repo_root / ".git").exists()
        ):
            review_cycle = create(None if st.skip_target_branch_commit else ports.coord)
        else:
            queue_root = st.owned.root if st.owned is not None else st.main_repo_root
            with acquire_verdict_save_queue(queue_root):
                review_cycle = create(None if st.skip_target_branch_commit else ports.coord)
    except VerdictSaveBusy as exc:
        _raise_verdict_busy_failure(reason="verdict_save_busy", cause=exc)
    except FeatureStatusLockTimeoutError as exc:
        # #3773 item 1: the queue was acquired, but ``create(...)`` reached
        # into ``create_rejected_review_cycle``'s own bounded
        # ``feature_status_lock`` acquisition (``review/cycle.py``) and THAT
        # wedged instead. Without this clause, this exception propagated
        # uncaught past the queue's own ``VerdictSaveBusy`` handling above --
        # an unhandled crash, not the truthful non-durable failure every
        # OTHER busy path here produces.
        _raise_verdict_busy_failure(
            reason=_DURABILITY_REASON_FEATURE_STATUS_LOCK_BUSY, cause=exc
        )

    if st.skip_target_branch_commit:
        local = review_cycle.persistence
        signal = _build_durability_signal(
            review_cycle,
            outcome=VerdictPersistenceOutcome(
                classification="persistence_failed",
                verdict_durably_persisted=False,
                evidence_ref=local.evidence_ref,
                destination_ref=None,
                reason=_DURABILITY_REASON_PROTECTED_TARGET_BRANCH,
                message=(
                    "Automatic verdict evidence could not be committed because "
                    "the governed destination branch is protected; complete "
                    f"evidence is retained at {local.evidence_ref}."
                ),
            ),
        )
        raise VerdictPersistenceFailure(signal)

    persistence = getattr(review_cycle, "persistence", None)
    if not isinstance(persistence, VerdictPersistenceOutcome):
        persistence = VerdictPersistenceOutcome(
            classification="durable",
            verdict_durably_persisted=True,
            evidence_ref=str(review_cycle.artifact_path),
            destination_ref=st.target_branch or "injected-test-destination",
            reason=None,
            message="Injected compatibility writer reported durable evidence.",
        )
    signal = _build_durability_signal(review_cycle, outcome=persistence)
    if not signal.durably_persisted:
        raise VerdictPersistenceFailure(signal)
    return signal


_DURABILITY_NOTICE_BY_REASON = {
    _DURABILITY_REASON_NO_AUTO_COMMIT: "--no-auto-commit",
    _DURABILITY_REASON_PROTECTED_TARGET_BRANCH: (
        "protected target branch under coordination topology"
    ),
}


def _announce_verdict_durability_gap(
    st: _MoveTaskState, signal: VerdictDurabilitySignal
) -> None:
    """Print the human-readable half of the durability signal (T049/T050).

    Guarded by ``json_output`` following this module's established pattern
    (:func:`persist_arbiter_override_decision`'s ``if not json_output:``
    console lines) -- a machine consumer reads the (currently unwired,
    see :class:`VerdictDurabilitySignal`) ``--json`` key instead.
    """
    if st.json_output or signal.durably_persisted or signal.skip_reason is None:
        return
    from specify_cli.cli.commands.agent import tasks as _tasks

    reason_text = _DURABILITY_NOTICE_BY_REASON[signal.skip_reason]
    _tasks.console.print(
        f"[yellow]Note:[/yellow] review-cycle verdict for {st.task_id} was "
        f"written but NOT committed ({reason_text})."
    )


def resolve_review_verdict_facts(
    wp_path: Path,
) -> tuple[str | None, Path | None, str | None]:
    """Resolve the latest review verdict for an approval-lane move (FR-002/D-PLAN-9).

    Extracted verbatim (site 1) from the inline block formerly inside
    ``_mt_gather_review_facts`` (``tasks_move_task.py:557``), guarded there by
    ``target_lane in (Lane.APPROVED, Lane.DONE)`` — the guard itself stays at
    the call site; this function is the unconditional resolve step.
    Returns ``(review_verdict, verdict_artifact_path, review_artifact_name)``.

    **WP05 (verdict-seam-write-unification-01KZ9Q35, T023) repoint:** this
    used to parse ``review-cycle-N.md`` frontmatter
    (``_get_latest_review_cycle_verdict``) — the exact fail-open surface this
    mission closes. Now resolves the event authority
    (:func:`~specify_cli.status.event_sourced_review_result`) and translates
    its three-way :class:`~specify_cli.status.ReviewResultLookup` outcome into
    the SAME three-value shape the two unowned callers
    (``tasks_move_task.py``'s ``_mt_gather_review_facts``, ``tasks_transition_
    core.py``'s ``_guard_rejected_verdict``/``_authorize_review_override``)
    already destructure, so neither needs a companion edit:

    - **absent** (``slot_present=False``) -> ``(None, None, None)`` — no
      verdict recorded; the caller's guard already treats
      ``review_artifact_name is None`` as "nothing to refuse on" (G2: absent
      is "no approval [blocker]", not a crash).
    - **damaged** (``slot_present=True, result=None``) -> a non-``None``
      synthetic ``review_artifact_name`` paired with ``review_verdict=None``
      — this is deliberate, not an oversight: the caller's guard refuses on
      exactly that combination ("no parseable review verdict"), so a
      corrupted event-log slot must still fail closed instead of silently
      passing as "no artifact at all" (SC-004).
    - **present** -> the artifact-domain verdict
      (:func:`~specify_cli.status.verdict_vocab.to_artifact_verdict`, mapping
      ``changes_requested`` back to ``rejected`` for the caller's existing
      string comparison) plus the ORIGINAL write-time artifact path
      (``ReviewResult.feedback_path``, threaded back from
      :func:`~specify_cli.review.cycle.create_rejected_review_cycle`'s own
      write) when present, else a directory-anchored synthetic path — never
      re-reads or re-parses ``review-cycle-N.md`` frontmatter for this.

    The event log is read from the **STATUS_STATE-authoritative** feature dir
    (:func:`_resolve_verdict_read_feature_dir`), not the PRIMARY
    ``wp_path.parent.parent`` alone — under a coordination topology the event
    log lives on the coord worktree, so reading the PRIMARY dir would find an
    always-empty log and treat every verdict as absent (the exact hazard
    ``_review_cycle_wp_dir``'s own docstring discloses this function used to
    carry, now fixed as part of this WP's repoint).
    """
    verdict_wp_dir = _resolve_verdict_wp_dir(wp_path)
    wp_id = _wp_id_from_stem(wp_path.stem)
    status_read_feature_dir = _resolve_verdict_read_feature_dir(wp_path)
    lookup = event_sourced_review_result(status_read_feature_dir, wp_id)
    if not lookup.slot_present:
        return None, None, None
    if lookup.result is None:
        synthetic_path = verdict_wp_dir / "review-cycle-damaged-event-record.md"
        return None, synthetic_path, synthetic_path.name
    review_verdict = to_artifact_verdict(lookup.result.verdict)
    artifact_path = (
        Path(lookup.result.feedback_path)
        if lookup.result.feedback_path
        else verdict_wp_dir / "review-cycle-event-recorded.md"
    )
    return review_verdict, artifact_path, artifact_path.name


def _resolve_verdict_read_feature_dir(wp_path: Path) -> Path:
    """Resolve the STATUS_STATE-authoritative feature dir for *wp_path*'s mission.

    Mirrors ``post_merge/review_artifact_consistency.py::
    _resolve_lane_state_read_dir``'s own convention: the event log
    (``status.events.jsonl``) is COORD-partition under a coordination
    topology, PRIMARY otherwise — resolving it through the kind-aware
    placement seam (rather than trusting ``wp_path.parent.parent`` — the
    PRIMARY mission dir every caller of this function happens to hold) is
    what makes the read agree with wherever
    :func:`~specify_cli.status.emit_status_transition` actually wrote the
    ``review_result`` slot.

    Degrades to the PRIMARY ``feature_dir`` unchanged when no workspace root
    is derivable (a bare non-git test fixture) — the same "flat self-home"
    degrade :func:`_resolve_verdict_wp_dir` uses for the identical edge case.
    """
    from mission_runtime import MissionArtifactKind, placement_seam

    from specify_cli.core.paths import WorkspaceRootNotFound, resolve_canonical_root

    feature_dir = wp_path.parent.parent
    try:
        main_repo_root = resolve_canonical_root(feature_dir)
    except WorkspaceRootNotFound:
        return feature_dir

    mission_slug = feature_dir.name
    resolved: Path = placement_seam(main_repo_root, mission_slug).read_dir(
        MissionArtifactKind.STATUS_STATE
    )
    return resolved


def _resolve_verdict_wp_dir(wp_path: Path) -> Path:
    """Resolve the review-cycle directory for the WP task file at *wp_path*.

    ``wp_path`` is a REAL, on-disk file (``locate_work_package`` finds it via
    a ``tasks/*.md`` glob filtered by the SAME separator-anchored regex T057
    introduced for ``_resolve_wp_slug`` -- ``task_utils/support.py``'s
    ``wp_pattern = re.compile(rf"^{{wp_id}}(?:[-_.]|\\.md$)")``), so
    ``wp_path.stem`` IS ALREADY the correct, fully-resolved slug -- never a
    bare task id. Calling ``_resolve_wp_slug`` again on a task id
    reverse-extracted from that stem would be a redundant, strictly riskier
    round-trip (re-deriving a bare id from an already-correct slug, then
    re-scanning the same ``tasks/`` directory with the same regex, to arrive
    at the identical answer) -- not genuine consolidation. This function
    therefore reuses the already-known ``wp_path.stem`` directly and routes
    ONLY through :func:`~specify_cli.review.cycle._review_cycle_wp_dir` (the
    T058 owner function actually responsible for directory resolution) at
    its DEFAULT ``kind`` (``WORK_PACKAGE_TASK`` -- T062 voided the
    COORD-wins flip; this site does not opt in either).

    Degrades to the historical flat join (``wp_path.parent / wp_path.stem``)
    when no workspace root is derivable from ``wp_path``'s mission directory
    (a bare test fixture with no git ancestor -- this module's own
    ``tests/specify_cli/cli/commands/agent/test_tasks_move_task_seam.py``
    exercises exactly this shape) -- the SAME "flat self-home" degrade
    ``post_merge/review_artifact_consistency.py::_resolve_partition_read_dir``
    uses for the identical edge case, and byte-identical to this function's
    own pre-fix behaviour for that case, so those pre-existing tests are
    unaffected.
    """
    from specify_cli.core.paths import WorkspaceRootNotFound, resolve_canonical_root

    feature_dir = wp_path.parent.parent
    try:
        main_repo_root = resolve_canonical_root(feature_dir)
    except WorkspaceRootNotFound:
        return wp_path.parent / wp_path.stem

    mission_slug = feature_dir.name
    resolved: Path = _review_cycle_wp_dir(main_repo_root, mission_slug, wp_path.stem)
    return resolved


def persist_review_override_before_guard(st: _MoveTaskState) -> None:
    """OLD-timing review-artifact override persist (FR-004 partial-write-on-refusal).

    Extracted verbatim (site 2) from ``_mt_fire_override_persist``
    (``tasks_move_task.py:635``), which is now a thin forwarder onto this
    function (frozen ``tasks.<name>`` compat symbol — see the module
    docstring). Fires before the guard sequence so a LATER guard's exit-1
    refusal still leaves the override on disk, reproducing the un-refactored
    command's timing.
    """
    assert st.request is not None
    if not (override_persist_signal(st.request) and st.verdict_artifact_path is not None):
        return
    override_reason = st.note.strip() if isinstance(st.note, str) else ""
    # FR-009 (WP09): a single topology-resolved ``InnerStateChanged`` ``review``
    # emit is authoritative for both the primary and coord worktrees, so the
    # former ``_persist_review_artifact_override_in_coord`` mirror is collapsed
    # away — one emit, no coord frontmatter stamp.
    _persist_review_artifact_override(
        st.verdict_artifact_path,
        repo_root=st.main_repo_root,
        wp_id=st.task_id,
        actor=st.agent or "operator",
        reason=override_reason,
    )


def _persist_approved_review_cycle(
    st: _MoveTaskState, ports: TasksPorts
) -> VerdictDurabilitySignal | None:
    """T005: fire the generalized writer on the ordinary approval path.

    Only when the WP's current highest-numbered review-cycle artifact is
    ``rejected`` — a first-ever cycle (no prior artifact) or an
    already-approved latest are both no-ops (FR-001 closes the stale-
    rejection gap; it does not write a redundant/duplicate approval). Returns
    ``None`` for that no-op case (nothing was written, durable or otherwise);
    returns a populated :class:`VerdictDurabilitySignal` whenever a write was
    actually attempted (T049/T050).

    De-nested (site 3a) from the closure of the same name formerly inside
    ``_mt_finalize_plan`` (``tasks_move_task.py:1712-1757``) per the DM ruling
    CONDITION 2: its captured locals (``st``, ``ports``) are threaded in as
    explicit parameters — a mechanical parameter-passing change, not a rename
    of the function's own name (kept identical).

    T055 (FR-011, WP12, arbiter-override-retirement): ``_mt_finalize_plan``
    calls this function for EVERY ``target_lane in (APPROVED, DONE)`` move,
    with no arbiter-aware guard of its own (that guard lives here, in this
    WP's owned file, not in the unowned caller). An arbiter override targeting
    ``approved``/``done`` (``--force`` over a standing rejection,
    ``st.request.is_arbiter_override``) must never ALSO be recorded as an
    approval — I-4 (data-model.md): "an arbiter override is never recorded as
    an approval, in either store." The naive fix (suppressing only this
    write) would leave nothing recording the arbitration; that is NOT what
    happens here, because ``persist_arbiter_override_decision`` /
    ``persist_arbiter_decision`` already durably emitted the ``ReviewOverride``
    event earlier in the SAME command, at ``_mt_run_decision``'s pass 2
    (``_mt_fire_arbiter_persist``, which runs before ``_mt_finalize_plan``) —
    this early-return only stops the SECOND, fabricated representation from
    being written alongside the real one. Guarded by ``st.request is not
    None`` rather than asserted: several existing unit tests (outside this
    WP's ``owned_files``) call this function directly against a hand-built
    ``_MoveTaskState`` that never populates ``.request`` (the incumbent body
    never read it either) — in the REAL ``_mt_finalize_plan`` call path
    ``st.request`` is always populated by this point (a ``st.decision`` this
    caller already asserts non-``None`` cannot exist without one), so this
    guard is a no-op in production and only avoids breaking those tests'
    unrelated fixtures.

    **WP05 (verdict-seam-write-unification-01KZ9Q35, T023) repoint:** the
    "is the current verdict a rejection" probe used to parse
    ``review-cycle-N.md`` frontmatter (``latest_review_artifact_verdict``,
    D-PLAN-9's "approval-write probe") — now resolves the event authority
    (:func:`~specify_cli.status.event_sourced_review_result`) from
    ``st.feature_dir`` (the STATUS_STATE-authoritative dir this state already
    carries — coord-aware, unlike a raw ``main_repo_root``-anchored join).
    Absent or damaged both no-op here (fail closed on the SAFE side for a
    WRITE decision: when this probe cannot establish "the current verdict IS
    a rejection", it must not synthesize a redundant/fabricated approval —
    matching the pre-existing no-op contract for "no prior artifact" /
    "already approved").
    """
    if st.request is not None and st.request.is_arbiter_override:
        return None
    wp_slug = (
        st.wp.path.stem
        if st.owned is not None and st.wp is not None
        else _resolve_wp_slug(st.main_repo_root, st.mission_slug, st.task_id)
    )
    lookup = event_sourced_review_result(st.feature_dir, st.task_id)
    # FR-007 (T2 / IC-04): a malformed/damaged event-sourced slot
    # (``slot_present=True, result=None``) stays a no-op, UNCHANGED — the
    # reader (``event_sourced_review_result``) already fails closed rather
    # than fabricate a verdict, and this writer must not paper over that
    # ambiguity with a synthesized approval write.
    if lookup.slot_present and lookup.result is None:
        return None
    # :852 idempotency (unchanged, PRESERVED): the current event-sourced
    # verdict is already something other than a stale rejection (i.e.
    # already ``approved``) -- never a redundant/duplicate write.
    if lookup.result is not None and lookup.result.verdict != "changes_requested":
        return None
    # FR-007 (T2, brownfield gap closed): a genuine first-pass approval —
    # NO prior event-sourced verdict slot at all (``lookup.slot_present``
    # False) — used to be an unconditional no-op here, so a first-pass
    # approve authored NO ``review-cycle-N.md`` evidence artifact at all
    # (SC-006). It now falls through to the SAME write this function
    # already used for the "stale rejection -> fresh approval" flip,
    # reusing ``create_rejected_review_cycle(..., verdict="approved")`` —
    # already verdict-symmetric — rather than a second writer.
    #
    # Real reviewer_agent (matches ``_mt_plan_review_result``'s own
    # fallback chain) — never the literal "unknown" for a genuine
    # approval.
    reviewer_agent = (st.reviewer or st.agent or st.actor or "unknown").strip() or "unknown"
    # #4327: pointer-only -- ``--approval-ref`` or the synthetic ``approval:<WP>``
    # token, never the operator's ``--note`` prose (the note stays whole in the
    # emitted event's ``reason``).
    approval_reference = (st.approval_ref or synthetic_approval_ref(st.task_id)).strip() or synthetic_approval_ref(st.task_id)
    # SC-006: the artifact carries at least a reproduction_command —
    # auto-derived from the decision already made (NFR-005), never a new
    # hand-filled field: the exact ``move-task`` invocation that reproduces
    # this approval. #4670: carries the resolved ``reviewer_agent`` too
    # (the same identity this write already attributes the approval to)
    # so a replay of this exact command reproduces the SAME attribution
    # instead of silently falling back to whoever re-runs it.
    reproduction_command = (
        f"spec-kitty agent tasks move-task {st.task_id} --to approved "
        f"--mission {st.mission_slug} --agent {reviewer_agent}"
    )
    # M1 (adversarial squad, PR #3156): the approval body is synthesized
    # by THIS caller, not supplied by a reviewer — pass it via ``body=``
    # rather than a throwaway ``feedback_source`` file. This both drops
    # the tempfile dance entirely and keeps the write off
    # ``_guard_feedback_source_provenance``'s content-identity arm, which
    # exists to police externally-supplied feedback files (#990/#2996(b))
    # and produces a false collision here: a repeated ``--note "Review
    # passed"`` approval synthesizes the SAME deterministic body every
    # time, which used to be indistinguishable from a reviewer replaying
    # a prior cycle's content.
    def _create(commit_router: CoordCommitRouter | None) -> CreatedRejectedReviewCycle:
        return create_rejected_review_cycle(
            main_repo_root=st.main_repo_root,
            mission_slug=st.mission_slug,
            wp_id=st.task_id,
            wp_slug=wp_slug,
            body=f"Approved by {reviewer_agent}: {approval_reference}\n",
            reviewer_agent=reviewer_agent,
            verdict="approved",
            commit_router=commit_router,
            reproduction_command=reproduction_command,
            effective_root=st.owned.root if st.owned else None,
        )

    durability_signal = _persist_review_cycle_with_queue(st, ports, _create)
    _announce_verdict_durability_gap(st, durability_signal)
    return durability_signal


def persist_rejected_review_cycle_for_rollback(
    st: _MoveTaskState, ports: TasksPorts
) -> VerdictDurabilitySignal:
    """Persist the rejection review cycle for a planned-rollback transition.

    Extracted (site 3b) from the ``if decision.planned_rollback and
    st.resolved_feedback_source is not None:`` block formerly inside
    ``_mt_finalize_plan`` (``tasks_move_task.py:1759-1772``). The guard itself
    stays at the call site (unchanged); this function is the unconditional
    body, so the caller must only invoke it once the guard has already
    confirmed ``st.resolved_feedback_source is not None`` — asserted here to
    satisfy strict typing across the function boundary the guard used to
    narrow inline.
    """
    assert st.resolved_feedback_source is not None

    def _create(commit_router: CoordCommitRouter | None) -> CreatedRejectedReviewCycle:
        return create_rejected_review_cycle(
            main_repo_root=st.main_repo_root,
            mission_slug=st.mission_slug,
            wp_id=st.task_id,
            wp_slug=(
                st.wp.path.stem
                if st.owned is not None and st.wp is not None
                else _resolve_wp_slug(st.main_repo_root, st.mission_slug, st.task_id)
            ),
            feedback_source=st.resolved_feedback_source,
            reviewer_agent=st.agent or "unknown",
            commit_router=commit_router,
            effective_root=st.owned.root if st.owned else None,
        )

    durability_signal = _persist_review_cycle_with_queue(st, ports, _create)
    review_cycle = durability_signal.review_cycle
    assert review_cycle is not None
    st.review_feedback_pointer = review_cycle.pointer
    st.rejected_review_result = review_cycle.review_result
    _announce_verdict_durability_gap(st, durability_signal)
    return durability_signal


def persist_arbiter_override_decision(
    *,
    feature_dir: Path,
    wp_id: str,
    review_ref: str | None,
    decision: ArbiterDecision,
    category: ArbiterCategory,
    explanation: str,
    json_output: bool,
    main_repo_root: Path,
) -> None:
    """The OLD-timing arbiter-decision persist (FR-004 partial-write-on-refusal).

    FR-016 (WP07, arbiter-root-threading): ``main_repo_root`` is the caller's
    already-resolved repo root (``_run_arbiter_override``'s own parameter of
    the same name) and is threaded straight through to :func:`persist_arbiter_
    decision` as its now-required ``repo_root``. This function never infers
    it — under a coordination topology, ``feature_dir`` may already be the
    coord-husk mission dir, so any inference from it (e.g.
    ``feature_dir.parent.parent``) would land on the coord WORKTREE root, not
    the real ``main_repo_root`` the downstream event-sourced write needs.

    Extracted verbatim (site 4) from ``_run_arbiter_override``
    (``tasks_move_task.py:2540-2552``). ``_run_arbiter_override`` itself stays
    in ``tasks_move_task.py`` (frozen ``tasks.<name>`` compat symbol — see the
    module docstring) and now calls straight into this function instead of
    running the try/except inline. ``persist_arbiter_decision`` is imported
    lazily (function-local) rather than at module scope: the caller only
    reaches this function after already successfully importing its two
    siblings from the SAME ``review.arbiter`` module (guarded by the caller's
    own ``except ImportError``), so the import here is guaranteed to succeed
    — but keeping it lazy avoids adding a module-scope dependency this module
    does not otherwise require.

    T054 (FR-009/FR-010/FR-011, WP12): the incumbent's exception handling —
    ``except Exception as _arb_err: if not json_output: console.print(...)``
    — is DELETED, not merely relocated. Two independent defects made this the
    wrong shape: (1) the ``if not json_output:`` guard meant a persistence
    failure produced literally NO output under ``--json`` — silent data loss
    an operator/script had no way to detect (spec.md User Story 2 Acceptance
    Scenario 3: "an override whose persistence fails... the failure is
    surfaced — never swallowed into a warning"); (2) once T051/T052 retire
    the frontmatter/JSON-sidecar fallbacks, the event-sourced ``ReviewOverride``
    emit inside :func:`persist_arbiter_decision` is the ONLY durable record of
    the override — there is no best-effort secondary representation left to
    fall back on, so a failure here is not the "warn and continue" case
    ``move_task`` reserves for genuinely best-effort side effects. This
    function therefore no longer catches the exception at all: it propagates
    to ``tasks_move_task.py``'s existing outer ``except Exception as e:``
    (``_do_move_task``, outside this WP's ``owned_files`` — but its handler
    itself is UNCHANGED), which already reports failures correctly under BOTH
    ``--json`` (a structured error envelope via ``_output_error``) and plain
    console output (a red ``Error:`` line) — reusing that already-correct,
    already-shared machinery rather than duplicating a second reporting path
    here.
    """
    from specify_cli.cli.commands.agent import tasks as _tasks
    from specify_cli.review.arbiter import persist_arbiter_decision

    arb_path = persist_arbiter_decision(
        feature_dir=feature_dir,
        wp_id=wp_id,
        review_ref=review_ref,
        decision=decision,
        repo_root=main_repo_root,
    )
    if not json_output:
        _tasks.console.print(
            f"[yellow]Arbiter override recorded:[/yellow] [bold]{category}[/bold] — {explanation}"
        )
        _tasks.console.print(f"[dim]  Decision persisted: {arb_path}[/dim]")
