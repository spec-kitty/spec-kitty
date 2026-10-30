"""Release packaging commands for AI agents.

The ``prep`` subcommand builds release artifacts from local filesystem
artifacts only (no network calls per FR-014):

  - Draft changelog block from ``kitty-specs/`` accepted missions/WPs
  - Proposed version bump based on release channel (alpha / beta / stable)
  - Structured inputs for the GitHub release tag/PR workflow

Automated steps (what this command does):
  - Changelog draft
  - Version bump proposal
  - Structured release-prep payload (JSON-serializable)

Still-manual steps (FR-023 scope cut):
  - PR creation: ``gh pr create --title "..." --body "<changelog>"``
  - Tag push: ``git tag -a vX.Y.Z -m "..." && git push origin vX.Y.Z``
  - Release workflow monitoring: ``gh run watch``
"""

from __future__ import annotations

import json as _json
from dataclasses import asdict
from pathlib import Path

import typer
from specify_cli.cli.console import console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from specify_cli.coordination.surface_resolver import (
    CoordinationBranchDeleted,
    WorktreeRegistryUnavailable,
)
from specify_cli.release.payload import ReleasePrepPayload, build_release_prep_payload
from specify_cli.release.version import ReleaseChannel
from specify_cli.status import StoreError

app = typer.Typer(
    name="release",
    help="Release packaging commands for AI agents",
    no_args_is_help=True,
)


def _render_text(payload: ReleasePrepPayload) -> None:
    """Render a human-readable release prep summary to the console."""
    # Version bump table
    version_table = Table(show_header=False, box=None, padding=(0, 2))
    version_table.add_column("Label", style="bold")
    version_table.add_column("Value")
    version_table.add_row("Channel", payload.channel)
    version_table.add_row("Current version", payload.current_version)
    version_table.add_row(
        "Proposed version",
        Text(payload.proposed_version, style="green bold"),
    )
    version_table.add_row("Target branch", payload.target_branch)
    version_table.add_row("Tag name", payload.structured_inputs.get("tag_name", ""))
    console.print(Panel(version_table, title="Version Bump", expand=False))

    # Changelog block
    if payload.changelog_block.strip():
        console.print(
            Panel(
                payload.changelog_block.rstrip(),
                title="Draft Changelog Block",
                expand=False,
            )
        )
    else:
        console.print("[yellow]No accepted missions found for changelog block.[/yellow]")

    # Structured inputs table
    inputs_table = Table(show_header=True, box=None, padding=(0, 2))
    inputs_table.add_column("Input", style="bold")
    inputs_table.add_column("Value")
    for key, value in payload.structured_inputs.items():
        if key == "release_notes_body":
            # Abbreviate long content
            preview = (value[:60] + "...") if len(value) > 60 else value
            inputs_table.add_row(key, preview)
        else:
            inputs_table.add_row(key, value)
    console.print(Panel(inputs_table, title="Structured Inputs", expand=False))

    # Scope-cut notice (FR-023)
    notice = (
        "[bold]Still-manual steps[/bold] (not automated by this command):\n"
        '  1. PR creation:  [cyan]gh pr create --title "Release {v}" '
        '--body "<changelog_block>"[/cyan]\n'
        '  2. Tag push:     [cyan]git tag -a {v} -m "Release {v}" && '
        "git push origin {v}[/cyan]\n"
        "  3. Monitoring:   [cyan]gh run watch[/cyan]\n"
        "\n"
        "If you need these steps automated, please file a follow-up issue."
    ).format(v=payload.structured_inputs.get("tag_name", "vX.Y.Z"))
    console.print(Panel(notice, title="Next Steps (Manual)", expand=False))


@app.command("prep")
def prep(
    channel: ReleaseChannel = typer.Option(..., "--channel", help="Release channel: alpha | beta | stable"),
    repo_root: Path = typer.Option(Path("."), "--repo", help="Repository root (default: current directory)"),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON instead of human-readable text"),
) -> None:
    """Prepare release artifacts (changelog draft, version bump, structured inputs).

    Reads kitty-specs/ artifacts and local git tags. No network calls.
    """
    try:
        payload = build_release_prep_payload(
            channel=channel,
            repo_root=repo_root.resolve(),
        )
    except (StoreError, CoordinationBranchDeleted, WorktreeRegistryUnavailable) as exc:
        # A corrupt status log, a deleted coordination branch, or an
        # unconsultable worktree registry must fail release prep loudly but
        # cleanly — like every other status reader (see agent/status.py) —
        # not as a raw traceback (#6612).
        if json_output:
            console.print_json(_json.dumps({"error": str(exc)}))
        else:
            console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(1) from None
    if json_output:
        console.print_json(_json.dumps(asdict(payload)))
    else:
        _render_text(payload)
