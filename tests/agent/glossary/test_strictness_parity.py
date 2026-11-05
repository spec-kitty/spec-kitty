"""Regression tests for #7065: the semantic-check event must record the gate's policy.

`SemanticCheckEvaluated` used to publish ``effective_strictness = "medium"`` whenever the
execution context did not carry a resolved strictness, and derived ``blocked`` from a
coarse ``strictness != "off"`` test. The semantic-check middleware emits that event *before*
``GenerationGateMiddleware`` resolves the global -> mission -> step -> runtime chain, so a
configured ``off``/``max`` (or a ``--strictness`` override) was published as ``medium`` and
the recorded blocking decision could differ from the one the gate applied.

These tests drive the pre-existing entry points -- ``emit_semantic_check_evaluated``,
``SemanticCheckMiddleware`` through ``create_standard_pipeline``, and
``GenerationGateMiddleware`` -- and assert the event and the gate agree.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from spec_kitty_events.persistence import build_record

from glossary.events import (
    emit_semantic_check_evaluated,
    get_event_log_path,
    read_events,
)
from glossary.middleware import GenerationGateMiddleware, SemanticCheckMiddleware
from glossary.models import ConflictType, SemanticConflict, SenseRef, Severity, TermSurface
from glossary.pipeline import create_standard_pipeline
from glossary.strictness import Strictness

pytestmark = pytest.mark.fast


@dataclass
class ParityContext:
    """Execution context shaped like the mission runtime's primitive context."""

    step_id: str = "step-7065"
    mission_id: str = "mission-7065"
    run_id: str = "run-7065"
    metadata: dict[str, Any] = field(default_factory=dict)
    step_input: dict[str, Any] = field(default_factory=dict)
    step_output: dict[str, Any] = field(default_factory=dict)
    extracted_terms: list[Any] = field(default_factory=list)
    conflicts: list[SemanticConflict] = field(default_factory=list)
    effective_strictness: Any = None
    mission_strictness: Any = None
    step_strictness: Any = None


def _repo_with_strictness(root: Path, value: str) -> Path:
    kittify = root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text(f"glossary:\n  strictness: {value}\n", encoding="utf-8")
    return root


def _conflict(severity: Severity) -> SemanticConflict:
    return SemanticConflict(
        term=TermSurface("workspace"),
        conflict_type=ConflictType.AMBIGUOUS,
        severity=severity,
        confidence=0.9,
        candidate_senses=[
            SenseRef("workspace", "team_domain", "Git worktree directory", 0.9),
            SenseRef("workspace", "team_domain", "Editor workspace file", 0.7),
        ],
        context="description field",
    )


class TestEventMatchesTheGate:
    """The persisted event carries the strictness and decision the gate applies."""

    def test_configured_off_is_recorded_and_nothing_is_marked_blocked(self, tmp_path: Path) -> None:
        root = _repo_with_strictness(tmp_path, "off")
        conflicts = [_conflict(Severity.HIGH)]

        event = emit_semantic_check_evaluated(
            context=ParityContext(),
            conflicts=conflicts,
            repo_root=root,
        )

        assert event is not None
        assert event["effective_strictness"] == Strictness.OFF.value
        assert event["blocked"] is False
        build_record(event)  # conforms to the spec-kitty-events contract

        gate_context = GenerationGateMiddleware(repo_root=root).process(ParityContext(conflicts=list(conflicts)))
        assert gate_context.effective_strictness is Strictness.OFF
        assert gate_context.effective_strictness.value == event["effective_strictness"]

    def test_configured_max_is_recorded_and_blocks_like_the_gate(self, tmp_path: Path) -> None:
        from glossary.exceptions import BlockedByConflict

        root = _repo_with_strictness(tmp_path, "max")
        conflicts = [_conflict(Severity.LOW)]

        event = emit_semantic_check_evaluated(
            context=ParityContext(),
            conflicts=conflicts,
            repo_root=root,
        )

        assert event is not None
        assert event["effective_strictness"] == Strictness.MAX.value
        assert event["blocked"] is True
        build_record(event)

        with pytest.raises(BlockedByConflict) as blocked:
            GenerationGateMiddleware(repo_root=root).process(ParityContext(conflicts=list(conflicts)))
        assert blocked.value.strictness is Strictness.MAX

    def test_medium_policy_does_not_report_a_block_the_gate_would_not_apply(self, tmp_path: Path) -> None:
        """Under the default policy a medium-severity conflict is not a block."""
        root = _repo_with_strictness(tmp_path, "medium")

        medium_event = emit_semantic_check_evaluated(
            context=ParityContext(),
            conflicts=[_conflict(Severity.MEDIUM)],
            repo_root=root,
        )
        high_event = emit_semantic_check_evaluated(
            context=ParityContext(),
            conflicts=[_conflict(Severity.HIGH)],
            repo_root=root,
        )

        assert medium_event is not None and high_event is not None
        assert medium_event["effective_strictness"] == Strictness.MEDIUM.value
        assert medium_event["blocked"] is False
        # Positive control: the same fixture still reports a real block.
        assert high_event["blocked"] is True


