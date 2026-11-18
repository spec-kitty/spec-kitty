"""A project's manifest-owned ``spk-gate-merge`` copy is removed on reinstall (#7702).

The skill was renamed to ``spk-gate-consolidate``. ``spec-kitty upgrade`` reassesses
project skills with ``retire=True``, so a manifest-owned entry that the catalog no
longer carries is pruned. This pins that path for a project that already holds the
old skill.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from specify_cli.skills.installer import install_all_skills
from specify_cli.skills.manifest import load_manifest, save_manifest
from specify_cli.skills.registry import SkillRegistry
from specify_cli.skills.retired import RETIRED_CANONICAL_SKILL_NAMES

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _write_skill(root: Path, name: str) -> None:
    skill_md = root / name / "SKILL.md"
    skill_md.parent.mkdir(parents=True, exist_ok=True)
    skill_md.write_text(f"---\nname: {name}\ndescription: {name}\n---\n# {name}\n", encoding="utf-8")


def test_manifest_owned_spk_gate_merge_is_removed_on_reinstall(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert "spk-gate-merge" in RETIRED_CANONICAL_SKILL_NAMES
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    source = tmp_path / "skills"
    project = tmp_path / "project"
    project.mkdir()
    _write_skill(source, "spk-gate-merge")
    _write_skill(source, "spk-gate-consolidate")

    save_manifest(install_all_skills(project, ["claude"], SkillRegistry(source)), project)
    old = project / ".claude" / "skills" / "spk-gate-merge" / "SKILL.md"
    assert old.is_file()
    manifest = load_manifest(project)
    assert manifest is not None
    assert any("spk-gate-merge" in entry.installed_path for entry in manifest.entries)

    shutil.rmtree(source / "spk-gate-merge")
    save_manifest(install_all_skills(project, ["claude"], SkillRegistry(source)), project)

    assert not old.exists()
    assert not (project / ".claude" / "skills" / "spk-gate-merge").exists()
    assert (project / ".claude" / "skills" / "spk-gate-consolidate" / "SKILL.md").is_file()
    manifest = load_manifest(project)
    assert manifest is not None
    assert not any("spk-gate-merge" in entry.installed_path for entry in manifest.entries)
