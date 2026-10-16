"""Deterministic interleavings of identical terminal calls (#5681, FR-007, NFR-001/002).

A terminal call (resolve / defer / cancel) holds the decisions lock across the
index save, the artifact write and the terminal event.  Every test here
pauses the REAL emit on its first call so the interleaving is decided by
events, not by timing luck; every thread is a daemon with a bounded join.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from kernel.locks import LockAcquireTimeout
from specify_cli.decisions import emit as _emit
from specify_cli.decisions.index_fold import fold_events
from specify_cli.decisions.models import DecisionStatus, DecisionTerminalResponse, IndexEntry, OriginFlow
from specify_cli.decisions.service import open_decision, resolve_decision

pytestmark = [pytest.mark.unit]

MISSION_ID = "01KTEST_MISSION_ID_000002"
MISSION_SLUG = "concurrency-mission"
_WAIT_S = 20.0


def _mission_dir(repo_root: Path) -> Path:
    return repo_root / "kitty-specs" / MISSION_SLUG


def _open(repo_root: Path, key: str = "team_size") -> str:
    mission_dir = _mission_dir(repo_root)
    mission_dir.mkdir(parents=True, exist_ok=True)
    meta = {"mission_id": MISSION_ID, "mission_slug": MISSION_SLUG}
    (mission_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    resp = open_decision(
        repo_root,
        MISSION_SLUG,
        origin_flow=OriginFlow.CHARTER,
        step_id=f"step-{key}",
        input_key=key,
        question="How large is the team?",
        options=("1-5", "6-20"),
        actor="alice",
    )
    return str(resp.decision_id)


def _events(repo_root: Path) -> list[dict[str, Any]]:
    path = _mission_dir(repo_root) / "status.events.jsonl"
    if not path.exists():
        return []
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _resolved_rows(repo_root: Path, did: str) -> list[dict[str, Any]]:
    return [
        e
        for e in _events(repo_root)
        if e["event_type"] == "DecisionPointResolved" and e["payload"]["decision_point_id"] == did and e["payload"]["terminal_outcome"] == "resolved"
    ]


def _resolve(repo_root: Path, did: str, answer: str = "1-5") -> DecisionTerminalResponse:
    resp: DecisionTerminalResponse = resolve_decision(repo_root, MISSION_SLUG, did, final_answer=answer, actor="alice")
    return resp


class _Pause:
    """Pause the FIRST real ``emit_decision_resolved`` call until released."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.reached = threading.Event()
        self.release = threading.Event()
        self._real = _emit.emit_decision_resolved
        self._first = True
        self._guard = threading.Lock()
        monkeypatch.setattr(_emit, "emit_decision_resolved", self._wrapper)

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


def _fold(repo_root: Path, did: str) -> IndexEntry:
    rows = [e for e in _events(repo_root) if e["payload"].get("decision_point_id") == did]
    return fold_events(rows)


@pytest.mark.timeout(60)
def test_first_attempt_paused_after_index_save_blocks_identical_retry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A paused first attempt (index saved, event pending) blocks an identical retry.

    Red on the base (the retry returns at once having written nothing) and red
    against a repair-only fix (the retry writes a second row).
    """
    did = _open(tmp_path)
    pause = _Pause(monkeypatch)
    a = _Worker(lambda: _resolve(tmp_path, did)).start()
    assert pause.reached.wait(_WAIT_S)
    b = _Worker(lambda: _resolve(tmp_path, did)).start()
    b.thread.join(0.5)
    assert b.thread.is_alive(), "retry must wait on the decisions lock held by the first attempt"

    pause.release.set()
    a.finish()
    b.finish()

    assert len(_resolved_rows(tmp_path, did)) == 1
    assert a.result.idempotent is False and a.result.event_lamport is not None
    assert b.result.idempotent is True and b.result.event_lamport is None
    assert _fold(tmp_path, did).status == DecisionStatus.RESOLVED


@pytest.mark.timeout(60)
def test_paused_retry_blocks_second_retry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    did = _open(tmp_path)
    with monkeypatch.context() as m:
        m.setattr(_emit, "_append_raw_event", _raise_oserror)
        with pytest.raises(OSError, match="simulated interruption"):
            _resolve(tmp_path, did)
    assert _resolved_rows(tmp_path, did) == []

    pause = _Pause(monkeypatch)
    a = _Worker(lambda: _resolve(tmp_path, did)).start()
    assert pause.reached.wait(_WAIT_S)
    b = _Worker(lambda: _resolve(tmp_path, did)).start()
    b.thread.join(0.5)
    assert b.thread.is_alive()

    pause.release.set()
    a.finish()
    b.finish()

    assert len(_resolved_rows(tmp_path, did)) == 1
    lamports = [r.event_lamport for r in (a.result, b.result)]
    assert sum(lp is not None for lp in lamports) == 1
    assert _fold(tmp_path, did).status == DecisionStatus.RESOLVED


@pytest.mark.timeout(60)
def test_double_first_submit_writes_one_event(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ratchet (green on the base): guards against the fix introducing a double write."""
    did = _open(tmp_path)
    pause = _Pause(monkeypatch)
    a = _Worker(lambda: _resolve(tmp_path, did)).start()
    assert pause.reached.wait(_WAIT_S)
    b = _Worker(lambda: _resolve(tmp_path, did)).start()
    b.thread.join(0.3)
    pause.release.set()
    a.finish()
    b.finish()

    assert len(_resolved_rows(tmp_path, did)) == 1


