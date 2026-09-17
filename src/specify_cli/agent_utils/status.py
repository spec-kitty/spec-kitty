"""Status board utilities for AI agents.

This module provides functions that agents can import and call directly
to display beautiful status boards without going through the CLI.
"""

from __future__ import annotations

from mission_runtime import MissionArtifactKind, placement_seam
from collections import Counter
from kernel.clock import datetime, now_utc, parse_iso
from pathlib import Path

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from specify_cli.cli.console import CliConsole
from specify_cli.core.paths import (
    get_main_repo_root,  # noqa: F401 — re-exported for test patching (see tests/agent/test_agent_utils_status.py and tests/contract/test_machine_facing_canonical_fields.py)
    get_status_read_root,
    locate_project_root,
)
from specify_cli.mission_metadata import resolve_mission_identity
from specify_cli.status import Lane, NON_DISPLAY_LANES, StatusEvent
from specify_cli.status import PROGRESS_SEMANTICS, compute_done_percentage, compute_weighted_progress
from specify_cli.status import event_sourced_review_result, is_changes_requested, wp_state_for
from specify_cli.task_utils import extract_scalar, split_frontmatter

console = CliConsole()

# WP05 (verdict-seam-write-unification-01KZ9Q35, FR-002/FR-004/T024): the
# board's stale/damaged-verdict detection used to glob ``review-cycle-*.md``
# and parse its YAML frontmatter directly (``_get_wp_review_verdict`` +
# ``DamagedVerdictRecordError``, both retired) -- the exact fail-open surface
# this mission closes. The loop inside :func:`show_kanban_status` now resolves
# :func:`~specify_cli.status.event_sourced_review_result` instead; see that
# loop for the three-way (absent/damaged/present) translation.


def _get_last_event_time(events: list[StatusEvent], wp_id: str) -> datetime | None:
    """Return the ``at`` datetime of the most recent event for wp_id, or None."""
    wp_events = [e for e in events if e.wp_id == wp_id]
    if not wp_events:
        return None
    latest = max(wp_events, key=lambda e: e.at)
    at_str = latest.at
    if not at_str:
        return None
    try:
        return parse_iso(at_str)
    except ValueError:
        return None


def show_kanban_status(mission_slug: str | None = None) -> dict:
    """Render the agent status board, retaining the public display API."""
    try:
        data = build_kanban_status(mission_slug)
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        return {"error": str(exc)}
    if not data["work_packages"]:
        console.print("[yellow]No work packages found[/yellow]")
        return data
    by_lane = {lane: [] for lane in Lane if lane not in NON_DISPLAY_LANES}
    for wp in data["work_packages"]:
        if wp["lane"] in by_lane:
            by_lane[wp["lane"]].append(wp)
    _display_status_board(data["mission_slug"], data["work_packages"], by_lane,
                          data["total_wps"], data["done_count"], data["in_progress_count"],
                          data["planned_count"], data["done_percentage"], data["progress_percentage"],
                          data["parallelization"])
    return data


