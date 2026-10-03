"""The single leak-pattern authority for the contract tooling (plan D-P11).

Three kinds of leak are recognised: an absolute host path, an e-mail address and
a property name that carries local identity. String values fall into field
classes (spec D-14), because real titles and names legitimately mention ``~/``
or a temporary directory:

* ``strict``: identifiers, handles and path-like values. A leading ``~/`` or any
  absolute path is a host path.
* ``human``: free text. Only a real host path is a leak; a bare ``~/`` or a
  temporary-directory word is not.

The e-mail pattern applies to every string field. Pattern sources and name lists
are written so that this file does not match its own rules; a unit test scans
this source with the human-text class and expects no finding.

Library only: standard library, no pytest, nothing from ``tests/`` or ``scripts/``.
"""

from __future__ import annotations

import re
from typing import Any

STRICT = "strict"
HUMAN = "human"
FIELD_CLASSES: tuple[str, ...] = (STRICT, HUMAN)

CODE_HOST_PATH = "HOST_PATH"
CODE_EMAIL = "EMAIL"

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

EMAIL_PATTERN: re.Pattern[str] = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")

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
    """The leak codes found in ``value`` for ``field_class``: ``HOST_PATH`` then ``EMAIL``.

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
    return tuple(codes)
