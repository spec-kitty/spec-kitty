"""Mission-review command package.

Public entry: review_mission()
Internal modules:
  _diagnostics.py   — MissionReviewDiagnostic StrEnum (WP03)
  _mode.py          — MissionReviewMode + resolve_mode() (WP03)
  _issue_matrix.py  — issue-matrix validator (WP03)
  _lane_gate.py     — Gate 1: WP lane consistency check
  _dead_code.py     — Gate 2: dead-code scan
  _ble001_audit.py  — Gate 3: BLE001 broad-except audit
  _report.py        — Gate 4: report writer

See: src/specify_cli/cli/commands/review/ERROR_CODES.md (authored by WP03)
"""

from __future__ import annotations

import json
import subprocess  # noqa: F401  (monkeypatched in tests)
from pathlib import Path
from typing import Annotated, Literal

from specify_cli.mission_metadata import load_meta_or_empty

import typer
from rich.console import Console

from specify_cli.cli.commands._test_env_check import (  # noqa: F401
    ENV_SKEW_DIAGNOSTIC_CODE,
    ENV_SKEW_REMEDIATION,
    EnvSkew,
    PackageSkew,
    TestExtraMissing,
    assert_pytest_available,
    assert_typer_click_lock_parity,
    format_env_skew_message,
)
from specify_cli.compat._detect.install_method import InstallMethod  # noqa: F401
from specify_cli.compat._detect.runtime import InstalledCliRuntime, detect_runtime
from specify_cli.compat.remediation import RemediationCommand, plan_remediation, RemediationIntent
from specify_cli.cli.selector_resolution import resolve_mission_handle  # noqa: F401
from specify_cli.task_utils import TaskCliError, find_repo_root  # noqa: F401
from specify_cli.tasks.issue_matrix_migration import issue_matrix_artifact_present
from specify_cli.tasks.issue_reference_discovery import discover_issue_references
from specify_cli.version_utils import get_version  # noqa: F401

from ._ble001_audit import (  # noqa: F401
    Ble001SuppressionFinding,
    audit_auth_storage_ble001_line,
    collect_auth_storage_ble001_findings,
)
from ._dead_code import scan_dead_code  # noqa: F401
from ._diagnostics import MissionReviewDiagnostic  # noqa: F401
from ._issue_matrix import validate_issue_matrix  # noqa: F401
from ._lane_gate import check_wp_lanes  # noqa: F401
from ._mode import MissionReviewMode, ModeMismatchError, resolve_mode  # noqa: F401
from ._report import GateRecord, write_review_report  # noqa: F401


def _fail_missing_test_extra(console: object) -> None:
    import sys

    diagnostic_code = MissionReviewDiagnostic.TEST_EXTRA_MISSING
    remediation = _missing_test_extra_remediation()
    diagnostic = {
        "diagnostic_code": str(diagnostic_code),
        "message": (f"pytest is not importable from the active Python interpreter. Run `{remediation}` to install pytest into that interpreter, then retry."),
        "remediation": remediation,
    }
    console.print(  # type: ignore[attr-defined]
        f"[red]Error:[/red] {diagnostic_code}: {diagnostic['message']}"
    )
    sys.stdout.write(json.dumps(diagnostic) + "\n")
    raise typer.Exit(1)


def _missing_test_extra_remediation() -> str:
    """Return the repair command for the missing [test] extra.

    Uses detect_runtime() (CHK032: never raises) and plan_remediation()
    to produce a platform-appropriate reinstall command.  For UV_TOOL
    installs the command preserves install provenance (directory / editable
    / path / git / url / injected deps) and adds pytest via ``--with pytest``
    — never silently re-pinning a source install to the PyPI release
    (FR-019 / SC-003 / issue #1358; SC-001: single receipt read per
    invocation via detect_runtime()).  ``target_version`` only pins the
    receipt-absent PyPI fallback; receipt-derived provenance is authoritative.
    If render() raises ValueError (e.g. CHK028 path-safety violation),
    returns cmd.note or a safe guidance fallback.  For all other install
    methods returns ``uv sync --extra test``.
    """
    runtime: InstalledCliRuntime = detect_runtime()
    if runtime.install_method != InstallMethod.UV_TOOL:
        return "uv sync --extra test"
    cmd: RemediationCommand = plan_remediation(runtime, RemediationIntent.REINSTALL_WITH_TEST, target_version=get_version())
    try:
        rendered: str = cmd.render(runtime.platform)
        return rendered
    except ValueError:
        note: str | None = cmd.note
        return note if note is not None else "see spec-kitty docs"


