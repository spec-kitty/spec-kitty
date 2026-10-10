"""Workspace-husk health cluster for ``doctor`` (WP09, #2059).

Extracts Cluster C — the ``.worktrees/`` husk scan + ``--fix`` remediation — out
of ``doctor.py`` into a cohesive standalone module (not a ``_misc`` catch-all,
per data-model.md). The ``workspaces`` @app.command shell stays in ``doctor.py``
and delegates to :func:`run_workspaces`; ``repo_root`` is resolved in the shell
(the patchable ``locate_project_root`` seam) and injected here.

Import discipline (one-way, I-2): imports shared infra from
:mod:`._doctor_shared`; never imports the CLI ``doctor`` module. The heavy
``specify_cli.status`` husk imports stay function-local per the existing pattern.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import typer

from ._doctor_shared import console

if TYPE_CHECKING:
    from specify_cli.status import RegisteredWorktreePaths

# ``__all__`` lists this sibling's single cross-module entrypoint. The render
# helpers are intra-module (used here + by this module's own unit tests) and are
# deliberately NOT exported — listing them would register orphan public symbols
# under the dead-symbol gate (tests/architectural/test_no_dead_symbols).
__all__ = [
    "run_workspaces",
]


def _workspace_husk_status_label(registered: bool | None) -> str:
    if registered is None:
        return "unknown registration state (fix refused until git succeeds)"
    if registered:
        return "registered (manual repair needed)"
    return "unregistered (safe to --fix)"


def _emit_workspace_husk_fix(repo_root: Path, json_output: bool) -> None:
    from specify_cli.status import WorkspaceHuskRegistrationError, fix_workspace_husks

    try:
        report, fix_result = fix_workspace_husks(repo_root)
    except WorkspaceHuskRegistrationError as exc:
        payload = {
            "healthy": False,
            "fix_refused": True,
            "error": str(exc),
        }
        if json_output:
            console.print_json(json.dumps(payload, indent=2))
            raise typer.Exit(1) from exc
        console.print(f"[red]Error:[/red] {exc}")
        console.print("[yellow]Workspace husks were not modified.[/yellow]")
        raise typer.Exit(1) from exc

    remaining = [
        *fix_result.skipped_registered,
        *fix_result.skipped_appeared_valid,
        *fix_result.skipped_unsafe,
    ]
    fix_payload: dict[str, object] = {
        **report.to_dict(),
        **fix_result.to_dict(),
        "healthy": not remaining,
    }
    if json_output:
        console.print_json(json.dumps(fix_payload, indent=2))
        raise typer.Exit(0 if not remaining else 1)

    for removed in fix_result.removed:
        console.print(f"[green]Removed husk:[/green] {removed}")
    for skipped in fix_result.skipped_registered:
        console.print(
            f"[yellow]Preserved registered worktree:[/yellow] {skipped} "
            "(repair manually: `git worktree repair` or `git worktree remove <path>`)"
        )
    for skipped in fix_result.skipped_appeared_valid:
        console.print(
            f"[yellow]Skipped path that became a git worktree:[/yellow] {skipped}"
        )
    for skipped in fix_result.skipped_unsafe:
        console.print(
            f"[yellow]Preserved husk holding local work:[/yellow] {skipped} "
            "(inspect or move its contents, then remove it by hand)"
        )
    if not report.husks:
        console.print("[green]No workspace husks found.[/green]")
    stale_results = _refresh_stale_coord_worktrees(repo_root)
    for wt_path, outcome in stale_results:
        if outcome == "refreshed":
            console.print(f"[green]Refreshed stale coord worktree:[/green] {wt_path}")
        elif outcome == "failed":
            console.print(f"[yellow]Could not refresh coord worktree:[/yellow] {wt_path}")
    raise typer.Exit(0 if not remaining else 1)


def _emit_workspace_husk_report(repo_root: Path, json_output: bool) -> None:
    from specify_cli.status import scan_workspace_husks

    report = scan_workspace_husks(repo_root)
    if json_output:
        console.print_json(json.dumps(report.to_dict(), indent=2))
        raise typer.Exit(0 if report.healthy else 1)

    if report.healthy:
        console.print("[green]No workspace husks found.[/green]")
        raise typer.Exit(0)
    if report.registration_error is not None and not report.husks:
        console.print(f"[red]Error:[/red] {report.registration_error}")
        raise typer.Exit(1)

    console.print(f"[bold]Workspace husks under {report.worktrees_dir}[/bold]")
    for entry in report.husks:
        status = _workspace_husk_status_label(entry.registered)
        console.print(f"  [yellow]![/yellow] {entry.path}  [dim]{status}[/dim]")
    console.print()
    if report.registration_error is not None:
        console.print(f"[red]Error:[/red] {report.registration_error}")
    console.print("Remove unregistered husks with: spec-kitty doctor workspaces --fix")
    raise typer.Exit(1)


_COORD_SUFFIX = "-coord"


def _registered_coord_worktrees(
    repo_root: Path, registered: RegisteredWorktreePaths,
) -> list[Path]:
    """Return registered coord worktrees under ``.worktrees/``.

    A coord worktree ends with ``-coord`` and is present in the git registry.
    Skips the ``.worktrees/`` directory when it does not exist.
    """
    from specify_cli.status import WORKTREES_DIRNAME

    worktrees_dir = repo_root / WORKTREES_DIRNAME
    if not worktrees_dir.is_dir() or registered.error:
        return []
    return [
        entry
        for entry in sorted(worktrees_dir.iterdir(), key=lambda p: p.name)
        if (
            entry.is_dir()
            and entry.name.endswith(_COORD_SUFFIX)
            and entry.resolve() in registered.paths
        )
    ]


def _coord_worktree_needs_refresh(worktree: Path, repo_root: Path) -> tuple[bool, str]:
    """Return (is_stale, branch_name).  is_stale=False when up-to-date or unreadable."""
    branch_result = subprocess.run(
        ["git", "-C", str(worktree), "symbolic-ref", "--short", "HEAD"],
        capture_output=True, text=True, check=False,
    )
    branch = branch_result.stdout.strip() if branch_result.returncode == 0 else ""
    if not branch:
        return False, ""
    head_result = subprocess.run(
        ["git", "-C", str(worktree), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=False,
    )
    tip_result = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", f"refs/heads/{branch}"],
        capture_output=True, text=True, check=False,
    )
    head_sha = head_result.stdout.strip() if head_result.returncode == 0 else ""
    tip_sha = tip_result.stdout.strip() if tip_result.returncode == 0 else ""
    if not head_sha or not tip_sha or head_sha == tip_sha:
        return False, branch
    ancestor = subprocess.run(
        ["git", "-C", str(repo_root), "merge-base", "--is-ancestor",
         head_sha, tip_sha],
        capture_output=True, check=False,
    )
    return ancestor.returncode == 0, branch


def _refresh_stale_coord_worktrees(
    repo_root: Path,
) -> list[tuple[str, str]]:
    """Fast-forward each stale registered coord worktree to its branch tip.

    Returns a list of ``(path_str, outcome)`` tuples where *outcome* is one of
    ``"refreshed"``, ``"failed"``, ``"already_current"``, or ``"skip_detached"``.
    """
    from specify_cli.status import registered_worktree_paths

    registered = registered_worktree_paths(repo_root)
    outcomes: list[tuple[str, str]] = []
    for worktree in _registered_coord_worktrees(repo_root, registered):
        stale, branch = _coord_worktree_needs_refresh(worktree, repo_root)
        if not branch:
            outcomes.append((str(worktree), "skip_detached"))
            continue
        if not stale:
            outcomes.append((str(worktree), "already_current"))
            continue
        merge = subprocess.run(
            ["git", "-C", str(worktree), "merge", "--ff-only",
             f"refs/heads/{branch}"],
            capture_output=True, check=False,
        )
        outcomes.append((str(worktree), "refreshed" if merge.returncode == 0 else "failed"))
    return outcomes


def run_workspaces(repo_root: Path, fix: bool, json_output: bool) -> None:
    """Entry point for ``doctor workspaces`` (0 clean / 1 husks-or-error).

    *repo_root* is resolved + injected by the ``doctor.py`` command shell.
    """
    if fix:
        _emit_workspace_husk_fix(repo_root, json_output)
        return
    _emit_workspace_husk_report(repo_root, json_output)
