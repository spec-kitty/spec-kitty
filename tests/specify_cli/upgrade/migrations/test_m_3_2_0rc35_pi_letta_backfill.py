"""Integration tests for the 3.2.0rc350 Pi/Letta gitignore and skill backfill migration.

All tests operate on real filesystem paths via ``tmp_path``.  Installer calls
that would require a full package wheel are patched with ``unittest.mock`` so
the migration logic can be verified without a live package dependency.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from specify_cli.gitignore_manager import GitignorePathError
from specify_cli.skills import command_installer, manifest_store
from specify_cli.skills.command_installer import CANONICAL_COMMANDS
from specify_cli.upgrade.migrations.m_3_2_0rc35_pi_letta_backfill import (
    PiLettaBackfillMigration,
)

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_project(
    tmp_path: Path,
    agents: list[str],
    gitignore_lines: list[str] | None = None,
    install_skills: bool = False,
) -> Path:
    """Create a minimal kittify project tree in *tmp_path*."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True)

    # Write config.yaml
    config_yaml = kittify / "config.yaml"
    available = "\n".join(f"    - {a}" for a in agents)
    config_yaml.write_text(
        f"agents:\n  available:\n{available}\n",
        encoding="utf-8",
    )

    # Optionally write .gitignore
    if gitignore_lines is not None:
        (tmp_path / ".gitignore").write_text(
            "\n".join(gitignore_lines) + "\n",
            encoding="utf-8",
        )

    # Optionally pre-install skill files
    if install_skills:
        for cmd in CANONICAL_COMMANDS:
            skill_file = (
                tmp_path / ".agents" / "skills" / f"spec-kitty.{cmd}" / "SKILL.md"
            )
            skill_file.parent.mkdir(parents=True, exist_ok=True)
            skill_file.write_text(f"# skill: {cmd}\n", encoding="utf-8")

    return tmp_path


#: #6475: this shipped migration is frozen (DIRECTIVE_044) and its detect() still reads the
#: pre-rename dotted layout, while the installer it calls now writes ``spec-kitty-<cmd>``. So a
#: re-run repeats the idempotent install; ledger selection never re-runs it on a project it has
#: settled. Tests that need "skills present" seed the layout of the migration's own era.
_ERA_NOTE = "frozen migration reads the pre-#6475 dotted layout"


def _seed_dotted_layout(project: Path, agents: tuple[str, ...]) -> None:
    """Lay out the dotted skills and manifest a pre-#6475 release recorded."""
    entries = []
    for cmd in CANONICAL_COMMANDS:
        rel = f".agents/skills/spec-kitty.{cmd}/SKILL.md"
        path = project / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# skill: {cmd}\n", encoding="utf-8")
        entries.append(manifest_store.ManifestEntry(rel, manifest_store.fingerprint_file(path), agents, "2026-01-01T00:00:00+00:00", "3.2.0"))
    manifest_store.save(project, manifest_store.SkillsManifest(entries=entries))


# ---------------------------------------------------------------------------
# Gitignore tests
# ---------------------------------------------------------------------------


def test_adds_pi_gitignore_when_configured(tmp_path: Path) -> None:
    """Migration adds .pi/ to .gitignore when pi is configured and entry missing."""
    project = _make_project(tmp_path, agents=["pi"], install_skills=True)

    migration = PiLettaBackfillMigration()
    result = migration.apply(project)

    assert result.success
    gitignore_text = (project / ".gitignore").read_text(encoding="utf-8")
    assert ".pi/" in gitignore_text
    assert any(".pi/" in change for change in result.changes_made)


def test_adds_letta_gitignore_when_configured(tmp_path: Path) -> None:
    """Migration adds .letta/ to .gitignore when letta is configured and entry missing."""
    project = _make_project(tmp_path, agents=["letta"], install_skills=True)

    migration = PiLettaBackfillMigration()
    result = migration.apply(project)

    assert result.success
    gitignore_text = (project / ".gitignore").read_text(encoding="utf-8")
    assert ".letta/" in gitignore_text
    assert any(".letta/" in change for change in result.changes_made)


def test_skips_gitignore_if_already_present(tmp_path: Path) -> None:
    """Migration does not duplicate an existing .pi/ entry."""
    project = _make_project(
        tmp_path, agents=["pi"], gitignore_lines=[".pi/"], install_skills=True
    )

    migration = PiLettaBackfillMigration()
    result = migration.apply(project)

    assert result.success
    gitignore_text = (project / ".gitignore").read_text(encoding="utf-8")
    assert gitignore_text.count(".pi/") == 1
    # No gitignore change reported
    assert not any(".pi/" in change and "Added" in change for change in result.changes_made)


def test_detect_rejects_symlinked_gitignore(tmp_path: Path) -> None:
    """detect() must not follow a .gitignore that is a symlink (issue #626)."""
    project = _make_project(tmp_path, agents=["pi"], install_skills=True)
    outside_target = tmp_path.parent / f"outside-target-{os.getpid()}.txt"
    outside_target.write_text("do-not-touch\n")
    (project / ".gitignore").symlink_to(outside_target)

    migration = PiLettaBackfillMigration()
    try:
        with pytest.raises(GitignorePathError):
            migration.detect(project)
    finally:
        outside_target.unlink(missing_ok=True)


