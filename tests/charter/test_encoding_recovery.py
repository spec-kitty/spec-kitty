"""Tests for the canonical whole-file encoding-recovery detector (#4962, WP01).

Covers the "Hardened acceptance" list from
``kitty-specs/charter-encoding-codepage-guard-01M3FFP1/tasks/WP01-canonical-encoding-detector.md``:
whole-file round-trip, cp1252-over-cp1250 tie-break, the 0x81 ambiguity
fixture, BOM/strict-UTF-8 confidence, single-pass detection, determinism,
and the lossless ``unsafe`` bypass.
"""

from __future__ import annotations

import charset_normalizer
import pytest

from charter.encoding_recovery import (
    _CP1252_UNDEFINED_BYTES,
    _MAX_HONEST_CONFIDENCE,
    _TIE_EPSILON,
    EncodingRecoveryResult,
    _honest_confidence,
    recover,
)

# Deliberately contains ñ (0xF1 in cp1252) and ã (0xE3 in cp1252) so that a
# wrong-code-page decode (e.g. cp1250, which maps those byte values to
# different characters) fails a full string equality check.
SENTINEL = "# Team Charter\n\n" + "Tests must pass before merge.\n" * 10 + "We don’t ship on Fridays — the “freeze” rule. Owner: José Peña, São Paulo.\n"

# The five byte values Windows-1252 leaves undefined. On their own they are
# not strict-cp1252-decodable and, per fixture exploration, charset_normalizer
# returns multiple tied non-cp1252 candidates for them — the canonical
# "ambiguous, no viable cp1252 fallback" case.
UNDEFINED_CP1252_FIXTURE = bytes(sorted(_CP1252_UNDEFINED_BYTES))


def test_sentinel_cp1252_round_trips_byte_exactly() -> None:
    result = recover(SENTINEL.encode("cp1252"))

    assert result.text == SENTINEL
    assert result.ambiguous is False


def test_sentinel_ties_cp1252_over_cp1250() -> None:
    data = SENTINEL.encode("cp1252")

    # Sanity-check the fixture actually produces a real tie in the
    # underlying detector, otherwise this test would not exercise the
    # tie-break logic at all.
    matches = charset_normalizer.from_bytes(data)
    chaoses = {match.encoding: match.chaos for match in matches}
    assert "cp1250" in chaoses
    assert "cp1252" in chaoses
    assert abs(chaoses["cp1250"] - chaoses["cp1252"]) <= _TIE_EPSILON

    result = recover(data)

    assert result.source_encoding == "cp1252"
    assert 0.0 < result.confidence < 1.0
    assert result.ambiguous is False
    assert result.bypass_used is False


def test_undefined_cp1252_bytes_are_ambiguous() -> None:
    result = recover(UNDEFINED_CP1252_FIXTURE)

    assert result.ambiguous is True
    assert result.text is None
    assert result.source_encoding is None
    assert result.bypass_used is False


def test_bom_utf8_sig_is_full_confidence_and_normalized() -> None:
    data = b"\xef\xbb\xbf" + b"hello world"

    result = recover(data)

    assert result.text == "hello world"
    assert result.source_encoding == "utf-8-sig"
    assert result.confidence == 1.0
    assert result.normalization_applied is True
    assert result.ambiguous is False


def test_bom_utf16_le_is_full_confidence() -> None:
    data = b"\xff\xfe" + "hello".encode("utf-16-le")

    result = recover(data)

    assert result.text == "hello"
    assert result.source_encoding == "utf-16-le"
    assert result.confidence == 1.0
    assert result.normalization_applied is True


def test_bom_utf16_be_is_full_confidence() -> None:
    data = b"\xfe\xff" + "hello".encode("utf-16-be")

    result = recover(data)

    assert result.text == "hello"
    assert result.source_encoding == "utf-16-be"
    assert result.confidence == 1.0
    assert result.normalization_applied is True


def test_strict_utf8_is_full_confidence_and_not_normalized() -> None:
    data = "café — plain utf-8, no BOM".encode()

    result = recover(data)

    assert result.text == "café — plain utf-8, no BOM"
    assert result.source_encoding == "utf-8"
    assert result.confidence == 1.0
    assert result.normalization_applied is False


