"""Closed enums and Pydantic models for custom-mission validation outputs.

The wire spelling of every code in :class:`LoaderErrorCode` and
:class:`LoaderWarningCode` is part of the loader's stability contract
(NFR-002). See ``kitty-specs/local-custom-mission-loader-01KQ2VNJ/contracts/
validation-errors.md`` for the canonical reference.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from runtime.next._internal_runtime.schema import (
    DiscoveredMission,
    MissionTemplate,
)


class LoaderErrorCode(StrEnum):
    """Closed set of operator-fixable loader error codes.

    Wire spellings (string values) are stable; renames or removals are
    breaking changes. Additions are non-breaking.
    """

    MISSION_YAML_MALFORMED = "MISSION_YAML_MALFORMED"
    MISSION_REQUIRED_FIELD_MISSING = "MISSION_REQUIRED_FIELD_MISSING"
    MISSION_KEY_UNKNOWN = "MISSION_KEY_UNKNOWN"
    MISSION_KEY_AMBIGUOUS = "MISSION_KEY_AMBIGUOUS"
    MISSION_KEY_RESERVED = "MISSION_KEY_RESERVED"
    MISSION_RETROSPECTIVE_MISSING = "MISSION_RETROSPECTIVE_MISSING"
    MISSION_STEP_NO_PROFILE_BINDING = "MISSION_STEP_NO_PROFILE_BINDING"
    MISSION_STEP_AMBIGUOUS_BINDING = "MISSION_STEP_AMBIGUOUS_BINDING"
    MISSION_STEP_DEPENDENCY_INVALID = "MISSION_STEP_DEPENDENCY_INVALID"
    MISSION_CONTRACT_REF_UNRESOLVED = "MISSION_CONTRACT_REF_UNRESOLVED"


class LoaderWarningCode(StrEnum):
    """Closed set of loader warning codes (non-fatal)."""

    MISSION_KEY_SHADOWED = "MISSION_KEY_SHADOWED"
    MISSION_PACK_LOAD_FAILED = "MISSION_PACK_LOAD_FAILED"


class LoaderError(BaseModel):
    """Single operator-fixable validation error produced by the loader."""

    model_config = ConfigDict(frozen=True)

    code: LoaderErrorCode
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class LoaderWarning(BaseModel):
    """Single non-fatal validation warning produced by the loader."""

    model_config = ConfigDict(frozen=True)

    code: LoaderWarningCode
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ValidationReport(BaseModel):
    """Result of :func:`mission_loader.validator.validate_custom_mission`.

    ``ok`` is convenience: True iff a template successfully loaded AND no
    errors were collected. Warnings do NOT affect ``ok``.
    """

    model_config = ConfigDict(frozen=True)

    template: MissionTemplate | None = None
    discovered: DiscoveredMission | None = None
    errors: list[LoaderError] = Field(default_factory=list)
    warnings: list[LoaderWarning] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.template is not None and not self.errors


__all__ = [
    "LoaderError",
    "LoaderErrorCode",
    "LoaderWarning",
    "LoaderWarningCode",
    "ValidationReport",
]
