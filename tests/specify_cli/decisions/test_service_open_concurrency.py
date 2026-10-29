"""Deterministic interleavings of identical opens (#4848 open half, FR-001/FR-002, NFR-001/002).

An open holds the decisions lock across the dedup lookup, the index append,
the artifact write and the opening event; an idempotent retry holds it across
the "is the opening in the log?" check and its repair.  Every test here
pauses the REAL ``emit_decision_opened`` on its first call so the interleaving
is decided by events, not by timing luck; every thread is a daemon with a
bounded join.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from specify_cli.decisions import emit as _emit
from specify_cli.decisions.index_fold import fold_events
from specify_cli.decisions.models import DecisionOpenResponse, DecisionStatus, IndexEntry, OriginFlow
from specify_cli.decisions.service import open_decision

pytestmark = [pytest.mark.unit]

MISSION_ID = "01KTEST_MISSION_ID_000003"
MISSION_SLUG = "open-concurrency-mission"
_WAIT_S = 20.0


def _mission_dir(repo_root: Path) -> Path:
    return repo_root / "kitty-specs" / MISSION_SLUG


def _setup(repo_root: Path) -> None:
    mission_dir = _mission_dir(repo_root)
    mission_dir.mkdir(parents=True, exist_ok=True)
    meta = {"mission_id": MISSION_ID, "mission_slug": MISSION_SLUG}
    (mission_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def _open(repo_root: Path) -> DecisionOpenResponse:
    resp: DecisionOpenResponse = open_decision(
        repo_root,
        MISSION_SLUG,
        origin_flow=OriginFlow.CHARTER,
        step_id="step-team-size",
        input_key="team_size",
        question="How large is the team?",
        options=("1-5", "6-20"),
        actor="alice",
    )
    return resp


def _events(repo_root: Path) -> list[dict[str, Any]]:
    path = _mission_dir(repo_root) / "status.events.jsonl"
    if not path.exists():
        return []
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _opened_rows(repo_root: Path) -> list[dict[str, Any]]:
    return [e for e in _events(repo_root) if e["event_type"] == "DecisionPointOpened"]


def _fold(repo_root: Path, did: str) -> IndexEntry:
    rows = [e for e in _events(repo_root) if e["payload"].get("decision_point_id") == did]
    return fold_events(rows)


def _raise_oserror(*_a: Any, **_k: Any) -> None:
    raise OSError("simulated interruption")


def _interrupted_open(repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Open once with the event append failing: the index entry is saved, no row is written."""
    with monkeypatch.context() as m:
        m.setattr(_emit, "_append_raw_event", _raise_oserror)
        with pytest.raises(OSError, match="simulated interruption"):
            _open(repo_root)
    index = json.loads((_mission_dir(repo_root) / "decisions" / "index.json").read_text(encoding="utf-8"))
    assert len(index["entries"]) == 1
    assert _opened_rows(repo_root) == []


class _Pause:
    """Pause the FIRST real ``emit_decision_opened`` call until released."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.reached = threading.Event()
        self.release = threading.Event()
        self._real = _emit.emit_decision_opened
        self._first = True
        self._guard = threading.Lock()
        monkeypatch.setattr(_emit, "emit_decision_opened", self._wrapper)

    def _wrapper(self, *args: Any, **kwargs: Any) -> int:
        with self._guard:
            first, self._first = self._first, False
        if first:
            self.reached.set()
            assert self.release.wait(_WAIT_S), "pause was never released"
        return int(self._real(*args, **kwargs))


class _Worker:
    """Run *fn* on a daemon thread, capturing its result or exception."""

    def __init__(self, fn: Callable[[], Any]) -> None:
        self.result: Any = None
        self.error: BaseException | None = None
        self._fn = fn
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        try:
            self.result = self._fn()
        except BaseException as exc:  # captured for the asserting test thread
            self.error = exc

    def start(self) -> _Worker:
        self.thread.start()
        return self

    def finish(self, timeout: float = 30.0) -> None:
        self.thread.join(timeout)
        assert not self.thread.is_alive(), "worker did not finish"
        assert self.error is None, repr(self.error)


def _race_with_paused_first(repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[_Worker, _Worker, bool]:
    """Pause open A inside its opening append, start identical open B, then release A.

    Returns ``(a, b, b_was_blocked)``. ``b_was_blocked`` records whether B was
    still waiting (on the decisions lock) while A was paused; it is asserted
    by the caller AFTER the row count, so a red run shows the duplicate row.
    """
    pause = _Pause(monkeypatch)
    a = _Worker(lambda: _open(repo_root)).start()
    assert pause.reached.wait(_WAIT_S)
    b = _Worker(lambda: _open(repo_root)).start()
    b.thread.join(0.5)
    b_was_blocked = b.thread.is_alive()

    pause.release.set()
    a.finish()
    b.finish()
    return a, b, b_was_blocked


@pytest.mark.timeout(60)
def test_first_open_paused_in_emit_blocks_identical_open(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ARM A (FR-001): a fresh open paused inside its opening append blocks an identical open.

    Red on the planning base: the lock covered only the index append, so the
    identical open found the entry, saw no row yet and wrote its own.
    """
    _setup(tmp_path)
    a, b, b_was_blocked = _race_with_paused_first(tmp_path, monkeypatch)

    assert len(_opened_rows(tmp_path)) == 1
    assert b_was_blocked, "identical open must wait on the decisions lock held by the first open"
    assert a.result.idempotent is False and a.result.event_lamport is not None
    # NFR-002: the blocked open records nothing itself (one append per lock hold).
    assert b.result.idempotent is True and b.result.event_lamport is None
    assert b.result.decision_id == a.result.decision_id
    assert _fold(tmp_path, a.result.decision_id).status == DecisionStatus.OPEN


