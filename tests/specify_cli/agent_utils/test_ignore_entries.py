"""Agent-files ignore set and its .gitignore block (#6474)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.agent_utils.ignore_entries import (
    STATE_DIR_ENTRIES,
    agent_ignore_entries,
    ignored_agent_keys,
)
from specify_cli.agent_utils.ignore_entries import _SECRET_ENTRIES as SECRET_ENTRIES
from specify_cli.core.agent_config import AgentConfig, AgentConfigError, save_agent_config
from specify_cli.core.config import AI_CHOICES
from specify_cli.gitignore_manager import (
    AGENT_BLOCK_BEGIN,
    AGENT_BLOCK_END,
    GitignoreBlockError,
    GitignoreManager,
    refresh_agent_block,
    replace_agent_block,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast, pytest.mark.git_repo]

_SHARED_RESERVED = [".agents/skills/spec-kitty-*/", ".agents/skills/spec-kitty.*/", ".agents/skills/spec-kitty/", ".agents/skills/spk-*/"]


def _configure(project: Path, *agents: str) -> None:
    (project / ".kittify").mkdir(parents=True, exist_ok=True)
    save_agent_config(project, AgentConfig(available=list(agents)))


def _write_skills_manifest(project: Path, *entries: tuple[str, str, str]) -> None:
    """Write ``.kittify/skills-manifest.json`` from (agent, installed_path, origin) rows."""
    payload = {
        "version": 1,
        "created_at": "2026-10-21T00:00:00+00:00",
        "updated_at": "2026-10-21T00:00:00+00:00",
        "spec_kitty_version": "4.0.0rc8",
        "entries": [
            {
                "skill_name": path.split("/")[-2],
                "source_file": "SKILL.md",
                "installed_path": path,
                "installation_class": "native-root-required",
                "agent_key": agent,
                "content_hash": "sha256:" + "0" * 64,
                "installed_at": "2026-10-21T00:00:00+00:00",
                "origin": origin,
            }
            for agent, path, origin in entries
        ],
    }
    (project / ".kittify").mkdir(parents=True, exist_ok=True)
    (project / ".kittify" / "skills-manifest.json").write_text(json.dumps(payload), encoding="utf-8")


def _is_ignored(project: Path, path: str) -> bool:
    return subprocess.run(["git", "-C", str(project), "check-ignore", "-q", path], check=False).returncode == 0


class TestIgnoredAgentKeys:
    def test_configured_list_is_used(self, tmp_path: Path) -> None:
        _configure(tmp_path, "claude", "codex")

        assert ignored_agent_keys(tmp_path) == ("claude", "codex")

    def test_explicit_empty_list_means_no_agents(self, tmp_path: Path) -> None:
        _configure(tmp_path)

        assert ignored_agent_keys(tmp_path) == ()

    def test_missing_list_keeps_every_agent(self, tmp_path: Path) -> None:
        assert ignored_agent_keys(tmp_path) == tuple(AI_CHOICES)

    def test_unreadable_config_raises(self, tmp_path: Path) -> None:
        (tmp_path / ".kittify").mkdir()
        (tmp_path / ".kittify" / "config.yaml").write_text("agents: [unclosed\n", encoding="utf-8")

        with pytest.raises(AgentConfigError):
            ignored_agent_keys(tmp_path)


class TestAgentIgnoreEntries:
    def test_secrets_and_state_folders_come_first_even_without_agents(self, tmp_path: Path) -> None:
        """Spec Kitty's reserved names in the shared root stay ignored without agents too."""
        assert agent_ignore_entries(tmp_path, ()) == [*SECRET_ENTRIES, *STATE_DIR_ENTRIES, *_SHARED_RESERVED]

    def test_claude_gets_command_and_reserved_skill_patterns_only(self, tmp_path: Path) -> None:
        entries = agent_ignore_entries(tmp_path, ("claude",))

        assert ".claude/commands/spec-kitty.*" in entries
        assert ".claude/skills/spec-kitty-*/" in entries
        assert ".claude/skills/spk-*/" in entries
        assert ".claude/" not in entries
        assert ".claude/settings.json" not in entries
        assert not any(entry.startswith(".claude/rules") for entry in entries)

    def test_whole_session_files_are_ignored_but_append_mode_files_are_not(self, tmp_path: Path) -> None:
        entries = agent_ignore_entries(tmp_path, ("cursor", "kiro", "claude", "copilot", "gemini"))

        assert ".cursor/rules/spec-kitty.mdc" in entries
        assert ".kiro/steering/spec-kitty.md" in entries
        assert ".claude/CLAUDE.md" not in entries
        assert ".github/copilot-instructions.md" not in entries
        assert "GEMINI.md" not in entries

    def test_shared_root_agents_get_narrow_agents_skills_patterns(self, tmp_path: Path) -> None:
        entries = agent_ignore_entries(tmp_path, ("codex",))

        assert ".agents/skills/spec-kitty-*/" in entries
        assert ".agents/skills/" not in entries

    def test_unconfigured_agent_contributes_nothing(self, tmp_path: Path) -> None:
        entries = agent_ignore_entries(tmp_path, ("claude",))
        generated = set(entries) - set(SECRET_ENTRIES) - set(STATE_DIR_ENTRIES)

        assert not any(entry.startswith((".gemini/", ".kiro/", ".cursor/")) for entry in generated)

    def test_unknown_agent_key_is_ignored(self, tmp_path: Path) -> None:
        assert agent_ignore_entries(tmp_path, ("nope",)) == agent_ignore_entries(tmp_path, ())

    def test_manifest_pack_skill_folders_are_listed_for_configured_agents(self, tmp_path: Path) -> None:
        _write_skills_manifest(
            tmp_path,
            ("claude", ".claude/skills/acme-review/references/x.md", "pack"),
            ("claude", ".claude/skills/machine-local/SKILL.md", "builtin"),  # per-machine: not listed
            ("qwen", ".qwen/skills/acme-review/SKILL.md", "pack"),
            ("claude", ".claude/skills/SKILL.md", "pack"),  # not inside a skill folder
        )

        entries = agent_ignore_entries(tmp_path, ("claude",))

        assert ".claude/skills/acme-review/" in entries
        assert ".claude/skills/machine-local/" not in entries
        assert ".qwen/skills/acme-review/" not in entries
        assert ".claude/skills/SKILL.md/" not in entries

    def test_shipped_builtin_skills_outside_the_reserved_names_are_listed(self, tmp_path: Path) -> None:
        """From the shipped catalog, so every clone on one version writes the same block."""
        entries = agent_ignore_entries(tmp_path, ("claude",))

        assert ".claude/skills/adversarial-squad/" in entries
        assert not any(entry.startswith(".claude/skills/spk-") and entry != ".claude/skills/spk-*/" for entry in entries)

    def test_missing_builtin_catalog_contributes_nothing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import specify_cli.skills.catalog as catalog

        monkeypatch.setattr(catalog, "resolve_builtin_skill_catalog", lambda: None)

        assert ".claude/skills/adversarial-squad/" not in agent_ignore_entries(tmp_path, ("claude",))

    @pytest.mark.parametrize("secret", [".codex/auth.json", ".codex/sessions/", ".claude/settings.local.json", ".gemini/.env", ".qwen/.env", ".llxprt/.env"])
    def test_secrets_stay_ignored_without_any_agent(self, tmp_path: Path, secret: str) -> None:
        assert secret in agent_ignore_entries(tmp_path, ())

    def test_projected_agent_profiles_are_listed(self, tmp_path: Path) -> None:
        payload = {
            "schema_version": 1,
            "entries": [
                {
                    "profile_urn": "agent_profile:architect",
                    "source_layer": "built-in",
                    "tool_key": "claude",
                    "output_path": ".claude/agents/architect.md",
                    "format": "claude-agent",
                    "file_hash": "0" * 64,
                }
            ],
        }
        (tmp_path / ".kittify").mkdir()
        (tmp_path / ".kittify" / "agent_profiles_manifest.json").write_text(json.dumps(payload), encoding="utf-8")

        assert ".claude/agents/architect.md" in agent_ignore_entries(tmp_path, ("claude",))

    def test_unreadable_profile_manifest_contributes_nothing(self, tmp_path: Path) -> None:
        (tmp_path / ".kittify").mkdir()
        (tmp_path / ".kittify" / "agent_profiles_manifest.json").write_text("not json", encoding="utf-8")

        assert agent_ignore_entries(tmp_path, ()) == [*SECRET_ENTRIES, *STATE_DIR_ENTRIES, *_SHARED_RESERVED]

    def test_manifest_path_outside_every_skill_root_is_skipped(self, tmp_path: Path) -> None:
        _write_skills_manifest(tmp_path, ("claude", "elsewhere/acme/SKILL.md", "pack"))

        assert "elsewhere/acme/" not in agent_ignore_entries(tmp_path, ("claude",))

    def test_wrapper_only_agent_has_no_skill_patterns(self, tmp_path: Path) -> None:
        entries = agent_ignore_entries(tmp_path, ("q",))

        assert ".amazonq/prompts/spec-kitty.*" in entries
        assert not any("skills" in entry for entry in entries if entry not in _SHARED_RESERVED)

    def test_output_is_deterministic(self, tmp_path: Path) -> None:
        assert agent_ignore_entries(tmp_path, ("kiro", "claude")) == agent_ignore_entries(tmp_path, ("claude", "kiro"))


