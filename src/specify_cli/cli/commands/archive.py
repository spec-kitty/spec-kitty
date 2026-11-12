"""``spec-kitty archive`` — operator-invoked mission archiving (FR-015 / US6).

Three verbs:

* ``archive create <mission> --by <operator> --reason <why>`` — archive a
  *terminal* mission, enforcing the AM-1..AM-5 guards. Refuses (non-zero exit)
  a non-terminal mission (AM-1) or one carrying a ``still_present`` invariant
  (AM-2). Success appends an immutable :class:`ArchivedMission` record.
* ``archive list`` — enumerate archived missions (AM-3 — visible, not deleted).
* ``archive reclaim <mission>`` — remove the coordination worktree, branch and marker an
  archived Mission still holds once its landing is proved (#4041;
  :mod:`specify_cli.missions.archive_reclaim`).

This is the ONLY entry point to :func:`archive_mission`. No lifecycle step or
migration calls it (AM-4): archiving is operator-invoked only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.markup import escape

from specify_cli.cli.console import console
from specify_cli.cli.json_contract import json_error
from specify_cli.core.paths import locate_project_root
from specify_cli.missions._archive import (
    MissionArchiveRefused,
    archive_mission,
    list_archived_missions,
)
from specify_cli.missions._read_path_resolver import MissionSelectorAmbiguous, candidate_feature_dir_for_mission
from specify_cli.missions.archive_reclaim import ReclaimRefused, ReclaimReport, holds_coordination_marker, reclaim_archived_mission, reclaim_command

app = typer.Typer(
    name="archive",
    help="Archive a terminal mission as an immutable, enumerable snapshot.",
    no_args_is_help=True,
)

_EXIT_OK = 0
_EXIT_REFUSED = 1
_EXIT_ERROR = 2
_NOT_IN_PROJECT = "Not in a spec-kitty project (no project root resolved)."
_JSON_HELP = "Emit the result as JSON."


def _project_root_or_exit(json_output: bool) -> Path:
    root = locate_project_root()
    if root is None:
        if json_output:
            console.emit_json(json_error("not_in_project", _NOT_IN_PROJECT))
        else:
            console.print(f"[red]{_NOT_IN_PROJECT}[/red]")
        raise typer.Exit(_EXIT_ERROR)
    return root


def _feature_dir_or_exit(root: Path, mission: str, json_output: bool) -> Path:
    try:
        feature_dir = candidate_feature_dir_for_mission(root, mission)
    except MissionSelectorAmbiguous as exc:
        if json_output:
            console.emit_json({**json_error(exc.error_code, str(exc)), "handle": exc.handle, "candidates": exc.candidates})
        else:
            console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(_EXIT_REFUSED) from exc
    if not feature_dir.exists():
        if json_output:
            console.emit_json(json_error("mission_not_found", f"Mission not found: {mission}"))
        else:
            console.print(f"[red]Mission not found: {mission}[/red]")
        raise typer.Exit(_EXIT_ERROR)
    resolved: Path = feature_dir
    return resolved


@app.command("create")
def create(
    mission: Annotated[
        str, typer.Argument(help="Mission selector (slug or mission_id).")
    ],
    by: Annotated[
        str,
        typer.Option("--by", help="Operator identity performing the archive (required)."),
    ],
    reason: Annotated[
        str,
        typer.Option("--reason", help="Why the mission is being archived (required)."),
    ],
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit the archive record as JSON.")
    ] = False,
) -> None:
    """Archive a terminal mission (AM-1..AM-5)."""
    root = _project_root_or_exit(json_output)
    feature_dir = _feature_dir_or_exit(root, mission, json_output)

    try:
        outcome = archive_mission(
            project_root=root,
            feature_dir=feature_dir,
            archived_by=by,
            reason=reason,
        )
    except MissionArchiveRefused as refused:
        if json_output:
            console.emit_json(json_error(refused.code, refused.reason))
        else:
            console.print(f"[red]Archive refused ({refused.code}):[/red] {refused.reason}")
        raise typer.Exit(_EXIT_REFUSED) from refused

    record = outcome.record
    if json_output:
        payload = {
            "record": record.to_dict(),
            "cleared_deferrals": [
                {"invariant_id": d.invariant_id, "disposition": d.disposition}
                for d in outcome.cleared_deferrals
            ],
        }
        console.print(json.dumps(payload, indent=2, sort_keys=True))
        return

    console.print(
        f"[green]Archived[/green] {record.mission_id} "
        f"({record.terminal_state_at_archive}) by {record.archived_by}."
    )
    if outcome.cleared_deferrals:
        ids = ", ".join(d.invariant_id for d in outcome.cleared_deferrals)
        console.print(
            f"  Cancellation cleared deferrals to a canceled disposition: {ids}"
        )
    if holds_coordination_marker(root, feature_dir.name):
        console.print(f"Reclaim its coordination worktree and branch with: {reclaim_command(feature_dir.name)}", soft_wrap=True)


@app.command("list")
def list_archives(
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit the archive registry as JSON.")
    ] = False,
) -> None:
    """Enumerate archived missions (AM-3)."""
    root = _project_root_or_exit(json_output)

    records = list_archived_missions(root)
    if json_output:
        console.print(
            json.dumps([r.to_dict() for r in records], indent=2, sort_keys=True)
        )
        return

    if not records:
        console.print("No archived missions.")
        return
    for record in records:
        console.print(
            f"{record.mission_id}  {record.terminal_state_at_archive}  "
            f"{record.archived_at}  by {record.archived_by}  — {record.reason}"
        )


@app.command("reclaim")
def reclaim(
    mission: Annotated[str, typer.Argument(help="Mission selector (slug or mission_id) of an archived Mission.")],
    json_output: Annotated[bool, typer.Option("--json", help=_JSON_HELP)] = False,
) -> None:
    """Remove the coordination worktree, branch and marker an archived Mission still holds.

    The branch is deleted only when the Mission records its landing (merged_at) and the
    coordination tip is the one that landing recorded (or behind it). A second run reports
    that nothing is left.

    Example: spec-kitty archive reclaim my-mission-01ABCDEF
    """
    root = _project_root_or_exit(json_output)
    feature_dir = _feature_dir_or_exit(root, mission, json_output)
    try:
        report = reclaim_archived_mission(root, feature_dir.name)
    except ReclaimRefused as refused:
        if json_output:
            console.emit_json({**json_error(refused.error_code, str(refused)), "remedy": refused.remedy})
        else:
            console.print(f"[red]Reclaim refused:[/red] {escape(str(refused))}\n  {escape(refused.remedy)}\nError code: {refused.error_code}.", soft_wrap=True)
        raise typer.Exit(_EXIT_REFUSED) from refused
    _render_reclaim(report, json_output)


def _render_reclaim(report: ReclaimReport, json_output: bool) -> None:
    if json_output:
        steps = [{"step": step.name, "outcome": step.outcome, "detail": step.detail} for step in report.steps]
        console.emit_json({"ok": True, "mission_slug": report.mission_slug, "nothing_left": report.nothing_left, "steps": steps})
        return
    if report.nothing_left:
        console.print(f"Nothing left to reclaim for {report.mission_slug}.")
        return
    for step in report.steps:
        suffix = f": {step.detail}" if step.detail else ""
        console.print(escape(f"  {step.name.capitalize()}  {step.outcome}{suffix}"), soft_wrap=True)
    console.print(f"[green]Reclaimed[/green] the coordination triple of {report.mission_slug}.")


__all__ = ["app", "create", "list_archives", "reclaim"]
