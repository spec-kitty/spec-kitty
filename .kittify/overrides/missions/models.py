"""Mission schema model.

This module defines the Pydantic model that serves as the single source of
truth for ``mission.schema.yaml``.  The model mirrors the hand-written schema
exactly; it is **not** the runtime domain model used by
``MissionTemplateRepository`` (which operates on raw dicts).

The former ``orchestration`` state machine (``MissionOrchestration`` /
``MissionStateObject`` / ``MissionTransition``) was retired in mission
dead-port-disposition-01M1TZVN: it was a REQUIRED field that no artefact in
the tree ever supplied, whose only name-level producer match was the
mission-DSL v1 blocks that the same mission deleted. Step sequencing is
authored in ``mission-runtime.yaml`` (a DAG of ``depends_on`` edges) instead.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MissionStep(BaseModel):
    """An optional step within the mission."""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    id: str
    title: str | None = None
    name: str | None = None
    description: str | None = None
    prompt_template: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    agent_profile: str | None = Field(default=None, alias="agent-profile", pattern=r"^[a-z][a-z0-9-]*$")


class Mission(BaseModel):
    """Top-level mission definition.

    This is the schema-generation model; do not confuse with the runtime
    ``MissionTemplateRepository`` which loads missions from raw YAML.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = Field(pattern=r"^1\.0$")
    key: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    name: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    steps: list[MissionStep] = Field(default_factory=list)
