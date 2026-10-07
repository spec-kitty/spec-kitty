"""Lane-based merge executor for the merge seam.

Mission #2057 (decompose ``cli/commands/merge.py``) — IC-10 / WP10 (HIGH-RISK).

Relocates ``_run_lane_based_consolidation`` (the global-lock wrapper) and the CC-102
``_run_lane_based_consolidation_locked`` driver out of the command shim, decomposing the
driver into phase helpers (each <= 15 CC) that thread shared mutable state via
the :class:`_MergeRunState` dataclass — never closures (INV-3). The decomposition
preserves, byte-for-byte:

* INV-5 — the #1827 ordering: baseline RECORD (post-target-merge, pre-
  bookkeeping-commit, in ``_phase_capture_and_baseline``) → bookkeeping
  ``safe_commit`` → baseline ASSERT (post-commit) — the commit and the assert
  run in ``_phase_commit_and_assert`` in exactly that order.
* INV-6 — the ``restore_generated_artifact_snapshots(...)``-then-reraise rollback
  sites, each with identical exception-class scoping.

Lazy imports inside the phases stay lazy (C-007). One-way import: this module
never imports the command shim.

Epic #2026 split the phase helpers out of this module along the consolidation
phases; this module keeps the orchestration only: the unlocked entry and lock
(:func:`_run_lane_based_consolidation`), the locked driver with its single
post-mutation rollback door (:func:`_run_lane_based_consolidation_locked`,
:func:`_report_rollback`) and operator-attestation recording. The unlocked entry
still runs its own inline pre-lock checks; ``entry_preflight`` holds only the
helpers it calls. Module map:

* ``run_state``         -- run record, post-tip recorder, snapshot capture, shared wording,
                           shared errors and helpers used by more than one phase
* ``entry_preflight``   -- unlocked pre-lock refusals (status dir, lanes.json, protected target)
* ``resume_recovery``   -- behind-own-HEAD lag advice and in-place resume repair
* ``phase_claim``       -- merge-ready gates, resume anchors, reconciliation claim
* ``phase_advance``     -- lanes -> mission branch, bake, mission -> target
* ``coord_strand``      -- coordination strand mark / heal / byte-restore
* ``phase_bookkeeping`` -- mission_number on target, done + projection, commit + asserts
* ``phase_gate``        -- reconciliation gate and squash projection proof
* ``phase_teardown``    -- lane cleanup and the coordination triple
* ``phase_finalize``    -- stale scan, push, summary
"""

from __future__ import annotations

import functools
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer

if TYPE_CHECKING:
    from specify_cli.lanes.models import LanesManifest

from specify_cli.cli.console import console
from specify_cli.core.constants import KITTIFY_DIR
from specify_cli.core.paths import (
    MissionMetaReadError,
    get_main_repo_root,
    resolve_merge_retention,
)
from specify_cli.git.ref_advance import reporting_advance_intents
from specify_cli.git.sparse_checkout import require_no_sparse_checkout

from specify_cli.lanes.persistence import read_lanes_json
from specify_cli.consolidation._constants import (
    GLOBAL_MERGE_LOCK_ID as _GLOBAL_MERGE_LOCK_ID,
)
from specify_cli.consolidation.bookkeeping_projection import (
    _resolve_ref_sha,
)
from specify_cli.consolidation.config import MergeStrategy
from specify_cli.consolidation.done_bookkeeping import (
    _resolve_merge_actor,
    acceptably_canceled_wp_ids,
)
from specify_cli.consolidation.origin_gate import check_origin_before_status_dir
from specify_cli.git.origin_freshness import OriginFreshnessRefused
from specify_cli.consolidation.preflight import (
    _check_mission_branch,
    _effective_push_requested,
    _enforce_planning_artifact_target_branch,
    _enforce_review_artifact_consistency,
)
from specify_cli.consolidation import rollback
from specify_cli.consolidation.push_preflight import _enforce_target_branch_sync_preflight
from specify_cli.consolidation.resolve import _load_or_create_merge_state
from specify_cli.consolidation.state import (
    MergeLockError,
    ConsolidationState,
    acquire_merge_lock,
    load_state,
    reconciliation_passed_for_tip,
    release_merge_lock,
    save_state,
)
from specify_cli.mission_metadata import resolve_mission_identity
from mission_runtime import (
    MissionArtifactKind,
    PlacementSeam,
    placement_seam,
)
from specify_cli.consolidation.coord_strand import (
    _heal_pending_coord_reconcile,
)
from specify_cli.consolidation.entry_preflight import (
    _refuse_protected_status_target_or_continue,
    _require_lanes_json_naming_mission_branch,
    _resolve_run_status_dir,
    _synthesize_no_lane_manifest,
)
from specify_cli.consolidation.phase_advance import (
    _capture_pre_target_gate_artifacts,
    _phase_bake_and_pre_target_done,
    _phase_baseline_and_surface,
    _phase_merge_lanes,
    _phase_mission_to_target,
    _switch_write_checkout_after_single_branch_landing,
)
from specify_cli.consolidation.phase_bookkeeping import (
    _phase_capture_and_baseline,
    _phase_commit_and_assert,
    _phase_porcelain_invariant,
    _phase_record_done_and_project,
)
from specify_cli.consolidation.phase_claim import (
    _capture_reconciliation_claim,
    _clear_fresh_record_on_pre_mutation_exit,
    _exit_unexplained_branch_move,
    _persist_executed_strategy,
    _verified_landing_exempt_branches,
    _phase_gates_and_state,
)
from specify_cli.consolidation.phase_finalize import (
    _phase_dossier_and_stale,
    _phase_finalize_and_summary,
    _phase_push,
)
from specify_cli.consolidation.phase_gate import (
    _phase_reconcile_before_teardown,
)
from specify_cli.consolidation.phase_teardown import (
    _phase_cleanup_worktrees_and_branches,
)
from specify_cli.consolidation.resume_recovery import (
    _pre_mutation_safety_preflight_with_recovery,
)
from specify_cli.consolidation.run_state import (
    _MergeRunState,
    _resume_reconciliation_already_passed,
    _status_surface_ref,
)


