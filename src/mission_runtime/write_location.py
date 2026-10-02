"""Write-location value objects (mission coord-artifact-single-home-01M3V4BE, WP03).

Types only -- no git, no locking, and no module-level ``specify_cli`` import
(MR-1/MR-2: ``mission_runtime`` submodules import package-root symbols plus
stdlib only; a cross-package type is a ``TYPE_CHECKING``-only import so
``import mission_runtime`` stays cold, ``test_package_root_cold_imports``).
See ``contracts/write-location-accessor.md`` and data-model.md section 2.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from mission_runtime.artifacts import TopologySurface

if TYPE_CHECKING:
    # TYPE_CHECKING-only: ``CoordState`` is a ``specify_cli.missions.
    # _read_path_resolver`` enum. A module-level import here would pull
    # ``specify_cli`` into ``import mission_runtime`` and break the package's
    # cold-import guarantee; the annotation alone (under
    # ``from __future__ import annotations``) needs no runtime binding.
    from specify_cli.missions._read_path_resolver import CoordState

__all__ = ["Establishment", "SeedReport", "WriteLocation"]


class Establishment(enum.Enum):
    """What :func:`~specify_cli.coordination.coord_seed.establish_coord_write_location` did.

    Named ``WORKTREE_MATERIALIZED`` rather than bare ``MATERIALIZED`` so it
    never collides, by name, with
    :class:`~specify_cli.missions._read_path_resolver.CoordState.MATERIALIZED`
    -- a DIFFERENT concept (the coordination state *before* the call, carried
    separately on :attr:`WriteLocation.coord_state_before`; see binding
    correction "Value objects" in the WP03 prompt).
    """

    #: No side effect was needed (PRIMARY kind, non-coordination topology, or
    #: an already-MATERIALIZED surface with no pending seed).
    NONE = "none"
    #: An ``UNMATERIALIZED`` local-head coordination worktree was created.
    WORKTREE_MATERIALIZED = "worktree_materialized"
    #: A pre-fix ``EMPTY`` surface was seeded from the repository-root checkout.
    SEEDED = "seeded"
    #: A post-fix ``EMPTY`` surface was restored from the coordination branch tip.
    RESTORED_FROM_BRANCH = "restored_from_branch"


@dataclass(frozen=True, kw_only=True)
class SeedReport:
    """Outcome of one coordination-surface seed attempt (``specify_cli.coordination.coord_seed``, module-private).

    See data-model.md section 3.
    """

    #: Mission-relative paths copied from the repository-root checkout into
    #: the coordination Mission dir this call.
    carried: tuple[str, ...] = ()
    #: Repository-relative root-checkout paths reset to their committed state
    #: (dirty-tracked) or removed (untracked) after a successful carry.
    restored_root: tuple[str, ...] = ()
    #: Mission-relative paths restored from the coordination branch tip
    #: (post-fix ``EMPTY`` regression only).
    restored_from_branch: tuple[str, ...] = ()
    #: The commit id of the seed commit on the coordination branch, or
    #: ``None`` when nothing was carried or the commit was refused.
    coord_commit: str | None = None
    #: Human-readable warnings (conflicting non-log copies, a refused seed
    #: commit, …) -- always logged at ``WARNING`` by the caller too.
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, kw_only=True)
class WriteLocation:
    """Where a write of one :class:`~mission_runtime.MissionArtifactKind` must land.

    See ``contracts/write-location-accessor.md``. ``kw_only=True`` (binding
    correction): a later field (``checkout_root``, post-tasks squad P-M3)
    after a defaulted one (``seed``) would otherwise be a ``TypeError`` under
    plain positional dataclass field ordering.
    """

    #: Absolute Mission directory to write ``kind`` files into.
    path: Path
    #: Root of the checkout holding ``path`` -- the coordination worktree
    #: root for ``surface=COORD``, the repository-root checkout for
    #: ``surface=PRIMARY``. Consumers use this instead of deriving
    #: ``path.parent.parent`` (``test_no_write_side_rederivation.py``).
    checkout_root: Path
    surface: TopologySurface
    #: ``None`` for PRIMARY-partition kinds / non-coordination topologies.
    coord_state_before: CoordState | None
    establishment: Establishment
    #: Set only when ``establishment`` is ``SEEDED`` or ``RESTORED_FROM_BRANCH``.
    seed: SeedReport | None = None
