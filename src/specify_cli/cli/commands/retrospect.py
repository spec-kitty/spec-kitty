"""``spec-kitty retrospect`` CLI surface — WP05 (T024-T027).

Commands:
    create    — Author a retrospective for one completed mission.
    backfill  — Author records for historical missions in bulk.
    summary   — Cross-mission retrospective summary (re-exported, 4-state output).

Source-of-truth contract:
    kitty-specs/retrospective-default-policy-01KS049J/contracts/retrospect-cli.contract.md
"""

from __future__ import annotations

from mission_runtime import MissionArtifactKind, resolve_topology
from specify_cli.coordination.coherence import is_coord_residue_churn
from specify_cli.coordination.commit_router import CommitRouterResult, commit_for_mission
from specify_cli.coordination.surface_resolver import resolve_status_surface
from specify_cli.core.constants import KITTIFY_DIR, KITTY_SPECS_DIR, RETROSPECTIVE_FILENAME
from specify_cli.core.utils import safe_is_dir
from specify_cli.mission_metadata import load_meta_or_empty
from specify_cli.missions._read_path_resolver import (
    candidate_feature_dir_for_mission,
)
import contextlib
import json
import subprocess
from kernel.clock import UTC, datetime, now_utc, parse_iso, parse_stamp, timedelta
from kernel.git import status_entries
from pathlib import Path
from typing import Annotated, Literal

import typer
from specify_cli.cli.console import console as _console
from specify_cli.cli.console import err_console as _err_console
from rich.markup import escape
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from specify_cli.context.mission_resolver import (
    AmbiguousHandleError,
    MissionNotFoundError,
    ResolvedMission,
    resolve_mission,
)
from specify_cli.core.agent_config import get_auto_commit_default
from specify_cli.core.paths import locate_project_root
from specify_cli.git.protection_policy import ProtectionPolicy
from specify_cli.retrospective import (
    RetrospectiveActor,
    emit_captured,
    emit_capture_failed,
    emit_skipped as _emit_retro_skipped,
    generate_retrospective,
    resolve_policy,
    write_gen_record,
    RecordExistsError,
    PolicyResolutionError,
)
from specify_cli.retrospective.reader import read_gen_record
from specify_cli.retrospective.writer import resolve_existing_record_path
from specify_cli.retrospective.schema import GenActor, GenProvenance, ProvenanceKind
from specify_cli.retrospective.summary import (
    classify_mission_record,
    iter_mission_instance_dirs,
    legacy_registry_record_dir,
)
from specify_cli.status import read_events
from specify_cli.status import TERMINAL_LANES

app = typer.Typer(
    name="retrospect",
    help=(
        "Retrospective authoring and summary surfaces.\n\n"
        "Use 'create' to author a retrospective for a completed mission,\n"
        "'backfill' to author records in bulk for historical missions,\n"
        "and 'summary' to view a cross-mission summary (read-only)."
    ),
    no_args_is_help=True,
)



# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _cli_actor() -> RetrospectiveActor:
    """Return a CLI actor for provenance."""
    return RetrospectiveActor(kind="human", id="cli", display="spec-kitty retrospect")


def _gen_actor() -> GenActor:
    """Return a GenActor for generator calls."""
    return GenActor(kind="human", id="cli", display="spec-kitty retrospect")


def _canonical_record_path(repo_root: Path, mission_slug: str, mission_id: str = "") -> Path:
    """Return the record path to read for a mission's retrospective.yaml.

    FR-006 (#1771): the record lives in the tracked feature_dir
    (``kitty-specs/<slug>/retrospective.yaml``). Prefers the tracked path; falls
    back to the legacy gitignored ``.kittify/missions/<id>/`` location only when
    a pre-relocation record still lives there (back-compat reads).
    """
    record_path: Path = resolve_existing_record_path(repo_root, mission_slug, mission_id)
    return record_path


def _canonical_events_path(repo_root: Path, mission_slug: str) -> Path:
    """Return the canonical ``status.events.jsonl`` path for *mission_slug*.

    FR-006 (#1735/#1771): retrospect status reads/commits resolve the event log
    through the single canonical surface resolver (:func:`resolve_status_surface`,
    coord-topology-aware, C-005) rather than re-deriving a primary-checkout-only
    path. Falls back to the primary-checkout feature dir only when the surface
    cannot be resolved (e.g. meta.json absent for a legacy mission).
    """
    try:
        surface: Path = resolve_status_surface(repo_root, mission_slug)
    except (FileNotFoundError, ValueError):
        feature_dir: Path = candidate_feature_dir_for_mission(repo_root, mission_slug)
        surface = feature_dir / "status.events.jsonl"
    return surface


