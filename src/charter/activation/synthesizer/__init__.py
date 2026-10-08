"""Charter Synthesizer — public package API.

This package delivers Phase 3 of the Charter EPIC: turning interview answers,
built-in doctrine, and the built-in DRG into project-local directives, tactics,
and styleguides stored under .kittify/charter-packs/ (content) and
.kittify/charter/ (provenance bookkeeping).

Public re-exports
-----------------
The symbols below are what downstream WPs and tests import from this package.
Everything else is package-internal.

Adapter seam (WP01, frozen):
    SynthesisAdapter — runtime-checkable Protocol
    AdapterOutput    — frozen dataclass

Request models (WP01, frozen):
    SynthesisRequest  — input envelope for generate() calls
    SynthesisTarget   — one unit of synthesis

Orchestrator (WP01 skeleton, WP02/WP05 populate):
    synthesize    — entry point for full synthesis
    resynthesize  — entry point for bounded resynthesis

Error taxonomy (WP01, frozen):
    SynthesisError                  — base exception
    PathGuardViolation              — write outside allowlist
    SynthesisSchemaError            — adapter output fails built-in schema
    ProjectDRGValidationError       — merged DRG validation failure
    DuplicateTargetError            — two targets share (kind, slug)
    TopicSelectorUnresolvedError    — --topic selector unresolvable
    TopicSelectorAmbiguousError     — --topic selector ambiguous
    FixtureAdapterMissingError      — fixture adapter missing fixture
    StagingPromoteError             — staging promote failed
    ManifestIntegrityError          — manifest content_hash mismatch

Test adapter (WP01):
    FixtureAdapter  — fixture-backed test adapter
"""

from .adapter import AdapterOutput, SynthesisAdapter
from .errors import (
    DuplicateTargetError,
    FixtureAdapterMissingError,
    ManifestIntegrityError,
    PathGuardViolation,
    ProjectDRGValidationError,
    StagingPromoteError,
    SynthesisError,
    SynthesisSchemaError,
    TopicSelectorAmbiguousError,
    TopicSelectorUnresolvedError,
)
from .fixture_adapter import FixtureAdapter
from .orchestrator import SynthesisResult, synthesize, resynthesize
from .path_guard import PathGuard
from .request import SynthesisRequest, SynthesisTarget

__all__ = [
    # Adapter seam
    "SynthesisAdapter",
    "AdapterOutput",
    # Request models
    "SynthesisRequest",
    "SynthesisTarget",
    # Orchestrator
    "synthesize",
    "resynthesize",
    "SynthesisResult",
    # Path guard
    "PathGuard",
    # Errors
    "SynthesisError",
    "PathGuardViolation",
    "SynthesisSchemaError",
    "ProjectDRGValidationError",
    "DuplicateTargetError",
    "TopicSelectorUnresolvedError",
    "TopicSelectorAmbiguousError",
    "FixtureAdapterMissingError",
    "StagingPromoteError",
    "ManifestIntegrityError",
    # Test adapter
    "FixtureAdapter",
]
