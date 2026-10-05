"""Unit tests for the WP01 (#4758) pure lane-compute-and-persist core.

Covers:
- T002: ``compute_and_write_lanes`` writes a valid ``lanes.json`` from
  already-resolved inputs, with zero ``typer``/console/JSON/``policy``
  imports (layer purity, C-001).
- T005/T006: determinism (same inputs -> byte-identical ``lanes.json``) and
  idempotence (re-running the core twice produces the same content) per
  NFR-004.
- The glob-revalidation failure path raises ``LaneGlobValidationError``
  without writing ``lanes.json``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mission_runtime import MissionTopology

from specify_cli.lanes.compute_and_persist import (
    LaneGlobValidationError,
    compute_and_write_lanes,
)
from specify_cli.lanes.compute import LaneComputationError, LaneMembershipFrozenError
from specify_cli.lanes.frozen_membership import FrozenLaneMembership
from specify_cli.lanes.models import LanesManifest
from specify_cli.lanes.persistence import read_lanes_json
from specify_cli.ownership.models import OwnershipManifest, WorkProductKind
from specify_cli.status import WPMetadata

pytestmark = [pytest.mark.unit, pytest.mark.fast]


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


def _feature_dir(tmp_path: Path, mission_slug: str = "test-mission") -> Path:
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    return feature_dir


class TestComputeAndWriteLanesCore:
    """T002: the pure core writes lanes.json from already-resolved inputs."""

    def test_writes_lanes_json_with_resolved_sha_and_mission_id(self, tmp_path: Path) -> None:
        repo_root = _make_repo_with_owned_files(tmp_path)
        feature_dir = _feature_dir(tmp_path)

        wp_manifests = {
            "WP01": _wp_manifest(("src/wp01/**",), "src/wp01/"),
            "WP02": _wp_manifest(("src/wp02/**",), "src/wp02/"),
        }
        wp_frontmatters = {
            "WP01": WPMetadata(work_package_id="WP01", title="WP01"),
            "WP02": WPMetadata(work_package_id="WP02", title="WP02"),
        }

        lanes_path, lanes_manifest = compute_and_write_lanes(
            feature_dir,
            repo_root,
            "test-mission",
            wp_manifests,
            {"WP01": [], "WP02": []},
            wp_frontmatters,
            {"WP01": "WP01 body", "WP02": "WP02 body"},
            "main",
            planning_commit_sha="deadbeef" * 5,
            mission_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
            topology=MissionTopology.LANES,
        )

        assert lanes_path == feature_dir / "lanes.json"
        assert lanes_path.exists()
        assert lanes_manifest.planning_commit_sha == "deadbeef" * 5
        assert lanes_manifest.mission_id == "01ARZ3NDEKTSV4RRFFQ69G5FAV"
        assert lanes_manifest.mission_slug == "test-mission"

        reread = read_lanes_json(feature_dir)
        assert reread is not None
        assert reread.planning_commit_sha == "deadbeef" * 5
        wp_ids = {wp_id for lane in reread.lanes for wp_id in lane.wp_ids}
        assert wp_ids == {"WP01", "WP02"}

    def test_tolerates_none_planning_commit_sha_and_mission_id(self, tmp_path: Path) -> None:
        repo_root = _make_repo_with_owned_files(tmp_path)
        feature_dir = _feature_dir(tmp_path)

        wp_manifests = {"WP01": _wp_manifest(("src/wp01/**",), "src/wp01/")}
        wp_frontmatters = {"WP01": WPMetadata(work_package_id="WP01", title="WP01")}

        _lanes_path, lanes_manifest = compute_and_write_lanes(
            feature_dir,
            repo_root,
            "test-mission",
            wp_manifests,
            {"WP01": []},
            wp_frontmatters,
            {"WP01": "WP01 body"},
            "main",
            planning_commit_sha=None,
            mission_id=None,
            topology=MissionTopology.LANES,
        )

        assert lanes_manifest.planning_commit_sha is None
        assert lanes_manifest.mission_id is None

    def test_glob_validation_failure_raises_and_writes_nothing(self, tmp_path: Path) -> None:
        # repo_root has NO src/wp01 directory at all, and the entry is a
        # literal path (no glob metacharacters), so it must hard-error.
        repo_root = tmp_path
        feature_dir = _feature_dir(tmp_path)

        wp_manifests = {
            "WP01": _wp_manifest(("src/wp01/missing_literal_file.py",), "src/wp01/"),
        }
        wp_frontmatters = {"WP01": WPMetadata(work_package_id="WP01", title="WP01")}

        with pytest.raises(LaneGlobValidationError) as exc_info:
            compute_and_write_lanes(
                feature_dir,
                repo_root,
                "test-mission",
                wp_manifests,
                {"WP01": []},
                wp_frontmatters,
                {"WP01": "WP01 body"},
                "main",
                planning_commit_sha=None,
                mission_id=None,
                topology=MissionTopology.LANES,
            )

        assert exc_info.value.result.errors
        assert not (feature_dir / "lanes.json").exists()


class TestComputeAndWriteLanesDeterminism:
    """NFR-004: rebuilding lanes.json from the same inputs is deterministic."""

    def _inputs(self, tmp_path: Path) -> tuple[Path, Path, dict[str, OwnershipManifest], dict[str, WPMetadata]]:
        repo_root = _make_repo_with_owned_files(tmp_path)
        feature_dir = _feature_dir(tmp_path)
        wp_manifests = {
            "WP01": _wp_manifest(("src/wp01/**",), "src/wp01/"),
            "WP02": _wp_manifest(("src/wp02/**",), "src/wp02/"),
        }
        wp_frontmatters = {
            "WP01": WPMetadata(work_package_id="WP01", title="WP01"),
            "WP02": WPMetadata(work_package_id="WP02", title="WP02"),
        }
        return repo_root, feature_dir, wp_manifests, wp_frontmatters

    def test_same_inputs_produce_byte_identical_lanes_json(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # ``compute_lanes`` stamps ``computed_at`` with the real wall clock;
        # pin it so two back-to-back calls over identical inputs are
        # byte-identical (NFR-004 determinism), not merely
        # content-equivalent-except-timestamp.
        monkeypatch.setattr("specify_cli.lanes.compute.now_utc_iso", lambda: "2026-01-01T00:00:00+00:00")
        repo_root, feature_dir, wp_manifests, wp_frontmatters = self._inputs(tmp_path)
        wp_dependencies = {"WP01": [], "WP02": ["WP01"]}
        wp_bodies = {"WP01": "WP01 body", "WP02": "WP02 body"}

        first_path, _ = compute_and_write_lanes(
            feature_dir,
            repo_root,
            "test-mission",
            wp_manifests,
            wp_dependencies,
            wp_frontmatters,
            wp_bodies,
            "main",
            planning_commit_sha="abc123",
            mission_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
            topology=MissionTopology.LANES,
        )
        first_bytes = first_path.read_bytes()

        # Idempotent rebuild: same inputs, run again over the same directory.
        second_path, _ = compute_and_write_lanes(
            feature_dir,
            repo_root,
            "test-mission",
            wp_manifests,
            wp_dependencies,
            wp_frontmatters,
            wp_bodies,
            "main",
            planning_commit_sha="abc123",
            mission_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
            topology=MissionTopology.LANES,
            frozen=FrozenLaneMembership.empty(),
        )
        second_bytes = second_path.read_bytes()

        assert first_bytes == second_bytes


class TestComputeAndWriteLanesFrozenMembership:
    """#5573 T007: the writer threads ``frozen`` through and re-asserts it before writing."""

    def _write(self, tmp_path: Path, wp_manifests: dict[str, OwnershipManifest], *, frozen: FrozenLaneMembership | None = None) -> tuple[Path, LanesManifest]:
        repo_root = tmp_path
        feature_dir = tmp_path / "kitty-specs" / "test-mission"
        wp_frontmatters = {wp: WPMetadata(work_package_id=wp, title=wp) for wp in wp_manifests}
        written: tuple[Path, LanesManifest] = compute_and_write_lanes(
            feature_dir,
            repo_root,
            "test-mission",
            wp_manifests,
            dict.fromkeys(wp_manifests, []),
            wp_frontmatters,
            {wp: f"{wp} body" for wp in wp_manifests},
            "main",
            planning_commit_sha=None,
            mission_id=None,
            topology=MissionTopology.LANES,
            frozen=frozen,
        )
        return written

    def _first_finalize(self, tmp_path: Path) -> tuple[dict[str, OwnershipManifest], Path]:
        _make_repo_with_owned_files(tmp_path)
        _feature_dir(tmp_path)
        manifests = {
            "WP01": _wp_manifest(("src/wp01/**",), "src/wp01/"),
            "WP02": _wp_manifest(("src/wp02/**",), "src/wp02/"),
        }
        lanes_path, first = self._write(tmp_path, manifests)
        assert {wp: lane.lane_id for lane in first.lanes for wp in lane.wp_ids} == {"WP01": "lane-a", "WP02": "lane-b"}
        return manifests, lanes_path

    def test_honoured_frozen_membership_writes_normally(self, tmp_path: Path) -> None:
        manifests, _ = self._first_finalize(tmp_path)
        manifests["WP01"] = _wp_manifest(("src/wp01/**", "src/wp02/**"), "src/wp01/")
        frozen = FrozenLaneMembership(bindings={"WP02": "lane-b"}, retired_wp_ids=frozenset())
        _, manifest = self._write(tmp_path, manifests, frozen=frozen)
        assert {wp: lane.lane_id for lane in manifest.lanes for wp in lane.wp_ids} == {"WP01": "lane-b", "WP02": "lane-b"}
        reread = read_lanes_json(tmp_path / "kitty-specs" / "test-mission")
        assert reread is not None
        assert [lane.lane_id for lane in reread.lanes] == ["lane-b"]

    def test_conflicting_frozen_membership_raises_and_leaves_lanes_json_byte_identical(self, tmp_path: Path) -> None:
        manifests, lanes_path = self._first_finalize(tmp_path)
        before = lanes_path.read_bytes()
        manifests["WP01"] = _wp_manifest(("src/wp01/**", "src/wp02/**"), "src/wp01/")
        frozen = FrozenLaneMembership(bindings={"WP01": "lane-a", "WP02": "lane-b"}, retired_wp_ids=frozenset())
        with pytest.raises(LaneMembershipFrozenError) as excinfo:
            self._write(tmp_path, manifests, frozen=frozen)
        assert excinfo.value.reason == "started_lanes_collapsed"
        assert lanes_path.read_bytes() == before

    def test_recompute_over_a_code_lane_manifest_without_freeze_evidence_refuses(self, tmp_path: Path) -> None:
        """``frozen=None`` means "nobody gathered evidence", not "nothing frozen": the #5573 move must not come back."""
        manifests, lanes_path = self._first_finalize(tmp_path)
        before = lanes_path.read_bytes()
        manifests["WP01"] = _wp_manifest(("src/wp01/**", "src/wp02/**"), "src/wp01/")
        with pytest.raises(LaneComputationError, match="freeze evidence") as excinfo:
            self._write(tmp_path, manifests)
        assert not isinstance(excinfo.value, LaneMembershipFrozenError)
        assert lanes_path.read_bytes() == before
        # Gathered evidence that happens to freeze nothing is a decision, and is accepted.
        self._write(tmp_path, manifests, frozen=FrozenLaneMembership.empty())

    def test_post_check_refuses_a_manifest_that_violates_bindings(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Defence in depth: even if compute_lanes regressed, the writer refuses before writing."""
        manifests, lanes_path = self._first_finalize(tmp_path)
        before = lanes_path.read_bytes()
        violating = read_lanes_json(tmp_path / "kitty-specs" / "test-mission")
        assert violating is not None
        monkeypatch.setattr("specify_cli.lanes.compute_and_persist.compute_lanes", lambda **_kwargs: violating)
        frozen = FrozenLaneMembership(bindings={"WP02": "lane-z"}, retired_wp_ids=frozenset())
        with pytest.raises(LaneMembershipFrozenError) as excinfo:
            self._write(tmp_path, manifests, frozen=frozen)
        assert excinfo.value.reason == "started_lanes_collapsed"
        assert excinfo.value.conflicts[0].wp_ids == ("WP02",)
        assert excinfo.value.conflicts[0].recorded_lanes == ("lane-z",)
        assert lanes_path.read_bytes() == before
