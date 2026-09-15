"""Tests for interview_mapping.py (T009, T014).

Covers:
- Every INTERVIEW_MAPPINGS entry has the expected section_label and kinds.
- resolve_sections() emits the right (section, context) pairs for a full snapshot.
- R-9 invariant: resolve_sections() refuses _use_built_in_only_drg=False.
- Expanded sections: selected_directives and language_scope produce per-item results.
- requires_nonempty gating: blank answers are skipped.
- Missing answer keys: absence is treated as blank.
"""

from __future__ import annotations

import pytest

from charter.activation.interview import QUESTION_ORDER
from charter.activation.synthesizer.interview_mapping import (
    INTERVIEW_MAPPINGS,
    InterviewSectionMapping,
    _EXPANDED_SECTIONS,
    _INTERVIEW_SECTION_ALIASES,
    _SYNTHETIC_SECTIONS,
    normalize_interview_snapshot,
    resolve_sections,
)


# ---------------------------------------------------------------------------
# T009a: INTERVIEW_MAPPINGS structure validation
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.unit]

class TestInterviewMappingsTable:
    """Validate the static mapping table is well-formed."""

    def test_all_entries_are_interview_section_mapping(self) -> None:
        """Every entry in INTERVIEW_MAPPINGS is an InterviewSectionMapping."""
        for entry in INTERVIEW_MAPPINGS:
            assert isinstance(entry, InterviewSectionMapping), (
                f"Expected InterviewSectionMapping, got {type(entry)}"
            )

    def test_all_kinds_are_valid(self) -> None:
        """Every kind in every entry is a valid artifact kind."""
        valid_kinds = {"directive", "tactic", "styleguide"}
        for entry in INTERVIEW_MAPPINGS:
            for kind in entry.kinds:
                assert kind in valid_kinds, (
                    f"Section '{entry.section_label}' has unknown kind '{kind}'"
                )

    def test_section_labels_are_nonempty_strings(self) -> None:
        """Every section_label is a non-empty string."""
        for entry in INTERVIEW_MAPPINGS:
            assert isinstance(entry.section_label, str)
            assert entry.section_label.strip(), (
                f"Empty section_label in entry {entry}"
            )

    def test_kinds_tuples_are_nonempty(self) -> None:
        """Every kinds tuple has at least one kind."""
        for entry in INTERVIEW_MAPPINGS:
            assert len(entry.kinds) >= 1, (
                f"Section '{entry.section_label}' has empty kinds tuple"
            )

    def test_section_labels_are_unique(self) -> None:
        """No duplicate section_label in INTERVIEW_MAPPINGS."""
        labels = [m.section_label for m in INTERVIEW_MAPPINGS]
        assert len(labels) == len(set(labels)), "Duplicate section_label found"

    def test_expected_sections_present(self) -> None:
        """Canonical interview sections are present in the mapping table."""
        present = {m.section_label for m in INTERVIEW_MAPPINGS}
        expected = {
            "mission_type",
            "testing_philosophy",
            "neutrality_posture",
            "risk_appetite",
            "quality_gates",
            "review_policy",
            "documentation_policy",
        }
        for section in expected:
            assert section in present, (
                f"Expected section '{section}' not in INTERVIEW_MAPPINGS"
            )

    def test_mapping_rows_have_producer_alias_or_synthetic_reason(self) -> None:
        """Every mapping has a real producer, alias, or documented exception."""
        producer_keys = set(QUESTION_ORDER)
        alias_targets = set(_INTERVIEW_SECTION_ALIASES)
        synthetic_targets = set(_SYNTHETIC_SECTIONS)

        for mapping in INTERVIEW_MAPPINGS:
            assert (
                mapping.section_label in producer_keys
                or mapping.section_label in alias_targets
                or mapping.section_label in synthetic_targets
            ), (
                f"{mapping.section_label} has no interview producer contract"
            )

    def test_expanded_sections_not_in_mappings_table(self) -> None:
        """Expanded sections (per-item) must NOT appear in INTERVIEW_MAPPINGS."""
        table_labels = {m.section_label for m in INTERVIEW_MAPPINGS}
        for expanded in _EXPANDED_SECTIONS:
            assert expanded not in table_labels, (
                f"Expanded section '{expanded}' must not be in INTERVIEW_MAPPINGS "
                f"(it is handled via per-item expansion in resolve_sections())"
            )


