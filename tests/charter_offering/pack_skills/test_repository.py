"""PackSkillRepository: tiers, sibling conflicts, overrides/enhances (FR-005)."""

from __future__ import annotations

import os
import warnings
from pathlib import Path

import pytest

from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.pack_skills import PackSkillConflictError, PackSkillRepository, PackSkillViolation
from charter.offering.pack_skills.models import PackSkill

from .conftest import prompt_skill, wrapper_skill, write_skill

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _load(skill_dirs: dict[str, Path], *, skill_namespace: str | None = None) -> tuple[PackSkillRepository, list[str]]:
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        repo = PackSkillRepository(
            built_in_dir=skill_dirs["builtin"],
            org_dirs=[skill_dirs["org_a"], skill_dirs["org_b"]],
            project_dir=skill_dirs["project"],
            skill_namespace=skill_namespace,
        )
    return repo, [str(w.message) for w in captured if issubclass(w.category, UserWarning)]


def test_skill_kind_ships_a_built_in_content_dir() -> None:
    assert ArtifactKind.SKILL.has_built_in_content_dir is True
    PackSkillRepository()  # the default built-in directory resolves and loads


def test_loads_three_tiers_with_provenance_and_body(skill_dirs: dict[str, Path]) -> None:
    write_skill(skill_dirs["builtin"], prompt_skill("core-skill"))
    write_skill(skill_dirs["org_a"], prompt_skill("land-pr"), body="landing body\n")
    write_skill(skill_dirs["project"], wrapper_skill("ship"))

    repo, warned = _load(skill_dirs)

    assert warned == []
    assert [item.id for item in repo.list_all()] == ["core-skill", "land-pr", "ship"]
    assert repo.provenance_of("core-skill") == "built-in"
    assert repo.provenance_of("land-pr") == "org"
    assert repo.provenance_of("ship") == "project"
    assert repo.body_text("land-pr") == "landing body\n"
    assert repo.body_text("ship") is None
    assert repo.body_text("missing") is None
    assert repo.source_path("land-pr") == skill_dirs["org_a"] / "land-pr.skill.yaml"
    assert repo.source_path("missing") is None


def test_invalid_org_skill_is_skipped_with_warning(skill_dirs: dict[str, Path]) -> None:
    write_skill(skill_dirs["org_a"], prompt_skill("spk-land"))
    write_skill(skill_dirs["org_a"], prompt_skill("fine"))

    repo, warned = _load(skill_dirs)

    assert [item.id for item in repo.list_all()] == ["fine"]
    assert len(warned) == 1
    assert "Skipping invalid org pack-skill spk-land.skill.yaml" in warned[0]
    assert "reserved for built-in" in warned[0]


def test_namespace_drives_the_reserved_prefix_check(skill_dirs: dict[str, Path]) -> None:
    write_skill(skill_dirs["org_a"], prompt_skill("land-pr"))
    repo, warned = _load(skill_dirs, skill_namespace="spk")
    assert repo.list_all() == []
    assert "reserved for built-in" in warned[0]


def test_same_id_in_sibling_org_packs_is_a_hard_conflict(skill_dirs: dict[str, Path]) -> None:
    write_skill(skill_dirs["org_a"], prompt_skill("land-pr"))
    write_skill(skill_dirs["org_b"], prompt_skill("land-pr"))
    with pytest.raises(PackSkillConflictError, match="two org packs"):
        _load(skill_dirs)


def test_same_org_pack_may_split_a_skill_across_subdirectories_without_conflict(skill_dirs: dict[str, Path]) -> None:
    write_skill(skill_dirs["org_a"] / "one", prompt_skill("alpha"))
    write_skill(skill_dirs["org_a"] / "two", prompt_skill("beta"))
    repo, warned = _load(skill_dirs)
    assert warned == []
    assert [item.id for item in repo.list_all()] == ["alpha", "beta"]


def test_enhances_tunes_lower_tier_skill_under_target_id(skill_dirs: dict[str, Path]) -> None:
    write_skill(skill_dirs["org_a"], prompt_skill("land-pr", triggers=["land"]))
    write_skill(
        skill_dirs["project"],
        prompt_skill("land-pr-local", enhances="land-pr", body_path="land-pr.skill.md", triggers=["local land"]),
        body=None,
    )

    repo, warned = _load(skill_dirs)

    assert warned == []
    assert [item.id for item in repo.list_all()] == ["land-pr"]
    assert repo.list_all()[0].triggers == ["local land"]
    assert repo.provenance_of("land-pr") == "project"
    # the enhancement never carries the body: the base file stays the body source
    assert repo.source_path("land-pr") == skill_dirs["org_a"] / "land-pr.skill.yaml"
    assert repo.body_text("land-pr") == "Do the thing: $ARGUMENTS\n"


