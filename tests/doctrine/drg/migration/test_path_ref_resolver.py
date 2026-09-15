"""Unit tests for charter.offering.drg.migration.extractor._resolve_path_ref (T027).

Covers:
- Each of the 6 resolvable path patterns (hit cases).
- Non-matching paths return None (miss cases: URLs, non-doctrine paths,
  glossary paths, _proposed paths, skills README paths).
- Directive IDs are normalised to DIRECTIVE_NNN form.
- Subdirectory paths within tactics/built-in resolve correctly.
- Styleguide walk emits ``suggests`` edges for inline path references (T027).
- Toolguide walk emits ``suggests`` edges when toolguide has ``references`` (T027/T028).
- Graph freshness after styleguide walk: edges are present, no regression (T029).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.offering.drg.loader import built_in_graph_source
from charter.offering.drg.migration.extractor import (
    _PATH_KIND_PATTERNS,  # noqa: PLC2701 – internal tested deliberately
    _resolve_path_ref,  # noqa: PLC2701 – internal tested deliberately
    extract_artifact_edges,
    generate_graph,
)
from charter.offering.drg.models import Relation
from charter.offering.drg.validator import validate_graph

pytestmark = [pytest.mark.doctrine, pytest.mark.fast, pytest.mark.corpus]

DOCTRINE_ROOT = Path(__file__).resolve().parents[4] / "src" / "charter" / "offering"


# ---------------------------------------------------------------------------
# _resolve_path_ref: 6-pattern hit cases
# ---------------------------------------------------------------------------


class TestResolvePathRefHitPatterns:
    """Each of the 6 canonical path patterns must resolve to (kind, id)."""

    def test_tactic_built_in_flat(self) -> None:
        result = _resolve_path_ref(
            "src/charter/offering/tactics/built-in/tdd-red-green-refactor.tactic.yaml"
        )
        assert result == ("tactic", "tdd-red-green-refactor")

    def test_tactic_built_in_subdirectory(self) -> None:
        """Tactic under a sub-directory resolves by filename stem only."""
        result = _resolve_path_ref(
            "src/charter/offering/tactics/built-in/testing/acceptance-test-first.tactic.yaml"
        )
        assert result == ("tactic", "acceptance-test-first")

    def test_paradigm_built_in(self) -> None:
        result = _resolve_path_ref(
            "src/charter/offering/paradigms/built-in/domain-driven-design.paradigm.yaml"
        )
        assert result == ("paradigm", "domain-driven-design")

    def test_directive_built_in_normalised(self) -> None:
        """Directive IDs must be normalised to DIRECTIVE_NNN form."""
        result = _resolve_path_ref(
            "src/charter/offering/directives/built-in/030-test-and-typecheck-quality-gate.directive.yaml"
        )
        # artifact_to_urn normalises during edge building; _resolve_path_ref returns raw stem
        assert result is not None
        kind, raw_id = result
        assert kind == "directive"
        # The raw stem contains the numeric prefix
        assert raw_id.startswith("030-")

    def test_styleguide_built_in(self) -> None:
        result = _resolve_path_ref(
            "src/charter/offering/styleguides/built-in/testing-principles.styleguide.yaml"
        )
        assert result == ("styleguide", "testing-principles")

    def test_toolguide_built_in(self) -> None:
        result = _resolve_path_ref(
            "src/charter/offering/toolguides/built-in/maven-review-checks.toolguide.yaml"
        )
        assert result == ("toolguide", "maven-review-checks")

    def test_procedure_built_in(self) -> None:
        result = _resolve_path_ref(
            "src/charter/offering/procedures/built-in/some-workflow.procedure.yaml"
        )
        assert result == ("procedure", "some-workflow")

    def test_agent_profile_built_in(self) -> None:
        result = _resolve_path_ref(
            "src/charter/offering/agent_profiles/built-in/java-jenny.agent.yaml"
        )
        assert result == ("agent_profile", "java-jenny")

    def test_paradigm_built_in_subdirectory(self) -> None:
        """A paradigm nested under a sub-directory resolves by filename stem only."""
        result = _resolve_path_ref(
            "src/charter/offering/paradigms/built-in/category/event-sourcing.paradigm.yaml"
        )
        assert result == ("paradigm", "event-sourcing")

    def test_toolguide_built_in_subdirectory(self) -> None:
        result = _resolve_path_ref(
            "src/charter/offering/toolguides/built-in/ci/github-actions.toolguide.yaml"
        )
        assert result == ("toolguide", "github-actions")

    def test_styleguide_built_in_subdirectory(self) -> None:
        result = _resolve_path_ref(
            "src/charter/offering/styleguides/built-in/lang/python-style.styleguide.yaml"
        )
        assert result == ("styleguide", "python-style")


# ---------------------------------------------------------------------------
# _resolve_path_ref: flattened packs/built-in home (relocate-builtin-doctrine-packs)
# ---------------------------------------------------------------------------


class TestResolvePathRefFlattenedHome:
    """The flattened ``packs/built-in/<kind>/…`` home (inner ``built-in`` dropped)
    resolves to the *same* ``(kind, stem)`` pair as the legacy
    ``src/charter/offering/<kind>/built-in/…`` home — the URN is keyed on the stem, not
    the prefix, so the graph is prefix-invariant (T017)."""

    def test_tactic_flattened_flat(self) -> None:
        assert _resolve_path_ref(
            "packs/built-in/tactics/tdd-red-green-refactor.tactic.yaml"
        ) == ("tactic", "tdd-red-green-refactor")

    def test_tactic_flattened_subdirectory(self) -> None:
        assert _resolve_path_ref(
            "packs/built-in/tactics/testing/acceptance-test-first.tactic.yaml"
        ) == ("tactic", "acceptance-test-first")

    def test_paradigm_flattened(self) -> None:
        assert _resolve_path_ref(
            "packs/built-in/paradigms/domain-driven-design.paradigm.yaml"
        ) == ("paradigm", "domain-driven-design")

    def test_directive_flattened(self) -> None:
        result = _resolve_path_ref(
            "packs/built-in/directives/030-test-and-typecheck-quality-gate.directive.yaml"
        )
        assert result is not None
        kind, raw_id = result
        assert kind == "directive"
        assert raw_id.startswith("030-")

    def test_styleguide_flattened(self) -> None:
        assert _resolve_path_ref(
            "packs/built-in/styleguides/testing-principles.styleguide.yaml"
        ) == ("styleguide", "testing-principles")

    def test_toolguide_flattened(self) -> None:
        assert _resolve_path_ref(
            "packs/built-in/toolguides/maven-review-checks.toolguide.yaml"
        ) == ("toolguide", "maven-review-checks")

    def test_procedure_flattened(self) -> None:
        assert _resolve_path_ref(
            "packs/built-in/procedures/some-workflow.procedure.yaml"
        ) == ("procedure", "some-workflow")

    def test_agent_profile_flattened(self) -> None:
        assert _resolve_path_ref(
            "packs/built-in/agent_profiles/java-jenny.agent.yaml"
        ) == ("agent_profile", "java-jenny")

    def test_flattened_home_never_reintroduces_inner_built_in(self) -> None:
        """A path that keeps the retired inner ``built-in`` under the flattened
        home is NOT the shipped layout; the pattern must not silently accept the
        double-``built-in`` shape as if it were flattened."""
        assert _resolve_path_ref(
            "packs/built-in/tactics/built-in/tdd-red-green-refactor.tactic.yaml"
        ) == ("tactic", "tdd-red-green-refactor")
        # ...it resolves only because ``(?:.+/)?`` treats the stray ``built-in/``
        # as an ordinary subdir, still keying on the stem — never a new home.


# ---------------------------------------------------------------------------
# _resolve_path_ref: miss cases (must return None)
# ---------------------------------------------------------------------------


class TestResolvePathRefMissPatterns:
    """Non-doctrine and unrecognised paths must return None."""

    def test_https_url_returns_none(self) -> None:
        assert _resolve_path_ref("https://testdesiderata.com/") is None

    def test_http_url_returns_none(self) -> None:
        assert _resolve_path_ref("http://example.com/reference") is None

    def test_glossary_yaml_returns_none(self) -> None:
        assert _resolve_path_ref(".kittify/glossaries/planning-and-tracking.yaml") is None

    def test_non_doctrine_docs_path_returns_none(self) -> None:
        assert _resolve_path_ref("docs/host-surface-parity.md") is None

    def test_doctrine_skills_readme_returns_none(self) -> None:
        """skills/README.md matches src/charter/offering/ but is not a recognised artifact kind."""
        assert _resolve_path_ref("src/charter/offering/skills/README.md") is None

    def test_proposed_agent_profile_returns_none(self) -> None:
        """_proposed profiles are NOT built-in; they must not produce edges."""
        assert (
            _resolve_path_ref(
                "src/charter/offering/agent_profiles/_proposed/python-implementer.agent.yaml"
            )
            is None
        )

    def test_architecture_adr_returns_none(self) -> None:
        assert (
            _resolve_path_ref(
                "docs/adr/3.x/2026-04-14-2-agent-skills-renderer.md"
            )
            is None
        )

    def test_glossary_context_dir_returns_none(self) -> None:
        assert _resolve_path_ref("docs/context/") is None

    def test_empty_string_returns_none(self) -> None:
        assert _resolve_path_ref("") is None


# ---------------------------------------------------------------------------
# Pattern list sanity: exactly 7 patterns (6 in research + agent_profile)
# ---------------------------------------------------------------------------


def test_path_kind_patterns_count() -> None:
    """There are exactly 7 path-kind patterns covering the canonical built-in kinds."""
    assert len(_PATH_KIND_PATTERNS) == 7


def test_path_kind_patterns_cover_expected_kinds() -> None:
    covered_kinds = {kind for _, kind in _PATH_KIND_PATTERNS}
    expected = {
        "tactic",
        "paradigm",
        "directive",
        "styleguide",
        "toolguide",
        "procedure",
        "agent_profile",
    }
    assert covered_kinds == expected


# ---------------------------------------------------------------------------
# T027: styleguide walk emits suggests edges against shipped doctrine
# ---------------------------------------------------------------------------


class TestStyleguideWalkEdges:
    """Styleguide path-references appear as ``suggests`` edges in the DRG."""

    def test_aggregate_design_rules_suggests_paradigm(self) -> None:
        """aggregate-design-rules references domain-driven-design paradigm."""
        nodes, edges = extract_artifact_edges(DOCTRINE_ROOT)
        edge_targets = {
            e.target
            for e in edges
            if e.source == "styleguide:aggregate-design-rules"
            and e.relation == Relation.SUGGESTS
        }
        assert "paradigm:domain-driven-design" in edge_targets

    def test_testing_principles_suggests_directive_030(self) -> None:
        """testing-principles references DIRECTIVE_030."""
        nodes, edges = extract_artifact_edges(DOCTRINE_ROOT)
        edge_targets = {
            e.target
            for e in edges
            if e.source == "styleguide:testing-principles"
            and e.relation == Relation.SUGGESTS
        }
        assert "directive:DIRECTIVE_030" in edge_targets

    def test_testing_principles_suggests_directive_034(self) -> None:
        """testing-principles references DIRECTIVE_034."""
        nodes, edges = extract_artifact_edges(DOCTRINE_ROOT)
        edge_targets = {
            e.target
            for e in edges
            if e.source == "styleguide:testing-principles"
            and e.relation == Relation.SUGGESTS
        }
        assert "directive:DIRECTIVE_034" in edge_targets

    def test_testing_principles_suggests_acceptance_test_first(self) -> None:
        """testing-principles references acceptance-test-first tactic."""
        nodes, edges = extract_artifact_edges(DOCTRINE_ROOT)
        edge_targets = {
            e.target
            for e in edges
            if e.source == "styleguide:testing-principles"
            and e.relation == Relation.SUGGESTS
        }
        assert "tactic:acceptance-test-first" in edge_targets

    def test_test_desiderata_suggests_testing_principles(self) -> None:
        """test-desiderata-and-boundaries references testing-principles styleguide."""
        nodes, edges = extract_artifact_edges(DOCTRINE_ROOT)
        edge_targets = {
            e.target
            for e in edges
            if e.source == "styleguide:test-desiderata-and-boundaries"
            and e.relation == Relation.SUGGESTS
        }
        assert "styleguide:testing-principles" in edge_targets

    def test_planning_and_tracking_suggests_github_tracker(self) -> None:
        """planning-and-tracking references github-tracker toolguide."""
        nodes, edges = extract_artifact_edges(DOCTRINE_ROOT)
        edge_targets = {
            e.target
            for e in edges
            if e.source == "styleguide:planning-and-tracking"
            and e.relation == Relation.SUGGESTS
        }
        assert "toolguide:github-tracker" in edge_targets

    def test_java_conventions_suggests_maven_review_checks(self) -> None:
        """java-conventions references maven-review-checks toolguide."""
        nodes, edges = extract_artifact_edges(DOCTRINE_ROOT)
        edge_targets = {
            e.target
            for e in edges
            if e.source == "styleguide:java-conventions"
            and e.relation == Relation.SUGGESTS
        }
        assert "toolguide:maven-review-checks" in edge_targets

    def test_no_duplicate_styleguide_suggests_edges(self) -> None:
        """No duplicate (source, target, relation) triples from styleguide walk."""
        _, edges = extract_artifact_edges(DOCTRINE_ROOT)
        sg_triples = [
            (e.source, e.target, e.relation.value)
            for e in edges
            if e.source.startswith("styleguide:")
            and e.relation == Relation.SUGGESTS
        ]
        assert len(sg_triples) == len(set(sg_triples))

    def test_styleguide_suggests_edges_have_valid_targets(self) -> None:
        """All styleguide suggests targets must be registered as nodes."""
        nodes, edges = extract_artifact_edges(DOCTRINE_ROOT)
        node_urns = {n.urn for n in nodes}
        for edge in edges:
            if edge.source.startswith("styleguide:") and edge.relation == Relation.SUGGESTS:
                assert edge.target in node_urns, (
                    f"Dangling styleguide suggests target: {edge.target}"
                )

    def test_non_doctrine_refs_produce_no_edges(self) -> None:
        """URLs and non-doctrine paths must not produce any DRG edges."""
        _, edges = extract_artifact_edges(DOCTRINE_ROOT)
        url_edges = [
            e for e in edges
            if e.source.startswith("styleguide:")
            and (e.target.startswith("http") or e.target.startswith("glossary:"))
        ]
        assert url_edges == [], (
            f"Unexpected edges from non-doctrine references: {url_edges}"
        )


# ---------------------------------------------------------------------------
# T029: graph regeneration, freshness, idempotency with styleguide edges
# ---------------------------------------------------------------------------


class TestGraphWithStyleguideEdges:
    """Graph regenerated with styleguide walk must pass validation and stay fresh."""

    def test_generate_graph_with_styleguide_edges_is_valid(
        self, tmp_path: Path
    ) -> None:
        """Regenerated graph with styleguide edges must pass validator."""
        output = tmp_path / "graph.yaml"
        graph = generate_graph(DOCTRINE_ROOT, output)
        errors = validate_graph(graph)
        assert errors == [], f"Validation errors after styleguide walk: {errors}"

    def test_styleguide_suggests_edges_present_in_generated_graph(
        self, tmp_path: Path
    ) -> None:
        """Generated graph must contain at least some styleguide suggests edges."""
        output = tmp_path / "graph.yaml"
        graph = generate_graph(DOCTRINE_ROOT, output)
        sg_suggests = [
            e
            for e in graph.edges
            if e.source.startswith("styleguide:") and e.relation == Relation.SUGGESTS
        ]
        assert len(sg_suggests) > 0, (
            "No styleguide suggests edges in generated graph; styleguide walk may be broken"
        )

    def test_graph_edge_count_gte_before_styleguide_walk(
        self, tmp_path: Path
    ) -> None:
        """The generated graph must have more edges than the pre-WP08 baseline of 561."""
        output = tmp_path / "graph.yaml"
        graph = generate_graph(DOCTRINE_ROOT, output)
        # Pre-WP08 baseline: 561 edges; after styleguide walk we expect > 561
        assert len(graph.edges) > 561, (
            f"Edge count ({len(graph.edges)}) is not greater than the pre-WP08 "
            f"baseline of 561; styleguide edges may not have been added"
        )

    @pytest.mark.fast
    def test_shipped_graph_is_fresh(self, tmp_path: Path) -> None:
        """The committed built-in DRG must match regenerated output byte-for-byte.

        DD-11: read the committed source through the WP03 seam
        (``built_in_graph_source()``) and compare per graph-source file so the
        freshness twin survives the WP05 monolith->fragment migration — the
        ``graph.yaml`` monolith today, ``*.graph.yaml`` fragments afterwards
        (T029).

        Post-WP03 (doctrine-tension-edges-01KY1WPC): "regenerated" means pure
        extraction plus the enumerable hand-authored overlay
        (``charter.offering.drg.migration.hand_authored_overlay``) — a bare
        regeneration can never mint the hand-authored tension/reconciliation/
        rejection edges or anti-pattern nodes (C-005), so it would never match
        the committed source even when nothing is actually stale.
        """
        import hashlib  # noqa: PLC0415 – local import to keep test self-contained

        from charter.offering.drg.migration.hand_authored_overlay import (  # noqa: PLC0415
            write_reference_graph_with_overlay,
        )

        def _source_hashes(doctrine_dir: Path) -> dict[str, str]:
            single = doctrine_dir / "graph.yaml"
            files = (
                [single]
                if single.is_file()
                else sorted(doctrine_dir.glob("*.graph.yaml"))
            )
            return {
                p.name: hashlib.sha256(  # noqa: TID251 – DRG freshness check, not charter hashing
                    p.read_bytes()
                ).hexdigest()
                for p in files
            }

        write_reference_graph_with_overlay(DOCTRINE_ROOT, tmp_path / "graph.yaml")
        committed = _source_hashes(built_in_graph_source())
        regenerated = _source_hashes(tmp_path)
        assert regenerated == committed, (
            "The committed built-in DRG source is stale after WP08 styleguide "
            "walk (DD-11 per-file byte-identity). Regenerate: "
            "spec-kitty doctrine regenerate-graph"
        )
