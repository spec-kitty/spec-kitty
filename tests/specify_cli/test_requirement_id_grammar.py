"""Unit tests for the single requirement-ID grammar authority (T003, C-001).

Every refusal below is paired with a same-fixture positive control
(acceptance-criteria-non-vacuity): a rejection is only meaningful proven
next to a case the same code path accepts.
"""

from __future__ import annotations

import pytest

from specify_cli.requirement_mapping import grammar, parse_requirement_ids_from_spec_md
from specify_cli.requirement_mapping.lint import lint_spec_requirement_ids

pytestmark = [pytest.mark.unit, pytest.mark.fast]


# --------------------------------------------------------------------------- #
# RE2 (C-005).
# --------------------------------------------------------------------------- #


def test_every_exported_pattern_compiles() -> None:
    # Every module-level compiled Pattern object in grammar.py -- discovered
    # dynamically so this stays complete as patterns are added or renamed,
    # rather than a hand-maintained list that silently omits a new one.
    pattern_type = type(grammar._STRICT_REF_MATCH)
    patterns = {name: value for name, value in vars(grammar).items() if isinstance(value, pattern_type)}
    assert len(patterns) >= 9, f"expected at least 9 compiled patterns in grammar.py, found {sorted(patterns)}"
    for name, pattern in patterns.items():
        assert pattern.pattern, f"{name} compiled to an empty/falsy pattern"
    for pattern in grammar.DECLARED_SHAPE_PATTERNS:
        assert pattern.pattern


# --------------------------------------------------------------------------- #
# Placeholder / canonical form / digit width.
# --------------------------------------------------------------------------- #


def test_placeholder_not_found_in_spec_scan_but_sibling_id_is() -> None:
    """FR-00N (~37 corpus hits, an unfilled template placeholder) must not
    parse under spec scanning; the same-text sibling FR-006a still does."""
    text = "… FR-00N … FR-006a …"
    scanned = [i.canonical for i in grammar.find_all(text, spec_scan=True)]
    assert scanned == ["FR-006a"]


def test_placeholder_under_ref_matching_case_tolerance_is_explicitly_pinned() -> None:
    """spec_scan=False (ref-item matching) is intentionally suffix-case-tolerant
    (mitigation note: tolerance lives only in parse/canonical and
    find_all(spec_scan=False)), so FR-00N there parses as FR-00 with an
    uppercase-tolerant suffix "n" -- pinned explicitly, not asserted empty."""
    ids = grammar.find_all("FR-00N", spec_scan=False)
    assert [i.canonical for i in ids] == ["FR-00n"]


def test_canonical_form() -> None:
    assert grammar.canonical("FR-006A") == "FR-006a"
    assert grammar.canonical("fr-006a") == "FR-006a"
    assert grammar.canonical("FR-006-a") is None


def test_digit_width_is_significant() -> None:
    assert grammar.parse("C-1") != grammar.parse("C-001")
    assert grammar.parse("C-001") == grammar.parse("c-001")


# --------------------------------------------------------------------------- #
# Qualifier consumed.
# --------------------------------------------------------------------------- #


def test_qualifier_consumed_foreign_and_local_coexist() -> None:
    ids = grammar.find_all("see other-mission#FR-001 and also FR-001", spec_scan=False)
    rendered = [str(i) for i in ids]
    assert rendered == ["other-mission#FR-001", "FR-001"]
    foreign, local = ids
    assert foreign.is_foreign is True
    assert local.is_foreign is False


@pytest.mark.parametrize(
    "text",
    [
        "Other-Mission#FR-001",
        "other_mission#FR-001",
        "x.y#FR-001",
    ],
)
def test_find_all_never_leaks_a_local_id_from_an_invalid_qualifier(text: str) -> None:
    """FR-009: an invalid qualifier must never surface as a local (or wrongly
    truncated foreign) id. `#` is itself a non-word character, so `\\b` holds
    right after it: a slug that fails the qualifier grammar (an uppercase
    letter, an underscore, an embedded dot) must not silently degrade to a
    bare local match, nor to a truncated foreign one. The whole `...#ID` run
    is dropped entirely."""
    assert grammar.find_all(text, spec_scan=False) == []


def test_find_all_invalid_qualifier_same_text_positive_control() -> None:
    """Same-text positive control for each invalid-qualifier case above: a
    clean bare id elsewhere in the same text is still found."""
    for invalid, expected in [
        ("Other-Mission#FR-001", "FR-002"),
        ("other_mission#FR-001", "FR-002"),
        ("x.y#FR-001", "FR-002"),
    ]:
        text = f"{invalid} beside a bare {expected} too"
        ids = [i.canonical for i in grammar.find_all(text, spec_scan=False)]
        assert ids == [expected], (text, ids)


