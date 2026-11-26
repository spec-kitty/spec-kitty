"""#5604 review fold R1: kernel name listings are immune to ``log.showSignature`` on a signed commit.

With ``log.showSignature=true`` ``git show`` / ``git log`` print gpg's verification of a signed commit
before the requested output. ``remerge_paths`` (the FR-004 own-content probe), ``commit_paths`` and
``log_paths`` parse that output as NUL-separated paths, so the verification text read as a path.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from kernel.git.listing import commit_paths, log_paths, remerge_paths
from tests._support.gpg_signing import sign_commits_and_show_signatures, use_throwaway_signing_key

pytestmark = pytest.mark.git_repo


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


def _signed_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str, str]:
    """``main`` and ``side`` each add a file in a signed commit; ``main`` then signs a clean merge of ``side``."""
    use_throwaway_signing_key(tmp_path, monkeypatch)
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-qb", "main", str(repo)], check=True)
    for key, value in (("user.email", "t@example.invalid"), ("user.name", "T")):
        _git(repo, "config", key, value)
    sign_commits_and_show_signatures(repo)
    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")
    _git(repo, "checkout", "-qb", "side")
    (repo / "side.txt").write_text("side\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "side")
    side = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "main")
    (repo / "main.txt").write_text("main\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "main")
    _git(repo, "merge", "-q", "--no-ff", "--no-edit", "side")
    merge = _git(repo, "rev-parse", "HEAD")
    shown = subprocess.run(["git", "-C", str(repo), "show", "-s", merge], capture_output=True, text=True, check=True)
    assert "Good signature" in shown.stdout + shown.stderr, "fixture: the commits must be signed"
    return repo, side, merge


def test_remerge_paths_of_a_signed_clean_merge_is_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, _side, merge = _signed_repo(tmp_path, monkeypatch)
    assert remerge_paths(repo, merge) == ()


def test_commit_paths_of_a_signed_commit_lists_only_its_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, side, _merge = _signed_repo(tmp_path, monkeypatch)
    assert [str(path) for path in commit_paths(repo, side)] == ["side.txt"]


def test_log_paths_over_signed_commits_lists_only_their_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, _side, merge = _signed_repo(tmp_path, monkeypatch)
    assert sorted(str(path) for path in log_paths(repo, f"{merge}~1..{merge}")) == ["side.txt"]
