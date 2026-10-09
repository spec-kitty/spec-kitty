"""Tier/trust validation for pack skills (FR-004)."""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.offering.pack_skills import PackSkill, PackSkillViolation
from charter.offering.pack_skills.validation import (
    Tier,
    apply_enhancement,
    validate_pack_skill,
)

from .conftest import prompt_skill, wrapper_skill, write_skill

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _load(data: dict[str, object], directory: Path, *, body: str | None = "body\n") -> tuple[PackSkill, Path]:
    return PackSkill.model_validate(data), write_skill(directory, data, body=body)


def test_valid_org_prompt_skill_passes(tmp_path: Path) -> None:
    skill, path = _load(prompt_skill(), tmp_path)
    validate_pack_skill(skill, path, tier="org", namespace="acme")


def test_wrapper_skill_needs_no_body_file(tmp_path: Path) -> None:
    skill, path = _load(wrapper_skill(), tmp_path)
    validate_pack_skill(skill, path, tier="project")


@pytest.mark.parametrize("skill_id", ["spk-land", "spec-kitty-land", "spec-kitty.land"])
def test_reserved_prefix_refused_for_org_and_project(tmp_path: Path, skill_id: str) -> None:
    # ids cannot contain '.', so the dotted prefix is exercised via the namespace below
    if "." in skill_id:
        pytest.skip("dot prefix is only reachable through a namespace")
    skill, path = _load(prompt_skill(skill_id), tmp_path)
    tiers: tuple[Tier, ...] = ("org", "project")
    for tier in tiers:
        with pytest.raises(PackSkillViolation, match="reserved for built-in"):
            validate_pack_skill(skill, path, tier=tier)


def test_reserved_prefix_refused_through_namespace(tmp_path: Path) -> None:
    skill, path = _load(prompt_skill(), tmp_path)
    with pytest.raises(PackSkillViolation, match="reserved for built-in"):
        validate_pack_skill(skill, path, tier="org", namespace="spk")
    with pytest.raises(PackSkillViolation, match="reserved for built-in"):
        validate_pack_skill(skill, path, tier="org", namespace="spec-kitty")


def test_builtin_tier_is_exempt_from_reserved_prefix(tmp_path: Path) -> None:
    skill, path = _load(prompt_skill("spk-land"), tmp_path)
    validate_pack_skill(skill, path, tier="builtin")
    validate_pack_skill(skill, path, tier="builtin", namespace="spk")


def test_builtin_tier_is_exempt_from_scripts_and_frontmatter(tmp_path: Path) -> None:
    skill, path = _load(prompt_skill(), tmp_path, body="---\nallowed-tools: Bash\n---\nbody\n")
    (tmp_path / "scripts").mkdir()
    validate_pack_skill(skill, path, tier="builtin")


@pytest.mark.parametrize("relative", ["scripts", "land-pr/scripts"])
def test_scripts_directory_refused(tmp_path: Path, relative: str) -> None:
    skill, path = _load(prompt_skill(), tmp_path)
    (tmp_path / relative).mkdir(parents=True)
    with pytest.raises(PackSkillViolation, match="scripts/"):
        validate_pack_skill(skill, path, tier="org")


@pytest.mark.parametrize("key", ["allowed-tools", "allowed_tools", "Allowed-Tools"])
def test_allowed_tools_frontmatter_refused(tmp_path: Path, key: str) -> None:
    skill, path = _load(prompt_skill(), tmp_path, body=f"---\n{key}: Bash\n---\nbody\n")
    with pytest.raises(PackSkillViolation, match="permission-widening"):
        validate_pack_skill(skill, path, tier="project")


def test_harmless_frontmatter_is_allowed(tmp_path: Path) -> None:
    skill, path = _load(prompt_skill(), tmp_path, body="---\nname: x\n---\nbody\n")
    validate_pack_skill(skill, path, tier="org")


