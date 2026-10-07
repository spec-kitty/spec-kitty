"""Doc-presence check for the 11 design-phase orchestrator-api verbs (WP09).

No pre-existing orchestrator-api-doc-consistency check exists in this repo
(verified: ``grep -rl "orchestrator-api.md" tests/ scripts/`` returns nothing
dedicated to this doc before this test was authored). Per plan.md's
RED-then-GREEN discipline, this small check stands in for that missing
automation: it asserts each of the 11 new verbs landed by WP03-WP08
(``specify``, ``plan``, ``tasks``, ``check-prerequisites``,
``record-analysis``, ``open-decision``, ``resolve-decision``,
``defer-decision``, ``cancel-decision``, ``design-status``,
``answer-decision``) appears as its own markdown heading in
``docs/api/orchestrator-api.md``. It was RED before WP09's doc content was
written (the headings did not exist yet) and is GREEN after.

This test does not verify request/response shape or error-code accuracy --
only heading presence. It is deliberately narrow, matching plan.md section
(h)'s "markdown-lint + doc-consistency check" phrase with a concrete, minimal
implementation rather than leaving that phrase unaddressed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DOC_PATH = _REPO_ROOT / "docs" / "api" / "orchestrator-api.md"

# The 11 new design-phase verbs added by WP03-WP08 (mission
# design-phase-orchestrator-api-01M1HE6M), by their literal orchestrator-api
# command name.
NEW_VERBS = (
    "specify",
    "plan",
    "tasks",
    "check-prerequisites",
    "record-analysis",
    "open-decision",
    "resolve-decision",
    "defer-decision",
    "cancel-decision",
    "design-status",
    "answer-decision",
    "artifact-read",
    "artifact-submit",
    "design-validate",
    "design-context",
    "interview-record",
    "next",
)


def _markdown_headings(text: str) -> list[str]:
    """Return the text of every ATX markdown heading line (``#`` .. ``######``)."""
    headings = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            headings.append(stripped.lstrip("#").strip())
    return headings


def test_orchestrator_api_doc_exists() -> None:
    assert _DOC_PATH.is_file(), f"expected {_DOC_PATH} to exist"


@pytest.mark.parametrize("verb", NEW_VERBS)
def test_new_verb_has_doc_heading(verb: str) -> None:
    """Each of the 11 new verbs must appear as its own heading, by literal name."""
    text = _DOC_PATH.read_text(encoding="utf-8")
    headings = _markdown_headings(text)
    matches = [h for h in headings if verb in h]
    assert matches, f"no markdown heading in {_DOC_PATH.name} mentions the new verb {verb!r}; headings present: {headings!r}"
