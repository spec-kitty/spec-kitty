"""Glossary management CLI commands.

Provides commands for listing glossary terms, viewing conflict history,
and resolving conflicts asynchronously.

Commands:
    glossary list       -- List all terms across scopes
    glossary conflicts  -- Display conflict history from event log
    glossary resolve    -- Resolve a conflict interactively
"""

import json as json_lib
import logging
from pathlib import Path

import typer
from specify_cli.cli.console import CliConsole
from specify_cli.cli.json_contract import json_error, json_output_guard
from rich.table import Table

from glossary.events import (
    _local_append_event,
    build_clarification_resolved,
    build_sense_updated,
    get_event_log_path,
    read_events,
)
from glossary.semantic_events import (
    EVT_GLOSSARY_CLARIFICATION_REQUESTED,
    EVT_GLOSSARY_CLARIFICATION_RESOLVED,
    EVT_GLOSSARY_SENSE_UPDATED,
    EVT_SEMANTIC_CHECK_EVALUATED,
)
from glossary.exceptions import SeedFileValidationError
from glossary.models import (
    TermSense,
    TermSurface,
)
from glossary.scope import GlossaryScope, _parse_sense_status, load_seed_file
from glossary.seed_validation import validate_scope_filename, validate_seed_file_data
from glossary.store import GlossaryStore
from glossary.strictness import Strictness

logger = logging.getLogger(__name__)

app = typer.Typer(help="Glossary management commands")
console = CliConsole(width=120)

# Valid scope values for validation
_VALID_SCOPES = {s.value for s in GlossaryScope}

# Valid strictness values for validation
_VALID_STRICTNESS = {s.value for s in Strictness}


def _glossary_error(json_output: bool, code: str, message: str) -> None:
    """Emit an adopted failure while preserving human diagnostics."""
    if json_output:
        console.emit_json(json_error(code, message))
    else:
        console.print(f"[red]Error: {message}[/red]")


def _load_store_from_seeds(repo_root: Path) -> GlossaryStore:
    """Load a GlossaryStore populated from seed files and event log.

    Reads all scope seed files from .kittify/glossaries/ and populates
    an in-memory store, then replays GlossarySenseUpdated and
    GlossaryClarificationResolved events from the event log to include
    runtime updates and custom definitions.

    Args:
        repo_root: Repository root path

    Returns:
        Populated GlossaryStore reflecting both seed data and event log state
    """
    from glossary.models import Provenance, SenseStatus
    from kernel.clock import now_utc_iso, parse_iso

    # Create a dummy event log path (store needs it but we read from seeds)
    event_log_path = repo_root / ".kittify" / "events" / "glossary" / "_cli.events.jsonl"
    store = GlossaryStore(event_log_path)

    for scope in GlossaryScope:
        senses = load_seed_file(scope, repo_root)
        for sense in senses:
            store.add_sense(sense)

    # Replay event log to incorporate runtime updates
    events_dir = repo_root / ".kittify" / "events" / "glossary"
    if events_dir.exists():
        for event_file in sorted(events_dir.glob("*.events.jsonl")):
            for event in read_events(event_file):
                event_type = event.get("event_type", "")

                if event_type == EVT_GLOSSARY_SENSE_UPDATED:
                    # A new or updated sense from event log
                    new_sense_data = event.get("new_sense", {})
                    surface_text = new_sense_data.get("surface", event.get("term_surface", ""))
                    if not surface_text:
                        continue
                    try:
                        sense = TermSense(
                            surface=TermSurface(surface_text),
                            scope=new_sense_data.get("scope", event.get("scope", "team_domain")),
                            definition=new_sense_data.get("definition", ""),
                            provenance=Provenance(
                                actor_id=event.get("actor", {}).get("actor_id", "system:event_log"),
                                timestamp=parse_iso(event.get("timestamp", now_utc_iso())),
                                source="event_log",
                            ),
                            confidence=new_sense_data.get("confidence", 1.0),
                            status=_parse_sense_status(new_sense_data.get("status")),
                        )
                        store.add_sense(sense)
                    except (ValueError, KeyError) as exc:
                        logger.warning("Skipping malformed GlossarySenseUpdated event: %s", exc)

                elif event_type == EVT_GLOSSARY_CLARIFICATION_RESOLVED:
                    # A resolved clarification may introduce a sense
                    selected = event.get("selected_sense", {})
                    surface_text = selected.get("surface", event.get("term_surface", ""))
                    if not surface_text or not selected.get("definition"):
                        continue
                    try:
                        sense = TermSense(
                            surface=TermSurface(surface_text),
                            scope=selected.get("scope", "team_domain"),
                            definition=selected["definition"],
                            provenance=Provenance(
                                actor_id=event.get("actor", {}).get("actor_id", "system:event_log"),
                                timestamp=parse_iso(event.get("timestamp", now_utc_iso())),
                                source="clarification_resolved",
                            ),
                            confidence=selected.get("confidence", 1.0),
                            status=SenseStatus.ACTIVE,
                        )
                        store.add_sense(sense)
                    except (ValueError, KeyError) as exc:
                        logger.warning("Skipping malformed GlossaryClarificationResolved event: %s", exc)

    return store


