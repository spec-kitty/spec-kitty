"""Gate 4: Report writer.

Extracted verbatim from src/specify_cli/cli/commands/review.py (WP07).
Extended by WP03 to add new frontmatter keys: mode, gates_recorded,
issue_matrix_present, mission_exception_present.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from rich.console import Console

from specify_cli.cli.commands.review._ble001_audit import _BLE001_REMEDIATION
from kernel.clock import now_utc_iso

_HARD_FAILURE_FINDING_TYPES = frozenset(
    {
        "wp_not_done",
        "rejected_review_artifact",
        "review_artifact_schema_invalid",
        "ble001_suppression",
        "issue_matrix_violation",
        "dead_code_baseline_missing",
        "dead_code_undeterminable",
        "dead_code_evidence_incomplete",
    }
)


@dataclass(frozen=True)
class GateRecord:
    """Record of a single gate execution (FR-007)."""

    id: Literal["gate_1", "gate_2", "gate_3", "gate_4"]
    name: str
    command: str
    exit_code: int
    result: Literal["pass", "fail", "skip"]


def _format_finding_line(finding: dict[str, str]) -> str | None:
    finding_type = finding["type"]
    if finding_type == "wp_not_done":
        return f"- **wp_not_done** `{finding['wp_id']}`: lane is `{finding.get('lane', 'unknown')}`"
    if finding_type == "dead_code":
        return f"- **dead_code** `{finding['file']}` — `{finding['symbol']}`: no non-test callers found"
    if finding_type == "dead_code_baseline_missing":
        return f"- **dead_code_baseline_missing** `{finding.get('diagnostic_code', 'unknown')}`: {finding.get('remediation', 'unknown')}"
    if finding_type == "dead_code_undeterminable":
        return (
            f"- **dead_code_undeterminable** "
            f"`{finding.get('diagnostic_code', 'unknown')}`: "
            f"{finding.get('reason', 'unknown')}; "
            f"remediation=`{finding.get('remediation', 'unknown')}`"
        )
    if finding_type == "dead_code_evidence_incomplete":
        return (
            f"- **dead_code_evidence_incomplete** "
            f"`{finding.get('diagnostic_code', 'unknown')}`: "
            f"pr_merge_evidence=`{finding.get('pr_merge_evidence', 'unknown')}`; "
            f"remediation=`{finding.get('remediation', 'unknown')}`"
        )
    if finding_type == "ble001_suppression":
        return (
            f"- **ble001_suppression** `{finding['file']}:{finding['line']}`: "
            f"`{finding.get('content', 'unknown')}`; "
            f"remediation=`{finding.get('remediation', _BLE001_REMEDIATION)}`"
        )
    if finding_type == "rejected_review_artifact":
        return (
            f"- **rejected_review_artifact** `{finding['wp_id']}`: lane is "
            f"`{finding.get('lane', 'unknown')}`, latest artifact is "
            f"`{finding.get('artifact_path', 'unknown')}`; "
            f"diagnostic_code=`{finding.get('diagnostic_code', 'unknown')}`, "
            "branch_or_work_package="
            f"`{finding.get('branch_or_work_package', 'unknown')}`, "
            f"violated_invariant=`{finding.get('violated_invariant', 'unknown')}`, "
            f"remediation=`{finding.get('remediation', 'unknown')}`"
        )
    if finding_type == "review_artifact_schema_invalid":
        return (
            f"- **review_artifact_schema_invalid** `{finding['wp_id']}`: lane is "
            f"`{finding.get('lane', 'unknown')}`, latest artifact is "
            f"`{finding.get('artifact_path', 'unknown')}`; "
            f"diagnostic_code=`{finding.get('diagnostic_code', 'unknown')}`, "
            "branch_or_work_package="
            f"`{finding.get('branch_or_work_package', 'unknown')}`, "
            f"violated_invariant=`{finding.get('violated_invariant', 'unknown')}`, "
            f"schema_error=`{finding.get('schema_error', 'unknown')}`, "
            f"remediation=`{finding.get('remediation', 'unknown')}`"
        )
    if finding_type == "issue_matrix_violation":
        return f"- **issue_matrix_violation** `{finding.get('diagnostic_code', 'unknown')}`: {finding.get('message', 'unknown')}"
    return None


def write_review_report(
    feature_dir: Path,
    repo_root: Path,
    findings: list[dict[str, str]],
    console: Console,
    *,
    mode: str = "lightweight",
    gates_recorded: list[GateRecord] | None = None,
    issue_matrix_present: bool | Literal["not_applicable"] = "not_applicable",
    mission_exception_present: bool | Literal["not_applicable"] = "not_applicable",
) -> None:
    """Step 4 — Write report and print summary verdict.

    Writes mission-review-report.md and prints verdict to console.
    Raises typer.Exit(1) on fail verdict.

    New keyword parameters (WP03, FR-005, FR-007):
      mode: resolved review mode string ("lightweight" or "post-merge").
      gates_recorded: list of GateRecord instances, one per gate executed.
      issue_matrix_present: True/False/not_applicable.
      mission_exception_present: True/False/not_applicable.
    """
    import typer

    hard_failure_count = sum(1 for f in findings if f["type"] in _HARD_FAILURE_FINDING_TYPES)
    if hard_failure_count > 0:
        verdict = "fail"
    elif findings:
        verdict = "pass_with_notes"
    else:
        verdict = "pass"

    reviewed_at = now_utc_iso()

    # Build gates_recorded YAML block
    gates_yaml_lines: list[str] = []
    if gates_recorded:
        gates_yaml_lines.append("gates_recorded:")
        for gate in gates_recorded:
            gates_yaml_lines.append(f"  - id: {gate.id}")
            gates_yaml_lines.append(f"    name: {gate.name}")
            gates_yaml_lines.append(f"    command: {gate.command}")
            gates_yaml_lines.append(f"    exit_code: {gate.exit_code}")
            gates_yaml_lines.append(f"    result: {gate.result}")
    else:
        gates_yaml_lines.append("gates_recorded: []")

    report_lines = [
        "---",
        f"verdict: {verdict}",
        f"mode: {mode}",
        f"reviewed_at: {reviewed_at}",
        f"findings: {len(findings)}",
        *gates_yaml_lines,
        f"issue_matrix_present: {str(issue_matrix_present).lower() if isinstance(issue_matrix_present, bool) else issue_matrix_present}",
        f"mission_exception_present: {str(mission_exception_present).lower() if isinstance(mission_exception_present, bool) else mission_exception_present}",
        "---",
        "",
    ]
    if findings:
        report_lines.append("## Findings")
        report_lines.append("")
        for f in findings:
            finding_line = _format_finding_line(f)
            if finding_line is not None:
                report_lines.append(finding_line)
    else:
        report_lines.append("No findings.")

    report_path = feature_dir / "mission-review-report.md"
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    # ------------------------------------------------------------------
    # Summary output
    # ------------------------------------------------------------------
    if verdict == "pass":
        verdict_color = "green"
    elif verdict == "pass_with_notes":
        verdict_color = "yellow"
    else:
        verdict_color = "red"
    console.print(f"\nVerdict: [{verdict_color}]{verdict}[/{verdict_color}]  ({len(findings)} finding(s))")
    try:
        rel_report = report_path.relative_to(repo_root)
    except ValueError:
        rel_report = report_path
    console.print(f"Report written: {rel_report}")

    if verdict == "fail":
        raise typer.Exit(1)