def test_single_pass_detection(monkeypatch: pytest.MonkeyPatch) -> None:
    call_count = 0
    real_from_bytes = charset_normalizer.from_bytes

    def counting_from_bytes(data: bytes):  # type: ignore[no-untyped-def]
        nonlocal call_count
        call_count += 1
        return real_from_bytes(data)

    monkeypatch.setattr(charset_normalizer, "from_bytes", counting_from_bytes)

    recover(SENTINEL.encode("cp1252"))

    assert call_count == 1


def test_determinism_across_repeated_calls() -> None:
    data = SENTINEL.encode("cp1252")

    results = [recover(data) for _ in range(100)]

    assert all(result == results[0] for result in results)


def test_unsafe_bypass_is_lossless_with_no_replacement_character() -> None:
    result = recover(UNDEFINED_CP1252_FIXTURE, unsafe=True)

    assert result.bypass_used is True
    assert result.ambiguous is False
    assert result.text is not None
    assert "�" not in result.text
    assert result.source_encoding == "cp1252"


def test_unsafe_bypass_preserves_byte_count() -> None:
    result = recover(UNDEFINED_CP1252_FIXTURE, unsafe=True)

    assert result.text is not None
    assert len(result.text) == len(UNDEFINED_CP1252_FIXTURE)
    for byte, char in zip(UNDEFINED_CP1252_FIXTURE, result.text, strict=True):
        assert ord(char) == byte


def test_result_is_frozen_dataclass() -> None:
    result = recover(b"plain ascii")

    assert isinstance(result, EncodingRecoveryResult)
    with pytest.raises(AttributeError):
        result.text = "mutated"  # type: ignore[misc]


def test_candidates_populated_only_on_single_byte_path() -> None:
    utf8_result = recover(b"plain ascii")
    assert utf8_result.candidates == ()

    tie_result = recover(SENTINEL.encode("cp1252"))
    assert len(tie_result.candidates) > 0


def test_chaos_lookup_matches_windows_1252_alias_when_tie_reports_that_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#4962 review fold C: the chaos lookup must be family-wide, not exact-name.

    ``_select_from_tied`` always returns the canonical ``CP1252_CODEC``
    label (``"cp1252"``) once a cp1252-family tie member strict-decodes --
    even when ``charset_normalizer`` itself reported that winning candidate
    under the OTHER family alias (``"windows-1252"``). Before the fold,
    ``_chaos_for`` looked up the exact string ``"cp1252"`` in the candidates
    tuple; when only ``"windows-1252"`` is present, that lookup silently
    misses and falls back to chaos ``0.0`` -- reporting a confidence right at
    the honest ceiling (:data:`_MAX_HONEST_CONFIDENCE`) with NO basis in the
    real detection. The family-aware lookup must instead recover the REAL,
    non-trivial chaos ``charset_normalizer`` reported for that alias.
    """
    data = SENTINEL.encode("cp1252")

    class _FakeMatch:
        def __init__(self, encoding: str, chaos: float) -> None:
            self.encoding = encoding
            self.chaos = chaos

    # A deliberately non-trivial chaos: distinguishable from the buggy
    # fallback's chaos 0.0 (which would report confidence == _MAX_HONEST_CONFIDENCE).
    fake_chaos = 0.2
    monkeypatch.setattr(
        charset_normalizer,
        "from_bytes",
        lambda _data: [_FakeMatch("windows-1252", fake_chaos)],
    )

    result = recover(data)

    assert result.ambiguous is False
    # _select_from_tied always reports the canonical alias, regardless of
    # which family member charset_normalizer named.
    assert result.source_encoding == "cp1252"
    # Non-vacuous: the buggy exact-name lookup reports chaos 0.0 here, i.e.
    # confidence == _MAX_HONEST_CONFIDENCE (0.98) -- clearly distinct from the
    # honest value derived from the REAL 0.2 chaos this test injected.
    expected_confidence = _honest_confidence(fake_chaos, tie_size=1)
    assert expected_confidence < _MAX_HONEST_CONFIDENCE - 0.05, "fixture chaos must be distinguishable from the buggy fallback"
    assert result.confidence == pytest.approx(expected_confidence)