def _get_all_terms_from_store(
    store: GlossaryStore,
    scope_filter: GlossaryScope | None = None,
    status_filter: str | None = None,
) -> list:
    """Retrieve all terms from a GlossaryStore.

    Args:
        store: Populated GlossaryStore
        scope_filter: Filter to specific scope (None = all scopes)
        status_filter: Filter by status (active/deprecated/draft)

    Returns:
        List of TermSense objects matching filters
    """
    terms = []

    # Determine scopes to query
    scopes = [scope_filter] if scope_filter else list(GlossaryScope)

    for scope in scopes:
        scope_value = scope.value
        if scope_value in store._cache:
            for _surface, senses in store._cache[scope_value].items():
                for sense in senses:
                    if status_filter and sense.status.value != status_filter:
                        continue
                    terms.append(sense)

    # Sort by scope precedence, then alphabetically by surface
    terms.sort(key=lambda t: (t.scope, t.surface.surface_text))
    return terms


def _extract_conflicts_from_events(  # noqa: C901
    events: list[dict],
    mission_filter: str | None = None,
    unresolved_only: bool = False,
    strictness_filter: str | None = None,
) -> list[dict]:
    """Extract conflict records from event log.

    Uses GlossaryClarificationRequested events as the primary source of
    conflicts (they carry canonical UUID conflict_ids). Falls back to
    SemanticCheckEvaluated findings for conflicts that never reached
    the clarification stage. Resolved status is determined by matching
    GlossaryClarificationResolved conflict_ids.

    Args:
        events: List of parsed event dicts from JSONL
        mission_filter: Filter to specific mission ID
        unresolved_only: Show only unresolved conflicts
        strictness_filter: Filter by effective strictness level

    Returns:
        List of conflict dicts with status tracking
    """
    conflict_events: list[dict] = []
    resolved_conflict_ids: set[str] = set()
    # Track which (step_id, term) combos have a GlossaryClarificationRequested
    clarification_requested_keys: set[tuple[str, str]] = set()

    # Index SemanticCheckEvaluated findings by (step_id, term) for enrichment
    finding_index: dict[tuple[str, str], dict] = {}
    check_event_index: dict[str, dict] = {}  # step_id -> event

    for event in events:
        event_type = event.get("event_type", "")

        if event_type == EVT_SEMANTIC_CHECK_EVALUATED:
            if event.get("blocked"):
                step_id = event.get("step_id", "unknown")
                check_event_index[step_id] = event
                for finding in event.get("findings", []):
                    term_data = finding.get("term", {})
                    term_text = term_data.get("surface_text", "unknown") if isinstance(term_data, dict) else str(term_data)
                    finding_index[(step_id, term_text)] = finding

        elif event_type == EVT_GLOSSARY_CLARIFICATION_REQUESTED:
            # Primary conflict source: has canonical UUID conflict_id
            cid = event.get("conflict_id", "")
            term_text = event.get("term", "unknown")
            step_id = event.get("step_id", "unknown")

            if not cid:
                continue

            clarification_requested_keys.add((step_id, term_text))

            # Enrich with data from SemanticCheckEvaluated finding if available
            finding = finding_index.get((step_id, term_text), {})
            check_event = check_event_index.get(step_id, {})

            conflict_events.append(
                {
                    "conflict_id": cid,
                    "term": term_text,
                    "type": finding.get("conflict_type", "unknown"),
                    "severity": event.get("urgency", finding.get("severity", "unknown")),
                    "mission_id": event.get("mission_id", ""),
                    "timestamp": event.get("timestamp", ""),
                    "status": "unresolved",
                    "effective_strictness": check_event.get("effective_strictness", "unknown"),
                }
            )

        elif event_type == EVT_GLOSSARY_CLARIFICATION_RESOLVED:
            cid = event.get("conflict_id", "")
            if cid:
                resolved_conflict_ids.add(cid)

    # For SemanticCheckEvaluated findings that never got a
    # GlossaryClarificationRequested (e.g., immediately resolved),
    # check if they have a matching GlossaryClarificationResolved instead
    for event in events:
        event_type = event.get("event_type", "")
        if event_type == EVT_GLOSSARY_CLARIFICATION_RESOLVED:
            cid = event.get("conflict_id", "")
            term_text = event.get("term_surface", "unknown")
            # If this resolved event's conflict_id is not yet in our list,
            # it was resolved immediately (no Requested event)
            existing_ids = {c["conflict_id"] for c in conflict_events}
            if cid and cid not in existing_ids:
                conflict_events.append(
                    {
                        "conflict_id": cid,
                        "term": term_text,
                        "type": "unknown",
                        "severity": "unknown",
                        "mission_id": "",
                        "timestamp": event.get("timestamp", ""),
                        "status": "resolved",
                        "effective_strictness": "unknown",
                    }
                )

    # Mark resolved conflicts
    for conflict in conflict_events:
        if conflict["conflict_id"] in resolved_conflict_ids:
            conflict["status"] = "resolved"

    # Apply filters
    if mission_filter:
        conflict_events = [c for c in conflict_events if c["mission_id"] == mission_filter]

    if unresolved_only:
        conflict_events = [c for c in conflict_events if c["status"] == "unresolved"]

    if strictness_filter:
        conflict_events = [c for c in conflict_events if c["effective_strictness"] == strictness_filter]

    return conflict_events


