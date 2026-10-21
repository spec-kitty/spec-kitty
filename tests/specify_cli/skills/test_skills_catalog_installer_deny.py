"""The skills catalog and installer never list or install a denied pack skill (WP05: M6, FR-006).

``specify_cli.skills.catalog`` and ``installer`` consume the prepared
projection from ``charter.activation.skill_preparation``, which is
deny-netted; no production change is needed here, so this pins the consumer
side. Ledger-seeded.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.skills.catalog import resolve_project_skill_catalog
from specify_cli.skills.installer import project_pack_skills
from specify_cli.skills.manifest import ORIGIN_PACK
from specify_cli.skills.registry import SkillRegistry
from tests._factories.activation_ledger import seed_activation_ledger
from tests.charter import skill_pack_support as support

pytestmark = [pytest.mark.integration]

_DENIED = "deploy-helper"
_KEPT = "lint-helper"


@pytest.fixture(autouse=True)
def _fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))


def _shipped(tmp_path: Path) -> SkillRegistry:
    root = tmp_path / "builtin-skills" / "spk-one"
    root.mkdir(parents=True)
    (root / "SKILL.md").write_text("---\nname: spk-one\ndescription: built-in\n---\n# spk-one\n", encoding="utf-8")
    return SkillRegistry(root.parent)


def _project(tmp_path: Path) -> Path:
    pack = tmp_path / "pack"
    pack.mkdir()
    for skill_id in (_DENIED, _KEPT):
        support.write_skill(pack, skill_id)
    support.write_org_charter(pack, namespace="acme")
    root = tmp_path / "project"
    config = root / ".kittify" / "config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(
        f"agents:\n  available:\n    - claude\ncharter_packs:\n  org:\n    packs:\n      - name: acme\n        local_path: {pack}\n",
        encoding="utf-8",
    )
    seed_activation_ledger(root, mission_type_activations=["software-dev"], activated_skills=[_DENIED, _KEPT])
    return root


def _pack_names(root: Path, shipped: SkillRegistry) -> set[str]:
    catalog = resolve_project_skill_catalog(root, builtin=shipped, stage=False)
    return {skill.name for skill in catalog.discover_skills() if skill.origin == ORIGIN_PACK}


def test_the_catalog_never_lists_a_denied_skill(tmp_path: Path) -> None:
    root, shipped = _project(tmp_path), _shipped(tmp_path)
    assert _pack_names(root, shipped) == {f"acme-{_DENIED}", f"acme-{_KEPT}"}  # positive control

    seed_activation_ledger(root, deactivated_skills=[_DENIED])
    assert _pack_names(root, shipped) == {f"acme-{_KEPT}"}


def test_the_installer_never_installs_a_denied_skill(tmp_path: Path) -> None:
    root, shipped = _project(tmp_path), _shipped(tmp_path)
    seed_activation_ledger(root, deactivated_skills=[_DENIED])

    project_pack_skills(root, registry=resolve_project_skill_catalog(root, builtin=shipped))

    skills_root = root / ".claude" / "skills"
    assert (skills_root / f"acme-{_KEPT}" / "SKILL.md").is_file()  # positive control: the kept skill installs
    assert not (skills_root / f"acme-{_DENIED}").exists()


def test_reactivating_restores_the_installed_skill(tmp_path: Path) -> None:
    root, shipped = _project(tmp_path), _shipped(tmp_path)
    seed_activation_ledger(root, deactivated_skills=[_DENIED])
    project_pack_skills(root, registry=resolve_project_skill_catalog(root, builtin=shipped))
    assert not (root / ".claude" / "skills" / f"acme-{_DENIED}").exists()

    seed_activation_ledger(root, deactivated_skills=[])
    project_pack_skills(root, registry=resolve_project_skill_catalog(root, builtin=shipped))
    assert (root / ".claude" / "skills" / f"acme-{_DENIED}" / "SKILL.md").is_file()
