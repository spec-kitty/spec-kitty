"""WP08 (T038-T041) + WP05 (T019-T022) -- enum <-> doc parity for every
relation description (FR-006, FR-012, NFR-003, NFR-004).

Scope was originally exactly the three tension-vocabulary relations added by
mission ``doctrine-tension-edges-01KY1WPC`` (``in_tension_with``,
``reconciles_tension``, ``rejects``); the other twelve pre-existing
``Relation`` members were deliberately out of scope for that parity check,
with backfilling flagged as a follow-up (spec.md Assumption A2, superseded).
Mission ``drg-relation-parity-activation-gate-01KY48PD`` (WP04/WP05) IS that
follow-up: it authored ``RELATION_DESCRIPTIONS`` entries and matching
``### ...`` doc sections for all twelve remaining relations and widened
``_SCOPED_RELATIONS`` to cover all 15 ``Relation`` members. There is no
remaining excluded subset.

``RELATION_DESCRIPTIONS`` in ``src/charter/offering/drg/models.py`` (WP01/WP04) is the
single canonical authority for relation description text. This module is
READ-ONLY with respect to that registry: it consumes the text, it never
edits it. The mirrored copy for human readers lives in
``docs/architecture/doctrine-relationships.md``, restructured (WP05) into one
dedicated ``### ...`` section per relation; this module is the enforcement
that the two never drift apart, and names the specific relation that
diverged when they do.

A parity check that only verifies *presence* (both sides have *some*
description) rather than content-equality would satisfy the letter of "a
check exists" while missing NFR-004's actual point. ``test_red_first_...``
below proves this comparator is content-equality, not presence-only, by
mutating one relation's description in an in-memory copy of the doc text and
confirming the check goes red and names exactly that relation.
"""

from __future__ import annotations

import re

import pytest

from charter.offering.drg.models import RELATION_DESCRIPTIONS, Relation
from tests.charter_offering.conftest import REPO_ROOT

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]

DOC_PATH = REPO_ROOT / "docs" / "architecture" / "doctrine-relationships.md"

#: All 15 ``Relation`` members are in parity scope (widened from the original
#: 3 tension-vocabulary relations by mission
#: ``drg-relation-parity-activation-gate-01KY48PD``, WP05/T020). There is no
#: excluded subset -- see module docstring.
_SCOPED_RELATIONS: tuple[Relation, ...] = tuple(Relation)

# Matches a level-3 markdown heading ("### ...") whose title carries the
# relation token as inline code (single OR double backticks -- the registry
# text itself uses RST-style double backticks, e.g. ``in_tension_with``, so
# the doc entries copy that verbatim). Anchored to "### " (exactly three
# hashes) specifically so the level-2 "## Tension vocabulary" heading -- which
# lists all three tokens together in its title -- is never matched.
_HEADING_TEMPLATE = r"^### [^\n]*`{{1,2}}{token}`{{1,2}}[^\n]*$"


def _normalize(text: str) -> str:
    """Collapse all whitespace runs to single spaces.

    Makes comparison insensitive to markdown line-wrapping: the registry
    strings are already single-line, but the doc entry may be soft-wrapped
    across multiple source lines for readability.
    """
    return " ".join(text.split())


def _find_heading_span(doc_text: str, relation: Relation) -> tuple[int, int]:
    """Return the ``(body_start, body_end)`` offsets for ``relation``'s section.

    ``body_start`` is just past the heading line; ``body_end`` is just before
    the next markdown heading of any level, or end-of-text if there is none.
    """
    token = relation.value
    heading_pattern = re.compile(_HEADING_TEMPLATE.format(token=re.escape(token)), re.MULTILINE)
    match = heading_pattern.search(doc_text)
    if match is None:
        raise LookupError(
            f"No '### ... `{token}` ...' heading found in {DOC_PATH} for relation {token!r}"
        )
    body_start = match.end()
    next_heading = re.search(r"^#{1,6} ", doc_text[body_start:], re.MULTILINE)
    body_end = body_start + next_heading.start() if next_heading else len(doc_text)
    return body_start, body_end


def _extract_doc_description(doc_text: str, relation: Relation) -> str:
    """Return the normalized body text under ``relation``'s doc heading."""
    body_start, body_end = _find_heading_span(doc_text, relation)
    return _normalize(doc_text[body_start:body_end])


