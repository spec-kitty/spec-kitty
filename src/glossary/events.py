"""Event emission adapters for Feature 007 glossary events.

This module can persist events through two paths:

1) Preferred (when available): canonical `spec-kitty-events` append adapter.
2) Fallback (always available): local JSONL append under `.kittify/events/glossary/`.

Unlike earlier implementations, fallback mode still persists events to JSONL
so checkpoint/resume and local observability remain deterministic even when
canonical contracts are unavailable in the installed package version.

Event classes:
- GlossaryScopeActivated
- TermCandidateObserved
- SemanticCheckEvaluated
- GlossaryClarificationRequested
- GlossaryClarificationResolved
- GlossarySenseUpdated
- GenerationBlockedBySemanticConflict
- StepCheckpointed

Event log format: .kittify/events/glossary/{mission_id}.events.jsonl
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from pathlib import Path
from typing import Any
from collections.abc import Iterator

from glossary.semantic_events import (
    EVT_GLOSSARY_CLARIFICATION_REQUESTED,
    EVT_GLOSSARY_CLARIFICATION_RESOLVED,
    EVT_GLOSSARY_SENSE_UPDATED,
    EVT_SEMANTIC_CHECK_EVALUATED,
)
from kernel.clock import now_utc_iso

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Import adapters: try spec-kitty-events package, fall back to local JSONL only
# ---------------------------------------------------------------------------

_CanonicGlossaryScopeActivated: Any = None
_CanonicTermCandidateObserved: Any = None
_CanonicSemanticCheckEvaluated: Any = None
_CanonicGlossaryClarificationRequested: Any = None
_CanonicGlossaryClarificationResolved: Any = None
# Note: _CanonicGlossarySenseUpdated is intentionally not imported — GlossarySenseUpdated
# is local-only and must not reach the canonical SaaS queue (spec-kitty #1549).
_CanonicGenerationBlockedBySemanticConflict: Any = None
_CanonicStepCheckpointed: Any = None
_pkg_append_event: Any = None

try:
    from spec_kitty_events.glossary.events import (  # type: ignore[import-not-found]
        GlossaryScopeActivated as _CanonicGlossaryScopeActivated,
        TermCandidateObserved as _CanonicTermCandidateObserved,
        SemanticCheckEvaluated as _CanonicSemanticCheckEvaluated,
        GlossaryClarificationRequested as _CanonicGlossaryClarificationRequested,
        GlossaryClarificationResolved as _CanonicGlossaryClarificationResolved,
        GenerationBlockedBySemanticConflict as _CanonicGenerationBlockedBySemanticConflict,
        StepCheckpointed as _CanonicStepCheckpointed,
    )
    from spec_kitty_events.persistence import append_event as _pkg_append_event  # type: ignore[import-not-found]

    EVENTS_AVAILABLE = True
    logger.info("spec-kitty-events canonical glossary adapter available")

except ImportError:
    EVENTS_AVAILABLE = False
    logger.debug("spec-kitty-events canonical glossary adapter unavailable")


# ---------------------------------------------------------------------------
# Event log path resolution
# ---------------------------------------------------------------------------


def _sanitize_mission_id(mission_id: str) -> str:
    """Sanitize mission ID for use as filename.

    Replaces path separators and special characters with hyphens.

    Args:
        mission_id: Raw mission identifier

    Returns:
        Filesystem-safe mission ID string
    """
    return re.sub(r"[^a-zA-Z0-9_\-.]", "-", mission_id)


def get_event_log_path(
    repo_root: Path,
    mission_id: str,
) -> Path:
    """Get event log path for a mission.

    Creates the parent directory if it does not exist.

    Args:
        repo_root: Repository root
        mission_id: Mission identifier

    Returns:
        Path to mission's event log file
    """
    events_dir = repo_root / ".kittify" / "events" / "glossary"
    events_dir.mkdir(parents=True, exist_ok=True)

    safe_id = _sanitize_mission_id(mission_id)
    return events_dir / f"{safe_id}.events.jsonl"


# ---------------------------------------------------------------------------
# JSONL persistence
#
# When EVENTS_AVAILABLE: try canonical append path first.
# In all cases: guarantee local JSONL persistence.
# ---------------------------------------------------------------------------


def append_event(event_dict: dict[str, Any], event_log_path: Path) -> None:
    """Append a single event dict to a JSONL event log.

    This function guarantees local JSONL persistence. When canonical
    `spec-kitty-events` append support is available, it is attempted first.
    Any canonical append failure falls back to local JSONL append.

    Args:
        event_dict: JSON-serializable event payload
        event_log_path: Path to the .events.jsonl file
    """
    if EVENTS_AVAILABLE and _pkg_append_event is not None:
        try:
            _pkg_append_event(event_dict, event_log_path)
            return
        except Exception as exc:
            logger.warning(
                "Canonical append failed for %s, using local JSONL fallback: %s",
                event_dict.get("event_type", "UnknownEvent"),
                exc,
            )

    try:
        _local_append_event(event_dict, event_log_path)
    except Exception as exc:
        logger.error(
            "Local append failed for %s: %s",
            event_dict.get("event_type", "UnknownEvent"),
            exc,
        )


def _local_append_event(event_dict: dict[str, Any], event_log_path: Path) -> None:
    """Low-level JSONL append.

    This is used by production fallback paths and tests.

    Args:
        event_dict: JSON-serializable event payload
        event_log_path: Path to the .events.jsonl file
    """
    event_log_path.parent.mkdir(parents=True, exist_ok=True)
    with event_log_path.open("a") as f:
        f.write(json.dumps(event_dict, sort_keys=True, default=str) + "\n")


def read_events(
    event_log_path: Path,
    event_type: str | None = None,
) -> Iterator[dict[str, Any]]:
    """Read events from JSONL event log.

    Args:
        event_log_path: Path to event log file
        event_type: Optional filter by event type (e.g., "StepCheckpointed")

    Yields:
        Event payloads as dictionaries
    """
    if not event_log_path.exists():
        return

    with open(event_log_path) as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue

            try:
                event = json.loads(stripped)
            except json.JSONDecodeError as e:
                logger.warning("Skipping malformed event line: %s", e)
                continue

            if event_type and event.get("event_type") != event_type:
                continue

            yield event


# ---------------------------------------------------------------------------
# Event payload builders (plain dicts -- always used for return values)
# ---------------------------------------------------------------------------


def build_glossary_scope_activated(
    scope_id: str,
    glossary_version_id: str,
    mission_id: str,
    run_id: str,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Build GlossaryScopeActivated event payload.

    Args:
        scope_id: Glossary scope (e.g., "team_domain")
        glossary_version_id: Glossary version (e.g., "v3")
        mission_id: Mission identifier
        run_id: Run identifier
        timestamp: ISO timestamp (default: now)

    Returns:
        JSON-serializable event dict
    """
    # canonical-producer-exempt: #1200 -- local-only glossary JSONL fallback.
    return {
        "event_type": "GlossaryScopeActivated",
        "scope_id": scope_id,
        "glossary_version_id": glossary_version_id,
        "mission_id": mission_id,
        "run_id": run_id,
        "timestamp": timestamp or now_utc_iso(),
    }


