"""``archived-missions.jsonl`` takes the interim lock.

#6606: the append takes the interim event-log lock (``kernel.event_log_append``),
refuses a torn last line and writes the row bytes it wrote before.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kernel.event_log_append import EventLogTornTailError
from specify_cli.missions._archive import ArchivedMission, append_archive_record, archive_registry_path

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_TORN = b'{"whole":1}\n{"torn":'


def _record() -> ArchivedMission:
    return ArchivedMission(
        mission_id="01HMISSION0000000000000000", archived_by="claude", archived_at="2026-10-25T00:00:00+00:00", reason="done", terminal_state_at_archive="merged"
    )


def test_appends_the_same_line(tmp_path: Path) -> None:
    path = append_archive_record(tmp_path, _record())
    assert path.read_text(encoding="utf-8") == json.dumps(_record().to_dict(), sort_keys=True) + "\n"


def test_refuses_a_torn_tail(tmp_path: Path) -> None:
    path = archive_registry_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_bytes(_TORN)
    with pytest.raises(EventLogTornTailError):
        append_archive_record(tmp_path, _record())
    assert path.read_bytes() == _TORN
