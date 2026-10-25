"""``mission-events.jsonl`` takes the interim lock.

#6606: the append takes the interim event-log lock (``kernel.event_log_append``),
refuses a torn last line and writes the row bytes it wrote before.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.mission_v1.events import MISSION_EVENTS_FILE, _write_event, emit_event

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_TORN = b'{"whole":1}\n{"torn":'


def test_writes_the_same_line(tmp_path: Path) -> None:
    event = {"type": "phase_entered", "timestamp": "t", "mission": "m", "payload": {"x": 1}}
    _write_event(tmp_path, event)
    assert (tmp_path / MISSION_EVENTS_FILE).read_text(encoding="utf-8") == json.dumps(event, sort_keys=True) + "\n"


def test_never_extends_a_torn_tail(tmp_path: Path) -> None:
    path = tmp_path / MISSION_EVENTS_FILE
    path.write_bytes(_TORN)
    emit_event("phase_entered", {"x": 1}, mission_name="m", feature_dir=tmp_path)  # swallows, as before
    assert path.read_bytes() == _TORN


def test_a_missing_mission_directory_is_not_created(tmp_path: Path) -> None:
    missing = tmp_path / "absent"
    emit_event("phase_entered", {}, mission_name="m", feature_dir=missing)
    assert not missing.exists()
