"""Activation-to-projection coherence on the real CLI (mission pack-skills-kind-01M43419, F5).

(a) absent ``activated_skills`` projects exactly the org-required skills;
(b) ``required_skills`` of several org packs union into the default-in-force set;
(c) a projection refusal after ``charter activate skill`` leaves config and disk
    coherent and tells the operator how to recover.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from charter.activation.doctrine_service_builder import build_activation_aware_doctrine_service
from specify_cli.cli.commands.charter import charter_app
from specify_cli.skills.manifest import load_manifest
from tests.charter import skill_pack_support as support

pytestmark = [pytest.mark.integration]

runner = CliRunner()
AGENTS = "agents:\n  available:\n    - claude\n"


@pytest.fixture(autouse=True)
def _fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))


def _skill_dirs(project: Path) -> set[str]:
    root = project / ".claude" / "skills"
    return {p.name for p in root.iterdir()} if root.is_dir() else set()


def _activate(project: Path, kind: str, skill_id: str, *extra: str) -> tuple[int, str]:
    result = runner.invoke(charter_app, ["activate", kind, skill_id, "--repo-root", str(project), "--no-compile", *extra], catch_exceptions=False)
    return result.exit_code, result.output


def _activated_skills(project: Path) -> list[str] | None:
    data = yaml.safe_load((project / ".kittify" / "config.yaml").read_text(encoding="utf-8")) or {}
    return data.get("activated_skills")


def test_required_skill_is_projected_and_unlisted_skill_is_not_when_key_is_absent(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    pack.mkdir()
    for skill_id in ("must-have", "optional-extra", "other"):
        support.write_skill(pack, skill_id)
    support.write_org_charter(pack, required_skills=["must-have"], namespace="acme")
    project = tmp_path / "project"
    project.mkdir()
    support.write_config(project, pack, extra=AGENTS)
    assert _activated_skills(project) is None  # the key is absent

    # Activating any *other* kind id is not needed: activating a skill re-projects
    # the whole in-force set, which for an absent key is exactly the required skills.
    code, output = _activate(project, "skill", "other")
    assert code == 0, output

    assert _skill_dirs(project) == {"acme-must-have", "acme-other"}
    assert (project / ".claude" / "skills" / "acme-must-have" / "SKILL.md").is_file()
    assert "acme-optional-extra" not in _skill_dirs(project)
    manifest = load_manifest(project, strict=True)
    assert manifest is not None
    assert {e.skill_name for e in manifest.entries if e.origin == "pack"} == {"acme-must-have", "acme-other"}


def test_required_skills_of_two_org_packs_union_into_default_in_force(tmp_path: Path) -> None:
    packs = []
    # sibling packs must not share a skill id; "shared" lives in pack one and is also required by pack two
    for name, skills, required in (("one", ["a", "shared", "unrequired-1"], ["a", "shared"]), ("two", ["b", "unrequired-2"], ["shared", "b"])):
        root = tmp_path / name
        root.mkdir()
        for skill_id in skills:
            support.write_skill(root, skill_id)
        support.write_org_charter(root, required_skills=required, namespace=name)
        packs.append(root)
    project = tmp_path / "project"
    project.mkdir()
    config = project / ".kittify" / "config.yaml"
    config.parent.mkdir()
    config.write_text(
        "mission_type_activations:\n  - software-dev\ncharter_packs:\n  org:\n    packs:\n"
        + "".join(f"      - name: {p.name}\n        local_path: {p}\n" for p in packs),
        encoding="utf-8",
    )

    assert set(build_activation_aware_doctrine_service(project).skills) == {"a", "b", "shared"}


def test_refused_projection_leaves_config_and_disk_coherent_with_a_recovery_message(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    pack.mkdir()
    support.write_skill(pack, "b-c")  # org namespace "a"      -> a-b-c
    support.write_org_charter(pack, namespace="a")
    project = tmp_path / "project"
    project.mkdir()
    support.write_config(project, pack, extra=AGENTS + "activated_skills: []\n", project_namespace="a-b")
    support.write_skill(project / ".kittify" / "doctrine", "c")  # project namespace "a-b" -> a-b-c (collision)

    code, output = _activate(project, "skill", "b-c")
    assert code == 0, output
    assert _skill_dirs(project) == {"a-b-c"}
    before = (project / ".claude" / "skills" / "a-b-c" / "SKILL.md").read_bytes()

    code, output = _activate(project, "skill", "c")

    assert code == 1
    assert "both render as" in output and "a-b-c" in output  # the cause
    assert "re-run this command" in output  # how to recover
    # Config records the activation (documented), disk is untouched: nothing half-written.
    assert _activated_skills(project) == ["b-c", "c"]
    assert _skill_dirs(project) == {"a-b-c"}
    assert (project / ".claude" / "skills" / "a-b-c" / "SKILL.md").read_bytes() == before
    manifest = load_manifest(project, strict=True)
    assert manifest is not None
    assert {e.skill_name for e in manifest.entries if e.origin == "pack"} == {"a-b-c"}

    # Recovery as the message says: fix the cause (a distinct project namespace) and re-run the same command.
    config = project / ".kittify" / "config.yaml"
    config.write_text(config.read_text(encoding="utf-8").replace("skill_namespace: a-b", "skill_namespace: mine"), encoding="utf-8")
    code, output = _activate(project, "skill", "c")
    assert code == 0, output
    assert _skill_dirs(project) == {"a-b-c", "mine-c"}
