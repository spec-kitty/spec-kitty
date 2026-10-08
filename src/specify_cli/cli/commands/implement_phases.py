"""Ordered phases of ``spec-kitty implement`` and the immutable values they pass along.

Each phase is built once, by exactly one phase function, and never changes afterwards
(data-model.md, "Phase results"). The command (``implement.py``) owns the tracker steps and their
exception handling; the phases raise and never render the tracker.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn

import typer
from rich.panel import Panel
from specify_cli.cli.console import console

from mission_runtime import MissionArtifactKind, placement_seam
from specify_cli.cli.commands import implement_claim, implement_planning_commit
from specify_cli.cli.selector_resolution import resolve_mission_handle
from specify_cli.coordination import planning_commit as coordination_planning_commit
from specify_cli.core import dependency_graph
from specify_cli.core.errors import PlacementResolutionRequired
from specify_cli.core.paths import MissionMetaReadError
from specify_cli.core.vcs import VCSBackend
from specify_cli.missions._read_path_resolver import mission_write_lock_dir
from specify_cli.git.commit_helpers import (
    SafeCommitHeadMismatch,
    SafeCommitPathPolicyError,
)
from specify_cli.lanes import implement_support
from specify_cli.lanes.implement_support import create_lane_workspace
from specify_cli.status import UNBOUNDED_LOCK_WAIT, mission_write_lock, read_events, reduce as reduce_status_events
from specify_cli.workspace import context as workspace_context
from specify_cli.workspace.context import resolve_workspace_for_wp

if TYPE_CHECKING:
    from contextlib import ExitStack

    from specify_cli.lanes.implement_support import LaneWorkspaceResult
    from specify_cli.lanes.models import ExecutionLane, LanesManifest
    from specify_cli.workspace.context import ResolvedWorkspace


@dataclass(frozen=True)
class ImplementContext:
    """The ``detect`` phase result: where the mission lives and what the WP declares."""

    repo_root: Path
    auto_commit: bool | None
    mission_slug: str
    mission_dir: Path
    wp_file: Path
    declared_deps: list[str]


@dataclass(frozen=True)
class ClaimPreflight:
    """The claim-preflight result: the target branch and the two surfaces the claim reads."""

    planning_branch: str
    status_feature_dir: Path
    lanes_feature_dir: Path


@dataclass(frozen=True)
class WorkspaceSelection:
    """The workspace/lane selection result."""

    resolved_workspace: ResolvedWorkspace
    lanes_manifest: LanesManifest | None
    lane: ExecutionLane | None


@dataclass(frozen=True)
class AllocationResult:
    """The ``allocate`` phase result: the allocated workspace plus the effective ``--base``."""

    result: LaneWorkspaceResult
    effective_base: str | None


def detect_mission_context(
    mission_flag: str | None = None,
    repo_root: Path | None = None,
    *,
    json_mode: bool = False,
) -> tuple[str | None, str]:
    """Require an explicit mission slug and return ``(mission_number, slug)``.

    Uses the canonical mission resolver (resolve_mission_handle) when
    repo_root is supplied, falling back to bare slug parsing otherwise.
    The repo_root is always available in the callers that matter.
    """
    import re as _re

    raw_handle = mission_flag
    if raw_handle is None:
        console.print("[red]Error:[/red] --mission <slug> is required")
        raise typer.Exit(1)

    if repo_root is not None:
        # Use canonical resolver — handles ambiguity, mid8, full ULID, etc.
        resolved = resolve_mission_handle(raw_handle, repo_root, json_mode=json_mode)
        slug = resolved.mission_slug
    else:
        # Bare-slug fallback for callers without a repo_root (e.g., unit tests).
        slug = raw_handle

    match = _re.match(r"^(\d{3})-", slug)
    return (match.group(1) if match else None), slug


_BASE_REF_UNRESOLVED_MSG = "[red]Error:[/red] Base ref '{base_ref}' does not resolve. Try 'git fetch' or 'git branch -a' to see available refs."


def _raise_base_ref_unresolved(base_ref: str) -> NoReturn:
    """Print the single canonical unresolved-base error and exit non-zero."""
    console.print(_BASE_REF_UNRESOLVED_MSG.format(base_ref=base_ref))
    raise typer.Exit(1)


def _validate_base_ref(repo_root: Path, base_ref: str) -> str:
    """Validate ``--base`` and return the effective (origin-preferred) base SHA.

    #4969: consults ``origin/<base_ref>`` and prefers it over a local cut that is
    absent or behind it, so a teammate's pushed approved lane is not shadowed (see
    :func:`implement_support.resolve_base_ref`). Raises typer.Exit(1) with a clear error message
    when the ref resolves neither locally nor on ``origin``.
    """
    resolved: tuple[str, str] | None = implement_support.resolve_base_ref(repo_root, base_ref)
    if resolved is None:
        _raise_base_ref_unresolved(base_ref)
    return resolved[1]


def _ensure_vcs_in_meta(feature_dir: Path, repo_root: Path | None = None) -> VCSBackend:
    """Ensure VCS is selected and locked in meta.json (printing adapter over the seam's decision)."""
    try:
        locked = implement_support.ensure_vcs_locked(feature_dir, repo_root=repo_root)
    except MissionMetaReadError as exc:
        console.print(f"[red]Error:[/red] Invalid JSON in meta.json: {exc}")
        raise typer.Exit(1) from exc
    except implement_support.MissionMetaMissing as exc:
        console.print(f"[red]Error:[/red] meta.json not found in {feature_dir}")
        console.print("Run /spec-kitty.specify inside your coding agent (Claude Code, Codex, Cursor) first to create the feature structure")
        raise typer.Exit(1) from exc
    if locked:
        console.print("[cyan]→ VCS locked to git in meta.json[/cyan]")
    return VCSBackend.GIT


# ---------------------------------------------------------------------------
# T017: implement() decomposition helpers -- each owns one leaf decision or
# side effect so the Typer-shell function itself stays a thin orchestration
# sequence (S3776 <=15). None of these change externally-observed behavior;
# see the WP03 tracer for the extraction rationale.
# ---------------------------------------------------------------------------


def _detect_wp_context(
    mission: str,
    wp_id: str,
    repo_root: Path,
    auto_commit: bool | None,
    *,
    json_mode: bool = False,
) -> tuple[bool | None, str, Path, Path, Any]:
    """Resolve ``(auto_commit, mission_slug, feature_dir, wp_file,
    declared_deps)`` for the ``detect`` step. Exceptions propagate to the
    caller's tracker-aware ``except`` clause unchanged."""
    from specify_cli.core.agent_config import get_auto_commit_default
    from specify_cli.core.dependency_graph import parse_wp_dependencies

    if auto_commit is None:
        auto_commit = get_auto_commit_default(repo_root)
    _mission_number, mission_slug = detect_mission_context(mission, repo_root=repo_root, json_mode=json_mode)
    # read-surface-ssot-closeout WP05 / FR-001 / NFR-001: route through the
    # kind-aware placement seam instead of the kind-blind
    # ``resolve_feature_dir_for_mission`` (which could return the
    # coordination worktree's mission dir once materialized -- the #2453
    # coord-husk-shadows-primary defect NFR-001 closes). ``SPEC`` is a
    # PRIMARY-partition kind (mission_runtime.artifacts), so ``read_dir``
    # resolves the topology-blind primary directory directly: the SAME
    # directory every downstream read in this function needs (meta.json,
    # spec.md, tasks.md, the occurrence-map gate). This collapses the
    # former three-step meta.json-existence cascade (resolve -> candidate
    # fallback -> primary fallback), which existed ONLY to paper over the
    # kind-blind resolver's coord-husk shadowing -- the kind-correct seam
    # never returns a meta-less coord husk in the first place.
    feature_dir = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.SPEC)
    wp_file = workspace_context.find_wp_file(repo_root, mission_slug, wp_id)
    declared_deps = parse_wp_dependencies(wp_file)
    return auto_commit, mission_slug, feature_dir, wp_file, declared_deps


