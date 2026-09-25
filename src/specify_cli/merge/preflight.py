"""Merge preflight checks for target branch safety.

Mission #2057 (decompose ``cli/commands/merge.py``) — IC-05 / WP05 relocated the
git / target-branch / mission-branch / canonical-status / review-artifact /
hollow-review preflights here (the historical home of the target-sync
remediation). One-way import: this module never imports the command shim.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer

from specify_cli import __version__ as SPEC_KITTY_VERSION
from specify_cli.cli.console import console
from specify_cli.core.env import is_interactive
from specify_cli.core.git_ops import run_command
from specify_cli.core.git_preflight import (
    build_git_preflight_failure_payload,
    run_git_preflight,
)
from specify_cli.merge._constants import (
    HollowReviewWarnings,
    MissionBranchBlocker,
    _STATUS_EVENTS_FILENAME,
    _STATUS_FILENAME,
)
from specify_cli.merge.git_probes import _has_branch_ref, _lane_already_integrated
from specify_cli.merge.state import load_state
from specify_cli.post_merge.review_artifact_consistency import (
    format_review_artifact_finding,
    review_artifact_finding_diagnostic,
    run_review_artifact_consistency_preflight,
)
from specify_cli.status import REVIEWER_SELF_APPROVAL

if TYPE_CHECKING:
    from specify_cli.merge.push_preflight import TargetBranchSyncStatus
    from specify_cli.post_merge.review_artifact_consistency import (
        ReviewArtifactFinding,
    )

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
        from specify_cli.merge import push_preflight

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
        from specify_cli.lanes.branch_naming import mission_branch_name_required

        focused_branch = focused_pr_branch_name(mission_slug, status.target_branch)
        source_branch = mission_branch or mission_branch_name_required(mission_slug, mission_id)
        lines.extend(
            [
                (f"Focused PR path: git switch -c {focused_branch} {source_branch}"),
                f"Then push it: git push -u origin {focused_branch}",
                f"Open a PR from {focused_branch} into {status.target_branch}.",
            ]
        )
    else:
        lines.append("If local-only commits are intentional, preserve them on a new PR branch before retrying.")

    lines.append("Do not use reset, rebase, or force-push as part of this preflight remediation.")
    return lines


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
    :class:`BranchIdentityUnresolved` for a genuinely-unresolvable modern slug
    (fail-closed preserved).
    """
    from specify_cli.lanes.branch_naming import resolve_branch_name

    expected_branch = expected_branch or resolve_branch_name(mission_slug, mission_id=mission_id)
    if _has_branch_ref(repo_root, expected_branch):
        return True, None

    retcode, stdout, _stderr = run_command(
        ["git", "rev-parse", "HEAD"],
        capture=True,
        check_return=False,
        cwd=repo_root,
    )
    base_sha = stdout.strip()[:12] if retcode == 0 else "<base-commit>"

    blocker_payload: MissionBranchBlocker = {
        "ready": False,
        "blocker": "missing_mission_branch",
        "expected_branch": expected_branch,
        "remediation": f"git branch {expected_branch} {base_sha}",
    }
    return False, blocker_payload


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

    payload = build_git_preflight_failure_payload(preflight, command_name="spec-kitty merge")
    if json_output:
        enriched = dict(payload)
        enriched["spec_kitty_version"] = SPEC_KITTY_VERSION
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
        print(json.dumps({"spec_kitty_version": SPEC_KITTY_VERSION, "error": error_msg}))
    else:
        console.print(f"[red]Error:[/red] {error_msg}")
    raise typer.Exit(1)


