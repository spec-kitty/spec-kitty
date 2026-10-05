"""``spec-kitty implement --recover``: crash recovery for a mission's implementation sessions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from specify_cli.cli.console import console

from specify_cli.task_utils import TaskCliError, find_repo_root
from specify_cli.cli.commands.implement_phases import detect_feature_context

if TYPE_CHECKING:
    # WP03 / T013: type-only -- ``_run_recover_mode`` and its extracted
    # helpers keep the real import lazy (inside the function body) to match
    # the module's existing deferred-import discipline; this gives mypy the
    # shapes without adding a runtime import edge to ``specify_cli.lanes``.
    from specify_cli.lanes.recovery import RecoveryReport, RecoveryState


def _recover_resolve_context(mission: str | None, json_output: bool) -> tuple[Path, str]:
    """Resolve ``(repo_root, mission_slug)`` for recovery.

    On failure, emits the JSON error payload (when requested) and exits 1 --
    matching the pre-extraction behavior byte-for-byte (T011 branch 1)."""
    try:
        repo_root = find_repo_root()
        _mission_number, mission_slug = detect_feature_context(mission, repo_root=repo_root)
    except (TaskCliError, typer.Exit) as exc:
        if json_output:
            print(json.dumps({"status": "error", "error": str(exc)}))
        raise typer.Exit(1) from None
    return repo_root, mission_slug


def _recover_emit_no_action_result(json_output: bool) -> None:
    """Report that the scan found nothing to recover (T011 branch 2)."""
    if json_output:
        print(
            json.dumps(
                {
                    "status": "ok",
                    "message": "No crashed implementation sessions found.",
                    "recovered_wps": [],
                    "worktrees_recreated": 0,
                    "transitions_emitted": 0,
                    "errors": [],
                }
            )
        )
    else:
        console.print("[green]No crashed implementation sessions found.[/green]")


def _recover_print_scan_table(needs_recovery: list[RecoveryState]) -> None:
    """Console-only rendering of the pre-recovery scan results table."""
    from rich.table import Table

    table = Table(title="Recovery Scan Results")
    table.add_column("WP", style="cyan")
    table.add_column("Lane", style="blue")
    table.add_column("Branch", style="dim")
    table.add_column("Worktree", style="green")
    table.add_column("Context", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("Action", style="bold")

    for s in needs_recovery:
        table.add_row(
            s.wp_id,
            s.lane_id,
            s.branch_name,
            "yes" if s.worktree_exists else "[red]NO[/red]",
            "yes" if s.context_exists else "[red]NO[/red]",
            s.status_lane,
            s.recovery_action,
        )
    console.print(table)
    console.print()


def _recover_emit_report(report: RecoveryReport, json_output: bool) -> None:
    """Emit the final recovery report -- json payload (no
    ``contexts_recreated``) vs the console summary (which includes it),
    plus the console-only errors block (T011 branches 3+4)."""
    if json_output:
        print(
            json.dumps(
                {
                    "status": "ok",
                    "recovered_wps": report.recovered_wps,
                    "worktrees_recreated": report.worktrees_recreated,
                    "transitions_emitted": report.transitions_emitted,
                    "errors": report.errors,
                }
            )
        )
        return
    console.print("[bold green]Recovery complete[/bold green]")
    console.print(f"  WPs recovered: {', '.join(report.recovered_wps) or 'none'}")
    console.print(f"  Worktrees recreated: {report.worktrees_recreated}")
    console.print(f"  Contexts recreated: {report.contexts_recreated}")
    console.print(f"  Status transitions emitted: {report.transitions_emitted}")
    if report.errors:
        console.print("  [red]Errors:[/red]")
        for err in report.errors:
            console.print(f"    - {err}")


def _run_recover_mode(
    _wp_id: str,
    mission: str | None,
    json_output: bool,
) -> None:
    """Run crash recovery for the given mission.

    Orchestrates scan + worktree/context/status reconciliation + reporting.
    The _wp_id argument is accepted but ignored for recovery -- all WPs in
    the mission are scanned.
    """
    from specify_cli.lanes.recovery import run_recovery, scan_recovery_state

    repo_root, mission_slug = _recover_resolve_context(mission, json_output)

    # First, show what we found
    states = scan_recovery_state(repo_root, mission_slug)
    needs_recovery = [s for s in states if s.recovery_action != "no_action"]

    if not needs_recovery:
        _recover_emit_no_action_result(json_output)
        return

    if not json_output:
        _recover_print_scan_table(needs_recovery)

    # Run recovery
    report = run_recovery(repo_root, mission_slug)
    _recover_emit_report(report, json_output)
