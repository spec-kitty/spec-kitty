"""Running-process probe for the landed-worktree prune (#7173, WP03, T009).

A fake ``/proc`` tree (``<pid>/cwd`` symlinks) drives every branch of
:func:`processes_with_cwd_under`; one smoke test reads the real ``/proc``.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from specify_cli.workspace import process_probe
from specify_cli.workspace.process_probe import processes_with_cwd_under

pytestmark = pytest.mark.unit


def _proc(root: Path, pid: int, cwd: Path) -> None:
    entry = root / str(pid)
    entry.mkdir(parents=True)
    (entry / "cwd").symlink_to(cwd)


@pytest.fixture
def worktrees(tmp_path: Path) -> tuple[Path, Path]:
    first = tmp_path / "wt-a"
    second = tmp_path / "wt-b"
    (first / "sub").mkdir(parents=True)
    second.mkdir()
    return first, second


def test_busy_when_a_process_cwd_is_the_worktree_or_under_it(tmp_path: Path, worktrees: tuple[Path, Path]) -> None:
    first, second = worktrees
    proc = tmp_path / "proc"
    _proc(proc, 101, first / "sub")
    _proc(proc, 102, tmp_path)

    result = processes_with_cwd_under([first, second], proc_root=proc)

    assert result.available
    assert result.busy == frozenset({first})


def test_idle_when_no_process_is_inside(tmp_path: Path, worktrees: tuple[Path, Path]) -> None:
    proc = tmp_path / "proc"
    _proc(proc, 101, tmp_path)
    (proc / "self").mkdir()  # non-numeric entries are not processes

    result = processes_with_cwd_under(list(worktrees), proc_root=proc)

    assert result.available
    assert result.busy == frozenset()


def test_a_sibling_with_a_shared_name_prefix_is_not_inside(tmp_path: Path, worktrees: tuple[Path, Path]) -> None:
    first, _ = worktrees
    sibling = tmp_path / "wt-a-other"
    sibling.mkdir()
    proc = tmp_path / "proc"
    _proc(proc, 101, sibling)

    assert processes_with_cwd_under([first], proc_root=proc).busy == frozenset()


def test_the_probing_process_itself_is_ignored(tmp_path: Path, worktrees: tuple[Path, Path]) -> None:
    first, _ = worktrees
    proc = tmp_path / "proc"
    _proc(proc, os.getpid(), first)

    result = processes_with_cwd_under([first], proc_root=proc)

    assert result.available
    assert result.busy == frozenset()


@pytest.mark.parametrize("cwd_readable", [True, False], ids=["readable-cwd", "unreadable-cwd"])
def test_another_users_process_is_not_considered(tmp_path: Path, worktrees: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, cwd_readable: bool) -> None:
    """U1: another user's process is skipped whether its cwd is readable (not busy) or not (not counted as uninspected)."""
    first, _ = worktrees
    proc = tmp_path / "proc"
    _proc(proc, 101, first)
    monkeypatch.setattr(process_probe, "_current_uid", lambda: os.stat(proc / "101").st_uid + 1)
    if not cwd_readable:

        def denied(link: Path) -> str:
            raise PermissionError(13, "Permission denied", str(link))

        monkeypatch.setattr(process_probe, "_read_cwd", denied)

    result = processes_with_cwd_under([first], proc_root=proc)

    assert result.available
    assert result.busy == frozenset()
    assert result.uninspected == 0


@pytest.mark.parametrize("error", [PermissionError(13, "Permission denied"), OSError(22, "Invalid argument")])
def test_a_same_uid_unreadable_cwd_is_skipped_and_counted(tmp_path: Path, worktrees: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, error: OSError) -> None:
    """Operator ruling plan.prune.unreadable_process: skip and report, never unavailable."""
    first, _ = worktrees
    proc = tmp_path / "proc"
    _proc(proc, 101, tmp_path)
    _proc(proc, 102, first)
    _proc(proc, 103, tmp_path)
    real = process_probe._read_cwd

    def denied(link: Path) -> str:
        if link.parent.name in ("101", "103"):
            raise error
        return real(link)

    monkeypatch.setattr(process_probe, "_read_cwd", denied)

    result = processes_with_cwd_under([first], proc_root=proc)

    assert result.available
    assert result.uninspected == 2
    assert result.busy == frozenset({first})


def test_an_unlistable_proc_root_is_unavailable(tmp_path: Path, worktrees: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    proc = tmp_path / "proc"
    proc.mkdir()
    real = os.scandir

    def refused(path: Any) -> Any:
        if path == proc:
            raise PermissionError(13, "Permission denied", str(path))
        return real(path)

    monkeypatch.setattr(process_probe.os, "scandir", refused)

    result = processes_with_cwd_under(list(worktrees), proc_root=proc)

    assert not result.available
    assert result.busy == frozenset()
    assert result.detail == f"cannot list {proc}: Permission denied"


def test_a_process_that_exits_mid_scan_is_skipped(tmp_path: Path, worktrees: tuple[Path, Path]) -> None:
    first, _ = worktrees
    proc = tmp_path / "proc"
    (proc / "101").mkdir(parents=True)  # no cwd link: the process exited between listing and reading

    result = processes_with_cwd_under([first], proc_root=proc)

    assert result.available
    assert result.busy == frozenset()


def test_missing_proc_root_is_unavailable(tmp_path: Path, worktrees: tuple[Path, Path]) -> None:
    result = processes_with_cwd_under(list(worktrees), proc_root=tmp_path / "no-proc")

    assert not result.available
    assert result.busy == frozenset()
    assert result.detail


def test_no_paths_needs_no_scan(tmp_path: Path) -> None:
    assert processes_with_cwd_under([], proc_root=tmp_path / "no-proc").available


def test_the_scan_reads_each_process_once_per_call(tmp_path: Path, worktrees: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-003: one ``/proc`` pass serves every path of the call."""
    proc = tmp_path / "proc"
    for pid in range(200, 210):
        _proc(proc, pid, tmp_path)
    reads: list[Path] = []
    real = process_probe._read_cwd

    def counting(link: Path) -> str:
        reads.append(link)
        return real(link)

    monkeypatch.setattr(process_probe, "_read_cwd", counting)

    processes_with_cwd_under([*worktrees, tmp_path / "c", tmp_path / "d"], proc_root=proc)

    assert len(reads) == 10


@pytest.fixture
def sleeper(tmp_path: Path) -> Iterator[tuple[subprocess.Popen[bytes], Path]]:
    cwd = tmp_path / "busy"
    cwd.mkdir()
    proc = subprocess.Popen(["sleep", "30"], cwd=cwd)
    try:
        yield proc, cwd
    finally:
        proc.kill()
        proc.wait()


@pytest.mark.skipif(sys.platform != "linux", reason="reads the real /proc")
def test_real_proc_smoke(tmp_path: Path, sleeper: tuple[subprocess.Popen[bytes], Path]) -> None:
    proc, cwd = sleeper
    # The whole real /proc: always available on Linux; unreadable processes are only counted.
    whole = processes_with_cwd_under([cwd])
    assert whole.available
    assert whole.busy == frozenset({cwd})
    # A view holding only the real sleeping process, linked to its real /proc entry.
    view = tmp_path / "proc-view"
    view.mkdir()
    (view / str(proc.pid)).symlink_to(Path("/proc") / str(proc.pid))
    narrowed = processes_with_cwd_under([cwd, tmp_path / "idle"], proc_root=view)
    assert narrowed.available
    assert narrowed.busy == frozenset({cwd})
