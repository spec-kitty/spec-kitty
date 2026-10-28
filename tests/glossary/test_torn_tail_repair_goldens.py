"""The glossary torn-tail repair against the goldens the Java port is held to.

``services/mission-status-api/event-log/src/test/resources/torn-tail/repair-cases.json`` records, per ledger shape,
what ``glossary.events._repair_torn_tail`` leaves in the ledger and in its ``<ledger>.torn`` quarantine file.
``TornTailRepairGoldenTest`` (Java, ``event-log``) holds ``TornTailRepair`` to the same file; this test keeps the
file honest against live Python, so the two sides cannot drift apart unnoticed (#6193 follow-up).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from glossary.events import TORN_TAIL_SUFFIX, _repair_torn_tail

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_GOLDENS = Path(__file__).resolve().parents[2] / "services" / "mission-status-api" / "event-log" / "src" / "test" / "resources" / "torn-tail" / "repair-cases.json"
_CASES: list[dict[str, Any]] = json.loads(_GOLDENS.read_text(encoding="utf-8"))["cases"]


def _bytes(segments: list[dict[str, Any]] | None) -> bytes | None:
    if segments is None:
        return None
    return b"".join(bytes.fromhex(segment["hex"]) * segment["repeat"] for segment in segments)


def test_the_goldens_cover_the_shapes_the_port_must_handle() -> None:
    names = {case["name"] for case in _CASES}
    assert {"whole-ledger", "empty-ledger", "fragment-longer-than-a-scan-block", "quarantine-already-holds-fragments"} <= names
    assert any(case["repaired"] for case in _CASES)
    assert any(not case["repaired"] for case in _CASES)


@pytest.mark.parametrize("case", _CASES, ids=[case["name"] for case in _CASES])
def test_python_repair_matches_the_golden(case: dict[str, Any], tmp_path: Path) -> None:
    log = tmp_path / "glossary.events.jsonl"
    log.write_bytes(_bytes(case["ledger"]) or b"")
    torn = log.with_name(log.name + TORN_TAIL_SUFFIX)
    torn_before = _bytes(case["torn_before"])
    if torn_before is not None:
        torn.write_bytes(torn_before)

    result = _repair_torn_tail(log)

    assert (result is not None) == case["repaired"]
    assert log.read_bytes() == _bytes(case["expected_ledger"])
    expected_torn = _bytes(case["expected_torn"])
    assert (torn.read_bytes() if torn.exists() else None) == expected_torn
    assert _repair_torn_tail(log) is None, "a second repair finds the tail whole"
