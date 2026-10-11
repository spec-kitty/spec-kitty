"""#6062: baseline capture must never wait on the ``for_review`` gate's
machine-wide scoped-run lock (``pre-review-gate-run.lock``).

A claim that captured a baseline reused the head runner's launch/reap machinery
(``baseline._run_command_for_baseline`` -> ``pre_review_gate._run_raw_command``),
which also entered the gate lock -- so a *claim* queued on a lock that belongs to
the ``move-task --to for_review`` regression gate (#2493). That coupling is the
#6062 hang.

These tests hold the REAL gate lock and observe behaviour:
- the baseline launcher completes while the lock is held;
- the ``for_review`` head runner (default serialization) does wait on it (#2493
  preserved) -- the positive control that proves the held lock is the real one.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from kernel.locks import machine_file_lock
from specify_cli.paths import get_runtime_root
from specify_cli.review import pre_review_gate

pytestmark = [pytest.mark.fast]

_ACQUIRE_TIMEOUT_S = 3.0
_BASELINE_DEADLINE_S = 1.5  # < the acquire timeout: a lock-coupled run cannot finish in time


@pytest.fixture
def held_gate_lock(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Hold the real ``pre-review-gate-run.lock`` for the duration of the test."""
    monkeypatch.setattr(pre_review_gate, "_LOCK_ACQUIRE_TIMEOUT_DEFAULT", _ACQUIRE_TIMEOUT_S)
    lock_path = get_runtime_root().base / "gate-locks" / pre_review_gate._SCOPED_RUN_LOCK_FILENAME
    with machine_file_lock(lock_path, blocking=True, timeout_s=5.0):
        yield


def _run_in_thread(target: object) -> threading.Thread:
    thread = threading.Thread(target=target, daemon=True)  # type: ignore[arg-type]
    thread.start()
    return thread


@pytest.mark.skipif(pre_review_gate.is_windows(), reason="the gate lock is a no-op on Windows")
def test_baseline_launcher_completes_while_gate_lock_is_held(held_gate_lock: None, tmp_path: Path) -> None:
    from specify_cli.review.baseline import _run_command_for_baseline

    thread = _run_in_thread(lambda: _run_command_for_baseline(["true"], cwd=tmp_path))
    thread.join(timeout=_BASELINE_DEADLINE_S)

    assert not thread.is_alive(), "baseline capture must not wait on the for_review gate lock (#6062)"


@pytest.mark.skipif(pre_review_gate.is_windows(), reason="the gate lock is a no-op on Windows")
def test_for_review_head_run_still_waits_on_gate_lock(held_gate_lock: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """#2493 positive control: the head run serializes (waits out the acquire bound)."""
    monkeypatch.setattr(pre_review_gate, "_LOCK_ACQUIRE_TIMEOUT_DEFAULT", 1.0)

    started = time.monotonic()
    pre_review_gate._run_raw_command(
        ["true"],
        repo_root=tmp_path,
        timeout=5,
        progress_callback=None,
        monotonic=time.monotonic,
        wait=pre_review_gate._default_process_wait,
    )

    assert time.monotonic() - started >= 0.9, "the for_review head run must keep serializing on the gate lock (#2493)"
