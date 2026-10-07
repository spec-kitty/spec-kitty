"""Both #4969 base resolvers build the remote-tracking ref with the one kernel builder (FR-016).

``workspace.context.resolve_lane_base_ref`` and ``lanes.implement_support.resolve_base_ref``
used to hand-write ``refs/remotes/origin/<b>`` / ``origin/<b>``. They now derive the remote
from ``kernel.git.remote.resolve_remote`` and the ref from ``tracking_ref``, so they agree
with each other and with the owner. An ``origin``-only repository behaves exactly as before.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from kernel.git.remote import tracking_ref
from specify_cli.lanes.implement_support import resolve_base_ref
from specify_cli.workspace.context import resolve_lane_base_ref

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_LANE = "kitty/mission-demo-lane-a"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def _repo_with_pushed_lane(tmp_path: Path, remote: str) -> tuple[Path, str]:
    """A repo whose only remote is *remote* and which holds a fetched ``<remote>/<lane>`` tip ahead of ``main``."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "-q", "-m", "base")
    _git(repo, "remote", "add", remote, str(tmp_path / "unused.git"))
    (repo / "b.txt").write_text("b\n", encoding="utf-8")
    _git(repo, "add", "b.txt")
    _git(repo, "commit", "-q", "-m", "teammate work")
    tip = _git(repo, "rev-parse", "HEAD")
    _git(repo, "update-ref", tracking_ref(remote, _LANE), tip)
    _git(repo, "reset", "-q", "--hard", "HEAD~1")
    return repo, tip


@pytest.mark.parametrize("remote", ["origin", "upstream"])
def test_lane_base_prefers_the_owning_remotes_tracking_ref(tmp_path: Path, remote: str) -> None:
    repo, _tip = _repo_with_pushed_lane(tmp_path, remote)

    assert resolve_lane_base_ref(repo, _LANE, fallback_base="main") == tracking_ref(remote, _LANE)


def test_lane_base_falls_back_when_no_tracking_ref_exists(tmp_path: Path) -> None:
    repo, _tip = _repo_with_pushed_lane(tmp_path, "origin")

    assert resolve_lane_base_ref(repo, "kitty/never-pushed", fallback_base="main") == "main"


@pytest.mark.parametrize("remote", ["origin", "upstream"])
def test_implement_base_resolves_to_the_short_remote_ref_and_its_tip(tmp_path: Path, remote: str) -> None:
    repo, tip = _repo_with_pushed_lane(tmp_path, remote)

    assert resolve_base_ref(repo, _LANE) == (f"{remote}/{_LANE}", tip)


def test_implement_base_keeps_a_local_ref_that_is_ahead_of_the_remote(tmp_path: Path) -> None:
    repo, tip = _repo_with_pushed_lane(tmp_path, "origin")
    _git(repo, "branch", _LANE, tip)
    (repo / "c.txt").write_text("c\n", encoding="utf-8")
    _git(repo, "checkout", "-q", _LANE)
    _git(repo, "add", "c.txt")
    _git(repo, "commit", "-q", "-m", "local ahead")
    local = _git(repo, "rev-parse", "HEAD")

    assert resolve_base_ref(repo, _LANE) == (_LANE, local)


def test_implement_base_unresolvable_everywhere_is_none(tmp_path: Path) -> None:
    repo, _tip = _repo_with_pushed_lane(tmp_path, "origin")

    assert resolve_base_ref(repo, "kitty/nowhere") is None
