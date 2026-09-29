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
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable, Iterator
import functools
import subprocess
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Concatenate, Final, NoReturn, ParamSpec, cast

import typer
from rich.markup import escape

if TYPE_CHECKING:
    from specify_cli.lanes.consolidation import MissionConsolidationResult
    from specify_cli.lanes.models import ExecutionLane, LanesManifest
    from specify_cli.migration.runtime_state_cutover import CutoverResult

from specify_cli.cli.console import console
from specify_cli.core.constants import KITTIFY_DIR, KITTY_SPECS_DIR, WORKTREES_DIR
from specify_cli.coordination.atomic_write import (
    capture_generated_artifact_snapshots,
    restore_generated_artifact_snapshots,
)
from specify_cli.coordination.coherence import (
    CoordRepairOutcome,
    coord_incoherent_done_wps,
    is_toolchain_generated_churn,
    repair_coord_strand,
)
from specify_cli.coordination.surface_resolver import (
    CoordinationBranchDeleted,
    CoordinationWorktreeUnmaterialized,
    is_under_worktrees_segment,
    resolve_status_surface,
)
from specify_cli.core.git_ops import has_remote, run_command
from kernel.clock import now_utc_iso
from specify_cli.core.paths import (
    MissionMetaReadError,
    RetentionDecision,
    get_main_repo_root,
    resolve_merge_retention,
    resolve_merge_target_branch,
)
from specify_cli.git.bookkeeping_commit import (
    commit_coord_seed_bookkeeping,
    commit_merge_bookkeeping,
)
from specify_cli.git.commit_helpers import SafeCommitRecoveryFailed
from specify_cli.git.ref_advance import RefAdvanceError, RefResyncError, RefRestoreError, restore_branch_ref
from specify_cli.git.destructive_guard import (
    MERGE_UNSAFE_PRIMARY_DIRTY,
    DestructiveOpRefused,
    assert_checkout_on_target,
    assert_worktree_clean,
    guarded_worktree_remove,
)
from specify_cli.consolidation.git_probes import _paths_have_status_changes
from specify_cli.git.sparse_checkout import require_no_sparse_checkout
from specify_cli.lanes.single_branch_landing import worktree_lanes

# Shared FR-004/FR-009 "fully canceled" predicate and lane-branch composer
# (single canonical home in ``lanes.compute`` — see its docstrings); re-exported
# under the historical private names so existing call sites and tests in this
# module (``ex._lane_fully_canceled`` / ``ex._created_lane_branch``) still work.
from specify_cli.lanes.compute import lane_created_branch as _created_lane_branch
from specify_cli.lanes.compute import lane_fully_canceled as _lane_fully_canceled
from specify_cli.lanes.persistence import read_lanes_json, require_lanes_json
from specify_cli.consolidation._constants import (
    GLOBAL_MERGE_LOCK_ID as _GLOBAL_MERGE_LOCK_ID,
    _STATUS_EVENTS_FILENAME,
    _STATUS_FILENAME,
    TARGET_BRANCH_CONTENT_CONFLICT,
    TARGET_BRANCH_CONTENT_CONFLICT_HEADER,
    TARGET_BRANCH_CONTENT_CONFLICT_REMEDIATION_UPDATE,
    logger,
)
from specify_cli.consolidation.baseline import (
    BaselineMergeCommitError,
    assert_baseline_merge_commit_on_target as _assert_baseline_merge_commit_on_target,
    assert_mission_number_on_target as _assert_mission_number_on_target,
    read_mission_number_from_ref as _read_mission_number_from_ref,
    record_baseline_merge_commit as _record_baseline_merge_commit,
)
from specify_cli.consolidation.bookkeeping_projection import (
    _post_checkpoint_mission_paths,
    _project_status_bookkeeping_to_target,
    _resolve_ref_sha,
    _target_bookkeeping_status_paths,
    _target_branch_still_at_baseline,
    projected_content_matches_target,
)
from specify_cli.consolidation.config import MergeStrategy
from specify_cli.consolidation.done_bookkeeping import (
    _assert_merged_wps_done_on_target,
    _record_merged_wps_done_for_merge,
    _resolve_merge_actor,
    acceptably_canceled_wp_ids,
)
from specify_cli.consolidation.git_probes import (
    GitProbeError,
    _branch_trees_equal,
    _classify_porcelain_lines,
    _emit_remediation_hint,
    _is_linear_history_rejection,
    _lane_already_integrated,
    _raw_porcelain_status,
    _refresh_primary_checkout_after_merge,
)
from specify_cli.consolidation.ordering import (
    _assign_planning_only_mission_number_if_needed,
    _bake_mission_number_into_mission_branch,
    _bake_mission_number_onto_target_tree,
    _mark_mission_number_baked,
    _read_target_tree_mission_number,
)
from specify_cli.consolidation.preflight import (
    _check_mission_branch,
    _effective_push_requested,
    _enforce_canonical_status_history,
    _enforce_planning_artifact_target_branch,
    _enforce_review_artifact_consistency,
    _warn_or_confirm_hollow_reviews,
)
from specify_cli.consolidation import rollback
from specify_cli.consolidation.push_preflight import _enforce_target_branch_sync_preflight
from specify_cli.consolidation.reconciliation import (
    ApprovedWpCommitSet,
    MergeOutcomeVerifier,
    VerifyResult,
    VerifyStatus,
    build_approved_wp_set,
    claim_integrity_refusal,
    detect_legacy_in_flight_state,
    route_terminus,
    write_post_fix_marker,
)
from specify_cli.consolidation.resolve import _load_or_create_merge_state
from specify_cli.consolidation.state import (
    MergeLockError,
    ConsolidationState,
    ConsolidationStateReadError,
    acquire_merge_lock,
    clear_state,
    get_state_path,
    lane_tip_cas_ok,
    load_state,
    reconciliation_passed_for_tip,
    release_merge_lock,
    save_state,
)
from specify_cli.consolidation.workspace import _worktree_removal_delay, cleanup_merge_workspace
from specify_cli.mission_metadata import resolve_mission_identity
from mission_runtime import (
    MissionArtifactKind,
    MissionTopology,
    placement_seam,
    resolve_placement_only,
)
from specify_cli.post_merge.stale_assertions import StaleAssertionFinding, StaleAssertionReport, run_check


# lane-branch-naming-authority-01M3EVC4 WP02 (T032, S1192): the single source
# for the abort-and-retry remediation text every resume-refusal message
# renders. Route EVERY occurrence (old and new) through these constants so
# the CLI command name below is spelled out, as a quoted literal, exactly
# once in this module (the assignment on the next line).
_CONSOLIDATE_ABORT_COMMAND = "spec-kitty consolidate --abort"
_CONSOLIDATE_ABORT_AND_RESTART_HINT = f"Run `{_CONSOLIDATE_ABORT_COMMAND}` and start the consolidation fresh."

# Shared fragment of the pre-teardown refusal texts (claim probe error, projection refusals).
_NOTHING_TORN_DOWN = "Nothing was torn down"


class CoordinationTeardownError(RuntimeError):
    """A leg of the coord triple (worktree, branch, marker) did not come down.

    #3131 INV-2 makes the triple all-or-nothing, so a partial teardown has to
    stop the run and say so rather than print a success line over a git error
    and leave a stranded coord worktree/branch behind (#3926).
    """


class LaneNamingSlugMismatch(RuntimeError):
    """``run.mission_slug`` diverged from ``lanes_manifest.mission_slug``.

    The manifest slug is the ONE naming input for lane branch/worktree
    composition; a real merge run is expected to carry the same slug on both
    fields. A divergence here would silently name/consolidate against two
    different slugs, so it fails loud with a typed error rather than an
    ``assert`` (which a ``python -O`` invocation would compile away).
    """


def _merge_snapshot_roots(main_repo: Path) -> list[Path]:
    """Trusted roots for the merge executor's non-coord (primary-checkout) surface.

    The owner (``atomic_write.capture_generated_artifact_snapshots``) enforces
    containment against these; the executor declares WHICH primary-checkout roots
    hold its generated bookkeeping bytes. Preserves the exact trusted set the
    retired merge-side snapshot-trust helper guarded (3 dirs).
    """
    repo = get_main_repo_root(main_repo).resolve(strict=False)
    return [
        (repo / KITTY_SPECS_DIR).resolve(strict=False),
        (repo / WORKTREES_DIR).resolve(strict=False),
        (repo / KITTIFY_DIR / "runtime" / "merge").resolve(strict=False),
    ]


def _merge_snapshot_files(main_repo: Path) -> list[Path]:
    """Trusted exact-file allowlist for the merge snapshot surface (merge-state.json)."""
    repo = get_main_repo_root(main_repo).resolve(strict=False)
    return [(repo / KITTIFY_DIR / "merge-state.json").resolve(strict=False)]


def _capture_merge_snapshots(main_repo: Path, *paths: Path) -> dict[Path, bytes | None]:
    """Capture pre-transaction bytes of merge bookkeeping paths through the owner.

    Thin adapter over the single owner compensator's capture: supplies this
    non-coord surface's trusted roots/files so the containment that used to live in
    the ``merge/`` package is enforced by the owner instead.
    """
    return capture_generated_artifact_snapshots(
        *paths,
        trusted_roots=_merge_snapshot_roots(main_repo),
        trusted_files=_merge_snapshot_files(main_repo),
    )


# #2804 / FR-009 (write-surface-coherence WP08): the gate-artifact basenames
# whose target-checkout content the mission->target squash merge must never
# silently clobber. Both are PLACEMENT-partition kinds (``ACCEPTANCE_MATRIX`` /
# ``ISSUE_MATRIX``) that WP08's write-surface fix (``scaffold_acceptance_matrix``
# / the accept-fill path) stops authoring a SECOND, divergent PRIMARY copy of
# under coordination topology — this defense-in-depth guard covers the
# genuinely parallel case: an already-accepted target-checkout copy that
# predates that fix, or a topology where the artifacts legitimately live on the
# PRIMARY partition (``SINGLE_BRANCH`` / ``LANES``) and can still diverge from a
# stale mission-branch scaffold placeholder (the exact #2804 incident shape).
# 2026-08-07 (landing fix, verdict-seam-write-unification #3245): registered as
# a justified-survivor R-014 exemption-registry row (tests/architectural/
# tool_artifact_enrolment/registry/_GATE_ARTIFACT_FILENAMES.md) rather than
# routed through the canonical churn owner `is_toolchain_generated_churn` --
# that owner classifies an already-observed path's dirty-state disposition,
# not "the basenames for kind X", so it cannot replace this mechanism's
# unconditional forward-build of candidate snapshot paths. See the row file
# for the full rationale.
_GATE_ARTIFACT_FILENAMES: Final[tuple[str, ...]] = ("acceptance-matrix.json", "issue-matrix.json")


def _gate_artifact_paths(run: _MergeRunState) -> tuple[Path, ...]:
    """Target-checkout paths for the #2804 gate-artifact preservation guard."""
    return tuple(run.target_feature_dir / name for name in _GATE_ARTIFACT_FILENAMES)


def _capture_pre_target_gate_artifacts(run: _MergeRunState) -> None:
    """Snapshot the TARGET's gate-artifact bytes BEFORE the mission->target squash.

    Called before :func:`_phase_mission_to_target` — the squash-merge step whose
    add/add resolution (via the gate-artifact merge drivers) can otherwise let the
    mission branch's stale finalize-time scaffold placeholder win over an
    already-accepted target-checkout ``acceptance-matrix.json`` /
    ``issue-matrix.json`` (#2804). A
    mission's gate artifacts are per-mission (``kitty-specs/<slug>/...``), so in
    ordinary operation (no #2404-class divergent write) target carries nothing
    here pre-merge and this snapshot is empty/``None`` — a genuine no-op for
    :func:`_restore_regressed_gate_artifacts` below.
    """
    run.pre_target_gate_artifact_snapshots = _capture_merge_snapshots(run.main_repo, *_gate_artifact_paths(run))


def _restore_regressed_gate_artifacts(run: _MergeRunState) -> None:
    """Preserve an already-accepted target gate artifact through the squash merge (#2804).

    D-PLAN-7: the durable fix is at the WRITE surface (WP08 T040/T041 stop a
    second, divergent PRIMARY-partition copy from ever being authored under
    coordination topology) — row-aware reconciliation of a genuine same-key
    divergence is WP09's merge-driver defense-in-depth, not this function's job.
    This guard is narrower and complementary: when the target checkout ALREADY
    held gate-artifact content before the squash merge (:func:`_capture_pre_
    target_gate_artifacts`) and the squash step's resolution changed it, the
    pre-merge bytes are restored verbatim — an established,
    already-accepted verdict is never silently discarded by the squash step.
    Restored paths are recorded on ``run`` so the caller can fold them into the
    same final bookkeeping commit and the post-merge porcelain-invariant gate
    (both in this module) rather than leaving the working tree unexpectedly
    dirty.
    """
    for path in _gate_artifact_paths(run):
        original = run.pre_target_gate_artifact_snapshots.get(path)
        if original is None:
            # Target held nothing here pre-merge (the ordinary, non-divergent
            # case) — whatever the squash merge produced is authoritative.
            continue
        current = path.read_bytes() if path.exists() else None
        if current == original:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(original)
        run.gate_artifact_restored_paths.append(path)


@dataclass
class _MergeRunState:
    """Shared mutable state threaded through the merge phase helpers (INV-3).

    Each phase takes this object, mutates the documented fields, and returns
    None; ``_run_lane_based_consolidation_locked`` becomes the linear phase caller.
    """

    # Inputs / identity
    main_repo: Path
    mission_slug: str
    canonical_id: str  # for path-based workspace management; slug for legacy missions
    canonical_mission_id: str | None  # WP04/FR-004: ULID or None; for mission_id event fields only
    feature_dir: Path
    target_feature_dir: Path
    lanes_manifest: LanesManifest
    all_wp_ids: list[str]
    push: bool
    delete_branch: bool
    remove_worktree: bool
    strategy: MergeStrategy
    assume_yes: bool
    planning_artifact_only: bool

    # Loaded / derived during the run
    state: ConsolidationState
    is_resume: bool
    any_lane_had_unintegrated_code: bool = False
    # FR-004 / FR-009: WP IDs at an acceptable *canceled* ending (operator
    # provenance) on the coord surface — resolved ONCE at lock entry via
    # ``acceptably_canceled_wp_ids`` and threaded to the lane-consolidation phase so a
    # fully-canceled lane (whose branch may not exist) is skipped without a
    # second coord read. ``all_wp_ids`` already has these filtered out.
    excluded_canceled_wp_ids: frozenset[str] = frozenset()
    # Slice-10 F4: WP ids whose ``--attest-canceled-superseded`` attestation THIS
    # run recorded (status events written before the claim), for truthful
    # claim-time refusal text.
    recorded_attestations: tuple[str, ...] = ()
    target_baseline_sha: str = "HEAD~1"
    # #4764 FOLD-F1 (primary-tree bake defeats the pre-target rollback guard):
    # the TRUE pre-merge target-branch tip. ``target_baseline_sha`` above is
    # re-anchored to the post-bake target tip in
    # ``_reanchor_baseline_past_primary_tree_bake`` whenever the coord-topology
    # ``_bake_mission_number_on_primary_tree`` fallback (meta.json absent on
    # the mission-branch tree) lands a bookkeeping commit directly on
    # ``target_branch`` -- the main repo's checkout never leaves it during a
    # merge (see ``lanes.consolidation._merge_branch_into``'s "the main repo's
    # checkout is never changed"). That re-anchoring keeps
    # ``_target_branch_still_at_baseline`` measuring the mission→target
    # step's OWN progress instead of this bookkeeping commit. This field
    # retains the ORIGINAL pre-bake tip so
    # ``_restore_pre_target_if_at_baseline``/``_revert_orphan_target_bake_commit``
    # can undo the orphan bake commit too when the rollback fires (US3-1).
    # ``None`` on every path that never advances target during the bake (the
    # common mission-branch write, or no bake at all) -- a proven no-op
    # everywhere it's consumed.
    pre_bake_target_baseline_sha: str | None = None
    baseline_mission_id: str | None = None
    done_marked_before_target: bool = False
    mission_already_applied: bool = False
    mission_number_meta_path: Path | None = None
    # #4900: the mission_number THIS run's mission-branch bake assigned
    # (``_bake_mission_number_into_mission_branch``'s return value, threaded
    # rather than discarded). ``None`` when the bake short-circuited this run
    # (resume / idempotency hit / no-op because the target already carried a
    # number) -- ``_phase_capture_and_baseline`` then falls back to reading
    # the mission branch's OWN committed value. Also the number the
    # target-tree read-back verifies and the post-verification "Assigned"
    # line announces (``_phase_commit_and_assert``).
    assigned_mission_number: int | None = None
    baseline_meta_path: Path | None = None
    stale_report: StaleAssertionReport | None = None
    # coord-write-placement-closure-01KYCF83 WP09 (IC-08 / FR-009): the birth-time
    # runtime cutover's outcome + the ``meta.json`` path it flipped (when it
    # flipped), so the porcelain-invariant + bookkeeping-commit phases can
    # recognize the write and the caller can inspect the outcome.
    birth_cutover_result: CutoverResult | None = None
    birth_cutover_meta_path: Path | None = None

    # Paths
    canonical_events_path: Path | None = None
    canonical_status_path: Path | None = None
    merge_state_path: Path | None = None
    target_events_path: Path | None = None
    target_status_path: Path | None = None

    # Rollback snapshots
    pre_target_bookkeeping_snapshots: dict[Path, bytes | None] = field(default_factory=dict)
    final_bookkeeping_snapshots: dict[Path, bytes | None] = field(default_factory=dict)

    # #2804 / FR-009: the target's pre-squash gate-artifact bytes, and the
    # subset the post-squash restore actually rewrote (folded into the final
    # bookkeeping commit + the porcelain-invariant expected-paths set).
    pre_target_gate_artifact_snapshots: dict[Path, bytes | None] = field(default_factory=dict)
    gate_artifact_restored_paths: list[Path] = field(default_factory=list)

    # #2711 FR-006 (Option A): the coordination-branch ref + tip SHA captured
    # BEFORE the pre-target ``done`` emit. On a target-advance rollback the
    # committed ``done`` is reverted back to this tip in lockstep with the
    # working-byte restore, so the committed reduction never strands ``done``
    # while the working tree rolls back to ``approved`` (the split-brain).
    pre_target_coord_ref: str | None = None
    pre_target_coord_sha: str | None = None

    # T008 (terminus-safety-invariant, FR-007/008): the coordination-branch
    # checkpoint captured BEFORE ``_phase_merge_lanes`` runs ANY consolidation
    # — the "pre-mutation" NAMED checkpoint the unified primitive resets to on
    # a post-mutation failure, undoing lane consolidation + the mission_number
    # bake + the pre-target ``done`` write together (never just the narrower
    # pre-``done`` span the pre-existing ``pre_target_coord_ref``/``_sha``
    # pair above covers). ``None`` for a non-coord topology / legacy mission —
    # a proven no-op everywhere it's consumed.
    pre_mutation_coord_ref: str | None = None
    pre_mutation_coord_sha: str | None = None

    # T021 (FR-012, FOLD 1): the executor capability behind ``merge
    # --skip-lanes``/``--no-lanes`` — tolerate an absent lanes.json for a
    # merge-ready no-lane direct-on-target mission. Never a bypass of the
    # merge-ready precondition (T007 still runs unconditionally).
    skip_lanes: bool = False

    # #2786 / #2367-B FR-005: the WPs THIS merge newly bakes ``done`` for during
    # its pre-target bake — every lane WP MINUS those already durably ``done`` on
    # the committed coordination ref at bake time. This (never ``all_wp_ids``) is
    # the candidate set handed to ``coord_incoherent_done_wps``: on a resume
    # ``all_wp_ids`` would include a WP a prior attempt legitimately baked
    # ``done``, so the heal would revert a genuinely-done WP (data-model
    # derivation contract). A genuinely-pre-existing-``done`` WP is excluded by
    # construction. Unused off the coord path.
    pre_target_done_write_set: list[str] = field(default_factory=list)

    # #3131 FR-004/INV-2: the COUPLED coord-topology teardown decision --
    # ``resolve_merge_retention(...).teardown_coordination`` (delete_branch AND
    # remove_worktree). For a coord mission the coordination branch, its
    # ``coordination_branch`` marker, and its worktree are ONE atomic unit
    # (#3086 flatten-atomicity); this single flag gates all three together in
    # ``_phase_cleanup_worktrees_and_branches`` instead of splitting them across
    # the standalone ``delete_branch`` / ``remove_worktree`` gates, which could
    # tear down the branch while stranding the worktree (or vice versa). Lives
    # in the DEFAULTED region (not next to the required ``delete_branch`` /
    # ``remove_worktree`` fields at ~303-304) so the pre-existing
    # ``_MergeRunState`` construction sites that predate #3131 keep compiling.
    teardown_coordination: bool = False

    # -- terminus-merge-integrity WP06 (S-D) scaffold fields ------------------
    # All new fields the serialized executor lane needs, added in ONE change so
    # the following serial WPs (WP07/WP08/WP09) only ASSIGN, never grow the
    # dataclass (PR-priti). Defaulted so every existing construction site
    # compiles and behavior is unchanged until the phases fill them. The
    # ``_CoordCheckpoint`` annotation is a forward reference (resolved lazily via
    # ``from __future__ import annotations``); the class is defined below.
    #
    # ``approved_wp_set`` (T027) — the fail-closed, Lamport-sourced claim,
    # captured ONCE at transaction start (before any mutation) so the teardown
    # gate compares the post-merge target against PRE-mutation lane tips.
    approved_wp_set: ApprovedWpCommitSet | None = None
    # ``coord_checkpoint`` — the coordination tip captured at transaction start;
    # the base the approved lane-tip SHAs are read relative to (S-B/WP08 also
    # projects post-checkpoint coord commits from here).
    coord_checkpoint: _CoordCheckpoint | None = None
    # ``reconciliation_result`` — the gate verdict, stored for the finalize
    # summary + post-run inspection.
    reconciliation_result: VerifyResult | None = None
    # ``coord_tip_after_projection`` (WP10 integration / S-B teardown gate) — the
    # coordination tip observed immediately AFTER
    # :func:`_project_status_bookkeeping_to_target` brought every post-checkpoint
    # coord commit forward. The teardown gate compare-and-swaps against this value
    # so a concurrent status-emit / verdict that landed AFTER projection (and was
    # therefore never projected) can never be silently destroyed at teardown
    # (#4981). ``None`` on a non-coord mission (no coord tip to anchor).
    coord_tip_after_projection: str | None = None
    # ``target_expected_old_sha`` (D2/WP02) — the target ref value read at
    # transaction start; the CAS anchor and the excluded-patch-id window base.
    # Under the serialized executor lane each ``advance_branch_ref`` call already
    # CASes on its own entry-observed old value (WP02's interim default), which
    # equals this transaction-start value for the FIRST target advance and is the
    # correct per-advance old value for the sequential advances that follow (a
    # single transaction-start value would wrongly reject the 2nd+ advance); this
    # field records the anchor and bounds the reconciliation excluded window.
    target_expected_old_sha: str | None = None
    # ``projected_since_checkpoint`` (S-B/WP08) — coord commits added after the
    # checkpoint that must be projected onto the target before teardown. WP06
    # scaffolds the slot; WP08 fills it.
    projected_since_checkpoint: tuple[str, ...] = ()


_P = ParamSpec("_P")


def _moved_by_this_run(exc: BaseException) -> bool:
    """False only for a compare-and-swap refusal (another actor moved the ref); a resync failure is ours."""
    return isinstance(exc, RefResyncError) or not isinstance(exc, (RefAdvanceError, RefRestoreError))