def _print_remediation_lines(remediation: object) -> None:
    """Print remediation lines from a ``dict[str, object]`` payload value.

    The payload is typed ``dict[str, object]`` so the ``remediation`` value is
    ``object`` at the call site; normalize to a list of strings before printing
    (behavior-preserving — the value is always a ``list[str]``).
    """
    lines = remediation if isinstance(remediation, list) else [str(remediation)]
    for line in lines:
        console.print(f"  - {line}")


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
    from specify_cli.merge.done_bookkeeping import _resolve_merge_actor
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
        # downstream; on a coord-less topology it delegates to the untouched
        # partition-agnostic emit (no-op parity).
        emit_inner_state_changed_transactional(
            feature_dir,
            wp_id,
            WPInnerStateDelta(review=ReviewOverride(at=timestamp, actor=actor, wp_id=wp_id, reason=note)),
            actor=actor,
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
    """Return the actor on WP's most recent transition into *to_lane*.

    Scans the raw event log rather than the reduced snapshot, because the
    snapshot's ``actor`` slot is overwritten on every transition -- it can
    only ever tell us who did the LATEST transition of any kind, never who
    specifically claimed/implemented versus who specifically approved.
    Returns ``None`` when the log is absent/unreadable or no matching,
    actor-bearing transition exists for this WP.
    """
    events_path = feature_dir / _STATUS_EVENTS_FILENAME
    if not events_path.exists():
        return None
    try:
        raw_lines = events_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    latest_key: tuple[str, str] = ("", "")
    latest_actor: str | None = None
    for raw_line in raw_lines:
        try:
            event = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("wp_id") != wp_id or event.get("to_lane") != to_lane:
            continue
        actor = event.get("actor")
        if not actor or not str(actor).strip():
            continue
        key = (str(event.get("at") or ""), str(event.get("event_id") or ""))
        if key >= latest_key:
            latest_key = key
            latest_actor = str(actor).strip()
    return latest_actor


def _independent_reviewer_confirmed(feature_dir: Path, wp_id: str) -> bool:
    """True when WP's latest approval actor positively differs from its
    latest implementation actor (#2412-adjacent field report, item #9).

    ``force_count`` alone cannot distinguish "reviewer used --force to bypass
    an unrelated gate false-positive" from "no independent review happened" --
    both increment the same counter. This checks the one thing that actually
    answers the question: did a different identity log the approving
    transition than the one that most recently claimed/implemented the WP?
    Returns False (never suppress) when either actor is missing/unknown --
    absence of evidence is not evidence of an independent review.
    """
    implementer = _latest_actor_for_transition(feature_dir, wp_id, "in_progress")
    reviewer = _latest_actor_for_transition(feature_dir, wp_id, "approved")
    if not implementer or not reviewer:
        return False
    return implementer != reviewer


def _collect_force_count_warnings(
    feature_dir: Path,
    wp_set: set[str],
    warnings: HollowReviewWarnings,
) -> None:
    """Append force_count>=2 warnings from ``status.json`` (WP05 split helper).

    Behavior-preserving extraction of the status-snapshot scan formerly inlined
    in ``_collect_hollow_review_warnings`` (FR-005, keeps CC <= 15) -- plus one
    additive guard (item #9): a WP whose approving actor is positively
    confirmed distinct from its implementing actor is not a hollow review,
    even with a high force_count, so it is not warned about here.
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
    for wp_id in sorted(wp_set):
        wp_state = work_packages.get(wp_id, {})
        if not isinstance(wp_state, dict):
            continue
        try:
            force_count = int(wp_state.get("force_count", 0))
        except (TypeError, ValueError):
            force_count = 0
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

_RESUME_HINT = "Then re-run: spec-kitty merge --resume"


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
    :mod:`specify_cli.merge.git_probes` (WP06 owns that module; it is consumed
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
      ``MergeState.pre_mutation_target_sha``) must be a STRICT ancestor of ``HEAD`` — the
      ref advanced past it. Equal ⇒ no lag ⇒ the dirt is genuine ⇒ ``False``.
    * the working tree AND the index must be byte-identical to ``base_sha``'s tree
      (``git diff --quiet <base>`` and ``git diff --cached --quiet <base>`` both clean).
      Any genuine edit, or an intentional deletion of a file unrelated to the advance,
      makes the tree differ from ``base_sha`` ⇒ ``False`` (fail-closed): it is preserved,
      never reset away.
    * no UNTRACKED file may obstruct a path the reset would restore. ``git diff`` is blind
      to untracked files, and ``git reset --hard HEAD`` silently OVERWRITES an untracked
      file sitting at a path present in HEAD's tree (a restored mission file). This last
      check closes that hole by reusing the single obstruction authority
      (:func:`ref_advance._path_obstructs_target_tree` against HEAD's tree paths); any
      obstructing untracked path ⇒ ``False``.

    Returns ``False`` on a missing ``base_sha`` or any git error (fail-closed): a state
    that cannot be proven a pure lag is treated as genuine local work.
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
    ancestor_ret, _out, _err = run_command(
        ["git", "merge-base", "--is-ancestor", base_sha, "HEAD"],
        capture=True,
        check_return=False,
        cwd=repo_root,
    )
    if ancestor_ret != 0:
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
    return not _untracked_obstructs_head(repo_root)


def _untracked_obstructs_head(repo_root: Path) -> bool:
    """True when an untracked file would be clobbered by ``git reset --hard HEAD``.

    ``git reset --hard`` preserves untracked files that do not collide, but OVERWRITES an
    untracked file at a path HEAD's tree carries (a restored tracked file). Reuse the
    single obstruction authority (:func:`ref_advance._path_obstructs_target_tree` against
    :func:`ref_advance._target_tree_paths` for HEAD) rather than a parallel predicate
    (INV-3). Fail-closed (``True``) on any git error, so an unprovable state blocks the
    reset. #4997 (untracked-collision hole confirmed in pre-PR review).
    """
    from specify_cli.git import ref_advance

    try:
        head_paths = ref_advance._target_tree_paths(repo_root, "HEAD", None)
    except Exception:
        return True
    untracked_ret, untracked_out, _err = run_command(
        ["git", "ls-files", "--others", "--exclude-standard"],
        capture=True,
        check_return=False,
        cwd=repo_root,
    )
    if untracked_ret != 0:
        return True
    for line in untracked_out.splitlines():
        path = line.strip().rstrip("/")
        if path and ref_advance._path_obstructs_target_tree(path, head_paths):
            return True
    return False
