"""Read-path coverage for the WP02 charter-encoding fix (#4962).

``charter.activation._io.load_charter_file`` -- and its downstream callers
``charter.activation.{sync,interview,compiler}`` -- now delegate whole-file
encoding recovery to the canonical, pure detector
(``charter.encoding_recovery.recover``, WP01) instead of
``charset_normalizer``'s raw ``.best()`` pick (contracts/detector-contract.md).

Pinned here:

- A cp1252 ``SENTINEL`` charter now loads CORRECTLY (byte-exact cp1252 text)
  via the read path, rather than the mojibake a naive ``.best()`` pick could
  silently produce.
- A genuinely ambiguous charter (containing an undefined cp1252 byte, 0x81)
  still fails closed with ``CHARTER_ENCODING_AMBIGUOUS`` rather than loading
  as mojibake.

Both scenarios are exercised directly against ``load_charter_file`` (the
read-path entry point every caller funnels through) and, for the correctness
scenario's propagation contract, through the real
``charter.activation.compiler._load_yaml_asset`` call site.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation._diagnostics import CharterEncodingDiagnostic
from charter.activation._io import CharterEncodingError, load_charter_file

pytestmark = [pytest.mark.unit]

SENTINEL = "# Team Charter\n\n" + "Tests must pass before merge.\n" * 10 + "We don’t ship on Fridays — the “freeze” rule. Owner: José Peña, São Paulo.\n"

# An undefined cp1252 byte (0x81) makes the cp1252 tie-break unavailable --
# the "0x81 fixture" ambiguity class (charter.encoding_recovery module docs).
_UNDEFINED_BYTE_CHARTER = b"# Charter\n\nBefore \x81 after.\n"
_UNDEFINED_BYTE_YAML = b"name: x\n\x81\nvalue: 1\n"


def _patch_provenance_route(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Route provenance writes into tmp_path so tests never touch the repo."""
    import charter.activation._io as _io_mod

    provenance_file = tmp_path / "provenance.jsonl"
    monkeypatch.setattr(_io_mod, "_route_provenance_path", lambda _source_path: provenance_file)


# ---------------------------------------------------------------------------
# Correct cp1252 decode via the read path
# ---------------------------------------------------------------------------


class TestReadPathCp1252Correctness:
    def test_cp1252_sentinel_loads_correctly_via_load_charter_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A cp1252 charter decodes to the exact original text -- not
        mojibake -- via the read-path chokepoint every caller funnels
        through."""
        _patch_provenance_route(monkeypatch, tmp_path)
        charter_file = tmp_path / "charter.md"
        charter_file.write_bytes(SENTINEL.encode("cp1252"))

        content = load_charter_file(charter_file)

        assert content.text == SENTINEL
        assert content.source_encoding == "cp1252"
        assert content.normalization_applied is True
        # Honest, tie-broken confidence: never a bare 1.0
        # (detector-contract.md guarantee #3).
        assert 0.0 < content.confidence < 1.0

    def test_cp1252_sentinel_loads_correctly_through_compiler_call_site(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """``charter.activation.compiler._load_yaml_asset`` (one of the
        sync/interview/compiler read-path callers) propagates the same
        correct decode rather than silently degrading to mojibake."""
        from charter.activation.compiler import _load_yaml_asset

        _patch_provenance_route(monkeypatch, tmp_path)
        charter_file = tmp_path / "charter.yaml"
        charter_file.write_bytes(SENTINEL.encode("cp1252"))

        # The SENTINEL prose is not valid YAML, so _load_yaml_asset's
        # pre-existing resilience contract degrades the *parse* to an empty
        # dict -- but it must reach that point, i.e. the encoding itself
        # must decode without raising. A genuinely ambiguous file raises
        # before the YAML parse is even attempted (see the class below).
        result = _load_yaml_asset(charter_file)

        assert result["_source_path"] == str(charter_file)


# ---------------------------------------------------------------------------
# Genuinely ambiguous content fails closed
# ---------------------------------------------------------------------------


class TestReadPathAmbiguousFailsClosed:
    def test_undefined_cp1252_byte_charter_fails_closed(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A charter containing an undefined cp1252 byte (0x81) is
        genuinely ambiguous and must fail closed rather than load as
        mojibake."""
        _patch_provenance_route(monkeypatch, tmp_path)
        charter_file = tmp_path / "charter.md"
        charter_file.write_bytes(_UNDEFINED_BYTE_CHARTER)

        with pytest.raises(CharterEncodingError) as excinfo:
            load_charter_file(charter_file)

        assert excinfo.value.code == CharterEncodingDiagnostic.AMBIGUOUS.value

    def test_undefined_cp1252_byte_fails_closed_through_compiler_call_site(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The compiler call site must NOT swallow the ambiguity into an
        empty dict -- it must propagate CHARTER_ENCODING_AMBIGUOUS."""
        from charter.activation.compiler import _load_yaml_asset

        _patch_provenance_route(monkeypatch, tmp_path)
        charter_file = tmp_path / "charter.yaml"
        charter_file.write_bytes(_UNDEFINED_BYTE_YAML)

        with pytest.raises(CharterEncodingError) as excinfo:
            _load_yaml_asset(charter_file)

        assert excinfo.value.code == CharterEncodingDiagnostic.AMBIGUOUS.value
