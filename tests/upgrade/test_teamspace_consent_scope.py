"""Seam unit tests for the report-only mission-state gate (C3, D-9, FR-001/002/011).

``upgrade`` never repairs mission state (ADR 2026-10-07-1, reversing the #4775
decision that ``--yes`` consents to the repair). With hosted drain on the gate
reports the blocker count, the finding codes and ``doctor mission-state --fix``;
with drain off readiness is not evaluated and nothing is printed. In both
cases ``repair_repo`` is never called and no consent prompt exists.
"""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import typer
from rich.console import Console

from specify_cli.cli.commands import _teamspace_mission_state_gate as gate
from specify_cli.cli.commands._teamspace_mission_state_gate import (
    MissionStateReportOutcome,
    TeamspaceMissionStateReadiness,
    report_teamspace_mission_state_blockers,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_DOCTOR_FIX = "spec-kitty doctor mission-state --fix"


def _blocked(repo_root: Path, *, audit_error: str | None = None) -> TeamspaceMissionStateReadiness:
    return TeamspaceMissionStateReadiness(
        repo_root=repo_root,
        total_missions=1,
        blocker_count=2,
        missions_with_blockers=1,
        blocker_codes=("teamspace-blocker",),
        audit_error=audit_error,
    )


def _arm(monkeypatch: pytest.MonkeyPatch, readiness: TeamspaceMissionStateReadiness) -> tuple[MagicMock, MagicMock]:
    """Return (readiness spy, repair_repo spy); the prompt cannot be reached."""
    readiness_spy = MagicMock(name="readiness", return_value=readiness)
    monkeypatch.setattr(gate, "check_teamspace_mission_state_readiness", readiness_spy)
    repair_spy = MagicMock(name="repair_repo")
    monkeypatch.setattr("specify_cli.migration.mission_state.repair_repo", repair_spy)
    monkeypatch.setattr(typer, "confirm", MagicMock(side_effect=AssertionError("the report-only gate must never prompt")))
    return readiness_spy, repair_spy


def _run(project: Path) -> tuple[MissionStateReportOutcome, str]:
    buffer = io.StringIO()
    outcome = report_teamspace_mission_state_blockers(project, console=Console(file=buffer, width=200))
    return outcome, buffer.getvalue()


def test_blocked_under_drain_reports_count_codes_and_doctor_command_without_repairing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, repair = _arm(monkeypatch, _blocked(tmp_path))

    outcome, output = _run(tmp_path)

    repair.assert_not_called()
    assert outcome.reported is True
    assert outcome.pending is False
    assert outcome.failed is False
    assert "Found 2 TeamSpace blocker(s)" in output
    assert "teamspace-blocker" in output
    assert _DOCTOR_FIX in output
    assert "cleared" not in output


@pytest.mark.real_drain_posture
def test_drain_off_does_not_evaluate_readiness_and_prints_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The real, file-based posture reader runs: no config means drain is off."""
    readiness, repair = _arm(monkeypatch, _blocked(tmp_path))

    outcome, output = _run(tmp_path)

    readiness.assert_not_called()
    repair.assert_not_called()
    assert outcome.pending is True
    assert outcome.reported is False
    assert output == ""


def test_not_blocked_is_pending_and_silent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, repair = _arm(monkeypatch, TeamspaceMissionStateReadiness(repo_root=tmp_path))

    outcome, output = _run(tmp_path)

    repair.assert_not_called()
    assert outcome.pending is True
    assert output == ""


def test_audit_error_is_reported_not_repaired(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, repair = _arm(monkeypatch, _blocked(tmp_path, audit_error="boom"))

    outcome, output = _run(tmp_path)

    repair.assert_not_called()
    assert outcome.reported is True
    assert "boom" in outcome.message
    assert "boom" in output


def test_report_never_raises_typer_exit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """D-9/C3: a reported blocker never changes the upgrade's exit code."""
    _arm(monkeypatch, _blocked(tmp_path))

    try:
        _run(tmp_path)
    except typer.Exit:
        pytest.fail("report_teamspace_mission_state_blockers must never raise typer.Exit")
