"""Materialize command — regenerate all derived views from the event log.

Derived views (status.json, board-summary.json, progress.json, lifecycle.json)
are output-only artefacts stored under ``.kittify/derived/<mission_slug>/``.
This command forces full regeneration for one or all features, which is
useful for CI pipelines, debugging, and external SaaS consumers.
"""

from __future__ import annotations

from specify_cli.core.constants import KITTY_SPECS_DIR
import json
from pathlib import Path
from typing import Annotated, Any

import typer
from specify_cli.cli.console import console
from specify_cli.cli.json_contract import json_error

from specify_cli.core.paths import locate_project_root
from specify_cli.missions._read_path_resolver import MissionSelectorAmbiguous
from kernel.clock import now_utc_iso



def _resolve_selected_dir(repo_root: Path, mission_slug: str, json_output: bool) -> Path:
    """Resolve the status partition, rendering expected selector ambiguity."""
    from mission_runtime import MissionArtifactKind, placement_seam

    try:
        return placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.STATUS_STATE)
    except MissionSelectorAmbiguous as exc:
        if json_output:
            console.emit_json({**json_error(exc.error_code, str(exc)), "handle": exc.handle, "candidates": exc.candidates})
        else:
            console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc


def materialize(
    mission: Annotated[
        str | None,
        typer.Option("--mission", help="Mission slug to materialise (all if omitted)"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output a machine-readable JSON summary"),
    ] = False,
) -> None:
    """Regenerate all derived views from the canonical event log.

    For each feature (or a single feature when --mission is given),
    writes the following files to ``.kittify/derived/<slug>/``:

    - ``status.json`` — full StatusSnapshot
    - ``board-summary.json`` — lane counts and WP lists
    - ``progress.json`` — lane-weighted progress percentage
    - ``lifecycle.json`` — canonical active/recent/stale/abandoned mission state

    Examples::

        spec-kitty materialize
        spec-kitty materialize --mission 034-my-feature
        spec-kitty materialize --json
    """
    from specify_cli.status import write_derived_views
    from specify_cli.status import generate_lifecycle_json
    from specify_cli.status import generate_progress_json

    repo_root = locate_project_root()
    if repo_root is None:
        if json_output:
            console.emit_json(json_error("not_in_project", "Not in a spec-kitty project"))
        else:
            console.print("[red]Error:[/red] Not in a spec-kitty project")
        raise typer.Exit(1)

    specs_dir = repo_root / KITTY_SPECS_DIR
    derived_dir = repo_root / ".kittify" / "derived"
    derived_dir.mkdir(parents=True, exist_ok=True)

    # Resolve feature directories to process. Normalize whitespace to preserve
    # the prior resolve_selector() behavior (` 034-foo ` must resolve the same as
    # `034-foo`); whitespace-only/empty means "all missions".
    mission_slug = mission.strip() if mission else mission

    if mission_slug:
        # WP09/FR-001 (kind-correct): ``write_derived_views`` /
        # ``generate_progress_json`` / ``generate_lifecycle_json`` all read the
        # append-only ``status.events.jsonl`` log via ``materialize()`` — the
        # STATUS-namespace surface. Route through the seam on ``STATUS_STATE``
        # (coord-aware) rather than the kind-blind slug resolver (NFR-001).
        feature_dirs = [_resolve_selected_dir(repo_root, mission_slug, json_output)]
        if not feature_dirs[0].exists():
            if json_output:
                console.emit_json(json_error("mission_not_found", f"Mission not found: {mission_slug}"))
            else:
                console.print(f"[red]Error:[/red] Mission not found: {mission_slug}")
            raise typer.Exit(1)
    else:
        if not specs_dir.exists():
            feature_dirs = []
        else:
            feature_dirs = sorted(
                p for p in specs_dir.iterdir() if p.is_dir() and not p.name.startswith(".")
            )

    processed: list[dict[str, Any]] = []
    errors: list[str] = []

    for feature_dir in feature_dirs:
        slug = feature_dir.name
        files_written: list[str] = []
        try:
            write_derived_views(feature_dir, derived_dir)
            files_written += ["status.json", "board-summary.json"]
            generate_progress_json(feature_dir, derived_dir)
            files_written.append("progress.json")
            generate_lifecycle_json(feature_dir, derived_dir)
            files_written.append("lifecycle.json")
            processed.append({
                "mission_slug": slug,
                "files_written": files_written,
                "timestamp": now_utc_iso(),
            })
        except Exception as exc:  # noqa: BLE001 — per-mission derived-view failure must not abort the full materialize pass
            errors.append(f"{slug}: {exc}")

    summary = {
        "processed": len(processed),
        "errors": errors,
        "missions": processed,
        "derived_dir": str(derived_dir),
    }

    if json_output:
        if errors:
            console.emit_json({**summary, **json_error("materialize_failed", "; ".join(errors))})
        else:
            console.print_json(json.dumps(summary, indent=2))
    else:
        if not processed:
            console.print("[dim]No features materialised.[/dim]")
        else:
            for entry in processed:
                display_slug = str(entry.get("mission_slug") or entry.get("mission_slug") or "")
                files = ", ".join(entry["files_written"])
                console.print(f"[green]OK[/green] {display_slug} — {files}")
        if errors:
            console.print()
            for err in errors:
                console.print(f"[red]ERR[/red] {err}")
        else:
            console.print(f"\n[dim]{len(processed)} mission(s) materialised to {derived_dir}[/dim]")

    raise typer.Exit(0 if not errors else 1)
