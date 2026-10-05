"""Implement command - allocate the lane worktree for a work package."""

from __future__ import annotations

import functools
import json
from collections.abc import Callable
from io import StringIO
from pathlib import Path
from typing import Annotated, Any

import typer
from pydantic import ValidationError
from specify_cli.cli.console import console

from specify_cli.cli import StepTracker
from specify_cli.core.context_validation import require_main_repo
from specify_cli.mission_metadata import resolve_mission_identity
from specify_cli.frontmatter import FrontmatterError
from mission_runtime import (
    MissionArtifactKind,
    placement_seam,
)
from specify_cli.lanes.worktree_allocator import (
    DependencyLaneMergeConflictError,
    OrphanedPlanningCommitError,
    PlanningCommitMergeConflictError,
)
from specify_cli.task_utils import TaskCliError, find_repo_root

from specify_cli.cli.commands import implement_phases, implement_recover

# WP02 / T008 / S1192: the workspace-ready banner's rich-markup open/close
# tags, repeated ~8x in ``_print_workspace_ready_banner`` -- hoisted to
# constants rather than restated at each call site. The bulk-edit inference
# banners (now in ``implement_phases``) use a different close tag.
_BANNER_OPEN = "[bold yellow]"
_BANNER_CLOSE = "[/bold yellow]"


