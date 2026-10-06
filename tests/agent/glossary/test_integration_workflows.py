"""Cross-module integration tests for glossary semantic integrity (WP11 / T050).

These tests verify end-to-end workflows that span multiple glossary modules,
exercising the full pipeline from term extraction through conflict detection,
clarification, generation gating, event emission, and checkpoint/resume.

Each test scenario creates realistic repo structures with seed files and config,
constructs PrimitiveExecutionContext objects, and exercises the full middleware
chain via create_standard_pipeline(). Unlike the existing pipeline integration
tests (test_pipeline_integration.py) which focus on individual pipeline
features, these tests validate multi-step cross-module workflows.
"""

import statistics
import time

import pytest

from glossary.exceptions import BlockedByConflict
from glossary.models import ConflictType, Severity
from glossary.pipeline import (
    create_standard_pipeline,
)
from glossary.strictness import Strictness
from specify_cli.missions import PrimitiveExecutionContext
from tests._perf_helpers import assert_timing_budget

pytestmark = pytest.mark.fast
# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_seed_file(tmp_path, scope_name, terms_yaml):
    """Create a seed file in .kittify/glossaries/."""
    glossaries = tmp_path / ".kittify" / "glossaries"
    glossaries.mkdir(parents=True, exist_ok=True)
    seed_file = glossaries / f"{scope_name}.yaml"
    seed_file.write_text(terms_yaml)
    return seed_file


