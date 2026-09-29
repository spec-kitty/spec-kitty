"""Re-finalize preserves the Mission branch (FR-010, FR-011, FR-012).

US3 AS1/AS2 + US5 AS2: ``compute_and_write_lanes`` keeps ``previous_lanes.mission_branch``
across a re-finalize instead of recomposing it from a since-backfilled
``mission_id`` (research Part A §4: recomposing names a branch
``_ensure_mission_branch`` never created, and later lanes fork from an empty
Mission branch). ``status/aggregate.py``'s destination-ref composition prefers
the same recorded value, and raises a typed :class:`BranchIdentityUnresolved`
refusal instead of a raw ``ValueError`` when it must recompose from an invalid
(< 8 char) identity (U1).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from mission_runtime import MissionTopology

from specify_cli.lanes.branch_naming import BranchIdentityUnresolved
from specify_cli.lanes.compute import LaneComputationError
from specify_cli.lanes.compute_and_persist import (
    _preserved_mission_branch,
    compute_and_write_lanes,
)
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import read_lanes_json
from specify_cli.lanes.worktree_allocator import allocate_lane_worktree
from specify_cli.migration.backfill_identity import backfill_mission
from specify_cli.ownership.models import OwnershipManifest, WorkProductKind
from specify_cli.status import WPMetadata
from specify_cli.status.aggregate import MissionStatus

pytestmark = [pytest.mark.unit, pytest.mark.fast, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------


def _wp_manifest(owned_files: tuple[str, ...], authoritative_surface: str) -> OwnershipManifest:
    return OwnershipManifest(
        execution_mode=WorkProductKind.CODE_CHANGE,
        owned_files=owned_files,
        authoritative_surface=authoritative_surface,
    )


def _make_repo_with_owned_files(tmp_path: Path) -> Path:
    (tmp_path / "src" / "wp01").mkdir(parents=True)
    (tmp_path / "src" / "wp01" / "mod.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "src" / "wp02").mkdir(parents=True)
    (tmp_path / "src" / "wp02" / "mod.py").write_text("y = 2\n", encoding="utf-8")
    return tmp_path


def _feature_dir(tmp_path: Path, mission_slug: str) -> Path:
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    return feature_dir


def _finalize(
    tmp_path: Path,
    feature_dir: Path,
    mission_slug: str,
    *,
    mission_id: str | None,
) -> LanesManifest:
    wp_manifests = {
        "WP01": _wp_manifest(("src/wp01/**",), "src/wp01/"),
        "WP02": _wp_manifest(("src/wp02/**",), "src/wp02/"),
    }
    wp_frontmatters = {
        "WP01": WPMetadata(work_package_id="WP01", title="WP01"),
        "WP02": WPMetadata(work_package_id="WP02", title="WP02"),
    }
    _lanes_path, manifest = compute_and_write_lanes(
        feature_dir,
        tmp_path,
        mission_slug,
        wp_manifests,
        {"WP01": [], "WP02": []},
        wp_frontmatters,
        {"WP01": "WP01 body", "WP02": "WP02 body"},
        "main",
        planning_commit_sha=None,
        mission_id=mission_id,
        topology=MissionTopology.LANES,
    )
    return manifest


# ---------------------------------------------------------------------------
# Re-finalize tests
# ---------------------------------------------------------------------------


class TestRefinalizePreservesMissionBranch:
    def test_backfill_then_refinalize_keeps_mission_branch_byte_identical(self, tmp_path: Path) -> None:
        """US3 AS1: backfilling identity then re-finalizing must not rename the branch."""
        repo_root = _make_repo_with_owned_files(tmp_path)
        mission_slug = "057-foo"
        feature_dir = _feature_dir(tmp_path, mission_slug)
        (feature_dir / "meta.json").write_text(json.dumps({}), encoding="utf-8")

        first = _finalize(repo_root, feature_dir, mission_slug, mission_id=None)
        assert first.mission_branch == "kitty/mission-057-foo"

        result = backfill_mission(feature_dir)
        assert result.action == "wrote"
        assert result.mission_id is not None

        second = _finalize(repo_root, feature_dir, mission_slug, mission_id=result.mission_id)

        assert second.mission_branch == first.mission_branch == "kitty/mission-057-foo"

        reread = read_lanes_json(feature_dir)
        assert reread is not None
        assert reread.mission_branch == "kitty/mission-057-foo"

    def test_first_time_finalize_of_modern_mission_matches_todays_golden(self, tmp_path: Path) -> None:
        """US3 AS2: a first finalize with identity present from the start is unchanged.

        The golden is a LITERAL recorded today, not computed by the code under
        test.
        """
        repo_root = _make_repo_with_owned_files(tmp_path)
        mission_slug = "foo-01KV6510"
        feature_dir = _feature_dir(tmp_path, mission_slug)

        manifest = _finalize(repo_root, feature_dir, mission_slug, mission_id="01KV6510ATWWFXS3K5ZJ9E5008")

        assert manifest.mission_branch == "kitty/mission-foo-01KV6510"

    def test_refinalize_lane_worktree_parents_from_recorded_mission_branch(self, tmp_path: Path) -> None:
        """US3 AS1 (continued): lane creation forks from the RECORDED branch, not a phantom mid8 one."""
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)

        mission_slug = "057-foo"
        feature_dir = _feature_dir(repo, mission_slug)
        (feature_dir / "meta.json").write_text(json.dumps({}), encoding="utf-8")
        (repo / "src" / "wp01").mkdir(parents=True)
        (repo / "src" / "wp01" / "mod.py").write_text("x = 1\n", encoding="utf-8")
        (repo / "src" / "wp02").mkdir(parents=True)
        (repo / "src" / "wp02" / "mod.py").write_text("y = 2\n", encoding="utf-8")
        _git_commit_all(repo, "seed owned files")

        first = _finalize(repo, feature_dir, mission_slug, mission_id=None)
        assert first.mission_branch == "kitty/mission-057-foo"

        result = backfill_mission(feature_dir)
        second = _finalize(repo, feature_dir, mission_slug, mission_id=result.mission_id)
        assert second.mission_branch == "kitty/mission-057-foo"

        allocate_lane_worktree(repo, mission_slug, "WP01", second)

        # The recorded branch was created ...
        subprocess.run(
            ["git", "rev-parse", "--verify", "refs/heads/kitty/mission-057-foo"],
            cwd=str(repo),
            check=True,
            capture_output=True,
        )
        # ... and the phantom mid8-recomposed branch was NOT.
        phantom = subprocess.run(
            ["git", "rev-parse", "--verify", f"refs/heads/kitty/mission-foo-{result.mission_id[:8]}"],
            cwd=str(repo),
            capture_output=True,
        )
        assert phantom.returncode != 0, "a phantom mid8-recomposed Mission branch must not be created"


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", str(path)], capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(path), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(path), capture_output=True, check=True)
    (path / "README.md").write_text("init\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(path), capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(path), capture_output=True, check=True)
    subprocess.run(["git", "branch", "-M", "main"], cwd=str(path), capture_output=True, check=True)


def _git_commit_all(path: Path, message: str) -> None:
    subprocess.run(["git", "add", "."], cwd=str(path), capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", message], cwd=str(path), capture_output=True, check=True)


# ---------------------------------------------------------------------------
# _preserved_mission_branch unit tests
# ---------------------------------------------------------------------------


def _manifest(mission_branch: str) -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug="test-mission",
        mission_id=None,
        mission_branch=mission_branch,
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=("WP01",),
                write_scope=("src/**",),
                predicted_surfaces=(),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at="2026-04-03T12:00:00+00:00",
        computed_from="test",
    )


class TestPreservedMissionBranchHelper:
    # #5100 WP05 (out-of-map edit to WP03's file, fold B3): ``topology`` is
    # now a required keyword -- these tests pin the pre-existing LANES
    # preserve-on-re-finalize behaviour, which the SINGLE_BRANCH-only new
    # branch leaves byte-identical. The SINGLE_BRANCH short-circuit itself
    # is pinned in ``tests/lanes/test_compute_lanes_single_branch.py``.
    def test_no_previous_manifest_returns_computed(self) -> None:
        assert _preserved_mission_branch(None, "kitty/mission-computed", topology=MissionTopology.LANES) == "kitty/mission-computed"

    def test_previous_with_empty_mission_branch_returns_computed(self) -> None:
        previous = _manifest("")
        assert _preserved_mission_branch(previous, "kitty/mission-computed", topology=MissionTopology.LANES) == "kitty/mission-computed"

    def test_previous_with_value_wins_over_computed(self) -> None:
        previous = _manifest("kitty/mission-057-foo")
        assert _preserved_mission_branch(previous, "kitty/mission-foo-01KV6510", topology=MissionTopology.LANES) == "kitty/mission-057-foo"

    def test_single_branch_never_preserves_stale_value(self) -> None:
        """Fold B3: SINGLE_BRANCH always takes the freshly-computed value."""
        previous = _manifest("kitty/mission-057-foo")
        computed = "issue-5100-single-branch-topology"
        assert _preserved_mission_branch(previous, computed, topology=MissionTopology.SINGLE_BRANCH) == computed


# ---------------------------------------------------------------------------
# U1 -- invalid (< 8 char) identity raises a typed refusal, not a bare ValueError
# ---------------------------------------------------------------------------


class TestInvalidIdentityTypedRefusal:
    def test_short_identity_raises_lane_computation_error_not_value_error(self, tmp_path: Path) -> None:
        repo_root = _make_repo_with_owned_files(tmp_path)
        mission_slug = "modern-mission-01KV6510"
        feature_dir = _feature_dir(tmp_path, mission_slug)

        with pytest.raises(LaneComputationError):
            _finalize(repo_root, feature_dir, mission_slug, mission_id="short12")


# ---------------------------------------------------------------------------
# status/aggregate.py destination-ref composition
# ---------------------------------------------------------------------------


def _write_lanes_json(feature_dir: Path, *, mission_branch: str) -> None:
    manifest = _manifest(mission_branch)
    (feature_dir / "lanes.json").write_text(json.dumps(manifest.to_dict(), indent=2), encoding="utf-8")


def _mission_status(
    tmp_path: Path,
    *,
    mission_slug: str,
    mission_id: str | None,
    coordination_branch: str | None,
) -> MissionStatus:
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    return MissionStatus(
        mission_slug=mission_slug,
        mission_id=mission_id,
        mid8=(mission_id or "")[:8],
        topology="coordination" if coordination_branch else "legacy",
        read_dir=feature_dir,
        repo_root=tmp_path,
        coordination_branch=coordination_branch,
    )


class TestDestinationRefPrefersRecordedBranch:
    def test_backfilled_legacy_mission_returns_recorded_branch(self, tmp_path: Path) -> None:
        mission_slug = "057-foo"
        feature_dir = tmp_path / "kitty-specs" / mission_slug
        feature_dir.mkdir(parents=True)
        _write_lanes_json(feature_dir, mission_branch="kitty/mission-057-foo")

        status = _mission_status(
            tmp_path,
            mission_slug=mission_slug,
            mission_id="01KV6510ATWWFXS3K5ZJ9E5008",
            coordination_branch=None,
        )

        assert status._destination_ref() == "kitty/mission-057-foo"

    def test_invalid_identity_with_no_recorded_branch_raises_typed_refusal(self, tmp_path: Path) -> None:
        mission_slug = "modern-mission"
        feature_dir = tmp_path / "kitty-specs" / mission_slug
        feature_dir.mkdir(parents=True)

        status = _mission_status(
            tmp_path,
            mission_slug=mission_slug,
            mission_id="abc",
            coordination_branch=None,
        )

        with pytest.raises(BranchIdentityUnresolved):
            status._destination_ref()

    def test_coordination_mission_returns_coordination_branch(self, tmp_path: Path) -> None:
        mission_slug = "057-foo"
        status = _mission_status(
            tmp_path,
            mission_slug=mission_slug,
            mission_id="01KV6510ATWWFXS3K5ZJ9E5008",
            coordination_branch="kitty/coord-057-foo",
        )

        assert status._destination_ref() == "kitty/coord-057-foo"