def _run_bulk_edit_gate_and_inference(feature_dir: Path, wp_file: Path, mission_slug: str, wp_id: str, acknowledge_not_bulk_edit: bool) -> None:
    """Bulk-edit occurrence-classification gate (FR-006) + inference warning
    (FR-009). Raises ``typer.Exit(1)`` on a gate failure or an un-acknowledged
    triggered inference; a silent return means the claim may proceed."""
    from specify_cli.bulk_edit.gate import ensure_occurrence_classification_ready, render_gate_failure

    gate_result = ensure_occurrence_classification_ready(feature_dir)
    if not gate_result.passed:
        render_gate_failure(gate_result, console)
        raise typer.Exit(1)

    # FR-012 / NFR-001: key on the ONE canonical check (``== "bulk_edit"``), not
    # implicit presence. A legacy ``change_mode`` value must behave identically to
    # absence — both fall through to the inference scan below — so normalizing a
    # legacy value to absent stays behavior-preserving.
    if gate_result.change_mode == "bulk_edit":
        return

    from specify_cli.bulk_edit.inference import (
        scan_spec_file,
        wp_authors_bulk_edit_planning_artifact,
    )

    inference = scan_spec_file(feature_dir)
    planning_wp = wp_authors_bulk_edit_planning_artifact(wp_file, mission_slug)
    if inference.triggered and planning_wp:
        matched = ", ".join(f"'{p}' ({w}pt)" for p, w in inference.matched_phrases)
        console.print(
            Panel(
                f"This mission's spec contains language suggesting a bulk edit "
                f"(score: {inference.score}/{inference.threshold}), but {wp_id} owns "
                f"the occurrence-map planning artifact.\n"
                f"  Matched: {matched}\n\n"
                f"Continuing without --acknowledge-not-bulk-edit for this planning WP.",
                title="[bold yellow]Bulk Edit Inference Informational[/]",
                border_style="yellow",
            )
        )
        return
    if inference.triggered and not acknowledge_not_bulk_edit:
        matched = ", ".join(f"'{p}' ({w}pt)" for p, w in inference.matched_phrases)
        console.print(
            Panel(
                f"This mission's spec contains language suggesting a bulk edit "
                f"(score: {inference.score}/{inference.threshold}):\n"
                f"  Matched: {matched}\n\n"
                f"If this IS a bulk edit, set change_mode to 'bulk_edit' in meta.json.\n"
                f"If it is NOT, re-run with --acknowledge-not-bulk-edit to suppress.",
                title="[bold yellow]Bulk Edit Inference Warning[/]",
                border_style="yellow",
            )
        )
        raise typer.Exit(1)