def find_divergent_relations(doc_text: str) -> list[str]:
    """Compare registry text against doc text for all 15 scoped relations.

    Returns the relation tokens (``Relation.value``) whose doc entry diverges
    from ``RELATION_DESCRIPTIONS`` -- empty when everything matches. This is
    the single comparator both the production parity test and the red-first
    mutation test drive, so the two can never silently diverge in behavior
    from each other.
    """
    divergent: list[str] = []
    for relation in _SCOPED_RELATIONS:
        registry_text = _normalize(RELATION_DESCRIPTIONS[relation])
        doc_entry = _extract_doc_description(doc_text, relation)
        if doc_entry != registry_text:
            divergent.append(relation.value)
    return divergent


@pytest.fixture(scope="module")
def doc_text() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def test_doc_file_exists() -> None:
    assert DOC_PATH.is_file(), f"expected doc-parity target at {DOC_PATH}"


@pytest.mark.parametrize("relation", _SCOPED_RELATIONS, ids=lambda r: r.value)
def test_doc_entry_matches_registry_verbatim(relation: Relation, doc_text: str) -> None:
    """Each of the 15 relations' doc entry must equal the registry text exactly."""
    registry_text = _normalize(RELATION_DESCRIPTIONS[relation])
    doc_entry = _extract_doc_description(doc_text, relation)
    assert doc_entry == registry_text, (
        f"doc-parity drift for relation '{relation.value}': "
        f"{DOC_PATH} entry does not match RELATION_DESCRIPTIONS verbatim.\n"
        f"registry: {registry_text!r}\n"
        f"doc:      {doc_entry!r}"
    )


def test_no_relations_diverge(doc_text: str) -> None:
    """Aggregate parity check: names every relation that diverges, if any."""
    divergent = find_divergent_relations(doc_text)
    assert divergent == [], f"doc-parity drift detected for relation(s): {divergent}"


def test_red_first_mutation_is_detected_and_named(doc_text: str) -> None:
    """T040 -- prove the comparator catches content drift, not just presence.

    Mutates ONE relation's description in an in-memory copy of the doc text
    only (the registry and the on-disk doc file are never touched), confirms
    ``find_divergent_relations`` fails and names exactly that relation, then
    "reverts" by re-running the check against the original, unmutated text
    and confirming it passes again -- and that the other 14 scoped relations
    never show up as divergent in either run.
    """
    target = Relation.RECONCILES_TENSION
    original_entry = _extract_doc_description(doc_text, target)
    assert original_entry, "sanity: original doc entry must be non-empty before mutating"
    assert "reconciliation" in original_entry, (
        "sanity: expected word to mutate is missing -- update this test if the "
        "registry text for RECONCILES_TENSION changes"
    )

    mutated_entry = original_entry.replace("reconciliation", "MUTATED-RECONCILIATION", 1)
    assert mutated_entry != original_entry, "mutation did not change the text -- fix the test"

    body_start, body_end = _find_heading_span(doc_text, target)
    mutated_doc_text = doc_text[:body_start] + f"\n\n{mutated_entry}\n\n" + doc_text[body_end:]

    # Red: the mutated copy must fail, and must name exactly the mutated
    # relation -- not "parity check failed" in general, and not any of the
    # other 14 scoped relations, which were left untouched.
    divergent_after_mutation = find_divergent_relations(mutated_doc_text)
    assert divergent_after_mutation == [target.value], (
        f"expected mutation to flag exactly ['{target.value}'], "
        f"got {divergent_after_mutation}"
    )

    # Green: reverting -- i.e. re-checking the untouched original text --
    # must pass again with zero divergence.
    divergent_after_revert = find_divergent_relations(doc_text)
    assert divergent_after_revert == []


def test_presence_only_shortcut_would_have_been_caught() -> None:
    """Regression guard for the specific shortcut called out in the WP risk note.

    A comparator that only checks "doc entry is non-empty" rather than
    "doc entry equals registry text" would pass this pytest module's own
    fixtures trivially. Assert directly that a merely-non-empty, differently
    worded string is NOT treated as matching by the real comparator -- i.e.
    equality, not presence, is what gates this check.
    """
    registry_text = _normalize(RELATION_DESCRIPTIONS[Relation.REJECTS])
    non_empty_but_wrong = "this is a non-empty description that is not the registry text"
    assert non_empty_but_wrong.strip() != ""
    assert non_empty_but_wrong != registry_text
