"""``spec-kitty archive`` — operator-invoked mission archiving (FR-015 / US6).

Two verbs:

* ``archive create <mission> --by <operator> --reason <why>`` — archive a
  *terminal* mission, enforcing the AM-1..AM-5 guards. Refuses (non-zero exit)
  a non-terminal mission (AM-1) or one carrying a ``still_present`` invariant
  (AM-2). Success appends an immutable :class:`ArchivedMission` record.
* ``archive list`` — enumerate archived missions (AM-3 — visible, not deleted).

This is the ONLY entry point to :func:`archive_mission`. No lifecycle step or
migration calls it (AM-4): archiving is operator-invoked only.
"""

from __future__ import annotations

import json
from typing import Annotated

import typer

from specify_cli.cli.console import console
from specify_cli.cli.json_contract import json_error
from specify_cli.core.paths import locate_project_root
from specify_cli.missions._archive import (
    MissionArchiveRefused,
    archive_mission,
    list_archived_missions,
)
from specify_cli.missions._read_path_resolver import MissionSelectorAmbiguous, candidate_feature_dir_for_mission

app = typer.Typer(
    name="archive",
    help="Archive a terminal mission as an immutable, enumerable snapshot.",
    no_args_is_help=True,
)

_EXIT_OK = 0
_EXIT_REFUSED = 1
_EXIT_ERROR = 2


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
    root = locate_project_root()
    if root is None:
        if json_output:
            console.emit_json(json_error("not_in_project", "Not in a spec-kitty project (no project root resolved)."))
        else:
            console.print("[red]Not in a spec-kitty project (no project root resolved).[/red]")
        raise typer.Exit(_EXIT_ERROR)

    try:
        feature_dir = candidate_feature_dir_for_mission(root, mission)
    except MissionSelectorAmbiguous as exc:
        if json_output:
            console.emit_json({**json_error(exc.error_code, str(exc)), "handle": exc.handle, "candidates": exc.candidates})
        else:
            console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
    if not feature_dir.exists():
        if json_output:
            console.emit_json(json_error("mission_not_found", f"Mission not found: {mission}"))
        else:
            console.print(f"[red]Mission not found: {mission}[/red]")
        raise typer.Exit(_EXIT_ERROR)

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


@app.command("list")
def list_archives(
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit the archive registry as JSON.")
    ] = False,
) -> None:
    """Enumerate archived missions (AM-3)."""
    root = locate_project_root()
    if root is None:
        if json_output:
            console.emit_json(json_error("not_in_project", "Not in a spec-kitty project (no project root resolved)."))
        else:
            console.print("[red]Not in a spec-kitty project (no project root resolved).[/red]")
        raise typer.Exit(_EXIT_ERROR)

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


__all__ = ["app", "create", "list_archives"]
