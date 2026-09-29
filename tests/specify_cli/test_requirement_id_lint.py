"""Unit tests for the setup-plan requirement-ID lint (WP05, T024, FR-013/FR-014).

Every refusal is paired with a same-fixture positive control
(acceptance-criteria-non-vacuity): a rejection is only meaningful proven next
to a case the same code path accepts.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.requirement_mapping import find_undeclared_requirement_citations, grammar, parse_requirement_ids_from_spec_md
from specify_cli.requirement_mapping.lint import (
    RULE_LOWERCASE_SUFFIX,
    InvalidRequirementId,
    RequirementIdWarning,
    _is_well_formed_declaration,
    lint_spec_requirement_ids,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_LIVE_TEMPLATE_PATH = Path(__file__).resolve().parents[2] / "packs/built-in/missions/software-dev/templates/spec-template.md"


# --------------------------------------------------------------------------- #
# Live template (WP07 guard).
# --------------------------------------------------------------------------- #


def test_live_template_passes_lint() -> None:
    text = _LIVE_TEMPLATE_PATH.read_text(encoding="utf-8")
    result = lint_spec_requirement_ids(text)
    assert result.errors == ()
    assert result.warnings == ()


def test_live_template_unwrapped_comment_control_fails() -> None:
    """Positive control: removing the ``<!--``/``-->`` markers that wrap
    ``FR-EXAMPLE`` proves comment-skipping is what saves the live template
    above (the template holds several unrelated comment blocks earlier in
    the file, so only the markers immediately around ``FR-EXAMPLE`` are
    removed -- not the first ``<!--``/``-->`` pair in the whole document)."""
    text = _LIVE_TEMPLATE_PATH.read_text(encoding="utf-8")
    example_idx = text.index("FR-EXAMPLE")
    open_idx = text.rindex("<!--", 0, example_idx)
    close_idx = text.index("-->", example_idx)
    unwrapped = text[:open_idx] + text[open_idx + len("<!--") : close_idx] + text[close_idx + len("-->") :]
    result = lint_spec_requirement_ids(unwrapped)
    assert any(error.token == "FR-EXAMPLE" for error in result.errors)


# --------------------------------------------------------------------------- #
# InvalidRequirementId / RequirementIdWarning -- contract dict shape.
# --------------------------------------------------------------------------- #


def test_invalid_requirement_id_as_dict_matches_contract_keys() -> None:
    error = InvalidRequirementId(token="C-007-mission", line=5, rule=grammar.RULE_TEXT)
    assert error.as_dict() == {"token": "C-007-mission", "line": 5, "rule": grammar.RULE_TEXT}


def test_requirement_id_warning_as_dict_matches_contract_keys() -> None:
    warning = RequirementIdWarning(token="FR-099", line=3, message="msg")
    assert warning.as_dict() == {"token": "FR-099", "line": 3, "message": "msg"}


# --------------------------------------------------------------------------- #
# Errors: one malformed declared lead per case, paired with a same-fixture
# positive control on the next line.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("malformed_row", "control_row", "expected_token", "expected_rule"),
    [
        ("| C-007-mission | x | y | z |", "| C-007 | x | y | z |", "C-007-mission", grammar.RULE_TEXT),
        ("| FR-001.1 | x | y | z |", "| FR-001 | x | y | z |", "FR-001.1", grammar.RULE_TEXT),
        ("| C-S1 | x | y | z |", "| C-001 | x | y | z |", "C-S1", grammar.RULE_TEXT),
        ("| FR_001 | x | y | z |", "| FR-001 | x | y | z |", "FR_001", grammar.RULE_TEXT),
        ("| FR-006A | x | y | z |", "| FR-006a | x | y | z |", "FR-006A", RULE_LOWERCASE_SUFFIX),
    ],
)
def test_declared_lead_errors_with_same_fixture_positive_control(
    malformed_row: str,
    control_row: str,
    expected_token: str,
    expected_rule: str,
) -> None:
    text = f"# Spec\n\n{malformed_row}\n{control_row}\n"
    result = lint_spec_requirement_ids(text)
    assert len(result.errors) == 1, result.errors
    error = result.errors[0]
    assert error.token == expected_token
    assert error.line == 3
    assert error.rule == expected_rule


@pytest.mark.parametrize(
    ("malformed_line", "control_line"),
    [
        ("| C-007-mission | x | y | z |", "| C-007 | x | y | z |"),
        ("### C-007-mission", "### C-007"),
        ("- C-007-mission: description", "- C-007: description"),
        ("**C-007-mission** trailing prose", "**C-007** trailing prose"),
    ],
    ids=["table", "heading", "bullet", "bold"],
)
def test_all_four_declared_positions_refuse_and_accept_the_same_fixture(malformed_line: str, control_line: str) -> None:
    text = f"# Spec\n\n{malformed_line}\n{control_line}\n"
    result = lint_spec_requirement_ids(text)
    assert len(result.errors) == 1, result.errors
    assert result.errors[0].token == "C-007-mission"
    assert result.errors[0].line == 3


# --------------------------------------------------------------------------- #
# No false positives from normalisation.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "line",
    [
        "### FR-001: Title",
        "- FR-001. Do X",
        "**FR-001 — Title.** body",
        "| **FR-001** |",
        "| ~~FR-006~~ |",
        "- **SC-001**: description",
        "| fr-001 |",
    ],
)
def test_normalisation_produces_no_false_positives(line: str) -> None:
    text = f"# Spec\n\n{line}\n"
    result = lint_spec_requirement_ids(text)
    assert result.errors == (), result.errors


# --------------------------------------------------------------------------- #
# Uppercase-kind-only detection (B5) -- case-sensitive, section-independent.
# --------------------------------------------------------------------------- #


def test_malformed_lead_is_case_sensitive_and_runs_outside_requirements_sections() -> None:
    text = "# Spec\n\n## Overview\n\n- C-style strings\n| C-suite |\n- c-001 lowercase\n| C-S1 |\n"
    result = lint_spec_requirement_ids(text)
    assert len(result.errors) == 1
    assert result.errors[0].token == "C-S1"


# --------------------------------------------------------------------------- #
# Lead-capture charset (B6) -- stops at the first out-of-charset character.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "line",
    [
        "- **FR-009's** trailing apostrophe",
        "| FR-001/FR-002 | cited pair |",
        "| FR-002–FR-006 | en-dash range |",
        "- **SC-001…004** ellipsis range",
    ],
)
def test_lead_capture_charset_stops_at_first_other_char_so_no_error(line: str) -> None:
    text = f"# Spec\n\n{line}\n"
    result = lint_spec_requirement_ids(text)
    assert result.errors == (), result.errors


# --------------------------------------------------------------------------- #
# Placeholder (FR-00N): malformed when declared, silently ignored in prose.
# --------------------------------------------------------------------------- #


def test_placeholder_fr_00n_is_malformed_in_a_declared_position() -> None:
    text = "# Spec\n\n| FR-00N |\n"
    result = lint_spec_requirement_ids(text)
    assert len(result.errors) == 1
    assert result.errors[0].rule == RULE_LOWERCASE_SUFFIX


def test_placeholder_fr_00n_in_prose_gives_no_error_and_no_warning() -> None:
    text = "# Spec\n\n## User Scenarios\nsee FR-00N in the future.\n"
    result = lint_spec_requirement_ids(text)
    assert result.errors == ()
    assert result.warnings == ()


# --------------------------------------------------------------------------- #
# HTML comments -- blanked, positions preserved.
# --------------------------------------------------------------------------- #


def test_single_line_html_comment_hides_a_declared_lead_from_errors() -> None:
    text = "# Spec\n\n<!-- | C-007-mission | -->\n"
    result = lint_spec_requirement_ids(text)
    assert result.errors == ()


def test_single_line_html_comment_positive_control_without_markers_errors() -> None:
    text = "# Spec\n\n| C-007-mission |\n"
    result = lint_spec_requirement_ids(text)
    assert len(result.errors) == 1


def test_multiline_html_comment_hides_a_declared_lead_from_errors() -> None:
    text = "# Spec\n\n<!--\n| C-007-mission |\n-->\n"
    result = lint_spec_requirement_ids(text)
    assert result.errors == ()


def test_multiline_html_comment_preserves_true_line_numbers_after_it() -> None:
    text = "# Spec\n\n<!--\nsome\ncomment\nlines\n-->\n| C-007-mission |\n"
    result = lint_spec_requirement_ids(text)
    assert len(result.errors) == 1
    assert result.errors[0].line == 8


# --------------------------------------------------------------------------- #
# Warnings (FR-014 / C-009).
# --------------------------------------------------------------------------- #


def test_prose_warns_once_for_undeclared_token_naming_its_line() -> None:
    text = "# Spec\n\n## User Scenarios\nsee FR-099 here.\n"
    result = lint_spec_requirement_ids(text)
    assert result.errors == ()
    assert len(result.warnings) == 1
    assert result.warnings[0].token == "FR-099"
    assert result.warnings[0].line == 4


def test_qualified_citations_never_warn() -> None:
    text = "# Spec\n\n## User Scenarios\nother-mission#FR-013 and requirement-id-grammar-01M3NRCA#FR-013 are both foreign.\n"
    result = lint_spec_requirement_ids(text)
    assert result.warnings == ()


def test_declared_id_cited_in_prose_never_warns() -> None:
    text = "# Spec\n\n| FR-001 |\n\n## User Scenarios\nFR-001 covers this.\n"
    result = lint_spec_requirement_ids(text)
    assert result.warnings == ()


def test_declaration_line_description_cell_citation_never_warns_but_bare_prose_does() -> None:
    text = "# Spec\n\n| FR-001 | see FR-098 for background | ... |\n\n## User Scenarios\nFR-098 needs a look.\n"
    result = lint_spec_requirement_ids(text)
    assert all(warning.line != 3 for warning in result.warnings)
    assert any(warning.token == "FR-098" for warning in result.warnings)


def test_ic_prefixed_concern_id_never_errors_or_warns() -> None:
    text = "# Spec\n\n| IC-01 |\n\n## User Scenarios\nsee IC-01 for context.\n"
    result = lint_spec_requirement_ids(text)
    assert result.errors == ()
    assert result.warnings == ()


def test_warnings_never_set_blocking() -> None:
    text = "# Spec\n\n## User Scenarios\nsee FR-099 here.\n"
    result = lint_spec_requirement_ids(text)
    assert result.warnings
    assert result.blocking is False


def test_warnings_deduplicate_per_distinct_token() -> None:
    text = "# Spec\n\n## User Scenarios\nFR-099 appears here, and FR-099 appears again.\n"
    result = lint_spec_requirement_ids(text)
    assert len(result.warnings) == 1


# --------------------------------------------------------------------------- #
# Relationship to find_undeclared_requirement_citations (extend, not
# duplicate) -- containment.
# --------------------------------------------------------------------------- #


def test_lint_warnings_contain_every_token_find_undeclared_citations_names() -> None:
    text = "# Spec\n\n## Functional Requirements\nFR-001 must hold. FR-002 too.\n"
    citation_warnings = find_undeclared_requirement_citations(text)
    assert citation_warnings  # sanity: this fixture is the trigger fixture
    result = lint_spec_requirement_ids(text)
    warned_tokens = {warning.token for warning in result.warnings}
    assert {"FR-001", "FR-002"} <= warned_tokens


# --------------------------------------------------------------------------- #
# Agreement with the declared set.
# --------------------------------------------------------------------------- #


def test_commented_declaration_is_undeclared_for_both_lint_and_declared_set() -> None:
    text = "# Spec\n\n<!-- | FR-004 | -->\n\n## User Scenarios\nsee FR-004 too.\n"
    result = lint_spec_requirement_ids(text)
    assert result.errors == ()
    assert any(warning.token == "FR-004" for warning in result.warnings)
    assert "FR-004" not in parse_requirement_ids_from_spec_md(text)["all"]


# --------------------------------------------------------------------------- #
# Helper: _is_well_formed_declaration.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("FR-001", True),
        ("fr-006a", True),
        ("SC-002b", True),
        ("FR-006A", False),
        ("FR-008-mandated", False),
    ],
)
def test_is_well_formed_declaration(token: str, expected: bool) -> None:
    assert _is_well_formed_declaration(token) is expected
