"""Operator-facing `retrospect` CLI surface.

Command surface: ``spec-kitty retrospect summary``

Reads the project's mission corpus from kitty-specs/*/retrospective.yaml
and kitty-specs/*/status.events.jsonl and emits a cross-mission summary.
No mutation is performed.

Source-of-truth:
    kitty-specs/mission-retrospective-learning-loop-01KQ6YEG/contracts/cli_surfaces.md
"""

from __future__ import annotations

from specify_cli.core.constants import KITTY_SPECS_DIR
from kernel.clock import now_utc_iso, date
import json
from pathlib import Path
from typing import Optional

import typer
from rich.panel import Panel
from rich.table import Table
from typing_extensions import Annotated

from specify_cli.cli.console import console as _console
from specify_cli.cli.console import err_console as _err_console

from specify_cli.retrospective.summary import (
    SummarySnapshot,
    build_summary,
)

app = typer.Typer(
    name="retrospect",
    help=(
        "Retrospective operator surface.\n\n"
        "Reads kitty-specs/*/retrospective.yaml and "
        "kitty-specs/*/status.events.jsonl. "
        "No mutation is performed."
    ),
    no_args_is_help=True,
)

# Output routes through the canonical CLI console seam (GitHub #2635):
# ``--json`` payloads bypass Rich's highlighter via ``CliConsole.print_json``,
# so a FORCE_COLOR-forcing harness never splices ANSI escapes into the JSON.


# ---------------------------------------------------------------------------
# JSON envelope helper
# ---------------------------------------------------------------------------


def _build_json_envelope(snapshot: SummarySnapshot) -> dict[str, object]:
    """Build the JSON output envelope per cli_surfaces.md."""
    return {
        "schema_version": "1",
        "command": "retrospect.summary",
        "generated_at": now_utc_iso(),
        "result": snapshot.model_dump(),
    }


# ---------------------------------------------------------------------------
# Rich renderer
# ---------------------------------------------------------------------------


def _render_rich(
    snapshot: SummarySnapshot,
    *,
    include_malformed: bool = False,
) -> None:
    """Render the SummarySnapshot as Rich output (informationally equiv to JSON)."""
    _console.print(
        Panel(
            "[bold cyan]Cross-Mission Retrospective Summary[/bold cyan]",
            expand=False,
        )
    )

    # --- Counts section ---
    counts_table = Table(title="Counts", show_header=True, header_style="bold")
    counts_table.add_column("Category")
    counts_table.add_column("Count", justify="right")
    counts_table.add_row("mission_count", str(snapshot.mission_count))
    counts_table.add_row("completed", str(snapshot.completed_count))
    counts_table.add_row("skipped", str(snapshot.skipped_count))
    counts_table.add_row("failed", str(snapshot.failed_count))
    counts_table.add_row("in_flight", str(snapshot.in_flight_count))
    counts_table.add_row("legacy_no_retro", str(snapshot.legacy_no_retro_count))
    counts_table.add_row("terminus_no_retro", str(snapshot.terminus_no_retro_count))
    counts_table.add_row("malformed", str(len(snapshot.malformed)))
    _console.print(counts_table)

    # --- Top Not-Helpful ---
    if snapshot.not_helpful_top:
        nh_table = Table(title="Top Not-Helpful Targets", show_header=True, header_style="bold yellow")
        nh_table.add_column("URN")
        nh_table.add_column("Count", justify="right")
        for tc in snapshot.not_helpful_top:
            nh_table.add_row(tc.urn, str(tc.count))
        _console.print(nh_table)

    # --- Top Missing Terms ---
    if snapshot.missing_terms_top:
        mt_table = Table(title="Top Missing Glossary Terms", show_header=True, header_style="bold magenta")
        mt_table.add_column("Term URN")
        mt_table.add_column("Count", justify="right")
        for term_c in snapshot.missing_terms_top:
            mt_table.add_row(term_c.key, str(term_c.count))
        _console.print(mt_table)

    # --- Top Missing Edges ---
    if snapshot.missing_edges_top:
        me_table = Table(title="Top Missing DRG Edges", show_header=True, header_style="bold magenta")
        me_table.add_column("Edge URN")
        me_table.add_column("Count", justify="right")
        for ec in snapshot.missing_edges_top:
            me_table.add_row(ec.urn, str(ec.count))
        _console.print(me_table)

    # --- Top Over-Inclusion ---
    if snapshot.over_inclusion_top:
        oi_table = Table(title="Top Over-Inclusion Targets", show_header=True, header_style="bold red")
        oi_table.add_column("URN")
        oi_table.add_column("Count", justify="right")
        for tc in snapshot.over_inclusion_top:
            oi_table.add_row(tc.urn, str(tc.count))
        _console.print(oi_table)

    # --- Top Under-Inclusion ---
    if snapshot.under_inclusion_top:
        ui_table = Table(title="Top Under-Inclusion Targets", show_header=True, header_style="bold blue")
        ui_table.add_column("URN")
        ui_table.add_column("Count", justify="right")
        for tc in snapshot.under_inclusion_top:
            ui_table.add_row(tc.urn, str(tc.count))
        _console.print(ui_table)

    # --- Proposal Acceptance Metrics ---
    pa = snapshot.proposal_acceptance
    pa_table = Table(title="Proposal Acceptance Metrics", show_header=True, header_style="bold green")
    pa_table.add_column("Metric")
    pa_table.add_column("Count", justify="right")
    pa_table.add_row("total", str(pa.total))
    pa_table.add_row("accepted", str(pa.accepted))
    pa_table.add_row("rejected", str(pa.rejected))
    pa_table.add_row("applied", str(pa.applied))
    pa_table.add_row("pending", str(pa.pending))
    pa_table.add_row("superseded", str(pa.superseded))
    _console.print(pa_table)

    # --- Top Skip Reasons ---
    if snapshot.skip_reasons_top:
        sr_table = Table(title="Top Skip Reasons", show_header=True, header_style="bold")
        sr_table.add_column("Reason")
        sr_table.add_column("Count", justify="right")
        for rc in snapshot.skip_reasons_top:
            sr_table.add_row(rc.reason, str(rc.count))
        _console.print(sr_table)

    # --- Malformed ---
    if snapshot.malformed:
        _console.print(f"\n[bold red]Malformed records:[/bold red] {len(snapshot.malformed)}")
        if include_malformed:
            mf_table = Table(title="Malformed Detail", show_header=True, header_style="bold red")
            mf_table.add_column("mission_id")
            mf_table.add_column("path")
            mf_table.add_column("reason")
            for entry in snapshot.malformed:
                mf_table.add_row(
                    entry.mission_id or "(unknown)",
                    entry.path,
                    entry.reason,
                )
            _console.print(mf_table)


