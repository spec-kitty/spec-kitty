"""TeamSpace mission-state readiness report and connection gate helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
import typer

from specify_cli.core import hosted_posture
from specify_cli.core.constants import KITTY_SPECS_DIR
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


def report_teamspace_mission_state_blockers(project_path: Path, *, console: Console) -> RepairOutcome:
    """Report (never repair) TeamSpace mission-state blockers for ``upgrade``.

    ``spec-kitty upgrade``, including ``--yes``, never runs the mission-state
    repair (ADR 2026-10-07-1): ``spec-kitty doctor mission-state --fix`` is the
    only consent path. With hosted drain off (the default) readiness is not
    evaluated at all and nothing is printed. With drain on, the blocker count,
    the finding codes and the doctor command are printed. Never raises
    ``typer.Exit`` (D-9, C3), so a reported blocker never changes the exit code.
    """
    if not hosted_posture.drain_posture(project_root=project_path).enabled:
        return RepairOutcome(pending=True, message="Hosted drain is off: mission-state readiness was not evaluated.")

    readiness = check_teamspace_mission_state_readiness(project_path)
    if not readiness.blocked:
        return RepairOutcome(pending=True, message="No TeamSpace mission-state blockers found.")

    _print_notice(
        readiness,
        console=console,
        title="TeamSpace Mission-State Migration",
        border_style="yellow",
    )
    console.print("[dim]`spec-kitty upgrade` never repairs mission state; only `spec-kitty doctor mission-state --fix` does.[/dim]")
    if readiness.audit_error:
        return RepairOutcome(
            reported=True,
            message=f"Could not verify TeamSpace mission-state readiness: {readiness.audit_error}",
        )
    return RepairOutcome(reported=True, message="TeamSpace mission-state blockers reported; not repaired.")
