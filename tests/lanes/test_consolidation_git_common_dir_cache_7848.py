"""The lane-merge pipeline reads a checkout's git common dir once per run (#7848).

The answer is a function of where the checkout's repository lives; the run's git read cache files
it under the repository it locates from the filesystem, so a linked checkout and the main
checkout give their own (equal) answers and a removed checkout is read again. Real repositories.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from kernel.git.read_cache import git_read_cache_scope
from specify_cli.lanes import consolidation

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@e", "-c", "commit.gpgsign=false", *args], cwd=cwd, check=True, capture_output=True)


@contextmanager
def _git_spawns() -> Iterator[list[list[str]]]:
    spawned: list[list[str]] = []
    real = subprocess.Popen.__init__

    def counting(self: Any, args: Any, *rest: Any, **kwargs: Any) -> None:
        spawned.append([str(a) for a in args])
        real(self, args, *rest, **kwargs)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(subprocess.Popen, "__init__", counting)
        yield spawned


def test_the_common_dir_is_read_once_per_checkout_in_a_run(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "commit", "-q", "--allow-empty", "-m", "one")
    linked = tmp_path / "linked"
    _git(root, "worktree", "add", "-q", "-b", "side", str(linked))
    common = (root / ".git").resolve()
    with git_read_cache_scope():
        with _git_spawns() as spawned:
            for _ in range(3):
                main_dir = consolidation._git_common_dir(root)
                linked_dir = consolidation._git_common_dir(linked)
        assert main_dir is not None and main_dir.resolve() == common
        assert linked_dir is not None and linked_dir.resolve() == common
        assert len(spawned) == 2
        _git(root, "worktree", "remove", "--force", str(linked))
        linked.mkdir()
        assert consolidation._git_common_dir(linked) is None  # no longer a checkout: read again, not stored
