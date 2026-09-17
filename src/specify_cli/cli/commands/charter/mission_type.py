"""``spec-kitty charter mission-type`` command group (FR-016).

Exposes activated mission types for the current project via:

* ``spec-kitty charter mission-type list [--json]``
  Lists all mission types that are activated in this project (charter-filtered).

  Unlike ``spec-kitty doctrine mission-type list`` (WP13 / FR-013), this
  command returns only types that are explicitly activated for the project.

Implementation notes
--------------------
The ``charter`` API is the entry point for activation state
(``charter.existing_mission_types``, ``charter.resolve_mission_type_context``).
Display metadata (``display_name``) is loaded from
``MissionTypeRepository`` via a lazy import through the ``charter.missions``
facade; runtime ``specify_cli`` modules reach doctrine artifacts only through
such charter doors (layer direction: kernel <- doctrine <- charter <- specify_cli).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, cast

import typer
from specify_cli.cli.console import console
from rich.table import Table

from charter.activation.pack_context import CharterPackConfigError
from specify_cli.cli.json_contract import json_error, json_output_guard

from charter.activation.mission_type_profiles import (
    UnknownMissionTypeError,
    existing_mission_types,
    resolve_mission_type_context,
)

if TYPE_CHECKING:
    from charter.activation.pack_context import PackContext
    from charter.offering.missions.models import MissionType

__all__ = [
    "charter_mission_type_app",
    "charter_mission_type_list",
    "mission_type_error_boundary",
    "resolve_layered_roster",
    "resolve_mission_type_source_layer",
]

charter_mission_type_app = typer.Typer(
    name="mission-type",
    help="Mission type commands (activated types only).",
    no_args_is_help=True,
)


def _layered_lookup_inputs(repo_root: Path) -> tuple[tuple[Path, ...], PackContext]:
    """Build the ``(mission_types_dirs, pack_context)`` pair the layered lookup needs.

    Single seam reused by every CLI surface this mission's WP07 fixes
    (FR-006 below; FR-007/FR-008, imported from here by
    ``specify_cli.cli.commands.mission_type`` / ``...doctrine``) — avoids each
    command re-deriving the same ``(dirs, pack_context)`` construction
    independently. Lazy imports mirror this module's existing
    ``charter.missions`` import convention (CLI startup cost, not the
    import-time-IO NFR-004 constrains — that gate scopes ``charter.*``
    modules, not ``specify_cli.cli.commands.*`` ones).
    """
    from charter.missions import MissionTemplateRepository  # noqa: PLC0415
    from charter.activation.pack_context import PackContext  # noqa: PLC0415

    pack_context = PackContext.from_config(repo_root)
    mission_types_dirs = (MissionTemplateRepository.default_missions_root() / "mission_types",)
    return mission_types_dirs, pack_context


def resolve_layered_roster(repo_root: Path) -> dict[str, MissionType]:
    """Return the full layered mission-type roster: built-in -> org -> project.

    FR-006/FR-007/FR-008 (mission ``up-mission-type-seam-01KZY1JB`` WP07): the
    one seam every CLI surface this mission fixes reaches for a real,
    non-"unknown" resolution — reused instead of querying the built-in-only
    ``MissionTypeRepository.default()``.
    """
    from charter.missions import resolve_layered_mission_types  # noqa: PLC0415

    mission_types_dirs, pack_context = _layered_lookup_inputs(repo_root)
    # See the matching comment on ``activate.py``'s own ``_source_urn``: the
    # ``charter.*`` mypy import-skip override (``follow_imports = "skip"``,
    # pyproject.toml) erases ``resolve_layered_mission_types``'s real return
    # type at this call site; the cast restates the real signature.
    return cast(
        "dict[str, MissionType]",
        resolve_layered_mission_types(mission_types_dirs, pack_context),
    )


def resolve_mission_type_source_layer(mission_type_id: str, repo_root: Path) -> str:
    """Return the real resolution layer (``"built-in"``/``"org"``/``"project"``).

    FR-006/FR-007: reuses ``charter.activation.mission_type_profiles``'s own
    ``resolve_action_sequence_layer`` — the identical precedence walk
    (project > org, earliest ``pack_root`` wins > built-in) that
    :func:`resolve_layered_roster`'s underlying factory itself implements —
    rather than re-deriving a second copy of that walk here.
    """
    from charter.activation.mission_type_profiles import resolve_action_sequence_layer  # noqa: PLC0415

    mission_types_dirs, pack_context = _layered_lookup_inputs(repo_root)
    return cast(
        str,
        resolve_action_sequence_layer(
            mission_type_id, mission_types_dirs=mission_types_dirs, pack_context=pack_context
        ),
    )


#: CR-02 (mission ``charter-code-topology-01M152G1`` S4): the placeholder
#: rendered in the ACTION SEQUENCE column for an ``--include-inactive`` row
#: that is not activated. Such a type is *deliberately* not resolved through
#: :func:`~charter.activation.mission_type_profiles.resolve_mission_type_context` --
#: that resolver hard-fails on a non-activated built-in type by design (the
#: FR-006 activation-subset gate), so this command must not call it for
#: exactly the rows ``--include-inactive`` adds.
_NOT_ACTIVATED_ACTION_SEQUENCE = "(not activated)"


@contextmanager
def mission_type_error_boundary(json_output: bool) -> Iterator[None]:
    """Translate required mission-type content failures at the command boundary."""
    try:
        with json_output_guard(json_output):
            yield
    except (CharterPackConfigError, ValueError, OSError) as exc:
        message = exc.body if isinstance(exc, CharterPackConfigError) else str(exc)
        if json_output:
            code = "invalid_mission_type"
            if isinstance(exc, CharterPackConfigError):
                code = "CHARTER_PACK_CONFIG_INVALID"
            elif isinstance(exc, UnknownMissionTypeError):
                code = "unknown_mission_type"
            console.emit_json(json_error(code, message))
        else:
            console.print(f"[red]Error:[/red] {message}")
        raise typer.Exit(1) from exc


def _mission_type_rows(repo_root: Path, activated_ids: list[str], roster: dict[str, MissionType], include_inactive: bool) -> list[dict[str, object]]:
    """Build display rows without coupling successful data to its renderer."""
    activated_id_set = set(activated_ids)
    # Preserves the pre-CR-02 row order (activated ids, in their own order)
    # and appends any inactive ids -- sorted for determinism, since the
    # roster dict has no declared order guarantee of its own -- only when
    # `--include-inactive` was passed.
    ordered_ids = list(activated_ids)
    if include_inactive:
        ordered_ids.extend(sorted(set(roster) - activated_id_set))

    rows: list[dict[str, object]] = []
    for mt_id in ordered_ids:
        mt = roster.get(mt_id)
        if mt is None:
            # Activated but unresolvable in any layer -- WP05's own
            # activation scan already validates resolvability before
            # activating, so this is a defensive backstop for a genuine
            # configuration inconsistency, not an expected steady-state
            # path. Report the failure plainly rather than a placeholder
            # "unknown" layer treated as a successful row (CL-006/NFR-002).
            err = UnknownMissionTypeError(mt_id, registered_ids=activated_ids)
            raise err

        is_activated = mt_id in activated_id_set
        if is_activated:
            action_seq: list[str] | str = list(resolve_mission_type_context(repo_root, mission_type=mt_id).action_sequence)
        else:
            action_seq = _NOT_ACTIVATED_ACTION_SEQUENCE

        rows.append(
            {
                "id": mt_id,
                "source_layer": resolve_mission_type_source_layer(mt_id, repo_root),
                "display_name": mt.display_name,
                "action_sequence": action_seq,
                "activated": is_activated,
            }
        )

    return rows


@charter_mission_type_app.command("list")
def charter_mission_type_list(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON.",
    ),
    include_inactive: bool = typer.Option(
        False,
        "--include-inactive",
        help=(
            "Also list mission types registered in the built-in/org/project "
            "layers but NOT activated for this project (activation-blind). "
            "The canonical replacement for `spec-kitty doctrine mission-type "
            "list` (CR-02, mission charter-code-topology-01M152G1 S4)."
        ),
    ),
) -> None:
    """List mission types for the current project (FR-016).

    By default, returns only mission types that are explicitly activated in
    this project's charter. Pass ``--include-inactive`` to also see every
    type registered in the built-in/org/project layers regardless of
    activation state -- the deprecated ``spec-kitty doctrine mission-type
    list`` group covered this before CR-02; this flag is its canonical
    replacement, not a straight alias (activation state still distinguishes
    the two row classes -- see ACTION SEQUENCE below).

    Output columns (table): ID, SOURCE, DISPLAY NAME, ACTION SEQUENCE. A
    non-activated ``--include-inactive`` row shows ``(not activated)`` in
    ACTION SEQUENCE: resolving a real action sequence requires activation
    (the FR-006 gate), so there is nothing to compute for it.
    """
    repo_root = Path.cwd()
    with mission_type_error_boundary(json_output):
        activated_ids = existing_mission_types(repo_root)
        roster = resolve_layered_roster(repo_root)
        rows = _mission_type_rows(repo_root, activated_ids, roster, include_inactive)

    if json_output:
        console.print_json(json.dumps(rows))
        raise typer.Exit(0)

    if not rows:
        console.print("[yellow]No activated mission types found for this project.[/yellow]")
        raise typer.Exit(0)

    table = Table(show_header=True, header_style="bold")
    table.add_column("ID", style="cyan")
    table.add_column("SOURCE", style="green")
    table.add_column("DISPLAY NAME")
    table.add_column("ACTION SEQUENCE")

    for row in rows:
        seq = row["action_sequence"]
        seq_str = ", ".join(seq) if isinstance(seq, list) else str(seq)
        table.add_row(
            str(row["id"]),
            str(row["source_layer"]),
            str(row["display_name"]),
            seq_str,
        )

    console.print(table)
    raise typer.Exit(0)
