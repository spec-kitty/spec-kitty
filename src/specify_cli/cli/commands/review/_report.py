"""Gate 4: Report writer.

Extracted verbatim from src/specify_cli/cli/commands/review.py (WP07).
Extended by WP03 to add new frontmatter keys: mode, gates_recorded,
issue_matrix_present, mission_exception_present.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, NoReturn

from rich.console import Console
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from specify_cli.cli.commands.review._ble001_audit import _BLE001_REMEDIATION
from specify_cli.cli.commands.review._diagnostics import MissionReviewDiagnostic
from kernel.clock import now_utc_iso

#: The file this command writes (and owns) inside ``kitty-specs/<slug>/``.
REVIEW_REPORT_FILENAME = "mission-review-report.md"

#: The file the ``spec-kitty-mission-review`` skill names for the report an
#: agent writes. It is never this command's to write (#7753).
AGENT_REVIEW_FILENAME = "mission-review.md"

_MACHINE_VERDICTS = frozenset({"pass", "pass_with_notes", "fail"})

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
    if finding_type == "dead_code_not_applicable":
        return (
            f"- **dead_code_not_applicable** "
            f"`{finding.get('diagnostic_code', 'unknown')}`: "
            f"unsupported_extensions=`{finding.get('unsupported_extensions') or '(none)'}`; "
            f"excluded_test_paths=`{finding.get('excluded_test_paths', '0')}`; "
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


class ReportPathOccupiedError(Exception):
    """The report path holds a file this command did not write (#7753)."""

    def __init__(self, report_path: Path) -> None:
        self.report_path = report_path
        super().__init__(
            f"{MissionReviewDiagnostic.REPORT_PATH_OCCUPIED}: {report_path} is not a report "
            "spec-kitty review wrote (no verdict/reviewed_at/findings frontmatter); "
            "refusing to overwrite it."
        )


def _leading_frontmatter(text: str) -> dict[object, object] | None:
    """Return the leading ``---`` YAML block as a mapping, or ``None``."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            try:
                parsed = YAML(typ="safe").load("\n".join(lines[1:idx]))
            except YAMLError:
                return None
            return parsed if isinstance(parsed, dict) else None
    return None


def is_machine_review_report(text: str) -> bool:
    """True when *text* is a report :func:`write_review_report` wrote.

    Every generation of the machine report opens with frontmatter carrying a
    ``verdict`` from the command's own vocabulary, a ``reviewed_at`` stamp and
    an integer ``findings`` count (``gates_recorded`` arrived later, so it is
    not required). Anything else is foreign and must not be overwritten.
    """
    frontmatter = _leading_frontmatter(text)
    if frontmatter is None:
        return False
    findings = frontmatter.get("findings")
    return frontmatter.get("verdict") in _MACHINE_VERDICTS and "reviewed_at" in frontmatter and isinstance(findings, int) and not isinstance(findings, bool)


def ensure_report_path_writable(feature_dir: Path) -> Path:
    """Return the report path, refusing when a foreign file occupies it.

    An absent path, or one holding a previous machine report, is writable. A
    file this command did not write (an agent's mission review, say), an
    unreadable file or a non-file at the path raises
    :class:`ReportPathOccupiedError` so its bytes are never lost (#7753).
    """
    report_path = feature_dir / REVIEW_REPORT_FILENAME
    if not report_path.exists() and not report_path.is_symlink():
        return report_path
    try:
        text = report_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ReportPathOccupiedError(report_path) from exc
    if report_path.is_symlink() or not is_machine_review_report(text):
        raise ReportPathOccupiedError(report_path)
    return report_path


def refuse_occupied_report_path(error: ReportPathOccupiedError, repo_root: Path, console: Console) -> NoReturn:
    """Print the named refusal and its remedy, then exit 1. Nothing is written."""
    import typer

    try:
        rel_path = error.report_path.relative_to(repo_root)
    except ValueError:
        rel_path = error.report_path
    target = rel_path.with_name(AGENT_REVIEW_FILENAME)
    console.print(
        f"[red]{MissionReviewDiagnostic.REPORT_PATH_OCCUPIED}[/red]: {rel_path} is not a report "
        "spec-kitty review wrote (no verdict/reviewed_at/findings frontmatter); refusing to overwrite it."
    )
    console.print(
        f"Move it to {target}, the path the spec-kitty-mission-review skill names for its report "
        f"(git mv {rel_path} {target}), then re-run spec-kitty review. Nothing was written."
    )
    raise typer.Exit(1)


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
    Raises typer.Exit(1) on fail verdict, and also (with
    ``MISSION_REVIEW_REPORT_PATH_OCCUPIED``, writing nothing) when the path
    holds a file this command did not write (#7753).

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

    try:
        report_path = ensure_report_path_writable(feature_dir)
    except ReportPathOccupiedError as exc:
        refuse_occupied_report_path(exc, repo_root, console)
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
