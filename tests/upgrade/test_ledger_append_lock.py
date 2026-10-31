"""The migration ledger's append is exclusive per partition (#6613, gap G-15).

The ledger is a state ledger (`.kittify/migration-ledger.jsonl` and
`.kittify/migrations/clone-local.jsonl`). Its append is a read-modify-write: read
every line, add the new records, write a temp file, `os.replace`. Before this
mission it took no lock, so two `spec-kitty upgrade` processes on one checkout
could each read the same line set and the second `replace` dropped the first's
record. A lost `success` record re-selects an already-applied migration on the
next run, invisibly.

These tests drive the public `MigrationLedger.append` / `append_many` entry
points, not the private seam:

* FR-001/FR-003: two concurrent appends both survive (lost-update repro).
* FR-002: `append_many` is exclusive per partition.
* FR-004/NFR-002: a second appender waits for the holder, and a lock that never
  frees produces the typed error with nothing appended.
* NFR-003: the lock path needs no git; it is a dedicated sidecar, never the
  payload (the primitive truncates the file it locks).
* C-002/C-003: no `base.py` import, no record-format change.
"""

from __future__ import annotations

import importlib
import json
import subprocess
import threading
import time
from pathlib import Path

import pytest
from kernel.clock import now_utc
from kernel.locks import machine_file_lock