class TestPipelineWiring:
    """The production pipeline records the strictness its gate enforces."""

    @pytest.mark.parametrize(
        ("runtime_strictness", "expected"),
        [
            pytest.param(Strictness.OFF, Strictness.OFF, id="runtime-override"),
            pytest.param(None, Strictness.MAX, id="configured-policy"),
        ],
    )
    def test_pipeline_records_the_strictness_its_gate_enforces(self, tmp_path: Path, runtime_strictness: Strictness | None, expected: Strictness) -> None:
        root = _repo_with_strictness(tmp_path, "max")

        pipeline = create_standard_pipeline(
            repo_root=root,
            runtime_strictness=runtime_strictness,
            interaction_mode="non-interactive",
        )
        check = next(mw for mw in pipeline.middleware if isinstance(mw, SemanticCheckMiddleware))

        context = ParityContext()
        result = check.process(context)

        assert result.effective_strictness is expected

        log_path = get_event_log_path(root, context.mission_id)
        events = [e for e in read_events(log_path) if e.get("event_type") == "SemanticCheckEvaluated"]
        assert len(events) == 1
        assert events[0]["effective_strictness"] == expected.value
        assert events[0]["blocked"] is False

        # The gate in the same pipeline enforces the value the event recorded.
        gate = next(mw for mw in pipeline.middleware if isinstance(mw, GenerationGateMiddleware))
        assert gate.process(result).effective_strictness is expected


class TestEmitterFallbacks:
    """The emitter's own resolution when a caller did not resolve strictness first."""

    def test_an_unrecognised_context_value_is_ignored_in_favour_of_the_policy(self, tmp_path: Path) -> None:
        """A malformed context value must not outrank the configured policy."""
        root = _repo_with_strictness(tmp_path, "off")
        context = ParityContext(effective_strictness="not-a-policy")

        event = emit_semantic_check_evaluated(context=context, conflicts=[], repo_root=root)

        assert event is not None
        assert event["effective_strictness"] == Strictness.OFF.value
        build_record(event)

    def test_no_policy_configured_still_yields_the_documented_medium_default(self, tmp_path: Path) -> None:
        context = ParityContext()

        event = emit_semantic_check_evaluated(context=context, conflicts=[])

        assert event is not None
        assert event["effective_strictness"] == Strictness.MEDIUM.value
        build_record(event)

    def test_a_direct_caller_can_pass_the_runtime_override(self, tmp_path: Path) -> None:
        """A caller that bypasses the middleware still resolves the CLI override."""
        root = _repo_with_strictness(tmp_path, "max")

        event = emit_semantic_check_evaluated(
            context=ParityContext(),
            conflicts=[],
            repo_root=root,
            runtime_override=Strictness.OFF,
        )

        assert event is not None
        assert event["effective_strictness"] == Strictness.OFF.value
        build_record(event)

    def test_an_explicit_argument_still_wins(self, tmp_path: Path) -> None:
        root = _repo_with_strictness(tmp_path, "off")

        event = emit_semantic_check_evaluated(
            context=ParityContext(),
            conflicts=[],
            effective_strictness=Strictness.MAX,
            repo_root=root,
        )

        assert event is not None
        assert event["effective_strictness"] == Strictness.MAX.value
