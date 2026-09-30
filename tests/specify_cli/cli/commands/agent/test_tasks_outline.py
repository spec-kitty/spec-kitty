"""Direct unit tests for the ``tasks_outline`` parsing seam (WP02, #2058).

These exercise the moved tasks.md / manifest parsers and WP-id resolvers
directly (no CLI, no git), proving the behaviour-preserving extraction and
locking in ≥90% coverage of the new module.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.cli.commands.agent.tasks_outline import (
    TaskIdResolutionFormat,
    TaskIdResolutionOutcome,
    TaskIdResult,
    _extract_pipe_table_wp_id,
    _is_pipe_table_task_row,
    _match_history_wp_heading,
    _normalize_task_id_input,
    _parse_pipe_table_header,
    _resolve_history_wp_id,
    _resolve_wp_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


# ---------------------------------------------------------------------------
# _normalize_task_id_input
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("T001", "T001"),
        ("WP01", "WP01"),
        ("my-mission/T001", "T001"),
        ("my-mission:WP01", "WP01"),
        ("083-some-mission/t012", "T012"),  # qualified + lowercased -> upper
        ("  my-mission/T001  ", "T001"),  # surrounding whitespace stripped
    ],
)
def test_normalize_task_id_input_recognized(raw: str, expected: str) -> None:
    assert _normalize_task_id_input(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("", ""),  # falsy -> early return, unchanged
        ("   ", ""),  # truthy whitespace -> stripped candidate, no match
        ("garbage", "garbage"),
        ("not a task id", "not a task id"),
        ("WP01/extra/segment", "WP01/extra/segment"),
    ],
)
def test_normalize_task_id_input_passthrough(raw: str, expected: str) -> None:
    # Unqualified input passes through (stripped); the downstream
    # "task not found" path remains the canonical surface for garbage.
    assert _normalize_task_id_input(raw) == expected


def test_normalize_task_id_input_non_string() -> None:
    # Non-string falsy/garbage is returned unchanged (defensive guard).
    sentinel: object = 12345
    assert _normalize_task_id_input(sentinel) is sentinel


# ---------------------------------------------------------------------------
# _is_pipe_table_task_row
# ---------------------------------------------------------------------------


def test_is_pipe_table_task_row_match() -> None:
    assert _is_pipe_table_task_row("| T001 | description | WP01 | No |", "T001") is True


def test_is_pipe_table_task_row_padded() -> None:
    assert _is_pipe_table_task_row("|  T001  | desc |", "T001") is True


def test_is_pipe_table_task_row_no_match() -> None:
    assert _is_pipe_table_task_row("| T002 | description |", "T001") is False


def test_is_pipe_table_task_row_rejects_separator() -> None:
    assert _is_pipe_table_task_row("|------|------|", "T001") is False
    assert _is_pipe_table_task_row("| :--- | :---: |", "T001") is False


def test_is_pipe_table_task_row_partial_id_not_matched() -> None:
    # "T001" must not match the longer cell value "T0012".
    assert _is_pipe_table_task_row("| T0012 | desc |", "T001") is False


# ---------------------------------------------------------------------------
# _parse_pipe_table_header
# ---------------------------------------------------------------------------


def test_parse_pipe_table_header_found() -> None:
    lines = [
        "| ID | Description | WP |",
        "|----|-------------|----|",
        "| T001 | do a thing | WP01 |",
    ]
    result = _parse_pipe_table_header(lines, 2)
    assert result == {"id": 0, "description": 1, "wp": 2}


def test_parse_pipe_table_header_skips_separator() -> None:
    lines = [
        "| ID | Status |",
        "|----|--------|",
        "| T001 | [ ] |",
    ]
    result = _parse_pipe_table_header(lines, 2)
    assert result == {"id": 0, "status": 1}


def test_parse_pipe_table_header_no_header() -> None:
    lines = ["", "| T001 | desc |"]
    result = _parse_pipe_table_header(lines, 1)
    assert result == {}


def test_parse_pipe_table_header_at_top() -> None:
    lines = ["| T001 | desc |"]
    result = _parse_pipe_table_header(lines, 0)
    assert result == {}


# ---------------------------------------------------------------------------
# _match_history_wp_heading
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "line, expected",
    [
        ("## WP01: Extract seam", "WP01"),
        ("### WP12 details", "WP12"),
        ("# Work Package WP03", "WP03"),
        ("## Work Package 07: thing", "WP07"),
        ("## Work Package 7", "WP07"),
        ("## wp05 lower", "WP05"),  # case-insensitive
    ],
)
def test_match_history_wp_heading_recognized(line: str, expected: str) -> None:
    assert _match_history_wp_heading(line) == expected


@pytest.mark.parametrize(
    "line",
    [
        "Just a paragraph, not a heading",
        "## Overview",  # heading without a WP id
        "- [ ] T001 a checkbox row",
        "## Work Package 123 too many digits",  # >2 digit guard
        "",
    ],
)
def test_match_history_wp_heading_none(line: str) -> None:
    assert _match_history_wp_heading(line) is None


# ---------------------------------------------------------------------------
# _extract_pipe_table_wp_id
# ---------------------------------------------------------------------------


def test_extract_pipe_table_wp_id_from_named_column() -> None:
    line = "| T001 | desc | WP04 |"
    header_map = {"id": 0, "description": 1, "wp": 2}
    assert _extract_pipe_table_wp_id(line, header_map) == "WP04"


def test_extract_pipe_table_wp_id_alternate_column_name() -> None:
    line = "| T001 | desc | the WP09 owner |"
    header_map = {"id": 0, "description": 1, "work package": 2}
    assert _extract_pipe_table_wp_id(line, header_map) == "WP09"


def test_extract_pipe_table_wp_id_fallback_scan() -> None:
    # No usable header column -> scan every cell for a bare WP id.
    line = "| T001 | desc | WP02 |"
    assert _extract_pipe_table_wp_id(line, {}) == "WP02"


def test_extract_pipe_table_wp_id_absent() -> None:
    line = "| T001 | desc | no owner |"
    assert _extract_pipe_table_wp_id(line, {}) is None


# ---------------------------------------------------------------------------
# _resolve_history_wp_id
# ---------------------------------------------------------------------------


def test_resolve_history_wp_id_via_heading_and_checkbox() -> None:
    content = "\n".join(
        [
            "## WP03: Some package",
            "- [ ] T010 do the thing",
        ]
    )
    assert _resolve_history_wp_id(content, "T010") == "WP03"


def test_resolve_history_wp_id_via_pipe_table_column() -> None:
    content = "\n".join(
        [
            "| ID | Description | WP |",
            "|----|-------------|----|",
            "| T020 | a task | WP06 |",
        ]
    )
    assert _resolve_history_wp_id(content, "T020") == "WP06"


def test_resolve_history_wp_id_pipe_table_falls_back_to_heading() -> None:
    content = "\n".join(
        [
            "## WP08: Owner heading",
            "| ID | Description |",
            "|----|-------------|",
            "| T021 | a task |",
        ]
    )
    # No WP column in the table -> owning heading wins.
    assert _resolve_history_wp_id(content, "T021") == "WP08"


def test_resolve_history_wp_id_checkbox_with_explicit_wp_no_heading() -> None:
    content = "- [ ] T030 belongs to WP11 inline"
    assert _resolve_history_wp_id(content, "T030") == "WP11"


def test_resolve_history_wp_id_checkbox_without_owner() -> None:
    content = "- [ ] T031 no owner anywhere"
    assert _resolve_history_wp_id(content, "T031") is None


def test_resolve_history_wp_id_inline_subtasks() -> None:
    content = "\n".join(
        [
            "## WP02: Seam",
            "Subtasks: T006, T007, T008",
        ]
    )
    assert _resolve_history_wp_id(content, "T007") == "WP02"


def test_resolve_history_wp_id_not_found() -> None:
    content = "## WP01: Nothing here\nsome prose"
    assert _resolve_history_wp_id(content, "T999") is None


# ---------------------------------------------------------------------------
# _resolve_wp_id
# ---------------------------------------------------------------------------


def test_resolve_wp_id_rejects_bare_wp(tmp_path: Path) -> None:
    result = _resolve_wp_id("WP04", "done", "mission", tmp_path)
    assert result is not None
    assert isinstance(result, TaskIdResult)
    assert result.id == "WP04"
    assert result.outcome is TaskIdResolutionOutcome.NOT_FOUND
    assert result.format is TaskIdResolutionFormat.WP_ID
    assert "move-task" in result.message


def test_resolve_wp_id_normalizes_case(tmp_path: Path) -> None:
    result = _resolve_wp_id("wp07", "pending", None, tmp_path)
    assert result is not None
    assert result.id == "WP07"


def test_resolve_wp_id_passes_through_non_wp(tmp_path: Path) -> None:
    # A task id (not a bare WP id) is not this resolver's concern.
    assert _resolve_wp_id("T001", "done", "mission", tmp_path) is None
