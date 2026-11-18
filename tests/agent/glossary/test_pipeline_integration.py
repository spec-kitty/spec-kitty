"""Full pipeline integration tests (T043).

These tests verify the end-to-end glossary middleware pipeline flow:
term extraction -> semantic check -> generation gate -> clarification -> resume.
"""


import pytest

from glossary.exceptions import BlockedByConflict
from glossary.models import (
    ConflictType,
    Severity,
)
from glossary.pipeline import (
    create_standard_pipeline,
)
from glossary.strictness import Strictness
from specify_cli.missions import PrimitiveExecutionContext
from tests._perf_helpers import median_in_process_seconds

pytestmark = pytest.mark.fast

def _make_context(**overrides):
    """Helper to create a PrimitiveExecutionContext with defaults."""
    defaults = {
        "step_id": "test-001",
        "mission_id": "test-mission",
        "run_id": "run-001",
        "inputs": {"description": "Simple test with no technical terms"},
        "metadata": {},
        "config": {},
    }
    defaults.update(overrides)
    return PrimitiveExecutionContext(**defaults)


def _create_seed_file(tmp_path, scope_name, terms_yaml):
    """Create a seed file in .kittify/glossaries/."""
    glossaries = tmp_path / ".kittify" / "glossaries"
    glossaries.mkdir(parents=True, exist_ok=True)
    seed_file = glossaries / f"{scope_name}.yaml"
    seed_file.write_text(terms_yaml)
    return seed_file


# ---------------------------------------------------------------------------
# Happy path: no conflicts
# ---------------------------------------------------------------------------


class TestPipelineNoConflicts:
    """Verify pipeline executes successfully when no conflicts are detected."""

    def test_pipeline_no_conflicts_simple_text(self, tmp_path):
        (tmp_path / ".kittify").mkdir()

        ctx = _make_context(
            inputs={"description": "Simple test with no technical terms"},
        )

        pipeline = create_standard_pipeline(tmp_path)
        result = pipeline.process(ctx)

        # No terms extracted (simple text, no quoted phrases / acronyms)
        assert result.conflicts == []
        # Strictness resolved to default (MEDIUM)
        assert result.effective_strictness == Strictness.MEDIUM

    def test_pipeline_no_conflicts_with_known_term(self, tmp_path):
        """A term that resolves to exactly one active sense is not a conflict."""
        _create_seed_file(
            tmp_path,
            "team_domain",
            (
                "terms:\n"
                "  - surface: workspace\n"
                "    definition: Git worktree directory\n"
                "    confidence: 1.0\n"
                "    status: active\n"
            ),
        )

        ctx = _make_context(
            inputs={"description": "test"},
            metadata={
                "glossary_watch_terms": ["workspace"],
            },
        )

        pipeline = create_standard_pipeline(tmp_path)
        result = pipeline.process(ctx)

        # Term extracted, but single-sense match = no conflict
        assert len(result.extracted_terms) >= 1
        assert result.conflicts == []


# ---------------------------------------------------------------------------
# Conflict detection: ambiguous term with two active senses
# ---------------------------------------------------------------------------


