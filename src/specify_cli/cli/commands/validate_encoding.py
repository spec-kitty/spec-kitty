"""Encoding validation command for Spec Kitty CLI."""

from __future__ import annotations

from specify_cli.core.constants import KITTY_SPECS_DIR
from pathlib import Path
from typing import Annotated

import typer
from rich.panel import Panel
from rich.table import Table

from mission_runtime import MissionArtifactKind, placement_seam

from specify_cli.cli.console import console
from specify_cli.cli.helpers import get_project_root_or_exit
from specify_cli.task_utils import TaskCliError, find_repo_root
from specify_cli.text_sanitization import detect_problematic_characters, sanitize_directory


def validate_encoding(
    mission: Annotated[str | None, typer.Option("--mission", help="Mission slug to validate")] = None,
    fix: Annotated[bool, typer.Option("--fix", help="Automatically fix encoding errors by sanitizing files")] = False,
    check_all: Annotated[bool, typer.Option("--all", help="Check all features, not just one")] = False,
    backup: Annotated[bool, typer.Option("--backup/--no-backup", help="Create .bak files before fixing")] = True,
) -> None:
    """Validate and optionally fix file encoding in feature artifacts.

    Scans markdown files for Windows-1252 smart quotes and other problematic
    characters that cause UTF-8 encoding errors. Can automatically fix issues
    by replacing problematic characters with safe alternatives.
    """
    try:
        repo_root = find_repo_root()
    except TaskCliError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc

    project_root = get_project_root_or_exit(repo_root)

    if check_all:
        # Validate all features
        mission_specs = repo_root / KITTY_SPECS_DIR
        if not mission_specs.exists():
            console.print("[yellow]No kitty-specs directory found.[/yellow]")
            raise typer.Exit(0)

        feature_dirs = [d for d in mission_specs.iterdir() if d.is_dir()]
        if not feature_dirs:
            console.print("[yellow]No mission directories found.[/yellow]")
            raise typer.Exit(0)

        console.print(f"[cyan]Checking encoding for {len(feature_dirs)} missions...[/cyan]")
        console.print()

        total_issues = 0
        total_fixed = 0

        for feature_dir in sorted(feature_dirs):
            issues, fixed = _validate_feature_dir(feature_dir, fix=fix, backup=backup)
            total_issues += issues
            total_fixed += fixed

        console.print()
        console.print(
            Panel(
                f"[bold]Summary:[/bold]\n"
                f"Total files with issues: [yellow]{total_issues}[/yellow]\n"
                f"Total files fixed: [green]{total_fixed}[/green]",
                title="Encoding Validation Complete",
                border_style="cyan" if total_issues == 0 else "yellow",
            )
        )

        raise typer.Exit(0 if total_issues == 0 or fix else 1)

    # Validate single feature
    if not mission or not mission.strip():
        console.print("[red]Error:[/red] --mission <slug> is required (or use --all)")
        raise typer.Exit(1)
    mission_slug = mission.strip()
    # WP09/FR-001 (kind-correct): scans ``**/*.md`` recursively — the bulk of
    # authored markdown (spec/plan/tasks/research/data-model) is PRIMARY-
    # partition content. Route through the seam on ``PRIMARY_METADATA`` so
    # this lands on the authored primary docs rather than the coordination
    # husk (NFR-001 — "do not pin the old coord husk").
    feature_dir = placement_seam(repo_root, mission_slug).read_dir(
        MissionArtifactKind.PRIMARY_METADATA
    )

    if not feature_dir.exists():
        console.print(f"[red]Error:[/red] Mission directory not found: {feature_dir}")
        raise typer.Exit(1)

    console.print(f"[cyan]Validating encoding for mission:[/cyan] {mission_slug}")
    console.print()

    issues, fixed = _validate_feature_dir(feature_dir, fix=fix, backup=backup)

    if issues == 0:
        console.print("[green]✓ All files are properly UTF-8 encoded![/green]")
        raise typer.Exit(0)
    elif fix and fixed > 0:
        console.print()
        console.print(f"[green]✓ Fixed {fixed} file(s) with encoding issues.[/green]")
        if backup:
            console.print("[dim]Backup files (.bak) were created.[/dim]")
        raise typer.Exit(0)
    else:
        console.print()
        console.print(f"[yellow]Found {issues} file(s) with encoding issues.[/yellow]")
        console.print("[dim]Run with --fix to automatically repair these files.[/dim]")
        raise typer.Exit(1)


def _validate_feature_dir(feature_dir: Path, *, fix: bool, backup: bool) -> tuple[int, int]:  # noqa: C901
    """Validate encoding for a single feature directory.

    Returns:
        Tuple of (issues_found, files_fixed)
    """
    console.print(f"[cyan]Checking:[/cyan] {feature_dir.name}")

    # Scan all markdown files
    results = sanitize_directory(feature_dir, pattern="**/*.md", backup=backup, dry_run=not fix)

    files_with_issues = []
    files_fixed = []
    file_errors = []

    for file_path_str, (was_modified, error) in results.items():
        file_path = Path(file_path_str)
        relative_path = file_path.relative_to(feature_dir) if file_path.is_relative_to(feature_dir) else file_path

        if error:
            file_errors.append((relative_path, error))
        elif was_modified:
            files_with_issues.append(relative_path)
            if fix:
                files_fixed.append(relative_path)

    # Display results
    if files_with_issues:
        table = Table(title=f"Files with Encoding Issues: {feature_dir.name}", show_header=True)
        table.add_column("File", style="cyan")
        table.add_column("Status", style="yellow")

        for file_path in files_with_issues:
            status = "[green]Fixed[/green]" if fix else "[yellow]Needs Fix[/yellow]"
            table.add_row(str(file_path), status)

        console.print(table)

        # Show detailed character issues for first file
        if files_with_issues and not fix:
            first_file = feature_dir / files_with_issues[0]
            try:
                # Read with fallback encoding
                try:
                    content = first_file.read_text(encoding="utf-8-sig")
                except UnicodeDecodeError:
                    content_bytes = first_file.read_bytes()
                    for encoding in ("cp1252", "latin-1"):
                        try:
                            content = content_bytes.decode(encoding)
                            break
                        except UnicodeDecodeError:
                            continue
                    else:
                        content = content_bytes.decode("utf-8", errors="replace")

                issues = detect_problematic_characters(content)
                if issues:
                    console.print()
                    console.print(f"[yellow]Example issues in {files_with_issues[0]}:[/yellow]")
                    for line_num, col, char, replacement in issues[:5]:  # Show first 5
                        console.print(f"  Line {line_num}, col {col}: '{char}' (U+{ord(char):04X}) → '{replacement}'")
                    if len(issues) > 5:
                        console.print(f"  ... and {len(issues) - 5} more")
            except Exception:  # noqa: S110
                pass

    if file_errors:
        console.print()
        console.print("[red]Errors encountered:[/red]")
        for file_path, error in file_errors:
            console.print(f"  [red]✗[/red] {file_path}: {error}")

    return len(files_with_issues), len(files_fixed)


__all__ = ["validate_encoding"]