def _records_post_mutation_tips(phase: Callable[Concatenate[_MergeRunState, _P], None]) -> Callable[Concatenate[_MergeRunState, _P], None]:
    """Record the live post-mutation tips when a ref-moving step exits (#5318 / #5332).

    The rollback authority CAS-restores each snapshotted branch against the tip
    this attempt LEFT it at. Recording on the normal end, every early ``return``
    and a raising phase alike attributes a partial advance to this attempt (so
    ``--abort`` can undo it) instead of looking foreign. Only branches whose tip
    CHANGED during this phase are (re)recorded (slice-10 F2): the entry tips are
    captured before the phase runs, so a foreign commit that landed between
    phases is never attributed to this run. Lane branches are never recorded.

    Two exceptions on the raising path (review cycle 1):

    * A ``RefAdvanceError``/``RefRestoreError`` means a compare-and-swap detected
      ANOTHER actor moving the ref. Recording that tip would make the foreign
      commit look like this run's own and a later rollback would restore over it
      (FR-007 / #4996), so nothing is recorded; the branch then reports
      ``NOT_RESTORED``. The exception is its :class:`RefResyncError` subclass:
      OUR compare-and-swap won and only a checkout resync failed, so the ref
      holds this run's own tip and IS recorded (slice-10 F1).
    * Recording is best-effort while an error is already propagating: a recorder
      failure (state I/O, missing git) must never replace the phase's own error.
      On the normal path a recorder failure is the only error and propagates.
    """

    @functools.wraps(phase)
    def recorded(run: _MergeRunState, *args: _P.args, **kwargs: _P.kwargs) -> None:
        entry_tips = rollback.movable_branch_tips(run.main_repo, run.state)
        try:
            phase(run, *args, **kwargs)
        except BaseException as exc:
            if _moved_by_this_run(exc):
                with contextlib.suppress(Exception):
                    rollback.record_post_mutation_tips(run.main_repo, run.state, entry_tips=entry_tips)
            raise
        rollback.record_post_mutation_tips(run.main_repo, run.state, entry_tips=entry_tips)

    return cast("Callable[Concatenate[_MergeRunState, _P], None]", recorded)


def _assert_mission_terminal_ready(run: _MergeRunState) -> None:
    """Unconditional merge-ready precondition (T007, FR-001/002/006, #4764).

    Refuses via ``typer.Exit(1)`` BEFORE any mutation when a non-cancelled WP
    is not yet at an acceptable ending — regardless of ``policy.merge_gates.mode``
    (never routed through the mode-softened evidence gate; C-003, no new error
    type). Built on the single shared aggregate
    :func:`~specify_cli.status_lanes.mission_terminal_acceptability` (FR-009 /
    C-SHARED-AUTHORITY), imported via the ``specify_cli.status`` facade for the
    event-log reader (C-002).

    Evaluated over ``run.all_wp_ids`` — the mission's WPs already minus
    ``run.excluded_canceled_wp_ids`` (WPs resolved ONCE at lock entry via
    :func:`~specify_cli.consolidation.done_bookkeeping.acceptably_canceled_wp_ids`,
    i.e. cancellations that already carry operator provenance and are always
    an acceptable ending) — so this call re-derives no cancellation logic of
    its own; it only asks the shared aggregate whether every remaining WP has
    reached ``approved``/``done``. A cancellation WITHOUT provenance stays in
    ``all_wp_ids`` and is correctly reported missing (US1-6).

    A WP declared in ``run.all_wp_ids`` but ABSENT from the reduced snapshot
    (no status event on the read surface at all) is treated as NOT ready and
    folded into ``missing`` — never silently dropped. A gate this is meant to
    be fail-CLOSED cannot fail-open on a WP the reducer has no record of; a
    missing snapshot entry is strictly less evidence of readiness than an
    ``in_progress`` one, so it must refuse, not pass. That absent-WP
    fail-closed rule is owned by the shared aggregate itself (its
    ``expected_wp_ids`` keyword) — this call no longer re-derives it locally
    (dedup fold, #4764).
    """
    from specify_cli.status import read_events, reduce
    from specify_cli.status_lanes import mission_terminal_acceptability

    snapshot = reduce(read_events(run.feature_dir))
    work_packages = snapshot.work_packages if hasattr(snapshot, "work_packages") else {}
    relevant = {wp_id: work_packages[wp_id] for wp_id in run.all_wp_ids if wp_id in work_packages}
    ok, missing = mission_terminal_acceptability(relevant, expected_wp_ids=run.all_wp_ids)
    if ok:
        return
    console.print(f"\n[red]Error:[/red] Mission is not merge-ready — WP(s) missing review approval: {', '.join(missing)}.")
    console.print(
        "  No lane consolidation and no mission_number bake have occurred; "
        "the mission is unchanged. Move the listed WP(s) through review "
        "(approved/done), or cancel them with operator provenance, then "
        "re-run the merge."
    )
    # Landing-pass remediation (#4764): the fresh run's own just-created state
    # is cleared by :func:`_clear_fresh_record_on_pre_mutation_exit`, which owns that rule for
    # EVERY pre-mutation exit (#5111), not just this one.
    raise typer.Exit(1)


def _phase_gates_and_state(run: _MergeRunState) -> None:
    """Unconditional merge-ready precondition, banner, merge gates, and
    bootstrap/hollow-review history guards.

    The review-artifact consistency gate runs in ``_run_lane_based_consolidation_locked``
    BEFORE merge-state is created (so a rejected mission writes no state.json).

    T007: ``_assert_mission_terminal_ready`` runs FIRST, at the top of this
    phase — before any console output that could be mistaken for progress, and
    strictly before ``_phase_merge_lanes`` (the first mutating phase). It is
    unconditional across ``policy.merge_gates.mode`` (FR-002).
    """
    from specify_cli.policy.config import load_policy_config
    from specify_cli.policy.merge_gates import evaluate_merge_gates

    _assert_mission_terminal_ready(run)

    lanes_manifest = run.lanes_manifest

    if run.is_resume:
        console.print(f"[bold cyan]Resuming[/bold cyan] merge for {run.mission_slug} ({len(run.state.completed_wps)}/{len(run.state.wp_order)} WPs already done)")

    console.print(f"[bold]Lane-based merge for {run.mission_slug}[/bold]")
    console.print(f"  Mission branch: {lanes_manifest.mission_branch}")
    console.print(f"  Lanes: {', '.join(ln.lane_id for ln in lanes_manifest.lanes)}")
    if run.planning_artifact_only:
        console.print("  [dim]Planning-artifact-only mission: target branch already contains deliverables; branch merge steps will be skipped.[/dim]")

    policy = load_policy_config(run.main_repo)
    gate_eval = evaluate_merge_gates(
        run.feature_dir,
        run.mission_slug,
        run.all_wp_ids,
        policy.merge_gates,
        run.main_repo,
    )
    for gate in gate_eval.gates:
        icon = "[green]✓[/green]" if gate.verdict == "pass" else "[yellow]⚠[/yellow]" if not gate.blocking else "[red]✗[/red]"
        console.print(f"  {icon} Gate {gate.gate_name}: {gate.details}")
    if not gate_eval.overall_pass:
        console.print("\n[red]Error:[/red] Merge gates failed.")
        raise typer.Exit(1)

    # -- Bootstrap-only canonical history guard (issue #1069) --
    _enforce_canonical_status_history(
        feature_dir=run.feature_dir,
        mission_slug=run.mission_slug,
        wp_ids=run.all_wp_ids,
    )
    _warn_or_confirm_hollow_reviews(
        feature_dir=run.feature_dir,
        wp_ids=run.all_wp_ids,
        assume_yes=run.assume_yes,
    )


def _lane_branch_ref_exists(run: _MergeRunState, lane_branch: str) -> bool:
    """True iff ``refs/heads/<lane_branch>`` currently resolves."""
    ret, _out, _err = run_command(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{lane_branch}"],
        capture=True,
        check_return=False,
        cwd=run.main_repo,
    )
    return bool(ret == 0)


def _lane_completed_but_branch_gone(run: _MergeRunState, lane: ExecutionLane, lane_branch: str) -> bool:
    """Resume tolerance (#5021 r1): a torn-down-but-already-done lane is integrated.

    ``_lane_already_integrated`` is conservatively ``False`` whenever the lane
    branch does not resolve (correct for a FRESH merge — an unresolvable branch
    there is a real error). On ``--resume`` after a crash mid-teardown, teardown
    may have already deleted the lane branch (:func:`_phase_cleanup_worktrees_
    and_branches` runs LANE branch deletion before coordination teardown) even
    though the merge had already fully landed. ``state.completed_wps`` is
    populated only AFTER a WP's mission→target ``done`` bookkeeping already
    committed (:func:`~specify_cli.consolidation.done_bookkeeping.mark_wp_complete`),
    which itself only runs after lane consolidation + the mission→target merge
    both already succeeded — so "branch gone" + "every WP in this lane already
    recorded done" is a sound, durable "nothing left to merge" signal. Fails
    closed: only fires on resume, only when the branch is truly gone, and only
    when EVERY WP the lane carries is already done — a lane with any
    not-yet-done WP still runs the real merge attempt (and any genuine error
    surfaces there, exactly as the conservative branch already does).
    """
    if not run.is_resume or not lane.wp_ids:
        return False
    if _lane_branch_ref_exists(run, lane_branch):
        return False
    completed = set(run.state.completed_wps)
    return all(wp in completed for wp in lane.wp_ids)


def _created_lane_worktree(main_repo: Path, mission_slug: str, lane_id: str) -> Path:
    """The lane's CREATED worktree, from the placement authority (PD-1).

    Routes through :func:`~specify_cli.lanes.worktree_allocator.predict_lane_worktree`
    (the single read-only lane-placement decision) rather than composing the
    path independently, so this seam and the allocator can never disagree.
    """
    from specify_cli.lanes.worktree_allocator import predict_lane_worktree

    # Re-wrap: mypy widens the late-imported return to Any (follow_imports=skip).
    path, _branch = predict_lane_worktree(main_repo, mission_slug, lane_id)
    return Path(path)


@_records_post_mutation_tips
def _phase_merge_lanes(run: _MergeRunState) -> None:
    """Merge each lane branch into the mission branch (skipping integrated lanes)."""
    from specify_cli.lanes.compute import is_repo_root_lane
    from specify_cli.lanes.consolidation import consolidate_lane_into_mission

    lanes_manifest = run.lanes_manifest
    # The manifest slug is the ONE naming input; run.mission_slug is checked
    # equal to it for a real run rather than read directly below, so a future
    # divergence between the two fails loud here instead of silently
    # naming/consolidating against two different slugs.
    if run.mission_slug != lanes_manifest.mission_slug:
        raise LaneNamingSlugMismatch(
            f"run.mission_slug {run.mission_slug!r} != "
            f"lanes_manifest.mission_slug {lanes_manifest.mission_slug!r} "
            "(lane naming is keyed on the manifest slug alone)"
        )
    for lane in lanes_manifest.lanes:
        # #5100 T020: keyed on the LANE (is_repo_root_lane), never on
        # ``run.planning_artifact_only`` -- a single_branch repo-root lane
        # holding CODE WPs has no lane branch to merge regardless of whether
        # the whole run is planning-artifact-only (it is not, for a
        # single_branch mission with code WPs). This replaces the former
        # ``planning_artifact_only``-gated skip; that field keeps its other
        # uses in this module unchanged.
        if is_repo_root_lane(lane):
            console.print(f"  [green]✓[/green] {lane.lane_id} already on {lanes_manifest.target_branch}")
            continue

        # FR-004 / FR-009: skip branch integration ONLY when EVERY WP in the lane
        # is a canceled-with-provenance acceptable ending (its lane branch may
        # never have been created — the #2945 shape). A mixed lane (survivors +
        # canceled) still integrates its survivors, so this guard requires ALL
        # WPs excluded, never merely any.
        if _lane_fully_canceled(lane, run.excluded_canceled_wp_ids):
            console.print(f"  [dim]Skipping {lane.lane_id} (all WPs canceled with provenance — acceptable ending, no branch to integrate)[/dim]")
            continue

        # FR-037: skip ONLY when the lane branch is already fully integrated into
        # the mission branch (real tree state), never on the ``done`` proxy.
        _lane_branch = _created_lane_branch(lanes_manifest, lane.lane_id)
        if not is_repo_root_lane(lane) and (
            _lane_already_integrated(run.main_repo, _lane_branch, lanes_manifest.mission_branch) or _lane_completed_but_branch_gone(run, lane, _lane_branch)
        ):
            console.print(f"  [dim]Skipping {lane.lane_id} (already integrated into {lanes_manifest.mission_branch})[/dim]")
            continue
        run.any_lane_had_unintegrated_code = True

        console.print(f"  [dim]Checking and merging {lane.lane_id}...[/dim]")
        lane_result = consolidate_lane_into_mission(run.main_repo, run.mission_slug, lane.lane_id, lanes_manifest)
        if lane_result.success:
            console.print(f"  [green]✓[/green] {lane.lane_id} → {lanes_manifest.mission_branch}")
        else:
            # T005: tolerate already-merged lanes on retry
            already_merged = any("already" in e.lower() or "up to date" in e.lower() or "ancestor" in e.lower() for e in lane_result.errors)
            if run.is_resume and already_merged:
                console.print(f"  [dim]{lane.lane_id} already merged, continuing[/dim]")
            else:
                for error in lane_result.errors:
                    console.print(f"  [red]✗[/red] {lane.lane_id}: {error}")
                raise typer.Exit(1)


def _phase_baseline_and_surface(run: _MergeRunState) -> None:
    """Capture target baseline SHA, resolve canonical mission_id + status surface paths."""
    lanes_manifest = run.lanes_manifest
    # -- Capture target baseline SHA for post-merge diff/review checks (T013) --
    _ret, target_baseline_sha, _err = run_command(
        ["git", "rev-parse", lanes_manifest.target_branch],
        capture=True,
        check_return=False,
        cwd=run.main_repo,
    )
    run.target_baseline_sha = target_baseline_sha.strip() if _ret == 0 else "HEAD~1"

    # -- Resolve the canonical mission_id (ULID) to gate modern-mission invariants --
    # FR (#2186): baseline identity is a PRIMARY_METADATA read. Route it onto the
    # PRIMARY anchor (``target_feature_dir`` is the pre-routed
    # ``placement_seam(...).read_dir(PRIMARY_METADATA)`` result (WP06,
    # read-side-seam-primary-primitive-closure-01KYKMMT T029) — the SAME primary
    # leg the :1000/:1022 identity reads use). Reading off the coord-aware
    # ``run.feature_dir`` STATUS leg lands on the meta-less / sentinel
    # ``-coord`` husk for a coord-topology mission → a None/wrong baseline id.
    # ``run.feature_dir`` stays the coord STATUS leg, untouched (C-001).
    try:
        run.baseline_mission_id = resolve_mission_identity(run.target_feature_dir).mission_id
    except Exception:  # noqa: BLE001 — meta.json may be missing/corrupt for legacy missions
        run.baseline_mission_id = None

    status_surface_path = resolve_status_surface(run.main_repo, run.mission_slug)
    from specify_cli.lanes.single_branch_landing import lands_mission_branch

    in_worktree_surface = is_under_worktrees_segment(status_surface_path) and not run.planning_artifact_only
    run.done_marked_before_target = in_worktree_surface or lands_mission_branch(run.main_repo, run.lanes_manifest)
    run.canonical_events_path = status_surface_path
    run.canonical_status_path = status_surface_path.parent / _STATUS_FILENAME
    run.merge_state_path = get_state_path(run.main_repo, run.state.mission_id)


@_records_post_mutation_tips
def _phase_bake_and_pre_target_done(run: _MergeRunState) -> None:
    """Bake mission_number on the mission branch and pre-target done bookkeeping."""
    lanes_manifest = run.lanes_manifest
    if run.planning_artifact_only:
        console.print(f"  [dim]Skipping mission branch merge; {lanes_manifest.target_branch} is the planning artifact branch.[/dim]")
        run.mission_already_applied = True
        return

    # -- WP10/T053/T055: assign dense integer mission_number on mission branch --
    # #4900: thread the assigned number (rather than discard it) so the
    # target-tree write + read-back in ``_phase_capture_and_baseline`` /
    # ``_phase_commit_and_assert`` has it, instead of depending on the
    # squash + merge-driver reconciliation alone.
    try:
        run.assigned_mission_number = _bake_mission_number_into_mission_branch(
            main_repo=run.main_repo,
            mission_slug=run.mission_slug,
            mission_branch=lanes_manifest.mission_branch,
            target_branch=lanes_manifest.target_branch,
            dry_run=False,
            merge_state=run.state,
        )
    except BaselineMergeCommitError as exc:
        # No mission_number can be determined at all (the
        # bake refused before writing anything, strictly before the target is
        # touched) -- surface it and exit 1 instead of finishing with a
        # ``null`` target and exit 0.
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
    # #4764 FOLD-F1: detect + re-anchor past a primary-tree bake commit that
    # just landed directly on target_branch (see field docstring above).
    _reanchor_baseline_past_primary_tree_bake(run)

    if run.done_marked_before_target:
        assert run.canonical_events_path is not None
        assert run.canonical_status_path is not None
        assert run.merge_state_path is not None
        run.pre_target_bookkeeping_snapshots.update(
            _capture_merge_snapshots(
                run.main_repo,
                run.canonical_events_path,
                run.canonical_status_path,
                run.merge_state_path,
            )
        )
        # #2711 FR-006: capture the coordination-branch tip BEFORE the ``done``
        # emit so a rollback can revert the committed ``done`` coherently.
        _capture_pre_target_coord_ref_sha(run)
        # #2786 / #2367-B FR-005: record THIS merge's ``done`` write-set (the
        # marker's candidate set) BEFORE the bake, so the strand derivation
        # excludes any legitimately-pre-existing-``done`` WP.
        _capture_pre_target_done_write_set(run)
        # Modern coordination-backed missions must carry done events in the
        # mission branch before it is merged to target.
        try:
            _record_merged_wps_done_for_merge(
                main_repo=run.main_repo,
                feature_dir=run.feature_dir,
                mission_slug=run.mission_slug,
                lanes_manifest=lanes_manifest,
                target_branch=lanes_manifest.target_branch,
                merge_state=run.state,
                all_wp_ids=run.all_wp_ids,
            )
        except Exception as exc:
            _restore_and_guard_coord_coherence(run, run.pre_target_bookkeeping_snapshots, error=exc)
            # #4764/FOLD-A (sibling of FOLD-F1): a primary-tree
            # ``mission_number`` bake may have just committed directly on
            # ``target_branch`` (the ``_reanchor_baseline_past_primary_tree_bake``
            # call above). This failure is strictly BEFORE the mission→target
            # step, so ``_restore_pre_target_if_at_baseline`` never runs for
            # it -- without this guard the orphan bake commit is permanently
            # stranded on an unmerged mission's target branch. Uses the SAME
            # still-at-baseline guard that function uses.
            if _target_branch_still_at_baseline(
                run.main_repo,
                run.lanes_manifest.target_branch,
                run.target_baseline_sha,
            ):
                _revert_orphan_target_bake_commit(run)
            raise


def _reanchor_baseline_past_primary_tree_bake(run: _MergeRunState) -> None:
    """#4764 FOLD-F1: detect + re-anchor past a primary-tree bake commit.

    The coord-topology ``_bake_mission_number_on_primary_tree`` fallback
    (``ordering.py``, invoked when meta.json is absent on the mission-branch
    tree) commits directly on ``run.main_repo``'s current checkout, which
    never leaves ``target_branch`` during a merge. Re-reading the target tip
    right after the bake call and comparing it to ``run.target_baseline_sha``
    (captured in ``_phase_baseline_and_surface``, strictly before the bake)
    detects exactly that case -- the mission-branch write path (the common
    case) never touches ``target_branch``, so this is a proven no-op there.

    When the tip moved, the ORIGINAL pre-bake tip is retained in
    ``run.pre_bake_target_baseline_sha`` (the later rollback's revert anchor
    -- see :func:`_revert_orphan_target_bake_commit`) and
    ``run.target_baseline_sha`` is re-anchored to the new tip so
    ``_target_branch_still_at_baseline`` keeps measuring the mission→target
    step's OWN progress, not this bookkeeping commit.
    """
    ret, current_tip, _err = run_command(
        ["git", "rev-parse", run.lanes_manifest.target_branch],
        capture=True,
        check_return=False,
        cwd=run.main_repo,
    )
    if ret != 0:
        return
    current_tip = current_tip.strip()
    if current_tip and current_tip != run.target_baseline_sha:
        run.pre_bake_target_baseline_sha = run.target_baseline_sha
        run.target_baseline_sha = current_tip


