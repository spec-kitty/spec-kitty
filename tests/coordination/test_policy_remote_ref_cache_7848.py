"""The workflow policy's remote-tracking probe is cached per ref within a run (#7848).

Real repositories: creating or deleting the probed ref invalidates the answer.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from kernel.git.read_cache import git_read_cache_scope
from specify_cli.coordination import policy

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


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


def test_remote_tracking_probe_follows_the_ref_inside_a_run(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "-c", "user.name=t", "-c", "user.email=t@e", "-c", "commit.gpgsign=false", "commit", "-q", "--allow-empty", "-m", "one")
    head = _git(root, "rev-parse", "HEAD")
    with git_read_cache_scope():
        with _git_spawns() as spawned:
            assert policy._remote_tracking_branch_exists(root, "feature") is False
            assert policy._remote_tracking_branch_exists(root, "feature") is False
        assert len(spawned) == 2  # refs/remotes/feature and refs/remotes/origin/feature, once each
        _git(root, "update-ref", "refs/remotes/origin/feature", head)
        assert policy._remote_tracking_branch_exists(root, "feature") is True
        _git(root, "update-ref", "-d", "refs/remotes/origin/feature")
        assert policy._remote_tracking_branch_exists(root, "feature") is False
        _git(root, "update-ref", "refs/remotes/origin/feature", head)
        assert policy._remote_tracking_branch_exists(root, "origin/feature") is True
