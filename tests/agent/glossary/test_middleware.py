"""Tests for glossary extraction middleware (WP03) and semantic check middleware (WP04)."""

import pytest
from kernel.clock import datetime
from pathlib import Path

from tests._perf_helpers import assert_timing_budget
from glossary.middleware import (
    GlossaryCandidateExtractionMiddleware,
    SemanticCheckMiddleware,
    MockContext,
)
from glossary.extraction import ExtractedTerm
from glossary.models import TermSurface, TermSense, Provenance, SenseStatus, ConflictType, Severity
from glossary.scope import GlossaryScope, SCOPE_RESOLUTION_ORDER
from glossary.store import GlossaryStore

pytestmark = pytest.mark.fast

class TestMiddlewareBasics:
    """Basic middleware functionality tests."""

    def test_middleware_initialization_default_fields(self):
        """Middleware initializes with default glossary fields."""
        middleware = GlossaryCandidateExtractionMiddleware()

        assert middleware.glossary_fields == ["description", "prompt", "output"]

    def test_middleware_initialization_custom_fields(self):
        """Middleware initializes with custom glossary fields."""
        middleware = GlossaryCandidateExtractionMiddleware(glossary_fields=["input", "result"])

        assert middleware.glossary_fields == ["input", "result"]


class TestMiddlewareProcess:
    """Tests for middleware process() method (T014)."""

    def test_process_extracts_from_step_input(self):
        """Middleware extracts terms from step_input."""
        middleware = GlossaryCandidateExtractionMiddleware(glossary_fields=["description"])

        context = MockContext(
            step_input={"description": 'The "workspace" is a term.'},
            metadata={},
        )

        result = middleware.process(context)

        # Should extract "workspace" from quoted phrase
        assert len(result.extracted_terms) > 0
        surfaces = {t.surface for t in result.extracted_terms}
        assert "workspace" in surfaces

    def test_process_extracts_from_step_output(self):
        """Middleware extracts terms from step_output."""
        middleware = GlossaryCandidateExtractionMiddleware(glossary_fields=["output"])

        context = MockContext(
            step_output={"output": "The API is an acronym."},
            metadata={},
        )

        result = middleware.process(context)

        # Should extract "api" from acronym pattern
        assert len(result.extracted_terms) > 0
        surfaces = {t.surface for t in result.extracted_terms}
        assert "api" in surfaces

    def test_process_combines_input_and_output(self):
        """Middleware combines step_input and step_output."""
        middleware = GlossaryCandidateExtractionMiddleware(glossary_fields=["description", "output"])

        context = MockContext(
            step_input={"description": 'The "workspace" is here.'},
            step_output={"output": "The API result."},
            metadata={},
        )

        result = middleware.process(context)

        # Should extract from both
        surfaces = {t.surface for t in result.extracted_terms}
        assert "workspace" in surfaces
        assert "api" in surfaces

    def test_process_with_metadata_hints(self):
        """Middleware uses metadata hints (highest confidence)."""
        middleware = GlossaryCandidateExtractionMiddleware()

        context = MockContext(
            step_input={"description": "Some text"},
            metadata={"glossary_watch_terms": ["mission", "primitive"]},
        )

        result = middleware.process(context)

        # Should extract metadata hints
        metadata_terms = [t for t in result.extracted_terms if t.source == "metadata_hint"]
        assert len(metadata_terms) == 2
        surfaces = {t.surface for t in metadata_terms}
        assert surfaces == {"mission", "primitive"}

    def test_process_deduplicates_terms(self):
        """Middleware deduplicates terms from multiple sources."""
        middleware = GlossaryCandidateExtractionMiddleware(glossary_fields=["description"])

        context = MockContext(
            step_input={"description": 'The "workspace" is a work_space.'},
            metadata={"glossary_watch_terms": ["workspace"]},
        )

        result = middleware.process(context)

        # "workspace" appears in metadata, quoted phrase, and casing pattern
        # Should only appear once (metadata takes precedence)
        workspace_terms = [t for t in result.extracted_terms if t.surface == "workspace"]
        assert len(workspace_terms) == 1
        assert workspace_terms[0].source == "metadata_hint"

    def test_process_excludes_filtered_terms(self):
        """Middleware excludes terms in glossary_exclude_terms from metadata hints."""
        middleware = GlossaryCandidateExtractionMiddleware()

        context = MockContext(
            step_input={"description": "Some generic text about workspace"},
            metadata={
                "glossary_watch_terms": ["test", "workspace"],
                "glossary_exclude_terms": ["test"],
            },
        )

        result = middleware.process(context)

        # "test" should be excluded from metadata hints
        # (it might still be extracted from text if it appears there, but it doesn't)
        metadata_surfaces = {t.surface for t in result.extracted_terms if t.source == "metadata_hint"}
        assert "test" not in metadata_surfaces
        assert "workspace" in metadata_surfaces

    def test_process_empty_context(self):
        """Middleware handles empty context gracefully."""
        middleware = GlossaryCandidateExtractionMiddleware()

        context = MockContext()

        result = middleware.process(context)

        # Should not crash, returns empty
        assert len(result.extracted_terms) == 0

    def test_process_respects_configured_fields(self):
        """Middleware only scans configured fields."""
        middleware = GlossaryCandidateExtractionMiddleware(
            glossary_fields=["description"]  # Only scan description
        )

        context = MockContext(
            step_input={
                "description": 'The "workspace" is here.',
                "prompt": 'The "mission" is ignored.',
            },
            metadata={},
        )

        result = middleware.process(context)

        # Should only extract from description
        surfaces = {t.surface for t in result.extracted_terms}
        assert "workspace" in surfaces
        assert "mission" not in surfaces


