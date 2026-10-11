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
from kernel.git.remote import resolve_remote, tracking_ref
from mission_runtime import MissionArtifactKind, placement_seam
from specify_cli.core.errors import StructuredError
from specify_cli.core.paths import load_meta_fail_closed
from specify_cli.core.git_ops import get_current_branch
from specify_cli.lanes.lane_env import lane_test_env
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.branch_naming import lane_branch_name, worktree_dir_name as _worktree_dir_name
from specify_cli.core.vcs.git import capture_branch_tip
from specify_cli.lanes._git import branch_exists
from specify_cli.lanes.persistence import read_lanes_json, require_lanes_json
from specify_cli.lanes.planning_commit_classify import PinClass, classify_recorded_pin
from specify_cli.lanes.worktree_allocator import (
    ORPHANED_PIN_RECOVERY_HINT,
    _read_coordination_branch,
    allocate_lane_worktree,
    persist_lane_context,
    predict_lane_worktree,
)
from specify_cli.mission_metadata import set_vcs_lock
from specify_cli.workspace.context import ResolvedWorkspace
from specify_cli.workspace.context import WorkspaceContext


def git_stdout(repo_root: Path, args: list[str]) -> str:
    """Run ``git <args>`` in *repo_root* and return stripped stdout, or ``""`` on a non-zero exit.

    The public leaf the ``implement`` planning-commit adapter and the base-ref code import. It is
    deliberately NOT merged with :func:`specify_cli.lanes.lifecycle_sync._git_stdout`, whose contract
    differs: that twin takes variadic ``*args``, tolerates an absent ``cwd`` and returns ``None``
    (not ``""``) when the read fails.
    """
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


class BaseRefUnresolved(StructuredError):
    """``--base`` names a ref that resolves neither locally nor on ``origin``."""

    error_code: str = "BASE_REF_UNRESOLVED"

    def __init__(self, base_ref: str) -> None:
        super().__init__(f"Base ref {base_ref!r} does not resolve")
        self.base_ref = base_ref


class MissionMetaMissing(StructuredError):
    """The mission's ``meta.json`` does not exist (the VCS lock has nothing to lock into)."""

    error_code: str = "MISSION_META_MISSING"

    def __init__(self, feature_dir: Path) -> None:
        super().__init__(f"meta.json not found in {feature_dir}")
        self.feature_dir = feature_dir


class WriteCheckoutWrongBranchError(StructuredError):
    """The repo-root write checkout's HEAD is not the WP's expected branch (#5100 T018)."""

    error_code: str = "WRITE_CHECKOUT_WRONG_BRANCH"


class WriteCheckoutOccupiedError(StructuredError):
    """Another WP is already ``in_progress`` in this single_branch write checkout (#5100 T018)."""

    error_code: str = "WRITE_CHECKOUT_OCCUPIED"


class WriteCheckoutDirtyError(StructuredError):
    """The repo-root write checkout has uncommitted changes outside spec-kitty's own paths (#5100 T018)."""

    error_code: str = "WRITE_CHECKOUT_DIRTY"


def _owned_status_prefixes(mission_slug: str) -> tuple[str, ...]:
    """Spec-kitty-owned path prefixes to exclude from the dirty-checkout scan.

    A single_branch mission's status log and snapshot live on the PRIMARY
    partition (no coordination worktree), and ``.kittify/`` and ``.spec-kitty/``
    (the review lock ``agent action review`` writes untracked into the repo
    root) hold spec-kitty's own runtime state -- none is the operator's own
    uncommitted work. The two directories mirror the runtime-state authority
    ``_RUNTIME_STATE_DENY_LIST`` in ``cli/commands/agent/tasks_shared.py``;
    ``lanes/`` sits below the CLI layer, so it names them here instead of
    importing a private CLI constant. ``meta.json`` is included too:
    ``implement`` itself writes to it earlier in the SAME call
    (``_ensure_vcs_in_meta`` locks the VCS backend on a mission's first
    claim) -- without this, that self-inflicted write would make every
    first-ever single_branch claim refuse itself as "dirty".
    """
    return (
        f"kitty-specs/{mission_slug}/status.events.jsonl",
        f"kitty-specs/{mission_slug}/status.json",
        f"kitty-specs/{mission_slug}/meta.json",
        ".kittify/",
        ".spec-kitty/",
    )


