"""Leak-check doctor sibling for committed provenance (T015, C-PRV-5).

Self-registering ``doctor provenance`` subcommand: scans the current
project's committed ``.kittify/charter/charter.yaml`` catalog and
``.kittify/agent_profiles_manifest.json`` for an absolute built-in-pack
``source_path`` and reports each leak with a heal hint. Reuses the exact same
classification the heal migration
(``specify_cli.upgrade.migrations.m_3_2_7_heal_provenance_paths.describe_leaks``)
uses to decide what is healable, so "flagged by doctor" and "fixed by heal"
never drift apart.

**Auto-discovery seam (T015, the load-bearing fix for the WP03/WP04/WP05
three-lane collision).** ``doctor.py`` no longer hand-imports each sibling
and hand-writes its ``@app.command`` shell; it instead imports every
``cli/commands/_*_doctor.py`` module and calls ``register(app)`` when the
module exposes one (mirrors the migration auto-discovery at
``upgrade/migrations/__init__.py``). This module is the first to use the new
seam: it never requires an edit to ``doctor.py``, and neither will a future
sibling (e.g. WP04/WP05's own doctor checks).

Import discipline (mirrors the existing sibling convention, e.g.
``_cutover_doctor.py``): shared console/output infra comes from
``._doctor_shared``; this module never imports ``doctor.py`` itself.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from specify_cli.core.paths import locate_project_root
from specify_cli.upgrade.migrations.m_3_2_7_heal_provenance_paths import describe_leaks

from ._doctor_shared import _emit_not_in_project, console

__all__ = ["register", "run_provenance_audit"]

_HEAL_HINT = "spec-kitty migrate  # applies m_3_2_7_heal_provenance_paths"


def run_provenance_audit(repo_root: Path, *, json_output: bool) -> None:
    """Entry point for ``doctor provenance``.

    Advisory (matches ``doctor cutover``'s informational shape): exits 1 when
    a leak is found so CI can gate on it if desired, but this command never
    mutates anything -- healing is a separate, explicit ``spec-kitty
    migrate`` step.
    """
    leaks = describe_leaks(repo_root)

    if json_output:
        payload = {"leaks": leaks, "leak_count": len(leaks), "heal_hint": _HEAL_HINT}
        console.print_json(json.dumps(payload, indent=2))
        raise typer.Exit(1 if leaks else 0)

    if not leaks:
        console.print(
            "[green]Provenance[/green]: no absolute built-in-pack source_path leaks found."
        )
        raise typer.Exit(0)

    console.print(
        f"\n[bold yellow]Provenance leak(s)[/bold yellow] -- {len(leaks)} absolute "
        "built-in-pack source_path(s)\n"
    )
    for leak in leaks:
        console.print(f"  • [yellow]{leak}[/yellow]")
    console.print(f"\n  [dim]Heal with:[/dim] {_HEAL_HINT}\n")
    raise typer.Exit(1)


def register(app: typer.Typer) -> None:
    """Register the ``provenance`` subcommand onto *app* (doctor.py auto-discovery seam)."""

    @app.command(name="provenance")
    def provenance(
        json_output: Annotated[
            bool,
            typer.Option("--json", help="Machine-readable JSON output"),
        ] = False,
    ) -> None:
        """Flag committed absolute built-in-pack source_path leaks (C-PRV-5).

        Scans .kittify/charter/charter.yaml's catalog and
        .kittify/agent_profiles_manifest.json for a source_path that should
        be a ${SPEC_KITTY_PACKS_ROOT}/built-in/... token but is not, and
        prints a heal hint for each. Read-only -- never mutates state.

        Examples:
            spec-kitty doctor provenance
            spec-kitty doctor provenance --json
        """
        try:
            repo_root = locate_project_root()
        except Exception as exc:
            _emit_not_in_project(json_output)
            raise typer.Exit(1) from exc
        if repo_root is None:
            _emit_not_in_project(json_output)
            raise typer.Exit(1)
        run_provenance_audit(repo_root, json_output=json_output)