def _resolve_effective_base(repo_root: Path, base: str | None, resolved_workspace: Any) -> str | None:
    """Validate ``--base`` and return the effective base to thread through ``create_lane_workspace``.

    Prints the planning-lane "ignored" warning (FR-007) and translates the seam's
    ``BaseRefUnresolved`` into the single canonical unresolved-base message plus exit 1. This runs
    inside ``implement``'s create ``try``, so ``except typer.Exit`` renders the tracker unchanged.
    """
    effective_base: str | None
    try:
        effective_base, ignored = implement_support.resolve_effective_base(repo_root, base, resolved_workspace)
    except implement_support.BaseRefUnresolved as exc:
        _raise_base_ref_unresolved(exc.base_ref)
    if ignored:
        console.print("[yellow]Warning:[/yellow] --base is ignored for repository-root planning work")
    return effective_base


# ---------------------------------------------------------------------------
# The phase sequence. Each body is the block ``implement()`` ran between its
# tracker calls, moved unchanged; it unpacks the earlier phase values into the
# local names the block used and returns the value it used to bind.
# ---------------------------------------------------------------------------


def detect_context(mission: str, wp_id: str, repo_root: Path, auto_commit: bool | None, *, json_mode: bool) -> ImplementContext:
    """Charter preflight, then resolve the mission and the WP (the ``detect`` step)."""
    json_output = json_mode
    # FR-006 caller contract (T024): charter preflight runs BEFORE
    # any worktree allocation or .kittify/ modification. On failure
    # we exit 1 with the blocked_reason — no state mutation.
    from specify_cli.charter_runtime.preflight.hook import run_preflight_or_abort

    run_preflight_or_abort(repo_root, consumer="implement")
    auto_commit, mission_slug, feature_dir, wp_file, declared_deps = _detect_wp_context(mission, wp_id, repo_root, auto_commit, json_mode=json_output)
    return ImplementContext(repo_root, auto_commit, mission_slug, feature_dir, wp_file, declared_deps)


