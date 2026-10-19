"""Tests for #3052 edge wiring (WP07): no fabricated edges, and no mission-type edge (#6443).

FR-012 / NFR-007: ``charter synthesize`` emits an edge only where the interview
mapping declares an upstream doctrine relationship, and emits NO edge where no
such relationship is declared (no fabrication).

The ``mission_type`` section used to wire ``directive --requires--> mission_type:<id>``
when the answer named a shipped mission type. No traversal read that edge and the
always-synthesized directive is the *project-intent* directive, not one scoped to a
mission type, so FR-007 (#6443) removed the source: the ``mission_type_urn_candidate``
helper and ``targets._mission_type_evidence_urns`` are gone. The positive evidence
tests were removed with them; this module now pins that no edge is emitted, also when
the answer names a shipped id and the run's DRG snapshot carries the node.

The other sections (``testing_philosophy``, ``neutrality_posture``, ``risk_appetite``,
``quality_gates``, ``review_policy``, ``documentation_policy``) are free-text interview
prompts with no fixed vocabulary tying an answer to an existing DRG URN, so they stay
no-fabrication negative cases.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.offering.drg.models import DRGEdge, DRGGraph, DRGNode

from charter.activation.synthesizer.fixture_adapter import FixtureAdapter
from charter.activation.synthesizer.interview_mapping import resolve_sections
from charter.activation.synthesizer.project_drg import emit_project_layer
from charter.activation.synthesizer.request import SynthesisRequest, SynthesisTarget
from charter.activation.synthesizer.synthesize_pipeline import run_all
from charter.activation.synthesizer.targets import build_targets

pytestmark = [pytest.mark.unit]


_GENERATED_AT = "2026-04-17T00:00:00+00:00"


def _empty_built_in_drg(
    nodes: list[DRGNode] | None = None,
    edges: list[DRGEdge] | None = None,
) -> DRGGraph:
    return DRGGraph(
        schema_version="1.0",
        generated_at=_GENERATED_AT,
        generated_by="test-built-in-layer",
        nodes=nodes or [],
        edges=edges or [],
    )


# ---------------------------------------------------------------------------
# Negative: no declared evidence anywhere -> no fabrication (NFR-007)
# ---------------------------------------------------------------------------


class TestNoFabricationForFreeTextSections:
    """Sections with no fixed vocabulary tying the answer to a DRG URN must
    never synthesize source_urns -- `edges: []` stays `edges: []`."""

    @pytest.mark.parametrize(
        ("section", "answer"),
        [
            ("testing_philosophy", "test-driven development with high coverage"),
            ("neutrality_posture", "balanced"),
            ("risk_appetite", "moderate"),
            ("quality_gates", "coverage >= 90%"),
            ("review_policy", "two reviewers required"),
            ("documentation_policy", "all public APIs must be documented"),
        ],
    )
    def test_free_text_section_never_populates_source_urns(
        self, section: str, answer: str
    ) -> None:
        interview_snapshot = {section: answer}
        drg_snapshot: dict = {"nodes": [], "edges": [], "schema_version": "1.0"}

        sections = resolve_sections(interview_snapshot)
        targets = build_targets(interview_snapshot, sections, drg_snapshot)

        matching = [t for t in targets if t.source_section == section]
        assert matching, f"expected at least one target for section {section!r}"
        for target in matching:
            assert target.source_urns == ()

    @pytest.mark.parametrize(
        ("section", "answer"),
        [
            ("testing_philosophy", "test-driven development with high coverage"),
            ("neutrality_posture", "balanced"),
            ("risk_appetite", "moderate"),
        ],
    )
    def test_free_text_section_overlay_edges_stay_empty(
        self, section: str, answer: str
    ) -> None:
        interview_snapshot = {section: answer}
        drg_snapshot: dict = {"nodes": [], "edges": [], "schema_version": "1.0"}

        sections = resolve_sections(interview_snapshot)
        targets = build_targets(interview_snapshot, sections, drg_snapshot)

        overlay = emit_project_layer(
            targets, spec_kitty_version="test", built_in_drg=_empty_built_in_drg()
        )
        assert overlay.edges == []


class TestMissionTypeAnswerNeverWiresAnEdge:
    """FR-007 (#6443): even a shipped mission-type id, corroborated by the run's own DRG
    snapshot, produces no source URN and no overlay edge."""

    @pytest.mark.parametrize("answer", ["software-dev", "software_dev", "research", "Ship trustworthy agent workflows"])
    def test_no_source_urn_and_no_overlay_edge(self, answer: str) -> None:
        interview_snapshot = {"mission_type": answer}
        drg_snapshot = {
            "nodes": [{"urn": "mission_type:software-dev", "kind": "mission_type"}, {"urn": "mission_type:research", "kind": "mission_type"}],
            "edges": [],
            "schema_version": "1.0",
        }

        sections = resolve_sections(interview_snapshot)
        targets = build_targets(interview_snapshot, sections, drg_snapshot)

        mission_type_target = next(t for t in targets if t.source_section == "mission_type")
        assert mission_type_target.source_urns == ()
        overlay = emit_project_layer(targets, spec_kitty_version="test", built_in_drg=_empty_built_in_drg())
        assert overlay.edges == []


# ---------------------------------------------------------------------------
# End-to-end: full pipeline (resolve -> build -> adapter) via a recorded
# fixture (T029 -- the FixtureAdapter is inputs-hash-keyed and raises on a
# miss; a source_urns-bearing target changes the inputs hash, so this
# exercises a NEWLY recorded fixture at
# tests/charter/fixtures/synthesizer/directive/mission-type-scope-directive/).
# ---------------------------------------------------------------------------


class TestFullPipelineWithRecordedFixture:
    def test_run_all_generates_the_project_intent_directive_without_a_source_urn(self) -> None:
        target = SynthesisTarget(
            kind="directive",
            slug="project-intent-directive",
            title="Project Intent Directive",
            artifact_id="PROJECT_001",
            source_section="mission_type",
        )
        request = SynthesisRequest(
            target=target,
            interview_snapshot={"mission_type": "software-dev"},
            doctrine_snapshot={"directives": {}, "tactics": {}, "styleguides": {}},
            drg_snapshot={
                "nodes": [{"urn": "mission_type:software-dev", "kind": "mission_type"}],
                "edges": [],
                "schema_version": "1.0",
            },
            run_id="01KPE222CD1MMCYEGB3ZCY51VR",
        )
        fixture_root = Path(__file__).parent.parent / "fixtures" / "synthesizer"
        adapter = FixtureAdapter(fixture_root=fixture_root)

        results = run_all(request, adapter=adapter)

        assert len(results) == 1
        body, provenance = results[0]
        assert body["id"] == "PROJECT_001"
        assert list(provenance.source_urns) == []
