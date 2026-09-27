"""Agent-profile schema models.

This module defines the Pydantic model that serves as the single source of
truth for ``agent-profile.schema.yaml``.  It is intentionally **separate**
from the domain model in ``profile.py`` because:

* The schema uses kebab-case field names (``profile-id``, ``agent-profile``),
  while the domain model uses snake_case with aliases.
* The schema includes reference sections (``tactic-references``,
  ``toolguide-references``, ``styleguide-references``, ``self-review-protocol``)
  that the domain model does not carry.
* The domain model has runtime fields (``excluding``) that are not part of
  the canonical schema.
* The domain model uses ``BeforeValidator`` / ``Role`` coercion that should
  not leak into schema generation.

The generated schema targets Draft 2020-12 (like all other generated schemas).
"""

from __future__ import annotations

from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from charter.offering.agent_profiles.schema_version import AGENT_PROFILE_SCHEMA_VERSION_PATTERN

# Relationship fields retired in the FR-028 hard cutover. Agent-profile YAML
# uses kebab-case keys, so both the snake_case and kebab-case spellings are
# rejected. Lineage (``specializes-from``) and augmentation
# (``enhances``/``overrides``) are authored as DRG fragment edges merged into
# ``packs/built-in/*.graph.yaml`` — never as inline profile fields.
_RETIRED_PROFILE_RELATIONSHIP_KEYS = (
    "specializes_from",
    "specializes-from",
    "enhances",
    "overrides",
)


def _reject_retired_profile_relationship_fields(data: Any) -> Any:
    """Raise an actionable error if a retired relationship key is authored."""
    if not isinstance(data, dict):
        return data
    present = [key for key in _RETIRED_PROFILE_RELATIONSHIP_KEYS if key in data]
    if present:
        keys = ", ".join(repr(key) for key in present)
        raise ValueError(
            f"Retired relationship field(s) {keys} on agent profile are no "
            f"longer accepted (FR-028 hard cutover). Author lineage and "
            f"augmentation as DRG edges "
            f"(e.g. {{source: agent_profile:<id>, target: agent_profile:<id>, "
            f"relation: specializes_from|enhances|overrides}}) in the fragment "
            f"for the source kind, packs/built-in/agent_profile.graph.yaml — "
            f"not as inline profile fields."
        )
    return data


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


class AgentSpecialization(BaseModel):
    """Agent specialization definition."""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    primary_focus: str = Field(alias="primary-focus")
    secondary_awareness: str | None = Field(default=None, alias="secondary-awareness")
    avoidance_boundary: str | None = Field(default=None, alias="avoidance-boundary")
    success_definition: str | None = Field(default=None, alias="success-definition")


class AgentCollaboration(BaseModel):
    """Agent collaboration patterns and outputs."""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    handoff_to: list[str] = Field(default_factory=list, alias="handoff-to")
    handoff_from: list[str] = Field(default_factory=list, alias="handoff-from")
    works_with: list[str] = Field(default_factory=list, alias="works-with")
    output_artifacts: list[str] = Field(default_factory=list, alias="output-artifacts")
    operating_procedures: list[str] = Field(default_factory=list, alias="operating-procedures")
    canonical_verbs: list[str] = Field(default_factory=list, alias="canonical-verbs")


class AgentModeDefault(BaseModel):
    """Available reasoning mode with description."""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    mode: str
    description: str
    use_case: str = Field(alias="use-case")


class AgentSpecializationContext(BaseModel):
    """Declarative conditions defining when a specialist is preferred."""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    file_patterns: list[str] = Field(default_factory=list, alias="file-patterns")
    domain_keywords: list[str] = Field(default_factory=list, alias="domain-keywords")
    writing_style: list[str] = Field(default_factory=list, alias="writing-style")
    complexity_preference: list[str] = Field(default_factory=list, alias="complexity-preference")


class AgentDirectiveReference(BaseModel):
    """Reference to a directive with usage rationale."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    name: str
    rationale: str


class AgentTacticReference(BaseModel):
    """Reference to a tactic with usage rationale."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    rationale: str


class AgentToolguideReference(BaseModel):
    """Reference to a toolguide with usage rationale."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    rationale: str


class AgentStyleguideReference(BaseModel):
    """Reference to a styleguide with usage rationale."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    rationale: str


