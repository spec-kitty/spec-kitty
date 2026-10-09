"""Tests for charter.offering.shared.scoping — language-scoping helpers.

Extends the former top-level test_scoping.py with boundary-pair
coverage needed to kill surviving mutants.

Targets:
- applies_to_languages_match: unscoped artifact (always True), None active_languages
  (always True), empty active scope (False), overlap True/False, set-intersection path
- normalize_languages: None, empty, dedup, lowercase

Patterns: Boundary Pair (empty/None/non-empty), Bi-Directional Logic
(True/False returns).
"""

from __future__ import annotations

import pytest

from charter.offering.shared.scoping import applies_to_languages_match, normalize_languages

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]


# ── normalize_languages ────────────────────────────────────────────────────────


class TestNormalizeLanguages:
    """Boundary pairs on None, empty, whitespace, duplicates."""

    def test_none_returns_empty_tuple(self):
        assert normalize_languages(None) == ()

    def test_empty_iterable_returns_empty_tuple(self):
        assert normalize_languages([]) == ()

    def test_lowercase_conversion(self):
        result = normalize_languages(["Python", "JAVA"])
        assert "python" in result
        assert "java" in result

    def test_strips_whitespace(self):
        result = normalize_languages([" python "])
        assert "python" in result

    def test_deduplicates(self):
        result = normalize_languages(["python", "python", "Python"])
        assert result.count("python") == 1

    def test_blank_strings_excluded(self):
        result = normalize_languages(["python", "", "  "])
        assert "" not in result
        assert "  " not in result

    def test_preserves_order_of_first_occurrence(self):
        result = normalize_languages(["rust", "python"])
        assert result == ("rust", "python")


# ── applies_to_languages_match ────────────────────────────────────────────────


class TestAppliesToLanguagesMatch:
    """Covers all 5 branches: unscoped, no-active-filter, empty-active, overlap, no-overlap."""

    def test_unscoped_artifact_none_returns_true(self):
        assert applies_to_languages_match(None, ["python"]) is True

    def test_active_languages_none_returns_true(self):
        assert applies_to_languages_match(["python"], None) is True

    def test_empty_active_scope_returns_false(self):
        assert applies_to_languages_match(["python"], []) is False

    def test_matching_language_returns_true(self):
        assert applies_to_languages_match(["python"], ["python"]) is True

    def test_non_matching_language_returns_false(self):
        assert applies_to_languages_match(["python"], ["rust"]) is False

    def test_case_insensitive_match(self):
        assert applies_to_languages_match(["Python"], ["python"]) is True
