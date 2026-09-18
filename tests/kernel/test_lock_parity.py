"""Cross-OS parity harness for ``kernel.locks`` (T014, SC-004, FR-007/NFR-004).

**The PRIMARY proof is STRUCTURAL** (post-tasks squad N-2): a runtime
"acquire, read, assert no error" test is VACUOUS on advisory POSIX -- the
holder of a POSIX ``flock`` can always read its own locked file; that is
precisely why #4703 (Windows-mandatory-lock refusal on a self-held lock)
shipped undetected. Section A below proves, structurally, that the public
API surface has NO code path from a successful acquire to a handle on the
protected resource -- there is nothing TO read through the lock, on any OS.

Section B is the SECONDARY runtime proof (R-03): a harness that simulates
Windows' MANDATORY lock semantics on POSIX (a second ``os.open`` of an
already-locked path raises ``PermissionError``, unlike advisory ``flock``)
and shows (b1) the simulation is faithful -- a naive hand-rolled second open
of a held lock's path DOES raise under it -- and (b2) the canonical
primitive's own acquire/write/release cycle never trips it, because it only
ever touches the resource through the ORIGINAL locked fd.

Section C covers cross-process contention (subprocess, not just
same-process asyncio tasks) and blocking-with-timeout. Section D covers
release-truncates (inode stability, G3).
"""

from __future__ import annotations

import ast
import asyncio
import dataclasses
import multiprocessing
import os
import time
from collections.abc import Callable
from pathlib import Path

import pytest

