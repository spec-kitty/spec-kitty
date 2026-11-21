"""Emulate an NTFS host on Linux for mode-convergence tests (#4927, #4810).

On Windows, NTFS does not store POSIX permission bits; Python synthesizes them:

* a directory always reads ``0o777``;
* a regular file reads ``0o666`` while writable and ``0o444`` while read-only;
* ``os.chmod`` only toggles the read-only attribute (from the requested
  mode's owner write bit) and is a no-op on a directory.

:func:`emulate_ntfs` reproduces exactly that through ``monkeypatch`` (so the
real ``os`` functions come back at teardown) and pins the canonical host seam
``kernel.paths.is_windows`` to True. It never fakes ``os.name``, which would
switch ``pathlib`` to ``WindowsPath``.

Known gap: ``os.DirEntry.stat`` / ``os.scandir`` results are not synthesized.
The planners observe modes through ``lstat``/``stat``/``fstat`` only
(research R-6), so this does not affect them.
"""

from __future__ import annotations

import os
import stat
from collections.abc import Iterator
from typing import Any

import pytest

from kernel import paths as kernel_paths

_NTFS_DIRECTORY_MODE = 0o777
_NTFS_WRITABLE_FILE_MODE = 0o666
_NTFS_READ_ONLY_FILE_MODE = 0o444
_WRITE_BIT = 0o200


def _ntfs_view(result: os.stat_result) -> os.stat_result:
    mode = result.st_mode
    if stat.S_ISDIR(mode):
        permissions = _NTFS_DIRECTORY_MODE
    elif stat.S_ISREG(mode):
        permissions = _NTFS_WRITABLE_FILE_MODE if mode & _WRITE_BIT else _NTFS_READ_ONLY_FILE_MODE
    else:
        return result
    values = list(result)
    values[0] = stat.S_IFMT(mode) | permissions
    return os.stat_result(values)


def _real_bits(mode: int) -> int:
    """The real POSIX mode that carries the read-only attribute NTFS would keep."""
    return 0o644 if mode & _WRITE_BIT else _NTFS_READ_ONLY_FILE_MODE


def emulate_ntfs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make this process observe and set modes the way Windows on NTFS does."""
    real_stat, real_lstat, real_fstat = os.stat, os.lstat, os.fstat
    real_chmod, real_fchmod = os.chmod, os.fchmod

    def fake_stat(path: Any, *args: Any, **kwargs: Any) -> os.stat_result:
        return _ntfs_view(real_stat(path, *args, **kwargs))

    def fake_lstat(path: Any, *args: Any, **kwargs: Any) -> os.stat_result:
        return _ntfs_view(real_lstat(path, *args, **kwargs))

    def fake_fstat(fd: int) -> os.stat_result:
        return _ntfs_view(real_fstat(fd))

    def fake_chmod(path: Any, mode: int, *args: Any, **kwargs: Any) -> None:
        if isinstance(path, int):
            fake_fchmod(path, mode)
            return
        follow = kwargs.get("follow_symlinks", True)
        target = real_stat(path, dir_fd=kwargs.get("dir_fd"), follow_symlinks=follow)
        if stat.S_ISDIR(target.st_mode):
            return
        real_chmod(path, _real_bits(mode), *args, **kwargs)

    def fake_fchmod(fd: int, mode: int) -> None:
        if stat.S_ISDIR(real_fstat(fd).st_mode):
            return
        real_fchmod(fd, _real_bits(mode))

    monkeypatch.setattr(os, "stat", fake_stat)
    monkeypatch.setattr(os, "lstat", fake_lstat)
    monkeypatch.setattr(os, "fstat", fake_fstat)
    monkeypatch.setattr(os, "chmod", fake_chmod)
    monkeypatch.setattr(os, "fchmod", fake_fchmod)
    monkeypatch.setattr(kernel_paths, "is_windows", lambda: True)


@pytest.fixture
def ntfs_host(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """A test body that runs as if on Windows with an NTFS file system."""
    emulate_ntfs(monkeypatch)
    yield


@pytest.fixture
def posix_host(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """A test body that runs on POSIX regardless of the harness's real host."""
    monkeypatch.setattr(kernel_paths, "is_windows", lambda: False)
    yield
