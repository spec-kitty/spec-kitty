"""Unit tests for the doc-kitty frontmatter contract module (#6931).

These are the *contract's own* tests: they need no doc-kitty, no `site/` and no
built corpus. They pin the four things a contract has to get right —

1. resolution order (an authored value beats a derived one, an index is a `Hub`,
   an unclassified page is a failure and never a guess);
2. the ADR D-7 alias/ADR tables, including the two recorded judgement calls
   (D-8's draft subtrees, and the fact that an alias is *not* applied where D-8
   already decided the lifecycle);
3. the instant grammar's severity split, which mirrors doc-kitty's own
   (date-only and non-UTC are advisories; unparseable is an error);
4. that the migration is frontmatter-only, idempotent, and refuses to collapse a
   value it does not understand.
"""

from __future__ import annotations

import pytest

from scripts.docs.frontmatter_contract import (
    DOC_STATUSES,
    KINDS,
    MAX_DESCRIPTION_LENGTH,
    apply_edit,
    check_instant,
    has_divio_type,
    normalise_doc_status,
    normalise_updated,
    plan_page,
    read_instant,
    resolve_kind,
    validate_page,
)


def _errors(verdict) -> list[str]:
    return [f"{v.field}:{v.reason}" for v in verdict.errors]


def _warnings(verdict) -> list[str]:
    return [f"{v.field}:{v.reason}" for v in verdict.warnings]


# --------------------------------------------------------------------------
# resolve_kind — precedence
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "frontmatter", "expected"),
    [
        # An authored kind always wins: a later migration, or another PR, decided.
        ("docs/guides/how.md", {"kind": "Tutorial", "type": "how-to"}, "Tutorial"),
        # A section index is a Hub, including inside the ADR tree.
        ("docs/guides/index.md", {}, "Hub"),
        ("docs/adr/index.md", {}, "Hub"),
        ("docs/adr/1.x/README.md", {}, "Hub"),
        # The ADR tree is ADR; the file name is still an ADR, not a hub.
        ("docs/adr/1.x/2026-01-23-1-record-it.md", {"status": "Accepted"}, "ADR"),
        # A Divio type folds into its doc-kitty kind (ADR D-7).
        ("docs/guides/getting-started.md", {"type": "tutorial"}, "Tutorial"),
        ("docs/guides/do-it.md", {"type": "how-to"}, "How-To"),
        ("docs/api/commands.md", {"type": "reference"}, "Reference"),
        ("docs/architecture/why.md", {"type": "explanation"}, "Explanation"),
        # The path-prefix table covers the pages that carry no Divio type.
        ("docs/plans/some-plan.md", {}, "Planning"),
        ("docs/changelog/1x/artifacts.md", {}, "Changelog"),
        ("docs/api/agent_profiles/x.md", {}, "Reference"),
        ("docs/architecture/adr-template.md", {}, "Explanation"),
        ("docs/context/audience/internal/x.md", {}, "Explanation"),
        ("docs/migrations/from-charter-2x.md", {}, "How-To"),
        ("docs/operations/recovery-index-x.md", {}, "How-To"),
        # Longest prefix wins: the reference sub-tree beats the section default.
        ("docs/development/reference/version-taxonomy.md", {}, "Reference"),
    ],
)
def test_resolve_kind_precedence(path: str, frontmatter: dict, expected: str) -> None:
    assert resolve_kind(path, frontmatter) == expected


def test_every_resolvable_kind_is_in_the_canonical_set() -> None:
    """A rule may not resolve to a kind doc-kitty does not know."""
    paths = [
        "docs/guides/how-to/x.md",
        "docs/guides/tutorials/x.md",
        "docs/adr/x.md",
        "docs/adr/index.md",
        "docs/plans/x.md",
        "docs/changelog/x.md",
        "docs/api/x.md",
        "docs/architecture/x.md",
        "docs/context/x.md",
        "docs/migrations/x.md",
        "docs/operations/x.md",
        "docs/configuration/x.md",
        "docs/development/reference/x.md",
    ]
    for path in paths:
        kind = resolve_kind(path, {})
        assert kind in KINDS, f"{path} resolved to {kind!r}, outside the canonical set"