class TestMiddlewareIntegration:
    """Integration tests for full middleware pipeline."""

    def test_full_extraction_pipeline(self):
        """Full pipeline: metadata hints + heuristics + normalization + scoring."""
        middleware = GlossaryCandidateExtractionMiddleware()

        context = MockContext(
            step_input={
                "description": """
                The "workspace" contains a mission primitive.
                Each WP has a work_package configuration.
                The workspace workspace workspace appears often.
                """
            },
            metadata={
                "glossary_watch_terms": ["primitive"],
                "glossary_aliases": {"WP": "work package"},
            },
        )

        result = middleware.process(context)

        # Should extract:
        # - primitive (metadata_hint, confidence 1.0)
        # - work package (metadata alias, confidence 1.0)
        # - workspace (quoted_phrase, confidence 0.8)
        # - wp (acronym, confidence 0.8)
        # - work_package (casing_pattern, confidence 0.8)
        # - workspace (repeated_noun, confidence 0.5) - deduped with quoted

        assert len(result.extracted_terms) > 0

        # Check metadata hints present
        metadata_terms = [t for t in result.extracted_terms if t.source == "metadata_hint"]
        surfaces = {t.surface for t in metadata_terms}
        assert "primitive" in surfaces
        assert "work package" in surfaces

        # Check confidence ordering (metadata hints first)
        confidences = [t.confidence for t in result.extracted_terms]
        assert confidences[0] == 1.0  # Highest confidence first

    def test_extraction_middleware_functional(self) -> None:
        """Middleware extracts terms for typical input (functional, #4015 split)."""
        middleware = GlossaryCandidateExtractionMiddleware()

        # Typical step input (500 words)
        context = MockContext(
            step_input={
                "description": " ".join(
                    [
                        "The workspace contains a mission primitive.",
                        "Each WP has a work_package configuration.",
                        'The "semantic integrity" is validated.',
                    ]
                    * 50  # ~500 words
                ),
            },
            metadata={
                "glossary_watch_terms": ["workspace", "mission"],
            },
        )

        result = middleware.process(context)

        # Should extract some terms
        assert len(result.extracted_terms) > 0

    @pytest.mark.performance
    def test_performance_within_budget(self) -> None:
        """Middleware completes within performance budget (<100ms, #4015 split)."""
        import time

        middleware = GlossaryCandidateExtractionMiddleware()

        # Typical step input (500 words)
        context = MockContext(
            step_input={
                "description": " ".join(
                    [
                        "The workspace contains a mission primitive.",
                        "Each WP has a work_package configuration.",
                        'The "semantic integrity" is validated.',
                    ]
                    * 50  # ~500 words
                ),
            },
            metadata={
                "glossary_watch_terms": ["workspace", "mission"],
            },
        )

        start = time.perf_counter()
        middleware.process(context)
        elapsed = time.perf_counter() - start

        assert_timing_budget(elapsed, 0.1, name="elapsed")

    def test_adds_to_existing_extracted_terms(self):
        """Middleware appends to existing extracted_terms list."""
        middleware = GlossaryCandidateExtractionMiddleware()

        # Pre-populate extracted_terms
        existing_term = ExtractedTerm(
            surface="existing",
            source="manual",
            confidence=1.0,
            original="existing",
        )

        context = MockContext(
            step_input={"description": 'The "workspace" is a term.'},
            metadata={},
        )
        context.extracted_terms.append(existing_term)

        result = middleware.process(context)

        # Should preserve existing term and add new ones
        assert len(result.extracted_terms) > 1
        surfaces = {t.surface for t in result.extracted_terms}
        assert "existing" in surfaces
        assert "workspace" in surfaces


