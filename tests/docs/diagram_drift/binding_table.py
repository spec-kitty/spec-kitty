"""Explicit ``file:anchor -> model`` binding table + ArtifactKind disposition map.

The guard checks every binding here (1:N per diagram file allowed) and refuses to
pass unless EVERY ``ArtifactKind`` member carries an explicit disposition. Adding
a diagram means adding a binding row; adding an ``ArtifactKind`` member means
adding a disposition (the guard fails until you do).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from charter.offering.agent_profiles.schema_models import (
    AgentProfileSchema,
    AgentSpecialization,
)
from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.drg.models import DRGEdge, DRGNode, NodeKind, Relation
from charter.offering.missions.action_index import ActionIndex
from charter.offering.missions.step_contracts import (
    MissionStepContract,
    MissionStepContractStep,
)

__all__ = [
    "ARTIFACT_KIND_DISPOSITIONS",
    "BINDINGS",
    "DiagramBinding",
    "ModelKind",
]

_RELATIONSHIPS = "docs/architecture/doctrine-relationships.md"
_MISSION_TYPE = "docs/architecture/mission-type-resolution.md"
_KINDS = "docs/architecture/doctrine-kinds.md"


class ModelKind(StrEnum):
    """How to introspect the bound model's field/member set."""

    PYDANTIC = "pydantic"  # model_fields, FieldInfo.alias or name
    DATACLASS = "dataclass"  # dataclasses.fields()
    STRENUM = "strenum"  # list(EnumType) member values


@dataclass(frozen=True)
class DiagramBinding:
    """One diagram anchor bound to one code model (1:N per file)."""

    doc: str  # repo-relative markdown path
    anchor: str  # the YAML key naming this model inside a @startyaml block
    model: type[object]  # the class / enum introspected
    kind: ModelKind


# The authored corpus. Each anchor is a class-name YAML key inside a @startyaml
# block; nested value objects are found recursively by their class-name key.
BINDINGS: tuple[DiagramBinding, ...] = (
    # doctrine-relationships.md — the DRG (flat node + edge over two vocabularies)
    DiagramBinding(_RELATIONSHIPS, "DRGNode", DRGNode, ModelKind.PYDANTIC),
    DiagramBinding(_RELATIONSHIPS, "DRGEdge", DRGEdge, ModelKind.PYDANTIC),
    DiagramBinding(_RELATIONSHIPS, "NodeKind", NodeKind, ModelKind.STRENUM),
    DiagramBinding(_RELATIONSHIPS, "Relation", Relation, ModelKind.STRENUM),
    # mission-type-resolution.md — mission-step contract (nested) + action index
    DiagramBinding(_MISSION_TYPE, "MissionStepContract", MissionStepContract, ModelKind.PYDANTIC),
    DiagramBinding(
        _MISSION_TYPE, "MissionStepContractStep", MissionStepContractStep, ModelKind.PYDANTIC
    ),
    DiagramBinding(_MISSION_TYPE, "ActionIndex", ActionIndex, ModelKind.DATACLASS),
    # doctrine-kinds.md — the vocabulary + the agent-profile schema (aliased + nested)
    DiagramBinding(_KINDS, "ArtifactKind", ArtifactKind, ModelKind.STRENUM),
    DiagramBinding(_KINDS, "AgentProfileSchema", AgentProfileSchema, ModelKind.PYDANTIC),
    DiagramBinding(_KINDS, "AgentSpecialization", AgentSpecialization, ModelKind.PYDANTIC),
)


# EVERY ArtifactKind member MUST appear here. `diagrammed` = has a dedicated
# @startyaml schema diagram; `consciously-omitted` = documented in prose / the
# cross-kind overview but no per-kind field schema (a thin marker, or — for
# anti_pattern — a DRG node kind with no backing model class at all).
#
# NOTE the three-way `anti pattern` disambiguation: ArtifactKind.ANTI_PATTERN
# (this map) is NOT bound to `styleguides/models.py:AntiPattern` (a real BaseModel)
# NOR to the `NodeKind.ANTI_PATTERN` string — all three are distinct concepts.
ARTIFACT_KIND_DISPOSITIONS: dict[str, str] = {
    "directive": "consciously-omitted",
    "tactic": "consciously-omitted",
    "styleguide": "consciously-omitted",
    "toolguide": "consciously-omitted",
    "paradigm": "consciously-omitted",
    "procedure": "consciously-omitted",
    "agent_profile": "diagrammed",  # AgentProfileSchema (doctrine-kinds.md)
    "mission_step_contract": "diagrammed",  # MissionStepContract (mission-type-resolution.md)
    "template": "consciously-omitted",  # mission-scoped file selection, no authored schema
    "asset": "consciously-omitted",  # loose-contract blob, resolved to a path
    "glossary_pack": "consciously-omitted",  # documented; bundle of glossary/scope nodes
    "anti_pattern": "consciously-omitted",  # DRG node kind, no backing model class
    "skill": "consciously-omitted",  # documented (doctrine-kinds.md#skill); PackSkill model, thin entry point
}
