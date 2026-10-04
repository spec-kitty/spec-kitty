"""Read-only catalog resolution and fail-closed migrations (WP04 review cycle 2).

``detect()``, assessment and ``--dry-run`` never write (no staging, no rmtree);
a broken pack skill is a recorded migration failure, not a traceback.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from specify_cli.skills.catalog import resolve_project_skill_catalog
from specify_cli.skills.installer import assess_skill_installation, install_all_skills
from specify_cli.skills.manifest import save_manifest
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


def _broken_org_drg(root: Path, pack: Path) -> None:
    (pack / "broken.graph.yaml").write_text("nodes: [unclosed\n", encoding="utf-8")


def _unfetched_pack(root: Path, pack: Path) -> None:
    shutil.rmtree(pack)


def _unparsable_charter(root: Path, pack: Path) -> None:
    (pack / "org-charter.yaml").write_text("org_name: [unclosed\n", encoding="utf-8")


def _string_required_skills(root: Path, pack: Path) -> None:
    (pack / "org-charter.yaml").write_text("org_name: acme-org\nrequired_skills: deploy-helper\n", encoding="utf-8")


def _pack_block(root: Path, pack: Path) -> tuple[Path, str, str]:
    config = root / ".kittify" / "config.yaml"
    return config, config.read_text(encoding="utf-8"), f"      - name: acme\n        local_path: {pack}\n"


def _registry_entry_without_local_path_beside_the_pack(root: Path, pack: Path) -> None:
    config, text, entry = _pack_block(root, pack)
    config.write_text(text.replace(entry, f"{entry}      - name: nopath\n"), encoding="utf-8")


def _registry_entry_without_local_path_alone(root: Path, pack: Path) -> None:
    config, text, entry = _pack_block(root, pack)
    config.write_text(text.replace(entry, "      - name: nopath\n"), encoding="utf-8")


def _packs_not_a_list(root: Path, pack: Path) -> None:
    config, text, entry = _pack_block(root, pack)
    config.write_text(text.replace(f"    packs:\n{entry}", "    packs: acme\n"), encoding="utf-8")


def _charter_packs_not_a_mapping(root: Path, pack: Path) -> None:
    config, text, entry = _pack_block(root, pack)
    config.write_text(text.replace(f"charter_packs:\n  org:\n    packs:\n{entry}", "charter_packs: nope\n"), encoding="utf-8")


def _org_block_not_a_mapping(root: Path, pack: Path) -> None:
    config, text, entry = _pack_block(root, pack)
    config.write_text(text.replace(f"  org:\n    packs:\n{entry}", "  org: nope\n"), encoding="utf-8")


def _pack_path_is_a_file(root: Path, pack: Path) -> None:
    shutil.rmtree(pack)
    pack.write_text("not a directory\n", encoding="utf-8")


def _unset_env_var_in_pack_path(root: Path, pack: Path) -> None:
    config, text, _entry = _pack_block(root, pack)
    config.write_text(text.replace(f"local_path: {pack}", "local_path: ${SPEC_KITTY_TEST_UNSET_PACK_DIR}/pack"), encoding="utf-8")


def _empty_org_charter(root: Path, pack: Path) -> None:
    (pack / "org-charter.yaml").write_bytes(b"")


def _whitespace_only_org_charter(root: Path, pack: Path) -> None:
    (pack / "org-charter.yaml").write_text(" \n\n  \n", encoding="utf-8")


#: Damages to the org-pack registry or the pack on disk, valid for a project with or without a pack skill.
REGISTRY_DAMAGES = [
    _registry_entry_without_local_path_beside_the_pack,
    _registry_entry_without_local_path_alone,
    _packs_not_a_list,
    _charter_packs_not_a_mapping,
    _org_block_not_a_mapping,
    _pack_path_is_a_file,
    _unset_env_var_in_pack_path,
]


@pytest.mark.parametrize(
    "damage", [_broken_org_drg, _unfetched_pack, _unparsable_charter, _string_required_skills, _empty_org_charter, _whitespace_only_org_charter, *REGISTRY_DAMAGES]
)
@pytest.mark.parametrize("migration", DETECTING)
def test_a_broken_org_pack_changes_nothing_for_a_project_that_uses_no_pack_skill(tmp_path: Path, migration: type, damage: Callable[[Path, Path], None]) -> None:
    """No skill path may depend on the health of a pack the project takes no skill from (no pack entry, no activation)."""
    plain = tmp_path / "plain"
    plain.mkdir()
    support.write_config(plain, None, extra="agents:\n  available:\n    - claude\n    - codex\n")
    pack = tmp_path / "pack"
    pack.mkdir()
    support.write_org_charter(pack)
    broken = tmp_path / "broken"
    broken.mkdir()
    support.write_config(broken, pack, extra="agents:\n  available:\n    - claude\n    - codex\n")
    damage(broken, pack)

    assert _outcome(broken, migration) == _outcome(plain, migration)
    consent = ApplyConsent(automatic=True)
    assert _skill_codes(broken, consent) == _skill_codes(plain, consent)


def _skill_codes(root: Path, consent: ApplyConsent) -> set[str]:
    """Diagnostic codes of the skill paths. An unfetched pack also changes the *profile* provider's codes
    (``profile_input_invalid`` and friends), and an unset ``${VAR}`` in a pack path stops the whole-tool inventory
    (``inventory_unreadable``) -- on ``main`` too: neither belongs to the skill path, which this compares."""
    unrelated = {"inventory_unreadable"}
    return {item.code for item in prepare_upgrade_repairs(root, consent=consent).diagnostics if "profile" not in item.code and item.code not in unrelated}


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
    _broken_org_drg(root, pack)


def _non_utf8_body(root: Path, pack: Path) -> None:
    (pack / "skills" / "deploy-helper.skill.md").write_bytes(b"\xff\xfe not utf-8")


def _non_list_activation(root: Path, pack: Path) -> None:
    config = root / ".kittify" / "config.yaml"
    config.write_text(config.read_text(encoding="utf-8").replace("activated_skills:\n  - deploy-helper\n", "activated_skills: deploy-helper\n"), encoding="utf-8")


def _org_required(root: Path, pack: Path, charter: str = "org_name: acme-org\nskill_namespace: acme\nrequired_skills: [deploy-helper]\n") -> None:
    """Switch the project from an explicit activation to the org-required default (the org charter decides)."""
    config = root / ".kittify" / "config.yaml"
    config.write_text(config.read_text(encoding="utf-8").replace("activated_skills:\n  - deploy-helper\n", ""), encoding="utf-8")
    (pack / "org-charter.yaml").write_text(charter, encoding="utf-8")


def _explicit_pack_not_fetched(root: Path, pack: Path) -> None:
    shutil.rmtree(pack)


def _org_required_pack_not_fetched(root: Path, pack: Path) -> None:
    _org_required(root, pack)
    shutil.rmtree(pack)


def _org_charter_unparsable(root: Path, pack: Path) -> None:
    _org_required(root, pack, "org_name: [unclosed\n")


def _org_required_skills_not_a_list(root: Path, pack: Path) -> None:
    _org_required(root, pack, "org_name: acme-org\nskill_namespace: acme\nrequired_skills: deploy-helper\n")


def _while_org_decides(damage: Callable[[Path, Path], None]) -> Callable[[Path, Path], None]:
    """The registry damages with the org charter (not an explicit list) deciding what is in force: the registry is
    then the only record of which pack the installed skill came from."""

    def damaged(root: Path, pack: Path) -> None:
        _org_required(root, pack)
        damage(root, pack)

    damaged.__name__ = f"{damage.__name__}_while_org_decides"
    return damaged


def _org_charter_empty(root: Path, pack: Path) -> None:
    _org_required(root, pack, "")


def _org_charter_whitespace_only(root: Path, pack: Path) -> None:
    _org_required(root, pack, " \n\n  \n")


def _installed_copies(project: Path) -> list[Path]:
    return [project / ".claude" / "skills" / "acme-deploy-helper" / "SKILL.md", project / ".agents" / "skills" / "acme-deploy-helper" / "SKILL.md"]


@pytest.mark.parametrize(
    "cause",
    [
        _no_namespace,
        _sibling_duplicate_id,
        _broken_graph,
        _non_utf8_body,
        _non_list_activation,
        _explicit_pack_not_fetched,
        _org_required_pack_not_fetched,
        _org_charter_unparsable,
        _org_required_skills_not_a_list,
        _org_charter_empty,
        _org_charter_whitespace_only,
        *[_while_org_decides(damage) for damage in REGISTRY_DAMAGES],
    ],
)
@pytest.mark.parametrize("migration", DETECTING)
def test_a_broken_pack_makes_detect_true_and_apply_a_reported_error(tmp_path: Path, migration: type, cause: Callable[[Path, Path], None]) -> None:
    project = _project(tmp_path)
    save_manifest(install_all_skills(project, ["claude", "codex"], resolve_project_skill_catalog(project)), project)
    assert all(copy.is_file() for copy in _installed_copies(project))
    cause(project, tmp_path / "pack")
    before = _tree(project)

    assert migration().detect(project) is True
    for dry_run in (True, False):
        result = migration().apply(project, dry_run=dry_run)
        assert not result.success and "Pack skills could not be resolved" in result.errors[0]
    assert _tree(project) == before
    assert all(copy.is_file() for copy in _installed_copies(project))  # a refusal never retires an installed copy


def _charter_without_required_skills(root: Path, pack: Path) -> None:
    _org_required(root, pack, "org_name: acme-org\nskill_namespace: acme\n")


def _charter_with_null_required_skills(root: Path, pack: Path) -> None:
    _org_required(root, pack, "org_name: acme-org\nskill_namespace: acme\nrequired_skills:\n")


def _charter_requiring_nothing(root: Path, pack: Path) -> None:
    _org_required(root, pack, "org_name: acme-org\nskill_namespace: acme\nrequired_skills: []\n")


def _charter_deleted(root: Path, pack: Path) -> None:
    _org_required(root, pack)
    (pack / "org-charter.yaml").unlink()


def _pack_removed_from_config(root: Path, pack: Path) -> None:
    _org_required(root, pack)
    support.write_config(root, None, extra="agents:\n  available:\n    - claude\n    - codex\n")


@pytest.mark.parametrize(
    "authored",
    [_charter_without_required_skills, _charter_with_null_required_skills, _charter_requiring_nothing, _charter_deleted, _pack_removed_from_config],
)
def test_a_pack_skill_the_org_no_longer_requires_is_still_retired(tmp_path: Path, authored: Callable[[Path, Path], None]) -> None:
    """The refusals above never turn into "keep forever": an authored state that no longer requires the skill retires it."""
    project = _project(tmp_path)
    save_manifest(install_all_skills(project, ["claude", "codex"], resolve_project_skill_catalog(project)), project)
    authored(project, tmp_path / "pack")

    result = RepairSkillPackMigration().apply(project, dry_run=False)

    assert result.success, result.errors
    assert not any(copy.exists() for copy in _installed_copies(project))


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