def test_skips_unconfigured_agent(tmp_path: Path) -> None:
    """Migration leaves .gitignore untouched for agents not in config."""
    project = _make_project(tmp_path, agents=["claude"], install_skills=True)
    # .gitignore does not exist yet
    assert not (project / ".gitignore").exists()

    migration = PiLettaBackfillMigration()
    result = migration.apply(project)

    assert result.success
    # Nothing written (no pi/letta configured)
    assert not (project / ".gitignore").exists() or (
        ".pi/" not in (project / ".gitignore").read_text(encoding="utf-8")
        and ".letta/" not in (project / ".gitignore").read_text(encoding="utf-8")
    )
    assert result.changes_made == []


def test_dry_run_does_not_mutate(tmp_path: Path) -> None:
    """dry_run=True reports changes without writing to disk."""
    project = _make_project(tmp_path, agents=["pi"], install_skills=True)

    migration = PiLettaBackfillMigration()
    result = migration.apply(project, dry_run=True)

    assert result.success
    # .gitignore must NOT have been created/written
    gitignore_path = project / ".gitignore"
    assert not gitignore_path.exists() or ".pi/" not in gitignore_path.read_text(
        encoding="utf-8"
    )
    # But a "Would add" change is reported
    assert any("Would add" in change for change in result.changes_made)


def test_idempotent(tmp_path: Path) -> None:
    """Running the migration twice produces no duplicate gitignore entries."""
    project = _make_project(tmp_path, agents=["pi", "letta"], install_skills=True)

    migration = PiLettaBackfillMigration()
    first = migration.apply(project)
    second = migration.apply(project)

    assert first.success
    assert second.success
    # The gitignore backfill is idempotent; the skill repair repeats (see _ERA_NOTE).
    assert not any(".gitignore" in change for change in second.changes_made), _ERA_NOTE

    gitignore_text = (project / ".gitignore").read_text(encoding="utf-8")
    assert gitignore_text.count(".pi/") == 1
    assert gitignore_text.count(".letta/") == 1


# ---------------------------------------------------------------------------
# Skill repair tests
# ---------------------------------------------------------------------------


def test_skill_repair_triggered_when_skills_missing(tmp_path: Path) -> None:
    """Installer is called when skill files are absent for a configured pi agent."""
    project = _make_project(
        tmp_path, agents=["pi"], gitignore_lines=[".pi/"], install_skills=False
    )

    with patch(
        "specify_cli.skills.command_installer.install"
    ) as mock_install:
        mock_install.return_value = MagicMock()
        migration = PiLettaBackfillMigration()
        result = migration.apply(project)

    assert result.success
    mock_install.assert_called_once_with(project, "pi")
    assert any("Repaired skill pack" in change for change in result.changes_made)


def test_no_skill_repair_when_skills_present(tmp_path: Path) -> None:
    """Installer is NOT called when skill files and manifest ownership are present."""
    project = _make_project(
        tmp_path,
        agents=["pi"],
        gitignore_lines=[".pi/"],
        install_skills=False,
    )
    _seed_dotted_layout(project, ("pi",))

    with patch(
        "specify_cli.skills.command_installer.install"
    ) as mock_install:
        migration = PiLettaBackfillMigration()
        result = migration.apply(project)

    assert result.success
    mock_install.assert_not_called()
    assert result.changes_made == []


def test_repairs_manifest_ownership_for_both_pi_and_letta(tmp_path: Path) -> None:
    """Both configured agents must be recorded as command-skill owners."""
    project = _make_project(
        tmp_path,
        agents=["pi", "letta"],
        gitignore_lines=[".pi/", ".letta/"],
        install_skills=False,
    )

    migration = PiLettaBackfillMigration()
    assert migration.detect(project)

    result = migration.apply(project)

    assert result.success
    manifest = manifest_store.load(project)
    assert len(manifest.entries) == len(CANONICAL_COMMANDS)
    for entry in manifest.entries:
        assert entry.agents == ("letta", "pi")
    # detect() stays true after the rename (see _ERA_NOTE); ownership is what this pins.


def test_repairs_manifest_ownership_when_shared_skills_already_exist(
    tmp_path: Path,
) -> None:
    """Existing shared skills are incomplete until Pi/Letta own manifest entries."""
    project = _make_project(
        tmp_path,
        agents=["pi", "letta"],
        gitignore_lines=[".pi/", ".letta/"],
        install_skills=False,
    )
    command_installer.install(project, "codex")

    migration = PiLettaBackfillMigration()
    assert migration.detect(project)

    result = migration.apply(project)

    assert result.success
    manifest = manifest_store.load(project)
    for entry in manifest.entries:
        assert entry.agents == ("codex", "letta", "pi")
    # detect() stays true after the rename (see _ERA_NOTE); ownership is what this pins.


def test_6155_backfill_names_regenerated_shared_skill_in_changes(tmp_path: Path) -> None:
    """#6155: the Pi/Letta skill backfill reinstalls over the shared root, which regenerates a
    drifted shared projection; the migration names that path once in ``changes_made``."""
    from specify_cli.tool_surface.repair import REGENERATED_SURFACE_LINE

    project = _make_project(tmp_path, agents=["pi", "letta"], gitignore_lines=[".pi/", ".letta/"])
    command_installer.install(project, "codex")
    drifted = project / ".agents" / "skills" / "spec-kitty-plan" / "SKILL.md"
    drifted.write_bytes(drifted.read_bytes() + b"\n<!-- stale output from another checkout -->\n")
    rel = drifted.relative_to(project).as_posix()

    result = PiLettaBackfillMigration().apply(project)

    assert result.success, result.errors
    assert result.changes_made.count(REGENERATED_SURFACE_LINE.format(path=rel)) == 1, result.changes_made