def _json_wrapper_resolve_wp_id(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
    """Resolve the ``wp_id`` used for JSON error payloads: the ``wp_id``
    kwarg first, else the first positional argument (the Typer commands
    wrapped by ``_json_safe_output`` all take ``wp_id`` as arg 0)."""
    wp_id = kwargs.get("wp_id")
    if wp_id is None and args:
        wp_id = args[0]
    return wp_id


def _json_wrapper_begin_capture(json_output: bool) -> tuple[bool, StringIO | None]:
    """Snapshot ``console.quiet`` and, in ``--json`` mode, redirect console
    output into an in-memory buffer so wrapped-function chatter never leaks
    onto stdout ahead of the machine-readable payload."""
    previous_quiet = console.quiet
    capture_buffer: StringIO | None = None
    if json_output:
        capture_buffer = StringIO()
        console.file = capture_buffer
        console.quiet = False
    return previous_quiet, capture_buffer


def _json_wrapper_summarize_capture(capture_buffer: StringIO | None) -> str:
    """Return the last 20 non-blank, rstripped lines captured from the
    console -- the JSON error-summary shape pinned by T010."""
    lines = [line.rstrip() for line in (capture_buffer.getvalue() if capture_buffer else "").splitlines() if line.strip()]
    return "\n".join(lines[-20:]).strip() if lines else "implement command failed"


def _json_wrapper_emit_error_payload(error: str, wp_id: Any) -> None:
    payload: dict[str, Any] = {"status": "error", "error": error}
    if wp_id:
        payload["wp_id"] = str(wp_id)
    print(json.dumps(payload))


def _json_wrapper_handle_typer_exit(exc: typer.Exit, json_output: bool, capture_buffer: StringIO | None, wp_id: Any) -> None:
    """Emit the JSON error payload for a ``typer.Exit`` failure -- unless
    ``exit_code`` is falsy (0), which is a success exit and never gets a
    payload. The caller re-raises ``exc`` verbatim afterwards; this helper
    never raises."""
    exit_code: object = getattr(exc, "exit_code", 1)
    if json_output and exit_code:
        summary = _json_wrapper_summarize_capture(capture_buffer)
        _json_wrapper_emit_error_payload(summary or "implement command failed", wp_id)


def _json_wrapper_end_capture(previous_quiet: bool) -> None:
    console.quiet = previous_quiet
    # Reset _file to None so the console uses sys.stdout dynamically.
    # Restoring previous_file can leave the console pointing at a closed
    # pytest capsys buffer when tests run in sequence.
    console._file = None


def _json_safe_output(func: Callable[..., Any]) -> Callable[..., Any]:
    """Ensure --json mode stays machine-readable on both success and failure."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        json_output = bool(kwargs.get("json_output", False))
        wp_id = _json_wrapper_resolve_wp_id(args, kwargs)
        previous_quiet, capture_buffer = _json_wrapper_begin_capture(json_output)

        try:
            return func(*args, **kwargs)
        except typer.Exit as exc:
            _json_wrapper_handle_typer_exit(exc, json_output, capture_buffer, wp_id)
            raise
        except Exception as exc:  # pragma: no cover - defensive
            if json_output:
                _json_wrapper_emit_error_payload(str(exc), wp_id)
            raise typer.Exit(1) from exc
        finally:
            _json_wrapper_end_capture(previous_quiet)

    return wrapper


def _complete_validate_step(tracker: StepTracker, lane: Any) -> None:
    """Complete the ``validate`` tracker step with the selected lane."""
    if lane is None:
        tracker.complete("validate", "Execution: repository root planning workspace")
    else:
        tracker.complete("validate", f"Lane: {lane.lane_id}")


def _print_explicit_base_ref(effective_base: str | None, resolved_workspace: Any) -> None:
    """Print the explicit ``--base`` line after a successful allocation."""
    # #3571 (FR-005): the success line prints ONLY here — AFTER
    # create_lane_workspace has actually returned successfully — so it
    # can never fabricate success. Guarded so it fires only when a base
    # was supplied AND actually applies (not on a repository-root
    # planning lane, where --base is a no-op warned about above); it is
    # therefore unreachable on base=None, on the planning-lane branch,
    # on the orchestrator-api path (a different call site entirely), and
    # on any fail-loud raise (control never reaches this line).
    from specify_cli.lanes.compute import is_planning_lane

    if effective_base is not None and not is_planning_lane(resolved_workspace):
        console.print(f"[cyan]→ Using explicit base ref: {effective_base}[/cyan]")


def _render_create_failure(tracker: StepTracker, exc: Exception, workspace_created: bool) -> None:
    """Render a ``create`` step failure (the caller raises ``typer.Exit(1)``)."""
    tracker.error("create", f"workspace allocation failed: {exc}")
    console.print(tracker.render())
    if workspace_created:
        # #4888/T025: the workspace was already created (`create_lane_workspace`
        # returned) and the failure happened inside `_start_wp_implementation_status`
        # -- possibly AFTER its status commit already landed (e.g. a
        # `SafeCommitRecoveryFailed` whose `commit_sha` is set). Printing
        # the generic "Workspace allocation failed" line here would
        # contradict a WP that is already `claimed`/`in_progress` and
        # committed, so name the actual failure point instead.
        commit_sha = getattr(exc, "commit_sha", None)
        landed_note = (
            f" A status commit (sha={commit_sha}) may have already landed on the lane branch."
            if commit_sha
            else " The WP status transition may have already landed on the lane branch."
        )
        console.print(
            f"\n[red]Error:[/red] Workspace was created but starting the WP status failed: {exc}.{landed_note} "
            "Run `spec-kitty agent tasks status` to check the WP's actual lane before retrying."
        )
    else:
        console.print(f"\n[red]Error:[/red] Workspace allocation failed: {exc}")
    # F-50 (#3937): a tooling/allocation failure that happens BEFORE the
    # workspace exists emits NO lifecycle transition. ``create_lane_workspace``
    # runs BEFORE the claim, so the WP is still ``planned`` in that case,
    # and the allocator self-cleans (abort + ``reset --hard``, no
    # ``lanes.json`` write). The former ``_emit_blocked_on_alloc_failure``
    # manufactured ``planned -> blocked``, an unrecoverable state
    # (``blocked -> planned`` is illegal). Leaving the WP ``planned`` is
    # recoverable and reentrant — at parity with the orchestrator-api
    # path, which never emits ``blocked``. When the failure happens AFTER
    # workspace creation (``workspace_created`` above), the WP may
    # instead already be ``claimed``/``in_progress`` with a landed commit
    # — the message above says so instead of implying ``planned``.
    # Surface the exception's actionable ``next_step`` for the
    # conflict/orphan types that carry one, so the operator gets the
    # concrete resolution rather than a generic "re-run".
    if isinstance(
        exc,
        (DependencyLaneMergeConflictError, PlanningCommitMergeConflictError, OrphanedPlanningCommitError),
    ):
        console.print(f"[yellow]Next step:[/yellow] {exc.next_step}")


def _build_implement_json_payload(
    repo_root: Path,
    mission_slug: str,
    wp_id: str,
    workspace_path: Path,
    branch_name: str | None,
    result: Any,
    resolved_workspace: Any,
) -> dict[str, Any]:
    """Assemble the ``--json`` success payload (FR-004/FR-005 #2186 identity
    anchor + FR-006 lane-test-env passthrough)."""
    result_execution_mode = result.execution_mode if isinstance(result.execution_mode, str) else resolved_workspace.execution_mode
    workspace_rel = str(workspace_path.relative_to(repo_root))
    # FR-004/FR-005 (#2186): the JSON ``mission_slug``/``mission_number``/
    # ``mission_type`` come from meta.json, which lives ONLY on the PRIMARY
    # checkout. ``feature_dir`` above may have landed on the coord husk (the
    # topology-aware resolve→candidate cascade); give the identity read its OWN
    # PRIMARY anchor rather than relying on the conditional meta-fallback above
    # (C-EXCL-FALLBACK — so that fallback can be retired later). NFR-004: no
    # primary-dir stub — this resolves the durable PRIMARY home for real.
    # read-side-seam-primary-primitive-closure-01KYKMMT WP05/FR-004: routed
    # through the kind-aware seam (PRIMARY_METADATA is a PRIMARY-partition
    # kind, so it never lands on the coord husk the topology-aware
    # resolve→candidate cascade above can).
    identity_dir = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.PRIMARY_METADATA)
    identity = resolve_mission_identity(identity_dir)
    return {
        "workspace": workspace_rel,
        "workspace_path": workspace_rel,
        "branch": branch_name,
        "mission_slug": identity.mission_slug,
        "mission_number": identity.mission_number,
        "mission_type": identity.mission_type,
        "wp_id": wp_id,
        "lane_id": result.lane_id,
        "execution_mode": result_execution_mode,
        "status": "created",
        # FR-006: surface the lane-suffixed test DB env so
        # downstream agents / test runners can `os.environ.update`
        # without re-deriving the helper. Empty dict for
        # planning-artifact workspaces (lane_id is None) or
        # when the result type doesn't carry a real dict
        # (e.g. a MagicMock in unit tests).
        "lane_test_env": (result.lane_test_env if isinstance(getattr(result, "lane_test_env", None), dict) else {}),
    }


def _report_workspace_created(tracker: StepTracker, result: Any, workspace_path: Path, repo_root: Path) -> None:
    """Complete the ``create`` tracker step and print the workspace/branch
    summary lines shared by the repo-root and lane-worktree cases."""
    if result.lane_id is None:
        tracker.complete("create", f"Repository root: {workspace_path.relative_to(repo_root)}")
    elif result.is_reuse:
        tracker.complete("create", f"Reused lane {result.lane_id}: {workspace_path.relative_to(repo_root)}")
    else:
        tracker.complete("create", f"Lane {result.lane_id}: {workspace_path.relative_to(repo_root)}")
    console.print(tracker.render())
    if result.mission_branch:
        console.print(f"[cyan]→ Mission branch: {result.mission_branch}[/cyan]")
    if result.branch_name:
        console.print(f"[cyan]→ Lane branch: {result.branch_name}[/cyan]")
    else:
        console.print("[cyan]→ Workspace contract: repository root planning workspace[/cyan]")


def _print_workspace_ready_banner(result: Any, workspace_path: Path) -> None:
    """Human-readable "workspace ready" banner (repo-root planning vs lane
    worktree), plus the FR-006 lane-test-env export block."""
    if result.lane_id is None:
        console.print("\n[bold green]✓ Repository-root workspace ready[/bold green]")
        console.print()
        console.print(_BANNER_OPEN + "=" * 72 + _BANNER_CLOSE)
        console.print(_BANNER_OPEN + "Planning-artifact work for this WP happens in the repository root" + _BANNER_CLOSE)
        console.print(_BANNER_OPEN + "=" * 72 + _BANNER_CLOSE)
        console.print()
        console.print(f"  [bold]cd {workspace_path}[/bold]")
        console.print()
        console.print("[dim]This WP does not get a lane worktree or workspace context file.[/dim]")
        console.print("[dim]Make planning-artifact changes directly in the repository root.[/dim]")
        return

    if getattr(result, "resolution_kind", None) == "repo_root" and result.branch_name:
        # single_branch code WP: executes in the write checkout, no lane worktree.
        console.print("\n[bold green]✓ Repository-root workspace ready[/bold green]")
        console.print()
        console.print(f"  Work in the repository root checkout on branch [bold]{result.branch_name}[/bold]")
        console.print(f"  [bold]cd {workspace_path}[/bold]")
        console.print()
        console.print("[dim]This WP runs directly in the repository root; commit your work on this branch yourself.[/dim]")
        return

    console.print("\n[bold green]✓ Lane worktree ready[/bold green]")
    console.print()
    console.print(_BANNER_OPEN + "=" * 72 + _BANNER_CLOSE)
    console.print(_BANNER_OPEN + "CRITICAL: Change to the lane worktree before editing files" + _BANNER_CLOSE)
    console.print(_BANNER_OPEN + "=" * 72 + _BANNER_CLOSE)
    console.print()
    console.print(f"  [bold]cd {workspace_path}[/bold]")
    console.print()
    console.print("[dim]All file edits, writes, and commits MUST happen in this directory.[/dim]")
    console.print("[dim]Writing to the main repository instead of the lane worktree is a critical error.[/dim]")

    # FR-006: surface the lane-suffixed test DB env so the agent can
    # export it before running the project's test suite. Persisted to
    # WorkspaceContext for resurrection by later commands; printed here
    # so a human operator can copy/paste in their shell.
    lane_env = getattr(result, "lane_test_env", None)
    if isinstance(lane_env, dict) and lane_env:
        console.print()
        console.print("[bold cyan]Lane-specific test environment (FR-006):[/bold cyan]")
        for key, value in sorted(lane_env.items()):
            console.print(f"  export {key}={value}")
        console.print("[dim]Two parallel SaaS / Django lanes will collide on a single shared test DB unless these are exported in the lane's test process.[/dim]")


@_json_safe_output
@require_main_repo
def implement(
    wp_id: str = typer.Argument(..., help="Work package ID (for example, WP01)"),
    mission: Annotated[str | None, typer.Option("--mission", help="Mission slug (for example, 001-my-feature)")] = None,
    auto_commit: Annotated[
        bool | None,
        typer.Option("--auto-commit/--no-auto-commit", help="Auto-commit status and planning changes (default: from project config)"),
    ] = None,
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format"),
    recover: bool = typer.Option(False, "--recover", help="Recover from crashed implementation session"),
    base: Annotated[
        str | None,
        typer.Option(
            "--base",
            help=(
                "Explicit base ref for the lane workspace (default: auto-detect). "
                "Use this when upstream dependency branches have been merged-and-deleted "
                "and you want to start from the current target branch tip, e.g. --base main."
            ),
        ),
    ] = None,
    acknowledge_not_bulk_edit: Annotated[
        bool,
        typer.Option(
            "--acknowledge-not-bulk-edit",
            help="Suppress the bulk-edit inference warning when spec language resembles a bulk edit but the mission is not one.",
        ),
    ] = False,
    actor: Annotated[str | None, typer.Option("--actor", hidden=True, help="Actor identity for programmatic callers")] = None,
) -> None:
    """Internal — allocate or reuse the lane worktree for a work package.

    This command is internal infrastructure, used by ``spec-kitty agent action implement``
    for workspace creation. It is not the canonical user-facing implementation path for
    spec-kitty 3.1.1.

    Canonical user workflow::

      spec-kitty next --agent <name> --mission <slug>   (loop entry)
      spec-kitty agent action implement <WP> --agent <name>  (per-WP verb)

    This command remains available as a compatibility surface for direct callers.
    See FR-503 and D-4 in the 3.1.1 spec.
    """
    # SC-003 no-selector guard: exit 2 when --mission is omitted (mirrors
    # all other commands and aligns with the no-selector-error-contract).
    # Guard runs BEFORE --recover so that `implement --recover` with no
    # --mission also exits 2, not 1 via detect_feature_context.
    if mission is None:
        console.print("[red]Error:[/red] --mission <slug> is required")
        raise typer.Exit(2)

    if recover:
        implement_recover._run_recover_mode(wp_id, mission, json_output)
        return

    tracker = StepTracker(f"Implement {wp_id}")
    tracker.add("detect", "Detect feature context")
    tracker.add("validate", "Validate planning state")
    tracker.add("create", "Resolve execution workspace")
    console.print()

    tracker.start("detect")
    try:
        repo_root = find_repo_root()
        ctx = implement_phases.detect_context(mission, wp_id, repo_root, auto_commit, json_mode=json_output)
        tracker.complete("detect", f"Feature: {ctx.mission_slug}")
    except (TaskCliError, FileNotFoundError, FrontmatterError, ValidationError, typer.Exit) as exc:
        tracker.error("detect", str(exc))
        console.print(tracker.render())
        raise typer.Exit(1) from exc

    tracker.start("validate")
    try:
        preflight = implement_phases.claim_preflight(ctx, wp_id)
        implement_phases.commit_planning_artifacts(ctx, wp_id, preflight)
        implement_phases.run_bulk_edit_gate(ctx, wp_id, acknowledge_not_bulk_edit)
        implement_phases.build_operational_context(ctx, wp_id, actor)
        selection = implement_phases.select_workspace(ctx, wp_id, preflight)
        _complete_validate_step(tracker, selection.lane)
    except Exception as exc:
        # Catches (among others) CorruptLanesError, MissingLanesError,
        # WorkPackageStartRejected, ValueError, typer.Exit -- every failure
        # in this block maps to the same "report + exit 1" outcome, so one
        # generic handler (Exception is a strict superset) replaces the
        # former specific-tuple + generic-fallback pair without changing
        # behavior for any of them.
        tracker.error("validate", str(exc))
        console.print(tracker.render())
        raise typer.Exit(1) from exc

    tracker.start("create")
    effective_actor = actor or "implement-command"
    status_result = None
    status_execution_mode = selection.resolved_workspace.status_execution_mode
    # #4888/T025: distinguishes a failure that occurred BEFORE the workspace
    # existed (create_lane_workspace itself failed -- the WP is still
    # `planned`, matching the comment below) from a failure that occurred
    # AFTER it (inside _start_wp_implementation_status, e.g. a
    # SafeCommitRecoveryFailed surfacing after the status commit already
    # landed) -- so the printed message never contradicts a WP that is
    # already `in_progress`/committed.
    workspace_created = False
    try:
        allocation = implement_phases.allocate(ctx, wp_id, selection, base)
        result = allocation.result
        workspace_path = result.workspace_path
        branch_name = result.branch_name
        workspace_created = True

        status_result = implement_phases.record_claim(ctx, wp_id, effective_actor, allocation, status_execution_mode)

        _report_workspace_created(tracker, result, workspace_path, ctx.repo_root)

        _print_explicit_base_ref(allocation.effective_base, selection.resolved_workspace)
    except typer.Exit:
        console.print(tracker.render())
        raise
    except Exception as exc:
        _render_create_failure(tracker, exc, workspace_created)
        raise typer.Exit(1) from exc

    implement_phases.commit_claim(ctx, wp_id, status_result)

    if json_output:
        print(json.dumps(_build_implement_json_payload(ctx.repo_root, ctx.mission_slug, wp_id, workspace_path, branch_name, result, selection.resolved_workspace)))
        return

    _print_workspace_ready_banner(result, workspace_path)


__all__ = ["implement"]
