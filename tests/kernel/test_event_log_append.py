"""Tests for ``kernel.event_log_append`` -- the interim locked event-log append (#6606).

Contract: ``kitty-specs/eventbridge-gate-and-locked-appends-01M5T0TN/contracts/interim-ledger-lock.md``.
"""

from __future__ import annotations

import errno
import json
import multiprocessing
import os
import subprocess
import threading
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

import kernel.event_log_append as event_log_append
from kernel.event_log_append import (
    NON_GIT_LOCK_SUFFIX,
    EventLogAppendError,
    EventLogLockTimeoutError,
    EventLogLockUnavailableError,
    EventLogShortWriteError,
    EventLogSymlinkError,
    EventLogTornTailError,
    append_event_log_lines,
    event_log_lock,
    event_log_lock_path,
)
from kernel.git_topology import GitTopologyUnavailableError, clear_caches

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_ROWS_PER_WRITER = 50
_WRITERS = 8


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "init")
    clear_caches()
    return root


@pytest.fixture()
def log(repo: Path) -> Path:
    path = repo / "kitty-specs" / "m" / "decisions.events.jsonl"
    path.parent.mkdir(parents=True)
    return path


# ---------------------------------------------------------------------------
# Framing and bytes
# ---------------------------------------------------------------------------


def test_appends_one_unit_with_exact_bytes(log: Path) -> None:
    append_event_log_lines(log, ['{"a":1}'])
    append_event_log_lines(log, ['{"b":2}', '{"c":"é"}'])
    assert log.read_bytes() == b'{"a":1}\n{"b":2}\n{"c":"\xc3\xa9"}\n'


@pytest.mark.parametrize("lines", [[], "a string", ["ok", "two\nlines"], ["cr\r"]])
def test_refuses_bad_framing_without_touching_the_log(log: Path, lines: Sequence[str]) -> None:
    with pytest.raises(ValueError, match="line"):
        append_event_log_lines(log, lines)
    assert not log.exists()


def test_refuses_non_str_lines(log: Path) -> None:
    not_text: list[Any] = [b"bytes"]
    with pytest.raises(TypeError, match="str"):
        append_event_log_lines(log, not_text)
    assert not log.exists()


def test_appends_to_an_empty_existing_log(log: Path) -> None:
    log.write_bytes(b"")
    append_event_log_lines(log, ["x"])
    assert log.read_bytes() == b"x\n"


# ---------------------------------------------------------------------------
# Torn tail
# ---------------------------------------------------------------------------


def test_refuses_a_torn_tail_and_leaves_the_log_byte_identical(log: Path) -> None:
    log.write_bytes(b'{"whole":1}\n{"torn":')
    with pytest.raises(EventLogTornTailError) as excinfo:
        append_event_log_lines(log, ['{"next":2}'])
    assert log.read_bytes() == b'{"whole":1}\n{"torn":'
    assert excinfo.value.code == "EVENT_LOG_TORN_TAIL"
    assert str(excinfo.value).endswith("Error code: EVENT_LOG_TORN_TAIL.")
    assert isinstance(excinfo.value, OSError)


def test_torn_tail_is_checked_before_the_precondition(log: Path) -> None:
    log.write_bytes(b"torn")
    seen: list[bytes] = []
    with pytest.raises(EventLogTornTailError):
        append_event_log_lines(log, ["x"], precondition=seen.append)
    assert seen == []


# ---------------------------------------------------------------------------
# Precondition, create, parents, no-follow
# ---------------------------------------------------------------------------


def test_precondition_sees_existing_bytes_and_can_refuse(log: Path) -> None:
    log.write_bytes(b"first\n")
    seen: list[bytes] = []
    append_event_log_lines(log, ["second"], precondition=seen.append)
    assert seen == [b"first\n"]

    def refuse(_existing: bytes) -> None:
        raise LookupError("no")

    with pytest.raises(LookupError):
        append_event_log_lines(log, ["third"], precondition=refuse)
    assert log.read_bytes() == b"first\nsecond\n"


def test_create_false_refuses_a_missing_log(log: Path) -> None:
    with pytest.raises(FileNotFoundError):
        append_event_log_lines(log, ["x"], create=False)
    assert not log.exists()


def test_missing_parent_raises_before_any_lock_or_directory(tmp_path: Path) -> None:
    missing = tmp_path / "absent" / "mission-events.jsonl"
    with pytest.raises(FileNotFoundError):
        append_event_log_lines(missing, ["x"])
    assert not missing.parent.exists()
    assert list(tmp_path.iterdir()) == []


def test_create_parents_creates_the_directory(repo: Path) -> None:
    target = repo / ".kittify" / "archive" / "archived-missions.jsonl"
    append_event_log_lines(target, ["x"], create_parents=True)
    assert target.read_bytes() == b"x\n"


