"""Helpers for deriving active project languages from charter inputs."""

from __future__ import annotations

from pathlib import Path
import re
from typing import TYPE_CHECKING

from charter.activation.charter_yaml_io import read_catalog_field
from charter.activation.interview import read_interview_answers
from charter.offering.shared.scoping import normalize_languages

if TYPE_CHECKING:
    from charter.activation.interview import CharterInterview

__all__ = [
    "extract_declared_languages",
    "infer_repo_languages",
]



_LANGUAGE_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("python", (r"\bpython\b", r"\bpytest\b", r"\bmypy\b", r"\bruff\b")),
    ("typescript", (r"\btypescript\b", r"\btsc\b")),
    ("javascript", (r"\bjavascript\b", r"\bjest\b", r"\bnode(?:\.js)?\b", r"\bnpm\b", r"\bpnpm\b", r"\byarn\b")),
    ("rust", (r"\brust\b", r"\bcargo\b", r"\brustc\b")),
    ("java", (r"\bjava\b", r"\bjunit\b", r"\bgradle\b", r"\bmaven\b")),
    ("swift", (r"\bswift\b", r"\bxctest\b")),
    ("ruby", (r"\bruby\b", r"\brspec\b", r"\brails\b")),
    ("php", (r"\bphp\b", r"\bphpunit\b")),
)


def extract_declared_languages(text: str) -> list[str]:
    """Return canonical language identifiers mentioned in free-form text."""
    haystack = text.lower()
    matches: list[str] = []
    for language, patterns in _LANGUAGE_PATTERNS:
        if any(re.search(pattern, haystack) for pattern in patterns):
            matches.append(language)
    return list(normalize_languages(matches))


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


def infer_repo_languages(
    repo_root: Path | None,
    *,
    interview: CharterInterview | None = None,
) -> list[str] | None:
    """Infer active project languages — the SINGLE authority for this signal.

    Both consumers of "active languages" — ``charter.activation.compiler.compile_charter``
    (which stamps the result into ``catalog.languages`` at compile time) and
    ``charter.activation.doctrine_service_builder`` (which uses the result to gate which
    language-scoped styleguides/toolguides resolve to real content) — call
    this one function so they can never independently compute diverging
    answers (issue #3292: two separate ``extract_declared_languages`` calls
    used to feed a compile-time-only stamp and a runtime gate respectively,
    letting the first compile's empty stamp become the second run's
    authoritative "admit nothing" signal — a self-reinforcing feedback loop).

    *repo_root* is ``Path | None`` (not just ``Path``) so ``compile_charter``
    can call this same function even when it has no repository to read a
    compiled charter or an on-disk interview transcript from (e.g. tests
    that compile in-memory only). ``None`` skips tiers 1 and disk-tier-2
    entirely and resolves purely from *interview*, if supplied.

    Resolution precedence (FR-008/FR-009/FR-010):
      1. The structured ``languages`` field persisted in ``charter.yaml``'s
         ``catalog`` section at ``charter generate``/``charter sync`` time.
         Once *present* (the key exists and is a list), this is authoritative
         and unconditionally wins — the interview transcript is never
         consulted, even if it would produce a different answer, and even
         when the persisted list is empty (``catalog.languages: []`` is a
         legitimate, load-bearing answer if something actually wrote it —
         see the next paragraph for why nothing in this codebase does,
         post-#3292).
      2. Otherwise (no compiled charter yet, or a ``charter.yaml`` compiled
         before this field existed, i.e. tier 1 found no persisted list at
         all): fall back to the interview transcript. *interview*, when
         supplied, is used directly — this is how a caller mid-compile (which
         holds the freshly-loaded interview in memory, possibly not yet
         persisted to disk) shares the exact answer this function would give
         a caller reading only from disk. When *interview* is not supplied,
         the on-disk transcript at ``.kittify/charter/interview/answers.yaml``
         is read instead. Either way, the extraction result is returned only
         when it is **non-empty** — an interview that names no recognized
         language is treated the same as no interview at all (#3292 fix: this
         tier used to return the empty extraction result as a "legitimate"
         answer, which is indistinguishable from tier 1's genuinely-empty
         case once it round-trips through a compile — see below).
      3. When no tier above yields a result — no compiled charter, no
         interview transcript, OR an interview/transcript that names no
         recognized language — there is no active-language signal. Resolves
         to ``None``, distinct from an empty list.

    The ``None`` vs. ``[]`` distinction is load-bearing for callers, not
    cosmetic: ``charter.offering.shared.scoping.applies_to_languages_match`` treats
    ``active_languages=None`` as "admit every scoped artifact" and an
    explicitly empty active set as "admit none". #3292's root cause was
    ``charter.activation.compiler.compile_charter`` independently re-scanning the
    interview on every compile and unconditionally stamping the (possibly
    empty) result into ``catalog.languages``, while this function's tier 1
    then read that persisted empty list back as authoritative "admit none" on
    the *next* run — even though the compile that produced it had no real
    signal at all. ``compile_charter`` now calls this exact function
    (passing its in-memory *interview*) instead of scanning independently,
    and tier 2 no longer treats an empty scan as a legitimate answer — so a
    language-agnostic or absent interview resolves to ``None`` at compile
    time too, and ``compile_charter`` persists that as an *absent* structured
    field (schema-null / omitted key), which tier 1 above also reads back as
    "not present" on the next run. A tier-1 ``[]`` therefore can only appear
    from a hand-edited or externally-authored ``charter.yaml`` — the sole
    built-in producer never emits one anymore, which is what makes tier 1's
    "authoritative even when empty" rule safe: it never observes its own
    compiler's output looping back as a false "admit none" signal.

    There is no further ``charter.md`` prose fallback (WP08 / FR-009):
    ``charter.md`` is a curated narrative document, not a decision input, and
    ``catalog.languages`` is populated from the same interview signal at
    compile time — so a free-text re-scan of the prose would be redundant
    with tier-2, never additive.
    """
    compiled_languages = _read_compiled_languages(repo_root) if repo_root is not None else None
    if compiled_languages is not None:
        return compiled_languages

    resolved_interview = interview
    if resolved_interview is None and repo_root is not None:
        interview_path = repo_root / ".kittify" / "charter" / "interview" / "answers.yaml"
        resolved_interview = read_interview_answers(interview_path)

    if resolved_interview is not None:
        combined = "\n".join(str(value) for value in resolved_interview.answers.values())
        declared = extract_declared_languages(combined)
        if declared:
            return declared

    return None
