"""Regression tests for the --unsafe bypass on the encoding chokepoint (FR-019).

Tests:
  - unsafe=True succeeds on ambiguous input that would otherwise raise.
  - bypass_used=True is recorded in the provenance record.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from charter.activation._io import CharterContent, CharterEncodingError, load_charter_bytes

pytestmark = pytest.mark.fast


# A byte sequence that is NOT valid strict UTF-8.
# Using a compact but reliable non-UTF-8 byte sequence:
# 0xe9 is 'é' in cp1252 but starts a 3-byte sequence in UTF-8 that
# requires continuation bytes 0x80-0xBF — the following content does not
# provide valid continuation bytes.
_NON_UTF8_BYTES = b"Caf\xe9 au lait"  # cp1252 'é', invalid in strict UTF-8


def _read_provenance(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def _patch_provenance_route(tmp_path: Path):
    """Context manager that patches provenance routing to write into tmp_path."""
    import charter.activation._io as _io_mod

    original = _io_mod._route_provenance_path
    provenance_file = tmp_path / "provenance.jsonl"

    def _patched(source_path: Path | None) -> Path:
        return provenance_file

    _io_mod._route_provenance_path = _patched
    return _io_mod, original, provenance_file


def test_unsafe_bypass_succeeds_on_non_utf8_input(tmp_path: Path) -> None:
    """load_charter_bytes with unsafe=True succeeds on a byte sequence that
    is not valid UTF-8, returning a CharterContent with normalization_applied=True.
    """
    _io_mod, original, _ = _patch_provenance_route(tmp_path)
    try:
        content = load_charter_bytes(_NON_UTF8_BYTES, origin="test:cp1252", unsafe=True)
    finally:
        _io_mod._route_provenance_path = original

    assert isinstance(content, CharterContent)
    assert content.normalization_applied is True
    # The output text should contain something reasonable (no raw bytes).
    assert isinstance(content.text, str)


def test_unsafe_bypass_records_bypass_used_flag(tmp_path: Path) -> None:
    """When unsafe=True is used, the provenance record must have bypass_used=True.

    This test verifies that the audit trail correctly records bypass usage so
    operators can identify files that were ingested with the override active.
    """
    _io_mod, original, provenance_file = _patch_provenance_route(tmp_path)
    try:
        content = load_charter_bytes(_NON_UTF8_BYTES, origin="test:cp1252", unsafe=True)
    finally:
        _io_mod._route_provenance_path = original

    assert isinstance(content, CharterContent)

    records = _read_provenance(provenance_file)
    assert len(records) >= 1, "Expected at least one provenance record"

    # The last record corresponds to this ingest.
    record = records[-1]
    assert record["bypass_used"] is True, f"Expected bypass_used=True in provenance record, got: {record}"


def test_unsafe_false_raises_on_non_utf8_input_below_threshold(tmp_path: Path) -> None:
    """Without --unsafe, a byte sequence that fails UTF-8 decode and has no
    cp1252-viable tie candidate raises CharterEncodingError.

    This is the complementary test to the bypass tests: it verifies the
    non-bypass path fails closed.  We use the same non-UTF-8 bytes but
    explicitly pass unsafe=False.

    WP02 tightening (out-of-map edit): the pre-WP02 chokepoint's outcome for
    this fixture depended on charset_normalizer's raw ``.best()`` confidence
    crossing the (now-retired) 0.85 threshold, so the test hedged both
    outcomes. Under the canonical tie-break detector (WP01), this fixture
    is deterministic: charset_normalizer never offers cp1252 as a candidate
    for this short byte sequence (confirmed empirically), so it is
    unconditionally ambiguous when unsafe=False. The hedge is removed.
    """
    _io_mod, original, provenance_file = _patch_provenance_route(tmp_path)
    try:
        with pytest.raises(CharterEncodingError) as excinfo:
            load_charter_bytes(_NON_UTF8_BYTES, origin="test:cp1252", unsafe=False)
    finally:
        _io_mod._route_provenance_path = original

    from charter.activation._diagnostics import CharterEncodingDiagnostic

    assert excinfo.value.code == CharterEncodingDiagnostic.AMBIGUOUS
    assert "ERROR: CHARTER_ENCODING_AMBIGUOUS" in excinfo.value.body

    records = _read_provenance(provenance_file)
    assert records == [], "Provenance must not be written when encoding detection fails"
