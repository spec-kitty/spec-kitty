"""Running-process probe for the landed-worktree prune (#7173, WP03).

:func:`processes_with_cwd_under` answers one question: does any process have
its working directory inside one of the given worktrees? A worktree a shell,
an editor or a test run is standing in is in use and must not be removed, even
when its committed work has landed.

How it decides (Linux ``/proc``, read once per call, NFR-003):

* every ``/proc/<pid>`` entry owned by the current uid is read
  (``os.readlink("/proc/<pid>/cwd")``) and compared with each resolved input
  path (equal to it, or under it);
* the probing process itself is skipped, its parent shell is not: a shell left
  in the worktree is a real "busy" signal;
* a process that exits between the listing and the read
  (``FileNotFoundError`` / ``ProcessLookupError``) is skipped;
* a same-uid process whose cwd cannot be read (``PermissionError`` or any
  other ``OSError``, e.g. a non-dumpable process such as ``gpg-agent``, or a
  container's pid 1) is skipped and counted in
  :attr:`ProcessProbeResult.uninspected` (operator ruling
  ``plan.prune.unreadable_process``, 2026-11-05: skip and report), so the
  caller can say how many processes could not be inspected;
* the probe is unavailable only when ``/proc`` is absent (not Linux) or
  cannot be listed.

Known residuals, documented for operators (WP06):

* (U1) only processes owned by the current uid are considered: another
  user's process standing in the worktree is not detected;
* a process whose cwd cannot be read (non-dumpable, or otherwise refused) is
  not detected either; it is only counted.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["ProcessProbeResult", "processes_with_cwd_under"]

DEFAULT_PROC_ROOT = Path("/proc")


@dataclass(frozen=True)
class ProcessProbeResult:
    """Outcome of one probe.

    ``available`` is ``False`` when the probe could not prove anything (no
    ``/proc``, or it cannot be listed); ``busy`` is then empty and must not be
    read as "idle". ``detail`` explains an unavailable probe. ``uninspected``
    counts same-uid processes whose cwd could not be read (skipped, not
    detected).
    """

    available: bool
    busy: frozenset[Path] = field(default_factory=frozenset)
    detail: str = ""
    uninspected: int = 0


def _current_uid() -> int | None:
    getuid = getattr(os, "getuid", None)
    return getuid() if getuid is not None else None


def _read_cwd(link: Path) -> str:
    return os.readlink(link)


class _Uninspectable(Exception):
    """A current-uid process whose cwd cannot be read: skipped and counted."""


def _process_cwd(entry: Path, uid: int) -> Path | None:
    """The cwd of the process at ``entry``; ``None`` when it is not ours or has exited.

    Raises:
        _Uninspectable: it is ours but its cwd cannot be read.
    """
    try:
        if entry.stat().st_uid != uid:
            return None
        return Path(_read_cwd(entry / "cwd"))
    except (FileNotFoundError, ProcessLookupError):
        return None
    except OSError as exc:  # PermissionError included: skip and report (operator ruling).
        raise _Uninspectable(entry.name) from exc


def _scan_cwds(proc_root: Path, uid: int) -> tuple[list[Path], int]:
    """Every readable cwd of a current-uid process except this one, and the count of unreadable ones; one pass."""
    own_pid = str(os.getpid())
    cwds: list[Path] = []
    uninspected = 0
    with os.scandir(proc_root) as entries:
        for entry in entries:
            if not entry.name.isdigit() or entry.name == own_pid:
                continue
            try:
                cwd = _process_cwd(Path(entry.path), uid)
            except _Uninspectable:
                uninspected += 1
                continue
            if cwd is not None:
                cwds.append(cwd)
    return cwds, uninspected


def _inside(cwd: Path, root: Path) -> bool:
    return cwd == root or cwd.is_relative_to(root)


def processes_with_cwd_under(paths: Sequence[Path], *, proc_root: Path = DEFAULT_PROC_ROOT) -> ProcessProbeResult:
    """Which of ``paths`` some current-uid process has as its cwd (or under it).

    ``busy`` holds the input paths exactly as given. ``proc_root`` is
    injectable for tests; the default ``/proc`` is used only on Linux.
    """
    if not paths:
        return ProcessProbeResult(available=True)
    uid = _current_uid()
    if uid is None or (proc_root == DEFAULT_PROC_ROOT and not sys.platform.startswith("linux")):
        return ProcessProbeResult(available=False, detail="no /proc on this platform; running processes cannot be checked")
    if not proc_root.is_dir():
        return ProcessProbeResult(available=False, detail=f"{proc_root} is not available; running processes cannot be checked")
    try:
        cwds, uninspected = _scan_cwds(proc_root, uid)
    except OSError as exc:
        return ProcessProbeResult(available=False, detail=f"cannot list {proc_root}: {exc.strerror or exc}")
    resolved = [(path, path.resolve()) for path in paths]
    busy = frozenset(path for path, root in resolved if any(_inside(cwd, root) for cwd in cwds))
    return ProcessProbeResult(available=True, busy=busy, uninspected=uninspected)