@app.command("list")
def list_terms(
    scope: str | None = typer.Option(
        None,
        "--scope",
        help="Filter by scope (mission_local, team_domain, audience_domain, spec_kitty_core)",
    ),
    status: str | None = typer.Option(
        None,
        "--status",
        help="Filter by status (active, deprecated, draft)",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON (machine-parseable)",
    ),
) -> None:
    """List all terms in glossary."""
    repo_root = Path.cwd()

    # Validate scope
    scope_enum: GlossaryScope | None = None
    if scope:
        if scope not in _VALID_SCOPES:
            _glossary_error(json_output, "invalid_scope", f"Invalid scope '{scope}'. Valid scopes: {', '.join(sorted(_VALID_SCOPES))}")
            raise typer.Exit(1)
        scope_enum = GlossaryScope(scope)

    # Validate status
    valid_statuses = {"active", "deprecated", "draft"}
    if status and status not in valid_statuses:
        _glossary_error(json_output, "invalid_status", f"Invalid status '{status}'. Valid statuses: {', '.join(sorted(valid_statuses))}")
        raise typer.Exit(1)

    # Check glossary directory exists
    glossaries_dir = repo_root / ".kittify" / "glossaries"
    if not glossaries_dir.exists():
        _glossary_error(json_output, "glossary_not_initialized", "Glossary not initialized. Run 'spec-kitty init' with glossary enabled.")
        raise typer.Exit(1)

    # Load store from seed files
    try:
        with json_output_guard(json_output):
            store = _load_store_from_seeds(repo_root)
    except Exception as exc:
        _glossary_error(json_output, "glossary_load_failed", str(exc))
        raise typer.Exit(1) from exc

    # Get all terms with filters
    all_terms = _get_all_terms_from_store(store, scope_enum, status)

    if not all_terms:
        if json_output:
            print("[]")
        else:
            console.print("[dim]No terms found[/dim]")
        return

    # JSON output for scripting (use print() to avoid Rich markup)
    if json_output:
        output = [
            {
                "surface": term.surface.surface_text,
                "scope": term.scope,
                "definition": term.definition,
                "status": term.status.value,
                "confidence": term.confidence,
            }
            for term in all_terms
        ]
        print(json_lib.dumps(output, indent=2))
        return

    # Rich table output
    table = Table(title="Glossary Terms")
    table.add_column("Scope", style="cyan")
    table.add_column("Term", style="bold")
    table.add_column("Definition")
    table.add_column("Status", style="yellow")
    table.add_column("Confidence", justify="right")

    for term in all_terms:
        status_style = {
            "active": "green",
            "deprecated": "red",
            "draft": "yellow",
        }.get(term.status.value, "white")

        definition = term.definition
        if len(definition) > 60:
            definition = definition[:60] + "..."

        table.add_row(
            term.scope,
            term.surface.surface_text,
            definition,
            f"[{status_style}]{term.status.value}[/{status_style}]",
            f"{term.confidence:.2f}",
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(all_terms)} term(s)[/dim]")


