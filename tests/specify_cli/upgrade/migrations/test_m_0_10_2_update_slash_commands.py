"""Ownership-boundary tests for the m_0_10_2 legacy command TOML sweep (WP06).

The migration's ``apply()`` sweeps ``.kittify/commands/*.toml`` while migrating
slash commands to the flat structure. Before WP06 the sweep unlinked every
``.toml`` unconditionally — a name/directory-based delete that destroyed
user-authored command TOMLs. These tests pin BOTH directions the
asset-preservation guard must honour (contract C4 US4; data-model census row 4):

* a user-authored ``.kittify/commands/custom.toml`` with no command-skills
  manifest entry and no version marker SURVIVES + a preservation diagnostic
  (RED on base ``32cfc272ee`` — the unconditional ``unlink`` deletes it); and
* a genuinely package-owned ``.toml`` carrying the
  ``<!-- spec-kitty-command-version:`` marker is STILL removed (non-vacuity
  anchor, GREEN on base since base deletes everything).

The command-skills manifest cannot be the operative signal for this site: its
schema restricts every entry ``path`` to
``.agents/skills/spec-kitty.<cmd>/SKILL.md``, so a legacy
``.kittify/commands/*.toml`` can never carry a manifest entry. The
manifest-first ``AnyProver`` ordering is still correct (a cheap exact-path
lookup first), but for a ``.toml`` it always falls through to the whole-file
marker scan.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.upgrade.migrations.m_0_10_2_update_slash_commands import (
    UpdateSlashCommandsMigration,
)

pytestmark = [pytest.mark.fast]

_MARKER = "<!-- spec-kitty-command-version: 1.0 -->"


def _seed_mission_templates(project_path: Path) -> None:
    """Create the mission command-templates dir so ``apply()`` reaches the sweep.

    ``apply()`` returns early with an error before the ``.kittify/commands``
    sweep when no mission command-templates directory exists; seeding an (empty)
    one lets the sweep run with ``total_updated == 0``.
    """
    templates = project_path / ".kittify" / "missions" / "software-dev" / "command-templates"
    templates.mkdir(parents=True, exist_ok=True)


def _write_command_toml(project_path: Path, name: str, body: str) -> Path:
    commands_dir = project_path / ".kittify" / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)
    toml_file = commands_dir / name
    toml_file.write_text(body, encoding="utf-8")
    return toml_file


def test_apply_preserves_user_authored_command_toml(tmp_path: Path) -> None:
    """A user ``.toml`` with no manifest entry and no marker SURVIVES + diagnostic.

    RED on base ``32cfc272ee`` (the unconditional ``toml_file.unlink()`` deletes
    it); GREEN once the sweep routes through the asset-preservation guard.
    """
    _seed_mission_templates(tmp_path)
    user_body = 'prompt = """\nMy own custom command; not shipped by Spec Kitty.\n"""\n'
    custom = _write_command_toml(tmp_path, "custom.toml", user_body)

    result = UpdateSlashCommandsMigration().apply(tmp_path)

    assert result.success is True
    assert custom.is_file(), "user-authored command TOML must be preserved"
    assert custom.read_text(encoding="utf-8") == user_body, "preserved bytes must be verbatim"
    # The commands dir survives because it still holds the preserved file.
    assert (tmp_path / ".kittify" / "commands").is_dir()
    assert any("custom.toml" in warning and "Preserved" in warning for warning in result.warnings), (
        f"a preservation diagnostic must name the survivor; warnings={result.warnings}"
    )


def test_apply_dry_run_preserves_user_authored_command_toml(tmp_path: Path) -> None:
    """Dry-run never mutates and still reports the preservation decision."""
    _seed_mission_templates(tmp_path)
    user_body = 'prompt = """\nAnother user command.\n"""\n'
    custom = _write_command_toml(tmp_path, "custom.toml", user_body)

    result = UpdateSlashCommandsMigration().apply(tmp_path, dry_run=True)

    assert result.success is True
    assert custom.is_file()
    assert not any("Removed legacy custom.toml" in change for change in result.changes_made)


def test_apply_removes_marker_bearing_command_toml(tmp_path: Path) -> None:
    """A ``.toml`` carrying the version marker (past a 15-line head) IS removed.

    Non-vacuity anchor via ``CanonicalContentProver`` (whole-file scan): a
    preserve-everything guard would leave this file and fail the assertion.
    """
    _seed_mission_templates(tmp_path)
    head = "\n".join(f"# filler line {index}" for index in range(20))
    owned_body = f'prompt = """\n{head}\n{_MARKER}\nGenerated command body.\n"""\n'
    owned = _write_command_toml(tmp_path, "specify.toml", owned_body)

    result = UpdateSlashCommandsMigration().apply(tmp_path)

    assert result.success is True
    assert not owned.exists(), "marker-bearing (package-owned) TOML must be removed"
    assert any("Removed legacy specify.toml" in change for change in result.changes_made)
    # Sole occupant removed ⇒ the empty commands dir is torn down too.
    assert not (tmp_path / ".kittify" / "commands").exists()


def test_apply_mixed_owned_and_user_command_tomls(tmp_path: Path) -> None:
    """Both directions in one sweep: owned removed, user preserved."""
    _seed_mission_templates(tmp_path)
    owned_body = f'prompt = """\n{_MARKER}\nshipped.\n"""\n'
    owned = _write_command_toml(tmp_path, "tasks.toml", owned_body)
    user_body = 'prompt = """\nkeep me.\n"""\n'
    custom = _write_command_toml(tmp_path, "custom.toml", user_body)

    result = UpdateSlashCommandsMigration().apply(tmp_path)

    assert result.success is True
    assert not owned.exists()
    assert custom.is_file()
    assert custom.read_text(encoding="utf-8") == user_body
    # A survivor remains ⇒ the commands dir is NOT torn down.
    assert (tmp_path / ".kittify" / "commands").is_dir()


# ---------------------------------------------------------------------------
# #6247 fold: the canonical-command OVERWRITE path is ownership-gated too.
#
# apply() writes each mission template over spec-kitty.<stem>.md in every agent
# dir. Before this fold it overwrote unconditionally (a canonical-name write with
# no ownership proof), clobbering a user's hand-edits to a canonical command.
# ---------------------------------------------------------------------------

_TEMPLATE_BODY = "# specify\nUpdated template body from the mission.\n"


def _seed_template(project_path: Path, stem: str, body: str) -> None:
    templates = project_path / ".kittify" / "missions" / "software-dev" / "command-templates"
    templates.mkdir(parents=True, exist_ok=True)
    (templates / f"{stem}.md").write_text(body, encoding="utf-8")


def _seed_claude_agent(project_path: Path) -> Path:
    kittify = project_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text("agents:\n  available:\n  - claude\n", encoding="utf-8")
    cmd = project_path / ".claude" / "commands"
    cmd.mkdir(parents=True, exist_ok=True)
    return cmd


def test_apply_preserves_user_authored_canonical_command(tmp_path: Path) -> None:
    """#6247: a user's own spec-kitty.<cmd>.md (no marker) is not clobbered by the template.

    RED on base (the unconditional ``write_generated_file`` overwrites it);
    GREEN once the overwrite routes through ``guard_destructive_overwrite``.
    """
    _seed_template(tmp_path, "specify", _TEMPLATE_BODY)
    cmd = _seed_claude_agent(tmp_path)
    user_cmd = cmd / "spec-kitty.specify.md"
    user_body = "# my own specify\nhand written, no version marker\n"
    user_cmd.write_text(user_body, encoding="utf-8")

    result = UpdateSlashCommandsMigration().apply(tmp_path)

    assert result.success is True
    assert user_cmd.read_text(encoding="utf-8") == user_body, "a user-authored canonical command must be preserved verbatim"
    assert any("spec-kitty.specify.md" in warning for warning in result.warnings)


def test_apply_overwrites_marker_bearing_canonical_command(tmp_path: Path) -> None:
    """A proven package-generated command IS updated with the template (non-vacuity)."""
    _seed_template(tmp_path, "specify", _TEMPLATE_BODY)
    cmd = _seed_claude_agent(tmp_path)
    owned = cmd / "spec-kitty.specify.md"
    owned.write_text(f"{_MARKER}\n# stale generated specify\n", encoding="utf-8")

    result = UpdateSlashCommandsMigration().apply(tmp_path)

    assert result.success is True
    assert owned.read_text(encoding="utf-8") == _TEMPLATE_BODY, "a generated command must be updated to the template"


def test_apply_creates_absent_canonical_command(tmp_path: Path) -> None:
    """An absent command is still created — the migration's populate behavior is intact."""
    _seed_template(tmp_path, "specify", _TEMPLATE_BODY)
    cmd = _seed_claude_agent(tmp_path)
    dest = cmd / "spec-kitty.specify.md"
    assert not dest.exists()

    result = UpdateSlashCommandsMigration().apply(tmp_path)

    assert result.success is True
    assert dest.read_text(encoding="utf-8") == _TEMPLATE_BODY
