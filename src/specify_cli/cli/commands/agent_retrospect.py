"""Agent retrospect commands — synthesizer CLI surface (WP08 / FR-021).

Command surface: ``spec-kitty agent retrospect synthesize``

Default is dry-run.  Pass ``--apply`` to mutate project-local doctrine,
DRG, or glossary state.

Source-of-truth contract:
    kitty-specs/mission-retrospective-learning-loop-01KQ6YEG/contracts/cli_surfaces.md
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from specify_cli.cli.console import console as _console
from specify_cli.cli.console import err_console as _err_console
from rich.table import Table
from typing_extensions import Annotated

from specify_cli.context.mission_resolver import AmbiguousHandleError, MissionNotFoundError, ResolvedMission, resolve_mission
from specify_cli.coordination.surface_resolver import resolve_status_surface
from specify_cli.core.paths import locate_project_root
from kernel.clock import now_utc_iso
from specify_cli.doctrine_synthesizer import (
    SynthesisResult,
    apply_proposals,
)
from specify_cli.retrospective import (
    emit_captured,
)
from specify_cli.retrospective.lifecycle_events import Actor as LifecycleActor
from specify_cli.retrospective.reader import (
    FINDING_CATEGORIES,
    PROPOSAL_CATEGORIES,
    SchemaError,
    YAMLParseError,
    read_gen_record,
    read_record,
)
from specify_cli.retrospective.schema import (
    ActorRef,
    GenActor,
    GenProvenance,
    GenRetrospectiveRecord,
    RetrospectiveRecord,
)
from specify_cli.retrospective.writer import (
    WriterError,
    resolve_existing_record_path,
    write_gen_record,
)
from specify_cli.runtime.resolver import resolve_configured_artifact_name
from specify_cli.status import reduce as reduce_status_events
from specify_cli.status import read_events

app = typer.Typer(
    name="retrospect",
    help="Retrospective synthesis commands for AI agents",
    no_args_is_help=True,
)



def resolve_mission_handle(handle: str, repo_root: Path, *, json_mode: bool = False) -> ResolvedMission:
    """Resolve a mission handle for this command without pre-rendering JSON errors."""
    del json_mode
    return resolve_mission(handle, repo_root)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _retro_path(repo_root: Path, mission_slug: str, mission_id: str = "") -> Path:
    """Return the retrospective.yaml path to read for a mission.

    FR-006 (#1771): the record lives in the tracked feature_dir
    (``kitty-specs/<slug>/retrospective.yaml``); falls back to the legacy
    gitignored ``.kittify/missions/<id>/`` location for pre-relocation records.
    """
    record_path: Path = resolve_existing_record_path(repo_root, mission_slug, mission_id)
    return record_path


def _build_actor(actor_id: Optional[str]) -> ActorRef:
    """Build an :class:`ActorRef` from the supplied actor-id or environment."""
    resolved_id = actor_id or "agent"
    return ActorRef(kind="agent", id=resolved_id)


def _render_rich(result: SynthesisResult, *, dry_run: bool) -> None:
    """Render a :class:`SynthesisResult` as a Rich table to stdout.

    Informationally equivalent to the JSON ``result`` field (CHK034):
    - planned count + proposal_id + kind + diff_preview
    - applied count + proposal_id + target_urn + artifact_path
    - conflicts count + proposal_ids + reason
    - rejected count + proposal_id + reason + detail
    """
    mode_label = "[yellow]DRY-RUN[/yellow]" if dry_run else "[green]APPLY[/green]"
    _console.print(f"\n[bold]agent retrospect synthesize[/bold]  ({mode_label})\n")

    # Planned applications
    if result.planned:
        planned_table = Table(title="Planned Applications", show_header=True, header_style="bold cyan")
        planned_table.add_column("proposal_id", style="dim", no_wrap=True)
        planned_table.add_column("kind")
        planned_table.add_column("diff_preview")
        for p in result.planned:
            planned_table.add_row(p.proposal_id, p.kind, p.diff_preview)
        _console.print(planned_table)
    else:
        _console.print("[dim]No planned applications.[/dim]")

    # Applied changes (only populated when dry_run=False)
    if result.applied:
        applied_table = Table(title="Applied Changes", show_header=True, header_style="bold green")
        applied_table.add_column("proposal_id", style="dim", no_wrap=True)
        applied_table.add_column("target_urn")
        applied_table.add_column("artifact_path")
        applied_table.add_column("re_applied")
        for a in result.applied:
            applied_table.add_row(
                a.proposal_id,
                a.target_urn,
                a.artifact_path,
                str(a.re_applied),
            )
        _console.print(applied_table)

    # Conflicts
    if result.conflicts:
        conflict_table = Table(title="Conflicts", show_header=True, header_style="bold red")
        conflict_table.add_column("proposal_ids")
        conflict_table.add_column("reason")
        for cg in result.conflicts:
            conflict_table.add_row(", ".join(cg.proposal_ids), cg.reason)
        _console.print(conflict_table)

    # Rejections
    if result.rejected:
        rejected_table = Table(title="Rejections", show_header=True, header_style="bold magenta")
        rejected_table.add_column("proposal_id", style="dim", no_wrap=True)
        rejected_table.add_column("reason")
        rejected_table.add_column("detail")
        for r in result.rejected:
            rejected_table.add_row(r.proposal_id, r.reason, r.detail)
        _console.print(rejected_table)

    # Summary line
    _console.print(
        f"\n[bold]Summary:[/bold] "
        f"planned={len(result.planned)} "
        f"applied={len(result.applied)} "
        f"conflicts={len(result.conflicts)} "
        f"rejected={len(result.rejected)} "
        f"events_emitted={len(result.events_emitted)}"
    )


def _build_json_envelope(
    result: SynthesisResult,
    *,
    dry_run: bool,
    outcome: str = "retrospective_synthesized",
    retrospective_path: Path | None = None,
    mission_id: str | None = None,
    mission_slug: str | None = None,
    status: str = "ok",
    next_action: str | None = None,
) -> dict[str, object]:
    """Build the JSON output envelope per cli_surfaces.md / CHK034."""
    envelope: dict[str, object] = {
        "schema_version": "1",
        "command": "agent.retrospect.synthesize",
        "generated_at": now_utc_iso(),
        "dry_run": dry_run,
        "status": status,
        "outcome": outcome,
        "result": result.model_dump(),
    }
    if mission_id is not None:
        envelope["mission_id"] = mission_id
    if mission_slug is not None:
        envelope["mission_slug"] = mission_slug
    if retrospective_path is not None:
        envelope["retrospective_path"] = str(retrospective_path)
    if next_action is not None:
        envelope["next_action"] = next_action
    return envelope


def _canonical_events_dir(repo_root: Path, mission_slug: str, fallback_dir: Path) -> Path:
    """Resolve the directory holding the canonical ``status.events.jsonl`` (FR-009 / #1735).

    Under coordination topology the authoritative event log lives in the
    coordination worktree, not the primary checkout's feature dir — reading
    events through ``resolved.feature_dir`` directly is exactly the #1735
    split-brain bug class. Route through the single canonical surface
    resolver (:func:`resolve_status_surface`, C-005); fall back to
    *fallback_dir* only when the surface cannot be resolved (e.g.
    ``meta.json`` absent for a legacy mission).
    """
    try:
        surface: Path = resolve_status_surface(repo_root, mission_slug)
    except (FileNotFoundError, ValueError):
        return fallback_dir
    return surface.parent


def _required_planning_artifact_filenames() -> tuple[str, str, str]:
    """Return today's (spec, plan, tasks) filenames via the resolved artifact-name seam."""
    return (
        resolve_configured_artifact_name("input.spec.main"),
        resolve_configured_artifact_name("output.plan.main"),
        resolve_configured_artifact_name("output.tasks.list"),
    )


def _mission_artifacts_sufficient_for_empty_record(
    feature_dir: Path,
    *,
    repo_root: Path,
    mission_slug: str,
) -> bool:
    """Return True when mission artifacts can support an empty retrospective.

    ``feature_dir`` anchors the *artifact* checks (spec/plan/tasks live in the
    primary checkout); the *status events* are read through the canonical
    status surface (FR-009 / #1735), which diverges from ``feature_dir`` under
    coordination topology.
    """
    for required in _required_planning_artifact_filenames():
        if not (feature_dir / required).is_file():
            return False
    tasks_dir = feature_dir / "tasks"
    if not tasks_dir.is_dir() or not list(tasks_dir.glob("WP*.md")):
        return False
    try:
        events = read_events(_canonical_events_dir(repo_root, mission_slug, feature_dir))
        if not events:
            return False
        snapshot = reduce_status_events(events)
    except Exception:
        return False
    if not snapshot.work_packages:
        return False
    return all(
        str(state.get("lane")) in {"approved", "done"}
        for state in snapshot.work_packages.values()
    )


def _create_empty_retrospective_record(
    *,
    repo_root: Path,
    mission_id: str,
    mission_slug: str,
    feature_dir: Path,
    actor: ActorRef,
) -> tuple[Path, GenRetrospectiveRecord]:
    """Create an empty retrospective record with synthesize_fabricate provenance.

    Produces a GenRetrospectiveRecord (dataclass-shape) with:
      - provenance.kind = "synthesize_fabricate"
      - findings_status = "ran_no_findings"
    Written via write_gen_record() which enforces the T014 invariant.
    Also emits a RetrospectiveCaptured event with provenance_kind="explicit_create"
    (distinct from the record's provenance.kind per contract semantics).

    Returns:
        A tuple of (canonical_path, gen_record) so the caller can use the
        gen_record directly without re-reading the YAML via the Pydantic reader.
    """
    del feature_dir
    now = now_utc_iso()
    gen_actor = GenActor(kind=actor.kind, id=actor.id)
    record = GenRetrospectiveRecord(
        schema_version=1,
        mission_id=mission_id,
        mission_slug=mission_slug,
        mission_number=None,
        friendly_name="",
        mission_type="software-dev",
        target_branch="main",
        created_at=now,
        created_by=gen_actor,
        provenance=GenProvenance(
            kind="synthesize_fabricate",
            invoked_at=now,
            policy_resolved_from={},
            command="agent retrospect synthesize --fabricate-empty",
        ),
        policy_source={},
        findings_status="ran_no_findings",
        helped=[],
        not_helpful=[],
        gaps=[],
        proposals=[],
        evidence_refs=[],
        generator_version="spec-kitty-cli",
    )
    canonical_path = write_gen_record(record, mode="error", repo_root=repo_root)
    # Emit lifecycle event — provenance_kind="explicit_create" per contract semantics
    # (the event's provenance_kind is distinct from the record's provenance.kind).
    try:
        lifecycle_actor = LifecycleActor(kind="agent", id=actor.id, display="agent retrospect synthesize")
        emit_captured(
            record,
            repo_root,
            provenance_kind="explicit_create",
            actor=lifecycle_actor,
        )
    except Exception:  # noqa: BLE001
        # Non-fatal: record write already succeeded.
        pass
    return canonical_path, record


# ---------------------------------------------------------------------------
# synthesize subcommand
# ---------------------------------------------------------------------------


@app.command(
    "synthesize",
    help=(
        "Apply staged proposals from a mission's retrospective record.\n\n"
        "--dry-run is the default; pass --apply to mutate project state.\n"
        "flag_not_helpful is the only auto-applied kind (Q2-A).\n"
        "Conflict detection is fail-closed: any conflict blocks the whole batch.\n\n"
        "When no retrospective.yaml exists, the command errors with "
        "RETROSPECTIVE_RECORD_MISSING (exit 1) and points to 'spec-kitty retrospect create'.\n"
        "Pass --fabricate-empty to use the legacy auto-fabrication path instead."
    ),
)
def synthesize_cmd(
    mission: Annotated[str, typer.Option("--mission", help="Mission handle (mission_id / mid8 / mission_slug)")],
    apply: Annotated[bool, typer.Option("--apply", help="Execute application after checks pass (default is dry-run)")] = False,
    proposal_id: Annotated[Optional[list[str]], typer.Option("--proposal-id", help="Restrict batch to specific proposal ids (repeatable)")] = None,
    json_out: Annotated[Optional[Path], typer.Option("--json-out", help="Write JSON envelope to PATH in addition to other output")] = None,
    json_only: Annotated[bool, typer.Option("--json", help="Emit JSON to stdout (suppresses Rich rendering)")] = False,
    actor_id: Annotated[Optional[str], typer.Option("--actor-id", help="Override provenance actor id (default: inferred from environment)")] = None,
    fabricate_empty: Annotated[
        bool,
        typer.Option("--fabricate-empty", help="Legacy: auto-fabricate an empty record when none exists (synthesize_fabricate provenance)"),
    ] = False,
) -> None:
    """Apply staged proposals from a mission's retrospective record.

    --dry-run is the default; pass --apply to mutate project-local doctrine,
    DRG, or glossary state.  flag_not_helpful proposals are the only kind
    applied automatically.  Conflict detection is fail-closed.
    """
    # ------------------------------------------------------------------
    # Step 1: Locate project root
    # ------------------------------------------------------------------
    repo_root = locate_project_root()
    if repo_root is None:
        _err_console.print(
            "[red]Error:[/red] Could not locate project root. "
            "Ensure you are inside a spec-kitty project (has .kittify/ or kitty-specs/)."
        )
        raise typer.Exit(1)

    # ------------------------------------------------------------------
    # Step 2: Resolve mission handle → mission_id
    # Exit 1 on unresolvable / ambiguous handle (resolve_mission_handle
    # calls sys.exit(2) internally; we wrap it so our exit code matches
    # the contract's exit=1 for unresolvable).
    # ------------------------------------------------------------------
    try:
        resolved = resolve_mission_handle(mission, repo_root, json_mode=False)
    except MissionNotFoundError as exc:
        if json_only:
            _console.print_json(
                json.dumps(
                    {
                        "schema_version": "1",
                        "command": "agent.retrospect.synthesize",
                        "status": "error",
                        "outcome": "MISSION_NOT_FOUND",
                        "error": "MISSION_NOT_FOUND",
                        "handle": exc.handle,
                        "next_action": "Check the mission handle or run `spec-kitty agent mission list`.",
                    }
                )
            )
        else:
            _err_console.print(
                f'[red]Error:[/red] No mission found for handle "{exc.handle}". '
                f"Check that the handle is correct and that the mission exists in kitty-specs/."
            )
        raise typer.Exit(1) from exc
    except AmbiguousHandleError as exc:
        if json_only:
            _console.print_json(
                json.dumps(
                    {
                        **exc.to_dict(),
                        "schema_version": "1",
                        "command": "agent.retrospect.synthesize",
                        "status": "error",
                        "outcome": "MISSION_AMBIGUOUS_SELECTOR",
                    }
                )
            )
        else:
            _err_console.print(str(exc))
        raise typer.Exit(1) from exc
    except SystemExit as exc:
        raise typer.Exit(1) from exc

    mission_id = resolved.mission_id
    actor = _build_actor(actor_id)

    # ------------------------------------------------------------------
    # Step 3: Load retrospective record
    # Exit 2 = I/O error, 3 = malformed/missing
    # ------------------------------------------------------------------
    retro_file = _retro_path(repo_root, resolved.mission_slug, mission_id)
    outcome = "retrospective_synthesized"
    record: RetrospectiveRecord | None = None
    generator_record: GenRetrospectiveRecord | None = None
    _fabricated_empty = False
    try:
        record = read_record(retro_file)
    except FileNotFoundError as exc:
        missing_record_exc = exc
        # T028: Default path — error with RETROSPECTIVE_RECORD_MISSING (exit 1).
        # Legacy path preserved behind --fabricate-empty flag.
        if not fabricate_empty:
            if json_only:
                _console.print_json(
                    json.dumps(
                        {
                            "result": "blocked",
                            "code": "RETROSPECTIVE_RECORD_MISSING",
                            "mission_id": mission_id,
                            "mission_slug": resolved.mission_slug,
                            "blocked_reason": (
                                f"No retrospective record found for this mission. "
                                f"Author one with: spec-kitty retrospect create --mission {resolved.mission_slug}"
                            ),
                            "exit_code": 1,
                        }
                    )
                )
            else:
                _err_console.print(
                    f"[red]Error RETROSPECTIVE_RECORD_MISSING:[/red] "
                    f"No retrospective record found for this mission.\n"
                    f"Author one with: [bold]spec-kitty retrospect create --mission {resolved.mission_slug}[/bold]"
                )
            raise typer.Exit(1) from missing_record_exc

        # --fabricate-empty: legacy auto-fabrication path
        feature_dir = resolved.feature_dir
        if feature_dir is not None and _mission_artifacts_sufficient_for_empty_record(
            feature_dir,
            repo_root=repo_root,
            mission_slug=resolved.mission_slug,
        ):
            try:
                retro_file, _gen_record = _create_empty_retrospective_record(
                    repo_root=repo_root,
                    mission_id=mission_id,
                    mission_slug=resolved.mission_slug,
                    feature_dir=feature_dir,
                    actor=actor,
                )
                # The fabricated record is in GenRetrospectiveRecord (dataclass) format.
                # We do NOT call read_record() here because the Pydantic reader cannot
                # parse the GenRecord YAML schema. For --fabricate-empty, proposals=[],
                # so we skip re-reading and proceed with an empty proposal set.
                # record is intentionally not set here; all_proposals will be [].
                outcome = "retrospective_record_created"
                # Jump directly to the proposal-building step with empty proposals.
                # Use a sentinel to signal we should skip the normal record-reading path.
                _fabricated_empty = True
            except (WriterError, OSError, YAMLParseError, SchemaError) as exc:
                if json_only:
                    _console.print_json(
                        json.dumps(
                            {
                                "schema_version": "1",
                                "command": "agent.retrospect.synthesize",
                                "status": "error",
                                "outcome": "insufficient_mission_artifacts",
                                "mission_id": mission_id,
                                "mission_slug": resolved.mission_slug,
                                "error": "record_create_failed",
                                "detail": str(exc),
                                "path": str(retro_file),
                                "next_action": "Create or repair retrospective source artifacts, then rerun synthesize.",
                            }
                        )
                    )
                else:
                    _err_console.print(f"[red]Error:[/red] Could not create retrospective record: {exc}")
                raise typer.Exit(3) from exc
        else:
            msg = f"Retrospective record not found and mission artifacts are insufficient: {retro_file}"
            if json_only:
                _console.print_json(
                    json.dumps(
                        {
                            "schema_version": "1",
                            "command": "agent.retrospect.synthesize",
                            "status": "error",
                            "outcome": "insufficient_mission_artifacts",
                            "mission_id": mission_id,
                            "mission_slug": resolved.mission_slug,
                            "error": "record_not_found",
                            "path": str(retro_file),
                            "next_action": "Complete mission artifacts and approved/done WP status, then rerun synthesize.",
                        }
                    )
                )
                raise typer.Exit(0) from missing_record_exc
            _err_console.print(f"[red]Error:[/red] {msg}")
            raise typer.Exit(3) from missing_record_exc
    except (YAMLParseError, SchemaError) as exc:
        gen_exc: Exception | None = None
        try:
            generator_record = read_gen_record(retro_file)
            record = None
        except (FileNotFoundError, YAMLParseError, SchemaError) as gen_error:
            generator_record = None
            gen_exc = gen_error
        else:
            outcome = "retrospective_synthesized"
            if generator_record.proposals:
                _err_console.print(
                    "[yellow]Warning:[/yellow] This retrospective uses the generator record schema; "
                    "proposal application is not available for generator-shape proposals yet, "
                    "so synthesize will run as an empty dry-run batch."
                )
        if generator_record is None:
            # #3533: report the GENERATOR reader's diagnosis, not the Pydantic one.
            # A record written by `retrospect create` is generator-shaped, so the
            # nested-schema reader ALWAYS fails on it and its ~100 field errors
            # describe a schema the file was never meant to satisfy. The generator
            # reader's message is one line and names the offending field, e.g.
            # "not_helpful[0].category is invalid" — the only actionable half.
            # Surfacing the wrong one has twice led readers to conclude the tool
            # contradicts itself when a single enum value was wrong.
            detail = str(gen_exc) if gen_exc is not None else str(exc)
            if gen_exc is not None and "category is invalid" in detail:
                # Findings and proposals both raise "<label>.category is invalid"
                # but draw from DIFFERENT allow-lists (#3537 landing). Pick by the
                # label so a bad proposal category is not handed the finding set.
                if "proposals[" in detail:
                    allowed = ", ".join(sorted(PROPOSAL_CATEGORIES))
                    detail = f"{detail}\nAllowed proposal categories: {allowed}"
                else:
                    allowed = ", ".join(sorted(FINDING_CATEGORIES))
                    detail = f"{detail}\nAllowed finding categories: {allowed}"
            msg = f"Retrospective record malformed: {detail}"
            if json_only:
                _err_console.print_json(json.dumps({"error": "record_malformed", "detail": detail}))
            else:
                _err_console.print(f"[red]Error:[/red] {msg}")
            raise typer.Exit(3) from (gen_exc if gen_exc is not None else exc)
    except OSError as exc:
        msg = f"I/O error reading retrospective: {exc}"
        if json_only:
            _err_console.print_json(json.dumps({"error": "io_error", "detail": str(exc)}))
        else:
            _err_console.print(f"[red]Error:[/red] {msg}")
        raise typer.Exit(2) from exc

    # ------------------------------------------------------------------
    # Step 4: Build the proposal batch
    # Default: all proposals with state.status == "accepted", plus all
    # flag_not_helpful proposals (apply_proposals handles the latter
    # automatically).
    # ------------------------------------------------------------------
    # When --fabricate-empty created the record, _fabricated_empty is True and
    # record is not defined (the gen record format is incompatible with Pydantic
    # read_record). The fabricated record has no proposals by definition.
    if _fabricated_empty or generator_record is not None:
        all_proposals = []
    else:
        assert record is not None
        all_proposals = record.proposals

    if proposal_id:
        # --proposal-id filter: restrict approved_proposal_ids to those listed
        approved_ids: set[str] = set(proposal_id)
    else:
        # Default: all accepted proposals
        approved_ids = {
            p.id for p in all_proposals if p.state.status == "accepted"
        }

    dry_run = not apply

    # ------------------------------------------------------------------
    # Step 5: Call apply_proposals
    # ------------------------------------------------------------------
    result = apply_proposals(
        mission_id=mission_id,
        repo_root=repo_root,
        proposals=all_proposals,
        approved_proposal_ids=approved_ids,
        actor=actor,
        dry_run=dry_run,
    )

    # ------------------------------------------------------------------
    # Step 6: Render output (Rich + optional JSON)
    # ------------------------------------------------------------------
    envelope = _build_json_envelope(
        result,
        dry_run=dry_run,
        outcome=outcome,
        retrospective_path=retro_file,
        mission_id=mission_id,
        mission_slug=resolved.mission_slug,
    )

    if json_only:
        _console.print_json(json.dumps(envelope))
    else:
        _render_rich(result, dry_run=dry_run)

    if json_out is not None:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(envelope, indent=2), encoding="utf-8")
        if not json_only:
            _console.print(f"\n[dim]JSON written to {json_out}[/dim]")

    # ------------------------------------------------------------------
    # Step 7: Exit codes
    # Exit 0 = dry-run complete OR apply succeeded with no issues
    # Exit 4 = conflicts present (apply only)
    # Exit 5 = staleness/invalid-payload rejections (apply only)
    # ------------------------------------------------------------------
    if apply:
        if result.conflicts:
            raise typer.Exit(4)
        has_rejections = any(
            r.reason in ("stale_evidence", "invalid_payload")
            for r in result.rejected
        )
        if has_rejections:
            raise typer.Exit(5)

    raise typer.Exit(0)


# ---------------------------------------------------------------------------
# summary subcommand — back-compat alias for `spec-kitty agent retrospect summary`
# T027: delegates to the canonical implementation in retrospect.py which
#        surfaces the 4-state output. READ-ONLY invariant is enforced there.
# ---------------------------------------------------------------------------


@app.command(
    "summary",
    help=(
        "Cross-mission retrospective summary.\n\n"
        "Back-compat alias: equivalent to `spec-kitty retrospect summary`.\n\n"
        "Distinguishes four record states: has_findings / ran_no_findings / missing / failed.\n\n"
        "No mutation is performed."
    ),
    hidden=False,
)
def summary_cmd(
    project: Annotated[Optional[Path], typer.Option("--project", help="Project root (default: cwd)")] = None,
    json_only: Annotated[bool, typer.Option("--json", help="Emit JSON to stdout")] = False,
    json_out: Annotated[Optional[Path], typer.Option("--json-out", help="Also write JSON to this file")] = None,
    limit: Annotated[int, typer.Option("--limit", min=1, max=100, help="Top-N for ranked sections")] = 20,
    since: Annotated[Optional[str], typer.Option("--since", help="ISO-8601 date filter")] = None,
    include_malformed: Annotated[bool, typer.Option("--include-malformed", help="Include malformed record detail")] = False,
    filter_state: Annotated[Optional[str], typer.Option("--filter", help="Filter by record state (has_findings|ran_no_findings|missing|failed)")] = None,
) -> None:
    """Cross-mission retrospective summary (back-compat alias). READ-ONLY."""
    from specify_cli.cli.commands.retrospect import summary_cmd as _canonical_summary
    _canonical_summary(
        project=project,
        json_only=json_only,
        json_out=json_out,
        limit=limit,
        since=since,
        include_malformed=include_malformed,
        filter_state=filter_state,
    )
