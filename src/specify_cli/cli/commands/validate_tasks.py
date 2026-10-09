"""Task metadata validation command for Spec Kitty CLI."""

from __future__ import annotations

from specify_cli.core.constants import KITTY_SPECS_DIR
import os
from pathlib import Path

import typer
from rich.panel import Panel
from rich.table import Table

from specify_cli.cli.console import console
from specify_cli.cli.helpers import get_project_root_or_exit
from specify_cli.task_metadata_validation import (
    repair_lane_mismatch,
    scan_all_tasks_for_mismatches,
)
from specify_cli.task_utils import TaskCliError, find_repo_root


def _normalize_mission_option(value: object) -> str | None:
    """Return a stripped mission selector, treating Typer sentinels as unset."""
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def validate_tasks(
    mission: str | None = typer.Option(
        None, "--mission", help="Mission slug to validate"
    ),
    fix: bool = typer.Option(False, "--fix", help="Automatically repair metadata inconsistencies"),
    check_all: bool = typer.Option(False, "--all", help="Check all features, not just one"),
    agent: str | None = typer.Option(None, "--agent", help="Agent name for activity log"),
    shell_pid: str | None = typer.Option(None, "--shell-pid", help="Shell PID for activity log"),
) -> None:
    """LEGACY: Validate and repair directory/frontmatter lane mismatches.

    This command is for legacy projects that used directory-based lanes
    (tasks/planned/, tasks/doing/, etc.). Modern projects (3.0+) use
    flat tasks/ directories with canonical status in status.events.jsonl.

    For modern projects, use `spec-kitty agent mission finalize-tasks`
    to ensure canonical status state exists.
    """
    try:
        repo_root = find_repo_root()
    except TaskCliError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)

    project_root = get_project_root_or_exit(repo_root)

    # Get agent and shell_pid from environment if not provided
    if not agent:
        agent = os.environ.get("SPEC_KITTY_AGENT", "system")
    if not shell_pid:
        shell_pid = str(os.getpid())

    if check_all:
        # Validate all features
        mission_specs = repo_root / KITTY_SPECS_DIR
        worktrees = repo_root / ".worktrees"

        feature_dirs = []
        if mission_specs.exists():
            feature_dirs.extend([d for d in mission_specs.iterdir() if d.is_dir()])
        if worktrees.exists():
            for wt_dir in worktrees.iterdir():
                if wt_dir.is_dir():
                    wt_specs = wt_dir / KITTY_SPECS_DIR
                    if wt_specs.exists():
                        feature_dirs.extend([d for d in wt_specs.iterdir() if d.is_dir()])

        if not feature_dirs:
            console.print("[yellow]No mission directories found.[/yellow]")
            raise typer.Exit(0)

        console.print(f"[cyan]Checking task metadata for {len(feature_dirs)} missions...[/cyan]")
        console.print()

        total_mismatches = 0
        total_fixed = 0

        for feature_dir in sorted(feature_dirs, key=lambda d: d.name):
            mismatches, fixed = _validate_feature_tasks(
                feature_dir, fix=fix, agent=agent, shell_pid=shell_pid
            )
            total_mismatches += mismatches
            total_fixed += fixed

        console.print()
        console.print(
            Panel(
                f"[bold]Summary:[/bold]\n"
                f"Total mismatches found: [yellow]{total_mismatches}[/yellow]\n"
                f"Total mismatches fixed: [green]{total_fixed}[/green]",
                title="Task Metadata Validation Complete",
                border_style="cyan" if total_mismatches == 0 else "yellow",
            )
        )

        raise typer.Exit(0 if total_mismatches == 0 or fix else 1)

    # Validate single feature
    mission_slug = _normalize_mission_option(mission)
    if mission_slug is None:
        console.print("[red]Error:[/red] --mission <slug> is required (or use --all)")
        raise typer.Exit(1)
    # FR-009 / single-leg PRIMARY (T028).
    # scan_all_tasks_for_mismatches reads WP-frontmatter from tasks/planned|doing|…/WP*.md
    # (WORK_PACKAGE_TASK partition).  Before this fix, the coord-aware resolver returned the
    # STATUS-only husk which carries no tasks/ → silent {} (pre-fix bug).
    from mission_runtime import (  # late import — keeps cold-start cost low
        MissionArtifactKind,
        placement_seam,
    )

    planning_dir = placement_seam(repo_root, mission_slug).read_dir(
        MissionArtifactKind.WORK_PACKAGE_TASK
    )
    if not planning_dir.exists():
        console.print(f"[red]Error:[/red] Mission directory not found: {planning_dir}")
        raise typer.Exit(1)

    console.print(f"[cyan]Validating task metadata for mission:[/cyan] {mission_slug}")
    console.print()

    mismatches, fixed = _validate_feature_tasks(
        planning_dir, fix=fix, agent=agent, shell_pid=shell_pid
    )

    if mismatches == 0:
        console.print("[green]✓ All task metadata is consistent![/green]")
        raise typer.Exit(0)
    elif fix and fixed > 0:
        console.print()
        console.print(f"[green]✓ Fixed {fixed} metadata mismatch(es).[/green]")
        raise typer.Exit(0)
    else:
        console.print()
        console.print(f"[yellow]Found {mismatches} metadata mismatch(es).[/yellow]")
        console.print("[dim]Run with --fix to automatically repair these mismatches.[/dim]")
        raise typer.Exit(1)


def _validate_feature_tasks(
    feature_dir: Path,
    *,
    fix: bool,
    agent: str,
    shell_pid: str,
) -> tuple[int, int]:
    """Validate task metadata for a single feature directory.

    Reads WP-frontmatter from the PRIMARY planning surface (tasks/planned|doing|…/WP*.md).
    This is a single-leg PRIMARY read: the frontmatter ``lane:`` field is compared against
    the lane-subdir the file lives in; no STATUS leg (status.events.jsonl) is read.

    Args:
        feature_dir: PRIMARY-partition planning dir (tasks/ frontmatter reads).
        fix: When True, automatically repair lane mismatches in-place.
        agent: Agent name written to the activity log on repair.
        shell_pid: Shell PID written to the activity log on repair.

    Returns:
        Tuple of (mismatches_found, mismatches_fixed)
    """
    console.print(f"[cyan]Checking:[/cyan] {feature_dir.name}")

    mismatches_dict = scan_all_tasks_for_mismatches(feature_dir)

    if not mismatches_dict:
        console.print("  [green]✓[/green] No metadata mismatches")
        return 0, 0

    # Display mismatches in a table
    table = Table(title=f"Task Metadata Mismatches: {feature_dir.name}", show_header=True)
    table.add_column("File", style="cyan")
    table.add_column("Expected Lane", style="green")
    table.add_column("Actual Lane", style="yellow")
    table.add_column("Status", style="white")

    fixed_count = 0
    for file_path, (_, expected, actual) in mismatches_dict.items():
        full_path = feature_dir / file_path

        status = "[yellow]Needs Fix[/yellow]"
        if fix:
            was_repaired, error = repair_lane_mismatch(
                full_path, agent=agent, shell_pid=shell_pid, add_history=True, dry_run=False
            )
            if was_repaired:
                status = "[green]Fixed[/green]"
                fixed_count += 1
            elif error:
                status = f"[red]Error: {error}[/red]"

        table.add_row(file_path, expected or "?", actual or "?", status)

    console.print(table)

    if fix:
        console.print()
        console.print(f"  [green]Fixed {fixed_count} of {len(mismatches_dict)} mismatches[/green]")

    return len(mismatches_dict), fixed_count


__all__ = ["validate_tasks"]
