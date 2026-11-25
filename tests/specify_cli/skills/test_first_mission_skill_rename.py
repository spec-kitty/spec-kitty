"""The first-mission skill says Mission, not feature (#7725, Terminology Canon).

``spk-start-first-feature`` is renamed ``spk-start-first-mission``; the old id is
retired so the global skill sync removes an unedited old copy, and no shipped
skill text routes to the old id.
"""

from __future__ import annotations

import pytest

from specify_cli.skills.registry import SkillRegistry
from specify_cli.skills.retired import RETIRED_CANONICAL_SKILL_NAMES

pytestmark = [pytest.mark.fast]

_OLD = "spk-start-first-feature"
_NEW = "spk-start-first-mission"


def _registry() -> SkillRegistry:
    return SkillRegistry.from_package()


def test_catalog_ships_the_new_id_only() -> None:
    names = {skill.name for skill in _registry().discover_skills()}
    assert _NEW in names
    assert _OLD not in names


def test_old_id_is_retired() -> None:
    assert _OLD in RETIRED_CANONICAL_SKILL_NAMES


def test_no_shipped_skill_names_the_old_id() -> None:
    offenders = [
        f"{skill.name}/{path.relative_to(skill.skill_dir).as_posix()}"
        for skill in _registry().discover_skills()
        for path in skill.all_files
        if _OLD in path.read_text(encoding="utf-8")
    ]
    assert not offenders


def test_start_here_says_mission() -> None:
    skill = next(s for s in _registry().discover_skills() if s.name == "spk-start-here")
    text = skill.skill_md.read_text(encoding="utf-8")
    assert "New feature" not in text
    assert f"`{_NEW}`" in text
