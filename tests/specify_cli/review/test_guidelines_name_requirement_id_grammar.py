"""C7 (requirement-id-grammar-01M3NRCA pre-PR fold): the software-dev
mission's action-scoped guidelines pin the requirement-ID grammar bullets
this mission added.

Companion to ``test_antipattern_checklist.py`` (WP07's ATDD for the review
anti-pattern checklist and the specify/tasks/tasks-finalize/tasks-outline
prompt.md files): that file never reads ``guidelines.md``, so a drift in
these three SOURCE files (edited by the charter/guidance work committed
alongside WP07, not this fold) could regress silently. Pins the SPECIFIC
grammar vocabulary each file's own bullet is supposed to carry, not merely
that "something" in the file matches -- a same-file distinctness check
(every needle actually present, not a coincidental substring match on
unrelated prose) is the acceptance-criteria-non-vacuity discipline this
mission's other tests already apply.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_GUIDELINES_ROOT = _REPO_ROOT / "packs" / "built-in" / "missions" / "mission-steps" / "software-dev"

_SPECIFY_GUIDELINES = _GUIDELINES_ROOT / "specify" / "guidelines.md"
_TASKS_GUIDELINES = _GUIDELINES_ROOT / "tasks" / "guidelines.md"
_REVIEW_GUIDELINES = _GUIDELINES_ROOT / "review" / "guidelines.md"


def test_specify_guidelines_name_sc_kind_and_lowercase_suffix() -> None:
    text = _SPECIFY_GUIDELINES.read_text(encoding="utf-8")
    assert "SC-###" in text
    assert "lowercase letter suffix" in text


def test_tasks_guidelines_name_sc_kind_and_lowercase_suffix() -> None:
    text = _TASKS_GUIDELINES.read_text(encoding="utf-8")
    assert "SC-###" in text
    assert "lowercase letter suffix" in text


def test_review_guidelines_name_the_three_rejection_reasons() -> None:
    """FR-019/FR-012 parity: the review checklist names all three shared
    verdict reasons (malformed / unknown_spec_id block; foreign_qualified
    never blocks), not just one or two of them."""
    text = _REVIEW_GUIDELINES.read_text(encoding="utf-8")
    assert "malformed" in text
    assert "unknown_spec_id" in text
    assert "foreign_qualified" in text
