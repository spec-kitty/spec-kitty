"""Structured error taxonomy for the Charter Synthesizer pipeline.

All errors inherit from SynthesisError and carry structured fields rather than
bare string messages. The CLI renders these via a shared rich panel helper so
operators see context-rich diagnostics, not tracebacks.

See data-model.md §E-8 for the authoritative error taxonomy.

ARCHITECTURAL NOTE: The production adapter (Anthropic SDK) has been removed.
spec-kitty never calls an LLM itself. Synthesis is performed by the LLM harness
(Claude Code, Codex, Cursor, etc.) via the spk-charter-governance skill.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

__all__ = [
    "DuplicateTargetError",
    "FixtureAdapterMissingError",
    "GeneratedArtifactLoadError",
    "GeneratedArtifactMissingError",
    "ManifestIntegrityError",
    "NeutralityGateViolation",
    "PathGuardViolation",
    "ProjectDRGValidationError",
    "StagingPromoteError",
    "SynthesisError",
    "SynthesisSchemaError",
    "TopicSelectorAmbiguousError",
    "TopicSelectorUnresolvedError",
    "render_error_panel",
]



# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class SynthesisError(Exception):
    """Base class for all charter synthesizer errors.

    Subclasses are frozen dataclasses so every error carries structured,
    type-safe fields. The CLI layer catches SynthesisError and delegates
    rendering to render_error_panel().
    """


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def render_error_panel(error: SynthesisError, console: Console | None = None) -> None:
    """Render a SynthesisError as a rich error panel to stderr."""
    if console is None:
        console = Console(stderr=True)
    title = type(error).__name__
    body = str(error)
    console.print(Panel(Text(body, style="red"), title=f"[bold red]{title}[/]", border_style="red"))


# ---------------------------------------------------------------------------
# Path guard
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PathGuardViolation(SynthesisError):
    """Raised before any filesystem mutation when a write targets a forbidden path.

    The path guard fires before the filesystem is touched (FR-016, US-7).
    """

    attempted_path: str
    caller: str

    def __str__(self) -> str:
        return (
            f"PathGuard blocked write to '{self.attempted_path}' "
            f"(caller: {self.caller}). "
            f"Synthesizer writes must target .kittify/charter-packs/ (content) "
            f"or .kittify/charter/ (bookkeeping) only."
        )


# ---------------------------------------------------------------------------
# Schema / validation errors
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SynthesisSchemaError(SynthesisError):
    """AdapterOutput.body fails built-in-layer Pydantic schema validation (FR-019).

    Raised before any provenance or DRG writes occur.
    """

    artifact_kind: str
    artifact_slug: str
    validation_errors: tuple[str, ...]

    def __str__(self) -> str:
        errs = "; ".join(self.validation_errors)
        return (
            f"Adapter output for {self.artifact_kind}:{self.artifact_slug} "
            f"failed schema validation: {errs}"
        )


@dataclass(frozen=True)
class ProjectDRGValidationError(SynthesisError):
    """validate_graph() returned ≥1 errors on the merged (built-in + project) graph (FR-008).

    Raised before promote; no files land in the live tree.
    """

    errors: tuple[str, ...]
    merged_graph_summary: str

    def __str__(self) -> str:
        errs = "; ".join(self.errors)
        return (
            f"Project DRG validation failed ({len(self.errors)} error(s)): {errs}. "
            f"Graph summary: {self.merged_graph_summary}"
        )


# ---------------------------------------------------------------------------
# Duplicate / collision errors
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DuplicateTargetError(SynthesisError):
    """Two targets in one run share the same (kind, slug) (EC-7)."""

    kind: str
    slug: str
    occurrences: int

    def __str__(self) -> str:
        return (
            f"Duplicate synthesis target: {self.kind}:{self.slug} "
            f"appears {self.occurrences} time(s) in a single run. "
            f"Each (kind, slug) pair must be unique within a run."
        )


# ---------------------------------------------------------------------------
# Topic selector errors
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TopicSelectorUnresolvedError(SynthesisError):
    """--topic selector cannot be resolved by any of the three tiers (US-6, FR-013).

    Attributes
    ----------
    raw:
        The original user-supplied selector string.
    candidates:
        Top-5 nearest candidates by Levenshtein distance, formatted as
        "{form}:{value} (distance={n})" strings.
    attempted_forms:
        Which resolution forms were tried before failing, e.g.
        ``("kind_slug", "drg_urn")`` or ``("interview_section",)``.
        Included for debuggability (contracts/topic-selector.md §2.1).
    """

    raw: str
    candidates: tuple[str, ...]
    attempted_forms: tuple[str, ...] = ()

    def __str__(self) -> str:
        forms = ", ".join(self.attempted_forms) if self.attempted_forms else "all"
        if self.candidates:
            cands = ", ".join(self.candidates)
            return (
                f"Topic selector '{self.raw}' could not be resolved "
                f"(tried: {forms}). "
                f"Did you mean one of: {cands}?"
            )
        return (
            f"Topic selector '{self.raw}' could not be resolved "
            f"(tried: {forms}). "
            f"No candidates found in the project-local artifact set, "
            f"merged DRG, or interview section labels."
        )


@dataclass(frozen=True)
class TopicSelectorAmbiguousError(SynthesisError):
    """Topic selector matches multiple candidates with equal priority (FR-013)."""

    raw: str
    candidates: tuple[str, ...]

    def __str__(self) -> str:
        cands = ", ".join(self.candidates)
        return (
            f"Topic selector '{self.raw}' is ambiguous — matched: {cands}. "
            f"Use a more specific selector (e.g. include the artifact kind prefix)."
        )


# ---------------------------------------------------------------------------
# Fixture adapter error
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FixtureAdapterMissingError(SynthesisError):
    """Fixture adapter cannot find a recorded fixture for the normalized request hash.

    The expected_path field tells the operator exactly where to place a new fixture.
    """

    expected_path: str
    kind: str
    slug: str
    inputs_hash: str

    def __str__(self) -> str:
        return (
            f"No fixture found for {self.kind}:{self.slug} "
            f"(inputs_hash={self.inputs_hash[:12]}...); "
            f"expected at {self.expected_path}"
        )


@dataclass(frozen=True)
class GeneratedArtifactMissingError(SynthesisError):
    """The harness-owned generated-artifact adapter cannot find an expected file."""

    expected_path: str
    kind: str
    slug: str
    expected_id: str

    def __str__(self) -> str:
        return (
            f"No generated artifact found for {self.kind}:{self.slug}; "
            f"expected YAML at {self.expected_path} with id '{self.expected_id}'. "
            "Write the agent-authored artifact there, then rerun synthesis."
        )


@dataclass(frozen=True)
class GeneratedArtifactLoadError(SynthesisError):
    """The harness-owned generated-artifact adapter could not parse or trust a file."""

    artifact_path: str
    reason: str
    expected_id: str | None = None
    actual_id: str | None = None

    def __str__(self) -> str:
        details = f"Generated artifact at {self.artifact_path} could not be loaded: {self.reason}"
        if self.expected_id is not None:
            details += f". Expected id '{self.expected_id}'"
            if self.actual_id is not None:
                details += f", got '{self.actual_id}'"
        return details


# ---------------------------------------------------------------------------
# Staging / promote errors
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StagingPromoteError(SynthesisError):
    """os.replace or manifest write failed during the promote step (KD-2).

    Orchestration preserves staging dir as .failed/ for operator diagnosis.
    """

    run_id: str
    staging_dir: str
    cause: str

    def __str__(self) -> str:
        return (
            f"Synthesis promote failed for run {self.run_id} "
            f"(staging: {self.staging_dir}): {self.cause}. "
            f"Staging directory preserved as {self.staging_dir}.failed/ for diagnosis."
        )


@dataclass(frozen=True)
class ManifestIntegrityError(SynthesisError):
    """A reader found that manifest-listed content_hash does not match disk content (E-6)."""

    manifest_path: str
    offending_artifact: str

    def __str__(self) -> str:
        return (
            f"Manifest integrity check failed: artifact '{self.offending_artifact}' "
            f"listed in {self.manifest_path} does not match its on-disk content hash. "
            f"Re-run 'charter synthesize' to repair."
        )


# ---------------------------------------------------------------------------
# Neutrality gate error
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NeutralityGateViolation(SynthesisError):
    """Raised when a generic-scoped synthesized artifact contains language/tool-specific bias.

    Promotion is blocked. The staging directory is preserved for operator inspection.
    Raised after staging, before the first ``os.replace`` in ``promote()``.

    FR-011, FR-012 — data-model.md §E-8
    """

    artifact_urn: str  # URN of the offending artifact
    detected_terms: tuple[str, ...]  # banned terms found in the artifact body
    staging_dir: Path  # preserved staging directory path

    def __str__(self) -> str:
        terms = ", ".join(f"'{t}'" for t in self.detected_terms)
        return (
            f"Neutrality gate blocked promotion of {self.artifact_urn}.\n"
            f"Language-specific terms detected in a generic-scoped artifact: {terms}.\n"
            f"Inspect the staged artifact at: {self.staging_dir}"
        )
