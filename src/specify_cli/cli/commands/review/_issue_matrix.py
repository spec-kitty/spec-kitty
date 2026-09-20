"""Issue-matrix validator (T019).

NFR-007: the closed-set vocabulary (MANDATORY_COLUMNS, NAMED_OPTIONAL_COLUMNS,
COLUMN_ALIASES, IssueMatrixVerdict) is encoded ONCE here and imported by any
other module that needs it.  Do not duplicate these constants.

See: src/specify_cli/cli/commands/review/ERROR_CODES.md
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from specify_cli.cli.commands.review._diagnostics import MissionReviewDiagnostic

# ---------------------------------------------------------------------------
# Closed-set vocabulary (NFR-007 single source of truth)
# ---------------------------------------------------------------------------

MANDATORY_COLUMNS: tuple[str, ...] = ("issue", "verdict", "evidence_ref")

NAMED_OPTIONAL_COLUMNS: tuple[str, ...] = (
    "title",
    "scope",
    "wp",
    "fr",
    "nfr",
    "sc",
    "repo",
)

# Maps input header spellings → canonical column name.
# All lookups are applied AFTER lowercasing the raw header cell value.
COLUMN_ALIASES: dict[str, str] = {
    "evidence ref": "evidence_ref",
    "wp_id": "wp",
    "fr(s)": "fr",
    "nfr(s)": "nfr",
    "theme": "scope",
}

_ALL_VALID_COLUMNS: frozenset[str] = frozenset(MANDATORY_COLUMNS) | frozenset(
    NAMED_OPTIONAL_COLUMNS
)


class IssueMatrixVerdict(StrEnum):
    """Closed-set verdict allow-list for issue-matrix.md rows.

    Derived from audit of 6 existing matrices (2026-05-12); no drift observed.

    ``in-mission`` (2026-06-08) is a non-terminal verdict: the issue is being
    fixed *by this mission* in a work package that has not yet completed. It is
    accepted at per-WP ``approved`` (so a long dependency chain is not blocked
    on issues its own later WPs will close), but it must NOT survive to mission
    ``done``/merge — the approval blocker rejects any ``in-mission`` row on a
    ``done`` transition, forcing resolution to a terminal verdict first.

    ``not-applicable`` (move-task-approval-ergonomics-01M302R0 WP02, #3469) is
    the mirror-image case: the reference is cited for context or is a PR/
    commit reference, and the mission owes it no work at all. Unlike
    ``in-mission`` it is **terminal** — it passes the ``done``/merge
    completeness gate unchanged, because there is no future state in which
    this mission will "resolve" a reference it never owed work on. It is also
    **non-gating** at ``approved``: the approval blocker never requires a row
    at all for a reference the WP01 classifier
    (:mod:`specify_cli.tasks.issue_reference_discovery`) demotes to
    ``context_only``/``pr_or_commit_ref``, but an operator may still record
    ``not-applicable`` explicitly (including on a row the classifier would
    otherwise gate) per the lever SSOT: classification decides whether a row
    is *required*; verdict decides whether an existing row is *resolved*. See
    ``docs/adr/3.x/2026-09-20-1-issue-matrix-not-applicable-verdict.md``.

    See: src/specify_cli/cli/commands/review/ERROR_CODES.md
    """

    FIXED = "fixed"
    VERIFIED_ALREADY_FIXED = "verified-already-fixed"
    DEFERRED_WITH_FOLLOWUP = "deferred-with-followup"
    IN_MISSION = "in-mission"
    NOT_APPLICABLE = "not-applicable"


# ---------------------------------------------------------------------------
# Parsed row dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IssueMatrixRow:
    """One row from a parsed issue-matrix.md table."""

    # Mandatory canonical fields (lowercase normalized)
    issue: str
    verdict: IssueMatrixVerdict
    evidence_ref: str

    # Named-optional canonical fields (None when absent)
    title: str | None = None
    scope: str | None = None
    wp: str | None = None
    fr: str | None = None
    nfr: str | None = None
    sc: str | None = None
    repo: str | None = None


# ---------------------------------------------------------------------------
# Validation result types
# ---------------------------------------------------------------------------


@dataclass
class IssueMatrixValidationResult:
    """Result of validating a single issue-matrix.md file."""

    path: Path
    passed: bool
    rows: list[IssueMatrixRow] = field(default_factory=list)
    diagnostics: list[dict[str, str]] = field(default_factory=list)

    def add_diagnostic(
        self,
        code: MissionReviewDiagnostic,
        message: str,
        *,
        detail: str = "",
    ) -> None:
        entry: dict[str, str] = {
            "diagnostic_code": str(code),
            "message": message,
        }
        if detail:
            entry["detail"] = detail
        self.diagnostics.append(entry)
        self.passed = False


# ---------------------------------------------------------------------------
# Markdown table parser helpers
# ---------------------------------------------------------------------------

_TABLE_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")
_SEPARATOR_RE = re.compile(r"^\s*\|[\s\-|:]+\|\s*$")


def _strip_backticks(value: str) -> str:
    """Remove surrounding backtick pairs from a cell value."""
    s = value.strip()
    if s.startswith("`") and s.endswith("`") and len(s) >= 2:
        return s[1:-1]
    return s


def _normalize_issue(value: str) -> str:
    """Extract canonical #NNN from linkified values like [#123](https://...)."""
    # Match [#NNN](url) → #NNN
    m = re.match(r"\[#(\d+)\]\(https?://[^)]+\)", value.strip())
    if m:
        return f"#{m.group(1)}"
    return value.strip()


def _split_cells(row_text: str) -> list[str]:
    """Split a Markdown table row into cells, stripping leading/trailing whitespace."""
    parts = row_text.split("|")
    # Remove the empty first and last elements that result from '|...|' format
    if parts and not parts[0].strip():
        parts = parts[1:]
    if parts and not parts[-1].strip():
        parts = parts[:-1]
    return [p.strip() for p in parts]


def _find_tables(lines: list[str]) -> list[tuple[int, int]]:
    """Return list of (start_line_idx, end_line_idx+1) for each Markdown table block."""
    tables: list[tuple[int, int]] = []
    i = 0
    while i < len(lines):
        if _TABLE_ROW_RE.match(lines[i]):
            start = i
            # advance past separator and data rows
            while i < len(lines) and _TABLE_ROW_RE.match(lines[i]):
                i += 1
            tables.append((start, i))
        else:
            i += 1
    return tables


# ---------------------------------------------------------------------------
# Header normalisation
# ---------------------------------------------------------------------------


def _normalize_header(raw: str) -> str:
    """Lowercase + strip, then apply COLUMN_ALIASES."""
    key = raw.strip().lower()
    return COLUMN_ALIASES.get(key, key)


# ---------------------------------------------------------------------------
# Core validator
# ---------------------------------------------------------------------------


def validate_issue_matrix(path: Path) -> IssueMatrixValidationResult:  # noqa: C901
    """Validate an issue-matrix against the closed-set schema.

    JSON-first (M7 / write-side-seam-matrix-tracer-01KYP3MH WP05 / T023):
    when ``issue-matrix.json`` exists at ``path``'s directory (the structured,
    canonical artifact -- C-008), it is validated via the ONE canonical
    dir-based reader (:func:`specify_cli.tasks.issue_matrix_migration.
    load_issue_matrix`) and NO markdown parsing happens. Otherwise falls back
    to the legacy markdown parser below (FR-013 back-compat).

    Parameters
    ----------
    path:
        Absolute path to the ``issue-matrix.md`` (or ``.json``) file to
        validate -- historically always ``<feature_dir>/issue-matrix.md``;
        ``path.parent`` is treated as the mission's issue-matrix directory
        for the JSON-first check.

    Returns
    -------
    IssueMatrixValidationResult
        ``passed`` is ``True`` only when no violations are found.
    """
    result = IssueMatrixValidationResult(path=path, passed=True)

    json_path = path if path.name == "issue-matrix.json" else path.parent / "issue-matrix.json"
    if json_path.exists():
        return _validate_structured_issue_matrix(json_path, result)

    if not path.exists():
        result.add_diagnostic(
            MissionReviewDiagnostic.ISSUE_MATRIX_MISSING,
            f"issue-matrix.md not found at {path}",
        )
        return result

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    # -----------------------------------------------------------------------
    # Rule: exactly one table
    # -----------------------------------------------------------------------
    tables = _find_tables(lines)
    if len(tables) > 1:
        result.add_diagnostic(
            MissionReviewDiagnostic.ISSUE_MATRIX_MULTI_TABLE,
            f"issue-matrix.md contains {len(tables)} Markdown tables; exactly one is allowed.",
            detail=f"Table spans found at lines: {[(s+1, e) for s, e in tables]}",
        )
        return result

    if len(tables) == 0:
        result.add_diagnostic(
            MissionReviewDiagnostic.ISSUE_MATRIX_MISSING,
            "issue-matrix.md contains no Markdown table.",
        )
        return result

    table_start, table_end = tables[0]
    table_lines = lines[table_start:table_end]

    # Separate header, separator, and data rows
    # (At minimum: header row + separator row)
    if len(table_lines) < 2:
        result.add_diagnostic(
            MissionReviewDiagnostic.ISSUE_MATRIX_SCHEMA_DRIFT,
            "issue-matrix.md table has fewer than 2 rows (header + separator expected).",
        )
        return result

    header_cells = _split_cells(table_lines[0])
    # Skip separator row (index 1)
    data_lines = table_lines[2:]

    # -----------------------------------------------------------------------
    # Normalize header → canonical column names
    # -----------------------------------------------------------------------
    canonical_headers = [_normalize_header(h) for h in header_cells]

    # -----------------------------------------------------------------------
    # Rule: all mandatory columns present
    # -----------------------------------------------------------------------
    missing_mandatory = [c for c in MANDATORY_COLUMNS if c not in canonical_headers]
    if missing_mandatory:
        result.add_diagnostic(
            MissionReviewDiagnostic.ISSUE_MATRIX_SCHEMA_DRIFT,
            f"Mandatory column(s) missing: {', '.join(missing_mandatory)}",
            detail=f"Found columns after normalization: {canonical_headers}",
        )

    # -----------------------------------------------------------------------
    # Rule: all columns are either mandatory or named-optional
    # -----------------------------------------------------------------------
    unknown_columns = [c for c in canonical_headers if c not in _ALL_VALID_COLUMNS]
    if unknown_columns:
        result.add_diagnostic(
            MissionReviewDiagnostic.ISSUE_MATRIX_SCHEMA_DRIFT,
            f"Unknown column(s) not in mandatory or named-optional vocabulary: "
            f"{', '.join(unknown_columns)}",
            detail=(
                f"Valid columns: {list(MANDATORY_COLUMNS)} (mandatory) + "
                f"{list(NAMED_OPTIONAL_COLUMNS)} (optional)"
            ),
        )

    # If structural problems prevent further parsing, return early
    if not result.passed and missing_mandatory:
        return result

    # -----------------------------------------------------------------------
    # Build column index map
    # -----------------------------------------------------------------------
    col_idx: dict[str, int] = {col: idx for idx, col in enumerate(canonical_headers)}

    def _get_cell(row_cells: list[str], col: str) -> str | None:
        idx = col_idx.get(col)
        if idx is None or idx >= len(row_cells):
            return None
        return _strip_backticks(row_cells[idx]) or None

    # -----------------------------------------------------------------------
    # Parse and validate data rows
    # -----------------------------------------------------------------------
    for raw_line in data_lines:
        if not _TABLE_ROW_RE.match(raw_line):
            continue
        row_cells = _split_cells(raw_line)

        raw_issue = _get_cell(row_cells, "issue") or ""
        issue = _normalize_issue(_strip_backticks(raw_issue))

        raw_verdict = _get_cell(row_cells, "verdict") or ""
        evidence_ref = _get_cell(row_cells, "evidence_ref") or ""

        # Rule: evidence_ref non-empty
        if not evidence_ref:
            result.add_diagnostic(
                MissionReviewDiagnostic.ISSUE_MATRIX_EVIDENCE_REF_EMPTY,
                f"Row for issue '{issue}': evidence_ref is empty.",
            )

        # Rule: verdict in allow-list
        verdict_normalized = raw_verdict.strip().lower()
        verdict: IssueMatrixVerdict | None
        try:
            verdict = IssueMatrixVerdict(verdict_normalized)
        except ValueError:
            result.add_diagnostic(
                MissionReviewDiagnostic.ISSUE_MATRIX_VERDICT_UNKNOWN,
                f"Row for issue '{issue}': verdict '{raw_verdict}' is not in the "
                f"allowed set: {[v.value for v in IssueMatrixVerdict]}",
            )
            verdict = None

        # Rule: deferred-with-followup must contain follow-up handle
        if verdict is IssueMatrixVerdict.DEFERRED_WITH_FOLLOWUP:
            has_handle = bool(re.search(r"#\d+", evidence_ref)) or (
                "Follow-up:" in evidence_ref
            )
            if not has_handle:
                result.add_diagnostic(
                    MissionReviewDiagnostic.ISSUE_MATRIX_DEFERRED_WITHOUT_HANDLE,
                    f"Row for issue '{issue}': verdict is 'deferred-with-followup' "
                    f"but evidence_ref contains no follow-up handle "
                    f"(expected '#NNN' or 'Follow-up:' substring); "
                    f"got: '{evidence_ref}'",
                )

        if verdict is not None and result.passed or (
            verdict is not None and not missing_mandatory and not unknown_columns
        ):
            row = IssueMatrixRow(
                issue=issue,
                verdict=verdict,
                evidence_ref=evidence_ref,
                title=_get_cell(row_cells, "title"),
                scope=_get_cell(row_cells, "scope"),
                wp=_get_cell(row_cells, "wp"),
                fr=_get_cell(row_cells, "fr"),
                nfr=_get_cell(row_cells, "nfr"),
                sc=_get_cell(row_cells, "sc"),
                repo=_get_cell(row_cells, "repo"),
            )
            result.rows.append(row)

    return result


def _validate_structured_issue_matrix(
    json_path: Path, result: IssueMatrixValidationResult
) -> IssueMatrixValidationResult:
    """Validate ``issue-matrix.json`` business rules (M7 / T023).

    Re-points onto the ONE canonical dir-based reader
    (:func:`specify_cli.tasks.issue_matrix_migration.load_issue_matrix`) for
    ``.rows`` -- deferred import to avoid a module-load cycle (``issue_matrix_
    migration`` also imports FROM this module for row construction). The
    markdown-only structural diagnostics (``ISSUE_MATRIX_MULTI_TABLE`` /
    unknown-column ``ISSUE_MATRIX_SCHEMA_DRIFT``) do not apply to a
    machine-written, already-structured JSON document; only the semantic
    business rules (verdict allow-list, non-empty evidence, deferred-with-
    followup handle) are re-checked here, against the RAW rows (so a
    scaffolded placeholder verdict like ``"unknown"`` is still flagged even
    though it is excluded from the canonical ``.rows`` list -- mirroring the
    markdown validator's existing row-filtering contract).
    """
    from specify_cli.tasks.issue_matrix_migration import (
        diagnose_structured_issue_matrix,
        load_issue_matrix,
    )

    result.path = json_path
    result.diagnostics = diagnose_structured_issue_matrix(json_path)
    result.rows = load_issue_matrix(json_path.parent)
    result.passed = not result.diagnostics
    return result


__all__ = [
    # COLUMN_ALIASES, IssueMatrixRow, MANDATORY_COLUMNS, NAMED_OPTIONAL_COLUMNS:
    # demoted — intra-module only; no cross-module src/ from-import callers
    # (WP01 harden-dead-symbol-gate-01KW0RJR).
    "IssueMatrixValidationResult",
    "IssueMatrixVerdict",
    "validate_issue_matrix",
]
