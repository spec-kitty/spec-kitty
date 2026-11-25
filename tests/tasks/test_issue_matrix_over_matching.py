"""Issue-matrix over-matching (#7808, #5297, #5516).

Red-first acceptance tests for three false-positive families that forced
operators to hand-record ``not-applicable`` rows:

* #7808 -- a hex colour (``#000000``, ``#000``, or an all-digit value in CSS
  declaration form such as ``color: #112233;``) was read as an issue number,
  including the impossible issue 0.
* #5297 -- a commit citation ``(`<sha>`, #N)`` was classified as an
  implementation target instead of a PR/commit reference.
* #5516 -- every ``#N`` in research/plan/contracts prose (a planted-break label
  such as "Break #19", a table id) gated approval. Operator ruling "Scope
  decides": only ``spec.md``, ``tasks/`` and closing keywords gate.

Every demotion has a same-fixture positive control, so a do-nothing change
cannot pass these tests and a fail-open change cannot hide behind them.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.tasks.issue_matrix import detect_issue_references, issue_citations_in_line
from specify_cli.tasks.issue_reference_discovery import (
    GatingClass,
    Occurrence,
    classify_occurrence,
    discover_issue_references,
    gating_issue_numbers,
    mission_source_issue_numbers,
)

pytestmark = [pytest.mark.fast]


def issue_numbers_in_text(text: str) -> list[int]:
    """The numbers the canonical detector reads from ``text``, in order."""
    return [number for number, _offset in issue_citations_in_line(text)]


def _mission(tmp_path: Path, files: dict[str, str]) -> Path:
    feature_dir = tmp_path / "kitty-specs" / "demo-01M81KK0"
    feature_dir.mkdir(parents=True)
    for relative, text in files.items():
        path = feature_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return feature_dir


def _classes(feature_dir: Path) -> dict[int, GatingClass]:
    return {ref.number: ref.classification for ref in discover_issue_references(feature_dir)}


# ---------------------------------------------------------------------------
# #7808 -- colours are not issue references
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_research_colours_are_no_reference_7808(tmp_path: Path) -> None:
    """``#000000``, ``#000`` and ``color: #112233;`` in research.md give no reference."""
    feature_dir = _mission(
        tmp_path,
        {
            "research.md": (
                "# Palette\n\n"
                "| Token | Value |\n|---|---|\n| ink | `#000000` |\n| short | #000 |\n\n"
                "```css\n.btn { color: #112233; background-color:#445566 }\n:root { --brand: #778899; }\n```\n"
            )
        },
    )
    assert discover_issue_references(feature_dir) == []


@pytest.mark.regression
def test_spec_colours_are_no_reference_7808(tmp_path: Path) -> None:
    """The filter is not a scope effect: spec.md colours give no reference either."""
    feature_dir = _mission(tmp_path, {"spec.md": "Use `#000000` text with `border-color: #112233;`.\n"})
    assert discover_issue_references(feature_dir) == []


@pytest.mark.parametrize(
    "text",
    ["#00", "#000", "#0000", "#000000", "#0123", "see `#012345`"],
)
def test_leading_zero_is_never_an_issue_number_7808(text: str) -> None:
    assert issue_numbers_in_text(text) == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Positive control: a real reference on a line that mentions a CSS word.
        ("The color picker regression is tracked in #4521.", [4521]),
        ("Set color: red, see #4521 for the background story.", [4521]),
        # A 4-digit value outside declaration form stays a reference (fail-safe).
        ("The overlay uses #1234 as its tint.", [1234]),
        # The declaration filter binds to the value right after the colon only.
        ("color: #112233; and #4521 still counts", [4521]),
        # A non-colour property name is not a declaration form.
        ("Issue: #4521", [4521]),
        ("Parent: #4521", [4521]),
        # A capitalised prose label is not a (lower-case) CSS property name.
        ("Background: #4521", [4521]),
        # Squad fold: the property must be a whole token, not a word ending in a
        # colour word, and a non-CSS custom-looking option is not a property.
        ("Backfill: #4521", [4521]),
        ("- backfill: #4521", [4521]),
        ("tasks-outline: #4521", [4521]),
        ("Watercolor: #4521", [4521]),
        ("UI-color: #4521", [4521]),
        # A real property name in prose with no declaration terminator stays a reference.
        ("- background: #4521 reported in triage", [4521]),
        ("outline: #4521", [4521]),
        ("| border | #4521 |", [4521]),
        # Review cycle 1 (B1): every row of the reviewer's table, each with a
        # terminator added where the original lacked one, so the declaration-start
        # anchor and the colour-length check are what keep them.
        ("Border-color: #4521 tracks this", [4521]),
        ("Recolor: #4521 is broken", [4521]),
        ("Fix text color: #4521", [4521]),
        ("Fix text color: #4521;", [4521]),
        ("See the outline: #4521", [4521]),
        ("See the outline: #4521;", [4521]),
        ("Fix the shadow: #4521 rendering", [4521]),
        ("- shadow: #4521 follow", [4521]),
        ("--note: #4521", [4521]),
        ("Run with --note: #4521;", [4521]),
        ("fill: #12345", [12345]),
        ("fill: #12345;", [12345]),
        ("a { color: red } then color: #4521;", [4521]),
        # Review cycle 2 nit: a quote closes only a declaration it opened.
        ("color: #4521's fix landed", [4521]),
        ('`color: #4521" in the log', [4521]),
    ],
)
def test_real_references_survive_the_colour_filter_7808(text: str, expected: list[int]) -> None:
    assert issue_numbers_in_text(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "color: #112233;",
        "a { border-color: #445566 }",
        "`--brand: #778899`",
        "background: #112233 !important;",
        'style="color: #112233"',
        "box-shadow: #112233;",
        "  color: #1122;",
        "a {color: #112;}",
        "`fill: #11223344`",
        "'color: #112233'",
        "{ color: #112233; }",
    ],
)
def test_declaration_forms_are_filtered_7808(text: str) -> None:
    assert issue_numbers_in_text(text) == []


