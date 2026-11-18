"""Merge preflight checks for target branch safety.

Mission #2057 (decompose ``cli/commands/merge.py``) — IC-05 / WP05 relocated the
git / target-branch / mission-branch / canonical-status / review-artifact /
hollow-review preflights here (the historical home of the target-sync
remediation). One-way import: this module never imports the command shim.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer

from kernel.git import GitCommandError, GitPath
from kernel.git import changed_paths as git_changed_paths
from kernel.git import index_entries, status_entries
from kernel.git_topology import GitTopologyError, git_common_dir

from specify_cli.version_utils import cli_version
from specify_cli.cli.console import console
from specify_cli.coordination.coherence import is_coordination_kind_file
from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.core.env import is_interactive
from specify_cli.core.git_ops import run_command
from specify_cli.core.git_preflight import (
    build_git_preflight_failure_payload,
    run_git_preflight,
)
from specify_cli.consolidation._constants import (
    HollowReviewWarnings,
    MissionBranchBlocker,
    _STATUS_EVENTS_FILENAME,
    _STATUS_FILENAME,
)
from specify_cli.git.ref_advance import reset_would_obstruct_untracked
from specify_cli.consolidation.approved_bound import is_approved_reviewed_attestation
from specify_cli.consolidation.no_implementation_attestation import is_no_implementation_attestation
from specify_cli.consolidation.git_probes import _has_branch_ref, _lane_already_integrated, sha_reachable_from
from specify_cli.consolidation.state import ConsolidationStateReadError, load_state
from specify_cli.post_merge.review_artifact_consistency import (
    format_review_artifact_finding,
    review_artifact_finding_diagnostic,
    run_review_artifact_consistency_preflight,
)
from specify_cli.missions._read_path_resolver import mission_dir_aliases
from specify_cli.status import (
    GENERIC_IMPLEMENTATION_ACTORS,
    REVIEWER_SELF_APPROVAL,
    _actor_key,
    actor_full_identity,
    actor_identities_independent,
    build_system_actor,
    is_migration_actor,
    latest_implementer_identity,
    read_events_lenient,
)

if TYPE_CHECKING:
    from specify_cli.consolidation.push_preflight import TargetBranchSyncStatus
    from specify_cli.coordination.types import Refused
    from specify_cli.consolidation.state import ConsolidationState
    from specify_cli.lanes.models import LanesManifest
    from specify_cli.status.models import StatusEvent
    from specify_cli.post_merge.review_artifact_consistency import (
        ReviewArtifactFinding,
    )

_DONE_LANE = "done"

_PUSH_PREFLIGHT_EXPORTS = {
    "TargetBranchRefreshStatus",
    "TargetBranchSyncState",
    "TargetBranchSyncStatus",
    "inspect_target_branch_sync",
    "refresh_target_branch_tracking_ref",
}


def __getattr__(name: str) -> Any:
    """Lazily expose moved publish-layer symbols for transition compatibility."""
    if name in _PUSH_PREFLIGHT_EXPORTS:
        from specify_cli.consolidation import push_preflight

        return getattr(push_preflight, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def focused_pr_branch_name(mission_slug: str, target_branch: str) -> str:
    """Return a deterministic branch name for non-destructive recovery."""
    safe_target = target_branch.replace("/", "-")
    return f"kitty/pr/{mission_slug}-to-{safe_target}"


def target_branch_sync_remediation(
    status: TargetBranchSyncStatus,
    *,
    mission_slug: str | None,
    mission_branch: str | None = None,
    mission_id: str | None = None,
) -> list[str]:
    """Build actionable, non-destructive remediation diagnostics.

    The focused-PR recovery source branch prefers the recorded
    ``mission_branch`` (``lanes.json.mission_branch``) verbatim. When it is
    absent the canonical branch is composed via the fail-closed WP01 seam
    :func:`mission_branch_name_required`, NOT a bare ``kitty/mission-<slug>``
    f-string that drops the ``-<mid8>`` disambiguator / keeps a stale ``NNN-``
    prefix and so names a never-created branch (#1978).
    """
    tracking_branch = status.tracking_branch or f"origin/{status.target_branch}"
    lines = [
        (
            f"Local target branch '{status.target_branch}' is {status.state} "
            f"relative to '{tracking_branch}' "
            f"({status.ahead_count} ahead, {status.behind_count} behind)."
        ),
        "Spec Kitty stopped before mutating merge state or reconstructing branches.",
        f"Refresh remote refs: git fetch origin {status.target_branch}",
        (f"Inspect differences: git log --oneline --left-right --cherry-pick {status.target_branch}...{tracking_branch}"),
        (f"Inspect changed paths: git diff --name-only {tracking_branch}...{status.target_branch}"),
    ]

    if status.state in {"ahead", "diverged"}:
        lines.extend(
            [
                (f"Recommended: use the focused PR path unless you verified every ahead commit belongs on '{status.target_branch}' now."),
                (
                    f"Do not run 'git push origin {status.target_branch}' just to satisfy "
                    "this preflight; local target commits may include orchestration history "
                    "or unrelated missions."
                ),
                (f"Only direct-push '{status.target_branch}' after reviewing the ahead commits and changed paths."),
            ]
        )
    elif status.state == "behind":
        lines.append(
            f"Recommended: update local '{status.target_branch}' from '{tracking_branch}' after reviewing remote-only commits; do not push the local target branch."
        )

    if mission_slug:
        lines.extend(_focused_pr_remediation_lines(mission_slug, mission_branch, mission_id, status.target_branch))
    else:
        lines.append("If local-only commits are intentional, preserve them on a new PR branch before retrying.")

    lines.append("Do not use reset, rebase, or force-push as part of this preflight remediation.")
    return lines


def _focused_pr_remediation_lines(
    mission_slug: str,
    mission_branch: str | None,
    mission_id: str | None,
    target_branch: str,
) -> list[str]:
    """Build the focused-PR recovery lines, degrading gracefully on unresolvable identity.

    FR-011: the recorded ``lanes.json.mission_branch`` always wins verbatim.
    When it is absent the canonical branch is composed via the fail-closed
    seam :func:`mission_branch_name_required`. An *absent* identity on a
    modern slug raises :class:`BranchIdentityUnresolved`, which propagates
    unchanged (its remedy, ``migrate backfill-identity``, is correct there).
    Only a *present-but-invalid* ``mission_id`` (the typed subclass
    :class:`InvalidMissionIdentity`, raised at the source in ``_mid8``)
    degrades to advisory text, because this diagnostics builder's contract
    returns remediation text rather than crashing and that case needs a
    hand edit that no command performs.
    """
    from specify_cli.lanes.branch_naming import InvalidMissionIdentity, mission_branch_name_required

    focused_branch = focused_pr_branch_name(mission_slug, target_branch)
    source_branch = mission_branch
    if source_branch is None:
        try:
            source_branch = mission_branch_name_required(mission_slug, mission_id)
        except InvalidMissionIdentity:
            source_branch = None

    if source_branch is None:
        return [
            (
                f"Could not resolve a canonical source branch for mission {mission_slug!r} "
                f"(mission_id={mission_id!r} is too short to derive a mid8 disambiguator). "
                "`spec-kitty doctor identity --json` only AUDITS mission-identity "
                "health -- it does not mint or repair a value, and neither does "
                "`spec-kitty migrate backfill-identity` (it only mints a mission_id "
                "when one is absent; a present-but-invalid value is left as-is). "
                "Correct mission_id in the mission's meta.json by hand, confirm with "
                "`spec-kitty doctor identity --json`, then retry the focused-PR path."
            )
        ]
    return [
        f"Focused PR path: git switch -c {focused_branch} {source_branch}",
        f"Then push it: git push -u origin {focused_branch}",
        f"Open a PR from {focused_branch} into {target_branch}.",
    ]


def _check_mission_branch(
    mission_slug: str,
    repo_root: Path,
    *,
    expected_branch: str | None = None,
    mission_id: str | None = None,
) -> tuple[bool, MissionBranchBlocker | None]:
    """Check whether the expected mission branch exists locally.

    Dry-run and real merge both use this as a read-only preflight. Missing
    branches are reported as structured blockers; this function never creates
    the branch.

    When ``expected_branch`` is not supplied (no recorded
    ``lanes.json.mission_branch``), the branch to CHECK is RESOLVED via the WP01
    seam :func:`resolve_branch_name` — the canonical-first / legacy-failover
    resolver (FR-004) — rather than a bare ``kitty/mission-<slug>`` f-string. The
    f-string drops the ``-<mid8>`` disambiguator and never strips a stale ``NNN-``
    prefix, so it mis-targeted the never-created branch and falsely reported it
    missing (#1978). ``resolve_branch_name`` keeps that #1978 fix intact for
    canonical/embedded slugs (no warning), failovers to the legacy ``NNN-`` branch
    with a one-shot deprecation warning, and still raises
    :class:`BranchIdentityUnresolved` for a genuinely-unresolvable modern slug,
    or its typed subclass :class:`InvalidMissionIdentity` (raised at the source
    in ``_mid8``, #5108 residual) for a present-but-too-short ``mission_id`` —
    no local conversion shim needed; both are already the typed, fail-closed
    refusal this function's callers expect (never a raw ``ValueError``).
    """
    from specify_cli.lanes.branch_naming import resolve_branch_name

    if expected_branch is None:
        expected_branch = resolve_branch_name(mission_slug, mission_id=mission_id)
    if _has_branch_ref(repo_root, expected_branch):
        return True, None

    blocker_payload: MissionBranchBlocker = {
        "ready": False,
        "blocker": "missing_mission_branch",
        "expected_branch": expected_branch,
        "remediation": _missing_mission_branch_remediation(repo_root, expected_branch),
    }
    return False, blocker_payload


def _missing_mission_branch_remediation(repo_root: Path, expected_branch: str) -> str:
    """How to recreate a missing Mission branch, preferring its last recorded tip.

    A deleted coordination or Mission branch must come back at the commit it last pointed
    at. Its recorded lane-tip ref (``refs/spec-kitty/lane-tip/<branch>``) restores exactly
    that; otherwise the reflog still holds it. Recreating the branch at the repository
    root's HEAD is offered only as a last resort, because HEAD may not hold the Mission's
    work.
    """
    from specify_cli.lanes.lane_tip import tip_ref

    recorded = tip_ref(expected_branch)
    retcode, _stdout, _stderr = run_command(
        ["git", "rev-parse", "--verify", "--quiet", recorded],
        capture=True,
        check_return=False,
        cwd=repo_root,
    )
    if retcode == 0:
        return f"git branch {expected_branch} {recorded}"
    retcode, stdout, _stderr = run_command(
        ["git", "rev-parse", "HEAD"],
        capture=True,
        check_return=False,
        cwd=repo_root,
    )
    base_sha = stdout.strip()[:12] if retcode == 0 else "<base-commit>"
    return (
        f"git branch {expected_branch} <last-tip-sha> (find its last tip with `git reflog`; "
        f"recreate it at the current HEAD, {base_sha}, only as a last resort: HEAD may not hold the Mission's work)"
    )


def mission_branch_check_required(
    main_repo: Path,
    manifest: LanesManifest,
    existing_state: ConsolidationState | None,
) -> bool:
    """Whether consolidation must find the recorded Mission branch before it starts.

    The ONE predicate the real run (``executor``) and the dry-run forecast share, so a
    forecast never refuses a run that would proceed (#7267). The check is skipped when:

    * the manifest is planning-artifact-only and does not land a Mission branch — a
      planning-only manifest records a ``mission_branch`` that is never created; the run
      writes straight to the target instead; or
    * a resume finds cleanup already started after a verified landing — the Mission branch
      was torn down with the coordination triple and only cleanup is left (S5 FR-035).
    """
    from specify_cli.consolidation.run_state import landing_verified_for_resume
    from specify_cli.lanes.compute import is_planning_artifact_only
    from specify_cli.lanes.single_branch_landing import lands_mission_branch

    if is_planning_artifact_only(manifest) and not lands_mission_branch(main_repo, manifest):
        return False
    resuming_cleanup = existing_state is not None and existing_state.cleanup_started
    return not (resuming_cleanup and landing_verified_for_resume(main_repo, existing_state))


def _enforce_planning_artifact_target_branch(repo_root: Path, target_branch: str) -> None:
    """Planning-only closeout writes directly to the target branch."""

    retcode, stdout, _stderr = run_command(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture=True,
        check_return=False,
        cwd=repo_root,
    )
    current_branch = stdout.strip() if retcode == 0 else ""
    if current_branch == target_branch:
        return

    current_label = current_branch or "detached HEAD"
    console.print(f"[red]Error:[/red] Planning-artifact-only merge must run on target branch {target_branch}, not {current_label}.")
    raise typer.Exit(1)


def _enforce_git_preflight(repo_root: Path, *, json_output: bool) -> None:
    """Run git preflight checks and stop early with deterministic remediation."""
    if not (repo_root / ".git").exists():
        return

    preflight = run_git_preflight(repo_root, check_worktree_list=True)
    if preflight.passed:
        return

    payload = build_git_preflight_failure_payload(preflight, command_name="spec-kitty consolidate")
    if json_output:
        enriched = dict(payload)
        enriched["spec_kitty_version"] = cli_version()
        print(json.dumps(enriched))
    else:
        console.print(f"[red]Error:[/red] {payload['error']}")
        # ``payload`` is a heterogeneous ``dict[str, object]`` (the JSON-shaped
        # failure payload). Read the remediation entry from it — the contract is
        # that the human channel mirrors the payload — and narrow the erased
        # ``object`` value with an ``isinstance`` guard so it type-checks as an
        # iterable without a cast or ``# type: ignore``.
        remediation = payload.get("remediation")
        if isinstance(remediation, list):
            for cmd in remediation:
                console.print(f"  - Run: {cmd}")
    raise typer.Exit(1)


def _validate_target_branch(
    repo_root: Path,
    mission_slug: str | None,
    target_branch: str,
    target_source: str | None,
    *,
    json_output: bool,
) -> None:
    ret_local, _, _ = run_command(
        ["git", "rev-parse", "--verify", f"refs/heads/{target_branch}"],
        capture=True,
        check_return=False,
        cwd=repo_root,
    )
    if ret_local == 0:
        return

    ret_remote, _, _ = run_command(
        ["git", "rev-parse", "--verify", f"refs/remotes/origin/{target_branch}"],
        capture=True,
        check_return=False,
        cwd=repo_root,
    )
    if ret_remote == 0:
        return

    if target_source == "meta.json" and mission_slug:
        error_msg = f"Target branch '{target_branch}' (from meta.json) does not exist locally or on origin. Check kitty-specs/{mission_slug}/meta.json."
    elif target_source == "primary_branch" and mission_slug:
        error_msg = f"Target branch '{target_branch}' (resolved as primary branch) does not exist locally or on origin. Check kitty-specs/{mission_slug}/meta.json."
    else:
        error_msg = f"Target branch '{target_branch}' does not exist locally or on origin."

    if json_output:
        print(json.dumps({"spec_kitty_version": cli_version(), "error": error_msg}))
    else:
        console.print(f"[red]Error:[/red] {error_msg}")
    raise typer.Exit(1)


def _effective_push_requested(
    repo_root: Path,
    mission_id: str,
    requested_push: bool,
) -> bool:
    """Return persisted push intent for resumptions, otherwise current CLI intent."""
    state = load_state(repo_root, mission_id)
    if state is not None:
        return bool(state.push_requested)
    return requested_push


def _enforce_canonical_status_history(
    *,
    feature_dir: Path,
    mission_slug: str,
    wp_ids: list[str],
) -> None:
    """Refuse to merge missions whose canonical status log is bootstrap-only.

    A bootstrap-only log is a ``status.events.jsonl`` that contains
    nothing but forced ``planned -> planned`` entries emitted by
    ``finalize-tasks``. When the mission carries work packages that
    must have advanced past planned for merge to make sense, the log
    is an unreliable source of truth and downstream replay (TeamSpace
    rebuild, dashboard refresh) will reset every WP to planned. We
    fail loudly with a remediation hint rather than ship in that
    state. See https://github.com/Priivacy-ai/spec-kitty/issues/1069.
    """
    from specify_cli.status import has_non_bootstrap_status_history

    if not wp_ids:
        return

    log_path = feature_dir / _STATUS_EVENTS_FILENAME
    if not log_path.exists():
        return

    if has_non_bootstrap_status_history(feature_dir):
        return

    console.print(
        "[red]Error:[/red] Canonical status history is bootstrap-only — the local "
        "event log cannot prove that WPs advanced past planned, so a merge would "
        "ship a mission whose downstream replay would regress every WP."
    )
    console.print(f"  Mission: {mission_slug}")
    console.print(f"  Event log: {log_path}")
    console.print(f"  Work packages requiring history: {', '.join(wp_ids)}")
    console.print(
        "  Remediation: re-run the per-WP `spec-kitty agent action review` and "
        "`spec-kitty agent action implement` flows so the canonical event log "
        "captures the real lane transitions before merging, or run the "
        "repair/replay tooling for this mission."
    )
    raise typer.Exit(1)


def _record_review_artifact_skip_evidence(
    *,
    repo_root: Path,
    feature_dir: Path,
    mission_slug: str,
    findings: list[ReviewArtifactFinding],
    note: str,
) -> None:
    """Record a ``--skip-review-artifact-check`` bypass as durable evidence.

    WP01 (#2959) escape hatch: an operator skip is NEVER silent. For every WP the
    gate would have blocked, emit a complete :class:`ReviewOverride` carrying the
    operator ``note`` as the reason into the append-only status log — the SAME
    override annotation the gate honors, so the bypass is auditable exactly like an
    ordinary review override. ``feature_dir`` here is already the coord-aware
    ``STATUS_STATE`` surface the merge flow resolved, so the override lands where
    the gate reads it (the partition-correctness this WP also fixes on the write
    side of :func:`_persist_review_artifact_override`).
    """
    from kernel.clock import now_utc_stamp

    from specify_cli.coordination.status_transition import (
        emit_inner_state_changed_transactional,
    )
    from specify_cli.consolidation.done_bookkeeping import _resolve_merge_actor
    from specify_cli.status import ReviewOverride, WPInnerStateDelta

    actor = _resolve_merge_actor(repo_root)
    timestamp = now_utc_stamp()
    console.print("[yellow]⚠️  Review-artifact consistency gate BYPASSED via --skip-review-artifact-check.[/yellow]")
    console.print(f"    Reason (recorded as override evidence): {note}")
    for finding in findings:
        wp_id = finding.wp_id
        console.print(f"    - {wp_id}: skip recorded as override evidence")
        # #2959 durability (squad architect-alphonso): the escape hatch advertises
        # "durable override evidence", so the skip record must be COMMITTED, not
        # merely written. The gate runs at a clean preflight point BEFORE any
        # merge-state or branch-integration git mutation, so committing the coord
        # STATUS surface here is safe. Use the commit-durable sibling
        # (emit_inner_state_changed_transactional, the same #2939 seam a lane hop
        # uses): on coord it rides a BookkeepingTransaction committed on the
        # coordination ref, so the evidence survives even if the merge aborts
        # downstream; on a stored LANES or SINGLE_BRANCH mission (no distinct
        # coordination ref) it commits on the write branch instead (#5655);
        # only a flat/legacy mission with no stored topology delegates to the
        # untouched partition-agnostic emit (no-op parity).
        # #6722: the event's actor is the structured system actor; the override's own
        # four-field slot keeps the plain operator identity (its shape is pinned).
        emit_inner_state_changed_transactional(
            feature_dir,
            wp_id,
            WPInnerStateDelta(review=ReviewOverride(at=timestamp, actor=actor, wp_id=wp_id, reason=note)),
            actor=build_system_actor(actor),
            mission_slug=mission_slug,
            at=timestamp,
            repo_root=repo_root,
        )


def _enforce_review_artifact_consistency(
    *,
    repo_root: Path,
    feature_dir: Path,
    mission_slug: str,
    wp_ids: list[str],
    skip_review_artifact_check: bool = False,
    skip_note: str | None = None,
) -> None:
    """Block terminal signoff when the latest review artifact is rejected.

    FR-001 (WP07/T030, traced not assumed): this function consumes
    ``run_review_artifact_consistency_preflight``'s ``ReviewArtifactPreflightResult``
    opaquely (``.passed`` / ``.findings`` / the diagnostic dicts it renders below)
    and performs no independent frontmatter re-parse of its own. The event-sourced
    ``review_result`` reducer slot T029 wired into the gate therefore reaches this
    call site automatically — no additional code change is needed here.

    WP01 (#2959) escape hatch: when ``skip_review_artifact_check`` is set the gate
    does NOT raise. Instead the skip is recorded as durable ``ReviewOverride``
    evidence (:func:`_record_review_artifact_skip_evidence`) carrying ``skip_note``
    — a bypass that is auditable, never silent. ``skip_note`` is guaranteed
    non-empty by the CLI boundary; the belt-and-suspenders fallback below keeps the
    evidence honest if a programmatic caller forgets it.
    """
    preflight = run_review_artifact_consistency_preflight(feature_dir, wp_ids=wp_ids)
    if preflight.passed:
        return
    findings = list(preflight.findings)

    if skip_review_artifact_check:
        _record_review_artifact_skip_evidence(
            repo_root=repo_root,
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            findings=findings,
            note=(skip_note or "").strip() or "review-artifact gate skipped via --skip-review-artifact-check",
        )
        return

    console.print("[red]Error:[/red] Review artifact consistency gate failed.")
    for finding in findings:
        diagnostic = review_artifact_finding_diagnostic(
            finding,
            repo_root=repo_root,
        )
        console.print(f"  - {format_review_artifact_finding(finding, repo_root=repo_root)}")
        console.print(f"    diagnostic_code: {diagnostic['diagnostic_code']}")
        console.print(f"    branch_or_work_package: {diagnostic['branch_or_work_package']}")
        console.print(f"    violated_invariant: {diagnostic['violated_invariant']}")
        console.print(f"    latest_review_cycle_path: {diagnostic['latest_review_cycle_path']}")
        if "latest_review_cycle_verdict" in diagnostic:
            console.print(f"    latest_review_cycle_verdict: {diagnostic['latest_review_cycle_verdict']}")
        if "schema_error" in diagnostic:
            console.print(f"    schema_error: {diagnostic['schema_error']}")
        remediation = diagnostic.get("remediation", [])
        if not isinstance(remediation, list):
            remediation = [str(remediation)]
        for line in remediation:
            console.print(f"    remediation: {line}")
    console.print(f"  Mission: {mission_slug}")
    raise typer.Exit(1)


def _latest_actor_for_transition(feature_dir: Path, wp_id: str, to_lane: str) -> str | None:
    """Return the full identity of the actor on WP's latest transition into *to_lane*.

    "Latest" is **append order** of the log, not the wall-clock ``(at, event_id)`` maximum.
    ADR ``2026-02-09-3`` Amendment 2026-10-22 records the ordering the reducer applies: wall
    clock, the writer's ``at`` then ``event_id``, with the #4941 approved-departure lift, so
    a skewed clock does not let an approval outrank the departure that followed it. A lane
    ``StatusEvent`` still carries no logical clock to sort on, and the lift only repairs
    departures from ``approved``; a non-approval transition minted on a clock behind the
    event it follows would sort before it. This function needs the sequence the log itself
    records, so the append-only log's own order is the causal order available here; it is
    also the order ``review_roles.latest_implementer_event`` reads, so the implementer and the
    approving reviewer of one WP are projected from the same sequence.

    Reads the event log rather than the reduced snapshot, because the
    snapshot's ``actor`` slot is overwritten on every transition -- it can
    only ever tell us who did the LATEST transition of any kind, never who
    specifically claimed/implemented versus who specifically approved.
    Returns ``None`` when the log is absent/unreadable or no matching,
    actor-bearing transition exists for this WP. An operator attestation of an
    approval (``--attest-approved-reviewed``, #5668) is a forced ``approved ->
    approved`` record, not a review, so it is never the approving transition;
    neither is a no-implementation attestation (``--attest-no-implementation``,
    #6715), which only lifts ``IMPLEMENTATION_MISSING``.
    A migration seed (#6257) is never the actor of record either: a
    ``verdict_provenance_backfill`` seed into ``approved`` restates a verdict, it
    is not a review. A generic placeholder actor (``GENERIC_IMPLEMENTATION_ACTORS``
    through ``_actor_key``, the projection the implementer side uses, #6715) names
    nobody: when the latest matching transition carries one, the actor is unknown
    (``None``), so a move recorded as ``user`` is never an independent review. So is a
    matching transition whose actor carries no identity at all (blank): the latest
    approval decides, and an older reviewer never stands in for it (#6715 squad fold).
    """
    latest: str | None = None
    for event in read_events_lenient(feature_dir):
        if event.wp_id != wp_id or not _enters_lane(event, to_lane):
            continue
        if _is_operator_attestation(event.policy_metadata) or is_migration_actor(event.actor):
            continue
        if _actor_key(event.actor) in GENERIC_IMPLEMENTATION_ACTORS:
            # #6715: a generic placeholder (``user``, ``unknown``, ...) names no actor, so the
            # latest such transition leaves the actor of record unknown, never an earlier one.
            latest = None
            continue
        latest = actor_full_identity(event.actor)
    return latest


def _enters_lane(event: StatusEvent, to_lane: str) -> bool:
    """True when *event* moves into *to_lane*; an unforced ``in_review -> done`` also enters ``approved``.

    That hop records the review verdict and the landing in one move, so the approval bound
    already reads it as an approval (#5668); the approving-actor read does the same (#6715).
    """
    if str(event.to_lane) == to_lane:
        return True
    review_to_done: bool = str(event.from_lane) == "in_review" and str(event.to_lane) == "done" and not event.force
    return to_lane == "approved" and review_to_done


def _is_operator_attestation(policy_metadata: dict[str, Any] | None) -> bool:
    """True for an operator attestation that is never a review (approved-reviewed, #5668; no-implementation, #6715)."""
    attested: bool = is_approved_reviewed_attestation(policy_metadata) or is_no_implementation_attestation(policy_metadata)
    return attested


def _latest_implementer_identity(feature_dir: Path, wp_id: str) -> str | None:
    """Full recorded identity of the WP's implementer of record (#5340).

    Delegates to the one projection in ``status.review_roles`` (a reviewer's
    rework verdict is not an implementation claim; the implementer's own
    ``for_review`` submissions refine the claim, #7159) and keeps the full-identity
    string, not the tool-scoped key, so same-tool/different-profile pairs stay
    distinct.
    """
    identity: str | None = latest_implementer_identity(read_events_lenient(feature_dir), wp_id)
    return identity


def _independent_reviewer_confirmed(feature_dir: Path, wp_id: str) -> bool:
    """True when WP's latest approval actor provably differs from its
    latest implementation actor (#2412-adjacent field report, item #9).

    ``force_count`` alone cannot distinguish "reviewer used --force to bypass
    an unrelated gate false-positive" from "no independent review happened" --
    both increment the same counter. This checks the one thing that actually
    answers the question: did a different identity log the approving
    transition than the one that most recently claimed/implemented the WP?
    Returns False (never suppress) when either actor is missing/unknown --
    absence of evidence is not evidence of an independent review. The two
    identities compare segment-wise (:func:`~specify_cli.status.actor_identities_independent`,
    operator ruling R1, #6715): a model or profile recorded on one side only
    never proves they differ.
    """
    implementer = _latest_implementer_identity(feature_dir, wp_id)
    reviewer = _latest_actor_for_transition(feature_dir, wp_id, "approved")
    independent: bool = actor_identities_independent(implementer, reviewer)
    return independent


def _review_force_counts(feature_dir: Path, wp_set: set[str]) -> dict[str, int]:
    """Count forced review transitions per WP in the event log (#2267).

    ``move-task --to planned --force --review-feedback-file`` is the standard
    rejection path and a review claim is a forced ``for_review -> in_progress``
    move, so both raise the reducer's ``force_count``. Those transitions are
    evidence of review, not of its absence. A no-implementation attestation
    (#6715) is a forced operator self-transition that says nothing about the
    review, so it is discounted too. Lines are deduped by ``event_id`` as the reducer dedupes them;
    an absent or unreadable log yields no discount (fail toward warning).
    """
    from specify_cli.review.rejection_signal import is_documented_review_rejection, is_review_claim

    events_path = feature_dir / _STATUS_EVENTS_FILENAME
    try:
        raw_lines = events_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    seen: set[str] = set()
    counts: dict[str, int] = {}
    for raw_line in raw_lines:
        try:
            event = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict) or not event.get("force") or event.get("wp_id") not in wp_set:
            continue
        event_id = str(event.get("event_id") or "")
        if (event_id and event_id in seen) or not _is_discounted_force(event, is_documented_review_rejection, is_review_claim):
            continue
        seen.add(event_id)
        counts[event["wp_id"]] = counts.get(event["wp_id"], 0) + 1
    return counts


def _is_discounted_force(event: dict[str, Any], *predicates: Callable[[dict[str, Any]], bool]) -> bool:
    """True when a forced event is a review signal (*predicates*) or a no-implementation attestation (#6715)."""
    metadata = event.get("policy_metadata")
    if is_no_implementation_attestation(metadata if isinstance(metadata, dict) else None):
        return True
    return any(predicate(event) for predicate in predicates)


def _collect_force_count_warnings(
    feature_dir: Path,
    wp_set: set[str],
    warnings: HollowReviewWarnings,
) -> None:
    """Append force_count>=2 warnings from ``status.json`` (WP05 split helper).

    Behavior-preserving extraction of the status-snapshot scan formerly inlined
    in ``_collect_hollow_review_warnings`` (FR-005, keeps CC <= 15) -- plus two
    additive guards. Item #9: a WP whose approving actor is positively
    confirmed distinct from its implementing actor is not a hollow review,
    even with a high force_count. #2267: forced documented review rejections
    and review claims are discounted, so the count reflects only undocumented
    forcing.
    """
    status_path = feature_dir / _STATUS_FILENAME
    if not status_path.exists():
        return
    try:
        status = json.loads(status_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        status = {}
    work_packages = status.get("work_packages", {}) if isinstance(status, dict) else {}
    if not isinstance(work_packages, dict):
        return
    discounts = _review_force_counts(feature_dir, wp_set)
    for wp_id in sorted(wp_set):
        wp_state = work_packages.get(wp_id, {})
        if not isinstance(wp_state, dict):
            continue
        try:
            force_count = int(wp_state.get("force_count", 0))
        except (TypeError, ValueError):
            force_count = 0
        force_count = max(force_count - discounts.get(wp_id, 0), 0)
        if force_count >= 2 and not _independent_reviewer_confirmed(feature_dir, wp_id):
            warnings.setdefault(wp_id, []).append(f"force_count={force_count}")


def _collect_self_approval_warnings(
    feature_dir: Path,
    wp_set: set[str],
    warnings: HollowReviewWarnings,
) -> None:
    """Append ReviewerSelfApproval warnings from the event log (WP05 split helper).

    Behavior-preserving extraction of the event-log scan formerly inlined in
    ``_collect_hollow_review_warnings`` (FR-005, keeps CC <= 15).
    """
    events_path = feature_dir / _STATUS_EVENTS_FILENAME
    if not events_path.exists():
        return
    try:
        raw_lines = events_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        raw_lines = []
    for raw_line in raw_lines:
        try:
            event = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict) or event.get("event_type") != REVIEWER_SELF_APPROVAL:
            continue
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue
        wp_id = str(payload.get("wp_id") or "")
        if wp_id not in wp_set:
            continue
        intended = str(payload.get("intended_reviewer") or "unknown")
        actor = str(payload.get("implementing_actor") or "unknown")
        reason = str(payload.get("failure_reason") or "reviewer_failed")
        warnings.setdefault(wp_id, []).append(f"ReviewerSelfApproval ({intended} failed: {reason}; {actor} self-reviewed)")


def _collect_hollow_review_warnings(feature_dir: Path, wp_ids: list[str]) -> HollowReviewWarnings:
    """Return WPs whose approval history indicates missing independent review.

    Delegates to two focused scans (status-snapshot force_count + event-log
    ReviewerSelfApproval). The split keeps each helper <= 15 CC (FR-005) while
    preserving the exact warning buckets and emission order.
    """
    warnings: HollowReviewWarnings = {}
    wp_set = set(wp_ids)
    _collect_force_count_warnings(feature_dir, wp_set, warnings)
    _collect_self_approval_warnings(feature_dir, wp_set, warnings)
    return warnings


def _warn_or_confirm_hollow_reviews(
    *,
    feature_dir: Path,
    wp_ids: list[str],
    assume_yes: bool,
) -> None:
    warnings = _collect_hollow_review_warnings(feature_dir, wp_ids)
    if not warnings:
        return

    console.print("\n[bold yellow]MERGE WARNING: Hollow reviews detected[/bold yellow]\n")
    console.print("The following WPs were approved without clear independent review:")
    for wp_id in sorted(warnings):
        console.print(f"  {wp_id}: {' + '.join(warnings[wp_id])}")
    console.print()
    console.print("These WPs may have been approved by the implementing agent, not an independent reviewer.")
    console.print("Consider re-reviewing before merge.\n")

    if assume_yes or not is_interactive():
        console.print("[yellow]Proceeding without interactive confirmation.[/yellow]")
        return

    if not typer.confirm("Proceed?", default=False):
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Behind-own-HEAD resume remedy classifier (FR-011, traces #4982 / #4997)
# ---------------------------------------------------------------------------
#
# After an interrupted terminus the ``update-ref`` that advanced the target and
# the ``reset --hard`` that refreshes the checkout are two UNLINKED steps
# (DEBRIEF §2 R1). When the second never runs, the primary checkout is merely
# *behind its own HEAD*: the lane's already-merged files read as staged
# deletions / "local changes". Advising the operator to "Commit" them stages a
# new commit that REVERTS the integrated merge — resume then skips the lane as
# integrated and the target lands without the WP's code while every WP is marked
# done and the command exits 0. The classifier below distinguishes that state
# from a genuinely dirty checkout via a read-only ancestry probe, so the remedy
# is fast-forward/reset-to-HEAD recovery, never the merge-reverting commit.

_RESUME_HINT = "Then re-run: spec-kitty consolidate --resume"
_ABORT_COMMAND = "spec-kitty consolidate --abort"


class ResumeRemedyKind(Enum):
    """Classification of a dirty resume checkout's underlying cause."""

    BEHIND_OWN_HEAD = "behind_own_head"
    LOCAL_CHANGES = "local_changes"
    BLOCKED_INDEX_LOCK = "blocked_index_lock"


@dataclass(frozen=True)
class ResumeDirtyRemedy:
    """A classified dirty-resume state paired with its safe recovery remedy."""

    kind: ResumeRemedyKind
    remediation: list[str]


def _index_lock_path(repo_root: Path) -> Path | None:
    """Return the checkout's ``index.lock`` path (worktree-aware), or ``None``.

    Uses ``git rev-parse --git-path`` so linked worktrees resolve to their
    per-worktree index lock rather than the shared repo's.
    """
    retcode, stdout, _stderr = run_command(
        ["git", "rev-parse", "--git-path", "index.lock"],
        capture=True,
        check_return=False,
        cwd=repo_root,
    )
    if retcode != 0:
        return None
    raw = stdout.strip()
    if not raw:
        return None
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    return candidate


def _reset_blocked_by_index_lock(repo_root: Path) -> bool:
    """True when an ``index.lock`` shows a ``reset --hard`` blocked mid-transaction."""
    lock = _index_lock_path(repo_root)
    return lock is not None and lock.exists()


def _is_behind_own_head(repo_root: Path, lane_branch: str, head_ref: str) -> bool:
    """True when ``lane_branch``'s commits are already reachable from ``head_ref``.

    Delegates to the read-only ancestry probe in
    :mod:`specify_cli.consolidation.git_probes` (WP06 owns that module; it is consumed
    here without modification, C-004). When the lane is already an ancestor of
    the checkout's own recorded HEAD, a dirty worktree is explained by the
    checkout lagging its already-advanced HEAD — the interrupted-terminus
    behind-own-HEAD state — rather than by genuine local work. The decision is
    made by ancestry, NOT a file-name heuristic.
    """
    return bool(_lane_already_integrated(repo_root, lane_branch, head_ref))


def classify_resume_dirty_remedy(
    repo_root: Path,
    *,
    lane_branch: str,
    head_ref: str = "HEAD",
) -> ResumeDirtyRemedy:
    """Classify a dirty resume checkout and return its safe recovery remedy.

    Call this when the resume/merge preflight has already found the checkout
    dirty; it decides *why* and returns the remedy the operator should follow.

    Precedence (each an O(1) probe, NFR-003):

    1. ``BLOCKED_INDEX_LOCK`` — an ``index.lock`` indicates a ``reset --hard``
       was interrupted mid-transaction, so the checkout state is unknown. This
       is surfaced first so it is never misread as a clean or committable state.
    2. ``BEHIND_OWN_HEAD`` — ``lane_branch`` is already an ancestor of
       ``head_ref`` (the merge advanced HEAD but the checkout was never
       refreshed). The remedy fast-forwards the checkout to HEAD and NEVER
       advises committing, which would revert the already-integrated lane.
    3. ``LOCAL_CHANGES`` — the lane is not yet in HEAD, so the dirty entries are
       genuine local work; the normal commit/stash/revert remedy is safe and no
       merge is reverted by preserving them.
    """
    if _reset_blocked_by_index_lock(repo_root):
        lock_display = _index_lock_path(repo_root) or (repo_root / ".git" / "index.lock")
        return ResumeDirtyRemedy(
            kind=ResumeRemedyKind.BLOCKED_INDEX_LOCK,
            remediation=[
                f"A git index.lock is present ({lock_display}) — a reset --hard was interrupted mid-transaction, so the checkout state is unknown.",
                f"Confirm no other git process is running, then remove the stale lock before retrying: rm {lock_display}",
                _RESUME_HINT,
            ],
        )

    if _is_behind_own_head(repo_root, lane_branch, head_ref):
        return ResumeDirtyRemedy(
            kind=ResumeRemedyKind.BEHIND_OWN_HEAD,
            remediation=[
                "The working checkout is behind its own HEAD: the lane's "
                "already-merged files read as local changes because a prior terminus "
                "advanced the target ref but the reset --hard that refreshes the "
                "checkout never ran.",
                "Do NOT stage or record these changes — they are the integrated lane "
                "read in reverse; recording them reverts the merge and drops the WP's "
                "code from the target.",
                f"Fast-forward the checkout to its own HEAD: git -C {repo_root} reset --hard HEAD",
                _RESUME_HINT,
            ],
        )

    return ResumeDirtyRemedy(
        kind=ResumeRemedyKind.LOCAL_CHANGES,
        remediation=[
            f"Commit, stash, or revert the local changes in {repo_root} before "
            "retrying — the lane is not yet integrated into HEAD, so nothing is "
            "reverted by preserving them.",
            _RESUME_HINT,
        ],
    )


def head_is_strictly_ahead_of(repo_root: Path, base_sha: str | None) -> bool:
    """True iff ``base_sha`` is a STRICT ancestor of ``repo_root``'s ``HEAD`` (the ref advanced past it).

    Fail-closed ``False`` on a missing ``base_sha``, ``base_sha == HEAD`` (no lag) or any
    git error. The shared first step of :func:`is_pure_behind_head_lag` and
    :func:`has_unrefreshed_head_advance`.
    """
    if not base_sha:
        return False
    head_ret, head_sha, _head_err = run_command(
        ["git", "rev-parse", "HEAD"],
        capture=True,
        check_return=False,
        cwd=repo_root,
    )
    if head_ret != 0 or head_sha.strip() == base_sha:
        return False
    return bool(sha_reachable_from(repo_root, base_sha, "HEAD"))


def _diff_paths(repo_root: Path, *revs: str) -> set[GitPath]:
    """Paths ``git diff <revs>`` reports in ``repo_root`` (``set()`` on any git error)."""
    try:
        return set(git_changed_paths(repo_root, *revs))
    except GitCommandError:
        return set()


def has_unrefreshed_head_advance(repo_root: Path, *, base_sha: str | None) -> bool:
    """True iff ``repo_root`` still reads the ``base_sha`` -> ``HEAD`` advance in reverse (#5571).

    ``HEAD`` is a strict descendant of ``base_sha`` AND at least one path the advance
    changed (``base_sha..HEAD``) still differs between the checkout (index or working
    tree) and ``HEAD`` — i.e. recording the checkout as-is would revert the advance.

    This is the *advisory* sibling of :func:`is_pure_behind_head_lag`: it does NOT prove the
    dirt is purely that lag (a genuine edit may be mixed in), so it never authorises a
    reset; it only tells the refusal report to stop advising "commit". A checkout dirty
    only on paths the advance never touched is genuine local work and stays ``False``
    (the stock remedy is then safe). ``False`` on a missing ``base_sha`` or any git error
    (fail-closed toward the stock remedy).
    """
    if not head_is_strictly_ahead_of(repo_root, base_sha):
        return False
    advanced_paths = _diff_paths(repo_root, str(base_sha), "HEAD")
    return bool(advanced_paths & _diff_paths(repo_root, "HEAD"))


def checked_out_branch(checkout: Path) -> str | None:
    """The branch *checkout* has checked out, or ``None`` (detached HEAD, not a checkout, missing directory)."""
    if not checkout.is_dir():
        return None
    ret, out, _err = run_command(["git", "symbolic-ref", "--short", "-q", "HEAD"], capture=True, check_return=False, cwd=checkout)
    return (out.strip() or None) if ret == 0 else None


def _resume_edit_patch_path(checkout: Path) -> Path:
    """Where the operator saves their edit: the repository's COMMON git dir, which survives a worktree removal.

    The file name carries a checksum of the checkout's full path, so two worktrees that share a
    directory name never write the same patch. When git cannot name the common dir the patch
    goes beside the checkout, never under ``<checkout>/.git`` (a file in a linked worktree).
    """
    resolved = checkout.resolve()
    digest = f"{zlib.crc32(str(resolved).encode('utf-8', 'surrogateescape')):08x}"
    try:
        directory = git_common_dir(resolved)
    except GitTopologyError:
        directory = resolved.parent
    return directory / f"spec-kitty-resume-edit-{checkout.name}-{digest}.patch"


#: The two ``XY`` codes ``git status`` prints for a tracked file deleted in the working tree (`` D``) or staged for deletion (``D ``).
_DELETION_CODES = (" D", "D ")


def _is_deleted_coordination_file(entry: str, *, composed_prefix: str) -> bool:
    """True when *entry* (a rendered ``XY path`` line) deletes a coordination-kind file under *composed_prefix*.

    ``StatusEntry.display`` renders ``<X><Y> <path>`` and says never to parse it back for data; this reads
    it only to RECOGNISE a state, and any entry it cannot read with certainty (a rename, a quoted
    or escaped path) is not recognised, which keeps the stock remedy.
    """
    if entry[:2] not in _DELETION_CODES or entry[2:3] != " ":
        return False
    path = entry[3:]
    return path.startswith(composed_prefix) and is_coordination_kind_file(path[len(composed_prefix) :])


def _is_primary_fold_projection(entry: str, *, primary_prefix: str) -> bool:
    """True when *entry* modifies/adds the fold's OWN projection to the PRIMARY Mission directory.

    A kill inside the one-directory fold leaves, besides the composed-directory deletions, the
    fold's half-written projection to the primary directory in the working tree: its ``meta.json``
    (the baseline / mission-number bake) and its coordination-kind status pair, modified or added
    but not yet committed. Those are the fold's own uncommitted work, not genuine local changes, so
    they do not disqualify the interrupted-fold recognition. A DELETION under the primary directory,
    a rename, a modification OUTSIDE it, or a non-projection file is NOT this (kept to ``None``).
    """
    code = entry[:2]
    if entry[2:3] != " " or code in ("??", "!!") or "D" in code or "R" in code or not ("M" in code or "A" in code):
        return False
    path = entry[3:]
    if not path.startswith(primary_prefix):
        return False
    tail = path[len(primary_prefix) :]
    return tail == "meta.json" or is_coordination_kind_file(tail)


def interrupted_alias_fold_guidance(dirty_entries: list[str], *, main_repo: Path, mission_slug: str) -> list[str] | None:
    """Advice for a root checkout that an interrupted one-directory fold left dirty (#5748), else ``None``.

    The fold of a bare-slug coordination Mission (``bookkeeping_projection.coordination_alias_files``,
    run by ``phase_bookkeeping._fold_alias_directory``) writes its projection to the primary Mission
    directory (``meta.json`` plus the coordination-kind status pair) and unlinks the composed
    ``<slug>-<mid8>`` directory's coordination-kind files (the status pair, traces, matrices, the
    decision log, review cycles), then commits the removal. A run killed before that commit leaves,
    in the repository root checkout, those composed-directory deletions AND the fold's half-written
    primary-directory projection; the landed Mission is already on the target. Recording, stashing or
    restoring them does not let ``--resume`` complete, whereas rolling the interrupted run back with
    ``consolidate --abort`` and starting fresh does.

    Recognition is exact. The composed name comes from
    :func:`~specify_cli.missions._read_path_resolver.mission_dir_aliases` (the Mission's recorded
    identity, never a guess from the slug). At least one entry must be the deletion, unstaged or
    staged, of a coordination-kind file under the composed directory
    (:func:`~specify_cli.coordination.coherence.is_coordination_kind_file`, the predicate the fold
    itself uses), and every remaining entry must be either another such composed-directory deletion
    or the fold's own primary-directory projection (:func:`_is_primary_fold_projection`). Anything
    else (a file outside the Mission's directories, a composed-directory modification, a
    primary-directory deletion, an untracked file, a Mission with no composed directory, no entry at
    all) is genuine local work and keeps the stock remedy: ``None``.
    """
    composed = mission_dir_aliases(main_repo, mission_slug) - {mission_slug}
    if len(composed) != 1:
        return None
    (composed_name,) = composed
    composed_prefix = f"{KITTY_SPECS_DIR}/{composed_name}/"
    primary_prefix = f"{KITTY_SPECS_DIR}/{mission_slug}/"
    composed_deletions = [entry for entry in dirty_entries if _is_deleted_coordination_file(entry, composed_prefix=composed_prefix)]
    if not composed_deletions or not all(
        _is_deleted_coordination_file(entry, composed_prefix=composed_prefix) or _is_primary_fold_projection(entry, primary_prefix=primary_prefix)
        for entry in dirty_entries
    ):
        return None
    return [
        f"An earlier consolidation of {mission_slug} was interrupted while folding the composed directory {KITTY_SPECS_DIR}/{composed_name} "
        "into the primary Mission directory: some of its coordination files are deleted in this checkout, but the commit that records the removal was never made.",
        "Committing, stashing or restoring these deletions does not let a resume complete.",
        f"Roll the interrupted run back: {_ABORT_COMMAND}",
        "Then start the consolidation fresh: spec-kitty consolidate",
    ]


def lag_with_edit_guidance(checkout: Path, *, label: str, base_sha: str) -> list[str]:
    """Advice for a worktree that lags its own HEAD AND carries an operator edit (#5571 / #5613).

    Call only when :func:`has_unrefreshed_head_advance` holds and :func:`is_pure_behind_head_lag`
    does not. Nothing is mutated; the lines are printed by the refusal report.

    The edit is saved as a ``--binary`` patch (a plain diff records a binary edit only as "Binary
    files differ", which the advised ``reset --hard`` would then lose) of ONLY the paths that
    differ from ``base_sha`` (the branch tip before the interrupted run): at the lag the working tree still equals that tip, so those paths
    are the operator's own and never a lane path the lag reads as deleted. Two remedies are ruled
    out by name: recording the checkout (it reverts the integrated lanes) and ``git stash`` (the
    stash is taken against the advanced HEAD, so popping it after the refresh deletes the lane
    files again). The patch is re-applied only AFTER the resume, whose guards refuse a dirty
    worktree and whose refresh would overwrite the edit.
    """
    where = f"git -C {shlex.quote(str(checkout))}"
    patch = shlex.quote(str(_resume_edit_patch_path(checkout)))
    edited = " ".join(shlex.quote(str(path)) for path in sorted(_diff_paths(checkout, base_sha), key=str))
    lines = [
        f"The {label} {checkout} is behind its own HEAD (a prior consolidation advanced its branch but never refreshed this worktree) "
        "AND carries changes of its own.",
        "Do NOT stage or record these changes: the staged deletions are the integrated lanes read in reverse and recording them reverts the merge.",
        "Do NOT use git stash for your edit: popping it after the refresh deletes the lane files again.",
    ]
    if reset_would_obstruct_untracked(checkout, "HEAD"):
        lines.append("Untracked or ignored files sit on paths HEAD tracks and the refresh would overwrite them: move them out of the worktree first.")
    if edited:
        save = f"{where} diff --binary {base_sha} -- {edited} > {patch}"
        lines.append(f"Save your own edits outside the worktree first, as a patch of only the paths you changed: {save}")
    else:
        lines.append("Save your own edits outside the worktree first.")
    lines.append(f"Refresh the worktree to its own HEAD: {where} reset --hard HEAD")
    lines.append(_RESUME_HINT)
    if edited:
        lines.append(f"Only after the resume completes, re-apply your edit (add --3way if a lane changed the same lines): {where} apply {patch}")
        lines.append("If the consolidation removed this worktree, run that git apply in the checkout that now holds those files.")
    else:
        lines.append("Only after the resume completes, re-apply your edits.")
    return lines


def is_pure_behind_head_lag(
    repo_root: Path,
    *,
    base_sha: str | None,
) -> bool:
    """True iff ``repo_root`` is a *provably pure* behind-own-HEAD lag of ``base_sha``.

    #4997. After an interrupted terminus the ``update-ref`` that advanced the target and
    the ``reset --hard`` that refreshes the checkout are two unlinked steps; when the
    second never runs the checkout sits behind its own (already-advanced) HEAD and the
    mission's files read as staged deletions. A ``git reset --hard HEAD`` fully repairs
    that — but ONLY when the checkout carries nothing genuine that the reset would destroy.

    ``BEHIND_OWN_HEAD`` (lane-ancestry, :func:`classify_resume_dirty_remedy`) proves the
    lane is integrated; it proves NOTHING about *what* is dirty. This predicate adds the
    missing content proof so the reset is provably non-destructive (the safety hole a
    lane-ancestry-only gate leaves open):

    * ``base_sha`` (the persisted transaction-start target tip,
      ``ConsolidationState.pre_mutation_target_sha``) must be a STRICT ancestor of ``HEAD`` — the
      ref advanced past it. Equal ⇒ no lag ⇒ the dirt is genuine ⇒ ``False``.
    * the working tree AND the index must be byte-identical to ``base_sha``'s tree
      (``git diff --quiet <base>`` and ``git diff --cached --quiet <base>`` both clean).
      Any genuine edit, or an intentional deletion of a file unrelated to the advance,
      makes the tree differ from ``base_sha`` ⇒ ``False`` (fail-closed): it is preserved,
      never reset away.
    * no UNTRACKED or IGNORED file may obstruct a path the reset would restore. ``git
      diff`` is blind to both, and ``git reset --hard HEAD`` silently OVERWRITES an
      untracked *or ignored* file sitting at a path present in HEAD's tree (a restored
      mission file force-added via ``git add -f`` despite a ``.gitignore`` entry is still
      a path HEAD's tree tracks). This last check closes that hole by delegating to the
      public git-layer seam :func:`specify_cli.git.ref_advance.reset_would_obstruct_untracked`
      (INV-3: the merge layer never reaches into ``ref_advance``'s private helpers); any
      obstructing untracked-or-ignored path ⇒ ``False``.

    Returns ``False`` on a missing ``base_sha`` or any git error (fail-closed): a state
    that cannot be proven a pure lag is treated as genuine local work.
    """
    if not base_sha or not head_is_strictly_ahead_of(repo_root, base_sha):
        return False
    worktree_ret, _wout, _werr = run_command(
        ["git", "diff", "--quiet", base_sha],
        capture=True,
        check_return=False,
        cwd=repo_root,
    )
    if worktree_ret != 0:
        return False
    index_ret, _iout, _ierr = run_command(
        ["git", "diff", "--cached", "--quiet", base_sha],
        capture=True,
        check_return=False,
        cwd=repo_root,
    )
    if index_ret != 0:
        return False
    return not reset_would_obstruct_untracked(repo_root, "HEAD")


def _current_lanes_or_empty(main_repo: Path, mission_slug: str) -> dict[str, str]:
    """``{wp_id: lane}`` reduced from the mission's status surface; ``{}`` when unreadable.

    The same status read door the done bookkeeping and ``acceptably_canceled_wp_ids``
    read. An unreadable surface proves no WP ``done``, so every WP counts as pending
    (the preflight then still asks the policy -- fail toward probing, never skip).
    """
    from specify_cli.coordination.status_service import StatusSurfaceRefUnreadable
    from specify_cli.status import StoreError, reduce
    from specify_cli.status import read_status_events, resolve_status_read

    try:
        snapshot = reduce(read_status_events(resolve_status_read(main_repo, mission_slug)))
    except (FileNotFoundError, StoreError, StatusSurfaceRefUnreadable):
        return {}
    return {wp_id: str(wp.get("lane", "")) for wp_id, wp in snapshot.work_packages.items() if isinstance(wp, dict)}


def pending_done_wp_ids(
    main_repo: Path,
    mission_slug: str,
    lanes_manifest: LanesManifest,
    *,
    excluded_canceled_wp_ids: frozenset[str],
) -> list[str]:
    """The lane WPs the done bookkeeping would still write, in manifest order.

    Mirrors ``_record_merged_wps_done_for_merge``: canceled-with-provenance WPs are
    skipped, and a WP whose current lane is already ``done`` writes nothing.
    """
    lanes = _current_lanes_or_empty(main_repo, mission_slug)
    return [wp_id for lane in lanes_manifest.lanes for wp_id in lane.wp_ids if wp_id not in excluded_canceled_wp_ids and lanes.get(wp_id) != _DONE_LANE]


def refuse_protected_status_target(
    main_repo: Path,
    mission_slug: str,
    lanes_manifest: LanesManifest,
    *,
    excluded_canceled_wp_ids: frozenset[str] | None = None,
    retarget_to: str | None = None,
) -> Refused | None:
    """The workflow-policy refusal the consolidation's ``done`` bookkeeping would hit, else ``None``.

    #5385: a LANES (or mission-branch-less single_branch) mission whose recorded
    target is protected used to squash onto the target and only then fail its
    ``done`` write. This probes that write BEFORE anything moves, through the
    transactional status door's own entry and the transaction's own policy gate
    (:func:`~specify_cli.coordination.status_transition.status_write_refusal`,
    C-001: no second protection rule). The request has the shape
    ``done_bookkeeping._mark_wp_merged_done`` builds; the write target is the
    mission's RECORDED target (meta), never ``--target``.

    ``None`` when no ``done`` write is pending (an all-done resume writes nothing).
    ``excluded_canceled_wp_ids`` defaults to ``acceptably_canceled_wp_ids``.

    ``retarget_to``: a retarget re-points the probe at the new target (#7692); the verdict
    stays the policy's own (C-001). The recorded target is resolved once here, and the door
    swaps it for ``retarget_to`` only where the write would go to it (a coordination-less
    topology); a coordination destination is left alone. The probe is never skipped.
    """
    from mission_runtime import MissionArtifactKind, placement_seam
    from specify_cli.consolidation.done_bookkeeping import MERGE_ACTOR, acceptably_canceled_wp_ids
    from specify_cli.coordination.status_transition import status_write_refusal
    from specify_cli.status import TransitionRequest

    if excluded_canceled_wp_ids is None:
        excluded_canceled_wp_ids = frozenset(acceptably_canceled_wp_ids(main_repo, mission_slug))
    pending = pending_done_wp_ids(main_repo, mission_slug, lanes_manifest, excluded_canceled_wp_ids=excluded_canceled_wp_ids)
    if not pending:
        return None
    request = TransitionRequest(
        feature_dir=placement_seam(main_repo, mission_slug).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK),
        mission_slug=mission_slug,
        wp_id=pending[0],
        to_lane="done",
        actor=build_system_actor(MERGE_ACTOR),
        repo_root=main_repo,
    )
    if retarget_to is None:
        return status_write_refusal(request)
    from specify_cli.core.paths import resolve_merge_target_branch

    recorded_target = resolve_merge_target_branch(main_repo, mission_slug, None)[0]
    return status_write_refusal(request, retarget=(recorded_target, retarget_to))


def refuse_protected_target_override(
    main_repo: Path,
    mission_slug: str,
    *,
    recorded_target: str,
    effective_target: str,
) -> Refused | None:
    """The refusal for a ``--target`` override that would land the Mission on a protected branch, else ``None``.

    #6464: the branch-integration step commits the squashed Mission onto the
    EFFECTIVE target, and that commit is a raw ``git commit`` in an ephemeral
    worktree (:func:`specify_cli.lanes.consolidation._merge_branch_into`), so the
    workflow mutation policy every status commit passes through never sees it. The
    RECORDED target is :func:`refuse_protected_status_target`'s business (#5385);
    this probe owns the RETARGET -- an override naming a branch this project
    protects that is not the Mission's recorded target.

    ``None`` when the two targets agree (restating the recorded target is not a
    retarget) or when the effective target is unprotected, so the decisions #5385
    already makes -- a coordination-topology Mission, an all-done Mission, a
    ``single_branch`` Mission with ``commit_to_target`` -- keep their outcome.

    The decision is :class:`~specify_cli.git.protection_policy.ProtectionPolicy`'s
    own (``is_protected`` -- the resolved ``protection.protected_branches`` set, or its
    ``{main, master} + remote default`` default), which folds the operator hatch and the
    mission-scoped ``commit_to_target`` bypass. It is the SAME set every status write is
    judged against, so there is no second protected-branch list and no second rule here
    (C-002); a repo primary the operator never put on that list is not this guard's call.
    """
    if effective_target == recorded_target:
        return None

    from specify_cli.coordination.types import PROTECTED_BRANCH_REFUSED, Refused
    from specify_cli.git.protection_policy import ProtectionPolicy

    if not ProtectionPolicy.resolve_for_mission(main_repo, mission_slug).is_protected(effective_target):
        return None

    return Refused(
        error_code=PROTECTED_BRANCH_REFUSED,
        message=(
            f"Refusing to land the mission branch on '{effective_target}': "
            f"'--target {effective_target}' overrides the mission's recorded target "
            f"'{recorded_target}', and '{effective_target}' is on this project's protected "
            "branch list. The branch-integration step would commit the squashed mission "
            "straight onto it, outside the protection gate every status commit goes through."
        ),
        destination_ref=effective_target,
        next_step=(
            f"Drop '--target {effective_target}' to consolidate into the mission's recorded "
            f"target '{recorded_target}'; or, if that record is wrong, correct 'target_branch' "
            f"in the mission's meta.json and re-run so the recorded-target policy decides; or "
            f"declare '{effective_target}' unprotected for this repo by setting "
            "SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS to a truthy value. "
            "If the landing belongs on a protected branch, deliver it as a pull request from a "
            "topic branch instead."
        ),
    )


#: #5783: a ``--target`` retarget whose RECORDED target's bookkeeping cannot be committed in this run.
TARGET_OVERRIDE_RECORDED_TARGET_UNWRITABLE = "TARGET_OVERRIDE_RECORDED_TARGET_UNWRITABLE"

#: #7692 FR-011: a ``--retarget`` whose record (``meta.json``) cannot be committed on the new target in this run.
RETARGET_RECORD_UNWRITABLE = "RETARGET_RECORD_UNWRITABLE"

#: #7692: ``--resume --target X --retarget`` naming an X other than the retarget the merge record persisted.
RETARGET_RESUME_MISMATCH = "RETARGET_RESUME_MISMATCH"

#: #7692 C-006: ``--retarget`` of a Mission whose write branch IS its recorded target (a commit-to-target
#: ``single_branch`` Mission): the landing would read the old target as the Mission branch and tear it down.
RETARGET_WRITE_BRANCH_IS_RECORDED_TARGET = "RETARGET_WRITE_BRANCH_IS_RECORDED_TARGET"


def refuse_unwritable_recorded_target(
    main_repo: Path,
    mission_slug: str,
    *,
    recorded_target: str,
    effective_target: str,
) -> Refused | None:
    """The refusal for a ``--target`` retarget whose recorded target cannot be written, else ``None``.

    #5783 (operator ruling 2026-11-16): the branch-integration step lands on the EFFECTIVE
    target, but part of the run's bookkeeping -- the per-WP ``done`` transitions on a
    coordination-less Mission, the coordination flatten, the landed ``mission_branch`` clear --
    resolves its destination from ``meta.json`` and commits to the RECORDED target, in the
    repository root checkout. The write target stays
    the recorded target (adopting ``--target`` as the new record is out of scope), so when
    those commits have no checkout to run in, the run is refused before its first mutation
    instead of landing and then failing (lanes: rollback, exit 1) or landing and leaving the
    bookkeeping uncommitted (coord: the flatten fails open, exit 0).

    ``None`` when the two targets agree (restating the recorded target is not a retarget) or
    when the recorded target's PRIMARY write checkout holds it. The decision is the bookkeeping
    write's own (:func:`~specify_cli.coordination.transaction.write_checkout_refusal`: the
    placement seam's checkout and :meth:`~specify_cli.coordination.transaction.BookkeepingTransaction.acquire`'s
    hold check), never a blanket rule. In the usual shape the repository root checkout must sit
    on the effective target (``MERGE_UNSAFE_PRIMARY_OFF_TARGET``), so it cannot hold the recorded
    one. Read-only and lock-free: no ref, file or merge record is touched.
    """
    if effective_target == recorded_target:
        return None

    from specify_cli.coordination.transaction import write_checkout_refusal
    from specify_cli.coordination.types import Refused

    hold = write_checkout_refusal(main_repo, mission_slug, recorded_target, operation=f"consolidation bookkeeping for {mission_slug}")
    if hold is None:
        return None
    return Refused(
        error_code=TARGET_OVERRIDE_RECORDED_TARGET_UNWRITABLE,
        message=(
            f"Refusing to land the mission branch on '{effective_target}': '--target {effective_target}' "
            f"overrides the mission's recorded target '{recorded_target}', but this run still commits part of "
            f"its bookkeeping (the work packages' done transitions, the coordination flatten) to the recorded "
            f"target '{recorded_target}', and that cannot be committed here. {hold.message}"
        ),
        destination_ref=recorded_target,
        next_step=(
            f"Drop '--target {effective_target}' and consolidate into the recorded target from a checkout "
            f"of it (`git checkout {recorded_target}`); or, if the record is wrong, correct 'target_branch' "
            f"in the mission's meta.json to '{effective_target}', commit it, and re-run without '--target'; "
            f"or, to make '{effective_target}' the mission's new recorded target in this run, re-run "
            f"`spec-kitty consolidate --target {effective_target} --retarget` (CLI only)."
        ),
    )


def _manifest_mission_branch(main_repo: Path, mission_slug: str) -> str | None:
    """The ``mission_branch`` the Mission's ``lanes.json`` names, else ``None`` (absent or corrupt manifest).

    Read through the placement seam (``LANE_STATE`` is a PRIMARY-partition artifact), as the
    forecast does. An unreadable manifest names no Mission branch; the run's own lanes
    preflight reports it.
    """
    from mission_runtime import MissionArtifactKind, placement_seam
    from specify_cli.lanes.persistence import CorruptLanesError, read_lanes_json

    try:
        manifest = read_lanes_json(placement_seam(main_repo, mission_slug).read_dir(MissionArtifactKind.LANE_STATE))
    except CorruptLanesError:
        return None
    return manifest.mission_branch if manifest is not None else None


def _branch_tree_carries(main_repo: Path, branch: str, rel_path: str) -> bool:
    """``True`` when *branch* resolves and its tree carries *rel_path* (``git cat-file -e``)."""
    probe = subprocess.run(
        ["git", "cat-file", "-e", f"refs/heads/{branch}:{rel_path}"],
        cwd=str(main_repo),
        capture_output=True,
    )
    return probe.returncode == 0


def _rel_meta_path(main_repo: Path, mission_slug: str) -> Path:
    from specify_cli.missions._read_path_resolver import compose_meta_json_path

    meta_path: Path = compose_meta_json_path(main_repo, mission_slug)
    return meta_path.relative_to(main_repo)


def retarget_record_holders(main_repo: Path, mission_slug: str, *, mission_branch: str | None, effective_target: str) -> tuple[str, ...]:
    """The branches a retarget record is written on: each of the Mission branch and *effective_target* whose tree carries ``meta.json``.

    #7692 holder rule (plan D4/D10, operator ruling 2026-11-17): the record is written at
    every ``meta.json`` the landing reads. That is the Mission branch when its tree carries
    ``kitty-specs/<slug>/meta.json`` (always for a default-topology Mission, whose record lives
    on its topic branch) and the new target when it carries it (an explicit layout whose target
    was cut after the Mission existed). The ONE owner of that decision: the preflight and the
    retarget phase both read it here. Order: Mission branch first; deduplicated; a missing or
    unresolvable branch carries nothing. Read-only.
    """
    rel_meta = _rel_meta_path(main_repo, mission_slug).as_posix()
    candidates = dict.fromkeys(branch for branch in (mission_branch, effective_target) if branch)
    return tuple(branch for branch in candidates if _branch_tree_carries(main_repo, branch, rel_meta))


def _retarget_record_unwritable(recorded_target: str, effective_target: str, reason: str, next_step: str) -> Refused:
    from specify_cli.coordination.types import Refused

    return Refused(
        error_code=RETARGET_RECORD_UNWRITABLE,
        message=(
            f"Refusing to retarget the mission from '{recorded_target}' to '{effective_target}': its record "
            f"(meta.json) cannot be committed on '{effective_target}' in this run: {reason.rstrip('.')}."
        ),
        destination_ref=effective_target,
        next_step=next_step,
    )


def _record_on_neither_reason(rel_meta: Path, mission_branch: str | None, effective_target: str) -> str:
    if mission_branch is None:
        return f"'{effective_target}' does not carry {rel_meta.as_posix()} and the mission's lanes.json names no mission branch"
    return (
        f"neither the mission branch '{mission_branch}' nor '{effective_target}' carries {rel_meta.as_posix()} "
        "(the record lives only on the recorded target, and the new target was cut before the mission existed)"
    )


def retarget_record_refusal(
    main_repo: Path,
    mission_slug: str,
    *,
    recorded_target: str,
    effective_target: str,
) -> Refused | None:
    """The ``RETARGET_RECORD_UNWRITABLE`` refusal for a retarget whose record cannot be written, else ``None``.

    #7692 FR-011: a retarget rewrites ``meta.json`` (``target_branch``) on every branch
    :func:`retarget_record_holders` names, before anything else moves. It is refused up front
    when that write cannot happen in this run:

    * neither the Mission branch nor *effective_target* carries ``meta.json`` (the only shape
      that genuinely cannot be written: the record lives only on the recorded target);
    * *effective_target* carries it, but the repository root checkout cannot take the commit:
      the bookkeeping write's own hold check
      (:func:`~specify_cli.coordination.transaction.write_checkout_refusal`), then the shared
      primary-checkout precheck
      (:func:`~specify_cli.consolidation.meta_write.primary_checkout_refusal`: on
      *effective_target*, not detached, ``meta.json`` tracked, clean and not skip-worktree), with
      a skip-worktree or assume-unchanged BIT refused even with no edit (:func:`_index_bit`;
      retarget only, the bake's own precheck is unchanged);
    * *effective_target* is not a holder, but the root checkout on it holds untracked copies of
      the Mission directory the landing would overwrite (:func:`_untracked_mission_copies_refusal`).

    When only the Mission branch carries the record, the root checkout is not required to
    hold it: the landing carries the record to *effective_target*. ``None`` when the two
    targets agree (FR-012: restating the record is not a retarget). Read-only and lock-free,
    like its #5783 sibling :func:`refuse_unwritable_recorded_target`.
    """
    if effective_target == recorded_target:
        return None

    mission_branch = _manifest_mission_branch(main_repo, mission_slug)
    holders = retarget_record_holders(main_repo, mission_slug, mission_branch=mission_branch, effective_target=effective_target)
    rel_meta = _rel_meta_path(main_repo, mission_slug)
    if not holders:
        return _retarget_record_unwritable(
            recorded_target,
            effective_target,
            _record_on_neither_reason(rel_meta, mission_branch, effective_target),
            next_step=(
                f"Consolidate into the recorded target '{recorded_target}' (drop '--target {effective_target} --retarget'); "
                f"or first bring the mission onto '{effective_target}' so it carries {rel_meta.parent.as_posix()}/ "
                f"(integrate '{recorded_target}' into '{effective_target}'), then re-run with '--target {effective_target} --retarget'."
            ),
        )
    if effective_target not in holders:
        return _untracked_mission_copies_refusal(main_repo, rel_meta, recorded_target=recorded_target, effective_target=effective_target)
    return _new_target_checkout_refusal(main_repo, mission_slug, rel_meta, recorded_target=recorded_target, effective_target=effective_target)


#: ``git ls-files -v`` tags: ``S`` is skip-worktree; a lowercase tag is assume-unchanged.
_SKIP_WORKTREE_TAG = "S"


def _index_bit(main_repo: Path, rel_path: Path) -> tuple[str, str] | None:
    """``(bit name, the command that clears it)`` when *rel_path* carries skip-worktree and/or assume-unchanged, else ``None``.

    ``ls-files -v`` tags ``S`` (skip-worktree), a lowercase letter (assume-unchanged) and ``s``
    (both). One ``update-index`` call clears only one of the two bits, so for ``s`` the command is
    two calls joined by ``&&`` (re-review LOW-4). A probe that cannot run reads as no bit: the
    primary-checkout precheck that follows refuses any probe failure on its own.
    """
    try:
        entries = index_entries(main_repo, pathspecs=(rel_path.as_posix(),), tags=True)
    except GitCommandError:
        return None
    tag = (entries[0].tag or "") if entries else ""
    path = shlex.quote(rel_path.as_posix())
    flags = [flag for flag, present in (("--no-skip-worktree", tag.upper() == _SKIP_WORKTREE_TAG), ("--no-assume-unchanged", tag.islower())) if present]
    if not flags:
        return None
    names = {"--no-skip-worktree": "skip-worktree", "--no-assume-unchanged": "assume-unchanged"}
    return " and ".join(names[flag] for flag in flags), " && ".join(f"git update-index {flag} {path}" for flag in flags)


#: ``ls-files -v`` tags of a skip-worktree entry: ``S``, or ``s`` when it also carries assume-unchanged (review SW-2).
_SKIP_WORKTREE_TAGS = frozenset({_SKIP_WORKTREE_TAG, _SKIP_WORKTREE_TAG.lower()})

#: A checkout the landing resyncs holds a skip-worktree index entry, its file present in the working
#: tree, at a path the landing writes: the resync's ``git reset --hard`` cannot update it.
CHECKOUT_SKIP_WORKTREE_ENTRIES = "CHECKOUT_SKIP_WORKTREE_ENTRIES"


def _present_skip_worktree_paths(checkout: Path) -> list[str]:
    """Index entries of *checkout* carrying the skip-worktree bit whose file EXISTS in its working tree.

    A sparse-checkout exclusion sets the same bit but leaves no file, so it is never listed: only a
    bit set by hand (``git update-index --skip-worktree``) is. A probe that cannot run lists nothing.
    """
    try:
        entries = index_entries(checkout, tags=True)
    except GitCommandError:
        return []
    flagged = (entry.path.as_posix() for entry in entries if entry.tag in _SKIP_WORKTREE_TAGS)
    return [path for path in dict.fromkeys(flagged) if os.path.lexists(checkout / path)]


def _landing_paths(main_repo: Path, target_branch: str, branches: list[str]) -> set[str]:
    """Every path the Mission and lane branches change since they left *target_branch* (``<target>...<branch>``)."""
    paths: set[str] = set()
    for branch in branches:
        try:
            paths.update(path.as_posix() for path in git_changed_paths(main_repo, f"{target_branch}...{branch}"))
        except GitCommandError:
            continue
    return paths


def skip_worktree_landing_refusal(main_repo: Path, mission_slug: str, lanes_manifest: LanesManifest, *, target_branch: str) -> Refused | None:
    """``CHECKOUT_SKIP_WORKTREE_ENTRIES`` when a checkout the run resyncs holds a skip-worktree entry it writes, else ``None``.

    The run moves the Mission branch (each lane is consolidated into it) and *target_branch* (the landing) with
    :func:`~specify_cli.git.ref_advance.advance_branch_ref`, which resyncs every checkout holding
    the branch, and writes its bookkeeping (``meta.json``, the status files) into the Mission
    directory of the checkout on the target. A skip-worktree entry there hides the run's own write
    from the bookkeeping commit: the post-merge ``meta.json`` (``baseline_merge_commit``) is left out
    ("No post-merge bookkeeping changes to commit"), the baseline validation fails, and the
    rollback's resync back to the snapshot then fails on the now-edited file ("not uptodate"),
    leaving the landing staged in the checkout and the merge record behind. Refusing Mission
    directory entries is the real fix. Entries on paths the Mission and lane branches change are
    refused conservatively: an EDITED skip-worktree file is invisible to ``git status`` and to the
    dirty-checkout gate, so the resync would overwrite or trip on it; an unedited one would land,
    and is refused anyway. The resync contract is unchanged.

    Judged per checkout holding *target_branch* or the Mission branch: its entries tagged ``S`` or
    ``s`` (skip-worktree, alone or with assume-unchanged) whose path exists in the working tree
    (``lexists``: a dangling symlink counts; a sparse-checkout exclusion has no file and never
    does), under the Mission directory or among the paths the Mission and lane branches change
    (:func:`_landing_paths`, read only when such an entry exists). An assume-unchanged bit alone is
    not refused: the bookkeeping commit stages its write. The index listing is ``ls-files``, which
    expands a sparse index in memory (git >= 2.35's ``--sparse`` is above the git floor). Read-only
    and lock-free; a probe that cannot run is left to the run's own refusals.
    """
    from specify_cli.coordination.types import Refused
    from specify_cli.git.ref_advance import RefAdvanceError, worktrees_with_branch_checked_out
    from specify_cli.lanes.compute import lane_created_branch

    mission_prefix = f"{KITTY_SPECS_DIR}/{mission_slug}/"
    written: set[str] | None = None
    for branch in dict.fromkeys(b for b in (target_branch, lanes_manifest.mission_branch) if b):
        try:
            checkouts = worktrees_with_branch_checked_out(main_repo, branch)
        except RefAdvanceError:
            continue
        for checkout in checkouts:
            flagged = _present_skip_worktree_paths(checkout)
            if not flagged:
                continue
            if written is None:
                branches = [lanes_manifest.mission_branch, *(lane_created_branch(lanes_manifest, lane.lane_id) for lane in lanes_manifest.lanes)]
                written = _landing_paths(main_repo, target_branch, [b for b in dict.fromkeys(branches) if b and b != target_branch])
            hits = [path for path in flagged if path.startswith(mission_prefix) or path in written]
            if hits:
                return _skip_worktree_refused(main_repo, checkout, branch, hits, Refused)
    return None


def _skip_worktree_refused(main_repo: Path, checkout: Path, branch: str, hits: list[str], refused: type[Refused]) -> Refused:
    quoted = " ".join(shlex.quote(path) for path in hits)
    git = "git" if checkout.resolve() == main_repo.resolve() else f"git -C {shlex.quote(str(checkout))}"
    return refused(
        error_code=CHECKOUT_SKIP_WORKTREE_ENTRIES,
        message=(
            f"the checkout at {checkout} holds '{branch}' and marks {len(hits)} file(s) this consolidation writes as "
            f"skip-worktree ({', '.join(hits[:5])}{', ...' if len(hits) > 5 else ''}); git would leave the run's writes "
            "out of its commits and could not resync the checkout."
        ),
        destination_ref=branch,
        next_step=f"Clear the bit (`{git} update-index --no-skip-worktree {quoted}`), then re-run.",
    )


def _untracked_mission_copies_refusal(main_repo: Path, rel_meta: Path, *, recorded_target: str, effective_target: str) -> Refused | None:
    """The refusal when the landing would overwrite untracked copies of the Mission directory, else ``None`` (#7692 FR-011).

    *effective_target* is not a holder (it was cut before the Mission existed), so the landing
    writes ``kitty-specs/<slug>/`` into the repository root checkout. When that checkout is on
    *effective_target* and holds untracked files under that directory, the landing's resync
    would overwrite them: the run would mutate first and then fail. Only the root checkout on
    *effective_target* is judged; the off-target preflight owns a checkout on another branch.
    """
    if checked_out_branch(main_repo) != effective_target:
        return None
    mission_dir = rel_meta.parent.as_posix()
    try:
        entries = status_entries(main_repo, pathspecs=(mission_dir,), untracked="all")
    except GitCommandError:
        entries = ()
    untracked = [entry.path.as_posix() for entry in entries if entry.is_untracked]
    if not untracked:
        return None
    return _retarget_record_unwritable(
        recorded_target,
        effective_target,
        (
            f"the repository root checkout holds {len(untracked)} untracked file(s) under {mission_dir}/ (e.g. {untracked[0]}) "
            f"that the landing would overwrite, because '{effective_target}' does not carry the mission yet"
        ),
        next_step=f"Remove the untracked copies under {mission_dir}/ (or move them aside), then re-run with '--target {effective_target} --retarget'.",
    )


def _new_target_checkout_refusal(main_repo: Path, mission_slug: str, rel_meta: Path, *, recorded_target: str, effective_target: str) -> Refused | None:
    """The refusal when the root checkout cannot take the record commit on *effective_target*, else ``None``."""
    from specify_cli.consolidation.meta_write import primary_checkout_refusal
    from specify_cli.coordination.transaction import write_checkout_refusal

    hold = write_checkout_refusal(main_repo, mission_slug, effective_target, operation=f"retarget record for {mission_slug}")
    if hold is not None:
        return _retarget_record_unwritable(
            recorded_target,
            effective_target,
            hold.message,
            next_step=f"Check out '{effective_target}' in the repository root checkout (`git checkout {effective_target}`), then re-run.",
        )
    bit = _index_bit(main_repo, rel_meta)
    if bit is not None:
        name, clear = bit
        return _retarget_record_unwritable(
            recorded_target,
            effective_target,
            f"{rel_meta.as_posix()} carries the {name} bit in the repository root checkout, so git cannot be trusted to read or rewrite it",
            next_step=f"Clear the bit (`{clear}`), then re-run with '--target {effective_target} --retarget'.",
        )
    reason = primary_checkout_refusal(main_repo, rel_meta, effective_target)
    if reason is None:
        return None
    return _retarget_record_unwritable(
        recorded_target,
        effective_target,
        reason,
        next_step=(
            f"Check out '{effective_target}' in the repository root checkout (`git checkout {effective_target}`) and make sure "
            f"{rel_meta.as_posix()} is tracked there with no uncommitted or skip-worktree edit (commit or discard the edit), then re-run."
        ),
    )


def retarget_write_branch_refusal(*, mission_branch: str | None, recorded_target: str, effective_target: str) -> Refused | None:
    """``RETARGET_WRITE_BRANCH_IS_RECORDED_TARGET`` when the Mission's write branch is its recorded target, else ``None`` (#7692, C-006).

    A commit-to-target ``single_branch`` Mission writes on its target: ``lanes.json`` names the
    recorded target as its ``mission_branch``. Retargeted, the run would treat the old target as
    the Mission branch, land it on the new one and then delete it with the Mission's other
    branches. Witnessed end to end before this guard: ``main`` was deleted. Pure; equal targets
    are never a retarget (FR-012).
    """
    if effective_target == recorded_target or mission_branch != recorded_target:
        return None
    from specify_cli.coordination.types import Refused

    return Refused(
        error_code=RETARGET_WRITE_BRANCH_IS_RECORDED_TARGET,
        message=(
            f"Refusing to retarget the mission from '{recorded_target}' to '{effective_target}': its work is written on "
            f"'{recorded_target}' itself (a commit-to-target single_branch mission), so this run would land "
            f"'{recorded_target}' as the mission branch and then delete it."
        ),
        destination_ref=effective_target,
        next_step=(
            f"Consolidate into the recorded target '{recorded_target}' (drop '--target {effective_target} --retarget'), "
            f"then integrate '{recorded_target}' into '{effective_target}' with git."
        ),
    )


def merge_record_key(main_repo: Path, mission_slug: str) -> str:
    """The key the executor stores this Mission's merge record under: the ``meta.json`` ``mission_id``, else the slug.

    The same rule as ``executor._run_lane_based_consolidation`` (``resolve_mission_identity`` on the
    PRIMARY_METADATA directory), so a caller holding a legacy ``lanes.json`` without ``mission_id``
    still finds the record (#7692 review OA-1). An unreadable ``meta.json`` keys on the slug, as the
    executor's own fallback does for a Mission with no identity.
    """
    from mission_runtime import ActionContextError, MissionArtifactKind, placement_seam
    from specify_cli.core.paths import MissionMetaReadError
    from specify_cli.mission_metadata import resolve_mission_identity

    try:
        identity = resolve_mission_identity(placement_seam(main_repo, mission_slug).read_dir(MissionArtifactKind.PRIMARY_METADATA))
    except (ActionContextError, MissionMetaReadError, ValueError):
        return mission_slug
    return identity.mission_id or mission_slug


def persisted_retarget_pair(main_repo: Path, canonical_id: str) -> tuple[str, str] | None:
    """``(from, to)`` of the retarget an existing merge record persisted, else ``None`` (#7692).

    An unreadable record contributes none: the run's resume code owns that error.
    """
    try:
        state = load_state(main_repo, canonical_id)
    except (ConsolidationStateReadError, OSError):
        return None
    return state.retarget_pair() if state is not None else None


@dataclass(frozen=True)
class RetargetMode:
    """How a run is judged against a retarget (#7692): the ONE decision the entry preflight and the forecast share.

    ``pair`` is the ``(recorded, new)`` target pair when the run is a retarget, else ``None``.
    ``mismatch`` is the ``RETARGET_RESUME_MISMATCH`` refusal when a merge record persisted a
    retarget and this run's target is not that retarget's new target; each caller renders it its
    own way.
    """

    pair: tuple[str, str] | None
    mismatch: Refused | None = None


def _retarget_resume_mismatch(persisted: tuple[str, str], effective_target: str, *, retarget: bool) -> Refused:
    from specify_cli.coordination.types import Refused

    recorded, persisted_to = persisted
    asked = f"'--target {effective_target} --retarget'" if retarget else f"'--target {effective_target}'"
    instead = f"retarget onto '{effective_target}'" if retarget else f"consolidate into '{effective_target}'"
    return Refused(
        error_code=RETARGET_RESUME_MISMATCH,
        message=(f"this mission's interrupted consolidation retargets it from '{recorded}' to '{persisted_to}', but this run asks for {asked}."),
        destination_ref=effective_target,
        next_step=(
            f"re-run with '--target {persisted_to} --retarget' (or a bare `spec-kitty consolidate --resume`) to finish "
            f"that retarget, or run `spec-kitty consolidate --abort` first to {instead} instead."
        ),
    )


def retarget_mode(main_repo: Path, canonical_id: str, *, retarget: bool, recorded: str, effective: str) -> RetargetMode:
    """Judge whether this run is a retarget (#7692); the single owner both the run and ``--dry-run`` read.

    A merge record that persisted a retarget binds every later run: a target other than that
    retarget's new target is a mismatch, with or without ``--retarget`` (mission review RISK-1:
    ``--target <recorded>`` used to pass this check and then have the locked run re-apply the
    persisted retarget anyway). Equal targets are never a retarget (FR-012). Otherwise the run is a
    retarget when ``--retarget`` asks for one, or when the merge record persisted this very
    retarget (a bare ``--resume``, or a re-run after a re-baselined failure).
    """
    persisted = persisted_retarget_pair(main_repo, canonical_id)
    if persisted is not None and persisted[1] != effective:
        return RetargetMode(pair=None, mismatch=_retarget_resume_mismatch(persisted, effective, retarget=retarget))
    if recorded == effective:
        return RetargetMode(pair=None)
    if retarget or persisted == (recorded, effective):
        return RetargetMode(pair=(recorded, effective))
    return RetargetMode(pair=None)


def persisted_retarget_refusal(main_repo: Path, canonical_id: str, mission_slug: str) -> Refused | None:
    """``RETARGET_RESUME_MISMATCH`` for a command with no ``--retarget`` facing a persisted retarget, else ``None`` (#7692).

    ``orchestrator-api consolidate-mission`` can neither finish a persisted retarget (it runs no
    retarget preflight and has no rollback door) nor land on any target while the merge record
    names one (mission review RISK-1), so every persisted retarget refuses there, whatever its
    ``--target``. The next step names the ``spec-kitty consolidate`` commands that can.
    """
    persisted = persisted_retarget_pair(main_repo, canonical_id)
    if persisted is None:
        return None
    from specify_cli.coordination.types import Refused

    source, to = persisted
    return Refused(
        error_code=RETARGET_RESUME_MISMATCH,
        message=(f"this mission's interrupted consolidation retargets it from '{source}' to '{to}', and only `spec-kitty consolidate` can finish a retarget."),
        destination_ref=to,
        next_step=(
            f"run `spec-kitty consolidate --mission {mission_slug} --resume` to finish that retarget, or "
            f"`spec-kitty consolidate --mission {mission_slug} --abort` first to drop it."
        ),
    )


def target_override_verdict(
    main_repo: Path,
    mission_slug: str,
    *,
    recorded_target: str,
    effective_target: str,
    retarget: bool = False,
) -> Refused | None:
    """The ONE owner of the ``--target`` override verdict (#7692, plan D1), else ``None``.

    #6464 (:func:`refuse_protected_target_override`) runs first, then the record check:

    * a plain ``--target`` (``retarget=False``): the #5783 recorded-target check
      (:func:`refuse_unwritable_recorded_target`), exactly today's chain (C-002);
    * ``--retarget``: :func:`retarget_record_refusal`; a retarget never consults #5783.

    Pure verdict: each caller keeps its own rendering and exception type.
    """
    protected = refuse_protected_target_override(main_repo, mission_slug, recorded_target=recorded_target, effective_target=effective_target)
    if protected is not None:
        return protected
    record_check = retarget_record_refusal if retarget else refuse_unwritable_recorded_target
    return record_check(main_repo, mission_slug, recorded_target=recorded_target, effective_target=effective_target)
