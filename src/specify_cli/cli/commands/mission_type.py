"""Mission management CLI commands.

The top-level ``spec-kitty mission-type`` group exposes:

* ``mission-type list [--json]``   — alias for ``charter mission-type list``
  (activated types only, charter-filtered).
* ``mission-type show <id> [--json]`` — fully resolved doctrine MissionType
  definition for an activated mission type.

The older commands in this module (``current``, ``info``, ``create``,
``run``, ``close``, ``switch``) remain on the ``spec-kitty mission``
surface; they operate on per-mission metadata, not doctrine mission types.
"""

from __future__ import annotations

import contextlib
import json
import warnings

from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.core.paths import MissionMetaReadError, get_main_repo_root, load_meta_fail_closed
from specify_cli.core.utils import safe_is_dir
from specify_cli.git.remote_probes import RemoteLookup, remote_branch_lookup
from specify_cli.lanes.branch_naming import resolve_mid8
from specify_cli.mission_metadata import load_meta
from specify_cli.missions._read_path_resolver import resolve_feature_dir_for_mission
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

import typer
from mission_runtime import MissionArtifactKind, placement_seam
from rich.panel import Panel
from rich.text import Text

from specify_cli.cli.console import console
from specify_cli.cli.helpers import get_project_root_or_exit
from specify_cli.cli.json_contract import json_error, json_output_guard
from specify_cli.mission import (
    Mission,
    MissionError,
    MissionNotFoundError,
    get_mission_by_name,
    get_mission_for_feature,
    list_available_missions,
)

if TYPE_CHECKING:
    from specify_cli.retrospective.schema import ProvenanceKind

app = typer.Typer(
    name="mission-type",
    help=(
        "Inspect mission types for this project.\n\n"
        "Use 'list' to see activated types (charter-filtered) and "
        "'show <id>' for a full resolved definition.\n\n"
        "Mission types are selected per mission run during /spec-kitty.specify."
    ),
    no_args_is_help=True,
)


def _resolve_primary_repo_root(project_root: Path) -> Path:
    """Return the primary repository root even when invoked from a worktree."""
    resolved = project_root.resolve()
    parts = list(resolved.parts)
    if ".worktrees" not in parts:
        return resolved

    idx = parts.index(".worktrees")
    # Rebuild the path up to (but excluding) ".worktrees"
    base = Path(parts[0])
    for segment in parts[1:idx]:
        base /= segment
    return base


def _mission_details_lines(mission: Mission, include_description: bool = True) -> list[str]:
    """Return formatted mission details."""
    details: list[str] = [
        f"[cyan]Name:[/cyan] {mission.name}",
        f"[cyan]Domain:[/cyan] {mission.domain}",
        f"[cyan]Version:[/cyan] {mission.version}",
        f"[cyan]Path:[/cyan] {mission.path}",
    ]
    if include_description and mission.description:
        details.append(f"[cyan]Description:[/cyan] {mission.description}")
    details.extend(["", "[cyan]Workflow Phases:[/cyan]"])
    for phase in mission.config.workflow.phases:
        details.append(f"  • {phase.name} – {phase.description}")

    details.extend(["", "[cyan]Required Artifacts:[/cyan]"])
    if mission.config.artifacts.required:
        for artifact in mission.config.artifacts.required:
            details.append(f"  • {artifact}")
    else:
        details.append("  • (none)")

    if mission.config.artifacts.optional:
        details.extend(["", "[cyan]Optional Artifacts:[/cyan]"])
        for artifact in mission.config.artifacts.optional:
            details.append(f"  • {artifact}")

    details.extend(["", "[cyan]Validation Checks:[/cyan]"])
    if mission.config.validation.checks:
        for check in mission.config.validation.checks:
            details.append(f"  • {check}")
    else:
        details.append("  • (none)")

    if mission.config.paths:
        details.extend(["", "[cyan]Path Conventions:[/cyan]"])
        for key, value in mission.config.paths.items():
            details.append(f"  • {key}: {value}")

    if mission.config.mcp_tools:
        details.extend(["", "[cyan]MCP Tools:[/cyan]"])
        details.append(f"  • Required: {', '.join(mission.config.mcp_tools.required) or 'none'}")
        details.append(f"  • Recommended: {', '.join(mission.config.mcp_tools.recommended) or 'none'}")
        details.append(f"  • Optional: {', '.join(mission.config.mcp_tools.optional) or 'none'}")

    return details


def _detect_current_feature(project_root: Path) -> str | None:
    """Return None — no auto-detection (requires explicit --mission).

    Args:
        project_root: Project root path (unused)

    Returns:
        Always None; caller must provide --mission explicitly.
    """
    return None


@app.command("current")
def current_cmd(
    mission: Annotated[str | None, typer.Option("--mission", help="Mission slug")] = None,
) -> None:
    """Show currently active mission for a mission (auto-detects mission from cwd)."""
    project_root = get_project_root_or_exit()

    detected_mission = _detect_current_feature(project_root)

    if mission is None and not detected_mission:
        console.print(
            "[yellow]No active mission detected.[/yellow]\n"
            "\nUse [cyan]--mission <slug>[/cyan] to specify one, "
            "or run from within a mission worktree."
        )
        # Optionally list available missions
        mission_specs = project_root / KITTY_SPECS_DIR
        if mission_specs.is_dir():
            missions = sorted(
                d.name for d in mission_specs.iterdir()
                if d.is_dir() and d.name[0:1].isdigit()
            )
            if missions:
                console.print("\n[cyan]Available missions:[/cyan]")
                for slug in missions[:10]:
                    console.print(f"  - {slug}")
                if len(missions) > 10:
                    console.print(f"  ... and {len(missions) - 10} more")
        raise typer.Exit(2)

    mission_slug: str
    if mission is None:
        # No flag was explicitly provided — use auto-detected mission as-is.
        # (We already exited above when detected_mission was also None.)
        assert detected_mission is not None
        mission_slug = detected_mission
    else:
        mission_norm = mission.strip() if isinstance(mission, str) else None
        if not mission_norm:
            raise typer.BadParameter("--mission <slug> is required")
        mission_slug = mission_norm

    try:
        # WP09/FR-001 (kind-correct — deliberately EXCLUDED from the
        # `read_dir(kind)` migration, mirroring `close_cmd` below and
        # `decision.py::_resolve_repo_root_and_slug`): the sibling `close_cmd`
        # existence probe carries a pinned test requiring
        # `resolve_action_context`'s structured `ActionContextError` to
        # propagate for an unresolvable/ambiguous handle — neither
        # `read_dir(kind)` partition leg replicates that (see the rationale at
        # `close_cmd`). This site shares the identical existence-probe shape,
        # so it keeps calling the richer resolver directly for the same
        # fail-closed guarantee.
        feature_dir = resolve_feature_dir_for_mission(project_root, mission_slug)
        if not feature_dir.exists():
            console.print(f"[red]Mission not found:[/red] {mission_slug}")
            raise typer.Exit(1)

        # FR-005 (#3831): `get_mission_for_feature` signals a software-dev
        # fallback substitution only via `warnings.warn` (mission.py, unchanged
        # by this fix — every other caller keeps that exact signal). Under
        # default warning filters that never reaches an operator running the
        # CLI normally (and even under `-W always` it never reaches *this*
        # command's stdout), so the substitution was previously invisible here.
        # Capture that one warning locally and re-surface it loudly through the
        # same `console` object already used for the two sibling exceptions
        # just below (`MissionNotFoundError` / `MissionError`), without
        # altering `mission.py`'s own warning behavior for any other caller.
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always")
            loaded_mission = get_mission_for_feature(feature_dir, project_root)
        for caught in caught_warnings:
            if issubclass(caught.category, UserWarning) and "using software-dev as default" in str(caught.message):
                console.print(f"[yellow]Warning:[/yellow] {caught.message}")
            else:
                # #3831 fold: `catch_warnings(record=True)` captures EVERY
                # warning raised inside the block, not just the fallback one
                # this command specifically surfaces above — anything else
                # was previously dropped on the floor. Re-emit it through the
                # normal warnings machinery so it still reaches whatever
                # filter/handler the caller has configured, instead of being
                # silently swallowed by this command's own capture.
                warnings.warn_explicit(
                    caught.message, caught.category, caught.filename, caught.lineno
                )
        context = f"Mission: {mission_slug}"

    except MissionNotFoundError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
    except MissionError as exc:
        console.print(f"[red]Failed to load active mission:[/red] {exc}")
        raise typer.Exit(1) from exc

    panel = Panel(
        "\n".join(_mission_details_lines(loaded_mission)),
        title=f"Active Mission ({context})",
        border_style="cyan",
    )
    console.print(panel)