def test_non_ascii_digits_are_never_issue_numbers_7808() -> None:
    assert issue_numbers_in_text("#\u0661\u0662\u0663 and #1\u0662\u0663") == []


def test_same_repo_url_with_leading_zero_is_not_a_reference_7808() -> None:
    assert issue_numbers_in_text("https://github.com/spec-kitty/spec-kitty/issues/0123") == []
    assert issue_numbers_in_text("https://github.com/spec-kitty/spec-kitty/issues/123") == [123]


# ---------------------------------------------------------------------------
# #5297 -- commit citations are cited, not owed
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_spec_commit_citation_is_non_gating_5297(tmp_path: Path) -> None:
    """``(`ed6d34e75`, #4757)`` in spec.md is a PR/commit reference, not a target."""
    feature_dir = _mission(
        tmp_path,
        {
            "spec.md": (
                "| Test | Why |\n|---|---|\n"
                "| doctor decisions | added on purpose (`ed6d34e75`, #4757) |\n"
                "| decision list | added on purpose (`989667221`, #3951) |\n"
                "| bare target | fix #4521 |\n"
            )
        },
    )
    classes = _classes(feature_dir)
    assert classes[4757] is GatingClass.PR_OR_COMMIT_REF
    # All-digit backticked token: not provably a SHA, so it stays gating (fail-safe).
    assert classes[3951] is GatingClass.IMPLEMENTATION_TARGET
    # Positive control: an unrelated bare reference in the same file still gates.
    assert classes[4521] is GatingClass.IMPLEMENTATION_TARGET
    assert gating_issue_numbers(feature_dir) == {"#3951", "#4521"}


@pytest.mark.parametrize(
    ("line", "offset_of", "expected"),
    [
        ("(`ed6d34e75`, #4757)", "#4757", GatingClass.PR_OR_COMMIT_REF),
        ("#4757 (`ed6d34e75`)", "#4757", GatingClass.PR_OR_COMMIT_REF),
        ("Reverted in `0123456789abcdef0123456789abcdef01234567` for #4757", "#4757", GatingClass.PR_OR_COMMIT_REF),
        # The SHA describes #4757 only; #4521 far away on the same line still gates.
        ("(`ed6d34e75`, #4757) and separately we must implement the fix for #4521", "#4521", GatingClass.IMPLEMENTATION_TARGET),
        # Window boundary: a gap of exactly 16 characters demotes, 17 does not.
        ("(`ed6d34e75`" + " " * 16 + "#4757)", "#4757", GatingClass.PR_OR_COMMIT_REF),
        ("(`ed6d34e75`" + " " * 17 + "#4757)", "#4757", GatingClass.IMPLEMENTATION_TARGET),
        ("#4757" + " " * 16 + "`ed6d34e75`", "#4757", GatingClass.PR_OR_COMMIT_REF),
        ("#4757" + " " * 17 + "`ed6d34e75`", "#4757", GatingClass.IMPLEMENTATION_TARGET),
        # All-letter hex words are English, not SHAs.
        ("Revert `defaced` then do #4757", "#4757", GatingClass.IMPLEMENTATION_TARGET),
        # Too short (6 hex chars) is not a SHA.
        ("(`abcdef`, #4757)", "#4757", GatingClass.IMPLEMENTATION_TARGET),
        # Not backticked: plain hex words are not commit citations.
        ("(ed6d34e75, #4757)", "#4757", GatingClass.IMPLEMENTATION_TARGET),
    ],
)
def test_commit_sha_rule_is_positional_5297(line: str, offset_of: str, expected: GatingClass) -> None:
    occurrence = Occurrence(source_file="spec.md", line_text=line, ref_offset=line.index(offset_of))
    assert classify_occurrence(occurrence) is expected


