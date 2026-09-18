"""Migration regression coverage for ``checkout_file_lock`` (WP05, #4714, T021).

Distinct from ``tests/core/test_checkout_file_lock.py`` (the module's
ordinary behavioural unit coverage, itself updated onto the new primitive by
this same WP): this file exists specifically to pin the MIGRATION invariants
-- no ``filelock`` import survives, ``acquire_or_raise`` returns the
canonical ``LockRecord``, and the G6 test-double injection seam (monkeypatch
``kernel.locks.SyncMachineFileLock``, not the caller module) still lets a
test substitute the whole lock behaviour for a caller built on
:func:`kernel.locks.machine_file_lock`.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kernel.locks import LockAcquireTimeout, LockRecord, machine_file_lock
from specify_cli.core import checkout_file_lock
from specify_cli.core.checkout_file_lock import acquire_or_raise

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_module_imports_no_filelock() -> None:
    """AST-level pin: the migrated module never imports the retired ``filelock`` package."""
    source = Path(checkout_file_lock.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_names.add(node.module)
    assert "filelock" not in imported_names


def test_acquire_or_raise_returns_the_canonical_lock_record(tmp_path: Path) -> None:
    """A successful entry returns ``kernel.locks.LockRecord`` holder metadata."""
    lock_path = tmp_path / "migration.lock"
    lock = machine_file_lock(lock_path, blocking=True, timeout_s=1.0)

    record = acquire_or_raise(lock, build_timeout_error=AssertionError)
    try:
        assert isinstance(record, LockRecord)
        assert record.pid > 0
    finally:
        lock.__exit__(None, None, None)


def test_g6_injection_seam_substitutes_lock_behaviour_via_kernel_locks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Patching ``kernel.locks.SyncMachineFileLock`` swaps behaviour for a
    caller built on :func:`kernel.locks.machine_file_lock`.

    This is the exact seam ``review.verdict_commit_queue`` (T023) and
    ``status.locking``/``zeitgeist_client.*`` (T022/T025) rely on: a caller
    never constructs ``SyncMachineFileLock`` directly, so a test can
    substitute the whole lock behaviour by monkeypatching the *class*
    ``kernel.locks`` resolves at call time -- not any attribute of the
    caller's own module.
    """
    lock_path = tmp_path / "double.lock"
    calls: list[Path] = []

    class _DoubleLock:
        def __init__(self, path: Path, **_kwargs: object) -> None:
            calls.append(path)

        def __enter__(self) -> LockRecord:
            raise LockAcquireTimeout(path=str(lock_path))

        def __exit__(self, *_exc: object) -> None:
            pytest.fail("a lock that was never entered must not be released")

    monkeypatch.setattr("kernel.locks.SyncMachineFileLock", _DoubleLock)

    lock = machine_file_lock(lock_path, blocking=True, timeout_s=1.0)

    class _CallerTimeout(RuntimeError):
        pass

    with pytest.raises(_CallerTimeout) as raised:
        acquire_or_raise(lock, build_timeout_error=lambda: _CallerTimeout("busy"))

    assert calls == [lock_path]
    assert isinstance(raised.value.__cause__, LockAcquireTimeout)
