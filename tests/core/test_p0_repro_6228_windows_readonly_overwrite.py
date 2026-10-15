"""OPEN P0 #6228 -- red-first reproduction (Windows-only; p0_repro lane).

``spec-kitty upgrade --project`` fails on Windows with ``WinError 5`` (access denied)
when it overwrites a project ``SKILL.md`` that is on disk read-only, and its own
prescribed remedy ("re-run ``spec-kitty upgrade``") fails identically -- the upgrade
can never self-converge on Windows, because the CLI re-sets those files read-only on
every run.

Root cause: the shared atomic writer ``specify_cli.core.atomic.atomic_write`` does
``os.replace(tmp, path)`` with no read-only handling (``core/atomic.py``). On Windows
``os.replace`` onto a read-only destination raises ``PermissionError`` (WinError 5);
on POSIX it ignores the target mode and succeeds. The skill-installer overwrite
(``skills/installer.py`` ``_apply_project_skill_write``) calls ``atomic_write`` then
re-applies the read-only bit, so it is the one writer still missing the #3771 fix its
two siblings carry (``runtime/generated_writer.py`` and
``core/utils.write_text_within_directory`` restore the write bit before ``os.replace``).

This is **Windows-only**: it cannot red on the Linux nightly ``p0-repro`` lane (POSIX
``os.replace`` ignores target mode), so it is gated to ``win32`` and runs on the nightly
``windows-p0-repro`` lane -- the Windows sibling of the Linux ``p0-repro`` job, honestly
red until this bug is fixed (see ``.github/workflows/ci-nightly.yml``). On the Linux
nightly lane it is collected-but-skipped (reported as "no verdict"), which is honest:
Linux cannot confirm or clear this bug.

Ideal, asserted here and RED on Windows until #6228 is fixed: ``atomic_write`` must
overwrite a read-only file cleanly (restoring the write bit before ``os.replace``, as
its sibling writers do). Today it raises ``PermissionError`` on Windows. The fix PR
removes the ``p0_repro`` marker. See ADR 2026-07-17-1 and
docs/development/reference/red-main-and-release-readiness.md.
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

from specify_cli.core.atomic import atomic_write

pytestmark = [pytest.mark.unit]


@pytest.mark.p0_repro(issue=6228)
@pytest.mark.skipif(
    sys.platform != "win32",
    reason="#6228 is Windows-only: POSIX os.replace ignores target mode; the defect reproduces only on win32.",
)
def test_atomic_write_overwrites_a_read_only_file(tmp_path: Path) -> None:
    target = tmp_path / "SKILL.md"
    target.write_text("old project skill\n", encoding="utf-8")
    os.chmod(target, stat.S_IREAD)  # project skills are deliberately left read-only on disk
    assert not os.access(target, os.W_OK), "fixture: the target must be read-only before the overwrite"

    # Ideal: atomic_write restores the write bit before os.replace and overwrites cleanly,
    # exactly as `spec-kitty upgrade --project` must be able to overwrite a read-only SKILL.md.
    # Today on Windows os.replace onto a read-only target raises PermissionError (WinError 5),
    # and the CLI's own re-run prescription fails identically (upgrade cannot self-converge).
    atomic_write(target, "new project skill\n")

    assert target.read_text(encoding="utf-8") == "new project skill\n"