def claim_preflight(ctx: ImplementContext, wp_id: str) -> ClaimPreflight:
    """Target branch, protected-branch refusal, status and lanes surfaces, dependency gate."""
    repo_root, mission_slug, auto_commit, declared_deps = ctx.repo_root, ctx.mission_slug, ctx.auto_commit, ctx.declared_deps
    planning_branch = workspace_context.resolve_mission_target_branch(mission_slug, repo_root)
    implement_claim._raise_if_status_commit_protected(repo_root, planning_branch, auto_commit, mission_slug)

    from specify_cli.coordination.surface_resolver import (
        resolve_status_surface_with_anchor as _resolve_status_surface,
    )

    # FR-003 layer 4: read WP-lane status through the SAME canonical,
    # config-determined surface authority the status WRITE path
    # (coordination/status_transition) uses, never a second ad-hoc
    # resolution. resolve_mission_read_path derived its own coord
    # preference from a slug-derived mid8 (empty for bare slugs), so in the
    # planning→implement window the read landed on a different surface than
    # the write and saw genesis ("WP not finalized"). The anchor authority
    # derives mid8 from meta and carries the fail-closed coord semantics
    # (StatusReadPathNotFound) — one authority, C-STAT-1.
    _status_feature_dir = _resolve_status_surface(repo_root, mission_slug).read_dir
    # ``lanes.json`` (LANE_STATE) is a PRIMARY-partition artifact with INV-5
    # read/write symmetry, so its dir resolves through the kind-aware
    # placement seam (PRIMARY surface) — a DIFFERENT surface than the coord
    # STATUS read above. Resolving it on the coord surface (the pre-symmetry
    # C-LANES-1 read) mismatched the PRIMARY write and broke coord-mission
    # implement (#3371). See :func:`specify_cli.workspace.context.resolve_lane_state_dir`.
    _lanes_feature_dir: Path = workspace_context.resolve_lane_state_dir(repo_root, mission_slug)

    # T012 / Contract 3 + dependency gate: reject unseeded WPs and
    # not-yet-ready dependencies BEFORE any workspace allocation.
    _claim_snapshot = reduce_status_events(read_events(_status_feature_dir))
    dependency_graph.ensure_wp_claim_preconditions(wp_id, declared_deps, _claim_snapshot.work_packages)
    return ClaimPreflight(planning_branch, _status_feature_dir, _lanes_feature_dir)


def commit_planning_artifacts(ctx: ImplementContext, wp_id: str, preflight: ClaimPreflight) -> None:
    """Commit the mission's planning artifacts on the seam-owned placement (or refuse)."""
    repo_root, mission_slug, auto_commit, feature_dir = ctx.repo_root, ctx.mission_slug, ctx.auto_commit, ctx.mission_dir
    planning_branch = preflight.planning_branch
    # WP06 / T019 / C-PLACE-1 / #5232: the seam owns the planning placement, so
    # implement-claim never reconciles a primary↔coord planning-artifact split
    # (#1816). A resolved placement is the SAME CommitTarget status events
    # resolve to; an unresolved WP context degrades, inside the seam and
    # only after the planning commit's structural check, to the mission's
    # declared coordination branch (R-1b, #5232 shape 2).
    _placement = coordination_planning_commit.resolve_claim_planning_placement(repo_root, mission_slug=mission_slug, wp_id=wp_id)

    implement_planning_commit._ensure_planning_artifacts_committed_git(
        repo_root=repo_root,
        feature_dir=feature_dir,
        mission_slug=mission_slug,
        wp_id=wp_id,
        planning_branch=implement_planning_commit._planning_commit_branch(repo_root, mission_slug, planning_branch),
        auto_commit=bool(auto_commit),
        placement=_placement,
    )


def run_bulk_edit_gate(ctx: ImplementContext, wp_id: str, acknowledge_not_bulk_edit: bool) -> None:
    """The bulk-edit gate phase."""
    feature_dir, wp_file, mission_slug = ctx.mission_dir, ctx.wp_file, ctx.mission_slug
    # Bulk edit occurrence classification gate (FR-006) + inference
    # warning for potentially unmarked bulk edits (FR-009).
    _run_bulk_edit_gate_and_inference(feature_dir, wp_file, mission_slug, wp_id, acknowledge_not_bulk_edit)


