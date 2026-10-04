"""Run state shared by every consolidation phase (epic #2026).

Holds :class:`_MergeRunState` (the mutable record each phase helper takes,
INV-3), :class:`_CoordCheckpoint` and its resolver, the per-phase post-mutation
tip recorder :func:`_records_post_mutation_tips` that the rollback authority
relies on (only branches that moved during the phase are recorded; never after a
compare-and-swap refusal, always after a ``RefResyncError``), the primary-checkout
snapshot capture, the shared refusal wording, the stored-topology probes, the
shared error types, and the small helpers more than one phase module calls
(:func:`_created_lane_worktree`, :func:`_resume_reconciliation_already_passed`).

Moved from ``consolidation/executor.py`` by epic #2026 with no logic change.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
import functools
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Concatenate, ParamSpec, cast


if TYPE_CHECKING:
    from specify_cli.lanes.models import LanesManifest

from specify_cli.core.constants import KITTIFY_DIR, KITTY_SPECS_DIR, WORKTREES_DIR
from specify_cli.coordination.atomic_write import (
    capture_generated_artifact_snapshots,
)
from specify_cli.core.git_ops import run_command
from specify_cli.core.paths import (
    MissionMetaReadError,
    get_main_repo_root,
)
from specify_cli.git.ref_advance import (
    RefAdvanceError,
    RefResyncError,
    RefRestoreError,
)

from specify_cli.consolidation._constants import (
    COORD_MOVED_AFTER_LANDING,
    COORD_MOVED_AFTER_LANDING_EXIT_CODE,
)
from specify_cli.consolidation.config import MergeStrategy
from specify_cli.consolidation import rollback
from specify_cli.consolidation.reconciliation import (
    ApprovedWpCommitSet,
    VerifyResult,
)
from specify_cli.consolidation.bookkeeping_projection import _resolve_ref_sha
from specify_cli.consolidation.state import (
    ConsolidationState,
    reconciliation_passed_for_tip,
)
from mission_runtime import (
    MissionArtifactKind,
    MissionTopology,
    resolve_placement_only,
)
from specify_cli.post_merge.stale_assertions import StaleAssertionReport


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

    #: The exit code ``spec-kitty consolidate`` reports for this refusal.
    exit_code: int = 1


class CoordMovedAfterLanding(CoordinationTeardownError):
    """The mission/coordination branch moved after the landing was verified (#5570, #5613).

    The compare-and-swap delete kept the branch, so the late commit is intact and
    the landed target is not rolled back. A subclass, so every existing handler
    of :class:`CoordinationTeardownError` still sees it; it only adds the stable
    code and the distinct exit code automation keys on.

    The remedy differs per variant and is spelled out by the message
    (:func:`_tip_moved_teardown_error`): a coordination branch is finished by
    ``spec-kitty consolidate --resume``; a mission branch with no coordination
    topology is landed and deleted by hand.

    Not the same refusal as
    :class:`~specify_cli.coordination.teardown.ProjectionTeardownAbort`
    (``PROJECTION_TEARDOWN_ABORTED``). That one is the same race caught in an
    EARLIER window: the coordination tip moved between the projection capture and
    the teardown gate, before anything was persisted or destroyed, so the whole
    coordination triple survives. It keeps its own code and exit 1. This class is
    the later window: the gate passed and the worktree was removed, then the branch
    moved before its compare-and-swap delete.
    """

    error_code = COORD_MOVED_AFTER_LANDING
    exit_code = COORD_MOVED_AFTER_LANDING_EXIT_CODE


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
    # Explicit annotation: under ``follow_imports = "skip"`` the owner's return is ``Any``.
    snapshots: dict[Path, bytes | None] = capture_generated_artifact_snapshots(
        *paths,
        trusted_roots=_merge_snapshot_roots(main_repo),
        trusted_files=_merge_snapshot_files(main_repo),
    )
    return snapshots


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
    # coord-write-placement-closure-01KYCF83 WP09 (IC-08 / FR-009): the
    # ``meta.json`` path the birth-time runtime cutover flipped (when it
    # flipped), so the porcelain-invariant + bookkeeping-commit phases can
    # recognize the write.
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

    # #2711 FR-006: the coordination-branch ref + tip SHA captured BEFORE the
    # pre-target ``done`` emit. The strand marker (``_persist_coord_reconcile_marker``)
    # and the ``done`` write-set derivation read the committed coordination state
    # relative to this tip; the ref undo itself is the driver's single rollback door.
    pre_target_coord_ref: str | None = None
    pre_target_coord_sha: str | None = None

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


@dataclass(frozen=True)
class _CoordCheckpoint:
    """T008: a NAMED, resolved coordination-branch checkpoint (ref + tip SHA).

    Captured via :func:`_capture_coord_checkpoint`. Consumers: the
    transaction-start ``run.coord_checkpoint`` (the reconciliation claim's base
    and the projection window), the persisted pre-mutation anchor
    (:func:`_resolve_pre_mutation_coord_sha`, which seeds the rollback
    snapshot), and the pre-``done`` tip (``run.pre_target_coord_ref``/``_sha``)
    the strand marker reads. None of them is a revert anchor: undoing a
    consolidation's ref moves is the single rollback door's job (#5385).
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
