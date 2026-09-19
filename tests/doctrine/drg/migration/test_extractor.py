"""Tests for charter.offering.drg.migration.extractor.

Includes:
- T012/T013 unit tests against real shipped doctrine
- T016 end-to-end graph generation
- T017 edge-count completeness validation
- Idempotency verification
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

from charter.offering.drg.loader import built_in_graph_source
from charter.offering.drg.migration.calibrator import measure_surface
from charter.offering.drg.migration.extractor import (
    _AGENT_PROFILE_IMPLEMENTER_IVAN,
    _CURATED_ARTIFACT_EDGES,
    _SKIP_REF_TYPES,
    _discover_built_in_nodes_in_dir,
    _partition_by_kind,
    _relation_for_procedure_ref_type,
    assert_governance_scope_edges_resolve,
    extract_action_edges,
    extract_artifact_edges,
    extract_governance_profile_scope_edges,
    extract_mission_type_edges,
    generate_graph,
)
from charter.offering.drg.migration.hand_authored_overlay import write_reference_graph_with_overlay
from charter.offering.drg.migration.id_normalizer import artifact_to_urn
from charter.offering.drg.models import DRGEdge, DRGGraph, DRGNode, NodeKind, Relation
from charter.offering.drg.query import resolve_context
from charter.offering.drg.validator import validate_graph
from charter.offering.missions.mission_type_repository import MissionTypeRepository

# Path to the shipped doctrine root inside the repo.

pytestmark = [pytest.mark.doctrine, pytest.mark.fast, pytest.mark.corpus]
DOCTRINE_ROOT: Path = Path(__file__).resolve().parents[4] / "src" / "charter" / "offering"

_yaml = YAML(typ="safe")


def _count_inline_refs(doctrine_root: Path) -> int:  # noqa: C901
    """Count every inline reference field entry across all shipped artifacts.

    This mirrors the extraction logic but only counts -- used for the T017
    completeness assertion.
    """
    total = 0

    # Directives
    directives_dir = built_in_graph_source() / "directives"
    if directives_dir.is_dir():
        for path in sorted(directives_dir.glob("*.directive.yaml")):
            data: Any = _yaml.load(path)
            if not data:
                continue
            total += len(data.get("tactic_refs", []) or [])
            for ref in data.get("references", []) or []:
                if ref.get("type", "") not in _SKIP_REF_TYPES:
                    total += 1

    # Tactics
    tactics_dir = built_in_graph_source() / "tactics"
    if tactics_dir.is_dir():
        for path in sorted(tactics_dir.rglob("*.tactic.yaml")):
            data = _yaml.load(path)
            if not data:
                continue
            for ref in data.get("references", []) or []:
                if ref.get("type", "") not in _SKIP_REF_TYPES:
                    total += 1
            for step in data.get("steps", []) or []:
                for ref in step.get("references", []) or []:
                    if ref.get("type", "") not in _SKIP_REF_TYPES:
                        total += 1

    # Paradigms
    paradigms_dir = built_in_graph_source() / "paradigms"
    if paradigms_dir.is_dir():
        for path in sorted(paradigms_dir.glob("*.paradigm.yaml")):
            data = _yaml.load(path)
            if not data:
                continue
            total += len(data.get("tactic_refs", []) or [])
            total += len(data.get("directive_refs", []) or [])
            for ref in data.get("references", []) or []:
                if ref.get("type", "") not in _SKIP_REF_TYPES:
                    total += 1

    # Procedures
    procedures_dir = built_in_graph_source() / "procedures"
    if procedures_dir.is_dir():
        for path in sorted(procedures_dir.glob("*.procedure.yaml")):
            data = _yaml.load(path)
            if not data:
                continue
            for ref in data.get("references", []) or []:
                if ref.get("type", "") not in _SKIP_REF_TYPES:
                    total += 1

    # Action indices
    missions_dir = doctrine_root / "missions"
    if missions_dir.is_dir():
        for index_path in sorted(missions_dir.rglob("actions/*/index.yaml")):
            data = _yaml.load(index_path)
            if not data:
                continue
            for field in (
                "directives",
                "tactics",
                "paradigms",
                "styleguides",
                "toolguides",
                "procedures",
                "agent_profiles",
            ):
                total += len(data.get(field, []) or [])

    # Agent profiles
    profiles_dir = built_in_graph_source() / "agent_profiles"
    if profiles_dir.is_dir():
        for path in sorted(profiles_dir.glob("*.agent.yaml")):
            data = _yaml.load(path)
            if not data:
                continue
            # Consolidated onto the canonical ``*-references`` surface (mission
            # doctrine-drg-silent-drop-boundary-01M0PE7E); the retired
            # ``context-sources.directives`` projection is now
            # ``directive-references``, and toolguide/styleguide references newly
            # project as ``suggests`` edges.
            total += len(data.get("directive-references", []) or [])
            total += len(data.get("tactic-references", []) or [])
            total += len(data.get("toolguide-references", []) or [])
            total += len(data.get("styleguide-references", []) or [])

    return total


# ---------------------------------------------------------------------------
# T012: Artifact walker tests
# ---------------------------------------------------------------------------


@pytest.mark.doctrine
class TestExtractArtifactEdges:
    def test_returns_nodes_and_edges(self) -> None:
        nodes, edges = extract_artifact_edges(DOCTRINE_ROOT)
        assert len(nodes) > 0
        assert len(edges) > 0

    def test_directive_nodes_present(self) -> None:
        nodes, _ = extract_artifact_edges(DOCTRINE_ROOT)
        directive_urns = {n.urn for n in nodes if n.kind == NodeKind.DIRECTIVE}
        # We know DIRECTIVE_001, DIRECTIVE_024, DIRECTIVE_003 exist
        assert "directive:DIRECTIVE_001" in directive_urns
        assert "directive:DIRECTIVE_024" in directive_urns
        assert "directive:DIRECTIVE_003" in directive_urns

    def test_tactic_nodes_present(self) -> None:
        nodes, _ = extract_artifact_edges(DOCTRINE_ROOT)
        tactic_urns = {n.urn for n in nodes if n.kind == NodeKind.TACTIC}
        assert "tactic:tdd-red-green-refactor" in tactic_urns
        assert "tactic:adr-drafting-workflow" in tactic_urns

    def test_paradigm_nodes_present(self) -> None:
        nodes, _ = extract_artifact_edges(DOCTRINE_ROOT)
        paradigm_urns = {n.urn for n in nodes if n.kind == NodeKind.PARADIGM}
        assert "paradigm:domain-driven-design" in paradigm_urns
        assert "paradigm:atomic-design" in paradigm_urns
        assert "paradigm:c4-incremental-detail-modeling" in paradigm_urns

    def test_no_duplicate_nodes(self) -> None:
        nodes, _ = extract_artifact_edges(DOCTRINE_ROOT)
        urns = [n.urn for n in nodes]
        assert len(urns) == len(set(urns)), "Duplicate node URNs found"

    # One migration-extractor regression test was deleted in WP03 of the
    # excise-doctrine-curation-and-inline-references-01KP54J6 mission;
    # it exercised the pre-WP02 inline-reference path that no longer has
    # shipped input data. The migration extractor itself remains covered
    # by the other TestExtractArtifactEdges cases.
    #
    # The directive-tension "produces replaces" regression test was removed
    # in WP03 of doctrine-tension-edges-01KY1WPC: the extractor no longer
    # mints ``replaces`` edges from the retired contradiction-declaration
    # field. The 024<->025 tension it exercised is now a hand-authored
    # ``in_tension_with`` edge -- covered by
    # ``tests/doctrine/drg/test_graph_sharding_equality.py`` and the
    # freshness-canary tests in this module, not duplicated here.

    def test_paradigm_directive_refs_normalised(self) -> None:
        """Paradigm directive_refs (DIRECTIVE_NNN format) should be normalised."""
        _, edges = extract_artifact_edges(DOCTRINE_ROOT)
        ddd_requires = [
            e for e in edges
            if e.source == "paradigm:domain-driven-design"
            and e.relation == Relation.REQUIRES
            and e.target.startswith("directive:")
        ]
        targets = {e.target for e in ddd_requires}
        assert "directive:DIRECTIVE_001" in targets
        assert "directive:DIRECTIVE_031" in targets
        assert "directive:DIRECTIVE_032" in targets

    def test_curated_paradigm_tactic_edges_are_preserved(self) -> None:
        """Curated paradigm tactic edges should survive regeneration."""
        _, edges = extract_artifact_edges(DOCTRINE_ROOT)
        targets = {
            e.target
            for e in edges
            if e.source == "paradigm:specification-by-example"
            and e.relation == Relation.REQUIRES
        }
        assert "tactic:usage-examples-sync" in targets

    def test_tactic_references_produce_suggests(self) -> None:
        """Tactic references should produce 'suggests' edges."""
        _, edges = extract_artifact_edges(DOCTRINE_ROOT)
        pd_suggests = [
            e for e in edges
            if e.source == "tactic:problem-decomposition"
            and e.relation == Relation.SUGGESTS
        ]
        # problem-decomposition has 4 top-level refs (skipping template)
        # -> eisenhower-prioritisation, stakeholder-alignment, review-intent-and-risk-first
        targets = {e.target for e in pd_suggests}
        assert "tactic:eisenhower-prioritisation" in targets

    def test_duplicate_tactic_refs_preserve_metadata(self, tmp_path: Path) -> None:
        """Duplicate triples merge metadata instead of keeping the bare edge.

        Injects a synthetic tactic under a flattened pack root (``<root>/tactics``
        — no inner ``built-in``); a synthetic root is honoured as-is by the
        extractor's artifact-root resolver.
        """
        doctrine_root = tmp_path / "pack"
        tactics_dir = doctrine_root / "tactics"
        tactics_dir.mkdir(parents=True)
        (tactics_dir / "metadata-merge.tactic.yaml").write_text(
            "\n".join(
                [
                    "schema_version: '1.0'",
                    "id: metadata-merge",
                    "name: Metadata Merge",
                    "purpose: test",
                    "references:",
                    "  - type: tactic",
                    "    id: target-tactic",
                    "  - type: tactic",
                    "    id: target-tactic",
                    "    when: Preserve this metadata.",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        _, edges = extract_artifact_edges(doctrine_root)

        edge = next(
            edge
            for edge in edges
            if edge.source == "tactic:metadata-merge"
            and edge.target == "tactic:target-tactic"
        )
        assert edge.when == "Preserve this metadata."

    def test_directive_reference_reason_roundtrips(self, tmp_path: Path) -> None:
        """A directive ``references`` entry carries ``reason`` symmetrically with
        ``when`` (#3009 residual, WP02/T007). Backward-compatible: an entry with
        no ``reason`` yields ``reason=None``.

        This is the extractor capability that makes the overlay-to-frontmatter
        promotions LOSSLESS -- without it a promoted edge would drop its curated
        ``reason`` and the regenerated fragment would drift.
        """
        doctrine_root = tmp_path / "pack"
        directives_dir = doctrine_root / "directives"
        directives_dir.mkdir(parents=True)
        (directives_dir / "reason-roundtrip.directive.yaml").write_text(
            "\n".join(
                [
                    "schema_version: '1.0'",
                    "id: reason-roundtrip",
                    "title: Reason Roundtrip",
                    "references:",
                    "  - type: styleguide",
                    "    id: with-reason",
                    "    when: applying the styleguide",
                    "    reason: because the directive suggests it here",
                    "  - type: toolguide",
                    "    id: without-reason",
                    "    when: running the tool",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        _, edges = extract_artifact_edges(doctrine_root)

        with_reason = next(
            e for e in edges if e.target == "styleguide:with-reason"
        )
        assert with_reason.relation == Relation.SUGGESTS
        assert with_reason.when == "applying the styleguide"
        assert with_reason.reason == "because the directive suggests it here"

        without_reason = next(
            e for e in edges if e.target == "toolguide:without-reason"
        )
        assert without_reason.when == "running the tool"
        assert without_reason.reason is None

    def test_tactic_reference_reason_roundtrips(self, tmp_path: Path) -> None:
        """A tactic ``references`` entry (top-level AND step-level) carries
        ``reason`` symmetrically with ``when``, via the single
        :func:`_reference_edge_kwargs` authority.

        Regression for the pre-merge finding that the tactic branches read only
        ``when`` while the directive/paradigm branches read both -- so a future
        overlay-to-frontmatter promotion on a *tactic* source would have silently
        dropped its rationale at the extractor. Closes the defect class by
        construction (one helper feeds every reference branch).
        """
        doctrine_root = tmp_path / "pack"
        tactics_dir = doctrine_root / "tactics"
        tactics_dir.mkdir(parents=True)
        (tactics_dir / "reason-roundtrip.tactic.yaml").write_text(
            "\n".join(
                [
                    "schema_version: '1.0'",
                    "id: tactic-reason-roundtrip",
                    "name: Tactic Reason Roundtrip",
                    "references:",
                    "  - type: styleguide",
                    "    id: top-with-reason",
                    "    when: at the top level",
                    "    reason: because the tactic suggests it",
                    "steps:",
                    "  - references:",
                    "      - type: toolguide",
                    "        id: step-with-reason",
                    "        when: at the step level",
                    "        reason: because the step suggests it",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        _, edges = extract_artifact_edges(doctrine_root)

        top = next(e for e in edges if e.target == "styleguide:top-with-reason")
        assert top.when == "at the top level"
        assert top.reason == "because the tactic suggests it"

        step = next(e for e in edges if e.target == "toolguide:step-with-reason")
        assert step.when == "at the step level"
        assert step.reason == "because the step suggests it"

    def test_procedure_reference_reason_roundtrips(self, tmp_path: Path) -> None:
        """A procedure ``references`` entry carries ``reason`` symmetrically with
        ``when`` (#3605, WP01/T001), matching the directive/tactic/paradigm
        branches. Backward-compatible: an entry with no ``reason`` yields
        ``reason=None``.

        Before WP01 the procedures loop minted its ``DRGEdge`` inline, bypassing
        the single authority :func:`_reference_edge_kwargs` -- so a procedure
        reference's authored ``when``/``reason`` never reached the DRG edge even
        though shipped procedure fixtures already author ``reason`` in YAML.
        """
        doctrine_root = tmp_path / "pack"
        procedures_dir = doctrine_root / "procedures"
        procedures_dir.mkdir(parents=True)
        (procedures_dir / "reason-roundtrip.procedure.yaml").write_text(
            "\n".join(
                [
                    "schema_version: '1.0'",
                    "id: reason-roundtrip",
                    "name: Reason Roundtrip",
                    "purpose: test",
                    "references:",
                    "  - type: styleguide",
                    "    id: with-reason",
                    "    when: applying the styleguide",
                    "    reason: because the procedure suggests it here",
                    "  - type: toolguide",
                    "    id: without-reason",
                    "    when: running the tool",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        _, edges = extract_artifact_edges(doctrine_root)

        with_reason = next(
            e for e in edges if e.target == "styleguide:with-reason"
        )
        assert with_reason.relation == Relation.SUGGESTS
        assert with_reason.when == "applying the styleguide"
        assert with_reason.reason == "because the procedure suggests it here"

        without_reason = next(
            e for e in edges if e.target == "toolguide:without-reason"
        )
        assert without_reason.when == "running the tool"
        assert without_reason.reason is None

    def test_procedure_reference_metadata_addition_preserves_triples(
        self, tmp_path: Path
    ) -> None:
        """T003/NFR-002/AC-009 triple-identity guard: adding ``when``/``reason``
        metadata to procedure references must never change the edge
        **(source, target, relation)** triple set -- only the two metadata
        fields differ.

        Builds two fixtures with IDENTICAL references (same type/id pairs,
        same order, one REQUIRES-class ref and one SUGGESTS-class ref) -- one
        authoring ``when``/``reason``, one bare -- and asserts the extracted
        triple sets are byte-identical between them. This is the guard the
        re-ledger (WP04) relies on: WP01 only ever adds metadata to an edge
        that already exists, it never mints, drops, or retargets one.
        """
        def _make_fixture(root: Path, *, with_metadata: bool) -> Path:
            procedures_dir = root / "procedures"
            procedures_dir.mkdir(parents=True)
            metadata_lines = (
                [
                    "    when: doing the thing",
                    "    reason: because triples must not move",
                ]
                if with_metadata
                else []
            )
            lines = [
                "schema_version: '1.0'",
                "id: triple-identity",
                "name: Triple Identity",
                "purpose: test",
                "references:",
                "  - type: procedure",
                "    id: required-sibling",
                *metadata_lines,
                "  - type: styleguide",
                "    id: suggested-guide",
                "",
            ]
            (procedures_dir / "triple-identity.procedure.yaml").write_text(
                "\n".join(lines), encoding="utf-8"
            )
            return root

        def _procedure_triples(
            edges: list[DRGEdge],
        ) -> set[tuple[str, str, str]]:
            return {
                (e.source, e.target, e.relation.value)
                for e in edges
                if e.source == "procedure:triple-identity"
            }

        _, bare_edges = extract_artifact_edges(
            _make_fixture(tmp_path / "bare", with_metadata=False)
        )
        _, annotated_edges = extract_artifact_edges(
            _make_fixture(tmp_path / "annotated", with_metadata=True)
        )

        bare_triples = _procedure_triples(bare_edges)
        annotated_triples = _procedure_triples(annotated_edges)

        assert bare_triples == annotated_triples, (
            "adding when/reason metadata changed the procedure edge triple set"
        )
        assert bare_triples == {
            ("procedure:triple-identity", "procedure:required-sibling", "requires"),
            ("procedure:triple-identity", "styleguide:suggested-guide", "suggests"),
        }

        # The metadata itself DID change -- proving this isn't a vacuously
        # true "nothing changed at all" assertion.
        bare_by_target = {e.target: e for e in bare_edges}
        annotated_by_target = {e.target: e for e in annotated_edges}
        annotated_required = annotated_by_target["procedure:required-sibling"]
        bare_required = bare_by_target["procedure:required-sibling"]
        assert bare_required.reason is None
        assert annotated_required.reason == "because triples must not move"
        assert bare_required.relation == annotated_required.relation

    def test_procedure_edge_relation_matches_ref_type_over_built_in_corpus(
        self,
    ) -> None:
        """Corpus-level companion to the fixture-based triple-identity guard:
        every edge the ``references:`` loop produces for a real shipped
        procedure has the relation :func:`_relation_for_procedure_ref_type`
        computes from its raw YAML ``type`` field -- confirming WP01's
        re-route through :func:`_add_ref_edge`/:func:`_reference_edge_kwargs`
        kept the relation computation unchanged; it only added
        ``when``/``reason``.

        Deliberately walks the raw YAML ``references:`` entries (not the
        assembled edge list) so hand-curated edges in
        ``_CURATED_ARTIFACT_EDGES`` -- which carry their own explicit,
        independently-reasoned relation and never flow through
        ``_relation_for_procedure_ref_type`` -- cannot produce a false
        mismatch here.
        """
        procedures_dir = built_in_graph_source() / "procedures"
        procedure_files = sorted(procedures_dir.glob("*.procedure.yaml"))
        assert procedure_files, "expected at least one shipped procedure"

        _, edges = extract_artifact_edges(built_in_graph_source())
        edges_by_triple = {(e.source, e.target, e.relation) for e in edges}

        checked = 0
        for path in procedure_files:
            data = _yaml.load(path)
            if not isinstance(data, dict):
                continue
            procedure_id = data.get("id", "")
            src_urn = f"procedure:{procedure_id}"
            for ref in data.get("references", []) or []:
                ref_type = ref.get("type", "")
                ref_id = ref.get("id", "")
                if not ref_type or not ref_id:
                    continue
                expected_relation = _relation_for_procedure_ref_type(ref_type)
                tgt_urn = f"{ref_type}:{ref_id}"
                assert (src_urn, tgt_urn, expected_relation) in edges_by_triple, (
                    f"{src_urn} -> {tgt_urn}: expected extracted edge with "
                    f"relation {expected_relation}, not found in graph"
                )
                checked += 1
        assert checked > 0, "expected at least one procedure reference to check"

    def _write_profile(self, root: Path, op_entries: list[str]) -> None:
        profiles_dir = root / "agent_profiles"
        profiles_dir.mkdir(parents=True, exist_ok=True)
        lines = ["profile-id: p", "name: P", "collaboration:", "  operating-procedures:"]
        lines += [f"    - {e}" for e in op_entries]
        (profiles_dir / "p.agent.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_operating_procedure_edge_emitted_for_resolvable_target(
        self, tmp_path: Path
    ) -> None:
        """A resolvable operating-procedures entry emits one requires edge (M3)."""
        root = tmp_path / "pack"
        procedures_dir = root / "procedures"
        procedures_dir.mkdir(parents=True)
        (procedures_dir / "foo.procedure.yaml").write_text(
            "id: foo\nname: Foo\n", encoding="utf-8"
        )
        self._write_profile(root, ["foo"])

        _, edges = extract_artifact_edges(root)

        matches = [
            e
            for e in edges
            if e.source == "agent_profile:p"
            and e.target == "procedure:foo"
            and e.relation is Relation.REQUIRES
        ]
        assert len(matches) == 1

    def test_unresolvable_operating_procedure_fails_closed(
        self, tmp_path: Path
    ) -> None:
        """A fictional operating-procedures entry raises at extraction (M3)."""
        root = tmp_path / "pack"
        (root / "procedures").mkdir(parents=True)
        self._write_profile(root, ["ghost-procedure"])

        with pytest.raises(ValueError, match="operating-procedures"):
            extract_artifact_edges(root)

    def test_wrong_kind_operating_procedure_fails_closed(
        self, tmp_path: Path
    ) -> None:
        """An operating-procedures entry naming a tactic (wrong kind) raises (M3)."""
        root = tmp_path / "pack"
        tactics_dir = root / "tactics"
        tactics_dir.mkdir(parents=True)
        (tactics_dir / "t.tactic.yaml").write_text(
            "schema_version: '1.0'\nid: t\nname: T\npurpose: test\n", encoding="utf-8"
        )
        (root / "procedures").mkdir(parents=True)
        self._write_profile(root, ["t"])

        with pytest.raises(ValueError, match="operating-procedures"):
            extract_artifact_edges(root)

    def test_procedure_template_references_produce_template_edges(self) -> None:
        """Procedure template references should be represented in the DRG."""
        _, edges = extract_artifact_edges(DOCTRINE_ROOT)
        issue_triage_suggests = [
            e
            for e in edges
            if e.source == "procedure:issue-triage-state-machine"
            and e.relation == Relation.SUGGESTS
        ]

        targets = {e.target for e in issue_triage_suggests}
        assert "template:agent-brief-template" in targets
        assert "template:out-of-scope-record-template" in targets

    def test_agent_profile_references_produce_requires(self) -> None:
        """Agent profile context and tactic references should enter the DRG."""
        nodes, edges = extract_artifact_edges(DOCTRINE_ROOT)
        assert any(
            n.urn == "agent_profile:debugger-debbie"
            and n.kind == NodeKind.AGENT_PROFILE
            for n in nodes
        )
        targets = {
            e.target
            for e in edges
            if e.source == "agent_profile:debugger-debbie"
            and e.relation == Relation.REQUIRES
        }
        assert "tactic:five-paradigm-parallel-debugging" in targets

    def test_walks_all_built_in_directives(self) -> None:
        nodes, _ = extract_artifact_edges(DOCTRINE_ROOT)
        directive_count = len(
            list(
                (built_in_graph_source() / "directives").glob("*.directive.yaml")
            )
        )
        graph_directive_nodes = [
            n for n in nodes
            if n.kind == NodeKind.DIRECTIVE and n.label is not None
        ]
        # Each shipped directive should appear as a labelled node
        assert len(graph_directive_nodes) >= directive_count

    def test_walks_all_shipped_paradigms(self) -> None:
        nodes, _ = extract_artifact_edges(DOCTRINE_ROOT)
        paradigm_files = list(
            (built_in_graph_source() / "paradigms").glob("*.paradigm.yaml")
        )
        graph_paradigm_nodes = [
            n for n in nodes
            if n.kind == NodeKind.PARADIGM and n.label is not None
        ]
        assert len(graph_paradigm_nodes) == len(paradigm_files)


# ---------------------------------------------------------------------------
# T013: Action index walker tests
# ---------------------------------------------------------------------------


@pytest.mark.doctrine
class TestExtractActionEdges:
    def test_returns_nodes_and_edges(self) -> None:
        nodes, edges = extract_action_edges(DOCTRINE_ROOT)
        assert len(nodes) > 0
        assert len(edges) > 0

    def test_action_nodes_created(self) -> None:
        nodes, _ = extract_action_edges(DOCTRINE_ROOT)
        action_urns = {n.urn for n in nodes if n.kind == NodeKind.ACTION}
        expected = {
            "action:software-dev/specify",
            "action:software-dev/plan",
            "action:software-dev/tasks",
            "action:software-dev/implement",
            "action:software-dev/review",
        }
        assert expected.issubset(action_urns)

    def test_directive_slugs_normalised(self) -> None:
        """Directive slugs in action indices should be normalised to DIRECTIVE_NNN."""
        _, edges = extract_action_edges(DOCTRINE_ROOT)
        implement_edges = [
            e for e in edges
            if e.source == "action:software-dev/implement"
            and e.target.startswith("directive:")
        ]
        for edge in implement_edges:
            assert edge.target.startswith("directive:DIRECTIVE_")

    def test_scope_edges_only(self) -> None:
        """All action edges should be scope edges."""
        _, edges = extract_action_edges(DOCTRINE_ROOT)
        for edge in edges:
            assert edge.relation == Relation.SCOPE

    def test_empty_lists_produce_no_edges(self) -> None:
        """Empty styleguides/toolguides/procedures lists should produce no edges."""
        _, edges = extract_action_edges(DOCTRINE_ROOT)
        specify_edges = [
            e for e in edges
            if e.source == "action:software-dev/specify"
        ]
        # specify has 2 directives + 1 tactic = 3 scope edges
        assert {e.target for e in specify_edges} == {
            "directive:DIRECTIVE_010",
            "directive:DIRECTIVE_003",
            "tactic:requirements-validation-workflow",
        }

    def test_agent_profile_scope_edges(self) -> None:
        """Action indexes may scope built-in agent profiles."""
        nodes, edges = extract_action_edges(DOCTRINE_ROOT)
        assert any(
            n.urn == "agent_profile:retrospective-facilitator"
            and n.kind == NodeKind.AGENT_PROFILE
            for n in nodes
        )
        assert any(
            e.source == "action:software-dev/retrospect"
            and e.target == "agent_profile:retrospective-facilitator"
            and e.relation == Relation.SCOPE
            for e in edges
        )

    def test_paradigm_scope_edges(self) -> None:
        """Action indexes may scope built-in paradigms."""
        nodes, edges = extract_action_edges(DOCTRINE_ROOT)
        assert any(
            n.urn == "paradigm:execution-lanes"
            and n.kind == NodeKind.PARADIGM
            for n in nodes
        )
        assert any(
            e.source == "action:software-dev/implement"
            and e.target == "paradigm:execution-lanes"
            and e.relation == Relation.SCOPE
            for e in edges
        )

    def test_tasks_action_has_seven_refs(self) -> None:
        """The tasks action index should produce 7 scope edges."""
        _, edges = extract_action_edges(DOCTRINE_ROOT)
        tasks_edges = [
            e for e in edges
            if e.source == "action:software-dev/tasks"
        ]
        assert {e.target for e in tasks_edges} == {
            "directive:DIRECTIVE_003",
            "directive:DIRECTIVE_010",
            "directive:DIRECTIVE_024",
            "tactic:adr-drafting-workflow",
            "tactic:problem-decomposition",
            "tactic:requirements-validation-workflow",
            "procedure:issue-triage-state-machine",
        }

    def test_nonexistent_doctrine_root(self) -> None:
        nodes, edges = extract_action_edges(Path("/nonexistent"))
        assert nodes == []
        assert edges == []


# ---------------------------------------------------------------------------
# T016: generate_graph end-to-end
# ---------------------------------------------------------------------------


@pytest.mark.doctrine
class TestGenerateGraph:
    def test_generates_valid_graph(self, tmp_path: Path) -> None:
        output = tmp_path / "graph.yaml"
        graph = generate_graph(DOCTRINE_ROOT, output)
        errors = validate_graph(graph)
        assert errors == [], f"Validation errors: {errors}"

    def test_graph_file_exists(self, tmp_path: Path) -> None:
        output = tmp_path / "graph.yaml"
        generate_graph(DOCTRINE_ROOT, output)
        # Sharded layout (mission #2680 WP05): the generator writes per-kind
        # ``*.graph.yaml`` fragments into ``output``'s directory and retires any
        # ``graph.yaml`` monolith in the same write (DD-7).
        assert sorted(tmp_path.glob("*.graph.yaml"))
        assert not output.exists()

    def test_schema_version(self, tmp_path: Path) -> None:
        output = tmp_path / "graph.yaml"
        graph = generate_graph(DOCTRINE_ROOT, output)
        assert graph.schema_version == "1.0"

    def test_generated_by(self, tmp_path: Path) -> None:
        output = tmp_path / "graph.yaml"
        graph = generate_graph(DOCTRINE_ROOT, output)
        assert graph.generated_by == "drg-migration-v1"

    def test_all_node_urns_unique(self, tmp_path: Path) -> None:
        output = tmp_path / "graph.yaml"
        graph = generate_graph(DOCTRINE_ROOT, output)
        urns = [n.urn for n in graph.nodes]
        assert len(urns) == len(set(urns))

    def test_all_edge_triples_unique(self, tmp_path: Path) -> None:
        output = tmp_path / "graph.yaml"
        graph = generate_graph(DOCTRINE_ROOT, output)
        triples = [(e.source, e.target, e.relation.value) for e in graph.edges]
        assert len(triples) == len(set(triples))

    def test_idempotent(self, tmp_path: Path) -> None:
        """Running generate_graph twice must produce identical fragments (DD-11)."""
        dir1 = tmp_path / "run1"
        dir2 = tmp_path / "run2"
        dir1.mkdir()
        dir2.mkdir()
        generate_graph(DOCTRINE_ROOT, dir1 / "graph.yaml")
        generate_graph(DOCTRINE_ROOT, dir2 / "graph.yaml")

        def _fragment_hashes(directory: Path) -> dict[str, str]:
            return {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()  # noqa: TID251 — DRG-output file-integrity idempotency check, not charter freshness hashing
                for p in sorted(directory.glob("*.graph.yaml"))
            }

        first = _fragment_hashes(dir1)
        second = _fragment_hashes(dir2)
        assert first, "generate_graph produced no fragments"
        assert first == second, "generate_graph is not idempotent (per-fragment drift)"

    @pytest.mark.fast
    def test_shipped_graph_yaml_is_fresh(self, tmp_path: Path) -> None:
        """Committed shipped DRG fragments must match generator output byte-for-byte.

        Sharded per mission #2680 (WP05): compare the per-kind ``*.graph.yaml``
        fragment set rather than a single monolith (DD-11 per-file byte-identity).

        Post-WP03 (doctrine-tension-edges-01KY1WPC): the reference is "pure
        extraction + the enumerable hand-authored overlay"
        (``charter.offering.drg.migration.hand_authored_overlay``), not a bare
        extractor regeneration — the extractor has no frontmatter mechanism
        that could ever mint the hand-authored tension/reconciliation/rejection
        edges or anti-pattern nodes, so a bare regeneration would never match
        even when nothing is actually stale.
        """
        write_reference_graph_with_overlay(DOCTRINE_ROOT, tmp_path / "graph.yaml")

        def _fragments(directory: Path) -> dict[str, str]:
            return {
                p.name: p.read_text(encoding="utf-8")
                for p in sorted(directory.glob("*.graph.yaml"))
            }

        regenerated = _fragments(tmp_path)
        committed = _fragments(built_in_graph_source())
        assert regenerated, "generate_graph produced no fragments"
        assert regenerated == committed, (
            "packs/built-in/*.graph.yaml fragments are stale. Regenerate the "
            "shipped DRG with `spec-kitty doctrine regenerate-graph` and commit "
            "the result."
        )

    def test_surface_inequalities(self, tmp_path: Path) -> None:
        """Verify governance surface inequalities after calibration."""
        output = tmp_path / "graph.yaml"
        graph = generate_graph(DOCTRINE_ROOT, output)

        specify = measure_surface("action:software-dev/specify", graph.edges)
        plan = measure_surface("action:software-dev/plan", graph.edges)
        tasks = measure_surface("action:software-dev/tasks", graph.edges)
        implement = measure_surface("action:software-dev/implement", graph.edges)
        review = measure_surface("action:software-dev/review", graph.edges)

        assert specify < plan, f"|specify| ({specify}) should be < |plan| ({plan})"
        assert plan < implement, f"|plan| ({plan}) should be < |implement| ({implement})"
        assert tasks < implement, f"|tasks| ({tasks}) should be < |implement| ({implement})"
        assert review >= 0.80 * implement, (
            f"|review| ({review}) should be >= 80% of |implement| ({implement})"
        )

    def test_resolved_surface_inequalities(self, tmp_path: Path) -> None:
        """Generated graph must satisfy shipped resolved-context calibration."""
        output = tmp_path / "graph.yaml"
        graph = generate_graph(DOCTRINE_ROOT, output)

        def _resolved(action: str) -> int:
            return len(
                resolve_context(
                    graph,
                    f"action:software-dev/{action}",
                    depth=2,
                ).artifact_urns
            )

        specify = _resolved("specify")
        plan = _resolved("plan")
        tasks = _resolved("tasks")
        implement = _resolved("implement")
        review = _resolved("review")

        assert specify < plan, f"resolved specify ({specify}) should be < plan ({plan})"
        assert plan < implement, (
            f"resolved plan ({plan}) should be < implement ({implement})"
        )
        assert tasks < implement, (
            f"resolved tasks ({tasks}) should be < implement ({implement})"
        )
        assert review >= 0.80 * implement, (
            f"resolved review ({review}) should be >= 80% of implement ({implement})"
        )

    def test_discovers_styleguide_nodes(self, tmp_path: Path) -> None:
        output = tmp_path / "graph.yaml"
        graph = generate_graph(DOCTRINE_ROOT, output)
        styleguide_nodes = [n for n in graph.nodes if n.kind == NodeKind.STYLEGUIDE]
        # At least the shipped styleguides should be present
        assert len(styleguide_nodes) >= 1

    def test_discovers_toolguide_nodes(self, tmp_path: Path) -> None:
        output = tmp_path / "graph.yaml"
        graph = generate_graph(DOCTRINE_ROOT, output)
        toolguide_nodes = [n for n in graph.nodes if n.kind == NodeKind.TOOLGUIDE]
        assert len(toolguide_nodes) >= 1

    def test_discovers_procedure_nodes(self, tmp_path: Path) -> None:
        output = tmp_path / "graph.yaml"
        graph = generate_graph(DOCTRINE_ROOT, output)
        procedure_nodes = [n for n in graph.nodes if n.kind == NodeKind.PROCEDURE]
        assert len(procedure_nodes) >= 1


# ---------------------------------------------------------------------------
# T017: Edge-count completeness validation
# ---------------------------------------------------------------------------


@pytest.mark.doctrine
class TestEdgeCountCompleteness:
    def test_edge_count_gte_inline_refs(self, tmp_path: Path) -> None:
        """Total edge count must be >= total inline reference field count.

        The >= accounts for calibration-added edges.
        """
        output = tmp_path / "graph.yaml"
        graph = generate_graph(DOCTRINE_ROOT, output)
        total_inline = _count_inline_refs(DOCTRINE_ROOT)
        assert len(graph.edges) >= total_inline, (
            f"Edge count ({len(graph.edges)}) < inline refs ({total_inline}). "
            f"Some references were dropped."
        )

    def test_per_directive_edges_complete(self) -> None:
        """Each directive's inline refs should have corresponding edges."""
        _, edges = extract_artifact_edges(DOCTRINE_ROOT)
        directives_dir = built_in_graph_source() / "directives"
        for path in sorted(directives_dir.glob("*.directive.yaml")):
            data: Any = _yaml.load(path)
            if not data:
                continue
            src_id = data.get("id", "")
            src_urn = f"directive:{src_id}"
            src_edges = [e for e in edges if e.source == src_urn]

            expected_count = len(data.get("tactic_refs", []) or [])
            for ref in data.get("references", []) or []:
                if ref.get("type", "") not in _SKIP_REF_TYPES:
                    expected_count += 1

            assert len(src_edges) >= expected_count, (
                f"{path.name}: expected >= {expected_count} edges from "
                f"{src_urn}, found {len(src_edges)}"
            )

    def test_per_paradigm_edges_complete(self) -> None:
        """Each paradigm's inline refs should have corresponding edges."""
        _, edges = extract_artifact_edges(DOCTRINE_ROOT)
        paradigms_dir = built_in_graph_source() / "paradigms"
        for path in sorted(paradigms_dir.glob("*.paradigm.yaml")):
            data: Any = _yaml.load(path)
            if not data:
                continue
            src_id = data.get("id", "")
            src_urn = f"paradigm:{src_id}"
            src_edges = [e for e in edges if e.source == src_urn]

            expected_count = (
                len(data.get("tactic_refs", []) or [])
                + len(data.get("directive_refs", []) or [])
            )

            assert len(src_edges) >= expected_count, (
                f"{path.name}: expected >= {expected_count} edges from "
                f"{src_urn}, found {len(src_edges)}"
            )

    def test_per_action_edges_complete(self) -> None:
        """Each action's scope refs should have corresponding edges."""
        _, edges = extract_action_edges(DOCTRINE_ROOT)
        missions_dir = DOCTRINE_ROOT / "missions"
        for index_path in sorted(missions_dir.rglob("actions/*/index.yaml")):
            data: Any = _yaml.load(index_path)
            if not data:
                continue
            action_name = data.get("action", index_path.parent.name)
            mission_name = index_path.parent.parent.parent.name
            action_urn = f"action:{mission_name}/{action_name}"
            action_edges = [e for e in edges if e.source == action_urn]

            expected_count = 0
            for field in (
                "directives",
                "tactics",
                "paradigms",
                "styleguides",
                "toolguides",
                "procedures",
                "agent_profiles",
            ):
                expected_count += len(data.get(field, []) or [])

            assert len(action_edges) == expected_count, (
                f"{action_name}: expected {expected_count} edges, "
                f"found {len(action_edges)}"
            )


# ---------------------------------------------------------------------------
# Mission-type edge emission (mission-type-drg-edges mission, SC-001)
# ---------------------------------------------------------------------------

MISSION_TYPES_DIR = DOCTRINE_ROOT / "missions" / "mission_types"


def _shipped_action_sequences() -> dict[str, list[str]]:
    """Resolved ``action_sequence`` per shipped mission type via the WP02 seam.

    Re-pointed (WP04, T013) from a raw ``data.get("action_sequence")`` YAML
    read to :class:`MissionTypeRepository`'s resolved value -- the same
    projection-or-fallback seam :func:`extract_mission_type_edges` now reads.
    A raw-YAML read would go red at the WP07 cutover once ``action_sequence``
    is no longer authored in the shipped YAML; reading through the repository
    turns this into a referential-integrity check that survives the cutover
    unchanged.
    """
    repo = MissionTypeRepository(MISSION_TYPES_DIR)
    return {
        mission_type.id: list(mission_type.action_sequence or [])
        for mission_type in repo.load_all()
    }


@pytest.mark.doctrine
class TestMissionTypeEdges:
    """Green-pinning for the ``mission_type --requires--> action`` edges.

    WP01 landed the emission (and demonstrated red-first inside its own loop);
    these tests pin the full behaviour comprehensively against the shipped
    generator entry points.
    """

    def test_plan_emits_exactly_its_four_requires_edges(self) -> None:
        """``mission_type:plan`` emits exactly 4 requires edges to its actions."""
        edges = extract_mission_type_edges(DOCTRINE_ROOT)
        plan_edges = [
            e for e in edges if e.source == "mission_type:plan"
        ]

        assert all(e.relation is Relation.REQUIRES for e in plan_edges)
        assert {e.target for e in plan_edges} == {
            "action:plan/specify",
            "action:plan/research",
            "action:plan/plan",
            "action:plan/review",
        }
        assert len(plan_edges) == 4

    def test_documentation_emits_full_seven_edge_sequence(self) -> None:
        """A non-plan type emits its full 7-step sequence (FR-001 breadth)."""
        edges = extract_mission_type_edges(DOCTRINE_ROOT)
        doc_edges = [
            e for e in edges if e.source == "mission_type:documentation"
        ]

        assert all(e.relation is Relation.REQUIRES for e in doc_edges)
        assert {e.target for e in doc_edges} == {
            "action:documentation/discover",
            "action:documentation/audit",
            "action:documentation/design",
            "action:documentation/generate",
            "action:documentation/validate",
            "action:documentation/publish",
            "action:documentation/accept",
        }
        assert len(doc_edges) == 7

    def test_every_mission_type_edge_matches_its_action_sequence(self) -> None:
        """Each shipped type emits one requires edge per action_sequence step."""
        edges = extract_mission_type_edges(DOCTRINE_ROOT)
        sequences = _shipped_action_sequences()

        for mission_id, steps in sequences.items():
            source_urn = f"mission_type:{mission_id}"
            emitted = {
                e.target
                for e in edges
                if e.source == source_urn and e.relation is Relation.REQUIRES
            }
            assert emitted == {
                f"action:{mission_id}/{step}" for step in steps
            }, f"{source_urn} edges do not match its action_sequence"

    def test_total_mission_type_edge_count_is_twenty_one(self) -> None:
        """SC-001: the four shipped types emit 21 requires edges in total.

        4 (plan) + 7 (documentation) + 5 (research) + 5 (software-dev) = 21.
        This is a deliberate cardinality contract over the built-in mission
        types, not incidental golden-count debt.
        """
        edges = extract_mission_type_edges(DOCTRINE_ROOT)
        requires_edges = [
            e
            for e in edges
            if e.source.startswith("mission_type:")
            and e.relation is Relation.REQUIRES
        ]
        assert len(requires_edges) == 21

    def test_no_mission_type_or_sequence_action_node_is_orphan(
        self, tmp_path: Path
    ) -> None:
        """No mission_type node -- and no action node named in a sequence --
        remains an orphan in the fully generated graph (SC-001)."""
        output = tmp_path / "graph.yaml"
        graph = generate_graph(DOCTRINE_ROOT, output)

        incident: set[str] = set()
        for edge in graph.edges:
            incident.add(edge.source)
            incident.add(edge.target)

        mission_type_urns = {
            n.urn for n in graph.nodes if n.kind == NodeKind.MISSION_TYPE
        }
        assert mission_type_urns, "expected shipped mission_type nodes"
        orphan_mission_types = mission_type_urns - incident
        assert not orphan_mission_types, (
            f"mission_type nodes are orphaned: {orphan_mission_types}"
        )

        sequence_action_urns = {
            f"action:{mission_id}/{step}"
            for mission_id, steps in _shipped_action_sequences().items()
            for step in steps
        }
        orphan_sequence_actions = sequence_action_urns - incident
        assert not orphan_sequence_actions, (
            f"sequence action nodes are orphaned: {orphan_sequence_actions}"
        )


def _hand_partition_graph() -> DRGGraph:
    """A small, deliberately-unsorted hand-made graph exercising every
    ``_partition_by_kind`` invariant (FR-007 source-kind routing + DD-11 order).

    Shape (input order is intentionally NOT canonical so the sort is exercised):

    * three populated kinds -- ``MISSION_TYPE``, ``ACTION`` and a **target-only**
      ``TEMPLATE`` (owns a node but is never an edge source);
    * multi-kind edges: ``MISSION_TYPE``-sourced ``requires`` edges to actions
      AND an ``ACTION``-sourced ``instantiates`` edge to the template -- so a
      wrong (e.g. target-kind) routing would still reconstitute the same merged
      graph yet land edges in the wrong fragment.
    """
    return DRGGraph(
        schema_version="1.0",
        generated_at="2026-07-16T00:00:00+00:00",
        generated_by="test",
        # Unsorted within each kind: software_dev before research; specify before plan.
        nodes=[
            DRGNode(urn="mission_type:software_dev", kind=NodeKind.MISSION_TYPE),
            DRGNode(urn="action:specify", kind=NodeKind.ACTION),
            DRGNode(urn="template:spec_tmpl", kind=NodeKind.TEMPLATE),
            DRGNode(urn="mission_type:research", kind=NodeKind.MISSION_TYPE),
            DRGNode(urn="action:plan", kind=NodeKind.ACTION),
        ],
        # Unsorted: software_dev->specify before software_dev->plan, research last.
        edges=[
            DRGEdge(
                source="mission_type:software_dev",
                target="action:specify",
                relation=Relation.REQUIRES,
            ),
            DRGEdge(
                source="mission_type:software_dev",
                target="action:plan",
                relation=Relation.REQUIRES,
            ),
            DRGEdge(
                source="mission_type:research",
                target="action:specify",
                relation=Relation.REQUIRES,
            ),
            DRGEdge(
                source="action:specify",
                target="template:spec_tmpl",
                relation=Relation.INSTANTIATES,
            ),
        ],
    )


class TestPartitionByKind:
    """Focused unit coverage for ``_partition_by_kind`` (DD-8/DD-11, FR-007).

    The end-to-end fragment tests reconstitute the merged graph, so a
    wrong-source-kind routing (e.g. by target kind) would still round-trip and
    pass every one of them. These assertions pin the currently-invisible
    per-fragment placement + ordering contract directly.
    """

    def test_one_fragment_per_populated_kind_including_target_only(self) -> None:
        """Totality (DD-8): every populated kind -- including a target-only
        kind that is never an edge source -- yields exactly one fragment, and
        the target-only kind's fragment carries an empty edge list."""
        fragments = _partition_by_kind(_hand_partition_graph())

        assert set(fragments) == {
            NodeKind.MISSION_TYPE,
            NodeKind.ACTION,
            NodeKind.TEMPLATE,
        }
        # TEMPLATE owns a node but sources no edge -> present, with no edges.
        assert [n.urn for n in fragments[NodeKind.TEMPLATE].nodes] == [
            "template:spec_tmpl"
        ]
        assert fragments[NodeKind.TEMPLATE].edges == []

    def test_each_fragment_is_kind_homogeneous(self) -> None:
        """Homogeneity: every node in a fragment is of that fragment's kind."""
        fragments = _partition_by_kind(_hand_partition_graph())
        for kind, fragment in fragments.items():
            assert all(node.kind == kind for node in fragment.nodes)

    def test_edge_lands_in_its_source_node_kind_fragment(self) -> None:
        """FR-007 (the invisible clause): each edge is placed in the fragment of
        its **source** node's kind -- not its target's."""
        fragments = _partition_by_kind(_hand_partition_graph())
        kind_by_urn = {
            n.urn: n.kind
            for frag in fragments.values()
            for n in frag.nodes
        }
        for kind, fragment in fragments.items():
            for edge in fragment.edges:
                assert kind_by_urn[edge.source] == kind

        # Concrete guard against target-kind routing: the ACTION-sourced edge to
        # the template lands in ACTION (not TEMPLATE), and the mission_type
        # edges land in MISSION_TYPE (not ACTION).
        action_edges = fragments[NodeKind.ACTION].edges
        assert [(e.source, e.target) for e in action_edges] == [
            ("action:specify", "template:spec_tmpl")
        ]
        mt_sources = {e.source for e in fragments[NodeKind.MISSION_TYPE].edges}
        assert mt_sources == {
            "mission_type:research",
            "mission_type:software_dev",
        }

    def test_intra_fragment_canonical_order(self) -> None:
        """DD-11: fragment nodes are sorted by URN and edges by
        ``(source, target, relation)`` regardless of input order."""
        fragments = _partition_by_kind(_hand_partition_graph())

        assert [n.urn for n in fragments[NodeKind.MISSION_TYPE].nodes] == [
            "mission_type:research",
            "mission_type:software_dev",
        ]
        assert [n.urn for n in fragments[NodeKind.ACTION].nodes] == [
            "action:plan",
            "action:specify",
        ]
        assert [
            (e.source, e.target, e.relation.value)
            for e in fragments[NodeKind.MISSION_TYPE].edges
        ] == [
            ("mission_type:research", "action:specify", "requires"),
            ("mission_type:software_dev", "action:plan", "requires"),
            ("mission_type:software_dev", "action:specify", "requires"),
        ]

    def test_disjoint_union_reconstructs_input_exactly(self) -> None:
        """Fragments partition the input: their disjoint union reproduces the
        original node and edge sets with nothing lost or duplicated."""
        graph = _hand_partition_graph()
        fragments = _partition_by_kind(graph)

        recomposed_nodes = [n.urn for frag in fragments.values() for n in frag.nodes]
        recomposed_edges = [
            (e.source, e.target, e.relation.value)
            for frag in fragments.values()
            for e in frag.edges
        ]
        # No duplication (disjointness) + exact set equality (completeness).
        assert len(recomposed_nodes) == len(graph.nodes)
        assert set(recomposed_nodes) == {n.urn for n in graph.nodes}
        assert len(recomposed_edges) == len(graph.edges)
        assert set(recomposed_edges) == {
            (e.source, e.target, e.relation.value) for e in graph.edges
        }


class TestDiscoverBuiltInNodesInDir:
    """Direct unit tests for the extracted per-subdir scan helper (WP03 T011),
    pulled out of ``_discover_built_in_artifact_nodes`` to keep its cognitive
    complexity within the ruff C901 limit (15)."""

    def test_registers_a_node_per_artifact_with_label(self, tmp_path: Path) -> None:
        styleguide_dir = tmp_path / "styleguides"
        styleguide_dir.mkdir()
        (styleguide_dir / "one.styleguide.yaml").write_text(
            "id: my-style\nname: My Style\n", encoding="utf-8"
        )

        nodes_by_urn: dict[str, DRGNode] = {}
        _discover_built_in_nodes_in_dir(
            styleguide_dir, "styleguide", NodeKind.STYLEGUIDE, nodes_by_urn
        )

        assert set(nodes_by_urn) == {"styleguide:my-style"}
        node = nodes_by_urn["styleguide:my-style"]
        assert node.kind == NodeKind.STYLEGUIDE
        assert node.label == "My Style"

    def test_agent_profile_kind_uses_profile_id_key_and_agent_glob(
        self, tmp_path: Path
    ) -> None:
        """agent_profile is the one kind with a different glob/id-key pair."""
        profiles_dir = tmp_path / "agent_profiles"
        profiles_dir.mkdir()
        (profiles_dir / "pedro.agent.yaml").write_text(
            "profile-id: python-pedro\nname: Python Pedro\n", encoding="utf-8"
        )
        # A same-named .toolguide.yaml sibling must NOT match the agent glob.
        (profiles_dir / "pedro.toolguide.yaml").write_text(
            "id: not-an-agent\n", encoding="utf-8"
        )

        nodes_by_urn: dict[str, DRGNode] = {}
        _discover_built_in_nodes_in_dir(
            profiles_dir, "agent_profile", NodeKind.AGENT_PROFILE, nodes_by_urn
        )

        assert set(nodes_by_urn) == {"agent_profile:python-pedro"}

    def test_file_with_no_artifact_id_is_skipped(self, tmp_path: Path) -> None:
        toolguides_dir = tmp_path / "toolguides"
        toolguides_dir.mkdir()
        (toolguides_dir / "noid.toolguide.yaml").write_text(
            "name: No ID Here\n", encoding="utf-8"
        )

        nodes_by_urn: dict[str, DRGNode] = {}
        _discover_built_in_nodes_in_dir(
            toolguides_dir, "toolguide", NodeKind.TOOLGUIDE, nodes_by_urn
        )

        assert nodes_by_urn == {}

    def test_empty_yaml_document_is_skipped(self, tmp_path: Path) -> None:
        procedures_dir = tmp_path / "procedures"
        procedures_dir.mkdir()
        (procedures_dir / "empty.procedure.yaml").write_text("", encoding="utf-8")

        nodes_by_urn: dict[str, DRGNode] = {}
        _discover_built_in_nodes_in_dir(
            procedures_dir, "procedure", NodeKind.PROCEDURE, nodes_by_urn
        )

        assert nodes_by_urn == {}

    def test_nested_subdirectory_artifacts_are_discovered_via_rglob(
        self, tmp_path: Path
    ) -> None:
        assets_dir = tmp_path / "assets"
        nested = assets_dir / "nested" / "deeper"
        nested.mkdir(parents=True)
        (nested / "deep.asset.yaml").write_text(
            "id: deep-asset\ntitle: Deep Asset\n", encoding="utf-8"
        )

        nodes_by_urn: dict[str, DRGNode] = {}
        _discover_built_in_nodes_in_dir(
            assets_dir, "asset", NodeKind.ASSET, nodes_by_urn
        )

        assert set(nodes_by_urn) == {"asset:deep-asset"}


class TestAgentProfileImplementerIvanConstant:
    """S1192 hoist (WP03 T009): the ``agent_profile:implementer-ivan``
    lineage target was duplicated 4x in ``_CURATED_ARTIFACT_EDGES``; it is
    now one named module constant referenced at every site."""

    def test_constant_has_the_expected_urn(self) -> None:
        assert _AGENT_PROFILE_IMPLEMENTER_IVAN == "agent_profile:implementer-ivan"

    def test_implementer_lineage_edges_reference_the_constant(self) -> None:
        lineage_sources = [
            source
            for source, target, relation in _CURATED_ARTIFACT_EDGES
            if relation == Relation.SPECIALIZES_FROM
            and target == _AGENT_PROFILE_IMPLEMENTER_IVAN
        ]
        # Non-empty guards against a vacuous pass; uniqueness catches a
        # specialist registered twice. Deliberately no frozen count: adding an
        # implementer specialist must not require editing this test.
        assert lineage_sources
        assert len(lineage_sources) == len(set(lineage_sources))
        assert "agent_profile:drupal-dries" in lineage_sources


class TestExtractGovernanceProfileScopeEdges:
    """Focused unit tests for ``extract_governance_profile_scope_edges``
    (#3604), which was previously only exercised end-to-end against the real
    shipped doctrine tree. Mirrors ``TestDiscoverBuiltInNodesInDir``'s
    tmp_path fixture-pack style. Covers the branches the end-to-end path
    never isolates: the ``mission_type`` fallback to the profile's own
    parent-directory name, the ``seen_triples`` dedup guard, and the
    missing-``missions/``-dir early return.
    """

    def test_missing_missions_dir_returns_no_edges(self, tmp_path: Path) -> None:
        """A doctrine root with no ``missions/`` directory at all degrades to
        an empty edge list rather than raising -- mirrors every other
        extraction pass's missing-source-dir tolerance."""
        assert not (tmp_path / "missions").exists()

        edges = extract_governance_profile_scope_edges(tmp_path)

        assert edges == []

    def test_mission_type_falls_back_to_parent_dir_name(self, tmp_path: Path) -> None:
        """When ``governance-profile.yaml`` omits the ``mission_type`` key,
        the source mission-type id is the profile's own parent directory
        name (``profile_path.parent.name``) -- not left unresolved or
        defaulted to some other constant."""
        profile_dir = tmp_path / "missions" / "research"
        profile_dir.mkdir(parents=True)
        (profile_dir / "governance-profile.yaml").write_text(
            "selected_directives:\n  - DIRECTIVE_999\n",
            encoding="utf-8",
        )

        edges = extract_governance_profile_scope_edges(tmp_path)

        assert {(e.source, e.target, e.relation) for e in edges} == {
            (
                artifact_to_urn("mission_type", "research"),
                artifact_to_urn("directive", "DIRECTIVE_999"),
                Relation.SCOPE,
            )
        }

    def test_explicit_mission_type_overrides_parent_dir_name(
        self, tmp_path: Path
    ) -> None:
        """When authored, the ``mission_type`` key wins over the parent
        directory name -- proving the fallback above really is a fallback,
        not an always-preferred value."""
        profile_dir = tmp_path / "missions" / "on-disk-dir-name"
        profile_dir.mkdir(parents=True)
        (profile_dir / "governance-profile.yaml").write_text(
            "mission_type: authored-type\n"
            "selected_paradigms:\n"
            "  - fixture-paradigm\n",
            encoding="utf-8",
        )

        edges = extract_governance_profile_scope_edges(tmp_path)

        assert {(e.source, e.target, e.relation) for e in edges} == {
            (
                artifact_to_urn("mission_type", "authored-type"),
                artifact_to_urn("paradigm", "fixture-paradigm"),
                Relation.SCOPE,
            )
        }

    def test_duplicate_selected_id_is_deduplicated_via_seen_triples(
        self, tmp_path: Path
    ) -> None:
        """The same target id repeated within a ``selected_*`` list collapses
        to a single ``(source, target, relation)`` edge via the
        ``seen_triples`` guard, instead of emitting a duplicate edge per
        repeated entry."""
        profile_dir = tmp_path / "missions" / "plan"
        profile_dir.mkdir(parents=True)
        (profile_dir / "governance-profile.yaml").write_text(
            "mission_type: plan\n"
            "selected_tactics:\n"
            "  - fixture-tactic\n"
            "  - fixture-tactic\n"
            "  - fixture-tactic\n",
            encoding="utf-8",
        )

        edges = extract_governance_profile_scope_edges(tmp_path)

        # List-equality (not set): proves the three duplicate entries collapse to
        # exactly one emitted edge, not merely to one unique triple.
        assert [(e.source, e.target, e.relation) for e in edges] == [
            (
                artifact_to_urn("mission_type", "plan"),
                artifact_to_urn("tactic", "fixture-tactic"),
                Relation.SCOPE,
            )
        ]

    def test_multiple_profiles_and_fields_each_emit_their_own_edge(
        self, tmp_path: Path
    ) -> None:
        """Sanity check the dedup guard is scoped per-triple, not global: two
        distinct mission types, and two distinct fields on the same profile,
        each still produce their own edge."""
        research_dir = tmp_path / "missions" / "research"
        research_dir.mkdir(parents=True)
        (research_dir / "governance-profile.yaml").write_text(
            "mission_type: research\n"
            "selected_directives:\n"
            "  - DIRECTIVE_999\n"
            "selected_tactics:\n"
            "  - fixture-tactic\n",
            encoding="utf-8",
        )
        plan_dir = tmp_path / "missions" / "plan"
        plan_dir.mkdir(parents=True)
        (plan_dir / "governance-profile.yaml").write_text(
            "mission_type: plan\nselected_directives:\n  - DIRECTIVE_999\n",
            encoding="utf-8",
        )

        edges = extract_governance_profile_scope_edges(tmp_path)

        triples = {(e.source, e.target, e.relation) for e in edges}
        assert triples == {
            (
                artifact_to_urn("mission_type", "research"),
                artifact_to_urn("directive", "DIRECTIVE_999"),
                Relation.SCOPE,
            ),
            (
                artifact_to_urn("mission_type", "research"),
                artifact_to_urn("tactic", "fixture-tactic"),
                Relation.SCOPE,
            ),
            (
                artifact_to_urn("mission_type", "plan"),
                artifact_to_urn("directive", "DIRECTIVE_999"),
                Relation.SCOPE,
            ),
        }

    def test_selected_agent_profiles_and_step_contracts_project_scope_edges(
        self, tmp_path: Path
    ) -> None:
        """#3633 item 3: the two fields ``TestMultipleProfilesAndFields``
        (and the rest of this class) never exercises --
        ``selected_agent_profiles`` / ``selected_mission_step_contracts`` --
        each still project a ``scope`` edge to the right node kind. Uses
        real, resolvable ids (an actual shipped agent profile + step
        contract) rather than the class's usual fictional fixtures, so this
        case remains valid once #3629's fail-loud contract is wired to a
        real node universe (:func:`assert_governance_scope_edges_resolve`)
        -- unlike the fictional-id tests above, which only ever exercise
        the pure, existence-check-free extractor."""
        profile_dir = tmp_path / "missions" / "software-dev"
        profile_dir.mkdir(parents=True)
        (profile_dir / "governance-profile.yaml").write_text(
            "mission_type: software-dev\n"
            "selected_agent_profiles:\n"
            "  - implementer-ivan\n"
            "selected_mission_step_contracts:\n"
            "  - software-dev/implement\n",
            encoding="utf-8",
        )

        edges = extract_governance_profile_scope_edges(tmp_path)

        triples = {(e.source, e.target, e.relation) for e in edges}
        assert triples == {
            (
                artifact_to_urn("mission_type", "software-dev"),
                artifact_to_urn("agent_profile", "implementer-ivan"),
                Relation.SCOPE,
            ),
            (
                artifact_to_urn("mission_type", "software-dev"),
                artifact_to_urn("mission_step_contract", "software-dev/implement"),
                Relation.SCOPE,
            ),
        }


# ---------------------------------------------------------------------------
# #3629 item 2 — fail-loud on unresolved governance-profile scope selections
# ---------------------------------------------------------------------------


class TestAssertGovernanceScopeEdgesResolve:
    """Unit coverage for :func:`assert_governance_scope_edges_resolve`, the
    fail-closed check :func:`generate_graph` runs against
    ``extract_governance_profile_scope_edges``'s output before the
    calibration-target loop that used to phantom-mint a node for any
    fictional ``selected_*`` id (#3629)."""

    def test_raises_with_mission_type_field_and_id_for_unresolved_target(self) -> None:
        edge = DRGEdge(
            source=artifact_to_urn("mission_type", "research"),
            target=artifact_to_urn("agent_profile", "does-not-exist"),
            relation=Relation.SCOPE,
        )

        with pytest.raises(ValueError, match=r"research:selected_agent_profiles=does-not-exist"):
            assert_governance_scope_edges_resolve(edges=[edge], nodes_by_urn={})

    def test_passes_silently_when_every_target_is_minted(self) -> None:
        target_urn = artifact_to_urn("directive", "DIRECTIVE_001")
        edge = DRGEdge(
            source=artifact_to_urn("mission_type", "plan"),
            target=target_urn,
            relation=Relation.SCOPE,
        )
        nodes_by_urn = {
            target_urn: DRGNode(urn=target_urn, kind=NodeKind.DIRECTIVE, label="DIRECTIVE_001")
        }

        # Must not raise.
        assert_governance_scope_edges_resolve(edges=[edge], nodes_by_urn=nodes_by_urn)

    def test_reports_every_unresolved_edge_not_just_the_first(self) -> None:
        edges = [
            DRGEdge(
                source=artifact_to_urn("mission_type", "research"),
                target=artifact_to_urn("tactic", "phantom-tactic"),
                relation=Relation.SCOPE,
            ),
            DRGEdge(
                source=artifact_to_urn("mission_type", "plan"),
                target=artifact_to_urn("paradigm", "phantom-paradigm"),
                relation=Relation.SCOPE,
            ),
        ]

        with pytest.raises(ValueError) as exc_info:
            assert_governance_scope_edges_resolve(edges=edges, nodes_by_urn={})

        message = str(exc_info.value)
        assert "research:selected_tactics=phantom-tactic" in message
        assert "plan:selected_paradigms=phantom-paradigm" in message


# ---------------------------------------------------------------------------
# #3629 item 2 — end-to-end: generate_graph fails loud, no phantom node
# ---------------------------------------------------------------------------


class TestGenerateGraphFailsLoudOnFictionalGovernanceSelection:
    """End-to-end companion to ``TestAssertGovernanceScopeEdgesResolve``:
    proves the check is actually wired into :func:`generate_graph` against
    a real, fully-minted node universe -- not merely correct in isolation.
    Mirrors this module's own ``_emit_operating_procedure_edges`` fail-
    closed precedent."""

    @staticmethod
    def _copy_real_pack_root(tmp_path: Path) -> Path:
        repo_root = Path(__file__).resolve().parents[4]
        packs_built_in = repo_root / "packs" / "built-in"
        pack_copy = tmp_path / "pack-root"
        shutil.copytree(packs_built_in, pack_copy)
        return pack_copy

    def test_fictional_selected_agent_profile_raises_not_phantom_mints(
        self, tmp_path: Path
    ) -> None:
        pack_root = self._copy_real_pack_root(tmp_path)
        profile_path = pack_root / "missions" / "research" / "governance-profile.yaml"
        original = profile_path.read_text(encoding="utf-8")
        marker = "selected_agent_profiles: []"
        assert marker in original
        profile_path.write_text(
            original.replace(marker, "selected_agent_profiles:\n  - does-not-exist", 1),
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="does-not-exist"):
            generate_graph(pack_root, tmp_path / "output" / "graph.yaml")