def _pending_heal_branch(state: ConsolidationState) -> str | None:
    """The coordination branch a ``pending_coord_reconcile`` marker names; the resume-start heal owns it."""
    marker = state.pending_coord_reconcile
    return str(marker["coord_ref"]) if marker and marker.get("coord_ref") else None


def _refuse_unexplained_branch_moves(main_repo: Path, canonical_id: str) -> dict[str, str]:
    """Read-only FR-005 pre-check; returns the run-movable branches' tips at its end.

    The returned tips are the "before" tips of the operator attestations that run
    right after it (:func:`_own_moves_after_step`); they never make a later move
    this process's own by themselves.

    Runs before the operator attestations and the coord-strand heal, so a re-run
    or ``--resume`` facing a move its record cannot explain refuses with
    ``UNEXPLAINED_BRANCH_MOVE`` before anything could move a branch. Nothing is
    written: the record is loaded read-only and never saved. No record, or a
    record without a snapshot (zero progress), has nothing to check (``{}``).

    The branch a ``pending_coord_reconcile`` marker names is left to the heal
    (orchestrator ruling, WP03): it is settled after a heal that clears the
    marker, and otherwise ``begin_attempt`` refuses it at the claim.

    A record whose reconciliation PASS still holds for the live target tip (a
    verified landing, mid-teardown; #5021 / #5570) exempts only the target and
    coordination rows (F1, :func:`_verified_landing_exempt_branches`): the
    rollback authority never rolls such a landing back (FR-011), and a late
    coordination commit is landed and compare-and-swap guarded by the teardown.
    An unexplained mission-branch move still refuses, because the teardown would
    delete that branch against its live tip.
    """
    state = load_state(main_repo, canonical_id)
    if state is None or not state.pre_mutation_refs:
        return {}
    healed = _pending_heal_branch(state)
    rows = [row for row in rollback.unexplained_branches(main_repo, state) if row[0] != healed]
    if rows and reconciliation_passed_for_tip(state, _resolve_ref_sha(main_repo, state.target_branch) or ""):
        exempt = _verified_landing_exempt_branches(state, None)
        rows = [row for row in rows if row[0] not in exempt]
    if rows:
        _exit_unexplained_branch_move(rows)
    return {branch: tip for branch, tip in rollback.movable_branch_tips(main_repo, state).items() if tip is not None}


def _settle_healed_coordination_branch(run: _MergeRunState, marker: Mapping[str, Any] | None) -> None:
    """Orchestrator ruling (WP03): a heal that cleared its marker settles the coordination branch it names.

    The heal (``repair_coord_strand``) reverted this run's stranded ``done``
    forward, so nothing of this run remains unrestored on that branch. Settling
    it, and dropping it from this process's own pre-claim moves, lets
    ``begin_attempt`` classify it as a settled branch: it re-anchors to the live
    tip (ADR A2) and keeps the other actor's commit. A heal that could not clear the marker leaves the branch
    unsettled, and the claim refuses it (``UNEXPLAINED_BRANCH_MOVE``).
    """
    if not marker or run.state.pending_coord_reconcile is not None:
        return
    branch = str(marker["coord_ref"])
    rollback.settle_branch(run.main_repo, run.state, branch)
    run.own_pre_claim_moves.pop(branch, None)


def _own_moves_after_step(
    main_repo: Path,
    own_moves: Mapping[str, rollback.OwnMove],
    before: Mapping[str, str | None],
    *,
    writes: Iterable[str | None],
) -> dict[str, rollback.OwnMove]:
    """Fold one pre-claim step into this process's own moves: only a branch the step writes whose tip changed since ``before``."""
    branches = [branch for branch in writes if branch is not None and branch in before]
    if not branches:
        return dict(own_moves)
    return rollback.own_moves_across(own_moves, before, rollback.branch_tips(main_repo, branches), writes=branches)


def _tips_before_heal(run: _MergeRunState, marker: Mapping[str, Any] | None) -> dict[str, str | None]:
    """The run-movable tips immediately before the resume-start heal; ``{}`` when no heal runs or nothing is snapshotted."""
    return rollback.movable_branch_tips(run.main_repo, run.state) if marker and run.state.pre_mutation_refs else {}


def _note_advance_intent(run: _MergeRunState, branch: str, old_sha: str, new_sha: str) -> None:
    """The door span's advance-intent sink (FR-006): persist before the CAS write; a failure fails the advance closed."""
    rollback.note_advance_intent(run.main_repo, run.state, branch, old_sha, new_sha)


