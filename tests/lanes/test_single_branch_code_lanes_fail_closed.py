"""Fail-closed guard: an unmigrated single_branch mission's code-lane
manifest is never silently rewritten OR allocated against (#5100 IC-02 /
WP05 T022, US5.3).

A ``single_branch`` mission whose ``lanes.json`` still carries a real code
lane (never re-stamped after #5100, or a hand-authored manifest) violates
Invariant T-1 (data-model.md): ``topology == single_branch`` implies
``has_code_lanes(manifest) is False``. Two writer chokepoints refuse rather
than silently treating the mismatch as data:

(a) :func:`~specify_cli.lanes.compute_and_persist.compute_and_write_lanes`
    (the ``finalize-tasks`` pure core) -- refuses BEFORE overwriting the
    existing on-disk manifest.
(b) :func:`~specify_cli.lanes.worktree_allocator.allocate_lane_worktree`
    (``implement``'s worktree-creation entry point) -- refuses BEFORE any
    git mutation.

Both raise :class:`mission_runtime.TopologyManifestMismatch` with
``error_code == "SINGLE_BRANCH_CODE_LANES_UNMIGRATED"`` and never create a
``.worktrees/`` entry.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mission_runtime import MissionTopology, TopologyManifestMismatch

from specify_cli.lanes.compute_and_persist import compute_and_write_lanes
from specify_cli.lanes.frozen_membership import FrozenLaneMembership
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import read_lanes_json, write_lanes_json
from specify_cli.lanes.worktree_allocator import allocate_lane_worktree
from specify_cli.ownership.models import OwnershipManifest, WorkProductKind
from specify_cli.status import WPMetadata

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_SLUG = "single-branch-unmigrated"
_MISSION_ID = "01JZZFAILCLOSEDTESTXXXXXXX"


def _seed_meta(repo_root: Path, *, topology: str) -> Path:
    feature_dir = repo_root / "kitty-specs" / _SLUG
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": _MISSION_ID,
                "mission_slug": _SLUG,
                "topology": topology,
                "target_branch": "main",
            }
        ),
        encoding="utf-8",
    )
    return feature_dir


def _code_lane_manifest() -> LanesManifest:
    """A hand-authored manifest with a real (non-repo-root) code lane.

    Models the #5100 drift: a ``single_branch`` mission whose ``lanes.json``
    was written before the re-stamp migration (or before #5100 landed) still
    carries a ``lane-a`` code lane instead of the canonical single
    ``lane-planning`` repo-root lane.
    """
    return LanesManifest(
        version=1,
        mission_slug=_SLUG,
        mission_id=_MISSION_ID,
        mission_branch=f"kitty/mission-{_SLUG}",
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=("WP01",),
                write_scope=("src/**",),
                predicted_surfaces=("core",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at="2026-09-28T00:00:00+00:00",
        computed_from="test",
    )


def _wp01_inputs() -> tuple[dict[str, OwnershipManifest], dict[str, WPMetadata]]:
    wp_manifests = {
        "WP01": OwnershipManifest(
            execution_mode=WorkProductKind.CODE_CHANGE,
            owned_files=("src/wp01.py",),
            authoritative_surface="src/wp01.py",
        )
    }
    wp_frontmatters = {"WP01": WPMetadata(work_package_id="WP01", title="A", execution_mode="code_change")}
    return wp_manifests, wp_frontmatters


def test_finalize_write_fails_closed_on_unmigrated_manifest(tmp_path: Path) -> None:
    """(a) ``compute_and_write_lanes`` refuses to overwrite an unmigrated
    single_branch mission's existing code-lane manifest; lanes.json is left
    untouched and no ``.worktrees/`` entry is created."""
    feature_dir = _seed_meta(tmp_path, topology="single_branch")
    write_lanes_json(feature_dir, _code_lane_manifest())
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "wp01.py").write_text("VALUE = 1\n", encoding="utf-8")
    wp_manifests, wp_frontmatters = _wp01_inputs()

    with pytest.raises(TopologyManifestMismatch) as excinfo:
        compute_and_write_lanes(
            feature_dir,
            tmp_path,
            _SLUG,
            wp_manifests,
            {"WP01": []},
            wp_frontmatters,
            {},
            "main",
            planning_commit_sha=None,
            mission_id=_MISSION_ID,
            topology=MissionTopology.SINGLE_BRANCH,
        )

    assert excinfo.value.error_code == "SINGLE_BRANCH_CODE_LANES_UNMIGRATED"
    assert not (tmp_path / ".worktrees").exists()
    on_disk = read_lanes_json(feature_dir)
    assert on_disk is not None
    assert [lane.lane_id for lane in on_disk.lanes] == ["lane-a"], "the pre-existing code-lane manifest must be untouched"


def test_allocate_lane_worktree_fails_closed_on_unmigrated_manifest(tmp_path: Path) -> None:
    """(b) ``allocate_lane_worktree`` refuses BEFORE any git mutation, so no
    ``.worktrees/`` directory is ever created."""
    _seed_meta(tmp_path, topology="single_branch")
    manifest = _code_lane_manifest()

    with pytest.raises(TopologyManifestMismatch) as excinfo:
        allocate_lane_worktree(tmp_path, _SLUG, "WP01", manifest)

    assert excinfo.value.error_code == "SINGLE_BRANCH_CODE_LANES_UNMIGRATED"
    assert not (tmp_path / ".worktrees").exists()


def test_control_lanes_topology_finalize_write_is_unaffected(tmp_path: Path) -> None:
    """Non-vacuity control: the IDENTICAL code-lane manifest shape under a
    genuine ``lanes`` mission is never refused -- the guard discriminates on
    topology, not on manifest shape alone."""
    feature_dir = _seed_meta(tmp_path, topology="lanes")
    write_lanes_json(feature_dir, _code_lane_manifest())
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "wp01.py").write_text("VALUE = 1\n", encoding="utf-8")
    wp_manifests, wp_frontmatters = _wp01_inputs()

    lanes_path, lanes_manifest = compute_and_write_lanes(
        feature_dir,
        tmp_path,
        _SLUG,
        wp_manifests,
        {"WP01": []},
        wp_frontmatters,
        {},
        "main",
        planning_commit_sha=None,
        mission_id=_MISSION_ID,
        topology=MissionTopology.LANES,
        frozen=FrozenLaneMembership.empty(),
    )

    assert lanes_path == feature_dir / "lanes.json"
    assert lanes_manifest.lanes  # a real lane got (re)computed, not refused


def test_allocate_lane_worktree_fails_closed_on_corrupt_meta(tmp_path: Path) -> None:
    """(b') A corrupt ``meta.json`` is not "nothing to enforce": the guard
    raises the typed :class:`MissionMetaReadError` BEFORE any git mutation
    rather than silently skipping the topology check."""
    from specify_cli.core.paths import MissionMetaReadError

    feature_dir = tmp_path / "kitty-specs" / _SLUG
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text("{not json", encoding="utf-8")

    with pytest.raises(MissionMetaReadError):
        allocate_lane_worktree(tmp_path, _SLUG, "WP01", _code_lane_manifest())

    assert not (tmp_path / ".worktrees").exists()
