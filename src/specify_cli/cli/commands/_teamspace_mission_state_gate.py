"""TeamSpace mission-state migration prompt and connection gate helpers."""

from __future__ import annotations

from specify_cli.core.constants import KITTY_SPECS_DIR
from dataclasses import dataclass
from pathlib import Path
import sys

import typer
from rich.console import Console
from rich.panel import Panel

from specify_cli.upgrade.outcome import RepairOutcome


@dataclass(frozen=True)
class TeamspaceMissionStateReadiness:
    """Readiness summary for TeamSpace historical mission-state import."""

    repo_root: Path
    total_missions: int = 0
    blocker_count: int = 0
    missions_with_blockers: int = 0
    blocker_codes: tuple[str, ...] = ()
    audit_error: str | None = None

    @property
    def migration_pending(self) -> bool:
        return self.blocker_count > 0

    @property
    def blocked(self) -> bool:
        return self.migration_pending or self.audit_error is not None


def check_teamspace_mission_state_readiness(repo_root: Path) -> TeamspaceMissionStateReadiness:
    """Return mission-state readiness for TeamSpace connect/import paths."""
    repo_root = repo_root.resolve()
    if not (repo_root / KITTY_SPECS_DIR).is_dir():
        return TeamspaceMissionStateReadiness(repo_root=repo_root)

    try:
        from specify_cli.audit import AuditOptions, run_audit
        from specify_cli.audit.models import is_teamspace_blocker

        report = run_audit(AuditOptions(repo_root=repo_root))
    except Exception as exc:  # noqa: BLE001 - connection paths fail closed on unknown readiness
        return TeamspaceMissionStateReadiness(
            repo_root=repo_root,
            audit_error=str(exc),
        )

    blocker_codes: set[str] = set()
    blocker_count = 0
    missions_with_blockers = 0
    for mission in report.missions:
        mission_has_blocker = False
        for finding in mission.findings:
            if not is_teamspace_blocker(finding):
                continue
            blocker_count += 1
            blocker_codes.add(finding.code)
            mission_has_blocker = True
        if mission_has_blocker:
            missions_with_blockers += 1

    return TeamspaceMissionStateReadiness(
        repo_root=repo_root,
        total_missions=int(report.repo_summary.get("total_missions", len(report.missions))),
        blocker_count=blocker_count,
        missions_with_blockers=missions_with_blockers,
        blocker_codes=tuple(sorted(blocker_codes)),
    )


def _guidance_lines(readiness: TeamspaceMissionStateReadiness) -> list[str]:
    if readiness.audit_error:
        return [
            "Spec Kitty could not verify local mission-state readiness.",
            f"Audit error: {readiness.audit_error}",
            "",
            "Run the audit before connecting to TeamSpace:",
            "  spec-kitty doctor mission-state --audit --fail-on teamspace-blocker",
        ]

    codes = ", ".join(readiness.blocker_codes) if readiness.blocker_codes else "unknown"
    return [
        "TeamSpace mission-state migration is required before connecting.",
        (f"Found {readiness.blocker_count} TeamSpace blocker(s) across {readiness.missions_with_blockers} mission(s)."),
        f"Finding codes: {codes}",
        "",
        "Recommended sequence:",
        "  spec-kitty doctor mission-state --audit --fail-on teamspace-blocker",
        "  spec-kitty doctor mission-state --fix",
        "  spec-kitty doctor mission-state --teamspace-dry-run",
    ]


def _print_notice(
    readiness: TeamspaceMissionStateReadiness,
    *,
    console: Console,
    title: str,
    border_style: str,
) -> None:
    console.print(
        Panel(
            "\n".join(_guidance_lines(readiness)),
            title=title,
            border_style=border_style,
            expand=False,
        )
    )


def enforce_teamspace_mission_state_ready(*, console: Console, command_name: str) -> None:
    """Block TeamSpace connect/sync commands until local mission-state is ready."""
    try:
        from specify_cli.core.paths import locate_project_root

        repo_root = locate_project_root()
    except Exception:  # noqa: BLE001 - outside a project is not a project migration problem
        repo_root = None

    if repo_root is None:
        return

    readiness = check_teamspace_mission_state_readiness(repo_root)
    if not readiness.blocked:
        return

    _print_notice(
        readiness,
        console=console,
        title="TeamSpace Migration Required",
        border_style="red",
    )
    console.print(f"[red]Blocked:[/red] `{command_name}` will not connect until this migration is complete.")
    raise typer.Exit(1)


def safe_confirm(prompt: str, *, default: bool) -> bool:
    """Prompt for confirmation, declining safely on abort or EOF (NFR-005).

    Wraps ``typer.confirm`` and explicitly catches ``typer.Abort`` (typer's
    public surface for the exception ``typer.confirm`` raises on Ctrl-C or
    when reading hits EOF — do not reference ``click.exceptions.Abort``
    directly; TID251 bans it because it is a distinct class from typer's own
    in typer>=0.26) and ``EOFError`` itself, folding either into a plain
    decline (``False``) rather than letting the exception crash an
    otherwise-successful upgrade run. Deliberately NOT a bare
    ``except Exception``: any other exception raised while prompting is a
    real bug and must propagate, not be silently swallowed as "declined".
    """
    try:
        return typer.confirm(prompt, default=default)
    except (typer.Abort, EOFError):
        return False


