"""Expected artifact manifest schema (FR-009 / C-001).

Relocated from ``specify_cli.dossier.manifest`` so the runtime resolver and
dossier registry can share pure offering-layer data models without importing
``specify_cli`` from the charter layers.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "ArtifactClassEnum",
    "ExpectedArtifactManifest",
    "ExpectedArtifactSpec",
]


class ArtifactClassEnum(StrEnum):
    """Classification of artifacts in the dossier system."""

    INPUT = "input"
    WORKFLOW = "workflow"
    OUTPUT = "output"
    EVIDENCE = "evidence"
    POLICY = "policy"
    RUNTIME = "runtime"


class ExpectedArtifactSpec(BaseModel):
    """Single artifact expected at a mission step."""

    model_config = ConfigDict(extra="forbid")

    artifact_key: str = Field(
        ...,
        min_length=1,
        description="Stable, unique key (e.g., 'input.spec.main', 'output.tasks.per_wp')",
    )
    artifact_class: ArtifactClassEnum = Field(
        ...,
        description="Classification: input | workflow | output | evidence | policy | runtime",
    )
    path_pattern: str = Field(
        ...,
        min_length=1,
        description="Glob pattern relative to feature directory (e.g., 'spec.md', 'tasks/*.md')",
    )
    blocking: bool = Field(
        default=False,
        description="If True, missing artifact blocks mission completeness",
    )


class ExpectedArtifactManifest(BaseModel):
    """Complete expected artifact manifest for a mission type."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="1.0",
        description="Manifest schema version",
    )
    mission_type: str = Field(
        ...,
        description="Mission type (e.g., 'software-dev', 'research', 'documentation')",
    )
    manifest_version: str = Field(
        default="1",
        description="Manifest data version",
    )
    required_always: list[ExpectedArtifactSpec] = Field(
        default_factory=list,
        description="Artifacts required regardless of mission step",
    )
    required_by_step: dict[str, list[ExpectedArtifactSpec]] = Field(
        default_factory=dict,
        description="Dict mapping step_id to required artifacts for that step",
    )
    optional_always: list[ExpectedArtifactSpec] = Field(
        default_factory=list,
        description="Artifacts optional regardless of mission step",
    )

    def get_step_ids(self) -> list[str]:
        """Return all step IDs in ``required_by_step``."""
        return list(self.required_by_step.keys())
