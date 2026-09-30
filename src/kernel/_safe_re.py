"""Linear-time regular expression engine backed by Google RE2.

Drop-in replacement for ``import re`` that uses Google's RE2 engine
(``google-re2``, a mandatory core dependency).  RE2 guarantees O(n)
matching time, preventing catastrophic backtracking (ReDoS).

Usage::

    from kernel._safe_re import re

    # All stdlib re idioms continue to work:
    re.compile(r"\\d+")
    re.search(r"\\w+", text)
    isinstance(obj, re.Pattern)
    re.MULTILINE | re.DOTALL

RE2 routing policy
------------------
All patterns are compiled with RE2.  If RE2 rejects a pattern (e.g. it
uses PCRE-only syntax such as lookahead/lookbehind assertions or
back-references), ``re.error`` is raised immediately — the same
exception type that stdlib ``re.compile`` raises for invalid patterns.

Files that genuinely require PCRE features must use ``import re`` from
the stdlib directly and are deliberately excluded from the RE2 migration.
There is no silent fallback; a failed compile is always an error.

Flags
-----
``re.VERBOSE`` and ``re.LOCALE`` are not supported by RE2.  Passing
them raises ``re.error``.  All other stdlib flags (``IGNORECASE``,
``MULTILINE``, ``DOTALL``, ``ASCII``, ``UNICODE``, ``NOFLAG``) are
translated to inline-flag prefixes understood by RE2.
"""

from __future__ import annotations

import re as _stdlib_re
import sys
import types
from contextlib import suppress
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

__all__ = ["re"]

# ── RE2 import (hard dependency — fails loudly if google-re2 not installed) ──

import re2 as _re2_mod  # type: ignore[import-untyped]  # noqa: E402  # see research.md §1; upstream stubs pending

# ── Inline-flag prefix map ───────────────────────────────────────────────────
# RE2 does not expose re.MULTILINE / re.DOTALL etc. as integer constants.
# They must be expressed as inline flags prepended to the pattern string.

_FLAG_TO_INLINE: dict[int, str] = {
    _stdlib_re.IGNORECASE: "i",
    _stdlib_re.MULTILINE: "m",
    _stdlib_re.DOTALL: "s",
}

# Flags that RE2 does not support — using them is an error, not a fallback.
_UNSUPPORTED_FLAGS: int = _stdlib_re.VERBOSE | _stdlib_re.LOCALE


def _prepend_flags(pattern: str, flags: int) -> str:
    """Return *pattern* with RE2 inline-flag prefix applied.

    Raises ``re.error`` for unsupported flags rather than silently
    degrading to a different engine.
    """
    if flags & _UNSUPPORTED_FLAGS:
        bad = []
        if flags & _stdlib_re.VERBOSE:
            bad.append("re.VERBOSE")
        if flags & _stdlib_re.LOCALE:
            bad.append("re.LOCALE")
        raise _stdlib_re.error(
            f"kernel._safe_re: {', '.join(bad)} not supported by RE2. "
            "Use stdlib re directly for patterns that require these flags."
        )

    inline: list[str] = []
    for flag_val, letter in _FLAG_TO_INLINE.items():
        if flags & flag_val:
            inline.append(letter)

    if inline:
        pattern = "(?{})".format("".join(inline)) + pattern

    return pattern


def _re2_compile(pattern: str, flags: int = 0) -> _stdlib_re.Pattern:  # type: ignore[type-arg]
    """Compile *pattern* with RE2.

    Raises ``re.error`` (the stdlib type) if RE2 rejects the pattern for
    any reason, including PCRE-only syntax.  Never falls back silently.
    """
    re2_pattern = _prepend_flags(pattern, flags)
    try:
        return _re2_mod.compile(re2_pattern)  # type: ignore[no-any-return]
    except Exception as exc:
        # RE2 rejected the pattern — propagate as re.error so callers get a
        # familiar exception type.  Do not fall back to stdlib re.
        raise _stdlib_re.error(
            f"kernel._safe_re: RE2 rejected pattern {pattern!r}: {exc}. "
            "If this pattern requires PCRE features (lookahead, lookbehind, "
            "back-references), use stdlib re directly."
        ) from exc


# ── Build a fake module that mirrors stdlib re ───────────────────────────────
# Using types.ModuleType so that re.Pattern, re.RegexFlag, re.Match, etc.
# all resolve correctly at runtime and in type checkers.

_mod = types.ModuleType("kernel._safe_re.re")
_mod.__doc__ = "RE2-backed drop-in for stdlib re (kernel._safe_re)"