def _record_operator_attestations(
    main_repo: Path,
    mission_slug: str,
    *,
    wp_ids: tuple[str, ...],
    reason: str | None,
    acceptably_canceled: frozenset[str],
    approved_wp_ids: tuple[str, ...] = (),
    feature_dir: Path | None = None,
    lanes_manifest: LanesManifest | None = None,
) -> tuple[str, ...]:
    """Validate and record ``--attest-canceled-superseded`` (FR-012) and ``--attest-approved-reviewed`` (#5668), before any mutation.

    Returns the WP ids whose attestation was recorded (``()`` when none was requested).
    Both requests are validated before either is recorded, so a refusal records nothing.

    Refuses (exit 1, nothing recorded) a WP that is not canceled with operator
    provenance. Every explicit ``--attest-canceled-superseded`` records a FRESH
    attestation, even for a WP already attested: each is a new operator act
    with its own reason and a new ``lane_head`` stamp, and that stamp is what
    bounds the closed-world exemption (a straggler landed after an earlier
    attestation is covered only once the operator attests again). Written through the canonical transactional status seam
    (``canceled_attestation.record_canceled_superseded_attestation``).
    """
    if not (wp_ids or approved_wp_ids):
        return ()
    approved_plan = _plan_approved_attestations(main_repo, feature_dir, lanes_manifest, approved_wp_ids, reason, acceptably_canceled)
    canceled = _record_canceled_attestations(main_repo, mission_slug, wp_ids=wp_ids, reason=reason, acceptably_canceled=acceptably_canceled)
    return canceled + _record_approved_attestations(main_repo, mission_slug, approved_plan, reason)


def _record_canceled_attestations(
    main_repo: Path,
    mission_slug: str,
    *,
    wp_ids: tuple[str, ...],
    reason: str | None,
    acceptably_canceled: frozenset[str],
) -> tuple[str, ...]:
    """Validate and record ``--attest-canceled-superseded`` (FR-012); ``()`` when none was requested."""
    if not wp_ids:
        return ()
    from specify_cli.consolidation.canceled_attestation import (
        AttestationError,
        record_canceled_superseded_attestation,
        validate_attestation_request,
    )
    from specify_cli.consolidation.done_bookkeeping import _resolve_merge_actor

    try:
        requested: tuple[str, ...] = validate_attestation_request(wp_ids, reason, acceptably_canceled=acceptably_canceled)
    except AttestationError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
    primary_feature_dir = placement_seam(main_repo, mission_slug).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK)
    actor = _resolve_merge_actor(main_repo)
    for wp_id in requested:
        record_canceled_superseded_attestation(
            repo_root=main_repo,
            feature_dir=primary_feature_dir,
            mission_slug=mission_slug,
            wp_id=wp_id,
            reason=reason or "",
            actor=actor,
        )
        console.print(f"[yellow]⚠️  Operator attestation recorded for canceled {wp_id} by {actor}:[/yellow] {(reason or '').strip()}")
    return requested


def _plan_approved_attestations(
    main_repo: Path,
    feature_dir: Path | None,
    lanes_manifest: LanesManifest | None,
    wp_ids: tuple[str, ...],
    reason: str | None,
    excluded_canceled_wp_ids: frozenset[str],
) -> dict[str, str]:
    """Validate ``--attest-approved-reviewed`` against the status log: WP id -> current lane (exit 1, nothing recorded, when refused)."""
    if not wp_ids or feature_dir is None or lanes_manifest is None:
        return {}
    from specify_cli.consolidation.approved_attestation import plan_approved_attestations
    from specify_cli.consolidation.canceled_attestation import AttestationError

    try:
        return plan_approved_attestations(main_repo, feature_dir, lanes_manifest, wp_ids, reason, excluded_canceled_wp_ids=excluded_canceled_wp_ids)
    except AttestationError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc


def _record_approved_attestations(main_repo: Path, mission_slug: str, plan: dict[str, str], reason: str | None) -> tuple[str, ...]:
    """Record the validated ``--attest-approved-reviewed`` requests (#5668); ``()`` when there are none."""
    if not plan:
        return ()
    from specify_cli.consolidation.approved_attestation import record_approved_reviewed_attestation
    from specify_cli.consolidation.done_bookkeeping import _resolve_merge_actor

    primary_feature_dir = placement_seam(main_repo, mission_slug).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK)
    actor = _resolve_merge_actor(main_repo)
    for wp_id, current_lane in plan.items():
        record_approved_reviewed_attestation(
            repo_root=main_repo,
            feature_dir=primary_feature_dir,
            mission_slug=mission_slug,
            wp_id=wp_id,
            current_lane=current_lane,
            reason=reason or "",
            actor=actor,
        )
        console.print(f"[yellow]⚠️  Operator attestation recorded for approved {wp_id} by {actor}:[/yellow] {(reason or '').strip()}")
    return tuple(plan)