def build_kanban_status(mission_slug: str | None = None) -> dict:
    """Build status data without rendering; genuine input errors raise to the caller."""
    cwd = Path.cwd().resolve()
    repo_root = locate_project_root(cwd)

    if repo_root is None:
        raise ValueError("Not in a spec-kitty project")

    # mission_slug is required; no auto-detection
    if not mission_slug:
        msg = (
            "mission_slug is required. "
            "Pass it explicitly: show_kanban_status('057-my-feature')"
        )
        raise ValueError(msg)

    # Read-only path: use worktree-aware resolution so detached-worktree
    # verification (#984) reads the current worktree's events, not the
    # primary checkout's potentially-divergent state.
    main_repo_root = get_status_read_root()

    # STATUS leg (C-001 / NFR-001): the append-only event log stays
    # coord-aware so the kanban lanes reflect the worktree-local log.
    # read-surface-ssot-closeout WP08 / FR-001 / NFR-001: routed through the
    # kind-aware placement seam instead of the kind-blind
    # resolve_feature_dir_for_mission (same coord-aware STATUS_STATE resolution).
    feature_dir = placement_seam(main_repo_root, mission_slug).read_dir(
        MissionArtifactKind.STATUS_STATE
    )

    if not feature_dir.exists():
        raise FileNotFoundError(f"Feature directory not found: {feature_dir}")

    # PRIMARY leg: the WP*.md frontmatter glob (#2187, WORK_PACKAGE_TASK) and
    # the mission identity (#2186, PRIMARY_METADATA) live ONLY on the PRIMARY
    # checkout post-#2106 — the coord husk carries neither. Both PRIMARY-kinds
    # resolve topology-blind to the same PRIMARY dir via the kind-aware seam.
    # read-side-placement-seam-migration WP07: names WORK_PACKAGE_TASK
    # through the seam authority instead of the kind-blind
    # ``resolve_planning_read_dir`` — behavior-identical here since
    # WORK_PACKAGE_TASK is PRIMARY-partition (no fail-loud arm reachable).
    primary_dir = placement_seam(main_repo_root, mission_slug).read_dir(
        MissionArtifactKind.WORK_PACKAGE_TASK
    )

    tasks_dir = primary_dir / "tasks"

    if not tasks_dir.exists():
        raise FileNotFoundError(f"Tasks directory not found: {tasks_dir}")

    identity = resolve_mission_identity(primary_dir)

    # Load project config for stall threshold
    config_file = main_repo_root / ".kittify" / "config.yaml"
    config: dict = {}
    if config_file.exists():
        try:
            import yaml as _yaml  # noqa: PLC0415
            config = _yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001
            config = {}
    threshold_minutes: int = (
        int(config.get("review", {}).get("stall_threshold_minutes", 30))
        if isinstance(config, dict)
        else 30
    )

    # Build lane map from event log (canonical source of truth)
    from specify_cli.status import reduce, read_events  # noqa: PLC0415
    events = read_events(feature_dir)
    snapshot = reduce(events)
    # snapshot.work_packages: {wp_id: {"lane": ..., ...}}
    event_log_lanes: dict[str, Lane] = {
        wp_id: Lane(state.get("lane", Lane.GENESIS))
        for wp_id, state in snapshot.work_packages.items()
    }

    # Collect all work packages with dependencies (static metadata from frontmatter)
    import re
    work_packages = []
    for wp_file in sorted(tasks_dir.glob("WP*.md")):
        front, body, padding = split_frontmatter(wp_file.read_text(encoding="utf-8-sig"))

        wp_id = extract_scalar(front, "work_package_id")
        title = extract_scalar(front, "title")
        phase = extract_scalar(front, "phase") or "Unknown Phase"

        # Lane comes from event log; default to Lane.GENESIS for unseeded WPs
        # (WPs not yet in the log have not been through finalize-tasks).
        # Contract 3 (FR-008): read side must agree with write side.
        lane: Lane = event_log_lanes.get(wp_id or "", Lane.GENESIS)

        # Parse dependencies
        dependencies = []
        if "dependencies:" in front:
            dep_match = re.search(r'dependencies:\s*\n((?:\s+-\s+"[^"]+"\s*\n)*)', front, re.MULTILINE)
            if dep_match:
                dep_text = dep_match.group(1)
                dependencies = re.findall(r'"([^"]+)"', dep_text)

        work_packages.append({
            "id": wp_id,
            "title": title,
            "lane": lane,
            "phase": phase,
            "file": wp_file.name,
            "artifact_dir": wp_file.stem,
            "dependencies": dependencies
        })

    # Group by lane using Lane enum keys (avoids raw lane-string comparisons)
    by_lane: dict[Lane, list] = {
        Lane.PLANNED: [], Lane.CLAIMED: [], Lane.IN_PROGRESS: [], Lane.IN_REVIEW: [],
        Lane.FOR_REVIEW: [], Lane.APPROVED: [], Lane.DONE: [], Lane.BLOCKED: [], Lane.CANCELED: [],
    }
    for wp in work_packages:
        lane = wp["lane"]
        if lane in NON_DISPLAY_LANES:
            # Genesis/uninitialized WPs are non-display (not finalized); silently skip them
            # from all kanban columns — they will appear once finalize-tasks
            # seeds them to planned (Contract 2, FR-008).
            pass
        elif lane in by_lane:
            by_lane[lane].append(wp)
        else:
            # Fallback: use progress_bucket to classify unknown lanes
            bucket = wp_state_for(lane).progress_bucket()
            if bucket == "terminal":
                by_lane[Lane.DONE].append(wp)
            elif bucket == "review":
                by_lane[Lane.FOR_REVIEW].append(wp)
            else:
                by_lane[Lane.PLANNED].append(wp)

    # Calculate metrics using progress_bucket() — no raw lane-string comparisons.
    # Genesis/uninitialized WPs are excluded from all metric buckets (non-display; Contract 2).
    _display_wps = [wp for wp in work_packages if wp["lane"] not in NON_DISPLAY_LANES]
    # Count only display WPs so the total matches the summed lane buckets;
    # genesis WPs are non-display and would otherwise inflate the total while
    # appearing in no column (review m1).
    total = len(_display_wps)
    done_count = sum(
        1 for wp in _display_wps
        if wp_state_for(wp["lane"]).progress_bucket() == "terminal"
        and wp["lane"] == Lane.DONE
    )
    in_progress = sum(
        1 for wp in _display_wps
        if wp_state_for(wp["lane"]).progress_bucket() in ("in_flight", "review")
    )
    planned_count = sum(
        1 for wp in _display_wps
        if wp_state_for(wp["lane"]).progress_bucket() == "not_started"
    )
    progress_result = compute_weighted_progress(snapshot)
    progress_pct = round(progress_result.percentage, 1)
    done_pct = round(compute_done_percentage(done_count, total), 1)

    # Analyze parallelization opportunities
    done_wp_ids = {wp["id"] for wp in work_packages if wp["lane"] == Lane.DONE}
    parallel_info = _analyze_parallelization(work_packages, done_wp_ids)

    # --- Stale verdict detection (T023) ---
    # Warn if approved/done WPs have a review artifact with verdict=rejected
    stale_verdicts: list[dict[str, str]] = []
    # T064/FR-012: a SEPARATE channel from stale_verdicts (not folded into
    # it) for the "artifact present but unreadable" refusal signal, so the
    # existing stale_verdicts contract (pinned byte-for-byte by
    # tests/agent/test_agent_utils_status.py, outside this WP's owned
    # surface) is untouched for the rejected-verdict case.
    damaged_verdicts: list[dict[str, str]] = []
    for wp in work_packages:
        if wp["lane"] not in (Lane.APPROVED, Lane.DONE):
            continue
        wp_id = wp["id"]
        if not wp_id:
            continue
        lookup = event_sourced_review_result(feature_dir, wp_id)
        if not lookup.slot_present:
            # absent -- legitimately no verdict recorded yet, not damage.
            continue
        if lookup.result is None:
            # refuse (FR-012): distinct board entry, not a command crash —
            # a damaged event-log ``review_result`` slot, never silently
            # folded into the same "no verdict" case a genuinely absent
            # slot produces.
            damaged_verdicts.append(
                {"wp_id": wp_id, "artifact": "review artifact: unreadable/damaged verdict record"}
            )
            wp["_damaged_verdict"] = True
            continue
        if is_changes_requested(lookup.result.verdict):
            stale_verdicts.append({"wp_id": wp_id, "artifact": "review artifact: verdict=rejected"})
            wp["_stale_verdict"] = True

    # --- Stall detection (T025) ---
    # Flag in_review WPs whose last event is older than the threshold
    current_instant = now_utc()
    stalled_wps: list[dict] = []
    for wp in by_lane.get(Lane.IN_REVIEW, []):
        wp_id = wp["id"]
        if not wp_id:
            continue
        last_event_time = _get_last_event_time(events, wp_id)
        if last_event_time is not None:
            age_minutes = (current_instant - last_event_time).total_seconds() / 60
            if age_minutes > threshold_minutes:
                stall_label = f"STALLED — no move-task in {int(age_minutes)}m"
                wp["_stall_label"] = stall_label
                stalled_wps.append({
                    "wp_id": wp_id,
                    "age_minutes": int(age_minutes),
                    "mission_slug": mission_slug,
                })

    # Return structured data (by_lane uses Lane.value to produce string keys)
    lane_counts = Counter(wp["lane"].value for wp in work_packages)
    return {
        "mission_slug": identity.mission_slug,
        "mission_number": identity.mission_number,
        "mission_type": identity.mission_type,
        "total_wps": total,
        "by_lane": dict(lane_counts),
        "work_packages": work_packages,
        "progress_percentage": progress_pct,
        "progress_semantics": PROGRESS_SEMANTICS,
        "weighted_percentage": progress_pct,
        "done_percentage": done_pct,
        "done_count": done_count,
        "in_progress_count": in_progress,
        "planned_count": planned_count,
        "parallelization": parallel_info,
        "stalled_wps": stalled_wps,
        "stale_verdicts": stale_verdicts,
        "damaged_verdicts": damaged_verdicts,
    }