class TestPipelineConflictDetection:
    """Verify the pipeline detects semantic conflicts."""

    def _setup_ambiguous_workspace(self, tmp_path):
        """Create a seed file with two active senses for 'workspace'."""
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

    def test_ambiguous_term_creates_conflict(self, tmp_path):
        """When a term has 2+ active senses, an AMBIGUOUS conflict is detected."""
        self._setup_ambiguous_workspace(tmp_path)

        ctx = _make_context(
            inputs={"description": "The workspace contains implementation files"},
            metadata={"glossary_watch_terms": ["workspace"]},
        )

        pipeline = create_standard_pipeline(
            tmp_path,
            runtime_strictness=Strictness.OFF,  # Don't block
        )
        result = pipeline.process(ctx)

        # With strictness=OFF, pipeline completes (no blocking)
        # but conflicts are still detected
        workspace_conflicts = [c for c in result.conflicts if c.term.surface_text == "workspace"]
        assert len(workspace_conflicts) >= 1
        assert workspace_conflicts[0].conflict_type == ConflictType.AMBIGUOUS

    def test_ambiguous_term_blocked_with_medium_strictness(self, tmp_path):
        """AMBIGUOUS conflicts cause blocking under MEDIUM strictness
        only when they are HIGH severity (critical step)."""
        self._setup_ambiguous_workspace(tmp_path)

        ctx = _make_context(
            inputs={"description": "The workspace contains implementation files"},
            metadata={
                "glossary_watch_terms": ["workspace"],
                "critical_step": True,  # Makes AMBIGUOUS -> HIGH severity
            },
        )

        pipeline = create_standard_pipeline(
            tmp_path,
            runtime_strictness=Strictness.MEDIUM,
        )

        with pytest.raises(BlockedByConflict) as exc_info:
            pipeline.process(ctx)

        assert len(exc_info.value.conflicts) >= 1

    def test_ambiguous_term_blocked_with_max_strictness(self, tmp_path):
        """MAX strictness blocks on any conflict regardless of severity."""
        self._setup_ambiguous_workspace(tmp_path)

        ctx = _make_context(
            inputs={"description": "The workspace contains implementation files"},
            metadata={"glossary_watch_terms": ["workspace"]},
        )

        pipeline = create_standard_pipeline(
            tmp_path,
            runtime_strictness=Strictness.MAX,
        )

        with pytest.raises(BlockedByConflict):
            pipeline.process(ctx)

    def test_ambiguous_term_not_blocked_with_off_strictness(self, tmp_path):
        """OFF strictness never blocks."""
        self._setup_ambiguous_workspace(tmp_path)

        ctx = _make_context(
            inputs={"description": "The workspace contains implementation files"},
            metadata={"glossary_watch_terms": ["workspace"]},
        )

        pipeline = create_standard_pipeline(
            tmp_path,
            runtime_strictness=Strictness.OFF,
        )

        # Should not raise
        result = pipeline.process(ctx)
        assert result.effective_strictness == Strictness.OFF

    def test_multiple_conflicts_all_reported(self, tmp_path):
        """Multiple ambiguous terms should all appear in BlockedByConflict."""
        _create_seed_file(
            tmp_path,
            "team_domain",
            (
                "terms:\n"
                "  - surface: workspace\n"
                "    definition: Git worktree directory\n"
                "    confidence: 0.9\n"
                "    status: active\n"
                "  - surface: workspace\n"
                "    definition: VS Code workspace config\n"
                "    confidence: 0.7\n"
                "    status: active\n"
                "  - surface: mission\n"
                "    definition: Purpose-specific workflow\n"
                "    confidence: 0.9\n"
                "    status: active\n"
                "  - surface: mission\n"
                "    definition: Organization goal\n"
                "    confidence: 0.6\n"
                "    status: active\n"
            ),
        )

        ctx = _make_context(
            inputs={"description": "test"},
            metadata={
                "glossary_watch_terms": ["workspace", "mission"],
                "critical_step": True,
            },
        )

        pipeline = create_standard_pipeline(
            tmp_path,
            runtime_strictness=Strictness.MAX,
        )

        with pytest.raises(BlockedByConflict) as exc_info:
            pipeline.process(ctx)

        # Both workspace and mission should be in conflicts
        conflict_terms = {c.term.surface_text for c in exc_info.value.conflicts}
        assert "workspace" in conflict_terms
        assert "mission" in conflict_terms


# ---------------------------------------------------------------------------
# Clarification flow
# ---------------------------------------------------------------------------


class TestPipelineClarification:
    """Test clarification middleware integration in the pipeline."""

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

    def test_clarification_defers_in_non_interactive_mode(self, tmp_path):
        """In non-interactive mode with OFF strictness, conflicts pass through
        the gate and are deferred by clarification middleware."""
        self._setup_ambiguous_workspace(tmp_path)

        ctx = _make_context(
            inputs={"description": "The workspace"},
            metadata={"glossary_watch_terms": ["workspace"]},
        )

        pipeline = create_standard_pipeline(
            tmp_path,
            runtime_strictness=Strictness.OFF,
            interaction_mode="non-interactive",
        )

        result = pipeline.process(ctx)

        # Conflicts are detected but not resolved (deferred)
        # The clarification middleware removes resolved conflicts from
        # context.conflicts. Since no prompt_fn, all are deferred.
        # They remain in context.conflicts.
        assert len(result.conflicts) >= 1


# ---------------------------------------------------------------------------
# Strictness precedence
# ---------------------------------------------------------------------------


