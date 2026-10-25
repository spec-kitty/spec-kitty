"""The Op lifecycle log and the propagation-error log take the interim lock.

#6606: the append takes the interim event-log lock (``kernel.event_log_append``),
refuses a torn last line and writes the row bytes it wrote before.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from kernel.event_log_append import EventLogTornTailError
from specify_cli.invocation.lifecycle import append_lifecycle_record, lifecycle_log_path
from specify_cli.invocation.propagator import PROPAGATION_ERRORS_PATH, _log_propagation_error
from specify_cli.invocation.record import OpStartedEvent, ProfileInvocationRecord

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_TORN = b'{"whole":1}\n{"torn":'


def _record() -> ProfileInvocationRecord:
    return ProfileInvocationRecord(
        canonical_action_id="implement::do",
        phase="started",
        at=datetime(2026, 4, 28, 12, 0, 0, tzinfo=UTC),
        agent="claude",
        mission_id="01HMISSION0000000000000000",
        wp_id="WP01",
    )


def _op() -> OpStartedEvent:
    return OpStartedEvent(
        invocation_id="01KPQRX2EVGMRVB4Q1JQBAZJV3",
        profile_id="implementer-fixture",
        action="implement",
        request_text="implement the work package",
        actor="claude",
        mode_of_work="task_execution",
        governance_context_hash="abcdef0123456789",
        governance_context_available=True,
        started_at="2026-04-21T10:00:00Z",
    )


def test_lifecycle_append_writes_the_same_line(tmp_path: Path) -> None:
    record = _record()
    path = append_lifecycle_record(tmp_path, record)
    assert path.read_text(encoding="utf-8") == record.to_json_line() + "\n"


def test_lifecycle_append_refuses_a_torn_tail(tmp_path: Path) -> None:
    path = lifecycle_log_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_bytes(_TORN)
    with pytest.raises(EventLogTornTailError):
        append_lifecycle_record(tmp_path, _record())
    assert path.read_bytes() == _TORN


def test_propagation_error_log_writes_one_whole_line(tmp_path: Path) -> None:
    _log_propagation_error(tmp_path, _op(), "boom")
    rows = [json.loads(line) for line in (tmp_path / PROPAGATION_ERRORS_PATH).read_text(encoding="utf-8").splitlines()]
    assert [(row["invocation_id"], row["error"]) for row in rows] == [("01KPQRX2EVGMRVB4Q1JQBAZJV3", "boom")]


def test_propagation_error_log_never_extends_a_torn_tail(tmp_path: Path) -> None:
    path = tmp_path / PROPAGATION_ERRORS_PATH
    path.parent.mkdir(parents=True)
    path.write_bytes(_TORN)
    _log_propagation_error(tmp_path, _op(), "boom")  # never raises
    assert path.read_bytes() == _TORN
