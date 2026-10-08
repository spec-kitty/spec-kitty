"""On-demand ``doctor cutover`` audit (WP05, FR-007).

Gives an operator an on-demand, outside-CI audit of every mission's
cut-over status. Per the doctor per-subcommand-module convention (see
``_workspace_husk_doctor.py`` / ``_mission_state_doctor.py``), the ``cutover``
@app.command shell in ``doctor.py`` stays a thin delegator; all logic lives
here.

**Reuse, not reimplementation** (plan IC-05 / research "Audit host"): this
module backs the audit with
``migration.runtime_state_cutover.cutover_repo(repo_root, dry_run=True)`` —
the same fail-closed seed-then-verify spine ``migrate backfill-runtime-state``
and the merge-terminus cutover seam use. It does not walk ``kitty-specs/``
itself and does not re-derive verify semantics; it only reduces each
:class:`~specify_cli.migration.runtime_state_cutover.CutoverResult` to a
human-facing cut-over verdict + reason.

Verdict derivation: ``dry_run=True`` never flips (``CutoverResult.flipped`` is
always ``False`` on this path), so the verdict rides ``would_flip`` — which
:func:`~specify_cli.migration.runtime_state_cutover.cutover_mission` sets
whenever the fail-closed verify passes (``verify.ok``). A verify-passing
mission is either already cut over or has nothing outstanding to migrate; a
verify-failing mission still carries legacy runtime that has not been
event-sourced, which is exactly "not yet cut over" for FR-007's purposes. A
per-mission ``error`` (a malformed WP file, a strip-ordering violation, a
placement-port mismatch) takes priority over ``would_flip`` since verify never
ran in that case.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import typer
from rich.table import Table

from specify_cli.migration.runtime_state_cutover import CutoverResult, cutover_repo

from ._doctor_shared import console

# ``run_cutover_audit`` is the one symbol an src/ caller consumes (the
# ``doctor cutover`` @app.command shell in ``doctor.py``). ``CutoverAuditEntry``
# and ``collect_cutover_audit`` are this module's own internals -- exporting
# them tripped the symbol-level dead-code gate, since nothing outside imports
# them. They stay module-level (tests reach them by direct attribute access);
# they are simply not part of the public surface.
__all__ = [
    "run_cutover_audit",
]


@dataclass(frozen=True)
class CutoverAuditEntry:
    """One mission's audit verdict, reduced from a dry-run :class:`CutoverResult`.

    Attributes:
        slug: Mission directory name.
        cut_over: True iff the mission is fully event-sourced (verify passed
            or nothing needed seeding); False iff legacy runtime still needs
            migrating, or the run aborted with an ``error``.
        reason: Human-readable explanation -- the abort error, the mismatch
            list, or a short affirmative note.
    """

    slug: str
    cut_over: bool
    reason: str


_NO_LEGACY_RUNTIME_REASON = "no legacy runtime to migrate"
_WOULD_FLIP_REASON = "verify passed -- cut over (or already flipped)"
_NOT_MIGRATED_REASON = "not yet migrated (no verify result)"


def _reason_for(result: CutoverResult) -> str:
    """Derive the human-readable reason for *result*'s cut-over verdict.

    See the module docstring for the full derivation contract.
    """
    if result.error is not None:
        # ``CutoverResult`` resolves as ``Any`` under this narrow-file-path
        # mypy run (the ``specify_cli.*`` ``follow_imports = "skip"`` override
        # in pyproject.toml), so an explicit ``str()`` pins the return type
        # rather than propagating an untyped-Any return (no-any-return).
        return str(result.error)
    if result.would_flip:
        if result.verify is not None and result.verify.wp_count == 0:
            return _NO_LEGACY_RUNTIME_REASON
        return _WOULD_FLIP_REASON
    if result.verify is not None and result.verify.mismatches:
        return "; ".join(result.verify.mismatches)
    return _NOT_MIGRATED_REASON


def _entry_for(result: CutoverResult) -> CutoverAuditEntry:
    return CutoverAuditEntry(
        slug=result.slug, cut_over=result.would_flip, reason=_reason_for(result)
    )


def collect_cutover_audit(repo_root: Path) -> list[CutoverAuditEntry]:
    """Run the read-only dry-run cutover audit and reduce it to verdicts.

    Delegates the corpus walk and the seed/verify spine entirely to
    :func:`~specify_cli.migration.runtime_state_cutover.cutover_repo` with
    ``dry_run=True`` -- this function writes nothing.
    """
    return [_entry_for(result) for result in cutover_repo(repo_root, dry_run=True)]


def _emit_json(entries: list[CutoverAuditEntry], cut_over_count: int, total: int) -> None:
    payload = {
        "missions": [
            {"slug": e.slug, "cut_over": e.cut_over, "reason": e.reason} for e in entries
        ],
        "cut_over_count": cut_over_count,
        "total": total,
    }
    console.print_json(json.dumps(payload, indent=2))


def _emit_human(entries: list[CutoverAuditEntry], cut_over_count: int, total: int) -> None:
    if not entries:
        console.print("[green]Cutover[/green]: no missions found under kitty-specs/.")
        return

    console.print(
        f"\n[bold]Cutover Audit[/bold] -- {cut_over_count}/{total} mission(s) cut over\n"
    )
    table = Table(box=None, padding=(0, 2), show_edge=False)
    table.add_column("Mission", style="cyan", min_width=24)
    table.add_column("Cut Over", min_width=10)
    table.add_column("Reason", min_width=30)
    for entry in entries:
        status = "[green]yes[/green]" if entry.cut_over else "[yellow]no[/yellow]"
        table.add_row(entry.slug, status, entry.reason)
    console.print(table)
    console.print()


def run_cutover_audit(repo_root: Path, *, json_output: bool) -> None:
    """Entry point for ``doctor cutover``.

    Informational only (T021): always exits 0 with a clear count, regardless
    of how many missions are un-cut-over. This audits standing drift; it does
    not gate a workflow on it (unlike ``doctor charter-packs`` / ``coordination``,
    which reflect health in their exit code).
    """
    entries = collect_cutover_audit(repo_root)
    cut_over_count = sum(1 for e in entries if e.cut_over)
    total = len(entries)

    if json_output:
        _emit_json(entries, cut_over_count, total)
    else:
        _emit_human(entries, cut_over_count, total)
    raise typer.Exit(0)
