"""Context validation for location-aware commands.

This module provides runtime validation to ensure commands are executed
in the correct location (main repository vs worktree). Prevents common
mistakes like running 'implement' from inside a worktree.

Example:
    from specify_cli.core.context_validation import (
        require_main_repo,
        get_current_context,
    )

    @require_main_repo
    def implement(wp_id: str):
        # This function can only run from main repo
        pass
"""

from __future__ import annotations

import functools
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TypeVar
from collections.abc import Callable

import typer
from rich.console import Console

console = Console()


class ExecutionContext(StrEnum):
    """Execution context for a command."""

    MAIN_REPO = "main"  # Command runs in main repository
    WORKTREE = "worktree"  # Command runs inside a worktree
    EITHER = "either"  # Command can run in either location


@dataclass
class CurrentContext:
    """Current execution context information."""

    location: ExecutionContext
    cwd: Path
    repo_root: Path | None
    worktree_name: str | None  # e.g., "010-feature-lane-a" if in worktree
    worktree_path: Path | None  # Absolute path to worktree directory


def detect_execution_context(cwd: Path | None = None) -> CurrentContext:
    """Detect current execution context.

    Args:
        cwd: Current working directory (defaults to Path.cwd())

    Returns:
        CurrentContext with location, paths, and worktree info

    Example:
        >>> ctx = detect_execution_context()
        >>> if ctx.location == ExecutionContext.WORKTREE:
        ...     print(f"In worktree: {ctx.worktree_name}")
    """
    cwd = Path.cwd().resolve() if cwd is None else cwd.resolve()

    # Check if .worktrees is in path
    if ".worktrees" in cwd.parts:
        # Extract worktree information
        for i, part in enumerate(cwd.parts):
            if part == ".worktrees" and i + 1 < len(cwd.parts):
                candidate_root = Path(*cwd.parts[:i])
                if (candidate_root / ".kittify").exists() or (candidate_root / ".git").exists():
                    worktree_name = cwd.parts[i + 1]
                    worktree_path = Path(*cwd.parts[: i + 2])
                    repo_root = candidate_root

                    return CurrentContext(
                        location=ExecutionContext.WORKTREE,
                        cwd=cwd,
                        repo_root=repo_root,
                        worktree_name=worktree_name,
                        worktree_path=worktree_path,
                    )

    # Not in worktree - assume main repo
    # Try to find repo root (directory containing .kittify or .git)
    repo_root = None
    search_path = cwd
    for _ in range(10):  # Limit depth
        if (search_path / ".kittify").exists() or (search_path / ".git").exists():
            repo_root = search_path
            break
        if search_path.parent == search_path:
            break  # Reached filesystem root
        search_path = search_path.parent

    return CurrentContext(
        location=ExecutionContext.MAIN_REPO,
        cwd=cwd,
        repo_root=repo_root,
        worktree_name=None,
        worktree_path=None,
    )


def get_current_context() -> CurrentContext:
    """Get current execution context.

    Convenience function that detects context from current working directory.

    Returns:
        CurrentContext with location and path information
    """
    return detect_execution_context()


def format_location_error(
    required: ExecutionContext,
    actual: ExecutionContext,
    command_name: str,
    current_ctx: CurrentContext,
) -> str:
    """Format a clear error message for location mismatch.

    Args:
        required: Required execution context
        actual: Actual execution context
        command_name: Name of command being run
        current_ctx: Current context information

    Returns:
        Formatted error message with actionable instructions
    """
    if required == ExecutionContext.MAIN_REPO and actual == ExecutionContext.WORKTREE:
        # Command needs main repo, but in worktree
        if current_ctx.repo_root:
            return (
                f"[bold red]Error:[/bold red] '{command_name}' must run from the main repository\n\n"
                f"[yellow]Current location:[/yellow] Inside worktree [cyan]{current_ctx.worktree_name}[/cyan]\n"
                f"[yellow]Required location:[/yellow] Main repository\n\n"
                f"[bold]Change to main repository:[/bold]\n"
                f"  cd {current_ctx.repo_root}\n\n"
                f"[dim]This command creates/manages worktrees and must run from the main repository.\n"
                f"Running from inside a worktree would create nested worktrees, corrupting git state.[/dim]"
            )
        else:
            return (
                f"[bold red]Error:[/bold red] '{command_name}' must run from the main repository\n\n"
                f"[yellow]Current location:[/yellow] Inside worktree [cyan]{current_ctx.worktree_name}[/cyan]\n"
                f"[yellow]Required location:[/yellow] Main repository\n\n"
                f"[bold]Change to main repository:[/bold]\n"
                f"  cd ../..  # Navigate up from worktree\n\n"
                f"[dim]This command must run from the main repository.[/dim]"
            )

    elif required == ExecutionContext.WORKTREE and actual == ExecutionContext.MAIN_REPO:
        # Command needs worktree, but in main repo
        return (
            f"[bold red]Error:[/bold red] '{command_name}' must run from inside a worktree\n\n"
            f"[yellow]Current location:[/yellow] Main repository\n"
            f"[yellow]Required location:[/yellow] Inside a worktree\n\n"
            f"[bold]Change to a worktree:[/bold]\n"
            f"  cd .worktrees/###-feature-lane-a/\n\n"
            f"[dim]This command operates on workspace files and must run from inside a worktree.[/dim]"
        )

    else:
        # Generic error
        return (
            f"[bold red]Error:[/bold red] '{command_name}' cannot run in current location\n\n"
            f"[yellow]Current location:[/yellow] {actual.value}\n"
            f"[yellow]Required location:[/yellow] {required.value}\n"
        )


# Type variable for function decoration
F = TypeVar("F", bound=Callable)


def require_main_repo(func: F) -> F:
    """Decorator to require command runs from main repository.

    Prevents commands from running inside worktrees, which could cause
    nested worktrees or other git corruption.

    Example:
        @require_main_repo
        def implement(wp_id: str):
            # Can only run from main repo
            create_worktree(...)

    Args:
        func: Function to decorate

    Returns:
        Decorated function that validates location before executing
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        ctx = get_current_context()

        if ctx.location == ExecutionContext.WORKTREE:
            error_msg = format_location_error(
                required=ExecutionContext.MAIN_REPO,
                actual=ctx.location,
                command_name=func.__name__,
                current_ctx=ctx,
            )
            console.print(error_msg)
            raise typer.Exit(1)

        return func(*args, **kwargs)

    return wrapper  # type: ignore


__all__ = [
    "ExecutionContext",
    "CurrentContext",
    "detect_execution_context",
    "get_current_context",
    "require_main_repo",
]
