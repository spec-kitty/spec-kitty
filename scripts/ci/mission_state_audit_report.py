#!/usr/bin/env python3
"""Render the ``doctor mission-state --audit --json`` report for the CI audit job (#6058).

GitHub runs ``run:`` steps under ``bash -e``, so a failing audit used to abort the step before
anything was printed. The ``mission-state-audit`` job in ``.github/workflows/ci-router.yml`` now
captures the auditor's exit code and hands the JSON report to this script, which prints every
TeamSpace blocker (mission, code, artifact, detail, remedy) to the log as ``::error`` annotations
and appends the same table to ``$GITHUB_STEP_SUMMARY``.

The blocker predicate is *not* a second authority: :func:`is_blocking` restates
``specify_cli.audit.models.is_teamspace_blocker`` over the JSON shape (that function takes a
``MissionFinding``, not a dict) and imports the one code set it reads,
``TEAMSPACE_BLOCKER_CODES``. ``tests/ci/test_mission_state_audit_report.py`` pins the two against
each other over every code and severity.

The script never changes the step's result (contract R5): :func:`main` returns 0 and the step's own
``exit "$status"`` decides. Usage::

    python scripts/ci/mission_state_audit_report.py <report.json> <audit exit code>
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

from specify_cli.audit.models import TEAMSPACE_BLOCKER_CODES

__all__ = ["is_blocking", "main", "render"]

#: GitHub truncates a step summary at 1 MiB; stay well under it.
SUMMARY_BUDGET_BYTES = 900 * 1024
DETAIL_LIMIT = 300
#: More unrelated Missions than this drifting at once points at a reducer/dependency change.
MANY_DRIFT_THRESHOLD = 5
SNAPSHOT_DRIFT = "SNAPSHOT_DRIFT"
SUMMARY_ENV = "GITHUB_STEP_SUMMARY"
NO_BLOCKERS = "No TeamSpace blockers."
NO_MISSIONS_NOTE = "The report has no `missions` list, so no blockers could be listed; see the uploaded artifact."
ANNOTATION_TITLE = "mission-state audit"
SUMMARY_HEADING = "## Mission-state audit"
TABLE_HEADER = ("| Mission | Code | Artifact | Detail | Remedy |", "|---|---|---|---|---|")
REPAIR_DOC = "docs/migrations/teamspace-mission-state-repair.md"
REMEDY_SNAPSHOT_DRIFT = "spec-kitty agent status materialize --mission {slug}"
REMEDY_DEFAULT = f"spec-kitty doctor mission-state --audit --mission {{slug}} (see {REPAIR_DOC})"
MANY_DRIFT_HINT = f"{{count}} Missions report {SNAPSHOT_DRIFT} in one run: suspect a reducer or dependency change (see #6058) before re-materializing anything."

Blocker = tuple[str, Mapping[str, Any]]


def is_blocking(finding: Mapping[str, Any]) -> bool:
    """Whether a finding blocks TeamSpace readiness: error severity OR a blocker code."""
    return finding.get("severity") == "error" or finding.get("code") in TEAMSPACE_BLOCKER_CODES


def _remedy(code: str, slug: str) -> str:
    template = REMEDY_SNAPSHOT_DRIFT if code == SNAPSHOT_DRIFT else REMEDY_DEFAULT
    return template.format(slug=slug)


def _blockers(report: Mapping[str, Any]) -> Iterator[Blocker]:
    for mission in report.get("missions") or []:
        slug = str(mission["mission_slug"])
        for finding in mission["findings"]:
            if is_blocking(finding):
                yield slug, finding


def _safe(text: str) -> str:
    """Make text encodable: the doctor emits surrogateescape'd names for non-UTF-8 Mission directories."""
    return text.encode("utf-8", "backslashreplace").decode("utf-8")


def _annotation_escape(text: str) -> str:
    """Escape a workflow-command message so a multi-line detail stays one annotation."""
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _cell(text: object, limit: int | None = None) -> str:
    """A markdown table cell: single line, ``|`` escaped, optionally truncated."""
    flat = " ".join(str(text if text is not None else "").split())
    if limit is not None and len(flat) > limit:
        flat = flat[: limit - 1] + "…"
    return flat.replace("|", "\\|")


def _log_line(slug: str, finding: Mapping[str, Any]) -> str:
    code = str(finding.get("code"))
    message = f"{slug} {code} {finding.get('artifact_path')}: {finding.get('detail')} → remedy: {_remedy(code, slug)}"
    return f"::error title={ANNOTATION_TITLE}::{_annotation_escape(message)}"


