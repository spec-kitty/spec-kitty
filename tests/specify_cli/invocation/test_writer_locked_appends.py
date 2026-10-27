"""Op-record appends take the interim event-log lock (#6606).

The ``kitty-ops`` index, the closure spine and the per-Op trails used an
unlocked ``O_APPEND`` handle. They now go through ``kernel.event_log_append``:
one locked write, a torn last line refused, the started-event identity checked
under the same lock, and one lock file for every per-Op trail.
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

import kernel.event_log_append as event_log_append
import specify_cli.invocation.writer as writer_module

from kernel.event_log_append import EventLogLockTimeoutError, EventLogTornTailError, event_log_lock, event_log_lock_path
from specify_cli.invocation.errors import AlreadyClosedError, InvocationError, InvocationWriteError
from specify_cli.invocation.record import OpCompletedEvent, OpStartedEvent
from specify_cli.invocation.writer import EVENTS_DIR, InvocationWriter, append_op_closure, op_closures_path

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_ID = "01KPQRX2EVGMRVB4Q1JQBAZJV3"
_TORN = b'{"torn":'


def _started(invocation_id: str = _ID) -> OpStartedEvent:
    return OpStartedEvent(
        invocation_id=invocation_id,
        profile_id="implementer-fixture",
        action="implement",
        request_text="implement the work package",
        actor="claude",
        mode_of_work="task_execution",
        governance_context_hash="abcdef0123456789",
        governance_context_available=True,
        started_at="2026-04-21T10:00:00Z",
    )


def _completed(invocation_id: str = _ID) -> OpCompletedEvent:
    return OpCompletedEvent(invocation_id=invocation_id, completed_at="2026-04-21T10:05:00Z", outcome="done", closed_by="agent")


@pytest.fixture
def writer(tmp_path: Path) -> InvocationWriter:
    return InvocationWriter(tmp_path)


def test_started_trail_is_created_inside_the_family_lock(writer: InvocationWriter, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """F5: the exclusive create runs under the ``kitty-ops`` lock, so no append sees an empty trail."""
    trail = tmp_path / EVENTS_DIR / f"{_ID}.jsonl"
    seen: list[tuple[str, Path, object]] = []
    real_lock = writer_module.event_log_lock

    @contextmanager
    def recording_lock(anchor: Path) -> Iterator[Path]:
        seen.append(("enter", anchor, trail.exists()))
        with real_lock(anchor) as lock_path:
            yield lock_path
        seen.append(("exit", anchor, [json.loads(row)["event"] for row in trail.read_text(encoding="utf-8").splitlines()]))

    monkeypatch.setattr(writer_module, "event_log_lock", recording_lock)
    writer.write_started(_started())
    family = tmp_path / EVENTS_DIR
    assert seen == [("enter", family, False), ("exit", family, ["started"])]


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits")
def test_new_trail_and_index_are_owner_only(writer: InvocationWriter, tmp_path: Path) -> None:
    previous = os.umask(0o022)
    try:
        trail = writer.write_started(_started())
    finally:
        os.umask(previous)
    assert trail.stat().st_mode & 0o777 == 0o600
    assert (tmp_path / EVENTS_DIR / "ops-index.jsonl").stat().st_mode & 0o777 == 0o600


def test_completed_appends_after_a_whole_started_line(writer: InvocationWriter) -> None:
    path = writer.write_started(_started())
    writer.write_completed(_completed())
    lines = path.read_text(encoding="utf-8").splitlines()
    assert [line.count('"event"') for line in lines] == [1, 1]
    assert lines[1] == _completed().to_jsonl_line()


def test_completed_refuses_a_torn_trail_and_leaves_it_byte_identical(writer: InvocationWriter) -> None:
    path = writer.write_started(_started())
    path.write_bytes(path.read_bytes() + _TORN)
    before = path.read_bytes()
    with pytest.raises(InvocationError, match=r"unreadable: .*Error code: EVENT_LOG_TORN_TAIL\.\)$"):
        writer.write_completed(_completed())
    assert path.read_bytes() == before


def test_correlation_link_refuses_a_torn_trail(writer: InvocationWriter) -> None:
    path = writer.write_started(_started())
    path.write_bytes(path.read_bytes() + _TORN)
    before = path.read_bytes()
    with pytest.raises(InvocationError):
        writer.append_correlation_link(_ID, ref="docs/x.md")
    assert path.read_bytes() == before


def test_second_completion_is_still_refused(writer: InvocationWriter) -> None:
    writer.write_started(_started())
    writer.write_completed(_completed())
    with pytest.raises(AlreadyClosedError):
        writer.write_completed(_completed())


def test_missing_trail_is_still_not_found(writer: InvocationWriter) -> None:
    with pytest.raises(InvocationError, match="not found"):
        writer.append_correlation_link(_ID, ref="docs/x.md")


def test_closure_spine_refuses_a_torn_tail(tmp_path: Path) -> None:
    path = op_closures_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_bytes(_TORN)
    with pytest.raises(EventLogTornTailError):
        append_op_closure(tmp_path, _completed())
    assert path.read_bytes() == _TORN


def test_index_append_never_extends_a_torn_tail(writer: InvocationWriter, tmp_path: Path) -> None:
    index = tmp_path / EVENTS_DIR / "ops-index.jsonl"
    index.parent.mkdir(parents=True)
    index.write_bytes(_TORN)
    writer.write_started(_started())  # the index is a performance aid: refused, the Op still starts
    assert index.read_bytes() == _TORN


def test_a_held_family_lock_refuses_the_append(writer: InvocationWriter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = writer.write_started(_started())
    before = path.read_bytes()
    real_append = event_log_append.append_event_log_lines

    def short_wait(log: Path, lines: list[str], **kwargs: Any) -> None:
        kwargs["timeout_s"] = 0.2
        real_append(log, lines, **kwargs)

    monkeypatch.setattr(writer_module, "append_event_log_lines", short_wait)
    # Another thread holds the family lock: the lock is re-entrant within one thread (#6706).
    held, release = threading.Event(), threading.Event()

    def holder() -> None:
        with event_log_lock(tmp_path / EVENTS_DIR):
            held.set()
            release.wait(10)

    thread = threading.Thread(target=holder)
    thread.start()
    held.wait(10)
    try:
        with pytest.raises(InvocationWriteError) as excinfo:
            writer.write_completed(_completed())
    finally:
        release.set()
        thread.join()
    assert isinstance(excinfo.value.__cause__, EventLogLockTimeoutError)
    assert path.read_bytes() == before


def test_per_op_trails_share_one_family_lock(writer: InvocationWriter, tmp_path: Path) -> None:
    first = writer.write_started(_started())
    second = writer.write_started(_started("01KPQRX2EVGMRVB4Q1JQBAZJV4"))
    writer.write_completed(_completed())
    writer.write_completed(_completed("01KPQRX2EVGMRVB4Q1JQBAZJV4"))
    family_lock = event_log_lock_path(tmp_path / EVENTS_DIR)
    assert family_lock.exists()
    assert event_log_lock_path(first) != family_lock
    assert not event_log_lock_path(second).exists()


def test_symlinked_trail_is_still_refused(writer: InvocationWriter, tmp_path: Path) -> None:
    real = writer.write_started(_started())
    target = tmp_path / "elsewhere.jsonl"
    target.write_bytes(real.read_bytes())
    real.unlink()
    real.symlink_to(target)
    with pytest.raises((InvocationError, ValueError)):
        writer.write_completed(_completed())
    assert target.read_bytes().count(b"\n") == 1


def test_trail_swapped_for_a_symlink_after_the_path_check_is_a_write_error(writer: InvocationWriter, tmp_path: Path) -> None:
    # The race ``invocation_path`` cannot see: the trail becomes a symlink after
    # its own check. Same type and message as the pre-lock O_NOFOLLOW open.
    real = writer.write_started(_started())
    target = tmp_path / "elsewhere.jsonl"
    target.write_bytes(real.read_bytes())
    real.unlink()
    real.symlink_to(target)
    with pytest.raises(InvocationWriteError, match="Failed to open invocation record safely"):
        writer._append_validated(real, _ID, _completed().to_jsonl_line())
    assert target.read_bytes().count(b"\n") == 1


def test_a_trail_line_that_is_not_json_is_unreadable(writer: InvocationWriter) -> None:
    path = writer.write_started(_started())
    path.write_bytes(b"not json\n")
    with pytest.raises(InvocationError, match="unreadable"):
        writer.write_completed(_completed())
    assert path.read_bytes() == b"not json\n"


def test_a_trail_without_a_started_event_is_refused(writer: InvocationWriter) -> None:
    path = writer.write_started(_started())
    body = _completed().to_jsonl_line().encode("utf-8") + b"\n"
    path.write_bytes(body)
    with pytest.raises(InvocationError, match="no started event"):
        writer.append_correlation_link(_ID, ref="docs/x.md")
    assert path.read_bytes() == body


def test_a_refused_index_append_is_logged_not_silent(writer: InvocationWriter, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """A torn index tail refuses every later index row; the drop is logged, so it is visible (pre-PR squad)."""
    index = tmp_path / EVENTS_DIR / "ops-index.jsonl"
    index.parent.mkdir(parents=True)
    index.write_bytes(_TORN)
    with caplog.at_level("WARNING", logger=writer_module.__name__):
        writer.write_started(_started())
    assert index.read_bytes() == _TORN
    assert any("ops-index.jsonl" in record.getMessage() and "torn" in record.getMessage() for record in caplog.records)
