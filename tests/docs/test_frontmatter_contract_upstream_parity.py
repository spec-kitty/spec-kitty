"""The contract's mirror of doc-kitty's frontmatter gate, pinned (#6931).

``scripts/docs/frontmatter_contract.py`` states doc-kitty's contract so the corpus
can be checked before the site exists. A mirror that nobody checks is a second,
drifting authority — exactly the defect class this repository's docs tooling keeps
paying for. This module is the check: it records the upstream values, at the commit
the #6100 spike pinned, and fails when the local mirror moves away from them.

Upstream sources (spec-kitty/doc-kitty, commit ``494f2d878e2e4766d9859a4f073efb793ad86900``):

=========================================  ==================================
file                                       what is pinned here
=========================================  ==================================
``src/lib/vocabulary-core.mjs``            ``CANONICAL_REQUIRED``,
                                           ``REQUIRED_FIELD_FLOOR``,
                                           ``STATUSES``, ``KINDS``,
                                           ``DOC_TYPES``,
                                           ``NOT_A_DATE_MESSAGE``
``src/scripts/validate-frontmatter.mjs``   the error/warning split
=========================================  ==================================

Two invariants are asserted, and they fail in different directions:

* **equality** — the required-field tuple and both vocabulary tuples are the
  upstream tuples, in upstream order. A divergence means a page this gate calls
  clean could fail doc-kitty's, or the reverse.
* **agreement with the repository's own enum** — ``DOC_STATUSES`` equals
  :class:`scripts.docs.frontmatter_backfill.DocStatus`. This is the same
  cross-source agreement check the repo already applies to directive 042's
  vocabulary (``tests/docs/test_doc_status_durable.py``); the contract keeps a copy
  of the set *on purpose*, so that the copy can be checked rather than trusted.

If doc-kitty's vocabulary legitimately grows, the change is: update the mirror in
the contract module, update the recorded tuple here in the same commit, and say so
in the PR. That is the intended friction — it is what makes "mirrored" mean
something.
"""

from __future__ import annotations

import pytest

from scripts.docs.frontmatter_backfill import DocStatus
from scripts.docs.frontmatter_contract import (
    ADR_STATUS_TO_DOC_STATUS,
    DOC_STATUSES,
    DOC_TYPES,
    DIVIO_TYPE_TO_KIND,
    FIELD_FLOOR,
    KINDS,
    REQUIRED_FIELDS,
    UPDATED_INSTANT_INSTRUCTIONS,
)

pytestmark = pytest.mark.architectural

#: ``CANONICAL_REQUIRED`` in doc-kitty ``src/lib/vocabulary-core.mjs``.
UPSTREAM_CANONICAL_REQUIRED = ("title", "description", "doc_status", "updated", "kind")

#: ``REQUIRED_FIELD_FLOOR`` — the one field a charter can never relax.
UPSTREAM_REQUIRED_FIELD_FLOOR = ("title",)

#: ``STATUSES`` — the canonical lifecycle values, in upstream order.
UPSTREAM_STATUSES = ("draft", "active", "deprecated", "superseded", "durable")

#: ``KINDS`` — ADR-0009's page-kind vocabulary, in upstream order.
UPSTREAM_KINDS = (
    "Tutorial",
    "How-To",
    "Reference",
    "Explanation",
    "Hub",
    "ADR",
    "Changelog",
    "Glossary",
    "Presentation",
    "Persona",
    "Planning",
    "Feature",
    "User-Journey",
    "Specification",
    "Schematic",
)

#: ``DOC_TYPES`` — the section-type vocabulary (18 items), in upstream order.
UPSTREAM_DOC_TYPES = (
    "Context",
    "Architecture",
    "ADR",
    "Template",
    "Plan",
    "Epic",
    "Feature",
    "API",
    "Configuration",
    "Integration",
    "Security",
    "Guide",
    "Operations",
    "Runbook",
    "Migration",
    "Changelog",
    "Presentation",
    "Specification",
)

#: ``NOT_A_DATE_MESSAGE`` upstream. The local gate reuses the wording so a red
#: message reads the same to a maintainer whichever gate printed it.
UPSTREAM_NOT_A_DATE_MESSAGE = "not a date: write a UTC instant, YYYY-MM-DDTHH:MM:SSZ"


def test_required_fields_match_upstream_canonical_required() -> None:
    assert REQUIRED_FIELDS == UPSTREAM_CANONICAL_REQUIRED


def test_field_floor_matches_upstream() -> None:
    assert FIELD_FLOOR == UPSTREAM_REQUIRED_FIELD_FLOOR
    # The floor is a subset of the required set, and it is never the field the
    # corpus could do without.
    assert set(FIELD_FLOOR) <= set(REQUIRED_FIELDS)


def test_doc_statuses_match_upstream_statuses() -> None:
    assert DOC_STATUSES == UPSTREAM_STATUSES


def test_kinds_match_upstream_kinds() -> None:
    assert KINDS == UPSTREAM_KINDS


def test_doc_types_match_upstream_doc_types() -> None:
    assert DOC_TYPES == UPSTREAM_DOC_TYPES


def test_instant_error_message_matches_upstream() -> None:
    assert UPDATED_INSTANT_INSTRUCTIONS == UPSTREAM_NOT_A_DATE_MESSAGE


def test_doc_statuses_agree_with_the_repository_enum() -> None:
    """The contract's copy of the lifecycle set equals the repo's ``DocStatus``.

    Kept as a copy (not an import) so this assertion can exist: importing would make
    the two sources one and remove the check.
    """
    assert tuple(status.value for status in DocStatus) == DOC_STATUSES


#: The three legacy values ADR D-7 names, exactly as the mapping must carry them.
LEGACY_ALIASES = {"closeout": "durable", "point_in_time": "durable", "proposal": "draft"}


def test_every_alias_target_and_adr_mapping_is_a_canonical_status() -> None:
    """A mapping may only point at a value the corpus is allowed to keep."""
    canonical = set(DOC_STATUSES)
    for alias, target in LEGACY_ALIASES.items():
        assert target in canonical, f"{alias} -> {target} is not canonical"
    for status, target in ADR_STATUS_TO_DOC_STATUS.items():
        assert target in canonical, f"ADR status {status} -> {target} is not canonical"


def test_every_divio_mapping_targets_a_canonical_kind() -> None:
    canonical = set(KINDS)
    for divio, kind in DIVIO_TYPE_TO_KIND.items():
        assert kind in canonical, f"Divio type {divio} -> {kind} is not a canonical kind"


def test_the_three_legacy_doc_status_values_are_the_ones_the_corpus_carried() -> None:
    """Guards the alias table against a silent widening.

    ADR D-7 names exactly three legacy values. A fourth appearing here without the
    corpus growing one is a change nobody asked for.
    """
    from scripts.docs.frontmatter_contract import DOC_STATUS_ALIASES

    assert set(DOC_STATUS_ALIASES) == {"closeout", "point_in_time", "proposal"}
