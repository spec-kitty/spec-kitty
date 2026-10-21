"""Regression guard for #6470 (formerly its red-first P0 repro): Antigravity gets command skills, not workflows.

``spec-kitty init --ai antigravity`` must install the command skills under
``.agents/skills/spec-kitty-<command>/`` and must not write
``spec-kitty.*.md`` workflow files into the global ``~/.agent/workflows``
(nor, as a secondary guard, the project ``.agent/workflows``).
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli import app as root_app

pytestmark = [pytest.mark.integration, pytest.mark.slow]

_COMMANDS = (
    "accept",
    "analyze",
    "charter",
    "consolidate",
    "implement",
    "plan",
    "research",
    "review",
    "specify",
    "status",
    "tasks",
    "tasks-finalize",
    "tasks-outline",
    "tasks-packages",
)
_SKILLS_ROOT = ".agents/skills"
_WORKFLOWS = ".agent/workflows"


@pytest.fixture()
def antigravity_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    home = (tmp_path / "home").resolve()
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    project = (tmp_path / "project").resolve()
    project.mkdir()
    with contextlib.chdir(project):
        result = CliRunner().invoke(root_app, ["init", "--ai", "antigravity", "--non-interactive"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    return project, home


def test_antigravity_installs_command_skills(antigravity_project: tuple[Path, Path]) -> None:
    project, _home = antigravity_project
    for command in _COMMANDS:
        skill_md = project / _SKILLS_ROOT / f"spec-kitty-{command}" / "SKILL.md"
        assert skill_md.is_file(), f"missing {skill_md.relative_to(project)}"
    manifest = json.loads((project / ".kittify" / "command-skills-manifest.json").read_text(encoding="utf-8"))
    agents = {agent for entry in manifest["entries"] for agent in entry["agents"]}
    assert "antigravity" in agents, f"no manifest entry lists antigravity: {sorted(agents)}"


def test_antigravity_writes_no_global_workflow_files(antigravity_project: tuple[Path, Path]) -> None:
    _project, home = antigravity_project
    leaked = sorted(p.name for p in (home / _WORKFLOWS).glob("spec-kitty.*.md"))
    assert not leaked, f"global ~/{_WORKFLOWS} still receives workflow files: {leaked}"


def test_antigravity_writes_no_project_workflow_files(antigravity_project: tuple[Path, Path]) -> None:
    project, _home = antigravity_project
    leaked = sorted(p.name for p in (project / _WORKFLOWS).glob("spec-kitty.*"))
    assert not leaked, f"project {_WORKFLOWS} still receives workflow files: {leaked}"