def _analyze_parallelization(work_packages: list, done_wp_ids: set) -> dict:
    """Analyze which work packages can be started and parallelized.

    Args:
        work_packages: List of all work packages with dependencies
        done_wp_ids: Set of WP IDs that are already done

    Returns:
        dict with 'ready' (WPs that can start now) and 'parallel_groups' (groups that can run together)
    """
    # Find WPs that are ready (all dependencies satisfied)
    # Skip WPs that are already active or terminal — use progress_bucket() for semantic check.
    # Genesis/uninitialized WPs are also skipped: they are not yet finalized and cannot be started.
    ready_wps = []
    for wp in work_packages:
        if wp["lane"] in NON_DISPLAY_LANES:
            continue
        state = wp_state_for(wp["lane"])
        # Skip if already in-flight, under review, or terminal
        if state.progress_bucket() in ("in_flight", "review", "terminal"):
            continue

        # Check if all dependencies are satisfied
        deps = wp.get("dependencies", [])
        if all(dep in done_wp_ids for dep in deps):
            ready_wps.append(wp)

    # Group ready WPs by parallelization potential
    # WPs can run in parallel if they don't depend on each other
    parallel_groups = []
    if ready_wps:
        # Build dependency relationships among ready WPs
        ready_ids = {wp["id"] for wp in ready_wps}

        # Check which ready WPs don't depend on any other ready WPs
        independent = []
        dependent = []

        for wp in ready_wps:
            wp_deps = set(wp.get("dependencies", []))
            if not (wp_deps & ready_ids):  # No dependencies on other ready WPs
                independent.append(wp)
            else:
                dependent.append(wp)

        if independent:
            if len(independent) > 1:
                parallel_groups.append({
                    "type": "parallel",
                    "wps": independent,
                    "note": f"These {len(independent)} WPs can run in parallel"
                })
            else:
                parallel_groups.append({
                    "type": "single",
                    "wps": independent,
                    "note": "Ready to start"
                })

        if dependent:
            parallel_groups.append({
                "type": "sequential",
                "wps": dependent,
                "note": "Must wait for other ready WPs to complete first"
            })

    return {
        "ready_wps": ready_wps,
        "parallel_groups": parallel_groups,
        "can_parallelize": len(ready_wps) > 1 and any(g["type"] == "parallel" for g in parallel_groups)
    }


