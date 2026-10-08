"""Per-type governance override channel, ridden through the shared overlay stack.

A project may override a mission type's governance **without editing the project
charter or shipped doctrine** (FR-011) by dropping a
``.kittify/charter-packs/mission_types/<type>/governance-profile.yaml`` file.  That
override is resolved through the *existing* ``doctrine/base.py`` builtin → org →
project overlay (field-merge + :class:`~charter.offering.base.DoctrineLayerCollisionWarning`)
— **not** a bespoke second merge.  :class:`MissionTypeProfileRepository` is the
adapter that lets :class:`~charter.activation.mission_type_profiles.MissionTypeProfile` ride
that stack.

The named adapter cost (recorded in the mission ADR): ``base.py`` keys overlays
on the raw YAML ``id`` field and skips id-less files, while a mission-type
profile is conceptually keyed on ``mission_type``.  The reconciliation is the
``id == mission_type`` invariant enforced by
:meth:`~charter.activation.mission_type_profiles.MissionTypeProfile._bind_id_to_mission_type`
— every shipped and project ``governance-profile.yaml`` carries ``id`` equal to
its ``mission_type``.

Layer rule
----------
This repository lives under ``src/charter/`` **by necessity**: the base
(``doctrine/base.py``) is importable in the ``charter → doctrine`` direction, but
``doctrine ↛ charter`` (a hard ratchet pinned by
``tests/architectural/test_layer_rules.py``).  Placing the
``MissionTypeProfile``-typed subclass in ``doctrine/`` would force a
``doctrine → charter`` import (the profile model lives in ``charter/``) and trip
the layer rule.

Do **not** confuse this with
``doctrine/missions/mission_type_repository.py::MissionTypeRepository`` — that
loads the mission-type *artefact* model (``extends`` / ``action_sequence``), a
different shape.  This repository loads the *governance profile*.
"""

from __future__ import annotations

from pathlib import Path

from charter.activation.mission_type_profiles import MissionTypeProfile
from charter.offering.base import BaseArtifactRepository
from charter.offering.pack_paths import built_in_missions_root as _pack_paths_built_in_missions_root
from kernel.charter_pack_paths import project_pack_root

__all__ = ["MissionTypeProfileRepository", "builtin_missions_root"]

#: Shipped built-in profiles live at
#: ``src/charter/offering/missions/<type>/governance-profile.yaml``; project overrides
#: mirror that shape under ``.kittify/charter-packs/mission_types/<type>/``.
_GOVERNANCE_PROFILE_GLOB = "governance-profile.yaml"

#: Project override directory relative to the project pack root.
_PROJECT_OVERRIDE_DIRNAME = "mission_types"


def builtin_missions_root() -> Path:
    """Shipped profiles root: ``packs/built-in/missions``.

    Thin delegate (FR-004, #3575) directly onto the one canonical
    :func:`~charter.offering.pack_paths.built_in_missions_root` authority.
    Unlike ``MissionTemplateRepository.default_missions_root()``, this
    accessor returns the joined path without performing the repository
    existence check.

    Public module-level accessor (#2668) so cross-module consumers (e.g.
    ``charter.activation.action_grain``, ``charter.activation.mission_type_profiles``) no longer
    need to reach into :class:`MissionTypeProfileRepository`'s private
    ``_default_built_in_dir`` classmethod.
    """
    return _pack_paths_built_in_missions_root()


class MissionTypeProfileRepository(BaseArtifactRepository[MissionTypeProfile]):
    """Load mission-type governance profiles through the builtin → org → project overlay.

    Both the shipped and project layers nest each profile under a per-type
    directory (``<type>/governance-profile.yaml``), so the project scan is
    recursive (the shared built-in scan is already recursive).
    """

    def __init__(
        self,
        built_in_dir: Path | None = None,
        *,
        org_dirs: list[Path] | None = None,
        project_dir: Path | None = None,
    ) -> None:
        super().__init__(
            built_in_dir=built_in_dir or self._default_built_in_dir(),
            org_dirs=org_dirs,
            project_dir=project_dir,
        )

    @classmethod
    def for_project(
        cls,
        repo_root: Path,
        *,
        org_dirs: list[Path] | None = None,
    ) -> MissionTypeProfileRepository:
        """Build a repository whose project layer reads *repo_root*'s override dir.

        The project overlay is
        ``<repo_root>/.kittify/charter-packs/mission_types/<type>/governance-profile.yaml``.
        The directory need not exist — an absent overlay simply yields the
        shipped baseline (see :meth:`~charter.offering.base.BaseArtifactRepository._load`).
        """
        return cls(
            org_dirs=org_dirs,
            project_dir=project_pack_root(repo_root) / _PROJECT_OVERRIDE_DIRNAME,
        )

    @staticmethod
    def _default_built_in_dir() -> Path:
        """Shipped profiles root: ``packs/built-in/missions``.

        Delegates to the public module-level :func:`builtin_missions_root`
        (#2668) — kept as a thin classmethod wrapper so the existing
        ``__init__`` call site (and any other intra-class caller) is
        unaffected by the promotion.
        """
        return builtin_missions_root()

    @property
    def _schema(self) -> type[MissionTypeProfile]:
        return MissionTypeProfile

    @property
    def _glob(self) -> str:
        return _GOVERNANCE_PROFILE_GLOB

    def _key(self, obj: MissionTypeProfile) -> str:
        """Key on the overlay identity (``id == mission_type`` invariant)."""
        return obj.id
