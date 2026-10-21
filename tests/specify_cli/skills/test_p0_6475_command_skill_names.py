"""Red-first P0 repro for #6475: command skills must carry spec-valid names.

A fresh ``spec-kitty init --ai codex`` must install every command skill in a
folder whose name (and frontmatter ``name``) is the Agent Skills form
``spec-kitty-<command>`` (lowercase alphanumerics and single hyphens, at most
64 characters). Literals are used on purpose: importing a naming authority
would make this guard pass vacuously once that authority exists.
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


@pytest.fixture()
def codex_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = (tmp_path / "home").resolve()
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    project = (tmp_path / "project").resolve()
    project.mkdir()
    with contextlib.chdir(project):
        result = CliRunner().invoke(root_app, ["init", "--ai", "codex", "--non-interactive"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    return project


def test_command_set_literal_matches_installer() -> None:
    assert len(CANONICAL_COMMANDS) == len(_COMMANDS) == 14


def test_init_installs_spec_valid_command_skill_names(codex_project: Path) -> None:
    skills = codex_project / _SKILLS_ROOT
    dotted = sorted(p.name for p in skills.glob("spec-kitty.*"))
    assert not dotted, f"dotted command skill folders are not spec-valid names: {dotted}"
    for command in _COMMANDS:
        expected = f"spec-kitty-{command}"
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
