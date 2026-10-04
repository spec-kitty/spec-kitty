"""SC-001 ATDD: a charter-activated pack skill survives every retiring installer path.

Drives the real paths end to end (mission ``pack-skills-kind-01M43419``, WP04,
issue #5193):

``spec-kitty charter activate skill`` -> project skill roots of the configured
agents -> each of the four skill-installing migrations and the verifier repair
(all of which retire what the catalog no longer lists) -> still present ->
``charter deactivate skill`` -> removed, with everything else byte-identical.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import charter_app
from specify_cli.skills.catalog import PackSkillCatalogError, resolve_project_skill_catalog
from specify_cli.skills.installer import install_all_skills
from specify_cli.skills.manifest import ORIGIN_PACK, load_manifest, save_manifest
from specify_cli.skills.verifier import repair_skills, verify_installed_skills
from specify_cli.tool_surface.operations import ApplyConsent
from specify_cli.upgrade.assessment import prepare_upgrade_repairs
from specify_cli.upgrade.migrations.m_2_0_11_install_skills import InstallSkillsMigration
from specify_cli.upgrade.migrations.m_2_1_1_repair_skill_pack import RepairSkillPackMigration
from specify_cli.upgrade.migrations.m_3_0_3_globalize_skill_pack import GlobalizeSkillPackMigration
from specify_cli.upgrade.migrations.m_3_2_0rc35_spk_skill_pack import SpkSkillPackMigration
from tests.charter import skill_pack_support as support

pytestmark = [pytest.mark.integration]

runner = CliRunner()

PACK_SKILL_STAGING = Path(".kittify/runtime/pack-skills")  # the documented staging root (plan decision 4)
SKILL_ID = "deploy-helper"
RENDERED = "acme-deploy-helper"
AGENT_ROOTS = (".claude/skills", ".agents/skills")  # claude (native) + codex (shared)
PROCEDURE_TEXT = "Substance carried by a procedure."
AGENTS_CONFIG = "agents:\n  available:\n    - claude\n    - codex\nactivated_skills: []\n"


def _invoke(project: Path, verb: str, *args: str) -> str:
    result = runner.invoke(charter_app, [verb, "--repo-root", str(project), "--no-compile", *args], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    return result.output


def _snapshot(root: Path, *, ignore: tuple[str, ...] = ()) -> dict[str, object]:
    """Every file, symlink and directory under *root*, minus *ignore* subtrees."""
    entries: dict[str, object] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if any(relative == item or relative.startswith(item + "/") for item in ignore):
            continue
        if path.is_symlink():
            entries[relative] = ("link", os.readlink(path))
        elif path.is_dir():
            entries[relative] = "dir"
        else:
            entries[relative] = path.read_bytes()
    return entries


def _without_empty_runtime(entries: dict[str, object]) -> dict[str, object]:
    """Drop the ``.kittify/runtime`` directory the staging root leaves behind when empty."""
    return {key: value for key, value in entries.items() if not (key == ".kittify/runtime" and not any(k.startswith(".kittify/runtime/") for k in entries))}


def _rendered_path(project: Path, root: str, name: str = RENDERED) -> Path:
    return project / root / name / "SKILL.md"


def _assert_projected(project: Path) -> None:
    for root in AGENT_ROOTS:
        assert _rendered_path(project, root).is_file(), f"{root}/{RENDERED} missing"
    manifest = load_manifest(project, strict=True)
    assert manifest is not None
    pack_entries = [entry for entry in manifest.entries if entry.origin == ORIGIN_PACK]
    assert {entry.agent_key for entry in pack_entries} == {"claude", "codex"}
    assert {entry.skill_name for entry in pack_entries} == {RENDERED}
    assert all(entry.source_hash and entry.source_ref for entry in pack_entries)


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    return fake_home


@pytest.fixture
def project(tmp_path: Path, home: Path) -> Path:
    """A configured project (claude + codex) with an org pack, built-in skills already installed."""
    pack = tmp_path / "pack"
    pack.mkdir()
    support.write_skill(pack, SKILL_ID)
    support.write_procedure(pack, "release-proc")
    support.write_fragment(
        pack, nodes=[(f"skill:{SKILL_ID}", "skill"), ("procedure:release-proc", "procedure")], edges=[(f"skill:{SKILL_ID}", "procedure:release-proc", "requires")]
    )
    support.write_org_charter(pack, namespace="acme")
    root = tmp_path / "project"
    root.mkdir()
    support.write_config(root, pack, extra=AGENTS_CONFIG)
    manifest = install_all_skills(root, ["claude", "codex"], resolve_project_skill_catalog(root))
    save_manifest(manifest, root)
    return root


def test_pack_skill_lifecycle_survives_every_retiring_path(project: Path, home: Path) -> None:
    before = _snapshot(project, ignore=(PACK_SKILL_STAGING.as_posix(), ".kittify/skills-manifest.json"))
    home_before = _snapshot(home)

    _invoke(project, "activate", "skill", SKILL_ID)
    _assert_projected(project)

    body = _rendered_path(project, ".claude/skills").read_text(encoding="utf-8")
    assert "spec-kitty charter context --include procedure:release-proc" in body
    assert PROCEDURE_TEXT not in body
    assert "allowed-tools" not in body

    # Each skill-installing migration (retire semantics) leaves the pack skill in place.
    for migration in (InstallSkillsMigration(), RepairSkillPackMigration(), GlobalizeSkillPackMigration(), SpkSkillPackMigration()):
        result = migration.apply(project)
        assert result.success, (migration.migration_id, result.errors)
        _assert_projected(project)

    # The verifier repair path (retire=True) restores a deleted pack file and keeps the rest.
    _rendered_path(project, ".claude/skills").unlink()
    verdict = verify_installed_skills(project)
    assert not verdict.ok and any(entry.skill_name == RENDERED for entry in verdict.missing)
    repaired, failed = repair_skills(project, verdict, resolve_project_skill_catalog(project))
    assert (repaired, failed) == (1, 0)
    _assert_projected(project)
    assert verify_installed_skills(project).ok

    # A skill in force whose source stopped loading is a refusal, never a planned retirement.
    record = project.parent / "pack" / "skills" / f"{SKILL_ID}.skill.yaml"
    loadable = record.read_text(encoding="utf-8")
    record.write_text(loadable.replace("{", "{unknown_key: 1, ", 1), encoding="utf-8")
    with pytest.warns(UserWarning, match="Skipping invalid org pack-skill"), pytest.raises(PackSkillCatalogError, match=SKILL_ID):
        prepare_upgrade_repairs(project, consent=ApplyConsent(automatic=True))
    record.write_text(loadable, encoding="utf-8")
    _assert_projected(project)

    # Pack skills are project-root only: nothing carrying the rendered name under HOME.
    assert not [path for path in home.rglob("*") if RENDERED in path.as_posix()]

    _invoke(project, "deactivate", "skill", SKILL_ID)
    for root in AGENT_ROOTS:
        assert not (project / root / RENDERED).exists(), f"{root}/{RENDERED} not retired"
    manifest = load_manifest(project, strict=True)
    assert manifest is not None and not [entry for entry in manifest.entries if entry.origin == ORIGIN_PACK]

    after = _snapshot(project, ignore=(PACK_SKILL_STAGING.as_posix(), ".kittify/skills-manifest.json"))
    assert _without_empty_runtime(after) == _without_empty_runtime(before)
    assert _snapshot(home) == home_before or all(RENDERED not in key for key in _snapshot(home))


def test_unowned_same_name_directory_is_preserved_and_reported(project: Path) -> None:
    foreign = project / ".claude" / "skills" / RENDERED
    foreign.mkdir(parents=True)
    (foreign / "notes.txt").write_text("mine\n", encoding="utf-8")
    other = _rendered_path(project, ".agents/skills")
    other.parent.mkdir(parents=True)
    other.write_text("---\nname: acme-deploy-helper\n---\nuser authored\n", encoding="utf-8")

    output = _invoke(project, "activate", "skill", SKILL_ID)

    assert (foreign / "notes.txt").read_text(encoding="utf-8") == "mine\n"
    assert not (foreign / "SKILL.md").exists()
    assert other.read_text(encoding="utf-8").endswith("user authored\n")
    assert output.count("preserved") >= 2, output
    manifest = load_manifest(project, strict=True)
    assert manifest is not None and not [entry for entry in manifest.entries if entry.origin == ORIGIN_PACK]


def _reconfigure(project: Path, pack: Path, activated: list[str], *, project_namespace: str | None = None) -> None:
    listed = "".join(f"  - {item}\n" for item in activated)
    support.write_config(project, pack, extra=f"agents:\n  available:\n    - claude\n    - codex\nactivated_skills:\n{listed}", project_namespace=project_namespace)


def test_name_collision_fails_before_any_write(tmp_path: Path, project: Path) -> None:
    """Two skills rendering to one name: refused with the whole tree (staging, roots, manifest) untouched."""
    pack = tmp_path / "pack"
    support.write_skill(pack, "x-y")  # org tier, namespace "acme"  -> acme-x-y
    support.write_skill(project / ".kittify" / "doctrine", "y")  # project tier, namespace "acme-x" -> acme-x-y
    _reconfigure(project, pack, ["x-y", "y"], project_namespace="acme-x")
    snapshot = _snapshot(project)

    with pytest.raises(PackSkillCatalogError, match="acme-x-y"):
        resolve_project_skill_catalog(project)
    assert _snapshot(project) == snapshot


def test_unknown_builtin_wrapper_target_is_refused_with_no_writes(tmp_path: Path, project: Path) -> None:
    pack = tmp_path / "pack"
    support.write_skill(pack, "bad-wrapper", form="wrapper", expands_to="builtin:spec-kitty.nope")
    _reconfigure(project, pack, ["bad-wrapper"])
    snapshot = _snapshot(project)

    with pytest.raises(PackSkillCatalogError, match="spec-kitty.nope"):
        resolve_project_skill_catalog(project)
    assert _snapshot(project) == snapshot


def test_activation_hook_reports_a_refusal_and_writes_no_skill_files(tmp_path: Path, project: Path) -> None:
    """The activation is committed, but the refused projection writes nothing and says how to recover."""
    pack = tmp_path / "pack"
    support.write_skill(pack, "x-y")
    support.write_skill(project / ".kittify" / "doctrine", "y")
    _reconfigure(project, pack, ["y"], project_namespace="acme-x")
    snapshot_roots = {root: _snapshot(project / root) if (project / root).exists() else None for root in AGENT_ROOTS}

    result = runner.invoke(charter_app, ["activate", "--repo-root", str(project), "--no-compile", "skill", "x-y"], catch_exceptions=False)

    assert result.exit_code == 1, result.output
    assert "pack skills were not projected" in result.output and "acme-x-y" in result.output
    assert {root: _snapshot(project / root) if (project / root).exists() else None for root in AGENT_ROOTS} == snapshot_roots
    assert not (project / PACK_SKILL_STAGING).exists()


def test_the_hook_ignores_every_kind_but_skill(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.cli.commands.charter import activate

    def boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("only a skill (de)activation re-projects")

    monkeypatch.setattr("specify_cli.skills.installer.project_pack_skills", boom)
    assert activate.reproject_pack_skills(project, "directive") is None