def build_operational_context(ctx: ImplementContext, wp_id: str, actor: str | None) -> Any:
    """Build and validate the runtime OperationalContext before any allocation."""
    repo_root, feature_dir, mission_slug = ctx.repo_root, ctx.mission_dir, ctx.mission_slug
    # FR-017 / NFR-004: build and validate the runtime OperationalContext
    # BEFORE any worktree allocation. The shared claim builder is read-only
    # (no worktree, no status event); calling its guards here means a
    # missing-context precondition failure aborts before create_lane_workspace
    # runs, so a failed claim leaves zero new worktree paths and zero new
    # status events.
    from runtime.next.runtime_bridge import build_operational_context_for_claim

    operational_context = build_operational_context_for_claim(
        repo_root=repo_root,
        feature_dir=feature_dir,
        mission_slug=mission_slug,
        wp_id=wp_id,
        actor=actor or "implement-command",
        active_model=actor,
        active_role=actor or "implement-command",
        current_activity="implement",
    )
    operational_context.require_active_role()
    return operational_context


def select_workspace(ctx: ImplementContext, wp_id: str, preflight: ClaimPreflight) -> WorkspaceSelection:
    """Resolve the execution workspace (write intent) and the WP's lane."""
    repo_root, mission_slug = ctx.repo_root, ctx.mission_slug
    # Seam-B (WP03, #3128 / FR-005): true WP-execution write site. Refuse a
    # claim invoked from a checkout the mission does not own (canonically
    # another mission's lane worktree in the same registry). write_intent
    # gates the checkout-identity refusal; the ~20 pure read vehicles leave
    # it False, so reads/planning are never falsely refused.
    resolved_workspace = resolve_workspace_for_wp(repo_root, mission_slug, wp_id, write_intent=True)

    lanes_manifest, lane = implement_support.resolve_execution_lane(resolved_workspace, preflight.lanes_feature_dir, wp_id)
    return WorkspaceSelection(resolved_workspace, lanes_manifest, lane)


def enter_checkout_claim_lock(stack: ExitStack, ctx: ImplementContext, selection: WorkspaceSelection) -> None:
    """Hold the write-checkout claim lock on *stack* for a single_branch repo-root claim (#5796).

    Entered before :func:`allocate` (whose occupancy scan it protects) and kept until
    *stack* closes, i.e. through the claim emit and the claim commit. Reuses the one
    predicate ``agent action implement`` uses; a lane worktree or a non-single_branch
    Mission takes nothing. Lock order: this lock outermost, then the Mission lock.
    """
    from specify_cli.cli.commands.agent import workflow_executor

    workflow_executor.enter_checkout_claim_lock(stack, ctx.repo_root, ctx.mission_slug, selection.resolved_workspace)


def hold_mission_write_lock(stack: ExitStack, ctx: ImplementContext) -> None:
    """Hold the Mission write lock on *stack* from the claim emit through the claim commit (#5468).

    The key is the one the claim emit itself re-enters (``start_implementation_status``
    locks ``mission_lock_key(feature_dir)``), so the emit nests inside this hold and the claim commit stages a consistent snapshot of
    the status files. Unbounded wait (``UNBOUNDED_LOCK_WAIT``): the initiating command queues rather
    than failing.
    """
    stack.enter_context(mission_write_lock(mission_write_lock_dir(ctx.repo_root, ctx.mission_slug), repo_root=ctx.repo_root, timeout=UNBOUNDED_LOCK_WAIT))


