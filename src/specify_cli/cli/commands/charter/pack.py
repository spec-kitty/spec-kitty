"""spec-kitty charter pack — charter pack commands.

``list`` / ``path`` read the project's offering (FR-004 / FR-006): one row per
pack (the built-in pack, each declared org pack, and the ``project`` layer)
with the activation presets it ships (``presets/<name>.yaml``), resolved through
:func:`charter.packs.list_offering_packs`. A preset is applied with
``spec-kitty charter activate [--pack <pack>] --preset <preset>``.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.markup import escape
from rich.table import Table
from specify_cli.cli.console import console

from charter.activation.invocation_context import ProjectContext
from charter.activation.preset_application import PresetApplicationError, find_offering_pack, load_pack_preset
from charter.packs import OfferingPack, PresetFormatError, discover_presets, list_offering_packs
from specify_cli.cli.commands.charter._coded_errors import render_coded_error, render_preset_format_error

__all__ = ["charter_pack_app"]

charter_pack_app = typer.Typer(
    name="pack",
    help="Charter pack management commands.",
    no_args_is_help=True,
)


@charter_pack_app.command("consistency-check")
def consistency_check_cmd(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
    repo_root: Path = typer.Option(Path("."), hidden=True),
) -> None:
    """Run consistency check against activated doctrine artifacts (FR-011)."""
    from charter.activation.consistency_check import run_consistency_check  # noqa: PLC0415

    ctx = ProjectContext.from_repo(repo_root)
    report = run_consistency_check(ctx)
    if json_output:
        typer.echo(report.to_json())
    else:
        if report.coherent:
            console.print("[green]Charter pack is coherent.[/green]")
        else:
            console.print("[red]Consistency issues found:[/red]")
            for ref in report.unknown_references:
                console.print(f"  [red]Unknown reference:[/red] {ref}")
            for ref in report.missing_from_doctrine:
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


#: Name of the project layer's row (spec Key Entities: it ships no presets).
_PROJECT_PACK = "project"
_KITTIFY_DIRNAME = ".kittify"


def _pack_rows(repo_root: Path) -> list[dict[str, object]]:
    """One row per offering pack with its presets.

    The ``project`` row is listed only inside a project (``.kittify/``
    present): outside one there is no project layer to report.
    """
    rows: list[dict[str, object]] = []
    in_project = (repo_root / _KITTIFY_DIRNAME).is_dir()
    for pack in list_offering_packs(repo_root):
        if pack.name == _PROJECT_PACK and pack.tier == _PROJECT_PACK and not in_project:
            continue
        rows.append({"name": pack.name, "tier": pack.tier, "root": str(pack.root), "presets": _preset_rows(pack)})
    return rows


def _preset_rows(pack: OfferingPack) -> list[dict[str, str]]:
    if not pack.ships_presets or not pack.root.is_dir():
        return []
    return [{"name": preset.name, "description": preset.description, "path": str(preset.source)} for preset in discover_presets(pack.root)]


@charter_pack_app.command("list")
def list_cmd(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
    repo_root: Path = typer.Option(Path("."), hidden=True),
) -> None:
    """List the packs of the project's offering and the presets each ships (FR-004)."""
    try:
        rows = _pack_rows(repo_root.resolve())
    except PresetFormatError as exc:
        render_preset_format_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    if json_output:
        console.emit_json({"packs": rows})
        return
    table = Table(title="Charter packs")
    table.add_column("Pack")
    table.add_column("Tier")
    table.add_column("Presets")
    for row in rows:
        presets = row["presets"]
        names = ", ".join(preset["name"] for preset in presets) if isinstance(presets, list) else ""
        table.add_row(escape(str(row["name"])), str(row["tier"]), escape(names) or "—")
    console.print(table)
    console.print("\n[dim]Apply a preset with `spec-kitty charter activate [--pack <pack>] --preset <preset>`.[/dim]")


@charter_pack_app.command("path")
def path_cmd(
    pack: str = typer.Argument(..., help="Pack name (built-in, an org pack name, or project)."),
    preset: str | None = typer.Option(None, "--preset", help="Print this preset's file instead of the pack root."),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
    repo_root: Path = typer.Option(Path("."), hidden=True),
) -> None:
    """Print a pack's root, or with --preset the preset file (FR-006).

    Fails closed (exit 1) with PACK_NOT_FOUND or PRESET_NOT_FOUND, listing the
    valid names.
    """
    try:
        offering_pack = find_offering_pack(repo_root.resolve(), pack)
        path = offering_pack.root if preset is None else load_pack_preset(offering_pack, preset).source
    except PresetApplicationError as exc:
        render_coded_error(exc.code, str(exc), details=exc.detail_lines(), payload=exc.payload(), json_output=json_output)
        raise typer.Exit(1) from exc
    except PresetFormatError as exc:
        render_preset_format_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    if json_output:
        payload: dict[str, str] = {"pack": offering_pack.name, "path": str(path)}
        if preset is not None:
            payload["preset"] = preset
        console.emit_json(payload)
    else:
        typer.echo(str(path))