def _table_row(slug: str, finding: Mapping[str, Any]) -> str:
    code = str(finding.get("code"))
    cells = (
        f"`{_cell(slug)}`",
        f"`{_cell(code)}`",
        f"`{_cell(finding.get('artifact_path'))}`",
        _cell(finding.get("detail"), DETAIL_LIMIT),
        f"`{_cell(_remedy(code, slug))}`",
    )
    return "| " + " | ".join(cells) + " |"


def _counts_line(blockers: Sequence[Blocker]) -> str:
    by_code = Counter(str(finding.get("code")) for _, finding in blockers)
    counts = ", ".join(f"{code} x{n}" for code, n in by_code.most_common())
    return _annotation_escape("By code: " + counts)


def _drift_hint(blockers: Sequence[Blocker]) -> str | None:
    drifted = {slug for slug, finding in blockers if finding.get("code") == SNAPSHOT_DRIFT}
    return MANY_DRIFT_HINT.format(count=len(drifted)) if len(drifted) > MANY_DRIFT_THRESHOLD else None


def _stat(value: object) -> str:
    return "?" if value is None else str(value)


def _summary_stats(report: Mapping[str, Any]) -> str:
    stats = report.get("repo_summary") or {}
    errors = (stats.get("findings_by_severity") or {}).get("error")
    return f"{_stat(stats.get('total_missions'))} Missions, {_stat(stats.get('missions_with_teamspace_blockers'))} with TeamSpace blockers, {_stat(errors)} errors."


def _no_blockers_text(report: Mapping[str, Any]) -> str:
    """Say so when the report had no ``missions`` list, instead of claiming a clean audit."""
    return NO_BLOCKERS if report.get("missions") is not None else NO_MISSIONS_NOTE


def _fit_rows(rows: Sequence[str], head_bytes: int) -> tuple[list[str], int]:
    """The rows that fit the summary budget (all of them when they do) and how many were left out."""
    kept: list[str] = []
    used = head_bytes
    for row in rows:
        used += len(row.encode("utf-8", "backslashreplace")) + 1
        if used > SUMMARY_BUDGET_BYTES:
            break
        kept.append(row)
    return kept, len(rows) - len(kept)


def _markdown(report: Mapping[str, Any], exit_code: int, blockers: Sequence[Blocker]) -> str:
    verdict = "FAILED" if exit_code else "passed"
    head = [f"{SUMMARY_HEADING}: {verdict} (exit {exit_code})", "", _summary_stats(report), ""]
    if not blockers:
        return "\n".join([*head, _no_blockers_text(report), ""])
    head.append(_counts_line(blockers))
    hint = _drift_hint(blockers)
    if hint:
        head += ["", f"**{hint}**"]
    head += ["", *TABLE_HEADER]
    rows, left_out = _fit_rows(
        [_table_row(slug, finding) for slug, finding in blockers],
        len("\n".join(head).encode("utf-8")),
    )
    tail = ["", f"{left_out} more blocker(s) in the uploaded artifact and the step log."] if left_out else []
    return "\n".join([*head, *rows, *tail]) + "\n"


def _log_text(report: Mapping[str, Any], blockers: Sequence[Blocker], exit_code: int) -> str:
    lines = [_counts_line(blockers)] if blockers else [_no_blockers_text(report)]
    lines += [_log_line(slug, finding) for slug, finding in blockers]
    hint = _drift_hint(blockers)
    if hint:
        lines.append(f"::warning title={ANNOTATION_TITLE}::{hint}")
    lines.append(f"mission-state audit exit code: {exit_code}")
    return "\n".join(lines) + "\n"


def render(report: Mapping[str, Any], exit_code: int) -> tuple[str, str]:
    """Return ``(log_text, summary_markdown)`` for a parsed audit report."""
    blockers = list(_blockers(report))
    return _safe(_log_text(report, blockers, exit_code)), _safe(_markdown(report, exit_code, blockers))


def _append_summary(markdown: str) -> None:
    target = os.environ.get(SUMMARY_ENV)
    if not target:
        return
    try:
        with Path(target).open("a", encoding="utf-8") as handle:
            handle.write(markdown)
    except Exception as exc:  # noqa: BLE001 - R5: nothing here may change the step's result
        print(f"::warning::the mission-state audit summary could not be written ({type(exc).__name__}: {exc}).")


def main(argv: Sequence[str] | None = None) -> int:
    """Print the blockers and append the summary; always return 0 (the step decides the result)."""
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        report = json.loads(Path(args[0]).read_text(encoding="utf-8"))
        log_text, markdown = render(report, int(args[1]))
        sys.stdout.write(log_text)
    except Exception as exc:  # noqa: BLE001 - R5: nothing here may change the step's result (RecursionError included)
        print(f"::warning::the mission-state audit report could not be rendered ({type(exc).__name__}).")
        return 0
    _append_summary(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
