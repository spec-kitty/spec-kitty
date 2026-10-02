"""``tracer-append`` command (FR-006 / contracts/commands.md).

A lane-origin-safe CLI wrapper over
:func:`specify_cli.retrospective.tracer_writer.append_tracer_finding`: appends
a dated, attributed finding to ``traces/<category>.md``, routed to the COORD
surface via the WP03 seam. Resolves ``repo_root`` to the MAIN repo root
(``get_main_repo_root``) exactly like ``record-analysis`` does, so invoking
this command from inside a lane worktree never touches the lane's own
``kitty-specs/`` checkout -- the write always targets the primary checkout,
which the seam then stages onto the coordination branch (#2980 / #2549).
"""

from __future__ import annotations

from typing import Annotated

import typer

from rich.markup import escape

from specify_cli.agent_tasks_ports import RealRender
from specify_cli.cli.console import console
from specify_cli.core.paths import (
    get_feature_target_branch,
    get_main_repo_root,
    locate_project_root,
)
from specify_cli.coordination.commit_outcome import (
    commit_outcome_exit_code,
    commit_outcome_payload,
    render_commit_outcome,
)
from specify_cli.coordination.surface_resolver import CoordinationWorktreeUnmaterialized
from specify_cli.coordination.write_seam import WriteSeamResult
from specify_cli.git.protection_policy import ProtectionPolicy
from specify_cli.retrospective.tracer_writer import (
    TRACER_CATEGORIES,
    TracerAttributionError,
    TracerCategoryError,
    append_tracer_finding,
)

__all__ = ["tracer_append"]

_KIND_LABEL = "TRACER_FILE"
_DESTINATION_SURFACE = "coord"  # TRACER_FILE is unconditionally COORD-partition.
_REFUSAL_DEFERRED_TO = "#3033"
_PROJECT_ROOT_NOT_FOUND = "Could not locate project root"
_CATEGORY_HELP = "Tracer category: " + " | ".join(sorted(TRACER_CATEGORIES))


def _emit(payload: dict[str, object], *, json_output: bool, ok: bool) -> None:
    if json_output:
        # Routed through the sanctioned RealRender.json_envelope adapter — the
        # ONE blessed json.dumps home in the agent command surface (FR-007 /
        # test_no_inline_json_dumps_outside_allowlist); never an inline
        # json.dumps here (tasks-py-degod-wave2-01KWH9EQ
        # contracts/gate-contracts.md Gate 1).
        print(RealRender().json_envelope(payload))
        return
    if ok:
        # WP10 cycle 2 (B1 sibling): ``row_or_entry_ref``/``error`` are
        # computed from caller-controlled diagnostics (git error text, path
        # segments, ...) and interpolated into a Rich-styled f-string --
        # ``escape()`` neutralises any bracketed substring that would
        # otherwise be parsed as a (potentially unbalanced) markup tag.
        console.print(f"[green]✓[/green] {escape(str(payload.get('row_or_entry_ref', '')))}")
    else:
        console.print(f"[red]Error:[/red] {escape(str(payload.get('error', 'tracer-append failed')))}")


def _error_payload(message: str) -> dict[str, object]:
    return {"ok": False, "kind": _KIND_LABEL, "error": message}


def _emit_with_surfaces(
    result: WriteSeamResult,
    payload: dict[str, object],
    *,
    json_output: bool,
    ok: bool,
) -> None:
    """Render every surface (rule 6) on EVERY arm, text or JSON (WP10 cycle 2, B1/B2).

    ``markup=False`` (B1): a surface diagnostic can legitimately contain a
    bracketed substring (e.g. a path segment or a ``[/red]``-shaped token
    inside someone's commit message) -- without it, Rich's markup parser
    raises ``rich.errors.MarkupError`` mid-refusal, crashing the very error
    report it was rendering.
    """
    if not json_output:
        for line in render_commit_outcome(result):
            console.print(line, markup=False)
    _emit(payload, json_output=json_output, ok=ok)