def build_term_candidate_observed(
    term: str,
    source_step: str,
    actor_id: str,
    confidence: float,
    extraction_method: str,
    context: str,
    mission_id: str,
    run_id: str,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Build TermCandidateObserved event payload.

    Args:
        term: Extracted term surface text
        source_step: Step that produced the term
        actor_id: Actor who triggered extraction
        confidence: Extraction confidence (0.0-1.0)
        extraction_method: Method used (metadata_hint, casing_pattern, etc.)
        context: Where the term was found
        mission_id: Mission identifier
        run_id: Run identifier
        timestamp: ISO timestamp (default: now)

    Returns:
        JSON-serializable event dict
    """
    # canonical-producer-exempt: #1200 -- local-only glossary JSONL fallback.
    return {
        "event_type": "TermCandidateObserved",
        "term": term,
        "source_step": source_step,
        "actor_id": actor_id,
        "confidence": confidence,
        "extraction_method": extraction_method,
        "context": context,
        "mission_id": mission_id,
        "run_id": run_id,
        "timestamp": timestamp or now_utc_iso(),
    }


def build_semantic_check_evaluated(
    step_id: str,
    mission_id: str,
    run_id: str,
    findings: list[dict[str, Any]],
    overall_severity: str,
    confidence: float,
    effective_strictness: str,
    recommended_action: str,
    blocked: bool,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Build SemanticCheckEvaluated event payload.

    Args:
        step_id: Step identifier
        mission_id: Mission identifier
        run_id: Run identifier
        findings: List of conflict finding dicts
        overall_severity: Max severity ("low", "medium", "high")
        confidence: Overall confidence
        effective_strictness: Resolved strictness ("off", "medium", "max")
        recommended_action: Recommended action ("proceed", "warn", "block")
        blocked: Whether generation was blocked
        timestamp: ISO timestamp (default: now)

    Returns:
        JSON-serializable event dict
    """
    # canonical-producer-exempt: #1200 -- local-only glossary JSONL fallback.
    return {
        "event_type": EVT_SEMANTIC_CHECK_EVALUATED,
        "step_id": step_id,
        "mission_id": mission_id,
        "run_id": run_id,
        "findings": findings,
        "overall_severity": overall_severity,
        "confidence": confidence,
        "effective_strictness": effective_strictness,
        "recommended_action": recommended_action,
        "blocked": blocked,
        "timestamp": timestamp or now_utc_iso(),
    }


def build_generation_blocked(
    step_id: str,
    mission_id: str,
    run_id: str,
    conflicts: list[dict[str, Any]],
    strictness_mode: str,
    effective_strictness: str,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Build GenerationBlockedBySemanticConflict event payload.

    Args:
        step_id: Step identifier
        mission_id: Mission identifier
        run_id: Run identifier
        conflicts: List of conflict finding dicts
        strictness_mode: Strictness mode string
        effective_strictness: Resolved strictness string
        timestamp: ISO timestamp (default: now)

    Returns:
        JSON-serializable event dict
    """
    # canonical-producer-exempt: #1200 -- local-only glossary JSONL fallback.
    return {
        "event_type": "GenerationBlockedBySemanticConflict",
        "step_id": step_id,
        "mission_id": mission_id,
        "run_id": run_id,
        "conflicts": conflicts,
        "strictness_mode": strictness_mode,
        "effective_strictness": effective_strictness,
        "timestamp": timestamp or now_utc_iso(),
    }


def build_clarification_requested(
    question: str,
    term: str,
    options: list[str],
    urgency: str,
    mission_id: str,
    run_id: str,
    step_id: str,
    conflict_id: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Build GlossaryClarificationRequested event payload.

    Args:
        question: Human-readable clarification question
        term: Term requiring clarification
        options: Ranked candidate definitions
        urgency: Urgency level ("low", "medium", "high")
        mission_id: Mission identifier
        run_id: Run identifier
        step_id: Step identifier
        conflict_id: UUID tracking ID (auto-generated if None)
        timestamp: ISO timestamp (default: now)

    Returns:
        JSON-serializable event dict
    """
    # canonical-producer-exempt: #1200 -- local-only glossary JSONL fallback.
    return {
        "event_type": EVT_GLOSSARY_CLARIFICATION_REQUESTED,
        "question": question,
        "term": term,
        "options": options,
        "urgency": urgency,
        "mission_id": mission_id,
        "run_id": run_id,
        "step_id": step_id,
        "conflict_id": conflict_id or str(uuid.uuid4()),
        "timestamp": timestamp or now_utc_iso(),
    }


def build_clarification_resolved(
    conflict_id: str,
    term_surface: str,
    selected_sense: dict[str, Any],
    actor: dict[str, Any],
    resolution_mode: str,
    provenance: dict[str, Any],
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Build GlossaryClarificationResolved event payload.

    Args:
        conflict_id: UUID from the requesting event
        term_surface: Term that was clarified
        selected_sense: Selected SenseRef dict
        actor: ActorIdentity dict
        resolution_mode: "interactive" or "async"
        provenance: Provenance dict
        timestamp: ISO timestamp (default: now)

    Returns:
        JSON-serializable event dict
    """
    # canonical-producer-exempt: #1200 -- local-only glossary JSONL fallback.
    return {
        "event_type": EVT_GLOSSARY_CLARIFICATION_RESOLVED,
        "conflict_id": conflict_id,
        "term_surface": term_surface,
        "selected_sense": selected_sense,
        "actor": actor,
        "resolution_mode": resolution_mode,
        "provenance": provenance,
        "timestamp": timestamp or now_utc_iso(),
    }


def build_sense_updated(
    term_surface: str,
    scope: str,
    new_sense: dict[str, Any],
    actor: dict[str, Any],
    update_type: str,
    provenance: dict[str, Any],
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Build GlossarySenseUpdated event payload.

    Args:
        term_surface: Term surface text
        scope: Glossary scope (e.g., "team_domain")
        new_sense: New TermSense dict
        actor: ActorIdentity dict
        update_type: "create" or "update"
        provenance: Provenance dict
        timestamp: ISO timestamp (default: now)

    Returns:
        JSON-serializable event dict
    """
    # canonical-producer-exempt: #1200 -- local-only glossary JSONL fallback.
    return {
        "event_type": EVT_GLOSSARY_SENSE_UPDATED,
        "term_surface": term_surface,
        "scope": scope,
        "new_sense": new_sense,
        "actor": actor,
        "update_type": update_type,
        "provenance": provenance,
        "timestamp": timestamp or now_utc_iso(),
    }


def build_step_checkpointed(
    mission_id: str,
    run_id: str,
    step_id: str,
    strictness: str,
    scope_refs: list[dict[str, str]],
    input_hash: str,
    cursor: str,
    retry_token: str,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Build StepCheckpointed event payload.

    Args:
        mission_id: Mission identifier
        run_id: Run identifier
        step_id: Step identifier
        strictness: Strictness mode string
        scope_refs: List of scope ref dicts
        input_hash: SHA256 of step inputs
        cursor: Execution stage
        retry_token: UUID for idempotency
        timestamp: ISO timestamp (default: now)

    Returns:
        JSON-serializable event dict
    """
    # canonical-producer-exempt: #1200 -- local-only glossary JSONL fallback.
    return {
        "event_type": "StepCheckpointed",
        "mission_id": mission_id,
        "run_id": run_id,
        "step_id": step_id,
        "strictness": strictness,
        "scope_refs": scope_refs,
        "input_hash": input_hash,
        "cursor": cursor,
        "retry_token": retry_token,
        "timestamp": timestamp or now_utc_iso(),
    }


# ---------------------------------------------------------------------------
# Canonical event persistence
#
# When EVENTS_AVAILABLE is True:
#   - Instantiate the canonical event class from spec-kitty-events
#   - Pass that INSTANCE (not a dict) to _pkg_append_event
#
# When canonical persistence fails or is unavailable:
#   - Fall back to deterministic local JSONL append.
# ---------------------------------------------------------------------------


def _persist_event(
    event_dict: dict[str, Any],
    repo_root: Path,
    mission_id: str,
    canonical_cls: Any = None,
) -> None:
    """Persist an event to the event log.

    Behavior:
    - Try canonical adapter if available and a canonical class is provided.
    - Fall back to local JSONL append on any failure.

    Args:
        event_dict: JSON-serializable event payload (used both for
                    constructing canonical instances and as the return value)
        repo_root: Repository root for event log path
        mission_id: Mission identifier for JSONL file
        canonical_cls: Canonical event class constructor (optional)
    """
    try:
        event_log_path = get_event_log_path(repo_root, mission_id)
    except Exception as exc:
        logger.error(
            "Failed to resolve event log path for %s (mission=%s): %s",
            event_dict.get("event_type", "UnknownEvent"),
            mission_id,
            exc,
        )
        return
    event_dict.setdefault("event_id", str(uuid.uuid4()))

    if EVENTS_AVAILABLE and _pkg_append_event is not None and canonical_cls is not None:
        try:
            canonical_instance = canonical_cls(**event_dict)
            _pkg_append_event(canonical_instance, event_log_path)
            return
        except Exception as exc:
            logger.warning(
                "Canonical persistence failed for %s, using local JSONL fallback: %s",
                event_dict.get("event_type", "UnknownEvent"),
                exc,
            )

    try:
        _local_append_event(event_dict, event_log_path)
    except Exception as exc:
        logger.error(
            "Local persistence failed for %s: %s",
            event_dict.get("event_type", "UnknownEvent"),
            exc,
        )


# ---------------------------------------------------------------------------
# High-level emission functions used by middleware
# ---------------------------------------------------------------------------


def _serialize_conflicts(
    conflicts: list[Any],
) -> list[dict[str, Any]]:
    """Serialize conflict objects to dicts for event payloads.

    Args:
        conflicts: List of SemanticConflict dataclass instances

    Returns:
        List of JSON-serializable conflict dicts
    """
    from .models import semantic_conflict_to_dict

    result: list[dict[str, Any]] = []
    for c in conflicts:
        result.append(semantic_conflict_to_dict(c))
    return result


def emit_term_candidate_observed(
    term: Any,
    context: Any,
    repo_root: Path | None = None,
) -> dict[str, Any] | None:
    """Emit TermCandidateObserved event for an extracted term.

    When EVENTS_AVAILABLE is True and repo_root is provided:
        Creates a _CanonicTermCandidateObserved instance and persists it.
    When EVENTS_AVAILABLE is False:
        Logs the event payload via logger.info. No file I/O.

    Args:
        term: ExtractedTerm instance
        context: PrimitiveExecutionContext (must have step_id, mission_id, etc.)
        repo_root: Repository root (for event log path). If None, log only.

    Returns:
        Event dict if emitted, None if emission failed
    """
    step_id = getattr(context, "step_id", "unknown")
    mission_id = getattr(context, "mission_id", "unknown")
    run_id = getattr(context, "run_id", "unknown")
    actor_id = getattr(context, "actor_id", "unknown")

    event = build_term_candidate_observed(
        term=term.surface,
        source_step=step_id,
        actor_id=actor_id,
        confidence=term.confidence,
        extraction_method=term.source,
        context=f"source: {term.source}",
        mission_id=mission_id,
        run_id=run_id,
    )

    try:
        if repo_root is not None:
            _persist_event(event, repo_root, mission_id, canonical_cls=_CanonicTermCandidateObserved)
        else:
            logger.info("glossary.TermCandidateObserved: term=%s", term.surface)
    except Exception as exc:
        logger.error("Failed to emit TermCandidateObserved: %s", exc)
        return None

    return event


def emit_semantic_check_evaluated(
    context: Any,
    conflicts: list[Any],
    effective_strictness: str | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any] | None:
    """Emit SemanticCheckEvaluated event.

    When EVENTS_AVAILABLE is True and repo_root is provided:
        Creates a _CanonicSemanticCheckEvaluated instance and persists it.
    When EVENTS_AVAILABLE is False:
        Logs the event payload via logger.info. No file I/O.

    Args:
        context: PrimitiveExecutionContext
        conflicts: List of SemanticConflict instances
        effective_strictness: Resolved strictness string
        repo_root: Repository root (for event log path). If None, log only.

    Returns:
        Event dict if emitted, None if emission failed
    """
    step_id = getattr(context, "step_id", "unknown")
    mission_id = getattr(context, "mission_id", "unknown")
    run_id = getattr(context, "run_id", "unknown")

    # Compute overall severity
    if conflicts:
        from .models import Severity

        severities = [c.severity for c in conflicts]
        if Severity.HIGH in severities:
            overall = "high"
        elif Severity.MEDIUM in severities:
            overall = "medium"
        else:
            overall = "low"

        overall_confidence = max(c.confidence for c in conflicts)
    else:
        overall = "low"
        overall_confidence = 1.0

    # Determine recommended action
    if not conflicts:
        recommended = "proceed"
    elif overall == "high":
        recommended = "block"
    else:
        recommended = "warn"

    # The semantic-check middleware emits before the generation gate resolves
    # strictness, so the context can still carry None: write the default rather
    # than the string "None" (#6399).
    eff_str_raw: Any = effective_strictness or getattr(context, "effective_strictness", None) or "medium"
    eff_str: str = eff_str_raw.value if hasattr(eff_str_raw, "value") else str(eff_str_raw)

    blocked = len(conflicts) > 0 and eff_str != "off"

    event = build_semantic_check_evaluated(
        step_id=step_id,
        mission_id=mission_id,
        run_id=run_id,
        findings=_serialize_conflicts(conflicts),
        overall_severity=overall,
        confidence=overall_confidence,
        effective_strictness=eff_str,
        recommended_action=recommended,
        blocked=blocked,
    )

    try:
        if repo_root is not None:
            _persist_event(event, repo_root, mission_id, canonical_cls=_CanonicSemanticCheckEvaluated)
        else:
            logger.info("glossary.SemanticCheckEvaluated: findings=%d", len(conflicts))
    except Exception as exc:
        logger.error("Failed to emit SemanticCheckEvaluated: %s", exc)
        return None

    # Keep the latest semantic check reference on context for downstream
    # clarification events.
    if event is not None:
        context.semantic_check_event_id = event.get("event_id")

    return event


def emit_generation_blocked_event(
    step_id: str,
    mission_id: str,
    conflicts: list[Any],
    strictness_mode: Any,
    run_id: str | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any] | None:
    """Emit GenerationBlockedBySemanticConflict event.

    When EVENTS_AVAILABLE is True and repo_root is provided:
        Creates a _CanonicGenerationBlockedBySemanticConflict instance and persists it.
    When EVENTS_AVAILABLE is False:
        Logs the event payload via logger.info. No file I/O.

    Args:
        step_id: Step identifier
        mission_id: Mission identifier
        conflicts: List of SemanticConflict instances
        strictness_mode: Strictness enum or string
        run_id: Run identifier
        repo_root: Repository root (for event log path). If None, log only.

    Returns:
        Event dict if emitted, None if emission failed
    """
    mode_str = strictness_mode.value if hasattr(strictness_mode, "value") else str(strictness_mode)

    event = build_generation_blocked(
        step_id=step_id,
        mission_id=mission_id,
        run_id=run_id or "unknown",
        conflicts=_serialize_conflicts(conflicts),
        strictness_mode=mode_str,
        effective_strictness=mode_str,
    )

    try:
        if repo_root is not None:
            _persist_event(event, repo_root, mission_id, canonical_cls=_CanonicGenerationBlockedBySemanticConflict)
        else:
            logger.info(
                "glossary.GenerationBlockedBySemanticConflict: conflicts=%d, strictness=%s, step=%s, mission=%s",
                len(conflicts),
                mode_str,
                step_id,
                mission_id,
            )
    except Exception as exc:
        logger.error("Failed to emit GenerationBlockedBySemanticConflict: %s", exc)
        return None

    return event


def emit_step_checkpointed(
    checkpoint: Any,
    project_root: Path | None = None,
) -> dict[str, Any] | None:
    """Emit StepCheckpointed event to event log.

    When EVENTS_AVAILABLE is True and project_root is provided:
        Creates a _CanonicStepCheckpointed instance and persists it.
    When EVENTS_AVAILABLE is False:
        Logs the event payload via logger.info. No file I/O.

    Args:
        checkpoint: StepCheckpoint instance
        project_root: Repository root for event log storage. If None,
                      only logs (useful for testing without filesystem).

    Returns:
        Event dict if emitted, None if emission failed
    """
    from .checkpoint import checkpoint_to_dict

    # Build standardized event from checkpoint data
    ckpt_dict = checkpoint_to_dict(checkpoint)
    event = build_step_checkpointed(
        mission_id=ckpt_dict["mission_id"],
        run_id=ckpt_dict["run_id"],
        step_id=ckpt_dict["step_id"],
        strictness=ckpt_dict["strictness"],
        scope_refs=ckpt_dict["scope_refs"],
        input_hash=ckpt_dict["input_hash"],
        cursor=ckpt_dict["cursor"],
        retry_token=ckpt_dict["retry_token"],
        timestamp=ckpt_dict["timestamp"],
    )

    logger.info(
        "Checkpoint emitted: step=%s, cursor=%s, hash=%s...",
        checkpoint.step_id,
        checkpoint.cursor,
        checkpoint.input_hash[:8],
    )

    try:
        if project_root is not None:
            _persist_event(event, project_root, checkpoint.mission_id, canonical_cls=_CanonicStepCheckpointed)
        else:
            logger.info(
                "glossary.StepCheckpointed: step=%s, cursor=%s (no repo_root)",
                checkpoint.step_id,
                checkpoint.cursor,
            )
    except Exception as exc:
        logger.error("Failed to persist StepCheckpointed event: %s", exc)
        return None

    return event


def emit_clarification_requested(
    conflict: Any,
    context: Any,
    conflict_id: str | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any] | None:
    """Emit GlossaryClarificationRequested event.

    When EVENTS_AVAILABLE is True and repo_root is provided:
        Creates a _CanonicGlossaryClarificationRequested instance and persists it.
    When EVENTS_AVAILABLE is False:
        Logs the event payload via logger.info. No file I/O.

    Args:
        conflict: SemanticConflict instance
        context: PrimitiveExecutionContext
        conflict_id: UUID for tracking (auto-generated if None)
        repo_root: Repository root (for event log path). If None, log only.

    Returns:
        Event dict if emitted, None if emission failed
    """
    step_id = getattr(context, "step_id", "unknown")
    mission_id = getattr(context, "mission_id", "unknown")
    run_id = getattr(context, "run_id", "unknown")

    cid = conflict_id or str(uuid.uuid4())
    options = [s.definition for s in conflict.candidate_senses] if conflict.candidate_senses else []
    urgency = conflict.severity.value if hasattr(conflict.severity, "value") else str(conflict.severity)

    event = build_clarification_requested(
        question=f"What does '{conflict.term.surface_text}' mean in this context?",
        term=conflict.term.surface_text,
        options=options,
        urgency=urgency,
        mission_id=mission_id,
        run_id=run_id,
        step_id=step_id,
        conflict_id=cid,
    )
    # Reference the preceding semantic check only when there was one; the
    # contract makes the field optional but never empty (#6399).
    semantic_check_event_id = getattr(context, "semantic_check_event_id", None)
    if semantic_check_event_id:
        event["semantic_check_event_id"] = semantic_check_event_id

    try:
        if repo_root is not None:
            _persist_event(event, repo_root, mission_id, canonical_cls=_CanonicGlossaryClarificationRequested)
        else:
            logger.info("glossary.GlossaryClarificationRequested: term=%s", conflict.term.surface_text)
    except Exception as exc:
        logger.error("Failed to emit GlossaryClarificationRequested: %s", exc)
        return None

    return event


def emit_clarification_resolved(
    conflict_id: str,
    conflict: Any,
    selected_sense: Any,
    context: Any,
    resolution_mode: str = "interactive",
    repo_root: Path | None = None,
) -> dict[str, Any] | None:
    """Emit GlossaryClarificationResolved event.

    When EVENTS_AVAILABLE is True and repo_root is provided:
        Creates a _CanonicGlossaryClarificationResolved instance and persists it.
    When EVENTS_AVAILABLE is False:
        Logs the event payload via logger.info. No file I/O.

    Args:
        conflict_id: UUID from the requesting event
        conflict: SemanticConflict instance
        selected_sense: SenseRef that was selected
        context: PrimitiveExecutionContext
        resolution_mode: "interactive" or "async"
        repo_root: Repository root (for event log path). If None, log only.

    Returns:
        Event dict if emitted, None if emission failed
    """
    mission_id = getattr(context, "mission_id", "unknown")
    actor_id = getattr(context, "actor_id", "unknown")

    ts = now_utc_iso()

    event = build_clarification_resolved(
        conflict_id=conflict_id,
        term_surface=conflict.term.surface_text,
        selected_sense={
            "surface": selected_sense.surface,
            "scope": selected_sense.scope,
            "definition": selected_sense.definition,
            "confidence": selected_sense.confidence,
        },
        actor={
            "actor_id": actor_id,
            "actor_type": "human",
            "display_name": actor_id,
        },
        resolution_mode=resolution_mode,
        provenance={
            "source": "user_clarification",
            "timestamp": ts,
            "actor_id": actor_id,
        },
    )

    try:
        if repo_root is not None:
            _persist_event(event, repo_root, mission_id, canonical_cls=_CanonicGlossaryClarificationResolved)
        else:
            logger.info("glossary.GlossaryClarificationResolved: term=%s", conflict.term.surface_text)
    except Exception as exc:
        logger.error("Failed to emit GlossaryClarificationResolved: %s", exc)
        return None

    return event


def emit_sense_updated(
    conflict: Any,
    custom_definition: str,
    scope_value: str,
    context: Any,
    update_type: str = "create",
    repo_root: Path | None = None,
) -> dict[str, Any] | None:
    """Emit GlossarySenseUpdated event.

    When EVENTS_AVAILABLE is True and repo_root is provided:
        Creates a _CanonicGlossarySenseUpdated instance and persists it.
    When EVENTS_AVAILABLE is False:
        Logs the event payload via logger.info. No file I/O.

    Args:
        conflict: SemanticConflict instance
        custom_definition: Custom sense definition text
        scope_value: Glossary scope string (e.g., "team_domain")
        context: PrimitiveExecutionContext
        update_type: "create" or "update"
        repo_root: Repository root (for event log path). If None, log only.

    Returns:
        Event dict if emitted, None if emission failed
    """
    mission_id = getattr(context, "mission_id", "unknown")
    actor_id = getattr(context, "actor_id", "unknown")

    ts = now_utc_iso()

    event = build_sense_updated(
        term_surface=conflict.term.surface_text,
        scope=scope_value,
        new_sense={
            "surface": conflict.term.surface_text,
            "scope": scope_value,
            "definition": custom_definition,
            "confidence": 1.0,
            "status": "active",
        },
        actor={
            "actor_id": actor_id,
            "actor_type": "human",
            "display_name": actor_id,
        },
        update_type=update_type,
        provenance={
            "source": "user_clarification",
            "timestamp": ts,
            "actor_id": actor_id,
        },
    )

    try:
        if repo_root is not None:
            # GlossarySenseUpdated is local-only — not queued for SaaS delivery (spec-kitty #1549).
            # The seed file is the authoritative current glossary state.
            # Per-extraction noise (hundreds of events per session) must not pollute the SaaS queue.
            event_log_path = get_event_log_path(repo_root, mission_id)
            event.setdefault("event_id", str(uuid.uuid4()))
            _local_append_event(event, event_log_path)
        else:
            logger.info("glossary.GlossarySenseUpdated: term=%s", conflict.term.surface_text)
    except Exception as exc:
        logger.error("Failed to emit GlossarySenseUpdated: %s", exc)
        return None

    return event


def emit_scope_activated(
    scope_id: str,
    glossary_version_id: str,
    mission_id: str,
    run_id: str,
    repo_root: Path | None = None,
) -> dict[str, Any] | None:
    """Emit GlossaryScopeActivated event.

    When EVENTS_AVAILABLE is True and repo_root is provided:
        Creates a _CanonicGlossaryScopeActivated instance and persists it.
    When EVENTS_AVAILABLE is False:
        Logs the event payload via logger.info. No file I/O.

    Args:
        scope_id: Glossary scope (e.g., "team_domain")
        glossary_version_id: Glossary version (e.g., "v3")
        mission_id: Mission identifier
        run_id: Run identifier
        repo_root: Repository root (for event log path). If None, log only.

    Returns:
        Event dict if emitted, None if emission failed
    """
    event = build_glossary_scope_activated(
        scope_id=scope_id,
        glossary_version_id=glossary_version_id,
        mission_id=mission_id,
        run_id=run_id,
    )

    try:
        if repo_root is not None:
            _persist_event(event, repo_root, mission_id, canonical_cls=_CanonicGlossaryScopeActivated)
        else:
            logger.info("glossary.GlossaryScopeActivated: scope=%s", scope_id)
    except Exception as exc:
        logger.error("Failed to emit GlossaryScopeActivated: %s", exc)
        return None

    return event