class TestMiddlewareEdgeCases:
    """Edge case tests for middleware."""

    def test_missing_configured_fields(self):
        """Middleware handles missing configured fields gracefully."""
        middleware = GlossaryCandidateExtractionMiddleware(glossary_fields=["description", "prompt"])

        context = MockContext(
            step_input={"other": "Only other field present"},
            metadata={},
        )

        result = middleware.process(context)

        # Should not crash, returns empty
        assert len(result.extracted_terms) == 0

    def test_none_metadata(self):
        """Middleware handles None metadata gracefully."""
        middleware = GlossaryCandidateExtractionMiddleware()

        context = MockContext(
            step_input={"description": 'The "workspace" is here.'},
            metadata=None,  # type: ignore
        )

        result = middleware.process(context)

        # Should extract from text (no metadata hints)
        assert len(result.extracted_terms) > 0
        surfaces = {t.surface for t in result.extracted_terms}
        assert "workspace" in surfaces

    def test_malformed_metadata(self):
        """Middleware handles malformed metadata gracefully."""
        middleware = GlossaryCandidateExtractionMiddleware()

        context = MockContext(
            step_input={"description": "Some text"},
            metadata={
                "glossary_watch_terms": "not_a_list",  # Should be list
            },
        )

        # Should not crash (extract_metadata_hints handles gracefully)
        # May log warning in production
        result = middleware.process(context)

        # Should still process text (just no metadata hints)
        assert len(result.extracted_terms) >= 0


