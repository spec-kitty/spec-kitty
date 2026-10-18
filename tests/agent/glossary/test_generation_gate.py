"""Integration tests for GenerationGateMiddleware (WP05)."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock
from dataclasses import dataclass, field
from typing import Any

from glossary.middleware import GenerationGateMiddleware
from glossary.models import (
    SemanticConflict,
    Severity,
    TermSurface,
    ConflictType,
)
from glossary.strictness import Strictness
from glossary.exceptions import BlockedByConflict
import contextlib

pytestmark = pytest.mark.fast

@dataclass
class MockPrimitiveContext:
    """Mock execution context for testing."""

    step_id: str = "test-step-001"
    mission_id: str = "software-dev"
    metadata: dict[str, Any] = field(default_factory=dict)
    step_input: dict[str, Any] = field(default_factory=dict)
    step_output: dict[str, Any] = field(default_factory=dict)
    extracted_terms: list[Any] = field(default_factory=list)
    conflicts: list[SemanticConflict] = field(default_factory=list)
    mission_strictness: Strictness | None = None
    step_strictness: Strictness | None = None
    effective_strictness: Strictness | None = None


@pytest.fixture
def mock_context():
    """Create mock primitive execution context."""
    return MockPrimitiveContext()


@pytest.fixture
def high_severity_conflict():
    """Create high-severity conflict for testing."""
    from glossary.models import SenseRef

    return SemanticConflict(
        term=TermSurface(surface_text="workspace"),
        conflict_type=ConflictType.AMBIGUOUS,
        severity=Severity.HIGH,
        confidence=0.9,
        candidate_senses=[
            SenseRef(surface="workspace", scope="mission_local", definition="test def 1", confidence=0.9),
            SenseRef(surface="workspace", scope="team_domain", definition="test def 2", confidence=0.8),
        ],
        context="term 'workspace' has multiple active senses",
    )


@pytest.fixture
def medium_severity_conflict():
    """Create medium-severity conflict for testing."""
    from glossary.models import SenseRef

    return SemanticConflict(
        term=TermSurface(surface_text="utility"),
        conflict_type=ConflictType.AMBIGUOUS,
        severity=Severity.MEDIUM,
        confidence=0.6,
        candidate_senses=[
            SenseRef(surface="utility", scope="mission_local", definition="test def 1", confidence=0.7),
            SenseRef(surface="utility", scope="team_domain", definition="test def 2", confidence=0.6),
        ],
        context="term 'utility' has multiple active senses",
    )


@pytest.fixture
def low_severity_conflict():
    """Create low-severity conflict for testing."""
    return SemanticConflict(
        term=TermSurface(surface_text="helper"),
        conflict_type=ConflictType.UNKNOWN,
        severity=Severity.LOW,
        confidence=0.3,
        candidate_senses=[],
        context="term 'helper' not found in any scope",
    )


class TestOffModeNeverBlocks:
    """Test that OFF strictness mode never blocks generation."""

    def test_off_allows_empty_conflicts(self, mock_context):
        """OFF mode allows generation with no conflicts."""
        gate = GenerationGateMiddleware(runtime_override=Strictness.OFF)
        mock_context.conflicts = []

        result = gate.process(mock_context)

        assert result == mock_context
        assert result.effective_strictness == Strictness.OFF

    def test_off_allows_low_severity(self, mock_context, low_severity_conflict):
        """OFF mode allows generation with low-severity conflicts."""
        gate = GenerationGateMiddleware(runtime_override=Strictness.OFF)
        mock_context.conflicts = [low_severity_conflict]

        result = gate.process(mock_context)

        assert result == mock_context
        assert result.effective_strictness == Strictness.OFF

    def test_off_allows_medium_severity(self, mock_context, medium_severity_conflict):
        """OFF mode allows generation with medium-severity conflicts."""
        gate = GenerationGateMiddleware(runtime_override=Strictness.OFF)
        mock_context.conflicts = [medium_severity_conflict]

        result = gate.process(mock_context)

        assert result == mock_context

    def test_off_allows_high_severity(self, mock_context, high_severity_conflict):
        """OFF mode allows generation even with high-severity conflicts."""
        gate = GenerationGateMiddleware(runtime_override=Strictness.OFF)
        mock_context.conflicts = [high_severity_conflict]

        result = gate.process(mock_context)

        assert result == mock_context
        assert result.effective_strictness == Strictness.OFF

    def test_off_allows_mixed_severity(
        self, mock_context, low_severity_conflict, medium_severity_conflict, high_severity_conflict
    ):
        """OFF mode allows generation with mixed-severity conflicts."""
        gate = GenerationGateMiddleware(runtime_override=Strictness.OFF)
        mock_context.conflicts = [
            low_severity_conflict,
            medium_severity_conflict,
            high_severity_conflict,
        ]

        result = gate.process(mock_context)

        assert result == mock_context


class TestMediumModeBlocksHighSeverity:
    """Test that MEDIUM strictness blocks only high-severity conflicts."""

    def test_medium_allows_empty_conflicts(self, mock_context):
        """MEDIUM mode allows generation with no conflicts."""
        gate = GenerationGateMiddleware(runtime_override=Strictness.MEDIUM)
        mock_context.conflicts = []

        result = gate.process(mock_context)

        assert result == mock_context
        assert result.effective_strictness == Strictness.MEDIUM

    def test_medium_allows_low_severity(self, mock_context, low_severity_conflict):
        """MEDIUM mode allows generation with low-severity conflicts."""
        gate = GenerationGateMiddleware(runtime_override=Strictness.MEDIUM)
        mock_context.conflicts = [low_severity_conflict]

        result = gate.process(mock_context)

        assert result == mock_context

    def test_medium_allows_medium_severity(self, mock_context, medium_severity_conflict):
        """MEDIUM mode allows generation with medium-severity conflicts."""
        gate = GenerationGateMiddleware(runtime_override=Strictness.MEDIUM)
        mock_context.conflicts = [medium_severity_conflict]

        result = gate.process(mock_context)

        assert result == mock_context

    def test_medium_blocks_high_severity(self, mock_context, high_severity_conflict):
        """MEDIUM mode blocks generation on high-severity conflicts."""
        gate = GenerationGateMiddleware(runtime_override=Strictness.MEDIUM)
        mock_context.conflicts = [high_severity_conflict]

        with pytest.raises(BlockedByConflict) as exc_info:
            gate.process(mock_context)

        assert exc_info.value.strictness == Strictness.MEDIUM
        assert len(exc_info.value.conflicts) == 1
        assert "high-severity" in str(exc_info.value).lower()

    def test_medium_blocks_mixed_with_high(
        self, mock_context, low_severity_conflict, medium_severity_conflict, high_severity_conflict
    ):
        """MEDIUM mode blocks if ANY conflict is high-severity."""
        gate = GenerationGateMiddleware(runtime_override=Strictness.MEDIUM)
        mock_context.conflicts = [
            low_severity_conflict,
            medium_severity_conflict,
            high_severity_conflict,
        ]

        with pytest.raises(BlockedByConflict) as exc_info:
            gate.process(mock_context)

        assert len(exc_info.value.conflicts) == 3
        assert "1 high-severity" in str(exc_info.value)
        assert "out of 3 total" in str(exc_info.value)

    def test_medium_allows_many_low_conflicts(self, mock_context):
        """MEDIUM mode allows many low-severity conflicts."""
        conflicts = [
            SemanticConflict(
                term=TermSurface(surface_text=f"term{i}"),
                conflict_type=ConflictType.UNKNOWN,
                severity=Severity.LOW,
                confidence=0.3,
                candidate_senses=[],
                context="test",
            )
            for i in range(100)
        ]
        gate = GenerationGateMiddleware(runtime_override=Strictness.MEDIUM)
        mock_context.conflicts = conflicts

        result = gate.process(mock_context)

        assert result == mock_context


class TestMaxModeBlocksAnyConflict:
    """Test that MAX strictness blocks on any conflict."""

    def test_max_allows_empty_conflicts(self, mock_context):
        """MAX mode allows generation with no conflicts."""
        gate = GenerationGateMiddleware(runtime_override=Strictness.MAX)
        mock_context.conflicts = []

        result = gate.process(mock_context)

        assert result == mock_context
        assert result.effective_strictness == Strictness.MAX

    def test_max_blocks_low_severity(self, mock_context, low_severity_conflict):
        """MAX mode blocks even on low-severity conflicts."""
        gate = GenerationGateMiddleware(runtime_override=Strictness.MAX)
        mock_context.conflicts = [low_severity_conflict]

        with pytest.raises(BlockedByConflict):
            gate.process(mock_context)

    def test_max_blocks_medium_severity(self, mock_context, medium_severity_conflict):
        """MAX mode blocks on medium-severity conflicts."""
        gate = GenerationGateMiddleware(runtime_override=Strictness.MAX)
        mock_context.conflicts = [medium_severity_conflict]

        with pytest.raises(BlockedByConflict):
            gate.process(mock_context)

    def test_max_blocks_high_severity(self, mock_context, high_severity_conflict):
        """MAX mode blocks on high-severity conflicts."""
        gate = GenerationGateMiddleware(runtime_override=Strictness.MAX)
        mock_context.conflicts = [high_severity_conflict]

        with pytest.raises(BlockedByConflict):
            gate.process(mock_context)

    def test_max_blocks_single_low(self, mock_context):
        """MAX mode blocks on a single low-severity conflict."""
        conflict = SemanticConflict(
            term=TermSurface(surface_text="test"),
            conflict_type=ConflictType.UNKNOWN,
            severity=Severity.LOW,
            confidence=0.1,
            candidate_senses=[],
            context="test",
        )
        gate = GenerationGateMiddleware(runtime_override=Strictness.MAX)
        mock_context.conflicts = [conflict]

        with pytest.raises(BlockedByConflict):
            gate.process(mock_context)


class TestPrecedenceResolution:
    """Test strictness precedence resolution."""

    def test_runtime_override_beats_all(self, mock_context):
        """Runtime override takes precedence over all other settings."""
        gate = GenerationGateMiddleware(runtime_override=Strictness.OFF)
        mock_context.mission_strictness = Strictness.MAX
        mock_context.step_strictness = Strictness.MAX

        # Add high-severity conflict
        from glossary.models import SenseRef

        mock_context.conflicts = [
            SemanticConflict(
                term=TermSurface(surface_text="test"),
                conflict_type=ConflictType.AMBIGUOUS,
                severity=Severity.HIGH,
                confidence=0.9,
                candidate_senses=[
                    SenseRef(surface="test", scope="mission_local", definition="def1", confidence=0.9),
                ],
                context="test",
            )
        ]

        # Runtime override (OFF) should win, allowing generation
        result = gate.process(mock_context)
        assert result.effective_strictness == Strictness.OFF

    def test_step_override_beats_mission(self, mock_context, low_severity_conflict):
        """Step strictness beats mission strictness."""
        gate = GenerationGateMiddleware()  # No runtime override
        mock_context.mission_strictness = Strictness.OFF
        mock_context.step_strictness = Strictness.MAX
        mock_context.conflicts = [low_severity_conflict]

        # Step override (MAX) should win, blocking generation
        with pytest.raises(BlockedByConflict):
            gate.process(mock_context)

    def test_mission_override_beats_global(self, mock_context, tmp_path):
        """Mission strictness beats global default."""
        # Setup config with global strictness=OFF
        config_dir = tmp_path / ".kittify"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text("glossary:\n  strictness: off\n")

        gate = GenerationGateMiddleware(repo_root=tmp_path)
        mock_context.mission_strictness = Strictness.MAX
        mock_context.step_strictness = None
        mock_context.conflicts = [
            SemanticConflict(
                term=TermSurface(surface_text="test"),
                conflict_type=ConflictType.UNKNOWN,
                severity=Severity.LOW,
                confidence=0.3,
                candidate_senses=[],
                context="test",
            )
        ]

        # Mission override (MAX) should win over global (OFF)
        with pytest.raises(BlockedByConflict):
            gate.process(mock_context)

    def test_global_default_used_when_no_overrides(self, mock_context, tmp_path):
        """Global default is used when no overrides are set."""
        # Setup config with global strictness=MAX
        config_dir = tmp_path / ".kittify"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text("glossary:\n  strictness: max\n")

        gate = GenerationGateMiddleware(repo_root=tmp_path)
        mock_context.mission_strictness = None
        mock_context.step_strictness = None
        mock_context.conflicts = [
            SemanticConflict(
                term=TermSurface(surface_text="test"),
                conflict_type=ConflictType.UNKNOWN,
                severity=Severity.LOW,
                confidence=0.3,
                candidate_senses=[],
                context="test",
            )
        ]

        # Global (MAX) should be used
        with pytest.raises(BlockedByConflict):
            gate.process(mock_context)

    def test_fallback_to_medium_when_no_config(self, mock_context, high_severity_conflict):
        """When no config exists, defaults to MEDIUM."""
        gate = GenerationGateMiddleware(repo_root=Path("/nonexistent"))
        mock_context.conflicts = [high_severity_conflict]

        # Should block (MEDIUM blocks high-severity)
        with pytest.raises(BlockedByConflict):
            gate.process(mock_context)


class TestEventEmission:
    """Test event emission behavior."""

    def test_event_emitted_before_blocking(self, mock_context, high_severity_conflict, monkeypatch):
        """Verify event is emitted BEFORE exception is raised."""
        from glossary import events

        emission_order = []

        def mock_emit(*args, **kwargs):
            emission_order.append("event")

        monkeypatch.setattr(events, "emit_generation_blocked_event", mock_emit)

        gate = GenerationGateMiddleware(runtime_override=Strictness.MEDIUM)
        mock_context.conflicts = [high_severity_conflict]

        try:
            gate.process(mock_context)
        except BlockedByConflict:
            emission_order.append("exception")

        # Event should be emitted before exception
        assert emission_order == ["event", "exception"]

    def test_event_includes_context_info(self, mock_context, high_severity_conflict, monkeypatch):
        """Event emission includes step_id, mission_id, conflicts, and strictness."""
        from glossary import events

        captured_args = {}

        def mock_emit(**kwargs):
            captured_args.update(kwargs)

        monkeypatch.setattr(events, "emit_generation_blocked_event", mock_emit)

        gate = GenerationGateMiddleware(runtime_override=Strictness.MEDIUM)
        mock_context.step_id = "test-step-123"
        mock_context.mission_id = "test-mission-456"
        mock_context.conflicts = [high_severity_conflict]

        with contextlib.suppress(BlockedByConflict):
            gate.process(mock_context)

        assert captured_args["step_id"] == "test-step-123"
        assert captured_args["mission_id"] == "test-mission-456"
        assert len(captured_args["conflicts"]) == 1
        assert captured_args["strictness_mode"] == Strictness.MEDIUM

    def test_no_event_when_not_blocking(self, mock_context, low_severity_conflict, monkeypatch):
        """Event is not emitted when generation is allowed."""
        from glossary import events

        emission_count = [0]

        def mock_emit(*args, **kwargs):
            emission_count[0] += 1

        monkeypatch.setattr(events, "emit_generation_blocked_event", mock_emit)

        gate = GenerationGateMiddleware(runtime_override=Strictness.MEDIUM)
        mock_context.conflicts = [low_severity_conflict]

        gate.process(mock_context)

        # No event should be emitted
        assert emission_count[0] == 0


class TestErrorMessages:
    """Test error message formatting."""

    def test_message_includes_high_severity_count(self, mock_context):
        """Error message includes high-severity conflict count."""
        from glossary.models import SenseRef

        high1 = SemanticConflict(
            term=TermSurface(surface_text="test1"),
            conflict_type=ConflictType.AMBIGUOUS,
            severity=Severity.HIGH,
            confidence=0.9,
            candidate_senses=[
                SenseRef(surface="test1", scope="mission_local", definition="def1", confidence=0.9),
            ],
            context="test",
        )
        high2 = SemanticConflict(
            term=TermSurface(surface_text="test2"),
            conflict_type=ConflictType.AMBIGUOUS,
            severity=Severity.HIGH,
            confidence=0.9,
            candidate_senses=[
                SenseRef(surface="test2", scope="mission_local", definition="def2", confidence=0.9),
            ],
            context="test",
        )
        low = SemanticConflict(
            term=TermSurface(surface_text="test3"),
            conflict_type=ConflictType.UNKNOWN,
            severity=Severity.LOW,
            confidence=0.3,
            candidate_senses=[],
            context="test",
        )

        gate = GenerationGateMiddleware(runtime_override=Strictness.MEDIUM)
        mock_context.conflicts = [high1, high2, low]

        with pytest.raises(BlockedByConflict) as exc_info:
            gate.process(mock_context)

        message = str(exc_info.value)
        assert "2 high-severity" in message
        assert "out of 3 total" in message

    def test_message_for_all_low_in_max_mode(self, mock_context):
        """Error message when MAX mode blocks on low-severity conflicts."""
        conflicts = [
            SemanticConflict(
                term=TermSurface(surface_text=f"test{i}"),
                conflict_type=ConflictType.UNKNOWN,
                severity=Severity.LOW,
                confidence=0.3,
                candidate_senses=[],
                context="test",
            )
            for i in range(3)
        ]

        gate = GenerationGateMiddleware(runtime_override=Strictness.MAX)
        mock_context.conflicts = conflicts

        with pytest.raises(BlockedByConflict) as exc_info:
            gate.process(mock_context)

        message = str(exc_info.value)
        assert "3 unresolved semantic conflict(s)" in message
        # Should NOT mention high-severity (since there are none)
        assert "high-severity" not in message.lower() or "0 high-severity" in message.lower()


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_no_repo_root_uses_medium_default(self, mock_context, high_severity_conflict):
        """When repo_root is None, uses MEDIUM as global default."""
        gate = GenerationGateMiddleware(repo_root=None)
        mock_context.conflicts = [high_severity_conflict]

        # MEDIUM should block on high-severity
        with pytest.raises(BlockedByConflict):
            gate.process(mock_context)

    def test_context_without_conflicts_attribute(self):
        """Context without conflicts attribute is treated as empty list."""
        # Create a minimal context without conflicts attribute
        minimal_context = MagicMock()
        minimal_context.step_id = "test-step"
        minimal_context.mission_id = "test-mission"

        gate = GenerationGateMiddleware(runtime_override=Strictness.MEDIUM)

        # Should not raise (empty conflicts, never blocks)
        result = gate.process(minimal_context)
        assert result == minimal_context

    def test_effective_strictness_stored_in_context(self, mock_context):
        """Effective strictness is stored in context for observability."""
        gate = GenerationGateMiddleware(runtime_override=Strictness.MAX)
        mock_context.conflicts = []

        result = gate.process(mock_context)

        assert hasattr(result, "effective_strictness")
        assert result.effective_strictness == Strictness.MAX

    def test_blocking_with_custom_message(self, mock_context, high_severity_conflict):
        """BlockedByConflict exception includes custom message."""
        gate = GenerationGateMiddleware(runtime_override=Strictness.MEDIUM)
        mock_context.conflicts = [high_severity_conflict]

        with pytest.raises(BlockedByConflict) as exc_info:
            gate.process(mock_context)

        # Message should be user-friendly
        message = str(exc_info.value)
        assert "Generation blocked" in message
        assert "Resolve conflicts" in message

    def test_blocked_by_conflict_still_raised_when_event_emission_fails(
        self, mock_context, high_severity_conflict, monkeypatch
    ):
        """BlockedByConflict MUST be raised even if emit_generation_blocked_event raises.

        Regression test for review issue 1: if the event emitter throws
        (transport failure, serialization, etc.), the middleware must still
        raise BlockedByConflict so that generation is never allowed through.
        """
        from glossary import events

        def failing_emit(*args, **kwargs):
            raise RuntimeError("Transport failure in event emission")

        monkeypatch.setattr(events, "emit_generation_blocked_event", failing_emit)

        gate = GenerationGateMiddleware(runtime_override=Strictness.MEDIUM)
        mock_context.conflicts = [high_severity_conflict]

        # BlockedByConflict must still be raised, not RuntimeError
        with pytest.raises(BlockedByConflict) as exc_info:
            gate.process(mock_context)

        assert exc_info.value.strictness == Strictness.MEDIUM
        assert len(exc_info.value.conflicts) == 1

    def test_event_emission_error_is_logged(self, mock_context, high_severity_conflict, monkeypatch, caplog):
        """When event emission fails, the error is logged."""
        import logging
        from glossary import events


        def failing_emit(*args, **kwargs):
            raise ValueError("Serialization error")

        monkeypatch.setattr(events, "emit_generation_blocked_event", failing_emit)

        gate = GenerationGateMiddleware(runtime_override=Strictness.MEDIUM)
        mock_context.conflicts = [high_severity_conflict]

        with caplog.at_level(logging.ERROR), pytest.raises(BlockedByConflict):
            gate.process(mock_context)

        assert "Failed to emit generation-blocked event" in caplog.text
        assert "Serialization error" in caplog.text
