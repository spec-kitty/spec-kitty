"""Registration facts of the ``skill`` kind (FR-003, SC-008, SC-009)."""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation.context_renderers.delivery_table import _ACTION_BUNDLE_DELIVERY_BY_KIND, _DELIVERY_REASON_BY_KIND
from charter.activation.pack_context import PackContext
from charter.activation.resolver import DoctrineService as ActivationService
from charter.offering.artifact_kinds import (
    CHARTER_ACTIVATABLE_KINDS,
    CHARTER_KIND_TOKENS,
    ORG_REQUIRABLE_KIND_FIELDS,
    PROJECT_KIND_DIRS,
    SELECTION_OVERLAYABLE_KIND_FIELDS,
    ArtifactKind,
)
from charter.offering.drg.migration.extractor import _emit_skill_nodes
from charter.offering.drg.models import DRGNode, NodeKind
from charter.offering.pack_paths import built_in_dir
from charter.offering.service import DoctrineService
from charter.activation.org_charter import (
    REQUIRED_KIND_FIELDS,
    OrgCharterPolicy,
    _fold_policies,
    load_org_charter_policies,
)

from .conftest import prompt_skill, write_skill

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_artifact_kind_facts() -> None:
    kind = ArtifactKind.SKILL
    assert kind.value == "skill"
    assert kind.plural == "skills"
    assert kind.glob_pattern == "*.skill.yaml"
    assert kind.has_built_in_content_dir is True
    assert PROJECT_KIND_DIRS[kind] == "skills"
    assert kind.operator_token == "skill"
    assert ArtifactKind.from_operator_token("skill") is kind
    assert ArtifactKind.from_plural("skills") is kind


def test_skill_is_activatable_and_org_requirable_but_not_selection_overlayable() -> None:
    kind = ArtifactKind.SKILL
    assert kind.activatable is True
    assert kind in CHARTER_ACTIVATABLE_KINDS
    assert "skill" in CHARTER_KIND_TOKENS
    assert kind.org_requirable is True
    assert "skills" in ORG_REQUIRABLE_KIND_FIELDS
    assert kind.selection_overlayable is False
    assert "skills" not in SELECTION_OVERLAYABLE_KIND_FIELDS


def test_built_in_skills_dir_exists() -> None:
    assert built_in_dir(ArtifactKind.SKILL).is_dir()


def test_org_charter_policy_gains_required_skills_and_namespace(tmp_path: Path) -> None:
    assert "skills" in REQUIRED_KIND_FIELDS
    policy = OrgCharterPolicy(required_skills=["land-pr"], skill_namespace="acme")
    assert policy.required_skills == ["land-pr"]
    assert OrgCharterPolicy().required_skills == []
    assert OrgCharterPolicy().skill_namespace is None
    assert OrgCharterPolicy(skill_namespace="x" * 32).skill_namespace == "x" * 32
    assert OrgCharterPolicy(skill_namespace="   ").skill_namespace == "   "  # blank means "not set"; the fold ignores it
    # A bad namespace is refused where a skill is rendered, never by the policy model: it must not
    # take the pack's other policy (here a required directive) down with it.
    for hostile in ("../x", "/abs", "a/b", ".x", "SPK", "café", "acme-", "a\nb", "x" * 33):
        assert OrgCharterPolicy(skill_namespace=hostile, required_directives=["d"]).required_directives == ["d"]
    pack = tmp_path / "pack"
    pack.mkdir()
    (pack / "org-charter.yaml").write_text(
        "schema_version: '1'\norg_name: acme-org\nskill_namespace: Acme\nrequired_directives: [010-fidelity]\n",
        encoding="utf-8",
    )
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify" / "config.yaml").write_text(f"charter_packs:\n  org:\n    packs:\n      - name: acme\n        local_path: {pack}\n", encoding="utf-8")
    loaded = load_org_charter_policies(tmp_path)
    assert loaded.required_directives == ["010-fidelity"]
    assert loaded.org_name == "acme-org"


def test_fold_unions_required_skills_and_last_namespace_wins() -> None:
    folded = _fold_policies(
        [
            OrgCharterPolicy(required_skills=["a", "b"], skill_namespace="first"),
            OrgCharterPolicy(required_skills=["b", "c"]),
            OrgCharterPolicy(skill_namespace="last"),
        ]
    )
    assert folded.required_skills == ["a", "b", "c"]
    assert folded.skill_namespace == "last"
    assert _fold_policies([OrgCharterPolicy(required_skills=["a"])]).skill_namespace is None


def _config(root: Path, body: str) -> None:
    (root / ".kittify").mkdir(parents=True, exist_ok=True)
    (root / ".kittify" / "config.yaml").write_text(body, encoding="utf-8")


def test_pack_context_reads_activated_skills_three_state(tmp_path: Path) -> None:
    _config(tmp_path, "agents:\n  available: [claude]\n")
    # default-in-force (WP03): an absent key is "org-required only" (none here), never None/"all"
    assert PackContext.from_config(tmp_path).activated_skills == frozenset()
    _config(tmp_path, "activated_skills: [land-pr]\n")
    assert PackContext.from_config(tmp_path).activated_skills == frozenset({"land-pr"})
    _config(tmp_path, "activated_skills: []\n")
    assert PackContext.from_config(tmp_path).activated_skills == frozenset()


def test_delivery_table_excludes_skill_with_a_reason() -> None:
    assert _ACTION_BUNDLE_DELIVERY_BY_KIND[NodeKind.SKILL].slot is None
    assert _DELIVERY_REASON_BY_KIND[NodeKind.SKILL]


def test_extractor_emits_nodes_for_built_in_skills_and_nothing_when_absent(tmp_path: Path) -> None:
    nodes: dict[str, DRGNode] = {}
    _emit_skill_nodes(tmp_path, nodes)
    assert nodes == {}

    skills = tmp_path / "skills"
    write_skill(skills, prompt_skill("core-skill"))
    (skills / "no-id.skill.yaml").write_text("title: x\n", encoding="utf-8")
    (skills / "empty.skill.yaml").write_text("", encoding="utf-8")
    _emit_skill_nodes(tmp_path, nodes)
    assert list(nodes) == ["skill:core-skill"]
    assert nodes["skill:core-skill"].kind is NodeKind.SKILL


def _service(tmp_path: Path) -> DoctrineService:
    project = tmp_path / "doctrine"
    write_skill(project / "skills", prompt_skill("alpha"))
    write_skill(project / "skills", prompt_skill("beta"))
    return DoctrineService(project_root=project)


def test_service_exposes_skills_repository(tmp_path: Path) -> None:
    service = _service(tmp_path)
    assert [item.id for item in service.skills.list_all()] == ["alpha", "beta"]
    assert service.skills is service.skills


def test_resolver_filters_skills_by_activation(tmp_path: Path) -> None:
    inner = _service(tmp_path)
    unfiltered = ActivationService(inner, pack_context=None)
    assert set(unfiltered.skills) == {"alpha", "beta"}

    _config(tmp_path, "activated_skills: [beta]\n")
    scoped = ActivationService(inner, pack_context=PackContext.from_config(tmp_path))
    assert set(scoped.skills) == {"beta"}

    _config(tmp_path, "agents:\n  available: [claude]\n")
    absent = ActivationService(inner, pack_context=PackContext.from_config(tmp_path))
    assert set(absent.skills) == set()  # default-in-force: no required skills => none in force
    assert unfiltered.raw_repository("skills") is inner.skills
