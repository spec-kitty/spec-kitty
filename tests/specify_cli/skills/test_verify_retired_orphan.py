"""Verification reports a hash-clean retired managed skill, so the drain runs (#2460).

``ManagedSkillsProvider._delegate_repair`` returns early when verification is
``ok``. A copy-mode file of a skill the registry no longer ships, still equal to
its recorded hash, used to verify clean (the recorded hash stands in when the
registry has no canonical source), so the retirement drain in ``repair_skills``
never ran and the orphan lingered without a warning.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.skills.manifest import (
    ManagedFileEntry,
    ManagedSkillManifest,
    compute_content_hash,
    load_manifest,
    save_manifest,
)
from specify_cli.skills.registry import SkillRegistry
from specify_cli.skills.verifier import repair_skills, verify_installed_skills
from specify_cli.tool_surface.providers.managed_skills import ManagedSkillsProvider
from specify_cli.tool_surface.status import SurfaceStatus

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_RETIRED = "spk-team-sync"
_RETIRED_PATH = f".claude/skills/{_RETIRED}/SKILL.md"


def _registry(tmp_path: Path) -> SkillRegistry:
    skill = tmp_path / "_registry" / "kept-skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: kept-skill\ndescription: Kept.\n---\n# Kept\n", encoding="utf-8")
    return SkillRegistry(tmp_path / "_registry")


def _install_retired_copy(project: Path, body: str = "# Retired\n") -> ManagedFileEntry:
    dest = project / _RETIRED_PATH
    dest.parent.mkdir(parents=True)
    dest.write_text(body, encoding="utf-8")
    entry = ManagedFileEntry(
        skill_name=_RETIRED,
        source_file="SKILL.md",
        installed_path=_RETIRED_PATH,
        installation_class="native-root-required",
        agent_key="claude",
        content_hash=compute_content_hash(dest),
        installed_at="2026-01-01T00:00:00+00:00",
        delivery_mode="copy",
    )
    save_manifest(ManagedSkillManifest(entries=[entry]), project)
    return entry


@pytest.fixture
def registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SkillRegistry:
    registry = _registry(tmp_path)
    monkeypatch.setattr("specify_cli.skills.verifier._discover_registry", lambda project: registry)
    return registry


def test_hash_clean_retired_copy_is_reported(tmp_path: Path, registry: SkillRegistry) -> None:
    entry = _install_retired_copy(tmp_path)

    result = verify_installed_skills(tmp_path)

    assert not result.ok
    assert [item.installed_path for item in result.retired] == [entry.installed_path]


def test_reported_retired_copy_is_drained_by_repair(tmp_path: Path, registry: SkillRegistry) -> None:
    _install_retired_copy(tmp_path)

    repaired, failed = repair_skills(tmp_path, verify_installed_skills(tmp_path), registry)

    assert (repaired, failed) == (1, 0)
    assert not (tmp_path / _RETIRED_PATH).exists()
    manifest = load_manifest(tmp_path)
    assert manifest is not None and manifest.find_by_skill(_RETIRED) == []
    assert verify_installed_skills(tmp_path).ok


def test_provider_delegate_repair_runs_the_drain(tmp_path: Path, registry: SkillRegistry) -> None:
    _install_retired_copy(tmp_path)
    provider = ManagedSkillsProvider(registry_factory=lambda: registry)

    outcome = provider._delegate_repair(tmp_path, ("retired",), unmanifested=False)

    assert not outcome.failed, outcome.failed
    assert not (tmp_path / _RETIRED_PATH).exists()


def test_edited_retired_copy_is_never_deleted(tmp_path: Path, registry: SkillRegistry) -> None:
    _install_retired_copy(tmp_path)
    dest = tmp_path / _RETIRED_PATH
    dest.write_text("# Retired, with my edits\n", encoding="utf-8")

    result = verify_installed_skills(tmp_path)
    repair_skills(tmp_path, result, registry)

    assert dest.read_text(encoding="utf-8") == "# Retired, with my edits\n"
    assert not result.retired  # an edited file is drift (consent rules), not a clean retired copy


def test_empty_registry_reports_no_retirement(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    empty = SkillRegistry(tmp_path / "_none")
    monkeypatch.setattr("specify_cli.skills.verifier._discover_registry", lambda project: empty)
    _install_retired_copy(tmp_path)

    result = verify_installed_skills(tmp_path)

    assert result.ok and not result.retired


def test_clean_install_verifies_ok(tmp_path: Path, registry: SkillRegistry) -> None:
    save_manifest(ManagedSkillManifest(entries=[]), tmp_path)
    result = verify_installed_skills(tmp_path)
    assert result.ok and not result.retired


def test_provider_probe_reports_retired_entry_as_stale_and_repair_drains_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The production repair path (no legacy collaborators) acts only on actionable
    statuses, so the retired entry must probe as actionable for the drain to run."""
    from specify_cli.tool_surface.providers.managed_skills import managed_skill_definition
    from specify_cli.tool_surface.status import STATE_STALE

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home / ".kittify"))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    project = tmp_path / "project"
    project.mkdir()
    registry = _registry(tmp_path)
    _install_retired_copy(project)
    provider = ManagedSkillsProvider(registry_factory=lambda: registry)

    instances = provider.expand(managed_skill_definition(), "claude", project)
    statuses = [provider.probe(instance) for instance in instances]
    retired = [s for s in statuses if s.instance.path == project / _RETIRED_PATH]

    assert [s.state for s in retired] == [STATE_STALE]
    assert retired[0].findings and "retired" in retired[0].findings[0].message.lower()

    outcome = provider.repair(project, statuses)

    assert not outcome.failed, outcome.failed
    assert not (project / _RETIRED_PATH).exists()