def test_new_log_gets_the_requested_mode(log: Path) -> None:
    if os.name != "posix":
        pytest.skip("POSIX permission bits")
    append_event_log_lines(log, ["x"], mode=0o600)
    assert log.stat().st_mode & 0o777 == 0o600
    # The default follows the umask, so a group-shared checkout (umask 002) gets 0664.
    shared = log.with_name("shared.jsonl")
    previous = os.umask(0o002)
    try:
        append_event_log_lines(shared, ["x"])
    finally:
        os.umask(previous)
    assert shared.stat().st_mode & 0o777 == 0o664


def test_no_follow_refuses_a_symlink(log: Path, tmp_path: Path) -> None:
    real = tmp_path / "real.jsonl"
    real.write_bytes(b"")
    log.symlink_to(real)
    with pytest.raises(EventLogSymlinkError, match=r"Error code: EVENT_LOG_SYMLINK\.$") as excinfo:
        append_event_log_lines(log, ["x"], no_follow=True)
    assert isinstance(excinfo.value, OSError)
    assert real.read_bytes() == b""


def test_follows_a_symlink_when_allowed(log: Path, tmp_path: Path) -> None:
    real = tmp_path / "real.jsonl"
    real.write_bytes(b"")
    log.symlink_to(real)
    append_event_log_lines(log, ["x"])
    assert real.read_bytes() == b"x\n"


