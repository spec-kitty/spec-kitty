"""Catalog seam + project-root projection of pack skills (mission pack-skills-kind-01M43419, WP04 T017/T019).

NFR-002: every refusal leaves the agent roots, the staging directory and the
manifest byte-identical (0 writes). Pack skills never reach a user-global root.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from specify_cli.skills import catalog as catalog_module
from specify_cli.skills.catalog import (
    PackSkillCatalogError,
    resolve_builtin_skill_catalog,
    resolve_project_skill_catalog,
)
from specify_cli.skills.installer import (
    PackSkillProjection,
    assess_skill_installation,
    install_all_skills,
    project_pack_skills,
)
from specify_cli.skills.manifest import (
    ORIGIN_BUILTIN,
    ORIGIN_PACK,
    ManagedFileEntry,
    ManagedSkillManifest,
    load_manifest,
    save_manifest,
)
from specify_cli.skills.registry import SkillRegistry
from specify_cli.tool_surface.operations import AssessmentInputs, ApplyConsent, OperationRoot
from tests.charter import skill_pack_support as support

pytestmark = [pytest.mark.integration]

PACK_SKILL_STAGING = Path(".kittify/runtime/pack-skills")  # the documented staging root (plan decision 4)
RENDERED = "acme-deploy-helper"
AGENTS = ("claude", "codex")
CONFIG_EXTRA = "agents:\n  available:\n    - claude\n    - codex\nactivated_skills:\n  - deploy-helper\n"


def _tree(root: Path) -> dict[str, object]:
    out: dict[str, object] = {}
    for path in sorted(root.rglob("*")):
        key = path.relative_to(root).as_posix()
        out[key] = ("link", os.readlink(path)) if path.is_symlink() else ("dir" if path.is_dir() else path.read_bytes())
    return out


def _fake_builtin(tmp_path: Path, *names: str) -> SkillRegistry:
    root = tmp_path / "builtin-skills"
    root.mkdir(exist_ok=True)
    for name in names:
        (root / name).mkdir(exist_ok=True)
        (root / name / "SKILL.md").write_text(f"---\nname: {name}\ndescription: built-in {name}\n---\n# {name}\n", encoding="utf-8")
    return SkillRegistry(root)


@pytest.fixture(autouse=True)
def _fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


@pytest.fixture
def project(tmp_path: Path) -> Path:
    pack = tmp_path / "pack"
    pack.mkdir()
    support.write_skill(pack, "deploy-helper")
    support.write_org_charter(pack, namespace="acme")
    root = tmp_path / "project"
    root.mkdir()
    support.write_config(root, pack, extra=CONFIG_EXTRA)
    return root


# -- builtin resolution -------------------------------------------------------


def test_builtin_catalog_prefers_the_package_then_the_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package = resolve_builtin_skill_catalog()
    assert package is not None and package.discover_skills()

    checkout = tmp_path / "repo"
    skills = checkout / "src" / "charter" / "offering" / "skills" / "local-only"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text("# local\n", encoding="utf-8")
    preferred = resolve_builtin_skill_catalog(local_repo=checkout, prefer_local=True)
    assert preferred is not None and [skill.name for skill in preferred.discover_skills()] == ["local-only"]

    def broken() -> SkillRegistry:
        raise ModuleNotFoundError("charter.offering")

    monkeypatch.setattr(SkillRegistry, "from_package", staticmethod(broken))
    fallback = resolve_builtin_skill_catalog(local_repo=checkout)
    assert fallback is not None and [skill.name for skill in fallback.discover_skills()] == ["local-only"]

    empty = tmp_path / "empty-repo"
    (empty / "src" / "charter" / "offering" / "skills").mkdir(parents=True)
    assert resolve_builtin_skill_catalog(local_repo=empty) is None
    monkeypatch.setattr("specify_cli.template.get_local_repo_root", lambda *a, **k: None)
    assert resolve_builtin_skill_catalog() is None


# -- the seam -----------------------------------------------------------------


def test_project_without_pack_sources_returns_the_shipped_registry_and_writes_nothing(tmp_path: Path) -> None:
    project = tmp_path / "plain"
    (project / ".kittify").mkdir(parents=True)
    shipped = _fake_builtin(tmp_path, "spk-one")
    before = _tree(project)

    assert resolve_project_skill_catalog(project, builtin=shipped) is shipped
    assert _tree(project) == before


def test_missing_shipped_catalog_falls_back_to_the_package_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = tmp_path / "plain"
    (project / ".kittify").mkdir(parents=True)
    monkeypatch.setattr(catalog_module, "resolve_builtin_skill_catalog", lambda **_: None)
    assert isinstance(resolve_project_skill_catalog(project), SkillRegistry)


def test_pack_skill_is_staged_tagged_and_merged_with_the_shipped_catalog(project: Path, tmp_path: Path) -> None:
    shipped = _fake_builtin(tmp_path, "spk-one")

    registry = resolve_project_skill_catalog(project, builtin=shipped)

    staged = project / PACK_SKILL_STAGING / RENDERED / "SKILL.md"
    assert staged.is_file() and (staged.stat().st_mode & 0o777) == 0o644
    assert 'name: "acme-deploy-helper"' in staged.read_text(encoding="utf-8")
    skills = {skill.name: skill for skill in registry.discover_skills()}
    assert set(skills) == {"spk-one", RENDERED}
    assert skills["spk-one"].origin == ORIGIN_BUILTIN and skills["spk-one"].source_hash == ""
    pack = skills[RENDERED]
    assert pack.origin == ORIGIN_PACK and len(pack.source_hash) == 64
    assert pack.source_ref.endswith("deploy-helper.skill.yaml")
    assert registry.get_skill(RENDERED) == pack

    snapshot_skills, observations = registry.snapshot_catalog()
    assert {skill.name for skill in snapshot_skills} == {"spk-one", RENDERED}
    assert {skill.origin for skill in snapshot_skills} == {ORIGIN_BUILTIN, ORIGIN_PACK}
    assert any(item.path == staged for item in observations)


def test_warm_resolution_does_not_rewrite_the_staged_file(project: Path, tmp_path: Path) -> None:
    shipped = _fake_builtin(tmp_path, "spk-one")
    resolve_project_skill_catalog(project, builtin=shipped)
    staged = project / PACK_SKILL_STAGING / RENDERED / "SKILL.md"
    first = staged.stat().st_mtime_ns

    resolve_project_skill_catalog(project, builtin=shipped)

    assert staged.stat().st_mtime_ns == first


def test_changed_source_restages_and_a_deactivated_skill_is_unstaged(project: Path, tmp_path: Path) -> None:
    shipped = _fake_builtin(tmp_path, "spk-one")
    resolve_project_skill_catalog(project, builtin=shipped)
    staged_dir = project / PACK_SKILL_STAGING
    (staged_dir / "stale-leftover").mkdir()
    (staged_dir / "stray-file").write_text("x", encoding="utf-8")

    support.write_skill(tmp_path / "pack", "deploy-helper")
    (tmp_path / "pack" / "skills" / "deploy-helper.skill.md").write_text("New body\n", encoding="utf-8")
    resolve_project_skill_catalog(project, builtin=shipped)
    assert "New body" in (staged_dir / RENDERED / "SKILL.md").read_text(encoding="utf-8")
    assert sorted(path.name for path in staged_dir.iterdir()) == [RENDERED]

    support.write_config(project, tmp_path / "pack", extra="agents:\n  available:\n    - claude\nactivated_skills: []\n")
    assert resolve_project_skill_catalog(project, builtin=shipped) is shipped
    assert not staged_dir.exists()


def test_a_symlinked_or_non_directory_staging_root_is_refused(project: Path, tmp_path: Path) -> None:
    shipped = _fake_builtin(tmp_path, "spk-one")
    staging = project / PACK_SKILL_STAGING
    staging.parent.mkdir(parents=True)
    target = tmp_path / "elsewhere"
    target.mkdir()
    staging.symlink_to(target)
    with pytest.raises(PackSkillCatalogError, match="staging root"):
        resolve_project_skill_catalog(project, builtin=shipped)
    assert not any(target.iterdir())

    staging.unlink()
    staging.write_text("not a directory", encoding="utf-8")
    with pytest.raises(PackSkillCatalogError, match="staging root"):
        resolve_project_skill_catalog(project, builtin=shipped)


def test_symlinked_skill_directory_and_directory_in_place_of_file_are_refused(project: Path, tmp_path: Path) -> None:
    shipped = _fake_builtin(tmp_path, "spk-one")
    staging = project / PACK_SKILL_STAGING
    staging.mkdir(parents=True)
    target = tmp_path / "elsewhere"
    target.mkdir()
    (staging / RENDERED).symlink_to(target)
    with pytest.raises(PackSkillCatalogError, match="symlink"):
        resolve_project_skill_catalog(project, builtin=shipped)
    assert not any(target.iterdir())

    (staging / RENDERED).unlink()
    (staging / RENDERED).mkdir()
    (staging / RENDERED / "SKILL.md").mkdir()
    with pytest.raises(PackSkillCatalogError, match="not a regular file"):
        resolve_project_skill_catalog(project, builtin=shipped)


def test_collision_with_a_builtin_skill_name_is_refused_with_zero_writes(project: Path, tmp_path: Path) -> None:
    """NFR-002: agent roots, staging and manifest are all byte-identical after the refusal."""
    shipped = _fake_builtin(tmp_path, RENDERED)
    manifest = ManagedSkillManifest(spec_kitty_version="1")
    manifest.add_entry(ManagedFileEntry("keep", "SKILL.md", ".claude/skills/keep/SKILL.md", "native-root-required", "claude", "sha256:00", "t"))
    save_manifest(manifest, project)
    (project / ".claude" / "skills" / "keep").mkdir(parents=True)
    (project / ".claude" / "skills" / "keep" / "SKILL.md").write_text("mine", encoding="utf-8")
    before = _tree(project)

    with pytest.raises(PackSkillCatalogError, match="name of a built-in skill"):
        resolve_project_skill_catalog(project, builtin=shipped)

    assert _tree(project) == before
    assert not (project / PACK_SKILL_STAGING).exists()


def test_a_namespaceless_pack_skill_is_refused_before_staging(project: Path, tmp_path: Path) -> None:
    support.write_org_charter(tmp_path / "pack", namespace=None)
    before = _tree(project)
    with pytest.raises(PackSkillCatalogError, match="skill namespace"):
        resolve_project_skill_catalog(project, builtin=_fake_builtin(tmp_path, "spk-one"))
    assert _tree(project) == before


# -- manifest provenance --------------------------------------------------------


def test_manifest_provenance_fields_are_optional_and_omitted_by_default(tmp_path: Path) -> None:
    project = tmp_path / "p"
    (project / ".kittify").mkdir(parents=True)
    manifest = ManagedSkillManifest(spec_kitty_version="1")
    manifest.add_entry(ManagedFileEntry("b", "SKILL.md", ".claude/skills/b/SKILL.md", "native-root-required", "claude", "sha256:aa", "t"))
    manifest.add_entry(
        ManagedFileEntry(
            "p",
            "SKILL.md",
            ".claude/skills/p/SKILL.md",
            "native-root-required",
            "claude",
            "sha256:bb",
            "t",
            origin=ORIGIN_PACK,
            source_ref="pack/x.skill.yaml",
            source_hash="cc",
        )
    )
    save_manifest(manifest, project)

    raw = (project / ".kittify" / "skills-manifest.json").read_text(encoding="utf-8")
    assert raw.count('"origin"') == 1 and raw.count('"source_hash"') == 1 and raw.count('"source_ref"') == 1
    loaded = load_manifest(project, strict=True)
    assert loaded is not None
    by_name = {entry.skill_name: entry for entry in loaded.entries}
    assert (by_name["b"].origin, by_name["b"].source_ref, by_name["b"].source_hash) == (ORIGIN_BUILTIN, "", "")
    assert (by_name["p"].origin, by_name["p"].source_ref, by_name["p"].source_hash) == (ORIGIN_PACK, "pack/x.skill.yaml", "cc")


def test_a_pre_provenance_manifest_loads_and_is_not_rewritten(tmp_path: Path) -> None:
    project = tmp_path / "p"
    (project / ".kittify").mkdir(parents=True)
    legacy = (
        '{\n  "version": 1,\n  "created_at": "t",\n  "updated_at": "t",\n  "spec_kitty_version": "1",\n  "entries": [\n    {\n'
        '      "skill_name": "b",\n      "source_file": "SKILL.md",\n      "installed_path": ".claude/skills/b/SKILL.md",\n'
        '      "installation_class": "native-root-required",\n      "agent_key": "claude",\n      "content_hash": "sha256:aa",\n'
        '      "installed_at": "t",\n      "delivery_mode": "copy"\n    }\n  ]\n}\n'
    )
    target = project / ".kittify" / "skills-manifest.json"
    target.write_text(legacy, encoding="utf-8")
    loaded = load_manifest(project, strict=True)
    assert loaded is not None and loaded.entries[0].origin == ORIGIN_BUILTIN
    save_manifest(loaded, project)
    assert target.read_text(encoding="utf-8") == legacy


# -- installer ------------------------------------------------------------------


def _installed(project: Path, tmp_path: Path) -> tuple[SkillRegistry, SkillRegistry]:
    shipped = _fake_builtin(tmp_path, "spk-one")
    merged = resolve_project_skill_catalog(project, builtin=shipped)
    save_manifest(install_all_skills(project, list(AGENTS), merged), project)
    return shipped, merged


def test_pack_skills_install_to_project_roots_only_never_global(project: Path, tmp_path: Path, _fake_home: Path) -> None:
    _installed(project, tmp_path)

    for root in (".claude/skills", ".agents/skills"):
        assert (project / root / RENDERED / "SKILL.md").is_file()
    assert not [path for path in _fake_home.rglob("*") if RENDERED in path.as_posix()]
    assert (_fake_home / ".claude" / "skills" / "spk-one" / "SKILL.md").exists()  # built-in still goes global
    manifest = load_manifest(project, strict=True)
    assert manifest is not None
    pack = [entry for entry in manifest.entries if entry.origin == ORIGIN_PACK]
    assert {(entry.agent_key, entry.installed_path) for entry in pack} == {
        ("claude", f".claude/skills/{RENDERED}/SKILL.md"),
        ("codex", f".agents/skills/{RENDERED}/SKILL.md"),
    }


def test_the_global_batch_never_selects_a_pack_skill(project: Path, tmp_path: Path) -> None:
    _, merged = _installed(project, tmp_path)
    consent = ApplyConsent(automatic=True)
    inputs = AssessmentInputs(OperationRoot("project", "project", project.absolute()), consent=consent)

    installation = assess_skill_installation(inputs, merged, AGENTS)

    assert not [effect for effect in installation.global_assets.effects if RENDERED in effect.path]
    assert [effect for effect in installation.project_skills.effects if effect.path.endswith("SKILL.md") and RENDERED in effect.path] == []  # already current


def test_a_builtin_only_catalog_would_retire_the_pack_skill(project: Path, tmp_path: Path) -> None:
    """The retire hazard (#5193): why every caller must resolve its catalog through the seam."""
    shipped, _ = _installed(project, tmp_path)

    save_manifest(install_all_skills(project, list(AGENTS), shipped), project)

    assert not (project / ".claude" / "skills" / RENDERED).exists()
    manifest = load_manifest(project, strict=True)
    assert manifest is not None and not [entry for entry in manifest.entries if entry.origin == ORIGIN_PACK]


def test_the_last_pack_skill_is_retired_even_with_an_empty_catalog(project: Path, tmp_path: Path) -> None:
    _installed(project, tmp_path)
    empty = SkillRegistry(tmp_path / "no-skills-here")
    (tmp_path / "no-skills-here").mkdir()

    manifest = install_all_skills(project, list(AGENTS), empty)

    assert not (project / ".claude" / "skills" / RENDERED).exists()
    assert not (project / ".agents" / "skills" / RENDERED).exists()
    assert [entry.skill_name for entry in manifest.entries if entry.origin == ORIGIN_PACK] == []
    # An empty catalog is ambiguous for built-in skills: they are never retired by it.
    assert any(entry.skill_name == "spk-one" for entry in manifest.entries)
    assert (project / ".claude" / "skills" / "spk-one" / "SKILL.md").is_file()


def test_a_locally_modified_pack_file_survives_retirement_and_is_reported(project: Path, tmp_path: Path) -> None:
    shipped, _ = _installed(project, tmp_path)
    edited = project / ".claude" / "skills" / RENDERED / "SKILL.md"
    edited.write_text("my edits\n", encoding="utf-8")

    support.write_config(project, tmp_path / "pack", extra="agents:\n  available:\n    - claude\n    - codex\nactivated_skills: []\n")
    projection = project_pack_skills(project, registry=resolve_project_skill_catalog(project, builtin=shipped))

    assert edited.read_text(encoding="utf-8") == "my edits\n"
    assert not (project / ".agents" / "skills" / RENDERED).exists()
    assert any(path.endswith(f"{RENDERED}/SKILL.md") and "consent" in reason.lower() for path, reason in projection.preserved)


# -- project_pack_skills ----------------------------------------------------------


def test_projection_is_empty_without_installable_agents_or_pack_skills(project: Path, tmp_path: Path) -> None:
    shipped = _fake_builtin(tmp_path, "spk-one")
    support.write_config(project, tmp_path / "pack", extra="agents:\n  available:\n    - q\nactivated_skills:\n  - deploy-helper\n")
    assert project_pack_skills(project, registry=resolve_project_skill_catalog(project, builtin=shipped)) == PackSkillProjection()

    support.write_config(project, tmp_path / "pack", extra=CONFIG_EXTRA.replace("  - deploy-helper\n", "[]\n").replace("activated_skills:\n", "activated_skills: "))
    assert project_pack_skills(project, registry=resolve_project_skill_catalog(project, builtin=shipped)) == PackSkillProjection()

    support.write_config(project, None, extra="activated_skills: []\n")
    assert project_pack_skills(project) == PackSkillProjection()


def test_projection_touches_only_pack_paths_and_reports_changes(project: Path, tmp_path: Path) -> None:
    shipped = _fake_builtin(tmp_path, "spk-one")
    registry = resolve_project_skill_catalog(project, builtin=shipped)

    projection = project_pack_skills(project, registry=registry)

    assert projection.changed == (f".agents/skills/{RENDERED}/SKILL.md", f".claude/skills/{RENDERED}/SKILL.md")
    assert projection.preserved == ()
    assert not (project / ".claude" / "skills" / "spk-one").exists()  # built-in files are not this hook's business
    assert project_pack_skills(project, registry=registry).changed == ()  # idempotent


def test_projection_raises_when_the_assessment_is_incomplete(project: Path, tmp_path: Path) -> None:
    shipped = _fake_builtin(tmp_path, "spk-one")
    registry = resolve_project_skill_catalog(project, builtin=shipped)
    (project / ".kittify" / "skills-manifest.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="[Ii]nvalid|manifest"):
        project_pack_skills(project, registry=registry)

    (project / ".kittify" / "skills-manifest.json").unlink()
    conflicting = project / ".claude" / "skills"
    conflicting.parent.mkdir(parents=True, exist_ok=True)
    conflicting.write_text("a file where the skills root should be", encoding="utf-8")
    with pytest.raises(OSError, match="[Aa]ssessment|skill"):
        project_pack_skills(project, registry=registry)


def test_an_unowned_same_name_directory_without_skill_md_is_left_alone(project: Path, tmp_path: Path) -> None:
    shipped = _fake_builtin(tmp_path, "spk-one")
    foreign = project / ".claude" / "skills" / RENDERED
    foreign.mkdir(parents=True)
    (foreign / "notes.txt").write_text("mine", encoding="utf-8")

    projection = project_pack_skills(project, registry=resolve_project_skill_catalog(project, builtin=shipped))

    assert sorted(path.name for path in foreign.iterdir()) == ["notes.txt"]
    assert (f".claude/skills/{RENDERED}/SKILL.md", "Existing skill directory is not owned by the skill manager") in projection.preserved
    assert (project / ".agents" / "skills" / RENDERED / "SKILL.md").is_file()  # the other agent root is unaffected


def test_without_agents_the_projection_neither_stages_nor_refuses(project: Path, tmp_path: Path) -> None:
    """No project skill root to write into: even an unusable (namespaceless) pack skill is not an error yet."""
    support.write_org_charter(tmp_path / "pack", namespace=None)
    support.write_config(project, tmp_path / "pack", extra="activated_skills:\n  - deploy-helper\n")
    before = _tree(project)

    assert project_pack_skills(project) == PackSkillProjection()
    assert _tree(project) == before
