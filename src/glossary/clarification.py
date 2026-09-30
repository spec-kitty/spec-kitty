"""Interactive clarification middleware (WP06, WP08).

This module implements the ClarificationMiddleware that handles interactive
conflict resolution. It emits 3 event types at its boundaries:

- GlossaryClarificationRequested: when user defers a conflict
- GlossaryClarificationResolved: when user selects a candidate sense
- GlossarySenseUpdated: when user provides a custom sense definition

Pipeline position: Layer 4 (after extraction, semantic check, and gate)
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from kernel.clock import now_utc

logger = logging.getLogger(__name__)


class ClarificationMiddleware:
    """Middleware for interactive conflict clarification.

    When conflicts are detected and generation is not blocked (or after
    the user resolves a blocking conflict), this middleware handles:

    1. Presenting conflicts to the user for resolution
    2. Accepting user's choice: select a candidate sense OR provide custom
    3. Emitting appropriate events for each resolution action
    4. Updating the execution context with resolved senses

    Usage:
        clarification = ClarificationMiddleware(
            repo_root=Path("."),
            prompt_fn=my_prompt_function,
        )
        context = clarification.process(context)
    """

    def __init__(
        self,
        repo_root: Path | None = None,
        prompt_fn: Any = None,
        glossary_store: Any = None,
    ) -> None:
        """Initialize clarification middleware.

        Args:
            repo_root: Repository root for event log persistence.
                If None, events are logged but not persisted.
            prompt_fn: Optional function to prompt user for resolution.
                Signature: (conflict, candidates) -> (choice: str, custom_def: str | None)
                Returns ("select", None) with index in conflict.selected_index
                or ("custom", "definition text") for custom sense.
                If None, all conflicts are deferred.
            glossary_store: Optional GlossaryStore instance. When provided,
                custom senses are applied in-memory immediately after
                clarification so subsequent checks in the same run see
                updated meanings.
        """
        self.repo_root = repo_root
        self.prompt_fn = prompt_fn
        self.glossary_store = glossary_store

    def process(
        self,
        context: Any,
    ) -> Any:
        """Process conflicts requiring clarification.

        For each unresolved conflict in context.conflicts, either:
        - Prompt user for resolution (if prompt_fn is provided)
        - Defer to async (emit GlossaryClarificationRequested)

        Args:
            context: Execution context with conflicts populated

        Returns:
            Updated context with resolved conflicts removed
        """
        conflicts = getattr(context, "conflicts", [])
        if not conflicts:
            return context

        resolved_conflicts: list[Any] = []

        for conflict in conflicts:
            conflict_id = str(uuid.uuid4())
            # Always emit the request event first so any eventual resolution
            # references an existing clarification request.
            self._emit_requested(conflict, conflict_id, context)

            if self.prompt_fn is not None:
                # Interactive mode: prompt user
                try:
                    choice, custom_def = self.prompt_fn(conflict, conflict.candidate_senses)
                except Exception as exc:
                    logger.error(
                        "Prompt function failed for %s: %s",
                        conflict.term.surface_text,
                        exc,
                    )
                    # Defer on prompt failure
                    continue

                if choice == "select" and conflict.candidate_senses:
                    # User selected a candidate sense
                    selected_idx = getattr(conflict, "selected_index", 0)
                    selected_sense = (
                        conflict.candidate_senses[selected_idx]
                        if 0 <= selected_idx < len(conflict.candidate_senses)
                        else conflict.candidate_senses[0]
                    )
                    self._handle_candidate_selection(conflict, conflict_id, selected_sense, context)
                    resolved_conflicts.append(conflict)
                elif choice == "custom" and custom_def:
                    # User provided custom definition
                    self._handle_custom_sense(conflict, conflict_id, custom_def, context)
                    resolved_conflicts.append(conflict)
                # Any other response means deferred. Request event already emitted.
            # No prompt function means deferred (request event already emitted).

        # Remove resolved conflicts from context
        remaining = [c for c in conflicts if c not in resolved_conflicts]
        context.conflicts = remaining
        context.resolved_conflicts = resolved_conflicts

        return context

    def _emit_requested(
        self,
        conflict: Any,
        conflict_id: str,
        context: Any,
    ) -> None:
        """Emit GlossaryClarificationRequested for a deferred conflict.

        Args:
            conflict: SemanticConflict instance
            conflict_id: UUID tracking ID
            context: PrimitiveExecutionContext
        """
        from .events import emit_clarification_requested

        try:
            emit_clarification_requested(
                conflict=conflict,
                context=context,
                conflict_id=conflict_id,
                repo_root=self.repo_root,
            )
        except Exception as exc:
            logger.error(
                "Failed to emit ClarificationRequested for %s: %s",
                conflict.term.surface_text,
                exc,
            )

    def _handle_candidate_selection(
        self,
        conflict: Any,
        conflict_id: str,
        selected_sense: Any,
        context: Any,
    ) -> None:
        """Handle user selecting a candidate sense.

        Emits GlossaryClarificationResolved event.

        Args:
            conflict: SemanticConflict instance
            conflict_id: UUID from the requesting event
            selected_sense: SenseRef that was selected
            context: PrimitiveExecutionContext
        """
        from .events import emit_clarification_resolved

        try:
            emit_clarification_resolved(
                conflict_id=conflict_id,
                conflict=conflict,
                selected_sense=selected_sense,
                context=context,
                resolution_mode="interactive",
                repo_root=self.repo_root,
            )
        except Exception as exc:
            logger.error(
                "Failed to emit ClarificationResolved for %s: %s",
                conflict.term.surface_text,
                exc,
            )

    def _handle_custom_sense(
        self,
        conflict: Any,
        _conflict_id: str,
        custom_definition: str,
        context: Any,
    ) -> None:
        """Handle user providing a custom sense definition.

        Emits GlossarySenseUpdated event.

        Args:
            conflict: SemanticConflict instance
            conflict_id: UUID from the requesting event
            custom_definition: Custom definition text from user
            context: PrimitiveExecutionContext
        """
        from .events import emit_sense_updated
        from .models import Provenance, SenseStatus, TermSense

        try:
            emit_sense_updated(
                conflict=conflict,
                custom_definition=custom_definition,
                scope_value="team_domain",
                context=context,
                update_type="create",
                repo_root=self.repo_root,
            )
            if self.glossary_store is not None:
                actor_id = getattr(context, "actor_id", "unknown")
                provenance = Provenance(
                    actor_id=str(actor_id),
                    timestamp=now_utc(),
                    source="user_clarification",
                )
                term_sense = TermSense(
                    surface=conflict.term,
                    scope="team_domain",
                    definition=custom_definition,
                    provenance=provenance,
                    confidence=1.0,
                    status=SenseStatus.ACTIVE,
                )
                self.glossary_store.add_sense(term_sense)
        except Exception as exc:
            logger.error(
                "Failed to emit SenseUpdated for %s: %s",
                conflict.term.surface_text,
                exc,
            )