def test_find_all_valid_qualifier_still_recognised() -> None:
    """Positive control proving the invalid-qualifier checks do not over-reach:
    a genuinely well-formed qualifier is still recognised as foreign."""
    ids = grammar.find_all("other-mission#FR-001", spec_scan=False)
    assert [str(i) for i in ids] == ["other-mission#FR-001"]


def test_requirement_id_kind_properties() -> None:
    fr = grammar.parse("FR-001")
    nfr = grammar.parse("NFR-001")
    c = grammar.parse("C-001")
    sc = grammar.parse("SC-001")
    assert fr is not None and nfr is not None and c is not None and sc is not None

    assert fr.is_functional is True
    assert fr.is_success_criterion is False

    assert sc.is_success_criterion is True
    assert sc.is_functional is False

    assert nfr.is_functional is False
    assert nfr.is_success_criterion is False

    assert c.is_functional is False
    assert c.is_success_criterion is False


# --------------------------------------------------------------------------- #
# Prose compounds.
# --------------------------------------------------------------------------- #


def test_prose_compounds_are_not_ids() -> None:
    assert grammar.parse("FR-008-mandated") is None
    assert grammar.parse("C-007-mission") is None
    assert grammar.parse("FR-008") is not None


def test_prose_compound_find_all_yields_nothing_but_bare_sibling_is_found() -> None:
    text = "FR-008-mandated and C-007-mission but also bare FR-008 here"
    ids = grammar.find_all(text, spec_scan=True)
    assert [str(i) for i in ids] == ["FR-008"]


# --------------------------------------------------------------------------- #
# Boundary negative controls (each with a same-text positive).
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("IC-01 vs C-01", ["C-01"]),
        ("XFR-001 vs FR-001", ["FR-001"]),
        ("only FR-00N appears here", []),
        ("FR-008-mandated vs FR-008", ["FR-008"]),
        ("FR-0011x alone", ["FR-0011x"]),
        ("x_FR-001 vs FR-001", ["FR-001"]),
        ("FR-001_ vs FR-001", ["FR-001"]),
    ],
)
def test_boundary_negative_controls(text: str, expected: list[str]) -> None:
    assert [i.canonical for i in grammar.find_all(text, spec_scan=True)] == expected


def test_fr_00_alone_is_never_found() -> None:
    assert grammar.find_all("FR-00N", spec_scan=True) == []


def test_c_dash_1_dash_2_is_not_an_id_in_prose() -> None:
    text = "C-1-2 is not an id, but bare C-1 elsewhere is"
    ids = [i.canonical for i in grammar.find_all(text, spec_scan=True)]
    assert ids == ["C-1"]


def test_unicode_suffix_behaves_identically_under_re2() -> None:
    """FR-001é must not be mistaken for a suffixed id under either matching mode."""
    for spec_scan in (True, False):
        ids = grammar.find_all("FR-001é", spec_scan=spec_scan)
        assert [i.canonical for i in ids] == ["FR-001"]


# --------------------------------------------------------------------------- #
# Dotted.
# --------------------------------------------------------------------------- #


def test_dotted_number_is_not_an_id() -> None:
    assert grammar.parse("FR-001.1") is None
    assert grammar.parse("FR-001") is not None


@pytest.mark.parametrize(
    "text",
    [
        "see FR-002.3 in the table",
        "### FR-001.1 Title",
        "**FR-004.1** x",
    ],
)
def test_dotted_id_is_dropped_not_truncated_by_find_all(text: str) -> None:
    """A dotted sub-id must never be silently truncated to its well-formed
    prefix (``FR-002.3`` -> ``FR-002``): that would let ``find_all``/the
    declared-id scan accept a token as if the shorter id alone had been
    written, disagreeing with the setup-plan lint, which refuses the SAME
    dotted token as malformed (both read the same lead charset,
    ``[A-Za-z0-9_.-]``, so they must agree on what the token even is)."""
    assert grammar.find_all(text, spec_scan=True) == []


def test_dotted_id_sentence_final_period_positive_control() -> None:
    """A sentence-final period (not a dotted tail) must still yield the id --
    the compound-tail check only fires when a following ``.`` is itself
    immediately followed by an alphanumeric character."""
    assert [i.canonical for i in grammar.find_all("see FR-001. Next sentence.", spec_scan=True)] == ["FR-001"]
    assert [i.canonical for i in grammar.find_all("see FR-001.", spec_scan=True)] == ["FR-001"]


