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

import importlib
import threading
from collections.abc import Callable, Iterator, Sequence
from contextlib import ExitStack, contextmanager
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from specify_cli.status.locking import FeatureStatusLockTimeoutError

# Patched by attribute name: ``importlib`` keeps the module attributes dynamic for the type checker.
mm = importlib.import_module("specify_cli.mission_metadata")
mission_write = importlib.import_module("specify_cli.status.mission_write")

WRITER_A = "writer-a"
JOIN_SECONDS = 30.0
META_NAME = "meta.json"


def _is_meta_json(path: Path) -> bool:
    return path.name == META_NAME


def _wrap_atomic_writes(
    monkeypatch: pytest.MonkeyPatch,
    modules: Sequence[ModuleType],
    wrap: Callable[[Callable[..., None]], Callable[..., None]],
) -> None:
    """Replace each module's ``atomic_write`` with ``wrap(original)``; a module without one is paused through ``Path.write_text``."""
    for module in modules:
        real = getattr(module, "atomic_write", None)
        if real is not None:
            monkeypatch.setattr(module, "atomic_write", wrap(real))


def run_overlap(
    monkeypatch: pytest.MonkeyPatch,
    writer_a: Callable[[], object],
    writer_b: Callable[[], object],
    *,
    pause_when: Callable[[Path], bool] = _is_meta_json,
    atomic_modules: Sequence[ModuleType] = (mm,),
) -> list[Exception]:
    """Run *writer_a* paused before its write while *writer_b* runs; return both errors.

    *pause_when* picks the file whose first write by writer A is the pause point (``meta.json`` by default) and
    *atomic_modules* lists the modules whose ``atomic_write`` name is wrapped, so a writer that imports it
    elsewhere (the frontmatter helper, the issue-matrix writer) pauses too. ``Path.write_text`` is always wrapped.
    """
    a_at_write = threading.Event()
    release_a = threading.Event()
    errors: list[Exception] = []
    real_write_text = Path.write_text
    real_lock = mission_write.feature_status_lock

    def pause_if_writer_a(path: Path) -> None:
        if threading.current_thread().name == WRITER_A and pause_when(path) and not a_at_write.is_set():
            a_at_write.set()
            release_a.wait(JOIN_SECONDS)

    def paused_for(real_atomic_write: Callable[..., None]) -> Callable[..., None]:
        def paused_atomic_write(path: Path, *args: Any, **kwargs: Any) -> None:
            pause_if_writer_a(path)
            real_atomic_write(path, *args, **kwargs)

        return paused_atomic_write

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

    _wrap_atomic_writes(monkeypatch, atomic_modules, paused_for)
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
