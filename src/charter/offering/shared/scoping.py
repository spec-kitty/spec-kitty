"""Shared helpers for optional doctrine artifact scoping."""

from __future__ import annotations

from typing import Iterable

__all__ = [
    "RESERVED_LANGUAGE_TOKENS",
    "SENTINEL_LANGUAGE_TOKENS",
    "UNKNOWN_LANGUAGE",
    "applies_to_languages_match",
    "is_unknown_language",
    "normalize_languages",
]

#: Reserved language value Spec Kitty itself writes for a project whose
#: language it does not recognise.  Artifacts cannot target it (the
#: ``charter validate`` guard rejects it) and it is stripped from both sides
#: of ``applies_to_languages_match``.  It is deliberately NOT a sentinel.
UNKNOWN_LANGUAGE = "unknown"

#: Tokens that are never real language identifiers for artifact scoping.
RESERVED_LANGUAGE_TOKENS: frozenset[str] = frozenset({UNKNOWN_LANGUAGE})

#: Sentinel strings that should never appear as real language tokens.
#: ``charter validate`` rejects artifacts that carry these at authoring time
#: (T020 guard in ``_validate_single_artifact``).  At runtime, reaching
#: ``applies_to_languages_match`` with one of these sentinels means the
#: artifact bypassed validation (e.g. hand-edited or loaded without the CLI
#: guard).  Defense-in-depth: treat them as unscoped so the artifact loads
#: rather than silently disappearing — the validator is the authoring-time
#: signal; the runtime must never silently drop content.
_SENTINEL_TOKENS: frozenset[str] = frozenset({"any", "all"})

#: Public alias so authoring-time validators reuse this set instead of copying it.
SENTINEL_LANGUAGE_TOKENS: frozenset[str] = _SENTINEL_TOKENS


def normalize_languages(values: Iterable[str] | None) -> tuple[str, ...]:
    """Return lowercase, de-duplicated language identifiers."""
    if values is None:
        return ()

    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value).strip().lower()
        if not item or item in seen:
            continue
        seen.add(item)
        normalized.append(item)
    return tuple(normalized)


def is_unknown_language(languages: Iterable[str] | None) -> bool:
    """Return True iff the normalized language set is exactly ``{"unknown"}``.

    ``None`` and empty sets are not unknown-language projects, and a
    hand-edited mixed set such as ``[python, unknown]`` is not either.
    """
    return set(normalize_languages(languages)) == {UNKNOWN_LANGUAGE}


def _strip_reserved(values: Iterable[str] | None) -> set[str]:
    """Normalize *values* and drop reserved tokens."""
    return set(normalize_languages(values)) - RESERVED_LANGUAGE_TOKENS


def applies_to_languages_match(
    artifact_languages: Iterable[str] | None,
    active_languages: Iterable[str] | None,
) -> bool:
    """Return whether an artifact should load for the active language set.

    Rules:
    - Unscoped artifacts always load.
    - When no active language filter is provided, scoped artifacts still load.
    - When active languages are explicitly empty/unknown, scoped artifacts do not load.
    - Otherwise any overlap between artifact and active languages is sufficient.
    - Reserved tokens (``unknown``) are stripped from BOTH sides first: an
      artifact scoped only to ``unknown`` never loads (invalid scope), an
      active set that is only ``unknown`` admits no scoped artifact, and
      ``[python, unknown]`` behaves exactly like ``[python]``.

    Defense-in-depth (T021): if ``artifact_languages`` contains a sentinel
    token (``any`` / ``all``) the artifact is treated as unscoped (always
    loads).  These tokens are rejected at authoring time by the
    ``charter validate`` guard; reaching this function with them means the
    artifact bypassed validation.  Treating them as unscoped is the correct
    fallback — silently filtering the artifact would cause harder-to-diagnose
    missing-content failures at runtime.
    """
    raw_scope = set(normalize_languages(artifact_languages))
    if not raw_scope:
        return True

    artifact_scope = raw_scope - RESERVED_LANGUAGE_TOKENS
    if not artifact_scope:
        # Scoped only to a reserved token: invalid scope, never load.
        return False

    # Defense-in-depth: sentinel tokens bypass scope filtering — see docstring.
    if artifact_scope <= _SENTINEL_TOKENS:
        return True

    if active_languages is None:
        return True

    active_scope = _strip_reserved(active_languages)
    if not active_scope:
        return False

    return bool(artifact_scope & active_scope)
