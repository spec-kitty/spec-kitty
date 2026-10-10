"""``abort_git_merge`` aborts a merge in a spec-kitty-owned merge workspace through the destructive-op guard (#5965 / #5966)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.consolidation.state import abort_git_merge

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=check)


def _conflicted_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _git(workspace, "init", "-q", "-b", "main")
    for key, value in (("user.email", "t@example.invalid"), ("user.name", "T"), ("commit.gpgsign", "false")):
        _git(workspace, "config", key, value)
    (workspace / "f.txt").write_text("base\n", encoding="utf-8")
    _git(workspace, "add", "-A")
    _git(workspace, "commit", "-q", "-m", "base")
    _git(workspace, "checkout", "-q", "-b", "side")
    (workspace / "f.txt").write_text("side\n", encoding="utf-8")
    _git(workspace, "commit", "-q", "-am", "side")
    _git(workspace, "checkout", "-q", "main")
    (workspace / "f.txt").write_text("main\n", encoding="utf-8")
    _git(workspace, "commit", "-q", "-am", "main")
    _git(workspace, "merge", "side", check=False)
    return workspace


def test_a_conflicted_merge_in_the_workspace_is_aborted(tmp_path: Path) -> None:
    workspace = _conflicted_workspace(tmp_path)
    assert (workspace / ".git" / "MERGE_HEAD").exists()

    assert abort_git_merge(workspace) is True

    assert not (workspace / ".git" / "MERGE_HEAD").exists()
    assert (workspace / "f.txt").read_text(encoding="utf-8") == "main\n"


def test_no_merge_in_progress_is_reported_as_nothing_aborted(tmp_path: Path) -> None:
    workspace = _conflicted_workspace(tmp_path)
    _git(workspace, "merge", "--abort")

    assert abort_git_merge(workspace) is False