def _resolve_handle(
    handle: str,
    repo_root: Path,
    *,
    json_output: bool = False,
) -> ResolvedMission:
    """Resolve a mission handle, emitting structured errors on failure."""
    try:
        return resolve_mission(handle, repo_root)
    except MissionNotFoundError as exc:
        if json_output:
            _console.print_json(
                json.dumps({
                    "result": "blocked",
                    "code": "MISSION_NOT_FOUND",
                    "blocked_reason": f"No mission found for handle {exc.handle!r}.",
                    "exit_code": 1,
                })
            )
        else:
            _err_console.print(
                f"[red]Error MISSION_NOT_FOUND:[/red] "
                f"No mission found for handle {handle!r}. "
                "Check the mission handle or run `spec-kitty agent mission list`."
            )
        raise typer.Exit(1) from exc
    except AmbiguousHandleError as exc:
        if json_output:
            _console.print_json(
                json.dumps({
                    "result": "blocked",
                    "code": "MISSION_AMBIGUOUS_SELECTOR",
                    "blocked_reason": str(exc),
                    "candidates": exc.to_dict().get("candidates", []),
                    "exit_code": 2,
                })
            )
        else:
            _err_console.print(f"[red]Error MISSION_AMBIGUOUS_SELECTOR:[/red] {exc}")
        raise typer.Exit(2) from exc
    except SystemExit as exc:
        raise typer.Exit(1) from exc


def _check_mission_completed(
    resolved: ResolvedMission,
    _repo_root: Path,
) -> list[dict[str, str]]:
    """Check if mission has any open WPs. Returns non-empty list if not completed."""
    TERMINAL = TERMINAL_LANES  # frozenset{"done", "canceled"}

    # FR-006 (#1735): peek at the canonical status surface (coord-aware), not the
    # primary-checkout feature dir, so completion checks see coord-owned events.
    events_path = _canonical_events_path(_repo_root, resolved.mission_slug)
    feature_dir = events_path.parent
    if not feature_dir.exists():
        return []

    try:
        events = read_events(feature_dir)
    except Exception:
        return []

    if not events:
        return []

    # Build per-WP lane snapshot from events
    from specify_cli.status import reduce as reduce_events
    snapshot = reduce_events(events)

    open_wps: list[dict[str, str]] = []
    for wp_id, wp_state in snapshot.work_packages.items():
        lane = str(wp_state.get("lane", ""))
        if lane not in TERMINAL:
            open_wps.append({"wp_id": wp_id, "lane": lane})

    return open_wps


def _policy_source_dict(policy_source: dict[str, str]) -> dict[str, str]:
    """Return a policy_source dict suitable for JSON output."""
    return {
        "enabled": policy_source.get("enabled", "<default>"),
        "timing": policy_source.get("timing", "<default>"),
        "failure_policy": policy_source.get("failure_policy", "<default>"),
    }


def _auto_commit_failure_detail(exc: Exception) -> str:
    """Return the most useful one-line reason for a failed auto-commit.

    A failed ``git`` call carries git's own message (e.g. ``fatal: ... is
    outside repository``, a hook's rejection) on stderr, or on stdout for
    ``git commit`` refusals such as "nothing to commit"; anything else falls
    back to the exception text.
    """
    if isinstance(exc, subprocess.CalledProcessError):
        for raw in (exc.stderr, exc.stdout):
            text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw or "")
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            if lines:
                return " ".join(lines)
        return f"`{' '.join(str(arg) for arg in exc.cmd)}` exited {exc.returncode}"
    return str(exc) or type(exc).__name__


def _warn_auto_commit_failed(files: list[Path], exc: Exception) -> None:
    """Tell the operator, on stderr, that the auto-commit did not happen.

    Non-fatal by design (the record write already succeeded), but never
    silent: without this the record stays uncommitted and nothing says so.
    Printed to stderr so ``--json`` stdout stays machine-parseable.
    """
    paths = " ".join(str(f) for f in files)
    _err_console.print(
        f"[yellow]Warning:[/yellow] retrospective auto-commit failed: "
        f"{escape(_auto_commit_failure_detail(exc))}. "
        f"The record is written but not committed; commit it by hand: {escape(paths)}",
        soft_wrap=True,
    )


def _warn_protected_target_refused(target: str, files: list[Path]) -> None:
    """Tell the operator, on stderr, that the protected target branch refused the commit.

    Non-fatal: the record and its events are on disk. The mission commit router
    refuses a STANDARD commit onto a protected branch, and the retrospect CLI holds
    no protected-flow capability, so the operator commits from a branch that may
    take it. The hint names a feature branch and never the mission branch: on a
    coordination-topology Mission the only ``kitty/mission-*`` branch is the
    coordination branch, which must never carry the PRIMARY-partition record.
    """
    paths = " ".join(str(f) for f in files)
    _err_console.print(
        f"[yellow]Warning:[/yellow] retrospective auto-commit skipped: the mission's "
        f"target branch '{escape(target)}' is protected, so nothing was committed to it. "
        f"The record is written but not committed; commit it from a feature branch "
        f"(never the coordination branch) and land it through a pull request: {escape(paths)}",
        soft_wrap=True,
    )


def _refused_on_protected_target(repo_root: Path, mission_slug: str, result: CommitRouterResult) -> bool:
    """True when the router refused *result* because the mission's target branch is protected."""
    return result.status == "no_op_wrong_surface" and ProtectionPolicy.resolve_for_mission(repo_root, mission_slug).is_protected(result.placement_ref)


