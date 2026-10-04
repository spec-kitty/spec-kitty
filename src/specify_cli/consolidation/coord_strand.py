"""Coordination-strand primitive: mark, heal and byte-restore (FR-005/FR-006/FR-008).

Captures the coordination tip and the ``done`` write-set before the pre-target
``done`` bake, records a stranded committed ``done`` as a reconcile marker, heals
it on resume start (only the driver calls the heal), and byte-restores
bookkeeping through :func:`_restore_and_guard_coord_coherence`. Ref undo is never
done here: that is the driver's single rollback door (#5385).

Moved from ``consolidation/executor.py`` by epic #2026 with no logic change.
"""

from __future__ import annotations

from pathlib import Path

from rich.markup import escape

from specify_cli.cli.console import console
from specify_cli.coordination.atomic_write import (
    restore_generated_artifact_snapshots,
)
from specify_cli.coordination.coherence import (
    CoordRepairOutcome,
    coord_incoherent_done_wps,
    repair_coord_strand,
    status_log_commits_in_range,
)
from specify_cli.coordination.surface_resolver import (
    is_under_worktrees_segment,
)
from kernel.clock import now_utc_iso

from specify_cli.consolidation.bookkeeping_projection import (
    _target_branch_still_at_baseline,
)
from specify_cli.consolidation.state import (
    STRAND_SHAS_KEY,
    marker_strand_shas,
    save_state,
)
from mission_runtime import (
    MissionArtifactKind,
    placement_seam,
)
from specify_cli.consolidation.run_state import (
    _MergeRunState,
    _capture_coord_checkpoint,
    _records_post_mutation_tips,
)


def _capture_pre_target_coord_ref_sha(run: _MergeRunState) -> None:
    """Capture the coordination-branch ref + tip SHA BEFORE the pre-target
    ``done`` emit (#2711 / FR-006).

    The captured tip anchors the strand marker
    (:func:`_persist_coord_reconcile_marker`) and the ``done`` write-set. A
    placement that cannot be resolved (a non-coord topology, or a legacy
    mission) leaves both fields ``None``, which makes both a proven no-op.
    Delegates checkpoint resolution to :func:`_capture_coord_checkpoint`.
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
    feature_dir = _coord_reconcile_read_feature_dir(run)
    stranded = coord_incoherent_done_wps(
        coord_ref,
        run.pre_target_done_write_set,
        repo_root=run.main_repo,
        feature_dir=feature_dir,
    )
    if not stranded:
        return
    marker: dict[str, object] = {
        "coord_ref": coord_ref,
        "captured_sha": captured_sha,
        "coord_worktree": str(coord_worktree),
        "stranded_wp_ids": list(stranded),
        "revert_error": str(error) if error is not None else None,
        "detected_at": now_utc_iso(),
    }
    # #5572: record the strand's OWN commits now. Every marker write runs after the
    # done bake and before anything else lands on the coordination branch under this
    # run's lock, so the status-log commits in ``captured_sha..coord_ref`` are exactly
    # this run's strand. The heal reverts only these. When git cannot enumerate the
    # range the key is left out: the marker then reads as legacy and the heal refuses
    # (fail closed) instead of guessing.
    strand_shas = status_log_commits_in_range(run.main_repo, captured_sha, coord_ref, feature_dir)
    if strand_shas is not None:
        marker[STRAND_SHAS_KEY] = strand_shas
    run.state.pending_coord_reconcile = marker
    save_state(run.state, run.main_repo)


def _report_refused_strand_heal(outcome: CoordRepairOutcome) -> None:
    """Say plainly that a resume-start heal did NOT revert the stranded ``done`` (#5572).

    The marker is kept (the caller clears it only on a genuine heal), so the strand is
    still visible to ``doctor coordination``, which carries the manual-reconcile steps.
    """
    if outcome.legacy_marker:
        reason = (
            "the reconcile marker recorded no strand commits (written by an older release, or the range was "
            "unreadable when it was written), so the strand cannot be told apart from later work"
        )
    elif outcome.foreign_status_commits:
        foreign = ", ".join(sha[:10] for sha in outcome.foreign_status_commits)
        reason = f"the status log holds commits the marker did not record (foreign: {foreign}), e.g. a later reopen"
    else:
        reason = "the status log no longer matches the commits the marker recorded"
    console.print(
        "[yellow]Warning:[/yellow] the stranded coordination `done` was NOT reverted: "
        f"{escape(reason)}. The reconcile marker is kept. Reconcile the coordination status log "
        "manually; see `spec-kitty doctor coordination`. This resume continues and, unless the "
        "coordination branch is retained, will tear down the coordination branch at the end, "
        "so the stranded commit does not ship."
    )


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
        strand_shas=marker_strand_shas(marker),
    )
    if outcome.legacy_marker or outcome.strand_mismatch:
        _report_refused_strand_heal(outcome)
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
    coord-topology rollback it records any residual strand (mark-not-raise). Off the
    coord path (``done_marked_before_target`` False) it is a pure byte-restore.

    It never heals: the heal is a forward ``git revert`` and would commit inside the
    rollback span (#5385). The driver's rollback door restores the coordination
    branch (and clears the marker after a full restore); the resume-start heal in the
    driver is the only heal caller. The recorder decorator stays because the byte
    restore can rewrite ``state.json``; the recorder re-saves the in-memory record.
    """
    restore_generated_artifact_snapshots(snapshots)
    if not run.done_marked_before_target:
        return
    _persist_coord_reconcile_marker(run, error)


def _restore_pre_target_if_at_baseline(run: _MergeRunState) -> None:
    """Restore the pre-target working-tree bookkeeping iff the target never advanced (INV-6).

    Restores ONLY when done events were recorded pre-target AND the target branch
    still points at the pre-merge baseline -- i.e. the mission→target merge made
    no progress. Byte restore + strand marker only: every ref undo (the committed
    coordination ``done``, an orphan primary-tree bake commit on the target) is
    the driver's single rollback door (#5385). ``run.target_baseline_sha`` is the
    re-anchored baseline (:func:`_reanchor_baseline_past_primary_tree_bake`), so
    this guard measures the mission→target step's own progress.
    """
    still_at_baseline = _target_branch_still_at_baseline(
        run.main_repo,
        run.lanes_manifest.target_branch,
        run.target_baseline_sha,
    )
    if run.done_marked_before_target and still_at_baseline:
        _restore_and_guard_coord_coherence(run, run.pre_target_bookkeeping_snapshots)
