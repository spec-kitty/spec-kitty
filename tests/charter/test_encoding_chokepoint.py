"""Regression tests for the charter encoding chokepoint (FR-016 – FR-021).

Tests:
  - Pure UTF-8 ingest: confidence=1.0, normalization_applied=False.
  - CP-1252 ingest: normalization_applied=True, provenance record present.
  - UTF-8-BOM file: recognized and stripped.
  - Ambiguous content without --unsafe: raises CharterEncodingError(AMBIGUOUS).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from charter.activation._diagnostics import CharterEncodingDiagnostic
from charter.activation._io import CharterContent, CharterEncodingError, load_charter_bytes, load_charter_file

pytestmark = pytest.mark.fast

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_UTF8_TEXT = "Hello, world! This is a spec-kitty charter.\n"
_UTF8_BYTES = _UTF8_TEXT.encode("utf-8")

# A byte sequence that is NOT valid UTF-8 but is valid cp1252.
# 0x80–0x9F are windows-1252 printable characters, invalid in strict UTF-8.
#
# WP02 note: this must be long/varied enough for charset_normalizer to
# actually offer cp1252 as a tied candidate (the canonical detector's
# cp1252 tie-break only fires when cp1252 IS in the tied set -- a short
# fixture like a bare "Café" often has charset_normalizer omit cp1252 from
# its ranking entirely, which is exactly the upstream bug WP01 built the
# tie-break detector to route around). This is the mission's canonical
# SENTINEL fixture (data-model.md), proven to tie cp1252 reliably.
_CP1252_TEXT = "# Team Charter\n\n" + "Tests must pass before merge.\n" * 10 + "We don’t ship on Fridays — the “freeze” rule. Owner: José Peña, São Paulo.\n"
_CP1252_BYTES = _CP1252_TEXT.encode("cp1252")

# UTF-8 BOM prefix + UTF-8 content.
_BOM_PREFIX = b"\xef\xbb\xbf"
_BOM_BYTES = _BOM_PREFIX + _UTF8_BYTES

# Mixed-content that is genuinely ambiguous: a byte sequence whose first half
# suggests one encoding and second half another, making single-encoding
# detection unreliable and charset-normalizer likely to return low confidence.
# We use a crafted sequence of cp1252 bytes interspersed with control codes
# that makes detection unreliable.  In practice we rely on the fixture
# producing a UnicodeDecodeError for UTF-8 AND low-confidence from c-n.
# We use a known-bad Latin-1/cp1252 mixed sequence here.
_AMBIGUOUS_BYTES = (
    b"\xff\xfe"  # UTF-16-LE BOM — but then continued as cp1252 content
    + b"\x00" * 30  # null bytes that confuse the detector
    + b"\x80\x81\x82\x83\x84\x85\x86\x87\x88\x89"  # cp1252 control region
    b"\x00\x00\x00\x00\x00"
    b"\xef\xbf\xbd\x00\xff"  # UTF-8 replacement char embedded, then invalid byte
)


def _read_provenance(path: Path) -> list[dict[str, object]]:
    """Read all JSONL provenance records from a file."""
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


# ---------------------------------------------------------------------------
# Pure UTF-8 tests
# ---------------------------------------------------------------------------


def test_pure_utf8_ingest_records_provenance_without_normalization(tmp_path: Path) -> None:
    """Pure UTF-8 charter file is ingested with confidence=1.0 and
    normalization_applied=False.  A provenance record is written.
    """
    charter_file = tmp_path / "charter.md"
    charter_file.write_bytes(_UTF8_BYTES)

    # Patch provenance routing to write into tmp_path so tests don't pollute CWD.
    import charter.activation._io as _io_mod

    original_route = _io_mod._route_provenance_path

    def _patched_route(source_path: Path | None) -> Path:
        return tmp_path / "provenance.jsonl"

    _io_mod._route_provenance_path = _patched_route
    try:
        content = load_charter_file(charter_file)
    finally:
        _io_mod._route_provenance_path = original_route

    assert isinstance(content, CharterContent)
    assert content.text == _UTF8_TEXT
    assert content.source_encoding == "utf-8"
    assert content.confidence == 1.0
    assert content.normalization_applied is False
    assert content.source_path == charter_file

    records = _read_provenance(tmp_path / "provenance.jsonl")
    assert len(records) == 1
    assert records[0]["source_encoding"] == "utf-8"
    assert records[0]["normalization_applied"] is False
    assert records[0]["bypass_used"] is False


# ---------------------------------------------------------------------------
# CP-1252 tests
# ---------------------------------------------------------------------------


def test_cp1252_ingest_normalizes_and_records_provenance(tmp_path: Path) -> None:
    """CP-1252-encoded file is detected, normalized to UTF-8, and provenance
    record includes normalization_applied=True.
    """
    charter_file = tmp_path / "charter.md"
    charter_file.write_bytes(_CP1252_BYTES)

    import charter.activation._io as _io_mod

    original_route = _io_mod._route_provenance_path

    def _patched_route(source_path: Path | None) -> Path:
        return tmp_path / "provenance.jsonl"

    _io_mod._route_provenance_path = _patched_route
    try:
        content = load_charter_file(charter_file)
    finally:
        _io_mod._route_provenance_path = original_route

    assert isinstance(content, CharterContent)
    assert content.normalization_applied is True
    # The decoded text must round-trip byte-exactly (detector-contract.md
    # guarantee #4: cp1252 tie-break round-trips SENTINEL exactly).
    assert content.text == _CP1252_TEXT
    assert content.source_encoding == "cp1252"
    # A tie-broken single-byte pick must report an honest LOWERED
    # confidence, never a bare 1.0 (detector-contract.md guarantee #3).
    assert 0.0 < content.confidence < 1.0

    records = _read_provenance(tmp_path / "provenance.jsonl")
    assert len(records) == 1
    assert records[0]["normalization_applied"] is True
    assert records[0]["bypass_used"] is False


# ---------------------------------------------------------------------------
# BOM sniff tests
# ---------------------------------------------------------------------------


def test_bom_sniff_recognized(tmp_path: Path) -> None:
    """UTF-8-BOM file is recognized; BOM is stripped; normalization_applied=True."""
    charter_file = tmp_path / "charter.md"
    charter_file.write_bytes(_BOM_BYTES)

    import charter.activation._io as _io_mod

    original_route = _io_mod._route_provenance_path

    def _patched_route(source_path: Path | None) -> Path:
        return tmp_path / "provenance.jsonl"

    _io_mod._route_provenance_path = _patched_route
    try:
        content = load_charter_file(charter_file)
    finally:
        _io_mod._route_provenance_path = original_route

    assert isinstance(content, CharterContent)
    assert content.source_encoding == "utf-8-sig"
    assert content.normalization_applied is True
    # BOM must be stripped from the text.
    assert not content.text.startswith("﻿")
    assert content.text == _UTF8_TEXT
    assert content.confidence == 1.0

    records = _read_provenance(tmp_path / "provenance.jsonl")
    assert len(records) == 1
    assert records[0]["source_encoding"] == "utf-8-sig"
    assert records[0]["normalization_applied"] is True


# ---------------------------------------------------------------------------
# Ambiguous content / CharterEncodingError tests
# ---------------------------------------------------------------------------


def test_ambiguous_content_raises_without_unsafe(tmp_path: Path) -> None:
    """A genuinely ambiguous byte sequence raises CharterEncodingError with
    the AMBIGUOUS diagnostic code when unsafe=False (the default).

    We use load_charter_bytes() with an ambiguous payload so we don't need a
    file on disk.  The test asserts that:
    - A CharterEncodingError is raised.
    - Its code is CharterEncodingDiagnostic.AMBIGUOUS.
    - The error body contains the ERROR: prefix.
    - No provenance record is written (failure path is not audit-worthy).

    WP02 tightening (out-of-map edit): the pre-WP02 chokepoint used
    charset_normalizer's raw ``.best()`` pick gated by a (now-retired) >=0.85
    confidence threshold, so this fixture's outcome depended on
    charset_normalizer internals and the test hedged both directions via
    ``except AssertionError: return``. Under the canonical tie-break
    detector (WP01), this exact fixture is deterministic: it contains an
    undefined cp1252 byte (0x81) and charset_normalizer returns zero
    candidates for it, so it is unconditionally ambiguous. The hedge is
    removed.
    """
    # A mix of Latin-1/cp1252 control-region bytes around null bytes,
    # including 0x81 (a cp1252-undefined byte -- the "0x81 fixture"
    # ambiguity class per charter.encoding_recovery's module docs), that
    # charset_normalizer cannot resolve to any candidate.
    ambiguous = b"\x80" + b"\x00" * 10 + b"\x81" + b"\x00" * 10 + b"\x9f" + b"\x00" * 5

    import charter.activation._io as _io_mod

    original_route = _io_mod._route_provenance_path
    provenance_file = tmp_path / "provenance.jsonl"

    def _patched_route(source_path: Path | None) -> Path:
        return provenance_file

    _io_mod._route_provenance_path = _patched_route
    try:
        with pytest.raises(CharterEncodingError) as exc_info:
            load_charter_bytes(ambiguous, origin="test:ambiguous", unsafe=False)
    finally:
        _io_mod._route_provenance_path = original_route

    assert exc_info.value.code == CharterEncodingDiagnostic.AMBIGUOUS
    assert "ERROR: CHARTER_ENCODING_AMBIGUOUS" in exc_info.value.body

    # Provenance must NOT be written for the failure path.
    records = _read_provenance(provenance_file)
    assert records == [], "Provenance must not be written when encoding detection fails"
