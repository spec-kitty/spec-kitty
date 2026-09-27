"""Canonical, pure encoding-recovery detector for charter/mission text.

Single chokepoint for whole-file encoding recovery (#4962, WP01). Given raw
``bytes``, :func:`recover` returns an :class:`EncodingRecoveryResult` without
touching the filesystem, logging, or provenance — deterministic, single-pass,
and honest about confidence.

See ``kitty-specs/charter-encoding-codepage-guard-01M3FFP1/contracts/detector-contract.md``
and the companion ``data-model.md`` for the governing contract this module
implements.
"""

from __future__ import annotations

import codecs
from dataclasses import dataclass

import charset_normalizer

_BOM_UTF8_SIG = b"\xef\xbb\xbf"
_BOM_UTF16_LE = b"\xff\xfe"
_BOM_UTF16_BE = b"\xfe\xff"

#: Canonical name of the single-byte repair codec this module treats as the
#: cp1252 recovery target. Exported so other encoding-repair call sites
#: (e.g. ``specify_cli.text_sanitization``) share one definition instead of
#: duplicating the literal (#4896 unification, WP04).
CP1252_CODEC = "cp1252"

#: Tie tolerance around the minimum chaos score (WP01, test-driven; contract
#: allows re-tuning, but only via failing tests that demand a new value).
_TIE_EPSILON = 0.02

#: cp1252 / windows-1252 are the same code page under two common aliases.
_CP1252_FAMILY = frozenset({CP1252_CODEC, "windows-1252"})

#: The five byte values Windows-1252 leaves undefined (never legitimately
#: decodable by strict cp1252). Consumed only by
#: ``tests/charter/test_encoding_recovery.py``'s "0x81 fixture" ambiguity
#: class (``UNDEFINED_CP1252_FIXTURE``) -- NOT by the unsafe lossless bypass
#: (:func:`_cp1252_lossless_error_handler`), which maps ANY byte cp1252's own
#: decoder raises on to its raw code point generically, without consulting
#: this set. #4962 review fold C: the prior comment claimed the bypass
#: consumed this constant too; it never did.
_CP1252_UNDEFINED_BYTES = frozenset({0x81, 0x8D, 0x8F, 0x90, 0x9D})

#: A tie-broken single-byte pick must never report a bare 1.0 (contract
#: guarantee #3). This is the hard ceiling honest confidence can approach.
_MAX_HONEST_CONFIDENCE = 1.0 - _TIE_EPSILON

#: Confidence reported for the forced ``unsafe`` bypass: this is not a
#: detection result, it is an operator override, so it is reported as
#: minimally confident rather than borrowing a detection score.
_BYPASS_CONFIDENCE = 0.0

_LOSSLESS_CP1252_ERRORS = "charter-cp1252-lossless"


def _cp1252_lossless_error_handler(error: UnicodeError) -> tuple[str, int]:
    """Map cp1252-undefined bytes to their raw code point.

    Never substitutes U+FFFD: each undefined byte becomes the Unicode code
    point of the same ordinal, keeping the decode total and invertible
    instead of lossy. Registered only for decode use, so ``error`` is always
    a :class:`UnicodeDecodeError` in practice; the narrowing below satisfies
    ``codecs.register_error``'s broader ``UnicodeError`` signature.
    """
    if not isinstance(error, UnicodeDecodeError):
        raise error
    chunk = error.object[error.start : error.end]
    return "".join(chr(byte) for byte in chunk), error.end


codecs.register_error(_LOSSLESS_CP1252_ERRORS, _cp1252_lossless_error_handler)


@dataclass(frozen=True)
class EncodingRecoveryResult:
    """Pure result of a single :func:`recover` call.

    See ``data-model.md`` (Phase 1, "EncodingRecoveryResult") for the field
    contract this mirrors exactly.
    """

    text: str | None
    source_encoding: str | None
    confidence: float
    ambiguous: bool
    candidates: tuple[tuple[str, float], ...]
    normalization_applied: bool
    bypass_used: bool


def recover(data: bytes, *, unsafe: bool = False) -> EncodingRecoveryResult:
    """Recover text from ``data`` with an honest, deterministic verdict.

    Pure and I/O-free: no filesystem, logging, or provenance access. Calls
    ``charset_normalizer.from_bytes`` at most once, only when neither a BOM
    nor strict UTF-8 settles the question.
    """
    bom_result = _recover_from_bom(data)
    if bom_result is not None:
        return bom_result

    utf8_result = _recover_strict_utf8(data)
    if utf8_result is not None:
        return utf8_result

    return _recover_single_byte(data, unsafe=unsafe)


def _recover_from_bom(data: bytes) -> EncodingRecoveryResult | None:
    if data.startswith(_BOM_UTF8_SIG):
        return _bom_result(data, "utf-8-sig", "utf-8-sig")
    if data.startswith(_BOM_UTF16_LE):
        return _bom_result(data, "utf-16", "utf-16-le")
    if data.startswith(_BOM_UTF16_BE):
        return _bom_result(data, "utf-16", "utf-16-be")
    return None


