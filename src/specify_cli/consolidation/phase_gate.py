"""Reconciliation gate: verify the landed target before any teardown (S-D, FR-001/FR-002).

Builds the strategy-appropriate claim, runs :class:`MergeOutcomeVerifier`, records
the PASS anchor, runs the SQUASH projected-content proof, and on FAIL/REFUSE
restores the target to its pre-mutation tip (FR-010) and exits non-zero. The
resume short-circuit for an already-verified landing (#5021) lives here too.

Moved from ``consolidation/executor.py`` by epic #2026 with no logic change.
"""

from __future__ import annotations

from dataclasses import replace

import typer
from rich.markup import escape

from specify_cli.cli.console import console
from kernel.git import GitCommandError
from specify_cli.git.ref_advance import (
    RefRestoreError,
    restore_branch_ref,
)

from specify_cli.consolidation.bookkeeping_projection import (
    _post_checkpoint_mission_paths,
    _resolve_ref_sha,
    projected_content_matches_target,
)
from specify_cli.consolidation.config import MergeStrategy
from specify_cli.consolidation.git_probes import (
    GitProbeError,
    _refresh_primary_checkout_after_merge,
)
from specify_cli.consolidation.reconciliation import (
    ApprovedWpCommitSet,
    MergeOutcomeVerifier,
    VerifyResult,
    VerifyStatus,
    build_approved_wp_set,
    lane_tips_moved_refusal,
    route_terminus,
)
from specify_cli.consolidation.state import (
    save_state,
)
from specify_cli.consolidation.run_state import (
    _MergeRunState,
    _NOTHING_TORN_DOWN,
    _resume_reconciliation_already_passed,
)


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


def _lane_recheck_verdict(run: _MergeRunState, claim: ApprovedWpCommitSet) -> VerifyResult | None:
    """Refusal when content reached an approved lane after the claim-time check validated it, else ``None`` (#5668).

    The lane tips and anchor SHAs were captured before this run mutated anything
    (``phase_claim``); a live branch name would not do, because every lane was merged
    into the mission branch with a no-ff merge and the live mission branch therefore
    reaches the very commit this looks for. A probe error is a REFUSE, as the
    verifier reports one.
    """
    approved_by_lane = {lane.lane_id: [wp for wp in lane.wp_ids if wp in claim.approved] for lane in run.lanes_manifest.lanes}
    try:
        refusal = lane_tips_moved_refusal(
            run.main_repo,
            run.lanes_manifest,
            validated_tips=run.validated_lane_tips,
            anchor_shas=run.bound_anchor_shas,
            planning_prefix=claim.planning_prefix,
            approved_wp_ids=approved_by_lane,
        )
    except GitProbeError as exc:
        return VerifyResult.refused(f"a git probe failed while re-checking the lane tips against their approval: {exc}")
    return VerifyResult.refused(refusal) if refusal is not None else None


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
    result = _lane_recheck_verdict(run, claim)
    if result is None:
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


def _squash_projected_paths_or_refuse(run: _MergeRunState, checkpoint_sha: str, coord_ref: str) -> tuple[str, ...]:
    """Return the projected bookkeeping paths the squash content proof must check.

    Guard (FR-013): an unreadable coord window must never escape as a traceback
    AFTER the reconciliation PASS anchor was saved — that would skip the
    caller's rollback and leave a PASS anchor a later ``--abort`` trusts. A
    :class:`~kernel.git.GitCommandError` is converted into the same refusal
    (message + ``typer.Exit(1)``) as a content-proof REFUSE, so the caller's
    ``_report_rollback`` runs exactly as it does for that REFUSE.
    """
    try:
        return tuple(_post_checkpoint_mission_paths(run.main_repo, run.mission_slug, checkpoint_sha, coord_ref))
    except GitCommandError as exc:
        console.print(
            "\n[red]Error:[/red] SQUASH reconciliation refused: the projected "
            f"coordination bookkeeping window could not be read ({escape(str(exc))}). "
            f"{_NOTHING_TORN_DOWN}; re-run `spec-kitty consolidate --resume`."
        )
        raise typer.Exit(1) from exc


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
    projected_paths = _squash_projected_paths_or_refuse(run, checkpoint.sha, checkpoint.ref)
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
