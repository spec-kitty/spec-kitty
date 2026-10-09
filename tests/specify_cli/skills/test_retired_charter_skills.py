"""The skill families folded by the charter-pack cutover are retired, not aliased (FR-008, C-001, #3732)."""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.runtime import agent_skills
from specify_cli.skills.registry import SkillRegistry
from specify_cli.skills.retired import RETIRED_CANONICAL_SKILL_NAMES

pytestmark = [pytest.mark.fast]

#: The twelve FR-008 names plus ``spec-kitty-constitution-doctrine`` (ruling FI-S4).
FOLDED_NAMES = frozenset(
    {
        "ad-hoc-profile-load",
        "spec-kitty-bulk-edit-classification",
        "spec-kitty-charter-doctrine",
        "spec-kitty-constitution-doctrine",
        "spec-kitty-glossary-context",
        "spec-kitty-spdd-reasons",
        "spk-doctrine-bulk-edit",
        "spk-doctrine-charter",
        "spk-doctrine-glossary",
        "spk-doctrine-profile-load",
        "spk-doctrine-semantic-compression",
        "spk-doctrine-show-me",
        "spk-doctrine-spdd-reasons",
    }
)
NEW_NAMES = frozenset(
    {
        "spk-charter-glossary",
        "spk-charter-governance",
        "spk-charter-profile-load",
        "spk-charter-spdd-reasons",
        "spk-practice-bulk-edit",
        "spk-practice-semantic-compression",
        "spk-practice-show-me",
    }
)
OLD_GLOBAL_COPIES = ("spk-doctrine-charter", "spec-kitty-glossary-context")


def _shipped_names() -> set[str]:
    return {skill.name for skill in SkillRegistry.from_package().discover_skills()}


def _write_skill(root: Path, name: str, body: str) -> None:
    skill_dir = root / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {body}\n---\n# {name}\n", encoding="utf-8")


@pytest.fixture
def global_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home / ".kittify"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("OPENCODE_CONFIG_DIR", str(home / ".config" / "opencode"))
    return home


def _install_as_older_release(catalog: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Materialize *catalog* globally the way an older CLI did, recording the global inventory."""
    with monkeypatch.context() as patch:
        patch.setattr(agent_skills, "_discover_registry", lambda: SkillRegistry(catalog))
        agent_skills.ensure_global_agent_skills()


def test_every_folded_name_is_retired() -> None:
    assert len(FOLDED_NAMES) == 13
    assert FOLDED_NAMES <= RETIRED_CANONICAL_SKILL_NAMES, sorted(FOLDED_NAMES - RETIRED_CANONICAL_SKILL_NAMES)


def test_shipped_registry_carries_the_new_families_and_no_folded_name() -> None:
    shipped = _shipped_names()
    assert shipped >= NEW_NAMES, sorted(NEW_NAMES - shipped)
    assert not FOLDED_NAMES & shipped, sorted(FOLDED_NAMES & shipped)


def test_global_root_retires_old_copies_and_keeps_custom_skill(global_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    catalog = tmp_path / "older-release"
    for name in OLD_GLOBAL_COPIES:
        _write_skill(catalog, name, "shipped by an older release")
    _install_as_older_release(catalog, monkeypatch)
    root = global_home / ".claude" / "skills"
    _write_skill(root, "team-custom", "not managed by spec-kitty")
    assert {*OLD_GLOBAL_COPIES, "team-custom"} <= {p.name for p in root.iterdir()}, "control: the old copies are installed"

    agent_skills.ensure_global_agent_skills()

    names = {p.name for p in root.iterdir()}
    assert not names & set(OLD_GLOBAL_COPIES), sorted(names & set(OLD_GLOBAL_COPIES))
    assert "team-custom" in names, "an unrelated custom skill is preserved"
    assert names >= NEW_NAMES, sorted(NEW_NAMES - names)


def test_global_root_keeps_an_unproven_copy_under_a_retired_name(global_home: Path) -> None:
    root = global_home / ".claude" / "skills"
    _write_skill(root, "spk-doctrine-charter", "hand-written, never installed by spec-kitty")

    agent_skills.ensure_global_agent_skills()

    assert (root / "spk-doctrine-charter" / "SKILL.md").is_file(), "unproven content is never deleted by name alone"
