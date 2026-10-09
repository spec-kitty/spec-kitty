"""tasks.md / manifest parsing and WP-id resolution helpers.

Behaviour-preserving seam extracted from ``tasks.py`` (issue #2058, WP02).
These helpers parse tasks.md structure (checkbox rows, pipe-table rows and
headers, section headings, inline subtask references) and resolve the work
package that owns a given task id. They are pure parsers with no CLI or git
side effects.

One-way import rule (INV-2): this module MUST NOT import from
``specify_cli.cli.commands.agent.tasks``. ``tasks.py`` imports from here.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
import enum
from kernel._safe_re import re
from pathlib import Path

TASKS_MD_FILENAME = "tasks.md"


class TaskIdResolutionOutcome(enum.StrEnum):
    UPDATED = "updated"
    ALREADY_SATISFIED = "already_satisfied"
    NOT_FOUND = "not_found"


class TaskIdResolutionFormat(enum.StrEnum):
    CHECKBOX = "checkbox"
    PIPE_TABLE = "pipe_table"
    INLINE_SUBTASKS = "inline_subtasks"
    WP_ID = "wp_id"
    #: The authored ``subtasks:`` frontmatter roster — canonical static intent
    #: since #2816 IC-10, and the shape the shipped software-dev template
    #: produces. See ``_resolve_authored_roster`` (#2962).
    AUTHORED_ROSTER = "authored_roster"


@dataclass
class TaskIdResult:
    id: str
    outcome: TaskIdResolutionOutcome
    format: TaskIdResolutionFormat | None
    message: str


# WP04/T022 (FR-017): normalize qualified task identifiers so that
# `mark-status` accepts both bare (``T001`` / ``WP01``) and mission-qualified
# (``<mission_slug>/T001`` or ``<mission_slug>:WP01``) emissions from
# ``tasks-finalize`` and downstream automation. This is a parser-side
# extension; the original token is returned unchanged when it does not match
# a qualified shape so downstream "task not found" surfaces stay structured
# for genuinely garbage input.
_QUALIFIED_TASK_ID_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*[/:](?P<task>[A-Za-z]+\d+)$"
)


def _normalize_task_id_input(raw: str) -> str:
    """Normalize a task ID to its bare form (e.g. ``T001`` or ``WP01``).

    Accepts:
        - ``T001`` / ``WP01`` (bare) -> returned unchanged
        - ``<mission_slug>/T001`` (qualified) -> ``T001``
        - ``<mission_slug>:WP01`` (qualified) -> ``WP01``

    Garbage inputs are returned unchanged so the downstream "task ID not
    found in tasks.md" error path remains the canonical structured
    failure surface for unknown identifiers.
    """
    if not raw or not isinstance(raw, str):
        return raw
    candidate = raw.strip()
    match = _QUALIFIED_TASK_ID_RE.match(candidate)
    if match:
        # ``str(...)``: the RE2 engine (kernel._safe_re) is untyped, so
        # ``match.group`` is inferred as ``Any``; coerce to the str it already
        # returns at runtime to keep this seam strict-clean (behaviour-identical).
        return str(match.group("task")).upper()
    return candidate


_INLINE_SUBTASKS_RE = re.compile(
    r"(?:Subtasks|\*\*Subtasks\*\*):\s*(?P<ids>(?:T|WP)\d+(?:\s*,\s*(?:T|WP)\d+)*)",
    re.IGNORECASE,
)


def _is_pipe_table_task_row(line: str, task_id: str) -> bool:
    """Return True if *line* is a pipe-table data row containing *task_id*.

    Rules:
    - Separator rows (|---|---| or |:---|:---:|) are always rejected.
    - The task ID must appear as a whole cell, not as a substring of a longer
      token (e.g. "T001" must not match "T0012" or "XT001").
    """
    # Reject separator rows: any row whose non-pipe content is only dashes/colons/spaces
    if re.match(r"^\s*\|[\s\-:]+\|", line):
        return False
    # Match the task ID as a complete cell value (whitespace-padded OK)
    return bool(re.search(rf"\|\s*{re.escape(task_id)}\s*\|", line))


def _parse_pipe_table_header(lines: list[str], task_row_idx: int) -> dict[str, int]:
    """Scan backwards from a pipe-table task row to find its header row.

    Returns a mapping of lower-case column name -> zero-based column index.
    Returns an empty dict if no header can be identified.
    """
    for i in range(task_row_idx - 1, -1, -1):
        candidate = lines[i].strip()
        # Skip separator rows
        if re.match(r"^\|[\s\-:]+\|", candidate):
            continue
        # A header row must contain '|' and must not look like a separator
        if "|" in candidate:
            cells = [c.strip().lower() for c in candidate.split("|")[1:-1]]
            return {name: idx for idx, name in enumerate(cells) if name}
        # Anything else (blank line, heading, etc.) means no header found
        break
    return {}


_WP_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(?P<title>.+?)\s*$")
_WP_ID_TITLE_RE = re.compile(r"^(?:Work Package\s+)?(?P<wp_id>WP\d+)(?:\b|:)", re.IGNORECASE)


def _match_history_wp_heading(line: str) -> str | None:
    """Return the owning WP id from supported tasks.md section headings."""
    heading_match = _WP_HEADING_RE.match(line)
    if not heading_match:
        return None

    title = str(heading_match.group("title")).strip()
    if wp_match := _WP_ID_TITLE_RE.match(title):
        return str(wp_match.group("wp_id")).upper()
    work_package_prefix = "Work Package "
    if title.startswith(work_package_prefix):
        suffix = title[len(work_package_prefix) :]
        digit_count = 0
        while digit_count < len(suffix) and digit_count < 2 and suffix[digit_count].isdigit():
            digit_count += 1
        if digit_count and (digit_count == len(suffix) or not suffix[digit_count].isdigit()):
            remainder = suffix[digit_count:]
            if not remainder or remainder[0].isspace() or remainder[0] in ":-" or ord(remainder[0]) == 0x2014:
                return f"WP{int(suffix[:digit_count]):02d}"
    return None


def _extract_pipe_table_wp_id(line: str, header_map: dict[str, int]) -> str | None:
    """Return the owning WP id from a pipe-table task row, when present."""
    cells = [cell.strip() for cell in line.split("|")[1:-1]]
    for column_name in ("wp", "work package", "work_package", "work package id", "work_package_id"):
        column_index = header_map.get(column_name)
        if column_index is not None and column_index < len(cells):
            candidate = cells[column_index].upper()
            wp_match = re.search(r"\b(WP\d+)\b", candidate)
            if wp_match:
                return str(wp_match.group(1))
    for cell in cells:
        candidate = cell.upper()
        if re.fullmatch(r"WP\d+", candidate):
            return candidate
    return None


def _iter_history_owner_candidates(tasks_content: str, task_id: str) -> Iterator[str | None]:
    """Yield the owning WP (or ``None`` when unattributable) of every STRUCTURED tasks.md
    row that names *task_id*: a pipe-table row, a checkbox row, or an inline
    ``Subtasks:`` list. Prose mentions never yield."""
    normalized_task_id = task_id.upper()
    current_wp_id: str | None = None
    lines = tasks_content.split("\n")

    for line_index, line in enumerate(lines):
        heading_wp_id = _match_history_wp_heading(line)
        if heading_wp_id:
            current_wp_id = heading_wp_id

        if _is_pipe_table_task_row(line, normalized_task_id):
            header_map = _parse_pipe_table_header(lines, line_index)
            yield _extract_pipe_table_wp_id(line, header_map) or current_wp_id
        elif re.search(rf"-\s*\[[ x]\]\s*{re.escape(normalized_task_id)}\b", line, re.IGNORECASE):
            explicit_wp = re.search(r"\b(WP\d+)\b", line, re.IGNORECASE)
            yield current_wp_id or (str(explicit_wp.group(1)).upper() if explicit_wp else None)
        elif inline_match := _INLINE_SUBTASKS_RE.search(line):
            ids = [value.strip().upper() for value in inline_match.group("ids").split(",")]
            if normalized_task_id in ids:
                yield current_wp_id


def _resolve_history_wp_id(tasks_content: str, task_id: str) -> str | None:
    """Resolve the WP that owns *task_id* from tasks.md structure (first structured row)."""
    return next(_iter_history_owner_candidates(tasks_content, task_id), None)


def history_wp_ids(tasks_content: str, task_id: str) -> list[str]:
    """Return every WP whose structured tasks.md rows name *task_id*, sorted.

    Unlike :func:`_resolve_history_wp_id` this does not stop at the first row, so
    a subtask id shared by several work packages is reported for all of them.
    """
    return sorted({owner for owner in _iter_history_owner_candidates(tasks_content, task_id) if owner})


def _resolve_wp_id(
    wp_id: str,
    status: str,
    mission_slug: str | None,
    feature_dir: Path,
) -> TaskIdResult | None:
    """Reject bare WP IDs; mark-status is scoped to task/subtask updates."""
    if not re.match(r"^WP\d+$", wp_id, re.IGNORECASE):
        return None

    normalized_wp_id = wp_id.upper()
    del status, mission_slug, feature_dir
    return TaskIdResult(
        id=normalized_wp_id,
        outcome=TaskIdResolutionOutcome.NOT_FOUND,
        format=TaskIdResolutionFormat.WP_ID,
        message=(
            f"{normalized_wp_id}: mark-status does not change work-package lanes. "
            "Use `spec-kitty agent tasks move-task <WP_ID> --to <lane>`."
        ),
    )