def _uncommitted_target_files(repo_root: Path, mission_slug: str, files: list[Path]) -> list[Path]:
    """The *files* bound for the mission's target branch that still differ from ``HEAD``.

    Coordination residue (the coordination branch's own event log) is left out:
    the router commits it on the coordination branch even when it refuses the
    protected target.
    """
    topology = resolve_topology(repo_root, mission_slug)
    targeted = [f for f in files if not is_coord_residue_churn(f, mission_slug=mission_slug, topology=topology)]
    if not targeted:
        return []
    entries = status_entries(repo_root, pathspecs=tuple(str(f) for f in targeted), untracked="all")
    return targeted if entries else []


def _maybe_auto_commit(
    repo_root: Path,
    mission_slug: str,
    files: list[Path],
    message: str,
) -> None:
    """Auto-commit *files* for *mission_slug* if auto_commit is enabled in config.

    The commit goes through the canonical STANDARD mission commit router as a
    ``RETROSPECTIVE`` artifact. The router is the one authority that splits the
    batch by partition: the record lands on the mission's target branch, and on a
    coordination-topology mission the canonical event log lands on the
    coordination branch. A protected target branch is refused, and that refusal
    is a warning, not a failure (silent when those files are already committed).
    Any other failure is non-fatal too (the record
    is already on disk) but is surfaced as a stderr warning naming the cause, so
    the operator can commit by hand; "nothing to commit" stays silent.
    """
    try:
        if not get_auto_commit_default(repo_root):
            return
        result = commit_for_mission(
            repo_root,
            mission_slug,
            tuple(files),
            message,
            ProtectionPolicy.resolve(repo_root),
            kind=MissionArtifactKind.RETROSPECTIVE,
        )
        if _refused_on_protected_target(repo_root, mission_slug, result):
            uncommitted = _uncommitted_target_files(repo_root, mission_slug, files)
            if uncommitted:
                _warn_protected_target_refused(result.placement_ref, uncommitted)
        elif result.status in ("error", "no_op_wrong_surface"):
            _warn_auto_commit_failed(files, RuntimeError(result.diagnostic or result.status))
    except Exception as exc:
        # Non-fatal (the record write already succeeded), but never silent.
        _warn_auto_commit_failed(files, exc)


# ---------------------------------------------------------------------------
# create command
# ---------------------------------------------------------------------------