@pytest.mark.parametrize(
    ("shape_line", "dotted_id"),
    [
        ("| FR-002.3 | text |", "FR-002.3"),
        ("### FR-001.1 Title", "FR-001.1"),
        ("**FR-004.1** x", "FR-004.1"),
    ],
)
def test_declared_scan_and_lint_agree_on_dotted_ids(shape_line: str, dotted_id: str) -> None:
    """FR-013 agreement: the declared-ID scan (via
    ``parse_requirement_ids_from_spec_md``) and the setup-plan lint must
    agree that a dotted lead is NOT a well-formed declaration -- the scan
    drops it (never silently counts the truncated prefix as declared), and
    the lint refuses it as malformed. A same-fixture positive control (the
    sentence-final ``FR-001.``) proves the lint is still scanning the text,
    not vacuously silent."""
    text = f"# Spec\n\n{shape_line}\n\nsee FR-001.\n"

    truncated_prefix = dotted_id.split(".")[0]
    declared = parse_requirement_ids_from_spec_md(text)
    assert truncated_prefix not in declared["all"], f"{dotted_id} must not be truncated into the declared set as {truncated_prefix}"

    lint_result = lint_spec_requirement_ids(text)
    assert any(error.token == dotted_id for error in lint_result.errors), lint_result.errors


# --------------------------------------------------------------------------- #
# Uppercase mid8 slug tail.
# --------------------------------------------------------------------------- #


def test_uppercase_mid8_slug_tail_and_plain_slug_both_parse() -> None:
    rid = grammar.parse("requirement-id-grammar-01M3NRCA#FR-001")
    assert rid is not None
    assert rid.mission == "requirement-id-grammar-01M3NRCA"
    assert rid.canonical == "FR-001"

    plain = grammar.parse("other-mission#FR-001")
    assert plain is not None
    assert plain.mission == "other-mission"


# --------------------------------------------------------------------------- #
# Declared shapes.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("shape_index", "line", "expected_id"),
    [
        (0, "| SC-001 | text |", "SC-001"),
        (0, "| FR-006a | text |", "FR-006a"),
        (1, "### SC-001: Title", "SC-001"),
        (1, "### FR-006a: Title", "FR-006a"),
        (2, "- SC-001: text", "SC-001"),
        (2, "- FR-006a: text", "FR-006a"),
        (2, "- **SC-001**: text", "SC-001"),
        (2, "- **FR-006a**: text", "FR-006a"),
        (3, "**SC-001** leads a paragraph.", "SC-001"),
        (3, "**FR-006a** leads a paragraph.", "FR-006a"),
    ],
)
def test_each_declared_shape_recognises_success_criteria_and_suffixed_ids(shape_index: int, line: str, expected_id: str) -> None:
    """Each of the 4 declared shapes (table=0, heading=1, bullet=2, bold
    paragraph lead=3) recognises both SC and a letter-suffixed FR, asserted
    against the SPECIFIC intended shape's ``group(1)`` -- not merely "some
    pattern in the tuple matched"."""
    pattern = grammar.DECLARED_SHAPE_PATTERNS[shape_index]
    match = pattern.match(line)
    assert match is not None, f"shape {shape_index} did not match {line!r}"
    assert match.group(1) == expected_id


def test_uppercase_suffix_declares_nothing_lowercase_declares() -> None:
    upper_line = "| FR-006A | text |"
    lower_line = "| FR-006a | text |"
    upper_matches = [p.match(upper_line) for p in grammar.DECLARED_SHAPE_PATTERNS]
    lower_matches = [p.match(lower_line) for p in grammar.DECLARED_SHAPE_PATTERNS]
    assert all(m is None for m in upper_matches)
    assert any(m is not None for m in lower_matches)


def test_concern_id_is_never_declared() -> None:
    line = "### IC-01: Some concern"
    matched = [p.match(line) for p in grammar.DECLARED_SHAPE_PATTERNS]
    assert all(m is None for m in matched)


# --------------------------------------------------------------------------- #
# MALFORMED_DECLARED_LEAD.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "line",
    ["- C-style strings", "| C-suite |", "- c-001 lowercase"],
)
def test_malformed_declared_lead_negative_controls(line: str) -> None:
    assert grammar.MALFORMED_DECLARED_LEAD.match(line) is None


@pytest.mark.parametrize(
    "line",
    ["| C-S1 |", "| C-007-mission |"],
)
def test_malformed_declared_lead_same_fixture_positives(line: str) -> None:
    match = grammar.MALFORMED_DECLARED_LEAD.match(line)
    assert match is not None
    assert grammar.parse(match.group("lead")) is None


