"""Charter facade for mission-step-contract types.

This module is the charter-layer proxy for runtime callers that historically
imported from ``charter.offering.mission_step_contracts`` (now retired). The
runtime → charter → charter.offering boundary (ADR 2026-03-27-1, tightened by
mission ``charter-mediated-doctrine-selection-01KRTZCA``) requires runtime
modules under ``src/specify_cli/`` to reach charter offering artifacts only through
charter facades.

WP01 of mission ``charter-doctrine-mission-type-configuration-01KSWJVX``
relocated the legacy contract types into
:mod:`charter.offering.missions.step_contracts`. The unified mission-step model
(FR-011) now lives at :class:`charter.offering.missions.models.MissionStep`; the
legacy ``MissionStepContract`` shape is preserved as a compatibility
surface for the runtime contract registry and on-disk
``*.step-contract.yaml`` loader.

The exported ``MissionStep`` symbol is the **unified** model owned by
``MissionType`` (per FR-011). The legacy step-shape used by
``MissionStepContract.steps`` is :class:`MissionStepContractStep`.

This file is a **pure re-export** module — no behaviour, no wrappers, no
type aliases.
"""

# MissionStepRepository: compat re-export (test-consumed); dropped from
# __all__ when WP02 (mission up-mission-type-seam-01KZY1JB) deleted
# resolve_mission_steps, the last src/ importer reached through this facade.
# Direct callers still reach the same object via the charter.missions facade
# or charter.offering.missions.mission_step_repository directly.
from charter.offering.missions.mission_step_repository import MissionStepRepository as MissionStepRepository
from charter.offering.missions.models import MissionStep as MissionStep  # compat re-export (test-consumed); dropped from __all__ when last src importer was retyped
from charter.offering.missions.step_contracts import (
    GateBinding,
    MissionStepContract,
    MissionStepInput,
    MissionStepContractRepository,
    MissionStepContractStep,
)

__all__ = [
    "GateBinding",
    "MissionStepContract",
    "MissionStepInput",
    "MissionStepContractRepository",
    "MissionStepContractStep",
]
