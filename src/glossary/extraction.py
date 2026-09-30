"""Term extraction logic (WP03).

This module implements term extraction using metadata hints and deterministic
heuristics, with scope-aware normalization and confidence scoring.

Performance target: <100ms for typical step input (100-500 words).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# Compiled regex patterns for performance
QUOTED_PHRASE_PATTERN = re.compile(r'"([^"]+)"')
ACRONYM_PATTERN = re.compile(r"\b[A-Z]{2,5}\b")
SNAKE_CASE_PATTERN = re.compile(r"\b[a-z]+_[a-z_]+\b")
CAMEL_CASE_PATTERN = re.compile(r"\b[a-z]+[A-Z][a-zA-Z]+\b")
# Simple word pattern for validation
WORD_PATTERN = re.compile(r"^[a-z]+$")

# Common English words to exclude (top 100 most common)
COMMON_WORDS = {
    "the",
    "be",
    "to",
    "of",
    "and",
    "a",
    "in",
    "that",
    "have",
    "i",
    "it",
    "for",
    "not",
    "on",
    "with",
    "he",
    "as",
    "you",
    "do",
    "at",
    "this",
    "but",
    "his",
    "by",
    "from",
    "they",
    "we",
    "say",
    "her",
    "she",
    "or",
    "an",
    "will",
    "my",
    "one",
    "all",
    "would",
    "there",
    "their",
    "what",
    "so",
    "up",
    "out",
    "if",
    "about",
    "who",
    "get",
    "which",
    "go",
    "me",
    "when",
    "make",
    "can",
    "like",
    "time",
    "no",
    "just",
    "him",
    "know",
    "take",
    "people",
    "into",
    "year",
    "your",
    "good",
    "some",
    "could",
    "them",
    "see",
    "other",
    "than",
    "then",
    "now",
    "look",
    "only",
    "come",
    "its",
    "over",
    "think",
    "also",
    "back",
    "after",
    "use",
    "two",
    "how",
    "our",
    "work",
    "first",
    "well",
    "way",
    "even",
    "new",
    "want",
    "because",
    "any",
    "these",
    "give",
    "day",
    "most",
    "us",
}


@dataclass(frozen=True)
class ExtractedTerm:
    """A term extracted from input text."""

    surface: str  # Normalized surface form
    source: str  # Source of extraction (metadata_hint, quoted_phrase, etc.)
    confidence: float  # Confidence score (0.0-1.0)
    original: str = ""  # Original surface before normalization


def extract_metadata_hints(metadata: dict[str, Any]) -> list[ExtractedTerm]:
    """Extract terms from metadata hints (highest confidence).

    Args:
        metadata: Dictionary containing glossary metadata fields

    Returns:
        List of ExtractedTerm with source="metadata_hint" and confidence=1.0

    Metadata fields:
        - glossary_watch_terms: List[str] - explicit terms to watch
        - glossary_aliases: Dict[str, str] - alias -> canonical mapping
        - glossary_exclude_terms: List[str] - terms to exclude (not returned)

    Note:
        Malformed metadata (wrong types) is silently ignored to ensure graceful
        degradation. Invalid entries are skipped rather than causing crashes.
    """
    terms: set[str] = set()
    exclude_terms: set[str] = set()

    # Explicit exclusions (validate list[str])
    if "glossary_exclude_terms" in metadata:
        exclude_field = metadata["glossary_exclude_terms"]
        if isinstance(exclude_field, list):
            for term in exclude_field:
                if isinstance(term, str):
                    exclude_terms.add(normalize_term(term))

    # Explicit watch terms (validate list[str])
    if "glossary_watch_terms" in metadata:
        watch_field = metadata["glossary_watch_terms"]
        if isinstance(watch_field, list):
            for term in watch_field:
                if isinstance(term, str):
                    normalized = normalize_term(term)
                    if normalized not in exclude_terms:
                        terms.add(normalized)

    # Aliases (validate dict[str, str])
    if "glossary_aliases" in metadata:
        aliases_field = metadata["glossary_aliases"]
        if isinstance(aliases_field, dict):
            for alias, canonical in aliases_field.items():
                if isinstance(alias, str) and isinstance(canonical, str):
                    normalized_canonical = normalize_term(canonical)
                    if normalized_canonical not in exclude_terms:
                        terms.add(normalized_canonical)

    return [
        ExtractedTerm(surface=term, source="metadata_hint", confidence=1.0, original=term) for term in sorted(terms)
    ]


def extract_quoted_phrases(text: str) -> list[ExtractedTerm]:
    """Extract terms from quoted phrases.

    Args:
        text: Input text to scan

    Returns:
        List of ExtractedTerm with source="quoted_phrase" and confidence=0.8
    """
    terms: set[str] = set()

    for match in QUOTED_PHRASE_PATTERN.finditer(text):
        phrase = match.group(1)
        normalized = normalize_term(phrase)
        # Filter common words and single characters
        if normalized and len(normalized) > 1 and normalized not in COMMON_WORDS:
            terms.add(normalized)

    return [
        ExtractedTerm(surface=term, source="quoted_phrase", confidence=0.8, original=term) for term in sorted(terms)
    ]


def extract_acronyms(text: str) -> list[ExtractedTerm]:
    """Extract acronyms (2-5 uppercase letters).

    Args:
        text: Input text to scan

    Returns:
        List of ExtractedTerm with source="acronym" and confidence=0.8
    """
    terms: set[str] = set()

    for match in ACRONYM_PATTERN.finditer(text):
        acronym = match.group(0)
        # Lowercase for normalization (acronyms stored in lowercase internally)
        normalized = acronym.lower()
        # Filter common words (AND, THE, etc.)
        if normalized in COMMON_WORDS:
            continue
        # Don't normalize further (acronyms are already normalized)
        terms.add(normalized)

    return [
        ExtractedTerm(surface=term, source="acronym", confidence=0.8, original=term.upper()) for term in sorted(terms)
    ]


def extract_casing_patterns(text: str) -> list[ExtractedTerm]:
    """Extract snake_case and camelCase terms.

    Args:
        text: Input text to scan

    Returns:
        List of ExtractedTerm with source="casing_pattern" and confidence=0.8
    """
    terms: set[str] = set()

    # Snake case
    for match in SNAKE_CASE_PATTERN.finditer(text):
        term = match.group(0)
        normalized = normalize_term(term)
        if normalized and normalized not in COMMON_WORDS:
            terms.add(normalized)

    # Camel case
    for match in CAMEL_CASE_PATTERN.finditer(text):
        term = match.group(0)
        normalized = normalize_term(term)
        if normalized and normalized not in COMMON_WORDS:
            terms.add(normalized)

    return [
        ExtractedTerm(surface=term, source="casing_pattern", confidence=0.8, original=term) for term in sorted(terms)
    ]


def extract_repeated_nouns(text: str, min_occurrences: int = 3) -> list[ExtractedTerm]:
    """Extract noun phrases that appear multiple times.

    Args:
        text: Input text to scan
        min_occurrences: Minimum number of occurrences (default: 3)

    Returns:
        List of ExtractedTerm with source="repeated_noun" and confidence=0.5

    Note: This is a simple word-counting heuristic. Production might use NLP.
    """
    # Extract words (lowercase)
    words = re.findall(r"\b[a-z]{3,}\b", text.lower())

    # Count occurrences
    word_counts: dict[str, int] = {}
    for word in words:
        if word not in COMMON_WORDS:
            word_counts[word] = word_counts.get(word, 0) + 1

    # Filter by min occurrences
    repeated = {word for word, count in word_counts.items() if count >= min_occurrences}

    return [
        ExtractedTerm(surface=word, source="repeated_noun", confidence=0.5, original=word) for word in sorted(repeated)
    ]


def normalize_term(surface: str) -> str:
    """Normalize term surface: lowercase, trim, stem-light.

    Args:
        surface: Raw term surface

    Returns:
        Normalized surface (lowercase, trimmed, plural -> singular)

    Normalization rules:
        1. Lowercase
        2. Strip whitespace
        3. Simple plural removal (ends with 's', length > 3)
    """
    # Lowercase + trim
    normalized = surface.lower().strip()

    # Stem-light: simple plural removal
    if normalized.endswith("s") and len(normalized) > 3:
        # workspaces -> workspace
        singular = normalized[:-1]
        if is_likely_word(singular):
            return singular

    return normalized


def is_likely_word(text: str) -> bool:
    """Heuristic check if text is a likely English word after stemming.

    Args:
        text: Text after removing trailing 's' (candidate singular form)

    Returns:
        True if text looks like a valid word (i.e., stemming is safe)

    Note: This is a simple heuristic. Production might use a dictionary.

    Common false positives prevented:
        - class -> clas (ends in 'ss', don't stem)
        - glass -> glas (ends in 'ss', don't stem)
        - address -> addres (ends in 'ss', don't stem)
        - status -> statu (ends in 'us', don't stem)
        - process -> proces (ends in 'ss', don't stem)
    """
    # Must match word pattern (letters only) first
    if not WORD_PATTERN.match(text):
        return False

    # Must have at least one vowel
    if not any(c in text for c in "aeiouy"):
        return False

    # The original word (before stemming) is text + 's'
    # Check if original ends with patterns indicating it's already singular
    original = text + "s"

    # Double-s words: class, glass, mass, pass, address, process, etc.
    # These are already singular - don't stem
    if original.endswith("ss"):
        return False

    # -us endings: status, bonus, campus, etc.
    # These are already singular (or irregular Latin) - don't stem
    if original.endswith("us"):
        return False

    # -as endings: atlas, canvas, etc.
    # These are already singular - don't stem
    if original.endswith("as") and len(original) > 3:
        return False

    # -is endings: analysis, basis, crisis, etc.
    # These are already singular (Greek origin) - don't stem
    if original.endswith("is"):
        return False

    # -os endings: chaos, pathos, etc.
    # These are already singular (Greek origin) - don't stem
    return not original.endswith("os")


def extract_all_terms(
    text: str, metadata: dict[str, Any] | None = None, limit_words: int = 1000
) -> list[ExtractedTerm]:
    """Extract all terms from text using metadata hints and heuristics.

    Args:
        text: Input text to scan (limited to first limit_words)
        metadata: Optional metadata dictionary
        limit_words: Maximum words to scan (performance limit)

    Returns:
        List of ExtractedTerm, deduplicated and sorted by confidence (descending)

    Performance: <100ms for typical inputs (100-500 words).
    """
    # Limit input size for performance
    words = text.split()
    if len(words) > limit_words:
        text = " ".join(words[:limit_words])

    terms_by_surface: dict[str, ExtractedTerm] = {}

    # 1. Extract from metadata hints (highest confidence)
    if metadata:
        for term in extract_metadata_hints(metadata):
            terms_by_surface[term.surface] = term

    # 2. Extract from heuristics
    for term in extract_quoted_phrases(text):
        if term.surface not in terms_by_surface:
            terms_by_surface[term.surface] = term

    for term in extract_acronyms(text):
        if term.surface not in terms_by_surface:
            terms_by_surface[term.surface] = term

    for term in extract_casing_patterns(text):
        if term.surface not in terms_by_surface:
            terms_by_surface[term.surface] = term

    for term in extract_repeated_nouns(text):
        if term.surface not in terms_by_surface:
            terms_by_surface[term.surface] = term

    # Sort by confidence (descending), then surface (alphabetical)
    return sorted(terms_by_surface.values(), key=lambda t: (-t.confidence, t.surface))
