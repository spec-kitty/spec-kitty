"""Tests for the 4.0.0rc8 stale mission template fork retirement (#5280).

The stale content these tests plant is the real frozen fork under
``src/specify_cli/missions/<type>/templates/`` (the bytes the shipped
``0.9.2`` / ``0.12.0`` migrations copy today), and the expected replacement is
the real packs copy from ``get_package_asset_root()``.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import specify_cli
from specify_cli.runtime.home import get_package_asset_root
from specify_cli.runtime.resolver import ResolutionTier, resolve_template
from specify_cli.upgrade.migrations import m_4_0_0rc8_retire_stale_mission_template_forks as module
from specify_cli.upgrade.migrations.m_0_9_2_research_mission_templates import ResearchMissionTemplatesMigration
from specify_cli.upgrade.migrations.m_0_12_0_documentation_mission import InstallDocumentationMission
from specify_cli.upgrade.migrations.m_4_0_0rc8_retire_stale_mission_template_forks import (
    RetireStaleMissionTemplateForksMigration,
    kept_warning,
    skipped_tree_warning,
)

pytestmark = pytest.mark.fast

FROZEN_ROOT = Path(specify_cli.__file__).parent / "missions"
TASK_PROMPT = "task-prompt-template.md"


def _fork(mission_type: str, rel: str) -> bytes:
    return (FROZEN_ROOT / mission_type / "templates" / rel).read_bytes()


def _pack(mission_type: str, rel: str) -> bytes:
    return (get_package_asset_root() / mission_type / "templates" / rel).read_bytes()


def _plant(project: Path, tree: str, mission_type: str, rel: str, content: bytes) -> Path:
    path = project / ".kittify" / tree / mission_type / "templates" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    # An empty global home, so resolution falls through to the package tier.
    monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path / "empty-global-home"))
    monkeypatch.delenv("SPEC_KITTY_TEMPLATE_ROOT", raising=False)
    root = tmp_path / "project"
    (root / ".kittify").mkdir(parents=True)
    return root


@pytest.mark.parametrize("eol", [b"\n", b"\r\n"], ids=["lf", "crlf-checkout"])
def test_overrides_stale_copy_is_removed_and_pack_copy_resolves(project: Path, eol: bytes) -> None:
    stale = _plant(project, "overrides/missions", "research", TASK_PROMPT, _fork("research", TASK_PROMPT).replace(b"\n", eol))
    assert resolve_template(TASK_PROMPT, project, "research").tier is ResolutionTier.OVERRIDE

    migration = RetireStaleMissionTemplateForksMigration()
    assert migration.detect(project) is True
    result = migration.apply(project)

    assert result.success, result.errors
    assert not stale.exists()
    assert stale.parent.is_dir(), "directories are never removed"
    resolved = resolve_template(TASK_PROMPT, project, "research")
    assert resolved.tier is ResolutionTier.PACKAGE_DEFAULT
    assert resolved.path.read_bytes() == _pack("research", TASK_PROMPT)


def test_legacy_tree_stale_copy_is_replaced_with_pack_copy(project: Path) -> None:
    research = _plant(project, "missions", "research", TASK_PROMPT, _fork("research", TASK_PROMPT))
    divio = _plant(
        project,
        "missions",
        "documentation",
        "divio/tutorial-template.md",
        _fork("documentation", "divio/tutorial-template.md"),
    )

    result = RetireStaleMissionTemplateForksMigration().apply(project)

    assert result.success, result.errors
    assert research.read_bytes() == _pack("research", TASK_PROMPT)
    assert divio.read_bytes() == _pack("documentation", "divio/tutorial-template.md")
    assert len(result.changes_made) == 2
    assert all(change.startswith("Replaced stale .kittify/missions/") for change in result.changes_made)


def test_replacing_keeps_the_0_9_2_migration_quiet(project: Path) -> None:
    """Removing the research task prompt would re-arm 0.9.2, which would copy the fork back."""
    _plant(project, "missions", "research", TASK_PROMPT, _fork("research", TASK_PROMPT))

    RetireStaleMissionTemplateForksMigration().apply(project)

    assert ResearchMissionTemplatesMigration().detect(project) is False


@pytest.mark.parametrize("mission_type", ["documentation", "research"])
@pytest.mark.parametrize("name", ["plan-template.md", "spec-template.md"])
def test_fork_only_stale_copy_is_removed_in_both_trees(project: Path, mission_type: str, name: str) -> None:
    legacy = _plant(project, "missions", mission_type, name, _fork(mission_type, name))
    override = _plant(project, "overrides/missions", mission_type, name, _fork(mission_type, name))

    result = RetireStaleMissionTemplateForksMigration().apply(project)

    assert result.success, result.errors
    assert not legacy.exists()
    assert not override.exists()


@pytest.mark.parametrize("tree", ["missions", "overrides/missions"])
def test_hand_edited_copy_is_kept_with_a_warning_naming_it(project: Path, tree: str) -> None:
    edited = _fork("research", TASK_PROMPT) + b"\nOur team's extra step.\n"
    path = _plant(project, tree, "research", TASK_PROMPT, edited)
    migration = RetireStaleMissionTemplateForksMigration()

    assert migration.detect(project) is True
    result = migration.apply(project)

    assert result.success
    assert path.read_bytes() == edited
    rel = f".kittify/{tree}/research/templates/{TASK_PROMPT}"
    assert result.warnings == [kept_warning(rel)]
    assert result.changes_made == []


def test_unrelated_files_are_never_touched(project: Path) -> None:
    own = _plant(project, "overrides/missions", "research", "my-own-template.md", b"mine\n")
    readme = _plant(project, "missions", "documentation", "README.md", _fork("research", TASK_PROMPT))

    migration = RetireStaleMissionTemplateForksMigration()
    assert migration.detect(project) is False
    migration.apply(project)

    assert own.read_bytes() == b"mine\n"
    assert readme.exists()


def test_pack_identical_copy_is_left_alone_silently(project: Path) -> None:
    current = _plant(project, "overrides/missions", "research", TASK_PROMPT, _pack("research", TASK_PROMPT))
    migration = RetireStaleMissionTemplateForksMigration()

    assert migration.detect(project) is False
    result = migration.apply(project)

    assert current.exists()
    assert result.changes_made == [] and result.warnings == []


def test_second_run_is_a_no_op(project: Path) -> None:
    _plant(project, "missions", "research", TASK_PROMPT, _fork("research", TASK_PROMPT))
    _plant(project, "overrides/missions", "documentation", TASK_PROMPT, _fork("documentation", TASK_PROMPT))
    migration = RetireStaleMissionTemplateForksMigration()
    migration.apply(project)

    assert migration.detect(project) is False
    again = migration.apply(project)
    assert again.success and again.changes_made == [] and again.warnings == []


def test_dry_run_changes_nothing(project: Path) -> None:
    legacy = _plant(project, "missions", "research", TASK_PROMPT, _fork("research", TASK_PROMPT))
    override = _plant(project, "overrides/missions", "research", TASK_PROMPT, _fork("research", TASK_PROMPT))

    result = RetireStaleMissionTemplateForksMigration().apply(project, dry_run=True)

    assert result.success
    assert legacy.read_bytes() == _fork("research", TASK_PROMPT)
    assert override.exists()
    assert sorted(result.changes_made) == [
        f"Would remove package-owned .kittify/overrides/missions/research/templates/{TASK_PROMPT} (proof: canonical_content)",
        f"Would replace stale .kittify/missions/research/templates/{TASK_PROMPT} with the shipped template",
    ]


def test_absent_trees_detect_false_and_create_nothing(project: Path) -> None:
    migration = RetireStaleMissionTemplateForksMigration()

    assert migration.detect(project) is False
    result = migration.apply(project)

    assert result.success
    assert sorted(p.name for p in (project / ".kittify").iterdir()) == []


@pytest.mark.skipif(os.name == "nt", reason="symlink creation needs privileges on Windows")
def test_symlinked_tree_is_refused_and_left_untouched(project: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    target = outside / "missions" / "research" / "templates" / TASK_PROMPT
    target.parent.mkdir(parents=True)
    target.write_bytes(_fork("research", TASK_PROMPT))
    (project / ".kittify" / "overrides").symlink_to(outside, target_is_directory=True)
    migration = RetireStaleMissionTemplateForksMigration()

    assert migration.detect(project) is True
    result = migration.apply(project)

    assert result.success
    assert target.exists()
    assert result.warnings == [skipped_tree_warning(".kittify/overrides")]


@pytest.mark.skipif(os.name == "nt", reason="symlink creation needs privileges on Windows")
def test_symlinked_template_file_is_kept(project: Path, tmp_path: Path) -> None:
    real = tmp_path / "real.md"
    real.write_bytes(_fork("research", TASK_PROMPT))
    link = project / ".kittify" / "overrides" / "missions" / "research" / "templates" / TASK_PROMPT
    link.parent.mkdir(parents=True)
    link.symlink_to(real)

    result = RetireStaleMissionTemplateForksMigration().apply(project)

    assert link.is_symlink() and real.exists()
    assert result.warnings == [kept_warning(f".kittify/overrides/missions/research/templates/{TASK_PROMPT}")]


def test_write_failure_is_reported_as_an_error(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _plant(project, "missions", "research", TASK_PROMPT, _fork("research", TASK_PROMPT))

    def _boom(path: Path, content: bytes) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(module, "atomic_write", _boom)
    result = RetireStaleMissionTemplateForksMigration().apply(project)

    assert result.success is False
    assert result.errors == [f"Could not repair .kittify/missions/research/templates/{TASK_PROMPT}: disk full"]


def test_missing_shipped_templates_detects_work_and_refuses(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _plant(project, "missions", "research", TASK_PROMPT, _fork("research", TASK_PROMPT))

    def _missing() -> Path:
        raise FileNotFoundError("no packs")

    monkeypatch.setattr(module, "get_package_asset_root", _missing)
    migration = RetireStaleMissionTemplateForksMigration()

    assert migration.detect(project) is True
    can_apply, reason = migration.can_apply(project)
    assert can_apply is False
    assert "no packs" in reason


def test_can_apply_with_shipped_templates(project: Path) -> None:
    assert RetireStaleMissionTemplateForksMigration().can_apply(project) == (True, "")


def _run_shipped_fork_writers(project: Path) -> Path:
    """Run the real 0.12.0 and 0.9.2 migrations on a pre-2.x project; return its research mission dir."""
    research_mission = project / ".kittify" / "missions" / "research"
    research_mission.mkdir(parents=True)
    (research_mission / "mission.yaml").write_bytes((get_package_asset_root() / "research" / "mission.yaml").read_bytes())
    for shipped in (InstallDocumentationMission(), ResearchMissionTemplatesMigration()):
        assert shipped.detect(project) is True
        assert shipped.can_apply(project) == (True, "")
        assert shipped.apply(project).success
    assert (research_mission / "templates" / TASK_PROMPT).read_bytes() == _fork("research", TASK_PROMPT)
    return research_mission


def _overrides(project: Path) -> list[str]:
    root = project / ".kittify" / "overrides"
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()) if root.exists() else []


def test_upgrade_chain_of_shipped_migrations_then_repair_resolves_pack_copies(project: Path) -> None:
    """The real upgrade chain, end to end (#5280 10-20 evidence, #6548).

    0.12.0 copies the documentation fork into a pre-2.x project and 0.9.2 adds
    the research task prompt fork. The 2.0.6 runtime-asset move used to put
    those copies into ``overrides/``, where they won; it now compares a project
    mission copy with the package mission, so it removes the pack-identical
    files and leaves the differing forks in place, where no resolver tier
    serves them (only the fork-only names, which have no package counterpart,
    still move). The repair then replaces or removes them, and a later
    ``spec-kitty migrate`` never moves the pack copies into ``overrides/``.
    """
    from specify_cli.runtime.migrate import execute_migration

    _run_shipped_fork_writers(project)
    execute_migration(project)
    # Only the fork-only names (0.12.0 copied them; 0.9.2 copies none), which
    # have no package counterpart, still move.
    assert _overrides(project) == [
        "missions/documentation/templates/plan-template.md",
        "missions/documentation/templates/spec-template.md",
    ]

    repair = RetireStaleMissionTemplateForksMigration()
    assert repair.detect(project) is True
    result = repair.apply(project)
    assert result.success, result.errors
    assert result.warnings == []
    assert repair.detect(project) is False

    execute_migration(project)  # e.g. ``spec-kitty migrate`` after ``doctor`` suggests it
    assert _overrides(project) == []
    for mission_type in ("documentation", "research"):
        resolved = resolve_template(TASK_PROMPT, project, mission_type)
        assert resolved.tier is ResolutionTier.PACKAGE_DEFAULT
        assert resolved.path.read_bytes() == _pack(mission_type, TASK_PROMPT), resolved


def test_project_upgraded_by_an_older_build_resolves_pack_copies_after_repair(project: Path) -> None:
    """An older build's 2.0.6 move left the forks in ``overrides/`` (the 10-20 reproduction)."""
    research_mission = _run_shipped_fork_writers(project)
    documentation_templates = project / ".kittify" / "missions" / "documentation" / "templates"
    for templates_dir, mission_type in ((documentation_templates, "documentation"), (research_mission / "templates", "research")):
        for path in sorted(p for p in templates_dir.rglob("*.md")):
            dest = project / ".kittify" / "overrides" / "missions" / mission_type / "templates" / path.relative_to(templates_dir)
            dest.parent.mkdir(parents=True, exist_ok=True)
            path.rename(dest)
    for mission_type in ("documentation", "research"):
        before = resolve_template(TASK_PROMPT, project, mission_type)
        assert before.tier is ResolutionTier.OVERRIDE, "the reproduction: the fork wins at tier 1"
        assert before.path.read_bytes() == _fork(mission_type, TASK_PROMPT)

    result = RetireStaleMissionTemplateForksMigration().apply(project)

    assert result.success, result.errors
    assert result.warnings == []
    assert [rel for rel in _overrides(project) if rel.endswith(".md")] == []
    for mission_type in ("documentation", "research"):
        resolved = resolve_template(TASK_PROMPT, project, mission_type)
        assert resolved.path.read_bytes() == _pack(mission_type, TASK_PROMPT), resolved


def test_unreadable_file_fails_closed(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A read error never proves a file stale, and never calls it current."""
    path = _plant(project, "overrides/missions", "research", TASK_PROMPT, _fork("research", TASK_PROMPT))
    original = Path.read_bytes

    def _read_bytes(self: Path) -> bytes:
        if self == path:
            raise OSError("permission denied")
        return original(self)

    monkeypatch.setattr(Path, "read_bytes", _read_bytes)
    candidate = module._Candidate(path=path, key=f"research/{TASK_PROMPT}", in_overrides=True)

    assert module._KnownForkProver(candidate.key).prove(path, project) is None
    assert module._is_current(candidate, get_package_asset_root() / "research" / "templates" / TASK_PROMPT) is False


def test_rel_falls_back_to_the_absolute_path_outside_the_project(tmp_path: Path) -> None:
    outside = tmp_path / "elsewhere" / "file.md"

    assert module._rel(outside, tmp_path / "project") == str(outside)
