"""Deterministic interleavings of identical terminal calls (#5681, FR-007, NFR-001/002).

A terminal call (resolve / defer / cancel) holds the decisions lock across the
index save, the artifact write and the terminal event.  Every test here
pauses the REAL emit on its first call so the interleaving is decided by
events, not by timing luck; every thread is a daemon.

This file owns exactly two wall clocks, and no test here inherits one from the
product (#6773):

* ``_WAIT_S`` -- a rendezvous participant must reach (or leave) its event.  A
  failure here names the missed rendezvous.
* ``_DEADLOCK_BUDGET_S`` -- the single backstop deciding "stuck": a worker that
  has not returned by then is deadlocked, and its failure carries a thread dump
  plus the decisions-lock holder record (``_deadlock_report``).

``_WAIT_S`` is the largest legitimate wait any scenario can incur, so
``_DEADLOCK_BUDGET_S`` is sized above it and below every ``@pytest.mark.timeout``
marker in this file: a genuine deadlock must produce this file's verdict, never
a bare ``Failed: Timeout`` from the marker.

The coexistence scenario additionally pins the decisions-lock acquire bound it
runs under (``_run_coexistence``), so a holder that is merely slow on a loaded
runner can never be reported as a deadlock.  The product's bounded refusal keeps
its own coverage in ``test_decisions_lock_waiter_times_out_and_writes_nothing``.
"""

from __future__ import annotations

import faulthandler
import io
import json
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from specify_cli.decisions import emit as _emit
from specify_cli.decisions import service as _service
from specify_cli.decisions import store as _store
from specify_cli.decisions.index_fold import fold_events
from specify_cli.decisions.models import DecisionErrorCode, DecisionStatus, DecisionTerminalResponse, IndexEntry, OriginFlow
from specify_cli.decisions.service import DecisionError, open_decision, resolve_decision

pytestmark = [pytest.mark.unit]

MISSION_ID = "01KTEST_MISSION_ID_000002"
MISSION_SLUG = "concurrency-mission"
#: A rendezvous participant must reach its event (see ``_Pause``).  Bounded so a
#: missed rendezvous fails by name instead of hanging the worker.
_WAIT_S = 20.0
#: The ONE deadline that decides "stuck" (#6773).  ``_WAIT_S`` is the largest
#: legitimate wait inside a scenario, so this keeps more than 2x headroom over it
#: and stays below every ``@pytest.mark.timeout`` marker in the file (60 s on the
#: pause-driven tests, 90 s on the coexistence ratchet): a genuine deadlock
#: produces this file's verdict (a thread dump plus the decisions-lock holder),
#: never a bare ``Failed: Timeout`` from the marker.
_DEADLOCK_BUDGET_S = 45.0


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


def _deadlock_report(repo_root: Path | None) -> str:
    """Diagnose a join that timed out: live thread stacks and the decisions lock state.

    ``kernel.locks`` truncates a lock file on release, so a non-empty record names
    the holder that never let go and an empty one names a released lock.
    """
    buffer = io.StringIO()
    buffer.write("\n\nlive threads (the participant that never returned is in here):\n")
    # ``faulthandler`` writes to a real file descriptor, so it cannot target the
    # StringIO directly; a temporary file keeps the dump off stdout.
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as dump:
        faulthandler.dump_traceback(file=dump, all_threads=True)
        dump.seek(0)
        buffer.write(dump.read())
    lock_files = sorted((_mission_dir(repo_root) / "decisions").glob("*.lock")) if repo_root is not None else []
    if lock_files:
        buffer.write("\ndecisions lock files (truncated on release, so a record names the holder):\n")
        for path in lock_files:
            try:
                record = path.read_text(encoding="utf-8").strip()
            except OSError as exc:  # pragma: no cover - unreadable sidecar
                record = f"<unreadable: {exc}>"
            buffer.write(f"  {path}: {record or '<empty: released>'}\n")
    return buffer.getvalue()


class _Worker:
    """Run *fn* on a daemon thread, capturing its result or exception."""

    def __init__(self, fn: Callable[[], Any], *, repo_root: Path | None = None) -> None:
        self.result: Any = None
        self.error: BaseException | None = None
        self._fn = fn
        self._repo_root = repo_root
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        try:
            self.result = self._fn()
        except BaseException as exc:  # captured for the asserting test thread
            self.error = exc

    def start(self) -> _Worker:
        self.thread.start()
        return self

    def finish(self, timeout: float = _DEADLOCK_BUDGET_S) -> None:
        self.thread.join(timeout)
        if self.thread.is_alive():
            raise AssertionError(f"worker did not finish within {timeout:g}s -- a participant is stuck, not merely slow{_deadlock_report(self._repo_root)}")
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


