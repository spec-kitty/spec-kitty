"""Tests for safe per-project command cleanup across both upgrade paths."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from specify_cli.upgrade.migrations.m_3_1_2_globalize_commands import (
    GlobalizeCommandsMigration,
    _VERSION_MARKER_PREFIX,
)
from specify_cli.upgrade.migrations.m_3_2_0a4_safe_globalize_commands import (
    SafeGlobalizeCommandsMigration,
)

pytestmark = pytest.mark.fast

_MARKER = f"{_VERSION_MARKER_PREFIX} 3.1.1a2 -->\n"


@pytest.fixture(params=[GlobalizeCommandsMigration, SafeGlobalizeCommandsMigration], ids=["3.1.2", "3.2.0a4"])
def migration(request: pytest.FixtureRequest) -> GlobalizeCommandsMigration | SafeGlobalizeCommandsMigration:
    return request.param()


def _make_project(tmp_path: Path, agent_files: dict[str, str]) -> Path:
    (tmp_path / ".kittify").mkdir()
    for rel_path, content in agent_files.items():
        full = tmp_path / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
    return tmp_path


def test_generated_file_is_kept_without_review_when_global_runtime_is_absent(
    tmp_path: Path,
    migration: GlobalizeCommandsMigration | SafeGlobalizeCommandsMigration,
) -> None:
    project = _make_project(tmp_path, {
        ".claude/commands/spec-kitty.implement.md": f"{_MARKER}# content",
    })
    with patch.object(migration, "_global_runtime_present", return_value=False):
        result = migration.apply(project)
    assert result.success
    assert result.manual_review_required is False
    assert result.preserved_paths == []
    assert any("Kept" in change and "global runtime" in change for change in result.changes_made)
    assert (project / ".claude/commands/spec-kitty.implement.md").exists()


def test_marker_less_file_is_held_even_without_runtime(
    tmp_path: Path,
    migration: GlobalizeCommandsMigration | SafeGlobalizeCommandsMigration,
) -> None:
    project = _make_project(tmp_path, {
        ".claude/commands/spec-kitty.custom.md": "# hand written, no marker\n",
    })
    with patch.object(migration, "_global_runtime_present", return_value=False):
        result = migration.apply(project)

    assert result.manual_review_required is True
    assert result.preserved_paths == [".claude/commands/spec-kitty.custom.md"]
    assert (project / ".claude/commands/spec-kitty.custom.md").exists()


def test_per_agent_skip_keeps_generated_file_without_review(
    tmp_path: Path,
    migration: GlobalizeCommandsMigration | SafeGlobalizeCommandsMigration,
) -> None:
    project = _make_project(tmp_path, {
        ".claude/commands/spec-kitty.implement.md": f"{_MARKER}# content",
        ".codex/prompts/spec-kitty.implement.md": f"{_MARKER}# content",
    })

    def mock_global_commands(agent_root: str, subdir: str, filename: str) -> bool:
        return agent_root == ".codex"

    with patch.object(migration, "_global_runtime_present", return_value=True), \
         patch.object(migration, "_global_command_file_present", side_effect=mock_global_commands):
        result = migration.apply(project)

    assert result.success
    assert result.manual_review_required is False
    assert result.preserved_paths == []
    assert any("Kept: .claude/commands/spec-kitty.implement.md" in change for change in result.changes_made)
    assert (project / ".claude/commands/spec-kitty.implement.md").exists()
    assert not (project / ".codex/prompts/spec-kitty.implement.md").exists()


def test_no_version_header_skips_file_and_flags_review(
    tmp_path: Path,
    migration: GlobalizeCommandsMigration | SafeGlobalizeCommandsMigration,
) -> None:
    project = _make_project(tmp_path, {
        ".claude/commands/spec-kitty.implement.md": f"{_MARKER}# generated",
        ".claude/commands/spec-kitty.custom.md": "# no marker here\n# user-authored",
    })
    with patch.object(migration, "_global_runtime_present", return_value=True), \
         patch.object(migration, "_global_command_file_present", return_value=True):
        result = migration.apply(project)

    assert not (project / ".claude/commands/spec-kitty.implement.md").exists()
    assert (project / ".claude/commands/spec-kitty.custom.md").exists()
    assert result.manual_review_required is True
    assert result.preserved_paths == [".claude/commands/spec-kitty.custom.md"]


def test_dry_run_no_deletions(
    tmp_path: Path,
    migration: GlobalizeCommandsMigration | SafeGlobalizeCommandsMigration,
) -> None:
    project = _make_project(tmp_path, {
        ".claude/commands/spec-kitty.implement.md": f"{_MARKER}# content",
    })
    with patch.object(migration, "_global_runtime_present", return_value=True), \
         patch.object(migration, "_global_command_file_present", return_value=True):
        result = migration.apply(project, dry_run=True)

    assert result.success
    assert result.manual_review_required is False
    assert any("Would remove" in change for change in result.changes_made)
    assert (project / ".claude/commands/spec-kitty.implement.md").exists()


def test_mixed_agents(
    tmp_path: Path,
    migration: GlobalizeCommandsMigration | SafeGlobalizeCommandsMigration,
) -> None:
    project = _make_project(tmp_path, {
        ".claude/commands/spec-kitty.implement.md": f"{_MARKER}# content",
        ".codex/prompts/spec-kitty.implement.md": f"{_MARKER}# content",
        ".opencode/command/spec-kitty.implement.md": f"{_MARKER}# content",
    })

    def mock_global(agent_root: str, subdir: str, filename: str) -> bool:
        return agent_root in (".claude", ".opencode")

    with patch.object(migration, "_global_runtime_present", return_value=True), \
         patch.object(migration, "_global_command_file_present", side_effect=mock_global):
        result = migration.apply(project)

    assert not (project / ".claude/commands/spec-kitty.implement.md").exists()
    assert (project / ".codex/prompts/spec-kitty.implement.md").exists()
    assert not (project / ".opencode/command/spec-kitty.implement.md").exists()
    assert result.manual_review_required is False
    assert result.preserved_paths == []
    assert any("Kept: .codex/prompts/spec-kitty.implement.md" in change for change in result.changes_made)


def test_detect_false_when_no_files(
    tmp_path: Path,
    migration: GlobalizeCommandsMigration | SafeGlobalizeCommandsMigration,
) -> None:
    _make_project(tmp_path, {".claude/commands/my-custom.md": "# user file"})
    assert migration.detect(tmp_path) is False


_NEW_FORMAT_BODY = (
    "---\n"
    "description: Execute a work package implementation\n"
    "---\n"
    f"{_VERSION_MARKER_PREFIX} 3.1.1a2 -->\n"
    "Run this exact command and treat its output as authoritative.\n"
    "Do not rediscover context from branches, files, or prompt contents.\n"
    "In repos with multiple missions, pass --mission <slug> in your arguments.\n"
    "\n"
    "`spec-kitty agent action implement $ARGUMENTS --agent claude`\n"
)


def test_is_generated_file_recognizes_new_format(tmp_path: Path) -> None:
    target = tmp_path / "spec-kitty.implement.md"
    target.write_text(_NEW_FORMAT_BODY, encoding="utf-8")
    assert GlobalizeCommandsMigration._is_generated_file(target) is True


def test_is_generated_file_recognizes_old_format(tmp_path: Path) -> None:
    target = tmp_path / "spec-kitty.legacy.md"
    target.write_text(f"{_MARKER}# legacy body\n", encoding="utf-8")
    assert GlobalizeCommandsMigration._is_generated_file(target) is True


def test_is_generated_file_rejects_user_authored(tmp_path: Path) -> None:
    target = tmp_path / "spec-kitty.custom.md"
    target.write_text(
        "---\n"
        "description: My personal command\n"
        "---\n"
        "Do something useful.\n",
        encoding="utf-8",
    )
    assert GlobalizeCommandsMigration._is_generated_file(target) is False


def test_is_generated_file_rejects_marker_beyond_head_window(tmp_path: Path) -> None:
    body = "\n".join(["filler"] * 50) + f"\n{_VERSION_MARKER_PREFIX} 3.1.1a2 -->\n"
    target = tmp_path / "spec-kitty.deep.md"
    target.write_text(body, encoding="utf-8")
    assert GlobalizeCommandsMigration._is_generated_file(target) is False


def test_is_generated_file_handles_unreadable_path(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.md"
    assert GlobalizeCommandsMigration._is_generated_file(missing) is False


def test_apply_removes_new_format_files(
    tmp_path: Path,
    migration: GlobalizeCommandsMigration | SafeGlobalizeCommandsMigration,
) -> None:
    project = _make_project(tmp_path, {
        ".claude/commands/spec-kitty.implement.md": _NEW_FORMAT_BODY,
    })
    with patch.object(migration, "_global_runtime_present", return_value=True), \
         patch.object(migration, "_global_command_file_present", return_value=True):
        result = migration.apply(project)

    assert result.success
    assert result.manual_review_required is False
    assert not (project / ".claude/commands/spec-kitty.implement.md").exists()
