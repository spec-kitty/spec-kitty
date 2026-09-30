"""Ops command - operation history and undo functionality.

This command provides access to VCS operation history via the git reflog.
Git provides read-only access to the reflog (no undo).
"""

from __future__ import annotations

from pathlib import Path

import typer
from specify_cli.cli.commands._git_remedies import GIT_UNDO_ALTERNATIVES
from specify_cli.cli.console import console
from rich.table import Table

from specify_cli.core.vcs import (
    OperationInfo,
    get_vcs,
)

app = typer.Typer(
    name="ops",
    help="Operation history (git reflog)",
    no_args_is_help=True,
)


def _display_operations(ops: list[OperationInfo]) -> None:
    """Display operation history in a formatted table.

    Args:
        ops: List of operations to display
    """
    if not ops:
        console.print("[dim]No operations found[/dim]")
        return

    table = Table(title="Operation History (git reflog)")

    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Time", style="dim")
    table.add_column("Description")

    for op in ops:
        # Truncate operation ID for display
        short_id = op.operation_id[:12] if len(op.operation_id) > 12 else op.operation_id

        # Format timestamp
        time_str = op.timestamp.strftime("%Y-%m-%d %H:%M")

        # Truncate description if too long
        desc = op.description[:60] + "..." if len(op.description) > 60 else op.description

        row = [short_id, time_str, desc]

        table.add_row(*row)

    console.print(table)


@app.command()
def log(
    limit: int = typer.Option(
        20,
        "--limit",
        "-n",
        help="Number of operations to show",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show full operation IDs and details",
    ),
) -> None:
    """Show operation history.

    Shows the git reflog (read-only history).

    Examples:
        # Show recent operations
        spec-kitty ops log

        # Show last 5 operations
        spec-kitty ops log --limit 5

        # Show with full details
        spec-kitty ops log --verbose
    """
    workspace_path = Path.cwd()

    # Get VCS implementation
    try:
        get_vcs(workspace_path)
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to detect VCS: {e}")
        raise typer.Exit(1)

    console.print("\n[cyan]Backend:[/cyan] git")
    console.print()

    # Get operation history (git reflog only)
    from specify_cli.core.vcs.git import git_get_reflog

    ops = git_get_reflog(workspace_path, limit=limit)

    _display_operations(ops)

    if verbose and ops:
        console.print("\n[dim]Full operation IDs:[/dim]")
        for op in ops[:5]:  # Show first 5 full IDs
            console.print(f"  {op.operation_id}")

    console.print()


@app.command()
def undo() -> None:
    """Undo is not supported for git.

    Git does not have reversible operation history.
    Consider using these alternatives manually:
      - git reset --soft HEAD~1  (undo last commit, keep changes)
      - git reset --hard HEAD~1  (undo last commit, discard changes)
      - git revert <commit>      (create reverting commit)
      - git reflog               (find previous states)
    """
    console.print("\n[red]Undo not supported for git[/red]")
    console.print()
    console.print("[dim]Git does not have reversible operation history.[/dim]")
    console.print("[dim]Consider using these alternatives manually:[/dim]")
    for _alt in GIT_UNDO_ALTERNATIVES:
        console.print(f"  {_alt}")
    console.print()
    raise typer.Exit(1)
