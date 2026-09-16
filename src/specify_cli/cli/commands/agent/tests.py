"""Test-related commands for AI agents.

Provides the ``spec-kitty agent tests stale-check`` subcommand which wraps the
``run_check`` library function from ``specify_cli.post_merge.stale_assertions``.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Annotated

import typer
from specify_cli.cli.console import console
from specify_cli.cli.console import err_console
from rich.table import Table

from specify_cli.post_merge.stale_assertions import (
    FP_CEILING,
    StaleAssertionReport,
    run_check,
)

app = typer.Typer(
    name="tests",
    help="Test-related commands for AI agents",
    no_args_is_help=True,
)



def _report_to_dict(report: StaleAssertionReport) -> dict:  # type: ignore[type-arg]
    """Serialize a StaleAssertionReport to a JSON-compatible dict."""
    d = dataclasses.asdict(report)
    # Convert Path objects to strings for JSON serialization.
    d["repo_root"] = str(d["repo_root"])
    for finding in d.get("findings", []):
        finding["test_file"] = str(finding["test_file"])
        finding["source_file"] = str(finding["source_file"])
    return d


@app.command("stale-check")
def stale_check(
    base: Annotated[str, typer.Option("--base", help="Base git ref for the diff")],
    head: Annotated[str, typer.Option("--head", help="Head git ref for the diff")] = "HEAD",
    repo_root: Annotated[
        Path, typer.Option("--repo", help="Repository root (default: current directory)")
    ] = Path("."),
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit JSON instead of human-readable text")
    ] = False,
) -> None:
    """Detect test assertions likely invalidated by source changes between two refs.

    Compares BASE..HEAD and reports assertions in the test suite that reference
    symbols (functions, classes, string literals) that were renamed or removed in
    the source diff.  Uses AST analysis only — no regex on test text, no test
    execution.

    Confidence levels:
      high   — identifier referenced directly inside Assert or assert* call
      medium — identifier appears anywhere in an assertion node
      low    — string literal matches a Constant in an assertion-bearing position
      info   — message-content check (literal checked against captured
               diagnostic text); skipped from CI noise, surfaced for manual
               review (#3957)
    """
    resolved_root = repo_root.resolve()

    report = run_check(base_ref=base, head_ref=head, repo_root=resolved_root)

    # FR-022 self-monitoring: warn to stderr if FP ceiling exceeded.
    if report.findings_per_100_loc > FP_CEILING:
        err_console.print(
            f"[yellow]WARNING[/yellow]: findings_per_100_loc={report.findings_per_100_loc:.1f} "
            f"exceeds NFR-002 ceiling of {FP_CEILING:.1f}. "
            "Consider narrowing scope to function-rename detection only (FR-022).",
        )

    if json_output:
        console.print_json(json.dumps(_report_to_dict(report)))
        return

    # --- Rich human-readable output ---
    console.print(
        f"\n[bold]Stale-assertion analysis:[/bold] "
        f"{report.base_ref!r} → {report.head_ref!r}"
    )
    console.print(
        f"  scanned {report.files_scanned} test file(s) in "
        f"{report.elapsed_seconds:.2f}s | "
        f"findings/100 LOC: {report.findings_per_100_loc:.2f}"
    )

    if not report.findings:
        console.print("[green]No stale assertions detected.[/green]\n")
        return

    # Group by confidence for readability. Info-grade (message-content)
    # findings are surfaced with their own title, not silently dropped
    # (#3957) — they are the assertions the analyzer deliberately skips.
    for level in ("high", "medium", "low", "info"):
        level_findings = [f for f in report.findings if f.confidence == level]
        if not level_findings:
            continue

        if level == "info":
            title = (
                "[bold]INFO — message-content assertions[/bold] "
                "(skipped from CI noise; review manually if diagnostic text changed)"
            )
        else:
            title = f"[bold]{level.upper()} confidence[/bold]"

        table = Table(
            title=title,
            show_header=True,
            header_style="bold",
        )
        table.add_column("Test file", style="cyan", no_wrap=False)
        table.add_column("Line", justify="right")
        table.add_column("Changed symbol", style="yellow")
        table.add_column("Source file")
        table.add_column("Hint")

        for finding in level_findings:
            table.add_row(
                str(finding.test_file.relative_to(resolved_root)
                    if finding.test_file.is_relative_to(resolved_root)
                    else finding.test_file),
                str(finding.test_line),
                finding.changed_symbol,
                f"{finding.source_file.name}:{finding.source_line}",
                finding.hint,
            )

        console.print(table)

    console.print()