@app.command()
def conflicts(
    mission: str | None = typer.Option(
        None,
        "--mission",
        help="Filter conflicts by mission ID",
    ),
    unresolved_only: bool = typer.Option(
        False,
        "--unresolved",
        help="Show only unresolved conflicts",
    ),
    strictness: str | None = typer.Option(
        None,
        "--strictness",
        help="Filter by effective strictness level (off, medium, max)",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON (machine-parseable)",
    ),
) -> None:
    """Display conflict history from event log."""
    repo_root = Path.cwd()

    # Validate strictness filter
    if strictness and strictness not in _VALID_STRICTNESS:
        _glossary_error(json_output, "invalid_strictness", f"Invalid strictness '{strictness}'. Valid values: {', '.join(sorted(_VALID_STRICTNESS))}")
        raise typer.Exit(1)

    # Collect events from all mission event logs
    events_dir = repo_root / ".kittify" / "events" / "glossary"
    all_events: list[dict] = []

    try:
        with json_output_guard(json_output):
            if events_dir.exists():
                for event_file in sorted(events_dir.glob("*.events.jsonl")):
                    for event in read_events(event_file):
                        all_events.append(event)
    except Exception as exc:
        _glossary_error(json_output, "glossary_events_failed", str(exc))
        raise typer.Exit(1) from exc

    if not all_events:
        if json_output:
            print("[]")
        else:
            console.print("[dim]No events found in glossary event log[/dim]")
        return

    # Extract conflicts from events
    conflict_events = _extract_conflicts_from_events(
        all_events,
        mission_filter=mission,
        unresolved_only=unresolved_only,
        strictness_filter=strictness,
    )

    if not conflict_events:
        if json_output:
            print("[]")
        else:
            console.print("[dim]No conflicts found[/dim]")
            console.print("\n[dim]Total: 0 conflict(s)[/dim]")
        return

    # JSON output (use print() to avoid Rich markup)
    if json_output:
        print(json_lib.dumps(conflict_events, indent=2, default=str))
        return

    # Rich table output
    table = Table(title="Conflict History")
    table.add_column("Conflict ID", style="dim")
    table.add_column("Term", style="bold")
    table.add_column("Type")
    table.add_column("Severity")
    table.add_column("Status")
    table.add_column("Strictness", style="magenta")
    table.add_column("Mission", style="cyan")
    table.add_column("Timestamp")

    for conflict in conflict_events:
        severity_style = {
            "high": "red",
            "medium": "yellow",
            "low": "green",
        }.get(conflict["severity"], "white")

        status_style = {
            "resolved": "green",
            "unresolved": "red",
        }.get(conflict["status"], "white")

        cid = conflict["conflict_id"]
        if len(cid) > 20:
            cid = cid[:20] + "..."

        timestamp = conflict["timestamp"]
        if len(timestamp) > 19:
            timestamp = timestamp[:19]

        table.add_row(
            cid,
            conflict["term"],
            conflict["type"],
            f"[{severity_style}]{conflict['severity']}[/{severity_style}]",
            f"[{status_style}]{conflict['status']}[/{status_style}]",
            conflict.get("effective_strictness", ""),
            conflict.get("mission_id", ""),
            timestamp,
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(conflict_events)} conflict(s)[/dim]")

    # Summary statistics
    unresolved_count = len([c for c in conflict_events if c["status"] == "unresolved"])
    if unresolved_count > 0:
        console.print(f"[red]Unresolved: {unresolved_count}[/red]")


