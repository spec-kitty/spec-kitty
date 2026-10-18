"""Glossary semantic integrity runtime for mission framework.

Public API
----------
Models:
    TermSurface, TermSense, SemanticConflict, SenseRef, Provenance,
    SenseStatus, ConflictType, Severity

Exceptions:
    GlossaryError, BlockedByConflict, DeferredToAsync, AbortResume

Scopes & Resolution:
    GlossaryScope, resolve_term, GlossaryStore

Conflict Detection:
    classify_conflict, score_severity, create_conflict

Strictness:
    Strictness, resolve_strictness, load_global_strictness,
    should_block, categorize_conflicts

Middleware:
    GlossaryMiddlewarePipeline, GlossaryMiddleware,
    GlossaryCandidateExtractionMiddleware, SemanticCheckMiddleware,
    GenerationGateMiddleware, ResumeMiddleware, ClarificationMiddleware

Checkpoint:
    StepCheckpoint, ScopeRef, compute_input_hash, create_checkpoint,
    verify_input_hash, handle_context_change, load_checkpoint,
    parse_checkpoint_event, checkpoint_to_dict, compute_input_diff

Extraction:
    ExtractedTerm, extract_all_terms

Events:
    get_event_log_path, append_event, read_events,
    emit_term_candidate_observed, emit_semantic_check_evaluated,
    emit_generation_blocked_event, emit_step_checkpointed,
    emit_clarification_requested, emit_clarification_resolved,
    emit_sense_updated, emit_scope_activated

Pipeline:
    create_standard_pipeline, prompt_conflict_resolution_safe

Attachment:
    GlossaryAwarePrimitiveRunner, attach_glossary_pipeline,
    glossary_enabled, read_glossary_check_metadata, run_with_glossary
"""

from __future__ import annotations

from .models import (
    Provenance,
    SenseRef,
    TermSurface,
    TermSense,
    SemanticConflict,
    SenseStatus,
    ConflictType,
    Severity,
)
from .exceptions import (
    GlossaryError,
    BlockedByConflict,
    DeferredToAsync,
    AbortResume,
    SeedValidationError,
    SeedFileValidationError,
)
from .scope import GlossaryScope, load_seed_file, save_seed_file
from .seed_schema import GlossarySeedFile, GlossarySeedTerm
from .seed_validation import validate_seed_file_data, validate_scope_filename
from .store import GlossaryStore
from .resolution import resolve_term
from .extraction import ExtractedTerm, extract_all_terms
from .conflict import classify_conflict, score_severity, create_conflict
from .middleware import (
    GlossaryCandidateExtractionMiddleware,
    SemanticCheckMiddleware,
    GenerationGateMiddleware,
    ResumeMiddleware,
)
from .clarification import ClarificationMiddleware
from .strictness import (
    Strictness,
    resolve_strictness,
    load_global_strictness,
    should_block,
    categorize_conflicts,
)
from .checkpoint import (
    StepCheckpoint,
    ScopeRef,
    compute_input_hash,
    create_checkpoint,
    verify_input_hash,
    handle_context_change,
    load_checkpoint,
    parse_checkpoint_event,
    checkpoint_to_dict,
    compute_input_diff,
)
from .events import (
    get_event_log_path,
    append_event,
    read_events,
    emit_term_candidate_observed,
    emit_semantic_check_evaluated,
    emit_generation_blocked_event,
    emit_step_checkpointed,
    emit_clarification_requested,
    emit_clarification_resolved,
    emit_sense_updated,
    emit_scope_activated,
)
from .pipeline import (
    GlossaryMiddlewarePipeline,
    GlossaryMiddleware,
    create_standard_pipeline,
)
from .attachment import (
    GlossaryAwarePrimitiveRunner,
    attach_glossary_pipeline,
    glossary_enabled,
    read_glossary_check_metadata,
    run_with_glossary,
)
from .pipeline import prompt_conflict_resolution_safe

__all__ = [
    # Models
    "Provenance",
    "SenseRef",
    "TermSurface",
    "TermSense",
    "SemanticConflict",
    "SenseStatus",
    "ConflictType",
    "Severity",
    # Exceptions
    "GlossaryError",
    "BlockedByConflict",
    "DeferredToAsync",
    "AbortResume",
    "SeedValidationError",
    "SeedFileValidationError",
    # Scopes & Resolution
    "GlossaryScope",
    "load_seed_file",
    "save_seed_file",
    # Seed Schema & Validation
    "GlossarySeedFile",
    "GlossarySeedTerm",
    "validate_seed_file_data",
    "validate_scope_filename",
    "GlossaryStore",
    "resolve_term",
    # Extraction
    "ExtractedTerm",
    "extract_all_terms",
    # Conflict Detection
    "classify_conflict",
    "score_severity",
    "create_conflict",
    # Middleware
    "GlossaryCandidateExtractionMiddleware",
    "SemanticCheckMiddleware",
    "GenerationGateMiddleware",
    "ResumeMiddleware",
    "ClarificationMiddleware",
    # Strictness
    "Strictness",
    "resolve_strictness",
    "load_global_strictness",
    "should_block",
    "categorize_conflicts",
    # Checkpoint
    "StepCheckpoint",
    "ScopeRef",
    "compute_input_hash",
    "create_checkpoint",
    "verify_input_hash",
    "handle_context_change",
    "load_checkpoint",
    "parse_checkpoint_event",
    "checkpoint_to_dict",
    "compute_input_diff",
    # Events
    "get_event_log_path",
    "append_event",
    "read_events",
    "emit_term_candidate_observed",
    "emit_semantic_check_evaluated",
    "emit_generation_blocked_event",
    "emit_step_checkpointed",
    "emit_clarification_requested",
    "emit_clarification_resolved",
    "emit_sense_updated",
    "emit_scope_activated",
    # Pipeline
    "GlossaryMiddlewarePipeline",
    "GlossaryMiddleware",
    "create_standard_pipeline",
    "prompt_conflict_resolution_safe",
    # Attachment
    "GlossaryAwarePrimitiveRunner",
    "attach_glossary_pipeline",
    "glossary_enabled",
    "read_glossary_check_metadata",
    "run_with_glossary",
]

__version__ = "0.1.0"
