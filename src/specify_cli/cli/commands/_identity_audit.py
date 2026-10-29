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
from rich.markup import escape
from rich.table import Table

from kernel.git import GitCommandError
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

#: The remedy for each ``residue`` reason of ``doctor identity`` (#5875, FR-004, D5). They are
#: separate from ``mission_resolver.RESIDUE_NOTICE`` (the write-seam text, which a regex parses).
#: ``~1`` rather than ``^``: ``^`` is the escape character of Windows ``cmd``.
RESIDUE_REMEDY_NO_META = (
    "No meta.json on disk, so Mission selection does not list it. If it is leftover residue, delete the folder. "
    "If it is a real Mission whose meta.json was deleted: when `git status` shows the deletion, run "
    "`git restore <path>/meta.json`; when the deletion was committed, find it with "
    "`git log --diff-filter=D --format=%h -1 -- <path>/meta.json` and run "
    "`git checkout <sha>~1 -- <path>/meta.json`. If its meta.json was never committed, re-create the Mission "
    "with `spec-kitty agent mission create` and move its spec.md into the new folder."
)
RESIDUE_REMEDY_UNTRACKED_IDLESS_META = (
    "A meta.json without a mission_id that git does not track (nor the spec.md), so Mission selection does not "
    "list it. If it is a real Mission, commit its meta.json or run `spec-kitty migrate backfill-identity`; "
    "otherwise delete the folder."
)
RESIDUE_REMEDY_CORRUPT_META = (
    "The Mission content is corrupt: meta.json could not be read (the error is on each row). Do not delete the "
    "folder before checking. Repair it: fix its permissions or its JSON. If `git status` shows it staged as "
    "deleted, restore it with `git checkout HEAD -- <path>/meta.json`. If a commit removed it, find that commit "
    "with `git log --diff-filter=D --format=%h -1 -- <path>/meta.json` and restore it with "
    "`git checkout <sha>~1 -- <path>/meta.json`. Otherwise re-create the Mission with "
    "`spec-kitty agent mission create` and move its content in."
)
#: ``residue_reason`` -> remedy, in report order (``status.RESIDUE_REASONS``).
RESIDUE_REMEDIES: dict[str, str] = {
    "no_meta": RESIDUE_REMEDY_NO_META,
    "untracked_idless_meta": RESIDUE_REMEDY_UNTRACKED_IDLESS_META,
    "corrupt_meta": RESIDUE_REMEDY_CORRUPT_META,
}
#: ``residue_reason`` -> the heading of its group in the human output.
_RESIDUE_GROUP_HEADINGS: dict[str, str] = {
    "no_meta": "No meta.json:",
    "untracked_idless_meta": "Untracked meta.json without a mission_id:",
    "corrupt_meta": "Corrupt meta.json (could not be read):",
}

#: ``--json`` ``error_code`` when git cannot list the tracked ``kitty-specs/`` paths (a broken index).
GIT_INDEX_UNREADABLE = "GIT_INDEX_UNREADABLE"
_GIT_INDEX_REMEDIATION = (
    "Repair the git index: run `git reset`; if that fails too, delete the index file "
    "(its path is printed by `git rev-parse --git-path index`) and run `git reset` again, then re-run."
)


# --- identity helpers --------------------------------------------------------


def _scope_to_mission(
    repo_root: Path,
    all_states: list[IdentityState],
    mission: str,
) -> list[IdentityState]:
    """Filter states to a single mission slug (or classify it directly, residue rule included)."""
    from specify_cli.status import classify_walk_entry

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
    # #5875: the same read-side rule as the walk, so ``--mission <residue>`` reports ``residue``.
    if target_dir.is_dir():
        return [classify_walk_entry(target_dir, repo_root=repo_root)]
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
    residue = sum(1 for s in all_states if s.state == "residue")
    console.print(f"\n[bold]Mission Identity Audit[/bold] — {len(all_states) - residue} Mission(s), {residue} residue folder(s)\n")

    summary_table = Table(box=None, padding=(0, 2), show_edge=False)
    summary_table.add_column("State", style="cyan", min_width=10)
    summary_table.add_column("Count", justify="right", min_width=6)
    from specify_cli.status import IDENTITY_STATES

    _state_styles = {"assigned": "[green]", "pending": "[yellow]", "legacy": "[red]", "orphan": "[red]", "residue": "[yellow]"}
    for state_name in IDENTITY_STATES:
        count = counts_dict.get(state_name, 0)
        styled = f"{_state_styles.get(state_name, '')}{state_name}[/]"
        summary_table.add_row(styled, str(count))
    console.print(summary_table)
    console.print()


