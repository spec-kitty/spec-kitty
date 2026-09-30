"""Leak-check doctor sibling for the run index (mission runindex-feature-runs-port).

Self-registering ``doctor run-index`` subcommand: scans the current project's
``.kittify/runtime/feature-runs.json`` for absolute ``run_dir`` values that are
not portable across a project copy/move, and reports each with a heal hint.
Reuses the exact classification the heal migration
(``specify_cli.upgrade.migrations.m_4_0_0rc5_heal_run_index_paths.describe_leaks``)
uses, so "flagged by doctor" and "fixed by migrate" never drift apart.

Registered via ``doctor.py``'s auto-discovery seam (any ``cli/commands/_*_doctor.py``
exposing ``register(app)``); mirrors ``_provenance_doctor.py``. Read-only — never
mutates state.
"""

from __future__ import annotations

import json
from typing import Annotated

import typer

from specify_cli.core.paths import locate_project_root
from specify_cli.upgrade.migrations.m_4_0_0rc5_heal_run_index_paths import describe_leaks

from . import _doctor_shared
from ._doctor_shared import console

__all__ = ["register"]

_HEAL_HINT = "spec-kitty migrate  # rewrites absolute run_dir paths to portable tokens"


def _run_index_audit(repo_root, *, json_output: bool) -> None:  # type: ignore[no-untyped-def]
    """Entry point for ``doctor run-index``.

    Advisory (matches ``doctor provenance``): exits 1 when an absolute ``run_dir``
    leak is found so CI can gate on it if desired, but never mutates anything —
    healing is the explicit ``spec-kitty migrate`` step.
    """
    leaks = describe_leaks(repo_root)

    if json_output:
        payload = {
            "leaks": leaks,
            "leak_count": len(leaks),
            "heal_hint": _HEAL_HINT if leaks else None,
        }
        console.print_json(json.dumps(payload, indent=2))
        raise typer.Exit(1 if leaks else 0)

    if not leaks:
        console.print("[green]Run index[/green]: no absolute run_dir leaks found.")
        raise typer.Exit(0)

    console.print(f"\n[bold yellow]Run-index finding(s)[/bold yellow] -- {len(leaks)} absolute run_dir(s)\n")
    for leak in leaks:
        console.print(f"  • [yellow]{leak}[/yellow]")
    console.print(f"\n  [dim]Heal a relocated run index with:[/dim] {_HEAL_HINT}")
    console.print()
    raise typer.Exit(1)


def register(app: typer.Typer) -> None:
    """Register the ``run-index`` subcommand onto *app* (doctor.py auto-discovery seam)."""

    @app.command(name="run-index")
    def run_index(
        json_output: Annotated[
            bool,
            typer.Option("--json", help="Machine-readable JSON output"),
        ] = False,
    ) -> None:
        """Flag absolute run_dir paths in the run index that break on copy/move (#5390).

        Scans .kittify/runtime/feature-runs.json for run_dir values stored as
        absolute paths (nonportable — a copied or moved project resolves the
        original folder's cursor). Read-only; heal with ``spec-kitty migrate``.

        Examples:
            spec-kitty doctor run-index
            spec-kitty doctor run-index --json
        """
        repo_root = _doctor_shared.resolve_project_root_or_exit(locate_project_root, json_output)
        _run_index_audit(repo_root, json_output=json_output)
