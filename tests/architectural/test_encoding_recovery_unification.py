"""Fork-guard for the encoding-recovery unification (#4896 / WP04).

The mission's whole point is *one* canonical whole-file detector
(``charter.encoding_recovery.recover``) plus *one* shared cp1252-repair-codec
contract, consumed by every encoding-detection call site instead of each
call site vendoring its own ``charset_normalizer``/``from_bytes`` usage. See
``kitty-specs/charter-encoding-codepage-guard-01M3FFP1/contracts/detector-contract.md``
(Consumers table) and ``research.md`` R-5.

This test does **not** assert away ``specify_cli.text_sanitization``'s
byte-offset faithful repair algorithm: R-5 explicitly keeps that module's
per-invalid-byte repair, content-sniff binary guard, and CRLF preservation
in place -- only the cp1252 codec *name* converges to a single definition.
Replacing its algorithm with whole-file ``recover()`` would re-decode a
mostly-valid-UTF-8 file wholesale and reintroduce the exact corruption
#4896 was filed to stop (see ``test_stray_cp1252_byte_is_byte_faithfully_repaired``
below).

WP02 rewired ``src/charter/activation/_io.py`` and WP03 rewired
``src/specify_cli/acceptance/__init__.py`` off their former direct
``charset_normalizer``/``from_bytes`` usage and onto the single canonical
``charter.encoding_recovery.recover``. Both fork-guards below are now
unconditional hard asserts: reintroducing a second whole-file detector (a
direct ``charset_normalizer`` import in either module, or a bare ``cp1252``
repair literal in ``text_sanitization``) fails the build.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src"

_CHARTER_IO = _SRC / "charter" / "activation" / "_io.py"
_ACCEPTANCE_INIT = _SRC / "specify_cli" / "acceptance" / "__init__.py"
_ENCODING_RECOVERY = _SRC / "charter" / "encoding_recovery.py"
_TEXT_SANITIZATION = _SRC / "specify_cli" / "text_sanitization.py"


def _imports_charset_normalizer(path: Path) -> bool:
    """True if `path` imports the `charset_normalizer` package directly.

    AST-based (not a substring grep) so a comment or docstring mentioning
    the package name never produces a false positive.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(alias.name.split(".")[0] == "charset_normalizer" for alias in node.names):
            return True
        if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] == "charset_normalizer":
            return True
    return False


