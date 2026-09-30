"""Tests for term extraction (WP03)."""

import time

import pytest

from tests._perf_helpers import assert_timing_budget
from glossary.extraction import (
    extract_metadata_hints,
    extract_quoted_phrases,
    extract_acronyms,
    extract_casing_patterns,
    extract_repeated_nouns,
    normalize_term,
    is_likely_word,
    extract_all_terms,
)

pytestmark = pytest.mark.fast

class TestMetadataExtraction:
    """Tests for T010: Metadata hints extraction."""

    def test_extract_watch_terms(self):
        """Metadata watch terms extracted correctly."""
        metadata = {"glossary_watch_terms": ["workspace", "mission", "primitive"]}
        terms = extract_metadata_hints(metadata)

        assert len(terms) == 3
        assert all(t.confidence == 1.0 for t in terms)
        assert all(t.source == "metadata_hint" for t in terms)
        surfaces = {t.surface for t in terms}
        assert surfaces == {"workspace", "mission", "primitive"}

    def test_extract_aliases(self):
        """Aliases mapped to canonical terms."""
        metadata = {
            "glossary_aliases": {
                "WP": "work package",
                "spec": "specification",
            }
        }
        terms = extract_metadata_hints(metadata)

        assert len(terms) == 2
        surfaces = {t.surface for t in terms}
        # Normalized (lowercase, trim, singular if applicable)
        assert surfaces == {"work package", "specification"}

    def test_exclude_terms_filtered(self):
        """Exclude terms are filtered out."""
        metadata = {
            "glossary_watch_terms": ["workspace", "mission", "test"],
            "glossary_exclude_terms": ["test"],
        }
        terms = extract_metadata_hints(metadata)

        assert len(terms) == 2
        surfaces = {t.surface for t in terms}
        assert "test" not in surfaces
        assert surfaces == {"workspace", "mission"}

    def test_empty_metadata(self):
        """Empty metadata returns no terms."""
        terms = extract_metadata_hints({})
        assert len(terms) == 0


class TestMetadataValidation:
    """Tests for defensive metadata validation (regression tests for Codex review)."""

    def test_watch_terms_wrong_type_string(self):
        """watch_terms as string (not list) is silently ignored."""
        metadata = {"glossary_watch_terms": "workspace"}
        terms = extract_metadata_hints(metadata)
        assert len(terms) == 0

    def test_watch_terms_wrong_type_dict(self):
        """watch_terms as dict (not list) is silently ignored."""
        metadata = {"glossary_watch_terms": {"workspace": "value"}}
        terms = extract_metadata_hints(metadata)
        assert len(terms) == 0

    def test_watch_terms_list_with_non_strings(self):
        """watch_terms list with non-string items filters invalid entries."""
        metadata = {
            "glossary_watch_terms": [
                "workspace",  # Valid
                42,  # Invalid (int)
                None,  # Invalid (None)
                ["nested"],  # Invalid (list)
                "mission",  # Valid
            ]
        }
        terms = extract_metadata_hints(metadata)
        assert len(terms) == 2
        surfaces = {t.surface for t in terms}
        assert surfaces == {"workspace", "mission"}

    def test_aliases_wrong_type_list(self):
        """aliases as list (not dict) is silently ignored."""
        metadata = {"glossary_aliases": ["workspace", "mission"]}
        terms = extract_metadata_hints(metadata)
        assert len(terms) == 0

    def test_aliases_wrong_type_string(self):
        """aliases as string (not dict) is silently ignored."""
        metadata = {"glossary_aliases": "WP:work package"}
        terms = extract_metadata_hints(metadata)
        assert len(terms) == 0

    def test_aliases_dict_with_non_string_keys(self):
        """aliases dict with non-string keys filters invalid entries."""
        metadata = {
            "glossary_aliases": {
                "WP": "work package",  # Valid
                42: "invalid key",  # Invalid (int key)
                None: "null key",  # Invalid (None key)
                "spec": "specification",  # Valid
            }
        }
        terms = extract_metadata_hints(metadata)
        assert len(terms) == 2
        surfaces = {t.surface for t in terms}
        assert surfaces == {"work package", "specification"}

    def test_aliases_dict_with_non_string_values(self):
        """aliases dict with non-string values filters invalid entries."""
        metadata = {
            "glossary_aliases": {
                "WP": "work package",  # Valid
                "num": 42,  # Invalid (int value)
                "none": None,  # Invalid (None value)
                "spec": "specification",  # Valid
            }
        }
        terms = extract_metadata_hints(metadata)
        assert len(terms) == 2
        surfaces = {t.surface for t in terms}
        assert surfaces == {"work package", "specification"}

    def test_exclude_terms_wrong_type_string(self):
        """exclude_terms as string (not list) is silently ignored."""
        metadata = {
            "glossary_watch_terms": ["workspace", "test"],
            "glossary_exclude_terms": "test",  # Should be list
        }
        terms = extract_metadata_hints(metadata)
        # Exclude is ignored (wrong type), so both terms extracted
        assert len(terms) == 2

    def test_exclude_terms_wrong_type_dict(self):
        """exclude_terms as dict (not list) is silently ignored."""
        metadata = {
            "glossary_watch_terms": ["workspace", "test"],
            "glossary_exclude_terms": {"test": True},
        }
        terms = extract_metadata_hints(metadata)
        # Exclude is ignored (wrong type), so both terms extracted
        assert len(terms) == 2

    def test_exclude_terms_list_with_non_strings(self):
        """exclude_terms list with non-string items filters invalid entries."""
        metadata = {
            "glossary_watch_terms": ["workspace", "mission", "test"],
            "glossary_exclude_terms": [
                "test",  # Valid
                42,  # Invalid (int)
                None,  # Invalid (None)
            ],
        }
        terms = extract_metadata_hints(metadata)
        assert len(terms) == 2
        surfaces = {t.surface for t in terms}
        assert surfaces == {"workspace", "mission"}
        assert "test" not in surfaces

    def test_combined_malformed_metadata(self):
        """Multiple malformed fields handled gracefully."""
        metadata = {
            "glossary_watch_terms": "not_a_list",  # Wrong type
            "glossary_aliases": ["not", "a", "dict"],  # Wrong type
            "glossary_exclude_terms": {"not": "a list"},  # Wrong type
        }
        terms = extract_metadata_hints(metadata)
        # All malformed, should return empty
        assert len(terms) == 0

    def test_mixed_valid_and_invalid_metadata(self):
        """Valid and invalid fields mixed - valid ones processed."""
        metadata = {
            "glossary_watch_terms": ["workspace"],  # Valid
            "glossary_aliases": "invalid",  # Invalid (ignored)
            "glossary_exclude_terms": {"invalid": True},  # Invalid (ignored)
        }
        terms = extract_metadata_hints(metadata)
        assert len(terms) == 1
        assert terms[0].surface == "workspace"


