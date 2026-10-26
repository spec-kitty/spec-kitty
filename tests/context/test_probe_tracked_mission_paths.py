"""``probe_tracked_mission_paths``: the one hardened tracked-path probe (#6669)."""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from kernel.git import GitCommandError
from specify_cli.context import mission_resolver
from specify_cli.context.mission_resolver import probe_tracked_mission_paths, tracked_mission_paths

pytestmark = [pytest.mark.git_repo]


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _failing(cwd: Path, *, timed_out: bool) -> Callable[[Path], frozenset[str]]:
    def _raise(_root: Path) -> frozenset[str]:
        raise GitCommandError(argv=("ls-files",), cwd=cwd, returncode=128, stderr="corrupt index", timed_out=timed_out)

    return _raise


def test_happy_path_returns_the_tracked_set(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "kitty-specs" / "m").mkdir(parents=True)
    (tmp_path / "kitty-specs" / "m" / "spec.md").write_text("# s\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")

    assert probe_tracked_mission_paths(tmp_path) == frozenset({"kitty-specs/m/spec.md"})
    assert probe_tracked_mission_paths(tmp_path) == tracked_mission_paths(tmp_path)


def test_outside_a_work_tree_is_none(tmp_path: Path) -> None:
    assert probe_tracked_mission_paths(tmp_path) is None


def test_a_git_command_error_degrades_to_none_and_warns_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.setattr(mission_resolver, "tracked_mission_paths", _failing(tmp_path, timed_out=False))

    other_root = tmp_path / "other-checkout"
    other_root.mkdir()

    with caplog.at_level(logging.WARNING, logger=mission_resolver.__name__):
        assert probe_tracked_mission_paths(tmp_path) is None
        assert probe_tracked_mission_paths(tmp_path) is None  # a second walk in the same run
        assert probe_tracked_mission_paths(other_root) is None  # another checkout root warns on its own

    warnings = [r for r in caplog.records if r.name == mission_resolver.__name__ and r.levelno == logging.WARNING]
    assert len(warnings) == 2, "one warning per checkout root, not per process or per call"
    assert "fall back to file presence" in warnings[0].getMessage()
    assert "corrupt index" in warnings[0].getMessage()


def test_a_timeout_is_reraised(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mission_resolver, "tracked_mission_paths", _failing(tmp_path, timed_out=True))

    with pytest.raises(GitCommandError) as caught:
        probe_tracked_mission_paths(tmp_path)

    assert caught.value.timed_out