def test_an_unclassifiable_page_returns_none_and_is_an_error() -> None:
    """ADR D-7: an unclassified page is a migration failure, never a guess."""
    assert resolve_kind("docs/templates/adr-template.md", {}) is None
    verdict = validate_page(
        "docs/templates/adr-template.md",
        {"title": "t", "description": "d", "doc_status": "active", "updated": "2026-01-01T00:00:00Z"},
    )
    assert "kind:unclassified" in _errors(verdict)


# --------------------------------------------------------------------------
# doc_status — alias table, ADR mapping, D-8 override
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "frontmatter", "expected"),
    [
        # A canonical value is returned unchanged (idempotence).
        ("docs/guides/x.md", {"doc_status": "active"}, "active"),
        ("docs/guides/x.md", {"doc_status": "durable"}, "durable"),
        # ADR D-7's alias table.
        ("docs/architecture/x.md", {"doc_status": "proposal"}, "draft"),
        ("docs/guides/x.md", {"doc_status": "point_in_time"}, "durable"),
        ("docs/guides/x.md", {"doc_status": "closeout"}, "durable"),
        # ADR D-7's ADR row, including ruling 5 (Proposed stays indexed).
        ("docs/adr/1.x/x.md", {"status": "Accepted"}, "active"),
        ("docs/adr/1.x/x.md", {"status": "Proposed"}, "active"),
        ("docs/adr/1.x/x.md", {"status": "Superseded"}, "superseded"),
        # D-8 beats the alias table inside the draft-and-unpublished subtrees.
        # Applying D-7's point_in_time -> durable here would publish a page the
        # operator ruled unpublished.
        ("docs/plans/engineering-notes/x.md", {"doc_status": "point_in_time"}, "draft"),
        # An *authored* canonical value wins even inside a D-8 draft subtree: D-8
        # governs what the migration derives (#6932 owns marking those subtrees),
        # not what a human may author on a page.
        ("docs/plans/engineering-notes/x.md", {"doc_status": "durable"}, "durable"),
        ("docs/plans/investigations/x.md", {"doc_status": "point_in_time"}, "draft"),
        ("docs/plans/research/x.md", {}, "draft"),
    ],
)
def test_normalise_doc_status(path: str, frontmatter: dict, expected: str) -> None:
    assert normalise_doc_status(path, frontmatter) == expected


def test_unknown_doc_status_is_reported_not_rewritten() -> None:
    """A value nobody mapped is a human decision, not a migration input."""
    assert normalise_doc_status("docs/guides/x.md", {"doc_status": "retired"}) == "retired"
    verdict = validate_page(
        "docs/guides/x.md",
        {
            "title": "t",
            "description": "d",
            "doc_status": "retired",
            "updated": "2026-01-01T00:00:00Z",
            "kind": "Reference",
        },
    )
    assert "doc_status:outside_canonical_set" in _warnings(verdict)


def test_every_canonical_doc_status_maps_to_itself() -> None:
    for value in DOC_STATUSES:
        assert normalise_doc_status("docs/guides/x.md", {"doc_status": value}) == value


def test_unmapped_adr_status_is_an_error() -> None:
    verdict = validate_page(
        "docs/adr/1.x/x.md",
        {"title": "t", "description": "d", "status": "Withdrawn", "date": "2026-01-01"},
    )
    assert "status:unmapped_adr_status" in _errors(verdict)


