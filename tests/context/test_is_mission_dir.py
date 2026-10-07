"""``is_mission_dir``: the one is-a-Mission predicate (#5812)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.context.mission_resolver import is_mission_dir, tracked_mission_paths

pytestmark = [pytest.mark.git_repo]


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "T")
    (tmp_path / ".gitignore").write_text("*.lock\n", encoding="utf-8")
    return tmp_path


def _dir(repo: Path, name: str) -> Path:
    path = repo / "kitty-specs" / name
    path.mkdir(parents=True)
    return path


@pytest.mark.parametrize("marker", ["spec.md", "meta.json"])
@pytest.mark.parametrize("batch", [False, True])
def test_tracked_marker_is_a_mission(repo: Path, marker: str, batch: bool) -> None:
    path = _dir(repo, "m-01AAAAAA")
    (path / marker).write_text("{}" if marker == "meta.json" else "# s\n", encoding="utf-8")
    _git(repo, "add", "-A")
    tracked = tracked_mission_paths(repo) if batch else None
    assert is_mission_dir(path, repo_root=repo, tracked=tracked)


def test_untracked_meta_with_mission_id_is_a_mission(repo: Path) -> None:
    path = _dir(repo, "fresh-01BBBBBB")
    (path / "meta.json").write_text(json.dumps({"mission_id": "01HZZZZZZZZZZZZZZZZZZZZREA"}), encoding="utf-8")
    assert is_mission_dir(path, repo_root=repo, tracked=tracked_mission_paths(repo))


def test_gitignored_lock_only_is_residue(repo: Path) -> None:
    path = _dir(repo, "ghost-01CCCCCC")
    (path / "decisions").mkdir()
    (path / "decisions" / "index.json.lock").write_text("", encoding="utf-8")
    assert not is_mission_dir(path, repo_root=repo, tracked=tracked_mission_paths(repo))
    assert not is_mission_dir(path, repo_root=repo)


def test_untracked_meta_without_mission_id_is_residue(repo: Path) -> None:
    path = _dir(repo, "noid-01DDDDDD")
    (path / "meta.json").write_text(json.dumps({"mission_id": ""}), encoding="utf-8")
    assert not is_mission_dir(path, repo_root=repo, tracked=tracked_mission_paths(repo))


def test_non_git_root_falls_back_to_existence_rule(tmp_path: Path) -> None:
    has_spec = tmp_path / "kitty-specs" / "a"
    has_spec.mkdir(parents=True)
    (has_spec / "spec.md").write_text("# s\n", encoding="utf-8")
    empty = tmp_path / "kitty-specs" / "b"
    empty.mkdir()
    assert tracked_mission_paths(tmp_path) is None
    assert is_mission_dir(has_spec, repo_root=tmp_path)
    assert not is_mission_dir(empty, repo_root=tmp_path)
