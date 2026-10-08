from __future__ import annotations

import re
from pathlib import Path

import click
import pytest
from typer.main import get_command

from specify_cli import app
from specify_cli.skills.registry import SkillRegistry


pytestmark = [pytest.mark.doctrine, pytest.mark.fast]
REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_ROOT = REPO_ROOT / "src" / "charter" / "offering" / "skills"
SPK_SKILLS = {
    "spk-admin-agent-config",
    "spk-admin-git-workflow",
    "spk-admin-setup-doctor",
    "spk-admin-upgrade",
    "spk-charter-glossary",
    "spk-charter-governance",
    "spk-charter-profile-load",
    "spk-charter-spdd-reasons",
    "spk-gate-accept",
    "spk-gate-consolidate",
    "spk-gate-mission-review",
    "spk-gate-retrospective",
    "spk-integrate-orchestrator-api",
    "spk-meta-skill-authoring",
    "spk-meta-skill-map",
    "spk-mission-documentation",
    "spk-mission-plan",
    "spk-mission-research",
    "spk-mission-specify",
    "spk-mission-tasks",
    "spk-mission-types",
    "spk-practice-bulk-edit",
    "spk-practice-semantic-compression",
    "spk-practice-show-me",
    "spk-run-blocked-recovery",
    "spk-run-implement-review",
    "spk-run-next",
    "spk-run-program-orchestrate",
    "spk-run-review-wp",
    "spk-run-verdict-capture",
    "spk-start-agent-surface",
    "spk-start-command-map",
    "spk-start-first-feature",
    "spk-start-here",
    "spk-team-auth",
    "spk-team-connectors",
    "spk-team-sync",
    "spk-team-tracker",
}
LEGACY_ALIAS_SKILLS = {
    "spec-kitty-git-workflow",
    "spec-kitty-implement-review",
    "spec-kitty-mission-review",
    "spec-kitty-mission-system",
    "spec-kitty-orchestrator-api-operator",
    "spec-kitty-program-orchestrate",
    "spec-kitty-runtime-next",
    "spec-kitty-runtime-review",
    "spec-kitty-setup-doctor",
}


def _frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"^---\n(?P<body>.*?)\n---\n", text, re.DOTALL)
    assert match, "SKILL.md must start with a YAML frontmatter block"
    fields: dict[str, str] = {}
    for line in match.group("body").splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip().strip('"')
    return fields


def test_320_spk_skill_pack_is_complete() -> None:
    actual = {
        path.name
        for path in SKILLS_ROOT.iterdir()
        if path.is_dir() and path.name.startswith("spk-")
    }

    assert actual == SPK_SKILLS


def test_spk_skill_frontmatter_matches_directory_name() -> None:
    for skill_name in sorted(SPK_SKILLS):
        skill_md = SKILLS_ROOT / skill_name / "SKILL.md"
        assert skill_md.is_file(), f"missing {skill_name}/SKILL.md"

        fields = _frontmatter(skill_md.read_text(encoding="utf-8"))

        assert fields.get("name") == skill_name
        assert fields.get("description"), f"{skill_name} needs a description"
        assert len(fields["description"]) <= 200


def test_spk_skill_bodies_stay_concise() -> None:
    for skill_name in sorted(SPK_SKILLS):
        skill_md = SKILLS_ROOT / skill_name / "SKILL.md"
        body = skill_md.read_text(encoding="utf-8").split("---\n", 2)[2]

        assert len(body.splitlines()) <= 80, f"{skill_name} body is too long"


def test_skill_command_literals_resolve_against_live_cli() -> None:
    root_command = get_command(app)
    errors: list[str] = []

    for skill_md in sorted(SKILLS_ROOT.rglob("SKILL.md")):
        text = skill_md.read_text(encoding="utf-8")
        for literal in re.findall(r"`(spec-kitty\s+[^`]+)`(?!\s+not found)", text):
            command = root_command
            command_path: list[str] = []
            unresolved: str | None = None
            for token in literal.split()[1:]:
                if token.startswith("-") or token in {"...", "…"}:
                    break
                if token.startswith("<") and token.endswith(">"):
                    break
                if not isinstance(command, click.Group):
                    break
                next_command = command.commands.get(token)
                if next_command is None:
                    # The walk stopped on an unresolved token while the current
                    # node is still a `click.Group` -- i.e. a real subcommand was
                    # expected and none exists. Record it rather than breaking
                    # silently, so drift *below* the first token (e.g.
                    # `spec-kitty tracker sync-pull`, the exact class issue #669
                    # exists to catch) can no longer sail through green on the
                    # already-resolved prefix left in `command_path`.
                    unresolved = token
                    break
                command_path.append(token)
                command = next_command

            if unresolved is not None:
                under = " ".join(["spec-kitty", *command_path])
                errors.append(
                    f"{skill_md.relative_to(REPO_ROOT)}: `{literal}` references "
                    f"unknown command '{unresolved}'"
                    + (f" under `{under}`" if command_path else "")
                )
            elif not command_path:
                errors.append(
                    f"{skill_md.relative_to(REPO_ROOT)}: `{literal}` resolves no command"
                )

    assert not errors, "\n".join(errors)


def test_spk_skill_map_mentions_every_public_skill() -> None:
    skill_map = (
        SKILLS_ROOT
        / "spk-meta-skill-map"
        / "references"
        / "spk-skill-map.md"
    ).read_text(encoding="utf-8")

    for skill_name in sorted(SPK_SKILLS):
        assert f"`{skill_name}`" in skill_map


def test_legacy_alias_skills_remain_installed() -> None:
    actual = {
        path.name
        for path in SKILLS_ROOT.iterdir()
        if path.is_dir() and (path / "SKILL.md").is_file()
    }

    assert actual >= LEGACY_ALIAS_SKILLS


def test_profile_load_skill_owns_and_installs_detailed_mechanics() -> None:
    registry = SkillRegistry.from_local_repo(REPO_ROOT)
    skill = registry.get_skill("spk-charter-profile-load")

    assert skill is not None
    reference = (
        SKILLS_ROOT
        / "spk-charter-profile-load"
        / "references"
        / "profile-load-mechanics.md"
    )
    assert skill.references == [reference]

    skill_text = skill.skill_md.read_text(encoding="utf-8")
    reference_text = reference.read_text(encoding="utf-8")

    # The folded skill keeps the retired alias's trigger phrases (FR-008, #3732).
    for trigger in ("act as the architect", "load the reviewer profile", "adopt a profile"):
        assert trigger in skill_text, trigger
    assert "alias" not in skill_text.lower(), "no compatibility alias remains (C-001)"
    assert "spec-kitty agent profile show <profile-id>" in reference_text
    assert "spec-kitty charter context --action <action> --json" in reference_text
    assert "read-only harness that cannot invoke the CLI" in reference_text
    assert "specializes_from" in reference_text