class TestPipelineStrictnessPrecedence:
    """Test strictness resolution precedence: runtime > step > mission > global."""

    def test_runtime_override_wins_over_all(self, tmp_path):
        (tmp_path / ".kittify").mkdir()

        ctx = _make_context(
            metadata={"glossary_check_strictness": "medium"},
            config={"glossary": {"strictness": "max"}},
        )

        pipeline = create_standard_pipeline(
            tmp_path,
            runtime_strictness=Strictness.OFF,
        )

        result = pipeline.process(ctx)
        assert result.effective_strictness == Strictness.OFF

    def test_step_override_wins_over_mission(self, tmp_path):
        (tmp_path / ".kittify").mkdir()

        # Step says OFF, mission says MAX
        ctx = _make_context(
            metadata={"glossary_check_strictness": "off"},
            config={"glossary": {"strictness": "max"}},
        )

        pipeline = create_standard_pipeline(tmp_path)
        result = pipeline.process(ctx)
        assert result.effective_strictness == Strictness.OFF

    def test_mission_override_used_when_no_step_or_runtime(self, tmp_path):
        # Write config.yaml with glossary.strictness = max
        kittify = tmp_path / ".kittify"
        kittify.mkdir()
        config_yaml = kittify / "config.yaml"
        config_yaml.write_text("glossary:\n  strictness: max\n")

        ctx = _make_context(
            config={"glossary": {"strictness": "max"}},
        )

        pipeline = create_standard_pipeline(tmp_path)
        result = pipeline.process(ctx)
        # mission_strictness comes from context.config; effective resolution
        # uses the 4-tier chain. With global=max, effective=max.
        assert result.effective_strictness == Strictness.MAX

    def test_global_default_when_nothing_overrides(self, tmp_path):
        (tmp_path / ".kittify").mkdir()

        ctx = _make_context()
        pipeline = create_standard_pipeline(tmp_path)
        result = pipeline.process(ctx)

        # Default global = MEDIUM
        assert result.effective_strictness == Strictness.MEDIUM


# ---------------------------------------------------------------------------
# Pipeline disabled
# ---------------------------------------------------------------------------


class TestPipelineDisabled:
    """Test that pipeline skips correctly when disabled."""

    def test_pipeline_skips_when_step_disabled(self, tmp_path):
        (tmp_path / ".kittify").mkdir()

        ctx = _make_context(
            inputs={"description": "test with workspace mission terms"},
            metadata={"glossary_check": "disabled"},
        )

        pipeline = create_standard_pipeline(tmp_path)
        result = pipeline.process(ctx)

        assert result.extracted_terms == []
        assert result.conflicts == []
        assert result.effective_strictness is None

    def test_pipeline_skips_when_step_disabled_bool_false(self, tmp_path):
        """Regression: YAML `glossary_check: false` (boolean) must skip."""
        (tmp_path / ".kittify").mkdir()

        ctx = _make_context(
            inputs={"description": "test with workspace mission terms"},
            metadata={"glossary_check": False},
        )

        pipeline = create_standard_pipeline(tmp_path)
        result = pipeline.process(ctx)

        assert result.extracted_terms == []
        assert result.conflicts == []
        assert result.effective_strictness is None

    def test_pipeline_skips_when_step_disabled_string_false(self, tmp_path):
        """Regression: string 'false' must skip."""
        (tmp_path / ".kittify").mkdir()

        ctx = _make_context(
            inputs={"description": "test with workspace mission terms"},
            metadata={"glossary_check": "false"},
        )

        pipeline = create_standard_pipeline(tmp_path)
        result = pipeline.process(ctx)

        assert result.extracted_terms == []
        assert result.conflicts == []
        assert result.effective_strictness is None

    def test_pipeline_skips_when_mission_disabled(self, tmp_path):
        (tmp_path / ".kittify").mkdir()

        ctx = _make_context(
            inputs={"description": "test with workspace mission terms"},
            config={"glossary": {"enabled": False}},
        )

        pipeline = create_standard_pipeline(tmp_path)
        result = pipeline.process(ctx)

        assert result.extracted_terms == []
        assert result.conflicts == []
        assert result.effective_strictness is None


# ---------------------------------------------------------------------------
# Unknown terms (UNKNOWN conflict type)
# ---------------------------------------------------------------------------


class TestPipelineUnknownTerms:
    """Test pipeline behavior with terms not found in any scope."""

    def test_unknown_term_detected_as_conflict(self, tmp_path):
        """A metadata-hinted term not in any glossary -> UNKNOWN conflict."""
        (tmp_path / ".kittify").mkdir()

        ctx = _make_context(
            inputs={"description": "test"},
            metadata={
                "glossary_watch_terms": ["frobulator"],
            },
        )

        pipeline = create_standard_pipeline(
            tmp_path,
            runtime_strictness=Strictness.OFF,
        )
        result = pipeline.process(ctx)

        # frobulator not in any seed file -> UNKNOWN
        unknown_conflicts = [c for c in result.conflicts if c.term.surface_text == "frobulator"]
        assert len(unknown_conflicts) == 1
        assert unknown_conflicts[0].conflict_type == ConflictType.UNKNOWN


# ---------------------------------------------------------------------------
# Seed file edge cases
# ---------------------------------------------------------------------------


