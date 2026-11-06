"""Legacy sparse-checkout detection + remediation cluster for ``doctor`` (WP08, #2059).

Extracts Cluster E out of ``doctor.py`` and decomposes the ``sparse-checkout``
command (CC19) into <=15-CC sub-helpers (detect → render-finding →
build-remediation-plan → apply-or-refuse).

Import discipline (one-way, I-2): imports shared infra from
:mod:`._doctor_shared`; never imports the CLI ``doctor`` module. Heavy domain
imports (``specify_cli.git.sparse_checkout*``) stay FUNCTION-LOCAL to keep module
import cheap and avoid circular-import edge cases, mirroring the pre-extraction
pattern. The ``sparse-checkout`` subcommand name is owned by the shell in
``doctor.py`` and is byte-preserved (I-7: the compat safety predicate keys on it).
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import typer

from specify_cli.core.paths import locate_project_root

from ._doctor_shared import _is_interactive_environment, console

if TYPE_CHECKING:
    # Type-only imports: zero runtime cost, so the heavy domain modules stay
    # function-local at runtime (circular-import safety) while annotations use
    # the concrete types instead of ``object`` + ``# type: ignore``.
    from specify_cli.git.sparse_checkout import SparseCheckoutScanReport
    from specify_cli.git.sparse_checkout_remediation import (
        SparseCheckoutRemediationResult,
    )
    from specify_cli.lanes.lane_checkout import MissionCodeLane

# ``__all__`` lists this sibling's single cross-module entrypoint. The render
# helpers are intra-module (used here + by this module's own unit tests) and are
# deliberately NOT exported — listing them would register orphan public symbols
# under the dead-symbol gate (tests/architectural/test_no_dead_symbols).
__all__ = [
    "run_sparse_checkout",
]

_FIX_HINT = "spec-kitty doctor sparse-checkout --fix"

LANE_STATUS_AUTHORED = "LANE_STATUS_AUTHORED"
"""Doctor finding code (``contracts/error-codes.yaml``, FR-045)."""

LANE_STATUS_NOT_EXCLUDED = "LANE_STATUS_NOT_EXCLUDED"
"""Doctor finding code: a registered lane worktree still shows the Mission status files (FR-044)."""


@dataclass(frozen=True)
class LaneStatusAuthored:
    """A live lane branch carrying a lane-authored change to its Mission status files (FR-045).

    ``commits`` are the lane's own non-merge commits that touch the status
    files: reachable from the lane, from none of the branches the status bytes
    come from (the coordination branch, the target branch, the Mission
    branch). Status bytes merged into the lane from those branches do not
    count, however far they moved on after the lane was cut.
    """

    lane_branch: str
    mission: str
    paths: tuple[str, ...]
    commits: tuple[str, ...]
    code: str = LANE_STATUS_AUTHORED


@dataclass(frozen=True)
class LaneStatusNotExcluded:
    """A registered lane worktree without the status-file exclusion, and what to do about it."""

    worktree: Path
    lane_id: str
    detail: str
    remedy: str
    code: str = LANE_STATUS_NOT_EXCLUDED


def find_lane_status_authored(repo_root: Path) -> list[LaneStatusAuthored]:
    """Every live code-lane branch of every Mission carrying a lane-authored status change.

    The comparison covers the Mission's two status files only. A lane whose
    branch is gone, or none of whose status-surface branches resolves, is not
    a live lane this probe can judge and yields no finding.
    """
    from specify_cli.lanes.lane_checkout import mission_code_lanes

    findings: list[LaneStatusAuthored] = []
    for lane in mission_code_lanes(repo_root):
        finding = _probe_lane(repo_root, lane)
        if finding is not None:
            findings.append(finding)
    return findings


def _probe_lane(repo_root: Path, lane: MissionCodeLane) -> LaneStatusAuthored | None:
    if not _branch_exists(repo_root, lane.branch):
        return None
    bases = _status_source_branches(repo_root, lane)
    if not bases:
        return None
    own_commits = (lane.branch, "--not", *bases, "--", *lane.status_paths)
    commits = tuple(_git_stdout(repo_root, "log", "--no-merges", "--format=%H", *own_commits).split())
    if not commits:
        return None
    touched = set(_git_stdout(repo_root, "log", "--no-merges", "--format=", "--name-only", *own_commits).splitlines())
    paths = tuple(path for path in lane.status_paths if path in touched)
    return LaneStatusAuthored(lane_branch=lane.branch, mission=lane.mission, paths=paths, commits=commits)


def _status_source_branches(repo_root: Path, lane: MissionCodeLane) -> tuple[str, ...]:
    """The existing branches a lane's status bytes legitimately come from: coordination, target, Mission branch."""
    candidates = (lane.coordination_branch, lane.target_branch, lane.mission_branch)
    return tuple(dict.fromkeys(branch for branch in candidates if branch and _branch_exists(repo_root, branch)))


