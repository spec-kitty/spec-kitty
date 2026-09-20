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

from specify_cli.lanes.compute_and_persist import (
    LaneGlobValidationError,
    compute_and_write_lanes,
)
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
        )
        second_bytes = second_path.read_bytes()

        assert first_bytes == second_bytes
