"""Tests for the requirement-text resolver (WP04, FR-010, FR-011, NFR-003).

``resolve_requirement_texts`` turns the requirement IDs a work package cites
into their declared text from the Mission's ``spec.md``. It reads the
declaring site ``declaration_occurrences`` reports and takes ambiguity only
from ``duplicate_declared_ids`` (#3481: no third declaration parser).
"""

from __future__ import annotations

import dataclasses
import textwrap
from pathlib import Path

import pytest

from specify_cli.requirement_mapping import duplicate_declared_ids, parse_requirement_ids_from_spec_md
from specify_cli.requirement_mapping.text import (
    TEXT_LIMIT,
    TRUNCATION_MARKER,
    CitedRequirement,
    Resolution,
    resolve_requirement_texts,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _spec(body: str) -> str:
    return textwrap.dedent(body).lstrip("\n")


def _one(spec: str, ref: str, *, mission_type: str = "software-dev") -> CitedRequirement:
    results = resolve_requirement_texts(spec, [ref], mission_type=mission_type)
    assert len(results) == 1
    return results[0]


_TABLES = _spec(
    """
    # Spec

    | ID | Title | User Story | Priority |
    |----|-------|------------|----------|
    | FR-001 | Range per WP | As a reviewer, I want a range. | High |
    | FR-003a | Suffixed | A suffixed statement. | Low |
    | FR-003 | Unsuffixed | An unsuffixed statement. | Low |

    | ID | Title | Requirement | Category |
    |----|-------|-------------|----------|
    | NFR-001 | Bounded growth | At most 4 KB. | Performance |

    | ID | Title | Constraint | Type |
    |----|-------|------------|------|
    | C-001 | No diff body | The prompt never inlines patch text. | Business |
    """
)


class TestTableRows:
    @pytest.mark.parametrize(
        ("ref", "expected"),
        [
            ("FR-001", "FR-001 — Range per WP: As a reviewer, I want a range."),
            ("NFR-001", "NFR-001 — Bounded growth: At most 4 KB."),
            ("C-001", "C-001 — No diff body: The prompt never inlines patch text."),
        ],
    )
    def test_table_row_resolves_title_and_statement(self, ref: str, expected: str) -> None:
        result = _one(_TABLES, ref)
        assert result == CitedRequirement(ref=ref, resolution=Resolution.DECLARED, text=expected)

    def test_escaped_pipe_does_not_split_the_cell(self) -> None:
        spec = _spec(
            """
            | ID | Title | Requirement |
            |----|-------|-------------|
            | FR-001 | Pipes | Either a \\| b holds. | High |
            """
        )
        assert _one(spec, "FR-001").text == "FR-001 — Pipes: Either a | b holds."

    def test_single_cell_row_has_no_colon(self) -> None:
        spec = "| FR-001 | Only a title |\n"
        assert _one(spec, "FR-001").text == "FR-001 — Only a title"

    def test_bold_id_cell(self) -> None:
        spec = "| **FR-001** | Bold | Bold statement. |\n"
        assert _one(spec, "FR-001").text == "FR-001 — Bold: Bold statement."


class TestSuffixedIds:
    def test_lower_suffix_resolves(self) -> None:
        assert _one(_TABLES, "FR-003a").text == "FR-003a — Suffixed: A suffixed statement."

    def test_upper_suffix_citation_resolves_to_the_same_row(self) -> None:
        result = _one(_TABLES, "FR-003A")
        assert result.ref == "FR-003a"
        assert result.text == "FR-003a — Suffixed: A suffixed statement."

    def test_suffixed_and_unsuffixed_stay_distinct(self) -> None:
        unsuffixed, suffixed = resolve_requirement_texts(_TABLES, ["FR-003", "FR-003a"])
        assert unsuffixed.text == "FR-003 — Unsuffixed: An unsuffixed statement."
        assert suffixed.text == "FR-003a — Suffixed: A suffixed statement."


class TestSuccessCriteriaBullets:
    def test_build_trailer_is_stripped(self) -> None:
        spec = "- **SC-001**: Something holds. — [build] · no-op passable: no\n"
        assert _one(spec, "SC-001").text == "SC-001 — Something holds."

    def test_ratchet_trailer_is_stripped_entirely(self) -> None:
        spec = "- **SC-004**: Verdicts are unchanged. — [ratchet] · no-op passable: yes — paired with SC-001's fixture\n"
        result = _one(spec, "SC-004")
        assert result.text == "SC-004 — Verdicts are unchanged."

    def test_em_dash_inside_the_statement_is_kept(self) -> None:
        spec = "- **SC-002**: Every ID — declared or not — appears. — [build] · no-op passable: no\n"
        assert _one(spec, "SC-002").text == "SC-002 — Every ID — declared or not — appears."


class TestBlockDeclarations:
    def test_heading_takes_title_and_first_paragraph_only(self) -> None:
        spec = _spec(
            """
            ### FR-007: Title of seven

            First paragraph line one
            continues here.

            Second paragraph is not included.
            """
        )
        assert _one(spec, "FR-007").text == "FR-007 — Title of seven: First paragraph line one continues here."

    def test_heading_without_title(self) -> None:
        spec = "### FR-007\n\nOnly a paragraph.\n"
        assert _one(spec, "FR-007").text == "FR-007 — Only a paragraph."

    def test_heading_with_no_paragraph_is_the_bare_title(self) -> None:
        spec = "### FR-007: Lonely title\n### Next heading\n"
        assert _one(spec, "FR-007").text == "FR-007 — Lonely title"

    def test_empty_declaration_is_the_bare_id(self) -> None:
        spec = "### FR-007\n"
        assert _one(spec, "FR-007").text == "FR-007"

    def test_list_item_keeps_continuation_and_stops_at_next_bullet(self) -> None:
        spec = _spec(
            """
            - FR-001: The statement wraps
              onto a continuation line.
            - FR-002: The next bullet.
            """
        )
        first, second = resolve_requirement_texts(spec, ["FR-001", "FR-002"])
        assert first.text == "FR-001 — The statement wraps onto a continuation line."
        assert second.text == "FR-002 — The next bullet."

    def test_list_item_stops_at_blank_line(self) -> None:
        spec = "- FR-001: One line.\n\nUnrelated paragraph.\n"
        assert _one(spec, "FR-001").text == "FR-001 — One line."

    def test_bold_led_paragraph(self) -> None:
        spec = "**FR-001 — Bold title.** Body of the requirement.\n"
        assert _one(spec, "FR-001").text == "FR-001 — Bold title. Body of the requirement."


class TestResearchKinds:
    _RESEARCH = _spec(
        """
        | ID | Title | Statement |
        |----|-------|-----------|
        | DR-001 | Decision | Decide a thing. |
        | AR-001 | Analysis | Analyse a thing. |
        | QR-001 | Question | Ask a thing. |
        """
    )

    @pytest.mark.parametrize("ref", ["DR-001", "AR-001", "QR-001"])
    def test_research_kinds_resolve_under_research_mission(self, ref: str) -> None:
        result = _one(self._RESEARCH, ref, mission_type="research")
        assert result.resolution is Resolution.DECLARED
        assert result.text is not None
        assert result.text.startswith(f"{ref} — ")

    def test_research_kind_under_default_mission_is_not_declared(self) -> None:
        result = _one(self._RESEARCH, "DR-001")
        assert result == CitedRequirement(ref="DR-001", resolution=Resolution.NOT_DECLARED, text=None)


class TestUnresolvedCitations:
    def test_cross_mission_citation_is_labelled_even_when_declared_here(self) -> None:
        spec = "| FR-002 | Here | Declared here too. |\n"
        result = _one(spec, "other-mission#FR-002")
        assert result == CitedRequirement(ref="other-mission#FR-002", resolution=Resolution.OTHER_MISSION, text=None)

    def test_undeclared_id(self) -> None:
        result = _one(_TABLES, "C-009")
        assert result == CitedRequirement(ref="C-009", resolution=Resolution.NOT_DECLARED, text=None)

    @pytest.mark.parametrize("token", ["FR-", "<NON_STRING:3>"])
    def test_malformed_token_is_kept_as_written(self, token: str) -> None:
        result = _one(_TABLES, token)
        assert result == CitedRequirement(ref=token, resolution=Resolution.NOT_DECLARED, text=None)

    def test_id_declared_only_inside_html_comment_is_not_declared(self) -> None:
        spec = "<!--\n| FR-001 | Hidden | Commented out. |\n-->\n"
        assert _one(spec, "FR-001").resolution is Resolution.NOT_DECLARED


class TestAmbiguity:
    def test_two_rows_of_the_same_table_are_ambiguous(self) -> None:
        spec = "| FR-004 | One | First. |\n| FR-004 | Two | Second. |\n"
        assert duplicate_declared_ids(spec)
        assert _one(spec, "FR-004") == CitedRequirement(ref="FR-004", resolution=Resolution.AMBIGUOUS, text=None)

    def test_two_id_headings_are_ambiguous(self) -> None:
        spec = "### FR-005\n\nFirst.\n\n### FR-005\n\nSecond.\n"
        assert duplicate_declared_ids(spec)
        assert _one(spec, "FR-005").resolution is Resolution.AMBIGUOUS

    @pytest.mark.parametrize(
        "restatement",
        [
            "- **FR-001 has a second leg**\n",
            "| Requirement | Criterion |\n|---|---|\n| FR-001 | SC-001 |\n",
            "### FR-001 Detail: more words\n\nDetail body.\n",
        ],
        ids=["bullet", "traceability-table", "detail-heading"],
    )
    def test_restatement_after_table_row_is_not_ambiguous(self, restatement: str) -> None:
        spec = "| FR-001 | Range | The statement. |\n\n" + restatement
        assert duplicate_declared_ids(spec) == {}
        assert _one(spec, "FR-001") == CitedRequirement(ref="FR-001", resolution=Resolution.DECLARED, text="FR-001 — Range: The statement.")


class TestTruncation:
    def test_over_limit_is_cut_at_limit_with_marker(self) -> None:
        spec = f"- FR-001: {'x' * 700}\n"
        text = _one(spec, "FR-001").text
        assert text is not None
        assert text.endswith(TRUNCATION_MARKER)
        assert len(text) == TEXT_LIMIT + len(TRUNCATION_MARKER)
        assert text[:TEXT_LIMIT] == ("FR-001 — " + "x" * 700)[:TEXT_LIMIT]

    def test_exactly_at_limit_has_no_marker(self) -> None:
        prefix = "FR-001 — "
        spec = f"- FR-001: {'y' * (TEXT_LIMIT - len(prefix))}\n"
        text = _one(spec, "FR-001").text
        assert text is not None
        assert len(text) == TEXT_LIMIT
        assert not text.endswith(TRUNCATION_MARKER)

    def test_limit_is_six_hundred(self) -> None:
        assert TEXT_LIMIT == 600

    def test_twenty_max_length_citations_fit_twelve_kib(self) -> None:
        statement = "Résumé of the requirement " + "z" * 700 + " — naïve tail"
        lines = [f"| FR-{n:03d} | Title {n} | {statement} |" for n in range(1, 21)]
        spec = "\n".join(lines) + "\n"
        refs = [f"FR-{n:03d}" for n in range(1, 21)]
        results = resolve_requirement_texts(spec, refs)
        assert all(r.resolution is Resolution.DECLARED for r in results)
        assert all(r.text is not None and r.text.endswith(TRUNCATION_MARKER) for r in results)
        rendered_lines = [f"  {c.text}" for c in results]
        assert len("\n".join(rendered_lines).encode()) <= 12 * 1024


class TestOrderAndNormalisation:
    def test_output_follows_citation_order(self) -> None:
        results = resolve_requirement_texts(_TABLES, ["NFR-001", "FR-003", "C-001"])
        assert [r.ref for r in results] == ["NFR-001", "FR-003", "C-001"]

    def test_repeated_citation_appears_once_at_first_position(self) -> None:
        results = resolve_requirement_texts(_TABLES, ["FR-001", "C-001", "fr-001", "FR-001"])
        assert [r.ref for r in results] == ["FR-001", "C-001"]

    def test_whitespace_collapses_and_bold_markers_never_appear(self) -> None:
        spec = "- **FR-001**:   Spread    over\n  two   lines.\n"
        text = _one(spec, "FR-001").text
        assert text == "FR-001 — Spread over two lines."
        assert "**" not in text

    def test_empty_refs_yield_empty_tuple(self) -> None:
        assert resolve_requirement_texts(_TABLES, []) == ()


class TestCitedRequirementInvariant:
    def test_text_only_for_declared(self) -> None:
        with pytest.raises(ValueError, match="DECLARED"):
            CitedRequirement(ref="FR-001", resolution=Resolution.NOT_DECLARED, text="FR-001 — x")

    def test_is_frozen(self) -> None:
        cited = CitedRequirement(ref="FR-001", resolution=Resolution.NOT_DECLARED)
        field_name = "ref"
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(cited, field_name, "FR-002")

    def test_resolution_members(self) -> None:
        assert {member.value for member in Resolution} == {"declared", "not_declared", "other_mission", "ambiguous"}


class TestThisMissionsSpec:
    _SPEC_PATH = Path(__file__).resolve().parents[2] / "kitty-specs/review-context-wp-diff-01M774QF/spec.md"

    def test_every_declared_id_resolves_with_text(self) -> None:
        spec = self._SPEC_PATH.read_text(encoding="utf-8")
        declared = parse_requirement_ids_from_spec_md(spec)["all"]
        assert len(declared) >= 34
        results = resolve_requirement_texts(spec, declared)
        assert [r.ref for r in results] == declared
        for result in results:
            assert result.resolution is Resolution.DECLARED, result
            assert result.text, result
            assert result.text.startswith(result.ref)
        by_ref = {r.ref: r.text or "" for r in results}
        assert "Cited requirement text" in by_ref["FR-010"]
        assert "no-op passable" not in by_ref["SC-002"]