class TestQuotedPhrases:
    """Tests for T011: Quoted phrase extraction."""

    def test_extract_quoted_phrases(self):
        """Quoted phrases extracted correctly."""
        text = 'The "workspace" contains a "mission" primitive.'
        terms = extract_quoted_phrases(text)

        assert len(terms) == 2
        surfaces = {t.surface for t in terms}
        assert surfaces == {"workspace", "mission"}
        assert all(t.source == "quoted_phrase" for t in terms)
        assert all(t.confidence == 0.8 for t in terms)

    def test_filter_common_words(self):
        """Common words are filtered."""
        text = 'The "the" and "a" are common words.'
        terms = extract_quoted_phrases(text)

        assert len(terms) == 0

    def test_filter_single_characters(self):
        """Single characters are filtered."""
        text = 'The "a" and "x" are single characters.'
        terms = extract_quoted_phrases(text)

        assert len(terms) == 0

    def test_multi_word_phrases(self):
        """Multi-word phrases extracted."""
        text = 'The "work package" and "semantic integrity" are terms.'
        terms = extract_quoted_phrases(text)

        assert len(terms) == 2
        surfaces = {t.surface for t in terms}
        assert surfaces == {"work package", "semantic integrity"}


class TestAcronyms:
    """Tests for T011: Acronym extraction."""

    def test_extract_acronyms(self):
        """Acronyms (2-5 uppercase) extracted."""
        text = "WP is a work package. API and CLI are acronyms."
        terms = extract_acronyms(text)

        surfaces = {t.surface for t in terms}
        assert "wp" in surfaces  # Normalized to lowercase
        assert "api" in surfaces
        assert "cli" in surfaces
        assert all(t.source == "acronym" for t in terms)
        assert all(t.confidence == 0.8 for t in terms)

    def test_filter_too_long(self):
        """Acronyms > 5 letters filtered."""
        text = "ABCDEF is too long."
        terms = extract_acronyms(text)

        surfaces = {t.surface for t in terms}
        assert "abcdef" not in surfaces

    def test_filter_single_letter(self):
        """Single letters filtered."""
        text = "A is a single letter."
        terms = extract_acronyms(text)

        surfaces = {t.surface for t in terms}
        assert "a" not in surfaces

    def test_filter_common_words_and(self):
        """Common word 'AND' filtered from acronyms (regression: codex review)."""
        text = "AND THE API are uppercase."
        terms = extract_acronyms(text)

        surfaces = {t.surface for t in terms}
        assert "and" not in surfaces  # Common word filtered
        assert "the" not in surfaces  # Common word filtered
        assert "api" in surfaces  # Real acronym preserved

    def test_filter_common_words_comprehensive(self):
        """All common words filtered from acronyms (regression: codex review)."""
        text = "OR AND THE BUT IF SO GO ME NO."
        terms = extract_acronyms(text)

        # All common words should be filtered
        surfaces = {t.surface for t in terms}
        assert surfaces == set()  # All are common words


