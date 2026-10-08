"""Org artifacts enter the DRG without duplicate hand-authored node manifests (#4186)."""

from pathlib import Path

import pytest
import yaml

from charter.activation.action_governance_bundle import _load_action_governance_bundle
from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.drg.org_pack_loader import OrgPackSchemaError, load_org_pack
from specify_cli.cli.commands._doctrine_collect import _collect_org_layer_data

pytestmark = pytest.mark.fast


def _fragment(pack: Path, data: dict) -> None:
    (pack / "drg").mkdir(parents=True, exist_ok=True)
    (pack / "drg" / "fragment.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")


def _artifact(pack: Path, kind: ArtifactKind, data: dict, name: str = "nested/artifact") -> Path:
    path = pack / kind.plural / kind.glob_pattern.replace("*", name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


@pytest.mark.parametrize("authored", [False, True], ids=["inferred", "explicit-control"])
def test_artifact_reaches_doctor_and_only_its_scoped_action(tmp_path: Path, authored: bool) -> None:
    """Existing production seams must deliver a real directive, not just count a node."""
    pack = tmp_path / "pack"
    repo = tmp_path / "consumer"
    (repo / ".kittify").mkdir(parents=True)
    (repo / ".kittify" / "config.yaml").write_text(
        yaml.safe_dump({"charter_packs": {"org": {"packs": [{"name": "acme", "local_path": str(pack)}]}}}),
        encoding="utf-8",
    )
    directive = yaml.safe_load(
        (Path(__file__).resolve().parents[3] / "packs/built-in/directives/001-architectural-integrity-standard.directive.yaml").read_text(encoding="utf-8")
    )
    directive["id"] = "ACME_001_FOO"
    _artifact(pack, ArtifactKind.DIRECTIVE, directive, name="acme")
    _fragment(
        pack,
        {
            "nodes": [{"id": "ACME_001_FOO", "kind": "directives"}] if authored else [],
            "edges": [{"source": "action:software-dev/implement", "target": "directive:ACME_001_FOO", "relation": "scope"}],
        },
    )

    doctor = _collect_org_layer_data(repo)
    assert doctor["errors"] == [], doctor
    assert doctor["configured_packs"][0]["node_count"] == 1
    for action, expected in (("implement", True), ("review", False)):
        bundle = _load_action_governance_bundle(
            repo_root=repo,
            action=action,
            effective_depth=3,
            mission_type="software-dev",
        )
        assert ("ACME_001_FOO" in bundle.directive_ids) is expected
        assert bundle.merged is not None
        nodes = [node for node in bundle.merged.nodes if str(node.urn) == "directive:ACME_001_FOO"]
        assert len(nodes) == 1
        assert nodes[0].provenance == "org:acme"


@pytest.mark.parametrize(
    "kind,plural",
    [
        (ArtifactKind.DIRECTIVE, "directives"),
        (ArtifactKind.TACTIC, "tactics"),
        (ArtifactKind.STYLEGUIDE, "styleguides"),
        (ArtifactKind.TOOLGUIDE, "toolguides"),
        (ArtifactKind.PARADIGM, "paradigms"),
        (ArtifactKind.PROCEDURE, "procedures"),
        (ArtifactKind.AGENT_PROFILE, "agent_profiles"),
        (ArtifactKind.GLOSSARY_PACK, "glossary_packs"),
        (ArtifactKind.ASSET, "assets"),
        (ArtifactKind.MISSION_STEP_CONTRACT, "mission_steps"),
    ],
)
@pytest.mark.parametrize("nodes", [{}, {"nodes": []}])
def test_supported_nested_artifacts_use_declared_identity(tmp_path: Path, kind: ArtifactKind, plural: str, nodes: dict) -> None:
    _fragment(tmp_path, nodes)
    identity = "profile-id" if kind is ArtifactKind.AGENT_PROFILE else "id"
    _artifact(tmp_path, kind, {identity: "real-identity", "name": "Artifact name", "body_path": "bodies/example.md"})
    fragment = load_org_pack("test", tmp_path, 2)
    assert [node.model_dump() for node in fragment.nodes] == [
        {"id": "real-identity", "kind": plural, "title": "Artifact name", "body_path": "bodies/example.md"},
    ]
    assert fragment.pack_name == "test"
    assert fragment.layer_index == 2
    assert fragment.edges == []


def test_additive_inference_preserves_explicit_metadata_and_kind_identity(tmp_path: Path) -> None:
    explicit = {"id": "shared", "kind": "mission_step_contracts", "title": "Authored", "body_path": "authored.md"}
    _fragment(tmp_path, {"nodes": [explicit, {"id": "virtual", "kind": "templates"}]})
    _artifact(tmp_path, ArtifactKind.MISSION_STEP_CONTRACT, {"id": "shared", "title": "Inferred"})
    _artifact(tmp_path, ArtifactKind.DIRECTIVE, {"id": "shared", "title": "First"}, "a")
    _artifact(tmp_path, ArtifactKind.DIRECTIVE, {"id": "shared", "title": "Last"}, "z")
    fragment = load_org_pack("test", tmp_path, 1)
    assert [node.model_dump() for node in fragment.nodes] == [
        {**explicit, "kind": "mission_steps"},
        {"id": "virtual", "kind": "templates", "title": None, "body_path": None},
        {"id": "shared", "kind": "directives", "title": "First", "body_path": None},
    ]


@pytest.mark.parametrize(
    "bad",
    [
        {"id": "real", "kind": "invalid"},
        {"id": "real", "kind": "directives", "title": []},
        {"urn": "directive:real", "kind": "directives"},
    ],
)
def test_invalid_explicit_nodes_still_fail_before_inference(tmp_path: Path, bad: dict) -> None:
    _fragment(tmp_path, {"nodes": [bad]})
    _artifact(tmp_path, ArtifactKind.DIRECTIVE, {"id": "real"})
    with pytest.raises(OrgPackSchemaError):
        load_org_pack("test", tmp_path, 1)


def test_explicit_duplicates_are_not_silently_discarded(tmp_path: Path) -> None:
    node = {"id": "same", "kind": "directives"}
    _fragment(tmp_path, {"nodes": [node, node]})
    _artifact(tmp_path, ArtifactKind.DIRECTIVE, {"id": "same"})
    assert len(load_org_pack("test", tmp_path, 1).nodes) == 2


@pytest.mark.parametrize("content", ["[", "- item", "null", "id: 42", "id: ''", "id: '   '", "name: No identity", "id: real\ntitle: []\nbody_path: 12"])
def test_malformed_artifacts_do_not_invent_identity_or_break_loading(tmp_path: Path, content: str) -> None:
    _fragment(tmp_path, {})
    file = _artifact(tmp_path, ArtifactKind.DIRECTIVE, {})
    file.write_text(content, encoding="utf-8")
    fragment = load_org_pack("test", tmp_path, 1)
    # Optional malformed metadata is ignored; a valid identity remains useful.
    assert [(n.id, n.title, n.body_path) for n in fragment.nodes] == ([("real", None, None)] if content.startswith("id: real") else [])


def test_unrelated_files_and_dangling_edge_targets_are_not_nodes(tmp_path: Path) -> None:
    edge = {"source": "directive:real", "target": "directive:missing", "relation": "requires"}
    _fragment(tmp_path, {"edges": [edge]})
    _artifact(tmp_path, ArtifactKind.DIRECTIVE, {"id": "real", "title": "Actual"})
    (tmp_path / "directives" / "unrelated.yaml").write_text("id: accidental", encoding="utf-8")
    _artifact(tmp_path, ArtifactKind.ANTI_PATTERN, {"id": "not-file-backed"})
    fragment = load_org_pack("test", tmp_path, 1)
    assert [node.id for node in fragment.nodes] == ["real"]
    assert [e.model_dump(exclude_none=True) for e in fragment.edges] == [edge]


def test_unreadable_artifact_and_non_utf8_yaml_are_skipped(tmp_path: Path) -> None:
    _fragment(tmp_path, {})
    artifact = _artifact(tmp_path, ArtifactKind.DIRECTIVE, {}, name="binary")
    artifact.write_bytes(b"\xff\xfe")
    # A directory matching the suffix reaches discovery but cannot be read.
    (tmp_path / "directives" / "directory.directive.yaml").mkdir()
    assert load_org_pack("test", tmp_path, 1).nodes == []