def _print_path_section(heading: str, paths: object) -> bool:
    """Print *heading* and one indented line per path; ``False`` (nothing printed) when *paths* is empty."""
    if not isinstance(paths, list) or not paths:
        return False
    console.print(heading)
    for p in paths:
        console.print(f"  {p}")
    console.print()
    return True


def _residue_groups(all_states: list[IdentityState]) -> dict[str, list[IdentityState]]:
    """The ``residue`` rows grouped by ``residue_reason``, in report order, present reasons only."""
    from specify_cli.status import RESIDUE_REASONS

    groups: dict[str, list[IdentityState]] = {reason: [] for reason in RESIDUE_REASONS}
    for s in all_states:
        if s.state == "residue":
            if s.residue_reason is None:
                raise ValueError(f"residue row {s.slug!r} carries no residue_reason")
            groups[s.residue_reason].append(s)
    return {reason: rows for reason, rows in groups.items() if rows}


def _print_residue_section(all_states: list[IdentityState]) -> None:
    """Print the residue rows grouped by reason; each present reason's remedy prints once, after its rows."""
    groups = _residue_groups(all_states)
    if not groups:
        return
    console.print("[bold yellow]Residue folders (not Missions; Mission selection does not list them):[/bold yellow]")
    for reason, rows in groups.items():
        console.print(f"  [yellow]{_RESIDUE_GROUP_HEADINGS[reason]}[/yellow]")
        for row in rows:
            detail = f" — {escape(row.error)}" if row.error else ""
            console.print(f"    {escape(str(row.path))}{detail}", soft_wrap=True)
        console.print(f"  [bold]Remedy:[/bold] {RESIDUE_REMEDIES[reason]}", soft_wrap=True)
    console.print()


def _print_identity_path_sections(summary: dict[str, object], all_states: list[IdentityState]) -> None:
    """Print the legacy and orphan path sections, then the residue section grouped by reason."""
    _print_path_section("[bold red]Legacy missions (need backfill):[/bold red]", summary.get("legacy_paths"))
    _print_path_section("[bold red]Orphan missions (need triage):[/bold red]", summary.get("orphan_paths"))
    _print_residue_section(all_states)


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
    _print_identity_path_sections(summary, all_states)

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
    """Build the ``--json`` report payload for ``doctor identity``.

    ``residue_remedies`` (``{residue_reason: remedy}``, the reasons present) is
    added only when at least one row is ``residue`` (#5875).
    """
    report: dict[str, object] = {
        "summary": summary["counts"],
        "missions": [s.to_dict() for s in all_states],
        "duplicate_prefixes": {prefix: [s.to_dict() for s in items] for prefix, items in dup_prefixes.items()},
        "ambiguous_selectors": {handle: [s.to_dict() for s in items] for handle, items in ambig_selectors.items()},
        "fail_on_triggered": fail_on_triggered,
    }
    groups = _residue_groups(all_states)
    if groups:
        report["residue_remedies"] = {reason: RESIDUE_REMEDIES[reason] for reason in groups}
    return report


def _git_index_unreadable(exc: GitCommandError, *, json_output: bool) -> typer.Exit:
    """Report a git index that cannot be read as one line (or a JSON envelope); the caller raises the exit."""
    message = f"git could not read the git index, so doctor identity cannot tell tracked kitty-specs/ files apart: {exc}"
    if json_output:
        envelope = {"error_code": GIT_INDEX_UNREADABLE, "error": message, "remediation": _GIT_INDEX_REMEDIATION}
        sys.stdout.write(json.dumps(envelope, indent=2) + "\n")
        sys.stdout.flush()
    else:
        console.print(f"[red]Error:[/red] {escape(message)} {escape(_GIT_INDEX_REMEDIATION)}", soft_wrap=True)
    return typer.Exit(1)


def _audit_identity(repo_root: Path, mission: str | None) -> tuple[list[IdentityState], dict[str, list[IdentityState]]] | None:
    """Walk ``kitty-specs/`` (scoped to *mission* when given); ``None`` when *mission* is not found."""
    from specify_cli.status import audit_repo, find_duplicate_prefixes

    all_states = audit_repo(repo_root, residue_aware=True)
    if mission is not None:
        all_states = _scope_to_mission(repo_root, all_states, mission)
        if not all_states:
            return None
    dup_prefixes = find_duplicate_prefixes(repo_root, residue_aware=True)
    if mission is not None:
        dup_prefixes = _scope_prefixes(dup_prefixes, mission)
    return all_states, dup_prefixes


