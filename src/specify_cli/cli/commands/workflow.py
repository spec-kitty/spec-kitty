"""Workflow portability commands."""

from __future__ import annotations

from pathlib import Path

import typer

from kernel.guarded_read import read_guarded
from specify_cli.core.atomic import atomic_write
from runtime.next._internal_runtime.workflow_registry import (
    WorkflowFileError,
    list_available_workflows,
    load_workflow_file,
    resolve_workflow_path,
)

app = typer.Typer(name="workflow", help="Manage mission workflow definitions")


@app.command(name="list")
def list_workflows(
    project_root: Path = typer.Option(
        Path("."),
        "--project-root",
        help="Project root used for .kittify workflow discovery.",
    ),
) -> None:
    """List workflow ids available to a project."""
    for workflow_id in list_available_workflows(project_root=project_root.resolve()):
        typer.echo(workflow_id)


@app.command(name="export")
def export_workflow(
    workflow_id: str = typer.Argument(..., help="Workflow id to export."),
    output: Path = typer.Argument(..., help="Destination file or directory."),
    project_root: Path = typer.Option(
        Path("."),
        "--project-root",
        help="Project root used for .kittify workflow discovery.",
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing destination file."),
) -> None:
    """Export a resolvable workflow YAML file."""
    source = resolve_workflow_path(workflow_id, project_root=project_root.resolve())
    load_workflow_file(source, requested_workflow_id=workflow_id)
    destination = _destination_path(output, workflow_id=workflow_id)
    _copy_workflow(source, destination, force=force)
    typer.echo(str(destination))


@app.command(name="import")
def import_workflow(
    source: Path = typer.Argument(
        ...,
        help="Workflow YAML file to import.",
        # readable=False: an unreadable/missing source is a domain error
        # (FR-003/#4738), not a Typer usage error — Click's own default
        # readable check would otherwise reject it at exit 2 *before*
        # `load_workflow_file` ever runs, bypassing the guarded-read seam
        # (mission cli-error-surface-seam-01M2WJD2, WP02).
        readable=False,
    ),
    project_root: Path = typer.Option(
        Path("."),
        "--project-root",
        help="Project root that receives the workflow override.",
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing workflow file."),
) -> None:
    """Import a workflow YAML into `.kittify/overrides/workflows`."""
    workflow = load_workflow_file(source)
    destination = project_root.resolve() / ".kittify" / "overrides" / "workflows" / f"{workflow.workflow_id}.yaml"
    _copy_workflow(source, destination, force=force)
    typer.echo(str(destination))


def _destination_path(output: Path, *, workflow_id: str) -> Path:
    if output.exists() and output.is_dir():
        return output / f"{workflow_id}.yaml"
    if str(output).endswith(("/", "\\")):
        return output / f"{workflow_id}.yaml"
    return output


def _copy_workflow(source: Path, destination: Path, *, force: bool) -> None:
    if destination.exists() and not force:
        raise typer.BadParameter(f"Destination exists: {destination}")
    # Guarded (not a bare `source.read_bytes()`) even though the caller
    # already validated `source` via `load_workflow_file`: a concurrent
    # delete/permission change between that validation and this copy would
    # otherwise traceback (mission cli-error-surface-seam-01M2WJD2, WP02,
    # binding squad amendment #2 — no unguarded read in this in-scope module).
    content = read_guarded(source, lambda raw: raw, error_cls=WorkflowFileError, mode="bytes")
    atomic_write(destination, content, mkdir=True)
