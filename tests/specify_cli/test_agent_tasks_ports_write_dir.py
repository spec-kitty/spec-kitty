"""``agent_tasks_ports.py`` writers route through the single write-location
accessor (coord-artifact-single-home-01M3V4BE, WP07, T040).

* ``RealCoordCommitRouter.feature_write_dir`` resolves through
  ``placement_seam(...).write_dir(STATUS_STATE)`` for both owned and
  non-owned handles -- never ``resolve_feature_dir_for_mission`` (retired)
  nor a bare ``read_dir`` (FR-014).
* ``CommitArtifactResult`` carries ``CommitRouterResult``'s additive
  ``surfaces`` / ``commit_hashes`` / ``reason`` fields through unchanged
  (contracts/commit-outcome.md).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from mission_runtime import MissionArtifactKind, MissionTopology
from specify_cli.agent_tasks_ports import (
    CommitArtifactResult,
    MissionHandle,
    RealCoordCommitRouter,
)
from specify_cli.coordination.commit_outcome import SurfaceOutcome
from specify_cli.coordination.commit_router import CommitRouterResult
from specify_cli.git.protection_policy import ProtectionPolicy
from tests._factories.coord_mission import event_ids, make_prefix_coord_mission

pytestmark = [pytest.mark.fast]


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _build_flat_mission(tmp_path: Path) -> tuple[Path, str]:
    """A minimal ``lanes`` (coord-less) mission -- never probes coordination."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / ".kittify").mkdir()
    (repo / ".kittify" / "config.yaml").write_text("agents:\n  available:\n    - claude\n", encoding="utf-8")
    slug = "flat-demo"
    feature_dir = repo / "kitty-specs" / slug
    feature_dir.mkdir(parents=True)
    meta = {
        "mission_id": "01FLATDEMO0000000000000000",
        "mission_slug": slug,
        "mission_type": "software-dev",
        "target_branch": "main",
        "friendly_name": "flat demo",
        "topology": MissionTopology.LANES.value,
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "init")
    return repo, slug


def test_feature_write_dir_on_prefix_empty_mission_seeds_and_returns_coord_dir(tmp_path: Path) -> None:
    """A pre-fix EMPTY coordination mission: ``feature_write_dir`` seeds the
    coordination surface (carrying the root checkout's records over) and
    returns the coordination Mission dir -- never the repository root
    checkout (the #5519-adjacent EMPTY-blind defect this WP fixes)."""
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty")
    root_ids_before = event_ids(coord.root_mission_dir / "status.events.jsonl")
    assert root_ids_before

    handle = MissionHandle(repo_root=coord.repo_root, mission_slug=coord.mission_dir_name)
    resolved = RealCoordCommitRouter().feature_write_dir(handle)

    assert resolved == coord.coord_mission_dir
    coord_ids_after = event_ids(resolved / "status.events.jsonl")
    assert set(root_ids_before) <= set(coord_ids_after)


def test_feature_write_dir_on_lanes_topology_is_byte_identical_to_primary(tmp_path: Path) -> None:
    """``lanes`` (coord-less) topology: ``feature_write_dir`` resolves to the
    SAME primary dir as before the accessor migration (C-008)."""
    repo, slug = _build_flat_mission(tmp_path)
    handle = MissionHandle(repo_root=repo, mission_slug=slug)

    resolved = RealCoordCommitRouter().feature_write_dir(handle)

    assert resolved == repo / "kitty-specs" / slug


def test_commit_artifact_result_carries_both_surfaces(tmp_path: Path) -> None:
    """A split (mixed-partition) commit's TWO surface outcomes both land on
    :attr:`CommitArtifactResult.surfaces` -- the port result is a thin,
    unchanged passthrough of ``CommitRouterResult.surfaces``."""
    primary_surface = SurfaceOutcome(
        surface="primary",
        branch="main",
        status="committed",
        commit_hash="a" * 40,
        committed=("kitty-specs/m/spec.md",),
    )
    coord_surface = SurfaceOutcome(
        surface="coordination",
        branch="kitty/mission-m-01ABCDEF",
        status="committed",
        commit_hash="b" * 40,
        committed=("kitty-specs/m/status.events.jsonl",),
    )

    def _fake_commit_fn(*_args: object, **_kwargs: object) -> CommitRouterResult:
        return CommitRouterResult(
            status="committed",
            placement_ref="main",
            commit_hash="a" * 40,
            commit_hashes=(("main", "a" * 40), ("kitty/mission-m-01ABCDEF", "b" * 40)),
            reason=None,
            surfaces=(primary_surface, coord_surface),
        )

    router = RealCoordCommitRouter(commit_fn=_fake_commit_fn)
    handle = MissionHandle(repo_root=tmp_path, mission_slug="m")
    policy = ProtectionPolicy(protected_branches=frozenset(), operator_hatch_active=False)

    result = router.commit_artifact(
        handle,
        [tmp_path / "kitty-specs" / "m" / "spec.md"],
        "chore: split commit",
        kind=MissionArtifactKind.SPEC,
        policy=policy,
    )

    assert isinstance(result, CommitArtifactResult)
    assert result.surfaces == (primary_surface, coord_surface)
    assert result.commit_hashes == (("main", "a" * 40), ("kitty/mission-m-01ABCDEF", "b" * 40))
    assert result.reason is None