# --------------------------------------------------------------------------
# updated — instant grammar and its severity split
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "canonical", "advisory"),
    [
        ("2026-10-26T00:00:00Z", "2026-10-26T00:00:00Z", None),
        ("2026-10-26", "2026-10-26T00:00:00Z", "date-only"),
        ("2026-10-26T05:00:00+02:00", "2026-10-26T03:00:00Z", "not UTC"),
        ("2026-10-26T00:00:00", "2026-10-26T00:00:00Z", "no zone"),
        ("2026-02-30", None, None),
        ("last tuesday", None, None),
        ("", None, None),
        (None, None, None),
    ],
)
def test_read_instant(raw: object, canonical: str | None, advisory: str | None) -> None:
    reading = read_instant(raw)
    assert reading.canonical == canonical
    if advisory is None:
        assert reading.advisory is None
    else:
        assert reading.advisory is not None and advisory in reading.advisory


def test_check_instant_is_strict_about_the_canonical_form() -> None:
    assert check_instant("2026-10-26T00:00:00Z") is None
    for value in ("2026-10-26", "2026-10-26T00:00:00", "2026-10-26T00:00:00+02:00", "2026-13-01T00:00:00Z"):
        assert check_instant(value) is not None


def test_date_only_updated_is_a_warning_while_unparseable_is_an_error() -> None:
    """Upstream parity: doc-kitty advises on a non-canonical instant, rejects garbage."""
    base = {"title": "t", "description": "d", "doc_status": "active", "kind": "Reference"}
    dated = validate_page("docs/guides/x.md", {**base, "updated": "2026-10-26"})
    assert dated.errors == ()
    assert "updated:not_canonical" in _warnings(dated)

    garbage = validate_page("docs/guides/x.md", {**base, "updated": "sometime last year"})
    assert "updated:unparseable" in _errors(garbage)


def test_adr_updated_comes_from_date_and_an_explicit_updated_wins() -> None:
    assert (
        normalise_updated("docs/adr/1.x/x.md", {"status": "Accepted", "date": "2026-01-23"})
        == "2026-01-23T00:00:00Z"
    )
    # An explicit `updated` is a later amendment; the decision date must not win.
    assert (
        normalise_updated(
            "docs/adr/1.x/x.md",
            {"status": "Accepted", "date": "2026-01-23", "updated": "2026-05-01"},
        )
        == "2026-05-01T00:00:00Z"
    )


# --------------------------------------------------------------------------
# validate_page — severity parity with the pinned doc-kitty gate
# --------------------------------------------------------------------------


def test_a_minimal_valid_page_is_clean() -> None:
    verdict = validate_page(
        "docs/guides/x.md",
        {
            "title": "Do the thing",
            "description": "A description that is comfortably inside the band of the gate.",
            "doc_status": "active",
            "updated": "2026-10-26T00:00:00Z",
            "kind": "How-To",
        },
    )
    assert verdict.errors == ()
    assert verdict.warnings == ()


def test_absent_required_fields_are_errors_naming_each_field() -> None:
    verdict = validate_page("docs/guides/x.md", {})
    missing = {v.field for v in verdict.errors if v.reason == "required"}
    assert missing == {"title", "description", "doc_status", "updated", "kind"}


def test_divio_type_remaining_on_a_page_is_a_warning_not_an_error() -> None:
    verdict = validate_page(
        "docs/guides/x.md",
        {
            "title": "t",
            "description": "d",
            "doc_status": "active",
            "updated": "2026-10-26T00:00:00Z",
            "kind": "How-To",
            "type": "how-to",
        },
    )
    assert verdict.errors == ()
    assert "type:outside_canonical_set" in _warnings(verdict)


def test_over_long_description_warns() -> None:
    verdict = validate_page(
        "docs/guides/x.md",
        {
            "title": "t",
            "description": "x" * (MAX_DESCRIPTION_LENGTH + 1),
            "doc_status": "active",
            "updated": "2026-10-26T00:00:00Z",
            "kind": "How-To",
        },
    )
    assert "description:too_long" in _warnings(verdict)


