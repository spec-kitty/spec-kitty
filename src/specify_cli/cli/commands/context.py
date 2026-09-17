"""Context command - query workspace context information and manage MissionContext tokens.

Provides visibility into current workspace context for LLM agents and users,
plus canonical MissionContext token lifecycle (resolve, show).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import typer
from specify_cli.cli.console import console
from specify_cli.cli.json_contract import json_error
from rich.table import Table
from typing_extensions import Annotated

from specify_cli.task_utils import find_repo_root, TaskCliError
from specify_cli.core.paths import locate_project_root
from specify_cli.workspace.context import (
    cleanup_orphaned_contexts,
    find_orphaned_contexts,
    list_contexts,
    load_context,
)

app = typer.Typer(help="Query workspace context information")


def _emit_error(code: str, message: str, json_output: bool) -> None:
    """Render a boundary failure without defining another envelope authority."""
    if json_output:
        console.emit_json(json_error(code, message))
    else:
        console.print(f"[red]Error:[/red] {message}")


@contextmanager
def _workspace_read_boundary(json_output: bool) -> Iterator[None]:
    """Keep workspace filesystem failures at the command output boundary."""
    try:
        yield
    except OSError as exc:
        _emit_error("workspace_read_failed", f"Could not read workspace context: {exc}", json_output)
        raise typer.Exit(1) from exc


def detect_current_workspace(cwd: Path, _repo_root: Path) -> str | None:
    """Detect if current directory is inside a worktree.

    Args:
        cwd: Current working directory
        repo_root: Repository root path

    Returns:
        Workspace name if inside worktree, None otherwise
    """
    # Check if .worktrees is in path
    if ".worktrees" not in cwd.parts:
        return None

    # Extract workspace name from path
    for i, part in enumerate(cwd.parts):
        if part == ".worktrees" and i + 1 < len(cwd.parts):
            return cwd.parts[i + 1]

    return None


@app.command(name="info")
def info_command(
    workspace: Annotated[str | None, typer.Option("--workspace", "-w", help="Workspace name (auto-detected if inside worktree)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output in JSON format")] = False,
) -> None:
    """Show context information for current or specified workspace.

    Examples:
        # Auto-detect from current directory (if inside worktree)
        spec-kitty context info

        # Explicit workspace
        spec-kitty context info --workspace 010-mission-lane-a

        # JSON output
        spec-kitty context info --json
    """
    try:
        repo_root = find_repo_root()
    except TaskCliError as e:
        _emit_error("not_in_project", str(e), json_output)
        raise typer.Exit(1) from e

    # Auto-detect workspace if not provided
    if workspace is None:
        workspace = detect_current_workspace(Path.cwd(), repo_root)
        if workspace is None:
            _emit_error("no_worktree", "Not inside a worktree and no --workspace specified", json_output)
            if not json_output:
                console.print("\nRun from inside a worktree or use --workspace flag:")
                console.print("  spec-kitty context info --workspace 010-mission-lane-a")
            raise typer.Exit(1)

    # Load context
    with _workspace_read_boundary(json_output):
        context = load_context(repo_root, workspace)
    if context is None:
        _emit_error("workspace_not_found", f"No context found for workspace: {workspace}", json_output)
        if not json_output:
            console.print("\nContext file not found:")
            console.print(f"  {repo_root / '.kittify' / 'workspaces' / f'{workspace}.json'}")
        raise typer.Exit(1)

    # Output
    if json_output:
        console.emit_json(context.to_dict())
    else:
        console.print("\n[bold cyan]📍 Workspace Context[/bold cyan]")
        console.print("─" * 50)

        # Build info table
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Field", style="dim")
        table.add_column("Value")

        table.add_row("Work Package", f"[bold]{context.wp_id}[/bold]")
        table.add_row("Mission", context.mission_slug)
        table.add_row("Base Branch", f"[cyan]{context.base_branch}[/cyan]")
        base_commit = context.base_commit[:12] if context.base_commit else "unknown"
        table.add_row("Base Commit", f"[dim]{base_commit}[/dim]")
        table.add_row("Dependencies", ", ".join(context.dependencies) if context.dependencies else "[dim]none[/dim]")
        table.add_row("Created", context.created_at)
        table.add_row("Worktree", context.worktree_path)
        table.add_row("Branch", context.branch_name)
        table.add_row("VCS Backend", context.vcs_backend)

        console.print(table)
        console.print()


@app.command(name="list")
def list_command(
    json_output: Annotated[bool, typer.Option("--json", help="Output in JSON format")] = False,
    show_orphaned: bool = typer.Option(False, "--orphaned", help="Show only orphaned contexts"),
) -> None:
    """List all workspace contexts.

    Examples:
        # List all contexts
        spec-kitty context list

        # List only orphaned contexts (worktree deleted)
        spec-kitty context list --orphaned

        # JSON output
        spec-kitty context list --json
    """
    try:
        repo_root = find_repo_root()
    except TaskCliError as e:
        _emit_error("not_in_project", str(e), json_output)
        raise typer.Exit(1) from e

    if show_orphaned:
        with _workspace_read_boundary(json_output):
            orphaned = find_orphaned_contexts(repo_root)
        if json_output:
            console.emit_json([{"workspace": name, "context": ctx.to_dict()} for name, ctx in orphaned])
        else:
            if not orphaned:
                console.print("[green]✓[/green] No orphaned contexts found")
                return

            console.print(f"\n[yellow]⚠️  Found {len(orphaned)} orphaned context(s)[/yellow]\n")
            for name, ctx in orphaned:
                console.print(f"  [bold]{name}[/bold]")
                console.print(f"    Worktree: [dim]{ctx.worktree_path} (deleted)[/dim]")
                console.print(f"    Created: {ctx.created_at}")
                console.print()

            console.print("[dim]Clean up with: spec-kitty context cleanup[/dim]\n")
    else:
        with _workspace_read_boundary(json_output):
            contexts = list_contexts(repo_root)
        if json_output:
            console.emit_json([ctx.to_dict() for ctx in contexts])
        else:
            if not contexts:
                console.print("[dim]No workspace contexts found[/dim]")
                return

            console.print(f"\n[bold]Workspace Contexts[/bold] ({len(contexts)} total)\n")

            table = Table(show_header=True)
            table.add_column("WP", style="bold")
            table.add_column("Mission", style="dim")
            table.add_column("Base", style="cyan")
            table.add_column("Dependencies")
            table.add_column("Status")

            for ctx in sorted(contexts, key=lambda c: (c.mission_slug, c.wp_id)):
                # Check if worktree exists
                worktree_path = repo_root / ctx.worktree_path
                status = "[green]Active[/green]" if worktree_path.exists() else "[yellow]Orphaned[/yellow]"

                deps = ", ".join(ctx.dependencies) if ctx.dependencies else "[dim]none[/dim]"

                table.add_row(
                    ctx.wp_id,
                    ctx.mission_slug,
                    ctx.base_branch,
                    deps,
                    status,
                )

            console.print(table)
            console.print()


@app.command(name="cleanup")
def cleanup_command(
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be cleaned up without deleting"),
) -> None:
    """Clean up orphaned workspace contexts.

    Removes context files for workspaces that no longer exist.

    Examples:
        # Preview cleanup
        spec-kitty context cleanup --dry-run

        # Clean up orphaned contexts
        spec-kitty context cleanup
    """
    try:
        repo_root = find_repo_root()
    except TaskCliError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e

    orphaned = find_orphaned_contexts(repo_root)

    if not orphaned:
        console.print("[green]✓[/green] No orphaned contexts to clean up")
        return

    console.print(f"\n[yellow]Found {len(orphaned)} orphaned context(s):[/yellow]\n")
    for name, ctx in orphaned:
        console.print(f"  [bold]{name}[/bold]")
        console.print(f"    {ctx.worktree_path}")

    console.print()

    if dry_run:
        console.print("[dim]Dry run - no files deleted[/dim]")
        console.print(f"[dim]Would delete {len(orphaned)} context file(s)[/dim]")
    else:
        cleaned = cleanup_orphaned_contexts(repo_root)
        console.print(f"[green]✓[/green] Cleaned up {cleaned} orphaned context(s)")


@app.command(name="mission-resolve")
def mission_resolve_command(
    wp: Annotated[str, typer.Option("--wp", help="Work package code (e.g., WP01)")],
    mission: Annotated[str | None, typer.Option("--mission", help="Mission slug (e.g., 057-mission-name)")] = None,
    agent: Annotated[str | None, typer.Option("--agent", help="Agent name (default: 'unknown')")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output full JSON context (default: token only)")] = False,
) -> None:
    """Resolve and persist a MissionContext token.

    Creates a new bound context for the given work package and mission,
    writes it to .kittify/runtime/contexts/, and prints the token.

    The token can be passed to other commands via --context <token>.

    Examples:
        # Resolve and print token for piping
        TOKEN=$(spec-kitty context mission-resolve --wp WP01 --mission 057-my-mission)

        # Resolve and print full JSON
        spec-kitty context mission-resolve --wp WP01 --mission 057-my-mission --json
    """
    from specify_cli.context import resolve_context, ContextResolutionError

    repo_root = locate_project_root()
    if repo_root is None:
        _emit_error("not_in_project", "Could not locate project root (no .kittify/ directory found)", json_output)
        raise typer.Exit(1)

    mission_norm = mission.strip() if isinstance(mission, str) else None
    if not mission_norm:
        if json_output:
            _emit_error("missing_mission", "--mission <slug> is required", True)
            raise typer.Exit(2)
        raise typer.BadParameter("--mission <slug> is required")
    canonical = mission_norm

    try:
        ctx = resolve_context(
            wp_code=wp,
            mission_slug=canonical,
            agent=agent or "unknown",
            repo_root=repo_root,
        )
    except ContextResolutionError as e:
        _emit_error("context_resolution_failed", str(e), json_output)
        raise typer.Exit(1) from e

    if json_output:
        console.emit_json(ctx.to_dict())
    else:
        # Plain token output for easy piping / shell capture
        print(ctx.token)


@app.command(name="mission-show")
def mission_show_command(
    context_token: Annotated[str, typer.Option("--context", help="Context token (e.g., ctx-01HV...)")],
    json_output: Annotated[bool, typer.Option("--json", help="Output raw JSON")] = False,
) -> None:
    """Show all fields of a persisted MissionContext token.

    Loads the context file and pretty-prints its bound fields.

    Examples:
        spec-kitty context mission-show --context ctx-01HVXYZ...
        spec-kitty context mission-show --context ctx-01HVXYZ... --json
    """
    from specify_cli.context import load_context as load_mission_context
    from specify_cli.context import ContextNotFoundError, ContextCorruptedError

    repo_root = locate_project_root()
    if repo_root is None:
        _emit_error("not_in_project", "Could not locate project root (no .kittify/ directory found)", json_output)
        raise typer.Exit(1)

    try:
        ctx = load_mission_context(context_token, repo_root)
    except ContextNotFoundError as e:
        _emit_error("context_not_found", str(e), json_output)
        raise typer.Exit(1) from e
    except ContextCorruptedError as e:
        _emit_error("context_corrupted", str(e), json_output)
        raise typer.Exit(1) from e
    except (UnicodeDecodeError, OSError) as e:
        _emit_error("context_corrupted", f"Cannot read context token '{context_token}': {e}", json_output)
        raise typer.Exit(1) from e

    if json_output:
        console.emit_json(ctx.to_dict())
    else:
        console.print("\n[bold cyan]MissionContext[/bold cyan]")
        console.print("─" * 60)

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Field", style="dim")
        table.add_column("Value")

        table.add_row("Token", f"[bold]{ctx.token}[/bold]")
        table.add_row("WP Code", f"[bold]{ctx.wp_code}[/bold]")
        table.add_row("Mission Slug", ctx.mission_slug)
        table.add_row("Mission ID", ctx.mission_id)
        table.add_row("Work Package ID", ctx.work_package_id)
        table.add_row("Project UUID", ctx.project_uuid)
        table.add_row("Target Branch", f"[cyan]{ctx.target_branch}[/cyan]")
        table.add_row("Authoritative Repo", ctx.authoritative_repo)
        table.add_row("Authoritative Ref", ctx.authoritative_ref or "[dim]none[/dim]")
        table.add_row("Execution Mode", ctx.execution_mode)
        table.add_row("Dependency Mode", ctx.dependency_mode)
        table.add_row("Created At", ctx.created_at)
        table.add_row("Created By", ctx.created_by)
        if ctx.owned_files:
            table.add_row("Owned Files", "\n".join(ctx.owned_files))
        else:
            table.add_row("Owned Files", "[dim]none[/dim]")

        console.print(table)
        console.print()


# Default command when no subcommand specified
@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Query workspace context information."""
    if ctx.invoked_subcommand is None:
        # No subcommand - default to "info"
        info_command()


__all__ = ["app"]