def _should_run_repair(*, repair_opt_in: bool) -> bool:
    """Decide whether to run the mission-state repair (its own consent scope).

    NFR-003/FR-005/FR-006: this decision reads its OWN explicit opt-in — it
    is never derived from the unrelated migration-apply consent
    (``--yes``/``--force``) a caller may hold; a caller is free to choose to
    pass the SAME value for both (as the ``upgrade.py`` call site now does,
    reconciling FR-017's "``--yes`` is fully non-interactive" promise with
    this decision's own consent requirement), but this function itself has
    no such parameter and structurally cannot read that unrelated flag.
    An explicit opt-in short-circuits the prompt. A non-interactive
    session (no TTY) with no opt-in denies WITHOUT aborting: ``safe_confirm``
    declines instead of letting ``typer.confirm``'s ``typer.Abort`` (raised
    when there is no TTY / stdin hits EOF) sink an unrelated,
    already-successful upgrade run.
    """
    if repair_opt_in:
        return True
    if not sys.stdin.isatty():
        return False
    return safe_confirm(
        "Run `spec-kitty doctor mission-state --fix` now?",
        default=False,
    )


def offer_teamspace_mission_state_migration(
    project_path: Path,
    *,
    console: Console,
    dry_run: bool,
    assume_yes: bool = False,
    repair_opt_in: bool = False,
) -> RepairOutcome:
    """Surface and optionally run the TeamSpace mission-state migration.

    Never raises ``typer.Exit`` (D-9, C3) — every outcome, including repair
    failures and a still-blocked post-repair state, is folded into the
    returned :class:`RepairOutcome` for the finalizer to fold into
    ``UpgradeOutcome`` without sinking an otherwise-successful upgrade
    (FR-014).

    ``assume_yes`` is the caller's migration-apply consent flag
    (``--yes``/``--force``). It is accepted here only so existing call sites
    keep working; it is deliberately NEVER read BY THIS FUNCTION (nor by
    :func:`_should_run_repair`) to decide whether to run the repair
    (NFR-003/FR-005/FR-006) — that decision has its OWN explicit opt-in,
    ``repair_opt_in``.

    Reconciling FR-017 ("``--yes``/``--force`` is fully non-interactive")
    with NFR-003 ("the repair sub-gate has its own consent"): a CALLER may
    choose to pass the same value for both ``assume_yes`` and
    ``repair_opt_in`` — the ``upgrade.py`` finalizer now does exactly this,
    wiring ``repair_opt_in=confirm`` alongside ``assume_yes=confirm`` — so
    that ``--yes`` also opts into the repair sub-gate end to end. That is a
    call-site decision, not a derivation performed here: this function still
    never inspects ``assume_yes`` to make the repair decision itself. See
    :func:`_should_run_repair`.
    """
    _ = assume_yes  # intentionally unread — see docstring (NFR-003)
    readiness = check_teamspace_mission_state_readiness(project_path)
    if not readiness.blocked:
        return RepairOutcome(pending=True, message="No TeamSpace mission-state blockers found.")

    _print_notice(
        readiness,
        console=console,
        title="TeamSpace Mission-State Migration",
        border_style="yellow",
    )

    if readiness.audit_error:
        return RepairOutcome(
            pending=True,
            message=f"Could not verify TeamSpace mission-state readiness: {readiness.audit_error}",
        )

    if dry_run:
        console.print("[dim]Dry run: mission-state repair was not run.[/dim]")
        return RepairOutcome(pending=True, message="Dry run: mission-state repair was not run.")

    if not _should_run_repair(repair_opt_in=repair_opt_in):
        console.print("[yellow]Skipped TeamSpace mission-state repair.[/yellow]")
        return RepairOutcome(declined=True, message="TeamSpace mission-state repair declined.")

    from specify_cli.migration.mission_state import MissionStateRepairError, repair_repo

    try:
        report = repair_repo(project_path)
    except MissionStateRepairError as exc:
        console.print(f"[red]Mission-state repair failed:[/red] {exc}")
        return RepairOutcome(ran=True, failed=True, message=str(exc))
    except Exception as exc:  # noqa: BLE001 - repair boundary must not crash the upgrade tail
        console.print(f"[red]Mission-state repair encountered an unexpected error:[/red] {exc}")
        return RepairOutcome(ran=True, failed=True, message=str(exc))

    summary = report.to_dict()["summary"]
    if not isinstance(summary, dict):
        return RepairOutcome(
            ran=True,
            failed=True,
            message=f"Unexpected repair report summary type: {type(summary)!r}",
        )
    console.print(
        "[green]Mission-state repair complete[/green] "
        f"(updated={summary['missions_updated']}, "
        f"unchanged={summary['missions_unchanged']}, "
        f"errors={summary['missions_error']})."
    )
    console.print(f"Manifest: {report.manifest_path}")

    post_repair = check_teamspace_mission_state_readiness(project_path)
    if post_repair.blocked:
        _print_notice(
            post_repair,
            console=console,
            title="TeamSpace Migration Still Blocked",
            border_style="red",
        )
        return RepairOutcome(
            ran=True,
            failed=True,
            message="TeamSpace mission-state blockers remain after repair.",
        )

    console.print("[green]TeamSpace mission-state blockers cleared.[/green]")
    return RepairOutcome(ran=True, message="TeamSpace mission-state blockers cleared.")