def test_commit_sha_rule_without_offset_searches_the_line_5297() -> None:
    assert classify_occurrence(Occurrence(source_file="spec.md", line_text="(`ed6d34e75`, #4757)")) is GatingClass.PR_OR_COMMIT_REF


# ---------------------------------------------------------------------------
# #5516 -- scope decides
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_research_planted_break_is_cited_5516(tmp_path: Path) -> None:
    """research.md "Break #19" is cited (non-gating); it is still listed for the audit trail."""
    feature_dir = _mission(tmp_path, {"research.md": "Break #19 plants a stale lane.\n"})
    assert _classes(feature_dir) == {19: GatingClass.CONTEXT_ONLY}
    assert gating_issue_numbers(feature_dir) == set()


@pytest.mark.regression
def test_spec_closes_gates_5516(tmp_path: Path) -> None:
    """spec.md "Closes #19" gates."""
    feature_dir = _mission(tmp_path, {"spec.md": "Closes #19\n"})
    assert gating_issue_numbers(feature_dir) == {"#19"}


@pytest.mark.parametrize("artefact", ["plan.md", "research.md", "analysis-report.md", "contracts/api.md", "contracts/spec.md"])
def test_out_of_scope_artefacts_cite_bare_references_5516(tmp_path: Path, artefact: str) -> None:
    feature_dir = _mission(tmp_path, {artefact: "Background in #4521 and table id #22.\n"})
    assert _classes(feature_dir) == {4521: GatingClass.CONTEXT_ONLY, 22: GatingClass.CONTEXT_ONLY}


@pytest.mark.parametrize("artefact", ["spec.md", "tasks/WP01-demo.md"])
def test_in_scope_artefacts_still_gate_bare_references_5516(tmp_path: Path, artefact: str) -> None:
    """Positive control: the default-gating fail-safe holds inside the gating scope."""
    feature_dir = _mission(tmp_path, {artefact: "Background in #4521.\n"})
    assert _classes(feature_dir) == {4521: GatingClass.IMPLEMENTATION_TARGET}


@pytest.mark.parametrize("keyword", ["Fixes #4521", "Closes: #4521", "resolves #4521", "Fixed #4521"])
def test_closing_keyword_gates_in_any_artefact_5516(tmp_path: Path, keyword: str) -> None:
    feature_dir = _mission(tmp_path, {"plan.md": f"{keyword} as part of this plan.\n"})
    assert gating_issue_numbers(feature_dir) == {"#4521"}


@pytest.mark.parametrize(
    "line",
    [
        "**Closes** #4521",
        "**Fixes:** #4521",
        "Fixes `#4521`",
        "Closes [#4521](https://github.com/spec-kitty/spec-kitty/issues/4521)",
        "Closes https://github.com/spec-kitty/spec-kitty/issues/4521",
        "Closes ([#4521](https://github.com/spec-kitty/spec-kitty/issues/4521))",
    ],
)
def test_closing_keyword_wrapped_forms_gate_out_of_scope_5516(tmp_path: Path, line: str) -> None:
    feature_dir = _mission(tmp_path, {"research.md": f"{line}\n"})
    assert gating_issue_numbers(feature_dir) == {"#4521"}


def test_closing_keyword_names_only_the_citation_it_leads_into_5516(tmp_path: Path) -> None:
    """GitHub semantics: ``Closes #A and #B`` closes only ``#A``; out of scope ``#B`` is cited."""
    feature_dir = _mission(tmp_path, {"plan.md": "Closes #4521 and #4600\n"})
    assert _classes(feature_dir) == {4521: GatingClass.IMPLEMENTATION_TARGET, 4600: GatingClass.CONTEXT_ONLY}


def test_closing_keyword_inside_a_word_is_not_a_label_5516(tmp_path: Path) -> None:
    feature_dir = _mission(tmp_path, {"plan.md": "This encloses #4521 and the prefix #4600.\n"})
    assert gating_issue_numbers(feature_dir) == set()


