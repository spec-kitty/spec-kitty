"""Mission-identity + topology audit cluster for ``doctor`` (WP04, #2059).

Extracts Cluster D out of ``doctor.py`` and decomposes the ``identity`` command
body into small, individually-tested helpers (each <=15 CC, I-4). The
``@app.command`` shells stay in ``doctor.py`` (the ``add_typer`` target); they
delegate to :func:`run_identity_audit` / :func:`run_topology_audit` here.

Import discipline (one-way, I-2): this module imports shared infra from
:mod:`._doctor_shared` and ``specify_cli`` libraries; it never imports
``doctor.py``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.table import Table

from mission_runtime import MissionArtifactKind, placement_seam
from specify_cli.core.constants import KITTY_SPECS_DIR

from ._doctor_shared import console

if TYPE_CHECKING:
    from specify_cli.status import IdentityState

# ``__all__`` lists this sibling's cross-module entrypoints only. The
# decomposed helpers are intra-module (used here + by this module's own unit
# tests) and are deliberately NOT exported — listing them would register orphan
# public symbols under the dead-symbol gate (tests/architectural/test_no_dead_symbols).
__all__ = [
    "run_identity_audit",
    "run_topology_audit",
]


# --- identity helpers --------------------------------------------------------


def _scope_to_mission(
    repo_root: Path,
    all_states: list[IdentityState],
    mission: str,
) -> list[IdentityState]:
    """Filter states to a single mission slug (or classify it directly)."""
    from specify_cli.status import classify_mission

    filtered = [s for s in all_states if s.slug == mission]
    if filtered:
        return filtered
    # read-surface-ssot-closeout WP05 / FR-001 / NFR-001: route through the
    # kind-aware placement seam instead of the kind-blind
    # ``resolve_feature_dir_for_mission`` (which could return the
    # coordination worktree's mission dir once materialized -- the #2453
    # coord-husk-shadows-primary defect NFR-001 closes). ``PRIMARY_METADATA``
    # is the artifact kind for a mission's ``meta.json`` -- exactly what
    # ``classify_mission`` reads -- and is a PRIMARY-partition kind, so
    # ``read_dir`` resolves the topology-blind primary directory directly.
    target_dir = placement_seam(repo_root, mission).read_dir(MissionArtifactKind.PRIMARY_METADATA)
    if target_dir.is_dir():
        return [classify_mission(target_dir)]
    return []


def _scope_prefixes(
    duplicate_prefixes: dict[str, list[IdentityState]],
    mission: str,
) -> dict[str, list[IdentityState]]:
    """Narrow duplicate_prefixes to the prefix of the scoped mission."""
    import re as _re

    m = _re.match(r"^(\d{3})-", mission)
    if not m:
        return {}
    prefix = m.group(1)
    return {prefix: duplicate_prefixes[prefix]} if prefix in duplicate_prefixes else {}


def _print_dup_and_ambig(
    duplicate_prefixes: dict[str, list[IdentityState]],
    ambiguous_selectors: dict[str, list[IdentityState]],
) -> None:
    """Print duplicate-prefix and ambiguous-selector sections."""
    if duplicate_prefixes:
        console.print("[bold yellow]Duplicate Prefixes[/bold yellow]")
        for prefix, items in sorted(duplicate_prefixes.items()):
            console.print(f"  [yellow]{prefix}[/yellow] — {len(items)} collision(s):")
            for s in items:
                mid = s.mission_id or "[dim]no mission_id[/dim]"
                console.print(f"    {s.slug}  mission_id={mid}  state={s.state}")
        console.print()

    if ambiguous_selectors:
        console.print("[bold yellow]Ambiguous Selectors[/bold yellow]")
        for handle, items in sorted(ambiguous_selectors.items()):
            console.print(f"  [yellow]{handle!r}[/yellow] → {len(items)} candidate(s):")
            for s in items:
                console.print(f"    {s.slug}")
        console.print()

    if not duplicate_prefixes and not ambiguous_selectors:
        console.print("[green]No duplicate prefixes or ambiguous selectors.[/green]\n")


def _print_identity_summary_table(all_states: list[IdentityState], summary: dict[str, object]) -> None:
    """Print the per-state count table (extracted to keep callers <=15 CC)."""
    counts_dict: dict[str, int] = summary["counts"]  # type: ignore[assignment]
    total = len(all_states)
    console.print(f"\n[bold]Mission Identity Audit[/bold] — {total} mission(s)\n")

    summary_table = Table(box=None, padding=(0, 2), show_edge=False)
    summary_table.add_column("State", style="cyan", min_width=10)
    summary_table.add_column("Count", justify="right", min_width=6)
    _state_styles = {"assigned": "[green]", "pending": "[yellow]", "legacy": "[red]", "orphan": "[red]"}
    for state_name in ("assigned", "pending", "legacy", "orphan"):
        count = counts_dict.get(state_name, 0)
        styled = f"{_state_styles.get(state_name, '')}{state_name}[/]"
        summary_table.add_row(styled, str(count))
    console.print(summary_table)
    console.print()


def _print_identity_path_sections(summary: dict[str, object]) -> None:
    """Print the legacy + orphan path sections (extracted helper)."""
    legacy_paths: list[str] = summary["legacy_paths"]  # type: ignore[assignment]
    orphan_paths: list[str] = summary["orphan_paths"]  # type: ignore[assignment]
    if legacy_paths:
        console.print("[bold red]Legacy missions (need backfill):[/bold red]")
        for p in legacy_paths:
            console.print(f"  {p}")
        console.print()
    if orphan_paths:
        console.print("[bold red]Orphan missions (need triage):[/bold red]")
        for p in orphan_paths:
            console.print(f"  {p}")
        console.print()


def _print_identity_human(
    all_states: list[IdentityState],
    duplicate_prefixes: dict[str, list[IdentityState]],
    ambiguous_selectors: dict[str, list[IdentityState]],
    summary: dict[str, object],
    fail_on_states: set[str],
    fail_on_triggered: bool,
    fail_on: str | None,
) -> None:
    """Render the human-readable identity report to the console."""
    _print_identity_summary_table(all_states, summary)
    _print_dup_and_ambig(duplicate_prefixes, ambiguous_selectors)
    _print_identity_path_sections(summary)

    if fail_on_triggered:
        console.print(f"[bold red]FAIL:[/bold red] --fail-on {fail_on!r} triggered (one or more missions in: {', '.join(sorted(fail_on_states))})")


def _compute_fail_on(fail_on: str | None, all_states: list[IdentityState]) -> tuple[set[str], bool]:
    """Parse ``--fail-on`` states and determine whether the gate is triggered."""
    fail_on_states: set[str] = {s.strip() for s in fail_on.split(",") if s.strip()} if fail_on else set()
    fail_on_triggered = bool(fail_on_states and any(s.state in fail_on_states for s in all_states))
    return fail_on_states, fail_on_triggered


def _build_identity_json(
    all_states: list[IdentityState],
    summary: dict[str, object],
    dup_prefixes: dict[str, list[IdentityState]],
    ambig_selectors: dict[str, list[IdentityState]],
    fail_on_triggered: bool,
) -> dict[str, object]:
    """Build the ``--json`` report payload for ``doctor identity``."""
    return {
        "summary": summary["counts"],
        "missions": [s.to_dict() for s in all_states],
        "duplicate_prefixes": {prefix: [s.to_dict() for s in items] for prefix, items in dup_prefixes.items()},
        "ambiguous_selectors": {handle: [s.to_dict() for s in items] for handle, items in ambig_selectors.items()},
        "fail_on_triggered": fail_on_triggered,
    }


def run_identity_audit(repo_root: Path, json_output: bool, mission: str | None, fail_on: str | None) -> None:
    """Entry point for ``doctor identity`` — preserves the original exit contract.

    *repo_root* is resolved by the ``doctor.py`` command shell (which owns the
    patchable ``locate_project_root`` seam) and injected here, preserving the
    existing monkeypatch contracts of the command's tests.
    """
    from specify_cli.status import (
        audit_repo,
        find_ambiguous_selectors,
        find_duplicate_prefixes,
        summarize,
    )

    all_states = audit_repo(repo_root)

    if mission is not None:
        scoped = _scope_to_mission(repo_root, all_states, mission)
        if not scoped:
            console.print(f"[red]Error:[/red] Mission not found: {mission!r}")
            raise typer.Exit(1)
        all_states = scoped

    summary = summarize(all_states)
    dup_prefixes = find_duplicate_prefixes(repo_root)
    if mission is not None:
        dup_prefixes = _scope_prefixes(dup_prefixes, mission)
    ambig_selectors = find_ambiguous_selectors(all_states)

    fail_on_states, fail_on_triggered = _compute_fail_on(fail_on, all_states)

    if json_output:
        report = _build_identity_json(all_states, summary, dup_prefixes, ambig_selectors, fail_on_triggered)
        sys.stdout.write(json.dumps(report, indent=2) + "\n")
        sys.stdout.flush()
        raise typer.Exit(1 if fail_on_triggered else 0)

    _print_identity_human(
        all_states,
        dup_prefixes,
        ambig_selectors,
        summary,
        fail_on_states,
        fail_on_triggered,
        fail_on,
    )
    raise typer.Exit(1 if fail_on_triggered else 0)


# --- topology helpers --------------------------------------------------------


_SINGLE_BRANCH_CODE_LANES_UNMIGRATED_FINDING = "SINGLE_BRANCH_CODE_LANES_UNMIGRATED"
# Review cycle-1 blocker: a stored single_branch mission whose lanes.json
# exists but the canonical reader rejects (e.g. a legacy feature_slug-keyed
# manifest, #064) must NEVER report as clean just because the reader could
# not tell whether it has a code lane. This finding is the honest "cannot
# verify Invariant T-1" signal -- distinct from
# SINGLE_BRANCH_CODE_LANES_UNMIGRATED (which means "verified violation") so
# an operator knows a manual/manifest-level fix is needed, not a re-stamp.
_LANES_MANIFEST_UNREADABLE_FINDING = "LANES_MANIFEST_UNREADABLE"


def _topology_finding(topology: object, feature_dir: Path) -> str | None:
    """Return the doctor finding code for one mission's topology row (#5100 IC-02 / T014).

    ``SINGLE_BRANCH_CODE_LANES_UNMIGRATED`` when the mission's STORED
    ``topology`` is ``single_branch`` (Invariant T-1, ``data-model.md``) but
    its ``lanes.json`` has a code lane — the exact selection
    :func:`~specify_cli.migration.backfill_topology.restamp_single_branch_with_code_lanes`
    uses, so the finding and the migration's selection never drift apart.
    ``LANES_MANIFEST_UNREADABLE`` when ``topology`` is ``single_branch`` and
    ``lanes.json`` exists but the canonical reader cannot parse it (never
    silently ``None`` -- an unreadable manifest might still hide a code
    lane, so it must not read as clean). ``None`` for every other mission: a
    clean ``single_branch`` mission (the negative control), any other
    topology, or a mission with no ``lanes.json`` at all.
    """
    if topology != "single_branch":
        return None
    from specify_cli.lanes import CorruptLanesError, read_lanes_json
    from specify_cli.lanes.compute import has_code_lanes

    try:
        manifest = read_lanes_json(feature_dir)
    except CorruptLanesError:
        return _LANES_MANIFEST_UNREADABLE_FINDING
    if manifest is None or not has_code_lanes(manifest):
        return None
    return _SINGLE_BRANCH_CODE_LANES_UNMIGRATED_FINDING


def _read_stored_topology(feature_dir: Path) -> dict[str, object | None]:
    """Read the STORED topology + flattened flag for one mission (no re-inference).

    Reports the value as persisted in ``meta.json``. A mission not yet backfilled
    surfaces ``topology: null`` (so the audit drives the backfill); an unreadable
    ``meta.json`` surfaces ``topology: null`` with an ``error`` reason.
    """
    # read-surface-ssot-closeout WP05 / FR-005: route the inline
    # ``json.loads`` read through the canonical ``load_meta`` authority. This
    # site does NOT hard-fail on a missing meta.json -- it softly degrades to
    # an informative row (``error: "meta.json not found"``) -- so the
    # post-#2091 contract here is ``allow_missing=True`` (the pre-existing
    # soft-degrade, not a guard being masked: no guard exists to mask because
    # the caller never raised on missing). Malformed JSON keeps its distinct
    # "corrupt json" message via ``on_malformed="raise"`` + a local catch,
    # rather than folding it into the generic on_malformed="empty" adapter
    # (which would lose the distinct error text).
    from specify_cli.core.paths import MissionMetaReadError, load_meta_fail_closed

    try:
        meta = load_meta_fail_closed(feature_dir)
    except MissionMetaReadError as exc:
        return {"slug": feature_dir.name, "topology": None, "flattened": None, "error": f"corrupt json: {exc}", "finding": None}
    if meta is None:
        return {"slug": feature_dir.name, "topology": None, "flattened": None, "error": "meta.json not found", "finding": None}
    topology = meta.get("topology")
    return {
        "slug": feature_dir.name,
        "topology": topology,
        "flattened": meta.get("flattened"),
        "error": None,
        "finding": _topology_finding(topology, feature_dir),
    }


def _collect_topology_rows(repo_root: Path, mission: str | None) -> list[dict[str, object | None]]:
    """Collect stored-topology rows for all missions (or one when scoped)."""
    specs_dir = repo_root / KITTY_SPECS_DIR
    if not specs_dir.is_dir():
        return []
    if mission is not None:
        # read-surface-ssot-closeout WP05 / FR-001 / NFR-001: the kind-aware
        # seam (see ``_scope_to_mission`` above for the full rationale) --
        # ``PRIMARY_METADATA`` again, since this reads the mission's
        # ``meta.json``-bearing directory.
        target = placement_seam(repo_root, mission).read_dir(MissionArtifactKind.PRIMARY_METADATA)
        return [_read_stored_topology(target)] if target.is_dir() else []
    return [_read_stored_topology(entry) for entry in sorted(specs_dir.iterdir()) if entry.is_dir()]


def _print_topology_human(rows: list[dict[str, object | None]]) -> None:
    """Render a minimal stored-topology table to the console."""
    console.print(f"\n[bold]Mission Topology Audit[/bold] — {len(rows)} mission(s)\n")
    table = Table(box=None, padding=(0, 2), show_edge=False)
    table.add_column("Mission", style="cyan")
    table.add_column("Topology")
    table.add_column("Flattened")
    table.add_column("Finding")
    for row in rows:
        topology = row["topology"]
        rendered = str(topology) if topology is not None else "[red]null[/red]"
        flattened = "" if row["flattened"] is None else str(row["flattened"])
        finding = row.get("finding")
        rendered_finding = f"[yellow]{finding}[/yellow]" if finding else ""
        table.add_row(str(row["slug"]), rendered, flattened, rendered_finding)
    console.print(table)


def run_topology_audit(repo_root: Path, json_output: bool, mission: str | None) -> None:
    """Entry point for ``doctor topology`` — preserves the original exit contract.

    *repo_root* is resolved + injected by the ``doctor.py`` command shell.
    """
    if mission is not None and not _collect_topology_rows(repo_root, mission):
        console.print(f"[red]Error:[/red] Mission not found: {mission!r}")
        raise typer.Exit(1)

    rows = _collect_topology_rows(repo_root, mission)

    if json_output:
        report = {"missions": rows}
        sys.stdout.write(json.dumps(report, indent=2) + "\n")
        sys.stdout.flush()
        return

    _print_topology_human(rows)
