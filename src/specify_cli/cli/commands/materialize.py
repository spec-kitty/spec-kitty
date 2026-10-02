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

from mission_runtime import ActionContextError
from specify_cli.core.paths import locate_project_root
from specify_cli.missions._read_path_resolver import MissionSelectorAmbiguous, StatusReadPathNotFound
from specify_cli.status.locking import FeatureStatusLockTimeoutError
from kernel.clock import now_utc_iso



# Write-location refusals a per-Mission resolution can raise (nothing is mutated):
# a deleted / remote-only coordination branch (``StatusReadPathNotFound``
# subclasses), a seed fork (``CoordSeedForkRefused``, an ``ActionContextError``)
# and a held status lock. Rendered per Mission, never as a traceback.
_RESOLUTION_REFUSALS: tuple[type[Exception], ...] = (
    StatusReadPathNotFound,
    FeatureStatusLockTimeoutError,
    ActionContextError,
)


def _status_dir_for(repo_root: Path, mission_slug: str) -> Path:
    """The Mission dir whose ``status.events.jsonl`` ``materialize`` reduces (ruling Q4, FR-003).

    Resolved through the WRITE accessor, so a coordination-routed Mission is
    reduced from its coordination surface's log. That may ``git worktree add``
    an UNMATERIALIZED coordination surface (once) and seed a pre-fix EMPTY one;
    for ``lanes`` / ``single_branch`` Missions it is byte-identical to the read
    resolver (C-008), with no side effects.
    """
    from mission_runtime import MissionArtifactKind, placement_seam

    return placement_seam(repo_root, mission_slug).write_dir(MissionArtifactKind.STATUS_STATE).path


def _refusal_message(mission_slug: str, exc: Exception) -> str:
    """``"<slug>: <code>: <message>"`` for a per-Mission resolution refusal."""
    code = getattr(exc, "error_code", None) or getattr(exc, "code", None) or type(exc).__name__
    return f"{mission_slug}: {code}: {exc}"


def _resolve_selected_dir(repo_root: Path, mission_slug: str, json_output: bool) -> Path:
    """Resolve the status partition, rendering expected selector ambiguity and write-location refusals."""
    try:
        return _status_dir_for(repo_root, mission_slug)
    except MissionSelectorAmbiguous as exc:
        if json_output:
            console.emit_json({**json_error(exc.error_code, str(exc)), "handle": exc.handle, "candidates": exc.candidates})
        else:
            console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
    except _RESOLUTION_REFUSALS as exc:
        message = _refusal_message(mission_slug, exc)
        if json_output:
            console.emit_json(json_error("materialize_failed", message))
        else:
            console.print(f"[red]Error:[/red] {message}")
        raise typer.Exit(1) from exc


def _mission_dirs_to_process(repo_root: Path, specs_dir: Path, errors: list[str]) -> list[tuple[str, Path]]:
    """``(slug, status_dir)`` for every Mission under *specs_dir*, in slug order.

    The slug is the repository root checkout's dir name (it names
    ``.kittify/derived/<slug>``), never the name of the coordination path. A
    per-Mission refusal (remote-only or deleted coordination branch, seed fork,
    held status lock) becomes an ``errors[]`` entry and the loop continues.
    """
    if not specs_dir.exists():
        return []
    targets: list[tuple[str, Path]] = []
    for root_dir in sorted(p for p in specs_dir.iterdir() if p.is_dir() and not p.name.startswith(".")):
        try:
            targets.append((root_dir.name, _status_dir_for(repo_root, root_dir.name)))
        except _RESOLUTION_REFUSALS as exc:
            errors.append(_refusal_message(root_dir.name, exc))
    return targets


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

    A coordination-routed Mission is reduced from its coordination surface's
    event log. To find that log this command may create the coordination
    worktree (one ``git worktree add`` per coordination-routed Mission, done
    once) and, for a Mission created before the coordination surface was
    seeded, seed it. ``lanes`` and ``single_branch`` Missions are reduced from
    the repository root checkout exactly as before. A Mission whose coordination
    branch exists only on a remote, or whose logs diverged, is reported in the
    error summary and the remaining Missions are still processed.

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

    # Resolve the Missions to process. Normalize whitespace to preserve
    # the prior resolve_selector() behavior (` 034-foo ` must resolve the same as
    # `034-foo`); whitespace-only/empty means "all missions".
    mission_slug = mission.strip() if mission else mission
    errors: list[str] = []

    if mission_slug:
        # WP09/FR-001 (kind-correct): ``write_derived_views`` /
        # ``generate_progress_json`` / ``generate_lifecycle_json`` all read the
        # append-only ``status.events.jsonl`` log via ``materialize()`` — the
        # STATUS-namespace surface. Route through the seam on ``STATUS_STATE``
        # (coordination-aware, WRITE accessor) rather than the kind-blind slug
        # resolver (NFR-001).
        selected_dir = _resolve_selected_dir(repo_root, mission_slug, json_output)
        if not selected_dir.exists():
            if json_output:
                console.emit_json(json_error("mission_not_found", f"Mission not found: {mission_slug}"))
            else:
                console.print(f"[red]Error:[/red] Mission not found: {mission_slug}")
            raise typer.Exit(1)
        targets = [(selected_dir.name, selected_dir)]
    else:
        targets = _mission_dirs_to_process(repo_root, specs_dir, errors)

    processed: list[dict[str, Any]] = []

    for slug, feature_dir in targets:
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
