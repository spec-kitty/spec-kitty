"""Narrowing the whole-folder agent ignores Spec Kitty wrote (#6474).

- Only lines in a Spec Kitty-written run are removed (after the auto-managed
  marker or the 0.4.8 header); the operator's own rules are kept and named.
- The agent-files block is written for the configured agents only.
- Files the removed lines hid are reported, never added anywhere.
- detect()/apply() are idempotent; dry-run writes nothing; unsafe inputs fail.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from kernel.clock import now_utc

from specify_cli.agent_utils.ignore_entries import STATE_DIR_ENTRIES
from specify_cli.agent_utils.ignore_entries import _SECRET_ENTRIES as SECRET_ENTRIES
from specify_cli.core.agent_config import AgentConfig, save_agent_config
from specify_cli.gitignore_manager import AGENT_BLOCK_BEGIN, AGENT_BLOCK_END, SPEC_KITTY_GITIGNORE_MARKER
from specify_cli.upgrade.metadata import ProjectMetadata
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.migrations.m_4_0_0rc8_narrow_agent_gitignore import (
    LEGACY_AGENT_ENTRIES,
    NarrowAgentGitignoreMigration,
    _visibility_warning,
)
from specify_cli.upgrade.registry import MigrationRegistry
from specify_cli.upgrade.runner import MigrationRunner

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_LEGACY_HEADER = "# AI Agent directories (added by Spec Kitty CLI)\n# These contain auth tokens and should NEVER be committed\n"


def _project(tmp_path: Path, gitignore: str, *agents: str) -> Path:
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    (tmp_path / ".kittify").mkdir()
    save_agent_config(tmp_path, AgentConfig(available=list(agents)))
    (tmp_path / ".gitignore").write_text(gitignore, encoding="utf-8")
    return tmp_path


def _touch(project: Path, *paths: str) -> None:
    for rel in paths:
        target = project / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x\n", encoding="utf-8")


def _is_ignored(project: Path, path: str) -> bool:
    return subprocess.run(["git", "-C", str(project), "check-ignore", "-q", path], check=False).returncode == 0


def _lines(project: Path) -> list[str]:
    return (project / ".gitignore").read_text(encoding="utf-8").splitlines()


def test_marker_run_lines_are_replaced_by_the_configured_block(tmp_path: Path) -> None:
    project = _project(tmp_path, f"node_modules/\n\n{SPEC_KITTY_GITIGNORE_MARKER}\n.claude/\n.codex/\n.gemini/\n.kittify/runtime/\n.agents/skills/\n", "claude")
    _touch(project, ".claude/settings.json", ".claude/skills/spk-x/SKILL.md")
    migration = NarrowAgentGitignoreMigration()

    assert migration.detect(project)
    result = migration.apply(project)

    assert result.success, result.errors
    lines = _lines(project)
    for entry in (".claude/", ".codex/", ".gemini/", ".agents/skills/"):
        assert entry not in lines
    assert ".kittify/runtime/" in lines
    assert "node_modules/" in lines
    assert lines.count(AGENT_BLOCK_BEGIN) == 1
    assert ".claude/commands/spec-kitty.*" in lines
    assert not any(line.startswith(".gemini/") and line != ".gemini/.env" for line in lines)
    assert not _is_ignored(project, ".claude/settings.json")
    assert _is_ignored(project, ".claude/skills/spk-x/SKILL.md")
    assert _is_ignored(project, ".codex/auth.json")
    assert not migration.detect(project)


def test_legacy_0_4_8_header_and_its_entries_are_removed(tmp_path: Path) -> None:
    project = _project(tmp_path, f"{_LEGACY_HEADER}.claude/\n.roo/\n.github/copilot/\n", "claude")

    result = NarrowAgentGitignoreMigration().apply(project)

    assert result.success
    text = (project / ".gitignore").read_text(encoding="utf-8")
    assert "AI Agent directories" not in text
    assert "auth tokens" not in text
    assert ".roo/" not in text.splitlines()
    assert ".github/copilot/" in text.splitlines()  # re-emitted inside the block


def test_operator_rules_outside_a_spec_kitty_run_are_kept_and_named(tmp_path: Path) -> None:
    gitignore = f".kiro\n/.claude/\n\n{SPEC_KITTY_GITIGNORE_MARKER}\n.codex/\nmy-own/\n.gemini/\n"
    project = _project(tmp_path, gitignore, "claude")

    result = NarrowAgentGitignoreMigration().apply(project)

    assert result.success
    lines = _lines(project)
    assert ".kiro" in lines
    assert "/.claude/" in lines
    assert ".gemini/" in lines  # after an operator line: no longer provably ours
    assert ".codex/" not in lines
    assert result.manual_review_required
    named = " ".join(result.warnings)
    assert "'.kiro'" in named
    assert "'/.claude/'" in named
    assert "'.gemini/'" in named


def test_newly_visible_files_are_reported_not_added(tmp_path: Path) -> None:
    project = _project(tmp_path, f"{SPEC_KITTY_GITIGNORE_MARKER}\n.claude/\n.agents/skills/\n", "claude")
    _touch(project, ".claude/settings.json", ".claude/rules/team.md", ".agents/skills/team/SKILL.md")

    result = NarrowAgentGitignoreMigration().apply(project)

    visibility = [warning for warning in result.warnings if warning.startswith("Git now shows")]
    assert len(visibility) == 1
    for path in (".claude/settings.json", ".claude/rules/team.md", ".agents/skills/team/SKILL.md"):
        assert path in visibility[0]
    staged = subprocess.run(["git", "-C", str(project), "diff", "--cached", "--name-only"], capture_output=True, text=True, check=True).stdout
    assert staged == ""


def test_explicit_empty_agent_list_keeps_only_secrets_and_state(tmp_path: Path) -> None:
    project = _project(tmp_path, f"{SPEC_KITTY_GITIGNORE_MARKER}\n.claude/\n.vibe/\n")

    assert NarrowAgentGitignoreMigration().apply(project).success

    lines = _lines(project)
    block = lines[lines.index(AGENT_BLOCK_BEGIN) + 1 : lines.index(AGENT_BLOCK_END)]
    shared_reserved = [f".agents/skills/{name}" for name in ("spec-kitty-*/", "spec-kitty.*/", "spec-kitty/", "spk-*/")]
    assert block == [*SECRET_ENTRIES, *STATE_DIR_ENTRIES, *shared_reserved]
    assert ".vibe/" not in lines[: lines.index(AGENT_BLOCK_BEGIN)]


def test_dry_run_reports_without_writing(tmp_path: Path) -> None:
    gitignore = f"{SPEC_KITTY_GITIGNORE_MARKER}\n.claude/\n"
    project = _project(tmp_path, gitignore, "claude")

    result = NarrowAgentGitignoreMigration().apply(project, dry_run=True)

    assert result.success
    assert any(change.startswith("Would remove") for change in result.changes_made)
    assert any(change.startswith("Would write") for change in result.changes_made)
    assert (project / ".gitignore").read_text(encoding="utf-8") == gitignore


def test_second_apply_changes_nothing(tmp_path: Path) -> None:
    project = _project(tmp_path, f"{SPEC_KITTY_GITIGNORE_MARKER}\n.claude/\n", "claude")
    migration = NarrowAgentGitignoreMigration()
    migration.apply(project)
    before = (project / ".gitignore").read_text(encoding="utf-8")

    result = migration.apply(project)

    assert result.changes_made == ["Agent ignore rules already narrow"]
    assert (project / ".gitignore").read_text(encoding="utf-8") == before


def test_missing_gitignore_gets_the_block(tmp_path: Path) -> None:
    project = _project(tmp_path, "", "claude")
    (project / ".gitignore").unlink()
    migration = NarrowAgentGitignoreMigration()

    assert migration.detect(project)
    assert migration.apply(project).success
    assert _lines(project)[0] == AGENT_BLOCK_BEGIN


def test_crlf_file_keeps_crlf(tmp_path: Path) -> None:
    project = _project(tmp_path, f"x\r\n{SPEC_KITTY_GITIGNORE_MARKER}\r\n.claude/\r\n", "claude")

    assert NarrowAgentGitignoreMigration().apply(project).success

    raw = (project / ".gitignore").read_bytes()
    assert b"\r\n" in raw
    assert b"\n" not in raw.replace(b"\r\n", b"")


@pytest.mark.parametrize(
    ("setup", "message"),
    [
        ("config", "config"),
        ("block", "damaged"),
        ("symlink", "symlink"),
    ],
)
def test_unsafe_inputs_fail_closed(tmp_path: Path, setup: str, message: str) -> None:
    project = _project(tmp_path, f"{SPEC_KITTY_GITIGNORE_MARKER}\n.claude/\n", "claude")
    if setup == "config":
        (project / ".kittify" / "config.yaml").write_text("agents: [unclosed\n", encoding="utf-8")
    elif setup == "block":
        (project / ".gitignore").write_text(f"{AGENT_BLOCK_BEGIN}\n", encoding="utf-8")
    else:
        (project / "real-ignore").write_text(".claude/\n", encoding="utf-8")
        (project / ".gitignore").unlink()
        (project / ".gitignore").symlink_to(project / "real-ignore")
    migration = NarrowAgentGitignoreMigration()

    assert migration.detect(project)
    ok, reason = migration.can_apply(project)
    result = migration.apply(project)

    assert not ok
    assert message in reason.lower()
    assert not result.success
    assert message in " ".join(result.errors).lower()


def test_can_apply_refuses_a_missing_project(tmp_path: Path) -> None:
    ok, reason = NarrowAgentGitignoreMigration().can_apply(tmp_path / "absent")

    assert not ok
    assert "does not exist" in reason


def test_visibility_warning_caps_the_list() -> None:
    warning = _visibility_warning([f"f{i}" for i in range(25)])

    assert warning is not None
    assert "25 file(s)" in warning
    assert "and 5 more" in warning
    assert _visibility_warning([]) is None


def test_legacy_entry_list_is_frozen() -> None:
    """The provenance set never follows the live registry (ADR 2026-07-07-1)."""
    assert ".claude/" in LEGACY_AGENT_ENTRIES
    assert ".roo/" in LEGACY_AGENT_ENTRIES
    assert ".agents/skills/" in LEGACY_AGENT_ENTRIES
    assert len(LEGACY_AGENT_ENTRIES) == 22


def test_runner_narrows_an_rc7_project_end_to_end(tmp_path: Path) -> None:
    project = _project(tmp_path, f"{SPEC_KITTY_GITIGNORE_MARKER}\n.claude/\n.kiro/\n", "claude")
    ProjectMetadata(version="4.0.0rc7", initialized_at=now_utc()).save(project / ".kittify")
    _touch(project, ".claude/settings.json", ".kiro/steering/team.md")
    assert _is_ignored(project, ".claude/settings.json")

    MigrationRegistry.clear()
    auto_discover_migrations()
    result = MigrationRunner(project).upgrade("4.0.0rc8", include_worktrees=False)

    assert NarrowAgentGitignoreMigration.migration_id in result.migrations_applied, result.errors
    assert not _is_ignored(project, ".claude/settings.json")
    assert not _is_ignored(project, ".kiro/steering/team.md")


def test_backfill_rows_appended_after_operator_lines_are_still_spec_kittys(tmp_path: Path) -> None:
    """3.2.5 / 3.2.6rc3 appended at EOF once the marker existed, after the operator's own lines."""
    gitignore = f"{SPEC_KITTY_GITIGNORE_MARKER}\n.claude/\n\n# mine\nbuild/\n.agents/skills/\n.cursor/commands/\n.cursor/skills/\n"
    project = _project(tmp_path, gitignore, "codex")

    result = NarrowAgentGitignoreMigration().apply(project)

    lines = _lines(project)
    for entry in (".agents/skills/", ".cursor/commands/", ".cursor/skills/"):
        assert entry not in lines
    assert "build/" in lines
    assert not any("Kept your own" in warning for warning in result.warnings)


