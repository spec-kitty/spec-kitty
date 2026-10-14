"""TeamSpace mission-state readiness report helper for ``upgrade``.

The hosted TeamSpace connect/import surface was removed from open-core (#6164).
The only surviving entry point is :func:`report_teamspace_mission_state_blockers`,
which ``spec-kitty upgrade`` calls: with the hosted surface gone there is no
TeamSpace to import historical mission state into, so it evaluates nothing and
returns a benign pending outcome (the same outcome ``upgrade`` already received
when hosted drain was off, which was the default — so ``upgrade``'s behaviour is
unchanged). ``spec-kitty doctor mission-state --fix`` remains the only
mission-state repair path (ADR 2026-10-07-1).
"""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from specify_cli.upgrade.outcome import MissionStateReportOutcome


def report_teamspace_mission_state_blockers(project_path: Path, *, console: Console) -> MissionStateReportOutcome:
    """Report (never repair) TeamSpace mission-state blockers for ``upgrade``.

    The hosted TeamSpace surface was removed (#6164), so nothing is evaluated
    and nothing is printed; this returns a pending outcome and never raises
    ``typer.Exit`` (D-9, C3), so it never changes the exit code.
    """
    del project_path, console  # hosted surface removed: nothing to evaluate or print
    return MissionStateReportOutcome(pending=True, message="Hosted TeamSpace surface removed: mission-state readiness was not evaluated.")