def _run_lane_based_consolidation_locked(
    main_repo: Path,
    mission_slug: str,
    canonical_id: str,
    canonical_mission_id: str | None,
    feature_dir: Path,
    lanes_manifest: LanesManifest,
    *,
    push: bool,
    delete_branch: bool,
    remove_worktree: bool,
    teardown_coordination: bool = False,
    strategy: MergeStrategy = MergeStrategy.SQUASH,
    assume_yes: bool = False,
    skip_review_artifact_check: bool = False,
    skip_note: str | None = None,
    skip_lanes: bool = False,
    attest_canceled_superseded: tuple[str, ...] = (),
    attest_reason: str | None = None,
    attest_approved_reviewed: tuple[str, ...] = (),
) -> None:
    """Inner merge flow, called with the global merge lock held.

    Linear phase caller: each phase mutates the shared :class:`_MergeRunState`.
    The #1827 ordering (INV-5) and the snapshot-restore-on-exception sites (INV-6)
    are preserved exactly within and across the phase boundaries.
    """
    from specify_cli.lanes.compute import is_planning_artifact_only
    from specify_cli.lanes.single_branch_landing import lands_mission_branch

    # read-side-seam-primary-primitive-closure-01KYKMMT WP06 (T029): routed off
    # the retiring ``primary_feature_dir_for_mission`` wrapper onto the seam
    # directly — PRIMARY_METADATA, since this anchors ``run.target_feature_dir``
    # (meta.json reads/writes: ``:867`` ``meta.json`` path, ``:996``
    # ``cutover_mission``'s ``status_phase`` flip target). WP08 (T036):
    # dropped the caller-side canonicalizer fold — redundant with the seam's
    # own internal fold for a PRIMARY-partition kind.
    target_feature_dir = placement_seam(main_repo, mission_slug).read_dir(MissionArtifactKind.PRIMARY_METADATA)
    # FR-004 / FR-009: exclude canceled-with-provenance WPs from the per-WP
    # done/review derivations. ``all_wp_ids`` feeds the review-artifact
    # consistency gate (:1671), the evidence/canonical-history guards
    # (``_phase_gates_and_state``), ``wp_order`` (:1681), and the final
    # ``_assert_merged_wps_reached_done`` — a canceled WP has no review artifact
    # and never reaches ``done``, so leaving it in would break the merge on an
    # acceptable ending. Resolved once here and threaded to the lane-consolidation phase.
    excluded_canceled_wp_ids = frozenset(acceptably_canceled_wp_ids(main_repo, mission_slug))
    all_wp_ids = [wp for lane in lanes_manifest.lanes for wp in lane.wp_ids if wp not in excluded_canceled_wp_ids]
    planning_artifact_only = is_planning_artifact_only(lanes_manifest) and not lands_mission_branch(main_repo, lanes_manifest)
    # #5686 (FR-005): refuse a move the record cannot explain BEFORE anything this
    # process does could move a branch (the attestations below, the resume heal).
    start_tips = _refuse_unexplained_branch_moves(main_repo, canonical_id)
    # FR-012: record any operator attestation BEFORE the claim is captured, so
    # the reconciliation gate reads it from the event log it already reads.
    recorded_attestations = _record_operator_attestations(
        main_repo,
        mission_slug,
        wp_ids=attest_canceled_superseded,
        reason=attest_reason,
        acceptably_canceled=excluded_canceled_wp_ids,
        approved_wp_ids=attest_approved_reviewed,
        feature_dir=feature_dir,
        lanes_manifest=lanes_manifest,
    )
    # P1: only the status-surface branch the attestations write, and only when its tip changed across them, is this process's own move.
    own_pre_claim_moves = _own_moves_after_step(main_repo, {}, start_tips if recorded_attestations else {}, writes=(_status_surface_ref(main_repo, mission_slug),))

    # INV (ordering preserved from the pre-refactor monolith): the review-artifact
    # consistency gate runs BEFORE merge-state is loaded/created, so a rejected
    # mission fails without ever writing state.json (regression: schema preflight
    # must not write merge state).
    _enforce_review_artifact_consistency(
        repo_root=main_repo,
        feature_dir=feature_dir,
        mission_slug=mission_slug,
        wp_ids=all_wp_ids,
        skip_review_artifact_check=skip_review_artifact_check,
        skip_note=skip_note,
    )

    state, is_resume = _load_or_create_merge_state(
        main_repo=main_repo,
        mission_slug=mission_slug,
        canonical_id=canonical_id,
        target_branch=lanes_manifest.target_branch,
        wp_order=all_wp_ids,
        push_requested=push,
        skip_lanes=skip_lanes,
        strategy=strategy.value,
    )

    # terminus-merge-integrity WP06 (C-1 wiring half / T029): reseed the manifest
    # target from the PERSISTED ConsolidationState target immediately after load, so the
    # 28 ``lanes_manifest.target_branch`` read-sites consume the single persisted
    # authority (never the meta-seeded copy) on both a fresh and a ``--resume``d
    # merge. WP09 owns RESOLVING/PERSISTING ``state.target_branch`` (precedence
    # explicit ``--target`` > persisted > meta); this WP only makes the executor
    # CONSUME it — until WP09 lands, ``state.target_branch`` equals the value
    # passed in above, so this reseed is an identity no-op (proven safe for
    # NFR-004) that establishes the consumption seam. Flagged to WP09.
    lanes_manifest.target_branch = state.target_branch

    run = _MergeRunState(
        main_repo=main_repo,
        mission_slug=mission_slug,
        canonical_id=canonical_id,
        canonical_mission_id=canonical_mission_id,
        feature_dir=feature_dir,
        target_feature_dir=target_feature_dir,
        lanes_manifest=lanes_manifest,
        all_wp_ids=all_wp_ids,
        excluded_canceled_wp_ids=excluded_canceled_wp_ids,
        push=push,
        delete_branch=delete_branch,
        remove_worktree=remove_worktree,
        teardown_coordination=teardown_coordination,
        strategy=strategy,
        assume_yes=assume_yes,
        planning_artifact_only=planning_artifact_only,
        state=state,
        is_resume=is_resume,
        skip_lanes=skip_lanes,
        recorded_attestations=recorded_attestations,
        own_pre_claim_moves=own_pre_claim_moves,
    )

    # FR-006: at resume startup, heal any coord strand a prior attempt left
    # durably marked (strand-gated + atomic-clear via the coordination primitive).
    # Placed BEFORE the frozen phase list (not a phase-driver wrapper — INV-5),
    # so it is never part of ``expected_order``.
    if run.is_resume:
        pending_marker = run.state.pending_coord_reconcile
        before_heal = _tips_before_heal(run, pending_marker)
        _heal_pending_coord_reconcile(run)
        # P1: the heal's own move counts only while the branch stays where the heal left it.
        heal_ref = str(pending_marker["coord_ref"]) if pending_marker else None
        run.own_pre_claim_moves = _own_moves_after_step(run.main_repo, run.own_pre_claim_moves, before_heal, writes=(heal_ref,))
        _settle_healed_coordination_branch(run, pending_marker)

    with _clear_fresh_record_on_pre_mutation_exit(run):
        # terminus-integrity-followups WP05 (T020, FR-003, F14): mirror the C-1 target
        # reseed above for strategy — persist the strategy attempt-1 ACTUALLY executes
        # (the CLI-resolved value threaded in here) so a ``--resume`` reads a truthful
        # authority instead of the inert ``ConsolidationState.strategy`` default. Fresh-only; a
        # resume's persisted value already sourced this run's strategy (WP04 CLI
        # precedence) and must never be re-stamped. Inside the #5111 guard: it is the
        # first write after the fresh record is created, so an I/O failure here
        # clears that record too instead of leaving a zero-progress resume behind.
        _persist_executed_strategy(run.state, run.strategy, is_resume=run.is_resume, main_repo=run.main_repo)
        _phase_gates_and_state(run)
        # terminus-merge-integrity WP06 (T027/T029): capture the fail-closed,
        # Lamport-sourced reconciliation claim + the transaction-start target tip
        # (CAS anchor / excluded-window base) NOW — before any mutation — and refuse
        # a resumed pre-fix in-flight state (FR-012). The teardown gate compares the
        # post-merge target against this pre-mutation claim.
        _capture_reconciliation_claim(run)
    # #5021 residual 1 (Decision 3): a ``--resume`` whose persisted CAS anchor
    # proves reconciliation already PASSed for the target's CURRENT tip must
    # not re-run the consolidation/bake/mission->target/done-bookkeeping
    # phases at all — several of them (the pre-target ``done`` mark + status
    # projection) write NEW bookkeeping content onto the coordination branch
    # that a fresh ``_phase_mission_to_target`` tree-equality re-check would
    # then see as a genuine divergence from the target's own already-projected
    # copy, forcing a spurious second squash attempt (and, separately, a lane
    # branch teardown already deleted collapses the rebuilt authored-blobs
    # claim to empty). Skipping straight to the reconciliation gate — which
    # itself short-circuits the content axis via the SAME CAS check — is what
    # "complete teardown instead of re-running [already-verified work]" means.
    # A genuinely incomplete resume (no PASS recorded, or the target moved
    # since) takes the full phase list unchanged — the R2 guard.
    # #5385 (ADR 2026-09-19-1 A3): ONE rollback door for the whole post-mutation
    # span, from the first mutation (``_phase_merge_lanes``) through the gate. A
    # non-zero ``typer.Exit``, any other exception or an interrupt restores every
    # snapshotted branch through ``rollback_to_snapshot`` (``_report_rollback``) and
    # re-raises the original; ``typer.Exit(0)`` passes through untouched
    # (``typer.Exit`` subclasses ``RuntimeError``, so its clause comes first).
    # ``anchor_before`` lets ``_report_rollback`` undo THIS run's own PASS anchor
    # (BLOCKER 1) while an EARLIER attempt's anchor keeps its verified landing.
    # The phase calls stay inline: the phase-boundary pins index them here.
    #
    # Landing reconciliation (#5444): main independently added the narrower,
    # phase-local ``_phase_record_done_and_project_or_roll_back`` (it caught only a
    # ``typer.Exit`` from the done-and-project phase). This single door subsumes it
    # with the identical ``anchor_before`` + ``_report_rollback`` mechanism over the
    # whole span, so the interim variant is removed and the done-and-project phase
    # calls the base ``_phase_record_done_and_project`` inside this try.
    anchor_before = run.state.reconciliation_passed_target_sha
    # #5686 (FR-006): every advance inside the span persists its intent first, so a
    # kill between the compare-and-swap write and the phase recorder stays provable.
    with reporting_advance_intents(functools.partial(_note_advance_intent, run)):
        try:
            if not _resume_reconciliation_already_passed(run):
                _phase_merge_lanes(run)
                _phase_baseline_and_surface(run)
                _phase_bake_and_pre_target_done(run)
                _capture_pre_target_gate_artifacts(run)
                _phase_mission_to_target(run)
                _switch_write_checkout_after_single_branch_landing(run)
                _phase_capture_and_baseline(run)
                _phase_record_done_and_project(run)
                _phase_porcelain_invariant(run)
                _phase_commit_and_assert(run)
            else:
                # Skipped ``_phase_baseline_and_surface`` above never set
                # ``run.target_baseline_sha`` (default ``"HEAD~1"``, a stale window for
                # a target that has not moved in THIS run) — ``_phase_dossier_and_stale``
                # still runs unconditionally below and would otherwise scan an
                # arbitrary/wrong window. Nothing new landed in this run, so the correct
                # stale-assertion baseline IS the target's current tip (an empty window).
                run.target_baseline_sha = _resolve_ref_sha(run.main_repo, run.lanes_manifest.target_branch) or run.target_baseline_sha
            # terminus-merge-integrity WP06 (S-D): the tree-authoritative reconciliation
            # gate runs strictly BEFORE any teardown/push; teardown executes only after
            # verify == PASS.
            _phase_reconcile_before_teardown(run)
        except typer.Exit as exc:
            if exc.exit_code:
                _report_rollback(run, anchor_before=anchor_before)
            raise
        except BaseException:
            _report_rollback(run, anchor_before=anchor_before)
            raise
    # #5686 (FR-003, post-tasks squad HIGH): the reconciliation PASS and the squash
    # projection proof both succeeded (or an earlier attempt's PASS still holds for
    # this tip), so the target is settled; never before the whole span completed.
    rollback.settle_branch(run.main_repo, run.state, run.lanes_manifest.target_branch)
    _phase_dossier_and_stale(run)
    _phase_push(run)
    _phase_cleanup_worktrees_and_branches(run)
    _phase_finalize_and_summary(run)