@app.command(
    "create",
    help=(
        "Author a retrospective for one completed mission.\n\n"
        "Validates mission completion, resolves policy, runs the generator,\n"
        "and writes the record. Use --overwrite or --update to handle existing records."
    ),
)
def create_cmd(
    mission: Annotated[
        str,
        typer.Option("--mission", help="Mission handle (mission_id, mid8, or mission_slug)"),
    ],
    overwrite: Annotated[
        bool,
        typer.Option("--overwrite", help="Replace an existing record (mutually exclusive with --update)"),
    ] = False,
    update: Annotated[
        bool,
        typer.Option("--update", help="Merge into an existing record (mutually exclusive with --overwrite)"),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit structured JSON output instead of Rich rendering"),
    ] = False,
) -> None:
    """Author a retrospective for one completed mission."""
    if overwrite and update:
        _err_console.print(
            "[red]Error:[/red] --overwrite and --update are mutually exclusive. "
            "Pass exactly one."
        )
        raise typer.BadParameter("--overwrite and --update are mutually exclusive")

    # Locate project root
    repo_root = locate_project_root()
    if repo_root is None:
        _err_console.print(
            "[red]Error:[/red] Could not locate project root. "
            "Ensure you are inside a spec-kitty project."
        )
        raise typer.Exit(1)

    # Resolve mission handle
    resolved = _resolve_handle(mission, repo_root, json_output=json_output)

    # Check mission completion state
    open_wps = _check_mission_completed(resolved, repo_root)
    if open_wps:
        open_str = ", ".join(f"{w['wp_id']} ({w['lane']})" for w in open_wps)
        if json_output:
            _console.print_json(
                json.dumps({
                    "result": "blocked",
                    "code": "MISSION_NOT_COMPLETED",
                    "mission_id": resolved.mission_id,
                    "mission_slug": resolved.mission_slug,
                    "blocked_reason": (
                        f"Mission has WPs in non-terminal lanes: {open_str}. "
                        "Complete the mission before authoring a retrospective."
                    ),
                    "open_wps": open_wps,
                    "exit_code": 1,
                })
            )
        else:
            _err_console.print(
                f"[red]Error MISSION_NOT_COMPLETED:[/red] "
                f"Mission has WPs in non-terminal lanes: {open_str}. "
                "Complete the mission before authoring a retrospective."
            )
        raise typer.Exit(1)

    # Resolve policy
    try:
        policy, source_map = resolve_policy(repo_root)
    except PolicyResolutionError as exc:
        if json_output:
            _console.print_json(
                json.dumps({
                    "result": "blocked",
                    "code": "POLICY_RESOLUTION_ERROR",
                    "mission_id": resolved.mission_id,
                    "mission_slug": resolved.mission_slug,
                    "blocked_reason": str(exc),
                    "exit_code": 1,
                })
            )
        else:
            _err_console.print(f"[red]Error POLICY_RESOLUTION_ERROR:[/red] {exc}")
        raise typer.Exit(1) from exc

    # Determine write mode
    if overwrite:
        write_mode: Literal["error", "overwrite", "update"] = "overwrite"
    elif update:
        write_mode = "update"
    else:
        write_mode = "error"
    provenance_kind: ProvenanceKind = "explicit_create"

    # Generate the record
    try:
        record = generate_retrospective(
            resolved.mission_slug,
            policy,
            repo_root,
            provenance_kind=provenance_kind,
            actor=_gen_actor(),
            policy_source=source_map,
        )
    except FileNotFoundError as exc:
        _err_console.print(f"[red]Error:[/red] Could not find mission artifacts: {exc}")
        raise typer.Exit(1) from exc
    except Exception as exc:
        _err_console.print(f"[red]Error:[/red] Generator failed: {exc}")
        raise typer.Exit(1) from exc

    # Override provenance with explicit_create
    import dataclasses
    record = dataclasses.replace(
        record,
        provenance=GenProvenance(
            kind="explicit_create",
            invoked_at=record.provenance.invoked_at,
            policy_resolved_from=record.provenance.policy_resolved_from,
            command="spec-kitty retrospect create",
        ),
    )

    # Write the record
    try:
        record_path = write_gen_record(record, mode=write_mode, repo_root=repo_root)
    except RecordExistsError as exc:
        if json_output:
            _console.print_json(
                json.dumps({
                    "result": "blocked",
                    "code": "RETROSPECTIVE_RECORD_EXISTS",
                    "mission_id": resolved.mission_id,
                    "mission_slug": resolved.mission_slug,
                    "record_path": str(exc.path),
                    "blocked_reason": (
                        "A retrospective record already exists for this mission. "
                        "Pass --overwrite to replace it or --update to merge."
                    ),
                    "exit_code": 1,
                })
            )
        else:
            _err_console.print(
                f"[red]Error RETROSPECTIVE_RECORD_EXISTS:[/red] "
                f"A retrospective record already exists at {exc.path}. "
                "Pass --overwrite to replace it or --update to merge."
            )
        raise typer.Exit(1) from exc
    except Exception as exc:
        _err_console.print(f"[red]Error:[/red] Failed to write record: {exc}")
        raise typer.Exit(1) from exc

    # Read back the persisted record: write_gen_record(mode="update") merges
    # the freshly-generated record with the existing on-disk record and
    # recomputes findings_status from the union, but only returns a Path
    # (C-002). Reporting/emitting must reflect what is ACTUALLY on disk, not
    # the pre-merge `record` (#3320). This read-back is a no-op for
    # --overwrite / mode="error" / backfill, where persisted == new.
    persisted = read_gen_record(record_path)

    # FR-006 (#1735/#1771): the event is appended to, and committed from, the
    # ONE canonical status surface (coord-aware), never a primary-only copy.
    events_path = _canonical_events_path(repo_root, persisted.mission_slug)

    # Emit lifecycle event (non-fatal — record write already succeeded)
    with contextlib.suppress(Exception):
        emit_captured(
            persisted,
            repo_root,
            provenance_kind="explicit_create",
            actor=_cli_actor(),
            event_log_dir=events_path.parent,
        )

    # Auto-commit if enabled, through the mission commit router.
    _maybe_auto_commit(
        repo_root,
        persisted.mission_slug,
        [path for path in (record_path, events_path) if path.exists()],
        f"chore(retrospective): author retrospective for {persisted.mission_slug}",
    )

    # Build output
    policy_source_out = _policy_source_dict(source_map)
    counts = {
        "helped": len(persisted.helped),
        "not_helpful": len(persisted.not_helpful),
        "gaps": len(persisted.gaps),
        "proposals": len(persisted.proposals),
        "evidence_refs": len(persisted.evidence_refs),
    }
    next_step = (
        f"Run `spec-kitty agent retrospect synthesize --mission {resolved.mission_slug}` "
        "to review proposals (dry-run by default; add --apply to mutate)."
    )

    if json_output:
        _console.print_json(
            json.dumps({
                "result": "success",
                "mission_id": resolved.mission_id,
                "mission_slug": resolved.mission_slug,
                "record_path": str(record_path),
                "findings_status": persisted.findings_status,
                "counts": counts,
                "provenance_kind": "explicit_create",
                "policy_source": policy_source_out,
                "next_step": next_step,
            })
        )
    else:
        _console.print(
            Panel(
                f"[bold green]Retrospective authored[/bold green]\n\n"
                f"[bold]Mission:[/bold] {resolved.mission_slug}\n"
                f"[bold]Record path:[/bold] {record_path}\n"
                f"[bold]Findings status:[/bold] {persisted.findings_status}\n"
                f"[bold]Counts:[/bold] "
                f"helped={counts['helped']} not_helpful={counts['not_helpful']} "
                f"gaps={counts['gaps']} proposals={counts['proposals']}\n\n"
                f"[dim]{next_step}[/dim]",
                title="spec-kitty retrospect create",
                expand=False,
            )
        )

    raise typer.Exit(0)


