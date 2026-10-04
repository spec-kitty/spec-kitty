"""``prepare_skill_activations``: the pure charter-side preparation of activated pack skills (WP03, T014)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from charter.activation.skill_preparation import (
    _PROJECT_NAMESPACE_CONFIG_PATH,
    SkillPreparationError,
    prepare_project_skill_activations,
    _prepare_skill_activations,
    _read_project_skill_namespace,
)
from charter.drg import DRGEdge, DRGGraph, DRGNode, NodeKind, Relation
from charter.offering.pack_skills.models import PackSkill
from kernel.content_digest import sha256_digest

from . import skill_pack_support as support

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _skill(skill_id: str, **extra: object) -> PackSkill:
    data: dict[str, object] = {
        "schema_version": "1.0",
        "id": skill_id,
        "title": f"Skill {skill_id}",
        "description": "d",
        "form": "prompt",
        "body_path": f"{skill_id}.skill.md",
    }
    data.update(extra)
    return PackSkill.model_validate(data)


def _wrapper(skill_id: str) -> PackSkill:
    return PackSkill.model_validate(
        {
            "schema_version": "1.0",
            "id": skill_id,
            "title": "t",
            "description": "d",
            "form": "wrapper",
            "expands_to": {"target": "builtin:spec-kitty.consolidate", "args": "--strategy squash $ARGUMENTS"},
        }
    )


class FakeSource:
    """In-memory :class:`_SkillSource`."""

    def __init__(self) -> None:
        self.skills: dict[str, PackSkill] = {}
        self.tiers: dict[str, str] = {}
        self.bodies: dict[str, str] = {}

    def add(self, skill: PackSkill, tier: str, body: str | None = "body\n") -> FakeSource:
        self.skills[skill.id] = skill
        self.tiers[skill.id] = tier
        if body is not None:
            self.bodies[skill.id] = body
        return self

    def get(self, item_id: str) -> PackSkill | None:
        return self.skills.get(item_id)

    def source_path(self, skill_id: str) -> Path | None:
        return Path(f"/packs/{self.tiers[skill_id]}/skills/{skill_id}.skill.yaml") if skill_id in self.skills else None

    def provenance_of(self, skill_id: str) -> str | None:
        return self.tiers.get(skill_id)

    def body_text(self, skill_id: str) -> str | None:
        return self.bodies.get(skill_id)


def _graph(*edges: tuple[str, str, Relation]) -> DRGGraph:
    urns = {urn for source, target, _ in edges for urn in (source, target)}
    kinds = {"skill": NodeKind.SKILL, "procedure": NodeKind.PROCEDURE, "directive": NodeKind.DIRECTIVE}
    return DRGGraph(
        schema_version="1.0",
        generated_at="2026-10-04T00:00:00Z",
        generated_by="test",
        nodes=[DRGNode(urn=urn, kind=kinds[urn.partition(":")[0]]) for urn in sorted(urns)],
        edges=[DRGEdge(source=s, target=t, relation=r) for s, t, r in edges],
    )


def _prepare(source: FakeSource, ids: list[str], *, org: str | None = "acme", project: str | None = "proj", graph: DRGGraph | None = None):
    return _prepare_skill_activations(source, ids, graph=graph or _graph(), org_namespace=org, project_namespace=project)


# ---------------------------------------------------------------------------
# Record contents
# ---------------------------------------------------------------------------


def test_org_prompt_skill_is_prepared_with_namespace_body_and_requires() -> None:
    source = FakeSource().add(_skill("land-pr"), "org", body="Land: $ARGUMENTS\n")
    graph = _graph(
        ("skill:land-pr", "procedure:landing", Relation.REQUIRES),
        ("skill:land-pr", "directive:no-heavy", Relation.REQUIRES),
        ("skill:land-pr", "directive:nice-to-have", Relation.SUGGESTS),
        ("skill:other", "procedure:unrelated", Relation.REQUIRES),
    )

    (prepared,) = _prepare(source, ["land-pr"], graph=graph)

    assert prepared.id == "land-pr"
    assert prepared.tier == "org"
    assert prepared.rendered_name == "acme-land-pr"
    assert prepared.form == "prompt"
    assert prepared.body == "Land: $ARGUMENTS\n"
    assert prepared.expansion is None
    assert prepared.requires == ("directive:no-heavy", "procedure:landing")
    assert prepared.source_path == Path("/packs/org/skills/land-pr.skill.yaml")
    assert prepared.skill is source.skills["land-pr"]


def test_wrapper_skill_keeps_its_builtin_target_unresolved() -> None:
    source = FakeSource().add(_wrapper("ship"), "org", body=None)

    (prepared,) = _prepare(source, ["ship"])

    assert prepared.form == "wrapper"
    assert prepared.body is None
    assert prepared.expansion is not None
    assert prepared.expansion.target == "builtin:spec-kitty.consolidate"
    assert prepared.expansion.args == "--strategy squash $ARGUMENTS"
    assert prepared.requires == ()


def test_builtin_skill_renders_under_its_bare_id_without_a_namespace() -> None:
    source = FakeSource().add(_skill("spk-demo"), "builtin")
    (prepared,) = _prepare(source, ["spk-demo"], org=None, project=None)
    assert prepared.rendered_name == "spk-demo"
    assert prepared.tier == "builtin"


def test_project_skill_uses_the_project_namespace() -> None:
    source = FakeSource().add(_skill("notes"), "project")
    (prepared,) = _prepare(source, ["notes"], org="acme", project="mine")
    assert prepared.rendered_name == "mine-notes"
    assert prepared.tier == "project"


def test_output_is_sorted_by_id_and_deduplicated() -> None:
    source = FakeSource().add(_skill("b"), "org").add(_skill("a"), "org")
    assert [p.id for p in _prepare(source, ["b", "a", "b"])] == ["a", "b"]


def test_nothing_activated_prepares_nothing() -> None:
    assert _prepare(FakeSource(), []) == []


# ---------------------------------------------------------------------------
# source_hash
# ---------------------------------------------------------------------------


def _expected_hash(skill: PackSkill, body: str | None, requires: list[str], name: str) -> str:
    inputs = {"record": skill.model_dump(mode="json"), "requires": requires, "rendered_name": name}
    return sha256_digest(json.dumps(inputs, sort_keys=True).encode("utf-8") + b"\0" + (body or "").encode("utf-8"))


def test_source_hash_covers_record_requires_rendered_name_and_body_bytes() -> None:
    skill = _skill("land-pr")
    source = FakeSource().add(skill, "org", body="héllo\n")

    (prepared,) = _prepare(source, ["land-pr"])

    assert prepared.source_hash == _expected_hash(skill, "héllo\n", [], "acme-land-pr")
    assert prepared.source_hash.startswith("sha256:")


def test_source_hash_changes_with_the_body_and_with_the_record() -> None:
    base = _prepare(FakeSource().add(_skill("a"), "org", body="one"), ["a"])[0].source_hash
    other_body = _prepare(FakeSource().add(_skill("a"), "org", body="two"), ["a"])[0].source_hash
    other_record = _prepare(FakeSource().add(_skill("a", title="renamed"), "org", body="one"), ["a"])[0].source_hash
    assert len({base, other_body, other_record}) == 3


def test_source_hash_is_stable_for_the_same_input_and_tracks_the_rendered_name() -> None:
    again = [_prepare(FakeSource().add(_skill("a"), "org"), ["a"], org="one")[0].source_hash for _ in range(2)]
    other_namespace = _prepare(FakeSource().add(_skill("a"), "org"), ["a"], org="two")[0].source_hash
    assert again[0] == again[1]
    assert other_namespace != again[0]  # the rendered name is a rendered-output input


def test_wrapper_hash_has_no_body_component() -> None:
    wrapper = _wrapper("ship")
    (prepared,) = _prepare(FakeSource().add(wrapper, "org", body=None), ["ship"])
    assert prepared.source_hash == _expected_hash(wrapper, None, [], prepared.rendered_name)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


def test_project_skill_without_a_namespace_is_refused_with_the_config_key_as_remedy() -> None:
    source = FakeSource().add(_skill("notes"), "project")
    with pytest.raises(SkillPreparationError) as excinfo:
        _prepare(source, ["notes"], project=None)
    assert _PROJECT_NAMESPACE_CONFIG_PATH in str(excinfo.value)
    assert "'notes'" in str(excinfo.value)


def test_org_skill_without_a_namespace_is_refused_with_the_org_charter_key_as_remedy() -> None:
    source = FakeSource().add(_skill("land-pr"), "org")
    with pytest.raises(SkillPreparationError, match="skill_namespace.*org-charter.yaml"):
        _prepare(source, ["land-pr"], org=None)


def test_blank_namespace_counts_as_missing() -> None:
    with pytest.raises(SkillPreparationError, match="no skill namespace"):
        _prepare(FakeSource().add(_skill("a"), "org"), ["a"], org="")


@pytest.mark.parametrize(
    ("namespace", "reason"),
    [
        ("spk", "reserved for built-in"),
        ("spec-kitty", "reserved for built-in"),
        # Upper-case variants of the reserved prefixes are not accepted at all.
        ("SPK", "not valid"),
        ("Spec-Kitty", "not valid"),
        # Directory-escaping, hidden, malformed, non-ASCII and over-long values (never normalised).
        ("../x", "not valid"),
        ("/etc/x", "not valid"),
        ("a/b", "not valid"),
        (".x", "not valid"),
        ("~", "not valid"),
        ("a b", "not valid"),
        ("acme-", "not valid"),
        ("ac\nme", "not valid"),
        ("café", "not valid"),
        ("аcme", "not valid"),  # leading Cyrillic look-alike of "a"
        ("x" * 33, "not valid"),
    ],
)
def test_a_namespace_that_renders_a_reserved_prefix_or_is_not_a_safe_name_is_refused(namespace: str, reason: str) -> None:
    with pytest.raises(SkillPreparationError, match=reason):
        _prepare(FakeSource().add(_skill("demo"), "org"), ["demo"], org=namespace)


def test_two_skills_rendering_to_the_same_name_fail_before_anything_is_returned() -> None:
    source = FakeSource().add(_skill("b-c"), "org").add(_skill("c"), "project")
    with pytest.raises(SkillPreparationError, match="both render as 'a-b-c'"):
        _prepare(source, ["b-c", "c"], org="a", project="a-b")


def test_distinct_rendered_names_do_not_collide() -> None:
    source = FakeSource().add(_skill("same"), "org").add(_skill("same-too"), "project")
    assert [p.rendered_name for p in _prepare(source, ["same", "same-too"])] == ["acme-same", "proj-same-too"]


def test_an_activated_id_missing_from_every_tier_is_refused() -> None:
    with pytest.raises(SkillPreparationError, match="not available in any pack tier"):
        _prepare(FakeSource(), ["ghost"])


def test_unknown_provenance_is_refused() -> None:
    source = FakeSource().add(_skill("a"), "mystery")
    with pytest.raises(SkillPreparationError, match="unknown provenance 'mystery'"):
        _prepare(source, ["a"])


# ---------------------------------------------------------------------------
# _read_project_skill_namespace
# ---------------------------------------------------------------------------


def _config(tmp_path: Path, text: str) -> Path:
    config = tmp_path / ".kittify" / "config.yaml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(text, encoding="utf-8")
    return tmp_path


def test_project_namespace_is_read_from_the_nested_config_key(tmp_path: Path) -> None:
    assert _read_project_skill_namespace(_config(tmp_path, "charter_packs:\n  project:\n    skill_namespace: ' mine '\n")) == "mine"
    for hostile in ("../x", "/etc/x", "Mine", "café", "mine-"):  # refused where it is read, never normalised
        text = f"charter_packs:\n  project:\n    skill_namespace: {hostile!r}\n"
        with pytest.raises(SkillPreparationError, match="not valid.*charter_packs.project.skill_namespace"):
            _read_project_skill_namespace(_config(tmp_path, text))


@pytest.mark.parametrize(
    "text",
    [
        "other: 1\n",
        "charter_packs: nope\n",
        "charter_packs:\n  project: nope\n",
        "charter_packs:\n  project:\n    skill_namespace: 3\n",
        "charter_packs:\n  project:\n    skill_namespace: '  '\n",
        "",
    ],
)
def test_project_namespace_absent_or_malformed_is_none(tmp_path: Path, text: str) -> None:
    assert _read_project_skill_namespace(_config(tmp_path, text)) is None


def test_project_namespace_without_a_config_file_is_none(tmp_path: Path) -> None:
    assert _read_project_skill_namespace(tmp_path) is None


def test_project_namespace_with_invalid_yaml_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(SkillPreparationError, match="cannot read"):
        _read_project_skill_namespace(_config(tmp_path, "a: [unclosed\n"))


# ---------------------------------------------------------------------------
# Project-level wiring: default-in-force + merged DRG + both namespaces
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_project_preparation_uses_the_effective_set_the_merged_graph_and_namespaces(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    pack.mkdir()
    for skill_id in ("required-one", "x", "y"):
        support.write_skill(pack, skill_id)
    support.write_procedure(pack, "proc-p")
    support.write_fragment(
        pack,
        nodes=[("skill:x", "skill"), ("procedure:proc-p", "procedure")],
        edges=[("skill:x", "procedure:proc-p", "requires")],
    )
    support.write_org_charter(pack, required_skills=["required-one"], namespace="acme")
    support.write_config(tmp_path, pack, extra="activated_skills: [required-one, x, notes]\n", project_namespace="mine")
    support.write_skill(tmp_path / ".kittify" / "doctrine", "notes")

    prepared = {p.id: p for p in prepare_project_skill_activations(tmp_path)}

    assert set(prepared) == {"required-one", "x", "notes"}
    assert prepared["x"].rendered_name == "acme-x"
    assert prepared["x"].tier == "org"
    assert prepared["x"].requires == ("procedure:proc-p",)
    assert prepared["x"].body == "Run x: $ARGUMENTS\n"
    assert prepared["notes"].tier == "project"
    assert prepared["notes"].rendered_name == "mine-notes"
    assert prepared["notes"].requires == ()


@pytest.mark.integration
def test_project_preparation_default_in_force_is_only_the_required_skills(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    pack.mkdir()
    for skill_id in ("required-one", "x"):
        support.write_skill(pack, skill_id)
    support.write_org_charter(pack, required_skills=["required-one"])
    support.write_config(tmp_path, pack)

    assert [p.rendered_name for p in prepare_project_skill_activations(tmp_path)] == ["acme-required-one"]

    # An id required by the org but present in no pack tier is refused, not resolved cleanly.
    support.write_org_charter(pack, required_skills=["required-one", "ghost"])
    with pytest.raises(SkillPreparationError, match="ghost"):
        prepare_project_skill_activations(tmp_path)

    # A required skill whose record stopped loading is refused naming it, never silently dropped.
    support.write_org_charter(pack, required_skills=["required-one"])
    record = pack / "skills" / "required-one.skill.yaml"
    record.write_text(record.read_text(encoding="utf-8").replace("{", "{unknown_key: 1, ", 1), encoding="utf-8")
    with pytest.warns(UserWarning, match="Skipping invalid org pack-skill"), pytest.raises(SkillPreparationError, match="(?s)required-one.*unknown_key"):
        prepare_project_skill_activations(tmp_path)


@pytest.mark.integration
def test_project_preparation_refuses_a_project_skill_without_a_namespace(tmp_path: Path) -> None:
    support.write_config(tmp_path, None, extra="activated_skills: [notes]\n")
    support.write_skill(tmp_path / ".kittify" / "doctrine", "notes")

    with pytest.raises(SkillPreparationError, match=_PROJECT_NAMESPACE_CONFIG_PATH.replace(".", r"\.")):
        prepare_project_skill_activations(tmp_path)
