"""``recover()`` shares its BOM/strict-UTF-8 steps with ``kernel.text_decode`` (#4940).

Pins two things:

1. The UTF-32-LE BOM correction: ``recover()`` used to mis-decode a
   UTF-32-LE-BOM input as UTF-16-LE (with embedded NUL bytes), because the
   UTF-32-LE BOM (``FF FE 00 00``) starts with the UTF-16-LE BOM
   (``FF FE``) and the old ``_recover_from_bom`` only checked UTF-16
   prefixes. A BOM is proof of encoding (DIRECTIVE_044's "provable
   encodings" policy).
2. Agreement with the kernel rule: ``recover()``'s BOM and strict-UTF-8
   results equal ``kernel.text_decode.decode_unambiguous``'s for the same
   inputs, and a BOM followed by undecodable bytes still raises
   ``UnicodeDecodeError`` from ``recover()`` (never silently falls through
   to single-byte guessing).
"""

from __future__ import annotations

import pytest

from charter.encoding_recovery import recover
from kernel.text_decode import decode_unambiguous

pytestmark = pytest.mark.fast


def test_utf32_le_bom_is_reported_as_utf32_le_not_utf16_le() -> None:
    data = "﻿{}".encode("utf-32-le")

    result = recover(data)

    assert result.source_encoding == "utf-32-le"
    assert result.text == "{}"
    assert "\x00" not in result.text


def test_utf32_be_bom_is_reported_as_utf32_be() -> None:
    data = "﻿{}".encode("utf-32-be")

    result = recover(data)

    assert result.source_encoding == "utf-32-be"
    assert result.text == "{}"


def test_bom_followed_by_undecodable_bytes_still_raises() -> None:
    """`recover(b"\\xff\\xfe\\x00\\xd8")` raises `UnicodeDecodeError`; it must
    NOT silently fall through to strict-UTF-8/cp1252 guessing. Only
    `decode_unambiguous` returns `None` for this."""
    data = b"\xff\xfe" + b"\x00\xd8"  # UTF-16-LE BOM + lone surrogate

    assert decode_unambiguous(data) is None

    with pytest.raises(UnicodeDecodeError):
        recover(data)


@pytest.mark.parametrize(
    "data",
    [
        b"\xef\xbb\xbf" + b"hello",
        "﻿{}".encode("utf-16-le"),
        "﻿{}".encode("utf-16-be"),
        "﻿{}".encode("utf-32-le"),
        "﻿{}".encode("utf-32-be"),
        b"plain ascii, no bom",
        "José".encode(),
    ],
)
def test_recover_bom_and_strict_results_equal_decode_unambiguous(data: bytes) -> None:
    """recover()'s BOM/strict-UTF-8 outcome matches
    kernel.text_decode.decode_unambiguous for every provable input."""
    unambiguous = decode_unambiguous(data)
    assert unambiguous is not None  # sanity: fixture is provable

    result = recover(data)

    assert (result.text, result.source_encoding) == unambiguous
