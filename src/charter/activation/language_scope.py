"""Helpers for deriving active project languages from charter inputs."""

from __future__ import annotations

import ast
import functools
from collections.abc import Iterable
from pathlib import Path
import re
from typing import TYPE_CHECKING

from charter.activation.charter_yaml_io import read_catalog_field
from charter.activation.interview import packaged_default_answer, read_interview_answers
from charter.activation.language_authority import declared_languages, expand_language_families
from charter.activation.language_vocabulary import scoped_language_vocabulary
from charter.offering.shared.language_catalog import COMPOUND_PREFIX_GUARD
from charter.offering.shared.scoping import (
    RESERVED_LANGUAGE_TOKENS,
    SENTINEL_LANGUAGE_TOKENS,
    UNKNOWN_LANGUAGE,
    is_unknown_language,
    normalize_languages,
)

if TYPE_CHECKING:
    from charter.activation.interview import CharterInterview

__all__ = [
    "RESERVED_LANGUAGE_TOKENS",
    "SENTINEL_LANGUAGE_TOKENS",
    "UNKNOWN_LANGUAGE",
    "extract_declared_languages",
    "infer_repo_languages",
    "is_placeholder_language_answer",
    "is_unknown_language",
    "lacks_specialist_guidance",
]

_LANGUAGES_ANSWER_KEY = "languages_frameworks"

#: Normalised (casefolded, whitespace-collapsed) answers that declare nothing:
#: not a language, and never a signal that the language is *unknown*.
_PLACEHOLDER_ANSWERS: frozenset[str] = frozenset(
    {"", "[]", "-", "n/a", "na", "none", "null", "tbd", "language-agnostic", "language agnostic"}
) | SENTINEL_LANGUAGE_TOKENS | RESERVED_LANGUAGE_TOKENS
_NEEDS_CLARIFICATION_PREFIX = "[needs clarification"



#: Whole words only; ``C#``/``C++``-style tokens are not words and resolve to
#: ``unknown`` (out of scope by design).
_WORD_TOKEN = re.compile(COMPOUND_PREFIX_GUARD + r"\b\w+\b(?![#+])")


def extract_declared_languages(text: str) -> list[str]:
    """Return canonical language identifiers mentioned in free-form text.

    Delegates to :func:`charter.activation.language_authority.declared_languages`
    (the build-token rule included): "Gradle" alone is ``["jvm"]``.
    """
    return declared_languages(text)


def _normalize_answer(value: object) -> str:
    return " ".join(str(value).casefold().split())


@functools.cache
def _shipped_default_answer() -> str:
    return _normalize_answer(packaged_default_answer(_LANGUAGES_ANSWER_KEY) or "")


def is_placeholder_language_answer(value: object) -> bool:
    """Return True when *value* declares no language (placeholder, sentinel, ``unknown`` or the shipped default)."""
    normalized = _normalize_answer(value)
    return (
        normalized in _PLACEHOLDER_ANSWERS
        or normalized.startswith(_NEEDS_CLARIFICATION_PREFIX)
        or normalized == _shipped_default_answer()
    )


def _answer_items(raw: str) -> list[str]:
    """Split a stringified answer: a list repr (``"['Zig', 'C']"``) becomes its members."""
    text = raw.strip()
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = ast.literal_eval(text)
        except (ValueError, SyntaxError):
            return [text]
        if isinstance(parsed, (list, tuple)):
            return [str(item) for item in parsed]
    return [text]


_LIST_SEPARATORS = re.compile(r"[,;]|\s/\s")
_SLASH_SEPARATOR = re.compile(r"/")


def _real_parts(item: str) -> list[str]:
    """Split a scalar answer on ``,``/``;``/`` / ``/``/`` and drop placeholder parts.

    A whole item or comma/semicolon piece is tested before slash-splitting so
    ``n/a`` stays one placeholder rather than becoming ``n`` and ``a``.
    """
    if is_placeholder_language_answer(item):
        return []
    parts: list[str] = []
    for piece in _LIST_SEPARATORS.split(item):
        if is_placeholder_language_answer(piece):
            continue
        parts.extend(sub.strip() for sub in _SLASH_SEPARATOR.split(piece) if not is_placeholder_language_answer(sub))
    return parts


def _declared_language_answer(interview: CharterInterview) -> str | None:
    """Return the real ``languages_frameworks`` declaration, or ``None`` when it declares nothing."""
    raw = interview.answers.get(_LANGUAGES_ANSWER_KEY)
    if raw is None:
        return None
    real = [part for item in _answer_items(str(raw)) for part in _real_parts(item)]
    return ", ".join(real) or None


def _vocabulary_languages(answer: str, repo_root: Path | None) -> list[str]:
    """Whole-word tokens of *answer* that some doctrine artifact is scoped to."""
    vocabulary = scoped_language_vocabulary(repo_root)
    return sorted({token for token in _WORD_TOKEN.findall(answer.casefold()) if token in vocabulary})


def _languages_from_interview(repo_root: Path | None, interview: CharterInterview) -> list[str] | None:
    """Tier 2: resolve languages from the interview, the declared answer first.

    Operator decision D1 (2026-09-29): when the languages/frameworks answer is a
    REAL declaration, it decides alone -- built-in detector hits in that answer
    UNION doctrine-vocabulary whole-word hits in that answer, else
    ``[unknown]``.  Other answers are scanned (built-in detector only) solely
    when that answer is absent, default or a placeholder; nothing found is
    ``None`` (no signal).
    """
    answer = _declared_language_answer(interview)
    if answer is not None:
        recognised = set(extract_declared_languages(answer)) | set(_vocabulary_languages(answer, repo_root))
        return sorted(recognised) or [UNKNOWN_LANGUAGE]
    combined = "\n".join(str(value) for value in interview.answers.values())
    return extract_declared_languages(combined) or None