def _revert_orphan_target_bake_commit(run: _MergeRunState) -> None:
    """#4764 FOLD-F1: undo an orphan primary-tree ``mission_number`` bake commit.

    Fires from :func:`_restore_pre_target_if_at_baseline` once the (re-
    anchored) baseline guard confirms the mission→target step made no
    progress -- i.e. the bake commit is an orphan on ``target_branch`` for a
    mission that never merged and must be undone too (US3-1), not just
    halted.

    Mirrors :func:`_reset_coord_to_checkpoint`'s forward-reversing ``git
    revert`` discipline (never a raw ``update-ref``/hard reset -- AC-B3),
    applied directly to ``run.main_repo`` since the primary-tree bake
    committed there and the main repo's checkout never leaves
    ``target_branch`` during a merge. No-op when no primary-tree bake landed
    on target this run (``pre_bake_target_baseline_sha`` is ``None``).

    Also clears the persisted ``mission_number_baked`` flag (set the moment
    the primary-tree write succeeded, before this later-phase failure was
    even known) so a subsequent ``--resume`` re-attempts the bake instead of
    short-circuiting on a flag that no longer matches the reverted git state
    (FR-008 resume coherence).
    """
    pre_bake_sha = run.pre_bake_target_baseline_sha
    if pre_bake_sha is None:
        return
    from specify_cli.lanes.consolidation import _make_merge_env

    env = _make_merge_env()
    head = subprocess.run(
        ["git", "-C", str(run.main_repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if head.returncode != 0 or head.stdout.strip() == pre_bake_sha:
        run.pre_bake_target_baseline_sha = None
        return  # already at (or before) the pre-bake tip -- no-op
    revert = subprocess.run(
        ["git", "-C", str(run.main_repo), "revert", "--no-edit", f"{pre_bake_sha}..HEAD"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if revert.returncode != 0:
        subprocess.run(
            ["git", "-C", str(run.main_repo), "revert", "--abort"],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        logger.warning(
            "#4764/FOLD-F1: could not revert the orphan mission_number bake commit on %s (%s..HEAD); target may still carry an unmerged bake commit: %s",
            run.lanes_manifest.target_branch,
            pre_bake_sha[:12],
            (revert.stderr or revert.stdout or "").strip(),
        )
        return
    run.pre_bake_target_baseline_sha = None
    if run.state is not None and run.state.mission_number_baked:
        run.state.mission_number_baked = False
        save_state(run.state, run.main_repo)


@dataclass(frozen=True)
class _CoordCheckpoint:
    """T008: a NAMED, resolved coordination-branch checkpoint (ref + tip SHA).

    The one shape unifying what were three fragmentary capture/revert/
    coherence-guard functions (``_capture_pre_target_coord_ref_sha``,
    ``_restore_and_guard_coord_coherence``, ``_revert_coord_done_commit``,
    pre-T008). A checkpoint is captured via :func:`_capture_coord_checkpoint`
    and consumed by :func:`_reset_coord_to_checkpoint`. Two named checkpoints
    are captured over a merge run: ``pre_mutation`` (before
    ``_phase_merge_lanes`` — see ``run.pre_mutation_coord_ref``/``_sha``) and
    ``pre_done`` (before the pre-target ``done`` emit — ``run.pre_target_coord_ref``/
    ``_sha``, the pre-existing #2711 checkpoint, kept under its historical
    field names so existing callers/tests are unaffected).
    """

    ref: str
    sha: str


def _capture_coord_checkpoint(run: _MergeRunState) -> _CoordCheckpoint | None:
    """Resolve + capture the coordination branch's CURRENT ref + tip SHA.

    Pure resolution step shared by every named checkpoint. The ref is sourced
    from the canonical write-target ``done``/bake commits resolve to
    (``resolve_placement_only(..., kind=STATUS_STATE).ref``) — NOT an inline
    ``meta.get("coordination_branch")`` (the retired D-2 CWD-divergence
    class). Returns ``None`` when the placement cannot be resolved (a
    non-coord topology, or a legacy mission) — every checkpoint built from
    ``None`` is a proven no-op wherever it is later consumed.
    """
    try:
        coord_ref = resolve_placement_only(run.main_repo, run.mission_slug, kind=MissionArtifactKind.STATUS_STATE).ref
    except Exception:  # noqa: BLE001 — unresolvable placement: skip the coherent revert
        return None
    ret, sha, _err = run_command(
        ["git", "rev-parse", coord_ref],
        capture=True,
        check_return=False,
        cwd=run.main_repo,
    )
    if ret == 0 and sha.strip():
        return _CoordCheckpoint(ref=coord_ref, sha=sha.strip())
    return None


def _capture_pre_mutation_coord_checkpoint(run: _MergeRunState) -> None:
    """T008 (FR-007/008): capture the coordination checkpoint BEFORE ANY
    mutation begins — called right before ``_phase_merge_lanes``, the first
    mutating phase. On a coord-topology mission (``lanes_manifest.mission_branch
    == coordination_branch`` — the 083+ layout) lane consolidation commits
    land on this SAME branch, so this checkpoint is strictly earlier than (and
    on a mission with real lane commits, distinct from) the pre-``done``
    checkpoint captured later in ``_phase_bake_and_pre_target_done``. Resetting
    to THIS checkpoint on a post-mutation failure undoes consolidation AND the
    bake AND the pre-target ``done`` write together (see
    :func:`_rollback_to_pre_mutation_checkpoint`).
    """
    checkpoint = _capture_coord_checkpoint(run)
    if checkpoint is not None:
        run.pre_mutation_coord_ref = checkpoint.ref
        run.pre_mutation_coord_sha = checkpoint.sha


def _capture_pre_target_coord_ref_sha(run: _MergeRunState) -> None:
    """Capture the coordination-branch ref + tip SHA BEFORE the pre-target
    ``done`` emit (#2711 / FR-006).

    The captured tip is the coherent rollback anchor consumed by
    :func:`_revert_coord_done_commit`. A placement that cannot be resolved (a
    non-coord topology, or a legacy mission) leaves both fields ``None`` so the
    rollback revert is a proven no-op. T008: delegates checkpoint resolution to
    the shared :func:`_capture_coord_checkpoint` primitive; field names/external
    behavior preserved verbatim for existing callers.
    """
    checkpoint = _capture_coord_checkpoint(run)
    if checkpoint is not None:
        run.pre_target_coord_ref = checkpoint.ref
        run.pre_target_coord_sha = checkpoint.sha


def _coord_reconcile_read_feature_dir(run: _MergeRunState) -> Path:
    """Primary feature dir (name == slug) anchoring the committed-coord read.

    Mirrors ``done_bookkeeping._durable_done_wps_on_coordination_ref``: a
    ``WORK_PACKAGE_TASK`` read folds onto the topology-blind
    ``primary_feature_dir_for_mission`` (name == slug), so the coord-ref path
    (``kitty-specs/<slug>/status.events.jsonl``) and the legacy-parse dir match
    the placement the rollback used — no ``-coord`` husk, no re-resolution drift.
    """
    feature_dir: Path = placement_seam(run.main_repo, run.mission_slug).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK)
    return feature_dir


def _capture_pre_target_done_write_set(run: _MergeRunState) -> None:
    """Record the WPs THIS merge will newly bake ``done`` (#2786 / #2367-B FR-005).

    The write-set is every lane WP that is NOT already durably ``done`` on the
    committed coordination ref at bake time. Handing this (never
    ``run.all_wp_ids``) to :func:`coord_incoherent_done_wps` excludes a
    genuinely-pre-existing-``done`` WP by construction, so a resume never
    re-strands a legitimately-done WP. The reduction is the single coordination
    authority (``coord_incoherent_done_wps``) — never re-derived locally. When
    the coordination ref is unresolved (non-coord topology / legacy mission) the
    write-set degrades to all WPs; it is unused off the coord path.
    """
    coord_ref = run.pre_target_coord_ref
    if not coord_ref:
        run.pre_target_done_write_set = list(run.all_wp_ids)
        return
    pre_existing_done = set(
        coord_incoherent_done_wps(
            coord_ref,
            run.all_wp_ids,
            repo_root=run.main_repo,
            feature_dir=_coord_reconcile_read_feature_dir(run),
        )
    )
    run.pre_target_done_write_set = [wp for wp in run.all_wp_ids if wp not in pre_existing_done]


def _coord_worktree_root(run: _MergeRunState) -> Path | None:
    """Resolve the coordination worktree carrying the pre-target ``done`` commit.

    Derived from the resolved status surface
    (``canonical_events_path`` == ``<coord-worktree>/kitty-specs/<slug>/status.events.jsonl``).
    Returns ``None`` for a non-coord topology (no coordination worktree — the
    ``single_branch`` / ``lanes`` no-op case).
    """
    events_path = run.canonical_events_path
    if events_path is None:
        return None
    # Strip ``status.events.jsonl`` / ``<slug>`` / ``kitty-specs`` -> worktree root.
    worktree_root = events_path.parents[2]
    if not is_under_worktrees_segment(worktree_root):
        return None
    return worktree_root


def _reset_coord_to_checkpoint(run: _MergeRunState, checkpoint: _CoordCheckpoint | None) -> None:
    """T008: the ONE reset primitive — revert the coordination branch back to
    ``checkpoint`` via a forward-reversing ``git revert`` (never a raw
    ``git update-ref``/hard reset — AC-B3; ``advance_branch_ref`` cannot serve
    here because moving the ref back to the captured tip is the non-fast-forward
    move it refuses by design). Reverses every commit made since the checkpoint
    tip — on the pre-mutation checkpoint this undoes lane consolidation, the
    mission_number bake, AND the pre-target ``done`` write together, since a
    coord-topology mission's ``lanes_manifest.mission_branch`` IS the
    coordination branch (the 083+ layout) — consolidation commits land on the
    SAME branch this resets. Idempotent: a HEAD already at (or before) the
    checkpoint is a proven no-op, so calling this after a narrower rollback
    already ran (e.g. :func:`_revert_coord_done_commit`) safely extends the
    revert range rather than double-reverting.

    Subprocess env routes through ``_make_merge_env`` (AC-F1). This is the
    #2711 in-merge lockstep revert on the (still-clean) pre-restore worktree —
    kept in its canonical raw form (its no-op / success / abort branches are
    pinned by ``test_executor_option_a_revert_helpers_2711.py``).

    Fail-closed detection (T008 edge case — "rollback attempted after the
    coordination worktree has already been torn down"): logs a loud warning
    when a checkpoint reset was due on a mission that had already reached the
    coord-topology ``done``-marking point (``run.done_marked_before_target``)
    but the coordination worktree cannot be resolved — the structural ordering
    guarantee is that this function is only ever invoked before
    ``_phase_cleanup_worktrees_and_branches`` tears that worktree down, so this
    branch should be unreachable; the warning surfaces a genuine ordering bug
    rather than silently no-op-ing.
    """
    if checkpoint is None:
        return
    coord_worktree = _coord_worktree_root(run)
    if coord_worktree is None:
        if getattr(run, "done_marked_before_target", False):
            logger.warning(
                "T008: a coordination checkpoint reset to %s (%s) was due, but "
                "the coordination worktree is unresolved. If teardown already "
                "ran, this reset was ordered too late (a bug); otherwise this "
                "is a legitimate no-op (nothing was mutated on the coordination "
                "branch yet).",
                checkpoint.ref,
                checkpoint.sha[:12],
            )
        return
    from specify_cli.lanes.consolidation import _make_merge_env

    env = _make_merge_env()
    head = subprocess.run(
        ["git", "-C", str(coord_worktree), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if head.returncode != 0 or head.stdout.strip() == checkpoint.sha:
        return  # nothing committed on the coordination branch since capture — no-op
    revert = subprocess.run(
        ["git", "-C", str(coord_worktree), "revert", "--no-edit", f"{checkpoint.sha}..HEAD"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if revert.returncode != 0:
        subprocess.run(
            ["git", "-C", str(coord_worktree), "revert", "--abort"],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        logger.warning(
            "#2711/T008: could not revert coordination commit(s) on %s (%s..HEAD); committed/working coherence may be degraded: %s",
            checkpoint.ref,
            checkpoint.sha[:12],
            (revert.stderr or revert.stdout or "").strip(),
        )


def _revert_coord_done_commit(run: _MergeRunState) -> None:
    """Revert the pre-target ``done`` commit on the coordination branch (#2711 / FR-006).

    On a target-advance rollback the committed coordination ``done`` must be
    reversed in lockstep with the working-tree byte restore, or the committed
    reduction (``done``) diverges from the rolled-back working tree (``approved``)
    — the #2711 split-brain, which also breaks resume dedup / idempotency.

    T008: thin wrapper delegating to the unified :func:`_reset_coord_to_checkpoint`
    primitive with the pre-``done`` checkpoint (``run.pre_target_coord_ref``/
    ``_sha``) — external behavior/signature preserved verbatim for existing
    callers. The NEW #2786 / #2367-B reconciliation authority is the
    resume/doctor heal, which routes through the shared coordination primitive
    ``repair_coord_strand`` (see :func:`_heal_pending_coord_reconcile`); this
    leg stays orthogonal.
    """
    coord_ref = run.pre_target_coord_ref
    captured_sha = run.pre_target_coord_sha
    if not coord_ref or not captured_sha:
        return  # no coordination ref captured (non-coord topology) — no-op
    _reset_coord_to_checkpoint(run, _CoordCheckpoint(ref=coord_ref, sha=captured_sha))


def _persist_coord_reconcile_marker(run: _MergeRunState, error: BaseException | None) -> None:
    """Durably record a stranded committed-coord ``done`` (#2786 / #2367-B FR-005).

    Derives the strand set from the COMMITTED coordination ref (never a
    committed-vs-working diff, which is empty at the mark point per data-model D7)
    via the single coordination authority :func:`coord_incoherent_done_wps` over
    THIS merge's ``done`` write-set — so the marker names the SPECIFIC WP(s) this
    merge stranded, excluding both a coherent (only-``approved``) WP and a
    genuinely-pre-existing-``done`` WP. Writes the marker (via ``save_state``) only
    when the strand is non-empty (an empty strand is not a strand). Mark-not-raise:
    the caller keeps propagating its original failure; this merely records.
    """
    coord_ref = run.pre_target_coord_ref
    captured_sha = run.pre_target_coord_sha
    if not coord_ref or not captured_sha:
        return
    coord_worktree = _coord_worktree_root(run)
    if coord_worktree is None:
        return
    stranded = coord_incoherent_done_wps(
        coord_ref,
        run.pre_target_done_write_set,
        repo_root=run.main_repo,
        feature_dir=_coord_reconcile_read_feature_dir(run),
    )
    if not stranded:
        return
    run.state.pending_coord_reconcile = {
        "coord_ref": coord_ref,
        "captured_sha": captured_sha,
        "coord_worktree": str(coord_worktree),
        "stranded_wp_ids": list(stranded),
        "revert_error": str(error) if error is not None else None,
        "detected_at": now_utc_iso(),
    }
    save_state(run.state, run.main_repo)


def _heal_pending_coord_reconcile(run: _MergeRunState) -> None:
    """Strand-gated ``git revert`` heal of a pending coord-reconcile marker (FR-006).

    Delegates the repair to the single self-sufficient coordination authority
    :func:`repair_coord_strand` (which re-derives the strand from the committed
    ref and no-ops if already coherent — a blind ``git revert captured_sha..HEAD``
    would re-apply ``done`` and is rejected). The primitive itself performs the
    scoped clean-to-HEAD (after its strand gate, before the revert) so the forward
    revert can apply over the byte-restored (dirty) tree — this caller no longer
    pre-cleans, keeping the clean happening exactly once, inside the primitive.
    Idempotent (NFR-002): the marker is cleared atomically with the heal only once
    the revert commits (or the ref is already coherent — a stale marker heals to a
    no-op clear). A revert that could not be applied leaves the marker for the next
    resume/doctor pass.
    """
    marker = run.state.pending_coord_reconcile
    if not marker:
        return
    coord_worktree = Path(str(marker["coord_worktree"]))
    outcome: CoordRepairOutcome = repair_coord_strand(
        coord_ref=str(marker["coord_ref"]),
        captured_sha=str(marker["captured_sha"]),
        coord_worktree=coord_worktree,
        candidate_wps=[str(wp) for wp in marker.get("stranded_wp_ids", [])],
        repo_root=run.main_repo,
        feature_dir=_coord_reconcile_read_feature_dir(run),
    )
    # Clear the marker only on a genuine heal OR a re-derived-coherent no-op.
    # A ``worktree_missing`` short-circuit returns an EMPTY ``stranded_wp_ids``
    # because the strand was never checked (the worktree is gone) — NOT because
    # it is coherent. Clearing on that would erase the marker for an unresolved
    # committed split-brain, making it invisible to a later doctor/resume once the
    # worktree is re-materialized (debugger-debbie HIGH). Preserve it.
    if outcome.healed or (not outcome.stranded_wp_ids and not outcome.worktree_missing):
        run.state.pending_coord_reconcile = None
        save_state(run.state, run.main_repo)


@_records_post_mutation_tips
def _restore_and_guard_coord_coherence(
    run: _MergeRunState,
    snapshots: dict[Path, bytes | None],
    *,
    error: BaseException | None = None,
) -> None:
    """Restore primitive (FR-008 structural): byte-restore + coord-coherence guard.

    Co-locates the coherence mark/heal AT the ``restore_generated_artifact_snapshots``
    seam so a future restore site cannot strand silently — EVERY restore call-site
    routes through here (the primary marking mechanism; the hand-picked marks are
    reached THROUGH it, no double-mark). Inner-only (not the INV-5 phase-driver
    wrapper): leg-b byte-restore always runs first and is preserved verbatim. On a
    coord-topology rollback it records any residual strand (mark-not-raise) and, on
    a resume, heals it via the strand-gated coordination primitive. Off the coord
    path (``done_marked_before_target`` False) it is a pure byte-restore.
    """
    restore_generated_artifact_snapshots(snapshots)
    if not run.done_marked_before_target:
        return
    _persist_coord_reconcile_marker(run, error)
    if run.is_resume:
        _heal_pending_coord_reconcile(run)


@_records_post_mutation_tips
def _rollback_to_pre_mutation_checkpoint(run: _MergeRunState, *, error: BaseException | None) -> None:
    """T008 (FR-007/008): the pre-mutation-checkpoint backstop.

    Wraps ONLY ``_phase_merge_lanes`` in ``_run_lane_based_consolidation_locked`` (see
    the scope note at that call site): on an exception from lane
    consolidation, resets the coordination ref + worktree back to the
    checkpoint captured strictly before it began (see
    :func:`_capture_pre_mutation_coord_checkpoint`) via
    :func:`_reset_coord_to_checkpoint`, and marks/heals any residual strand
    through the SAME coordination-reconcile primitive the later, denser
    granular rollback sites use (``_phase_capture_and_baseline``,
    ``_phase_record_done_and_project``, ``_phase_porcelain_invariant``,
    ``_phase_mission_to_target``) — those cover every later mutating phase
    with their own (git-safe, never spanning a lane-consolidation merge
    commit) pre-``done`` checkpoint; this function closes the one remaining
    gap, a failure DURING consolidation itself, which had no rollback
    coverage at all before T008. MUST run before
    ``_phase_cleanup_worktrees_and_branches`` tears the coordination worktree
    down — this function is only ever invoked from the driver's wrapper,
    which sits strictly before that phase in the linear call order.
    """
    checkpoint = (
        _CoordCheckpoint(ref=run.pre_mutation_coord_ref, sha=run.pre_mutation_coord_sha) if run.pre_mutation_coord_ref and run.pre_mutation_coord_sha else None
    )
    _reset_coord_to_checkpoint(run, checkpoint)
    if run.pre_target_bookkeeping_snapshots:
        restore_generated_artifact_snapshots(run.pre_target_bookkeeping_snapshots)
    _persist_coord_reconcile_marker(run, error)
    if run.is_resume:
        _heal_pending_coord_reconcile(run)


@_records_post_mutation_tips
def _restore_pre_target_if_at_baseline(run: _MergeRunState) -> None:
    """Roll back the pre-target state iff the target never advanced (INV-6).

    Behavior-preserving extraction of the repeated mission-to-target rollback
    guard (identical at every failure exit). Restores ONLY when done events were
    recorded pre-target AND the target branch still points at the pre-merge
    baseline — i.e. the mission→target merge made no progress.

    #2711 FR-006 (Option A): the coherent revert of the committed coordination
    ``done`` runs BEFORE the working-byte restore so both legs converge on the
    pre-emit (``approved``) reduction — the committed ref no longer strands a
    ``done`` the working tree has rolled back.

    #4764 FOLD-F1: ``run.target_baseline_sha`` is the RE-ANCHORED baseline
    (post-bake tip, see :func:`_reanchor_baseline_past_primary_tree_bake`), so
    this guard measures the mission→target step's own progress even when a
    primary-tree bake commit landed on ``target_branch`` first. When the
    guard fires, :func:`_revert_orphan_target_bake_commit` additionally undoes
    that orphan bake commit — evaluated independently of
    ``done_marked_before_target`` since the primary-tree bake is orthogonal
    to whether a coordination ``done`` was recorded.
    """
    still_at_baseline = _target_branch_still_at_baseline(
        run.main_repo,
        run.lanes_manifest.target_branch,
        run.target_baseline_sha,
    )
    if run.done_marked_before_target and still_at_baseline:
        _revert_coord_done_commit(run)
        _restore_and_guard_coord_coherence(run, run.pre_target_bookkeeping_snapshots)
    if still_at_baseline:
        _revert_orphan_target_bake_commit(run)


def _reject_zero_diff_noop_integration(run: _MergeRunState) -> None:
    """FR-037 fail-loud: refuse a zero-code no-op mission→target integration.

    Strategy-neutral (#4997 Defect B): the guard condition is content-based
    (``already_applied`` + un-integrated lane work OR the mission tree not equal to the
    target tree), so it applies to the MERGE strategy's "Already up to date" no-op exactly
    as it does to the squash no-op — the name no longer implies squash-only.
    """
    console.print(
        "[red]Error:[/red] Mission→target merge integrated zero lane "
        "diffs but un-integrated lane work remains. Refusing to report a "
        "zero-code integration as success (#1772 FR-037)."
    )
    console.print(
        f"  Mission branch: {run.lanes_manifest.mission_branch}; "
        f"target: {run.lanes_manifest.target_branch}. "
        f"Inspect the lane branches and rerun, or `{_CONSOLIDATE_ABORT_COMMAND}`."
    )
    _restore_pre_target_if_at_baseline(run)
    raise typer.Exit(1)


def _emit_mission_target_content_conflict(
    run: _MergeRunState,
    mission_result: MissionConsolidationResult,
) -> None:
    """Print the #4892 target-content conflict with the SAME code/remediation as ``--dry-run``.

    The real merge previously printed only plain prose here while the dry-run
    forecast emitted a structured ``TARGET_BRANCH_CONTENT_CONFLICT`` code — so an
    operator who trusted the preview got a different, less actionable message on
    the real run. Both paths now speak the same diagnostic vocabulary.
    """
    lanes_manifest = run.lanes_manifest
    # Render the code the result carried (data-driven parity with the dry-run),
    # falling back to the shared constant if a caller left it unset.
    diagnostic_code = getattr(mission_result, "diagnostic_code", None) or TARGET_BRANCH_CONTENT_CONFLICT
    console.print(f"[red]Error:[/red] {TARGET_BRANCH_CONTENT_CONFLICT_HEADER}")
    console.print(f"  diagnostic_code: {diagnostic_code}")
    console.print(f"  mission_branch: {lanes_manifest.mission_branch}")
    console.print(f"  target_branch: {lanes_manifest.target_branch}")
    for path in mission_result.conflicting_paths:
        console.print(f"  conflicting_path: {path}")
    console.print(f"  remediation: {TARGET_BRANCH_CONTENT_CONFLICT_REMEDIATION_UPDATE}")
    console.print("  remediation: Resolve the listed conflicts, then rerun `spec-kitty consolidate`.")


def _handle_mission_merge_result(
    run: _MergeRunState,
    mission_result: MissionConsolidationResult,
    *,
    mission_integrated_into_target: bool,
) -> None:
    """Process the mission→target result: fail-loud / retry-tolerance / success log."""
    lanes_manifest = run.lanes_manifest
    run.mission_already_applied = getattr(mission_result, "already_applied", False) is True
    if run.mission_already_applied and not run.planning_artifact_only and (run.any_lane_had_unintegrated_code or not mission_integrated_into_target):
        _reject_zero_diff_noop_integration(run)

    if not mission_result.success:
        # #4892: a real target-content conflict carries structured paths. NEVER
        # let the resume "already merged" tolerance below fire for it — the
        # tolerance is a substring match on ``errors`` and a conflicting path
        # such as ``tests/test_already_applied.py`` would otherwise read as
        # "already merged" and continue to done-marking/cleanup while the target
        # never moved. Report the SAME diagnostic code + remediation the
        # ``--dry-run`` forecast emits, then fail closed. (``getattr`` mirrors the
        # defensive ``already_applied`` read above — a real ``MissionConsolidationResult``
        # always carries the field.)
        if getattr(mission_result, "conflicting_paths", ()):
            _emit_mission_target_content_conflict(run, mission_result)
            _restore_pre_target_if_at_baseline(run)
            raise typer.Exit(1)
        # T005: tolerate already-merged on retry — but ONLY when the branch trees
        # are actually equal (#4892 hardening). The substring match on error text
        # is fragile: an operational RuntimeError (a failed hook/driver — a
        # non-zero squash with no unmerged paths) carries ``conflicting_paths=()``
        # and embeds raw git stderr, so on resume a stderr that happens to contain
        # "already"/"up to date" would otherwise be tolerated even though the
        # target never received the mission tree. Gating on the tree-equality
        # signal the executor already computed ties the tolerance to the real
        # state, not the message text.
        already_merged = any("already" in e.lower() or "up to date" in e.lower() for e in mission_result.errors)
        if run.is_resume and already_merged and mission_integrated_into_target:
            console.print(f"[dim]{lanes_manifest.mission_branch} already merged into {lanes_manifest.target_branch}[/dim]")
        else:
            for error in mission_result.errors:
                console.print(f"[red]Error:[/red] {error}")
            _restore_pre_target_if_at_baseline(run)
            raise typer.Exit(1)
    else:
        console.print(f"\n[green]✓[/green] {lanes_manifest.mission_branch} → {lanes_manifest.target_branch}")
        if run.mission_already_applied:
            console.print("  [dim]Mission changes already present on target; continuing bookkeeping.[/dim]")
        if mission_result.commit:
            console.print(f"  Commit: {mission_result.commit[:7]}")


def _run_has_code_wps(run: _MergeRunState) -> bool:
    """The WP-kind "has code" question for *run* (#5100 T020 / plan fold B3).

    Delegates to :func:`specify_cli.lanes.compute.has_code_wps` over a
    freshly-built WP-kind index (:func:`build_normalized_wp_index`), never
    ``run.planning_artifact_only`` (lane-based, unchanged for its other
    callers in this module) -- a single_branch mission's ONE repo-root lane
    reads as lane-based "planning-only" even when it holds real CODE WPs.

    #5100 WP04 cycle-2 fix (review issue 2): ONLY an EXPLICIT frontmatter
    ``execution_mode`` (``mode_source == "frontmatter"``) counts as a
    reliable "code" signal here. A WP with no ``execution_mode`` in its
    frontmatter normalizes via :func:`~specify_cli.ownership.inference.infer_execution_mode`,
    which DEFAULTS to ``code_change`` when the body carries neither a
    planning nor a code signal (``mode_source == "inferred_legacy"``) -- the
    prior ``entry.metadata.execution_mode or WorkProductKind.CODE_CHANGE``
    trusted that bare default as "real" code, flipping a genuinely
    lane-planning-only legacy mission into "has code" and wrongly running
    the birth cutover for a bookkeeping-only merge (regression:
    ``test_planning_only_bookkeeping_reaches_target_branch``). Excluding an
    ``inferred_legacy`` entry from the index entirely (never defaulting it)
    means an untyped legacy WP simply does not vote either way, restoring
    the base's conservative lane-based floor for that case while still
    letting an EXPLICITLY-authored ``code_change`` WP (this mission's own
    single_branch-with-code contract) register as real code.

    #5100 WP04 cycle-3 fix (review issue 1): the frontmatter-only filter
    above over-corrected -- it also drops a REAL legacy lanes/coord
    mission's body-evidenced code WP (no explicit ``execution_mode``, but
    the body says e.g. ``src/parser.py``), which ALSO normalizes to
    ``mode_source == "inferred_legacy"``. Delegates to
    :func:`~specify_cli.lanes.compute.mission_has_code`, which ORs this same
    frontmatter-only kind check with the lane-shape floor
    (``has_code_lanes``) -- a real code lane always means code, so a legacy
    mission's per-WP frontmatter ambiguity can never flip it to "no code"
    the way the bare kind check alone just did.
    """
    from specify_cli.lanes.compute import mission_has_code
    from specify_cli.ownership.models import WorkProductKind
    from specify_cli.workspace.context import build_normalized_wp_index

    index = build_normalized_wp_index(run.main_repo, run.mission_slug)
    wp_kinds = {wp_id: WorkProductKind(entry.metadata.execution_mode) for wp_id, entry in index.items() if entry.mode_source == "frontmatter"}
    # bool(...): the project's ``specify_cli.*`` follow_imports=skip mypy
    # setting means this deferred cross-module import's return type is not
    # visible here -- see gates_core.py's module docstring for the same
    # note. ``mission_has_code`` is declared ``-> bool``; this reasserts it.
    return bool(mission_has_code(run.lanes_manifest, wp_kinds))


@_records_post_mutation_tips
def _phase_mission_to_target(run: _MergeRunState) -> None:
    """Merge the mission branch into the target branch (honoring strategy)."""
    lanes_manifest = run.lanes_manifest
    if lanes_manifest.mission_branch == lanes_manifest.target_branch:
        # #5100 T020 / research.md R-9: the unprotected single_branch
        # bookkeeping-only case -- there is no separate mission branch to
        # land, so this phase is a no-op. Checked BEFORE
        # ``run.planning_artifact_only`` below: a single_branch mission's
        # ONE repo-root lane always reads as lane-based "planning-only"
        # (plan fold B3) even when it holds CODE WPs, so gating this skip on
        # that flag alone would also incorrectly no-op a PROTECTED
        # single_branch mission (WP08/IC-05) whose ``mission_branch``
        # genuinely differs from ``target_branch`` and needs to land.
        return
    if run.planning_artifact_only:
        return

    from specify_cli.lanes.consolidation import integrate_mission_into_target

    # FR-037 (#1772 Bug 3): gate the no-op squash recovery on tree equivalence.
    _mission_integrated_into_target = _branch_trees_equal(
        run.main_repo,
        lanes_manifest.mission_branch,
        lanes_manifest.target_branch,
    )
    _allow_noop = run.is_resume and _mission_integrated_into_target
    console.print(f"  [dim]Merging mission branch into {lanes_manifest.target_branch}...[/dim]")
    try:
        mission_result = integrate_mission_into_target(
            run.main_repo,
            run.mission_slug,
            lanes_manifest,
            strategy=run.strategy,
            allow_already_applied=_allow_noop,
        )
    except Exception:
        _restore_pre_target_if_at_baseline(run)
        raise
    _handle_mission_merge_result(run, mission_result, mission_integrated_into_target=_mission_integrated_into_target)


def _resolve_expected_mission_number(run: _MergeRunState) -> int | None:
    """Resolve the mission_number to write + verify on the target tree (#4900).

    Priority, so the SAME number is found on every topology and a stale
    mission-branch value can never overwrite a number the target already
    carries ("target wins", and resume safety):

    1. The TARGET's own CURRENT working-tree value, when it already carries
       an assigned number for this mission. Authoritative -- covers a
       squash that already correctly preserved it (the merge-driver fix), a
       genuinely-completed prior run, AND the coord-topology primary-tree
       fallback (``ordering._bake_mission_number_on_primary_tree`` commits
       DIRECTLY onto ``target_branch``, so by the time this phase runs
       post-squash the target already carries it -- no separate "primary
       tree" read is needed here). Read via
       :func:`~specify_cli.consolidation.ordering._read_target_tree_mission_number`
       (the WORKING TREE, not ``git show``) -- deliberately a DIFFERENT
       mechanism than the ``baseline._read_committed_meta_json`` seam the
       later verify step uses, so a broken read/decode seam cannot make
       "what we expect" and "did it land" agree vacuously (mirrors
       ``baseline._recorded_baseline_from_working_meta``'s same
       independence for the baseline invariant).
    2. ``run.assigned_mission_number`` -- the number THIS run's
       mission-branch bake just freshly computed. Only reached when the
       target did NOT already have one, so it can never disagree with (1).
    3. The mission branch's own committed value, when this run's bake
       short-circuited (resume / idempotency hit / already-baked no-op) but
       a PRIOR run already wrote it there and the target-tree write never
       landed (e.g. the process crashed between the mission-branch write and
       this phase).

    Returns ``None`` only when none of the above yields an assigned number
    -- the pre-existing "nothing to bake this run" degrade path (no target
    write, no verification, matching ``_bake_mission_number_into_mission_
    branch``'s own documented skip conditions).
    """
    lanes_manifest = run.lanes_manifest
    target_current = _read_target_tree_mission_number(run.target_feature_dir)
    if target_current is not None:
        return target_current
    if run.assigned_mission_number is not None:
        return run.assigned_mission_number
    return _read_mission_number_from_ref(run.main_repo, lanes_manifest.mission_branch, run.mission_slug)


def _record_mission_number_on_target_tree(run: _MergeRunState) -> None:
    """Write the decided mission_number onto the TARGET-tree meta.json (#4900).

    Planning-only closeout assigns directly on the target; the lane path writes
    the number the mission-branch bake decided (or the target already carries).
    Either way ``run.assigned_mission_number`` is set, so
    :func:`_verify_and_announce_mission_number` reads it back from the committed
    target and only THEN announces it (the planning-only path never prints an
    unverified "Assigned" line).

    Lane path: the write happens UNCONDITIONALLY, after the mission->target
    squash has already run -- this guarantee never depends on squash ordering
    or on whether git invoked ``merge-driver-meta`` for this squash at all.
    ``_resolve_expected_mission_number`` picks the number (target wins over a
    stale mission-branch value). ``None`` means mission_number
    assignment was never engaged for this mission at all (not a git repo, the
    resume short-circuit with nothing recorded anywhere, or the caller mocking
    the bake out entirely, which many existing non-mission_number-focused tests
    do). A mission-branch write that failed or was skipped no longer lands here:
    the bake returns its computed number regardless, and an undeterminable
    number raises instead. The "never skip verification" concern -- a run that DID decide a number and then lost track of it on
    resume -- is closed by reading TARGET first, via an independent
    (working-tree, not ``git show``) seam.

    Raises ``MissionMetaReadError`` (corrupt target meta.json) or
    ``MissionNumberVerificationError`` (absent target meta.json); the caller
    restores the final snapshots and exits 1.
    """
    if run.planning_artifact_only:
        planning_number = _assign_planning_only_mission_number_if_needed(
            run.main_repo,
            run.feature_dir,
        )
        if planning_number is not None:
            run.assigned_mission_number = planning_number
            run.mission_number_meta_path = run.feature_dir / "meta.json"
        return
    expected_number = _resolve_expected_mission_number(run)
    if expected_number is not None:
        run.assigned_mission_number = expected_number
        run.mission_number_meta_path = _bake_mission_number_onto_target_tree(
            run.target_feature_dir,
            expected_number,
        )


def _switch_write_checkout_after_single_branch_landing(run: _MergeRunState) -> None:
    """WP08/IC-05: back to target_branch before teardown (non-coord only; see lanes.single_branch_landing)."""
    from specify_cli.lanes.single_branch_landing import switch_checkout_to_target

    if not _is_coord_topology_mission(run):
        switch_checkout_to_target(run.main_repo, run.lanes_manifest.mission_branch, run.lanes_manifest.target_branch)


def _phase_capture_and_baseline(run: _MergeRunState) -> None:
    """Refresh checkout, capture final snapshots, plan mission_number, RECORD #1827 baseline."""
    # -- WP05/T006 FR-013: Post-merge working-tree refresh --
    # WP03/T011 (#4752): pass the target branch so the refresh's own
    # defense-in-depth guard can refuse a ``reset --hard`` against an
    # off-target checkout even if the earlier preflight were ever bypassed.
    _refresh_primary_checkout_after_merge(run.main_repo, run.lanes_manifest.target_branch)

    assert run.canonical_events_path is not None
    assert run.canonical_status_path is not None
    assert run.merge_state_path is not None
    if not run.done_marked_before_target:
        run.final_bookkeeping_snapshots.update(
            _capture_merge_snapshots(
                run.main_repo,
                run.canonical_events_path,
                run.canonical_status_path,
                run.merge_state_path,
            )
        )
    target_events_path, target_status_path = _target_bookkeeping_status_paths(
        main_repo=run.main_repo,
        mission_slug=run.mission_slug,
        status_feature_dir=run.feature_dir,
    )
    target_meta_path = run.target_feature_dir / "meta.json"
    run.final_bookkeeping_snapshots.update(
        _capture_merge_snapshots(
            run.main_repo,
            target_events_path,
            target_status_path,
            target_meta_path,
        )
    )
    run.target_events_path = target_events_path
    run.target_status_path = target_status_path

    # The target-tree mission_number read/write gets the SAME
    # restore-then-``Exit(1)`` handling as the baseline record below -- a
    # corrupt target meta.json (``MissionMetaReadError``) or an absent one
    # (``MissionNumberVerificationError``, never a fabricated stub) must not
    # escape as a raw traceback with the final snapshots left un-restored.
    try:
        _record_mission_number_on_target_tree(run)
    except (BaselineMergeCommitError, MissionMetaReadError) as exc:
        _restore_and_guard_coord_coherence(run, run.final_bookkeeping_snapshots, error=exc)
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc

    # INV-5: record the #1827 baseline AFTER the target merge, BEFORE the
    # bookkeeping commit. On failure restore the final snapshots then exit.
    try:
        run.baseline_meta_path = _record_baseline_merge_commit(
            run.target_feature_dir,
            run.target_baseline_sha,
            mission_id=run.baseline_mission_id,
        )
    except BaselineMergeCommitError as exc:
        _restore_and_guard_coord_coherence(run, run.final_bookkeeping_snapshots, error=exc)
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc


@_records_post_mutation_tips
def _phase_record_done_and_project(run: _MergeRunState) -> None:
    """Mark WPs done (post-target path) and project status bookkeeping to target."""
    lanes_manifest = run.lanes_manifest
    # -- T001: Mark WPs done with per-WP state tracking --
    if not run.done_marked_before_target:
        try:
            _record_merged_wps_done_for_merge(
                main_repo=run.main_repo,
                feature_dir=run.feature_dir,
                mission_slug=run.mission_slug,
                lanes_manifest=lanes_manifest,
                target_branch=lanes_manifest.target_branch,
                merge_state=run.state,
                all_wp_ids=run.all_wp_ids,
            )
        except Exception as exc:
            # Site is inside ``if not run.done_marked_before_target:`` →
            # dead-for-coord (the guard inside the primitive no-ops the mark/heal);
            # routed for structural uniformity so no restore site can strand.
            _restore_and_guard_coord_coherence(run, run.final_bookkeeping_snapshots, error=exc)
            raise

    # WP10 integration (S-B / FR-004, #4981/#4970/#4973): thread the coordination
    # checkpoint captured at transaction start so the projection ALSO brings every
    # NON-status post-checkpoint coord commit (concurrent status-emit / acceptance
    # verdict) forward onto the target — the status union alone covers only the two
    # status files. Both kwargs default to ``None`` (WP07's byte-unchanged path)
    # unless a coord checkpoint resolved, so a non-coord/legacy mission is
    # unaffected.
    checkpoint = run.coord_checkpoint
    checkpoint_sha = checkpoint.sha if checkpoint is not None else None
    coord_ref = checkpoint.ref if checkpoint is not None else None
    try:
        target_events_path, target_status_path = _project_status_bookkeeping_to_target(
            main_repo=run.main_repo,
            mission_slug=run.mission_slug,
            status_feature_dir=run.feature_dir,
            checkpoint_sha=checkpoint_sha,
            coord_ref=coord_ref,
        )
    except Exception as exc:
        # Coord-reachable live strand: OUTSIDE the done_marked_before_target guard,
        # after the target advanced — MUST be markable (#2786-shape site 701).
        _restore_and_guard_coord_coherence(run, run.final_bookkeeping_snapshots, error=exc)
        raise
    run.target_events_path = target_events_path
    run.target_status_path = target_status_path

    _restore_regressed_gate_artifacts(run)

    _run_birth_cutover(run)

    # WP10 integration (S-B teardown gate): snapshot the coord tip AFTER every
    # merge-owned coord write of this phase (the done-recording above, the general
    # projection, and the birth-cutover status_phase seed) has landed — this is the
    # merge's LAST write to the coordination ref. :func:`_teardown_coord_worktree`
    # compare-and-swaps the ref against this value before destroying the coordination
    # triple, so a genuinely CONCURRENT status-emit / verdict that lands on the coord
    # ref AFTER this point (and was therefore never projected) is caught and teardown
    # refuses fail-closed (#4981). Capturing it here — not mid-phase — is what keeps
    # a clean merge's own cutover commit from tripping the CAS.
    if coord_ref is not None:
        run.coord_tip_after_projection = _resolve_ref_sha(run.main_repo, coord_ref)


def _run_birth_cutover(run: _MergeRunState) -> None:
    """WP09 (IC-08 / FR-009 / C-004): stamp ``status_phase`` + reconcile residual
    runtime at the merge bake stage, reusing :func:`cutover_mission` as the SOLE
    ``status_phase`` writer (no forked writer — the two-target form EXTENDS the
    spine).

    **Timing (T043 — a documented DEVIATION from the classic pre-target
    ``_bake_mission_number`` hook; see ``tracers/design-decisions.md`` IC-08 for
    the full rationale):** wired here, immediately AFTER the target merge
    (``_phase_mission_to_target`` already advanced the target ref) and AFTER
    :func:`_project_status_bookkeeping_to_target` just above — NOT at the
    pre-target bake hook (``ordering._bake_mission_number_into_mission_branch``,
    ``executor.py`` bake phase). A detached mission-branch worktree (the
    mission-number bake's own mechanism) cannot host the flip: ``_flip_phase``
    resolves its write target via ``canonicalize_feature_dir``, which follows
    ANY real worktree's ``.git`` pointer back to the canonical main-repo root
    (``resolve_canonical_root`` — confirmed by inspection) and — because
    planning artifacts (``meta.json``) already live on the target branch from
    mission-creation time — would silently redirect the flip back onto
    ``main_repo``'s STALE pre-merge ``meta.json`` instead of the intended
    mission-branch tip. Running post-target on ``run.target_feature_dir`` (the
    real, just-merged, already-refreshed PRIMARY checkout) sidesteps that hazard
    entirely and reuses the SAME resume/heal machinery already governing the
    bookkeeping commit (below) rather than inventing a parallel one.

    **Two-partition split (T044 / IC-08 risk 2):** ``run.target_feature_dir``
    (PRIMARY — real, up-to-date ``tasks/`` post-merge) is the read+flip leg;
    ``run.canonical_events_path.parent`` (the topology-aware STATUS/COORD leg,
    already resolved at merge entry via ``resolve_status_surface`` — the SAME
    port-routed authority ``_project_status_bookkeeping_to_target`` above just
    read from) is the seed+verify leg. They collapse to the same directory
    under flat/single-branch topology (T047's degenerate case). Running AFTER
    the projection call above means a genuinely-seeded event is present on the
    COORD authority but absent from the (already-fixed) PRIMARY projected copy
    — the T047 partition-surface assertion.

    **Resume-heal (T045 / IC-08 risk 3):** no new marker/transaction is
    introduced. ``cutover_mission`` is idempotent by construction (the seed
    phase skips already-seeded deterministic ids; the flip short-circuits once
    ``status_phase`` is snapshot-authority), so a crash between the COORD seed
    write and the PRIMARY flip heals by mere re-invocation on ``merge
    --resume`` — this SAME phase reruns and completes whichever leg is still
    open, with zero duplicate writes (NFR-002).

    Best-effort / non-fatal: a cutover failure must not abort an otherwise
    successful merge (the runtime-state gap remains repairable via the
    standing ``migrate backfill-runtime-state`` command) — logged, never
    raised, and skipped entirely for a mission with no code WPs to
    reconcile.

    #5100 T020 / plan fold B3: keyed on :func:`_run_has_code_wps` (a WP-kind
    question), never ``run.planning_artifact_only`` (lane-based) -- a
    single_branch mission's ONE repo-root lane reads as lane-based
    "planning-only" even when it holds real CODE WPs, which would wrongly
    skip their runtime-state reconciliation.
    """
    if not _run_has_code_wps(run):
        return

    from specify_cli.migration.runtime_state_cutover import cutover_mission

    assert run.canonical_events_path is not None
    status_feature_dir = run.canonical_events_path.parent
    try:
        result = cutover_mission(run.target_feature_dir, status_feature_dir=status_feature_dir)
    except Exception as exc:  # noqa: BLE001 — birth-cutover is best-effort, never fatal
        logger.warning("birth-cutover failed for %s: %s", run.mission_slug, exc)
        return

    run.birth_cutover_result = result
    if result.flipped:
        run.birth_cutover_meta_path = run.target_feature_dir / "meta.json"
    elif result.error:
        logger.warning("birth-cutover for %s did not reconcile: %s", run.mission_slug, result.error)

    # Commit a genuinely-seeded COORD leg (the migration-coexistence case) onto
    # the coordination branch from ITS OWN worktree. Gated on dirty-state (not
    # the per-run seeded_count) so it heals on resume, targeted at the coord ref
    # (not the primary bookkeeping seam), and best-effort — see
    # ``_commit_coord_seed_events`` (PR #2920 review F1/F2).
    if status_feature_dir != run.target_feature_dir:
        _commit_coord_seed_events(run, status_feature_dir)


def _commit_coord_seed_events(run: _MergeRunState, status_feature_dir: Path) -> None:
    """Commit birth-cutover seed events onto the coordination branch (PR #2920
    review F1/F2 — architect / debbie / paula converged on the same block).

    Closes three faults in the original inline commit:

    1. **Right partition through the seam (F1, #2884).** ``status.events.jsonl``
       is a ``STATUS_STATE`` = COORD-partition artifact. It routes through
       :func:`commit_coord_seed_bookkeeping`, which selects
       ``MissionArtifactKind.STATUS_STATE`` so the placement port resolves the
       COORD ref (the coordination branch under coordination topology) — the ref
       the coord worktree's HEAD is already on, so ``safe_commit``'s
       HEAD-must-match-destination guard is satisfied (no
       ``SafeCommitHeadMismatch``). ``run.pre_target_coord_ref`` is passed only as
       the degrade-path fallback (used solely if placement resolution fails).
       This is ONE kind-parameterized bookkeeping seam, not a duplicated
       guard-capability call site: PR #2920's earlier direct-``safe_commit``
       workaround wrongly assumed the seam could only serve the PRIMARY partition
       (it merely hardcoded ``PRIMARY_METADATA``).

    2. **Resume-heal asymmetry (F2).** The old guard ``result.seeded_count > 0``
       is a PER-RUN delta that is 0 on ``merge --resume`` — so an interrupted
       merge that seeded events to disk but died before this commit skipped it
       forever on resume, stranding them uncommitted while the sticky ``flipped``
       leg healed. We gate on the coord worktree's ACTUAL dirty state
       (``_paths_have_status_changes``) so resume completes whichever leg is open.

    3. **Fatal on failure.** The old call sat outside the best-effort ``try`` and
       could abort an otherwise-successful merge. This helper never raises —
       birth-cutover is best-effort (repairable via ``migrate
       backfill-runtime-state``).
    """
    coord_worktree_root = _coord_worktree_root(run)
    coord_ref = run.pre_target_coord_ref
    if coord_worktree_root is None or not coord_ref:
        return
    events_path = status_feature_dir / _STATUS_EVENTS_FILENAME
    try:
        if not _paths_have_status_changes(coord_worktree_root, [events_path]):
            return  # nothing seeded/uncommitted — resume-safe no-op
        # Intentionally exercised UN-mocked by tests/migration/test_birth_cutover.py
        # (the real git write) — do not add this call to a mock stack.
        commit_coord_seed_bookkeeping(
            repo_root=run.main_repo,
            worktree_root=coord_worktree_root,
            mission_slug=run.mission_slug,
            message=f"chore({run.mission_slug}): birth-cutover seed events reconciled",
            paths=(events_path,),
            branch=coord_ref,
        )
    except Exception as exc:  # noqa: BLE001 — best-effort, must never abort the merge
        logger.warning("birth-cutover coord seed commit failed for %s: %s", run.mission_slug, exc)


def _phase_porcelain_invariant(run: _MergeRunState) -> None:
    """WP05/T007 FR-014: post-merge working-tree invariant before the housekeeping commit."""
    _ret_status, _out_status = _raw_porcelain_status(run.main_repo)
    if _ret_status != 0:
        console.print(f"[yellow]Warning:[/yellow] post-merge invariant check skipped: git status --porcelain returned {_ret_status}")
        return

    expected_paths: set[str] = set()
    if run.baseline_meta_path is not None:
        expected_paths.add(str(run.baseline_meta_path.relative_to(run.main_repo)))
    if run.mission_number_meta_path is not None:
        expected_paths.add(str(run.mission_number_meta_path.relative_to(run.main_repo)))
    if run.birth_cutover_meta_path is not None:
        expected_paths.add(str(run.birth_cutover_meta_path.relative_to(run.main_repo)))
    # #2804 / FR-009: a path this run's gate-artifact preservation guard
    # rewrote is an EXPECTED post-merge delta, folded into the same final
    # bookkeeping commit below — never a violation of the post-merge invariant.
    for restored_path in run.gate_artifact_restored_paths:
        expected_paths.add(str(restored_path.relative_to(run.main_repo)))

    def _is_coord_residue(path_part: str) -> bool:
        # FR-012: consult the single canonical toolchain-churn classifier so this
        # gate agrees with every other gate on what is spec-kitty-generated churn.
        return is_toolchain_generated_churn(path_part, mission_slug=run.mission_slug)

    offending_lines, _skipped_untracked = _classify_porcelain_lines(
        (_out_status or "").splitlines(),
        expected_paths,
        residue_predicate=_is_coord_residue,
    )
    if not offending_lines:
        return

    console.print("[red]Error:[/red] Post-merge working-tree invariant violated. The following paths diverge from HEAD unexpectedly:")
    for line in offending_lines:
        console.print(f"  {line}")
    deleted_or_modified = any(len(line) >= 2 and (line[1] in ("D", "M") or line[0] in ("D", "M")) for line in offending_lines)
    if deleted_or_modified:
        console.print("\nThis may indicate a sparse-checkout or filter-driver issue. Run\n  spec-kitty doctor sparse-checkout --fix\nbefore retrying the merge.")
    else:
        console.print("\nUnexpected working-tree state after merge. Run `git status` to investigate before retrying.")
    _restore_and_guard_coord_coherence(run, run.final_bookkeeping_snapshots)
    raise typer.Exit(1)


@_records_post_mutation_tips
def _phase_commit_and_assert(run: _MergeRunState) -> None:
    """INV-5: bookkeeping safe_commit → done-on-target assert → baseline assert (post-commit)."""
    lanes_manifest = run.lanes_manifest
    assert run.target_events_path is not None
    assert run.target_status_path is not None
    # -- T012: FR-019 — Persist done events to git BEFORE any worktree removal --
    files_to_commit = [run.target_events_path, run.target_status_path]
    if run.mission_number_meta_path is not None:
        files_to_commit.append(run.mission_number_meta_path)
    if run.baseline_meta_path is not None:
        files_to_commit.append(run.baseline_meta_path)
    if run.birth_cutover_meta_path is not None:
        files_to_commit.append(run.birth_cutover_meta_path)
    # #2804 / FR-009: fold any gate-artifact path the preservation guard
    # rewrote into the SAME final bookkeeping commit, so the restored,
    # already-accepted content is the one that lands on the target branch.
    files_to_commit.extend(run.gate_artifact_restored_paths)
    files_to_commit = list(dict.fromkeys(files_to_commit))
    # Drop any candidate that genuinely does not exist on disk (e.g. a mission
    # whose ``status.json`` was never materialized): ``safe_commit`` stages
    # every requested path with ``git add --force`` and hard-fails if one is
    # missing, whereas ``_paths_have_status_changes`` (the gate just below)
    # tolerates a nonexistent path (``git status --porcelain`` reports nothing
    # for it). Before the birth-cutover phase, this list's non-optional
    # members (``target_events_path``/``target_status_path``) were the only
    # ones ever unconditionally present and a delta-free mission never
    # triggered the commit at all, so this latent existence mismatch was never
    # exercised; the birth-cutover's own genuine delta (a seed event / the
    # ``status_phase`` flip) can now be the ONLY change in an otherwise
    # status.json-less mission, surfacing it.
    # NOTE (PR #2920 review F5): this filter is write/update-only — it drops a
    # path that is absent on disk (a never-materialized status.json). It is NOT
    # deletion-safe: were a future bookkeeping step to need a path REMOVED, the
    # filter would silently skip the deletion instead of committing it. None of
    # the current members are ever deleted during merge, so this is inert today.
    files_to_commit = [path for path in files_to_commit if path.exists()]

    has_bookkeeping_changes = _paths_have_status_changes(run.main_repo, files_to_commit)
    if has_bookkeeping_changes:
        try:
            commit_merge_bookkeeping(
                repo_root=run.main_repo,
                worktree_root=run.main_repo,
                mission_slug=run.mission_slug,
                # WP03/FR-003: ``branch`` is now a degrade-path ONLY — the
                # destination is derived through the placement port from
                # ``mission_slug``; this value is used solely if that
                # resolution fails.
                branch=lanes_manifest.target_branch,
                # terminus-merge-integrity C-1 (#4985/#4991): thread the RESOLVED
                # merge target (WP09's single persisted authority — explicit
                # ``--target`` > ``ConsolidationState.target_branch`` > meta — already
                # baked into ``lanes_manifest.target_branch``) as the housekeeping
                # commit's destination. The placement port would otherwise resolve
                # PRIMARY_METADATA from the mission's STALE meta ``target_branch``,
                # raising ``SafeCommitHeadMismatch`` on a non-default-target merge
                # (HEAD on the resolved target, meta expects the old one) and
                # aborting before the work durably lands. For a default-target
                # merge this equals the meta target — byte-identical behavior.
                destination_ref_override=lanes_manifest.target_branch,
                message=f"chore({run.mission_slug}): record done transitions for merged WPs",
                paths=tuple(files_to_commit),
            )
        except Exception as exc:
            if not (isinstance(exc, SafeCommitRecoveryFailed) and exc.commit_sha is not None):
                _restore_and_guard_coord_coherence(run, run.final_bookkeeping_snapshots, error=exc)
            raise
    else:
        console.print("  [dim]No post-merge bookkeeping changes to commit; continuing cleanup.[/dim]")

    _assert_merged_wps_done_on_target(
        run.main_repo,
        run.mission_slug,
        lanes_manifest.target_branch,
        run.all_wp_ids,
        feature_dir=run.feature_dir,
        mission_id=run.baseline_mission_id,
    )

    # -- Post-merge baseline invariant (assert AFTER the commit landed) --
    try:
        _assert_baseline_merge_commit_on_target(
            run.main_repo,
            run.mission_slug,
            lanes_manifest.target_branch,
            run.target_baseline_sha,
            feature_dir=run.target_feature_dir,
            mission_id=run.baseline_mission_id,
        )
    except BaselineMergeCommitError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc

    _verify_and_announce_mission_number(run, lanes_manifest)


def _verify_and_announce_mission_number(run: _MergeRunState, lanes_manifest: LanesManifest) -> None:
    """#4900: verify the target-tree write, mark baked, THEN announce.

    Runs immediately after the baseline invariant, using the SAME error
    handling (``BaselineMergeCommitError`` -> ``Error:`` line ->
    ``typer.Exit(1)``) -- :class:`~specify_cli.consolidation.baseline.
    MissionNumberVerificationError` is a sibling subclass. When
    ``run.assigned_mission_number`` is ``None`` (no number was ever decided
    for this run -- e.g. an unsafe mission_slug refused assignment
    upstream), there is nothing to verify or announce, matching the
    pre-existing degrade-with-warning behavior on that path.

    ``mission_number_baked`` is marked HERE, and only here -- never inside
    ``ordering``'s bake/write seams, which run BEFORE the target-tree write
    even exists. Setting it earlier is unsafe: it let a ``--resume`` short-circuit past this
    verification and exit 0 with a wrong or null number on the target.
    """
    if run.assigned_mission_number is None:
        return
    try:
        _assert_mission_number_on_target(
            run.main_repo,
            lanes_manifest.target_branch,
            run.mission_slug,
            run.assigned_mission_number,
        )
    except BaselineMergeCommitError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc

    _mark_mission_number_baked(run.state, run.main_repo)

    console.print(f"[green]Assigned[/green] mission_number={run.assigned_mission_number} to mission {run.mission_slug}")
    logger.info(
        "Assigned mission_number=%d to mission %s (verified on %s)",
        run.assigned_mission_number,
        run.mission_slug,
        lanes_manifest.target_branch,
    )


def _resolve_pre_mutation_target_sha(main_repo: Path, target_branch: str, state: ConsolidationState) -> str | None:
    """Resolve the TRANSACTION-START target tip, persisting it at first capture.

    #5001 pre-merge FOLD-4. The excluded/closed-world reconciliation window base
    (and the rollback CAS anchor) MUST be the genuine pre-mutation target tip, not
    the current tip. On a fresh merge that is the live ``rev-parse`` here — before
    any lane/mission→target advance — and it is persisted into ``ConsolidationState`` so a
    later ``--resume`` (which runs AFTER attempt-1 already advanced the target)
    re-reads the ORIGINAL tip instead of recapturing the already-advanced one.
    Without this, the resume window collapses to empty and the excluded/closed-
    world axes false-PASS, and the rollback would anchor to the stale advanced tip
    (Debbie [MEDIUM] resume false-PASS). ``None`` when the target ref cannot be
    resolved (nothing is persisted — a subsequent resume re-attempts the read).
    """
    persisted = state.pre_mutation_target_sha
    if persisted:
        return persisted
    ret, target_sha, _err = run_command(
        ["git", "rev-parse", target_branch],
        capture=True,
        check_return=False,
        cwd=main_repo,
    )
    resolved = target_sha.strip() if ret == 0 and target_sha.strip() else None
    if resolved is not None:
        state.pre_mutation_target_sha = resolved
        save_state(state, main_repo)
    return resolved


def _persist_executed_strategy(
    state: ConsolidationState,
    strategy: MergeStrategy,
    *,
    is_resume: bool,
    main_repo: Path,
) -> None:
    """Persist the strategy attempt-1 ACTUALLY executes into ``ConsolidationState`` (FR-003).

    terminus-integrity-followups WP05 (T020, F14; #4982/#4985/#4991). A fresh state
    is created with the inert ``ConsolidationState.strategy`` dataclass default (``"merge"``)
    regardless of the operator's choice, so a ``--resume`` that reads it back would
    silently upgrade a squash operator to merge. The CLI resolves the effective
    strategy (explicit ``--strategy`` > persisted > config > SQUASH; an explicit flip
    on resume is refused — WP04) and hands the executor the resolved enum; this stamps
    that resolved value so the persisted record is truthful. Mirrors the C-1 target
    reseed neighbourhood. **Fresh-only:** a resume's persisted value already IS the
    executed strategy (WP04's CLI precedence sourced it), so re-stamping would be a
    no-op that could only ever overwrite the authority with a re-derived proxy — the
    persisted authority is never touched on resume (same rule as ``skip_lanes``)."""
    if is_resume:
        return
    state.strategy = strategy.value
    save_state(state, main_repo)


def _capture_pre_interrupt_lane_tips(run: _MergeRunState) -> dict[str, str]:
    """Resolve each lane BRANCH's current tip SHA at pre-mutation capture (FR-004).

    terminus-integrity-followups WP05 (T021, b2); re-keyed by
    lane-branch-naming-authority-01M3EVC4 WP02 (T031). Keyed by the lane's
    CREATED branch (:func:`_created_lane_branch` — never a Mission identity),
    so a resume CAS-checks the SAME ref via :func:`lane_tip_cas_ok`
    (``refs/heads/<key>``). The canonical ``lane-planning`` lane resolves to
    the target branch (not a ``kitty/mission-…`` branch) and is skipped — its
    "tip" is the moving target ref, never a pre-interrupt identity to
    preserve. A fully-canceled lane (FR-009, every WP an acceptable canceled
    ending) is also skipped — its branch may never have been created. A
    branch that does not resolve for any other reason contributes no entry
    (tolerant, like the claim builder). Captured ONCE before
    ``_phase_merge_lanes`` mutates anything."""
    tips: dict[str, str] = {}
    for lane in run.lanes_manifest.lanes:
        if lane.lane_id == "lane-planning":
            continue
        if _lane_fully_canceled(lane, run.excluded_canceled_wp_ids):
            continue
        branch = _created_lane_branch(run.lanes_manifest, lane.lane_id)
        ret, sha, _err = run_command(
            ["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}^{{commit}}"],
            capture=True,
            check_return=False,
            cwd=run.main_repo,
        )
        resolved = sha.strip() if ret == 0 and sha.strip() else None
        if resolved is not None:
            tips[branch] = resolved
    return tips


def _resolve_pre_mutation_coord_sha(state: ConsolidationState, run: _MergeRunState) -> str | None:
    """Resolve the TRANSACTION-START coord tip, persisting it (+ lane tips) once.

    terminus-integrity-followups WP05 (T021, FR-004; F3/F9). The coord-window twin of
    :func:`_resolve_pre_mutation_target_sha` — read-persisted-first, byte-for-byte
    shape: if a value is already persisted, return it (a ``--resume`` MUST anchor the
    reconciliation claim to the TRUE pre-mutation base, never the live checkpoint,
    which already contains attempt-1's partial consolidation and would collapse the
    approved-WP claim to empty — the #4982 vacuous-claim false PASS). Otherwise capture
    the coord checkpoint ONCE (a fresh merge, before any mutation), persist it together
    with the per-lane pre-interrupt tips, and return it. ``None`` when the coord tip
    cannot be resolved (a non-coord / legacy mission — nothing is persisted, and the
    claim falls back to the mission-branch ref). NEVER overwrites a persisted value on
    a later resume (re-poison)."""
    persisted: str | None = state.pre_mutation_coord_sha
    if persisted:
        return persisted
    checkpoint = _capture_coord_checkpoint(run)
    if checkpoint is None:
        return None
    state.pre_mutation_coord_sha = checkpoint.sha
    state.pre_mutation_coord_ref = checkpoint.ref
    if not state.pre_interrupt_lane_tips:
        state.pre_interrupt_lane_tips = _capture_pre_interrupt_lane_tips(run)
    save_state(state, run.main_repo)
    return checkpoint.sha


def _unanchored_lane_branches(run: _MergeRunState) -> list[str]:
    """The CREATED branches of every lane the H5 resume guard requires an
    anchor for, but that ``run.state.pre_interrupt_lane_tips`` has no key for.

    lane-branch-naming-authority-01M3EVC4 WP02 (T032). Mirrors EXACTLY the
    lanes :func:`_capture_pre_interrupt_lane_tips` captures keys for (never
    the canonical ``lane-planning`` lane, never a fully-canceled lane), so a
    lane this function flags as missing is always a lane the capture step was
    supposed to key — an empty, partial, or old-form (identity-keyed) record
    is caught here, never a lane that was legitimately never captured.
    Returned sorted for a deterministic message."""
    from specify_cli.lanes.compute import is_planning_lane

    missing: list[str] = []
    for lane in run.lanes_manifest.lanes:
        if is_planning_lane(lane) or _lane_fully_canceled(lane, run.excluded_canceled_wp_ids):
            continue
        branch = _created_lane_branch(run.lanes_manifest, lane.lane_id)
        if branch not in run.state.pre_interrupt_lane_tips:
            missing.append(branch)
    return sorted(missing)


def _refuse_unanchored_resume(run: _MergeRunState, *, coord_topology: bool) -> None:
    """H5 (lane-branch-naming-authority-01M3EVC4 WP02, FR-005): refuse a resume
    whose persisted ``pre_interrupt_lane_tips`` record has no key for one of
    :func:`_unanchored_lane_branches`' CREATED branches — an empty record, a
    partial one (some lanes missing), or an old-form record keyed by an
    identity-form branch name a post-fix capture never produces. Scoped to
    ``coord_topology and state.pre_mutation_coord_sha`` (the same precondition
    the tips are captured/persisted under, H4); a canceled-only or
    planning-only manifest is exempt because the helper already excludes
    those lanes. Extracted from :func:`_enforce_resume_anchor_integrity` so
    that function stays within its complexity ceiling (DoD: current + 1)."""
    if not (coord_topology and run.state.pre_mutation_coord_sha):
        return
    missing = _unanchored_lane_branches(run)
    if not missing:
        return
    console.print(
        "\n[red]Error:[/red] cannot resume this merge: the persisted "
        "pre-interrupt lane-tip record has no anchor for lane "
        "branch(es) " + ", ".join(repr(b) for b in missing) + " (the record is empty, partial, or was written by an "
        "older release under a different name). Resuming without "
        "an anchor would disarm the resume guard. " + _CONSOLIDATE_ABORT_AND_RESTART_HINT
    )
    raise typer.Exit(1)


def _enforce_resume_anchor_integrity(run: _MergeRunState, *, coord_topology: bool) -> None:
    """Fail-closed resume guard for the persisted coord/lane-tip anchors (FR-004/005).

    terminus-integrity-followups WP05 (T022, H3/H4); lane-branch-naming-authority-
    01M3EVC4 WP02 (T032, H5). Runs only on a ``--resume``; a fresh merge has
    nothing persisted yet (the anchors are captured moments later). Order matches
    the T032 spec (after H4, before the H3 CAS loop): an old-form (identity-keyed)
    record then gets H5's message, never a misleading H3 "diverged" one.

    * **H4** — a coord-topology resume *that requires the persisted base* REFUSEs on
      its absence rather than silently collapsing to the live (already-advanced)
      checkpoint (the exact vacuous-claim false PASS this mission closes). "Requires
      it" == attempt-1 durably consolidated at least one lane (``completed_wps``
      non-empty), so the live checkpoint is poisoned by that consolidation and the
      claim MUST anchor to the persisted pre-mutation base. When attempt-1 recorded no
      consolidation, the live checkpoint is still the pristine pre-mutation tip, so the
      resolver may safely capture+persist it — refusing there would break a merge that
      was interrupted before any mutation (regression). In post-fix code the base is
      ALWAYS persisted before any consolidation (persist-before-mutate, see
      :func:`_resolve_pre_mutation_coord_sha` called from :func:`_capture_reconciliation_claim`
      before :func:`_phase_merge_lanes`), so a consolidated-but-baseless state is an
      inconsistency (corruption / pre-fix residue) and refusing it is correct.
    * **H5** — see :func:`_refuse_unanchored_resume`.
    * **H3** — each persisted pre-interrupt lane tip must satisfy the CAS expectation
      (:func:`lane_tip_cas_ok`: equal / descendant / behind-HEAD ancestor OK; true
      divergence REFUSEs), so a legitimately-advanced lane is never silently dropped
      and a superseded tip is never resurrected. The behind-HEAD #4982 window is
      explicitly NOT a refusal."""
    if not run.is_resume:
        return
    state = run.state
    manifest_lists_wps = any(lane.wp_ids for lane in run.lanes_manifest.lanes)
    attempt_one_consolidated = bool(state.completed_wps)
    if coord_topology and manifest_lists_wps and attempt_one_consolidated and not state.pre_mutation_coord_sha:
        console.print(
            "\n[red]Error:[/red] cannot resume this merge: a prior attempt already "
            "consolidated work but the pre-mutation coordination base was not "
            "persisted, so the reconciliation claim cannot be anchored to the true "
            "pre-interrupt tip. " + _CONSOLIDATE_ABORT_AND_RESTART_HINT
        )
        raise typer.Exit(1)
    _refuse_unanchored_resume(run, coord_topology=coord_topology)
    for branch, persisted_sha in state.pre_interrupt_lane_tips.items():
        if not lane_tip_cas_ok(run.main_repo, branch, persisted_sha):
            console.print(
                "\n[red]Error:[/red] cannot resume this merge: lane branch "
                f"{branch!r} diverged from its persisted pre-interrupt tip "
                f"{persisted_sha[:10]} (neither equal, ancestor, nor descendant). "
                "Resuming would drop or resurrect work. " + _CONSOLIDATE_ABORT_AND_RESTART_HINT
            )
            raise typer.Exit(1)


@contextlib.contextmanager
def _clear_fresh_record_on_pre_mutation_exit(run: _MergeRunState) -> Iterator[None]:
    """Clear a FRESH run's own transaction record if a pre-mutation phase exits.

    #5111 (and the #4764 landing-pass remediation it generalises): a fresh run
    persisted its transaction record (``state.json`` + reconciliation marker) in
    ``_load_or_create_merge_state`` before the gate/checkpoint/claim phases this
    wraps, and none of them mutates a ref, worktree, or status log. So when ANY
    of them exits -- a failed merge gate, the canonical-history guard, a
    declined hollow-review prompt or Ctrl-C, a fail-closed claim refusal, or an
    unexpected exception -- the mission is unchanged, and the fresh run's own
    record is cleared: the operator's next plain ``spec-kitty consolidate`` is
    then a genuinely fresh run that re-resolves target/strategy/push from its
    own flags, instead of an auto-resume of a zero-progress state. A
    pre-existing ``--resume``'s record is never destroyed here. A hard kill
    cannot run this handler; the marker-with-state ordering keeps that residue
    resumable (not "pre-fix").
    """
    try:
        yield
    except BaseException:
        if not run.is_resume:
            try:
                clear_state(run.main_repo, run.canonical_id)
            except OSError as clear_error:
                # Never let a failed cleanup replace the real exit (a gate
                # failure's typer.Exit, a Ctrl-C) as the operator's headline.
                # A half-cleared record is at worst an orphan marker, which the
                # next fresh run re-stamps.
                logger.warning("Could not clear the fresh consolidation record for %s: %s", run.canonical_id, clear_error)
                console.print(f"[yellow]Warning:[/yellow] could not clear this run's consolidation record ({clear_error}); a plain re-run still starts fresh.")
        raise


def _capture_reconciliation_claim(run: _MergeRunState) -> None:
    """Capture the fail-closed, Lamport-sourced claim ONCE at transaction start.

    terminus-merge-integrity WP06 (T027/T029). Runs BEFORE any mutating phase so
    the teardown gate (:func:`_phase_reconcile_before_teardown`) compares the
    post-merge target against a claim sourced from the PRE-mutation lane tips.
    Also enforces FR-012: a resumed pre-fix in-flight state (no post-fix marker)
    is refused here — before any mutation — rather than proceeding under the new
    gate against unknown-shape state. A fresh merge's marker was already written
    with its ``state.json`` (#5111); the write below is an idempotent re-stamp.
    """
    legacy = detect_legacy_in_flight_state(run.main_repo, run.canonical_id, is_resume=run.is_resume)
    if legacy is not None:
        console.print(f"[red]Error:[/red] {legacy}")
        raise typer.Exit(1)
    write_post_fix_marker(run.main_repo, run.canonical_id)

    checkpoint = _capture_coord_checkpoint(run)
    run.coord_checkpoint = checkpoint

    # terminus-integrity-followups WP05 (T021/T022, FR-004/005; F3/F9/H3/H4): the
    # reconciliation CLAIM's coord base MUST be the PERSISTED pre-mutation coord tip,
    # not the live checkpoint (which on a resume already contains attempt-1's partial
    # consolidation and would collapse the approved-WP claim to empty — the #4982
    # vacuous-claim false PASS). ``run.coord_checkpoint`` above stays the LIVE tip: it
    # anchors the projection + teardown CAS (a separate, unchanged concern). Validate
    # the persisted anchors fail-closed on resume BEFORE resolving the base, so an
    # absent base (H4) or a truly-divergent lane tip (H3) refuses rather than the
    # resolver falling back to a live capture.
    _enforce_resume_anchor_integrity(run, coord_topology=checkpoint is not None)
    coord_base_sha = _resolve_pre_mutation_coord_sha(run.state, run)
    coord_base = coord_base_sha if coord_base_sha is not None else (checkpoint.sha if checkpoint is not None else run.lanes_manifest.mission_branch)

    run.target_expected_old_sha = _resolve_pre_mutation_target_sha(run.main_repo, run.lanes_manifest.target_branch, run.state)

    try:
        run.approved_wp_set = build_approved_wp_set(
            run.main_repo,
            run.feature_dir,
            run.lanes_manifest,
            coord_base_ref=coord_base,
            excluded_canceled_wp_ids=run.excluded_canceled_wp_ids,
            excluded_window_base=run.target_expected_old_sha,
        )
    except GitProbeError as exc:
        _exit_on_claim_probe_error(exc)

    # #5338: act on a claim-integrity refusal HERE, before the first mutating
    # phase, instead of storing it for the post-mutation gate. A resume whose
    # reconciliation already PASSed for the current target tip (#5021) is exempt:
    # its lane branches may legitimately be gone already.
    refusal = claim_integrity_refusal(run.approved_wp_set)
    if refusal is not None and not _resume_reconciliation_already_passed(run):
        _exit_on_claim_integrity_refusal(refusal, attested=run.recorded_attestations)

    # #5318 / #5332: snapshot every branch this attempt may move, strictly before
    # the first mutating phase, and fix this attempt's restore targets.
    _capture_snapshot_and_begin_attempt(run)


def _capture_snapshot_and_begin_attempt(run: _MergeRunState) -> None:
    """Capture the pre-mutation snapshot ONCE and begin this attempt (T013).

    A resume reuses the persisted snapshot (the authority never recaptures);
    every attempt, fresh or resumed, computes its own per-branch restore targets
    and resets its post-mutation tips. A candidate branch that does not resolve is
    not snapshotted -- warn so the operator knows a rollback will not cover it.
    """
    coord_ref = run.coord_checkpoint.ref if run.coord_checkpoint is not None else None
    rollback.capture_pre_mutation_snapshot(run.main_repo, run.state, run.lanes_manifest, coord_ref=coord_ref, is_resume=run.is_resume)
    for branch in rollback.missing_snapshot_branches(run.main_repo, run.lanes_manifest, coord_ref=coord_ref):
        console.print(f"[yellow]Warning:[/yellow] branch {branch!r} does not exist and is not snapshotted; a rollback will not cover it.")
    rollback.begin_attempt(run.main_repo, run.state)


def _claim_refusal_change_sentence(attested: tuple[str, ...]) -> str:
    """What this run changed before a claim-time refusal: nothing, or only the operator attestations (F4)."""
    if not attested:
        return "No branch, worktree or status record was changed by this run."
    return f"No branch or worktree was changed by this run; only the operator attestation(s) for {', '.join(attested)} were recorded."


def _exit_on_claim_integrity_refusal(refusal: str, *, attested: tuple[str, ...] = ()) -> NoReturn:
    """Abort before any mutation because the approved-WP claim failed integrity (#5338).

    Runs strictly pre-mutation (inside ``_clear_fresh_record_on_pre_mutation_exit``),
    so no branch or worktree was changed by this run. ``--attest-canceled-superseded``
    writes its status events BEFORE the claim (FR-012); when this run recorded any
    (``attested``), the text says so instead of claiming no status record changed.
    The verdict leads with the same ``Reconciliation refused (fail-closed)``
    header the teardown gate prints (#5359), so operators and tooling see one
    REFUSE vocabulary whether the claim refuses early or the gate refuses late.
    """
    console.print(
        f"\n[red]Error:[/red] Reconciliation refused (fail-closed) at claim time, before any change: {refusal.rstrip('.')}. "
        f"{_claim_refusal_change_sentence(attested)} Fix the cause, then re-run; "
        f"if an earlier attempt left partial state, run `{_CONSOLIDATE_ABORT_COMMAND}` first."
    )
    raise typer.Exit(1)


def _exit_on_claim_probe_error(exc: GitProbeError) -> NoReturn:
    """Abort clean when a git probe errored while building the claim.

    #5001: a git probe (patch_id_of/changed_paths_of) errored while deriving the
    claim's excluded/authored SHA sets. This runs strictly pre-mutation — nothing
    has landed yet — so abort clean (fail-closed) rather than let the uncaught
    GitProbeError surface as a raw traceback. Mirrors how the teardown gate's own
    GitProbeError→VerifyResult.refused(...) REFUSE is reported to the operator.
    """
    console.print(
        f"\n[red]Error:[/red] Reconciliation refused (fail-closed): a git "
        f"probe failed while building the approved-WP claim: {exc}. "
        f"{_NOTHING_TORN_DOWN} and no refs/worktrees were mutated. Resolve the "
        "underlying git issue, then re-run the merge."
    )
    raise typer.Exit(1) from exc


def _reconciliation_claim_for_gate(run: _MergeRunState) -> ApprovedWpCommitSet:
    """Return the strategy-appropriate claim for the teardown gate.

    Content reachability (approved-SHA ancestry + excluded SHA/patch-id) is only
    SOUND for ancestry-preserving strategies (merge/rebase). A squash merge
    preserves neither lane-tip SHAs nor per-lane patch-ids, and the post-merge
    target additionally carries legitimate bookkeeping commits (mission_number
    bake, done-transition record) that make even an aggregate mission→target tree
    comparison diverge (verified: :func:`lane_integrated_by_tree_or_ancestry`
    returns False on a genuine squash merge because of that bookkeeping). Proving
    approved content landed under squash therefore requires the projection seam
    WP07/WP08 own. For squash we hand the verifier a claim with
    ``verify_reachability=False`` so it still runs the squash-sound blob-attribution
    content axis (#5013) plus fail-closed claim integrity (surface + refusal),
    deferring only the per-SHA approved-reachability check — never false-failing a
    legitimate squash merge (NFR-004). The ``replace`` preserves ``enforce_closed_world``
    and ``authored_blobs`` so the content axis is reachable. Merge/rebase use the
    captured per-SHA claim verbatim (the Tier-0 clean-merge strategy).
    """
    captured = run.approved_wp_set
    if captured is None:
        # Defensive: the claim should have been captured at transaction start.
        # Rebuild fail-closed rather than pass vacuously.
        captured = build_approved_wp_set(
            run.main_repo,
            run.feature_dir,
            run.lanes_manifest,
            coord_base_ref=run.lanes_manifest.mission_branch,
            excluded_canceled_wp_ids=run.excluded_canceled_wp_ids,
            excluded_window_base=run.target_expected_old_sha,
        )
    if run.strategy is MergeStrategy.SQUASH:
        return replace(captured, verify_reachability=False)
    return captured


def _resume_reconciliation_already_passed(run: _MergeRunState) -> bool:
    """Detect a completed-but-mid-teardown resume (#5021 residual 1 / Decision 3).

    ``--resume`` re-runs the WHOLE phase list, including
    :func:`_capture_reconciliation_claim`, which rebuilds ``authored_blobs`` from
    each approved lane's first-parent spine. If a crash landed mid-teardown
    AFTER a lane branch was already deleted (:func:`_phase_cleanup_worktrees_
    and_branches` deletes lane branches before tearing down coordination), that
    rebuild's ``_lane_first_parent_spine`` tolerates the now-unresolvable range
    into an EMPTY spine, and the squash blob axis then REFUSEs an empty
    authored set against resolved approved WPs — false-FAILing a merge that
    already PASSed and already landed.

    The signal must be an EXACT, durable proof that THIS target state already
    PASSed — never a fuzzy "looks advanced" heuristic (a crash BETWEEN
    ``_phase_mission_to_target`` and ``_phase_reconcile_before_teardown`` would
    leave the target advanced but genuinely UNVERIFIED — the R2 guard).
    ``_phase_reconcile_before_teardown`` persists ``state.reconciliation_passed_
    target_sha`` = the target branch's tip SHA the INSTANT it records a PASS
    (:func:`_record_reconciliation_pass`); resuming only short-circuits when
    that persisted SHA still equals the target's CURRENT tip (a compare-and-
    swap) — anything that moved the target since (a rollback, a further
    mutation) falls through to the full gate, so a genuinely-incomplete or
    genuinely-divergent merge is never silently tolerated.
    """
    if not run.is_resume:
        return False
    return bool(reconciliation_passed_for_tip(run.state, _resolve_ref_sha(run.main_repo, run.lanes_manifest.target_branch)))


def _record_reconciliation_pass(run: _MergeRunState) -> None:
    """Persist the CAS anchor proving reconciliation PASSed for the target's tip.

    Enables :func:`_resume_reconciliation_already_passed` to recognize a
    completed-but-mid-teardown resume without re-running the content axis
    against a possibly torn-down lane's now-partial ``authored_blobs`` claim
    (#5021 r1). A no-op when the target ref cannot be resolved (nothing safe to
    anchor).
    """
    target_sha = _resolve_ref_sha(run.main_repo, run.lanes_manifest.target_branch)
    if not target_sha:
        return
    run.state.reconciliation_passed_target_sha = target_sha
    save_state(run.state, run.main_repo)


def _phase_reconcile_before_teardown(run: _MergeRunState) -> None:
    """S-D gate: verify the merge outcome by tree reachability BEFORE any teardown.

    terminus-merge-integrity WP06 (FR-001/FR-002; NFR-005). Runs strictly between
    ``_phase_commit_and_assert`` and cleanup. On FAIL/REFUSE it refuses (non-zero
    exit) with recovery guidance, tears down NOTHING, and restores the target ref to
    its pre-mutation tip with a compare-and-swap (FR-010); on PASS it continues to
    cleanup. The success message is scoped to
    **approved-WP commit reachability** (NOT verdict integrity — #4941 out of
    scope, FR-013; #4990 closed the rejection-after-approval case).
    """
    # NFR-005: this executor path is the ``merge`` terminus entry point; routing
    # it through the allowlist proves the gate is reached (a 7th, unrouted path
    # would raise here). ``merge --resume`` reuses the same executor flow.
    route_terminus("consolidate --resume" if run.is_resume else "consolidate")
    if _resume_reconciliation_already_passed(run):
        # #5021 r1: this exact target state already PASSed reconciliation in a
        # prior attempt (persisted CAS proof) — do not re-run the content axis
        # against a possibly torn-down lane's now-partial claim. Still runs the
        # squash projection proof below (a separate, unaffected axis).
        run.reconciliation_result = VerifyResult.passed()
        _assert_squash_projected_content_landed(run)
        console.print(_reconciliation_pass_message(run.strategy))
        return
    claim = _reconciliation_claim_for_gate(run)
    result = MergeOutcomeVerifier(run.main_repo).verify(run.lanes_manifest.target_branch, claim)
    run.reconciliation_result = result
    if result.is_pass:
        _record_reconciliation_pass(run)
        _assert_squash_projected_content_landed(run)
        console.print(_reconciliation_pass_message(run.strategy))
        return
    console.print(f"\n[red]Error:[/red] {result.recovery_guidance()}")
    # terminus-merge-integrity (S-D) / FR-010 (mixed-lane-authorship-soundness
    # operator decision 01M3MAB8FTDKKVVTXPREK75AEP, "Rollback on REFUSE only"):
    # the mission→target advance already landed before this gate (it is homed
    # post-``_phase_commit_and_assert``), so EVERY non-PASS verdict leaves the
    # target sitting on a state this gate did not just prove sound. A FAIL is a
    # proven tree divergence — a removed/canceled commit rode a carrier lane onto
    # the target, or approved work is missing. A REFUSE is a fail-closed claim
    # that could not even be evaluated — the target is equally unverified, not
    # "known good", so there is exactly as much to revert. Roll the target ref
    # back to its PRE-mutation tip (captured at transaction start) on both so the
    # epic invariant holds: after a non-zero exit, the target is at its
    # pre-mutation tip. NO teardown runs (branches/worktrees are retained for
    # inspection — the ordering guarantee), and the revert is a CAS restore that
    # fails safe if the ref moved since (warns, never overwrites a newer tip).
    if result.status in (VerifyStatus.FAIL, VerifyStatus.REFUSE):
        _rollback_target_after_failed_reconciliation(run)
    raise typer.Exit(1)


def _reconciliation_pass_message(strategy: MergeStrategy) -> str:
    """Operator-facing reconciliation PASS line, honest per strategy.

    #5001 pre-merge FOLD-2 + #5013. Under SQUASH the gate verifies approved-WP claim
    integrity AND the squash-sound blob-attribution content axis (#5013 — no
    un-attributable content on the target); only the per-SHA approved-reachability
    check (structurally unsatisfiable once squash mints new SHAs) is deferred. The
    message must NOT claim "no excluded commit reachable" (a per-SHA phrasing never
    computed under squash — the pre-fix line did, fabricating success), but it no
    longer under-claims: content attribution WAS verified. Merge/rebase ran the full
    per-SHA reachability + excluded/closed-world checks and keep the full-
    verification line.
    """
    if strategy is MergeStrategy.SQUASH:
        return (
            "  [green]✓[/green] Reconciliation verified: approved-WP claim "
            "integrity and squash content attribution verified (no un-attributable "
            "content on the target); per-SHA approved-reachability deferred under "
            "squash strategy."
        )
    return "  [green]✓[/green] Reconciliation verified: approved-WP commit reachability on the target (no excluded commit reachable)."


def _rollback_target_after_failed_reconciliation(run: _MergeRunState) -> None:
    """Revert the target ref to its pre-mutation tip after a non-PASS reconciliation
    verdict (FAIL or REFUSE — FR-010, "Rollback on REFUSE only").

    Restores ``target_branch`` to ``run.target_expected_old_sha`` (the tip read at
    transaction start, before any lane/mission→target advance) with a
    compare-and-swap, then refreshes the primary checkout so its working tree
    matches the reverted ref. The name is kept (not ``..._failed_or_refused_...``)
    because tests import it directly by this name (e.g.
    ``test_merge_state_authority.py::TestRollbackTargetAfterFailedReconciliation``
    and ``test_refuse_restores_target.py``) — the helper itself never
    distinguished FAIL from REFUSE; only its caller's gating condition did. Best-effort and non-fatal:
    the command is already exiting non-zero with recovery guidance; a rollback
    hiccup is warned, never masked. No-op when the pre-mutation tip is unknown
    (nothing safe to restore).
    """
    pre_merge_sha = run.target_expected_old_sha
    if not pre_merge_sha:
        return
    target_branch = run.lanes_manifest.target_branch
    current_sha = _resolve_ref_sha(run.main_repo, target_branch)
    # ``_resolve_ref_sha`` returns "" (never ``None``) for an unresolvable ref, so
    # the guard tests falsiness (#5001 pre-merge FOLD-5: the pre-fix ``is None``
    # arm was dead code — "" fell through to a restore with expected_current_sha=""
    # that git rejects). An empty/unresolvable current tip, or one already at the
    # pre-merge tip, means there is nothing safe to undo.
    if not current_sha or current_sha == pre_merge_sha:
        return
    try:
        restore_branch_ref(
            run.main_repo,
            target_branch,
            pre_merge_sha,
            expected_current_sha=current_sha,
        )
    except RefRestoreError as exc:
        console.print(
            f"[yellow]Warning:[/yellow] could not revert {target_branch!r} to its "
            f"pre-merge tip after the reconciliation FAIL/REFUSE: {exc}. Inspect the "
            "target branch by hand before retrying."
        )
        return
    _refresh_primary_checkout_after_merge(run.main_repo, target_branch)


def _assert_squash_projected_content_landed(run: _MergeRunState) -> None:
    """SQUASH content proof (WP10 integration / S-D + WP07 handoff).

    The reconciliation claim for a SQUASH merge runs with
    ``verify_reachability=False`` (a squash preserves neither lane-tip SHAs nor
    per-lane patch-ids, so SHA/patch-id reachability is unsound — see
    :func:`_reconciliation_claim_for_gate`). This restores content verification
    for squash — WITHOUT the unsound SHA reachability — by asserting, over the
    set of bookkeeping paths the projection brought forward, that each one
    legitimately landed on the target: byte-equality with the coordination ref
    when the target never diverged from the shared checkpoint baseline for that
    path, or driver-replay attribution against the target's PRE-squash tip
    (``run.target_expected_old_sha``) when it did (#5038 —
    :func:`projected_content_matches_target`). A legitimate squash merge already
    copied that content forward (or a registered driver losslessly reconciled a
    genuine divergence), so this PASSES (NFR-004: never false-fail a genuine
    squash); it refuses fail-closed only if a projected path's content did not
    actually land as either the coord ref's bytes OR the driver's own replayed
    output — the divergence a bare ``verify_reachability=False`` would have
    missed. A no-op for merge/rebase (SHA reachability already covered them) and
    for a non-coord/legacy mission (no checkpoint window to project)."""
    if run.strategy is not MergeStrategy.SQUASH:
        return
    checkpoint = run.coord_checkpoint
    if checkpoint is None:
        return
    projected_paths = tuple(_post_checkpoint_mission_paths(run.main_repo, run.mission_slug, checkpoint.sha, checkpoint.ref))
    if not projected_paths:
        return
    pre_squash_target_ref = run.target_expected_old_sha
    if pre_squash_target_ref is None:
        # Fail-closed (never tautologically diff the POST-squash target against
        # itself): without the genuine pre-mutation tip, a diverged path's
        # driver-replay attribution cannot be evaluated soundly.
        console.print(
            "\n[red]Error:[/red] SQUASH reconciliation refused: the pre-merge "
            "target baseline could not be resolved, so the projected "
            "coordination bookkeeping content proof cannot be evaluated. "
            f"{_NOTHING_TORN_DOWN}; re-run `spec-kitty consolidate --resume`."
        )
        raise typer.Exit(1)
    if projected_content_matches_target(
        main_repo=run.main_repo,
        coord_ref=checkpoint.ref,
        target_ref=run.lanes_manifest.target_branch,
        projected_paths=projected_paths,
        checkpoint_sha=checkpoint.sha,
        pre_squash_target_ref=pre_squash_target_ref,
    ):
        return
    # #5001 pre-merge FOLD-5 (asymmetry rationale): unlike the reconciliation-FAIL
    # path, this does NOT roll the target back. A FAIL means the tree diverged from
    # the approved-WP claim (the whole advance is untrustworthy → revert). Here the
    # squash content itself DID land; only the projected bookkeeping diverged, so
    # reverting the target would discard legitimately-landed approved code. The
    # merge is resumable — ``--resume`` re-projects the bookkeeping — so we exit
    # non-zero WITHOUT a rollback and retain everything for inspection. A
    # squash-sound revert of only the bookkeeping projection is deferred (FU-4
    # squash-content-soundness).
    console.print(
        "\n[red]Error:[/red] SQUASH reconciliation refused: projected coordination "
        f"bookkeeping content did not land on the target. {_NOTHING_TORN_DOWN}; "
        "re-run `spec-kitty consolidate --resume`."
    )
    raise typer.Exit(1)


def _phase_dossier_and_stale(run: _MergeRunState) -> None:
    """Stale-assertion advisory scan (failures never abort)."""
    console.print("  [dim]Running stale-assertion check...[/dim]")
    try:
        run.stale_report = run_check(
            base_ref=run.target_baseline_sha,
            head_ref="HEAD",
            repo_root=run.main_repo,
        )
    except Exception as exc:  # noqa: BLE001 — stale-assertion check is advisory; a failure must never abort an otherwise-successful merge
        logger.warning("Stale-assertion check failed: %s", exc)
        run.stale_report = None


def _phase_push(run: _MergeRunState) -> None:
    """Push the target branch to origin when requested (and a remote exists)."""
    lanes_manifest = run.lanes_manifest
    if not (run.push and has_remote(run.main_repo)):
        return
    _ret_push, _out_push, stderr_push = run_command(
        ["git", "push", "origin", lanes_manifest.target_branch],
        capture=True,
        check_return=False,
        cwd=run.main_repo,
    )
    if _ret_push != 0:
        if _is_linear_history_rejection(stderr_push):
            _emit_remediation_hint(console)
        console.print(f"[red]Error:[/red] Push failed: {stderr_push.strip() or _out_push.strip()}")
        raise typer.Exit(1)
    console.print(f"[green]✓[/green] Pushed {lanes_manifest.target_branch} to origin")


def _flatten_coordination_metadata_after_branch_delete(run: _MergeRunState) -> None:
    """issue #3086: clear the coordination marker once the coord branch is gone.

    ``spec-kitty consolidate --delete-branch`` (the default) deletes a Mission's
    coordination branch (``kitty/mission-<slug>``) from git but, before this fix,
    left the paired ``coordination_branch`` key in
    ``kitty-specs/<slug>/meta.json``. Every later command routing through
    ``resolve_status_surface_with_anchor`` then hit ``CoordState.DELETED`` and
    raised ``CoordinationBranchDeleted`` — the deliberate #1848 data-loss
    hard-fail — a 100% crash on merged coord missions.

    This mirrors the canonical flatten already performed by
    ``spec-kitty mission close --discard`` and ``doctor coordination --fix``:
    all three converge on the single
    :func:`~specify_cli.mission_metadata.flatten_coordination_metadata`
    primitive (#3219 / FR-015 / D-PLAN-17), rather than each call site
    inventing its own copy of the pop-``coordination_branch`` / pop-``topology``
    / set-``flattened`` mutation set.

    **Known residual (T054, verdict-seam-write-unification-01KZ9Q35 WP10):**
    this flatten (and its bookkeeping commit) runs in
    ``_phase_cleanup_worktrees_and_branches``, which executes AFTER
    ``_phase_push``. On a ``spec-kitty consolidate --push``, the flatten bookkeeping
    commit therefore lands LOCAL-ONLY -- it is never pushed to origin, so
    origin/target keeps the stale ``coordination_branch`` key even though the
    local target branch is correctly flattened. Verified as a real, pre-existing
    ordering gap (not introduced or regressed by WP10's convergence); fixing it
    would mean either re-ordering the two phases or pushing a second time after
    cleanup, both out of WP10's scope (a lane-owned convergence WP, not a merge
    phase-ordering change) -- tracked as a follow-up rather than silently
    expanded into here.

    Placement & ordering. This lives in the ``delete_branch`` gate, co-located
    with the branch deletion, so the marker is cleared **iff** the branch it
    names is deleted — the two mutations stay atomic. It is deliberately NOT
    folded into the earlier, unconditional ``_phase_commit_and_assert``: doing so
    would (a) require duplicating this gate's ``delete_branch`` guard into a phase
    that must stay unconditional, and (b) clear the marker *before* the branch is
    deleted, so a failed deletion would strand the inverse inconsistency (a
    cleared marker with a still-live branch). It still runs after the lane->target
    merge-driver reconciliation (which treats ``coordination_branch`` as a
    *theirs-authoritative* planning key, ``consolidation/drivers.py``), so the clear
    is the last writer regardless.

    The edit is persisted through the same protected-flow bookkeeping-commit seam
    the merge uses for its other meta.json mutations. A commit failure here is
    logged and swallowed (fail-open), never raised: this runs in the post-push
    cleanup phase, the on-disk flatten has already cleared ``coordination_branch``
    (so #3086 stays fixed), and aborting an otherwise-complete merge — or
    restoring the pre-flatten snapshot, which would re-strand the marker — is
    worse than a locally-dirty meta.json (recoverable via
    ``spec-kitty doctor coordination --fix``).

    A non-coord Mission (``SINGLE_BRANCH`` / ``LANES``) or an already-flattened
    one carries no ``coordination_branch`` key, so this is an idempotent no-op
    that leaves ``topology`` / ``flattened`` untouched.
    """
    from specify_cli.mission_metadata import flatten_coordination_metadata, load_meta_or_empty

    feature_dir = run.target_feature_dir
    meta = load_meta_or_empty(feature_dir)
    if "coordination_branch" not in meta:
        return

    # Canonical three-mutation flatten (#3219 / FR-015 / D-PLAN-17), converged
    # onto the ONE shared primitive -- parity with ``doctor coordination --fix``
    # / ``mission close --discard``, and closes the double-write window the
    # former two-call (clear + separate topology/flattened write) shape here
    # invited. ``coordination_branch`` presence above means meta.json exists,
    # so ``flatten_coordination_metadata`` cannot raise here.
    flatten_coordination_metadata(feature_dir)

    meta_path = feature_dir / "meta.json"
    if not _paths_have_status_changes(run.main_repo, [meta_path]):
        return

    # Fail-open, unlike ``_phase_commit_and_assert``'s restore-and-reraise: the
    # on-disk flatten already cleared ``coordination_branch`` (so #3086 stays
    # fixed even if the commit does not land), and restoring the pre-flatten
    # snapshot would re-strand the marker. A recovered commit (``commit_sha`` set)
    # actually landed and is a success; every other failure is logged, not raised.
    try:
        commit_merge_bookkeeping(
            repo_root=run.main_repo,
            worktree_root=run.main_repo,
            mission_slug=run.mission_slug,
            branch=run.lanes_manifest.target_branch,
            message=(f"chore({run.mission_slug}): flatten coordination metadata after branch deletion (#3086)"),
            paths=(meta_path,),
        )
    except SafeCommitRecoveryFailed as exc:
        if exc.commit_sha is None:
            logger.warning(
                "Flatten bookkeeping commit did not land for %s (%s); meta.json is "
                "flattened on disk but may be uncommitted — recover with "
                "`spec-kitty doctor coordination --fix`",
                run.mission_slug,
                exc,
            )
    except Exception as exc:
        # Fail-open: never abort a completed merge for a bookkeeping-commit failure.
        logger.warning(
            "Flatten bookkeeping commit failed for %s (%s); meta.json is flattened "
            "on disk but may be uncommitted — recover with "
            "`spec-kitty doctor coordination --fix`",
            run.mission_slug,
            exc,
        )


def _stored_topology_for(feature_dir: Path) -> MissionTopology | None:
    """Read the mission's STORED :class:`MissionTopology` for the churn classifier.

    WP10 integration (C-3 / #4978): the merge dirty gate must thread the mission's
    real topology into :func:`is_toolchain_generated_churn` so the coord-residue
    leg is topology-aware — on a LANES / SINGLE_BRANCH mission a coord-partition
    artifact (``issue-matrix.md``, the status log, ``acceptance-matrix.json``) is
    NEVER residue and is never ``reset --hard``ed as such. Routes through the pure
    :func:`~specify_cli.migration.backfill_topology.read_topology` reader (stored
    value, else derived from ``coordination_branch`` + lanes presence — it never
    persists). An unreadable/absent meta degrades to ``None``, which
    :func:`is_toolchain_generated_churn` maps to its explicit, overridable
    COORD-projecting backward-compatibility default (behaviour-preserving).
    """
    from specify_cli.migration.backfill_topology import read_topology

    try:
        topology: MissionTopology = read_topology(feature_dir)
    except (FileNotFoundError, ValueError, MissionMetaReadError):
        return None
    return topology


def _is_coord_topology_mission(run: _MergeRunState) -> bool:
    """Detect coord topology via the same signal the flatten helper uses (#3131).

    A ``coordination_branch`` key present in the (target) meta.json marks a
    coordination-topology mission whose mission/coord branch, marker, and
    worktree are ONE atomic unit (INV-2) — see
    :func:`_flatten_coordination_metadata_after_branch_delete`, which early-
    returns on this same absence. Reusing that exact signal (rather than
    inventing a second detector) keeps the two functions from silently
    disagreeing about what counts as "coord". Its absence means either the
    mission is ``single_branch``/``lanes`` topology, or a prior partial run
    already flattened it — either way the coupled gate below is inert and the
    mission-branch deletion falls back to the plain ``delete_branch`` gate
    (no behavior change, #3131 T008).
    """
    from specify_cli.mission_metadata import load_meta_or_empty

    meta = load_meta_or_empty(run.target_feature_dir)
    return "coordination_branch" in meta


def _mission_branch_exists(run: _MergeRunState) -> bool:
    ret, _, _ = run_command(
        ["git", "rev-parse", "--verify", f"refs/heads/{run.lanes_manifest.mission_branch}"],
        capture=True,
        check_return=False,
        cwd=run.main_repo,
    )
    return ret == 0


def _delete_mission_branch(run: _MergeRunState) -> bool:
    """Delete the mission/coordination branch from git, if it exists.

    Returns whether the branch is gone afterwards — deleted now, or already
    absent. ``git branch -D`` refuses while the branch is checked out in a
    worktree and ``check_return=False`` swallows that (#3926), so the caller
    that couples this to the rest of the coord triple needs the answer rather
    than an assumed success.

    #5100 T020 safety fix: an UNPROTECTED single_branch mission's manifest
    carries ``mission_branch == target_branch`` (contracts/single-branch-
    execution.md's consolidate table -- bookkeeping only, no branch merge or
    deletion). Without this guard, ``git branch -D <mission_branch>`` would
    delete the mission's TARGET branch itself (e.g. ``main``) the moment
    ``run.delete_branch`` is True -- the single most dangerous consequence
    of ``lanes_manifest.mission_branch`` being unconditionally derived
    ``kitty/mission-...`` for every other topology previously made
    unreachable. Returns ``True`` (nothing to delete, target is untouched)
    rather than attempting it.
    """
    lanes_manifest = run.lanes_manifest
    if lanes_manifest.mission_branch == lanes_manifest.target_branch:
        return True
    if _mission_branch_exists(run):
        run_command(
            ["git", "branch", "-D", lanes_manifest.mission_branch],
            cwd=run.main_repo,
            check_return=False,
        )
        return not _mission_branch_exists(run)
    logger.debug(
        "Mission branch %s does not exist, skipping deletion",
        lanes_manifest.mission_branch,
    )
    return True


def _teardown_coord_worktree(run: _MergeRunState) -> None:
    """Coordination worktree teardown (WP07/FR-016/SC-10).

    The shared ``teardown_coordination_topology`` seam (FR-004) persists the
    retrospective to its durable home BEFORE destroying the worktree
    (persist-before-destroy, FR-005), then performs the idempotent worktree
    removal that safely no-ops for legacy missions that never created a
    coordination worktree (FR-017, empty ``mid8``).
    """
    from specify_cli.coordination.teardown import (
        ProjectionTeardownGate,
        teardown_coordination_topology,
    )
    from specify_cli.core.paths import load_meta_fail_closed as _load_meta

    # FR-007 route: ``route-unwrapped`` census site -- a corrupt meta.json
    # surfaces the typed ``MissionMetaReadError`` (never a raw
    # ``ValueError``) and PROPAGATES, exactly as the raw read did before.
    _meta_for_teardown = _load_meta(run.feature_dir)
    _mid8_for_teardown = str(_meta_for_teardown.get("mid8", "")).strip() if isinstance(_meta_for_teardown, dict) else ""
    # WP10 integration (S-B / FR-004 / T034): when the merge captured a
    # coordination checkpoint AND ran the reconciliation gate, build the
    # projection teardown gate so ``teardown_coordination_topology`` refuses
    # fail-closed unless (a) the reconciliation reachability check passed AND
    # (b) the coordination tip is unchanged since the projection captured its
    # window (compare-and-swap). A non-coord/legacy mission (no checkpoint)
    # keeps the ungated behaviour (``projection_gate=None``).
    #
    # The compare-and-swap protects a SEPARATE coordination branch from a
    # concurrent commit landing between projection and teardown (#4981). When the
    # coordination ref IS the target branch (a degenerate placement where the
    # STATUS_STATE surface resolves to the target itself), the merge's OWN final
    # bookkeeping commit legitimately advances that ref AFTER the projection
    # capture, so a fixed-SHA CAS would false-abort (#2804 regression) — and there
    # is no distinct coordination surface for it to protect anyway. In that case
    # enforce ONLY the reachability leg (a stable ``expected_coord_sha`` equal to
    # the ref's current tip makes the CAS a satisfied no-op) rather than skipping
    # the gate entirely.
    projection_gate: ProjectionTeardownGate | None = None
    checkpoint = run.coord_checkpoint
    if checkpoint is not None and run.reconciliation_result is not None:
        coord_is_distinct = _resolve_ref_sha(run.main_repo, checkpoint.ref) != _resolve_ref_sha(run.main_repo, run.lanes_manifest.target_branch)
        if coord_is_distinct:
            expected_coord_sha = run.coord_tip_after_projection or checkpoint.sha
        else:
            # No separate coordination branch to CAS-protect; anchor on the ref's
            # current tip so the compare-and-swap is a satisfied no-op and only the
            # reachability leg gates teardown.
            expected_coord_sha = _resolve_ref_sha(run.main_repo, checkpoint.ref) or checkpoint.sha
        projection_gate = ProjectionTeardownGate(
            coord_ref=checkpoint.ref,
            expected_coord_sha=expected_coord_sha,
            reachability_ok=run.reconciliation_result.is_pass,
        )
    teardown_coordination_topology(
        run.main_repo,
        run.mission_slug,
        _mid8_for_teardown,
        projection_gate=projection_gate,
    )
    logger.debug(
        "Coordination topology teardown for %s-%s completed",
        run.mission_slug,
        _mid8_for_teardown,
    )


def _teardown_coordination_triple(run: _MergeRunState) -> None:
    """Coord branch + marker-flatten + coord-worktree -- ONE atomic unit.

    #3131 INV-2 / T008: for a coord-topology mission these three resources
    must always be mutually consistent (all retained, or all torn down
    together) -- never a branch deleted while its marker/worktree survive
    (or vice versa), which reintroduces #3086 or strands a coord husk. Called
    only when ``run.teardown_coordination`` (``delete_branch AND
    remove_worktree``) is True.

    **Order matters (#3926).** The worktree goes first: ``git branch -D``
    refuses while the branch is checked out in the coord worktree
    (``cannot delete branch '...' used by worktree at '...'``), and with the
    branch-delete leg running first that refusal was swallowed
    (``check_return=False``) while the flatten ran anyway — leaving exactly
    the inverted #3086 shape the invariant forbids: marker flattened, branch
    and worktree both surviving, and a "Cleaned up" line printed over the
    git error. Removing the worktree first releases the checkout, so the
    delete can succeed; the flatten then runs only once the branch is
    actually gone, and a leg that fails raises instead of reporting success.
    """
    _teardown_coord_worktree(run)
    if not _delete_mission_branch(run):
        raise CoordinationTeardownError(
            f"coordination branch {run.lanes_manifest.mission_branch!r} still exists after teardown; "
            "the mission's coordination marker was left intact so the branch, its worktree and the "
            "marker stay consistent. Remove whatever still references the branch "
            "(`git worktree list`), then re-run `spec-kitty consolidate --resume`."
        )
    _flatten_coordination_metadata_after_branch_delete(run)


def _clear_landed_single_branch_mission_branch(run: _MergeRunState) -> None:
    """#5100 B4: drop ``meta.mission_branch`` once the landed branch is deleted.

    A protected single_branch mission records its minted ``mission_branch`` in
    ``meta.json``. After landing + deletion it names a dead branch: post-merge
    writes (retrospective, status) would route to it and ``mission reopen``
    refuses. Clearing it (mirroring the coord flatten) makes later writes
    resolve to ``target_branch``. No-op unless the branch was landed and is gone.
    """
    from specify_cli.lanes.single_branch_landing import lands_mission_branch
    from specify_cli.mission_metadata import load_meta_or_empty, write_meta

    if not lands_mission_branch(run.main_repo, run.lanes_manifest) or _mission_branch_exists(run):
        return
    feature_dir = run.target_feature_dir
    meta = load_meta_or_empty(feature_dir)
    if "mission_branch" not in meta:
        return
    del meta["mission_branch"]
    write_meta(feature_dir, meta, validate=False)
    meta_path = feature_dir / "meta.json"
    try:
        commit_merge_bookkeeping(
            repo_root=run.main_repo,
            worktree_root=run.main_repo,
            mission_slug=run.mission_slug,
            branch=run.lanes_manifest.target_branch,
            message=f"chore({run.mission_slug}): clear landed mission_branch (#5100)",
            paths=(meta_path,),
        )
    except Exception as exc:  # fail-open: never abort a completed merge for a bookkeeping commit
        logger.warning("mission_branch clear commit failed for %s (%s); meta.json is cleared on disk but may be uncommitted", run.mission_slug, exc)


def _cleanup_mission_branch_and_coordination(run: _MergeRunState) -> None:
    """Topology-aware mission/coordination cleanup (#3131 T008).

    A coord-topology mission couples its mission/coordination branch, marker,
    and worktree under the single ``teardown_coordination`` decision (INV-2)
    so a partial-retention request (only ``delete_branch`` or only
    ``remove_worktree``) never half-tears the coord triple. A non-coord
    mission (``single_branch``/``lanes``) has no coordination branch/marker/
    worktree, so its mission-branch deletion stays on the plain
    ``delete_branch`` gate exactly as before this change (no behavior
    change) -- and the (harmless, no-op) flatten + coord-worktree-teardown
    calls stay wired to their original standalone gates too.
    """
    if _is_coord_topology_mission(run):
        if run.teardown_coordination:
            _teardown_coordination_triple(run)
            console.print("  Cleaned up mission/coordination branch + worktree")
        return

    if run.delete_branch:
        _delete_mission_branch(run)
        _clear_landed_single_branch_mission_branch(run)
        # issue #3086: the coordination branch is now gone from git; flatten the
        # mission's meta.json in the SAME gate so we can never delete the branch
        # yet strand the paired ``coordination_branch`` marker. A no-op here
        # (non-coord mission carries no ``coordination_branch`` key).
        _flatten_coordination_metadata_after_branch_delete(run)
    # A landed protected single_branch mission has NO coordination worktree; its
    # checkpoint ref is the (now deleted) mission branch, so the projection
    # teardown gate would false-abort. Nothing to tear down.
    from specify_cli.lanes.single_branch_landing import lands_mission_branch

    if run.remove_worktree and not lands_mission_branch(run.main_repo, run.lanes_manifest):
        _teardown_coord_worktree(run)


def _remove_lane_worktrees(run: _MergeRunState) -> None:
    """T005/T012 (#4753, C-003): remove every lane worktree + tombstone its context.

    Extracted (tidy-first, WP02/T034) out of
    :func:`_phase_cleanup_worktrees_and_branches`, behaviour-preserving. Routed
    through the shared :func:`~specify_cli.git.destructive_guard.guarded_worktree_remove`
    chokepoint instead of a raw ``git worktree remove --force``. The T010
    preflight has already fail-closed on any dirty lane worktree BEFORE any
    ref advance, so every worktree reaching this loop is known-clean; the
    guard call here is defense-in-depth against a race between preflight and
    cleanup, not the primary safety mechanism. ``retain=False`` because this
    function only runs when ``run.remove_worktree`` is True (removal
    requested) — ``--keep-worktree`` already makes ``run.remove_worktree``
    False and skips this function entirely (ADVISORY-3: do not map the
    operator retain flag onto the guard's ``retain`` parameter here).
    """
    from specify_cli.workspace import delete_context

    lanes_manifest = run.lanes_manifest
    delay = _worktree_removal_delay()
    # WP10 integration (C-3 / #4978): thread the STORED topology so the
    # coord-residue leg is topology-aware — a coord-partition-KIND artifact
    # on a LANES / SINGLE_BRANCH mission is real work, never reset as residue.
    is_residue = functools.partial(
        is_toolchain_generated_churn,
        mission_slug=run.mission_slug,
        topology=_stored_topology_for(run.target_feature_dir),
    )
    for idx, lane in enumerate(worktree_lanes(lanes_manifest)):
        # lane-branch-naming-authority-01M3EVC4 WP02 (T035): the CREATED
        # worktree (never keyed by ``run.baseline_mission_id``), so a
        # divergent-identity mission's worktree is never orphaned.
        wt_path = _created_lane_worktree(run.main_repo, lanes_manifest.mission_slug, lane.lane_id)
        if wt_path.exists():
            guarded_worktree_remove(wt_path, retain=False, is_residue=is_residue)
            console.print(f"  Removed worktree: {wt_path.name}")
            if delay > 0 and idx < len(worktree_lanes(lanes_manifest)) - 1:
                time.sleep(delay)
        else:
            logger.debug("Worktree %s does not exist, skipping removal", wt_path)

    # FR-005/LC-6 (#1842 WP03): tombstone each lane's workspace-context
    # JSON when its worktree is removed at merge completion. The tombstone
    # is deliberately nested under ``remove_worktree``: the context JSON
    # *describes* the worktree, so the two are torn down together — a
    # ``--no-remove-worktree`` merge intentionally keeps BOTH the worktree
    # and its context (never orphaning one from the other).
    # ``delete_context`` itself is a pure, order-independent unlink — it
    # targets the legacy ``<slug>-<lane>`` filename ``save_context`` always
    # writes, and silently no-ops for a lane that never saved a context
    # (e.g. a planning-artifact lane) or one already tombstoned. The
    # filename MUST equal ``_created_lane_worktree(...).name`` (the string
    # ``save_context`` wrote) — never independently composed.
    for lane in worktree_lanes(lanes_manifest):
        workspace_name = _created_lane_worktree(run.main_repo, lanes_manifest.mission_slug, lane.lane_id).name
        delete_context(run.main_repo, workspace_name)


def _delete_lane_branches(run: _MergeRunState) -> None:
    """T005/#3131 T008: delete every non-planning lane branch, retry-tolerant.

    Extracted (tidy-first, WP02/T034) out of
    :func:`_phase_cleanup_worktrees_and_branches`, behaviour-preserving. Lane
    branches stay keyed to the plain ``delete_branch`` gate regardless of
    topology — only the MISSION/coordination branch
    (:func:`_cleanup_mission_branch_and_coordination`) is topology-aware and
    coupled to ``teardown_coordination`` for a coord mission.
    """
    from specify_cli.lanes.compute import is_planning_lane
    from specify_cli.lanes.lane_tip import clear_tip

    lanes_manifest = run.lanes_manifest
    for lane in lanes_manifest.lanes:
        if is_planning_lane(lane):
            continue
        # lane-branch-naming-authority-01M3EVC4 WP02 (T035): the CREATED
        # branch (never a Mission-identity form).
        branch_name = _created_lane_branch(lanes_manifest, lane.lane_id)
        ret, _, _ = run_command(
            ["git", "rev-parse", "--verify", f"refs/heads/{branch_name}"],
            capture=True,
            check_return=False,
            cwd=run.main_repo,
        )
        if ret == 0:
            run_command(
                ["git", "branch", "-D", branch_name],
                cwd=run.main_repo,
                check_return=False,
            )
        else:
            logger.debug("Branch %s does not exist, skipping deletion", branch_name)
        # #5115/WP07 (sibling-owned, one line): the lane-tip ref outlives the
        # branch it was keyed on -- clear it here too, or a future recut of
        # the SAME branch name would inherit a stale tip.
        clear_tip(run.main_repo, branch_name)
    console.print(f"  Cleaned up {len(lanes_manifest.lanes)} lane branch(es)")


def _phase_cleanup_worktrees_and_branches(run: _MergeRunState) -> None:
    """Worktree removal + lane/mission branch deletion + coordination teardown."""
    if run.remove_worktree:
        _remove_lane_worktrees(run)

    if run.delete_branch:
        _delete_lane_branches(run)

    # -- #3131 T008: MISSION/coordination branch + marker + worktree --
    # Topology-aware and (for coord) coupled under ``teardown_coordination``;
    # see ``_cleanup_mission_branch_and_coordination`` for the INV-2 rationale.
    _cleanup_mission_branch_and_coordination(run)


def _phase_finalize_and_summary(run: _MergeRunState) -> None:
    """Cleanup workspace + clear state, render stale findings."""
    # -- T002: Cleanup workspace (preserves state.json) then clear state --
    cleanup_merge_workspace(run.canonical_id, run.main_repo)
    # terminus-merge-integrity WP06 (FR-012) / #5111: ``clear_state`` drops the
    # state and its post-fix marker together (state first), so a subsequent,
    # unrelated merge for the same mission never mistakes a leftover marker for
    # its own in-flight transaction.
    clear_state(run.main_repo, run.canonical_id)

    _render_stale_findings(run.stale_report)


def _render_stale_findings(stale_report: StaleAssertionReport | None) -> None:
    """Render the stale-assertion findings block in the merge summary (T013/T023).

    #3957: message-content (info-grade) assertions are the real signal the
    analyzer skips, so they are surfaced as a named block with per-assertion
    ``file:line`` entries — placed BEFORE the low-grade noise, never buried
    behind it as a trailing count note.
    """
    console.print("\n[bold]Stale assertion findings:[/bold]")
    if stale_report is None:
        console.print("  [yellow]Stale-assertion check could not run.[/yellow]")
        return
    if not stale_report.findings:
        console.print("  No likely-stale assertions detected.")
        return

    actionable = [f for f in stale_report.findings if f.confidence in ("high", "medium")]
    low_grade = [f for f in stale_report.findings if f.confidence == "low"]
    info_grade = [f for f in stale_report.findings if f.confidence == "info"]

    for finding in actionable:
        console.print(_stale_finding_line(finding.confidence, finding))
    if info_grade:
        console.print(f"  Message-content assertions skipped as info grade ({len(info_grade)}) — review manually if diagnostic text changed:")
        for finding in info_grade:
            console.print(_stale_finding_line("info", finding))
    for finding in low_grade:
        console.print(_stale_finding_line(finding.confidence, finding))


def _stale_finding_line(grade: str, finding: StaleAssertionFinding) -> str:
    """One ``[grade] file:line — hint`` finding line, escaped for Rich.

    The line is operator data, not markup: unescaped, Rich parses the bracketed
    grade label (``[high]``, ``[info]`` ...) as an unknown style tag and drops
    it, so the operator could not tell actionable findings from noise.
    """
    return "  " + escape(f"[{grade}] {finding.test_file.name}:{finding.test_line} — {finding.hint}")


def _resolve_coord_worktree_for_preflight(
    main_repo: Path,
    mission_slug: str,
    primary_meta_dir: Path,
) -> Path | None:
    """Resolve the coordination worktree path for the T010 preflight, purely.

    Mirrors ``_is_coord_topology_mission``'s ``coordination_branch``-presence
    signal (rather than inventing a second coord-topology detector) so
    preflight and cleanup never disagree about whether a coordination
    worktree is in play (INV-2). Returns ``None`` for a non-coord-topology
    mission, or a coord mission with no recorded ``mid8`` (legacy/never
    created) — in either case there is no coordination worktree to guard.
    """
    from specify_cli.coordination.workspace import CoordinationWorkspace
    from specify_cli.core.paths import load_meta_fail_closed

    meta = load_meta_fail_closed(primary_meta_dir) or {}
    if "coordination_branch" not in meta:
        return None
    mid8 = str(meta.get("mid8", "")).strip()
    if not mid8:
        return None
    # ``coordination.workspace`` sits behind a repo-wide ``follow_imports =
    # "skip"`` mypy override (pyproject.toml), so the imported staticmethod's
    # declared ``Path`` return type is erased to ``Any`` at this call site.
    # Re-wrapping in ``Path(...)`` (a real, idempotent no-op on the already-
    # ``Path`` runtime value) restores a concrete static type instead of
    # suppressing the check.
    return Path(CoordinationWorkspace.worktree_path(main_repo, mission_slug, mid8))


def _pre_mutation_safety_preflight(
    main_repo: Path,
    mission_slug: str,
    target_branch: str,
    lanes_manifest: LanesManifest,
    primary_meta_dir: Path,
    *,
    remove_worktree: bool,
    teardown_coordination: bool,
) -> None:
    """Refuse-before-destroy preflight for #4752/#4753 (WP03/T010).

    Called from the OUTER :func:`_run_lane_based_consolidation`, BEFORE
    :func:`_run_lane_based_consolidation_locked` runs its phase list — in particular
    before ``_phase_merge_lanes`` (which git-merges lanes into the mission
    branch) and ``_phase_bake_and_pre_target_done`` (which commits a
    done-event on the coord branch). This is the only placement where a
    refusal is byte-identical to pre-invocation (NFR-001): nothing in the
    locked flow has mutated anything yet. Because both a fresh merge and a
    ``--resume`` merge route through the same outer function, ``--resume``
    honors this preflight identically (US1 AC4) with no separate wiring.

    Checks, in order:

    1. The primary checkout is on ``target_branch`` and clean
       (``MERGE_UNSAFE_PRIMARY_OFF_TARGET`` / ``MERGE_UNSAFE_PRIMARY_DIRTY`` —
       FR-001/FR-002/US1 AC1-2).
    2. Every lane worktree is clean (FR-003/US2 AC1) — unless
       ``remove_worktree`` is False (worktree retention in effect), in which
       case a dirty lane worktree is the existing retention path's concern
       (kept, never force-removed) rather than a preflight refusal (US2 AC2).
       This mirrors exactly the gate ``_phase_cleanup_worktrees_and_branches``
       already applies to its own removal loop.
    3. The coordination worktree, when the mission is coord-topology AND the
       coupled coord teardown is actually going to run (``teardown_coordination``
       — ``delete_branch AND remove_worktree``, #3131 INV-2), is clean
       (FR-004/US2 AC4). Gating on ``teardown_coordination`` rather than
       ``remove_worktree`` alone matches ``_cleanup_mission_branch_and_coordination``'s
       real gate for a coord mission, so a partial-retention merge that will
       never touch the coord triple is never refused for a dirty coord
       worktree it was never going to disturb (NFR-002 no-regression).

    Any :class:`~specify_cli.git.destructive_guard.DestructiveOpRefused` raised
    here propagates to the caller, which aborts the merge fail-closed before
    the lock is acquired and before any mutation.
    """
    # WP10 integration (C-3 / #4978): thread the STORED topology so the pre-mutation
    # dirty gate never resets a coord-partition-KIND artifact as residue on a
    # LANES / SINGLE_BRANCH mission.
    is_residue = functools.partial(
        is_toolchain_generated_churn,
        mission_slug=mission_slug,
        topology=_stored_topology_for(primary_meta_dir),
    )

    from specify_cli.lanes.single_branch_landing import expected_consolidate_checkout

    assert_checkout_on_target(main_repo, expected_consolidate_checkout(main_repo, lanes_manifest, target_branch))
    assert_worktree_clean(
        main_repo,
        is_residue=is_residue,
        error_code=MERGE_UNSAFE_PRIMARY_DIRTY,
    )

    if not remove_worktree:
        return

    for lane in worktree_lanes(lanes_manifest):
        # lane-branch-naming-authority-01M3EVC4 WP02 (T033): the CREATED
        # worktree (never a Mission-identity form) — the same placement
        # ``_phase_cleanup_worktrees_and_branches`` removes.
        wt_path = _created_lane_worktree(main_repo, mission_slug, lane.lane_id)
        if wt_path.exists():
            # #4753 Finding A: this worktree is removal-destined, so an
            # untracked-only operator file must block just as a tracked edit
            # does — the obstruction-only default is correct for a
            # ``reset --hard`` (``advance_branch_ref``), not a
            # ``git worktree remove --force``.
            assert_worktree_clean(wt_path, is_residue=is_residue, treat_untracked_as_dirty=True)

    if not teardown_coordination:
        return

    coord_worktree = _resolve_coord_worktree_for_preflight(main_repo, mission_slug, primary_meta_dir)
    if coord_worktree is not None and coord_worktree.exists():
        assert_worktree_clean(coord_worktree, is_residue=is_residue, treat_untracked_as_dirty=True)


def _record_operator_attestations(
    main_repo: Path,
    mission_slug: str,
    *,
    wp_ids: tuple[str, ...],
    reason: str | None,
    acceptably_canceled: frozenset[str],
) -> tuple[str, ...]:
    """Validate and record ``--attest-canceled-superseded`` (FR-012), before any mutation.

    Returns the WP ids whose attestation was recorded (``()`` when none was requested).

    Refuses (exit 1, nothing recorded) a WP that is not canceled with operator
    provenance. Every explicit ``--attest-canceled-superseded`` records a FRESH
    attestation, even for a WP already attested: each is a new operator act
    with its own reason and a new ``lane_head`` stamp, and that stamp is what
    bounds the closed-world exemption (a straggler landed after an earlier
    attestation is covered only once the operator attests again). Written through the canonical transactional status seam
    (``canceled_attestation.record_canceled_superseded_attestation``).
    """
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
    # FR-012: record any operator attestation BEFORE the claim is captured, so
    # the reconciliation gate reads it from the event log it already reads.
    recorded_attestations = _record_operator_attestations(
        main_repo,
        mission_slug,
        wp_ids=attest_canceled_superseded,
        reason=attest_reason,
        acceptably_canceled=excluded_canceled_wp_ids,
    )

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
    )

    # FR-006: at resume startup, heal any coord strand a prior attempt left
    # durably marked (strand-gated + atomic-clear via the coordination primitive).
    # Placed BEFORE the frozen phase list (not a phase-driver wrapper — INV-5),
    # so it is never part of ``expected_order``.
    if run.is_resume:
        _heal_pending_coord_reconcile(run)

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
        # T008 (FR-007/008): capture the pre-mutation checkpoint strictly before the
        # first mutating phase. Consumed by the narrow backstop immediately below
        # AND left available for the resume/doctor heal machinery.
        #
        # Scope note (git-level constraint, verified live): on a coord-topology
        # mission whose lanes.json has MULTIPLE lanes, ``_phase_merge_lanes``
        # produces MERGE commits on the coordination/mission branch (one per
        # consolidated lane). ``git revert <sha>..HEAD`` cannot auto-revert a
        # range that contains a merge commit without an explicit ``-m`` mainline
        # per merge commit — attempting the WIDER revert (back through
        # consolidation) for every later-phase failure corrupted two proven
        # multi-lane coord-topology tests
        # (``tests/specify_cli/cli/commands/test_merge_coord_worktree_resync_1826.py``)
        # during this WP's development, so the backstop below is deliberately
        # scoped to ONLY ``_phase_merge_lanes`` itself — the one phase with no
        # PRE-EXISTING rollback coverage at all, and the only span where the
        # pre-mutation checkpoint is guaranteed not to already contain a
        # just-created merge commit from a SUCCESSFUL prior lane in this same
        # call. Every later phase (baseline/bake through commit-and-assert)
        # keeps its dense pre-existing granular rollback (``_restore_and_guard_
        # coord_coherence`` / ``_restore_pre_target_if_at_baseline``), which
        # never needs to cross a lane-consolidation merge commit because its own
        # checkpoint is captured AFTER consolidation. A residual strand from a
        # PARTIAL multi-lane consolidation failure (lane A ok, lane B fails) is
        # not silently dropped either way: :func:`_reset_coord_to_checkpoint`
        # degrades gracefully (abort + warn) rather than corrupting the branch,
        # and :func:`_rollback_to_pre_mutation_checkpoint` still marks/heals via
        # the SEPARATE, proven coordination-reconcile primitive.
        _capture_pre_mutation_coord_checkpoint(run)
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
    if not _resume_reconciliation_already_passed(run):
        try:
            _phase_merge_lanes(run)
        except Exception as exc:
            _rollback_to_pre_mutation_checkpoint(run, error=exc)
            raise
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
    # gate runs strictly BEFORE any teardown/push — on FAIL/REFUSE it refuses
    # (non-zero), restores the target ref, and tears down nothing (ordering
    # guarantee: teardown executes only after verify == PASS). On a non-zero
    # exit every other snapshotted branch is rolled back too (#5318 / #5332);
    # the target the gate already restored reports ALREADY_AT_SNAPSHOT. The post
    # tips are the ones each ref-moving phase recorded for the branches it moved
    # (slice-10 F2): no blanket re-record here, which would attribute a foreign
    # commit that landed between phases to this run.
    anchor_before = run.state.reconciliation_passed_target_sha
    try:
        _phase_reconcile_before_teardown(run)
    except typer.Exit as exc:
        if exc.exit_code:
            _report_rollback(run, anchor_before=anchor_before)
        raise
    _phase_dossier_and_stale(run)
    _phase_push(run)
    _phase_cleanup_worktrees_and_branches(run)
    _phase_finalize_and_summary(run)


def _report_rollback(run: _MergeRunState, *, anchor_before: str | None) -> None:
    """Roll every snapshotted branch back after a gate/projection refusal and print the report (#5318 / #5332).

    ``anchor_before`` is ``reconciliation_passed_target_sha`` as it stood BEFORE
    the gate phase ran. On a fresh PASS the gate persists THIS run's own PASS
    anchor before the projection proof refuses; left in place, the authority
    would read it as a landing verified by an EARLIER reconciliation (FR-011) and
    refuse to roll back. Restore the pre-gate value first; an anchor from an
    earlier attempt is unchanged by the gate and therefore still keeps that
    verified landing.
    """
    if run.state.reconciliation_passed_target_sha != anchor_before:
        run.state.reconciliation_passed_target_sha = anchor_before
        save_state(run.state, run.main_repo)
    try:
        report = rollback.rollback_to_snapshot(run.main_repo, run.state, target_branch=run.lanes_manifest.target_branch)
    except Exception as exc:
        # The caller re-raises the gate's own ``typer.Exit``; never let a failing
        # rollback replace it with a traceback, and never imply it succeeded.
        branches = ", ".join(sorted(run.state.pre_mutation_refs)) or "the mission branches"
        console.print(f"Rollback could not complete: {exc}; inspect {branches} before re-running.", markup=False)
        return
    console.print(report.render(), markup=False)


def _synthesize_no_lane_manifest(
    *,
    main_repo: Path,
    mission_slug: str,
    status_feature_dir: Path,
    primary_meta_dir: Path,
    target_override: str | None,
) -> LanesManifest:
    """T021 (FR-012, FOLD 1): synthesize a NO-LANE manifest for a direct-on-
    target mission under ``--skip-lanes`` when ``lanes.json`` is genuinely
    absent.

    Reuses the existing, well-tested ``is_planning_artifact_only`` skip-the-
    branch-merge machinery rather than inventing a parallel phase-skip path:
    the target branch already carries the WPs' deliverables (the sanctioned
    direct-on-target fallback — no separate mission branch was ever created),
    which is exactly the precondition ``is_planning_artifact_only`` recognizes.
    The synthesized manifest's single lane uses the canonical planning-lane id
    (:data:`~specify_cli.lanes.compute.PLANNING_LANE_ID`) so every downstream
    phase that already special-cases a planning-artifact-only mission
    (``_phase_merge_lanes``, ``_phase_mission_to_target``,
    ``_phase_bake_and_pre_target_done``) takes its proven already-on-target
    branch, instead of attempting to merge the target branch into itself.

    ``mission_branch`` is set equal to the resolved target branch — there is
    no separate mission branch to merge FROM on this path. WP ids are read off
    the mission's reduced status snapshot (the same mission's WPs the T007
    precondition will evaluate), never re-derived from a different source.
    """
    from specify_cli.lanes.compute import PLANNING_LANE_ID
    from specify_cli.lanes.models import ExecutionLane, LanesManifest
    from specify_cli.status import read_events, reduce

    identity = resolve_mission_identity(primary_meta_dir)
    target_branch, _source = resolve_merge_target_branch(main_repo, mission_slug, target_override)
    snapshot = reduce(read_events(status_feature_dir))
    work_packages = snapshot.work_packages if hasattr(snapshot, "work_packages") else {}
    wp_ids = tuple(sorted(work_packages.keys()))
    lane = ExecutionLane(
        lane_id=PLANNING_LANE_ID,
        wp_ids=wp_ids,
        write_scope=(),
        predicted_surfaces=(),
        depends_on_lanes=(),
        parallel_group=0,
    )
    return LanesManifest(
        version=1,
        mission_slug=mission_slug,
        mission_id=identity.mission_id,
        mission_branch=target_branch,
        target_branch=target_branch,
        lanes=[lane],
        computed_at=now_utc_iso(),
        computed_from="skip-lanes direct-on-target synthesis (T021, FR-012)",
    )


def _report_pre_mutation_refusal(
    exc: DestructiveOpRefused,
    main_repo: Path,
    *,
    mission_branch: str,
    base_sha: str | None = None,
) -> None:
    """Print the pre-mutation refusal, upgrading a behind-own-HEAD remedy (WP05 / #4982/#4997).

    WP10 integration: a dirty-PRIMARY refusal may actually be the checkout sitting
    BEHIND ITS OWN HEAD — a prior terminus advanced the target ref but the
    ``reset --hard`` that refreshes the checkout never ran, so the already-integrated
    lane's files read as local changes. The generic "commit/stash/revert" remedy is
    DANGEROUS there (recording them reverts the merge). Route a
    ``MERGE_UNSAFE_PRIMARY_DIRTY`` refusal through
    :func:`~specify_cli.consolidation.preflight.classify_resume_dirty_remedy` so a
    behind-own-HEAD (or interrupted-``reset``) state gets the safe reset-to-HEAD
    remedy instead. Advisory only — the refusal still aborts fail-closed BEFORE any
    mutation (NFR-001); this only changes the printed guidance.

    #4933: on a FRESH consolidation the mission branch is created off the target
    and never advances until the lanes merge, so it is trivially "already an
    ancestor of HEAD" — the lane-ancestry-only ``BEHIND_OWN_HEAD`` classification
    misfires on every dirty refusal, not just a genuinely interrupted terminus.
    Printing the reset-to-HEAD guidance there tells the operator to run
    ``git reset --hard HEAD``, which destroys the very user edit (e.g. a dirty
    ``src/app/meta.json``) the refusal protects. The upgraded guidance is now gated on
    :func:`~specify_cli.consolidation.preflight.is_pure_behind_head_lag`, the
    content proof #4997 already uses for the ``--resume`` auto-recovery path
    (:func:`_recover_behind_head_primary_on_resume`): it needs a persisted
    ``ConsolidationState.pre_mutation_target_sha`` (``base_sha``) that is a STRICT
    ancestor of HEAD with a byte-identical tree/index and no obstructing untracked
    path. A fresh consolidation has no persisted state (``base_sha=None``), so the
    predicate is fail-closed False and this always falls through to the safe
    commit/stash/revert remedy already present in ``str(exc)``. ``BLOCKED_INDEX_LOCK``
    is unaffected -- it never claims a specific working-tree state to reset into, so
    it carries no #4933 hazard and stays gated on classification alone.
    """
    console.print(f"[red]Error:[/red] {exc}")
    if getattr(exc, "error_code", None) == MERGE_UNSAFE_PRIMARY_DIRTY:
        from specify_cli.consolidation.preflight import (
            ResumeRemedyKind,
            classify_resume_dirty_remedy,
            is_pure_behind_head_lag,
        )

        remedy = classify_resume_dirty_remedy(main_repo, lane_branch=mission_branch)
        proven_behind_head = remedy.kind is ResumeRemedyKind.BEHIND_OWN_HEAD and is_pure_behind_head_lag(main_repo, base_sha=base_sha)
        if remedy.kind is ResumeRemedyKind.BLOCKED_INDEX_LOCK or proven_behind_head:
            console.print("[yellow]Resume recovery guidance (behind-own-HEAD / interrupted reset detected):[/yellow]")
            for line in remedy.remediation:
                console.print(f"  • {line}")
            return
    console.print("[yellow]Merge aborted before any state change.[/yellow] Resolve the reported condition, then re-run [bold]spec-kitty consolidate[/bold].")


def _load_state_on_refusal_path(main_repo: Path, canonical_id: str) -> ConsolidationState | None:
    """Read the persisted merge state on a pre-mutation REFUSAL path, fail-closed (N6).

    A corrupt ``state.json`` raises :class:`ConsolidationStateReadError`; on the
    refusal path that exception would REPLACE the dirty-tree refusal the operator
    needs to see. Treat it as "no provable resume state" instead: ``None`` means no
    auto-recovery and no reset-to-HEAD guidance (the safe commit/stash/revert remedy
    already in the refusal message stands). The corruption is still surfaced as a
    warning so it is not silently lost; a later ``--resume`` hits the loud
    fail-closed read on its own normal path.
    """
    try:
        return load_state(main_repo, canonical_id)
    except ConsolidationStateReadError as exc:
        console.print(f"[yellow]Warning:[/yellow] ignoring unreadable merge state while reporting the refusal: {exc}")
        return None


def _recover_behind_head_primary_on_resume(
    exc: DestructiveOpRefused,
    main_repo: Path,
    canonical_id: str,
    *,
    mission_branch: str,
) -> bool:
    """Recover a provably-pure behind-own-HEAD primary in place, ON A RESUME (#4997).

    The pre-mutation primary dirty guard refuses ``MERGE_UNSAFE_PRIMARY_DIRTY`` when the
    checkout carries staged deletions. After an interrupted terminus that advanced the
    target ref but never ran the checkout's ``reset --hard`` (#1826), those deletions are
    the mission's already-integrated files read in reverse — a pure lag, NOT genuine local
    work. Instead of aborting (which strands the merge, or invites the catastrophic
    "Commit" mis-remedy), a ``--resume`` repairs it here: ``git reset --hard HEAD``.

    Fail-closed, and NEVER on a fresh merge:

    * only on a ``--resume`` (a persisted :class:`ConsolidationState` exists);
    * only when :func:`~specify_cli.consolidation.preflight.classify_resume_dirty_remedy` reports
      ``BEHIND_OWN_HEAD`` (lane-ancestry) AND
      :func:`~specify_cli.consolidation.preflight.is_pure_behind_head_lag` proves the working tree
      AND index are byte-identical to the persisted ``pre_mutation_target_sha`` with no
      untracked file obstructing a restored path (so the reset destroys nothing genuine —
      the data-loss hole a lane-ancestry-only gate would leave).

    Returns ``True`` iff it reset the primary (the caller re-runs the preflight once and
    continues); ``False`` for every non-recoverable refusal (the caller aborts unchanged).
    """
    if getattr(exc, "error_code", None) != MERGE_UNSAFE_PRIMARY_DIRTY:
        return False
    state = _load_state_on_refusal_path(main_repo, canonical_id)
    if state is None:
        return False  # fresh merge (or unreadable state): a dirty primary is genuine, never auto-reset.
    from specify_cli.consolidation.preflight import (
        ResumeRemedyKind,
        classify_resume_dirty_remedy,
        is_pure_behind_head_lag,
    )

    remedy = classify_resume_dirty_remedy(main_repo, lane_branch=mission_branch)
    if remedy.kind is not ResumeRemedyKind.BEHIND_OWN_HEAD:
        return False
    if not is_pure_behind_head_lag(main_repo, base_sha=state.pre_mutation_target_sha):
        return False
    reset_ret, _out, reset_err = run_command(
        ["git", "reset", "--hard", "HEAD"],
        capture=True,
        check_return=False,
        cwd=main_repo,
    )
    if reset_ret != 0:
        console.print(f"[red]Error:[/red] behind-own-HEAD recovery `git reset --hard HEAD` failed in {main_repo}: {reset_err.strip()}")
        return False
    console.print("[yellow]Recovered a behind-own-HEAD primary checkout (git reset --hard HEAD over phantom staged deletions); continuing resume.[/yellow]")
    return True


def _pre_mutation_safety_preflight_with_recovery(
    main_repo: Path,
    mission_slug: str,
    lanes_manifest: LanesManifest,
    canonical_id: str,
    primary_meta_dir: Path,
    retention: RetentionDecision,
) -> None:
    """Run the pre-mutation safety preflight, with #4997 behind-own-HEAD resume recovery.

    On a ``DestructiveOpRefused``, a ``--resume`` first tries to recover a provably-pure
    behind-own-HEAD primary (:func:`_recover_behind_head_primary_on_resume`) and re-runs the
    preflight once; every non-recoverable refusal (and every fresh-merge refusal) aborts
    fail-closed with the reported remediation. Kept as one helper so the outer
    :func:`_run_lane_based_consolidation` stays within the complexity ceiling.
    """

    def _run() -> None:
        _pre_mutation_safety_preflight(
            main_repo,
            mission_slug,
            lanes_manifest.target_branch,
            lanes_manifest,
            primary_meta_dir,
            remove_worktree=retention.remove_worktree,
            teardown_coordination=retention.teardown_coordination,
        )

    try:
        _run()
    except DestructiveOpRefused as exc:
        recovered = _recover_behind_head_primary_on_resume(exc, main_repo, canonical_id, mission_branch=lanes_manifest.mission_branch)
        if not recovered:
            # #4933: the persisted ``pre_mutation_target_sha`` (absent on a fresh
            # consolidation) is the only proof `_report_pre_mutation_refusal` will
            # accept for the reset-to-HEAD guidance -- see its docstring.
            state = _load_state_on_refusal_path(main_repo, canonical_id)
            _report_pre_mutation_refusal(
                exc,
                main_repo,
                mission_branch=lanes_manifest.mission_branch,
                base_sha=state.pre_mutation_target_sha if state else None,
            )
            raise typer.Exit(1) from exc
        try:
            _run()
        except DestructiveOpRefused as exc_after:
            state = _load_state_on_refusal_path(main_repo, canonical_id)
            _report_pre_mutation_refusal(
                exc_after,
                main_repo,
                mission_branch=lanes_manifest.mission_branch,
                base_sha=state.pre_mutation_target_sha if state else None,
            )
            raise typer.Exit(1) from exc_after


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
    # coord-aware STATUS legs (``status_feature_dir``). It MUST stay on the
    # topology-aware resolver so the append-only event log resolves the coord
    # worktree for a coord-topology mission.
    seam = placement_seam(main_repo, mission_slug)
    # Fail-closed, but NOT with a traceback, for either coord-partition read
    # failure sibling: a deleted coordination branch means the mission's status
    # authority is gone, so the merge cannot proceed (``CoordinationBranchDeleted``);
    # an unmaterialized-but-still-extant coordination worktree (fresh clone / CI /
    # ``git worktree remove`` window) means the status authority is intact but not
    # yet checked out (``CoordinationWorktreeUnmaterialized``, #4959) — neither is a
    # traceback-worthy crash. Render each exception's own remediation (its
    # ``next_step``, already folded into ``str(exc)``) and exit, matching the
    # handler shape at ``agent/status.py`` and ``mission_finalize.py``.
    try:
        feature_dir = seam.read_dir(MissionArtifactKind.STATUS_STATE)
    except CoordinationBranchDeleted as exc:
        console.print(f"[red]Error:[/red] {exc}")
        console.print(
            "[yellow]Merge aborted before any state change.[/yellow] Recover the mission's status authority, then re-run [bold]spec-kitty consolidate[/bold]."
        )
        raise typer.Exit(1) from exc
    except CoordinationWorktreeUnmaterialized as exc:
        console.print(f"[red]Error:[/red] {exc}")
        console.print(
            "[yellow]Merge aborted before any state change.[/yellow] Materialize the coordination worktree, then re-run [bold]spec-kitty consolidate[/bold]."
        )
        raise typer.Exit(1) from exc
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

    if skip_lanes:
        lanes_manifest = read_lanes_json(lanes_read_dir)
        if lanes_manifest is None:
            lanes_manifest = _synthesize_no_lane_manifest(
                main_repo=main_repo,
                mission_slug=mission_slug,
                status_feature_dir=feature_dir,
                primary_meta_dir=primary_meta_dir,
                target_override=target_override,
            )
    else:
        lanes_manifest = require_lanes_json(lanes_read_dir)
    if target_override:
        lanes_manifest.target_branch = target_override
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
        )
    finally:
        release_merge_lock(_GLOBAL_MERGE_LOCK_ID, main_repo)


__all__ = [
    "_run_lane_based_consolidation",
    "_run_lane_based_consolidation_locked",
]