class TestPipelineSeedFileEdgeCases:
    """Test pipeline behavior with various seed file states."""

    def test_no_seed_files(self, tmp_path):
        """Pipeline works when no seed files exist."""
        (tmp_path / ".kittify").mkdir()

        ctx = _make_context(
            inputs={"description": "test with workspace"},
            metadata={"glossary_watch_terms": ["workspace"]},
        )

        pipeline = create_standard_pipeline(
            tmp_path,
            runtime_strictness=Strictness.OFF,
        )
        result = pipeline.process(ctx)

        # workspace not found -> UNKNOWN conflict
        assert any(c.conflict_type == ConflictType.UNKNOWN for c in result.conflicts)

    def test_malformed_seed_file_skipped(self, tmp_path):
        """Pipeline continues when seed file is malformed YAML."""
        glossaries = tmp_path / ".kittify" / "glossaries"
        glossaries.mkdir(parents=True)
        (glossaries / "team_domain.yaml").write_text("{{{{invalid yaml")

        ctx = _make_context(
            inputs={"description": "test"},
        )

        pipeline = create_standard_pipeline(
            tmp_path,
            runtime_strictness=Strictness.OFF,
        )

        # Should not crash -- malformed seed file is logged and skipped
        result = pipeline.process(ctx)
        assert result is not None

    def test_empty_seed_file(self, tmp_path):
        """Pipeline handles empty seed file gracefully."""
        glossaries = tmp_path / ".kittify" / "glossaries"
        glossaries.mkdir(parents=True)
        (glossaries / "team_domain.yaml").write_text("")

        ctx = _make_context()

        pipeline = create_standard_pipeline(
            tmp_path,
            runtime_strictness=Strictness.OFF,
        )

        # Empty file loads as None, should be handled gracefully
        result = pipeline.process(ctx)
        assert result is not None


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------


#: Steady-state budget for one pipeline step (the <200ms requirement). Nightly
#: CI measured 0.005-0.103 s for these workloads over eight green runs (runs
#: 40626642957 to 44009807449), so 0.2 s keeps about 2x headroom over the
#: slowest clean figure. #7704: the figure is the median of
#: ``IN_PROCESS_SAMPLE_RUNS`` steps after one untimed warm-up step. A single
#: step was red twice over: alone, any of these tests paid the process's
#: first ``jsonschema`` import (about 1 s) and failed; and run 44230080019
#: stalled one step for 4.295 s while the identical-workload
#: ``test_hundred_watch_terms_under_200ms`` passed minutes earlier in the
#: same process. The budget is unchanged; no retry.
_PIPELINE_STEP_BUDGET_S = 0.2

_SEED_TERMS_YAML = (
    "terms:\n"
    "  - surface: workspace\n"
    "    definition: Git worktree directory\n"
    "    confidence: 1.0\n"
    "    status: active\n"
    "  - surface: mission\n"
    "    definition: Purpose-specific workflow\n"
    "    confidence: 1.0\n"
    "    status: active\n"
)


def _median_step_seconds(tmp_path, *, seed_yaml=None, pipeline_kwargs=None, **context_overrides):
    """Median seconds of one ``pipeline.process`` step, each on a fresh repository."""

    def prepare(label):
        repo = tmp_path / label
        (repo / ".kittify").mkdir(parents=True)
        if seed_yaml is not None:
            _create_seed_file(repo, "team_domain", seed_yaml)
        pipeline = create_standard_pipeline(repo, **(pipeline_kwargs or {}))
        ctx = _make_context(**context_overrides)
        return lambda: pipeline.process(ctx)

    return median_in_process_seconds(prepare)


class TestPipelinePerformance:
    """Verify pipeline execution time meets the <200ms requirement."""

    @pytest.mark.performance
    def test_pipeline_performance_simple(self, tmp_path):
        """Full pipeline execution should complete in <200ms for simple input."""
        elapsed = _median_step_seconds(
            tmp_path,
            inputs={"description": "Test with some technical terms"},
        )

        assert elapsed < _PIPELINE_STEP_BUDGET_S, f"Pipeline too slow: {elapsed:.3f}s"

    @pytest.mark.performance
    def test_pipeline_performance_with_seed_file(self, tmp_path):
        """Pipeline with seed files still completes within budget."""
        elapsed = _median_step_seconds(
            tmp_path,
            seed_yaml=_SEED_TERMS_YAML,
            pipeline_kwargs={"runtime_strictness": Strictness.OFF},
            inputs={"description": "The workspace and mission are configured"},
            metadata={"glossary_watch_terms": ["workspace", "mission"]},
        )

        assert elapsed < _PIPELINE_STEP_BUDGET_S, f"Pipeline too slow: {elapsed:.3f}s"

    @pytest.mark.performance
    def test_pipeline_performance_100_terms(self, tmp_path):
        """Pipeline with 100+ extracted terms still completes within budget."""
        elapsed = _median_step_seconds(
            tmp_path,
            pipeline_kwargs={"runtime_strictness": Strictness.OFF},
            inputs={"description": "test"},
            metadata={"glossary_watch_terms": [f"term{i}" for i in range(100)]},
        )

        assert elapsed < _PIPELINE_STEP_BUDGET_S, f"Pipeline too slow: {elapsed:.3f}s"


