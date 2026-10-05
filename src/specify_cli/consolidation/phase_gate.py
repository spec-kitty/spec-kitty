"""Reconciliation gate: verify the landed target before any teardown (S-D, FR-001/FR-002).

Builds the strategy-appropriate claim, runs :class:`MergeOutcomeVerifier`, refuses a
PASS over a target that moved during verification, runs the SQUASH
projected-content proof, then records the PASS anchor (the verified tip), and on FAIL/REFUSE
exits non-zero WITHOUT moving any ref: the driver's single rollback door (#5385)
restores the target (FR-010, #5666). The resume short-circuit for an
already-verified landing (#5021) lives here too.

Moved from ``consolidation/executor.py`` by epic #2026 with no logic change.
"""

from __future__ import annotations

from dataclasses import replace

import typer
from rich.markup import escape

from specify_cli.cli.console import console
from kernel.git import GitCommandError
from specify_cli.consolidation.bookkeeping_projection import (
    _post_checkpoint_mission_paths,
    _resolve_ref_sha,
    projected_content_matches_target,
)
from specify_cli.consolidation.config import MergeStrategy
from specify_cli.consolidation.git_probes import GitProbeError
from specify_cli.consolidation.reconciliation import (
    ApprovedWpCommitSet,
    MergeOutcomeVerifier,
    VerifyResult,
    build_approved_wp_set,
    lane_tips_moved_refusal,
    route_terminus,
)
from specify_cli.consolidation.state import (
    save_state,
)
from specify_cli.consolidation.run_state import (
    _CONSOLIDATE_ABORT_COMMAND,
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


def _record_reconciliation_pass(run: _MergeRunState, verified_sha: str | None) -> None:
    """Persist the CAS anchor proving reconciliation PASSed for ``verified_sha``.

    ``verified_sha`` is the target tip read BEFORE ``verify()`` ran (F3), never a
    fresh read after it, and the caller persists it only once the squash
    projection proof passed too. Enables
    :func:`_resume_reconciliation_already_passed` to recognize a
    completed-but-mid-teardown resume without re-running the content axis
    against a possibly torn-down lane's now-partial ``authored_blobs`` claim
    (#5021 r1). A no-op when the target ref could not be resolved (nothing safe
    to anchor).
    """
    if not verified_sha:
        return
    run.state.reconciliation_passed_target_sha = verified_sha
    save_state(run.state, run.main_repo)


def _refuse_target_moved_during_verification(run: _MergeRunState, verified_sha: str | None) -> None:
    """F3: a PASS over a target that moved while ``verify()`` ran proves nothing about the live tip; refuse.

    The ``typer.Exit(1)`` lands in the driver's rollback door, which keeps the
    commit that landed meanwhile (the target is reported NOT restored) and
    restores the other branches; no PASS anchor is written.
    """
    live = _resolve_ref_sha(run.main_repo, run.lanes_manifest.target_branch)
    if live == verified_sha:
        return
    target = run.lanes_manifest.target_branch
    run.reconciliation_result = VerifyResult.refused(f"target {target} moved while reconciliation was verifying it")
    console.print(
        f"\n[red]Error:[/red] Reconciliation refused (fail-closed): the target {escape(target)} moved while reconciliation "
        f"was verifying it ({(verified_sha or 'unresolved')[:10]} -> {(live or 'unresolved')[:10]}), so the PASS does not cover "
        f"its current tip. {_NOTHING_TORN_DOWN}."
    )
    _print_moved_target_next_steps(run, target, live)
    raise typer.Exit(1)


def _print_moved_target_next_steps(run: _MergeRunState, target: str, live: str | None) -> None:
    """Non-destructive next steps after a target moved during verification (C-002).

    The door leaves the target NOT restored and unsettled at a tip the record
    cannot explain, so a plain ``--resume`` refuses with ``UNEXPLAINED_BRANCH_MOVE``
    until the operator releases or moves that commit.
    """
    restore_target = run.state.restore_targets.get(target, run.state.pre_mutation_refs.get(target, ""))
    lines = (
        "To continue:",
        f"  - inspect the new commit on {target}: git log {restore_target}..{live or target}",
        f'  - keep it and clear the record: {_CONSOLIDATE_ABORT_COMMAND} --release-branch {target} --release-reason "<why>"',
        "  - a `spec-kitty consolidate --resume` will refuse with UNEXPLAINED_BRANCH_MOVE until that commit is released or moved.",
    )
    for line in lines:
        console.print(line, markup=False, soft_wrap=True)


def _phase_reconcile_before_teardown(run: _MergeRunState) -> None:
    """S-D gate: verify the merge outcome by tree reachability BEFORE any teardown.

    terminus-merge-integrity WP06 (FR-001/FR-002; NFR-005). Runs strictly between
    ``_phase_commit_and_assert`` and cleanup. On FAIL/REFUSE it refuses (non-zero
    exit) with recovery guidance, tears down NOTHING and moves NO ref: the
    ``typer.Exit(1)`` it raises lands in the driver's single rollback door, which
    restores the target (FR-010, #5666); on PASS it continues to cleanup. The
    success message is scoped to **approved-WP commit reachability** (NOT verdict integrity — #4941 out of
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
    # F3: the anchor is exactly the tip verify() judged, read before it ran.
    verified_sha = _resolve_ref_sha(run.main_repo, run.lanes_manifest.target_branch)
    result = _lane_recheck_verdict(run, claim)
    if result is None:
        result = MergeOutcomeVerifier(run.main_repo).verify(run.lanes_manifest.target_branch, claim)
    run.reconciliation_result = result
    if result.is_pass:
        _refuse_target_moved_during_verification(run, verified_sha)
        _assert_squash_projected_content_landed(run)
        # P3: checked again right before the anchor, so a move during the
        # projection proof is never anchored as verified either.
        _refuse_target_moved_during_verification(run, verified_sha)
        # F3: persisted only after the projection proof passed, so a projection
        # refusal never leaves this run's PASS anchor on disk.
        _record_reconciliation_pass(run, verified_sha)
        console.print(_reconciliation_pass_message(run.strategy))
        return
    console.print(f"\n[red]Error:[/red] {escape(result.recovery_guidance())}", soft_wrap=True)
    # FR-010 (operator decision 01M3MAB8FTDKKVVTXPREK75AEP, "Rollback on REFUSE
    # only") still holds: the mission->target advance already landed before this
    # gate, so EVERY non-PASS verdict (a proven FAIL or a fail-closed REFUSE)
    # leaves the target on a state this gate did not prove sound, and the target
    # must be rolled back. The gate itself moves nothing (#5666). The
    # ``typer.Exit(1)`` below lands inside the driver's single rollback door
    # (#5385, ``executor._run_lane_based_consolidation_locked``), whose
    # ``rollback_to_snapshot`` compare-and-swaps each branch against the post tip
    # THIS run recorded. A commit another actor landed on top of the landing is
    # therefore kept and reported NOT restored, never discarded; with no foreign
    # commit the target is restored to its pre-consolidation snapshot and its
    # checkouts are resynced. NO teardown runs (branches/worktrees are retained
    # for inspection: the ordering guarantee).
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


def _squash_projected_paths_or_refuse(run: _MergeRunState, checkpoint_sha: str, coord_ref: str) -> tuple[str, ...]:
    """Return the projected bookkeeping paths the squash content proof must check.

    Guard (FR-013): an unreadable coord window must never escape as a raw
    traceback past the gate's refusal vocabulary (the PASS anchor is persisted
    only after this proof passes, F3, so none is left behind either way). A
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