def _check_env_skew(console: object, repo_root: Path) -> list[PackageSkew]:
    """Run the typer/click lock-parity preflight (FR-001).

    Warn-loud by default: divergence from ``uv.lock`` is printed as a
    warning and review proceeds. Fail-closed is opt-in via
    ``SPEC_KITTY_ENV_SKEW_FAIL_CLOSED`` (see
    ``assert_typer_click_lock_parity``), in which case this exits like the
    missing-pytest preflight does.
    """
    import sys

    try:
        mismatches = assert_typer_click_lock_parity(repo_root)
    except EnvSkew as exc:
        # EnvSkew carries the diagnostic code in args[0] and the already
        # human-formatted message (format_env_skew_message() output) in
        # args[1] -- NOT str(exc), which for a 2-arg exception renders the
        # raw args tuple repr (e.g. "('MISSION_REVIEW_ENV_SKEW', '...')")
        # instead of the clean multi-line diagnostic.
        skew_message: str = str(exc.args[1])
        diagnostic = {
            "diagnostic_code": ENV_SKEW_DIAGNOSTIC_CODE,
            "message": skew_message,
            "remediation": ENV_SKEW_REMEDIATION,
        }
        console.print(f"[red]Error:[/red] {diagnostic['message']}")  # type: ignore[attr-defined]
        sys.stdout.write(json.dumps(diagnostic) + "\n")
        raise typer.Exit(1) from exc
    if mismatches:
        console.print(  # type: ignore[attr-defined]
            f"  [yellow]![/yellow]  {format_env_skew_message(mismatches)}"
        )
    return mismatches


def _resolve_repo_root(console: object) -> Path:
    try:
        root: Path = find_repo_root()
        return root
    except TaskCliError as exc:
        console.print(f"[red]Error:[/red] {exc}")  # type: ignore[attr-defined]
        raise typer.Exit(2) from exc


def _require_mission_handle(mission: str, console: object) -> str:
    handle = mission.strip()
    if not handle:
        console.print("[red]Error:[/red] --mission is required.")  # type: ignore[attr-defined]
        raise typer.Exit(2)
    return handle


def _resolve_mode_or_exit(
    *,
    console: object,
    cli_mode: str | None,
    baseline_merge_commit: str | None,
) -> tuple[MissionReviewMode, bool]:
    try:
        result: tuple[MissionReviewMode, bool] = resolve_mode(
            cli_flag=cli_mode,
            baseline_merge_commit=baseline_merge_commit,
        )
        return result
    except ModeMismatchError as exc:
        diagnostic = {
            "diagnostic_code": str(exc.diagnostic_code),
            "message": exc.message,
        }
        console.print(f"[red]Error:[/red] {exc.diagnostic_code}")  # type: ignore[attr-defined]
        console.print(exc.message)  # type: ignore[attr-defined]
        import sys

        sys.stdout.write(json.dumps(diagnostic) + "\n")
        raise typer.Exit(1) from exc


def _record_gate(
    gates_recorded: list[GateRecord],
    *,
    gate_id: Literal["gate_1", "gate_2", "gate_3", "gate_4"],
    name: str,
    result: Literal["pass", "fail"],
) -> None:
    gates_recorded.append(
        GateRecord(
            id=gate_id,
            name=name,
            command=f"spec-kitty review (internal {gate_id.replace('_', ' ')})",
            exit_code=1 if result == "fail" else 0,
            result=result,
        )
    )


def _run_lane_gate(
    feature_dir: Path,
    repo_root: Path,
    console: Console,
    findings: list[dict[str, str]],
    gates_recorded: list[GateRecord],
) -> None:
    findings_before = len(findings)
    check_wp_lanes(feature_dir, repo_root, console, findings)
    result: Literal["pass", "fail"] = "fail" if len(findings) > findings_before else "pass"
    _record_gate(gates_recorded, gate_id="gate_1", name="wp_lane_check", result=result)


def _run_dead_code_gate(
    *,
    baseline_merge_commit: str | None,
    repo_root: Path,
    console: Console,
    findings: list[dict[str, str]],
    mission_id: str | None,
    mission_slug: str,
    acceptance_mode: str | None = None,
    pr_merge_evidence: str | None = None,
    gates_recorded: list[GateRecord],
) -> None:
    findings_before = len(findings)
    scan_dead_code(
        baseline_merge_commit,
        repo_root,
        console,
        findings,
        mission_id=mission_id,
        mission_slug=mission_slug,
        acceptance_mode=acceptance_mode,
        pr_merge_evidence=pr_merge_evidence,
    )
    result: Literal["pass", "fail"] = "fail" if len(findings) > findings_before else "pass"
    _record_gate(gates_recorded, gate_id="gate_2", name="dead_code_scan", result=result)