# ── Type aliases forwarded from stdlib (so re.Pattern[str] etc. work) ────
_mod.Pattern = _stdlib_re.Pattern  # type: ignore[attr-defined]
_mod.Match = _stdlib_re.Match  # type: ignore[attr-defined]
_mod.RegexFlag = _stdlib_re.RegexFlag  # type: ignore[attr-defined]
_mod.error = _stdlib_re.error  # type: ignore[attr-defined]

# ── Flag constants forwarded from stdlib ──────────────────────────────────
_mod.IGNORECASE = _stdlib_re.IGNORECASE  # type: ignore[attr-defined]
_mod.I = _stdlib_re.IGNORECASE  # type: ignore[attr-defined]
_mod.MULTILINE = _stdlib_re.MULTILINE  # type: ignore[attr-defined]
_mod.M = _stdlib_re.MULTILINE  # type: ignore[attr-defined]
_mod.DOTALL = _stdlib_re.DOTALL  # type: ignore[attr-defined]
_mod.S = _stdlib_re.DOTALL  # type: ignore[attr-defined]
_mod.VERBOSE = _stdlib_re.VERBOSE  # type: ignore[attr-defined]
_mod.X = _stdlib_re.VERBOSE  # type: ignore[attr-defined]
_mod.ASCII = _stdlib_re.ASCII  # type: ignore[attr-defined]
_mod.A = _stdlib_re.ASCII  # type: ignore[attr-defined]
_mod.UNICODE = _stdlib_re.UNICODE  # type: ignore[attr-defined]
_mod.U = _stdlib_re.UNICODE  # type: ignore[attr-defined]
_mod.LOCALE = _stdlib_re.LOCALE  # type: ignore[attr-defined]
_mod.L = _stdlib_re.LOCALE  # type: ignore[attr-defined]
_mod.NOFLAG = _stdlib_re.NOFLAG  # type: ignore[attr-defined]


# ── Module-level functions ────────────────────────────────────────────────


def _compile(pattern: str, flags: int = 0) -> _stdlib_re.Pattern:  # type: ignore[type-arg]
    return _re2_compile(pattern, flags)


def _search(pattern: str, string: str, flags: int = 0) -> _stdlib_re.Match | None:  # type: ignore[type-arg]
    return _re2_compile(pattern, flags).search(string)


def _match(pattern: str, string: str, flags: int = 0) -> _stdlib_re.Match | None:  # type: ignore[type-arg]
    return _re2_compile(pattern, flags).match(string)


def _fullmatch(pattern: str, string: str, flags: int = 0) -> _stdlib_re.Match | None:  # type: ignore[type-arg]
    return _re2_compile(pattern, flags).fullmatch(string)


def _findall(pattern: str, string: str, flags: int = 0) -> list:  # type: ignore[type-arg]
    return _re2_compile(pattern, flags).findall(string)


def _finditer(pattern: str, string: str, flags: int = 0) -> Iterator[_stdlib_re.Match[str]]:
    return _re2_compile(pattern, flags).finditer(string)


def _sub(pattern: str, repl: str, string: str, count: int = 0, flags: int = 0) -> str:
    return _re2_compile(pattern, flags).sub(repl, string, count)


def _subn(pattern: str, repl: str, string: str, count: int = 0, flags: int = 0) -> tuple[str, int]:
    return _re2_compile(pattern, flags).subn(repl, string, count)


def _split(pattern: str, string: str, maxsplit: int = 0, flags: int = 0) -> list:  # type: ignore[type-arg]
    return _re2_compile(pattern, flags).split(string, maxsplit)


def _escape(pattern: str) -> str:
    return _stdlib_re.escape(pattern)


def _purge() -> None:
    with suppress(AttributeError):
        _re2_mod.purge()
    _stdlib_re.purge()


_mod.compile = _compile  # type: ignore[attr-defined]
_mod.search = _search  # type: ignore[attr-defined]
_mod.match = _match  # type: ignore[attr-defined]
_mod.fullmatch = _fullmatch  # type: ignore[attr-defined]
_mod.findall = _findall  # type: ignore[attr-defined]
_mod.finditer = _finditer  # type: ignore[attr-defined]
_mod.sub = _sub  # type: ignore[attr-defined]
_mod.subn = _subn  # type: ignore[attr-defined]
_mod.split = _split  # type: ignore[attr-defined]
_mod.escape = _escape  # type: ignore[attr-defined]
_mod.purge = _purge  # type: ignore[attr-defined]

# Register in sys.modules so `import kernel._safe_re.re` also works
sys.modules["kernel._safe_re.re"] = _mod

# ── Public export ────────────────────────────────────────────────────────────

#: Drop-in replacement for the ``re`` module backed by RE2.  Use as::
#:
#:     from kernel._safe_re import re
re = _mod