def test_missing_body_refused_for_every_tier(tmp_path: Path) -> None:
    skill, path = _load(prompt_skill(), tmp_path, body=None)
    tiers: tuple[Tier, ...] = ("builtin", "org")
    for tier in tiers:
        with pytest.raises(PackSkillViolation, match="not found"):
            validate_pack_skill(skill, path, tier=tier)


def test_body_path_escaping_directory_refused(tmp_path: Path) -> None:
    skills = tmp_path / "skills"
    data = prompt_skill(body_path="../outside.md")
    skill, path = _load(data, skills, body=None)
    (tmp_path / "outside.md").write_text("x", encoding="utf-8")
    with pytest.raises(PackSkillViolation, match="escapes"):
        validate_pack_skill(skill, path, tier="org")


@pytest.mark.parametrize(
    "body, message",
    [
        ("---\nname: a\nbody", "not closed"),
        ("---\n- a\n- b\n---\nbody", "must be a mapping"),
        ("---\nname: [unclosed\n---\nbody", "not valid YAML"),
    ],
)
def test_malformed_frontmatter_is_refused_through_validation(tmp_path: Path, body: str, message: str) -> None:
    skill, path = _load(prompt_skill(), tmp_path, body=body)
    with pytest.raises(PackSkillViolation, match=message):
        validate_pack_skill(skill, path, tier="org")


# -- enhances limits -------------------------------------------------------


def _base() -> PackSkill:
    return PackSkill.model_validate(
        prompt_skill(
            triggers=["land"],
            parameters=[{"name": "pr", "required": True}, {"name": "steer", "default": "none"}],
            invocation={"user_invocable": True, "model_invocable": True, "side_effects": ["git-push"]},
        )
    )


def _enhancer(**overrides: object) -> PackSkill:
    base = prompt_skill(
        "land-pr-tuned",
        body_path="land-pr.skill.md",
        enhances="land-pr",
        triggers=["landing pass"],
        tools=["claude"],
        parameters=[{"name": "pr", "required": True}, {"name": "steer", "default": "fast"}],
        invocation={"side_effects": ["git-push", "gh-write"]},
    )
    base.update(overrides)
    return PackSkill.model_validate(base)


def test_enhancement_may_tune_defaults_triggers_tools_and_narrow() -> None:
    result = apply_enhancement(_base(), _enhancer())
    assert result.id == "land-pr"
    assert result.triggers == ["landing pass"]
    assert result.tools == ["claude"]
    assert result.parameters[1].default == "fast"
    assert result.invocation.side_effects == ["git-push", "gh-write"]
    assert result.invocation.model_invocable is False
    assert result.body_path == "land-pr.skill.md"


@pytest.mark.parametrize(
    "mutation, message",
    [
        ({"body_path": "other.md"}, "body or expansion"),
        ({"form": "wrapper", "body_path": None, "expands_to": {"target": "builtin:x"}}, "body or expansion"),
        ({"parameters": [{"name": "pr", "required": True}]}, "parameter defaults"),
        ({"parameters": [{"name": "pr", "required": False}, {"name": "steer"}]}, "parameter defaults"),
        ({"invocation": {"side_effects": []}}, "narrow invocation"),
    ],
)
def test_enhancement_refusals(mutation: dict[str, object], message: str) -> None:
    with pytest.raises(PackSkillViolation, match=message):
        apply_enhancement(_base(), _enhancer(**mutation))


def test_enhancement_may_not_widen_invocation() -> None:
    narrow = PackSkill.model_validate(prompt_skill(invocation={"user_invocable": False, "model_invocable": False}))
    widen_user = _enhancer(invocation={"user_invocable": True, "model_invocable": False}, parameters=[])
    widen_model = _enhancer(invocation={"user_invocable": False, "model_invocable": True}, parameters=[])
    for enhancer in (widen_user, widen_model):
        with pytest.raises(PackSkillViolation, match="narrow invocation"):
            apply_enhancement(narrow, enhancer)
