"""Shared input-validation tables for the hardened Feedback validator.

``RATING_CASES``, ``COMMENT_CASES`` and ``EMAIL_CASES`` are exported so other
work packages can reuse the same rows for surface parity checks.

Comment policy under test: terminal escape sequences and characters in the
Unicode categories Cc and Cf are removed, every whitespace run (including
newlines and tabs) collapses to one space, markup is preserved untouched.
"""

from __future__ import annotations

import time
import unicodedata
from typing import Any

import pytest

from specify_cli.feedback.payload import (
    COMMENT_MAX_LENGTH,
    EMAIL_MAX_LENGTH,
    normalize_comment,
    parse_email,
    parse_rating,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

# (raw, expected rating value or None when rejected)
RATING_CASES: list[tuple[Any, int | None]] = [
    (0, None),
    (6, None),
    (-1, None),
    (4.5, None),
    ("five", None),
    ("5 stars", None),
    (" 5 ", None),
    ("5\n", None),
    ("", None),
    (True, None),
    (False, None),
    (None, None),
    (1, 1),
    (2, 2),
    (3, 3),
    (4, 4),
    (5, 5),
    ("1", 1),
    ("2", 2),
    ("3", 3),
    ("4", 4),
    ("5", 5),
]

_ESC = "\x1b"

# (raw, expected cleaned text or None, expected truncated flag)
COMMENT_CASES: list[tuple[str | None, str | None, bool]] = [
    # hostile input: terminal escapes
    (f"{_ESC}[31mred{_ESC}[0m", "red", False),
    (f"{_ESC}[1;32;40mgreen{_ESC}[m text", "green text", False),
    (f"a{_ESC}[2Jb", "ab", False),
    (f"a{_ESC}[?25lb", "ab", False),
    (f"{_ESC}]0;evil title\x07shown", "shown", False),
    (f"{_ESC}]8;;http://example.test{_ESC}\\link{_ESC}]8;;{_ESC}\\", "link", False),
    (f"x{_ESC}cy", "xy", False),
    # hostile input: 8-bit C1 introducers must not leak their payload
    ("a\x9b31mb", "ab", False),
    ("a\x9b2Jb", "ab", False),
    ("a\x9d0;title\x07b", "ab", False),
    ("a\x9d0;title\x9cb", "ab", False),
    ("a\x90qpayload\x9cb", "ab", False),
    ("a\x98sos text\x9cb", "ab", False),
    ("a\x9epriv\x9cb", "ab", False),
    ("a\x9fapc\x9cb", "ab", False),
    (f"a{_ESC}Pdcs payload{_ESC}\\b", "ab", False),
    (f"a{_ESC}_apc payload{_ESC}\\b", "ab", False),
    # hostile input: control characters
    ("a\x00b", "ab", False),
    ("a\x07b", "ab", False),
    ("a\x08b", "ab", False),
    ("a\x7fb", "ab", False),
    ("a\x85b", "ab", False),
    ("a\x9b", "a", False),  # unterminated CSI introducer is still dropped
    ("a\x80\x81\x82b", "ab", False),
    # hostile input: format characters
    ("a\u200bb", "ab", False),
    ("a\u200db", "ab", False),
    ("a\u200cb", "ab", False),
    ("a\u202ereversed\u202c", "areversed", False),
    ("\u2066x\u2069", "x", False),
    ("\ufeffbom", "bom", False),
    ("a\u2060b", "ab", False),
    (f"\ufeff{_ESC}[31m\x00a\u200b\u202eb\x07", "ab", False),
    # whitespace normalisation
    ("  padded  ", "padded", False),
    ("two\nlines\tand   gaps", "two lines and gaps", False),
    ("a\r\nb", "a b", False),
    # empty after cleaning means absent
    (None, None, False),
    ("", None, False),
    ("   \n\t ", None, False),
    ("\u200b\x00\x07", None, False),
    (f"{_ESC}[31m{_ESC}[0m", None, False),
    # preserved content
    ("use <b>bold</b> and a < b", "use <b>bold</b> and a < b", False),
    ("café naïve Zoë", "café naïve Zoë", False),
    ("great \U0001f600 tool", "great \U0001f600 tool", False),
    ("x = [i for i in range(3)]  # ok", "x = [i for i in range(3)] # ok", False),
    ("<script>alert(1)</script>", "<script>alert(1)</script>", False),
    ("cafe\u0301", "caf\u00e9", False),  # NFC composes
    # NFC must hold after format characters are dropped
    ("e\u200b\u0301", "\u00e9", False),
    ("e\u200d\u0301x", "\u00e9x", False),
    ("e\x00\u0301", "\u00e9", False),
    (f"e{_ESC}[0m\u0301", "\u00e9", False),
    ("a" * (COMMENT_MAX_LENGTH - 1) + "e\u200b\u0301", "a" * (COMMENT_MAX_LENGTH - 1) + "\u00e9", False),
    ("a" * (COMMENT_MAX_LENGTH - 1) + "e\u200b\u0301\u0323", "a" * (COMMENT_MAX_LENGTH - 1), True),
    # truncation
    ("a" * COMMENT_MAX_LENGTH, "a" * COMMENT_MAX_LENGTH, False),
    ("a" * (COMMENT_MAX_LENGTH + 1), "a" * COMMENT_MAX_LENGTH, True),
    ("\u00e9" * (COMMENT_MAX_LENGTH + 5), "\u00e9" * COMMENT_MAX_LENGTH, True),
    ("a" * (COMMENT_MAX_LENGTH - 1) + "e\u0302\u0323", "a" * (COMMENT_MAX_LENGTH - 1) + "\u1ec7", False),
]

# (raw, expected value or None, expected ok flag)
EMAIL_CASES: list[tuple[str | None, str | None, bool]] = [
    # invalid
    ("a@b", None, False),
    ("a b@example.test", None, False),
    ("a@@example.test", None, False),
    ("a@example.test, b@example.test", None, False),
    ("a@example.test;b@example.test", None, False),
    ("a@example.test b@example.test", None, False),
    ("a\x00@example.test", None, False),
    ("a@exam\x07ple.test", None, False),
    ("a@exa\nmple.test", None, False),
    ("a@.example.test", None, False),
    ("a@example.test.", None, False),
    ("a@example..test", None, False),
    ("a@-example.test", None, False),
    ("@example.test", None, False),
    ("a@", None, False),
    ("plainaddress", None, False),
    (".a@example.test", None, False),
    ("a.@example.test", None, False),
    ("a..b@example.test", None, False),
    ("a" * (EMAIL_MAX_LENGTH - len("@example.test") + 1) + "@example.test", None, False),
    # valid
    ("person@example.test", "person@example.test", True),
    ("first.last+tag@mail.example.test", "first.last+tag@mail.example.test", True),
    ("  person@example.test  ", "person@example.test", True),
    ("a" * (EMAIL_MAX_LENGTH - len("@example.test")) + "@example.test", "a" * (EMAIL_MAX_LENGTH - len("@example.test")) + "@example.test", True),
    # absent
    ("", None, True),
    ("   ", None, True),
    (None, None, True),
]


@pytest.mark.parametrize(("raw", "expected"), RATING_CASES)
def test_rating_table(raw: Any, expected: int | None) -> None:
    result = parse_rating(raw)
    if expected is None:
        assert result is None
    else:
        assert result is not None
        assert int(result) == expected


@pytest.mark.parametrize(("raw", "text", "truncated"), COMMENT_CASES)
def test_comment_table(raw: str | None, text: str | None, truncated: bool) -> None:
    assert normalize_comment(raw) == (text, truncated)


@pytest.mark.parametrize(("raw", "value", "ok"), EMAIL_CASES)
def test_email_table(raw: str | None, value: str | None, ok: bool) -> None:
    assert parse_email(raw) == (value, ok)


def test_every_comment_output_is_nfc() -> None:
    outputs = [normalize_comment(raw)[0] for raw, _, _ in COMMENT_CASES]
    cleaned = [out for out in outputs if out]
    assert cleaned
    for out in cleaned:
        assert unicodedata.is_normalized("NFC", out)
        assert out == unicodedata.normalize("NFC", out)


def test_table_sizes_meet_minimums() -> None:
    assert sum(1 for _, e in RATING_CASES if e is None) >= 10
    assert len(COMMENT_CASES) >= 20
    assert sum(1 for _, v, ok in EMAIL_CASES if not ok) >= 10


def test_comment_cleaning_leaves_no_control_or_format_characters() -> None:
    # C1 introducers (CSI/string types) consume following text by design; they have their own cases.
    introducers = {0x90, 0x98, 0x9B, 0x9D, 0x9E, 0x9F}
    plain_c1 = [chr(c) for c in range(0x7F, 0xA0) if c not in introducers]
    raw = "".join(chr(c) for c in range(0x20)) + "".join(plain_c1) + "ok\u200b\u202e"
    cleaned, _ = normalize_comment(raw)
    assert cleaned == "ok"
    assert all(unicodedata.category(ch) not in {"Cc", "Cf"} for ch in (cleaned or ""))


def test_truncation_does_not_split_combining_sequence() -> None:
    # Base letter lands on the last allowed slot; its combining mark would be cut.
    raw = "a" * (COMMENT_MAX_LENGTH - 1) + "x\u0301\u0301" + "tail"
    cleaned, truncated = normalize_comment(raw)
    assert truncated is True
    assert cleaned is not None
    assert len(cleaned) <= COMMENT_MAX_LENGTH
    assert not unicodedata.category(cleaned[-1]).startswith("M")
    assert "x" not in cleaned or cleaned.endswith("\u0301\u0301")


def test_validation_is_fast_nfr_001() -> None:
    """NFR-001: validating one submission stays far below 10 ms (generous margin)."""
    comment = ("word <b>x</b> \x1b[31m\u200b " * 200)[: COMMENT_MAX_LENGTH * 2]
    start = time.perf_counter()
    parse_rating("5")
    normalize_comment(comment)
    parse_email("person@example.test")
    elapsed = time.perf_counter() - start
    assert elapsed < 0.010, f"validation took {elapsed * 1000:.2f} ms"
