"""Focused per-helper tests for ``_mission_state_doctor`` (WP06, #2059).

Cover mode validation (exclusivity → exit 2), fail-on resolution, audit-root
resolution, the audit-fail gate, and the dispatch entrypoint, plus the rich
report renderer, so each branch is exercised directly. >=90% coverage target.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
import typer

from specify_cli.cli.commands import _mission_state_doctor as ms

pytestmark = [pytest.mark.fast]


# --- _validate_modes ---------------------------------------------------------


def test_validate_modes_none_exits_0() -> None:
    with pytest.raises(typer.Exit) as exc:
        ms._validate_modes(False, False)
    assert exc.value.exit_code == 0


def test_validate_modes_multiple_exits_2() -> None:
    with pytest.raises(typer.Exit) as exc:
        ms._validate_modes(True, True)
    assert exc.value.exit_code == 2


def test_validate_modes_single() -> None:
    assert ms._validate_modes(True, False) is ms._MissionStateMode.AUDIT
    assert ms._validate_modes(False, True) is ms._MissionStateMode.FIX


# --- _resolve_fail_on --------------------------------------------------------


def test_resolve_fail_on_none() -> None:
    assert ms._resolve_fail_on(None) == (None, False)


def test_resolve_fail_on_teamspace_blocker() -> None:
    sev, blocker = ms._resolve_fail_on("teamspace-blocker")
    assert sev is None and blocker is True


def test_resolve_fail_on_valid_severity() -> None:
    sev, blocker = ms._resolve_fail_on("error")
    assert sev is not None and blocker is False


def test_resolve_fail_on_invalid_exits_2() -> None:
    with pytest.raises(typer.Exit) as exc:
        ms._resolve_fail_on("nonsense")
    assert exc.value.exit_code == 2


# --- _resolve_audit_root -----------------------------------------------------


def test_resolve_audit_root_include_and_fixture_conflict() -> None:
    with pytest.raises(typer.Exit) as exc:
        ms._resolve_audit_root(Path("/x"), include_fixtures=True)
    assert exc.value.exit_code == 2


def test_resolve_audit_root_missing_bundled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ms, "_audit_fixture_root", lambda: Path("/nonexistent-fixtures"))
    with pytest.raises(typer.Exit) as exc:
        ms._resolve_audit_root(None, include_fixtures=True)
    assert exc.value.exit_code == 2


def test_resolve_audit_root_no_project(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ms, "locate_project_root", lambda: None)
    with pytest.raises(typer.Exit) as exc:
        ms._resolve_audit_root(None, include_fixtures=False)
    assert exc.value.exit_code == 1


def test_resolve_audit_root_locate_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom() -> Path:
        raise RuntimeError("x")

    monkeypatch.setattr(ms, "locate_project_root", _boom)
    with pytest.raises(typer.Exit) as exc:
        ms._resolve_audit_root(None, include_fixtures=False)
    assert exc.value.exit_code == 1


def test_resolve_audit_root_fixture_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # No project root, but a fixture_dir supplied → repo_root = fixture_dir.parent.
    fixture = tmp_path / "fx"
    fixture.mkdir()
    monkeypatch.setattr(ms, "locate_project_root", lambda: None)
    repo_root, resolved = ms._resolve_audit_root(fixture, include_fixtures=False)
    assert repo_root == fixture.parent
    assert resolved == fixture


def test_resolve_audit_root_happy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(ms, "locate_project_root", lambda: tmp_path)
    repo_root, resolved = ms._resolve_audit_root(None, include_fixtures=False)
    assert repo_root == tmp_path
    assert resolved is None


# --- _audit_fail_gate --------------------------------------------------------


@dataclass
class _Finding:
    severity: Any
    code: str = "X001"


@dataclass
class _MissionResult:
    findings: list[_Finding] = field(default_factory=list)
    status: str = "ok"
    mission_slug: str = "083-a"


@dataclass
class _Report:
    missions: list[_MissionResult] = field(default_factory=list)
    repo_summary: dict[str, int] = field(
        default_factory=lambda: {
            "total_missions": 1,
            "missions_with_errors": 0,
            "missions_with_warnings": 0,
            "teamspace_blockers": 0,
        }
    )


def test_audit_fail_gate_no_gate() -> None:
    # No severity and no blocker → never raises.
    ms._audit_fail_gate(_Report(missions=[_MissionResult()]), None, False)


def test_audit_fail_gate_severity_triggers() -> None:
    from specify_cli.audit import Severity

    report = _Report(missions=[_MissionResult(findings=[_Finding(Severity.ERROR)])])
    with pytest.raises(typer.Exit) as exc:
        ms._audit_fail_gate(report, Severity.ERROR, False)
    assert exc.value.exit_code == 1


# --- _emit_json_error --------------------------------------------------------


def test_emit_json_error(capsys: pytest.CaptureFixture[str]) -> None:
    ms._emit_json_error("BOOM", handle="x")
    out = capsys.readouterr().out
    assert "BOOM" in out
    assert "handle" in out


# --- _print_rich_audit_report ------------------------------------------------


def test_print_rich_audit_report_clean() -> None:
    from specify_cli.audit import RepoAuditReport

    # A report with no findings prints the clean message.
    report = RepoAuditReport(missions=[], shape_counters={}, repo_summary={})
    ms._print_rich_audit_report(report)


# --- run_mission_state dispatch ----------------------------------------------


def test_run_mission_state_no_mode_exits_0() -> None:
    with pytest.raises(typer.Exit) as exc:
        ms.run_mission_state(
            audit=False,
            fix=False,
            json_output=False,
            mission=None,
            fail_on=None,
            fixture_dir=None,
            include_fixtures=False,
            manifest_path=None,
            allow_dirty=False,
        )
    assert exc.value.exit_code == 0


def test_run_mission_state_dispatches_audit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(ms, "locate_project_root", lambda: tmp_path)
    called: dict[str, Any] = {}
    monkeypatch.setattr(
        ms,
        "_run_audit_mode",
        lambda *a: called.setdefault("audit", a),
    )
    ms.run_mission_state(
        audit=True,
        fix=False,
        json_output=False,
        mission=None,
        fail_on=None,
        fixture_dir=None,
        include_fixtures=False,
        manifest_path=None,
        allow_dirty=False,
    )
    assert "audit" in called


def test_run_mission_state_dispatches_fix(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(ms, "locate_project_root", lambda: tmp_path)
    called: dict[str, Any] = {}
    monkeypatch.setattr(ms, "_run_mission_repair", lambda *a: called.setdefault("fix", a))
    ms.run_mission_state(
        audit=False,
        fix=True,
        json_output=False,
        mission=None,
        fail_on=None,
        fixture_dir=None,
        include_fixtures=False,
        manifest_path=None,
        allow_dirty=False,
    )
    assert "fix" in called


def test_print_rich_audit_report_with_findings() -> None:
    from specify_cli.audit import RepoAuditReport
    from specify_cli.audit.models import (
        MissionAuditResult,
        MissionFinding,
        Severity,
    )

    finding = MissionFinding(code="X001", severity=Severity.ERROR, artifact_path="m.json")
    result = MissionAuditResult(
        mission_slug="083-a",
        mission_dir=Path("/nonexistent/083-a"),
        findings=[finding],
    )
    report = RepoAuditReport(
        missions=[result],
        shape_counters={},
        repo_summary={
            "total_missions": 1,
            "missions_with_errors": 1,
            "missions_with_warnings": 0,
            "teamspace_blockers": 0,
        },
    )
    ms._print_rich_audit_report(report)


def test_audit_fixture_root_returns_path() -> None:
    root = ms._audit_fixture_root()
    assert root.name == "fixtures"


def test_run_audit_mode_mission_not_found(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import specify_cli.audit as audit_mod
    from specify_cli.context.mission_resolver import MissionNotFoundError

    def _boom(_opts: Any) -> Any:
        raise MissionNotFoundError("nope")

    monkeypatch.setattr(audit_mod, "run_audit", _boom)
    with pytest.raises(typer.Exit) as exc:
        ms._run_audit_mode(tmp_path, None, "999-x", None, False, True)
    assert exc.value.exit_code == 1


def test_run_audit_mode_mission_not_found_human(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import specify_cli.audit as audit_mod
    from specify_cli.context.mission_resolver import MissionNotFoundError

    def _boom(_opts: Any) -> Any:
        raise MissionNotFoundError("nope")

    monkeypatch.setattr(audit_mod, "run_audit", _boom)
    # Human (non-JSON) branch of the not-found handler.
    with pytest.raises(typer.Exit) as exc:
        ms._run_audit_mode(tmp_path, None, "999-x", None, False, False)
    assert exc.value.exit_code == 1