class TestMetadataDrivenFieldSelection:
    """Regression tests for metadata.glossary_fields runtime override (cycle 3 fix)."""

    def test_metadata_glossary_fields_overrides_constructor(self):
        """metadata.glossary_fields overrides constructor default at runtime."""
        middleware = GlossaryCandidateExtractionMiddleware(
            glossary_fields=["description", "prompt"]  # Constructor default
        )

        context = MockContext(
            step_input={
                "description": 'The "workspace" is in description.',
                "prompt": 'The "mission" is in prompt.',
                "custom_field": 'The "primitive" is in custom_field.',
            },
            metadata={
                "glossary_fields": ["custom_field"]  # Runtime override
            },
        )

        result = middleware.process(context)

        # Should only scan custom_field (metadata override)
        surfaces = {t.surface for t in result.extracted_terms}
        assert "primitive" in surfaces  # From custom_field
        assert "workspace" not in surfaces  # description ignored
        assert "mission" not in surfaces  # prompt ignored

    def test_metadata_glossary_fields_empty_list(self):
        """metadata.glossary_fields=[] scans no fields."""
        middleware = GlossaryCandidateExtractionMiddleware()

        context = MockContext(
            step_input={
                "description": 'The "workspace" is here.',
            },
            metadata={
                "glossary_fields": []  # Empty list = scan nothing
            },
        )

        result = middleware.process(context)

        # Should extract no terms from text (but may have metadata hints)
        text_terms = [t for t in result.extracted_terms if t.source != "metadata_hint"]
        assert len(text_terms) == 0

    def test_metadata_glossary_fields_invalid_type_ignored(self):
        """Invalid metadata.glossary_fields (not list) falls back to constructor."""
        middleware = GlossaryCandidateExtractionMiddleware(glossary_fields=["description"])

        context = MockContext(
            step_input={
                "description": 'The "workspace" is here.',
                "other": 'The "mission" is ignored.',
            },
            metadata={
                "glossary_fields": "not_a_list"  # Invalid type
            },
        )

        result = middleware.process(context)

        # Should fall back to constructor fields (description only)
        surfaces = {t.surface for t in result.extracted_terms}
        assert "workspace" in surfaces  # From description
        assert "mission" not in surfaces  # other field ignored

    def test_metadata_glossary_fields_invalid_elements_ignored(self):
        """metadata.glossary_fields with non-string elements falls back to constructor."""
        middleware = GlossaryCandidateExtractionMiddleware(glossary_fields=["description"])

        context = MockContext(
            step_input={
                "description": 'The "workspace" is here.',
            },
            metadata={
                "glossary_fields": ["description", 123, None]  # Invalid elements
            },
        )

        result = middleware.process(context)

        # Should fall back to constructor fields (invalid list ignored)
        surfaces = {t.surface for t in result.extracted_terms}
        assert "workspace" in surfaces

    def test_metadata_glossary_fields_multiple_fields(self):
        """metadata.glossary_fields with multiple fields scans all of them."""
        middleware = GlossaryCandidateExtractionMiddleware(
            glossary_fields=["description"]  # Constructor default
        )

        context = MockContext(
            step_input={
                "field1": 'The "workspace" is in field1.',
                "field2": 'The "mission" is in field2.',
                "field3": 'The "primitive" is in field3.',
                "ignored": 'The "term" is ignored.',
            },
            metadata={
                "glossary_fields": ["field1", "field2", "field3"]  # Runtime override
            },
        )

        result = middleware.process(context)

        # Should scan all three metadata-specified fields
        surfaces = {t.surface for t in result.extracted_terms}
        assert "workspace" in surfaces  # field1
        assert "mission" in surfaces  # field2
        assert "primitive" in surfaces  # field3
        assert "term" not in surfaces  # ignored field not scanned

    def test_metadata_glossary_fields_with_step_output(self):
        """metadata.glossary_fields applies to both step_input and step_output."""
        middleware = GlossaryCandidateExtractionMiddleware()

        context = MockContext(
            step_input={
                "custom_input": 'The "workspace" is in input.',
            },
            step_output={
                "custom_output": 'The "mission" is in output.',
            },
            metadata={"glossary_fields": ["custom_input", "custom_output"]},
        )

        result = middleware.process(context)

        # Should scan both input and output fields
        surfaces = {t.surface for t in result.extracted_terms}
        assert "workspace" in surfaces  # From step_input
        assert "mission" in surfaces  # From step_output

    def test_metadata_glossary_fields_no_metadata(self):
        """No metadata.glossary_fields uses constructor default."""
        middleware = GlossaryCandidateExtractionMiddleware(glossary_fields=["description"])

        context = MockContext(
            step_input={
                "description": 'The "workspace" is here.',
                "other": 'The "mission" is ignored.',
            },
            metadata={},  # No glossary_fields
        )

        result = middleware.process(context)

        # Should use constructor default (description only)
        surfaces = {t.surface for t in result.extracted_terms}
        assert "workspace" in surfaces
        assert "mission" not in surfaces

    def test_metadata_glossary_fields_combined_with_watch_terms(self):
        """metadata.glossary_fields works alongside glossary_watch_terms."""
        middleware = GlossaryCandidateExtractionMiddleware()

        context = MockContext(
            step_input={
                "custom_field": 'The "workspace" is in custom_field.',
                "ignored_field": 'The "mission" is ignored.',
            },
            metadata={
                "glossary_fields": ["custom_field"],  # Only scan custom_field
                "glossary_watch_terms": ["primitive"],  # Metadata hints
            },
        )

        result = middleware.process(context)

        # Should have metadata hint + text extraction from custom_field only
        surfaces = {t.surface for t in result.extracted_terms}
        assert "primitive" in surfaces  # From glossary_watch_terms
        assert "workspace" in surfaces  # From custom_field text
        assert "mission" not in surfaces  # ignored_field not scanned