def test_fsyncs_the_log(log: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    synced_inodes: list[int] = []
    real_fsync = os.fsync

    def recording_fsync(fd: int) -> None:
        synced_inodes.append(os.fstat(fd).st_ino)
        real_fsync(fd)

    monkeypatch.setattr(os, "fsync", recording_fsync)
    append_event_log_lines(log, ["x"])
    # The lock record is fsynced too; the log's own inode must be among them.
    assert log.stat().st_ino in synced_inodes


@pytest.mark.parametrize("fails_with", [EventLogShortWriteError, OSError], ids=["short-write", "enospc-after-partial"])
def test_short_write_is_reported(log: Path, monkeypatch: pytest.MonkeyPatch, fails_with: type[OSError]) -> None:
    """A partial write is cut back, so no torn tail blocks the next append."""
    log.write_bytes(b'{"whole":1}\n')
    real_write = os.write

    def partial_unit_write(fd: int, payload: bytes) -> int:
        if payload != b"xyz\n":
            return real_write(fd, payload)
        written = real_write(fd, payload[:2])
        if fails_with is OSError:
            raise OSError(errno.ENOSPC, "No space left on device")
        return written

    monkeypatch.setattr(os, "write", partial_unit_write)
    with pytest.raises(fails_with) as excinfo:
        append_event_log_lines(log, ["xyz"])
    if fails_with is EventLogShortWriteError:
        assert str(excinfo.value).endswith("Error code: EVENT_LOG_SHORT_WRITE.")
    assert log.read_bytes() == b'{"whole":1}\n'


def test_every_refusal_is_an_oserror() -> None:
    for kind in (EventLogTornTailError, EventLogLockTimeoutError, EventLogLockUnavailableError, EventLogSymlinkError, EventLogShortWriteError):
        assert issubclass(kind, EventLogAppendError)
        assert issubclass(kind, OSError)
        assert kind.code.startswith("EVENT_LOG_")


# ---------------------------------------------------------------------------
# Lock-path rule (contract rule 1)
# ---------------------------------------------------------------------------


def test_lock_path_lives_under_the_git_common_dir(log: Path, repo: Path) -> None:
    lock = event_log_lock_path(log)
    assert lock.parent == (repo / ".git").resolve() / "spec-kitty-locks" / "event-logs"


@pytest.mark.skipif(os.name != "posix", reason="POSIX absolute path; normcase is the identity there")
def test_lock_path_digest_golden_value(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Contract rule 1 pinned by value: sha256 of the UTF-8 resolved path, first 32 hex.

    The Java writer (#6193) must compute this same name for this same path.
    """
    monkeypatch.setattr(event_log_append, "git_common_dir", lambda _path: tmp_path)
    anchor = Path("/srv/repo/kitty-specs/m/decisions.events.jsonl")
    assert event_log_lock_path(anchor) == tmp_path / "spec-kitty-locks" / "event-logs" / "5d011f83a018c89fa185a10c696c8293.lock"


def test_lock_path_does_not_depend_on_the_working_directory(log: Path, repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from_repo = event_log_lock_path(log)
    monkeypatch.chdir(tmp_path)
    clear_caches()
    assert event_log_lock_path(log) == from_repo


def test_lock_path_is_shared_by_every_worktree_of_one_repository(repo: Path, tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    _git(repo, "worktree", "add", "-q", str(worktree), "-b", "lane")
    clear_caches()
    main_log = repo / "kitty-specs" / "m" / "x.jsonl"
    lane_log = worktree / "kitty-specs" / "m" / "x.jsonl"
    main_log.parent.mkdir(parents=True)
    lane_log.parent.mkdir(parents=True)
    main_lock = event_log_lock_path(main_log)
    lane_lock = event_log_lock_path(lane_log)
    assert main_lock.parent == lane_lock.parent  # one lock directory per repository
    assert main_lock != lane_lock  # each worktree's file is its own log


def test_lock_path_outside_git_is_a_distinct_sibling(tmp_path: Path) -> None:
    clear_caches()
    target = tmp_path / "events.jsonl"
    assert event_log_lock_path(target) == target.resolve().with_name("events.jsonl" + NON_GIT_LOCK_SUFFIX)
    assert NON_GIT_LOCK_SUFFIX != ".lock"  # never the glossary repair lock's name


def test_git_unavailable_refuses_and_writes_nothing(log: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable(path: Path) -> Path:
        raise GitTopologyUnavailableError(path, "git: not found")

    monkeypatch.setattr(event_log_append, "git_common_dir", unavailable)
    with pytest.raises(EventLogLockUnavailableError, match=r"Error code: EVENT_LOG_LOCK_UNAVAILABLE\.$"):
        append_event_log_lines(log, ["x"])
    assert not log.exists()


def test_family_anchor_gives_one_lock_for_many_files(repo: Path) -> None:
    family = repo / "kitty-ops"
    family.mkdir()
    first = family / "01AAAA.jsonl"
    second = family / "01BBBB.jsonl"
    append_event_log_lines(first, ["a"], lock_anchor=family)
    append_event_log_lines(second, ["b"], lock_anchor=family)
    lock_dir = event_log_lock_path(family).parent
    assert sorted(p.name for p in lock_dir.iterdir()) == [event_log_lock_path(family).name]


# ---------------------------------------------------------------------------
# Exclusion, bounded wait, concurrency (NFR-002, NFR-003)
# ---------------------------------------------------------------------------


def test_lock_timeout_refuses_and_writes_nothing(log: Path) -> None:
    # Another thread holds the lock: the lock is re-entrant within one thread (#6706).
    held, release = threading.Event(), threading.Event()

    def holder() -> None:
        with event_log_lock(log):
            held.set()
            release.wait(10)

    thread = threading.Thread(target=holder)
    thread.start()
    held.wait(10)
    try:
        with pytest.raises(EventLogLockTimeoutError) as excinfo:
            append_event_log_lines(log, ["x"], timeout_s=0.2)
    finally:
        release.set()
        thread.join()
    assert excinfo.value.code == "EVENT_LOG_LOCK_TIMEOUT"
    assert str(excinfo.value).endswith("Error code: EVENT_LOG_LOCK_TIMEOUT.")
    assert not log.exists()


def _append_rows(log_path: str, writer: int) -> None:
    for row in range(_ROWS_PER_WRITER):
        append_event_log_lines(Path(log_path), [json.dumps({"writer": writer, "row": row, "pad": "x" * 200})], timeout_s=30.0)


def test_concurrent_writers_never_interleave(log: Path) -> None:
    context = multiprocessing.get_context("spawn")
    processes = [context.Process(target=_append_rows, args=(str(log), writer)) for writer in range(_WRITERS)]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=120)
        assert process.exitcode == 0
    rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == _WRITERS * _ROWS_PER_WRITER
    assert {(r["writer"], r["row"]) for r in rows} == {(w, r) for w in range(_WRITERS) for r in range(_ROWS_PER_WRITER)}


# ---------------------------------------------------------------------------
# Re-entrancy within one thread (#6706)
# ---------------------------------------------------------------------------


def test_nested_lock_on_the_same_anchor_reuses_the_held_lock(log: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    acquired: list[Path] = []
    real = event_log_append.machine_file_lock

    def counting(path: Path, **kwargs: Any) -> Any:
        acquired.append(path)
        return real(path, **kwargs)

    monkeypatch.setattr(event_log_append, "machine_file_lock", counting)
    with event_log_lock(log) as outer:
        with event_log_lock(log) as inner:
            assert inner == outer
        append_event_log_lines(log, ["a"])
        append_event_log_lines(log, ["b"])
    assert acquired == [outer]
    assert log.read_bytes() == b"a\nb\n"


def test_lock_is_taken_again_after_the_outer_block_ends(log: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    acquired: list[Path] = []
    real = event_log_append.machine_file_lock

    def counting(path: Path, **kwargs: Any) -> Any:
        acquired.append(path)
        return real(path, **kwargs)

    monkeypatch.setattr(event_log_append, "machine_file_lock", counting)
    with event_log_lock(log):
        pass
    append_event_log_lines(log, ["a"])
    assert len(acquired) == 2

    errors: list[OSError] = []

    def other_writer() -> None:
        try:
            with event_log_lock(log, timeout_s=0.5):
                pass
        except OSError as exc:
            errors.append(exc)

    thread = threading.Thread(target=other_writer)
    thread.start()
    thread.join()
    assert errors == []


def test_another_thread_still_waits_for_a_held_lock(log: Path) -> None:
    errors: list[OSError] = []

    def other_writer() -> None:
        try:
            append_event_log_lines(log, ["other"], timeout_s=0.2)
        except OSError as exc:
            errors.append(exc)

    with event_log_lock(log):
        thread = threading.Thread(target=other_writer)
        thread.start()
        thread.join()
    assert len(errors) == 1 and isinstance(errors[0], EventLogLockTimeoutError)
    assert not log.exists()
