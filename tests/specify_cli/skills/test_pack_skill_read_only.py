"""Read-only catalog resolution and fail-closed migrations (WP04 review cycle 2).

``detect()``, assessment and ``--dry-run`` never write (no staging, no rmtree);
a broken pack skill is a recorded migration failure, not a traceback.
"""

from __future__ import annotations

import os
from collections.abc import Callable
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
from specify_cli.upgrade.assessment import prepare_upgrade_repairs
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


def _outcome(root: Path, migration: type) -> tuple[bool, bool, int]:
    """What a project's own migration run reports: detect, apply success, number of changes."""
    detected = migration().detect(root)
    result = migration().apply(root, dry_run=False)
    return detected, result.success, len(result.changes_made)


@pytest.mark.parametrize("migration", DETECTING)
def test_a_broken_org_drg_changes_nothing_for_a_project_that_uses_no_pack_skill(tmp_path: Path, migration: type) -> None:
    """A pack that ships zero skills may have any DRG; no skill path may depend on its health."""
    plain = tmp_path / "plain"
    plain.mkdir()
    support.write_config(plain, None, extra="agents:\n  available:\n    - claude\n    - codex\n")
    pack = tmp_path / "pack"
    pack.mkdir()
    support.write_org_charter(pack)
    (pack / "broken.graph.yaml").write_text("nodes: [unclosed\n", encoding="utf-8")
    broken = tmp_path / "broken"
    broken.mkdir()
    support.write_config(broken, pack, extra="agents:\n  available:\n    - claude\n    - codex\n")

    assert _outcome(broken, migration) == _outcome(plain, migration)
    consent = ApplyConsent(automatic=True)
    assert prepare_upgrade_repairs(broken, consent=consent).complete == prepare_upgrade_repairs(plain, consent=consent).complete


def _no_namespace(root: Path, pack: Path) -> None:
    support.write_org_charter(pack, namespace=None)


def _sibling_duplicate_id(root: Path, pack: Path) -> None:
    other = root.parent / "other-pack"
    other.mkdir()
    support.write_skill(other, "deploy-helper")
    support.write_org_charter(other, namespace="other")
    config = root / ".kittify" / "config.yaml"
    entry = f"        local_path: {pack}\n"
    config.write_text(config.read_text(encoding="utf-8").replace(entry, f"{entry}      - name: other\n        local_path: {other}\n"), encoding="utf-8")


def _broken_graph(root: Path, pack: Path) -> None:
    (pack / "broken.graph.yaml").write_text("nodes: [unclosed\n", encoding="utf-8")


def _non_utf8_body(root: Path, pack: Path) -> None:
    (pack / "skills" / "deploy-helper.skill.md").write_bytes(b"\xff\xfe not utf-8")


def _non_list_activation(root: Path, pack: Path) -> None:
    config = root / ".kittify" / "config.yaml"
    config.write_text(config.read_text(encoding="utf-8").replace("activated_skills:\n  - deploy-helper\n", "activated_skills: deploy-helper\n"), encoding="utf-8")


@pytest.mark.parametrize("cause", [_no_namespace, _sibling_duplicate_id, _broken_graph, _non_utf8_body, _non_list_activation])
@pytest.mark.parametrize("migration", DETECTING)
def test_a_broken_pack_makes_detect_true_and_apply_a_reported_error(tmp_path: Path, migration: type, cause: Callable[[Path, Path], None]) -> None:
    project = _project(tmp_path)
    cause(project, tmp_path / "pack")
    before = _tree(project)

    assert migration().detect(project) is True
    for dry_run in (True, False):
        result = migration().apply(project, dry_run=dry_run)
        assert not result.success and "Pack skills could not be resolved" in result.errors[0]
    assert _tree(project) == before


def test_the_runner_records_a_failed_migration_for_a_broken_pack(tmp_path: Path) -> None:
    """The runner treats the migrations' reported failure uniformly; one migration stands for all three."""
    project = _project(tmp_path, namespace=None)
    metadata = MagicMock()
    metadata.has_migration.return_value = False
    runner = MigrationRunner(project)
    with patch.object(MigrationRunner, "_record_migration_result"):
        result, status = runner._apply_migration(SpkSkillPackMigration(), metadata, dry_run=False)
    assert status == "failed" and not result.success
    assert any("Pack skills could not be resolved" in error for error in result.errors)