def tracer_append(
    mission: Annotated[str, typer.Option("--mission", help="Mission handle (e.g. 'my-mission-01ABCDEF')")],
    category: Annotated[str, typer.Option("--category", help=_CATEGORY_HELP)],
    entry: Annotated[str, typer.Option("--entry", help="Finding text")],
    actor: Annotated[str, typer.Option("--actor", help="Attribution (required, non-empty)")],
    json_output: Annotated[bool, typer.Option("--json", help="Output JSON format")] = False,
) -> None:
    """Append a dated, attributed finding to the mission's tracer surface."""
    cwd_repo_root = locate_project_root()
    if cwd_repo_root is None:
        _emit(_error_payload(_PROJECT_ROOT_NOT_FOUND), json_output=json_output, ok=False)
        raise typer.Exit(1)
    repo_root = get_main_repo_root(cwd_repo_root)

    try:
        policy = ProtectionPolicy.resolve(repo_root)
        try:
            target_branch = get_feature_target_branch(repo_root, mission)
        except Exception:  # noqa: BLE001 - best-effort ff-advance target only
            target_branch = None

        result = append_tracer_finding(
            repo_root=repo_root,
            mission_slug=mission,
            category=category,
            entry=entry,
            actor=actor,
            policy=policy,
            target_branch=target_branch,
        )
    except CoordinationWorktreeUnmaterialized as exc:
        # coord-read-fail-closed-01M38VVH WP04 out-of-map wrap (mid-mission
        # coordinator referral from WP02's review): WP02 narrows the tracer
        # read's absorption so a coord-topology read on an UNMATERIALIZED
        # coordination worktree now PROPAGATES out of
        # ``append_tracer_finding`` instead of degrading to "" — this CLI
        # boundary previously caught only ``TracerAttributionError``/
        # ``TracerCategoryError``, so the new sibling would have surfaced as a
        # raw traceback here. Minimal message-wrap only: present the same
        # structured ``{"ok": false, ...}`` refusal shape the other error
        # branches below use, carrying the sibling's operator-facing
        # ``next_step`` verbatim rather than swallowing it into success.
        payload = {
            "ok": False,
            "kind": _KIND_LABEL,
            "error": str(exc),
            "next_step": exc.next_step,
        }
        _emit(payload, json_output=json_output, ok=False)
        raise typer.Exit(1) from None
    except (TracerAttributionError, TracerCategoryError) as exc:
        _emit(_error_payload(str(exc)), json_output=json_output, ok=False)
        raise typer.Exit(1) from None
    except UnicodeDecodeError as exc:
        # coord-read-fail-closed-01M38VVH WP02/#4959 (pre-PR squad fold): the
        # writer's own read-before-write (``tracer_writer._read_current_coord_
        # content``) now PROPAGATES ``UnicodeDecodeError`` when an EXISTING
        # ``traces/<category>.md`` file is not valid UTF-8, rather than
        # degrading to "" and letting the merge clobber it with a
        # from-scratch header. That refusal previously had no catcher here,
        # so it surfaced as a raw traceback instead of the same structured
        # ``{"ok": false, ...}`` refusal shape every other fail-closed branch
        # above uses.
        payload = {
            "ok": False,
            "kind": _KIND_LABEL,
            "error": f"the traces file is not valid UTF-8; refusing to overwrite: {exc}",
            "next_step": "inspect and repair the corrupt traces file on the coordination surface before retrying",
        }
        _emit(payload, json_output=json_output, ok=False)
        raise typer.Exit(1) from None

    if result.status == "refused":
        payload = {
            "ok": False,
            "kind": _KIND_LABEL,
            "error": result.diagnostic or "tracer-append refused an unroutable write target",
            "refusal": {
                "reason": result.diagnostic,
                "deferred_to": _REFUSAL_DEFERRED_TO,
            },
            **commit_outcome_payload(result),
        }
        _emit_with_surfaces(result, payload, json_output=json_output, ok=False)
        raise typer.Exit(1)

    if result.status == "error":
        payload = {
            **_error_payload(result.diagnostic or "tracer-append commit failed"),
            **commit_outcome_payload(result),
        }
        _emit_with_surfaces(result, payload, json_output=json_output, ok=False)
        raise typer.Exit(1)

    # WP10 (T055 step 4, contracts/commit-outcome.md rule 5/6): the shared
    # exit-code rule additionally flags a MIXED outcome (e.g. the PRIMARY
    # group committed while the coordination group was refused) even though
    # the legacy top-level ``result.status`` alone would read "committed".
    # The surfaces list, when non-empty, is always rendered too (rule 6 --
    # no consumer formats surface outcomes by hand).
    surfaces_exit_code = commit_outcome_exit_code(result)
    payload = {
        "ok": surfaces_exit_code == 0,
        "kind": _KIND_LABEL,
        "destination_surface": _DESTINATION_SURFACE,
        "row_or_entry_ref": result.entry_id,
        "status": result.status,
        "commit_ref": result.destination_surface,
        "commit_hash": result.commit_hash,
        **commit_outcome_payload(result),
    }
    _emit_with_surfaces(result, payload, json_output=json_output, ok=surfaces_exit_code == 0)
    if surfaces_exit_code != 0:
        raise typer.Exit(1)