def _create_config(tmp_path, config_yaml):
    """Create .kittify/config.yaml."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    config_file = kittify / "config.yaml"
    config_file.write_text(config_yaml)
    return config_file


def _setup_multi_scope_repo(tmp_path):
    """Create a realistic multi-scope repo with team_domain and spec_kitty_core terms.

    Returns:
        tmp_path (the repo root)
    """
    # Team domain terms: "workspace" is ambiguous (2 active senses)
    _create_seed_file(
        tmp_path,
        "team_domain",
        (
            "terms:\n"
            "  - surface: workspace\n"
            "    definition: Git worktree directory for a work package\n"
            "    confidence: 0.9\n"
            "    status: active\n"
            "  - surface: workspace\n"
            "    definition: VS Code workspace configuration file\n"
            "    confidence: 0.7\n"
            "    status: active\n"
            "  - surface: pipeline\n"
            "    definition: CI/CD workflow automation\n"
            "    confidence: 1.0\n"
            "    status: active\n"
            "  - surface: artifact\n"
            "    definition: Build output file (binary, package, image)\n"
            "    confidence: 0.95\n"
            "    status: active\n"
        ),
    )

    # Spec kitty core terms: unambiguous
    _create_seed_file(
        tmp_path,
        "spec_kitty_core",
        (
            "terms:\n"
            "  - surface: mission\n"
            "    definition: Structured workflow with primitives and steps\n"
            "    confidence: 1.0\n"
            "    status: active\n"
            "  - surface: primitive\n"
            "    definition: Atomic mission operation (specify, plan, implement)\n"
            "    confidence: 1.0\n"
            "    status: active\n"
        ),
    )

    return tmp_path


# ---------------------------------------------------------------------------
# Scenario 1: Full workflow -- specify -> conflict -> clarify -> resume
# ---------------------------------------------------------------------------


class TestFullWorkflowSpecifyClarifyResume:
    """End-to-end: specify step -> extraction -> conflict -> clarification -> gate passes."""

    def test_interactive_clarification_resolves_conflict_and_pipeline_completes(self, tmp_path, monkeypatch):
        """User selects a candidate sense for an ambiguous term. The pipeline
        should complete without raising BlockedByConflict, even under MEDIUM
        strictness (which would block unresolved HIGH-severity conflicts)."""
        _setup_multi_scope_repo(tmp_path)

        # Mock prompt: user selects first candidate
        prompt_calls = []

        def mock_prompt(conflict, candidates):
            prompt_calls.append(conflict.term.surface_text)
            conflict.selected_index = 0
            return ("select", None)

        monkeypatch.setattr(
            "glossary.pipeline.prompt_conflict_resolution_safe",
            mock_prompt,
        )

        ctx = PrimitiveExecutionContext(
            step_id="specify-001",
            mission_id="software-dev",
            run_id="run-int-001",
            inputs={
                "description": ("Implement workspace management feature with artifact storage"),
            },
            metadata={
                "glossary_check": "enabled",
                "glossary_watch_terms": ["workspace"],
                "critical_step": True,  # AMBIGUOUS -> HIGH severity
            },
            config={},
        )

        pipeline = create_standard_pipeline(
            tmp_path,
            runtime_strictness=Strictness.MEDIUM,
            interaction_mode="interactive",
        )

        result = pipeline.process(ctx)

        # Pipeline completed (no BlockedByConflict)
        assert result.effective_strictness == Strictness.MEDIUM

        # User was prompted for the ambiguous "workspace" term
        assert "workspace" in prompt_calls

        # Conflict was resolved (moved to resolved_conflicts, not in conflicts)
        remaining_workspace = [c for c in result.conflicts if c.term.surface_text == "workspace"]
        assert len(remaining_workspace) == 0

        resolved = getattr(result, "resolved_conflicts", [])
        resolved_surfaces = [c.term.surface_text for c in resolved]
        assert "workspace" in resolved_surfaces

    def test_custom_definition_resolves_and_emits_sense_update(self, tmp_path, monkeypatch):
        """User provides a custom definition for an ambiguous term.
        Pipeline should complete and the custom sense is treated as resolution."""
        _setup_multi_scope_repo(tmp_path)

        def mock_prompt(conflict, candidates):
            return ("custom", "The project working directory on disk")

        monkeypatch.setattr(
            "glossary.pipeline.prompt_conflict_resolution_safe",
            mock_prompt,
        )

        ctx = PrimitiveExecutionContext(
            step_id="specify-002",
            mission_id="software-dev",
            run_id="run-int-002",
            inputs={"description": "Configure workspace settings"},
            metadata={
                "glossary_watch_terms": ["workspace"],
            },
            config={},
        )

        pipeline = create_standard_pipeline(
            tmp_path,
            runtime_strictness=Strictness.MAX,
            interaction_mode="interactive",
        )

        # Even MAX strictness: custom definition resolves the conflict
        result = pipeline.process(ctx)

        assert result.effective_strictness == Strictness.MAX
        assert len(result.conflicts) == 0

        resolved = getattr(result, "resolved_conflicts", [])
        assert len(resolved) >= 1
        assert resolved[0].term.surface_text == "workspace"

    def test_multi_term_workflow_only_ambiguous_terms_prompt(self, tmp_path, monkeypatch):
        """When input contains both ambiguous and unambiguous terms, only the
        ambiguous ones trigger clarification prompts."""
        _setup_multi_scope_repo(tmp_path)

        prompted_terms = []

        def mock_prompt(conflict, candidates):
            prompted_terms.append(conflict.term.surface_text)
            conflict.selected_index = 0
            return ("select", None)

        monkeypatch.setattr(
            "glossary.pipeline.prompt_conflict_resolution_safe",
            mock_prompt,
        )

        ctx = PrimitiveExecutionContext(
            step_id="specify-003",
            mission_id="software-dev",
            run_id="run-int-003",
            inputs={"description": "test"},
            metadata={
                "glossary_watch_terms": ["workspace", "mission", "pipeline"],
            },
            config={},
        )

        pipeline = create_standard_pipeline(
            tmp_path,
            runtime_strictness=Strictness.MAX,
            interaction_mode="interactive",
        )

        result = pipeline.process(ctx)

        # Only "workspace" is ambiguous (2 active senses)
        # "mission" and "pipeline" each have 1 active sense -> no conflict
        assert "workspace" in prompted_terms
        assert "mission" not in prompted_terms
        assert "pipeline" not in prompted_terms

        assert len(result.conflicts) == 0


# ---------------------------------------------------------------------------
# Scenario 2: Defer workflow -- user defers conflict
# ---------------------------------------------------------------------------


class TestDeferWorkflow:
    """User defers conflict resolution. Conflict should remain unresolved
    and the generation gate should block (under MEDIUM/MAX strictness)."""

    def test_defer_leaves_conflict_unresolved_and_gate_blocks(self, tmp_path, monkeypatch):
        """Deferring a HIGH-severity ambiguous conflict under MEDIUM strictness
        should result in BlockedByConflict."""
        _setup_multi_scope_repo(tmp_path)

        def mock_prompt(conflict, candidates):
            return ("defer", None)

        monkeypatch.setattr(
            "glossary.pipeline.prompt_conflict_resolution_safe",
            mock_prompt,
        )

        ctx = PrimitiveExecutionContext(
            step_id="specify-defer-001",
            mission_id="software-dev",
            run_id="run-int-004",
            inputs={"description": "Configure workspace settings"},
            metadata={
                "glossary_watch_terms": ["workspace"],
                "critical_step": True,
            },
            config={},
        )

        pipeline = create_standard_pipeline(
            tmp_path,
            runtime_strictness=Strictness.MEDIUM,
            interaction_mode="interactive",
        )

        with pytest.raises(BlockedByConflict) as exc_info:
            pipeline.process(ctx)

        # Exception contains the unresolved workspace conflict
        conflict_terms = {c.term.surface_text for c in exc_info.value.conflicts}
        assert "workspace" in conflict_terms

    def test_defer_under_off_strictness_completes(self, tmp_path, monkeypatch):
        """Even when user defers, OFF strictness never blocks."""
        _setup_multi_scope_repo(tmp_path)

        def mock_prompt(conflict, candidates):
            return ("defer", None)

        monkeypatch.setattr(
            "glossary.pipeline.prompt_conflict_resolution_safe",
            mock_prompt,
        )

        ctx = PrimitiveExecutionContext(
            step_id="specify-defer-002",
            mission_id="software-dev",
            run_id="run-int-005",
            inputs={"description": "Configure workspace settings"},
            metadata={
                "glossary_watch_terms": ["workspace"],
            },
            config={},
        )

        pipeline = create_standard_pipeline(
            tmp_path,
            runtime_strictness=Strictness.OFF,
            interaction_mode="interactive",
        )

        # OFF strictness: no blocking regardless of deferred conflicts
        result = pipeline.process(ctx)

        assert result.effective_strictness == Strictness.OFF
        # Conflict remains unresolved (deferred)
        workspace_conflicts = [c for c in result.conflicts if c.term.surface_text == "workspace"]
        assert len(workspace_conflicts) >= 1

    def test_non_interactive_mode_defers_all(self, tmp_path):
        """In non-interactive mode with MAX strictness, all conflicts defer
        and the gate blocks."""
        _setup_multi_scope_repo(tmp_path)

        ctx = PrimitiveExecutionContext(
            step_id="specify-ni-001",
            mission_id="software-dev",
            run_id="run-int-006",
            inputs={"description": "workspace test"},
            metadata={
                "glossary_watch_terms": ["workspace"],
            },
            config={},
        )

        pipeline = create_standard_pipeline(
            tmp_path,
            runtime_strictness=Strictness.MAX,
            interaction_mode="non-interactive",
        )

        with pytest.raises(BlockedByConflict):
            pipeline.process(ctx)


# ---------------------------------------------------------------------------
# Scenario 3: Pipeline skip when disabled
# ---------------------------------------------------------------------------


class TestPipelineSkipWhenDisabled:
    """Pipeline must skip all processing when glossary checks are disabled."""

    def test_disabled_via_metadata_skips_extraction(self, tmp_path):
        """glossary_check: disabled in metadata -> no extraction, no conflicts."""
        _setup_multi_scope_repo(tmp_path)

        ctx = PrimitiveExecutionContext(
            step_id="plan-001",
            mission_id="software-dev",
            run_id="run-int-007",
            inputs={
                "description": "This has workspace and pipeline terms everywhere",
            },
            metadata={"glossary_check": "disabled"},
            config={},
        )

        pipeline = create_standard_pipeline(tmp_path)
        result = pipeline.process(ctx)

        assert len(result.extracted_terms) == 0
        assert len(result.conflicts) == 0
        assert result.effective_strictness is None

    def test_disabled_via_mission_config_skips_extraction(self, tmp_path):
        """glossary.enabled: false in config -> no extraction, no conflicts."""
        _setup_multi_scope_repo(tmp_path)

        ctx = PrimitiveExecutionContext(
            step_id="plan-002",
            mission_id="software-dev",
            run_id="run-int-008",
            inputs={
                "description": "workspace pipeline artifact mission primitive",
            },
            metadata={},
            config={"glossary": {"enabled": False}},
        )

        pipeline = create_standard_pipeline(tmp_path)
        result = pipeline.process(ctx)

        assert len(result.extracted_terms) == 0
        assert len(result.conflicts) == 0
        assert result.effective_strictness is None

    def test_disabled_via_boolean_false_skips(self, tmp_path):
        """glossary_check: false (YAML boolean) -> skip."""
        _setup_multi_scope_repo(tmp_path)

        ctx = PrimitiveExecutionContext(
            step_id="plan-003",
            mission_id="software-dev",
            run_id="run-int-009",
            inputs={"description": "workspace test"},
            metadata={"glossary_check": False},
            config={},
        )

        pipeline = create_standard_pipeline(tmp_path)
        result = pipeline.process(ctx)

        assert len(result.extracted_terms) == 0
        assert len(result.conflicts) == 0


# ---------------------------------------------------------------------------
# Scenario 4: Strictness mode combinations
# ---------------------------------------------------------------------------


class TestStrictnessModes:
    """Verify OFF/MEDIUM/MAX strictness modes with various conflict scenarios."""

    def _setup_ambiguous_workspace(self, tmp_path):
        _create_seed_file(
            tmp_path,
            "team_domain",
            (
                "terms:\n"
                "  - surface: workspace\n"
                "    definition: Git worktree directory for a work package\n"
                "    confidence: 0.9\n"
                "    status: active\n"
                "  - surface: workspace\n"
                "    definition: VS Code workspace configuration file\n"
                "    confidence: 0.7\n"
                "    status: active\n"
            ),
        )

    def test_off_mode_never_blocks(self, tmp_path):
        """OFF mode: conflicts are detected but never trigger blocking."""
        self._setup_ambiguous_workspace(tmp_path)

        ctx = PrimitiveExecutionContext(
            step_id="strict-off-001",
            mission_id="test",
            run_id="run-strict-001",
            inputs={"description": "workspace test"},
            metadata={
                "glossary_watch_terms": ["workspace"],
                "critical_step": True,  # HIGH severity
            },
            config={},
        )

        pipeline = create_standard_pipeline(
            tmp_path,
            runtime_strictness=Strictness.OFF,
            interaction_mode="non-interactive",
        )

        result = pipeline.process(ctx)

        assert result.effective_strictness == Strictness.OFF
        # Conflicts are detected but not blocking
        workspace_conflicts = [c for c in result.conflicts if c.term.surface_text == "workspace"]
        assert len(workspace_conflicts) >= 1
        assert workspace_conflicts[0].conflict_type == ConflictType.AMBIGUOUS

    def test_medium_mode_blocks_high_severity_only(self, tmp_path):
        """MEDIUM mode: blocks on HIGH severity, allows LOW/MEDIUM through."""
        self._setup_ambiguous_workspace(tmp_path)

        # Critical step -> AMBIGUOUS -> HIGH severity -> SHOULD BLOCK
        ctx_critical = PrimitiveExecutionContext(
            step_id="strict-med-001",
            mission_id="test",
            run_id="run-strict-002",
            inputs={"description": "workspace test"},
            metadata={
                "glossary_watch_terms": ["workspace"],
                "critical_step": True,
            },
            config={},
        )

        pipeline_critical = create_standard_pipeline(
            tmp_path,
            runtime_strictness=Strictness.MEDIUM,
            interaction_mode="non-interactive",
        )

        with pytest.raises(BlockedByConflict):
            pipeline_critical.process(ctx_critical)

        # Non-critical step -> AMBIGUOUS -> MEDIUM severity -> should NOT block
        ctx_noncritical = PrimitiveExecutionContext(
            step_id="strict-med-002",
            mission_id="test",
            run_id="run-strict-003",
            inputs={"description": "workspace test"},
            metadata={
                "glossary_watch_terms": ["workspace"],
                # No critical_step -> AMBIGUOUS -> MEDIUM severity
            },
            config={},
        )

        pipeline_noncritical = create_standard_pipeline(
            tmp_path,
            runtime_strictness=Strictness.MEDIUM,
            interaction_mode="non-interactive",
        )

        # MEDIUM severity under MEDIUM strictness -> no block
        result = pipeline_noncritical.process(ctx_noncritical)
        assert result.effective_strictness == Strictness.MEDIUM

    def test_max_mode_blocks_any_conflict(self, tmp_path):
        """MAX mode: blocks on any conflict regardless of severity."""
        self._setup_ambiguous_workspace(tmp_path)

        # Non-critical step -> AMBIGUOUS -> MEDIUM severity
        ctx = PrimitiveExecutionContext(
            step_id="strict-max-001",
            mission_id="test",
            run_id="run-strict-004",
            inputs={"description": "workspace test"},
            metadata={
                "glossary_watch_terms": ["workspace"],
                # No critical_step -> AMBIGUOUS -> MEDIUM severity
            },
            config={},
        )

        pipeline = create_standard_pipeline(
            tmp_path,
            runtime_strictness=Strictness.MAX,
            interaction_mode="non-interactive",
        )

        # MAX blocks even MEDIUM severity
        with pytest.raises(BlockedByConflict):
            pipeline.process(ctx)

    def test_unknown_term_under_max_blocks(self, tmp_path):
        """MAX mode: an UNKNOWN term (not in any glossary) triggers blocking."""
        (tmp_path / ".kittify").mkdir()

        ctx = PrimitiveExecutionContext(
            step_id="strict-max-002",
            mission_id="test",
            run_id="run-strict-005",
            inputs={"description": "test"},
            metadata={
                "glossary_watch_terms": ["frobnicator"],
            },
            config={},
        )

        pipeline = create_standard_pipeline(
            tmp_path,
            runtime_strictness=Strictness.MAX,
            interaction_mode="non-interactive",
        )

        with pytest.raises(BlockedByConflict) as exc_info:
            pipeline.process(ctx)

        conflict_terms = {c.term.surface_text for c in exc_info.value.conflicts}
        assert "frobnicator" in conflict_terms

    def test_strictness_precedence_runtime_over_config(self, tmp_path):
        """Runtime --strictness override takes precedence over config.yaml."""
        self._setup_ambiguous_workspace(tmp_path)
        _create_config(tmp_path, "glossary:\n  strictness: max\n")

        ctx = PrimitiveExecutionContext(
            step_id="strict-prec-001",
            mission_id="test",
            run_id="run-strict-006",
            inputs={"description": "workspace test"},
            metadata={
                "glossary_watch_terms": ["workspace"],
            },
            config={},
        )

        # Config says MAX, but runtime override says OFF
        pipeline = create_standard_pipeline(
            tmp_path,
            runtime_strictness=Strictness.OFF,
            interaction_mode="non-interactive",
        )

        # OFF overrides MAX -> no block
        result = pipeline.process(ctx)
        assert result.effective_strictness == Strictness.OFF


# ---------------------------------------------------------------------------
# Scenario 5: Multiple conflicts in one step
# ---------------------------------------------------------------------------


class TestMultipleConflictsSingleStep:
    """Verify handling of multiple ambiguous terms detected in a single step."""

    def test_multiple_ambiguous_terms_all_reported(self, tmp_path):
        """Two ambiguous terms should both appear in BlockedByConflict."""
        _create_seed_file(
            tmp_path,
            "team_domain",
            (
                "terms:\n"
                "  - surface: workspace\n"
                "    definition: Git worktree directory for a work package\n"
                "    confidence: 0.9\n"
                "    status: active\n"
                "  - surface: workspace\n"
                "    definition: VS Code workspace configuration file\n"
                "    confidence: 0.7\n"
                "    status: active\n"
                "  - surface: mission\n"
                "    definition: Purpose-specific workflow\n"
                "    confidence: 0.9\n"
                "    status: active\n"
                "  - surface: mission\n"
                "    definition: Organizational goal statement\n"
                "    confidence: 0.6\n"
                "    status: active\n"
            ),
        )

        ctx = PrimitiveExecutionContext(
            step_id="multi-001",
            mission_id="test-multi",
            run_id="run-multi-001",
            inputs={"description": "test"},
            metadata={
                "glossary_watch_terms": ["workspace", "mission"],
                "critical_step": True,
            },
            config={},
        )

        pipeline = create_standard_pipeline(
            tmp_path,
            runtime_strictness=Strictness.MAX,
            interaction_mode="non-interactive",
        )

        with pytest.raises(BlockedByConflict) as exc_info:
            pipeline.process(ctx)

        conflict_terms = {c.term.surface_text for c in exc_info.value.conflicts}
        assert "workspace" in conflict_terms
        assert "mission" in conflict_terms

    def test_resolve_all_multiple_conflicts_interactively(self, tmp_path, monkeypatch):
        """User resolves all conflicts interactively. Pipeline completes."""
        _create_seed_file(
            tmp_path,
            "team_domain",
            (
                "terms:\n"
                "  - surface: workspace\n"
                "    definition: Git worktree directory for a work package\n"
                "    confidence: 0.9\n"
                "    status: active\n"
                "  - surface: workspace\n"
                "    definition: VS Code workspace configuration file\n"
                "    confidence: 0.7\n"
                "    status: active\n"
                "  - surface: mission\n"
                "    definition: Purpose-specific workflow\n"
                "    confidence: 0.9\n"
                "    status: active\n"
                "  - surface: mission\n"
                "    definition: Organizational goal statement\n"
                "    confidence: 0.6\n"
                "    status: active\n"
            ),
        )

        prompt_count = 0

        def mock_prompt(conflict, candidates):
            nonlocal prompt_count
            prompt_count += 1
            conflict.selected_index = 0
            return ("select", None)

        monkeypatch.setattr(
            "glossary.pipeline.prompt_conflict_resolution_safe",
            mock_prompt,
        )

        ctx = PrimitiveExecutionContext(
            step_id="multi-002",
            mission_id="test-multi",
            run_id="run-multi-002",
            inputs={"description": "test"},
            metadata={
                "glossary_watch_terms": ["workspace", "mission"],
            },
            config={},
        )

        pipeline = create_standard_pipeline(
            tmp_path,
            runtime_strictness=Strictness.MAX,
            interaction_mode="interactive",
        )

        result = pipeline.process(ctx)

        # Both conflicts resolved
        assert len(result.conflicts) == 0
        assert prompt_count == 2  # One prompt per ambiguous term

        resolved = getattr(result, "resolved_conflicts", [])
        resolved_surfaces = {c.term.surface_text for c in resolved}
        assert "workspace" in resolved_surfaces
        assert "mission" in resolved_surfaces

    def test_partial_resolution_some_deferred(self, tmp_path, monkeypatch):
        """User resolves one conflict but defers another.
        Under MAX strictness, the deferred conflict causes blocking."""
        _create_seed_file(
            tmp_path,
            "team_domain",
            (
                "terms:\n"
                "  - surface: workspace\n"
                "    definition: Git worktree directory for a work package\n"
                "    confidence: 0.9\n"
                "    status: active\n"
                "  - surface: workspace\n"
                "    definition: VS Code workspace configuration file\n"
                "    confidence: 0.7\n"
                "    status: active\n"
                "  - surface: mission\n"
                "    definition: Purpose-specific workflow\n"
                "    confidence: 0.9\n"
                "    status: active\n"
                "  - surface: mission\n"
                "    definition: Organizational goal statement\n"
                "    confidence: 0.6\n"
                "    status: active\n"
            ),
        )

        call_count = 0

        def mock_prompt(conflict, candidates):
            nonlocal call_count
            call_count += 1
            if conflict.term.surface_text == "workspace":
                conflict.selected_index = 0
                return ("select", None)
            else:
                return ("defer", None)

        monkeypatch.setattr(
            "glossary.pipeline.prompt_conflict_resolution_safe",
            mock_prompt,
        )

        ctx = PrimitiveExecutionContext(
            step_id="multi-003",
            mission_id="test-multi",
            run_id="run-multi-003",
            inputs={"description": "test"},
            metadata={
                "glossary_watch_terms": ["workspace", "mission"],
            },
            config={},
        )

        pipeline = create_standard_pipeline(
            tmp_path,
            runtime_strictness=Strictness.MAX,
            interaction_mode="interactive",
        )

        # workspace resolved, mission deferred -> MAX blocks on remaining
        with pytest.raises(BlockedByConflict) as exc_info:
            pipeline.process(ctx)

        # Only the deferred "mission" conflict should be in the exception
        remaining_terms = {c.term.surface_text for c in exc_info.value.conflicts}
        assert "mission" in remaining_terms
        # workspace was resolved, should not be in remaining
        assert "workspace" not in remaining_terms


# ---------------------------------------------------------------------------
# Scenario 6: Scope hierarchy resolution
# ---------------------------------------------------------------------------


class TestScopeHierarchyIntegration:
    """Test that multi-scope resolution works end-to-end through the pipeline."""

    def test_term_resolved_from_single_scope_no_conflict(self, tmp_path):
        """A term with 1 active sense in one scope -> no conflict."""
        _create_seed_file(
            tmp_path,
            "team_domain",
            (
                "terms:\n"
                "  - surface: artifact\n"
                "    definition: Build output file\n"
                "    confidence: 1.0\n"
                "    status: active\n"
            ),
        )

        ctx = PrimitiveExecutionContext(
            step_id="scope-001",
            mission_id="test",
            run_id="run-scope-001",
            inputs={"description": "test"},
            metadata={"glossary_watch_terms": ["artifact"]},
            config={},
        )

        pipeline = create_standard_pipeline(tmp_path)
        result = pipeline.process(ctx)

        assert len(result.conflicts) == 0
        assert len(result.extracted_terms) >= 1

    def test_term_in_no_scope_is_unknown(self, tmp_path):
        """A metadata-hinted term not found in any scope -> UNKNOWN conflict."""
        (tmp_path / ".kittify").mkdir()

        ctx = PrimitiveExecutionContext(
            step_id="scope-002",
            mission_id="test",
            run_id="run-scope-002",
            inputs={"description": "test"},
            metadata={"glossary_watch_terms": ["xylophone"]},
            config={},
        )

        pipeline = create_standard_pipeline(
            tmp_path,
            runtime_strictness=Strictness.OFF,
        )
        result = pipeline.process(ctx)

        unknown_conflicts = [c for c in result.conflicts if c.term.surface_text == "xylophone"]
        assert len(unknown_conflicts) == 1
        assert unknown_conflicts[0].conflict_type == ConflictType.UNKNOWN

    def test_cross_scope_terms_resolved_independently(self, tmp_path):
        """Terms from different scopes are each resolved independently."""
        _setup_multi_scope_repo(tmp_path)

        ctx = PrimitiveExecutionContext(
            step_id="scope-003",
            mission_id="test",
            run_id="run-scope-003",
            inputs={"description": "test"},
            metadata={
                # "pipeline" is in team_domain (unambiguous)
                # "mission" is in spec_kitty_core (unambiguous)
                "glossary_watch_terms": ["pipeline", "mission"],
            },
            config={},
        )

        pipeline = create_standard_pipeline(tmp_path)
        result = pipeline.process(ctx)

        # Both are unambiguous single-sense terms -> no conflicts
        assert len(result.conflicts) == 0
        # Both were extracted
        extracted_surfaces = {t.surface for t in result.extracted_terms}
        assert "pipeline" in extracted_surfaces
        assert "mission" in extracted_surfaces


# ---------------------------------------------------------------------------
# Scenario 7: Event emission through the full stack
# ---------------------------------------------------------------------------


class TestEventEmissionEndToEnd:
    """Verify that events are emitted at each pipeline stage.

    Since spec-kitty-events may not be installed, events go through log-only
    mode. We verify the event builder functions return correct payloads.
    """

    def test_extraction_emits_term_candidate_events(self, tmp_path):
        """Term extraction stage should emit TermCandidateObserved events."""
        (tmp_path / ".kittify").mkdir()

        from glossary.events import emit_term_candidate_observed
        from glossary.extraction import ExtractedTerm

        term = ExtractedTerm(
            surface="workspace",
            source="metadata_hint",
            confidence=1.0,
            original="workspace",
        )

        ctx = PrimitiveExecutionContext(
            step_id="evt-001",
            mission_id="test",
            run_id="run-evt-001",
            inputs={"description": "test"},
            metadata={},
            config={},
        )

        event = emit_term_candidate_observed(term=term, context=ctx, repo_root=tmp_path)

        assert event is not None
        assert event["event_type"] == "TermCandidateObserved"
        assert event["term"] == "workspace"
        assert event["confidence"] == 1.0
        assert event["extraction_method"] == "metadata_hint"

    def test_semantic_check_emits_evaluation_event(self, tmp_path):
        """Semantic check stage should emit SemanticCheckEvaluated event."""
        from glossary.events import emit_semantic_check_evaluated
        from glossary.models import (
            ConflictType,
            SemanticConflict,
            SenseRef,
            TermSurface,
        )

        ctx = PrimitiveExecutionContext(
            step_id="evt-002",
            mission_id="test",
            run_id="run-evt-002",
            inputs={"description": "test"},
            metadata={},
            config={},
        )

        conflict = SemanticConflict(
            term=TermSurface("workspace"),
            conflict_type=ConflictType.AMBIGUOUS,
            severity=Severity.HIGH,
            confidence=0.9,
            candidate_senses=[
                SenseRef("workspace", "team_domain", "Git worktree", 0.9),
                SenseRef("workspace", "team_domain", "VS Code config", 0.7),
            ],
            context="test",
        )

        event = emit_semantic_check_evaluated(
            context=ctx,
            conflicts=[conflict],
            repo_root=tmp_path,
        )

        assert event is not None
        assert event["event_type"] == "SemanticCheckEvaluated"
        assert event["overall_severity"] == "high"
        assert len(event["findings"]) == 1

    def test_generation_blocked_emits_event(self, tmp_path):
        """Generation gate blocking should emit GenerationBlockedBySemanticConflict."""
        from glossary.events import emit_generation_blocked_event
        from glossary.models import (
            ConflictType,
            SemanticConflict,
            SenseRef,
            TermSurface,
        )

        conflict = SemanticConflict(
            term=TermSurface("workspace"),
            conflict_type=ConflictType.AMBIGUOUS,
            severity=Severity.HIGH,
            confidence=0.9,
            candidate_senses=[
                SenseRef("workspace", "team_domain", "Git worktree", 0.9),
            ],
            context="test",
        )

        event = emit_generation_blocked_event(
            step_id="evt-003",
            mission_id="test",
            conflicts=[conflict],
            strictness_mode=Strictness.MEDIUM,
            run_id="run-evt-003",
            repo_root=tmp_path,
        )

        assert event is not None
        assert event["event_type"] == "GenerationBlockedBySemanticConflict"
        assert event["strictness_mode"] == "medium"
        assert len(event["conflicts"]) == 1

    def test_clarification_requested_emits_event(self, tmp_path):
        """Deferred conflict should emit GlossaryClarificationRequested."""
        from glossary.events import emit_clarification_requested
        from glossary.models import (
            ConflictType,
            SemanticConflict,
            SenseRef,
            TermSurface,
        )

        ctx = PrimitiveExecutionContext(
            step_id="evt-004",
            mission_id="test",
            run_id="run-evt-004",
            inputs={"description": "test"},
            metadata={},
            config={},
        )

        conflict = SemanticConflict(
            term=TermSurface("workspace"),
            conflict_type=ConflictType.AMBIGUOUS,
            severity=Severity.HIGH,
            confidence=0.9,
            candidate_senses=[
                SenseRef("workspace", "team_domain", "Git worktree", 0.9),
                SenseRef("workspace", "team_domain", "VS Code config", 0.7),
            ],
            context="test",
        )

        event = emit_clarification_requested(
            conflict=conflict,
            context=ctx,
            conflict_id="test-conflict-id",
            repo_root=tmp_path,
        )

        assert event is not None
        assert event["event_type"] == "GlossaryClarificationRequested"
        assert event["term"] == "workspace"
        assert len(event["options"]) == 2

    def test_clarification_resolved_emits_event(self, tmp_path):
        """Resolved conflict should emit GlossaryClarificationResolved."""
        from glossary.events import emit_clarification_resolved
        from glossary.models import (
            ConflictType,
            SemanticConflict,
            SenseRef,
            TermSurface,
        )

        ctx = PrimitiveExecutionContext(
            step_id="evt-005",
            mission_id="test",
            run_id="run-evt-005",
            inputs={"description": "test"},
            metadata={},
            config={},
        )

        conflict = SemanticConflict(
            term=TermSurface("workspace"),
            conflict_type=ConflictType.AMBIGUOUS,
            severity=Severity.HIGH,
            confidence=0.9,
            candidate_senses=[
                SenseRef("workspace", "team_domain", "Git worktree", 0.9),
            ],
            context="test",
        )

        selected_sense = SenseRef("workspace", "team_domain", "Git worktree", 0.9)

        event = emit_clarification_resolved(
            conflict_id="test-conflict-resolved",
            conflict=conflict,
            selected_sense=selected_sense,
            context=ctx,
            resolution_mode="interactive",
            repo_root=tmp_path,
        )

        assert event is not None
        assert event["event_type"] == "GlossaryClarificationResolved"
        assert event["conflict_id"] == "test-conflict-resolved"
        assert event["resolution_mode"] == "interactive"
        assert event["selected_sense"]["definition"] == "Git worktree"


# ---------------------------------------------------------------------------
# Scenario 8: Production code path (execute_with_glossary)
# ---------------------------------------------------------------------------


class TestProductionCodePath:
    """Verify full integration through the production execute_with_glossary hook."""

    def test_full_e2e_production_specify_clarify_proceed(self, tmp_path, monkeypatch):
        """Full production path: hook -> pipeline -> clarify -> primitive."""
        from specify_cli.missions import execute_with_glossary

        _setup_multi_scope_repo(tmp_path)

        def mock_prompt(conflict, candidates):
            conflict.selected_index = 0
            return ("select", None)

        monkeypatch.setattr(
            "glossary.pipeline.prompt_conflict_resolution_safe",
            mock_prompt,
        )

        primitive_results = []

        def my_specify_primitive(context):
            primitive_results.append(
                {
                    "strictness": context.effective_strictness,
                    "remaining_conflicts": len(context.conflicts),
                    "terms_extracted": len(context.extracted_terms),
                }
            )
            return primitive_results[-1]

        ctx = PrimitiveExecutionContext(
            step_id="prod-001",
            mission_id="software-dev",
            run_id="run-prod-001",
            inputs={
                "description": "Implement workspace management feature",
            },
            metadata={
                "glossary_check": "enabled",
                "glossary_watch_terms": ["workspace"],
                "critical_step": True,
            },
            config={},
        )

        result = execute_with_glossary(
            primitive_fn=my_specify_primitive,
            context=ctx,
            repo_root=tmp_path,
            runtime_strictness=Strictness.MEDIUM,
            interaction_mode="interactive",
        )

        # Primitive executed
        assert len(primitive_results) == 1
        # Conflict was resolved by clarification
        assert result["remaining_conflicts"] == 0
        assert result["strictness"] == Strictness.MEDIUM
        assert result["terms_extracted"] >= 1

    def test_production_path_disabled_skips_pipeline_runs_primitive(self, tmp_path):
        """When glossary is disabled, the primitive still runs."""
        from specify_cli.missions import execute_with_glossary


        _setup_multi_scope_repo(tmp_path)

        def my_primitive(context):
            return {"ran": True, "strictness": context.effective_strictness}

        ctx = PrimitiveExecutionContext(
            step_id="prod-002",
            mission_id="software-dev",
            run_id="run-prod-002",
            inputs={"description": "workspace test"},
            metadata={"glossary_check": "disabled"},
            config={},
        )

        result = execute_with_glossary(
            primitive_fn=my_primitive,
            context=ctx,
            repo_root=tmp_path,
        )

        assert result["ran"] is True
        assert result["strictness"] is None  # Pipeline was skipped


# ---------------------------------------------------------------------------
# Scenario 9: Error handling and edge cases
# ---------------------------------------------------------------------------


class TestErrorHandlingEdgeCases:
    """Test error paths and edge cases in cross-module workflows."""

    def test_malformed_seed_file_does_not_crash_pipeline(self, tmp_path):
        """Pipeline handles malformed seed files gracefully."""
        glossaries = tmp_path / ".kittify" / "glossaries"
        glossaries.mkdir(parents=True)
        (glossaries / "team_domain.yaml").write_text("{{{{invalid yaml content")

        ctx = PrimitiveExecutionContext(
            step_id="edge-001",
            mission_id="test",
            run_id="run-edge-001",
            inputs={"description": "workspace test"},
            metadata={"glossary_watch_terms": ["workspace"]},
            config={},
        )

        pipeline = create_standard_pipeline(tmp_path, runtime_strictness=Strictness.OFF)

        # Should not crash
        result = pipeline.process(ctx)
        assert result is not None

    def test_empty_seed_file_handled(self, tmp_path):
        """Pipeline handles empty seed file gracefully."""
        glossaries = tmp_path / ".kittify" / "glossaries"
        glossaries.mkdir(parents=True)
        (glossaries / "team_domain.yaml").write_text("")

        ctx = PrimitiveExecutionContext(
            step_id="edge-002",
            mission_id="test",
            run_id="run-edge-002",
            inputs={"description": "test"},
            metadata={},
            config={},
        )

        pipeline = create_standard_pipeline(tmp_path, runtime_strictness=Strictness.OFF)

        result = pipeline.process(ctx)
        assert result is not None

    def test_no_kittify_directory_handled(self, tmp_path):
        """Pipeline creates .kittify if needed and handles missing glossaries."""
        # tmp_path has no .kittify directory
        ctx = PrimitiveExecutionContext(
            step_id="edge-003",
            mission_id="test",
            run_id="run-edge-003",
            inputs={"description": "test"},
            metadata={},
            config={},
        )

        pipeline = create_standard_pipeline(tmp_path, runtime_strictness=Strictness.OFF)

        result = pipeline.process(ctx)
        assert result is not None

    def test_prompt_function_failure_defers_conflict(self, tmp_path, monkeypatch):
        """If the prompt function raises an exception, the conflict is deferred
        (not lost), and the pipeline continues to the gate."""
        _create_seed_file(
            tmp_path,
            "team_domain",
            (
                "terms:\n"
                "  - surface: workspace\n"
                "    definition: Git worktree directory for a work package\n"
                "    confidence: 0.9\n"
                "    status: active\n"
                "  - surface: workspace\n"
                "    definition: VS Code workspace configuration file\n"
                "    confidence: 0.7\n"
                "    status: active\n"
            ),
        )

        def broken_prompt(conflict, candidates):
            raise RuntimeError("Simulated prompt failure")

        monkeypatch.setattr(
            "glossary.pipeline.prompt_conflict_resolution_safe",
            broken_prompt,
        )

        ctx = PrimitiveExecutionContext(
            step_id="edge-004",
            mission_id="test",
            run_id="run-edge-004",
            inputs={"description": "workspace test"},
            metadata={
                "glossary_watch_terms": ["workspace"],
            },
            config={},
        )

        pipeline = create_standard_pipeline(
            tmp_path,
            runtime_strictness=Strictness.MAX,
            interaction_mode="interactive",
        )

        # Prompt fails -> conflict deferred -> MAX blocks
        with pytest.raises(BlockedByConflict):
            pipeline.process(ctx)

# ---------------------------------------------------------------------------
# Performance validation
# ---------------------------------------------------------------------------


#: Warm-up pipeline runs discarded before timing: the first run(s) pay one-time
#: cache / pack resolution that is runner-bound, not the per-run cost this guards.
_PERF_WARMUP_RUNS = 2
#: Timed warm runs taken after the warm-up.
_PERF_SAMPLE_RUNS = 10
#: Samples at each edge whose median forms the head / tail figure (absorbs one spike).
_PERF_EDGE_WINDOW = 3
#: PROVISIONAL (ADR 2026-10-05-2 posture): a warm run's tail median must stay within
#: this multiple of its head median. The clean ratio is ~1.0 locally (0.96 to 1.04
#: over five runs, max/min <= 1.18); 3.0 leaves wide room for shared-runner noise
#: while still catching a per-run accumulation that doubles the cost across the run.
#: The ratio is recorded as an xunit property for nightly confirmation of the CI
#: magnitude. Within-process, not a CLI spawn, so test_perf_limit_authority does not
#: bind it (cf. tests/consolidation/test_canceled_content_benchmark.py's _BUDGET_SECONDS).
_PERF_ACCUMULATION_RATIO_LIMIT = 3.0


class TestIntegrationPerformance:
    """Verify integration test workflows complete within performance budget."""

    @pytest.mark.performance
    def test_full_pipeline_under_200ms(self, tmp_path):
        """Full pipeline execution (no conflict) completes in < 200ms."""
        _setup_multi_scope_repo(tmp_path)

        ctx = PrimitiveExecutionContext(
            step_id="perf-001",
            mission_id="test",
            run_id="run-perf-001",
            inputs={"description": "Simple test with no special terms"},
            metadata={},
            config={},
        )

        pipeline = create_standard_pipeline(tmp_path)

        start = time.perf_counter()
        pipeline.process(ctx)
        elapsed = time.perf_counter() - start

        assert elapsed < 0.2, f"Pipeline too slow: {elapsed:.3f}s (expected < 0.2s)"

    @pytest.mark.performance
    def test_repeated_conflict_resolution_has_no_runaway_accumulation(self, tmp_path, monkeypatch, record_property):
        """Repeated conflict-resolution runs stay flat -- a warm run's tail is not
        pathologically slower than its head (#5419).

        Replaces the former ``test_ten_iterations_under_five_seconds``, which
        summed 10 cold iterations against an absolute 5.0 s wall-clock budget.
        That budget measured the shared runner (cold filesystem / pack
        resolution), not the code: it flaked at 5.23 s with no product change
        while the same loop costs ~0.003 s locally. A warm *within-run ratio*
        cancels machine speed -- the head and tail medians are sampled in the
        same run on the same runner -- so it catches the real regression class
        (per-run accumulation: caches not reused, a growing event log re-read,
        pack re-resolution) without an absolute number of seconds.

        The ratio limit is PROVISIONAL (ADR 2026-10-05-2 posture): the clean
        ratio is ~1.0 locally; the head/tail medians and the ratio are recorded
        as xunit properties so a nightly can confirm the CI magnitude.
        """
        _setup_multi_scope_repo(tmp_path)

        def mock_prompt(conflict, candidates):
            conflict.selected_index = 0
            return ("select", None)

        monkeypatch.setattr(
            "glossary.pipeline.prompt_conflict_resolution_safe",
            mock_prompt,
        )

        def _run_once(index: int) -> float:
            start = time.perf_counter()
            ctx = PrimitiveExecutionContext(
                step_id=f"perf-{index:03d}",
                mission_id="perf-test",
                run_id=f"run-perf-{index:03d}",
                inputs={"description": "Implement workspace and artifact handling"},
                metadata={"glossary_watch_terms": ["workspace"]},
                config={},
            )
            pipeline = create_standard_pipeline(
                tmp_path,
                runtime_strictness=Strictness.MAX,
                interaction_mode="interactive",
            )
            pipeline.process(ctx)
            return time.perf_counter() - start

        # Discard the cold run(s): one-time cache / pack resolution is runner-bound
        # and not the per-run cost this test guards.
        for index in range(_PERF_WARMUP_RUNS):
            _run_once(index)

        samples = [_run_once(_PERF_WARMUP_RUNS + index) for index in range(_PERF_SAMPLE_RUNS)]

        # Medians of the first and last few samples absorb a single scheduler/GC
        # spike; a systematic accumulation pushes the tail above the head.
        head = statistics.median(samples[:_PERF_EDGE_WINDOW])
        tail = statistics.median(samples[-_PERF_EDGE_WINDOW:])
        ratio = tail / head if head > 0 else float("inf")

        record_property("perf_head_median_s", round(head, 6))
        record_property("perf_tail_median_s", round(tail, 6))
        record_property("perf_accumulation_ratio", round(ratio, 4))
        record_property("perf_samples_s", [round(value, 6) for value in samples])

        # The tail median must stay within RATIO_LIMIT x the head median; runner
        # speed cancels because both are sampled in this same run.
        assert_timing_budget(
            tail,
            _PERF_ACCUMULATION_RATIO_LIMIT * head,
            name=f"warm tail median vs {_PERF_ACCUMULATION_RATIO_LIMIT}x head median (s); ratio={ratio:.3f}",
        )

    @pytest.mark.performance
    def test_hundred_watch_terms_under_200ms(self, tmp_path):
        """Pipeline with 100 metadata watch terms completes in < 200ms."""
        (tmp_path / ".kittify").mkdir()

        terms = [f"term{i}" for i in range(100)]
        ctx = PrimitiveExecutionContext(
            step_id="perf-100",
            mission_id="perf-test",
            run_id="run-perf-100",
            inputs={"description": "test"},
            metadata={"glossary_watch_terms": terms},
            config={},
        )

        pipeline = create_standard_pipeline(tmp_path, runtime_strictness=Strictness.OFF)

        start = time.perf_counter()
        pipeline.process(ctx)
        elapsed = time.perf_counter() - start

        assert elapsed < 0.2, f"Pipeline too slow with 100 terms: {elapsed:.3f}s"
