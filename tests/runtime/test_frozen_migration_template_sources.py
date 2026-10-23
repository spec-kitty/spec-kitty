"""Guard the frozen, migration-only template forks under ``specify_cli/missions`` (#5280).

The shipped migrations ``0.12.0_documentation_mission`` and
``0.9.2_research_mission_templates`` (and ``0.6.7_ensure_missions``, which cannot
apply today) stay byte-identical (DIRECTIVE_044) and
locate their sources at ``specify_cli/missions/{documentation,research}``, so
those ``templates/`` trees are frozen in place (operator ruling 2026-10-22).
This module pins three things:

1. the frozen tree never changes and nothing new appears under any
   ``specify_cli/missions/*/templates/`` (precedent:
   ``test_template_source_consolidation.test_software_dev_runtime_template_tree_removed``, #1731);
2. both shipped migrations still find their frozen sources in the REAL package
   tree (``test_m_0_9_2_research_mission_templates.py`` builds a fake one);
3. runtime never serves a frozen file, and the corrective migration
   ``4.0.0rc8_retire_stale_mission_template_forks`` recognises every frozen
   ``.md`` it may find in a project.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import specify_cli
from specify_cli.mission import Mission, get_mission_by_name
from specify_cli.runtime.home import get_package_asset_root
from specify_cli.runtime.resolver import resolve_template
from specify_cli.upgrade.migrations.m_0_9_2_research_mission_templates import ResearchMissionTemplatesMigration
from specify_cli.upgrade.migrations.m_0_12_0_documentation_mission import InstallDocumentationMission
from specify_cli.upgrade.migrations.m_4_0_0rc8_retire_stale_mission_template_forks import KNOWN_FORK_SHA256
from specify_cli.upgrade.migrations.m_4_0_0rc8_retire_stale_mission_template_forks import _fingerprint as fork_fingerprint

pytestmark = [pytest.mark.fast]

FROZEN_ROOT = Path(specify_cli.__file__).resolve().parent / "missions"

#: SHA-256 (CRLF folded to LF) of every file under ``specify_cli/missions/*/templates/``.
#: Frozen: changing a value means editing a source a shipped migration copies.
FROZEN_TEMPLATE_SOURCES: dict[str, str] = {
    "documentation/templates/divio/explanation-template.md": "fe810f3091a941c11f32df0ff0ede27446607468b3e9e373fac03b7b4af45c7a",
    "documentation/templates/divio/howto-template.md": "bad57e533f97024b369970e3712cf6fff6d57bfba75578d5bf70fcef9de44671",
    "documentation/templates/divio/reference-template.md": "33ad6e668847415a3813e145c8ffccb615e3e54effb67ba5d86e337154f2eb06",
    "documentation/templates/divio/tutorial-template.md": "e43f2cf966f9147b8e0d4d8729a944b398b3e50002ebede90dbb4789c8db4056",
    "documentation/templates/generators/jsdoc.json.template": "76206c45be8215c2c832474c19cda68dcaef1f417cd27966e56489daca4c9d19",
    "documentation/templates/generators/sphinx-conf.py.template": "9033d66b251f205d38bde9553bb5893866a323e71b211cb0e2a99d88684e437b",
    "documentation/templates/plan-template.md": "02088b60642aae5354f98b38ea12759189b7378ca1410ab976909b555553482c",
    "documentation/templates/release-template.md": "856b61fe0e7735a3c7103e1bcf242f5064326ed971edbb5aa3b5f6c4f04cf437",
    "documentation/templates/spec-template.md": "98cebd2cfab3d35d5bcb3bcd34083fe8e02be52e08fd3543e67fad5d0e19083c",
    "documentation/templates/task-prompt-template.md": "0e05bb4136f36d0f91b992853bd4e47b5271894650efef94f5faa2933deb7eba",
    "documentation/templates/tasks-template.md": "eaa08544c484100e6f4448370ad80face005e644ffb0754f09d10af7c1678cae",
    "research/templates/data-model-template.md": "d9115c00810c62874f1b456e3811827a14a94e2d8f770f30906ea41fc697d0c5",
    "research/templates/plan-template.md": "3c6bc2be02d879b3397e075a7d3770bcca23fcdf15e54cd77d08ae5176aec857",
    "research/templates/research-template.md": "3104d75be3c6112572c332c1362bfe8a8370b77a60da85304ec0e66ca384edbd",
    "research/templates/research/evidence-log.csv": "fb7b2021cbf3e5aa0c3a99f4cdd375a73410380d82bd7dd476cc0f4be1954d5c",
    "research/templates/research/source-register.csv": "2bd413c1cb1d9ff979604d02c7c3ddb2b06b93561827ec62bb621a5f55d291a6",
    "research/templates/spec-template.md": "16c845b94c48c67506e0a729ac5608357e971cb4078476e6211b862ba8168eae",
    "research/templates/task-prompt-template.md": "455a90e561f6020608395765f8bc851d4c7bff6350038efe0b549f5d953af9e6",
    "research/templates/tasks-template.md": "237b0954d3a87bc7f073c9a0037f231a068cec7db3e493f08c19de3e84c5689a",
}

_FROZEN_MD = sorted(rel for rel in FROZEN_TEMPLATE_SOURCES if rel.endswith(".md"))


def _fingerprint(path: Path) -> str:
    # The corrective migration's own fingerprint, so the pins and its proof agree.
    return fork_fingerprint(path.read_bytes())


def _template_files_under_live_tree() -> dict[str, str]:
    found: dict[str, str] = {}
    for templates_dir in sorted(FROZEN_ROOT.glob("*/templates")):
        for path in sorted(templates_dir.rglob("*")):
            if path.is_file() and path.name != ".gitkeep" and "__pycache__" not in path.parts:
                found[path.relative_to(FROZEN_ROOT).as_posix()] = _fingerprint(path)
    return found


def test_frozen_template_sources_are_unchanged_and_nothing_new_appears() -> None:
    """No file is added, edited or removed under ``specify_cli/missions/*/templates/``.

    Canonical templates live in ``packs/built-in/missions/<type>/templates/``
    (fetched from spec-kitty-open-packs). Edit them there; the files pinned
    here exist only so two shipped migrations keep their sources.
    """
    assert _template_files_under_live_tree() == FROZEN_TEMPLATE_SOURCES


def test_every_frozen_markdown_template_is_a_known_fork_version() -> None:
    """The corrective migration must recognise whatever the shipped migrations copy today."""
    for rel in _FROZEN_MD:
        mission_type, _, name = rel.partition("/templates/")
        key = f"{mission_type}/{name}"
        assert FROZEN_TEMPLATE_SOURCES[rel] in KNOWN_FORK_SHA256[key], key
    assert len(KNOWN_FORK_SHA256) == len(_FROZEN_MD)


def test_0_9_2_research_migration_finds_its_frozen_source_in_the_real_package(tmp_path: Path) -> None:
    migration = ResearchMissionTemplatesMigration()

    source = migration._find_package_research_mission()

    assert source is not None
    assert source.resolve() == FROZEN_ROOT / "research"
    assert (source / "templates" / "task-prompt-template.md").is_file()
    assert migration.can_apply(tmp_path) == (True, "")


def test_0_12_0_documentation_migration_finds_its_frozen_source_in_the_real_package(tmp_path: Path) -> None:
    migration = InstallDocumentationMission()

    source = migration._find_source_mission()

    assert source is not None
    assert source.resolve() == FROZEN_ROOT / "documentation"
    copied = {p.relative_to(FROZEN_ROOT).as_posix() for p in (source / "templates").rglob("*") if p.is_file()}
    assert copied == {rel for rel in FROZEN_TEMPLATE_SOURCES if rel.startswith("documentation/")}
    assert migration.can_apply(tmp_path) == (True, "")


@pytest.mark.parametrize("rel", _FROZEN_MD)
def test_runtime_resolution_never_serves_a_frozen_template(
    rel: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path / "empty-global-home"))
    monkeypatch.delenv("SPEC_KITTY_TEMPLATE_ROOT", raising=False)
    project = tmp_path / "project"
    (project / ".kittify").mkdir(parents=True)
    mission_type, _, name = rel.partition("/templates/")

    try:
        resolved = resolve_template(name, project, mission_type)
    except FileNotFoundError:
        return  # a fork-only name the packs renamed: nothing serves the fork either
    assert not resolved.path.resolve().is_relative_to(FROZEN_ROOT), resolved


@pytest.mark.parametrize("mission_type", ["documentation", "plan", "research", "software-dev"])
def test_packaged_mission_reads_templates_from_the_packs_copy(mission_type: str, tmp_path: Path) -> None:
    """Every packaged mission type redirects, so each must have a packs ``templates/`` dir."""
    pack_templates = get_package_asset_root() / mission_type / "templates"
    sample = next(p.name for p in sorted(pack_templates.iterdir()) if p.is_file())

    assert Mission(FROZEN_ROOT / mission_type).templates_dir == pack_templates
    mission = get_mission_by_name(mission_type, tmp_path / ".kittify")
    assert mission.templates_dir == pack_templates
    assert mission.get_template(sample) == pack_templates / sample


def test_project_mission_keeps_its_own_templates_dir(tmp_path: Path) -> None:
    project_mission = tmp_path / ".kittify" / "missions" / "research"
    project_mission.mkdir(parents=True)
    (project_mission / "mission.yaml").write_bytes((FROZEN_ROOT / "research" / "mission.yaml").read_bytes())

    assert Mission(project_mission).templates_dir == project_mission / "templates"


def test_init_fallback_never_seeds_the_frozen_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When the packs root is missing, ``init`` must not fall back to the frozen fork."""
    from charter.missions import MissionsRootNotFound, MissionTemplateRepository

    from specify_cli.template.manager import copy_specify_base_from_package

    def _missing() -> Path:
        raise MissionsRootNotFound("packs missing")

    monkeypatch.setattr(MissionTemplateRepository, "default_missions_root", staticmethod(_missing))
    project = tmp_path / "project"
    project.mkdir()

    copy_specify_base_from_package(project)

    assert not (project / ".kittify" / "missions" / "research" / "templates").exists()
    assert not (project / ".kittify" / "missions" / "documentation" / "templates").exists()