def _is_single_branch_mission(repo_root: Path, mission_slug: str) -> bool:
    """Return whether *mission_slug*'s STORED topology is ``single_branch``.

    #5100 WP04 cycle-2 fix (review issue 1): a planning_artifact WP of EVERY
    topology resolves to the same ``lane-planning`` repo-root lane
    (``is_repo_root_lane``), so gating the write-checkout refusals on the
    LANE alone fired them for lanes/coord missions too -- breaking the
    ordinary "dirty while planning" case those topologies have always
    allowed. ``contracts/single-branch-execution.md`` scopes "Implement:
    refusals" to single_branch missions only; this is the topology gate that
    enforces that scope. Uses the canonical stored-topology read
    (:func:`mission_runtime.resolve_topology`), never re-derived here.
    """
    from mission_runtime import is_single_branch, resolve_topology

    return is_single_branch(resolve_topology(repo_root, mission_slug))


def _ensure_repo_root_checkout_available(
    repo_root: Path,
    mission_slug: str,
    wp_id: str,
    resolved_workspace: ResolvedWorkspace,
    *,
    occupancy_verified: bool = False,
) -> bool:
    """Enforce the repo-root-lane refusal order (contract order 2-4, #5100 T018).

    Refusal 1 (unmigrated) is NOT checked here: it never reaches this arm.
    An unmigrated single_branch mission's WPs are still assigned to CODE
    lanes in ``lanes.json`` (the re-stamp migration has not run), so
    :func:`~specify_cli.lanes.compute.is_repo_root_lane` never routes them to
    this repo-root arm in the first place -- they resolve through the
    ordinary code-lane path unchanged (contracts/single-branch-execution.md).

    Scoped to single_branch missions ONLY (cycle-2 fix, review issue 1): a
    planning_artifact WP of a lanes/coord mission ALSO resolves to the
    repo-root ``lane-planning`` lane, but that mission's repo-root checkout
    is the ordinary shared planning root, not the single_branch write
    checkout this refusal order protects -- a dirty planning root or a
    non-target HEAD there is normal and must stay allowed. A no-op (returns
    immediately) for every other topology.

    Order (single_branch only):
      2. Wrong branch -- refuses unconditionally (no resume exemption).
      3. Occupied -- another WP (any single_branch mission) ``in_progress``
         in this checkout. ``exclude`` already drops this WP's own entry, so
         resuming itself is structurally never "another WP". The scan reads
         every candidate mission's status log, so a caller that already ran
         it earlier in the SAME ``implement`` call passes
         ``occupancy_verified=True`` to skip the repeat. That is sound
         because the caller holds the write-checkout claim lock
         (:func:`~specify_cli.status.write_checkout_claim_lock`) from the
         scan to the claim emit: the claim that would change the answer
         cannot land in between (#5796).
      4. Dirty -- skipped when THIS wp_id is itself already ``in_progress``
         (a genuine resume; the checkout is expected to carry its own
         uncommitted work).

    Returns:
        ``True`` when the occupancy scan ran (or was already verified) for
        this call, so the caller can thread it into a later repeat check;
        ``False`` when the mission is not single_branch and nothing was checked.
    """
    if not _is_single_branch_mission(repo_root, mission_slug):
        return False

    from specify_cli.lanes.checkout_occupancy import dirty_paths, in_progress_wps_in_write_checkout
    from specify_cli.status import Lane
    from specify_cli.status import get_wp_lane, has_event_log

    write_checkout = resolved_workspace.worktree_path
    expected_branch = resolved_workspace.branch_name
    if expected_branch is None:
        # A planning_artifact WP resolves no branch expectation of its own (its
        # repo root is the ordinary planning root in every other topology), but
        # in a single_branch mission it shares THIS write checkout and must
        # sit on the mission's write branch just like a code WP -- take it from
        # the same single rule, regardless of WP kind.
        from mission_runtime import resolve_single_branch_write_ref
        from specify_cli.core.paths import get_feature_target_branch

        expected_branch = resolve_single_branch_write_ref(repo_root, mission_slug, get_feature_target_branch(repo_root, mission_slug))
    current_branch = get_current_branch(write_checkout)
    if current_branch != expected_branch:
        raise WriteCheckoutWrongBranchError(
            f"The write checkout at {write_checkout} is on branch "
            f"{current_branch!r}, but {mission_slug} {wp_id} expects "
            f"{expected_branch!r}. Check out {expected_branch!r} in "
            f"{write_checkout} before retrying."
        )

    occupants = [] if occupancy_verified else in_progress_wps_in_write_checkout(repo_root, write_checkout, exclude=(mission_slug, wp_id))
    if occupants:
        other_mission, other_wp = occupants[0]
        # The scan only reports missions whose write branch is the branch the
        # checkout is on (#5680), or whose write branch is unknown and so
        # counts fail-closed; the wrong-branch refusal above pinned the
        # checkout's branch to expected_branch.
        raise WriteCheckoutOccupiedError(
            f"{other_mission} {other_wp} is already in_progress in the shared "
            f"write checkout at {write_checkout} on branch {expected_branch!r}. "
            f"Move {other_wp} out of in_progress (approve, reject, or block it) "
            f"before claiming {mission_slug} {wp_id}. If {other_mission} is "
            f"finished or abandoned, run: spec-kitty agent tasks move-task "
            f'{other_wp} --to blocked --mission {other_mission} --note "<reason>" '
            "(use --to canceled instead if the work is abandoned)"
        )

    status_feature_dir = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.STATUS_STATE)
    # has_event_log guard: a caller reaching this arm before the event log
    # is bootstrapped (e.g. a direct unit-level call to this function,
    # bypassing implement's own earlier ``ensure_wp_claim_preconditions``
    # seeded-WP check) has, by construction, no recorded claim -- never a
    # resume.
    is_resume = has_event_log(status_feature_dir) and get_wp_lane(status_feature_dir, wp_id) == Lane.IN_PROGRESS
    if not is_resume:
        dirty = dirty_paths(write_checkout, owned_prefixes=_owned_status_prefixes(mission_slug))
        if dirty:
            listed = ", ".join(dirty)
            raise WriteCheckoutDirtyError(
                f"The write checkout at {write_checkout} has uncommitted changes: {listed}. Commit or stash them before claiming {mission_slug} {wp_id}."
            )
    return True


