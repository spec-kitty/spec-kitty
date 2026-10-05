"""Seam tests for ``lanes.implement_support.git_stdout`` (implement-degod WP05).

``git_stdout`` is the public leaf the planning-commit adapter and the base-ref code import. It is
NOT ``lanes.lifecycle_sync._git_stdout`` (variadic args, returns ``None`` on failure): this one
takes an argv list and returns ``""`` on a non-zero exit.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.lanes import implement_support

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "T")
    (tmp_path / "f.txt").write_text("x\n", encoding="utf-8")
    _git(tmp_path, "add", "f.txt")
    _git(tmp_path, "commit", "-q", "-m", "init")
    return tmp_path


def test_returns_stripped_stdout_on_success(repo: Path) -> None:
    assert implement_support.git_stdout(repo, ["rev-parse", "--abbrev-ref", "HEAD"]) == "main"


def test_returns_empty_string_on_nonzero_exit(repo: Path) -> None:
    assert implement_support.git_stdout(repo, ["rev-parse", "--verify", "--quiet", "refs/heads/absent"]) == ""


def test_runs_in_the_given_directory(repo: Path) -> None:
    assert implement_support.git_stdout(repo, ["status", "--porcelain"]) == ""
    (repo / "g.txt").write_text("y\n", encoding="utf-8")
    assert implement_support.git_stdout(repo, ["status", "--porcelain"]) == "?? g.txt"
