"""Skill activation: config key, default-in-force, cascade (mission pack-skills-kind, WP03).

Covers FR-006 (activation key + the CLI token), FR-007 (absent key => org
``required_skills`` only, never "every skill") and the SC-006 shared-procedure
cascade, plus the existing kinds still resolving ``all`` when their key is absent.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from charter.activation.activation_engine import NoActivationRestrictionsError, plan_activation
from charter.activation.doctrine_service_builder import build_activation_aware_doctrine_service
from charter.activation.invocation_context import ProjectContext
from charter.activation.org_pack_discovery import read_org_required_ids, read_org_skill_namespace
from charter.activation.pack_context import PackContext, _absent_key_default
from charter.activation.pack_manager import CharterPackManager, YAML_KEY_MAP
from charter.activation.skill_preparation import SkillPreparationError
from charter.offering.artifact_kinds import ArtifactKind
from specify_cli.cli.commands.charter import charter_app

from . import skill_pack_support as support

pytestmark = [pytest.mark.integration]

runner = CliRunner()


def _skill_ids_in_force(project: Path) -> set[str]:
    return set(build_activation_aware_doctrine_service(project).skills)


def _activated(project: Path, key: str) -> list[str] | None:
    data = yaml.safe_load((project / ".kittify" / "config.yaml").read_text(encoding="utf-8")) or {}
    value = data.get(key)
    return None if value is None else list(value)


def _activate(project: Path, *args: str) -> str:
    result = runner.invoke(charter_app, ["activate", "--repo-root", str(project), "--no-compile", *args], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    return result.output


def _deactivate(project: Path, *args: str) -> str:
    result = runner.invoke(charter_app, ["deactivate", "--repo-root", str(project), "--no-compile", *args], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    return result.output


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A project registering an org pack with 4 skills, one of them required."""
    pack = tmp_path / "pack"
    pack.mkdir()
    for skill_id in ("required-one", "x", "y", "z"):
        support.write_skill(pack, skill_id)
    support.write_org_charter(pack, required_skills=["required-one"])
    support.write_config(tmp_path, pack)
    return tmp_path


# ---------------------------------------------------------------------------
# Kind fact
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", list(ArtifactKind), ids=lambda k: k.value)
def test_only_skill_is_required_when_absent(kind: ArtifactKind) -> None:
    expected = "required" if kind is ArtifactKind.SKILL else "all"
    assert kind.effective_when_absent == expected


def test_skill_has_an_activation_key() -> None:
    assert YAML_KEY_MAP["skill"] == "activated_skills"


# ---------------------------------------------------------------------------
# Org-charter readers
# ---------------------------------------------------------------------------


def test_org_required_ids_union_dedupes_and_skips_malformed(tmp_path: Path) -> None:
    pack_a, pack_b = tmp_path / "a", tmp_path / "b"
    for root in (pack_a, pack_b):
        root.mkdir()
    (pack_a / "org-charter.yaml").write_text("required_skills: [one, two, ' ', one]\nskill_namespace: first\n", encoding="utf-8")
    (pack_b / "org-charter.yaml").write_text("required_skills: not-a-list\nskill_namespace: '  '\n", encoding="utf-8")
    third = tmp_path / "c"
    third.mkdir()
    (third / "org-charter.yaml").write_text("required_skills: [three, one]\nskill_namespace: last\n", encoding="utf-8")
    config = tmp_path / ".kittify" / "config.yaml"
    config.parent.mkdir()
    config.write_text(
        "mission_type_activations: [software-dev]\ncharter_packs:\n  org:\n    packs:\n"
        + "".join(f"      - name: {r.name}\n        local_path: {r}\n" for r in (pack_a, pack_b, third)),
        encoding="utf-8",
    )

    assert read_org_required_ids(tmp_path, ArtifactKind.SKILL) == ["one", "two", "three"]
    assert read_org_skill_namespace(tmp_path) == "last"
    assert "last".isascii()

    (third / "org-charter.yaml").write_text("skill_namespace: '../../x'\n", encoding="utf-8")  # refused where it is read
    with pytest.raises(SkillPreparationError, match=r"not valid.*org pack 'c'"):
        read_org_skill_namespace(tmp_path)


def test_org_readers_without_packs(tmp_path: Path) -> None:
    support.write_config(tmp_path, None)
    assert read_org_required_ids(tmp_path, ArtifactKind.SKILL) == []
    assert read_org_skill_namespace(tmp_path) is None


# ---------------------------------------------------------------------------
# Three-state resolution (FR-007)
# ---------------------------------------------------------------------------