class TestCasingPatterns:
    """Tests for T011: Casing pattern extraction."""

    def test_extract_snake_case(self):
        """snake_case terms extracted."""
        text = "The work_package and mission_config are terms."
        terms = extract_casing_patterns(text)

        surfaces = {t.surface for t in terms}
        assert "work_package" in surfaces
        assert "mission_config" in surfaces
        assert all(t.source == "casing_pattern" for t in terms)
        assert all(t.confidence == 0.8 for t in terms)

    def test_extract_camel_case(self):
        """camelCase terms extracted."""
        text = "The workPackage and missionConfig are terms."
        terms = extract_casing_patterns(text)

        surfaces = {t.surface for t in terms}
        assert "workpackage" in surfaces  # Normalized
        assert "missionconfig" in surfaces
        assert all(t.source == "casing_pattern" for t in terms)

    def test_filter_common_words(self):
        """Common words filtered from casing patterns."""
        text = "The new_work is a term."
        terms = extract_casing_patterns(text)

        # "new" and "work" separately are common, but "new_work" is not
        surfaces = {t.surface for t in terms}
        assert "new_work" in surfaces


class TestRepeatedNouns:
    """Tests for T011: Repeated noun extraction."""

    def test_extract_repeated(self):
        """Terms repeated 3+ times extracted."""
        text = """
        The workspace contains files.
        Each workspace has a branch.
        The workspace is clean.
        A workspace can be removed.
        """
        terms = extract_repeated_nouns(text, min_occurrences=3)

        surfaces = {t.surface for t in terms}
        assert "workspace" in surfaces
        assert all(t.source == "repeated_noun" for t in terms)
        assert all(t.confidence == 0.5 for t in terms)

    def test_filter_below_threshold(self):
        """Terms below threshold filtered."""
        text = """
        The workspace contains files.
        Each mission has a goal.
        """
        terms = extract_repeated_nouns(text, min_occurrences=3)

        # Neither appears 3+ times
        assert len(terms) == 0

    def test_filter_common_words(self):
        """Common words filtered."""
        text = """
        The the the the the.
        And and and and and.
        """
        terms = extract_repeated_nouns(text, min_occurrences=3)

        # "the" and "and" are common words
        assert len(terms) == 0


