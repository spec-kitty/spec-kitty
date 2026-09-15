"""Tests for src/charter/activation/synthesizer/project_drg.py (T021 + T023).

Covers:
- Overlay composition: one node + edges per target.
- Additive-only node collision rejection (FR-020 / EC-6).
- Edge duplicate rejection.
- YAML serialization round-trip via persist().
- Overlay nodes carry correct generated_by.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.activation.synthesizer import project_drg
from charter.activation.synthesizer.errors import ProjectDRGValidationError
from charter.activation.synthesizer.path_guard import PathGuard
from charter.activation.synthesizer.project_drg import emit_project_layer, persist
from charter.activation.synthesizer.request import SynthesisTarget
from charter.offering.drg.loader import load_graph, merge_layers
from charter.offering.drg.models import DRGEdge, DRGGraph, DRGNode, NodeKind, Relation
from charter.offering.drg.project_scan import MalformedProjectProfileError
from charter.offering.drg.validator import validate_graph


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.unit]

def _make_shipped_graph(
    nodes: list[tuple[str, NodeKind]] | None = None,
    edges: list[tuple[str, str, Relation]] | None = None,
) -> DRGGraph:
    """Build a minimal shipped DRGGraph for testing."""
    drg_nodes = [DRGNode(urn=urn, kind=kind) for urn, kind in (nodes or [])]
    drg_edges = [
        DRGEdge(source=src, target=tgt, relation=rel)
        for src, tgt, rel in (edges or [])
    ]
    return DRGGraph(
        schema_version="1.0",
        generated_at="2026-04-17T00:00:00+00:00",
        generated_by="test-shipped-layer",
        nodes=drg_nodes,
        edges=drg_edges,
    )


def _make_target(
    kind: str = "directive",
    slug: str = "project-test-directive",
    artifact_id: str = "PROJECT_001",
    source_section: str | None = "testing_philosophy",
    source_urns: tuple[str, ...] = (),
) -> SynthesisTarget:
    return SynthesisTarget(
        kind=kind,
        slug=slug,
        title=f"Test {kind} title",
        artifact_id=artifact_id,
        source_section=source_section,
        source_urns=source_urns,
    )


# ---------------------------------------------------------------------------
# 0. T003/T005 — the inline serialization loops are extracted into mapping
#    helpers (T003) and then repointed at the derived ``model_to_graph_dict``
#    (T005). The derived shape emits the declared ``DRGNode.tags`` field the old
#    hand-restated shape silently dropped — the defect this WP closes.
# ---------------------------------------------------------------------------


class TestSerializationHelperExtraction:
    """T005: ``_serialize_graph`` builds its dicts via the derived mapping helper.

    The node dict now includes ``tags`` — the field the pre-WP inline loop
    dropped. Both helpers derive their keys from ``model_fields``, so a field a
    later mission adds is emitted without editing this writer.
    """

    def test_node_helper_now_emits_the_previously_dropped_tags_field(self) -> None:
        node = DRGNode(
            urn="directive:PROJECT_001",
            kind=NodeKind.DIRECTIVE,
            label="A label",
            tags=["no-longer-dropped"],
        )
        assert project_drg._node_to_dict(node) == {
            "urn": "directive:PROJECT_001",
            "kind": "directive",
            "label": "A label",
            "tags": ["no-longer-dropped"],
        }

    def test_node_helper_still_omits_empty_tags(self) -> None:
        """Byte-stability for the common overlay node: an empty ``tags`` stays out."""
        node = DRGNode(
            urn="directive:PROJECT_001", kind=NodeKind.DIRECTIVE, label="A label"
        )
        assert project_drg._node_to_dict(node) == {
            "urn": "directive:PROJECT_001",
            "kind": "directive",
            "label": "A label",
        }

    def test_edge_helper_reproduces_the_inline_edge_dict(self) -> None:
        edge = DRGEdge(
            source="directive:PROJECT_001",
            target="directive:DIRECTIVE_003",
            relation=Relation.REQUIRES,
            when="a condition",
            reason="a rationale",
        )
        assert project_drg._edge_to_dict(edge) == {
            "source": "directive:PROJECT_001",
            "target": "directive:DIRECTIVE_003",
            "relation": "requires",
            "when": "a condition",
            "reason": "a rationale",
        }


# ---------------------------------------------------------------------------
# 1. Basic overlay composition
# ---------------------------------------------------------------------------

class TestEmitProjectLayer:
    """Tests for emit_project_layer()."""

    def test_single_directive_target_produces_one_node(self) -> None:
        shipped = _make_shipped_graph()
        target = _make_target(kind="directive", artifact_id="PROJECT_001")
        graph = emit_project_layer([target], "0.1.0", shipped)

        assert {n.urn for n in graph.nodes} == {"directive:PROJECT_001"}
        assert graph.nodes[0].urn == "directive:PROJECT_001"
        assert graph.nodes[0].kind == NodeKind.DIRECTIVE

    def test_tactic_target_produces_tactic_node(self) -> None:
        shipped = _make_shipped_graph()
        target = _make_target(
            kind="tactic",
            slug="how-we-apply-directive-003",
            artifact_id="how-we-apply-directive-003",
        )
        graph = emit_project_layer([target], "0.1.0", shipped)

        assert {n.urn for n in graph.nodes} == {"tactic:how-we-apply-directive-003"}
        assert graph.nodes[0].urn == "tactic:how-we-apply-directive-003"
        assert graph.nodes[0].kind == NodeKind.TACTIC

    def test_styleguide_target_produces_styleguide_node(self) -> None:
        shipped = _make_shipped_graph()
        target = _make_target(
            kind="styleguide",
            slug="python-testing-style",
            artifact_id="python-testing-style",
        )
        graph = emit_project_layer([target], "0.1.0", shipped)

        assert graph.nodes[0].kind == NodeKind.STYLEGUIDE

    def test_node_label_matches_target_title(self) -> None:
        shipped = _make_shipped_graph()
        target = _make_target(kind="directive", artifact_id="PROJECT_001")
        target_with_title = SynthesisTarget(
            kind=target.kind,
            slug=target.slug,
            title="My Custom Title",
            artifact_id=target.artifact_id,
            source_section=target.source_section,
            source_urns=target.source_urns,
        )
        graph = emit_project_layer([target_with_title], "0.1.0", shipped)
        assert graph.nodes[0].label == "My Custom Title"

    def test_generated_by_contains_version(self) -> None:
        shipped = _make_shipped_graph()
        target = _make_target()
        graph = emit_project_layer([target], "1.2.3", shipped)
        assert "1.2.3" in graph.generated_by
        assert "spec-kitty charter synthesize" in graph.generated_by

    def test_schema_version_is_one_zero(self) -> None:
        shipped = _make_shipped_graph()
        target = _make_target()
        graph = emit_project_layer([target], "0.1.0", shipped)
        assert graph.schema_version == "1.0"

    def test_empty_targets_produces_empty_graph(self) -> None:
        shipped = _make_shipped_graph()
        graph = emit_project_layer([], "0.1.0", shipped)
        assert graph.nodes == []
        assert graph.edges == []

    def test_multiple_targets_produce_multiple_nodes(self) -> None:
        shipped = _make_shipped_graph()
        targets = [
            _make_target(kind="directive", slug="p1", artifact_id="PROJECT_001"),
            _make_target(
                kind="tactic",
                slug="how-we-apply-p1",
                artifact_id="how-we-apply-p1",
            ),
        ]
        graph = emit_project_layer(targets, "0.1.0", shipped)
        assert {n.urn for n in graph.nodes} == {
            "directive:PROJECT_001",
            "tactic:how-we-apply-p1",
        }


# ---------------------------------------------------------------------------
# 2. Edge derivation from source_urns
# ---------------------------------------------------------------------------

class TestEdgeDerivedFromSourceUrns:
    """Tests for edges derived from SynthesisTarget.source_urns."""

    def test_directive_source_urn_produces_requires_edge(self) -> None:
        shipped = _make_shipped_graph(
            nodes=[("directive:DIRECTIVE_003", NodeKind.DIRECTIVE)]
        )
        target = _make_target(
            kind="directive",
            artifact_id="PROJECT_001",
            source_urns=("directive:DIRECTIVE_003",),
            source_section=None,
        )
        graph = emit_project_layer([target], "0.1.0", shipped)
        assert {(e.source, e.target, e.relation) for e in graph.edges} == {
            ("directive:PROJECT_001", "directive:DIRECTIVE_003", Relation.REQUIRES)
        }
        edge = graph.edges[0]
        assert edge.source == "directive:PROJECT_001"
        assert edge.target == "directive:DIRECTIVE_003"
        assert edge.relation == Relation.REQUIRES

    def test_tactic_source_urn_produces_applies_edge(self) -> None:
        shipped = _make_shipped_graph(
            nodes=[("directive:DIRECTIVE_003", NodeKind.DIRECTIVE)]
        )
        target = _make_target(
            kind="tactic",
            slug="how-we-apply-003",
            artifact_id="how-we-apply-003",
            source_urns=("directive:DIRECTIVE_003",),
            source_section=None,
        )
        graph = emit_project_layer([target], "0.1.0", shipped)
        assert {(e.source, e.target, e.relation) for e in graph.edges} == {
            ("tactic:how-we-apply-003", "directive:DIRECTIVE_003", Relation.APPLIES)
        }
        assert graph.edges[0].relation == Relation.APPLIES

    def test_multiple_source_urns_produce_multiple_edges(self) -> None:
        shipped = _make_shipped_graph(
            nodes=[
                ("directive:DIRECTIVE_003", NodeKind.DIRECTIVE),
                ("directive:DIRECTIVE_010", NodeKind.DIRECTIVE),
            ]
        )
        target = _make_target(
            kind="directive",
            artifact_id="PROJECT_001",
            source_urns=("directive:DIRECTIVE_003", "directive:DIRECTIVE_010"),
            source_section=None,
        )
        graph = emit_project_layer([target], "0.1.0", shipped)
        assert {(e.source, e.target, e.relation) for e in graph.edges} == {
            ("directive:PROJECT_001", "directive:DIRECTIVE_003", Relation.REQUIRES),
            ("directive:PROJECT_001", "directive:DIRECTIVE_010", Relation.REQUIRES),
        }

    def test_no_source_urns_produces_no_edges(self) -> None:
        shipped = _make_shipped_graph()
        target = _make_target(source_urns=(), source_section="testing_philosophy")
        graph = emit_project_layer([target], "0.1.0", shipped)
        assert graph.edges == []


# ---------------------------------------------------------------------------
# 3. Additive-only enforcement (FR-020 / EC-6, T023)
# ---------------------------------------------------------------------------

class TestAdditiveOnlyEnforcement:
    """Tests for FR-020 / EC-6 — no shadowing of shipped URNs."""

    def test_colliding_node_urn_raises_validation_error(self) -> None:
        shipped = _make_shipped_graph(
            nodes=[("directive:PROJECT_001", NodeKind.DIRECTIVE)]
        )
        target = _make_target(kind="directive", artifact_id="PROJECT_001")
        with pytest.raises(ProjectDRGValidationError) as exc_info:
            emit_project_layer([target], "0.1.0", shipped)
        assert "PROJECT_001" in str(exc_info.value)
        assert "FR-020" in str(exc_info.value)

    def test_error_names_colliding_urn(self) -> None:
        shipped = _make_shipped_graph(
            nodes=[("tactic:how-we-apply-directive-003", NodeKind.TACTIC)]
        )
        target = _make_target(
            kind="tactic",
            slug="how-we-apply-directive-003",
            artifact_id="how-we-apply-directive-003",
        )
        with pytest.raises(ProjectDRGValidationError) as exc_info:
            emit_project_layer([target], "0.1.0", shipped)
        err = exc_info.value
        assert "tactic:how-we-apply-directive-003" in " ".join(err.errors)

    def test_colliding_edge_triple_raises_validation_error(self) -> None:
        # Test the overlay-internal duplicate URN case:
        # Two targets with the same (kind, artifact_id) create the same URN.
        t1 = _make_target(kind="directive", slug="p1", artifact_id="PROJECT_001")
        t2 = _make_target(kind="directive", slug="p1", artifact_id="PROJECT_001")
        with pytest.raises(ProjectDRGValidationError) as exc_info:
            emit_project_layer([t1, t2], "0.1.0", _make_shipped_graph())
        assert "PROJECT_001" in str(exc_info.value)

    def test_shipped_edge_collision_raises_validation_error(self) -> None:
        """A project target that would create a triple already in shipped raises."""
        # Build a shipped graph that already has an edge FROM a shipped node P_SHIP
        # to another shipped node.  Then create a project target whose urn == P_SHIP
        # — but that collides on the NODE level first, which is what we test here.
        # Instead: simulate the edge-level collision:
        # Use the fact that shipped_edge_triples check runs per source_urn.
        # For this to fire: project_urn must NOT be in shipped_nodes (new urn)
        # AND the edge (project_urn, source_urn, relation) must be in shipped_edges.
        # This is structurally impossible for new project URNs unless shipped has
        # a dangling edge pointing FROM the new project URN.
        # So we place a "pre-existing" edge in shipped from the project URN to a shipped node.
        shipped = _make_shipped_graph(
            nodes=[("directive:DIRECTIVE_003", NodeKind.DIRECTIVE)],
            edges=[
                ("directive:PROJECT_001", "directive:DIRECTIVE_003", Relation.REQUIRES)
            ],
        )
        # NOTE: shipped graph has a dangling edge (PROJECT_001 not in nodes) — that's
        # intentional for this test to exercise the EC-6 edge collision path.
        target = _make_target(
            kind="directive",
            artifact_id="PROJECT_001",
            source_urns=("directive:DIRECTIVE_003",),
            source_section=None,
        )
        with pytest.raises(ProjectDRGValidationError) as exc_info:
            emit_project_layer([target], "0.1.0", shipped)
        assert "Duplicate edge" in str(exc_info.value)

    def test_disjoint_urns_succeed(self) -> None:
        shipped = _make_shipped_graph(
            nodes=[("directive:DIRECTIVE_003", NodeKind.DIRECTIVE)]
        )
        target = _make_target(
            kind="directive",
            artifact_id="PROJECT_001",
            source_urns=("directive:DIRECTIVE_003",),
            source_section=None,
        )
        # Should NOT raise
        graph = emit_project_layer([target], "0.1.0", shipped)
        assert {n.urn for n in graph.nodes} == {"directive:PROJECT_001"}


# ---------------------------------------------------------------------------
# 4. YAML serialization round-trip via persist() + load_graph()
# ---------------------------------------------------------------------------

class TestPersistRoundTrip:
    """Tests for persist() — YAML serialization."""

    def test_persisted_graph_roundtrips_via_load_graph(self, tmp_path: Path) -> None:
        shipped = _make_shipped_graph()
        target = _make_target(kind="directive", artifact_id="PROJECT_001")
        graph = emit_project_layer([target], "0.1.0", shipped)

        # Set up PathGuard allowing writes into tmp_path
        guard = PathGuard(
            repo_root=tmp_path,
            extra_allowed_prefixes=[str(tmp_path)],
        )
        staging_dir = tmp_path / "staging"
        staging_dir.mkdir()

        persist(graph, staging_dir, guard)

        written_path = staging_dir / "doctrine" / "graph.yaml"
        assert written_path.exists()

        loaded = load_graph(written_path)
        assert {n.urn for n in loaded.nodes} == {"directive:PROJECT_001"}
        assert loaded.nodes[0].urn == "directive:PROJECT_001"
        assert loaded.generated_by == graph.generated_by

    def test_persisted_graph_passes_validate_graph(self, tmp_path: Path) -> None:
        shipped = _make_shipped_graph(
            nodes=[("directive:DIRECTIVE_003", NodeKind.DIRECTIVE)]
        )
        target = _make_target(
            kind="directive",
            artifact_id="PROJECT_001",
            source_urns=("directive:DIRECTIVE_003",),
            source_section=None,
        )
        graph = emit_project_layer([target], "0.1.0", shipped)
        guard = PathGuard(repo_root=tmp_path, extra_allowed_prefixes=[str(tmp_path)])
        staging_dir = tmp_path / "staging"
        staging_dir.mkdir()
        persist(graph, staging_dir, guard)

        loaded = load_graph(staging_dir / "doctrine" / "graph.yaml")
        # Merge and validate: edges in project may reference shipped nodes.
        merged = merge_layers(shipped, loaded)
        errors = validate_graph(merged)
        assert errors == []

    def test_persist_creates_doctrine_subdir(self, tmp_path: Path) -> None:
        shipped = _make_shipped_graph()
        graph = emit_project_layer([], "0.1.0", shipped)
        guard = PathGuard(repo_root=tmp_path, extra_allowed_prefixes=[str(tmp_path)])
        staging_dir = tmp_path / "staging"
        staging_dir.mkdir()
        persist(graph, staging_dir, guard)
        assert (staging_dir / "doctrine").is_dir()

    def test_persisted_yaml_is_valid_yaml(self, tmp_path: Path) -> None:
        shipped = _make_shipped_graph()
        target = _make_target()
        graph = emit_project_layer([target], "0.1.0", shipped)
        guard = PathGuard(repo_root=tmp_path, extra_allowed_prefixes=[str(tmp_path)])
        staging_dir = tmp_path / "staging"
        staging_dir.mkdir()
        persist(graph, staging_dir, guard)

        yaml_text = (staging_dir / "doctrine" / "graph.yaml").read_text()
        yaml = YAML(typ="safe")
        loaded = yaml.load(yaml_text)
        assert isinstance(loaded, dict)
        assert "nodes" in loaded
        assert "edges" in loaded


# ---------------------------------------------------------------------------
# 5. Integration: merged graph from emit_project_layer + shipped validates
# ---------------------------------------------------------------------------

class TestMergedGraphValidation:
    """Integration: merged (shipped + project) graph validates end-to-end."""

    def test_merged_graph_validates_with_edges(self) -> None:
        shipped = _make_shipped_graph(
            nodes=[("directive:DIRECTIVE_003", NodeKind.DIRECTIVE)]
        )
        target = _make_target(
            kind="directive",
            artifact_id="PROJECT_001",
            source_urns=("directive:DIRECTIVE_003",),
            source_section=None,
        )
        project = emit_project_layer([target], "0.1.0", shipped)
        merged = merge_layers(shipped, project)
        errors = validate_graph(merged)
        assert errors == [], errors

    def test_merged_graph_with_dangling_source_urn_fails_validate(self) -> None:
        """If source_urn references a URN not in shipped, validation detects it."""
        shipped = _make_shipped_graph()  # empty — no nodes
        target = _make_target(
            kind="directive",
            artifact_id="PROJECT_001",
            # This source_urn is NOT in shipped — dangling
            source_urns=("directive:DIRECTIVE_999",),
            source_section=None,
        )
        project = emit_project_layer([target], "0.1.0", shipped)
        merged = merge_layers(shipped, project)
        errors = validate_graph(merged)
        # Should report a dangling target reference
        assert any("DIRECTIVE_999" in e for e in errors)


# ---------------------------------------------------------------------------
# 6. Kind-admission map (M6 / #3038): agent_profile is admitted; asset is not.
# ---------------------------------------------------------------------------

class TestKindAdmission:
    """`_node_kind_for` admits the project-tier emittable-kind allowlist."""

    def test_agent_profile_is_admitted(self) -> None:
        """T002: agent_profile resolves to NodeKind.AGENT_PROFILE (was None on base)."""
        assert project_drg._node_kind_for("agent_profile") is NodeKind.AGENT_PROFILE

    def test_directive_tactic_styleguide_still_admitted(self) -> None:
        assert project_drg._node_kind_for("directive") is NodeKind.DIRECTIVE
        assert project_drg._node_kind_for("tactic") is NodeKind.TACTIC
        assert project_drg._node_kind_for("styleguide") is NodeKind.STYLEGUIDE

    def test_asset_is_not_admitted(self) -> None:
        """T008 (INV-4): asset stays reference-only — never emitted as a project node."""
        assert project_drg._node_kind_for("asset") is None

    def test_unknown_and_non_emittable_kinds_are_none(self) -> None:
        """T008: a non-ArtifactKind string and non-emittable kinds resolve to None."""
        assert project_drg._node_kind_for("not-a-kind") is None
        assert project_drg._node_kind_for("procedure") is None
        assert project_drg._node_kind_for("template") is None


# ---------------------------------------------------------------------------
# 7. Project-tier agent_profile walk (T006) + compose guards (T007/T008).
# ---------------------------------------------------------------------------

def _write_profile(root: Path, name: str, profile_id: str, display: str | None = "Reviewer Rhonda") -> Path:
    profiles_dir = root / ".kittify" / "doctrine" / "agent_profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    path = profiles_dir / f"{name}.agent.yaml"
    body = f"profile-id: {profile_id}\n"
    if display is not None:
        body += f"name: {display}\n"
    path.write_text(body, encoding="utf-8")
    return path


class TestProjectProfileWalk:
    """Unit coverage for the reusable walk under src/doctrine/drg/."""

    def test_walk_yields_agent_profile_node(self, tmp_path: Path) -> None:
        from charter.offering.drg.project_scan import walk_project_agent_profile_nodes

        _write_profile(tmp_path, "reviewer-rhonda", "reviewer-rhonda")
        nodes = walk_project_agent_profile_nodes(tmp_path)
        assert len(nodes) == 1
        node = nodes[0]
        assert node.urn == "agent_profile:reviewer-rhonda"
        assert node.kind is NodeKind.AGENT_PROFILE
        assert node.label == "Reviewer Rhonda"
        assert node.provenance == "project"

    def test_walk_missing_dir_returns_empty(self, tmp_path: Path) -> None:
        from charter.offering.drg.project_scan import walk_project_agent_profile_nodes

        assert walk_project_agent_profile_nodes(tmp_path) == []

    def test_walk_is_recursive_and_sorted(self, tmp_path: Path) -> None:
        from charter.offering.drg.project_scan import walk_project_agent_profile_nodes

        profiles_dir = tmp_path / ".kittify" / "doctrine" / "agent_profiles"
        (profiles_dir / "nested").mkdir(parents=True, exist_ok=True)
        (profiles_dir / "zeta.agent.yaml").write_text("profile-id: zeta\nname: Zeta\n", encoding="utf-8")
        (profiles_dir / "nested" / "alpha.agent.yaml").write_text(
            "profile-id: alpha\nname: Alpha\n", encoding="utf-8"
        )
        urns = [n.urn for n in walk_project_agent_profile_nodes(tmp_path)]
        assert urns == ["agent_profile:alpha", "agent_profile:zeta"]

    def test_walk_missing_profile_id_fails_loud_naming_file(self, tmp_path: Path) -> None:
        """T008 / NFR-002: a profile without profile-id raises, naming the file."""
        from charter.offering.drg.project_scan import walk_project_agent_profile_nodes

        path = _write_profile(tmp_path, "broken", "placeholder")
        path.write_text("name: No Id Here\n", encoding="utf-8")
        with pytest.raises(MalformedProjectProfileError, match=r"broken\.agent\.yaml"):
            walk_project_agent_profile_nodes(tmp_path)

    def test_walk_unparseable_yaml_fails_loud_naming_file(self, tmp_path: Path) -> None:
        """T008 / NFR-002: malformed YAML raises, naming the file — no silent skip."""
        from charter.offering.drg.project_scan import walk_project_agent_profile_nodes

        path = _write_profile(tmp_path, "malformed", "placeholder")
        path.write_text("profile-id: [unterminated\n", encoding="utf-8")
        with pytest.raises(MalformedProjectProfileError, match=r"malformed\.agent\.yaml"):
            walk_project_agent_profile_nodes(tmp_path)

    def test_walk_urn_unsafe_profile_id_fails_loud_naming_file(self, tmp_path: Path) -> None:
        """NFR-002: a URN-unsafe profile-id raises MalformedProjectProfileError
        naming the file — not a raw pydantic ValidationError that hides it."""
        from charter.offering.drg.project_scan import walk_project_agent_profile_nodes

        # Trailing space / embedded colon / non-ASCII would form an invalid
        # ``agent_profile:<id>`` URN and otherwise surface as a bare pydantic error.
        _write_profile(tmp_path, "spacey", "has a space")
        with pytest.raises(MalformedProjectProfileError, match=r"spacey\.agent\.yaml"):
            walk_project_agent_profile_nodes(tmp_path)


class TestComposeProjectProfileNodes:
    """emit_project_layer composes walked nodes through the additive/dedupe guards."""

    def test_walked_profile_node_appears_in_overlay(self, tmp_path: Path) -> None:
        _write_profile(tmp_path, "reviewer-rhonda", "reviewer-rhonda")
        shipped = _make_shipped_graph()
        graph = emit_project_layer([], "0.1.0", shipped, project_root=tmp_path)
        urns = {n.urn for n in graph.nodes}
        assert "agent_profile:reviewer-rhonda" in urns

    def test_walked_profile_collision_with_built_in_rejected(self, tmp_path: Path) -> None:
        """T008 / INV-1: a project profile URN colliding with a built-in node is rejected."""
        _write_profile(tmp_path, "researcher-ryan", "researcher-ryan")
        shipped = _make_shipped_graph(
            nodes=[("agent_profile:researcher-ryan", NodeKind.AGENT_PROFILE)]
        )
        with pytest.raises(ProjectDRGValidationError):
            emit_project_layer([], "0.1.0", shipped, project_root=tmp_path)

    def test_duplicate_profile_id_across_files_fails_loud(self, tmp_path: Path) -> None:
        """NFR-002: the SAME profile-id in two authored files fails loud (naming
        both), rather than one silently winning — a dropped overlay node is the
        governance-invisible defect the walk exists to prevent."""
        profiles_dir = tmp_path / ".kittify" / "doctrine" / "agent_profiles"
        (profiles_dir / "a").mkdir(parents=True, exist_ok=True)
        (profiles_dir / "b").mkdir(parents=True, exist_ok=True)
        (profiles_dir / "a" / "dup.agent.yaml").write_text(
            "profile-id: dup\nname: Dup A\n", encoding="utf-8"
        )
        (profiles_dir / "b" / "dup.agent.yaml").write_text(
            "profile-id: dup\nname: Dup B\n", encoding="utf-8"
        )
        shipped = _make_shipped_graph()
        with pytest.raises(MalformedProjectProfileError, match=r"dup"):
            emit_project_layer([], "0.1.0", shipped, project_root=tmp_path)

    def test_no_project_root_is_answer_driven_only(self, tmp_path: Path) -> None:
        """Omitting project_root preserves pre-M6 answer-driven-only behaviour."""
        _write_profile(tmp_path, "reviewer-rhonda", "reviewer-rhonda")
        shipped = _make_shipped_graph()
        graph = emit_project_layer([], "0.1.0", shipped)
        assert graph.nodes == []
