"""The glossary torn-tail repair against the goldens the Java port is held to.

``services/mission-status-api/event-log/src/test/resources/torn-tail/repair-cases.json`` records, per ledger shape,
what ``glossary.events._repair_torn_tail`` leaves in the ledger and in its ``<ledger>.torn`` quarantine file.
``TornTailRepairGoldenTest`` (Java, ``event-log``) holds ``TornTailRepair`` to the same file. This module is the file's
one source: :data:`CASES` lists the ledger shapes, live Python computes the expected bytes, and
:func:`test_the_committed_goldens_are_what_python_produces` keeps the committed file equal to that, so the two sides
cannot drift apart unnoticed (#6193 follow-up). After changing :data:`CASES` or the Python repair, rewrite the file::

    uv run --frozen python -m tests.glossary.test_torn_tail_repair_goldens
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from glossary.events import TORN_TAIL_SUFFIX, _repair_torn_tail

pytestmark = [pytest.mark.unit, pytest.mark.fast]

GOLDENS = Path(__file__).resolve().parents[2] / "services" / "mission-status-api" / "event-log" / "src" / "test" / "resources" / "torn-tail" / "repair-cases.json"

_BLOCK = 64 * 1024
#: A run of at least this many equal bytes is written as one repeated segment.
_RUN = 16

#: (name, ledger bytes, quarantine bytes before the repair or None, why the case is there)
CASES: list[tuple[str, bytes, bytes | None, str]] = [
    ("whole-ledger", b'{"a": 1}\n{"b": 2}\n', None, "every line ends in LF: nothing changes and no quarantine file is created"),
    ("empty-ledger", b"", None, "an empty ledger has no torn tail"),
    ("torn-json-line", b'{"a": 1}\n{"b": 2', None, "the half-written last line moves to the quarantine file"),
    ("no-newline-at-all", b'{"a": 1', None, "a ledger with no LF is all fragment: it is cut back to empty"),
    ("lone-carriage-return", b'{"a": 1}\n\r', None, "a CR after the last LF is a fragment; only LF ends a line"),
    ("crlf-line-then-fragment", b'{"a": 1}\r\n{"b"', None, "the CR of a CRLF line stays with its line"),
    ("non-utf8-fragment", b'{"a": 1}\n\xff\xfe\x00', None, "the fragment is moved byte for byte, never decoded"),
    ("fragment-longer-than-a-scan-block", b'{"a": 1}\n' + b"x" * 70000, None, "the backward scan crosses the 64 KiB block boundary"),
    ("newline-just-before-the-last-block", b"a" * 9 + b"\n" + b"y" * _BLOCK, None, "the last LF sits one byte outside the final 64 KiB block"),
    ("newline-first-byte-of-the-last-block", b"abc\n" + b"z" * (_BLOCK - 1), None, "the last LF is the first byte of the final 64 KiB block"),
    ("no-newline-across-several-blocks", b"q" * (2 * _BLOCK + 4464), None, "with no LF the scan runs back across several blocks to offset 0"),
    ("quarantine-already-holds-fragments", b'{"a": 1}\n{"c"', b'{"old"\n', "a second repair appends to the existing quarantine file"),
]


def _segments(data: bytes) -> list[dict[str, Any]]:
    """Hex segments, a long run of one byte written once with its repeat count."""
    out: list[dict[str, Any]] = []
    literal = bytearray()
    i = 0
    while i < len(data):
        j = i
        while j < len(data) and data[j] == data[i]:
            j += 1
        if j - i >= _RUN:
            if literal:
                out.append({"hex": literal.hex(), "repeat": 1})
                literal = bytearray()
            out.append({"hex": data[i : i + 1].hex(), "repeat": j - i})
        else:
            literal += data[i:j]
        i = j
    if literal:
        out.append({"hex": literal.hex(), "repeat": 1})
    return out


def _bytes(segments: list[dict[str, Any]] | None) -> bytes | None:
    if segments is None:
        return None
    return b"".join(bytes.fromhex(segment["hex"]) * segment["repeat"] for segment in segments)


def _repair_in(directory: Path, ledger: bytes, torn_before: bytes | None) -> tuple[bool, bytes, bytes | None, Path, Path]:
    log = directory / "glossary.events.jsonl"
    log.write_bytes(ledger)
    torn = log.with_name(log.name + TORN_TAIL_SUFFIX)
    if torn_before is not None:
        torn.write_bytes(torn_before)
    repaired = _repair_torn_tail(log) is not None
    return repaired, log.read_bytes(), torn.read_bytes() if torn.exists() else None, log, torn


def render_goldens() -> str:
    """The goldens file as live Python produces it from :data:`CASES`."""
    cases = []
    for name, ledger, torn_before, why in CASES:
        with tempfile.TemporaryDirectory() as directory:
            repaired, after, torn_after, _, _ = _repair_in(Path(directory), ledger, torn_before)
        cases.append(
            {
                "name": name,
                "why": why,
                "ledger": _segments(ledger),
                "torn_before": None if torn_before is None else _segments(torn_before),
                "repaired": repaired,
                "expected_ledger": _segments(after),
                "expected_torn": None if torn_after is None else _segments(torn_after),
            }
        )
    document = {
        "about": (
            "Torn-tail repair goldens: glossary.events._repair_torn_tail (Python) and TornTailRepair (Java) must both turn each ledger into "
            "expected_ledger and the quarantine file <ledger>.torn into expected_torn (null: no quarantine file). Bytes are hex segments, each "
            "repeated `repeat` times. Written by `uv run --frozen python -m tests.glossary.test_torn_tail_repair_goldens` from live Python; "
            "tests/glossary/test_torn_tail_repair_goldens.py fails when this file differs from what Python produces."
        ),
        "cases": cases,
    }
    return json.dumps(document, indent=2) + "\n"


_COMMITTED: list[dict[str, Any]] = json.loads(GOLDENS.read_text(encoding="utf-8"))["cases"]


def test_the_committed_goldens_are_what_python_produces() -> None:
    assert GOLDENS.read_text(encoding="utf-8") == render_goldens(), "regenerate: uv run --frozen python -m tests.glossary.test_torn_tail_repair_goldens"


def test_the_goldens_cover_the_shapes_the_port_must_handle() -> None:
    names = {case["name"] for case in _COMMITTED}
    assert {
        "whole-ledger",
        "empty-ledger",
        "newline-first-byte-of-the-last-block",
        "no-newline-across-several-blocks",
        "quarantine-already-holds-fragments",
    } <= names
    assert any(case["repaired"] for case in _COMMITTED)
    assert any(not case["repaired"] for case in _COMMITTED)


@pytest.mark.parametrize("case", _COMMITTED, ids=[case["name"] for case in _COMMITTED])
def test_python_repair_matches_the_golden(case: dict[str, Any], tmp_path: Path) -> None:
    repaired, after, torn_after, log, _ = _repair_in(tmp_path, _bytes(case["ledger"]) or b"", _bytes(case["torn_before"]))
    assert repaired == case["repaired"]
    assert after == _bytes(case["expected_ledger"])
    assert torn_after == _bytes(case["expected_torn"])
    assert _repair_torn_tail(log) is None, "a second repair finds the tail whole"


def test_a_failed_quarantine_write_leaves_the_ledger_untouched(tmp_path: Path) -> None:
    """The quarantine is written before the ledger is cut, so a failed quarantine write loses nothing (the Java port pins the same)."""
    log = tmp_path / "glossary.events.jsonl"
    log.write_bytes(b'{"a": 1}\n{"b"')
    log.with_name(log.name + TORN_TAIL_SUFFIX).mkdir()
    with pytest.raises((IsADirectoryError, PermissionError)):  # PermissionError on Windows
        _repair_torn_tail(log)
    assert log.read_bytes() == b'{"a": 1}\n{"b"'


def test_a_missing_ledger_is_refused_and_not_created(tmp_path: Path) -> None:
    """Like the Java port: the repair refuses a missing ledger and creates neither it nor a quarantine file (only its lock file)."""
    log = tmp_path / "absent.events.jsonl"
    with pytest.raises(FileNotFoundError):
        _repair_torn_tail(log)
    assert not log.exists()
    assert not log.with_name(log.name + TORN_TAIL_SUFFIX).exists()
    assert log.with_name(log.name + ".lock").exists()


if __name__ == "__main__":
    GOLDENS.write_text(render_goldens(), encoding="utf-8")
