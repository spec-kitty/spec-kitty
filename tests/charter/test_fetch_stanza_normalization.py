"""Red-first ATDD: fetch-stanza when-clause normalization (#3082, WP01 T001).

`fetch_stanza_lines` composes the ``When you <clause>, run this command and
apply the returned rule.`` disclosure line from an arbitrary authored ``when``
clause. Authored clauses are frequently gerund phrases or full sentences
(see ``src/charter/offering/agent_profile.graph.yaml``, e.g. ``designing or reviewing
significant code changes``, or the ``STATED_DEFAULT_WHEN`` fallback), which
today are spliced verbatim after ``When you`` and read as ungrammatical --
e.g. ``When you designing or reviewing significant code changes, run this
command ...``. The fix must normalize every clause shape into a form headed
by one of the CLOSED 6-verb ``_WHEN_DOING_RE`` lead-ins
(``are about to|need to|encounter|introduce|rename|review`` --
``tests/specify_cli/next/test_wp_prompt_governance_contract.py:221``) so the
prompt-governance contract keeps matching per rendered stanza, not merely
somewhere in the whole prompt.

This test is RED before T002's normalization lands in
``src/charter/activation/context_renderers/fetch_stanza.py``.
"""

from __future__ import annotations

import pytest

from charter.activation.context_renderers.fetch_stanza import (
    DEFAULT_WHEN_CLAUSE,
    fetch_stanza_lines,
)
from charter.activation.progressive_disclosure import STATED_DEFAULT_WHEN
from tests.specify_cli.next.test_wp_prompt_governance_contract import _WHEN_DOING_RE

pytestmark = [pytest.mark.fast, pytest.mark.unit]

_SELECTOR = "directive:DIRECTIVE_030"


def _when_line(clause: str) -> str:
    """Render the two-line stanza for *clause* and return its second line."""
    lines = fetch_stanza_lines(_SELECTOR, clause)
    # fetch_stanza_lines' return shape IS a fixed 2-line stanza (selector line +
    # When-clause line); there is no named-item collection here for a
    # set/frozenset equality to express more strongly than the count.
    assert len(lines) == 2, (
        f"fetch_stanza_lines must always return exactly 2 lines, got {lines!r}"
    )
    return lines[1]


class TestFetchStanzaWhenClauseGrammaticality:
    """SC-003 (#3082): every clause shape authored across the doctrine graph
    must render a grammatical ``When you ...`` line headed by one of the
    closed ``_WHEN_DOING_RE`` lead-ins -- asserted PER STANZA (this test
    renders and checks one stanza at a time), never via a whole-prompt
    ``.search()`` that a single unrelated matching line elsewhere would pass.
    """

    def test_leading_gerund_clause_is_normalized_and_matches(self) -> None:
        # Verbatim string authored in src/charter/offering/agent_profile.graph.yaml
        # (agent_profile:architect-alphonso -> paradigm:domain-driven-design,
        # relation: suggests).
        clause = "designing or reviewing significant code changes"
        line = _when_line(clause)
        assert "When you designing" not in line, (
            f"Gerund clause must not be spliced directly after 'When you': {line!r}"
        )
        assert _WHEN_DOING_RE.search(line), (
            f"Normalized gerund clause must match the closed lead-in set: {line!r}"
        )

    def test_full_sentence_stated_default_when_is_normalized_and_matches(self) -> None:
        # STATED_DEFAULT_WHEN is a complete sentence ending in a period --
        # rendering it verbatim doubles the sentence terminator into
        # "...authored yet)., run this command ...".
        line = _when_line(STATED_DEFAULT_WHEN)
        assert ".," not in line, f"Must not double a sentence terminator: {line!r}"
        assert _WHEN_DOING_RE.search(line), (
            f"Normalized STATED_DEFAULT_WHEN must match the closed lead-in set: {line!r}"
        )

    def test_already_well_formed_clause_is_byte_unchanged(self) -> None:
        # DEFAULT_WHEN_CLAUSE already begins with the "are about to" lead-in --
        # the good path must not be touched by normalization (no regression).
        line = _when_line(DEFAULT_WHEN_CLAUSE)
        assert line == (
            f"When you {DEFAULT_WHEN_CLAUSE}, run this command and apply the returned rule."
        )
        assert _WHEN_DOING_RE.search(line)

    def test_need_to_style_clause_passes_through_unchanged(self) -> None:
        clause = "need to add a database migration for the schema change"
        line = _when_line(clause)
        assert line == (
            f"When you {clause}, run this command and apply the returned rule."
        )
        assert _WHEN_DOING_RE.search(line)

    def test_review_style_clause_passes_through_unchanged(self) -> None:
        clause = "review a merged diff for terminology drift"
        line = _when_line(clause)
        assert line == (
            f"When you {clause}, run this command and apply the returned rule."
        )
        assert _WHEN_DOING_RE.search(line)

    def test_leading_when_prefixed_authored_clause_is_normalized_and_matches(self) -> None:
        # Verbatim string authored in src/charter/offering/agent_profile.graph.yaml
        # (agent_profile:python-pedro -> directive:DIRECTIVE_030, suggests).
        # Authors wrote a redundant leading "when" that would otherwise
        # double into "When you when assessing ...".
        clause = "when assessing whether tests meet the quality gate they must pass"
        line = _when_line(clause)
        assert "when you when" not in line.lower(), (
            f"Must not double the 'when' conjunction: {line!r}"
        )
        assert _WHEN_DOING_RE.search(line), (
            f"Normalized when-prefixed clause must match the closed lead-in set: {line!r}"
        )
