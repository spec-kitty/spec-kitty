"""Read-only catalog resolution and fail-closed migrations (WP04 review cycle 2).

``detect()``, assessment and ``--dry-run`` never write (no staging, no rmtree);
a broken pack skill is a recorded migration failure, not a traceback.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from specify_cli.skills.catalog import resolve_project_skill_catalog
from specify_cli.skills.installer import assess_skill_installation
from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot
from specify_cli.upgrade.migrations.m_2_0_11_install_skills import InstallSkillsMigration
from specify_cli.upgrade.migrations.m_2_1_1_repair_skill_pack import RepairSkillPackMigration
from specify_cli.upgrade.migrations.m_3_0_3_globalize_skill_pack import GlobalizeSkillPackMigration
from specify_cli.upgrade.migrations.m_3_2_0rc35_spk_skill_pack import SpkSkillPackMigration
from specify_cli.upgrade.runner import MigrationRunner
from tests.charter import skill_pack_support as support

pytestmark = [pytest.mark.integration]

STAGING = Path(".kittify/runtime/pack-skills")
CONFIG = "agents:\n  available:\n    - claude\n    - codex\nactivated_skills:\n  - deploy-helper\n"
DETECTING = (RepairSkillPackMigration, GlobalizeSkillPackMigration, SpkSkillPackMigration)


def _tree(root: Path) -> dict[str, object]:
    return {
        p.relative_to(root).as_posix(): ("link", os.readlink(p)) if p.is_symlink() else ("dir" if p.is_dir() else p.read_bytes()) for p in sorted(root.rglob("*"))
    }


@pytest.fixture(autouse=True)
def _home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "home").mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))


def _project(tmp_path: Path, *, namespace: str | None = "acme") -> Path:
    pack = tmp_path / "pack"
    pack.mkdir()
    support.write_skill(pack, "deploy-helper")
    support.write_org_charter(pack, namespace=namespace)
    root = tmp_path / "project"
    root.mkdir()
    support.write_config(root, pack, extra=CONFIG)
    return root


def test_read_only_resolution_never_writes_but_still_lists_the_pack_skill(tmp_path: Path) -> None:
    project = _project(tmp_path)
    before = _tree(project)

    registry = resolve_project_skill_catalog(project, stage=False)

    skill = registry.get_skill("acme-deploy-helper")
    assert skill is not None and skill.origin == "pack"
    assert project not in skill.skill_md.parents
    assert _tree(project) == before and not (project / STAGING).exists()


def test_read_only_resolution_leaves_an_existing_staging_root_untouched(tmp_path: Path) -> None:
    project = _project(tmp_path)
    stale = project / STAGING / "stale" / "SKILL.md"
    stale.parent.mkdir(parents=True)
    stale.write_text("old", encoding="utf-8")
    before = _tree(project)
    resolve_project_skill_catalog(project, stage=False)
    assert _tree(project) == before


def test_an_unused_empty_staging_root_is_not_removed(tmp_path: Path) -> None:
    project = tmp_path / "plain"
    (project / STAGING).mkdir(parents=True)
    support.write_config(project, None, extra="activated_skills: []\n")
    resolve_project_skill_catalog(project)
    assert (project / STAGING).is_dir()


@pytest.mark.parametrize("migration", DETECTING)
def test_detect_and_assessment_write_nothing(tmp_path: Path, migration: type) -> None:
    project = _project(tmp_path)
    before = _tree(project)

    migration().detect(project)
    registry = resolve_project_skill_catalog(project, stage=False)
    inputs = AssessmentInputs(OperationRoot("project", "project", project.absolute()), consent=ApplyConsent(automatic=True))
    assess_skill_installation(inputs, registry, ("claude", "codex"))

    assert _tree(project) == before


@pytest.mark.parametrize("migration", (*DETECTING, InstallSkillsMigration))
def test_dry_run_apply_writes_nothing(tmp_path: Path, migration: type) -> None:
    project = _project(tmp_path)
    before = _tree(project)
    result = migration().apply(project, dry_run=True)
    assert result.success, result.errors
    assert _tree(project) == before


@pytest.mark.parametrize("migration", DETECTING)
def test_a_broken_pack_makes_detect_true_and_apply_a_reported_error(tmp_path: Path, migration: type) -> None:
    project = _project(tmp_path, namespace=None)
    before = _tree(project)

    assert migration().detect(project) is True
    for dry_run in (True, False):
        result = migration().apply(project, dry_run=dry_run)
        assert not result.success and "Pack skills could not be resolved" in result.errors[0]
    assert _tree(project) == before


@pytest.mark.parametrize("dry_run", [True, False])
@pytest.mark.parametrize("migration", DETECTING)
def test_the_runner_records_a_failed_migration_for_a_broken_pack(tmp_path: Path, migration: type, dry_run: bool) -> None:
    project = _project(tmp_path, namespace=None)
    metadata = MagicMock()
    metadata.has_migration.return_value = False
    runner = MigrationRunner(project)
    with patch.object(MigrationRunner, "_record_migration_result"):
        result, status = runner._apply_migration(migration(), metadata, dry_run=dry_run)
    assert status == "failed" and not result.success
    assert any("Pack skills could not be resolved" in error for error in result.errors)