import kernel.locks as locks
from kernel.locks import (
    LockAcquireTimeout,
    LockRecord,
    MachineFileLock,
    SyncMachineFileLock,
    read_lock_record,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_LOCKS_SOURCE_PATH = Path(locks.__file__)


# ---------------------------------------------------------------------------
# Section A -- structural read-safety proof (FR-007/G2, primary per N-2)
# ---------------------------------------------------------------------------


def test_lock_record_fields_are_exactly_holder_metadata() -> None:
    """G2/E-01 invariant 2: ``LockRecord`` carries ONLY holder metadata.

    Non-vacuous: a mutation adding any field that could carry or reference
    the protected resource's content (e.g. a ``raw_fd``/``handle``/``data``
    field) would grow this set and fail the equality -- the check is exact,
    not "contains at least."
    """
    field_names = {f.name for f in dataclasses.fields(LockRecord)}
    assert field_names == {"schema_version", "pid", "started_at", "host", "version"}


def test_lock_record_exposes_no_read_capable_attribute() -> None:
    """G2: nothing on a returned ``LockRecord`` lets you pivot to a payload read.

    Checks the instance's public surface for read-capable names -- a mutation
    adding a ``.read()``/``.open()``/``.fileno()``/``.fd`` accessor would be
    caught here even if it were computed lazily rather than stored as a field.
    """
    record = LockRecord(schema_version=1, pid=1, started_at=locks.now_utc(), host="h", version="v")
    banned_substrings = ("read", "open", "fileno", "handle", "descriptor")
    public_attrs = [name for name in dir(record) if not name.startswith("_")]
    offenders = [name for name in public_attrs if any(bad in name.lower() for bad in banned_substrings)]
    assert offenders == [], f"LockRecord exposes read-capable attribute(s): {offenders}"
    # And there really is no callable path from the fd int type to bytes.
    assert not hasattr(record, "fd")
    assert not hasattr(record, "path")


def _is_public_name(name: str) -> bool:
    """``True`` unless ``name`` has a leading underscore and is not a dunder.

    A dunder such as ``__aenter__``/``__enter__``/``__aexit__``/``__exit__``
    IS the public context-manager protocol surface (the exact entry points
    this module's read-safety guarantee is about) even though it starts with
    ``_`` -- excluding dunders by a naive ``startswith("_")`` check would
    silently skip scanning the two functions that matter most.
    """
    if not name.startswith("_"):
        return True
    return name.startswith("__") and name.endswith("__")


def _public_functions_and_methods(tree: ast.Module) -> list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    """``(qualname, node)`` for every public module function/method (see :func:`_is_public_name`).

    Deliberately walks only ``tree.body`` (module top level) and each public
    class's OWN ``body`` -- NOT a flat ``ast.walk`` -- so a class's methods
    are counted exactly once (qualified), never a second time as a bare
    module-level name. Only classes whose OWN name is public count as
    "public API surface": ``_LockCore.open_fd`` legitimately returns a raw
    fd (it is the shared internal primitive both facades delegate to, never
    exposed to a caller), so it must not be scanned here even though its own
    method name has no leading underscore.
    """
    found: list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            if not _is_public_name(node.name):
                continue
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_public_name(child.name):
                    found.append((f"{node.name}.{child.name}", child))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_public_name(node.name):
            found.append((node.name, node))
    return found


def _returns_a_raw_descriptor(ret: ast.Return) -> bool:
    """``True`` when a ``return`` statement's value looks like a raw fd/handle.

    Flags a bare ``Name``/``Attribute`` whose identifier contains ``fd`` (the
    :class:`_LockCore` field name, and the conventional local for an
    ``os.open`` result), or a direct ``os.open(...)``/builtin ``open(...)``
    call -- the two shapes that would hand a caller a payload handle instead
    of a :class:`LockRecord`.
    """
    value = ret.value
    if value is None:
        return False
    if isinstance(value, ast.Name) and "fd" in value.id.lower():
        return True
    if isinstance(value, ast.Attribute) and "fd" in value.attr.lower():
        return True
    if isinstance(value, ast.Call):
        func = value.func
        if isinstance(func, ast.Name) and func.id == "open":
            return True
        if isinstance(func, ast.Attribute) and func.attr == "open" and isinstance(func.value, ast.Name) and func.value.id == "os":
            return True
    return False


def find_payload_handle_returns(source: str) -> list[tuple[str, int]]:
    """``(qualname, lineno)`` for every public function/method that returns a raw descriptor."""
    tree = ast.parse(source)
    violations: list[tuple[str, int]] = []
    for qualname, func in _public_functions_and_methods(tree):
        for node in ast.walk(func):
            if isinstance(node, ast.Return) and _returns_a_raw_descriptor(node):
                violations.append((qualname, node.lineno))
    return violations


def test_no_public_entrypoint_returns_a_raw_descriptor() -> None:
    """FR-007/G2: no public function or method in the door returns a raw fd/handle."""
    source = _LOCKS_SOURCE_PATH.read_text(encoding="utf-8")
    assert find_payload_handle_returns(source) == []


def test_detector_flags_a_planted_payload_handle_return() -> None:
    """Non-vacuity (C-009): the detector above DOES fire on a planted violation."""
    planted = "class Leaky:\n    def enter(self):\n        fd = 1\n        return fd\n"
    assert find_payload_handle_returns(planted) == [("Leaky.enter", 4)]

    planted_open = "def open_resource(path):\n    return open(path)\n"
    assert find_payload_handle_returns(planted_open) == [("open_resource", 2)]


def test_aenter_and_enter_return_annotations_are_lock_record() -> None:
    """The two facade entry points are annotated to return ``LockRecord``, not e.g. ``Any``."""
    tree = ast.parse(_LOCKS_SOURCE_PATH.read_text(encoding="utf-8"))
    annotations: dict[str, str | None] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name in {"MachineFileLock", "SyncMachineFileLock"}:
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name in {"__aenter__", "__enter__"}:
                    returns = child.returns
                    annotations[f"{node.name}.{child.name}"] = ast.unparse(returns) if returns is not None else None

    assert annotations == {
        "MachineFileLock.__aenter__": "LockRecord",
        "SyncMachineFileLock.__enter__": "LockRecord",
    }


# ---------------------------------------------------------------------------
# Section B -- simulated Windows mandatory-lock semantics on POSIX (R-03)
# ---------------------------------------------------------------------------


class _WindowsMandatoryLockSimulator:
    """Fakes Windows' MANDATORY (not merely advisory) file-lock refusal on POSIX.

    Tracks which resolved paths are currently OS-locked (by any holder,
    including "this same process") and makes a SECOND ``os.open`` of an
    already-locked path raise :class:`PermissionError` -- the #4703
    signature that POSIX's advisory ``flock`` never enforces (a holder can
    always open+read its own locked file again on POSIX). The real
    ``_os_lock``/``_os_unlock`` still run underneath; this only layers the
    extra "you cannot even OPEN a locked file a second time" refusal on top.
    """

    def __init__(self) -> None:
        self._locked_paths: set[str] = set()
        self._fd_to_path: dict[int, str] = {}

    def wrap_open(self, real_open: Callable[..., int]) -> Callable[..., int]:
        def _open(path: str, flags: int, mode: int = 0o777) -> int:
            resolved = str(Path(path).resolve())
            if resolved in self._locked_paths:
                raise PermissionError(13, "The process cannot access the file because another process has locked a portion of the file")
            fd = real_open(path, flags, mode)
            self._fd_to_path[fd] = resolved
            return fd

        return _open

    def wrap_os_lock(self, real_os_lock: Callable[[int], None]) -> Callable[[int], None]:
        def _locking(fd: int) -> None:
            real_os_lock(fd)
            path = self._fd_to_path.get(fd)
            if path is not None:
                self._locked_paths.add(path)

        return _locking

    def wrap_os_unlock(self, real_os_unlock: Callable[[int], None]) -> Callable[[int], None]:
        def _unlocking(fd: int) -> None:
            real_os_unlock(fd)
            path = self._fd_to_path.pop(fd, None)
            if path is not None:
                self._locked_paths.discard(path)

        return _unlocking


@pytest.fixture()
def windows_mandatory_lock_simulation(monkeypatch: pytest.MonkeyPatch) -> _WindowsMandatoryLockSimulator:
    sim = _WindowsMandatoryLockSimulator()
    monkeypatch.setattr(os, "open", sim.wrap_open(os.open))
    monkeypatch.setattr(locks, "_os_lock", sim.wrap_os_lock(locks._os_lock))
    monkeypatch.setattr(locks, "_os_unlock", sim.wrap_os_unlock(locks._os_unlock))
    return sim


def test_naive_second_open_of_a_held_lock_raises_under_simulation(tmp_path: Path, windows_mandatory_lock_simulation: _WindowsMandatoryLockSimulator) -> None:
    """Faithfulness check (b1): the simulation reproduces the #4703 signature.

    This is the exact hazard class the mission exists to close: a naive,
    hand-rolled SECOND open of a path the current process already holds a
    lock over. On advisory POSIX this would silently succeed (which is how
    #4703 shipped); under this simulation it raises, matching real Windows.
    """
    resource = tmp_path / "payload.lock"

    with SyncMachineFileLock(resource), pytest.raises(PermissionError):
        os.open(str(resource), os.O_RDONLY)


def test_sync_primitive_never_reopens_the_resource_while_held(tmp_path: Path, windows_mandatory_lock_simulation: _WindowsMandatoryLockSimulator) -> None:
    """Positive control (b2): the sync facade's own acquire/write/release never trips it.

    :class:`SyncMachineFileLock` only ever reads/writes the resource through
    the ORIGINAL locked fd (``_LockCore``'s own ``os.write``/``os.ftruncate``
    calls) -- never a second ``os.open`` of the same path -- so running the
    full lifecycle under the simulated mandatory-lock refusal completes
    without ever raising it.
    """
    resource = tmp_path / "payload.lock"

    with SyncMachineFileLock(resource) as record:
        assert isinstance(record, LockRecord)

    # Released -- a subsequent read (e.g. `auth doctor`, a non-holder) is safe.
    assert read_lock_record(resource) is None


async def test_async_primitive_never_reopens_the_resource_while_held(tmp_path: Path, windows_mandatory_lock_simulation: _WindowsMandatoryLockSimulator) -> None:
    """Positive control (b2), async facade."""
    resource = tmp_path / "payload_async.lock"

    async with MachineFileLock(resource) as record:
        assert isinstance(record, LockRecord)

    assert read_lock_record(resource) is None


# ---------------------------------------------------------------------------
# Section C -- cross-process contention + blocking-with-timeout (R-03)
# ---------------------------------------------------------------------------


def _worker_acquire_and_flag(lock_path: str, flag_path: str, sleep_s: float) -> None:
    """Worker process: acquire the async lock, write a flag file, hold briefly, release."""

    async def _run() -> None:
        async with MachineFileLock(Path(lock_path), acquire_timeout_s=10.0):
            Path(flag_path).write_text("held", encoding="utf-8")  # noqa: ASYNC240
            await asyncio.sleep(sleep_s)
            Path(flag_path).write_text("released", encoding="utf-8")  # noqa: ASYNC240

    asyncio.run(_run())


@pytest.mark.slow
def test_contention_across_processes_serializes_access(tmp_path: Path) -> None:
    """Two real OS processes contend for the same lock and both complete cleanly.

    Proves the acquire retry loop handles genuine cross-process OS-level
    contention, not merely same-process ``asyncio`` task interleaving
    (:func:`test_concurrent_acquire_serialized` in ``test_locks.py`` only
    proves the latter).
    """
    ctx = multiprocessing.get_context("spawn")
    lock_path = str(tmp_path / "mp_test.lock")
    flag_path = str(tmp_path / "flag.txt")

    p1 = ctx.Process(target=_worker_acquire_and_flag, args=(lock_path, flag_path, 0.1))
    p2 = ctx.Process(target=_worker_acquire_and_flag, args=(lock_path, flag_path, 0.05))

    p1.start()
    time.sleep(0.02)  # give p1 a head start
    p2.start()

    p1.join(timeout=15)
    p2.join(timeout=15)

    assert p1.exitcode == 0, f"Process 1 exited with code {p1.exitcode}"
    assert p2.exitcode == 0, f"Process 2 exited with code {p2.exitcode}"


def _worker_sync_blocking_acquire(lock_path: str, result_path: str, timeout_s: float) -> None:
    """Worker process: attempt a sync blocking-with-timeout acquire, record the outcome."""
    try:
        with SyncMachineFileLock(Path(lock_path), blocking=True, timeout_s=timeout_s) as record:
            Path(result_path).write_text(f"acquired:{record.pid}", encoding="utf-8")
    except LockAcquireTimeout:
        Path(result_path).write_text("timeout", encoding="utf-8")


@pytest.mark.slow
def test_sync_blocking_with_timeout_across_processes(tmp_path: Path) -> None:
    """A subprocess using ``blocking=True``+``timeout_s`` waits out a held lock."""
    ctx = multiprocessing.get_context("spawn")
    lock_path = tmp_path / "mp_sync_blocking.lock"
    result_path = tmp_path / "result.txt"

    holder = SyncMachineFileLock(lock_path)
    holder.__enter__()
    worker = ctx.Process(
        target=_worker_sync_blocking_acquire,
        args=(str(lock_path), str(result_path), 5.0),
    )
    worker.start()
    time.sleep(0.2)  # ensure the worker observes contention, not a race for first acquire
    holder.__exit__(None, None, None)
    worker.join(timeout=15)

    assert worker.exitcode == 0
    assert result_path.read_text(encoding="utf-8").startswith("acquired:")


# ---------------------------------------------------------------------------
# Section D -- release truncates, never unlinks (G3)
# ---------------------------------------------------------------------------


def test_release_truncates_and_preserves_inode(tmp_path: Path) -> None:
    """G3: the on-disk inode survives a release; a contender never mints a rival inode."""
    resource = tmp_path / "inode.lock"

    with SyncMachineFileLock(resource):
        pass
    inode_after_first = resource.stat().st_ino

    with SyncMachineFileLock(resource) as record:
        assert isinstance(record, LockRecord)
    inode_after_second = resource.stat().st_ino

    assert inode_after_first == inode_after_second
    assert resource.stat().st_size == 0
