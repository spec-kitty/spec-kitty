"""``spec-kitty charter consistency-check`` — coherence of the active charter.

Checks the project's active charter (activated artifacts, references and DRG
kind coverage) against the offering (OD-8; formerly
``charter pack consistency-check``, moved by mission
charter-pack-cutover-01M491G6, FR-006). Exits 0 when coherent, 1 otherwise.
"""

from __future__ import annotations

from pathlib import Path

import typer

from charter.activation.invocation_context import ProjectContext
from specify_cli.cli.console import console

__all__ = ["consistency_check_cmd"]


def consistency_check_cmd(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
    repo_root: Path = typer.Option(Path("."), hidden=True),
) -> None:
    """Check the active charter for coherence against the offering (FR-011)."""
    from charter.activation.consistency_check import run_consistency_check  # noqa: PLC0415

    ctx = ProjectContext.from_repo(repo_root)
    report = run_consistency_check(ctx)
    if json_output:
        typer.echo(report.to_json())
    else:
        if report.coherent:
            console.print("[green]Active charter is coherent.[/green]")
        else:
            console.print("[red]Consistency issues found:[/red]")
            for ref in report.unknown_references:
                console.print(f"  [red]Unknown reference:[/red] {ref}")
            for ref in report.missing_from_offering:
                console.print(f"  [yellow]Missing from charter.offering:[/yellow] {ref}")
            for v in report.kind_violations:
                console.print(f"  [red]Kind violation:[/red] {v}")
            for ref in report.reference_id_divergences:
                console.print(f"  [red]Reference ID divergence:[/red] {ref}")
            for kind in report.graph_kind_gaps:
                console.print(f"  [red]Graph kind gap:[/red] {kind}")
            for s in report.suggestions:
                console.print(f"  [dim]Suggestion:[/dim] {s}")
    raise typer.Exit(0 if report.coherent else 1)