@app.command()
def resolve(  # noqa: C901
    conflict_id: str = typer.Argument(..., help="Conflict ID to resolve"),
    mission: str | None = typer.Option(
        None,
        "--mission",
        help="Mission ID for event log (auto-detected if omitted)",
    ),
) -> None:
    """Resolve a conflict asynchronously."""
    repo_root = Path.cwd()

    # FR-010 (WP07): emit the sparse-checkout session warning once per process
    # at this external state-mutating surface. ``warn_if_sparse_once`` is
    # self-memoizing (first caller wins) and swallows detection errors, so it
    # is safe to call unconditionally and never crashes the command.
    try:
        from specify_cli.git.sparse_checkout import warn_if_sparse_once

        warn_if_sparse_once(repo_root, command="spec-kitty glossary resolve")
    except Exception as _exc:  # noqa: BLE001 - defensive; must never break CLI
        logger.debug("sparse-checkout session warning failed for glossary resolve: %s", _exc)

    # Collect events from all mission event logs
    events_dir = repo_root / ".kittify" / "events" / "glossary"
    all_events: list[dict] = []

    if events_dir.exists():
        for event_file in sorted(events_dir.glob("*.events.jsonl")):
            for event in read_events(event_file):
                all_events.append(event)

    # Find the conflict by UUID in GlossaryClarificationRequested events
    # (canonical source of conflict_id UUIDs)
    requested_event: dict | None = None
    conflict_finding: dict | None = None
    conflict_mission_id: str | None = None

    # Index SemanticCheckEvaluated findings for enrichment
    finding_index: dict[tuple[str, str], dict] = {}
    for event in all_events:
        if event.get("event_type") == EVT_SEMANTIC_CHECK_EVALUATED and event.get("blocked"):
            step_id = event.get("step_id", "unknown")
            for finding in event.get("findings", []):
                term_data = finding.get("term", {})
                term_text = term_data.get("surface_text", "unknown") if isinstance(term_data, dict) else str(term_data)
                finding_index[(step_id, term_text)] = finding

    # Search GlossaryClarificationRequested events for the UUID conflict_id
    for event in all_events:
        if event.get("event_type") == EVT_GLOSSARY_CLARIFICATION_REQUESTED:  # noqa: SIM102
            if event.get("conflict_id") == conflict_id:
                requested_event = event
                conflict_mission_id = event.get("mission_id", "unknown")
                # Enrich with finding data
                step_id = event.get("step_id", "unknown")
                term_text = event.get("term", "unknown")
                conflict_finding = finding_index.get((step_id, term_text))
                break

    if not requested_event:
        console.print(f"[red]Error: Conflict '{conflict_id}' not found[/red]")
        raise typer.Exit(1)

    # Check if already resolved
    resolved = any(
        e.get("event_type") == EVT_GLOSSARY_CLARIFICATION_RESOLVED and e.get("conflict_id") == conflict_id
        for e in all_events
    )

    if resolved:
        console.print(f"[yellow]Warning: Conflict '{conflict_id}' already resolved[/yellow]")
        if not typer.confirm("Resolve again?"):
            raise typer.Exit(0)

    # Display conflict details
    term_text = requested_event.get("term", "unknown")

    console.print(f"\n[bold]Conflict: {conflict_id}[/bold]")
    console.print(f"Term: [cyan]{term_text}[/cyan]")

    if conflict_finding:
        console.print(f"Type: {conflict_finding.get('conflict_type', 'unknown')}")
        console.print(f"Severity: {conflict_finding.get('severity', 'unknown')}")
        console.print(f"Context: {conflict_finding.get('context', 'N/A')}")
    else:
        console.print(f"Urgency: {requested_event.get('urgency', 'unknown')}")

    # Show candidate senses - prefer from finding, fall back to requested options
    candidates = []
    if conflict_finding:
        candidates = conflict_finding.get("candidate_senses", [])
    if not candidates:
        # Build candidates from requested event options
        options = requested_event.get("options", [])
        candidates = [
            {"surface": term_text, "scope": "unknown", "definition": opt, "confidence": 0.5} for opt in options
        ]

    if candidates:
        console.print("\n[bold]Candidate senses:[/bold]")
        for i, candidate in enumerate(candidates, 1):
            console.print(f"  {i}. [{candidate.get('scope', '?')}] {candidate.get('definition', 'No definition')}")
    console.print()

    # Prompt for resolution
    options_text = ""
    if candidates:
        options_text = f"Enter 1-{len(candidates)} to select a candidate, "
    options_text += "'C' for custom definition, 'D' to defer"
    console.print(f"[dim]{options_text}[/dim]")

    choice = typer.prompt("Resolution")

    effective_mission = mission or conflict_mission_id or "unknown"

    if choice.upper() == "D":
        console.print("[yellow]Conflict deferred (no resolution made)[/yellow]")
        raise typer.Exit(0)

    if choice.upper() == "C":
        custom_def = typer.prompt("Enter custom definition")
        selected_sense = {
            "surface": term_text,
            "scope": "team_domain",
            "definition": custom_def,
            "confidence": 1.0,
        }
    elif candidates and choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(candidates):
            selected_sense = candidates[idx]
        else:
            console.print(f"[red]Error: Invalid selection '{choice}'[/red]")
            raise typer.Exit(1)
    else:
        console.print(f"[red]Error: Invalid choice '{choice}'[/red]")
        raise typer.Exit(1)

    # Build and persist GlossaryClarificationResolved event
    event = build_clarification_resolved(
        conflict_id=conflict_id,
        term_surface=term_text,
        selected_sense=selected_sense,
        actor={
            "actor_id": "user:cli",
            "actor_type": "human",
            "display_name": "CLI User",
        },
        resolution_mode="async",
        provenance={
            "source": "cli_resolve",
            "timestamp": "",
            "actor_id": "user:cli",
        },
    )

    # Persist to event log
    event_log_path = get_event_log_path(repo_root, effective_mission)
    _local_append_event(event, event_log_path)

    # For custom definitions (choice "C"), also emit GlossarySenseUpdated
    # to persist the new sense in the event log, matching ClarificationMiddleware behavior
    if choice.upper() == "C":
        sense_event = build_sense_updated(
            term_surface=term_text,
            scope=selected_sense.get("scope", "team_domain"),
            new_sense={
                "surface": term_text,
                "scope": selected_sense.get("scope", "team_domain"),
                "definition": selected_sense["definition"],
                "confidence": selected_sense.get("confidence", 1.0),
                "status": "active",
            },
            actor={
                "actor_id": "user:cli",
                "actor_type": "human",
                "display_name": "CLI User",
            },
            update_type="create",
            provenance={
                "source": "cli_resolve",
                "timestamp": "",
                "actor_id": "user:cli",
            },
        )
        _local_append_event(sense_event, event_log_path)

    console.print("[green]Conflict resolved successfully[/green]")


