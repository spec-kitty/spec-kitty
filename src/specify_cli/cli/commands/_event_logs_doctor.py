"""Retention doctor sibling for local event logs (#6610, ADR 2026-10-13-2 D-3).

Self-registering ``doctor event-logs`` subcommand: previews, then on request
prunes, the gitignored run journals, per-Mission glossary logs and rebuildable
caches under ``.kittify/`` that are past retention. The
verdicts come from the retention engine (:mod:`specify_cli.state.retention`);
the limits come from ``ledger.retention`` in ``.kittify/config.yaml``
(:mod:`specify_cli.core.ledger_retention`). This module only renders the
engine's report and maps its outcome to an exit code.

Registered via ``doctor.py``'s auto-discovery seam (any ``cli/commands/_*_doctor.py``
exposing ``register(app)``); mirrors ``_run_index_doctor.py``. It changes
nothing unless ``--apply`` is given (FR-006).

Exit codes (FR-012; unlike the doctor family's "1 = findings", a preview with
candidates exits 0): 0 for a preview or an apply where every deletion
succeeded, 1 when at least one deletion failed, 2 when the command is not run
inside a project, the configuration cannot be read or ``ledger.retention`` is
invalid, or the state registry and the engine disagree (nothing is scanned or
deleted then).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.markup import escape

from specify_cli.core.ledger_retention import RetentionConfigError, RetentionLimits, load_retention_limits
from specify_cli.core.paths import locate_project_root
from specify_cli.state.retention import (
    RetentionPlan,
    RetentionPolicyDriftError,
    RetentionResult,
    apply_retention,
    scan_retention,
)

from . import _doctor_shared
from ._doctor_shared import console

__all__ = ["register"]

_EXIT_OK = 0
_EXIT_DELETION_FAILED = 1
_EXIT_USAGE = 2

_CONFIG_ERROR_CODE = "config_error"
_DRIFT_ERROR_CODE = "retention_policy_drift"
_DRIFT_PREFIX = "Internal error: the state registry and the retention engine disagree."

_ITEM_DETAIL_INDENT = "      "


# ---------------------------------------------------------------------------
# Errors (exit 2, nothing scanned or deleted)
# ---------------------------------------------------------------------------


def _fail_usage(code: str, message: str, *, json_output: bool) -> typer.Exit:
    """Emit *message* on the channel the caller asked for and return the exit-2 signal."""
    if json_output:
        console.print_json(json.dumps(_doctor_shared._json_error(code, message), indent=2))
    else:
        console.print(f"[red]Error:[/red] {escape(message)}")
    return typer.Exit(_EXIT_USAGE)


def _load_limits_or_exit(repo_root: Path, *, json_output: bool) -> RetentionLimits:
    try:
        return load_retention_limits(repo_root)
    except RetentionConfigError as exc:
        raise _fail_usage(_CONFIG_ERROR_CODE, str(exc), json_output=json_output) from exc


def _scan_or_exit(repo_root: Path, limits: RetentionLimits, *, json_output: bool) -> RetentionPlan:
    try:
        return scan_retention(repo_root, limits)
    except RetentionPolicyDriftError as exc:
        message = f"{_DRIFT_PREFIX} {exc} Please report this; nothing was scanned or deleted."
        raise _fail_usage(_DRIFT_ERROR_CODE, message, json_output=json_output) from exc


# ---------------------------------------------------------------------------
# Human rendering (from the same payload --json emits)
# ---------------------------------------------------------------------------


def _print_item(item: Mapping[str, Any], *, detail: str | None = None) -> None:
    console.print(f"  • {escape(str(item['path']))}")
    line = f"{item['surface']} · {item['age_days']} days old · {detail if detail is not None else item['reason']}"
    console.print(f"{_ITEM_DETAIL_INDENT}[dim]{escape(line)}[/dim]")


def _print_section(title: str, items: Sequence[Mapping[str, Any]], *, error_key: str | None = None) -> None:
    if not items:
        return
    console.print(f"\n[bold]{title} ({len(items)})[/bold]")
    for item in items:
        _print_item(item, detail=str(item[error_key]) if error_key else None)


def _print_kept(kept: Sequence[Mapping[str, Any]]) -> None:
    """Every kept item, grouped under its reason, so each kept reason is visible."""
    if not kept:
        return
    console.print(f"\n[bold]Kept ({len(kept)})[/bold]")
    by_reason: dict[str, list[Mapping[str, Any]]] = {}
    for item in kept:
        by_reason.setdefault(str(item["reason"]), []).append(item)
    for reason, items in by_reason.items():
        console.print(f"  [green]{escape(reason)}[/green] ({len(items)})")
        for item in items:
            console.print(f"    - {escape(str(item['path']))} [dim]({escape(str(item['surface']))})[/dim]")


def _render_human(payload: Mapping[str, Any]) -> None:
    applied = bool(payload["applied"])
    limits = payload["limits"]
    mode = "Apply" if applied else "Preview (nothing changed)"
    console.print(f"\n[bold]Local event-log retention[/bold] — {mode}")
    console.print(f"[dim]Limits: keep_runs={limits['keep_runs']}, max_age_days={limits['max_age_days']} (source: {escape(str(limits['source']))})[/dim]")

    candidates = payload["candidates"]
    if not candidates:
        console.print("\n[green]Nothing to remove:[/green] no item is past retention.")
    elif applied:
        deleted = payload["deleted"]
        if deleted:
            console.print(f"\n[bold green]Deleted {len(deleted)} item(s)[/bold green]")
            for item in deleted:
                _print_item(item)
        else:
            console.print("\n[yellow]Nothing was deleted.[/yellow]")
        _print_section("Failed", payload["failed"], error_key="error")
        _print_section_lines("Removed run-index entries", payload["removed_index_entries"])
    else:
        _print_section("Candidates", candidates)

    _print_kept(payload["kept"])

    if candidates and not applied:
        console.print(f"\nRun with --apply to delete these {len(candidates)} item(s).")
    console.print()


def _print_section_lines(title: str, lines: Sequence[str]) -> None:
    if not lines:
        return
    console.print(f"\n[bold]{title} ({len(lines)})[/bold]")
    for line in lines:
        console.print(f"  • {escape(line)}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _event_logs(repo_root: Path, *, apply: bool, json_output: bool) -> None:
    """Scan, optionally apply, render, and exit per FR-012."""
    limits = _load_limits_or_exit(repo_root, json_output=json_output)
    plan = _scan_or_exit(repo_root, limits, json_output=json_output)
    report: RetentionPlan | RetentionResult = apply_retention(repo_root, plan) if apply else plan
    payload = report.to_dict(repo_root)
    if json_output:
        console.print_json(json.dumps(payload, indent=2))
    else:
        _render_human(payload)
    raise typer.Exit(_EXIT_DELETION_FAILED if payload["failed"] else _EXIT_OK)


def register(app: typer.Typer) -> None:
    """Register the ``event-logs`` subcommand onto *app* (doctor.py auto-discovery seam)."""

    @app.command(name="event-logs")
    def event_logs_command(
        apply: Annotated[
            bool,
            typer.Option("--apply", help="Delete the listed candidates (default: preview only)"),
        ] = False,
        json_output: Annotated[
            bool,
            typer.Option("--json", help="Machine-readable JSON output"),
        ] = False,
    ) -> None:
        """Preview, then prune, local run journals, event logs and caches past retention (#6610).

        Reads ledger.retention (keep_runs, max_age_days) from .kittify/config.yaml;
        an item is removed only when it is outside the newest keep_runs of its kind
        AND older than max_age_days, and its work is over: a run once its Mission
        is merged or the run finished, a glossary log once its Mission is
        completed. Rebuildable caches are candidates whatever their age, unless
        locked. Committed ledgers, the Op index, lock files, items of an open or
        unknown Mission and locked items are never removed.

        Without --apply nothing changes. Exit codes: 0 preview or clean apply,
        1 a deletion failed, 2 config, usage or internal error.

        Examples:
            spec-kitty doctor event-logs
            spec-kitty doctor event-logs --json
            spec-kitty doctor event-logs --apply
        """
        repo_root = _doctor_shared.resolve_project_root_or_exit(locate_project_root, json_output, exit_code=_EXIT_USAGE)
        _event_logs(repo_root, apply=apply, json_output=json_output)