class TestEventEmission:
    """Tests for T014: Event emission (stub implementation for WP08).

    These tests verify that the event emission interface is properly defined
    and called for all extracted terms, even though the actual event infrastructure
    is deferred to WP08.
    """

    def test_emit_called_for_each_term(self):
        """_emit_term_candidate_observed is called once per extracted term."""
        middleware = GlossaryCandidateExtractionMiddleware()

        # Track emission calls
        emission_calls = []

        # Monkey-patch the emission method to track calls
        original_emit = middleware._emit_term_candidate_observed

        def track_emit(term, context):
            emission_calls.append((term.surface, term.confidence, term.source))
            return original_emit(term, context)

        middleware._emit_term_candidate_observed = track_emit

        context = MockContext(
            step_input={
                "description": 'The "workspace" and "mission" are quoted terms.',
            },
            metadata={
                "glossary_watch_terms": ["primitive"],  # Metadata hint
            },
        )

        middleware.process(context)

        # Should have emitted events for all extracted terms
        assert len(emission_calls) > 0

        # Verify metadata hint was emitted (confidence 1.0)
        metadata_emissions = [(surf, conf, src) for surf, conf, src in emission_calls if src == "metadata_hint"]
        assert len(metadata_emissions) == 1
        assert metadata_emissions[0][0] == "primitive"
        assert metadata_emissions[0][1] == 1.0

        # Verify quoted phrases were emitted (confidence 0.8)
        quoted_emissions = [(surf, conf, src) for surf, conf, src in emission_calls if src == "quoted_phrase"]
        assert len(quoted_emissions) >= 2
        surfaces = {surf for surf, _, _ in quoted_emissions}
        assert "workspace" in surfaces
        assert "mission" in surfaces

    def test_emit_stub_is_noop(self):
        """_emit_term_candidate_observed stub is safe to call (no-op until WP08)."""
        middleware = GlossaryCandidateExtractionMiddleware()

        context = MockContext(
            step_input={"description": 'The "workspace" is here.'},
        )

        # Should not raise exception (stub is safe)
        result = middleware.process(context)

        # Terms should still be added to context
        assert len(result.extracted_terms) > 0

    def test_emit_interface_contract(self):
        """Event emission method signature matches WP08 contract."""
        from inspect import signature

        middleware = GlossaryCandidateExtractionMiddleware()

        # Check method exists
        assert hasattr(middleware, "_emit_term_candidate_observed")

        # Check signature: (self, term: ExtractedTerm, context: PrimitiveExecutionContext)
        sig = signature(middleware._emit_term_candidate_observed)
        params = list(sig.parameters.keys())

        assert "term" in params, "Expected 'term' parameter"
        assert "context" in params, "Expected 'context' parameter"
        assert len(params) == 2, f"Expected 2 parameters, got {len(params)}"


# ============================================================================
# WP04: SemanticCheckMiddleware Tests (T019)
# ============================================================================


@pytest.fixture
def semantic_check_store(tmp_path: Path) -> GlossaryStore:
    """Create a GlossaryStore with sample data for semantic check tests."""
    store = GlossaryStore(tmp_path / "events.log")

    provenance = Provenance(
        actor_id="user:alice",
        timestamp=datetime(2026, 2, 16, 12, 0, 0),
        source="user_clarification",
    )

    # Add terms for testing different conflict scenarios
    # 1. Single sense (no conflict)
    store.add_sense(
        TermSense(
            surface=TermSurface("feature"),
            scope=GlossaryScope.SPEC_KITTY_CORE.value,
            definition="A unit of work with specifications",
            provenance=provenance,
            confidence=1.0,
            status=SenseStatus.ACTIVE,
        )
    )

    # 2. Multiple senses (ambiguous conflict)
    store.add_sense(
        TermSense(
            surface=TermSurface("workspace"),
            scope=GlossaryScope.MISSION_LOCAL.value,
            definition="Git worktree directory",
            provenance=provenance,
            confidence=1.0,
            status=SenseStatus.ACTIVE,
        )
    )
    store.add_sense(
        TermSense(
            surface=TermSurface("workspace"),
            scope=GlossaryScope.TEAM_DOMAIN.value,
            definition="VS Code workspace file",
            provenance=provenance,
            confidence=0.9,
            status=SenseStatus.ACTIVE,
        )
    )

    return store


