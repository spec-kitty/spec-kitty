"""The single leak-pattern authority for the contract tooling (plan D-P11).

Four kinds of leak are recognised: an absolute host path, an e-mail address, a
secret or token (a GitHub token, an AWS access key id, a private-key header) and
a property name that carries local identity. String values fall into field
classes (spec D-14), because real titles and names legitimately mention ``~/``
or a temporary directory:

* ``strict``: identifiers, handles and path-like values. A leading ``~/`` or any
  absolute path is a host path.
* ``human``: free text. Only a real host path is a leak; a bare ``~/`` or a
  temporary-directory word is not.

The e-mail and secret patterns apply to every string field. Pattern sources and name lists
are written so that this file does not match its own rules; a unit test scans
this source with the human-text class and expects no finding.

Library only: standard library, no pytest, nothing from ``tests/`` or ``scripts/``.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

STRICT = "strict"
HUMAN = "human"
FIELD_CLASSES: tuple[str, ...] = (STRICT, HUMAN)

CODE_HOST_PATH = "HOST_PATH"
CODE_EMAIL = "EMAIL"
CODE_CREDENTIAL = "SECRET"

_HOME_ROOTS = "(?:home|Users)"

# Strict fields: a value is a host path if it starts like one anywhere in the
# filesystem, names a home directory segment, or names a Windows user profile.
STRICT_HOST_PATH_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^(?:/|~/|[A-Za-z]:[\\/])"),
    re.compile(r"(?:^|/)" + _HOME_ROOTS + r"/[^/\s]+/"),
    re.compile(r"[A-Za-z]:\\Users\\"),
)

# Human text fields: only a real host path inside prose. A leading tilde and a
# bare temporary-directory word are not host paths here.
HUMAN_HOST_PATH_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?<![\w.~-])/(?:home|Users|root)/[^\s/]+"),
    re.compile(r"(?<![\w.~-])/(?:tmp|var/tmp|var/folders)/\S"),
    re.compile(r"[A-Za-z]:\\Users\\[^\s\\]+"),
)

# An address is a local part, the at sign and a dotted domain, or the at sign and a dotless host
# (a bare ``localhost`` or build-host name). The dotless form is deliberately narrow so that
# ``name@<build id>``, ``owner/repo@ref``, ``@scope/pkg`` and ``HEAD@{1}`` are not read as
# addresses: it needs a left boundary and an all-letter host (a digit makes it an id, not a host).
# Both alternatives start only at the start of a token, so a long token without an at sign is
# scanned once and not once per character (the unanchored form took quadratic time).
# DETECTION ONLY: this pattern answers whether an address is present (``.search``). It does not give every
# span the old unanchored form gave (a second address glued onto a match is missed), so never use it
# for ``.sub``, ``.subn``, ``.finditer`` or ``.findall``: use ``email_matches`` or ``redact_emails``.
EMAIL_PATTERN: re.Pattern[str] = re.compile(
    r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+"
    r"|(?<![\w.%+/@-])[A-Za-z0-9._%+-]+@[A-Za-z][A-Za-z-]*(?![\w@-]|\.[A-Za-z0-9])"
)

# The same address grammar without the leading lookbehind. It is only ever applied anchored, at the
# position where the previous match ended (see ``email_matches``); unanchored it is quadratic.
_EMAIL_ANCHORED: re.Pattern[str] = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+"
    r"|(?<![\w.%+/@-])[A-Za-z0-9._%+-]+@[A-Za-z][A-Za-z-]*(?![\w@-]|\.[A-Za-z0-9])"
)


def email_matches(text: str) -> Iterator[re.Match[str]]:
    """Every address in ``text``, with the spans the unanchored quadratic pattern found, in linear time.

    ``EMAIL_PATTERN`` starts only at the start of a token. The unanchored form could also start
    inside a token, but only where the previous match had just ended (a local-part character glued
    onto the end of an address); that one position is tried anchored here. A start elsewhere inside
    a token fails whenever the start of the token fails, so no other span is lost.
    """
    position = 0
    while position <= len(text):
        found = _EMAIL_ANCHORED.match(text, position) if position else None
        if found is None:
            found = EMAIL_PATTERN.search(text, position)
        if found is None:
            return
        yield found
        position = found.end()


def redact_emails(text: str, token: str) -> tuple[str, int]:
    """``text`` with every address replaced by ``token``, and how many were replaced."""
    parts: list[str] = []
    last = 0
    count = 0
    for found in email_matches(text):
        parts.append(text[last : found.start()])
        parts.append(token)
        last = found.end()
        count += 1
    parts.append(text[last:])
    return "".join(parts), count


# Secrets and tokens: a GitHub token (classic gh[pousr]_ or fine-grained), an AWS access key id
# (long-lived AKIA or temporary ASIA) and the header line of a PEM private key. The sources are
# written so that none of them matches its own text.
SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?<![A-Za-z0-9_])gh[pousr]_[A-Za-z0-9]{36,}"),
    re.compile(r"(?<![A-Za-z0-9_])github_pat_[A-Za-z0-9_]{40,}"),
    re.compile(r"(?<![A-Za-z0-9])(?:AKIA|ASIA)[0-9A-Z]{16}(?![A-Za-z0-9])"),
    re.compile(r"-{5}BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY(?: BLOCK)?-{5}"),
)

_HOST_PATH_PATTERNS = {STRICT: STRICT_HOST_PATH_PATTERNS, HUMAN: HUMAN_HOST_PATH_PATTERNS}

# Property names that would expose local paths. Matching ignores case, underscores
# and hyphens, so the camel-case and kebab forms are covered by the same entries.
FORBIDDEN_PROPERTY_NAMES: tuple[str, ...] = (
    "feedback_path",
    "record_path",
    "prompt_path",
    "feature_dir",
    "worktree",
    "worktree_path",
    "project_path",
    "feedbackPath",
    "recordPath",
    "promptPath",
    "featureDir",
    "worktreePath",
    "projectPath",
)


def _normalise(name: str) -> str:
    return name.lower().replace("_", "").replace("-", "")


_FORBIDDEN_NORMALISED = frozenset(_normalise(name) for name in FORBIDDEN_PROPERTY_NAMES)


def is_forbidden_property_name(name: str) -> bool:
    """True when ``name`` is a forbidden property name in any spelling."""
    return _normalise(name) in _FORBIDDEN_NORMALISED


def leak_codes(value: Any, field_class: str) -> tuple[str, ...]:
    """The leak codes found in ``value`` for ``field_class``: ``HOST_PATH``, ``EMAIL``, then ``SECRET``.

    Only strings are scanned; any other value yields no code. An unknown field
    class is refused rather than treated as clean.
    """
    if field_class not in _HOST_PATH_PATTERNS:
        raise ValueError(f"unknown field class {field_class!r}; expected one of {FIELD_CLASSES}")
    if not isinstance(value, str):
        return ()
    codes: list[str] = []
    if any(pattern.search(value) for pattern in _HOST_PATH_PATTERNS[field_class]):
        codes.append(CODE_HOST_PATH)
    if EMAIL_PATTERN.search(value):
        codes.append(CODE_EMAIL)
    if any(pattern.search(value) for pattern in SECRET_PATTERNS):
        codes.append(CODE_CREDENTIAL)
    return tuple(codes)
