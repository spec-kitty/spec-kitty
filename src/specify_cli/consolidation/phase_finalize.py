"""Finalize phases: stale-assertion scan, optional push, summary and state clear.

Moved from ``consolidation/executor.py`` by epic #2026 with no logic change.
"""

from __future__ import annotations


import typer
from rich.markup import escape

from specify_cli.cli.console import console
from specify_cli.core.git_ops import has_remote, run_command

from specify_cli.consolidation._constants import (
    logger,
)
from specify_cli.consolidation.git_probes import (
    _emit_remediation_hint,
    _is_linear_history_rejection,
)
from specify_cli.consolidation.state import (
    clear_state,
)
from specify_cli.consolidation.workspace import cleanup_merge_workspace
from specify_cli.post_merge.stale_assertions import StaleAssertionFinding, StaleAssertionReport, run_check
from specify_cli.consolidation.run_state import (
    _MergeRunState,
)


def _phase_dossier_and_stale(run: _MergeRunState) -> None:
    """Stale-assertion advisory scan (failures never abort)."""
    console.print("  [dim]Running stale-assertion check...[/dim]")
    try:
        run.stale_report = run_check(
            base_ref=run.target_baseline_sha,
            head_ref="HEAD",
            repo_root=run.main_repo,
        )
    except Exception as exc:  # noqa: BLE001 — stale-assertion check is advisory; a failure must never abort an otherwise-successful merge
        logger.warning("Stale-assertion check failed: %s", exc)
        run.stale_report = None


def _phase_push(run: _MergeRunState) -> None:
    """Push the target branch to origin when requested (and a remote exists)."""
    lanes_manifest = run.lanes_manifest
    if not (run.push and has_remote(run.main_repo)):
        return
    _ret_push, _out_push, stderr_push = run_command(
        ["git", "push", "origin", lanes_manifest.target_branch],
        capture=True,
        check_return=False,
        cwd=run.main_repo,
    )
    if _ret_push != 0:
        if _is_linear_history_rejection(stderr_push):
            _emit_remediation_hint(console)
        console.print(f"[red]Error:[/red] Push failed: {stderr_push.strip() or _out_push.strip()}")
        raise typer.Exit(1)
    console.print(f"[green]✓[/green] Pushed {lanes_manifest.target_branch} to origin")


def _phase_finalize_and_summary(run: _MergeRunState) -> None:
    """Cleanup workspace + clear state, render stale findings."""
    # -- T002: Cleanup workspace (preserves state.json) then clear state --
    cleanup_merge_workspace(run.canonical_id, run.main_repo)
    # terminus-merge-integrity WP06 (FR-012) / #5111: ``clear_state`` drops the
    # state and its post-fix marker together (state first), so a subsequent,
    # unrelated merge for the same mission never mistakes a leftover marker for
    # its own in-flight transaction.
    clear_state(run.main_repo, run.canonical_id)

    _render_stale_findings(run.stale_report)


def _render_stale_findings(stale_report: StaleAssertionReport | None) -> None:
    """Render the stale-assertion findings block in the merge summary (T013/T023).

    #3957: message-content (info-grade) assertions are the real signal the
    analyzer skips, so they are surfaced as a named block with per-assertion
    ``file:line`` entries — placed BEFORE the low-grade noise, never buried
    behind it as a trailing count note.
    """
    console.print("\n[bold]Stale assertion findings:[/bold]")
    if stale_report is None:
        console.print("  [yellow]Stale-assertion check could not run.[/yellow]")
        return
    if not stale_report.findings:
        console.print("  No likely-stale assertions detected.")
        return

    actionable = [f for f in stale_report.findings if f.confidence in ("high", "medium")]
    low_grade = [f for f in stale_report.findings if f.confidence == "low"]
    info_grade = [f for f in stale_report.findings if f.confidence == "info"]

    for finding in actionable:
        console.print(_stale_finding_line(finding.confidence, finding))
    if info_grade:
        console.print(f"  Message-content assertions skipped as info grade ({len(info_grade)}) — review manually if diagnostic text changed:")
        for finding in info_grade:
            console.print(_stale_finding_line("info", finding))
    for finding in low_grade:
        console.print(_stale_finding_line(finding.confidence, finding))


def _stale_finding_line(grade: str, finding: StaleAssertionFinding) -> str:
    """One ``[grade] file:line — hint`` finding line, escaped for Rich.

    The line is operator data, not markup: unescaped, Rich parses the bracketed
    grade label (``[high]``, ``[info]`` ...) as an unknown style tag and drops
    it, so the operator could not tell actionable findings from noise.
    """
    return "  " + escape(f"[{grade}] {finding.test_file.name}:{finding.test_line} — {finding.hint}")
