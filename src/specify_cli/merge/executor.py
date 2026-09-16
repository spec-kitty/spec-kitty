"""Lane-based merge executor for the merge seam.

Mission #2057 (decompose ``cli/commands/merge.py``) — IC-10 / WP10 (HIGH-RISK).

Relocates ``_run_lane_based_merge`` (the global-lock wrapper) and the CC-102
``_run_lane_based_merge_locked`` driver out of the command shim, decomposing the
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

import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Final

import typer

if TYPE_CHECKING:
    from specify_cli.lanes.merge import MissionMergeResult
    from specify_cli.lanes.models import LanesManifest
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
    is_under_worktrees_segment,
    resolve_status_surface,
)
from specify_cli.core.git_ops import has_remote, run_command
from kernel.clock import now_utc_iso
from specify_cli.core.paths import (
    MissionMetaReadError,
    get_main_repo_root,
    resolve_merge_retention,
)
from specify_cli.git.bookkeeping_commit import (
    commit_coord_seed_bookkeeping,
    commit_merge_bookkeeping,
)
from specify_cli.git.commit_helpers import SafeCommitRecoveryFailed
from specify_cli.merge.git_probes import _paths_have_status_changes
from specify_cli.git.sparse_checkout import require_no_sparse_checkout
from specify_cli.lanes.persistence import require_lanes_json
from specify_cli.merge._constants import _STATUS_EVENTS_FILENAME, _STATUS_FILENAME, logger
from specify_cli.merge.baseline import (
    BaselineMergeCommitError,
    assert_baseline_merge_commit_on_target as _assert_baseline_merge_commit_on_target,
    record_baseline_merge_commit as _record_baseline_merge_commit,
)
from specify_cli.merge.bookkeeping_projection import (
    _project_status_bookkeeping_to_target,
    _target_bookkeeping_status_paths,
    _target_branch_still_at_baseline,
)
from specify_cli.merge.config import MergeStrategy
from specify_cli.merge.done_bookkeeping import (
    _assert_merged_wps_done_on_target,
    _record_merged_wps_done_for_merge,
    _resolve_merge_actor,
    acceptably_canceled_wp_ids,
)
from specify_cli.merge.git_probes import (
    _branch_trees_equal,
    _classify_porcelain_lines,
    _emit_remediation_hint,
    _is_linear_history_rejection,
    _lane_already_integrated,
    _raw_porcelain_status,
    _refresh_primary_checkout_after_merge,
)
from specify_cli.merge.ordering import (
    _assign_planning_only_mission_number_if_needed,
    _bake_mission_number_into_mission_branch,
)
from specify_cli.merge.preflight import (
    _check_mission_branch,
    _effective_push_requested,
    _enforce_canonical_status_history,
    _enforce_planning_artifact_target_branch,
    _enforce_review_artifact_consistency,
    _warn_or_confirm_hollow_reviews,
)
from specify_cli.merge.push_preflight import _enforce_target_branch_sync_preflight
from specify_cli.merge.resolve import _load_or_create_merge_state
from specify_cli.merge.state import (
    MergeLockError,
    MergeState,
    acquire_merge_lock,
    clear_state,
    get_state_path,
    release_merge_lock,
    save_state,
)
from specify_cli.merge.workspace import _worktree_removal_delay, cleanup_merge_workspace
from specify_cli.mission_metadata import resolve_mission_identity
from mission_runtime import MissionArtifactKind, placement_seam, resolve_placement_only
from specify_cli.post_merge.stale_assertions import StaleAssertionReport, run_check

_GLOBAL_MERGE_LOCK_ID = "__global_merge__"


class CoordinationTeardownError(RuntimeError):
    """A leg of the coord triple (worktree, branch, marker) did not come down.

    #3131 INV-2 makes the triple all-or-nothing, so a partial teardown has to
    stop the run and say so rather than print a success line over a git error
    and leave a stranded coord worktree/branch behind (#3926).
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
    ``-X theirs`` add/add conflict resolution can discard an already-accepted
    target-checkout ``acceptance-matrix.json`` / ``issue-matrix.json`` in favor of
    the mission branch's stale finalize-time scaffold placeholder (#2804). A
    mission's gate artifacts are per-mission (``kitty-specs/<slug>/...``), so in
    ordinary operation (no #2404-class divergent write) target carries nothing
    here pre-merge and this snapshot is empty/``None`` — a genuine no-op for
    :func:`_restore_regressed_gate_artifacts` below.
    """
    run.pre_target_gate_artifact_snapshots = _capture_merge_snapshots(
        run.main_repo, *_gate_artifact_paths(run)
    )


def _restore_regressed_gate_artifacts(run: _MergeRunState) -> None:
    """Preserve an already-accepted target gate artifact through the squash merge (#2804).

    D-PLAN-7: the durable fix is at the WRITE surface (WP08 T040/T041 stop a
    second, divergent PRIMARY-partition copy from ever being authored under
    coordination topology) — row-aware reconciliation of a genuine same-key
    divergence is WP09's merge-driver defense-in-depth, not this function's job.
    This guard is narrower and complementary: when the target checkout ALREADY
    held gate-artifact content before the squash merge (:func:`_capture_pre_
    target_gate_artifacts`) and the squash step's ``-X theirs`` resolution
    changed it, the pre-merge bytes are restored verbatim — an established,
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
    None; ``_run_lane_based_merge_locked`` becomes the linear phase caller.
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
    state: MergeState
    is_resume: bool
    any_lane_had_unintegrated_code: bool = False
    # FR-004 / FR-009: WP IDs at an acceptable *canceled* ending (operator
    # provenance) on the coord surface — resolved ONCE at lock entry via
    # ``acceptably_canceled_wp_ids`` and threaded to the lane-consolidation phase so a
    # fully-canceled lane (whose branch may not exist) is skipped without a
    # second coord read. ``all_wp_ids`` already has these filtered out.
    excluded_canceled_wp_ids: frozenset[str] = frozenset()
    target_baseline_sha: str = "HEAD~1"
    baseline_mission_id: str | None = None
    done_marked_before_target: bool = False
    mission_already_applied: bool = False
    mission_number_meta_path: Path | None = None
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


def _phase_gates_and_state(run: _MergeRunState) -> None:
    """Banner, merge gates, and bootstrap/hollow-review history guards.

    The review-artifact consistency gate runs in ``_run_lane_based_merge_locked``
    BEFORE merge-state is created (so a rejected mission writes no state.json).
    """
    from specify_cli.policy.config import load_policy_config
    from specify_cli.policy.merge_gates import evaluate_merge_gates

    lanes_manifest = run.lanes_manifest

    if run.is_resume:
        console.print(
            f"[bold cyan]Resuming[/bold cyan] merge for {run.mission_slug} "
            f"({len(run.state.completed_wps)}/{len(run.state.wp_order)} WPs already done)"
        )

    console.print(f"[bold]Lane-based merge for {run.mission_slug}[/bold]")
    console.print(f"  Mission branch: {lanes_manifest.mission_branch}")
    console.print(f"  Lanes: {', '.join(ln.lane_id for ln in lanes_manifest.lanes)}")
    if run.planning_artifact_only:
        console.print(
            "  [dim]Planning-artifact-only mission: target branch already "
            "contains deliverables; branch merge steps will be skipped.[/dim]"
        )

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


def _phase_merge_lanes(run: _MergeRunState) -> None:
    """Merge each lane branch into the mission branch (skipping integrated lanes)."""
    from specify_cli.lanes.branch_naming import lane_branch_name
    from specify_cli.lanes.compute import is_planning_lane
    from specify_cli.lanes.merge import consolidate_lane_into_mission

    lanes_manifest = run.lanes_manifest
    for lane in lanes_manifest.lanes:
        if run.planning_artifact_only and is_planning_lane(lane):
            console.print(
                f"  [green]✓[/green] {lane.lane_id} already on {lanes_manifest.target_branch}"
            )
            continue

        # FR-004 / FR-009: skip branch integration ONLY when EVERY WP in the lane
        # is a canceled-with-provenance acceptable ending (its lane branch may
        # never have been created — the #2945 shape). A mixed lane (survivors +
        # canceled) still integrates its survivors, so this guard requires ALL
        # WPs excluded, never merely any.
        if lane.wp_ids and all(
            wp in run.excluded_canceled_wp_ids for wp in lane.wp_ids
        ):
            console.print(
                f"  [dim]Skipping {lane.lane_id} (all WPs canceled with "
                "provenance — acceptable ending, no branch to integrate)[/dim]"
            )
            continue

        # FR-037: skip ONLY when the lane branch is already fully integrated into
        # the mission branch (real tree state), never on the ``done`` proxy.
        _lane_branch = lane_branch_name(
            run.mission_slug,
            lane.lane_id,
            planning_base_branch=lanes_manifest.target_branch,
        )
        if not is_planning_lane(lane) and _lane_already_integrated(
            run.main_repo, _lane_branch, lanes_manifest.mission_branch
        ):
            console.print(
                f"  [dim]Skipping {lane.lane_id} (already integrated into "
                f"{lanes_manifest.mission_branch})[/dim]"
            )
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
        run.baseline_mission_id = resolve_mission_identity(
            run.target_feature_dir
        ).mission_id
    except Exception:  # noqa: BLE001 — meta.json may be missing/corrupt for legacy missions
        run.baseline_mission_id = None

    status_surface_path = resolve_status_surface(run.main_repo, run.mission_slug)
    run.done_marked_before_target = (
        is_under_worktrees_segment(status_surface_path) and not run.planning_artifact_only
    )
    run.canonical_events_path = status_surface_path
    run.canonical_status_path = status_surface_path.parent / _STATUS_FILENAME
    run.merge_state_path = get_state_path(run.main_repo, run.state.mission_id)


def _phase_bake_and_pre_target_done(run: _MergeRunState) -> None:
    """Bake mission_number on the mission branch and pre-target done bookkeeping."""
    lanes_manifest = run.lanes_manifest
    if run.planning_artifact_only:
        console.print(
            f"  [dim]Skipping mission branch merge; {lanes_manifest.target_branch} "
            "is the planning artifact branch.[/dim]"
        )
        run.mission_already_applied = True
        return

    # -- WP10/T053/T055: assign dense integer mission_number on mission branch --
    _bake_mission_number_into_mission_branch(
        main_repo=run.main_repo,
        mission_slug=run.mission_slug,
        mission_branch=lanes_manifest.mission_branch,
        target_branch=lanes_manifest.target_branch,
        dry_run=False,
        merge_state=run.state,
    )

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
            _restore_and_guard_coord_coherence(
                run, run.pre_target_bookkeeping_snapshots, error=exc
            )
            raise


def _capture_pre_target_coord_ref_sha(run: _MergeRunState) -> None:
    """Capture the coordination-branch ref + tip SHA BEFORE the pre-target
    ``done`` emit (#2711 / FR-006).

    The ref is sourced from the canonical write-target the ``done`` commit
    resolves to (``resolve_placement_only(..., kind=STATUS_STATE).ref``) — NOT
    an inline ``meta.get("coordination_branch")`` (the retired D-2 CWD-divergence
    class). The captured tip is the coherent rollback anchor consumed by
    :func:`_revert_coord_done_commit`. A placement that cannot be resolved (a
    non-coord topology, or a legacy mission) leaves both fields ``None`` so the
    rollback revert is a proven no-op.
    """
    try:
        coord_ref = resolve_placement_only(
            run.main_repo, run.mission_slug, kind=MissionArtifactKind.STATUS_STATE
        ).ref
    except Exception:  # noqa: BLE001 — unresolvable placement: skip the coherent revert
        return
    ret, sha, _err = run_command(
        ["git", "rev-parse", coord_ref],
        capture=True,
        check_return=False,
        cwd=run.main_repo,
    )
    if ret == 0 and sha.strip():
        run.pre_target_coord_ref = coord_ref
        run.pre_target_coord_sha = sha.strip()


def _coord_reconcile_read_feature_dir(run: _MergeRunState) -> Path:
    """Primary feature dir (name == slug) anchoring the committed-coord read.

    Mirrors ``done_bookkeeping._durable_done_wps_on_coordination_ref``: a
    ``WORK_PACKAGE_TASK`` read folds onto the topology-blind
    ``primary_feature_dir_for_mission`` (name == slug), so the coord-ref path
    (``kitty-specs/<slug>/status.events.jsonl``) and the legacy-parse dir match
    the placement the rollback used — no ``-coord`` husk, no re-resolution drift.
    """
    feature_dir: Path = placement_seam(run.main_repo, run.mission_slug).read_dir(
        MissionArtifactKind.WORK_PACKAGE_TASK
    )
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
    run.pre_target_done_write_set = [
        wp for wp in run.all_wp_ids if wp not in pre_existing_done
    ]


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


def _revert_coord_done_commit(run: _MergeRunState) -> None:
    """Revert the pre-target ``done`` commit on the coordination branch (#2711 / FR-006).

    On a target-advance rollback the committed coordination ``done`` must be
    reversed in lockstep with the working-tree byte restore, or the committed
    reduction (``done``) diverges from the rolled-back working tree (``approved``)
    — the #2711 split-brain, which also breaks resume dedup / idempotency.

    Reverses every commit made since the captured pre-emit tip via a coord-worktree
    ``git revert`` — a forward reversing commit that resyncs HEAD + index + working
    tree coherently. This is the AC-B3-symmetric inverse of the ``safe_commit``
    (``git commit``) that recorded the ``done``: NEVER a raw ``git update-ref``
    (AC-B3); ``advance_branch_ref`` cannot serve here because moving the ref back
    to the captured tip is the non-fast-forward move it refuses by design.
    Subprocess env routes through ``_make_merge_env`` (AC-F1).

    This is the #2711 in-merge lockstep revert on the (still-clean) pre-restore
    worktree — kept in its canonical raw form (its no-op / success / abort branches
    are pinned by ``test_executor_option_a_revert_helpers_2711.py``). The NEW #2786
    / #2367-B reconciliation authority is the resume/doctor heal, which routes
    through the shared coordination primitive ``repair_coord_strand`` (see
    :func:`_heal_pending_coord_reconcile`); this leg stays orthogonal.
    """
    from specify_cli.lanes.merge import _make_merge_env

    coord_ref = run.pre_target_coord_ref
    captured_sha = run.pre_target_coord_sha
    if not coord_ref or not captured_sha:
        return  # no coordination ref captured (non-coord topology) — no-op
    coord_worktree = _coord_worktree_root(run)
    if coord_worktree is None:
        return
    env = _make_merge_env()
    head = subprocess.run(
        ["git", "-C", str(coord_worktree), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if head.returncode != 0 or head.stdout.strip() == captured_sha:
        return  # nothing committed on the coordination branch since capture — no-op
    revert = subprocess.run(
        ["git", "-C", str(coord_worktree), "revert", "--no-edit", f"{captured_sha}..HEAD"],
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
            "#2711: could not revert coordination 'done' commit(s) on %s (%s..HEAD); "
            "committed/working coherence may be degraded: %s",
            coord_ref,
            captured_sha[:12],
            (revert.stderr or revert.stdout or "").strip(),
        )


def _persist_coord_reconcile_marker(
    run: _MergeRunState, error: BaseException | None
) -> None:
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
    """
    if run.done_marked_before_target and _target_branch_still_at_baseline(
        run.main_repo,
        run.lanes_manifest.target_branch,
        run.target_baseline_sha,
    ):
        _revert_coord_done_commit(run)
        _restore_and_guard_coord_coherence(run, run.pre_target_bookkeeping_snapshots)


def _reject_zero_diff_noop_squash(run: _MergeRunState) -> None:
    """FR-037 fail-loud: refuse a zero-code no-op squash when lane work remains."""
    console.print(
        "[red]Error:[/red] Mission→target merge integrated zero lane "
        "diffs but un-integrated lane work remains. Refusing to report a "
        "zero-code squash as success (#1772 FR-037)."
    )
    console.print(
        f"  Mission branch: {run.lanes_manifest.mission_branch}; "
        f"target: {run.lanes_manifest.target_branch}. "
        "Inspect the lane branches and rerun, or `spec-kitty merge --abort`."
    )
    _restore_pre_target_if_at_baseline(run)
    raise typer.Exit(1)


def _handle_mission_merge_result(
    run: _MergeRunState,
    mission_result: MissionMergeResult,
    *,
    mission_integrated_into_target: bool,
) -> None:
    """Process the mission→target result: fail-loud / retry-tolerance / success log."""
    lanes_manifest = run.lanes_manifest
    run.mission_already_applied = getattr(mission_result, "already_applied", False) is True
    if (
        run.mission_already_applied
        and not run.planning_artifact_only
        and (run.any_lane_had_unintegrated_code or not mission_integrated_into_target)
    ):
        _reject_zero_diff_noop_squash(run)

    if not mission_result.success:
        # T005: tolerate already-merged on retry
        already_merged = any("already" in e.lower() or "up to date" in e.lower() for e in mission_result.errors)
        if run.is_resume and already_merged:
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


def _phase_mission_to_target(run: _MergeRunState) -> None:
    """Merge the mission branch into the target branch (honoring strategy)."""
    if run.planning_artifact_only:
        return

    from specify_cli.lanes.merge import integrate_mission_into_target

    lanes_manifest = run.lanes_manifest
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
    _handle_mission_merge_result(
        run, mission_result, mission_integrated_into_target=_mission_integrated_into_target
    )


def _phase_capture_and_baseline(run: _MergeRunState) -> None:
    """Refresh checkout, capture final snapshots, plan mission_number, RECORD #1827 baseline."""
    # -- WP05/T006 FR-013: Post-merge working-tree refresh --
    _refresh_primary_checkout_after_merge(run.main_repo)

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

    if run.planning_artifact_only:
        run.mission_number_meta_path = _assign_planning_only_mission_number_if_needed(
            run.main_repo,
            run.feature_dir,
        )

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

    try:
        target_events_path, target_status_path = _project_status_bookkeeping_to_target(
            main_repo=run.main_repo,
            mission_slug=run.mission_slug,
            status_feature_dir=run.feature_dir,
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
    raised, and skipped entirely for a planning-artifact-only mission (no WPs
    to reconcile).
    """
    if run.planning_artifact_only:
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
        logger.warning(
            "birth-cutover for %s did not reconcile: %s", run.mission_slug, result.error
        )

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
        logger.warning(
            "birth-cutover coord seed commit failed for %s: %s", run.mission_slug, exc
        )


def _phase_porcelain_invariant(run: _MergeRunState) -> None:
    """WP05/T007 FR-014: post-merge working-tree invariant before the housekeeping commit."""
    _ret_status, _out_status = _raw_porcelain_status(run.main_repo)
    if _ret_status != 0:
        console.print(
            "[yellow]Warning:[/yellow] post-merge invariant check skipped: "
            f"git status --porcelain returned {_ret_status}"
        )
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

    console.print(
        "[red]Error:[/red] Post-merge working-tree invariant violated. "
        "The following paths diverge from HEAD unexpectedly:"
    )
    for line in offending_lines:
        console.print(f"  {line}")
    deleted_or_modified = any(
        len(line) >= 2 and (line[1] in ("D", "M") or line[0] in ("D", "M"))
        for line in offending_lines
    )
    if deleted_or_modified:
        console.print(
            "\nThis may indicate a sparse-checkout or filter-driver issue. Run\n"
            "  spec-kitty doctor sparse-checkout --fix\n"
            "before retrying the merge."
        )
    else:
        console.print(
            "\nUnexpected working-tree state after merge. "
            "Run `git status` to investigate before retrying."
        )
    _restore_and_guard_coord_coherence(run, run.final_bookkeeping_snapshots)
    raise typer.Exit(1)


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

    ``spec-kitty merge --delete-branch`` (the default) deletes a Mission's
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
    ``_phase_push``. On a ``spec-kitty merge --push``, the flatten bookkeeping
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
    *theirs-authoritative* planning key, ``merge/merge_driver.py``), so the clear
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
            message=(
                f"chore({run.mission_slug}): flatten coordination metadata "
                f"after branch deletion (#3086)"
            ),
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
    """
    lanes_manifest = run.lanes_manifest
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
    from specify_cli.coordination.teardown import teardown_coordination_topology
    from specify_cli.core.paths import load_meta_fail_closed as _load_meta

    # FR-007 route: ``route-unwrapped`` census site -- a corrupt meta.json
    # surfaces the typed ``MissionMetaReadError`` (never a raw
    # ``ValueError``) and PROPAGATES, exactly as the raw read did before.
    _meta_for_teardown = _load_meta(run.feature_dir)
    _mid8_for_teardown = (
        str(_meta_for_teardown.get("mid8", "")).strip()
        if isinstance(_meta_for_teardown, dict)
        else ""
    )
    teardown_coordination_topology(
        run.main_repo,
        run.mission_slug,
        _mid8_for_teardown,
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
            "(`git worktree list`), then re-run `spec-kitty merge --resume`."
        )
    _flatten_coordination_metadata_after_branch_delete(run)


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
        # issue #3086: the coordination branch is now gone from git; flatten the
        # mission's meta.json in the SAME gate so we can never delete the branch
        # yet strand the paired ``coordination_branch`` marker. A no-op here
        # (non-coord mission carries no ``coordination_branch`` key).
        _flatten_coordination_metadata_after_branch_delete(run)
    if run.remove_worktree:
        _teardown_coord_worktree(run)


def _phase_cleanup_worktrees_and_branches(run: _MergeRunState) -> None:
    """Worktree removal + lane/mission branch deletion + coordination teardown."""
    from specify_cli.lanes.branch_naming import lane_branch_name, worktree_dir_name, worktree_path
    from specify_cli.lanes.compute import is_planning_lane
    from specify_cli.workspace import delete_context

    lanes_manifest = run.lanes_manifest
    # -- T005: Worktree removal with retry tolerance and macOS FSEvents delay --
    if run.remove_worktree:
        delay = _worktree_removal_delay()
        for idx, lane in enumerate(lanes_manifest.lanes):
            wt_path = worktree_path(
                run.main_repo,
                run.mission_slug,
                mission_id=run.baseline_mission_id,
                lane_id=lane.lane_id,
            )
            if wt_path.exists():
                run_command(
                    ["git", "worktree", "remove", str(wt_path), "--force"],
                    cwd=run.main_repo,
                    check_return=False,
                )
                console.print(f"  Removed worktree: {wt_path.name}")
                if delay > 0 and idx < len(lanes_manifest.lanes) - 1:
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
        # writes (mission_id=None, matching the workspace/context.py grammar),
        # and silently no-ops for a lane that never saved a context (e.g. a
        # planning-artifact lane) or one already tombstoned.
        for lane in lanes_manifest.lanes:
            workspace_name = worktree_dir_name(run.mission_slug, mission_id=None, lane_id=lane.lane_id)
            delete_context(run.main_repo, workspace_name)

    # -- T005: LANE branch deletion with retry tolerance --
    # #3131 T008: lane branches stay keyed to the plain ``delete_branch`` gate
    # regardless of topology — only the MISSION/coordination branch (below) is
    # topology-aware and coupled to ``teardown_coordination`` for a coord
    # mission.
    if run.delete_branch:
        for lane in lanes_manifest.lanes:
            if is_planning_lane(lane):
                continue
            branch_name = lane_branch_name(run.mission_slug, lane.lane_id)
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
        console.print(f"  Cleaned up {len(lanes_manifest.lanes)} lane branch(es)")

    # -- #3131 T008: MISSION/coordination branch + marker + worktree --
    # Topology-aware and (for coord) coupled under ``teardown_coordination``;
    # see ``_cleanup_mission_branch_and_coordination`` for the INV-2 rationale.
    _cleanup_mission_branch_and_coordination(run)


def _phase_finalize_and_summary(run: _MergeRunState) -> None:
    """Cleanup workspace + clear state, render stale findings."""
    # -- T002: Cleanup workspace (preserves state.json) then clear state --
    cleanup_merge_workspace(run.canonical_id, run.main_repo)
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
        console.print(
            f"  [{finding.confidence}] {finding.test_file.name}:{finding.test_line} — {finding.hint}"
        )
    if info_grade:
        console.print(
            f"  Message-content assertions skipped as info grade ({len(info_grade)}) — "
            "review manually if diagnostic text changed:"
        )
        for finding in info_grade:
            console.print(
                f"  [info] {finding.test_file.name}:{finding.test_line} — {finding.hint}"
            )
    for finding in low_grade:
        console.print(
            f"  [{finding.confidence}] {finding.test_file.name}:{finding.test_line} — {finding.hint}"
        )


def _run_lane_based_merge_locked(
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
) -> None:
    """Inner merge flow, called with the global merge lock held.

    Linear phase caller: each phase mutates the shared :class:`_MergeRunState`.
    The #1827 ordering (INV-5) and the snapshot-restore-on-exception sites (INV-6)
    are preserved exactly within and across the phase boundaries.
    """
    from specify_cli.lanes.compute import is_planning_artifact_only

    # read-side-seam-primary-primitive-closure-01KYKMMT WP06 (T029): routed off
    # the retiring ``primary_feature_dir_for_mission`` wrapper onto the seam
    # directly — PRIMARY_METADATA, since this anchors ``run.target_feature_dir``
    # (meta.json reads/writes: ``:867`` ``meta.json`` path, ``:996``
    # ``cutover_mission``'s ``status_phase`` flip target). WP08 (T036):
    # dropped the caller-side canonicalizer fold — redundant with the seam's
    # own internal fold for a PRIMARY-partition kind.
    target_feature_dir = placement_seam(main_repo, mission_slug).read_dir(
        MissionArtifactKind.PRIMARY_METADATA
    )
    # FR-004 / FR-009: exclude canceled-with-provenance WPs from the per-WP
    # done/review derivations. ``all_wp_ids`` feeds the review-artifact
    # consistency gate (:1671), the evidence/canonical-history guards
    # (``_phase_gates_and_state``), ``wp_order`` (:1681), and the final
    # ``_assert_merged_wps_reached_done`` — a canceled WP has no review artifact
    # and never reaches ``done``, so leaving it in would break the merge on an
    # acceptable ending. Resolved once here and threaded to the lane-consolidation phase.
    excluded_canceled_wp_ids = frozenset(
        acceptably_canceled_wp_ids(main_repo, mission_slug)
    )
    all_wp_ids = [
        wp
        for lane in lanes_manifest.lanes
        for wp in lane.wp_ids
        if wp not in excluded_canceled_wp_ids
    ]
    planning_artifact_only = is_planning_artifact_only(lanes_manifest)

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
    )

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
    )

    # FR-006: at resume startup, heal any coord strand a prior attempt left
    # durably marked (strand-gated + atomic-clear via the coordination primitive).
    # Placed BEFORE the frozen phase list (not a phase-driver wrapper — INV-5),
    # so it is never part of ``expected_order``.
    if run.is_resume:
        _heal_pending_coord_reconcile(run)

    _phase_gates_and_state(run)
    _phase_merge_lanes(run)
    _phase_baseline_and_surface(run)
    _phase_bake_and_pre_target_done(run)
    _capture_pre_target_gate_artifacts(run)
    _phase_mission_to_target(run)
    _phase_capture_and_baseline(run)
    _phase_record_done_and_project(run)
    _phase_porcelain_invariant(run)
    _phase_commit_and_assert(run)
    _phase_dossier_and_stale(run)
    _phase_push(run)
    _phase_cleanup_worktrees_and_branches(run)
    _phase_finalize_and_summary(run)


def _run_lane_based_merge(
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
) -> None:
    """Execute the lane-only merge flow with MergeState lifecycle for recovery.

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
    """
    main_repo = get_main_repo_root(repo_root)
    # STATUS leg (C-001 / KEEP): ``feature_dir`` is threaded into
    # ``_run_lane_based_merge_locked`` as ``run.feature_dir`` and feeds the
    # coord-aware STATUS legs (``status_feature_dir``). It MUST stay on the
    # topology-aware resolver so the append-only event log resolves the coord
    # worktree for a coord-topology mission.
    seam = placement_seam(main_repo, mission_slug)
    # Fail-closed, but NOT with a traceback: a deleted coordination branch means
    # the mission's status authority is gone, so the merge cannot proceed. Render
    # the exception's own remediation (``doctor coordination --fix``) and exit,
    # matching the handler shape at ``agent/status.py`` and ``mission_finalize.py``.
    try:
        feature_dir = seam.read_dir(MissionArtifactKind.STATUS_STATE)
    except CoordinationBranchDeleted as exc:
        console.print(f"[red]Error:[/red] {exc}")
        console.print(
            "[yellow]Merge aborted before any state change.[/yellow] "
            "Recover the mission's status authority, then re-run "
            "[bold]spec-kitty merge[/bold]."
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
        command="spec-kitty merge",
        override_flag=allow_sparse_checkout,
        actor=_resolve_merge_actor(main_repo),
        mission_slug=mission_slug,
        mission_id=_preflight_mission_id,  # WP04: str | None; slug fallback removed
    )

    from specify_cli.lanes.compute import is_planning_artifact_only

    lanes_manifest = require_lanes_json(lanes_read_dir)
    if target_override:
        lanes_manifest.target_branch = target_override
    planning_artifact_only = is_planning_artifact_only(lanes_manifest)

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
        console.print(
            "[red]Error:[/red] Cannot resolve the merge retention policy: "
            f"{exc}. meta.json exists but is corrupt or unreadable; fix it "
            "before merging."
        )
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
            console.print(
                "[red]Error:[/red] Missing mission branch: "
                f"{branch_blocker['expected_branch']}. "
                f"Run: {branch_blocker['remediation']}"
            )
            raise typer.Exit(1)

    # -- Acquire global merge lock to serialize concurrent merges --
    if not acquire_merge_lock(_GLOBAL_MERGE_LOCK_ID, main_repo):
        raise MergeLockError(
            _GLOBAL_MERGE_LOCK_ID,
            main_repo / KITTIFY_DIR / "runtime" / "merge" / _GLOBAL_MERGE_LOCK_ID / "lock",
        )

    try:
        _run_lane_based_merge_locked(
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
        )
    finally:
        release_merge_lock(_GLOBAL_MERGE_LOCK_ID, main_repo)


__all__ = [
    "_run_lane_based_merge",
    "_run_lane_based_merge_locked",
]