# ---------------------------------------------------------------------------
# End-to-end: specify step with conflict
# ---------------------------------------------------------------------------


class TestEndToEndSpecifyWithConflict:
    """Simulate a full spec-kitty specify step encountering a conflict."""

    def test_specify_step_blocked_by_ambiguous_term(self, tmp_path):
        """Full scenario: specify step -> extraction -> conflict -> BLOCKED."""
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

        # Simulate a specify step context
        ctx = PrimitiveExecutionContext(
            step_id="specify-001",
            mission_id="software-dev",
            run_id="run-abc-123",
            inputs={
                "description": ("Create a new feature that manages workspace configuration for parallel development"),
            },
            metadata={
                "glossary_check": "enabled",
                "glossary_watch_terms": ["workspace"],
                "critical_step": True,
            },
            config={
                "glossary": {
                    "enabled": True,
                    "strictness": "medium",
                },
            },
        )

        pipeline = create_standard_pipeline(tmp_path)

        with pytest.raises(BlockedByConflict) as exc_info:
            pipeline.process(ctx)

        # Verify exception has the right conflict details
        conflicts = exc_info.value.conflicts
        assert len(conflicts) >= 1

        workspace_conflict = next(
            (c for c in conflicts if c.term.surface_text == "workspace"),
            None,
        )
        assert workspace_conflict is not None
        assert workspace_conflict.conflict_type == ConflictType.AMBIGUOUS
        assert workspace_conflict.severity in (Severity.MEDIUM, Severity.HIGH)

    def test_specify_step_passes_with_off_strictness(self, tmp_path):
        """Same scenario but with --strictness off: pipeline completes."""
        _create_seed_file(
            tmp_path,
            "team_domain",
            (
                "terms:\n"
                "  - surface: workspace\n"
                "    definition: Git worktree directory\n"
                "    confidence: 0.9\n"
                "    status: active\n"
                "  - surface: workspace\n"
                "    definition: VS Code workspace config\n"
                "    confidence: 0.7\n"
                "    status: active\n"
            ),
        )

        ctx = PrimitiveExecutionContext(
            step_id="specify-001",
            mission_id="software-dev",
            run_id="run-abc-123",
            inputs={"description": "Manage workspace configuration"},
            metadata={
                "glossary_watch_terms": ["workspace"],
            },
            config={},
        )

        pipeline = create_standard_pipeline(
            tmp_path,
            runtime_strictness=Strictness.OFF,
        )

        result = pipeline.process(ctx)

        # Pipeline completes, conflicts detected but not blocked
        assert result.effective_strictness == Strictness.OFF
        # workspace is ambiguous but we don't block
        workspace_conflicts = [c for c in result.conflicts if c.term.surface_text == "workspace"]
        assert len(workspace_conflicts) >= 1

    def test_specify_step_no_conflicts_clean_glossary(self, tmp_path):
        """Specify step with a clean glossary (single sense per term) passes."""
        _create_seed_file(
            tmp_path,
            "team_domain",
            (
                "terms:\n"
                "  - surface: workspace\n"
                "    definition: Git worktree directory for a work package\n"
                "    confidence: 1.0\n"
                "    status: active\n"
            ),
        )

        ctx = PrimitiveExecutionContext(
            step_id="specify-001",
            mission_id="software-dev",
            run_id="run-abc-123",
            inputs={"description": "test"},
            metadata={
                "glossary_watch_terms": ["workspace"],
            },
            config={},
        )

        pipeline = create_standard_pipeline(tmp_path)
        result = pipeline.process(ctx)

        # Single sense: no conflict
        assert result.conflicts == []
        assert result.effective_strictness == Strictness.MEDIUM


# ---------------------------------------------------------------------------
# Exception details verification
# ---------------------------------------------------------------------------