class TestSemanticCheckMiddleware:
    """Tests for SemanticCheckMiddleware (WP04 T019, T020)."""

    def test_middleware_initialization_default(self, semantic_check_store: GlossaryStore):
        """SemanticCheckMiddleware initializes with default scope order."""
        middleware = SemanticCheckMiddleware(semantic_check_store)

        assert middleware.glossary_store == semantic_check_store
        assert middleware.scope_order == SCOPE_RESOLUTION_ORDER

    def test_middleware_initialization_custom_scopes(self, semantic_check_store: GlossaryStore):
        """SemanticCheckMiddleware initializes with custom scope order."""
        custom_order = [GlossaryScope.TEAM_DOMAIN, GlossaryScope.SPEC_KITTY_CORE]
        middleware = SemanticCheckMiddleware(semantic_check_store, custom_order)

        assert middleware.scope_order == custom_order

    def test_process_no_conflicts(self, semantic_check_store: GlossaryStore):
        """Middleware processes context with no conflicts."""
        middleware = SemanticCheckMiddleware(semantic_check_store)

        context = MockContext(
            metadata={},
            extracted_terms=[
                ExtractedTerm(
                    surface="feature",
                    source="quoted_phrase",
                    confidence=0.8,
                    original="feature",
                )
            ],
        )
        context.conflicts = []

        result = middleware.process(context)

        # No conflicts should be detected (single sense match)
        assert len(result.conflicts) == 0

    def test_process_unknown_conflict(self, semantic_check_store: GlossaryStore):
        """Middleware detects UNKNOWN conflict for unmatched terms."""
        middleware = SemanticCheckMiddleware(semantic_check_store)

        context = MockContext(
            metadata={},
            extracted_terms=[
                ExtractedTerm(
                    surface="nonexistent",
                    source="quoted_phrase",
                    confidence=0.8,
                    original="nonexistent",
                )
            ],
        )
        context.conflicts = []

        result = middleware.process(context)

        assert len(result.conflicts) == 1
        conflict = result.conflicts[0]
        assert conflict.conflict_type == ConflictType.UNKNOWN
        assert conflict.term.surface_text == "nonexistent"
        assert conflict.severity == Severity.LOW  # High confidence unknown

    def test_process_ambiguous_conflict(self, semantic_check_store: GlossaryStore):
        """Middleware detects AMBIGUOUS conflict for multiple senses."""
        middleware = SemanticCheckMiddleware(semantic_check_store)

        context = MockContext(
            metadata={},
            extracted_terms=[
                ExtractedTerm(
                    surface="workspace",
                    source="quoted_phrase",
                    confidence=0.8,
                    original="workspace",
                )
            ],
        )
        context.conflicts = []

        result = middleware.process(context)

        assert len(result.conflicts) == 1
        conflict = result.conflicts[0]
        assert conflict.conflict_type == ConflictType.AMBIGUOUS
        assert conflict.term.surface_text == "workspace"
        assert conflict.severity == Severity.MEDIUM  # Non-critical step
        assert len(conflict.candidate_senses) == 2

    def test_process_critical_step_severity(self, semantic_check_store: GlossaryStore):
        """Middleware scores HIGH severity for conflicts in critical steps."""
        middleware = SemanticCheckMiddleware(semantic_check_store)

        context = MockContext(
            metadata={"critical_step": True},
            extracted_terms=[
                ExtractedTerm(
                    surface="workspace",
                    source="quoted_phrase",
                    confidence=0.8,
                    original="workspace",
                )
            ],
        )
        context.conflicts = []

        result = middleware.process(context)

        assert len(result.conflicts) == 1
        conflict = result.conflicts[0]
        assert conflict.severity == Severity.HIGH  # Critical step + ambiguous

    def test_process_multiple_terms(self, semantic_check_store: GlossaryStore):
        """Middleware processes multiple extracted terms."""
        middleware = SemanticCheckMiddleware(semantic_check_store)

        context = MockContext(
            metadata={},
            extracted_terms=[
                ExtractedTerm("feature", "quoted_phrase", 0.8, "feature"),
                ExtractedTerm("workspace", "quoted_phrase", 0.8, "workspace"),
                ExtractedTerm("unknown", "quoted_phrase", 0.5, "unknown"),
            ],
        )
        context.conflicts = []

        result = middleware.process(context)

        # Should detect 2 conflicts: ambiguous (workspace) + unknown (unknown)
        assert len(result.conflicts) == 2

        conflict_types = {c.conflict_type for c in result.conflicts}
        assert ConflictType.AMBIGUOUS in conflict_types
        assert ConflictType.UNKNOWN in conflict_types

    def test_process_preserves_existing_conflicts(self, semantic_check_store: GlossaryStore):
        """Middleware extends existing conflicts list."""
        from glossary.models import SemanticConflict

        middleware = SemanticCheckMiddleware(semantic_check_store)

        # Create an existing conflict manually
        existing_conflict = SemanticConflict(
            term=TermSurface("existing"),
            conflict_type=ConflictType.UNKNOWN,
            severity=Severity.LOW,
            confidence=0.8,
            candidate_senses=[],
            context="test",
        )

        context = MockContext(
            metadata={},
            extracted_terms=[ExtractedTerm("workspace", "quoted_phrase", 0.8, "workspace")],
        )
        context.conflicts = [existing_conflict]

        result = middleware.process(context)

        # Should have both existing and new conflict
        assert len(result.conflicts) == 2
        surfaces = {c.term.surface_text for c in result.conflicts}
        assert "existing" in surfaces
        assert "workspace" in surfaces

    def test_process_context_string_populated(self, semantic_check_store: GlossaryStore):
        """Middleware populates context field with extraction source."""
        middleware = SemanticCheckMiddleware(semantic_check_store)

        context = MockContext(
            metadata={},
            extracted_terms=[ExtractedTerm("unknown", "metadata_hint", 1.0, "unknown")],
        )
        context.conflicts = []

        result = middleware.process(context)

        assert len(result.conflicts) == 1
        conflict = result.conflicts[0]
        assert "metadata_hint" in conflict.context

    def test_process_no_critical_step_metadata(self, semantic_check_store: GlossaryStore):
        """Middleware handles missing critical_step metadata gracefully."""
        middleware = SemanticCheckMiddleware(semantic_check_store)

        context = MockContext(
            metadata={},  # No critical_step field
            extracted_terms=[ExtractedTerm("workspace", "quoted_phrase", 0.8, "workspace")],
        )
        context.conflicts = []

        result = middleware.process(context)

        # Should default to is_critical_step=False
        assert len(result.conflicts) == 1
        assert result.conflicts[0].severity == Severity.MEDIUM

    def test_emit_semantic_check_stub(self, semantic_check_store: GlossaryStore):
        """_emit_semantic_check_evaluated stub is safe to call (no-op until WP08)."""
        middleware = SemanticCheckMiddleware(semantic_check_store)

        context = MockContext(
            metadata={},
            extracted_terms=[ExtractedTerm("workspace", "quoted_phrase", 0.8, "workspace")],
        )
        context.conflicts = []

        # Should not raise exception (stub is safe)
        result = middleware.process(context)

        # Conflicts should still be added to context
        assert len(result.conflicts) > 0

    def test_emit_interface_contract(self, semantic_check_store: GlossaryStore):
        """Event emission method signature matches WP08 contract."""
        from inspect import signature


        middleware = SemanticCheckMiddleware(semantic_check_store)

        # Check method exists
        assert hasattr(middleware, "_emit_semantic_check_evaluated")

        # Check signature: (self, context, conflicts)
        sig = signature(middleware._emit_semantic_check_evaluated)
        params = list(sig.parameters.keys())

        assert "context" in params, "Expected 'context' parameter"
        assert "conflicts" in params, "Expected 'conflicts' parameter"
        assert len(params) == 2, f"Expected 2 parameters, got {len(params)}"


