"""
Stale Work Package Detection
============================

Detects work packages that are in "doing" lane but have no recent VCS activity,
indicating the agent may have stopped without transitioning the WP.

Uses git/jj commit timestamps as a "heartbeat" - if no commits for a threshold
period, the WP is considered stale.

FR-005 (claim-liveness re-point): claim-liveness inputs (``shell_pid`` /
``shell_pid_created_at``) resolve unconditionally from the reduced
event-sourced snapshot whenever a WP's feature directory is supplied; the
snapshot is the sole authority for this call -- it is never blended with the
frontmatter-extracted values the caller passes (C-001). When no
``feature_dir`` is supplied (the WP02 runtime window) the caller-supplied
frontmatter values are used unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kernel.clock import UTC, datetime, now_utc, parse_iso
from mission_runtime import OwnedCheckout
from specify_cli.core.process_liveness import is_claiming_process_alive, is_process_alive
from specify_cli.frontmatter import SHELL_PID_BASELINE_FIELD
from specify_cli.status import wp_snapshot_state as _wp_snapshot_state
from specify_cli.workspace.context import resolve_workspace_for_wp

PLANNING_ARTIFACT_REPO_ROOT_REASON = "planning_artifact_repo_root_shared_workspace"
LIVE_CLAIM_PROCESS_REASON = "live_claim_process"


@dataclass(frozen=True)
class StaleState:
    """Canonical stale-state payload for machine-facing status surfaces."""

    status: str
    reason: str | None = None
    minutes_since_commit: float | None = None
    last_commit_time: datetime | None = None

    def to_dict(self) -> dict[str, str | float | None]:
        """Serialize to the canonical JSON-compatible stale object."""
        return {
            "status": self.status,
            "reason": self.reason,
            "minutes_since_commit": self.minutes_since_commit,
            "last_commit_time": self.last_commit_time.isoformat() if self.last_commit_time else None,
        }


@dataclass
class StaleCheckResult:
    """Result of checking a work package for staleness."""

    wp_id: str
    stale: StaleState
    workspace_exists: bool
    workspace_kind: str
    error: str | None = None

    @property
    def is_stale(self) -> bool:
        """Deprecated flat compatibility field derived from the stale object."""
        return self.stale.status == "stale"

    @property
    def last_commit_time(self) -> datetime | None:
        """Deprecated flat compatibility field derived from the stale object."""
        return self.stale.last_commit_time

    @property
    def minutes_since_commit(self) -> float | None:
        """Deprecated flat compatibility field derived from the stale object."""
        return self.stale.minutes_since_commit

    @property
    def worktree_exists(self) -> bool:
        """Deprecated flat compatibility field derived from the stale object."""
        return self.workspace_kind != "repo_root" and self.workspace_exists


def get_default_branch(repo_path: Path) -> str:
    """
    Get the default/base branch name for the repository (for stale detection).

    This is used to find the branch that feature branches diverged FROM.
    Unlike resolve_primary_branch() in git_ops, this does NOT use the current
    branch because stale detection always runs from worktrees where the current
    branch is always the feature branch, never the base branch.

    Tries multiple methods to detect the default branch:
    1. Check origin's HEAD symbolic ref
    2. Check which common branch exists (main, master, develop)
    3. Fallback to "main"

    Args:
        repo_path: Path to the repository

    Returns:
        Default branch name (e.g., "main", "master", "develop")
    """
    import subprocess

    # Method 1: Get from origin's HEAD
    result = subprocess.run(
        ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=5,
    )

    if result.returncode == 0:
        # Output: "refs/remotes/origin/main" → extract "main"
        ref = result.stdout.strip()
        return ref.split("/")[-1]

    # Method 2: Check which common branch exists
    for branch in ["main", "master", "develop"]:
        check = subprocess.run(
            ["git", "rev-parse", "--verify", branch],
            cwd=repo_path,
            capture_output=True,
            timeout=5,
        )
        if check.returncode == 0:
            return branch

    # Method 3: Fallback
    return "main"


def get_last_meaningful_commit_time(worktree_path: Path) -> tuple[datetime | None, bool]:
    """
    Get the timestamp of the most recent meaningful commit in a worktree.

    A "meaningful" commit is one made ON THIS BRANCH since it diverged from main.
    This prevents false staleness when a worktree is just created but no commits
    have been made yet (HEAD points to parent branch's old commit).

    For worktrees, we always use git to check the branch-specific history,
    even in jj colocated repos. This is because:
    - jj's shared history includes commits from ALL workspaces
    - jj continuously auto-snapshots the working copy
    - We need the last commit on THIS worktree's branch, not the shared history

    Args:
        worktree_path: Path to the worktree

    Returns:
        Tuple of (datetime of last commit on this branch, has_own_commits).
        has_own_commits is False if the branch has no commits since diverging from main.
    """
    import subprocess

    if not worktree_path.exists():
        return None, False

    try:
        # Detect the actual default branch name (main, master, develop, etc.)
        default_branch = get_default_branch(worktree_path)

        # First, check if this branch has any commits since diverging from the default branch
        # This prevents false staleness when worktree was just created
        merge_base_result = subprocess.run(
            ["git", "merge-base", "HEAD", default_branch],
            cwd=worktree_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )

        if merge_base_result.returncode != 0:
            # Merge-base failed - branch might not exist, detached HEAD, etc.
            # Return None to avoid using wrong commit timestamp from parent branch
            return None, False

        merge_base = merge_base_result.stdout.strip()

        # Count commits on this branch since the merge base
        count_result = subprocess.run(
            ["git", "rev-list", "--count", f"{merge_base}..HEAD"],
            cwd=worktree_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )

        if count_result.returncode == 0:
            commit_count = int(count_result.stdout.strip())
            if commit_count == 0:
                # No commits on this branch yet - worktree just created
                # Don't flag as stale since agent just started
                return None, False

        # Get the last commit time on this branch
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cI"],
            cwd=worktree_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )

        if result.returncode != 0 or not result.stdout.strip():
            return None, False

        # Parse ISO format timestamp
        timestamp_str = result.stdout.strip()
        return parse_iso(timestamp_str), True

    except subprocess.TimeoutExpired:
        return None, False
    except Exception:
        return None, False


def _is_claiming_process_alive(shell_pid: str | None, shell_pid_baseline: str | None = None) -> bool:
    """Return whether ``shell_pid`` (as read from WP frontmatter) is a live process.

    Reuses the existing ``task_utils``-style frontmatter value (already extracted
    by callers via ``extract_scalar``/``WorkPackage.shell_pid`` — no new parse
    happens here). Conservative: an absent or unparseable ``shell_pid`` is
    treated as "not provably alive" so the timestamp heuristic remains the
    fallback.

    ``shell_pid_baseline`` (FR-005) is the persisted creation-time identity
    baseline co-written alongside ``shell_pid`` at claim time. Gated on
    presence (D3a, additive degradation):

    - Absent (a legacy claim written before the baseline field existed) ->
      delegates to the canonical ``core.process_liveness.is_process_alive``
      check verbatim (C-002) — today's exact live-PID trust, zero regression.
    - Present -> delegates to the PID-reuse-aware
      ``core.process_liveness.is_claiming_process_alive`` compare (FR-004): a
      mismatch (the PID was recycled) is treated as not alive.
    """
    if not shell_pid:
        return False
    try:
        pid = int(shell_pid)
    except (TypeError, ValueError):
        return False
    # bool() wrap: keeps per-file `mypy --strict` clean (follow_imports=skip erases the
    # imported `-> bool`), matching emit.py's defensive pattern at the same boundary.
    if not shell_pid_baseline:
        return bool(is_process_alive(pid))
    return bool(is_claiming_process_alive(pid, shell_pid_baseline))


def _read_wp_runtime_snapshot_state(feature_dir: Path, wp_id: str) -> dict[str, Any]:
    """Read the reduced-snapshot per-WP runtime state for *wp_id* (FR-005).

    Reuses the canonical annotation-aware read seam -- ``status.store
    .read_event_stream`` + ``status.reducer.reduce`` -- the same entry the
    rest of the ``status`` package folds through (e.g.
    ``status.emit._infer_subtasks_complete`` via
    ``core.subtask_rows.unchecked_subtask_ids_from_snapshot``). No second
    parser/read path is introduced (#2093 / FR-013).

    Returns an empty dict when the WP has no reduced snapshot entry (never
    claimed, or the event log is empty) -- a valid, authoritative "no runtime
    state yet" result, not a signal to fall back to frontmatter.

    Delegates to the shared ``status.reducer.wp_snapshot_state`` accessor (IC-08
    dedup); ``or {}`` preserves the empty-dict "no runtime state yet" contract.
    """
    # dict(): the shared accessor returns a Mapping; this function's contract is
    # dict[str, Any], so materialize a real dict (``or {}`` keeps the empty-dict
    # "no runtime state yet" result).
    return dict(_wp_snapshot_state(feature_dir, wp_id) or {})


def _resolve_claim_liveness_inputs(
    feature_dir: Path | None,
    wp_id: str,
    shell_pid: str | None,
    shell_pid_baseline: str | None,
) -> tuple[str | None, str | None]:
    """Resolve claim-liveness ``(shell_pid, shell_pid_baseline)`` (FR-005).

    - *feature_dir* is ``None`` (the WP02 runtime window): return
      ``(shell_pid, shell_pid_baseline)`` unchanged -- the caller-supplied
      frontmatter-sourced values.
    - *feature_dir* supplied: the reduced snapshot is the sole source (C-001 --
      a snapshot-first reader must never also consult the frontmatter fallback).
      The frontmatter-extracted ``shell_pid``/``shell_pid_baseline`` arguments
      are ignored entirely, including when the snapshot has no entry for *wp_id*
      (that degrades to ``(None, None)`` -- the same conservative "not provably
      alive" state :func:`check_wp_staleness` already handles for an
      absent/unparseable PID).

    The snapshot's ``shell_pid`` slot is stored as ``int``; it is coerced to
    ``str`` here so the return shape matches what callers have always passed
    (frontmatter is always string-typed).
    """
    if feature_dir is None:
        return shell_pid, shell_pid_baseline

    wp_state = _read_wp_runtime_snapshot_state(feature_dir, wp_id)
    snapshot_pid = wp_state.get("shell_pid")
    snapshot_baseline = wp_state.get("shell_pid_created_at")
    return (
        str(snapshot_pid) if snapshot_pid is not None else None,
        str(snapshot_baseline) if snapshot_baseline is not None else None,
    )


def check_wp_staleness(
    wp_id: str,
    worktree_path: Path,
    threshold_minutes: int = 10,
    shell_pid: str | None = None,
    shell_pid_baseline: str | None = None,
    feature_dir: Path | None = None,
) -> StaleCheckResult:
    """
    Check if a work package is stale based on VCS activity.

    A WP is considered stale if:
    - Its worktree exists
    - The branch has commits since diverging from main (agent has done work)
    - The last commit is older than threshold_minutes

    A WP with a worktree but NO commits since diverging is NOT stale - the agent
    just started and hasn't committed yet.

    A WP whose claiming ``shell_pid`` (FR-007) is a live process is never flagged
    stale, regardless of commit age — this suppresses false positives for an
    agent that is reading/planning for minutes before its first commit
    (Scenario 3). This is a *suppression* of the timestamp heuristic, not a
    replacement: when no ``shell_pid`` is recorded, it is unparseable, or the
    process is not alive, the timestamp-based logic below still applies.

    Args:
        wp_id: Work package ID (e.g., "WP01")
        worktree_path: Path to the WP's worktree
        threshold_minutes: Minutes of inactivity before considered stale
        shell_pid: The WP's claiming shell PID, as read from frontmatter (may be
            ``None``, empty, or unparseable — handled conservatively). Ignored
            whenever *feature_dir* is supplied (the snapshot wins, unconditionally).
        shell_pid_baseline: The PID-reuse identity baseline (FR-005) co-written
            alongside ``shell_pid`` at claim time, as read from frontmatter.
            ``None`` (absent — a legacy claim) preserves today's live-PID trust
            (D3a); present-but-mismatched treats the claim as not alive. Ignored
            whenever *feature_dir* is supplied (the snapshot wins, unconditionally).
        feature_dir: The WP's kitty-specs feature directory (e.g.
            ``kitty-specs/<slug>``); when supplied, the reduced snapshot's
            ``shell_pid``/``shell_pid_created_at`` slots are read unconditionally
            in place of *shell_pid*/*shell_pid_baseline* above. ``None`` (the
            default) preserves today's frontmatter-sourced behavior verbatim --
            existing callers that do not pass it see zero regression.

    Returns:
        StaleCheckResult with staleness status
    """
    resolved_shell_pid, resolved_shell_pid_baseline = _resolve_claim_liveness_inputs(feature_dir, wp_id, shell_pid, shell_pid_baseline)

    if not worktree_path.exists():
        return StaleCheckResult(
            wp_id=wp_id,
            stale=StaleState(status="fresh"),
            workspace_exists=False,
            workspace_kind="lane_workspace",
        )

    if _is_claiming_process_alive(resolved_shell_pid, resolved_shell_pid_baseline):
        return StaleCheckResult(
            wp_id=wp_id,
            stale=StaleState(status="fresh", reason=LIVE_CLAIM_PROCESS_REASON),
            workspace_exists=True,
            workspace_kind="lane_workspace",
        )

    try:
        last_commit, has_own_commits = get_last_meaningful_commit_time(worktree_path)

        if last_commit is None:
            # Can't determine commit time, or no commits on this branch yet
            # If no commits yet (has_own_commits=False), agent just started - not stale
            return StaleCheckResult(
                wp_id=wp_id,
                stale=StaleState(status="fresh"),
                workspace_exists=True,
                workspace_kind="lane_workspace",
                error=None if not has_own_commits else "Could not determine last commit time",
            )

        now = now_utc()
        # Ensure last_commit is timezone-aware
        if last_commit.tzinfo is None:
            last_commit = last_commit.replace(tzinfo=UTC)

        delta = now - last_commit
        minutes_since = delta.total_seconds() / 60

        is_stale = minutes_since > threshold_minutes

        return StaleCheckResult(
            wp_id=wp_id,
            stale=StaleState(
                status="stale" if is_stale else "fresh",
                minutes_since_commit=round(minutes_since, 1),
                last_commit_time=last_commit,
            ),
            workspace_exists=True,
            workspace_kind="lane_workspace",
        )

    except Exception as e:
        return StaleCheckResult(
            wp_id=wp_id,
            stale=StaleState(status="fresh"),
            workspace_exists=True,
            workspace_kind="lane_workspace",
            error=str(e),
        )


def _resolve_feature_dir_for_staleness(main_repo_root: Path, mission_slug: str) -> Path | None:
    """Resolve the mission's kitty-specs feature directory for the FR-005 lookup.

    Lazy-imported (mirrors ``task_utils.support.locate_work_package``) so this
    module does not pay for the ``missions``/``mission_runtime`` import surface
    on every cold start -- only when a "doing" WP is actually checked. Never
    raises: an unresolvable mission (e.g. a malformed slug) degrades to
    ``None``, which makes :func:`check_wp_staleness` fall back to the
    frontmatter-sourced legacy path (no ``feature_dir`` to read the snapshot from).
    """
    try:
        # read-side-placement-seam-migration WP07: routed through
        # ``placement_seam`` (fail-loud on a deleted-coord mismatch, NFR-002)
        # instead of the kind-blind ``resolve_planning_read_dir`` — the
        # surrounding ``except Exception`` already absorbs any resolution
        # failure into the pre-existing ``None``-degrade contract, independent
        # of the seam's own fail-loud behavior.
        from mission_runtime import MissionArtifactKind, placement_seam

        return placement_seam(main_repo_root, mission_slug).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK)
    except Exception:
        return None


def check_doing_wps_for_staleness(
    main_repo_root: Path,
    mission_slug: str,
    doing_wps: list[dict[str, Any]],
    threshold_minutes: int = 10,
    *,
    owned: OwnedCheckout | None = None,
) -> dict[str, StaleCheckResult]:
    """
    Check all WPs in "doing" lane for staleness.

    Args:
        main_repo_root: Root of the main repository
        mission_slug: Feature slug
        doing_wps: List of WP dicts with at least 'id' key
        threshold_minutes: Minutes of inactivity threshold
        owned: Validated ownership fact (owned-checkout-lifecycle-authority
            WP05); threaded into :func:`resolve_workspace_for_wp` so an owned
            mission's staleness check reads the owned checkout, never a
            repository-root-side lane worktree.

    Returns:
        Dict mapping WP ID to StaleCheckResult
    """
    results = {}

    for wp in doing_wps:
        wp_id = wp.get("id") or wp.get("work_package_id")
        if not wp_id:
            continue

        workspace = resolve_workspace_for_wp(main_repo_root, mission_slug, wp_id, owned=owned)

        if workspace.runs_in_checkout_root:
            result = StaleCheckResult(
                wp_id=wp_id,
                stale=StaleState(
                    status="not_applicable",
                    reason=PLANNING_ARTIFACT_REPO_ROOT_REASON,
                ),
                workspace_exists=workspace.exists,
                workspace_kind=workspace.resolution_kind,
            )
            results[wp_id] = result
            continue

        if workspace.exists:
            # Reuse the shell_pid already extracted from frontmatter by the caller
            # (task_utils.support.extract_scalar — the same reader backing
            # WorkPackage.shell_pid) — no new frontmatter parse (C-002). Same for
            # the paired baseline (FR-005): if the caller's wp dict doesn't carry
            # SHELL_PID_BASELINE_FIELD, this is None and staleness falls back to
            # today's live-PID trust (D3a) — no regression for callers not yet
            # updated to surface the new field. These are the fallback used only
            # when feature_dir cannot be resolved: check_wp_staleness reads
            # unconditionally from the reduced snapshot (below) whenever
            # feature_dir is available.
            shell_pid = wp.get("shell_pid") or None
            shell_pid_baseline = wp.get(SHELL_PID_BASELINE_FIELD) or None
            feature_dir = _resolve_feature_dir_for_staleness(main_repo_root, mission_slug)
            result = check_wp_staleness(
                wp_id,
                workspace.worktree_path,
                threshold_minutes,
                shell_pid=shell_pid,
                shell_pid_baseline=shell_pid_baseline,
                feature_dir=feature_dir,
            )
        else:
            result = StaleCheckResult(
                wp_id=wp_id,
                stale=StaleState(status="fresh"),
                workspace_exists=False,
                workspace_kind=workspace.resolution_kind,
            )

        results[wp_id] = result

    return results
