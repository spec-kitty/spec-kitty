"""L1 pure-decode primitive for ``meta.json`` content — the single malformed authority.

Lives in ``kernel`` (the zero-dependency root) so every layer can depend on it:
``git/ref_advance.py`` is git plumbing that may not import ``specify_cli`` (C-003),
while ``mission_metadata.py`` (L2) already imports ``specify_cli.core.*``. Only the
kernel is reachable from both plumbing and application, so the malformed *definition*
must live here (D1).

This module is **pure**: it never touches the filesystem. Callers read the bytes/str
(L2 owns file I/O and the ``empty→benign`` short-circuit; L3 owns the dir-level
fail-closed policy) and hand the raw content here for the one canonical decode.

The malformed set — defined exactly once, here (D2):

- :class:`json.JSONDecodeError` (JSON syntax error),
- :class:`UnicodeDecodeError` from the **explicit** ``raw.decode("utf-8")`` of
  ``bytes`` *before* :func:`json.loads` (``json.loads(b"...")`` auto-detects the
  encoding and would raise :class:`json.JSONDecodeError`, never
  :class:`UnicodeDecodeError`; the explicit decode is load-bearing so bad bytes
  surface as the encoding error the malformed contract requires),
- a non-``dict`` top level (e.g. a JSON array or scalar).

Empty/whitespace-only content is **not** L1's concern (C-010): ``None`` means
*malformed only*. A caller/L2 that contracts empty→benign must short-circuit before
calling here.

**Refactor note (mission cli-error-surface-seam-01M2WJD2, WP01/T003)**: this module
stays pure (no filesystem I/O) so it cannot literally call
:func:`kernel.guarded_read.read_guarded` (which requires a ``Path``) without
breaking that documented contract. The plan's ``MDEC --> PRIM`` dependency arrow is
therefore expressed by sharing ``read_guarded``'s private exception-collapsing
helper (:func:`kernel.guarded_read._collapse`) for the one branch that is a genuine
"catch a declared exception, raise one typed error" pattern (the JSON-decode
branch); the non-dict-top-level check is a post-condition on already-decoded data,
not an exception being collapsed, so it stays a direct ``raise``.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from kernel.errors import GuardedReadError
from kernel.guarded_read import _collapse

__all__ = [
    "MetaDecodeError",
    "decode_meta",
]

OnMalformed = Literal["raise", "empty", "none"]

_DECODE_ERRORS: tuple[type[BaseException], ...] = (json.JSONDecodeError, UnicodeDecodeError)


class MetaDecodeError(GuardedReadError, ValueError):
    """Raised when ``meta.json`` content is malformed.

    Subclasses :class:`ValueError` so every existing ``except ValueError``
    boundary (L2 ``_parse_meta_text``, L3 ``load_meta_fail_closed``'s wrap, and
    other callers) keeps catching by inheritance. Also subclasses
    :class:`kernel.errors.GuardedReadError` (mission cli-error-surface-seam)
    so the global CLI presentation hook catches it too — MRO
    ``[MetaDecodeError, GuardedReadError, ValueError, Exception, ...]`` keeps
    both ``isinstance`` contracts. Deliberately **not** a subclass of
    :class:`kernel.errors.KittyInternalConsistencyError`, which is *not* a
    :class:`ValueError` and would therefore leak past those boundaries.
    """


def _absorb(on_malformed: OnMalformed) -> dict[str, Any] | None:
    """Return the absorbed sentinel for a non-raising malformed policy."""
    return {} if on_malformed == "empty" else None


def _decode_json(raw: str | bytes) -> Any:
    """Decode *raw* to a JSON value, explicitly UTF-8-decoding ``bytes`` first."""
    text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
    return json.loads(text)


def _decode_meta_or_raise(raw: str | bytes) -> dict[str, Any]:
    """``on_malformed="raise"`` path: collapse decode errors, then check shape."""
    data = _collapse(
        lambda: _decode_json(raw),
        _DECODE_ERRORS,
        lambda exc: MetaDecodeError(str(exc)),
    )
    if not isinstance(data, dict):
        raise MetaDecodeError(f"Expected JSON object, got {type(data).__name__}")
    return data


def _decode_meta_absorbing(raw: str | bytes, on_malformed: OnMalformed) -> dict[str, Any] | None:
    """``on_malformed in {"empty", "none"}`` path: absorb instead of raising."""
    try:
        data = _decode_json(raw)
    except _DECODE_ERRORS:
        return _absorb(on_malformed)
    if not isinstance(data, dict):
        return _absorb(on_malformed)
    return data


def decode_meta(
    raw: str | bytes,
    *,
    on_malformed: OnMalformed = "raise",
) -> dict[str, Any] | None:
    """Decode ``meta.json`` *raw* content to a mapping — the L1 malformed authority.

    Args:
        raw: The undecoded ``meta.json`` content. ``bytes`` are decoded as
            UTF-8 explicitly (see module docstring) before parsing; ``str`` is
            parsed directly.
        on_malformed: Policy when the content is malformed —
            ``"raise"`` (default) raises :class:`MetaDecodeError`,
            ``"empty"`` returns ``{}``, ``"none"`` returns ``None``.

    Returns:
        The parsed mapping when *raw* is a valid JSON object; otherwise the
        absorbed sentinel (``{}`` / ``None``) per *on_malformed*.

    Raises:
        MetaDecodeError: When *raw* is malformed and ``on_malformed="raise"``.
    """
    if on_malformed == "raise":
        return _decode_meta_or_raise(raw)
    return _decode_meta_absorbing(raw, on_malformed)
