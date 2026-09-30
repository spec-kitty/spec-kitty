"""Tests for lane worktree topology analysis."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.core.worktree_topology import (
    FeatureTopology,
    WPTopologyEntry,
    materialize_worktree_topology,
    render_topology_json,
)
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json

pytestmark = pytest.mark.fast


def _manifest(mission_slug: str = "002-feature") -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=mission_slug,
        mission_id=f"mission-{mission_slug}",
        mission_branch=f"kitty/mission-{mission_slug}",
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=("WP01", "WP02"),
                write_scope=("src/**",),
                predicted_surfaces=("core",),
                depends_on_lanes=(),
                parallel_group=0,
            ),
            ExecutionLane(
                lane_id="lane-b",
                wp_ids=("WP03",),
                write_scope=("docs/**",),
                predicted_surfaces=("docs",),
                depends_on_lanes=("lane-a",),
                parallel_group=1,
            ),
        ],
        computed_at="2026-04-04T10:00:00Z",
        computed_from="test",
    )


class TestWPTopologyEntry:
    def test_defaults(self) -> None:
        entry = WPTopologyEntry(
            wp_id="WP01",
            lane_id="lane-a",
            lane_wp_ids=["WP01", "WP02"],
            branch_name="kitty/mission-002-feature-lane-a",
            base_branch="kitty/mission-002-feature",
        )
        assert entry.dependencies == []
        assert entry.lane == "planned"
        assert entry.worktree_exists is False
        assert entry.commits_ahead_of_base == 0


class TestFeatureTopology:
    def test_has_stacking_when_lane_is_shared(self) -> None:
        topology = FeatureTopology(
            mission_slug="002-feature",
            target_branch="main",
            mission_branch="kitty/mission-002-feature",
            entries=[
                WPTopologyEntry(
                    wp_id="WP01",
                    lane_id="lane-a",
                    lane_wp_ids=["WP01", "WP02"],
                    branch_name="kitty/mission-002-feature-lane-a",
                    base_branch="kitty/mission-002-feature",
                )
            ],
        )
        assert topology.has_stacking is True
        assert topology.get_actual_base_for_wp("WP01") == "kitty/mission-002-feature"


class TestRenderTopologyJson:
    def test_json_markers_and_payload(self) -> None:
        topology = FeatureTopology(
            mission_slug="002-feature",
            target_branch="main",
            mission_branch="kitty/mission-002-feature",
            entries=[
                WPTopologyEntry(
                    wp_id="WP01",
                    lane_id="lane-a",
                    lane_wp_ids=["WP01", "WP02"],
                    branch_name="kitty/mission-002-feature-lane-a",
                    base_branch="kitty/mission-002-feature",
                    lane="doing",
                    worktree_exists=True,
                    commits_ahead_of_base=3,
                ),
                WPTopologyEntry(
                    wp_id="WP02",
                    lane_id="lane-a",
                    lane_wp_ids=["WP01", "WP02"],
                    branch_name="kitty/mission-002-feature-lane-a",
                    base_branch="kitty/mission-002-feature",
                    lane="planned",
                ),
            ],
        )
        lines = render_topology_json(topology, "WP01")
        assert lines[0] == "<!-- WORKTREE_TOPOLOGY -->"
        assert lines[-1] == "<!-- /WORKTREE_TOPOLOGY -->"

        payload = json.loads("\n".join(lines[1:-1]))
        assert payload["mission_slug"] == "002-feature"
        # mission_number is display-only: mission_identity_fields() strips
        # leading zeros, so the slug prefix "002" renders as "2" at the
        # payload boundary. Canonical identity is mission_id (not asserted
        # here because FeatureTopology was constructed without one).
        assert payload["mission_number"] == "2"
        assert payload["mission_type"] == "software-dev"
        assert payload["mission_branch"] == "kitty/mission-002-feature"
        assert payload["shared_lane"] is True
        assert payload["diff_command"] == "git diff kitty/mission-002-feature..HEAD"


class TestMaterializeWorktreeTopology:
    def test_materialize_from_manifest_and_context(self, tmp_path: Path) -> None:
        repo_root = tmp_path
        mission_slug = "002-feature"
        feature_dir = repo_root / "kitty-specs" / mission_slug
        feature_dir.mkdir(parents=True)
        (feature_dir / "meta.json").write_text(
            json.dumps({"feature_number": "002", "mission_slug": mission_slug, "target_branch": "main"}),
            encoding="utf-8",
        )
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir()
        (tasks_dir / "WP01-core.md").write_text("---\nwork_package_id: WP01\ndependencies: []\n---\n")
        (tasks_dir / "WP02-api.md").write_text("---\nwork_package_id: WP02\ndependencies: [WP01]\n---\n")
        (tasks_dir / "WP03-docs.md").write_text("---\nwork_package_id: WP03\ndependencies: [WP02]\n---\n")
        write_lanes_json(feature_dir, _manifest(mission_slug))

        worktree = repo_root / ".worktrees" / f"{mission_slug}-lane-a"
        worktree.mkdir(parents=True)
        (repo_root / ".git").mkdir()
        (repo_root / ".kittify" / "workspaces").mkdir(parents=True, exist_ok=True)
        (repo_root / ".kittify" / "workspaces" / f"{mission_slug}-lane-a.json").write_text(
            json.dumps(
                {
                    "wp_id": "WP02",
                    "mission_slug": mission_slug,
                    "worktree_path": f".worktrees/{mission_slug}-lane-a",
                    "branch_name": f"kitty/mission-{mission_slug}-lane-a",
                    "base_branch": f"kitty/mission-{mission_slug}",
                    "base_commit": "abc123",
                    "dependencies": ["WP01"],
                    "created_at": "2026-01-25T12:00:00Z",
                    "created_by": "implement-command-lane",
                    "vcs_backend": "git",
                    "lane_id": "lane-a",
                    "lane_wp_ids": ["WP01", "WP02"],
                    "current_wp": "WP02",
                }
            ),
            encoding="utf-8",
        )

        topology = materialize_worktree_topology(repo_root, mission_slug)

        assert topology.mission_branch == f"kitty/mission-{mission_slug}"
        assert [entry.wp_id for entry in topology.entries] == ["WP01", "WP02", "WP03"]
        assert topology.get_entry("WP01").lane_id == "lane-a"
        assert topology.get_entry("WP03").lane_id == "lane-b"