class TestBlockedByConflictDetails:
    """Verify BlockedByConflict exception carries detailed info."""

    def test_exception_includes_strictness(self, tmp_path):
        _create_seed_file(
            tmp_path,
            "team_domain",
            (
                "terms:\n"
                "  - surface: workspace\n"
                "    definition: Git worktree directory\n"
                "    confidence: 0.9\n"
                "    status: active\n"
                "  - surface: workspace\n"
                "    definition: VS Code workspace config\n"
                "    confidence: 0.7\n"
                "    status: active\n"
            ),
        )

        ctx = _make_context(
            inputs={"description": "workspace test"},
            metadata={
                "glossary_watch_terms": ["workspace"],
            },
        )

        pipeline = create_standard_pipeline(
            tmp_path,
            runtime_strictness=Strictness.MAX,
        )

        with pytest.raises(BlockedByConflict) as exc_info:
            pipeline.process(ctx)

        assert exc_info.value.strictness == Strictness.MAX

    def test_exception_message_is_user_friendly(self, tmp_path):
        _create_seed_file(
            tmp_path,
            "team_domain",
            (
                "terms:\n"
                "  - surface: workspace\n"
                "    definition: Git worktree directory\n"
                "    confidence: 0.9\n"
                "    status: active\n"
                "  - surface: workspace\n"
                "    definition: VS Code workspace config\n"
                "    confidence: 0.7\n"
                "    status: active\n"
            ),
        )

        ctx = _make_context(
            inputs={"description": "workspace test"},
            metadata={
                "glossary_watch_terms": ["workspace"],
            },
        )

        pipeline = create_standard_pipeline(
            tmp_path,
            runtime_strictness=Strictness.MAX,
        )

        with pytest.raises(BlockedByConflict) as exc_info:
            pipeline.process(ctx)

        msg = str(exc_info.value)
        assert "blocked" in msg.lower() or "conflict" in msg.lower()


# ---------------------------------------------------------------------------
# Regression: Issue 1 -- pipeline called from production code path
# ---------------------------------------------------------------------------


class TestExecuteWithGlossaryProductionHook:
    """Verify the production code path in missions.glossary_hook calls the
    glossary pipeline. This is the concrete call site that satisfies the
    reviewer's Issue 1 requirement.
    """

    def test_execute_with_glossary_runs_pipeline(self, tmp_path):
        """execute_with_glossary() calls the glossary pipeline before the
        primitive function runs."""
        from specify_cli.missions import execute_with_glossary

        (tmp_path / ".kittify").mkdir()

        primitive_called = []

        def my_primitive(context):
            primitive_called.append(True)
            # By the time the primitive runs, effective_strictness is set
            return {"strictness": context.effective_strictness}

        ctx = _make_context()
        result = execute_with_glossary(
            primitive_fn=my_primitive,
            context=ctx,
            repo_root=tmp_path,
        )

        assert primitive_called == [True]
        assert result["strictness"] == Strictness.MEDIUM

    def test_execute_with_glossary_skips_when_disabled(self, tmp_path):
        """When glossary_check is disabled, the pipeline is skipped but the
        primitive still runs."""
        from specify_cli.missions import execute_with_glossary

        (tmp_path / ".kittify").mkdir()

        def my_primitive(context):
            return {"ran": True, "strictness": context.effective_strictness}

        ctx = _make_context(metadata={"glossary_check": "disabled"})
        result = execute_with_glossary(
            primitive_fn=my_primitive,
            context=ctx,
            repo_root=tmp_path,
        )

        assert result["ran"] is True
        # Pipeline was skipped, so strictness was never set
        assert result["strictness"] is None

    def test_execute_with_glossary_propagates_blocked_by_conflict(self, tmp_path):
        """BlockedByConflict from the pipeline propagates through
        execute_with_glossary."""
        from specify_cli.missions import execute_with_glossary

        _create_seed_file(
            tmp_path,
            "team_domain",
            (
                "terms:\n"
                "  - surface: workspace\n"
                "    definition: Git worktree directory\n"
                "    confidence: 0.9\n"
                "    status: active\n"
                "  - surface: workspace\n"
                "    definition: VS Code workspace config\n"
                "    confidence: 0.7\n"
                "    status: active\n"
            ),
        )

        def my_primitive(context):
            return {"result": "should not reach here"}

        ctx = _make_context(
            inputs={"description": "workspace test"},
            metadata={
                "glossary_watch_terms": ["workspace"],
            },
        )

        with pytest.raises(BlockedByConflict):
            execute_with_glossary(
                primitive_fn=my_primitive,
                context=ctx,
                repo_root=tmp_path,
                runtime_strictness=Strictness.MAX,
                interaction_mode="non-interactive",
            )

    def test_glossary_aware_runner_execute(self, tmp_path):
        """GlossaryAwarePrimitiveRunner.execute() runs pipeline + primitive."""
        from glossary.attachment import GlossaryAwarePrimitiveRunner

        (tmp_path / ".kittify").mkdir()

        runner = GlossaryAwarePrimitiveRunner(
            repo_root=tmp_path,
            runtime_strictness=Strictness.OFF,
        )

        def my_primitive(context, extra):
            return {"strictness": context.effective_strictness, "extra": extra}

        ctx = _make_context()
        result = runner.execute(my_primitive, ctx, "hello")

        assert result["strictness"] == Strictness.OFF
        assert result["extra"] == "hello"


