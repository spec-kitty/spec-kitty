"""Workspace creation support for the implement command.

Extracted from implement.py to keep the command clean.
This module handles both supported execution paths:
- code_change WPs allocate or reuse a lane worktree and write context
- planning_artifact WPs execute directly in the repository root
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, replace
from pathlib import Path

from kernel.clock import now_utc_iso
from mission_runtime import MissionArtifactKind, placement_seam
from specify_cli.ownership.models import WorkProductKind
from specify_cli.lanes.lane_env import lane_test_env
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.branch_naming import lane_branch_name, worktree_dir_name as _worktree_dir_name
from specify_cli.core.vcs.git import capture_branch_tip
from specify_cli.lanes._git import branch_exists
from specify_cli.lanes.persistence import read_lanes_json
from specify_cli.lanes.planning_commit_classify import PinClass, classify_recorded_pin
from specify_cli.lanes.worktree_allocator import (
    ORPHANED_PIN_RECOVERY_HINT,
    _read_coordination_branch,
    allocate_lane_worktree,
    predict_lane_worktree,
)
from specify_cli.workspace.context import ResolvedWorkspace
from specify_cli.workspace.context import WorkspaceContext, save_context


@dataclass
class LaneWorkspaceResult:
    """Result of implement workspace creation."""

    workspace_path: Path
    branch_name: str | None
    workspace_name: str
    lane_id: str | None
    mission_branch: str | None
    is_reuse: bool
    vcs_backend_value: str
    execution_mode: str
    resolution_kind: str
    # WP01/T006/FR-006: lane-specific test database env vars, derived from
    # mission_slug + lane_id. Empty for planning-artifact resolutions
    # (no per-lane test DB needed when there is no per-lane worktree).
    lane_test_env: dict[str, str] | None = None

    def __post_init__(self) -> None:
        if self.lane_test_env is None:
            self.lane_test_env = {}


def refresh_reused_lane_context(
    repo_root: Path,
    mission_slug: str,
    lane_id: str | None,
    wp_id: str,
    declared_deps: list[str],
) -> bool:
    """Refresh a reused lane's workspace context to the newly active WP (#3946).

    A shared lane worktree outlives its WPs: claiming a later WP into the lane
    advances the canonical active WP, but the lane's persisted workspace context
    keeps ``current_wp`` from the earlier WP until something refreshes it —
    every later lane commit then warns ``ACTIVE_WP_CONTEXT_STALE`` and scopes
    against the prior WP's ownership (F-78). Both WP writers that reuse a lane
    — the native ``implement`` flow and the orchestrator API's
    ``start-implementation`` — route through this helper so the refresh cannot
    drift between them. No-op (returns ``False``) when the lane has no
    persisted context: an orchestrator-driven mission that never created one
    keeps that shape.

    Args:
        repo_root: Main repository root.
        mission_slug: Mission slug used for the lane's context filename (the
            same string the context was saved under).
        lane_id: Lane identifier; ``None`` is a no-op (no lane workspace).
        wp_id: The WP now active in the lane.
        declared_deps: Declared dependencies for this WP.

    Returns:
        True when an existing context was found and refreshed.
    """
    if lane_id is None:
        return False

    from specify_cli.workspace.context import load_context

    context_name = _worktree_dir_name(mission_slug, mission_id=None, lane_id=lane_id)
    existing_ctx = load_context(repo_root, context_name)
    if existing_ctx is None:
        return False
    existing_ctx.wp_id = wp_id
    existing_ctx.current_wp = wp_id
    existing_ctx.dependencies = declared_deps
    save_context(repo_root, existing_ctx)
    return True


def create_lane_workspace(
    repo_root: Path,
    mission_slug: str,
    wp_id: str,
    wp_file: Path,
    resolved_workspace: ResolvedWorkspace,
    lanes_manifest: LanesManifest | None,
    declared_deps: list[str],
    vcs_backend_value: str,
    base: str | None = None,
) -> LaneWorkspaceResult:
    """Create or reuse the execution workspace for the given WP.

    Planning-artifact WPs reuse the repository root directly and do not write a
    lane workspace context file.

    Args:
        repo_root: Repository root.
        mission_slug: Feature slug.
        wp_id: Work package ID.
        wp_file: Path to the WP markdown file (for frontmatter updates).
        resolved_workspace: Canonical workspace contract for the WP.
        lanes_manifest: The computed lanes manifest for code_change WPs.
        declared_deps: Declared dependencies for this WP.
        vcs_backend_value: VCS backend value string (e.g., "git").
        base: Explicit ``--base`` ref, threaded into allocation and recorded
            as the honored base for fresh lane provenance.

    Returns:
        LaneWorkspaceResult with workspace info.
    """
    if resolved_workspace.execution_mode == WorkProductKind.PLANNING_ARTIFACT:
        return LaneWorkspaceResult(
            workspace_path=resolved_workspace.worktree_path,
            branch_name=resolved_workspace.branch_name,
            workspace_name=resolved_workspace.workspace_name,
            lane_id=resolved_workspace.lane_id,
            mission_branch=None,
            is_reuse=False,
            vcs_backend_value=vcs_backend_value,
            execution_mode=resolved_workspace.execution_mode,
            resolution_kind=resolved_workspace.resolution_kind,
        )

    if lanes_manifest is None:
        raise ValueError(f"{wp_id} requires lanes.json workspace allocation metadata")

    lane = lanes_manifest.lane_for_wp(wp_id)
    lane_id = lane.lane_id if lane else "unknown"

    # #3571 follow-up: capture reuse STRUCTURALLY, BEFORE allocation. A lane
    # whose worktree already exists on disk (2nd+ WP in the lane / resume) — or
    # whose branch exists while the worktree was lost (crash-recovery re-attach)
    # — is a genuine reuse; a lane the allocator creates fresh from ``base`` is
    # not. This mirrors the allocator's own fresh-vs-reuse fork and is immune to
    # base divergence. The prior ``_has_commits_beyond_base(honored_base)``
    # content probe misfired here: on a fresh lane rooted on a divergent
    # ``--base``, the recorded planning-commit / dependency-tip merges land as
    # "commits beyond base", which read as reuse — skipping the ``base_commit``
    # provenance write below and defeating ``for_review_gate``'s recorded-
    # honored-base lookup on exactly the divergent-``--base`` lane it exists for.
    predicted_path, predicted_branch = predict_lane_worktree(repo_root, mission_slug, lane_id)
    is_reuse = predicted_path.exists() or branch_exists(repo_root, predicted_branch)

    workspace_path, branch_name = allocate_lane_worktree(
        repo_root=repo_root,
        mission_slug=mission_slug,
        wp_id=wp_id,
        lanes_manifest=lanes_manifest,
        base=base,
    )

    # Install pre-commit ownership guard.
    from specify_cli.policy.hook_installer import install_commit_guard

    hook_guard_record = install_commit_guard(workspace_path, repo_root)
    # #4895: a foreign (non-spec-kitty) pre-existing hook was backed up
    # before being overwritten -- surface the sidecar path in `implement`'s
    # output so the operator can recover it, instead of leaving the
    # preservation silent (the original harm: nothing printed).
    if hook_guard_record is not None and hook_guard_record.backup_path is not None:
        from specify_cli.cli.console import console

        console.print(
            f"[yellow]⚠ Existing .git/hooks/pre-commit was not spec-kitty-managed; "
            f"backed up to {hook_guard_record.backup_path} before installing the "
            f"commit guard.[/yellow]"
        )

    # FR-011 / C-001: record the ACTUAL honored parent, not always
    # ``mission_branch``. ``base`` when supplied (the allocator parented the
    # lane on it, D1); otherwise the SAME topology parent
    # ``allocate_lane_worktree`` itself just used to create the lane
    # (``coordination_branch`` for coord topology, ``mission_branch`` for
    # legacy — mirrors ``_read_coordination_branch``, the private helper the
    # allocator reads internally, so this can never diverge from what was
    # actually created). No-regression pin: a default no-``--base`` coord
    # lane still records ``coordination_branch`` exactly as before.
    coordination_branch = _read_coordination_branch(repo_root, mission_slug)
    topology_parent = coordination_branch if coordination_branch is not None else lanes_manifest.mission_branch
    # WP10 integration (C-4 / #4969): record the ACTUAL honored parent the allocator
    # cut from. When no explicit ``base`` was supplied, the allocator prefers
    # ``origin/<lane>`` when it exists (:func:`resolve_lane_base_ref`), so the
    # provenance we persist must reflect that same origin-aware resolution — not the
    # topology parent the fresh cut may have been shadowed away from.
    if base is not None:
        honored_base = base
    else:
        from specify_cli.workspace.context import resolve_lane_base_ref

        honored_base = resolve_lane_base_ref(repo_root, predicted_branch, fallback_base=topology_parent)

    base_branch = honored_base

    if is_reuse:
        # Reuse — refresh context to reflect the new active WP (#3946).
        refresh_reused_lane_context(repo_root, mission_slug, lane_id, wp_id, declared_deps)
    else:
        # Fresh creation — update frontmatter and create context.
        base_commit_sha = _rev_parse(repo_root, base_branch)
        created_at = now_utc_iso()

        from specify_cli.frontmatter import update_fields

        update_fields(
            wp_file,
            {
                "base_branch": base_branch,
                "base_commit": base_commit_sha,
                "created_at": created_at,
            },
        )

        # FR-006: persist the lane-specific test-DB env so consumers
        # (agents, test runners) do not have to re-derive it. Empty for
        # planning-artifact workspaces; non-empty for code lanes.
        persisted_lane_test_env = lane_test_env(mission_slug, lane_id) if lane_id is not None else {}

        context = WorkspaceContext(
            wp_id=wp_id,
            mission_slug=mission_slug,
            worktree_path=str(workspace_path.relative_to(repo_root)),
            branch_name=branch_name,
            base_branch=base_branch,
            base_commit=base_commit_sha,
            dependencies=declared_deps,
            created_at=created_at,
            created_by="implement-command-lane",
            vcs_backend=vcs_backend_value,
            lane_id=lane_id,
            lane_wp_ids=list(lane.wp_ids) if lane else [],
            current_wp=wp_id,
            lane_test_env=persisted_lane_test_env,
        )
        save_context(repo_root, context)

    return LaneWorkspaceResult(
        workspace_path=workspace_path,
        branch_name=branch_name,
        workspace_name=workspace_path.name,
        lane_id=lane_id,
        mission_branch=lanes_manifest.mission_branch,
        is_reuse=is_reuse,
        vcs_backend_value=vcs_backend_value,
        execution_mode=resolved_workspace.execution_mode,
        resolution_kind=resolved_workspace.resolution_kind,
        # FR-006: derive a lane-suffixed test DB name so two parallel lanes
        # (e.g. SaaS / Django) cannot collide on a shared test database.
        lane_test_env=lane_test_env(mission_slug, lane_id),
    )


def _rev_parse(repo_root: Path, ref: str) -> str:
    result = subprocess.run(
        ["git", "rev-parse", ref],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


# ---------------------------------------------------------------------------
# #3281 (WP03) -- lane-allocation retry self-heal + post-materialize ancestry
# gate (FR-005/FR-006/FR-007, C-005/C-006, C-WP03).
# ---------------------------------------------------------------------------


def _planning_dir(main_repo_root: Path, mission_slug: str) -> Path:
    """PRIMARY-partition mission dir (where ``lanes.json`` lives) for *mission_slug*.

    Routes through the kind-aware placement seam -- the same seam
    :func:`_read_coordination_branch` above and ``orchestrator_api``'s
    ``_planning_read_dir`` use -- so this can never diverge from where the
    allocator itself reads ``lanes.json``/``meta.json``, independent of
    topology (coord-topology missions carry a SEPARATE status/coord dir that
    does NOT hold ``lanes.json``, #2118).
    """
    return placement_seam(main_repo_root, mission_slug).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK)


def reenter_lane_self_heal(
    main_repo_root: Path,
    mission_slug: str,
    wp_id: str,
) -> Path | None:
    """Idempotent self-heal re-entry for a stale lane workspace (FR-005/#3281/C-006).

    Calls :func:`~specify_cli.lanes.worktree_allocator._merge_recorded_planning_commit`
    and :func:`~specify_cli.lanes.worktree_allocator._merge_dependency_lane_tips`
    DIRECTLY -- the exact two calls the allocator's own reuse-path self-heal
    makes -- rather than delegating to the full
    :func:`~specify_cli.lanes.worktree_allocator.allocate_lane_worktree`. That
    full function also runs ``_validate_worktree_clean`` (a real ``git
    status``), which is a DIFFERENT concern (guarding a NEW WP picking up a
    dirty worktree from a prior WP in the same lane) this retry-self-heal
    seam must not couple to: re-entering self-heal for the SAME in-flight WP
    must not hard-fail just because the agent has legitimate uncommitted
    work-in-progress, and git's own merge machinery already refuses a merge
    that would conflict with dirty local changes -- no separate upfront gate
    is needed for allocator-owned lane worktrees. Planning lanes instead reuse
    the canonical root workspace: pending reconciliation there requires a clean,
    unprotected checkout, and only fully approved dependency tips are merged.

    A workspace whose ancestry is already correct is a true no-op: both merge
    helpers short-circuit on their own ``git merge-base --is-ancestor`` check
    (and a manifest with no ``planning_commit_sha`` / no ``depends_on_lanes``
    short-circuits before any git call at all), so calling this on a retry
    never creates a redundant merge commit and never shells out to git for a
    lane with nothing recorded to merge -- preserving the #1832/#1833 no-op-
    resume behaviour observably, even though it is no longer a bare early
    return.

    Returns the worktree path on success, or ``None`` for a legacy/non-lane
    mission (no ``lanes.json``), a WP not assigned to any lane, or a
    not-yet-materialized workspace -- nothing to self-heal in any of those
    cases. A genuine merge conflict propagates as the allocator's own
    structured exception; this helper does not swallow it.
    """
    from specify_cli.lanes.worktree_allocator import (
        _merge_dependency_lane_tips,
        _merge_recorded_planning_commit,
        _validate_worktree_clean,
    )
    from specify_cli.lanes.compute import is_planning_lane
    from specify_cli.ownership.workspace_strategy import create_planning_workspace
    from specify_cli.git import assert_not_protected_branch

    manifest = read_lanes_json(_planning_dir(main_repo_root, mission_slug))
    if manifest is None:
        return None
    lane = manifest.lane_for_wp(wp_id)
    if lane is None:
        return None
    workspace_path: Path
    if is_planning_lane(lane):
        workspace_path = create_planning_workspace(mission_slug, wp_id, list(lane.write_scope), main_repo_root)
        status_dir = placement_seam(main_repo_root, mission_slug).read_dir(MissionArtifactKind.STATUS_STATE)
        if check_claim_ancestry(main_repo_root, mission_slug, status_dir, wp_id, workspace_path).ok:
            return workspace_path
        # Root is shared, not an allocator-owned disposable lane checkout.
        # Refuse protected/dirty roots before the merge helpers can mutate it.
        assert_not_protected_branch(workspace_path, operation="reconcile planning workspace ancestry")
        _validate_worktree_clean(workspace_path, lane.lane_id)
        # A planning lane aggregates multiple WPs' dependencies. Reconcile only
        # the fully approved tips required by the existing claim predicate.
        approved = _approved_dependency_lane_refs(main_repo_root, mission_slug, status_dir, lane, manifest)
        lane = replace(lane, depends_on_lanes=tuple(dep_id for dep_id, _ref in approved))
    else:
        workspace_path, _branch = predict_lane_worktree(main_repo_root, mission_slug, lane.lane_id)
    if not workspace_path.exists():
        return None
    # #4827/WP03/T014: thread the target-branch tip through the shared merge
    # helper here too, mirroring the allocator's own C-006 capture -- this is
    # the SECOND call site D5 centralizes detection through (the allocator's
    # reuse/crash-recovery/fresh-path calls are the other three).
    target_tip = capture_branch_tip(main_repo_root, manifest.target_branch)
    _merge_recorded_planning_commit(main_repo_root, workspace_path, lane.lane_id, manifest.planning_commit_sha, target_tip)
    _merge_dependency_lane_tips(main_repo_root, workspace_path, mission_slug, lane, manifest)
    return workspace_path


@dataclass(frozen=True)
class AncestryCheckResult:
    """Outcome of the POST-materialize claim-ancestry predicate (C-WP03/FR-007).

    ``ok=True`` for a legacy/non-lane WP (nothing to check) or when every
    required ref -- the recorded planning-artifact commit and each APPROVED
    dependency lane's tip -- is a git ancestor of the workspace HEAD.
    ``missing_refs`` names what is not yet an ancestor, for the caller's
    refusal message; empty when ``ok`` is True.
    """

    ok: bool
    missing_refs: tuple[str, ...] = ()


def _workspace_head(workspace_path: Path) -> str | None:
    """Return the commit SHA at ``workspace_path``'s HEAD, or ``None``."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(workspace_path),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _is_git_ancestor(workspace_path: Path, ref: str, head: str) -> bool:
    """``True`` iff ``ref`` is a git ancestor of ``head``, checked at ``workspace_path``."""
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ref, head],
        cwd=str(workspace_path),
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _dependency_lane_status(mission_dir: Path) -> dict[str, str]:
    """Map every WP id to its current lane, read from the STATUS event log.

    ``mission_dir`` is the coord-aware STATUS surface (``read_events``'s
    contract), distinct from :func:`_planning_dir`'s PRIMARY surface --
    callers resolve each once and pass both in rather than this helper
    re-deriving either (FR-007 keeps the two partitions explicit, #2118).
    """
    from specify_cli.status import Lane, read_events, reduce

    events = read_events(mission_dir)
    if not events:
        return {}
    snapshot = reduce(events)
    return {wp_id: str(state.get("lane", Lane.PLANNED)) for wp_id, state in snapshot.work_packages.items()}


def _approved_dependency_lane_refs(
    main_repo_root: Path,
    mission_slug: str,
    mission_dir: Path,
    lane: ExecutionLane,
    lanes_manifest: LanesManifest,
) -> list[tuple[str, str]]:
    """``(dep_lane_id, branch)`` pairs for every FULLY APPROVED dependency lane.

    A dependency lane still in flight (any of its WPs not yet
    ``approved``/``done``) is intentionally OMITTED -- it is not yet an
    ancestry requirement. This is what keeps an approved same-mission
    dependency from deadlocking (C-005): the PRE-materialize dependency-status
    gate (``implement_check_dependency_gate`` / ``start_implementation``'s own
    readiness check) already blocks the claim transition until each of THIS
    WP's declared dependencies is approved; this predicate only additionally
    asserts that the approved sibling-lane CODE actually landed in the merged
    tip, never that an in-flight one has.

    A dependency lane whose branch does not resolve (merged-and-deleted
    post-mission, mirroring ``_merge_dependency_lane_tips``'s own skip) is
    likewise omitted -- there is nothing left to assert ancestry against.
    """
    from specify_cli.status import Lane

    dependency_lanes = _dependency_lane_status(mission_dir)
    by_id = {dep_lane.lane_id: dep_lane for dep_lane in lanes_manifest.lanes}

    refs: list[tuple[str, str]] = []
    for dep_id in lane.depends_on_lanes:
        dep_lane = by_id.get(dep_id)
        if dep_lane is None or not dep_lane.wp_ids:
            continue
        all_approved = all(dependency_lanes.get(wp_id) in (Lane.APPROVED, Lane.DONE) for wp_id in dep_lane.wp_ids)
        if not all_approved:
            continue
        branch = lane_branch_name(mission_slug, dep_id)
        if not branch_exists(main_repo_root, branch):
            continue
        refs.append((dep_id, branch))
    return refs


def _planning_commit_missing_diagnostic(main_repo_root: Path, manifest: LanesManifest) -> str:
    """Diagnostic string for a recorded planning commit absent from HEAD's ancestry.

    #4827/WP03/T014: only called once the ordinary ``_is_git_ancestor`` check
    has already failed (never changes whether the gate fires, only what it
    says). Distinguishes an ``ORPHANED`` pin -- a stale mission-wide record
    only ``finalize-tasks --refresh-planning-commit --allow-orphaned`` can
    fix -- from a merely-not-yet-merged but still reachable pin, using the
    SAME :func:`classify_recorded_pin` classification the allocator's merge
    helper and ``tasks_move_task._mt_resolve_owned_review_base`` use
    (research.md D5), so an orphan never surfaces as three differently
    worded, unreconciled diagnostics.

    ``FOREIGN`` (the object never existed / was GC'd) deliberately falls
    through to the ORIGINAL bare wording, never the orphan recovery hint:
    D3 refuses a foreign object even with ``--allow-orphaned``, so pointing
    at that flag here would name a recovery that cannot actually work.
    """
    assert manifest.planning_commit_sha is not None
    target_tip = capture_branch_tip(main_repo_root, manifest.target_branch)
    pin_class = classify_recorded_pin(main_repo_root, manifest.planning_commit_sha, target_tip)
    if pin_class is PinClass.ORPHANED:
        return (
            f"recorded planning commit {manifest.planning_commit_sha} is orphaned against the target-branch tip; run {ORPHANED_PIN_RECOVERY_HINT!r} to re-point it"
        )
    return f"recorded planning commit {manifest.planning_commit_sha}"


def check_claim_ancestry(
    main_repo_root: Path,
    mission_slug: str,
    mission_dir: Path,
    wp_id: str,
    workspace_path: Path,
) -> AncestryCheckResult:
    """THE shared POST-materialize claim-ancestry predicate (C-WP03/FR-007/C-005).

    MUST be called AFTER the workspace is materialized/self-healed and keyed
    on the MERGED tip -- never pre-materialize and never on a live/unmerged
    branch tip (C-005's deadlock hazard: evaluating ancestry before the
    self-heal merges run rejects an already-approved same-mission dependency
    that simply has not been merged into THIS lane yet).

    The single definition all three claim sites call (the boundary-leak fix):
    the CLI seam (``workflow.py``, between ``_ensure_workspace_materialized``
    and claim emission) and BOTH of ``orchestrator_api/commands.py``'s claim
    paths (``start_implementation``'s composite and ``transition``'s raw
    ``--to claimed``) -- so no caller independently re-derives (and
    potentially diverges on) this decision.
    """
    manifest = read_lanes_json(_planning_dir(main_repo_root, mission_slug))
    if manifest is None:
        return AncestryCheckResult(ok=True)
    lane = manifest.lane_for_wp(wp_id)
    if lane is None:
        return AncestryCheckResult(ok=True)

    head = _workspace_head(workspace_path)
    if head is None:
        # A workspace whose HEAD cannot even be read is orthogonal to THIS
        # predicate -- husk detection (`ResolvedWorkspace.is_husk`) and the
        # post-create "workspace was not materialized" check already cover a
        # genuinely broken/absent worktree upstream of this gate. Failing
        # permissively here (nothing to assert, not a refusal) keeps this
        # predicate scoped to its one job -- ancestry -- rather than
        # re-diagnosing workspace health.
        return AncestryCheckResult(ok=True)

    missing: list[str] = []
    if manifest.planning_commit_sha and not _is_git_ancestor(workspace_path, manifest.planning_commit_sha, head):
        missing.append(_planning_commit_missing_diagnostic(main_repo_root, manifest))
    for dep_id, branch in _approved_dependency_lane_refs(main_repo_root, mission_slug, mission_dir, lane, manifest):
        if not _is_git_ancestor(workspace_path, branch, head):
            missing.append(f"approved dependency lane {dep_id} ({branch})")

    return AncestryCheckResult(ok=not missing, missing_refs=tuple(missing))


def resolve_claim_ancestry_gate(
    main_repo_root: Path,
    mission_slug: str,
    mission_dir: Path,
    wp_id: str,
    workspace_path: Path,
) -> AncestryCheckResult:
    """Ancestry check with self-heal-coupled retry (C-005/FR-005+FR-007 land together).

    On a failed :func:`check_claim_ancestry`, re-enters the idempotent
    self-heal (:func:`reenter_lane_self_heal`) ONCE and rechecks -- callers
    hard-refuse the claim ONLY on this final result, never the bare first
    check, so a workspace that simply had not been self-healed yet never
    spuriously blocks a legitimate claim (a gate without self-heal is a
    dead-end retry, FR-005+FR-007's explicit pairing).
    """
    result = check_claim_ancestry(main_repo_root, mission_slug, mission_dir, wp_id, workspace_path)
    if result.ok:
        return result
    reenter_lane_self_heal(main_repo_root, mission_slug, wp_id)
    return check_claim_ancestry(main_repo_root, mission_slug, mission_dir, wp_id, workspace_path)
