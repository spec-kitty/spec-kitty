"""Unit tests for :mod:`kernel.text_decode` (#4940, #4998).

Pins the "provable encodings only" decode rule and the newline normaliser
that ``charter.encoding_recovery`` and ``charter.hasher`` delegate to.
"""

from __future__ import annotations

import pytest

from kernel.text_decode import decode_unambiguous, detect_bom, normalize_newlines

pytestmark = pytest.mark.fast


# --------------------------------------------------------------------------- #
# decode_unambiguous — provable cases
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "text",
    ["hello world", "José", "São Paulo — naïve café"],
    ids=["ascii", "non-ascii", "mixed-non-ascii"],
)
def test_strict_utf8_decodes(text: str) -> None:
    result = decode_unambiguous(text.encode("utf-8"))

    assert result == (text, "utf-8")


def test_utf8_bom_decodes_without_bom_char() -> None:
    data = b"\xef\xbb\xbf" + b"hello"

    result = decode_unambiguous(data)

    assert result == ("hello", "utf-8-sig")
    assert result is not None
    assert "﻿" not in result[0]


def test_utf16_le_bom_decodes() -> None:
    data = "﻿{}".encode("utf-16-le")

    result = decode_unambiguous(data)

    assert result == ("{}", "utf-16-le")


def test_utf16_be_bom_decodes() -> None:
    data = "﻿{}".encode("utf-16-be")

    result = decode_unambiguous(data)

    assert result == ("{}", "utf-16-be")


def test_utf32_le_bom_decodes_and_is_not_utf16() -> None:
    """The UTF-32-LE BOM (`FF FE 00 00`) starts with the UTF-16-LE BOM
    (`FF FE`) -- it must resolve as utf-32-le, never utf-16-le."""
    data = "﻿{}".encode("utf-32-le")

    result = decode_unambiguous(data)

    assert result == ("{}", "utf-32-le")


def test_utf32_be_bom_decodes() -> None:
    data = "﻿{}".encode("utf-32-be")

    result = decode_unambiguous(data)

    assert result == ("{}", "utf-32-be")


def test_empty_bytes_decode_as_utf8() -> None:
    assert decode_unambiguous(b"") == ("", "utf-8")


# --------------------------------------------------------------------------- #
# decode_unambiguous — unprovable cases
# --------------------------------------------------------------------------- #


def test_cp1252_bytes_are_not_provable() -> None:
    data = b'{"env":{"OWNER":"Jos\xe9"}}'

    assert decode_unambiguous(data) is None


def test_bom_followed_by_undecodable_bytes_returns_none() -> None:
    """A BOM match followed by bytes that fail that codec is not proof of
    anything else -- it must return None, not fall through or raise."""
    data = b"\xff\xfe" + b"\x00\xd8"  # UTF-16-LE BOM + lone surrogate

    assert decode_unambiguous(data) is None


# --------------------------------------------------------------------------- #
# detect_bom
# --------------------------------------------------------------------------- #


def test_detect_bom_returns_none_for_plain_utf8() -> None:
    assert detect_bom(b"hello") is None


@pytest.mark.parametrize(
    ("prefix", "expected"),
    [
        (b"\x00\x00\xfe\xff", ("utf-32", "utf-32-be")),
        # Must match before the UTF-16-LE BOM it starts with.
        (b"\xff\xfe\x00\x00", ("utf-32", "utf-32-le")),
        (b"\xef\xbb\xbf", ("utf-8-sig", "utf-8-sig")),
        (b"\xff\xfe", ("utf-16", "utf-16-le")),
        (b"\xfe\xff", ("utf-16", "utf-16-be")),
    ],
)
def test_detect_bom_recognises_each_bom(prefix: bytes, expected: tuple[str, str]) -> None:
    assert detect_bom(prefix + b"rest") == expected


# --------------------------------------------------------------------------- #
# normalize_newlines
# --------------------------------------------------------------------------- #


def test_normalize_newlines_converts_crlf_and_cr() -> None:
    assert normalize_newlines("a\r\nb\rc\n") == "a\nb\nc\n"


def test_normalize_newlines_mixed() -> None:
    assert normalize_newlines("one\r\ntwo\rthree\nfour") == "one\ntwo\nthree\nfour"


def test_normalize_newlines_noop_on_lf_only() -> None:
    text = "a\nb\nc\n"

    assert normalize_newlines(text) == text


def test_normalize_newlines_preserves_bom_char() -> None:
    assert normalize_newlines("﻿x\r\n") == "﻿x\n"


def test_normalize_newlines_preserves_leading_trailing_whitespace() -> None:
    assert normalize_newlines("  \r\n  a  \r\n  ") == "  \n  a  \n  "