def _run_ble001_gate(
    repo_root: Path,
    console: object,
    findings: list[dict[str, str]],
    gates_recorded: list[GateRecord],
) -> None:
    ble001_findings = collect_auth_storage_ble001_findings(repo_root)
    for finding in ble001_findings:
        findings.append(
            {
                "type": "ble001_suppression",
                "file": finding.file,
                "line": str(finding.line),
                "content": finding.suppression,
                "remediation": finding.remediation,
            }
        )

    if ble001_findings:
        console.print(  # type: ignore[attr-defined]
            f"  [red]✗[/red]  BLE001 audit: {len(ble001_findings)} unjustified suppression(s)"
        )
        for finding in ble001_findings:
            console.print(f"       {finding.file}:{finding.line}")  # type: ignore[attr-defined]
            console.print(f"       suppression: {finding.suppression}")  # type: ignore[attr-defined]
            console.print(f"       remediation: {finding.remediation}")  # type: ignore[attr-defined]
        result: Literal["pass", "fail"] = "fail"
    else:
        console.print("  [green]✓[/green]  BLE001 audit: 0 unjustified suppressions")  # type: ignore[attr-defined]
        result = "pass"

    _record_gate(gates_recorded, gate_id="gate_3", name="ble001_audit", result=result)


def _evaluate_issue_matrix(
    *,
    feature_dir: Path,
    review_mode: MissionReviewMode,
    console: object,
    findings: list[dict[str, str]],
) -> bool | Literal["not_applicable"]:
    """Gate 4: issue-matrix enforcement.

    FR-005 / #3035: ``not_applicable`` is a first-class Gate-4 verdict, not a
    fabricated matrix or a hard fail. A mission that declares ZERO canonical
    issue references (per WP08's :func:`discover_issue_references` -- the
    SAME multi-file completeness definition finalization/merge-gates use, not
    a local re-scan) has nothing for an issue-matrix to enforce, so this
    returns ``not_applicable`` rather than failing on a matrix the mission
    never needed. When references DO exist, fail-closed behaviour is
    retained: a mission with no rows the reader can load is a hard failure.

    C-008 / B-1 (#3035, T044): presence is checked via WP05's dir-based
    :func:`~specify_cli.tasks.issue_matrix_migration.
    issue_matrix_artifact_present` (JSON-first, ``.md`` failover) -- NOT a
    hardcoded ``issue-matrix.md`` ``.exists()`` precheck, which wrongly
    hard-failed a JSON-only (B3) mission before ever consulting the failover
    reader. ``issue_matrix_artifact_present`` is an EXISTENCE check, not a
    "has rows" check (a structurally malformed ``.md`` exists but may parse
    to zero valid rows) -- so a present-but-invalid matrix still reaches
    :func:`validate_issue_matrix` below for its specific schema diagnostic,
    rather than being misreported as merely "missing".
    """
    if review_mode is not MissionReviewMode.POST_MERGE:
        return "not_applicable"

    if not discover_issue_references(feature_dir):
        console.print(  # type: ignore[attr-defined]
            "  [green]✓[/green]  Issue matrix: not_applicable (mission declares zero canonical issue references)"
        )
        return "not_applicable"

    if not issue_matrix_artifact_present(feature_dir):
        console.print(  # type: ignore[attr-defined]
            f"  [red]✗[/red]  Issue matrix: "
            f"{MissionReviewDiagnostic.ISSUE_MATRIX_MISSING}: "
            "issue-matrix not found (required in post-merge mode when "
            "canonical issue references exist)"
        )
        findings.append(
            {
                "type": "issue_matrix_violation",
                "diagnostic_code": str(MissionReviewDiagnostic.ISSUE_MATRIX_MISSING),
                "message": ("issue-matrix is required in post-merge mode when canonical issue references exist"),
            }
        )
        return False

    issue_matrix_path = feature_dir / "issue-matrix.md"
    matrix_result = validate_issue_matrix(issue_matrix_path)
    if not matrix_result.passed:
        for diag in matrix_result.diagnostics:
            console.print(  # type: ignore[attr-defined]
                f"  [red]✗[/red]  Issue matrix: {diag['diagnostic_code']}: {diag['message']}"
            )
            findings.append(
                {
                    "type": "issue_matrix_violation",
                    "diagnostic_code": diag["diagnostic_code"],
                    "message": diag["message"],
                }
            )
    else:
        console.print(  # type: ignore[attr-defined]
            f"  [green]✓[/green]  Issue matrix: {len(matrix_result.rows)} row(s) validated"
        )
    return True


