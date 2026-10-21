"""Integration tests for agent config add/remove vibe (T027).

Tests:
- agent config add vibe: config updated, skill-only registration.
- agent config remove vibe (vibe-only): manifest empty, files gone.
- agent config remove vibe (codex+vibe): manifest has codex-only entries.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.config import app
from specify_cli.core.agent_config import save_agent_config, load_agent_config, AgentConfig
from specify_cli.skills import command_installer, manifest_store

pytestmark = [pytest.mark.integration, pytest.mark.non_sandbox]  # non_sandbox: subprocess CLI invocation
runner = CliRunner()

def _write_config(tmp_path: Path, agents: list[str]) -> None:
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    config = AgentConfig(available=agents)
    save_agent_config(tmp_path, config)


def _expected_command_skill_paths() -> set[str]:
    return {
        f".agents/skills/spec-kitty-{command}/SKILL.md"
        for command in command_installer.CANONICAL_COMMANDS
    }


# ---------------------------------------------------------------------------
# T027-A: agent config add vibe
# ---------------------------------------------------------------------------


def test_add_vibe_updates_config(tmp_path: Path) -> None:
    """agent config add vibe must add vibe to agents.available in config.yaml."""
    _write_config(tmp_path, [])

    with patch("specify_cli.cli.commands.agent.config.find_repo_root", return_value=tmp_path):
        result = runner.invoke(app, ["add", "vibe"])

    assert result.exit_code == 0, result.output

    config = load_agent_config(tmp_path)
    assert "vibe" in config.available

    vibe_config = tmp_path / ".vibe" / "config.toml"
    assert vibe_config.is_file(), ".vibe/config.toml was not created"
    with vibe_config.open("rb") as fh:
        vibe_data = tomllib.load(fh)
    assert vibe_data["skill_paths"] == [".agents/skills"]


def test_add_vibe_prints_registered(tmp_path: Path) -> None:
    """agent config add vibe must print a registration confirmation."""
    _write_config(tmp_path, [])

    with patch("specify_cli.cli.commands.agent.config.find_repo_root", return_value=tmp_path):
        result = runner.invoke(app, ["add", "vibe"])

    assert result.exit_code == 0
    output = result.output
    # Should mention vibe registered or added
    assert "vibe" in output.lower() or "Registered" in output


def test_add_vibe_idempotent(tmp_path: Path) -> None:
    """Adding vibe twice must leave config with exactly one vibe entry."""
    _write_config(tmp_path, [])

    with patch("specify_cli.cli.commands.agent.config.find_repo_root", return_value=tmp_path):
        runner.invoke(app, ["add", "vibe"])
        result2 = runner.invoke(app, ["add", "vibe"])

    assert result2.exit_code == 0
    config = load_agent_config(tmp_path)
    assert config.available.count("vibe") == 1


# ---------------------------------------------------------------------------
# T027-B: agent config remove vibe (vibe-only)
# ---------------------------------------------------------------------------


def test_remove_vibe_only(tmp_path: Path) -> None:
    """remove vibe from vibe-only project: manifest empty, skill dirs gone."""
    _write_config(tmp_path, ["vibe"])

    # Match init/config-add behavior for command-skill agents: command skills
    # are rendered into the shared .agents/skills/ root.
    expected_paths = _expected_command_skill_paths()
    report = command_installer.install(tmp_path, "vibe")
    assert set(report.added) == expected_paths

    # Verify files exist before removal
    manifest = manifest_store.load(tmp_path)
    assert {entry.path for entry in manifest.entries} == expected_paths
    for entry in manifest.entries:
        assert (tmp_path / entry.path).exists()

    with patch("specify_cli.cli.commands.agent.config.find_repo_root", return_value=tmp_path):
        result = runner.invoke(app, ["remove", "vibe"])

    assert result.exit_code == 0, result.output

    # Manifest must be empty
    manifest_after = manifest_store.load(tmp_path)
    assert len(manifest_after.entries) == 0, (
        f"Expected empty manifest after remove vibe; got {len(manifest_after.entries)} entries"
    )

    # Skill dirs must be gone
    skills_root = tmp_path / ".agents" / "skills"
    if skills_root.exists():
        remaining = [p for p in skills_root.glob("spec-kitty-*/SKILL.md") if p.parent.name.removeprefix("spec-kitty-") in command_installer.CANONICAL_COMMANDS]
        assert len(remaining) == 0, f"Unexpected SKILL.md files remain: {remaining}"

    # Config must not contain vibe
    config = load_agent_config(tmp_path)
    assert "vibe" not in config.available


# ---------------------------------------------------------------------------
# T027-C: agent config remove vibe with codex also configured
# ---------------------------------------------------------------------------


def test_remove_vibe_leaves_codex_entries(tmp_path: Path) -> None:
    """remove vibe when codex+vibe configured: codex manifest entries remain."""
    _write_config(tmp_path, ["codex", "vibe"])

    # Install codex first, then vibe (shared root — same files, two agents)
    command_installer.install(tmp_path, "codex")
    command_installer.install(tmp_path, "vibe")

    # After both installs, all entries should have agents == ("codex", "vibe")
    expected_paths = _expected_command_skill_paths()
    manifest_before = manifest_store.load(tmp_path)
    assert {entry.path for entry in manifest_before.entries} == expected_paths
    for entry in manifest_before.entries:
        assert "codex" in entry.agents
        assert "vibe" in entry.agents

    # Snapshot bytes before remove
    snapshots: dict[str, bytes] = {}
    for entry in manifest_before.entries:
        abs_path = tmp_path / entry.path
        snapshots[entry.path] = abs_path.read_bytes()

    with patch("specify_cli.cli.commands.agent.config.find_repo_root", return_value=tmp_path):
        result = runner.invoke(app, ["remove", "vibe"])

    assert result.exit_code == 0, result.output

    # Manifest must still have all command-skill entries — codex still owns them
    manifest_after = manifest_store.load(tmp_path)
    assert {entry.path for entry in manifest_after.entries} == expected_paths, (
        "Expected codex-owned command-skill entries to remain; got "
        f"{[entry.path for entry in manifest_after.entries]}"
    )

    # All entries must be codex-only now
    for entry in manifest_after.entries:
        assert entry.agents == ("codex",), (
            f"Entry {entry.path} has agents={entry.agents}, expected ('codex',)"
        )

    # Files must be byte-identical (no rewrite)
    for entry in manifest_after.entries:
        abs_path = tmp_path / entry.path
        assert abs_path.exists(), f"File missing: {entry.path}"
        assert abs_path.read_bytes() == snapshots[entry.path], (
            f"File content changed after removing vibe: {entry.path}"
        )

    # Config must not contain vibe but must still contain codex
    config = load_agent_config(tmp_path)
    assert "vibe" not in config.available
    assert "codex" in config.available


# ---------------------------------------------------------------------------
# #6475 review: removing one agent from a legacy (dotted) layout
# ---------------------------------------------------------------------------


def test_remove_vibe_from_legacy_layout_keeps_codex_skills_and_warns(tmp_path: Path) -> None:
    """FR-020: ``agent config remove vibe`` never strips codex's dotted skills; an edited
    skill whose last owner was vibe is kept with the "no longer managed" warning."""
    from specify_cli.skills.command_skill_names import legacy_command_skill_rel_path

    _write_config(tmp_path, ["codex", "vibe"])
    entries = []
    for command in command_installer.CANONICAL_COMMANDS:
        rel = legacy_command_skill_rel_path(command)
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"old {command}\n", encoding="utf-8")
        agents = ("vibe",) if command == "plan" else ("codex", "vibe")
        entries.append(manifest_store.ManifestEntry(rel, manifest_store.fingerprint_file(path), agents, "2026-01-01T00:00:00+00:00", "3.2.0"))
    manifest_store.save(tmp_path, manifest_store.SkillsManifest(entries=entries))
    edited = tmp_path / legacy_command_skill_rel_path("plan")
    edited.write_text("my edits\n", encoding="utf-8")

    with patch("specify_cli.cli.commands.agent.config.find_repo_root", return_value=tmp_path):
        result = runner.invoke(app, ["remove", "vibe"])

    assert result.exit_code == 0, result.output
    after = {entry.path: entry.agents for entry in manifest_store.load(tmp_path).entries}
    codex_paths = {legacy_command_skill_rel_path(c) for c in command_installer.CANONICAL_COMMANDS if c != "plan"}
    assert after == dict.fromkeys(codex_paths, ("codex",))
    assert all((tmp_path / path).is_file() for path in codex_paths)
    assert edited.read_text(encoding="utf-8") == "my edits\n"
    text = " ".join(result.output.split())
    assert "no longer managed" in text and legacy_command_skill_rel_path("plan") in text
