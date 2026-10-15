"""Integration tests for intake size-cap enforcement (WP02 T009 / NFR-003).

These tests exercise :func:`specify_cli.intake.scanner.read_brief` and
:func:`read_stdin_capped` end-to-end:

* A 50 MB random file is rejected before being read into memory; peak
  RSS stays below ``1.5 × cap``.
* A 4 MB file is accepted normally.
* A simulated 6 MB STDIN input is rejected without buffering the
  entire payload.
"""
from __future__ import annotations

import io
import os
import resource
import sys
from pathlib import Path

import pytest

from specify_cli.intake.errors import IntakeTooLargeError
from specify_cli.intake.scanner import (
    DEFAULT_MAX_BRIEF_BYTES,
    read_brief,
    read_stdin_capped,
)


pytestmark = [pytest.mark.integration, pytest.mark.fast]


def _peak_rss_bytes() -> int:
    """Return process peak RSS in bytes.  ``ru_maxrss`` is bytes on macOS,
    KiB on Linux — normalise to bytes."""
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return int(rss)
    return int(rss) * 1024


def test_50mb_file_rejected_with_bounded_memory(tmp_path):
    """NFR-003: 50 MB rejection must keep peak RSS below 1.5 × cap."""
    cap = DEFAULT_MAX_BRIEF_BYTES  # 5 MB
    big = tmp_path / "huge.md"

    # Write 50 MB in chunks so the test doesn't itself blow the budget.
    chunk = os.urandom(1024 * 1024)  # 1 MB
    with open(big, "wb") as f:
        for _ in range(50):
            f.write(chunk)

    rss_before = _peak_rss_bytes()
    with pytest.raises(IntakeTooLargeError) as ei:
        read_brief(big, cap=cap)

    # The structured detail surfaces both the actual size and the cap.
    assert ei.value.detail["cap"] == cap
    assert ei.value.detail["size"] == 50 * 1024 * 1024

    rss_after = _peak_rss_bytes()
    # NFR-003: rejection itself must not balloon RSS by more than
    # 1.5 × cap.  We compare *delta* so the budget isn't dominated by
    # whatever pytest already had loaded.  Fudge factor: 0.5 × cap on
    # top of 1.5 × cap to absorb getrusage rounding.
    delta = rss_after - rss_before
    assert delta < int(1.5 * cap) + cap, (
        f"RSS delta {delta} exceeds 1.5×cap {int(1.5 * cap)} + slack {cap}"
    )


def test_4mb_file_accepted(tmp_path):
    cap = DEFAULT_MAX_BRIEF_BYTES
    small = tmp_path / "small.md"
    payload = b"x" * (4 * 1024 * 1024)
    small.write_bytes(payload)

    text = read_brief(small, cap=cap)
    assert len(text) == 4 * 1024 * 1024


def test_file_at_cap_boundary_accepted(tmp_path):
    """Spec: ``size > cap`` → reject.  At-cap is allowed."""
    cap = 1024
    fp = tmp_path / "exact.md"
    fp.write_bytes(b"a" * cap)
    text = read_brief(fp, cap=cap)
    assert len(text) == cap


def test_file_one_byte_over_cap_rejected(tmp_path):
    cap = 1024
    fp = tmp_path / "over.md"
    fp.write_bytes(b"a" * (cap + 1))
    with pytest.raises(IntakeTooLargeError):
        read_brief(fp, cap=cap)


def test_stdin_6mb_rejected():
    """STDIN cannot be ``stat()``ed; the cap+1 read protects against overrun."""
    cap = DEFAULT_MAX_BRIEF_BYTES  # 5 MB
    payload = b"y" * (6 * 1024 * 1024)
    stream = io.BytesIO(payload)

    with pytest.raises(IntakeTooLargeError) as ei:
        read_stdin_capped(stream, cap=cap)

    assert ei.value.detail["cap"] == cap
    # We only buffered cap + 1 bytes regardless of payload size.
    assert ei.value.detail["size"] == cap + 1


def test_stdin_under_cap_accepted():
    cap = 1024
    payload = b"hello world"
    stream = io.BytesIO(payload)
    out = read_stdin_capped(stream, cap=cap)
    assert out == "hello world"


def test_stdin_text_stream_under_cap_accepted():
    cap = 1024
    payload = "# brief from stdin"
    stream = io.StringIO(payload)
    out = read_stdin_capped(stream, cap=cap)
    assert out == payload
