"""Core data models for glossary semantic integrity."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from kernel.clock import datetime


@dataclass(frozen=True)
class TermSurface:
    """Raw string representation of a term."""

    surface_text: str  # e.g., "workspace"

    def __post_init__(self) -> None:
        # Validate: must be normalized (lowercase, trimmed)
        if self.surface_text != self.surface_text.lower().strip():
            raise ValueError(f"TermSurface must be normalized: {self.surface_text}")


class SenseStatus(Enum):
    """Status of a TermSense."""

    DRAFT = "draft"  # Auto-extracted, low confidence
    ACTIVE = "active"  # Promoted by user or high confidence
    DEPRECATED = "deprecated"  # Kept in history, not in active resolution


@dataclass
class Provenance:
    """Provenance metadata for a TermSense."""

    actor_id: str  # e.g., "user:alice" or "llm:claude-sonnet-4"
    timestamp: datetime
    source: str  # e.g., "user_clarification", "metadata_hint", "auto_extraction"


@dataclass
class TermSense:
    """Meaning of a TermSurface within a specific GlossaryScope."""

    surface: TermSurface
    scope: str  # GlossaryScope enum value (defined in scope.py)
    definition: str
    provenance: Provenance
    confidence: float  # 0.0-1.0
    status: SenseStatus = SenseStatus.DRAFT

    def __post_init__(self) -> None:
        # Validate confidence range
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be 0.0-1.0: {self.confidence}")
        # Validate definition not empty
        if not self.definition.strip():
            raise ValueError("Definition cannot be empty")


class ConflictType(Enum):
    """Type of semantic conflict."""

    UNKNOWN = "unknown"  # No match in any scope
    AMBIGUOUS = "ambiguous"  # Multiple active senses, unqualified usage
    INCONSISTENT = "inconsistent"  # LLM output contradicts active glossary
    UNRESOLVED_CRITICAL = "unresolved_critical"  # Unknown critical term, low confidence


class Severity(Enum):
    """Severity level of a semantic conflict."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class SenseRef:
    """Reference to a TermSense (used in conflict candidates)."""

    surface: str
    scope: str
    definition: str
    confidence: float


@dataclass
class SemanticConflict:
    """Classification of a term conflict."""

    term: TermSurface
    conflict_type: ConflictType
    severity: Severity
    confidence: float  # 0.0-1.0 (confidence in conflict detection)
    candidate_senses: list[SenseRef] = field(default_factory=list)
    context: str = ""  # Usage location (e.g., "step input: description field")

    def __post_init__(self) -> None:
        # Validate: AMBIGUOUS type must have candidates
        if self.conflict_type == ConflictType.AMBIGUOUS and not self.candidate_senses:
            raise ValueError("AMBIGUOUS conflict must have candidate_senses")


# Serialization helpers for event emission


def term_surface_to_dict(ts: TermSurface) -> dict[str, Any]:
    """Serialize TermSurface to dict."""
    return {"surface_text": ts.surface_text}


def semantic_conflict_to_dict(sc: SemanticConflict) -> dict[str, Any]:
    """Serialize SemanticConflict to dict."""
    return {
        "term": term_surface_to_dict(sc.term),
        "conflict_type": sc.conflict_type.value,
        "severity": sc.severity.value,
        "confidence": sc.confidence,
        "candidate_senses": [
            {
                "surface": c.surface,
                "scope": c.scope,
                "definition": c.definition,
                "confidence": c.confidence,
            }
            for c in sc.candidate_senses
        ],
        "context": sc.context,
    }