def find_lanes_lacking_exclusion(repo_root: Path, *, fix: bool) -> list[LaneStatusNotExcluded]:
    """Every registered lane worktree still lacking the status-file exclusion (FR-044).

    With *fix*, the exclusion is first applied wherever the upgrade migration
    would apply it (the same checks: a lane copy holding lane-only events, or
    a lane mid-merge or mid-rebase, is left untouched and still reported).

    Raises:
        MigrationStateUnreadableError: the worktree registry cannot be read.
    """
    from specify_cli.upgrade.migrations.m_4_0_0rc8_lane_checkout_status_exclusion import (
        lane_checkouts_lacking_exclusion,
        lane_exclusion_remedy,
    )

    return [
        LaneStatusNotExcluded(worktree=item.worktree, lane_id=item.lane_id, detail=item.render(), remedy=lane_exclusion_remedy(item))
        for item in lane_checkouts_lacking_exclusion(repo_root, fix=fix)
    ]


def _branch_exists(repo_root: Path, branch: str) -> bool:
    probe = subprocess.run(
        ["git", "-C", str(repo_root), "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        capture_output=True,
        check=False,
    )
    return probe.returncode == 0


def _git_stdout(repo_root: Path, *args: str) -> str:
    """Stdout of one read-only git command, or ``""`` when it fails."""
    result = subprocess.run(["git", "-C", str(repo_root), *args], capture_output=True, text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else ""


def _render_lane_status_authored(findings: Sequence[LaneStatusAuthored]) -> None:
    """Print each ``LANE_STATUS_AUTHORED`` finding on grep-able lines."""
    console.print("[yellow]⚠ Lane branches carry lane-authored status changes[/yellow]", soft_wrap=True)
    for finding in findings:
        console.print(
            f"  {finding.code}: {finding.lane_branch} (Mission {finding.mission}) changes {', '.join(finding.paths)} in commits {', '.join(finding.commits)}",
            soft_wrap=True,
        )
    console.print(
        "  A lane never changes status; the resolved status surface is the authority. "
        "Revert the change on the lane branch, or record the transitions with spec-kitty agent tasks move-task.",
        soft_wrap=True,
    )
    console.print()


def _render_lanes_not_excluded(findings: Sequence[LaneStatusNotExcluded]) -> None:
    """Print each ``LANE_STATUS_NOT_EXCLUDED`` finding with its remedy on grep-able lines."""
    console.print("[yellow]⚠ Lane worktrees still show the Mission status files[/yellow]", soft_wrap=True)
    for finding in findings:
        console.print(f"  {finding.code}: {finding.detail}", soft_wrap=True)
        console.print(f"    Remedy: {finding.remedy}", soft_wrap=True)
    console.print()


def _report_lane_findings(repo_root: Path, fix: bool) -> bool:
    """Render the two lane findings (after the safe exclusion fix when *fix*); True when any remains."""
    from specify_cli.upgrade.migrations.base import MigrationStateUnreadableError

    authored = find_lane_status_authored(repo_root)
    if authored:
        _render_lane_status_authored(authored)
    try:
        not_excluded = find_lanes_lacking_exclusion(repo_root, fix=fix)
    except MigrationStateUnreadableError as exc:
        console.print(f"[red]✗ Cannot read the worktree registry to check lane worktrees:[/red] {exc}", soft_wrap=True)
        return True
    if not_excluded:
        _render_lanes_not_excluded(not_excluded)
    return bool(authored or not_excluded)


def _render_sparse_finding(report: SparseCheckoutScanReport) -> None:
    """Render Quickstart Flow 1 finding output to the console.

    Kept separate from the command callback so tests can exercise the
    reporting surface directly. Uses ``soft_wrap=True`` to keep file
    paths on a single line regardless of terminal width — the doctor
    output contract is that affected paths are grep-able verbatim.
    """
    console.print(
        "[yellow]⚠ Legacy sparse-checkout state detected[/yellow]",
        soft_wrap=True,
    )
    if report.primary.is_active:
        console.print(f"  Primary: {report.primary.path}", soft_wrap=True)
        console.print("    core.sparseCheckout = true", soft_wrap=True)
        if report.primary.pattern_file_present and report.primary.pattern_file_path is not None:
            pf_rel = report.primary.pattern_file_path
            console.print(
                f"    pattern file: {pf_rel} ({report.primary.pattern_line_count} lines)",
                soft_wrap=True,
            )
    active_wts = [w for w in report.worktrees if w.is_blocking]
    if active_wts:
        console.print(f"  Lane worktrees: {len(active_wts)} affected", soft_wrap=True)
        for wt in active_wts:
            console.print(f"    {wt.path}", soft_wrap=True)
    console.print()
    console.print("  Why this matters:", soft_wrap=True)
    console.print(
        "    spec-kitty v3.0+ removed sparse-checkout support but does not ship a",
        soft_wrap=True,
    )
    console.print(
        "    migration. This state can cause silent data loss during mission merge",
        soft_wrap=True,
    )
    console.print("    and broken lane worktrees on agent action implement.", soft_wrap=True)
    console.print("    See spec-kitty/spec-kitty#588.", soft_wrap=True)
    console.print()
    console.print("  Fix:", soft_wrap=True)
    console.print(f"    {_FIX_HINT}", soft_wrap=True)


def _render_remediation_plan(report: SparseCheckoutScanReport) -> None:
    """Print the numbered step-by-step plan operators see before consenting."""
    console.print("Proceed? This will:")
    step = 1
    console.print(f"  {step}. git sparse-checkout disable (primary)")
    step += 1
    console.print(f"  {step}. git config --unset core.sparseCheckout (primary)")
    step += 1
    console.print(f"  {step}. rm {report.primary.path}/.git/info/sparse-checkout (primary)")
    step += 1
    console.print(f"  {step}. git checkout HEAD -- . (primary)")
    for wt in report.worktrees:
        if not wt.is_blocking:
            continue
        step += 1
        console.print(f"  {step}. repeat steps 1–4 in {wt.path}")


def _resolve_repo_root() -> Path:
    """Resolve the project root or exit(1) with the standard message."""
    try:
        repo_root: Path | None = locate_project_root()
    except Exception as exc:
        console.print("[red]Error:[/red] Not in a spec-kitty project")
        raise typer.Exit(1) from exc
    if repo_root is None:
        console.print("[red]Error:[/red] Not in a spec-kitty project")
        raise typer.Exit(1)
    return repo_root


def _emit_clean_state(fix: bool) -> None:
    """Emit the no-state message for both modes and exit 0."""
    if fix:
        console.print("No sparse-checkout state to remediate.")
    else:
        console.print("[green]✓ No legacy sparse-checkout state detected.[/green]")
    raise typer.Exit(0)


def _prompt_consent() -> bool:
    """Prompt the operator once for plan consent; return True iff they consented."""
    try:
        response = input("[y/N] ").strip().lower()
    except EOFError:
        response = ""
    return response == "y"


def _render_remediation_results(
    results: Sequence[SparseCheckoutRemediationResult],
) -> bool:
    """Render per-path remediation results; return True iff any path failed."""
    any_failure = False
    for r in results:
        if r.success:
            steps = len(r.steps_completed)
            console.print(f"[green]✓[/green] {r.path}: remediated ({steps} steps, clean verify)")
        else:
            any_failure = True
            detail = r.error_detail or "unknown error"
            step = r.error_step or "unknown step"
            console.print(f"[red]✗[/red] {r.path}: failed at {step} — {detail}")
    return any_failure


def _emit_dirty_refusal(
    results: Sequence[SparseCheckoutRemediationResult],
) -> None:
    """Emit the dirty-tree refusal message and exit 1."""
    console.print("[red]✗ Cannot remediate: uncommitted changes detected.[/red]")
    for r in results:
        if r.dirty_before_remediation:
            console.print(f"  {r.path}")
    console.print()
    console.print("  Commit or stash your changes and retry:")
    console.print("    git stash push -u")
    console.print(f"    {_FIX_HINT}")
    raise typer.Exit(1)


def _apply_sparse_remediation(report: SparseCheckoutScanReport) -> None:
    """Interactive --fix arm: show plan, prompt, remediate, render results.

    Exits 0 on operator abort or full success; exits 1 on dirty-tree refusal
    or any per-path failure.
    """
    from specify_cli.git.sparse_checkout_remediation import remediate

    _render_remediation_plan(report)
    if not _prompt_consent():
        console.print("Aborted — no changes made.")
        raise typer.Exit(0)

    # Consent already obtained for the whole plan; pass ``interactive=False``
    # so the remediator does not re-prompt per path.
    rep = remediate(report, interactive=False, confirm=None)
    results = [rep.primary_result, *rep.worktree_results]

    if any(r.dirty_before_remediation for r in results):
        _emit_dirty_refusal(results)

    any_failure = _render_remediation_results(results)
    raise typer.Exit(0 if rep.overall_success and not any_failure else 1)


def run_sparse_checkout(fix: bool) -> None:
    """Entry point for ``doctor sparse-checkout`` (0 clean / 1 state-or-CI-refusal)."""
    from specify_cli.git.sparse_checkout import scan_repo

    repo_root = _resolve_repo_root()
    report = scan_repo(repo_root)
    lane_findings = _report_lane_findings(repo_root, fix)

    if not report.any_blocking:
        if lane_findings:
            raise typer.Exit(1)
        _emit_clean_state(fix)

    # Detection-only surface: print the finding and exit non-zero so CI scripts
    # that invoke `doctor sparse-checkout` can gate on the result.
    if not fix:
        _render_sparse_finding(report)
        raise typer.Exit(1)

    # --fix path: route by interactivity.
    if not _is_interactive_environment():
        # FR-023: CI/non-TTY surface is a single deterministic pointer line so
        # scripts can grep it reliably. No state mutation; non-zero exit.
        # Bypass Rich's auto-wrapping (which splits on terminal width and breaks
        # grep) by using the stdlib print.
        print(f"sparse-checkout --fix requires an interactive terminal; run '{_FIX_HINT}' from a local TTY to remediate.")
        raise typer.Exit(1)

    _apply_sparse_remediation(report)