def _display_status_board(mission_slug: str, work_packages: list, by_lane: dict[Lane, list],
                         total: int, done_count: int, in_progress: int,
                         planned_count: int, done_pct: float, progress_pct: float,
                         parallel_info: dict) -> None:
    """Display the rich-formatted status board."""
    # Create title panel
    title_text = Text()
    title_text.append("📊 Work Package Status: ", style="bold cyan")
    title_text.append(mission_slug, style="bold white")

    console.print()
    console.print(Panel(title_text, border_style="cyan"))

    # Progress bar
    progress_text = Text()
    progress_text.append("Done progress: ", style="bold")
    progress_text.append(f"{done_count}/{total}", style="bold green")
    progress_text.append(f" ({done_pct}%)", style="dim")
    progress_text.append("\nWeighted readiness: ", style="bold")
    progress_text.append(f"{progress_pct}%", style="bold cyan")

    # Create visual readiness bar
    bar_width = 40
    filled = int(bar_width * progress_pct / 100)
    bar = "█" * filled + "░" * (bar_width - filled)
    progress_text.append(f"\n{bar}", style="green")

    console.print(progress_text)
    console.print()

    # Kanban board table
    # Note: in_review does NOT get its own column — it folds into "In Progress"
    # with a bright_cyan colour marker to distinguish it visually.

    # Merge in_review WPs into the in_progress display list with a marker
    display_in_progress = list(by_lane.get(Lane.IN_PROGRESS, []))
    in_review_wps = by_lane.get(Lane.IN_REVIEW, [])
    for wp in in_review_wps:
        wp["_display_in_review"] = True
        display_in_progress.append(wp)

    kanban_lanes = [
        (Lane.PLANNED, "Planned", "yellow"),
        (Lane.CLAIMED, "Claimed", "bright_yellow"),
        (Lane.IN_PROGRESS, "In Progress", "blue"),
        (Lane.FOR_REVIEW, "For Review", "cyan"),
        (Lane.APPROVED, "Approved", "magenta"),
        (Lane.DONE, "Done", "green"),
        (Lane.BLOCKED, "Blocked", "red"),
        (Lane.CANCELED, "Canceled", "dim"),
    ]

    table = Table(title="Kanban Board", show_header=True, header_style="bold magenta", border_style="dim")
    for _, label, style in kanban_lanes:
        table.add_column(label, style=style, no_wrap=False, width=16)

    # Find max length for rows
    max_rows = max(
        (len(display_in_progress) if lk == Lane.IN_PROGRESS else len(by_lane[lk]))
        for lk, _, _ in kanban_lanes
    ) if work_packages else 0

    # Add rows
    for i in range(max_rows):
        row = []
        for lane_key, _, _ in kanban_lanes:
            lane_data = display_in_progress if lane_key == Lane.IN_PROGRESS else by_lane[lane_key]
            if i < len(lane_data):
                wp = lane_data[i]
                title_part = f"{wp['title'][:14]}..." if len(wp['title']) > 14 else wp['title']
                # in_review WPs folded into "In Progress" get bright_cyan colour
                if wp.get("_display_in_review"):
                    cell = f"[bright_cyan]{wp['id']} (review)[/bright_cyan]\n{title_part}"
                else:
                    cell = f"{wp['id']}\n{title_part}"
                row.append(cell)
            else:
                row.append("")
        table.add_row(*row)

    # Add count row
    count_row = [f"[bold]{len(display_in_progress) if lane_key == Lane.IN_PROGRESS else len(by_lane[lane_key])} WPs[/bold]" for lane_key, _, _ in kanban_lanes]
    table.add_row(*count_row, style="dim")

    console.print(table)
    console.print()

    # Next steps section
    if by_lane[Lane.FOR_REVIEW]:
        console.print("[bold cyan]👀 Ready for Review:[/bold cyan]")
        for wp in by_lane[Lane.FOR_REVIEW]:
            console.print(f"  • {wp['id']} - {wp['title']}")
        console.print()

    if by_lane[Lane.APPROVED]:
        console.print("[bold magenta]👍 Approved Awaiting Merge:[/bold magenta]")
        for wp in by_lane[Lane.APPROVED]:
            line = f"  • {wp['id']} - {wp['title']}"
            if wp.get("_stale_verdict"):
                line += "  [bold yellow]⚠ review artifact: verdict=rejected[/bold yellow]"
            if wp.get("_damaged_verdict"):
                # refuse (FR-012): a distinct, declared board entry — not the
                # same silent "no verdict" a genuinely-unverdicted WP shows.
                line += "  [bold red]⚠ review artifact: unreadable/damaged verdict record[/bold red]"
            console.print(line)
        console.print()

    # Show done WPs with stale or damaged verdict warnings (if any)
    done_stale = [
        wp for wp in by_lane[Lane.DONE] if wp.get("_stale_verdict") or wp.get("_damaged_verdict")
    ]
    if done_stale:
        console.print("[bold green]✅ Done (with stale verdict warnings):[/bold green]")
        for wp in done_stale:
            line = f"  • {wp['id']} - {wp['title']}"
            if wp.get("_stale_verdict"):
                line += "  [bold yellow]⚠ review artifact: verdict=rejected[/bold yellow]"
            if wp.get("_damaged_verdict"):
                line += "  [bold red]⚠ review artifact: unreadable/damaged verdict record[/bold red]"
            console.print(line)
        console.print()

    if by_lane[Lane.IN_PROGRESS]:
        console.print("[bold blue]🔄 In Progress:[/bold blue]")
        for wp in by_lane[Lane.IN_PROGRESS]:
            console.print(f"  • {wp['id']} - {wp['title']}")
        console.print()

    if by_lane[Lane.CLAIMED]:
        console.print("[bold bright_yellow]🤝 Claimed:[/bold bright_yellow]")
        for wp in by_lane[Lane.CLAIMED]:
            console.print(f"  • {wp['id']} - {wp['title']}")
        console.print()

    if by_lane[Lane.BLOCKED]:
        console.print("[bold red]🚫 Blocked:[/bold red]")
        for wp in by_lane[Lane.BLOCKED]:
            console.print(f"  • {wp['id']} - {wp['title']}")
        console.print()

    if by_lane.get(Lane.IN_REVIEW):
        console.print("[bold bright_cyan]🔍 In Review (shown in In Progress column):[/bold bright_cyan]")
        for wp in by_lane[Lane.IN_REVIEW]:
            line = f"  • {wp['id']} - {wp['title']}"
            if wp.get("_stall_label"):
                line += f"  [bold yellow]⚠ {wp['_stall_label']}[/bold yellow]"
            console.print(line)
        console.print()

    if by_lane[Lane.PLANNED]:
        console.print("[bold yellow]📋 Next Up (Planned):[/bold yellow]")
        # Show first 3 planned items
        for wp in by_lane[Lane.PLANNED][:3]:
            console.print(f"  • {wp['id']} - {wp['title']}")
        if len(by_lane[Lane.PLANNED]) > 3:
            console.print(f"  [dim]... and {len(by_lane[Lane.PLANNED]) - 3} more[/dim]")
        console.print()

    # Parallelization opportunities
    if parallel_info["ready_wps"]:
        console.print("[bold magenta]🔀 Parallelization Strategy:[/bold magenta]")

        for group in parallel_info["parallel_groups"]:
            if group["type"] == "parallel":
                console.print("\n  [bold green]✨ Can run in PARALLEL:[/bold green]")
                for wp in group["wps"]:
                    console.print(f"     • {wp['id']} - {wp['title']}")
                console.print("  [dim]  → All dependencies satisfied, no inter-dependencies[/dim]")

                # Show implementation commands
                console.print("\n  [bold]Start commands:[/bold]")
                for wp in group["wps"]:
                    console.print(f"     spec-kitty implement {wp['id']} &")

            elif group["type"] == "single":
                console.print("\n  [bold yellow]▶️  Ready to start:[/bold yellow]")
                for wp in group["wps"]:
                    console.print(f"     • {wp['id']} - {wp['title']}")
                    console.print(f"     spec-kitty implement {wp['id']}")

            elif group["type"] == "sequential":
                console.print("\n  [bold blue]⏭️  Sequential (blocked by other ready WPs):[/bold blue]")
                for wp in group["wps"]:
                    deps_in_ready = [d for d in wp.get("dependencies", [])
                                    if d in {w["id"] for w in parallel_info["ready_wps"]}]
                    console.print(f"     • {wp['id']} - {wp['title']}")
                    console.print(f"       [dim]Waiting for: {', '.join(deps_in_ready)}[/dim]")

        console.print()
    elif by_lane[Lane.PLANNED] and not by_lane[Lane.IN_PROGRESS] and not by_lane[Lane.CLAIMED] and not by_lane[Lane.FOR_REVIEW] and not by_lane.get(Lane.IN_REVIEW) and not by_lane[Lane.APPROVED]:
        # All planned WPs are blocked
        console.print("[bold red]⚠️  All remaining WPs are blocked[/bold red]")
        console.print("  Check dependency status above\n")

    # Summary metrics
    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold")
    summary.add_column()
    summary.add_row("Total WPs:", str(total))
    summary.add_row("Completed:", f"[green]{done_count}[/green] ({done_pct}%)")
    summary.add_row("Weighted readiness:", f"[cyan]{progress_pct}%[/cyan]")
    summary.add_row("In Progress:", f"[blue]{in_progress}[/blue]")
    summary.add_row("Planned:", f"[yellow]{planned_count}[/yellow]")

    console.print(Panel(summary, title="[bold]Summary[/bold]", border_style="dim"))
    console.print()
