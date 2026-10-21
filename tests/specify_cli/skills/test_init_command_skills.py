"""End-to-end ``spec-kitty init`` guards for command skills (#6475, #6470).

A fresh ``init`` must install every command skill in a folder whose name (and
frontmatter ``name``) is the Agent Skills form ``spec-kitty-<command>``, and
Antigravity must receive them as skills, never as ``.agent/workflows`` files.
The installer-level contract lives in ``test_command_installer.py`` and the name
grammar in ``test_command_skill_names.py``; these tests pin what only a real
``init`` shows: the folders on disk, the frontmatter, the manifest and the
absence of workflow files.
"""

from __future__ import annotations

import contextlib
import json
import re
from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from specify_cli import app as root_app
from specify_cli.skills.command_installer import CANONICAL_COMMANDS

pytestmark = [pytest.mark.integration, pytest.mark.slow]

_SKILLS_ROOT = ".agents/skills"
_WORKFLOWS = ".agent/workflows"
_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_ALLOWED_KEYS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
_MAX_NAME = 64
_MAX_DESCRIPTION = 1024


def _frontmatter(skill_md: Path) -> dict[str, Any]:
    text = skill_md.read_text(encoding="utf-8")
    parts = text.split("---\n", 2)
    assert len(parts) == 3 and parts[0] == "", f"{skill_md} has no leading frontmatter block"
    data = YAML(typ="safe").load(parts[1])
    assert isinstance(data, dict), f"{skill_md} frontmatter is not a mapping"
    return data


def _init(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, agent: str) -> tuple[Path, Path]:
    home = (tmp_path / "home").resolve()
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    project = (tmp_path / "project").resolve()
    project.mkdir()
    with contextlib.chdir(project):
        result = CliRunner().invoke(root_app, ["init", "--ai", agent, "--non-interactive"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    return project, home


@pytest.fixture()
def codex_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    return _init(tmp_path, monkeypatch, "codex")[0]


@pytest.fixture()
def antigravity_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    return _init(tmp_path, monkeypatch, "antigravity")


def test_init_installs_spec_valid_command_skill_names(codex_project: Path) -> None:
    skills = codex_project / _SKILLS_ROOT
    dotted = sorted(p.name for p in skills.glob("spec-kitty.*"))
    assert not dotted, f"dotted command skill folders are not spec-valid names: {dotted}"
    # Literal prefix on purpose: deriving the folder from the naming authority would pass vacuously.
    expected_folders = {f"spec-kitty-{command}" for command in CANONICAL_COMMANDS}
    assert expected_folders <= {p.name for p in skills.iterdir() if p.is_dir()}
    for expected in sorted(expected_folders):
        skill_md = skills / expected / "SKILL.md"
        assert skill_md.is_file(), f"missing {skill_md.relative_to(codex_project)}"
        meta = _frontmatter(skill_md)
        assert meta.get("name") == expected
        assert _NAME_RE.fullmatch(expected) and len(expected) <= _MAX_NAME
        assert set(meta) <= _ALLOWED_KEYS, f"unexpected frontmatter keys: {sorted(set(meta) - _ALLOWED_KEYS)}"
        assert len(str(meta.get("description", ""))) <= _MAX_DESCRIPTION


def test_manifest_entries_use_hyphenated_skill_paths(codex_project: Path) -> None:
    manifest = json.loads((codex_project / ".kittify" / "command-skills-manifest.json").read_text(encoding="utf-8"))
    paths = [entry["path"] for entry in manifest["entries"]]
    assert paths, "manifest has no entries"
    bad = [p for p in paths if not p.startswith(f"{_SKILLS_ROOT}/spec-kitty-")]
    assert not bad, f"manifest entries outside the spec-valid folder form: {bad}"


def test_antigravity_installs_command_skills_not_workflows(antigravity_project: tuple[Path, Path]) -> None:
    project, home = antigravity_project
    for command in CANONICAL_COMMANDS:
        skill_md = project / _SKILLS_ROOT / f"spec-kitty-{command}" / "SKILL.md"
        assert skill_md.is_file(), f"missing {skill_md.relative_to(project)}"
    manifest = json.loads((project / ".kittify" / "command-skills-manifest.json").read_text(encoding="utf-8"))
    agents = {agent for entry in manifest["entries"] for agent in entry["agents"]}
    assert "antigravity" in agents, f"no manifest entry lists antigravity: {sorted(agents)}"
    global_leak = sorted(p.name for p in (home / _WORKFLOWS).glob("spec-kitty.*.md"))
    assert not global_leak, f"global ~/{_WORKFLOWS} still receives workflow files: {global_leak}"
    project_leak = sorted(p.name for p in (project / _WORKFLOWS).glob("spec-kitty.*"))
    assert not project_leak, f"project {_WORKFLOWS} still receives workflow files: {project_leak}"