def allocate(ctx: ImplementContext, wp_id: str, selection: WorkspaceSelection, base: str | None) -> AllocationResult:
    """Refusals, VCS lock, effective base, then allocate or reuse the workspace."""
    repo_root, mission_slug, feature_dir, wp_file, declared_deps = ctx.repo_root, ctx.mission_slug, ctx.mission_dir, ctx.wp_file, ctx.declared_deps
    resolved_workspace, lanes_manifest = selection.resolved_workspace, selection.lanes_manifest
    # WP04/T015 (FR-004/NFR-003/SC-004): the pre-write claim triple rides
    # the planned -> claimed transition's policy_metadata sidecar (see
    # _start_wp_implementation_status below). The former frontmatter
    # dual-write mirror was removed in the #2816 unconditional cutover, so
    # `spec-kitty implement` writes 0 runtime bytes to the WP file.
    # #5100 A3: refusals (wrong branch / occupied / dirty) run BEFORE the VCS
    # lock is written into meta.json, so a refused implement leaves nothing
    # behind (the read-only check is repeated, idempotently, at allocation).
    occupancy_verified = implement_support.refuse_repo_root_checkout_if_unavailable(repo_root, mission_slug, wp_id, resolved_workspace)
    # #5738: a claim whose auto-commit cannot land on the checked-out branch is
    # refused here too, before the VCS lock, the lane worktree and the status write.
    implement_claim._raise_if_claim_commit_head_mismatch(repo_root, mission_slug, wp_id, ctx.auto_commit)
    vcs_backend = _ensure_vcs_in_meta(feature_dir, repo_root)

    # #3571: when --base is provided, validate the ref (planning-lane
    # "ignored" warning applied here, FR-007) and thread the EFFECTIVE
    # base as an explicit parameter into create_lane_workspace, which
    # forwards it to the topology-aware allocator (never smuggled
    # through lanes_manifest.mission_branch — the coord path never read
    # that field).
    effective_base = _resolve_effective_base(repo_root, base, resolved_workspace)

    result = create_lane_workspace(
        repo_root=repo_root,
        mission_slug=mission_slug,
        wp_id=wp_id,
        wp_file=wp_file,
        resolved_workspace=resolved_workspace,
        lanes_manifest=lanes_manifest,
        declared_deps=declared_deps,
        vcs_backend_value=vcs_backend.value,
        base=effective_base,
        occupancy_verified=occupancy_verified,
    )
    _report_hook_backup(result)
    return AllocationResult(result, effective_base)


def _report_hook_backup(result: LaneWorkspaceResult) -> None:
    """Tell the operator where a foreign pre-commit hook was backed up (#4895; printed here, #5715)."""
    if result.hook_backup_path is None:
        return
    console.print(
        f"[yellow]⚠ Existing .git/hooks/pre-commit was not spec-kitty-managed; backed up to {result.hook_backup_path} before installing the commit guard.[/yellow]"
    )


def record_claim(ctx: ImplementContext, wp_id: str, effective_actor: str, allocation: AllocationResult, status_execution_mode: str) -> Any:
    """Start the WP's implementation status (the claim)."""
    repo_root, mission_slug, feature_dir = ctx.repo_root, ctx.mission_slug, ctx.mission_dir
    workspace_path = allocation.result.workspace_path
    status_result = implement_claim._start_wp_implementation_status(
        feature_dir=feature_dir,
        mission_slug=mission_slug,
        wp_id=wp_id,
        effective_actor=effective_actor,
        workspace_path=workspace_path,
        status_execution_mode=status_execution_mode,
        repo_root=repo_root,
    )
    return status_result


def commit_claim(ctx: ImplementContext, wp_id: str, status_result: Any) -> None:
    """Auto-commit the claim; three refusals propagate, anything else is a warning."""
    repo_root, feature_dir, mission_slug, wp_file, auto_commit = ctx.repo_root, ctx.mission_dir, ctx.mission_slug, ctx.wp_file, ctx.auto_commit
    try:
        implement_claim._commit_wp_claim_status(
            repo_root=repo_root,
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id=wp_id,
            wp_file=wp_file,
            auto_commit=auto_commit,
            status_result=status_result,
        )
    except SafeCommitPathPolicyError:
        # #2155 (FR-002 / T011): a wrong-surface guard refusal must NOT be folded
        # into the soft "Could not update WP status" warning — let it propagate so
        # the defect surfaces (the inner handler already re-raised it on purpose).
        raise
    except SafeCommitHeadMismatch:
        # #610: mirrors the SafeCommitPathPolicyError clause above — a genuine
        # branch-name mismatch must NOT be folded into the soft "Could not
        # update WP status" warning either (the inner handler already
        # re-raised it on purpose).
        raise
    except PlacementResolutionRequired:
        # WP03 / D11: a fail-closed placement-resolution refusal must NOT be
        # folded into the soft "Could not update WP status" warning either —
        # that would silently resurrect the checkout-derived fallback this
        # error exists to forbid. Let it propagate so the operator sees and
        # acts on the structured, actionable message.
        raise
    except Exception as exc:
        console.print(f"[yellow]Warning:[/yellow] Could not update WP status: {exc}")
