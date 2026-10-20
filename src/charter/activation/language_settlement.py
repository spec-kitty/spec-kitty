"""The language settlement: detect, propose or ask, decide what to store, then store it (#6540, #6542).

Settling decides and never writes: :func:`settle_project_languages` returns a
:class:`LanguageSettlement` whose ``to_store`` says what, if anything, belongs in
``.kittify/config.yaml``. :func:`store_language_settlement` performs that write, so a caller
can store the languages together with the rest of its results and an aborted run stores
nothing (#6542).

This module sits above both :mod:`charter.activation.language_authority` and the code reader
(:mod:`charter.activation.evidence.code_reader`): the code reader imports the authority, and
the authority never imports the code reader, so the only edge between them points one way (#6540).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from charter.activation.evidence.code_reader import CodeReadingCollector
from charter.activation.language_authority import (
    CONFIG_LANGUAGES_KEY,
    CONFIG_RELATIVE_PATH,
    configured_languages,
    invalid_language_reason,
    languages_key_is_set,
    write_configured_languages,
)
from charter.languages import LANGUAGE_TOKENS
from charter.offering.shared.scoping import normalize_languages

__all__ = [
    "LanguageSettlement",
    "settle_project_languages",
    "store_language_settlement",
]

_ANSWER_SEPARATORS = re.compile(r"[,;\s]+")
_NO_LANGUAGES_ANSWERS = frozenset({"none", "-", "n/a"})

#: How many times an interactive answer is re-asked after an invalid entry before the step fails.
_ANSWER_ATTEMPTS = 3


@dataclass(frozen=True, slots=True)
class LanguageSettlement:
    """What the interview's language step decided.

    ``source`` is ``stored`` (an existing list kept as it was), ``confirmed`` (the operator's
    answer), ``detected`` (a non-interactive run proposes the detected list because the key
    is absent) or ``none`` (nothing to store). ``languages`` is empty only for ``none``.
    ``to_store`` is the list :func:`store_language_settlement` writes, or ``None`` when
    ``config.yaml`` is to stay as it is; nothing is written until then. ``notice`` is set for
    ``detected`` (what is stored, that it was detected rather than confirmed, and how to
    change it; DM-01M5ASPC) and for a ``none`` left by a set but unusable key.
    """

    languages: tuple[str, ...]
    source: Literal["stored", "confirmed", "detected", "none"]
    detected: tuple[str, ...]
    to_store: tuple[str, ...] | None = None
    notice: str | None = None


def _parse_language_answer(answer: str) -> tuple[str, ...]:
    """Return the catalog tokens an operator answer lists; ``ValueError`` names every invalid entry.

    ``none`` (or ``-``, ``n/a``, blank) is an empty list.
    """
    text = answer.strip().lower()
    if text in _NO_LANGUAGES_ANSWERS or not text:
        return ()
    tokens = tuple(normalize_languages(part for part in _ANSWER_SEPARATORS.split(text) if part))
    invalid = [token for token in tokens if invalid_language_reason(token) is not None]
    if invalid:
        known = ", ".join(LANGUAGE_TOKENS)
        raise ValueError(f"Not a catalog language: {', '.join(invalid)}. Use any of: {known}.")
    return tokens


def _detect_repository_languages(repo_root: Path) -> tuple[str, ...]:
    """Observe the repository's languages, ignoring any configured list (primary first)."""
    return tuple(CodeReadingCollector(repo_root, use_configured_languages=False).collect().languages)


def _detected_notice(languages: tuple[str, ...]) -> str:
    """Return the notice a non-interactive run shows after storing the detected list."""
    return (
        f"Project languages stored as DETECTED, not confirmed: {', '.join(languages)}. "
        f"To change them, edit '{CONFIG_LANGUAGES_KEY}:' in {CONFIG_RELATIVE_PATH.as_posix()} "
        "or re-run 'spec-kitty charter interview' interactively."
    )


def _ask_until_valid(
    ask: Callable[[str], str],
    proposal: str,
    on_invalid: Callable[[str], None] | None,
) -> tuple[str, ...]:
    """Ask for the language list, re-asking after an invalid answer; raise the last error after the bounded retries."""
    for attempt in range(1, _ANSWER_ATTEMPTS + 1):
        try:
            return _parse_language_answer(ask(proposal))
        except ValueError as exc:
            if attempt == _ANSWER_ATTEMPTS:
                raise
            if on_invalid is not None:
                on_invalid(str(exc))
    raise AssertionError("unreachable")  # pragma: no cover


def _unusable_notice() -> str:
    """Return the notice shown when the key is set but yields no usable language, so nothing is stored."""
    return (
        f"'{CONFIG_LANGUAGES_KEY}:' in {CONFIG_RELATIVE_PATH.as_posix()} is set but holds no usable language list, so it was left as it is. "
        f"Set it to a list of catalog language tokens (for example '{CONFIG_LANGUAGES_KEY}: [python]') or remove the key, "
        "then re-run 'spec-kitty charter interview'."
    )


def _settle_without_asking(repo_root: Path, stored: tuple[str, ...] | None, detected: tuple[str, ...]) -> LanguageSettlement:
    """Non-interactive settle: keep a stored list, else propose the detected one with a notice.

    A key that is set but unusable (a scalar, only non-catalog entries, an unreadable file) is the
    operator's, not absent: it is never overwritten and the notice says how to fix it.
    """
    if stored is not None:
        return LanguageSettlement(stored, "stored", detected)
    if languages_key_is_set(repo_root):
        return LanguageSettlement((), "none", detected, notice=_unusable_notice())
    if not detected:
        return LanguageSettlement((), "none", detected)
    return LanguageSettlement(detected, "detected", detected, to_store=detected, notice=_detected_notice(detected))


def settle_project_languages(
    repo_root: Path,
    *,
    ask: Callable[[str], str] | None,
    on_invalid: Callable[[str], None] | None = None,
) -> LanguageSettlement:
    """Detect the repository's languages, propose them, and decide what to store (FR-020). Writes nothing.

    *ask* receives the proposal (the stored list, else the detected one, comma-separated) and
    returns the operator's answer; it is ``None`` for a non-interactive or ``--defaults`` run,
    which never blocks and never overwrites a stored list: it decides to store the detected
    list only when the key is absent, and says so in ``notice``. An invalid answer is reported
    through *on_invalid* and asked again, up to the retry bound; after that
    ``ValueError`` is raised. A blank or ``none`` answer leaves the key as it was. The
    decision is carried out by :func:`store_language_settlement`.
    """
    stored = configured_languages(repo_root)
    detected = _detect_repository_languages(repo_root)
    if ask is None:
        return _settle_without_asking(repo_root, stored, detected)

    confirmed = _ask_until_valid(ask, ", ".join(stored or detected), on_invalid)
    if not confirmed:
        return LanguageSettlement(stored or (), "stored" if stored else "none", detected)
    if confirmed == stored:
        return LanguageSettlement(stored, "stored", detected)
    return LanguageSettlement(confirmed, "confirmed", detected, to_store=confirmed)


def store_language_settlement(repo_root: Path, settlement: LanguageSettlement) -> None:
    """Write what *settlement* decided to ``.kittify/config.yaml``; a no-op when it decided nothing. Idempotent.

    A ``detected`` settlement was decided because the key was absent. The write comes later (after
    the interview answers), so the key is checked again: one that appeared meanwhile is the
    operator's and is never overwritten.
    """
    if settlement.to_store is None:
        return
    if settlement.source == "detected" and languages_key_is_set(repo_root):
        return
    write_configured_languages(repo_root, settlement.to_store)
