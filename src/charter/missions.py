"""Charter facade for mission-template / mission-type repository types.

This module is the charter-layer proxy for runtime callers that historically
imported the mission-template, mission-type, and mission-step repository
surfaces directly from ``charter.offering.missions.*``. The runtime → charter →
charter.offering boundary (ADR 2026-03-27-1, tightened by mission
``charter-mediated-doctrine-selection-01KRTZCA`` and re-affirmed by mission
``doctrine-public-api-surface-01KZPDSR``) requires runtime modules under
``src/specify_cli/`` to reach charter offering artifacts only through such charter
facades.

Every path re-exported here is dispositioned ``FACADE-ONLY`` in the WP01
census (``tests/architectural/test_doctrine_census.py::DISPOSITION``): a clean
charter door is preferred over widening ``charter/offering/api.py`` (these types are
not part of the ``spec-kitty-doctrine`` wheel's public contract).

This file is a **pure re-export** module — no behaviour, no wrappers, no type
aliases. Object identity is preserved (e.g.
``charter.missions.MissionTemplateRepository is
charter.offering.missions.repository.MissionTemplateRepository``), enforced by
``tests/architectural/test_charter_facades_reexport_offering.py``.
"""

from charter.offering.missions.expected_artifact_manifest import (
    ArtifactClassEnum,
    ExpectedArtifactManifest,
    ExpectedArtifactSpec,
)
from charter.offering.missions.mission_step_repository import MissionStepRepository
from charter.offering.missions.mission_type_repository import (
    MissionTypeRepository,
    builtin_mission_type_ids,
    resolve_layered_mission_types,
)
from charter.offering.missions.repository import (
    MalformedManifestError,
    MissionsRootNotFound,
    MissionTemplateRepository,
)
from charter.offering.missions.step_projection import (
    project_artifact_name_set,
    project_template_set,
)

__all__ = [
    "ArtifactClassEnum",
    "ExpectedArtifactManifest",
    "ExpectedArtifactSpec",
    "MalformedManifestError",
    "MissionsRootNotFound",
    "MissionStepRepository",
    "MissionTemplateRepository",
    "MissionTypeRepository",
    "builtin_mission_type_ids",
    "project_artifact_name_set",
    "project_template_set",
    "resolve_layered_mission_types",
]
