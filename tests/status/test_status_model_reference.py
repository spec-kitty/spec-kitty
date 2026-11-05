"""The status reference states the gated rewind family (#6955, #6514).

Docs rot silently. These are grep-level pins on the published reference page: if a
future edit drops the force-insurmountable requirement, the writer table, or the
append-only position for rows written before the fix, this fails instead of the
operator learning about it from a dropped sync.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.fast

_PAGE = Path(__file__).resolve().parents[2] / "docs" / "architecture" / "status-model.md"


@pytest.fixture(scope="module")
def page() -> str:
    return _PAGE.read_text(encoding="utf-8")


def test_the_page_names_the_gated_family(page: str) -> None:
    """Every gated edge's ``from -> to`` spelling is on the page, read off the authority.

    Driven from ``REVIEW_REF_REQUIRED_EDGES`` so the page and the owning edge set
    cannot drift: a member added to the set must appear on the page, and a member
    removed from the set leaves no stale spelling behind.
    """
    from specify_cli.status.wp_state import REVIEW_REF_REQUIRED_EDGES

    assert "Forced rewinds out of review" in page
    assert "force-insurmountable" in page
    for from_lane, to_lane in sorted(REVIEW_REF_REQUIRED_EDGES):
        spelling = f"`{from_lane.value} -> {to_lane.value}`"
        assert spelling in page, f"{spelling} missing from the reference page"


def test_the_page_states_which_each_writer_supplies(page: str) -> None:
    """Every write door is named with the pointer it records, sentinel included."""
    assert "force-override" in page
    for writer in (
        "spec-kitty agent status emit --to in_progress",
        "spec-kitty orchestrator-api transition --to in_progress",
        "spec-kitty agent tasks move-task --to in_progress",
        "spec-kitty agent action implement",
    ):
        assert writer in page, writer


def test_the_page_keeps_the_append_only_recovery_position(page: str) -> None:
    assert "never rewrites historical event bytes" in page
    assert "append-only" in page
    assert "#6955" in page
    assert "#7080" in page