# ---------------------------------------------------------------------------
# Regression: Issue 2 -- clarification runs BEFORE gate
# ---------------------------------------------------------------------------


class TestClarificationBeforeGate:
    """Verify that the pipeline ordering (clarification before gate) allows
    users to resolve conflicts before the gate blocks.

    The critical flow tested here:
    1. Ambiguous term detected (HIGH severity conflict)
    2. Clarification middleware prompts user -> user resolves conflict
    3. Generation gate sees no remaining conflicts -> does NOT block
    4. Pipeline completes successfully

    This was broken before the reorder: gate raised BlockedByConflict
    immediately, and clarification never got a chance to run.
    """

    def _setup_ambiguous_workspace(self, tmp_path):
        """Create a seed file with two active senses for 'workspace'."""
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

    def test_resolved_conflict_allows_generation_to_proceed(self, tmp_path, monkeypatch):
        """HIGH-severity conflict -> clarification resolves -> gate does NOT block.

        This is the key regression test for Issue 2. Under the old ordering
        (gate before clarification), this test would fail with BlockedByConflict
        because the gate would fire before clarification had a chance to run.
        """
        self._setup_ambiguous_workspace(tmp_path)

        # Mock the prompt function to always select candidate #1
        def mock_prompt(conflict, candidates):
            conflict.selected_index = 0
            return ("select", None)

        monkeypatch.setattr(
            "glossary.pipeline.prompt_conflict_resolution_safe",
            mock_prompt,
        )

        ctx = _make_context(
            inputs={"description": "The workspace contains implementation files"},
            metadata={
                "glossary_watch_terms": ["workspace"],
                "critical_step": True,  # Makes AMBIGUOUS -> HIGH severity
            },
        )

        # Use MEDIUM strictness which WOULD block on HIGH severity
        pipeline = create_standard_pipeline(
            tmp_path,
            runtime_strictness=Strictness.MEDIUM,
            interaction_mode="interactive",
        )

        # With the new ordering, clarification resolves the conflict
        # before the gate runs. Gate sees no remaining conflicts -> no block.
        result = pipeline.process(ctx)

        # Verify: conflict was resolved (not blocked)
        assert result.effective_strictness == Strictness.MEDIUM
        # The resolved conflict was moved out of context.conflicts
        remaining_workspace = [c for c in result.conflicts if c.term.surface_text == "workspace"]
        assert len(remaining_workspace) == 0

        # The resolved conflict is available in resolved_conflicts
        resolved = getattr(result, "resolved_conflicts", [])
        assert len(resolved) >= 1
        assert resolved[0].term.surface_text == "workspace"

    def test_max_strictness_resolved_conflict_also_proceeds(self, tmp_path, monkeypatch):
        """Even MAX strictness: if clarification resolves all conflicts,
        the gate allows generation to proceed."""
        self._setup_ambiguous_workspace(tmp_path)

        def mock_prompt(conflict, candidates):
            conflict.selected_index = 0
            return ("select", None)

        monkeypatch.setattr(
            "glossary.pipeline.prompt_conflict_resolution_safe",
            mock_prompt,
        )

        ctx = _make_context(
            inputs={"description": "The workspace contains implementation files"},
            metadata={"glossary_watch_terms": ["workspace"]},
        )

        pipeline = create_standard_pipeline(
            tmp_path,
            runtime_strictness=Strictness.MAX,
            interaction_mode="interactive",
        )

        # MAX strictness would block ANY conflict, but clarification resolved it
        result = pipeline.process(ctx)

        assert result.effective_strictness == Strictness.MAX
        assert len(result.conflicts) == 0

    def test_unresolved_conflict_still_blocked_after_clarification(self, tmp_path):
        """If clarification does NOT resolve the conflict (non-interactive mode),
        the gate still blocks correctly."""
        self._setup_ambiguous_workspace(tmp_path)

        ctx = _make_context(
            inputs={"description": "The workspace contains implementation files"},
            metadata={
                "glossary_watch_terms": ["workspace"],
                "critical_step": True,
            },
        )

        pipeline = create_standard_pipeline(
            tmp_path,
            runtime_strictness=Strictness.MEDIUM,
            interaction_mode="non-interactive",  # No prompt -> conflicts remain
        )

        # Non-interactive: clarification defers, gate sees unresolved conflicts
        with pytest.raises(BlockedByConflict) as exc_info:
            pipeline.process(ctx)

        assert len(exc_info.value.conflicts) >= 1

    def test_deferred_conflict_still_blocked(self, tmp_path, monkeypatch):
        """If user defers during clarification, the conflict remains and
        the gate blocks."""
        self._setup_ambiguous_workspace(tmp_path)

        # Mock prompt to defer
        def mock_prompt(conflict, candidates):
            return ("defer", None)

        monkeypatch.setattr(
            "glossary.pipeline.prompt_conflict_resolution_safe",
            mock_prompt,
        )

        ctx = _make_context(
            inputs={"description": "The workspace contains implementation files"},
            metadata={
                "glossary_watch_terms": ["workspace"],
                "critical_step": True,
            },
        )

        pipeline = create_standard_pipeline(
            tmp_path,
            runtime_strictness=Strictness.MEDIUM,
            interaction_mode="interactive",
        )

        # User deferred -> conflict stays -> gate blocks
        with pytest.raises(BlockedByConflict):
            pipeline.process(ctx)

    def test_custom_definition_resolves_conflict(self, tmp_path, monkeypatch):
        """User provides custom definition -> conflict resolved -> gate allows."""
        self._setup_ambiguous_workspace(tmp_path)

        def mock_prompt(conflict, candidates):
            return ("custom", "The project workspace directory on disk")

        monkeypatch.setattr(
            "glossary.pipeline.prompt_conflict_resolution_safe",
            mock_prompt,
        )

        ctx = _make_context(
            inputs={"description": "The workspace contains implementation files"},
            metadata={"glossary_watch_terms": ["workspace"]},
        )

        pipeline = create_standard_pipeline(
            tmp_path,
            runtime_strictness=Strictness.MAX,
            interaction_mode="interactive",
        )

        # Custom definition resolves the conflict -> gate allows
        result = pipeline.process(ctx)

        assert result.effective_strictness == Strictness.MAX
        assert len(result.conflicts) == 0
        resolved = getattr(result, "resolved_conflicts", [])
        assert len(resolved) >= 1

    def test_pipeline_order_verified_at_runtime(self, tmp_path):
        """Verify that in the standard pipeline, ClarificationMiddleware
        runs at index 2 (before GenerationGateMiddleware at index 3)."""
        from glossary.clarification import ClarificationMiddleware
        from glossary.middleware import GenerationGateMiddleware

        (tmp_path / ".kittify").mkdir()
        pipeline = create_standard_pipeline(tmp_path)

        # Find the indices of clarification and gate
        clarification_idx = None
        gate_idx = None
        for i, mw in enumerate(pipeline.middleware):
            if isinstance(mw, ClarificationMiddleware):
                clarification_idx = i
            if isinstance(mw, GenerationGateMiddleware):
                gate_idx = i

        assert clarification_idx is not None, "ClarificationMiddleware not in pipeline"
        assert gate_idx is not None, "GenerationGateMiddleware not in pipeline"
        assert clarification_idx < gate_idx, (
            f"ClarificationMiddleware (index {clarification_idx}) must run "
            f"BEFORE GenerationGateMiddleware (index {gate_idx})"
        )


