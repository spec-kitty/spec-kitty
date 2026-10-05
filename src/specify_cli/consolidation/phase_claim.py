"""Pre-mutation phase: merge-ready gates, resume anchors and the reconciliation claim.

Everything here runs before the first ref moves: the merge-ready precondition and
merge gates, the persisted resume anchors (read-persisted-first target/coord tips,
pre-interrupt lane tips, executed strategy), the fresh-record clearing guard
(#5111), and :func:`_capture_reconciliation_claim`, which refuses a claim that fails
integrity before any mutation (#5338) and captures the pre-mutation snapshot once.

Moved from ``consolidation/executor.py`` by epic #2026 with no logic change.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path
from typing import NoReturn

import typer
from rich.markup import escape

from specify_cli.cli.console import console
from specify_cli.core.git_ops import run_command

# Shared FR-004/FR-009 "fully canceled" predicate and lane-branch composer
# (single canonical home in ``lanes.compute`` — see its docstrings), imported
# under the historical private names this module's call sites use.
from specify_cli.lanes.compute import lane_created_branch as _created_lane_branch
from specify_cli.lanes.compute import lane_fully_canceled as _lane_fully_canceled
from specify_cli.consolidation._constants import (
    logger,
)
from specify_cli.consolidation.config import MergeStrategy
from specify_cli.consolidation.git_probes import (
    GitProbeError,
    resolve_commit,
)
from specify_cli.consolidation.preflight import (
    _enforce_canonical_status_history,
    _warn_or_confirm_hollow_reviews,
)
from specify_cli.consolidation import rollback
from specify_cli.consolidation.entry_preflight import _REFUSED_WITH_EARLIER_RECORD
from specify_cli.consolidation.reconciliation import (
    build_approved_wp_set,
    claim_integrity_refusal,
    detect_legacy_in_flight_state,
    write_post_fix_marker,
)
from specify_cli.consolidation.state import (
    ConsolidationState,
    clear_state,
    lane_tip_cas_ok,
    save_state,
)
from specify_cli.consolidation.run_state import (
    _resume_reconciliation_already_passed,
    _CONSOLIDATE_ABORT_AND_RESTART_HINT,
    _CONSOLIDATE_ABORT_COMMAND,
    _MergeRunState,
    _NOTHING_TORN_DOWN,
    _capture_coord_checkpoint,
    _stored_topology_for,
)


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


def _planning_only_notice(run: _MergeRunState) -> str | None:
    """The banner for a run that skips branch-merge steps (#5100 B6), else ``None``.

    A single_branch mission has ONE repo-root lane so ``planning_artifact_only``
    reads True even for a code mission; calling it planning-artifact-only was
    false. Say what is actually true for that topology instead.
    """
    if not run.planning_artifact_only:
        return None
    from mission_runtime import is_single_branch

    if is_single_branch(_stored_topology_for(run.target_feature_dir)):
        return "  [dim]single_branch mission: work is committed on the write checkout; no lane branches to merge or delete.[/dim]"
    return "  [dim]Planning-artifact-only mission: target branch already contains deliverables; branch merge steps will be skipped.[/dim]"


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
    notice = _planning_only_notice(run)
    if notice is not None:
        console.print(notice)

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
    persisted: str | None = state.pre_mutation_target_sha
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

    run.validated_lane_tips = dict(run.approved_wp_set.bound_lane_tips)
    run.bound_anchor_shas = _bound_anchor_shas(run, coord_base)

    # #5338: act on a claim-integrity refusal HERE, before the first mutating
    # phase, instead of storing it for the post-mutation gate. A resume whose
    # reconciliation already PASSed for the current target tip (#5021) is exempt:
    # its lane branches may legitimately be gone already.
    refusal = claim_integrity_refusal(run.approved_wp_set)
    if refusal is not None and not _resume_reconciliation_already_passed(run):
        _exit_on_claim_integrity_refusal(
            refusal,
            attested=run.recorded_attestations,
            earlier_moved=_branches_moved_by_earlier_attempts(run),
            target_branch=run.lanes_manifest.target_branch,
        )

    # #5318 / #5332: snapshot every branch this attempt may move, strictly before
    # the first mutating phase, and fix this attempt's restore targets.
    _capture_snapshot_and_begin_attempt(run)


def _bound_anchor_shas(run: _MergeRunState, coord_base: str) -> tuple[str, ...]:
    """The mission branch, the target and the coordination base as SHAs now, for the gate's lane re-check (#5668).

    Captured before any mutation: at gate time the live mission branch already holds every
    merged lane commit, so a branch name would exempt the very commit the re-check looks
    for. A reference that does not resolve is left out, which exempts less and so only refuses more.
    """
    shas: list[str] = []
    for ref in (run.lanes_manifest.mission_branch, run.target_expected_old_sha, coord_base):
        if not ref:
            continue
        try:
            sha = resolve_commit(run.main_repo, ref)
        except GitProbeError:
            continue
        if sha not in shas:
            shas.append(sha)
    return tuple(shas)


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


def _branches_moved_by_earlier_attempts(run: _MergeRunState) -> tuple[str, ...]:
    """The branches an earlier attempt of this consolidation recorded moving; empty on a fresh run (#5668).

    A ``--resume`` carries the persisted record's post-mutation tips: each is a branch the
    interrupted run advanced, so a claim-time refusal of the resume does not mean nothing moved.
    """
    return tuple(sorted(run.state.post_mutation_refs)) if run.is_resume else ()


def _claim_refusal_footer(attested: tuple[str, ...], earlier_moved: tuple[str, ...], target_branch: str) -> str:
    """The closing sentences of a claim-time refusal: a fresh run changed nothing; a resume leads with ``--abort`` (#5668).

    A resume refused after an earlier attempt already advanced the target leaves that
    content on the local target, so the text starts from the restore command (the same
    sentence an up-front protected-target refusal of a resume prints) and says so.
    """
    if not earlier_moved:
        return (
            f"{_claim_refusal_change_sentence(attested)} Fix the cause, then re-run; "
            f"if an earlier attempt left partial state, run `{_CONSOLIDATE_ABORT_COMMAND}` first."
        )
    holds = f" (the local target '{target_branch}' currently holds content from it)" if target_branch in earlier_moved else ""
    recorded = f" Only the operator attestation(s) for {', '.join(attested)} were recorded by this run." if attested else ""
    return f"{_REFUSED_WITH_EARLIER_RECORD} That attempt already moved {', '.join(earlier_moved)}{holds}.{recorded} Then fix the cause and re-run."


def _exit_on_claim_integrity_refusal(
    refusal: str,
    *,
    attested: tuple[str, ...] = (),
    earlier_moved: tuple[str, ...] = (),
    target_branch: str = "",
) -> NoReturn:
    """Abort before any mutation because the approved-WP claim failed integrity (#5338).

    Runs strictly pre-mutation (inside ``_clear_fresh_record_on_pre_mutation_exit``),
    so no branch or worktree was changed by this run. ``--attest-canceled-superseded``
    writes its status events BEFORE the claim (FR-012); when this run recorded any
    (``attested``), the text says so instead of claiming no status record changed.
    A resume refused after an earlier attempt moved branches (``earlier_moved``) says to
    abort first (:func:`_claim_refusal_footer`).
    The verdict leads with the same ``Reconciliation refused (fail-closed)``
    header the teardown gate prints (#5359), so operators and tooling see one
    REFUSE vocabulary whether the claim refuses early or the gate refuses late.
    """
    # A multi-line refusal ends on a recovery line: the footer starts its own line. The text is escaped (a path may
    # hold ``[id]``) and printed unwrapped, so a recovery command stays on one copyable line.
    footer_separator = "\n" if "\n" in refusal else " "
    before_any_change = "" if earlier_moved else ", before any change"
    console.print(
        f"\n[red]Error:[/red] Reconciliation refused (fail-closed) at claim time{before_any_change}: {escape(refusal.rstrip('.'))}."
        f"{footer_separator}{escape(_claim_refusal_footer(attested, earlier_moved, target_branch))}",
        soft_wrap=True,
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