def review_mission(
    mission: Annotated[
        str,
        typer.Option("--mission", help="Mission handle (id, mid8, or slug)."),
    ] = "",
    mode: Annotated[
        str | None,
        typer.Option(
            "--mode",
            help=(
                "Review mode: 'lightweight' (consistency check only) or "
                "'post-merge' (full release-gate contract). "
                "Auto-detected from meta.json.baseline_merge_commit when omitted."
            ),
            show_default=False,
        ),
    ] = None,
) -> None:
    """Validate a merged mission: WP lane check, dead-code scan, BLE001 audit.

    Writes kitty-specs/<slug>/mission-review-report.md with a machine-readable
    verdict.  See module docstring for known false-positive scenarios in the
    dead-code scan step.
    """
    from specify_cli.cli.console import console

    repo_root = _resolve_repo_root(console)
    try:
        assert_pytest_available(repo_root)
    except TestExtraMissing:
        _fail_missing_test_extra(console)
    _check_env_skew(console, repo_root)

    handle = _require_mission_handle(mission, console)
    resolved = resolve_mission_handle(handle, repo_root)
    feature_dir = resolved.feature_dir
    mission_slug = resolved.mission_slug
    meta = load_meta_or_empty(feature_dir)
    friendly_name: str = str(meta.get("friendly_name") or mission_slug)
    _bmc_raw = meta.get("baseline_merge_commit")
    baseline_merge_commit: str | None = str(_bmc_raw) if _bmc_raw else None
    review_mode, auto_detected = _resolve_mode_or_exit(
        console=console,
        cli_mode=mode,
        baseline_merge_commit=baseline_merge_commit,
    )
    mode_label = f"{review_mode.value} ({'auto-detected' if auto_detected else 'explicit'})"
    console.print(f"\nReviewing mission: {friendly_name} ({mission_slug})")
    console.print(f"Mode: {mode_label}\n")

    findings: list[dict[str, str]] = []
    gates_recorded: list[GateRecord] = []
    _mission_id_raw = meta.get("mission_id")
    _mission_id: str | None = str(_mission_id_raw) if _mission_id_raw else None
    _acceptance_mode_raw = meta.get("acceptance_mode")
    _acceptance_mode: str | None = str(_acceptance_mode_raw) if _acceptance_mode_raw else None
    _pr_merge_evidence_raw = meta.get("pr_merge_evidence")
    _pr_merge_evidence: str | None = str(_pr_merge_evidence_raw) if _pr_merge_evidence_raw else None
    _run_lane_gate(feature_dir, repo_root, console, findings, gates_recorded)
    _run_dead_code_gate(
        baseline_merge_commit=baseline_merge_commit,
        repo_root=repo_root,
        console=console,
        findings=findings,
        mission_id=_mission_id,
        mission_slug=mission_slug,
        acceptance_mode=_acceptance_mode,
        pr_merge_evidence=_pr_merge_evidence,
        gates_recorded=gates_recorded,
    )
    _run_ble001_gate(repo_root, console, findings, gates_recorded)
    # coord-commit-integrity SURFACE A #1c: ``issue-matrix.md`` is COORD-partition.
    # Route the read through the shared placement seam so a coord/lanes-with-coord
    # mission reads the coordination surface; ``coord_read_dir_for`` fails soft to
    # ``None`` (→ primary ``feature_dir``) for coord-less missions AND for a
    # post-merge mission whose coordination worktree has been consolidated away.
    from mission_runtime import MissionArtifactKind, coord_read_dir_for

    issue_matrix_dir = coord_read_dir_for(repo_root, mission_slug, MissionArtifactKind.ISSUE_MATRIX) or feature_dir
    issue_matrix_present = _evaluate_issue_matrix(
        feature_dir=issue_matrix_dir,
        review_mode=review_mode,
        console=console,
        findings=findings,
    )
    mission_exception_present: bool | Literal["not_applicable"] = (
        (feature_dir / "mission-exception.md").exists() if review_mode is MissionReviewMode.POST_MERGE else "not_applicable"
    )
    write_review_report(
        feature_dir,
        repo_root,
        findings,
        console,
        mode=review_mode.value,
        gates_recorded=gates_recorded,
        issue_matrix_present=issue_matrix_present,
        mission_exception_present=mission_exception_present,
    )
    _record_gate(gates_recorded, gate_id="gate_4", name="report_writer", result="pass")


__all__ = [
    "Ble001SuppressionFinding",
    "GateRecord",
    "MissionReviewDiagnostic",
    "MissionReviewMode",
    "ModeMismatchError",
    "TestExtraMissing",
    "assert_pytest_available",
    "audit_auth_storage_ble001_line",
    "collect_auth_storage_ble001_findings",
    "resolve_mode",
    "review_mission",
    "validate_issue_matrix",
]
