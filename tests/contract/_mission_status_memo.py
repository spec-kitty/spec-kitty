"""The resolver memo of the Mission Status health, drift and ops reads (plan D-P2, spec FR-015).

The coordination-aware resolver (``MissionStatus.load``) starts git queries and, for a Mission whose declared
coordination branch is absent locally, probes the configured remotes. The new reader code (the ``Project``
builder, the drift scan, the oracles) must not pay for it twice, so it reaches the resolver through one object,
``ResolverMemo``, created once per run (one reality run, or one fixture build) and keyed by the resolved
repository root and the Mission directory name. An entry holds the RAW outcome (the read directory, or the
exception the resolver raised) and the number of processes the call started; each consumer applies its own
fallback rules to that raw outcome, so the memo never decides what an exception means.

This module is neither a reader nor an oracle, and imports no reader. It is a helper of the tests: it uses
``pytest.MonkeyPatch`` for its one patch (a counter around ``subprocess.Popen.__init__``), never a manual mutation.
"""

from __future__ import annotations

import inspect
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from specify_cli.status.aggregate import MissionStatus

# The frame the "resolver call is on the stack" marker looks for: the one function that calls the resolver.
RESOLVER_FRAME = "_run_resolver"


@dataclass
class SubprocessCount:
    """How many processes were started while a counting context was open."""

    started: int = 0


@contextmanager
def counting_subprocesses() -> Iterator[SubprocessCount]:
    """Count every ``subprocess.Popen`` started inside the context; the wrapper is undone with its ``MonkeyPatch``."""
    count = SubprocessCount()
    original = subprocess.Popen.__init__

    def counted(self: Any, *arguments: Any, **options: Any) -> None:
        count.started += 1
        original(self, *arguments, **options)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(subprocess.Popen, "__init__", counted)
        yield count


@dataclass(frozen=True)
class MemoEntry:
    """The raw outcome of one resolver call: the read directory or the exception, and the processes the call started."""

    outcome: Path | Exception
    subprocesses: int


class ResolverMemo:
    """The per-run memo: one resolver call per (resolved repository root, Mission directory name)."""

    def __init__(self) -> None:
        self.runs = 0
        self._entries: dict[tuple[Path, str], MemoEntry] = {}

    def entries(self) -> list[MemoEntry]:
        """Every entry recorded so far, in the order the resolver ran."""
        return list(self._entries.values())

    def lookup(self, key: tuple[Path, str]) -> MemoEntry | None:
        return self._entries.get(key)

    def record(self, key: tuple[Path, str], entry: MemoEntry) -> None:
        self._entries[key] = entry
        self.runs += 1


def resolver_call_on_stack() -> bool:
    """True while the memo's resolver call is running: the stack holds a frame of ``_run_resolver`` of this module."""
    frame = inspect.currentframe()
    while frame is not None:
        if frame.f_code.co_name == RESOLVER_FRAME and frame.f_code.co_filename == __file__:
            return True
        frame = frame.f_back
    return False


def _run_resolver(repo_root: Path, name: str) -> MemoEntry:
    """Call the resolver once and keep its raw outcome with the number of processes the call started."""
    with counting_subprocesses() as count:
        try:
            outcome: Path | Exception = Path(MissionStatus.load(repo_root, name).read_dir)
        except Exception as error:  # the raw outcome: each consumer decides what an exception means
            outcome = error
    return MemoEntry(outcome=outcome, subprocesses=count.started)


def memo_resolve(memo: ResolverMemo, repo_root: Path, name: str) -> MemoEntry:
    """The one place the coordination resolver is called: a hit costs nothing, a miss runs it once."""
    key = (repo_root.resolve(), name)
    entry = memo.lookup(key)
    if entry is None:
        entry = _run_resolver(repo_root, name)
        memo.record(key, entry)
    return entry
