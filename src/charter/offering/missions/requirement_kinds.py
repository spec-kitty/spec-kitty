"""Requirement-kind declaration schema (#5956 loader seam, mission org-pack-chain-authority).

Pure offering-layer data models for ``requirement-kinds.yaml``; the tier-walking
loader lives in :mod:`charter.activation.manifest_loader` (activation may import
offering, never the reverse). Mirrors
:class:`~charter.offering.missions.expected_artifact_manifest.ExpectedArtifactSpec`
/ ``ExpectedArtifactManifest``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "RequirementKind",
    "RequirementKindDeclaration",
    "default_requirement_kinds",
]


class RequirementKind(BaseModel):
    """One requirement kind (e.g. ``FR``) a mission type declares."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    prefix: str = Field(..., min_length=1, description="Requirement-ID prefix (e.g. 'FR')")
    label: str = Field(..., min_length=1, description="Human label (e.g. 'Functional requirement')")
    glossary_term: str = Field(..., min_length=1, description="Glossary term name; referenced only")
    must_map_to_wp: bool = Field(..., description="Whether every ID of this kind must map to a WP")


class RequirementKindDeclaration(BaseModel):
    """The full requirement-kind set a mission type declares (whole-file, no additive floor)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1", description="Declaration schema version")
    mission_type: str = Field(..., min_length=1, description="Mission type this set applies to")
    kinds: list[RequirementKind] = Field(..., min_length=1, description="The full kind set")


# Derived from today's ``FR|NFR|SC|C`` set (``specify_cli.requirement_mapping.grammar._KIND_ALT``).
_DEFAULT_KINDS: tuple[RequirementKind, ...] = (
    RequirementKind(prefix="FR", label="Functional requirement", glossary_term="functional requirement", must_map_to_wp=True),
    RequirementKind(prefix="NFR", label="Non-functional requirement", glossary_term="non-functional requirement", must_map_to_wp=True),
    RequirementKind(prefix="SC", label="Success criterion", glossary_term="success criterion", must_map_to_wp=True),
    RequirementKind(prefix="C", label="Constraint", glossary_term="constraint", must_map_to_wp=False),
)


def default_requirement_kinds(mission_type: str) -> RequirementKindDeclaration:
    """Return the built-in default kind set, used when no tier declares a file."""
    return RequirementKindDeclaration(schema_version="1", mission_type=mission_type, kinds=list(_DEFAULT_KINDS))
