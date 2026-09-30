"""Glossary extraction middleware (WP03, updated WP08).

This module implements middleware that extracts glossary term candidates from
primitive execution context (step inputs/outputs) and emits events.

WP08 replaces all event emission stubs with real implementations that
persist events to JSONL files via the events module.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from .extraction import ExtractedTerm, extract_all_terms

_logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from . import models, scope, store
    from .checkpoint import StepCheckpoint
    from .strictness import Strictness


class PrimitiveExecutionContext(Protocol):
    """Protocol for primitive execution context.

    This is a forward reference to the actual context that will be implemented
    in WP08 (orchestrator integration). For now, we define the minimal interface
    needed for extraction middleware.
    """

    metadata: dict[str, Any]
    """Step metadata (may contain glossary_* fields)"""

    step_input: dict[str, Any]
    """Step input data"""

    step_output: dict[str, Any]
    """Step output data"""

    extracted_terms: list[ExtractedTerm]
    """List of extracted terms (populated by middleware)"""


@dataclass
class MockContext:
    """Mock context for testing middleware in isolation.

    This will be replaced by the actual PrimitiveExecutionContext in WP08.
    """

    metadata: dict[str, Any] = field(default_factory=dict)
    step_input: dict[str, Any] = field(default_factory=dict)
    step_output: dict[str, Any] = field(default_factory=dict)
    extracted_terms: list[ExtractedTerm] = field(default_factory=list)


class GlossaryCandidateExtractionMiddleware:
    """Middleware that extracts glossary term candidates from execution context.

    This middleware:
    1. Extracts terms from metadata hints (glossary_watch_terms, etc.)
    2. Extracts terms from heuristics (quoted phrases, acronyms, casing patterns, repeated nouns)
    3. Normalizes all terms
    4. Scores confidence
    5. Emits TermCandidateObserved events to JSONL event log
    6. Adds extracted terms to context.extracted_terms

    Performance target: <100ms for typical step input (100-500 words).
    """

    def __init__(
        self,
        glossary_fields: list[str] | None = None,
        repo_root: Path | None = None,
    ) -> None:
        """Initialize middleware.

        Args:
            glossary_fields: List of field names to scan for terms.
                If None, scans all fields. Default: ["description", "prompt", "output"]
            repo_root: Repository root for event log persistence. If None,
                events are logged but not persisted to disk.
        """
        self.glossary_fields = glossary_fields or ["description", "prompt", "output"]
        self.repo_root = repo_root

    def process(self, context: PrimitiveExecutionContext) -> PrimitiveExecutionContext:
        """Process context and extract term candidates.

        Args:
            context: Execution context (must have metadata, step_input, step_output)

        Returns:
            Updated context with extracted_terms populated

        Side effects:
            - Emits TermCandidateObserved events (WP08)
        """
        # 1. Determine which fields to scan
        # Check if metadata specifies glossary_fields (runtime override)
        fields_to_scan = self.glossary_fields
        if context.metadata and "glossary_fields" in context.metadata:
            metadata_fields = context.metadata["glossary_fields"]
            # Validate it's a list of strings
            if isinstance(metadata_fields, list) and all(isinstance(f, str) for f in metadata_fields):
                fields_to_scan = metadata_fields

        # 2. Collect text from glossary fields
        text_parts: list[str] = []

        # Scan configured fields in step_input
        for field_name in fields_to_scan:
            if field_name in context.step_input:
                value = context.step_input[field_name]
                if isinstance(value, str):
                    text_parts.append(value)

        # Scan configured fields in step_output
        for field_name in fields_to_scan:
            if field_name in context.step_output:
                value = context.step_output[field_name]
                if isinstance(value, str):
                    text_parts.append(value)

        # Combine all text
        combined_text = "\n".join(text_parts)

        # 3. Extract terms (metadata hints + heuristics)
        extracted = extract_all_terms(
            text=combined_text,
            metadata=context.metadata if context.metadata else None,
            limit_words=1000,
        )

        # 4. Add to context
        context.extracted_terms.extend(extracted)

        # 5. Emit events for each extracted term
        for term in extracted:
            self._emit_term_candidate_observed(term, context)

        return context

    def _emit_term_candidate_observed(
        self,
        term: ExtractedTerm,
        context: PrimitiveExecutionContext,
    ) -> None:
        """Emit TermCandidateObserved event to event log.

        Args:
            term: Extracted term to emit event for
            context: Execution context providing metadata
        """
        from .events import emit_term_candidate_observed

        try:
            emit_term_candidate_observed(
                term=term,
                context=context,
                repo_root=self.repo_root,
            )
        except Exception as exc:
            import logging

            logging.getLogger(__name__).error(
                "Failed to emit TermCandidateObserved for %s: %s",
                term.surface,
                exc,
            )


class SemanticCheckMiddleware:
    """Middleware that resolves extracted terms and detects semantic conflicts.

    This middleware:
    1. Resolves extracted terms against scope hierarchy
    2. Classifies conflicts (UNKNOWN, AMBIGUOUS, INCONSISTENT, UNRESOLVED_CRITICAL)
    3. Scores severity based on step criticality + confidence
    4. Emits SemanticCheckEvaluated events to JSONL event log
    5. Adds conflicts to context.conflicts

    Usage:
        middleware = SemanticCheckMiddleware(glossary_store, scope_order)
        context = middleware.process(context)
    """

    def __init__(
        self,
        glossary_store: store.GlossaryStore,
        scope_order: list[scope.GlossaryScope] | None = None,
        repo_root: Path | None = None,
    ) -> None:
        """Initialize middleware.

        Args:
            glossary_store: GlossaryStore to query for term resolution
            scope_order: List of GlossaryScope in precedence order.
                If None, uses default SCOPE_RESOLUTION_ORDER.
            repo_root: Repository root for event log persistence. If None,
                events are logged but not persisted to disk.
        """
        from . import scope

        self.glossary_store = glossary_store
        self.scope_order = scope_order or scope.SCOPE_RESOLUTION_ORDER
        self.repo_root = repo_root

    def process(self, context: PrimitiveExecutionContext) -> PrimitiveExecutionContext:
        """Process context and detect semantic conflicts.

        Args:
            context: Execution context with extracted_terms populated

        Returns:
            Updated context with conflicts populated

        Side effects:
            - Emits SemanticCheckEvaluated event (WP08)
        """
        from typing import cast, Any
        from .conflict import classify_conflict, create_conflict, score_severity
        from .resolution import resolve_term

        conflicts: list[models.SemanticConflict] = []

        # Get step criticality flag from metadata (default: False)
        is_critical_step = False
        if hasattr(context, "metadata") and context.metadata:
            is_critical_step = context.metadata.get("critical_step", False)

        # Get LLM output text for INCONSISTENT detection (if available)
        llm_output_text: str | None = None
        if hasattr(context, "step_output") and context.step_output:
            # Extract text from output fields for contradiction detection
            output_parts: list[str] = []
            for value in context.step_output.values():
                if isinstance(value, str):
                    output_parts.append(value)
            if output_parts:
                llm_output_text = "\n".join(output_parts)

        # Resolve each extracted term
        for extracted_term in context.extracted_terms:
            # 1. Resolve against scope hierarchy
            senses = resolve_term(
                extracted_term.surface,
                self.scope_order,
                self.glossary_store,
            )

            # 2. Classify conflict (with all 4 types)
            conflict_type = classify_conflict(
                extracted_term,
                senses,
                is_critical_step=is_critical_step,
                llm_output_text=llm_output_text,
            )

            # 3. If conflict exists, score severity and create conflict
            if conflict_type is not None:
                severity = score_severity(
                    conflict_type,
                    extracted_term.confidence,
                    is_critical_step,
                )

                # Determine context string
                context_str = f"source: {extracted_term.source}"

                conflict = create_conflict(
                    term=extracted_term,
                    conflict_type=conflict_type,
                    severity=severity,
                    candidate_senses=senses,
                    context=context_str,
                )

                conflicts.append(conflict)

        # Add conflicts to context (using setattr to handle Protocol)
        if not hasattr(context, "conflicts"):
            context.conflicts = []
        cast(Any, context).conflicts.extend(conflicts)

        # Emit SemanticCheckEvaluated event
        self._emit_semantic_check_evaluated(context, conflicts)

        return context

    def _emit_semantic_check_evaluated(
        self,
        context: PrimitiveExecutionContext,
        conflicts: list[models.SemanticConflict],
    ) -> None:
        """Emit SemanticCheckEvaluated event to event log.

        Args:
            context: Execution context
            conflicts: List of detected conflicts
        """
        from .events import emit_semantic_check_evaluated

        try:
            emit_semantic_check_evaluated(
                context=context,
                conflicts=conflicts,
                repo_root=self.repo_root,
            )
        except Exception as exc:
            import logging

            logging.getLogger(__name__).error("Failed to emit SemanticCheckEvaluated: %s", exc)


class GenerationGateMiddleware:
    """Generation gate that blocks LLM calls on unresolved conflicts.

    This middleware:
    1. Resolves effective strictness from precedence chain
    2. Evaluates whether to block based on strictness policy
    3. Emits GenerationBlockedBySemanticConflict event if blocking
    4. Raises BlockedByConflict exception to halt pipeline

    Pipeline position: Layer 3 (after extraction and semantic check)

    Usage:
        gate = GenerationGateMiddleware(
            repo_root=Path("."),
            runtime_override=Strictness.MEDIUM,
        )
        context = gate.process(context)
    """

    def __init__(
        self,
        repo_root: Path | None = None,
        runtime_override: Strictness | None = None,
    ) -> None:
        """Initialize gate with optional runtime override.

        Args:
            repo_root: Path to repository root (for loading config)
            runtime_override: CLI --strictness flag value (highest precedence)
        """
        self.repo_root = repo_root
        self.runtime_override = runtime_override

    def process(
        self,
        context: PrimitiveExecutionContext,
    ) -> PrimitiveExecutionContext:
        """Evaluate conflicts and block if necessary.

        Args:
            context: Execution context (must have conflicts populated by SemanticCheckMiddleware)

        Returns:
            Unmodified context if generation is allowed to proceed

        Raises:
            BlockedByConflict: When strictness policy requires blocking

        Side effects:
            - Stores effective_strictness in context
            - Emits GenerationBlockedBySemanticConflict event (if blocking)
        """
        from .strictness import (
            resolve_strictness,
            should_block,
            Strictness,
            load_global_strictness,
        )
        from .exceptions import BlockedByConflict
        from .events import emit_generation_blocked_event

        # Get conflicts from context (populated by SemanticCheckMiddleware)
        conflicts = getattr(context, "conflicts", [])

        # Resolve effective strictness
        global_default = Strictness.MEDIUM
        if self.repo_root:
            global_default = load_global_strictness(self.repo_root)

        # Get mission and step overrides from context
        mission_strictness = getattr(context, "mission_strictness", None)
        step_strictness = getattr(context, "step_strictness", None)

        effective_strictness = resolve_strictness(
            global_default=global_default,
            mission_override=mission_strictness,
            step_override=step_strictness,
            runtime_override=self.runtime_override,
        )

        # Store effective strictness in context for observability
        context.effective_strictness = effective_strictness

        # Evaluate blocking decision
        if should_block(effective_strictness, conflicts):
            # Get step and mission IDs from context
            step_id = getattr(context, "step_id", "unknown")
            mission_id = getattr(context, "mission_id", "unknown")
            run_id = getattr(context, "run_id", "unknown")

            # WP07: CHECKPOINT BEFORE BLOCKING
            # Emit checkpoint event first so state is persisted before
            # the pipeline halts. If checkpoint emission fails, log and
            # continue -- blocking must never be bypassed.
            try:
                from .checkpoint import create_checkpoint
                from .events import emit_step_checkpointed

                scope_refs = self._build_scope_refs(context)
                inputs = getattr(context, "inputs", {})

                checkpoint = create_checkpoint(
                    mission_id=mission_id,
                    run_id=run_id,
                    step_id=step_id,
                    strictness=effective_strictness,
                    scope_refs=scope_refs,
                    inputs=inputs,
                    cursor="pre_generation_gate",
                )

                emit_step_checkpointed(
                    checkpoint,
                    project_root=self.repo_root,
                )

                # Store checkpoint in context for downstream access
                context.checkpoint = checkpoint
                # Keep token on context for resume middleware compatibility.
                context.retry_token = checkpoint.retry_token
                # Backward-compat field used by some callers/tests.
                context.checkpoint_token = checkpoint.retry_token
            except Exception as ckpt_err:
                import logging

                _logger = logging.getLogger(__name__)
                _logger.error(
                    "Failed to emit checkpoint (blocking proceeds): %s",
                    ckpt_err,
                )

            # Emit generation-blocked event AFTER checkpoint.
            # Guard: if emission fails, log the error but ALWAYS proceed
            # to raise BlockedByConflict -- blocking must never be bypassed.
            try:
                emit_generation_blocked_event(
                    step_id=step_id,
                    mission_id=mission_id,
                    conflicts=conflicts,
                    strictness_mode=effective_strictness,
                    run_id=run_id,
                    repo_root=self.repo_root,
                )
            except Exception as emit_err:
                import logging

                _logger = logging.getLogger(__name__)
                _logger.error(
                    "Failed to emit generation-blocked event (blocking proceeds): %s",
                    emit_err,
                )

            # Block generation by raising exception
            raise BlockedByConflict(
                conflicts=conflicts,
                strictness=effective_strictness,
                message=self._format_block_message(conflicts),
            )

        # Generation allowed - return context unchanged
        return context

    def _build_scope_refs(
        self,
        context: PrimitiveExecutionContext,
    ) -> list[Any]:
        """Build scope refs from context's active glossary scopes.

        Args:
            context: Execution context with optional active_scopes field

        Returns:
            List of ScopeRef instances for checkpoint
        """
        from .checkpoint import ScopeRef
        from .scope import GlossaryScope

        active_scopes = getattr(context, "active_scopes", None)
        if not active_scopes:
            return []

        refs = []
        for scope_val, version in active_scopes.items():
            if isinstance(scope_val, GlossaryScope):
                refs.append(ScopeRef(scope=scope_val, version_id=version))
            else:
                # Try to convert string to GlossaryScope
                try:  # noqa: SIM105
                    refs.append(ScopeRef(scope=GlossaryScope(scope_val), version_id=version))
                except ValueError:
                    pass  # Skip unknown scopes
        return refs

    def _format_block_message(
        self,
        conflicts: list[models.SemanticConflict],
    ) -> str:
        """Format user-facing error message for blocked generation.

        Args:
            conflicts: List of conflicts that caused blocking

        Returns:
            Formatted error message with conflict count and severity breakdown
        """
        from . import models

        high_severity = [c for c in conflicts if c.severity == models.Severity.HIGH]
        conflict_count = len(conflicts)
        high_count = len(high_severity)

        if high_count > 0:
            return (
                f"Generation blocked: {high_count} high-severity "
                f"semantic conflict(s) detected (out of {conflict_count} total). "
                f"Resolve conflicts before proceeding."
            )
        else:
            return (
                f"Generation blocked: {conflict_count} unresolved "
                f"semantic conflict(s) detected. Resolve conflicts before proceeding."
            )


class ResumeMiddleware:
    """Checkpoint/resume middleware for cross-session recovery (WP07).

    This middleware orchestrates:
    1. Loading the latest checkpoint for the current step from the event log
    2. Verifying the input hash to detect context changes
    3. Prompting user for confirmation if context has changed
    4. Restoring execution state from checkpoint (strictness, scopes, cursor)

    Pipeline position: Layer 5 (before re-running generation gate on retry)

    Usage:
        resume = ResumeMiddleware(project_root=Path("."))
        context = resume.process(context)
    """

    def __init__(
        self,
        project_root: Path,
        confirm_fn: Any = None,
    ) -> None:
        """Initialize resume middleware.

        Args:
            project_root: Repository root (for event log access)
            confirm_fn: Optional confirmation function override for
                        context-change prompts. Signature:
                        (old_hash: str, new_hash: str) -> bool.
        """
        self.project_root = project_root
        self.confirm_fn = confirm_fn

    def process(
        self,
        context: PrimitiveExecutionContext,
    ) -> PrimitiveExecutionContext:
        """Load checkpoint, verify context, restore state, resume execution.

        Args:
            context: Primitive execution context (may have retry_token set)

        Returns:
            Restored context if checkpoint found and verified,
            original context if no checkpoint (fresh execution)

        Raises:
            AbortResume: If user declines context change confirmation
        """
        import logging

        from .checkpoint import handle_context_change, load_checkpoint
        from .exceptions import AbortResume

        _logger = logging.getLogger(__name__)

        # Check if this is a resume attempt (retry_token present)
        retry_token = getattr(context, "retry_token", None)
        if not retry_token:
            retry_token = getattr(context, "checkpoint_token", None)
        if not retry_token:
            # Fresh execution, no resume needed
            return context

        step_id = getattr(context, "step_id", "unknown")
        mission_id = getattr(context, "mission_id", None)

        # Load checkpoint from event log
        checkpoint = load_checkpoint(
            self.project_root,
            step_id=step_id,
            mission_id=mission_id,
            retry_token=retry_token,
        )

        if checkpoint is None:
            # No checkpoint found, treat as fresh execution
            _logger.warning(
                "Checkpoint not found for step=%s, treating as fresh execution",
                step_id,
            )
            return context

        # Verify input context hasn't changed
        inputs = getattr(context, "inputs", {})
        if not handle_context_change(checkpoint, inputs, confirm_fn=self.confirm_fn):
            # User declined resumption
            raise AbortResume("User declined resumption due to context change")

        # Restore context from checkpoint
        self._restore_context(context, checkpoint)

        # Mark as resumed for downstream middleware
        context.resumed_from_checkpoint = True

        _logger.info(
            "Resumed from checkpoint: step=%s cursor=%s",
            step_id,
            checkpoint.cursor,
        )

        return context

    def _restore_context(
        self,
        context: PrimitiveExecutionContext,
        checkpoint: StepCheckpoint,
    ) -> None:
        """Restore execution context from checkpoint state.

        Updates context fields with checkpoint values to recreate the
        execution state at the time of checkpoint.

        Args:
            context: Context to restore into
            checkpoint: Checkpoint with saved state
        """
        # Restore strictness
        context.strictness = checkpoint.strictness

        # Restore scope refs as active_scopes dict
        context.active_scopes = {ref.scope: ref.version_id for ref in checkpoint.scope_refs}

        # Store checkpoint cursor for pipeline resumption
        context.checkpoint_cursor = checkpoint.cursor

        # Store retry token for idempotency
        context.retry_token = checkpoint.retry_token