class TestNormalization:
    """Tests for T012: Scope-aware normalization."""

    def test_lowercase_and_trim(self):
        """Lowercase and trim whitespace."""
        assert normalize_term("  Workspace  ") == "workspace"
        assert normalize_term("MISSION") == "mission"

    def test_plural_to_singular(self):
        """Plurals convert to singular."""
        assert normalize_term("workspaces") == "workspace"
        assert normalize_term("missions") == "mission"
        assert normalize_term("primitives") == "primitive"

    def test_plural_edge_cases(self):
        """Plural edge cases handled."""
        # Words ending in 'ces' (would become non-words) stay plural
        assert normalize_term("process") == "process"

        # Short words (<= 3 letters) stay plural
        assert normalize_term("was") == "was"

    def test_no_stemming_double_s_words(self):
        """Words ending in 'ss' are not stemmed (regression test for cycle 4)."""
        # These words end in 's' but are already singular
        # Stemming them creates invalid words
        assert normalize_term("class") == "class"  # not "clas"
        assert normalize_term("glass") == "glass"  # not "glas"
        assert normalize_term("address") == "address"  # not "addres"
        assert normalize_term("process") == "process"  # not "proces"
        assert normalize_term("mass") == "mass"  # not "mas"
        assert normalize_term("pass") == "pass"  # not "pas"

    def test_no_stemming_us_endings(self):
        """Words ending in 'us' are not stemmed (regression test for cycle 4)."""
        # Latin-origin words ending in -us
        assert normalize_term("status") == "status"  # not "statu"
        assert normalize_term("bonus") == "bonus"  # not "bonu"
        assert normalize_term("campus") == "campus"  # not "campu"
        assert normalize_term("focus") == "focus"  # not "focu"

    def test_no_stemming_irregular_endings(self):
        """Words with Greek/Latin endings are not stemmed (regression test for cycle 4)."""
        # -is endings (Greek origin)
        assert normalize_term("analysis") == "analysis"  # not "analysi"
        assert normalize_term("basis") == "basis"  # not "basi"
        assert normalize_term("crisis") == "crisis"  # not "crisi"

        # -as endings (various origins)
        assert normalize_term("atlas") == "atlas"  # not "atla"
        assert normalize_term("canvas") == "canvas"  # not "canva"

        # -os endings (Greek origin)
        assert normalize_term("chaos") == "chaos"  # not "chao"
        assert normalize_term("pathos") == "pathos"  # not "patho"

    def test_idempotent(self):
        """Normalization is idempotent."""
        term = "workspace"
        assert normalize_term(normalize_term(term)) == term

    def test_multi_word(self):
        """Multi-word terms normalized."""
        assert normalize_term("Work Package") == "work package"
        assert normalize_term("  API Gateway  ") == "api gateway"


class TestIsLikelyWord:
    """Tests for is_likely_word helper (stemming safety checks)."""

    def test_valid_words(self):
        """Valid words return True (safe to stem)."""
        assert is_likely_word("workspace") is True  # workspaces -> workspace OK
        assert is_likely_word("mission") is True  # missions -> mission OK
        assert is_likely_word("primitive") is True  # primitives -> primitive OK

    def test_no_vowels(self):
        """Words without vowels return False (unsafe to stem)."""
        assert is_likely_word("bcdfg") is False
        assert is_likely_word("xzq") is False

    def test_prevents_double_s_corruption(self):
        """Prevents stemming words ending in 'ss' (regression test for cycle 4)."""
        # These are text + 's' combinations where original ends in 'ss'
        assert is_likely_word("clas") is False  # class -> clas (BAD)
        assert is_likely_word("glas") is False  # glass -> glas (BAD)
        assert is_likely_word("addres") is False  # address -> addres (BAD)
        assert is_likely_word("proces") is False  # process -> proces (BAD)

    def test_prevents_us_ending_corruption(self):
        """Prevents stemming words ending in 'us' (regression test for cycle 4)."""
        assert is_likely_word("statu") is False  # status -> statu (BAD)
        assert is_likely_word("bonu") is False  # bonus -> bonu (BAD)
        assert is_likely_word("campu") is False  # campus -> campu (BAD)

    def test_prevents_irregular_ending_corruption(self):
        """Prevents stemming Greek/Latin endings (regression test for cycle 4)."""
        # -is endings
        assert is_likely_word("analysi") is False  # analysis -> analysi (BAD)
        assert is_likely_word("basi") is False  # basis -> basi (BAD)

        # -as endings
        assert is_likely_word("atla") is False  # atlas -> atla (BAD)
        assert is_likely_word("canva") is False  # canvas -> canva (BAD)

        # -os endings
        assert is_likely_word("chao") is False  # chaos -> chao (BAD)

    def test_non_alphabetic(self):
        """Non-alphabetic strings return False."""
        assert is_likely_word("work123") is False
        assert is_likely_word("test-case") is False


