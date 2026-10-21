"""Typer command for ``spec-kitty charter preflight``.

Wires :func:`specify_cli.charter_preflight.runner.run_charter_preflight`
into the existing ``charter`` typer app via
``src/specify_cli/cli/commands/charter.py``.

Exit-code contract (binding,
``contracts/charter-preflight-json.md`` §"Exit codes"):

* ``0`` — ``passed=True`` OR (``passed=False`` AND ``--strict`` not set).
* ``1`` — ``passed=False`` AND ``--strict`` set.
* ``2`` — hard error (charter file unreadable, internal exception, etc.).
  In this case **no JSON payload is printed**, only a single stderr line.

Human output is intentionally compact — operators reading this in CI
should see the pass/fail headline first and the per-layer details
below, with the recovery command at the bottom when blocked.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer
from rich.console import Console

from charter.activation.api import ActiveCharterConfigError
from specify_cli.charter_runtime.preflight.result import CharterPreflightResult
from specify_cli.charter_runtime.preflight.runner import run_charter_preflight
from specify_cli.task_utils import TaskCliError, find_repo_root

__all__ = ["charter_preflight"]


_console = Console()
_err_console = Console(stderr=True)


def charter_preflight(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Emit the result as JSON (binding shape, see "
        "contracts/charter-preflight-json.md).",
    ),
    auto_refresh: bool = typer.Option(
        False,
        "--auto-refresh",
        help="When checks fail and the worktree has no uncommitted "
        "generated artifacts, run the safe refresh sequence "
        "(charter generate / upgrade --yes -> synthesize -> bundle validate).",
    ),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Exit non-zero on any non-fresh state (default: exit zero "
        "unless a hard error occurs).",
    ),
) -> None:
    """Verify charter-derived state before a governed session begins.

    Pipeline:

    1. Resolve the repo root (same logic as the rest of the ``charter``
       subcommand group).
    2. Invoke :func:`run_charter_preflight`.
    3. Render JSON or a Rich summary, then exit per the contract.
    """
    try:
        repo_root = find_repo_root()
    except TaskCliError as exc:
        # Hard error -> exit 2, no JSON payload (per the contract).
        _err_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    try:
        result = run_charter_preflight(
            Path(repo_root),
            auto_refresh=auto_refresh,
            strict=strict,
        )
    except ActiveCharterConfigError as exc:
        # The activation store cannot be read (e.g. a malformed ledger): render
        # the code and the body, which names the file and the remediation.
        # Deferred import: the charter command package imports this module at load time.
        from specify_cli.cli.commands.charter.activate import render_pack_config_error

        render_pack_config_error(exc, _err_console)
        raise typer.Exit(code=2) from exc
    except Exception as exc:  # noqa: BLE001 — defence in depth; runner is documented as non-raising.
        _err_console.print(f"[red]Error:[/red] preflight aborted: {exc}")
        raise typer.Exit(code=2) from exc

    if json_output:
        # ``print`` rather than rich-console so the JSON is byte-exact and
        # diffable across runs (no ANSI, no rich wrapping).
        sys.stdout.write(json.dumps(result.to_dict(), sort_keys=True, ensure_ascii=False))
        sys.stdout.write("\n")
        sys.stdout.flush()
    else:
        _render_human(result)

    # Exit-code mapping per contract.
    if result.passed:
        raise typer.Exit(code=0)
    if strict:
        raise typer.Exit(code=1)
    raise typer.Exit(code=0)


def _render_human(result: CharterPreflightResult) -> None:
    """Print a compact human summary."""
    headline_colour = "green" if result.passed else "red"
    headline = "PASSED" if result.passed else "BLOCKED"
    _console.print(f"[bold {headline_colour}]Charter preflight: {headline}[/bold {headline_colour}]")

    for check in result.checks:
        colour = {
            "fresh": "green",
            "skipped": "dim",
            "built_in_only": "cyan",
            "stale": "yellow",
            "missing": "blue",
            "invalid": "red",
        }.get(check.state, "white")
        line = f"  [{colour}]{check.state.upper():>14}[/{colour}]  {check.name}: {check.detail}"
        _console.print(line)
        if check.remediation:
            _console.print(f"                  [dim]Run: {check.remediation}[/dim]")

    if result.auto_refresh_applied:
        _console.print("\n[bold]Auto-refresh:[/bold]")
        for cmd in result.auto_refresh_actions:
            _console.print(f"  [green]ran:[/green] {cmd}")

    if result.blocked_reason:
        _console.print(f"\n[red]Blocked:[/red] {result.blocked_reason}")
