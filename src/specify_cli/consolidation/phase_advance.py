"""Advance phases: lanes into the mission branch, then the mission into the target.

Lane consolidation (skipping integrated and fully-canceled lanes), the status
surface and target baseline, the mission-number bake plus pre-target ``done``
bookkeeping, the mission->target integration with its fail-loud handling, the
#2804 gate-artifact preservation guard, and the single_branch write-checkout
switch. Ref-moving phases carry :func:`~specify_cli.consolidation.run_state._records_post_mutation_tips`.

Moved from ``consolidation/executor.py`` by epic #2026 with no logic change.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Final

import typer

if TYPE_CHECKING:
    from specify_cli.lanes.consolidation import MissionConsolidationResult
    from specify_cli.lanes.models import ExecutionLane

from specify_cli.cli.console import console
from specify_cli.coordination.surface_resolver import (
    is_under_worktrees_segment,
    resolve_status_surface,
)
from specify_cli.core.git_ops import run_command
from specify_cli.core.paths import (
    MissionMetaReadError,
)

# Shared FR-004/FR-009 "fully canceled" predicate and lane-branch composer
# (single canonical home in ``lanes.compute`` — see its docstrings), imported
# under the historical private names this module's call sites use.
from specify_cli.lanes.compute import lane_created_branch as _created_lane_branch
from specify_cli.lanes.compute import lane_fully_canceled as _lane_fully_canceled
from specify_cli.consolidation._constants import (
    _STATUS_EVENTS_FILENAME,
    _STATUS_FILENAME,
    TARGET_BRANCH_CONTENT_CONFLICT,
    TARGET_BRANCH_CONTENT_CONFLICT_HEADER,
    TARGET_BRANCH_CONTENT_CONFLICT_REMEDIATION_UPDATE,
)
from specify_cli.consolidation.baseline import (
    BaselineMergeCommitError,
)
from specify_cli.consolidation.done_bookkeeping import (
    _record_merged_wps_done_for_merge,
)
from specify_cli.consolidation.git_probes import (
    _branch_trees_equal,
    _lane_already_integrated,
)
from specify_cli.consolidation.mission_number.bake import (
    _bake_mission_number_into_mission_branch,
)
from specify_cli.consolidation.state import (
    get_state_path,
)
from specify_cli.mission_metadata import resolve_mission_identity
from specify_cli.consolidation.coord_strand import (
    _capture_pre_target_coord_ref_sha,
    _capture_pre_target_done_write_set,
    _restore_and_guard_coord_coherence,
    _restore_pre_target_if_at_baseline,
)
from specify_cli.consolidation.run_state import (
    LaneNamingSlugMismatch,
    _CONSOLIDATE_ABORT_COMMAND,
    _MergeRunState,
    _capture_merge_snapshots,
    _is_coord_topology_mission,
    _records_post_mutation_tips,
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


def _primary_mission_is_merged(primary_dir: Path) -> bool:
    """True when the PRIMARY Mission dir carries merge evidence (non-raising).

    Same predicate ``resolve_status_surface`` applies before re-anchoring a
    completed Mission on the repository root checkout: a corrupt or unreadable
    ``meta.json`` reads as not-merged.
    """
    from specify_cli.status import StoreError, is_mission_merged

    if not (primary_dir / "meta.json").is_file():
        return False
    try:
        return bool(is_mission_merged(primary_dir))
    except (StoreError, MissionMetaReadError):
        return False


def _completed_mission_projected_events_path(run: _MergeRunState) -> Path | None:
    """The completed-Mission ``--resume`` events path, or ``None`` when the Mission is not completed.

    The ONE sanctioned read of a status surface in this module (FR-008): after a
    landed consolidation the records are already projected onto the target, so a
    ``--resume`` re-entering a completed Mission keeps the PRIMARY answer
    ``resolve_status_surface`` returns. This is a READ of projected records, not a
    write location.
    """
    if not _primary_mission_is_merged(run.target_feature_dir):
        return None
    # Explicit annotation: under ``follow_imports = "skip"`` the cross-module
    # return is seen as ``Any``; the function IS typed ``-> Path``.
    projected: Path = resolve_status_surface(run.main_repo, run.mission_slug)
    return projected


def _resolve_run_status_surface(run: _MergeRunState) -> Path:
    """The run's canonical ``status.events.jsonl`` path: ONE authority per run (ruling Q4).

    ``run.feature_dir`` was resolved once through the write accessor in the
    unlocked pre-phase; the locked driver does not re-derive the surface, except
    for the completed-Mission ``--resume`` case (see
    :func:`_completed_mission_projected_events_path`).
    """
    projected = _completed_mission_projected_events_path(run)
    return projected if projected is not None else run.feature_dir / _STATUS_EVENTS_FILENAME


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

    status_surface_path = _resolve_run_status_surface(run)
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
            # Working-tree bytes + strand marker only; an orphan primary-tree bake
            # commit on the target is undone by the driver's rollback door (#5385).
            _restore_and_guard_coord_coherence(run, run.pre_target_bookkeeping_snapshots, error=exc)
            raise


def _reanchor_baseline_past_primary_tree_bake(run: _MergeRunState) -> None:
    """#4764 FOLD-F1: detect + re-anchor past a primary-tree bake commit.

    The coord-topology ``_bake_mission_number_on_primary_tree`` fallback
    (``mission_number/bake.py``, invoked when meta.json is absent on the mission-branch
    tree) commits directly on ``run.main_repo``'s current checkout, which
    never leaves ``target_branch`` during a merge. Re-reading the target tip
    right after the bake call and comparing it to ``run.target_baseline_sha``
    (captured in ``_phase_baseline_and_surface``, strictly before the bake)
    detects exactly that case -- the mission-branch write path (the common
    case) never touches ``target_branch``, so this is a proven no-op there.

    When the tip moved, ``run.target_baseline_sha`` is re-anchored to the new
    tip so ``_target_branch_still_at_baseline`` keeps measuring the
    mission→target step's OWN progress, not this bookkeeping commit. Undoing
    the bake commit itself on a failure is the driver's rollback door (#5385).
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
        run.target_baseline_sha = current_tip


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


def _switch_write_checkout_after_single_branch_landing(run: _MergeRunState) -> None:
    """WP08/IC-05: back to target_branch before teardown (protected single_branch only; see lanes.single_branch_landing)."""
    from specify_cli.lanes.single_branch_landing import lands_mission_branch, switch_checkout_to_target

    # Gate on the STORED single_branch topology + meta.mission_branch, never on
    # manifest ``mission_branch != target_branch`` (true for every lanes mission).
    if not _is_coord_topology_mission(run) and lands_mission_branch(run.main_repo, run.lanes_manifest):
        switch_checkout_to_target(run.main_repo, run.lanes_manifest.mission_branch, run.lanes_manifest.target_branch)