@pytest.mark.timeout(60)
def test_retries_after_interrupted_open_write_one_opening(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ARM B (FR-002): after an interrupted open, two concurrent retries repair the opening once.

    Red on the planning base: the repair's check and append ran outside the
    lock, so both retries saw the row missing and both appended it.
    """
    _setup(tmp_path)
    _interrupted_open(tmp_path, monkeypatch)

    a, b, b_was_blocked = _race_with_paused_first(tmp_path, monkeypatch)

    assert len(_opened_rows(tmp_path)) == 1
    assert b_was_blocked, "second retry must wait on the decisions lock held by the repairing retry"
    assert a.result.idempotent is True and a.result.event_lamport is not None
    assert b.result.idempotent is True and b.result.event_lamport is None
    assert b.result.decision_id == a.result.decision_id
    assert _fold(tmp_path, a.result.decision_id).status == DecisionStatus.OPEN


@pytest.mark.timeout(60)
def test_serial_identical_opens_write_one_opening(tmp_path: Path) -> None:
    """Serial control (green on the base): an identical open after a completed one writes nothing."""
    _setup(tmp_path)
    first = _open(tmp_path)
    second = _open(tmp_path)

    assert len(_opened_rows(tmp_path)) == 1
    assert first.idempotent is False and first.event_lamport is not None
    assert second.idempotent is True and second.event_lamport is None
    assert second.decision_id == first.decision_id


@pytest.mark.timeout(60)
def test_serial_retries_after_interrupted_open_write_one_opening(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Serial control (green on the base): the first retry repairs, the second finds the row."""
    _setup(tmp_path)
    _interrupted_open(tmp_path, monkeypatch)

    first = _open(tmp_path)
    second = _open(tmp_path)

    assert len(_opened_rows(tmp_path)) == 1
    assert first.idempotent is True and first.event_lamport is not None
    assert second.idempotent is True and second.event_lamport is None
    assert _fold(tmp_path, first.decision_id).status == DecisionStatus.OPEN


def _open_key(repo_root: Path, key: str) -> DecisionOpenResponse:
    resp: DecisionOpenResponse = open_decision(
        repo_root,
        MISSION_SLUG,
        origin_flow=OriginFlow.CHARTER,
        step_id=f"step-{key}",
        input_key=key,
        question=f"Question {key}?",
        options=("a", "b"),
        actor="alice",
    )
    return resp


class _StatusLockHolder:
    """Hold the REAL Mission status lock on a daemon thread until released."""

    def __init__(self, repo_root: Path) -> None:
        self.held = threading.Event()
        self.release = threading.Event()
        self._feature_dir = _mission_dir(repo_root)
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        from specify_cli.status import feature_status_lock, mission_lock_key
        from specify_cli.workspace.root_resolver import resolve_status_lock_root

        lock_root = resolve_status_lock_root(self._feature_dir)
        with feature_status_lock(lock_root, mission_lock_key(self._feature_dir, repo_root=lock_root)):
            self.held.set()
            assert self.release.wait(_WAIT_S), "status lock holder was never released"

    def start(self) -> _StatusLockHolder:
        self.thread.start()
        assert self.held.wait(_WAIT_S)
        return self


@pytest.mark.timeout(60)
def test_distinct_open_waits_without_bound_behind_open_held_on_status_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """S1 (operator ruling): an open waits on the decisions lock without a time bound.

    Open A holds the decisions lock while its opening append waits (without a
    bound) on the Mission status lock another writer holds. Open B, of a
    DIFFERENT decision, must wait behind A and then succeed -- not fail with a
    lock timeout once the (here shortened) bounded wait expires.

    Red on 581b5c46: B raised ``LockAcquireTimeout`` after the bounded wait.
    """
    from specify_cli.decisions import service

    _setup(tmp_path)
    monkeypatch.setattr(service, "_LOCK_ACQUIRE_TIMEOUT_S", 0.5)
    holder = _StatusLockHolder(tmp_path).start()

    a_in_emit = threading.Event()
    real_emit = _emit.emit_decision_opened

    def _signal_then_emit(*args: Any, **kwargs: Any) -> int:
        a_in_emit.set()
        return int(real_emit(*args, **kwargs))

    monkeypatch.setattr(_emit, "emit_decision_opened", _signal_then_emit)
    a = _Worker(lambda: _open_key(tmp_path, "k1")).start()
    assert a_in_emit.wait(_WAIT_S), "open A never reached its opening append"
    b = _Worker(lambda: _open_key(tmp_path, "k2")).start()
    b.thread.join(1.5)  # three times the shortened bound
    b_waiting = b.thread.is_alive()
    b_error = b.error

    holder.release.set()
    holder.thread.join(_WAIT_S)
    a.finish()
    assert b_error is None, repr(b_error)
    assert b_waiting, "open B must still be waiting on the decisions lock, not have given up"
    b.finish()

    index = json.loads((_mission_dir(tmp_path) / "decisions" / "index.json").read_text(encoding="utf-8"))
    assert len(index["entries"]) == 2
    assert len(_opened_rows(tmp_path)) == 2
    assert a.result.decision_id != b.result.decision_id