# ---------------------------------------------------------------------------
# T009b: R-9 invariant — shipped-only DRG during interview
# ---------------------------------------------------------------------------


class TestR9ShippedOnlyDrgInvariant:
    """Lock the R-9 invariant: resolve_sections must use shipped-only DRG."""

    def test_r9_default_is_shipped_only(self) -> None:
        """Default call to resolve_sections uses shipped-only DRG (no exception)."""
        snapshot = {"testing_philosophy": "tdd"}
        # Must not raise
        result = resolve_sections(snapshot)
        assert isinstance(result, list)

    def test_r9_shipped_only_drg_false_raises(self) -> None:
        """Passing _use_built_in_only_drg=False raises ValueError (R-9 guard)."""
        snapshot = {"testing_philosophy": "tdd"}
        with pytest.raises(ValueError, match="R-9"):
            resolve_sections(snapshot, _use_built_in_only_drg=False)

    def test_r9_error_message_mentions_invariant(self) -> None:
        """Error message contains the invariant name."""
        with pytest.raises(ValueError) as exc_info:
            resolve_sections({}, _use_built_in_only_drg=False)
        assert "R-9" in str(exc_info.value)


# ---------------------------------------------------------------------------
# T009c: resolve_sections() — standard table-driven sections
# ---------------------------------------------------------------------------


class TestResolveSectionsTableDriven:
    """Table-driven tests: one per INTERVIEW_MAPPINGS entry."""

    def _snapshot_with(self, section_label: str, value: str = "some answer") -> dict:
        return {section_label: value}

    @pytest.mark.parametrize("mapping", INTERVIEW_MAPPINGS)
    def test_nonempty_answer_emits_section(self, mapping: InterviewSectionMapping) -> None:
        """A non-empty answer for a requires_nonempty section emits the section."""
        snapshot = {mapping.section_label: "non-empty answer"}
        results = resolve_sections(snapshot)
        labels = [label for label, _ in results]
        assert mapping.section_label in labels, (
            f"Section '{mapping.section_label}' not emitted for non-empty answer"
        )

    @pytest.mark.parametrize(
        "mapping",
        [m for m in INTERVIEW_MAPPINGS if m.requires_nonempty],
    )
    def test_empty_answer_suppresses_requires_nonempty_section(
        self, mapping: InterviewSectionMapping
    ) -> None:
        """A blank answer for a requires_nonempty section is NOT emitted."""
        snapshot = {mapping.section_label: "   "}  # whitespace only
        results = resolve_sections(snapshot)
        labels = [label for label, _ in results]
        assert mapping.section_label not in labels, (
            f"Section '{mapping.section_label}' was emitted despite blank answer"
        )

    @pytest.mark.parametrize(
        "mapping",
        [m for m in INTERVIEW_MAPPINGS if m.requires_nonempty],
    )
    def test_absent_answer_suppresses_requires_nonempty_section(
        self, mapping: InterviewSectionMapping
    ) -> None:
        """An absent key for a requires_nonempty section is NOT emitted."""
        snapshot: dict = {}  # no answers at all
        results = resolve_sections(snapshot)
        labels = [label for label, _ in results]
        assert mapping.section_label not in labels

    @pytest.mark.parametrize(
        "mapping",
        [m for m in INTERVIEW_MAPPINGS if not m.requires_nonempty],
    )
    def test_absent_answer_emits_optional_section(
        self, mapping: InterviewSectionMapping
    ) -> None:
        """An absent answer for a requires_nonempty=False section IS emitted."""
        snapshot: dict = {}
        results = resolve_sections(snapshot)
        labels = [label for label, _ in results]
        assert mapping.section_label in labels, (
            f"Optional section '{mapping.section_label}' was NOT emitted for absent answer"
        )

    @pytest.mark.parametrize("mapping", INTERVIEW_MAPPINGS)
    def test_answer_context_contains_source_section(
        self, mapping: InterviewSectionMapping
    ) -> None:
        """answer_context carries source_section equal to the section_label."""
        snapshot = {mapping.section_label: "answer"}
        results = resolve_sections(snapshot)
        for label, ctx in results:
            if label == mapping.section_label:
                assert ctx.get("source_section") == mapping.section_label


# ---------------------------------------------------------------------------
# T009d: Expanded sections — selected_directives
# ---------------------------------------------------------------------------