class TestReplaceAgentBlock:
    def test_appends_block_after_a_blank_line(self) -> None:
        updated = replace_agent_block("node_modules/\n", ["a/"])

        assert updated == f"node_modules/\n\n{AGENT_BLOCK_BEGIN}\na/\n{AGENT_BLOCK_END}\n"

    def test_creates_file_content_from_nothing(self) -> None:
        assert replace_agent_block(None, ["a/"]) == f"{AGENT_BLOCK_BEGIN}\na/\n{AGENT_BLOCK_END}\n"

    def test_replaces_block_in_place_and_keeps_user_lines(self) -> None:
        content = f"top\n{AGENT_BLOCK_BEGIN}\nold/\n{AGENT_BLOCK_END}\nbottom\n"

        assert replace_agent_block(content, ["new/"]) == f"top\n{AGENT_BLOCK_BEGIN}\nnew/\n{AGENT_BLOCK_END}\nbottom\n"

    def test_unchanged_block_returns_none(self) -> None:
        content = f"{AGENT_BLOCK_BEGIN}\na/\n{AGENT_BLOCK_END}\n"

        assert replace_agent_block(content, ["a/"]) is None

    def test_no_block_and_no_create_returns_none(self) -> None:
        assert replace_agent_block("x\n", ["a/"], create=False) is None

    def test_keeps_crlf(self) -> None:
        updated = replace_agent_block("x\r\n", ["a/"])

        assert updated is not None
        assert "\n" not in updated.replace("\r\n", "")

    @pytest.mark.parametrize(
        "content",
        [
            f"{AGENT_BLOCK_BEGIN}\na/\n",
            f"a/\n{AGENT_BLOCK_END}\n",
            f"{AGENT_BLOCK_END}\n{AGENT_BLOCK_BEGIN}\n",
            f"{AGENT_BLOCK_BEGIN}\n{AGENT_BLOCK_END}\n{AGENT_BLOCK_BEGIN}\n{AGENT_BLOCK_END}\n",
        ],
    )
    def test_damaged_block_refuses(self, content: str) -> None:
        with pytest.raises(GitignoreBlockError, match="damaged"):
            replace_agent_block(content, ["a/"])