def _imports_specify_cli(path: Path) -> bool:
    """True if `path` imports anything under `specify_cli` (layer violation).

    ``charter`` sits below ``specify_cli`` in the enforced layer chain
    (``kernel <- charter <- {glossary, runtime, mission_runtime} <- specify_cli``,
    see project CLAUDE.md "Modularity SSOT"); charter code must never import
    upward from specify_cli.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(alias.name.split(".")[0] == "specify_cli" for alias in node.names):
            return True
        if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] == "specify_cli":
            return True
    return False


def test_charter_io_detection_funnels_through_recover() -> None:
    """`_io.py` must not import `charset_normalizer` directly.

    WP02 rewired this file onto ``charter.encoding_recovery.recover`` (#4962),
    so detection funnels through the single canonical detector. This is an
    unconditional hard fork-guard: reintroducing a direct ``charset_normalizer``
    import here (a second whole-file detector) fails the build.
    """
    assert not _imports_charset_normalizer(_CHARTER_IO)


def test_acceptance_init_detection_funnels_through_recover() -> None:
    """`acceptance/__init__.py` must not import `charset_normalizer` directly.

    WP03 rewired ``accept --normalize-encoding`` off its hand-rolled
    cp1252-then-latin-1 fallback and onto ``charter.encoding_recovery.recover``
    (#4968). This is an unconditional hard fork-guard against a future
    regression that adds a direct ``charset_normalizer`` import here instead of
    reusing the canonical detector.
    """
    assert not _imports_charset_normalizer(_ACCEPTANCE_INIT)


def test_charset_normalizer_has_a_single_importer_repo_wide() -> None:
    """Fork-guard, repo-wide: ``charset_normalizer`` may be imported by ONLY
    the canonical detector module (#4962 review fold D).

    The two guards above pin the specific historical fork sites
    (``_io.py`` / ``acceptance/__init__.py``, #4896/#4962/#4968) by name.
    This walks the WHOLE ``src/`` tree instead, so a future THIRD or FOURTH
    call site vendoring its own ``charset_normalizer``/``from_bytes`` usage
    fails the build too -- not just a regression at one of the two
    already-named files. Keep the per-file guards (a clearer, more specific
    failure message for the two known-sensitive sites) alongside this one.
    """
    importers = sorted(path.relative_to(_REPO_ROOT).as_posix() for path in _SRC.rglob("*.py") if _imports_charset_normalizer(path))
    expected = [_ENCODING_RECOVERY.relative_to(_REPO_ROOT).as_posix()]
    assert importers == expected, f"charset_normalizer must be imported ONLY by {expected[0]} -- found importers: {importers}"


def test_text_sanitization_imports_shared_cp1252_codec_symbol() -> None:
    """`text_sanitization` must consume the shared codec constant, not a local literal."""
    tree = ast.parse(_TEXT_SANITIZATION.read_text(encoding="utf-8"), filename=str(_TEXT_SANITIZATION))
    imports_shared_constant = any(
        isinstance(node, ast.ImportFrom) and node.module == "charter.encoding_recovery" and any(alias.name == "CP1252_CODEC" for alias in node.names)
        for node in ast.walk(tree)
    )
    assert imports_shared_constant, "text_sanitization.py must import CP1252_CODEC from charter.encoding_recovery"


def test_text_sanitization_has_no_local_cp1252_repair_codec_literal() -> None:
    """No bare `"cp1252"` string literal may define the repair codec locally.

    Only the shared `charter.encoding_recovery.CP1252_CODEC` constant may
    carry that value; a reintroduced local literal would silently fork the
    codec definition again.
    """
    tree = ast.parse(_TEXT_SANITIZATION.read_text(encoding="utf-8"), filename=str(_TEXT_SANITIZATION))
    literal_cp1252_strings = [
        node for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.lower() in {"cp1252", "windows-1252"}
    ]
    assert literal_cp1252_strings == [], "text_sanitization.py must not define its own 'cp1252' literal -- import CP1252_CODEC instead"


def test_encoding_recovery_module_does_not_import_specify_cli() -> None:
    """Charter-layer code must never import upward from specify_cli.

    Note: ``charter.encoding_recovery`` runs ``codecs.register_error(...)``
    at import time (WP01) -- that is an intentional, allowed module-level
    side effect (registering the lossless cp1252 error handler once) and is
    not what this test guards against. This test only checks import
    *direction*, never "no import-time side effects."
    """
    assert not _imports_specify_cli(_ENCODING_RECOVERY)


def test_stray_cp1252_byte_is_byte_faithfully_repaired(tmp_path: Path) -> None:
    """#4896 non-regression: byte-offset repair, not whole-file re-decode.

    A mostly-valid-UTF-8 file with exactly one stray cp1252 byte (a 0x92
    "right single quotation mark" apostrophe, never valid as a UTF-8
    continuation/lead byte in this position) must come out with:
      - every valid multibyte UTF-8 sequence untouched,
      - CRLF line endings preserved,
      - only the stray byte repaired.

    Routing this through whole-file ``charter.encoding_recovery.recover()``
    would re-decode the *entire* file under a single guessed codec, mangling
    the valid multibyte UTF-8 content elsewhere in the file -- that is
    precisely the #4896 regression this test exists to catch.
    """
    from specify_cli.text_sanitization import sanitize_file

    # "café" (valid UTF-8 for the é) + a stray cp1252 apostrophe (0x92) in
    # place of a real apostrophe + CRLF line endings throughout.
    valid_multibyte = "café résumé naïve".encode()
    stray_byte = b"\x92"  # cp1252 RIGHT SINGLE QUOTATION MARK, invalid as UTF-8 here
    raw = valid_multibyte + b" don" + stray_byte + b"t stop\r\nsecond line: caf\xc3\xa9\r\n"

    target = tmp_path / "sample.md"
    target.write_bytes(raw)

    modified, error = sanitize_file(target, backup=False)

    assert error is None
    assert modified is True

    result_bytes = target.read_bytes()
    result_text = result_bytes.decode("utf-8")

    # Valid multibyte UTF-8 content survives untouched.
    assert "café" in result_text
    assert "résumé" in result_text
    assert "naïve" in result_text
    # The stray byte was repaired to its cp1252-decoded character (U+2019)
    # and then run through the module's own smart-quote normalization
    # (PROBLEMATIC_CHARS maps U+2019 -> "'"), never dropped or replaced
    # with U+FFFD.
    assert "don't stop" in result_text
    # CRLF line endings are preserved byte-for-byte, not collapsed to LF.
    assert b"\r\n" in result_bytes
    assert result_text.count("\r\n") == 2