def _raise_oserror(*_a: Any, **_k: Any) -> None:
    raise OSError("simulated interruption")


@pytest.mark.timeout(90)
def test_terminal_calls_do_not_deadlock_with_other_decision_lock_holders(tmp_path: Path) -> None:
    """Ratchet (NFR-002 (2)): terminal calls, an open, the doctor repair and a status-lock writer coexist."""
    from specify_cli.cli.commands import _decisions_doctor as doctor
    from specify_cli.status import feature_status_lock, mission_lock_key
    from specify_cli.workspace.root_resolver import resolve_status_lock_root

    d1 = _open(tmp_path, "k1")
    d2 = _open(tmp_path, "k2")
    feature_dir = _mission_dir(tmp_path)
    barrier = threading.Barrier(4, timeout=_WAIT_S)

    def status_writer() -> None:
        lock_root = resolve_status_lock_root(feature_dir)
        with feature_status_lock(lock_root, mission_lock_key(feature_dir, repo_root=lock_root)):
            pass

    def doctor_repair() -> None:
        doctor._repair(doctor._mission_dir(tmp_path, MISSION_SLUG), doctor._ledger_dir(tmp_path, MISSION_SLUG))

    def gated(fn: Callable[[], Any]) -> Callable[[], Any]:
        def run() -> Any:
            barrier.wait()
            return fn()

        return run

    workers = [
        _Worker(gated(lambda: (_resolve(tmp_path, d1), _resolve(tmp_path, d2)))),
        _Worker(gated(lambda: _open(tmp_path, "k3"))),
        _Worker(gated(doctor_repair)),
        _Worker(gated(status_writer)),
    ]
    for w in workers:
        w.start()
    for w in workers:
        w.finish()

    events_dir = doctor._mission_dir(tmp_path, MISSION_SLUG)
    ledger_dir = doctor._ledger_dir(tmp_path, MISSION_SLUG)
    report, _ = doctor._diagnose(events_dir, ledger_dir, MISSION_SLUG)
    assert report.clean


@pytest.mark.timeout(60)
def test_decisions_lock_waiter_times_out_and_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-002 (3): a waiter that outlives the lock timeout fails closed and writes nothing."""
    from specify_cli.decisions import service

    d1 = _open(tmp_path, "k1")
    d2 = _open(tmp_path, "k2")
    pause = _Pause(monkeypatch)
    a = _Worker(lambda: _resolve(tmp_path, d1)).start()
    assert pause.reached.wait(_WAIT_S)

    index_path = _mission_dir(tmp_path) / "decisions" / "index.json"
    artifact = _mission_dir(tmp_path) / "decisions" / f"DM-{d2}.md"
    before = (index_path.read_bytes(), artifact.read_bytes(), len(_events(tmp_path)))
    monkeypatch.setattr(service, "_LOCK_ACQUIRE_TIMEOUT_S", 0.3)
    b = _Worker(lambda: _resolve(tmp_path, d2)).start()
    b.thread.join(10)
    assert not b.thread.is_alive()
    assert isinstance(b.error, LockAcquireTimeout)
    assert (index_path.read_bytes(), artifact.read_bytes(), len(_events(tmp_path))) == before

    pause.release.set()
    a.finish()
    monkeypatch.setattr(service, "_LOCK_ACQUIRE_TIMEOUT_S", 10.0)
    assert _resolve(tmp_path, d2).event_lamport is not None
    assert len(_resolved_rows(tmp_path, d2)) == 1
