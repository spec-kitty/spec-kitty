"""User-global Claude commands and skills follow ``$CLAUDE_CONFIG_DIR`` (#7701).

Claude Code reads its user configuration from ``$CLAUDE_CONFIG_DIR`` when set,
so the user-global ``commands/`` and ``skills/`` roots resolve there. Copies an
earlier release wrote under ``~/.claude`` are left in place, never migrated.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.runtime import agent_skills
from specify_cli.runtime.agent_commands import ensure_global_agent_commands, get_global_command_dir
from specify_cli.runtime.doctor import resolve_command_file_dirs
from specify_cli.skills.paths import (
    CLAUDE_CONFIG_DIR_ENV,
    get_claude_user_config_root,
    get_primary_global_skill_root,
    get_project_skill_root_for_global_root,
)

pytestmark = [pytest.mark.fast]


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home / ".kittify"))
    monkeypatch.delenv(CLAUDE_CONFIG_DIR_ENV, raising=False)
    return home


@pytest.fixture
def claude_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, home: Path) -> Path:
    root = tmp_path / "claude-alt"
    monkeypatch.setenv(CLAUDE_CONFIG_DIR_ENV, str(root))
    return root


def test_default_claude_roots_stay_under_home(home: Path) -> None:
    assert get_claude_user_config_root() == home / ".claude"
    assert get_global_command_dir("claude") == home / ".claude" / "commands"
    assert get_primary_global_skill_root("claude") == home / ".claude" / "skills"


def test_empty_claude_config_dir_is_unset(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(CLAUDE_CONFIG_DIR_ENV, "")
    assert get_global_command_dir("claude") == home / ".claude" / "commands"


def test_claude_config_dir_expands_user(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(CLAUDE_CONFIG_DIR_ENV, "~/.claude-t3")
    assert get_global_command_dir("claude") == home / ".claude-t3" / "commands"
    assert get_primary_global_skill_root("claude") == home / ".claude-t3" / "skills"


def test_claude_config_dir_redirects_claude_only(home: Path, claude_root: Path) -> None:
    assert get_global_command_dir("claude") == claude_root / "commands"
    assert get_primary_global_skill_root("claude") == claude_root / "skills"
    assert get_global_command_dir("gemini") == home / ".gemini" / "commands"
    assert get_primary_global_skill_root("codex") == home / ".agents" / "skills"


def test_redirected_claude_skill_root_keeps_native_projection(claude_root: Path) -> None:
    root = claude_root / "skills"
    assert get_project_skill_root_for_global_root(root) == ".claude/skills"
    assert agent_skills._is_shared_global_root(root) is False
    assert get_project_skill_root_for_global_root(claude_root / "elsewhere") is None


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def test_switching_to_claude_config_dir_leaves_owned_home_copies_untouched(home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Copies the sync owns under ``~/.claude`` (inventory-recorded) are neither migrated nor retired."""
    agent_skills.ensure_global_agent_skills()
    ensure_global_agent_commands(agent_keys=["claude"])
    legacy_root = home / ".claude"
    assert (legacy_root / "skills" / "spk-gate-consolidate" / "SKILL.md").is_file(), "control: the sync owns ~/.claude"
    assert (legacy_root / "commands" / "spec-kitty.plan.md").is_file(), "control: the sync owns ~/.claude"
    before = _tree_bytes(legacy_root)

    claude_root = tmp_path / "claude-alt"
    monkeypatch.setenv(CLAUDE_CONFIG_DIR_ENV, str(claude_root))
    agent_skills.ensure_global_agent_skills()
    ensure_global_agent_commands(agent_keys=["claude"])

    assert (claude_root / "skills" / "spk-gate-consolidate" / "SKILL.md").is_file()
    assert (claude_root / "commands" / "spec-kitty.plan.md").is_file()
    assert _tree_bytes(legacy_root) == before, "the ~/.claude tree is not migrated, retired or rewritten"


def test_skill_identity_tracks_the_claude_root(home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.skills.installer import _agent_config_identity

    default = _agent_config_identity()
    monkeypatch.setenv(CLAUDE_CONFIG_DIR_ENV, str(tmp_path / "claude-alt"))
    assert _agent_config_identity() != default, "a root change must invalidate the skill assessment"


def _claude_project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    (project / ".kittify").mkdir(parents=True)
    (project / ".kittify" / "config.yaml").write_text("project:\n  uuid: test-uuid-7701\nagents:\n  available:\n    - claude\n", encoding="utf-8")
    return project


def test_doctor_resolves_claude_command_dir(tmp_path: Path, claude_root: Path) -> None:
    assert resolve_command_file_dirs(_claude_project(tmp_path)) == {"claude": claude_root / "commands"}


def test_doctor_command_files_prints_resolved_dir(tmp_path: Path, claude_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.cli.commands.doctor import app

    project = _claude_project(tmp_path)
    monkeypatch.chdir(project)
    result = CliRunner().invoke(app, ["command-files"], env={"COLUMNS": "40"})

    assert f"claude: {claude_root / 'commands'}" in result.output, result.output