def test_presentation_and_persona_path_invariants_are_errors() -> None:
    presentation = validate_page(
        "docs/guides/deck.md",
        {
            "title": "t",
            "description": "d",
            "doc_status": "active",
            "updated": "2026-10-26T00:00:00Z",
            "kind": "Presentation",
        },
    )
    assert "kind:presentation_path" in _errors(presentation)

    persona = validate_page(
        "docs/context/audience/x.md",
        {
            "title": "t",
            "description": "d",
            "doc_status": "active",
            "updated": "2026-10-26T00:00:00Z",
            "kind": "Persona",
        },
    )
    assert "role:persona_requires_field" in _errors(persona)


def test_has_divio_type_only_flags_divio_values() -> None:
    assert has_divio_type({"type": "how-to"}) is True
    assert has_divio_type({"type": "Guide"}) is False
    assert has_divio_type({}) is False


# --------------------------------------------------------------------------
# Migration — frontmatter-only, idempotent, refuses what it cannot represent
# --------------------------------------------------------------------------

_SAMPLE = """---
title: 'A page'
description: 'A description long enough to be plausible for the gate.'
updated: '2026-10-26'
doc_status: proposal
audience: docs/context/audience/internal/maintainer.md
type: how-to
---

# A page

Body **must not move**, including this `---` line and trailing whitespace.   
"""


def test_plan_page_proposes_kind_updated_and_divio_type_removal() -> None:
    edit = plan_page("docs/guides/sample.md", _SAMPLE)
    assert edit.set_values == {
        "kind": "How-To",
        "doc_status": "draft",
        "updated": "2026-10-26T00:00:00Z",
    }
    assert edit.drop_keys == ("type",)


def test_apply_edit_changes_only_frontmatter_lines() -> None:
    edit = plan_page("docs/guides/sample.md", _SAMPLE)
    result = apply_edit(_SAMPLE, edit)
    body = _SAMPLE.split("\n---\n", 1)[1]
    assert result.split("\n---\n", 1)[1] == body
    assert "type: how-to" not in result
    assert "audience: docs/context/audience/internal/maintainer.md" in result
    assert "kind: How-To" in result
    assert "updated: '2026-10-26T00:00:00Z'" in result
    assert "doc_status: draft" in result


def test_apply_edit_is_idempotent() -> None:
    once = apply_edit(_SAMPLE, plan_page("docs/guides/sample.md", _SAMPLE))
    assert plan_page("docs/guides/sample.md", once).is_empty()
    assert apply_edit(once, plan_page("docs/guides/sample.md", once)) == once


def test_apply_edit_preserves_crlf_and_a_body_without_trailing_newline() -> None:
    """A CRLF page stays CRLF, and the body after the *closing* fence is verbatim."""
    text = "---\r\ntitle: t\r\nkind: Reference\r\nupdated: '2026-01-01'\r\n---\r\nbody line\r\n"
    result = apply_edit(text, plan_page("docs/api/x.md", text))
    assert result.count("---\r\n") == 2  # opening and closing fence, no stray fence
    assert result.endswith("---\r\nbody line\r\n")
    assert "\n" not in result.replace("\r\n", "")  # no bare LF introduced

    without_trailing = "---\ntitle: t\nkind: Reference\nupdated: '2026-01-01'\n---\nbody with no newline"
    rewritten = apply_edit(without_trailing, plan_page("docs/api/x.md", without_trailing))
    assert rewritten.endswith("---\nbody with no newline")


def test_apply_edit_refuses_a_block_scalar_it_would_collapse() -> None:
    text = "---\ntitle: t\nupdated: >-\n  2026-10-26\n---\nbody\n"
    with pytest.raises(ValueError, match="spans"):
        apply_edit(text, plan_page("docs/api/x.md", text))


def test_plan_page_refuses_a_page_without_frontmatter() -> None:
    with pytest.raises(ValueError, match="no frontmatter"):
        plan_page("docs/guides/x.md", "no frontmatter here\n")


def test_plan_page_refuses_an_unclassifiable_page() -> None:
    text = "---\ntitle: t\nupdated: '2026-10-26'\n---\nbody\n"
    with pytest.raises(ValueError, match="unclassified"):
        plan_page("docs/templates/x.md", text)
