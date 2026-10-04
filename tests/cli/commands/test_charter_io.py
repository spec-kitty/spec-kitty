"""Bucket B (filesystem I/O) coverage for ``specify_cli.cli.commands.charter``.

These tests call internal helper functions directly using ``tmp_path`` real
I/O.  No patch of ``Path.read_text``, ``Path.write_text``, or
``os.path.exists`` — all file-system interactions use real files.

Tactic: function-over-form-testing (src/charter/offering/tactics/built-in/testing/).
Structure: AAA (Arrange / Act / Assert).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests._support.eacces import deny_path_method
from specify_cli.cli.commands.charter import (
    _display_path,
    _interview_path,
    _resolve_charter_path,
    _parse_csv_option,
    _ensure_gitignore_entries,
    _get_mission_id,
)
from specify_cli.task_utils import TaskCliError


# ---------------------------------------------------------------------------
# _resolve_charter_path
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.integration]

def test_resolve_charter_path_returns_path_when_file_exists(tmp_path: Path) -> None:
    """Arrange: charter.md exists at canonical location;
    Act: resolve;
    Assert: returned path points to the file."""
    charter_dir = tmp_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True)
    charter_file = charter_dir / "charter.md"
    charter_file.write_text("# Charter\n", encoding="utf-8")

    result = _resolve_charter_path(tmp_path)

    assert result == charter_file


def test_resolve_charter_path_raises_when_file_missing(tmp_path: Path) -> None:
    """Arrange: no charter.md exists;
    Act: resolve;
    Assert: TaskCliError is raised with actionable message."""
    (tmp_path / ".kittify" / "charter").mkdir(parents=True)

    with pytest.raises(TaskCliError) as exc_info:
        _resolve_charter_path(tmp_path)

    assert "charter" in str(exc_info.value).lower() or "not found" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# _parse_csv_option
# ---------------------------------------------------------------------------

def test_parse_csv_option_returns_none_when_input_is_none() -> None:
    """Arrange: None input; Act: parse; Assert: None returned."""
    result = _parse_csv_option(None)
    assert result is None


def test_parse_csv_option_splits_comma_separated_values() -> None:
    """Arrange: comma-separated string; Act: parse; Assert: list returned."""
    result = _parse_csv_option("alpha, beta, gamma")
    assert result == ["alpha", "beta", "gamma"]


def test_parse_csv_option_filters_empty_parts() -> None:
    """Arrange: string with trailing/double commas; Act: parse; Assert: empties dropped."""
    result = _parse_csv_option("alpha,,beta,")
    assert "alpha" in result
    assert "beta" in result
    assert "" not in result


def test_parse_csv_option_empty_string_returns_empty_list() -> None:
    """Arrange: empty string; Act: parse; Assert: empty list returned."""
    result = _parse_csv_option("")
    assert result == []


# ---------------------------------------------------------------------------
# _interview_path
# ---------------------------------------------------------------------------

def test_interview_path_returns_expected_location(tmp_path: Path) -> None:
    """Arrange: project root; Act: resolve interview path; Assert: canonical path returned."""
    expected = tmp_path / ".kittify" / "charter" / "interview" / "answers.yaml"
    result = _interview_path(tmp_path)
    assert result == expected


# ---------------------------------------------------------------------------
# _display_path
# ---------------------------------------------------------------------------

def test_display_path_returns_relative_string_when_subpath(tmp_path: Path) -> None:
    """Arrange: path inside repo_root; Act: display; Assert: relative string returned."""
    sub = tmp_path / "subdir" / "file.txt"
    result = _display_path(sub, tmp_path)
    assert "subdir/file.txt" in result


def test_display_path_returns_absolute_when_outside_root(tmp_path: Path) -> None:
    """Arrange: path outside repo_root; Act: display; Assert: absolute path returned."""
    other = Path("/some/outside/path")
    result = _display_path(other, tmp_path)
    # Should not crash; returns str representation of the path
    assert "/some/outside/path" in result


# ---------------------------------------------------------------------------
# _ensure_gitignore_entries
# ---------------------------------------------------------------------------

def test_ensure_gitignore_entries_creates_gitignore_when_missing(tmp_path: Path) -> None:
    """Arrange: no .gitignore; Act: ensure entries; Assert: .gitignore created with entries."""
    _ensure_gitignore_entries(tmp_path, [".kittify/charter/governance.yaml"])

    gitignore = tmp_path / ".gitignore"
    assert gitignore.exists()
    content = gitignore.read_text(encoding="utf-8")
    assert ".kittify/charter/governance.yaml" in content


def test_ensure_gitignore_entries_appends_when_entry_absent(tmp_path: Path) -> None:
    """Arrange: .gitignore with some content; Act: ensure new entry; Assert: entry appended."""
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("__pycache__/\n", encoding="utf-8")

    _ensure_gitignore_entries(tmp_path, [".kittify/charter/directives.yaml"])

    content = gitignore.read_text(encoding="utf-8")
    assert "__pycache__/" in content
    assert ".kittify/charter/directives.yaml" in content


def test_ensure_gitignore_entries_skips_already_present_entries(tmp_path: Path) -> None:
    """Arrange: .gitignore already has the required entry; Act: ensure; Assert: no duplicate."""
    gitignore = tmp_path / ".gitignore"
    original = ".kittify/charter/governance.yaml\n"
    gitignore.write_text(original, encoding="utf-8")

    _ensure_gitignore_entries(tmp_path, [".kittify/charter/governance.yaml"])

    content = gitignore.read_text(encoding="utf-8")
    assert content.count(".kittify/charter/governance.yaml") == 1


def test_ensure_gitignore_entries_noop_when_all_present(tmp_path: Path) -> None:
    """Arrange: .gitignore already contains all required entries; Act: ensure; Assert: file unchanged."""
    entries = [".kittify/charter/governance.yaml", ".kittify/charter/directives.yaml"]
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("\n".join(entries) + "\n", encoding="utf-8")
    original_mtime = gitignore.stat().st_mtime_ns

    _ensure_gitignore_entries(tmp_path, entries)

    # File should not have been rewritten (mtime preserved)
    assert gitignore.stat().st_mtime_ns == original_mtime


# ---------------------------------------------------------------------------
# _get_mission_id
# ---------------------------------------------------------------------------

def test_get_mission_id_returns_mission_id_from_meta_json(tmp_path: Path) -> None:
    """Arrange: kitty-specs/<slug>/meta.json with mission_id; Act: resolve; Assert: ULID returned."""
    slug = "my-feature"
    meta_dir = tmp_path / "kitty-specs" / slug
    meta_dir.mkdir(parents=True)
    (meta_dir / "meta.json").write_text(
        json.dumps({"mission_id": "01ABCDEFGHIJKLMNOPQRSTUVWX"}),
        encoding="utf-8",
    )

    result = _get_mission_id(tmp_path, slug)

    assert result == "01ABCDEFGHIJKLMNOPQRSTUVWX"


def test_get_mission_id_returns_none_when_meta_json_missing(tmp_path: Path) -> None:
    """Arrange: no meta.json; Act: resolve; Assert: None returned (no exception)."""
    result = _get_mission_id(tmp_path, "nonexistent-feature")
    assert result is None


def test_get_mission_id_returns_none_when_mission_id_key_absent(tmp_path: Path) -> None:
    """Arrange: meta.json without mission_id key; Act: resolve; Assert: None returned."""
    slug = "other-feature"
    meta_dir = tmp_path / "kitty-specs" / slug
    meta_dir.mkdir(parents=True)
    (meta_dir / "meta.json").write_text(json.dumps({"mission_number": 42}), encoding="utf-8")

    result = _get_mission_id(tmp_path, slug)

    assert result is None


def test_get_mission_id_returns_none_when_meta_json_malformed(tmp_path: Path) -> None:
    """Arrange: meta.json with invalid JSON; Act: resolve; Assert: None returned (graceful)."""
    slug = "broken-feature"
    meta_dir = tmp_path / "kitty-specs" / slug
    meta_dir.mkdir(parents=True)
    (meta_dir / "meta.json").write_text("{bad json", encoding="utf-8")

    result = _get_mission_id(tmp_path, slug)

    assert result is None


# ---------------------------------------------------------------------------
# Permission-denied edge case
# ---------------------------------------------------------------------------

def test_resolve_charter_path_raises_when_directory_not_readable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Arrange: .kittify/charter exists but stat on charter.md is denied;
    Act: resolve;
    Assert: PermissionError raised rather than a silent fallback.

    The denial is injected at the ``Path.exists`` seam instead of ``chmod 000``:
    root bypasses file mode bits, so the chmod form gave different verdicts by
    uid (#5622).
    """
    charter_dir = tmp_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True)
    charter_file = charter_dir / "charter.md"
    charter_file.write_text("# Charter\n", encoding="utf-8")

    deny_path_method(monkeypatch, "exists", charter_file)
    with pytest.raises(PermissionError):
        _resolve_charter_path(tmp_path)