def _report_rollback(run: _MergeRunState, *, anchor_before: str | None) -> None:
    """Roll every snapshotted branch back after a post-mutation failure and print the report (#5318 / #5385).

    The single rollback door's body: the driver calls it for a non-zero exit, an
    exception or an interrupt anywhere from ``_phase_merge_lanes`` through the gate.

    ``anchor_before`` is ``reconciliation_passed_target_sha`` as it stood BEFORE
    the span ran. Since F3 the gate persists THIS run's own PASS anchor only as
    its last step, after the projection proof passed, so a gate refusal leaves
    none; the reset stays as a backstop for any exit after that write (a failed
    save, an interrupt): left in place, the authority would read it as a landing
    verified by an EARLIER reconciliation (FR-011) and refuse to roll back. An
    anchor from an earlier attempt is unchanged by the span and therefore still
    keeps that verified landing.

    Never raises: the caller re-raises the ORIGINAL error, so a failing anchor
    reset or rollback prints one line naming the branches to inspect instead of
    replacing that error with its own traceback, and never implies success.
    ``BaseException`` on purpose: a second Ctrl-C (or ``SystemExit``) during the
    rollback must not replace the original error either; the caller's bare
    ``raise`` still propagates that original.
    """
    try:
        if run.state.reconciliation_passed_target_sha != anchor_before:
            run.state.reconciliation_passed_target_sha = anchor_before
            save_state(run.state, run.main_repo)
        report = rollback.rollback_to_snapshot(run.main_repo, run.state, target_branch=run.lanes_manifest.target_branch)
    except BaseException as exc:
        branches = ", ".join(sorted(run.state.pre_mutation_refs)) or "the mission branches"
        console.print(f"Rollback could not complete: {exc}; inspect {branches} before re-running.", markup=False)
        return
    console.print(report.render(), markup=False)


