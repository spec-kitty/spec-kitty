"""The status read door finds an owned coordination Mission (WP02, FR-007, FR-005/FR-006).

Mission ``runtime-status-read-door-01M73HHB``; ADR ``2026-11-06-2`` Amendment 2026-11-11. The
fixture is the WP05 matrix Mission (``tests/status/test_status_read_matrix.py``): the
coordination branch carries the authority (``planned -> claimed -> in_progress``). An owned
checkout P is then added and the Mission directory is removed from the repository root
checkout R, so the Mission exists only in P while the coordination branch and its worktree stay
under R. The door must take the Mission directory, ``meta.json``, the landed check and the
pre-seed fallback from P, and probe the coordination state under R.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from mission_runtime import MissionTopology
from mission_runtime.owned_checkout import OwnedCheckout
from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted
from specify_cli.status.read_surface import StatusReadSource, StatusReadSurface, materialize_status, resolve_status_read
from tests.status.test_status_read_matrix import (
    COORD_BRANCH,
    EMPTY,
    KITTY_SPECS,
    LANES_WITH_COORD,
    MATERIALIZED,
    SLUG,
    UNMATERIALIZED,
    build_matrix_mission,
    git,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

OWNED_BRANCH = "owned/matrix"
COORD_TOPOLOGIES = [MissionTopology.COORD, MissionTopology.LANES_WITH_COORD]
COORD_REF = f"refs/heads/{COORD_BRANCH}"


def _owned_only_coordination_mission(base: Path, topology: MissionTopology, coord_state: str = UNMATERIALIZED) -> tuple[Path, OwnedCheckout]:
    """Build the matrix Mission, add owned checkout P, then remove the Mission from R's checkout.

    Returns ``(R, fact)``. The fact is minted the way ``placement_seam`` tests mint one (the
    validator itself is ``specify_cli.core.owned_mission``'s, out of this door's scope).
    """
    mission = build_matrix_mission(base, LANES_WITH_COORD, coord_state)
    repo = mission.repo
    owned_root = base / "P"
    git(repo, "worktree", "add", "-q", "-b", OWNED_BRANCH, str(owned_root), "main")
    owned_dir = owned_root / KITTY_SPECS / SLUG
    if topology is not MissionTopology.LANES_WITH_COORD:
        _update_meta(owned_dir, topology=topology.value)
    git(repo, "rm", "-rq", f"{KITTY_SPECS}/{SLUG}")
    git(repo, "commit", "-q", "-m", "the Mission lives only in the owned checkout")
    assert not (repo / KITTY_SPECS / SLUG).exists()
    fact = OwnedCheckout._mint(
        repository_root=repo,
        owned_root=owned_root,
        mission_dir=owned_dir,
        mission_slug=SLUG,
        topology=topology,
        write_branch=OWNED_BRANCH,
    )
    return repo, fact


def _update_meta(mission_dir: Path, **fields: object) -> None:
    meta_path = mission_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta.update(fields)
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


def _coord_worktree(repo: Path) -> Path:
    return repo / ".worktrees" / f"{SLUG}-coord"


def _wp01_lane(surface: StatusReadSurface) -> object:
    return materialize_status(surface).work_packages["WP01"]["lane"]


# ---------------------------------------------------------------------------
# T006 (FR-007, red first): an owned-only coordination Mission resolves
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("topology", COORD_TOPOLOGIES, ids=lambda t: t.value)
def test_owned_only_coordination_mission_resolves(tmp_path: Path, topology: MissionTopology) -> None:
    """The Mission exists only in P: the door still resolves it and reads the committed lanes."""
    repo, fact = _owned_only_coordination_mission(tmp_path, topology)

    surface = resolve_status_read(repo, SLUG, owned=fact)

    assert surface.source is StatusReadSource.COORD_BRANCH_REF
    assert surface.ref == f"refs/heads/{COORD_BRANCH}"
    assert surface.topology is topology
    assert surface.repo_root.resolve() == repo.resolve()
    snapshot = materialize_status(surface)
    assert snapshot.work_packages["WP01"]["lane"] == "in_progress"


# ---------------------------------------------------------------------------
# T008: each owned coordination cell (data model, owned columns)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("topology", COORD_TOPOLOGIES, ids=lambda t: t.value)
def test_owned_materialized_reads_the_coordination_worktree_under_r(tmp_path: Path, topology: MissionTopology) -> None:
    repo, fact = _owned_only_coordination_mission(tmp_path, topology, MATERIALIZED)

    surface = resolve_status_read(repo, SLUG, owned=fact)

    assert surface.source is StatusReadSource.COORD_WORKTREE
    assert surface.path is not None
    assert surface.path.resolve() == (_coord_worktree(repo) / KITTY_SPECS / SLUG).resolve()
    assert _wp01_lane(surface) == "in_progress"


@pytest.mark.parametrize("topology", COORD_TOPOLOGIES, ids=lambda t: t.value)
def test_owned_empty_coordination_worktree_reads_the_branch(tmp_path: Path, topology: MissionTopology) -> None:
    repo, fact = _owned_only_coordination_mission(tmp_path, topology, MATERIALIZED)
    shutil.rmtree(_coord_worktree(repo) / KITTY_SPECS / SLUG)

    surface = resolve_status_read(repo, SLUG, owned=fact)

    assert surface.source is StatusReadSource.COORD_BRANCH_REF
    assert surface.ref == COORD_REF
    assert _wp01_lane(surface) == "in_progress"


@pytest.mark.parametrize("topology", COORD_TOPOLOGIES, ids=lambda t: t.value)
def test_owned_removed_coordination_worktree_reads_the_branch(tmp_path: Path, topology: MissionTopology) -> None:
    repo, fact = _owned_only_coordination_mission(tmp_path, topology, MATERIALIZED)
    git(repo, "worktree", "remove", "--force", str(_coord_worktree(repo)))

    surface = resolve_status_read(repo, SLUG, owned=fact)

    assert surface.source is StatusReadSource.COORD_BRANCH_REF
    assert surface.ref == COORD_REF
    assert _wp01_lane(surface) == "in_progress"


@pytest.mark.parametrize("topology", COORD_TOPOLOGIES, ids=lambda t: t.value)
def test_owned_deleted_coordination_branch_not_landed_refuses(tmp_path: Path, topology: MissionTopology) -> None:
    repo, fact = _owned_only_coordination_mission(tmp_path, topology)
    git(repo, "branch", "-D", COORD_BRANCH)

    with pytest.raises(CoordinationBranchDeleted) as refused:
        resolve_status_read(repo, SLUG, owned=fact)
    assert Path(refused.value.primary_candidate) == fact.mission_dir


@pytest.mark.parametrize("topology", COORD_TOPOLOGIES, ids=lambda t: t.value)
def test_owned_landed_reads_the_owned_mission_dir(tmp_path: Path, topology: MissionTopology) -> None:
    """``merged_at`` in P's meta.json: the landed check reads P, so the deleted branch is not refused."""
    repo, fact = _owned_only_coordination_mission(tmp_path, topology)
    _update_meta(fact.mission_dir, merged_at="2026-11-10T00:00:00+00:00")
    git(repo, "branch", "-D", COORD_BRANCH)

    surface = resolve_status_read(repo, SLUG, owned=fact)

    assert surface.source is StatusReadSource.CONSOLIDATED_TARGET
    assert surface.path == fact.mission_dir
    assert surface.repo_root.resolve() == repo.resolve()


@pytest.mark.parametrize("topology", COORD_TOPOLOGIES, ids=lambda t: t.value)
def test_owned_pre_seed_falls_back_to_the_owned_mission_dir(tmp_path: Path, topology: MissionTopology) -> None:
    """The coordination branch holds no log yet: the declared fallback is P's directory, never R's."""
    repo, fact = _owned_only_coordination_mission(tmp_path, topology, EMPTY)

    surface = resolve_status_read(repo, SLUG, owned=fact)

    assert surface.source is StatusReadSource.WRITE_CHECKOUT
    assert surface.path == fact.mission_dir
    assert surface.fallback_reason is not None
    assert _wp01_lane(surface) == "planned"


@pytest.mark.parametrize("topology", [MissionTopology.SINGLE_BRANCH, MissionTopology.LANES], ids=lambda t: t.value)
def test_owned_coordination_less_topology_is_unchanged(tmp_path: Path, topology: MissionTopology) -> None:
    repo, fact = _owned_only_coordination_mission(tmp_path, topology)

    surface = resolve_status_read(repo, SLUG, owned=fact)

    assert surface.source is StatusReadSource.WRITE_CHECKOUT
    assert surface.path == fact.mission_dir
    assert surface.ref is None
    assert surface.fallback_reason is None
