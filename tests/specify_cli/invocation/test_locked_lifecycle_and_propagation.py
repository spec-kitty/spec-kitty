"""The Op lifecycle log and the propagation-error log take the interim lock.

#6606: the append takes the interim event-log lock (``kernel.event_log_append``),
refuses a torn last line and writes the row bytes it wrote before.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from kernel.clock import parse_iso
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
        at=parse_iso("2026-04-28T12:00:00+00:00"),
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


def test_lifecycle_append_never_touches_a_torn_legacy_log(tmp_path: Path) -> None:
    """#7003: the legacy log is read-only, so even a torn one never blocks a new record."""
    legacy = lifecycle_log_path(tmp_path)
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(_TORN)
    written = append_lifecycle_record(tmp_path, _record())
    assert legacy.read_bytes() == _TORN
    assert written.read_text(encoding="utf-8") == _record().to_json_line() + "\n"


def test_lifecycle_append_refuses_a_torn_record_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.invocation.lifecycle as lifecycle

    monkeypatch.setattr(lifecycle, "_new_record_id", lambda: "01ARZ3NDEKTSV4RRFFQ69G5FAV")
    path = lifecycle.lifecycle_records_dir(tmp_path) / "01ARZ3NDEKTSV4RRFFQ69G5FAV.json"
    path.parent.mkdir(parents=True)
    path.write_bytes(_TORN)
    with pytest.raises(EventLogTornTailError):
        append_lifecycle_record(tmp_path, _record())
    assert path.read_bytes() == _TORN


def test_lifecycle_append_takes_the_record_directory_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """One family lock anchored on the record directory, not one lock file per record."""
    from kernel import event_log_append
    from specify_cli.invocation.lifecycle import lifecycle_records_dir

    seen: list[object] = []
    real = event_log_append.append_event_log_lines

    def _spy(log: Path, lines: list[str], **kwargs: Any) -> None:
        seen.append(kwargs.get("lock_anchor"))
        real(log, lines, **kwargs)

    monkeypatch.setattr("specify_cli.invocation.lifecycle.append_event_log_lines", _spy)
    append_lifecycle_record(tmp_path, _record())
    append_lifecycle_record(tmp_path, _record())
    assert seen == [lifecycle_records_dir(tmp_path)] * 2


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