def test_enhances_may_not_change_body(skill_dirs: dict[str, Path]) -> None:
    write_skill(skill_dirs["org_a"], prompt_skill("land-pr"))
    write_skill(skill_dirs["project"], prompt_skill("land-pr-local", enhances="land-pr", body_path="other.md"))

    repo, warned = _load(skill_dirs)

    assert [item.id for item in repo.list_all()] == ["land-pr"]
    assert repo.provenance_of("land-pr") == "org"
    assert any("body or expansion" in message for message in warned)


def test_overrides_replaces_org_skill_under_target_id(skill_dirs: dict[str, Path]) -> None:
    write_skill(skill_dirs["org_a"], prompt_skill("land-pr"), body="org body\n")
    write_skill(skill_dirs["project"], prompt_skill("my-land", overrides="land-pr", body_path="my-land.skill.md"), body="project body\n")

    repo, warned = _load(skill_dirs)

    assert warned == []
    assert [item.id for item in repo.list_all()] == ["land-pr"]
    assert repo.list_all()[0].overrides is None
    assert repo.body_text("land-pr") == "project body\n"


def test_overriding_a_builtin_skill_is_refused(skill_dirs: dict[str, Path]) -> None:
    write_skill(skill_dirs["builtin"], prompt_skill("core-skill"))
    write_skill(skill_dirs["org_a"], prompt_skill("mine", overrides="core-skill"))

    repo, warned = _load(skill_dirs)

    assert [item.id for item in repo.list_all()] == ["core-skill"]
    assert any("replaceable-builtins" in message for message in warned)


def test_augmenter_with_unknown_target_is_skipped(skill_dirs: dict[str, Path]) -> None:
    write_skill(skill_dirs["project"], prompt_skill("orphan", enhances="nope"))
    repo, warned = _load(skill_dirs)
    assert repo.list_all() == []
    assert any("not loaded from a lower tier" in message for message in warned)


def test_augmenter_in_same_tier_as_target_is_skipped(skill_dirs: dict[str, Path]) -> None:
    write_skill(skill_dirs["org_a"], prompt_skill("land-pr"))
    write_skill(skill_dirs["org_a"], prompt_skill("land-pr-b", enhances="land-pr", body_path="land-pr.skill.md"))
    repo, warned = _load(skill_dirs)
    assert [item.id for item in repo.list_all()] == ["land-pr"]
    assert any("lower tier" in message for message in warned)


# -- body_path containment at read time (#6734) ------------------------------


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks are unavailable on this platform")
def test_body_text_refuses_symlink_swapped_after_load(skill_dirs: dict[str, Path]) -> None:
    # TOCTOU through the public entry point: the body passes load-time
    # validation (the link still resolves inside the skill directory), then is
    # repointed outside before the read.
    skill_dir = skill_dirs["org_a"] / "team"
    data = prompt_skill("land-pr", body_path="link.md")
    write_skill(skill_dir, data, body=None)
    (skill_dir / "target.md").write_text("inside body\n", encoding="utf-8")
    (skill_dir / "link.md").symlink_to(skill_dir / "target.md")

    repo, warned = _load(skill_dirs)

    assert warned == []
    assert repo.body_text("land-pr") == "inside body\n"
    outside = skill_dirs["org_a"].parent / "outside.md"
    outside.write_text("SECRET OUTSIDE\n", encoding="utf-8")
    (skill_dir / "link.md").unlink()
    (skill_dir / "link.md").symlink_to(outside)
    with pytest.raises(PackSkillViolation, match="escapes"):
        repo.body_text("land-pr")


@pytest.mark.parametrize("body_path", ["../outside.md", "/etc/passwd", "nested/../../outside.md"])
def test_body_text_refuses_escaping_body_path(skill_dirs: dict[str, Path], body_path: str) -> None:
    # Injected record: load-time validation skips a file with an escaping
    # body_path, so the catalog cannot hold one through loading -- the read-time
    # guard is defense-in-depth for records that reach it any other way.
    (skill_dirs["org_a"].parent / "outside.md").write_text("SECRET OUTSIDE\n", encoding="utf-8")
    repo, _ = _load(skill_dirs)
    escaped = PackSkill.model_validate(prompt_skill("escaped", body_path=body_path))
    repo._items["escaped"] = escaped
    repo._sources["escaped"] = skill_dirs["org_a"] / "escaped.skill.yaml"
    with pytest.raises(PackSkillViolation, match="escapes"):
        repo.body_text("escaped")


def test_body_text_reads_a_nested_contained_body(skill_dirs: dict[str, Path]) -> None:
    # Positive control: a contained (nested) body still loads and reads.
    (skill_dirs["org_a"] / "nested").mkdir()
    write_skill(skill_dirs["org_a"], prompt_skill("land-pr", body_path="nested/body.md"), body="nested body\n")
    repo, warned = _load(skill_dirs)
    assert warned == []
    assert repo.body_text("land-pr") == "nested body\n"
