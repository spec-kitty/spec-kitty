"""Canonical status management commands for AI agents.

Provides CLI access to the status emit/materialize pipeline:
- ``spec-kitty agent status emit`` -- record a lane transition
- ``spec-kitty agent status materialize`` -- rebuild status.json from event log
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Annotated, Any

import typer
from mission_runtime import MissionArtifactKind, placement_seam
from specify_cli.cli.console import console
from rich.table import Table

from specify_cli.cli.selector_resolution import resolve_mission_handle
from specify_cli.core.paths import locate_project_root, get_main_repo_root
from specify_cli.missions._read_path_resolver import (
    MissionSelectorAmbiguous,
    resolve_bare_modern_mission_dir_name,
)
from specify_cli.status import feature_status_lock
from specify_cli.status import EVENTS_FILENAME, EventPersistenceError, StoreError
from specify_cli.status import parse_review_result_json

logger = logging.getLogger(__name__)

app = typer.Typer(
    name="status",
    help="Canonical status management commands",
    no_args_is_help=True,
)

PROJECT_ROOT_NOT_FOUND = "Could not locate project root"


def _find_mission_slug(
    explicit_mission: str | None = None,
    *,
    json_output: bool = False,
    repo_root: Path | None = None,
) -> str:
    """Require an explicit mission slug.

    When repo_root is supplied, the handle is resolved via the canonical
    mission resolver which handles ambiguous numeric-prefix handles, mid8
    prefixes, and full ULID forms.

    Args:
        explicit_mission: Mission slug provided explicitly.
        json_output: Propagate to resolver error rendering.
        repo_root: Repository root; if provided, enables canonical resolver.

    Returns:
        Mission slug (e.g., "034-feature-name")

    Raises:
        typer.Exit: If the mission slug is not provided.
    """
    if not explicit_mission or not explicit_mission.strip():
        err = "--mission <slug> is required"
        if json_output:
            print(json.dumps({"error": err}))
        else:
            console.print(f"[red]Error:[/red] {err}")
        raise typer.Exit(1)

    raw_handle = explicit_mission.strip()
    if repo_root is not None:
        try:
            legacy_dir = placement_seam(get_main_repo_root(repo_root), raw_handle).read_dir(
                MissionArtifactKind.PRIMARY_METADATA
            )
        except MissionSelectorAmbiguous as exc:
            # Same shape as tasks_shared._find_mission_slug (#241): this
            # read-path resolver family raises BEFORE resolve_mission_handle
            # runs, so the ambiguous case must map onto the SAME shared
            # {"success": False, "error_code": ..., "error": ..., "handle":
            # ..., "candidates": [...]} envelope resolve_mission_handle emits
            # below, not a bare {"error": str(exc)}.
            envelope = {
                "success": False,
                "error_code": exc.error_code,
                "error": str(exc),
                "handle": exc.handle,
                "candidates": exc.candidates,
            }
            if json_output:
                print(json.dumps(envelope))
                raise typer.Exit(1) from None
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(2) from None
        if legacy_dir.exists():
            # F-001: the candidate resolver canonicalizes mid8/ULID/numeric
            # handles, so the resolved directory's NAME — not the raw operator
            # handle — is the canonical mission slug downstream consumers need.
            return legacy_dir.name
        # C6 (WP05): the bare-modern-slug resolution is the ONE shared seam in
        # ``missions._read_path_resolver`` — the CLI consumes it rather than keeping
        # a byte-for-byte glob clone (NFR-004 single-definition).
        if resolved_bare := resolve_bare_modern_mission_dir_name(
            get_main_repo_root(repo_root), raw_handle
        ):
            return resolved_bare
        try:
            resolved = resolve_mission_handle(raw_handle, repo_root, json_mode=json_output)
            return resolved.mission_slug
        except (SystemExit, typer.Exit):
            if legacy_dir.exists():
                return legacy_dir.name
            raise

    return raw_handle


def _output_result(json_mode: bool, data: dict, success_message: str | None = None):
    """Output result in JSON or human-readable format."""
    if json_mode:
        print(json.dumps(data))
    elif success_message:
        console.print(success_message)


def _output_error(json_mode: bool, error_message: str, diagnostic: dict | None = None):
    """Output error in JSON or human-readable format."""
    if json_mode:
        print(json.dumps(diagnostic if diagnostic is not None else {"error": error_message}))
    else:
        console.print(f"[red]Error:[/red] {error_message}")


def _resolve_status_surface(
    explicit_mission: str | None = None,
    *,
    json_output: bool = False,
) -> tuple[Path, str, Path]:
    """Resolve the status read surface, mission slug, and repo root.

    This is the ``MissionStatus`` authority resolver (slug validation +
    fail-closed coord authority), **not** the dir-only feature-dir resolver
    in :mod:`specify_cli.missions._read_path_resolver`. It uses
    ``MissionStatus.load()`` to resolve the coord-aware read path so that
    coordination-topology missions read from the coord worktree rather than
    the (potentially stale) primary checkout.

    Returns:
        (feature_dir, mission_slug, repo_root)

    Raises:
        typer.Exit: If resolution fails
    """
    from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted
    from specify_cli.status import CoordAuthorityUnavailable, MissionMetadataUnavailable, MissionStatus

    cwd = Path.cwd().resolve()
    repo_root = locate_project_root(cwd)

    if repo_root is None:
        console.print(f"[red]Error:[/red] {PROJECT_ROOT_NOT_FOUND}")
        raise typer.Exit(1)

    mission_slug = _find_mission_slug(
        explicit_mission=explicit_mission,
        json_output=json_output,
        repo_root=repo_root,
    )
    main_repo_root = get_main_repo_root(repo_root)

    try:
        ms = MissionStatus.load(repo_root=main_repo_root, mission_slug=mission_slug)
        feature_dir = ms.read_dir
    # ``CoordinationBranchDeleted`` (WP05 / T025) surfaces the converged coord-
    # deleted hard-fail (#1848 data-loss) identically to the other fail-closed
    # boundary types; it is listed explicitly because the aggregate now propagates
    # it VERBATIM rather than re-wrapping to ``CoordAuthorityUnavailable``.
    except (CoordinationBranchDeleted, CoordAuthorityUnavailable, MissionMetadataUnavailable) as exc:
        _output_error(json_output, str(exc))
        raise typer.Exit(1)

    return feature_dir, mission_slug, main_repo_root


def _resolve_mission_status_for_repo(
    main_repo_root: Path,
    mission_slug: str,
    json_output: bool = False,
) -> Any:
    """Resolve the coord-aware ``MissionStatus`` aggregate for a mission.

    Centralises ``MissionStatus.load`` + fail-closed error handling so callers
    that need the aggregate itself (not just its ``read_dir``) do not have to
    ``load()`` twice. FR-004 routes status writes through the returned
    aggregate's ``transition()`` method.

    Returns:
        The resolved :class:`~specify_cli.status.MissionStatus` aggregate.

    Raises:
        typer.Exit: If the slug is invalid or the coord authority is
            unavailable / metadata cannot be trusted (fail closed).
    """
    from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted
    from specify_cli.status import (
        CoordAuthorityUnavailable,
        InvalidMissionSlug,
        MissionMetadataUnavailable,
        MissionStatus,
    )

    try:
        return MissionStatus.load(repo_root=main_repo_root, mission_slug=mission_slug)
    # ``CoordinationBranchDeleted`` (WP05 / T025): the aggregate now propagates the
    # converged coord-deleted hard-fail VERBATIM, so the CLI surfaces it as a clean
    # fail-closed error (#1848) rather than letting it escape uncaught.
    except (CoordinationBranchDeleted, CoordAuthorityUnavailable, MissionMetadataUnavailable, InvalidMissionSlug) as exc:
        _output_error(json_output, str(exc))
        raise typer.Exit(1)


def _resolve_status_surface_for_repo(
    main_repo_root: Path,
    mission_slug: str,
    json_output: bool = False,
) -> tuple[Path, str, Path]:
    """Resolve coord-aware status read_dir given an already-resolved main_repo_root.

    Factored out to avoid duplicating MissionStatus.load + CoordAuthorityUnavailable
    handling across multiple commands (reduces cyclomatic complexity).

    Returns:
        (feature_dir, mission_slug, main_repo_root)

    Raises:
        typer.Exit: If CoordAuthorityUnavailable is raised.
    """
    ms = _resolve_mission_status_for_repo(main_repo_root, mission_slug, json_output)
    return ms.read_dir, mission_slug, main_repo_root


def _enforce_emit_for_review_gate(
    json_output: bool,
    main_repo_root: Path,
    mission_slug: str,
    wp_id: str,
    to: str,
    force: bool,
) -> None:
    """Reject an in_progress->for_review emit with no lane commit (FR-011).

    Thin CLI adapter over the shared, surface-neutral gate leaf
    (:func:`specify_cli.lanes.for_review_gate.evaluate_for_review_gate`) --
    mirrors the orchestrator-api ``transition`` surface's
    ``_enforce_for_review_commit_gate`` so BOTH surfaces enforce identical
    semantics (a WP with zero commits on its lane branch cannot reach
    ``for_review``). No-ops when the alias-resolved target lane is not
    ``for_review``, when bypassed (``--force``), or when the gate does not
    apply (no ``lanes.json``, or the WP is not in any lane) -- the leaf
    decides those cases and returns a passing decision.

    Raises:
        typer.Exit: With code 1 when the gate rejects the transition.
    """
    from specify_cli.lanes.for_review_gate import (
        GateDecision,
        evaluate_for_review_gate,
    )
    from specify_cli.status import Lane, resolve_lane_alias

    if resolve_lane_alias(to) != Lane.FOR_REVIEW:
        return

    decision: GateDecision = evaluate_for_review_gate(
        main_repo_root, mission_slug, wp_id, force=force
    )
    if not decision.passed:
        _output_error(
            json_output,
            decision.reason,
            {
                "error": decision.reason,
                "wp_id": wp_id,
                "lane_id": decision.lane_id,
            },
        )
        raise typer.Exit(1)


@app.command()
def emit(
    wp_id: Annotated[str, typer.Argument(help="Work package ID (e.g., WP01)")],
    to: Annotated[
        str,
        typer.Option(
            "--to",
            help="Target lane (e.g., claimed, in_progress, for_review, approved, done)",
        ),
    ] = ...,
    actor: Annotated[str, typer.Option("--actor", help="Who is making this transition")] = ...,
    mission: Annotated[
        str | None,
        typer.Option("--mission", help="Mission slug (required in multi-mission repos)"),
    ] = None,

    force: Annotated[bool, typer.Option("--force", help="Force transition bypassing guards")] = False,
    reason: Annotated[str | None, typer.Option("--reason", help="Reason for forced transition")] = None,
    evidence_json: Annotated[str | None, typer.Option("--evidence-json", help="JSON string with done evidence")] = None,
    review_ref: Annotated[str | None, typer.Option("--review-ref", help="Review feedback reference")] = None,
    review_result_json: Annotated[
        str | None,
        typer.Option(
            "--review-result-json",
            help="JSON structured review outcome for transitions from in_review",
        ),
    ] = None,
    workspace_context: Annotated[
        str | None,
        typer.Option(
            "--workspace-context",
            help="Workspace context identifier for claimed->in_progress",
        ),
    ] = None,
    subtasks_complete: Annotated[
        bool | None,
        typer.Option(
            "--subtasks-complete",
            help="Whether required subtasks are complete for in_progress->for_review",
        ),
    ] = None,
    implementation_evidence_present: Annotated[
        bool | None,
        typer.Option(
            "--implementation-evidence-present",
            help="Whether implementation evidence exists for in_progress->for_review",
        ),
    ] = None,
    execution_mode: Annotated[str, typer.Option("--execution-mode", help="Execution mode (worktree or direct_repo)")] = "worktree",
    json_output: Annotated[bool, typer.Option("--json", help="Machine-readable JSON output")] = False,
) -> None:
    """Emit a status transition event for a work package.

    Records a lane transition in the canonical event log, validates the
    transition against the state machine, materializes a snapshot, and
    updates legacy compatibility views.

    Examples:
        spec-kitty agent status emit WP01 --to claimed --actor claude
        spec-kitty agent status emit WP01 --to approved --actor claude --review-result-json '{"reviewer": "alice", "verdict": "approved", "reference": "PR#1"}'
        spec-kitty agent status emit WP01 --to in_progress --actor claude --force --reason "resuming after crash"
    """
    try:
        # Resolve repo root
        cwd = Path.cwd().resolve()
        repo_root = locate_project_root(cwd)
        if repo_root is None:
            _output_error(json_output, PROJECT_ROOT_NOT_FOUND)
            raise typer.Exit(1)

        main_repo_root = get_main_repo_root(repo_root)

        # Resolve feature slug
        mission_slug = _find_mission_slug(explicit_mission=mission, json_output=json_output, repo_root=repo_root)

        # Resolve coord-aware mission aggregate via MissionStatus.load(). The
        # aggregate is retained (not just its read_dir) so the write below can
        # route through it without loading twice (FR-004).
        ms = _resolve_mission_status_for_repo(main_repo_root, mission_slug, json_output)
        feature_dir = ms.read_dir

        # Parse evidence JSON if provided
        evidence = None
        if evidence_json is not None:
            try:
                evidence = json.loads(evidence_json)
            except json.JSONDecodeError as exc:
                example = '{"review": {"reviewer": "alice", "verdict": "approved", "reference": "PR#1"}}'
                _output_error(
                    json_output,
                    f"Invalid JSON in --evidence-json: {exc}\n"
                    f"Expected valid JSON object, e.g.: '{example}'",
                )
                raise typer.Exit(1)

        # Parse/validate the structured review verdict through the SAME hoisted
        # parser the orchestrator-api transition surface uses (FR-010/FR-013),
        # so both surfaces accept/reject an identical shape.
        review_result = None
        if review_result_json is not None:
            try:
                review_result = parse_review_result_json(review_result_json)
            except ValueError as exc:
                _output_error(json_output, str(exc))
                raise typer.Exit(1)

        # FR-011: the shared, topology-aware for_review commit gate -- no-ops
        # unless the alias-resolved target lane is for_review, mirroring the
        # orchestrator-api transition surface's identical gate placement
        # (immediately before the transition is emitted).
        _enforce_emit_for_review_gate(json_output, main_repo_root, mission_slug, wp_id, to, force)

        # Lazy import to avoid circular imports
        from specify_cli.status import TransitionError
        from specify_cli.status import TransitionRequest

        # FR-004: the MissionStatus aggregate is the sole write entry point.
        # ms.transition() validates and delegates to the transactional path,
        # so this is behavior-preserving relative to the prior direct call.
        event = ms.transition(TransitionRequest(
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id=wp_id,
            to_lane=to,
            actor=actor,
            force=force,
            reason=reason,
            evidence=evidence,
            review_ref=review_ref,
            review_result=review_result,
            workspace_context=workspace_context,
            subtasks_complete=subtasks_complete,
            implementation_evidence_present=implementation_evidence_present,
            execution_mode=execution_mode,
            repo_root=main_repo_root,
        ))

        # ``transition()`` can materialize the coordination worktree and write
        # there even when the initial aggregate read from primary during the
        # create→first-write window. Reload so machine output points at the
        # event log affected by this command.
        output_feature_dir = feature_dir
        try:
            output_feature_dir = type(ms).load(
                repo_root=main_repo_root,
                mission_slug=mission_slug,
            ).read_dir
        except Exception as reload_exc:  # noqa: BLE001
            logger.debug(
                "Could not reload mission status after transition for %s: %s",
                mission_slug,
                reload_exc,
            )

        # Build result
        result = {
            "event_id": event.event_id,
            "wp_id": event.wp_id,
            "work_package_id": event.wp_id,
            "from_lane": str(event.from_lane),
            "to_lane": str(event.to_lane),
            "status_events_path": str(output_feature_dir / EVENTS_FILENAME),
            "actor": event.actor,
        }

        _output_result(
            json_output,
            result,
            f"[green]OK[/green] {event.wp_id}: "
            f"{event.from_lane} -> {event.to_lane} "
            f"(event: {event.event_id[:12]}...)",
        )

    except typer.Exit:
        raise
    except Exception as exc:
        # Check if it's a TransitionError (imported lazily above)
        try:
            from specify_cli.status import TransitionError
            if isinstance(exc, TransitionError):
                _output_error(json_output, str(exc))
                raise typer.Exit(1)
        except ImportError:
            pass
        diagnostic = exc.to_diagnostic() if isinstance(exc, EventPersistenceError) else None
        _output_error(json_output, str(exc), diagnostic=diagnostic)
        raise typer.Exit(1)


@app.command()
def materialize(
    mission: Annotated[str | None, typer.Option("--mission", help="Mission slug (required in multi-mission repos)")] = None,

    json_output: Annotated[bool, typer.Option("--json", help="Machine-readable JSON output")] = False,
) -> None:
    """Rebuild status.json from the canonical event log.

    Reads all events from status.events.jsonl, applies the deterministic
    reducer to produce a snapshot, writes status.json, and updates legacy
    compatibility views.

    Examples:
        spec-kitty agent status materialize
        spec-kitty agent status materialize --mission 034-my-feature
        spec-kitty agent status materialize --json
    """
    try:
        # Resolve repo root
        cwd = Path.cwd().resolve()
        repo_root = locate_project_root(cwd)
        if repo_root is None:
            _output_error(json_output, PROJECT_ROOT_NOT_FOUND)
            raise typer.Exit(1)

        main_repo_root = get_main_repo_root(repo_root)

        # Resolve feature slug
        mission_slug = _find_mission_slug(explicit_mission=mission, json_output=json_output, repo_root=repo_root)

        # Resolve coord-aware mission directory via MissionStatus aggregate
        feature_dir, _, _ = _resolve_status_surface_for_repo(main_repo_root, mission_slug, json_output)

        # Lazy import to avoid circular imports
        from specify_cli.status import materialize as do_materialize
        from specify_cli.status import EVENTS_FILENAME

        # Check that the events file exists
        events_path = feature_dir / EVENTS_FILENAME
        if not events_path.exists():
            _output_error(
                json_output,
                f"No event log found at {events_path}\n"
                "Run 'spec-kitty agent status emit' to create the first event, "
                "or run a migration to initialize the event log.",
            )
            raise typer.Exit(1)

        with feature_status_lock(main_repo_root, feature_dir.name):
            # Materialize snapshot from event log
            snapshot = do_materialize(feature_dir)

        # Build output
        if json_output:
            print(json.dumps(snapshot.to_dict()))
        else:
            # Human-readable summary
            wp_count = len(snapshot.work_packages)
            event_count = snapshot.event_count

            console.print(
                f"[green]Materialized[/green] {mission_slug}: "
                f"{event_count} events -> {wp_count} WPs"
            )

            # Lane distribution
            lane_parts = []
            for lane_name, count in sorted(snapshot.summary.items()):
                if count > 0:
                    lane_parts.append(f"{lane_name}: {count}")
            if lane_parts:
                console.print(f"  {', '.join(lane_parts)}")

    except typer.Exit:
        raise
    except Exception as exc:
        _output_error(json_output, str(exc))
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Doctor command (WP12)
# ---------------------------------------------------------------------------


@app.command()
def doctor(
    mission: Annotated[
        str | None,
        typer.Option("--mission", help="Mission slug"),
    ] = None,

    stale_claimed: Annotated[
        int,
        typer.Option(
            "--stale-claimed-days", help="Threshold for stale claims (days)"
        ),
    ] = 7,
    stale_in_progress: Annotated[
        int,
        typer.Option(
            "--stale-in-progress-days",
            help="Threshold for stale in-progress (days)",
        ),
    ] = 14,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Machine-readable JSON output"),
    ] = False,
) -> None:
    """Run health checks for status hygiene and global runtime.

    Detects global runtime issues (missing runtime directory, version mismatch,
    corrupted missions) and project-level issues (stale claims, orphan
    workspaces, drift).
    Exit code 0 = healthy, 1 = issues found.

    Examples:
        spec-kitty agent status doctor
        spec-kitty agent status doctor --mission 034-my-feature
        spec-kitty agent status doctor --stale-claimed-days 3 --json
    """
    from specify_cli.runtime.doctor import run_global_checks
    from specify_cli.status import run_doctor

    feature_dir, mission_slug, repo_root = _resolve_status_surface(mission, json_output=json_output)

    # Run global runtime checks BEFORE project-specific checks
    global_checks = run_global_checks(project_dir=repo_root)
    global_has_issues = any(not c.passed for c in global_checks)

    try:
        result = run_doctor(
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            repo_root=repo_root,
            stale_claimed_days=stale_claimed,
            stale_in_progress_days=stale_in_progress,
        )
    except FileNotFoundError as e:
        if json_output:
            console.print_json(
                json.dumps({"error": str(e), "healthy": False})
            )
        else:
            console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    overall_healthy = result.is_healthy and not global_has_issues

    if json_output:
        report = {
            "mission_slug": result.mission_slug,
            "healthy": overall_healthy,
            "global_runtime": [
                {
                    "name": c.name,
                    "passed": c.passed,
                    "message": c.message,
                    "severity": c.severity,
                }
                for c in global_checks
            ],
            "findings": [
                {
                    "severity": str(f.severity),
                    "category": str(f.category),
                    "wp_id": f.wp_id,
                    "message": f.message,
                    "recommended_action": f.recommended_action,
                }
                for f in result.findings
            ],
        }
        console.print_json(json.dumps(report))
    else:
        # Global Runtime section
        console.print("\n[bold]Global Runtime:[/bold]")
        for check in global_checks:
            if check.passed:
                icon = "✓"
                color = "green"
            elif check.severity == "warning":
                icon = "⚠"
                color = "yellow"
            else:
                icon = "✗"
                color = "red"
            console.print(f"  [{color}]{icon}[/{color}] {check.message}")

        # Project-specific section
        console.print(f"\n[bold]Mission Status: {result.mission_slug}[/bold]")
        if result.is_healthy:
            console.print("  [green]Healthy[/green]")
        else:
            console.print("  [yellow]Issues found[/yellow]")
            table = Table(title="Doctor Findings")
            table.add_column("Severity", style="bold")
            table.add_column("Category")
            table.add_column("WP")
            table.add_column("Message")
            table.add_column("Action")
            for f in result.findings:
                severity_style = (
                    "red" if f.severity == "error" else "yellow"
                )
                table.add_row(
                    f"[{severity_style}]{f.severity}[/{severity_style}]",
                    str(f.category),
                    f.wp_id or "-",
                    f.message,
                    f.recommended_action,
                )
            console.print(table)

    raise typer.Exit(0 if overall_healthy else 1)


# ---------------------------------------------------------------------------
# Lifecycle command (MVP stale/abandoned surface)
# ---------------------------------------------------------------------------


@app.command()
def lifecycle(
    mission: Annotated[
        str | None,
        typer.Option("--mission", help="Mission slug"),
    ] = None,

    json_output: Annotated[
        bool,
        typer.Option("--json", help="Machine-readable JSON output"),
    ] = False,
) -> None:
    """Show the canonical lifecycle state for one mission.

    This is the product-facing state layer above raw WP lanes. It answers
    whether a mission is active, recently completed, stale, abandoned, or
    now just recoverable/archive history.
    """
    from specify_cli.status import derive_mission_lifecycle

    feature_dir, mission_slug, _repo_root = _resolve_status_surface(mission, json_output=json_output)
    try:
        result = derive_mission_lifecycle(feature_dir)
    except StoreError as exc:
        _output_error(json_output, str(exc))
        raise typer.Exit(1)

    if json_output:
        print(json.dumps(result.to_dict()))
        raise typer.Exit(0)

    table = Table(show_header=False, box=None)
    table.add_column("Key", style="dim")
    table.add_column("Value")
    table.add_row("Mission", result.mission_slug)
    table.add_row("State", result.state)
    table.add_row("Default Surface", result.surface_state or "off")
    table.add_row("Reason", result.reason)
    table.add_row("Completion", f"{result.completion_pct:.1f}%")
    table.add_row("Work Packages", str(result.total_wps))
    table.add_row("Active WPs", str(result.active_wp_count))
    table.add_row("Review WPs", str(result.review_wp_count))
    table.add_row("Blocked WPs", str(result.blocked_wp_count))
    table.add_row("Terminal WPs", str(result.terminal_wp_count))
    table.add_row("Event Log", "present" if result.has_event_log else "missing")
    table.add_row("Age", f"{result.age_days}d" if result.age_days is not None else "unknown")
    table.add_row(
        "Last Activity",
        result.last_activity_at.isoformat() if result.last_activity_at is not None else "unknown",
    )
    console.print()
    console.print(f"[bold]Mission Lifecycle: {mission_slug}[/bold]")
    console.print(table)

    # WP02 / T009: render post-mission lifecycle history (re-opens + follow-ups).
    from specify_cli.status import format_post_mission_events

    history_lines = format_post_mission_events(result.post_mission_events)
    if history_lines:
        console.print()
        console.print("[bold]Post-mission History[/bold]")
        for line in history_lines:
            console.print(f"  • {line}")
    raise typer.Exit(0)


# ---------------------------------------------------------------------------
# Migration command (WP14)
# ---------------------------------------------------------------------------


def _migration_result_to_dict(result: Any) -> dict[str, Any]:
    """Convert a MigrationResult to a JSON-serializable dict."""
    return {
        "features": [
            {
                "mission_slug": f.mission_slug,
                "status": f.status,
                "wp_count": len(f.wp_details),
                "wp_details": [
                    {
                        "wp_id": wp.wp_id,
                        "original_lane": wp.original_lane,
                        "canonical_lane": wp.canonical_lane,
                        "alias_resolved": wp.alias_resolved,
                    }
                    for wp in f.wp_details
                ],
                "error": f.error,
            }
            for f in result.features
        ],
        "summary": {
            "total_migrated": result.total_migrated,
            "total_skipped": result.total_skipped,
            "total_failed": result.total_failed,
            "aliases_resolved": result.aliases_resolved,
        },
    }


def _status_style(status: str) -> str:
    return {
        "migrated": "[green]migrated[/green]",
        "skipped": "[yellow]skipped[/yellow]",
        "failed": "[red]failed[/red]",
    }.get(status, status)


def _print_rich_migrate_output(result: Any, *, dry_run: bool) -> None:
    title = "Migration Preview (dry-run)" if dry_run else "Migration Results"
    table = Table(title=title)
    table.add_column("Feature", style="cyan")
    table.add_column("Status")
    table.add_column("WPs", justify="right")
    table.add_column("Aliases Resolved", justify="right")
    table.add_column("Notes")

    for f in result.features:
        aliases = sum(1 for wp in f.wp_details if wp.alias_resolved)
        notes = f.error or ""
        table.add_row(
            f.mission_slug,
            _status_style(f.status),
            str(len(f.wp_details)),
            str(aliases),
            notes,
        )

    console.print()
    console.print(table)
    console.print()

    console.print(
        f"Migrated: [green]{result.total_migrated}[/green]  "
        f"Skipped: [yellow]{result.total_skipped}[/yellow]  "
        f"Failed: [red]{result.total_failed}[/red]  "
        f"Aliases resolved: {result.aliases_resolved}"
    )
    console.print()


@app.command()
def migrate(
    mission: Annotated[
        str | None,
        typer.Option("--mission", help="Single mission slug to migrate"),
    ] = None,

    _all_features: Annotated[
        bool,
        typer.Option("--all", help="Migrate all features in kitty-specs/"),
    ] = False,
    _dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview migration without writing events"),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output results as JSON"),
    ] = False,
    _actor: Annotated[
        str,
        typer.Option("--actor", help="Actor name for bootstrap events"),
    ] = "migration",
) -> None:
    """[REMOVED] Frontmatter-to-event-log bootstrap migration has been removed.

    The canonical status model uses the event log as sole authority.
    One-shot bootstrap migration from frontmatter is handled by the
    upgrade migration system (``spec-kitty upgrade``), not this command.

    Examples:
        spec-kitty upgrade  # applies all pending migrations
    """
    if mission is not None:
        _find_mission_slug(explicit_mission=mission, json_output=json_output)

    msg = (
        "The migrate command has been removed. "
        "Bootstrap migration from frontmatter is handled by the upgrade system. "
        "Run 'spec-kitty upgrade' to apply pending migrations."
    )
    if json_output:
        print(json.dumps({"error": msg}))
    else:
        console.print(f"[red]Removed:[/red] {msg}")
    raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Validate command (WP11)
# ---------------------------------------------------------------------------


def _collect_status_validation_findings(feature_dir: Path, result: Any) -> bool:
    """Populate validation findings from status.events.jsonl.

    Returns False when there are no events to validate.
    """
    from specify_cli.status import read_events, read_events_raw
    from specify_cli.status import validate_done_evidence, validate_event_schema, validate_materialization_drift, validate_transition_legality

    try:
        raw_events = read_events_raw(feature_dir)

        if not raw_events:
            return False

        status_events = [event.to_dict() for event in read_events(feature_dir)]

        for event in status_events:
            result.errors.extend(validate_event_schema(event))

        result.errors.extend(validate_transition_legality(status_events))
        result.errors.extend(validate_done_evidence(status_events))

        # Drift detection: event log is sole authority, drift is always an error
        drift_findings = validate_materialization_drift(feature_dir)
        result.errors.extend(drift_findings)
    except StoreError as exc:
        result.errors.append(f"status.events.jsonl is corrupt: {exc}")

    return True


@app.command()
def validate(
    mission: Annotated[
        str | None,
        typer.Option("--mission", help="Mission slug (required in multi-mission repos)"),
    ] = None,

    json_output: Annotated[
        bool,
        typer.Option("--json", help="Machine-readable JSON output"),
    ] = False,
) -> None:
    """Validate canonical status model integrity.

    Runs all validation checks: event schema, transition legality,
    done-evidence completeness, materialization drift, and derived-view drift.

    Exit code 0 for pass (no errors), exit code 1 for fail (any errors).
    Warnings do not cause failure.

    Examples:
        spec-kitty agent status validate
        spec-kitty agent status validate --mission 034-my-feature
        spec-kitty agent status validate --json
    """
    from specify_cli.status import ValidationResult

    cwd = Path.cwd().resolve()
    repo_root = locate_project_root(cwd)
    if repo_root is None:
        if json_output:
            print(json.dumps({"error": PROJECT_ROOT_NOT_FOUND}))
        else:
            console.print(f"[red]Error:[/red] {PROJECT_ROOT_NOT_FOUND}")
        raise typer.Exit(1)

    mission_slug = _find_mission_slug(explicit_mission=mission, json_output=json_output, repo_root=repo_root)

    main_repo_root = get_main_repo_root(repo_root)
    feature_dir, _, _ = _resolve_status_surface_for_repo(main_repo_root, mission_slug, json_output)

    if not feature_dir.exists():
        msg = f"Mission directory not found: {feature_dir}"
        _output_error(json_output, msg)
        raise typer.Exit(1)

    result = ValidationResult()

    has_events = _collect_status_validation_findings(feature_dir, result)
    if not has_events:
        if json_output:
            print(
                json.dumps(
                    {
                        "mission_slug": mission_slug,
                        "passed": True,
                        "errors": [],
                        "warnings": [],
                        "error_count": 0,
                        "warning_count": 0,
                    }
                )
            )
        else:
            console.print(
                f"[green]Status Validation: {mission_slug}[/green]"
            )
            console.print("No events to validate.")
            console.print("[green]Result: PASS[/green]")
        raise typer.Exit(0)

    if json_output:
        print(
            json.dumps(
                {
                    "mission_slug": mission_slug,
                    "passed": result.passed,
                    "errors": result.errors,
                    "warnings": result.warnings,
                    "error_count": len(result.errors),
                    "warning_count": len(result.warnings),
                }
            )
        )
    else:
        console.print(
            f"\n[bold]Status Validation: {mission_slug}[/bold]"
        )
        console.print("-" * 50)

        if result.errors:
            console.print(f"[red]Errors: {len(result.errors)}[/red]")
            for error in result.errors:
                console.print(f"  - {error}")

        if result.warnings:
            console.print(f"[yellow]Warnings: {len(result.warnings)}[/yellow]")
            for warning in result.warnings:
                console.print(f"  - {warning}")

        if result.passed:
            if result.warnings:
                console.print(
                    f"\n[green]Result: PASS[/green] ({len(result.warnings)} warning(s))"
                )
            else:
                console.print("\n[green]Result: PASS[/green]")
        else:
            console.print("\n[red]Result: FAIL[/red]")

    raise typer.Exit(0 if result.passed else 1)


# ---------------------------------------------------------------------------
# Reconcile command (WP13)
# ---------------------------------------------------------------------------


@app.command()
def reconcile(
    mission: Annotated[
        str | None,
        typer.Option("--mission", help="Mission slug (required in multi-mission repos)"),
    ] = None,

    _dry_run: Annotated[
        bool,
        typer.Option("--dry-run/--apply", help="Preview vs persist reconciliation events"),
    ] = True,
    _target_repo: Annotated[
        list[Path] | None,
        typer.Option("--target-repo", "-t", help="Target repo path(s) to scan"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Machine-readable JSON output"),
    ] = False,
) -> None:
    """[REMOVED] Cross-repo reconciliation has been removed.

    The canonical status model uses the event log as sole authority.
    Cross-repo drift detection via frontmatter scanning is no longer
    supported. Use ``spec-kitty agent status validate`` to check
    event log integrity.

    Examples:
        spec-kitty agent status validate --mission 034-feature-name
    """
    if mission is not None:
        _find_mission_slug(explicit_mission=mission, json_output=json_output)

    msg = (
        "The reconcile command has been removed. "
        "The event log is now the sole authority for WP state. "
        "Use 'spec-kitty agent status validate' to check event log integrity."
    )
    if json_output:
        print(json.dumps({"error": msg}))
    else:
        console.print(f"[red]Removed:[/red] {msg}")
    raise typer.Exit(1)