def test_absent_key_puts_only_required_skills_in_force(project: Path) -> None:
    assert PackContext.from_config(project).activated_skills == frozenset({"required-one"})
    assert _skill_ids_in_force(project) == {"required-one"}


def test_absent_key_without_required_skills_means_no_skills(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    pack.mkdir()
    support.write_skill(pack, "x")
    support.write_config(tmp_path, pack)
    assert PackContext.from_config(tmp_path).activated_skills == frozenset()
    assert _skill_ids_in_force(tmp_path) == set()


def test_explicit_empty_list_is_nothing_even_with_required_skills(project: Path) -> None:
    support.write_config(project, project / "pack", extra="activated_skills: []\n")
    assert PackContext.from_config(project).activated_skills == frozenset()
    assert _skill_ids_in_force(project) == set()


def test_explicit_list_is_exactly_that_list(project: Path) -> None:
    support.write_config(project, project / "pack", extra="activated_skills: [y]\n")
    assert PackContext.from_config(project).activated_skills == frozenset({"y"})
    assert _skill_ids_in_force(project) == {"y"}


def test_existing_kinds_still_resolve_all_when_absent(project: Path) -> None:
    ctx = PackContext.from_config(project)
    assert ctx.activated_tactics is None
    assert ctx.activated_procedures is None
    assert _absent_key_default(ArtifactKind.TACTIC, project) is None


# ---------------------------------------------------------------------------
# Planner (pure)
# ---------------------------------------------------------------------------


def test_plan_required_kind_never_falls_back_to_every_available() -> None:
    plan = plan_activation("skill", "x", yaml_key="activated_skills", available_ids=["a", "b", "x"], config_data={}, effective_when_absent="required")
    assert plan.new_list == ["x"]


def test_plan_required_kind_keeps_the_effective_set() -> None:
    plan = plan_activation(
        "skill", "x", yaml_key="activated_skills", available_ids=["a", "b", "x"], config_data={}, effective_ids=["r"], effective_when_absent="required"
    )
    assert plan.new_list == ["r", "x"]


def test_plan_all_kind_with_empty_effective_still_falls_back_to_available() -> None:
    plan = plan_activation("tactic", "b", yaml_key="activated_tactics", available_ids=["a", "b"], config_data={})
    assert plan.new_list == ["a", "b"]


# ---------------------------------------------------------------------------
# End to end through the CLI (the `skill` token)
# ---------------------------------------------------------------------------


def test_activate_skill_from_absent_key_yields_exactly_required_plus_x(project: Path) -> None:
    """Amendment: >=3 available skills, 1 required, activate X => exactly {required, X}."""
    output = _activate(project, "skill", "x")

    assert "Activated" in output
    assert _activated(project, "activated_skills") == ["required-one", "x"]
    assert _skill_ids_in_force(project) == {"required-one", "x"}
    assert not _skill_ids_in_force(project) & {"y", "z"}


def test_activate_already_required_skill_from_absent_key(project: Path) -> None:
    _activate(project, "skill", "required-one")
    assert _activated(project, "activated_skills") == ["required-one"]


def test_activate_unknown_skill_is_refused_without_writing(project: Path) -> None:
    result = runner.invoke(charter_app, ["activate", "--repo-root", str(project), "--no-compile", "skill", "nope"], catch_exceptions=False)
    assert result.exit_code == 1
    assert _activated(project, "activated_skills") is None


def test_deactivate_skill_removes_only_that_skill(project: Path) -> None:
    _activate(project, "skill", "x")
    _activate(project, "skill", "y")
    _deactivate(project, "skill", "x")
    assert _activated(project, "activated_skills") == ["required-one", "y"]


def test_deactivate_skill_from_absent_key_is_refused_with_guidance(project: Path) -> None:
    with pytest.raises(NoActivationRestrictionsError) as excinfo:
        CharterPackManager().deactivate(ProjectContext(repo_root=project), "skill", "required-one")
    message = str(excinfo.value)
    assert "spec-kitty charter activate skill <id>" in message
    assert "spec-kitty upgrade" not in message


def test_absent_key_remedy_for_all_kinds_still_points_at_upgrade() -> None:
    assert "spec-kitty upgrade" in str(NoActivationRestrictionsError("tactic"))
    assert "spec-kitty upgrade" in str(NoActivationRestrictionsError("not-a-kind"))


def test_activating_a_skill_leaves_other_kinds_untouched(project: Path) -> None:
    _activate(project, "skill", "x")
    assert _activated(project, "activated_tactics") is None
    assert _activated(project, "activated_procedures") is None


# ---------------------------------------------------------------------------
# merge_defaults must not write the skills key (reviewer-mandated)
# ---------------------------------------------------------------------------


def test_merge_defaults_keeps_an_absent_skills_key_absent(project: Path) -> None:
    result = CharterPackManager().merge_defaults(ProjectContext(repo_root=project))

    assert "skill" not in result.kinds_written
    assert _activated(project, "activated_skills") is None
    assert _activated(project, "activated_directives") is not None
    assert _skill_ids_in_force(project) == {"required-one"}


def test_merge_defaults_preserves_an_explicit_skills_key(project: Path) -> None:
    support.write_config(project, project / "pack", extra="activated_skills: [z]\n")
    CharterPackManager().merge_defaults(ProjectContext(repo_root=project))
    assert _activated(project, "activated_skills") == ["z"]


# ---------------------------------------------------------------------------
# Cascade (FR-006, SC-006)
# ---------------------------------------------------------------------------


@pytest.fixture
def cascade_project(tmp_path: Path) -> Path:
    """Skills s1/s2/s3 and directive d, procedures p (shared) and p2 (s2 only)."""
    pack = tmp_path / "pack"
    pack.mkdir()
    for skill_id in ("s1", "s2", "s3"):
        support.write_skill(pack, skill_id)
    for procedure_id in ("shared-proc", "solo-proc"):
        support.write_procedure(pack, procedure_id)
    support.write_directive(pack, "dir-d")
    support.write_fragment(
        pack,
        nodes=[
            ("skill:s1", "skill"),
            ("skill:s2", "skill"),
            ("skill:s3", "skill"),
            ("procedure:shared-proc", "procedure"),
            ("procedure:solo-proc", "procedure"),
            ("directive:dir-d", "directive"),
        ],
        edges=[
            ("skill:s1", "procedure:shared-proc", "requires"),
            ("directive:dir-d", "procedure:shared-proc", "requires"),
            ("skill:s2", "procedure:solo-proc", "requires"),
            ("skill:s3", "directive:dir-d", "suggests"),
        ],
    )
    support.write_config(tmp_path, pack)
    return tmp_path


def test_activate_skill_cascades_to_what_it_requires(cascade_project: Path) -> None:
    output = _activate(cascade_project, "--cascade", "procedure,directive", "skill", "s1")

    assert "Cascade-activated: procedure/shared-proc" in output
    assert "shared-proc" in (_activated(cascade_project, "activated_procedures") or [])


def test_activate_skill_cascade_scope_limits_the_kinds(cascade_project: Path) -> None:
    output = _activate(cascade_project, "--cascade", "procedure", "skill", "s3")

    assert "Cascade-activated: directive/dir-d" not in output
    assert "Skipped (out of scope): directive/dir-d" in output


def test_activate_skill_without_cascade_warns_about_referenced_artifacts(cascade_project: Path) -> None:
    output = _activate(cascade_project, "skill", "s1")

    assert "referenced procedure/shared-proc" in output
    assert "Cascade-activated" not in output


def test_deactivate_skill_keeps_a_procedure_still_referenced_by_a_directive(cascade_project: Path) -> None:
    """SC-006: s1 and directive d both require shared-proc; removing s1 keeps it."""
    _activate(cascade_project, "directive", "dir-d")
    _activate(cascade_project, "--cascade", "procedure", "skill", "s1")
    assert "shared-proc" in (_activated(cascade_project, "activated_procedures") or [])

    output = _deactivate(cascade_project, "--cascade", "procedure", "skill", "s1")

    assert "shared-proc" in (_activated(cascade_project, "activated_procedures") or [])
    assert "Skipped (shared artifact)" in output
    assert "directive:dir-d" in output
    assert "s1" not in (_activated(cascade_project, "activated_skills") or [])


def test_deactivate_skill_removes_an_unshared_procedure(cascade_project: Path) -> None:
    """SC-006 control: solo-proc is referenced only by s2, so it goes with it."""
    _activate(cascade_project, "--cascade", "procedure", "skill", "s2")
    assert "solo-proc" in (_activated(cascade_project, "activated_procedures") or [])

    output = _deactivate(cascade_project, "--cascade", "procedure", "skill", "s2")

    assert "Cascade-deactivated: procedure/solo-proc" in output
    assert "solo-proc" not in (_activated(cascade_project, "activated_procedures") or [])
    assert "shared-proc" in (_activated(cascade_project, "activated_procedures") or [])
