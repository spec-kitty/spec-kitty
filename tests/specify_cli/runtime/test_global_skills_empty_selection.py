"""A global skill assessment with no selected agent still prepares a valid inventory effect.

``upgrade`` assesses the user-global skills with a selection of the project's agents.
When none of them has a user-global skill root, the selection names no agent. An
inventory written by an older release is still rewritten once into the #7722 layout,
and that effect must keep a logical owner: an empty owner tuple is not a valid effect
(``PhysicalEffect``). Found red on main after #7763 (``upgrade`` exited 1 with
"Effect requires owner, reason, exact ownership and logical owners").
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.core.config import CLAUDE_CONFIG_DIR_ENV
from specify_cli.runtime import agent_skills

pytestmark = [pytest.mark.fast]


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home / ".kittify"))
    monkeypatch.delenv(CLAUDE_CONFIG_DIR_ENV, raising=False)
    return home


def _legacy_inventory(home: Path) -> Path:
    """An inventory as a release before #7722 wrote it: schema 1, no ``anchor`` key."""
    inventory = home / ".kittify" / "cache" / "global_skills-assets.json"
    inventory.parent.mkdir(parents=True)
    inventory.write_text(json.dumps({"schema_version": 1, "entries": {}}), encoding="utf-8")
    return inventory


def test_a_selection_without_agents_keeps_the_owner_as_logical_owner(home: Path) -> None:
    inventory = _legacy_inventory(home)
    selection = agent_skills.GlobalSkillSelection(skills=(), agent_keys=())

    assessment = agent_skills.assess_global_agent_skills(selection=selection)

    assert assessment.complete, assessment.diagnostics
    rewrite = [effect for effect in assessment.effects if assessment.root.path / effect.path == inventory]
    assert rewrite, "control: the legacy inventory is rewritten once in the #7722 layout"
    assert all(effect.logical_owners for effect in assessment.effects)


def test_a_selection_with_agents_still_attributes_effects_to_them(home: Path) -> None:
    _legacy_inventory(home)
    selection = agent_skills.GlobalSkillSelection(skills=(), agent_keys=("claude",))

    assessment = agent_skills.assess_global_agent_skills(selection=selection)

    assert assessment.complete, assessment.diagnostics
    assert {owner for effect in assessment.effects for owner in effect.logical_owners} == {"claude"}


def test_upgrades_combined_global_assessment_with_no_agents_is_complete(home: Path) -> None:
    """The combined global assessment ``upgrade`` runs, with every owner's inventory in the old layout."""
    from specify_cli.runtime.asset_preparation import assess_global_assets

    cache = home / ".kittify" / "cache"
    cache.mkdir(parents=True)
    for owner in ("runtime_bootstrap", "slash_commands", "global_skills"):
        (cache / f"{owner}-assets.json").write_text(json.dumps({"schema_version": 1, "entries": {}}), encoding="utf-8")

    assessment = assess_global_assets(agent_keys=[], skill_selection=agent_skills.GlobalSkillSelection(skills=(), agent_keys=()))

    assert assessment.complete, assessment.diagnostics
    assert all(effect.logical_owners for effect in assessment.effects)