class SelfReviewStep(BaseModel):
    """A single step in the self-review protocol."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    command: str | None = None
    gate: str


class SelfReviewProtocol(BaseModel):
    """Self-review checklist the agent runs before handing off work."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    steps: list[SelfReviewStep] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Top-level schema model
# ---------------------------------------------------------------------------


class AgentProfileSchema(BaseModel):
    """Rich agent profile schema with 6-section structure.

    This is the **schema-generation** model. For the runtime domain model
    see ``charter.offering.agent_profiles.profile.AgentProfile``.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        populate_by_name=True,
        json_schema_extra={
            "$comment": "schema-version: 2 — roles list support added; legacy 1.0 remains accepted",
            "anyOf": [{"required": ["role"]}, {"required": ["roles"]}],
        },
    )

    # Core identity
    profile_id: str = Field(alias="profile-id", pattern=r"^[a-z][a-z0-9-]*$")
    name: str
    description: str | None = None
    schema_version: str | None = Field(
        default=None, alias="schema-version", pattern=AGENT_PROFILE_SCHEMA_VERSION_PATTERN
    )
    purpose: str
    role: str | None = Field(
        default=None,
        description="Agent role - deprecated scalar form; prefer roles array",
    )
    roles: list[str] | None = Field(
        default=None,
        min_length=1,
        description="Agent roles list (first entry is primary role)",
    )
    avatar_image: str | None = Field(default=None, alias="avatar-image")
    sentinel: bool = Field(default=False)
    tags: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    routing_priority: int | None = Field(default=None, alias="routing-priority", ge=0, le=100)
    max_concurrent_tasks: int | None = Field(default=None, alias="max-concurrent-tasks", ge=1)
    applies_to_languages: list[str] = Field(default_factory=list)
    # Optional model/effort routing hint (FR-005); mirrors ``AgentProfile``'s
    # ``preferred_model``/``effort`` in profile.py. Use an explicit alias (not a
    # bare ``model`` field, which fails to register on this model) so the
    # generated JSON schema exposes ``model``/``effort`` properties.
    # #5117 KEEP verdict: consumer-authored, wired end-to-end to the dispatch
    # routing advisory — not an inert slot despite the detector's local-variable
    # name collision at drg/project_scan.py:207.
    preferred_model: str | None = Field(
        default=None,
        alias="model",
        description=(
            "Consumer-authored preferred model id for this profile's routing "
            "preference. Built-in profiles deliberately leave it unset; the "
            "dispatch routing advisory surfaces it as the profile-preference "
            "candidate."
        ),
    )
    effort: str | None = Field(default=None, alias="effort")

    # Specialization
    specialization: AgentSpecialization

    # Section 3: Collaboration contract
    collaboration: AgentCollaboration | None = None

    # Section 4: Mode defaults
    mode_defaults: list[AgentModeDefault] = Field(default_factory=list, alias="mode-defaults")

    # Section 5: Initialization declaration
    initialization_declaration: str | None = Field(default=None, alias="initialization-declaration")

    # Section 6: Specialization context
    specialization_context: AgentSpecializationContext | None = Field(
        default=None, alias="specialization-context"
    )

    # Directive references
    directive_references: list[AgentDirectiveReference] = Field(
        default_factory=list, alias="directive-references"
    )

    # Tactic references
    tactic_references: list[AgentTacticReference] = Field(
        default_factory=list, alias="tactic-references"
    )

    # Toolguide references
    toolguide_references: list[AgentToolguideReference] = Field(
        default_factory=list, alias="toolguide-references"
    )

    # Styleguide references
    styleguide_references: list[AgentStyleguideReference] = Field(
        default_factory=list, alias="styleguide-references"
    )

    # Self-review protocol
    self_review_protocol: SelfReviewProtocol | None = Field(
        default=None, alias="self-review-protocol"
    )

    @model_validator(mode="before")
    @classmethod
    def _reject_retired_relationship_fields(cls, data: Any) -> Any:
        return _reject_retired_profile_relationship_fields(data)

    @model_validator(mode="after")
    def _requires_role_or_roles(self) -> Self:
        if self.role is None and self.roles is None:
            raise ValueError("agent profile requires either role or roles")
        return self