import specify_cli.upgrade.ledger as ledger_module
from specify_cli.upgrade.ledger import (
    LedgerRecord,
    MigrationLedger,
    MigrationLedgerLockTimeoutError,
    ledger_lock_path,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

#: How long a helper thread may take to reach or finish its section before the test fails.
JOIN_SECONDS = 20.0
#: How long the artificial read stall lasts: long enough for both threads to read, short
#: enough to stay far below ``LEDGER_LOCK_TIMEOUT_S``.
READ_STALL_SECONDS = 0.15
#: How long to observe "the contender has not completed yet" before releasing the holder.
OBSERVE_SECONDS = 0.3


def _record(migration_id: str, *, clone_local: bool = False) -> LedgerRecord:
    return LedgerRecord(
        id=migration_id,
        applied_at=now_utc(),
        result="success",
        identity=migration_id,
        content_hash="sha256:deadbeef",
        cli_version="4.0.0rc8",
        clone_local=clone_local,
    )


def _stall_reads(monkeypatch: pytest.MonkeyPatch) -> None:
    """Slow the ledger READ, so two unlocked appends both read the pre-append file.

    Stalling the read (not the write) is what makes the lost update deterministic
    rather than a race against a fast `os.replace`: both threads must be inside
    their read when the first write lands.
    """
    original = MigrationLedger._read_raw_lines

    def slow_read(path: Path) -> list[str]:
        lines = original(path)
        time.sleep(READ_STALL_SECONDS)
        return lines

    monkeypatch.setattr(MigrationLedger, "_read_raw_lines", staticmethod(slow_read))


def _start_together(targets: list[tuple[str, object]]) -> list[threading.Thread]:
    """Start one thread per ``(migration_id, callable)`` from a shared start gate."""
    gate = threading.Event()
    threads: list[threading.Thread] = []

    def run(migration_id: str, work: object) -> None:
        gate.wait(JOIN_SECONDS)
        work(migration_id)  # type: ignore[operator]

    for migration_id, work in targets:
        thread = threading.Thread(target=run, args=(migration_id, work), name=migration_id)
        threads.append(thread)
        thread.start()
    gate.set()
    return threads


def test_concurrent_appends_keep_both_records(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Two appends reading the same pre-append file must both survive (FR-001)."""
    ledger = MigrationLedger(tmp_path)
    _stall_reads(monkeypatch)

    threads = _start_together(
        [
            ("m_alpha", lambda migration_id: ledger.append(_record(migration_id))),
            ("m_beta", lambda migration_id: ledger.append(_record(migration_id))),
        ]
    )
    for thread in threads:
        thread.join(JOIN_SECONDS)
        assert not thread.is_alive(), f"{thread.name} never completed"

    recorded = {record.id for record in ledger.read_tracked()}
    assert recorded == {"m_alpha", "m_beta"}


def test_append_many_keeps_both_partitions_under_concurrency(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A multi-record append is exclusive per partition, so neither partition loses a record (FR-002)."""
    ledger = MigrationLedger(tmp_path)
    _stall_reads(monkeypatch)

    def batch(prefix: str) -> None:
        ledger.append_many([_record(f"{prefix}_tracked"), _record(f"{prefix}_clone", clone_local=True)])

    threads = _start_together([("first", batch), ("second", batch)])
    for thread in threads:
        thread.join(JOIN_SECONDS)
        assert not thread.is_alive(), f"{thread.name} never completed"

    assert {record.id for record in ledger.read_tracked()} == {"first_tracked", "second_tracked"}
    assert {record.id for record in ledger.read_clone_local()} == {"first_clone", "second_clone"}


def test_append_waits_for_a_held_ledger_lock(tmp_path: Path) -> None:
    """A second appender blocks on the sidecar lock until the holder releases it (FR-004)."""
    ledger = MigrationLedger(tmp_path)
    lock_path = ledger_lock_path(ledger.tracked_path)

    with machine_file_lock(lock_path, blocking=True, timeout_s=JOIN_SECONDS):
        thread = threading.Thread(target=lambda: ledger.append(_record("m_waited")), name="contender")
        thread.start()
        thread.join(OBSERVE_SECONDS)
        assert thread.is_alive(), "the append did not wait for the held ledger lock"
        assert ledger.read_tracked() == [], "the append wrote while the lock was held"

    thread.join(JOIN_SECONDS)
    assert not thread.is_alive()
    assert {record.id for record in ledger.read_tracked()} == {"m_waited"}


def test_append_raises_typed_error_when_the_lock_never_frees(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A lock that never frees fails loudly and appends nothing (FR-004, NFR-002)."""
    ledger = MigrationLedger(tmp_path)
    ledger.append(_record("m_before"))
    before = ledger.tracked_path.read_bytes()
    monkeypatch.setattr(ledger_module, "LEDGER_LOCK_TIMEOUT_S", 0.2)

    with (
        machine_file_lock(ledger_lock_path(ledger.tracked_path), blocking=True, timeout_s=JOIN_SECONDS),
        pytest.raises(MigrationLedgerLockTimeoutError) as caught,
    ):
        ledger.append(_record("m_dropped"))

    assert ".lock" in str(caught.value)
    assert ledger.tracked_path.read_bytes() == before, "a failed append must leave the ledger byte-identical"
    assert {record.id for record in ledger.read_tracked()} == {"m_before"}


def test_lock_path_is_a_per_ledger_file_sidecar_outside_the_checkout(tmp_path: Path) -> None:
    """The lock is keyed per ledger file, never the payload, and lives outside the project (NFR-003)."""
    ledger = MigrationLedger(tmp_path)
    tracked_lock = ledger_lock_path(ledger.tracked_path)
    clone_lock = ledger_lock_path(ledger.clone_local_path)

    assert tracked_lock != ledger.tracked_path, "the payload itself must never be the lock file"
    assert tracked_lock != clone_lock, "two partitions must never share one lock"
    assert tracked_lock != ledger_lock_path(MigrationLedger(tmp_path / "other").tracked_path), "two projects must never share one lock"
    assert not tracked_lock.is_relative_to(tmp_path), "a lock inside the checkout can dirty `git status`"


def test_an_append_leaves_git_status_clean_without_any_gitignore_entry(tmp_path: Path) -> None:
    """With no `.gitignore` at all, an append adds no untracked file: the lock is not in the checkout."""
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / ".kittify").mkdir()
    ledger = MigrationLedger(tmp_path)

    ledger.append(_record("m_status"))
    assert ledger_lock_path(ledger.tracked_path).exists(), "the probe cannot see a lock file that was never created"

    status = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=tmp_path, check=True, capture_output=True, text=True)
    assert ".lock" not in status.stdout
    assert ".kittify/migrations" not in status.stdout


def test_append_outside_a_git_repository(tmp_path: Path) -> None:
    """The lock path needs no git invocation, so a non-repository project still appends (NFR-003)."""
    assert not (tmp_path / ".git").exists()
    ledger = MigrationLedger(tmp_path)

    ledger.append(_record("m_no_git"))

    assert {record.id for record in ledger.read_tracked()} == {"m_no_git"}


def test_nested_append_does_not_self_deadlock(tmp_path: Path) -> None:
    """A thread already holding the ledger lock can append without waiting on itself (FR-004)."""
    ledger = MigrationLedger(tmp_path)

    with machine_file_lock(ledger_lock_path(ledger.tracked_path), blocking=True, timeout_s=JOIN_SECONDS, reentrant=True):
        ledger.append(_record("m_nested"))

    assert {record.id for record in ledger.read_tracked()} == {"m_nested"}


def test_appended_record_bytes_are_unchanged(tmp_path: Path) -> None:
    """The lock changes no byte of the record it protects (C-003)."""
    ledger = MigrationLedger(tmp_path)
    record = _record("m_bytes")

    ledger.append(record)

    assert ledger.tracked_path.read_text(encoding="utf-8") == json.dumps(record.to_dict(), ensure_ascii=False) + "\n"


def test_ledger_module_does_not_import_the_migration_base(tmp_path: Path) -> None:
    """The ledger keeps reaching migration identity defensively, never by importing base (C-002)."""
    source = Path(importlib.import_module("specify_cli.upgrade.ledger").__file__ or "").read_text(encoding="utf-8")

    assert "from .migrations.base" not in source
    assert "from specify_cli.upgrade.migrations.base" not in source