# ---------------------------------------------------------------------------
# Regression: execute_with_glossary end-to-end
# ---------------------------------------------------------------------------


class TestExecuteWithGlossaryEndToEnd:
    """Full end-to-end tests using the production code path
    (execute_with_glossary from missions.glossary_hook).
    """

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

    def test_e2e_production_path_clarify_then_proceed(self, tmp_path, monkeypatch):
        """Full end-to-end: production hook -> clarification -> gate -> primitive.

        Proves that execute_with_glossary (the production entry point) calls
        the pipeline, clarification resolves the conflict, and the primitive
        function executes successfully.
        """
        from specify_cli.missions import execute_with_glossary


        self._setup_ambiguous_workspace(tmp_path)

        # Mock prompt to resolve
        def mock_prompt(conflict, candidates):
            conflict.selected_index = 0
            return ("select", None)

        monkeypatch.setattr(
            "glossary.pipeline.prompt_conflict_resolution_safe",
            mock_prompt,
        )

        primitive_results = []

        def my_specify_primitive(context):
            """Simulate a real specify step primitive."""
            primitive_results.append(
                {
                    "strictness": context.effective_strictness,
                    "remaining_conflicts": len(context.conflicts),
                }
            )
            return primitive_results[-1]

        ctx = _make_context(
            inputs={"description": "The workspace contains implementation files"},
            metadata={
                "glossary_watch_terms": ["workspace"],
                "critical_step": True,
            },
        )

        result = execute_with_glossary(
            primitive_fn=my_specify_primitive,
            context=ctx,
            repo_root=tmp_path,
            runtime_strictness=Strictness.MEDIUM,
            interaction_mode="interactive",
        )

        # Primitive ran
        assert len(primitive_results) == 1
        # No remaining conflicts (clarification resolved them)
        assert result["remaining_conflicts"] == 0
        # Strictness was applied
        assert result["strictness"] == Strictness.MEDIUM