def _load_lanes_manifest(
    main_repo: Path,
    mission_slug: str,
    *,
    lanes_read_dir: Path,
    status_feature_dir: Path,
    primary_meta_dir: Path,
    skip_lanes: bool,
    target_override: str | None,
) -> LanesManifest:
    """The run's lanes manifest: read, or (``--skip-lanes`` with none) synthesized, then retargeted by ``--target``."""
    if skip_lanes:
        manifest = read_lanes_json(lanes_read_dir)
        if manifest is None:
            manifest = _synthesize_no_lane_manifest(
                main_repo=main_repo,
                mission_slug=mission_slug,
                status_feature_dir=status_feature_dir,
                primary_meta_dir=primary_meta_dir,
                target_override=target_override,
            )
    else:
        manifest = _require_lanes_json_naming_mission_branch(main_repo, lanes_read_dir)
    if target_override:
        manifest.target_branch = target_override
    return manifest


def _enforce_origin_gate(main_repo: Path, seam: PlacementSeam, origin_check: str | None) -> None:
    """Print the origin gate's warnings, or its refusal text and exit 1 (nothing has moved yet)."""
    try:
        warnings = check_origin_before_status_dir(main_repo, seam, origin_check)
    except OriginFreshnessRefused as exc:
        console.print(str(exc), markup=False)
        raise typer.Exit(1) from exc
    for warning in warnings:
        console.print(warning, markup=False)