# ---------------------------------------------------------------------------
# summary subcommand
# ---------------------------------------------------------------------------


@app.command(
    "summary",
    help=(
        "Cross-mission retrospective summary.\n\n"
        "Reads kitty-specs/*/retrospective.yaml and "
        "kitty-specs/*/status.events.jsonl to produce a cross-mission view.\n\n"
        "No mutation is performed."
    ),
)
def summary_cmd(
    project: Annotated[
        Optional[Path],
        typer.Option("--project", help="Project root (default: current working directory)"),
    ] = None,
    json_only: Annotated[
        bool,
        typer.Option("--json", help="Emit JSON to stdout instead of Rich rendering"),
    ] = False,
    json_out: Annotated[
        Optional[Path],
        typer.Option(
            "--json-out",
            help="Emit JSON to a file in addition to whatever rendering is selected",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", min=1, max=100, help="Top-N for ranked sections (default: 20)"),
    ] = 20,
    since: Annotated[
        Optional[str],
        typer.Option("--since", help="ISO-8601 date; only include missions started on or after DATE"),
    ] = None,
    include_malformed: Annotated[
        bool,
        typer.Option(
            "--include-malformed",
            help="Include malformed records' detail in output (default: counts only)",
        ),
    ] = False,
) -> None:
    """Cross-mission retrospective summary.

    Reads kitty-specs/*/retrospective.yaml and
    kitty-specs/*/status.events.jsonl.
    No mutation is performed.
    """
    # Resolve project root
    resolved_project: Path
    if project is not None:
        resolved_project = project.resolve()
    else:
        resolved_project = Path.cwd()

    # Validate project root: exit 1 if neither .kittify/ nor kitty-specs/ exists
    has_kittify = (resolved_project / ".kittify").exists()
    has_mission_specs = (resolved_project / KITTY_SPECS_DIR).exists()
    if not has_kittify and not has_mission_specs:
        _err_console.print(
            "[red]Error:[/red] Project root invalid: "
            f"neither .kittify/ nor kitty-specs/ found in {resolved_project}"
        )
        raise typer.Exit(1)

    # Parse --since
    since_date: date | None = None
    if since is not None:
        try:
            since_date = date.fromisoformat(since)
        except ValueError:
            _err_console.print(
                f"[red]Error:[/red] Invalid --since date {since!r}. "
                "Expected ISO-8601 format (YYYY-MM-DD)."
            )
            raise typer.Exit(1)

    # Run the reducer
    try:
        snapshot = build_summary(
            project_path=resolved_project,
            since=since_date,
            limit_top_n=limit,
        )
    except OSError as exc:
        _err_console.print(f"[red]Error:[/red] I/O error reading corpus: {exc}")
        raise typer.Exit(2)

    # Build JSON envelope
    envelope = _build_json_envelope(snapshot)

    # Render
    if json_only:
        _console.print_json(json.dumps(envelope))
    else:
        _render_rich(snapshot, include_malformed=include_malformed)

    if json_out is not None:
        try:
            json_out.parent.mkdir(parents=True, exist_ok=True)
            json_out.write_text(json.dumps(envelope, indent=2), encoding="utf-8")
            if not json_only:
                _console.print(f"\n[dim]JSON written to {json_out}[/dim]")
        except OSError as exc:
            _err_console.print(f"[red]Error:[/red] Could not write JSON to {json_out}: {exc}")
            raise typer.Exit(2)

    raise typer.Exit(0)