def _bom_result(data: bytes, codec_name: str, source_encoding: str) -> EncodingRecoveryResult:
    text = data.decode(codec_name)
    return EncodingRecoveryResult(
        text=text,
        source_encoding=source_encoding,
        confidence=1.0,
        ambiguous=False,
        candidates=(),
        normalization_applied=True,
        bypass_used=False,
    )


def _recover_strict_utf8(data: bytes) -> EncodingRecoveryResult | None:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return EncodingRecoveryResult(
        text=text,
        source_encoding="utf-8",
        confidence=1.0,
        ambiguous=False,
        candidates=(),
        normalization_applied=False,
        bypass_used=False,
    )


def _recover_single_byte(data: bytes, *, unsafe: bool) -> EncodingRecoveryResult:
    matches = charset_normalizer.from_bytes(data)
    candidates = tuple((match.encoding, 1.0 - match.chaos) for match in matches)

    tied = _tied_candidates(candidates)
    selected = _select_from_tied(tied, data)
    if selected is not None:
        encoding, tie_size = selected
        return _selected_result(data, encoding, tie_size, candidates)

    if unsafe:
        return _bypass_result(data, candidates)

    return _ambiguous_result(candidates)


def _tied_candidates(candidates: tuple[tuple[str, float], ...]) -> dict[str, float]:
    if not candidates:
        return {}
    chaoses = {encoding: 1.0 - confidence for encoding, confidence in candidates}
    min_chaos = min(chaoses.values())
    return {encoding: chaos for encoding, chaos in chaoses.items() if chaos <= min_chaos + _TIE_EPSILON}


def _select_from_tied(tied: dict[str, float], data: bytes) -> tuple[str, int] | None:
    cp1252_in_tied = any(encoding in _CP1252_FAMILY for encoding in tied)
    if cp1252_in_tied and _strict_decodable(data, CP1252_CODEC):
        return CP1252_CODEC, len(tied)

    if len(tied) == 1:
        (only_encoding,) = tied
        if only_encoding in _CP1252_FAMILY:
            # The sole tied candidate is cp1252 itself, but it already
            # failed the strict-decodable check above: no viable decode.
            return None
        return only_encoding, 1

    return None


def _strict_decodable(data: bytes, encoding: str) -> bool:
    try:
        data.decode(encoding)
    except UnicodeDecodeError:
        return False
    return True


def _chaos_for(candidates: tuple[tuple[str, float], ...], encoding: str) -> float:
    """Return the chaos score ``charset_normalizer`` reported for ``encoding``.

    Matches by EXACT name, with one deliberate exception: when ``encoding``
    is the canonical cp1252 alias (:data:`CP1252_CODEC`), the lookup matches
    ANY :data:`_CP1252_FAMILY` member present in ``candidates``. This closes
    a real gap (#4962 review fold C): ``_select_from_tied`` always returns
    the canonical ``"cp1252"`` label as the selected encoding even when
    ``charset_normalizer`` itself reported the winning tie member under the
    OTHER family alias (``"windows-1252"``) -- an exact-name-only lookup then
    silently misses, falls back to chaos ``0.0``, and reports a near-max
    honest confidence with no basis. Every OTHER encoding this function is
    called with is always the verbatim string a candidate reported (the
    ``_select_from_tied`` non-cp1252 branch returns ``only_encoding`` straight
    off the candidates tuple), so exact matching stays correct there.
    """
    if encoding in _CP1252_FAMILY:
        for candidate_encoding, confidence in candidates:
            if candidate_encoding in _CP1252_FAMILY:
                return 1.0 - confidence
        return 0.0
    for candidate_encoding, confidence in candidates:
        if candidate_encoding == encoding:
            return 1.0 - confidence
    return 0.0


def _honest_confidence(chaos: float, tie_size: int) -> float:
    penalty = _TIE_EPSILON * tie_size
    raw = (1.0 - chaos) - penalty
    return max(0.0, min(raw, _MAX_HONEST_CONFIDENCE))


def _selected_result(
    data: bytes,
    encoding: str,
    tie_size: int,
    candidates: tuple[tuple[str, float], ...],
) -> EncodingRecoveryResult:
    chaos = _chaos_for(candidates, encoding)
    confidence = _honest_confidence(chaos, tie_size)
    text = data.decode(encoding)
    return EncodingRecoveryResult(
        text=text,
        source_encoding=encoding,
        confidence=confidence,
        ambiguous=False,
        candidates=candidates,
        normalization_applied=True,
        bypass_used=False,
    )


def _bypass_result(data: bytes, candidates: tuple[tuple[str, float], ...]) -> EncodingRecoveryResult:
    text = data.decode(CP1252_CODEC, errors=_LOSSLESS_CP1252_ERRORS)
    return EncodingRecoveryResult(
        text=text,
        source_encoding=CP1252_CODEC,
        confidence=_BYPASS_CONFIDENCE,
        ambiguous=False,
        candidates=candidates,
        normalization_applied=True,
        bypass_used=True,
    )


def _ambiguous_result(candidates: tuple[tuple[str, float], ...]) -> EncodingRecoveryResult:
    return EncodingRecoveryResult(
        text=None,
        source_encoding=None,
        confidence=0.0,
        ambiguous=True,
        candidates=candidates,
        normalization_applied=False,
        bypass_used=False,
    )
