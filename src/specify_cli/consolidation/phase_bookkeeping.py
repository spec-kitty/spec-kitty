"""Bookkeeping phases after the target advanced (INV-5 #1827 ordering).

The target-tree mission_number write and verification (#4900), the final snapshot
capture and baseline RECORD, ``done`` recording plus status projection onto the
target (and the projection CAS anchor for the teardown gate), the birth-time
runtime cutover, the post-merge porcelain invariant, and the bookkeeping commit
followed by the done and baseline ASSERTs.

Moved from ``consolidation/executor.py`` by epic #2026 with no logic change.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

import typer
from rich.markup import escape

if TYPE_CHECKING:
    from specify_cli.lanes.models import LanesManifest

from specify_cli.cli.console import console
from specify_cli.coordination.coherence import (
    is_toolchain_generated_churn,
)
from kernel.git import GitCommandError
from specify_cli.core.paths import (
    MissionMetaReadError,
)
from specify_cli.git.bookkeeping_commit import (
    commit_coord_seed_bookkeeping,
    commit_merge_bookkeeping,
)
from specify_cli.git.commit_helpers import SafeCommitRecoveryFailed
from specify_cli.consolidation.git_probes import _paths_have_status_changes

from specify_cli.consolidation._constants import (
    _STATUS_EVENTS_FILENAME,
    _STATUS_FILENAME,
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
    AliasFileNotPreserved,
    AliasFiles,
    AliasStatusEventsNotPreserved,
    _project_status_bookkeeping_to_target,
    _resolve_ref_sha,
    _target_bookkeeping_status_paths,
    assert_alias_events_preserved,
    assert_alias_files_preserved,
    coordination_alias_files,
    remove_alias_files,
)
from specify_cli.consolidation.done_bookkeeping import (
    _assert_merged_wps_done_on_target,
    _record_merged_wps_done_for_merge,
)
from specify_cli.consolidation.git_probes import (
    _classify_porcelain_lines,
    _raw_porcelain_status,
    _refresh_primary_checkout_after_merge,
)
from specify_cli.consolidation.mission_number.bake import (
    _assign_planning_only_mission_number_if_needed,
    _bake_mission_number_onto_target_tree,
    _mark_mission_number_baked,
    _read_target_tree_mission_number,
)
from specify_cli.consolidation.coord_strand import (
    _coord_worktree_root,
    _restore_and_guard_coord_coherence,
)
from specify_cli.consolidation.phase_advance import (
    _restore_regressed_gate_artifacts,
)
from specify_cli.consolidation.run_state import (
    _MergeRunState,
    _NOTHING_TORN_DOWN,
    _capture_merge_snapshots,
    _records_post_mutation_tips,
)

# ``specify_cli.*`` imports are followed with ``follow_imports = "skip"``, so the imported tip
# recorder reads as ``Any`` and would leave every phase it decorates untyped. Declaring its
# signature once keeps the decorated phases typed.
_PhaseStep = Callable[[_MergeRunState], None]
_record_post_mutation_tips: Callable[[_PhaseStep], _PhaseStep] = _records_post_mutation_tips


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


def _resolve_expected_mission_number(run: _MergeRunState) -> int | None:
    """Resolve the mission_number to write + verify on the target tree (#4900).

    Priority, so the SAME number is found on every topology and a stale
    mission-branch value can never overwrite a number the target already
    carries ("target wins", and resume safety):

    1. The TARGET's own CURRENT working-tree value, when it already carries
       an assigned number for this mission. Authoritative -- covers a
       squash that already correctly preserved it (the merge-driver fix), a
       genuinely-completed prior run, AND the coord-topology primary-tree
       fallback (``mission_number.bake._bake_mission_number_on_primary_tree`` commits
       DIRECTLY onto ``target_branch``, so by the time this phase runs
       post-squash the target already carries it -- no separate "primary
       tree" read is needed here). Read via
       :func:`~specify_cli.consolidation.mission_number.bake._read_target_tree_mission_number`
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
    target_current: int | None = _read_target_tree_mission_number(run.target_feature_dir)
    if target_current is not None:
        return target_current
    if run.assigned_mission_number is not None:
        return int(run.assigned_mission_number)
    from_ref: int | None = _read_mission_number_from_ref(run.main_repo, lanes_manifest.mission_branch, run.mission_slug)
    return from_ref


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


def _phase_capture_and_baseline(run: _MergeRunState) -> None:
    """Refresh checkout, capture final snapshots, plan mission_number, RECORD #1827 baseline."""
    # A previous attempt may have landed the mission before failing here. The
    # target tip captured earlier in this resumed attempt can then be the
    # mission's own commit; use the transaction-start anchor persisted before
    # the first attempt changed the target. That anchor predates a coord-topology
    # primary-tree mission-number bake, which a fresh run re-anchors past
    # (phase_advance._reanchor_baseline_past_primary_tree_bake), so on such a
    # resume the review diff also shows that one bookkeeping commit.
    if run.is_resume and run.state.pre_mutation_target_sha:
        run.target_baseline_sha = run.state.pre_mutation_target_sha

    # -- WP05/T006 FR-013: Post-merge working-tree refresh --
    # WP03/T011 (#4752): pass the target branch so the refresh's own
    # defense-in-depth guard can refuse a ``reset --hard`` against an
    # off-target checkout even if the earlier preflight were ever bypassed.
    _refresh_primary_checkout_after_merge(
        run.main_repo,
        run.lanes_manifest.target_branch,
        mission_slug=run.mission_slug,
        lag_base_sha=run.state.pre_mutation_target_sha,
    )

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


@_record_post_mutation_tips
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
        if isinstance(exc, GitCommandError):
            _refuse_unreadable_projection_window(exc)
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


def _refuse_unreadable_projection_window(exc: GitCommandError) -> NoReturn:
    """Turn an unreadable coordination window into a refusal (FR-013).

    The post-checkpoint projection runs AFTER ``_phase_mission_to_target``
    advanced the target, so a failed ``rev-list``/diff over the coordination
    window must not escape as a traceback: it exits non-zero so the merge
    driver's single post-mutation rollback door (#5385) rolls the target back
    through the single rollback authority, the same shape as
    :func:`_squash_projected_paths_or_refuse`.
    """
    console.print(
        "\n[red]Error:[/red] Consolidation refused: the coordination bookkeeping "
        f"window to project onto the target could not be read ({escape(str(exc))}). "
        f"{_NOTHING_TORN_DOWN}; re-run `spec-kitty consolidate --resume`."
    )
    raise typer.Exit(1) from exc


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
    pre-target bake hook (``mission_number.bake._bake_mission_number_into_mission_branch``,
    the ``phase_advance`` bake phase). A detached mission-branch worktree (the
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
    under flat/single-branch topology (T047's degenerate case). Because this runs
    AFTER the projection call above, a seed appended to the COORD leg is then
    re-projected onto the PRIMARY copy (:func:`_project_birth_cutover_seed_to_target`,
    #4787): PRIMARY is the post-merge status authority and the coord triple is
    torn down, so a COORD-only seed would leave the flipped mission's canonical
    log without its deterministic seed rows.

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
        _project_birth_cutover_seed_to_target(run, status_feature_dir)


def _project_birth_cutover_seed_to_target(run: _MergeRunState, status_feature_dir: Path) -> None:
    """Carry birth-cutover seed events from the COORD leg onto the target (#4787).

    The cutover runs AFTER :func:`_project_status_bookkeeping_to_target`, so any
    seed it appends to the COORD ``status.events.jsonl`` would be missing from
    the PRIMARY copy — yet PRIMARY is the post-merge status authority
    (``resolve_status_surface`` re-anchors a merged mission there) and the coord
    triple is torn down afterwards. Re-run the status-only projection (the
    idempotent event-log union + ``status.json`` rematerialization; no checkpoint,
    so the non-status window is not re-projected and the teardown CAS anchor is
    untouched). The target paths are already in the final bookkeeping commit.
    Best-effort, like the rest of the birth-cutover: logged, never raised.
    """
    try:
        _project_status_bookkeeping_to_target(
            main_repo=run.main_repo,
            mission_slug=run.mission_slug,
            status_feature_dir=status_feature_dir,
        )
    except Exception as exc:  # noqa: BLE001 — best-effort, must never abort the merge
        logger.warning("birth-cutover seed projection failed for %s: %s", run.mission_slug, exc)


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
    # The seed phase refreshes a persisted ``status.json`` alongside the log (#5862); commit the
    # pair together or the refreshed snapshot is left dirty and the teardown guard refuses.
    snapshot_path = status_feature_dir / _STATUS_FILENAME
    seed_paths = (events_path, snapshot_path) if snapshot_path.is_file() else (events_path,)
    try:
        if not _paths_have_status_changes(coord_worktree_root, list(seed_paths)):
            return  # nothing seeded/uncommitted — resume-safe no-op
        # Intentionally exercised UN-mocked by tests/migration/test_birth_cutover.py
        # (the real git write) — do not add this call to a mock stack.
        commit_coord_seed_bookkeeping(
            repo_root=run.main_repo,
            worktree_root=coord_worktree_root,
            mission_slug=run.mission_slug,
            message=f"chore({run.mission_slug}): birth-cutover seed events reconciled",
            paths=seed_paths,
            branch=coord_ref,
        )
    except Exception as exc:  # noqa: BLE001 — best-effort, must never abort the merge
        logger.warning("birth-cutover coord seed commit failed for %s: %s", run.mission_slug, exc)


def _phase_porcelain_invariant(run: _MergeRunState) -> None:
    """WP05/T007 FR-014: post-merge working-tree invariant before the housekeeping commit."""
    _ret_status, _out_status = _raw_porcelain_status(run.main_repo)
    if _ret_status != 0:
        # Guard (FR-013): an unreadable working tree is not a clean one. Refuse
        # exactly like a violated invariant instead of skipping the check.
        console.print(
            "[red]Error:[/red] Post-merge working-tree invariant could not be checked: "
            f"git status --porcelain returned {_ret_status}. Run `git status` to investigate before retrying."
        )
        _restore_and_guard_coord_coherence(run, run.final_bookkeeping_snapshots)
        raise typer.Exit(1)

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
        churn: bool = is_toolchain_generated_churn(path_part, mission_slug=run.mission_slug)
        return churn

    offending_entries, _skipped_untracked = _classify_porcelain_lines(
        _out_status,
        expected_paths,
        residue_predicate=_is_coord_residue,
    )
    if not offending_entries:
        return

    console.print("[red]Error:[/red] Post-merge working-tree invariant violated. The following paths diverge from HEAD unexpectedly:")
    for entry in offending_entries:
        console.print(f"  {entry.display()}")
    deleted_or_modified = any(entry.worktree in ("D", "M") or entry.index in ("D", "M") for entry in offending_entries)
    if deleted_or_modified:
        console.print("\nThis may indicate a sparse-checkout or filter-driver issue. Run\n  spec-kitty doctor sparse-checkout --fix\nbefore retrying the merge.")
    else:
        console.print("\nUnexpected working-tree state after merge. Run `git status` to investigate before retrying.")
    if any("/decisions/" in entry.display() for entry in offending_entries):
        # WP12 (#5023) reclassified the decision ledger to the PRIMARY
        # partition, so this predicate no longer exempts uncommitted
        # ``decisions/`` content as coord-residue churn (message-only
        # change -- the predicate itself, ``is_toolchain_generated_churn``,
        # is untouched here).
        console.print(
            f"\nUncommitted decision-ledger files under kitty-specs/{run.mission_slug}/decisions/ are real "
            'content now (WP12) -- commit them with `spec-kitty accept` or `spec-kitty spec-commit -m "..." '
            f"kitty-specs/{run.mission_slug}/decisions/` before retrying."
        )
    _restore_and_guard_coord_coherence(run, run.final_bookkeeping_snapshots)
    raise typer.Exit(1)


def _prove_alias_files_redundant(run: _MergeRunState, alias: AliasFiles) -> None:
    """Prove every file of *alias* redundant with the primary Mission directory, or raise (nothing is touched).

    The status log first: every event id of the composed log is in the unioned primary log
    (:func:`assert_alias_events_preserved`). Then every other coordination-kind file by its bytes
    (:func:`assert_alias_files_preserved`), against the primary directory's copy in the target
    checkout or at the run's pre-mutation target tip.
    """
    assert run.target_events_path is not None
    events_log = alias.directory / _STATUS_EVENTS_FILENAME
    if events_log in alias.files:
        assert_alias_events_preserved(alias_events_path=events_log, primary_events_path=run.target_events_path)
    assert_alias_files_preserved(
        alias,
        main_repo=run.main_repo,
        pre_mutation_sha=run.state.pre_mutation_refs.get(run.lanes_manifest.target_branch),
    )


def _fold_alias_directory(run: _MergeRunState) -> list[Path]:
    """Remove the composed coordination directory's coordination-kind files from the target tree (#5651, FR-019).

    A bare-slug coordination Mission ends with ONE Mission directory on the
    target, the primary one. The coordination seed carries every coordination-kind
    file of that directory (the status pair, traces, matrices, the decision log, review
    cycles) into the composed ``<slug>-<mid8>`` directory, and they ride the squash onto the
    target. The status events were unioned into the primary log earlier in this run. Here,
    after proving EVERY such file redundant (:func:`_prove_alias_files_redundant`: the status
    log by event id, any other file by its bytes against the primary directory's copy now or at
    the run's pre-mutation target tip), the files are unlinked together with the directories
    that leaves empty, and returned so the caller commits the removal in the bookkeeping commit
    that already exists. Returns ``[]`` for a Mission whose status directory is its primary
    directory. A file that is not a coordination kind is never touched, so the gate still fails
    on it. Fails closed and all or nothing: if any file cannot be proven, the snapshots are
    restored, nothing is unlinked and the refusal propagates.
    """
    assert run.target_events_path is not None
    alias = coordination_alias_files(
        main_repo=run.main_repo,
        mission_slug=run.mission_slug,
        status_feature_dir=run.feature_dir,
    )
    if alias is None:
        return []
    run.final_bookkeeping_snapshots.update(_capture_merge_snapshots(run.main_repo, *alias.files))
    try:
        _prove_alias_files_redundant(run, alias)
    except (AliasStatusEventsNotPreserved, AliasFileNotPreserved) as exc:
        _restore_and_guard_coord_coherence(run, run.final_bookkeeping_snapshots, error=exc)
        raise
    remove_alias_files(alias)
    return list(alias.files)


@_record_post_mutation_tips
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
    # every requested path with ``git add --force`` and fails when a path is
    # neither on disk nor tracked, whereas ``_paths_have_status_changes`` (the
    # gate just below) tolerates a nonexistent path (``git status --porcelain``
    # reports nothing for it). Before the birth-cutover phase, this list's
    # non-optional members (``target_events_path``/``target_status_path``) were
    # the only ones ever unconditionally present and a delta-free mission never
    # triggered the commit at all, so this latent existence mismatch was never
    # exercised; the birth-cutover's own genuine delta (a seed event / the
    # ``status_phase`` flip) can now be the ONLY change in an otherwise
    # status.json-less mission, surfacing it.
    # NOTE (PR #2920 review F5): this filter is write/update-only -- it drops a
    # path that is absent on disk, so it cannot carry a deletion. The one
    # deletion this phase makes, the composed coordination directory's
    # coordination-kind files (#5651), is therefore appended AFTER the filter on
    # purpose: those files are tracked on the target, so ``safe_commit`` stages
    # their removal.
    files_to_commit = [path for path in files_to_commit if path.exists()]
    files_to_commit.extend(_fold_alias_directory(run))

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
    ``mission_number.bake``'s bake/write seams, which run BEFORE the target-tree write
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