@app.command()
def show(
    term: str = typer.Argument(
        ...,
        help="Term surface name or glossary URN (e.g. 'deployment-target' or 'glossary:deployment-target')",
    ),
) -> None:
    """Render the entity page for a glossary term."""
    # Lazy imports to avoid circular imports
    from glossary.entity_pages import GlossaryEntityPageRenderer, TermNotFoundError
    from rich.markdown import Markdown

    repo_root = Path.cwd()

    surface = term.removeprefix("glossary:").strip().lower()
    renderer = GlossaryEntityPageRenderer(repo_root)
    candidates = [f"glossary:{surface}"]
    if not term.startswith("glossary:"):
        candidates.append(surface)
    for candidate in candidates:
        try:
            page_path = renderer.generate_one(candidate)
        except TermNotFoundError:
            continue
        console.print(Markdown(page_path.read_text(encoding="utf-8")))
        return

    # Compiled entity pages need not exist for a seed/event-backed term.
    # Reuse list's replayed store and retain every scoped sense it exposes.
    store = _load_store_from_seeds(repo_root)
    senses = store.lookup(surface, tuple(scope.value for scope in GlossaryScope))
    if senses:
        for sense in senses:
            console.print(f"{sense.surface.surface_text} ({sense.scope})", markup=False)
            console.print(sense.definition, markup=False)
            console.print(f"Status: {sense.status.value}; confidence: {sense.confidence:.2f}", markup=False)
        return

    console.print(f"[red]Term not found:[/red] {term}")
    console.print("[dim]Run `spec-kitty glossary list` to see available terms.[/dim]")
    raise typer.Exit(1)


