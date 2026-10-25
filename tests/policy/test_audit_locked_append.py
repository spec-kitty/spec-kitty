"""``policy-audit.jsonl`` takes the interim lock.

#6606: the append takes the interim event-log lock (``kernel.event_log_append``),
refuses a torn last line and writes the row bytes it wrote before.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel.event_log_append import EventLogTornTailError
from specify_cli.policy.audit import AUDIT_FILENAME, append_audit_event, create_audit_event

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_TORN = b'{"whole":1}\n{"torn":'


def test_appends_the_same_line(tmp_path: Path) -> None:
    event = create_audit_event("override", "m", "claude", "why")
    append_audit_event(tmp_path, event)
    assert (tmp_path / AUDIT_FILENAME).read_text(encoding="utf-8") == event.to_json_line() + "\n"


def test_refuses_a_torn_tail(tmp_path: Path) -> None:
    (tmp_path / AUDIT_FILENAME).write_bytes(_TORN)
    with pytest.raises(EventLogTornTailError):
        append_audit_event(tmp_path, create_audit_event("override", "m", "claude", "why"))
    assert (tmp_path / AUDIT_FILENAME).read_bytes() == _TORN