@app.command("info")
def info_cmd(
    mission_name: str = typer.Argument(..., help="Mission name to display details for"),
) -> None:
    """Show details for a specific mission without switching."""
    project_root = get_project_root_or_exit()
    kittify_dir = project_root / ".kittify"

    try:
        mission = get_mission_by_name(mission_name, kittify_dir)
    except MissionNotFoundError:
        console.print(f"[red]Mission not found:[/red] {mission_name}")
        available = list_available_missions(kittify_dir)
        if available:
            console.print("\n[yellow]Available missions:[/yellow]")
            for name in available:
                console.print(f"  • {name}")
        raise typer.Exit(1) from None
    except MissionError as exc:
        console.print(f"[red]Error loading mission '{mission_name}':[/red] {exc}")
        raise typer.Exit(1) from exc

    panel = Panel(
        "\n".join(_mission_details_lines(mission, include_description=True)),
        title=f"Mission Details · {mission.name}",
        border_style="cyan",
    )
    console.print(panel)


@app.command("create")
def create_cmd(
    from_ticket: Annotated[
        str,
        typer.Option(
            "--from-ticket",
            help="Tracker ticket reference in provider:KEY format (e.g. linear:PRI-42)",
        ),
    ],
) -> None:
    """Fetch a tracker ticket and prepare it as a mission brief.

    Writes the ticket content to .kittify/ticket-context.md so the LLM can
    read it and run /spec-kitty.specify. Records a pending origin so the
    mission-to-ticket link is established automatically when specify completes.

    Example:
        spec-kitty mission create --from-ticket linear:PRI-42
    """
    from specify_cli.core.saas_sync_config import is_saas_sync_enabled, saas_sync_disabled_message
    from specify_cli.tracker.config import load_tracker_config, require_repo_root
    from specify_cli.tracker.saas_client import SaaSTrackerClientError
    from specify_cli.tracker.service import TrackerService, TrackerServiceError
    from specify_cli.tracker.ticket_context import write_pending_origin, write_ticket_context

    if not is_saas_sync_enabled():
        typer.secho(saas_sync_disabled_message(), err=True, fg=typer.colors.RED)
        raise typer.Exit(1)

    # Parse provider:KEY
    if ":" not in from_ticket:
        typer.secho(
            "Error: --from-ticket requires format provider:KEY (e.g. linear:PRI-42)",
            err=True, fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    provider, issue_key = from_ticket.split(":", 1)
    provider = provider.strip().lower()
    issue_key = issue_key.strip()

    if not provider or not issue_key:
        typer.secho("Error: Both provider and issue key are required.", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)

    # Locate repo root and load tracker config
    try:
        repo_root = require_repo_root()
    except Exception as exc:  # noqa: BLE001 — repo-root resolution failure is reported to stderr then converted to Exit(1)
        typer.secho(f"Error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1) from exc

    config = load_tracker_config(repo_root)
    if config.provider and config.provider != provider:
        typer.secho(
            f"Error: This repo is bound to '{config.provider}', not '{provider}'. "
            f"Run: spec-kitty tracker bind --provider {provider}",
            err=True, fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    # Fetch ticket via the SaaS service
    try:
        service = TrackerService(repo_root)
        results = service.issue_search(provider=provider, query=issue_key, limit=5)
    except (TrackerServiceError, SaaSTrackerClientError) as exc:
        typer.secho(f"Error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1) from exc

    # Find exact match on identifier
    ticket = next(
        (t for t in results if (t.get("identifier") or "").upper() == issue_key.upper()),
        results[0] if results else None,
    )
    if ticket is None:
        typer.secho(
            f"Error: Ticket '{issue_key}' not found in {provider}. Check the key and try again.",
            err=True, fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    # Write artefacts
    context_path = write_ticket_context(repo_root, ticket)
    write_pending_origin(repo_root, ticket, provider)

    # Handoff
    console.print()
    console.print(
        f"[green]✓[/green] Ticket [bold]{ticket.get('identifier', issue_key)}[/bold] "
        f"fetched → [dim]{context_path.relative_to(repo_root)}[/dim]"
    )
    console.print(f"  [dim]{ticket.get('title', '')}[/dim]")
    console.print()
    console.print(
        "Run [cyan]/spec-kitty.specify[/cyan] inside your coding agent (Claude Code, Codex, Cursor) "
        "to create the mission from this ticket."
    )
    console.print(
        "The mission will be linked to "
        f"[bold]{provider}:{ticket.get('identifier', issue_key)}[/bold] "
        "automatically on completion."
    )
    console.print()


def _resolve_mission_slug(repo_root: Path, mission_slug: str) -> str:
    """Canonicalize a ``--mission`` handle at the ``run`` boundary.

    F-001: ``--mission`` accepts handles (bare mid8, full ULID, numeric
    prefix). Canonicalize here — the same pattern as the agent
    ``_find_mission_slug`` helpers and ``next_cmd._resolve_mission_slug`` —
    so ``run_custom_mission`` -> ``get_or_start_run`` keys
    ``.kittify/runtime/feature-runs.json`` (and its persisted
    ``mission_slug``) by the canonical directory name. A raw mid8 here
    creates a split-brain duplicate run vs the full-slug invocation.
    Handles that resolve to no existing directory keep their raw form,
    preserving the historical lazy-meta-creation behaviour downstream; an
    ambiguous handle propagates MissionSelectorAmbiguous (C-CTX-4 —
    structured error, never a silent fallback).
    """
    from specify_cli.missions._read_path_resolver import StatusReadPathNotFound

    try:
        candidate: Path = placement_seam(
            get_main_repo_root(repo_root), mission_slug
        ).read_dir(MissionArtifactKind.PRIMARY_METADATA)
    except StatusReadPathNotFound:
        # Fail-closed coordination window (coord worktree root materialized,
        # mission dir absent): fall back to the raw handle so slug resolution
        # stays non-raising at this boundary — the runtime surfaces its own
        # diagnostic downstream.
        return mission_slug
    if candidate.exists():
        return candidate.name
    return mission_slug


@app.command("run")
def run_cmd(
    mission_key: Annotated[
        str,
        typer.Argument(help="The reusable custom mission key."),
    ],
    mission_slug: Annotated[
        str,
        typer.Option("--mission", help="Tracked mission slug."),
    ],
    json_output: Annotated[
        bool,
        typer.Option(
            "--json/--no-json",
            help="Emit JSON envelope to stdout instead of a rich panel.",
        ),
    ] = False,
) -> None:
    """Start (or attach to) a runtime for a project-authored custom mission definition."""
    from specify_cli.mission_loader.command import run_custom_mission

    from specify_cli.missions._read_path_resolver import MissionSelectorAmbiguous

    project_root = get_project_root_or_exit(json_output=json_output)
    try:
        mission_slug = _resolve_mission_slug(project_root, mission_slug)
    except MissionSelectorAmbiguous as exc:
        _emit_selector_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    result = run_custom_mission(mission_key, mission_slug, project_root)
    _render_envelope(result.envelope, json_output)
    raise typer.Exit(code=result.exit_code)


def _render_envelope(envelope: dict[str, Any], json_output: bool) -> None:
    """Render the mission-run envelope to stdout.

    With ``json_output`` true, prints a stable JSON dump (no key
    sorting; the contract pins the field order). Without it, builds a
    rich :class:`Panel` mirroring the same fields.
    """
    if json_output:
        if envelope.get("result") == "error":
            payload = json_error(str(envelope["error_code"]), str(envelope["message"]))
            payload.update({key: envelope[key] for key in ("details", "warnings") if key in envelope})
            console.emit_json(payload)
        else:
            print(json.dumps(envelope, indent=2, sort_keys=False))
        return
    _render_human(envelope)


def _render_human(envelope: dict[str, Any]) -> None:
    """Render the envelope as a :class:`rich.panel.Panel`."""
    if envelope.get("result") == "success":
        title = "Mission Run Started"
        border = "green"
        body = _build_success_body(envelope)
    else:
        title = str(envelope.get("error_code") or "ERROR")
        border = "red"
        body = _build_error_body(envelope)

    _append_warning_lines(body, envelope.get("warnings"))

    console.print(Panel(body, title=title, border_style=border))


def _build_success_body(envelope: dict[str, Any]) -> Text:
    body = Text()
    body.append(f"mission_key:  {envelope.get('mission_key')}\n")
    body.append(f"mission_slug: {envelope.get('mission_slug')}\n")
    mission_id = envelope.get("mission_id")
    if mission_id:
        body.append(f"mission_id:   {mission_id}\n")
    body.append(f"feature_dir:  {envelope.get('feature_dir')}\n")
    body.append(f"run_dir:      {envelope.get('run_dir')}")
    return body


def _build_error_body(envelope: dict[str, Any]) -> Text:
    body = Text(str(envelope.get("message") or ""))
    details = envelope.get("details") or {}
    if not isinstance(details, dict):
        return body
    for key, value in details.items():
        body.append(f"\n  {key}: {value}")
    return body


def _append_warning_lines(body: Text, warnings: Any) -> None:
    for warn in warnings or []:
        if not isinstance(warn, dict):
            continue
        body.append(f"\n[warn] {warn.get('code', '')}: {warn.get('message', '')}")


@app.command("close")
def close_cmd(
    mission: Annotated[
        str | None,
        typer.Option("--mission", help="Mission slug (auto-detected from cwd if omitted)"),
    ] = None,
    discard: Annotated[
        bool,
        typer.Option(
            "--discard",
            help="Discard the mission mid-flight: delete the coordination "
                 "branch + all lane branches and tear down all worktrees. "
                 "Without --discard, requires that the mission has already "
                 "been merged (no-op cleanup otherwise).",
        ),
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Skip the confirmation prompt when --discard is set.",
        ),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit a JSON envelope instead of a rich panel."),
    ] = False,
) -> None:
    """Close a mission. Wraps FR-016 lifecycle teardown.

    Without ``--discard``: fail-closed precondition (FR-004/FR-005, #4765) —
    refuses (non-zero exit, no writes) unless the mission has a recorded merge
    baseline (``is_mission_merged``). An all-terminal-but-unmerged mission
    (e.g. every work package cancelled) still refuses here; use ``--discard``
    to abandon it. Once merged: runs the merge-completion teardown — persists
    the mission retrospective to its durable home and tears down the
    coordination worktree. Idempotent after a successful ``spec-kitty merge``
    (which already ran the same teardown); useful when the teardown was
    skipped (e.g. the legacy plain-git/GitHub merge path) or interrupted.
    NOTE: on a merged mission without a retrospective, this generates one
    (``kitty-specs/<slug>/retrospective.yaml``) plus a ``RetrospectiveCaptured``
    event and commits both — it is not a pure no-op in that case. Tolerates a
    mission left with an orphaned ``coordination_branch`` marker (FR-013,
    #2745) — no traceback, the mission slug is rendered once.

    With ``--discard``: abandon the mission mid-flight. Deletes the
    coordination branch and every lane branch named in
    ``lanes.json``, then tears down the coordination worktree and the
    operator-visible lane worktrees. Requires confirmation unless
    ``--force`` is also passed. The coordination + lane branches are
    deleted with ``git branch -D`` (force-delete) because mid-flight
    abandonment by definition leaves uncommitted or unmerged work.

    Implements FR-016 from
    ``kitty-specs/mission-coordination-branch-atomic-event-log-01KSPTVW``.
    """
    project_root = get_project_root_or_exit(json_output=json_output)
    repo_root = _resolve_primary_repo_root(project_root)

    # Resolve mission slug.
    mission_slug = mission or _detect_current_feature(project_root)
    if not mission_slug:
        _emit_mission_error(
            "[red]Error:[/red] No mission specified and no active mission "
            "detected. Use [cyan]--mission <slug>[/cyan].",
            code="mission_not_specified",
            json_output=json_output,
        )
        raise typer.Exit(1)

    # WP09/FR-001 (kind-correct — deliberately EXCLUDED from the `read_dir(kind)`
    # migration, mirroring `decision.py::_resolve_repo_root_and_slug`):
    # `test_mission_close_unresolvable_handle_keeps_structured_error` /
    # `test_mission_close_ambiguous_handle_propagates_structured_error` pin
    # that an unresolvable/ambiguous `--mission` handle here RAISES the
    # structured `ActionContextError` from `resolve_action_context` (never a
    # silent "Mission not found" or a wrong-mission pick). Both `read_dir(kind)`
    # partition legs are lenient by design (`primary_feature_dir_for_mission`
    # is deliberately topology-blind; `candidate_feature_dir_for_mission`
    # never raises on an unresolvable directory) and would swallow that
    # contract, so this keeps calling the richer resolver directly.
    feature_dir = resolve_feature_dir_for_mission(repo_root, mission_slug)
    if not feature_dir.exists():
        _emit_mission_error(
            f"[red]Mission not found:[/red] {mission_slug}",
            code="mission_not_found",
            json_output=json_output,
        )
        raise typer.Exit(1)

    # F-001: re-key to the canonical directory name. `--mission` accepts
    # handles (bare mid8, numeric prefix); the resolver canonicalizes the
    # DIRECTORY only, while `_discard_mission` / `_teardown_coordination_worktree`
    # compose names from the slug — `_delete_lane_branches` via
    # `lane_branch_name(raw, lane_id)` and `_remove_lane_worktrees` via the
    # exact-name `_expected_lane_worktree_dir_names` composition
    # (`<slug>-<mid8>-lane-<id>`). Fed a raw handle, those helpers would compose
    # the WRONG on-disk names and leave the real worktrees/branches behind while
    # the command reports success.
    mission_slug = feature_dir.name

    # Surface fix (#2120): identity/lane reads (meta.json/lanes.json) and the
    # teardown below are all PRIMARY-anchored. The resolver above stays the
    # canonical handle-resolution + structured-error source, but once a
    # coordination worktree exists it returns that worktree's status-only dir
    # (no meta.json → _read_mission_mid8 empties → teardown silently no-ops).
    # Re-anchor to the primary mission dir, matching how `mission reopen` resolves.
    # read-side-seam-primary-primitive-closure-01KYKMMT WP04 (FR-004): the
    # terminal read is routed through the kind-aware placement seam directly —
    # the (now-bypassed) primary_feature_dir_for_mission wrapper's own body was
    # exactly this seam call reading PRIMARY_METADATA (meta.json is read right
    # below), so passing the kind here lets the resolver decide the partition.
    # WP08 (T036): the caller-side canonicalizer fold DROPPED — this call is
    # ``read_dir(...)``, not a direct canonicalizer-primitive call, so it was
    # never subject to that gate's def-use check; ``mission_slug`` is already
    # ``feature_dir.name`` (line 593, already composed) and the seam folds it
    # again internally regardless (idempotent no-op for an already-canonical
    # handle).
    feature_dir = placement_seam(repo_root, mission_slug).read_dir(
        MissionArtifactKind.PRIMARY_METADATA
    )

    meta_path = feature_dir / "meta.json"
    mid8_value = _read_mission_mid8(meta_path)

    # FR-013 (#2745 facet 3): suppress incidental logging noise (e.g. the
    # placement-seam ZERO_EVIDENCE degrade warning fired by an orphaned
    # ``coordination_branch`` marker, #1848) while emitting a JSON envelope so
    # ``--json`` output stays parseable machine output, not mixed human text.
    with json_output_guard(json_output):
        if discard:
            _discard_mission(
                repo_root=repo_root,
                feature_dir=feature_dir,
                mission_slug=mission_slug,
                mid8_value=mid8_value,
                meta_path=meta_path,
                force=force,
            )
            # Fail closed (#2120): a destructive discard must not report success
            # while leaving worktrees/branches behind. Verify BEFORE flattening so the
            # legacy-branch check can still read coordination_branch from meta.json.
            _verify_discard_complete(
                repo_root, mission_slug, mid8_value, feature_dir, meta_path
            )
            # Flatten: drop the now-dangling coordination_branch marker so subsequent
            # commands for this mission don't trip CoordinationBranchDeleted (#2120).
            _flatten_discarded_mission(feature_dir)
            # #704: the spec directory deliberately survives a discard (the
            # retrospective lives there), so mark the mission instead of deleting it
            # and let the dashboard filter on the marker. Written before the commit
            # leg below so it lands in the same bookkeeping commit as the flatten.
            _mark_mission_discarded(feature_dir)
            # #3716: the flatten is the LAST mutating write on the discard path and
            # previously had no commit leg, leaving ``meta.json`` modified-uncommitted
            # after a discard that reported success. Commit it to the PRIMARY surface.
            _commit_flattened_meta(repo_root, feature_dir, mission_slug)
            if json_output:
                console.emit_json({"ok": True, "result": "discarded", "mission_slug": mission_slug})
            else:
                console.print(f"[green]✓[/green] Mission {mission_slug} discarded.")
        else:
            # Fail-closed precondition (FR-004/FR-005, #4765): a non-discard
            # close must never fabricate a completion record (retrospective +
            # teardown) for a mission that was never merged. Checked BEFORE any
            # write/teardown so a refused close leaves the mission untouched —
            # writes/commits/emits NOTHING and the coordination worktree stays
            # intact. D4: keyed on `is_mission_merged` (the explicit `merged_at`
            # marker), NOT `is_mission_completed` — an all-terminal-but-unmerged
            # mission (e.g. every work package cancelled) must still go via
            # `--discard`, not be treated as completed. Mirrors the existing
            # `reopen_cmd` guard (#1926).
            from specify_cli.status import is_mission_merged  # noqa: PLC0415 — facade import (C-002)

            if not is_mission_merged(feature_dir):
                _emit_mission_error(
                    "[red]Error:[/red] cannot close: mission "
                    f"[bold]{mission_slug}[/bold] has not been merged.\n"
                    "[dim]Remediation: this mission has no recorded merge "
                    "baseline. Use `--discard` to abandon it mid-flight, or "
                    "merge it first (`spec-kitty merge`) before closing.[/dim]",
                    code="mission_not_merged",
                    json_output=json_output,
                )
                raise typer.Exit(1)

            # Teardown the coordination worktree. Routes through the shared
            # ``coordination/teardown.py`` seam (persist-before-destroy), the same
            # seam the ``spec-kitty merge`` cleanup + ``--abort`` paths use.
            # Idempotent: no-ops on legacy missions / when already torn down.
            # Tolerates an orphaned ``coordination_branch`` marker (FR-013):
            # the seam's destroy leg is itself idempotent on a missing
            # worktree/branch, so no traceback surfaces here.
            _teardown_coordination_worktree(
                repo_root, mission_slug, mid8_value, quiet=json_output
            )
            if json_output:
                console.emit_json({"ok": True, "result": "closed", "mission_slug": mission_slug})
            else:
                console.print(f"[green]✓[/green] Mission {mission_slug} closed.")


def _read_mission_mid8(meta_path: Path) -> str:
    meta = load_meta(meta_path.parent, allow_missing=True, on_malformed="none")
    if not isinstance(meta, dict):
        return ""
    mid8_value = str(meta.get("mid8") or "").strip()
    if mid8_value:
        return mid8_value
    mission_id_meta = str(meta.get("mission_id") or "").strip()
    # No slug in scope here; the canonical resolver derives ``mission_id[:8]``
    # from the declared id alone. The >= 8 guard preserves the ``else ""``
    # contract (resolve_mid8 also declines to "" below 8 chars).
    return resolve_mid8("", mission_id=mission_id_meta) if len(mission_id_meta) >= 8 else ""


def _discard_mission(
    *,
    repo_root: Path,
    feature_dir: Path,
    mission_slug: str,
    mid8_value: str,
    meta_path: Path,
    force: bool,
) -> None:
    _confirm_discard(mission_slug, force=force)
    lanes_manifest = _load_lanes_manifest_for_discard(feature_dir, mission_slug)
    # Remove ALL worktrees BEFORE deleting their branches (#2120): a branch that
    # is checked out in a worktree cannot be `git branch -D`'d, so the prior
    # branch-first order silently leaked the coordination/lane branches.
    # #3716: this is the abandonment leg — the retrospective the teardown persists
    # must carry ``runtime_abandoned`` provenance, not completion provenance.
    _teardown_coordination_worktree(
        repo_root, mission_slug, mid8_value, provenance_kind="runtime_abandoned"
    )
    if lanes_manifest is not None:
        _remove_lane_worktrees(repo_root, mission_slug, lanes_manifest)
        _delete_lane_branches(repo_root, mission_slug, lanes_manifest)
        return
    _delete_legacy_coordination_branch(repo_root, meta_path)


def _load_lanes_manifest_for_discard(feature_dir: Path, mission_slug: str) -> Any | None:
    """Load ``lanes.json`` for a discard, failing CLOSED on corruption.

    Unlike :func:`_load_lanes_manifest` (which degrades a corrupt manifest to
    ``None``), a destructive discard must not silently route a modern mission
    through the legacy single-branch path on a corrupt manifest — that would
    leave the lane branches/worktrees behind while reporting success (#2120).
    A *missing* manifest is still a legacy mission (``None``); a *corrupt* one
    aborts.
    """
    from specify_cli.lanes.persistence import (
        CorruptLanesError,
        MissingLanesError,
        require_lanes_json,
    )

    try:
        return require_lanes_json(feature_dir)
    except MissingLanesError:
        return None
    except CorruptLanesError as exc:
        console.print(
            f"[red]Error:[/red] cannot discard {mission_slug}: lanes.json is "
            f"corrupt ({exc}). Repair or remove it, then retry."
        )
        raise typer.Exit(1) from exc


def _branch_exists(repo_root: Path, branch_name: str) -> bool:
    import subprocess as _subprocess

    result = _subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{branch_name}"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def _registered_worktree_names(repo_root: Path) -> list[str]:
    """Return the directory names of every git-registered worktree.

    Reads ``git worktree list --porcelain`` so the residual check can catch a
    stale/broken registration whose on-disk directory is already gone — which a
    plain ``.worktrees/`` directory scan would miss.
    """
    import subprocess as _subprocess

    result = _subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    names: list[str] = []
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            names.append(Path(line[len("worktree "):].strip()).name)
    return names


def _expected_discard_branches(
    feature_dir: Path, mission_slug: str, meta_path: Path
) -> list[str]:
    """The branches a discard is expected to delete (for post-teardown verify).

    Mirrors :func:`_delete_lane_branches` / :func:`_delete_legacy_coordination_branch`
    so the residual check verifies exactly the set the discard tried to remove.
    """
    branches: list[str] = []
    manifest = _load_lanes_manifest(feature_dir)
    if manifest is not None:
        from specify_cli.lanes.branch_naming import lane_branch_name
        from specify_cli.lanes.compute import is_planning_lane

        for lane in manifest.lanes:
            if is_planning_lane(lane):
                continue
            branches.append(lane_branch_name(mission_slug, lane.lane_id))
        branches.append(manifest.mission_branch)
        return branches
    meta = load_meta(meta_path.parent, allow_missing=True, on_malformed="none")
    coord_branch = meta.get("coordination_branch") if isinstance(meta, dict) else None
    if coord_branch:
        branches.append(str(coord_branch))
    return branches


def _verify_discard_complete(
    repo_root: Path,
    mission_slug: str,
    mid8_value: str,
    feature_dir: Path,
    meta_path: Path,
) -> None:
    """Fail closed if a discard left worktrees or branches behind (#2120).

    The bug this guards against is a *silent* no-op that still printed success.
    After teardown, any surviving coordination worktree, EXACT lane worktree, or
    expected branch is a real leak — surface it as a non-zero error instead of a
    false ``✓``. Worktrees are matched by exact name (not a ``<slug>-*`` prefix)
    so a sibling mission sharing the prefix neither masks a leak nor trips a
    spurious failure.
    """
    leaks: list[str] = []
    worktrees_root = repo_root / ".worktrees"
    # A surviving worktree leaks if its directory is on disk OR a stale/broken git
    # registration remains (dir gone) — the latter is invisible to an on-disk scan.
    registered = set(_registered_worktree_names(repo_root))

    # Coordination worktree — exact canonical name, on disk OR still registered.
    if mid8_value:
        from specify_cli.coordination import CoordinationWorkspace

        coord_name = CoordinationWorkspace.worktree_path(
            repo_root, mission_slug, mid8_value
        ).name
        if (
            CoordinationWorkspace.is_present(repo_root, mission_slug, mid8_value)
            or coord_name in registered
        ):
            leaks.append(f".worktrees/{coord_name}")

    # Lane worktrees — EXACT names from the manifest (no prefix over-match),
    # likewise checked both on disk and in the git worktree registry.
    manifest = _load_lanes_manifest(feature_dir)
    if manifest is not None:
        for name in sorted(_expected_lane_worktree_dir_names(mission_slug, manifest)):
            if (worktrees_root / name).is_dir() or name in registered:
                leaks.append(f".worktrees/{name}")

    for branch in _expected_discard_branches(feature_dir, mission_slug, meta_path):
        if _branch_exists(repo_root, branch):
            leaks.append(f"branch {branch}")

    if not leaks:
        return

    console.print(
        f"[red]Error:[/red] discard of {mission_slug} did not complete — these "
        "artifacts were not removed:"
    )
    for leak in leaks:
        console.print(f"  - {leak}")
    console.print(
        "[dim]Remove them manually (git worktree remove --force / git branch -D) "
        "and retry, or report this as a bug.[/dim]"
    )
    raise typer.Exit(1)


def _flatten_discarded_mission(feature_dir: Path) -> None:
    """Flatten a discarded mission's coordination metadata (#2120 / #3219).

    Converged onto the canonical ``flatten_coordination_metadata`` primitive
    (FR-015 / D-PLAN-17): pops BOTH ``coordination_branch`` AND the now-stale
    ``topology``, and records ``flattened=True``. Fixes a latent bug the prior
    ``clear_coordination_metadata``-only call left: it cleared
    ``coordination_branch`` but never popped ``topology``, so a discarded
    coord mission could still carry a stored ``topology: "coord"`` value and
    route back through coordination, hitting ``CoordinationBranchDeleted`` on
    a mission that was supposed to be flattened.

    Tolerant: a missing meta.json (legacy mission) is a no-op — flattening is a
    best-effort cleanup, never a hard failure of an otherwise-successful discard.
    """
    from specify_cli.mission_metadata import flatten_coordination_metadata

    with contextlib.suppress(FileNotFoundError):
        flatten_coordination_metadata(feature_dir)


def _mark_mission_discarded(feature_dir: Path) -> None:
    """Stamp ``discarded_at`` on a discarded mission (#704).

    Tolerant in the same way as :func:`_flatten_discarded_mission`: a legacy
    mission with no meta.json is a no-op rather than a hard failure of an
    otherwise-successful discard. Unlike the flatten, this runs for every
    topology — ``flatten_coordination_metadata`` no-ops when there is no
    ``coordination_branch``, so a SINGLE_BRANCH/LANES mission would otherwise
    carry no marker at all.

    Also tolerant of a CORRUPT/unparseable meta.json (``MissionMetaReadError``)
    -- deliberately more tolerant than the flatten leg above. An abandoned
    mission is exactly the one likely to hold a degraded meta.json, and by
    this point the discard has already torn down branches and worktrees;
    crashing here over a cosmetic dashboard marker is the wrong trade.
    """
    from specify_cli.mission_metadata import record_discard

    with contextlib.suppress(FileNotFoundError, MissionMetaReadError):
        record_discard(feature_dir)


def _meta_has_uncommitted_changes(repo_root: Path, meta_path: Path) -> bool:
    """Return ``True`` when ``meta_path`` differs from HEAD or is untracked.

    Fail-open helper (never raises): a git failure or an absent file reports
    "not dirty" so the tolerant commit leg simply no-ops.
    """
    if not meta_path.exists():
        return False
    from specify_cli.core.git_ops import run_command

    rel = str(meta_path)
    resolved_root = repo_root.resolve()
    if meta_path.is_absolute():
        with contextlib.suppress(ValueError):
            rel = str(meta_path.resolve().relative_to(resolved_root))
    ret, out, _ = run_command(
        ["git", "status", "--porcelain", "--", rel],
        capture=True,
        check_return=False,
        cwd=repo_root,
    )
    return ret == 0 and bool(out.strip())


def _commit_flattened_meta(
    repo_root: Path, feature_dir: Path, mission_slug: str
) -> None:
    """Commit the discard flatten's ``meta.json`` write to the PRIMARY surface (#3716).

    ``_flatten_discarded_mission`` is the last mutating write on the discard path
    and (pre-#3716) had no commit leg, so ``mission close --discard`` reported
    success while leaving ``M kitty-specs/<slug>/meta.json`` uncommitted. Route
    the write through the ONE sanctioned bookkeeping-commit surface (the same
    ``commit_merge_bookkeeping`` the retrospective terminus uses).

    The mission is now flattened to single-branch, so the destination is the
    PRIMARY ``target_branch`` — NEVER the coordination branch, which the discard
    already DELETED. That target is also supplied as the degrade ref so the commit
    still lands on the primary surface if placement resolution fails closed
    (the failure mode the discard teardown surfaces, #3716 nuance).

    Tolerant: a legacy/no-op meta (nothing changed, or no ``meta.json``) is a
    silent no-op. Fail-open-but-loud: a commit failure is WARNED, never raised —
    a bookkeeping hiccup must not turn a completed discard into an error.
    """
    meta_path = feature_dir / "meta.json"
    if not _meta_has_uncommitted_changes(repo_root, meta_path):
        return

    from specify_cli.git.bookkeeping_commit import commit_merge_bookkeeping

    meta = load_meta(feature_dir, allow_missing=True, on_malformed="none")
    target_branch = (
        str(meta.get("target_branch") or "").strip() if isinstance(meta, dict) else ""
    ) or None

    try:
        commit_merge_bookkeeping(
            repo_root=repo_root,
            worktree_root=repo_root,
            mission_slug=mission_slug,
            message=f"chore({mission_slug}): flatten discarded mission metadata",
            paths=(meta_path,),
            branch=target_branch,
        )
    except Exception as exc:  # noqa: BLE001 — fail-open: warn, never abort discard
        console.print(
            f"[yellow]Warning:[/yellow] discard of {mission_slug} flattened "
            f"meta.json but could not commit it ({exc}). Commit it manually: "
            f"git -C {repo_root} add {meta_path} && git -C {repo_root} commit "
            f"-m 'chore({mission_slug}): flatten discarded mission metadata'"
        )


def _confirm_discard(mission_slug: str, *, force: bool) -> None:
    if force:
        return
    confirm = typer.confirm(
        f"Discard mission {mission_slug}? This deletes the coordination "
        f"branch, every lane branch, and all worktrees. Unmerged work "
        f"on those branches WILL BE LOST.",
        default=False,
    )
    if not confirm:
        console.print("[yellow]Aborted.[/yellow]")
        raise typer.Exit(1)


def _load_lanes_manifest(feature_dir: Path) -> Any | None:
    try:
        from specify_cli.lanes.persistence import (
            CorruptLanesError,
            MissingLanesError,
            require_lanes_json,
        )

        return require_lanes_json(feature_dir)
    except (MissingLanesError, CorruptLanesError):
        return None


def _delete_lane_branches(repo_root: Path, mission_slug: str, lanes_manifest: Any) -> None:
    from specify_cli.lanes.branch_naming import lane_branch_name
    from specify_cli.lanes.compute import is_planning_lane

    for lane in lanes_manifest.lanes:
        if is_planning_lane(lane):
            continue
        branch_name = lane_branch_name(mission_slug, lane.lane_id)
        _force_delete_branch_if_exists(repo_root, branch_name)

    _force_delete_branch_if_exists(repo_root, lanes_manifest.mission_branch)
    console.print(
        f"  Deleted {len(lanes_manifest.lanes)} lane branch(es) + "
        f"mission/coordination branch"
    )


def _delete_legacy_coordination_branch(repo_root: Path, meta_path: Path) -> None:
    meta = load_meta(meta_path.parent, allow_missing=True, on_malformed="none")
    coord_branch = meta.get("coordination_branch") if isinstance(meta, dict) else None
    if coord_branch:
        _force_delete_branch_if_exists(repo_root, str(coord_branch))
        console.print(f"  Deleted coordination branch {coord_branch}")


def _teardown_coordination_worktree(
    repo_root: Path,
    mission_slug: str,
    mid8_value: str,
    *,
    provenance_kind: ProvenanceKind = "runtime_post_completion",
    quiet: bool = False,
) -> None:
    if not mid8_value:
        return
    # Route through the shared ``teardown_coordination_topology`` seam (FR-004):
    # persist the retrospective to its durable home BEFORE destroying the
    # coordination worktree (persist-before-destroy, FR-005). The destroy leg is
    # best-effort inside the seam; we report success/failure from the on-disk
    # ``is_present`` truth so the operator sees whether manual cleanup is needed.
    # ``provenance_kind`` stamps the captured retrospective — the discard leg
    # passes ``"runtime_abandoned"`` (#3716) so an abandoned mission is not tagged
    # with completion provenance. An orphaned ``coordination_branch`` marker
    # (FR-013, #2745) — declared in meta.json but absent from git — degrades
    # gracefully here: the seam's destroy leg is idempotent on a missing
    # worktree/branch, so this never raises.
    from specify_cli.coordination.teardown import teardown_coordination_topology
    from specify_cli.coordination.workspace import CoordinationWorkspace
    from specify_cli.lanes.branch_naming import coord_mission_dir_name

    teardown_coordination_topology(
        repo_root, mission_slug, mid8_value, provenance_kind=provenance_kind
    )
    if quiet:
        # ``--json`` mode (FR-013): the caller emits a single structured
        # envelope instead — these are the human-readable rich lines.
        return
    if CoordinationWorkspace.is_present(repo_root, mission_slug, mid8_value):
        console.print(
            "[yellow]Warning:[/yellow] coordination worktree still "
            "present after teardown; manual cleanup may be required."
        )
    else:
        # The slug read from the feature dir already embeds the mid8, so name
        # the identity through the seam's idempotent composer instead of
        # appending the mid8 a second time (#4163).
        console.print(
            f"[green]✓[/green] Coordination worktree torn down for "
            f"{coord_mission_dir_name(mission_slug, mid8=mid8_value)}"
        )


def _force_delete_branch_if_exists(repo_root: Path, branch_name: str) -> None:
    """Delete a branch with ``git branch -D`` if it exists. No-op otherwise."""
    import subprocess as _subprocess

    rev_parse = _subprocess.run(
        ["git", "rev-parse", "--verify", f"refs/heads/{branch_name}"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if rev_parse.returncode != 0:
        return
    _subprocess.run(
        ["git", "branch", "-D", "--", branch_name],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )


def _expected_lane_worktree_dir_names(mission_slug: str, lanes_manifest: Any) -> set[str]:
    """Exact on-disk lane-worktree dir names a discard targets (no prefix match).

    Composed by the canonical ``worktree_dir_name`` grammar, keyed on the same
    ``mission_slug`` (= ``feature_dir.name``) and lane set as
    :func:`_delete_lane_branches`, so worktree removal and branch deletion target
    the SAME lanes. Replaces ``.worktrees/<slug>-*`` prefix matching, which
    over-matches a *sibling* mission whose name shares the prefix (legacy non-mid8
    slugs) and could delete its worktree — including uncommitted work.
    """
    from specify_cli.lanes.branch_naming import worktree_dir_name
    from specify_cli.lanes.compute import is_planning_lane

    return {
        worktree_dir_name(mission_slug, mission_id=None, lane_id=lane.lane_id)
        for lane in lanes_manifest.lanes
        if not is_planning_lane(lane)
    }


def _remove_lane_worktrees(
    repo_root: Path,
    mission_slug: str,
    lanes_manifest: Any,
) -> None:
    """Remove this mission's operator-visible lane worktrees by EXACT name.

    The coordination worktree is handled separately by
    :func:`_teardown_coordination_worktree`.
    """
    import subprocess as _subprocess

    worktrees_root = repo_root / ".worktrees"
    if not safe_is_dir(worktrees_root):
        return

    removed = 0
    for name in sorted(_expected_lane_worktree_dir_names(mission_slug, lanes_manifest)):
        entry = worktrees_root / name
        if not safe_is_dir(entry):
            continue
        _subprocess.run(
            ["git", "-C", str(repo_root), "worktree", "remove", str(entry), "--force"],
            capture_output=True,
            text=True,
            check=False,
        )
        removed += 1
    if removed:
        console.print(f"  Removed {removed} lane worktree(s)")


# ---------------------------------------------------------------------------
# WP02 / FR-001/FR-002 — post-mission lifecycle commands
# (``spec-kitty mission reopen`` + ``spec-kitty mission follow-up``)
# ---------------------------------------------------------------------------

def _detect_actor() -> str:
    """Detect caller identity from environment variables.

    Mirrors the ``do``/``advise`` actor-detection chokepoint so re-open and
    follow-up attribution is consistent across the governed-Op surfaces.
    """
    import os  # noqa: PLC0415

    if os.environ.get("CLAUDE_CODE_ENTRYPOINT"):
        return "claude"
    if os.environ.get("CODEX_CLI"):
        return "codex"
    return "operator"


@dataclass(frozen=True, slots=True)
class _ResolvedMissionHandle:
    """Resolution of an operator ``<handle>`` to a concrete mission (T008)."""

    mission_id: str | None
    mission_slug: str
    feature_dir: Path
    mission_branch: str | None


def _resolve_mission_handle(repo_root: Path, handle: str) -> _ResolvedMissionHandle:
    """Resolve a ``mission_id`` / ``mid8`` / slug handle to a mission (T008).

    Disambiguates by ``mission_id`` via the canonical identity resolver
    (``context.mission_resolver.resolve_mission``). An ambiguous handle raises
    ``MissionSelectorAmbiguous`` (stable error code ``MISSION_AMBIGUOUS_SELECTOR``)
    — never a silent slug guess (NFR-004). When the handle resolves to a single
    identity-bearing mission, the canonical ``feature_dir`` is used. Handles that
    match no identity-bearing mission fall back to the literal slug directory
    (legacy missions without ``mission_id`` and direct directory names).
    """
    from specify_cli.context.mission_resolver import (  # noqa: PLC0415
        AmbiguousHandleError,
        MissionNotFoundError,
        resolve_mission,
    )
    from specify_cli.missions._read_path_resolver import (  # noqa: PLC0415
        MissionSelectorAmbiguous,
    )

    try:
        resolved = resolve_mission(handle, repo_root)
    except AmbiguousHandleError as exc:
        # Re-raise as the canonical structured selector error (no silent fallback).
        raise MissionSelectorAmbiguous(
            handle=handle,
            candidates=[c.mission_slug for c in exc.candidates],
        ) from exc
    except MissionNotFoundError:
        # Legacy / no-mission_id handle: fall back to the literal slug directory.
        # #2136/#2164: the seam folds the handle through the proven full-fold
        # internally (WP08 T036: no caller-side pre-fold needed) so a bare
        # human slug whose on-disk primary dir carries the composed ``<slug>-<mid8>``
        # name lands on the real dir (the identity resolver above keys on the dir NAME
        # and so cannot match a bare slug onto a composed dir — it raised
        # MissionNotFoundError). The fold is a NO-OP for a genuinely literal/legacy
        # dir name (back-compat preserved) and propagates ``MissionSelectorAmbiguous``
        # on an ambiguous handle (no silent pick — C-009).
        # read-side-seam-primary-primitive-closure-01KYKMMT WP04 (FR-004): the
        # terminal read is routed through the kind-aware placement seam
        # directly (meta.json is read right below) rather than the
        # (now-bypassed) primary_feature_dir_for_mission wrapper.
        feature_dir = placement_seam(repo_root, handle).read_dir(
            MissionArtifactKind.PRIMARY_METADATA
        )
        meta = _safe_load_meta(feature_dir)
        return _ResolvedMissionHandle(
            mission_id=(meta or {}).get("mission_id") if meta else None,
            mission_slug=feature_dir.name,
            feature_dir=feature_dir,
            mission_branch=(meta or {}).get("mission_branch") if meta else None,
        )

    meta = _safe_load_meta(resolved.feature_dir)
    return _ResolvedMissionHandle(
        mission_id=resolved.mission_id,
        mission_slug=resolved.mission_slug,
        feature_dir=resolved.feature_dir,
        mission_branch=(meta or {}).get("mission_branch") if meta else None,
    )


def _safe_load_meta(feature_dir: Path) -> dict[str, Any] | None:
    """Load ``meta.json`` tolerating absence/corruption (returns ``None``)."""
    try:
        result: dict[str, Any] | None = load_meta_fail_closed(feature_dir)
        return result
    except (OSError, MissionMetaReadError):
        return None


def _branch_resolvable(repo_root: Path, branch: str) -> bool:
    """Return ``True`` when *branch* resolves in the local repo OR any remote.

    Fail-closed predicate (per contract) — but fail-TOWARD-FALSE, the
    opposite posture from the coordination read path's
    ``_coord_branch_exists`` (fail-toward-present): a mission branch that
    cannot be proven to exist anywhere is treated as unrecoverable. A missing
    worktree directory alone does NOT make a mission unrecoverable — the
    branch is re-materializable — so this check is intentionally branch-only.

    #4979 (C-001): consumes the SAME shared
    :func:`~specify_cli.git.remote_probes.remote_branch_lookup` primitive
    ``_coord_branch_exists`` does, refactored off its own hand-rolled
    ``git remote`` + ``git ls-remote`` loop (which had no ``timeout=`` and
    could hang on an unreachable/prompting remote — the primitive fixes that
    too). Only ``HIT`` counts as resolvable here; ``ERROR`` / ``NO_REMOTE`` /
    ``CLEAN_MISS`` all fall through to ``False`` — the fail-closed direction
    this predicate has always used, unlike the coordination read path's
    ERROR-is-present posture.
    """
    from specify_cli.core import git_ops  # noqa: PLC0415

    code, _out, _err = git_ops.run_command(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"],
        check_return=False,
        capture=True,
        cwd=repo_root,
    )
    if code == 0:
        return True

    return remote_branch_lookup(repo_root, branch) is RemoteLookup.HIT


def _emit_mission_error(message: str, *, code: str, json_output: bool) -> None:
    """Preserve human diagnostics while emitting the shared machine contract."""
    if json_output:
        console.emit_json(json_error(code, Text.from_markup(message).plain))
    else:
        console.print(message)


def _emit_selector_error(exc: Exception, *, json_output: bool = False) -> None:
    """Render a selector failure, retaining handle/candidate diagnostic metadata."""
    if json_output:
        payload = json_error(getattr(exc, "error_code", "MISSION_AMBIGUOUS_SELECTOR"), str(exc))
        payload.update(handle=getattr(exc, "handle", ""), candidates=getattr(exc, "candidates", []))
        console.emit_json(payload)
        return
    console.print(f"[red]MISSION_AMBIGUOUS_SELECTOR[/red]\n{exc}")


@app.command("reopen")
def reopen_cmd(
    handle: Annotated[
        str,
        typer.Argument(help="Mission handle: mission_id (ULID), mid8, or slug."),
    ],
    reason: Annotated[
        str,
        typer.Option("--reason", help="Why the mission is being re-opened (required, audited)."),
    ],
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit a JSON envelope instead of a rich panel."),
    ] = False,
) -> None:
    """Re-open a merged/closed mission, returning it to an actionable state (FR-002).

    Appends a ``MissionReopened`` lifecycle event (the authority for
    actionability — ``derive_mission_lifecycle`` reports the ``reopened``
    surface_state) and clears the ``merged_*`` markers from ``meta.json``. Does
    NOT mutate WP lanes — the operator repositions WPs explicitly afterwards.

    Fail-closed (NFR-004): the mission is unrecoverable when ``meta.json`` is
    absent/corrupt OR the mission branch resolves in neither the local repo nor
    any configured remote. A missing worktree directory alone is recoverable. On
    unrecoverable input the command exits non-zero with a remediation hint and
    writes no event / no metadata change.
    """
    from specify_cli.missions._read_path_resolver import (  # noqa: PLC0415
        MissionSelectorAmbiguous,
    )
    from specify_cli.mission_metadata import (
        clear_merge_metadata,
        snapshot_merge_metadata,
    )
    from specify_cli.status import emit_mission_reopened, is_mission_completed

    project_root = get_project_root_or_exit(json_output=json_output)
    repo_root = _resolve_primary_repo_root(project_root)

    try:
        resolved = _resolve_mission_handle(repo_root, handle)
    except MissionSelectorAmbiguous as exc:
        _emit_selector_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc

    # Fail-closed predicate (a): meta.json absent / corrupt (no resolvable mission_id).
    meta = _safe_load_meta(resolved.feature_dir)
    if meta is None or not resolved.mission_id:
        _emit_mission_error(
            "[red]Error:[/red] mission is unrecoverable — "
            f"meta.json is missing or corrupt for handle [bold]{handle}[/bold].\n"
            "[dim]Remediation: restore meta.json (or run "
            "`spec-kitty migrate backfill-identity`) before re-opening.[/dim]",
            code="mission_unrecoverable",
            json_output=json_output,
        )
        raise typer.Exit(1)

    # Fail-closed predicate (b): branch in neither local repo nor any remote.
    mission_branch = resolved.mission_branch or meta.get("mission_branch")
    if mission_branch and not _branch_resolvable(repo_root, str(mission_branch)):
        _emit_mission_error(
            "[red]Error:[/red] mission is unrecoverable — branch "
            f"[bold]{mission_branch}[/bold] resolves in neither the local repo "
            "nor any configured remote.\n"
            "[dim]Remediation: fetch the branch (`git fetch <remote> "
            f"{mission_branch}`) or restore it before re-opening.[/dim]",
            code="mission_branch_unavailable",
            json_output=json_output,
        )
        raise typer.Exit(1)

    # Fail-closed precondition (#1926): a mission can only be re-opened once it
    # has reached completion (merged, or all WPs terminal). Checked BEFORE any
    # metadata mutation so a rejected re-open leaves meta.json untouched and
    # writes no event. The emit helper enforces the same invariant defensively.
    if not is_mission_completed(resolved.feature_dir):
        _emit_mission_error(
            "[red]Error:[/red] cannot re-open: mission "
            f"[bold]{resolved.mission_slug}[/bold] has not completed/merged.\n"
            "[dim]Remediation: a mission can only be re-opened after it has "
            "merged or all its work packages are terminal.[/dim]",
            code="mission_not_completed",
            json_output=json_output,
        )
        raise typer.Exit(1)

    # Persist the replacement audit fact while the completion proof is still
    # present. Clearing first made marker-only missions fail the producer's
    # canonical completion guard after their sole proof had already been
    # durably removed (#4870). The event-first order has no proofless gap if
    # emission refuses or fails: meta.json remains byte-for-byte untouched.
    # The trailing clear below is a separate, guarded step: if it raises
    # (e.g. FileNotFoundError, concurrent delete) AFTER the event above has
    # already been durably appended, that is surfaced as a clean, retryable
    # error rather than an unhandled traceback (#4870 follow-up).
    cleared = snapshot_merge_metadata(meta)
    event = emit_mission_reopened(
        resolved.feature_dir,
        mission_id=resolved.mission_id,
        mission_slug=resolved.mission_slug,
        reason=reason,
        reopened_by=_detect_actor(),
        cleared_merge=cleared or None,
    )
    try:
        clear_merge_metadata(resolved.feature_dir)
    except Exception as exc:  # noqa: BLE001 — surfaced as a structured, retryable error
        _emit_mission_error(
            "[red]Error:[/red] mission "
            f"[bold]{resolved.mission_slug}[/bold] was re-opened and the audit "
            f"event was recorded, but clearing the merge markers failed ({exc}).\n"
            "[dim]Remediation: rerun `spec-kitty mission reopen "
            f"{resolved.mission_slug}` to complete marker cleanup.[/dim]",
            code="mission_reopen_clear_failed",
            json_output=json_output,
        )
        raise typer.Exit(1) from exc

    if json_output:
        print(
            json.dumps(
                {
                    "result": "reopened",
                    "mission_id": resolved.mission_id,
                    "mission_slug": resolved.mission_slug,
                    "reason": reason,
                    "cleared_merge": cleared,
                    "event_id": (event or {}).get("event_id"),
                },
                indent=2,
                sort_keys=True,
            )
        )
        raise typer.Exit(0)

    console.print(
        f"[green]✓[/green] Mission [bold]{resolved.mission_slug}[/bold] re-opened "
        "and is actionable again."
    )
    if cleared:
        console.print(f"  [dim]Cleared merge markers: {', '.join(sorted(cleared))}[/dim]")
    raise typer.Exit(0)


@app.command("follow-up")
def follow_up_cmd(
    handle: Annotated[
        str,
        typer.Argument(help="Mission handle: mission_id (ULID), mid8, or slug."),
    ],
    commit: Annotated[
        str | None,
        typer.Option("--commit", help="40-hex commit SHA of the follow-up."),
    ] = None,
    pr: Annotated[
        int | None,
        typer.Option("--pr", help="Pull-request number of the follow-up."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit a JSON envelope instead of a rich panel."),
    ] = False,
) -> None:
    """Record a follow-up commit or PR against a mission (FR-001).

    Exactly one of ``--commit <40-hex>`` / ``--pr <int>`` must be supplied.
    Appends a ``FollowUpRecorded`` lifecycle event attributed to ``mission_id``.
    Fail-closed (#1926): only valid once the mission has reached completion
    (merged, or all WPs terminal) — a follow-up against a not-yet-completed
    mission exits non-zero with a structured error and writes no event.
    Idempotent on its dedup key ``(mission_id, commit_sha | pr_number)`` —
    re-recording the same reference is a successful no-op.
    """
    import re  # noqa: PLC0415

    from specify_cli.missions._read_path_resolver import (  # noqa: PLC0415
        MissionSelectorAmbiguous,
    )
    from specify_cli.status import emit_follow_up_recorded, is_mission_completed

    # Validate: exactly one of --commit / --pr.
    if (commit is None) == (pr is None):
        _emit_mission_error(
            "[red]Error:[/red] supply exactly one of [cyan]--commit <40-hex>[/cyan] or [cyan]--pr <int>[/cyan].",
            code="invalid_follow_up_reference",
            json_output=json_output,
        )
        raise typer.Exit(1)

    if commit is not None and not re.fullmatch(r"[0-9a-fA-F]{40}", commit):
        _emit_mission_error(
            f"[red]Error:[/red] --commit must be a 40-character hex SHA, got {commit!r}.",
            code="invalid_commit_sha",
            json_output=json_output,
        )
        raise typer.Exit(1)

    project_root = get_project_root_or_exit(json_output=json_output)
    repo_root = _resolve_primary_repo_root(project_root)

    try:
        resolved = _resolve_mission_handle(repo_root, handle)
    except MissionSelectorAmbiguous as exc:
        _emit_selector_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc

    if not resolved.mission_id:
        _emit_mission_error(
            "[red]Error:[/red] mission has no resolvable mission_id for handle "
            f"[bold]{handle}[/bold].\n"
            "[dim]Remediation: run `spec-kitty migrate backfill-identity`.[/dim]",
            code="mission_identity_missing",
            json_output=json_output,
        )
        raise typer.Exit(1)

    # Fail-closed precondition (#1926): a follow-up is a post-mission fact and is
    # only valid once the mission has reached completion (merged, or all WPs
    # terminal). Checked before emitting so a rejected follow-up writes no event.
    # The emit helper enforces the same invariant defensively.
    if not is_mission_completed(resolved.feature_dir):
        _emit_mission_error(
            "[red]Error:[/red] cannot record follow-up: mission "
            f"[bold]{resolved.mission_slug}[/bold] has not completed/merged.\n"
            "[dim]Remediation: follow-ups can only be recorded after a mission "
            "has merged or all its work packages are terminal.[/dim]",
            code="mission_not_completed",
            json_output=json_output,
        )
        raise typer.Exit(1)

    follow_up_type = "commit" if commit is not None else "pr"
    event = emit_follow_up_recorded(
        resolved.feature_dir,
        mission_id=resolved.mission_id,
        mission_slug=resolved.mission_slug,
        follow_up_type=follow_up_type,
        commit_sha=commit,
        pr_number=pr,
        recorded_by=_detect_actor(),
    )

    deduped = event is None  # idempotent no-op when already recorded.

    if json_output:
        print(
            json.dumps(
                {
                    "result": "recorded" if not deduped else "duplicate",
                    "mission_id": resolved.mission_id,
                    "mission_slug": resolved.mission_slug,
                    "follow_up_type": follow_up_type,
                    "commit_sha": commit,
                    "pr_number": pr,
                    "event_id": (event or {}).get("event_id"),
                },
                indent=2,
                sort_keys=True,
            )
        )
        raise typer.Exit(0)

    ref = commit if commit is not None else f"#{pr}"
    if deduped:
        console.print(
            f"[dim]Follow-up {follow_up_type} {ref} already recorded for "
            f"{resolved.mission_slug} (no-op).[/dim]"
        )
    else:
        console.print(
            f"[green]✓[/green] Recorded follow-up {follow_up_type} [bold]{ref}[/bold] "
            f"for {resolved.mission_slug}."
        )
    raise typer.Exit(0)


@app.command("switch", deprecated=True)
def switch_cmd(
    mission_name: str = typer.Argument(..., help="Mission name (no longer supported)"),  # noqa: ARG001
    force: bool = typer.Option(False, "--force", help="(ignored)"),  # noqa: ARG001
) -> None:
    """[REMOVED] Switch active mission - this command was removed in v0.8.0."""
    console.print("[bold red]Error:[/bold red] The 'mission switch' command was removed in v0.8.0.")
    console.print()
    console.print("Mission types are now selected [bold]per mission run[/bold] during [cyan]/spec-kitty.specify[/cyan].")
    console.print()
    console.print("[cyan]New workflow:[/cyan]")
    console.print("  1. Run [bold]/spec-kitty.specify[/bold] inside your coding agent (Claude Code, Codex, Cursor) to start a new feature")
    console.print("  2. The system will infer and confirm the appropriate mission")
    console.print("  3. Mission is stored in the feature's [dim]meta.json[/dim]")
    console.print()
    console.print("[cyan]To see available missions:[/cyan]")
    console.print("  spec-kitty mission list")
    console.print()
    console.print("[dim]See: https://github.com/your-org/spec-kitty#mission-types[/dim]")
    raise typer.Exit(1)


# ---------------------------------------------------------------------------
# FR-016: spec-kitty mission-type list (alias for charter mission-type list)
# FR-017: spec-kitty mission-type show <id>
# ---------------------------------------------------------------------------


@app.command("list")
def list_mission_types(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON.",
    ),
) -> None:
    """List activated mission types for the current project (FR-016).

    Alias for ``spec-kitty charter mission-type list``.

    Returns only mission types that are explicitly activated in this
    project's charter (activation-filtered).  For all doctrine-layer
    types regardless of activation, use ``spec-kitty doctrine mission-type list``.
    """
    from specify_cli.cli.commands.charter.mission_type import (  # noqa: PLC0415
        charter_mission_type_list,
    )

    charter_mission_type_list(json_output=json_output, include_inactive=False)


@app.command("show")
def show_mission_type(
    mission_type_id: str = typer.Argument(..., help="Mission type ID (e.g. software-dev)."),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON.",
    ),
) -> None:
    """Show the fully resolved MissionType definition for this project (FR-017).

    Displays all fields of the activated mission type:
    id, display_name, action_sequence, template_set,
    source_layer, extends.

    Exits with code 1 and lists registered IDs when ``mission_type_id``
    is not an activated type.
    """
    from charter.activation.mission_type_profiles import (  # noqa: PLC0415
        UnknownMissionTypeError,
        existing_mission_types,
        resolve_mission_type_context,
    )
    from specify_cli.cli.commands.charter.mission_type import (  # noqa: PLC0415
        mission_type_error_boundary,
        resolve_layered_roster,
        resolve_mission_type_source_layer,
    )

    repo_root = Path.cwd()
    with mission_type_error_boundary(json_output):
        activated_ids = existing_mission_types(repo_root)

        if mission_type_id not in activated_ids:
            err = UnknownMissionTypeError(mission_type_id, registered_ids=activated_ids)
            raise err

        mt = resolve_layered_roster(repo_root).get(mission_type_id)
        if mt is None:
            err = UnknownMissionTypeError(mission_type_id, registered_ids=activated_ids)
            raise err

        # FR-007 (sites 2/3): one real, resolved value shared by both the JSON
        # and Panel branches below -- not two independently-hardcoded literals.
        source_layer = resolve_mission_type_source_layer(mission_type_id, repo_root)

        try:
            resolved = resolve_mission_type_context(repo_root, mission_type=mission_type_id)
            action_seq = resolved.action_sequence
            # S-C cutover (mission-step-creatability-01KXQA6R WP01, FR-003): the
            # retired `MissionType.template_set` field is replaced by the resolved
            # context's `template_set` (still `ResolvedMissionType.template_set`
            # per C-006 -- an immutable mapping, never the model field).
            template_mapping = resolved.template_set
        except UnknownMissionTypeError:
            # Optional-narrowing (WP07 S-B cutover): `MissionType.action_sequence` is
            # `list[str] | None` since WP01 (projection-sourced post-cutover, YAML no
            # longer carries a literal fallback) — narrow before `list()` for mypy --strict.
            action_seq = list(mt.action_sequence or [])
            # Mirrors the resolver's own computation (FR-002): the retired model
            # field has no fallback value to read, so this narrow branch computes
            # the mapping straight from the step authority instead.
            from charter.missions import (  # noqa: PLC0415
                MissionStepRepository,
                project_template_set,
            )

            fallback_steps = list(MissionStepRepository.default().resolve_all_for_mission_type(mission_type_id, pack_context=None).values())
            template_mapping = project_template_set(fallback_steps)
        # `dict()`-wrap: `ResolvedMissionType.template_set` is a `MappingProxyType`,
        # which `json.dumps` cannot serialize directly (TypeError) -- and the panel
        # branch below needs a concrete mapping to test truthiness/sort on.
        template_set = dict(template_mapping) if template_mapping is not None else None

    if json_output:
        data = {
            "id": mt.id,
            "display_name": mt.display_name,
            "action_sequence": action_seq,
            "template_set": template_set,
            "source_layer": source_layer,
            "extends": mt.extends,
        }
        print(json.dumps(data, indent=2))
        raise typer.Exit(0)

    # Human-readable panel output.
    from rich.panel import Panel as _Panel  # noqa: PLC0415

    lines: list[str] = [
        f"[cyan]ID:[/cyan] {mt.id}",
        f"[cyan]Display Name:[/cyan] {mt.display_name}",
        f"[cyan]Source Layer:[/cyan] {source_layer}",
    ]
    if mt.extends:
        lines.append(f"[cyan]Extends:[/cyan] {mt.extends}")
    lines.append(f"[cyan]Action Sequence:[/cyan] {', '.join(action_seq)}")
    if template_set:
        tset_parts = [f"{k}={v}" for k, v in sorted(template_set.items())]
        lines.append(f"[cyan]Template Set:[/cyan] {', '.join(tset_parts)}")
    else:
        lines.append("[cyan]Template Set:[/cyan] (none)")

    console.print(
        _Panel(
            "\n".join(lines),
            title=f"Mission Type · {mt.id}",
            border_style="cyan",
        )
    )
    raise typer.Exit(0)
