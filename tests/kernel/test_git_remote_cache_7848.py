"""``configured_remotes`` is read once per repository config state within a run (#7848).

Real repositories: a remote added or removed through git rewrites the repository config, which
invalidates the cached listing.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from kernel.git.read_cache import git_read_cache_scope
from kernel.git.remote import configured_remotes

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def test_configured_remotes_follows_config_writes_inside_a_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    calls: list[tuple[str, ...]] = []
    import kernel.git.remote as remote
    from kernel.git.runner import run_git as real

    def counting(cwd: Path, *args: str, **kwargs: Any) -> Any:
        calls.append(args)
        return real(cwd, *args, **kwargs)

    monkeypatch.setattr(remote, "run_git", counting)
    with git_read_cache_scope():
        assert configured_remotes(root) == []
        assert configured_remotes(root) == []
        assert len(calls) == 1
        _git(root, "remote", "add", "origin", "https://example.invalid/r.git")
        assert configured_remotes(root) == ["origin"]
        _git(root, "remote", "add", "upstream", "https://example.invalid/u.git")
        assert configured_remotes(root) == ["origin", "upstream"]
        _git(root, "remote", "remove", "origin")
        assert configured_remotes(root) == ["upstream"]
        assert configured_remotes(root) == ["upstream"]
    assert len(calls) == 4


def test_a_failed_listing_is_not_stored(tmp_path: Path) -> None:
    outside = tmp_path / "not-a-repo"
    outside.mkdir()
    with git_read_cache_scope():
        assert configured_remotes(outside) == []
        _git(outside, "init", "-q")
        _git(outside, "remote", "add", "origin", "https://example.invalid/r.git")
        assert configured_remotes(outside) == ["origin"]


@pytest.mark.parametrize("legacy_dir", ["remotes", "branches"])
def test_configured_remotes_agrees_with_git_after_a_legacy_remote_file(tmp_path: Path, legacy_dir: str) -> None:
    """#7848 review NIT-1: the cached listing also depends on ``.git/remotes/`` and ``.git/branches/``.

    Whether ``git remote`` lists those legacy entries depends on the git version (2.43 does not), so
    the cached answer is compared with an uncached ``git remote`` after the write.
    """
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    with git_read_cache_scope():
        assert configured_remotes(root) == []
        legacy = root / ".git" / legacy_dir
        legacy.mkdir(exist_ok=True)
        content = "URL: https://example.invalid/r.git\n" if legacy_dir == "remotes" else "https://example.invalid/r.git\n"
        (legacy / "legacy").write_text(content, encoding="utf-8")
        listed = subprocess.run(["git", "remote"], cwd=root, check=True, capture_output=True, text=True).stdout.split()
        assert configured_remotes(root) == listed


def test_a_legacy_remote_file_invalidates_the_cached_listing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The legacy remote directories are part of the dependency: a write there re-runs ``git remote``."""
    import kernel.git.remote as remote
    from kernel.git.runner import run_git as real

    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    calls: list[tuple[str, ...]] = []

    def counting(cwd: Path, *args: str, **kwargs: Any) -> Any:
        calls.append(args)
        return real(cwd, *args, **kwargs)

    monkeypatch.setattr(remote, "run_git", counting)
    with git_read_cache_scope():
        configured_remotes(root)
        configured_remotes(root)
        assert len(calls) == 1
        (root / ".git" / "branches").mkdir(exist_ok=True)
        (root / ".git" / "branches" / "legacy").write_text("https://example.invalid/r.git\n", encoding="utf-8")
        configured_remotes(root)
    assert len(calls) == 2
