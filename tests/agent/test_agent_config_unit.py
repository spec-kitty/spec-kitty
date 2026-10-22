"""Agent config parsing and validation tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.core.agent_config import (
    AgentConfig,
    AgentConfigError,
    get_auto_commit_default,
    load_agent_config,
    save_agent_config,
)


pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _write_config(tmp_path: Path, content: str) -> Path:
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    config_file = kittify / "config.yaml"
    config_file.write_text(content, encoding="utf-8")
    return config_file


class TestCorruptYaml:
    def test_corrupt_yaml_clear_error(self, tmp_path: Path) -> None:
        """Corrupt YAML should produce parse error, not silent fallback."""
        _write_config(tmp_path, "invalid: yaml: content: [")

        with pytest.raises(AgentConfigError) as exc_info:
            load_agent_config(tmp_path)

        assert "Invalid YAML" in str(exc_info.value)
        assert "config.yaml" in str(exc_info.value)


class TestNonMappingConfigShape:
    @pytest.mark.parametrize("content", ["[]", "false", "0", "''", "[claude]", "true", "42"])
    def test_non_mapping_root_is_not_a_default(self, tmp_path: Path, content: str) -> None:
        _write_config(tmp_path, content)

        with pytest.raises(AgentConfigError, match="expected a YAML mapping at the top level"):
            load_agent_config(tmp_path)

    @pytest.mark.parametrize("value", ["[]", "false", "0", "''", "[claude]", "true", "text"])
    @pytest.mark.parametrize(
        "prefix, section",
        [("", "agents"), ("", "tools"), ("agents: null\n", "tools"), ("agents: {}\n", "tools")],
    )
    def test_selected_section_requires_mapping(self, tmp_path: Path, value: str, prefix: str, section: str) -> None:
        config_file = _write_config(tmp_path, f"{prefix}{section}: {value}\n")

        with pytest.raises(AgentConfigError) as exc_info:
            load_agent_config(tmp_path)

        message = str(exc_info.value)
        assert str(config_file) in message
        assert section in message
        assert "mapping" in message

    def test_malformed_agents_cannot_fall_back_to_valid_tools(self, tmp_path: Path) -> None:
        _write_config(tmp_path, "agents: false\ntools:\n  available: [codex]\n")

        with pytest.raises(AgentConfigError):
            load_agent_config(tmp_path)

    def test_non_mapping_top_level_raises_agent_config_error(self, tmp_path: Path) -> None:
        """A ``config.yaml`` whose top-level YAML content is a bare scalar
        (valid YAML, not a mapping) previously crashed with a bare
        ``AttributeError: 'str' object has no attribute 'get'`` from the
        unguarded ``data.get("agents")`` call -- same defect class as ledger
        SK-16 (``charter status --json``'s leaked-exception bug). It must
        instead fail closed with a controlled ``AgentConfigError``, matching
        the sibling raise for a YAML parse error two lines above."""
        _write_config(tmp_path, "just-a-plain-string-not-a-mapping\n")

        with pytest.raises(AgentConfigError) as exc_info:
            load_agent_config(tmp_path)

        message = str(exc_info.value)
        assert "has no attribute" not in message, f"leaked a raw AttributeError instead of a controlled diagnostic: {message}"
        assert "config.yaml" in message


class TestUnknownAgentKey:
    def test_unknown_agent_reported(self, tmp_path: Path) -> None:
        """Unknown agent key should be explicitly reported."""
        _write_config(tmp_path, "agents:\n  available:\n    - unknown_agent_xyz\n")

        with pytest.raises(AgentConfigError) as exc_info:
            load_agent_config(tmp_path)

        message = str(exc_info.value)
        assert "unknown_agent_xyz" in message
        assert "Valid agents" in message


class TestSaveAgentConfig:
    def test_save_agent_config_no_selection_block(self, tmp_path: Path) -> None:
        """Persisted agent config must not include a selection block."""
        config = AgentConfig(
            available=["claude", "codex"],
        )

        save_agent_config(tmp_path, config)
        content = (tmp_path / ".kittify" / "config.yaml").read_text(encoding="utf-8")

        assert "selection:" not in content
        assert "preferred_implementer" not in content
        assert "preferred_reviewer" not in content


class TestAutoCommitLoading:
    def test_loads_top_level_auto_commit_without_agents_section(self, tmp_path: Path) -> None:
        """Top-level auto_commit should still work when agents config is absent."""
        _write_config(tmp_path, "auto_commit: false\n")

        config = load_agent_config(tmp_path)

        assert config.auto_commit is False
        assert config.available == []
        assert get_auto_commit_default(tmp_path) is False

    def test_agents_auto_commit_overrides_top_level(self, tmp_path: Path) -> None:
        """agents.auto_commit should take precedence over the legacy top-level key."""
        _write_config(
            tmp_path,
            "auto_commit: false\nagents:\n  available: []\n  auto_commit: true\n",
        )

        config = load_agent_config(tmp_path)

        assert config.auto_commit is True


class TestToolsKeyFallback:
    @pytest.mark.parametrize("content", [None, "", "null", "{}", "agents: null", "agents: {}", "tools: null", "tools: {}"])
    def test_empty_config_returns_defaults(self, tmp_path: Path, content: str | None) -> None:
        if content is not None:
            _write_config(tmp_path, content)

        assert load_agent_config(tmp_path) == AgentConfig()

    @pytest.mark.parametrize("agents", ["null", "{}"])
    def test_empty_agents_falls_back_to_tools(self, tmp_path: Path, agents: str) -> None:
        _write_config(
            tmp_path,
            f"agents: {agents}\ntools:\n  available: [codex]\n  auto_commit: false\n  lint_on_edit: true\n",
        )

        assert load_agent_config(tmp_path) == AgentConfig(available=["codex"], auto_commit=False, lint_on_edit=True)

    @pytest.mark.parametrize("tools", ["false", "[codex]", "{available: [codex]}"])
    def test_selected_agents_ignores_tools(self, tmp_path: Path, tools: str) -> None:
        _write_config(
            tmp_path,
            f"agents:\n  available: [claude]\n  auto_commit: false\n  lint_on_edit: true\ntools: {tools}\n",
        )

        assert load_agent_config(tmp_path) == AgentConfig(available=["claude"], auto_commit=False, lint_on_edit=True)

    @pytest.mark.parametrize("section", ["agents", "tools"])
    def test_empty_section_preserves_top_level_settings(self, tmp_path: Path, section: str) -> None:
        _write_config(tmp_path, f"{section}: {{}}\nauto_commit: false\nlint_on_edit: true\n")

        assert load_agent_config(tmp_path) == AgentConfig(auto_commit=False, lint_on_edit=True)

    def test_load_agent_config_tools_key(self, tmp_path: Path) -> None:
        """load_agent_config() reads from 'tools' key (post-m_2_0_1 migration)."""
        config_dir = tmp_path / ".kittify"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text("tools:\n  available:\n    - opencode\n  auto_commit: false\n")
        config = load_agent_config(tmp_path)
        assert config.available == ["opencode"]
        assert config.auto_commit is False

    def test_load_agent_config_agents_key_takes_precedence(self, tmp_path: Path) -> None:
        """'agents' key takes precedence over 'tools' key when both present."""
        _write_config(
            tmp_path,
            "agents:\n  available:\n    - claude\n  auto_commit: true\ntools:\n  available:\n    - opencode\n  auto_commit: false\n",
        )
        config = load_agent_config(tmp_path)
        assert config.available == ["claude"]
        assert config.auto_commit is True

    def test_load_agent_config_neither_key_returns_defaults(self, tmp_path: Path) -> None:
        """Config with neither 'agents' nor 'tools' key returns defaults."""
        _write_config(tmp_path, "vcs:\n  base_branch: main\n")
        config = load_agent_config(tmp_path)
        assert config.available == []
        assert config.auto_commit is True


class TestExplicitAgentList:
    """``explicit_agent_list`` separates ``available: []`` from a missing list (#6494)."""

    @pytest.mark.parametrize(
        "content",
        ["agents:\n  available: []\n", "agents:\n  available: [claude]\n", "tools:\n  available: []\n", "agents:\n  available: claude\n"],
    )
    def test_available_key_is_explicit(self, tmp_path: Path, content: str) -> None:
        _write_config(tmp_path, content)

        assert load_agent_config(tmp_path).explicit_agent_list is True

    @pytest.mark.parametrize("content", [None, "", "agents: {}", "agents:\n  auto_commit: false\n", "vcs:\n  base_branch: main\n"])
    def test_missing_available_key_is_not_explicit(self, tmp_path: Path, content: str | None) -> None:
        if content is not None:
            _write_config(tmp_path, content)

        assert load_agent_config(tmp_path).explicit_agent_list is False

    def test_flag_does_not_change_equality(self) -> None:
        assert AgentConfig(available=[], explicit_agent_list=True) == AgentConfig()

    def test_saved_config_round_trips_as_explicit(self, tmp_path: Path) -> None:
        (tmp_path / ".kittify").mkdir()
        save_agent_config(tmp_path, AgentConfig(available=[]))

        assert load_agent_config(tmp_path).explicit_agent_list is True


class TestConfigErrorRemedy:
    @pytest.mark.parametrize(
        "content",
        ["agents: [unclosed\n", "just a scalar\n", "agents: [claude]\n", "agents:\n  available: {a: 1}\n", "agents:\n  available: [nope]\n"],
    )
    def test_every_config_error_names_the_remedy(self, tmp_path: Path, content: str) -> None:
        _write_config(tmp_path, content)

        with pytest.raises(AgentConfigError, match=r"spec-kitty agent config list"):
            load_agent_config(tmp_path)


class TestSaveKeepsALegacyListAbsent:
    """#6494: changing a setting on a list-free config must not write ``available: []``."""

    def test_legacy_config_stays_list_free_after_save(self, tmp_path: Path) -> None:
        config_file = _write_config(tmp_path, "agents:\n  auto_commit: true\n")
        config = load_agent_config(tmp_path)
        config.auto_commit = False

        save_agent_config(tmp_path, config)

        assert "available" not in config_file.read_text(encoding="utf-8")
        reloaded = load_agent_config(tmp_path)
        assert reloaded.explicit_agent_list is False
        assert reloaded.auto_commit is False

    def test_a_config_built_in_code_states_its_list(self) -> None:
        assert AgentConfig().explicit_agent_list is True
