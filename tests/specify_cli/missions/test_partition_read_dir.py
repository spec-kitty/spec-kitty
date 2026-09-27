"""``resolve_partition_read_dir``: the single handed-dir partition read authority (#5180).

Each cell of the resolver's contract, on real git fixtures:

* no workspace root → the handed dir (flat self-home);
* a phantom resolved partition (foreign ambient anchor, #154) → the handed dir;
* phantom resolved partition AND missing handed dir → the resolved path, unguessed;
* flat / single-branch topology → the primary dir;
* materialised coord → the coord husk, never the PRIMARY decoy log;
* unmaterialised / deleted coord → the seam's typed error propagates.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from mission_runtime import MissionArtifactKind
from specify_cli.coordination.surface_resolver import (
    CoordinationBranchDeleted,
    CoordinationWorktreeUnmaterialized,
)
from specify_cli.missions._read_path_resolver import resolve_partition_read_dir
from tests.integration.coord_topology_fixture import (  # noqa: F401 -- pytest fixtures
    CoordTopologyContext,
    FlatTopologyContext,
    coord_topology_mission,
    flat_topology_mission,
)

# Re-export the fixtures so pytest discovers them in this module.
__all__ = ["coord_topology_mission", "flat_topology_mission"]

pytestmark = pytest.mark.git_repo

_STATUS = MissionArtifactKind.STATUS_STATE


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _foreign_anchor_dir(tmp_path: Path, *, create: bool) -> Path:
    ambient = tmp_path / "ambient-checkout"
    ambient.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(ambient)], check=True)
    feature_dir = ambient / "repo" / "kitty-specs" / "001-foreign-anchor"
    if create:
        feature_dir.mkdir(parents=True)
    return feature_dir


def test_no_workspace_root_returns_handed_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.core.paths import WorkspaceRootNotFound
    from specify_cli.missions import _read_path_resolver

    def _no_root(_path: Path) -> Path:
        raise WorkspaceRootNotFound("no git ancestor")

    monkeypatch.setattr(_read_path_resolver, "resolve_canonical_root", _no_root)
    feature_dir = tmp_path / "kitty-specs" / "001-bare"

    assert resolve_partition_read_dir(feature_dir, _STATUS) == feature_dir


def test_phantom_partition_degrades_to_existing_handed_dir(tmp_path: Path) -> None:
    feature_dir = _foreign_anchor_dir(tmp_path, create=True)

    assert resolve_partition_read_dir(feature_dir, _STATUS) == feature_dir


def test_phantom_partition_with_missing_handed_dir_returns_resolved_path(tmp_path: Path) -> None:
    feature_dir = _foreign_anchor_dir(tmp_path, create=False)

    resolved = resolve_partition_read_dir(feature_dir, _STATUS)

    assert resolved != feature_dir
    assert resolved == tmp_path / "ambient-checkout" / "kitty-specs" / "001-foreign-anchor"
    assert not resolved.exists()


def test_flat_topology_resolves_primary(flat_topology_mission: FlatTopologyContext) -> None:
    ctx = flat_topology_mission

    assert resolve_partition_read_dir(ctx.primary_feature_dir, _STATUS) == ctx.primary_feature_dir


def test_materialised_coord_resolves_husk_not_primary_decoy(
    coord_topology_mission: CoordTopologyContext,
) -> None:
    ctx = coord_topology_mission

    resolved = resolve_partition_read_dir(ctx.primary_feature_dir, _STATUS)

    assert resolved == ctx.coord_feature_dir
    assert (resolved / "status.events.jsonl").read_text(encoding="utf-8") == ctx.status_events_path.read_text(encoding="utf-8")
    assert resolved != ctx.decoy_events_path.parent


def test_primary_kind_on_coord_topology_resolves_primary(
    coord_topology_mission: CoordTopologyContext,
) -> None:
    ctx = coord_topology_mission

    resolved = resolve_partition_read_dir(ctx.primary_feature_dir, MissionArtifactKind.PRIMARY_METADATA)

    assert resolved == ctx.primary_feature_dir


def test_unmaterialised_coord_raises(coord_topology_mission: CoordTopologyContext) -> None:
    ctx = coord_topology_mission
    _git(ctx.repo, "worktree", "remove", "--force", str(ctx.coord_feature_dir.parent.parent))

    with pytest.raises(CoordinationWorktreeUnmaterialized):
        resolve_partition_read_dir(ctx.primary_feature_dir, _STATUS)


def test_deleted_coord_branch_raises(coord_topology_mission: CoordTopologyContext) -> None:
    ctx = coord_topology_mission
    _git(ctx.repo, "worktree", "remove", "--force", str(ctx.coord_feature_dir.parent.parent))
    _git(ctx.repo, "branch", "-D", ctx.coord_branch)

    with pytest.raises(CoordinationBranchDeleted):
        resolve_partition_read_dir(ctx.primary_feature_dir, _STATUS)
