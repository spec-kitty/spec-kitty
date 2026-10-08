"""Deterministic two-writer overlap harness for ``meta.json`` read-modify-write tests.

Writer A is paused *just before it writes* ``meta.json`` (so it already holds a copy read earlier). Writer B, a
Mission-locked setter, then runs on another thread. A is released by whichever of these happens first, neither of
them a timer:

* B finished its whole write (nothing stopped it, so A held no lock: A's stale copy now overwrites B's field), or
* B tried to take the Mission lock and found it held (B is observably waiting behind A, so A holds the lock).

The probe is a non-blocking first attempt on the lock B is about to wait for, so "B is waiting" is observed, not
assumed. ``JOIN_SECONDS`` only bounds a hung test.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any

import pytest

import specify_cli.mission_metadata as mm
import specify_cli.status.mission_write as mission_write
from specify_cli.status.locking import FeatureStatusLockTimeoutError

WRITER_A = "writer-a"
JOIN_SECONDS = 30.0
META_NAME = "meta.json"


def run_overlap(
    monkeypatch: pytest.MonkeyPatch,
    writer_a: Callable[[], object],
    writer_b: Callable[[], object],
) -> list[Exception]:
    """Run *writer_a* paused before its meta.json write while *writer_b* runs; return both errors."""
    a_at_write = threading.Event()
    release_a = threading.Event()
    errors: list[Exception] = []
    real_atomic_write = mm.atomic_write
    real_write_text = Path.write_text
    real_lock = mission_write.feature_status_lock

    def pause_if_writer_a(path: Path) -> None:
        if threading.current_thread().name == WRITER_A and path.name == META_NAME and not a_at_write.is_set():
            a_at_write.set()
            release_a.wait(JOIN_SECONDS)

    def paused_atomic_write(path: Path, *args: Any, **kwargs: Any) -> None:
        pause_if_writer_a(path)
        real_atomic_write(path, *args, **kwargs)

    def paused_write_text(self: Path, *args: Any, **kwargs: Any) -> int:
        pause_if_writer_a(self)
        return real_write_text(self, *args, **kwargs)

    @contextmanager
    def probing_lock(root: Path, key: str, *, timeout: float) -> Iterator[Path]:
        if threading.current_thread().name == WRITER_A:
            with real_lock(root, key, timeout=timeout) as held:
                yield held
            return
        with ExitStack() as stack:
            try:
                held = stack.enter_context(real_lock(root, key, timeout=0.0))
            except FeatureStatusLockTimeoutError:
                release_a.set()  # B found the lock held: it is waiting behind writer A
                held = stack.enter_context(real_lock(root, key, timeout=timeout))
            yield held

    monkeypatch.setattr(mm, "atomic_write", paused_atomic_write)
    monkeypatch.setattr(Path, "write_text", paused_write_text)
    monkeypatch.setattr(mission_write, "feature_status_lock", probing_lock)

    def run_a() -> None:
        try:
            writer_a()
        except Exception as exc:
            errors.append(exc)
        finally:
            a_at_write.set()

    def run_b() -> None:
        a_at_write.wait(JOIN_SECONDS)
        try:
            writer_b()
        except Exception as exc:
            errors.append(exc)
        finally:
            release_a.set()  # B finished: A held no lock

    threads = [threading.Thread(target=run_a, name=WRITER_A), threading.Thread(target=run_b)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(JOIN_SECONDS)
    return errors
