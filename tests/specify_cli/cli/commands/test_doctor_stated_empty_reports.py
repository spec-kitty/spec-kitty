"""Doctor surface reports must be truthful when no agent surface is CLI-managed (#6493).

A project whose `.kittify/config.yaml` states `agents: {available: []}` has said that
Spec Kitty manages none of its agent surfaces (a harness plugin or another writer
supplies them, #6494). `doctor skills`, `doctor tool-surfaces` and
`doctor command-files` used to print `all ... healthy (0 ...)` over a surface set
they never examined. This module pins the honest line for both empty shapes and
positive controls proving the healthy line still appears when there is something to
check.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import specify_cli.cli.commands.doctor as doctor_mod
from specify_cli.cli.commands import _command_surface_doctor as doctor_surface
from specify_cli.cli.commands.doctor import app
from specify_cli.skills import command_installer

pytestmark = [pytest.mark.unit, pytest.mark.fast]

runner = CliRunner()

#: The vacuous-health summary lines this defect reported.
VACUOUS_HEALTHY_LINES = (
    "all manifest entries healthy",
    "all surfaces healthy",
    "all files healthy",
)


def _write_config(repo_root: Path, body: str) -> None:
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text(body, encoding="utf-8")


def _stated_empty(repo_root: Path) -> None:
    _write_config(repo_root, "agents:\n  available: []\n")


def _write_healthy_command_files(global_dir: Path) -> None:
    """Write the 15 command files `doctor command-files` calls healthy for claude.

    Prompt-driven files need more than 50 non-empty lines and CLI-driven shims fewer
    than 15, each carrying the current version marker in its head.
    """
    from importlib.metadata import version as pkg_version

    from specify_cli import __version__
    from specify_cli.shims.registry import CLI_DRIVEN_COMMANDS, PROMPT_DRIVEN_COMMANDS

    try:
        current = pkg_version("spec-kitty-cli")
    except Exception:  # pragma: no cover - fallback mirrors the production read
        current = __version__
    marker = f"<!-- spec-kitty-command-version: {current} -->"
    global_dir.mkdir(parents=True, exist_ok=True)
    for command in sorted(PROMPT_DRIVEN_COMMANDS):
        body = "\n".join(f"Step {index}: do the thing." for index in range(60))
        (global_dir / f"spec-kitty.{command}.md").write_text(f"{marker}\n{body}\n", encoding="utf-8")
    for command in sorted(CLI_DRIVEN_COMMANDS):
        (global_dir / f"spec-kitty.{command}.md").write_text(f"{marker}\nRun the CLI.\n", encoding="utf-8")


def _invoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: str, *args: str):
    """Run a real `doctor` subcommand shell against *tmp_path* as project root."""
    monkeypatch.setattr(doctor_mod, "locate_project_root", lambda: tmp_path)
    monkeypatch.setattr(doctor_surface, "locate_project_root", lambda: tmp_path)
    return runner.invoke(app, [command, *args])


def _flat(output: str) -> str:
    return " ".join(output.split())


@pytest.mark.parametrize("command", ["skills", "tool-surfaces", "command-files"])
def test_doctor_reports_no_cli_managed_surfaces_for_stated_empty_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: str) -> None:
    """FR-005: a stated-empty project is not reported as vacuously healthy."""
    _stated_empty(tmp_path)

    result = _invoke(tmp_path, monkeypatch, command)

    output = _flat(result.output)
    assert result.exit_code == 0, result.output
    assert "no cli-managed agents" in output.lower()
    for vacuous in VACUOUS_HEALTHY_LINES:
        assert vacuous not in output.lower()


def test_doctor_skills_still_reports_healthy_for_an_installed_agent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive control: with a real CLI-managed surface the healthy line is honest."""
    _write_config(tmp_path, "agents:\n  available:\n    - codex\n")
    command_installer.install(tmp_path, "codex")

    result = _invoke(tmp_path, monkeypatch, "skills")

    output = _flat(result.output)
    assert result.exit_code == 0, result.output
    assert "all manifest entries healthy" in output
    assert f"({len(command_installer.CANONICAL_COMMANDS)} file(s))" in output
    assert "no cli-managed agents" not in output.lower()


def test_doctor_tool_surfaces_audits_a_listed_agent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive control: a listed agent is audited for real, not short-circuited.

    The fixture only installs command skills, so the audit reports the remaining
    surface gaps (exit 1). The point is that the stated-empty branch does not claim
    the project, and the summary is not a vacuous "all surfaces healthy".
    """
    _write_config(tmp_path, "agents:\n  available:\n    - codex\n")
    command_installer.install(tmp_path, "codex")

    result = _invoke(tmp_path, monkeypatch, "tool-surfaces")

    output = _flat(result.output)
    assert result.exit_code == 1, result.output
    assert "no cli-managed agents" not in output.lower()
    assert "all surfaces healthy" not in output.lower()


def test_doctor_command_files_still_reports_healthy_for_a_listed_agent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive control: `all files healthy` still prints when files really are healthy."""
    _write_config(tmp_path, "agents:\n  available:\n    - claude\n")
    global_dir = tmp_path / "global-claude-commands"
    _write_healthy_command_files(global_dir)
    monkeypatch.setattr(
        "specify_cli.runtime.agent_commands.get_global_command_dir",
        lambda agent_key: global_dir,
    )

    result = _invoke(tmp_path, monkeypatch, "command-files")

    output = _flat(result.output)
    assert result.exit_code == 0, result.output
    assert "all files healthy" in output.lower()
    assert "no cli-managed agents" not in output.lower()


def test_doctor_skills_fix_writes_nothing_for_stated_empty_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-003: --fix in the stated-empty shape must not install a second surface."""
    _stated_empty(tmp_path)

    result = _invoke(tmp_path, monkeypatch, "skills", "--fix")

    assert result.exit_code == 0, result.output
    assert not (tmp_path / ".agents" / "skills").exists()
    assert not (tmp_path / ".kittify" / "skills-manifest.json").exists()


def test_doctor_skills_json_envelope_is_unchanged_for_stated_empty_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-002/SC-004: the machine-readable envelope keeps its exact key set."""
    _stated_empty(tmp_path)

    result = _invoke(tmp_path, monkeypatch, "skills", "--json")

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert set(data) == {
        "configured_agents",
        "manifest_agents",
        "entries",
        "canonical_commands",
        "drift",
        "gaps",
        "orphans",
        "stale",
        "unsafe",
        "legacy",
        "collisions",
        "uninstalled_agents",
        "vibe_config_missing",
        "repaired_agents",
        "repaired_paths",
        "pruned",
        "repaired_vibe_config",
        "repair_errors",
        "ok",
        "slash_commands",
        "pack_skills",
        "tool_folders",
    }
    assert data["configured_agents"] == []
    assert data["ok"] is True
