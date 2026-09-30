"""read-surface-ssot-closeout WP04 (T015/T016) — workflow.py render helpers.

Campsite SAFE items #2 and #3 (DIRECTIVE_025 tidy-first, S1192): the 9x
duplicated blank-box banner line and the byte-identical WP-prompt
begin/end wrapper block are extracted out of the ``implement``/``review``
inline blocks into pure, independently-testable functions. These tests pin
the exact rendered output for both modes so the extraction stays
behaviour-preserving.
"""

from __future__ import annotations

from specify_cli.cli.commands.agent.workflow_cores import (
    render_isolation_banner as _render_isolation_banner,
    render_wp_prompt_wrapper as _render_wp_prompt_wrapper,
)

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]


# ---------------------------------------------------------------------------
# T015 — _render_isolation_banner
# ---------------------------------------------------------------------------


def test_render_isolation_banner_implement_mode() -> None:
    """``implement`` mode renders the ASSIGNED-TO verb + subtask-ownership bullets."""
    lines = _render_isolation_banner("WP04", "implement")

    assert lines[0] == "╔" + "=" * 78 + "╗"
    assert lines[-1] == "╚" + "=" * 78 + "╝"
    assert "║  YOU ARE ASSIGNED TO: WP04" in lines[3]
    assert any("Only mark subtasks belonging to WP04" in line for line in lines)
    assert any("Mark subtasks that don't belong to WP04" in line for line in lines)
    # review-only bullet must NOT appear in implement mode
    assert not any("Review or approve any WP other than" in line for line in lines)


def test_render_isolation_banner_review_mode() -> None:
    """``review`` mode renders the REVIEWING verb + review-ownership bullet."""
    lines = _render_isolation_banner("WP04", "review")

    assert lines[0] == "╔" + "=" * 78 + "╗"
    assert lines[-1] == "╚" + "=" * 78 + "╝"
    assert "║  YOU ARE REVIEWING: WP04" in lines[3]
    assert any("Review or approve any WP other than WP04" in line for line in lines)
    # implement-only bullets must NOT appear in review mode
    assert not any("Only mark subtasks belonging to" in line for line in lines)
    assert not any("Mark subtasks that don't belong to" in line for line in lines)


def test_render_isolation_banner_lines_are_fixed_width() -> None:
    """Every frame (``╔``/``╚``) line in the banner keeps the fixed 80-char box width.

    Behaviour-preservation guard: the extraction must not silently drop or
    change the padding that keeps the box rectangular. Emoji-bearing ``║``
    content lines are excluded — some emoji are multi-codepoint, so
    ``len()`` legitimately diverges from on-screen width for those lines
    (unchanged from the pre-extraction inline code; not a regression).
    """
    for mode in ("implement", "review"):
        for line in _render_isolation_banner("WP04", mode):
            if line.startswith(("╔", "╚")):
                assert len(line) == 80, f"mode={mode!r} line {line!r} is not 80 chars wide"


# ---------------------------------------------------------------------------
# T016 — _render_wp_prompt_wrapper
# ---------------------------------------------------------------------------


def test_render_wp_prompt_wrapper_wraps_text_with_markers() -> None:
    """The wrapper surrounds ``wp_text`` with BEGIN/END banner markers."""
    lines = _render_wp_prompt_wrapper("WP CONTENT HERE")

    assert lines == [
        "╔" + "=" * 78 + "╗",
        "║  WORK PACKAGE PROMPT BEGINS                                            ║",
        "╚" + "=" * 78 + "╝",
        "",
        "WP CONTENT HERE",
        "",
        "╔" + "=" * 78 + "╗",
        "║  WORK PACKAGE PROMPT ENDS                                              ║",
        "╚" + "=" * 78 + "╝",
        "",
    ]


def test_render_wp_prompt_wrapper_is_ten_lines_including_content() -> None:
    """The wrapper is exactly the 10-line frame (9 markers + the content line)."""
    lines = _render_wp_prompt_wrapper("")
    assert len(lines) == 10
