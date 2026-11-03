"""The status reference states the gated rewind family (#7080).

A prose page is the operator-facing half of the rule: the writer refuses a pointerless
rewind and the auditor reports one, and the page must say which edges those are and how a
door supplies the pointer. This pin is deliberately narrow -- it greps for the statements the
change makes, not for their wording everywhere -- so an edit that drops one of them turns red
instead of leaving the page quietly behind the code.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.fast

_STATUS_MODEL = Path("docs/architecture/status-model.md")


def _page() -> str:
    return _STATUS_MODEL.read_text(encoding="utf-8")


def test_the_page_names_the_three_gated_rewinds() -> None:
    page = _page()
    assert "contract gates on `review_ref`" in page
    assert "`for_review -> in_progress`\n(#6514), `approved -> in_progress` (#6955) and `in_review -> in_progress` (#7080)" in page


def test_the_page_names_the_derivation_and_the_append_only_position() -> None:
    page = _page()
    assert "transition_pipeline.py::prepare_transition" in page
    assert "`in_review -> in_progress` row written before #7080" in page


def test_the_page_does_not_claim_the_edge_is_still_deferred() -> None:
    """#6955's carve-out sentence must not survive the closure (#7080)."""
    page = _page()
    assert "is not in the local set yet" not in page
    assert "tracked in" not in page
