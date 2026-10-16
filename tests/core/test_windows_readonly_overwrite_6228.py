"""Windows regression guard for #6228 -- atomic_write over a read-only file.

`spec-kitty upgrade --project` failed on Windows with ``WinError 5`` (access denied)
when it overwrote a project ``SKILL.md`` that is on disk read-only, and its own
prescribed remedy ("re-run ``spec-kitty upgrade``") failed identically -- the upgrade
could never self-converge, because the CLI re-marks managed skill files read-only on
every run (so 4.x->4.x upgrades hit the same wall, not only 3.x->4.x).

Root cause: the shared atomic writer ``specify_cli.core.atomic.atomic_write`` did
``os.replace(tmp, path)`` with no read-only handling. On Windows ``os.replace`` onto a
read-only destination raises ``PermissionError`` (WinError 5); on POSIX it ignores the
target mode and succeeds. The fix restores the destination's owner write bit before the
replace and re-applies its mode afterward, mirroring the sibling writers
``core.safe_delete.force_writable`` and ``runtime.generated_writer.write_generated_file``.

This Windows-only I/O check is the OS-specific gate (``windows_ci``, runs on the per-PR
Windows job and auto-skips off-win32 via ``tests/conftest.py``). The cross-platform
assertion of the write-bit-restore path -- observable on POSIX via the final mode -- lives
in ``tests/specify_cli/test_atomic_write.py`` and ``tests/kernel/test_atomic.py`` and gates
every PR on every platform.
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

from specify_cli.core.atomic import atomic_write


@pytest.mark.windows_ci
def test_atomic_write_overwrites_a_read_only_file(tmp_path: Path) -> None:
    # The ``windows_ci`` marker auto-skips off-win32 (tests/conftest.py); the defect
    # reproduces only on Windows, where os.replace refuses a read-only destination.
    assert sys.platform == "win32"
    target = tmp_path / "SKILL.md"
    target.write_text("old project skill\n", encoding="utf-8")
    os.chmod(target, stat.S_IREAD)  # project skills are deliberately left read-only on disk
    assert not os.access(target, os.W_OK), "fixture: the target must be read-only before the overwrite"

    # atomic_write restores the write bit before os.replace and overwrites cleanly,
    # exactly as `spec-kitty upgrade --project` must be able to overwrite a read-only
    # SKILL.md. Before the fix this raised PermissionError (WinError 5) on Windows and
    # the CLI's own re-run prescription failed identically (upgrade could not converge).
    atomic_write(target, "new project skill\n")

    assert target.read_text(encoding="utf-8") == "new project skill\n"