def test_skill_absent_from_catalog_but_not_retired_is_not_reported(tmp_path: Path, registry: SkillRegistry) -> None:
    """Absence alone is not retirement: only a name Spec Kitty retired is drained."""
    dest = tmp_path / ".claude/skills/someone-elses-skill/SKILL.md"
    dest.parent.mkdir(parents=True)
    dest.write_text("# Theirs\n", encoding="utf-8")
    entry = ManagedFileEntry(
        skill_name="someone-elses-skill",
        source_file="SKILL.md",
        installed_path=".claude/skills/someone-elses-skill/SKILL.md",
        installation_class="native-root-required",
        agent_key="claude",
        content_hash=compute_content_hash(dest),
        installed_at="2026-01-01T00:00:00+00:00",
        delivery_mode="copy",
    )
    save_manifest(ManagedSkillManifest(entries=[entry]), tmp_path)

    result = verify_installed_skills(tmp_path)

    assert result.ok and not result.retired


def _provider_statuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, edit: bool) -> tuple[ManagedSkillsProvider, Path, list[SurfaceStatus]]:
    from specify_cli.tool_surface.providers.managed_skills import managed_skill_definition

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home / ".kittify"))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    project = tmp_path / "project"
    project.mkdir()
    registry = _registry(tmp_path)
    _install_retired_copy(project)
    if edit:
        (project / _RETIRED_PATH).write_text("# Retired, with my edits\n", encoding="utf-8")
    provider = ManagedSkillsProvider(registry_factory=lambda: registry)
    instances = provider.expand(managed_skill_definition(), "claude", project)
    return provider, project, [provider.probe(instance) for instance in instances]


def test_provider_probe_reports_edited_retired_copy_as_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An edited retired copy is drift, which needs consent: never the auto-drained STALE state."""
    from specify_cli.tool_surface.status import STATE_DRIFTED

    _, project, statuses = _provider_statuses(tmp_path, monkeypatch, edit=True)
    retired = [s for s in statuses if s.instance.path == project / _RETIRED_PATH]

    assert [s.state for s in retired] == [STATE_DRIFTED]
    assert "still installed" not in retired[0].findings[0].message


def test_retired_marks_do_not_outlive_their_manifest_entry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A re-expansion after the retired entry left the manifest must not report it as retired."""
    from specify_cli.tool_surface.providers.managed_skills import managed_skill_definition

    provider, project, _ = _provider_statuses(tmp_path, monkeypatch, edit=False)
    save_manifest(ManagedSkillManifest(entries=[]), project)

    provider.expand(managed_skill_definition(), "claude", project)

    assert not any(".spk-team-sync." in surface_id for surface_id in provider._retired_surface_ids)