def guard_repo_root_claim(
    repo_root: Path,
    mission_slug: str,
    wp_id: str,
    resolved_workspace: ResolvedWorkspace,
    *,
    occupancy_verified: bool = False,
) -> None:
    """Guard and record a claim on a repo-root lane: the ONE claim seam both claim verbs share.

    Runs the write-checkout refusal order (wrong branch / occupied / dirty;
    single_branch only) BEFORE recording the claim base, so a refusal never
    leaves a stray claim-base ref behind. The claim base is recorded once
    (idempotent-by-absence) so the for_review gate has a starting point to
    diff against (WP02/T007, contracts/single-branch-execution.md "Claim base
    and for_review").

    ``implement`` reaches this through :func:`create_lane_workspace`;
    ``agent action implement`` calls it directly, because the repository root
    checkout always exists and so never goes through workspace creation
    (#5459).
    """
    _ensure_repo_root_checkout_available(repo_root, mission_slug, wp_id, resolved_workspace, occupancy_verified=occupancy_verified)

    from specify_cli.lanes.claim_base import record_claim_base

    record_claim_base(repo_root, repo_root, mission_slug, wp_id)


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
    # #4895/#5715: where a foreign (non-spec-kitty) ``.git/hooks/pre-commit``
    # was backed up before the commit guard replaced it. ``None`` when nothing
    # was backed up. The command layer prints the notice; this seam never does.
    # Every caller MUST surface it (``implement_phases._report_hook_backup``), or
    # the #4895 harm returns: the hook is preserved but nobody is told where.
    hook_backup_path: Path | None = None
    #: This call wrote ``base_branch``/``base_commit``/``created_at`` into the claimed WP prompt (a fresh lane only).
    #: Reported by the writer itself, so a concurrent edit to the prompt is never mistaken for the claim's stamp (#5673).
    wp_stamped: bool = False

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

    context_name = _worktree_dir_name(mission_slug, lane_id=lane_id)
    existing_ctx = load_context(repo_root, context_name)
    if existing_ctx is None:
        return False
    existing_ctx.wp_id = wp_id
    existing_ctx.current_wp = wp_id
    existing_ctx.dependencies = declared_deps
    persist_lane_context(repo_root, existing_ctx)
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
    occupancy_verified: bool = False,
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
        occupancy_verified: The caller already ran the write-checkout
            occupancy scan earlier in this same call (``implement``'s early
            refusal), so the repo-root arm skips repeating that full-repo
            scan; wrong-branch and dirty checks still repeat (cheap).

    Returns:
        LaneWorkspaceResult with workspace info.
    """
    from specify_cli.lanes.compute import is_repo_root_lane

    if is_repo_root_lane(resolved_workspace):
        # Repo-root lane: the WP executes directly in the write checkout
        # (``repo_root``), with no worktree of its own. Keyed on the LANE,
        # not the WP kind (T009): WP05 routes single_branch code WPs through
        # this same arm. #5100 T018: enforce the write-checkout refusal
        # order (wrong branch / occupied / dirty) BEFORE recording the claim
        # base, so a refusal never leaves a stray claim-base ref behind.
        guard_repo_root_claim(repo_root, mission_slug, wp_id, resolved_workspace, occupancy_verified=occupancy_verified)
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
    # #5115/WP07: the lane-tip recorder is installed inside
    # ``allocate_lane_worktree`` itself (worktree_allocator.py), the single
    # choke point every route/caller passes through -- not duplicated here.
    # #4895: a foreign (non-spec-kitty) pre-existing hook was backed up
    # before being overwritten -- carry the sidecar path on the result so
    # `implement` surfaces it and the operator can recover it, instead of
    # leaving the preservation silent (the original harm: nothing printed).
    # #5715: this seam returns the path; the command layer prints it.
    hook_backup_path = hook_guard_record.backup_path if hook_guard_record is not None else None

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

    wp_stamped = False
    if is_reuse:
        # Reuse — refresh context to reflect the new active WP (#3946).
        refresh_reused_lane_context(repo_root, mission_slug, lane_id, wp_id, declared_deps)
    else:
        # Fresh creation — update frontmatter and create context.
        base_commit_sha = _rev_parse(repo_root, base_branch)
        created_at = now_utc_iso()

        from specify_cli.frontmatter import locked_update_frontmatter

        provenance = {
            "base_branch": base_branch,
            "base_commit": base_commit_sha,
            "created_at": created_at,
        }
        # A locked read-modify-write of the work package as it is now (plan A10): a field or note another
        # writer landed since the claim began (a map-requirements ref) survives.
        locked_update_frontmatter(wp_file, lambda frontmatter: frontmatter.update(provenance), feature_dir=wp_file.parent.parent, repo_root=repo_root)
        wp_stamped = True

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
        persist_lane_context(repo_root, context)

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
        hook_backup_path=hook_backup_path,
        wp_stamped=wp_stamped,
    )


def _rev_parse(repo_root: Path, ref: str) -> str:
    # ``--verify --end-of-options`` forces ``ref`` to be read as a single
    # positional revision, so a ref beginning with ``-`` can never be parsed as
    # a git option (Sonar pythonsecurity:S6350); argv form already precludes
    # shell injection. ``--verify`` keeps the output a single SHA (plain
    # ``rev-parse --end-of-options`` echoes the flag itself); the sole caller
    # passes a branch name that resolves to exactly one commit, and an
    # unresolvable ref still exits non-zero and yields ``"unknown"`` as before.
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--end-of-options", ref],
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
        branch: str | None = None
    else:
        workspace_path, branch = predict_lane_worktree(main_repo_root, mission_slug, lane.lane_id)
    if not workspace_path.exists():
        return None
    # #4827/WP03/T014: thread the target-branch tip through the shared merge
    # helper here too, mirroring the allocator's own C-006 capture -- this is
    # the SECOND call site D5 centralizes detection through (the allocator's
    # reuse/crash-recovery/fresh-path calls are the other three).
    target_tip = capture_branch_tip(main_repo_root, manifest.target_branch)
    _merge_recorded_planning_commit(main_repo_root, workspace_path, lane.lane_id, manifest.planning_commit_sha, target_tip, mission_slug=mission_slug)
    _merge_dependency_lane_tips(main_repo_root, workspace_path, mission_slug, lane, manifest)
    if branch is not None:
        # #5115/WP07 (FR-018): a CODE lane self-heal re-entry (never the
        # planning lane, which has no ``-lane-``-matching branch of its own
        # to record a tip for) refreshes its tip too.
        from specify_cli.lanes.lane_tip import record_tip

        record_tip(main_repo_root, branch)
    return workspace_path


@dataclass(frozen=True)
class AncestryCheckResult:
    """Outcome of the POST-materialize claim-ancestry predicate (C-WP03/FR-007).

    ``ok=True`` for a legacy/non-lane WP (nothing to check) or when every
    required ref -- the recorded planning-artifact commit and each APPROVED
    dependency lane's tip -- is a git ancestor of the workspace HEAD.
    ``missing_refs`` names what is not yet an ancestor, for the caller's
    refusal message; empty when ``ok`` is True.

    ``code_lanes_deferred_to`` is the target branch when the #5296 waiver
    applied (a planning-lane claim on the target-branch root checkout): the
    caller that owns console output tells the operator that code lanes reach
    that branch through ``spec-kitty consolidate``. ``None`` otherwise.
    """

    ok: bool
    missing_refs: tuple[str, ...] = ()
    code_lanes_deferred_to: str | None = None


def _workspace_head(workspace_path: Path) -> str | None:
    """Return the commit SHA at ``workspace_path``'s HEAD, or ``None``.

    An unborn HEAD or a path outside any repository resolves to ``None``,
    exactly as the verified ``rev-parse`` probe of :func:`_rev_parse_ref` maps
    a ref that does not resolve to ``""``.
    """
    return _rev_parse_ref(workspace_path, "HEAD") or None


def _is_git_ancestor(workspace_path: Path, ref: str, head: str) -> bool:
    """``True`` iff ``ref`` is a git ancestor of ``head``, checked at ``workspace_path``."""
    # ``--end-of-options`` keeps ``ref``/``head`` positional, so neither can be
    # read as a git option if it begins with ``-`` (Sonar S6350 sibling of
    # :func:`_rev_parse`; argv form already precludes shell injection).
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", "--end-of-options", ref, head],
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


def _root_checkout_is_target(main_repo_root: Path, lanes_manifest: LanesManifest) -> bool:
    """``True`` iff the repository root checkout's HEAD is the mission target branch.

    Detached HEAD or an unresolvable HEAD is ``False`` (the waiver never fires).
    """
    result = subprocess.run(
        ["git", "symbolic-ref", "--short", "-q", "HEAD"],
        cwd=str(main_repo_root),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False
    return bool(result.stdout.strip() == lanes_manifest.target_branch)


def _planning_claim_waives_code_lanes(main_repo_root: Path, lane: ExecutionLane, lanes_manifest: LanesManifest) -> bool:
    """``True`` for the #5296 waiver scope: planning lane AND root checkout on the target."""
    from specify_cli.lanes.compute import is_planning_lane

    return is_planning_lane(lane) and _root_checkout_is_target(main_repo_root, lanes_manifest)


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

    #5296 waiver (the ONLY place it lives): a claim of the canonical planning
    lane (:func:`is_planning_lane`) whose repository root checkout HEAD is the
    mission's target branch requires NO code-lane ancestry -- this returns
    ``[]``. The planning lane's workspace IS that root checkout, so merging
    code dependency lanes into it would land code on the target (or die with
    ``ProtectedBranchCommitError`` on a protected target) outside
    ``spec-kitty consolidate``'s attribution window; code lanes reach the
    target only through consolidation. Every dependency lane of the planning
    lane other than itself is a code lane, so nothing narrower is needed. A
    planning lane with the root on any OTHER branch, and every code lane,
    are unchanged.
    """
    from specify_cli.status import Lane

    if _planning_claim_waives_code_lanes(main_repo_root, lane, lanes_manifest):
        return []

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
        branch = lane_branch_name(mission_slug, dep_id, target_branch=lanes_manifest.target_branch)
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
    and claim emission) and BOTH of ``orchestrator_api/wp_lifecycle.py``'s claim
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

    deferred = manifest.target_branch if _planning_claim_waives_code_lanes(main_repo_root, lane, manifest) else None
    return AncestryCheckResult(ok=not missing, missing_refs=tuple(missing), code_lanes_deferred_to=deferred)


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


def _rev_parse_ref(repo_root: Path, ref: str) -> str:
    """Return the full SHA *ref* resolves to, or ``""`` when it does not resolve.

    ``--end-of-options`` keeps a leading-dash ref (e.g. ``--git-dir``) from being
    consumed as a rev-parse option (#1917); ``--verify --quiet`` yields an empty
    stdout + non-zero exit on a missing ref, which :func:`git_stdout` maps to
    ``""``.
    """
    return git_stdout(repo_root, ["rev-parse", "--verify", "--quiet", "--end-of-options", ref])


def _is_ancestor(repo_root: Path, maybe_ancestor: str, descendant: str) -> bool:
    """Return whether *maybe_ancestor* is an ancestor of (or equal to) *descendant*."""
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", maybe_ancestor, descendant],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return result.returncode == 0


def resolve_base_ref(repo_root: Path, base_ref: str) -> tuple[str, str] | None:
    """Resolve ``--base`` to ``(effective_ref, sha)``, preferring ``origin/<lane>`` (#4969).

    A teammate's pushed approved lane on ``origin/<base_ref>`` must NOT be
    shadowed by a fresh/stale local cut from ``main``: when ``origin/<base_ref>``
    resolves AND the local ``base_ref`` is either absent or strictly behind it (an
    ancestor of the origin tip), the origin ref wins. A local ref that is ahead of
    (or unrelated to) origin is kept, and a ref that resolves nowhere returns
    ``None`` so the caller can fail closed. The origin-aware base cutting itself
    (threading ``effective_ref`` into worktree allocation) is coordinated with
    WP04's ``workspace/context.py`` / ``lanes/compute.py``; this WP owns only the
    ``implement.py`` resolution site.
    """
    local_sha = _rev_parse_ref(repo_root, base_ref)
    remote = resolve_remote(repo_root, base_ref) or "origin"
    # The effective ref NAME stays the short ``<remote>/<base>`` form callers and
    # messages show; the probe uses the shared fully-qualified builder (FR-016).
    origin_ref = f"{remote}/{base_ref}"
    origin_sha = _rev_parse_ref(repo_root, tracking_ref(remote, base_ref))
    if origin_sha and (not local_sha or _is_ancestor(repo_root, local_sha, origin_sha)):
        return origin_ref, origin_sha
    if local_sha:
        return base_ref, local_sha
    return None


def refuse_repo_root_checkout_if_unavailable(
    repo_root: Path,
    mission_slug: str,
    wp_id: str,
    resolved_workspace: ResolvedWorkspace,
) -> bool:
    """Run the repo-root write-checkout refusals early (no side effects).

    Returns ``True`` when the occupancy scan ran, so ``implement`` threads it
    into ``create_lane_workspace`` and the full-repo scan runs once per call.
    """
    from specify_cli.lanes.compute import is_repo_root_lane

    if is_repo_root_lane(resolved_workspace):
        return _ensure_repo_root_checkout_available(repo_root, mission_slug, wp_id, resolved_workspace)
    return False


def resolve_effective_base(repo_root: Path, base: str | None, resolved_workspace: ResolvedWorkspace) -> tuple[str | None, bool]:
    """Resolve ``--base`` to ``(effective_base, ignored_on_planning_lane)`` (#1684, #3571).

    ``effective_base`` is ``None`` when ``--base`` was not supplied or the workspace is a
    repository-root planning lane, where ``--base`` has no effect (FR-007); the second element
    then reports whether the flag was supplied and ignored, so the caller can warn. Otherwise
    the base resolves origin-first (#4969) and the effective ref name is returned.

    Raises :class:`BaseRefUnresolved` when the ref resolves neither locally nor on ``origin``.
    """
    from specify_cli.lanes.compute import is_planning_lane

    if base is None:
        return None, False
    if is_planning_lane(resolved_workspace):
        return None, True
    resolved = resolve_base_ref(repo_root, base)
    if resolved is None:
        raise BaseRefUnresolved(base)
    return resolved[0], False


def resolve_execution_lane(resolved_workspace: ResolvedWorkspace, lanes_feature_dir: Path, wp_id: str) -> tuple[LanesManifest | None, ExecutionLane | None]:
    """Resolve ``(lanes_manifest, lane)`` for a lane workspace, or ``(None, None)`` for a repository-root planning workspace.

    Raises ``MissingLanesError`` / ``CorruptLanesError`` from the manifest read and ``ValueError``
    when *wp_id* is assigned to no lane.
    """
    from specify_cli.lanes.compute import is_repo_root_lane

    if is_repo_root_lane(resolved_workspace):
        return None, None
    lanes_manifest = require_lanes_json(lanes_feature_dir)
    lane = lanes_manifest.lane_for_wp(wp_id)
    if lane is None:
        raise ValueError(f"{wp_id} is not assigned to any lane in lanes.json")
    return lanes_manifest, lane


def ensure_vcs_locked(feature_dir: Path, *, repo_root: Path | None = None) -> bool:
    """Lock the VCS backend to git in ``meta.json`` on a mission's first claim; return whether it wrote the lock.

    Hard-fails on a missing or malformed ``meta.json`` (post-#2091 contract: ``allow_missing``
    semantics must never mask the guard): raises :class:`MissionMetaMissing` or
    ``MissionMetaReadError``.

    The read-modify-write of ``meta.json`` runs under the Mission write lock (re-entrant),
    because the claim commit stages that file and a concurrent claim would otherwise
    commit or overwrite a half-written copy (#5468, plan A6).
    """
    from specify_cli.status import UNBOUNDED_LOCK_WAIT, mission_write_lock

    with mission_write_lock(feature_dir, repo_root=repo_root, timeout=UNBOUNDED_LOCK_WAIT):
        meta = load_meta_fail_closed(feature_dir)
        if meta is None:
            raise MissionMetaMissing(feature_dir)
        if "vcs" in meta:
            return False
        set_vcs_lock(feature_dir, vcs_type="git", locked_at=now_utc_iso())
        return True