class TestSemanticCheckIntegration:
    """Integration tests combining extraction and semantic check middleware."""

    def test_full_pipeline_no_conflicts(self, semantic_check_store: GlossaryStore):
        """Test full pipeline: extract → semantic check (no conflicts)."""
        # 1. Extract terms
        extraction_middleware = GlossaryCandidateExtractionMiddleware(glossary_fields=["description"])

        context = MockContext(
            metadata={},
            step_input={"description": 'The "feature" is defined.'},
        )

        context = extraction_middleware.process(context)

        # 2. Check semantics
        check_middleware = SemanticCheckMiddleware(semantic_check_store)
        context.conflicts = []
        context = check_middleware.process(context)

        # No conflicts (feature has single sense)
        assert len(context.conflicts) == 0

    def test_full_pipeline_with_conflicts(self, semantic_check_store: GlossaryStore):
        """Test full pipeline: extract → semantic check (with conflicts)."""
        # 1. Extract terms
        extraction_middleware = GlossaryCandidateExtractionMiddleware(glossary_fields=["description"])

        context = MockContext(
            metadata={},
            step_input={"description": 'The "workspace" and "unknown" terms.'},
        )

        context = extraction_middleware.process(context)

        # 2. Check semantics
        check_middleware = SemanticCheckMiddleware(semantic_check_store)
        context.conflicts = []
        context = check_middleware.process(context)

        # Should detect conflicts
        assert len(context.conflicts) >= 1

        conflict_types = {c.conflict_type for c in context.conflicts}
        # At least one of: AMBIGUOUS (workspace) or UNKNOWN (unknown)
        assert ConflictType.AMBIGUOUS in conflict_types or ConflictType.UNKNOWN in conflict_types

    def test_middleware_detects_unresolved_critical(self, semantic_check_store: GlossaryStore):
        """Middleware detects UNRESOLVED_CRITICAL for unknown low-confidence terms in critical steps."""
        middleware = SemanticCheckMiddleware(semantic_check_store)

        context = MockContext(
            metadata={"critical_step": True},
            extracted_terms=[
                ExtractedTerm(
                    surface="unknown_critical_term",
                    source="quoted_phrase",
                    confidence=0.3,  # Low confidence
                    original="unknown_critical_term",
                )
            ],
        )
        context.conflicts = []

        result = middleware.process(context)

        assert len(result.conflicts) == 1
        conflict = result.conflicts[0]
        assert conflict.conflict_type == ConflictType.UNRESOLVED_CRITICAL
        assert conflict.severity == Severity.HIGH  # Always high for unresolved critical

    def test_middleware_detects_inconsistent(self, semantic_check_store: GlossaryStore):
        """Middleware detects INCONSISTENT for contradictory usage of known terms."""
        middleware = SemanticCheckMiddleware(semantic_check_store)

        # LLM output that contradicts the glossary definition
        llm_output_with_contradiction = (
            "The feature is not a unit of work. The feature refers to a plugin or extension module."
        )

        context = MockContext(
            metadata={},
            step_input={"description": 'Using the "feature" term.'},
            step_output={"result": llm_output_with_contradiction},
            extracted_terms=[
                ExtractedTerm(
                    surface="feature",
                    source="quoted_phrase",
                    confidence=0.8,
                    original="feature",
                )
            ],
        )
        context.conflicts = []

        result = middleware.process(context)

        # Should detect INCONSISTENT conflict
        assert len(result.conflicts) == 1
        conflict = result.conflicts[0]
        assert conflict.conflict_type == ConflictType.INCONSISTENT
        assert conflict.severity == Severity.LOW  # Always low (informational)

    def test_middleware_all_four_conflict_types(self, semantic_check_store: GlossaryStore):
        """Middleware can detect all 4 conflict types in a single pass."""
        middleware = SemanticCheckMiddleware(semantic_check_store)

        # Prepare LLM output with contradiction for "feature"
        llm_output = "The feature is not a unit of work. The feature refers to something else entirely."

        context = MockContext(
            metadata={"critical_step": True},
            step_input={"description": ('Using "feature", "workspace", "unknown_term", and "critical_unknown".')},
            step_output={"result": llm_output},
            extracted_terms=[
                # INCONSISTENT: known term with contradictory usage
                ExtractedTerm("feature", "quoted_phrase", 0.8, "feature"),
                # AMBIGUOUS: multiple active senses
                ExtractedTerm("workspace", "quoted_phrase", 0.8, "workspace"),
                # UNKNOWN: no match, high confidence
                ExtractedTerm("unknown_term", "quoted_phrase", 0.9, "unknown_term"),
                # UNRESOLVED_CRITICAL: no match, low confidence, critical step
                ExtractedTerm("critical_unknown", "quoted_phrase", 0.3, "critical_unknown"),
            ],
        )
        context.conflicts = []

        result = middleware.process(context)

        # Should detect 4 conflicts (one of each type)
        assert len(result.conflicts) == 4

        conflict_types = {c.conflict_type for c in result.conflicts}
        assert ConflictType.INCONSISTENT in conflict_types
        assert ConflictType.AMBIGUOUS in conflict_types
        assert ConflictType.UNKNOWN in conflict_types
        assert ConflictType.UNRESOLVED_CRITICAL in conflict_types

        # Verify severity assignments
        for conflict in result.conflicts:
            if conflict.conflict_type == ConflictType.INCONSISTENT:
                assert conflict.severity == Severity.LOW
            elif conflict.conflict_type == ConflictType.AMBIGUOUS:
                assert conflict.severity == Severity.HIGH  # Critical step
            elif conflict.conflict_type == ConflictType.UNRESOLVED_CRITICAL:
                assert conflict.severity == Severity.HIGH
            elif conflict.conflict_type == ConflictType.UNKNOWN and conflict.term.surface_text == "unknown_term":
                assert conflict.severity == Severity.LOW
