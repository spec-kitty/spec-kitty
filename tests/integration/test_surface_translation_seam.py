"""WP02 — the surface→filesystem translation seam (the true schema root).

Behavioural coverage for the ONE affirmative, stamped surface resolver
(``mission_runtime.resolve_artifact_surface``) and the ONE total member→path
translation (``mission_runtime.resolution.translate_surface``), against **un-stubbed** git
fixtures (NFR-008 — no resolver is patched here).

Three concerns, each pinned to a contract clause:

* **Totality / no phantom** (data-model.md "TopologySurface", contract C4): every
  ``TopologySurface`` member translates to a real location — a member the seam
  cannot locate would be a phantom, and this is the operator's resolvability
  signal. ``LANE`` / ``CONSOLIDATED`` / ``TEMP`` have no production caller yet, so
  the totality test IS what makes "declared with the seam, not before it" true.
* **Four CoordState answers** (contract C3 / GEC-3): ``DELETED`` raises,
  ``EMPTY`` / ``UNMATERIALIZED`` resolve primary + stamp PRIMARY, ``MATERIALIZED``
  resolves coord + stamp COORD, and flat resolves primary affirmatively (AH-2).
* **AH-1 read/write symmetry** (from #2874 — the one preservation invariant with
  no other acceptance signal in this mission): ``read_surface == write_surface``
  for every ``MissionArtifactKind``, and the seam's stamp agrees with that
  symmetric home.

Git/mission scaffolding is reused verbatim from ``test_placement_partition_
golden_path`` (do NOT duplicate the git primitives), mirroring
``tests/mission_runtime/test_coord_read_seam.py``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from mission_runtime import (
    CommitTarget,
    MissionArtifactKind,
    MissionTopology,
    TopologySurface,
    resolve_artifact_surface,
)
from mission_runtime.artifacts import artifact_home_for
from mission_runtime.resolution import ResolvedSurface, SurfaceLocations, translate_surface
from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted, CoordinationWorktreeUnmaterialized
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.core.mission_creation import MissionCreationResult

from tests.integration.test_placement_partition_golden_path import (
    _create_mission,
    _init_git_repo,
    _materialize_coord_worktree,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_WORK_BRANCH = "surface-translation-seam-work"


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo, branch=_WORK_BRANCH)
    return repo


# ---------------------------------------------------------------------------
# Totality / no phantom — translate_surface handles EVERY member (contract C4).
# ---------------------------------------------------------------------------


def _all_locations(tmp_path: Path) -> tuple[SurfaceLocations, dict[TopologySurface, Path]]:
    """Build a SurfaceLocations with a distinct real dir per member."""
    expected: dict[TopologySurface, Path] = {}
    fields: dict[str, Path] = {}
    for member in TopologySurface:
        member_dir = tmp_path / member.value
        member_dir.mkdir()
        expected[member] = member_dir
        fields[member.value] = member_dir
    locations = SurfaceLocations(
        primary=fields["primary"],
        coord=fields["coord"],
        lane=fields["lane"],
        consolidated=fields["consolidated"],
        temp=fields["temp"],
    )
    return locations, expected


def test_every_surface_member_translates_to_a_real_location(tmp_path: Path) -> None:
    """Totality: no phantom — every TopologySurface member resolves to its dir."""
    locations, expected = _all_locations(tmp_path)
    for member in TopologySurface:
        resolved = translate_surface(member, locations)
        assert resolved == expected[member]
        assert resolved.exists()
    # Non-vacuity: the members mapped to DISTINCT locations, not one shared dir.
    assert len({expected[member] for member in TopologySurface}) == len(list(TopologySurface))


def test_planned_members_are_declared_not_phantom(tmp_path: Path) -> None:
    """The three members landing with the seam (LANE/CONSOLIDATED/TEMP) resolve."""
    locations, expected = _all_locations(tmp_path)
    for member in (
        TopologySurface.LANE,
        TopologySurface.CONSOLIDATED,
        TopologySurface.TEMP,
    ):
        assert translate_surface(member, locations) == expected[member]


def test_translate_refuses_a_member_with_no_resolved_location(tmp_path: Path) -> None:
    """A member whose location is ``None`` is refused, never guessed."""
    primary = tmp_path / "primary"
    primary.mkdir()
    locations = SurfaceLocations(primary=primary)  # coord/lane/... stay None
    assert translate_surface(TopologySurface.PRIMARY, locations) == primary
    with pytest.raises(ValueError, match="No resolved location for surface 'coord'"):
        translate_surface(TopologySurface.COORD, locations)


# ---------------------------------------------------------------------------
# Four CoordState answers (contract C3 / GEC-3), on un-stubbed git fixtures.
# ---------------------------------------------------------------------------


def _coord_mission_dir(coord_root: Path, mission_slug: str) -> Path:
    return coord_root / "kitty-specs" / mission_slug


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=True)


def _remove_coord_worktree(repo: Path, result: MissionCreationResult) -> None:
    """Remove the coordination worktree create materialized, keeping the branch.

    #5440: create now seeds the status log in a materialized coordination
    worktree; tests needing an unmaterialized (or deletable) branch remove it.
    """
    mid8 = str(result.meta["mission_id"])[:8]
    _git(repo, "worktree", "remove", "--force", str(CoordinationWorkspace.worktree_path(repo, result.mission_slug, mid8)))


def test_materialized_coord_resolves_coord_and_stamps_coord(tmp_path: Path) -> None:
    """MATERIALIZED → the coordination mission dir, stamped COORD."""
    repo = _repo(tmp_path)
    result = _create_mission(repo, "seam-materialized", MissionTopology.COORD)
    coord_root = _materialize_coord_worktree(repo, result)
    coord_dir = _coord_mission_dir(coord_root, result.mission_slug)
    coord_dir.mkdir(parents=True, exist_ok=True)
    (coord_dir / "issue-matrix.md").write_text("# issues\n", encoding="utf-8")

    resolved = resolve_artifact_surface(repo, result.mission_slug, MissionArtifactKind.ISSUE_MATRIX)
    assert isinstance(resolved, ResolvedSurface)
    assert resolved.surface_kind is TopologySurface.COORD
    assert resolved.path.resolve() == coord_dir.resolve()
    # Non-vacuity: it is NOT the primary checkout under materialised coord.
    assert resolved.path.resolve() != result.feature_dir.resolve()


def test_empty_coord_resolves_primary_and_stamps_primary(tmp_path: Path) -> None:
    """EMPTY (coord root present, mission dir absent) → primary + stamp PRIMARY."""
    repo = _repo(tmp_path)
    baseline = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, check=True, text=True).stdout.strip()
    result = _create_mission(repo, "seam-empty", MissionTopology.COORD)
    assert result.coordination_branch is not None
    # #5440: create commits the mission dir (status log) on the coord branch; reset
    # the branch to the pre-create baseline so it carries no mission dir → EMPTY.
    _remove_coord_worktree(repo, result)
    _git(repo, "branch", "-f", result.coordination_branch, baseline)
    coord_root = _materialize_coord_worktree(repo, result)
    assert not _coord_mission_dir(coord_root, result.mission_slug).exists()

    resolved = resolve_artifact_surface(repo, result.mission_slug, MissionArtifactKind.ISSUE_MATRIX)
    assert resolved.surface_kind is TopologySurface.PRIMARY
    assert resolved.path.resolve() == result.feature_dir.resolve()


def test_unmaterialized_coord_refuses_fail_closed(
    tmp_path: Path,
) -> None:
    """UNMATERIALIZED (coord branch exists, worktree absent) → fail closed.

    ADR ``2026-09-24-2-coord-read-fail-closed`` (#4959) retired the former
    "resolve to PRIMARY and stamp PRIMARY" substitution: a coord-partition kind
    now raises ``CoordinationWorktreeUnmaterialized`` rather than handing back
    the empty primary checkout as if it were the coord surface.
    """
    repo = _repo(tmp_path)
    result = _create_mission(repo, "seam-unmaterialized", MissionTopology.COORD)
    # Remove the coord worktree create materialised → coord root absent, branch present.
    _remove_coord_worktree(repo, result)

    with pytest.raises(CoordinationWorktreeUnmaterialized) as exc_info:
        resolve_artifact_surface(repo, result.mission_slug, MissionArtifactKind.ISSUE_MATRIX)
    assert exc_info.value.error_code == "COORDINATION_WORKTREE_UNMATERIALIZED"


def test_deleted_coord_branch_raises_fail_loud(tmp_path: Path) -> None:
    """DELETED (declared coord branch gone from git) → raises, no primary fallback."""
    repo = _repo(tmp_path)
    result = _create_mission(repo, "seam-deleted", MissionTopology.COORD)
    assert result.coordination_branch is not None
    # #5440: a checked-out branch cannot be deleted; remove the coord worktree first.
    _remove_coord_worktree(repo, result)
    # Delete the declared coordination branch; leave meta.json declaring it.
    subprocess.run(
        ["git", "-C", str(repo), "branch", "-D", result.coordination_branch],
        capture_output=True,
        check=True,
    )

    with pytest.raises(CoordinationBranchDeleted) as exc_info:
        resolve_artifact_surface(repo, result.mission_slug, MissionArtifactKind.ISSUE_MATRIX)
    assert exc_info.value.error_code == "COORDINATION_BRANCH_DELETED"


def test_flat_topology_resolves_primary_affirmatively(tmp_path: Path) -> None:
    """AH-2: a coord-less (SINGLE_BRANCH) mission resolves primary affirmatively."""
    repo = _repo(tmp_path)
    result = _create_mission(repo, "seam-flat", MissionTopology.SINGLE_BRANCH)

    resolved = resolve_artifact_surface(repo, result.mission_slug, MissionArtifactKind.ISSUE_MATRIX)
    assert resolved.surface_kind is TopologySurface.PRIMARY
    assert resolved.path.resolve() == result.feature_dir.resolve()


def test_primary_kind_ignores_deleted_coord_branch(tmp_path: Path) -> None:
    """A PRIMARY-partition kind never transits coord: a deleted coord branch is
    irrelevant to reading it (AH-1/AH-3 — no probe, no raise)."""
    repo = _repo(tmp_path)
    result = _create_mission(repo, "seam-primary-kind", MissionTopology.COORD)
    assert result.coordination_branch is not None
    # #5440: a checked-out branch cannot be deleted; remove the coord worktree first.
    _remove_coord_worktree(repo, result)
    subprocess.run(
        ["git", "-C", str(repo), "branch", "-D", result.coordination_branch],
        capture_output=True,
        check=True,
    )

    resolved = resolve_artifact_surface(repo, result.mission_slug, MissionArtifactKind.SPEC)
    assert resolved.surface_kind is TopologySurface.PRIMARY
    assert resolved.path.resolve() == result.feature_dir.resolve()


# ---------------------------------------------------------------------------
# AH-1 read/write symmetry (#2874) — the one preservation invariant.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", list(MissionArtifactKind))
def test_ah1_home_is_read_write_symmetric(kind: MissionArtifactKind) -> None:
    """AH-1: ``read_surface == write_surface`` for every kind (topology-blind)."""
    home = artifact_home_for(kind, CommitTarget(ref="target-branch"))
    assert home.read_surface == home.write_surface


@pytest.fixture(scope="module")
def _materialized_coord_mission(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, str, Path]:
    """A MATERIALIZED coord mission with its coord mission dir present.

    Module-scoped so the AH-1 parametrisation over every kind does not re-create a
    mission per kind (mission creation is real git — kept to one build).
    """
    tmp_path = tmp_path_factory.mktemp("ah1-coord")
    repo = _repo(tmp_path)
    result = _create_mission(repo, "seam-ah1", MissionTopology.COORD)
    coord_root = _materialize_coord_worktree(repo, result)
    coord_dir = _coord_mission_dir(coord_root, result.mission_slug)
    coord_dir.mkdir(parents=True, exist_ok=True)
    (coord_dir / "issue-matrix.md").write_text("# issues\n", encoding="utf-8")
    return repo, result.mission_slug, result.feature_dir


@pytest.mark.parametrize("kind", list(MissionArtifactKind))
def test_ah1_seam_stamp_agrees_with_symmetric_home(
    _materialized_coord_mission: tuple[Path, str, Path],
    kind: MissionArtifactKind,
) -> None:
    """The seam's read stamp agrees with the (symmetric) declared home.

    On a MATERIALIZED coord mission the seam resolves coord-partition kinds to
    COORD and primary-partition kinds to PRIMARY — matching ``read_surface`` (which
    equals ``write_surface`` by AH-1). This is the read/write symmetry the total
    rebuild is most likely to break, with no other acceptance signal in the mission.
    """
    repo, mission_slug, _feature_dir = _materialized_coord_mission
    home = artifact_home_for(kind, CommitTarget(ref="target-branch"))
    resolved = resolve_artifact_surface(repo, mission_slug, kind)
    assert resolved.surface_kind == home.read_surface == home.write_surface
