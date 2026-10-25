"""The glossary contract append runs under the interim lock.

#6606: the append takes the interim event-log lock (``kernel.event_log_append``),
refuses a torn last line and writes the row bytes it wrote before.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

import glossary.events as glossary_events

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_append_and_repair_run_under_the_event_log_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    log = tmp_path / "events" / "glossary" / "m.events.jsonl"
    observed: list[str] = []

    @contextmanager
    def recording_lock(anchor: Path) -> Iterator[Path]:
        observed.append(f"lock:{anchor.name}")
        yield anchor
        observed.append("unlock")

    def fake_append(_event: object, _path: object) -> None:
        observed.append("append")

    monkeypatch.setattr(glossary_events, "event_log_lock", recording_lock)
    monkeypatch.setattr(glossary_events, "_ledger_append", fake_append)
    glossary_events.append_event({"event_type": "X"}, log)
    assert observed == ["lock:m.events.jsonl", "append", "unlock"]
    assert log.parent.is_dir()
