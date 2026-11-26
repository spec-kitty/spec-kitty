"""Count the git processes a test starts (the proof a git read was kept, not repeated)."""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest import mock

_REAL_POPEN = subprocess.Popen


class GitSpawns:
    """Counts git processes started while patched in."""

    def __init__(self) -> None:
        self.count = 0

    def __call__(self, args: Any, *rest: Any, **kwargs: Any) -> Any:
        argv = args if isinstance(args, (list, tuple)) else [args]
        if argv and Path(str(argv[0])).name.startswith("git"):
            self.count += 1
        return _REAL_POPEN(args, *rest, **kwargs)


@contextmanager
def count_git_spawns() -> Iterator[GitSpawns]:
    """Patch ``subprocess.Popen`` so every git process started inside the block is counted."""
    counter = GitSpawns()
    with mock.patch.object(subprocess, "Popen", counter):
        yield counter
