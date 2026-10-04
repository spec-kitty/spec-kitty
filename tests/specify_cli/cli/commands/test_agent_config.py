"""WP07: ``agent config`` routes install state through the surface contract.

These tests pin the refactor that replaced ``agent config``'s ad-hoc per-agent
existence probes with a single :class:`SurfacePresenceIndex` pass over a
:class:`~specify_cli.tool_surface.model.SurfacePlan`. They assert two things:

1. The :class:`SurfacePresenceIndex` rollup is *equivalent* to the legacy
   directory-existence semantics (global commands, project skills, missing
   tools) so the frozen ``agent config`` interface is preserved.
2. ``agent config list``/``status`` actually consult the plan -- i.e. the
   builder is invoked and the rendered presence reflects the plan, not an
   independent recomputation.

Structure: AAA (Arrange / Act / Assert).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.config import app
from specify_cli.cli.commands.agent.surface_presence import (
    SurfacePresenceIndex,
    ToolSurfacePresence,
)
from specify_cli.core.agent_config import save_agent_config, load_agent_config
from specify_cli.core.config import AGENT_COMMAND_CONFIG

pytestmark = pytest.mark.fast

runner = CliRunner()

_SKILL_ONLY = "codex"
_GLOBAL_AGENT = "gemini"


def _fake_global_resolver(global_root: Path):
    """Resolver that mirrors ``get_global_command_dir`` under an isolated root."""

    def _resolve(agent_key: str) -> Path:
        if agent_key == "opencode":
            return global_root / ".config" / "opencode" / "commands"
        return global_root / str(AGENT_COMMAND_CONFIG[agent_key]["dir"])

    return _resolve


def _write_project(root: Path, available: list[str]) -> Path:
    kittify = root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    lines = ["agents:", "  available:"]
    lines.extend(f"    - {agent}" for agent in available)
    if not available:
        lines[-1] = "  available: []"
    (kittify / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return root


# ---------------------------------------------------------------------------
# SurfacePresenceIndex — rollup equivalence with legacy directory semantics
# ---------------------------------------------------------------------------


class TestSurfacePresenceIndex:
    def test_global_agent_present_when_global_dir_exists(self, tmp_path: Path) -> None:
        """Arrange: global command dir created; Act: build; Assert: exists True."""
        global_root = tmp_path / "home"
        resolver = _fake_global_resolver(global_root)
        resolver(_GLOBAL_AGENT).mkdir(parents=True)

        index = SurfacePresenceIndex.build(
            tmp_path, [_GLOBAL_AGENT], global_command_dir=resolver
        )

        assert index.exists(_GLOBAL_AGENT) is True

    def test_global_agent_absent_when_global_dir_missing(self, tmp_path: Path) -> None:
        """Arrange: no global dir; Act: build; Assert: exists False (isolated)."""
        resolver = _fake_global_resolver(tmp_path / "home")

        index = SurfacePresenceIndex.build(
            tmp_path, [_GLOBAL_AGENT], global_command_dir=resolver
        )

        assert index.exists(_GLOBAL_AGENT) is False

    def test_skill_only_agent_maps_to_project_skills_root(self, tmp_path: Path) -> None:
        """Arrange: .agents/skills created; Act: build; Assert: present + root."""
        (tmp_path / ".agents" / "skills").mkdir(parents=True)
        resolver = _fake_global_resolver(tmp_path / "home")

        index = SurfacePresenceIndex.build(
            tmp_path, [_SKILL_ONLY], global_command_dir=resolver
        )

        presence = index.presence(_SKILL_ONLY)
        assert presence.exists is True
        assert presence.roots == (tmp_path / ".agents" / "skills",)

    def test_skill_only_agent_has_no_global_command_root(self, tmp_path: Path) -> None:
        """A skill-only tool must not resolve a user-global command directory.

        The slash-command provider emits an ``<unsupported>`` sentinel for tools
        without a command-file adapter; that sentinel must contribute no root
        (and must not call the global resolver, which would ``KeyError``).
        """
        resolver = _fake_global_resolver(tmp_path / "home")

        index = SurfacePresenceIndex.build(
            tmp_path, [_SKILL_ONLY], global_command_dir=resolver
        )

        roots = index.presence(_SKILL_ONLY).roots
        assert roots == (tmp_path / ".agents" / "skills",)

    def test_unplanned_tool_reports_empty_presence(self, tmp_path: Path) -> None:
        """Arrange: tool not built; Act: query; Assert: empty roots, not present."""
        resolver = _fake_global_resolver(tmp_path / "home")
        index = SurfacePresenceIndex.build(
            tmp_path, [_GLOBAL_AGENT], global_command_dir=resolver
        )

        presence = index.presence("not-a-real-tool")
        assert presence.roots == ()
        assert presence.exists is False

    def test_build_deduplicates_tool_keys(self, tmp_path: Path) -> None:
        """Repeated tool keys collapse to a single rollup entry."""
        resolver = _fake_global_resolver(tmp_path / "home")
        index = SurfacePresenceIndex.build(
            tmp_path,
            [_GLOBAL_AGENT, _GLOBAL_AGENT],
            global_command_dir=resolver,
        )

        assert index.presence(_GLOBAL_AGENT).roots  # built exactly once, still present-capable

    def test_presence_exists_requires_real_directory(self, tmp_path: Path) -> None:
        """ToolSurfacePresence.exists is False when no root directory exists."""
        presence = ToolSurfacePresence(
            tool_key="x", roots=(tmp_path / "missing",)
        )
        assert presence.exists is False

    def test_default_resolver_is_used_when_not_injected(self, tmp_path: Path) -> None:
        """When no resolver is injected, the canonical resolver is consulted."""
        sentinel_dir = tmp_path / "injected"
        with patch(
            "specify_cli.cli.commands.agent.surface_presence.get_global_command_dir",
            return_value=sentinel_dir,
        ):
            index = SurfacePresenceIndex.build(tmp_path, [_GLOBAL_AGENT])

        assert index.presence(_GLOBAL_AGENT).roots == (sentinel_dir,)

    def test_corrupt_manifest_degrades_instead_of_crashing(self, tmp_path: Path) -> None:
        """A corrupt skills manifest must not crash read-only presence queries.

        The legacy ``agent config`` never loaded the manifest; the refactor must
        preserve that by degrading to static roots when the plan cannot expand.
        """
        kittify = tmp_path / ".kittify"
        kittify.mkdir(parents=True)
        # ``{}`` has no schema_version -> manifest_store.load raises ManifestError.
        (kittify / "command-skills-manifest.json").write_text("{}", encoding="utf-8")
        global_root = tmp_path / "home"
        resolver = _fake_global_resolver(global_root)
        resolver(_GLOBAL_AGENT).mkdir(parents=True)
        (tmp_path / ".agents" / "skills").mkdir(parents=True)

        index = SurfacePresenceIndex.build(
            tmp_path,
            [_GLOBAL_AGENT, _SKILL_ONLY],
            global_command_dir=resolver,
        )

        # Global agent still resolves via the resolver; skill-only via .agents/skills.
        assert index.exists(_GLOBAL_AGENT) is True
        assert index.exists(_SKILL_ONLY) is True

    def test_static_fallback_skill_only_has_no_global_root(
        self, tmp_path: Path
    ) -> None:
        """Degraded path keeps the same applicability as the providers."""
        kittify = tmp_path / ".kittify"
        kittify.mkdir(parents=True)
        (kittify / "command-skills-manifest.json").write_text("{}", encoding="utf-8")
        resolver = _fake_global_resolver(tmp_path / "home")

        index = SurfacePresenceIndex.build(
            tmp_path, [_SKILL_ONLY], global_command_dir=resolver
        )

        # No global command directory root for a skill-only tool, even degraded.
        assert index.presence(_SKILL_ONLY).roots == (
            tmp_path / ".agents" / "skills",
        )


# ---------------------------------------------------------------------------
# CLI integration — list/status consult the plan, not an independent probe
# ---------------------------------------------------------------------------


class TestListConsultsSurfacePlan:
    def test_list_invokes_presence_index_builder(self, tmp_path: Path) -> None:
        """``list`` must build a SurfacePresenceIndex (route through the plan)."""
        _write_project(tmp_path, [_GLOBAL_AGENT])

        real_build = SurfacePresenceIndex.build
        with patch(
            "specify_cli.cli.commands.agent.config.find_repo_root",
            return_value=tmp_path,
        ), patch(
            "specify_cli.cli.commands.agent.config.SurfacePresenceIndex.build",
            side_effect=real_build,
        ) as spy:
            result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert spy.called

    def test_list_marks_present_when_plan_root_exists(self, tmp_path: Path) -> None:
        """A configured global agent renders ✓ when its plan root exists."""
        global_root = tmp_path / "home"
        resolver = _fake_global_resolver(global_root)
        resolver(_GLOBAL_AGENT).mkdir(parents=True)
        _write_project(tmp_path, [_GLOBAL_AGENT])

        with patch(
            "specify_cli.cli.commands.agent.config.find_repo_root",
            return_value=tmp_path,
        ), patch(
            "specify_cli.cli.commands.agent.config.get_global_command_dir",
            side_effect=resolver,
        ):
            result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "✓" in result.output
        assert _GLOBAL_AGENT in result.output

    def test_list_marks_missing_when_plan_root_absent(self, tmp_path: Path) -> None:
        """A configured global agent renders ⚠ when its plan root is absent."""
        resolver = _fake_global_resolver(tmp_path / "home")
        _write_project(tmp_path, [_GLOBAL_AGENT])

        with patch(
            "specify_cli.cli.commands.agent.config.find_repo_root",
            return_value=tmp_path,
        ), patch(
            "specify_cli.cli.commands.agent.config.get_global_command_dir",
            side_effect=resolver,
        ):
            result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "⚠" in result.output


class TestStatusConsultsSurfacePlan:
    def test_status_present_reflects_plan_root(self, tmp_path: Path) -> None:
        """``status`` reports OK for a configured tool whose plan root exists."""
        global_root = tmp_path / "home"
        resolver = _fake_global_resolver(global_root)
        resolver(_GLOBAL_AGENT).mkdir(parents=True)
        _write_project(tmp_path, [_GLOBAL_AGENT])

        with patch(
            "specify_cli.cli.commands.agent.config.find_repo_root",
            return_value=tmp_path,
        ), patch(
            "specify_cli.cli.commands.agent.config.get_global_command_dir",
            side_effect=resolver,
        ):
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "Agent Status" in result.output

    def test_status_builds_presence_index(self, tmp_path: Path) -> None:
        """``status`` must build a SurfacePresenceIndex for the known tools."""
        _write_project(tmp_path, [_GLOBAL_AGENT])
        real_build = SurfacePresenceIndex.build
        with patch(
            "specify_cli.cli.commands.agent.config.find_repo_root",
            return_value=tmp_path,
        ), patch(
            "specify_cli.cli.commands.agent.config.SurfacePresenceIndex.build",
            side_effect=real_build,
        ) as spy:
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert spy.called


class TestConfiguredClaudeSessionPresence:
    """FR-004: a configured ``claude`` resolves its session-presence surface
    through the registry path (``GLOBAL_COMMAND_AGENTS`` + SurfacePresenceIndex),
    not an ad-hoc per-agent probe.

    ``claude`` is a global-command agent: its managed surface is the global
    command directory. These tests exercise the real registry path end to end
    (no stub) for both the present and absent surface states.
    """

    _CLAUDE = "claude"

    def test_claude_present_resolves_via_registry_path(self, tmp_path: Path) -> None:
        """claude configured + global surface present → ✓ via the presence index."""
        global_root = tmp_path / "home"
        resolver = _fake_global_resolver(global_root)
        # Materialize the claude session-presence (global command) surface.
        resolver(self._CLAUDE).mkdir(parents=True)
        _write_project(tmp_path, [self._CLAUDE])

        real_build = SurfacePresenceIndex.build
        with patch(
            "specify_cli.cli.commands.agent.config.find_repo_root",
            return_value=tmp_path,
        ), patch(
            "specify_cli.cli.commands.agent.config.get_global_command_dir",
            side_effect=resolver,
        ), patch(
            "specify_cli.cli.commands.agent.config.SurfacePresenceIndex.build",
            side_effect=real_build,
        ) as spy:
            result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        # The registry path was taken (presence index built), and claude shows ✓.
        assert spy.called
        assert self._CLAUDE in result.output
        assert "✓" in result.output
        assert "(global)" in result.output

    def test_claude_absent_resolves_via_registry_path(self, tmp_path: Path) -> None:
        """claude configured + global surface absent → ⚠ via the presence index."""
        resolver = _fake_global_resolver(tmp_path / "home")
        _write_project(tmp_path, [self._CLAUDE])

        real_build = SurfacePresenceIndex.build
        with patch(
            "specify_cli.cli.commands.agent.config.find_repo_root",
            return_value=tmp_path,
        ), patch(
            "specify_cli.cli.commands.agent.config.get_global_command_dir",
            side_effect=resolver,
        ), patch(
            "specify_cli.cli.commands.agent.config.SurfacePresenceIndex.build",
            side_effect=real_build,
        ) as spy:
            result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert spy.called
        assert self._CLAUDE in result.output
        assert "⚠" in result.output


def test_config_roundtrip_helpers_still_exposed(tmp_path: Path) -> None:
    """Sanity: the preserved config I/O helpers remain importable + functional."""
    _write_project(tmp_path, [_GLOBAL_AGENT])
    config = load_agent_config(tmp_path)
    assert _GLOBAL_AGENT in config.available
    save_agent_config(tmp_path, config)
    assert (tmp_path / ".kittify" / "config.yaml").exists()


def test_sync_create_missing_restores_vibe_pointer_without_touching_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An installed vibe agent with a lost ``.vibe/config.toml`` pointer is recovered.

    ``sync --create-missing`` skips re-installing an already-installed skill
    agent so it never rewrites the pinned command-skills manifest (#2691), but
    the gitignored vibe ``skill_paths`` pointer is not part of that manifest and
    must still be restored. A repeat run reports no change.
    """
    import json
    import subprocess

    from specify_cli.skills import command_installer
    from specify_cli.skills.vibe_config import skill_path_configured

    # Arrange: an initialized vibe clone whose skills are present, pointer absent.
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    _write_project(tmp_path, ["vibe"])
    command_installer.install(tmp_path, "vibe")
    manifest = tmp_path / ".kittify" / "command-skills-manifest.json"
    manifest_before = manifest.read_bytes()
    assert not skill_path_configured(tmp_path)
    monkeypatch.chdir(tmp_path)

    # Act: the recovery command init recommends.
    first = runner.invoke(app, ["sync", "--create-missing", "--keep-orphaned", "--json"])
    second = runner.invoke(app, ["sync", "--create-missing", "--keep-orphaned", "--json"])

    # Assert: pointer restored once, manifest bytes untouched, repeat is a no-op.
    assert first.exit_code == 0, first.output
    assert skill_path_configured(tmp_path)
    assert manifest.read_bytes() == manifest_before
    first_summary = json.loads(first.output[first.output.index("{") :])
    assert first_summary == {"changes_made": True, "tracked_mutations": []}

    assert second.exit_code == 0, second.output
    second_summary = json.loads(second.output[second.output.index("{") :])
    assert second_summary == {"changes_made": False, "tracked_mutations": []}
    assert manifest.read_bytes() == manifest_before