def run_identity_audit(repo_root: Path, json_output: bool, mission: str | None, fail_on: str | None) -> None:
    """Entry point for ``doctor identity`` — preserves the original exit contract.

    *repo_root* is resolved by the ``doctor.py`` command shell (which owns the
    patchable ``locate_project_root`` seam) and injected here, preserving the
    existing monkeypatch contracts of the command's tests. A git index that
    cannot be read exits 1 with one error line (``GIT_INDEX_UNREADABLE`` under
    ``--json``) instead of a traceback (#5875).
    """
    from specify_cli.status import find_ambiguous_selectors, summarize

    try:
        audited = _audit_identity(repo_root, mission)
    except GitCommandError as exc:
        if exc.timed_out:
            raise  # a timeout is not a broken index
        raise _git_index_unreadable(exc, json_output=json_output) from exc
    if audited is None:
        console.print(f"[red]Error:[/red] Mission not found: {mission!r}")
        raise typer.Exit(1)
    all_states, dup_prefixes = audited

    summary = summarize(all_states)
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

# FR-015: every topology finding carries its operator remedy (``{slug}`` is filled per mission).
# LANES_MANIFEST_UNREADABLE: ``finalize-tasks`` REFUSES a corrupt lanes.json (CorruptLanesError),
# so the remedy is restore-from-git or delete + rebuild -- and the rebuild command depends on
# whether execution has begun (finalize-tasks refuses once a WP is past ``planned``;
# ``doctor mission-state --fix`` rebuilds only from the event log once execution has begun).
_TOPOLOGY_REMEDIES: dict[str, str] = {
    _SINGLE_BRANCH_CODE_LANES_UNMIGRATED_FINDING: (
        "spec-kitty migrate backfill-topology --restamp-single-branch (or `spec-kitty upgrade`, which runs migration m_4_0_0rc5_single_branch_code_lanes_restamp)"
    ),
    _LANES_MANIFEST_UNREADABLE_FINDING: (
        "restore lanes.json from git history: `git checkout <ref> -- kitty-specs/{slug}/lanes.json`; "
        "or delete it and rebuild: `spec-kitty agent mission finalize-tasks --mission {slug}` "
        "if no WP has started, `spec-kitty doctor mission-state --fix --mission {slug}` if execution has begun"
    ),
}


def _topology_remedy(finding: object, slug: str) -> str | None:
    """Return the remedy text for a topology finding code (filled for *slug*), or ``None``."""
    template = _TOPOLOGY_REMEDIES.get(finding) if isinstance(finding, str) else None
    return template.format(slug=slug) if template is not None else None


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
    # Operator decision (PR #5398 handoff addendum): a TERMINAL (archived)
    # mission is never run again, so reporting SINGLE_BRANCH_CODE_LANES_UNMIGRATED
    # on it is pointless churn on a frozen dossier. Suppress it, keyed on the same
    # canonical completion predicate the re-stamp migration uses
    # (:func:`specify_cli.status.lifecycle.is_mission_completed` — a ``merged_at``
    # marker OR every WP terminal) so the finding and the migration's selection
    # never drift apart. Checked last, only for an otherwise-flagged mission, so
    # its event-log read is not paid for every mission the audit walks.
    from specify_cli.status import is_mission_completed

    if is_mission_completed(feature_dir):
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
        return {"slug": feature_dir.name, "topology": None, "flattened": None, "error": f"corrupt json: {exc}", "finding": None, "remedy": None}
    if meta is None:
        return {"slug": feature_dir.name, "topology": None, "flattened": None, "error": "meta.json not found", "finding": None, "remedy": None}
    topology = meta.get("topology")
    finding = _topology_finding(topology, feature_dir)
    return {
        "slug": feature_dir.name,
        "topology": topology,
        "flattened": meta.get("flattened"),
        "error": None,
        "finding": finding,
        "remedy": _topology_remedy(finding, feature_dir.name),
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
    for row in rows:
        if row.get("remedy"):
            console.print(f"\n[bold]Remedy[/bold] for {row['slug']} ({row['finding']}): {row['remedy']}", soft_wrap=True)


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
