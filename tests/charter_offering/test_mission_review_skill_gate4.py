"""Regression pin for the spec-kitty-mission-review skill's Gate 4 doctrine.

Mission ``issue-matrix-partition-integrity-01M3H10A`` WP03 (IC-02, #5171, FR-002).

The Gate-4 doctrine at ``SKILL.md`` used to instruct a raw, unconditional
``cat kitty-specs/<slug>/issue-matrix.json`` -- always the PRIMARY partition,
even on a coord-topology mission whose real verdicts live on the coordination
surface (materialized worktree, or its retained branch post-consolidation).
A manual reviewer following that instruction reads stale primary residue
instead of the actual verdict -- the doctrine half of #5171.

This is a POSITIVE control (FR-002): it asserts the rendered Gate 4 section
names a resolver-backed read (the ``spec-kitty review`` partition-aware gate,
or an equivalent resolver-backed read command/API), not merely that the raw
``cat`` line is gone. A skill edit that just deleted the instruction and left
the reviewer nothing to run would still fail this test.
"""

from __future__ import annotations

import re

import pytest

from tests.charter_offering.conftest import OFFERING_SOURCE_ROOT

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]

_MISSION_REVIEW_SKILL = OFFERING_SOURCE_ROOT / "skills" / "spec-kitty-mission-review" / "SKILL.md"

_GATE4_HEADING_PATTERN = r"^### Gate 4:.*$"

_RAW_CAT_ISSUE_MATRIX_PATTERN = re.compile(r"^\s*cat\s+.*issue-matrix", re.MULTILINE)

# Positive control: the replacement instruction must point at a resolver-backed
# read surface -- either the CLI gate itself (``spec-kitty review``, which
# WP03's code change routes through ``resolve_issue_matrix_partition``) or a
# dedicated resolver-backed read command/API naming the partition helper.
_RESOLVER_BACKED_READ_MARKERS: tuple[str, ...] = (
    "spec-kitty review",
    "resolve_issue_matrix_partition",
)


@pytest.fixture(scope="module")
def skill_text() -> str:
    assert _MISSION_REVIEW_SKILL.is_file(), f"SOURCE skill not found: {_MISSION_REVIEW_SKILL!s}. If the file was moved, update the path in this test."
    return _MISSION_REVIEW_SKILL.read_text(encoding="utf-8")


def _gate4_section(skill_text: str) -> str:
    heading_match = re.search(_GATE4_HEADING_PATTERN, skill_text, re.MULTILINE)
    assert heading_match is not None, "Regression: Gate 4 heading not found in the mission-review skill."
    start = heading_match.end()
    next_heading = re.search(r"^### Gate \d|^### Operator exception path|^## ", skill_text[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading is not None else len(skill_text)
    return skill_text[heading_match.start() : end]


def test_gate4_no_longer_instructs_a_raw_cat_of_issue_matrix(skill_text: str) -> None:
    section = _gate4_section(skill_text)
    assert _RAW_CAT_ISSUE_MATRIX_PATTERN.search(section) is None, (
        "Regression: Gate 4 must not instruct a raw, unconditional "
        "`cat kitty-specs/<slug>/issue-matrix...` -- on a coord-topology "
        "mission that always reads stale PRIMARY residue instead of the "
        "coordination-partition verdict. See spec-kitty#5171 (FR-002)."
    )


def test_gate4_names_a_resolver_backed_read_positive_control(skill_text: str) -> None:
    """FR-002 positive control: Gate 4 must POSITIVELY instruct a resolver-backed
    read, not merely lack the raw `cat` (a bare deletion would pass a mere
    absence check but leave the reviewer nothing to run)."""
    section = _gate4_section(skill_text)
    assert any(marker in section for marker in _RESOLVER_BACKED_READ_MARKERS), (
        "Regression: Gate 4 must name a resolver-backed read surface (e.g. "
        "`spec-kitty review`'s partition-aware gate, or "
        "`resolve_issue_matrix_partition`) so a manual reviewer reads the "
        "coordination-partition verdict, not stale PRIMARY residue. "
        "See spec-kitty#5171 (FR-002)."
    )


def test_gate4_heading_still_present_and_unrelated_gates_unaffected(skill_text: str) -> None:
    """Sanity: Gate 4's heading (and its FR-037 citation) survives the edit --
    this is a content fix inside the section, not a section removal."""
    heading_match = re.search(_GATE4_HEADING_PATTERN, skill_text, re.MULTILINE)
    assert heading_match is not None
    assert "FR-037" in heading_match.group(0)
