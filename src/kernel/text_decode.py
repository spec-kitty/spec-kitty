"""Single, non-guessing decode rule and newline normaliser (#4940, #4998).

Lives in ``kernel`` (the zero-dependency root) so it is reachable from every
layer, including ``charter``, which is not allowed to import upward from
``specify_cli`` (see ``docs/context/orchestration.md`` and the enforced layer
chain ``kernel <- charter <- {glossary, runtime, mission_runtime} <-
specify_cli``). This module imports **only the standard library** — no
``charset_normalizer``, no ``specify_cli``, nothing else. Reviewers grep the
imports of this file specifically.

**Provable encodings only.** :func:`decode_unambiguous` never guesses: it
succeeds only when a byte-order mark (BOM) or strict UTF-8 *proves* the
encoding. Anything else (single-byte code pages, tied ``charset_normalizer``
candidates, ambiguous heuristics) is out of scope here — that guessing layer
belongs one level up, in :func:`charter.encoding_recovery.recover`, which
calls :func:`charset_normalizer.from_bytes` for the cases a BOM/strict-UTF-8
proof cannot settle. This split is deliberate policy (#4940): user-owned
text that this kernel touches directly (e.g. a settings file) is either
decoded with proof or left
alone — never silently reinterpreted under a guessed code page.

BOMs are checked longest/most-specific first: the UTF-32-LE BOM
(``FF FE 00 00``) begins with the UTF-16-LE BOM (``FF FE``), so UTF-32 must
be tried before UTF-16 or a UTF-32-LE file is silently mis-decoded as
UTF-16-LE with embedded NUL bytes (the historical latent bug this module
fixes for ``charter.encoding_recovery.recover``).

``charter.encoding_recovery`` layers cp1252 (and other single-byte code
page) detection on top of the primitives this module exports; it does not
duplicate them.
"""

from __future__ import annotations

__all__ = ["decode_unambiguous", "detect_bom", "normalize_newlines"]

# Checked in this order: longest/most-specific match first. UTF-32 BOMs MUST
# be tried before UTF-16 BOMs because the UTF-32-LE BOM (`FF FE 00 00`)
# starts with the UTF-16-LE BOM (`FF FE`) -- reversing this order is exactly
# the historical mis-decode this module fixes.
_BOM_TABLE: tuple[tuple[bytes, str, str], ...] = (
    (b"\x00\x00\xfe\xff", "utf-32", "utf-32-be"),
    (b"\xff\xfe\x00\x00", "utf-32", "utf-32-le"),
    (b"\xef\xbb\xbf", "utf-8-sig", "utf-8-sig"),
    (b"\xff\xfe", "utf-16", "utf-16-le"),
    (b"\xfe\xff", "utf-16", "utf-16-be"),
)


def detect_bom(data: bytes) -> tuple[str, str] | None:
    """Return ``(codec, source_encoding)`` for a recognised BOM, or ``None``.

    Pure detection only — this never decodes ``data``. Checks
    :data:`_BOM_TABLE` in order (UTF-32 before UTF-16, see module docstring).
    """
    for prefix, codec, source_encoding in _BOM_TABLE:
        if data.startswith(prefix):
            return codec, source_encoding
    return None


def decode_unambiguous(data: bytes) -> tuple[str, str] | None:
    """Decode ``data`` only when a BOM or strict UTF-8 proves the encoding.

    Returns ``(text, source_encoding)`` on success, ``None`` when the
    encoding cannot be proven. Never guesses and never calls
    ``charset_normalizer``.

    - A recognised BOM (see :func:`detect_bom`) is tried first. If the bytes
      following the BOM fail to decode under its codec, that is **not**
      proof of anything else, so this returns ``None`` (it does not fall
      through to strict UTF-8 or raise).
    - Otherwise, strict ``UTF-8`` is tried (``data.decode("utf-8")`` with no
      error handler). Success proves ``utf-8``; failure returns ``None``.
    - Empty bytes decode to ``("", "utf-8")``.
    """
    bom = detect_bom(data)
    if bom is not None:
        codec, source_encoding = bom
        try:
            text = data.decode(codec)
        except UnicodeDecodeError:
            return None
        return text, source_encoding

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return text, "utf-8"


def normalize_newlines(text: str) -> str:
    """Convert CRLF and lone CR to LF. Nothing else.

    No BOM stripping, no whitespace trimming — callers that need those do
    them separately (see ``charter.hasher.hash_content``, which strips a
    leading BOM and outer whitespace itself around this call).
    """
    return text.replace("\r\n", "\n").replace("\r", "\n")
