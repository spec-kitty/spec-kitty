"""Regression tests for the post-merge working-tree invariant helper.

Exercises _classify_porcelain_lines() to verify that:
- Untracked (??) lines never appear in offending_lines (T001/T002)
- Tracked modifications/deletions are offending (T003)
- Mixed lines produce the correct split (T004)
- expected_paths exemption works (T005)

Entries are typed ``StatusEntry`` records (NUL-delimited porcelain), so the former
"malformed line is ignored" case cannot occur and is gone.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from kernel.git import GitPath, StatusEntry
from specify_cli.cli.commands.consolidate import (
    _classify_porcelain_lines,
    _refresh_primary_checkout_after_merge,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _porcelain_entries(lines: list[str]) -> list[StatusEntry]:
    """Typed entries for plain ``XY path`` porcelain lines (no renames; blank lines skipped)."""
    return [StatusEntry(xy=line[:2], path=GitPath.parse(line[3:].rstrip("/")), is_directory=line.endswith("/")) for line in lines if line.strip()]


def test_classify_untracked_lines_returns_empty_offending() -> None:
    """?? lines must not appear in offending_lines."""
    lines = ["?? .claude/", "?? .agents/", "?? .kittify/merge-state.json"]
    expected: set[str] = {
        "kitty-specs/test/status.events.jsonl",
        "kitty-specs/test/status.json",
    }
    offending, skipped = _classify_porcelain_lines(_porcelain_entries(lines), expected)
    assert offending == []
    assert skipped == 3


def test_classify_tracked_modification_is_offending() -> None:
    """' M' lines for tracked files are offending."""
    lines = [" M src/specify_cli/some_module.py"]
    offending, skipped = _classify_porcelain_lines(_porcelain_entries(lines), set())
    assert [entry.display() for entry in offending] == [" M src/specify_cli/some_module.py"]
    assert skipped == 0


def test_classify_mixed_untracked_and_tracked() -> None:
    """Mix of ?? and ' M': tracked line is offending, untracked is not."""
    lines = ["?? .claude/", " M src/specify_cli/some_module.py"]
    offending, skipped = _classify_porcelain_lines(_porcelain_entries(lines), set())
    assert [entry.display() for entry in offending] == [" M src/specify_cli/some_module.py"]
    assert skipped == 1


def test_classify_deletion_is_offending() -> None:
    """' D' lines are offending."""
    lines = [" D src/specify_cli/old_module.py"]
    offending, skipped = _classify_porcelain_lines(_porcelain_entries(lines), set())
    assert [entry.display() for entry in offending] == [" D src/specify_cli/old_module.py"]
    assert skipped == 0


def test_classify_expected_path_not_offending() -> None:
    """Paths in expected_paths are not offending regardless of status code."""
    lines = [" M kitty-specs/feat/status.events.jsonl"]
    expected = {"kitty-specs/feat/status.events.jsonl"}
    offending, skipped = _classify_porcelain_lines(_porcelain_entries(lines), expected)
    assert offending == []
    assert skipped == 0


def test_classify_empty_lines_ignored() -> None:
    """Empty and whitespace-only lines are silently dropped."""
    lines = ["", "   ", " M src/specify_cli/some_module.py"]
    offending, skipped = _classify_porcelain_lines(_porcelain_entries(lines), set())
    assert [entry.display() for entry in offending] == [" M src/specify_cli/some_module.py"]


def test_classify_multiple_untracked_directories() -> None:
    """Multiple untracked agent directories common in fresh checkouts are ignored."""
    lines = [
        "?? .amazonq/",
        "?? .augment/",
        "?? .claude/",
        "?? .cursor/",
        "?? .gemini/",
        "?? .kiro/",
        "?? .opencode/",
    ]
    offending, skipped = _classify_porcelain_lines(_porcelain_entries(lines), set())
    assert offending == []
    assert skipped == 7


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=True,
    )


def test_refresh_primary_checkout_removes_sparse_rename_source(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")

    old_path = repo / "scripts" / "google" / "authorize-calendar.py"
    new_path = repo / "docs" / "archive" / "scripts" / "authorize-calendar.py"
    old_path.parent.mkdir(parents=True)
    old_path.write_text("authorize\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial")

    _git(repo, "sparse-checkout", "init", "--no-cone")
    (repo / ".git" / "info" / "sparse-checkout").write_text("/*\n", encoding="utf-8")
    _git(repo, "read-tree", "-mu", "HEAD")

    _git(repo, "switch", "-c", "kitty/mission-rename")
    new_path.parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "mv", "scripts/google/authorize-calendar.py", "docs/archive/scripts/authorize-calendar.py")
    _git(repo, "commit", "-m", "rename script")
    _git(repo, "switch", "main")

    new_tree = _git(repo, "rev-parse", "kitty/mission-rename^{tree}").stdout.strip()
    new_commit = _git(repo, "commit-tree", new_tree, "-p", "main", "-m", "squash").stdout.strip()
    _git(repo, "update-ref", "refs/heads/main", new_commit)

    checkout_only = subprocess.run(
        ["git", "checkout", "HEAD", "--", "."],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )
    assert checkout_only.returncode == 0
    assert "A  scripts/google/authorize-calendar.py" in _git(repo, "status", "--porcelain").stdout

    _refresh_primary_checkout_after_merge(repo)

    assert _git(repo, "status", "--porcelain").stdout == ""
    assert not old_path.exists()
    assert new_path.exists()
