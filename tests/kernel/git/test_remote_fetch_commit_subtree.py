"""``fetch_commit_subtree`` against a REAL ``file://`` bare repository (WP02 / T043)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from kernel.git.remote import CommitUnresolvable, RemoteUnreachable, fetch_commit_subtree

pytestmark = [pytest.mark.git_repo]

_SUBTREE = "packs/built-in"
_MISSING_SHA = "0" * 40


def _env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_AUTHOR_NAME="t",
        GIT_AUTHOR_EMAIL="t@example.invalid",
        GIT_COMMITTER_NAME="t",
        GIT_COMMITTER_EMAIL="t@example.invalid",
    )
    return env


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, env=_env(), check=True, capture_output=True, text=True).stdout.strip()


def _make_remote(tmp_path: Path, *, allow_filter: bool = True) -> tuple[str, str]:
    work = tmp_path / "work"
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")
    (work / _SUBTREE).mkdir(parents=True)
    (work / _SUBTREE / "a.txt").write_text("alpha\n")
    (work / "other").mkdir()
    (work / "other" / "b.txt").write_text("beta\n")
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "init")
    sha = _git(work, "rev-parse", "HEAD")
    bare = tmp_path / "remote.git"
    _git(tmp_path, "clone", "-q", "--bare", str(work), str(bare))
    _git(bare, "config", "uploadpack.allowFilter", "true" if allow_filter else "false")
    _git(bare, "config", "uploadpack.allowAnySHA1InWant", "true")
    return bare.as_uri(), sha


def test_fetches_only_the_requested_subtree(tmp_path: Path) -> None:
    url, sha = _make_remote(tmp_path)
    dest = tmp_path / "dest"
    fetch_commit_subtree(url, sha, _SUBTREE, dest, timeout=60)
    assert (dest / _SUBTREE / "a.txt").read_text() == "alpha\n"
    assert not (dest / "other" / "b.txt").exists()


def test_user_autocrlf_does_not_rewrite_fetched_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Windows runners set core.autocrlf=true globally; the pinned full-tree digest
    # hashes raw bytes, so the fetch must check out exactly what the commit holds.
    url, sha = _make_remote(tmp_path)
    global_config = tmp_path / "gitconfig"
    global_config.write_text("[core]\n\tautocrlf = true\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    dest = tmp_path / "dest"
    fetch_commit_subtree(url, sha, _SUBTREE, dest, timeout=60)
    assert (dest / _SUBTREE / "a.txt").read_bytes() == b"alpha\n"


def test_falls_back_when_the_server_refuses_filter(tmp_path: Path) -> None:
    url, sha = _make_remote(tmp_path, allow_filter=False)
    dest = tmp_path / "dest"
    fetch_commit_subtree(url, sha, _SUBTREE, dest, timeout=60)
    assert (dest / _SUBTREE / "a.txt").read_text() == "alpha\n"


def test_unknown_sha_is_commit_unresolvable(tmp_path: Path) -> None:
    url, _ = _make_remote(tmp_path)
    with pytest.raises(CommitUnresolvable):
        fetch_commit_subtree(url, _MISSING_SHA, _SUBTREE, tmp_path / "dest", timeout=60)


def test_unreachable_url_is_remote_unreachable_not_unresolvable(tmp_path: Path) -> None:
    url = (tmp_path / "nowhere.git").as_uri()
    with pytest.raises(RemoteUnreachable) as info:
        fetch_commit_subtree(url, _MISSING_SHA, _SUBTREE, tmp_path / "dest", timeout=60)
    assert not isinstance(info.value, CommitUnresolvable)


@pytest.mark.parametrize("url", ["-oProxyCommand=evil", "ssh://host/repo.git", "http://host/repo.git", "/local/path"])
def test_refuses_unsafe_urls(tmp_path: Path, url: str) -> None:
    with pytest.raises(ValueError, match="url"):
        fetch_commit_subtree(url, _MISSING_SHA, _SUBTREE, tmp_path / "dest", timeout=5)


@pytest.mark.parametrize("sha", ["main", "--upload-pack=x", "abc", "G" * 40])
def test_refuses_non_sha(tmp_path: Path, sha: str) -> None:
    with pytest.raises(ValueError, match="sha"):
        fetch_commit_subtree("file:///x", sha, _SUBTREE, tmp_path / "dest", timeout=5)


@pytest.mark.parametrize("subtree", ["", "/abs", "a/../b", "..", "-x"])
def test_refuses_unsafe_subtree(tmp_path: Path, subtree: str) -> None:
    with pytest.raises(ValueError, match="subtree"):
        fetch_commit_subtree("file:///x", _MISSING_SHA, subtree, tmp_path / "dest", timeout=5)