def test_negated_closing_keyword_out_of_scope_is_cited_5516(tmp_path: Path) -> None:
    feature_dir = _mission(tmp_path, {"plan.md": "This change does not fix #4521.\n"})
    assert gating_issue_numbers(feature_dir) == set()


def test_closing_keyword_wins_over_commit_sha_5516() -> None:
    line = "Fixes #4757 (`ed6d34e75`)"
    occurrence = Occurrence(source_file="research.md", line_text=line, ref_offset=line.index("#4757"), in_gating_scope=False)
    assert classify_occurrence(occurrence) is GatingClass.IMPLEMENTATION_TARGET


def test_closing_keyword_binds_to_its_own_citation_5516() -> None:
    """``Fixes #4521`` does not promote a later, unrelated number on the same line."""
    line = "Fixes #4521; background in #22"
    occurrence = Occurrence(source_file="plan.md", line_text=line, ref_offset=line.index("#22"), in_gating_scope=False)
    assert classify_occurrence(occurrence) is GatingClass.CONTEXT_ONLY


def test_direct_occurrence_construction_defaults_to_gating_scope_5516() -> None:
    """C-002: positional construction keeps its pre-change outcome."""
    occurrence = Occurrence("research.md", "Background in #4521.")
    assert occurrence.in_gating_scope is True
    assert classify_occurrence(occurrence) is GatingClass.IMPLEMENTATION_TARGET


def test_dual_cited_number_gates_when_any_occurrence_is_in_scope_5516(tmp_path: Path) -> None:
    feature_dir = _mission(tmp_path, {"spec.md": "Implement #4521.\n", "research.md": "Background in #4521.\n"})
    assert gating_issue_numbers(feature_dir) == {"#4521"}


def test_source_issue_still_gates_when_cited_only_out_of_scope_5516(tmp_path: Path) -> None:
    """The #7011 promotion still applies: the Mission's own issue gates wherever cited."""
    feature_dir = _mission(
        tmp_path,
        {"meta.json": '{"source_description": "Issue #4521: the bug."}', "research.md": "Background in #4521.\n"},
    )
    assert gating_issue_numbers(feature_dir) == {"#4521"}


def test_detect_single_file_keeps_default_scope_5516(tmp_path: Path) -> None:
    """``detect_issue_references`` on one file (the scaffold path) is unchanged."""
    path = tmp_path / "research.md"
    path.write_text("Background in #4521.\n", encoding="utf-8")
    (ref,) = detect_issue_references(path)
    assert ref.classification is GatingClass.IMPLEMENTATION_TARGET


# ---------------------------------------------------------------------------
# FR-006 -- the source-description and closing-keyword patterns share the filter
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        ("Issue #0123: leading zero", frozenset()),
        ("#000: colour-like", frozenset()),
        ("Issue #4521: real", frozenset({4521})),
        ("GitHub issue 4521 - hashless form", frozenset({4521})),
        ("Ticket 0123 - hashless leading zero", frozenset()),
        # The number must directly follow the lead; a later citation is not the lead.
        ("Issue #abc, see #4521", frozenset()),
    ],
)
def test_source_description_uses_the_shared_filter(tmp_path: Path, description: str, expected: frozenset[int]) -> None:
    import json

    feature_dir = _mission(tmp_path, {"meta.json": json.dumps({"source_description": description})})
    assert mission_source_issue_numbers(feature_dir) == expected


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        ("Closes #0123\n", frozenset()),
        ("Fixes #000\n", frozenset()),
        ("Closes #4521\n", frozenset({4521})),
    ],
)
def test_closing_keyword_source_issues_use_the_shared_filter(tmp_path: Path, spec: str, expected: frozenset[int]) -> None:
    feature_dir = _mission(tmp_path, {"spec.md": spec})
    assert mission_source_issue_numbers(feature_dir) == expected


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        # Only the FIRST ``**Input**`` line names the source issue.
        ("**Input**: Issue #4521\n**Input**: Issue #4600\n", frozenset({4521})),
        # Every citation on the Input line has a label in front of it: none is the source.
        ("**Input**: Epic #4521\n", frozenset()),
        ("**Input**: Epic #4521 -- Issue #4600\n", frozenset({4600})),
    ],
)
def test_input_line_source_issue_paths(tmp_path: Path, spec: str, expected: frozenset[int]) -> None:
    feature_dir = _mission(tmp_path, {"spec.md": spec})
    assert mission_source_issue_numbers(feature_dir) == expected
