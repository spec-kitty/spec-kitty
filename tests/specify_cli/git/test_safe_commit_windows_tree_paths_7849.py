"""#7849: ``safe_commit`` names nested paths to git trees with ``/``, on every platform.

``preflight_commit`` normalizes requested paths with ``str(Path)``, which spells a nested
path with ``\\`` on Windows. ``git add`` accepts that spelling as a pathspec, but a tree
object path does not: ``git rev-parse <tree>:kitty-specs\\m\\status.events.jsonl`` fails
with ``fatal: Needed a single revision``. The expected-parent mode's raw-bytes check
(``expected_path_bytes``) named the staged blob that way, so every pinned-parent commit of
a nested path refused on Windows (setup-plan's lifecycle commit since #3933). The same
spelling reached the runtime-lock tree check (``tree_entry``) and the gitlink index probe
(``index_entries``), where a non-match is silently "absent", not a refusal.

The unit tests simulate Windows path semantics by substituting ``PureWindowsPath`` for the
module's ``Path``, so they go red on Linux too. The integration test runs the real commit
with a nested path on every platform, and on the ``windows_ci`` lane exercises the
backslash spelling for real.
"""

from __future__ import annotations

import subprocess
from pathlib import Path, PureWindowsPath
from typing import cast

import pytest

from kernel.git.listing import IndexEntry
from kernel.git.paths import GitPath
from specify_cli.git import commit_helpers
from specify_cli.git.commit_helpers import safe_commit

_BRANCH = "kitty/mission-7849-nested"
_NESTED = "kitty-specs/m-7849/status.events.jsonl"
_NESTED_WINDOWS = "kitty-specs\\m-7849\\status.events.jsonl"


@pytest.fixture
def windows_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    """Give ``commit_helpers`` Windows path semantics (``str(Path)`` spells ``\\``)."""
    monkeypatch.setattr(commit_helpers, "Path", PureWindowsPath)


@pytest.mark.fast
def test_expected_bytes_keys_use_git_tree_spelling_on_windows(tmp_path: Path, windows_paths: None) -> None:
    normalized = commit_helpers._normalize_expected_parent_path_bytes(
        tmp_path,
        [_NESTED_WINDOWS],  # what preflight_commit returns on Windows
        {cast(Path, PureWindowsPath(_NESTED)): b"{}\n"},
    )

    assert normalized == {_NESTED: b"{}\n"}


@pytest.mark.fast
def test_expected_bytes_still_refuses_an_unrequested_path_on_windows(tmp_path: Path, windows_paths: None) -> None:
    with pytest.raises(RuntimeError, match="was not requested for staging"):
        commit_helpers._normalize_expected_parent_path_bytes(
            tmp_path,
            ["kitty-specs\\m-7849\\other.json"],
            {cast(Path, PureWindowsPath(_NESTED)): b"{}\n"},
        )


@pytest.mark.fast
def test_gitlink_probe_matches_a_windows_spelled_path(tmp_path: Path, windows_paths: None, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[list[str]] = []

    def fake_index_entries(_root: Path, *, pathspecs: list[str]) -> tuple[IndexEntry, ...]:
        seen.append(pathspecs)
        return (IndexEntry(mode="160000", oid="0" * 40, stage=0, path=GitPath.parse("vendor/mod")),)

    monkeypatch.setattr(commit_helpers, "index_entries", fake_index_entries)

    assert commit_helpers._is_gitlink(tmp_path, "vendor\\mod") is True
    assert seen == [["vendor/mod"]]


@pytest.mark.fast
def test_expected_bytes_keeps_a_posix_backslash_as_a_filename_character(tmp_path: Path) -> None:
    # On POSIX ``\\`` is an ordinary filename character, never a separator.
    normalized = commit_helpers._normalize_expected_parent_path_bytes(tmp_path, ["odd\\name.txt"], {Path("odd\\name.txt"): b"x"})

    assert normalized == {"odd\\name.txt": b"x"}


_LOCK_WINDOWS = "kitty-specs\\m-7849\\decisions\\.runtime.lock"


@pytest.mark.fast
def test_runtime_lock_tree_check_looks_up_a_windows_spelled_lock(tmp_path: Path, windows_paths: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """A lock still in the candidate tree is refused, even when staging spelled it with ``\\``."""
    looked_up: list[str] = []

    def fake_tree_entry(_root: Path, _tree: str, path: str, **_: object) -> object | None:
        looked_up.append(path)
        return object() if path == "kitty-specs/m-7849/decisions/.runtime.lock" else None

    ok = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
    monkeypatch.setattr(commit_helpers, "_run_git_for_commit", lambda *_a, **_k: ok)
    monkeypatch.setattr(commit_helpers, "_write_expected_parent_tree", lambda *_a, **_k: "tree-sha")
    monkeypatch.setattr(commit_helpers, "_run_expected_parent_hook", lambda *_a, **_k: None)
    monkeypatch.setattr(commit_helpers, "tree_entry", fake_tree_entry)

    with pytest.raises(RuntimeError, match="decision runtime lock remains in candidate tree"):
        commit_helpers._build_expected_parent_tree(
            tmp_path,
            "parent-sha",
            [_LOCK_WINDOWS],
            tmp_path / "COMMIT_EDITMSG",
            env={},
            expected_path_bytes={},
            index_only_removals=frozenset({_LOCK_WINDOWS}),
        )
    assert looked_up == ["kitty-specs/m-7849/decisions/.runtime.lock"]


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "kitty-specs" / "m-7849").mkdir(parents=True)
    _git(root, "init", "-q", "-b", _BRANCH)
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test User")
    _git(root, "config", "commit.gpgsign", "false")
    (root / _NESTED).write_bytes(b"")
    _git(root, "add", _NESTED)
    _git(root, "commit", "-q", "-m", "seed")
    return root


def _assert_expected_parent_commit_of_a_nested_path_lands(repo: Path) -> None:
    parent = _git(repo, "rev-parse", f"refs/heads/{_BRANCH}")
    log = repo / "kitty-specs" / "m-7849" / "status.events.jsonl"
    payload = b'{"event_id": "01K7849"}\n'
    log.write_bytes(payload)

    result = safe_commit(
        repo_root=repo,
        worktree_root=repo,
        destination_ref=_BRANCH,
        message="chore(spec-kitty): lifecycle event",
        paths=(log,),
        expected_parent_sha=parent,
        expected_path_bytes={log: payload},
    )

    assert _git(repo, "rev-parse", f"refs/heads/{_BRANCH}") == result.sha
    assert _git(repo, "rev-parse", f"{result.sha}^") == parent
    assert _git(repo, "show", f"{result.sha}:{_NESTED}") == payload.decode().strip()


@pytest.mark.integration
@pytest.mark.git_repo
def test_expected_parent_commit_of_a_nested_path_lands(repo: Path) -> None:
    _assert_expected_parent_commit_of_a_nested_path_lands(repo)


@pytest.mark.windows_ci
@pytest.mark.integration
@pytest.mark.git_repo
def test_expected_parent_commit_of_a_nested_path_lands_on_windows(repo: Path) -> None:
    """The #7849 reproduction: on Windows ``preflight_commit`` spells the path with ``\\``."""
    _assert_expected_parent_commit_of_a_nested_path_lands(repo)