class TestSyncAgentBlock:
    def test_protect_ignores_generated_files_but_not_team_files(self, tmp_path: Path) -> None:
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)

        result = GitignoreManager(tmp_path).protect_all_agents(["claude", "codex"])

        assert result.success, result.errors
        assert _is_ignored(tmp_path, ".claude/skills/spk-start-here/SKILL.md")
        assert _is_ignored(tmp_path, ".claude/commands/spec-kitty.plan.md")
        assert _is_ignored(tmp_path, ".agents/skills/spec-kitty-plan/SKILL.md")
        assert _is_ignored(tmp_path, ".codex/auth.json")
        assert _is_ignored(tmp_path, ".vibe/session.log")
        assert not _is_ignored(tmp_path, ".claude/settings.json")
        assert not _is_ignored(tmp_path, ".claude/rules/team.md")
        assert not _is_ignored(tmp_path, ".kiro/steering/team.md")
        assert not _is_ignored(tmp_path, ".agents/skills/team-skill/SKILL.md")
        assert not _is_ignored(tmp_path, ".codex/config.toml")
        assert ".claude/commands/spec-kitty.*" in result.entries_added

    def test_second_protect_reports_block_entries_as_skipped(self, tmp_path: Path) -> None:
        manager = GitignoreManager(tmp_path)
        manager.protect_all_agents(["claude"])

        result = manager.protect_all_agents(["claude"])

        assert result.success
        assert not result.modified
        assert not result.entries_added

    def test_sync_reads_config_when_no_agents_given(self, tmp_path: Path) -> None:
        _configure(tmp_path, "kiro")

        assert GitignoreManager(tmp_path).sync_agent_block()
        assert ".kiro/steering/spec-kitty.md" in (tmp_path / ".gitignore").read_text(encoding="utf-8")

    def test_sync_without_create_leaves_a_file_without_block_alone(self, tmp_path: Path) -> None:
        (tmp_path / ".gitignore").write_text("x\n", encoding="utf-8")

        assert not GitignoreManager(tmp_path).sync_agent_block(["claude"], create=False)
        assert (tmp_path / ".gitignore").read_text(encoding="utf-8") == "x\n"

    def test_protect_reports_damaged_block_as_error(self, tmp_path: Path) -> None:
        (tmp_path / ".gitignore").write_text(f"{AGENT_BLOCK_BEGIN}\n", encoding="utf-8")

        result = GitignoreManager(tmp_path).protect_all_agents(["claude"])

        assert not result.success
        assert any("damaged" in error for error in result.errors)


class TestRefreshAgentBlock:
    def test_refresh_follows_config(self, tmp_path: Path) -> None:
        _configure(tmp_path, "claude")
        GitignoreManager(tmp_path).sync_agent_block()
        _configure(tmp_path, "gemini")

        assert refresh_agent_block(tmp_path) is None
        text = (tmp_path / ".gitignore").read_text(encoding="utf-8")
        assert ".gemini/commands/spec-kitty.*" in text
        assert ".claude/commands/spec-kitty.*" not in text

    def test_refresh_reports_instead_of_raising(self, tmp_path: Path) -> None:
        (tmp_path / ".kittify").mkdir()
        (tmp_path / ".kittify" / "config.yaml").write_text("agents: [unclosed\n", encoding="utf-8")

        warning = refresh_agent_block(tmp_path)

        assert warning is not None
        assert "not refreshed" in warning

    def test_refresh_on_missing_project_is_a_no_op(self, tmp_path: Path) -> None:
        assert refresh_agent_block(tmp_path / "absent") is None

    def test_refresh_without_a_block_writes_nothing(self, tmp_path: Path) -> None:
        _configure(tmp_path, "claude")

        assert refresh_agent_block(tmp_path) is None
        assert not (tmp_path / ".gitignore").exists()