def test_operator_cursor_row_after_the_managed_run_is_kept(tmp_path: Path) -> None:
    """Only 3.2.6rc3's neighbour proof makes a blanket .cursor/ row Spec Kitty's."""
    project = _project(tmp_path, f"node_modules/\n{SPEC_KITTY_GITIGNORE_MARKER}\n.claude/\n.kittify/runtime/\n.cursor/\n", "claude")
    _touch(project, ".cursor/local-secrets.json")

    result = NarrowAgentGitignoreMigration().apply(project)

    assert ".cursor/" in _lines(project)
    assert _is_ignored(project, ".cursor/local-secrets.json")
    assert any("'.cursor/'" in warning for warning in result.warnings)


def test_historical_cursor_row_between_its_neighbours_is_removed(tmp_path: Path) -> None:
    project = _project(tmp_path, f"{SPEC_KITTY_GITIGNORE_MARKER}\n.gemini/\n.cursor/\n.qwen/\n", "claude")

    NarrowAgentGitignoreMigration().apply(project)

    assert ".cursor/" not in _lines(project)


def test_marker_with_nothing_left_under_it_is_removed(tmp_path: Path) -> None:
    project = _project(tmp_path, f"x\n{SPEC_KITTY_GITIGNORE_MARKER}\n.claude/\n.codex/\n", "claude")

    NarrowAgentGitignoreMigration().apply(project)

    assert SPEC_KITTY_GITIGNORE_MARKER not in _lines(project)


def test_operator_rule_for_a_still_ignored_state_folder_draws_no_warning(tmp_path: Path) -> None:
    project = _project(tmp_path, ".pi/\nx\n", "claude")

    result = NarrowAgentGitignoreMigration().apply(project)

    assert ".pi/" in _lines(project)
    assert not any("Kept your own" in warning for warning in result.warnings)