def lacks_specialist_guidance(languages: Iterable[str] | None, repo_root: Path | None) -> bool:
    """Return True when no installed doctrine is scoped to any of *languages* (operator decision D2).

    ``None`` (no signal) and ``[]`` (explicit empty) are never advisory
    candidates.  Otherwise reserved tokens are stripped and the remainder is
    compared with :func:`scoped_language_vocabulary`: ``[unknown]`` and
    ``[rust]`` (no shipped rust doctrine) lack guidance, ``[python]`` does not.
    Families are expanded before intersecting (a ``jvm``-scoped artifact is guidance
    for ``kotlin`` and ``java``). Drives the charter-extension advisory; the stored
    languages value is rendered independently.
    """
    if languages is None:
        return False
    normalized = set(normalize_languages(languages))
    if not normalized:
        return False
    active = set(expand_language_families(normalized)) - RESERVED_LANGUAGE_TOKENS
    return not active & scoped_language_vocabulary(repo_root)


def _read_compiled_languages(repo_root: Path) -> list[str] | None:
    """Read the structured ``languages`` field persisted at compile time.

    Returns ``None`` when ``charter.yaml`` does not exist, or its ``catalog``
    section does not carry the structured ``languages`` field yet (a charter
    compiled before this field existed) — the caller falls back to interview
    extraction in that case. Returns an empty list (not ``None``) when the
    field is present but empty, since that is a legitimate compiled answer,
    not an absence signal.

    Tier-1, authoritative post-inversion (WP08): reads ``charter.yaml``'s
    ``catalog.languages`` rather than the retired ``references.yaml``.

    Reads through the single shared ``catalog.<field>`` accessor
    (:func:`charter.activation.charter_yaml_io.read_catalog_field`,
    Finding B / #4993) -- absent file, unparseable document, absent
    ``catalog``, and absent ``languages`` all collapse to the accessor's
    uniform ``None``, which this function's own ``isinstance(languages,
    list)`` guard below already treats identically to a present-but-null
    or non-list value (byte-identical behavior to the prior hand-rolled
    read).
    """
    languages = read_catalog_field(repo_root, "languages")
    if not isinstance(languages, list):
        return None

    return list(normalize_languages(str(item) for item in languages))


def _read_disk_interview(repo_root: Path | None) -> CharterInterview | None:
    if repo_root is None:
        return None
    return read_interview_answers(repo_root / ".kittify" / "charter" / "interview" / "answers.yaml")


def _is_packaged_default_interview(interview: CharterInterview) -> bool:
    """Return True when every answer is the shipped ``defaults.yaml`` text (a non-user interview)."""
    return all(str(value) == packaged_default_answer(key) for key, value in interview.answers.items())


def infer_repo_languages(
    repo_root: Path | None,
    *,
    interview: CharterInterview | None = None,
    prefer_interview: bool = False,
) -> list[str] | None:
    """Infer active project languages — the SINGLE authority for this signal.

    Every consumer (``compile_charter``'s ``catalog.languages`` stamp and the
    active charter service builder's language gate) calls this one function so they
    can never compute diverging answers (#3292).

    Result states (the distinction is load-bearing for
    ``applies_to_languages_match``):

    * ``None`` — no signal (no charter/interview, or an answer that declares
      nothing: empty, placeholder, the shipped default text). Admit everything.
    * ``[]`` — an explicit empty compiled answer. Admit nothing scoped.
    * a recognised list — e.g. ``["python"]``.
    * ``["unknown"]`` — a real declaration no doctrine artifact is scoped to
      (#5284); the runtime falls back to language-independent guidance.

    Tier order: (1) the compiled ``catalog.languages`` in ``charter.yaml`` —
    authoritative once present, even when empty; (2) the interview (*interview*
    if supplied, else the on-disk transcript), via
    :func:`_languages_from_interview`. There is no ``charter.md`` fallback.

    Runtime stays compiled-first on purpose (#2395/#3292: a stale interview must
    never override a compiled charter). Regeneration is the one place that
    bypasses tier 1: ``prefer_interview=True`` with an interview available (in
    memory or on disk) resolves from the interview alone and may return ``None``.

    *repo_root* may be ``None`` (in-memory compiles): tier 1 and the on-disk
    interview are then skipped.
    """
    resolved_interview = interview
    if prefer_interview and resolved_interview is None:
        resolved_interview = _read_disk_interview(repo_root)

    if not (prefer_interview and resolved_interview is not None):
        compiled_languages = _read_compiled_languages(repo_root) if repo_root is not None else None
        if compiled_languages is not None:
            return compiled_languages
        if resolved_interview is None or _is_packaged_default_interview(resolved_interview):
            # No compiled tier: read the on-disk transcript exactly as the runtime does. A
            # supplied interview that is only the shipped default carries no user answers, so it
            # must not mask them (compile and runtime would otherwise diverge, F5).
            resolved_interview = _read_disk_interview(repo_root) or resolved_interview

    if resolved_interview is None:
        return None
    return _languages_from_interview(repo_root, resolved_interview)