# ---------------------------------------------------------------------------
# validate command
# ---------------------------------------------------------------------------


def _validate_single_file(file_path: Path, json_output: bool) -> None:
    """Validate a single glossary seed file."""
    from ruamel.yaml import YAML

    yaml = YAML()
    yaml.preserve_quotes = True

    try:
        data = yaml.load(file_path)
    except Exception as exc:
        if json_output:
            result = {
                "files": [{"path": str(file_path), "valid": False, "term_count": 0,
                           "errors": [{"term_index": None, "term_surface": None,
                                       "field": None, "message": f"YAML parse error: {exc}"}]}],
                "total_files": 1, "valid_files": 0, "invalid_files": 1,
            }
            console.emit_json({**result, **json_error("glossary_validation_failed", f"YAML parse error: {exc}")})
        else:
            console.print(f"[red]YAML parse error in {file_path}: {exc}[/red]")
        raise typer.Exit(1) from exc

    try:
        validated = validate_seed_file_data(data, file_path)
        term_count = len(validated.terms)
        if json_output:
            result = {
                "files": [{"path": str(file_path), "valid": True,
                           "term_count": term_count, "errors": []}],
                "total_files": 1, "valid_files": 1, "invalid_files": 0,
            }
            print(json_lib.dumps(result, indent=2))
        else:
            console.print(f"[green]✓[/green] {file_path} — Valid ({term_count} terms)")
    except SeedFileValidationError as exc:
        if json_output:
            errors = [
                {
                    "term_index": e.term_index,
                    "term_surface": e.term_surface,
                    "field": e.field,
                    "message": e.message,
                }
                for e in exc.errors
            ]
            result = {
                "files": [{"path": str(file_path), "valid": False,
                           "term_count": 0, "errors": errors}],
                "total_files": 1, "valid_files": 0, "invalid_files": 1,
            }
            console.emit_json({**result, **json_error("glossary_validation_failed", str(exc))})
        else:
            console.print(f"\n[red]Validating {file_path}...[/red]\n")
            for e in exc.errors:
                loc_parts: list[str] = []
                if e.term_index is not None:
                    surface_label = f" '{e.term_surface}'" if e.term_surface else ""
                    loc_parts.append(f"term[{e.term_index}]{surface_label}")
                if e.field:
                    loc_parts.append(e.field)
                loc = " → ".join(loc_parts) if loc_parts else "file"
                console.print(f"  [red]✗[/red] {loc}: {e.message}")
            console.print(f"\n{len(exc.errors)} error(s) in {file_path}")
        raise typer.Exit(1) from exc


def _emit_validation_summary(result: dict, invalid_count: int) -> None:
    """Keep successful validation data intact; add the common envelope on failure."""
    if invalid_count:
        console.emit_json({**result, **json_error("glossary_validation_failed", f"{invalid_count} file(s) failed validation")})
    else:
        print(json_lib.dumps(result, indent=2))