def test_sync_create_missing_reports_unrestorable_vibe_pointer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A corrupt ``.vibe/config.toml`` is reported as an error and left untouched.

    The pointer restore never overwrites an operator file it cannot parse; the
    sync surfaces the failure (exit 1) and the pinned manifest is unchanged.
    """
    import subprocess

    from specify_cli.skills import command_installer

    # Arrange: an installed vibe clone whose pointer file is unparseable TOML.
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    _write_project(tmp_path, ["vibe"])
    command_installer.install(tmp_path, "vibe")
    manifest = tmp_path / ".kittify" / "command-skills-manifest.json"
    manifest_before = manifest.read_bytes()
    pointer = tmp_path / ".vibe" / "config.toml"
    pointer.parent.mkdir()
    corrupt = b"skill_paths = [unterminated\n"
    pointer.write_bytes(corrupt)
    monkeypatch.chdir(tmp_path)

    # Act
    result = runner.invoke(app, ["sync", "--create-missing", "--keep-orphaned"])

    # Assert: error surfaced, operator file preserved byte-for-byte, manifest pinned.
    assert result.exit_code == 1, result.output
    output = " ".join(result.output.split())
    assert "Failed to restore .vibe/config.toml skill_paths pointer" in output
    assert pointer.read_bytes() == corrupt
    assert manifest.read_bytes() == manifest_before