# ---------------------------------------------------------------------------
# backfill command
# ---------------------------------------------------------------------------


def _parse_iso_date_or_exit(value: str, flag_name: str) -> datetime:
    """Parse an ISO date/datetime string; raise BadParameter on failure."""
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            dt = parse_stamp(value, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt
        except ValueError:
            continue
    # Try stdlib fromisoformat
    try:
        dt = parse_iso(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except ValueError:
        pass
    raise typer.BadParameter(
        f"Invalid {flag_name} value {value!r}. "
        "Expected ISO-8601 date (YYYY-MM-DD) or datetime."
    )


def _discover_missions_for_backfill(
    repo_root: Path,
    since: datetime,
    until: datetime,
    mission_filter: str | None,
) -> list[dict[str, object]]:
    """Discover completed missions in the given window for backfill.

    Returns a list of candidate dicts with keys:
        mission_id, mission_slug, completed_at, meta_path
    """
    candidates: list[dict[str, object]] = []
    missions_root = repo_root / KITTIFY_DIR / "missions"

    if not safe_is_dir(missions_root):
        return candidates

    for entry in sorted(missions_root.iterdir()):
        if not safe_is_dir(entry):
            continue

        meta_path = entry / "meta.json"
        meta = load_meta_or_empty(entry)
        if not meta:
            continue

        mission_id = meta.get("mission_id")
        mission_slug = meta.get("mission_slug") or meta.get("slug")
        if not mission_id or not mission_slug:
            continue

        # mission_filter: skip if filter is set and this mission doesn't match
        if mission_filter is not None and (
            mission_id != mission_filter
            and not mission_id.startswith(mission_filter)
            and mission_slug != mission_filter
        ):
            candidates.append({
                "mission_id": mission_id,
                "mission_slug": mission_slug,
                "skip_reason": "mission_filter_excluded",
                "meta_path": str(meta_path),
            })
            continue

        # Get completed_at timestamp
        completed_at_str = meta.get("completed_at") or meta.get("mission_completed_at")
        if not completed_at_str:
            candidates.append({
                "mission_id": mission_id,
                "mission_slug": mission_slug,
                "skip_reason": "not_completed",
                "meta_path": str(meta_path),
            })
            continue

        try:
            completed_at = parse_iso(completed_at_str)
            if completed_at.tzinfo is None:
                completed_at = completed_at.replace(tzinfo=UTC)
        except ValueError:
            candidates.append({
                "mission_id": mission_id,
                "mission_slug": mission_slug,
                "skip_reason": "not_completed",
                "meta_path": str(meta_path),
            })
            continue

        # Check window
        if completed_at < since or completed_at > until:
            candidates.append({
                "mission_id": mission_id,
                "mission_slug": mission_slug,
                "completed_at": completed_at_str,
                "skip_reason": "out_of_window",
                "meta_path": str(meta_path),
            })
            continue

        candidates.append({
            "mission_id": mission_id,
            "mission_slug": mission_slug,
            "completed_at": completed_at_str,
            "meta_path": str(meta_path),
        })

    return candidates


def _auto_commit_backfilled(repo_root: Path, created: list[dict[str, object]]) -> None:
    """Auto-commit each backfilled mission's record and canonical event log, one mission at a time.

    FR-006 (#1735/#1771): the event log is the canonical status surface
    (coord-aware); the mission commit router lands it on the coordination branch
    of a coordination-topology mission, and the record on the target branch.
    """
    for entry in created:
        mslug = str(entry["mission_slug"])
        events_path = _canonical_events_path(repo_root, mslug)
        files = [Path(str(entry["record_path"]))]
        if events_path.exists():
            files.append(events_path)
        _maybe_auto_commit(
            repo_root,
            mslug,
            files,
            f"chore(retrospective): backfill retrospective for {mslug}",
        )


@app.command(
    "backfill",
    help=(
        "Author retrospective records for historical missions in bulk.\n\n"
        "Iterates completed missions in the given time window and authors\n"
        "retrospective.yaml records for those that don't already have one.\n\n"
        "Per-mission failures are NOT fatal; aggregate report shows them."
    ),
)
def backfill_cmd(  # noqa: C901
    since: Annotated[
        str | None,
        typer.Option("--since", help="Only consider missions completed on or after this ISO date (default: 30 days ago)"),
    ] = None,
    until: Annotated[
        str | None,
        typer.Option("--until", help="Only consider missions completed on or before this ISO date (default: now)"),
    ] = None,
    mission: Annotated[
        str | None,
        typer.Option("--mission", help="Restrict backfill to a single mission handle"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Report what would be authored without writing"),
    ] = False,
    emit_skipped: Annotated[
        bool,
        typer.Option("--emit-skipped", help="Append a RetrospectiveSkipped event for skipped missions"),
    ] = False,
    emit_failures: Annotated[
        bool,
        typer.Option("--emit-failures", help="Append RetrospectiveCaptureFailed events for failed missions"),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit a single aggregate JSON object at the end"),
    ] = False,
) -> None:
    """Author retrospective records for historical missions in bulk."""
    # Parse window
    now = now_utc()
    default_since = now - timedelta(days=30)

    since_dt: datetime = _parse_iso_date_or_exit(since, "--since") if since else default_since
    until_dt: datetime = _parse_iso_date_or_exit(until, "--until") if until else now

    # Locate project root
    repo_root = locate_project_root()
    if repo_root is None:
        _err_console.print(
            "[red]Error:[/red] Could not locate project root. "
            "Ensure you are inside a spec-kitty project."
        )
        raise typer.Exit(1)

    # Discover missions
    candidates = _discover_missions_for_backfill(repo_root, since_dt, until_dt, mission)

    window_out = {
        "since": since_dt.date().isoformat(),
        "until": until_dt.date().isoformat(),
    }

    # Separate pre-screened skips from candidates that need processing
    skipped: list[dict[str, object]] = []
    failed: list[dict[str, object]] = []
    created: list[dict[str, object]] = []
    created_paths: list[Path] = []

    def _maybe_emit_skip(mission_id: str, mission_slug: str, reason: str) -> None:
        """Emit a RetrospectiveSkipped event when --emit-skipped is set and not dry_run."""
        if not emit_skipped or dry_run:
            return
        with contextlib.suppress(Exception):
            _emit_retro_skipped(
                mission_id,
                mission_slug,
                repo_root,
                skip_reason=f"backfill_skip: {reason}",
                skip_reason_source="cli_flag",
                policy_source={},
                actor=_cli_actor(),
                event_log_dir=_canonical_events_path(repo_root, mission_slug).parent,
            )

    work_candidates = []
    for c in candidates:
        if "skip_reason" in c:
            skip_entry: dict[str, object] = {
                "mission_id": c["mission_id"],
                "mission_slug": c["mission_slug"],
                "reason": c["skip_reason"],
            }
            if c.get("skip_reason") == "already_exists":
                skip_entry["record_path"] = str(
                    _canonical_record_path(
                        repo_root, str(c["mission_slug"]), str(c["mission_id"])
                    )
                )
            skipped.append(skip_entry)
            _maybe_emit_skip(str(c["mission_id"]), str(c["mission_slug"]), str(c["skip_reason"]))
        else:
            work_candidates.append(c)

    # Process each work candidate
    def _process_candidate(c: dict[str, object]) -> None:
        mid = str(c["mission_id"])
        mslug = str(c["mission_slug"])
        record_path = _canonical_record_path(repo_root, mslug, mid)

        # Already exists?
        if record_path.exists():
            skipped.append({
                "mission_id": mid,
                "mission_slug": mslug,
                "reason": "already_exists",
                "record_path": str(record_path),
            })
            _maybe_emit_skip(mid, mslug, "already_exists")
            return

        if dry_run:
            created.append({"mission_id": mid, "mission_slug": mslug, "dry_run": True})
            return

        # Generate and write
        try:
            policy, source_map = resolve_policy(repo_root)
            record = generate_retrospective(
                mslug,
                policy,
                repo_root,
                provenance_kind="backfill",
                actor=_gen_actor(),
                policy_source=source_map,
            )
            import dataclasses
            record = dataclasses.replace(
                record,
                provenance=GenProvenance(
                    kind="backfill",
                    invoked_at=record.provenance.invoked_at,
                    policy_resolved_from=record.provenance.policy_resolved_from,
                    command="spec-kitty retrospect backfill",
                ),
            )
            written_path = write_gen_record(record, mode="error", repo_root=repo_root)
            emit_captured(
                record,
                repo_root,
                provenance_kind="backfill",
                actor=_cli_actor(),
                event_log_dir=_canonical_events_path(repo_root, mslug).parent,
            )
            created.append({
                "mission_id": mid,
                "mission_slug": mslug,
                "record_path": str(written_path),
            })
            created_paths.append(written_path)
        except RecordExistsError as exc:
            skipped.append({
                "mission_id": mid,
                "mission_slug": mslug,
                "reason": "already_exists",
                "record_path": str(exc.path),
            })
        except FileNotFoundError as exc:
            remediation = (
                f"Mission lacks required artifacts; rebuild via "
                f"`spec-kitty migrate normalize-lifecycle --mission {mslug}`."
            )
            failed_entry: dict[str, object] = {
                "mission_id": mid,
                "mission_slug": mslug,
                "failure_category": "missing_artifacts",
                "missing": [str(exc)],
                "remediation_hint": remediation,
            }
            failed.append(failed_entry)
            if emit_failures:
                with contextlib.suppress(Exception):
                    emit_capture_failed(
                        mid,
                        mslug,
                        repo_root,
                        failure_category="missing_artifacts",
                        failure_message=str(exc),
                        remediation_hint=remediation,
                        policy_source={},
                        attempted_provenance_kind="backfill",
                        missing_artifacts=[str(exc)],
                        actor=_cli_actor(),
                        event_log_dir=_canonical_events_path(repo_root, mslug).parent,
                    )
        except Exception as exc:
            failed_entry = {
                "mission_id": mid,
                "mission_slug": mslug,
                "failure_category": "generator_exception",
                "missing": [],
                "remediation_hint": str(exc),
            }
            failed.append(failed_entry)
            if emit_failures:
                with contextlib.suppress(Exception):
                    emit_capture_failed(
                        mid,
                        mslug,
                        repo_root,
                        failure_category="generator_exception",
                        failure_message=str(exc),
                        remediation_hint=None,
                        policy_source={},
                        attempted_provenance_kind="backfill",
                        missing_artifacts=None,
                        actor=_cli_actor(),
                        event_log_dir=_canonical_events_path(repo_root, mslug).parent,
                    )

    if json_output:
        for c in work_candidates:
            _process_candidate(c)
    else:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            task = progress.add_task("Processing missions...", total=len(work_candidates))
            for c in work_candidates:
                mslug = str(c.get("mission_slug", ""))
                progress.update(task, description=f"Processing {mslug}...")
                _process_candidate(c)
                progress.advance(task)

    # Auto-commit created records, one mission at a time, through the mission
    # commit router.
    if created_paths and not dry_run:
        _auto_commit_backfilled(repo_root, created)

    # Compute next actions
    next_actions: list[str] = []
    if created and not dry_run:
        next_actions.append(
            "Run `spec-kitty agent retrospect synthesize --mission <handle>` "
            "on newly authored records (dry-run by default; add --apply to mutate)."
        )
    if failed:
        next_actions.append(f"Inspect the {len(failed)} failed mission(s) listed above.")

    total_scanned = len(candidates)
    result_data: dict[str, object] = {
        "result": "success",
        "window": window_out,
        "scanned": total_scanned,
        "created": len(created),
        "skipped": skipped,
        "failed": failed,
        "next_actions": next_actions,
    }

    if json_output:
        _console.print_json(json.dumps(result_data))
    else:
        _console.print(
            Panel(
                f"[bold]Backfill complete[/bold]\n\n"
                f"Window: {window_out['since']} to {window_out['until']}\n"
                f"Scanned: {total_scanned} | "
                f"Created: {len(created)} | "
                f"Skipped: {len(skipped)} | "
                f"Failed: {len(failed)}"
                + (" [yellow](dry-run — no files written)[/yellow]" if dry_run else ""),
                title="spec-kitty retrospect backfill",
                expand=False,
            )
        )
        if failed:
            _err_console.print(f"\n[yellow]Failures ({len(failed)}):[/yellow]")
            for f_entry in failed:
                _err_console.print(
                    f"  [red]{f_entry['mission_slug']}[/red]: "
                    f"{f_entry['failure_category']} — {f_entry.get('remediation_hint', '')}"
                )

    raise typer.Exit(0)


# ---------------------------------------------------------------------------
# summary command — re-exported from retrospective.cli with 4-state extension
# ---------------------------------------------------------------------------


@app.command(
    "summary",
    help=(
        "Cross-mission retrospective summary.\n\n"
        "Reads kitty-specs/*/retrospective.yaml and "
        "kitty-specs/*/status.events.jsonl to produce a cross-mission view.\n\n"
        "Distinguishes four record states: has_findings / ran_no_findings / missing / failed.\n\n"
        "No mutation is performed."
    ),
)
def summary_cmd(  # noqa: C901
    project: Annotated[
        Path | None,
        typer.Option("--project", help="Project root (default: current working directory)"),
    ] = None,
    json_only: Annotated[
        bool,
        typer.Option("--json", help="Emit JSON to stdout instead of Rich rendering"),
    ] = False,
    json_out: Annotated[
        Path | None,
        typer.Option("--json-out", help="Also write JSON to this file path"),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", min=1, max=100, help="Top-N for ranked sections (default: 20)"),
    ] = 20,
    since: Annotated[
        str | None,
        typer.Option("--since", help="ISO-8601 date; only include missions started on or after DATE"),
    ] = None,
    include_malformed: Annotated[
        bool,
        typer.Option("--include-malformed", help="Include malformed record detail in output"),
    ] = False,
    filter_state: Annotated[
        str | None,
        typer.Option(
            "--filter",
            help="Only show missions in this record state (has_findings|ran_no_findings|missing|failed)",
        ),
    ] = None,
) -> None:
    """Cross-mission retrospective summary with 4-state record classification.

    READ-ONLY: no filesystem mutation is performed.
    """
    from kernel.clock import date as date_type
    from specify_cli.retrospective.cli import (
        _build_json_envelope as _base_json_envelope,
        _render_rich as _base_render_rich,
    )
    from specify_cli.retrospective.summary import build_summary

    # Resolve project root
    resolved_project: Path = project.resolve() if project is not None else Path.cwd()

    has_kittify = (resolved_project / KITTIFY_DIR).exists()
    has_mission_specs = (resolved_project / KITTY_SPECS_DIR).exists()
    if not has_kittify and not has_mission_specs:
        _err_console.print(
            "[red]Error:[/red] Project root invalid: "
            f"neither .kittify/ nor kitty-specs/ found in {resolved_project}"
        )
        raise typer.Exit(1)

    # Parse --since
    since_date: date_type | None = None
    if since is not None:
        try:
            since_date = date_type.fromisoformat(since)
        except ValueError as exc:
            _err_console.print(
                f"[red]Error:[/red] Invalid --since date {since!r}. "
                "Expected ISO-8601 format (YYYY-MM-DD)."
            )
            raise typer.Exit(1) from exc

    # Validate --filter state
    valid_states = {"has_findings", "ran_no_findings", "missing", "failed"}
    if filter_state is not None and filter_state not in valid_states:
        _err_console.print(
            f"[red]Error:[/red] Invalid --filter value {filter_state!r}. "
            f"Must be one of: {', '.join(sorted(valid_states))}"
        )
        raise typer.Exit(1)

    try:
        snapshot = build_summary(
            project_path=resolved_project,
            since=since_date,
            limit_top_n=limit,
        )
    except OSError as exc:
        _err_console.print(f"[red]Error:[/red] I/O error reading corpus: {exc}")
        raise typer.Exit(2) from exc

    # Build per-mission 4-state classification
    missions_with_state: list[dict[str, object]] = []
    aggregate_counts: dict[str, int] = {
        "has_findings": 0,
        "ran_no_findings": 0,
        "missing": 0,
        "failed": 0,
    }

    # FR-013 (#2717): anchor per-mission discovery on the canonical
    # ``kitty-specs/*`` instance home via the shared iterator, not the
    # ``.kittify/missions/`` support/registry root (which omits real records).
    for mission_dir in iter_mission_instance_dirs(resolved_project):
        meta = load_meta_or_empty(mission_dir)
        mission_id = meta.get("mission_id")
        mission_slug = meta.get("mission_slug") or meta.get("slug")

        # mission_dir is already the canonical kitty-specs home; keep the
        # topology-aware resolver for slugs whose dir name differs.
        feature_dir_for_classify: Path = mission_dir
        if mission_slug:
            kitty_dir = candidate_feature_dir_for_mission(resolved_project, mission_slug)
            if safe_is_dir(kitty_dir):
                feature_dir_for_classify = kitty_dir

        state = classify_mission_record(feature_dir_for_classify)

        # Back-compat: legacy in-registry record keyed by mission_id.
        if state == "missing" and mission_id:
            registry_dir = legacy_registry_record_dir(resolved_project, mission_id)
            if (registry_dir / RETROSPECTIVE_FILENAME).exists():
                state = classify_mission_record(registry_dir)

        aggregate_counts[state] = aggregate_counts.get(state, 0) + 1

        # Get policy_source from most recent Captured event in event log
        policy_source_snap: dict[str, object] | None = None
        events_path = feature_dir_for_classify / "status.events.jsonl"
        if events_path.exists():
            try:
                best_captured = None
                best_lp = -1
                for raw in events_path.read_text(encoding="utf-8").splitlines():
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        obj = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if obj.get("type") == "RetrospectiveCaptured":
                        lp = obj.get("lamport", 0)
                        if isinstance(lp, int) and lp >= best_lp:
                            best_captured = obj
                            best_lp = lp
                if best_captured:
                    ps = best_captured.get("policy_source", {})
                    if isinstance(ps, dict):
                        policy_source_snap = ps
            except Exception:
                pass

        mission_entry: dict[str, object] = {
            "mission_id": mission_id or mission_dir.name,
            "mission_slug": mission_slug or "",
            "findings_status": state,
            "policy_source": policy_source_snap,
        }

        if filter_state is None or state == filter_state:
            missions_with_state.append(mission_entry)

    # Build extended JSON envelope
    base_envelope = _base_json_envelope(snapshot)
    extended_envelope: dict[str, object] = {
        **base_envelope,
        "missions": missions_with_state,
        "aggregate": aggregate_counts,
    }
    if filter_state is not None:
        extended_envelope["filter"] = filter_state

    if json_only:
        _console.print_json(json.dumps(extended_envelope))
    else:
        _base_render_rich(snapshot, include_malformed=include_malformed)
        # Show 4-state aggregate
        from rich.table import Table
        state_table = Table(title="Record State Summary (4-state)", show_header=True, header_style="bold cyan")
        state_table.add_column("State")
        state_table.add_column("Count", justify="right")
        for state_name, count in aggregate_counts.items():
            state_table.add_row(state_name, str(count))
        _console.print(state_table)

    if json_out is not None:
        try:
            json_out.parent.mkdir(parents=True, exist_ok=True)
            json_out.write_text(json.dumps(extended_envelope, indent=2), encoding="utf-8")
            if not json_only:
                _console.print(f"\n[dim]JSON written to {json_out}[/dim]")
        except OSError as exc:
            _err_console.print(f"[red]Error:[/red] Could not write JSON to {json_out}: {exc}")
            raise typer.Exit(2) from exc

    raise typer.Exit(0)


__all__ = ["app", "summary_cmd"]
