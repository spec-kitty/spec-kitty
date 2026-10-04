"""``lane_tip.recorded_tip_branches`` — one git call lists every lane work tip (#5573 T008).

The frozen-lane preflight uses it as fallback evidence that a lane holds work
even when no status event says so. Real git in ``tmp_path`` throughout.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.lanes.lane_tip import record_tip, recorded_tip_branches

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True)


def _init_repo(repo: Path) -> str:
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "-q", "-m", "seed")
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def test_no_recorded_tips_returns_empty(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    assert recorded_tip_branches(repo) == frozenset()


def test_returns_every_recorded_branch_name(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    head = _init_repo(repo)
    record_tip(repo, "kitty/mission-x-lane-a", head)
    record_tip(repo, "lane-plain", head)
    assert recorded_tip_branches(repo) == frozenset({"kitty/mission-x-lane-a", "lane-plain"})


def test_non_git_directory_returns_empty(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    assert recorded_tip_branches(plain) == frozenset()


def test_missing_git_binary_returns_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _no_git(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("git")

    monkeypatch.setattr("specify_cli.lanes.lane_tip.subprocess.run", _no_git)
    assert recorded_tip_branches(tmp_path) == frozenset()
