"""Glossary primitive types.

Zero external dependencies — stdlib only. Consumed by charter (including
charter.offering) and specify_cli. Lives in kernel so the dependency direction
stays clean:

    kernel  <-  charter
    kernel  <-  specify_cli
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, StrEnum


class GlossaryScope(Enum):
    """Glossary scope levels in the hierarchy."""

    MISSION_LOCAL = "mission_local"
    TEAM_DOMAIN = "team_domain"
    AUDIENCE_DOMAIN = "audience_domain"
    SPEC_KITTY_CORE = "spec_kitty_core"


class Strictness(StrEnum):
    """Glossary enforcement strictness levels.

    - OFF: No enforcement, generation always proceeds
    - MEDIUM: Warn broadly, block only high-severity conflicts
    - MAX: Block any unresolved conflict regardless of severity
    """

    OFF = "off"
    MEDIUM = "medium"
    MAX = "max"


@dataclass(frozen=True)
class ExtractedTerm:
    """A term extracted from input text."""

    surface: str  # Normalized surface form
    source: str  # Source of extraction (metadata_hint, quoted_phrase, etc.)
    confidence: float  # Confidence score (0.0-1.0)
    original: str = ""  # Original surface before normalization


@dataclass(frozen=True)
class TermSurface:
    """Raw string representation of a term."""

    surface_text: str  # e.g., "workspace"

    def __post_init__(self) -> None:
        # Validate: must be normalized (lowercase, trimmed)
        if self.surface_text != self.surface_text.lower().strip():
            raise ValueError(f"TermSurface must be normalized: {self.surface_text}")


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


@dataclass(frozen=True)
class ScopeRef:
    """Reference to a specific glossary scope version."""

    scope: GlossaryScope
    version_id: str  # e.g., "v3", "2026-02-16-001"


__all__ = [
    "GlossaryScope",
    "Strictness",
    "ExtractedTerm",
    "TermSurface",
    "ConflictType",
    "Severity",
    "SenseRef",
    "SemanticConflict",
    "ScopeRef",
]