class TestResolveSectionsSelectedDirectives:
    def test_each_directive_produces_one_result(self) -> None:
        """Two selected directives → two (selected_directives, ctx) pairs."""
        snapshot = {
            "selected_directives": ["DIRECTIVE_003", "DIRECTIVE_010"],
        }
        results = resolve_sections(snapshot)
        directive_results = [
            (label, ctx) for label, ctx in results if label == "selected_directives"
        ]
        assert len(directive_results) == 2

    def test_directive_id_in_context(self) -> None:
        """Each directive's context carries the directive_id."""
        snapshot = {"selected_directives": ["DIRECTIVE_003"]}
        results = resolve_sections(snapshot)
        for label, ctx in results:
            if label == "selected_directives":
                assert ctx["directive_id"] == "DIRECTIVE_003"

    def test_directive_context_includes_source_urns(self) -> None:
        """Directive context includes source_urns with the directive URN."""
        snapshot = {"selected_directives": ["DIRECTIVE_003"]}
        results = resolve_sections(snapshot)
        for label, ctx in results:
            if label == "selected_directives":
                assert "directive:DIRECTIVE_003" in ctx.get("source_urns", ())

    def test_empty_directives_list_produces_no_results(self) -> None:
        """Empty selected_directives list produces zero results for that section."""
        snapshot = {"selected_directives": []}
        results = resolve_sections(snapshot)
        directive_results = [
            label for label, _ in results if label == "selected_directives"
        ]
        assert len(directive_results) == 0

    def test_blank_directive_items_are_skipped(self) -> None:
        """Blank items in selected_directives are ignored."""
        snapshot = {"selected_directives": ["", "  ", "DIRECTIVE_003"]}
        results = resolve_sections(snapshot)
        directive_results = [
            (label, ctx) for label, ctx in results if label == "selected_directives"
        ]
        assert len(directive_results) == 1
        assert directive_results[0][1]["directive_id"] == "DIRECTIVE_003"


# ---------------------------------------------------------------------------
# T009e: Expanded sections — language_scope
# ---------------------------------------------------------------------------


class TestResolveSectionsLanguageScope:
    def test_each_language_produces_one_result(self) -> None:
        """Two languages → two (language_scope, ctx) pairs."""
        snapshot = {"language_scope": ["python", "typescript"]}
        results = resolve_sections(snapshot)
        lang_results = [
            (label, ctx) for label, ctx in results if label == "language_scope"
        ]
        assert len(lang_results) == 2

    def test_language_in_context(self) -> None:
        """Language context carries the language key."""
        snapshot = {"language_scope": ["python"]}
        results = resolve_sections(snapshot)
        for label, ctx in results:
            if label == "language_scope":
                assert ctx["language"] == "python"

    def test_language_is_lowercased(self) -> None:
        """Language strings are normalised to lower-case."""
        snapshot = {"language_scope": ["Python", "TypeScript"]}
        results = resolve_sections(snapshot)
        langs = [
            ctx["language"]
            for label, ctx in results
            if label == "language_scope"
        ]
        assert "python" in langs
        assert "typescript" in langs

    def test_string_language_scope(self) -> None:
        """A scalar string for language_scope is treated as a single language."""
        snapshot = {"language_scope": "python"}
        results = resolve_sections(snapshot)
        lang_results = [
            (label, ctx) for label, ctx in results if label == "language_scope"
        ]
        assert len(lang_results) == 1
        assert lang_results[0][1]["language"] == "python"

    def test_empty_language_scope_produces_no_results(self) -> None:
        """Empty language_scope list produces no language-scope results."""
        snapshot = {"language_scope": []}
        results = resolve_sections(snapshot)
        lang_results = [label for label, _ in results if label == "language_scope"]
        assert len(lang_results) == 0

    def test_language_frameworks_emits_language_styleguide_targets(self) -> None:
        """Real producer key languages_frameworks feeds language_scope expansion."""
        snapshot = {"languages_frameworks": "Python 3.11, TypeScript, pytest"}
        results = resolve_sections(snapshot)
        langs = [
            ctx["language"]
            for label, ctx in results
            if label == "language_scope"
        ]

        assert langs == ["python", "typescript"]

    def test_language_scope_takes_precedence_over_alias(self) -> None:
        """Explicit legacy language_scope remains stable if both keys are present."""
        snapshot = {
            "language_scope": ["rust"],
            "languages_frameworks": "Python 3.11",
        }
        results = resolve_sections(snapshot)
        langs = [
            ctx["language"]
            for label, ctx in results
            if label == "language_scope"
        ]

        assert langs == ["rust"]