class TestExtractAllTerms:
    """Integration tests for extract_all_terms."""

    def test_extract_with_metadata(self):
        """Extract with metadata hints prioritized."""
        metadata = {"glossary_watch_terms": ["workspace", "mission"]}
        text = 'The "primitive" is a new term.'

        terms = extract_all_terms(text, metadata)

        # Metadata hints come first (confidence 1.0)
        assert terms[0].surface in ["mission", "workspace"]
        assert terms[0].confidence == 1.0

        # Quoted phrase comes after (confidence 0.8)
        quoted_terms = [t for t in terms if t.source == "quoted_phrase"]
        assert any(t.surface == "primitive" for t in quoted_terms)

    def test_deduplication(self):
        """Terms deduplicated across sources."""
        metadata = {"glossary_watch_terms": ["workspace"]}
        text = 'The "workspace" is a work_space.'

        terms = extract_all_terms(text, metadata)

        # "workspace" appears in metadata and quoted phrase
        # Should only appear once (metadata takes precedence)
        workspace_terms = [t for t in terms if t.surface == "workspace"]
        assert len(workspace_terms) == 1
        assert workspace_terms[0].source == "metadata_hint"

    def test_sorted_by_confidence(self):
        """Terms sorted by confidence descending."""
        metadata = {"glossary_watch_terms": ["mission"]}
        text = """
        The "workspace" is a term.
        The primitive primitive primitive appears often.
        """

        terms = extract_all_terms(text, metadata)

        # Check confidence descending
        confidences = [t.confidence for t in terms]
        assert confidences == sorted(confidences, reverse=True)

    def test_limit_words(self):
        """Large inputs limited for performance."""
        text = " ".join(["word"] * 2000)  # 2000 words
        extract_all_terms(text, limit_words=500)

        # Should only scan first 500 words (no performance issue)
        # This test just ensures it doesn't crash or timeout

    def test_empty_input(self):
        """Empty input returns no terms."""
        terms = extract_all_terms("", None)
        assert len(terms) == 0

    def test_no_terms_found(self):
        """Input with no extractable terms returns empty list."""
        text = "This is a sentence with no special terms."
        terms = extract_all_terms(text, None)

        # May extract repeated words if they appear 3+ times
        # But this simple sentence shouldn't have any
        assert len(terms) == 0


class TestPerformance:
    """Performance tests for extraction (T015)."""

    def test_extraction_functional(self) -> None:
        """Extraction returns terms for typical input (functional, #4015 split)."""
        # 500 words, typical step input size
        text = " ".join(
            [
                "The workspace contains a mission primitive.",
                "Each WP has a work_package configuration.",
                'The "semantic integrity" is validated.',
            ]
            * 50  # ~500 words
        )

        metadata = {
            "glossary_watch_terms": ["workspace", "mission", "primitive"],
            "glossary_aliases": {"WP": "work package"},
        }

        terms = extract_all_terms(text, metadata)

        # Should extract some terms
        assert len(terms) > 0

    @pytest.mark.performance
    def test_extraction_performance(self) -> None:
        """Extraction completes in <100ms for typical input (#4015 split)."""
        # 500 words, typical step input size
        text = " ".join(
            [
                "The workspace contains a mission primitive.",
                "Each WP has a work_package configuration.",
                'The "semantic integrity" is validated.',
            ]
            * 50  # ~500 words
        )

        metadata = {
            "glossary_watch_terms": ["workspace", "mission", "primitive"],
            "glossary_aliases": {"WP": "work package"},
        }

        start = time.perf_counter()
        extract_all_terms(text, metadata)
        elapsed = time.perf_counter() - start

        assert_timing_budget(elapsed, 0.1, name="elapsed")

    @pytest.mark.performance
    def test_large_input_performance(self):
        """Large inputs handled gracefully with limit."""
        # 5000 words, exceeds limit
        text = " ".join(["word"] * 5000)

        start = time.perf_counter()
        extract_all_terms(text, limit_words=1000)
        elapsed = time.perf_counter() - start

        # Should still complete quickly (only processes first 1000)
        assert elapsed < 0.2, f"Large input took {elapsed:.3f}s (expected <0.2s)"


class TestEdgeCases:
    """Edge case tests."""

    def test_special_characters(self):
        """Special characters handled gracefully."""
        text = 'The "wørk$päce" contains special chars.'
        terms = extract_quoted_phrases(text)

        # Should extract but normalize (lowercase)
        # Special chars stay
        surfaces = {t.surface for t in terms}
        assert "wørk$päce" in surfaces

    def test_empty_quoted_phrases(self):
        """Empty quoted phrases filtered."""
        text = 'The "" and "   " are empty.'
        terms = extract_quoted_phrases(text)

        assert len(terms) == 0

    def test_acronyms_in_quotes(self):
        """Acronyms in quotes extracted by both patterns."""
        text = 'The "API" is an acronym.'

        quoted = extract_quoted_phrases(text)
        acronyms = extract_acronyms(text)

        # Both extract "api" (normalized)
        assert any(t.surface == "api" for t in quoted)
        assert any(t.surface == "api" for t in acronyms)

    def test_underscore_normalization(self):
        """Underscores preserved in snake_case terms."""
        text = "The work_package is a term."
        terms = extract_casing_patterns(text)

        # snake_case preserved (part of the term identity)
        surfaces = {t.surface for t in terms}
        assert "work_package" in surfaces