def _run_coexistence(tmp_path: Path, *, slow_hold_s: float = 0.0) -> None:
    """Run the four-participant coexistence interleaving (#6773, NFR-002 (2)).

    The scenario owns the decisions-lock acquire bound it runs under.  The
    product bounds that wait at ``_LOCK_ACQUIRE_TIMEOUT_S`` (10 s) because a
    caller must fail loudly rather than hang, and that refusal is correct: it is
    pinned by ``test_decisions_lock_waiter_times_out_and_writes_nothing``.
    Inside THIS scenario a bounded wait would let a loaded runner turn "the
    holder is slow" into ``LOCK_TIMEOUT`` and be reported as a failed worker --
    the false red #6773 diagnosed.  Pinning the bound to ``None`` (the same
    unbounded wait ``open_decision`` already uses for ``_OPEN_LOCK_WAIT_S``)
    leaves ``_DEADLOCK_BUDGET_S`` as the only deadline, so the verdict is "a
    participant never returned", never "a participant was slow".

    ``slow_hold_s`` injects a FINITE hold into every holder's critical section;
    it exists so the proof in
    ``test_coexistence_ratchet_is_indifferent_to_the_ambient_acquire_bound`` can
    exercise a slow-but-finite environment through the same scenario body.
    """
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

    # The context manager restores both constants even when a worker raises, so a
    # sibling test in the same xdist worker never inherits an unbounded acquire.
    with pytest.MonkeyPatch.context() as pinned:
        pinned.setattr(_service, "_LOCK_ACQUIRE_TIMEOUT_S", None)
        pinned.setattr(doctor, "_LOCK_ACQUIRE_TIMEOUT_S", None)
        if slow_hold_s:
            real_save_index = _store.save_index

            def slow_save_index(*args: Any, **kwargs: Any) -> None:
                time.sleep(slow_hold_s)
                real_save_index(*args, **kwargs)

            pinned.setattr(_store, "save_index", slow_save_index)

        workers = [
            _Worker(gated(lambda: (_resolve(tmp_path, d1), _resolve(tmp_path, d2))), repo_root=tmp_path),
            _Worker(gated(lambda: _open(tmp_path, "k3")), repo_root=tmp_path),
            _Worker(gated(doctor_repair), repo_root=tmp_path),
            _Worker(gated(status_writer), repo_root=tmp_path),
        ]
        for w in workers:
            w.start()
        # If one participant is stuck, reporting it is the whole point: the first
        # failing finish raises (with the report) and the remaining daemon workers
        # are abandoned rather than waited on a second time. They only touch this
        # test's own tmp_path locks, so nothing leaks into a later test.
        for w in workers:
            w.finish()

    events_dir = doctor._mission_dir(tmp_path, MISSION_SLUG)
    ledger_dir = doctor._ledger_dir(tmp_path, MISSION_SLUG)
    report, _ = doctor._diagnose(events_dir, ledger_dir, MISSION_SLUG)
    assert report.clean


@pytest.mark.timeout(90)
def test_terminal_calls_do_not_deadlock_with_other_decision_lock_holders(tmp_path: Path) -> None:
    """Ratchet (NFR-002 (2)): terminal calls, an open, the doctor repair and a status-lock writer coexist."""
    _run_coexistence(tmp_path)


@pytest.mark.timeout(60)
def test_coexistence_ratchet_is_indifferent_to_the_ambient_acquire_bound(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A slow-but-finite holder is not a deadlock, whatever bound is ambient (#6773).

    Red before the fix, with this exact injection: the scenario inherited the
    ambient bound, so a holder slower than it made a peer refuse with
    ``LOCK_TIMEOUT`` and the ratchet reported a deadlock that did not exist (the
    reproducible pre-fix output is recorded in the mission's
    ``research/deadlock-budget-probe.md``).  The ambient bound here is tighter
    than the injected hold, so this stays non-vacuous: it can only pass because
    the scenario pins its own bound.
    """
    monkeypatch.setattr(_service, "_LOCK_ACQUIRE_TIMEOUT_S", 0.1)
    _run_coexistence(tmp_path, slow_hold_s=0.3)


@pytest.mark.timeout(60)
def test_deadlock_backstop_reports_a_participant_that_never_finishes(tmp_path: Path) -> None:
    """The backstop must bite, and name the lock (FR-004): a parked worker reds the verdict.

    Without this, the "no false red" fix would have bought silence instead of
    determinism: a participant that never returns must still fail the ratchet,
    inside its budget, with a report that names the decisions lock.
    """
    _open(tmp_path)  # mint the ledger so the report has a decisions lock path to name
    parked = threading.Event()
    worker = _Worker(parked.wait, repo_root=tmp_path).start()
    try:
        with pytest.raises(AssertionError) as raised:
            worker.finish(timeout=0.2)
    finally:
        parked.set()
        worker.thread.join(_WAIT_S)
    assert not worker.thread.is_alive(), "the parked worker must be joined before the test returns"

    message = str(raised.value)
    assert "worker did not finish" in message
    assert "index.json.lock" in message, message
    assert "in wait" in message and "threading.py" in message, message  # the parked frame


@pytest.mark.timeout(60)
def test_decisions_lock_waiter_times_out_and_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-002 (3): a waiter that outlives the lock timeout fails closed and writes nothing.

    S1 (operator ruling): the timeout surfaces as a structured
    ``DecisionError(LOCK_TIMEOUT)`` naming the lock and telling the caller to
    retry -- never a bare ``LockAcquireTimeout`` traceback. Red on 581b5c46.
    """
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
    assert isinstance(b.error, DecisionError), repr(b.error)
    assert b.error.code is DecisionErrorCode.LOCK_TIMEOUT
    lock_path = _mission_dir(tmp_path) / "decisions" / "index.json.lock"
    assert b.error.details["lock_path"] == str(lock_path)
    assert b.error.details["decision_id"] == d2
    assert str(lock_path) in str(b.error)
    assert "retry" in str(b.error).lower()
    assert (index_path.read_bytes(), artifact.read_bytes(), len(_events(tmp_path))) == before

    pause.release.set()
    a.finish()
    monkeypatch.setattr(service, "_LOCK_ACQUIRE_TIMEOUT_S", 10.0)
    assert _resolve(tmp_path, d2).event_lamport is not None
    assert len(_resolved_rows(tmp_path, d2)) == 1
