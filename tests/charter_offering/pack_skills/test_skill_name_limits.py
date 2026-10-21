"""Pack skill name and description limits (#6475, FR-014, US5 scenario 1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation.skill_preparation import SkillPreparationError, _prepare_skill_activations
from charter.drg import DRGGraph
from charter.offering.pack_skills import PackSkill, PackSkillViolation
from charter.offering.pack_skills.models import MAX_SKILL_DESCRIPTION_LENGTH, MAX_SKILL_NAME_LENGTH
from charter.offering.pack_skills.validation import Tier, rendered_description, skill_limit_violation, validate_pack_skill

from .conftest import prompt_skill, write_skill

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_NAMESPACE = "acme"
#: ``acme-`` + id: the id length that renders a name of exactly *n* characters.
_ID_FOR = {n: "a" * (n - len(_NAMESPACE) - 1) for n in (MAX_SKILL_NAME_LENGTH, MAX_SKILL_NAME_LENGTH + 1)}
_TRIGGERS = ["deploy now"]
#: ``" Triggers: deploy now."`` is 22 characters.
_SUFFIX = len(" Triggers: deploy now.")


def _load(tmp_path: Path, skill_id: str = "land", **overrides: object) -> tuple[PackSkill, Path]:
    data = prompt_skill(skill_id, **overrides)
    return PackSkill.model_validate(data), write_skill(tmp_path, data, body="body\n")


def test_limits_are_the_agent_skills_values() -> None:
    assert (MAX_SKILL_NAME_LENGTH, MAX_SKILL_DESCRIPTION_LENGTH) == (64, 1024)


def test_rendered_description_collapses_whitespace_and_appends_triggers(tmp_path: Path) -> None:
    skill, _ = _load(tmp_path, description="Land  a\n PR.", triggers=["land it", "ship"])
    assert rendered_description(skill) == "Land a PR. Triggers: land it, ship."


@pytest.mark.parametrize("tier", ["org", "project"])
def test_rendered_name_of_64_characters_is_accepted(tmp_path: Path, tier: Tier) -> None:
    skill, path = _load(tmp_path, _ID_FOR[64])
    validate_pack_skill(skill, path, tier=tier, namespace=_NAMESPACE)


@pytest.mark.parametrize("tier", ["org", "project"])
def test_rendered_name_of_65_characters_is_refused_naming_the_limit(tmp_path: Path, tier: Tier) -> None:
    skill, path = _load(tmp_path, _ID_FOR[65])
    with pytest.raises(PackSkillViolation, match=r"is 65 characters, over the 64-character skill name limit"):
        validate_pack_skill(skill, path, tier=tier, namespace=_NAMESPACE)


def test_builtin_tier_measures_the_bare_id(tmp_path: Path) -> None:
    skill, path = _load(tmp_path, "a" * 64)
    validate_pack_skill(skill, path, tier="built-in", namespace=_NAMESPACE)


def test_description_of_1024_characters_with_triggers_is_accepted(tmp_path: Path) -> None:
    skill, path = _load(tmp_path, description="d" * (1024 - _SUFFIX), triggers=_TRIGGERS)
    assert len(rendered_description(skill)) == 1024
    validate_pack_skill(skill, path, tier="org", namespace=_NAMESPACE)


def test_description_of_1025_characters_after_triggers_is_refused(tmp_path: Path) -> None:
    skill, path = _load(tmp_path, description="d" * (1025 - _SUFFIX), triggers=_TRIGGERS)
    with pytest.raises(PackSkillViolation, match=r"rendered description \(with its triggers\) is 1025 characters, over the 1024-character"):
        validate_pack_skill(skill, path, tier="built-in")


def test_skill_limit_violation_is_none_within_limits(tmp_path: Path) -> None:
    skill, _ = _load(tmp_path)
    assert skill_limit_violation(skill, "acme-land") is None


def _empty_graph() -> DRGGraph:
    return DRGGraph(schema_version="1.0", generated_at="2026-10-21T00:00:00Z", generated_by="test", nodes=[], edges=[])


class _Source:
    def __init__(self, skill: PackSkill, tier: str) -> None:
        self._skill, self._tier = skill, tier

    def get(self, item_id: str) -> PackSkill | None:
        return self._skill if item_id == self._skill.id else None

    def source_path(self, skill_id: str) -> Path | None:
        return Path(f"/packs/{skill_id}.skill.yaml") if skill_id == self._skill.id else None

    def provenance_of(self, skill_id: str) -> str | None:
        return self._tier

    def body_text(self, skill_id: str) -> str | None:
        return "body\n"


def test_preparation_refuses_a_65_character_rendered_name(tmp_path: Path) -> None:
    skill, _ = _load(tmp_path, _ID_FOR[65])
    with pytest.raises(SkillPreparationError, match="over the 64-character skill name limit"):
        _prepare_skill_activations(_Source(skill, "project"), [skill.id], graph=_empty_graph(), org_namespace=None, project_namespace=_NAMESPACE)


def test_preparation_accepts_a_64_character_rendered_name(tmp_path: Path) -> None:
    skill, _ = _load(tmp_path, _ID_FOR[64])
    prepared = _prepare_skill_activations(_Source(skill, "org"), [skill.id], graph=_empty_graph(), org_namespace=_NAMESPACE, project_namespace=None)
    assert len(prepared[0].rendered_name) == 64


def test_preparation_refuses_an_over_long_rendered_description(tmp_path: Path) -> None:
    skill, _ = _load(tmp_path, description="d" * 1025)
    with pytest.raises(SkillPreparationError, match="over the 1024-character skill description limit"):
        _prepare_skill_activations(_Source(skill, "org"), [skill.id], graph=_empty_graph(), org_namespace=_NAMESPACE, project_namespace=None)