# ---------------------------------------------------------------------------
# T009f: Full snapshot round-trip
# ---------------------------------------------------------------------------


class TestResolveFullSnapshot:
    """End-to-end check on a realistic interview snapshot."""

    def test_full_snapshot_produces_expected_sections(self) -> None:
        """A full snapshot produces results for all populated sections."""
        snapshot = {
            "mission_type": "software-dev",
            "testing_philosophy": "tdd",
            "neutrality_posture": "balanced",
            "risk_appetite": "moderate",
            "quality_gates": "coverage >= 90%",
            "review_policy": "two reviewers required",
            "documentation_policy": "all public APIs must be documented",
            "selected_directives": ["DIRECTIVE_003"],
            "language_scope": ["python"],
        }
        results = resolve_sections(snapshot)
        labels = [label for label, _ in results]

        # Standard sections
        for section in ["mission_type", "testing_philosophy", "neutrality_posture",
                        "risk_appetite", "quality_gates", "review_policy",
                        "documentation_policy"]:
            assert section in labels, f"Section '{section}' not emitted"

        # Expanded sections
        assert "selected_directives" in labels
        assert "language_scope" in labels

    def test_real_interview_answer_keys_emit_intended_sections(self) -> None:
        """Production-shaped CharterInterview.answers keys are accepted."""
        snapshot = {
            "project_intent": "Ship trustworthy agent workflows",
            "languages_frameworks": "Python 3.11 and TypeScript",
            "testing_requirements": "pytest coverage and browser tests",
            "quality_gates": "coverage >= 90%",
            "review_policy": "two reviewers required",
            "documentation_policy": "public APIs documented",
            "risk_boundaries": "no credential leaks",
        }

        results = resolve_sections(snapshot)
        labels = [label for label, _ in results]
        contexts = dict(results)

        assert contexts["mission_type"]["answer"] == "Ship trustworthy agent workflows"
        assert contexts["mission_type"]["answer_source"] == "project_intent"
        assert "testing_philosophy" in labels
        assert "risk_appetite" in labels
        assert "quality_gates" in labels
        assert "review_policy" in labels
        assert "documentation_policy" in labels
        assert labels.count("language_scope") == 2

    def test_return_type_is_list_of_tuples(self) -> None:
        """resolve_sections() always returns a list of 2-tuples."""
        result = resolve_sections({"testing_philosophy": "tdd"})
        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, tuple)
            assert len(item) == 2

    def test_context_is_dict(self) -> None:
        """Every answer_context is a dict."""
        result = resolve_sections({"testing_philosophy": "tdd"})
        for _, ctx in result:
            assert isinstance(ctx, dict)


class TestNormalizeInterviewSnapshot:
    def test_producer_keys_are_canonicalized_for_synthesis_requests(self) -> None:
        """Pipeline-facing snapshots use legacy synthesis labels, not aliases."""
        snapshot = {
            "project_intent": "Ship trustworthy agent workflows",
            "languages_frameworks": "Python 3.11 and TypeScript",
            "testing_requirements": "pytest coverage and browser tests",
            "risk_boundaries": "no credential leaks",
            "quality_gates": "coverage >= 90%",
        }

        normalized = normalize_interview_snapshot(snapshot)

        assert normalized["mission_type"] == "Ship trustworthy agent workflows"
        assert normalized["testing_philosophy"] == "pytest coverage and browser tests"
        assert normalized["risk_appetite"] == "no credential leaks"
        assert normalized["language_scope"] == ["python", "typescript"]
        assert "project_intent" not in normalized
        assert "testing_requirements" not in normalized
        assert "risk_boundaries" not in normalized
        assert "languages_frameworks" not in normalized

    def test_project_intent_wins_over_legacy_mission_identifier_collision(self) -> None:
        """Production snapshots must not treat workflow mission ids as intent text."""
        snapshot = {
            "mission_type": "software-dev",
            "project_intent": "Build a patient safety workflow assistant",
            "testing_requirements": "pytest coverage and browser tests",
            "risk_boundaries": "no credential leaks",
        }

        normalized = normalize_interview_snapshot(snapshot)
        contexts = dict(resolve_sections(normalized))

        assert normalized["mission_type"] == "Build a patient safety workflow assistant"
        assert "project_intent" not in normalized
        assert contexts["mission_type"]["answer"] == (
            "Build a patient safety workflow assistant"
        )
        assert contexts["mission_type"]["answer_source"] == "mission_type"