def _validate_directory(dir_path: Path, json_output: bool) -> None:
    """Validate all glossary seed files in a directory."""
    from ruamel.yaml import YAML

    yaml_files = sorted(dir_path.glob("*.yaml"))
    if not yaml_files:
        if json_output:
            print(json_lib.dumps({"files": [], "total_files": 0,
                                  "valid_files": 0, "invalid_files": 0}, indent=2))
        else:
            console.print(f"[yellow]No .yaml files found in {dir_path}[/yellow]")
        return

    yaml = YAML()
    yaml.preserve_quotes = True
    file_results: list[dict] = []
    invalid_count = 0

    for yaml_file in yaml_files:
        # Check scope filename
        scope = validate_scope_filename(yaml_file)
        if scope is None and not json_output:
            console.print(
                f"[yellow]⚠ {yaml_file.name}: not a recognized scope filename "
                f"(expected one of: {', '.join(f'{s.value}.yaml' for s in GlossaryScope)})[/yellow]"
            )

        try:
            data = yaml.load(yaml_file)
        except Exception as exc:
            file_results.append({
                "path": str(yaml_file), "valid": False, "term_count": 0,
                "errors": [{"term_index": None, "term_surface": None,
                            "field": None, "message": f"YAML parse error: {exc}"}],
            })
            invalid_count += 1
            if not json_output:
                console.print(f"[red]✗ {yaml_file.name}: YAML parse error: {exc}[/red]")
            continue

        try:
            validated = validate_seed_file_data(data, yaml_file)
            file_results.append({
                "path": str(yaml_file), "valid": True,
                "term_count": len(validated.terms), "errors": [],
            })
            if not json_output:
                console.print(f"[green]✓[/green] {yaml_file.name} — Valid ({len(validated.terms)} terms)")
        except SeedFileValidationError as exc:
            errors = [
                {"term_index": e.term_index, "term_surface": e.term_surface,
                 "field": e.field, "message": e.message}
                for e in exc.errors
            ]
            file_results.append({
                "path": str(yaml_file), "valid": False,
                "term_count": 0, "errors": errors,
            })
            invalid_count += 1
            if not json_output:
                console.print(f"\n[red]✗ {yaml_file.name}:[/red]")
                for e in exc.errors:
                    loc_parts: list[str] = []
                    if e.term_index is not None:
                        surface_label = f" '{e.term_surface}'" if e.term_surface else ""
                        loc_parts.append(f"term[{e.term_index}]{surface_label}")
                    if e.field:
                        loc_parts.append(e.field)
                    loc = " → ".join(loc_parts) if loc_parts else "file"
                    console.print(f"    {loc}: {e.message}")

    valid_count = len(file_results) - invalid_count

    if json_output:
        result = {
            "files": file_results,
            "total_files": len(file_results),
            "valid_files": valid_count,
            "invalid_files": invalid_count,
        }
        _emit_validation_summary(result, invalid_count)
    else:
        console.print(
            f"\nSummary: {invalid_count} of {len(file_results)} file(s) failed validation."
            if invalid_count
            else f"\nAll {len(file_results)} file(s) valid."
        )

    if invalid_count:
        raise typer.Exit(1)


@app.command("validate")
def validate_cmd(
    path: Path = typer.Argument(
        ...,
        help="Path to a glossary seed file (.yaml) or directory of seed files",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output validation results as JSON",
    ),
) -> None:
    """Validate glossary seed file(s) against the schema."""
    if not path.exists():
        message = f"Path '{path}' does not exist."
        if json_output:
            _glossary_error(True, "invalid_path", message)
            raise typer.Exit(2)
        raise typer.BadParameter(message, param_hint="PATH")
    if path.is_file():
        _validate_single_file(path, json_output)
    elif path.is_dir():
        _validate_directory(path, json_output)
    else:
        _glossary_error(json_output, "invalid_path", f"{path} is not a file or directory")
        raise typer.Exit(1)