def _run_lane_based_consolidation(
    repo_root: Path,
    mission_slug: str,
    *,
    push: bool,
    delete_branch: bool | None,
    remove_worktree: bool | None,
    target_override: str | None = None,
    strategy: MergeStrategy = MergeStrategy.SQUASH,
    allow_sparse_checkout: bool = False,
    assume_yes: bool = False,
    skip_review_artifact_check: bool = False,
    skip_note: str | None = None,
    skip_lanes: bool = False,
    attest_canceled_superseded: tuple[str, ...] = (),
    attest_reason: str | None = None,
    attest_approved_reviewed: tuple[str, ...] = (),
    origin_check: str | None = None,
    origin_gated: bool = False,
) -> None:
    """Execute the lane-only merge flow with ConsolidationState lifecycle for recovery.

    Args:
        repo_root: Repository root.
        mission_slug: Feature slug.
        push: Push to origin after merge.
        delete_branch: Tri-state ``--delete-branch``/``--keep-branch`` CLI
            resolution (#3131). ``None`` means the operator did not pass
            either flag, in which case :func:`~specify_cli.core.paths.resolve_merge_retention`
            resolves the effective decision from the mission's ``meta.json``
            retention policy (falling back to the historical default —
            delete — when no policy is recorded). An explicit ``True``/
            ``False`` always wins over the mission's policy (with a recorded
            override notice when it overrides a retaining policy).
        remove_worktree: Tri-state ``--remove-worktree``/``--keep-worktree``
            CLI resolution; same resolution rule as ``delete_branch``.
        target_override: Override target branch.
        strategy: Merge strategy for the mission→target step (FR-005, FR-006).
            Lane→mission step always uses merge commits regardless of this value.
        allow_sparse_checkout: When True, bypass the sparse-checkout preflight
            (FR-008). The commit-layer backstop (WP01) still fires under this
            override — it is NOT disabled by this flag. Use of this override is
            logged via ``require_no_sparse_checkout``.
        origin_check: ``--origin-check`` value (``enforce``/``warn``/``off``) or ``None`` to
            defer to ``SPEC_KITTY_ORIGIN_CHECK``; see :mod:`.origin_gate` (#5780).
        origin_gated: ``True`` when the caller already ran the origin freshness gate
            with its own resolved setting (``orchestrator-api consolidate-mission``),
            so this entry neither re-checks nor contacts the remote a second time.
        skip_lanes: T021 (FR-012, FOLD 1) — the executor capability behind
            ``merge --skip-lanes``/``--no-lanes``. When ``True`` AND
            ``lanes.json`` is genuinely absent, synthesizes a NO-LANE
            direct-on-target manifest instead of hard-failing with
            ``MissingLanesError`` — never a blanket bypass of the manifest
            requirement for a mission that genuinely has lanes (a present
            ``lanes.json`` is always honored as-is). The merge-ready
            precondition (``_assert_mission_terminal_ready``) still runs
            unconditionally on this path (no bypass of FR-001/002).
    """
    main_repo = get_main_repo_root(repo_root)
    # STATUS leg (C-001 / KEEP): ``feature_dir`` is threaded into
    # ``_run_lane_based_consolidation_locked`` as ``run.feature_dir`` and feeds the
    # coord-aware STATUS legs (``status_feature_dir``). Its location comes from the
    # WRITE accessor (ruling Q4, FR-003), never from a read resolver: this is where
    # the done bookkeeping, the birth cutover and the status reads land.
    seam = placement_seam(main_repo, mission_slug)
    # #5780: the origin freshness check runs BEFORE the status dir is resolved (that
    # resolution can seed or commit the coordination surface) and before any branch moves.
    if not origin_gated:
        _enforce_origin_gate(main_repo, seam, origin_check)
    feature_dir = _resolve_run_status_dir(seam)
    # PRIMARY-partition reads (FR-002 #2185), routed per-leg DIRECTLY (NOT threaded
    # from the ``:887`` ``target_feature_dir`` anchor in the *locked* function): the
    # mission identity (PRIMARY_METADATA) and ``lanes.json`` (LANE_STATE) live ONLY
    # on the PRIMARY checkout post-#2106. Reading them off the coord-aware
    # ``feature_dir`` above lands on the STATUS-only husk → a missing/sentinel
    # ``meta.json`` and an absent ``lanes.json``. Resolve each by its real kind.
    primary_meta_dir = seam.read_dir(MissionArtifactKind.PRIMARY_METADATA)
    lanes_read_dir = seam.read_dir(MissionArtifactKind.LANE_STATE)

    # -- WP05/T020/FR-006: Sparse-checkout preflight (BEFORE any state change) --
    _preflight_mission_id: str | None = None
    try:
        _preflight_identity = resolve_mission_identity(primary_meta_dir)
        _preflight_mission_id = _preflight_identity.mission_id
    except Exception:  # noqa: BLE001 — meta.json may be missing for legacy missions
        _preflight_mission_id = None

    require_no_sparse_checkout(
        repo_root=main_repo,
        command="spec-kitty consolidate",
        override_flag=allow_sparse_checkout,
        actor=_resolve_merge_actor(main_repo),
        mission_slug=mission_slug,
        mission_id=_preflight_mission_id,  # WP04: str | None; slug fallback removed
    )

    from specify_cli.lanes.compute import is_planning_artifact_only
    from specify_cli.lanes.single_branch_landing import lands_mission_branch

    lanes_manifest = _load_lanes_manifest(
        main_repo,
        mission_slug,
        lanes_read_dir=lanes_read_dir,
        status_feature_dir=feature_dir,
        primary_meta_dir=primary_meta_dir,
        skip_lanes=skip_lanes,
        target_override=target_override,
    )
    planning_artifact_only = is_planning_artifact_only(lanes_manifest) and not lands_mission_branch(main_repo, lanes_manifest)

    # -- Resolve canonical mission_id from meta.json (WP04/FR-004) --
    identity = resolve_mission_identity(primary_meta_dir)
    # canonical_mission_id: ULID or None (for mission_id event fields; slug never written here).
    # canonical_id: for path-based workspace management — explicit slug fallback for
    # legacy missions without a backfilled ULID (NOT a mission_id field value).
    canonical_mission_id = identity.mission_id
    canonical_id = identity.mission_id if identity.mission_id is not None else mission_slug

    # -- #3131 T007: resolve the retention decision ONCE, off primary_meta_dir --
    # (NOT the locked driver's coord STATUS husk — the partition trap). Emitted
    # operator-visibly (FR-005/FR-006); a corrupt meta.json aborts the merge
    # with a clean error, mirroring ``resolve_merge_target_branch`` handling.
    try:
        retention = resolve_merge_retention(
            primary_meta_dir,
            explicit_delete_branch=delete_branch,
            explicit_remove_worktree=remove_worktree,
        )
    except MissionMetaReadError as exc:
        console.print(f"[red]Error:[/red] Cannot resolve the merge retention policy: {exc}. meta.json exists but is corrupt or unreadable; fix it before merging.")
        raise typer.Exit(1) from exc
    for warning in retention.warnings:
        console.print(f"[yellow]Warning:[/yellow] {warning}")
    for notice in retention.override_notices:
        console.print(f"[yellow]Notice:[/yellow] {notice}")

    effective_push = _effective_push_requested(main_repo, canonical_id, push)
    if effective_push:
        _enforce_target_branch_sync_preflight(
            main_repo,
            target_branch=lanes_manifest.target_branch,
            mission_slug=mission_slug,
            mission_branch=lanes_manifest.mission_branch,
            mission_id=_preflight_mission_id,
        )

    if planning_artifact_only:
        _enforce_planning_artifact_target_branch(
            main_repo,
            lanes_manifest.target_branch,
        )
    else:
        branch_ok, branch_blocker = _check_mission_branch(
            mission_slug,
            main_repo,
            expected_branch=lanes_manifest.mission_branch,
            mission_id=_preflight_mission_id,
        )
        if not branch_ok:
            assert branch_blocker is not None
            console.print(f"[red]Error:[/red] Missing mission branch: {branch_blocker['expected_branch']}. Run: {branch_blocker['remediation']}")
            raise typer.Exit(1)

    # -- WP03/T010 (#4752/#4753): pre-mutation refuse-before-destroy preflight.
    # Placed after the existing CLI-precondition preflights above (push-sync,
    # mission-branch existence) so their own remediation still surfaces first
    # for the conditions THEY own, but still well BEFORE the global merge lock
    # is acquired and BEFORE ``_run_lane_based_consolidation_locked``'s phase list runs
    # — none of the checks above ever mutate the repository, so a refusal here
    # is still byte-identical to pre-invocation (NFR-001). Both a fresh merge
    # and ``--resume`` route through this same outer function, so ``--resume``
    # honors the guard identically (US1 AC4). The ONE sanctioned pre-lock
    # mutation is the #4997 behind-own-HEAD resume recovery inside the wrapper
    # below (a provably-non-destructive ``git reset --hard HEAD`` over phantom
    # staged deletions); every other outcome remains refuse (byte-identical) or
    # proceed.
    _refuse_protected_status_target_or_continue(main_repo, mission_slug, lanes_manifest, canonical_id)
    _pre_mutation_safety_preflight_with_recovery(
        main_repo,
        mission_slug,
        lanes_manifest,
        canonical_id,
        primary_meta_dir,
        retention,
    )

    # -- Acquire global merge lock to serialize concurrent merges --
    # WP09 (C-2, FR-008, #4996): stamp the lock with this merge's owner_token =
    # merge-state-id (``canonical_id``, stable across ``--resume``) so ``--abort``
    # can prove ownership and never free a DIFFERENT mission's live lock. This is
    # the single documented out-of-map (WP06-owned executor) edit sanctioned by
    # the WP09 prompt — serial lane after WP06, no ``_MergeRunState`` collision.
    if not acquire_merge_lock(_GLOBAL_MERGE_LOCK_ID, main_repo, owner_token=canonical_id):
        raise MergeLockError(
            _GLOBAL_MERGE_LOCK_ID,
            main_repo / KITTIFY_DIR / "runtime" / "merge" / _GLOBAL_MERGE_LOCK_ID / "lock",
        )

    try:
        _run_lane_based_consolidation_locked(
            main_repo=main_repo,
            mission_slug=mission_slug,
            canonical_id=canonical_id,
            canonical_mission_id=canonical_mission_id,
            feature_dir=feature_dir,
            lanes_manifest=lanes_manifest,
            push=effective_push,
            delete_branch=retention.delete_branch,
            remove_worktree=retention.remove_worktree,
            teardown_coordination=retention.teardown_coordination,
            strategy=strategy,
            assume_yes=assume_yes,
            skip_review_artifact_check=skip_review_artifact_check,
            skip_note=skip_note,
            skip_lanes=skip_lanes,
            attest_canceled_superseded=attest_canceled_superseded,
            attest_reason=attest_reason,
            attest_approved_reviewed=attest_approved_reviewed,
        )
    finally:
        release_merge_lock(_GLOBAL_MERGE_LOCK_ID, main_repo)


__all__ = [
    "_run_lane_based_consolidation",
    "_run_lane_based_consolidation_locked",
]