@pytest.mark.parametrize(
    ("line", "expected_lead"),
    [
        ("- **FR-009's** trailing apostrophe", "FR-009"),
        ("| FR-001/FR-002 | cited pair |", "FR-001"),
        ("| FR-002–FR-006 | en-dash range |", "FR-002"),
        ("- **SC-001…004** ellipsis range", "SC-001"),
    ],
)
def test_malformed_declared_lead_capture_charset_stops_at_first_other_char(line: str, expected_lead: str) -> None:
    match = grammar.MALFORMED_DECLARED_LEAD.match(line)
    assert match is not None
    assert match.group("lead") == expected_lead
    assert grammar.parse(match.group("lead")) is not None


# --------------------------------------------------------------------------- #
# Verdict table.
# --------------------------------------------------------------------------- #


def test_verdict_table() -> None:
    declared = {"FR-001", "SC-001"}

    malformed = grammar.classify("FR-001.1", declared)
    assert isinstance(malformed, grammar.Rejected)
    assert malformed.reason == grammar.MALFORMED

    foreign = grammar.classify("other-mission#FR-001", declared)
    assert isinstance(foreign, grammar.Rejected)
    assert foreign.reason == grammar.FOREIGN_QUALIFIED

    unknown = grammar.classify("FR-999", declared)
    assert isinstance(unknown, grammar.Rejected)
    assert unknown.reason == grammar.UNKNOWN_SPEC_ID

    accepted_fr = grammar.classify("FR-001", declared)
    assert isinstance(accepted_fr, grammar.Accepted)
    assert accepted_fr.requirement_id.canonical == "FR-001"

    accepted_sc = grammar.classify("sc-001", declared)
    assert isinstance(accepted_sc, grammar.Accepted)
    assert accepted_sc.requirement_id.canonical == "SC-001"

    assert {grammar.MALFORMED, grammar.UNKNOWN_SPEC_ID} == grammar.FAILING_REASONS
    assert grammar.FOREIGN_QUALIFIED not in grammar.FAILING_REASONS


def test_reason_constants_equal_contract_strings() -> None:
    assert grammar.MALFORMED == "malformed"
    assert grammar.UNKNOWN_SPEC_ID == "unknown_spec_id"
    assert grammar.FOREIGN_QUALIFIED == "foreign_qualified"


def test_rule_text_is_not_itself_flagged_as_a_pattern_literal() -> None:
    """RULE_TEXT has no "-\\d" shape, so it must not read as an ID pattern
    literal to the C-001 gate (T006)."""
    assert grammar.RULE_TEXT == "<kind>-<digits>[<lowercase letter>]"
    assert "-\\d" not in grammar.RULE_TEXT


# --------------------------------------------------------------------------- #
# tokenize_refs.
# --------------------------------------------------------------------------- #


def test_tokenize_refs_list_scalar_comma_scalar_whitespace_none_non_str() -> None:
    assert grammar.tokenize_refs(["FR-001", "NFR-002"]) == ["FR-001", "NFR-002"]
    assert grammar.tokenize_refs("FR-001, FR-002") == ["FR-001", "FR-002"]
    assert grammar.tokenize_refs("FR-001 FR-002") == ["FR-001", "FR-002"]
    assert grammar.tokenize_refs(None) == []
    assert grammar.tokenize_refs(["FR-001", 42]) == ["FR-001", "<NON_STRING:42>"]


# --------------------------------------------------------------------------- #
# blank_html_comments.
# --------------------------------------------------------------------------- #


def test_blank_html_comments_preserves_length_and_line_positions() -> None:
    text = "before <!-- hidden\nspan --> after\nnext line"
    blanked = grammar.blank_html_comments(text)
    assert len(blanked) == len(text)
    assert blanked.count("\n") == text.count("\n")
    assert "hidden" not in blanked
    assert "before" in blanked
    assert "after" in blanked
    # The token after the comment keeps its column.
    after_index = text.index("after")
    assert blanked[after_index : after_index + 5] == "after"


def test_blank_html_comments_unterminated_runs_to_end() -> None:
    text = "keep this <!-- gone from here to the end"
    blanked = grammar.blank_html_comments(text)
    assert "gone" not in blanked
    assert "keep this" in blanked
    assert len(blanked) == len(text)


def test_blank_html_comments_no_comment_is_unchanged() -> None:
    text = "no comments here at all"
    assert grammar.blank_html_comments(text) == text
